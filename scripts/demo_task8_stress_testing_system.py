#!/usr/bin/env python3
"""
Demo script for Task 8: Stress Testing System.

This script demonstrates the comprehensive stress testing capabilities including
scenario generation, execution, risk limit validation, failure documentation,
and recovery procedures.
"""

import sys
import time
import json
from pathlib import Path
from datetime import datetime

# Add src to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from src.operation.stress_testing_system import StressTestingSystem
from src.operation.base_types import StressTestConfig, AlertLevel


def print_header(title: str):
    """Print a formatted header."""
    print(f"\n{'='*60}")
    print(f"🧪 {title}")
    print(f"{'='*60}")


def print_section(title: str):
    """Print a formatted section header."""
    print(f"\n📊 {title}")
    print("-" * 40)


def print_result(key: str, value, indent: int = 0):
    """Print a formatted key-value result."""
    spaces = "  " * indent
    if isinstance(value, dict):
        print(f"{spaces}{key}:")
        for k, v in value.items():
            print_result(k, v, indent + 1)
    elif isinstance(value, list):
        print(f"{spaces}{key}: [{len(value)} items]")
        if len(value) <= 3:
            for item in value:
                print(f"{spaces}  - {item}")
        else:
            for item in value[:2]:
                print(f"{spaces}  - {item}")
            print(f"{spaces}  ... and {len(value) - 2} more")
    else:
        print(f"{spaces}{key}: {value}")


def demo_scenario_generation():
    """Demonstrate stress test scenario generation."""
    print_section("STRESS TEST SCENARIO GENERATION")
    
    # Create stress testing system
    config = StressTestConfig(
        default_scenario_duration_minutes=5,  # Short for demo
        min_risk_compliance_rate=0.8,
        enable_recovery_procedures=True
    )
    
    stress_tester = StressTestingSystem(config)
    
    print("🔧 Initializing Stress Testing System...")
    print(f"   Available Scenarios: {len(stress_tester.scenario_generators)}")
    print(f"   Risk Validators: {len(stress_tester.risk_validators)}")
    print(f"   Recovery Procedures: {len(stress_tester.recovery_procedures)}")
    
    # Demonstrate all available scenarios
    print(f"\n📋 Available Stress Test Scenarios:")
    
    scenarios_generated = []
    for scenario_name in stress_tester.scenario_generators.keys():
        print(f"\n🎯 Generating {scenario_name}...")
        
        # Generate default scenario
        scenario = stress_tester._generate_scenario(scenario_name)
        scenarios_generated.append(scenario)
        
        print(f"   Name: {scenario.name}")
        print(f"   Description: {scenario.description}")
        print(f"   Duration: {scenario.duration_minutes} minutes")
        print(f"   Severity: {scenario.severity}")
        print(f"   Parameters: {len(scenario.parameters)} configured")
        print(f"   Expected Impacts: {len(scenario.expected_impacts)} defined")
        print(f"   Risk Thresholds: {len(scenario.risk_thresholds)} set")
        
        # Show key parameters
        if scenario.parameters:
            print(f"   Key Parameters:")
            for key, value in list(scenario.parameters.items())[:3]:
                print(f"     - {key}: {value}")
        
        # Show expected impacts
        if scenario.expected_impacts:
            print(f"   Expected Impacts:")
            for impact in scenario.expected_impacts[:3]:
                print(f"     - {impact}")
    
    print(f"\n✅ Generated {len(scenarios_generated)} stress test scenarios")
    return stress_tester, scenarios_generated


