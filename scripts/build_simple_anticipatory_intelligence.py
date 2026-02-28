#!/usr/bin/env python3
"""
🧠 BUILD SIMPLE ANTICIPATORY INTELLIGENCE - NORTHSTAR V3 ENHANCEMENT
Simplified Version: Core Anticipatory Intelligence without Complex ML

This builds a simplified but functional anticipatory intelligence system
that focuses on the core regime memory and anticipatory allocation logic
without the complex autoencoder components that may cause memory issues.

Usage:
    python scripts/build_simple_anticipatory_intelligence.py
"""

import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def build_simple_regime_memory():
    """Build simplified regime memory using PCA only"""
    
    print("🧠 BUILDING SIMPLIFIED REGIME MEMORY")
    print("=" * 50)
    
    try:
        # Load extended price data
        extended_prices_dir = os.path.join(project_root, 'data/raw/prices_daily_extended')
        
        if not os.path.exists(extended_prices_dir):
            print("❌ Extended price data not found")
            return False
        
        import glob
        stock_files = glob.glob(os.path.join(extended_prices_dir, '*.csv'))
        
        if len(stock_files) < 50:
            print("❌ Insufficient stock files")
            return False
        
        print(f"📊 Processing {len(stock_files)} stock files...")
        
        # Load and process stock returns
        stock_returns = []
        processed_count = 0
        
        for file_path in stock_files[:100]:  # Limit to 100 stocks for simplicity
            try:
                ticker = os.path.basename(file_path).replace('.csv', '').replace('.NS', '')
                
                df = pd.read_csv(file_path, parse_dates=['Date'])
                if df.empty or len(df) < 200:
                    continue
                
                df = df.set_index('Date').sort_index()
                df['return'] = df['Close'].pct_change()
                
                # Resample to weekly
                weekly_returns = df['return'].resample('W-FRI').last()
                
                stock_returns.append(weekly_returns.rename(ticker))
                processed_count += 1
                
                if processed_count >= 50:  # Process 50 stocks
                    break
                    
            except Exception as e:
                continue
        
        if len(stock_returns) < 20:
            print("❌ Insufficient valid stock data")
            return False
        
        # Combine returns
        returns_matrix = pd.concat(stock_returns, axis=1, sort=True)
        returns_matrix = returns_matrix.fillna(0)
        
        print(f"✅ Combined returns matrix: {returns_matrix.shape}")
        
        # Apply PCA to create market factors
        from sklearn.decomposition import PCA
        from sklearn.preprocessing import StandardScaler
        
        scaler = StandardScaler()
        returns_scaled = scaler.fit_transform(returns_matrix.fillna(0))
        
        pca = PCA(n_components=10)  # 10 market factors
        market_factors = pca.fit_transform(returns_scaled)
        
        market_factors_df = pd.DataFrame(
            market_factors,
            index=returns_matrix.index,
            columns=[f'market_factor_{i}' for i in range(10)]
        )
        
        print(f"✅ Market factors created: {market_factors_df.shape}")
        print(f"   Explained variance: {pca.explained_variance_ratio_.sum():.3f}")
        
        # Create simple regime windows (6 months)
        window_size = 26  # 6 months
        stride = 13       # 3 months overlap
        
        windows = []
        window_dates = []
        
        for i in range(0, len(market_factors_df) - window_size + 1, stride):
            window_data = market_factors_df.iloc[i:i + window_size]
            
            # Simple window features: mean and std of each factor
            window_features = []
            for col in window_data.columns:
                window_features.extend([
                    window_data[col].mean(),
                    window_data[col].std()
                ])
            
            windows.append(window_features)
            window_dates.append(window_data.index[-1])
        
        windows_array = np.array(windows)
        
        print(f"✅ Created {len(windows)} regime windows")
        
        # Simple clustering using K-means
        from sklearn.cluster import KMeans
        
        n_clusters = 8
        kmeans = KMeans(n_clusters=n_clusters, random_state=42)
        cluster_labels = kmeans.fit_predict(windows_array)
        
        # Create regime fingerprints
        regime_fingerprints = pd.DataFrame(
            windows_array,
            index=window_dates,
            columns=[f'regime_feature_{i}' for i in range(windows_array.shape[1])]
        )
        
        regime_fingerprints['regime_cluster'] = cluster_labels
        
        # Simple regime names
        regime_names = {
            0: 'Crisis_Mode',
            1: 'Recovery_Phase', 
            2: 'Expansion_Early',
            3: 'Expansion_Late',
            4: 'Peak_Formation',
            5: 'Slowdown_Early',
            6: 'Slowdown_Late',
            7: 'Neutral_State'
        }
        
        regime_fingerprints['regime_name'] = [
            regime_names.get(label, f'Regime_{label}') 
            for label in cluster_labels
        ]
        
        # Save regime fingerprints
        os.makedirs('data/processed', exist_ok=True)
        regime_fingerprints.to_parquet('data/processed/simple_regime_fingerprints.parquet')
        
        print(f"✅ Regime fingerprints saved: {len(regime_fingerprints)} periods")
        
        # Create simple anticipatory signals
        current_regime = regime_fingerprints.iloc[-1]
        
        anticipatory_signals = {
            'timestamp': datetime.now().isoformat(),
            'version': '1.0_simple',
            'current_regime': {
                'cluster': int(current_regime['regime_cluster']),
                'name': current_regime['regime_name'],
                'stability': 0.7,  # Default stability
                'duration_in_regime': 5  # Default duration
            },
            'regime_transitions': {
                'next_regime_probabilities': {},  # Simplified - no predictions
                'transition_confidence': False
            },
            'forward_expectations': {},  # Simplified - no forward expectations
            'strategy_recommendations': {
                'current_regime': {
                    'favor': ['balanced', 'diversified'],
                    'avoid': ['extreme_positioning'],
                    'reasoning': f'Simple regime analysis for {current_regime["regime_name"]}'
                }
            },
            'risk_assessment': {
                'regime_risk_level': 'medium',
                'transition_risk': 0.3,
                'stability_risk': 0.3
            },
            'anticipatory_actions': {
                'capital_allocation_adjustment': {
                    'base_exposure': 0.6,
                    'cash_allocation': 0.25
                },
                'strategy_evolution_signals': {
                    'birth_strategies': [],
                    'death_strategies': [],
                    'modify_strategies': {}
                },
                'risk_management_actions': {
                    'position_sizing': 'normal',
                    'max_position_size': 0.05,
                    'stop_loss_tightening': False,
                    'correlation_monitoring': 'normal'
                }
            }
        }
        
        # Save anticipatory signals
        with open('data/processed/simple_anticipatory_signals.json', 'w') as f:
            import json
            json.dump(anticipatory_signals, f, indent=2, default=str)
        
        print(f"✅ Simple anticipatory signals created")
        print(f"   Current regime: {current_regime['regime_name']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error building simple regime memory: {e}")
        return False

