#!/usr/bin/env python3
"""
🔐 PROPERTY TESTS FOR CONFIGURATION SYSTEM - CAPITAL-GRADE VALIDATION
Tests the three fundamental system laws that protect configuration integrity

PROPERTIES TESTED:
- Property 1: Single Source of Truth (C1) - exactly one active configuration set
- Property 2: Risk Parameter Consistency (C2) - mathematical validation  
- Property 3: Configuration Completeness (C3) - all required fields present

These are SYSTEM LAWS - violation means the system is broken.
"""

import os
import sys
import tempfile
import shutil
import yaml
import json
from datetime import datetime
from typing import Dict, Any, List
import pytest
from hypothesis import given, strategies as st, settings, assume, example
from hypothesis.strategies import composite

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


from src.cohesion.configuration_manager import (
    ConfigurationManager, 
    MarketConfiguration, 
    RiskConfiguration,
    ValidationResult,
    ValidationError,
    ValidationSeverity
)

# ========================================================================
# COMPOSITE STRATEGIES FOR PROPERTY TESTING
# ========================================================================

@composite
def valid_market_config(draw):
    """Generate valid market configuration for testing"""
    return {
        "market_name": draw(st.sampled_from(["india", "usa", "uk", "japan"])),
        "currency": draw(st.sampled_from(["INR", "USD", "GBP", "JPY"])),
        "trading_hours": {
            "pre_open": draw(st.sampled_from(["09:00", "08:30", "09:15"])),
            "open": draw(st.sampled_from(["09:15", "09:30", "08:00"])),
            "close": draw(st.sampled_from(["15:30", "16:00", "17:00"]))
        },
        "sector_classifications": draw(st.lists(
            st.sampled_from(["BANKING", "IT", "PHARMA", "AUTO", "ENERGY"]),
            min_size=3, max_size=10, unique=True
        )),
        "risk_parameters": {
            "max_single_position": draw(st.floats(min_value=0.01, max_value=0.20)),
            "max_sector_exposure": draw(st.floats(min_value=0.10, max_value=0.50))
        },
        "data_sources": {
            "prices": draw(st.sampled_from(["yfinance", "bloomberg", "reuters"])),
            "macro": draw(st.sampled_from(["rbi", "fed", "ecb"])),
            "fundamentals": draw(st.sampled_from(["screener", "factset", "refinitiv"]))
        },
        "indices": {
            "primary": draw(st.sampled_from(["NIFTY50", "SPX", "FTSE100"])),
            "broad": draw(st.sampled_from(["NIFTY500", "SPX500", "FTSE250"]))
        }
    }

@composite
def mathematically_consistent_risk_params(draw):
    """Generate mathematically consistent risk parameters"""
    max_position_size = draw(st.floats(min_value=0.01, max_value=0.15))
    
    # Ensure mathematical consistency: max_position_size * 4 <= max_sector_exposure
    min_sector_exposure = max_position_size * 4
    max_sector_exposure = draw(st.floats(
        min_value=min_sector_exposure, 
        max_value=min(1.0, min_sector_exposure + 0.20)
    ))
    
    return {
        "max_position_size": max_position_size,
        "max_sector_exposure": max_sector_exposure,
        "max_drawdown_threshold": draw(st.floats(min_value=-0.50, max_value=-0.10)),
        "volatility_threshold": draw(st.floats(min_value=0.10, max_value=0.50)),
        "correlation_threshold": draw(st.floats(min_value=0.50, max_value=0.95)),
        "emergency_brake_params": {
            "max_drawdown_trigger": draw(st.floats(min_value=-0.20, max_value=-0.05)),
            "volatility_trigger": draw(st.floats(min_value=0.01, max_value=0.10)),
            "consecutive_losses": draw(st.integers(min_value=3, max_value=10))
        }
    }

