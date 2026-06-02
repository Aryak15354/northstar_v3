#!/usr/bin/env python3
"""
Comprehensive System Validation Runner Script

This script executes comprehensive system validation for the Northstar V3 trading
system, including system validation, integration testing, and health certification.

Usage:
    python scripts/run_comprehensive_system_validation.py [--config CONFIG_FILE] [--output OUTPUT_DIR]

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
    parser = argparse.ArgumentParser(description="Run Northstar V3 Comprehensive System Validation")
    parser.add_argument("--config", type=str, help="Configuration file path")
    parser.add_argument("--output", type=str, default="reports/system_validation", 
                       help="Output directory for reports")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    parser.add_argument("--skip-integration", action="store_true", 
                       help="Skip integration testing (system validation only)")
    parser.add_argument("--certification-threshold", type=float, default=0.85,
                       help="Minimum score threshold for certification")
    parser.add_argument("--components", nargs="+",
                       choices=["data_pipeline", "intelligence_engine", "risk_management", 
                               "portfolio_management", "system_integration"],
                       help="Specific components to validate")
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = "DEBUG" if args.verbose else "INFO"
    logger = setup_operation_logging(log_level=log_level)
    
    logger.info("=" * 80)
    logger.info("NORTHSTAR V3 COMPREHENSIVE SYSTEM VALIDATION RUNNER")
    logger.info("=" * 80)
    logger.info(f"Started at: {datetime.now()}")
    logger.info(f"Output directory: {args.output}")
    logger.info(f"Certification threshold: {args.certification_threshold:.2f}")
    logger.info(f"Skip integration testing: {args.skip_integration}")
    
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
        
        # Prepare validation parameters
        parameters = {
            "certification_threshold": args.certification_threshold,
            "skip_integration_testing": args.skip_integration
        }
        if args.components:
            parameters["components_to_validate"] = args.components
            logger.info(f"Validating specific components: {args.components}")
        else:
            logger.info("Validating all system components")
        
        # Execute comprehensive system validation
        logger.info("Starting comprehensive system validation...")
        logger.info("This includes:")
        logger.info("  - System component validation")
        logger.info("  - Data pipeline validation")
        logger.info("  - Intelligence engine validation")
        logger.info("  - Risk management validation")
        logger.info("  - Portfolio management validation")
        if not args.skip_integration:
            logger.info("  - Integration testing")
            logger.info("  - Component communication testing")
            logger.info("  - Data flow validation")
            logger.info("  - Error recovery testing")
        logger.info("This may take several minutes to complete...")
        
        result = controller.execute_scenario(
            scenario=OperationScenario.SYSTEM_VALIDATION,
            parameters=parameters,
            priority=OperationPriority.CRITICAL
        )
        
        # Report results
        logger.info("=" * 80)
        logger.info("COMPREHENSIVE SYSTEM VALIDATION RESULTS")
        logger.info("=" * 80)
        logger.info(f"Operation ID: {result.operation_id}")
        logger.info(f"Status: {result.status.value}")
        logger.info(f"Duration: {result.duration_seconds:.2f} seconds")
        
        if result.performance_metrics:
            logger.info("\nSystem Performance Metrics:")
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
        
        # System-specific reporting
        if result.performance_metrics:
            system_score = result.performance_metrics.get("system_validation_score", 0)
            integration_rate = result.performance_metrics.get("integration_test_success_rate", 0)
            certification_ready = result.performance_metrics.get("certification_ready", False)
            
            logger.info("\nSystem Health Summary:")
            logger.info(f"  System Validation Score: {system_score:.4f}")
            if not args.skip_integration:
                logger.info(f"  Integration Test Success Rate: {integration_rate:.4f}")
            logger.info(f"  Certification Ready: {'YES' if certification_ready else 'NO'}")
            
            # Certification assessment
            if certification_ready:
                logger.info("  ✅ System meets certification requirements")
            else:
                logger.info("  ❌ System does not meet certification requirements")
        
        if result.diagnostic_info:
            logger.info("\nDiagnostic Information:")
            for key, value in result.diagnostic_info.items():
                logger.info(f"  {key}: {value}")
        
        if result.alerts_generated:
            logger.info(f"\nAlerts Generated: {len(result.alerts_generated)}")
            for alert in result.alerts_generated[:5]:  # Show first 5 alerts
                logger.info(f"  [{alert.level.value}] {alert.component}: {alert.message}")
            if len(result.alerts_generated) > 5:
                logger.info(f"  ... and {len(result.alerts_generated) - 5} more alerts")
        
        if result.report_path:
            logger.info(f"\nDetailed report saved to: {result.report_path}")
        
        # Recommendations
        logger.info("\nRecommendations:")
        if result.status.value == "success":
            logger.info("  - System is ready for production deployment")
            logger.info("  - Continue with regular monitoring and maintenance")
            logger.info("  - Schedule periodic re-validation")
        elif result.status.value == "warning":
            logger.info("  - Address identified issues before production deployment")
            logger.info("  - Review component performance and optimization opportunities")
            logger.info("  - Re-run validation after fixes")
        else:
            logger.info("  - Critical issues must be resolved before deployment")
            logger.info("  - Review system architecture and component integration")
            logger.info("  - Consider system redesign for failed components")
        
        # Summary
        logger.info("=" * 80)
        if result.status.value == "success":
            logger.info("✅ COMPREHENSIVE SYSTEM VALIDATION COMPLETED SUCCESSFULLY")
            logger.info("   System is certified for production deployment")
            exit_code = 0
        elif result.status.value == "warning":
            logger.info("⚠️  COMPREHENSIVE SYSTEM VALIDATION COMPLETED WITH WARNINGS")
            logger.info("   System functional but requires attention before production")
            exit_code = 1
        else:
            logger.info("❌ COMPREHENSIVE SYSTEM VALIDATION FAILED")
            logger.info("   System not ready for production deployment")
            exit_code = 2
        
        logger.info(f"Completed at: {datetime.now()}")
        logger.info("=" * 80)
        
        return exit_code
        
    except KeyboardInterrupt:
        logger.info("\nSystem validation interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"System validation failed with error: {str(e)}")
        logger.exception("Full error details:")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)