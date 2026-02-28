#!/usr/bin/env python3
"""
🧭 NORTHSTAR V3 UNIFIED TERMINAL - PHASE 5
The Ultimate Investment Operating System Interface

This is the unified interface that brings together all Northstar V3 systems:
- Phase 1: Unified Entry Point & Master Orchestrator
- Phase 2: Data Pipeline Coordination  
- Phase 3: Intelligence Unification
- Phase 4: Portfolio & Risk Coordination
- Phase 5: Dashboard & Interface Unification

Built like Bloomberg Terminal + Two Sigma + Bridgewater War Room
"""

from src.cohesion.unified_state_manager import UnifiedStateManager, AuthorityLevel

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from datetime import datetime, timedelta
import os
import sys
import json
import warnings
warnings.filterwarnings('ignore')

# Add project root to path for imports
if project_root not in sys.path:
    pass  # Path already added
# =========================== TERMINAL CONFIGURATION ===========================

st.set_page_config(
    layout="wide", 
    page_title="🧭 Northstar V3 - Unified Investment Operating System",
    initial_sidebar_state="collapsed"
)

# =========================== UNIFIED TERMINAL STYLING ===========================

st.markdown("""
<style>
    /* NORTHSTAR V3 UNIFIED TERMINAL THEME */
    .main { padding: 0.3rem; }
    .block-container { padding: 0.5rem; max-width: 100%; }
    
    /* MASTER STATUS BAR - Shows all Phase 1-5 systems */
    .master-status-bar {
        background: linear-gradient(90deg, #001122, #002244, #003366);
        color: #00ff88;
        padding: 1rem 1.5rem;
        border-bottom: 3px solid #00ff88;
        position: sticky;
        top: 0;
        z-index: 1000;
        display: grid;
        grid-template-columns: repeat(8, 1fr);
        gap: 0.8rem;
        font-size: 0.85rem;
        font-weight: 700;
        box-shadow: 0 4px 15px rgba(0, 255, 136, 0.4);
        border-radius: 10px;
        margin-bottom: 1rem;
    }
    
    .status-metric {
        text-align: center;
        padding: 0.5rem;
        background: rgba(0, 255, 136, 0.1);
        border-radius: 8px;
        border: 1px solid rgba(0, 255, 136, 0.3);
        transition: all 0.3s ease;
    }
    
    .status-metric:hover {
        background: rgba(0, 255, 136, 0.2);
        border-color: #00ff88;
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0, 255, 136, 0.3);
    }
    
    .status-metric h5 {
        margin: 0;
        font-size: 0.65rem;
        color: #a0aec0;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    
    .status-metric h3 {
        margin: 0.2rem 0 0 0;
        font-size: 1rem;
        font-weight: 900;
    }
    
    /* PHASE INDICATORS */
    .phase-indicator {
        background: rgba(0, 255, 136, 0.15);
        border-left: 4px solid #00ff88;
        padding: 0.8rem;
        margin: 0.5rem 0;
        border-radius: 8px;
    }
    
    .phase-indicator h4 {
        margin: 0 0 0.3rem 0;
        color: #00ff88;
        font-size: 0.9rem;
        font-weight: 700;
    }
    
    .phase-indicator p {
        margin: 0;
        font-size: 0.8rem;
        color: #a0aec0;
    }
    
    /* COORDINATION PANELS */
    .coordination-panel {
        background: linear-gradient(135deg, #1a1a2e, #16213e);
        border: 2px solid #00ff88;
        border-radius: 12px;
        padding: 1rem;
        margin: 0.5rem 0;
    }
    
    .coordination-panel h3 {
        color: #00ff88;
        margin: 0 0 1rem 0;
        font-size: 1.1rem;
        font-weight: 900;
        text-align: center;
    }
    
    /* INTELLIGENCE PANEL */
    .intelligence-panel {
        background: linear-gradient(135deg, #2d1b69, #1e3a8a);
        border: 2px solid #60a5fa;
        border-radius: 12px;
        padding: 1rem;
        margin: 0.5rem 0;
    }
    
    .intelligence-panel h3 {
        color: #60a5fa;
        margin: 0 0 1rem 0;
        font-size: 1.1rem;
        font-weight: 900;
        text-align: center;
    }
    
    /* RISK PANEL */
    .risk-panel {
        background: linear-gradient(135deg, #7f1d1d, #991b1b);
        border: 2px solid #ff6b6b;
        border-radius: 12px;
        padding: 1rem;
        margin: 0.5rem 0;
    }
    
    .risk-panel h3 {
        color: #ff6b6b;
        margin: 0 0 1rem 0;
        font-size: 1.1rem;
        font-weight: 900;
        text-align: center;
    }
    
    /* PORTFOLIO PANEL */
    .portfolio-panel {
        background: linear-gradient(135deg, #065f46, #047857);
        border: 2px solid #10b981;
        border-radius: 12px;
        padding: 1rem;
        margin: 0.5rem 0;
    }
    
    .portfolio-panel h3 {
        color: #10b981;
        margin: 0 0 1rem 0;
        font-size: 1.1rem;
        font-weight: 900;
        text-align: center;
    }
    
    /* METRICS GRID */
    .metrics-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
        gap: 0.8rem;
        margin: 1rem 0;
    }
    
    .metric-card {
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 8px;
        padding: 0.8rem;
        text-align: center;
    }
    
    .metric-card h4 {
        margin: 0;
        font-size: 0.7rem;
        color: #a0aec0;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    
    .metric-card h2 {
        margin: 0.3rem 0 0 0;
        font-size: 1.3rem;
        font-weight: 900;
    }
</style>
""", unsafe_allow_html=True)

