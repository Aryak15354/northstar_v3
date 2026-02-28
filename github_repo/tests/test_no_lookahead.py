"""
No-Lookahead Validation Tests

These tests ensure that the system prevents future data access and maintains
temporal integrity across all components.
"""

import pytest
from datetime import datetime, date, timedelta
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from core.state import UnifiedState, TemporalGuard
from validation.performance_tracker import PerformanceTracker, Return


class TestTemporalGuard:
    """Test temporal protection mechanisms"""
    
    def test_temporal_guard_prevents_future_access(self):
        """Test that temporal guard prevents future data access"""
        current_time = datetime(2024, 1, 15, 10, 0, 0)
        guard = TemporalGuard(current_time)
        
        # Past access should be allowed
        past_time = datetime(2024, 1, 14, 10, 0, 0)
        assert guard.validate_access(past_time) == True
        
        # Current time access should be allowed
        assert guard.validate_access(current_time) == True
        
        # Future access should be denied
        future_time = datetime(2024, 1, 16, 10, 0, 0)
        assert guard.validate_access(future_time) == False
    
    def test_temporal_guard_time_advancement(self):
        """Test that time can only move forward"""
        current_time = datetime(2024, 1, 15, 10, 0, 0)
        guard = TemporalGuard(current_time)
        
        # Forward time movement should work
        new_time = datetime(2024, 1, 15, 11, 0, 0)
        guard.update_current_time(new_time)
        assert guard.current_time == new_time
        
        # Backward time movement should fail
        past_time = datetime(2024, 1, 15, 9, 0, 0)
        with pytest.raises(ValueError, match="Time cannot move backwards"):
            guard.update_current_time(past_time)


class TestUnifiedStateTemporalIntegrity:
    """Test unified state temporal integrity"""
    
    def test_unified_state_prevents_future_snapshots(self):
        """Test that unified state prevents access to future snapshots"""
        current_time = datetime(2024, 1, 15, 10, 0, 0)
        state = UnifiedState(current_time)
        
        # Create snapshot at current time
        snapshot = state.create_snapshot()
        assert snapshot.timestamp == current_time
        
        # Advance time
        new_time = datetime(2024, 1, 15, 11, 0, 0)
        state.advance_time(new_time)
        
        # Should not be able to get snapshot from future
        future_time = datetime(2024, 1, 15, 12, 0, 0)
        with pytest.raises(ValueError, match="Cannot access future state"):
            state.get_historical_snapshot(future_time)
    
    def test_unified_state_time_monotonicity(self):
        """Test that unified state enforces monotonic time"""
        current_time = datetime(2024, 1, 15, 10, 0, 0)
        state = UnifiedState(current_time)
        
        # Forward time advancement should work
        new_time = datetime(2024, 1, 15, 11, 0, 0)
        state.advance_time(new_time)
        assert state.current_time == new_time
        
        # Backward time advancement should fail
        past_time = datetime(2024, 1, 15, 9, 0, 0)
        with pytest.raises(ValueError, match="Time cannot move backwards"):
            state.advance_time(past_time)
    
    def test_unified_state_audit_trail_temporal_consistency(self):
        """Test that audit trail maintains temporal consistency"""
        current_time = datetime(2024, 1, 15, 10, 0, 0)
        state = UnifiedState(current_time)
        
        # Make some state changes
        state.update_state('key1', 'value1')
        
        # Advance time
        new_time = datetime(2024, 1, 15, 11, 0, 0)
        state.advance_time(new_time)
        state.update_state('key2', 'value2')
        
        # Check audit trail temporal ordering
        audit_trail = state.get_audit_trail()
        timestamps = [record['timestamp'] for record in audit_trail]
        
        # Timestamps should be monotonically increasing
        for i in range(1, len(timestamps)):
            assert timestamps[i] >= timestamps[i-1], "Audit trail timestamps not monotonic"


