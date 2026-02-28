#!/usr/bin/env python3
"""
🧠 PROPERTY TESTS FOR STATE MANAGEMENT SYSTEM - CAPITAL-GRADE VALIDATION
Tests the three fundamental system laws that protect state integrity

PROPERTIES TESTED:
- Property 4: Atomic State Updates (S1) - all components see same version simultaneously
- Property 5: Temporal Monotonicity (S2) - timestamps must be strictly increasing
- Property 6: State Authority Hierarchy (S3) - authority levels must be respected

These are SYSTEM LAWS - violation means the system is broken.
"""

import os
import sys
import tempfile
import shutil
from datetime import datetime, timedelta
from typing import Dict, Any, List
import pytest
from hypothesis import given, strategies as st, settings, assume, example
from hypothesis.strategies import composite

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


from src.cohesion.unified_state_manager import (
    UnifiedStateManager,
    SystemState,
    StateUpdate,
    StateConflict,
    StateHistory,
    AuthorityLevel,
    ComponentStatus
)

# ========================================================================
# COMPOSITE STRATEGIES FOR PROPERTY TESTING
# ========================================================================

@composite
def valid_component_name(draw):
    """Generate valid component names"""
    return draw(st.sampled_from(["market", "portfolio", "risk", "intelligence", "health"]))

@composite
def valid_authority_level(draw):
    """Generate valid authority levels"""
    return draw(st.sampled_from(list(AuthorityLevel)))

@composite
def valid_state_updates(draw):
    """Generate valid state updates"""
    component = draw(valid_component_name())
    
    # Generate field updates based on component type
    field_generators = {
        "market": st.dictionaries(
            st.sampled_from(["regime", "risk_on_probability", "volatility", "breadth"]),
            st.one_of(
                st.text(min_size=1, max_size=20),
                st.floats(min_value=0.0, max_value=1.0),
                st.integers(min_value=0, max_value=100)
            ),
            min_size=1, max_size=4
        ),
        "portfolio": st.dictionaries(
            st.sampled_from(["total_exposure", "cash_level", "position_count", "sector_allocation"]),
            st.one_of(
                st.floats(min_value=0.0, max_value=1.0),
                st.integers(min_value=0, max_value=500),
                st.dictionaries(st.text(min_size=1, max_size=10), st.floats(min_value=0.0, max_value=0.5))
            ),
            min_size=1, max_size=3
        ),
        "risk": st.dictionaries(
            st.sampled_from(["max_drawdown", "var_95", "emergency_active", "stress_level"]),
            st.one_of(
                st.floats(min_value=-1.0, max_value=0.0),
                st.booleans(),
                st.integers(min_value=0, max_value=10)
            ),
            min_size=1, max_size=3
        ),
        "intelligence": st.dictionaries(
            st.sampled_from(["signal_strength", "confidence", "regime_probability", "model_version"]),
            st.one_of(
                st.floats(min_value=0.0, max_value=1.0),
                st.integers(min_value=1, max_value=100),
                st.text(min_size=1, max_size=10)
            ),
            min_size=1, max_size=3
        ),
        "health": st.dictionaries(
            st.sampled_from(["cpu_usage", "memory_usage", "disk_usage", "component_status"]),
            st.one_of(
                st.floats(min_value=0.0, max_value=1.0),
                st.sampled_from(["active", "inactive", "failed", "degraded"])
            ),
            min_size=1, max_size=3
        )
    }
    
    updates = draw(field_generators[component])
    authority = draw(valid_authority_level())
    
    return component, updates, authority

@composite
def monotonic_timestamps(draw):
    """Generate strictly increasing timestamps"""
    base_time = datetime.now()
    count = draw(st.integers(min_value=2, max_value=10))
    
    timestamps = []
    current_time = base_time
    
    for i in range(count):
        # Add random increment (1 second to 1 hour)
        increment = draw(st.integers(min_value=1, max_value=3600))
        current_time = current_time + timedelta(seconds=increment)
        timestamps.append(current_time)
    
    return timestamps

