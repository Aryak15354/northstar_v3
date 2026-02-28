#!/usr/bin/env python3
"""
🧠 NORTHSTAR UNIFIED TERMINAL - DATA LOADER
The data nervous system that makes the terminal feel like Bloomberg

This is the single source of truth for all dashboard data.
One cached snapshot = instant loading, perfect synchronization.
"""

import streamlit as st
import pandas as pd
import numpy as np
import json
import os
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# =========================== GOLDEN RULE: ONE SNAPSHOT ===========================

@st.cache_data(ttl=300)  # 5-minute cache
def load_unified_snapshot():
    """
    Load the unified dashboard snapshot
    
    This is the ONLY function all dashboards should use for real-time data.
    One file = instant loading, perfect synchronization.
    """
    
    snapshot_path = 'data/processed/cache/dashboard_snapshot.parquet'
    
    if not os.path.exists(snapshot_path):
        # Build snapshot if it doesn't exist
        build_dashboard_snapshot()
    
    try:
        df = pd.read_parquet(snapshot_path)
        if not df.empty:
            return df.iloc[0].to_dict()
    except Exception as e:
        print(f"⚠️ Snapshot load error: {e}")
    
    # Fallback to live data if snapshot fails
    return build_live_snapshot()

@st.cache_data(ttl=300)
def load_timeseries(file_path):
    """Load time series data with caching"""
    try:
        if os.path.exists(file_path):
            return pd.read_parquet(file_path)
        else:
            return pd.DataFrame()
    except Exception as e:
        print(f"⚠️ Timeseries load error for {file_path}: {e}")
        return pd.DataFrame()

# =========================== SNAPSHOT BUILDER ===========================