@composite
def mathematically_inconsistent_risk_params(draw):
    """Generate mathematically inconsistent risk parameters"""
    max_position_size = draw(st.floats(min_value=0.10, max_value=0.25))
    
    # Ensure mathematical inconsistency: max_position_size * 4 > max_sector_exposure
    max_required = max_position_size * 4
    max_sector_exposure = draw(st.floats(
        min_value=0.05, 
        max_value=min(0.99, max_required - 0.01)
    ))
    
    # Only generate if truly inconsistent
    assume(max_position_size * 4 > max_sector_exposure)
    
    return {
        "max_position_size": max_position_size,
        "max_sector_exposure": max_sector_exposure,
        "max_drawdown_threshold": draw(st.floats(min_value=-0.50, max_value=-0.10)),
        "volatility_threshold": draw(st.floats(min_value=0.10, max_value=0.50)),
        "correlation_threshold": draw(st.floats(min_value=0.50, max_value=0.95)),
        "emergency_brake_params": {
            "max_drawdown_trigger": draw(st.floats(min_value=-0.20, max_value=-0.05)),
            "volatility_trigger": draw(st.floats(min_value=0.01, max_value=0.10)),
            "consecutive_losses": draw(st.integers(min_value=3, max_value=10))
        }
    }

@composite
def complete_market_config(draw):
    """Generate complete market configuration"""
    return {
        "market_name": draw(st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Ll')))),
        "currency": draw(st.sampled_from(["INR", "USD", "GBP", "JPY", "EUR"])),
        "trading_hours": {
            "pre_open": draw(st.sampled_from(["09:00", "08:30", "09:15"])),
            "open": draw(st.sampled_from(["09:15", "09:30", "08:00"])),
            "close": draw(st.sampled_from(["15:30", "16:00", "17:00"]))
        },
        "sector_classifications": draw(st.lists(
            st.text(min_size=2, max_size=10, alphabet=st.characters(whitelist_categories=('Lu',))),
            min_size=1, max_size=15, unique=True
        )),
        "risk_parameters": {
            "max_single_position": draw(st.floats(min_value=0.01, max_value=0.20)),
            "max_sector_exposure": draw(st.floats(min_value=0.10, max_value=0.50))
        },
        "data_sources": {
            "prices": draw(st.text(min_size=1, max_size=20)),
            "macro": draw(st.text(min_size=1, max_size=20)),
            "fundamentals": draw(st.text(min_size=1, max_size=20))
        },
        "indices": {
            "primary": draw(st.text(min_size=1, max_size=20)),
            "broad": draw(st.text(min_size=1, max_size=20))
        }
    }

@composite
def incomplete_market_config(draw):
    """Generate incomplete market configuration (missing required fields)"""
    complete_config = draw(complete_market_config())
    
    # Remove at least one required field
    required_fields = ["market_name", "currency", "trading_hours", "sector_classifications", 
                      "risk_parameters", "data_sources", "indices"]
    
    fields_to_remove = draw(st.lists(
        st.sampled_from(required_fields), 
        min_size=1, max_size=3, unique=True
    ))
    
    incomplete_config = complete_config.copy()
    for field in fields_to_remove:
        if field in incomplete_config:
            del incomplete_config[field]
    
    return incomplete_config, fields_to_remove

class TestConfigurationSystemProperties:
    """Property-based tests for configuration system invariants"""
    
    def setup_method(self):
        """Setup test environment with temporary directory"""
        self.test_dir = tempfile.mkdtemp()
        self.config_manager = ConfigurationManager(config_dir=self.test_dir)
    
    def teardown_method(self):
        """Cleanup test environment"""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    # ========================================================================
    # PROPERTY 1: SINGLE SOURCE OF TRUTH (C1)
    # ========================================================================
    
    @given(config_data=valid_market_config())
    @settings(max_examples=100, deadline=None)
    def test_property_1_single_source_of_truth(self, config_data):
        """
        **Feature: northstar-v3-system-cohesion, Property 1: Single Source of Truth (C1)**
        
        For any valid configuration loaded into the system, there must exist 
        exactly one active configuration set at all times.
        
        **Validates: Requirements 2.1, 4.1**
        """
        
        # Create configuration file
        config_file = os.path.join(self.test_dir, "market.yaml")
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        # Load configuration
        loaded_config = self.config_manager.load_config("market")
        
        # INVARIANT C1: Exactly one active configuration set
        assert len(self.config_manager.configs) >= 1, \
            f"INVARIANT C1 VIOLATION: No active configurations (count: {len(self.config_manager.configs)})"
        
        # The loaded configuration should be accessible
        assert "market" in self.config_manager.configs, \
            "INVARIANT C1 VIOLATION: Loaded configuration not in active configs"
        
        # Configuration should be identical to what was loaded
        assert self.config_manager.configs["market"] == loaded_config, \
            "INVARIANT C1 VIOLATION: Configuration modified after loading"
        
        # Loading the same config again should not create duplicates
        loaded_again = self.config_manager.load_config("market")
        assert len(self.config_manager.configs) == 1, \
            f"INVARIANT C1 VIOLATION: Duplicate configurations created (count: {len(self.config_manager.configs)})"
        
        assert loaded_config == loaded_again, \
            "INVARIANT C1 VIOLATION: Configuration changed on reload"
    
    @given(
        config1=valid_market_config(),
        config2=valid_market_config()
    )
    @settings(max_examples=50, deadline=None)
    def test_property_1_multiple_config_types_allowed(self, config1, config2):
        """
        **Feature: northstar-v3-system-cohesion, Property 1: Single Source of Truth (C1)**
        
        For any set of different configuration types, the system should maintain
        exactly one active configuration per type.
        
        **Validates: Requirements 2.1, 4.1**
        """
        
        # Create different configuration files
        market_file = os.path.join(self.test_dir, "market.yaml")
        with open(market_file, 'w') as f:
            yaml.dump(config1, f)
        
        # Create a valid risk configuration
        risk_config = {
            "max_position_size": 0.08,
            "max_sector_exposure": 0.35,
            "max_drawdown_threshold": -0.40,
            "volatility_threshold": 0.25,
            "correlation_threshold": 0.80,
            "emergency_brake_params": {
                "max_drawdown_trigger": -0.10,
                "volatility_trigger": 0.03,
                "consecutive_losses": 5
            }
        }
        
        risk_file = os.path.join(self.test_dir, "risk.yaml")
        with open(risk_file, 'w') as f:
            yaml.dump(risk_config, f)
        
        # Load both configurations
        market_loaded = self.config_manager.load_config("market")
        risk_loaded = self.config_manager.load_config("risk")
        
        # INVARIANT C1: One configuration per type
        assert len(self.config_manager.configs) == 2, \
            f"INVARIANT C1 VIOLATION: Expected 2 configs, got {len(self.config_manager.configs)}"
        
        assert "market" in self.config_manager.configs, \
            "INVARIANT C1 VIOLATION: Market config not active"
        
        assert "risk" in self.config_manager.configs, \
            "INVARIANT C1 VIOLATION: Risk config not active"
        
        # Each config type should have exactly one active instance
        assert self.config_manager.configs["market"] == market_loaded, \
            "INVARIANT C1 VIOLATION: Market config corrupted"
        
        assert self.config_manager.configs["risk"] == risk_loaded, \
            "INVARIANT C1 VIOLATION: Risk config corrupted"
    
    # ========================================================================
    # PROPERTY 2: RISK PARAMETER CONSISTENCY (C2)
    # ========================================================================
    
    @given(risk_params=mathematically_consistent_risk_params())
    @settings(max_examples=100, deadline=None)
    def test_property_2_risk_parameter_consistency_valid(self, risk_params):
        """
        **Feature: northstar-v3-system-cohesion, Property 2: Risk Parameter Consistency (C2)**
        
        For any mathematically consistent risk configuration, the system must 
        accept and validate the parameters without errors.
        
        **Validates: Requirements 7.3, 7.7**
        """
        
        # Create risk configuration
        risk_config = RiskConfiguration(**risk_params)
        
        # Validate consistency
        validation_result = risk_config.validate_consistency()
        
        # INVARIANT C2: Mathematically consistent parameters must be valid
        assert validation_result.is_valid, \
            f"INVARIANT C2 VIOLATION: Valid risk parameters rejected: {[e.message for e in validation_result.errors]}"
        
        # No critical errors should be present
        critical_errors = [e for e in validation_result.errors if e.severity == ValidationSeverity.CRITICAL]
        assert len(critical_errors) == 0, \
            f"INVARIANT C2 VIOLATION: Critical errors in valid config: {[e.message for e in critical_errors]}"
        
        # Mathematical consistency check
        min_positions_per_sector = 4
        required_sector_exposure = risk_params["max_position_size"] * min_positions_per_sector
        
        assert required_sector_exposure <= risk_params["max_sector_exposure"], \
            f"INVARIANT C2 VIOLATION: Mathematical inconsistency not caught: " \
            f"{risk_params['max_position_size']:.3f} × {min_positions_per_sector} = " \
            f"{required_sector_exposure:.3f} > {risk_params['max_sector_exposure']:.3f}"
    
    @given(risk_params=mathematically_inconsistent_risk_params())
    @settings(max_examples=100, deadline=None)
    def test_property_2_risk_parameter_consistency_invalid(self, risk_params):
        """
        **Feature: northstar-v3-system-cohesion, Property 2: Risk Parameter Consistency (C2)**
        
        For any mathematically inconsistent risk configuration, the system must 
        reject the parameters with critical errors.
        
        **Validates: Requirements 7.3, 7.7**
        """
        
        # Create risk configuration
        risk_config = RiskConfiguration(**risk_params)
        
        # Validate consistency
        validation_result = risk_config.validate_consistency()
        
        # INVARIANT C2: Mathematically inconsistent parameters must be rejected
        assert not validation_result.is_valid, \
            f"INVARIANT C2 VIOLATION: Invalid risk parameters accepted: " \
            f"max_position={risk_params['max_position_size']:.3f}, " \
            f"max_sector={risk_params['max_sector_exposure']:.3f}"
        
        # Must have critical errors for mathematical inconsistency
        critical_errors = [e for e in validation_result.errors 
                          if e.severity == ValidationSeverity.CRITICAL and 
                          "C2_MATHEMATICAL_INCONSISTENCY" in e.code]
        
        assert len(critical_errors) > 0, \
            f"INVARIANT C2 VIOLATION: Mathematical inconsistency not detected as critical error"
        
        # Verify the mathematical relationship is indeed violated
        min_positions_per_sector = 4
        required_sector_exposure = risk_params["max_position_size"] * min_positions_per_sector
        
        assert required_sector_exposure > risk_params["max_sector_exposure"], \
            f"INVARIANT C2 VIOLATION: Test case is actually mathematically consistent: " \
            f"{risk_params['max_position_size']:.3f} × {min_positions_per_sector} = " \
            f"{required_sector_exposure:.3f} <= {risk_params['max_sector_exposure']:.3f}"
    
    # ========================================================================
    # PROPERTY 3: CONFIGURATION COMPLETENESS (C3)
    # ========================================================================
    
    @given(config_data=complete_market_config())
    @settings(max_examples=100, deadline=None)
    def test_property_3_configuration_completeness_valid(self, config_data):
        """
        **Feature: northstar-v3-system-cohesion, Property 3: Configuration Completeness (C3)**
        
        For any complete market configuration with all required fields, 
        the system must validate successfully without critical errors.
        
        **Validates: Requirements 2.6**
        """
        
        # Create market configuration
        market_config = MarketConfiguration(**config_data)
        
        # Validate completeness
        validation_result = market_config.validate()
        
        # INVARIANT C3: Complete configurations must be valid
        critical_errors = [e for e in validation_result.errors if e.severity == ValidationSeverity.CRITICAL]
        
        # Should not have critical completeness errors
        completeness_errors = [e for e in critical_errors if "C3_MISSING_FIELD" in e.code]
        assert len(completeness_errors) == 0, \
            f"INVARIANT C3 VIOLATION: Complete config rejected for missing fields: " \
            f"{[e.message for e in completeness_errors]}"
        
        # All required fields should be present and valid
        required_fields = ["market_name", "currency", "trading_hours", "sector_classifications", 
                          "risk_parameters", "data_sources", "indices"]
        
        for field in required_fields:
            assert hasattr(market_config, field), \
                f"INVARIANT C3 VIOLATION: Required field '{field}' missing from config object"
            
            value = getattr(market_config, field)
            assert value is not None, \
                f"INVARIANT C3 VIOLATION: Required field '{field}' is None"
    
    @given(config_data_and_missing=incomplete_market_config())
    @settings(max_examples=100, deadline=None)
    def test_property_3_configuration_completeness_invalid(self, config_data_and_missing):
        """
        **Feature: northstar-v3-system-cohesion, Property 3: Configuration Completeness (C3)**
        
        For any incomplete market configuration missing required fields, 
        the system must reject with critical completeness errors.
        
        **Validates: Requirements 2.6**
        """
        
        incomplete_config, missing_fields = config_data_and_missing
        
        # Attempt to create market configuration (should handle missing fields gracefully)
        try:
            # Fill in missing fields with None to allow object creation
            filled_config = {
                "market_name": None,
                "currency": None,
                "trading_hours": None,
                "sector_classifications": None,
                "risk_parameters": None,
                "data_sources": None,
                "indices": None
            }
            filled_config.update(incomplete_config)
            
            market_config = MarketConfiguration(**filled_config)
            
            # Validate completeness
            validation_result = market_config.validate()
            
            # INVARIANT C3: Incomplete configurations must be rejected
            assert not validation_result.is_valid, \
                f"INVARIANT C3 VIOLATION: Incomplete config accepted (missing: {missing_fields})"
            
            # Must have critical errors for missing fields
            critical_errors = [e for e in validation_result.errors if e.severity == ValidationSeverity.CRITICAL]
            missing_field_errors = [e for e in critical_errors if "C3_MISSING_FIELD" in e.code]
            
            assert len(missing_field_errors) > 0, \
                f"INVARIANT C3 VIOLATION: Missing fields not detected as critical errors (missing: {missing_fields})"
            
            # Should detect all missing fields
            detected_missing = {e.field for e in missing_field_errors}
            expected_missing = set(missing_fields)
            
            assert expected_missing.issubset(detected_missing), \
                f"INVARIANT C3 VIOLATION: Not all missing fields detected. " \
                f"Expected: {expected_missing}, Detected: {detected_missing}"
        
        except TypeError as e:
            # If object creation fails due to missing required parameters, that's also valid
            # as long as it's due to missing required fields
            for missing_field in missing_fields:
                assert missing_field in str(e), \
                    f"INVARIANT C3 VIOLATION: TypeError not related to missing field '{missing_field}': {e}"
    
    # ========================================================================
    # INTEGRATION PROPERTY TESTS
    # ========================================================================
    
    @given(
        market_config=valid_market_config(),
        risk_config=mathematically_consistent_risk_params()
    )
    @settings(max_examples=50, deadline=None)
    def test_property_integration_all_invariants(self, market_config, risk_config):
        """
        **Feature: northstar-v3-system-cohesion, Property Integration: All System Laws**
        
        For any valid configuration set, all three system laws must be satisfied
        simultaneously: C1 (Single Source), C2 (Risk Consistency), C3 (Completeness).
        
        **Validates: Requirements 2.1, 4.1, 7.3, 7.7, 2.6**
        """
        
        # Create configuration files
        market_file = os.path.join(self.test_dir, "market.yaml")
        with open(market_file, 'w') as f:
            yaml.dump(market_config, f)
        
        risk_file = os.path.join(self.test_dir, "risk.yaml")
        with open(risk_file, 'w') as f:
            yaml.dump(risk_config, f)
        
        # Load configurations through manager
        loaded_market = self.config_manager.load_config("market")
        loaded_risk = self.config_manager.load_config("risk")
        
        # Validate all system laws
        validation_result = self.config_manager.validate_all_configs()
        
        # ALL INVARIANTS MUST BE SATISFIED
        
        # INVARIANT C1: Single Source of Truth
        assert len(self.config_manager.configs) == 2, \
            f"INVARIANT C1 VIOLATION: Expected 2 configs, got {len(self.config_manager.configs)}"
        
        assert "market" in self.config_manager.configs, \
            "INVARIANT C1 VIOLATION: Market config not active"
        
        assert "risk" in self.config_manager.configs, \
            "INVARIANT C1 VIOLATION: Risk config not active"
        
        # INVARIANT C2: Risk Parameter Consistency
        risk_obj = RiskConfiguration(**risk_config)
        risk_validation = risk_obj.validate_consistency()
        assert risk_validation.is_valid, \
            f"INVARIANT C2 VIOLATION: Risk parameters inconsistent: {[e.message for e in risk_validation.errors]}"
        
        # INVARIANT C3: Configuration Completeness
        market_obj = MarketConfiguration(**market_config)
        market_validation = market_obj.validate()
        assert market_validation.is_valid, \
            f"INVARIANT C3 VIOLATION: Market config incomplete: {[e.message for e in market_validation.errors]}"
        
        # Overall system validation
        if not validation_result.is_valid:
            critical_errors = [e for e in validation_result.errors if e.severity == ValidationSeverity.CRITICAL]
            assert len(critical_errors) == 0, \
                f"SYSTEM LAW VIOLATION: Critical errors in valid configuration set: " \
                f"{[e.message for e in critical_errors]}"
        
        # System should be ready for operation
        assert validation_result.metadata.get('invariants_checked') == ['C1', 'C2', 'C3'], \
            "SYSTEM LAW VIOLATION: Not all invariants were checked"

# Example-based tests for edge cases
class TestConfigurationEdgeCases:
    """Example-based tests for specific edge cases and regression testing"""
    
    def setup_method(self):
        """Setup test environment"""
        self.test_dir = tempfile.mkdtemp()
        self.config_manager = ConfigurationManager(config_dir=self.test_dir)
    
    def teardown_method(self):
        """Cleanup test environment"""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_edge_case_exact_mathematical_boundary(self):
        """Test exact mathematical boundary for risk parameter consistency"""
        
        # Create risk config at exact mathematical boundary
        risk_config = {
            "max_position_size": 0.08,
            "max_sector_exposure": 0.32,  # Exactly 0.08 * 4
            "max_drawdown_threshold": -0.40,
            "volatility_threshold": 0.25,
            "correlation_threshold": 0.80,
            "emergency_brake_params": {
                "max_drawdown_trigger": -0.10,
                "volatility_trigger": 0.03,
                "consecutive_losses": 5
            }
        }
        
        risk_obj = RiskConfiguration(**risk_config)
        validation_result = risk_obj.validate_consistency()
        
        # Should be valid at exact boundary
        assert validation_result.is_valid, \
            f"Edge case failed: exact boundary should be valid: {[e.message for e in validation_result.errors]}"
    
    def test_edge_case_just_over_mathematical_boundary(self):
        """Test just over mathematical boundary for risk parameter consistency"""
        
        # Create risk config just over mathematical boundary
        risk_config = {
            "max_position_size": 0.08,
            "max_sector_exposure": 0.31,  # Just under 0.08 * 4 = 0.32
            "max_drawdown_threshold": -0.40,
            "volatility_threshold": 0.25,
            "correlation_threshold": 0.80,
            "emergency_brake_params": {
                "max_drawdown_trigger": -0.10,
                "volatility_trigger": 0.03,
                "consecutive_losses": 5
            }
        }
        
        risk_obj = RiskConfiguration(**risk_config)
        validation_result = risk_obj.validate_consistency()
        
        # Should be invalid just over boundary
        assert not validation_result.is_valid, \
            "Edge case failed: just over boundary should be invalid"
        
        # Should have mathematical inconsistency error
        math_errors = [e for e in validation_result.errors if "C2_MATHEMATICAL_INCONSISTENCY" in e.code]
        assert len(math_errors) > 0, \
            "Edge case failed: mathematical inconsistency not detected"

if __name__ == "__main__":
    # Run property tests
    pytest.main([__file__, "-v", "--tb=short"])