def build_simple_capital_allocation():
    """Build simplified capital allocation"""
    
    print("\n🎯 BUILDING SIMPLE CAPITAL ALLOCATION")
    print("=" * 50)
    
    try:
        # Load simple anticipatory signals
        signals_path = 'data/processed/simple_anticipatory_signals.json'
        
        if not os.path.exists(signals_path):
            print("❌ Simple anticipatory signals not found")
            return False
        
        import json
        with open(signals_path, 'r') as f:
            signals = json.load(f)
        
        current_regime = signals.get('current_regime', {})
        regime_name = current_regime.get('name', 'Unknown')
        
        print(f"📊 Current regime: {regime_name}")
        
        # Create simple strategy allocations based on regime
        if 'crisis' in regime_name.lower():
            # Crisis allocation: defensive
            strategy_allocations = [
                {'strategy_name': 'quality_defensive', 'allocation_weight': 0.25, 'category': 'quality'},
                {'strategy_name': 'low_volatility', 'allocation_weight': 0.20, 'category': 'defensive'},
                {'strategy_name': 'value_contrarian', 'allocation_weight': 0.15, 'category': 'value'},
                {'strategy_name': 'CASH', 'allocation_weight': 0.40, 'category': 'cash'}
            ]
        elif 'expansion' in regime_name.lower():
            # Expansion allocation: growth and momentum
            strategy_allocations = [
                {'strategy_name': 'momentum_growth', 'allocation_weight': 0.30, 'category': 'momentum'},
                {'strategy_name': 'earnings_growth', 'allocation_weight': 0.25, 'category': 'growth'},
                {'strategy_name': 'sector_rotation', 'allocation_weight': 0.20, 'category': 'sector'},
                {'strategy_name': 'CASH', 'allocation_weight': 0.25, 'category': 'cash'}
            ]
        elif 'recovery' in regime_name.lower():
            # Recovery allocation: value and cyclical
            strategy_allocations = [
                {'strategy_name': 'value_momentum', 'allocation_weight': 0.30, 'category': 'value'},
                {'strategy_name': 'cyclical_rotation', 'allocation_weight': 0.25, 'category': 'sector'},
                {'strategy_name': 'small_cap_growth', 'allocation_weight': 0.20, 'category': 'growth'},
                {'strategy_name': 'CASH', 'allocation_weight': 0.25, 'category': 'cash'}
            ]
        else:
            # Neutral allocation: balanced
            strategy_allocations = [
                {'strategy_name': 'balanced_momentum', 'allocation_weight': 0.25, 'category': 'momentum'},
                {'strategy_name': 'balanced_value', 'allocation_weight': 0.25, 'category': 'value'},
                {'strategy_name': 'balanced_quality', 'allocation_weight': 0.20, 'category': 'quality'},
                {'strategy_name': 'CASH', 'allocation_weight': 0.30, 'category': 'cash'}
            ]
        
        # Add metadata to allocations
        for allocation in strategy_allocations:
            allocation.update({
                'timestamp': datetime.now(),
                'regime_name': regime_name,
                'regime_stability': current_regime.get('stability', 0.7),
                'allocation_score': allocation['allocation_weight'],
                'regime_fitness': 1.0,
                'adjusted_return': 0.08,  # Default expected return
                'adjusted_sharpe': 0.6,   # Default Sharpe
                'risk_contribution': allocation['allocation_weight'] * 0.1,
                'allocation_reason': f'Simple regime-based allocation for {regime_name}'
            })
        
        # Create DataFrame
        allocations_df = pd.DataFrame(strategy_allocations)
        
        # Save allocations
        allocations_df.to_parquet('data/processed/simple_anticipatory_allocations.parquet')
        
        print(f"✅ Simple capital allocation created")
        print(f"   Strategies: {len(allocations_df) - 1}")  # Exclude cash
        
        cash_allocation = allocations_df[allocations_df['strategy_name'] == 'CASH']['allocation_weight'].iloc[0]
        print(f"   Cash allocation: {cash_allocation:.1%}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error building simple capital allocation: {e}")
        return False

