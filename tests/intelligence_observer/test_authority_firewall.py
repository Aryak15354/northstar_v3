#!/usr/bin/env python3
"""
Authority Firewall Tests

Tests the critical authority firewall that prevents the Intelligence Observer
from gaining any decision-making authority or influencing system behavior.

CRITICAL TESTS:
1. Forbidden module imports are blocked
2. Forbidden function calls are blocked
3. Write access attempts are blocked
4. Observer suspension works correctly
5. Violation tracking is accurate
6. Output validation catches forbidden content
"""

import pytest
import sys
import os
from datetime import datetime
from unittest.mock import Mock, patch

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from src.intelligence_observer.guardrails.authority_firewall import (
    AuthorityFirewall, ViolationType, AuthorityViolation,
    ObserverImportHook, get_authority_firewall, install_authority_firewall
)

class TestAuthorityFirewall:
    """Test Authority Firewall functionality"""
    
    def setup_method(self):
        """Setup for each test"""
        self.firewall = AuthorityFirewall()
    
    def test_firewall_initialization(self):
        """Test firewall initializes correctly"""
        assert self.firewall.name == "Intelligence Observer Authority Firewall"
        assert self.firewall.version == "1.0.0"
        assert len(self.firewall.forbidden_modules) > 0
        assert len(self.firewall.forbidden_functions) > 0
        assert len(self.firewall.forbidden_attributes) > 0
        assert self.firewall.violation_count == 0
        assert not self.firewall.observer_suspended
    
    def test_forbidden_module_import_blocked(self):
        """Test that forbidden module imports are blocked"""
        # Test forbidden modules
        forbidden_modules = [
            'src.portfolio.portfolio_governor',
            'src.risk.emergency_brake',
            'src.intelligence.dual_engine_coordinator',
            'src.core.state'
        ]
        
        for module in forbidden_modules:
            allowed = self.firewall.check_import_attempt(module)
            assert not allowed, f"Module {module} should be forbidden"
            
        # Check violation was recorded
        assert self.firewall.violation_count > 0
        assert any(v.violation_type == ViolationType.FORBIDDEN_IMPORT 
                  for v in self.firewall.violations)
    
    def test_allowed_module_import_permitted(self):
        """Test that allowed module imports are permitted"""
        allowed_modules = [
            'pandas',
            'numpy',
            'datetime',
            'src.intelligence_observer.observer_core',
            'src.utils.data_standards'
        ]
        
        initial_count = self.firewall.violation_count
        
        for module in allowed_modules:
            allowed = self.firewall.check_import_attempt(module)
            assert allowed, f"Module {module} should be allowed"
        
        # No new violations should be recorded
        assert self.firewall.violation_count == initial_count
    
    def test_forbidden_function_calls_blocked(self):
        """Test that forbidden function calls are blocked"""
        forbidden_functions = [
            'set_exposure',
            'modify_position',
            'override_risk_limit',
            'activate_engine',
            'force_rebalance',
            'emergency_stop'
        ]
        
        for func in forbidden_functions:
            allowed = self.firewall.check_function_call(func, 'test_module')
            assert not allowed, f"Function {func} should be forbidden"
        
        # Check violations were recorded
        assert self.firewall.violation_count >= len(forbidden_functions)
        assert any(v.violation_type == ViolationType.DECISION_INFLUENCE 
                  for v in self.firewall.violations)
    
    def test_write_operations_blocked(self):
        """Test that write operations are blocked"""
        write_functions = [
            'set_parameter',
            'update_config',
            'modify_state',
            'change_allocation',
            'override_limit',
            'force_update'
        ]
        
        for func in write_functions:
            allowed = self.firewall.check_function_call(func, 'test_module')
            assert not allowed, f"Write function {func} should be forbidden"
        
        # Check violations were recorded
        assert any(v.violation_type == ViolationType.WRITE_ACCESS_ATTEMPT 
                  for v in self.firewall.violations)
    
    def test_forbidden_attribute_access_blocked(self):
        """Test that forbidden attribute access is blocked"""
        forbidden_attributes = [
            'current_positions',
            'live_pnl',
            'real_time_exposure',
            'active_orders',
            'execution_queue'
        ]
        
        for attr in forbidden_attributes:
            allowed = self.firewall.check_attribute_access(attr, 'read')
            assert not allowed, f"Attribute {attr} should be forbidden"
        
        # Check violations were recorded
        assert any(v.violation_type == ViolationType.EXECUTION_INTERFERENCE 
                  for v in self.firewall.violations)
    
    def test_write_attribute_access_blocked(self):
        """Test that all write attribute access is blocked"""
        test_attributes = [
            'allowed_attribute',
            'config_parameter',
            'data_field'
        ]
        
        for attr in test_attributes:
            allowed = self.firewall.check_attribute_access(attr, 'write')
            assert not allowed, f"Write access to {attr} should be forbidden"
        
        # Check violations were recorded
        assert any(v.violation_type == ViolationType.WRITE_ACCESS_ATTEMPT 
                  for v in self.firewall.violations)
    
    def test_observer_suspension_after_violations(self):
        """Test that Observer is suspended after multiple violations"""
        # Generate multiple violations
        for i in range(5):
            self.firewall.check_import_attempt('src.portfolio.portfolio_governor')
        
        # Observer should be suspended after 3 violations
        assert self.firewall.observer_suspended
        assert self.firewall.violation_count >= 3
    
    def test_output_validation_dict(self):
        """Test output validation for dictionary outputs"""
        # Valid output
        valid_output = {
            'score_value': 67.5,
            'confidence': 0.82,
            'interpretation': 'Current conditions resemble historical patterns'
        }
        
        assert self.firewall.validate_observer_output(valid_output)
        
        # Invalid output with forbidden keys
        invalid_output = {
            'score_value': 67.5,
            'trade_signal': 'BUY',  # Forbidden
            'position_change': 0.1   # Forbidden
        }
        
        assert not self.firewall.validate_observer_output(invalid_output)
        
        # Check violation was recorded
        assert any(v.violation_type == ViolationType.DECISION_INFLUENCE 
                  for v in self.firewall.violations)
    
    def test_output_validation_string(self):
        """Test output validation for string outputs"""
        # Valid output
        valid_output = "Current market conditions resemble historically volatile periods"
        assert self.firewall.validate_observer_output(valid_output)
        
        # Invalid outputs with forbidden phrases
        invalid_outputs = [
            "System should trade more aggressively",
            "Must buy this opportunity",
            "Should increase position size",
            "Must activate engine immediately"
        ]
        
        for output in invalid_outputs:
            assert not self.firewall.validate_observer_output(output)
        
        # Check violations were recorded
        assert any(v.violation_type == ViolationType.DECISION_INFLUENCE 
                  for v in self.firewall.violations)
    
    def test_violation_summary(self):
        """Test violation summary functionality"""
        # Generate some violations
        self.firewall.check_import_attempt('src.portfolio.portfolio_governor')
        self.firewall.check_function_call('set_exposure', 'test_module')
        
        summary = self.firewall.get_violation_summary()
        
        assert 'total_violations' in summary
        assert 'observer_suspended' in summary
        assert 'violations_by_type' in summary
        assert 'recent_violations' in summary
        
        assert summary['total_violations'] >= 2
        assert len(summary['recent_violations']) >= 2
    
    def test_violation_reset_with_authorization(self):
        """Test violation reset with proper authorization"""
        # Generate violations
        self.firewall.check_import_attempt('src.portfolio.portfolio_governor')
        assert self.firewall.violation_count > 0
        
        # Reset with correct authorization
        self.firewall.reset_violations("NORTHSTAR_ADMIN_RESET")
        
        assert self.firewall.violation_count == 0
        assert len(self.firewall.violations) == 0
        assert not self.firewall.observer_suspended
    
    def test_violation_reset_without_authorization(self):
        """Test violation reset fails without proper authorization"""
        # Generate violations
        self.firewall.check_import_attempt('src.portfolio.portfolio_governor')
        initial_count = self.firewall.violation_count
        
        # Try reset with wrong authorization
        self.firewall.reset_violations("WRONG_CODE")
        
        # Should not reset
        assert self.firewall.violation_count == initial_count
    
    def test_violation_record_structure(self):
        """Test that violation records have correct structure"""
        self.firewall.check_import_attempt('src.portfolio.portfolio_governor')
        
        assert len(self.firewall.violations) > 0
        violation = self.firewall.violations[0]
        
        assert isinstance(violation, AuthorityViolation)
        assert violation.violation_type == ViolationType.FORBIDDEN_IMPORT
        assert isinstance(violation.timestamp, datetime)
        assert violation.module_name == 'src.portfolio.portfolio_governor'
        assert violation.function_name == 'import'
        assert 'forbidden module' in violation.attempted_action.lower()
        assert violation.severity == "HIGH"
        
        # Test to_dict conversion
        violation_dict = violation.to_dict()
        assert 'violation_type' in violation_dict
        assert 'timestamp' in violation_dict
        assert 'module_name' in violation_dict

