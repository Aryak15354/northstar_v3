"""
Operation Controller - Central orchestrator for all Northstar V3 system operations.

This module provides the main entry point for running comprehensive system
validation, crisis testing, alpha validation, and live operations.
"""

import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path

from .base_types import (
    OperationResult, OperationStatus, OperationConfig,
    CrisisValidationResult, AlphaValidationResult, SystemHealthStatus,
    Alert, AlertLevel, HealthStatus
)
from .logging_config import setup_operation_logging
from .report_manager import ReportManager


class OperationController:
    """
    Central orchestrator for all system operations.
    
    Coordinates crisis validation, alpha testing, backtesting, monitoring,
    and live operations across the entire Northstar V3 system.
    """
    
    def __init__(self, config: Optional[OperationConfig] = None):
        """Initialize the operation controller."""
        self.config = config or OperationConfig()
        self.logger = setup_operation_logging()
        self.report_manager = ReportManager(self.config.reporting_config)
        
        # Operation tracking
        self.active_operations: Dict[str, OperationResult] = {}
        self.operation_history: List[OperationResult] = []
        
        # System state
        self.system_health = SystemHealthStatus(
            timestamp=datetime.now(),
            overall_health=HealthStatus.HEALTHY
        )
        
        self.logger.info("Operation Controller initialized")
        self.logger.info(f"Configuration: {len(self.config.crisis_periods)} crisis periods, "
                        f"{len(self.config.validation_scenarios)} validation scenarios")
    
    def run_comprehensive_validation(self) -> OperationResult:
        """
        Execute full system validation suite.
        
        This runs all validation scenarios including crisis testing,
        alpha validation, stress testing, and integration testing.
        
        Returns:
            OperationResult: Comprehensive validation results
        """
        operation_id = str(uuid.uuid4())
        operation = OperationResult(
            operation_id=operation_id,
            operation_type="comprehensive_validation",
            start_time=datetime.now(),
            status=OperationStatus.IN_PROGRESS
        )
        
        self.active_operations[operation_id] = operation
        self.logger.info(f"Starting comprehensive validation: {operation_id}")
        
        try:
            # Run all validation components
            validation_results = {}
            
            # 1. Crisis validation
            self.logger.info("Running crisis validation scenarios...")
            crisis_results = self._run_all_crisis_scenarios()
            validation_results["crisis_validation"] = all(
                result.stress_test_passed for result in crisis_results
            )
            
            # 2. Alpha validation
            self.logger.info("Running alpha validation scenarios...")
            alpha_results = self._run_all_alpha_scenarios()
            validation_results["alpha_validation"] = all(
                result.validation_passed for result in alpha_results
            )
            
            # 3. System health check
            self.logger.info("Performing system health validation...")
            health_status = self._validate_system_health()
            validation_results["system_health"] = health_status.overall_health == HealthStatus.HEALTHY
            
            # 4. Integration testing
            self.logger.info("Running integration tests...")
            integration_passed = self._run_integration_tests()
            validation_results["integration_tests"] = integration_passed
            
            # Compile results
            operation.validation_results = validation_results
            operation.performance_metrics = self._calculate_comprehensive_metrics(
                crisis_results, alpha_results, health_status
            )
            
            # Determine overall status
            all_passed = all(validation_results.values())
            operation.status = OperationStatus.SUCCESS if all_passed else OperationStatus.WARNING
            
            # Generate comprehensive report
            operation.report_path = self.report_manager.generate_comprehensive_report(
                operation, crisis_results, alpha_results, health_status
            )
            
            self.logger.info(f"Comprehensive validation completed: {operation.status.value}")
            
        except Exception as e:
            self.logger.error(f"Comprehensive validation failed: {str(e)}")
            operation.status = OperationStatus.FAILURE
            operation.diagnostic_info["error"] = str(e)
            
            # Generate failure alert
            alert = Alert(
                timestamp=datetime.now(),
                level=AlertLevel.CRITICAL,
                component="OperationController",
                message=f"Comprehensive validation failed: {str(e)}",
                details={"operation_id": operation_id, "error": str(e)}
            )
            operation.alerts_generated.append(alert)
        
        finally:
            operation.end_time = datetime.now()
            self.active_operations.pop(operation_id, None)
            self.operation_history.append(operation)
        
        return operation
    
    def run_crisis_scenarios(self, crisis_names: Optional[List[str]] = None) -> List[CrisisValidationResult]:
        """
        Execute historical crisis backtests.
        
        Args:
            crisis_names: Specific crisis periods to test. If None, tests all configured periods.
            
        Returns:
            List[CrisisValidationResult]: Results for each crisis period
        """
        operation_id = str(uuid.uuid4())
        operation = OperationResult(
            operation_id=operation_id,
            operation_type="crisis_validation",
            start_time=datetime.now(),
            status=OperationStatus.IN_PROGRESS
        )
        
        self.active_operations[operation_id] = operation
        self.logger.info(f"Starting crisis scenarios: {operation_id}")
        
        try:
            # Determine which crisis periods to test
            periods_to_test = self.config.crisis_periods
            if crisis_names:
                periods_to_test = [p for p in self.config.crisis_periods if p.name in crisis_names]
            
            results = []
            for period in periods_to_test:
                self.logger.info(f"Testing crisis period: {period.name}")
                result = self._validate_crisis_period(period)
                results.append(result)
                
                # Check if crisis validation passed thresholds
                if not result.stress_test_passed:
                    alert = Alert(
                        timestamp=datetime.now(),
                        level=AlertLevel.WARNING,
                        component="CrisisValidator",
                        message=f"Crisis validation failed for {period.name}",
                        details={
                            "period": period.name,
                            "max_drawdown": result.max_drawdown,
                            "sharpe_ratio": result.sharpe_ratio,
                            "var_breaches": result.var_breach_count
                        }
                    )
                    operation.alerts_generated.append(alert)
            
            # Calculate aggregate metrics
            operation.performance_metrics = self._calculate_crisis_aggregate_metrics(results)
            operation.validation_results = {
                period.name: result.stress_test_passed 
                for period, result in zip(periods_to_test, results)
            }
            
            operation.status = OperationStatus.SUCCESS
            self.logger.info(f"Crisis scenarios completed successfully")
            
            return results
            
        except Exception as e:
            self.logger.error(f"Crisis scenarios failed: {str(e)}")
            operation.status = OperationStatus.FAILURE
            operation.diagnostic_info["error"] = str(e)
            return []
        
        finally:
            operation.end_time = datetime.now()
            self.active_operations.pop(operation_id, None)
            self.operation_history.append(operation)
    
    def run_alpha_validation(self, regimes: Optional[List[str]] = None) -> List[AlphaValidationResult]:
        """
        Validate alpha generation across market regimes.
        
        Args:
            regimes: Specific market regimes to test. If None, tests all regimes.
            
        Returns:
            List[AlphaValidationResult]: Results for each market regime
        """
        operation_id = str(uuid.uuid4())
        operation = OperationResult(
            operation_id=operation_id,
            operation_type="alpha_validation",
            start_time=datetime.now(),
            status=OperationStatus.IN_PROGRESS
        )
        
        self.active_operations[operation_id] = operation
        self.logger.info(f"Starting alpha validation: {operation_id}")
        
        try:
            # Default regimes to test
            test_regimes = regimes or ["bull", "bear", "sideways"]
            
            results = []
            for regime in test_regimes:
                self.logger.info(f"Testing alpha generation in {regime} market")
                result = self._validate_alpha_regime(regime)
                results.append(result)
                
                # Check alpha validation results
                if not result.validation_passed:
                    alert = Alert(
                        timestamp=datetime.now(),
                        level=AlertLevel.WARNING,
                        component="AlphaValidator",
                        message=f"Alpha validation failed for {regime} market",
                        details={
                            "regime": regime,
                            "alpha_generated": result.alpha_generated,
                            "information_ratio": result.information_ratio,
                            "signal_quality": result.signal_quality_score
                        }
                    )
                    operation.alerts_generated.append(alert)
            
            # Calculate aggregate metrics
            operation.performance_metrics = self._calculate_alpha_aggregate_metrics(results)
            operation.validation_results = {
                result.regime: result.validation_passed for result in results
            }
            
            operation.status = OperationStatus.SUCCESS
            self.logger.info(f"Alpha validation completed successfully")
            
            return results
            
        except Exception as e:
            self.logger.error(f"Alpha validation failed: {str(e)}")
            operation.status = OperationStatus.FAILURE
            operation.diagnostic_info["error"] = str(e)
            return []
        
        finally:
            operation.end_time = datetime.now()
            self.active_operations.pop(operation_id, None)
            self.operation_history.append(operation)
    
    def start_live_operations(self) -> OperationResult:
        """
        Initialize live trading operations.
        
        Validates all system components and starts live monitoring.
        
        Returns:
            OperationResult: Live operation startup results
        """
        operation_id = str(uuid.uuid4())
        operation = OperationResult(
            operation_id=operation_id,
            operation_type="live_operations",
            start_time=datetime.now(),
            status=OperationStatus.IN_PROGRESS
        )
        
        self.active_operations[operation_id] = operation
        self.logger.info(f"Starting live operations: {operation_id}")
        
        try:
            # 1. Validate all system components
            self.logger.info("Validating system components for live operation...")
            component_status = self._validate_all_components()
            
            # 2. Check system health
            health_status = self._validate_system_health()
            
            # 3. Verify data feeds
            data_status = self._validate_data_feeds()
            
            # 4. Check risk management systems
            risk_status = self._validate_risk_systems()
            
            # Compile validation results
            validation_results = {
                "components": component_status,
                "health": health_status.overall_health == HealthStatus.HEALTHY,
                "data_feeds": data_status,
                "risk_systems": risk_status
            }
            
            operation.validation_results = validation_results
            
            # Determine if ready for live operations
            all_systems_ready = all(validation_results.values())
            
            if all_systems_ready:
                operation.status = OperationStatus.SUCCESS
                self.logger.info("All systems validated - ready for live operations")
                
                # Start monitoring
                if self.config.enable_real_time_monitoring:
                    self._start_real_time_monitoring()
                
            else:
                operation.status = OperationStatus.FAILURE
                failed_systems = [k for k, v in validation_results.items() if not v]
                
                alert = Alert(
                    timestamp=datetime.now(),
                    level=AlertLevel.CRITICAL,
                    component="OperationController",
                    message=f"Live operations validation failed: {failed_systems}",
                    details={"failed_systems": failed_systems}
                )
                operation.alerts_generated.append(alert)
                
                self.logger.error(f"Live operations validation failed: {failed_systems}")
            
        except Exception as e:
            self.logger.error(f"Live operations startup failed: {str(e)}")
            operation.status = OperationStatus.FAILURE
            operation.diagnostic_info["error"] = str(e)
        
        finally:
            operation.end_time = datetime.now()
            self.active_operations.pop(operation_id, None)
            self.operation_history.append(operation)
        
        return operation
    
    def generate_system_report(self, report_type: str = "comprehensive") -> str:
        """
        Generate comprehensive system reports.
        
        Args:
            report_type: Type of report to generate
            
        Returns:
            str: Path to generated report
        """
        self.logger.info(f"Generating {report_type} system report")
        
        try:
            # Collect current system status
            health_status = self._validate_system_health()
            recent_operations = self.operation_history[-10:]  # Last 10 operations
            
            # Generate report
            report_path = self.report_manager.generate_system_report(
                report_type=report_type,
                health_status=health_status,
                recent_operations=recent_operations,
                active_operations=list(self.active_operations.values())
            )
            
            self.logger.info(f"System report generated: {report_path}")
            return report_path
            
        except Exception as e:
            self.logger.error(f"Report generation failed: {str(e)}")
            raise
    
    def get_system_status(self) -> SystemHealthStatus:
        """Get current system health status."""
        return self._validate_system_health()
    
    def get_active_operations(self) -> List[OperationResult]:
        """Get list of currently active operations."""
        return list(self.active_operations.values())
    
    def get_operation_history(self, limit: int = 50) -> List[OperationResult]:
        """Get recent operation history."""
        return self.operation_history[-limit:]
    
    # Private helper methods
    
    def _run_all_crisis_scenarios(self) -> List[CrisisValidationResult]:
        """Run all configured crisis scenarios."""
        # This would integrate with the Crisis Validator component
        # For now, return mock results
        results = []
        for period in self.config.crisis_periods:
            result = self._validate_crisis_period(period)
            results.append(result)
        return results
    
    def _run_all_alpha_scenarios(self) -> List[AlphaValidationResult]:
        """Run all alpha validation scenarios."""
        # This would integrate with the Alpha Validator component
        # For now, return mock results
        regimes = ["bull", "bear", "sideways"]
        results = []
        for regime in regimes:
            result = self._validate_alpha_regime(regime)
            results.append(result)
        return results
    
    def _validate_crisis_period(self, period) -> CrisisValidationResult:
        """Validate system performance during a crisis period."""
        # Mock implementation - would integrate with actual crisis validator
        return CrisisValidationResult(
            crisis_period=period.name,
            start_date=period.start_date,
            end_date=period.end_date,
            total_return=-0.05,  # Mock 5% loss during crisis
            max_drawdown=0.12,   # Mock 12% max drawdown
            volatility=0.25,     # Mock 25% volatility
            sharpe_ratio=0.3,    # Mock Sharpe ratio
            var_breach_count=2,  # Mock VaR breaches
            stress_test_passed=True  # Mock passing result
        )
    
    def _validate_alpha_regime(self, regime: str) -> AlphaValidationResult:
        """Validate alpha generation in a specific market regime."""
        # Mock implementation - would integrate with actual alpha validator
        return AlphaValidationResult(
            regime=regime,
            period_start=datetime(2020, 1, 1),
            period_end=datetime(2023, 12, 31),
            alpha_generated=0.03,  # Mock 3% alpha
            information_ratio=0.8,  # Mock IR
            hit_rate=0.55,         # Mock 55% hit rate
            signal_quality_score=0.7,  # Mock signal quality
            consistency_score=0.8,     # Mock consistency
            regime_adaptation_score=0.75,  # Mock adaptation
            validation_passed=True
        )
    
    def _validate_system_health(self) -> SystemHealthStatus:
        """Validate current system health."""
        # Mock implementation - would integrate with actual health monitoring
        return SystemHealthStatus(
            timestamp=datetime.now(),
            overall_health=HealthStatus.HEALTHY,
            component_status={
                "data_pipeline": "healthy",
                "intelligence_engines": "healthy", 
                "risk_management": "healthy",
                "portfolio_management": "healthy"
            },
            performance_score=0.85,
            data_quality_score=0.92,
            latency_metrics={"avg_latency_ms": 45.2},
            error_counts={"total_errors": 0}
        )
    
    def _run_integration_tests(self) -> bool:
        """Run integration tests across all components."""
        # Mock implementation - would run actual integration tests
        return True
    
    def _validate_all_components(self) -> bool:
        """Validate all system components are operational."""
        # Mock implementation - would check actual components
        return True
    
    def _validate_data_feeds(self) -> bool:
        """Validate data feed connectivity and quality."""
        # Mock implementation - would check actual data feeds
        return True
    
    def _validate_risk_systems(self) -> bool:
        """Validate risk management systems."""
        # Mock implementation - would check actual risk systems
        return True
    
    def _start_real_time_monitoring(self):
        """Start real-time system monitoring."""
        # Mock implementation - would start actual monitoring
        self.logger.info("Real-time monitoring started")
    
    def _calculate_comprehensive_metrics(self, crisis_results, alpha_results, health_status) -> Dict[str, float]:
        """Calculate aggregate metrics for comprehensive validation."""
        return {
            "crisis_pass_rate": sum(r.stress_test_passed for r in crisis_results) / len(crisis_results),
            "alpha_pass_rate": sum(r.validation_passed for r in alpha_results) / len(alpha_results),
            "avg_sharpe_ratio": sum(r.sharpe_ratio for r in crisis_results) / len(crisis_results),
            "system_health_score": health_status.performance_score,
            "overall_score": 0.85  # Mock overall score
        }
    
    def _calculate_crisis_aggregate_metrics(self, results) -> Dict[str, float]:
        """Calculate aggregate metrics for crisis validation."""
        if not results:
            return {}
        
        return {
            "avg_total_return": sum(r.total_return for r in results) / len(results),
            "avg_max_drawdown": sum(r.max_drawdown for r in results) / len(results),
            "avg_volatility": sum(r.volatility for r in results) / len(results),
            "avg_sharpe_ratio": sum(r.sharpe_ratio for r in results) / len(results),
            "total_var_breaches": sum(r.var_breach_count for r in results),
            "pass_rate": sum(r.stress_test_passed for r in results) / len(results)
        }
    
    def _calculate_alpha_aggregate_metrics(self, results) -> Dict[str, float]:
        """Calculate aggregate metrics for alpha validation."""
        if not results:
            return {}
        
        return {
            "avg_alpha_generated": sum(r.alpha_generated for r in results) / len(results),
            "avg_information_ratio": sum(r.information_ratio for r in results) / len(results),
            "avg_hit_rate": sum(r.hit_rate for r in results) / len(results),
            "avg_signal_quality": sum(r.signal_quality_score for r in results) / len(results),
            "avg_consistency": sum(r.consistency_score for r in results) / len(results),
            "pass_rate": sum(r.validation_passed for r in results) / len(results)
        }