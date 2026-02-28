#!/usr/bin/env python3
"""
Demo Script for Task 4: Backtest Orchestrator

This script demonstrates the comprehensive backtesting capabilities including:
- Multi-year historical simulations
- Simultaneous intelligence engine coordination  
- Performance attribution analysis
- Risk management validation
- Comprehensive reporting

Usage:
    python scripts/demo_task4_backtest_orchestrator.py
"""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent))

from src.operation.backtest_orchestrator import BacktestOrchestrator
from src.operation.base_types import BacktestConfig
from datetime import datetime, timedelta
import json
import pandas as pd
import numpy as np


def create_demo_data():
    """Create demo data for backtesting if not available."""
    print("🔧 Creating demo data for backtesting...")
    
    # Create directories
    os.makedirs('data/processed', exist_ok=True)
    
    # Create sample price data
    dates = pd.date_range(start='2020-01-01', end='2023-12-31', freq='D')
    tickers = ['RELIANCE', 'TCS', 'HDFCBANK', 'INFY', 'HINDUNILVR', 
               'ICICIBANK', 'KOTAKBANK', 'BHARTIARTL', 'ITC', 'SBIN']
    
    # Generate realistic price data with different characteristics
    np.random.seed(42)
    price_data = []
    
    for ticker in tickers:
        base_price = np.random.uniform(100, 2000)  # Different starting prices
        volatility = np.random.uniform(0.15, 0.35)  # Different volatilities
        drift = np.random.uniform(-0.0002, 0.0008)  # Different drifts
        
        for date in dates:
            # Random walk with drift and volatility
            daily_return = np.random.normal(drift, volatility / np.sqrt(252))
            base_price *= (1 + daily_return)
            
            price_data.append({
                'Date': date,
                'ticker': ticker,
                'Close': base_price,
                'Volume': np.random.randint(100000, 10000000)
            })
    
    prices_df = pd.DataFrame(price_data)
    prices_df.to_parquet('data/processed/prices.parquet', index=False)
    print(f"   ✅ Created price data: {len(prices_df)} records")
    
    # Create sample market state data
    market_data = []
    regimes = ['bull', 'bear', 'sideways']
    vol_regimes = ['low', 'medium', 'high']
    
    for date in dates:
        # Create some persistence in regimes
        if len(market_data) > 0:
            prev_regime = market_data[-1]['macro_regime']
            # 80% chance to stay in same regime
            if np.random.random() < 0.8:
                current_regime = prev_regime
            else:
                current_regime = np.random.choice(regimes)
        else:
            current_regime = np.random.choice(regimes)
        
        market_data.append({
            'Date': date,
            'macro_regime': current_regime,
            'vol_regime': np.random.choice(vol_regimes),
            'liquidity_regime': np.random.choice(['high', 'medium', 'low']),
            'risk_on_probability': np.random.uniform(0.2, 0.8),
            'vix_level': np.random.uniform(12, 35),
            'yield_curve_slope': np.random.uniform(-0.5, 2.5)
        })
    
    market_df = pd.DataFrame(market_data)
    market_df.to_parquet('data/processed/market_state.parquet', index=False)
    print(f"   ✅ Created market state data: {len(market_df)} records")


