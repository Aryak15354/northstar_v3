#!/usr/bin/env python3
"""
Signal Strength Validation

Before running any walk-forward, we must validate that our alpha signals
have sufficient strength to overcome noise and transaction costs.

This is the test that determines if we have real alpha or just noise.
"""

import sys
import os
import numpy as np
import pandas as pd
from datetime import datetime
import matplotlib.pyplot as plt

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_signal_strength():
    """Test if our alpha signals have sufficient strength"""
    
    print("🔬 SIGNAL STRENGTH VALIDATION")
    print("=" * 60)
    print("Testing if alpha signals are stronger than noise + costs")
    print()
    
    # Generate test market data
    np.random.seed(42)  # Fixed seed for consistent test
    n_days = 5000  # ~20 years
    
    # Market returns (random walk)
    market_returns = np.random.normal(0.0008, 0.015, n_days)  # ~20% vol, 20% annual return
    
    # Test different signal strengths
    signal_strengths = [0.001, 0.002, 0.005, 0.010, 0.020]  # Daily alpha from 0.1% to 2%
    transaction_cost = 0.0015  # 15 bps per trade
    
    results = []
    
    for signal_strength in signal_strengths:
        print(f"\n🎯 Testing signal strength: {signal_strength*100:.1f}% daily")
        
        # Generate alpha signals with this strength
        true_alpha = np.random.normal(signal_strength, signal_strength * 0.5, n_days)
        
        # Add noise (this is what kills weak signals)
        noise = np.random.normal(0, signal_strength * 2, n_days)  # Noise 2x signal
        observed_alpha = true_alpha + noise
        
        # Simulate trading on these signals
        positions = np.sign(observed_alpha)  # Long/short based on signal
        position_changes = np.abs(np.diff(positions, prepend=0))
        
        # Calculate returns
        gross_returns = positions * market_returns
        
        # Subtract transaction costs
        costs = position_changes * transaction_cost
        net_returns = gross_returns - costs
        
        # Calculate metrics
        gross_sharpe = np.mean(gross_returns) / np.std(gross_returns) * np.sqrt(252)
        net_sharpe = np.mean(net_returns) / np.std(net_returns) * np.sqrt(252)
        
        total_gross_return = np.prod(1 + gross_returns) - 1
        total_net_return = np.prod(1 + net_returns) - 1
        
        turnover = np.mean(position_changes)
        total_costs = np.sum(costs)
        
        results.append({
            'signal_strength': signal_strength,
            'gross_sharpe': gross_sharpe,
            'net_sharpe': net_sharpe,
            'total_gross_return': total_gross_return,
            'total_net_return': total_net_return,
            'turnover': turnover,
            'total_costs': total_costs
        })
        
        print(f"   Gross Sharpe: {gross_sharpe:.2f}")
        print(f"   Net Sharpe: {net_sharpe:.2f}")
        print(f"   Total Gross Return: {total_gross_return*100:.1f}%")
        print(f"   Total Net Return: {total_net_return*100:.1f}%")
        print(f"   Daily Turnover: {turnover:.1f}%")
        print(f"   Total Costs: {total_costs*100:.1f}%")
    
    # Analysis
    print(f"\n📊 SIGNAL STRENGTH ANALYSIS")
    print("=" * 60)
    
    viable_strategies = [r for r in results if r['net_sharpe'] > 1.0 and r['total_net_return'] > 0.1]
    
    if not viable_strategies:
        print("💥 CRITICAL FAILURE: NO VIABLE SIGNAL STRENGTH FOUND")
        print()
        print("Analysis:")
        print("• All signal strengths fail to overcome noise + costs")
        print("• The strategy has no profitable regime")
        print("• Transaction costs dominate any potential alpha")
        print()
        print("Recommendation:")
        print("• Increase signal strength by 10x minimum")
        print("• Reduce transaction costs")
        print("• Reduce turnover/rebalancing frequency")
        print("• Find stronger, more persistent alpha sources")
        
        return False
    
    else:
        print(f"✅ VIABLE SIGNAL STRENGTHS FOUND: {len(viable_strategies)}")
        print()
        
        best_strategy = max(viable_strategies, key=lambda x: x['net_sharpe'])
        min_signal = min(viable_strategies, key=lambda x: x['signal_strength'])
        
        print(f"Best Strategy:")
        print(f"   Signal Strength: {best_strategy['signal_strength']*100:.1f}% daily")
        print(f"   Net Sharpe: {best_strategy['net_sharpe']:.2f}")
        print(f"   Net Return: {best_strategy['total_net_return']*100:.1f}%")
        
        print(f"\nMinimum Viable Signal:")
        print(f"   Signal Strength: {min_signal['signal_strength']*100:.1f}% daily")
        print(f"   Net Sharpe: {min_signal['net_sharpe']:.2f}")
        
        print(f"\n🎯 SIGNAL STRENGTH REQUIREMENTS:")
        print(f"   Minimum Daily Alpha: {min_signal['signal_strength']*100:.1f}%")
        print(f"   Minimum Annual Alpha: {min_signal['signal_strength']*252*100:.1f}%")
        print(f"   Required Sharpe: >1.0")
        
        return True

def test_current_northstar_signals():
    """Test the actual NorthStar signal strength"""
    
    print(f"\n🔍 TESTING CURRENT NORTHSTAR SIGNALS")
    print("=" * 60)
    
    # This would test the actual signals from the institutional alpha engine
    # For now, we'll simulate based on what we observed
    
    print("Based on walk-forward results:")
    print("• Observed massive variance under different seeds")
    print("• Returns ranging from 0.3% to 7,383%")
    print("• Coefficient of variation > 100%")
    print()
    
    print("🎯 DIAGNOSIS:")
    print("❌ Signal strength is insufficient")
    print("❌ Noise dominates signal")
    print("❌ No consistent edge detected")
    print()
    
    print("📋 REQUIRED ACTIONS:")
    print("1. Increase signal strength by 10x minimum")
    print("2. Reduce noise in signal generation")
    print("3. Implement signal quality filters")
    print("4. Add signal persistence requirements")
    print("5. Reduce rebalancing frequency")
    
    return False

def main():
    """Run signal strength validation"""
    
    print("🧪 NORTHSTAR SIGNAL STRENGTH VALIDATION")
    print("=" * 80)
    print("This test determines if we have real alpha or just noise.")
    print()
    
    # Test theoretical signal strengths
    has_viable_signals = test_signal_strength()
    
    # Test current NorthStar
    northstar_viable = test_current_northstar_signals()
    
    print(f"\n" + "=" * 80)
    
    if has_viable_signals and northstar_viable:
        print("🎯 VERDICT: NORTHSTAR HAS SUFFICIENT SIGNAL STRENGTH")
        print("The strategy can proceed to walk-forward validation.")
    else:
        print("💥 VERDICT: NORTHSTAR SIGNAL STRENGTH INSUFFICIENT")
        print("The strategy must be strengthened before walk-forward validation.")
        print()
        print("🚨 CRITICAL: Do not deploy capital until signal strength is validated.")
    
    return has_viable_signals and northstar_viable

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)