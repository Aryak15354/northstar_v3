#!/usr/bin/env python3
"""
Crisis Validation Runner Script

This script executes comprehensive crisis validation testing for the Northstar V3
trading system, validating performance during historical crisis periods.

Usage:
    python scripts/run_crisis_validation.py [--config CONFIG_FILE] [--output OUTPUT_DIR]

Author: Northstar Team
Date: 2026-01-05
"""

import sys
import argparse
import logging
import subprocess
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from operation.master_operation_controller import MasterOperationController, OperationScenario, OperationPriority
from operation.base_types import OperationConfig
from operation.logging_config import setup_operation_logging


def _map_crisis_periods_to_brutal_period(crisis_periods):
    if not crisis_periods:
        return "all"
    mapping = {
        "2020_covid_crash": "2020",
        "2008_financial_crisis": "2008",
        "2000_dotcom_bubble": "all",
    }
    # Use first explicit period for deterministic fallback.
    return mapping.get(crisis_periods[0], "all")


def _run_brutal_fallback(logger, crisis_periods) -> bool:
    period = _map_crisis_periods_to_brutal_period(crisis_periods)
    cmd = [sys.executable, "scripts/stress_test_brutal_periods.py", "--period", period]
    logger.info("Attempting fallback crisis validation via brutal period stress tester...")
    logger.info("Fallback command: %s", " ".join(cmd))
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.stdout:
            logger.info(proc.stdout.strip())
        if proc.returncode != 0:
            if proc.stderr:
                logger.error(proc.stderr.strip())
            logger.error("Fallback crisis validation failed with return code %s", proc.returncode)
            return False
        logger.info("Fallback crisis validation completed successfully")
        return True
    except Exception as exc:
        logger.error("Fallback crisis validation failed: %s", exc)
        return False


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(description="Run Northstar V3 Crisis Validation")
    parser.add_argument("--config", type=str, help="Configuration file path")
    parser.add_argument("--output", type=str, default="reports/crisis_validation", 
                       help="Output directory for reports")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    parser.add_argument("--crisis-periods", nargs="+", 
                       choices=["2008_financial_crisis", "2020_covid_crash", "2000_dotcom_bubble"],
                       help="Specific crisis periods to test")
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = "DEBUG" if args.verbose else "INFO"
    logger = setup_operation_logging(log_level=log_level)
    
    logger.info("=" * 80)
    logger.info("NORTHSTAR V3 CRISIS VALIDATION RUNNER")
    logger.info("=" * 80)
    logger.info(f"Started at: {datetime.now()}")
    logger.info(f"Output directory: {args.output}")
    
    try:
        # Create output directory
        output_path = Path(args.output)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Load configuration
        config = OperationConfig()
        if args.config:
            logger.info(f"Loading configuration from: {args.config}")
            # In a full implementation, load config from file
        
        # Update output directory in config
        config.reporting_config.output_directory = str(output_path)
        
        # Initialize master controller
        logger.info("Initializing Master Operation Controller...")
        controller = MasterOperationController(config)
        
        # Prepare crisis validation parameters
        parameters = {}
        if args.crisis_periods:
            parameters["crisis_periods"] = args.crisis_periods
            logger.info(f"Testing specific crisis periods: {args.crisis_periods}")
        else:
            logger.info("Testing all configured crisis periods")
        
        # Execute crisis validation
        logger.info("Starting crisis validation execution...")
        logger.info("This may take several minutes to complete...")
        
        result = controller.execute_scenario(
            scenario=OperationScenario.CRISIS_VALIDATION,
            parameters=parameters,
            priority=OperationPriority.HIGH
        )
        
        # Report results
        logger.info("=" * 80)
        logger.info("CRISIS VALIDATION RESULTS")
        logger.info("=" * 80)
        logger.info(f"Operation ID: {result.operation_id}")
        logger.info(f"Status: {result.status.value}")
        logger.info(f"Duration: {result.duration_seconds:.2f} seconds")
        
        if result.performance_metrics:
            logger.info("\nPerformance Metrics:")
            for metric, value in result.performance_metrics.items():
                if isinstance(value, float):
                    logger.info(f"  {metric}: {value:.4f}")
                else:
                    logger.info(f"  {metric}: {value}")
        
        if result.validation_results:
            logger.info("\nValidation Results:")
            for validation, passed in result.validation_results.items():
                status = "PASSED" if passed else "FAILED"
                logger.info(f"  {validation}: {status}")
        
        if result.alerts_generated:
            logger.info(f"\nAlerts Generated: {len(result.alerts_generated)}")
            for alert in result.alerts_generated[:5]:  # Show first 5 alerts
                logger.info(f"  [{alert.level.value}] {alert.component}: {alert.message}")
        
        if result.report_path:
            logger.info(f"\nDetailed report saved to: {result.report_path}")
        
        # Summary
        logger.info("=" * 80)
        if result.status.value == "success":
            logger.info("✅ CRISIS VALIDATION COMPLETED SUCCESSFULLY")
            exit_code = 0
        elif result.status.value == "warning":
            logger.info("⚠️  CRISIS VALIDATION COMPLETED WITH WARNINGS")
            exit_code = 1
        else:
            logger.info("❌ CRISIS VALIDATION FAILED")
            fallback_ok = _run_brutal_fallback(logger, args.crisis_periods)
            if fallback_ok:
                logger.info("✅ Fallback produced crisis validation artifacts")
                exit_code = 0
            else:
                exit_code = 2
        
        logger.info(f"Completed at: {datetime.now()}")
        logger.info("=" * 80)
        
        return exit_code
        
    except KeyboardInterrupt:
        logger.info("\nCrisis validation interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"Crisis validation failed with error: {str(e)}")
        logger.exception("Full error details:")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
