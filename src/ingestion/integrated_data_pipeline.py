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
        """Update RBI macro data pipeline using complete scraper → processor → cleaner chain"""
        print("\n🏦 UPDATING RBI MACRO DATA PIPELINE")
        print("-" * 50)
        
        success = True
        
        try:
            # Step 1: Run RBI scraper
            print("📥 Step 1: Running RBI scraper...")
            result = subprocess.run(
                [sys.executable, "-u", "src/ingestion/rbi_scraper.py"],
                text=True,
                timeout=600,
            )  # 10 min timeout
            
            if result.returncode == 0:
                print("✅ RBI scraper completed successfully")
            else:
                print(f"❌ RBI scraper failed: {result.stderr}")
                success = False
            
            # Step 2: Run RBI processor
            print("🔄 Step 2: Running RBI processor...")
            result = subprocess.run(
                [sys.executable, "-u", "src/ingestion/rbi_processor.py"],
                text=True,
                timeout=600,
            )  # 10 min timeout
            
            if result.returncode == 0:
                print("✅ RBI processor completed successfully")
            else:
                print(f"❌ RBI processor failed: {result.stderr}")
                success = False
            
            # Step 3: Run macro cleaner
            print("🧹 Step 3: Running macro cleaner...")
            result = subprocess.run(
                [sys.executable, "-u", "src/preprocessing/macro_cleaner.py"],
                text=True,
                timeout=600,
            )  # 10 min timeout
            
            if result.returncode == 0:
                print("✅ Macro cleaner completed successfully")
            else:
                print(f"❌ Macro cleaner failed: {result.stderr}")
                success = False
            
            if success:
                # Check if we have processed CSV files
                csv_files = []
                raw_dir = "data/macro/raw"
                if os.path.exists(raw_dir):
                    csv_files = [f for f in os.listdir(raw_dir) if f.endswith('.csv')]
                
                # Check if we have cleaned data
                cleaned_file = "data/macro/cleaned/macro_cleaned.parquet"
                cleaned_exists = os.path.exists(cleaned_file)
                # Extra sanity: require a fresh write in this run window.
                cleaned_fresh = False
                try:
                    if cleaned_exists:
                        age_seconds = (datetime.now() - datetime.fromtimestamp(os.path.getmtime(cleaned_file))).total_seconds()
                        cleaned_fresh = age_seconds < 6 * 3600  # should have been written recently
                except Exception:
                    cleaned_fresh = False
                
                print(f"📊 Available macro CSV files: {len(csv_files)}")
                print(f"🧹 Cleaned macro data: {'✅ Available' if cleaned_exists else '❌ Missing'}")

                if cleaned_exists and not cleaned_fresh:
                    print("⚠️ Macro cleaner did not write a fresh artifact (macro_cleaned.parquet looks stale).")

                return bool(success and cleaned_exists and cleaned_fresh)
            else:
                return False
                
        except subprocess.TimeoutExpired:
            print("❌ RBI macro data pipeline timed out")
            return False
        except Exception as e:
            print(f"❌ RBI macro data pipeline error: {e}")
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

        # Local proxy fallbacks produced by scripts/update_index_data.py
        proxy_map = {
            'NIFTY': 'nifty_50',
            'BANKNIFTY': 'nifty_bank',
            'IT': 'nifty_it',
            'FMCG': 'nifty_fmcg',
            'AUTO': 'nifty_auto',
            'PHARMA': 'nifty_pharma',
            'METAL': 'nifty_metal',
            'REALTY': 'nifty_realty',
            'ENERGY': 'nifty_energy',
            'PSU': 'nifty_psu',
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
                    # Fallback: local proxy index parquet (works offline / DNS outage).
                    proxy_file = os.path.join("data/processed/index_data", f"{proxy_map.get(name, '').strip()}.parquet")
                    if os.path.exists(proxy_file):
                        try:
                            px = pd.read_parquet(proxy_file)
                            close_col = next((c for c in ["close", "Close", "adj_close", "Adj Close"] if c in px.columns), None)
                            if close_col and len(px) >= 2:
                                close_series = pd.to_numeric(px[close_col], errors="coerce").dropna()
                                if len(close_series) >= 2:
                                    current_close = float(close_series.iloc[-1])
                                    prev_close = float(close_series.iloc[-2])
                                    net_change = current_close - prev_close
                                    pct_change = (net_change / prev_close) * 100 if prev_close else 0.0
                                    market_data['indices'][name] = {
                                        'current_price': current_close,
                                        'previous_close': prev_close,
                                        'net_change': net_change,
                                        'pct_change': pct_change,
                                        'source': 'local_proxy'
                                    }
                                    print(f"   🟡 {name}: {current_close:.2f} ({pct_change:+.2f}%) [local proxy]")
                                    continue
                        except Exception as proxy_err:
                            print(f"   ⚠️ {name}: Proxy fallback failed ({proxy_err})")
                    print(f"   ⚠️ {name}: No data available")
                    
            except Exception as e:
                # Exception path fallback to local proxy
                proxy_file = os.path.join("data/processed/index_data", f"{proxy_map.get(name, '').strip()}.parquet")
                if os.path.exists(proxy_file):
                    try:
                        px = pd.read_parquet(proxy_file)
                        close_col = next((c for c in ["close", "Close", "adj_close", "Adj Close"] if c in px.columns), None)
                        if close_col and len(px) >= 2:
                            close_series = pd.to_numeric(px[close_col], errors="coerce").dropna()
                            if len(close_series) >= 2:
                                current_close = float(close_series.iloc[-1])
                                prev_close = float(close_series.iloc[-2])
                                net_change = current_close - prev_close
                                pct_change = (net_change / prev_close) * 100 if prev_close else 0.0
                                market_data['indices'][name] = {
                                    'current_price': current_close,
                                    'previous_close': prev_close,
                                    'net_change': net_change,
                                    'pct_change': pct_change,
                                    'source': 'local_proxy'
                                }
                                print(f"   🟡 {name}: {current_close:.2f} ({pct_change:+.2f}%) [local proxy]")
                                continue
                    except Exception as proxy_err:
                        print(f"   ❌ {name}: {e} | proxy failed: {proxy_err}")
                        continue
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
            # 1) Recompute canonical market_state.parquet from real macro + market inputs.
            from src.state.market_state import MarketStateEngine
            from src.state.unified_state_manager import UnifiedStateManager

            spine_state = None
            try:
                print("🧠 Computing canonical market state...")
                spine = MarketStateEngine()
                spine_state = spine.compute_market_state()
                spine.save_market_state(spine_state)
                print("✅ Canonical market state refreshed")
            except Exception as e:
                print(f"⚠️ Canonical market state refresh failed: {e}")

            # 2) Refresh unified aggregated state for downstream consumers.
            print("🧠 Computing unified market state...")
            engine = UnifiedStateManager()
            success = engine.update_all_state()
            if not success:
                print("❌ Market State Spine update failed")
                return None

            market_state = engine.get_unified_state()
            if not isinstance(market_state, dict):
                return None

            # Merge canonical spine metrics so legacy + new consumers see a single view.
            if isinstance(spine_state, dict):
                market_block = market_state.get('market', {}) or {}
                for key, value in spine_state.items():
                    if key not in market_block or market_block.get(key) in [None, "", "unknown"]:
                        market_block[key] = value
                # Compatibility aliases.
                if market_block.get('risk_on') is None and market_block.get('risk_on_probability') is not None:
                    market_block['risk_on'] = market_block.get('risk_on_probability')
                if market_block.get('stress_score') is None and market_block.get('stress_level') is not None:
                    market_block['stress_score'] = market_block.get('stress_level')
                if market_block.get('regime') in [None, "", "unknown"] and market_block.get('macro_regime'):
                    market_block['regime'] = market_block.get('macro_regime')
                market_state['market'] = market_block

            print("✅ Market State Spine integration complete")

            # Validate integration
            self.validate_spine_integration(market_state)
            
            return market_state
            
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
        
        # Check macro integration using artifact presence + expected state keys.
        market_data = market_state.get('market', {})
        macro_cleaned_file = "data/macro/cleaned/macro_cleaned.parquet"
        macro_artifact_available = os.path.exists(macro_cleaned_file)
        macro_keys_present = (
            ('regime' in market_data) and
            (('macro_score' in market_data) or ('risk_on' in market_data) or ('risk_on_probability' in market_data))
        )

        if macro_artifact_available and macro_keys_present:
            validation_results['macro_integration'] = True
            print("✅ RBI Macro Data: Properly integrated")
        else:
            print("⚠️ RBI Macro Data: Integration incomplete (missing artifact or state keys)")

        # Check market integration using market snapshot artifact + state keys.
        market_data_file = os.path.join(self.market_data_dir, "market_data_latest.json")
        market_artifact_available = False
        index_count = 0
        if os.path.exists(market_data_file):
            try:
                with open(market_data_file, "r") as f:
                    mkt = json.load(f)
                index_count = len((mkt or {}).get("indices", {}))
                market_artifact_available = index_count > 0
            except Exception:
                market_artifact_available = False

        market_keys_present = (
            (('health_score' in market_data) or ('stress_score' in market_data)) and
            (('breadth_pct' in market_data) or ('pulse_intensity' in market_data) or ('momentum_score' in market_data))
        )

        if market_artifact_available and market_keys_present:
            validation_results['market_integration'] = True
            print(f"✅ YFinance Market Data: Properly integrated ({index_count} indices)")
        else:
            print("⚠️ YFinance Market Data: Integration incomplete (missing artifact or state keys)")

        # Check spine coherence: confidence is computed and finite.
        confidence = (
            market_data.get('confidence')
            if market_data.get('confidence') is not None
            else market_data.get('regime_confidence')
        )
        confidence_valid = isinstance(confidence, (int, float)) and np.isfinite(float(confidence))
        if confidence_valid:
            validation_results['spine_coherence'] = True
            if float(confidence) >= 0.5:
                print("✅ Market State Spine: Coherent and confident")
            else:
                print("✅ Market State Spine: Coherent (low-confidence regime)")
        else:
            print("⚠️ Market State Spine: Confidence missing/invalid")
        
        # Overall assessment
        integration_score = sum(validation_results.values())
        
        if integration_score == 3:
            print("\n🎯 INTEGRATION STATUS: ✅ FULLY INTEGRATED")
        elif integration_score == 2:
            print("\n🎯 INTEGRATION STATUS: 🟡 PARTIALLY INTEGRATED")
        else:
            print("\n🎯 INTEGRATION STATUS: 🔴 INTEGRATION ISSUES")
        
        return validation_results
    
    def run_full_pipeline(self, macro_only=False, market_only=False, force_macro=False, force_market=False):
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
        
        # Update YFinance market data first (if needed and not macro-only).
        # This ordering is intentional: downstream macro joins and end-of-day
        # aggregation should run after fresh market closes are available.
        if not macro_only:
            if force_market:
                print("📈 Forcing market data update...")
                success_flags['market_success'] = self.update_yfinance_market_data()
            elif not freshness['market_fresh']:
                print("📈 Market data is stale - updating...")
                success_flags['market_success'] = self.update_yfinance_market_data()
            else:
                print("📈 Market data is fresh - skipping update")

        # Update RBI macro data (if not market-only). Allow force to capture
        # retrospective revisions after market update.
        if not market_only:
            if force_macro:
                print("📊 Forcing RBI macro data update (capture retrospective changes)...")
                success_flags['macro_success'] = self.update_rbi_macro_data()
            elif not freshness['macro_fresh']:
                print("📊 RBI macro data is stale - updating...")
                success_flags['macro_success'] = self.update_rbi_macro_data()
            else:
                print("📊 RBI macro data is fresh - skipping update")
        
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
            
            macro_score = market_data.get('macro_score')
            if macro_score is None and market_data.get('risk_on') is not None:
                # Derive an interpretable score from risk_on when macro_score is unavailable.
                macro_score = float(market_data.get('risk_on')) * 2.0 - 1.0
            if macro_score is None:
                macro_score = 0.0

            risk_on_prob = market_data.get('risk_on_probability')
            if risk_on_prob is None:
                risk_on_prob = market_data.get('risk_on', 0.0)
            allowed_exp = market_data.get('allowed_exposure', 0.0)
            health_score = market_data.get('health_score')
            if health_score is None and market_data.get('stress_score') is not None:
                health_score = max(0.0, min(1.0, 1.0 - float(market_data.get('stress_score'))))
            if health_score is None:
                health_score = 0.0

            confidence = market_data.get('confidence')
            if confidence is None:
                confidence = market_data.get('regime_confidence', 0.0)
            
            print(f"   Macro Score: {macro_score:+.2f}")
            print(f"   Risk-On Probability: {risk_on_prob:.1%}")
            # Display exposure consistently whether stored as fraction (0-1) or percent (0-100).
            allowed_exp_pct = allowed_exp * 100.0 if allowed_exp <= 1.0 else allowed_exp
            print(f"   Allowed Exposure: {allowed_exp_pct:.1f}%")
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

    def run_integration_only(self):
        """Run only Market State Spine integration from existing artifacts."""
        print("🧠 INTEGRATION-ONLY MODE")
        print("=" * 70)
        market_state = self.integrate_with_market_state_spine()
        if market_state is None:
            print("❌ Integration-only run failed")
            return False
        print("✅ Integration-only run succeeded")
        return True

def main():
    """Main execution with command line options"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Integrated Data Pipeline - Market State Spine Feeder")
    parser.add_argument("--macro-only", action="store_true", help="Update only RBI macro data")
    parser.add_argument("--market-only", action="store_true", help="Update only YFinance market data")
    parser.add_argument(
        "--integrate-only",
        action="store_true",
        help="Skip data updates and only recompute Market State Spine integration",
    )
    parser.add_argument("--force-macro", action="store_true", help="Force RBI scraper + processing even if data appears fresh (captures retrospective revisions)")
    parser.add_argument("--force-market", action="store_true", help="Force market update even if data appears fresh")
    
    args = parser.parse_args()
    
    # Validate arguments
    selected_modes = sum([bool(args.macro_only), bool(args.market_only), bool(args.integrate_only)])
    if selected_modes > 1:
        print("❌ Specify only one of --macro-only, --market-only, or --integrate-only")
        return False

    # Run pipeline
    pipeline = IntegratedDataPipeline()
    if args.integrate_only:
        success = pipeline.run_integration_only()
    else:
        success = pipeline.run_full_pipeline(
            macro_only=args.macro_only,
            market_only=args.market_only,
            force_macro=args.force_macro,
            force_market=args.force_market,
        )
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