def demo_single_stress_tests(stress_tester: StressTestingSystem):
    """Demonstrate individual stress test execution."""
    print_section("INDIVIDUAL STRESS TEST EXECUTION")
    
    # Test specific scenarios with different characteristics
    test_scenarios = [
        {
            "name": "extreme_volatility",
            "description": "High volatility market conditions",
            "parameters": {"duration_minutes": 3, "volatility_multiplier": 8.0}
        },
        {
            "name": "liquidity_crisis", 
            "description": "Severe liquidity constraints",
            "parameters": {"duration_minutes": 4, "spread_widening_factor": 15.0}
        },
        {
            "name": "data_feed_interruption",
            "description": "Critical data feed failures",
            "parameters": {"duration_minutes": 2, "interruption_probability": 0.5}
        }
    ]
    
    test_results = []
    
    for test_config in test_scenarios:
        scenario_name = test_config["name"]
        parameters = test_config.get("parameters", {})
        
        print(f"\n🧪 Executing {scenario_name}...")
        print(f"   Description: {test_config['description']}")
        if parameters:
            print(f"   Custom Parameters:")
            for key, value in parameters.items():
                print(f"     - {key}: {value}")
        
        # Execute stress test
        start_time = time.time()
        result = stress_tester.run_single_stress_test(scenario_name, parameters)
        execution_time = time.time() - start_time
        
        test_results.append(result)
        
        # Show results
        print(f"\n📊 Test Results:")
        print(f"   Test ID: {result.test_id}")
        print(f"   Status: {'✅ PASSED' if result.test_passed else '❌ FAILED'}")
        print(f"   Duration: {result.duration_seconds:.2f} seconds")
        print(f"   Execution Time: {execution_time:.2f} seconds")
        
        if result.performance_impact:
            print(f"   Performance Impact:")
            for key, value in result.performance_impact.items():
                if isinstance(value, float):
                    print(f"     - {key}: {value:.3f}")
                else:
                    print(f"     - {key}: {value}")
        
        if result.system_behavior:
            print(f"   System Behavior:")
            for key, value in result.system_behavior.items():
                print(f"     - {key}: {value}")
        
        if not result.test_passed:
            print(f"   ❌ Failure Reason: {result.failure_reason}")
            
            if result.recovery_required:
                print(f"   🔄 Recovery Required: Yes")
                if hasattr(result, 'recovery_procedures_executed'):
                    recovery = result.recovery_procedures_executed
                    print(f"   🔄 Recovery Success: {recovery.get('success', False)}")
        
        # Show risk limit validation if available
        if hasattr(result, 'risk_limit_validation') and result.risk_limit_validation:
            risk_validation = result.risk_limit_validation
            print(f"   🛡️  Risk Compliance: {risk_validation.get('overall_compliance', 'Unknown')}")
            print(f"   🛡️  Compliance Rate: {risk_validation.get('compliance_rate', 0):.1%}")
        
        print(f"   ⏱️  Test completed in {execution_time:.2f}s")
    
    return test_results


def demo_comprehensive_stress_testing(stress_tester: StressTestingSystem):
    """Demonstrate comprehensive stress testing across multiple scenarios."""
    print_section("COMPREHENSIVE STRESS TESTING")
    
    print("🚀 Running comprehensive stress test suite...")
    
    # Select subset of scenarios for demo (to keep execution time reasonable)
    test_scenarios = [
        "extreme_volatility",
        "liquidity_crisis", 
        "system_overload",
        "data_feed_interruption"
    ]
    
    print(f"   Testing {len(test_scenarios)} scenarios:")
    for scenario in test_scenarios:
        print(f"     - {scenario}")
    
    # Execute comprehensive stress tests
    start_time = time.time()
    results = stress_tester.run_comprehensive_stress_tests(test_scenarios)
    total_execution_time = time.time() - start_time
    
    print(f"\n📊 Comprehensive Test Results:")
    print(f"   Total Scenarios: {len(results)}")
    print(f"   Total Execution Time: {total_execution_time:.2f} seconds")
    
    # Analyze results
    passed_tests = [r for r in results if r.test_passed]
    failed_tests = [r for r in results if not r.test_passed]
    
    print(f"   ✅ Passed: {len(passed_tests)}")
    print(f"   ❌ Failed: {len(failed_tests)}")
    print(f"   📊 Pass Rate: {len(passed_tests) / len(results):.1%}")
    
    # Show individual results
    print(f"\n📋 Individual Test Results:")
    for result in results:
        status_icon = "✅" if result.test_passed else "❌"
        print(f"   {status_icon} {result.scenario_name}: {result.duration_seconds:.2f}s")
        
        if not result.test_passed and result.failure_reason:
            print(f"      Failure: {result.failure_reason}")
    
    # Show alerts generated
    if stress_tester.alerts_generated:
        print(f"\n⚠️  Alerts Generated: {len(stress_tester.alerts_generated)}")
        
        # Group alerts by level
        alert_counts = {}
        for alert in stress_tester.alerts_generated:
            level = alert.level.value
            alert_counts[level] = alert_counts.get(level, 0) + 1
        
        for level, count in alert_counts.items():
            print(f"     - {level.upper()}: {count}")
        
        # Show recent alerts
        print(f"\n📢 Recent Alerts (last 3):")
        for alert in stress_tester.alerts_generated[-3:]:
            print(f"     - {alert.level.value.upper()}: {alert.message}")
    
    return results