def demo_multi_year_backtest():
    """Demonstrate multi-year backtesting across all engines."""
    print("\n" + "="*60)
    print("🧪 DEMO: Multi-Year Backtest Execution")
    print("="*60)
    
    orchestrator = BacktestOrchestrator()
    
    # Configure backtest
    config = BacktestConfig(
        start_date=datetime(2021, 1, 1),
        end_date=datetime(2023, 12, 31),
        initial_capital=1000000.0,
        rebalance_frequency="weekly",
        transaction_cost_bps=15.0,
        max_position_size=0.08,
        max_sector_exposure=0.30,
        benchmark="NIFTY50"
    )
    
    print(f"📅 Backtest Period: {config.start_date.date()} to {config.end_date.date()}")
    print(f"💰 Initial Capital: ₹{config.initial_capital:,.0f}")
    print(f"🔄 Rebalance Frequency: {config.rebalance_frequency}")
    print(f"💸 Transaction Costs: {config.transaction_cost_bps} bps")
    
    # Run multi-year backtest
    results = orchestrator.run_multi_year_backtest(config)
    
    print(f"\n📊 BACKTEST RESULTS:")
    print(f"   Engines Tested: {len(results)}")
    
    if results:
        # Display results
        passed_count = sum(1 for r in results if r.validation_passed)
        print(f"   Validation Pass Rate: {passed_count}/{len(results)} ({passed_count/len(results):.1%})")
        
        # Top performers
        by_return = sorted(results, key=lambda x: x.total_return, reverse=True)
        by_sharpe = sorted(results, key=lambda x: x.sharpe_ratio, reverse=True)
        
        print(f"\n🏆 TOP PERFORMERS:")
        print(f"   Best Return: {by_return[0].engine_name} ({by_return[0].total_return:.2%})")
        print(f"   Best Sharpe: {by_sharpe[0].engine_name} ({by_sharpe[0].sharpe_ratio:.2f})")
        
        # Performance summary
        avg_return = np.mean([r.total_return for r in results])
        avg_sharpe = np.mean([r.sharpe_ratio for r in results])
        avg_drawdown = np.mean([r.max_drawdown for r in results])
        
        print(f"\n📈 AGGREGATE PERFORMANCE:")
        print(f"   Average Return: {avg_return:.2%}")
        print(f"   Average Sharpe: {avg_sharpe:.2f}")
        print(f"   Average Max Drawdown: {avg_drawdown:.2%}")
    
    return results


def demo_regime_specific_backtests():
    """Demonstrate regime-specific backtesting."""
    print("\n" + "="*60)
    print("🎯 DEMO: Regime-Specific Backtests")
    print("="*60)
    
    orchestrator = BacktestOrchestrator()
    
    # Test different market regimes
    regimes = ['bull', 'bear', 'sideways']
    regime_results = orchestrator.run_regime_specific_backtests(regimes)
    
    print(f"📊 REGIME-SPECIFIC RESULTS:")
    
    for regime, results in regime_results.items():
        if results:
            avg_return = np.mean([r.total_return for r in results])
            avg_sharpe = np.mean([r.sharpe_ratio for r in results])
            best_engine = max(results, key=lambda x: x.sharpe_ratio)
            
            print(f"\n🎪 {regime.upper()} MARKET:")
            print(f"   Engines Tested: {len(results)}")
            print(f"   Average Return: {avg_return:.2%}")
            print(f"   Average Sharpe: {avg_sharpe:.2f}")
            print(f"   Best Engine: {best_engine.engine_name} (Sharpe: {best_engine.sharpe_ratio:.2f})")
        else:
            print(f"\n🎪 {regime.upper()} MARKET: No data available")
    
    return regime_results


