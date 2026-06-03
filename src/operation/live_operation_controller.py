"""
Live Operation Controller - Manages live trading operations with real-time monitoring.

This module provides comprehensive live operation management including system validation,
market data processing, signal execution, error handling, and daily reporting.
"""

import logging
import time
import threading
import queue
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from pathlib import Path
import json

from .base_types import (
    OperationResult, OperationStatus, OperationConfig,
    Alert, AlertLevel, HealthStatus, SystemHealthStatus,
    LiveOperationStatus, MarketDataStatus, SignalExecutionResult
)
from .logging_config import setup_operation_logging
from .report_manager import ReportManager


class LiveOperationController:
    """
    Manages live trading operations with comprehensive monitoring and control.
    
    Provides system component validation, market data processing with latency monitoring,
    risk-compliant signal execution, graceful error handling, and daily reporting.
    """
    
    def __init__(self, config: Optional[OperationConfig] = None):
        """Initialize the live operation controller."""
        self.config = config or OperationConfig()
        self.logger = setup_operation_logging()
        self.report_manager = ReportManager(self.config.reporting_config)
        
        # Operation state
        self.operation_status = LiveOperationStatus.STOPPED
        self.start_time: Optional[datetime] = None
        self.last_health_check: Optional[datetime] = None
        
        # Component validation
        self.component_status: Dict[str, bool] = {}
        self.validation_results: Dict[str, Any] = {}
        
        # Market data processing
        self.market_data_queue = queue.Queue(maxsize=1000)
        self.market_data_status = MarketDataStatus.DISCONNECTED
        self.latency_metrics: List[float] = []
        self.data_processing_thread: Optional[threading.Thread] = None
        
        # Signal execution
        self.signal_queue = queue.Queue(maxsize=100)
        self.execution_results: List[SignalExecutionResult] = []
        self.signal_execution_thread: Optional[threading.Thread] = None
        
        # Error handling
        self.error_count = 0
        self.error_log: List[Dict[str, Any]] = []
        self.recovery_attempts = 0
        
        # Monitoring and reporting
        self.daily_metrics: Dict[str, Any] = {}
        self.monitoring_data: List[Dict[str, Any]] = []
        self.alerts_generated: List[Alert] = []
        
        # Threading control
        self.shutdown_event = threading.Event()
        self.monitoring_thread: Optional[threading.Thread] = None
        
        self.logger.info("Live Operation Controller initialized")
    
    def start_live_operations(self) -> OperationResult:
        """
        Start live trading operations with comprehensive validation.
        
        Returns:
            OperationResult: Startup validation results
        """
        operation_start = datetime.now()
        self.logger.info("Starting live operations...")
        
        try:
            # Step 1: Validate all system components
            self.logger.info("Validating system components...")
            component_validation = self._validate_system_components()
            
            if not component_validation["all_components_valid"]:
                failed_components = component_validation["failed_components"]
                error_msg = f"Component validation failed: {failed_components}"
                self.logger.error(error_msg)
                
                return OperationResult(
                    operation_id="live_startup",
                    operation_type="live_operations_start",
                    start_time=operation_start,
                    end_time=datetime.now(),
                    status=OperationStatus.FAILURE,
                    validation_results=component_validation,
                    diagnostic_info={"error": error_msg}
                )
            
            # Step 2: Initialize market data processing
            self.logger.info("Initializing market data processing...")
            self._initialize_market_data_processing()
            
            # Step 3: Initialize signal execution system
            self.logger.info("Initializing signal execution system...")
            self._initialize_signal_execution()
            
            # Step 4: Start monitoring systems
            self.logger.info("Starting monitoring systems...")
            self._start_monitoring_systems()
            
            # Step 5: Update operation status
            self.operation_status = LiveOperationStatus.RUNNING
            self.start_time = operation_start
            self.last_health_check = datetime.now()
            
            self.logger.info("Live operations started successfully")
            
            return OperationResult(
                operation_id="live_startup",
                operation_type="live_operations_start",
                start_time=operation_start,
                end_time=datetime.now(),
                status=OperationStatus.SUCCESS,
                validation_results=component_validation,
                performance_metrics=self._get_startup_metrics()
            )
            
        except Exception as e:
            self.logger.error(f"Live operations startup failed: {str(e)}")
            self.operation_status = LiveOperationStatus.ERROR
            
            # Generate critical alert
            alert = Alert(
                timestamp=datetime.now(),
                level=AlertLevel.CRITICAL,
                component="LiveOperationController",
                message=f"Live operations startup failed: {str(e)}",
                details={"error": str(e), "startup_time": operation_start.isoformat()}
            )
            self.alerts_generated.append(alert)
            
            return OperationResult(
                operation_id="live_startup",
                operation_type="live_operations_start",
                start_time=operation_start,
                end_time=datetime.now(),
                status=OperationStatus.FAILURE,
                diagnostic_info={"error": str(e)},
                alerts_generated=[alert]
            )
    
    def stop_live_operations(self) -> OperationResult:
        """
        Stop live trading operations gracefully.
        
        Returns:
            OperationResult: Shutdown results
        """
        operation_start = datetime.now()
        self.logger.info("Stopping live operations...")
        
        try:
            # Signal shutdown to all threads
            self.shutdown_event.set()
            
            # Stop monitoring systems
            if self.monitoring_thread and self.monitoring_thread.is_alive():
                self.monitoring_thread.join(timeout=5.0)
            
            # Stop data processing
            if self.data_processing_thread and self.data_processing_thread.is_alive():
                self.data_processing_thread.join(timeout=5.0)
            
            # Stop signal execution
            if self.signal_execution_thread and self.signal_execution_thread.is_alive():
                self.signal_execution_thread.join(timeout=5.0)
            
            # Generate final daily report
            daily_report_path = self._generate_daily_report()
            
            # Update status
            self.operation_status = LiveOperationStatus.STOPPED
            
            self.logger.info("Live operations stopped successfully")
            
            return OperationResult(
                operation_id="live_shutdown",
                operation_type="live_operations_stop",
                start_time=operation_start,
                end_time=datetime.now(),
                status=OperationStatus.SUCCESS,
                report_path=daily_report_path,
                performance_metrics=self._get_shutdown_metrics()
            )
            
        except Exception as e:
            self.logger.error(f"Live operations shutdown failed: {str(e)}")
            self.operation_status = LiveOperationStatus.ERROR
            
            return OperationResult(
                operation_id="live_shutdown",
                operation_type="live_operations_stop",
                start_time=operation_start,
                end_time=datetime.now(),
                status=OperationStatus.FAILURE,
                diagnostic_info={"error": str(e)}
            )
    
    def process_market_data(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process incoming market data with latency monitoring.
        
        Args:
            market_data: Market data to process
            
        Returns:
            Dict[str, Any]: Processing results with latency metrics
        """
        processing_start = time.time()
        
        try:
            # Add to processing queue
            if not self.market_data_queue.full():
                self.market_data_queue.put({
                    "data": market_data,
                    "timestamp": datetime.now(),
                    "processing_start": processing_start
                })
                
                # Calculate latency
                processing_latency = (time.time() - processing_start) * 1000  # ms
                self.latency_metrics.append(processing_latency)
                
                # Keep only recent latency metrics (last 1000)
                if len(self.latency_metrics) > 1000:
                    self.latency_metrics = self.latency_metrics[-1000:]
                
                # Check latency thresholds
                if processing_latency > self.config.max_processing_latency_ms:
                    alert = Alert(
                        timestamp=datetime.now(),
                        level=AlertLevel.WARNING,
                        component="LiveOperationController",
                        message=f"High market data processing latency: {processing_latency:.2f}ms",
                        details={
                            "latency_ms": processing_latency,
                            "threshold_ms": self.config.max_processing_latency_ms,
                            "data_size": len(str(market_data))
                        }
                    )
                    self.alerts_generated.append(alert)
                
                return {
                    "status": "processed",
                    "latency_ms": processing_latency,
                    "queue_size": self.market_data_queue.qsize(),
                    "timestamp": datetime.now().isoformat()
                }
            else:
                # Queue is full - generate alert
                alert = Alert(
                    timestamp=datetime.now(),
                    level=AlertLevel.CRITICAL,
                    component="LiveOperationController",
                    message="Market data queue is full - dropping data",
                    details={"queue_size": self.market_data_queue.qsize()}
                )
                self.alerts_generated.append(alert)
                
                return {
                    "status": "queue_full",
                    "error": "Market data queue is full",
                    "queue_size": self.market_data_queue.qsize()
                }
                
        except Exception as e:
            self.logger.error(f"Market data processing failed: {str(e)}")
            self._handle_error("market_data_processing", str(e))
            
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def execute_signal(self, signal: Dict[str, Any]) -> SignalExecutionResult:
        """
        Execute trading signal with risk compliance validation.
        
        Args:
            signal: Trading signal to execute
            
        Returns:
            SignalExecutionResult: Execution results
        """
        execution_start = datetime.now()
        
        try:
            # Validate signal compliance with risk parameters
            compliance_check = self._validate_signal_compliance(signal)
            
            if not compliance_check["compliant"]:
                # Signal violates risk parameters
                result = SignalExecutionResult(
                    signal_id=signal.get("signal_id", "unknown"),
                    execution_time=execution_start,
                    status="rejected",
                    rejection_reason=compliance_check["rejection_reason"],
                    risk_compliance=False,
                    execution_latency_ms=0.0
                )
                
                # Generate alert for rejected signal
                alert = Alert(
                    timestamp=execution_start,
                    level=AlertLevel.WARNING,
                    component="LiveOperationController",
                    message=f"Signal rejected due to risk compliance: {compliance_check['rejection_reason']}",
                    details={
                        "signal_id": signal.get("signal_id"),
                        "rejection_reason": compliance_check["rejection_reason"],
                        "signal_details": signal
                    }
                )
                self.alerts_generated.append(alert)
                
                return result
            
            # Execute the signal (mock implementation)
            execution_latency = (datetime.now() - execution_start).total_seconds() * 1000
            
            result = SignalExecutionResult(
                signal_id=signal.get("signal_id", "unknown"),
                execution_time=execution_start,
                status="executed",
                execution_price=signal.get("target_price", 100.0),
                executed_quantity=signal.get("quantity", 100),
                risk_compliance=True,
                execution_latency_ms=execution_latency
            )
            
            self.execution_results.append(result)
            
            # Check execution latency
            if execution_latency > self.config.max_execution_latency_ms:
                alert = Alert(
                    timestamp=datetime.now(),
                    level=AlertLevel.WARNING,
                    component="LiveOperationController",
                    message=f"High signal execution latency: {execution_latency:.2f}ms",
                    details={
                        "signal_id": signal.get("signal_id"),
                        "latency_ms": execution_latency,
                        "threshold_ms": self.config.max_execution_latency_ms
                    }
                )
                self.alerts_generated.append(alert)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Signal execution failed: {str(e)}")
            self._handle_error("signal_execution", str(e))
            
            return SignalExecutionResult(
                signal_id=signal.get("signal_id", "unknown"),
                execution_time=execution_start,
                status="error",
                error_message=str(e),
                risk_compliance=False,
                execution_latency_ms=0.0
            )
    
    def get_system_health(self) -> SystemHealthStatus:
        """Get current system health status."""
        current_time = datetime.now()
        
        # Calculate health metrics
        avg_latency = sum(self.latency_metrics[-100:]) / len(self.latency_metrics[-100:]) if self.latency_metrics else 0.0
        error_rate = self.error_count / max(1, len(self.monitoring_data))
        
        # Determine overall health
        overall_health = HealthStatus.HEALTHY
        if error_rate > 0.05 or avg_latency > self.config.max_processing_latency_ms:
            overall_health = HealthStatus.WARNING
        if error_rate > 0.10 or avg_latency > self.config.max_processing_latency_ms * 2:
            overall_health = HealthStatus.CRITICAL
        
        return SystemHealthStatus(
            timestamp=current_time,
            overall_health=overall_health,
            component_status=self.component_status,
            performance_score=max(0.0, 1.0 - error_rate),
            data_quality_score=1.0 - (len([a for a in self.alerts_generated if "data" in a.message.lower()]) / max(1, len(self.alerts_generated))),
            latency_metrics={"avg_latency_ms": avg_latency, "max_latency_ms": max(self.latency_metrics[-100:]) if self.latency_metrics else 0.0},
            error_counts={"total_errors": self.error_count, "recent_errors": len([e for e in self.error_log if (current_time - datetime.fromisoformat(e["timestamp"])).total_seconds() < 3600])}
        )
    
    def generate_daily_report(self) -> str:
        """Generate comprehensive daily operations report."""
        return self._generate_daily_report()
    
    def get_operation_status(self) -> Dict[str, Any]:
        """Get current operation status and metrics."""
        current_time = datetime.now()
        uptime = (current_time - self.start_time).total_seconds() if self.start_time else 0
        
        return {
            "operation_status": self.operation_status.value,
            "uptime_seconds": uptime,
            "market_data_status": self.market_data_status.value,
            "queue_sizes": {
                "market_data": self.market_data_queue.qsize(),
                "signals": self.signal_queue.qsize()
            },
            "performance_metrics": {
                "avg_processing_latency_ms": sum(self.latency_metrics[-100:]) / len(self.latency_metrics[-100:]) if self.latency_metrics else 0.0,
                "total_signals_executed": len(self.execution_results),
                "successful_executions": len([r for r in self.execution_results if r.status == "executed"]),
                "error_count": self.error_count,
                "alerts_generated": len(self.alerts_generated)
            },
            "last_health_check": self.last_health_check.isoformat() if self.last_health_check else None
        }
    
    # Private helper methods
    
    def _validate_system_components(self) -> Dict[str, Any]:
        """Validate all system components are operational."""
        components_to_validate = [
            "data_pipeline",
            "intelligence_engines", 
            "risk_management",
            "portfolio_management",
            "market_data_feeds",
            "execution_system"
        ]
        
        validation_results = {}
        failed_components = []
        
        for component in components_to_validate:
            try:
                # Mock component validation - in real implementation would check actual components
                is_valid = self._validate_component(component)
                validation_results[component] = is_valid
                self.component_status[component] = is_valid
                
                if not is_valid:
                    failed_components.append(component)
                    
            except Exception as e:
                self.logger.error(f"Component validation failed for {component}: {str(e)}")
                validation_results[component] = False
                self.component_status[component] = False
                failed_components.append(component)
        
        all_valid = len(failed_components) == 0
        
        return {
            "all_components_valid": all_valid,
            "component_results": validation_results,
            "failed_components": failed_components,
            "validation_timestamp": datetime.now().isoformat()
        }
    
    def _validate_component(self, component_name: str) -> bool:
        """Validate a specific system component."""
        # Mock implementation - would check actual component health
        # For demo purposes, randomly fail some components occasionally
        import random
        return random.random() > 0.1  # 90% success rate
    
    def _initialize_market_data_processing(self):
        """Initialize market data processing thread."""
        self.market_data_status = MarketDataStatus.CONNECTING
        
        def data_processing_worker():
            """Worker thread for processing market data."""
            while not self.shutdown_event.is_set():
                try:
                    # Process data from queue
                    if not self.market_data_queue.empty():
                        data_item = self.market_data_queue.get(timeout=1.0)
                        # Process the data item (mock processing)
                        time.sleep(0.001)  # Simulate processing time
                        
                    self.market_data_status = MarketDataStatus.CONNECTED
                    
                except queue.Empty:
                    continue
                except Exception as e:
                    self.logger.error(f"Data processing error: {str(e)}")
                    self._handle_error("data_processing", str(e))
        
        self.data_processing_thread = threading.Thread(target=data_processing_worker, daemon=True)
        self.data_processing_thread.start()
    
    def _initialize_signal_execution(self):
        """Initialize signal execution thread."""
        def signal_execution_worker():
            """Worker thread for executing signals."""
            while not self.shutdown_event.is_set():
                try:
                    # Process signals from queue
                    if not self.signal_queue.empty():
                        signal = self.signal_queue.get(timeout=1.0)
                        result = self.execute_signal(signal)
                        # Signal processed
                        
                except queue.Empty:
                    continue
                except Exception as e:
                    self.logger.error(f"Signal execution error: {str(e)}")
                    self._handle_error("signal_execution", str(e))
        
        self.signal_execution_thread = threading.Thread(target=signal_execution_worker, daemon=True)
        self.signal_execution_thread.start()
    
    def _start_monitoring_systems(self):
        """Start monitoring and health check systems."""
        def monitoring_worker():
            """Worker thread for system monitoring."""
            while not self.shutdown_event.is_set():
                try:
                    # Perform health check
                    health_status = self.get_system_health()
                    self.last_health_check = datetime.now()
                    
                    # Store monitoring data
                    monitoring_data = {
                        "timestamp": datetime.now().isoformat(),
                        "health_status": health_status.overall_health.value,
                        "performance_score": health_status.performance_score,
                        "error_count": self.error_count,
                        "queue_sizes": {
                            "market_data": self.market_data_queue.qsize(),
                            "signals": self.signal_queue.qsize()
                        }
                    }
                    self.monitoring_data.append(monitoring_data)
                    
                    # Keep only recent monitoring data (last 1000 entries)
                    if len(self.monitoring_data) > 1000:
                        self.monitoring_data = self.monitoring_data[-1000:]
                    
                    # Sleep for monitoring interval
                    time.sleep(self.config.monitoring_interval_seconds)
                    
                except Exception as e:
                    self.logger.error(f"Monitoring error: {str(e)}")
                    self._handle_error("monitoring", str(e))
        
        self.monitoring_thread = threading.Thread(target=monitoring_worker, daemon=True)
        self.monitoring_thread.start()
    
    def _validate_signal_compliance(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        """Validate signal compliance with risk parameters."""
        # Mock risk compliance validation
        symbol = signal.get("symbol", "")
        quantity = signal.get("quantity", 0)
        signal_type = signal.get("type", "")
        
        # Check position size limits
        if abs(quantity) > self.config.max_position_size:
            return {
                "compliant": False,
                "rejection_reason": f"Position size {quantity} exceeds limit {self.config.max_position_size}"
            }
        
        # Check symbol restrictions
        if symbol in self.config.restricted_symbols:
            return {
                "compliant": False,
                "rejection_reason": f"Symbol {symbol} is restricted"
            }
        
        # Check signal type
        if signal_type not in self.config.allowed_signal_types:
            return {
                "compliant": False,
                "rejection_reason": f"Signal type {signal_type} not allowed"
            }
        
        return {"compliant": True}
    
    def _handle_error(self, component: str, error_message: str):
        """Handle errors with graceful recovery attempts."""
        self.error_count += 1
        
        error_entry = {
            "timestamp": datetime.now().isoformat(),
            "component": component,
            "error": error_message,
            "recovery_attempt": self.recovery_attempts
        }
        self.error_log.append(error_entry)
        
        # Keep only recent errors (last 1000)
        if len(self.error_log) > 1000:
            self.error_log = self.error_log[-1000:]
        
        # Generate alert for error
        alert_level = AlertLevel.WARNING
        if self.error_count > 10:
            alert_level = AlertLevel.CRITICAL
        
        alert = Alert(
            timestamp=datetime.now(),
            level=alert_level,
            component=component,
            message=f"Error in {component}: {error_message}",
            details={"error_count": self.error_count, "recovery_attempts": self.recovery_attempts}
        )
        self.alerts_generated.append(alert)
        
        # Attempt recovery if error count is high
        if self.error_count > 5:
            self._attempt_recovery(component)
    
    def _attempt_recovery(self, component: str):
        """Attempt to recover from component errors."""
        self.recovery_attempts += 1
        self.logger.info(f"Attempting recovery for component: {component} (attempt {self.recovery_attempts})")
        
        # Mock recovery procedures
        if component == "data_processing":
            # Restart data processing
            self.market_data_status = MarketDataStatus.RECONNECTING
        elif component == "signal_execution":
            # Clear signal queue if it's backing up
            if self.signal_queue.qsize() > 50:
                self.signal_queue.queue.clear()
        
        # Reset error count after recovery attempt
        if self.recovery_attempts % 3 == 0:
            self.error_count = 0
    
    def _generate_daily_report(self) -> str:
        """Generate comprehensive daily operations report."""
        report_data = {
            "report_date": datetime.now().date().isoformat(),
            "operation_summary": {
                "start_time": self.start_time.isoformat() if self.start_time else None,
                "uptime_hours": (datetime.now() - self.start_time).total_seconds() / 3600 if self.start_time else 0,
                "operation_status": self.operation_status.value,
                "total_errors": self.error_count,
                "recovery_attempts": self.recovery_attempts
            },
            "performance_metrics": {
                "market_data_processed": len(self.monitoring_data),
                "signals_executed": len(self.execution_results),
                "successful_executions": len([r for r in self.execution_results if r.status == "executed"]),
                "avg_processing_latency_ms": sum(self.latency_metrics) / len(self.latency_metrics) if self.latency_metrics else 0.0,
                "max_processing_latency_ms": max(self.latency_metrics) if self.latency_metrics else 0.0
            },
            "system_health": self.get_system_health().__dict__,
            "alerts_summary": {
                "total_alerts": len(self.alerts_generated),
                "critical_alerts": len([a for a in self.alerts_generated if a.level == AlertLevel.CRITICAL]),
                "warning_alerts": len([a for a in self.alerts_generated if a.level == AlertLevel.WARNING])
            },
            "component_status": self.component_status,
            "recommendations": self._generate_recommendations()
        }
        
        # Save report
        report_path = f"reports/daily_operations_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        Path(report_path).parent.mkdir(parents=True, exist_ok=True)
        
        with open(report_path, 'w') as f:
            json.dump(report_data, f, indent=2, default=str)
        
        self.logger.info(f"Daily report generated: {report_path}")
        return report_path
    
    def _generate_recommendations(self) -> List[str]:
        """Generate operational recommendations based on current metrics."""
        recommendations = []
        
        # Check error rate
        if self.error_count > 10:
            recommendations.append("High error count detected - consider system maintenance")
        
        # Check latency
        if self.latency_metrics and max(self.latency_metrics[-100:]) > self.config.max_processing_latency_ms * 2:
            recommendations.append("High processing latency detected - consider performance optimization")
        
        # Check queue sizes
        if self.market_data_queue.qsize() > 500:
            recommendations.append("Market data queue backing up - consider increasing processing capacity")
        
        # Check component health
        failed_components = [comp for comp, status in self.component_status.items() if not status]
        if failed_components:
            recommendations.append(f"Failed components detected: {failed_components} - investigate and repair")
        
        if not recommendations:
            recommendations.append("System operating normally - no immediate actions required")
        
        return recommendations
    
    def _get_startup_metrics(self) -> Dict[str, float]:
        """Get metrics for startup operation."""
        return {
            "components_validated": len(self.component_status),
            "validation_success_rate": sum(self.component_status.values()) / len(self.component_status) if self.component_status else 0.0,
            "startup_time_seconds": (datetime.now() - self.start_time).total_seconds() if self.start_time else 0.0
        }
    
    def _get_shutdown_metrics(self) -> Dict[str, float]:
        """Get metrics for shutdown operation."""
        return {
            "total_uptime_hours": (datetime.now() - self.start_time).total_seconds() / 3600 if self.start_time else 0.0,
            "total_data_processed": len(self.monitoring_data),
            "total_signals_executed": len(self.execution_results),
            "final_error_count": self.error_count,
            "alerts_generated": len(self.alerts_generated)
        }