class TestObserverImportHook:
    """Test Observer Import Hook functionality"""
    
    def setup_method(self):
        """Setup for each test"""
        self.firewall = AuthorityFirewall()
        self.import_hook = ObserverImportHook(self.firewall)
    
    def test_import_hook_creation(self):
        """Test import hook is created correctly"""
        assert self.import_hook.firewall == self.firewall
        assert self.import_hook.original_import is not None
    
    @patch('builtins.__import__')
    def test_import_hook_blocks_forbidden_modules(self, mock_import):
        """Test import hook blocks forbidden modules for Observer"""
        # Mock globals to simulate Observer module
        mock_globals = {'__name__': 'src.intelligence_observer.test_module'}
        
        # Try to import forbidden module
        with pytest.raises(ImportError, match="Authority Firewall"):
            self.import_hook('src.portfolio.portfolio_governor', 
                           globals=mock_globals)
        
        # Check violation was recorded
        assert self.firewall.violation_count > 0
    
    def test_import_hook_allows_normal_modules(self):
        """Test import hook allows normal modules for Observer"""
        # Mock globals to simulate Observer module
        mock_globals = {'__name__': 'src.intelligence_observer.test_module'}
        
        # Mock the original import to return a dummy module
        self.import_hook.original_import = Mock(return_value=Mock())
        
        # Try to import allowed module
        result = self.import_hook('pandas', globals=mock_globals)
        
        # Should succeed
        assert result is not None
        assert self.firewall.violation_count == 0

