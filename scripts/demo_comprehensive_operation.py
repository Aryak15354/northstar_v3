#!/usr/bin/env python3
"""
Demo script for Northstar V3 Comprehensive Operation System.

This script demonstrates the core functionality of the operation framework
including crisis validation, alpha testing, and system health monitoring.
"""

import sys
import os
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from operation import OperationController, OperationConfig
from operation.base_types import CrisisPeriod, ValidationScenario, AlertConfig, ReportConfig
from datetime import datetime
import logging


def setup_demo_logging():
    """Set up logging for the demo."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger("demo")


def create_demo_config() -> OperationConfig:
    """Create a demo configuration for testing."""
    
    # Create crisis periods
    crisis_periods = [
        CrisisPeriod(
            name="2008_financial_crisis",
            start_date=datetime(2007, 10, 1),
            end_date=datetime(2009, 3, 31),
            severity="extreme",
            characteristics=["credit_crunch", "liquidity_crisis", "volatility_spike"],
            description="Global financial crisis triggered by subprime mortgage collapse"
        ),
        CrisisPeriod(
            name="2020_covid_crash",
            start_date=datetime(2020, 2, 1),
            end_date=datetime(2020, 5, 31),
            severity="extreme",
            characteristics=["pandemic_shock", "circuit_breakers", "policy_response"],
            description="COVID-19 pandemic market crash and recovery"
        )
    ]
    
    # Create validation scenarios
    validation_scenarios = [
        ValidationScenario(
            name="comprehensive_test",
            scenario_type="full_system",
            parameters={"include_all": True},
            timeout_minutes=60
        )
    ]
    
    # Create alert config
    alert_config = AlertConfig(
        email_recipients=["demo@northstar.com"],
        alert_thresholds={
            "max_drawdown": 0.15,
            "min_sharpe": 0.5,
            "max_var_breaches": 5
        }
    )
    
    # Create report config
    report_config = ReportConfig(
        output_directory="reports/demo",
        report_formats=["json", "html"],
        include_charts=True
    )
    
    # Create main config
    config = OperationConfig(
        crisis_periods=crisis_periods,
        validation_scenarios=validation_scenarios,
        performance_thresholds={
            "min_sharpe_ratio": 0.5,
            "max_drawdown": 0.15,
            "min_information_ratio": 0.3,
            "max_var_breaches": 5.0
        },
        alert_settings=alert_config,
        reporting_config=report_config,
        max_concurrent_operations=2,
        enable_real_time_monitoring=True
    )
    
    return config


def demo_crisis_validation(controller: OperationController, logger: logging.Logger):
    """Demonstrate crisis validation functionality."""
    logger.info("=== CRISIS VALIDATION DEMO ===")
    
    # Run crisis scenarios
    crisis_results = controller.run_crisis_scenarios()
    
    logger.info(f"Crisis validation completed - {len(crisis_results)} periods tested")
    
    for result in crisis_results:
        logger.info(f"Crisis: {result.crisis_period}")
        logger.info(f"  Return: {result.total_return:.2%}")
        logger.info(f"  Max Drawdown: {result.max_drawdown:.2%}")
        logger.info(f"  Sharpe Ratio: {result.sharpe_ratio:.2f}")
        logger.info(f"  VaR Breaches: {result.var_breach_count}")
        logger.info(f"  Passed: {result.stress_test_passed}")
        logger.info("")
    
    return crisis_results


def demo_alpha_validation(controller: OperationController, logger: logging.Logger):
    """Demonstrate alpha validation functionality."""
    logger.info("=== ALPHA VALIDATION DEMO ===")
    
    # Run alpha validation
    alpha_results = controller.run_alpha_validation()
    
    logger.info(f"Alpha validation completed - {len(alpha_results)} regimes tested")
    
    for result in alpha_results:
        logger.info(f"Regime: {result.regime}")
        logger.info(f"  Alpha Generated: {result.alpha_generated:.2%}")
        logger.info(f"  Information Ratio: {result.information_ratio:.2f}")
        logger.info(f"  Hit Rate: {result.hit_rate:.2%}")
        logger.info(f"  Signal Quality: {result.signal_quality_score:.2f}")
        logger.info(f"  Passed: {result.validation_passed}")
        logger.info("")
    
    return alpha_results


def demo_comprehensive_validation(controller: OperationController, logger: logging.Logger):
    """Demonstrate comprehensive system validation."""
    logger.info("=== COMPREHENSIVE VALIDATION DEMO ===")
    
    # Run comprehensive validation
    result = controller.run_comprehensive_validation()
    
    logger.info(f"Comprehensive validation completed")
    logger.info(f"  Status: {result.status.value}")
    logger.info(f"  Duration: {result.duration_seconds:.1f} seconds")
    logger.info(f"  Validation Results: {result.validation_results}")
    logger.info(f"  Performance Metrics: {result.performance_metrics}")
    logger.info(f"  Alerts Generated: {len(result.alerts_generated)}")
    
    if result.report_path:
        logger.info(f"  Report Generated: {result.report_path}")
    
    return result


def demo_live_operations(controller: OperationController, logger: logging.Logger):
    """Demonstrate live operations startup."""
    logger.info("=== LIVE OPERATIONS DEMO ===")
    
    # Start live operations
    result = controller.start_live_operations()
    
    logger.info(f"Live operations startup completed")
    logger.info(f"  Status: {result.status.value}")
    logger.info(f"  Validation Results: {result.validation_results}")
    
    if result.alerts_generated:
        logger.info(f"  Alerts: {len(result.alerts_generated)}")
        for alert in result.alerts_generated:
            logger.info(f"    - {alert.level.value}: {alert.message}")
    
    return result


def demo_system_monitoring(controller: OperationController, logger: logging.Logger):
    """Demonstrate system monitoring functionality."""
    logger.info("=== SYSTEM MONITORING DEMO ===")
    
    # Get system status
    health_status = controller.get_system_status()
    
    logger.info(f"System Health Status:")
    logger.info(f"  Overall Health: {health_status.overall_health.value}")
    logger.info(f"  Performance Score: {health_status.performance_score:.2f}")
    logger.info(f"  Data Quality Score: {health_status.data_quality_score:.2f}")
    logger.info(f"  Component Status: {health_status.component_status}")
    
    # Get active operations
    active_ops = controller.get_active_operations()
    logger.info(f"  Active Operations: {len(active_ops)}")
    
    # Get operation history
    history = controller.get_operation_history(limit=5)
    logger.info(f"  Recent Operations: {len(history)}")
    
    return health_status


def demo_report_generation(controller: OperationController, logger: logging.Logger):
    """Demonstrate report generation."""
    logger.info("=== REPORT GENERATION DEMO ===")
    
    # Generate system report
    report_path = controller.generate_system_report("comprehensive")
    
    logger.info(f"System report generated: {report_path}")
    
    # Check if report file exists
    if os.path.exists(report_path):
        file_size = os.path.getsize(report_path)
        logger.info(f"Report file size: {file_size} bytes")
    
    return report_path


def main():
    """Main demo function."""
    logger = setup_demo_logging()
    
    logger.info("Starting Northstar V3 Comprehensive Operation System Demo")
    logger.info("=" * 60)
    
    try:
        # Create demo configuration
        config = create_demo_config()
        logger.info("Demo configuration created")
        
        # Initialize operation controller
        controller = OperationController(config)
        logger.info("Operation controller initialized")
        
        # Run demo scenarios
        logger.info("\nRunning demo scenarios...")
        
        # 1. Crisis validation demo
        crisis_results = demo_crisis_validation(controller, logger)
        
        # 2. Alpha validation demo
        alpha_results = demo_alpha_validation(controller, logger)
        
        # 3. System monitoring demo
        health_status = demo_system_monitoring(controller, logger)
        
        # 4. Live operations demo
        live_result = demo_live_operations(controller, logger)
        
        # 5. Comprehensive validation demo
        comprehensive_result = demo_comprehensive_validation(controller, logger)
        
        # 6. Report generation demo
        report_path = demo_report_generation(controller, logger)
        
        # Summary
        logger.info("\n" + "=" * 60)
        logger.info("DEMO SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Crisis Periods Tested: {len(crisis_results)}")
        logger.info(f"Alpha Regimes Tested: {len(alpha_results)}")
        logger.info(f"System Health: {health_status.overall_health.value}")
        logger.info(f"Live Operations Ready: {live_result.status.value == 'success'}")
        logger.info(f"Comprehensive Validation: {comprehensive_result.status.value}")
        logger.info(f"Report Generated: {report_path}")
        
        logger.info("\nDemo completed successfully!")
        
    except Exception as e:
        logger.error(f"Demo failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)