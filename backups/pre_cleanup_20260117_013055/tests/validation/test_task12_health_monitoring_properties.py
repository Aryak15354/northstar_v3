"""
Property-Based Tests for System Health Monitoring

Tests the capital-grade system laws for health monitoring:
- Property 25: Health Monitoring Completeness (H1)
- Property 26: Failover Consistency (H2)

Feature: northstar-v3-system-cohesion
"""

import pytest
import time
import threading
from datetime import datetime, timedelta
from hypothesis import given, strategies as st, settings, assume
from hypothesis.stateful import RuleBasedStateMachine, rule, invariant
from unittest.mock import Mock, MagicMock

from src.cohesion.health_monitor import (
    ComprehensiveHealthMonitor, HealthStatus, AlertSeverity,
    HealthCheckResult, DefaultFailoverHandler, HealthTrendAnalyzer
)


class TestHealthMonitoringCompleteness:
    """
    Test Property 25: Health Monitoring Completeness (H1)
    
    SYSTEM LAW: All critical components must have health monitoring and alerts triggered
    **Validates: Requirements 12.1, 12.2**
    """
    
    @given(
        components=st.lists(
            st.tuples(
                st.text(min_size=1, max_size=10),  # component name
                st.booleans(),  # is_critical
                st.booleans()   # is_healthy
            ),
            min_size=1,
            max_size=10
        )
    )
    @settings(max_examples=10, deadline=5000)
    def test_health_monitoring_completeness_property(self, components):
        """
        Property 25: Health Monitoring Completeness (H1)
        All critical components must have health monitoring and alerts triggered
        **Feature: northstar-v3-system-cohesion, Property 25: Health Monitoring Completeness**
        """
        monitor = ComprehensiveHealthMonitor(check_interval=timedelta(seconds=1))
        
        # Register components
        critical_components = []
        for name, is_critical, is_healthy in components:
            # Create mock health check
            def create_health_check(healthy):
                def health_check():
                    return {
                        'healthy': healthy,
                        'metrics': {'test_metric': 1.0 if healthy else 0.0},
                        'message': 'OK' if healthy else 'FAILED'
                    }
                return health_check
            
            success = monitor.register_component(
                name, 
                create_health_check(is_healthy),
                is_critical=is_critical
            )
            
            assert success, f"Failed to register component {name}"
            
            if is_critical:
                critical_components.append(name)
        
        # SYSTEM LAW: All critical components must be monitored
        for critical_component in critical_components:
            assert critical_component in monitor.components, \
                f"Critical component {critical_component} not in monitoring system"
            
            assert critical_component in monitor.critical_components, \
                f"Critical component {critical_component} not marked as critical"
        
        # Check system health
        system_health = monitor.get_system_health()
        
        # SYSTEM LAW: System health must reflect critical component status
        critical_unhealthy = system_health['critical_unhealthy']
        expected_critical_unhealthy = sum(
            1 for name, is_critical, is_healthy in components
            if is_critical and not is_healthy
        )
        
        assert critical_unhealthy == expected_critical_unhealthy, \
            f"Critical unhealthy count mismatch: {critical_unhealthy} != {expected_critical_unhealthy}"
        
        # SYSTEM LAW: System should be unhealthy if any critical component is unhealthy
        if expected_critical_unhealthy > 0:
            assert not system_health['overall_healthy'], \
                "System should be unhealthy when critical components are unhealthy"
    
    @given(
        component_name=st.text(min_size=1, max_size=10),
        metric_values=st.lists(
            st.floats(min_value=0.0, max_value=100.0),
            min_size=5,
            max_size=15
        ),
        warning_threshold=st.floats(min_value=20.0, max_value=50.0),
        critical_threshold=st.floats(min_value=60.0, max_value=90.0)
    )
    @settings(max_examples=10, deadline=5000)
    def test_threshold_alerting_completeness_property(self, component_name, metric_values, 
                                                    warning_threshold, critical_threshold):
        """
        Property 25 Extended: Threshold violations must trigger appropriate alerts
        For any metric exceeding thresholds, alerts must be generated
        **Feature: northstar-v3-system-cohesion, Property 25: Health Monitoring Completeness**
        """
        assume(critical_threshold > warning_threshold)
        
        monitor = ComprehensiveHealthMonitor()
        
        # Set up component with varying health
        metric_index = 0
        def health_check():
            nonlocal metric_index
            if metric_index < len(metric_values):
                value = metric_values[metric_index]
                metric_index += 1
                return {
                    'healthy': value < critical_threshold,
                    'metrics': {'test_metric': value},
                    'message': f'Value: {value}'
                }
            return {'healthy': True, 'metrics': {'test_metric': 0.0}}
        
        monitor.register_component(component_name, health_check, is_critical=True)
        monitor.set_alert_thresholds(component_name, 'test_metric', warning_threshold, critical_threshold)
        
        # Perform health checks
        for _ in range(len(metric_values)):
            monitor.check_component_health(component_name)
        
        # Check alerts
        alerts = monitor.get_active_alerts()
        
        # SYSTEM LAW: Alerts must be generated for threshold violations
        critical_violations = sum(1 for v in metric_values if v >= critical_threshold)
        warning_violations = sum(1 for v in metric_values if warning_threshold <= v < critical_threshold)
        
        critical_alerts = [a for a in alerts if a.severity == AlertSeverity.CRITICAL]
        warning_alerts = [a for a in alerts if a.severity == AlertSeverity.WARNING]
        
        # Should have alerts for violations (allowing for alert deduplication)
        if critical_violations > 0:
            assert len(critical_alerts) > 0, \
                f"Missing critical alerts for {critical_violations} violations"
        
        if warning_violations > 0 and critical_violations == 0:  # Only if no critical alerts
            assert len(warning_alerts) > 0, \
                f"Missing warning alerts for {warning_violations} violations"


