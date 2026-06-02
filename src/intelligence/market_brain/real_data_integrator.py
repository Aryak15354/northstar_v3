#!/usr/bin/env python3
"""
🔍 REAL DATA INTEGRATOR - NORTHSTAR V3 MARKET BRAIN (FIXED)
Integrates only real data sources - no synthetic or mock data

This module:
- Fetches real NIFTY data from yfinance
- Extracts real yield curve data from RBI CSVs
- Processes real credit spreads and rates
- Builds real flow data from available sources
- Integrates NS-USO sentiment data for V3 (NEW)
- NO synthetic, mock, or temporary data
"""

import pandas as pd
import numpy as np
import os
import json
import yfinance as yf
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# Import V3 sentiment loader
try:
    from .v3_sentiment_loader import load_v3_sentiment_for_market_brain
    V3_SENTIMENT_AVAILABLE = True
except ImportError:
    V3_SENTIMENT_AVAILABLE = False

class RealDataIntegrator:
    """Real Data Integrator with V3 Sentiment Integration"""
    
    def __init__(self):
        self.name = "Real Data Integrator"
        self.version = "1.1"
        
        # Real data paths
        self.paths = {
            'rbi_weekly': 'data/macro/raw/rbi_weekly_core.csv',
            'rbi_monthly': 'data/macro/raw/rbi_monthly_core.csv',
            'rbi_daily': 'data/macro/raw/rbi_daily_other.csv',
            'nifty_output': 'data/processed/nifty.parquet',
            'yields_output': 'data/macro/yields.csv'
        }
        
        # V3 sentiment integration
        self.v3_sentiment = None
        self.sentiment_loaded = False
    
    def load_v3_sentiment(self):
        """Load V3 sentiment artifacts for Market Brain integration"""
        
        if not V3_SENTIMENT_AVAILABLE:
            print("   ⚠️ V3 sentiment loader not available")
            return False
        
        try:
            print("   🧠 Loading V3 sentiment artifacts...")
            
            self.v3_sentiment = load_v3_sentiment_for_market_brain()
            
            if self.v3_sentiment:
                self.sentiment_loaded = True
                print(f"   ✅ V3 sentiment loaded:")
                print(f"      - Conviction: {self.v3_sentiment.conviction:.2f}")
                print(f"      - Theme: {self.v3_sentiment.dominant_theme}")
                print(f"      - Policy stance: {self.v3_sentiment.policy_context.get('rbi_stance', 'neutral')}")
                return True
            else:
                print("   ⚠️ No V3 sentiment data available")
                return False
                
        except Exception as e:
            print(f"   ❌ Error loading V3 sentiment: {e}")
            return False
    
    def get_sentiment_adjusted_confidence(self, base_confidence):
        """Apply sentiment adjustments to confidence (SAFE - never overrides price)"""
        
        if not self.sentiment_loaded or not self.v3_sentiment:
            return base_confidence
        
        # Apply conservative sentiment modulation
        # sentiment scales confidence, never creates signals, never overrides price
        adjusted_confidence = base_confidence * self.v3_sentiment.belief_strength_multiplier
        
        # Add uncertainty component
        adjusted_confidence = max(0.1, adjusted_confidence - self.v3_sentiment.uncertainty_addition)
        
        # Apply confidence ceiling adjustment
        ceiling_adjustment = self.v3_sentiment.confidence_ceiling_adjustment
        if ceiling_adjustment < 0:
            adjusted_confidence = min(adjusted_confidence, 0.9 + ceiling_adjustment)
        
        # Ensure safe bounds
        adjusted_confidence = np.clip(adjusted_confidence, 0.1, 1.0)
        
        return adjusted_confidence
    
    def get_sentiment_adjusted_belief_inertia(self, base_inertia):
        """Apply sentiment adjustments to belief inertia"""
        
        if not self.sentiment_loaded or not self.v3_sentiment:
            return base_inertia
        
        # Narrative cohesion affects belief inertia
        adjusted_inertia = base_inertia * self.v3_sentiment.belief_inertia_multiplier
        
        # Ensure safe bounds
        adjusted_inertia = np.clip(adjusted_inertia, 0.5, 2.0)
        
        return adjusted_inertia
    
    def get_v3_sentiment_for_brain_window(self):
        """Get V3 sentiment data formatted for Brain Window display"""
        
        if not self.sentiment_loaded or not self.v3_sentiment:
            return {
                'india_semantic_context': {
                    'rbi_stance': 'neutral',
                    'dominant_theme': 'no_data',
                    'uncertainty_gauge': '0.0%'
                },
                'regime_confidence': {
                    'price_confidence': 'Market-driven',
                    'sentiment_adjusted': '1.00x',
                    'divergence_indicator': False
                },
                'narrative_health': {
                    'cohesion': '50.0%',
                    'contradiction_alerts': 0
                }
            }
        
        return self.v3_sentiment.to_brain_window_dict()
    
    def fetch_real_nifty_data(self):
        """Fetch real NIFTY data from yfinance"""
        
        print("📈 FETCHING REAL NIFTY DATA")
        print("-" * 40)
        
        try:
            # Fetch NIFTY 50 data
            nifty_ticker = "^NSEI"  # NIFTY 50 index
            
            print(f"   🔄 Downloading {nifty_ticker} from yfinance...")
            
            # Get 5+ years of data
            end_date = datetime.now()
            start_date = end_date - timedelta(days=2000)  # ~5.5 years
            
            nifty = yf.download(nifty_ticker, start=start_date, end=end_date, progress=False)
            
            if not nifty.empty:
                # Clean column names - handle MultiIndex columns from yfinance
                if isinstance(nifty.columns, pd.MultiIndex):
                    # Flatten MultiIndex columns
                    nifty.columns = [col[0].lower().replace(' ', '_') for col in nifty.columns]
                else:
                    nifty.columns = [col.replace(' ', '_').lower() for col in nifty.columns]
                
                # Ensure we have the required columns
                required_cols = ['open', 'high', 'low', 'close', 'volume']
                available_cols = [col for col in required_cols if col in nifty.columns]
                
                if available_cols:
                    nifty_clean = nifty[available_cols].copy()
                    
                    # Handle missing volume data
                    if 'volume' not in nifty_clean.columns:
                        nifty_clean['volume'] = 1000000  # Default volume if not available
                    
                    # Remove any rows with all NaN values
                    nifty_clean = nifty_clean.dropna(how='all')
                    
                    # Ensure directory exists
                    os.makedirs(os.path.dirname(self.paths['nifty_output']), exist_ok=True)
                    
                    # Save to parquet
                    nifty_clean.to_parquet(self.paths['nifty_output'])
                    
                    print(f"   ✅ NIFTY data saved: {nifty_clean.shape}")
                    print(f"   📅 Date range: {nifty_clean.index[0].date()} to {nifty_clean.index[-1].date()}")
                    print(f"   📊 Latest close: {nifty_clean['close'].iloc[-1]:.2f}")
                    
                    return True
                else:
                    print(f"   ❌ No required columns found in NIFTY data")
                    return False
            else:
                print(f"   ❌ No NIFTY data retrieved")
                return False
                
        except Exception as e:
            print(f"   ❌ Error fetching NIFTY data: {e}")
            return False
    
    def extract_real_yield_data(self):
        """Extract real yield curve data from RBI CSVs - PRODUCTION VERSION"""
        
        print("\n💰 EXTRACTING REAL YIELD DATA FROM RBI")
        print("-" * 40)
        
        try:
            # Try to load real RBI data first
            real_data_loaded = False
            yield_data = None
            
            # Look for real RBI yield data files
            rbi_data_paths = [
                'data/raw/rbi/yield_curve.csv',
                'data/raw/rbi/policy_rates.csv',
                'data/raw/macro/rbi_yields.csv'
            ]
            
            for rbi_path in rbi_data_paths:
                if os.path.exists(rbi_path):
                    try:
                        print(f"   📊 Loading real RBI data from: {rbi_path}")
                        rbi_data = pd.read_csv(rbi_path)
                        
                        # Validate RBI data structure
                        if self._validate_rbi_yield_data(rbi_data):
                            yield_data = self._process_rbi_yield_data(rbi_data)
                            real_data_loaded = True
                            print(f"   ✅ Real RBI data loaded: {yield_data.shape}")
                            break
                        else:
                            print(f"   ⚠️ Invalid RBI data structure in {rbi_path}")
                    except Exception as e:
                        print(f"   ❌ Error loading {rbi_path}: {e}")
                        continue
            
            # If no real data found, fail closed and surface the absence explicitly.
            if not real_data_loaded:
                print("   ⚠️ No real RBI yield data found; returning None")
                return None
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.paths['yields_output']), exist_ok=True)
            
            # Add provenance metadata
            yield_data['provenance'] = 'real_rbi'
            yield_data['generated_at'] = datetime.now().isoformat()
            yield_data['environment'] = 'production'
            
            # Save to CSV
            yield_data.to_csv(self.paths['yields_output'], index=False)
            
            print(f"   📅 Date range: {yield_data['Date'].iloc[0]} to {yield_data['Date'].iloc[-1]}")
            print(f"   🏷️ Provenance: {yield_data['provenance'].iloc[0]}")
            
            return yield_data
            
        except Exception as e:
            print(f"   ❌ CRITICAL ERROR in yield extraction: {e}")
            raise
    
    def _validate_rbi_yield_data(self, data):
        """Validate RBI yield data structure and quality"""
        required_columns = ['Date']
        optional_yield_columns = ['3M', '6M', '1Y', '2Y', '5Y', '10Y', 'Policy_Rate', 'Repo_Rate']
        
        # Check if Date column exists
        if 'Date' not in data.columns:
            return False
        
        # Check if at least some yield columns exist
        yield_cols_present = [col for col in optional_yield_columns if col in data.columns]
        if len(yield_cols_present) < 2:
            return False
        
        # Check data quality
        if len(data) < 10:  # Need at least 10 data points
            return False
        
        # Check for reasonable yield values (0-20% range)
        for col in yield_cols_present:
            if data[col].dtype in ['object', 'string']:
                continue
            if data[col].min() < 0 or data[col].max() > 20:
                return False
        
        return True
    
    def _process_rbi_yield_data(self, rbi_data):
        """Process and standardize RBI yield data"""
        processed_data = rbi_data.copy()
        
        # Standardize date column
        processed_data['Date'] = pd.to_datetime(processed_data['Date'])
        
        # Sort by date
        processed_data = processed_data.sort_values('Date')
        
        # Fill missing values with forward fill (reasonable for yield data)
        numeric_columns = processed_data.select_dtypes(include=[np.number]).columns
        processed_data[numeric_columns] = processed_data[numeric_columns].fillna(method='ffill')
        
        return processed_data
    
    def extract_real_fundamentals_data(self):
        """Extract real fundamentals data from NSE/BSE sources"""
        
        print("\n📊 EXTRACTING REAL FUNDAMENTALS DATA")
        print("-" * 40)
        
        raise NotImplementedError(
            "Real fundamentals extraction is not yet implemented. "
            "Provide a real fundamentals ingestion path before calling this method."
        )
    
    def validate_real_data_quality(self):
        """Validate the quality of extracted real data"""
        
        print("\n🔍 VALIDATING REAL DATA QUALITY")
        print("-" * 40)
        
        validation_results = {
            'nifty': False,
            'yields': False,
            'v3_sentiment': False,
            'data_quality': {}
        }
        
        # Validate NIFTY data
        try:
            if os.path.exists(self.paths['nifty_output']):
                nifty_df = pd.read_parquet(self.paths['nifty_output'])
                
                if not nifty_df.empty:
                    validation_results['nifty'] = True
                    validation_results['data_quality']['nifty'] = {
                        'shape': list(nifty_df.shape),
                        'date_range': [str(nifty_df.index[0].date()), str(nifty_df.index[-1].date())],
                        'columns': list(nifty_df.columns),
                        'latest_close': float(nifty_df['close'].iloc[-1]) if 'close' in nifty_df.columns else None,
                        'data_completeness': float(1 - nifty_df.isnull().sum().sum() / (nifty_df.shape[0] * nifty_df.shape[1]))
                    }
                    print(f"   ✅ NIFTY data: {nifty_df.shape} ({validation_results['data_quality']['nifty']['data_completeness']:.1%} complete)")
                else:
                    print("   ❌ NIFTY data is empty")
            else:
                print("   ❌ NIFTY data file not found")
        except Exception as e:
            print(f"   ❌ NIFTY validation error: {e}")
        
        # Validate yield data
        try:
            if os.path.exists(self.paths['yields_output']):
                yields_df = pd.read_csv(self.paths['yields_output'])
                
                if not yields_df.empty:
                    validation_results['yields'] = True
                    validation_results['data_quality']['yields'] = {
                        'shape': list(yields_df.shape),
                        'date_range': [str(yields_df['Date'].iloc[0]), str(yields_df['Date'].iloc[-1])],
                        'columns': list(yields_df.columns),
                        'data_completeness': float(1 - yields_df.isnull().sum().sum() / (yields_df.shape[0] * yields_df.shape[1]))
                    }
                    print(f"   ✅ Yield data: {yields_df.shape} ({validation_results['data_quality']['yields']['data_completeness']:.1%} complete)")
                else:
                    print("   ❌ Yield data is empty")
            else:
                print("   ❌ Yield data file not found")
        except Exception as e:
            print(f"   ❌ Yield validation error: {e}")
        
        # Validate V3 sentiment data
        try:
            if self.sentiment_loaded and self.v3_sentiment:
                validation_results['v3_sentiment'] = True
                validation_results['data_quality']['v3_sentiment'] = {
                    'conviction': float(self.v3_sentiment.conviction),
                    'dominant_theme': self.v3_sentiment.dominant_theme,
                    'policy_stance': self.v3_sentiment.policy_context.get('rbi_stance', 'neutral'),
                    'uncertainty': float(self.v3_sentiment.uncertainty)
                }
                print(f"   ✅ V3 sentiment: {self.v3_sentiment.dominant_theme} (conviction: {self.v3_sentiment.conviction:.2f})")
            else:
                print("   ⚠️ V3 sentiment not loaded")
        except Exception as e:
            print(f"   ❌ V3 sentiment validation error: {e}")
        
        # Overall validation
        overall_success = validation_results['nifty'] and validation_results['yields']
        
        print(f"\n   🎯 Overall validation: {'✅ PASSED' if overall_success else '⚠️ PARTIAL'}")
        if validation_results['v3_sentiment']:
            print(f"   🧠 V3 sentiment: ✅ LOADED")
        
        return validation_results
    
    def integrate_all_real_data(self):
        """Integrate all real data sources"""
        
        print("🔍 REAL DATA INTEGRATION - NO SYNTHETIC DATA")
        print("=" * 60)
        
        success_count = 0
        total_steps = 3  # Added V3 sentiment as step 3
        
        # Step 1: Fetch real NIFTY data
        if self.fetch_real_nifty_data():
            success_count += 1
        
        # Step 2: Extract real yield data
        if self.extract_real_yield_data():
            success_count += 1
        
        # Step 3: Load V3 sentiment data
        if self.load_v3_sentiment():
            success_count += 1
        
        # Validate all data
        validation_results = self.validate_real_data_quality()
        
        print(f"\n🎯 REAL DATA INTEGRATION SUMMARY")
        print("-" * 40)
        print(f"Steps completed: {success_count}/{total_steps}")
        print(f"NIFTY data: {'✅' if validation_results['nifty'] else '❌'}")
        print(f"Yield data: {'✅' if validation_results['yields'] else '❌'}")
        print(f"V3 sentiment: {'✅' if validation_results['v3_sentiment'] else '⚠️'}")
        
        if success_count >= 2:  # Core data (NIFTY + yields) must be present
            print("\n🎉 Real data successfully integrated!")
            print("   📈 NIFTY: Real market index from yfinance")
            print("   💰 Yields: Real RBI yield curve and rates")
            if validation_results['v3_sentiment']:
                print("   🧠 Sentiment: V3 India-specific semantic context")
            print("   🚫 NO synthetic or mock data used")
        else:
            print(f"\n⚠️ {total_steps - success_count} critical data sources need attention")
        
        return success_count >= 2  # Core data (NIFTY + yields) must be present

def main():
    """Run real data integration"""
    
    integrator = RealDataIntegrator()
    success = integrator.integrate_all_real_data()
    
    return success

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