def build_dashboard_snapshot():
    """
    Build the unified dashboard snapshot
    
    This runs every 5 minutes to create the single source of truth
    """
    
    print("🧠 Building unified dashboard snapshot...")
    
    snapshot = {
        'timestamp': datetime.now(),
        'market': {},
        'portfolio': {},
        'strategies': {},
        'intelligence': {},
        'execution': {},
        'risk': {}
    }
    
    # MARKET STATE
    try:
        market_state = pd.read_parquet('data/processed/market_state.parquet')
        if not market_state.empty:
            latest = market_state.iloc[-1]
            snapshot['market'] = {
                'regime': latest.get('macro_regime', 'Neutral'),
                'allowed_exposure': latest.get('allowed_exposure', 50),
                'risk_on_prob': latest.get('risk_on_probability', 50),
                'liquidity_index': latest.get('liquidity_index', 50),
                'market_stability': latest.get('market_stability', 50),
                'coherence_score': latest.get('coherence_mean_60', 0.7)
            }
    except Exception as e:
        print(f"⚠️ Market state error: {e}")
        snapshot['market'] = {'regime': 'Unknown', 'allowed_exposure': 50}
    
    # MACRO SCORE
    try:
        macro_df = pd.read_parquet('data/macro/factors/macro_score.parquet')
        if not macro_df.empty:
            latest = macro_df.iloc[-1]
            snapshot['market'].update({
                'macro_score': latest.get('MacroScore', 0.0),
                'contrib_growth': latest.get('Contrib_G', 0.0),
                'contrib_inflation': latest.get('Contrib_I', 0.0),
                'contrib_liquidity': latest.get('Contrib_L', 0.0),
                'contrib_stress': latest.get('Contrib_S', 0.0)
            })
    except Exception:
        pass
    
    # PORTFOLIO STATE
    try:
        # Latest portfolio weights
        portfolio_df = pd.read_parquet('data/processed/portfolio_weights.parquet')
        if not portfolio_df.empty:
            total_exposure = portfolio_df['final_weight'].sum() * 100
            max_position = portfolio_df['final_weight'].max() * 100
            num_positions = len(portfolio_df)
            
            snapshot['portfolio'] = {
                'total_exposure': total_exposure,
                'max_position': max_position,
                'num_positions': num_positions,
                'top_holdings': portfolio_df.nlargest(10, 'final_weight')[['ticker', 'final_weight']].to_dict('records')
            }
    except Exception as e:
        print(f"⚠️ Portfolio error: {e}")
        snapshot['portfolio'] = {'total_exposure': 0, 'num_positions': 0}
    
    # PERFORMANCE
    try:
        pnl_df = pd.read_parquet('data/portfolio/pnl_on_paper.parquet')
        if not pnl_df.empty:
            latest_equity = pnl_df['Equity'].iloc[-1]
            
            # Calculate recent performance
            if len(pnl_df) > 20:
                recent_return = (latest_equity / pnl_df['Equity'].iloc[-21] - 1) * 100
                volatility = pnl_df['Daily_Return'].tail(20).std() * np.sqrt(252) * 100
                
                # Drawdown
                peak = pnl_df['Equity'].expanding().max()
                drawdown = ((pnl_df['Equity'] / peak - 1) * 100).iloc[-1]
            else:
                recent_return = 0
                volatility = 15
                drawdown = 0
            
            snapshot['portfolio'].update({
                'equity': latest_equity,
                'recent_return_20d': recent_return,
                'volatility_20d': volatility,
                'current_drawdown': drawdown
            })
    except Exception:
        pass
    
    # STRATEGY INTELLIGENCE
    try:
        # Strategy beliefs
        beliefs_df = pd.read_parquet('data/processed/strategy_beliefs.parquet')
        if not beliefs_df.empty:
            latest_beliefs = beliefs_df.iloc[-1]
            active_strategies = len([col for col in beliefs_df.columns if col.endswith('_status') and latest_beliefs.get(col) == 'ACTIVE'])
            
            snapshot['strategies'] = {
                'active_count': active_strategies,
                'total_count': len([col for col in beliefs_df.columns if col.endswith('_status')]),
                'avg_skill': beliefs_df.select_dtypes(include=[np.number]).iloc[-1].mean()
            }
    except Exception:
        snapshot['strategies'] = {'active_count': 0, 'total_count': 16}
    
    # CAPITAL ALLOCATION
    try:
        with open('data/processed/capital_allocations.json', 'r') as f:
            capital_data = json.load(f)
            
            allocated_strategies = len([s for s in capital_data.get('allocations', {}).values() if s > 0.01])
            max_allocation = max(capital_data.get('allocations', {}).values()) if capital_data.get('allocations') else 0
            
            snapshot['strategies'].update({
                'allocated_count': allocated_strategies,
                'max_allocation': max_allocation * 100,
                'capital_data': capital_data
            })
    except Exception:
        pass
    
    # AI INTELLIGENCE
    try:
        with open('data/intelligence/intelligence_state.json', 'r') as f:
            intelligence_data = json.load(f)
            
            snapshot['intelligence'] = {
                'status': intelligence_data.get('status', 'dormant'),
                'conviction': intelligence_data.get('conviction', 0.5),
                'regime_ai': intelligence_data.get('regime', 'neutral'),
                'primary_action': intelligence_data.get('primary_action', 'MAINTAIN_EXPOSURE'),
                'system_health': intelligence_data.get('system_health', {'grade': 'C'}),
                'narrative': intelligence_data.get('narrative', 'No narrative available')
            }
    except Exception:
        snapshot['intelligence'] = {'status': 'unavailable', 'conviction': 0.5}
    
    # RISK METRICS
    try:
        # Volatility state
        vol_df = pd.read_parquet('data/processed/volatility_state.parquet')
        if not vol_df.empty:
            latest_vol = vol_df.iloc[-1]
            snapshot['risk'] = {
                'market_vol': latest_vol.get('realized_vol', 0.15) * 100,
                'vol_regime': 'High' if latest_vol.get('realized_vol', 0.15) > 0.25 else 'Normal'
            }
    except Exception:
        snapshot['risk'] = {'market_vol': 15, 'vol_regime': 'Normal'}
    
    # EXECUTION
    try:
        # Recent trades
        trades_files = [f for f in os.listdir('data/portfolio/trades') if f.endswith('.parquet')]
        if trades_files:
            latest_trades = pd.read_parquet(f'data/portfolio/trades/{sorted(trades_files)[-1]}')
            snapshot['execution'] = {
                'recent_trades': len(latest_trades),
                'total_turnover': latest_trades['delta'].abs().sum() if 'delta' in latest_trades.columns else 0
            }
    except Exception:
        snapshot['execution'] = {'recent_trades': 0, 'total_turnover': 0}
    
    # Save snapshot
    os.makedirs('data/processed/cache', exist_ok=True)
    snapshot_df = pd.DataFrame([snapshot])
    snapshot_df.to_parquet('data/processed/cache/dashboard_snapshot.parquet')
    
    print(f"✅ Snapshot built: {len(snapshot)} components")
    return snapshot