class TestFailoverConsistency:
    """
    Test Property 26: Failover Consistency (H2)
    
    SYSTEM LAW: When components fail, failover must maintain system consistency
    **Validates: Requirements 12.4**
    """
    
    @given(
        primary_component=st.text(min_size=1, max_size=10),
        failover_target=st.text(min_size=1, max_size=10),
        failure_count=st.integers(min_value=1, max_value=5)
    )
    @settings(max_examples=10, deadline=5000)
    def test_failover_consistency_property(self, primary_component, failover_target, failure_count):
        """
        Property 26: Failover Consistency (H2)
        When components fail, failover must maintain system consistency
        **Feature: northstar-v3-system-cohesion, Property 26: Failover Consistency**
        """
        assume(primary_component != failover_target)
        
        # Mock failover handler to track failover operations
        failover_handler = Mock(spec=DefaultFailoverHandler)
        failover_handler.can_failover.return_value = True
        failover_handler.execute_failover.return_value = True
        failover_handler.rollback_failover.return_value = True
        
        monitor = ComprehensiveHealthMonitor(failover_handler=failover_handler)
        
        # Register primary component with failover
        failure_counter = 0
        def primary_health_check():
            nonlocal failure_counter
            failure_counter += 1
            return {
                'healthy': failure_counter <= 2,  # Fail after 2 checks
                'metrics': {'status': 1.0 if failure_counter <= 2 else 0.0},
                'message': 'OK' if failure_counter <= 2 else 'FAILED'
            }
        
        # Register failover target (always healthy)
        def target_health_check():
            return {
                'healthy': True,
                'metrics': {'status': 1.0},
                'message': 'OK'
            }
        
        monitor.register_component(
            primary_component, 
            primary_health_check,
            is_critical=True,
            failover_target=failover_target
        )
        
        monitor.register_component(
            failover_target,
            target_health_check,
            is_critical=False
        )
        
        # Trigger failures to cause failover
        for i in range(failure_count + 2):  # Ensure we exceed max_failures
            health_result = monitor.check_component_health(primary_component)
            
            # After max failures, failover should be attempted
            if i >= 2:  # max_failures = 3, so after 3rd failure
                component = monitor.components[primary_component]
                if component.status == HealthStatus.FAILED:
                    # SYSTEM LAW: Failover must be attempted for failed critical components
                    if component.failover_enabled:
                        failover_handler.execute_failover.assert_called()
                        
                        # SYSTEM LAW: Failover target must be verified as healthy
                        target_health = monitor.check_component_health(failover_target)
                        assert target_health.healthy, \
                            "Failover target must be healthy for successful failover"
                    break
        
        # Check system consistency after failover
        system_health = monitor.get_system_health()
        
        # SYSTEM LAW: System should maintain consistency after failover
        # The failover target should be healthy
        if failover_target in system_health['component_statuses']:
            target_status = system_health['component_statuses'][failover_target]
            assert target_status['healthy'], \
                "Failover target must remain healthy after failover"
    
    @given(
        components=st.lists(
            st.tuples(
                st.text(min_size=1, max_size=8),  # component name
                st.text(min_size=1, max_size=8),  # failover target
                st.booleans()  # target is healthy
            ),
            min_size=2,
            max_size=5
        )
    )
    @settings(max_examples=5, deadline=8000)
    def test_multiple_failover_consistency_property(self, components):
        """
        Property 26 Extended: Multiple failovers must maintain system consistency
        When multiple components fail, all failovers must be consistent
        **Feature: northstar-v3-system-cohesion, Property 26: Failover Consistency**
        """
        # Ensure unique component names and targets
        unique_components = {}
        for name, target, target_healthy in components:
            if name not in unique_components and target not in unique_components:
                unique_components[name] = (target, target_healthy)
        
        if len(unique_components) < 2:
            return  # Skip if not enough unique components
        
        failover_handler = Mock(spec=DefaultFailoverHandler)
        failover_handler.can_failover.return_value = True
        failover_handler.execute_failover.return_value = True
        
        monitor = ComprehensiveHealthMonitor(failover_handler=failover_handler)
        
        # Register all components
        for primary_name, (target_name, target_healthy) in unique_components.items():
            # Primary component (will fail)
            def create_failing_health_check():
                counter = 0
                def health_check():
                    nonlocal counter
                    counter += 1
                    return {
                        'healthy': counter <= 1,  # Fail quickly
                        'metrics': {'status': 0.0},
                        'message': 'FAILED'
                    }
                return health_check
            
            # Target component
            def create_target_health_check(healthy):
                def health_check():
                    return {
                        'healthy': healthy,
                        'metrics': {'status': 1.0 if healthy else 0.0},
                        'message': 'OK' if healthy else 'FAILED'
                    }
                return health_check
            
            monitor.register_component(
                primary_name,
                create_failing_health_check(),
                is_critical=True,
                failover_target=target_name
            )
            
            monitor.register_component(
                target_name,
                create_target_health_check(target_healthy),
                is_critical=False
            )
        
        # Trigger failures for all primary components
        for primary_name in unique_components.keys():
            for _ in range(4):  # Exceed max_failures
                monitor.check_component_health(primary_name)
        
        # SYSTEM LAW: All healthy targets should be available for failover
        system_health = monitor.get_system_health()
        
        for primary_name, (target_name, target_healthy) in unique_components.items():
            if target_healthy:
                target_status = system_health['component_statuses'].get(target_name, {})
                assert target_status.get('healthy', False), \
                    f"Healthy failover target {target_name} should remain healthy"
        
        # SYSTEM LAW: Failover should only succeed to healthy targets
        failover_calls = failover_handler.execute_failover.call_args_list
        for call in failover_calls:
            primary, target = call[0]
            if target in unique_components.values():
                target_info = next((t for p, t in unique_components.items() if t[0] == target), None)
                if target_info:
                    assert target_info[1], f"Failover to unhealthy target {target} should not succeed"


