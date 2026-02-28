#!/usr/bin/env python3
"""
🧠 MACRO TRANSMISSION ENGINE - DEMONSTRATION
Institutional probabilistic macro-equity intelligence

This demonstrates the evolution from static regressions to
probabilistic, time-varying, forward-looking macro intelligence.

Layers:
1. Bayesian Hierarchical Model → P(β > 0)
2. Kalman Filter → β_t trajectories
3. Bayesian VAR → E[ΔM]
4. Macro-Adjusted Alpha → α^{adj}
5. Stress Replay → Historical shocks

Usage:
    python examples/macro_transmission_engine_demo.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
from datetime import datetime

# Import MTE components
from src.macro_transmission_engine import (
    BayesianMacroTransmission,
    TimeVaryingBetaKalman,
    BayesianVARForecaster,
    MacroAlphaAdjuster,
    MacroStressReplay
)

# Import data loader from MIE
from src.macro_impact_engine import MacroDataLoader, MacroPreprocessor


def run_macro_transmission_demo():
    """
    Run complete macro transmission engine demo
    """
    
    print("=" * 80)
    print("🧠 MACRO TRANSMISSION ENGINE - INSTITUTIONAL DEMO")
    print("=" * 80)
    print(f"\nDemo Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # ========================================================================
    # STEP 1: LOAD AND PREPARE DATA
    # ========================================================================
    print("\n" + "=" * 80)
    print("STEP 1: DATA LOADING")
    print("=" * 80)
    
    loader = MacroDataLoader(target_frequency='W')
    
    try:
        data = loader.load_all(start_date="2020-01-01")
    except Exception as e:
        print(f"\n❌ Error loading data: {e}")
        print("\nUsing synthetic data for demo...")
        data = generate_synthetic_data()
    
    # Preprocess
    preprocessor = MacroPreprocessor(lags=[0], winsorize_pct=0.01)
    macro_processed, _ = preprocessor.preprocess_macro(
        data['macro'],
        make_stationary=True,
        standardize=True,
        construct_lags=False  # No lags for transmission engine
    )
    returns_processed = preprocessor.preprocess_returns(data['returns'])
    
    # Limit for demo
    macro_processed = macro_processed.iloc[:, :5]  # Top 5 macro factors
    returns_processed = returns_processed.iloc[:, :20]  # Top 20 companies
    
    print(f"\n   Macro factors: {len(macro_processed.columns)}")
    print(f"   Companies: {len(returns_processed.columns)}")
    print(f"   Time periods: {len(macro_processed)}")
    
    # ========================================================================
    # STEP 2: BAYESIAN HIERARCHICAL MODEL
    # ========================================================================
    print("\n" + "=" * 80)
    print("STEP 2: BAYESIAN HIERARCHICAL MODEL")
    print("=" * 80)
    
    try:
        bayesian_model = BayesianMacroTransmission(
            inference_method='svi',  # Fast variational inference
            num_samples=500
        )
        
        # Fit model
        bayesian_results = bayesian_model.fit_svi(
            returns_processed,
            macro_processed,
            data['sector_map'],
            num_steps=2000
        )
        
        # Get high-conviction relationships
        high_conviction = bayesian_model.get_high_conviction_relationships(threshold=0.85)
        
        print(f"\n   High-conviction relationships: {len(high_conviction)}")
        if not high_conviction.empty:
            print(f"\n   Top 5 by conviction:")
            for _, row in high_conviction.head(5).iterrows():
                print(f"      {row['ticker']} → {row['macro_variable']}: "
                      f"β={row['posterior_mean']:.3f}, P={row['conviction']:.3f}")
        
    except ImportError:
        print("\n   ⚠️ NumPyro not available, skipping Bayesian model")
        print("   Install with: pip install numpyro jax jaxlib")
        bayesian_results = None
    
    # ========================================================================
    # STEP 3: KALMAN FILTER (TIME-VARYING BETAS)
    # ========================================================================
    print("\n" + "=" * 80)
    print("STEP 3: KALMAN FILTER (TIME-VARYING BETAS)")
    print("=" * 80)
    
    kalman = TimeVaryingBetaKalman(Q_scale=0.001, R_scale=0.01)
    
    # Fit for all companies
    kalman_results = kalman.fit_all_companies(
        returns_processed,
        macro_processed,
        max_companies=10  # Limit for demo
    )
    
    print(f"\n   Fitted {len(kalman_results)} companies")
    
    # Show example trajectory
    if kalman_results:
        example_ticker = list(kalman_results.keys())[0]
        example_macro = macro_processed.columns[0]
        
        print(f"\n   Example: {example_ticker} sensitivity to {example_macro}")
        
        current_beta = kalman.get_current_beta(example_ticker)
        print(f"      Current betas: {current_beta.to_dict()}")
        
        # Detect regime transitions
        transitions = kalman.detect_regime_transitions(
            example_ticker,
            example_macro,
            threshold=2.0
        )
        
        if not transitions.empty:
            print(f"      Regime transitions detected: {len(transitions)}")
    
    # ========================================================================
    # STEP 4: BAYESIAN VAR FORECAST
    # ========================================================================
    print("\n" + "=" * 80)
    print("STEP 4: BAYESIAN VAR MACRO FORECAST")
    print("=" * 80)
    
    var_forecaster = BayesianVARForecaster(lags=1, num_samples=200)
    
    # Fit VAR
    var_results = var_forecaster.fit(macro_processed)
    
    # Generate forecast
    forecast_result = var_forecaster.forecast(macro_processed, horizon=4)
    
    print(f"\n   Forecast horizon: 4 periods")
    print(f"   Expected macro changes (1-period ahead):")
    
    expected_change = var_forecaster.get_expected_change(macro_processed, horizon=1)
    for macro_var, change in expected_change.items():
        print(f"      {macro_var}: {change:+.4f}")
    
    # ========================================================================
    # STEP 5: MACRO-ADJUSTED ALPHA
    # ========================================================================
    print("\n" + "=" * 80)
    print("STEP 5: MACRO-ADJUSTED ALPHA")
    print("=" * 80)
    
    # Generate synthetic raw alphas
    raw_alpha = pd.Series(
        np.random.randn(len(returns_processed.columns)) * 0.02,
        index=returns_processed.columns
    )
    
    # Create beta DataFrame from Kalman results
    beta_rows = []
    for ticker, result in kalman_results.items():
        if 'error' in result:
            continue
        current_betas = kalman.get_current_beta(ticker)
        for macro_var, beta in current_betas.items():
            beta_rows.append({
                'ticker': ticker,
                'macro_variable': macro_var,
                'beta': beta
            })
    
    beta_df = pd.DataFrame(beta_rows)
    
    # Adjust alpha
    adjuster = MacroAlphaAdjuster(adjustment_strength=0.5)
    
    adjusted_alpha_df = adjuster.adjust_alpha(
        raw_alpha,
        beta_df,
        expected_change
    )
    
    print(f"\n   Adjusted {len(adjusted_alpha_df)} alphas")
    print(f"\n   Top 5 macro adjustments:")
    top_adjustments = adjusted_alpha_df.nlargest(5, 'macro_adjustment')
    for _, row in top_adjustments.iterrows():
        print(f"      {row['ticker']}: raw={row['raw_alpha']:.4f}, "
              f"adj={row['macro_adjustment']:+.4f}, "
              f"final={row['adjusted_alpha']:.4f}")
    
    # ========================================================================
    # STEP 6: STRESS REPLAY
    # ========================================================================
    print("\n" + "=" * 80)
    print("STEP 6: MACRO STRESS REPLAY")
    print("=" * 80)
    
    stress_engine = MacroStressReplay()
    
    # Define 2020 COVID shock
    covid_shock = {
        macro_processed.columns[0]: -2.0,  # Growth shock
        macro_processed.columns[1]: +1.5,  # Volatility spike
        macro_processed.columns[2]: -1.0,  # Liquidity shock
    }
    
    stress_engine.define_shock('2020_covid_demo', covid_shock)
    
    # Replay shock
    stress_result = stress_engine.replay_shock(
        '2020_covid_demo',
        beta_df
    )
    
    print(f"\n   Scenario: 2020 COVID Demo")
    print(f"   Worst impacted stocks:")
    for ticker, impact in stress_result['worst_stocks'][:5]:
        print(f"      {ticker}: {impact:+.2%}")
    
    print(f"\n   Best positioned stocks:")
    for ticker, impact in stress_result['best_stocks'][:5]:
        print(f"      {ticker}: {impact:+.2%}")
    
    # ========================================================================
    # SUMMARY
    # ========================================================================
    print("\n" + "=" * 80)
    print("✅ MACRO TRANSMISSION ENGINE DEMO COMPLETE")
    print("=" * 80)
    
    print(f"\n📊 Summary:")
    print(f"   ✓ Bayesian hierarchical model: {'Fitted' if bayesian_results else 'Skipped'}")
    print(f"   ✓ Kalman filter: {len(kalman_results)} companies")
    print(f"   ✓ VAR forecast: 4-period ahead")
    print(f"   ✓ Alpha adjustment: {len(adjusted_alpha_df)} signals")
    print(f"   ✓ Stress replay: 1 scenario")
    
    print(f"\n🎯 Key Insights:")
    print(f"   - Time-varying betas reveal regime transitions")
    print(f"   - Macro forecasts enable forward-looking positioning")
    print(f"   - Probabilistic inference provides conviction scores")
    print(f"   - Stress testing identifies vulnerabilities")
    
    return {
        'bayesian_results': bayesian_results,
        'kalman_results': kalman_results,
        'var_results': var_results,
        'adjusted_alpha': adjusted_alpha_df,
        'stress_results': stress_result
    }


def generate_synthetic_data():
    """Generate synthetic data for demo"""
    print("\n   Generating synthetic data...")
    
    dates = pd.date_range('2020-01-01', '2023-12-31', freq='W')
    
    # Synthetic macro data
    macro_data = {}
    for i in range(5):
        macro_data[f'macro_{i}'] = np.cumsum(np.random.randn(len(dates))) * 0.01
    
    macro_df = pd.DataFrame(macro_data, index=dates)
    
    # Synthetic returns
    returns_data = {}
    for i in range(20):
        returns_data[f'STOCK_{i}'] = np.random.randn(len(dates)) * 0.02
    
    returns_df = pd.DataFrame(returns_data, index=dates)
    
    # Synthetic sector map
    sector_map = {f'STOCK_{i}': f'Sector_{i%4}' for i in range(20)}
    
    return {
        'macro': macro_df,
        'returns': returns_df,
        'market': None,
        'sector_map': sector_map
    }


if __name__ == "__main__":
    results = run_macro_transmission_demo()
    print("\n🎉 Demo complete!")
