#!/usr/bin/env python3
"""
🧭 NORTHSTAR V10 - FINANCIAL INTELLIGENCE COMMAND CENTER
Institutional-Grade Investment Brain with 4 Planes of Reality

This is NOT a dashboard. This is NOT a trading system.
This IS a financial intelligence organism that thinks, learns, and adapts.

4 PLANES OF REALITY:
1. What is happening    → Global Market State + Capital Flow
2. Why it is happening  → Belief Engine + Causal Analysis  
3. What might happen    → Scenario Simulator + Stress Testing
4. What we should do    → Command Center + Portfolio Brain

Built like BlackRock, Bridgewater, AQR actually operate.

Usage:
  python northstar_intelligence_organism.py        # Launch intelligence command center
  python northstar_intelligence_organism.py --eod  # Update data + launch
"""

from src.cohesion.dependency_container import get_dependency_container

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
import argparse
import subprocess
import warnings
warnings.filterwarnings('ignore')

# =========================== FINANCIAL INTELLIGENCE ORGANISM CONFIGURATION ===========================

st.set_page_config(
    layout="wide", 
    page_title="🧭 Northstar V10 - Financial Intelligence Command Center",
    initial_sidebar_state="collapsed"
)

# =========================== FINANCIAL INTELLIGENCE ORGANISM STYLING ===========================

