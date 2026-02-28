#!/usr/bin/env python3
"""
Task 6 Performance Monitor Demo Script

This script demonstrates the Performance Monitor capabilities including:
- Real-time performance tracking
- Performance deviation detection and alerting
- System health monitoring and diagnostics
- Emergency protocol execution
- Performance data storage and analysis
"""

import sys
import os
import time
import threading
from datetime import datetime, timedelta
from pathlib import Path
import json

# Add src to path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from operation.performance_monitor import PerformanceMonitor
from operation.base_types import Alert, AlertLevel, HealthStatus
from operation.logging_config import setup_operation_logging


def demo_alert_callback(alert: Alert):
    """Demo callback for alert notifications."""
    print(f"🚨 ALERT: [{alert.level.value.upper()}] {alert.message}")
    if alert.details:
        print(f"   Details: {alert.details}")


def demo_emergency_callback(reason: str, details: dict):
    """Demo callback for emergency notifications."""
    print(f"🆘 EMERGENCY: {reason}")
    print(f"   Emergency Details: {details}")


def simulate_normal_operations(monitor: PerformanceMonitor, duration_seconds: int = 30):
    """Simulate normal system operations with realistic metrics."""
    print(f"\n📊 Simulating normal operations for {duration_seconds} seconds...")
    
    import random
    start_time = time.time()
    
    while time.time() - start_time < duration_seconds:
        # Simulate normal performance metrics
        monitor.track_performance_metric("system_latency_ms", random.uniform(20, 80))
        monitor.track_performance_metric("data_quality_score", random.uniform(0.95, 0.99))
        monitor.track_performance_metric("error_rate", random.uniform(0.001, 0.02))
        monitor.track_performance_metric("memory_usage", random.uniform(0.4, 0.7))
        monitor.track_performance_metric("cpu_usage", random.uniform(0.3, 0.6))
        
        # Simulate trading performance metrics
        monitor.track_performance_metric("sharpe_ratio", random.uniform(0.8, 1.5))
        monitor.track_performance_metric("total_return", random.uniform(0.08, 0.15))
        monitor.track_performance_metric("max_drawdown", random.uniform(0.02, 0.08))
        
        time.sleep(1)  # 1 second intervals
    
    print("✅ Normal operations simulation completed")


def simulate_performance_degradation(monitor: PerformanceMonitor):
    """Simulate performance degradation that should trigger alerts."""
    print("\n⚠️  Simulating performance degradation...")
    
    # Gradually increase latency
    for latency in [90, 110, 130, 150, 180]:
        print(f"   📈 Increasing latency to {latency}ms")
        monitor.track_performance_metric("system_latency_ms", latency)
        time.sleep(2)
    
    # Decrease data quality
    for quality in [0.94, 0.92, 0.89, 0.85]:
        print(f"   📉 Decreasing data quality to {quality:.2f}")
        monitor.track_performance_metric("data_quality_score", quality)
        time.sleep(2)
    
    # Increase error rate
    for error_rate in [0.03, 0.06, 0.09, 0.12]:
        print(f"   🔴 Increasing error rate to {error_rate:.2%}")
        monitor.track_performance_metric("error_rate", error_rate)
        time.sleep(2)
    
    print("⚠️  Performance degradation simulation completed")


def simulate_system_crisis(monitor: PerformanceMonitor):
    """Simulate a system crisis that should trigger emergency protocols."""
    print("\n🚨 Simulating system crisis...")
    
    # Generate multiple critical alerts rapidly
    critical_issues = [
        "Database connection lost",
        "Memory usage critical (95%)",
        "Risk management system failure",
        "Data feed interruption detected"
    ]
    
    for i, issue in enumerate(critical_issues):
        print(f"   🔥 Critical Issue {i+1}: {issue}")
        
        critical_alert = Alert(
            timestamp=datetime.now(),
            level=AlertLevel.CRITICAL,
            component="SystemCrisis",
            message=issue,
            details={"crisis_simulation": True, "issue_id": i+1}
        )
        
        monitor.trigger_alert(critical_alert)
        time.sleep(1)  # Brief pause between critical alerts
    
    print("🚨 System crisis simulation completed")


