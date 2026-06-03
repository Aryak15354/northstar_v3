#!/usr/bin/env python3
"""
🌬️ SIMPLE TAILWIND ENGINE - NORTHSTAR V3 PHASE 3
Simplified strategy tailwinds for institutional validation layers

This creates a simplified tailwind system that:
1. Computes tailwinds based on regime + historical strategy performance
2. Uses 60% Sharpe + 40% regime-based tailwind weighting
3. Skips complex beta drift calculation (deferred to Phase 6)
4. Integrates cleanly with existing Capital_Allocator

Unlike the complex beta drift fabric, this focuses on:
- Simple regime-aware strategy scoring
- Historical performance-based tailwinds
- Clean integration with V3 architecture
- Regime-specific strategy preferences

Integration with V3:
- Uses RegimeMemorySystem for current regime detection
- Leverages existing strategy performance data
- Feeds into Capital_Allocator for enhanced allocation
- Stores data in standard V3 format

Output: data/intelligence/strategy_tailwinds.parquet
"""

import pandas as pd
import numpy as np
import os
import json
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

class SimpleTailwindEngine:
    """
    Simple Tailwind Engine for Phase 3
    
    Computes strategy tailwinds using:
    - Current regime detection from RegimeMemorySystem
    - Historical strategy performance by regime
    - Simple 60% Sharpe + 40% regime tailwind weighting
    - No complex beta drift (deferred to Phase 6)
    """
    
    def __init__(self):
        self.name = "Simple Tailwind Engine"
        self.version = "3.0"
        
        # Data paths
        self.paths = {
            'regime_memory': 'data/intelligence/regime_memory.parquet',
            'regime_metadata': 'data/intelligence/regime_metadata.json',
            'performance_summary': 'data/processed/performance_summary.parquet',
            'backtests': 'data/processed/backtests',
            'strategy_tailwinds': 'data/intelligence/strategy_tailwinds.parquet',
            'tailwind_metadata': 'data/intelligence/tailwind_metadata.json'
        }
        
        # Configuration
        self.config = {
            'sharpe_weight': 0.6,           # 60% weight on Sharpe ratio
            'regime_weight': 0.4,           # 40% weight on regime tailwind
            'min_periods': 12,              # Minimum periods for strategy analysis
            'lookback_months': 24,          # 2 years lookback for performance
            'regime_similarity_threshold': 0.7,  # Minimum similarity for regime match
        }
        
        # Regime-based strategy preferences
        # These are institutional best practices for different market regimes
        self.regime_preferences = {
            'Crisis': {
                'low_vol': 1.5,
                'quality_tilt': 1.4,
                'value_tilt': 1.2,
                'defensive': 1.3,
                'mom_6m': 0.6,
                'mom_12m': 0.7,
                'dual_momentum': 0.8,
                'growth': 0.5
            },
            'Expansion': {
                'mom_6m': 1.4,
                'mom_12m': 1.3,
                'dual_momentum': 1.2,
                'growth': 1.3,
                'northstar': 1.2,
                'quality_tilt': 1.1,
                'low_vol': 0.8,
                'value_tilt': 0.9
            },
            'Late-Expansion': {
                'quality_tilt': 1.3,
                'low_vol': 1.2,
                'northstar': 1.1,
                'value_tilt': 1.1,
                'mom_6m': 0.9,
                'mom_12m': 0.9,
                'growth': 0.8
            },
            'Slowdown': {
                'value_tilt': 1.4,
                'quality_tilt': 1.3,
                'low_vol': 1.2,
                'defensive': 1.2,
                'mom_6m': 0.7,
                'mom_12m': 0.8,
                'growth': 0.6
            }
        }
        self.family_preferences = {
            'Crisis': {'sentiment': 0.90, 'alternative': 0.92, 'ownership': 0.95},
            'Expansion': {'sentiment': 1.10, 'alternative': 1.08, 'ownership': 1.05},
            'Late-Expansion': {'sentiment': 1.02, 'alternative': 1.10, 'ownership': 1.12},
            'Slowdown': {'sentiment': 0.96, 'alternative': 1.05, 'ownership': 1.08},
        }
        
        # Strategy performance tracking
        self.strategy_performance = {}
        self.current_regime = None

    @staticmethod
    def _normalize_tailwind_frame(tailwinds: pd.DataFrame) -> pd.DataFrame:
        """Normalize canonical and legacy tailwind schemas into a common layout."""
        if tailwinds is None or tailwinds.empty:
            return pd.DataFrame()

        df = tailwinds.copy()

        if "strategy" not in df.columns and "strategy_id" in df.columns:
            df["strategy"] = df["strategy_id"].astype(str)
        if "combined_score" not in df.columns and "tailwind_score" in df.columns:
            df["combined_score"] = pd.to_numeric(df["tailwind_score"], errors="coerce")
        if "regime_tailwind" not in df.columns and "tailwind_score" in df.columns:
            df["regime_tailwind"] = pd.to_numeric(df["tailwind_score"], errors="coerce")
        if "sharpe" not in df.columns and "tailwind_score" in df.columns:
            df["sharpe"] = pd.to_numeric(df["tailwind_score"], errors="coerce")
        if "date" not in df.columns and "as_of_date" in df.columns:
            df["date"] = pd.to_datetime(df["as_of_date"], errors="coerce")
        elif "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")

        if "regime" not in df.columns:
            df["regime"] = "unknown"

        required = {"strategy", "combined_score", "sharpe", "regime_tailwind", "regime"}
        if not required.issubset(df.columns):
            return pd.DataFrame()

        keep = ["strategy", "combined_score", "sharpe", "regime_tailwind", "regime"]
        if "date" in df.columns:
            keep.append("date")
        return df[keep].copy()

    @staticmethod
    def _strategy_family(strategy_name: str) -> str:
        s = str(strategy_name or "").strip().lower()
        if any(token in s for token in ('ownership', 'shareholding', 'promoter')):
            return 'ownership'
        if any(token in s for token in ('sentiment', 'news')):
            return 'sentiment'
        if any(token in s for token in ('alternative', 'announcement', 'bulk', 'credit', 'pledge')):
            return 'alternative'
        return ''
    
    def load_strategy_performance(self):
        """Load strategy performance data from backtests"""
        
        print("📊 Loading strategy performance data...")
        
        strategy_data = {}
        
        # Load backtest results
        if os.path.exists(self.paths['backtests']):
            for file in os.listdir(self.paths['backtests']):
                if file.endswith('.parquet'):
                    strategy_name = file.replace('.parquet', '')
                    try:
                        df = pd.read_parquet(os.path.join(self.paths['backtests'], file))
                        if not df.empty and len(df) >= self.config['min_periods']:
                            # Calculate key metrics
                            returns = df['daily_return'] if 'daily_return' in df.columns else df.get('net_return', pd.Series())
                            
                            if not returns.empty:
                                # Annualized metrics
                                total_return = (1 + returns).prod() - 1
                                ann_return = (1 + returns.mean()) ** 252 - 1
                                volatility = returns.std() * np.sqrt(252)
                                sharpe = ann_return / volatility if volatility > 0 else 0
                                
                                # Risk metrics
                                max_dd = df['drawdown'].min() if 'drawdown' in df.columns else 0
                                win_rate = (returns > 0).mean()
                                
                                # Recent performance (last 6 months)
                                recent_returns = returns.tail(126)  # ~6 months of daily data
                                recent_sharpe = (recent_returns.mean() * 252) / (recent_returns.std() * np.sqrt(252)) if recent_returns.std() > 0 else 0
                                
                                strategy_data[strategy_name] = {
                                    'total_return': total_return,
                                    'ann_return': ann_return,
                                    'volatility': volatility,
                                    'sharpe': sharpe,
                                    'max_drawdown': max_dd,
                                    'win_rate': win_rate,
                                    'recent_sharpe': recent_sharpe,
                                    'n_periods': len(df),
                                    'returns': returns.tolist()
                                }
                    except Exception as e:
                        print(f"   ⚠️ Error loading {strategy_name}: {e}")
        
        print(f"   ✅ Loaded performance for {len(strategy_data)} strategies")
        self.strategy_performance = strategy_data
        return strategy_data
    
    def get_current_regime(self):
        """Get current market regime from RegimeMemorySystem"""
        
        print("🔍 Detecting current market regime...")
        
        try:
            # Load regime memory
            if os.path.exists(self.paths['regime_memory']):
                regime_memory = pd.read_parquet(self.paths['regime_memory'])
                
                if not regime_memory.empty:
                    # Get most recent regime
                    latest_regime = regime_memory.iloc[-1]
                    current_regime = latest_regime['Regime']
                    
                    print(f"   ✅ Current regime: {current_regime}")
                    self.current_regime = current_regime
                    return current_regime
            
            print("   ⚠️ No regime memory found, using default")
            self.current_regime = 'Late-Expansion'  # Default regime
            return self.current_regime
            
        except Exception as e:
            print(f"   ⚠️ Error detecting regime: {e}")
            self.current_regime = 'Late-Expansion'
            return self.current_regime
    
    def calculate_regime_tailwinds(self, strategy_data, current_regime):
        """Calculate regime-based tailwinds for each strategy"""
        
        print(f"🌬️ Calculating regime tailwinds for {current_regime}...")
        
        regime_tailwinds = {}
        regime_prefs = self.regime_preferences.get(current_regime, {})
        
        for strategy_name, data in strategy_data.items():
            # Get regime preference for this strategy
            base_preference = 1.0  # Neutral preference
            
            # Match strategy name to regime preferences
            for pref_key, pref_value in regime_prefs.items():
                if pref_key.lower() in strategy_name.lower():
                    base_preference = pref_value
                    break
            if base_preference == 1.0:
                family = self._strategy_family(strategy_name)
                base_preference = self.family_preferences.get(current_regime, {}).get(family, 1.0)
            
            # Adjust based on recent performance
            recent_sharpe = data.get('recent_sharpe', 0)
            performance_adjustment = 1.0
            
            if recent_sharpe > 1.0:
                performance_adjustment = 1.1  # Boost for good recent performance
            elif recent_sharpe < 0:
                performance_adjustment = 0.9  # Penalize for poor recent performance
            
            # Calculate final regime tailwind
            regime_tailwind = base_preference * performance_adjustment
            
            regime_tailwinds[strategy_name] = {
                'regime_preference': base_preference,
                'performance_adjustment': performance_adjustment,
                'regime_tailwind': regime_tailwind,
                'recent_sharpe': recent_sharpe
            }
        
        print(f"   ✅ Calculated tailwinds for {len(regime_tailwinds)} strategies")
        return regime_tailwinds
    
    def calculate_combined_scores(self, strategy_data, regime_tailwinds):
        """Calculate combined scores: 60% Sharpe + 40% regime tailwind"""
        
        print("⚖️ Calculating combined tailwind scores...")
        
        combined_scores = {}
        
        for strategy_name, data in strategy_data.items():
            if strategy_name not in regime_tailwinds:
                continue
            
            # Get components
            sharpe = data.get('sharpe', 0)
            regime_tailwind = regime_tailwinds[strategy_name]['regime_tailwind']
            
            # Normalize Sharpe ratio (cap at 3.0 for extreme values)
            normalized_sharpe = min(max(sharpe, -1.0), 3.0)
            
            # Calculate combined score
            combined_score = (
                self.config['sharpe_weight'] * normalized_sharpe +
                self.config['regime_weight'] * regime_tailwind
            )
            
            combined_scores[strategy_name] = {
                'sharpe': sharpe,
                'normalized_sharpe': normalized_sharpe,
                'regime_tailwind': regime_tailwind,
                'combined_score': combined_score,
                'sharpe_contribution': self.config['sharpe_weight'] * normalized_sharpe,
                'regime_contribution': self.config['regime_weight'] * regime_tailwind
            }
        
        print(f"   ✅ Calculated combined scores for {len(combined_scores)} strategies")
        return combined_scores
    
    def create_tailwind_dataframe(self, combined_scores, current_regime):
        """Create tailwind DataFrame for persistence"""
        
        print("📋 Creating tailwind DataFrame...")
        
        tailwind_data = []
        timestamp = datetime.now()
        
        for strategy_name, scores in combined_scores.items():
            tailwind_data.append({
                'date': timestamp.date(),
                'strategy': strategy_name,
                'regime': current_regime,
                'sharpe': scores['sharpe'],
                'normalized_sharpe': scores['normalized_sharpe'],
                'regime_tailwind': scores['regime_tailwind'],
                'combined_score': scores['combined_score'],
                'sharpe_contribution': scores['sharpe_contribution'],
                'regime_contribution': scores['regime_contribution']
            })
        
        tailwind_df = pd.DataFrame(tailwind_data)
        
        if not tailwind_df.empty:
            tailwind_df = tailwind_df.set_index('date')
        
        print(f"   ✅ Created tailwind DataFrame: {len(tailwind_df)} strategies")
        return tailwind_df
    
    def compute_strategy_tailwinds(self):
        """Main method to compute strategy tailwinds"""
        
        print("🌬️ COMPUTING SIMPLE STRATEGY TAILWINDS")
        print("=" * 60)
        
        # Load strategy performance
        strategy_data = self.load_strategy_performance()
        
        if not strategy_data:
            print("❌ No strategy performance data available")
            return pd.DataFrame()
        
        # Get current regime
        current_regime = self.get_current_regime()
        
        # Calculate regime tailwinds
        regime_tailwinds = self.calculate_regime_tailwinds(strategy_data, current_regime)
        
        # Calculate combined scores
        combined_scores = self.calculate_combined_scores(strategy_data, regime_tailwinds)
        
        # Create tailwind DataFrame
        tailwind_df = self.create_tailwind_dataframe(combined_scores, current_regime)
        
        # Save results
        if not tailwind_df.empty:
            self.save_tailwinds(tailwind_df, combined_scores, current_regime)
            
            # Print summary
            print(f"\n📊 TAILWIND SUMMARY")
            print(f"   Current Regime: {current_regime}")
            print(f"   Strategies Analyzed: {len(tailwind_df)}")
            print(f"\n   Top 5 Strategies by Combined Score:")
            
            top_strategies = tailwind_df.nlargest(5, 'combined_score')
            for _, row in top_strategies.iterrows():
                print(f"     {row['strategy']}: {row['combined_score']:.3f} "
                      f"(Sharpe: {row['sharpe']:.2f}, Regime: {row['regime_tailwind']:.2f})")
        
        return tailwind_df
    
    def save_tailwinds(self, tailwind_df, combined_scores, current_regime):
        """Save tailwind data and metadata"""
        
        # Create output directory
        os.makedirs(os.path.dirname(self.paths['strategy_tailwinds']), exist_ok=True)
        
        # Save tailwind data
        tailwind_df.to_parquet(self.paths['strategy_tailwinds'])
        print(f"💾 Saved strategy tailwinds: {self.paths['strategy_tailwinds']}")
        
        # Save metadata
        metadata = {
            'created_at': datetime.now().isoformat(),
            'version': self.version,
            'config': self.config,
            'current_regime': current_regime,
            'n_strategies': len(tailwind_df),
            'regime_preferences': self.regime_preferences.get(current_regime, {}),
            'strategy_scores': {k: v['combined_score'] for k, v in combined_scores.items()},
            'top_strategies': tailwind_df.nlargest(10, 'combined_score')['strategy'].tolist()
        }
        
        with open(self.paths['tailwind_metadata'], 'w') as f:
            json.dump(metadata, f, indent=2, default=str)
        print(f"📋 Saved tailwind metadata: {self.paths['tailwind_metadata']}")
    
    def load_tailwinds(self):
        """Load existing tailwind data"""
        
        try:
            if os.path.exists(self.paths['strategy_tailwinds']):
                tailwinds = pd.read_parquet(self.paths['strategy_tailwinds'])
                normalized = self._normalize_tailwind_frame(tailwinds)
                print(f"📊 Loaded strategy tailwinds: {tailwinds.shape}")
                return normalized if not normalized.empty else tailwinds
        except Exception as e:
            print(f"⚠️ Could not load tailwinds: {e}")
        
        return pd.DataFrame()
    
    def get_strategy_tailwind(self, strategy_name):
        """Get tailwind score for a specific strategy"""
        
        try:
            tailwinds = self.load_tailwinds()
            
            if not tailwinds.empty:
                strategy_data = tailwinds[tailwinds['strategy'] == strategy_name]
                
                if not strategy_data.empty:
                    latest = strategy_data.iloc[-1]
                    return {
                        'strategy': strategy_name,
                        'combined_score': float(latest['combined_score']),
                        'sharpe': float(latest['sharpe']),
                        'regime_tailwind': float(latest['regime_tailwind']),
                        'regime': latest['regime'],
                        'date': latest.name.strftime('%Y-%m-%d')
                    }
            
            return None
            
        except Exception as e:
            print(f"⚠️ Error getting strategy tailwind: {e}")
            return None
    
    def get_all_tailwinds(self):
        """Get tailwind scores for all strategies"""
        
        try:
            tailwinds = self.load_tailwinds()
            
            if not tailwinds.empty:
                # Get latest tailwinds for each strategy
                latest_tailwinds = tailwinds.groupby('strategy').tail(1)
                
                result = {}
                for _, row in latest_tailwinds.iterrows():
                    result[row['strategy']] = {
                        'combined_score': float(row['combined_score']),
                        'sharpe': float(row['sharpe']),
                        'regime_tailwind': float(row['regime_tailwind']),
                        'regime': row['regime']
                    }
                
                return result
            
            return {}
            
        except Exception as e:
            print(f"⚠️ Error getting all tailwinds: {e}")
            return {}

def main():
    """Compute strategy tailwinds"""
    
    engine = SimpleTailwindEngine()
    tailwinds = engine.compute_strategy_tailwinds()
    
    if not tailwinds.empty:
        print(f"\n🎯 Simple tailwinds ready for Phase 3!")
        print(f"   Next step: Write property test for tailwind scores")
        return True
    else:
        print("❌ Failed to compute tailwinds")
        return False

if __name__ == "__main__":
    main()
