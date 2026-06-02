#!/usr/bin/env python3
"""
Test every chart function and identify issues
"""

import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Import all chart functions
from src.dashboard.charts.chart_library import *

def load_test_data():
    """Load actual data files"""
    data_dir = PROJECT_ROOT / "data"
    
    # Load NAV history
    nav_df = pd.read_parquet(data_dir / "nav_history.parquet")
    print(f"✅ Loaded NAV: {len(nav_df)} records, columns: {list(nav_df.columns)}")
    
    # Load regime history
    regime_df = pd.read_parquet(data_dir / "regime_history.parquet")
    print(f"✅ Loaded Regime: {len(regime_df)} records, columns: {list(regime_df.columns)}")
    
    # Load benchmark
    benchmark_df = pd.read_parquet(data_dir / "benchmark_nifty50.parquet")
    print(f"✅ Loaded Benchmark: {len(benchmark_df)} records, columns: {list(benchmark_df.columns)}")
    
    return nav_df, regime_df, benchmark_df

def test_performance_charts(nav_df, benchmark_df):
    """Test all 15 performance charts"""
    print("\n" + "="*60)
    print("TESTING PERFORMANCE CHARTS (15)")
    print("="*60)
    
    charts = [
        ("Capital Curve", lambda: chart_capital_curve(nav_df)),
        ("Rolling Sharpe", lambda: chart_rolling_sharpe(nav_df)),
        ("Max Drawdown", lambda: chart_max_drawdown(nav_df)),
        ("Survival Probability", lambda: chart_survival_probability(nav_df)),
        ("Daily Returns Dist", lambda: chart_daily_returns_dist(nav_df)),
        ("Monthly Heatmap", lambda: chart_monthly_returns_heatmap(nav_df)),
        ("Cumulative vs Benchmark", lambda: chart_cumulative_vs_benchmark(nav_df, benchmark_df)),
        ("Rolling Volatility", lambda: chart_rolling_volatility(nav_df)),
        ("Win Rate", lambda: chart_win_rate(nav_df)),
        ("Profit Factor", lambda: chart_profit_factor(nav_df)),
        ("Risk-Adjusted Returns", lambda: chart_risk_adjusted_returns(nav_df)),
        ("Drawdown Duration", lambda: chart_drawdown_duration(nav_df)),
        ("NAV History", lambda: chart_nav_history(nav_df)),
        ("Underwater Plot", lambda: chart_underwater_plot(nav_df)),
        ("Returns Quantiles", lambda: chart_returns_quantiles(nav_df)),
    ]
    
    results = []
    for name, func in charts:
        try:
            fig = func()
            if fig is None:
                results.append((name, "❌ FAIL", "Returned None"))
            else:
                results.append((name, "✅ PASS", "OK"))
        except Exception as e:
            results.append((name, "❌ FAIL", str(e)[:50]))
    
    for name, status, msg in results:
        print(f"{status} {name:30s} {msg}")
    
    return results

def test_intelligence_charts(regime_df, nav_df):
    """Test all 12 intelligence charts"""
    print("\n" + "="*60)
    print("TESTING INTELLIGENCE CHARTS (12)")
    print("="*60)
    
    charts = [
        ("Regime Timeline", lambda: chart_regime_timeline(regime_df)),
        ("Transition Matrix", lambda: chart_regime_transition_matrix(regime_df)),
        ("Sentiment Score", lambda: chart_sentiment_score(regime_df)),
        ("Sentiment Polarity", lambda: chart_sentiment_polarity(regime_df)),
        ("Sentiment Conviction", lambda: chart_sentiment_conviction(regime_df)),
        ("Narrative Strength", lambda: chart_narrative_strength(regime_df)),
        ("Macro Driver Heatmap", lambda: chart_macro_driver_heatmap(regime_df)),
        ("Macro Changes", lambda: chart_macro_changes(regime_df)),
        ("Regime Stability", lambda: chart_regime_stability(regime_df)),
        ("Intelligence Freshness", lambda: chart_intelligence_freshness(regime_df)),
        ("Sentiment-Returns Corr", lambda: chart_sentiment_returns_correlation(regime_df, nav_df)),
        ("Regime Duration", lambda: chart_regime_duration_dist(regime_df)),
    ]
    
    results = []
    for name, func in charts:
        try:
            fig = func()
            if fig is None:
                results.append((name, "❌ FAIL", "Returned None"))
            else:
                results.append((name, "✅ PASS", "OK"))
        except Exception as e:
            results.append((name, "❌ FAIL", str(e)[:50]))
    
    for name, status, msg in results:
        print(f"{status} {name:30s} {msg}")
    
    return results

def main():
    print("="*60)
    print("DASHBOARD CHART TESTING")
    print("="*60)
    
    # Load data
    nav_df, regime_df, benchmark_df = load_test_data()
    
    # Test performance charts
    perf_results = test_performance_charts(nav_df, benchmark_df)
    
    # Test intelligence charts
    intel_results = test_intelligence_charts(regime_df, nav_df)
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    all_results = perf_results + intel_results
    passed = sum(1 for _, status, _ in all_results if "PASS" in status)
    failed = sum(1 for _, status, _ in all_results if "FAIL" in status)
    
    print(f"Total: {len(all_results)} charts")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"Success Rate: {passed/len(all_results)*100:.1f}%")
    
    if failed > 0:
        print("\nFailed charts:")
        for name, status, msg in all_results:
            if "FAIL" in status:
                print(f"  - {name}: {msg}")

if __name__ == "__main__":
    main()
