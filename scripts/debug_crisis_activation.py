#!/usr/bin/env python3
"""
🔍 DEBUG CRISIS ENGINE ACTIVATION

Debug why the Crisis Engine is not activating despite regime detection improvements.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from datetime import datetime

from src.intelligence.dual_engine_coordinator import DualEngineCoordinator
from src.intelligence.crisis_engine import NorthstarCrisisEngine

def create_high_volatility_scenario():
    """Create a scenario with very high volatility to test activation"""
    
    dates = pd.date_range('2020-01-01', '2020-06-30', freq='D')
    
    # Create extreme volatility scenario
    returns = []
    np.random.seed(42)
    
    for i in range(len(dates)):
        if 30 <= i <= 60:  # Extreme crisis period
            ret = np.random.normal(-0.05, 0.15)  # -5% mean, 15% daily vol = ~240% annualized
        else:
            ret = np.random.normal(0.001, 0.02)  # Normal period
        returns.append(ret)
    
    market_data = pd.DataFrame({
        'date': dates,
        'market_return': returns
    })
    
    return market_data

def test_crisis_engine_directly():
    """Test Crisis Engine directly with extreme data"""
    
    print("🔍 TESTING CRISIS ENGINE DIRECTLY")
    print("=" * 50)
    
    # Create crisis engine
    crisis_engine = NorthstarCrisisEngine()
    
    # Create extreme volatility data
    market_data = create_high_volatility_scenario()
    
    print(f"📊 Testing with {len(market_data)} days of data")
    
    # Test day by day through crisis period
    activations = []
    
    for i in range(30, len(market_data)):
        current_data = market_data.iloc[:i+1]
        current_date = market_data['date'].iloc[i]
        
        # Calculate current volatility
        returns = current_data['market_return'].tail(20)
        current_vol = returns.std() * np.sqrt(252)
        
        # Get crisis engine signals
        signals = crisis_engine.generate_crisis_signals(current_data, current_date)
        
        if signals['engine_active'] or current_vol > 0.30:
            activations.append({
                'date': current_date,
                'volatility': current_vol,
                'regime': signals['regime_state'],
                'allocation': signals['crisis_allocation'],
                'active': signals['engine_active']
            })
            
            print(f"{current_date.strftime('%Y-%m-%d')}: "
                  f"Vol={current_vol:.1%}, "
                  f"Regime={signals['regime_state']}, "
                  f"Allocation={signals['crisis_allocation']:.1%}, "
                  f"Active={signals['engine_active']}")
    
    print(f"\n📊 Crisis Engine Activations: {len([a for a in activations if a['active']])}")
    print(f"📊 High Volatility Days: {len(activations)}")
    
    return activations

def test_dual_engine_coordinator():
    """Test Dual Engine Coordinator with extreme data"""
    
    print("\n🎯 TESTING DUAL ENGINE COORDINATOR")
    print("=" * 50)
    
    # Create coordinator
    coordinator = DualEngineCoordinator()
    
    # Create extreme volatility data
    market_data = create_high_volatility_scenario()
    
    print(f"📊 Testing with {len(market_data)} days of data")
    
    # Test day by day through crisis period
    activations = []
    
    for i in range(30, len(market_data)):
        current_data = market_data.iloc[:i+1]
        current_date = market_data['date'].iloc[i]
        
        # Calculate current volatility
        returns = current_data['market_return'].tail(20)
        current_vol = returns.std() * np.sqrt(252)
        
        # Get engine allocation
        allocation = coordinator.coordinate_engine_allocations(current_data, current_date)
        
        if allocation.crisis_allocation > 0 or current_vol > 0.30:
            activations.append({
                'date': current_date,
                'volatility': current_vol,
                'regime': allocation.regime.value,
                'crisis_allocation': allocation.crisis_allocation,
                'trend_allocation': allocation.trend_allocation,
                'active_engine': allocation.active_engine
            })
            
            print(f"{current_date.strftime('%Y-%m-%d')}: "
                  f"Vol={current_vol:.1%}, "
                  f"Regime={allocation.regime.value}, "
                  f"Crisis={allocation.crisis_allocation:.1%}, "
                  f"Trend={allocation.trend_allocation:.1%}, "
                  f"Active={allocation.active_engine}")
    
    print(f"\n📊 Crisis Engine Activations: {len([a for a in activations if a['crisis_allocation'] > 0])}")
    print(f"📊 High Volatility Days: {len(activations)}")
    
    return activations

def main():
    """Main debug function"""
    
    print("🔍 CRISIS ENGINE ACTIVATION DEBUG")
    print("=" * 70)
    
    # Test Crisis Engine directly
    crisis_activations = test_crisis_engine_directly()
    
    # Test Dual Engine Coordinator
    coordinator_activations = test_dual_engine_coordinator()
    
    print(f"\n💡 ANALYSIS")
    print("=" * 50)
    
    if not crisis_activations:
        print("❌ Crisis Engine never activated even with extreme volatility")
        print("   Issue: Crisis Engine thresholds still too high or logic broken")
    else:
        print(f"✅ Crisis Engine activated {len(crisis_activations)} times")
    
    if not coordinator_activations:
        print("❌ Dual Engine Coordinator never activated Crisis Engine")
        print("   Issue: Coordinator logic not triggering Crisis Engine")
    else:
        crisis_count = len([a for a in coordinator_activations if a['crisis_allocation'] > 0])
        print(f"✅ Coordinator activated Crisis Engine {crisis_count} times")
    
    # Show current thresholds
    crisis_engine = NorthstarCrisisEngine()
    coordinator = DualEngineCoordinator()
    
    print(f"\n🎯 CURRENT THRESHOLDS")
    print("=" * 50)
    print(f"Crisis Engine HOSTILE: {crisis_engine.config.HOSTILE_REGIME_VOL_THRESHOLD:.1%}")
    print(f"Crisis Engine PANIC: {crisis_engine.config.PANIC_REGIME_VOL_THRESHOLD:.1%}")
    print(f"Coordinator HOSTILE: {coordinator.regime_config['volatility_threshold_hostile']:.1%}")
    print(f"Coordinator PANIC: {coordinator.regime_config['volatility_threshold_panic']:.1%}")
    
    # Calculate max volatility in test data
    market_data = create_high_volatility_scenario()
    max_vol = 0
    for i in range(20, len(market_data)):
        returns = market_data['market_return'].iloc[i-20:i]
        vol = returns.std() * np.sqrt(252)
        max_vol = max(max_vol, vol)
    
    print(f"\nTest Data Max Volatility: {max_vol:.1%}")
    
    if max_vol < crisis_engine.config.HOSTILE_REGIME_VOL_THRESHOLD:
        print("❌ Test data volatility below Crisis Engine threshold!")
        print("   Need to either:")
        print("   1. Lower Crisis Engine thresholds further")
        print("   2. Create more extreme test data")

if __name__ == "__main__":
    main()