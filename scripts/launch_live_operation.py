#!/usr/bin/env python3
"""
Live Operation Launcher Script

This script launches the Northstar V3 trading system in live operation mode,
starting all necessary components for real-time trading operations.

Usage:
    python scripts/launch_live_operation.py [--config CONFIG_FILE] [--dry-run]

Author: Northstar Team
Date: 2026-01-05
"""

import sys
import argparse
import logging
import signal
import time
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from operation.master_operation_controller import MasterOperationController, OperationScenario, OperationPriority
from operation.base_types import OperationConfig
from operation.logging_config import setup_operation_logging


class LiveOperationLauncher:
    """Live operation launcher with graceful shutdown handling."""
    
    def __init__(self, controller: MasterOperationController):
        self.controller = controller
        self.logger = logging.getLogger("northstar_operation")
        self.shutdown_requested = False
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        self.logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.shutdown_requested = True
    
    def launch(self, parameters: dict) -> int:
        """Launch live operation with monitoring."""
        try:
            # Start live operation
            self.logger.info("Launching live operation...")
            result = self.controller.execute_scenario(
                scenario=OperationScenario.LIVE_OPERATION,
                parameters=parameters,
                priority=OperationPriority.CRITICAL
            )
            
            if result.status.value != "success":
                self.logger.error("Failed to launch live operation")
                return 1
            
            self.logger.info("Live operation launched successfully")
            self.logger.info("System is now running in live mode")
            self.logger.info("Press Ctrl+C to initiate graceful shutdown")
            
            # Monitor operation
            return self._monitor_live_operation()
            
        except Exception as e:
            self.logger.error(f"Live operation launch failed: {str(e)}")
            return 1
    
    def _monitor_live_operation(self) -> int:
        """Monitor live operation until shutdown."""
        try:
            while not self.shutdown_requested:
                # Check system health
                health = self.controller.get_system_health()
                active_ops = self.controller.get_active_operations()
                
                self.logger.info(f"System Health: {health.value}, Active Operations: {len(active_ops)}")
                
                # Sleep for monitoring interval
                time.sleep(30)  # Check every 30 seconds
            
            # Graceful shutdown
            self.logger.info("Initiating graceful shutdown of live operation...")
            self.controller.stop_operation_controller()
            self.logger.info("Live operation shutdown completed")
            
            return 0
            
        except Exception as e:
            self.logger.error(f"Live operation monitoring failed: {str(e)}")
            return 1


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(description="Launch Northstar V3 Live Operation")
    parser.add_argument("--config", type=str, help="Configuration file path")
    parser.add_argument("--dry-run", action="store_true", 
                       help="Run in simulation mode (no real trading)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    parser.add_argument("--max-position-size", type=int, default=10000,
                       help="Maximum position size per trade")
    parser.add_argument("--risk-limit", type=float, default=0.02,
                       help="Maximum risk per trade as fraction of portfolio")
    parser.add_argument("--monitoring-interval", type=int, default=30,
                       help="Health monitoring interval in seconds")
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = "DEBUG" if args.verbose else "INFO"
    logger = setup_operation_logging(log_level=log_level)
    
    logger.info("=" * 80)
    logger.info("NORTHSTAR V3 LIVE OPERATION LAUNCHER")
    logger.info("=" * 80)
    logger.info(f"Started at: {datetime.now()}")
    logger.info(f"Mode: {'DRY RUN (Simulation)' if args.dry_run else 'LIVE TRADING'}")
    logger.info(f"Max position size: {args.max_position_size}")
    logger.info(f"Risk limit: {args.risk_limit:.4f}")
    
    # Safety confirmation for live trading
    if not args.dry_run:
        logger.warning("⚠️  LIVE TRADING MODE ENABLED ⚠️")
        logger.warning("This will execute real trades with real money!")
        
        try:
            confirmation = input("Type 'CONFIRM LIVE TRADING' to proceed: ")
            if confirmation != "CONFIRM LIVE TRADING":
                logger.info("Live trading not confirmed. Exiting.")
                return 0
        except KeyboardInterrupt:
            logger.info("\nOperation cancelled by user")
            return 0
    
    try:
        # Load configuration
        config = OperationConfig()
        if args.config:
            logger.info(f"Loading configuration from: {args.config}")
            # In a full implementation, load config from file
        
        # Update configuration with command line parameters
        config.max_position_size = args.max_position_size
        config.monitoring_interval_seconds = args.monitoring_interval
        
        # Initialize master controller
        logger.info("Initializing Master Operation Controller...")
        controller = MasterOperationController(config)
        
        # Start operation controller
        controller.start_operation_controller()
        
        # Prepare live operation parameters
        parameters = {
            "dry_run": args.dry_run,
            "max_position_size": args.max_position_size,
            "risk_limit": args.risk_limit,
            "monitoring_interval": args.monitoring_interval
        }
        
        # Pre-flight checks
        logger.info("Performing pre-flight system checks...")
        
        # Run quick system validation
        validation_result = controller.execute_scenario(
            scenario=OperationScenario.SYSTEM_VALIDATION,
            parameters={"quick_check": True},
            priority=OperationPriority.HIGH
        )
        
        if validation_result.status.value == "failure":
            logger.error("Pre-flight system validation failed")
            logger.error("Cannot launch live operation with system issues")
            return 1
        elif validation_result.status.value == "warning":
            logger.warning("Pre-flight system validation completed with warnings")
            if not args.dry_run:
                try:
                    confirmation = input("Continue with live operation despite warnings? (y/N): ")
                    if confirmation.lower() != 'y':
                        logger.info("Live operation cancelled due to system warnings")
                        return 0
                except KeyboardInterrupt:
                    logger.info("\nOperation cancelled by user")
                    return 0
        else:
            logger.info("✅ Pre-flight system validation passed")
        
        # Launch live operation
        launcher = LiveOperationLauncher(controller)
        exit_code = launcher.launch(parameters)
        
        return exit_code
        
    except KeyboardInterrupt:
        logger.info("\nLive operation launch interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"Live operation launch failed with error: {str(e)}")
        logger.exception("Full error details:")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)