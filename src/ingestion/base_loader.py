"""
BaseLoader — Abstract base class for all Northstar V3 data loaders.

Every loader in src/ingestion/ inherits from this. It enforces:
1. Point-in-time (PIT) compliance via as_of_date parameter
2. Data freshness checking with configurable staleness thresholds
3. Standardized return types (always pd.DataFrame or pd.Series)
4. Logging with structured metadata (loader name, as_of_date, rows returned, load time)
5. Caching with TTL to avoid redundant disk reads within a single run
"""

import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd

logger = logging.getLogger(__name__)


# Custom Exceptions
#
# PITViolationError and StaleDataError are CORRECTNESS failures — look-ahead bias
# and critically-stale data silently produce wrong signals and must NEVER be
# swallowed. They deliberately subclass BaseException (not Exception) so the
# loaders' blanket `except Exception: return empty_frame` graceful-degradation
# handlers cannot catch them: previously strict-mode PIT enforcement was
# decorative because every load_*() wrapped its body in `except Exception` and
# turned a PIT violation into a silent empty frame. Explicit handlers
# (`except PITViolationError` / `except StaleDataError`, as in the tests) still
# catch them normally; only broad Exception handlers are bypassed, which is the
# intended behaviour — these should crash the pipeline loudly.
class PITViolationError(BaseException):
    """Raised when loaded data contains dates after as_of_date — lookahead bias detected."""
    pass


class StaleDataError(BaseException):
    """Raised when data is older than the hard maximum staleness threshold."""
    pass


class StaleDataWarning(UserWarning):
    """Warning when data is older than the soft staleness threshold but within hard max."""
    pass


class DataNotFoundError(Exception):
    """Raised when expected data files do not exist."""
    pass


class DataSchemaError(Exception):
    """Raised when loaded data does not match expected schema."""
    pass