# =========================== DATA LOADING FUNCTIONS ===========================

@st.cache_data(ttl=60)
def load_unified_system_status():
    """Load unified system status from all Phase 1-5 components"""
    
    status = {
        'timestamp': datetime.now(),
        'phase_1': {'status': 'unknown', 'components': {}},
        'phase_2': {'status': 'unknown', 'components': {}},
        'phase_3': {'status': 'unknown', 'components': {}},
        'phase_4': {'status': 'unknown', 'components': {}},
        'phase_5': {'status': 'unknown', 'components': {}},
        'overall': {'status': 'unknown', 'health_score': 0.0}
    }
    
    # Phase 1: Foundation (Master Orchestrator, Unified State)
    try:
        if os.path.exists('data/processed/master_orchestrator_log.json'):
            with open('data/processed/master_orchestrator_log.json', 'r') as f:
                orchestrator_log = json.load(f)
                success_rate = orchestrator_log.get('success_rate', 0)
                status['phase_1']['status'] = 'active' if success_rate > 0.5 else 'degraded'
                status['phase_1']['components'] = {
                    'master_orchestrator': float(success_rate),
                    'unified_state': 1.0 if os.path.exists('data/processed/unified_state.json') else 0.0
                }
    except Exception as e:
        print(f"Phase 1 status error: {e}")
        status['phase_1']['status'] = 'offline'
        status['phase_1']['components'] = {'master_orchestrator': 0.0, 'unified_state': 0.0}
    
    # Phase 2: Data Pipeline
    try:
        if os.path.exists('data/processed/market_state.parquet'):
            market_df = pd.read_parquet('data/processed/market_state.parquet')
            if not market_df.empty:
                # Check data age
                if hasattr(market_df.index, 'max'):
                    latest_date = pd.to_datetime(market_df.index.max())
                else:
                    latest_date = datetime.now() - timedelta(hours=1)  # Assume recent
                
                data_age = (datetime.now() - latest_date).total_seconds() / 3600
                status['phase_2']['status'] = 'active' if data_age < 24 else 'stale'
                status['phase_2']['components'] = {
                    'data_pipeline': 1.0 if data_age < 24 else 0.5,
                    'market_state': 1.0 if not market_df.empty else 0.0
                }
            else:
                status['phase_2']['status'] = 'offline'
                status['phase_2']['components'] = {'data_pipeline': 0.0, 'market_state': 0.0}
    except Exception as e:
        print(f"Phase 2 status error: {e}")
        status['phase_2']['status'] = 'offline'
        status['phase_2']['components'] = {'data_pipeline': 0.0, 'market_state': 0.0}
    
    # Phase 3: Intelligence
    try:
        intelligence_active = False
        if os.path.exists('data/processed/capital_allocations.json'):
            with open('data/processed/capital_allocations.json', 'r') as f:
                allocations = json.load(f)
                allocations_dict = allocations.get('allocations', {})
                intelligence_active = len(allocations_dict) > 0
        
        status['phase_3']['status'] = 'active' if intelligence_active else 'offline'
        status['phase_3']['components'] = {
            'unified_intelligence': 1.0 if intelligence_active else 0.0,
            'market_brain': 1.0 if os.path.exists('data/processed/market_tensor.parquet') else 0.0
        }
    except Exception as e:
        print(f"Phase 3 status error: {e}")
        status['phase_3']['status'] = 'offline'
        status['phase_3']['components'] = {'unified_intelligence': 0.0, 'market_brain': 0.0}
    
    # Phase 4: Portfolio & Risk
    try:
        portfolio_active = os.path.exists('data/processed/portfolio_weights.parquet')
        risk_active = os.path.exists('data/risk/unified_risk_state.json')
        
        status['phase_4']['status'] = 'active' if portfolio_active and risk_active else 'degraded'
        status['phase_4']['components'] = {
            'portfolio_coordinator': 1.0 if portfolio_active else 0.0,
            'risk_coordinator': 1.0 if risk_active else 0.0
        }
    except Exception as e:
        print(f"Phase 4 status error: {e}")
        status['phase_4']['status'] = 'offline'
        status['phase_4']['components'] = {'portfolio_coordinator': 0.0, 'risk_coordinator': 0.0}
    
    # Phase 5: Dashboard (current)
    status['phase_5']['status'] = 'active'
    status['phase_5']['components'] = {
        'unified_terminal': 1.0,
        'dashboard_coordinator': 1.0
    }
    
    # Calculate overall health
    all_components = []
    for phase_key in ['phase_1', 'phase_2', 'phase_3', 'phase_4', 'phase_5']:
        phase_data = status[phase_key]
        if isinstance(phase_data, dict) and 'components' in phase_data:
            components = phase_data['components']
            if isinstance(components, dict):
                all_components.extend([v for v in components.values() if isinstance(v, (int, float))])
    
    status['overall']['health_score'] = np.mean(all_components) if all_components else 0.0
    status['overall']['status'] = 'healthy' if status['overall']['health_score'] > 0.8 else 'degraded'
    
    return status