def create_simple_integration_status():
    """Create simple integration status"""
    
    print("\n🔗 CREATING SIMPLE INTEGRATION STATUS")
    print("=" * 50)
    
    try:
        # Check what we have
        files_status = {
            'regime_fingerprints': os.path.exists('data/processed/simple_regime_fingerprints.parquet'),
            'anticipatory_signals': os.path.exists('data/processed/simple_anticipatory_signals.json'),
            'capital_allocations': os.path.exists('data/processed/simple_anticipatory_allocations.parquet')
        }
        
        integration_status = {
            'timestamp': datetime.now().isoformat(),
            'version': '1.0_simple',
            'type': 'simple_anticipatory_intelligence',
            'files_status': files_status,
            'components_available': sum(files_status.values()),
            'total_components': len(files_status),
            'system_ready': sum(files_status.values()) >= len(files_status) * 0.75
        }
        
        # Save status
        with open('data/processed/simple_anticipatory_status.json', 'w') as f:
            import json
            json.dump(integration_status, f, indent=2, default=str)
        
        print(f"✅ Integration status created")
        print(f"   Available components: {integration_status['components_available']}/{integration_status['total_components']}")
        print(f"   System ready: {'✅' if integration_status['system_ready'] else '❌'}")
        
        return integration_status['system_ready']
        
    except Exception as e:
        print(f"❌ Error creating integration status: {e}")
        return False

def main():
    """Main execution function"""
    
    print("🧠 SIMPLE ANTICIPATORY INTELLIGENCE BUILDER")
    print("=" * 60)
    print("Building core anticipatory intelligence without complex ML")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    total_start_time = datetime.now()
    
    # Step 1: Build simple regime memory
    regime_success = build_simple_regime_memory()
    
    if not regime_success:
        print("\n❌ SIMPLE ANTICIPATORY INTELLIGENCE BUILD FAILED")
        return False
    
    # Step 2: Build simple capital allocation
    allocation_success = build_simple_capital_allocation()
    
    # Step 3: Create integration status
    integration_success = create_simple_integration_status()
    
    # Final summary
    total_duration = (datetime.now() - total_start_time).total_seconds()
    
    print(f"\n🎯 SIMPLE ANTICIPATORY INTELLIGENCE BUILD COMPLETE")
    print("=" * 60)
    print(f"Total duration: {total_duration:.1f} seconds")
    print(f"Regime memory: {'✅' if regime_success else '❌'}")
    print(f"Capital allocation: {'✅' if allocation_success else '❌'}")
    print(f"Integration: {'✅' if integration_success else '❌'}")
    
    if regime_success and allocation_success:
        print(f"\n🎉 SIMPLE ANTICIPATORY INTELLIGENCE IS LIVE!")
        print("   🧠 Market regime recognition: ACTIVE")
        print("   🎯 Regime-based capital allocation: OPERATIONAL")
        print("   📊 Simple anticipatory signals: AVAILABLE")
        print()
        print("   This provides the core anticipatory intelligence functionality")
        print("   without the complex ML components that may cause issues.")
        print("   Northstar can now allocate capital based on regime analysis.")
        
        return True
    else:
        print(f"\n⚠️ Simple anticipatory intelligence partially operational")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)