class BaseLoader(ABC):
    """
    Abstract base class for all data loaders.
    
    All loaders must implement the load() method and can use the provided
    validation and caching utilities.
    """
    
    def __init__(self, config: Dict[str, Any], cache_ttl_seconds: int = 300):
        """
        Initialize the base loader.
        
        Args:
            config: System configuration dictionary (loaded from config.yaml)
            cache_ttl_seconds: Time-to-live for cache entries (default: 5 minutes)
        """
        self.config = config
        self.cache_ttl_seconds = cache_ttl_seconds
        self._cache: Dict[str, tuple[pd.DataFrame, float]] = {}
        
        # Extract ingestion config
        self.ingestion_config = config.get('ingestion', {})
        self.paths_config = self.ingestion_config.get('paths', {})
        self.staleness_config = self.ingestion_config.get('staleness_thresholds', {})
        self.pit_config = self.ingestion_config.get('pit', {})
        self.reporting_lags = self.ingestion_config.get('reporting_lags', {})
        
        # PIT enforcement settings
        self.pit_enabled = self.pit_config.get('enabled', True)
        self.pit_strict_mode = self.pit_config.get('strict_mode', True)
        
        logger.debug(
            f"Initialized {self.__class__.__name__} with cache_ttl={cache_ttl_seconds}s, "
            f"pit_enabled={self.pit_enabled}, strict_mode={self.pit_strict_mode}"
        )
    
    @abstractmethod
    def load(self, as_of_date: datetime, **kwargs) -> pd.DataFrame:
        """
        Load data as of a specific date.
        
        All subclasses must implement this method.
        
        Args:
            as_of_date: The point-in-time date for data loading
            **kwargs: Additional loader-specific parameters
            
        Returns:
            DataFrame with the loaded data
        """
        pass
    
    def _validate_pit(
        self,
        df: pd.DataFrame,
        date_col: str,
        as_of_date: datetime
    ) -> None:
        """
        Validate point-in-time compliance.
        
        Raises PITViolationError if any row has a date strictly after as_of_date.
        
        Args:
            df: DataFrame to validate
            date_col: Name of the date column to check
            as_of_date: The as-of date for PIT enforcement
            
        Raises:
            PITViolationError: If lookahead bias is detected
        """
        if not self.pit_enabled:
            logger.debug("PIT validation disabled in config")
            return
        
        if df.empty:
            return

        if date_col not in df.columns:
            # N4: a missing date column means PIT compliance cannot be verified.
            # In strict mode that is a schema failure, not a warning to swallow —
            # a silently-unvalidated frame is exactly how look-ahead slips through.
            msg = f"PIT validation could not run: date column '{date_col}' not found in DataFrame"
            if self.pit_strict_mode:
                logger.error(msg)
                raise DataSchemaError(msg)
            logger.warning(msg)
            return
        
        # Convert to datetime for comparison
        dates = pd.to_datetime(df[date_col], errors='coerce')
        as_of_ts = pd.Timestamp(as_of_date)
        
        # Find violations
        violations = dates > as_of_ts
        num_violations = violations.sum()
        
        if num_violations > 0:
            violation_dates = dates[violations].unique()
            error_msg = (
                f"PIT violation detected: {num_violations} rows have dates after {as_of_date}. "
                f"Violating dates: {violation_dates[:5].tolist()}"
            )
            
            if self.pit_strict_mode:
                logger.error(error_msg)
                raise PITViolationError(error_msg)
            else:
                logger.warning(error_msg)
    
    def _check_freshness(
        self,
        file_path: Path,
        max_age_hours: int,
        hard_max_hours: Optional[int] = None
    ) -> None:
        """
        Check data freshness based on file modification time.
        
        Emits StaleDataWarning if file is older than max_age_hours.
        Raises StaleDataError if file is older than hard_max_hours.
        
        Args:
            file_path: Path to the data file
            max_age_hours: Soft threshold for staleness warning
            hard_max_hours: Hard threshold for staleness error (optional)
            
        Raises:
            StaleDataError: If data exceeds hard maximum age
        """
        if not file_path.exists():
            raise DataNotFoundError(f"Data file not found: {file_path}")
        
        # Get file modification time
        mod_time = datetime.fromtimestamp(file_path.stat().st_mtime)
        age_hours = (datetime.now() - mod_time).total_seconds() / 3600
        
        # Check hard threshold first
        if hard_max_hours and age_hours > hard_max_hours:
            error_msg = (
                f"Data critically stale: {file_path.name} is {age_hours:.1f} hours old "
                f"(hard max: {hard_max_hours} hours)"
            )
            logger.error(error_msg)
            raise StaleDataError(error_msg)
        
        # Check soft threshold
        if age_hours > max_age_hours:
            warning_msg = (
                f"Data stale: {file_path.name} is {age_hours:.1f} hours old "
                f"(threshold: {max_age_hours} hours)"
            )
            logger.warning(warning_msg)
            # Emit warning but don't raise
    
    def _get_cached(self, cache_key: str) -> Optional[pd.DataFrame]:
        """
        Retrieve data from cache if available and not expired.
        
        Args:
            cache_key: Unique key for the cached data
            
        Returns:
            Cached DataFrame or None if not found/expired
        """
        if cache_key not in self._cache:
            return None
        
        df, timestamp = self._cache[cache_key]
        age_seconds = time.time() - timestamp
        
        if age_seconds > self.cache_ttl_seconds:
            # Cache expired
            del self._cache[cache_key]
            logger.debug(f"Cache expired for key: {cache_key}")
            return None
        
        logger.debug(f"Cache hit for key: {cache_key} (age: {age_seconds:.1f}s)")
        return df.copy()
    
    def _set_cached(self, cache_key: str, df: pd.DataFrame) -> None:
        """
        Store data in cache with current timestamp.
        
        Args:
            cache_key: Unique key for the cached data
            df: DataFrame to cache
        """
        self._cache[cache_key] = (df.copy(), time.time())
        logger.debug(f"Cached data for key: {cache_key}")
    
    def _log_load(
        self,
        rows: int,
        cols: int,
        source_path: str,
        elapsed_ms: float,
        as_of_date: Optional[datetime] = None
    ) -> None:
        """
        Log structured metadata about a data load operation.
        
        Args:
            rows: Number of rows loaded
            cols: Number of columns loaded
            source_path: Path to the source data file
            elapsed_ms: Time taken to load in milliseconds
            as_of_date: The as-of date for the load (optional)
        """
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'loader': self.__class__.__name__,
            'source': source_path,
            'rows': rows,
            'cols': cols,
            'elapsed_ms': elapsed_ms,
        }
        
        if as_of_date:
            log_entry['as_of_date'] = as_of_date.isoformat()
        
        logger.info(
            f"Loaded {rows} rows × {cols} cols from {Path(source_path).name} "
            f"in {elapsed_ms:.1f}ms"
        )
        logger.debug(f"Load metadata: {log_entry}")
    
    def _resolve_path(self, path_key: str, default: str = "") -> Path:
        """
        Resolve a data path from configuration.
        
        Args:
            path_key: Key in the paths configuration
            default: Default path if key not found
            
        Returns:
            Resolved Path object
        """
        path_str = self.paths_config.get(path_key, default)
        if not path_str:
            raise DataNotFoundError(f"Path not configured for key: {path_key}")
        
        path = Path(path_str)
        
        # Make relative paths absolute from project root
        if not path.is_absolute():
            # Assume config is relative to project root
            path = Path.cwd() / path
        
        return path
    
    def clear_cache(self) -> None:
        """Clear all cached data."""
        self._cache.clear()
        logger.debug(f"Cleared cache for {self.__class__.__name__}")