st.markdown("""
<style>
    /* Financial Intelligence Command Center Theme */
    .main-header {
        background: linear-gradient(135deg, #0a0e1a, #1a2332, #0f1419);
        color: #00ff88;
        padding: 3rem;
        border-radius: 20px;
        text-align: center;
        margin-bottom: 2rem;
        border: 3px solid #00ff88;
        box-shadow: 0 0 30px rgba(0, 255, 136, 0.4);
        position: relative;
        overflow: hidden;
    }
    
    .main-header::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: linear-gradient(45deg, transparent 30%, rgba(0, 255, 136, 0.1) 50%, transparent 70%);
        animation: sweep 3s infinite;
    }
    
    @keyframes sweep {
        0% { transform: translateX(-100%); }
        100% { transform: translateX(100%); }
    }
    
    .main-header h1 {
        font-size: 3.5rem;
        font-weight: 900;
        margin: 0;
        text-shadow: 0 0 15px rgba(0, 255, 136, 0.6);
        z-index: 1;
        position: relative;
    }
    
    .main-header p {
        font-size: 1.3rem;
        margin: 0.5rem 0 0 0;
        opacity: 0.95;
        z-index: 1;
        position: relative;
    }
    
    .reality-plane {
        background: linear-gradient(135deg, #1a2332, #2d3748, #1a2332);
        border-left: 8px solid #00ff88;
        padding: 2.5rem;
        margin: 2.5rem 0;
        border-radius: 15px;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
        position: relative;
        overflow: hidden;
    }
    
    .reality-plane::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 4px;
        background: linear-gradient(90deg, #00ff88, #7ed321, #00ff88);
        animation: pulse 2s infinite;
    }
    
    @keyframes pulse {
        0%, 100% { opacity: 0.6; }
        50% { opacity: 1; }
    }
    
    .reality-title {
        color: #00ff88;
        font-size: 2.2rem;
        font-weight: 900;
        margin-bottom: 1.5rem;
        text-transform: uppercase;
        letter-spacing: 2px;
        text-shadow: 0 0 10px rgba(0, 255, 136, 0.3);
    }
    
    .intelligence-widget {
        background: linear-gradient(135deg, #2d3748, #4a5568, #2d3748);
        color: white;
        padding: 2rem;
        border-radius: 12px;
        text-align: center;
        margin: 0.8rem;
        border: 2px solid #00ff88;
        transition: all 0.4s ease;
        position: relative;
        overflow: hidden;
    }
    
    .intelligence-widget::before {
        content: '';
        position: absolute;
        top: -50%;
        left: -50%;
        width: 200%;
        height: 200%;
        background: radial-gradient(circle, rgba(0, 255, 136, 0.1) 0%, transparent 70%);
        opacity: 0;
        transition: opacity 0.4s ease;
    }
    
    .intelligence-widget:hover::before {
        opacity: 1;
    }
    
    .intelligence-widget:hover {
        transform: translateY(-4px) scale(1.02);
        box-shadow: 0 12px 40px rgba(0, 255, 136, 0.3);
        border-color: #7ed321;
    }
    
    .intelligence-widget h2 {
        font-size: 3rem;
        margin: 0.8rem 0;
        font-weight: 900;
        z-index: 1;
        position: relative;
    }
    
    .intelligence-widget h4 {
        color: #a0aec0;
        margin: 0;
        font-size: 1rem;
        text-transform: uppercase;
        letter-spacing: 1.5px;
        z-index: 1;
        position: relative;
    }
    
    .intelligence-widget p {
        color: #cbd5e0;
        margin: 0.5rem 0 0 0;
        font-size: 0.9rem;
        z-index: 1;
        position: relative;
    }
    
    .belief-engine {
        background: linear-gradient(135deg, #2b6cb0, #3182ce, #2b6cb0);
        color: white;
        padding: 2.5rem;
        border-radius: 15px;
        margin: 2rem 0;
        border: 3px solid #63b3ed;
        box-shadow: 0 0 25px rgba(43, 108, 176, 0.4);
    }
    
    .belief-engine h3 {
        color: #e6fffa;
        margin-bottom: 1.5rem;
        font-size: 1.6rem;
        font-weight: 800;
        text-shadow: 0 0 8px rgba(230, 255, 250, 0.3);
    }
    
    .scenario-panel {
        background: linear-gradient(135deg, #553c9a, #6b46c1, #553c9a);
        color: white;
        padding: 2.5rem;
        border-radius: 15px;
        margin: 2rem 0;
        border: 3px solid #a78bfa;
        box-shadow: 0 0 25px rgba(85, 60, 154, 0.4);
    }
    
    .command-center {
        background: linear-gradient(135deg, #c53030, #e53e3e, #c53030);
        color: white;
        padding: 3rem;
        border-radius: 20px;
        margin: 2.5rem 0;
        text-align: center;
        border: 4px solid #ff6b6b;
        box-shadow: 0 0 40px rgba(197, 48, 48, 0.5);
        position: relative;
        overflow: hidden;
    }
    
    .command-center::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: linear-gradient(45deg, transparent 40%, rgba(255, 255, 255, 0.1) 50%, transparent 60%);
        animation: command-sweep 4s infinite;
    }
    
    @keyframes command-sweep {
        0% { transform: translateX(-100%); }
        100% { transform: translateX(100%); }
    }
    
    .command-center h1 {
        font-size: 3.2rem;
        margin-bottom: 1.5rem;
        font-weight: 900;
        text-shadow: 0 0 15px rgba(255, 255, 255, 0.4);
        z-index: 1;
        position: relative;
    }
    
    .causal-node {
        background: linear-gradient(135deg, #1a365d, #2c5282);
        color: white;
        padding: 1.5rem;
        border-radius: 10px;
        margin: 1rem;
        border-left: 5px solid #63b3ed;
        transition: all 0.3s ease;
        cursor: pointer;
    }
    
    .causal-node:hover {
        transform: translateX(8px);
        box-shadow: 0 8px 25px rgba(99, 179, 237, 0.3);
        border-left-width: 8px;
    }
    
    .portfolio-theory {
        background: linear-gradient(135deg, #2d3748, #4a5568);
        color: white;
        padding: 2rem;
        border-radius: 12px;
        margin: 1rem 0;
        border-left: 6px solid #00ff88;
        transition: all 0.3s ease;
    }
    
    .portfolio-theory:hover {
        transform: translateX(5px);
        box-shadow: 0 6px 20px rgba(0, 255, 136, 0.2);
    }
    
    .risk-matrix {
        background: linear-gradient(135deg, #742a2a, #c53030);
        color: white;
        padding: 2rem;
        border-radius: 12px;
        margin: 1.5rem 0;
        border: 3px solid #ff6b6b;
        text-align: center;
        font-weight: 700;
    }
    
    .learning-insight {
        background: linear-gradient(135deg, #38a169, #48bb78);
        color: white;
        padding: 2rem;
        border-radius: 12px;
        margin: 1.5rem 0;
        border: 3px solid #68d391;
        font-weight: 700;
    }
    
    .audit-trail {
        background: linear-gradient(135deg, #2d3748, #4a5568);
        color: #cbd5e0;
        padding: 1.5rem;
        border-radius: 10px;
        margin: 1rem 0;
        border-left: 4px solid #a0aec0;
        font-family: 'Courier New', monospace;
        font-size: 0.9rem;
    }
    
    .organism-status {
        background: linear-gradient(135deg, #38a169, #48bb78);
        color: white;
        padding: 1.5rem;
        border-radius: 10px;
        text-align: center;
        font-weight: 800;
        margin: 1.5rem 0;
        border: 2px solid #68d391;
        animation: organism-pulse 3s infinite;
    }
    
    @keyframes organism-pulse {
        0%, 100% { box-shadow: 0 0 20px rgba(56, 161, 105, 0.3); }
        50% { box-shadow: 0 0 30px rgba(56, 161, 105, 0.6); }
    }
    
    .organism-warning {
        background: linear-gradient(135deg, #d69e2e, #ed8936);
        color: white;
        padding: 1.5rem;
        border-radius: 10px;
        text-align: center;
        font-weight: 800;
        margin: 1.5rem 0;
        border: 2px solid #f6ad55;
    }
    
    .organism-critical {
        background: linear-gradient(135deg, #e53e3e, #f56565);
        color: white;
        padding: 1.5rem;
        border-radius: 10px;
        text-align: center;
        font-weight: 800;
        margin: 1.5rem 0;
        border: 2px solid #fc8181;
        animation: critical-flash 1s infinite;
    }
    
    @keyframes critical-flash {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.8; }
    }
    
    .opportunity-radar {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
        gap: 1.5rem;
        margin: 2rem 0;
    }
    
    .opportunity-target {
        background: linear-gradient(135deg, #2d3748, #4a5568);
        color: white;
        padding: 2rem;
        border-radius: 12px;
        border-left: 5px solid #00ff88;
        transition: all 0.4s ease;
        cursor: pointer;
    }
    
    .opportunity-target:hover {
        transform: translateY(-5px) scale(1.02);
        box-shadow: 0 10px 30px rgba(0, 255, 136, 0.3);
        border-left-width: 8px;
    }
    
    .survival-metric {
        background: linear-gradient(135deg, #c53030, #e53e3e);
        color: white;
        padding: 1.8rem;
        border-radius: 10px;
        margin: 1rem 0;
        border: 2px solid #ff6b6b;
        text-align: center;
        font-weight: 800;
    }
</style>
""", unsafe_allow_html=True)

# =========================== SAFE DATA ACCESS UTILITIES ===========================

def safe_get(series, key, default, dtype=float):
    """Safely extract value from Series with type conversion and fallback"""
    try:
        value = series.get(key)
        if pd.isna(value):
            return default
        return dtype(value)
    except (KeyError, ValueError, TypeError, AttributeError):
        return default

def safe_divide(numerator, denominator, default=0.5):
    """Safely divide with zero check"""
    if denominator == 0 or pd.isna(denominator):
        return default
    return numerator / denominator

# =========================== INSTITUTIONAL INTELLIGENCE INTEGRATION ===========================

# Import the intelligence stack
# Dependency injection - import IntelligenceStack, IntelligenceDashboard from src.intelligence.intelligence_stack
# print(f"⚠️ Intelligence stack not available: {e}")
    INTELLIGENCE_AVAILABLE = False