def demo_risk_limit_validation(stress_tester: StressTestingSystem):
    """Demonstrate risk limit validation under stress conditions."""
    print_section("RISK LIMIT VALIDATION UNDER STRESS")
    
    print("🛡️  Testing risk limit validation...")
    
    # Test various stress conditions
    stress_conditions_scenarios = [
        {
            "name": "High Volatility Stress",
            "conditions": {
                "scenario": "extreme_volatility",
                "performance_impact": {
                    "max_drawdown": 0.18,  # 18% drawdown
                    "var_breaches": 3,
                    "volatility_multiplier_applied": 6.0
                },
                "system_behavior": {
                    "processing_continuity": True,
                    "risk_monitoring_active": True
                }
            }
        },
        {
            "name": "Liquidity Crisis Stress",
            "conditions": {
                "scenario": "liquidity_crisis",
                "performance_impact": {
                    "avg_execution_delay": 45,  # 45 second delays
                    "avg_transaction_cost_bps": 150,  # 150 bps costs
                    "avg_fill_rate": 0.6  # 60% fill rate
                },
                "system_behavior": {
                    "execution_continuity": True,
                    "cost_monitoring_active": True
                }
            }
        },
        {
            "name": "System Overload Stress",
            "conditions": {
                "scenario": "system_overload",
                "performance_impact": {
                    "max_cpu_usage": 0.92,  # 92% CPU
                    "max_memory_usage": 0.88,  # 88% memory
                    "avg_processing_delay_ms": 800  # 800ms delays
                },
                "system_behavior": {
                    "system_stability": True,
                    "processing_continuity": True
                }
            }
        }
    ]
    
    validation_results = []
    
    for scenario in stress_conditions_scenarios:
        print(f"\n🧪 Testing {scenario['name']}...")
        
        conditions = scenario["conditions"]
        
        # Show stress conditions
        print(f"   Stress Conditions:")
        for key, value in conditions["performance_impact"].items():
            if isinstance(value, float):
                if "rate" in key or "usage" in key:
                    print(f"     - {key}: {value:.1%}")
                else:
                    print(f"     - {key}: {value:.3f}")
            else:
                print(f"     - {key}: {value}")
        
        # Validate risk limits
        validation_result = stress_tester.validate_risk_limits_under_stress(conditions)
        validation_results.append(validation_result)
        
        # Show validation results
        print(f"\n🛡️  Risk Validation Results:")
        print(f"   Overall Compliance: {'✅ PASS' if validation_result['overall_compliance'] else '❌ FAIL'}")
        print(f"   Compliance Rate: {validation_result['compliance_rate']:.1%}")
        
        # Show individual validations
        print(f"   Individual Validations:")
        for risk_type, validation in validation_result["validations"].items():
            status_icon = "✅" if validation["passed"] else "❌"
            print(f"     {status_icon} {risk_type}: {validation['passed']}")
            
            if "current_value" in validation and "limit_value" in validation:
                current = validation["current_value"]
                limit = validation["limit_value"]
                if isinstance(current, float) and isinstance(limit, float):
                    print(f"        Current: {current:.3f}, Limit: {limit:.3f}")
                else:
                    print(f"        Current: {current}, Limit: {limit}")
    
    # Show overall risk validation summary
    print(f"\n📊 Risk Validation Summary:")
    total_validations = len(validation_results)
    compliant_validations = sum(1 for v in validation_results if v["overall_compliance"])
    
    print(f"   Total Stress Scenarios: {total_validations}")
    print(f"   Compliant Scenarios: {compliant_validations}")
    print(f"   Overall Compliance Rate: {compliant_validations / total_validations:.1%}")
    
    # Show risk limit breach alerts
    risk_alerts = [
        alert for alert in stress_tester.alerts_generated
        if "risk limit breach" in alert.message.lower()
    ]
    
    if risk_alerts:
        print(f"\n⚠️  Risk Limit Breach Alerts: {len(risk_alerts)}")
        for alert in risk_alerts[-3:]:  # Show last 3
            print(f"     - {alert.level.value.upper()}: {alert.message}")
    
    return validation_results