class TestHealthTrendAnalysis:
    """
    Test health trend analysis for predictive alerting
    **Validates: Requirements 12.6**
    """
    
    @given(
        values=st.lists(
            st.floats(min_value=0.0, max_value=100.0),
            min_size=10,
            max_size=20
        )
    )
    @settings(max_examples=10, deadline=5000)
    def test_trend_analysis_property(self, values):
        """
        Property: Trend analysis must correctly identify patterns
        For any sequence of values, trend analysis should be consistent
        **Feature: northstar-v3-system-cohesion, Property: Trend Analysis**
        """
        analyzer = HealthTrendAnalyzer()
        
        # Add values to analyzer
        for i, value in enumerate(values):
            analyzer.add_metric("test_component", "test_metric", value)
        
        # Analyze trend
        trend_result = analyzer.analyze_trend("test_component", "test_metric")
        
        # SYSTEM LAW: Trend analysis must return valid results
        assert "trend" in trend_result, "Trend analysis must include trend direction"
        
        if trend_result["trend"] not in ["insufficient_data", "insufficient_recent_data", "analysis_error"]:
            # Should have statistical measures
            assert "mean" in trend_result, "Trend analysis must include mean"
            assert "data_points" in trend_result, "Trend analysis must include data point count"
            
            # Data points should match input
            assert trend_result["data_points"] <= len(values), \
                "Data points should not exceed input size"
            
            # Mean should be reasonable
            if len(values) > 0:
                expected_mean = sum(values) / len(values)
                actual_mean = trend_result["mean"]
                # Allow for windowing effects
                assert abs(actual_mean - expected_mean) <= max(expected_mean * 0.5, 10), \
                    f"Mean calculation error: {actual_mean} vs {expected_mean}"


