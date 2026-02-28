#!/usr/bin/env python3
"""
🧠 SIMPLIFIED REGIME MEMORY SYSTEM - NORTHSTAR V3 PHASE 3
Simplified regime memory for institutional validation layers

This creates a simplified regime memory system that:
1. Uses existing Market_Brain components for regime detection
2. Stores regime history with performance data
3. Computes cosine similarity for regime matching
4. Integrates cleanly with V3 architecture

Unlike the complex enhanced system, this focuses on:
- Simple regime fingerprints from current market state
- Historical regime performance tracking
- Regime similarity matching for allocation decisions
- Clean integration with Capital_Allocator

Integration with V3:
- Uses existing macro_regime.py for regime classification
- Leverages Market_Brain data for regime fingerprints
- Feeds into Capital_Allocator for regime-aware allocation
- Stores data in standard V3 format

Output: data/intelligence/regime_memory.parquet
"""

import pandas as pd
import numpy as np
import os
import json
from datetime import datetime, timedelta
from sklearn.preprocessing import StandardScaler
from sklearn.metrics.pairwise import cosine_similarity
import warnings
warnings.filterwarnings('ignore')

class RegimeMemorySystem:
    """
    Simplified Regime Memory System for Phase 3
    
    Creates regime fingerprints and tracks performance using:
    - Current macro regime classification
    - Market state features as regime fingerprints
    - Historical regime performance tracking
    - Cosine similarity for regime matching
    """
    
    def __init__(self):
        self.name = "Regime Memory System"
        self.version = "3.0"
        
        # Data paths
        self.paths = {
            'market_state': 'data/processed/market_state.parquet',
            'macro_score': 'data/macro/factors/macro_score.parquet',
            'performance_summary': 'data/processed/performance_summary.parquet',
            'regime_memory': 'data/intelligence/regime_memory.parquet',
            'regime_metadata': 'data/intelligence/regime_metadata.json'
        }
        
        # Configuration
        self.config = {
            'min_regime_periods': 4,     # Minimum weeks in regime for stability
            'similarity_threshold': 0.7,  # Minimum similarity for regime match
            'lookback_weeks': 52,        # 1 year lookback for regime analysis
            'feature_columns': [         # Market state features for fingerprints
                'macro_score', 'vol_regime_score', 'liquidity_score',
                'risk_on_probability', 'market_stress', 'sector_breadth'
            ]
        }
        
        # Regime performance tracking
        self.regime_performance = {}
        self.scaler = StandardScaler()
    
    def load_market_data(self):
        """Load market state and macro regime data"""
        
        print("📊 Loading market data for regime analysis...")
        
        market_data = {}
        
        # Load macro score/regime (primary data source)
        if os.path.exists(self.paths['macro_score']):
            try:
                macro_df = pd.read_parquet(self.paths['macro_score'])
                if not macro_df.empty:
                    # Ensure datetime index
                    if not isinstance(macro_df.index, pd.DatetimeIndex):
                        if 'date' in macro_df.columns:
                            macro_df['date'] = pd.to_datetime(macro_df['date'])
                            macro_df = macro_df.set_index('date')
                    
                    market_data['macro_regime'] = macro_df
                    print(f"   ✅ Macro regime: {len(macro_df)} periods")
                    print(f"      Date range: {macro_df.index.min().date()} to {macro_df.index.max().date()}")
            except Exception as e:
                print(f"   ⚠️ Error loading macro regime: {e}")
        
        # Load performance data
        if os.path.exists(self.paths['performance_summary']):
            try:
                perf_df = pd.read_parquet(self.paths['performance_summary'])
                if not perf_df.empty:
                    # Fix performance data index
                    if 'date' in perf_df.columns:
                        perf_df['date'] = pd.to_datetime(perf_df['date'])
                        perf_df = perf_df.set_index('date')
                    elif not isinstance(perf_df.index, pd.DatetimeIndex):
                        # Create synthetic dates if no date column
                        if 'macro_regime' in market_data:
                            # Use last N dates from macro data
                            macro_dates = market_data['macro_regime'].index[-len(perf_df):]
                            perf_df.index = macro_dates
                    
                    market_data['performance'] = perf_df
                    print(f"   ✅ Performance data: {len(perf_df)} periods")
                    if isinstance(perf_df.index, pd.DatetimeIndex):
                        print(f"      Date range: {perf_df.index.min().date()} to {perf_df.index.max().date()}")
            except Exception as e:
                print(f"   ⚠️ Error loading performance: {e}")
        
        # Skip market state for now since it's minimal
        print("   ℹ️ Using macro regime data as primary source")
        
        return market_data
    
    def create_regime_fingerprints(self, market_data):
        """Create regime fingerprints from market state features"""
        
        print("🔍 Creating regime fingerprints...")
        
        if 'macro_regime' not in market_data:
            print("   ❌ Missing macro regime data")
            return pd.DataFrame()
        
        macro_df = market_data['macro_regime']
        
        # Start with macro regime data as base
        combined_df = macro_df.copy()
        
        # Create feature matrix for regime fingerprints
        feature_cols = []
        
        # Add macro features
        if 'MacroScore' in combined_df.columns:
            feature_cols.append('MacroScore')
        
        # Add available macro components
        macro_components = ['Contrib_G', 'Contrib_I', 'Contrib_L', 'Contrib_S', 'TrueStress']
        for col in macro_components:
            if col in combined_df.columns:
                feature_cols.append(col)
        
        # Add market stress features if available
        stress_features = ['MarketStress_z', 'MarketBreadth', 'MarketParticipation']
        for col in stress_features:
            if col in combined_df.columns:
                feature_cols.append(col)
        
        # If no features available, create basic ones
        if not feature_cols:
            print("   ⚠️ No features found, creating basic fingerprints")
            combined_df['basic_score'] = 0
            feature_cols = ['basic_score']
        
        # Create regime fingerprints
        fingerprint_df = combined_df[feature_cols + ['Regime']].copy()
        
        # Fill missing values
        fingerprint_df = fingerprint_df.fillna(method='ffill').fillna(0)
        
        # Normalize features for similarity calculation
        feature_matrix = fingerprint_df[feature_cols].values
        if len(feature_matrix) > 1:
            feature_matrix_scaled = self.scaler.fit_transform(feature_matrix)
            
            # Add scaled features to dataframe
            for i, col in enumerate(feature_cols):
                fingerprint_df[f'{col}_scaled'] = feature_matrix_scaled[:, i]
        
        print(f"   ✅ Created fingerprints: {len(fingerprint_df)} periods, {len(feature_cols)} features")
        print(f"      Features: {feature_cols}")
        return fingerprint_df
    
    def analyze_regime_performance(self, fingerprints, market_data):
        """Analyze historical performance by regime"""
        
        print("📈 Analyzing regime performance...")
        
        if 'performance' not in market_data:
            print("   ⚠️ No performance data available")
            return fingerprints
        
        perf_df = market_data['performance']
        
        # Use available performance columns
        perf_columns = []
        if 'northstar_return' in perf_df.columns:
            perf_columns.append('northstar_return')
        if 'net_return' in perf_df.columns:
            perf_columns.append('net_return')
        if 'drawdown' in perf_df.columns:
            perf_columns.append('drawdown')
        if 'volatility' in perf_df.columns:
            perf_columns.append('volatility')
        
        if not perf_columns:
            print("   ⚠️ No usable performance columns found")
            return fingerprints
        
        # Align performance with regime data
        aligned_df = pd.merge(
            fingerprints, perf_df[perf_columns], 
            left_index=True, right_index=True, how='left'
        )
        
        # Calculate regime performance statistics
        regime_stats = {}
        
        for regime in aligned_df['Regime'].unique():
            if pd.isna(regime):
                continue
                
            regime_data = aligned_df[aligned_df['Regime'] == regime]
            
            if len(regime_data) >= self.config['min_regime_periods']:
                # Use available return column
                return_col = 'net_return' if 'net_return' in regime_data.columns else 'northstar_return'
                returns = regime_data[return_col].dropna()
                
                if len(returns) > 0:
                    regime_stats[regime] = {
                        'avg_return': float(returns.mean()),
                        'volatility': float(returns.std()),
                        'sharpe': float(returns.mean() / returns.std()) if returns.std() > 0 else 0,
                        'max_drawdown': float(regime_data['drawdown'].min()) if 'drawdown' in regime_data.columns else 0,
                        'periods': int(len(regime_data)),
                        'win_rate': float((returns > 0).mean())
                    }
        
        # Add regime performance to fingerprints
        aligned_df['regime_avg_return'] = aligned_df['Regime'].map(
            lambda x: regime_stats.get(x, {}).get('avg_return', 0)
        )
        aligned_df['regime_sharpe'] = aligned_df['Regime'].map(
            lambda x: regime_stats.get(x, {}).get('sharpe', 0)
        )
        
        print(f"   ✅ Analyzed {len(regime_stats)} regimes")
        for regime, stats in regime_stats.items():
            print(f"      {regime}: {stats['avg_return']:.2%} return, {stats['sharpe']:.2f} Sharpe")
        
        self.regime_performance = regime_stats
        return aligned_df
    
    def calculate_regime_similarity(self, current_fingerprint, historical_fingerprints):
        """Calculate cosine similarity between current and historical regimes"""
        
        # Get feature columns (scaled versions)
        feature_cols = [col for col in historical_fingerprints.columns if col.endswith('_scaled')]
        
        if not feature_cols:
            print("   ⚠️ No scaled features for similarity calculation")
            return pd.Series(index=historical_fingerprints.index, data=0.0)
        
        # Current fingerprint vector
        current_vector = current_fingerprint[feature_cols].values.reshape(1, -1)
        
        # Historical fingerprint matrix
        historical_matrix = historical_fingerprints[feature_cols].values
        
        # Calculate cosine similarity
        similarities = cosine_similarity(current_vector, historical_matrix)[0]
        
        return pd.Series(index=historical_fingerprints.index, data=similarities)
    
    def get_current_regime_match(self, current_market_state):
        """Find best matching historical regime for current market state"""
        
        try:
            # Load existing regime memory
            if not os.path.exists(self.paths['regime_memory']):
                print("   ⚠️ No regime memory found, need to build first")
                return None
            
            regime_memory = pd.read_parquet(self.paths['regime_memory'])
            
            # Create current fingerprint
            feature_cols = [col for col in regime_memory.columns if not col.endswith('_scaled') and col not in ['Regime', 'regime_avg_return', 'regime_sharpe', 'monthly_return', 'sharpe_ratio', 'max_drawdown']]
            
            current_fingerprint = {}
            for col in feature_cols:
                current_fingerprint[col] = current_market_state.get(col, 0)
            
            # Scale current fingerprint using stored scaler
            current_vector = np.array([current_fingerprint[col] for col in feature_cols]).reshape(1, -1)
            current_scaled = self.scaler.transform(current_vector)
            
            # Add scaled features
            for i, col in enumerate(feature_cols):
                current_fingerprint[f'{col}_scaled'] = current_scaled[0, i]
            
            current_fp = pd.Series(current_fingerprint)
            
            # Calculate similarities
            similarities = self.calculate_regime_similarity(current_fp, regime_memory)
            
            # Find best match
            best_match_idx = similarities.idxmax()
            best_similarity = similarities.max()
            
            if best_similarity >= self.config['similarity_threshold']:
                matched_regime = regime_memory.loc[best_match_idx]
                
                return {
                    'regime': matched_regime['Regime'],
                    'similarity': float(best_similarity),
                    'match_date': best_match_idx.strftime('%Y-%m-%d'),
                    'expected_return': float(matched_regime.get('regime_avg_return', 0)),
                    'expected_sharpe': float(matched_regime.get('regime_sharpe', 0)),
                    'confidence': 'high' if best_similarity > 0.85 else 'medium'
                }
            else:
                return {
                    'regime': 'Unknown',
                    'similarity': float(best_similarity),
                    'match_date': None,
                    'expected_return': 0.0,
                    'expected_sharpe': 0.0,
                    'confidence': 'low'
                }
        
        except Exception as e:
            print(f"   ⚠️ Error matching current regime: {e}")
            return None
    
    def build_regime_memory(self):
        """Build complete regime memory system"""
        
        print("🧠 BUILDING SIMPLIFIED REGIME MEMORY SYSTEM")
        print("=" * 60)
        
        # Load market data
        market_data = self.load_market_data()
        
        if not market_data:
            print("❌ No market data available")
            return False
        
        # Create regime fingerprints
        fingerprints = self.create_regime_fingerprints(market_data)
        
        if fingerprints.empty:
            print("❌ Could not create regime fingerprints")
            return False
        
        # Analyze regime performance
        regime_memory = self.analyze_regime_performance(fingerprints, market_data)
        
        # Save regime memory
        self.save_regime_memory(regime_memory)
        
        print(f"\n✅ Regime memory system built successfully!")
        print(f"   Regime periods: {len(regime_memory)}")
        print(f"   Unique regimes: {regime_memory['Regime'].nunique()}")
        print(f"   Date range: {regime_memory.index.min().date()} to {regime_memory.index.max().date()}")
        
        return True
    
    def save_regime_memory(self, regime_memory):
        """Save regime memory data and metadata"""
        
        # Create output directory
        os.makedirs(os.path.dirname(self.paths['regime_memory']), exist_ok=True)
        
        # Save regime memory
        regime_memory.to_parquet(self.paths['regime_memory'])
        print(f"💾 Saved regime memory: {self.paths['regime_memory']}")
        
        # Save metadata
        metadata = {
            'created_at': datetime.now().isoformat(),
            'version': self.version,
            'config': self.config,
            'regime_performance': self.regime_performance,
            'n_periods': len(regime_memory),
            'n_regimes': int(regime_memory['Regime'].nunique()),
            'date_range': {
                'start': regime_memory.index.min().isoformat(),
                'end': regime_memory.index.max().isoformat()
            },
            'feature_columns': [col for col in regime_memory.columns if not col.endswith('_scaled') and col not in ['Regime', 'regime_avg_return', 'regime_sharpe']]
        }
        
        with open(self.paths['regime_metadata'], 'w') as f:
            json.dump(metadata, f, indent=2, default=str)
        print(f"📋 Saved regime metadata: {self.paths['regime_metadata']}")
    
    def load_regime_memory(self):
        """Load existing regime memory system"""
        
        try:
            if os.path.exists(self.paths['regime_memory']):
                regime_memory = pd.read_parquet(self.paths['regime_memory'])
                print(f"📊 Loaded regime memory: {regime_memory.shape}")
                return regime_memory
        except Exception as e:
            print(f"⚠️ Could not load regime memory: {e}")
        
        return pd.DataFrame()
    
    def get_regime_transitions(self):
        """Analyze historical regime transitions"""
        
        try:
            regime_memory = self.load_regime_memory()
            if regime_memory.empty:
                return {}
            
            # Calculate transition matrix
            regimes = regime_memory['Regime'].values
            unique_regimes = list(set(regimes))
            n_regimes = len(unique_regimes)
            
            transition_matrix = np.zeros((n_regimes, n_regimes))
            
            for i in range(len(regimes) - 1):
                current_regime = regimes[i]
                next_regime = regimes[i + 1]
                
                if current_regime in unique_regimes and next_regime in unique_regimes:
                    current_idx = unique_regimes.index(current_regime)
                    next_idx = unique_regimes.index(next_regime)
                    transition_matrix[current_idx, next_idx] += 1
            
            # Normalize to probabilities
            row_sums = transition_matrix.sum(axis=1, keepdims=True)
            transition_probs = np.divide(transition_matrix, row_sums, 
                                       out=np.zeros_like(transition_matrix), 
                                       where=row_sums!=0)
            
            # Convert to interpretable format
            transitions = {}
            for i, current_regime in enumerate(unique_regimes):
                transitions[current_regime] = {}
                for j, next_regime in enumerate(unique_regimes):
                    transitions[current_regime][next_regime] = float(transition_probs[i, j])
            
            return transitions
            
        except Exception as e:
            print(f"⚠️ Error analyzing regime transitions: {e}")
            return {}
    
    def get_regime_characteristics(self, regime_name):
        """Get characteristics of a specific regime"""
        
        try:
            regime_memory = self.load_regime_memory()
            if regime_memory.empty:
                return {}
            
            regime_data = regime_memory[regime_memory['Regime'] == regime_name]
            
            if regime_data.empty:
                return {}
            
            characteristics = {
                'regime_name': regime_name,
                'occurrences': len(regime_data),
                'percentage': len(regime_data) / len(regime_memory) * 100,
                'avg_return': float(regime_data['regime_avg_return'].mean()),
                'avg_sharpe': float(regime_data['regime_sharpe'].mean()),
                'recent_occurrences': regime_data.tail(3).index.strftime('%Y-%m-%d').tolist()
            }
            
            return characteristics
            
        except Exception as e:
            print(f"⚠️ Error getting regime characteristics: {e}")
            return {}

def main():
    """Build simplified regime memory system"""
    
    system = RegimeMemorySystem()
    success = system.build_regime_memory()
    
    if success:
        print(f"\n🎯 Regime memory ready for Phase 3!")
        print(f"   Next step: Implement property test for regime similarity")
        return True
    else:
        print("❌ Failed to build regime memory")
        return False

if __name__ == "__main__":
    main()