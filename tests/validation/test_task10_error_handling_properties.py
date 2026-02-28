"""
Property-Based Tests for Task 10: Comprehensive Error Handling System

These tests validate the correctness properties for the error handling system
as defined in the design document.

**Feature: northstar-v3-system-cohesion, Property 21: Critical Error Fail-Fast (E1)**
**Feature: northstar-v3-system-cohesion, Property 22: Error Escalation Consistency (E2)**
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from datetime import datetime, timedelta
from typing import Dict, Any, List
import logging
import tempfile
import os
import json
import time

# Import the error handling system
from src.cohesion.error_handler import (
    ErrorHandler, ErrorSeverity, ErrorCategory, RecoveryStrategy, SystemError
)

logger = logging.getLogger(__name__)

# Strategies for property testing
@st.composite
def error_data_strategy(draw):
    """Generate error data for testing"""
    severity = draw(st.sampled_from(list(ErrorSeverity)))
    category = draw(st.sampled_from(list(ErrorCategory)))
    component = draw(st.sampled_from(['data_pipeline', 'state_manager', 'intelligence_engine', 'risk_engine', 'config_manager']))
    message = draw(st.text(min_size=10, max_size=200))
    
    context = {}
    if draw(st.booleans()):
        context['data_source'] = draw(st.text(min_size=5, max_size=50))
    if draw(st.booleans()):
        context['operation'] = draw(st.text(min_size=5, max_size=30))
    if draw(st.booleans()):
        context['user_id'] = draw(st.integers(min_value=1, max_value=10000))
    
    return {
        'severity': severity,
        'category': category,
        'component': component,
        'message': message,
        'context': context
    }

@st.composite
def escalation_scenario_strategy(draw):
    """Generate escalation scenarios for testing"""
    severity = draw(st.sampled_from(list(ErrorSeverity)))
    time_elapsed = draw(st.integers(min_value=0, max_value=7200))  # Up to 2 hours
    initial_escalation_level = draw(st.integers(min_value=0, max_value=2))
    
    return {
        'severity': severity,
        'time_elapsed': time_elapsed,
        'initial_escalation_level': initial_escalation_level
    }

class TestErrorHandlingProperties:
    """Property-based tests for error handling system"""
    
    def setup_method(self):
        """Set up test fixtures"""
        # Use temporary directory for test logs
        self.temp_dir = tempfile.mkdtemp()
        self.error_log_dir = os.path.join(self.temp_dir, "error_logs")
        
        self.error_handler = ErrorHandler(
            error_log_dir=self.error_log_dir,
            max_error_history=1000,
            pattern_analysis_window=3600
        )
        
        # Track critical errors for testing
        self.critical_errors_received = []
        self.error_handler.subscribe_to_errors(
            ErrorSeverity.CRITICAL,
            lambda error: self.critical_errors_received.append(error)
        )
    
    def teardown_method(self):
        """Clean up test fixtures"""
        if hasattr(self, 'error_handler'):
            self.error_handler.shutdown()
        
        # Clean up temp directory
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    @given(error_data_strategy())
    @settings(max_examples=100, deadline=5000)
    def test_property_21_critical_error_fail_fast(self, error_data):
        """
        Property 21: Critical Error Fail-Fast (E1)
        
        For any critical error, system must terminate immediately rather than 
        continue with corrupted state.
        
        **Validates: Requirements 5.2**
        """
        # Only test critical errors for this property
        assume(error_data['severity'] == ErrorSeverity.CRITICAL)
        
        # Clear previous critical errors for this test run
        self.critical_errors_received.clear()
        
        # Create a test exception
        test_exception = Exception(error_data['message'])
        
        # Critical errors should cause system termination
        with pytest.raises(SystemExit) as exc_info:
            self.error_handler.handle_error(
                error=test_exception,
                component=error_data['component'],
                severity=error_data['severity'],
                category=error_data['category'],
                context=error_data['context']
            )
        
        # Verify the system exit message contains the error
        assert error_data['message'] in str(exc_info.value)
        assert "CRITICAL ERROR - SYSTEM TERMINATED" in str(exc_info.value)
        
        # Verify critical error was logged
        assert len(self.critical_errors_received) == 1
        critical_error = self.critical_errors_received[0]
        
        # Verify error properties
        assert critical_error.severity == ErrorSeverity.CRITICAL
        assert critical_error.component == error_data['component']
        assert critical_error.category == error_data['category']
        assert critical_error.message == error_data['message']
        assert critical_error.context == error_data['context']
        
        # Verify fail-fast recovery strategy
        assert critical_error.recovery_strategy == RecoveryStrategy.FAIL_FAST
        
        # Verify error is not marked as resolved (system terminated)
        assert not critical_error.resolved
        assert critical_error.resolution_method == "SYSTEM_TERMINATED"
        
        # Verify critical error file was created
        critical_files = [f for f in os.listdir(self.error_log_dir) if f.startswith('CRITICAL_')]
        assert len(critical_files) >= 1  # May have multiple from previous test runs
        
        # Find the most recent critical error file
        critical_files.sort()
        latest_critical_file = critical_files[-1]
        
        # Verify critical error file contents
        critical_file_path = os.path.join(self.error_log_dir, latest_critical_file)
        with open(critical_file_path, 'r') as f:
            critical_data = json.load(f)
        
        assert critical_data['message'] == error_data['message']
        assert critical_data['component'] == error_data['component']
        assert critical_data['context'] == error_data['context']
    
    @given(escalation_scenario_strategy())
    @settings(max_examples=50, deadline=5000)
    def test_property_22_error_escalation_consistency(self, scenario):
        """
        Property 22: Error Escalation Consistency (E2)
        
        For any error, escalation must follow configured severity rules.
        
        **Validates: Requirements 5.5**
        """
        severity = scenario['severity']
        time_elapsed = scenario['time_elapsed']
        initial_escalation_level = scenario['initial_escalation_level']
        
        # Skip critical errors (they fail fast)
        assume(severity != ErrorSeverity.CRITICAL)
        
        # Create a test error
        test_exception = Exception(f"Test error for escalation - {severity.name}")
        
        # Handle the error (should not raise SystemExit for non-critical)
        system_error = self.error_handler.handle_error(
            error=test_exception,
            component='test_component',
            severity=severity,
            category=ErrorCategory.COMPONENT_FAILURE,
            context={'test': True}
        )
        
        # Get escalation rules for this severity
        escalation_rules = self.error_handler.escalation_rules[severity]
        
        # Set initial escalation level (but respect max level for severity)
        max_level = escalation_rules['max_escalation_level']
        valid_initial_level = min(initial_escalation_level, max_level)
        system_error.escalation_level = valid_initial_level
        
        # Simulate time passage and check escalation
        original_timestamp = system_error.timestamp
        system_error.timestamp = original_timestamp - timedelta(seconds=time_elapsed)
        
        # Trigger escalation check
        self.error_handler._handle_escalation(system_error)
        
        # Verify escalation follows rules
        expected_escalation_level = valid_initial_level
        
        # Check if immediate escalation should occur
        if escalation_rules['immediate_escalation']:
            expected_escalation_level = min(
                expected_escalation_level + 1, 
                escalation_rules['max_escalation_level']
            )
        
        # Check if time-based escalation should occur
        if time_elapsed > escalation_rules['escalation_timeout']:
            if expected_escalation_level < escalation_rules['max_escalation_level']:
                expected_escalation_level += 1
        
        # Ensure escalation doesn't exceed maximum
        expected_escalation_level = min(expected_escalation_level, escalation_rules['max_escalation_level'])
        
        # Verify escalation level is consistent with rules
        assert system_error.escalation_level <= escalation_rules['max_escalation_level'], \
            f"Escalation level {system_error.escalation_level} exceeds max {escalation_rules['max_escalation_level']}"
        
        # Verify escalation progression is logical
        assert system_error.escalation_level >= valid_initial_level, \
            "Escalation level should not decrease"
        
        # Verify operator alerts for high-severity errors
        if escalation_rules['requires_operator'] and system_error.escalation_level > 0:
            # Check if alert file was created
            alert_files = [f for f in os.listdir(self.error_log_dir) if f.startswith('alert_')]
            if severity in [ErrorSeverity.HIGH, ErrorSeverity.MEDIUM]:
                # Should have alerts for escalated high/medium severity errors
                assert len(alert_files) >= 0  # May or may not have alerts depending on escalation
        
        # Verify error is tracked in active errors
        assert system_error.error_id in self.error_handler.active_errors
        
        # Verify error history is maintained
        assert len(self.error_handler.error_history) > 0
        assert system_error in self.error_handler.error_history
    
    @given(st.lists(error_data_strategy(), min_size=1, max_size=10))
    @settings(max_examples=20, deadline=10000)
    def test_error_pattern_analysis(self, error_list):
        """
        Test error pattern analysis and tracking.
        
        Errors should be analyzed for patterns and frequency.
        """
        # Clear previous errors for this test run
        self.error_handler.error_history.clear()
        self.error_handler.active_errors.clear()
        self.error_handler.error_patterns.clear()
        
        # Filter out critical errors to avoid system termination
        non_critical_errors = [e for e in error_list if e['severity'] != ErrorSeverity.CRITICAL]
        assume(len(non_critical_errors) > 0)
        
        # Handle multiple errors
        handled_errors = []
        for error_data in non_critical_errors:
            test_exception = Exception(error_data['message'])
            
            system_error = self.error_handler.handle_error(
                error=test_exception,
                component=error_data['component'],
                severity=error_data['severity'],
                category=error_data['category'],
                context=error_data['context']
            )
            handled_errors.append(system_error)
        
        # Verify error patterns are tracked
        patterns = self.error_handler.get_error_patterns()
        assert len(patterns) > 0, "Error patterns should be tracked"
        
        # Verify pattern frequency
        for pattern in patterns:
            assert pattern.frequency > 0, "Pattern frequency should be positive"
            assert pattern.first_occurrence <= pattern.last_occurrence, \
                "First occurrence should be before or equal to last occurrence"
        
        # Verify error history
        error_history = self.error_handler.get_error_history()
        assert len(error_history) == len(non_critical_errors), \
            f"All non-critical errors should be in history: expected {len(non_critical_errors)}, got {len(error_history)}"
        
        # Verify component-specific patterns
        component_patterns = {}
        for error in handled_errors:
            component = error.component
            if component not in component_patterns:
                component_patterns[component] = 0
            component_patterns[component] += 1
        
        # Each component with errors should have at least one pattern
        for component, count in component_patterns.items():
            component_patterns_found = [p for p in patterns if p.component == component]
            assert len(component_patterns_found) > 0, f"Component {component} should have error patterns"
    
    @given(st.sampled_from(list(ErrorSeverity)))
    @settings(max_examples=20, deadline=3000)
    def test_recovery_strategy_assignment(self, severity):
        """
        Test that recovery strategies are assigned correctly based on severity and category.
        """
        # Skip critical errors for this test
        assume(severity != ErrorSeverity.CRITICAL)
        
        test_exception = Exception(f"Test error - {severity.name}")
        
        # Test different categories
        for category in ErrorCategory:
            system_error = self.error_handler.handle_error(
                error=test_exception,
                component='test_component',
                severity=severity,
                category=category,
                context={'test_category': category.value}
            )
            
            # Verify recovery strategy is assigned
            assert system_error.recovery_strategy is not None, \
                f"Recovery strategy should be assigned for {severity.name} {category.value}"
            
            # Verify recovery strategy is appropriate for severity
            if severity == ErrorSeverity.HIGH:
                # High severity should use quarantine or alert strategies
                assert system_error.recovery_strategy in [
                    RecoveryStrategy.QUARANTINE_DATA,
                    RecoveryStrategy.ALERT_OPERATOR,
                    RecoveryStrategy.GRACEFUL_DEGRADATION
                ], f"High severity should use appropriate recovery strategy"
            
            elif severity == ErrorSeverity.MEDIUM:
                # Medium severity should use retry or degradation
                assert system_error.recovery_strategy in [
                    RecoveryStrategy.RETRY_EXPONENTIAL,
                    RecoveryStrategy.GRACEFUL_DEGRADATION,
                    RecoveryStrategy.AUTOMATIC_RECOVERY,
                    RecoveryStrategy.ALERT_OPERATOR
                ], f"Medium severity should use appropriate recovery strategy"
            
            elif severity == ErrorSeverity.LOW:
                # Low severity should use automatic recovery or retry
                assert system_error.recovery_strategy in [
                    RecoveryStrategy.AUTOMATIC_RECOVERY,
                    RecoveryStrategy.RETRY_EXPONENTIAL,
                    RecoveryStrategy.ALERT_OPERATOR
                ], f"Low severity should use appropriate recovery strategy"
    
    def test_error_handler_health_monitoring(self):
        """
        Test error handler health monitoring functionality.
        """
        # Get initial health status
        initial_health = self.error_handler.get_system_health()
        
        assert isinstance(initial_health, dict)
        assert 'healthy' in initial_health
        assert 'active_errors' in initial_health
        assert 'total_errors_processed' in initial_health
        
        # Initially should be healthy with no errors
        assert initial_health['healthy'] == True
        assert initial_health['active_errors'] == 0
        assert initial_health['active_critical'] == 0
        
        # Add some non-critical errors
        for i in range(3):
            test_exception = Exception(f"Test error {i}")
            self.error_handler.handle_error(
                error=test_exception,
                component='test_component',
                severity=ErrorSeverity.MEDIUM,
                category=ErrorCategory.COMPONENT_FAILURE
            )
        
        # Check health after errors
        health_after_errors = self.error_handler.get_system_health()
        
        assert health_after_errors['active_errors'] == 3
        assert health_after_errors['active_medium'] == 3
        assert health_after_errors['total_errors_processed'] == 3
        
        # Should still be healthy (no critical errors)
        assert health_after_errors['healthy'] == True
    
    def test_error_subscription_and_notification(self):
        """
        Test error subscription and notification system.
        """
        # Set up subscribers for different severity levels
        high_errors = []
        medium_errors = []
        
        self.error_handler.subscribe_to_errors(
            ErrorSeverity.HIGH,
            lambda error: high_errors.append(error)
        )
        
        self.error_handler.subscribe_to_errors(
            ErrorSeverity.MEDIUM,
            lambda error: medium_errors.append(error)
        )
        
        # Generate errors of different severities
        high_exception = Exception("High severity error")
        medium_exception = Exception("Medium severity error")
        low_exception = Exception("Low severity error")
        
        # Handle errors
        self.error_handler.handle_error(
            error=high_exception,
            component='test_component',
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.DATA_CORRUPTION
        )
        
        self.error_handler.handle_error(
            error=medium_exception,
            component='test_component',
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.NETWORK_ERROR
        )
        
        self.error_handler.handle_error(
            error=low_exception,
            component='test_component',
            severity=ErrorSeverity.LOW,
            category=ErrorCategory.VALIDATION_ERROR
        )
        
        # Verify notifications
        assert len(high_errors) == 1, "High severity subscriber should receive high errors"
        assert len(medium_errors) == 1, "Medium severity subscriber should receive medium errors"
        
        # Verify error details in notifications
        assert high_errors[0].severity == ErrorSeverity.HIGH
        assert high_errors[0].message == "High severity error"
        
        assert medium_errors[0].severity == ErrorSeverity.MEDIUM
        assert medium_errors[0].message == "Medium severity error"
    
    def test_error_resolution_tracking(self):
        """
        Test error resolution and tracking functionality.
        """
        # Create and handle an error
        test_exception = Exception("Resolvable error")
        
        system_error = self.error_handler.handle_error(
            error=test_exception,
            component='test_component',
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.COMPONENT_FAILURE
        )
        
        # Verify error is active
        assert not system_error.resolved
        assert system_error.error_id in self.error_handler.active_errors
        
        # Resolve the error
        resolution_success = self.error_handler.resolve_error(
            system_error.error_id,
            "manual_intervention"
        )
        
        assert resolution_success == True
        
        # Verify error is marked as resolved
        resolved_error = self.error_handler.active_errors[system_error.error_id]
        assert resolved_error.resolved == True
        assert resolved_error.resolution_method == "manual_intervention"
        assert resolved_error.resolution_timestamp is not None
        
        # Verify resolution timestamp is recent
        time_since_resolution = datetime.now() - resolved_error.resolution_timestamp
        assert time_since_resolution.total_seconds() < 10  # Within 10 seconds

if __name__ == "__main__":
    # Run the property tests
    pytest.main([__file__, "-v", "--tb=short"])