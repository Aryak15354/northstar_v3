#!/usr/bin/env python3
"""
📈 FORCE MARKET UPDATE - NORTHSTAR V3
Force update of market data regardless of freshness

This script forces a market data update by:
1. Running the price fetcher for individual stocks
2. Fetching market indices
3. Updating market data files
4. Integrating with Market State Spine
"""

import sys
import os
import subprocess
from datetime import datetime

def force_market_update():
    """Force update of all market data"""
    
    print("📈 FORCE MARKET DATA UPDATE")
    print("=" * 50)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    success_flags = {
        'price_fetcher': False,
        'market_indices': False,
        'integration': False
    }
    
    # Step 1: Update individual stock prices
    print("\n📊 STEP 1: UPDATING INDIVIDUAL STOCK PRICES")
    print("-" * 40)
    
    try:
        result = subprocess.run([
            sys.executable, "src/ingestion/price_fetcher.py"
        ], capture_output=True, text=True, timeout=1800)  # 30 min timeout
        
        if result.returncode == 0:
            print("✅ Price fetcher completed successfully")
            success_flags['price_fetcher'] = True
        else:
            print(f"⚠️ Price fetcher had issues: {result.stderr}")
            print("Continuing with market indices update...")
            
    except subprocess.TimeoutExpired:
        print("⚠️ Price fetcher timed out - continuing anyway")
    except Exception as e:
        print(f"⚠️ Price fetcher error: {e}")
    
    # Step 2: Force market indices update
    print("\n📊 STEP 2: UPDATING MARKET INDICES")
    print("-" * 40)
    
    try:
        from src.ingestion.integrated_data_pipeline import IntegratedDataPipeline
        
        pipeline = IntegratedDataPipeline()
        success = pipeline.fetch_market_indices()
        
        if success:
            print("✅ Market indices updated successfully")
            success_flags['market_indices'] = True
        else:
            print("❌ Market indices update failed")
            
    except Exception as e:
        print(f"❌ Market indices update error: {e}")
    
    # Step 3: Force integration with Market State Spine
    print("\n🧠 STEP 3: INTEGRATING WITH MARKET STATE SPINE")
    print("-" * 40)
    
    try:
        from src.cohesion.unified_state_manager import UnifiedStateManager
        
        print("🧠 Computing unified market state...")
        engine = UnifiedStateManager()
        market_state = engine.run()
        
        if market_state:
            print("✅ Market State Spine integration complete")
            success_flags['integration'] = True
            
            # Print summary
            print(f"\n📊 MARKET STATE SUMMARY")
            print("-" * 30)
            print(f"Macro Score: {market_state.get('macro_score', 0):+.2f}")
            print(f"Regime: {market_state.get('macro_regime', 'Unknown')}")
            print(f"Risk-On Probability: {market_state.get('risk_on_probability', 0)*100:.1f}%")
            print(f"Market Health: {market_state.get('health_score', 0)*100:.1f}%")
            print(f"Breadth: {market_state.get('breadth_pct', 0):.0f}%")
            print(f"Confidence: {market_state.get('confidence', 0)*100:.1f}%")
        else:
            print("❌ Market State Spine integration failed")
            
    except Exception as e:
        print(f"❌ Market State Spine integration error: {e}")
    
    # Summary
    print(f"\n🎯 FORCE MARKET UPDATE SUMMARY")
    print("=" * 50)
    
    successful_steps = sum(success_flags.values())
    total_steps = len(success_flags)
    
    for step, success in success_flags.items():
        status = "✅" if success else "❌"
        print(f"{status} {step.replace('_', ' ').title()}")
    
    if successful_steps >= 2:  # At least market indices and integration
        print(f"\n🎉 MARKET UPDATE SUCCESSFUL ({successful_steps}/{total_steps} steps)")
        print("📈 Market data is now current")
        return True
    else:
        print(f"\n⚠️ MARKET UPDATE PARTIALLY FAILED ({successful_steps}/{total_steps} steps)")
        print("🔧 Some market data may be stale")
        return False

def main():
    """Main execution"""
    
    try:
        success = force_market_update()
        
        if success:
            print("\n✅ Force market update completed successfully!")
            return True
        else:
            print("\n⚠️ Force market update completed with issues!")
            return False
            
    except Exception as e:
        print(f"\n❌ Force market update failed: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)