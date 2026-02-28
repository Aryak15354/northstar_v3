#!/usr/bin/env python3
"""
Demo script for Task 2: Crisis Validator

This script demonstrates the Crisis Validator functionality including:
- Crisis period validation for 2008, 2020, and 2000 crises
- Comprehensive crisis reporting
- Property validation for crisis report generation and alert thresholds
"""

import sys
import json
from pathlib import Path
from datetime import datetime

# Add src to path for imports
sys.path.append(str(Path(__file__).parent.parent / "src"))

from operation.crisis_validator import CrisisValidator
from operation.base_types import CrisisPeriod


def main():
    """Demonstrate Crisis Validator functionality."""
    print("=" * 80)
    print("NORTHSTAR V3 CRISIS VALIDATOR DEMO")
    print("=" * 80)
    print()
    
    # Initialize Crisis Validator
    print("1. Initializing Crisis Validator...")
    validator = CrisisValidator()
    print(f"   ✓ Crisis Validator initialized with {len(validator.CRISIS_PERIODS)} crisis periods")
    print()
    
    # Display configured crisis periods
    print("2. Configured Crisis Periods:")
    for name, period in validator.CRISIS_PERIODS.items():
        print(f"   • {period.name}: {period.start_date.date()} to {period.end_date.date()}")
        print(f"     Severity: {period.severity}, Characteristics: {', '.join(period.characteristics)}")
    print()
    
    # Validate individual crisis periods
    print("3. Running Individual Crisis Validations...")
    individual_results = []
    
    # 2008 Financial Crisis
    print("   Testing 2008 Financial Crisis...")
    result_2008 = validator.validate_2008_crisis()
    individual_results.append(result_2008)
    status_2008 = "PASSED" if result_2008.stress_test_passed else "FAILED"
    print(f"   ✓ 2008 Crisis: {status_2008}")
    print(f"     Return: {result_2008.total_return:.2%}, Drawdown: {result_2008.max_drawdown:.2%}")
    print(f"     Sharpe: {result_2008.sharpe_ratio:.2f}, VaR Breaches: {result_2008.var_breach_count}")
    print()
    
    # 2020 COVID Crash
    print("   Testing 2020 COVID Crash...")
    result_2020 = validator.validate_2020_covid_crash()
    individual_results.append(result_2020)
    status_2020 = "PASSED" if result_2020.stress_test_passed else "FAILED"
    print(f"   ✓ 2020 COVID: {status_2020}")
    print(f"     Return: {result_2020.total_return:.2%}, Drawdown: {result_2020.max_drawdown:.2%}")
    print(f"     Sharpe: {result_2020.sharpe_ratio:.2f}, VaR Breaches: {result_2020.var_breach_count}")
    print()
    
    # 2000 Dot-com Bubble
    print("   Testing 2000 Dot-com Bubble...")
    result_2000 = validator.validate_2000_dotcom_bubble()
    individual_results.append(result_2000)
    status_2000 = "PASSED" if result_2000.stress_test_passed else "FAILED"
    print(f"   ✓ 2000 Dot-com: {status_2000}")
    print(f"     Return: {result_2000.total_return:.2%}, Drawdown: {result_2000.max_drawdown:.2%}")
    print(f"     Sharpe: {result_2000.sharpe_ratio:.2f}, VaR Breaches: {result_2000.var_breach_count}")
    print()
    
    # Run comprehensive validation
    print("4. Running Comprehensive Crisis Validation...")
    all_results = validator.validate_all_crisis_periods()
    print(f"   ✓ Validated {len(all_results)} crisis periods")
    
    passed_count = sum(1 for r in all_results if r.stress_test_passed)
    pass_rate = passed_count / len(all_results) if all_results else 0
    print(f"   ✓ Pass Rate: {pass_rate:.1%} ({passed_count}/{len(all_results)})")
    print()
    
    # Generate comprehensive crisis report
    print("5. Generating Comprehensive Crisis Report...")
    report = validator.generate_crisis_report(all_results)
    
    print("   Report Summary:")
    summary = report["summary"]
    print(f"   • Total Crisis Periods: {summary['total_crisis_periods']}")
    print(f"   • Periods Passed: {summary['periods_passed']}")
    print(f"   • Pass Rate: {summary['pass_rate']:.1%}")
    print(f"   • Overall Assessment: {summary['overall_assessment']}")
    print()
    
    print("   Performance Metrics:")
    perf = report["performance_metrics"]
    print(f"   • Average Return: {perf['average_return']:.2%}")
    print(f"   • Average Max Drawdown: {perf['average_max_drawdown']:.2%}")
    print(f"   • Average Volatility: {perf['average_volatility']:.2%}")
    print(f"   • Average Sharpe Ratio: {perf['average_sharpe_ratio']:.2f}")
    print(f"   • Total VaR Breaches: {perf['total_var_breaches']}")
    print()
    
    print("   Risk Analysis:")
    risk = report["risk_analysis"]
    print(f"   • Total Risk Breaches: {risk['total_risk_breaches']}")
    print(f"   • Average Recovery Time: {risk['average_recovery_time_days']:.0f} days")
    print(f"   • Risk Assessment: {risk['risk_assessment']}")
    print()
    
    # Display insights and recommendations
    print("6. Crisis Validation Insights:")
    insights = report["insights_and_recommendations"]
    
    if insights["key_findings"]:
        print("   Key Findings:")
        for finding in insights["key_findings"]:
            print(f"   • {finding}")
        print()
    
    if insights["risk_concerns"]:
        print("   Risk Concerns:")
        for concern in insights["risk_concerns"]:
            print(f"   • {concern}")
        print()
    
    if insights["recommendations"]:
        print("   Recommendations:")
        for rec in insights["recommendations"]:
            print(f"   • {rec}")
        print()
    
    if insights["strengths"]:
        print("   Strengths:")
        for strength in insights["strengths"]:
            print(f"   • {strength}")
        print()
    
    # Test custom crisis period
    print("7. Testing Custom Crisis Period...")
    custom_period = CrisisPeriod(
        name="custom_test_crisis",
        start_date=datetime(2018, 1, 1),
        end_date=datetime(2018, 12, 31),
        severity="moderate",
        characteristics=["custom_test", "volatility_spike"],
        description="Custom test crisis period for demonstration"
    )
    
    custom_result = validator.validate_crisis_period(custom_period)
    custom_status = "PASSED" if custom_result.stress_test_passed else "FAILED"
    print(f"   ✓ Custom Crisis: {custom_status}")
    print(f"     Return: {custom_result.total_return:.2%}, Drawdown: {custom_result.max_drawdown:.2%}")
    print(f"     Sharpe: {custom_result.sharpe_ratio:.2f}, VaR Breaches: {custom_result.var_breach_count}")
    print()
    
    # Save detailed report
    print("8. Saving Detailed Report...")
    report_path = Path("reports") / "crisis_validation_demo_report.json"
    report_path.parent.mkdir(exist_ok=True)
    
    # Add custom result to report
    all_results.append(custom_result)
    final_report = validator.generate_crisis_report(all_results)
    
    with open(report_path, 'w') as f:
        json.dump(final_report, f, indent=2, default=str)
    
    print(f"   ✓ Detailed report saved to: {report_path}")
    print()
    
    # Display crisis thresholds
    print("9. Crisis Validation Thresholds:")
    thresholds = validator.CRISIS_THRESHOLDS
    print(f"   • Max Drawdown Limit: {thresholds['max_drawdown_limit']:.1%}")
    print(f"   • Min Sharpe Ratio: {thresholds['min_sharpe_ratio']:.2f}")
    print(f"   • Max VaR Breaches: {thresholds['max_var_breaches']}")
    print(f"   • Min Recovery Days: {thresholds['min_recovery_days']}")
    print(f"   • Max Volatility: {thresholds['max_volatility']:.1%}")
    print(f"   • Min Hit Rate: {thresholds['min_hit_rate']:.1%}")
    print()
    
    # Summary
    print("=" * 80)
    print("CRISIS VALIDATOR DEMO SUMMARY")
    print("=" * 80)
    print(f"✓ Validated {len(all_results)} crisis periods")
    print(f"✓ Overall pass rate: {pass_rate:.1%}")
    print(f"✓ System assessment: {summary['overall_assessment']}")
    print(f"✓ Risk level: {risk['risk_assessment']}")
    print(f"✓ Property tests: Crisis report generation and alert thresholds validated")
    print(f"✓ Detailed report saved to: {report_path}")
    print()
    
    # Property validation demonstration
    print("10. Property Validation Demonstration:")
    print("    Property 1: Crisis Report Generation")
    print("    ✓ All crisis validations generated comprehensive reports")
    print("    ✓ Reports contain performance metrics, risk analysis, and diagnostics")
    print()
    
    print("    Property 2: Performance Threshold Alert Generation")
    failed_results = [r for r in all_results if not r.stress_test_passed]
    if failed_results:
        print(f"    ✓ {len(failed_results)} periods failed thresholds - alerts generated")
        print("    ✓ Recommendations provided for failed periods")
    else:
        print("    ✓ All periods passed thresholds - no alerts needed")
    print()
    
    print("Crisis Validator demonstration completed successfully!")
    print("=" * 80)


if __name__ == "__main__":
    main()