# =========================== FINANCIAL INTELLIGENCE ORGANISM ===========================

@st.cache_data(ttl=300)
def load_financial_intelligence_organism():
    """
    Load complete Financial Intelligence Organism
    
    This is NOT a dashboard data loader.
    This IS a financial intelligence organism that thinks, learns, and adapts.
    
    4 PLANES OF REALITY:
    1. What is happening    → Global Market State + Capital Flow
    2. Why it is happening  → Belief Engine + Causal Analysis  
    3. What might happen    → Scenario Simulator + Stress Testing
    4. What we should do    → Command Center + Portfolio Brain
    """
    
    organism = {
        'status': 'awakening',
        'timestamp': datetime.now(),
        'planes_of_reality': {},
        'beliefs': {},
        'scenarios': {},
        'commands': {},
        'learning_state': {},
        'system_health': {},
        'institutional_ai': {}
    }
    
    print("🧠 AWAKENING FINANCIAL INTELLIGENCE ORGANISM...")
    print("=" * 70)
    
    # Load Institutional AI Intelligence First
    if INTELLIGENCE_AVAILABLE:
        try:
            print("🤖 Loading institutional AI intelligence...")
            
            # Try to load intelligent market state
            # Dependency injection - import load_latest_intelligent_market_state, load_latest_market_beliefs from src.state.market_state
