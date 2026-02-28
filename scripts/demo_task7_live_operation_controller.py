#!/usr/bin/env python3
"""
Demo script for Task 7: Live Operation Controller.

This script demonstrates the comprehensive live operation management capabilities
including system validation, market data processing, signal execution, error
handling, and daily reporting.
"""

import sys
import time
import json
import threading
from pathlib import Path
from datetime import datetime, timedelta

# Add src to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from src.operation.live_operation_controller import LiveOperationController
from src.operation.base_types import OperationConfig, AlertLevel


def print_header(title: str):
    """Print a formatted header."""
    print(f"\n{'='*60}")
    print(f"🚀 {title}")
    print(f"{'='*60}")


def print_section(title: str):
    """Print a formatted section header."""
    print(f"\n📊 {title}")
    print("-" * 40)


def print_result(key: str, value, indent: int = 0):
    """Print a formatted key-value result."""
    spaces = "  " * indent
    if isinstance(value, dict):
        print(f"{spaces}{key}:")
        for k, v in value.items():
            print_result(k, v, indent + 1)
    elif isinstance(value, list):
        print(f"{spaces}{key}: [{len(value)} items]")
        if len(value) <= 3:
            for item in value:
                print(f"{spaces}  - {item}")
        else:
            for item in value[:2]:
                print(f"{spaces}  - {item}")
            print(f"{spaces}  ... and {len(value) - 2} more")
    else:
        print(f"{spaces}{key}: {value}")


def demo_system_startup():
    """Demonstrate system startup and component validation."""
    print_section("SYSTEM STARTUP & COMPONENT VALIDATION")
    
    # Create configuration
    config = OperationConfig(
        max_processing_latency_ms=100.0,
        max_execution_latency_ms=500.0,
        monitoring_interval_seconds=2,
        max_position_size=1000,
        restricted_symbols=["RESTRICTED_STOCK", "BANNED_TICKER"],
        allowed_signal_types=["buy", "sell", "hold"]
    )
    
    # Initialize controller
    controller = LiveOperationController(config)
    
    print("🔧 Initializing Live Operation Controller...")
    print(f"   Max Processing Latency: {config.max_processing_latency_ms}ms")
    print(f"   Max Execution Latency: {config.max_execution_latency_ms}ms")
    print(f"   Monitoring Interval: {config.monitoring_interval_seconds}s")
    print(f"   Max Position Size: {config.max_position_size}")
    print(f"   Restricted Symbols: {config.restricted_symbols}")
    
    # Start live operations
    print("\n🚀 Starting live operations...")
    startup_result = controller.start_live_operations()
    
    print_result("Startup Status", startup_result.status.value)
    print_result("Operation Type", startup_result.operation_type)
    print_result("Start Time", startup_result.start_time.strftime("%Y-%m-%d %H:%M:%S"))
    
    if startup_result.validation_results:
        print_result("Component Validation", startup_result.validation_results)
    
    if startup_result.performance_metrics:
        print_result("Startup Metrics", startup_result.performance_metrics)
    
    if startup_result.alerts_generated:
        print(f"\n⚠️  Alerts Generated: {len(startup_result.alerts_generated)}")
        for alert in startup_result.alerts_generated:
            print(f"   - {alert.level.value.upper()}: {alert.message}")
    
    return controller


def demo_market_data_processing(controller: LiveOperationController):
    """Demonstrate market data processing with latency monitoring."""
    print_section("MARKET DATA PROCESSING & LATENCY MONITORING")
    
    # Test various market data scenarios
    market_data_scenarios = [
        {
            "name": "Small Data Packet",
            "data": {"symbol": "AAPL", "price": 150.25, "volume": 1000}
        },
        {
            "name": "Medium Data Packet", 
            "data": {
                "symbol": "GOOGL", "price": 2800.50, "volume": 50000,
                "bid": 2799.75, "ask": 2801.25, "timestamp": datetime.now().isoformat()
            }
        },
        {
            "name": "Large Data Packet",
            "data": {
                "symbol": "MSFT", "price": 350.75, "volume": 100000,
                **{f"field_{i}": f"value_{i}" for i in range(50)}
            }
        },
        {
            "name": "High Frequency Data",
            "data": {"symbol": "TSLA", "price": 800.00, "volume": 5000}
        }
    ]
    
    processing_results = []
    
    for scenario in market_data_scenarios:
        print(f"\n📈 Processing {scenario['name']}...")
        
        # Process multiple times to test latency consistency
        scenario_results = []
        for i in range(5):
            result = controller.process_market_data(scenario["data"])
            scenario_results.append(result)
            time.sleep(0.01)  # Small delay between processing
        
        processing_results.extend(scenario_results)
        
        # Show results for this scenario
        successful_results = [r for r in scenario_results if r["status"] == "processed"]
        if successful_results:
            latencies = [r["latency_ms"] for r in successful_results]
            avg_latency = sum(latencies) / len(latencies)
            max_latency = max(latencies)
            
            print(f"   ✅ Processed: {len(successful_results)}/5 packets")
            print(f"   ⏱️  Average Latency: {avg_latency:.2f}ms")
            print(f"   ⏱️  Max Latency: {max_latency:.2f}ms")
            print(f"   📊 Queue Size: {successful_results[-1]['queue_size']}")
        else:
            print(f"   ❌ Processing failed for all packets")
    
    # Show overall latency statistics
    print(f"\n📊 Overall Latency Statistics:")
    if controller.latency_metrics:
        print(f"   Total Data Points: {len(controller.latency_metrics)}")
        print(f"   Average Latency: {sum(controller.latency_metrics) / len(controller.latency_metrics):.2f}ms")
        print(f"   Min Latency: {min(controller.latency_metrics):.2f}ms")
        print(f"   Max Latency: {max(controller.latency_metrics):.2f}ms")
        
        # Check for high latency alerts
        high_latency_alerts = [
            alert for alert in controller.alerts_generated
            if "latency" in alert.message.lower()
        ]
        if high_latency_alerts:
            print(f"   ⚠️  High Latency Alerts: {len(high_latency_alerts)}")
    
    return processing_results