@st.cache_data(ttl=60)
def load_portfolio_state():
    """Load current portfolio state"""
    
    portfolio_state = {
        'positions': 0,
        'exposure': 0.0,
        'top_positions': [],
        'strategy_allocation': {},
        'risk_metrics': {}
    }
    
    try:
        # Load portfolio weights
        if os.path.exists('data/processed/portfolio_weights.parquet'):
            portfolio_df = pd.read_parquet('data/processed/portfolio_weights.parquet')
            if not portfolio_df.empty:
                portfolio_state['positions'] = len(portfolio_df)
                portfolio_state['exposure'] = float(portfolio_df['final_weight'].sum())
                
                # Get top positions safely
                if 'ticker' in portfolio_df.columns and 'final_weight' in portfolio_df.columns:
                    top_positions_df = portfolio_df.nlargest(5, 'final_weight')
                    # Use standardized column names
                    columns_to_include = ['ticker', 'weight']  # Use standardized 'weight' column
                    
                    # Check for company name column with multiple possible names
                    company_name_candidates = ['Company Name', 'company_name', 'Company_Name']
                    for candidate in company_name_candidates:
                        if candidate in portfolio_df.columns:
                            columns_to_include.append(candidate)
                            break
                    
                    portfolio_state['top_positions'] = top_positions_df[columns_to_include].to_dict('records')
        
        # Load strategy allocations
        if os.path.exists('data/processed/capital_allocations.json'):
            with open('data/processed/capital_allocations.json', 'r') as f:
                allocations = json.load(f)
                if 'allocations' in allocations and isinstance(allocations['allocations'], dict):
                    portfolio_state['strategy_allocation'] = allocations['allocations']
        
        # Load risk metrics
        if os.path.exists('data/risk/unified_risk_state.json'):
            with open('data/risk/unified_risk_state.json', 'r') as f:
                risk_state = json.load(f)
                emergency_state = risk_state.get('emergency_state', {})
                risk_authority = risk_state.get('risk_authority', {})
                
                portfolio_state['risk_metrics'] = {
                    'emergency_active': emergency_state.get('emergency_active', False),
                    'risk_level': emergency_state.get('risk_level', 0.0),
                    'exposure_cap': risk_authority.get('final_exposure_cap', 1.0),
                    'authority_level': risk_authority.get('active_authority', 'SYSTEM')
                }
    
    except Exception as e:
        print(f"Error loading portfolio state: {e}")
        # Return default state on error
    
    return portfolio_state

