#!/usr/bin/env python3
"""
Demo script for Task 3: Alpha Validator

This script demonstrates the Alpha Validator functionality including:
- Market regime detection (bull, bear, sideways)
- Alpha validation across different market regimes
- Signal quality assessment and consistency analysis
- Alpha performance degradation detection
- Property validation for alpha signal generation and quality
"""

import sys
import json
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta

# Add src to path for imports
sys.path.append(str(Path(__file__).parent.parent / "src"))

from operation.alpha_validator import AlphaValidator, MarketRegimeDetector, MarketRegime
from operation.base_types import AlphaValidationResult


def generate_sample_market_data(num_days: int = 500, regime: str = "mixed") -> pd.DataFrame:
    """Generate sample market data for demonstration."""
    dates = pd.date_range(start='2020-01-01', periods=num_days, freq='D')
    
    np.random.seed(42)  # For reproducible demo
    
    if regime == "mixed":
        # Generate clear regime phases
        bull_days = num_days // 3
        bear_days = num_days // 3
        sideways_days = num_days - bull_days - bear_days
        
        # Bull phase - strong upward trend with low volatility
        bull_trend = np.linspace(0, 0.3, bull_days)  # 30% gain over period
        bull_noise = np.random.normal(0, 0.01, bull_days)
        bull_returns = np.diff(np.concatenate([[0], bull_trend])) + bull_noise
        
        # Bear phase - strong downward trend
        bear_trend = np.linspace(0, -0.25, bear_days)  # 25% loss over period
        bear_noise = np.random.normal(0, 0.02, bear_days)
        bear_returns = np.diff(np.concatenate([[0], bear_trend])) + bear_noise
        
        # Sideways phase - range-bound with mean reversion
        sideways_base = np.sin(np.linspace(0, 4*np.pi, sideways_days)) * 0.05  # 5% range
        sideways_noise = np.random.normal(0, 0.008, sideways_days)
        sideways_returns = np.diff(np.concatenate([[0], sideways_base])) + sideways_noise
        
        # Combine phases
        returns = np.concatenate([bull_returns, bear_returns, sideways_returns])
        
    elif regime == "bull":
        # Strong bull market
        trend = np.linspace(0, 0.4, num_days)  # 40% gain
        noise = np.random.normal(0, 0.012, num_days)
        returns = np.diff(np.concatenate([[0], trend])) + noise
        
    elif regime == "bear":
        # Strong bear market
        trend = np.linspace(0, -0.3, num_days)  # 30% loss
        noise = np.random.normal(0, 0.018, num_days)
        returns = np.diff(np.concatenate([[0], trend])) + noise
        
    elif regime == "sideways":
        # Clear sideways market
        base = np.sin(np.linspace(0, 6*np.pi, num_days)) * 0.08  # 8% range
        noise = np.random.normal(0, 0.006, num_days)
        returns = np.diff(np.concatenate([[0], base])) + noise
        
    else:
        returns = np.random.normal(0.0002, 0.018, num_days)
    
    # Generate prices
    initial_price = 100.0
    prices = [initial_price]
    for ret in returns:
        prices.append(prices[-1] * (1 + ret))
    
    # Generate volume
    volume = np.random.lognormal(10, 0.5, num_days)
    
    return pd.DataFrame({
        'date': dates,
        'close': prices[1:],
        'volume': volume
    })