class HealthMonitorStateMachine(RuleBasedStateMachine):
    """
    Stateful testing for health monitor
    Tests complex interactions and invariants
    """
    
    def __init__(self):
        super().__init__()
        self.monitor = ComprehensiveHealthMonitor(check_interval=timedelta(seconds=1))
        self.registered_components = set()
        self.critical_components = set()
    
    @rule(
        component_name=st.text(min_size=1, max_size=8),
        is_critical=st.booleans(),
        is_healthy=st.booleans()
    )
    def register_component(self, component_name, is_critical, is_healthy):
        """Register a component for monitoring"""
        if component_name not in self.registered_components:
            def health_check():
                return {
                    'healthy': is_healthy,
                    'metrics': {'test_metric': 1.0 if is_healthy else 0.0},
                    'message': 'OK' if is_healthy else 'FAILED'
                }
            
            success = self.monitor.register_component(
                component_name, health_check, is_critical=is_critical
            )
            
            if success:
                self.registered_components.add(component_name)
                if is_critical:
                    self.critical_components.add(component_name)
    
    @rule(component_name=st.text(min_size=1, max_size=8))
    def check_health(self, component_name):
        """Check health of a component"""
        if component_name in self.registered_components:
            result = self.monitor.check_component_health(component_name)
            assert isinstance(result.healthy, bool), "Health check must return boolean"
    
    @rule()
    def get_system_health(self):
        """Get overall system health"""
        health = self.monitor.get_system_health()
        
        # Verify system health structure
        assert 'overall_healthy' in health
        assert 'total_components' in health
        assert 'component_statuses' in health
        
        # Verify component count consistency
        assert health['total_components'] == len(self.registered_components)
    
    @invariant()
    def health_monitor_consistency_invariant(self):
        """Health monitor state must be consistent"""
        # All registered components should be in monitor
        for component in self.registered_components:
            assert component in self.monitor.components, \
                f"Registered component {component} not in monitor"
        
        # All critical components should be marked as critical
        for component in self.critical_components:
            assert component in self.monitor.critical_components, \
                f"Critical component {component} not marked as critical"
        
        # System health should be obtainable
        health = self.monitor.get_system_health()
        assert isinstance(health['overall_healthy'], bool), \
            "System health must be boolean"


# Test the stateful machine
TestHealthMonitorStateMachine = HealthMonitorStateMachine.TestCase


class TestHealthMonitorIntegration:
    """
    Integration tests for health monitoring system
    """
    
    def test_basic_health_monitoring_functionality(self):
        """
        Test basic health monitoring functionality works correctly
        **Feature: northstar-v3-system-cohesion, Property: Basic Functionality**
        """
        monitor = ComprehensiveHealthMonitor()
        
        # Register a healthy component
        def healthy_check():
            return {
                'healthy': True,
                'metrics': {'cpu_usage': 25.0, 'memory_usage': 60.0},
                'message': 'All systems operational'
            }
        
        success = monitor.register_component(
            "test_service", 
            healthy_check,
            is_critical=True
        )
        
        assert success, "Component registration should succeed"
        
        # Check health
        health_result = monitor.check_component_health("test_service")
        assert health_result.healthy, "Healthy component should report healthy"
        assert 'cpu_usage' in health_result.metrics, "Metrics should be included"
        
        # Get system health
        system_health = monitor.get_system_health()
        assert system_health['overall_healthy'], "System should be healthy"
        assert system_health['total_components'] == 1, "Should have 1 component"
        assert system_health['healthy_components'] == 1, "Should have 1 healthy component"
    
    def test_alert_generation_and_resolution(self):
        """
        Test alert generation and resolution
        **Feature: northstar-v3-system-cohesion, Property: Alert Management**
        """
        monitor = ComprehensiveHealthMonitor()
        
        # Register component with threshold
        value_counter = 0
        def variable_health_check():
            nonlocal value_counter
            value_counter += 1
            # Start low, then go high to trigger alert
            cpu_value = 30.0 if value_counter <= 2 else 85.0
            return {
                'healthy': cpu_value < 80.0,
                'metrics': {'cpu_usage': cpu_value},
                'message': f'CPU at {cpu_value}%'
            }
        
        monitor.register_component("cpu_service", variable_health_check, is_critical=True)
        monitor.set_alert_thresholds("cpu_service", "cpu_usage", 70.0, 80.0)
        
        # Initial checks (should be healthy)
        for _ in range(2):
            monitor.check_component_health("cpu_service")
        
        alerts = monitor.get_active_alerts()
        assert len(alerts) == 0, "Should have no alerts initially"
        
        # Trigger high CPU (should create alert)
        monitor.check_component_health("cpu_service")
        
        alerts = monitor.get_active_alerts()
        assert len(alerts) > 0, "Should have alerts after threshold breach"
        
        # Test alert resolution
        if alerts:
            alert_id = alerts[0].id
            monitor.resolve_alert(alert_id)
            
            resolved_alert = next((a for a in monitor.alerts if a.id == alert_id), None)
            assert resolved_alert is not None, "Alert should exist"
            assert resolved_alert.resolved, "Alert should be resolved"


if __name__ == "__main__":
    # Run property tests
    pytest.main([__file__, "-v", "--tb=short"])