"""
Property-Based Tests for Exposure History Tracker

Tests the correctness property:
- Property 6: Exposure History Append
"""

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck, assume
from datetime import datetime, timedelta
import pandas as pd
import tempfile
import shutil
from pathlib import Path

from src.cohesion.exposure_history_tracker import ExposureHistoryTracker
from src.cohesion.state_file_manager import StateFileManager


# Strategies for generating valid exposure values
exposure_value = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
regime_value = st.sampled_from(['early-expansion', 'late-expansion', 'early-contraction', 'late-contraction', 'unknown'])


class TestExposureHistoryProperties:
    """Property-based tests for ExposureHistoryTracker"""
    
    @pytest.fixture
    def temp_data_dir(self):
        """Create temporary data directory for testing"""
        temp_dir = tempfile.mkdtemp()
        data_dir = Path(temp_dir) / "data" / "processed"
        data_dir.mkdir(parents=True, exist_ok=True)
        
        # Temporarily override the paths
        original_paths = {
            'market': StateFileManager.MARKET_STATE_PATH,
            'portfolio': StateFileManager.PORTFOLIO_WEIGHTS_PATH,
            'risk': StateFileManager.RISK_STATE_PATH,
            'exposure': StateFileManager.EXPOSURE_HISTORY_PATH,
            'analytics': StateFileManager.PORTFOLIO_ANALYTICS_PATH,
            'backup': StateFileManager.BACKUP_DIR
        }
        
        StateFileManager.MARKET_STATE_PATH = data_dir / "market_state.parquet"
        StateFileManager.PORTFOLIO_WEIGHTS_PATH = data_dir / "portfolio_weights.parquet"
        StateFileManager.RISK_STATE_PATH = data_dir / "risk_state.parquet"
        StateFileManager.EXPOSURE_HISTORY_PATH = data_dir / "exposure_history.parquet"
        StateFileManager.PORTFOLIO_ANALYTICS_PATH = data_dir / "portfolio_analytics.json"
        StateFileManager.BACKUP_DIR = data_dir / "backups"
        StateFileManager.BACKUP_DIR.mkdir(exist_ok=True)
        
        yield temp_dir
        
        # Restore original paths
        StateFileManager.MARKET_STATE_PATH = original_paths['market']
        StateFileManager.PORTFOLIO_WEIGHTS_PATH = original_paths['portfolio']
        StateFileManager.RISK_STATE_PATH = original_paths['risk']
        StateFileManager.EXPOSURE_HISTORY_PATH = original_paths['exposure']
        StateFileManager.PORTFOLIO_ANALYTICS_PATH = original_paths['analytics']
        StateFileManager.BACKUP_DIR = original_paths['backup']
        
        # Clean up
        shutil.rmtree(temp_dir)
    
    @given(
        allowed=exposure_value,
        actual=exposure_value,
        risk_scaled=exposure_value,
        regime=regime_value,
        stress=exposure_value
    )
    @settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_exposure_history_append(
        self,
        temp_data_dir,
        allowed,
        actual,
        risk_scaled,
        regime,
        stress
    ):
        """
        Property 6: Exposure History Append
        
        For any exposure calculation, the exposure_history file must contain
        a new row with that calculation's timestamp and values.
        
        Validates: Requirements 7.1, 7.2
        """
        state_manager = StateFileManager()
        tracker = ExposureHistoryTracker(state_manager)
        
        # Get initial history count
        initial_history = tracker.get_exposure_history()
        initial_count = len(initial_history)
        
        # Record exposure
        test_date = datetime.now()
        tracker.record_exposure(
            date=test_date,
            allowed_exposure=allowed,
            actual_exposure=actual,
            risk_scaled_exposure=risk_scaled,
            regime=regime,
            stress_score=stress
        )
        
        # Read history
        updated_history = tracker.get_exposure_history()
        
        # Verify append property: history should have one more row
        assert len(updated_history) == initial_count + 1, \
            f"History append failed: expected {initial_count + 1} rows, got {len(updated_history)}"
        
        # Verify the new row contains correct values
        latest_row = updated_history.iloc[-1]
        
        assert abs(latest_row['allowed_exposure'] - allowed) < 1e-10, \
            f"allowed_exposure mismatch: expected {allowed}, got {latest_row['allowed_exposure']}"
        
        assert abs(latest_row['actual_exposure'] - actual) < 1e-10, \
            f"actual_exposure mismatch: expected {actual}, got {latest_row['actual_exposure']}"
        
        assert abs(latest_row['risk_scaled_exposure'] - risk_scaled) < 1e-10, \
            f"risk_scaled_exposure mismatch: expected {risk_scaled}, got {latest_row['risk_scaled_exposure']}"
        
        assert latest_row['regime'] == regime, \
            f"regime mismatch: expected {regime}, got {latest_row['regime']}"
        
        assert abs(latest_row['stress_score'] - stress) < 1e-10, \
            f"stress_score mismatch: expected {stress}, got {latest_row['stress_score']}"
    
    @given(
        num_records=st.integers(min_value=1, max_value=10)
    )
    @settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_multiple_appends(self, temp_data_dir, num_records):
        """
        Test that multiple appends accumulate correctly
        """
        state_manager = StateFileManager()
        tracker = ExposureHistoryTracker(state_manager)
        
        # Clear any existing history from previous test runs
        if state_manager.EXPOSURE_HISTORY_PATH.exists():
            state_manager.EXPOSURE_HISTORY_PATH.unlink()
        
        # Record multiple exposures
        for i in range(num_records):
            tracker.record_exposure(
                date=datetime.now() + timedelta(seconds=i),
                allowed_exposure=0.5,
                actual_exposure=0.5,
                risk_scaled_exposure=0.5,
                regime='expansion',
                stress_score=0.3
            )
        
        # Verify count
        history = tracker.get_exposure_history()
        assert len(history) == num_records, \
            f"Expected {num_records} records, got {len(history)}"
    
    def test_retention_policy(self, temp_data_dir):
        """
        Test that retention policy removes old records
        """
        state_manager = StateFileManager()
        tracker = ExposureHistoryTracker(state_manager)
        
        # Record old exposure (400 days ago)
        old_date = datetime.now() - timedelta(days=400)
        tracker.record_exposure(
            date=old_date,
            allowed_exposure=0.5,
            actual_exposure=0.5,
            risk_scaled_exposure=0.5,
            regime='expansion',
            stress_score=0.3
        )
        
        # Record recent exposure
        recent_date = datetime.now()
        tracker.record_exposure(
            date=recent_date,
            allowed_exposure=0.6,
            actual_exposure=0.6,
            risk_scaled_exposure=0.6,
            regime='expansion',
            stress_score=0.2
        )
        
        # Apply retention policy
        removed = tracker.apply_retention_policy()
        
        # Verify old record was removed
        assert removed == 1, f"Expected 1 record removed, got {removed}"
        
        # Verify only recent record remains
        history = tracker.get_exposure_history()
        assert len(history) == 1
        assert history.iloc[0]['allowed_exposure'] == 0.6
    
    def test_compare_allowed_vs_actual(self, temp_data_dir):
        """
        Test exposure comparison utility
        """
        state_manager = StateFileManager()
        tracker = ExposureHistoryTracker(state_manager)
        
        # Record exposures with known divergence
        for i in range(10):
            tracker.record_exposure(
                date=datetime.now() + timedelta(days=i),
                allowed_exposure=0.5,
                actual_exposure=0.6,  # Always 10% higher
                risk_scaled_exposure=0.5,
                regime='expansion',
                stress_score=0.3
            )
        
        # Compare
        stats = tracker.compare_allowed_vs_actual(lookback_days=30)
        
        # Verify statistics
        assert stats['record_count'] == 10
        assert abs(stats['mean_allowed'] - 0.5) < 1e-10
        assert abs(stats['mean_actual'] - 0.6) < 1e-10
        assert abs(stats['mean_divergence'] - 0.1) < 1e-10
        assert stats['times_actual_exceeded_allowed'] == 10
    
    def test_detect_exposure_violations(self, temp_data_dir):
        """
        Test violation detection
        """
        state_manager = StateFileManager()
        tracker = ExposureHistoryTracker(state_manager)
        
        # Record exposures with some violations
        for i in range(5):
            # Normal exposure
            tracker.record_exposure(
                date=datetime.now() + timedelta(days=i),
                allowed_exposure=0.5,
                actual_exposure=0.5,
                risk_scaled_exposure=0.5,
                regime='expansion',
                stress_score=0.3
            )
        
        for i in range(5, 10):
            # Violation: actual > allowed by more than tolerance
            tracker.record_exposure(
                date=datetime.now() + timedelta(days=i),
                allowed_exposure=0.5,
                actual_exposure=0.7,  # 20% higher
                risk_scaled_exposure=0.5,
                regime='expansion',
                stress_score=0.3
            )
        
        # Detect violations (5% tolerance)
        violations = tracker.detect_exposure_violations(tolerance=0.05, lookback_days=30)
        
        # Should find 5 violations
        assert len(violations) == 5, f"Expected 5 violations, found {len(violations)}"
    
    def test_get_exposure_by_regime(self, temp_data_dir):
        """
        Test regime-based exposure statistics
        """
        state_manager = StateFileManager()
        tracker = ExposureHistoryTracker(state_manager)
        
        # Record exposures for different regimes
        regimes = ['early-expansion', 'late-expansion', 'early-contraction']
        for regime in regimes:
            for i in range(3):
                tracker.record_exposure(
                    date=datetime.now() + timedelta(days=i),
                    allowed_exposure=0.5,
                    actual_exposure=0.5,
                    risk_scaled_exposure=0.5,
                    regime=regime,
                    stress_score=0.3
                )
        
        # Get regime statistics
        regime_stats = tracker.get_exposure_by_regime()
        
        # Verify all regimes are present
        assert len(regime_stats) == 3
        assert all(regime in regime_stats.index for regime in regimes)
    
    def test_date_range_filtering(self, temp_data_dir):
        """
        Test filtering exposure history by date range
        """
        state_manager = StateFileManager()
        tracker = ExposureHistoryTracker(state_manager)
        
        # Record exposures over 10 days
        base_date = datetime(2025, 1, 1)
        for i in range(10):
            tracker.record_exposure(
                date=base_date + timedelta(days=i),
                allowed_exposure=0.5,
                actual_exposure=0.5,
                risk_scaled_exposure=0.5,
                regime='expansion',
                stress_score=0.3
            )
        
        # Filter to middle 5 days
        start_date = base_date + timedelta(days=3)
        end_date = base_date + timedelta(days=7)
        filtered = tracker.get_exposure_history(start_date=start_date, end_date=end_date)
        
        # Should have 5 records
        assert len(filtered) == 5, f"Expected 5 records, got {len(filtered)}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