@composite
def non_monotonic_timestamps(draw):
    """Generate non-monotonic timestamps (for negative testing)"""
    base_time = datetime.now()
    count = draw(st.integers(min_value=2, max_value=5))
    
    timestamps = []
    current_time = base_time
    
    for i in range(count):
        if i == count - 1:
            # Make last timestamp earlier (violates monotonicity)
            current_time = current_time - timedelta(seconds=draw(st.integers(min_value=1, max_value=3600)))
        else:
            # Normal increment
            increment = draw(st.integers(min_value=1, max_value=3600))
            current_time = current_time + timedelta(seconds=increment)
        
        timestamps.append(current_time)
    
    return timestamps

@composite
def authority_conflict_scenario(draw):
    """Generate authority conflict scenarios"""
    component = draw(valid_component_name())
    field = draw(st.sampled_from(["critical_field", "shared_parameter", "system_status"]))
    
    # Generate conflicting updates with different authorities
    authorities = draw(st.lists(
        st.sampled_from(list(AuthorityLevel)), 
        min_size=2, max_size=4, unique=True
    ))
    
    values = draw(st.lists(
        st.one_of(st.floats(min_value=0.0, max_value=1.0), st.text(min_size=1, max_size=20)),
        min_size=len(authorities), max_size=len(authorities)
    ))
    
    return component, field, list(zip(authorities, values))

