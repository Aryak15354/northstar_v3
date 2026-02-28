#!/usr/bin/env python3
"""
Demo Script for Task 11: System Validation Suite

This script demonstrates the comprehensive system validation capabilities
of the Northstar V3 System Validation Suite.

Author: Northstar Team
Date: 2026-01-05
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
from src.operation.system_validation_suite import SystemValidationSuite
from src.operation.base_types import SystemHealthStatus, ComponentStatus


def print_header(title: str):
    """Print a formatted header."""
    print(f"\n{'='*80}")
    print(f"{'='*12} {title:^54} {'='*12}")
    print(f"{'='*80}")


def print_section(title: str):
    """Print a formatted section header."""
    print(f"\n📊 {title.upper()}")
    print("-" * 40)


def main():
    """Run the System Validation Suite demonstration."""
    
    print_header("📋 NORTHSTAR V3 SYSTEM VALIDATION SUITE DEMO")
    print("This demonstration showcases the comprehensive system validation")
    print("capabilities including component validation, health certification,")
    print("and system readiness assessment.")
    
    # Initialize System Validation Suite
    print_section("SYSTEM VALIDATION SUITE INITIALIZATION")
    
    validation_suite = SystemValidationSuite()
    
    print("🔧 System Validation Suite Configuration:")
    print(f"   Validation Timeout: {validation_suite.config['validation_timeout']} seconds")
    print(f"   Component Timeout: {validation_suite.config['component_timeout']} seconds")
    print(f"   Check Timeout: {validation_suite.config['check_timeout']} seconds")
    print(f"   Retry Attempts: {validation_suite.config['retry_attempts']}")
    print(f"   Health Score Threshold: {validation_suite.config['health_score_threshold']}")
    print(f"   Certification Threshold: {validation_suite.config['certification_threshold']}")
    print(f"   Validation Frequency: {validation_suite.config['validation_frequency_hours']} hours")
    
    print(f"\n📋 Validation Checks Loaded:")
    print(f"   Total Validation Checks: {len(validation_suite.validation_checks)}")
    
    # Group checks by component
    component_checks = {}
    for check in validation_suite.validation_checks:
        if check.component not in component_checks:
            component_checks[check.component] = []
        component_checks[check.component].append(check)
    
    print(f"   Components to Validate: {len(component_checks)}")
    for component, checks in component_checks.items():
        print(f"     - {component}: {len(checks)} checks")
    
    print(f"\n🔍 Validation Check Categories:")
    severity_counts = {}
    for check in validation_suite.validation_checks:
        severity = check.severity.value
        severity_counts[severity] = severity_counts.get(severity, 0) + 1
    
    for severity, count in severity_counts.items():
        print(f"     - {severity.upper()}: {count} checks")
    
    # Run Comprehensive System Validation
    print_section("COMPREHENSIVE SYSTEM VALIDATION")
    
    print("🚀 Running comprehensive system validation...")
    print("   This will validate all system components including:")
    print("   - Data Pipeline (connectivity, quality, latency)")
    print("   - Intelligence Engine (signals, models, memory)")
    print("   - Risk Management (limits, calculations, emergency systems)")
    print("   - Portfolio Management (sizing, rebalancing, costs)")
    print("   - System Integration (communication, events, synchronization)")
    
    validation_report = validation_suite.run_comprehensive_system_validation()
    
    print(f"\n📊 Validation Results:")
    print(f"   Validation ID: {validation_report.validation_id}")
    print(f"   Overall Status: {validation_report.overall_status.value}")
    print(f"   System Health Score: {validation_report.system_health_score:.3f}")
    print(f"   Certification Status: {validation_report.certification_status}")
    print(f"   Execution Time: {validation_report.execution_time_seconds:.2f} seconds")
    
    print(f"\n📈 Component Summary:")
    print(f"   Components Validated: {validation_report.components_validated}")
    print(f"   Components Passed: {validation_report.components_passed}")
    print(f"   Components Failed: {validation_report.components_failed}")
    print(f"   Total Checks: {validation_report.total_checks}")
    print(f"   Checks Passed: {validation_report.checks_passed}")
    print(f"   Checks Failed: {validation_report.checks_failed}")
    
    # Component-Level Results
    print_section("COMPONENT VALIDATION RESULTS")
    
    for component_result in validation_report.component_results:
        status_emoji = {
            ComponentStatus.HEALTHY: "✅",
            ComponentStatus.DEGRADED: "⚠️",
            ComponentStatus.FAILED: "❌"
        }.get(component_result.status, "❓")
        
        print(f"\n{status_emoji} {component_result.component_name.upper()}:")
        print(f"   Status: {component_result.status.value}")
        print(f"   Health Score: {component_result.health_score:.3f}")
        print(f"   Checks: {component_result.checks_passed}/{component_result.checks_total} passed")
        print(f"   Execution Time: {component_result.execution_time_seconds:.2f} seconds")
        
        if component_result.recommendations:
            print(f"   Recommendations:")
            for rec in component_result.recommendations[:3]:  # Show top 3
                print(f"     - {rec}")
        
        # Show detailed check results for failed or degraded components
        if component_result.status != ComponentStatus.HEALTHY:
            print(f"   Detailed Check Results:")
            for check_result in component_result.check_results:
                if check_result.status != ComponentStatus.HEALTHY:
                    check_emoji = "❌" if check_result.status == ComponentStatus.FAILED else "⚠️"
                    print(f"     {check_emoji} {check_result.name}: {check_result.message}")
    
    # Critical Issues and Recommendations
    if validation_report.critical_issues:
        print_section("CRITICAL ISSUES")
        print("🚨 Critical issues detected:")
        for i, issue in enumerate(validation_report.critical_issues, 1):
            print(f"   {i}. {issue}")
    
    if validation_report.recommendations:
        print_section("SYSTEM RECOMMENDATIONS")
        print("💡 System recommendations:")
        for i, recommendation in enumerate(validation_report.recommendations[:10], 1):
            print(f"   {i}. {recommendation}")
    
    # Health Certificate Generation
    print_section("HEALTH CERTIFICATE GENERATION")
    
    print("📜 Generating system health certificate...")
    certificate = validation_suite.generate_health_certificate()
    
    print(f"\n🏆 Health Certificate:")
    print(f"   Certificate ID: {certificate['certificate_id']}")
    print(f"   System Name: {certificate['system_name']}")
    print(f"   Certificate Status: {certificate['certification_status']}")
    print(f"   Health Score: {certificate['system_health_score']:.3f}")
    print(f"   Components Validated: {certificate['components_validated']}")
    print(f"   Components Passed: {certificate['components_passed']}")
    print(f"   Components Failed: {certificate['components_failed']}")
    print(f"   Total Checks: {certificate['total_checks']}")
    print(f"   Checks Passed: {certificate['checks_passed']}")
    print(f"   Checks Failed: {certificate['checks_failed']}")
    print(f"   Critical Issues: {certificate['critical_issues_count']}")
    
    cert_timestamp = datetime.fromisoformat(certificate['certificate_timestamp'])
    valid_until = datetime.fromisoformat(certificate['certificate_valid_until'])
    validity_hours = (valid_until - cert_timestamp).total_seconds() / 3600
    
    print(f"   Certificate Issued: {cert_timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   Valid Until: {valid_until.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   Validity Period: {validity_hours:.1f} hours")
    
    # Component Health Scores
    print(f"\n📊 Component Health Scores:")
    component_scores = certificate['certificate_details']['component_health_scores']
    for component, score in component_scores.items():
        score_emoji = "🟢" if score >= 0.9 else "🟡" if score >= 0.7 else "🔴"
        print(f"   {score_emoji} {component}: {score:.3f}")
    
    # Validation History and Trends
    print_section("VALIDATION HISTORY & TRENDS")
    
    validation_history = validation_suite.get_validation_history()
    print(f"📈 Validation History:")
    print(f"   Total Validations: {len(validation_history)}")
    print(f"   Latest Validation: {validation_history[-1].timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
    
    if len(validation_history) > 1:
        previous_score = validation_history[-2].system_health_score
        current_score = validation_history[-1].system_health_score
        score_change = current_score - previous_score
        
        trend_emoji = "📈" if score_change > 0 else "📉" if score_change < 0 else "➡️"
        print(f"   Health Score Trend: {trend_emoji} {score_change:+.3f}")
    
    # Validation Due Check
    print(f"\n⏰ Next Validation:")
    is_due = validation_suite.is_validation_due()
    print(f"   Validation Due: {'Yes' if is_due else 'No'}")
    print(f"   Next Due: {validation_report.next_validation_due.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # System Readiness Assessment
    print_section("SYSTEM READINESS ASSESSMENT")
    
    readiness_status = "READY" if validation_report.overall_status == SystemHealthStatus.HEALTHY else \
                      "CONDITIONAL" if validation_report.overall_status == SystemHealthStatus.WARNING else \
                      "NOT READY"
    
    readiness_emoji = {
        "READY": "🟢",
        "CONDITIONAL": "🟡", 
        "NOT READY": "🔴"
    }.get(readiness_status, "❓")
    
    print(f"{readiness_emoji} System Readiness: {readiness_status}")
    
    if readiness_status == "READY":
        print("   ✅ System is ready for production operation")
        print("   ✅ All critical components are healthy")
        print("   ✅ No critical issues detected")
        print("   ✅ Health score meets certification threshold")
    
    elif readiness_status == "CONDITIONAL":
        print("   ⚠️  System is functional with minor issues")
        print("   ⚠️  Some components may be degraded")
        print("   ⚠️  Monitor system closely during operation")
        print("   ⚠️  Address recommendations before full deployment")
    
    else:
        print("   ❌ System is not ready for production")
        print("   ❌ Critical issues must be resolved")
        print("   ❌ Failed components require immediate attention")
        print("   ❌ Do not deploy until issues are fixed")
    
    # Performance Metrics
    print_section("VALIDATION PERFORMANCE METRICS")
    
    print(f"⚡ Performance Metrics:")
    print(f"   Total Validation Time: {validation_report.execution_time_seconds:.2f} seconds")
    print(f"   Average Check Time: {validation_report.execution_time_seconds / validation_report.total_checks:.3f} seconds")
    print(f"   Checks per Second: {validation_report.total_checks / validation_report.execution_time_seconds:.1f}")
    
    component_times = [result.execution_time_seconds for result in validation_report.component_results]
    if component_times:
        print(f"   Fastest Component: {min(component_times):.2f} seconds")
        print(f"   Slowest Component: {max(component_times):.2f} seconds")
        print(f"   Average Component Time: {sum(component_times) / len(component_times):.2f} seconds")
    
    # Summary
    print_header("📋 DEMO COMPLETION SUMMARY")
    
    print("✅ System Validation Suite: Initialized successfully")
    print(f"📊 Comprehensive Validation: {validation_report.components_validated} components validated")
    print(f"🔍 Validation Checks: {validation_report.total_checks} checks executed")
    print(f"📜 Health Certificate: Generated successfully")
    print(f"📈 System Health Score: {validation_report.system_health_score:.3f}")
    print(f"🏆 Certification Status: {validation_report.certification_status}")
    print(f"⚡ Execution Time: {validation_report.execution_time_seconds:.2f} seconds")
    print(f"🎯 System Status: {validation_report.overall_status.value}")
    
    if validation_report.critical_issues:
        print(f"🚨 Critical Issues: {len(validation_report.critical_issues)} detected")
    else:
        print("✅ Critical Issues: None detected")
    
    print(f"💡 Recommendations: {len(validation_report.recommendations)} generated")
    
    print(f"\n🎉 System Validation Suite demonstration completed successfully!")
    print("The system demonstrated comprehensive validation capabilities")
    print("with detailed component analysis and health certification.")


if __name__ == "__main__":
    main()