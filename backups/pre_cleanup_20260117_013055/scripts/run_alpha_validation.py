#!/usr/bin/env python3
"""
Alpha Validation Runner Script

This script executes comprehensive alpha validation testing for the Northstar V3
trading system, validating alpha generation across different market regimes.

Usage:
    python scripts/run_alpha_validation.py [--config CONFIG_FILE] [--output OUTPUT_DIR]

Author: Northstar Team
Date: 2026-01-05
"""

import sys
import argparse
import logging
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from operation.master_operation_controller import MasterOperationController, OperationScenario, OperationPriority
from operation.base_types import OperationConfig
from operation.logging_config import setup_operation_logging


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(description="Run Northstar V3 Alpha Validation")
    parser.add_argument("--config", type=str, help="Configuration file path")
    parser.add_argument("--output", type=str, default="reports/alpha_validation", 
                       help="Output directory for reports")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    parser.add_argument("--regimes", nargs="+", 
                       choices=["bull_market", "bear_market", "sideways_market", "high_volatility", "low_volatility"],
                       help="Specific market regimes to test")
    parser.add_argument("--min-alpha", type=float, default=0.02, 
                       help="Minimum alpha threshold for validation")
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = "DEBUG" if args.verbose else "INFO"
    logger = setup_operation_logging(log_level=log_level)
    
    logger.info("=" * 80)
    logger.info("NORTHSTAR V3 ALPHA VALIDATION RUNNER")
    logger.info("=" * 80)
    logger.info(f"Started at: {datetime.now()}")
    logger.info(f"Output directory: {args.output}")
    logger.info(f"Minimum alpha threshold: {args.min_alpha:.4f}")
    
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
        
        # Prepare alpha validation parameters
        parameters = {
            "min_alpha_threshold": args.min_alpha
        }
        if args.regimes:
            parameters["market_regimes"] = args.regimes
            logger.info(f"Testing specific market regimes: {args.regimes}")
        else:
            logger.info("Testing all configured market regimes")
        
        # Execute alpha validation
        logger.info("Starting alpha validation execution...")
        logger.info("This may take several minutes to complete...")
        
        result = controller.execute_scenario(
            scenario=OperationScenario.ALPHA_VALIDATION,
            parameters=parameters,
            priority=OperationPriority.HIGH
        )
        
        # Report results
        logger.info("=" * 80)
        logger.info("ALPHA VALIDATION RESULTS")
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
        
        # Alpha-specific reporting
        if result.performance_metrics:
            avg_alpha = result.performance_metrics.get("average_alpha", 0)
            avg_ir = result.performance_metrics.get("average_information_ratio", 0)
            avg_hit_rate = result.performance_metrics.get("average_hit_rate", 0)
            
            logger.info("\nAlpha Generation Summary:")
            logger.info(f"  Average Alpha: {avg_alpha:.4f}")
            logger.info(f"  Average Information Ratio: {avg_ir:.4f}")
            logger.info(f"  Average Hit Rate: {avg_hit_rate:.4f}")
            
            # Performance assessment
            if avg_alpha >= args.min_alpha:
                logger.info("  ✅ Alpha generation meets minimum threshold")
            else:
                logger.info("  ❌ Alpha generation below minimum threshold")
        
        if result.alerts_generated:
            logger.info(f"\nAlerts Generated: {len(result.alerts_generated)}")
            for alert in result.alerts_generated[:5]:  # Show first 5 alerts
                logger.info(f"  [{alert.level.value}] {alert.component}: {alert.message}")
        
        if result.report_path:
            logger.info(f"\nDetailed report saved to: {result.report_path}")
        
        # Summary
        logger.info("=" * 80)
        if result.status.value == "success":
            logger.info("✅ ALPHA VALIDATION COMPLETED SUCCESSFULLY")
            exit_code = 0
        elif result.status.value == "warning":
            logger.info("⚠️  ALPHA VALIDATION COMPLETED WITH WARNINGS")
            exit_code = 1
        else:
            logger.info("❌ ALPHA VALIDATION FAILED")
            exit_code = 2
        
        logger.info(f"Completed at: {datetime.now()}")
        logger.info("=" * 80)
        
        return exit_code
        
    except KeyboardInterrupt:
        logger.info("\nAlpha validation interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"Alpha validation failed with error: {str(e)}")
        logger.exception("Full error details:")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)