@st.cache_data(ttl=60)
def load_market_intelligence():
    """Load market intelligence state"""
    
    intelligence = {
        'regime': 'unknown',
        'risk_on_prob': 0.5,
        'allowed_exposure': 0.6,
        'market_stability': 0.5,
        'intelligence_active': False
    }
    
    try:
        if os.path.exists('data/processed/market_state.parquet'):
            market_df = pd.read_parquet('data/processed/market_state.parquet')
            if not market_df.empty:
                latest = market_df.iloc[-1]
                intelligence['regime'] = latest.get('macro_regime', 'unknown')
                intelligence['risk_on_prob'] = float(latest.get('risk_on_probability', 0.5))
                
                # Handle allowed_exposure - could be percentage or decimal
                allowed_exp = latest.get('allowed_exposure', 60)
                if allowed_exp > 1:  # Assume it's a percentage
                    intelligence['allowed_exposure'] = float(allowed_exp) / 100
                else:  # Assume it's already a decimal
                    intelligence['allowed_exposure'] = float(allowed_exp)
                
                # Handle market_stability
                market_stab = latest.get('market_stability', 50)
                if market_stab > 1:  # Assume it's a percentage
                    intelligence['market_stability'] = float(market_stab) / 100
                else:  # Assume it's already a decimal
                    intelligence['market_stability'] = float(market_stab)
        
        # Check if AI intelligence is active
        if os.path.exists('data/processed/intelligent_market_state.parquet'):
            ai_df = pd.read_parquet('data/processed/intelligent_market_state.parquet')
            if not ai_df.empty:
                latest_ai = ai_df.iloc[-1]
                intelligence['intelligence_active'] = latest_ai.get('intelligence_status') == 'active'
    
    except Exception as e:
        print(f"Error loading market intelligence: {e}")
        # Return default values on error
    
    return intelligence

# =========================== TERMINAL COMPONENTS ===========================

