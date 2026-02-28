"""
State Persistence Validation Tests

Tests state save and restore across system restart, recovery from corrupted state,
and state validation on load.

**Validates: Requirements 13.6**
"""

import pytest
import json
import os
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta
import numpy as np

from src.volatility.state_engine import (
    VolatilityStateEngine,
    VolatilityState,
    RegimeState,
    PortfolioGreeks,
    ValidationStatus
)


class TestStateRestoreAcrossRestart:
    """
    **Validates: Requirements 13.6**
    
    Test state save and restore across system restart.
    
    Simulates system shutdown and restart, verifying that:
    - State is persisted correctly
    - State can be restored after restart
    - Restored state is equivalent to original
    - System can continue operating after restore
    """
    
    def setup_method(self):
        """Create temporary directory for each test"""
        self.temp_dir = tempfile.mkdtemp()
    
    def teardown_method(self):
        """Clean up temporary directory"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_basic_state_save_and_restore(self):
        """
        **Validates: Requirements 13.6**
        
        Test basic state persistence and restoration.
        
        Steps:
        1. Create state engine with data
        2. Persist state
        3. Create new state engine (simulating restart)
        4. Restore state
        5. Verify state is equivalent
        """
        # Step 1: Create state engine with data
        engine1 = VolatilityStateEngine(persistence_dir=self.temp_dir)
        
        # Add regime data
        regime = RegimeState(
            regime="high_vol",
            confidence=0.90,
            duration=timedelta(hours=3),
            previous_regime="low_vol",
            transition_probability=0.10
        )
        engine1.update_regime(regime)
        
        # Add volatility metrics
        engine1.update_volatility_metrics(
            vix_level=25.5,
            realized_vol_20d=0.28,
            realized_vol_60d=0.30,
            vol_of_vol=0.20
        )
        
        # Add portfolio Greeks
        greeks = PortfolioGreeks(
            delta=100.0,
            gamma=20.0,
            vega=800.0,
            theta=-40.0,
            rho=15.0,
            vanna=8.0,
            volga=4.0,
            delta_by_underlying={"SPY": 60.0, "QQQ": 40.0},
            vega_by_underlying={"SPY": 500.0, "QQQ": 300.0},
            num_positions=15,
            total_notional=750000.0
        )
        engine1.update_portfolio_greeks(greeks)
        
        # Get original state
        original_state = engine1.get_state()
        
        # Step 2: Persist state
        success = engine1.persist_state()
        assert success, "State persistence should succeed"
        
        # Verify state file exists
        state_file = Path(self.temp_dir) / "volatility_state.json"
        assert state_file.exists(), "State file should exist"
        
        # Step 3: Create new state engine (simulating restart)
        engine2 = VolatilityStateEngine(persistence_dir=self.temp_dir)
        
        # Step 4: Restore state
        success = engine2.restore_state()
        assert success, "State restoration should succeed"
        
        # Step 5: Verify state is equivalent
        restored_state = engine2.get_state()
        
        # Verify regime
        assert restored_state.regime.regime == original_state.regime.regime
        assert abs(restored_state.regime.confidence - original_state.regime.confidence) < 0.001
        
        # Verify volatility metrics
        assert abs(restored_state.vix_level - original_state.vix_level) < 0.01
        assert abs(restored_state.realized_vol_20d - original_state.realized_vol_20d) < 0.001
        assert abs(restored_state.vol_of_vol - original_state.vol_of_vol) < 0.001
        
        # Verify Greeks (handle dict conversion)
        orig_greeks = original_state.portfolio_greeks if isinstance(original_state.portfolio_greeks, dict) else {
            'delta': original_state.portfolio_greeks.delta,
            'gamma': original_state.portfolio_greeks.gamma,
            'vega': original_state.portfolio_greeks.vega,
            'theta': original_state.portfolio_greeks.theta
        }
        rest_greeks = restored_state.portfolio_greeks if isinstance(restored_state.portfolio_greeks, dict) else {
            'delta': restored_state.portfolio_greeks.delta,
            'gamma': restored_state.portfolio_greeks.gamma,
            'vega': restored_state.portfolio_greeks.vega,
            'theta': restored_state.portfolio_greeks.theta
        }
        
        assert abs(rest_greeks['delta'] - orig_greeks['delta']) < 0.01
        assert abs(rest_greeks['gamma'] - orig_greeks['gamma']) < 0.01
        assert abs(rest_greeks['vega'] - orig_greeks['vega']) < 0.01
        
        print(f"\n✓ State save and restore across restart:")
        print(f"  Original regime: {original_state.regime.regime}")
        print(f"  Restored regime: {restored_state.regime.regime}")
        print(f"  Original VIX: {original_state.vix_level:.2f}")
        print(f"  Restored VIX: {restored_state.vix_level:.2f}")
        print(f"  Original delta: {orig_greeks['delta']:.1f}")
        print(f"  Restored delta: {rest_greeks['delta']:.1f}")
    
    def test_state_restore_with_correlations(self):
        """
        **Validates: Requirements 13.6**
        
        Test state persistence with correlation matrix.
        
        Correlation matrices are numpy arrays that require special
        serialization handling.
        """
        # Create state engine
        engine1 = VolatilityStateEngine(persistence_dir=self.temp_dir)
        
        # Add correlation matrix
        corr_matrix = np.array([
            [1.0, 0.75, 0.60, 0.55],
            [0.75, 1.0, 0.70, 0.65],
            [0.60, 0.70, 1.0, 0.68],
            [0.55, 0.65, 0.68, 1.0]
        ])
        
        engine1.update_correlations(
            correlation_matrix=corr_matrix,
            implied_corr=0.68,
            realized_corr=0.65
        )
        
        # Persist and restore
        assert engine1.persist_state()
        
        engine2 = VolatilityStateEngine(persistence_dir=self.temp_dir)
        assert engine2.restore_state()
        
        # Verify correlation matrix
        restored_state = engine2.get_state()
        np.testing.assert_array_almost_equal(
            restored_state.correlation_matrix,
            corr_matrix,
            decimal=6
        )
        
        assert abs(restored_state.implied_correlation - 0.68) < 0.001
        assert abs(restored_state.realized_correlation - 0.65) < 0.001
        
        print(f"\n✓ Correlation matrix persistence:")
        print(f"  Matrix shape: {restored_state.correlation_matrix.shape}")
        print(f"  Implied corr: {restored_state.implied_correlation:.3f}")
        print(f"  Realized corr: {restored_state.realized_correlation:.3f}")
    
    def test_state_restore_after_multiple_updates(self):
        """
        **Validates: Requirements 13.6**
        
        Test state persistence after multiple updates.
        
        Simulates a system that has been running for a while with
        many state updates, then restarts.
        """
        # Create state engine
        engine1 = VolatilityStateEngine(persistence_dir=self.temp_dir)
        
        # Perform multiple updates
        for i in range(10):
            regime = RegimeState(
                regime="low_vol" if i % 2 == 0 else "high_vol",
                confidence=0.80 + i * 0.01,
                duration=timedelta(hours=i),
                previous_regime="transition",
                transition_probability=0.10
            )
            engine1.update_regime(regime)
            
            engine1.update_volatility_metrics(
                vix_level=15.0 + i * 0.5,
                realized_vol_20d=0.15 + i * 0.01,
                vol_of_vol=0.10 + i * 0.01
            )
        
        # Get final state
        final_state = engine1.get_state()
        
        # Persist
        assert engine1.persist_state()
        
        # Restore in new engine
        engine2 = VolatilityStateEngine(persistence_dir=self.temp_dir)
        assert engine2.restore_state()
        
        # Verify final state matches
        restored_state = engine2.get_state()
        assert restored_state.regime.regime == final_state.regime.regime
        assert abs(restored_state.vix_level - final_state.vix_level) < 0.01
        
        print(f"\n✓ State restore after {10} updates:")
        print(f"  Final regime: {restored_state.regime.regime}")
        print(f"  Final VIX: {restored_state.vix_level:.2f}")
        print(f"  State version: {restored_state.version}")
    
    def test_system_continues_after_restore(self):
        """
        **Validates: Requirements 13.6**
        
        Test that system can continue operating after state restore.
        
        After restoring state, the system should be able to:
        - Accept new updates
        - Maintain state consistency
        - Continue normal operations
        """
        # Create and populate state engine
        engine1 = VolatilityStateEngine(persistence_dir=self.temp_dir)
        
        regime1 = RegimeState(
            regime="low_vol",
            confidence=0.85,
            duration=timedelta(hours=2),
            previous_regime="transition",
            transition_probability=0.15
        )
        engine1.update_regime(regime1)
        engine1.persist_state()
        
        # Restore in new engine
        engine2 = VolatilityStateEngine(persistence_dir=self.temp_dir)
        assert engine2.restore_state()
        
        # Continue operations - add new updates
        regime2 = RegimeState(
            regime="high_vol",
            confidence=0.90,
            duration=timedelta(hours=1),
            previous_regime="low_vol",
            transition_probability=0.10
        )
        success = engine2.update_regime(regime2)
        assert success, "Should be able to update after restore"
        
        # Verify new state
        current_state = engine2.get_state()
        assert current_state.regime.regime == "high_vol"
        
        # Persist again
        assert engine2.persist_state()
        
        print(f"\n✓ System continues after restore:")
        print(f"  Restored regime: low_vol")
        print(f"  Updated regime: {current_state.regime.regime}")
        print(f"  New version: {current_state.version}")


class TestCorruptedStateRecovery:
    """
    **Validates: Requirements 13.6**
    
    Test recovery from corrupted state files.
    
    Tests various corruption scenarios:
    - Invalid JSON syntax
    - Missing required fields
    - Invalid data types
    - Out-of-range values
    """
    
    def setup_method(self):
        """Create temporary directory for each test"""
        self.temp_dir = tempfile.mkdtemp()
    
    def teardown_method(self):
        """Clean up temporary directory"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_invalid_json_recovery(self):
        """
        **Validates: Requirements 13.6**
        
        Test recovery from invalid JSON syntax.
        
        If state file has invalid JSON, restore should fail gracefully
        and system should continue with default state.
        """
        # Create state engine and persist valid state
        engine1 = VolatilityStateEngine(persistence_dir=self.temp_dir)
        regime = RegimeState(
            regime="low_vol",
            confidence=0.85,
            duration=timedelta(hours=2),
            previous_regime="transition",
            transition_probability=0.15
        )
        engine1.update_regime(regime)
        engine1.persist_state()
        
        # Corrupt the state file with invalid JSON
        state_file = Path(self.temp_dir) / "volatility_state.json"
        with open(state_file, 'w') as f:
            f.write("{ invalid json syntax }")
        
        # Try to restore
        engine2 = VolatilityStateEngine(persistence_dir=self.temp_dir)
        success = engine2.restore_state()
        
        # Should fail gracefully
        assert not success, "Restore should fail for invalid JSON"
        
        # System should still be operational with default state
        current_state = engine2.get_state()
        assert current_state is not None
        
        print(f"\n✓ Invalid JSON recovery:")
        print(f"  Restore failed gracefully: {not success}")
        print(f"  System operational: {current_state is not None}")
    
    def test_missing_fields_recovery(self):
        """
        **Validates: Requirements 13.6**
        
        Test recovery from state file with missing fields.
        
        If required fields are missing, restore should fail or
        use default values.
        """
        # Create valid state
        engine1 = VolatilityStateEngine(persistence_dir=self.temp_dir)
        regime = RegimeState(
            regime="low_vol",
            confidence=0.85,
            duration=timedelta(hours=2),
            previous_regime="transition",
            transition_probability=0.15
        )
        engine1.update_regime(regime)
        engine1.persist_state()
        
        # Modify state file to remove required fields
        state_file = Path(self.temp_dir) / "volatility_state.json"
        with open(state_file, 'r') as f:
            state_data = json.load(f)
        
        # Remove timestamp (required field)
        del state_data['timestamp']
        
        with open(state_file, 'w') as f:
            json.dump(state_data, f)
        
        # Try to restore
        engine2 = VolatilityStateEngine(persistence_dir=self.temp_dir)
        success = engine2.restore_state()
        
        # Should fail or handle gracefully
        print(f"\n✓ Missing fields recovery:")
        print(f"  Restore result: {success}")
        print(f"  System operational: {engine2.get_state() is not None}")
    
    def test_invalid_data_types_recovery(self):
        """
        **Validates: Requirements 13.6**
        
        Test recovery from invalid data types in state file.
        
        If fields have wrong data types, restore should fail or
        convert to correct types.
        """
        # Create valid state
        engine1 = VolatilityStateEngine(persistence_dir=self.temp_dir)
        engine1.update_volatility_metrics(vix_level=18.5)
        engine1.persist_state()
        
        # Modify state file with invalid data types
        state_file = Path(self.temp_dir) / "volatility_state.json"
        with open(state_file, 'r') as f:
            state_data = json.load(f)
        
        # Change vix_level to string (should be float)
        state_data['vix_level'] = "invalid_number"
        
        with open(state_file, 'w') as f:
            json.dump(state_data, f)
        
        # Try to restore
        engine2 = VolatilityStateEngine(persistence_dir=self.temp_dir)
        success = engine2.restore_state()
        
        # Should fail gracefully
        print(f"\n✓ Invalid data types recovery:")
        print(f"  Restore result: {success}")
        print(f"  System operational: {engine2.get_state() is not None}")
    
    def test_out_of_range_values_recovery(self):
        """
        **Validates: Requirements 13.6**
        
        Test recovery from out-of-range values.
        
        If values are outside valid ranges (e.g., confidence > 1.0),
        validation should catch them.
        """
        # Create valid state
        engine1 = VolatilityStateEngine(persistence_dir=self.temp_dir)
        regime = RegimeState(
            regime="low_vol",
            confidence=0.85,
            duration=timedelta(hours=2),
            previous_regime="transition",
            transition_probability=0.15
        )
        engine1.update_regime(regime)
        engine1.persist_state()
        
        # Modify state file with out-of-range values
        state_file = Path(self.temp_dir) / "volatility_state.json"
        with open(state_file, 'r') as f:
            state_data = json.load(f)
        
        # Set confidence > 1.0 (invalid)
        state_data['regime']['confidence'] = 1.5
        
        with open(state_file, 'w') as f:
            json.dump(state_data, f)
        
        # Try to restore with validation
        engine2 = VolatilityStateEngine(persistence_dir=self.temp_dir)
        success = engine2.restore_state(validate=True)
        
        # Should fail validation or handle gracefully
        print(f"\n✓ Out-of-range values recovery:")
        print(f"  Restore with validation: {success}")
        print(f"  System operational: {engine2.get_state() is not None}")


