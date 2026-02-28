#!/usr/bin/env python3
"""
🧭 NORTHSTAR UNIFIED TERMINAL
The ultimate hedge fund command center

This is not just a dashboard. This is a hedge fund war room that combines:
- War Room (Operations): Real-time survival layer
- Portfolio Command: Where money is actually placed  
- Intelligence Organism: Where Northstar thinks

Built like Bloomberg + Two Sigma + a war room.
"""

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

# Add src to path

from dashboard.data_loader import load_unified_snapshot, load_war_room_data, load_portfolio_data, load_intelligence_data, check_data_health

# =========================== TERMINAL CONFIGURATION ===========================

st.set_page_config(
    layout="wide", 
    page_title="🧭 Northstar Unified Terminal",
    initial_sidebar_state="collapsed"
)

# =========================== TERMINAL STYLING ===========================

st.markdown("""
<style>
    /* UNIFIED TERMINAL THEME */
    .main { padding: 0.5rem; }
    
    /* GLOBAL STATUS BAR */
    .status-bar {
        background: linear-gradient(90deg, #001122, #002244);
        color: #00ff88;
        padding: 0.8rem 1.5rem;
        border-bottom: 2px solid #00ff88;
        position: sticky;
        top: 0;
        z-index: 1000;
        display: grid;
        grid-template-columns: repeat(7, 1fr);
        gap: 1rem;
        font-size: 0.9rem;
        font-weight: 700;
        box-shadow: 0 2px 10px rgba(0, 255, 136, 0.3);
        border-radius: 8px;
        margin-bottom: 1rem;
    }
    
    .status-metric {
        text-align: center;
        padding: 0.4rem;
        background: rgba(0, 255, 136, 0.1);
        border-radius: 6px;
        border: 1px solid rgba(0, 255, 136, 0.3);
    }
    
    .status-metric h5 {
        margin: 0;
        font-size: 0.7rem;
        color: #a0aec0;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    
    .status-metric h3 {
        margin: 0.2rem 0 0 0;
        font-size: 1.1rem;
        font-weight: 900;
    }
    
    /* WAR ROOM STYLING */
    .war-room {
        background: linear-gradient(135deg, #7f1d1d, #991b1b);
        border: 2px solid #ff6b6b;
        border-radius: 12px;
        padding: 1rem;
        margin: 0.5rem 0;
    }
    
    .war-room h3 {
        color: #ff6b6b;
        margin: 0 0 1rem 0;
        font-size: 1.2rem;
        font-weight: 900;
        text-transform: uppercase;
        letter-spacing: 2px;
    }
    
    /* PORTFOLIO COMMAND STYLING */
    .portfolio-command {
        background: linear-gradient(135deg, #1e3a8a, #1d4ed8);
        border: 2px solid #60a5fa;
        border-radius: 12px;
        padding: 1rem;
        margin: 0.5rem 0;
    }
    
    .portfolio-command h3 {
        color: #60a5fa;
        margin: 0 0 1rem 0;
        font-size: 1.2rem;
        font-weight: 900;
        text-transform: uppercase;
        letter-spacing: 2px;
    }
    
    /* INTELLIGENCE ORGANISM STYLING */
    .intelligence-organism {
        background: linear-gradient(135deg, #064e3b, #047857);
        border: 2px solid #00ff88;
        border-radius: 12px;
        padding: 1rem;
        margin: 0.5rem 0;
    }
    
    .intelligence-organism h3 {
        color: #00ff88;
        margin: 0 0 1rem 0;
        font-size: 1.2rem;
        font-weight: 900;
        text-transform: uppercase;
        letter-spacing: 2px;
    }
    
    /* GAUGE STYLING */
    .gauge-container {
        display: flex;
        justify-content: space-around;
        margin: 1rem 0;
    }
    
    .gauge {
        text-align: center;
        padding: 1rem;
        background: rgba(0, 0, 0, 0.3);
        border-radius: 8px;
        border: 1px solid rgba(255, 255, 255, 0.2);
        min-width: 120px;
    }
    
    .gauge h4 {
        margin: 0;
        font-size: 0.8rem;
        color: #a0aec0;
        text-transform: uppercase;
    }
    
    .gauge h2 {
        margin: 0.5rem 0;
        font-size: 2rem;
        font-weight: 900;
    }
    
    /* TERMINAL GRID */
    .terminal-grid {
        display: grid;
        grid-template-columns: 1fr 1.5fr 1fr;
        gap: 1rem;
        margin-top: 1rem;
    }
    
    /* CHART CONTAINERS */
    .chart-container {
        background: rgba(0, 0, 0, 0.2);
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem 0;
        border: 1px solid rgba(255, 255, 255, 0.1);
    }
    
    .chart-title {
        color: white;
        font-size: 0.9rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
</style>
""", unsafe_allow_html=True)

