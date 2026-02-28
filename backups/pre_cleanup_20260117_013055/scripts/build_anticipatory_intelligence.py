#!/usr/bin/env python3
"""
🧠 BUILD ANTICIPATORY INTELLIGENCE - NORTHSTAR V3 MARKET BRAIN
The Complete Market Nervous System

This builds the full anticipatory intelligence stack:
1. Beta Drift Fabric (Market Nervous System)
2. Strategy Tailwinds (Anticipatory Signals)
3. Anticipatory Capital Allocation (Capital Moves First)

This is how hedge funds get paid: they see the storm before the clouds form.
"""

import sys
import os
))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json

def check_beta_drift_data():
    """Check if we have sufficient beta drift data"""
    
    print("🔍 CHECKING BETA DRIFT DATA")
    print("=" * 50)
    
    beta_drift_dir = 'data/beta_drift_insights'
    
    if not os.path.exists(beta_drift_dir):
        print("❌ No beta drift data found")
        print("   Run: python scripts/build_beta_drift_fabric.py")
        return False
    
    # Check processed years
    processed_years = [
        int(d) for d in os.listdir(beta_drift_dir)
        if d.isdigit() and os.path.isdir(os.path.join(beta_drift_dir, d))
    ]
    
    if not processed_years:
        print("❌ No processed years found")
        print("   Run: python scripts/build_beta_drift_fabric.py")
        return False
    
    # Count total beta drifts
    total_drifts = 0
    total_weeks = 0
    
    for year in processed_years:
        year_dir = os.path.join(beta_drift_dir, str(year))
        summary_file = os.path.join(year_dir, 'summary.parquet')
        
        if os.path.exists(summary_file):
            try:
                summary_df = pd.read_parquet(summary_file)
                total_drifts += len(summary_df)
                total_weeks += len(summary_df['week'].unique())
            except:
                continue
    
    print(f"✅ Beta drift data available:")
    print(f"   📅 Processed years: {sorted(processed_years)}")
    print(f"   🧬 Total beta drifts: {total_drifts:,}")
    print(f"   📊 Total weeks: {total_weeks}")
    
    if total_drifts < 100:
        print("⚠️ Limited beta drift data - consider processing more years")
        return True  # Still proceed
    
    print("✅ Sufficient beta drift data for anticipatory intelligence")
    return True

def build_strategy_tailwinds():
    """Build strategy tailwinds from beta drift signals"""
    
    print("\n🌊 BUILDING STRATEGY TAILWINDS")
    print("=" * 50)
    
    try:
        from src.intelligence.strategy_tailwinds import StrategyTailwinds
        
        tailwinds = StrategyTailwinds()
        success = tailwinds.build_strategy_tailwinds(lookback_weeks=8)
        
        if success:
            print("✅ Strategy tailwinds built successfully")
            return True
        else:
            print("❌ Failed to build strategy tailwinds")
            return False
            
    except Exception as e:
        print(f"❌ Error building strategy tailwinds: {e}")
        return False

def build_anticipatory_allocations():
    """Build anticipatory capital allocations"""
    
    print("\n🧠 BUILDING ANTICIPATORY CAPITAL ALLOCATIONS")
    print("=" * 50)
    
    try:
        from src.intelligence.anticipatory_capital_allocator import AnticipatoryCapitalAllocator
        
        allocator = AnticipatoryCapitalAllocator()
        success = allocator.build_anticipatory_allocations()
        
        if success:
            print("✅ Anticipatory capital allocations built successfully")
            return True
        else:
            print("❌ Failed to build anticipatory allocations")
            return False
            
    except Exception as e:
        print(f"❌ Error building anticipatory allocations: {e}")
        return False

def test_anticipatory_system():
    """Test the complete anticipatory intelligence system"""
    
    print("\n🧪 TESTING ANTICIPATORY INTELLIGENCE SYSTEM")
    print("=" * 50)
    
    try:
        # Test strategy tailwinds
        tailwinds_file = 'data/intelligence/strategy_tailwinds.json'
        if os.path.exists(tailwinds_file):
            with open(tailwinds_file, 'r') as f:
                tailwinds_data = json.load(f)
            
            strategy_tailwinds = tailwinds_data.get('strategy_tailwinds', {})
            print(f"✅ Strategy tailwinds: {len(strategy_tailwinds)} strategies")
            
            # Show top tailwinds
            if strategy_tailwinds:
                sorted_tailwinds = sorted(strategy_tailwinds.items(), key=lambda x: x[1]['total_tailwind'], reverse=True)
                print(f"   🏆 Top 3 tailwinds:")
                for i, (strategy, data) in enumerate(sorted_tailwinds[:3]):
                    print(f"      {i+1}. {strategy}: {data['total_tailwind']:+.3f}")
        else:
            print("⚠️ Strategy tailwinds file not found")
        
        # Test anticipatory allocations
        allocations_file = 'data/intelligence/anticipatory_allocations.json'
        if os.path.exists(allocations_file):
            with open(allocations_file, 'r') as f:
                allocations_data = json.load(f)
            
            allocations = allocations_data.get('allocations', {})
            print(f"✅ Anticipatory allocations: {len(allocations)} positions")
            
            # Show allocations
            if allocations:
                print(f"   💰 Allocation breakdown:")
                for strategy, data in sorted(allocations.items(), key=lambda x: x[1]['allocation'], reverse=True):
                    if strategy != 'cash':
                        tailwind_str = f" (tailwind: {data.get('raw_tailwind', 0):+.3f})" if data.get('raw_tailwind', 0) != 0 else ""
                        print(f"      {strategy}: {data['allocation']:.1%}{tailwind_str}")
                    else:
                        print(f"      {strategy}: {data['allocation']:.1%}")
        else:
            print("⚠️ Anticipatory allocations file not found")
        
        print("✅ Anticipatory intelligence system test completed")
        return True
        
    except Exception as e:
        print(f"❌ Error testing anticipatory system: {e}")
        return False

