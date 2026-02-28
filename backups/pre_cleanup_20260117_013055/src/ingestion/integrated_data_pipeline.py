#!/usr/bin/env python3
"""
🔄 INTEGRATED DATA PIPELINE - MARKET STATE SPINE FEEDER
Orchestrates both RBI macro data and yfinance market data into unified Market State Spine

This is the SINGLE ENTRY POINT for all data ingestion that feeds the Market State Spine.
No engine should bypass this pipeline.

Key Integration Points:
1. RBI Macro Data → Macro State (regime, forces, momentum)
2. YFinance Market Data → Market Health (breadth, participation, volatility)
3. Both feed into Market State Spine for unified truth propagation

Usage:
    python src/ingestion/integrated_data_pipeline.py
    python src/ingestion/integrated_data_pipeline.py --macro-only
    python src/ingestion/integrated_data_pipeline.py --market-only
"""

import os
import sys
import subprocess
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import json
import warnings
warnings.filterwarnings('ignore')

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.ingestion.rbi_scraper import RBIScraper

class IntegratedDataPipeline:
    """
    Unified data pipeline that feeds Market State Spine
    
    Coordinates:
    - RBI macro data (scraping + processing)
    - YFinance market data (prices + indicators)
    - Market State Spine integration
    """
    
    def __init__(self):
        self.universe_file = "universe/nifty500.csv"
        self.raw_price_dir = "data/raw/prices_daily"
        self.market_data_dir = "data/options/live"
        self.macro_raw_dir = "data/macro/raw"
        
        # Create directories
        for dir_path in [self.raw_price_dir, self.market_data_dir, self.macro_raw_dir]:
            os.makedirs(dir_path, exist_ok=True)
    
    def check_data_freshness(self):
        """Check freshness of both macro and market data"""
        
        freshness_status = {
            'macro_fresh': False,
            'market_fresh': False,
            'macro_age_hours': 999,
            'market_age_hours': 999
        }
        
        # Check RBI macro data freshness
        try:
            macro_files = [f for f in os.listdir(self.macro_raw_dir) if f.endswith('.csv')]
            if macro_files:
                # Check newest macro file
                newest_macro = max([
                    os.path.join(self.macro_raw_dir, f) for f in macro_files
                ], key=os.path.getmtime)
                
                macro_age = (datetime.now() - datetime.fromtimestamp(os.path.getmtime(newest_macro))).total_seconds() / 3600
                freshness_status['macro_age_hours'] = macro_age
                freshness_status['macro_fresh'] = macro_age < 168  # 7 days
                
                print(f"📊 RBI Macro Data: {macro_age:.1f} hours old ({'Fresh' if freshness_status['macro_fresh'] else 'Stale'})")
        except Exception as e:
            print(f"⚠️ Error checking macro data: {e}")
        
        # Check market data freshness
        try:
            market_data_file = os.path.join(self.market_data_dir, "market_data_latest.json")
            if os.path.exists(market_data_file):
                market_age = (datetime.now() - datetime.fromtimestamp(os.path.getmtime(market_data_file))).total_seconds() / 3600
                freshness_status['market_age_hours'] = market_age
                freshness_status['market_fresh'] = market_age < 4  # 4 hours for more frequent updates
                
                print(f"📈 Market Data: {market_age:.1f} hours old ({'Fresh' if freshness_status['market_fresh'] else 'Stale'})")
        except Exception as e:
            print(f"⚠️ Error checking market data: {e}")
        
        return freshness_status
    
    def update_rbi_macro_data(self):
        """Update RBI macro data pipeline using the new daily updater"""
        print("\n🏦 UPDATING RBI MACRO DATA PIPELINE")
        print("-" * 50)
        
        try:
            # Use the new RBI daily updater for complete pipeline
            result = subprocess.run([
                sys.executable, "src/ingestion/rbi_daily_updater.py", "--force"
            ], capture_output=True, text=True, timeout=1800)  # 30 min timeout
            
            if result.returncode == 0:
                print("✅ RBI daily updater completed successfully")
                
                # Check if we have processed CSV files
                csv_files = []
                raw_dir = "data/macro/raw"
                if os.path.exists(raw_dir):
                    csv_files = [f for f in os.listdir(raw_dir) if f.endswith('.csv')]
                
                print(f"📊 Available macro CSV files: {len(csv_files)}")
                
                return len(csv_files) > 0
            else:
                print(f"❌ RBI daily updater failed with code {result.returncode}")
                print(f"STDERR: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            print("❌ RBI daily updater timed out (>30 minutes)")
            return False
        except Exception as e:
            print(f"❌ RBI daily updater error: {e}")
            return False
    
    def update_yfinance_market_data(self):
        """Update YFinance market data pipeline"""
        print("\n📈 UPDATING YFINANCE MARKET DATA PIPELINE")
        print("-" * 50)
        
        try:
            # Update individual stock prices
            print("📊 Updating individual stock prices...")
            price_result = subprocess.run([
                sys.executable, "src/ingestion/price_fetcher.py"
            ], capture_output=True, text=True, timeout=1800)  # 30 min timeout
            
            if price_result.returncode != 0:
                print(f"⚠️ Price fetcher had issues: {price_result.stderr}")
                # Continue anyway - we can work with existing data
            
            # Update market indices and create live market data
            print("📊 Updating market indices...")
            success = self.fetch_market_indices()
            
            if success:
                print("✅ Market data updated successfully")
                return True
            else:
                print("❌ Market data update failed")
                return False
                
        except Exception as e:
            print(f"❌ Market data update error: {e}")
            return False
    
    def fetch_market_indices(self):
        """Fetch key market indices for market health calculation"""
        
        # Key Indian market indices
        indices = {
            'NIFTY': '^NSEI',
            'BANKNIFTY': '^NSEBANK', 
            'IT': '^CNXIT',
            'FMCG': '^CNXFMCG',
            'AUTO': '^CNXAUTO',
            'PHARMA': '^CNXPHARMA',
            'METAL': '^CNXMETAL',
            'REALTY': '^CNXREALTY',
            'ENERGY': '^CNXENERGY',
            'PSU': '^CNXPSE'
        }
        
        market_data = {
            'timestamp': datetime.now().isoformat(),
            'indices': {}
        }
        
        print("📊 Fetching market indices...")
        
        for name, ticker in indices.items():
            try:
                # Get 2 days of data to calculate change
                data = yf.download(ticker, period='2d', progress=False)
                
                if not data.empty and len(data) >= 2:
                    current_close = float(data['Close'].iloc[-1])
                    prev_close = float(data['Close'].iloc[-2])
                    net_change = current_close - prev_close
                    pct_change = (net_change / prev_close) * 100
                    
                    market_data['indices'][name] = {
                        'current_price': current_close,
                        'previous_close': prev_close,
                        'net_change': net_change,
                        'pct_change': pct_change
                    }
                    
                    print(f"   ✅ {name}: {current_close:.2f} ({pct_change:+.2f}%)")
                    
                else:
                    print(f"   ⚠️ {name}: No data available")
                    
            except Exception as e:
                print(f"   ❌ {name}: {e}")
        
        # Save market data
        market_data_file = os.path.join(self.market_data_dir, "market_data_latest.json")
        
        try:
            with open(market_data_file, 'w') as f:
                json.dump(market_data, f, indent=2)
            
            print(f"💾 Market data saved: {market_data_file}")
            return True
            
        except Exception as e:
            print(f"❌ Error saving market data: {e}")
            return False
    
    def integrate_with_market_state_spine(self):
        """Integrate both data sources with Market State Spine"""
        print("\n🧠 INTEGRATING WITH MARKET STATE SPINE")
        print("-" * 50)
        
        try:
            # Import and run Market State Spine
            from src.state.unified_state_manager import UnifiedStateManager
            
            print("🧠 Computing unified market state...")
            engine = UnifiedStateManager()
            success = engine.update_all_state()
            
            if success:
                market_state = engine.get_unified_state()
                print("✅ Market State Spine integration complete")
                
                # Validate integration
                self.validate_spine_integration(market_state)
                
                return market_state
            else:
                print("❌ Market State Spine update failed")
                return None
            
        except Exception as e:
            print(f"❌ Market State Spine integration failed: {e}")
            return None
    
    def validate_spine_integration(self, market_state):
        """Validate that both data sources are properly integrated"""
        
        print("\n🔍 VALIDATING SPINE INTEGRATION")
        print("-" * 40)
        
        validation_results = {
            'macro_integration': False,
            'market_integration': False,
            'spine_coherence': False
        }
        
        # Check if market_state is valid
        if not market_state or not isinstance(market_state, dict):
            print("⚠️ Market State: Invalid or empty state")
            return validation_results
        
        # Check macro integration - use 'market' key from unified state
        market_data = market_state.get('market', {})
        macro_score = market_data.get('macro_score', 0.0)
        macro_regime = market_data.get('regime', 'neutral')
        
        if macro_score != 0.0 or macro_regime != 'neutral':
            validation_results['macro_integration'] = True
            print("✅ RBI Macro Data: Properly integrated")
        else:
            print("⚠️ RBI Macro Data: Using defaults (check macro pipeline)")
        
        # Check market integration  
        health_score = market_data.get('health_score', 0.5)
        breadth_pct = market_data.get('breadth_pct', 50.0)
        
        if health_score != 0.5 or breadth_pct != 50.0:
            validation_results['market_integration'] = True
            print("✅ YFinance Market Data: Properly integrated")
        else:
            print("⚠️ YFinance Market Data: Using defaults (check market data)")
        
        # Check spine coherence
        confidence = market_data.get('confidence', 0.5)
        
        if confidence > 0.5:
            validation_results['spine_coherence'] = True
            print("✅ Market State Spine: Coherent and confident")
        else:
            print("⚠️ Market State Spine: Low confidence (check data quality)")
        
        # Overall assessment
        integration_score = sum(validation_results.values())
        
        if integration_score == 3:
            print("\n🎯 INTEGRATION STATUS: ✅ FULLY INTEGRATED")
        elif integration_score == 2:
            print("\n🎯 INTEGRATION STATUS: 🟡 PARTIALLY INTEGRATED")
        else:
            print("\n🎯 INTEGRATION STATUS: 🔴 INTEGRATION ISSUES")
        
        return validation_results
    
    def run_full_pipeline(self, macro_only=False, market_only=False, force_macro=False):
        """Run complete integrated data pipeline"""
        
        print("🔄 INTEGRATED DATA PIPELINE - MARKET STATE SPINE FEEDER")
        print("=" * 70)
        print("RBI Macro + YFinance Market → Unified Market State Spine")
        print()
        
        start_time = datetime.now()
        
        # Check current data freshness
        freshness = self.check_data_freshness()
        
        success_flags = {
            'macro_success': True,
            'market_success': True,
            'spine_success': False
        }
        
        # Update RBI macro data (if not market-only). Allow force to capture retrospective revisions.
        if not market_only:
            if force_macro:
                print("📊 Forcing RBI macro data update (capture retrospective changes)...")
                success_flags['macro_success'] = self.update_rbi_macro_data()
            elif not freshness['macro_fresh']:
                print("📊 RBI macro data is stale - updating...")
                success_flags['macro_success'] = self.update_rbi_macro_data()
            else:
                print("📊 RBI macro data is fresh - skipping update")
        
        # Update YFinance market data (if needed and not macro-only)
        if not macro_only:
            if not freshness['market_fresh']:
                print("📈 Market data is stale - updating...")
                success_flags['market_success'] = self.update_yfinance_market_data()
            else:
                print("📈 Market data is fresh - skipping update")
        
        # Always integrate with Market State Spine
        market_state = self.integrate_with_market_state_spine()
        success_flags['spine_success'] = market_state is not None
        
        # Pipeline summary
        duration = datetime.now() - start_time
        
        print(f"\n{'='*70}")
        print("INTEGRATED PIPELINE SUMMARY")
        print(f"{'='*70}")
        print(f"Duration: {duration}")
        
        if success_flags['macro_success']:
            print("✅ RBI Macro Pipeline: Operational")
        else:
            print("❌ RBI Macro Pipeline: Failed")
        
        if success_flags['market_success']:
            print("✅ YFinance Market Pipeline: Operational")
        else:
            print("❌ YFinance Market Pipeline: Failed")
        
        if success_flags['spine_success']:
            print("✅ Market State Spine: Integrated")
            
            # Handle nested state structure - use 'market' key
            market_data = market_state.get('market', {})
            
            macro_score = market_data.get('macro_score', 0.0)
            risk_on_prob = market_data.get('risk_on_probability', 0.0)
            allowed_exp = market_data.get('allowed_exposure', 0.0)
            health_score = market_data.get('health_score', 0.0)
            confidence = market_data.get('confidence', 0.0)
            
            print(f"   Macro Score: {macro_score:+.2f}")
            print(f"   Risk-On Probability: {risk_on_prob:.1%}")
            print(f"   Allowed Exposure: {allowed_exp:.1f}%")
            print(f"   Market Health: {health_score:.1%}")
            print(f"   Confidence: {confidence:.1%}")
        else:
            print("❌ Market State Spine: Integration Failed")
        
        # Overall status
        total_success = sum(success_flags.values())
        
        if total_success == 3:
            print(f"\n🧠 SYSTEM STATUS: ✅ FULLY OPERATIONAL")
            print("   Both data sources feeding Market State Spine")
        elif total_success >= 2 and success_flags['spine_success']:
            print(f"\n🧠 SYSTEM STATUS: 🟡 FUNCTIONAL")
            print("   Market State Spine operational with partial data")
        else:
            print(f"\n🧠 SYSTEM STATUS: 🔴 COMPROMISED")
            print("   Market State Spine integration issues")
        
        print(f"\n🎯 NEXT STEPS:")
        if total_success == 3:
            print("   ✅ System ready for trading decisions")
            print("   ✅ Run portfolio engines: python run_daily.py")
        else:
            print("   🔧 Fix data pipeline issues")
            print("   🔧 Check individual component logs")
        
        return total_success == 3

def main():
    """Main execution with command line options"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Integrated Data Pipeline - Market State Spine Feeder")
    parser.add_argument("--macro-only", action="store_true", help="Update only RBI macro data")
    parser.add_argument("--market-only", action="store_true", help="Update only YFinance market data")
    parser.add_argument("--force-macro", action="store_true", help="Force RBI scraper + processing even if data appears fresh (captures retrospective revisions)")
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.macro_only and args.market_only:
        print("❌ Cannot specify both --macro-only and --market-only")
        return False
    
    # Run pipeline
    pipeline = IntegratedDataPipeline()
    success = pipeline.run_full_pipeline(
        macro_only=args.macro_only,
        market_only=args.market_only,
        force_macro=args.force_macro,
    )
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)