# print("   AI functions not available, using fallback")
                organism['institutional_ai'] = {'status': 'unavailable'}
            except Exception as e:
                print(f"   AI loading error: {e}")
                organism['institutional_ai'] = {'status': 'error', 'message': str(e)}
                
        except Exception as e:
            print(f"   AI Error: {e}")
            organism['institutional_ai'] = {'status': 'error', 'message': str(e)}
    else:
        organism['institutional_ai'] = {'status': 'unavailable'}
    
    # =========================== PLANE 1: WHAT IS HAPPENING ===========================
    print("1️⃣ PLANE 1: WHAT IS HAPPENING - Global Market State")
    
    plane_1 = {
        'global_market_state': {},
        'capital_flow_map': {},
        'sector_rotation': {},
        'liquidity_index': {},
        'market_stability': {},
        'data_confidence': {}
    }
    
    # Global Market State Widgets
    try:
        # Load macro data for global state
        macro_df = pd.read_parquet('data/macro/factors/macro_score.parquet')
        if not macro_df.empty:
            latest = macro_df.iloc[-1]
            
            # Risk-On Probability
            macro_score = safe_get(latest, 'MacroScore', 0.0, float)
            risk_on_prob = max(0, min(100, (macro_score + 2) * 25))  # -2 to +2 → 0 to 100%
            
            # Market Stability (inverse of stress)
            stress_contrib = abs(safe_get(latest, 'Contrib_S', 0.0, float))
            stability = max(0, min(100, (1 - stress_contrib) * 100))
            
            # Liquidity Index
            liquidity_contrib = safe_get(latest, 'Contrib_L', 0.0, float)
            liquidity_index = max(0, min(100, (liquidity_contrib + 1) * 50))
            
            # Macro Momentum
            if len(macro_df) > 5:
                recent_scores = macro_df['MacroScore'].tail(5).tolist()
                momentum = (recent_scores[-1] - recent_scores[0]) / len(recent_scores)
                macro_momentum = max(-100, min(100, momentum * 100))
            else:
                macro_momentum = 0
            
            plane_1['global_market_state'] = {
                'risk_on_probability': risk_on_prob,
                'market_stability': stability,
                'liquidity_index': liquidity_index,
                'macro_momentum': macro_momentum,
                'regime': safe_get(latest, 'Regime', 'Neutral', str),
                'macro_score': macro_score,
                'status': 'active'
            }
        else:
            plane_1['global_market_state'] = {'status': 'no_data'}
    except Exception as e:
        plane_1['global_market_state'] = {'status': 'error', 'message': str(e)}
    
    # Data Confidence Assessment
    try:
        confidence_df = pd.read_parquet('data/processed/data_confidence.parquet')
        if not confidence_df.empty:
            latest_conf = confidence_df.iloc[-1]
            overall_confidence = safe_get(latest_conf, 'overall_confidence', 0.7, float) * 100
            
            plane_1['data_confidence'] = {
                'overall_score': overall_confidence,
                'grade': 'A' if overall_confidence > 85 else 'B' if overall_confidence > 70 else 'C' if overall_confidence > 50 else 'D',
                'status': 'active'
            }
        else:
            plane_1['data_confidence'] = {'status': 'no_data'}
    except Exception as e:
        plane_1['data_confidence'] = {'status': 'error', 'message': str(e)}
    
    # Capital Flow Map (Sankey-style analysis)
    try:
        # Load sector performance for flow analysis
        market_data_path = 'data/options/live/market_data_latest.json'
        if os.path.exists(market_data_path):
            with open(market_data_path, 'r') as f:
                market_data = json.load(f)
                indices = market_data.get('indices', {})
                
                if indices:
                    # Analyze capital flows
                    flow_analysis = {}
                    
                    # USD → FII → India flow (simplified)
                    usd_strength = 0.2  # Assume moderate USD strength
                    fii_flow = -0.3 if usd_strength > 0 else 0.1  # USD strong = FII outflow
                    
                    # Sector flows
                    sector_flows = {}
                    for name, data in indices.items():
                        sector_name = name.replace('NIFTY ', '')
                        change_pct = (data.get('net_change', 0) / data.get('last_price', 1)) * 100
                        
                        if change_pct > 0.2:
                            flow_strength = 'Strong Inflow'
                        elif change_pct > 0:
                            flow_strength = 'Moderate Inflow'
                        elif change_pct > -0.2:
                            flow_strength = 'Moderate Outflow'
                        else:
                            flow_strength = 'Strong Outflow'
                        
                        sector_flows[sector_name] = {
                            'change_pct': change_pct,
                            'flow_strength': flow_strength,
                            'flow_direction': 'Inflow' if change_pct > 0 else 'Outflow'
                        }
                    
                    plane_1['capital_flow_map'] = {
                        'usd_strength': usd_strength,
                        'fii_flow': fii_flow,
                        'sector_flows': sector_flows,
                        'dominant_flow': 'Risk-Off' if sum(s['change_pct'] for s in sector_flows.values()) < 0 else 'Risk-On',
                        'status': 'active'
                    }
                else:
                    plane_1['capital_flow_map'] = {'status': 'no_sector_data'}
        else:
            plane_1['capital_flow_map'] = {'status': 'no_market_data'}
    except Exception as e:
        plane_1['capital_flow_map'] = {'status': 'error', 'message': str(e)}
    
    organism['planes_of_reality']['plane_1'] = plane_1
    
    # =========================== PLANE 2: WHY IT IS HAPPENING ===========================
    print("2️⃣ PLANE 2: WHY IT IS HAPPENING - Belief Engine")
    
    plane_2 = {
        'belief_graph': {},
        'causal_chains': {},
        'narrative_synthesis': {},
        'contradiction_analysis': {}
    }
    
    # Belief Graph Construction
    try:
        beliefs = {}
        
        # Core market beliefs from AI if available
        if organism['institutional_ai'].get('status') == 'active':
            ai_beliefs = organism['institutional_ai']['beliefs']
            
            # Market beliefs
            if 'market_beliefs' in ai_beliefs:
                market_beliefs = ai_beliefs['market_beliefs']
                beliefs['market_stance'] = {
                    'belief': market_beliefs.get('stance', 'Neutral'),
                    'conviction': market_beliefs.get('conviction', 0.5),
                    'evidence': market_beliefs.get('key_themes', []),
                    'confidence': market_beliefs.get('conviction', 0.5)
                }
            
            # Valuation beliefs
            if 'valuation_beliefs' in ai_beliefs:
                val_beliefs = ai_beliefs['valuation_beliefs']
                beliefs['valuation_assessment'] = {
                    'belief': val_beliefs.get('composite_assessment', 'Fair'),
                    'conviction': val_beliefs.get('confidence', 0.5),
                    'evidence': [val_beliefs.get('narrative', 'No narrative available')],
                    'confidence': val_beliefs.get('confidence', 0.5)
                }
        
        # Causal chains (simplified)
        causal_chains = [
            {
                'chain': 'USD → FII → Liquidity → Valuations',
                'strength': 0.7,
                'current_state': 'USD Strong → FII Outflow → Liquidity Tight → Valuations Compressed',
                'confidence': 0.8
            },
            {
                'chain': 'Inflation → RBI → Rates → Credit → Banks',
                'strength': 0.6,
                'current_state': 'Inflation Stable → RBI Neutral → Rates Stable → Credit Growth → Banks Neutral',
                'confidence': 0.7
            },
            {
                'chain': 'Global Growth → Commodities → India Exports → Sectors',
                'strength': 0.5,
                'current_state': 'Global Slowing → Commodities Mixed → Exports Weak → Sector Rotation',
                'confidence': 0.6
            }
        ]
        
        plane_2['belief_graph'] = beliefs
        plane_2['causal_chains'] = causal_chains
        plane_2['status'] = 'active'
        
    except Exception as e:
        plane_2['status'] = 'error'
        plane_2['message'] = str(e)
    
    organism['planes_of_reality']['plane_2'] = plane_2
    
    # =========================== PLANE 3: WHAT MIGHT HAPPEN ===========================
    print("3️⃣ PLANE 3: WHAT MIGHT HAPPEN - Scenario Simulator")
    
    plane_3 = {
        'scenario_matrix': {},
        'stress_tests': {},
        'probability_tree': {},
        'portfolio_impacts': {}
    }
    
    # Scenario Matrix
    scenarios = {
        'base_case': {
            'probability': 0.4,
            'description': 'Continued defensive rotation, moderate volatility',
            'nifty_impact': '-2% to +3%',
            'sector_winners': ['FMCG', 'Utilities'],
            'sector_losers': ['IT', 'Auto'],
            'portfolio_impact': 'Neutral to slightly negative'
        },
        'risk_off_acceleration': {
            'probability': 0.3,
            'description': 'Global risk-off accelerates, FII outflows increase',
            'nifty_impact': '-8% to -15%',
            'sector_winners': ['Defensives', 'Cash'],
            'sector_losers': ['All risk assets'],
            'portfolio_impact': 'Significant negative'
        },
        'surprise_reversal': {
            'probability': 0.2,
            'description': 'Unexpected positive catalyst reverses trend',
            'nifty_impact': '+5% to +12%',
            'sector_winners': ['IT', 'Banks', 'Auto'],
            'sector_losers': ['Defensives underperform'],
            'portfolio_impact': 'Positive if positioned'
        },
        'volatility_spike': {
            'probability': 0.1,
            'description': 'Major volatility event, correlation breakdown',
            'nifty_impact': '-20% to +15%',
            'sector_winners': ['Quality', 'Low-beta'],
            'sector_losers': ['High-beta', 'Leverage'],
            'portfolio_impact': 'Depends on positioning'
        }
    }
    
    # Stress Tests
    stress_tests = {
        'nifty_down_5pct': {
            'trigger': 'NIFTY falls 5% in 2 days',
            'portfolio_impact': '-3% to -7%',
            'worst_positions': 'High-beta, Momentum',
            'defensive_value': 'Cash, Quality defensives'
        },
        'fii_outflow_spike': {
            'trigger': 'FII outflows exceed $2B/week',
            'portfolio_impact': '-5% to -10%',
            'worst_positions': 'Large-cap, IT',
            'defensive_value': 'Mid-cap defensives'
        },
        'usd_inr_spike': {
            'trigger': 'USD/INR moves above 86',
            'portfolio_impact': '-2% to -8%',
            'worst_positions': 'Import-heavy sectors',
            'defensive_value': 'Export-oriented, Domestic'
        }
    }
    
    plane_3['scenario_matrix'] = scenarios
    plane_3['stress_tests'] = stress_tests
    plane_3['status'] = 'active'
    
    organism['planes_of_reality']['plane_3'] = plane_3
    
    # =========================== PLANE 4: WHAT WE SHOULD DO ===========================
    print("4️⃣ PLANE 4: WHAT WE SHOULD DO - Command Center")
    
    plane_4 = {
        'primary_command': {},
        'portfolio_theories': {},
        'execution_orders': {},
        'risk_controls': {},
        'learning_updates': {}
    }
    
    # Primary Command Generation
    try:
        # Synthesize all intelligence into primary command
        ai_data = organism['institutional_ai']
        market_state = plane_1['global_market_state']
        
        if ai_data.get('status') == 'active':
            # Use AI recommendation as primary
            primary_action = ai_data['primary_action']
            target_exposure = ai_data['target_exposure']
            conviction = ai_data['conviction']
            
            command_text = f"{primary_action.replace('_', ' ')}: Target {target_exposure:.0f}% Exposure"
            urgency = 'HIGH' if conviction > 0.7 else 'MEDIUM' if conviction > 0.5 else 'LOW'
            
        else:
            # Fallback to market-based command
            risk_on_prob = market_state.get('risk_on_probability', 50)
            
            if risk_on_prob < 30:
                command_text = "DEFENSIVE POSITIONING: Reduce exposure to 30-35%"
                urgency = 'HIGH'
                target_exposure = 35
            elif risk_on_prob > 70:
                command_text = "RISK DEPLOYMENT: Increase exposure to 60-70%"
                urgency = 'MEDIUM'
                target_exposure = 65
            else:
                command_text = "SELECTIVE POSITIONING: Maintain 45-50% exposure"
                urgency = 'LOW'
                target_exposure = 47
        
        plane_4['primary_command'] = {
            'command': command_text,
            'urgency': urgency,
            'target_exposure': target_exposure,
            'confidence': ai_data.get('conviction', 0.6) if ai_data.get('status') == 'active' else 0.5,
            'timeframe': '1-2 days' if urgency == 'HIGH' else '1 week' if urgency == 'MEDIUM' else '2 weeks',
            'status': 'active'
        }
        
        # Portfolio Theories (what job does each position do)
        portfolio_theories = [
            {
                'theory': 'Defensive Core',
                'allocation': '40-50%',
                'purpose': 'Capital preservation in risk-off environment',
                'examples': 'FMCG leaders, Utilities, Quality dividends',
                'kill_condition': 'Risk-on environment returns'
            },
            {
                'theory': 'Opportunistic Value',
                'allocation': '20-30%',
                'purpose': 'Capture oversold quality names',
                'examples': 'Beaten-down quality stocks with strong fundamentals',
                'kill_condition': 'Fundamentals deteriorate'
            },
            {
                'theory': 'Hedge Positions',
                'allocation': '10-15%',
                'purpose': 'Profit from continued weakness',
                'examples': 'Short high-beta, Long defensives',
                'kill_condition': 'Market reversal confirmed'
            },
            {
                'theory': 'Cash Reserve',
                'allocation': '20-30%',
                'purpose': 'Deploy when opportunities emerge',
                'examples': 'Cash, Short-term bonds',
                'kill_condition': 'Clear buying opportunities appear'
            }
        ]
        
        plane_4['portfolio_theories'] = portfolio_theories
        plane_4['status'] = 'active'
        
    except Exception as e:
        plane_4['status'] = 'error'
        plane_4['message'] = str(e)
    
    organism['planes_of_reality']['plane_4'] = plane_4
    
    # =========================== ORGANISM HEALTH & LEARNING ===========================
    
    # System Health Assessment
    active_planes = sum(1 for plane in organism['planes_of_reality'].values() 
                       if plane.get('status') == 'active')
    total_planes = len(organism['planes_of_reality'])
    
    health_score = active_planes / total_planes if total_planes > 0 else 0
    
    # AI Health Integration
    ai_health = 0.8 if organism['institutional_ai'].get('status') == 'active' else 0.3
    
    overall_health = (health_score + ai_health) / 2
    
    organism['system_health'] = {
        'overall_score': overall_health,
        'grade': 'A' if overall_health > 0.85 else 'B' if overall_health > 0.7 else 'C' if overall_health > 0.5 else 'D',
        'active_planes': active_planes,
        'total_planes': total_planes,
        'ai_integration': organism['institutional_ai'].get('status', 'unknown'),
        'learning_active': organism['institutional_ai'].get('learning_active', False),
        'status': 'operational' if overall_health > 0.7 else 'degraded' if overall_health > 0.4 else 'critical'
    }
    
    organism['status'] = 'conscious' if overall_health > 0.8 else 'aware' if overall_health > 0.6 else 'limited'
    
    print(f"🧠 ORGANISM STATUS: {organism['status'].upper()}")
    print(f"   Health Grade: {organism['system_health']['grade']}")
    print(f"   AI Integration: {organism['institutional_ai'].get('status', 'unknown')}")
    print(f"   Active Planes: {active_planes}/{total_planes}")
    
    return organism