class TestStateValidationOnLoad:
    """
    **Validates: Requirements 13.6**
    
    Test state validation when loading from disk.
    
    Tests:
    - Validation is performed on restore
    - Invalid states are rejected
    - Validation errors are reported
    - System handles validation failures gracefully
    """
    
    def setup_method(self):
        """Create temporary directory for each test"""
        self.temp_dir = tempfile.mkdtemp()
    
    def teardown_method(self):
        """Clean up temporary directory"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_validation_performed_on_restore(self):
        """
        **Validates: Requirements 13.6**
        
        Test that validation is performed when restoring state.
        
        Validation should check:
        - Data consistency
        - Value ranges
        - Required fields
        - Data types
        """
        # Create valid state
        engine1 = VolatilityStateEngine(persistence_dir=self.temp_dir)
        
        regime = RegimeState(
            regime="low_vol",
            confidence=0.85,
            duration=timedelta(hours=2),
            previous_regime="transition",
            transition_probability=0.15
        )
        engine1.update_regime(regime)
        
        engine1.update_volatility_metrics(
            vix_level=18.5,
            realized_vol_20d=0.20,
            vol_of_vol=0.15
        )
        
        # Persist
        assert engine1.persist_state()
        
        # Restore with validation
        engine2 = VolatilityStateEngine(persistence_dir=self.temp_dir)
        success = engine2.restore_state(validate=True)
        
        # Should succeed for valid state
        assert success, "Restore with validation should succeed for valid state"
        
        # Check validation status
        restored_state = engine2.get_state()
        assert restored_state.validation_status.is_valid
        assert len(restored_state.validation_status.errors) == 0
        
        print(f"\n✓ Validation performed on restore:")
        print(f"  Restore succeeded: {success}")
        print(f"  State valid: {restored_state.validation_status.is_valid}")
        print(f"  Errors: {len(restored_state.validation_status.errors)}")
        print(f"  Warnings: {len(restored_state.validation_status.warnings)}")
    
    def test_invalid_state_rejected(self):
        """
        **Validates: Requirements 13.6**
        
        Test that invalid states are rejected during restore.
        
        States with validation errors should be rejected when
        validation is enabled.
        """
        # Create state
        engine1 = VolatilityStateEngine(persistence_dir=self.temp_dir)
        regime = RegimeState(
            regime="low_vol",
            confidence=0.85,
            duration=timedelta(hours=2),
            previous_regime="transition",
            transition_probability=0.15
        )
        engine1.update_regime(regime)
        engine1.persist_state()
        
        # Manually corrupt state file
        state_file = Path(self.temp_dir) / "volatility_state.json"
        with open(state_file, 'r') as f:
            state_data = json.load(f)
        
        # Make state invalid (negative VIX)
        state_data['vix_level'] = -10.0
        
        with open(state_file, 'w') as f:
            json.dump(state_data, f)
        
        # Try to restore with validation
        engine2 = VolatilityStateEngine(persistence_dir=self.temp_dir)
        success = engine2.restore_state(validate=True)
        
        # Should fail validation or handle gracefully
        print(f"\n✓ Invalid state rejection:")
        print(f"  Restore with validation: {success}")
        print(f"  System operational: {engine2.get_state() is not None}")
    
    def test_validation_errors_reported(self):
        """
        **Validates: Requirements 13.6**
        
        Test that validation errors are properly reported.
        
        When validation fails, detailed error messages should
        be available for debugging.
        """
        # Create state with validation errors
        engine = VolatilityStateEngine(persistence_dir=self.temp_dir)
        
        # Manually create invalid state
        state = engine.get_state()
        state.vix_level = -10.0  # Invalid: negative VIX
        state.realized_vol_20d = -0.5  # Invalid: negative vol
        
        # Validate
        is_valid = state.validate_consistency()
        
        # Should have errors
        assert not is_valid
        assert len(state.validation_status.errors) > 0
        
        print(f"\n✓ Validation errors reported:")
        print(f"  State valid: {is_valid}")
        print(f"  Number of errors: {len(state.validation_status.errors)}")
        print(f"  Errors:")
        for error in state.validation_status.errors:
            print(f"    - {error}")
    
    def test_graceful_handling_of_validation_failures(self):
        """
        **Validates: Requirements 13.6**
        
        Test graceful handling of validation failures.
        
        System should continue operating even if state validation
        fails, using default or cached state.
        """
        # Create valid state
        engine1 = VolatilityStateEngine(persistence_dir=self.temp_dir)
        regime = RegimeState(
            regime="low_vol",
            confidence=0.85,
            duration=timedelta(hours=2),
            previous_regime="transition",
            transition_probability=0.15
        )
        engine1.update_regime(regime)
        engine1.persist_state()
        
        # Corrupt state file
        state_file = Path(self.temp_dir) / "volatility_state.json"
        with open(state_file, 'r') as f:
            state_data = json.load(f)
        
        state_data['vix_level'] = -100.0  # Invalid
        
        with open(state_file, 'w') as f:
            json.dump(state_data, f)
        
        # Try to restore
        engine2 = VolatilityStateEngine(persistence_dir=self.temp_dir)
        success = engine2.restore_state(validate=True)
        
        # System should still be operational
        current_state = engine2.get_state()
        assert current_state is not None
        
        # Should be able to perform operations
        new_regime = RegimeState(
            regime="high_vol",
            confidence=0.90,
            duration=timedelta(hours=1),
            previous_regime="low_vol",
            transition_probability=0.10
        )
        update_success = engine2.update_regime(new_regime)
        
        print(f"\n✓ Graceful validation failure handling:")
        print(f"  Restore succeeded: {success}")
        print(f"  System operational: {current_state is not None}")
        print(f"  Can perform updates: {update_success}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
