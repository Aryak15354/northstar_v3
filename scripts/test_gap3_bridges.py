#!/usr/bin/env python3
"""
Test script for Gap 3 bridge modules.

Tests all three bridges:
1. MacroAlternativeBridge
2. ValuationAlternativeBridge
3. RiskAlternativeBridge
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import yaml

from src.ingestion.ingestion_registry import IngestionRegistry
from src.alternative_data import (
    MacroAlternativeBridge,
    ValuationAlternativeBridge,
    RiskAlternativeBridge
)


def load_config():
    """Load configuration."""
    config_path = Path(__file__).parent.parent / 'config' / 'ingestion_config.yaml'
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def test_macro_bridge():
    """Test MacroAlternativeBridge."""
    print("\n" + "="*80)
    print("TESTING MACRO ALTERNATIVE BRIDGE")
    print("="*80)
    
    config = load_config()
    registry = IngestionRegistry(config)
    bridge = MacroAlternativeBridge(registry, config)
    
    as_of_date = datetime(2024, 12, 31)
    
    # Test 1: Kalman observation vector
    print("\n1. Testing Kalman observation vector...")
    try:
        kalman_obs = bridge.get_kalman_observation_vector(as_of_date)
        print(f"   ✓ Kalman observation computed")
        print(f"     - GST YoY growth z-score: {kalman_obs['gst_yoy_growth_zscore']:.3f}")
        print(f"     - Power YoY growth z-score: {kalman_obs['power_yoy_growth_zscore']:.3f}")
        print(f"     - Composite activity score: {kalman_obs['composite_activity_score']:.3f}")
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    # Test 2: Macro forecast inputs
    print("\n2. Testing macro forecast inputs...")
    try:
        forecast_inputs = bridge.get_macro_forecast_inputs(as_of_date, forecast_horizon_months=3)
        print(f"   ✓ Forecast inputs computed")
        print(f"     - Current activity regime: {forecast_inputs['current_activity_regime']:.1f}")
        print(f"     - Activity momentum: {forecast_inputs['activity_momentum']:.3f}")
        print(f"     - Leading indicator signal: {forecast_inputs['leading_indicator_signal']:.3f}")
        print(f"     - Forecast confidence modifier: {forecast_inputs['forecast_confidence_modifier']:.2f}")
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    # Test 3: Sector macro sensitivities
    print("\n3. Testing sector macro sensitivities...")
    try:
        sector_sens = bridge.get_sector_macro_sensitivities(as_of_date)
        print(f"   ✓ Sector sensitivities computed for {len(sector_sens)} sectors")
        print("\n   Top 5 sectors by activity beta:")
        top_sectors = sector_sens.nlargest(5, 'activity_beta')
        for sector in top_sectors.index:
            row = top_sectors.loc[sector]
            print(f"     - {sector}: beta={row['activity_beta']:.2f}, "
                  f"regime_adj={row['regime_adjustment']:.3f}")
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    # Test 4: Activity regime context
    print("\n4. Testing activity regime context...")
    try:
        context = bridge.get_activity_regime_context(as_of_date)
        print(f"   ✓ Activity regime context built")
        print(f"     - Kalman observation keys: {list(context['kalman_observation'].keys())}")
        print(f"     - Forecast inputs keys: {list(context['forecast_inputs'].keys())}")
        print(f"     - Sector sensitivities shape: {context['sector_sensitivities'].shape}")
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    print("\n✓ MacroAlternativeBridge tests completed")


def test_valuation_bridge():
    """Test ValuationAlternativeBridge."""
    print("\n" + "="*80)
    print("TESTING VALUATION ALTERNATIVE BRIDGE")
    print("="*80)
    
    config = load_config()
    registry = IngestionRegistry(config)
    bridge = ValuationAlternativeBridge(registry, config)
    
    as_of_date = datetime(2024, 12, 31)
    test_tickers = ['RELIANCE', 'TCS', 'INFY', 'HDFCBANK', 'ICICIBANK']
    
    # Test 1: Credit inputs for valuation
    print("\n1. Testing credit inputs for valuation...")
    try:
        credit_inputs = bridge.get_credit_inputs_for_valuation(as_of_date, test_tickers)
        print(f"   ✓ Credit inputs computed for {len(credit_inputs)} tickers")
        print(f"     Columns: {list(credit_inputs.columns)}")
        
        # Show sample
        if not credit_inputs.empty:
            sample = credit_inputs.head(3)
            print("\n   Sample credit inputs:")
            for ticker in sample.index:
                row = sample.loc[ticker]
                print(f"     - {ticker}: rating={row['credit_rating']}, "
                      f"spread={row['credit_spread_bps']:.0f}bps, "
                      f"distress={row['credit_distress_flag']:.1f}")
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    # Test 2: Pledge inputs for forensics
    print("\n2. Testing pledge inputs for forensics...")
    try:
        pledge_inputs = bridge.get_pledge_inputs_for_forensics(as_of_date, test_tickers)
        print(f"   ✓ Pledge inputs computed for {len(pledge_inputs)} tickers")
        print(f"     Columns: {list(pledge_inputs.columns)}")
        
        # Show sample
        if not pledge_inputs.empty:
            sample = pledge_inputs.head(3)
            print("\n   Sample pledge inputs:")
            for ticker in sample.index:
                row = sample.loc[ticker]
                print(f"     - {ticker}: pledge={row['pledge_pct']:.1%}, "
                      f"risk_score={row['pledge_risk_score']:.2f}, "
                      f"haircut={row['pledge_valuation_haircut']:.1f}%")
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    # Test 3: Combined distress score
    print("\n3. Testing combined distress score...")
    try:
        distress_scores = bridge.get_combined_distress_score(as_of_date, test_tickers)
        print(f"   ✓ Distress scores computed for {len(distress_scores)} tickers")
        print(f"     Columns: {list(distress_scores.columns)}")
        
        # Show high-distress companies
        high_distress = distress_scores[distress_scores['distress_flag'] > 0.5]
        if not high_distress.empty:
            print(f"\n   High-distress companies ({len(high_distress)}):")
            for ticker in high_distress.index:
                row = high_distress.loc[ticker]
                print(f"     - {ticker}: score={row['distress_score']:.2f}, "
                      f"source={row['distress_source']}, "
                      f"action={row['recommended_action']}")
        else:
            print("\n   No high-distress companies in sample")
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    # Test 4: Valuation context
    print("\n4. Testing valuation context...")
    try:
        context = bridge.get_valuation_context(as_of_date, test_tickers)
        print(f"   ✓ Valuation context built")
        print(f"     - Credit inputs shape: {context['credit_inputs'].shape}")
        print(f"     - Pledge inputs shape: {context['pledge_inputs'].shape}")
        print(f"     - Distress scores shape: {context['distress_scores'].shape}")
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    print("\n✓ ValuationAlternativeBridge tests completed")


def test_risk_bridge():
    """Test RiskAlternativeBridge."""
    print("\n" + "="*80)
    print("TESTING RISK ALTERNATIVE BRIDGE")
    print("="*80)
    
    config = load_config()
    registry = IngestionRegistry(config)
    bridge = RiskAlternativeBridge(registry, config)
    
    as_of_date = datetime(2024, 12, 31)
    test_tickers = ['RELIANCE', 'TCS', 'INFY', 'HDFCBANK', 'ICICIBANK']
    
    # Create mock portfolio
    current_positions = pd.DataFrame({
        'Ticker': test_tickers,
        'Weight': [0.25, 0.20, 0.20, 0.20, 0.15]
    })
    
    # Test 1: Portfolio alternative risk
    print("\n1. Testing portfolio alternative risk...")
    try:
        portfolio_risk = bridge.get_portfolio_alternative_risk(as_of_date, current_positions)
        print(f"   ✓ Portfolio risk computed")
        print(f"     - Risk level: {portfolio_risk['risk_level']}")
        print(f"     - Distress exposure: {portfolio_risk['distress_exposure']:.1%}")
        print(f"     - High-pledge exposure: {portfolio_risk['high_pledge_exposure']:.1%}")
        print(f"     - Credit downgrade exposure: {portfolio_risk['credit_downgrade_exposure']:.1%}")
        print(f"     - Smart money alignment: {portfolio_risk['smart_money_alignment']:.2f}")
        
        if portfolio_risk['warnings']:
            print(f"\n   Warnings ({len(portfolio_risk['warnings'])}):")
            for warning in portfolio_risk['warnings']:
                print(f"     - {warning}")
        
        if portfolio_risk['recommendations']:
            print(f"\n   Recommendations ({len(portfolio_risk['recommendations'])}):")
            for rec in portfolio_risk['recommendations']:
                print(f"     - {rec}")
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    # Test 2: New position risk check
    print("\n2. Testing new position risk check...")
    try:
        new_ticker = 'TATAMOTORS'
        proposed_weight = 0.10
        
        risk_check = bridge.get_new_position_risk_check(
            as_of_date,
            new_ticker,
            proposed_weight,
            current_positions
        )
        
        print(f"   ✓ Position risk check completed for {new_ticker}")
        print(f"     - Status: {risk_check['status']}")
        print(f"     - Risk score: {risk_check['risk_score']:.2f}")
        print(f"     - Flags: {risk_check['flags']}")
        print(f"     - Max allowed weight: {risk_check['max_allowed_weight']:.1%}")
        print(f"     - Recommended weight: {risk_check['recommended_weight']:.1%}")
        print(f"     - Rationale: {risk_check['rationale']}")
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    # Test 3: Systemic risk signals
    print("\n3. Testing systemic risk signals...")
    try:
        systemic_risk = bridge.get_systemic_risk_signals(as_of_date)
        print(f"   ✓ Systemic risk signals computed")
        print(f"     - Risk regime: {systemic_risk['risk_regime']}")
        print(f"     - Systemic stress level: {systemic_risk['systemic_stress_level']:.2f}")
        print(f"     - Economic activity regime: {systemic_risk['economic_activity_regime']}")
        print(f"     - Credit market stress: {systemic_risk['credit_market_stress']:.2f}")
        print(f"     - Pledge systemic risk: {systemic_risk['pledge_systemic_risk']:.2f}")
        print(f"     - Smart money signal: {systemic_risk['smart_money_signal']}")
        print(f"     - Recommended adjustment: {systemic_risk['recommended_portfolio_adjustment']}")
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    print("\n✓ RiskAlternativeBridge tests completed")


def main():
    """Run all bridge tests."""
    print("\n" + "="*80)
    print("GAP 3 BRIDGE MODULES TEST SUITE")
    print("="*80)
    print("\nTesting three bridge modules:")
    print("1. MacroAlternativeBridge - Connects GST/power to Macro Transmission Engine")
    print("2. ValuationAlternativeBridge - Connects credit/pledges to Valuation Engine")
    print("3. RiskAlternativeBridge - Connects alternative data to Risk Management")
    
    try:
        test_macro_bridge()
    except Exception as e:
        print(f"\n✗ MacroAlternativeBridge test suite failed: {e}")
    
    try:
        test_valuation_bridge()
    except Exception as e:
        print(f"\n✗ ValuationAlternativeBridge test suite failed: {e}")
    
    try:
        test_risk_bridge()
    except Exception as e:
        print(f"\n✗ RiskAlternativeBridge test suite failed: {e}")
    
    print("\n" + "="*80)
    print("ALL BRIDGE TESTS COMPLETED")
    print("="*80)


if __name__ == '__main__':
    main()