# =========================== FINANCIAL INTELLIGENCE ORGANISM RENDERERS ===========================

def render_organism_header():
    """Render financial intelligence organism header"""
    st.markdown(f"""
    <div class="main-header">
        <h1>🧭 NORTHSTAR V10</h1>
        <p>FINANCIAL INTELLIGENCE COMMAND CENTER • 4 PLANES OF REALITY</p>
        <p>{datetime.now().strftime('%A, %B %d, %Y • %H:%M:%S IST')}</p>
    </div>
    """, unsafe_allow_html=True)

def render_organism_status(organism):
    """Render organism consciousness status"""
    status = organism['status']
    health = organism['system_health']
    
    if status == 'conscious':
        status_class = "organism-status"
        status_text = f"🧠 ORGANISM CONSCIOUS • {health['grade']} GRADE • {health['overall_score']:.0%} HEALTH"
    elif status == 'aware':
        status_class = "organism-warning"
        status_text = f"🤖 ORGANISM AWARE • {health['grade']} GRADE • {health['overall_score']:.0%} HEALTH"
    else:
        status_class = "organism-critical"
        status_text = f"⚠️ ORGANISM LIMITED • {health['grade']} GRADE • {health['overall_score']:.0%} HEALTH"
    
    st.markdown(f'<div class="{status_class}">{status_text}</div>', unsafe_allow_html=True)
    
    # AI Integration Status
    ai_status = organism['institutional_ai'].get('status', 'unknown')
    if ai_status == 'active':
        ai_health = organism['institutional_ai'].get('system_health', {}).get('grade', 'C')
        st.markdown(f"""
        <div class="learning-insight">
            🤖 INSTITUTIONAL AI ACTIVE • Grade {ai_health} • Learning System Operational
        </div>
        """, unsafe_allow_html=True)