def render_master_status_bar(system_status):
    """Render the master status bar showing all phases"""
    
    st.markdown("""
    <div class="master-status-bar">
        <div class="status-metric">
            <h5>Phase 1</h5>
            <h3>Foundation</h3>
            <p style="margin:0; font-size:0.6rem; color:#00ff88;">""" + system_status['phase_1']['status'].upper() + """</p>
        </div>
        <div class="status-metric">
            <h5>Phase 2</h5>
            <h3>Data Pipeline</h3>
            <p style="margin:0; font-size:0.6rem; color:#00ff88;">""" + system_status['phase_2']['status'].upper() + """</p>
        </div>
        <div class="status-metric">
            <h5>Phase 3</h5>
            <h3>Intelligence</h3>
            <p style="margin:0; font-size:0.6rem; color:#60a5fa;">""" + system_status['phase_3']['status'].upper() + """</p>
        </div>
        <div class="status-metric">
            <h5>Phase 4</h5>
            <h3>Portfolio</h3>
            <p style="margin:0; font-size:0.6rem; color:#10b981;">""" + system_status['phase_4']['status'].upper() + """</p>
        </div>
        <div class="status-metric">
            <h5>Phase 4</h5>
            <h3>Risk</h3>
            <p style="margin:0; font-size:0.6rem; color:#ff6b6b;">""" + ('ACTIVE' if system_status['phase_4']['components'].get('risk_coordinator', 0) > 0 else 'OFFLINE') + """</p>
        </div>
        <div class="status-metric">
            <h5>Phase 5</h5>
            <h3>Interface</h3>
            <p style="margin:0; font-size:0.6rem; color:#00ff88;">ACTIVE</p>
        </div>
        <div class="status-metric">
            <h5>System</h5>
            <h3>Health</h3>
            <p style="margin:0; font-size:0.6rem; color:#00ff88;">""" + f"{system_status['overall']['health_score']:.0%}" + """</p>
        </div>
        <div class="status-metric">
            <h5>Status</h5>
            <h3>""" + system_status['overall']['status'].title() + """</h3>
            <p style="margin:0; font-size:0.6rem; color:#a0aec0;">""" + datetime.now().strftime("%H:%M:%S") + """</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

def render_coordination_overview(system_status):
    """Render coordination overview panel"""
    
    st.markdown("""
    <div class="coordination-panel">
        <h3>🎯 NORTHSTAR V3 COORDINATION OVERVIEW</h3>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        <div class="phase-indicator">
            <h4>🏗️ FOUNDATION (Phase 1-2)</h4>
            <p>Master Orchestrator coordinating all systems</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Foundation metrics
        foundation_health = (system_status['phase_1']['components'].get('master_orchestrator', 0) + 
                           system_status['phase_2']['components'].get('data_pipeline', 0)) / 2
        st.metric("Foundation Health", f"{foundation_health:.0%}")
    
    with col2:
        st.markdown("""
        <div class="phase-indicator">
            <h4>🧠 INTELLIGENCE (Phase 3)</h4>
            <p>Unified intelligence with Bayesian beliefs</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Intelligence metrics
        intelligence_health = np.mean(list(system_status['phase_3']['components'].values()))
        st.metric("Intelligence Health", f"{intelligence_health:.0%}")
    
    with col3:
        st.markdown("""
        <div class="phase-indicator">
            <h4>🎯 EXECUTION (Phase 4-5)</h4>
            <p>Portfolio construction with absolute risk authority</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Execution metrics
        execution_health = (np.mean(list(system_status['phase_4']['components'].values())) + 
                          np.mean(list(system_status['phase_5']['components'].values()))) / 2
        st.metric("Execution Health", f"{execution_health:.0%}")

def render_portfolio_command_center(portfolio_state):
    """Render portfolio command center"""
    
    st.markdown("""
    <div class="portfolio-panel">
        <h3>🎯 PORTFOLIO COMMAND CENTER</h3>
    </div>
    """, unsafe_allow_html=True)
    
    # Portfolio metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Positions", portfolio_state['positions'])
    
    with col2:
        st.metric("Total Exposure", f"{portfolio_state['exposure']:.1%}")
    
    with col3:
        risk_metrics = portfolio_state.get('risk_metrics', {})
        exposure_cap = risk_metrics.get('exposure_cap', 1.0)
        st.metric("Risk Cap", f"{exposure_cap:.1%}")
    
    with col4:
        emergency_active = risk_metrics.get('emergency_active', False)
        st.metric("Emergency Status", "🚨 ACTIVE" if emergency_active else "✅ NORMAL")
    
    # All positions
    if portfolio_state['top_positions']:
        st.subheader("Portfolio Positions")
        
        # Load complete portfolio data
        try:
            if os.path.exists('data/processed/portfolio_weights.parquet'):
                full_portfolio_df = pd.read_parquet('data/processed/portfolio_weights.parquet')
                if not full_portfolio_df.empty:
                    # Format the portfolio for display
                    display_df = full_portfolio_df.copy()
                    
                    # Ensure we have the required columns
                    required_cols = ['ticker', 'final_weight']
                    if all(col in display_df.columns for col in required_cols):
                        # Add formatted weight column
                        display_df['Weight %'] = display_df['final_weight'].apply(lambda x: f"{x:.2%}")
                        
                        # Select columns for display
                        display_cols = ['ticker', 'Weight %']
                        if 'Company Name' in display_df.columns:
                            display_cols.insert(1, 'Company Name')
                        if 'sector' in display_df.columns:
                            display_cols.append('sector')
                        if 'role' in display_df.columns:
                            display_cols.append('role')
                        
                        # Sort by weight descending
                        display_df = display_df.sort_values('final_weight', ascending=False)
                        
                        # Show summary stats
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Total Positions", len(display_df))
                        with col2:
                            st.metric("Total Weight", f"{display_df['final_weight'].sum():.1%}")
                        with col3:
                            largest_position = display_df['final_weight'].max()
                            st.metric("Largest Position", f"{largest_position:.2%}")
                        
                        # Display the full portfolio table
                        st.dataframe(
                            display_df[display_cols].reset_index(drop=True), 
                            width='stretch',
                            height=400  # Set a reasonable height for scrolling
                        )
                        
                        # Show portfolio composition by sector if available
                        if 'sector' in display_df.columns:
                            st.subheader("Sector Allocation")
                            sector_allocation = display_df.groupby('sector')['final_weight'].sum().sort_values(ascending=False)
                            
                            # Create sector allocation chart
                            fig = px.pie(
                                values=sector_allocation.values,
                                names=sector_allocation.index,
                                title="Portfolio Allocation by Sector"
                            )
                            fig.update_traces(textposition='inside', textinfo='percent+label')
                            st.plotly_chart(fig, width='stretch')
                    else:
                        st.error("Portfolio data missing required columns")
                else:
                    st.warning("Portfolio data is empty")
            else:
                st.warning("Portfolio weights file not found")
        except Exception as e:
            st.error(f"Error loading complete portfolio: {e}")
            # Fallback to top positions if available
            if portfolio_state['top_positions']:
                st.subheader("Top Positions (Fallback)")
                positions_df = pd.DataFrame(portfolio_state['top_positions'])
                positions_df['Weight'] = positions_df['final_weight'].apply(lambda x: f"{x:.2%}")
                st.dataframe(positions_df[['ticker', 'Company Name', 'Weight']], width='stretch')
    
    # Strategy allocation
    if portfolio_state['strategy_allocation']:
        st.subheader("Strategy Allocation")
        
        # Create strategy allocation chart
        strategies = list(portfolio_state['strategy_allocation'].keys())
        allocations = list(portfolio_state['strategy_allocation'].values())
        
        fig = px.pie(
            values=allocations,
            names=strategies,
            title="Capital Allocation Across Strategies"
        )
        fig.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig, width='stretch')

def render_risk_authority_center(portfolio_state):
    """Render risk authority center"""
    
    risk_metrics = portfolio_state.get('risk_metrics', {})
    
    st.markdown("""
    <div class="risk-panel">
        <h3>🛡️ RISK AUTHORITY CENTER</h3>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        emergency_active = risk_metrics.get('emergency_active', False)
        st.metric("Emergency Brake", "🚨 ACTIVE" if emergency_active else "✅ INACTIVE")
    
    with col2:
        risk_level = risk_metrics.get('risk_level', 0.0)
        st.metric("Risk Level", f"{risk_level:.1f}")
    
    with col3:
        authority_level = risk_metrics.get('authority_level', 'SYSTEM')
        st.metric("Authority Level", authority_level)
    
    with col4:
        exposure_cap = risk_metrics.get('exposure_cap', 1.0)
        st.metric("Exposure Cap", f"{exposure_cap:.1%}")
    
    # Risk authority explanation
    if emergency_active:
        st.error("🚨 EMERGENCY BRAKE ACTIVE - Absolute authority over all portfolio decisions")
    else:
        st.success("✅ Normal operations - Portfolio and risk systems coordinated")

def render_intelligence_organism(intelligence):
    """Render intelligence organism panel"""
    
    st.markdown("""
    <div class="intelligence-panel">
        <h3>🧠 INTELLIGENCE ORGANISM</h3>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Market Regime", intelligence['regime'].title())
    
    with col2:
        st.metric("Risk-On Probability", f"{intelligence['risk_on_prob']:.1%}")
    
    with col3:
        st.metric("Allowed Exposure", f"{intelligence['allowed_exposure']:.1%}")
    
    with col4:
        ai_status = "🤖 ACTIVE" if intelligence['intelligence_active'] else "💤 INACTIVE"
        st.metric("AI Intelligence", ai_status)
    
    # Market stability gauge
    stability = intelligence['market_stability']
    stability_color = "green" if stability > 0.7 else "orange" if stability > 0.4 else "red"
    
    fig = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = stability * 100,
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': "Market Stability"},
        gauge = {
            'axis': {'range': [None, 100]},
            'bar': {'color': stability_color},
            'steps': [
                {'range': [0, 40], 'color': "lightgray"},
                {'range': [40, 70], 'color': "gray"},
                {'range': [70, 100], 'color': "lightgreen"}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': 90
            }
        }
    ))
    
    fig.update_layout(height=300)
    st.plotly_chart(fig, width='stretch')