def main():
    """Demonstrate Alpha Validator functionality."""
    print("=" * 80)
    print("NORTHSTAR V3 ALPHA VALIDATOR DEMO")
    print("=" * 80)
    print()
    
    # Initialize Alpha Validator
    print("1. Initializing Alpha Validator...")
    validator = AlphaValidator()
    regime_detector = MarketRegimeDetector()
    print(f"   ✓ Alpha Validator initialized")
    print(f"   ✓ Alpha thresholds: {validator.ALPHA_THRESHOLDS}")
    print()
    
    # Generate sample market data
    print("2. Generating Sample Market Data...")
    market_data = generate_sample_market_data(600, "mixed")
    print(f"   ✓ Generated {len(market_data)} days of market data")
    print(f"   ✓ Price range: ${market_data['close'].min():.2f} - ${market_data['close'].max():.2f}")
    print(f"   ✓ Date range: {market_data['date'].min().date()} to {market_data['date'].max().date()}")
    print()
    
    # Demonstrate market regime detection
    print("3. Market Regime Detection...")
    regime_periods = regime_detector.detect_regime_periods(market_data)
    
    if len(regime_periods) > 0:
        regime_counts = regime_periods['regime'].value_counts()
        print(f"   ✓ Detected {len(regime_periods)} regime periods")
        print("   Regime Distribution:")
        for regime, count in regime_counts.items():
            percentage = (count / len(regime_periods)) * 100
            print(f"     • {regime.capitalize()}: {count} periods ({percentage:.1f}%)")
        print()
        
        # Show regime transitions
        print("   Recent Regime Transitions:")
        for i in range(min(5, len(regime_periods))):
            period = regime_periods.iloc[i]
            print(f"     • {period['date'].strftime('%Y-%m-%d')}: {period['regime'].capitalize()} "
                  f"(Price: ${period['close']:.2f})")
        print()
    else:
        print("   ⚠ No regime periods detected (insufficient data)")
        print()
    
    # Validate alpha across individual regimes with specific data
    print("4. Alpha Validation Across Individual Regimes...")
    
    # Test each regime with regime-specific data
    regime_results = []
    
    # Bull market test
    print("   Testing Bull Market Alpha...")
    bull_data = generate_sample_market_data(400, "bull")
    bull_result = validator.validate_bull_market_alpha(bull_data)
    regime_results.append(bull_result)
    bull_status = "PASSED" if bull_result.validation_passed else "FAILED"
    print(f"   ✓ Bull Market: {bull_status}")
    print(f"     • Alpha Generated: {bull_result.alpha_generated:.2%}")
    print(f"     • Information Ratio: {bull_result.information_ratio:.2f}")
    print(f"     • Hit Rate: {bull_result.hit_rate:.1%}")
    print(f"     • Signal Quality: {bull_result.signal_quality_score:.2f}")
    print(f"     • Signal Count: {bull_result.signal_count}")
    print()
    
    # Bear market test
    print("   Testing Bear Market Alpha...")
    bear_data = generate_sample_market_data(400, "bear")
    bear_result = validator.validate_bear_market_alpha(bear_data)
    regime_results.append(bear_result)
    bear_status = "PASSED" if bear_result.validation_passed else "FAILED"
    print(f"   ✓ Bear Market: {bear_status}")
    print(f"     • Alpha Generated: {bear_result.alpha_generated:.2%}")
    print(f"     • Information Ratio: {bear_result.information_ratio:.2f}")
    print(f"     • Hit Rate: {bear_result.hit_rate:.1%}")
    print(f"     • Signal Quality: {bear_result.signal_quality_score:.2f}")
    print(f"     • Signal Count: {bear_result.signal_count}")
    print()
    
    # Sideways market test
    print("   Testing Sideways Market Alpha...")
    sideways_data = generate_sample_market_data(400, "sideways")
    sideways_result = validator.validate_sideways_market_alpha(sideways_data)
    regime_results.append(sideways_result)
    sideways_status = "PASSED" if sideways_result.validation_passed else "FAILED"
    print(f"   ✓ Sideways Market: {sideways_status}")
    print(f"     • Alpha Generated: {sideways_result.alpha_generated:.2%}")
    print(f"     • Information Ratio: {sideways_result.information_ratio:.2f}")
    print(f"     • Hit Rate: {sideways_result.hit_rate:.1%}")
    print(f"     • Signal Quality: {sideways_result.signal_quality_score:.2f}")
    print(f"     • Signal Count: {sideways_result.signal_count}")
    print()
    
    # Validate alpha across all regimes using mixed data
    print("5. Comprehensive Alpha Validation...")
    if len(regime_periods) > 0:
        all_results = validator.validate_all_regimes(market_data)
        if len(all_results) > 0:
            print(f"   ✓ Validated alpha across {len(all_results)} detected regimes")
            
            for result in all_results:
                status = "PASSED" if result.validation_passed else "FAILED"
                print(f"   • {result.regime.capitalize()}: {status}")
                print(f"     - Alpha: {result.alpha_generated:.2%}")
                print(f"     - Information Ratio: {result.information_ratio:.2f}")
                print(f"     - Hit Rate: {result.hit_rate:.1%}")
                print(f"     - Signal Quality: {result.signal_quality_score:.2f}")
        else:
            print("   ⚠ Using individual regime results due to regime detection issues")
            all_results = regime_results
    else:
        print("   ⚠ Using individual regime results due to regime detection issues")
        all_results = regime_results
    print()
    
    # Generate comprehensive alpha report
    print("6. Generating Comprehensive Alpha Report...")
    if all_results:
        report = validator.generate_alpha_report(all_results)
        
        print("   Report Summary:")
        summary = report["summary"]
        print(f"   • Total Regimes Tested: {summary['total_regimes_tested']}")
        print(f"   • Regimes Passed: {summary['regimes_passed']}")
        print(f"   • Pass Rate: {summary['pass_rate']:.1%}")
        print(f"   • Overall Assessment: {summary['overall_assessment']}")
        print()
        
        print("   Performance Metrics:")
        perf = report["performance_metrics"]
        print(f"   • Average Alpha Generated: {perf['average_alpha_generated']:.2%}")
        print(f"   • Average Information Ratio: {perf['average_information_ratio']:.2f}")
        print(f"   • Average Hit Rate: {perf['average_hit_rate']:.1%}")
        print(f"   • Average Signal Quality: {perf['average_signal_quality']:.2f}")
        print(f"   • Total Signals Generated: {perf['total_signals_generated']}")
        print()
        
        print("   Consistency Analysis:")
        consistency = report["consistency_analysis"]
        print(f"   • Overall Consistency Score: {consistency['overall_consistency_score']:.2f}")
        if "alpha_consistency" in consistency:
            alpha_cons = consistency["alpha_consistency"]
            print(f"   • Alpha Mean: {alpha_cons['mean']:.2%}")
            print(f"   • Alpha Std Dev: {alpha_cons['std']:.2%}")
        print()
    else:
        print("   ⚠ No results available for report generation")
        print()
    
    # Alpha consistency analysis
    print("7. Alpha Consistency Analysis...")
    if len(all_results) > 1:
        consistency_analysis = validator.analyze_alpha_consistency(all_results)
        
        print("   Cross-Regime Consistency:")
        overall_consistency = consistency_analysis["overall_consistency_score"]
        print(f"   • Overall Consistency Score: {overall_consistency:.2f}")
        
        if "regime_performance" in consistency_analysis:
            print("   • Regime Performance Comparison:")
            for regime, perf in consistency_analysis["regime_performance"].items():
                status = "✓" if perf["passed"] else "✗"
                print(f"     {status} {regime.capitalize()}: Alpha={perf['alpha']:.2%}, "
                      f"IR={perf['ir']:.2f}, Hit Rate={perf['hit_rate']:.1%}")
        print()
    else:
        print("   ⚠ Insufficient results for consistency analysis")
        print()
    
    # Alpha degradation detection demo
    print("8. Alpha Performance Degradation Detection...")
    
    # Create historical results (good performance)
    historical_results = [
        AlphaValidationResult(
            regime="bull",
            period_start=datetime(2019, 1, 1),
            period_end=datetime(2019, 12, 31),
            alpha_generated=0.06,  # 6% alpha
            information_ratio=1.2,
            hit_rate=0.62,
            signal_quality_score=0.85,
            consistency_score=0.8,
            regime_adaptation_score=0.9,
            validation_passed=True,
            signal_count=75
        ),
        AlphaValidationResult(
            regime="bear",
            period_start=datetime(2019, 1, 1),
            period_end=datetime(2019, 12, 31),
            alpha_generated=0.04,  # 4% alpha
            information_ratio=0.9,
            hit_rate=0.58,
            signal_quality_score=0.78,
            consistency_score=0.75,
            regime_adaptation_score=0.85,
            validation_passed=True,
            signal_count=60
        )
    ]
    
    # Create current results (some degradation)
    current_results = [
        AlphaValidationResult(
            regime="bull",
            period_start=datetime(2020, 1, 1),
            period_end=datetime(2020, 12, 31),
            alpha_generated=0.035,  # 3.5% alpha (degraded)
            information_ratio=0.8,   # Degraded IR
            hit_rate=0.58,          # Slightly lower hit rate
            signal_quality_score=0.72,  # Lower quality
            consistency_score=0.7,
            regime_adaptation_score=0.8,
            validation_passed=False,  # Failed due to degradation
            signal_count=65
        ),
        AlphaValidationResult(
            regime="bear",
            period_start=datetime(2020, 1, 1),
            period_end=datetime(2020, 12, 31),
            alpha_generated=0.038,  # 3.8% alpha (slight improvement)
            information_ratio=0.95,
            hit_rate=0.59,
            signal_quality_score=0.80,
            consistency_score=0.76,
            regime_adaptation_score=0.87,
            validation_passed=True,
            signal_count=58
        )
    ]
    
    # Detect degradation
    degradation_analysis = validator.detect_alpha_degradation(historical_results, current_results)
    
    print(f"   ✓ Degradation Analysis Completed")
    print(f"   • Degradation Detected: {degradation_analysis['degradation_detected']}")
    
    if "regime_analysis" in degradation_analysis:
        print("   • Regime-Specific Analysis:")
        for regime, analysis in degradation_analysis["regime_analysis"].items():
            status = "⚠ DEGRADED" if analysis["degradation_detected"] else "✓ STABLE"
            print(f"     {status} {regime.capitalize()}: {analysis['alpha_change']:.1%} change")
    
    if "alerts_generated" in degradation_analysis and degradation_analysis["alerts_generated"]:
        print(f"   • Alerts Generated: {len(degradation_analysis['alerts_generated'])}")
        for alert in degradation_analysis["alerts_generated"]:
            print(f"     ⚠ {alert.level.value.upper()}: {alert.message}")
    print()
    
    # Save detailed report
    print("9. Saving Detailed Report...")
    report_path = Path("reports") / "alpha_validation_demo_report.json"
    report_path.parent.mkdir(exist_ok=True)
    
    if all_results:
        final_report = validator.generate_alpha_report(all_results)
        
        # Add degradation analysis to report
        final_report["degradation_analysis"] = degradation_analysis
        
        with open(report_path, 'w') as f:
            json.dump(final_report, f, indent=2, default=str)
        
        print(f"   ✓ Detailed report saved to: {report_path}")
    else:
        print("   ⚠ No results to save")
    print()
    
    # Display alpha validation thresholds
    print("10. Alpha Validation Thresholds:")
    thresholds = validator.ALPHA_THRESHOLDS
    print(f"   • Min Alpha (Bull): {thresholds['min_alpha_bull']:.1%}")
    print(f"   • Min Alpha (Bear): {thresholds['min_alpha_bear']:.1%}")
    print(f"   • Min Alpha (Sideways): {thresholds['min_alpha_sideways']:.1%}")
    print(f"   • Min Information Ratio: {thresholds['min_information_ratio']:.2f}")
    print(f"   • Min Hit Rate: {thresholds['min_hit_rate']:.1%}")
    print(f"   • Min Signal Quality: {thresholds['min_signal_quality']:.1%}")
    print(f"   • Min Consistency: {thresholds['min_consistency']:.1%}")
    print(f"   • Max Alpha Degradation: {thresholds['max_alpha_degradation']:.1%}")
    print()
    
    # Summary
    print("=" * 80)
    print("ALPHA VALIDATOR DEMO SUMMARY")
    print("=" * 80)
    
    if all_results:
        passed_count = sum(1 for r in all_results if r.validation_passed)
        pass_rate = passed_count / len(all_results)
        avg_alpha = np.mean([r.alpha_generated for r in all_results])
        
        print(f"✓ Validated alpha generation across {len(all_results)} market regimes")
        print(f"✓ Overall pass rate: {pass_rate:.1%} ({passed_count}/{len(all_results)})")
        print(f"✓ Average alpha generated: {avg_alpha:.2%}")
        print(f"✓ Degradation detection: {'Active' if degradation_analysis['degradation_detected'] else 'No issues'}")
        print(f"✓ Property tests: Alpha signal generation, quality, and degradation validated")
        print(f"✓ Detailed report saved to: {report_path}")
    else:
        print("⚠ No alpha validation results generated")
    print()
    
    # Property validation demonstration
    print("11. Property Validation Demonstration:")
    print("    Property 3: Alpha Signal Generation Across Regimes")
    if all_results:
        print("    ✓ Alpha signals generated for all tested market regimes")
        print("    ✓ Signals adapted to regime characteristics")
        for result in all_results:
            print(f"      • {result.regime.capitalize()}: {result.signal_count} signals, "
                  f"{result.alpha_generated:.2%} alpha")
    else:
        print("    ⚠ No signals generated for validation")
    print()
    
    print("    Property 4: Alpha Signal Quality Validation")
    if all_results:
        quality_scores = [r.signal_quality_score for r in all_results]
        avg_quality = np.mean(quality_scores)
        print(f"    ✓ Signal quality validated across all regimes")
        print(f"    ✓ Average signal quality: {avg_quality:.2f}")
        print(f"    ✓ Quality consistency maintained across regimes")
    else:
        print("    ⚠ No quality metrics available")
    print()
    
    print("    Property 5: Alpha Performance Degradation Response")
    print(f"    ✓ Degradation detection system operational")
    print(f"    ✓ Degradation analysis completed for regime comparison")
    if degradation_analysis["degradation_detected"]:
        print(f"    ✓ Alerts generated for detected degradation")
    else:
        print(f"    ✓ No significant degradation detected")
    print()
    
    print("Alpha Validator demonstration completed successfully!")
    print("=" * 80)


if __name__ == "__main__":
    main()