def demo_performance_attribution():
    """Demonstrate comprehensive performance attribution."""
    print("\n" + "="*60)
    print("🔍 DEMO: Performance Attribution Analysis")
    print("="*60)
    
    orchestrator = BacktestOrchestrator()
    
    # Run backtest to get results
    results = orchestrator.run_multi_year_backtest()
    
    if not results:
        print("❌ No backtest results available for attribution")
        return None
    
    # Build comprehensive attribution system
    attribution_system = orchestrator.build_performance_attribution_system(results)
    
    print(f"📊 ATTRIBUTION ANALYSIS COMPLETE:")
    
    # Strategy-level attribution
    strategy_attr = attribution_system.get("strategy_level_attribution", {})
    print(f"\n🎯 STRATEGY-LEVEL ATTRIBUTION:")
    print(f"   Strategies Analyzed: {len(strategy_attr)}")
    
    if strategy_attr:
        # Find best risk-adjusted performer
        best_risk_adj = max(strategy_attr.items(), 
                           key=lambda x: x[1].get('risk_adjusted_contribution', 0))
        print(f"   Best Risk-Adjusted: {best_risk_adj[0]} ({best_risk_adj[1]['risk_adjusted_contribution']:.3f})")
    
    # Factor-level attribution
    factor_attr = attribution_system.get("factor_level_attribution", {})
    print(f"\n📈 FACTOR-LEVEL ATTRIBUTION:")
    
    for factor_name, factor_data in factor_attr.items():
        if isinstance(factor_data, dict) and 'average_contribution' in factor_data:
            contrib = factor_data['average_contribution']
            consistency = factor_data.get('consistency', 0)
            print(f"   {factor_name.replace('_', ' ').title()}: {contrib:.3f} (consistency: {consistency:.2f})")
    
    # Alpha/Beta decomposition
    alpha_beta = attribution_system.get("alpha_beta_decomposition", {})
    print(f"\n🔬 ALPHA/BETA DECOMPOSITION:")
    
    if alpha_beta:
        print(f"   Average Alpha: {alpha_beta.get('average_alpha', 0):.3f}")
        print(f"   Average Beta: {alpha_beta.get('average_beta', 1):.3f}")
        print(f"   Alpha Consistency: {alpha_beta.get('alpha_consistency', 0):.2f}")
        
        pure_alpha = alpha_beta.get('pure_alpha_strategies', [])
        if pure_alpha:
            print(f"   Pure Alpha Strategies: {', '.join(pure_alpha[:3])}")
    
    # Risk attribution
    risk_attr = attribution_system.get("risk_attribution", {})
    print(f"\n⚠️ RISK ATTRIBUTION:")
    
    if risk_attr:
        print(f"   Average Volatility: {risk_attr.get('average_volatility', 0):.3f}")
        print(f"   Average Max Drawdown: {risk_attr.get('average_max_drawdown', 0):.3f}")
        
        low_risk = risk_attr.get('low_risk_strategies', [])
        if low_risk:
            print(f"   Low Risk Strategies: {', '.join(low_risk[:3])}")
    
    # Summary insights
    insights = attribution_system.get("summary_insights", {})
    print(f"\n💡 KEY INSIGHTS:")
    
    for insight_type, insight_list in insights.items():
        if insight_list:
            print(f"   {insight_type.replace('_', ' ').title()}:")
            for insight in insight_list[:2]:  # Show top 2 insights
                print(f"     • {insight}")
    
    return attribution_system


def demo_risk_management_validation():
    """Demonstrate risk management validation during backtests."""
    print("\n" + "="*60)
    print("🛡️ DEMO: Risk Management Validation")
    print("="*60)
    
    orchestrator = BacktestOrchestrator()
    
    # Run backtest to get results
    results = orchestrator.run_multi_year_backtest()
    
    if not results:
        print("❌ No backtest results available for risk validation")
        return None
    
    # Validate risk management
    risk_validation = orchestrator.validate_risk_management(results)
    
    print(f"📊 RISK MANAGEMENT VALIDATION:")
    print(f"   Overall Status: {'✅ PASSED' if risk_validation['overall_passed'] else '❌ FAILED'}")
    
    # Engine-specific validations
    engine_validations = risk_validation.get("engine_validations", {})
    passed_engines = sum(1 for v in engine_validations.values() if v.get('passed', False))
    
    print(f"   Engines Passed: {passed_engines}/{len(engine_validations)}")
    
    # Risk violations
    violations = risk_validation.get("risk_violations", [])
    if violations:
        print(f"\n⚠️ RISK VIOLATIONS:")
        for violation in violations[:3]:  # Show top 3
            engine = violation.get('engine', 'Unknown')
            issues = violation.get('violations', [])
            print(f"   {engine}: {', '.join(issues)}")
    
    # Recommendations
    recommendations = risk_validation.get("recommendations", [])
    if recommendations:
        print(f"\n💡 RECOMMENDATIONS:")
        for rec in recommendations[:3]:  # Show top 3
            print(f"   • {rec}")
    
    return risk_validation


