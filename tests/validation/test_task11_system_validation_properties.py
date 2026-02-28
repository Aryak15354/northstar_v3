"""
Property Tests for Task 11: System Validation Suite

This module contains property-based tests that validate the universal correctness
properties of the System Validation Suite implementation.

Author: Northstar Team
Date: 2026-01-05
"""

import pytest
import numpy as np
from datetime import datetime, timedelta
from hypothesis import given, strategies as st, settings
from typing import Dict, List, Any

from src.operation.system_validation_suite import (
    SystemValidationSuite, ValidationCheck, ValidationSeverity,
    ComponentStatus, SystemHealthStatus
)
from src.operation.base_types import Alert, AlertLevel


class TestSystemValidationSuiteProperties:
    """Property tests for System Validation Suite."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.validation_suite = SystemValidationSuite()
    
    def test_property_27_comprehensive_system_validation(self):
        """
        Property 27: Comprehensive System Validation
        
        Universal Property: For any system validation execution, the system
        validates all critical components and generates comprehensive reports.
        
        Validates: Requirements 8.1, 8.2, 8.3
        """
        # Test comprehensive validation execution
        validation_report = self.validation_suite.run_comprehensive_system_validation()
        
        # Property: Validation report has required structure
        assert hasattr(validation_report, 'validation_id'), "Report must have validation ID"
        assert hasattr(validation_report, 'overall_status'), "Report must have overall status"
        assert hasattr(validation_report, 'system_health_score'), "Report must have health score"
        assert hasattr(validation_report, 'component_results'), "Report must have component results"
        
        # Property: All critical components are validated
        critical_components = {"data_pipeline", "intelligence_engine", "risk_management"}
        validated_components = {result.component_name for result in validation_report.component_results}
        
        for critical_component in critical_components:
            assert critical_component in validated_components, \
                f"Critical component {critical_component} must be validated"
        
        # Property: Health score is within valid range
        assert 0.0 <= validation_report.system_health_score <= 1.0, \
            "System health score must be between 0.0 and 1.0"
        
        # Property: Component results are comprehensive
        for component_result in validation_report.component_results:
            assert component_result.checks_total > 0, \
                f"Component {component_result.component_name} must have validation checks"
            assert component_result.checks_passed + component_result.checks_failed == component_result.checks_total, \
                "Check counts must be consistent"
            assert 0.0 <= component_result.health_score <= 1.0, \
                "Component health score must be between 0.0 and 1.0"
        
        # Property: Validation execution time is recorded
        assert validation_report.execution_time_seconds > 0, \
            "Validation execution time must be positive"
        
        # Property: Status consistency
        if validation_report.system_health_score >= 0.9:
            assert validation_report.overall_status in [SystemHealthStatus.HEALTHY, SystemHealthStatus.WARNING], \
                "High health score should correspond to healthy or warning status"
        
        if validation_report.components_failed > 0:
            assert validation_report.overall_status != SystemHealthStatus.HEALTHY, \
                "Failed components should prevent healthy status"
    
    def test_property_28_health_certificate_generation(self):
        """
        Property 28: Health Certificate Generation
        
        Universal Property: For any system with validation history, the system
        generates valid health certificates with complete information.
        
        Validates: Requirements 8.4
        """
        # Run validation to create history
        validation_report = self.validation_suite.run_comprehensive_system_validation()
        
        # Generate health certificate
        certificate = self.validation_suite.generate_health_certificate()
        
        # Property: Certificate has required fields
        required_fields = [
            "certificate_id", "system_name", "validation_id", "certificate_timestamp",
            "validation_timestamp", "overall_status", "system_health_score",
            "certification_status", "components_validated", "certificate_valid_until"
        ]
        
        for field in required_fields:
            assert field in certificate, f"Certificate must include {field}"
        
        # Property: Certificate data consistency
        assert certificate["validation_id"] == validation_report.validation_id, \
            "Certificate must reference correct validation"
        
        assert certificate["system_health_score"] == validation_report.system_health_score, \
            "Certificate health score must match validation"
        
        assert certificate["overall_status"] == validation_report.overall_status.value, \
            "Certificate status must match validation"
        
        # Property: Certificate validity period
        cert_timestamp = datetime.fromisoformat(certificate["certificate_timestamp"])
        valid_until = datetime.fromisoformat(certificate["certificate_valid_until"])
        
        assert valid_until > cert_timestamp, \
            "Certificate must have future validity period"
        
        # Property: Certificate includes component details
        assert "certificate_details" in certificate, \
            "Certificate must include detailed information"
        
        component_scores = certificate["certificate_details"]["component_health_scores"]
        assert len(component_scores) > 0, \
            "Certificate must include component health scores"
        
        for component_name, score in component_scores.items():
            assert 0.0 <= score <= 1.0, \
                f"Component {component_name} health score must be valid"
    
    def test_comprehensive_validation_component_coverage(self):
        """Test that comprehensive validation covers all system components."""
        validation_report = self.validation_suite.run_comprehensive_system_validation()
        
        # Property: All defined components are validated
        expected_components = {
            "data_pipeline", "intelligence_engine", "risk_management",
            "portfolio_management", "system_integration"
        }
        
        validated_components = {result.component_name for result in validation_report.component_results}
        
        assert expected_components.issubset(validated_components), \
            f"Missing components: {expected_components - validated_components}"
        
        # Property: Each component has multiple validation checks
        for component_result in validation_report.component_results:
            assert len(component_result.check_results) >= 2, \
                f"Component {component_result.component_name} should have multiple checks"
    
    def test_validation_check_dependency_handling(self):
        """Test that validation checks handle dependencies correctly."""
        validation_report = self.validation_suite.run_comprehensive_system_validation()
        
        # Property: Dependent checks are executed after their dependencies
        for component_result in validation_report.component_results:
            check_execution_order = {
                check.check_id: i for i, check in enumerate(component_result.check_results)
            }
            
            for check in component_result.check_results:
                # Find the original check definition
                original_check = next(
                    (c for c in self.validation_suite.validation_checks if c.check_id == check.check_id),
                    None
                )
                
                if original_check and original_check.dependencies:
                    check_position = check_execution_order[check.check_id]
                    
                    for dep_id in original_check.dependencies:
                        if dep_id in check_execution_order:
                            dep_position = check_execution_order[dep_id]
                            assert dep_position < check_position, \
                                f"Dependency {dep_id} must be executed before {check.check_id}"
    
    def test_validation_failure_handling(self):
        """Test validation behavior with simulated failures."""
        # Create a validation suite with mock failures
        validation_suite = SystemValidationSuite()
        
        # Run validation (some checks may fail randomly due to mock implementation)
        validation_report = validation_suite.run_comprehensive_system_validation()
        
        # Property: Failed checks are properly recorded
        total_failed = sum(result.checks_failed for result in validation_report.component_results)
        assert validation_report.checks_failed == total_failed, \
            "Total failed checks must match sum of component failures"
        
        # Property: Critical issues are identified
        if validation_report.checks_failed > 0:
            # Check if any failures were critical
            has_critical_failures = any(
                any(check.severity == ValidationSeverity.CRITICAL and check.status == ComponentStatus.FAILED
                    for check in result.check_results)
                for result in validation_report.component_results
            )
            
            if has_critical_failures:
                assert len(validation_report.critical_issues) > 0, \
                    "Critical failures should be recorded as critical issues"
        
        # Property: Recommendations are provided for failures
        if validation_report.checks_failed > 0:
            assert len(validation_report.recommendations) > 0, \
                "Validation failures should generate recommendations"
    
    def test_system_health_score_calculation(self):
        """Test system health score calculation properties."""
        validation_report = self.validation_suite.run_comprehensive_system_validation()
        
        # Property: Health score reflects component performance
        component_scores = [result.health_score for result in validation_report.component_results]
        
        if component_scores:
            min_component_score = min(component_scores)
            max_component_score = max(component_scores)
            
            # System score should be influenced by component scores
            assert min_component_score <= validation_report.system_health_score <= max_component_score or \
                   abs(validation_report.system_health_score - np.mean(component_scores)) < 0.3, \
                "System health score should reflect component performance"
        
        # Property: Health score consistency with status
        if validation_report.system_health_score >= 0.9:
            assert validation_report.overall_status in [
                SystemHealthStatus.HEALTHY, SystemHealthStatus.WARNING
            ], "High health score should correspond to good status"
        
        if validation_report.system_health_score < 0.5:
            assert validation_report.overall_status in [
                SystemHealthStatus.CRITICAL, SystemHealthStatus.DEGRADED
            ], "Low health score should correspond to poor status"
    
    def test_validation_timing_and_performance(self):
        """Test validation timing and performance properties."""
        start_time = datetime.now()
        validation_report = self.validation_suite.run_comprehensive_system_validation()
        end_time = datetime.now()
        
        total_execution_time = (end_time - start_time).total_seconds()
        
        # Property: Reported execution time is reasonable
        assert abs(validation_report.execution_time_seconds - total_execution_time) < 1.0, \
            "Reported execution time should match actual time"
        
        # Property: Component execution times sum reasonably to total
        component_times = sum(result.execution_time_seconds for result in validation_report.component_results)
        
        # Allow for some overhead and parallel execution
        assert component_times <= validation_report.execution_time_seconds * 2, \
            "Component times should not exceed total time by too much"
        
        # Property: Individual check times are reasonable
        for component_result in validation_report.component_results:
            for check_result in component_result.check_results:
                assert 0 < check_result.execution_time_seconds < 60, \
                    f"Check {check_result.name} execution time should be reasonable"
    
    def test_validation_report_completeness(self):
        """Test validation report completeness properties."""
        validation_report = self.validation_suite.run_comprehensive_system_validation()
        
        # Property: Report includes all executed checks
        total_checks_in_components = sum(
            len(result.check_results) for result in validation_report.component_results
        )
        
        assert validation_report.total_checks == total_checks_in_components, \
            "Total checks should match sum of component checks"
        
        # Property: Check status counts are consistent
        total_passed = sum(result.checks_passed for result in validation_report.component_results)
        total_failed = sum(result.checks_failed for result in validation_report.component_results)
        
        assert validation_report.checks_passed == total_passed, \
            "Total passed checks should match sum"
        assert validation_report.checks_failed == total_failed, \
            "Total failed checks should match sum"
        assert validation_report.checks_passed + validation_report.checks_failed == validation_report.total_checks, \
            "Passed + failed should equal total checks"
        
        # Property: Component status counts are consistent
        healthy_components = sum(
            1 for result in validation_report.component_results 
            if result.status == ComponentStatus.HEALTHY
        )
        failed_components = sum(
            1 for result in validation_report.component_results 
            if result.status == ComponentStatus.FAILED
        )
        
        assert validation_report.components_passed == healthy_components, \
            "Passed components count should match healthy components"
        
        # Property: Timestamps are reasonable
        assert validation_report.timestamp <= datetime.now(), \
            "Validation timestamp should not be in the future"
        
        assert validation_report.next_validation_due > datetime.now(), \
            "Next validation should be scheduled in the future"
    
    def test_health_certificate_validity(self):
        """Test health certificate validity properties."""
        # Run multiple validations to test certificate consistency
        validation_reports = []
        for _ in range(3):
            report = self.validation_suite.run_comprehensive_system_validation()
            validation_reports.append(report)
        
        # Generate certificate
        certificate = self.validation_suite.generate_health_certificate()
        
        # Property: Certificate reflects latest validation
        latest_validation = validation_reports[-1]
        assert certificate["validation_id"] == latest_validation.validation_id, \
            "Certificate should reference latest validation"
        
        # Property: Certificate status is consistent with validation
        if latest_validation.system_health_score >= 0.9 and not latest_validation.critical_issues:
            assert "CERTIFIED" in certificate["certification_status"] or \
                   "CONDITIONAL" in certificate["certification_status"], \
                "High health score with no critical issues should result in certification"
        
        if latest_validation.critical_issues:
            assert "FAILED" in certificate["certification_status"], \
                "Critical issues should result in failed certification"
        
        # Property: Certificate includes validation history context
        validation_history = self.validation_suite.get_validation_history()
        assert len(validation_history) >= 3, \
            "Validation history should include all executed validations"
    
    def test_validation_due_check_properties(self):
        """Test validation due check properties."""
        # Initially, validation should be due
        assert self.validation_suite.is_validation_due(), \
            "Validation should be due initially"
        
        # After running validation, it should not be due
        self.validation_suite.run_comprehensive_system_validation()
        assert not self.validation_suite.is_validation_due(), \
            "Validation should not be due immediately after execution"
        
        # Property: Validation due status is consistent with configuration
        last_validation_time = self.validation_suite.last_validation_time
        frequency_hours = self.validation_suite.config["validation_frequency_hours"]
        
        # Simulate time passage
        self.validation_suite.last_validation_time = datetime.now() - timedelta(hours=frequency_hours + 1)
        assert self.validation_suite.is_validation_due(), \
            "Validation should be due after frequency period has passed"