def build_live_snapshot():
    """Fallback live snapshot builder"""
    return {
        'timestamp': datetime.now(),
        'market': {'regime': 'Unknown', 'allowed_exposure': 50},
        'portfolio': {'total_exposure': 0, 'num_positions': 0},
        'strategies': {'active_count': 0, 'total_count': 16},
        'intelligence': {'status': 'unavailable', 'conviction': 0.5},
        'risk': {'market_vol': 15, 'vol_regime': 'Normal'},
        'execution': {'recent_trades': 0, 'total_turnover': 0}
    }

# =========================== SPECIALIZED LOADERS ===========================

@st.cache_data(ttl=300)
def load_war_room_data():
    """Load war room specific data"""
    return {
        'market_stress': load_timeseries('data/processed/market_stress.parquet'),
        'shock_state': load_timeseries('data/risk/shock_state.parquet'),
        'breadth': load_timeseries('data/processed/breadth.parquet'),
        'correlations': load_timeseries('data/processed/correlations.parquet')
    }

@st.cache_data(ttl=300)
def load_portfolio_data():
    """Load portfolio command data"""
    return {
        'weights': load_timeseries('data/processed/portfolio_weights.parquet'),
        'performance': load_timeseries('data/portfolio/pnl_on_paper.parquet'),
        'trades': load_timeseries('data/portfolio/trades/latest.parquet') if os.path.exists('data/portfolio/trades/latest.parquet') else pd.DataFrame(),
        'attribution': load_timeseries('data/processed/performance_attribution.parquet')
    }

@st.cache_data(ttl=300)
def load_intelligence_data():
    """Load intelligence organism data"""
    return {
        'beliefs': load_timeseries('data/processed/strategy_beliefs.parquet'),
        'regret': load_timeseries('data/processed/strategy_regret.parquet'),
        'events': load_timeseries('data/processed/strategy_events.parquet'),
        'lineage': load_timeseries('data/processed/strategy_lineage.parquet')
    }

# =========================== HEALTH CHECK ===========================

def check_data_health():
    """Check the health of the data ecosystem"""
    
    health = {
        'snapshot_age': 0,
        'missing_files': [],
        'stale_files': [],
        'overall_grade': 'A'
    }
    
    # Check snapshot age
    snapshot_path = 'data/processed/cache/dashboard_snapshot.parquet'
    if os.path.exists(snapshot_path):
        age_minutes = (datetime.now() - datetime.fromtimestamp(os.path.getmtime(snapshot_path))).total_seconds() / 60
        health['snapshot_age'] = age_minutes
    else:
        health['missing_files'].append('dashboard_snapshot.parquet')
    
    # Check critical files
    critical_files = [
        'data/processed/market_state.parquet',
        'data/processed/portfolio_weights.parquet',
        'data/portfolio/pnl_on_paper.parquet'
    ]
    
    for file_path in critical_files:
        if not os.path.exists(file_path):
            health['missing_files'].append(file_path)
        else:
            age_hours = (datetime.now() - datetime.fromtimestamp(os.path.getmtime(file_path))).total_seconds() / 3600
            if age_hours > 24:
                health['stale_files'].append(f"{file_path} ({age_hours:.1f}h old)")
    
    # Grade calculation
    if health['missing_files']:
        health['overall_grade'] = 'D'
    elif health['stale_files'] or health['snapshot_age'] > 10:
        health['overall_grade'] = 'C'
    elif health['snapshot_age'] > 5:
        health['overall_grade'] = 'B'
    
    return health

# =========================== MAIN FUNCTIONS ===========================

if __name__ == "__main__":
    # Build snapshot manually
    snapshot = build_dashboard_snapshot()
    print("📊 Snapshot built successfully")
    
    # Check health
    health = check_data_health()
    print(f"🏥 Data health: {health['overall_grade']}")