# =========================== GLOBAL STATUS BAR ===========================

def render_global_status_bar(snapshot):
    """Render the global status bar - the nerve center"""
    
    market = snapshot.get('market', {})
    portfolio = snapshot.get('portfolio', {})
    intelligence = snapshot.get('intelligence', {})
    risk = snapshot.get('risk', {})
    
    # Color coding for metrics
    regime = market.get('regime', 'Unknown')
    regime_color = "#00ff88" if regime in ['Expansion', 'Boom'] else "#ff6b6b" if regime in ['Crisis', 'Slowdown'] else "#ffa500"
    
    exposure = portfolio.get('total_exposure', 0)
    exposure_color = "#ff6b6b" if exposure > market.get('allowed_exposure', 50) else "#00ff88"
    
    drawdown = abs(portfolio.get('current_drawdown', 0))
    dd_color = "#ff6b6b" if drawdown > 10 else "#ffa500" if drawdown > 5 else "#00ff88"
    
    vol = risk.get('market_vol', 15)
    vol_color = "#ff6b6b" if vol > 25 else "#ffa500" if vol > 20 else "#00ff88"
    
    liquidity = market.get('liquidity_index', 50)
    liq_color = "#00ff88" if liquidity > 60 else "#ffa500" if liquidity > 40 else "#ff6b6b"
    
    ai_conviction = intelligence.get('conviction', 0.5)
    ai_color = "#00ff88" if ai_conviction > 0.7 else "#ffa500" if ai_conviction > 0.5 else "#ff6b6b"
    
    st.markdown(f"""
    <div class="status-bar">
        <div class="status-metric">
            <h5>REGIME</h5>
            <h3 style="color: {regime_color};">{regime.upper()}</h3>
        </div>
        <div class="status-metric">
            <h5>RISK</h5>
            <h3 style="color: {vol_color};">{vol:.0f}%</h3>
        </div>
        <div class="status-metric">
            <h5>EXPOSURE</h5>
            <h3 style="color: {exposure_color};">{exposure:.0f}%</h3>
        </div>
        <div class="status-metric">
            <h5>DD</h5>
            <h3 style="color: {dd_color};">{drawdown:.1f}%</h3>
        </div>
        <div class="status-metric">
            <h5>VOL</h5>
            <h3 style="color: {vol_color};">{vol:.0f}%</h3>
        </div>
        <div class="status-metric">
            <h5>LIQUIDITY</h5>
            <h3 style="color: {liq_color};">{liquidity:.0f}</h3>
        </div>
        <div class="status-metric">
            <h5>AI CONVICTION</h5>
            <h3 style="color: {ai_color};">{ai_conviction:.0%}</h3>
        </div>
    </div>
    """, unsafe_allow_html=True)

# =========================== WAR ROOM (OPERATIONS) ===========================

