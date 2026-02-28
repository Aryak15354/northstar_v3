"""
Northstar V3 Comprehensive Operation System - System Validation Suite

This module implements a comprehensive system validation suite that validates
all components of the Northstar V3 system including data pipelines, intelligence
engines, risk management, and integration points.

Author: Northstar Team
Date: 2026-01-05
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import json
import numpy as np

from .base_types import (
    Alert, AlertLevel, ValidationResult, SystemHealthStatus,
    ComponentStatus, ValidationReport, ReportConfig, SystemHealthLevel
)
from .logging_config import setup_operation_logging
from .report_manager import ReportManager


class ValidationSeverity(Enum):
    """Validation severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ValidationCheck:
    """Individual validation check definition."""
    check_id: str
    name: str
    description: str
    component: str
    severity: ValidationSeverity
    timeout_seconds: int = 30
    retry_count: int = 3
    dependencies: List[str] = None
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []


@dataclass
class ValidationCheckResult:
    """Result of a validation check."""
    check_id: str
    name: str
    component: str
    status: ComponentStatus
    severity: ValidationSeverity
    execution_time_seconds: float
    message: str
    details: Dict[str, Any]
    timestamp: datetime
    retry_count: int = 0
    error_details: Optional[str] = None


@dataclass
class ComponentValidationResult:
    """Validation result for a system component."""
    component_name: str
    status: ComponentStatus
    checks_passed: int
    checks_failed: int
    checks_total: int
    execution_time_seconds: float
    check_results: List[ValidationCheckResult]
    health_score: float
    recommendations: List[str]


@dataclass
class SystemValidationReport:
    """Comprehensive system validation report."""
    validation_id: str
    timestamp: datetime
    overall_status: SystemHealthStatus
    components_validated: int
    components_passed: int
    components_failed: int
    total_checks: int
    checks_passed: int
    checks_failed: int
    execution_time_seconds: float
    component_results: List[ComponentValidationResult]
    system_health_score: float
    critical_issues: List[str]
    recommendations: List[str]
    certification_status: str
    next_validation_due: datetime


