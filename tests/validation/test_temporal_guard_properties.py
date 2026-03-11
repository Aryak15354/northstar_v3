"""
Property-Based Tests for Temporal Guard

Feature: walk-forward-validation-engine
Property 1: Temporal Data Integrity

These tests validate that the TemporalGuard prevents any future data access
under all possible conditions using property-based testing.
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from datetime import datetime, timedelta
import sys
import os

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from validation.temporal_guard import (
    TemporalGuard, 
    TemporalViolationError, 
    DataDispatcher, 
    TimeController,
    TemporalViolationType
)

# Strategy for generating reasonable dates
def date_strategy(min_year=2005, max_year=2025):
    return st.datetimes(
        min_value=datetime(min_year, 1, 1),
        max_value=datetime(max_year, 12, 31)
    )

# Strategy for generating date pairs (simulation_date, data_timestamp)
@st.composite
def date_pair_strategy(draw):
    simulation_date = draw(date_strategy())
    
    # Generate data timestamp that could be before, at, or after simulation date
    offset_days = draw(st.integers(min_value=-1000, max_value=1000))
    data_timestamp = simulation_date + timedelta(days=offset_days)
    
    return simulation_date, data_timestamp

class TestTemporalGuardProperties:
    """Property-based tests for TemporalGuard temporal integrity"""
    
    @given(date_pair_strategy())
    @settings(max_examples=1000)
    def test_temporal_data_integrity_property(self, date_pair):
        """
        Feature: walk-forward-validation-engine, Property 1: Temporal Data Integrity
        
        For any simulation date and data access request, the Temporal Guard should 
        only allow access to data with timestamps at or before the simulation date.
        
        Validates: Requirements 1.1, 1.2, 7.1
        """
        simulation_date, data_timestamp = date_pair
        
        # Initialize temporal guard
        guard = TemporalGuard(simulation_date)
        
        # Test the core property: future data should be rejected
        if data_timestamp <= simulation_date:
            # Past or present data should be allowed
            assert guard.validate_data_access(data_timestamp, "property_test") == True
        else:
            # Future data should be rejected
            with pytest.raises(TemporalViolationError) as exc_info:
                guard.validate_data_access(data_timestamp, "property_test")
            
            # Verify the violation details
            violation = exc_info.value.violation
            assert violation.violation_type == TemporalViolationType.FUTURE_DATA_ACCESS
            assert violation.requested_timestamp == data_timestamp
            assert violation.current_simulation_date == simulation_date
    
    @given(st.lists(date_strategy(), min_size=1, max_size=50))
    @settings(max_examples=1000)
    def test_batch_temporal_validation_property(self, timestamps):
        """
        Property: Batch validation should be consistent with individual validation
        
        For any list of timestamps, batch validation results should match
        individual validation results.
        """
        # Use first timestamp as simulation date
        simulation_date = min(timestamps)
        guard = TemporalGuard(simulation_date)
        
        # Get batch results
        batch_results = guard.validate_timestamp_batch(timestamps, "batch_property_test")
        
        # Verify each result individually
        for timestamp in timestamps:
            expected_result = timestamp <= simulation_date
            
            if expected_result:
                # Should pass individual validation
                assert guard.validate_data_access(timestamp, "individual_test") == True
            else:
                # Should fail individual validation
                with pytest.raises(TemporalViolationError):
                    guard.validate_data_access(timestamp, "individual_test")
            
            # Batch result should match expectation
            assert batch_results[timestamp] == expected_result
    
    @given(date_strategy(), st.integers(min_value=1, max_value=100))
    @settings(max_examples=1000)
    def test_time_advancement_monotonicity_property(self, start_date, days_to_advance):
        """
        Property: Time advancement should be monotonic (always forward)
        
        For any valid time advancement, the simulation date should increase
        and data cutoff should advance accordingly.
        """
        guard = TemporalGuard(start_date)
        
        # Advance time forward
        new_date = start_date + timedelta(days=days_to_advance)
        guard.advance_time(new_date, "monotonicity_test")
        
        # Verify time moved forward
        assert guard.get_current_simulation_date() == new_date
        assert guard.get_available_data_cutoff() == new_date
        
        # Verify data access is now allowed up to new date
        assert guard.validate_data_access(new_date, "post_advancement_test") == True
        
        # Verify future data is still blocked
        future_date = new_date + timedelta(days=1)
        with pytest.raises(TemporalViolationError):
            guard.validate_data_access(future_date, "future_test")
    
    @given(date_strategy())
    @settings(max_examples=1000)
    def test_backward_time_travel_prevention_property(self, start_date):
        """
        Property: Backward time travel should always be prevented
        
        For any attempt to move simulation time backwards, the guard should
        reject the operation and maintain current state.
        """
        guard = TemporalGuard(start_date)
        
        # Try to move backwards
        past_date = start_date - timedelta(days=1)
        
        with pytest.raises(TemporalViolationError) as exc_info:
            guard.advance_time(past_date, "backward_test")
        
        # Verify violation type
        violation = exc_info.value.violation
        assert violation.violation_type == TemporalViolationType.BACKWARD_TIME_TRAVEL
        
        # Verify state unchanged
        assert guard.get_current_simulation_date() == start_date
        assert guard.get_available_data_cutoff() == start_date
    
    @given(date_strategy(), st.text(min_size=1, max_size=100))
    @settings(max_examples=1000)
    def test_context_preservation_property(self, simulation_date, context):
        """
        Property: Context information should be preserved in violations
        
        For any temporal violation, the context should be accurately recorded
        and retrievable from the violation record.
        """
        guard = TemporalGuard(simulation_date)
        
        # Generate future timestamp to trigger violation
        future_timestamp = simulation_date + timedelta(days=1)
        
        try:
            guard.validate_data_access(future_timestamp, context)
            assert False, "Should have raised TemporalViolationError"
        except TemporalViolationError as e:
            # Verify context is preserved
            assert e.violation.context == context
            assert e.violation.requested_timestamp == future_timestamp
            assert e.violation.current_simulation_date == simulation_date
        
        # Verify violation is recorded in guard
        violations = guard.get_violation_summary()
        assert violations['total_violations'] >= 1
        assert violations['last_violation'].context == context


class TestDataDispatcherProperties:
    """Property-based tests for DataDispatcher temporal validation"""
    
    @given(date_pair_strategy(), st.text(min_size=1, max_size=50))
    @settings(max_examples=1000)
    def test_data_dispatcher_temporal_consistency_property(self, date_pair, data_source):
        """
        Property: DataDispatcher should enforce same temporal rules as TemporalGuard
        
        For any data request, the dispatcher should only allow access to data
        that the underlying TemporalGuard would allow.
        """
        simulation_date, data_timestamp = date_pair
        
        guard = TemporalGuard(simulation_date)
        dispatcher = DataDispatcher(guard)
        
        # Test data access
        result = dispatcher.get_data_at_timestamp(data_source, data_timestamp, "property_test")
        
        if data_timestamp <= simulation_date:
            # Should succeed
            assert result is not None
            assert result['timestamp'] == data_timestamp
            assert result['source'] == data_source
        else:
            # Should fail (return None due to temporal violation)
            assert result is None
    
    @given(date_strategy(), st.integers(min_value=1, max_value=30), st.text(min_size=1, max_size=50))
    @settings(max_examples=1000)
    def test_data_range_temporal_boundary_property(self, start_date, range_days, data_source):
        """
        Property: Data range requests should respect temporal boundaries
        
        For any data range request, the end time must not exceed the current
        simulation date for the request to succeed.
        """
        guard = TemporalGuard(start_date)
        dispatcher = DataDispatcher(guard)
        
        range_start = start_date - timedelta(days=range_days)
        range_end = start_date + timedelta(days=range_days)
        
        # Request range that extends into future
        result = dispatcher.get_data_range(data_source, range_start, range_end, "range_property_test")
        
        # Should fail because range_end > simulation_date
        assert result is None
        
        # Request range that stays in past
        past_end = start_date - timedelta(days=1)
        result = dispatcher.get_data_range(data_source, range_start, past_end, "past_range_test")
        
        # Should succeed
        assert result is not None


class TestTimeControllerProperties:
    """Property-based tests for TimeController time advancement"""
    
    @given(date_strategy(), st.integers(min_value=1, max_value=365))
    @settings(max_examples=1000)
    def test_trading_day_advancement_property(self, start_date, simulation_days):
        """
        Property: Trading day advancement should skip weekends consistently
        
        For any sequence of trading day advancements, weekends should be
        consistently skipped and temporal guard should be properly updated.
        """
        # Ensure we have a reasonable end date
        end_date = start_date + timedelta(days=simulation_days + 100)
        
        guard = TemporalGuard(start_date)
        controller = TimeController(guard, start_date, end_date)
        
        previous_date = start_date
        advancement_count = 0
        
        # Advance through several days
        for _ in range(min(10, simulation_days)):  # Limit iterations for performance
            if not controller.advance_to_next_day():
                break
            
            current_date = controller.current_date
            
            # Verify advancement is forward
            assert current_date > previous_date
            
            # Verify it's a weekday (Monday=0, Sunday=6)
            assert current_date.weekday() < 5
            
            # Verify temporal guard is updated
            assert guard.get_current_simulation_date() == current_date
            
            previous_date = current_date
            advancement_count += 1
        
        # Should have made some progress
        assert advancement_count > 0
    
    @given(date_strategy())
    @settings(max_examples=1000)
    def test_simulation_progress_property(self, start_date):
        """
        Property: Simulation progress should be monotonic and bounded
        
        For any time advancement, progress should increase monotonically
        and remain between 0.0 and 1.0.
        """
        end_date = start_date + timedelta(days=30)  # Short simulation for testing
        
        guard = TemporalGuard(start_date)
        controller = TimeController(guard, start_date, end_date)
        
        # Initial progress should be 0
        initial_progress = controller.get_simulation_progress()
        assert 0.0 <= initial_progress <= 1.0
        
        previous_progress = initial_progress
        
        # Advance a few days and check progress
        for _ in range(5):
            if not controller.advance_to_next_day():
                break
            
            current_progress = controller.get_simulation_progress()
            
            # Progress should be bounded
            assert 0.0 <= current_progress <= 1.0
            
            # Progress should be monotonic (non-decreasing)
            assert current_progress >= previous_progress
            
            previous_progress = current_progress


class TestTemporalIntegrityInvariant:
    """Tests for temporal integrity invariants that must always hold"""
    
    @given(st.lists(date_strategy(), min_size=2, max_size=20))
    @settings(max_examples=1000)
    def test_temporal_invariant_preservation_property(self, dates):
        """
        Property: Temporal invariants should be preserved across all operations
        
        For any sequence of operations, the following invariants must hold:
        1. Current simulation date >= start date
        2. Data cutoff date == current simulation date
        3. No future data access is ever allowed
        """
        # Sort dates to create a valid sequence
        sorted_dates = sorted(dates)
        start_date = sorted_dates[0]
        
        guard = TemporalGuard(start_date)
        
        for date in sorted_dates[1:]:
            # Advance time
            guard.advance_time(date, "invariant_test")
            
            # Check invariants
            current_sim_date = guard.get_current_simulation_date()
            data_cutoff = guard.get_available_data_cutoff()
            
            # Invariant 1: Current date >= start date
            assert current_sim_date >= start_date
            
            # Invariant 2: Data cutoff == current simulation date
            assert data_cutoff == current_sim_date
            
            # Invariant 3: Future data access blocked
            future_date = current_sim_date + timedelta(days=1)
            with pytest.raises(TemporalViolationError):
                guard.validate_data_access(future_date, "invariant_future_test")
            
            # Past data access allowed
            past_date = current_sim_date - timedelta(days=1)
            if past_date >= start_date:
                assert guard.validate_data_access(past_date, "invariant_past_test") == True


if __name__ == "__main__":
    # Run property tests with verbose output
    pytest.main([__file__, "-v", "--tb=short"])