def demo_failure_documentation_and_recovery(stress_tester: StressTestingSystem):
    """Demonstrate failure documentation and recovery procedures."""
    print_section("FAILURE DOCUMENTATION & RECOVERY")
    
    print("💥 Testing failure handling and recovery...")
    
    # Check if we have any failures from previous tests
    if stress_tester.failure_documentation:
        print(f"\n📝 Documented Failures: {len(stress_tester.failure_documentation)}")
        
        # Show recent failures
        recent_failures = stress_tester.failure_documentation[-3:]
        for i, failure in enumerate(recent_failures, 1):
            print(f"\n💥 Failure {i}:")
            print(f"   Test ID: {failure['test_id']}")
            print(f"   Scenario: {failure['scenario_name']}")
            print(f"   Failure Time: {failure['failure_time']}")
            print(f"   Reason: {failure['failure_reason']}")
            print(f"   Recovery Required: {failure.get('recovery_required', False)}")
            
            if failure.get('performance_impact'):
                print(f"   Performance Impact:")
                for key, value in failure['performance_impact'].items():
                    if isinstance(value, float):
                        print(f"     - {key}: {value:.3f}")
                    else:
                        print(f"     - {key}: {value}")
    else:
        print("   No failures documented yet - system performing well!")
    
    # Demonstrate recovery procedures
    print(f"\n🔄 Available Recovery Procedures:")
    for procedure_name, procedure_func in stress_tester.recovery_procedures.items():
        print(f"   - {procedure_name}")
    
    # Test recovery procedures
    print(f"\n🧪 Testing Recovery Procedures:")
    
    recovery_tests = [
        {"name": "data_recovery", "description": "Data backup and restoration"},
        {"name": "system_restart", "description": "System service restart"},
        {"name": "failover", "description": "Backup system activation"}
    ]
    
    recovery_results = []
    
    for recovery_test in recovery_tests:
        procedure_name = recovery_test["name"]
        description = recovery_test["description"]
        
        print(f"\n🔄 Testing {procedure_name}...")
        print(f"   Description: {description}")
        
        # Execute recovery procedure
        start_time = time.time()
        if procedure_name in stress_tester.recovery_procedures:
            recovery_result = stress_tester.recovery_procedures[procedure_name]()
            execution_time = time.time() - start_time
            
            recovery_results.append(recovery_result)
            
            print(f"   Status: {'✅ SUCCESS' if recovery_result.get('success', False) else '❌ FAILED'}")
            print(f"   Execution Time: {execution_time:.2f} seconds")
            
            if recovery_result.get('success'):
                print(f"   Recovery Time: {recovery_result.get('recovery_time_seconds', 0)} seconds")
                
                # Show procedure-specific results
                if procedure_name == "data_recovery":
                    print(f"   Data Restored: {recovery_result.get('data_restored', False)}")
                    print(f"   Backup Activated: {recovery_result.get('backup_activated', False)}")
                elif procedure_name == "system_restart":
                    services = recovery_result.get('services_restarted', [])
                    print(f"   Services Restarted: {len(services)}")
                    for service in services:
                        print(f"     - {service}")
                elif procedure_name == "failover":
                    print(f"   Backup Systems: {recovery_result.get('backup_systems_activated', False)}")
                    print(f"   Service Continuity: {recovery_result.get('service_continuity_maintained', False)}")
        else:
            print(f"   ❌ Procedure not available")
    
    # Show recovery success rate
    successful_recoveries = sum(1 for r in recovery_results if r.get('success', False))
    total_recoveries = len(recovery_results)
    
    print(f"\n📊 Recovery Procedure Results:")
    print(f"   Total Procedures Tested: {total_recoveries}")
    print(f"   Successful Recoveries: {successful_recoveries}")
    print(f"   Recovery Success Rate: {successful_recoveries / total_recoveries:.1%}" if total_recoveries > 0 else "   Recovery Success Rate: N/A")
    
    return recovery_results