def render_war_room(snapshot, war_room_data):
    """🟥 WAR ROOM - Real-time Survival Layer"""
    
    st.markdown("""
    <div class="war-room">
        <h3>🟥 WAR ROOM (Operations)</h3>
        <p style="color: #fca5a5; margin: 0; font-style: italic;">"Are we safe right now?"</p>
    </div>
    """, unsafe_allow_html=True)
    
    # TOP ROW - Risk & Exposure Gauges
    col1, col2, col3, col4 = st.columns(4)
    
    portfolio = snapshot.get('portfolio', {})
    risk = snapshot.get('risk', {})
    market = snapshot.get('market', {})
    
    with col1:
        vol = risk.get('market_vol', 15)
        vol_color = "#ff6b6b" if vol > 25 else "#ffa500" if vol > 20 else "#00ff88"
        
        fig = go.Figure(go.Indicator(
            mode = "gauge+number",
            value = vol,
            domain = {'x': [0, 1], 'y': [0, 1]},
            title = {'text': "Volatility %"},
            gauge = {
                'axis': {'range': [None, 50]},
                'bar': {'color': vol_color},
                'steps': [
                    {'range': [0, 20], 'color': "rgba(0, 255, 136, 0.2)"},
                    {'range': [20, 30], 'color': "rgba(255, 165, 0, 0.2)"},
                    {'range': [30, 50], 'color': "rgba(255, 107, 107, 0.2)"}
                ],
                'threshold': {
                    'line': {'color': "red", 'width': 4},
                    'thickness': 0.75,
                    'value': 30
                }
            }
        ))
        fig.update_layout(height=200, margin=dict(l=20, r=20, t=40, b=20))
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        drawdown = abs(portfolio.get('current_drawdown', 0))
        dd_color = "#ff6b6b" if drawdown > 10 else "#ffa500" if drawdown > 5 else "#00ff88"
        
        fig = go.Figure(go.Indicator(
            mode = "gauge+number",
            value = drawdown,
            domain = {'x': [0, 1], 'y': [0, 1]},
            title = {'text': "Drawdown %"},
            gauge = {
                'axis': {'range': [0, 20]},
                'bar': {'color': dd_color},
                'steps': [
                    {'range': [0, 5], 'color': "rgba(0, 255, 136, 0.2)"},
                    {'range': [5, 10], 'color': "rgba(255, 165, 0, 0.2)"},
                    {'range': [10, 20], 'color': "rgba(255, 107, 107, 0.2)"}
                ],
                'threshold': {
                    'line': {'color': "red", 'width': 4},
                    'thickness': 0.75,
                    'value': 12
                }
            }
        ))
        fig.update_layout(height=200, margin=dict(l=20, r=20, t=40, b=20))
        st.plotly_chart(fig, use_container_width=True)
    
    with col3:
        exposure = portfolio.get('total_exposure', 0)
        allowed = market.get('allowed_exposure', 50)
        exposure_color = "#ff6b6b" if exposure > allowed else "#00ff88"
        
        fig = go.Figure(go.Indicator(
            mode = "gauge+number",
            value = exposure,
            domain = {'x': [0, 1], 'y': [0, 1]},
            title = {'text': "Exposure %"},
            gauge = {
                'axis': {'range': [0, 100]},
                'bar': {'color': exposure_color},
                'steps': [
                    {'range': [0, allowed], 'color': "rgba(0, 255, 136, 0.2)"},
                    {'range': [allowed, 100], 'color': "rgba(255, 107, 107, 0.2)"}
                ],
                'threshold': {
                    'line': {'color': "red", 'width': 4},
                    'thickness': 0.75,
                    'value': allowed
                }
            }
        ))
        fig.update_layout(height=200, margin=dict(l=20, r=20, t=40, b=20))
        st.plotly_chart(fig, use_container_width=True)
    
    with col4:
        # Kill Switch Status
        kill_switch_status = "SAFE"  # This would come from actual kill switch system
        status_color = "#00ff88" if kill_switch_status == "SAFE" else "#ff6b6b"
        
        st.markdown(f"""
        <div class="gauge" style="border-color: {status_color};">
            <h4>KILL SWITCH</h4>
            <h2 style="color: {status_color};">{kill_switch_status}</h2>
            <p style="color: #a0aec0; font-size: 0.8rem;">System Status</p>
        </div>
        """, unsafe_allow_html=True)
    
    # CENTER - Market Stress Visualization
    st.markdown("#### 🌡️ Market Stress Monitor")
    
    # Create market stress heatmap
    stress_data = war_room_data.get('market_stress', pd.DataFrame())
    if not stress_data.empty and len(stress_data) > 1:
        # Show recent stress indicators
        recent_stress = stress_data.tail(50)
        
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=('Liquidity Pressure', 'Breadth Collapse', 'Correlation Spike', 'Overall Stress'),
            specs=[[{"secondary_y": False}, {"secondary_y": False}],
                   [{"secondary_y": False}, {"secondary_y": False}]]
        )
        
        # Add stress indicators if columns exist
        if 'z_vol' in recent_stress.columns:
            fig.add_trace(go.Scatter(x=recent_stress.index, y=recent_stress['z_vol'], 
                                   name='Vol Stress', line=dict(color='#ff6b6b')), row=1, col=1)
        
        if 'z_breadth' in recent_stress.columns:
            fig.add_trace(go.Scatter(x=recent_stress.index, y=recent_stress['z_breadth'], 
                                   name='Breadth', line=dict(color='#ffa500')), row=1, col=2)
        
        if 'z_corr' in recent_stress.columns:
            fig.add_trace(go.Scatter(x=recent_stress.index, y=recent_stress['z_corr'], 
                                   name='Correlation', line=dict(color='#60a5fa')), row=2, col=1)
        
        if 'MarketStress' in recent_stress.columns:
            fig.add_trace(go.Scatter(x=recent_stress.index, y=recent_stress['MarketStress'], 
                                   name='Overall', line=dict(color='#00ff88')), row=2, col=2)
        
        fig.update_layout(height=400, showlegend=False, title_text="Market Stress Indicators")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Market stress data not available")
    
    # BOTTOM - Execution Monitor
    st.markdown("#### ⚡ Live Execution")
    
    exec_col1, exec_col2, exec_col3 = st.columns(3)
    
    execution = snapshot.get('execution', {})
    
    with exec_col1:
        st.metric("Recent Trades", execution.get('recent_trades', 0))
    
    with exec_col2:
        st.metric("Total Turnover", f"{execution.get('total_turnover', 0):.1%}")
    
    with exec_col3:
        # This would show live PnL vs expected
        st.metric("Live PnL", f"₹{portfolio.get('equity', 100000):.0f}")

