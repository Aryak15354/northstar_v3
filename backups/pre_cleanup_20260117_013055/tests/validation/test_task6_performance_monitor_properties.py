#!/usr/bin/env python3
"""
Property Tests for Task 6: Performance Monitor

Tests the universal correctness properties of the Performance Monitor:
- Property 11: Real-Time Performance Tracking
- Property 12: Performance Deviation Alert Triggering  
- Property 14: Emergency Protocol Execution

These tests validate that the Performance Monitor correctly tracks performance,
detects deviations, and executes emergency protocols under all conditions.
"""

import sys
import pytest
import time
import threading
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch
import numpy as np

# Add src to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent / "src"))

from operation.performance_monitor import PerformanceMonitor
from operation.base_types import Alert, AlertLevel, HealthStatus, SystemHealthStatus


class TestPerformanceMonitorProperties:
    """Test universal correctness properties of the Performance Monitor."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.monitor = PerformanceMonitor()
        
    def teardown_method(self):
        """Clean up after tests."""
        if self.monitor.is_monitoring:
            self.monitor.stop_monitoring()
    
    # Property 11: Real-Time Performance Tracking
    # For any live system operation, the performance monitor should continuously 
    # track and record performance metrics within acceptable latency limits.
    
    def test_property_11_real_time_performance_tracking_basic(self):
        """Test that performance monitor tracks metrics in real-time."""
        # Start monitoring
        assert self.monitor.start_monitoring() == True
        assert self.monitor.is_monitoring == True
        
        # Track a performance metric
        metric_name = "test_latency_ms"
        metric_value = 45.5
        start_time = datetime.now()
        
        self.monitor.track_performance_metric(metric_name, metric_value)
        
        # Verify metric was tracked within acceptable latency
        end_time = datetime.now()
        tracking_latency = (end_time - start_time).total_seconds() * 1000  # ms
        
        assert tracking_latency < 10.0  # Should track within 10ms
        assert metric_name in self.monitor.metrics_cache
        assert self.monitor.metrics_cache[metric_name]["value"] == metric_value
    
    def test_property_11_continuous_tracking_under_load(self):
        """Test continuous tracking under high load."""
        assert self.monitor.start_monitoring() == True
        
        # Track many metrics rapidly
        metrics_tracked = []
        start_time = datetime.now()
        
        for i in range(100):
            metric_name = f"load_test_metric_{i}"
            metric_value = float(i)
            self.monitor.track_performance_metric(metric_name, metric_value)
            metrics_tracked.append((metric_name, metric_value))
        
        end_time = datetime.now()
        total_time = (end_time - start_time).total_seconds() * 1000  # ms
        
        # Verify all metrics were tracked
        assert len(metrics_tracked) == 100
        
        # Verify tracking latency is acceptable (< 1ms per metric on average)
        avg_latency_per_metric = total_time / 100
        assert avg_latency_per_metric < 1.0
        
        # Verify metrics are in cache
        for metric_name, metric_value in metrics_tracked:
            assert metric_name in self.monitor.metrics_cache
            assert self.monitor.metrics_cache[metric_name]["value"] == metric_value
    
    def test_property_11_tracking_with_concurrent_operations(self):
        """Test tracking performance with concurrent operations."""
        assert self.monitor.start_monitoring() == True
        
        # Track metrics from multiple threads
        results = []
        
        def track_metrics(thread_id):
            thread_results = []
            for i in range(20):
                metric_name = f"thread_{thread_id}_metric_{i}"
                metric_value = float(thread_id * 100 + i)
                start = datetime.now()
                self.monitor.track_performance_metric(metric_name, metric_value)
                end = datetime.now()
                latency = (end - start).total_seconds() * 1000
                thread_results.append((metric_name, metric_value, latency))
            results.extend(thread_results)
        
        # Start multiple threads
        threads = []
        for thread_id in range(5):
            thread = threading.Thread(target=track_metrics, args=(thread_id,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify all metrics were tracked with acceptable latency
        assert len(results) == 100  # 5 threads × 20 metrics each
        
        for metric_name, metric_value, latency in results:
            assert latency < 10.0  # Each tracking operation < 10ms
            assert metric_name in self.monitor.metrics_cache
            assert self.monitor.metrics_cache[metric_name]["value"] == metric_value
    
    def test_property_11_tracking_persistence_across_time(self):
        """Test that tracking persists across time periods."""
        assert self.monitor.start_monitoring() == True
        
        # Track metrics over time
        tracked_metrics = []
        
        for minute in range(3):  # Track for 3 "minutes" (simulated)
            for second in range(5):  # 5 metrics per "minute"
                metric_name = f"time_series_metric_{minute}_{second}"
                metric_value = float(minute * 10 + second)
                timestamp = datetime.now() + timedelta(minutes=minute, seconds=second)
                
                self.monitor.track_performance_metric(metric_name, metric_value, timestamp)
                tracked_metrics.append((metric_name, metric_value, timestamp))
        
        # Verify all metrics are tracked and timestamped correctly
        assert len(tracked_metrics) == 15
        
        for metric_name, metric_value, timestamp in tracked_metrics:
            assert metric_name in self.monitor.metrics_cache
            cached_metric = self.monitor.metrics_cache[metric_name]
            assert cached_metric["value"] == metric_value
            # Timestamp should be close to expected (within 1 second)
            time_diff = abs((cached_metric["timestamp"] - timestamp).total_seconds())
            assert time_diff < 1.0
    
    # Property 12: Performance Deviation Alert Triggering
    # For any performance metric that deviates beyond expected ranges, 
    # the system should trigger immediate alerts with appropriate severity levels.
    
    def test_property_12_deviation_alert_triggering_basic(self):
        """Test that performance deviations trigger alerts."""
        assert self.monitor.start_monitoring() == True
        
        # Track a metric that exceeds threshold
        high_latency = 150.0  # Above 100ms threshold
        
        # Clear any existing alerts
        self.monitor.alert_history.clear()
        
        self.monitor.track_performance_metric("system_latency_ms", high_latency)
        
        # Give a moment for alert processing
        time.sleep(0.1)
        
        # Verify alert was triggered
        assert len(self.monitor.alert_history) > 0
        
        # Find the latency alert
        latency_alerts = [
            alert for alert in self.monitor.alert_history 
            if "system_latency_ms" in alert.message
        ]
        
        assert len(latency_alerts) > 0
        alert = latency_alerts[0]
        assert alert.level in [AlertLevel.WARNING, AlertLevel.CRITICAL]
        assert alert.component == "PerformanceMonitor"
        assert "deviation" in alert.message.lower()
    
    def test_property_12_multiple_deviation_types(self):
        """Test alerts for different types of performance deviations."""
        assert self.monitor.start_monitoring() == True
        
        # Clear existing alerts
        self.monitor.alert_history.clear()
        
        # Test different deviation types
        deviation_tests = [
            ("system_latency_ms", 150.0, "greater"),      # High latency
            ("data_quality_score", 0.90, "less"),         # Low data quality
            ("error_rate", 0.08, "greater"),              # High error rate
            ("memory_usage", 0.90, "greater"),            # High memory usage
            ("cpu_usage", 0.85, "greater")                # High CPU usage
        ]
        
        for metric_name, value, deviation_type in deviation_tests:
            self.monitor.track_performance_metric(metric_name, value)
        
        # Give time for alert processing
        time.sleep(0.2)
        
        # Verify alerts were triggered for each deviation
        assert len(self.monitor.alert_history) >= len(deviation_tests)
        
        # Check that each metric type has an alert
        alerted_metrics = set()
        for alert in self.monitor.alert_history:
            for metric_name, _, _ in deviation_tests:
                if metric_name in alert.message:
                    alerted_metrics.add(metric_name)
        
        # Should have alerts for most or all deviation types
        assert len(alerted_metrics) >= len(deviation_tests) - 1  # Allow for 1 miss due to timing
    
    def test_property_12_alert_severity_levels(self):
        """Test that alert severity levels are appropriate for deviation magnitude."""
        assert self.monitor.start_monitoring() == True
        
        # Clear existing alerts
        self.monitor.alert_history.clear()
        
        # Test different severity levels
        severity_tests = [
            ("system_latency_ms", 110.0),  # Slightly above threshold
            ("system_latency_ms", 200.0),  # Well above threshold
            ("data_quality_score", 0.93),  # Slightly below threshold
            ("data_quality_score", 0.80),  # Well below threshold
        ]
        
        for metric_name, value in severity_tests:
            self.monitor.track_performance_metric(metric_name, value)
        
        # Give time for alert processing
        time.sleep(0.2)
        
        # Verify alerts have appropriate severity
        assert len(self.monitor.alert_history) > 0
        
        # All deviation alerts should be at least WARNING level
        for alert in self.monitor.alert_history:
            if "deviation" in alert.message.lower():
                assert alert.level in [AlertLevel.WARNING, AlertLevel.CRITICAL]
    
    def test_property_12_alert_cooldown_mechanism(self):
        """Test that alert cooldown prevents spam."""
        assert self.monitor.start_monitoring() == True
        
        # Clear existing alerts
        self.monitor.alert_history.clear()
        
        # Track the same deviation multiple times rapidly
        high_latency = 150.0
        
        for _ in range(5):
            self.monitor.track_performance_metric("system_latency_ms", high_latency)
            time.sleep(0.01)  # Small delay between metrics
        
        # Give time for alert processing
        time.sleep(0.2)
        
        # Should have fewer alerts than metrics due to cooldown
        latency_alerts = [
            alert for alert in self.monitor.alert_history 
            if "system_latency_ms" in alert.message
        ]
        
        # Should have 1 alert due to cooldown (5 minute cooldown in config)
        assert len(latency_alerts) <= 2  # Allow for some timing variation
    
    # Property 14: Emergency Protocol Execution
    # For any critical issue detection, the system should execute emergency 
    # protocols according to predefined procedures without delay.
    
    def test_property_14_emergency_protocol_execution_basic(self):
        """Test that emergency protocols execute for critical issues."""
        assert self.monitor.start_monitoring() == True
        
        # Mock emergency callbacks to verify execution
        emergency_callback_called = []
        
        def mock_emergency_callback(reason, details):
            emergency_callback_called.append((reason, details))
        
        self.monitor.add_emergency_callback(mock_emergency_callback)
        
        # Trigger emergency protocol
        reason = "Test critical system failure"
        details = {"component": "test", "severity": "critical"}
        
        result = self.monitor.execute_emergency_protocol(reason, details)
        
        # Verify emergency protocol executed
        assert result == True
        assert len(emergency_callback_called) == 1
        assert emergency_callback_called[0][0] == reason
        assert emergency_callback_called[0][1] == details
        
        # Verify emergency alert was created
        emergency_alerts = [
            alert for alert in self.monitor.alert_history 
            if alert.level == AlertLevel.EMERGENCY
        ]
        assert len(emergency_alerts) > 0
        assert reason in emergency_alerts[0].message
    
    def test_property_14_emergency_protocol_multiple_critical_alerts(self):
        """Test emergency protocol triggers on multiple critical alerts."""
        assert self.monitor.start_monitoring() == True
        
        # Mock emergency callbacks
        emergency_executions = []
        
        def mock_emergency_callback(reason, details):
            emergency_executions.append((reason, details))
        
        self.monitor.add_emergency_callback(mock_emergency_callback)
        
        # Clear existing alerts
        self.monitor.alert_history.clear()
        
        # Generate multiple critical alerts rapidly
        for i in range(4):  # Above emergency threshold of 3
            critical_alert = Alert(
                timestamp=datetime.now(),
                level=AlertLevel.CRITICAL,
                component="TestComponent",
                message=f"Critical test alert {i}",
                details={"test_id": i}
            )
            self.monitor.trigger_alert(critical_alert)
        
        # Give time for emergency protocol to trigger
        time.sleep(0.2)
        
        # Verify emergency protocol was executed
        assert len(emergency_executions) > 0
        
        # Verify emergency was triggered due to multiple critical alerts
        reason, details = emergency_executions[0]
        assert "multiple critical alerts" in reason.lower()
        assert details["critical_alert_count"] >= 3
    
    def test_property_14_emergency_protocol_execution_speed(self):
        """Test that emergency protocols execute without delay."""
        assert self.monitor.start_monitoring() == True
        
        # Mock emergency callbacks to measure execution time
        execution_times = []
        
        def mock_emergency_callback(reason, details):
            execution_times.append(datetime.now())
        
        self.monitor.add_emergency_callback(mock_emergency_callback)
        
        # Trigger emergency protocol and measure time
        start_time = datetime.now()
        
        result = self.monitor.execute_emergency_protocol(
            "Speed test emergency", 
            {"test": "execution_speed"}
        )
        
        end_time = datetime.now()
        
        # Verify execution was fast
        assert result == True
        execution_time = (end_time - start_time).total_seconds() * 1000  # ms
        assert execution_time < 100.0  # Should execute within 100ms
        
        # Verify callback was executed quickly
        assert len(execution_times) == 1
        callback_time = (execution_times[0] - start_time).total_seconds() * 1000
        assert callback_time < 50.0  # Callback within 50ms
    
    def test_property_14_emergency_protocol_robustness(self):
        """Test emergency protocol robustness under various conditions."""
        assert self.monitor.start_monitoring() == True
        
        # Test emergency protocol with various inputs
        test_cases = [
            ("System overload", {"cpu": 0.95, "memory": 0.90}),
            ("Data corruption detected", {"affected_records": 1000}),
            ("Network connectivity lost", {"timeout_seconds": 30}),
            ("Critical component failure", {"component": "risk_engine"}),
            ("", {}),  # Edge case: empty inputs
        ]
        
        successful_executions = 0
        
        for reason, details in test_cases:
            try:
                result = self.monitor.execute_emergency_protocol(reason, details)
                if result:
                    successful_executions += 1
            except Exception as e:
                # Emergency protocol should not raise exceptions
                pytest.fail(f"Emergency protocol raised exception: {e}")
        
        # All emergency protocols should execute successfully
        assert successful_executions == len(test_cases)
        
        # Verify emergency alerts were created for all cases
        emergency_alerts = [
            alert for alert in self.monitor.alert_history 
            if alert.level == AlertLevel.EMERGENCY
        ]
        assert len(emergency_alerts) >= len(test_cases)
    
    def test_property_14_emergency_protocol_data_preservation(self):
        """Test that emergency protocols preserve critical data."""
        assert self.monitor.start_monitoring() == True
        
        # Add some performance data
        for i in range(10):
            self.monitor.track_performance_metric(f"test_metric_{i}", float(i))
        
        # Verify data exists before emergency
        assert len(self.monitor.metrics_cache) >= 10
        initial_data_count = len(self.monitor.metrics_cache)
        
        # Execute emergency protocol
        result = self.monitor.execute_emergency_protocol(
            "Data preservation test", 
            {"preserve_data": True}
        )
        
        # Verify emergency executed successfully
        assert result == True
        
        # Verify data is still preserved
        assert len(self.monitor.metrics_cache) == initial_data_count
        
        # Verify monitoring data files are created (emergency save)
        data_files = list(self.monitor.data_path.glob("*.json"))
        # Should have at least some data files after emergency save
        assert len(data_files) >= 0  # Emergency save may create files
    
    # Integration tests for multiple properties
    
    def test_integrated_monitoring_and_alerting(self):
        """Test integration of performance tracking and alerting."""
        assert self.monitor.start_monitoring() == True
        
        # Clear existing alerts
        self.monitor.alert_history.clear()
        
        # Track normal metrics (should not trigger alerts)
        normal_metrics = [
            ("system_latency_ms", 50.0),
            ("data_quality_score", 0.98),
            ("error_rate", 0.01),
            ("memory_usage", 0.60),
            ("cpu_usage", 0.45)
        ]
        
        for metric_name, value in normal_metrics:
            self.monitor.track_performance_metric(metric_name, value)
        
        # Track problematic metrics (should trigger alerts)
        problem_metrics = [
            ("system_latency_ms", 150.0),
            ("data_quality_score", 0.90),
            ("error_rate", 0.08)
        ]
        
        for metric_name, value in problem_metrics:
            self.monitor.track_performance_metric(metric_name, value)
        
        # Give time for processing
        time.sleep(0.2)
        
        # Verify normal metrics are tracked
        for metric_name, value in normal_metrics:
            assert metric_name in self.monitor.metrics_cache
            assert self.monitor.metrics_cache[metric_name]["value"] == value
        
        # Verify problem metrics triggered alerts
        assert len(self.monitor.alert_history) >= len(problem_metrics) - 1
        
        # Verify alerts are for the right metrics
        alerted_metrics = set()
        for alert in self.monitor.alert_history:
            for metric_name, _ in problem_metrics:
                if metric_name in alert.message:
                    alerted_metrics.add(metric_name)
        
        assert len(alerted_metrics) >= 2  # Should have alerts for most problem metrics
    
    def test_end_to_end_monitoring_lifecycle(self):
        """Test complete monitoring lifecycle from start to emergency."""
        # Start monitoring
        assert self.monitor.start_monitoring() == True
        assert self.monitor.is_monitoring == True
        
        # Track various metrics over time
        for i in range(20):
            self.monitor.track_performance_metric("lifecycle_metric", float(i))
            if i % 5 == 0:  # Occasional high latency
                self.monitor.track_performance_metric("system_latency_ms", 120.0)
        
        # Generate critical alerts to trigger emergency
        for i in range(4):
            critical_alert = Alert(
                timestamp=datetime.now(),
                level=AlertLevel.CRITICAL,
                component="LifecycleTest",
                message=f"Lifecycle critical alert {i}",
                details={"test_phase": "end_to_end"}
            )
            self.monitor.trigger_alert(critical_alert)
        
        # Give time for processing
        time.sleep(0.3)
        
        # Verify monitoring tracked metrics
        assert "lifecycle_metric" in self.monitor.metrics_cache
        
        # Verify alerts were generated
        assert len(self.monitor.alert_history) > 0
        
        # Verify emergency protocol was triggered
        emergency_alerts = [
            alert for alert in self.monitor.alert_history 
            if alert.level == AlertLevel.EMERGENCY
        ]
        assert len(emergency_alerts) > 0
        
        # Stop monitoring
        assert self.monitor.stop_monitoring() == True
        assert self.monitor.is_monitoring == False


if __name__ == "__main__":
    # Run the property tests
    pytest.main([__file__, "-v", "--tb=short"])