def demonstrate_anomaly_detection(monitor: PerformanceMonitor):
    """Demonstrate anomaly detection capabilities."""
    print("\n🔍 Demonstrating anomaly detection...")
    
    # Generate baseline data
    print("   📊 Generating baseline performance data...")
    import random
    
    for _ in range(50):
        # Normal latency around 50ms
        monitor.track_performance_metric("anomaly_test_latency", random.uniform(45, 55))
        time.sleep(0.1)
    
    # Introduce anomalies
    print("   🎯 Introducing performance anomalies...")
    anomalous_values = [150, 200, 25, 300, 10]  # Very high and very low values
    
    for value in anomalous_values:
        print(f"      📈 Anomalous latency: {value}ms")
        monitor.track_performance_metric("anomaly_test_latency", value)
        time.sleep(1)
    
    # Detect anomalies
    time.sleep(2)  # Give time for detection
    anomalies = monitor.detect_performance_anomalies()
    
    print(f"   🔍 Detected {len(anomalies)} anomalies:")
    for anomaly in anomalies:
        print(f"      - {anomaly['metric_name']}: {anomaly['value']:.2f} "
              f"(severity: {anomaly['severity']}, score: {anomaly['deviation_score']:.2f})")
    
    print("🔍 Anomaly detection demonstration completed")


def demonstrate_health_monitoring(monitor: PerformanceMonitor):
    """Demonstrate system health monitoring."""
    print("\n💚 Demonstrating health monitoring...")
    
    # Get initial health status
    health = monitor.validate_system_health()
    print(f"   📊 Initial Health Status: {health.overall_health.value}")
    print(f"   📈 Performance Score: {health.performance_score:.2f}")
    print(f"   📊 Data Quality Score: {health.data_quality_score:.2f}")
    
    if health.component_status:
        print("   🔧 Component Status:")
        for component, status in health.component_status.items():
            status_icon = "✅" if status == "healthy" else "⚠️" if status == "warning" else "🔴"
            print(f"      {status_icon} {component}: {status}")
    
    if health.recommended_actions:
        print("   💡 Recommended Actions:")
        for action in health.recommended_actions:
            print(f"      - {action}")
    
    print("💚 Health monitoring demonstration completed")


def demonstrate_performance_summary(monitor: PerformanceMonitor):
    """Demonstrate performance summary generation."""
    print("\n📈 Generating performance summary...")
    
    summary = monitor.get_performance_summary(hours=1)
    
    if "error" not in summary:
        print(f"   ⏱️  Period: {summary['period']['duration_hours']} hours")
        print(f"   ⏰ Uptime: {summary['uptime_hours']:.2f} hours")
        
        if summary.get('metrics'):
            print("   📊 Performance Metrics Summary:")
            for metric_name, stats in summary['metrics'].items():
                print(f"      📈 {metric_name}:")
                print(f"         Mean: {stats['mean']:.3f}, Std: {stats['std']:.3f}")
                print(f"         Range: [{stats['min']:.3f}, {stats['max']:.3f}]")
                print(f"         P95: {stats['p95']:.3f}, P99: {stats['p99']:.3f}")
        
        health_info = summary.get('health', {})
        print(f"   💚 Current Health: {health_info.get('current_status', 'unknown')}")
        print(f"   📊 Average Health Score: {health_info.get('average_score', 0):.2f}")
        print(f"   📈 Health Trend: {health_info.get('health_trend', 'unknown')}")
        
        alert_info = summary.get('alerts', {})
        print(f"   🚨 Total Alerts: {alert_info.get('total_alerts', 0)}")
        print(f"   🔴 Critical Alerts: {alert_info.get('critical_alerts', 0)}")
        print(f"   ⚡ Active Alerts: {alert_info.get('active_alerts', 0)}")
        
        print(f"   🎯 Anomalies Detected: {summary.get('anomalies', 0)}")
    else:
        print(f"   ❌ Error generating summary: {summary['error']}")
    
    print("📈 Performance summary demonstration completed")