class TestGlobalFirewallFunctions:
    """Test global firewall functions"""
    
    def test_get_authority_firewall_singleton(self):
        """Test that get_authority_firewall returns singleton"""
        firewall1 = get_authority_firewall()
        firewall2 = get_authority_firewall()
        
        assert firewall1 is firewall2
        assert isinstance(firewall1, AuthorityFirewall)
    
    def test_install_authority_firewall(self):
        """Test authority firewall installation"""
        firewall = install_authority_firewall()
        
        assert isinstance(firewall, AuthorityFirewall)
        # In a real test, we'd check that the import hook is installed
        # but that's complex to test without affecting the test environment

class TestAuthorityFirewallEdgeCases:
    """Test edge cases and error conditions"""
    
    def setup_method(self):
        """Setup for each test"""
        self.firewall = AuthorityFirewall()
    
    def test_empty_module_name(self):
        """Test handling of empty module names"""
        allowed = self.firewall.check_import_attempt('')
        assert allowed  # Empty module name should be allowed
    
    def test_none_module_name(self):
        """Test handling of None module names"""
        # Should handle gracefully without crashing
        try:
            allowed = self.firewall.check_import_attempt(None)
            # Behavior may vary, but shouldn't crash
        except (TypeError, AttributeError):
            # Acceptable to raise these exceptions
            pass
    
    def test_nested_dict_output_validation(self):
        """Test validation of nested dictionary outputs"""
        nested_output = {
            'level1': {
                'level2': {
                    'trade_signal': 'BUY'  # Forbidden nested key
                }
            }
        }
        
        assert not self.firewall.validate_observer_output(nested_output)
        
        # Check violation was recorded
        assert any(v.violation_type == ViolationType.DECISION_INFLUENCE 
                  for v in self.firewall.violations)
    
    def test_object_with_to_dict_validation(self):
        """Test validation of objects with to_dict method"""
        class MockOutput:
            def to_dict(self):
                return {'trade_signal': 'SELL'}  # Forbidden content
        
        mock_output = MockOutput()
        assert not self.firewall.validate_observer_output(mock_output)
    
    def test_case_insensitive_string_validation(self):
        """Test that string validation is case insensitive"""
        forbidden_phrases = [
            "SHOULD TRADE aggressively",
            "Must BUY this opportunity",
            "should INCREASE position"
        ]
        
        for phrase in forbidden_phrases:
            assert not self.firewall.validate_observer_output(phrase)
    
    def test_partial_match_forbidden_modules(self):
        """Test that partial matches of forbidden modules are caught"""
        # Test modules that contain forbidden module names
        test_modules = [
            'src.portfolio.portfolio_governor.submodule',
            'custom.src.risk.emergency_brake.extension'
        ]
        
        for module in test_modules:
            allowed = self.firewall.check_import_attempt(module)
            assert not allowed, f"Module {module} should be forbidden (partial match)"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])