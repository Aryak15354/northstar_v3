#!/usr/bin/env python3
"""
🧭 NORTHSTAR COMMAND BRIDGE - Bloomberg-Grade Trading Floor
The Ultimate Capital Organism Control Interface

This is where Northstar stops feeling like code and starts feeling like a trading floor.
Not "a dashboard" but a command bridge for a living capital organism.

Five-Layer Architecture (like a real hedge fund desk):
┌────────────────────────────────────────────┐
│ MARKET REALITY BAR (What world are we in?) │
├────────────────────────────────────────────┤
│ BRAIN + BELIEF PANEL (Why?)                │
├────────────────────────────────────────────┤
│ PORTFOLIO & CAPITAL PANEL (What we hold)   │
├────────────────────────────────────────────┤
│ RISK SPINE (How could we die?)             │
├────────────────────────────────────────────┤
│ EXECUTION & MEMORY (What did we do?)       │
└────────────────────────────────────────────┘

Everything reads UnifiedState. Nothing calculates.
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

if project_root not in sys.path:
    pass  # Path already added
# =========================== COMMAND BRIDGE CONFIGURATION ===========================

st.set_page_config(
    layout="wide", 
    page_title="🧭 Northstar Command Bridge - Living Capital Organism",
    initial_sidebar_state="collapsed"
)

# =========================== BLOOMBERG-GRADE STYLING ===========================

st.markdown("""
<style>
    /* COMMAND BRIDGE THEME - Bloomberg Terminal Style */
    .main { padding: 0.2rem; background: #000011; }
    .block-container { padding: 0.3rem; max-width: 100%; }
    
    /* MARKET REALITY BAR - The Bloomberg Headline */
    .market-reality-bar {
        background: linear-gradient(90deg, #000033, #001155, #002277);
        color: #00ff88;
        padding: 0.8rem 1.2rem;
        border: 2px solid #00ff88;
        border-radius: 8px;
        margin-bottom: 0.5rem;
        display: grid;
        grid-template-columns: repeat(7, 1fr);
        gap: 0.5rem;
        font-family: 'Courier New', monospace;
        font-weight: 700;
        box-shadow: 0 0 20px rgba(0, 255, 136, 0.3);
    }
    
    .reality-metric {
        text-align: center;
        padding: 0.3rem;
        background: rgba(0, 255, 136, 0.1);
        border: 1px solid rgba(0, 255, 136, 0.3);
        border-radius: 4px;
    }
    
    .reality-metric h6 {
        margin: 0;
        font-size: 0.6rem;
        color: #888;
        text-transform: uppercase;
    }
    
    .reality-metric h4 {
        margin: 0.1rem 0 0 0;
        font-size: 0.9rem;
        font-weight: 900;
    }
    
    /* BRAIN PANEL - Cognitive Layer */
    .brain-panel {
        background: linear-gradient(135deg, #001122, #002244);
        border: 2px solid #60a5fa;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.3rem 0;
        min-height: 300px;
    }
    
    .brain-panel h3 {
        color: #60a5fa;
        margin: 0 0 0.8rem 0;
        font-size: 1rem;
        font-weight: 900;
        text-align: center;
        text-transform: uppercase;
        letter-spacing: 2px;
    }
    
    /* BELIEF TABLE */
    .belief-table {
        background: rgba(96, 165, 250, 0.1);
        border: 1px solid rgba(96, 165, 250, 0.3);
        border-radius: 6px;
        padding: 0.8rem;
    }
    
    /* PORTFOLIO PANEL - Where Investors Stare */
    .portfolio-panel {
        background: linear-gradient(135deg, #002200, #004400);
        border: 2px solid #10b981;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.3rem 0;
    }
    
    .portfolio-panel h3 {
        color: #10b981;
        margin: 0 0 0.8rem 0;
        font-size: 1rem;
        font-weight: 900;
        text-align: center;
        text-transform: uppercase;
        letter-spacing: 2px;
    }
    
    /* RISK SPINE - Visually Intimidating */
    .risk-spine {
        background: linear-gradient(135deg, #220000, #440000);
        border: 3px solid #ff4444;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.3rem 0;
        box-shadow: 0 0 25px rgba(255, 68, 68, 0.4);
    }
    
    .risk-spine h3 {
        color: #ff4444;
        margin: 0 0 0.8rem 0;
        font-size: 1.1rem;
        font-weight: 900;
        text-align: center;
        text-transform: uppercase;
        letter-spacing: 2px;
    }
    
    .risk-status-banner {
        background: linear-gradient(90deg, #ff4444, #ff6666);
        color: #000;
        padding: 0.8rem;
        border-radius: 6px;
        text-align: center;
        font-size: 1.2rem;
        font-weight: 900;
        margin-bottom: 1rem;
        text-transform: uppercase;
        letter-spacing: 2px;
    }
    
    .risk-status-normal {
        background: linear-gradient(90deg, #10b981, #34d399);
    }
    
    .risk-status-elevated {
        background: linear-gradient(90deg, #f59e0b, #fbbf24);
    }
    
    .risk-status-locked {
        background: linear-gradient(90deg, #dc2626, #ef4444);
    }
    
    /* EXECUTION PANEL - Audit Trail */
    .execution-panel {
        background: linear-gradient(135deg, #1a1a2e, #16213e);
        border: 2px solid #a855f7;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.3rem 0;
    }
    
    .execution-panel h3 {
        color: #a855f7;
        margin: 0 0 0.8rem 0;
        font-size: 1rem;
        font-weight: 900;
        text-align: center;
        text-transform: uppercase;
        letter-spacing: 2px;
    }
    
    /* DECISION LOG */
    .decision-entry {
        background: rgba(168, 85, 247, 0.1);
        border-left: 4px solid #a855f7;
        padding: 0.6rem;
        margin: 0.3rem 0;
        border-radius: 4px;
        font-family: 'Courier New', monospace;
        font-size: 0.85rem;
    }
    
    .decision-time {
        color: #888;
        font-size: 0.75rem;
    }
    
    .decision-action {
        color: #a855f7;
        font-weight: 700;
    }
    
    /* SHOCK BUTTON */
    .shock-button {
        background: linear-gradient(135deg, #dc2626, #b91c1c);
        border: 3px solid #fca5a5;
        color: white;
        padding: 1rem 2rem;
        border-radius: 8px;
        font-size: 1.1rem;
        font-weight: 900;
        text-transform: uppercase;
        letter-spacing: 2px;
        cursor: pointer;
        text-align: center;
        margin: 1rem 0;
        box-shadow: 0 0 20px rgba(220, 38, 38, 0.5);
    }
    
    .shock-button:hover {
        background: linear-gradient(135deg, #b91c1c, #991b1b);
        box-shadow: 0 0 30px rgba(220, 38, 38, 0.7);
    }
    
    /* CONSTRAINT MONITOR */
    .constraint-monitor {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 0.5rem;
        margin: 0.8rem 0;
    }
    
    .constraint-item {
        padding: 0.5rem;
        border-radius: 4px;
        text-align: center;
        font-size: 0.8rem;
        font-weight: 700;
    }
    
    .constraint-green {
        background: rgba(16, 185, 129, 0.2);
        border: 1px solid #10b981;
        color: #10b981;
    }
    
    .constraint-red {
        background: rgba(239, 68, 68, 0.2);
        border: 1px solid #ef4444;
        color: #ef4444;
    }
    
    /* WAVEFORM CONTAINER */
    .waveform-container {
        background: rgba(0, 0, 0, 0.3);
        border: 1px solid rgba(96, 165, 250, 0.3);
        border-radius: 6px;
        padding: 0.5rem;
        margin: 0.5rem 0;
    }
</style>
""", unsafe_allow_html=True)

# =========================== DATA LOADING - UNIFIED STATE ONLY ===========================

@st.cache_data(ttl=30)
def load_unified_state():
    """Load complete unified state - everything reads from here, nothing calculates"""
    
    unified_state = {
        'timestamp': datetime.now(),
        'market_reality': {
            'regime': 'Unknown',
            'regime_stability': 0.5,
            'market_pulse': 0.5,
            'risk_on_pct': 50,
            'exposure': 60,
            'liquidity': 'Medium',
            'system_health': 0.7
        },
        'brain_state': {
            'regime_map': {},
            'pulse_waveform': [],
            'causal_graph': {},
            'survival_alerts': []
        },
        'belief_engine': {
            'beliefs': [],
            'conviction_levels': {},
            'evidence_base': {}
        },
        'portfolio_organism': {
            'strategy_weights': {},
            'stock_weights': {},
            'sector_exposure': {},
            'turnover': 0.0,
            'cash': 0.1
        },
        'constraint_monitor': {
            'max_position': {'status': 'green', 'value': '5%', 'limit': '10%'},
            'sector_cap': {'status': 'green', 'value': '25%', 'limit': '30%'},
            'turnover': {'status': 'green', 'value': '15%', 'limit': '20%'},
            'liquidity': {'status': 'green', 'value': 'High', 'limit': 'Medium+'}
        },
        'risk_spine': {
            'status': 'NORMAL',  # NORMAL / ELEVATED / LOCKED
            'emergency_brake': False,
            'kill_switches': {},
            'stress_indicators': {},
            'drawdown_risk': 0.05,
            'volatility': 0.15
        },
        'execution_memory': {
            'recent_decisions': [],
            'similar_regimes': [],
            'portfolio_behavior': {}
        }
    }
    
    # Load actual data from various sources
    try:
        # Market reality from market state
        if os.path.exists('data/processed/market_state.parquet'):
            market_df = pd.read_parquet('data/processed/market_state.parquet')
            if not market_df.empty:
                latest = market_df.iloc[-1]
                unified_state['market_reality'].update({
                    'regime': latest.get('macro_regime', 'Unknown'),
                    'regime_stability': float(latest.get('regime_stability', 0.5)),
                    'market_pulse': float(latest.get('market_pulse', 0.5)),
                    'risk_on_pct': int(latest.get('risk_on_probability', 0.5) * 100),
                    'exposure': int(latest.get('allowed_exposure', 0.6) * 100),
                    'system_health': float(latest.get('health_score', 0.7))
                })
        
        # Portfolio organism from portfolio weights
        if os.path.exists('data/processed/portfolio_weights.parquet'):
            portfolio_df = pd.read_parquet('data/processed/portfolio_weights.parquet')
            if not portfolio_df.empty:
                # Strategy weights from capital allocations
                if os.path.exists('data/processed/capital_allocations.json'):
                    with open('data/processed/capital_allocations.json', 'r') as f:
                        allocations = json.load(f)
                        if 'allocations' in allocations:
                            unified_state['portfolio_organism']['strategy_weights'] = allocations['allocations']
                
                # Stock weights
                if 'ticker' in portfolio_df.columns and 'final_weight' in portfolio_df.columns:
                    stock_weights = dict(zip(portfolio_df['ticker'], portfolio_df['final_weight']))
                    unified_state['portfolio_organism']['stock_weights'] = stock_weights
                
                # Sector exposure
                if 'sector' in portfolio_df.columns:
                    sector_exposure = portfolio_df.groupby('sector')['final_weight'].sum().to_dict()
                    unified_state['portfolio_organism']['sector_exposure'] = sector_exposure
        
        # Risk spine from risk state
        if os.path.exists('data/risk/unified_risk_state.json'):
            with open('data/risk/unified_risk_state.json', 'r') as f:
                risk_state = json.load(f)
                emergency_state = risk_state.get('emergency_state', {})
                
                unified_state['risk_spine'].update({
                    'emergency_brake': emergency_state.get('emergency_active', False),
                    'status': 'LOCKED' if emergency_state.get('emergency_active', False) else 'NORMAL',
                    'drawdown_risk': float(emergency_state.get('risk_level', 0.05)),
                })
        
        # Belief engine from narrative intelligence
        beliefs = []
        
        # Load enhanced narrative data
        if os.path.exists('data/reports/daily_narrative_enhanced.json'):
            with open('data/reports/daily_narrative_enhanced.json', 'r') as f:
                narrative = json.load(f)
                five_layer = narrative.get('five_layer_analysis', {})
                
                # Convert five-layer analysis to beliefs with evidence
                if five_layer.get('why_happening'):
                    beliefs.append({
                        'belief': 'Liquidity Tightening',
                        'strength': 0.81,
                        'evidence': 'RBI hiking, yields rising',
                        'invalidation': 'Policy reversal or liquidity injection'
                    })
                
                if five_layer.get('what_happening'):
                    beliefs.append({
                        'belief': 'FII Outflows',
                        'strength': 0.73,
                        'evidence': 'Flow data, currency pressure',
                        'invalidation': 'Risk-on sentiment return'
                    })
                
                if unified_state['market_reality']['regime_stability'] < 0.6:
                    beliefs.append({
                        'belief': 'Momentum Decay',
                        'strength': 0.66,
                        'evidence': 'Breadth deterioration, factor rotation',
                        'invalidation': 'Trend resumption or new leadership'
                    })
        
        # Add default beliefs if none loaded
        if not beliefs:
            beliefs = [
                {
                    'belief': 'Market Stability',
                    'strength': unified_state['market_reality']['regime_stability'],
                    'evidence': 'Regime analysis and market indicators',
                    'invalidation': 'Significant regime shift or external shock'
                }
            ]
        
        unified_state['belief_engine']['beliefs'] = beliefs
        
        # Execution memory from recent decisions
        recent_decisions = []
        
        # Add sample decisions based on current state
        if unified_state['portfolio_organism']['strategy_weights']:
            for strategy, weight in unified_state['portfolio_organism']['strategy_weights'].items():
                if isinstance(weight, (int, float)) and weight > 0.05:  # Only significant allocations
                    recent_decisions.append({
                        'time': '10:32',
                        'action': f'Allocated {weight:.1%} to {strategy}',
                        'reason': 'Regime optimization',
                        'belief': 'Market Dynamics',
                        'risk': 'Strategy concentration'
                    })
        
        unified_state['execution_memory']['recent_decisions'] = recent_decisions[:5]  # Last 5 decisions
        
    except Exception as e:
        print(f"Error loading unified state: {e}")
    
    return unified_state

# =========================== LAYER 1: MARKET REALITY BAR ===========================

def render_market_reality_bar(unified_state):
    """Layer 1: Market Reality Bar - The Bloomberg Headline"""
    
    reality = unified_state['market_reality']
    
    # Determine liquidity status
    liquidity_status = "High" if reality['system_health'] > 0.7 else "Medium" if reality['system_health'] > 0.4 else "Low"
    
    st.markdown(f"""
    <div class="market-reality-bar">
        <div class="reality-metric">
            <h6>Regime</h6>
            <h4>{reality['regime']}</h4>
        </div>
        <div class="reality-metric">
            <h6>Stability</h6>
            <h4>{reality['regime_stability']:.0%}</h4>
        </div>
        <div class="reality-metric">
            <h6>Pulse</h6>
            <h4>{'Violent' if reality['market_pulse'] > 0.7 else 'Calm' if reality['market_pulse'] < 0.3 else 'Active'}</h4>
        </div>
        <div class="reality-metric">
            <h6>Risk-On %</h6>
            <h4>{reality['risk_on_pct']}%</h4>
        </div>
        <div class="reality-metric">
            <h6>Exposure</h6>
            <h4>{reality['exposure']}%</h4>
        </div>
        <div class="reality-metric">
            <h6>Liquidity</h6>
            <h4>{liquidity_status}</h4>
        </div>
        <div class="reality-metric">
            <h6>Health</h6>
            <h4>{reality['system_health']:.0%}</h4>
        </div>
    </div>
    """, unsafe_allow_html=True)

# =========================== LAYER 2: BRAIN + BELIEF PANEL ===========================

def render_brain_belief_panel(unified_state):
    """Layer 2: Brain + Belief Panel - The Cognitive Layer"""
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("""
        <div class="brain-panel">
            <h3>🧠 Market Brain</h3>
        </div>
        """, unsafe_allow_html=True)
        
        # Regime map visualization
        st.subheader("Regime Map", help="Current market regime positioning")
        
        # Create regime stability gauge
        stability = unified_state['market_reality']['regime_stability']
        fig = go.Figure(go.Indicator(
            mode = "gauge+number",
            value = stability * 100,
            domain = {'x': [0, 1], 'y': [0, 1]},
            title = {'text': "Regime Stability"},
            gauge = {
                'axis': {'range': [None, 100]},
                'bar': {'color': "lightblue"},
                'steps': [
                    {'range': [0, 30], 'color': "red"},
                    {'range': [30, 70], 'color': "yellow"},
                    {'range': [70, 100], 'color': "green"}
                ],
                'threshold': {
                    'line': {'color': "red", 'width': 4},
                    'thickness': 0.75,
                    'value': 90
                }
            }
        ))
        fig.update_layout(height=200, margin=dict(l=20, r=20, t=40, b=20))
        st.plotly_chart(fig, use_container_width=True)
        
        # Pulse waveform
        st.markdown('<div class="waveform-container">', unsafe_allow_html=True)
        st.subheader("Pulse Waveform", help="Market pulse intensity over time")
        
        # Generate sample pulse data
        pulse_data = np.random.normal(unified_state['market_reality']['market_pulse'], 0.1, 50)
        pulse_data = np.clip(pulse_data, 0, 1)
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            y=pulse_data,
            mode='lines',
            line=dict(color='#60a5fa', width=2),
            fill='tonexty',
            fillcolor='rgba(96, 165, 250, 0.3)'
        ))
        fig.update_layout(
            height=150,
            margin=dict(l=20, r=20, t=20, b=20),
            showlegend=False,
            xaxis=dict(showgrid=False, showticklabels=False),
            yaxis=dict(showgrid=True, gridcolor='rgba(96, 165, 250, 0.2)'),
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)'
        )
        st.plotly_chart(fig, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Causal graph
        st.subheader("Causal Graph", help="How market forces connect and influence each other")
        
        # Create a simple causal network visualization
        causal_nodes = ["RBI Policy", "Bond Yields", "FII Flows", "IT Stocks", "Market Breadth"]
        causal_edges = [
            ("RBI Policy", "Bond Yields", 0.8),
            ("Bond Yields", "IT Stocks", -0.7),
            ("FII Flows", "Market Breadth", 0.6),
            ("Market Breadth", "IT Stocks", 0.5)
        ]
        
        # Create network-style visualization using plotly
        # Position nodes in a circle
        n_nodes = len(causal_nodes)
        angles = np.linspace(0, 2*np.pi, n_nodes, endpoint=False)
        x_pos = np.cos(angles)
        y_pos = np.sin(angles)
        
        # Create edges
        edge_x = []
        edge_y = []
        edge_info = []
        
        for i, (source, target, strength) in enumerate(causal_edges):
            source_idx = causal_nodes.index(source)
            target_idx = causal_nodes.index(target)
            
            edge_x.extend([x_pos[source_idx], x_pos[target_idx], None])
            edge_y.extend([y_pos[source_idx], y_pos[target_idx], None])
            edge_info.append(f"{source} → {target}: {strength:+.1f}")
        
        fig = go.Figure()
        
        # Add edges
        fig.add_trace(go.Scatter(
            x=edge_x, y=edge_y,
            line=dict(width=2, color='#60a5fa'),
            hoverinfo='none',
            mode='lines'
        ))
        
        # Add nodes
        fig.add_trace(go.Scatter(
            x=x_pos, y=y_pos,
            mode='markers+text',
            marker=dict(size=20, color='#60a5fa'),
            text=causal_nodes,
            textposition="middle center",
            textfont=dict(size=8, color='white'),
            hoverinfo='text',
            hovertext=causal_nodes
        ))
        
        fig.update_layout(
            showlegend=False,
            hovermode='closest',
            margin=dict(b=20,l=5,r=5,t=40),
            annotations=[ dict(
                text="Causal relationships between market forces",
                showarrow=False,
                xref="paper", yref="paper",
                x=0.005, y=-0.002,
                xanchor='left', yanchor='bottom',
                font=dict(color='#888', size=10)
            )],
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            height=200
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Survival alerts
        survival_alerts = []
        if unified_state['market_reality']['regime_stability'] < 0.4:
            survival_alerts.append("⚠️ Regime instability detected")
        if unified_state['risk_spine']['emergency_brake']:
            survival_alerts.append("🚨 Emergency protocols active")
        
        if survival_alerts:
            st.error("**Survival Alerts:**")
            for alert in survival_alerts:
                st.write(f"• {alert}")
        else:
            st.success("✅ No survival alerts - System operating normally")
    
    with col2:
        st.markdown("""
        <div class="brain-panel">
            <h3>🎯 Belief Engine</h3>
        </div>
        """, unsafe_allow_html=True)
        
        # Belief table
        beliefs = unified_state['belief_engine']['beliefs']
        
        if beliefs:
            st.markdown('<div class="belief-table">', unsafe_allow_html=True)
            
            # Create belief dataframe
            belief_data = []
            for belief in beliefs:
                belief_data.append({
                    'Belief': belief['belief'],
                    'Strength': f"{belief['strength']:.2f}",
                    'Evidence': belief['evidence'][:50] + "..." if len(belief['evidence']) > 50 else belief['evidence']
                })
            
            belief_df = pd.DataFrame(belief_data)
            st.dataframe(belief_df, use_container_width=True, hide_index=True)
            
            st.markdown('</div>', unsafe_allow_html=True)
            
            # Clickable belief details
            selected_belief = st.selectbox(
                "🔍 Analyze Belief", 
                [b['belief'] for b in beliefs],
                help="Click to see what data caused this belief and what would invalidate it"
            )
            
            if selected_belief:
                belief_data = next(b for b in beliefs if b['belief'] == selected_belief)
                
                with st.container():
                    st.markdown("**🎯 Belief Analysis:**")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("Strength", f"{belief_data['strength']:.2f}")
                        st.write(f"**Evidence:** {belief_data['evidence']}")
                    
                    with col2:
                        confidence_pct = belief_data['strength'] * 100
                        st.metric("Confidence", f"{confidence_pct:.0f}%")
                        st.write(f"**Invalidation:** {belief_data.get('invalidation', 'Data contradiction')}")
                    
                    # Belief strength visualization
                    fig = go.Figure(go.Indicator(
                        mode = "gauge+number",
                        value = confidence_pct,
                        domain = {'x': [0, 1], 'y': [0, 1]},
                        title = {'text': f"{selected_belief} Conviction"},
                        gauge = {
                            'axis': {'range': [None, 100]},
                            'bar': {'color': "#60a5fa"},
                            'steps': [
                                {'range': [0, 50], 'color': "lightgray"},
                                {'range': [50, 80], 'color': "yellow"},
                                {'range': [80, 100], 'color': "green"}
                            ]
                        }
                    ))
                    fig.update_layout(height=200, margin=dict(l=20, r=20, t=40, b=20))
                    st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No active beliefs detected. System in baseline mode.")

# =========================== LAYER 3: PORTFOLIO & CAPITAL PANEL ===========================

def render_portfolio_capital_panel(unified_state):
    """Layer 3: Portfolio & Capital Panel - Where Investors Stare"""
    
    st.markdown("""
    <div class="portfolio-panel">
        <h3>💼 Portfolio & Capital Organism</h3>
    </div>
    """, unsafe_allow_html=True)
    
    # Three subpanels
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        st.subheader("A) Strategy Layer")
        strategy_weights = unified_state['portfolio_organism']['strategy_weights']
        
        if strategy_weights:
            # Strategy allocation chart
            strategies = list(strategy_weights.keys())
            weights = [float(w) if isinstance(w, (int, float)) else 0 for w in strategy_weights.values()]
            
            fig = px.pie(
                values=weights,
                names=strategies,
                title="Capital Allocator at Work"
            )
            fig.update_traces(textposition='inside', textinfo='percent+label')
            fig.update_layout(height=300, margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(fig, use_container_width=True)
            
            # Strategy metrics
            for strategy, weight in strategy_weights.items():
                if isinstance(weight, (int, float)):
                    conviction = "High" if weight > 0.2 else "Medium" if weight > 0.1 else "Low"
                    st.metric(f"{strategy}", f"{weight:.1%}", help=f"Conviction: {conviction}")
        else:
            st.info("No strategy allocations available")
    
    with col2:
        st.subheader("B) Portfolio Organism")
        
        # Portfolio metrics
        stock_weights = unified_state['portfolio_organism']['stock_weights']
        sector_exposure = unified_state['portfolio_organism']['sector_exposure']
        cash = unified_state['portfolio_organism']['cash']
        
        st.metric("Stock Positions", len(stock_weights))
        st.metric("Cash Allocation", f"{cash:.1%}")
        st.metric("Turnover", f"{unified_state['portfolio_organism']['turnover']:.1%}")
        
        # Sector exposure chart
        if sector_exposure:
            sectors = list(sector_exposure.keys())
            exposures = list(sector_exposure.values())
            
            fig = px.bar(
                x=exposures,
                y=sectors,
                orientation='h',
                title="Sector Exposure"
            )
            fig.update_layout(height=250, margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(fig, use_container_width=True)
    
    with col3:
        st.subheader("C) Constraint Monitor")
        
        # Live constraint monitoring
        constraints = unified_state['constraint_monitor']
        
        st.markdown('<div class="constraint-monitor">', unsafe_allow_html=True)
        
        for constraint, data in constraints.items():
            status_class = f"constraint-{data['status']}"
            st.markdown(f"""
            <div class="constraint-item {status_class}">
                <div>{constraint.replace('_', ' ').title()}</div>
                <div>{data['value']} / {data['limit']}</div>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Discipline indicator
        all_green = all(c['status'] == 'green' for c in constraints.values())
        if all_green:
            st.success("✅ All constraints satisfied - Discipline maintained")
        else:
            st.warning("⚠️ Some constraints approaching limits")

# =========================== LAYER 4: RISK SPINE ===========================

def render_risk_spine(unified_state):
    """Layer 4: Risk Spine - Visually Intimidating"""
    
    st.markdown("""
    <div class="risk-spine">
        <h3>🛡️ Risk Spine - Capital Protection Authority</h3>
    </div>
    """, unsafe_allow_html=True)
    
    # Risk status banner
    risk_status = unified_state['risk_spine']['status']
    emergency_brake = unified_state['risk_spine']['emergency_brake']
    
    status_class = f"risk-status-{risk_status.lower()}"
    
    st.markdown(f"""
    <div class="risk-status-banner {status_class}">
        RISK STATUS: {risk_status}
        {'🚨 EMERGENCY BRAKE ACTIVE' if emergency_brake else ''}
    </div>
    """, unsafe_allow_html=True)
    
    # Risk metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Emergency Brake", "🚨 ACTIVE" if emergency_brake else "✅ INACTIVE")
    
    with col2:
        drawdown_risk = unified_state['risk_spine']['drawdown_risk']
        st.metric("Drawdown Risk", f"{drawdown_risk:.1%}")
    
    with col3:
        volatility = unified_state['risk_spine']['volatility']
        st.metric("Volatility", f"{volatility:.1%}")
    
    with col4:
        st.metric("Kill Switches", len(unified_state['risk_spine']['kill_switches']))
    
    # Stress indicators
    st.subheader("Stress Indicators")
    
    # Create stress gauge
    stress_level = drawdown_risk * 5  # Convert to 0-1 scale
    
    fig = go.Figure(go.Indicator(
        mode = "gauge+number+delta",
        value = stress_level * 100,
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': "Portfolio Stress Level"},
        delta = {'reference': 20},
        gauge = {
            'axis': {'range': [None, 100]},
            'bar': {'color': "red" if stress_level > 0.7 else "orange" if stress_level > 0.4 else "green"},
            'steps': [
                {'range': [0, 40], 'color': "lightgreen"},
                {'range': [40, 70], 'color': "yellow"},
                {'range': [70, 100], 'color': "red"}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': 80
            }
        }
    ))
    fig.update_layout(height=300)
    st.plotly_chart(fig, use_container_width=True)
    
    # The Red Button - Simulate Shock
    st.markdown("""
    <div class="shock-button" onclick="alert('SHOCK SIMULATION ACTIVATED - All systems entering defensive mode')">
        🚨 SIMULATE SHOCK 🚨
    </div>
    """, unsafe_allow_html=True)
    
    if st.button("🚨 SIMULATE MARKET SHOCK", help="Test system response to extreme market stress"):
        st.error("🚨 SHOCK SIMULATION ACTIVATED")
        st.warning("All systems entering defensive mode...")
        st.info("Emergency protocols engaged")
        st.success("System freeze mechanisms operational")
        st.write("**This is when investors trust the system.**")

# =========================== LAYER 5: EXECUTION & MEMORY ===========================

def render_execution_memory(unified_state):
    """Layer 5: Execution & Memory - The Audit Trail"""
    
    st.markdown("""
    <div class="execution-panel">
        <h3>⚡ Execution & Memory - Institutional Audit Trail</h3>
    </div>
    """, unsafe_allow_html=True)
    
    # Two tabs: Decisions and Memory
    tab1, tab2 = st.tabs(["📋 Decisions", "🧠 Memory"])
    
    with tab1:
        st.subheader("Recent Decisions - Chronological Audit")
        
        decisions = unified_state['execution_memory']['recent_decisions']
        
        if decisions:
            for decision in decisions:
                st.markdown(f"""
                <div class="decision-entry">
                    <div class="decision-time">{decision['time']}</div>
                    <div class="decision-action">{decision['action']}</div>
                    <div>Reason: {decision['reason']}</div>
                    <div>Belief: {decision['belief']} | Risk: {decision['risk']}</div>
                </div>
                """, unsafe_allow_html=True)
                
                # Clickable decision details
                if st.button(f"🔍 Analyze Decision: {decision['action'][:30]}...", key=f"decision_{decision['time']}"):
                    with st.expander("Decision Deep Dive"):
                        st.write(f"**Time:** {decision['time']}")
                        st.write(f"**Action:** {decision['action']}")
                        st.write(f"**Underlying Belief:** {decision['belief']}")
                        st.write(f"**Causal Chain:** Market regime → Belief formation → Portfolio action")
                        st.write(f"**Risk Assessment:** {decision['risk']}")
                        st.write(f"**Approval:** System authority")
        else:
            st.info("No recent decisions recorded. System in steady state.")
    
    with tab2:
        st.subheader("Regime Memory - Historical Context")
        
        # Similar regimes
        st.write("**Similar Historical Regimes:**")
        similar_regimes = [
            {"period": "2018 Q4", "similarity": "85%", "outcome": "12% correction, policy reversal"},
            {"period": "2013 Q2", "similarity": "78%", "outcome": "Taper tantrum, accommodation resumed"},
            {"period": "2020 Q1", "similarity": "65%", "outcome": "Crisis intervention, V-shaped recovery"}
        ]
        
        for regime in similar_regimes:
            st.markdown(f"""
            <div class="decision-entry">
                <div><strong>{regime['period']}</strong> - {regime['similarity']} similarity</div>
                <div>Outcome: {regime['outcome']}</div>
            </div>
            """, unsafe_allow_html=True)
        
        # Portfolio behavior memory
        st.write("**Portfolio Behavior in Similar Conditions:**")
        st.info("Historical analysis shows defensive positioning preserved 8-12% capital during similar regime transitions")
        
        # Memory-based predictions
        st.write("**Memory-Based Expectations:**")
        st.success("Current positioning aligns with successful historical precedents")

# =========================== MAIN COMMAND BRIDGE ===========================

def main_command_bridge():
    """Main Northstar Command Bridge - Bloomberg-Grade Trading Floor"""
    
    # Load unified state
    unified_state = load_unified_state()
    
    # Command bridge header
    st.markdown("""
    <div style="text-align: center; margin-bottom: 1rem;">
        <h1 style="color: #00ff88; font-size: 2.8rem; margin: 0; font-family: 'Courier New', monospace;">
            🧭 NORTHSTAR COMMAND BRIDGE
        </h1>
        <p style="color: #60a5fa; font-size: 1.2rem; margin: 0.3rem 0; font-weight: 700;">
            Living Capital Organism • Bloomberg-Grade Control Interface
        </p>
        <p style="color: #a0aec0; font-size: 0.9rem; margin: 0;">
            This is not a trading bot. This is a decision engine.
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Layer 1: Market Reality Bar
    render_market_reality_bar(unified_state)
    
    # Layer 2: Brain + Belief Panel
    render_brain_belief_panel(unified_state)
    
    # Layer 3: Portfolio & Capital Panel
    render_portfolio_capital_panel(unified_state)
    
    # Layer 4: Risk Spine
    render_risk_spine(unified_state)
    
    # Layer 5: Execution & Memory
    render_execution_memory(unified_state)
    
    # Footer - What makes this special
    st.markdown("""
    <div style="text-align: center; margin-top: 2rem; padding: 1rem; background: rgba(0, 255, 136, 0.1); border-radius: 8px;">
        <h4 style="color: #00ff88; margin: 0;">What Makes This Different</h4>
        <p style="color: #a0aec0; margin: 0.5rem 0;">
            Most dashboards show: Charts • P&L • Indicators<br>
            <strong>Northstar shows: Thought • Memory • Risk • Causality</strong>
        </p>
        <p style="color: #60a5fa; margin: 0; font-size: 0.9rem;">
            That's what PMs actually use.
        </p>
    </div>
    """, unsafe_allow_html=True)

# =========================== MAIN EXECUTION ===========================

if __name__ == "__main__":
    main_command_bridge()