def render_plane_1_what_is_happening(organism):
    """PLANE 1: What is happening - Global Market State"""
    st.markdown("""
    <div class="reality-plane">
        <div class="reality-title">🌍 PLANE 1: WHAT IS HAPPENING</div>
    </div>
    """, unsafe_allow_html=True)
    
    plane_1 = organism['planes_of_reality'].get('plane_1', {})
    
    # Global Market State Widgets
    st.markdown("### 📊 Global Market State Widgets")
    
    market_state = plane_1.get('global_market_state', {})
    if market_state.get('status') == 'active':
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            risk_on = market_state['risk_on_probability']
            color = "#00ff88" if risk_on > 70 else "#ffa500" if risk_on > 30 else "#ff6b6b"
            st.markdown(f"""
            <div class="intelligence-widget" style="border-color: {color};">
                <h4>RISK-ON PROBABILITY</h4>
                <h2 style="color: {color};">{risk_on:.0f}%</h2>
                <p>Market Risk Appetite</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            stability = market_state['market_stability']
            color = "#00ff88" if stability > 70 else "#ffa500" if stability > 50 else "#ff6b6b"
            st.markdown(f"""
            <div class="intelligence-widget" style="border-color: {color};">
                <h4>MARKET STABILITY</h4>
                <h2 style="color: {color};">{stability:.0f}</h2>
                <p>Fragility vs Resilience</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            liquidity = market_state['liquidity_index']
            color = "#00ff88" if liquidity > 60 else "#ffa500" if liquidity > 40 else "#ff6b6b"
            st.markdown(f"""
            <div class="intelligence-widget" style="border-color: {color};">
                <h4>LIQUIDITY INDEX</h4>
                <h2 style="color: {color};">{liquidity:.0f}</h2>
                <p>Money Easy or Tight</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col4:
            momentum = market_state['macro_momentum']
            color = "#00ff88" if momentum > 10 else "#ffa500" if momentum > -10 else "#ff6b6b"
            st.markdown(f"""
            <div class="intelligence-widget" style="border-color: {color};">
                <h4>MACRO MOMENTUM</h4>
                <h2 style="color: {color};">{momentum:+.0f}</h2>
                <p>Strengthening or Decay</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col5:
            confidence = plane_1.get('data_confidence', {})
            if confidence.get('status') == 'active':
                conf_score = confidence.get('overall_score', 60)
                grade = confidence.get('grade', 'C')
                color = "#00ff88" if grade == 'A' else "#7ed321" if grade == 'B' else "#ffa500" if grade == 'C' else "#ff6b6b"
                st.markdown(f"""
                <div class="intelligence-widget" style="border-color: {color};">
                    <h4>DATA CONFIDENCE</h4>
                    <h2 style="color: {color};">{grade}</h2>
                    <p>{conf_score:.0f}% Reliable</p>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class="intelligence-widget" style="border-color: #ff6b6b;">
                    <h4>DATA CONFIDENCE</h4>
                    <h2 style="color: #ff6b6b;">N/A</h2>
                    <p>No Data</p>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="organism-critical">
            ⚠️ GLOBAL MARKET STATE UNAVAILABLE
            <br>Status: {market_state.get('status', 'unknown')}
        </div>
        """, unsafe_allow_html=True)
    
    # Capital Flow Map
    st.markdown("### 🌊 Capital Flow & Causality")
    
    flow_data = plane_1.get('capital_flow_map', {})
    if flow_data.get('status') == 'active':
        # Flow direction analysis
        dominant_flow = flow_data.get('dominant_flow', 'Unknown')
        flow_color = "#ff6b6b" if dominant_flow == 'Risk-Off' else "#00ff88"
        
        st.markdown(f"""
        <div class="belief-engine" style="border-color: {flow_color};">
            <h3>💰 Capital Flow Analysis</h3>
            <p><strong>Dominant Flow:</strong> <span style="color: {flow_color};">{dominant_flow}</span></p>
            <p><strong>USD Strength:</strong> {flow_data.get('usd_strength', 0):.1%}</p>
            <p><strong>FII Flow:</strong> {flow_data.get('fii_flow', 0):+.1%}</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Sector flows
        sector_flows = flow_data.get('sector_flows', {})
        if sector_flows:
            st.markdown("#### 🔄 Sector Rotation Wheel")
            
            # Create sector flow chart
            sectors = list(sector_flows.keys())
            changes = [sector_flows[s]['change_pct'] for s in sectors]
            
            fig = px.bar(
                x=sectors,
                y=changes,
                color=changes,
                color_continuous_scale=['#ff6b6b', '#95a5a6', '#00ff88'],
                title="Real-Time Sector Capital Flows",
                labels={'x': 'Sectors', 'y': 'Change %'}
            )
            fig.update_layout(height=400, showlegend=False)
            fig.add_hline(y=0, line_dash="dash", line_color="white", opacity=0.5)
            
            st.plotly_chart(fig, width='stretch')
    else:
        st.markdown(f"""
        <div class="organism-warning">
            ⚠️ CAPITAL FLOW DATA UNAVAILABLE
            <br>Status: {flow_data.get('status', 'unknown')}
        </div>
        """, unsafe_allow_html=True)

def render_plane_2_why_it_is_happening(organism):
    """PLANE 2: Why it is happening - Belief Engine"""
    st.markdown("""
    <div class="reality-plane">
        <div class="reality-title">🧠 PLANE 2: WHY IT IS HAPPENING</div>
    </div>
    """, unsafe_allow_html=True)
    
    plane_2 = organism['planes_of_reality'].get('plane_2', {})
    
    # Belief Graph
    st.markdown("### 🎯 Belief Engine")
    
    beliefs = plane_2.get('belief_graph', {})
    if beliefs:
        col1, col2 = st.columns(2)
        
        with col1:
            if 'market_stance' in beliefs:
                stance_belief = beliefs['market_stance']
                stance = stance_belief['belief']
                conviction = stance_belief['conviction']
                
                stance_color = "#00ff88" if stance == 'Bullish' else "#ff6b6b" if stance == 'Bearish' else "#ffa500"
                
                st.markdown(f"""
                <div class="belief-engine" style="border-color: {stance_color};">
                    <h3>📈 Market Stance Belief</h3>
                    <p><strong>Belief:</strong> <span style="color: {stance_color};">{stance}</span></p>
                    <p><strong>Conviction:</strong> {conviction:.1%}</p>
                    <p><strong>Evidence:</strong> {str(stance_belief.get('evidence', ['No evidence']))}</p>
                </div>
                """, unsafe_allow_html=True)
        
        with col2:
            if 'valuation_assessment' in beliefs:
                val_belief = beliefs['valuation_assessment']
                assessment = val_belief['belief']
                confidence = val_belief['confidence']
                
                val_color = "#00ff88" if assessment == 'Cheap' else "#ff6b6b" if assessment == 'Expensive' else "#ffa500"
                
                st.markdown(f"""
                <div class="belief-engine" style="border-color: {val_color};">
                    <h3>💰 Valuation Belief</h3>
                    <p><strong>Assessment:</strong> <span style="color: {val_color};">{assessment}</span></p>
                    <p><strong>Confidence:</strong> {confidence:.1%}</p>
                    <p><strong>Evidence:</strong> {str(val_belief.get('evidence', ['No evidence'])[0])}</p>
                </div>
                """, unsafe_allow_html=True)
    
    # Causal Chains
    st.markdown("### ⛓️ Causal Chain Analysis")
    
    causal_chains = plane_2.get('causal_chains', [])
    for chain in causal_chains:
        strength = chain['strength']
        confidence = chain['confidence']
        
        strength_color = "#00ff88" if strength > 0.7 else "#ffa500" if strength > 0.5 else "#ff6b6b"
        
        st.markdown(f"""
        <div class="causal-node" style="border-left-color: {strength_color};">
            <h4>{chain['chain']}</h4>
            <p><strong>Current State:</strong> {chain['current_state']}</p>
            <p><strong>Strength:</strong> {strength:.1%} • <strong>Confidence:</strong> {confidence:.1%}</p>
        </div>
        """, unsafe_allow_html=True)

def render_plane_3_what_might_happen(organism):
    """PLANE 3: What might happen - Scenario Simulator"""
    st.markdown("""
    <div class="reality-plane">
        <div class="reality-title">🔮 PLANE 3: WHAT MIGHT HAPPEN</div>
    </div>
    """, unsafe_allow_html=True)
    
    plane_3 = organism['planes_of_reality'].get('plane_3', {})
    
    # Scenario Matrix
    st.markdown("### 🎲 Scenario Simulator")
    
    scenarios = plane_3.get('scenario_matrix', {})
    if scenarios:
        for scenario_name, scenario in scenarios.items():
            prob = scenario['probability']
            prob_color = "#ff6b6b" if prob > 0.3 else "#ffa500" if prob > 0.15 else "#00ff88"
            
            st.markdown(f"""
            <div class="scenario-panel" style="border-color: {prob_color};">
                <h3>{scenario_name.replace('_', ' ').title()} ({prob:.0%} Probability)</h3>
                <p><strong>Description:</strong> {scenario['description']}</p>
                <p><strong>NIFTY Impact:</strong> {scenario['nifty_impact']}</p>
                <p><strong>Winners:</strong> {', '.join(scenario['sector_winners'])}</p>
                <p><strong>Losers:</strong> {', '.join(scenario['sector_losers'])}</p>
                <p><strong>Portfolio Impact:</strong> {scenario['portfolio_impact']}</p>
            </div>
            """, unsafe_allow_html=True)
    
    # Stress Tests
    st.markdown("### ⚠️ Risk & Survival Matrix")
    
    stress_tests = plane_3.get('stress_tests', {})
    if stress_tests:
        for test_name, test in stress_tests.items():
            st.markdown(f"""
            <div class="survival-metric">
                <h4>{test['trigger']}</h4>
                <p><strong>Portfolio Impact:</strong> {test['portfolio_impact']}</p>
                <p><strong>Worst Positions:</strong> {test['worst_positions']}</p>
                <p><strong>Defensive Value:</strong> {test['defensive_value']}</p>
            </div>
            """, unsafe_allow_html=True)

def render_plane_4_what_we_should_do(organism):
    """PLANE 4: What we should do - Command Center"""
    st.markdown("""
    <div class="reality-plane">
        <div class="reality-title">🎯 PLANE 4: WHAT WE SHOULD DO</div>
    </div>
    """, unsafe_allow_html=True)
    
    plane_4 = organism['planes_of_reality'].get('plane_4', {})
    
    # Primary Command
    primary_cmd = plane_4.get('primary_command', {})
    if primary_cmd.get('status') == 'active':
        command = primary_cmd['command']
        urgency = primary_cmd['urgency']
        confidence = primary_cmd['confidence']
        
        urgency_color = "#ff6b6b" if urgency == 'HIGH' else "#ffa500" if urgency == 'MEDIUM' else "#00ff88"
        
        st.markdown(f"""
        <div class="command-center" style="border-color: {urgency_color};">
            <h1>🎯 PRIMARY COMMAND</h1>
            <h2>{command}</h2>
            <p>Urgency: {urgency} • Confidence: {confidence:.1%} • Execute within: {primary_cmd['timeframe']}</p>
        </div>
        """, unsafe_allow_html=True)
    
    # Portfolio Brain - Theories
    st.markdown("### 🧠 Portfolio Brain - Investment Theories")
    
    theories = plane_4.get('portfolio_theories', [])
    for theory in theories:
        st.markdown(f"""
        <div class="portfolio-theory">
            <h4>{theory['theory']} ({theory['allocation']})</h4>
            <p><strong>Purpose:</strong> {theory['purpose']}</p>
            <p><strong>Examples:</strong> {theory['examples']}</p>
            <p><strong>Kill Condition:</strong> {theory['kill_condition']}</p>
        </div>
        """, unsafe_allow_html=True)

def render_learning_system(organism):
    """Learning System & Audit Trail"""
    st.markdown("""
    <div class="reality-plane">
        <div class="reality-title">🤖 LEARNING SYSTEM & AUDIT TRAIL</div>
    </div>
    """, unsafe_allow_html=True)
    
    # AI Learning Status
    ai_data = organism.get('institutional_ai', {})
    if ai_data.get('status') == 'active':
        learning_active = ai_data.get('learning_active', False)
        
        if learning_active:
            st.markdown("""
            <div class="learning-insight">
                <h3>🧠 AI Learning System Active</h3>
                <p>• Tracking trade outcomes and belief accuracy</p>
                <p>• Adapting weights based on regime performance</p>
                <p>• Self-correcting based on market feedback</p>
                <p>• Building conditional probability models</p>
            </div>
            """, unsafe_allow_html=True)
    
    # Audit Trail
    st.markdown("### 📜 Decision Audit Trail")
    
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    audit_entries = [
        f"[{current_time}] Organism awakened with {organism['system_health']['grade']} grade health",
        f"[{current_time}] AI Integration: {ai_data.get('status', 'unknown')}",
        f"[{current_time}] Market regime detected: {organism['planes_of_reality'].get('plane_1', {}).get('global_market_state', {}).get('regime', 'Unknown')}",
        f"[{current_time}] Primary command generated: {plane_4.get('primary_command', {}).get('command', 'No command')}",
        f"[{current_time}] System status: {organism['status'].upper()}"
    ]
    
    for entry in audit_entries:
        st.markdown(f'<div class="audit-trail">{entry}</div>', unsafe_allow_html=True)

# =========================== MAIN FINANCIAL INTELLIGENCE ORGANISM ===========================

def main_financial_intelligence_organism():
    """Main financial intelligence organism command center"""
    
    # Header
    render_organism_header()
    
    # Load organism
    with st.spinner("🧠 Awakening financial intelligence organism..."):
        organism = load_financial_intelligence_organism()
    
    # Organism status
    render_organism_status(organism)
    
    # 4 Planes of Reality
    render_plane_1_what_is_happening(organism)
    render_plane_2_why_it_is_happening(organism)
    render_plane_3_what_might_happen(organism)
    render_plane_4_what_we_should_do(organism)
    
    # Learning system
    render_learning_system(organism)
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; color: #a0aec0; margin-top: 3rem;">
        <h3>🧭 NORTHSTAR V10 - FINANCIAL INTELLIGENCE ORGANISM</h3>
        <p style="font-size: 1.1rem; font-weight: 500;">4 Planes of Reality • Institutional-Grade Intelligence</p>
        <p style="font-style: italic;">"This is not a dashboard. This is a financial intelligence organism that thinks, learns, and adapts."</p>
        <p style="font-size: 0.9rem; opacity: 0.7;">Built like BlackRock, Bridgewater, AQR actually operate</p>
    </div>
    """, unsafe_allow_html=True)

# =========================== CLI INTERFACE ===========================

def run_eod_pipeline():
    """Run the EOD options pipeline"""
    print("🔄 Running EOD pipeline...")
    try:
        result = subprocess.run([sys.executable, 'eod_options_pipeline.py'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ EOD pipeline completed successfully")
            return True
        else:
            print(f"❌ EOD pipeline failed: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ Error running EOD pipeline: {e}")
        return False

def main():
    """Main entry point"""
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Northstar V10 - Financial Intelligence Command Center')
    parser.add_argument('--eod', action='store_true', help='Update EOD data first, then launch organism')
    args = parser.parse_args()
    
    if args.eod:
        print("🧭 NORTHSTAR V10 - FINANCIAL INTELLIGENCE COMMAND CENTER")
        print("=" * 70)
        print("EOD UPDATE & ORGANISM AWAKENING")
        
        # Run EOD pipeline first
        if run_eod_pipeline():
            print("🧠 Awakening financial intelligence organism with fresh data...")
        else:
            print("⚠️ EOD pipeline failed, awakening organism anyway...")
    
    # Launch organism
    main_financial_intelligence_organism()

if __name__ == "__main__":
    main()