# =========================== PORTFOLIO COMMAND (WHERE MONEY IS PLACED) ===========================

def render_portfolio_command(snapshot, portfolio_data):
    """🟦 PORTFOLIO COMMAND - Where money is actually placed"""
    
    st.markdown("""
    <div class="portfolio-command">
        <h3>🟦 PORTFOLIO COMMAND (What we hold)</h3>
        <p style="color: #93c5fd; margin: 0; font-style: italic;">"What are we holding and why?"</p>
    </div>
    """, unsafe_allow_html=True)
    
    portfolio = snapshot.get('portfolio', {})
    strategies = snapshot.get('strategies', {})
    
    # TOP - Capital Engine
    st.markdown("#### 💰 Capital Engine")
    
    cap_col1, cap_col2, cap_col3 = st.columns(3)
    
    with cap_col1:
        # Strategy Allocation Pie
        capital_data = strategies.get('capital_data', {})
        if capital_data and isinstance(capital_data, dict) and 'allocations' in capital_data:
            allocations = capital_data['allocations']
            
            # Filter out zero allocations and ensure we have valid data
            if isinstance(allocations, dict):
                active_allocations = {k: v for k, v in allocations.items() if isinstance(v, (int, float)) and v > 0.01}
                
                if active_allocations:
                    fig = px.pie(
                        values=list(active_allocations.values()),
                        names=list(active_allocations.keys()),
                        title="Strategy Capital Allocation"
                    )
                    fig.update_layout(height=300, showlegend=True)
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No active capital allocations")
            else:
                st.info("Capital allocation format issue")
        else:
            st.info("Capital allocation data not available")
    
    with cap_col2:
        # Bayesian Skill Bar
        active_count = strategies.get('active_count', 0)
        total_count = strategies.get('total_count', 16)
        avg_skill = strategies.get('avg_skill', 0.5)
        
        fig = go.Figure()
        
        # Add skill bar
        fig.add_trace(go.Bar(
            x=['Strategy Skill'],
            y=[avg_skill],
            marker_color='#60a5fa',
            text=[f'{avg_skill:.1%}'],
            textposition='inside'
        ))
        
        fig.update_layout(
            title="Average Strategy Skill",
            yaxis=dict(range=[0, 1], tickformat='.0%'),
            height=300
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with cap_col3:
        # Strategy Status
        st.markdown(f"""
        <div class="gauge">
            <h4>ACTIVE STRATEGIES</h4>
            <h2 style="color: #60a5fa;">{active_count}/{total_count}</h2>
            <p style="color: #a0aec0; font-size: 0.8rem;">Competing for Capital</p>
        </div>
        """, unsafe_allow_html=True)
    
    # CENTER - Holdings
    st.markdown("#### 📊 Current Holdings")
    
    top_holdings = portfolio.get('top_holdings', [])
    
    # Defensive check for different data types
    if top_holdings is not None and hasattr(top_holdings, '__len__') and len(top_holdings) > 0:
        try:
            # Create holdings dataframe
            holdings_df = pd.DataFrame(top_holdings)
            
            # Rename columns for display
            if 'final_weight' in holdings_df.columns:
                holdings_df = holdings_df.rename(columns={'final_weight': 'Weight %'})
            elif 'weight' in holdings_df.columns:
                holdings_df = holdings_df.rename(columns={'weight': 'Weight %'})
            
            holdings_df = holdings_df.rename(columns={'ticker': 'Ticker'})
            
            # Format weight as percentage
            if 'Weight %' in holdings_df.columns:
                holdings_df['Weight %'] = holdings_df['Weight %'].round(2)
            
            # Display as table
            st.dataframe(holdings_df, use_container_width=True, hide_index=True)
            
            # Holdings visualization
            if len(holdings_df) > 0:
                fig = px.bar(
                    holdings_df.head(10),
                    x='Ticker',
                    y='Weight %',
                    title="Top 10 Holdings",
                    color='Weight %',
                    color_continuous_scale='Blues'
                )
                fig.update_layout(height=300)
                st.plotly_chart(fig, use_container_width=True)
                
        except Exception as e:
            st.error(f"Error displaying holdings: {e}")
            st.info("Holdings data format issue - please check data structure")
    else:
        st.info("No holdings data available")
    
    # BOTTOM - Performance
    st.markdown("#### 📈 Portfolio Performance")
    
    perf_col1, perf_col2, perf_col3, perf_col4 = st.columns(4)
    
    with perf_col1:
        equity = portfolio.get('equity', 100000)
        st.metric("Portfolio Value", f"₹{equity:,.0f}")
    
    with perf_col2:
        recent_return = portfolio.get('recent_return_20d', 0)
        return_color = "normal" if abs(recent_return) < 5 else "inverse" if recent_return < 0 else "normal"
        st.metric("20D Return", f"{recent_return:+.1f}%", delta_color=return_color)
    
    with perf_col3:
        volatility = portfolio.get('volatility_20d', 15)
        st.metric("Volatility", f"{volatility:.1f}%")
    
    with perf_col4:
        max_dd = portfolio.get('max_drawdown', 0)
        st.metric("Max Drawdown", f"{max_dd:.1f}%")
    
    # Performance chart
    performance_data = portfolio_data.get('performance', pd.DataFrame())
    if not performance_data.empty and 'Equity' in performance_data.columns:
        # Show recent performance
        recent_perf = performance_data.tail(100)
        
        fig = px.line(
            recent_perf,
            x=recent_perf.index,
            y='Equity',
            title="Portfolio Equity Curve (Recent 100 Days)"
        )
        fig.update_layout(height=300)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Performance data not available")

# =========================== INTELLIGENCE ORGANISM (WHERE NORTHSTAR THINKS) ===========================

def render_intelligence_organism(snapshot, intelligence_data):
    """🧠 INTELLIGENCE ORGANISM - Where Northstar thinks"""
    
    st.markdown("""
    <div class="intelligence-organism">
        <h3>🧠 INTELLIGENCE ORGANISM (Why it exists)</h3>
        <p style="color: #6ee7b7; margin: 0; font-style: italic;">"What kind of world are we in?"</p>
    </div>
    """, unsafe_allow_html=True)
    
    intelligence = snapshot.get('intelligence', {})
    market = snapshot.get('market', {})
    
    # LEFT - Narrative Engine
    st.markdown("#### 🎯 AI Narrative Engine")
    
    ai_status = intelligence.get('status', 'unavailable')
    ai_conviction = intelligence.get('conviction', 0.5)
    ai_regime = intelligence.get('regime_ai', 'neutral')
    primary_action = intelligence.get('primary_action', 'MAINTAIN_EXPOSURE')
    
    # AI Status indicator
    status_color = "#00ff88" if ai_status == 'active' else "#ff6b6b" if ai_status == 'error' else "#ffa500"
    
    st.markdown(f"""
    <div style="background: rgba(0, 0, 0, 0.3); padding: 1rem; border-radius: 8px; border-left: 4px solid {status_color};">
        <h4 style="color: {status_color}; margin: 0 0 0.5rem 0;">AI STATUS: {ai_status.upper()}</h4>
        <p style="color: white; margin: 0.5rem 0;"><strong>Regime:</strong> {ai_regime.title()}</p>
        <p style="color: white; margin: 0.5rem 0;"><strong>Conviction:</strong> {ai_conviction:.1%}</p>
        <p style="color: white; margin: 0.5rem 0;"><strong>Primary Action:</strong> {primary_action.replace('_', ' ')}</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Market Forces
    st.markdown("##### 🌊 Key Market Forces")
    
    macro_score = market.get('macro_score', 0.0)
    regime = market.get('regime', 'Unknown')
    liquidity = market.get('liquidity_index', 50)
    
    forces = [
        f"Macro Environment: {regime} (Score: {macro_score:+.2f})",
        f"Liquidity Conditions: {'Tight' if liquidity < 40 else 'Ample' if liquidity > 60 else 'Neutral'} ({liquidity:.0f})",
        f"AI Conviction: {'High' if ai_conviction > 0.7 else 'Medium' if ai_conviction > 0.5 else 'Low'} ({ai_conviction:.1%})"
    ]
    
    for force in forces:
        st.markdown(f"• {force}")
    
    # CENTER - Strategy Evolution
    st.markdown("#### 🧬 Strategy Evolution")
    
    beliefs_data = intelligence_data.get('beliefs', pd.DataFrame())
    if not beliefs_data.empty:
        # Show strategy skill evolution over time
        recent_beliefs = beliefs_data.tail(30)
        
        # Get skill columns (assuming they exist)
        skill_columns = [col for col in recent_beliefs.columns if 'skill' in col.lower() or 'alpha' in col.lower()]
        
        if skill_columns:
            fig = px.line(
                recent_beliefs,
                x=recent_beliefs.index,
                y=skill_columns[:5],  # Show top 5 strategies
                title="Strategy Skill Evolution"
            )
            fig.update_layout(height=250, showlegend=True)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Strategy skill data not available")
    else:
        st.info("Strategy beliefs data not available")
    
    # RIGHT - Learning System
    st.markdown("#### 🤖 Learning System")
    
    system_health = intelligence.get('system_health', {})
    health_grade = system_health.get('grade', 'D')
    
    # Learning metrics
    learning_col1, learning_col2 = st.columns(2)
    
    with learning_col1:
        health_color = "#00ff88" if health_grade == 'A' else "#7ed321" if health_grade == 'B' else "#ffa500" if health_grade == 'C' else "#ff6b6b"
        
        st.markdown(f"""
        <div class="gauge" style="border-color: {health_color};">
            <h4>AI HEALTH</h4>
            <h2 style="color: {health_color};">{health_grade}</h2>
            <p style="color: #a0aec0; font-size: 0.8rem;">System Grade</p>
        </div>
        """, unsafe_allow_html=True)
    
    with learning_col2:
        # Learning status
        learning_active = ai_status == 'active'
        learning_color = "#00ff88" if learning_active else "#ff6b6b"
        learning_text = "ACTIVE" if learning_active else "DORMANT"
        
        st.markdown(f"""
        <div class="gauge" style="border-color: {learning_color};">
            <h4>LEARNING</h4>
            <h2 style="color: {learning_color};">{learning_text}</h2>
            <p style="color: #a0aec0; font-size: 0.8rem;">Adaptation Status</p>
        </div>
        """, unsafe_allow_html=True)
    
    # Recent Learning Insights
    st.markdown("##### 🧠 Recent Insights")
    
    if ai_status == 'active':
        insights = [
            f"AI detected {regime.lower()} regime with {ai_conviction:.0%} confidence",
            f"Recommending {primary_action.replace('_', ' ').lower()} strategy",
            f"System health grade: {health_grade} - {'Excellent' if health_grade == 'A' else 'Good' if health_grade == 'B' else 'Fair' if health_grade == 'C' else 'Poor'} performance"
        ]
        
        for i, insight in enumerate(insights):
            st.markdown(f"""
            <div style="background: rgba(0, 255, 136, 0.1); padding: 0.8rem; margin: 0.5rem 0; border-radius: 6px; border-left: 3px solid #00ff88;">
                <span style="color: #00ff88; font-weight: 700;">#{i+1}</span>
                <span style="color: white; margin-left: 0.5rem;">{insight}</span>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="background: rgba(255, 107, 107, 0.1); padding: 1rem; border-radius: 6px; border-left: 3px solid #ff6b6b;">
            <span style="color: #ff6b6b;">🤖 AI Intelligence System Offline</span><br>
            <span style="color: #fca5a5; font-size: 0.9rem;">Operating in manual mode with basic market state only.</span>
        </div>
        """, unsafe_allow_html=True)

# =========================== MAIN TERMINAL ===========================

def main_unified_terminal():
    """Main unified terminal function"""
    
    # Load unified snapshot
    try:
        with st.spinner("🧭 Loading unified terminal..."):
            snapshot = load_unified_snapshot()
            war_room_data = load_war_room_data()
            portfolio_data = load_portfolio_data()
            intelligence_data = load_intelligence_data()
    except Exception as e:
        st.error(f"❌ Critical Error Loading Data: {e}")
        st.info("Using fallback data...")
        snapshot = {
            'market': {'regime': 'Unknown', 'allowed_exposure': 50},
            'portfolio': {'total_exposure': 0, 'num_positions': 0, 'top_holdings': []},
            'strategies': {'active_count': 0, 'total_count': 16},
            'intelligence': {'status': 'error', 'conviction': 0.5},
            'risk': {'market_vol': 15, 'vol_regime': 'Normal'},
            'execution': {'recent_trades': 0, 'total_turnover': 0}
        }
        war_room_data = {}
        portfolio_data = {}
        intelligence_data = {}
    
    # Header
    st.markdown("""
    <div style="text-align: center; margin-bottom: 2rem;">
        <h1 style="color: #00ff88; font-size: 3rem; margin: 0;">🧭 NORTHSTAR UNIFIED TERMINAL</h1>
        <p style="color: #a0aec0; font-size: 1.2rem; margin: 0.5rem 0;">
            Hedge Fund Command Center • War Room + Portfolio + Intelligence
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Global Status Bar
    render_global_status_bar(snapshot)
    
    # Check data health
    health = check_data_health()
    if health['overall_grade'] != 'A':
        st.warning(f"⚠️ Data Health: {health['overall_grade']} grade - Snapshot age: {health['snapshot_age']:.1f} minutes")
    
    # Main Terminal Grid
    st.markdown('<div class="terminal-grid">', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1.5, 1])
    
    with col1:
        try:
            render_war_room(snapshot, war_room_data)
        except Exception as e:
            st.error(f"🟥 War Room Error: {e}")
            st.info("War Room temporarily unavailable")
    
    with col2:
        try:
            render_portfolio_command(snapshot, portfolio_data)
        except Exception as e:
            st.error(f"🟦 Portfolio Command Error: {e}")
            st.info("Portfolio Command temporarily unavailable")
    
    with col3:
        try:
            render_intelligence_organism(snapshot, intelligence_data)
        except Exception as e:
            st.error(f"🧠 Intelligence Organism Error: {e}")
            st.info("Intelligence Organism temporarily unavailable")
    
    st.markdown('</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main_unified_terminal()