"""
Unit Tests for TemporalGuard Edge Cases

These tests cover specific edge cases and boundary conditions that could
cause temporal violations or unexpected behavior.
"""

import pytest
from datetime import datetime, timedelta
import sys
import os

# Add src to path for imports
, '..', '..', 'src'))

from validation.temporal_guard import (
    TemporalGuard, 
    TemporalViolationError, 
    DataDispatcher, 
    TimeController,
    TemporalViolationType,
    TemporalViolation
)

class TestTemporalGuardEdgeCases:
    """Unit tests for TemporalGuard edge cases and boundary conditions"""
    
    def test_exact_boundary_timestamp(self):
        """Test data access at exact simulation date boundary"""
        simulation_date = datetime(2020, 1, 15, 9, 30, 0)
        guard = TemporalGuard(simulation_date)
        
        # Exact match should be allowed
        assert guard.validate_data_access(simulation_date, "exact_boundary") == True
        
        # One microsecond later should be blocked
        future_micro = simulation_date + timedelta(microseconds=1)
        with pytest.raises(TemporalViolationError):
            guard.validate_data_access(future_micro, "microsecond_future")
    
    def test_leap_year_handling(self):
        """Test temporal guard behavior around leap year dates"""
        # Leap year date
        leap_date = datetime(2020, 2, 29, 12, 0, 0)
        guard = TemporalGuard(leap_date)
        
        # Should handle leap year date correctly
        assert guard.validate_data_access(leap_date, "leap_year_test") == True
        
        # Advance past leap year
        next_year = datetime(2021, 2, 28, 12, 0, 0)
        guard.advance_time(next_year, "post_leap_year")
        
        assert guard.get_current_simulation_date() == next_year
    
    def test_year_boundary_crossing(self):
        """Test temporal advancement across year boundaries"""
        year_end = datetime(2019, 12, 31, 23, 59, 59)
        guard = TemporalGuard(year_end)
        
        # Advance to new year
        new_year = datetime(2020, 1, 1, 0, 0, 0)
        guard.advance_time(new_year, "new_year_advancement")
        
        assert guard.get_current_simulation_date() == new_year
        assert guard.validate_data_access(new_year, "new_year_data") == True
    
    def test_large_time_jump_warning(self):
        """Test handling of unusually large time jumps"""
        start_date = datetime(2020, 1, 1)
        guard = TemporalGuard(start_date)
        
        # Jump more than a year (should trigger warning but not error)
        large_jump = start_date + timedelta(days=400)
        guard.advance_time(large_jump, "large_jump_test")
        
        # Should still work but generate warning in violations
        violations = guard.get_violation_summary()
        assert violations['total_violations'] >= 1
        
        # Should find invalid time advancement violation
        violation_types = violations['violation_types']
        assert TemporalViolationType.INVALID_TIME_ADVANCEMENT.value in violation_types
    
    def test_same_date_advancement(self):
        """Test advancing to the same date (should be allowed)"""
        test_date = datetime(2020, 6, 15)
        guard = TemporalGuard(test_date)
        
        # Advancing to same date should be allowed
        guard.advance_time(test_date, "same_date_advancement")
        
        assert guard.get_current_simulation_date() == test_date
        
        # No violations should be recorded
        violations = guard.get_violation_summary()
        assert violations['total_violations'] == 0
    
    def test_checkpoint_restore_edge_cases(self):
        """Test checkpoint and restore with edge cases"""
        start_date = datetime(2020, 1, 1)
        guard = TemporalGuard(start_date)
        
        # Create initial checkpoint
        checkpoint1 = guard.create_checkpoint()
        
        # Make some changes
        guard.advance_time(start_date + timedelta(days=10), "checkpoint_test")
        
        # Trigger some violations
        try:
            guard.validate_data_access(start_date + timedelta(days=20), "violation_test")
        except TemporalViolationError:
            pass
        
        # Create second checkpoint
        checkpoint2 = guard.create_checkpoint()
        
        # Make more changes
        guard.advance_time(start_date + timedelta(days=20), "more_changes")
        
        # Restore to first checkpoint
        guard.restore_checkpoint(checkpoint1)
        
        assert guard.get_current_simulation_date() == start_date
        assert guard.get_violation_summary()['total_violations'] == 0
        
        # Restore to second checkpoint
        guard.restore_checkpoint(checkpoint2)
        
        assert guard.get_current_simulation_date() == start_date + timedelta(days=10)
    
    def test_empty_context_handling(self):
        """Test handling of empty or None context strings"""
        guard = TemporalGuard(datetime(2020, 1, 1))
        
        # Empty context should work
        assert guard.validate_data_access(datetime(2020, 1, 1), "") == True
        
        # None context should be handled gracefully
        assert guard.validate_data_access(datetime(2020, 1, 1), None) == True
    
    def test_violation_accumulation_limits(self):
        """Test behavior when many violations accumulate"""
        guard = TemporalGuard(datetime(2020, 1, 1))
        
        # Generate many violations
        for i in range(100):
            try:
                future_date = datetime(2020, 1, 1) + timedelta(days=i+1)
                guard.validate_data_access(future_date, f"violation_{i}")
            except TemporalViolationError:
                pass
        
        violations = guard.get_violation_summary()
        assert violations['total_violations'] == 100
        
        # Should still function normally
        assert guard.validate_data_access(datetime(2020, 1, 1), "normal_access") == True