def demo_stress_test_metrics_and_reporting(stress_tester: StressTestingSystem):
    """Demonstrate stress test metrics calculation and reporting."""
    print_section("STRESS TEST METRICS & REPORTING")
    
    print("📊 Generating comprehensive stress test metrics...")
    
    # Get comprehensive metrics
    metrics = stress_tester.get_stress_test_metrics()
    
    # Show test statistics
    print(f"\n📈 Test Statistics:")
    test_stats = metrics["test_statistics"]
    print_result("Total Tests", test_stats["total_tests"])
    print_result("Passed Tests", test_stats["passed_tests"])
    print_result("Failed Tests", test_stats["failed_tests"])
    print_result("Pass Rate", f"{test_stats['pass_rate']:.1%}")
    print_result("Average Duration", f"{test_stats['average_duration_seconds']:.2f} seconds")
    
    # Show scenario statistics
    if metrics["scenario_statistics"]:
        print(f"\n🎯 Scenario Statistics:")
        for scenario, stats in metrics["scenario_statistics"].items():
            print(f"   {scenario}:")
            print(f"     Total: {stats['total']}")
            print(f"     Passed: {stats['passed']}")
            print(f"     Failed: {stats['failed']}")
            print(f"     Failure Rate: {stats['failure_rate']:.1%}")
    
    # Show risk compliance metrics
    print(f"\n🛡️  Risk Compliance:")
    risk_compliance = metrics["risk_compliance"]
    print_result("Total Validations", risk_compliance["total_validations"])
    print_result("Compliant Tests", risk_compliance["compliant_tests"])
    
    # Show failure analysis
    print(f"\n💥 Failure Analysis:")
    failure_analysis = metrics["failure_analysis"]
    print_result("Total Failures", failure_analysis["total_failures"])
    print_result("Recovery Attempts", failure_analysis["recovery_attempts"])
    print_result("Successful Recoveries", failure_analysis["successful_recoveries"])
    
    # Show alerts summary
    print(f"\n⚠️  Alerts Summary:")
    print_result("Total Alerts Generated", metrics["alerts_generated"])
    
    # Generate comprehensive report
    print(f"\n📋 Generating comprehensive stress test report...")
    
    # Create some test results for the report
    recent_results = stress_tester.test_history[-5:] if stress_tester.test_history else []
    
    if recent_results:
        report_path = stress_tester._generate_stress_test_report(recent_results)
        print(f"✅ Report generated: {report_path}")
        
        # Load and show report summary
        try:
            with open(report_path, 'r') as f:
                report_data = json.load(f)
            
            print(f"\n📊 Report Summary:")
            if "test_summary" in report_data:
                summary = report_data["test_summary"]
                print(f"   Report Date: {report_data.get('report_date')}")
                print(f"   Total Tests: {summary['total_tests']}")
                print(f"   Pass Rate: {summary['pass_rate']:.1%}")
            
            if "recommendations" in report_data:
                print(f"\n💡 Recommendations:")
                for rec in report_data["recommendations"][:3]:
                    print(f"     - {rec}")
        
        except Exception as e:
            print(f"❌ Error reading report: {str(e)}")
    else:
        print("   No test results available for report generation")
    
    return metrics


def main():
    """Run the complete Stress Testing System demonstration."""
    print_header("NORTHSTAR V3 STRESS TESTING SYSTEM DEMO")
    
    print("This demonstration showcases the comprehensive stress testing capabilities")
    print("including scenario generation, execution, risk validation, failure handling,")
    print("recovery procedures, and detailed reporting.")
    
    try:
        # 1. Scenario Generation
        stress_tester, scenarios = demo_scenario_generation()
        
        # 2. Individual Stress Tests
        individual_results = demo_single_stress_tests(stress_tester)
        
        # 3. Comprehensive Stress Testing
        comprehensive_results = demo_comprehensive_stress_testing(stress_tester)
        
        # 4. Risk Limit Validation
        risk_validation_results = demo_risk_limit_validation(stress_tester)
        
        # 5. Failure Documentation and Recovery
        recovery_results = demo_failure_documentation_and_recovery(stress_tester)
        
        # 6. Metrics and Reporting
        final_metrics = demo_stress_test_metrics_and_reporting(stress_tester)
        
        # Final Summary
        print_header("DEMO COMPLETION SUMMARY")
        
        print(f"✅ Scenario Generation: {len(scenarios)} scenarios created")
        print(f"🧪 Individual Tests: {len(individual_results)} tests executed")
        print(f"🚀 Comprehensive Tests: {len(comprehensive_results)} scenarios tested")
        print(f"🛡️  Risk Validations: {len(risk_validation_results)} validations performed")
        print(f"🔄 Recovery Tests: {len(recovery_results)} procedures tested")
        
        # Show final statistics
        if final_metrics:
            test_stats = final_metrics["test_statistics"]
            print(f"📊 Overall Pass Rate: {test_stats['pass_rate']:.1%}")
            print(f"⚠️  Total Alerts: {final_metrics['alerts_generated']}")
            print(f"💥 Total Failures: {final_metrics['failure_analysis']['total_failures']}")
        
        print(f"\n🎉 Stress Testing System demonstration completed successfully!")
        print(f"The system demonstrated robust stress testing capabilities with")
        print(f"comprehensive scenario coverage, risk validation, and recovery procedures.")
        
    except Exception as e:
        print(f"\n💥 Demo failed with error: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()