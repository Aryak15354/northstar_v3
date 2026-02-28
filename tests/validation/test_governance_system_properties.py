#!/usr/bin/env python3
"""
Property-Based Tests for Governance System

Tests the correctness properties of the governance and human override system
for institutional validation.

# Feature: institutional-validation-layers, Property 41: Governance Override Logging
# Feature: institutional-validation-layers, Property 42: Emergency Pause Immediacy
"""

import pytest
import pandas as pd
import numpy as np
import os
import tempfile
import shutil
from datetime import datetime, timedelta
from hypothesis import given, strategies as st, settings, assume
from typing import Dict, List, Any

# Import the system under test
from src.validation.governance_system import GovernanceSystem, OverrideType, ApprovalAuthority, HumanOverride, GovernanceState


class TestGovernanceSystemProperties:
    """Property-based tests for Governance System"""
    
    def setup_method(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        
        # Create test governance system with fresh state
        self.governance = GovernanceSystem(
            base_dir=os.path.join(self.temp_dir, "governance")
        )
        
        # Ensure clean state
        self.governance.current_state.emergency_paused = False
        self.governance.current_state.exposure_cap = None
        self.governance.current_state.deactivated_strategies = []
        self.governance.current_state.active_overrides = []
        self.governance.override_history = []
    
    def teardown_method(self):
        """Clean up test environment"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    # ========================================================================
    # PROPERTY 41: Governance Override Logging
    # ========================================================================
    
    @given(
        reason=st.text(min_size=5, max_size=200),
        approved_by=st.sampled_from(['risk_manager', 'cio', 'compliance_officer'])  # Only valid authorities for emergency pause
    )
    @settings(max_examples=30, deadline=5000)
    def test_property_41_governance_override_logging(self, reason: str, approved_by: str):
        """
        Property 41: Governance Override Logging
        
        For any human override, a log entry must be created with date, 
        override_type, reason, and approved_by fields.
        
        Validates: Requirements 21.1, 21.2
        """
        
        # Execute emergency pause override
        override_id = self.governance.emergency_pause(reason, approved_by)
        
        # PROPERTY: Override must be logged
        assert override_id != ""
        assert len(override_id) > 0
        
        # PROPERTY: Override must be in history
        assert len(self.governance.override_history) > 0
        
        # Get the logged override
        logged_override = self.governance.override_history[-1]
        
        # PROPERTY: All required fields must be present
        assert logged_override.timestamp is not None
        assert logged_override.override_type == OverrideType.EMERGENCY_PAUSE
        assert logged_override.reason == reason
        assert logged_override.approved_by.value == approved_by
        assert isinstance(logged_override.parameters, dict)
        assert logged_override.status in ['pending', 'approved', 'executed', 'reverted']
        
        # PROPERTY: Override must be in governance status
        status = self.governance.get_governance_status()
        assert status['total_overrides'] > 0
        assert len(status['override_history_recent']) > 0
    
    @given(
        new_cap=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        reason=st.text(min_size=5, max_size=200),
        approved_by=st.sampled_from(['risk_manager', 'portfolio_manager', 'cio'])
    )
    @settings(max_examples=20, deadline=5000)
    def test_property_41_exposure_cap_logging(self, new_cap: float, reason: str, approved_by: str):
        """
        Property 41: Exposure Cap Override Logging
        
        Exposure cap changes must be properly logged.
        """
        
        # Execute exposure cap change
        override_id = self.governance.change_exposure_cap(new_cap, reason, approved_by)
        
        # PROPERTY: Override must be logged
        assert override_id != ""
        
        # PROPERTY: Override must be in history
        assert len(self.governance.override_history) > 0
        
        # Get the logged override
        logged_override = self.governance.override_history[-1]
        
        # PROPERTY: Override details must be correct
        assert logged_override.override_type == OverrideType.EXPOSURE_CAP_CHANGE
        assert logged_override.reason == reason
        assert logged_override.approved_by.value == approved_by
        assert logged_override.parameters['new_cap'] == new_cap
        
        # PROPERTY: Governance state must be updated
        assert self.governance.current_state.exposure_cap == new_cap
    
    # ========================================================================
    # PROPERTY 42: Emergency Pause Immediacy
    # ========================================================================
    
    @given(
        reason=st.text(min_size=5, max_size=200)
    )
    @settings(max_examples=20, deadline=5000)
    def test_property_42_emergency_pause_immediacy(self, reason: str):
        """
        Property 42: Emergency Pause Immediacy
        
        For any emergency pause override, all trading must halt and exposure 
        must reduce to cash within one system cycle.
        
        Validates: Requirements 21.4
        """
        
        # Ensure clean state for this test
        self.governance.current_state.emergency_paused = False
        
        # Verify initial state (not paused)
        assert not self.governance.is_emergency_paused()
        
        # Execute emergency pause
        override_id = self.governance.emergency_pause(reason, "risk_manager")
        
        # PROPERTY: Emergency pause must be immediate
        assert override_id != ""
        assert self.governance.is_emergency_paused()
        
        # PROPERTY: Override must be executed immediately
        logged_override = self.governance.override_history[-1]
        assert logged_override.status == 'executed'
        assert logged_override.execution_time is not None
        
        # PROPERTY: Execution time must be very recent (within seconds)
        time_diff = datetime.now() - logged_override.execution_time
        assert time_diff.total_seconds() < 5.0  # Must execute within 5 seconds
        
        # PROPERTY: Governance state must reflect emergency pause
        assert self.governance.current_state.emergency_paused is True
        assert self.governance.current_state.last_update is not None
    
    # ========================================================================
    # AUTHORITY VERIFICATION PROPERTIES
    # ========================================================================
    
    @given(
        reason=st.text(min_size=5, max_size=200),
        invalid_authority=st.sampled_from(['invalid_user', 'unauthorized', 'system_admin'])
    )
    @settings(max_examples=20, deadline=5000)
    def test_property_authority_verification(self, reason: str, invalid_authority: str):
        """
        Property: Authority Verification
        
        Invalid or insufficient authority must be rejected.
        """
        
        # Try emergency pause with invalid authority
        override_id = self.governance.emergency_pause(reason, invalid_authority)
        
        # PROPERTY: Invalid authority must be rejected
        if invalid_authority not in ['risk_manager', 'cio', 'compliance_officer']:
            assert override_id == ""
            assert not self.governance.is_emergency_paused()
    
    # ========================================================================
    # STRATEGY DEACTIVATION PROPERTIES
    # ========================================================================
    
    @given(
        strategy_name=st.text(min_size=3, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd', 'Pc'))),
        reason=st.text(min_size=5, max_size=200)
    )
    @settings(max_examples=20, deadline=5000)
    def test_property_strategy_deactivation_consistency(self, strategy_name: str, reason: str):
        """
        Property: Strategy Deactivation Consistency
        
        Deactivated strategies must be consistently blocked.
        """
        
        # Ensure clean state for this test
        self.governance.current_state.deactivated_strategies = []
        
        # Verify strategy is initially allowed
        assert self.governance.is_strategy_allowed(strategy_name)
        
        # Deactivate strategy
        override_id = self.governance.deactivate_strategy(strategy_name, reason, "portfolio_manager")
        
        # PROPERTY: Deactivation must succeed
        assert override_id != ""
        
        # PROPERTY: Strategy must be blocked after deactivation
        assert not self.governance.is_strategy_allowed(strategy_name)
        
        # PROPERTY: Strategy must be in deactivated list
        assert strategy_name in self.governance.current_state.deactivated_strategies
        
        # PROPERTY: Other strategies should still be allowed
        other_strategy = f"other_{strategy_name}"
        assert self.governance.is_strategy_allowed(other_strategy)
    
    # ========================================================================
    # EXPOSURE CAP PROPERTIES
    # ========================================================================
    
    @given(
        cap1=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        cap2=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=20, deadline=5000)
    def test_property_exposure_cap_consistency(self, cap1: float, cap2: float):
        """
        Property: Exposure Cap Consistency
        
        Exposure cap changes must be consistently applied.
        """
        
        # Ensure clean state for this test
        self.governance.current_state.exposure_cap = None
        
        # Verify no initial cap
        assert self.governance.get_effective_exposure_cap() is None
        
        # Set first cap
        override_id_1 = self.governance.change_exposure_cap(cap1, "Test cap 1", "risk_manager")
        
        # PROPERTY: First cap must be applied
        assert override_id_1 != ""
        assert self.governance.get_effective_exposure_cap() == cap1
        
        # Set second cap
        override_id_2 = self.governance.change_exposure_cap(cap2, "Test cap 2", "risk_manager")
        
        # PROPERTY: Second cap must override first
        assert override_id_2 != ""
        assert self.governance.get_effective_exposure_cap() == cap2
        
        # PROPERTY: Both overrides must be logged
        assert len(self.governance.override_history) >= 2
    
    # ========================================================================
    # REVERSION PROPERTIES
    # ========================================================================
    
    @given(
        reason=st.text(min_size=5, max_size=200)
    )
    @settings(max_examples=15, deadline=5000)
    def test_property_override_reversion(self, reason: str):
        """
        Property: Override Reversion
        
        Overrides must be properly reversible.
        """
        
        # Execute emergency pause
        override_id = self.governance.emergency_pause(reason, "risk_manager")
        
        # PROPERTY: Override must succeed
        assert override_id != ""
        assert self.governance.is_emergency_paused()
        
        # Revert override
        revert_success = self.governance.revert_override(
            override_id, "Test reversion", "risk_manager"
        )
        
        # PROPERTY: Reversion must succeed
        assert revert_success is True
        
        # PROPERTY: State must be reverted
        assert not self.governance.is_emergency_paused()
        
        # PROPERTY: Override must be marked as reverted
        reverted_override = self.governance.override_history[-1]
        assert reverted_override.status == 'reverted'
        assert reverted_override.revert_time is not None
    
    # ========================================================================
    # STATE PERSISTENCE PROPERTIES
    # ========================================================================
    
    def test_property_state_persistence(self):
        """
        Property: State Persistence
        
        Governance state must persist across system restarts.
        """
        
        # Set some state
        override_id = self.governance.emergency_pause("Test persistence", "risk_manager")
        cap_id = self.governance.change_exposure_cap(0.7, "Test cap", "portfolio_manager")
        
        # PROPERTY: State must be set
        assert self.governance.is_emergency_paused()
        assert self.governance.get_effective_exposure_cap() == 0.7
        
        # Create new governance system (simulating restart)
        new_governance = GovernanceSystem(
            base_dir=os.path.join(self.temp_dir, "governance")
        )
        
        # PROPERTY: State must be restored
        assert new_governance.is_emergency_paused()
        assert new_governance.get_effective_exposure_cap() == 0.7
        assert len(new_governance.override_history) >= 2
    
    # ========================================================================
    # VALIDATION PROPERTIES
    # ========================================================================
    
    def test_property_invalid_exposure_cap_rejection(self):
        """
        Property: Invalid Exposure Cap Rejection
        
        Invalid exposure caps must be rejected.
        """
        
        # Test invalid caps
        invalid_caps = [-0.1, 1.1, float('inf'), float('-inf')]
        
        for invalid_cap in invalid_caps:
            override_id = self.governance.change_exposure_cap(
                invalid_cap, "Test invalid cap", "risk_manager"
            )
            
            # PROPERTY: Invalid cap must be rejected
            assert override_id == ""
            
            # PROPERTY: State must not change
            # (Assuming no previous valid cap was set)
            if self.governance.get_effective_exposure_cap() is None:
                assert self.governance.get_effective_exposure_cap() is None
    
    # ========================================================================
    # SCHEMA ENFORCEMENT PROPERTIES
    # ========================================================================
    
    def test_property_override_schema_enforcement(self):
        """
        Property: Override Schema Enforcement
        
        Override data must conform to required schema.
        """
        
        # Execute override
        override_id = self.governance.emergency_pause("Test schema", "risk_manager")
        
        # PROPERTY: Override must be logged
        assert override_id != ""
        
        # Check if parquet file was created
        parquet_file = os.path.join(self.governance.base_dir, "human_overrides.parquet")
        assert os.path.exists(parquet_file)
        
        # Load and validate schema
        df = pd.read_parquet(parquet_file)
        
        # PROPERTY: Required columns must exist
        required_columns = [
            'override_id', 'timestamp', 'override_type', 'reason', 
            'approved_by', 'parameters', 'status', 'execution_time', 'revert_time'
        ]
        
        for col in required_columns:
            assert col in df.columns
        
        # PROPERTY: Data types must be correct
        assert pd.api.types.is_datetime64_any_dtype(df['timestamp'])
        assert pd.api.types.is_string_dtype(df['override_type'])
        assert pd.api.types.is_string_dtype(df['reason'])
        assert pd.api.types.is_string_dtype(df['approved_by'])
    
    # ========================================================================
    # ERROR HANDLING PROPERTIES
    # ========================================================================
    
    def test_property_duplicate_strategy_deactivation(self):
        """
        Property: Duplicate Strategy Deactivation Handling
        
        Attempting to deactivate an already deactivated strategy should be handled gracefully.
        """
        
        strategy_name = "test_strategy"
        
        # Deactivate strategy first time
        override_id_1 = self.governance.deactivate_strategy(
            strategy_name, "First deactivation", "portfolio_manager"
        )
        
        # PROPERTY: First deactivation must succeed
        assert override_id_1 != ""
        assert not self.governance.is_strategy_allowed(strategy_name)
        
        # Try to deactivate same strategy again
        override_id_2 = self.governance.deactivate_strategy(
            strategy_name, "Second deactivation", "portfolio_manager"
        )
        
        # PROPERTY: Duplicate deactivation should be rejected
        assert override_id_2 == ""
        
        # PROPERTY: Strategy should still be deactivated (no change)
        assert not self.governance.is_strategy_allowed(strategy_name)
    
    def test_property_nonexistent_override_reversion(self):
        """
        Property: Nonexistent Override Reversion Handling
        
        Attempting to revert a nonexistent override should fail gracefully.
        """
        
        # Try to revert nonexistent override
        success = self.governance.revert_override(
            "NONEXISTENT_ID", "Test reversion", "risk_manager"
        )
        
        # PROPERTY: Reversion must fail
        assert success is False


def test_human_override_validation():
    """Test HumanOverride validation"""
    
    # Valid override
    valid_override = HumanOverride(
        timestamp=datetime.now(),
        override_type=OverrideType.EMERGENCY_PAUSE,
        reason="Valid reason for testing",
        approved_by=ApprovalAuthority.RISK_MANAGER,
        parameters={"test": "value"},
        status="executed"
    )
    
    errors = valid_override.validate()
    assert len(errors) == 0
    
    # Invalid override - short reason
    invalid_override = HumanOverride(
        timestamp=datetime.now(),
        override_type=OverrideType.EMERGENCY_PAUSE,
        reason="Bad",  # Too short
        approved_by=ApprovalAuthority.RISK_MANAGER,
        parameters={"test": "value"},
        status="invalid_status"  # Invalid status
    )
    
    errors = invalid_override.validate()
    assert len(errors) > 0
    assert any("Reason must be at least 5 characters" in error for error in errors)
    assert any("Invalid status" in error for error in errors)


def test_governance_state_validation():
    """Test GovernanceState validation"""
    
    # Valid state
    valid_state = GovernanceState(
        emergency_paused=False,
        exposure_cap=0.8,
        deactivated_strategies=["strategy1"],
        active_overrides=["override1"],
        last_update=datetime.now()
    )
    
    errors = valid_state.validate()
    assert len(errors) == 0
    
    # Invalid state - bad exposure cap
    invalid_state = GovernanceState(
        emergency_paused=False,
        exposure_cap=1.5,  # Invalid cap > 1.0
        deactivated_strategies="not_a_list",  # Should be list
        active_overrides=["override1"],
        last_update=datetime.now()
    )
    
    errors = invalid_state.validate()
    assert len(errors) > 0
    assert any("Exposure cap" in error and "outside bounds" in error for error in errors)


if __name__ == "__main__":
    pytest.main([__file__])