"""
State File Manager - Atomic Operations for Canonical State Files

This module provides atomic read/write operations for all canonical state files
in the Northstar V3 system. It implements the single-source-of-truth pattern with:
- Atomic writes (temp file + rename)
- File locking for concurrent access protection
- Schema validation before commits
- Automatic backups of previous state
"""

import os
import json
import shutil
import logging
import threading
import time
import uuid
from pathlib import Path
from typing import Dict, Any, Optional, Callable, TypeVar
from dataclasses import dataclass
from datetime import datetime
from functools import wraps
import pandas as pd
import numpy as np

from src.options.state_io import ProcessLock

logger = logging.getLogger(__name__)

T = TypeVar('T')

# Per-path in-process locks, guarding the intra-process (multi-thread) case.
# ProcessLock (fcntl.flock) alone is not enough: empirically, on this
# platform, flock does not reliably serialize between file descriptors
# opened by *different threads of the same process* (verified directly --
# real cross-process concurrency via flock is fine; concurrent threads in
# one process occasionally both reported the lock "acquired" at once,
# corrupting a read-modify-write). Acquire this thread lock first, then the
# ProcessLock, and release in the opposite order everywhere, so ordering is
# always consistent and cannot deadlock.
_THREAD_LOCKS: Dict[str, threading.Lock] = {}
_THREAD_LOCKS_GUARD = threading.Lock()


class _FileLock:
    """Combined intra-process (threading.Lock) + inter-process (flock) lock for one target file."""

    def __init__(self, lock_path: Path):
        key = str(lock_path)
        with _THREAD_LOCKS_GUARD:
            if key not in _THREAD_LOCKS:
                _THREAD_LOCKS[key] = threading.Lock()
            self._thread_lock = _THREAD_LOCKS[key]
        self._process_lock = ProcessLock(lock_path)
        self._thread_lock_held = False

    def acquire(self, timeout: float = 30.0) -> bool:
        if not self._thread_lock.acquire(timeout=timeout):
            return False
        self._thread_lock_held = True
        if not self._process_lock.acquire(timeout=timeout):
            self._thread_lock.release()
            self._thread_lock_held = False
            return False
        return True

    def release(self) -> None:
        try:
            self._process_lock.release()
        finally:
            if self._thread_lock_held:
                self._thread_lock.release()
                self._thread_lock_held = False


