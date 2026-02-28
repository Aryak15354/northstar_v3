"""
Exposure History Tracker

Maintains a time series of exposure decisions for analysis and validation.
Tracks:
- allowed_exposure (from market brain)
- actual_exposure (from portfolio)
- risk_scaled_exposure (from risk calculation)
- regime and stress_score (context)

Implements 365-day retention policy and provides utilities for comparing
allowed vs actual exposure over time.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional
import pandas as pd

from src.cohesion.state_file_manager import StateFileManager

logger = logging.getLogger(__name__)


class ExposureHistoryTracker:
    """
    Tracks exposure decisions over time.
    
    Maintains a time series in exposure_history.parquet with:
    - date: timestamp of exposure calculation
    - allowed_exposure: exposure allowed by market conditions
    - actual_exposure: actual portfolio exposure
    - risk_scaled_exposure: exposure allowed by risk constraints
    - regime: market regime at time of calculation
    - stress_score: market stress level
    """
    
    # Retention policy
    RETENTION_DAYS = 365
    
    def __init__(self, state_manager: Optional[StateFileManager] = None):
        """
        Initialize the exposure history tracker.
        
        Args:
            state_manager: StateFileManager instance (creates new if None)
        """
        self.state_manager = state_manager or StateFileManager()
        logger.info("ExposureHistoryTracker initialized")
    
    def record_exposure(
        self,
        date: datetime,
        allowed_exposure: float,
        actual_exposure: float,
        risk_scaled_exposure: float,
        regime: str,
        stress_score: float
    ) -> None:
        """
        Record an exposure calculation to history.
        
        Args:
            date: Timestamp of calculation
            allowed_exposure: Exposure allowed by market conditions [0.0, 1.0]
            actual_exposure: Actual portfolio exposure [0.0, 1.0]
            risk_scaled_exposure: Exposure allowed by risk [0.0, 1.0]
            regime: Market regime
            stress_score: Market stress level [0.0, 1.0]
        """
        # Validate inputs
        assert 0.0 <= allowed_exposure <= 1.0, f"allowed_exposure {allowed_exposure} not in [0.0, 1.0]"
        assert 0.0 <= actual_exposure <= 1.0, f"actual_exposure {actual_exposure} not in [0.0, 1.0]"
        assert 0.0 <= risk_scaled_exposure <= 1.0, f"risk_scaled_exposure {risk_scaled_exposure} not in [0.0, 1.0]"
        assert 0.0 <= stress_score <= 1.0, f"stress_score {stress_score} not in [0.0, 1.0]"
        
        # Create history row
        history_row = pd.DataFrame([{
            'date': pd.Timestamp(date),
            'allowed_exposure': allowed_exposure,
            'actual_exposure': actual_exposure,
            'risk_scaled_exposure': risk_scaled_exposure,
            'regime': regime,
            'stress_score': stress_score
        }])
        
        # Append to history
        self.state_manager.append_exposure_history(history_row)
        
        logger.info(
            f"Recorded exposure: date={date}, allowed={allowed_exposure:.1%}, "
            f"actual={actual_exposure:.1%}, risk_scaled={risk_scaled_exposure:.1%}, "
            f"regime={regime}, stress={stress_score:.2f}"
        )
    
    def apply_retention_policy(self) -> int:
        """
        Apply retention policy to exposure history.
        
        Removes records older than RETENTION_DAYS.
        
        Returns:
            Number of records removed
        """
        try:
            # Read current history
            history = self.state_manager.read_exposure_history()
            
            if len(history) == 0:
                logger.debug("No exposure history to clean")
                return 0
            
            # Calculate cutoff date
            cutoff_date = pd.Timestamp(datetime.now() - timedelta(days=self.RETENTION_DAYS))
            
            # Filter to keep only recent records
            initial_count = len(history)
            filtered_history = history[history['date'] >= cutoff_date]
            removed_count = initial_count - len(filtered_history)
            
            if removed_count > 0:
                # Write filtered history back
                self.state_manager._atomic_write_parquet(
                    filtered_history,
                    self.state_manager.EXPOSURE_HISTORY_PATH,
                    self.state_manager.EXPOSURE_HISTORY_SCHEMA
                )
                logger.info(f"Removed {removed_count} old exposure records (retention: {self.RETENTION_DAYS} days)")
            else:
                logger.debug("No old records to remove")
            
            return removed_count
            
        except Exception as e:
            logger.error(f"Failed to apply retention policy: {e}")
            return 0
    
    def get_exposure_history(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> pd.DataFrame:
        """
        Get exposure history for a date range.
        
        Args:
            start_date: Start date (inclusive), None for all history
            end_date: End date (inclusive), None for all history
            
        Returns:
            DataFrame with exposure history
        """
        history = self.state_manager.read_exposure_history()
        
        if len(history) == 0:
            return history
        
        # Filter by date range
        if start_date is not None:
            history = history[history['date'] >= pd.Timestamp(start_date)]
        
        if end_date is not None:
            history = history[history['date'] <= pd.Timestamp(end_date)]
        
        return history
    
    def compare_allowed_vs_actual(
        self,
        lookback_days: int = 60
    ) -> dict:
        """
        Compare allowed vs actual exposure over time.
        
        Args:
            lookback_days: Number of days to analyze
            
        Returns:
            Dictionary with comparison statistics
        """
        try:
            # Get recent history
            start_date = datetime.now() - timedelta(days=lookback_days)
            history = self.get_exposure_history(start_date=start_date)
            
            if len(history) == 0:
                logger.warning("No exposure history available for comparison")
                return {
                    'error': 'No history available',
                    'lookback_days': lookback_days
                }
            
            # Calculate statistics
            divergence = (history['actual_exposure'] - history['allowed_exposure']).abs()
            
            stats = {
                'lookback_days': lookback_days,
                'record_count': len(history),
                'mean_allowed': history['allowed_exposure'].mean(),
                'mean_actual': history['actual_exposure'].mean(),
                'mean_divergence': divergence.mean(),
                'max_divergence': divergence.max(),
                'correlation': history['allowed_exposure'].corr(history['actual_exposure']),
                'times_actual_exceeded_allowed': (history['actual_exposure'] > history['allowed_exposure']).sum(),
                'times_actual_below_allowed': (history['actual_exposure'] < history['allowed_exposure']).sum(),
            }
            
            logger.info(
                f"Exposure comparison ({lookback_days} days): "
                f"mean_divergence={stats['mean_divergence']:.1%}, "
                f"correlation={stats['correlation']:.3f}"
            )
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to compare exposures: {e}")
            return {
                'error': str(e),
                'lookback_days': lookback_days
            }
    
    def get_exposure_by_regime(self) -> pd.DataFrame:
        """
        Get average exposure by regime.
        
        Returns:
            DataFrame with average exposures grouped by regime
        """
        try:
            history = self.state_manager.read_exposure_history()
            
            if len(history) == 0:
                logger.warning("No exposure history available")
                return pd.DataFrame()
            
            # Group by regime and calculate averages
            regime_stats = history.groupby('regime').agg({
                'allowed_exposure': ['mean', 'std', 'count'],
                'actual_exposure': ['mean', 'std'],
                'risk_scaled_exposure': ['mean', 'std'],
                'stress_score': 'mean'
            }).round(4)
            
            logger.info(f"Calculated exposure statistics by regime")
            return regime_stats
            
        except Exception as e:
            logger.error(f"Failed to get exposure by regime: {e}")
            return pd.DataFrame()
    
    def detect_exposure_violations(
        self,
        tolerance: float = 0.05,
        lookback_days: int = 30
    ) -> pd.DataFrame:
        """
        Detect times when actual exposure exceeded allowed exposure.
        
        Args:
            tolerance: Tolerance for violations (default 5%)
            lookback_days: Number of days to analyze
            
        Returns:
            DataFrame with violation records
        """
        try:
            # Get recent history
            start_date = datetime.now() - timedelta(days=lookback_days)
            history = self.get_exposure_history(start_date=start_date)
            
            if len(history) == 0:
                logger.warning("No exposure history available")
                return pd.DataFrame()
            
            # Find violations
            divergence = history['actual_exposure'] - history['allowed_exposure']
            violations = history[divergence > tolerance].copy()
            violations['divergence'] = divergence[divergence > tolerance]
            
            if len(violations) > 0:
                logger.warning(
                    f"Found {len(violations)} exposure violations in last {lookback_days} days "
                    f"(tolerance={tolerance:.1%})"
                )
            else:
                logger.info(f"No exposure violations in last {lookback_days} days")
            
            return violations
            
        except Exception as e:
            logger.error(f"Failed to detect violations: {e}")
            return pd.DataFrame()