class TestDataDispatcherEdgeCases:
    """Unit tests for DataDispatcher edge cases"""
    
    def test_none_data_source_handling(self):
        """Test handling of None or empty data source identifiers"""
        guard = TemporalGuard(datetime(2020, 1, 1))
        dispatcher = DataDispatcher(guard)
        
        # None data source
        result = dispatcher.get_data_at_timestamp(None, datetime(2020, 1, 1), "none_source")
        assert result is not None  # Should work with temporal validation
        
        # Empty string data source
        result = dispatcher.get_data_at_timestamp("", datetime(2020, 1, 1), "empty_source")
        assert result is not None
    
    def test_data_range_edge_cases(self):
        """Test data range requests with edge case parameters"""
        guard = TemporalGuard(datetime(2020, 1, 15))
        dispatcher = DataDispatcher(guard)
        
        # Start time after end time (invalid range)
        start_time = datetime(2020, 1, 10)
        end_time = datetime(2020, 1, 5)  # Before start time
        
        result = dispatcher.get_data_range("test_source", start_time, end_time, "invalid_range")
        # Should fail due to temporal violation (end_time validation)
        assert result is None
        
        # Zero-length range (start == end)
        same_time = datetime(2020, 1, 10)
        result = dispatcher.get_data_range("test_source", same_time, same_time, "zero_range")
        assert result is not None  # Should work if within temporal bounds
    
    def test_concurrent_access_simulation(self):
        """Test behavior under simulated concurrent access"""
        guard = TemporalGuard(datetime(2020, 1, 1))
        dispatcher = DataDispatcher(guard)
        
        # Simulate multiple "concurrent" requests
        results = []
        for i in range(10):
            timestamp = datetime(2020, 1, 1) - timedelta(hours=i)
            result = dispatcher.get_data_at_timestamp(f"source_{i}", timestamp, f"concurrent_{i}")
            results.append(result)
        
        # All should succeed (all in the past)
        assert all(r is not None for r in results)
        
        # Verify access log integrity
        access_log = guard.access_log
        assert len(access_log) >= 10