def retry_on_failure(
    max_retries: int = 3,
    delay: float = 0.5,
    backoff: float = 2.0,
    non_retry_exceptions: tuple[type[BaseException], ...] = (),
):
    """
    Decorator to retry operations on failure with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts
        delay: Initial delay between retries (seconds)
        backoff: Multiplier for delay on each retry
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            current_delay = delay
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if non_retry_exceptions and isinstance(e, non_retry_exceptions):
                        raise
                    last_exception = e
                    if attempt < max_retries:
                        logger.warning(
                            f"Attempt {attempt + 1}/{max_retries + 1} failed for {func.__name__}: {e}. "
                            f"Retrying in {current_delay:.1f}s..."
                        )
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(f"All {max_retries + 1} attempts failed for {func.__name__}")
            
            raise RuntimeError(
                f"Operation {func.__name__} failed after {max_retries + 1} attempts"
            ) from last_exception
        
        return wrapper
    return decorator



@dataclass
class ValidationResult:
    """Result of state file validation"""
    is_valid: bool
    errors: list[str]
    warnings: list[str]


class StateFileManager:
    """
    Manages atomic read/write operations for canonical state files.
    
    Canonical Files:
    - data/processed/market_state.parquet
    - data/processed/portfolio_weights.parquet
    - data/processed/risk_state.parquet
    - data/processed/exposure_history.parquet
    - data/processed/portfolio_analytics.json
    """
    
    # Canonical file paths
    MARKET_STATE_PATH = Path("data/processed/market_state.parquet")
    PORTFOLIO_WEIGHTS_PATH = Path("data/processed/portfolio_weights.parquet")
    RISK_STATE_PATH = Path("data/processed/risk_state.parquet")
    EXPOSURE_HISTORY_PATH = Path("data/processed/exposure_history.parquet")
    PORTFOLIO_ANALYTICS_PATH = Path("data/processed/portfolio_analytics.json")
    
    # Backup directory
    BACKUP_DIR = Path("data/processed/backups")
    
    # Expected schemas
    MARKET_STATE_SCHEMA = {
        'date': 'datetime64[ns]',
        'regime': 'object',
        'risk_on': 'float64',
        'allowed_exposure': 'float64',
        'stress_score': 'float64'
    }
    
    PORTFOLIO_WEIGHTS_SCHEMA = {
        'date': 'datetime64[ns]',
        'symbol': 'object',
        'weight': 'float64',
        'exposure': 'float64'
    }
    
    RISK_STATE_SCHEMA = {
        'date': 'datetime64[ns]',
        'volatility': 'float64',
        'correlation': 'float64',
        'var': 'float64'
    }
    
    EXPOSURE_HISTORY_SCHEMA = {
        'date': 'datetime64[ns]',
        'allowed_exposure': 'float64',
        'actual_exposure': 'float64',
        'risk_scaled_exposure': 'float64',
        'regime': 'object',
        'stress_score': 'float64'
    }
    
    def __init__(self):
        """Initialize the state file manager"""
        # Ensure directories exist
        self.MARKET_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        self.BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        
        logger.info("StateFileManager initialized")
    
    def _file_lock(self, file_path: Path) -> _FileLock:
        """
        Per-target-file exclusive lock (both intra-process and
        cross-process). This module's docstring has long claimed "File
        locking for concurrent access protection", but no lock was ever
        actually taken -- concurrent writers (e.g. the daemon's scheduled
        refresh racing a manually-triggered rebuild, or two threads in the
        same process) shared a fixed `.tmp` path with no serialization, so
        one writer's atomic rename could clobber or interleave with
        another's.
        """
        return _FileLock(file_path.with_name(file_path.name + ".lock"))

    def _validate_schema(self, df: pd.DataFrame, expected_schema: Dict[str, str], file_name: str) -> ValidationResult:
        """
        Validate DataFrame schema matches expected schema.
        
        Args:
            df: DataFrame to validate
            expected_schema: Expected column types
            file_name: Name of file for error messages
            
        Returns:
            ValidationResult with validation status
        """
        errors = []
        warnings = []
        
        # Check for missing columns
        missing_cols = set(expected_schema.keys()) - set(df.columns)
        if missing_cols:
            errors.append(f"{file_name}: Missing columns: {missing_cols}")
        
        # Extra columns are allowed for forward-compatible state evolution.
        # The canonical schema acts as a required minimum contract.
        
        # Check column types
        for col, expected_type in expected_schema.items():
            if col in df.columns:
                actual_type = str(df[col].dtype)
                if actual_type != expected_type:
                    errors.append(
                        f"{file_name}: Column '{col}' has type '{actual_type}', "
                        f"expected '{expected_type}'"
                    )
        
        # Check for NaN in critical columns
        if 'date' in df.columns and df['date'].isna().any():
            errors.append(f"{file_name}: 'date' column contains NaN values")
        
        is_valid = len(errors) == 0
        return ValidationResult(is_valid=is_valid, errors=errors, warnings=warnings)
    
    def _backup_file(self, file_path: Path) -> None:
        """
        Create backup of existing file before overwriting.
        
        Args:
            file_path: Path to file to backup
        """
        if not file_path.exists():
            return
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{file_path.stem}_{timestamp}{file_path.suffix}"
        backup_path = self.BACKUP_DIR / backup_name
        
        try:
            shutil.copy2(file_path, backup_path)
            logger.info(f"Created backup: {backup_path}")
            
            # Clean old backups (keep last 10)
            self._cleanup_old_backups(file_path.stem, keep=10)
        except Exception as e:
            logger.warning(f"Failed to create backup: {e}")
    
    def _cleanup_old_backups(self, file_stem: str, keep: int = 10) -> None:
        """
        Remove old backup files, keeping only the most recent.
        
        Args:
            file_stem: Stem of the file (e.g., 'market_state')
            keep: Number of backups to keep
        """
        backups = sorted(
            self.BACKUP_DIR.glob(f"{file_stem}_*"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        
        for old_backup in backups[keep:]:
            try:
                old_backup.unlink()
                logger.debug(f"Removed old backup: {old_backup}")
            except Exception as e:
                logger.warning(f"Failed to remove old backup {old_backup}: {e}")
    
    @retry_on_failure(
        max_retries=3,
        delay=0.5,
        non_retry_exceptions=(ValueError,),
    )
    def _atomic_write_parquet(
        self,
        df: pd.DataFrame,
        file_path: Path,
        schema: Dict[str, str],
        validate: bool = True,
        _lock_already_held: bool = False,
    ) -> None:
        """
        Atomically write DataFrame to parquet file with retry logic.

        Args:
            df: DataFrame to write
            file_path: Target file path
            schema: Expected schema for validation
            validate: Whether to validate schema before writing
            _lock_already_held: Set True only by a caller (e.g.
                append_exposure_history) that already holds this file's lock
                across its own read-modify-write section, to avoid this
                method re-acquiring the same exclusive lock and deadlocking.
        """
        df = df.copy()
        for column, expected_type in schema.items():
            if expected_type == "datetime64[ns]" and column in df.columns:
                df[column] = pd.to_datetime(df[column], errors="coerce").astype("datetime64[ns]")

        # Validate schema if requested
        if validate:
            validation = self._validate_schema(df, schema, file_path.name)
            if not validation.is_valid:
                raise ValueError(f"Schema validation failed: {validation.errors}")
            if validation.warnings:
                for warning in validation.warnings:
                    logger.warning(warning)

        lock = None if _lock_already_held else self._file_lock(file_path)
        if lock is not None and not lock.acquire(timeout=30.0):
            raise RuntimeError(f"Could not acquire write lock for {file_path} within 30s")
        try:
            # Create backup of existing file
            self._backup_file(file_path)

            # Write to a per-call-unique temp file so two writers can never
            # collide on the same temp path even if the lock above were ever
            # bypassed.
            temp_path = file_path.with_name(f"{file_path.name}.{os.getpid()}.{uuid.uuid4().hex[:8]}.tmp")
            try:
                df.to_parquet(temp_path, index=False, engine='pyarrow')

                # Verify the write by reading it back
                verify_df = pd.read_parquet(temp_path)
                if len(verify_df) != len(df):
                    raise ValueError(f"Verification failed: row count mismatch")

                # Atomic rename
                temp_path.replace(file_path)
                logger.info(f"Atomically wrote {len(df)} rows to {file_path}")

            except Exception as e:
                # Clean up temp file on failure
                if temp_path.exists():
                    temp_path.unlink()
                raise RuntimeError(f"Failed to write {file_path}: {e}") from e
        finally:
            if lock is not None:
                lock.release()

    @retry_on_failure(max_retries=3, delay=0.5)
    def _atomic_write_json(
        self,
        data: Dict[str, Any],
        file_path: Path,
        _lock_already_held: bool = False,
    ) -> None:
        """
        Atomically write dictionary to JSON file with retry logic.

        Args:
            data: Dictionary to write
            file_path: Target file path
            _lock_already_held: See _atomic_write_parquet.
        """
        lock = None if _lock_already_held else self._file_lock(file_path)
        if lock is not None and not lock.acquire(timeout=30.0):
            raise RuntimeError(f"Could not acquire write lock for {file_path} within 30s")
        try:
            # Create backup of existing file
            self._backup_file(file_path)

            # Write to a per-call-unique temp file (see _atomic_write_parquet).
            temp_path = file_path.with_name(f"{file_path.name}.{os.getpid()}.{uuid.uuid4().hex[:8]}.tmp")
            try:
                with open(temp_path, 'w') as f:
                    json.dump(data, f, indent=2, default=str)

                # Verify the write by reading it back
                with open(temp_path, 'r') as f:
                    verify_data = json.load(f)
                if not verify_data:
                    raise ValueError("Verification failed: empty data")

                # Atomic rename
                temp_path.replace(file_path)
                logger.info(f"Atomically wrote JSON to {file_path}")

            except Exception as e:
                # Clean up temp file on failure
                if temp_path.exists():
                    temp_path.unlink()
                raise RuntimeError(f"Failed to write {file_path}: {e}") from e
        finally:
            if lock is not None:
                lock.release()
    

    
    def _restore_from_backup(self, file_path: Path) -> bool:
        """
        Attempt to restore file from most recent backup.
        
        Args:
            file_path: Path to file to restore
            
        Returns:
            True if restoration successful, False otherwise
        """
        try:
            # Find most recent backup
            backups = sorted(
                self.BACKUP_DIR.glob(f"{file_path.stem}_*{file_path.suffix}"),
                key=lambda p: p.stat().st_mtime,
                reverse=True
            )
            
            if not backups:
                logger.error(f"No backups found for {file_path.name}")
                return False
            
            most_recent = backups[0]
            logger.info(f"Restoring {file_path.name} from backup: {most_recent.name}")
            
            # Copy backup to original location
            shutil.copy2(most_recent, file_path)
            
            # Verify restoration
            if file_path.suffix == '.parquet':
                pd.read_parquet(file_path)
            elif file_path.suffix == '.json':
                with open(file_path, 'r') as f:
                    json.load(f)
            
            logger.info(f"✓ Successfully restored {file_path.name} from backup")
            return True
            
        except Exception as e:
            logger.error(f"Failed to restore from backup: {e}")
            return False
    
    @retry_on_failure(max_retries=3, delay=0.5)
    def _read_parquet_with_fallback(self, file_path: Path) -> pd.DataFrame:
        """
        Read parquet file with automatic backup restoration on corruption.
        
        Args:
            file_path: Path to parquet file
            
        Returns:
            DataFrame from file
            
        Raises:
            RuntimeError: If file cannot be read and backup restoration fails
        """
        try:
            return pd.read_parquet(file_path)
        except Exception as e:
            logger.warning(f"Failed to read {file_path.name}: {e}")
            
            # Attempt backup restoration
            if self._restore_from_backup(file_path):
                # Try reading again after restoration
                return pd.read_parquet(file_path)
            else:
                raise RuntimeError(
                    f"Cannot read {file_path.name} and backup restoration failed"
                ) from e
    
    @retry_on_failure(max_retries=3, delay=0.5)
    def _read_json_with_fallback(self, file_path: Path) -> Dict[str, Any]:
        """
        Read JSON file with automatic backup restoration on corruption.
        
        Args:
            file_path: Path to JSON file
            
        Returns:
            Dictionary from file
            
        Raises:
            RuntimeError: If file cannot be read and backup restoration fails
        """
        try:
            with open(file_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to read {file_path.name}: {e}")
            
            # Attempt backup restoration
            if self._restore_from_backup(file_path):
                # Try reading again after restoration
                with open(file_path, 'r') as f:
                    return json.load(f)
            else:
                raise RuntimeError(
                    f"Cannot read {file_path.name} and backup restoration failed"
                ) from e

    # Public API - Market State
    
    def read_market_state(self) -> pd.DataFrame:
        """
        Read canonical market state with automatic error recovery.
        
        Returns:
            DataFrame with market state
            
        Raises:
            FileNotFoundError: If market state file doesn't exist
            RuntimeError: If file is corrupt and backup restoration fails
        """
        if not self.MARKET_STATE_PATH.exists():
            raise FileNotFoundError(f"Market state file not found: {self.MARKET_STATE_PATH}")
        
        df = self._read_parquet_with_fallback(self.MARKET_STATE_PATH)
        logger.debug(f"Read {len(df)} rows from market_state")
        return df
    
    def write_market_state(self, state: pd.DataFrame) -> None:
        """
        Write canonical market state atomically.
        
        Args:
            state: DataFrame with market state
        """
        self._atomic_write_parquet(
            state,
            self.MARKET_STATE_PATH,
            self.MARKET_STATE_SCHEMA
        )
    
    # Public API - Portfolio Weights
    
    def read_portfolio_weights(self) -> pd.DataFrame:
        """
        Read canonical portfolio weights with automatic error recovery.
        
        Returns:
            DataFrame with portfolio weights
            
        Raises:
            FileNotFoundError: If portfolio weights file doesn't exist
            RuntimeError: If file is corrupt and backup restoration fails
        """
        if not self.PORTFOLIO_WEIGHTS_PATH.exists():
            raise FileNotFoundError(f"Portfolio weights file not found: {self.PORTFOLIO_WEIGHTS_PATH}")
        
        df = self._read_parquet_with_fallback(self.PORTFOLIO_WEIGHTS_PATH)
        logger.debug(f"Read {len(df)} rows from portfolio_weights")
        return df
    
    def write_portfolio_weights(self, weights: pd.DataFrame) -> None:
        """
        Write canonical portfolio weights atomically.
        
        Args:
            weights: DataFrame with portfolio weights
        """
        self._atomic_write_parquet(
            weights,
            self.PORTFOLIO_WEIGHTS_PATH,
            self.PORTFOLIO_WEIGHTS_SCHEMA
        )
    
    # Public API - Risk State
    
    def read_risk_state(self) -> pd.DataFrame:
        """
        Read canonical risk state with automatic error recovery.
        
        Returns:
            DataFrame with risk state
            
        Raises:
            FileNotFoundError: If risk state file doesn't exist
            RuntimeError: If file is corrupt and backup restoration fails
        """
        if not self.RISK_STATE_PATH.exists():
            raise FileNotFoundError(f"Risk state file not found: {self.RISK_STATE_PATH}")
        
        df = self._read_parquet_with_fallback(self.RISK_STATE_PATH)
        logger.debug(f"Read {len(df)} rows from risk_state")
        return df
    
    def write_risk_state(self, risk: pd.DataFrame) -> None:
        """
        Write canonical risk state atomically.
        
        Args:
            risk: DataFrame with risk state
        """
        self._atomic_write_parquet(
            risk,
            self.RISK_STATE_PATH,
            self.RISK_STATE_SCHEMA
        )
    
    # Public API - Exposure History
    
    def read_exposure_history(self) -> pd.DataFrame:
        """
        Read exposure history with automatic error recovery.
        
        Returns:
            DataFrame with exposure history
            
        Raises:
            RuntimeError: If file is corrupt and backup restoration fails
        """
        if not self.EXPOSURE_HISTORY_PATH.exists():
            # Return empty DataFrame with correct schema
            return pd.DataFrame(columns=list(self.EXPOSURE_HISTORY_SCHEMA.keys()))
        
        df = self._read_parquet_with_fallback(self.EXPOSURE_HISTORY_PATH)
        logger.debug(f"Read {len(df)} rows from exposure_history")
        return df
    
    def append_exposure_history(self, history_row: pd.DataFrame) -> None:
        """
        Append to exposure history atomically.

        Args:
            history_row: DataFrame with single row to append

        This is read-modify-write, not a plain overwrite: the lock must span
        the read too, or two concurrent callers can both read the same
        existing history, each append their own row on top of it, and the
        second writer's rename silently discards the first writer's row
        (lost update). _atomic_write_parquet is called with
        _lock_already_held=True since we already hold this file's lock here.
        """
        lock = self._file_lock(self.EXPOSURE_HISTORY_PATH)
        if not lock.acquire(timeout=30.0):
            raise RuntimeError(
                f"Could not acquire write lock for {self.EXPOSURE_HISTORY_PATH} within 30s"
            )
        try:
            existing = self.read_exposure_history()
            updated = pd.concat([existing, history_row], ignore_index=True)
            self._atomic_write_parquet(
                updated,
                self.EXPOSURE_HISTORY_PATH,
                self.EXPOSURE_HISTORY_SCHEMA,
                _lock_already_held=True,
            )
        finally:
            lock.release()
    
    # Public API - Portfolio Analytics
    
    def read_portfolio_analytics(self) -> Dict[str, Any]:
        """
        Read portfolio analytics with automatic error recovery.
        
        Returns:
            Dictionary with portfolio analytics
            
        Raises:
            FileNotFoundError: If portfolio analytics file doesn't exist
            RuntimeError: If file is corrupt and backup restoration fails
        """
        if not self.PORTFOLIO_ANALYTICS_PATH.exists():
            raise FileNotFoundError(f"Portfolio analytics file not found: {self.PORTFOLIO_ANALYTICS_PATH}")
        
        data = self._read_json_with_fallback(self.PORTFOLIO_ANALYTICS_PATH)
        logger.debug(f"Read portfolio analytics")
        return data
    
    def write_portfolio_analytics(self, analytics: Dict[str, Any]) -> None:
        """
        Write portfolio analytics atomically.
        
        Args:
            analytics: Dictionary with portfolio analytics
        """
        self._atomic_write_json(analytics, self.PORTFOLIO_ANALYTICS_PATH)
    
    # Public API - Validation
    
    def validate_state_consistency(self) -> ValidationResult:
        """
        Validate consistency across all canonical state files.
        
        Returns:
            ValidationResult with consistency check results
        """
        errors = []
        warnings = []
        
        try:
            # Check if all required files exist
            required_files = [
                self.MARKET_STATE_PATH,
                self.PORTFOLIO_WEIGHTS_PATH,
                self.RISK_STATE_PATH
            ]
            
            for file_path in required_files:
                if not file_path.exists():
                    errors.append(f"Required file missing: {file_path}")
            
            if errors:
                return ValidationResult(is_valid=False, errors=errors, warnings=warnings)
            
            # Read all state files
            market_state = self.read_market_state()
            portfolio_weights = self.read_portfolio_weights()
            risk_state = self.read_risk_state()
            
            # Check date alignment
            market_date = market_state['date'].iloc[-1]
            portfolio_date = portfolio_weights['date'].iloc[-1]
            risk_date = risk_state['date'].iloc[-1]
            
            if market_date != portfolio_date:
                errors.append(
                    f"Date mismatch: market={market_date}, portfolio={portfolio_date}"
                )
            
            if market_date != risk_date:
                warnings.append(
                    f"Date mismatch: market={market_date}, risk={risk_date}"
                )
            
            # Check exposure alignment
            allowed_exposure = market_state['allowed_exposure'].iloc[-1]
            actual_exposure = portfolio_weights['exposure'].sum()
            
            if abs(allowed_exposure - actual_exposure) > 0.05:  # 5% tolerance
                warnings.append(
                    f"Exposure mismatch: allowed={allowed_exposure:.1%}, "
                    f"actual={actual_exposure:.1%}"
                )
            
            # Check for valid ranges
            if not (0.0 <= allowed_exposure <= 1.0):
                errors.append(f"Invalid allowed_exposure: {allowed_exposure}")
            
            if not (0.0 <= actual_exposure <= 1.0):
                errors.append(f"Invalid actual_exposure: {actual_exposure}")
            
            is_valid = len(errors) == 0
            return ValidationResult(is_valid=is_valid, errors=errors, warnings=warnings)
            
        except Exception as e:
            errors.append(f"Validation failed with exception: {e}")
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings)