class TestPerformanceTrackerTemporalValidation:
    """Test performance tracker temporal validation"""
    
    def test_performance_tracker_prevents_future_data(self):
        """Test that performance tracker prevents future data recording"""
        current_time = datetime(2024, 1, 15, 10, 0, 0)
        tracker = PerformanceTracker(current_time)
        
        # Past data should be allowed
        past_return = Return(
            date=date(2024, 1, 14),
            portfolio_return=0.01,
            benchmark_return=0.008,
            active_return=0.002,
            gross_return=0.01,
            net_return=0.009
        )
        tracker.record_performance(past_return)  # Should not raise
        
        # Future data should be rejected
        future_return = Return(
            date=date(2024, 1, 16),
            portfolio_return=0.01,
            benchmark_return=0.008,
            active_return=0.002,
            gross_return=0.01,
            net_return=0.009
        )
        
        with pytest.raises(ValueError, match="Cannot record future performance"):
            tracker.record_performance(future_return)
    
    def test_performance_tracker_calculation_period_validation(self):
        """Test that performance calculations validate period dates"""
        current_time = datetime(2024, 1, 15, 10, 0, 0)
        tracker = PerformanceTracker(current_time)
        
        # Add some historical data
        for i in range(5):
            return_date = date(2024, 1, 10 + i)
            return_data = Return(
                date=return_date,
                portfolio_return=0.001 * i,
                benchmark_return=0.0008 * i,
                active_return=0.0002 * i,
                gross_return=0.001 * i,
                net_return=0.0009 * i
            )
            tracker.record_performance(return_data)
        
        # Valid period calculation should work
        start_date = date(2024, 1, 10)
        end_date = date(2024, 1, 14)
        summary = tracker.calculate_period_performance(start_date, end_date)
        assert summary is not None
        
        # Future period calculation should fail
        future_start = date(2024, 1, 16)
        future_end = date(2024, 1, 20)
        
        with pytest.raises(ValueError, match="Cannot calculate performance for future period"):
            tracker.calculate_period_performance(future_start, future_end)


class TestSystemWideTemporalConsistency:
    """Test temporal consistency across integrated system components"""
    
    def test_integrated_system_temporal_consistency(self):
        """Test that all system components maintain temporal consistency"""
        current_time = datetime(2024, 1, 15, 10, 0, 0)
        
        # Initialize components
        unified_state = UnifiedState(current_time)
        performance_tracker = PerformanceTracker(current_time)
        
        # Advance time in unified state
        new_time = datetime(2024, 1, 15, 11, 0, 0)
        unified_state.advance_time(new_time)
        
        # Performance tracker should also be updated
        performance_tracker.update_current_time(new_time)
        
        # Both should have same current time
        assert unified_state.current_time == performance_tracker.temporal_validator.current_time
        
        # Both should prevent future data access
        future_time = datetime(2024, 1, 15, 12, 0, 0)
        
        with pytest.raises(ValueError):
            unified_state.get_historical_snapshot(future_time)
        
        future_return = Return(
            date=date(2024, 1, 16),
            portfolio_return=0.01,
            benchmark_return=0.008,
            active_return=0.002,
            gross_return=0.01,
            net_return=0.009
        )
        
        with pytest.raises(ValueError):
            performance_tracker.record_performance(future_return)
    
    def test_temporal_consistency_after_rollback(self):
        """Test temporal consistency is maintained after state rollback"""
        current_time = datetime(2024, 1, 15, 10, 0, 0)
        state = UnifiedState(current_time)
        
        # Create initial snapshot
        state.update_state('initial_value', 100)
        initial_snapshot = state.create_snapshot()
        
        # Advance time and make changes
        new_time = datetime(2024, 1, 15, 11, 0, 0)
        state.advance_time(new_time)
        state.update_state('modified_value', 200)
        
        # Rollback to initial snapshot
        state.rollback_to_snapshot(initial_snapshot)
        
        # Temporal guard should still prevent future access
        future_time = datetime(2024, 1, 15, 12, 0, 0)
        with pytest.raises(ValueError):
            state.get_historical_snapshot(future_time)
        
        # Current time should still be the advanced time
        assert state.current_time == new_time


class TestTemporalValidationEdgeCases:
    """Test edge cases in temporal validation"""
    
    def test_same_timestamp_access(self):
        """Test access at exactly the current timestamp"""
        current_time = datetime(2024, 1, 15, 10, 0, 0)
        guard = TemporalGuard(current_time)
        
        # Access at exactly current time should be allowed
        assert guard.validate_access(current_time) == True
    
    def test_microsecond_precision_temporal_validation(self):
        """Test temporal validation with microsecond precision"""
        current_time = datetime(2024, 1, 15, 10, 0, 0, 500000)  # 500ms
        guard = TemporalGuard(current_time)
        
        # 1 microsecond in the future should be denied
        future_time = datetime(2024, 1, 15, 10, 0, 0, 500001)
        assert guard.validate_access(future_time) == False
        
        # 1 microsecond in the past should be allowed
        past_time = datetime(2024, 1, 15, 10, 0, 0, 499999)
        assert guard.validate_access(past_time) == True
    
    def test_timezone_aware_temporal_validation(self):
        """Test temporal validation with timezone-aware datetimes"""
        from datetime import timezone
        
        # Current time in UTC
        current_time = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        guard = TemporalGuard(current_time)
        
        # Future time in UTC should be denied
        future_time = datetime(2024, 1, 15, 11, 0, 0, tzinfo=timezone.utc)
        assert guard.validate_access(future_time) == False
        
        # Past time in UTC should be allowed
        past_time = datetime(2024, 1, 15, 9, 0, 0, tzinfo=timezone.utc)
        assert guard.validate_access(past_time) == True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])