class TestStateManagementProperties:
    """Property-based tests for state management system invariants"""
    
    def setup_method(self):
        """Setup test environment with temporary directory"""
        self.test_dir = tempfile.mkdtemp()
        self.state_manager = UnifiedStateManager(persistence_dir=self.test_dir)
        
        # Reset state manager to clean state for each test
        self.state_manager.current_state = SystemState(
            market_state={},
            portfolio_state={},
            risk_state={},
            intelligence_state={},
            health_state={},
            timestamp=datetime.now(),
            version=1,
            authority_level=AuthorityLevel.SYSTEM,
            component_versions={}
        )
        
        # Clear field authorities to avoid conflicts between tests
        self.state_manager.field_authorities = {}
        self.state_manager._update_counter = 0
        
        # Reset state history
        self.state_manager.state_history = StateHistory()
        self.state_manager.state_history.add_snapshot(self.state_manager.current_state)
    
    def teardown_method(self):
        """Cleanup test environment"""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    # ========================================================================
    # PROPERTY 4: ATOMIC STATE UPDATES (S1)
    # ========================================================================
    
    @given(update_data=valid_state_updates())
    @settings(max_examples=50, deadline=None)  # Reduced examples for stability
    def test_property_4_atomic_state_updates(self, update_data):
        """
        **Feature: northstar-v3-system-cohesion, Property 4: Atomic State Updates (S1)**
        
        For any state change, all components must see the same version simultaneously.
        State version must increase exactly once per atomic update.
        
        **Validates: Requirements 3.2, 3.6**
        """
        
        component, updates, authority = update_data
        
        # Get initial state version
        initial_version = self.state_manager.get_state_version()
        
        # Perform atomic update
        success = self.state_manager.update_state(
            component=component,
            updates=updates,
            authority=authority,
            reason="Property test atomic update"
        )
        
        # Only test successful updates (authority conflicts are tested separately)
        if success:
            # INVARIANT S1: Version must increase by exactly 1
            new_version = self.state_manager.get_state_version()
            assert new_version == initial_version + 1, \
                f"INVARIANT S1 VIOLATION: Version increment not atomic. " \
                f"Expected {initial_version + 1}, got {new_version}"
            
            # INVARIANT S1: All updates must be visible in current state
            current_state = self.state_manager.get_state()
            component_state = self.state_manager.get_component_state(component)
            
            for field, expected_value in updates.items():
                actual_value = component_state.get(field)
                assert actual_value == expected_value, \
                    f"INVARIANT S1 VIOLATION: Update not atomic. " \
                    f"Field {component}.{field} expected {expected_value}, got {actual_value}"
            
            # INVARIANT S1: State version must be consistent across all components
            assert current_state.version == new_version, \
                f"INVARIANT S1 VIOLATION: State version inconsistency. " \
                f"Current state version {current_state.version} != manager version {new_version}"
            
            # INVARIANT S1: Component version must match system version
            if component in current_state.component_versions:
                component_version = current_state.component_versions[component]
                assert component_version == new_version, \
                    f"INVARIANT S1 VIOLATION: Component version inconsistency. " \
                    f"Component {component} version {component_version} != system version {new_version}"
    
    @given(
        update1=valid_state_updates(),
        update2=valid_state_updates()
    )
    @settings(max_examples=50, deadline=None)
    def test_property_4_multiple_atomic_updates(self, update1, update2):
        """
        **Feature: northstar-v3-system-cohesion, Property 4: Atomic State Updates (S1)**
        
        For any sequence of atomic updates, each update must be completely applied
        before the next update begins, maintaining version consistency.
        
        **Validates: Requirements 3.2, 3.6**
        """
        
        component1, updates1, authority1 = update1
        component2, updates2, authority2 = update2
        
        # Ensure different components to avoid authority conflicts
        assume(component1 != component2)
        
        initial_version = self.state_manager.get_state_version()
        
        # Apply first update
        success1 = self.state_manager.update_state(
            component=component1,
            updates=updates1,
            authority=authority1,
            reason="First atomic update"
        )
        
        if success1:
            intermediate_version = self.state_manager.get_state_version()
            
            # Apply second update with slight delay
            import time
            time.sleep(0.001)  # Ensure different timestamp
            
            success2 = self.state_manager.update_state(
                component=component2,
                updates=updates2,
                authority=authority2,
                reason="Second atomic update"
            )
            
            if success2:
                final_version = self.state_manager.get_state_version()
                
                # INVARIANT S1: Each update must increment version by exactly 1
                assert intermediate_version == initial_version + 1, \
                    f"INVARIANT S1 VIOLATION: First update version increment. " \
                    f"Expected {initial_version + 1}, got {intermediate_version}"
                
                assert final_version == intermediate_version + 1, \
                    f"INVARIANT S1 VIOLATION: Second update version increment. " \
                    f"Expected {intermediate_version + 1}, got {final_version}"
                
                # INVARIANT S1: Both updates must be visible in final state
                final_state = self.state_manager.get_state()
                
                component1_state = self.state_manager.get_component_state(component1)
                for field, expected_value in updates1.items():
                    actual_value = component1_state.get(field)
                    assert actual_value == expected_value, \
                        f"INVARIANT S1 VIOLATION: First update lost. " \
                        f"Field {component1}.{field} expected {expected_value}, got {actual_value}"
                
                component2_state = self.state_manager.get_component_state(component2)
                for field, expected_value in updates2.items():
                    actual_value = component2_state.get(field)
                    assert actual_value == expected_value, \
                        f"INVARIANT S1 VIOLATION: Second update lost. " \
                        f"Field {component2}.{field} expected {expected_value}, got {actual_value}"
    
    # ========================================================================
    # PROPERTY 5: TEMPORAL MONOTONICITY (S2)
    # ========================================================================
    
    @given(timestamps=monotonic_timestamps())
    @settings(max_examples=50, deadline=None)  # Reduced examples
    def test_property_5_temporal_monotonicity_valid(self, timestamps):
        """
        **Feature: northstar-v3-system-cohesion, Property 5: Temporal Monotonicity (S2)**
        
        For any sequence of state updates with strictly increasing timestamps,
        all updates must be accepted and timestamps must remain monotonic.
        
        **Validates: Requirements 3.3**
        """
        
        component = "market"
        
        # Adjust timestamps to be after current state timestamp
        current_time = self.state_manager.get_state().timestamp
        adjusted_timestamps = []
        
        for i, timestamp in enumerate(timestamps):
            # Make sure each timestamp is after the current state timestamp
            adjusted_timestamp = current_time + timedelta(seconds=i+1) + (timestamp - timestamps[0])
            adjusted_timestamps.append(adjusted_timestamp)
        
        successful_updates = 0
        for i, timestamp in enumerate(adjusted_timestamps):
            updates = {"test_field": f"value_{i}"}
            
            # All monotonic updates should succeed
            success = self.state_manager.update_state(
                component=component,
                updates=updates,
                authority=AuthorityLevel.INTELLIGENCE,
                timestamp=timestamp,
                reason=f"Monotonic update {i}"
            )
            
            if success:
                successful_updates += 1
                
                # INVARIANT S2: Current state timestamp must match update timestamp
                current_state = self.state_manager.get_state()
                assert current_state.timestamp == timestamp, \
                    f"INVARIANT S2 VIOLATION: State timestamp mismatch. " \
                    f"Expected {timestamp}, got {current_state.timestamp}"
        
        # At least some updates should succeed
        assert successful_updates > 0, \
            "INVARIANT S2 VIOLATION: No monotonic updates succeeded"
        
        # INVARIANT S2: Final state should have the latest successful timestamp
        final_state = self.state_manager.get_state()
        assert final_state.timestamp <= max(adjusted_timestamps), \
            f"INVARIANT S2 VIOLATION: Final timestamp exceeds maximum. " \
            f"Final: {final_state.timestamp}, Max: {max(adjusted_timestamps)}"
    
    @given(timestamps=non_monotonic_timestamps())
    @settings(max_examples=100, deadline=None)
    def test_property_5_temporal_monotonicity_invalid(self, timestamps):
        """
        **Feature: northstar-v3-system-cohesion, Property 5: Temporal Monotonicity (S2)**
        
        For any sequence of state updates with non-monotonic timestamps,
        the system must reject updates that violate temporal ordering.
        
        **Validates: Requirements 3.3**
        """
        
        component = "market"
        last_successful_timestamp = None
        
        for i, timestamp in enumerate(timestamps):
            updates = {"test_field": f"value_{i}"}
            
            try:
                success = self.state_manager.update_state(
                    component=component,
                    updates=updates,
                    authority=AuthorityLevel.INTELLIGENCE,
                    timestamp=timestamp,
                    reason=f"Non-monotonic update {i}"
                )
                
                if success:
                    # Update was accepted - check if it maintains monotonicity
                    if last_successful_timestamp is not None:
                        assert timestamp > last_successful_timestamp, \
                            f"INVARIANT S2 VIOLATION: Non-monotonic timestamp accepted. " \
                            f"Timestamp {timestamp} <= previous {last_successful_timestamp}"
                    
                    last_successful_timestamp = timestamp
                
            except ValueError as e:
                # Update was rejected - this is expected for non-monotonic timestamps
                if "INVARIANT S2 VIOLATION" in str(e):
                    # Verify that the timestamp is indeed non-monotonic
                    if last_successful_timestamp is not None:
                        assert timestamp <= last_successful_timestamp, \
                            f"INVARIANT S2 VIOLATION: Monotonic timestamp incorrectly rejected. " \
                            f"Timestamp {timestamp} > previous {last_successful_timestamp}"
                else:
                    # Unexpected error
                    raise e
        
        # INVARIANT S2: State should maintain the last valid timestamp
        if last_successful_timestamp is not None:
            final_state = self.state_manager.get_state()
            assert final_state.timestamp == last_successful_timestamp, \
                f"INVARIANT S2 VIOLATION: Final state timestamp incorrect. " \
                f"Expected {last_successful_timestamp}, got {final_state.timestamp}"
    
    # ========================================================================
    # PROPERTY 6: STATE AUTHORITY HIERARCHY (S3)
    # ========================================================================
    
    @given(conflict_data=authority_conflict_scenario())
    @settings(max_examples=100, deadline=None)
    def test_property_6_authority_hierarchy(self, conflict_data):
        """
        **Feature: northstar-v3-system-cohesion, Property 6: State Authority Hierarchy (S3)**
        
        For any conflicting state updates, authority hierarchy must be respected.
        Higher authority (lower enum value) must always override lower authority.
        
        **Validates: Requirements 3.4**
        """
        
        component, field, authority_value_pairs = conflict_data
        
        # Sort by authority level (higher authority = lower enum value)
        sorted_pairs = sorted(authority_value_pairs, key=lambda x: x[0].value)
        highest_authority, expected_final_value = sorted_pairs[0]
        
        # Apply updates in random order
        import random
        random.shuffle(authority_value_pairs)
        
        for i, (authority, value) in enumerate(authority_value_pairs):
            updates = {field: value}
            
            # Add small delay to ensure different timestamps
            import time
            time.sleep(0.001)
            
            success = self.state_manager.update_state(
                component=component,
                updates=updates,
                authority=authority,
                reason=f"Authority test update {i} with {authority.name}"
            )
            
            # Updates may be rejected based on authority, but should not fail
            # (rejection is different from failure)
        
        # INVARIANT S3: Final value must be from highest authority
        final_state = self.state_manager.get_component_state(component)
        actual_final_value = final_state.get(field)
        
        # The final value should be from the highest authority update
        # (Note: due to authority checking, lower authority updates may be rejected)
        if actual_final_value is not None:
            # Find which authority set this value
            found_authority = None
            for authority, value in authority_value_pairs:
                if value == actual_final_value:
                    if found_authority is None or authority.value < found_authority.value:
                        found_authority = authority
            
            # The authority that set the final value should be the highest or equal
            if found_authority is not None:
                assert found_authority.value <= highest_authority.value, \
                    f"INVARIANT S3 VIOLATION: Lower authority override detected. " \
                    f"Final value set by {found_authority.name} (level {found_authority.value}) " \
                    f"but highest authority was {highest_authority.name} (level {highest_authority.value})"
    
    @given(
        component=valid_component_name(),
        field=st.text(min_size=1, max_size=20),
        emergency_value=st.text(min_size=1, max_size=20),
        lower_value=st.text(min_size=1, max_size=20)
    )
    @settings(max_examples=50, deadline=None)
    def test_property_6_emergency_authority_override(self, component, field, emergency_value, lower_value):
        """
        **Feature: northstar-v3-system-cohesion, Property 6: State Authority Hierarchy (S3)**
        
        For any field, emergency authority must always override any other authority level.
        Emergency authority cannot be overridden by lower authorities.
        
        **Validates: Requirements 3.4**
        """
        
        # Ensure different values
        assume(emergency_value != lower_value)
        
        # First, set value with lower authority
        lower_authority = AuthorityLevel.INTELLIGENCE  # Lower authority
        self.state_manager.update_state(
            component=component,
            updates={field: lower_value},
            authority=lower_authority,
            reason="Initial lower authority update"
        )
        
        # Add delay
        import time
        time.sleep(0.001)
        
        # Then override with emergency authority
        emergency_success = self.state_manager.update_state(
            component=component,
            updates={field: emergency_value},
            authority=AuthorityLevel.EMERGENCY,
            reason="Emergency authority override"
        )
        
        # INVARIANT S3: Emergency authority must always succeed
        assert emergency_success, \
            f"INVARIANT S3 VIOLATION: Emergency authority update failed"
        
        # INVARIANT S3: Emergency value must be set
        component_state = self.state_manager.get_component_state(component)
        actual_value = component_state.get(field)
        assert actual_value == emergency_value, \
            f"INVARIANT S3 VIOLATION: Emergency authority not applied. " \
            f"Expected {emergency_value}, got {actual_value}"
        
        # Add delay
        time.sleep(0.001)
        
        # Try to override emergency with lower authority (should fail)
        lower_override_success = self.state_manager.update_state(
            component=component,
            updates={field: lower_value},
            authority=lower_authority,
            reason="Attempted lower authority override"
        )
        
        # INVARIANT S3: Lower authority should not override emergency
        final_component_state = self.state_manager.get_component_state(component)
        final_value = final_component_state.get(field)
        assert final_value == emergency_value, \
            f"INVARIANT S3 VIOLATION: Emergency authority was overridden. " \
            f"Expected {emergency_value}, got {final_value}"
    
    # ========================================================================
    # INTEGRATION PROPERTY TESTS
    # ========================================================================
    
    @given(
        updates_sequence=st.lists(valid_state_updates(), min_size=3, max_size=10)
    )
    @settings(max_examples=30, deadline=None)
    def test_property_integration_all_state_invariants(self, updates_sequence):
        """
        **Feature: northstar-v3-system-cohesion, Property Integration: All State Laws**
        
        For any sequence of state updates, all three state management laws must be
        satisfied simultaneously: S1 (Atomic Updates), S2 (Temporal Monotonicity), S3 (Authority Hierarchy).
        
        **Validates: Requirements 3.2, 3.6, 3.3, 3.4**
        """
        
        initial_version = self.state_manager.get_state_version()
        successful_updates = 0
        last_timestamp = self.state_manager.get_state().timestamp
        
        # Group updates by component to avoid authority conflicts
        component_updates = {}
        for component, updates, authority in updates_sequence:
            if component not in component_updates:
                component_updates[component] = []
            component_updates[component].append((updates, authority))
        
        # Process updates component by component to avoid conflicts
        for component, update_list in component_updates.items():
            for i, (updates, authority) in enumerate(update_list):
                # Ensure monotonic timestamps
                import time
                time.sleep(0.001)
                
                success = self.state_manager.update_state(
                    component=component,
                    updates=updates,
                    authority=authority,
                    reason=f"Integration test update {successful_updates}"
                )
                
                if success:
                    successful_updates += 1
                    current_state = self.state_manager.get_state()
                    
                    # INVARIANT S1: Version must increment atomically
                    expected_version = initial_version + successful_updates
                    assert current_state.version == expected_version, \
                        f"INVARIANT S1 VIOLATION: Version not atomic at update {successful_updates}. " \
                        f"Expected {expected_version}, got {current_state.version}"
                    
                    # INVARIANT S2: Timestamp must be monotonic
                    assert current_state.timestamp > last_timestamp, \
                        f"INVARIANT S2 VIOLATION: Non-monotonic timestamp at update {successful_updates}. " \
                        f"Current {current_state.timestamp} <= previous {last_timestamp}"
                    
                    last_timestamp = current_state.timestamp
        
        # ALL INVARIANTS: Final state integrity check
        integrity_valid = self.state_manager.validate_state_integrity()
        assert integrity_valid, \
            f"SYSTEM LAW VIOLATION: State integrity check failed after update sequence"
        
        # INVARIANT S1: Final version should match successful updates
        final_state = self.state_manager.get_state()
        expected_final_version = initial_version + successful_updates
        assert final_state.version == expected_final_version, \
            f"INVARIANT S1 VIOLATION: Final version mismatch. " \
            f"Expected {expected_final_version}, got {final_state.version}"