def demo_comprehensive_reporting():
    """Demonstrate comprehensive backtest reporting."""
    print("\n" + "="*60)
    print("📋 DEMO: Comprehensive Backtest Reporting")
    print("="*60)
    
    orchestrator = BacktestOrchestrator()
    
    # Run backtest to get results
    results = orchestrator.run_multi_year_backtest()
    
    if not results:
        print("❌ No backtest results available for reporting")
        return None
    
    # Generate comprehensive report
    report = orchestrator.generate_backtest_report(results)
    
    print(f"📊 COMPREHENSIVE BACKTEST REPORT:")
    
    # Summary
    summary = report.get("summary", {})
    print(f"\n📈 SUMMARY:")
    print(f"   Total Engines: {summary.get('total_engines_tested', 0)}")
    print(f"   Pass Rate: {summary.get('pass_rate', 0):.1%}")
    print(f"   Assessment: {summary.get('overall_assessment', 'Unknown')}")
    
    # Performance metrics
    perf_metrics = report.get("performance_metrics", {})
    print(f"\n💰 PERFORMANCE METRICS:")
    print(f"   Average Return: {perf_metrics.get('average_total_return', 0):.2%}")
    print(f"   Average Sharpe: {perf_metrics.get('average_sharpe_ratio', 0):.2f}")
    print(f"   Average Drawdown: {perf_metrics.get('average_max_drawdown', 0):.2%}")
    print(f"   Average Volatility: {perf_metrics.get('average_volatility', 0):.2%}")
    
    # Top performers
    top_performers = report.get("top_performers", {})
    print(f"\n🏆 TOP PERFORMERS:")
    
    best_return = top_performers.get("best_return", {})
    if best_return:
        print(f"   Best Return: {best_return.get('engine', 'N/A')} ({best_return.get('return', 0):.2%})")
    
    best_sharpe = top_performers.get("best_sharpe", {})
    if best_sharpe:
        print(f"   Best Sharpe: {best_sharpe.get('engine', 'N/A')} ({best_sharpe.get('sharpe', 0):.2f})")
    
    # Insights
    insights = report.get("insights_and_recommendations", {})
    print(f"\n💡 KEY INSIGHTS:")
    
    key_findings = insights.get("key_findings", [])
    for finding in key_findings[:2]:
        print(f"   • {finding}")
    
    recommendations = insights.get("recommendations", [])
    if recommendations:
        print(f"\n🎯 RECOMMENDATIONS:")
        for rec in recommendations[:2]:
            print(f"   • {rec}")
    
    print(f"\n📄 Report generated at: {report.get('generated_at', 'Unknown')}")
    
    return report


def main():
    """Main demo execution."""
    print("🚀 NORTHSTAR V3 BACKTEST ORCHESTRATOR DEMO")
    print("="*60)
    print("Demonstrating comprehensive backtesting capabilities")
    print("including multi-year simulations, attribution analysis,")
    print("and risk management validation.")
    
    # Create demo data if needed
    if not os.path.exists('data/processed/prices.parquet'):
        create_demo_data()
    
    try:
        # Demo 1: Multi-year backtest
        backtest_results = demo_multi_year_backtest()
        
        # Demo 2: Regime-specific backtests
        regime_results = demo_regime_specific_backtests()
        
        # Demo 3: Performance attribution
        attribution_results = demo_performance_attribution()
        
        # Demo 4: Risk management validation
        risk_results = demo_risk_management_validation()
        
        # Demo 5: Comprehensive reporting
        report_results = demo_comprehensive_reporting()
        
        print("\n" + "="*60)
        print("🎉 DEMO COMPLETE!")
        print("="*60)
        print("✅ Multi-year backtesting demonstrated")
        print("✅ Regime-specific analysis demonstrated")
        print("✅ Performance attribution demonstrated")
        print("✅ Risk management validation demonstrated")
        print("✅ Comprehensive reporting demonstrated")
        
        print(f"\n📊 SUMMARY:")
        if backtest_results:
            print(f"   Engines tested: {len(backtest_results)}")
            passed = sum(1 for r in backtest_results if r.validation_passed)
            print(f"   Validation pass rate: {passed}/{len(backtest_results)} ({passed/len(backtest_results):.1%})")
        
        print(f"\n🎯 Task 4 (Backtest Orchestrator) capabilities demonstrated successfully!")
        
    except Exception as e:
        print(f"\n❌ Demo failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)