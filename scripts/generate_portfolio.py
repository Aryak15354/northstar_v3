#!/usr/bin/env python3
"""
💼 GENERATE PORTFOLIO
Create portfolio using capital allocator and current market state
"""

import sys
import os
import pandas as pd
from pathlib import Path
from datetime import datetime
import json

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.intelligence.capital_allocator import CapitalAllocator
from src.state.market_state import MarketStateEngine
from src.state.unified_state_manager import UnifiedStateManager

def main():
    print("💼 NORTHSTAR V3 - PORTFOLIO GENERATION")
    print("=" * 70)
    
    # Step 1: Get current market state
    print("\n🌍 STEP 1: Loading Market State")
    print("-" * 70)
    
    try:
        market_engine = MarketStateEngine()
        market_state = market_engine.compute_market_state()
        
        print(f"   Regime: {market_state.get('macro_regime', 'unknown')}")
        print(f"   Risk-On: {market_state.get('risk_on_probability', 0):.1%}")
        print(f"   Allowed Exposure: {market_state.get('allowed_exposure', 0):.1%}")
        print(f"   Market Health: {market_state.get('market_health', 0):.1%}")
        
        allowed_exposure = market_state.get('allowed_exposure', 0.6)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return
    
    # Step 2: Initialize Capital Allocator
    print("\n💰 STEP 2: Initializing Capital Allocator")
    print("-" * 70)
    
    try:
        allocator = CapitalAllocator()
        print("   ✅ Capital Allocator initialized")
    except Exception as e:
        print(f"❌ Error: {e}")
        return
    
    # Step 3: Generate capital allocations
    print("\n🎯 STEP 3: Generating Capital Allocations")
    print("-" * 70)
    
    try:
        # Run capital allocation
        allocations = allocator.run_capital_allocation(
            regime=market_state.get('macro_regime', 'unknown'),
            risk_on_prob=market_state.get('risk_on_probability', 0.5),
            allowed_exposure=allowed_exposure
        )
        
        print(f"   ✅ Capital allocations generated")
        print(f"   Strategies: {len(allocations)}")
        
        # Display allocations
        print("\n   Strategy Allocations:")
        for strategy, weight in allocations.items():
            if weight > 0.01:  # Only show significant allocations
                print(f"      {strategy}: {weight:.1%}")
        
    except Exception as e:
        print(f"   ⚠️ Using default allocations: {e}")
        # Create default allocations
        allocations = {
            'quality': 0.30,
            'momentum': 0.25,
            'value': 0.20,
            'low_vol': 0.15,
            'cash': 0.10
        }
        print("   Using default strategy mix")
    
    # Step 4: Save allocations
    print("\n💾 STEP 4: Saving Portfolio")
    print("-" * 70)
    
    try:
        # Save capital allocations
        output_dir = project_root / 'data' / 'processed'
        output_dir.mkdir(exist_ok=True)
        
        allocation_data = {
            'timestamp': datetime.now().isoformat(),
            'regime': market_state.get('macro_regime', 'unknown'),
            'risk_on_probability': market_state.get('risk_on_probability', 0.5),
            'allowed_exposure': allowed_exposure,
            'allocations': allocations,
            'total_exposure': sum(v for k, v in allocations.items() if k != 'cash')
        }
        
        with open(output_dir / 'capital_allocations.json', 'w') as f:
            json.dump(allocation_data, f, indent=2)
        
        print(f"   ✅ Capital allocations saved")
        
        # Create simple portfolio weights
        portfolio_data = []
        
        # Get stock universe
        price_dir = project_root / 'data' / 'raw' / 'prices_daily'
        stock_files = list(price_dir.glob('*.csv'))[:50]  # Top 50 stocks
        
        num_stocks = len(stock_files)
        if num_stocks > 0:
            # Equal weight within each strategy
            for strategy, strategy_weight in allocations.items():
                if strategy != 'cash' and strategy_weight > 0:
                    stocks_per_strategy = max(5, num_stocks // len([k for k in allocations if k != 'cash']))
                    weight_per_stock = strategy_weight / stocks_per_strategy
                    
                    for i, stock_file in enumerate(stock_files[:stocks_per_strategy]):
                        ticker = stock_file.stem
                        portfolio_data.append({
                            'ticker': ticker,
                            'strategy': strategy,
                            'final_weight': weight_per_stock,
                            'timestamp': datetime.now().isoformat()
                        })
            
            # Save portfolio weights
            portfolio_df = pd.DataFrame(portfolio_data)
            portfolio_df.to_parquet(output_dir / 'portfolio_weights.parquet')
            
            print(f"   ✅ Portfolio weights saved")
            print(f"   Total positions: {len(portfolio_df)}")
            print(f"   Total exposure: {portfolio_df['final_weight'].sum():.1%}")
        
    except Exception as e:
        print(f"   ⚠️ Warning: {e}")
    
    # Step 5: Update unified state
    print("\n🔄 STEP 5: Updating Unified State")
    print("-" * 70)
    
    try:
        usm = UnifiedStateManager()
        usm.update_portfolio_state()
        usm.save_state()
        
        health = usm.compute_system_health()
        print(f"   System Health: {health['overall_health_score']:.1%}")
        print(f"   Portfolio Active: {'✅' if health['portfolio_active'] else '❌'}")
        print(f"   Portfolio Exposure: {health['portfolio_exposure']:.1%}")
        
    except Exception as e:
        print(f"   ⚠️ Warning: {e}")
    
    # Summary
    print("\n" + "=" * 70)
    print("🎯 PORTFOLIO GENERATION SUMMARY")
    print("=" * 70)
    print(f"✅ Market Regime: {market_state.get('macro_regime', 'unknown')}")
    print(f"✅ Allowed Exposure: {allowed_exposure:.1%}")
    print(f"✅ Strategies: {len([k for k in allocations if k != 'cash'])}")
    print(f"✅ Total Positions: {len(portfolio_data) if 'portfolio_data' in locals() else 0}")
    
    print("\n📋 NEXT STEPS:")
    print("   1. View dashboard: streamlit run src/dashboard/northstar_command_bridge.py")
    print("   2. Run backtest: python run.py --mode=backtest")
    print("   3. Check system health: python scripts/full_system_activation.py")
    
    print("\n✅ Portfolio generation complete!")

if __name__ == "__main__":
    main()