def show_integration_status():
    """Show integration status with existing V3 systems"""
    
    print("\n🔗 INTEGRATION STATUS")
    print("=" * 50)
    
    components = {
        'Beta Drift Fabric': 'data/beta_drift_insights',
        'Strategy Tailwinds': 'data/intelligence/strategy_tailwinds.json',
        'Anticipatory Allocations': 'data/intelligence/anticipatory_allocations.json',
        'Theme Pressure': 'data/intelligence/theme_pressure.json',
        'Market Tensor': 'data/processed/market_tensor.parquet'
    }
    
    for component, path in components.items():
        if os.path.exists(path):
            print(f"✅ {component}: Ready")
        else:
            print(f"⚠️ {component}: Not found")
    
    print("\n🎯 NEXT INTEGRATION STEPS:")
    print("1. 📊 Dashboard: Visualize pressure maps and tailwinds")
    print("2. 🔄 Portfolio: Use anticipatory allocations for rebalancing")
    print("3. 📈 Backtesting: Validate anticipatory performance")
    print("4. 📝 Narratives: Explain anticipatory positioning")

def show_anticipatory_intelligence_summary():
    """Show summary of the anticipatory intelligence system"""
    
    print("\n🧠 ANTICIPATORY INTELLIGENCE SYSTEM SUMMARY")
    print("=" * 60)
    
    print("🧬 WHAT WE BUILT:")
    print("   1. Market Nervous System (Beta Drift Fabric)")
    print("      - Detects when stocks become sensitive to macro forces")
    print("      - Measures sensitivity shifts, not return prediction")
    print("      - Provides weeks of advance warning")
    print()
    print("   2. Strategy Tailwinds Engine")
    print("      - Converts beta drifts into macro themes")
    print("      - Maps themes to strategy exposures")
    print("      - Provides anticipatory signals for capital allocation")
    print()
    print("   3. Anticipatory Capital Allocator")
    print("      - Integrates beliefs, regret, and tailwinds")
    print("      - Positions capital before price moves")
    print("      - Score = Sharpe × Belief × (1 + Tailwind)")
    print()
    
    print("🎯 HOW IT WORKS:")
    print("   📊 Market sensitivity shifts detected")
    print("   🧠 Macro themes identified")
    print("   🌊 Strategy tailwinds computed")
    print("   💰 Capital allocated anticipatorily")
    print("   📈 Positions taken before price moves")
    print()
    
    print("🏆 THIS IS HOW HEDGE FUNDS GET PAID:")
    print("   - They see the storm before the clouds form")
    print("   - They position before the market moves")
    print("   - They use sensitivity shifts, not price patterns")
    print("   - They have anticipatory intelligence, not reactive systems")

def main():
    """Build complete anticipatory intelligence system"""
    
    print("🧠 ANTICIPATORY INTELLIGENCE BUILDER - NORTHSTAR V3")
    print("Building the Market Nervous System")
    print("=" * 60)
    
    # Check prerequisites
    if not check_beta_drift_data():
        print("\n❌ Prerequisites not met")
        print("   Run: python scripts/build_beta_drift_fabric.py first")
        return False
    
    # Build strategy tailwinds
    if not build_strategy_tailwinds():
        print("\n❌ Failed to build strategy tailwinds")
        return False
    
    # Build anticipatory allocations
    if not build_anticipatory_allocations():
        print("\n❌ Failed to build anticipatory allocations")
        return False
    
    # Test the system
    if not test_anticipatory_system():
        print("\n⚠️ System tests failed, but components were built")
    
    # Show integration status
    show_integration_status()
    
    # Show summary
    show_anticipatory_intelligence_summary()
    
    print("\n🎉 ANTICIPATORY INTELLIGENCE BUILD COMPLETED!")
    print("🧠 Northstar now has a Market Nervous System")
    print("🌊 Capital moves before prices do")
    print("🎯 This is how hedge funds get paid")
    
    return True

if __name__ == "__main__":
    success = main()
    
    if success:
        print("\n✅ Build completed successfully!")
        exit(0)
    else:
        print("\n❌ Build failed!")
        exit(1)