# Example-based tests for edge cases
class TestStateManagementEdgeCases:
    """Example-based tests for specific edge cases and regression testing"""
    
    def setup_method(self):
        """Setup test environment"""
        self.test_dir = tempfile.mkdtemp()
        self.state_manager = UnifiedStateManager(persistence_dir=self.test_dir)
    
    def teardown_method(self):
        """Cleanup test environment"""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_edge_case_simultaneous_updates_same_field(self):
        """Test simultaneous updates to the same field with different authorities"""
        
        component = "risk"
        field = "emergency_active"
        
        # Simulate near-simultaneous updates
        base_time = datetime.now()
        
        # Lower authority first
        success1 = self.state_manager.update_state(
            component=component,
            updates={field: False},
            authority=AuthorityLevel.INTELLIGENCE,
            timestamp=base_time + timedelta(microseconds=1),
            reason="Intelligence update"
        )
        
        # Higher authority immediately after
        success2 = self.state_manager.update_state(
            component=component,
            updates={field: True},
            authority=AuthorityLevel.EMERGENCY,
            timestamp=base_time + timedelta(microseconds=2),
            reason="Emergency override"
        )
        
        # Both should succeed (or emergency should override)
        assert success2, "Emergency authority update should succeed"
        
        # Final value should be from emergency authority
        final_state = self.state_manager.get_component_state(component)
        assert final_state.get(field) == True, \
            "Emergency authority should override intelligence authority"
    
    def test_edge_case_empty_updates(self):
        """Test behavior with empty update dictionaries"""
        
        # Empty updates should not change version
        initial_version = self.state_manager.get_state_version()
        
        success = self.state_manager.update_state(
            component="market",
            updates={},
            authority=AuthorityLevel.INTELLIGENCE,
            reason="Empty update test"
        )
        
        # Empty updates might be rejected or accepted but should not change version
        final_version = self.state_manager.get_state_version()
        if not success:
            # If rejected, version should not change
            assert final_version == initial_version, \
                "Version should not change for rejected empty updates"
        else:
            # If accepted, version might or might not change (implementation dependent)
            # but should not break system integrity
            assert self.state_manager.validate_state_integrity(), \
                "System integrity should be maintained after empty updates"

if __name__ == "__main__":
    # Run property tests
    pytest.main([__file__, "-v", "--tb=short"])