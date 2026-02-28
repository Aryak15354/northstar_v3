#!/usr/bin/env python3
"""
🧠 RUN FULL INTELLIGENCE STACK
Generate intelligence for all stocks in the universe
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

from src.intelligence.intelligence_stack import IntelligenceStack
from src.state.unified_state_manager import UnifiedStateManager

def main():
    print("🧠 NORTHSTAR V3 - FULL INTELLIGENCE GENERATION")
    print("=" * 70)
    
    # Step 1: Get stock universe
    print("\n📊 STEP 1: Loading Stock Universe")
    print("-" * 70)
    
    try:
        # Get list of stocks from price data
        price_dir = project_root / 'data' / 'raw' / 'prices_daily'
        stock_files = list(price_dir.glob('*.csv'))
        all_tickers = [f.stem for f in stock_files]
        print(f"   Found {len(all_tickers)} stocks with price data")
        
        # Filter to stocks with recent data (check first 200)
        valid_tickers = []
        print("   Validating stock data...")
        
        for ticker in all_tickers[:200]:
            try:
                df = pd.read_csv(price_dir / f"{ticker}.csv")
                if len(df) > 100:  # At least 100 days of data
                    valid_tickers.append(ticker)
            except:
                pass
        
        print(f"   Valid stocks: {len(valid_tickers)}")
        print(f"   Sample: {valid_tickers[:10]}")
        
    except Exception as e:
        print(f"❌ Error loading universe: {e}")
        return
    
    # Step 2: Initialize Intelligence Stack
    print("\n🧠 STEP 2: Initializing Intelligence Stack")
    print("-" * 70)
    
    try:
        stack = IntelligenceStack()
        print("   ✅ Intelligence Stack initialized")
    except Exception as e:
        print(f"❌ Error initializing stack: {e}")
        return
    
    # Step 3: Run intelligence on stocks (in batches)
    print("\n🔬 STEP 3: Generating Intelligence")
    print("-" * 70)
    
    batch_size = 50
    total_batches = (len(valid_tickers) + batch_size - 1) // batch_size
    
    all_results = []
    successful = 0
    failed = 0
    
    for batch_num in range(min(total_batches, 4)):  # Process first 4 batches (200 stocks)
        start_idx = batch_num * batch_size
        end_idx = min(start_idx + batch_size, len(valid_tickers))
        batch_tickers = valid_tickers[start_idx:end_idx]
        
        print(f"\n   Batch {batch_num + 1}/{min(total_batches, 4)}: Processing {len(batch_tickers)} stocks...")
        
        for ticker in batch_tickers:
            try:
                # Run intelligence update for this ticker
                result = stack.run_intelligence_update(ticker)
                
                if result:
                    all_results.append(result)
                    successful += 1
                else:
                    failed += 1
                    
            except Exception as e:
                failed += 1
                if failed <= 3:  # Only print first 3 errors
                    print(f"      ⚠️ {ticker}: {str(e)[:50]}")
        
        print(f"      Progress: {successful} successful, {failed} failed")
    
    print(f"\n   ✅ Intelligence generation complete")
    print(f"   Total processed: {successful + failed}")
    print(f"   Successful: {successful}")
    print(f"   Failed: {failed}")
    
    # Step 4: Save intelligence results
    print("\n💾 STEP 4: Saving Intelligence Results")
    print("-" * 70)
    
    try:
        # Save to intelligence state file
        intelligence_dir = project_root / 'data' / 'intelligence'
        intelligence_dir.mkdir(exist_ok=True)
        
        intelligence_state = {
            'timestamp': datetime.now().isoformat(),
            'total_stocks': len(valid_tickers),
            'processed_stocks': successful + failed,
            'successful': successful,
            'failed': failed,
            'results': all_results[:100],  # Save first 100 for inspection
            'unified_conviction': successful / max(successful + failed, 1)
        }
        
        with open(intelligence_dir / 'intelligence_state.json', 'w') as f:
            json.dump(intelligence_state, f, indent=2)
        
        print(f"   ✅ Intelligence state saved")
        print(f"   Location: {intelligence_dir / 'intelligence_state.json'}")
        
    except Exception as e:
        print(f"   ⚠️ Warning saving results: {e}")
    
    # Step 5: Update unified state
    print("\n🔄 STEP 5: Updating Unified State")
    print("-" * 70)
    
    try:
        usm = UnifiedStateManager()
        usm.update_intelligence_state()
        usm.save_state()
        
        health = usm.compute_system_health()
        print(f"   System Health: {health['overall_health_score']:.1%}")
        print(f"   Intelligence Active: {'✅' if health['intelligence_active'] else '❌'}")
        print(f"   Intelligence Conviction: {health['intelligence_conviction']:.1%}")
        
    except Exception as e:
        print(f"   ⚠️ Warning: {e}")
    
    # Summary
    print("\n" + "=" * 70)
    print("🎯 INTELLIGENCE GENERATION SUMMARY")
    print("=" * 70)
    print(f"✅ Stocks Processed: {successful + failed}")
    print(f"✅ Successful: {successful}")
    print(f"⚠️ Failed: {failed}")
    print(f"✅ Success Rate: {successful / max(successful + failed, 1):.1%}")
    
    if successful > 0:
        print("\n📋 NEXT STEPS:")
        print("   1. Generate portfolio: python scripts/generate_portfolio.py")
        print("   2. View dashboard: streamlit run src/dashboard/northstar_command_bridge.py")
        print("   3. Run backtest: python run.py --mode=backtest")
    else:
        print("\n⚠️ No successful intelligence generation")
        print("   Check data availability and intelligence stack configuration")
    
    print("\n✅ Intelligence generation complete!")

if __name__ == "__main__":
    main()