def demo_signal_execution(controller: LiveOperationController):
    """Demonstrate risk-compliant signal execution."""
    print_section("RISK-COMPLIANT SIGNAL EXECUTION")
    
    # Test various signal scenarios
    signal_scenarios = [
        {
            "name": "Valid Buy Signal",
            "signal": {"signal_id": "BUY001", "symbol": "AAPL", "quantity": 100, "type": "buy", "target_price": 150.0},
            "expected": "executed"
        },
        {
            "name": "Valid Sell Signal",
            "signal": {"signal_id": "SELL001", "symbol": "GOOGL", "quantity": 50, "type": "sell", "target_price": 2800.0},
            "expected": "executed"
        },
        {
            "name": "Hold Signal",
            "signal": {"signal_id": "HOLD001", "symbol": "MSFT", "quantity": 0, "type": "hold"},
            "expected": "executed"
        },
        {
            "name": "Oversized Position",
            "signal": {"signal_id": "BIG001", "symbol": "TSLA", "quantity": 50000, "type": "buy"},
            "expected": "rejected"
        },
        {
            "name": "Restricted Symbol",
            "signal": {"signal_id": "REST001", "symbol": "RESTRICTED_STOCK", "quantity": 100, "type": "buy"},
            "expected": "rejected"
        },
        {
            "name": "Invalid Signal Type",
            "signal": {"signal_id": "INV001", "symbol": "NVDA", "quantity": 100, "type": "invalid_type"},
            "expected": "rejected"
        }
    ]
    
    execution_results = []
    
    for scenario in signal_scenarios:
        print(f"\n📋 Executing {scenario['name']}...")
        
        signal = scenario["signal"]
        expected = scenario["expected"]
        
        # Execute signal
        result = controller.execute_signal(signal)
        execution_results.append(result)
        
        # Show execution results
        print(f"   Signal ID: {result.signal_id}")
        print(f"   Status: {result.status}")
        print(f"   Risk Compliance: {result.risk_compliance}")
        print(f"   Execution Latency: {result.execution_latency_ms:.2f}ms")
        
        if result.status == "executed":
            print(f"   ✅ Executed at ${result.execution_price:.2f}")
            print(f"   📊 Quantity: {result.executed_quantity}")
        elif result.status == "rejected":
            print(f"   ❌ Rejected: {result.rejection_reason}")
        elif result.status == "error":
            print(f"   💥 Error: {result.error_message}")
        
        # Verify expected outcome
        if result.status == expected:
            print(f"   ✅ Expected outcome achieved")
        else:
            print(f"   ⚠️  Unexpected outcome: expected {expected}, got {result.status}")
    
    # Show execution summary
    print(f"\n📊 Execution Summary:")
    executed_count = len([r for r in execution_results if r.status == "executed"])
    rejected_count = len([r for r in execution_results if r.status == "rejected"])
    error_count = len([r for r in execution_results if r.status == "error"])
    
    print(f"   Total Signals: {len(execution_results)}")
    print(f"   Executed: {executed_count}")
    print(f"   Rejected: {rejected_count}")
    print(f"   Errors: {error_count}")
    
    # Check for execution latency alerts
    execution_alerts = [
        alert for alert in controller.alerts_generated
        if "execution latency" in alert.message.lower()
    ]
    if execution_alerts:
        print(f"   ⚠️  Execution Latency Alerts: {len(execution_alerts)}")
    
    return execution_results