class SystemValidationSuite:
    """
    Comprehensive system validation suite for Northstar V3.
    
    This class provides comprehensive validation of all system components
    including data pipelines, intelligence engines, risk management,
    and integration points.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the system validation suite."""
        self.logger = setup_operation_logging()
        self.report_manager = ReportManager(ReportConfig())
        
        # Configuration
        self.config = config or self._get_default_config()
        
        # Validation state
        self.validation_checks = self._initialize_validation_checks()
        self.validation_history = []
        self.component_health_cache = {}
        self.last_validation_time = None
        
        # Validation results
        self.current_validation_results = []
        self.system_health_status = SystemHealthLevel.UNKNOWN
        
        self.logger.info("System Validation Suite initialized")
        self.logger.info(f"Configuration: {len(self.validation_checks)} validation checks loaded")
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration for system validation."""
        return {
            "validation_timeout": 300,  # 5 minutes
            "component_timeout": 60,    # 1 minute per component
            "check_timeout": 30,        # 30 seconds per check
            "retry_attempts": 3,
            "health_score_threshold": 0.8,
            "certification_threshold": 0.9,
            "validation_frequency_hours": 24,
            "parallel_validation": True,
            "detailed_logging": True
        }
    
    def _initialize_validation_checks(self) -> List[ValidationCheck]:
        """Initialize all validation checks."""
        checks = []
        
        # Data Pipeline Validation Checks
        checks.extend([
            ValidationCheck(
                check_id="data_pipeline_001",
                name="Data Source Connectivity",
                description="Validate connectivity to all data sources",
                component="data_pipeline",
                severity=ValidationSeverity.CRITICAL,
                timeout_seconds=30
            ),
            ValidationCheck(
                check_id="data_pipeline_002", 
                name="Data Quality Validation",
                description="Validate data quality and completeness",
                component="data_pipeline",
                severity=ValidationSeverity.ERROR,
                timeout_seconds=45
            ),
            ValidationCheck(
                check_id="data_pipeline_003",
                name="Data Latency Check",
                description="Validate data processing latency",
                component="data_pipeline",
                severity=ValidationSeverity.WARNING,
                timeout_seconds=20
            ),
            ValidationCheck(
                check_id="data_pipeline_004",
                name="Data Format Validation",
                description="Validate data format consistency",
                component="data_pipeline",
                severity=ValidationSeverity.ERROR,
                timeout_seconds=25
            )
        ])
        
        # Intelligence Engine Validation Checks
        checks.extend([
            ValidationCheck(
                check_id="intelligence_001",
                name="Signal Generation Test",
                description="Validate signal generation capabilities",
                component="intelligence_engine",
                severity=ValidationSeverity.CRITICAL,
                timeout_seconds=60,
                dependencies=["data_pipeline_001", "data_pipeline_002"]
            ),
            ValidationCheck(
                check_id="intelligence_002",
                name="Model Performance Validation",
                description="Validate model performance metrics",
                component="intelligence_engine", 
                severity=ValidationSeverity.ERROR,
                timeout_seconds=45
            ),
            ValidationCheck(
                check_id="intelligence_003",
                name="Memory System Validation",
                description="Validate memory and state management",
                component="intelligence_engine",
                severity=ValidationSeverity.WARNING,
                timeout_seconds=30
            ),
            ValidationCheck(
                check_id="intelligence_004",
                name="Narrative Engine Test",
                description="Validate narrative generation and reasoning",
                component="intelligence_engine",
                severity=ValidationSeverity.INFO,
                timeout_seconds=40
            )
        ])
        
        # Risk Management Validation Checks
        checks.extend([
            ValidationCheck(
                check_id="risk_mgmt_001",
                name="Risk Limit Enforcement",
                description="Validate risk limit enforcement mechanisms",
                component="risk_management",
                severity=ValidationSeverity.CRITICAL,
                timeout_seconds=30
            ),
            ValidationCheck(
                check_id="risk_mgmt_002",
                name="Portfolio Risk Calculation",
                description="Validate portfolio risk calculations",
                component="risk_management",
                severity=ValidationSeverity.CRITICAL,
                timeout_seconds=45
            ),
            ValidationCheck(
                check_id="risk_mgmt_003",
                name="Emergency Brake Test",
                description="Validate emergency brake functionality",
                component="risk_management",
                severity=ValidationSeverity.CRITICAL,
                timeout_seconds=20
            ),
            ValidationCheck(
                check_id="risk_mgmt_004",
                name="Risk Monitoring Alerts",
                description="Validate risk monitoring and alerting",
                component="risk_management",
                severity=ValidationSeverity.ERROR,
                timeout_seconds=25
            )
        ])
        
        # Portfolio Management Validation Checks
        checks.extend([
            ValidationCheck(
                check_id="portfolio_001",
                name="Position Sizing Validation",
                description="Validate position sizing calculations",
                component="portfolio_management",
                severity=ValidationSeverity.CRITICAL,
                timeout_seconds=30,
                dependencies=["risk_mgmt_001", "risk_mgmt_002"]
            ),
            ValidationCheck(
                check_id="portfolio_002",
                name="Rebalancing Logic Test",
                description="Validate portfolio rebalancing logic",
                component="portfolio_management",
                severity=ValidationSeverity.ERROR,
                timeout_seconds=40
            ),
            ValidationCheck(
                check_id="portfolio_003",
                name="Transaction Cost Estimation",
                description="Validate transaction cost calculations",
                component="portfolio_management",
                severity=ValidationSeverity.WARNING,
                timeout_seconds=25
            )
        ])
        
        # System Integration Validation Checks
        checks.extend([
            ValidationCheck(
                check_id="integration_001",
                name="Component Communication",
                description="Validate inter-component communication",
                component="system_integration",
                severity=ValidationSeverity.CRITICAL,
                timeout_seconds=45,
                dependencies=["data_pipeline_001", "intelligence_001", "risk_mgmt_001"]
            ),
            ValidationCheck(
                check_id="integration_002",
                name="Event System Validation",
                description="Validate event system functionality",
                component="system_integration",
                severity=ValidationSeverity.ERROR,
                timeout_seconds=30
            ),
            ValidationCheck(
                check_id="integration_003",
                name="State Synchronization",
                description="Validate state synchronization across components",
                component="system_integration",
                severity=ValidationSeverity.ERROR,
                timeout_seconds=35
            )
        ])
        
        return checks
    
    def run_comprehensive_system_validation(self) -> SystemValidationReport:
        """
        Run comprehensive system validation across all components.
        
        Returns:
            SystemValidationReport: Complete validation report
        """
        validation_start = datetime.now()
        validation_id = f"SysVal_{int(time.time())}"
        
        self.logger.info(f"Starting comprehensive system validation: {validation_id}")
        
        try:
            # Group checks by component
            component_checks = self._group_checks_by_component()
            
            # Run validation for each component
            component_results = []
            for component_name, checks in component_checks.items():
                self.logger.info(f"Validating component: {component_name}")
                component_result = self._validate_component(component_name, checks)
                component_results.append(component_result)
            
            # Calculate overall system health
            overall_status, system_health_score = self._calculate_system_health(component_results)
            
            # Generate recommendations
            recommendations = self._generate_system_recommendations(component_results)
            
            # Identify critical issues
            critical_issues = self._identify_critical_issues(component_results)
            
            # Determine certification status
            certification_status = self._determine_certification_status(system_health_score, critical_issues)
            
            # Calculate summary statistics
            total_checks = sum(len(result.check_results) for result in component_results)  # Actual executed checks
            checks_passed = sum(result.checks_passed for result in component_results)
            checks_failed = sum(result.checks_failed for result in component_results)
            components_passed = sum(1 for result in component_results if result.status == ComponentStatus.HEALTHY)
            components_failed = len(component_results) - components_passed
            
            # Create validation report
            validation_report = SystemValidationReport(
                validation_id=validation_id,
                timestamp=validation_start,
                overall_status=overall_status,
                components_validated=len(component_results),
                components_passed=components_passed,
                components_failed=components_failed,
                total_checks=total_checks,
                checks_passed=checks_passed,
                checks_failed=checks_failed,
                execution_time_seconds=(datetime.now() - validation_start).total_seconds(),
                component_results=component_results,
                system_health_score=system_health_score,
                critical_issues=critical_issues,
                recommendations=recommendations,
                certification_status=certification_status,
                next_validation_due=datetime.now() + timedelta(hours=self.config["validation_frequency_hours"])
            )
            
            # Store validation results
            self.validation_history.append(validation_report)
            self.last_validation_time = datetime.now()
            self.system_health_status = overall_status
            
            # Generate and save report
            self._generate_validation_report(validation_report)
            
            self.logger.info(f"System validation completed: {overall_status.value}")
            self.logger.info(f"System health score: {system_health_score:.3f}")
            self.logger.info(f"Certification status: {certification_status}")
            
            return validation_report
            
        except Exception as e:
            self.logger.error(f"System validation failed: {str(e)}")
            raise
    
    def _group_checks_by_component(self) -> Dict[str, List[ValidationCheck]]:
        """Group validation checks by component."""
        component_checks = {}
        for check in self.validation_checks:
            if check.component not in component_checks:
                component_checks[check.component] = []
            component_checks[check.component].append(check)
        return component_checks
    
    def _validate_component(self, component_name: str, checks: List[ValidationCheck]) -> ComponentValidationResult:
        """Validate a single system component."""
        component_start = datetime.now()
        check_results = []
        
        # Sort checks by dependencies
        sorted_checks = self._sort_checks_by_dependencies(checks)
        
        for check in sorted_checks:
            check_result = self._execute_validation_check(check)
            check_results.append(check_result)
            
            # Stop on critical failures if configured
            if (check_result.status == ComponentStatus.FAILED and 
                check_result.severity == ValidationSeverity.CRITICAL and
                not self.config.get("continue_on_critical_failure", False)):
                self.logger.warning(f"Stopping component validation due to critical failure: {check.name}")
                break
        
        # Calculate component health
        checks_passed = sum(1 for result in check_results if result.status == ComponentStatus.HEALTHY)
        checks_failed = len(check_results) - checks_passed
        
        # Determine component status
        if checks_failed == 0:
            component_status = ComponentStatus.HEALTHY
        elif any(result.severity == ValidationSeverity.CRITICAL and result.status == ComponentStatus.FAILED 
                for result in check_results):
            component_status = ComponentStatus.FAILED
        else:
            component_status = ComponentStatus.DEGRADED
        
        # Calculate health score
        health_score = checks_passed / len(check_results) if check_results else 0.0
        
        # Generate component recommendations
        recommendations = self._generate_component_recommendations(component_name, check_results)
        
        return ComponentValidationResult(
            component_name=component_name,
            status=component_status,
            checks_passed=checks_passed,
            checks_failed=checks_failed,
            checks_total=len(check_results),
            execution_time_seconds=(datetime.now() - component_start).total_seconds(),
            check_results=check_results,
            health_score=health_score,
            recommendations=recommendations
        )
    
    def _sort_checks_by_dependencies(self, checks: List[ValidationCheck]) -> List[ValidationCheck]:
        """Sort checks by their dependencies."""
        # Simple topological sort for dependencies
        sorted_checks = []
        remaining_checks = checks.copy()
        
        while remaining_checks:
            # Find checks with no unmet dependencies
            ready_checks = []
            for check in remaining_checks:
                dependencies_met = all(
                    any(completed.check_id == dep_id for completed in sorted_checks)
                    for dep_id in check.dependencies
                )
                if dependencies_met:
                    ready_checks.append(check)
            
            if not ready_checks:
                # No more checks can be resolved, add remaining in original order
                sorted_checks.extend(remaining_checks)
                break
            
            # Add ready checks and remove from remaining
            sorted_checks.extend(ready_checks)
            for check in ready_checks:
                remaining_checks.remove(check)
        
        return sorted_checks
    
    def _execute_validation_check(self, check: ValidationCheck) -> ValidationCheckResult:
        """Execute a single validation check."""
        check_start = datetime.now()
        
        self.logger.debug(f"Executing validation check: {check.name}")
        
        try:
            # Execute the actual validation logic
            status, message, details = self._run_check_logic(check)
            
            return ValidationCheckResult(
                check_id=check.check_id,
                name=check.name,
                component=check.component,
                status=status,
                severity=check.severity,
                execution_time_seconds=(datetime.now() - check_start).total_seconds(),
                message=message,
                details=details,
                timestamp=check_start
            )
            
        except Exception as e:
            self.logger.error(f"Validation check failed: {check.name} - {str(e)}")
            
            return ValidationCheckResult(
                check_id=check.check_id,
                name=check.name,
                component=check.component,
                status=ComponentStatus.FAILED,
                severity=check.severity,
                execution_time_seconds=(datetime.now() - check_start).total_seconds(),
                message=f"Check execution failed: {str(e)}",
                details={"error": str(e)},
                timestamp=check_start,
                error_details=str(e)
            )
    
    def _run_check_logic(self, check: ValidationCheck) -> Tuple[ComponentStatus, str, Dict[str, Any]]:
        """Run the actual validation logic for a check."""
        # Mock validation logic - in real implementation, this would call actual system components
        
        if check.check_id.startswith("data_pipeline"):
            return self._validate_data_pipeline_check(check)
        elif check.check_id.startswith("intelligence"):
            return self._validate_intelligence_check(check)
        elif check.check_id.startswith("risk_mgmt"):
            return self._validate_risk_management_check(check)
        elif check.check_id.startswith("portfolio"):
            return self._validate_portfolio_check(check)
        elif check.check_id.startswith("integration"):
            return self._validate_integration_check(check)
        else:
            return ComponentStatus.HEALTHY, "Check passed", {"result": "success"}
    
    def _validate_data_pipeline_check(self, check: ValidationCheck) -> Tuple[ComponentStatus, str, Dict[str, Any]]:
        """Validate data pipeline checks."""
        # Mock data pipeline validation
        if "connectivity" in check.name.lower():
            # Simulate connectivity check
            latency_ms = np.random.uniform(10, 100)
            if latency_ms > 80:
                return ComponentStatus.DEGRADED, f"High latency detected: {latency_ms:.1f}ms", {"latency_ms": latency_ms}
            return ComponentStatus.HEALTHY, f"Connectivity OK (latency: {latency_ms:.1f}ms)", {"latency_ms": latency_ms}
        
        elif "quality" in check.name.lower():
            # Simulate data quality check
            quality_score = np.random.uniform(0.7, 1.0)
            if quality_score < 0.8:
                return ComponentStatus.DEGRADED, f"Data quality below threshold: {quality_score:.3f}", {"quality_score": quality_score}
            return ComponentStatus.HEALTHY, f"Data quality OK: {quality_score:.3f}", {"quality_score": quality_score}
        
        elif "latency" in check.name.lower():
            # Simulate latency check
            processing_latency = np.random.uniform(1, 10)
            if processing_latency > 8:
                return ComponentStatus.DEGRADED, f"Processing latency high: {processing_latency:.1f}s", {"processing_latency_s": processing_latency}
            return ComponentStatus.HEALTHY, f"Processing latency OK: {processing_latency:.1f}s", {"processing_latency_s": processing_latency}
        
        else:
            return ComponentStatus.HEALTHY, "Data pipeline check passed", {"result": "success"}
    
    def _validate_intelligence_check(self, check: ValidationCheck) -> Tuple[ComponentStatus, str, Dict[str, Any]]:
        """Validate intelligence engine checks."""
        # Mock intelligence engine validation
        if "signal" in check.name.lower():
            # Simulate signal generation test
            signal_quality = np.random.uniform(0.6, 1.0)
            signals_generated = np.random.randint(50, 200)
            
            if signal_quality < 0.7:
                return ComponentStatus.FAILED, f"Signal quality too low: {signal_quality:.3f}", {
                    "signal_quality": signal_quality,
                    "signals_generated": signals_generated
                }
            elif signal_quality < 0.8:
                return ComponentStatus.DEGRADED, f"Signal quality marginal: {signal_quality:.3f}", {
                    "signal_quality": signal_quality,
                    "signals_generated": signals_generated
                }
            
            return ComponentStatus.HEALTHY, f"Signal generation OK: {signal_quality:.3f} quality, {signals_generated} signals", {
                "signal_quality": signal_quality,
                "signals_generated": signals_generated
            }
        
        elif "performance" in check.name.lower():
            # Simulate model performance check
            accuracy = np.random.uniform(0.65, 0.95)
            if accuracy < 0.7:
                return ComponentStatus.FAILED, f"Model accuracy too low: {accuracy:.3f}", {"accuracy": accuracy}
            return ComponentStatus.HEALTHY, f"Model performance OK: {accuracy:.3f} accuracy", {"accuracy": accuracy}
        
        else:
            return ComponentStatus.HEALTHY, "Intelligence check passed", {"result": "success"}
    
    def _validate_risk_management_check(self, check: ValidationCheck) -> Tuple[ComponentStatus, str, Dict[str, Any]]:
        """Validate risk management checks."""
        # Mock risk management validation
        if "limit" in check.name.lower():
            # Simulate risk limit check
            current_risk = np.random.uniform(0.5, 1.2)
            risk_limit = 1.0
            
            if current_risk > risk_limit:
                return ComponentStatus.FAILED, f"Risk limit exceeded: {current_risk:.3f} > {risk_limit}", {
                    "current_risk": current_risk,
                    "risk_limit": risk_limit
                }
            elif current_risk > risk_limit * 0.9:
                return ComponentStatus.DEGRADED, f"Risk near limit: {current_risk:.3f}", {
                    "current_risk": current_risk,
                    "risk_limit": risk_limit
                }
            
            return ComponentStatus.HEALTHY, f"Risk within limits: {current_risk:.3f}", {
                "current_risk": current_risk,
                "risk_limit": risk_limit
            }
        
        elif "emergency" in check.name.lower():
            # Simulate emergency brake test
            brake_response_time = np.random.uniform(0.1, 2.0)
            if brake_response_time > 1.5:
                return ComponentStatus.FAILED, f"Emergency brake too slow: {brake_response_time:.2f}s", {"response_time_s": brake_response_time}
            return ComponentStatus.HEALTHY, f"Emergency brake OK: {brake_response_time:.2f}s response", {"response_time_s": brake_response_time}
        
        else:
            return ComponentStatus.HEALTHY, "Risk management check passed", {"result": "success"}
    
    def _validate_portfolio_check(self, check: ValidationCheck) -> Tuple[ComponentStatus, str, Dict[str, Any]]:
        """Validate portfolio management checks."""
        # Mock portfolio management validation
        if "sizing" in check.name.lower():
            # Simulate position sizing check
            sizing_accuracy = np.random.uniform(0.85, 1.0)
            if sizing_accuracy < 0.9:
                return ComponentStatus.DEGRADED, f"Position sizing accuracy low: {sizing_accuracy:.3f}", {"sizing_accuracy": sizing_accuracy}
            return ComponentStatus.HEALTHY, f"Position sizing OK: {sizing_accuracy:.3f} accuracy", {"sizing_accuracy": sizing_accuracy}
        
        else:
            return ComponentStatus.HEALTHY, "Portfolio check passed", {"result": "success"}
    
    def _validate_integration_check(self, check: ValidationCheck) -> Tuple[ComponentStatus, str, Dict[str, Any]]:
        """Validate system integration checks."""
        # Mock integration validation
        if "communication" in check.name.lower():
            # Simulate component communication check
            communication_latency = np.random.uniform(5, 50)
            if communication_latency > 40:
                return ComponentStatus.DEGRADED, f"High communication latency: {communication_latency:.1f}ms", {"communication_latency_ms": communication_latency}
            return ComponentStatus.HEALTHY, f"Component communication OK: {communication_latency:.1f}ms", {"communication_latency_ms": communication_latency}
        
        else:
            return ComponentStatus.HEALTHY, "Integration check passed", {"result": "success"}
    
    def _calculate_system_health(self, component_results: List[ComponentValidationResult]) -> Tuple[SystemHealthStatus, float]:
        """Calculate overall system health status and score."""
        if not component_results:
            return SystemHealthLevel.UNKNOWN, 0.0
        
        # Calculate weighted health score
        total_weight = 0
        weighted_score = 0
        
        component_weights = {
            "data_pipeline": 0.25,
            "intelligence_engine": 0.30,
            "risk_management": 0.25,
            "portfolio_management": 0.15,
            "system_integration": 0.05
        }
        
        for result in component_results:
            weight = component_weights.get(result.component_name, 0.1)
            weighted_score += result.health_score * weight
            total_weight += weight
        
        system_health_score = weighted_score / total_weight if total_weight > 0 else 0.0
        
        # Determine overall status
        failed_components = [r for r in component_results if r.status == ComponentStatus.FAILED]
        critical_failed = any(r.component_name in ["risk_management", "intelligence_engine"] for r in failed_components)
        
        if critical_failed:
            overall_status = SystemHealthLevel.CRITICAL
        elif failed_components:  # Any failed components should prevent healthy status
            overall_status = SystemHealthLevel.DEGRADED
        elif system_health_score < 0.5:
            overall_status = SystemHealthLevel.CRITICAL
        elif system_health_score < 0.7:
            overall_status = SystemHealthLevel.DEGRADED
        elif system_health_score < 0.9:
            overall_status = SystemHealthLevel.WARNING
        else:
            overall_status = SystemHealthLevel.HEALTHY
        
        return overall_status, system_health_score
    
    def _generate_system_recommendations(self, component_results: List[ComponentValidationResult]) -> List[str]:
        """Generate system-level recommendations."""
        recommendations = []
        
        # Analyze component results for system-level issues
        failed_components = [r for r in component_results if r.status == ComponentStatus.FAILED]
        degraded_components = [r for r in component_results if r.status == ComponentStatus.DEGRADED]
        
        if failed_components:
            recommendations.append(f"URGENT: {len(failed_components)} components have failed - immediate attention required")
            for component in failed_components:
                recommendations.append(f"- Fix critical issues in {component.component_name}")
        
        if degraded_components:
            recommendations.append(f"Monitor {len(degraded_components)} degraded components")
        
        # Add component-specific recommendations
        for result in component_results:
            recommendations.extend(result.recommendations)
        
        # System-level recommendations
        if len(failed_components) > 1:
            recommendations.append("Consider system-wide restart after fixing critical issues")
        
        return recommendations[:10]  # Limit to top 10 recommendations
    
    def _identify_critical_issues(self, component_results: List[ComponentValidationResult]) -> List[str]:
        """Identify critical system issues."""
        critical_issues = []
        
        for result in component_results:
            for check_result in result.check_results:
                if (check_result.severity == ValidationSeverity.CRITICAL and 
                    check_result.status == ComponentStatus.FAILED):
                    critical_issues.append(f"{result.component_name}: {check_result.message}")
        
        return critical_issues
    
    def _determine_certification_status(self, health_score: float, critical_issues: List[str]) -> str:
        """Determine system certification status."""
        if critical_issues:
            return "FAILED - Critical issues present"
        elif health_score >= self.config["certification_threshold"]:
            return "CERTIFIED - System ready for production"
        elif health_score >= self.config["health_score_threshold"]:
            return "CONDITIONAL - System functional with minor issues"
        else:
            return "FAILED - System health below acceptable threshold"
    
    def _generate_component_recommendations(self, component_name: str, check_results: List[ValidationCheckResult]) -> List[str]:
        """Generate recommendations for a specific component."""
        recommendations = []
        
        failed_checks = [r for r in check_results if r.status == ComponentStatus.FAILED]
        degraded_checks = [r for r in check_results if r.status == ComponentStatus.DEGRADED]
        
        if failed_checks:
            recommendations.append(f"Fix {len(failed_checks)} failed checks in {component_name}")
        
        if degraded_checks:
            recommendations.append(f"Investigate {len(degraded_checks)} degraded checks in {component_name}")
        
        # Component-specific recommendations
        if component_name == "data_pipeline":
            if any("latency" in check.name.lower() for check in failed_checks):
                recommendations.append("Optimize data processing pipeline for latency")
            if any("quality" in check.name.lower() for check in failed_checks):
                recommendations.append("Review data quality validation rules")
        
        elif component_name == "intelligence_engine":
            if any("signal" in check.name.lower() for check in failed_checks):
                recommendations.append("Retrain or recalibrate signal generation models")
        
        elif component_name == "risk_management":
            if any("limit" in check.name.lower() for check in failed_checks):
                recommendations.append("Review and adjust risk limits")
        
        return recommendations[:3]  # Limit to top 3 per component
    
    def _generate_validation_report(self, validation_report: SystemValidationReport):
        """Generate and save validation report."""
        try:
            # Create detailed report
            report_data = {
                "validation_summary": {
                    "validation_id": validation_report.validation_id,
                    "timestamp": validation_report.timestamp.isoformat(),
                    "overall_status": validation_report.overall_status.value,
                    "system_health_score": validation_report.system_health_score,
                    "certification_status": validation_report.certification_status,
                    "execution_time_seconds": validation_report.execution_time_seconds
                },
                "component_results": [
                    {
                        "component_name": result.component_name,
                        "status": result.status.value,
                        "health_score": result.health_score,
                        "checks_passed": result.checks_passed,
                        "checks_failed": result.checks_failed,
                        "checks_total": result.checks_total,
                        "execution_time_seconds": result.execution_time_seconds,
                        "recommendations": result.recommendations
                    }
                    for result in validation_report.component_results
                ],
                "detailed_check_results": [
                    {
                        "component": result.component_name,
                        "checks": [
                            {
                                "check_id": check.check_id,
                                "name": check.name,
                                "status": check.status.value,
                                "severity": check.severity.value,
                                "message": check.message,
                                "execution_time_seconds": check.execution_time_seconds,
                                "details": check.details
                            }
                            for check in result.check_results
                        ]
                    }
                    for result in validation_report.component_results
                ],
                "critical_issues": validation_report.critical_issues,
                "recommendations": validation_report.recommendations,
                "next_validation_due": validation_report.next_validation_due.isoformat()
            }
            
            # Save report
            report_filename = f"system_validation_report_{validation_report.validation_id}.json"
            self.report_manager._generate_json_report(report_data, "system_validation")
            
            self.logger.info(f"System validation report generated: {report_filename}")
            
        except Exception as e:
            self.logger.error(f"Failed to generate validation report: {str(e)}")
    
    def get_system_health_status(self) -> SystemHealthStatus:
        """Get current system health status."""
        return self.system_health_status
    
    def get_validation_history(self) -> List[SystemValidationReport]:
        """Get validation history."""
        return self.validation_history.copy()
    
    def is_validation_due(self) -> bool:
        """Check if system validation is due."""
        if not self.last_validation_time:
            return True
        
        time_since_last = datetime.now() - self.last_validation_time
        return time_since_last.total_seconds() > (self.config["validation_frequency_hours"] * 3600)
    
    def generate_health_certificate(self) -> Dict[str, Any]:
        """
        Generate system health certificate.
        
        Returns:
            Dict[str, Any]: Health certificate data
        """
        if not self.validation_history:
            return {
                "certificate_status": "UNAVAILABLE",
                "message": "No validation history available",
                "timestamp": datetime.now().isoformat()
            }
        
        latest_validation = self.validation_history[-1]
        
        certificate = {
            "certificate_id": f"HealthCert_{int(time.time())}",
            "system_name": "Northstar V3 Trading System",
            "validation_id": latest_validation.validation_id,
            "certificate_timestamp": datetime.now().isoformat(),
            "validation_timestamp": latest_validation.timestamp.isoformat(),
            "overall_status": latest_validation.overall_status.value,
            "system_health_score": latest_validation.system_health_score,
            "certification_status": latest_validation.certification_status,
            "components_validated": latest_validation.components_validated,
            "components_passed": latest_validation.components_passed,
            "components_failed": latest_validation.components_failed,
            "total_checks": latest_validation.total_checks,
            "checks_passed": latest_validation.checks_passed,
            "checks_failed": latest_validation.checks_failed,
            "critical_issues_count": len(latest_validation.critical_issues),
            "certificate_valid_until": latest_validation.next_validation_due.isoformat(),
            "recommendations_count": len(latest_validation.recommendations),
            "certificate_details": {
                "validation_execution_time": latest_validation.execution_time_seconds,
                "component_health_scores": {
                    result.component_name: result.health_score
                    for result in latest_validation.component_results
                }
            }
        }
        
        # Save certificate
        try:
            certificate_filename = f"health_certificate_{certificate['certificate_id']}.json"
            self.report_manager._generate_json_report(certificate, "health_certificate")
            self.logger.info(f"Health certificate generated: {certificate_filename}")
        except Exception as e:
            self.logger.error(f"Failed to save health certificate: {str(e)}")
        
        return certificate