class TestTimeControllerEdgeCases:
    """Unit tests for TimeController edge cases"""
    
    def test_weekend_boundary_handling(self):
        """Test trading day calculation around weekends"""
        # Start on Friday
        friday = datetime(2020, 1, 3)  # January 3, 2020 was a Friday
        end_date = datetime(2020, 1, 10)
        
        guard = TemporalGuard(friday)
        controller = TimeController(guard, friday, end_date)
        
        # Next trading day should be Monday
        next_day = controller.get_next_trading_day(friday)
        assert next_day.weekday() == 0  # Monday
        assert next_day == datetime(2020, 1, 6)  # January 6, 2020
        
        # Advance and verify
        success = controller.advance_to_next_day()
        assert success
        assert controller.current_date == datetime(2020, 1, 6)
    
    def test_simulation_end_boundary(self):
        """Test behavior at simulation end boundary"""
        start_date = datetime(2020, 1, 1)
        end_date = datetime(2020, 1, 3)  # Very short simulation
        
        guard = TemporalGuard(start_date)
        controller = TimeController(guard, start_date, end_date)
        
        # Should be able to advance to end date
        success = controller.advance_to_next_day()
        assert success
        
        # Next advancement should fail (past end date)
        success = controller.advance_to_next_day()
        assert not success
        
        # Progress should be 100%
        progress = controller.get_simulation_progress()
        assert progress >= 1.0
    
    def test_remaining_days_calculation(self):
        """Test remaining days calculation accuracy"""
        start_date = datetime(2020, 1, 1)  # Wednesday
        end_date = datetime(2020, 1, 10)   # Friday
        
        guard = TemporalGuard(start_date)
        controller = TimeController(guard, start_date, end_date)
        
        initial_remaining = controller.get_remaining_days()
        assert initial_remaining > 0
        
        # Advance one day
        controller.advance_to_next_day()
        
        new_remaining = controller.get_remaining_days()
        assert new_remaining == initial_remaining - 1
    
    def test_holiday_handling_basic(self):
        """Test basic holiday handling (weekends only for now)"""
        # Start on Thursday before a long weekend
        thursday = datetime(2020, 1, 2)  # January 2, 2020
        end_date = datetime(2020, 1, 10)
        
        guard = TemporalGuard(thursday)
        controller = TimeController(guard, thursday, end_date)
        
        # Advance through weekend
        controller.advance_to_next_day()  # Should go to Friday (Jan 3)
        assert controller.current_date.weekday() == 4  # Friday
        
        controller.advance_to_next_day()  # Should skip weekend, go to Monday (Jan 6)
        assert controller.current_date.weekday() == 0  # Monday
        assert controller.current_date == datetime(2020, 1, 6)


class TestTemporalIntegrityStressTests:
    """Stress tests for temporal integrity under extreme conditions"""
    
    def test_rapid_time_advancement(self):
        """Test rapid succession of time advancements"""
        start_date = datetime(2020, 1, 1)
        guard = TemporalGuard(start_date)
        
        current_date = start_date
        
        # Rapidly advance time 100 times
        for i in range(100):
            current_date += timedelta(days=1)
            guard.advance_time(current_date, f"rapid_advance_{i}")
            
            # Verify integrity maintained
            assert guard.get_current_simulation_date() == current_date
            assert guard.validate_data_access(current_date, f"verify_{i}") == True
    
    def test_extreme_date_ranges(self):
        """Test with extreme date ranges"""
        # Very early date
        early_date = datetime(1900, 1, 1)
        guard = TemporalGuard(early_date)
        
        assert guard.validate_data_access(early_date, "early_date_test") == True
        
        # Very far future date (within reasonable bounds)
        far_future = datetime(2100, 12, 31)
        guard.advance_time(far_future, "far_future_test")
        
        assert guard.get_current_simulation_date() == far_future
    
    def test_microsecond_precision_boundaries(self):
        """Test temporal boundaries at microsecond precision"""
        base_time = datetime(2020, 1, 1, 12, 0, 0, 0)
        guard = TemporalGuard(base_time)
        
        # Test microsecond boundaries
        for i in range(10):
            test_time = base_time - timedelta(microseconds=i)
            assert guard.validate_data_access(test_time, f"micro_test_{i}") == True
        
        # Future microseconds should fail
        future_micro = base_time + timedelta(microseconds=1)
        with pytest.raises(TemporalViolationError):
            guard.validate_data_access(future_micro, "future_microsecond")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])