def demo_error_handling(controller: LiveOperationController):
    """Demonstrate graceful error handling and recovery."""
    print_section("GRACEFUL ERROR HANDLING & RECOVERY")
    
    initial_error_count = controller.error_count
    initial_recovery_attempts = controller.recovery_attempts
    
    # Simulate various error scenarios
    error_scenarios = [
        {"component": "market_data_processing", "error": "Connection timeout to data feed"},
        {"component": "signal_execution", "error": "Execution service temporarily unavailable"},
        {"component": "risk_management", "error": "Risk calculation service error"},
        {"component": "portfolio_management", "error": "Position update failed"},
        {"component": "monitoring", "error": "Health check service unreachable"}
    ]
    
    print("🔥 Simulating error scenarios...")
    
    for i, scenario in enumerate(error_scenarios):
        component = scenario["component"]
        error_message = scenario["error"]
        
        print(f"\n💥 Error {i+1}: {component}")
        print(f"   Message: {error_message}")
        
        # Simulate error
        controller._handle_error(component, error_message)
        
        print(f"   Error Count: {controller.error_count}")
        print(f"   Recovery Attempts: {controller.recovery_attempts}")
        
        # Check if system is still operational
        status = controller.get_operation_status()
        print(f"   System Status: {status['operation_status']}")
        
        # Small delay between errors
        time.sleep(0.1)
    
    # Generate additional errors to trigger recovery
    print(f"\n🔄 Generating additional errors to trigger recovery...")
    for i in range(3):
        controller._handle_error("stress_test", f"Stress test error {i+1}")
    
    # Show error handling results
    print(f"\n📊 Error Handling Results:")
    print(f"   Initial Error Count: {initial_error_count}")
    print(f"   Final Error Count: {controller.error_count}")
    print(f"   Errors Added: {controller.error_count - initial_error_count}")
    print(f"   Recovery Attempts: {controller.recovery_attempts - initial_recovery_attempts}")
    
    # Show recent errors
    recent_errors = controller.error_log[-5:] if controller.error_log else []
    if recent_errors:
        print(f"\n📝 Recent Errors (last 5):")
        for error in recent_errors:
            print(f"   - {error['timestamp']}: {error['component']} - {error['error']}")
    
    # Show error-related alerts
    error_alerts = [
        alert for alert in controller.alerts_generated
        if alert.level in [AlertLevel.WARNING, AlertLevel.CRITICAL]
    ]
    if error_alerts:
        print(f"\n⚠️  Error Alerts Generated: {len(error_alerts)}")
        for alert in error_alerts[-3:]:  # Show last 3
            print(f"   - {alert.level.value.upper()}: {alert.message}")
    
    # Verify system is still operational
    final_status = controller.get_operation_status()
    print(f"\n✅ System Operational Status: {final_status['operation_status']}")
    
    return controller.error_count - initial_error_count


def demo_system_health_monitoring(controller: LiveOperationController):
    """Demonstrate system health monitoring."""
    print_section("SYSTEM HEALTH MONITORING")
    
    print("🏥 Monitoring system health...")
    
    # Get multiple health readings
    health_readings = []
    for i in range(5):
        health = controller.get_system_health()
        health_readings.append(health)
        print(f"\n📊 Health Check {i+1}:")
        print(f"   Timestamp: {health.timestamp.strftime('%H:%M:%S')}")
        print(f"   Overall Health: {health.overall_health.value}")
        print(f"   Performance Score: {health.performance_score:.3f}")
        print(f"   Data Quality Score: {health.data_quality_score:.3f}")
        
        if health.latency_metrics:
            print(f"   Avg Latency: {health.latency_metrics.get('avg_latency_ms', 0):.2f}ms")
            print(f"   Max Latency: {health.latency_metrics.get('max_latency_ms', 0):.2f}ms")
        
        if health.error_counts:
            print(f"   Total Errors: {health.error_counts.get('total_errors', 0)}")
            print(f"   Recent Errors: {health.error_counts.get('recent_errors', 0)}")
        
        time.sleep(0.5)
    
    # Show component status
    if controller.component_status:
        print(f"\n🔧 Component Status:")
        for component, status in controller.component_status.items():
            status_icon = "✅" if status else "❌"
            print(f"   {status_icon} {component}: {'Healthy' if status else 'Failed'}")
    
    # Show health trend
    if len(health_readings) > 1:
        print(f"\n📈 Health Trend:")
        first_score = health_readings[0].performance_score
        last_score = health_readings[-1].performance_score
        trend = "improving" if last_score > first_score else "declining" if last_score < first_score else "stable"
        print(f"   Performance Score Trend: {trend}")
        print(f"   Initial Score: {first_score:.3f}")
        print(f"   Final Score: {last_score:.3f}")
    
    return health_readings


