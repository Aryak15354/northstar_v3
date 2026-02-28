"""
Northstar V3 Comprehensive Operation System - Master Operation Controller

This module implements the master operation controller that orchestrates all
operation components, manages scenarios, and coordinates comprehensive system
validation and testing.

Author: Northstar Team
Date: 2026-01-05
"""

import logging
import time
import asyncio
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import json
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
import queue
from pathlib import Path

import pandas as pd

from .base_types import (
    OperationResult, OperationStatus, SystemHealthStatus,
    AlertLevel, Alert, ReportConfig, OperationConfig, SystemHealthLevel, HealthStatus
)
from .logging_config import setup_operation_logging
from .report_manager import ReportManager
from .crisis_validator import CrisisValidator
from .alpha_validator import AlphaValidator
from .backtest_orchestrator import BacktestOrchestrator
from .performance_monitor import PerformanceMonitor
from .live_operation_controller import LiveOperationController
from .stress_testing_system import StressTestingSystem
from .walk_forward_analysis_engine import WalkForwardAnalysisEngine
from .system_validation_suite import SystemValidationSuite
from .integration_testing_framework import IntegrationTestingFramework


class OperationScenario(Enum):
    """Types of operation scenarios."""
    CRISIS_VALIDATION = "crisis_validation"
    ALPHA_VALIDATION = "alpha_validation"
    COMPREHENSIVE_BACKTEST = "comprehensive_backtest"
    LIVE_OPERATION = "live_operation"
    STRESS_TESTING = "stress_testing"
    WALK_FORWARD_ANALYSIS = "walk_forward_analysis"
    SYSTEM_VALIDATION = "system_validation"
    INTEGRATION_TESTING = "integration_testing"
    FULL_SYSTEM_TEST = "full_system_test"


