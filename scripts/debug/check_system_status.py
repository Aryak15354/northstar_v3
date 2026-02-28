#!/usr/bin/env python3
"""
Quick System Status Check
"""

import json
import pandas as pd
import os

def check_system_status():
    print("🔍 NORTHSTAR V3 SYSTEM STATUS CHECK")
    print("=" * 50)
    
    # Check anticipatory signals
    try:
        with open('data/processed/anticipatory_signals.json', 'r') as f:
            signals = json.load(f)
        
        current_regime = signals.get('current_regime', {})
        transitions = signals.get('regime_transitions', {})
        forward_exp = signals.get('forward_expectations', {})
        confidence = signals.get('confidence_metrics', {})
        
        print("✅ ANTICIPATORY INTELLIGENCE:")
        print(f"   Current Regime: {current_regime.get('name', 'Unknown')}")
        print(f"   Regime Stability: {current_regime.get('stability', 0):.1%}")
        print(f"   Transition Predictions: {len(transitions.get('next_regime_probabilities', {}))}")
        print(f"   Forward Expectations: {len(forward_exp)} periods")
        print(f"   Overall Confidence: {confidence.get('overall', 0):.1%}")
        
    except Exception as e:
        print(f"❌ Anticipatory Intelligence: Error - {e}")
    
    # Check capital allocations
    try:
        df = pd.read_parquet('data/processed/anticipatory_capital_allocations.parquet')
        
        print(f"\n✅ CAPITAL ALLOCATIONS:")
        print(f"   Total Strategies: {len(df)}")
        print(f"   Regime Fitness Range: {df['regime_fitness'].min():.3f} - {df['regime_fitness'].max():.3f}")
        print(f"   Unique Fitness Values: {df['regime_fitness'].nunique()}")
        
        cash_alloc = df[df['strategy_name'] == 'CASH']['allocation_weight'].iloc[0]
        print(f"   Cash Allocation: {cash_alloc:.1%}")
        
        top_3 = df.nlargest(3, 'allocation_weight')
        print(f"   Top 3 Allocations:")
        for _, row in top_3.iterrows():
            print(f"     {row['strategy_name']}: {row['allocation_weight']:.1%}")
            
    except Exception as e:
        print(f"❌ Capital Allocations: Error - {e}")
    
    # Check max drawdown issue
    try:
        perf_df = pd.read_parquet('data/processed/strategy_performance.parquet')
        
        print(f"\n✅ MAX DRAWDOWN STATUS:")
        print(f"   Strategies: {len(perf_df)}")
        print(f"   Drawdown Range: {perf_df['max_drawdown'].min():.3f} to {perf_df['max_drawdown'].max():.3f}")
        print(f"   Unique Drawdown Values: {perf_df['max_drawdown'].nunique()}")
        
        if perf_df['max_drawdown'].min() < -0.01:
            print("   ✅ Max drawdown is working correctly (negative values)")
        else:
            print("   ❌ Max drawdown may have issues (no negative values)")
            
    except Exception as e:
        print(f"❌ Strategy Performance: Error - {e}")
    
    print(f"\n🎯 SYSTEM SUMMARY:")
    
    # Check key files exist
    key_files = [
        'data/processed/anticipatory_signals.json',
        'data/processed/anticipatory_capital_allocations.parquet',
        'data/processed/regime_fingerprints_extended.parquet',
        'data/processed/strategy_performance.parquet'
    ]
    
    files_exist = sum(1 for f in key_files if os.path.exists(f))
    print(f"   Key Files Present: {files_exist}/{len(key_files)}")
    
    if files_exist == len(key_files):
        print("   🎉 SYSTEM IS OPERATIONAL!")
    else:
        print("   ⚠️ Some components missing")

if __name__ == "__main__":
    check_system_status()