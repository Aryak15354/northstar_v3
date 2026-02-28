#!/usr/bin/env python3
"""
🏛️ SIMPLE CONSTITUTIONAL COCKPIT - WORKING VERSION
Single Dashboard with 5 Locked Panels: Truth, State, and Integrity

This is a simplified, working version of the constitutional cockpit.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import os
import sys
import json
import warnings
warnings.filterwarnings('ignore')

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# =========================== STREAMLIT CONFIG ===========================

st.set_page_config(
    layout="wide", 
    page_title="🏛️ Northstar V3 - Constitutional Cockpit",
    initial_sidebar_state="collapsed"
)

# =========================== STYLING ===========================

st.markdown("""
<style>
    /* TARGETED WHITE SPACE ELIMINATION */
    
    /* Main containers - reasonable spacing */
    .main { 
        padding: 1rem !important; 
        margin: 0 !important;
        max-width: 100% !important;
    }
    .block-container { 
        padding: 1rem !important; 
        margin: 0 !important;
        max-width: 100% !important;
    }
    
    /* Hide Streamlit branding */
    #MainMenu, footer, header, .stDeployButton, .stToolbar { 
        visibility: hidden !important; 
    }
    
    /* Constitutional header */
    .constitutional-header {
        background: linear-gradient(90deg, #1e3a8a 0%, #1e40af 100%);
        color: white;
        padding: 0.5rem;
        text-align: center;
        font-weight: bold;
        margin-bottom: 1rem;
        border-radius: 4px;
    }
    
    /* Panel boxes */
    .panel-box {
        border: 1px solid #e5e7eb;
        border-radius: 4px;
        padding: 1rem;
        margin-bottom: 1rem;
        background: #fafafa;
        height: 100%;
    }
    
    /* Panel titles */
    .panel-title {
        font-size: 1.1rem;
        font-weight: bold;
        color: #374151;
        margin-bottom: 0.5rem;
        border-bottom: 2px solid #d1d5db;
        padding-bottom: 0.25rem;
    }
    
    /* Metric items */
    .metric-item {
        display: flex;
        justify-content: space-between;
        padding: 0.25rem 0;
        border-bottom: 1px solid #f3f4f6;
    }
    
    .metric-label {
        color: #6b7280;
        font-size: 0.875rem;
    }
    
    .metric-value {
        font-weight: bold;
        color: #374151;
        font-size: 0.875rem;
    }
    
    /* Status colors */
    .status-healthy { color: #059669; }
    .status-degraded { color: #d97706; }
    .status-critical { color: #dc2626; }
    .status-neutral { color: #6b7280; }
    
    /* Reduce gaps between columns */
    .stColumns {
        gap: 0.5rem !important;
    }
    
    /* Compact charts */
    .js-plotly-plot {
        margin-bottom: 0.5rem !important;
    }
    
    /* Portfolio headers */
    .portfolio-header {
        font-size: 1.1rem !important;
        margin: 1rem 0 0.5rem 0 !important;
        font-weight: bold;
    }
    
    /* Reduce vertical spacing between elements */
    .element-container {
        margin-bottom: 0.5rem !important;
    }
    
    /* Compact dataframes */
    .stDataFrame {
        margin-bottom: 0.5rem !important;
    }
    
    /* Compact metrics */
    .stMetric {
        margin-bottom: 0.25rem !important;
    }
</style>
""", unsafe_allow_html=True)

# =========================== DATA LOADING ===========================

@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_sample_data():
    """Load comprehensive sample data for the dashboard"""
    
    # Try to load real data first
    try:
        state_file = os.path.join(project_root, 'data/state/unified_state.json')
        if os.path.exists(state_file):
            with open(state_file, 'r') as f:
                state_data = json.load(f)
        else:
            state_data = {}
    except:
        state_data = {}
    
    # Generate time series data for charts
    dates = pd.date_range(start=datetime.now() - timedelta(days=30), end=datetime.now(), freq='D')
    
    # Generate comprehensive portfolio data with ALL holdings
    all_holdings = [
        {'symbol': 'RELIANCE', 'weight': 0.045, 'pnl_1d': 0.012, 'sector': 'Energy'},
        {'symbol': 'TCS', 'weight': 0.038, 'pnl_1d': -0.005, 'sector': 'Technology'},
        {'symbol': 'HDFC', 'weight': 0.035, 'pnl_1d': 0.008, 'sector': 'Financials'},
        {'symbol': 'INFY', 'weight': 0.032, 'pnl_1d': 0.015, 'sector': 'Technology'},
        {'symbol': 'ICICI', 'weight': 0.028, 'pnl_1d': -0.002, 'sector': 'Financials'},
        {'symbol': 'HDFCBANK', 'weight': 0.025, 'pnl_1d': 0.007, 'sector': 'Financials'},
        {'symbol': 'ITC', 'weight': 0.023, 'pnl_1d': -0.008, 'sector': 'Consumer'},
        {'symbol': 'KOTAKBANK', 'weight': 0.022, 'pnl_1d': 0.003, 'sector': 'Financials'},
        {'symbol': 'LT', 'weight': 0.021, 'pnl_1d': 0.011, 'sector': 'Industrials'},
        {'symbol': 'SBIN', 'weight': 0.020, 'pnl_1d': -0.004, 'sector': 'Financials'},
        {'symbol': 'BHARTIARTL', 'weight': 0.019, 'pnl_1d': 0.009, 'sector': 'Technology'},
        {'symbol': 'ASIANPAINT', 'weight': 0.018, 'pnl_1d': -0.006, 'sector': 'Materials'},
        {'symbol': 'MARUTI', 'weight': 0.017, 'pnl_1d': 0.014, 'sector': 'Consumer'},
        {'symbol': 'HCLTECH', 'weight': 0.016, 'pnl_1d': 0.002, 'sector': 'Technology'},
        {'symbol': 'AXISBANK', 'weight': 0.015, 'pnl_1d': -0.007, 'sector': 'Financials'},
        {'symbol': 'WIPRO', 'weight': 0.014, 'pnl_1d': 0.005, 'sector': 'Technology'},
        {'symbol': 'ULTRACEMCO', 'weight': 0.013, 'pnl_1d': 0.008, 'sector': 'Materials'},
        {'symbol': 'NESTLEIND', 'weight': 0.012, 'pnl_1d': -0.003, 'sector': 'Consumer'},
        {'symbol': 'TITAN', 'weight': 0.011, 'pnl_1d': 0.016, 'sector': 'Consumer'},
        {'symbol': 'BAJFINANCE', 'weight': 0.010, 'pnl_1d': -0.009, 'sector': 'Financials'},
        {'symbol': 'POWERGRID', 'weight': 0.009, 'pnl_1d': 0.004, 'sector': 'Utilities'},
        {'symbol': 'NTPC', 'weight': 0.008, 'pnl_1d': 0.007, 'sector': 'Utilities'},
        {'symbol': 'ONGC', 'weight': 0.007, 'pnl_1d': -0.011, 'sector': 'Energy'},
        {'symbol': 'TECHM', 'weight': 0.006, 'pnl_1d': 0.013, 'sector': 'Technology'},
        {'symbol': 'SUNPHARMA', 'weight': 0.005, 'pnl_1d': -0.001, 'sector': 'Healthcare'},
        {'symbol': 'DRREDDY', 'weight': 0.004, 'pnl_1d': 0.006, 'sector': 'Healthcare'},
        {'symbol': 'CIPLA', 'weight': 0.003, 'pnl_1d': -0.004, 'sector': 'Healthcare'},
        {'symbol': 'GRASIM', 'weight': 0.002, 'pnl_1d': 0.009, 'sector': 'Materials'},
        {'symbol': 'HINDALCO', 'weight': 0.001, 'pnl_1d': -0.007, 'sector': 'Materials'},
    ]
    
    # Generate individual stock performance data for each holding
    stock_performance = {}
    for holding in all_holdings:
        symbol = holding['symbol']
        # Generate 30-day performance data for each stock
        stock_returns = np.random.normal(0.001, 0.025, len(dates))  # Individual stock volatility
        stock_cumulative = (1 + pd.Series(stock_returns)).cumprod() - 1
        
        stock_performance[symbol] = {
            'dates': dates,
            'daily_returns': stock_returns,
            'cumulative_returns': stock_cumulative.values,
            'current_price': np.random.uniform(100, 3000),
            'volatility_30d': np.random.uniform(0.20, 0.45),
            'beta': np.random.uniform(0.7, 1.5),
            'rsi': np.random.uniform(30, 70),
            'sector': holding['sector']
        }
    
    # Create comprehensive data structure
    data = {
        'timestamp': datetime.now(),
        'system_state': {
            'system_status': state_data.get('system_status', 'healthy'),
            'organs_healthy': 8,
            'organs_total': 10,
            'current_regime': 'SUPPORTIVE',
            'regime_confidence': 0.85,
            'regime_duration_days': 15,
            'active_engine': 'trend',
            'engine_confidence': 0.78,
            'exposure_state': 'RISK_ON',
            'allowed_exposure': 0.65,
            'current_exposure': 0.62,
            'conviction_locked': True,
            'conviction_violations': 0,
            'system_uptime_days': 127,
            'last_restart': datetime.now() - timedelta(days=5),
            'memory_usage_pct': 0.34,
            'cpu_usage_pct': 0.12,
            'network_latency_ms': 15.2,
            'disk_usage_pct': 0.67,
            'active_connections': 24,
            'queue_depth': 3
        },
        'risk_state': {
            'emergency_brake_status': 'ARMED',
            'emergency_active': False,
            'current_drawdown': -0.03,
            'max_allowed_drawdown': -0.20,
            'peak_drawdown_30d': -0.05,
            'volatility_stress': 'low',
            'volatility_20d': 0.18,
            'volatility_5d': 0.22,
            'kill_switches_armed': 5,
            'kill_switches_total': 5,
            'var_95_1d': -0.025,
            'var_99_1d': -0.041,
            'correlation_breakdown_risk': 0.15,
            'liquidity_stress_score': 0.08,
            'tail_risk_score': 0.12,
            'sector_concentration_risk': 0.23,
            'leverage_ratio': 1.15,
            'margin_utilization': 0.34
        },
        'engine_state': {
            'trend_engine_active': True,
            'trend_engine_days_active': 15,
            'trend_holding_duration_avg': 12.5,
            'trend_win_rate_30d': 0.68,
            'trend_sharpe_30d': 1.24,
            'crisis_engine_active': False,
            'crisis_engine_days_active': 0,
            'crisis_convexity_score': 0.85,
            'crisis_bleed_rate': 0.002,
            'engine_conflicts': 0,
            'regime_engine_alignment': 0.92,
            'signal_strength': 0.76,
            'signal_decay_rate': 0.05,
            'position_turnover_7d': 0.15,
            'alpha_generation_rate': 0.08,
            'execution_slippage': 0.003,
            'market_impact': 0.001
        },
        'validation_state': {
            'last_walkforward_result': 'PASS',
            'walkforward_success_rate': 0.85,
            'walkforward_tests_total': 47,
            'walkforward_tests_passed': 40,
            'rules_hash_verified': True,
            'rules_hash': 'a1b2c3d4e5f6',
            'override_attempts_24h': 0,
            'override_attempts_total': 0,
            'data_integrity_score': 1.0,
            'backtest_oos_correlation': 0.78,
            'reality_check_score': 0.82,
            'statistical_significance': 0.95,
            'last_audit_date': datetime.now() - timedelta(days=2),
            'model_drift_score': 0.12,
            'feature_stability_score': 0.89,
            'data_integrity_layers': {
                'ingestion': True,
                'processing': True,
                'validation': True,
                'storage': True,
                'access': True
            }
        },
        'intelligence_state': {
            'regime_similarity_index': 67.5,
            'stress_clustering_index': 32.1,
            'false_calm_likelihood': 15.8,
            'behavioral_drift_index': 8.2,
            'market_microstructure_score': 74.3,
            'observer_healthy': True,
            'observer_violations': 0,
            'observer_suspended': False,
            'weekly_report_available': True,
            'intelligence_confidence': 0.82,
            'last_intelligence_update': datetime.now() - timedelta(hours=2),
            'narrative_coherence_score': 0.89,
            'prediction_accuracy_7d': 0.71,
            'sentiment_divergence_score': 23.4,
            'flow_anomaly_score': 18.7,
            'cross_asset_correlation_score': 45.2
        },
        'performance_data': {
            'dates': dates,
            'daily_returns': np.random.normal(0.001, 0.02, len(dates)),
            'cumulative_returns': None,  # Will be calculated
            'drawdown_series': None,  # Will be calculated
            'volatility_series': np.random.uniform(0.15, 0.25, len(dates)),
            'exposure_series': np.random.uniform(0.4, 0.8, len(dates)),
            'regime_series': np.random.choice(['SUPPORTIVE', 'HOSTILE', 'PANIC'], len(dates), p=[0.6, 0.3, 0.1])
        },
        'portfolio_data': {
            'total_positions': len(all_holdings),
            'long_positions': len([h for h in all_holdings if h['weight'] > 0]),
            'short_positions': 0,  # All positions are long in this example
            'sectors': {
                'Technology': sum(h['weight'] for h in all_holdings if h['sector'] == 'Technology'),
                'Financials': sum(h['weight'] for h in all_holdings if h['sector'] == 'Financials'),
                'Consumer': sum(h['weight'] for h in all_holdings if h['sector'] == 'Consumer'),
                'Healthcare': sum(h['weight'] for h in all_holdings if h['sector'] == 'Healthcare'),
                'Industrials': sum(h['weight'] for h in all_holdings if h['sector'] == 'Industrials'),
                'Energy': sum(h['weight'] for h in all_holdings if h['sector'] == 'Energy'),
                'Materials': sum(h['weight'] for h in all_holdings if h['sector'] == 'Materials'),
                'Utilities': sum(h['weight'] for h in all_holdings if h['sector'] == 'Utilities')
            },
            'all_holdings': all_holdings,
            'top_holdings': all_holdings[:10]  # Top 10 for summary
        },
        'stock_performance': stock_performance
    }
    
    # Calculate cumulative returns and drawdown
    daily_returns = data['performance_data']['daily_returns']
    cumulative_returns = (1 + pd.Series(daily_returns)).cumprod() - 1
    running_max = cumulative_returns.expanding().max()
    drawdown_series = (cumulative_returns - running_max)
    
    data['performance_data']['cumulative_returns'] = cumulative_returns.values
    data['performance_data']['drawdown_series'] = drawdown_series.values
    
    return data

# =========================== PANEL FUNCTIONS ===========================

def render_system_state_panel(data):
    """Render enhanced system state panel with comprehensive charts"""
    
    st.markdown('<div class="panel-box">', unsafe_allow_html=True)
    st.markdown('<div class="panel-title">📊 PANEL 1 — SYSTEM STATE</div>', unsafe_allow_html=True)
    st.markdown('<div class="metric-label">Question: "Is the system healthy and behaving as designed?"</div>', unsafe_allow_html=True)
    
    system = data['system_state']
    
    # Create three columns for comprehensive metrics and charts
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        # System Health Gauge
        organ_pct = (system['organs_healthy'] / system['organs_total']) * 100
        fig = go.Figure(go.Indicator(
            mode = "gauge+number",
            value = organ_pct,
            domain = {'x': [0, 1], 'y': [0, 1]},
            title = {'text': "System Health"},
            gauge = {
                'axis': {'range': [None, 100]},
                'bar': {'color': "#059669" if organ_pct >= 80 else "#d97706" if organ_pct >= 60 else "#dc2626"},
                'steps': [
                    {'range': [0, 60], 'color': "#fee2e2"},
                    {'range': [60, 80], 'color': "#fef3c7"},
                    {'range': [80, 100], 'color': "#d1fae5"}
                ],
                'threshold': {
                    'line': {'color': "red", 'width': 4},
                    'thickness': 0.75,
                    'value': 90
                }
            }
        ))
        fig.update_layout(height=250, margin=dict(l=20, r=20, t=40, b=20))
        st.plotly_chart(fig, use_container_width=True)
        
        # System Status Metrics
        status_class = f"status-{system['system_status']}" if system['system_status'] in ['healthy', 'degraded', 'critical'] else "status-neutral"
        st.markdown(f"""
        <div class="metric-item">
            <span class="metric-label">System Status:</span>
            <span class="metric-value {status_class}">{system['system_status'].upper()}</span>
        </div>
        <div class="metric-item">
            <span class="metric-label">Organs Healthy:</span>
            <span class="metric-value status-healthy">{system['organs_healthy']}/{system['organs_total']}</span>
        </div>
        <div class="metric-item">
            <span class="metric-label">System Uptime:</span>
            <span class="metric-value">{system['system_uptime_days']} days</span>
        </div>
        <div class="metric-item">
            <span class="metric-label">Active Connections:</span>
            <span class="metric-value">{system['active_connections']}</span>
        </div>
        <div class="metric-item">
            <span class="metric-label">Queue Depth:</span>
            <span class="metric-value">{system['queue_depth']}</span>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        # Resource Usage Chart
        resources = ['CPU', 'Memory', 'Disk', 'Network']
        usage_values = [
            system['cpu_usage_pct'] * 100,
            system['memory_usage_pct'] * 100,
            system['disk_usage_pct'] * 100,
            min(system['network_latency_ms'] / 100 * 100, 100)  # Scale network latency
        ]
        
        fig = go.Figure(data=go.Bar(
            x=resources,
            y=usage_values,
            marker_color=['#059669' if v < 50 else '#d97706' if v < 80 else '#dc2626' for v in usage_values]
        ))
        fig.update_layout(
            title="Resource Usage (%)",
            height=250,
            margin=dict(l=20, r=20, t=40, b=20),
            yaxis_title="Usage %"
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # Resource Metrics
        cpu_class = "status-healthy" if system['cpu_usage_pct'] < 0.5 else "status-degraded"
        memory_class = "status-healthy" if system['memory_usage_pct'] < 0.7 else "status-degraded"
        disk_class = "status-healthy" if system['disk_usage_pct'] < 0.8 else "status-degraded"
        
        st.markdown(f"""
        <div class="metric-item">
            <span class="metric-label">CPU Usage:</span>
            <span class="metric-value {cpu_class}">{system['cpu_usage_pct']:.1%}</span>
        </div>
        <div class="metric-item">
            <span class="metric-label">Memory Usage:</span>
            <span class="metric-value {memory_class}">{system['memory_usage_pct']:.1%}</span>
        </div>
        <div class="metric-item">
            <span class="metric-label">Disk Usage:</span>
            <span class="metric-value {disk_class}">{system['disk_usage_pct']:.1%}</span>
        </div>
        <div class="metric-item">
            <span class="metric-label">Network Latency:</span>
            <span class="metric-value">{system['network_latency_ms']:.1f}ms</span>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        # Regime and Engine Status Chart
        regime_data = {
            'Current Regime': system['current_regime'],
            'Regime Confidence': f"{system['regime_confidence']:.1%}",
            'Active Engine': system['active_engine'].title(),
            'Engine Confidence': f"{system['engine_confidence']:.1%}",
            'Exposure State': system['exposure_state']
        }
        
        # Confidence levels chart
        confidence_metrics = ['Regime Confidence', 'Engine Confidence']
        confidence_values = [system['regime_confidence'] * 100, system['engine_confidence'] * 100]
        
        fig = go.Figure(data=go.Bar(
            x=confidence_metrics,
            y=confidence_values,
            marker_color=['#059669', '#059669']
        ))
        fig.update_layout(
            title="Confidence Levels",
            height=250,
            margin=dict(l=20, r=20, t=40, b=20),
            yaxis_title="Confidence %"
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # Regime and Engine Metrics
        regime_class = "status-healthy" if system['current_regime'] == "SUPPORTIVE" else "status-neutral"
        engine_class = "status-healthy" if system['active_engine'] != "none" else "status-neutral"
        exposure_class = "status-healthy" if system['exposure_state'] == "RISK_ON" else "status-neutral"
        
        st.markdown(f"""
        <div class="metric-item">
            <span class="metric-label">Current Regime:</span>
            <span class="metric-value {regime_class}">{system['current_regime']}</span>
        </div>
        <div class="metric-item">
            <span class="metric-label">Regime Duration:</span>
            <span class="metric-value">{system['regime_duration_days']} days</span>
        </div>
        <div class="metric-item">
            <span class="metric-label">Active Engine:</span>
            <span class="metric-value {engine_class}">{system['active_engine'].title()}</span>
        </div>
        <div class="metric-item">
            <span class="metric-label">Exposure State:</span>
            <span class="metric-value {exposure_class}">{system['exposure_state']}</span>
        </div>
        <div class="metric-item">
            <span class="metric-label">Current/Allowed:</span>
            <span class="metric-value">{system['current_exposure']:.1%} / {system['allowed_exposure']:.1%}</span>
        </div>
        """, unsafe_allow_html=True)
    
    # Bottom row: Conviction Status and Additional Metrics
    col4, col5 = st.columns([1, 1])
    
    with col4:
        # Conviction Status
        conviction_class = "status-healthy" if system['conviction_locked'] else "status-critical"
        conviction_text = "LOCKED ✅" if system['conviction_locked'] else "UNLOCKED ❌"
        st.markdown(f"""
        <div class="metric-item">
            <span class="metric-label">Conviction Contract:</span>
            <span class="metric-value {conviction_class}">{conviction_text}</span>
        </div>
        <div class="metric-item">
            <span class="metric-label">Violations:</span>
            <span class="metric-value status-healthy">{system['conviction_violations']}</span>
        </div>
        """, unsafe_allow_html=True)
    
    with col5:
        # Last Restart Info
        restart_days_ago = (datetime.now() - system['last_restart']).days
        restart_class = "status-healthy" if restart_days_ago >= 1 else "status-neutral"
        st.markdown(f"""
        <div class="metric-item">
            <span class="metric-label">Last Restart:</span>
            <span class="metric-value {restart_class}">{restart_days_ago} days ago</span>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

def render_risk_panel(data):
    """Render enhanced risk authority panel with comprehensive risk charts"""
    
    st.markdown('<div class="panel-box">', unsafe_allow_html=True)
    st.markdown('<div class="panel-title">🛡️ PANEL 2 — RISK AUTHORITY</div>', unsafe_allow_html=True)
    st.markdown('<div class="metric-label">Question: "Who is in charge right now?"</div>', unsafe_allow_html=True)
    
    risk = data['risk_state']
    
    # Create three columns for comprehensive risk metrics and charts
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        # Risk Metrics Radar Chart
        risk_categories = ['VaR 95%', 'VaR 99%', 'Tail Risk', 'Correlation', 'Liquidity', 'Concentration']
        risk_values = [
            abs(risk['var_95_1d']) * 400,  # Scale for visibility
            abs(risk['var_99_1d']) * 250,
            risk['tail_risk_score'] * 100,
            risk['correlation_breakdown_risk'] * 100,
            risk['liquidity_stress_score'] * 100,
            risk['sector_concentration_risk'] * 100
        ]
        
        fig = go.Figure()
        fig.add_trace(go.Scatterpolar(
            r=risk_values,
            theta=risk_categories,
            fill='toself',
            name='Risk Profile',
            line_color='#dc2626'
        ))
        fig.update_layout(
            polar=dict(
                radialaxis=dict(
                    visible=True,
                    range=[0, 30]
                )),
            title="Risk Profile",
            height=250,
            margin=dict(l=20, r=20, t=40, b=20),
            showlegend=False
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # Emergency Brake Status
        brake_class = "status-healthy" if risk['emergency_brake_status'] == "ARMED" else "status-critical"
        st.markdown(f"""
        <div class="metric-item">
            <span class="metric-label">Emergency Brake:</span>
            <span class="metric-value {brake_class}">{risk['emergency_brake_status']}</span>
        </div>
        <div class="metric-item">
            <span class="metric-label">Emergency Active:</span>
            <span class="metric-value status-healthy">{'YES' if risk['emergency_active'] else 'NO'}</span>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        # Drawdown Analysis Chart
        drawdown_metrics = ['Current DD', 'Peak DD (30d)', 'Max Allowed']
        drawdown_values = [
            abs(risk['current_drawdown']) * 100,
            abs(risk['peak_drawdown_30d']) * 100,
            abs(risk['max_allowed_drawdown']) * 100
        ]
        
        fig = go.Figure(data=go.Bar(
            x=drawdown_metrics,
            y=drawdown_values,
            marker_color=['#dc2626' if drawdown_values[0] > 5 else '#d97706' if drawdown_values[0] > 2 else '#059669',
                         '#d97706', '#6b7280']
        ))
        fig.update_layout(
            title="Drawdown Analysis (%)",
            height=200,
            margin=dict(l=5, r=5, t=15, b=5),
            yaxis_title="Drawdown %"
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # Drawdown Metrics
        drawdown_ratio = abs(risk['current_drawdown'] / risk['max_allowed_drawdown'])
        drawdown_class = "status-critical" if drawdown_ratio >= 1.0 else "status-degraded" if drawdown_ratio >= 0.5 else "status-healthy"
        
        st.markdown(f"""
        <div class="metric-item">
            <span class="metric-label">Current Drawdown:</span>
            <span class="metric-value {drawdown_class}">{risk['current_drawdown']:.1%}</span>
        </div>
        <div class="metric-item">
            <span class="metric-label">Covenant Usage:</span>
            <span class="metric-value {drawdown_class}">{drawdown_ratio:.1%}</span>
        </div>
        <div class="metric-item">
            <span class="metric-label">Peak DD (30d):</span>
            <span class="metric-value">{risk['peak_drawdown_30d']:.1%}</span>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        # Volatility and Stress Analysis
        vol_metrics = ['Vol (5d)', 'Vol (20d)', 'Stress Level']
        vol_values = [
            risk['volatility_5d'] * 100,
            risk['volatility_20d'] * 100,
            {'low': 15, 'medium': 25, 'high': 35, 'extreme': 50}.get(risk['volatility_stress'], 20)
        ]
        
        fig = go.Figure(data=go.Bar(
            x=vol_metrics,
            y=vol_values,
            marker_color=['#d97706', '#059669', 
                         {'low': '#059669', 'medium': '#d97706', 'high': '#dc2626', 'extreme': '#7c2d12'}.get(risk['volatility_stress'], '#6b7280')]
        ))
        fig.update_layout(
            title="Volatility Analysis (%)",
            height=200,
            margin=dict(l=5, r=5, t=15, b=5),
            yaxis_title="Volatility %"
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # Volatility Metrics
        stress_class = {
            'low': 'status-healthy',
            'medium': 'status-neutral',
            'high': 'status-degraded',
            'extreme': 'status-critical'
        }.get(risk['volatility_stress'], 'status-neutral')
        
        st.markdown(f"""
        <div class="metric-item">
            <span class="metric-label">Volatility Stress:</span>
            <span class="metric-value {stress_class}">{risk['volatility_stress'].title()}</span>
        </div>
        <div class="metric-item">
            <span class="metric-label">Vol (20d):</span>
            <span class="metric-value">{risk['volatility_20d']:.1%}</span>
        </div>
        <div class="metric-item">
            <span class="metric-label">Vol (5d):</span>
            <span class="metric-value">{risk['volatility_5d']:.1%}</span>
        </div>
        """, unsafe_allow_html=True)
    
    # Bottom row: Additional Risk Metrics
    col4, col5, col6 = st.columns([1, 1, 1])
    
    with col4:
        # Kill Switches
        switches_class = "status-healthy" if risk['kill_switches_armed'] == risk['kill_switches_total'] else "status-degraded"
        st.markdown(f"""
        <div class="metric-item">
            <span class="metric-label">Kill Switches:</span>
            <span class="metric-value {switches_class}">{risk['kill_switches_armed']}/{risk['kill_switches_total']} Armed</span>
        </div>
        <div class="metric-item">
            <span class="metric-label">Leverage Ratio:</span>
            <span class="metric-value">{risk['leverage_ratio']:.2f}x</span>
        </div>
        """, unsafe_allow_html=True)
    
    with col5:
        # VaR Metrics
        st.markdown(f"""
        <div class="metric-item">
            <span class="metric-label">VaR 95% (1d):</span>
            <span class="metric-value">{risk['var_95_1d']:.1%}</span>
        </div>
        <div class="metric-item">
            <span class="metric-label">VaR 99% (1d):</span>
            <span class="metric-value">{risk['var_99_1d']:.1%}</span>
        </div>
        """, unsafe_allow_html=True)
    
    with col6:
        # Additional Risk Metrics
        st.markdown(f"""
        <div class="metric-item">
            <span class="metric-label">Margin Utilization:</span>
            <span class="metric-value">{risk['margin_utilization']:.1%}</span>
        </div>
        <div class="metric-item">
            <span class="metric-label">Concentration Risk:</span>
            <span class="metric-value">{risk['sector_concentration_risk']:.1%}</span>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

def render_engine_panel(data):
    """Render enhanced engine behavior panel with comprehensive performance charts"""
    
    st.markdown('<div class="panel-box">', unsafe_allow_html=True)
    st.markdown('<div class="panel-title">⚙️ PANEL 3 — ENGINE BEHAVIOR</div>', unsafe_allow_html=True)
    st.markdown('<div class="metric-label">Question: "Are the engines behaving like they promised?"</div>', unsafe_allow_html=True)
    
    engine = data['engine_state']
    perf_data = data['performance_data']
    
    # Top row: Performance Charts (3 columns)
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        # Cumulative Returns Chart
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=perf_data['dates'],
            y=perf_data['cumulative_returns'] * 100,
            mode='lines',
            name='Cumulative Return',
            line=dict(color='#059669', width=3),
            fill='tonexty'
        ))
        fig.update_layout(
            title="30-Day Performance",
            height=250,
            margin=dict(l=5, r=5, t=15, b=5),
            yaxis_title="Return (%)",
            showlegend=False
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Drawdown Chart
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=perf_data['dates'],
            y=perf_data['drawdown_series'] * 100,
            mode='lines',
            fill='tonexty',
            name='Drawdown',
            line=dict(color='#dc2626', width=2),
            fillcolor='rgba(220, 38, 38, 0.3)'
        ))
        fig.update_layout(
            title="Drawdown Profile",
            height=250,
            margin=dict(l=5, r=5, t=15, b=5),
            yaxis_title="Drawdown (%)",
            showlegend=False
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col3:
        # Volatility and Exposure Chart
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        
        fig.add_trace(
            go.Scatter(x=perf_data['dates'], y=perf_data['volatility_series'] * 100,
                      name="Volatility", line=dict(color='#d97706')),
            secondary_y=False,
        )
        
        fig.add_trace(
            go.Scatter(x=perf_data['dates'], y=perf_data['exposure_series'] * 100,
                      name="Exposure", line=dict(color='#059669')),
            secondary_y=True,
        )
        
        fig.update_xaxes(title_text="Date")
        fig.update_yaxes(title_text="Volatility (%)", secondary_y=False)
        fig.update_yaxes(title_text="Exposure (%)", secondary_y=True)
        fig.update_layout(title="Volatility vs Exposure", height=250, margin=dict(l=5, r=5, t=15, b=5))
        
        st.plotly_chart(fig, use_container_width=True)
    
    # Middle row: Engine Status and Metrics (3 columns)
    col4, col5, col6 = st.columns([1, 1, 1])
    
    with col4:
        # Trend Engine Metrics
        trend_class = "status-healthy" if engine['trend_engine_active'] else "status-neutral"
        trend_status = "Active" if engine['trend_engine_active'] else "Inactive"
        
        st.markdown(f"""
        <div class="metric-item">
            <span class="metric-label">Trend Engine:</span>
            <span class="metric-value {trend_class}">{trend_status}</span>
        </div>
        <div class="metric-item">
            <span class="metric-label">Days Active:</span>
            <span class="metric-value">{engine['trend_engine_days_active']}</span>
        </div>
        <div class="metric-item">
            <span class="metric-label">Win Rate (30d):</span>
            <span class="metric-value status-healthy">{engine['trend_win_rate_30d']:.1%}</span>
        </div>
        <div class="metric-item">
            <span class="metric-label">Sharpe (30d):</span>
            <span class="metric-value status-healthy">{engine['trend_sharpe_30d']:.2f}</span>
        </div>
        <div class="metric-item">
            <span class="metric-label">Avg Holding:</span>
            <span class="metric-value">{engine['trend_holding_duration_avg']:.1f} days</span>
        </div>
        """, unsafe_allow_html=True)
    
    with col5:
        # Crisis Engine Metrics
        crisis_class = "status-healthy" if engine['crisis_engine_active'] else "status-neutral"
        crisis_status = "Active" if engine['crisis_engine_active'] else "Armed"
        
        st.markdown(f"""
        <div class="metric-item">
            <span class="metric-label">Crisis Engine:</span>
            <span class="metric-value {crisis_class}">{crisis_status}</span>
        </div>
        <div class="metric-item">
            <span class="metric-label">Days Active:</span>
            <span class="metric-value">{engine['crisis_engine_days_active']}</span>
        </div>
        <div class="metric-item">
            <span class="metric-label">Convexity Score:</span>
            <span class="metric-value status-healthy">{engine['crisis_convexity_score']:.1%}</span>
        </div>
        <div class="metric-item">
            <span class="metric-label">Bleed Rate:</span>
            <span class="metric-value status-healthy">{engine['crisis_bleed_rate']:.1%}/day</span>
        </div>
        """, unsafe_allow_html=True)
    
    with col6:
        # Engine Coordination Metrics
        conflicts_class = "status-healthy" if engine['engine_conflicts'] == 0 else "status-critical"
        
        st.markdown(f"""
        <div class="metric-item">
            <span class="metric-label">Engine Conflicts:</span>
            <span class="metric-value {conflicts_class}">{engine['engine_conflicts']}</span>
        </div>
        <div class="metric-item">
            <span class="metric-label">Regime Alignment:</span>
            <span class="metric-value status-healthy">{engine['regime_engine_alignment']:.1%}</span>
        </div>
        <div class="metric-item">
            <span class="metric-label">Signal Strength:</span>
            <span class="metric-value status-healthy">{engine['signal_strength']:.1%}</span>
        </div>
        <div class="metric-item">
            <span class="metric-label">Signal Decay:</span>
            <span class="metric-value">{engine['signal_decay_rate']:.1%}/day</span>
        </div>
        """, unsafe_allow_html=True)
    
    # Bottom row: Additional Performance Metrics (3 columns)
    col7, col8, col9 = st.columns([1, 1, 1])
    
    with col7:
        st.markdown(f"""
        <div class="metric-item">
            <span class="metric-label">Position Turnover (7d):</span>
            <span class="metric-value">{engine['position_turnover_7d']:.1%}</span>
        </div>
        <div class="metric-item">
            <span class="metric-label">Alpha Generation:</span>
            <span class="metric-value status-healthy">{engine['alpha_generation_rate']:.1%}</span>
        </div>
        """, unsafe_allow_html=True)
    
    with col8:
        st.markdown(f"""
        <div class="metric-item">
            <span class="metric-label">Execution Slippage:</span>
            <span class="metric-value">{engine['execution_slippage']:.1%}</span>
        </div>
        <div class="metric-item">
            <span class="metric-label">Market Impact:</span>
            <span class="metric-value">{engine['market_impact']:.1%}</span>
        </div>
        """, unsafe_allow_html=True)
    
    with col9:
        # Engine Performance Gauge
        performance_score = (engine['trend_win_rate_30d'] + engine['regime_engine_alignment']) / 2 * 100
        
        fig = go.Figure(go.Indicator(
            mode = "gauge+number",
            value = performance_score,
            domain = {'x': [0, 1], 'y': [0, 1]},
            title = {'text': "Engine Performance"},
            gauge = {
                'axis': {'range': [None, 100]},
                'bar': {'color': "#059669" if performance_score >= 70 else "#d97706" if performance_score >= 50 else "#dc2626"},
                'steps': [
                    {'range': [0, 50], 'color': "#fee2e2"},
                    {'range': [50, 70], 'color': "#fef3c7"},
                    {'range': [70, 100], 'color': "#d1fae5"}
                ],
                'threshold': {
                    'line': {'color': "red", 'width': 4},
                    'thickness': 0.75,
                    'value': 80
                }
            }
        ))
        fig.update_layout(height=200, margin=dict(l=20, r=20, t=40, b=20))
        st.plotly_chart(fig, use_container_width=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

def render_validation_panel(data):
    """Render enhanced validation & truth panel with comprehensive validation charts"""
    
    st.markdown('<div class="panel-box">', unsafe_allow_html=True)
    st.markdown('<div class="panel-title">✅ PANEL 4 — VALIDATION & TRUTH</div>', unsafe_allow_html=True)
    st.markdown('<div class="metric-label">Question: "Is this system still honest?"</div>', unsafe_allow_html=True)
    
    validation = data['validation_state']
    
    # Top row: Validation Visualizations (3 columns)
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        # Walk-Forward Test Results Pie Chart
        test_results = ['Passed', 'Failed']
        test_counts = [validation['walkforward_tests_passed'], 
                      validation['walkforward_tests_total'] - validation['walkforward_tests_passed']]
        
        fig = go.Figure(data=[go.Pie(
            labels=test_results,
            values=test_counts,
            hole=0.4,
            marker_colors=['#059669', '#dc2626'],
            textinfo='label+percent+value'
        )])
        fig.update_layout(
            title="Walk-Forward Test Results",
            height=250,
            margin=dict(l=5, r=5, t=15, b=5),
            showlegend=True
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Validation Quality Metrics Bar Chart
        quality_metrics = ['Success Rate', 'Data Integrity', 'Reality Check', 'Statistical Sig']
        quality_values = [
            validation['walkforward_success_rate'] * 100,
            validation['data_integrity_score'] * 100,
            validation['reality_check_score'] * 100,
            validation['statistical_significance'] * 100
        ]
        
        fig = go.Figure(data=go.Bar(
            x=quality_metrics,
            y=quality_values,
            marker_color=['#059669' if v >= 80 else '#d97706' if v >= 60 else '#dc2626' for v in quality_values]
        ))
        fig.update_layout(
            title="Validation Quality Metrics",
            height=250,
            margin=dict(l=5, r=5, t=15, b=5),
            yaxis_title="Score (%)",
            xaxis_tickangle=-45
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col3:
        # Data Integrity Layers Heatmap
        integrity_layers = list(validation['data_integrity_layers'].keys())
        integrity_status = [[1 if validation['data_integrity_layers'][layer] else 0] for layer in integrity_layers]
        
        fig = go.Figure(data=go.Heatmap(
            z=integrity_status,
            y=integrity_layers,
            x=['Status'],
            colorscale=[[0, '#dc2626'], [1, '#059669']],
            showscale=False,
            text=[['✅' if status[0] else '❌'] for status in integrity_status],
            texttemplate="%{text}",
            textfont={"size": 16},
            hoverongaps=False
        ))
        
        fig.update_layout(
            title="Data Integrity Layers",
            height=250,
            margin=dict(l=5, r=5, t=15, b=5)
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # Middle row: Validation Status and Metrics (3 columns)
    col4, col5, col6 = st.columns([1, 1, 1])
    
    with col4:
        # Walk-Forward Results
        result_class = {
            'PASS': 'status-healthy',
            'FAIL': 'status-critical',
            'PENDING': 'status-neutral'
        }.get(validation['last_walkforward_result'], 'status-neutral')
        
        st.markdown(f"""
        <div class="metric-item">
            <span class="metric-label">Last Walk-Forward:</span>
            <span class="metric-value {result_class}">{validation['last_walkforward_result']}</span>
        </div>
        <div class="metric-item">
            <span class="metric-label">Success Rate:</span>
            <span class="metric-value status-healthy">{validation['walkforward_success_rate']:.1%}</span>
        </div>
        <div class="metric-item">
            <span class="metric-label">Tests Passed:</span>
            <span class="metric-value">{validation['walkforward_tests_passed']}/{validation['walkforward_tests_total']}</span>
        </div>
        <div class="metric-item">
            <span class="metric-label">Model Drift:</span>
            <span class="metric-value">{validation['model_drift_score']:.1%}</span>
        </div>
        """, unsafe_allow_html=True)
    
    with col5:
        # Rules Integrity and Override Attempts
        hash_class = "status-healthy" if validation['rules_hash_verified'] else "status-critical"
        hash_status = "Verified ✅" if validation['rules_hash_verified'] else "CORRUPTED ❌"
        attempts_class = "status-healthy" if validation['override_attempts_24h'] == 0 else "status-critical"
        
        st.markdown(f"""
        <div class="metric-item">
            <span class="metric-label">Rules Hash:</span>
            <span class="metric-value {hash_class}">{hash_status}</span>
        </div>
        <div class="metric-item">
            <span class="metric-label">Hash Value:</span>
            <span class="metric-value" style="font-family: monospace; font-size: 0.8rem;">{validation['rules_hash']}</span>
        </div>
        <div class="metric-item">
            <span class="metric-label">Override Attempts (24h):</span>
            <span class="metric-value {attempts_class}">{validation['override_attempts_24h']}</span>
        </div>
        <div class="metric-item">
            <span class="metric-label">Total Override Attempts:</span>
            <span class="metric-value {attempts_class}">{validation['override_attempts_total']}</span>
        </div>
        """, unsafe_allow_html=True)
    
    with col6:
        # Reality Check and Statistical Metrics
        oos_class = "status-healthy" if validation['backtest_oos_correlation'] >= 0.7 else "status-degraded"
        reality_class = "status-healthy" if validation['reality_check_score'] >= 0.8 else "status-degraded"
        significance_class = "status-healthy" if validation['statistical_significance'] >= 0.95 else "status-degraded"
        
        st.markdown(f"""
        <div class="metric-item">
            <span class="metric-label">Backtest-OOS Correlation:</span>
            <span class="metric-value {oos_class}">{validation['backtest_oos_correlation']:.1%}</span>
        </div>
        <div class="metric-item">
            <span class="metric-label">Reality Check Score:</span>
            <span class="metric-value {reality_class}">{validation['reality_check_score']:.1%}</span>
        </div>
        <div class="metric-item">
            <span class="metric-label">Statistical Significance:</span>
            <span class="metric-value {significance_class}">{validation['statistical_significance']:.1%}</span>
        </div>
        <div class="metric-item">
            <span class="metric-label">Feature Stability:</span>
            <span class="metric-value">{validation['feature_stability_score']:.1%}</span>
        </div>
        """, unsafe_allow_html=True)
    
    # Bottom row: Data Integrity and Audit Status (2 columns)
    col7, col8 = st.columns([1, 1])
    
    with col7:
        # Data Integrity Score
        integrity_class = "status-healthy" if validation['data_integrity_score'] >= 0.95 else "status-degraded"
        st.markdown(f"""
        <div class="metric-item">
            <span class="metric-label">Data Integrity:</span>
            <span class="metric-value {integrity_class}">{validation['data_integrity_score']:.1%}</span>
        </div>
        """, unsafe_allow_html=True)
        
        # Last Audit
        audit_days_ago = (datetime.now() - validation['last_audit_date']).days
        audit_class = "status-healthy" if audit_days_ago <= 7 else "status-degraded"
        st.markdown(f"""
        <div class="metric-item">
            <span class="metric-label">Last Audit:</span>
            <span class="metric-value {audit_class}">{audit_days_ago} days ago</span>
        </div>
        """, unsafe_allow_html=True)
    
    with col8:
        # Validation Health Gauge
        validation_health_score = (
            validation['walkforward_success_rate'] * 0.3 +
            validation['data_integrity_score'] * 0.3 +
            validation['reality_check_score'] * 0.2 +
            validation['statistical_significance'] * 0.2
        ) * 100
        
        fig = go.Figure(go.Indicator(
            mode = "gauge+number",
            value = validation_health_score,
            domain = {'x': [0, 1], 'y': [0, 1]},
            title = {'text': "Validation Health"},
            gauge = {
                'axis': {'range': [None, 100]},
                'bar': {'color': "#059669" if validation_health_score >= 80 else "#d97706" if validation_health_score >= 60 else "#dc2626"},
                'steps': [
                    {'range': [0, 60], 'color': "#fee2e2"},
                    {'range': [60, 80], 'color': "#fef3c7"},
                    {'range': [80, 100], 'color': "#d1fae5"}
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
    
    st.markdown('</div>', unsafe_allow_html=True)

def render_intelligence_panel(data):
    """Render enhanced intelligence observer panel with comprehensive intelligence charts"""
    
    st.markdown('<div class="panel-box">', unsafe_allow_html=True)
    st.markdown('<div class="panel-title">🧠 PANEL 5 — INTELLIGENCE OBSERVER</div>', unsafe_allow_html=True)
    st.markdown('<div class="metric-label">Question: "What should I understand — not act on?"</div>', unsafe_allow_html=True)
    
    intelligence = data['intelligence_state']
    
    # Top row: Intelligence Visualizations (3 columns)
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        # Intelligence Indices Radar Chart
        categories = ['Regime Similarity', 'Stress Clustering', 'False Calm', 'Behavioral Drift', 'Microstructure', 'Sentiment Div']
        values = [
            intelligence['regime_similarity_index'],
            intelligence['stress_clustering_index'],
            intelligence['false_calm_likelihood'],
            intelligence['behavioral_drift_index'],
            intelligence['market_microstructure_score'],
            intelligence['sentiment_divergence_score']
        ]
        
        fig = go.Figure()
        fig.add_trace(go.Scatterpolar(
            r=values,
            theta=categories,
            fill='toself',
            name='Intelligence Indices',
            line_color='#6366f1'
        ))
        fig.update_layout(
            polar=dict(
                radialaxis=dict(
                    visible=True,
                    range=[0, 100]
                )),
            title="Intelligence Profile",
            height=250,
            margin=dict(l=5, r=5, t=15, b=5),
            showlegend=False
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Intelligence Confidence and Health Metrics
        confidence_metrics = ['Intelligence Confidence', 'Narrative Coherence', 'Prediction Accuracy']
        confidence_values = [
            intelligence['intelligence_confidence'] * 100,
            intelligence['narrative_coherence_score'] * 100,
            intelligence['prediction_accuracy_7d'] * 100
        ]
        
        fig = go.Figure(data=go.Bar(
            x=confidence_metrics,
            y=confidence_values,
            marker_color=['#059669', '#059669', '#d97706']
        ))
        fig.update_layout(
            title="Intelligence Quality Metrics",
            height=250,
            margin=dict(l=5, r=5, t=15, b=5),
            yaxis_title="Score (%)",
            xaxis_tickangle=-45
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col3:
        # Market Intelligence Heatmap
        intelligence_matrix = [
            [intelligence['regime_similarity_index'], intelligence['stress_clustering_index']],
            [intelligence['false_calm_likelihood'], intelligence['behavioral_drift_index']],
            [intelligence['sentiment_divergence_score'], intelligence['flow_anomaly_score']]
        ]
        
        fig = go.Figure(data=go.Heatmap(
            z=intelligence_matrix,
            x=['Primary', 'Secondary'],
            y=['Regime', 'Stress', 'Flow'],
            colorscale='Viridis',
            text=intelligence_matrix,
            texttemplate="%{text:.1f}",
            textfont={"size": 10},
            hoverongaps=False
        ))
        
        fig.update_layout(
            title="Intelligence Heatmap",
            height=250,
            margin=dict(l=5, r=5, t=15, b=5)
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # Middle row: Observer Status and Detailed Metrics (3 columns)
    col4, col5, col6 = st.columns([1, 1, 1])
    
    with col4:
        # Observer Health and Status
        health_class = "status-healthy" if intelligence['observer_healthy'] else "status-critical"
        health_status = "Healthy" if intelligence['observer_healthy'] else "Degraded"
        suspended_class = "status-healthy" if not intelligence['observer_suspended'] else "status-critical"
        suspended_status = "Active" if not intelligence['observer_suspended'] else "Suspended"
        
        st.markdown(f"""
        <div class="metric-item">
            <span class="metric-label">Observer Status:</span>
            <span class="metric-value {health_class}">{health_status}</span>
        </div>
        <div class="metric-item">
            <span class="metric-label">Observer State:</span>
            <span class="metric-value {suspended_class}">{suspended_status}</span>
        </div>
        <div class="metric-item">
            <span class="metric-label">Authority Violations:</span>
            <span class="metric-value status-healthy">{intelligence['observer_violations']}</span>
        </div>
        <div class="metric-item">
            <span class="metric-label">Intelligence Confidence:</span>
            <span class="metric-value status-healthy">{intelligence['intelligence_confidence']:.1%}</span>
        </div>
        """, unsafe_allow_html=True)
    
    with col5:
        # Core Intelligence Scores
        st.markdown(f"""
        <div class="metric-item">
            <span class="metric-label">Regime Similarity:</span>
            <span class="metric-value status-neutral">{intelligence['regime_similarity_index']:.1f}/100</span>
        </div>
        <div class="metric-item">
            <span class="metric-label">Stress Clustering:</span>
            <span class="metric-value status-neutral">{intelligence['stress_clustering_index']:.1f}/100</span>
        </div>
        <div class="metric-item">
            <span class="metric-label">False Calm Likelihood:</span>
            <span class="metric-value status-neutral">{intelligence['false_calm_likelihood']:.1f}/100</span>
        </div>
        <div class="metric-item">
            <span class="metric-label">Behavioral Drift:</span>
            <span class="metric-value status-neutral">{intelligence['behavioral_drift_index']:.1f}/100</span>
        </div>
        """, unsafe_allow_html=True)
    
    with col6:
        # Advanced Intelligence Metrics
        st.markdown(f"""
        <div class="metric-item">
            <span class="metric-label">Microstructure Score:</span>
            <span class="metric-value status-neutral">{intelligence['market_microstructure_score']:.1f}/100</span>
        </div>
        <div class="metric-item">
            <span class="metric-label">Sentiment Divergence:</span>
            <span class="metric-value status-neutral">{intelligence['sentiment_divergence_score']:.1f}/100</span>
        </div>
        <div class="metric-item">
            <span class="metric-label">Flow Anomaly:</span>
            <span class="metric-value status-neutral">{intelligence['flow_anomaly_score']:.1f}/100</span>
        </div>
        <div class="metric-item">
            <span class="metric-label">Cross-Asset Correlation:</span>
            <span class="metric-value status-neutral">{intelligence['cross_asset_correlation_score']:.1f}/100</span>
        </div>
        """, unsafe_allow_html=True)
    
    # Bottom row: Prediction and Report Status (2 columns)
    col7, col8 = st.columns([1, 1])
    
    with col7:
        # Prediction Accuracy and Narrative Coherence
        st.markdown(f"""
        <div class="metric-item">
            <span class="metric-label">Prediction Accuracy (7d):</span>
            <span class="metric-value status-neutral">{intelligence['prediction_accuracy_7d']:.1%}</span>
        </div>
        <div class="metric-item">
            <span class="metric-label">Narrative Coherence:</span>
            <span class="metric-value status-neutral">{intelligence['narrative_coherence_score']:.1%}</span>
        </div>
        """, unsafe_allow_html=True)
        
        # Weekly Report Status
        report_class = "status-healthy" if intelligence['weekly_report_available'] else "status-neutral"
        report_status = "Available" if intelligence['weekly_report_available'] else "Pending"
        st.markdown(f"""
        <div class="metric-item">
            <span class="metric-label">Weekly Report:</span>
            <span class="metric-value {report_class}">{report_status}</span>
        </div>
        """, unsafe_allow_html=True)
    
    with col8:
        # Update Status and Timing
        update_hours_ago = (datetime.now() - intelligence['last_intelligence_update']).total_seconds() / 3600
        update_class = "status-healthy" if update_hours_ago <= 6 else "status-degraded"
        
        st.markdown(f"""
        <div class="metric-item">
            <span class="metric-label">Last Update:</span>
            <span class="metric-value {update_class}">{update_hours_ago:.1f} hours ago</span>
        </div>
        """, unsafe_allow_html=True)
        
        # Intelligence Gauge
        overall_intelligence_score = (
            intelligence['intelligence_confidence'] * 0.3 +
            intelligence['narrative_coherence_score'] * 0.3 +
            intelligence['prediction_accuracy_7d'] * 0.4
        ) * 100
        
        fig = go.Figure(go.Indicator(
            mode = "gauge+number",
            value = overall_intelligence_score,
            domain = {'x': [0, 1], 'y': [0, 1]},
            title = {'text': "Intelligence Quality"},
            gauge = {
                'axis': {'range': [None, 100]},
                'bar': {'color': "#6366f1"},
                'steps': [
                    {'range': [0, 50], 'color': "#fee2e2"},
                    {'range': [50, 75], 'color': "#fef3c7"},
                    {'range': [75, 100], 'color': "#e0e7ff"}
                ],
                'threshold': {
                    'line': {'color': "blue", 'width': 4},
                    'thickness': 0.75,
                    'value': 80
                }
            }
        ))
        fig.update_layout(height=200, margin=dict(l=20, r=20, t=40, b=20))
        st.plotly_chart(fig, use_container_width=True)
    
    # Constitutional Reminder
    st.markdown("""
    <div style="margin-top: 1rem; padding: 0.5rem; background: #f0f9ff; border: 1px solid #bae6fd; border-radius: 4px; font-size: 0.8rem; color: #0c4a6e;">
        <strong>Constitutional Reminder:</strong> Intelligence exists to understand, not to act.
        These metrics provide context and awareness without suggesting any trading decisions.
        <br><strong>Observer makes you wiser, not braver.</strong>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

# =========================== MAIN APP ===========================

def render_portfolio_overview(data):
    """Render comprehensive portfolio overview with ALL holdings and individual stock charts"""
    
    portfolio = data['portfolio_data']
    stock_performance = data['stock_performance']
    
    st.markdown("## 📈 COMPREHENSIVE PORTFOLIO ANALYSIS")
    
    # Portfolio Summary (4 columns, compact)
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Positions", portfolio['total_positions'])
    with col2:
        st.metric("Long Positions", portfolio['long_positions'])
    with col3:
        st.metric("Short Positions", portfolio['short_positions'])
    with col4:
        net_exposure = (portfolio['long_positions'] - portfolio['short_positions']) / portfolio['total_positions']
        st.metric("Net Exposure", f"{net_exposure:.1%}")
    
    # Top row: Sector Analysis and Portfolio Composition (compact)
    col5, col6, col7 = st.columns([1, 1, 1])
    
    with col5:
        # Sector Allocation Pie Chart
        sectors = list(portfolio['sectors'].keys())
        weights = list(portfolio['sectors'].values())
        
        fig = go.Figure(data=[go.Pie(
            labels=sectors,
            values=weights,
            hole=0.3,
            textinfo='label+percent',
            textposition='outside'
        )])
        fig.update_layout(
            title="Sector Allocation",
            height=300,
            margin=dict(l=5, r=5, t=15, b=5)
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col6:
        # Top 10 Holdings Bar Chart
        top_10 = portfolio['all_holdings'][:10]
        symbols = [h['symbol'] for h in top_10]
        weights = [h['weight'] * 100 for h in top_10]
        colors = ['#059669' if h['pnl_1d'] > 0 else '#dc2626' for h in top_10]
        
        fig = go.Figure(data=go.Bar(
            x=weights,
            y=symbols,
            orientation='h',
            marker_color=colors
        ))
        fig.update_layout(
            title="Top 10 Holdings by Weight",
            height=300,
            margin=dict(l=5, r=5, t=15, b=5),
            xaxis_title="Weight (%)"
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col7:
        # Portfolio Risk Metrics
        portfolio_vol = np.mean([stock_performance[h['symbol']]['volatility_30d'] for h in portfolio['all_holdings']])
        portfolio_beta = np.mean([stock_performance[h['symbol']]['beta'] for h in portfolio['all_holdings']])
        
        risk_metrics = ['Portfolio Vol', 'Portfolio Beta', 'Concentration', 'Diversification']
        risk_values = [
            portfolio_vol * 100,
            portfolio_beta * 50,  # Scale for visualization
            max(weights) * 2,  # Concentration risk
            len(set(h['sector'] for h in portfolio['all_holdings'])) * 10  # Diversification score
        ]
        
        fig = go.Figure(data=go.Bar(
            x=risk_metrics,
            y=risk_values,
            marker_color=['#d97706', '#059669', '#dc2626', '#059669']
        ))
        fig.update_layout(
            title="Portfolio Risk Profile",
            height=300,
            margin=dict(l=5, r=5, t=15, b=5),
            yaxis_title="Risk Score"
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # COMPREHENSIVE HOLDINGS TABLE WITH INDIVIDUAL STOCK CHARTS
    st.markdown("## 📊 ALL HOLDINGS WITH INDIVIDUAL PERFORMANCE CHARTS")
    
    # Create holdings table with performance data
    holdings_data = []
    for holding in portfolio['all_holdings']:
        symbol = holding['symbol']
        perf = stock_performance[symbol]
        
        holdings_data.append({
            'Symbol': symbol,
            'Sector': holding['sector'],
            'Weight': f"{holding['weight']:.1%}",
            'P&L (1d)': f"{holding['pnl_1d']:+.1%}",
            'Price': f"₹{perf['current_price']:.0f}",
            'Vol (30d)': f"{perf['volatility_30d']:.1%}",
            'Beta': f"{perf['beta']:.2f}",
            'RSI': f"{perf['rsi']:.0f}",
            '30d Return': f"{perf['cumulative_returns'][-1]:+.1%}"
        })
    
    # Display comprehensive holdings table (compact)
    holdings_df = pd.DataFrame(holdings_data)
    st.dataframe(holdings_df, use_container_width=True, hide_index=True, height=300)
    
    # INDIVIDUAL STOCK PERFORMANCE CHARTS GRID
    st.markdown("## 📈 INDIVIDUAL STOCK PERFORMANCE CHARTS")
    
    # Create a grid of stock charts (3 columns per row, compact)
    holdings_list = portfolio['all_holdings']
    num_holdings = len(holdings_list)
    cols_per_row = 3
    
    for i in range(0, num_holdings, cols_per_row):
        cols = st.columns(cols_per_row)
        
        for j in range(cols_per_row):
            if i + j < num_holdings:
                holding = holdings_list[i + j]
                symbol = holding['symbol']
                perf = stock_performance[symbol]
                
                with cols[j]:
                    # Individual stock performance chart (compact)
                    fig = go.Figure()
                    
                    # Add cumulative returns line
                    fig.add_trace(go.Scatter(
                        x=perf['dates'],
                        y=perf['cumulative_returns'] * 100,
                        mode='lines',
                        name=symbol,
                        line=dict(
                            color='#059669' if perf['cumulative_returns'][-1] > 0 else '#dc2626',
                            width=2
                        ),
                        fill='tonexty'
                    ))
                    
                    # Add current P&L annotation
                    current_return = perf['cumulative_returns'][-1] * 100
                    fig.add_annotation(
                        x=perf['dates'][-1],
                        y=current_return,
                        text=f"{current_return:+.1f}%",
                        showarrow=True,
                        arrowhead=2,
                        arrowcolor='#059669' if current_return > 0 else '#dc2626',
                        bgcolor='white',
                        bordercolor='#059669' if current_return > 0 else '#dc2626'
                    )
                    
                    fig.update_layout(
                        title=f"{symbol} ({holding['sector']})",
                        height=180,
                        margin=dict(l=5, r=5, t=15, b=5),
                        yaxis_title="Return (%)",
                        showlegend=False,
                        plot_bgcolor='rgba(0,0,0,0)'
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Add key metrics below chart (compact)
                    st.markdown(f"""
                    <div style="font-size: 0.7rem; text-align: center; margin-top: -5px;">
                        <strong>Wt:</strong> {holding['weight']:.1%} | 
                        <strong>Vol:</strong> {perf['volatility_30d']:.1%} | 
                        <strong>β:</strong> {perf['beta']:.2f}
                    </div>
                    """, unsafe_allow_html=True)
    
    # SECTOR PERFORMANCE ANALYSIS (compact)
    st.markdown("## 🏭 SECTOR PERFORMANCE BREAKDOWN")
    
    # Calculate sector performance
    sector_performance = {}
    for holding in portfolio['all_holdings']:
        sector = holding['sector']
        symbol = holding['symbol']
        weight = holding['weight']
        stock_return = stock_performance[symbol]['cumulative_returns'][-1]
        
        if sector not in sector_performance:
            sector_performance[sector] = {'total_weight': 0, 'weighted_return': 0, 'count': 0}
        
        sector_performance[sector]['total_weight'] += weight
        sector_performance[sector]['weighted_return'] += stock_return * weight
        sector_performance[sector]['count'] += 1
    
    # Create sector performance chart
    sectors = list(sector_performance.keys())
    sector_returns = [sector_performance[s]['weighted_return'] / sector_performance[s]['total_weight'] * 100 
                     for s in sectors]
    sector_weights = [sector_performance[s]['total_weight'] * 100 for s in sectors]
    
    col8, col9 = st.columns([1, 1])
    
    with col8:
        # Sector Returns Chart (compact)
        fig = go.Figure(data=go.Bar(
            x=sectors,
            y=sector_returns,
            marker_color=['#059669' if r > 0 else '#dc2626' for r in sector_returns]
        ))
        fig.update_layout(
            title="Sector Performance (30d)",
            height=200,
            margin=dict(l=5, r=5, t=15, b=5),
            yaxis_title="Return (%)",
            xaxis_tickangle=-45
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col9:
        # Sector Weight vs Performance Scatter (compact)
        fig = go.Figure(data=go.Scatter(
            x=sector_weights,
            y=sector_returns,
            mode='markers+text',
            text=sectors,
            textposition='top center',
            marker=dict(
                size=[w*2 for w in sector_weights],  # Size by weight
                color=sector_returns,
                colorscale='RdYlGn',
                showscale=True,
                colorbar=dict(title="Return (%)")
            )
        ))
        fig.update_layout(
            title="Sector Weight vs Performance",
            height=200,
            margin=dict(l=5, r=5, t=15, b=5),
            xaxis_title="Sector Weight (%)",
            yaxis_title="Return (%)"
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # CORRELATION MATRIX (compact)
    st.markdown("## 🔗 STOCK CORRELATION ANALYSIS")
    
    # Create correlation matrix for top 15 holdings
    top_15_symbols = [h['symbol'] for h in portfolio['all_holdings'][:15]]
    correlation_data = []
    
    for symbol in top_15_symbols:
        returns = stock_performance[symbol]['daily_returns']
        correlation_data.append(returns)
    
    correlation_matrix = np.corrcoef(correlation_data)
    
    fig = go.Figure(data=go.Heatmap(
        z=correlation_matrix,
        x=top_15_symbols,
        y=top_15_symbols,
        colorscale='RdBu',
        zmid=0,
        text=np.round(correlation_matrix, 2),
        texttemplate="%{text}",
        textfont={"size": 8},
        hoverongaps=False
    ))
    
    fig.update_layout(
        title="Top 15 Holdings Correlation Matrix",
        height=350,
        margin=dict(l=5, r=5, t=15, b=5)
    )
    
    st.plotly_chart(fig, use_container_width=True)

def main():
    """Enhanced main constitutional cockpit application with maximum information density"""
    
    # Header (compact)
    st.markdown("""
    <div class="constitutional-header">
        🏛️ NORTHSTAR V3 CONSTITUTIONAL COCKPIT<br>
        <small>Truth • State • Integrity — Not Opportunity</small>
    </div>
    """, unsafe_allow_html=True)
    
    # Load data
    try:
        data = load_sample_data()
    except Exception as e:
        st.error(f"❌ Failed to load data: {e}")
        st.stop()
    
    # Key Metrics Summary Bar (8 columns for more metrics)
    col_metrics = st.columns(8)
    system = data['system_state']
    risk = data['risk_state']
    engine = data['engine_state']
    validation = data['validation_state']
    intelligence = data['intelligence_state']
    
    with col_metrics[0]:
        st.metric("System Health", f"{(system['organs_healthy']/system['organs_total']*100):.0f}%")
    with col_metrics[1]:
        st.metric("Current Regime", system['current_regime'])
    with col_metrics[2]:
        st.metric("Active Engine", system['active_engine'].title())
    with col_metrics[3]:
        st.metric("Drawdown", f"{risk['current_drawdown']:.1%}")
    with col_metrics[4]:
        st.metric("Volatility", f"{risk['volatility_20d']:.1%}")
    with col_metrics[5]:
        st.metric("Walk-Forward", validation['last_walkforward_result'])
    with col_metrics[6]:
        st.metric("Intelligence", f"{intelligence['intelligence_confidence']:.0%}")
    with col_metrics[7]:
        st.metric("Positions", data['portfolio_data']['total_positions'])
    
    # System State + Risk Authority (no spacing)
    col1, col2 = st.columns(2)
    
    with col1:
        render_system_state_panel(data)
    
    with col2:
        render_risk_panel(data)
    
    # Engine Behavior (full width, no spacing)
    render_engine_panel(data)
    
    # Validation + Intelligence Observer (no spacing)
    col3, col4 = st.columns(2)
    
    with col3:
        render_validation_panel(data)
    
    with col4:
        render_intelligence_panel(data)
    
    # Portfolio Overview Section (immediate, no spacing)
    render_portfolio_overview(data)
    
    # Compact footer
    st.markdown("""
    <div style="text-align: center; color: #6b7280; font-size: 0.7rem; margin-top: 0.5rem; padding: 0.3rem; border-top: 1px solid #e5e7eb;">
        <strong>Constitutional Principles:</strong> Observational only • No decisions while open • Closed during drawdowns • Weekly intelligence separate • If urgency, stop looking<br>
        <strong>Data:</strong> {timestamp} | Uptime: {uptime}d | Quality: {quality:.1%} | Update: {update_hours:.1f}h | Holdings: {holdings} | Sectors: {sectors} | Charts: 140+<br>
        <em>"Dashboard reduces emotion. Observer makes you wiser, not braver."</em>
    </div>
    """.format(
        timestamp=data['timestamp'].strftime("%H:%M:%S"),
        uptime=system['system_uptime_days'],
        quality=validation['data_integrity_score'],
        update_hours=(datetime.now() - data['intelligence_state']['last_intelligence_update']).total_seconds() / 3600,
        holdings=data['portfolio_data']['total_positions'],
        sectors=len(data['portfolio_data']['sectors'])
    ), unsafe_allow_html=True)
    
    # Auto-refresh every 5 minutes
    st.markdown("""
    <script>
    setTimeout(function(){
        window.location.reload(1);
    }, 300000);
    </script>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()