class OperationPriority(Enum):
    """Operation priority levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class OperationRequest:
    """Request for operation execution."""
    request_id: str
    scenario: OperationScenario
    priority: OperationPriority
    parameters: Dict[str, Any] = field(default_factory=dict)
    timeout_minutes: int = 120
    callback: Optional[Callable] = None
    dependencies: List[str] = field(default_factory=list)
    scheduled_time: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3


@dataclass
class OperationExecution:
    """Execution state of an operation."""
    request: OperationRequest
    start_time: datetime
    end_time: Optional[datetime] = None
    status: OperationStatus = OperationStatus.IN_PROGRESS
    result: Optional[OperationResult] = None
    error_message: Optional[str] = None
    progress_percentage: float = 0.0
    current_phase: str = "initializing"
    alerts: List[Alert] = field(default_factory=list)
    performance_metrics: Dict[str, float] = field(default_factory=dict)


class MasterOperationController:
    """
    Master operation controller for Northstar V3 comprehensive operations.
    
    This class orchestrates all operation components, manages execution scenarios,
    coordinates system validation, and provides comprehensive operation management.
    """
    
    def __init__(self, config: Optional[OperationConfig] = None):
        """Initialize the master operation controller."""
        self.logger = setup_operation_logging()
        self.config = config or OperationConfig()
        self.report_manager = ReportManager(self.config.reporting_config)
        
        # Initialize operation components
        self._initialize_operation_components()
        
        # Operation management
        self.operation_queue = queue.PriorityQueue()
        self.active_operations = {}
        self.completed_operations = []
        self.operation_history = []
        
        # Execution management
        self.executor = ThreadPoolExecutor(max_workers=self.config.max_concurrent_operations)
        self.is_running = False
        self.shutdown_event = threading.Event()
        
        # Monitoring
        self.system_health = SystemHealthLevel.HEALTHY
        self.last_health_check = datetime.now()
        self.performance_metrics = {}
        
        self.logger.info("Master Operation Controller initialized")
        self.logger.info(f"Configuration: max_concurrent={self.config.max_concurrent_operations}")
    
    def _initialize_operation_components(self):
        """Initialize all operation components."""
        try:
            # Wire real components (no mock runtime wiring)
            self.crisis_validator = CrisisValidator(self.config)
            self.alpha_validator = AlphaValidator(self.config)
            self.backtest_orchestrator = BacktestOrchestrator(logger=self.logger)
            self.performance_monitor = PerformanceMonitor(logger=self.logger)
            self.live_operation_controller = LiveOperationController(self.config)
            self.stress_testing_system = StressTestingSystem()
            self.walk_forward_engine = WalkForwardAnalysisEngine()
            self.system_validation_suite = SystemValidationSuite()
            self.integration_testing_framework = IntegrationTestingFramework()
            
            self.logger.info("All operation components initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize operation components: {str(e)}")
            raise
    
    def start_operation_controller(self):
        """Start the master operation controller."""
        if self.is_running:
            self.logger.warning("Operation controller is already running")
            return
        
        self.logger.info("Starting Master Operation Controller...")
        self.is_running = True
        self.shutdown_event.clear()
        
        # Start background monitoring
        self._start_background_monitoring()
        
        self.logger.info("Master Operation Controller started successfully")
    
    def stop_operation_controller(self):
        """Stop the master operation controller."""
        if not self.is_running:
            self.logger.warning("Operation controller is not running")
            return
        
        self.logger.info("Stopping Master Operation Controller...")
        self.is_running = False
        self.shutdown_event.set()
        
        # Wait for active operations to complete or timeout
        self._wait_for_operations_completion(timeout_seconds=300)
        
        # Shutdown executor
        self.executor.shutdown(wait=True)
        
        self.logger.info("Master Operation Controller stopped")
    
    def submit_operation(self, request: OperationRequest) -> str:
        """
        Submit an operation request for execution.
        
        Args:
            request: Operation request to execute
            
        Returns:
            str: Operation execution ID
        """
        execution_id = f"exec_{int(time.time())}_{request.request_id}"
        
        # Create operation execution
        execution = OperationExecution(
            request=request,
            start_time=datetime.now()
        )
        
        # Add to queue with priority
        priority_value = self._get_priority_value(request.priority)
        self.operation_queue.put((priority_value, execution_id, execution))
        
        self.logger.info(f"Operation submitted: {execution_id} - {request.scenario.value}")
        
        return execution_id
    
    def execute_scenario(self, scenario: OperationScenario, 
                        parameters: Optional[Dict[str, Any]] = None,
                        priority: OperationPriority = OperationPriority.MEDIUM) -> OperationResult:
        """
        Execute a specific operation scenario synchronously.
        
        Args:
            scenario: Operation scenario to execute
            parameters: Scenario parameters
            priority: Operation priority
            
        Returns:
            OperationResult: Result of the operation
        """
        request = OperationRequest(
            request_id=f"sync_{scenario.value}_{int(time.time())}",
            scenario=scenario,
            priority=priority,
            parameters=parameters or {}
        )
        
        execution_id = self.submit_operation(request)
        
        # Wait for completion
        return self._wait_for_operation_completion(execution_id)
    
    def execute_crisis_validation(self, parameters: Optional[Dict[str, Any]] = None) -> OperationResult:
        """Execute crisis validation scenario."""
        self.logger.info("Executing crisis validation scenario")
        
        operation_start = datetime.now()
        operation_id = f"crisis_validation_{int(time.time())}"
        
        try:
            # Run crisis validation
            crisis_results = self.crisis_validator.validate_all_crisis_periods()
            total_periods = len(crisis_results)
            if total_periods == 0:
                raise RuntimeError("Crisis validator returned no results")
            
            # Calculate performance metrics
            performance_metrics = {
                "total_crisis_periods": total_periods,
                "passed_periods": sum(1 for r in crisis_results if r.stress_test_passed),
                "average_sharpe": sum(r.sharpe_ratio for r in crisis_results) / total_periods,
                "worst_drawdown": max(r.max_drawdown for r in crisis_results),
                "total_var_breaches": sum(r.var_breach_count for r in crisis_results)
            }
            
            # Generate alerts for failures
            alerts = []
            failed_periods = [r for r in crisis_results if not r.stress_test_passed]
            for period in failed_periods:
                alerts.append(Alert(
                    timestamp=datetime.now(),
                    level=AlertLevel.WARNING,
                    component="crisis_validator",
                    message=f"Crisis validation failed for {period.crisis_period}",
                    details={"max_drawdown": period.max_drawdown, "sharpe_ratio": period.sharpe_ratio}
                ))
            
            # Generate report
            report_path = self.report_manager.generate_crisis_report(crisis_results, operation_id)
            
            # Determine operation status
            pass_rate = performance_metrics["passed_periods"] / total_periods
            status = OperationStatus.SUCCESS if pass_rate >= 0.8 else OperationStatus.WARNING
            
            return OperationResult(
                operation_id=operation_id,
                operation_type="crisis_validation",
                start_time=operation_start,
                end_time=datetime.now(),
                status=status,
                performance_metrics=performance_metrics,
                validation_results={"crisis_validation_passed": pass_rate >= 0.8},
                alerts_generated=alerts,
                report_path=report_path,
                diagnostic_info={"crisis_results": len(crisis_results)}
            )
            
        except Exception as e:
            self.logger.error(f"Crisis validation failed: {str(e)}")
            return OperationResult(
                operation_id=operation_id,
                operation_type="crisis_validation",
                start_time=operation_start,
                end_time=datetime.now(),
                status=OperationStatus.FAILURE,
                alerts_generated=[Alert(
                    timestamp=datetime.now(),
                    level=AlertLevel.CRITICAL,
                    component="crisis_validator",
                    message=f"Crisis validation execution failed: {str(e)}"
                )]
            )
    
    def execute_alpha_validation(self, parameters: Optional[Dict[str, Any]] = None) -> OperationResult:
        """Execute alpha validation scenario."""
        self.logger.info("Executing alpha validation scenario")
        
        operation_start = datetime.now()
        operation_id = f"alpha_validation_{int(time.time())}"
        
        try:
            # Run alpha validation
            market_data = self._load_alpha_market_data(parameters or {})
            alpha_results = self.alpha_validator.validate_all_regimes(market_data)
            total_regimes = len(alpha_results)
            if total_regimes == 0:
                raise RuntimeError("Alpha validator found no eligible market regimes in provided data")
            
            # Calculate performance metrics
            performance_metrics = {
                "total_regimes": total_regimes,
                "passed_regimes": sum(1 for r in alpha_results if r.validation_passed),
                "average_alpha": sum(r.alpha_generated for r in alpha_results) / total_regimes,
                "average_information_ratio": sum(r.information_ratio for r in alpha_results) / total_regimes,
                "average_hit_rate": sum(r.hit_rate for r in alpha_results) / total_regimes,
                "total_signals": sum(r.signal_count for r in alpha_results)
            }
            
            # Generate alerts for failures
            alerts = []
            failed_regimes = [r for r in alpha_results if not r.validation_passed]
            for regime in failed_regimes:
                alerts.append(Alert(
                    timestamp=datetime.now(),
                    level=AlertLevel.WARNING,
                    component="alpha_validator",
                    message=f"Alpha validation failed for {regime.regime} regime",
                    details={"alpha_generated": regime.alpha_generated, "hit_rate": regime.hit_rate}
                ))
            
            # Generate report
            report_path = self.report_manager.generate_alpha_report(alpha_results, operation_id)
            
            # Determine operation status
            pass_rate = performance_metrics["passed_regimes"] / total_regimes
            status = OperationStatus.SUCCESS if pass_rate >= 0.8 else OperationStatus.WARNING
            
            return OperationResult(
                operation_id=operation_id,
                operation_type="alpha_validation",
                start_time=operation_start,
                end_time=datetime.now(),
                status=status,
                performance_metrics=performance_metrics,
                validation_results={"alpha_validation_passed": pass_rate >= 0.8},
                alerts_generated=alerts,
                report_path=report_path,
                diagnostic_info={"alpha_results": len(alpha_results)}
            )
            
        except Exception as e:
            self.logger.error(f"Alpha validation failed: {str(e)}")
            return OperationResult(
                operation_id=operation_id,
                operation_type="alpha_validation",
                start_time=operation_start,
                end_time=datetime.now(),
                status=OperationStatus.FAILURE,
                alerts_generated=[Alert(
                    timestamp=datetime.now(),
                    level=AlertLevel.CRITICAL,
                    component="alpha_validator",
                    message=f"Alpha validation execution failed: {str(e)}"
                )]
            )
    
    def execute_comprehensive_system_validation(self, parameters: Optional[Dict[str, Any]] = None) -> OperationResult:
        """Execute comprehensive system validation scenario."""
        self.logger.info("Executing comprehensive system validation scenario")
        
        operation_start = datetime.now()
        operation_id = f"comprehensive_validation_{int(time.time())}"
        
        try:
            # Run system validation
            validation_report = self.system_validation_suite.run_comprehensive_system_validation()
            
            # Run integration testing
            integration_report = self.integration_testing_framework.run_comprehensive_integration_tests()
            
            # Calculate combined performance metrics
            integration_success_rate = (
                integration_report.tests_passed / integration_report.tests_executed
                if integration_report.tests_executed
                else 0.0
            )
            performance_metrics = {
                "system_validation_score": validation_report.system_health_score,
                "integration_test_success_rate": integration_success_rate,
                "total_validations": validation_report.total_checks,
                "passed_validations": validation_report.checks_passed,
                "total_integration_tests": integration_report.tests_executed,
                "passed_integration_tests": integration_report.tests_passed,
                "certification_ready": validation_report.certification_status in {"CERTIFIED", "PRODUCTION_READY"}
            }
            
            # Generate combined alerts
            alerts = []
            if validation_report.overall_status != SystemHealthLevel.HEALTHY:
                alerts.append(Alert(
                    timestamp=datetime.now(),
                    level=AlertLevel.WARNING,
                    component="system_validation",
                    message=f"System validation status: {validation_report.overall_status.value}",
                    details={"health_score": validation_report.system_health_score}
                ))
            
            if integration_report.overall_status != SystemHealthLevel.HEALTHY:
                alerts.append(Alert(
                    timestamp=datetime.now(),
                    level=AlertLevel.WARNING,
                    component="integration_testing",
                    message=f"Integration testing status: {integration_report.overall_status.value}",
                    details={"success_rate": integration_success_rate}
                ))
            
            # Generate comprehensive report
            combined_health = self._compose_system_health(validation_report, integration_report)
            report_path = self.report_manager.generate_system_report(
                "comprehensive_validation",
                combined_health,
                self.completed_operations[-20:],  # recent_operations
                []   # active_operations
            )
            
            # Determine operation status
            system_ready = (validation_report.overall_status == SystemHealthLevel.HEALTHY and
                          integration_report.overall_status == SystemHealthLevel.HEALTHY)
            status = OperationStatus.SUCCESS if system_ready else OperationStatus.WARNING
            
            return OperationResult(
                operation_id=operation_id,
                operation_type="comprehensive_system_validation",
                start_time=operation_start,
                end_time=datetime.now(),
                status=status,
                performance_metrics=performance_metrics,
                validation_results={
                    "system_validation_passed": validation_report.overall_status == SystemHealthLevel.HEALTHY,
                    "integration_testing_passed": integration_report.overall_status == SystemHealthLevel.HEALTHY,
                    "comprehensive_validation_passed": system_ready
                },
                alerts_generated=alerts,
                report_path=report_path,
                diagnostic_info={
                    "validation_components": validation_report.total_checks,
                    "integration_tests": integration_report.tests_executed
                }
            )
            
        except Exception as e:
            self.logger.error(f"Comprehensive system validation failed: {str(e)}")
            return OperationResult(
                operation_id=operation_id,
                operation_type="comprehensive_system_validation",
                start_time=operation_start,
                end_time=datetime.now(),
                status=OperationStatus.FAILURE,
                alerts_generated=[Alert(
                    timestamp=datetime.now(),
                    level=AlertLevel.CRITICAL,
                    component="master_controller",
                    message=f"Comprehensive system validation failed: {str(e)}"
                )]
            )
    
    def launch_live_operation(self, parameters: Optional[Dict[str, Any]] = None) -> OperationResult:
        """Launch live operation scenario."""
        self.logger.info("Launching live operation scenario")
        
        operation_start = datetime.now()
        operation_id = f"live_operation_{int(time.time())}"
        
        try:
            # Start live operation controller
            live_result = self.live_operation_controller.start_live_operations()
            
            # Start performance monitoring
            monitoring_started = self.performance_monitor.start_monitoring()
            
            # Calculate performance metrics
            performance_metrics = {
                "live_operation_status": live_result.status.value,
                "monitoring_active": bool(monitoring_started),
                "startup_time_seconds": (datetime.now() - operation_start).total_seconds()
            }
            
            # Generate alerts
            alerts = []
            if live_result.status != OperationStatus.SUCCESS:
                alerts.append(Alert(
                    timestamp=datetime.now(),
                    level=AlertLevel.CRITICAL,
                    component="live_operation",
                    message="Live operation failed to start",
                    details={"error": "Live operation startup failed"}
                ))
            if not monitoring_started:
                alerts.append(Alert(
                    timestamp=datetime.now(),
                    level=AlertLevel.WARNING,
                    component="performance_monitor",
                    message="Performance monitoring did not start",
                    details={"monitoring_active": False}
                ))
            
            # Determine operation status
            status = (
                OperationStatus.SUCCESS
                if live_result.status == OperationStatus.SUCCESS and monitoring_started
                else OperationStatus.FAILURE
            )
            
            return OperationResult(
                operation_id=operation_id,
                operation_type="live_operation_launch",
                start_time=operation_start,
                end_time=datetime.now(),
                status=status,
                performance_metrics=performance_metrics,
                validation_results={"live_operation_launched": status == OperationStatus.SUCCESS},
                alerts_generated=alerts,
                diagnostic_info={"live_controller_active": True}
            )
            
        except Exception as e:
            self.logger.error(f"Live operation launch failed: {str(e)}")
            return OperationResult(
                operation_id=operation_id,
                operation_type="live_operation_launch",
                start_time=operation_start,
                end_time=datetime.now(),
                status=OperationStatus.FAILURE,
                alerts_generated=[Alert(
                    timestamp=datetime.now(),
                    level=AlertLevel.CRITICAL,
                    component="live_operation",
                    message=f"Live operation launch failed: {str(e)}"
                )]
            )
    
    def get_operation_status(self, execution_id: str) -> Optional[OperationExecution]:
        """Get status of a specific operation."""
        return self.active_operations.get(execution_id)
    
    def get_active_operations(self) -> Dict[str, OperationExecution]:
        """Get all active operations."""
        return self.active_operations.copy()
    
    def get_operation_history(self) -> List[OperationResult]:
        """Get operation history."""
        return self.completed_operations.copy()
    
    def get_system_health(self) -> SystemHealthLevel:
        """Get current system health status."""
        return self.system_health

    def _load_alpha_market_data(self, parameters: Dict[str, Any]) -> pd.DataFrame:
        """
        Load market data for alpha validation with deterministic real-data fallback.
        """
        provided = parameters.get("market_data")
        if isinstance(provided, pd.DataFrame) and not provided.empty:
            df = provided.copy()
            if "date" not in df.columns:
                if isinstance(df.index, pd.DatetimeIndex):
                    df = df.reset_index().rename(columns={"index": "date"})
                else:
                    raise ValueError("Provided market_data must include a 'date' column")
            if "close" not in df.columns:
                raise ValueError("Provided market_data must include a 'close' column")
            return df

        market_data_path = parameters.get("market_data_path")
        candidate_paths = [Path(market_data_path)] if market_data_path else []
        candidate_paths.extend([
            Path("data/processed/nifty.parquet"),
            Path("data/processed/index_data/nifty_50.parquet"),
            Path("data/processed/prices.parquet"),
        ])

        for path in candidate_paths:
            if not path.exists():
                continue
            if path.suffix == ".parquet":
                df = pd.read_parquet(path)
            elif path.suffix in {".csv", ".txt"}:
                df = pd.read_csv(path)
            else:
                continue

            # Handle multi-ticker price tables.
            if "ticker" in df.columns and "Close" in df.columns:
                nifty_df = df[df["ticker"].astype(str).str.upper() == "NIFTY.NS"].copy()
                if nifty_df.empty:
                    nifty_df = df.sort_values("Date").groupby("Date", as_index=False)["Close"].mean()
                    nifty_df = nifty_df.rename(columns={"Date": "date", "Close": "close"})
                else:
                    nifty_df = nifty_df.rename(columns={"Date": "date", "Close": "close"})
                nifty_df["date"] = pd.to_datetime(nifty_df["date"], errors="coerce")
                return nifty_df.dropna(subset=["date", "close"]).sort_values("date")

            # Handle direct close-series data.
            close_col = None
            for col in ("close", "Close", "adj_close", "Adj Close"):
                if col in df.columns:
                    close_col = col
                    break
            if close_col is None:
                continue

            if "date" in df.columns:
                date_series = pd.to_datetime(df["date"], errors="coerce")
            elif "Date" in df.columns:
                date_series = pd.to_datetime(df["Date"], errors="coerce")
            elif isinstance(df.index, pd.DatetimeIndex):
                date_series = pd.to_datetime(df.index, errors="coerce")
            else:
                continue

            normalized = pd.DataFrame({
                "date": date_series,
                "close": pd.to_numeric(df[close_col], errors="coerce"),
            })
            normalized = normalized.dropna(subset=["date", "close"]).sort_values("date")
            if not normalized.empty:
                return normalized

        raise FileNotFoundError(
            "Unable to load alpha validation market data. "
            "Pass `parameters={'market_data': <DataFrame>}` or a valid `market_data_path`."
        )

    def _compose_system_health(self, validation_report: Any, integration_report: Any) -> SystemHealthStatus:
        """Build a unified SystemHealthStatus for reporting APIs."""
        overall_map = {
            SystemHealthLevel.HEALTHY: HealthStatus.HEALTHY,
            SystemHealthLevel.WARNING: HealthStatus.WARNING,
            SystemHealthLevel.DEGRADED: HealthStatus.WARNING,
            SystemHealthLevel.CRITICAL: HealthStatus.CRITICAL,
            SystemHealthLevel.UNKNOWN: HealthStatus.WARNING,
        }
        health_enum = overall_map.get(validation_report.overall_status, HealthStatus.WARNING)

        component_status = {
            "system_validation": validation_report.overall_status.value,
            "integration_testing": integration_report.overall_status.value,
        }
        performance_score = float(validation_report.system_health_score)
        data_quality_score = (
            float(integration_report.tests_passed / integration_report.tests_executed)
            if integration_report.tests_executed
            else 0.0
        )

        return SystemHealthStatus(
            timestamp=datetime.now(),
            overall_health=health_enum,
            component_status=component_status,
            performance_score=performance_score,
            data_quality_score=data_quality_score,
            alert_level=AlertLevel.WARNING if health_enum != HealthStatus.HEALTHY else AlertLevel.INFO,
            recommended_actions=[],
        )
    
    def _get_priority_value(self, priority: OperationPriority) -> int:
        """Convert priority enum to numeric value for queue ordering."""
        priority_map = {
            OperationPriority.CRITICAL: 1,
            OperationPriority.HIGH: 2,
            OperationPriority.MEDIUM: 3,
            OperationPriority.LOW: 4
        }
        return priority_map.get(priority, 3)
    
    def _wait_for_operation_completion(self, execution_id: str, timeout_seconds: int = 30) -> OperationResult:
        """Wait for operation completion."""
        start_time = time.time()
        
        while time.time() - start_time < timeout_seconds:
            # Check if operation completed
            for op in self.completed_operations:
                if execution_id in op.operation_id:
                    return op
            
            # Check if operation is still active
            if execution_id not in self.active_operations:
                # Operation may have completed, check again
                for op in self.completed_operations:
                    if execution_id in op.operation_id:
                        return op
                
                # If not found in completed and not active, it may have failed
                break
            
            time.sleep(0.1)  # Shorter sleep for better responsiveness
        
        # Timeout or operation not found - return a default result
        return OperationResult(
            operation_id=execution_id,
            operation_type="unknown",
            start_time=datetime.now(),
            end_time=datetime.now(),
            status=OperationStatus.FAILURE,
            alerts_generated=[Alert(
                timestamp=datetime.now(),
                level=AlertLevel.WARNING,
                component="master_controller",
                message=f"Operation {execution_id} timed out or was not found"
            )]
        )
    
    def _wait_for_operations_completion(self, timeout_seconds: int = 300):
        """Wait for all active operations to complete."""
        start_time = time.time()
        
        while self.active_operations and time.time() - start_time < timeout_seconds:
            time.sleep(1)
        
        if self.active_operations:
            self.logger.warning(f"Timeout waiting for {len(self.active_operations)} operations to complete")
    
    def _start_background_monitoring(self):
        """Start background monitoring thread."""
        def monitor_loop():
            while self.is_running and not self.shutdown_event.is_set():
                try:
                    self._update_system_health()
                    self._process_operation_queue()
                    time.sleep(10)  # Check every 10 seconds
                except Exception as e:
                    self.logger.error(f"Background monitoring error: {str(e)}")
        
        monitoring_thread = threading.Thread(target=monitor_loop, daemon=True)
        monitoring_thread.start()
    
    def _update_system_health(self):
        """Update system health status."""
        try:
            # Simple health check based on active operations and recent errors
            current_time = datetime.now()
            
            # Check if too many operations are failing
            recent_operations = [op for op in self.completed_operations 
                               if (current_time - op.start_time).total_seconds() < 3600]  # Last hour
            
            if recent_operations:
                failure_rate = sum(1 for op in recent_operations if op.status == OperationStatus.FAILURE) / len(recent_operations)
                
                if failure_rate > 0.5:
                    self.system_health = SystemHealthLevel.CRITICAL
                elif failure_rate > 0.2:
                    self.system_health = SystemHealthLevel.DEGRADED
                elif failure_rate > 0.1:
                    self.system_health = SystemHealthLevel.WARNING
                else:
                    self.system_health = SystemHealthLevel.HEALTHY
            
            self.last_health_check = current_time
            
        except Exception as e:
            self.logger.error(f"Health check failed: {str(e)}")
            self.system_health = SystemHealthLevel.UNKNOWN
    
    def _process_operation_queue(self):
        """Process operations from the queue."""
        while not self.operation_queue.empty() and len(self.active_operations) < self.config.max_concurrent_operations:
            try:
                priority, execution_id, execution = self.operation_queue.get_nowait()
                
                # Start operation execution
                future = self.executor.submit(self._execute_operation, execution_id, execution)
                self.active_operations[execution_id] = execution
                
                self.logger.info(f"Started operation execution: {execution_id}")
                
            except queue.Empty:
                break
            except Exception as e:
                self.logger.error(f"Failed to process operation queue: {str(e)}")
    
    def _execute_operation(self, execution_id: str, execution: OperationExecution) -> OperationResult:
        """Execute an operation."""
        try:
            self.logger.info(f"Executing operation: {execution_id} - {execution.request.scenario.value}")
            
            # Route to appropriate handler
            if execution.request.scenario == OperationScenario.CRISIS_VALIDATION:
                result = self.execute_crisis_validation(execution.request.parameters)
            elif execution.request.scenario == OperationScenario.ALPHA_VALIDATION:
                result = self.execute_alpha_validation(execution.request.parameters)
            elif execution.request.scenario == OperationScenario.SYSTEM_VALIDATION:
                result = self.execute_comprehensive_system_validation(execution.request.parameters)
            elif execution.request.scenario == OperationScenario.LIVE_OPERATION:
                result = self.launch_live_operation(execution.request.parameters)
            else:
                raise ValueError(f"Unsupported operation scenario: {execution.request.scenario}")
            
            # Update execution
            execution.end_time = datetime.now()
            execution.status = OperationStatus.SUCCESS
            execution.result = result
            execution.progress_percentage = 100.0
            execution.current_phase = "completed"
            
            # Move to completed operations
            self.completed_operations.append(result)
            
            # Execute callback if provided
            if execution.request.callback:
                try:
                    execution.request.callback(result)
                except Exception as e:
                    self.logger.error(f"Operation callback failed: {str(e)}")
            
            self.logger.info(f"Operation completed successfully: {execution_id}")
            return result
            
        except Exception as e:
            self.logger.error(f"Operation execution failed: {execution_id} - {str(e)}")
            
            # Create failure result
            result = OperationResult(
                operation_id=execution_id,
                operation_type=execution.request.scenario.value,
                start_time=execution.start_time,
                end_time=datetime.now(),
                status=OperationStatus.FAILURE,
                alerts_generated=[Alert(
                    timestamp=datetime.now(),
                    level=AlertLevel.CRITICAL,
                    component="master_controller",
                    message=f"Operation execution failed: {str(e)}"
                )]
            )
            
            execution.end_time = datetime.now()
            execution.status = OperationStatus.FAILURE
            execution.result = result
            execution.error_message = str(e)
            
            self.completed_operations.append(result)
            return result
            
        finally:
            # Remove from active operations
            if execution_id in self.active_operations:
                del self.active_operations[execution_id]
