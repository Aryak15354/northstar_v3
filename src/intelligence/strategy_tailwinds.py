#!/usr/bin/env python3
"""
🌊 STRATEGY TAILWINDS - NORTHSTAR V3 ANTICIPATORY INTELLIGENCE
Converting Beta Drift Signals into Strategy Allocation Weights

This is the missing link between market sensitivity detection and capital allocation.
Instead of waiting for returns, we move capital when sensitivity shifts occur.

Integration with V3:
- Reads weekly beta drift files from the Market Nervous System
- Converts micro-edges into macro themes
- Maps themes to strategy exposures
- Provides anticipatory tailwinds for capital allocation

This is how hedge funds get paid: they see the storm before the clouds form.
"""

import pandas as pd
import numpy as np
import os
import glob
import json
from datetime import datetime, timedelta
from collections import defaultdict
import warnings
warnings.filterwarnings('ignore')

class StrategyTailwinds:
    """
    Strategy Tailwinds Engine - The Anticipatory Capital Allocator
    
    Converts beta drift signals into strategy allocation weights:
    1. Aggregates weekly beta drifts into macro themes
    2. Maps themes to strategy exposures
    3. Computes anticipatory tailwinds
    4. Provides forward-looking allocation signals
    """
    
    def __init__(self):
        self.name = "Strategy Tailwinds"
        self.version = "1.0"
        
        # Data paths
        self.paths = {
            'beta_drift_insights': 'data/beta_drift_insights',
            'strategy_exposures': 'data/intelligence/strategy_exposures.json',
            'tailwinds_output': 'data/intelligence/strategy_tailwinds.json',
            'theme_pressure': 'data/intelligence/theme_pressure.json',
            'sector_mapping': 'data/processed/sector_mapping.csv'
        }
        
        # Strategy macro exposure fingerprints
        # These define how each strategy responds to macro forces
        self.strategy_exposures = {
            'dual_momentum': {
                'FX_Pressure': 0.8,
                'Liquidity': 0.6,
                'Inflation': -0.2,
                'Credit_Stress': 0.1,
                'Growth': 1.0,
                'Risk_Appetite': 0.9,
                'Rates': -0.3,
                'Monetary_Policy': 0.4,
                'External_Sector': 0.7,
                'Banking_Health': 0.2,
                'Commodity_Pressure': 0.3,
                'Market_Structure': 0.8
            },
            'sector_tilt_momentum': {
                'FX_Pressure': 0.6,
                'Liquidity': 0.5,
                'Inflation': -0.3,
                'Credit_Stress': 0.2,
                'Growth': 0.9,
                'Risk_Appetite': 0.8,
                'Rates': -0.2,
                'Monetary_Policy': 0.3,
                'External_Sector': 0.5,
                'Banking_Health': 0.4,
                'Commodity_Pressure': 0.6,
                'Market_Structure': 0.7
            },
            'momentum_12m': {
                'FX_Pressure': 0.7,
                'Liquidity': 0.4,
                'Inflation': -0.1,
                'Credit_Stress': 0.0,
                'Growth': 0.8,
                'Risk_Appetite': 0.7,
                'Rates': -0.4,
                'Monetary_Policy': 0.2,
                'External_Sector': 0.6,
                'Banking_Health': 0.1,
                'Commodity_Pressure': 0.4,
                'Market_Structure': 0.6
            },
            'value_tilt': {
                'FX_Pressure': -0.4,
                'Liquidity': -0.3,
                'Inflation': 0.6,
                'Credit_Stress': 0.5,
                'Growth': -0.2,
                'Risk_Appetite': -0.3,
                'Rates': 0.6,
                'Monetary_Policy': -0.2,
                'External_Sector': -0.1,
                'Banking_Health': 0.7,
                'Commodity_Pressure': 0.4,
                'Market_Structure': -0.2
            },
            'low_vol': {
                'FX_Pressure': -0.2,
                'Liquidity': 0.1,
                'Inflation': 0.4,
                'Credit_Stress': 0.6,
                'Growth': -0.3,
                'Risk_Appetite': -0.5,
                'Rates': 0.4,
                'Monetary_Policy': 0.3,
                'External_Sector': -0.1,
                'Banking_Health': 0.5,
                'Commodity_Pressure': 0.2,
                'Market_Structure': -0.4
            },
            'quality_growth': {
                'FX_Pressure': 0.3,
                'Liquidity': 0.2,
                'Inflation': -0.1,
                'Credit_Stress': -0.2,
                'Growth': 0.7,
                'Risk_Appetite': 0.4,
                'Rates': -0.1,
                'Monetary_Policy': 0.1,
                'External_Sector': 0.2,
                'Banking_Health': 0.3,
                'Commodity_Pressure': 0.1,
                'Market_Structure': 0.3
            }
        }
        
        # Sector groupings for theme aggregation
        self.sector_groups = {
            'IT': ['INFY', 'TCS', 'HCLTECH', 'WIPRO', 'TECHM', 'LTIM', 'LTTS'],
            'Banking': ['HDFCBANK', 'ICICIBANK', 'SBIN', 'KOTAKBANK', 'AXISBANK', 'INDUSINDBK'],
            'Auto': ['MARUTI', 'M&M', 'BAJAJ-AUTO', 'EICHERMOT', 'HEROMOTOCO', 'TVSMOTOR'],
            'Pharma': ['SUNPHARMA', 'DRREDDY', 'CIPLA', 'DIVISLAB', 'LUPIN', 'AUROPHARMA'],
            'FMCG': ['HINDUNILVR', 'BRITANNIA', 'DABUR', 'MARICO', 'COLPAL', 'GODREJCP'],
            'Energy': ['RELIANCE', 'ONGC', 'IOC', 'BPCL', 'HINDPETRO', 'GAIL'],
            'Metals': ['TATASTEEL', 'HINDALCO', 'VEDL', 'JINDALSTEL', 'SAIL', 'NATIONALUM'],
            'Cement': ['ULTRACEMCO', 'SHREECEM', 'AMBUJACEM', 'ACC', 'RAMCOCEM'],
            'Telecom': ['BHARTIARTL', 'IDEA', 'INDUS TOWERS']
        }
    
    def load_beta_drift_data(self, lookback_weeks=8):
        """Load recent beta drift data for tailwind computation"""
        
        try:
            print(f"📊 Loading beta drift data (last {lookback_weeks} weeks)...")
            
            # Find all processed years
            if not os.path.exists(self.paths['beta_drift_insights']):
                print("❌ No beta drift data found")
                return pd.DataFrame()
            
            processed_years = [
                int(d) for d in os.listdir(self.paths['beta_drift_insights'])
                if d.isdigit() and os.path.isdir(os.path.join(self.paths['beta_drift_insights'], d))
            ]
            
            if not processed_years:
                print("❌ No processed years found")
                return pd.DataFrame()
            
            # Load recent data
            all_drifts = []
            weeks_loaded = 0
            
            # Start from most recent year and work backwards
            for year in sorted(processed_years, reverse=True):
                year_dir = os.path.join(self.paths['beta_drift_insights'], str(year))
                week_files = glob.glob(os.path.join(year_dir, 'week_*.parquet'))
                
                # Sort by week number (descending)
                week_files.sort(key=lambda x: int(x.split('week_')[1].split('.')[0]), reverse=True)
                
                for week_file in week_files:
                    if weeks_loaded >= lookback_weeks:
                        break
                    
                    try:
                        week_data = pd.read_parquet(week_file)
                        if not week_data.empty:
                            all_drifts.append(week_data)
                            weeks_loaded += 1
                    except Exception as e:
                        continue
                
                if weeks_loaded >= lookback_weeks:
                    break
            
            if all_drifts:
                combined_drifts = pd.concat(all_drifts, ignore_index=True)
                print(f"   ✅ Loaded {len(combined_drifts)} beta drifts from {weeks_loaded} weeks")
                print(f"   📅 Date range: {combined_drifts['date'].min().date()} to {combined_drifts['date'].max().date()}")
                return combined_drifts
            else:
                print("   ⚠️ No beta drift data found")
                return pd.DataFrame()
                
        except Exception as e:
            print(f"❌ Error loading beta drift data: {e}")
            return pd.DataFrame()
    
    def aggregate_theme_pressure(self, drift_df):
        """Aggregate beta drifts into macro theme pressures"""
        
        try:
            print("🧠 Aggregating beta drifts into macro themes...")
            
            if drift_df.empty:
                return {}
            
            # Group stocks by sector
            stock_to_sector = {}
            for sector, stocks in self.sector_groups.items():
                for stock in stocks:
                    stock_to_sector[stock] = sector
            
            # Aggregate pressure by factor and sector
            theme_pressure = defaultdict(lambda: defaultdict(float))
            factor_totals = defaultdict(float)
            
            for _, row in drift_df.iterrows():
                stock = row['stock']
                factor = row['factor']
                pressure = abs(row['beta_drift']) * row.get('confidence', 1.0) * row.get('novelty', 1.0)
                
                # Add to factor total
                factor_totals[factor] += pressure
                
                # Add to sector if we can map it
                sector = stock_to_sector.get(stock, 'Other')
                theme_pressure[factor][sector] += pressure
            
            # Convert to regular dict and normalize
            theme_dict = {}
            for factor in factor_totals:
                if factor_totals[factor] > 0:
                    theme_dict[factor] = {
                        'total_pressure': float(factor_totals[factor]),
                        'sector_breakdown': dict(theme_pressure[factor]),
                        'dominant_sector': max(theme_pressure[factor].items(), key=lambda x: x[1])[0] if theme_pressure[factor] else 'None'
                    }
            
            print(f"   ✅ Computed pressure for {len(theme_dict)} macro factors")
            
            # Show top themes
            if theme_dict:
                sorted_themes = sorted(theme_dict.items(), key=lambda x: x[1]['total_pressure'], reverse=True)
                print(f"   🔝 Top 3 macro themes:")
                for i, (factor, data) in enumerate(sorted_themes[:3]):
                    print(f"      {i+1}. {factor}: {data['total_pressure']:.3f} (dominant: {data['dominant_sector']})")
            
            return theme_dict
            
        except Exception as e:
            print(f"❌ Error aggregating theme pressure: {e}")
            return {}
    
    def compute_strategy_tailwinds(self, theme_pressure):
        """Compute strategy tailwinds from theme pressure"""
        
        try:
            print("🌊 Computing strategy tailwinds...")
            
            if not theme_pressure:
                return {}
            
            strategy_tailwinds = {}
            
            for strategy, exposures in self.strategy_exposures.items():
                tailwind = 0.0
                factor_contributions = {}
                
                for factor, pressure_data in theme_pressure.items():
                    if factor in exposures:
                        exposure = exposures[factor]
                        pressure = pressure_data['total_pressure']
                        contribution = exposure * pressure
                        
                        tailwind += contribution
                        factor_contributions[factor] = {
                            'exposure': float(exposure),
                            'pressure': float(pressure),
                            'contribution': float(contribution)
                        }
                
                strategy_tailwinds[strategy] = {
                    'total_tailwind': float(tailwind),
                    'factor_contributions': factor_contributions,
                    'rank': 0  # Will be filled later
                }
            
            # Rank strategies by tailwind
            sorted_strategies = sorted(strategy_tailwinds.items(), key=lambda x: x[1]['total_tailwind'], reverse=True)
            for rank, (strategy, data) in enumerate(sorted_strategies):
                strategy_tailwinds[strategy]['rank'] = rank + 1
            
            print(f"   ✅ Computed tailwinds for {len(strategy_tailwinds)} strategies")
            
            # Show top strategies
            print(f"   🏆 Top 3 strategies by tailwind:")
            for i, (strategy, data) in enumerate(sorted_strategies[:3]):
                print(f"      {i+1}. {strategy}: {data['total_tailwind']:+.3f}")
            
            return strategy_tailwinds
            
        except Exception as e:
            print(f"❌ Error computing strategy tailwinds: {e}")
            return {}
    
    def save_tailwinds(self, theme_pressure, strategy_tailwinds):
        """Save tailwinds data for capital allocation"""
        
        try:
            # Create output directory
            os.makedirs(os.path.dirname(self.paths['tailwinds_output']), exist_ok=True)
            
            # Save strategy tailwinds
            tailwinds_data = {
                'created_at': datetime.now().isoformat(),
                'version': self.version,
                'strategy_tailwinds': strategy_tailwinds,
                'summary': {
                    'total_strategies': len(strategy_tailwinds),
                    'positive_tailwinds': len([s for s in strategy_tailwinds.values() if s['total_tailwind'] > 0]),
                    'negative_tailwinds': len([s for s in strategy_tailwinds.values() if s['total_tailwind'] < 0]),
                    'strongest_tailwind': max(strategy_tailwinds.values(), key=lambda x: x['total_tailwind'])['total_tailwind'] if strategy_tailwinds else 0,
                    'weakest_tailwind': min(strategy_tailwinds.values(), key=lambda x: x['total_tailwind'])['total_tailwind'] if strategy_tailwinds else 0
                }
            }
            
            with open(self.paths['tailwinds_output'], 'w') as f:
                json.dump(tailwinds_data, f, indent=2)
            
            print(f"   💾 Saved strategy tailwinds: {self.paths['tailwinds_output']}")
            
            # Save theme pressure
            theme_data = {
                'created_at': datetime.now().isoformat(),
                'version': self.version,
                'theme_pressure': theme_pressure,
                'summary': {
                    'total_themes': len(theme_pressure),
                    'strongest_theme': max(theme_pressure.items(), key=lambda x: x[1]['total_pressure'])[0] if theme_pressure else 'None',
                    'total_pressure': sum(data['total_pressure'] for data in theme_pressure.values())
                }
            }
            
            with open(self.paths['theme_pressure'], 'w') as f:
                json.dump(theme_data, f, indent=2)
            
            print(f"   💾 Saved theme pressure: {self.paths['theme_pressure']}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error saving tailwinds: {e}")
            return False
    
    def build_strategy_tailwinds(self, lookback_weeks=8):
        """Build complete strategy tailwinds from beta drift signals"""
        
        start_time = datetime.now()
        
        print("🌊 BUILDING STRATEGY TAILWINDS - ANTICIPATORY CAPITAL ALLOCATION")
        print("=" * 70)
        print("Converting beta drift signals into strategy allocation weights")
        print("This is how capital moves before prices do")
        print()
        
        # Load beta drift data
        drift_df = self.load_beta_drift_data(lookback_weeks)
        
        if drift_df.empty:
            print("❌ No beta drift data available")
            return False
        
        # Aggregate into theme pressure
        theme_pressure = self.aggregate_theme_pressure(drift_df)
        
        if not theme_pressure:
            print("❌ No theme pressure computed")
            return False
        
        # Compute strategy tailwinds
        strategy_tailwinds = self.compute_strategy_tailwinds(theme_pressure)
        
        if not strategy_tailwinds:
            print("❌ No strategy tailwinds computed")
            return False
        
        # Save results
        if not self.save_tailwinds(theme_pressure, strategy_tailwinds):
            print("❌ Failed to save tailwinds")
            return False
        
        processing_time = (datetime.now() - start_time).total_seconds()
        
        print("=" * 70)
        print("✅ STRATEGY TAILWINDS COMPLETED!")
        print(f"   📊 Processed {len(drift_df)} beta drifts")
        print(f"   🧠 Generated {len(theme_pressure)} macro themes")
        print(f"   🌊 Computed {len(strategy_tailwinds)} strategy tailwinds")
        print(f"   ⏱️  Processing time: {processing_time:.1f} seconds")
        print()
        print("🎯 INTEGRATION READY:")
        print("   Capital allocator can now use tailwinds for anticipatory positioning")
        print("   Strategies with positive tailwinds get increased allocation")
        print("   This happens BEFORE price moves, not after")
        
        return True
    
    def get_current_tailwinds(self):
        """Get current strategy tailwinds for capital allocation"""
        
        try:
            if os.path.exists(self.paths['tailwinds_output']):
                with open(self.paths['tailwinds_output'], 'r') as f:
                    data = json.load(f)
                return data.get('strategy_tailwinds', {})
            else:
                return {}
        except Exception as e:
            print(f"⚠️ Error loading current tailwinds: {e}")
            return {}

def main():
    """Build strategy tailwinds from beta drift signals"""
    
    tailwinds = StrategyTailwinds()
    
    print("🌊 STRATEGY TAILWINDS BUILDER")
    print("Converting market sensitivity shifts into capital allocation signals")
    print("=" * 60)
    
    success = tailwinds.build_strategy_tailwinds()
    
    if success:
        print("\n🎯 Strategy tailwinds ready for capital allocation!")
        print("   Next: Capital allocator uses these signals for anticipatory positioning")
        return True
    else:
        print("❌ Failed to build strategy tailwinds")
        return False

if __name__ == "__main__":
    main()