# =========================== MAIN TERMINAL ===========================

def main_unified_terminal_v3():
    """Main Northstar V3 Unified Terminal"""
    
    # Load system data
    system_status = load_unified_system_status()
    portfolio_state = load_portfolio_state()
    intelligence = load_market_intelligence()
    
    # Terminal header
    st.markdown("""
    <div style="text-align: center; margin-bottom: 1rem;">
        <h1 style="color: #00ff88; font-size: 2.5rem; margin: 0;">🧭 NORTHSTAR V3</h1>
        <p style="color: #a0aec0; font-size: 1.1rem; margin: 0.3rem 0;">
            Unified Investment Operating System • Phase 5 Complete
        </p>
        <p style="color: #60a5fa; font-size: 0.9rem; margin: 0;">
            Foundation → Data → Intelligence → Portfolio → Risk → Interface
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Master status bar
    render_master_status_bar(system_status)
    
    # Main terminal layout
    tab1, tab2, tab3, tab4 = st.tabs(["🎯 Command Center", "🧠 Intelligence", "🛡️ Risk Authority", "📊 System Status"])
    
    with tab1:
        render_coordination_overview(system_status)
        render_portfolio_command_center(portfolio_state)
    
    with tab2:
        render_intelligence_organism(intelligence)
        
        # Show recent intelligence activity
        st.subheader("Recent Intelligence Activity")
        if os.path.exists('data/processed/capital_allocations.json'):
            try:
                with open('data/processed/capital_allocations.json', 'r') as f:
                    allocations = json.load(f)
                    
                    # Format the allocations for better display
                    if 'allocations' in allocations and isinstance(allocations['allocations'], dict):
                        st.write("**Strategy Allocations:**")
                        for strategy, allocation in allocations['allocations'].items():
                            if isinstance(allocation, (int, float)):
                                st.write(f"- {strategy}: {allocation:.1%}")
                            else:
                                st.write(f"- {strategy}: {allocation}")
                    
                    # Show timestamp if available
                    if 'timestamp' in allocations:
                        timestamp_str = allocations['timestamp']
                        if isinstance(timestamp_str, str):
                            try:
                                # Parse and format timestamp for better display
                                from datetime import datetime
                                dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                                formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S")
                                st.write(f"**Last Updated:** {formatted_time}")
                            except:
                                st.write(f"**Last Updated:** {timestamp_str}")
                        else:
                            st.write(f"**Last Updated:** {timestamp_str}")
                    
                    # Show formatted data in expander (clean up floating point precision)
                    with st.expander("Formatted Allocation Data"):
                        if 'allocations' in allocations and isinstance(allocations['allocations'], dict):
                            formatted_allocations = {}
                            for strategy, allocation in allocations['allocations'].items():
                                if isinstance(allocation, (int, float)):
                                    formatted_allocations[strategy] = round(allocation, 4)
                                else:
                                    formatted_allocations[strategy] = allocation
                            
                            formatted_data = {
                                'timestamp': allocations.get('timestamp', 'unknown'),
                                'allocations': formatted_allocations
                            }
                            st.json(formatted_data)
                        else:
                            st.json(allocations)
            except Exception as e:
                st.error(f"Error loading capital allocations: {e}")
                st.write("This may be due to missing data files or JSON formatting issues.")
    
    with tab3:
        render_risk_authority_center(portfolio_state)
        
        # Show risk coordination log
        st.subheader("Risk Coordination Log")
        if os.path.exists('data/risk/risk_coordination_log.json'):
            try:
                with open('data/risk/risk_coordination_log.json', 'r') as f:
                    risk_log = json.load(f)
                    
                    # Show summary information safely
                    if isinstance(risk_log, dict):
                        if 'success_rate' in risk_log and isinstance(risk_log['success_rate'], (int, float)):
                            st.metric("Risk Coordination Success Rate", f"{risk_log['success_rate']:.1%}")
                        
                        if 'emergency_actions' in risk_log:
                            st.metric("Emergency Actions", str(risk_log['emergency_actions']))
                        
                        # Show formatted data in expander
                        with st.expander("Risk Log Data"):
                            # Clean up any datetime objects or precision issues
                            formatted_log = {}
                            for key, value in risk_log.items():
                                if isinstance(value, (int, float)):
                                    formatted_log[key] = round(value, 4) if isinstance(value, float) else value
                                elif isinstance(value, str):
                                    formatted_log[key] = value
                                else:
                                    formatted_log[key] = str(value)
                            st.json(formatted_log)
                    else:
                        st.json(risk_log)
            except Exception as e:
                st.error(f"Error loading risk coordination log: {e}")
                st.write("This may be due to missing risk log files or data formatting issues.")
        else:
            st.info("Risk coordination log not available yet. Run the risk coordinator to generate logs.")
    
    with tab4:
        st.subheader("System Component Status")
        
        # Show detailed system status
        for phase, data in system_status.items():
            if phase != 'overall' and isinstance(data, dict):
                st.write(f"**{phase.replace('_', ' ').title()}**: {data.get('status', 'unknown')}")
                components = data.get('components', {})
                if isinstance(components, dict):
                    for component, health in components.items():
                        if isinstance(health, (int, float)):
                            st.write(f"  - {component}: {health:.0%}")
                        else:
                            st.write(f"  - {component}: {health}")
        
        # Show system logs
        st.subheader("Master Orchestrator Log")
        if os.path.exists('data/processed/master_orchestrator_log.json'):
            try:
                with open('data/processed/master_orchestrator_log.json', 'r') as f:
                    orchestrator_log = json.load(f)
                    st.json(orchestrator_log)
            except Exception as e:
                st.error(f"Error loading orchestrator log: {e}")

# =========================== MAIN EXECUTION ===========================

if __name__ == "__main__":
    main_unified_terminal_v3()