def demo_daily_reporting(controller: LiveOperationController):
    """Demonstrate daily report generation."""
    print_section("DAILY REPORT GENERATION")
    
    print("📋 Generating comprehensive daily report...")
    
    # Generate daily report
    report_path = controller.generate_daily_report()
    
    print(f"✅ Daily report generated: {report_path}")
    
    # Load and display report summary
    try:
        with open(report_path, 'r') as f:
            report_data = json.load(f)
        
        print(f"\n📊 Report Summary:")
        print_result("Report Date", report_data.get("report_date"))
        
        if "operation_summary" in report_data:
            print_result("Operation Summary", report_data["operation_summary"])
        
        if "performance_metrics" in report_data:
            print_result("Performance Metrics", report_data["performance_metrics"])
        
        if "alerts_summary" in report_data:
            print_result("Alerts Summary", report_data["alerts_summary"])
        
        if "recommendations" in report_data:
            print(f"\n💡 Recommendations:")
            for rec in report_data["recommendations"]:
                print(f"   - {rec}")
        
    except Exception as e:
        print(f"❌ Error reading report: {str(e)}")
    
    return report_path


def demo_system_shutdown(controller: LiveOperationController):
    """Demonstrate graceful system shutdown."""
    print_section("GRACEFUL SYSTEM SHUTDOWN")
    
    print("🛑 Stopping live operations...")
    
    # Get final status before shutdown
    final_status = controller.get_operation_status()
    print(f"Pre-shutdown Status: {final_status['operation_status']}")
    print(f"Uptime: {final_status['uptime_seconds']:.1f} seconds")
    
    # Stop live operations
    shutdown_result = controller.stop_live_operations()
    
    print_result("Shutdown Status", shutdown_result.status.value)
    print_result("Shutdown Time", shutdown_result.end_time.strftime("%Y-%m-%d %H:%M:%S"))
    
    if shutdown_result.performance_metrics:
        print_result("Shutdown Metrics", shutdown_result.performance_metrics)
    
    if shutdown_result.report_path:
        print(f"📋 Final Report: {shutdown_result.report_path}")
    
    # Verify final status
    post_shutdown_status = controller.get_operation_status()
    print(f"\nPost-shutdown Status: {post_shutdown_status['operation_status']}")
    
    return shutdown_result


def main():
    """Run the complete Live Operation Controller demonstration."""
    print_header("NORTHSTAR V3 LIVE OPERATION CONTROLLER DEMO")
    
    print("This demonstration showcases the comprehensive live operation management")
    print("capabilities including system validation, market data processing, signal")
    print("execution, error handling, health monitoring, and daily reporting.")
    
    try:
        # 1. System Startup
        controller = demo_system_startup()
        
        if controller.operation_status.value != "running":
            print("\n❌ System startup failed - cannot continue demo")
            return
        
        # Small delay to let system stabilize
        time.sleep(1)
        
        # 2. Market Data Processing
        processing_results = demo_market_data_processing(controller)
        
        # 3. Signal Execution
        execution_results = demo_signal_execution(controller)
        
        # 4. Error Handling
        errors_generated = demo_error_handling(controller)
        
        # 5. System Health Monitoring
        health_readings = demo_system_health_monitoring(controller)
        
        # 6. Daily Reporting
        report_path = demo_daily_reporting(controller)
        
        # 7. System Shutdown
        shutdown_result = demo_system_shutdown(controller)
        
        # Final Summary
        print_header("DEMO COMPLETION SUMMARY")
        
        print(f"✅ System Startup: Successful")
        print(f"📊 Market Data Processed: {len(processing_results)} packets")
        print(f"📋 Signals Executed: {len(execution_results)} signals")
        print(f"💥 Errors Handled: {errors_generated} errors")
        print(f"🏥 Health Checks: {len(health_readings)} readings")
        print(f"📋 Daily Report: Generated ({report_path})")
        print(f"🛑 System Shutdown: {shutdown_result.status.value}")
        
        # Show final metrics
        if controller.latency_metrics:
            avg_latency = sum(controller.latency_metrics) / len(controller.latency_metrics)
            print(f"⏱️  Average Processing Latency: {avg_latency:.2f}ms")
        
        print(f"⚠️  Total Alerts Generated: {len(controller.alerts_generated)}")
        print(f"🔄 Recovery Attempts: {controller.recovery_attempts}")
        
        print(f"\n🎉 Live Operation Controller demonstration completed successfully!")
        print(f"The system demonstrated robust live operation capabilities with")
        print(f"comprehensive monitoring, error handling, and reporting.")
        
    except Exception as e:
        print(f"\n💥 Demo failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Try to shutdown gracefully if controller exists
        try:
            if 'controller' in locals():
                controller.stop_live_operations()
        except:
            pass


if __name__ == "__main__":
    main()