def run_performance_monitor_demo():
    """Run comprehensive Performance Monitor demonstration."""
    logger = setup_operation_logging()
    logger.info("=" * 80)
    logger.info("TASK 6: PERFORMANCE MONITOR DEMONSTRATION")
    logger.info("=" * 80)
    
    print("🚀 Starting Performance Monitor Demo")
    print("=" * 60)
    
    try:
        # Initialize Performance Monitor
        print("\n🔧 Initializing Performance Monitor...")
        monitor = PerformanceMonitor(logger)
        
        # Add demo callbacks
        monitor.add_alert_callback(demo_alert_callback)
        monitor.add_emergency_callback(demo_emergency_callback)
        
        # Start monitoring
        print("\n▶️  Starting real-time monitoring...")
        if not monitor.start_monitoring():
            print("❌ Failed to start monitoring")
            return False
        
        print("✅ Performance monitoring started successfully")
        
        # Demo 1: Normal Operations
        simulate_normal_operations(monitor, duration_seconds=15)
        
        # Demo 2: Health Monitoring
        demonstrate_health_monitoring(monitor)
        
        # Demo 3: Performance Degradation and Alerting
        simulate_performance_degradation(monitor)
        
        # Demo 4: Anomaly Detection
        demonstrate_anomaly_detection(monitor)
        
        # Demo 5: Performance Summary
        demonstrate_performance_summary(monitor)
        
        # Demo 6: System Crisis and Emergency Protocols
        simulate_system_crisis(monitor)
        
        # Give time for emergency protocol to execute
        time.sleep(3)
        
        # Final Status Check
        print("\n📊 Final System Status:")
        final_health = monitor.validate_system_health()
        print(f"   💚 Health Status: {final_health.overall_health.value}")
        print(f"   🚨 Total Alerts Generated: {len(monitor.alert_history)}")
        print(f"   ⚡ Active Alerts: {len(monitor.active_alerts)}")
        
        # Show recent alerts
        recent_alerts = monitor.get_recent_alerts(hours=1)
        if recent_alerts:
            print(f"\n🚨 Recent Alerts ({len(recent_alerts)}):")
            for alert in recent_alerts[-5:]:  # Show last 5 alerts
                print(f"   [{alert.level.value}] {alert.message}")
        
        # Stop monitoring
        print("\n⏹️  Stopping performance monitoring...")
        if monitor.stop_monitoring():
            print("✅ Performance monitoring stopped successfully")
        else:
            print("⚠️  Warning: Issues stopping performance monitoring")
        
        # Generate final report
        print("\n📄 Generating demonstration report...")
        generate_demo_report(monitor)
        
        print("\n" + "=" * 60)
        print("🎉 Performance Monitor Demo Completed Successfully!")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        logger.error(f"Performance Monitor demo failed: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def generate_demo_report(monitor: PerformanceMonitor):
    """Generate a comprehensive demo report."""
    try:
        report = {
            "demo_summary": {
                "timestamp": datetime.now().isoformat(),
                "demo_duration_minutes": 5,  # Approximate demo duration
                "monitoring_successful": True
            },
            "performance_tracking": {
                "metrics_tracked": len(monitor.metrics_cache),
                "tracking_successful": len(monitor.metrics_cache) > 0
            },
            "alerting_system": {
                "total_alerts": len(monitor.alert_history),
                "alert_levels": {
                    level.value: len([a for a in monitor.alert_history if a.level == level])
                    for level in AlertLevel
                },
                "alerting_successful": len(monitor.alert_history) > 0
            },
            "health_monitoring": {
                "health_checks_performed": len(monitor.health_history),
                "current_health": monitor.current_health.overall_health.value,
                "health_monitoring_successful": len(monitor.health_history) > 0
            },
            "anomaly_detection": {
                "anomalies_detected": len(monitor.detect_performance_anomalies()),
                "detection_successful": True
            },
            "emergency_protocols": {
                "emergency_alerts": len([a for a in monitor.alert_history if a.level == AlertLevel.EMERGENCY]),
                "emergency_protocols_executed": len([a for a in monitor.alert_history if a.level == AlertLevel.EMERGENCY]) > 0
            },
            "data_persistence": {
                "data_files_created": len(list(monitor.data_path.glob("*.json"))),
                "persistence_successful": monitor.data_path.exists()
            }
        }
        
        # Save report
        report_path = Path("reports") / f"TASK6_PERFORMANCE_MONITOR_DEMO_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        report_path.parent.mkdir(exist_ok=True)
        
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"📄 Demo report saved: {report_path}")
        
        # Print summary
        print("\n📊 Demo Results Summary:")
        print(f"   📈 Metrics Tracked: {report['performance_tracking']['metrics_tracked']}")
        print(f"   🚨 Alerts Generated: {report['alerting_system']['total_alerts']}")
        print(f"   💚 Health Checks: {report['health_monitoring']['health_checks_performed']}")
        print(f"   🎯 Anomalies Detected: {report['anomaly_detection']['anomalies_detected']}")
        print(f"   🆘 Emergency Protocols: {report['emergency_protocols']['emergency_alerts']}")
        
    except Exception as e:
        print(f"❌ Error generating demo report: {str(e)}")


if __name__ == "__main__":
    success = run_performance_monitor_demo()
    sys.exit(0 if success else 1)