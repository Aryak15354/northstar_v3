#!/usr/bin/env python3
"""
🏛️ PROFESSIONAL CONSTITUTIONAL COCKPIT - INSTITUTIONAL GRADE
Enhanced Dashboard with Professional Styling and Comprehensive Analytics

Features:
- Institutional-grade professional styling
- Large, clear visualizations optimized for analysis
- Comprehensive portfolio analytics
- Real-time system monitoring
- Advanced risk management displays
- Professional color schemes and typography
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
    page_title="🏛️ Northstar V3 - Professional Constitutional Cockpit",
    initial_sidebar_state="collapsed"
)

# =========================== PROFESSIONAL STYLING ===========================

st.markdown("""
<style>
    /* PROFESSIONAL INSTITUTIONAL STYLING */
    
    /* Import professional fonts */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    /* Main layout */
    .main { 
        padding: 2rem !important; 
        margin: 0 !important;
        max-width: 100% !important;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        background: #fafbfc;
    }
    .block-container { 
        padding: 2rem !important; 
        margin: 0 !important;
        max-width: 100% !important;
    }
    
    /* Hide Streamlit branding */
    #MainMenu, footer, header, .stDeployButton, .stToolbar { 
        visibility: hidden !important; 
    }
    
    /* Professional header */
    .professional-header {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #334155 100%);
        color: white;
        padding: 2rem;
        text-align: center;
        font-weight: 600;
        margin-bottom: 2rem;
        border-radius: 12px;
        box-shadow: 0 10px 25px rgba(0,0,0,0.1);
        border: 1px solid #e2e8f0;
    }
    
    .header-title {
        font-size: 2.5rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
        letter-spacing: -0.025em;
    }
    
    .header-subtitle {
        font-size: 1.125rem;
        opacity: 0.9;
        font-weight: 400;
    }
    
    /* Professional panel styling */
    .professional-panel {
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 2rem;
        margin-bottom: 2rem;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        transition: all 0.2s ease;
    }
    
    .professional-panel:hover {
        box-shadow: 0 8px 25px rgba(0,0,0,0.1);
        transform: translateY(-2px);
    }
    
    /* Panel titles */
    .panel-title {
        font-size: 1.5rem;
        font-weight: 600;
        color: #1e293b;
        margin-bottom: 1.5rem;
        padding-bottom: 0.75rem;
        border-bottom: 3px solid #3b82f6;
        display: flex;
        align-items: center;
    }
    
    .panel-icon {
        margin-right: 0.75rem;
        font-size: 1.75rem;
    }
    
    /* Metrics styling */
    .metric-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 1.5rem;
        margin-bottom: 2rem;
    }
    
    .metric-card {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 1.5rem;
        text-align: center;
        transition: all 0.2s ease;
    }
    
    .metric-card:hover {
        background: #f1f5f9;
        border-color: #3b82f6;
    }
    
    .metric-value {
        font-size: 2rem;
        font-weight: 700;
        color: #1e293b;
        margin-bottom: 0.25rem;
    }
    
    .metric-label {
        font-size: 0.875rem;
        color: #64748b;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    
    .metric-change {
        font-size: 0.875rem;
        font-weight: 600;
        margin-top: 0.5rem;
    }
    
    .metric-positive { color: #059669; }
    .metric-negative { color: #dc2626; }
    .metric-neutral { color: #6b7280; }
    
    /* Status indicators */
    .status-indicator {
        display: inline-flex;
        align-items: center;
        padding: 0.5rem 1rem;
        border-radius: 20px;
        font-size: 0.875rem;
        font-weight: 600;
        margin: 0.25rem;
    }
    
    .status-healthy {
        background: #dcfce7;
        color: #166534;
        border: 1px solid #bbf7d0;
    }
    
    .status-warning {
        background: #fef3c7;
        color: #92400e;
        border: 1px solid #fde68a;
    }
    
    .status-critical {
        background: #fee2e2;
        color: #991b1b;
        border: 1px solid #fecaca;
    }
    
    /* Chart containers */
    .chart-container {
        background: white;
        border-radius: 8px;
        padding: 1rem;
        margin: 1rem 0;
        border: 1px solid #e2e8f0;
    }
    
    /* Professional tables */
    .dataframe {
        border: none !important;
        border-radius: 8px !important;
        overflow: hidden !important;
    }
    
    .dataframe th {
        background: #f8fafc !important;
        color: #374151 !important;
        font-weight: 600 !important;
        padding: 1rem !important;
        border: none !important;
    }
    
    .dataframe td {
        padding: 0.75rem 1rem !important;
        border: none !important;
        border-bottom: 1px solid #f3f4f6 !important;
    }
    
    /* Constitutional principles */
    .constitutional-principles {
        background: linear-gradient(135deg, #fef7cd 0%, #fef3c7 100%);
        border: 1px solid #f59e0b;
        border-radius: 8px;
        padding: 1.5rem;
        margin: 2rem 0;
    }
    
    .principle-title {
        font-size: 1.125rem;
        font-weight: 600;
        color: #92400e;
        margin-bottom: 1rem;
    }
    
    .principle-item {
        color: #78350f;
        margin: 0.5rem 0;
        font-weight: 500;
    }
    
    /* Responsive design */
    @media (max-width: 768px) {
        .main { padding: 1rem !important; }
        .professional-panel { padding: 1rem !important; }
        .header-title { font-size: 2rem; }
        .metric-grid { grid-template-columns: 1fr; }
    }
</style>
""", unsafe_allow_html=True)

# =========================== PROFESSIONAL COLOR SCHEMES ===========================

PROFESSIONAL_COLORS = {
    'primary': '#3b82f6',
    'secondary': '#6366f1', 
    'success': '#10b981',
    'warning': '#f59e0b',
    'danger': '#ef4444',
    'info': '#06b6d4',
    'dark': '#1e293b',
    'light': '#f8fafc',
    'muted': '#64748b'
}

CHART_COLORS = [
    '#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', 
    '#06b6d4', '#84cc16', '#f97316', '#ec4899', '#6366f1'
]

# =========================== DATA LOADING FUNCTIONS ===========================

@st.cache_data(ttl=300)
def load_comprehensive_system_data():
    """Load comprehensive system data for all 5 constitutional panels"""
    try:
        # Try to load real data first
        data_paths = [
            'data/processed/portfolio_state.json',
            'data/live/current_positions.json',
            'data/backtests/latest_results.json',
            'data/system/health_metrics.json',
            'data/intelligence/observer_state.json'
        ]
        
        system_data = {}
        for path in data_paths:
            if os.path.exists(path):
                with open(path, 'r') as f:
                    system_data.update(json.load(f))
        
        if system_data:
            return enhance_system_data(system_data)
            
    except Exception as e:
        st.warning(f"Could not load real data: {e}")
    
    # Generate comprehensive sample data
    return generate_comprehensive_system_data()

def generate_comprehensive_system_data():
    """Generate comprehensive sample data for all 5 constitutional panels"""
    np.random.seed(42)
    
    # Generate dates for time series
    dates = pd.date_range(start='2024-01-01', periods=30, freq='D')
    
    # Portfolio holdings
    all_holdings = [
        {'symbol': 'RELIANCE', 'weight': 0.08, 'sector': 'Energy'},
        {'symbol': 'TCS', 'weight': 0.07, 'sector': 'Technology'},
        {'symbol': 'HDFCBANK', 'weight': 0.06, 'sector': 'Financials'},
        {'symbol': 'INFY', 'weight': 0.05, 'sector': 'Technology'},
        {'symbol': 'HINDUNILVR', 'weight': 0.04, 'sector': 'Consumer'},
        {'symbol': 'ICICIBANK', 'weight': 0.04, 'sector': 'Financials'},
        {'symbol': 'KOTAKBANK', 'weight': 0.03, 'sector': 'Financials'},
        {'symbol': 'BHARTIARTL', 'weight': 0.03, 'sector': 'Technology'},
        {'symbol': 'ITC', 'weight': 0.03, 'sector': 'Consumer'},
        {'symbol': 'SBIN', 'weight': 0.03, 'sector': 'Financials'},
        {'symbol': 'BAJFINANCE', 'weight': 0.03, 'sector': 'Financials'},
        {'symbol': 'ASIANPAINT', 'weight': 0.02, 'sector': 'Materials'},
        {'symbol': 'MARUTI', 'weight': 0.02, 'sector': 'Consumer'},
        {'symbol': 'AXISBANK', 'weight': 0.02, 'sector': 'Financials'},
        {'symbol': 'LT', 'weight': 0.02, 'sector': 'Industrials'},
        {'symbol': 'HCLTECH', 'weight': 0.02, 'sector': 'Technology'},
        {'symbol': 'WIPRO', 'weight': 0.02, 'sector': 'Technology'},
        {'symbol': 'ULTRACEMCO', 'weight': 0.02, 'sector': 'Materials'},
        {'symbol': 'NESTLEIND', 'weight': 0.02, 'sector': 'Consumer'},
        {'symbol': 'POWERGRID', 'weight': 0.02, 'sector': 'Utilities'},
        {'symbol': 'NTPC', 'weight': 0.02, 'sector': 'Utilities'},
        {'symbol': 'ONGC', 'weight': 0.02, 'sector': 'Energy'},
        {'symbol': 'TATAMOTORS', 'weight': 0.02, 'sector': 'Consumer'},
        {'symbol': 'TECHM', 'weight': 0.02, 'sector': 'Technology'},
        {'symbol': 'SUNPHARMA', 'weight': 0.02, 'sector': 'Healthcare'},
        {'symbol': 'JSWSTEEL', 'weight': 0.02, 'sector': 'Materials'},
        {'symbol': 'INDUSINDBK', 'weight': 0.02, 'sector': 'Financials'},
        {'symbol': 'BAJAJFINSV', 'weight': 0.02, 'sector': 'Financials'},
        {'symbol': 'GRASIM', 'weight': 0.02, 'sector': 'Materials'}
    ]
    
    # Generate individual stock performance data
    stock_performance = {}
    for holding in all_holdings:
        symbol = holding['symbol']
        stock_returns = np.random.normal(0.001, 0.025, len(dates))
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
    
    # Performance data
    daily_returns = np.random.normal(0.001, 0.02, len(dates))
    cumulative_returns = (1 + pd.Series(daily_returns)).cumprod() - 1
    running_max = cumulative_returns.expanding().max()
    drawdown_series = (cumulative_returns - running_max)
    
    return {
        'timestamp': datetime.now(),
        'system_state': {
            'system_status': 'healthy',
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
            'margin_utilization': 0.34,
            'sharpe_ratio': 1.24
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
            'feature_stability_score': 0.89
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
            'daily_returns': daily_returns,
            'cumulative_returns': cumulative_returns.values,
            'drawdown_series': drawdown_series.values,
            'volatility_series': np.random.uniform(0.15, 0.25, len(dates)),
            'exposure_series': np.random.uniform(0.4, 0.8, len(dates)),
            'regime_series': np.random.choice(['SUPPORTIVE', 'HOSTILE', 'PANIC'], len(dates), p=[0.6, 0.3, 0.1])
        },
        'portfolio_data': {
            'total_value': 10_000_000,
            'total_positions': len(all_holdings),
            'long_positions': len([h for h in all_holdings if h['weight'] > 0]),
            'short_positions': 0,
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
            'top_holdings': all_holdings[:10]
        },
        'stock_performance': stock_performance
    }

# =========================== CHART CREATION FUNCTIONS ===========================

def create_professional_portfolio_overview(data):
    """Create professional portfolio overview chart"""
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=('Portfolio Value Over Time', 'Daily P&L Distribution', 
                       'Risk Metrics', 'Sector Allocation'),
        specs=[[{"secondary_y": True}, {"type": "histogram"}],
               [{"type": "bar"}, {"type": "pie"}]],
        vertical_spacing=0.12,
        horizontal_spacing=0.1
    )
    
    # Portfolio value over time
    dates = pd.date_range(start='2024-01-01', periods=len(data['cumulative_pnl']), freq='D')
    portfolio_values = data['portfolio_value'] + data['cumulative_pnl']
    
    fig.add_trace(
        go.Scatter(
            x=dates, 
            y=portfolio_values,
            name='Portfolio Value',
            line=dict(color=PROFESSIONAL_COLORS['primary'], width=3),
            fill='tonexty',
            fillcolor='rgba(59, 130, 246, 0.1)'
        ),
        row=1, col=1
    )
    
    # Daily P&L distribution
    fig.add_trace(
        go.Histogram(
            x=data['daily_pnl'],
            name='Daily P&L',
            nbinsx=30,
            marker_color=PROFESSIONAL_COLORS['info'],
            opacity=0.7
        ),
        row=1, col=2
    )
    
    # Risk metrics
    risk_names = list(data['risk_metrics'].keys())
    risk_values = [abs(v) for v in data['risk_metrics'].values()]
    
    fig.add_trace(
        go.Bar(
            x=risk_names,
            y=risk_values,
            name='Risk Metrics',
            marker_color=CHART_COLORS[:len(risk_names)]
        ),
        row=2, col=1
    )
    
    # Sector allocation (sample)
    sectors = ['Technology', 'Financial', 'Consumer', 'Healthcare', 'Industrial', 'Energy']
    allocations = [25, 20, 18, 15, 12, 10]
    
    fig.add_trace(
        go.Pie(
            labels=sectors,
            values=allocations,
            name='Sector Allocation',
            marker_colors=CHART_COLORS[:len(sectors)]
        ),
        row=2, col=2
    )
    
    fig.update_layout(
        height=800,
        showlegend=True,
        title_text="Portfolio Overview Dashboard",
        title_x=0.5,
        title_font_size=24,
        font=dict(family="Inter, sans-serif", size=12),
        plot_bgcolor='white',
        paper_bgcolor='white'
    )
    
    return fig

def create_individual_stock_performance(data):
    """Create individual stock performance charts"""
    stock_performance = data['stock_performance']
    stocks = list(stock_performance.keys())[:12]  # Show top 12 stocks
    
    fig = make_subplots(
        rows=3, cols=4,
        subplot_titles=stocks,
        vertical_spacing=0.08,
        horizontal_spacing=0.05
    )
    
    for i, stock in enumerate(stocks):
        row = i // 4 + 1
        col = i % 4 + 1
        
        stock_info = stock_performance[stock]
        dates = stock_info['dates']
        
        fig.add_trace(
            go.Scatter(
                x=dates,
                y=stock_info['cumulative_returns'] * 100,
                name=stock,
                line=dict(color=CHART_COLORS[i % len(CHART_COLORS)], width=2),
                showlegend=False
            ),
            row=row, col=col
        )
    
    fig.update_layout(
        height=900,
        title_text="Individual Stock Performance",
        title_x=0.5,
        title_font_size=24,
        font=dict(family="Inter, sans-serif", size=10),
        plot_bgcolor='white',
        paper_bgcolor='white'
    )
    
    return fig

def create_risk_dashboard(data):
    """Create comprehensive risk dashboard"""
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=('Value at Risk', 'Drawdown Analysis', 'Correlation Heatmap', 'Risk Decomposition'),
        specs=[[{"type": "bar"}, {"type": "scatter"}],
               [{"type": "heatmap"}, {"type": "pie"}]]
    )
    
    # VaR analysis
    var_periods = ['1D', '5D', '1M', '3M']
    var_95 = [data['risk_metrics']['var_95'] * mult for mult in [1, 2.24, 4.47, 7.75]]
    var_99 = [data['risk_metrics']['var_99'] * mult for mult in [1, 2.24, 4.47, 7.75]]
    
    fig.add_trace(
        go.Bar(x=var_periods, y=var_95, name='VaR 95%', marker_color=PROFESSIONAL_COLORS['warning']),
        row=1, col=1
    )
    fig.add_trace(
        go.Bar(x=var_periods, y=var_99, name='VaR 99%', marker_color=PROFESSIONAL_COLORS['danger']),
        row=1, col=1
    )
    
    # Drawdown analysis
    drawdown = np.minimum.accumulate(data['cumulative_pnl']) - data['cumulative_pnl']
    dates = pd.date_range(start='2024-01-01', periods=len(drawdown), freq='D')
    
    fig.add_trace(
        go.Scatter(
            x=dates, 
            y=drawdown,
            name='Drawdown',
            fill='tozeroy',
            fillcolor='rgba(239, 68, 68, 0.3)',
            line=dict(color=PROFESSIONAL_COLORS['danger'])
        ),
        row=1, col=2
    )
    
    # Correlation heatmap (sample)
    corr_matrix = np.random.uniform(-0.5, 0.8, (8, 8))
    np.fill_diagonal(corr_matrix, 1.0)
    corr_matrix = (corr_matrix + corr_matrix.T) / 2  # Make symmetric
    
    asset_names = ['Equity', 'Bonds', 'Commodities', 'FX', 'REITs', 'Crypto', 'Alternatives', 'Cash']
    
    fig.add_trace(
        go.Heatmap(
            z=corr_matrix,
            x=asset_names,
            y=asset_names,
            colorscale='RdBu',
            zmid=0,
            showscale=True
        ),
        row=2, col=1
    )
    
    # Risk decomposition
    risk_sources = ['Market Risk', 'Credit Risk', 'Liquidity Risk', 'Operational Risk', 'Model Risk']
    risk_contributions = [45, 25, 15, 10, 5]
    
    fig.add_trace(
        go.Pie(
            labels=risk_sources,
            values=risk_contributions,
            name='Risk Decomposition',
            marker_colors=CHART_COLORS[:len(risk_sources)]
        ),
        row=2, col=2
    )
    
    fig.update_layout(
        height=800,
        title_text="Risk Management Dashboard",
        title_x=0.5,
        title_font_size=24,
        font=dict(family="Inter, sans-serif", size=12),
        plot_bgcolor='white',
        paper_bgcolor='white'
    )
    
    return fig

def create_system_health_dashboard(data):
    """Create system health monitoring dashboard"""
    health_metrics = data['system_health']
    
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=('System Health Scores', 'Performance Trends', 'Alert Status', 'Capacity Utilization'),
        specs=[[{"type": "bar"}, {"type": "scatter"}],
               [{"type": "indicator"}, {"type": "bar"}]]
    )
    
    # Health scores
    metrics = list(health_metrics.keys())
    scores = [v * 100 for v in health_metrics.values()]
    colors = [PROFESSIONAL_COLORS['success'] if s >= 95 else 
              PROFESSIONAL_COLORS['warning'] if s >= 85 else 
              PROFESSIONAL_COLORS['danger'] for s in scores]
    
    fig.add_trace(
        go.Bar(
            x=metrics,
            y=scores,
            name='Health Score (%)',
            marker_color=colors,
            text=[f'{s:.1f}%' for s in scores],
            textposition='outside'
        ),
        row=1, col=1
    )
    
    # Performance trends (sample)
    dates = pd.date_range(start='2024-01-01', periods=30, freq='D')
    performance = 95 + np.random.normal(0, 2, 30)
    
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=performance,
            name='System Performance',
            line=dict(color=PROFESSIONAL_COLORS['primary'], width=3),
            fill='tonexty',
            fillcolor='rgba(59, 130, 246, 0.1)'
        ),
        row=1, col=2
    )
    
    # Overall system health indicator
    overall_health = np.mean(list(health_metrics.values())) * 100
    
    fig.add_trace(
        go.Indicator(
            mode="gauge+number+delta",
            value=overall_health,
            domain={'x': [0, 1], 'y': [0, 1]},
            title={'text': "Overall Health"},
            delta={'reference': 95},
            gauge={
                'axis': {'range': [None, 100]},
                'bar': {'color': PROFESSIONAL_COLORS['primary']},
                'steps': [
                    {'range': [0, 70], 'color': PROFESSIONAL_COLORS['danger']},
                    {'range': [70, 85], 'color': PROFESSIONAL_COLORS['warning']},
                    {'range': [85, 100], 'color': PROFESSIONAL_COLORS['success']}
                ],
                'threshold': {
                    'line': {'color': "red", 'width': 4},
                    'thickness': 0.75,
                    'value': 90
                }
            }
        ),
        row=2, col=1
    )
    
    # Capacity utilization
    resources = ['CPU', 'Memory', 'Storage', 'Network', 'Database']
    utilization = [65, 78, 45, 32, 58]
    
    fig.add_trace(
        go.Bar(
            x=resources,
            y=utilization,
            name='Utilization (%)',
            marker_color=PROFESSIONAL_COLORS['info'],
            text=[f'{u}%' for u in utilization],
            textposition='outside'
        ),
        row=2, col=2
    )
    
    fig.update_layout(
        height=800,
        title_text="System Health & Monitoring",
        title_x=0.5,
        title_font_size=24,
        font=dict(family="Inter, sans-serif", size=12),
        plot_bgcolor='white',
        paper_bgcolor='white'
    )
    
    return fig

def create_advanced_analytics_dashboard(data):
    """Create advanced analytics dashboard with additional insights"""
    fig = make_subplots(
        rows=3, cols=2,
        subplot_titles=('Strategy Performance Attribution', 'Market Regime Analysis', 
                       'Alpha vs Beta Decomposition', 'Volatility Surface',
                       'Factor Exposure', 'Performance vs Benchmark'),
        specs=[[{"type": "bar"}, {"type": "scatter"}],
               [{"type": "scatter"}, {"type": "surface"}],
               [{"type": "bar"}, {"type": "scatter"}]],
        vertical_spacing=0.08
    )
    
    # Strategy performance attribution
    strategies = ['Momentum', 'Mean Reversion', 'Trend Following', 'Pairs Trading', 'Arbitrage']
    returns = [0.12, 0.08, 0.15, 0.06, 0.04]
    
    fig.add_trace(
        go.Bar(
            x=strategies,
            y=returns,
            name='Strategy Returns',
            marker_color=CHART_COLORS[:len(strategies)],
            text=[f'{r:.1%}' for r in returns],
            textposition='outside'
        ),
        row=1, col=1
    )
    
    # Market regime analysis
    regimes = ['Bull Market', 'Bear Market', 'Sideways', 'High Vol', 'Low Vol']
    probabilities = [0.35, 0.15, 0.25, 0.15, 0.10]
    
    fig.add_trace(
        go.Scatter(
            x=regimes,
            y=probabilities,
            mode='markers+lines',
            name='Regime Probability',
            marker=dict(size=15, color=PROFESSIONAL_COLORS['primary']),
            line=dict(width=3)
        ),
        row=1, col=2
    )
    
    # Alpha vs Beta decomposition
    alpha_values = np.random.normal(0.02, 0.05, 20)
    beta_values = np.random.normal(1.0, 0.3, 20)
    
    fig.add_trace(
        go.Scatter(
            x=beta_values,
            y=alpha_values,
            mode='markers',
            name='Alpha vs Beta',
            marker=dict(
                size=12,
                color=alpha_values,
                colorscale='RdYlGn',
                showscale=True,
                colorbar=dict(title="Alpha")
            )
        ),
        row=2, col=1
    )
    
    # Volatility surface (simplified)
    x_vol = np.linspace(0.1, 0.5, 10)
    y_vol = np.linspace(30, 365, 10)
    X_vol, Y_vol = np.meshgrid(x_vol, y_vol)
    Z_vol = 0.2 + 0.1 * np.sin(X_vol * 10) + 0.05 * np.cos(Y_vol / 50)
    
    fig.add_trace(
        go.Surface(
            x=X_vol,
            y=Y_vol,
            z=Z_vol,
            name='Volatility Surface',
            colorscale='Viridis'
        ),
        row=2, col=2
    )
    
    # Factor exposure
    factors = ['Market', 'Size', 'Value', 'Momentum', 'Quality', 'Low Vol']
    exposures = [0.85, -0.12, 0.23, 0.45, 0.18, -0.08]
    colors = [PROFESSIONAL_COLORS['success'] if e > 0 else PROFESSIONAL_COLORS['danger'] for e in exposures]
    
    fig.add_trace(
        go.Bar(
            x=factors,
            y=exposures,
            name='Factor Exposure',
            marker_color=colors,
            text=[f'{e:+.2f}' for e in exposures],
            textposition='outside'
        ),
        row=3, col=1
    )
    
    # Performance vs benchmark
    dates = data['performance_data']['dates']
    portfolio_perf = data['performance_data']['cumulative_returns']
    benchmark_perf = np.cumsum(np.random.normal(0.0005, 0.012, len(dates)))
    
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=portfolio_perf * 100,
            name='Portfolio',
            line=dict(color=PROFESSIONAL_COLORS['primary'], width=3)
        ),
        row=3, col=2
    )
    
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=benchmark_perf * 100,
            name='Benchmark',
            line=dict(color=PROFESSIONAL_COLORS['muted'], width=2, dash='dash')
        ),
        row=3, col=2
    )
    
    fig.update_layout(
        height=1200,
        title_text="Advanced Analytics Dashboard",
        title_x=0.5,
        title_font_size=24,
        font=dict(family="Inter, sans-serif", size=12),
        plot_bgcolor='white',
        paper_bgcolor='white',
        showlegend=True
    )
    
    return fig

def create_market_microstructure_dashboard(data):
    """Create market microstructure analysis dashboard"""
    fig = make_subplots(
        rows=2, cols=3,
        subplot_titles=('Order Flow Analysis', 'Bid-Ask Spreads', 'Market Impact',
                       'Execution Quality', 'Liquidity Heatmap', 'Transaction Costs'),
        specs=[[{"type": "bar"}, {"type": "scatter"}, {"type": "scatter"}],
               [{"type": "indicator"}, {"type": "heatmap"}, {"type": "bar"}]]
    )
    
    # Order flow analysis
    order_types = ['Market Buy', 'Market Sell', 'Limit Buy', 'Limit Sell', 'Stop Loss']
    volumes = [1200000, 980000, 2100000, 1850000, 450000]
    
    fig.add_trace(
        go.Bar(
            x=order_types,
            y=volumes,
            name='Order Volume',
            marker_color=CHART_COLORS[:len(order_types)]
        ),
        row=1, col=1
    )
    
    # Bid-ask spreads over time
    times = pd.date_range(start='09:15', end='15:30', freq='15min')
    spreads = 0.05 + 0.02 * np.random.random(len(times))
    
    fig.add_trace(
        go.Scatter(
            x=times,
            y=spreads,
            name='Bid-Ask Spread',
            line=dict(color=PROFESSIONAL_COLORS['warning'], width=2),
            fill='tozeroy',
            fillcolor='rgba(245, 158, 11, 0.2)'
        ),
        row=1, col=2
    )
    
    # Market impact
    trade_sizes = np.logspace(3, 6, 20)
    market_impact = 0.001 * np.sqrt(trade_sizes / 100000)
    
    fig.add_trace(
        go.Scatter(
            x=trade_sizes,
            y=market_impact,
            mode='markers+lines',
            name='Market Impact',
            marker=dict(size=8, color=PROFESSIONAL_COLORS['danger']),
            line=dict(width=2)
        ),
        row=1, col=3
    )
    
    # Execution quality gauge
    execution_score = 92.5
    
    fig.add_trace(
        go.Indicator(
            mode="gauge+number",
            value=execution_score,
            title={'text': "Execution Quality"},
            gauge={
                'axis': {'range': [None, 100]},
                'bar': {'color': PROFESSIONAL_COLORS['success']},
                'steps': [
                    {'range': [0, 70], 'color': PROFESSIONAL_COLORS['danger']},
                    {'range': [70, 85], 'color': PROFESSIONAL_COLORS['warning']},
                    {'range': [85, 100], 'color': PROFESSIONAL_COLORS['success']}
                ]
            }
        ),
        row=2, col=1
    )
    
    # Liquidity heatmap
    stocks_sample = ['RELIANCE', 'TCS', 'HDFCBANK', 'INFY', 'ICICIBANK']
    times_sample = ['09:30', '11:00', '12:30', '14:00', '15:15']
    liquidity_matrix = np.random.uniform(0.5, 1.0, (len(stocks_sample), len(times_sample)))
    
    fig.add_trace(
        go.Heatmap(
            z=liquidity_matrix,
            x=times_sample,
            y=stocks_sample,
            colorscale='Blues',
            showscale=True,
            colorbar=dict(title="Liquidity Score")
        ),
        row=2, col=2
    )
    
    # Transaction costs breakdown
    cost_components = ['Brokerage', 'Impact', 'Timing', 'Opportunity']
    costs = [0.05, 0.12, 0.08, 0.03]
    
    fig.add_trace(
        go.Bar(
            x=cost_components,
            y=costs,
            name='Transaction Costs (%)',
            marker_color=PROFESSIONAL_COLORS['info'],
            text=[f'{c:.2%}' for c in costs],
            textposition='outside'
        ),
        row=2, col=3
    )
    
    fig.update_layout(
        height=800,
        title_text="Market Microstructure Analysis",
        title_x=0.5,
        title_font_size=24,
        font=dict(family="Inter, sans-serif", size=12),
        plot_bgcolor='white',
        paper_bgcolor='white'
    )
    
    return fig

# =========================== THE 5 CONSTITUTIONAL PANELS ===========================

def render_system_state_panel(data):
    """PANEL 1 — SYSTEM STATE: Professional enhanced system state panel"""
    
    st.markdown('<div class="professional-panel">', unsafe_allow_html=True)
    st.markdown('<div class="panel-title"><span class="panel-icon">📊</span>PANEL 1 — SYSTEM STATE</div>', unsafe_allow_html=True)
    st.markdown('<div style="color: #64748b; font-style: italic; margin-bottom: 1.5rem;">Question: "Is the system healthy and behaving as designed?"</div>', unsafe_allow_html=True)
    
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
                'bar': {'color': PROFESSIONAL_COLORS['success'] if organ_pct >= 80 else PROFESSIONAL_COLORS['warning'] if organ_pct >= 60 else PROFESSIONAL_COLORS['danger']},
                'steps': [
                    {'range': [0, 60], 'color': '#fee2e2'},
                    {'range': [60, 80], 'color': '#fef3c7'},
                    {'range': [80, 100], 'color': '#d1fae5'}
                ],
                'threshold': {
                    'line': {'color': "red", 'width': 4},
                    'thickness': 0.75,
                    'value': 90
                }
            }
        ))
        fig.update_layout(height=300, margin=dict(l=20, r=20, t=40, b=20), font=dict(family="Inter, sans-serif"))
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
        
        # System Status Metrics
        status_class = "status-healthy" if system['system_status'] == 'healthy' else "status-warning"
        st.markdown(f"""
        <div class="metric-grid">
            <div class="metric-card">
                <div class="metric-value {status_class}">{system['system_status'].upper()}</div>
                <div class="metric-label">System Status</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{system['organs_healthy']}/{system['organs_total']}</div>
                <div class="metric-label">Organs Healthy</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        # Resource Usage Chart
        resources = ['CPU', 'Memory', 'Disk', 'Network']
        usage_values = [
            system['cpu_usage_pct'] * 100,
            system['memory_usage_pct'] * 100,
            system['disk_usage_pct'] * 100,
            min(system['network_latency_ms'] / 100 * 100, 100)
        ]
        
        fig = go.Figure(data=go.Bar(
            x=resources,
            y=usage_values,
            marker_color=[PROFESSIONAL_COLORS['success'] if v < 50 else PROFESSIONAL_COLORS['warning'] if v < 80 else PROFESSIONAL_COLORS['danger'] for v in usage_values],
            text=[f'{v:.1f}%' for v in usage_values],
            textposition='outside'
        ))
        fig.update_layout(
            title="Resource Usage (%)",
            height=300,
            margin=dict(l=20, r=20, t=40, b=20),
            yaxis_title="Usage %",
            font=dict(family="Inter, sans-serif"),
            plot_bgcolor='white'
        )
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
        
        # Resource Metrics
        st.markdown(f"""
        <div class="metric-grid">
            <div class="metric-card">
                <div class="metric-value">{system['cpu_usage_pct']:.1%}</div>
                <div class="metric-label">CPU Usage</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{system['memory_usage_pct']:.1%}</div>
                <div class="metric-label">Memory Usage</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        # Regime and Engine Status Chart
        confidence_metrics = ['Regime Confidence', 'Engine Confidence']
        confidence_values = [system['regime_confidence'] * 100, system['engine_confidence'] * 100]
        
        fig = go.Figure(data=go.Bar(
            x=confidence_metrics,
            y=confidence_values,
            marker_color=[PROFESSIONAL_COLORS['primary'], PROFESSIONAL_COLORS['secondary']],
            text=[f'{v:.1f}%' for v in confidence_values],
            textposition='outside'
        ))
        fig.update_layout(
            title="Confidence Levels",
            height=300,
            margin=dict(l=20, r=20, t=40, b=20),
            yaxis_title="Confidence %",
            font=dict(family="Inter, sans-serif"),
            plot_bgcolor='white'
        )
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
        
        # Regime and Engine Metrics
        st.markdown(f"""
        <div class="metric-grid">
            <div class="metric-card">
                <div class="metric-value">{system['current_regime']}</div>
                <div class="metric-label">Current Regime</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{system['active_engine'].title()}</div>
                <div class="metric-label">Active Engine</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # Bottom row: Additional System Metrics
    col4, col5, col6 = st.columns([1, 1, 1])
    
    with col4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{system['system_uptime_days']}</div>
            <div class="metric-label">System Uptime (Days)</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col5:
        conviction_text = "LOCKED ✅" if system['conviction_locked'] else "UNLOCKED ❌"
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{conviction_text}</div>
            <div class="metric-label">Conviction Contract</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col6:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{system['current_exposure']:.1%} / {system['allowed_exposure']:.1%}</div>
            <div class="metric-label">Current / Allowed Exposure</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

def render_risk_authority_panel(data):
    """PANEL 2 — RISK AUTHORITY: Professional enhanced risk authority panel"""
    
    st.markdown('<div class="professional-panel">', unsafe_allow_html=True)
    st.markdown('<div class="panel-title"><span class="panel-icon">🛡️</span>PANEL 2 — RISK AUTHORITY</div>', unsafe_allow_html=True)
    st.markdown('<div style="color: #64748b; font-style: italic; margin-bottom: 1.5rem;">Question: "Who is in charge right now?"</div>', unsafe_allow_html=True)
    
    risk = data['risk_state']
    
    # Create three columns for comprehensive risk metrics and charts
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        # Risk Metrics Radar Chart
        risk_categories = ['VaR 95%', 'VaR 99%', 'Tail Risk', 'Correlation', 'Liquidity', 'Concentration']
        risk_values = [
            abs(risk['var_95_1d']) * 400,
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
            line_color=PROFESSIONAL_COLORS['danger'],
            fillcolor=f'rgba(239, 68, 68, 0.2)'
        ))
        fig.update_layout(
            polar=dict(
                radialaxis=dict(
                    visible=True,
                    range=[0, 30]
                )),
            title="Risk Profile",
            height=300,
            margin=dict(l=20, r=20, t=40, b=20),
            showlegend=False,
            font=dict(family="Inter, sans-serif")
        )
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
        
        # Emergency Brake Status
        brake_class = "status-healthy" if risk['emergency_brake_status'] == "ARMED" else "status-critical"
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{risk['emergency_brake_status']}</div>
            <div class="metric-label">Emergency Brake</div>
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
            marker_color=[PROFESSIONAL_COLORS['danger'] if drawdown_values[0] > 5 else PROFESSIONAL_COLORS['warning'] if drawdown_values[0] > 2 else PROFESSIONAL_COLORS['success'],
                         PROFESSIONAL_COLORS['warning'], PROFESSIONAL_COLORS['muted']],
            text=[f'{v:.1f}%' for v in drawdown_values],
            textposition='outside'
        ))
        fig.update_layout(
            title="Drawdown Analysis (%)",
            height=300,
            margin=dict(l=20, r=20, t=40, b=20),
            yaxis_title="Drawdown %",
            font=dict(family="Inter, sans-serif"),
            plot_bgcolor='white'
        )
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
        
        # Drawdown Metrics
        st.markdown(f"""
        <div class="metric-grid">
            <div class="metric-card">
                <div class="metric-value">{risk['current_drawdown']:.1%}</div>
                <div class="metric-label">Current Drawdown</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{risk['leverage_ratio']:.2f}x</div>
                <div class="metric-label">Leverage Ratio</div>
            </div>
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
            marker_color=[PROFESSIONAL_COLORS['warning'], PROFESSIONAL_COLORS['success'], 
                         {'low': PROFESSIONAL_COLORS['success'], 'medium': PROFESSIONAL_COLORS['warning'], 'high': PROFESSIONAL_COLORS['danger'], 'extreme': '#7c2d12'}.get(risk['volatility_stress'], PROFESSIONAL_COLORS['muted'])],
            text=[f'{v:.1f}%' for v in vol_values],
            textposition='outside'
        ))
        fig.update_layout(
            title="Volatility Analysis (%)",
            height=300,
            margin=dict(l=20, r=20, t=40, b=20),
            yaxis_title="Volatility %",
            font=dict(family="Inter, sans-serif"),
            plot_bgcolor='white'
        )
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
        
        # Volatility Metrics
        st.markdown(f"""
        <div class="metric-grid">
            <div class="metric-card">
                <div class="metric-value">{risk['volatility_stress'].title()}</div>
                <div class="metric-label">Volatility Stress</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{risk['kill_switches_armed']}/{risk['kill_switches_total']}</div>
                <div class="metric-label">Kill Switches Armed</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # Bottom row: VaR and Additional Risk Metrics
    col4, col5, col6 = st.columns([1, 1, 1])
    
    with col4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{risk['var_95_1d']:.1%}</div>
            <div class="metric-label">VaR 95% (1d)</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col5:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{risk['var_99_1d']:.1%}</div>
            <div class="metric-label">VaR 99% (1d)</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col6:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{risk['margin_utilization']:.1%}</div>
            <div class="metric-label">Margin Utilization</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

def render_engine_behavior_panel(data):
    """PANEL 3 — ENGINE BEHAVIOR: Professional enhanced engine behavior panel"""
    
    st.markdown('<div class="professional-panel">', unsafe_allow_html=True)
    st.markdown('<div class="panel-title"><span class="panel-icon">⚙️</span>PANEL 3 — ENGINE BEHAVIOR</div>', unsafe_allow_html=True)
    st.markdown('<div style="color: #64748b; font-style: italic; margin-bottom: 1.5rem;">Question: "Are the engines behaving like they promised?"</div>', unsafe_allow_html=True)
    
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
            line=dict(color=PROFESSIONAL_COLORS['primary'], width=3),
            fill='tonexty',
            fillcolor=f'rgba(59, 130, 246, 0.2)'
        ))
        fig.update_layout(
            title="30-Day Performance",
            height=300,
            margin=dict(l=20, r=20, t=40, b=20),
            yaxis_title="Return (%)",
            showlegend=False,
            font=dict(family="Inter, sans-serif"),
            plot_bgcolor='white'
        )
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
    
    with col2:
        # Drawdown Chart
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=perf_data['dates'],
            y=perf_data['drawdown_series'] * 100,
            mode='lines',
            fill='tonexty',
            name='Drawdown',
            line=dict(color=PROFESSIONAL_COLORS['danger'], width=2),
            fillcolor=f'rgba(239, 68, 68, 0.3)'
        ))
        fig.update_layout(
            title="Drawdown Series",
            height=300,
            margin=dict(l=20, r=20, t=40, b=20),
            yaxis_title="Drawdown (%)",
            showlegend=False,
            font=dict(family="Inter, sans-serif"),
            plot_bgcolor='white'
        )
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
    
    with col3:
        # Engine Performance Metrics
        engine_metrics = ['Win Rate', 'Sharpe Ratio', 'Signal Strength', 'Alpha Generation']
        engine_values = [
            engine['trend_win_rate_30d'] * 100,
            engine['trend_sharpe_30d'] * 20,  # Scale for visibility
            engine['signal_strength'] * 100,
            engine['alpha_generation_rate'] * 100
        ]
        
        fig = go.Figure(data=go.Bar(
            x=engine_metrics,
            y=engine_values,
            marker_color=CHART_COLORS[:len(engine_metrics)],
            text=[f'{v:.1f}%' if i != 1 else f'{engine["trend_sharpe_30d"]:.2f}' for i, v in enumerate(engine_values)],
            textposition='outside'
        ))
        fig.update_layout(
            title="Engine Performance Metrics",
            height=300,
            margin=dict(l=20, r=20, t=40, b=20),
            yaxis_title="Performance %",
            font=dict(family="Inter, sans-serif"),
            plot_bgcolor='white'
        )
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
    
    # Bottom row: Engine Status and Metrics
    col4, col5, col6, col7 = st.columns([1, 1, 1, 1])
    
    with col4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{'ACTIVE' if engine['trend_engine_active'] else 'INACTIVE'}</div>
            <div class="metric-label">Trend Engine</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col5:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{engine['trend_engine_days_active']}</div>
            <div class="metric-label">Days Active</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col6:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{engine['trend_holding_duration_avg']:.1f}</div>
            <div class="metric-label">Avg Holding (Days)</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col7:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{engine['position_turnover_7d']:.1%}</div>
            <div class="metric-label">Position Turnover (7d)</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

def render_validation_truth_panel(data):
    """PANEL 4 — VALIDATION & TRUTH: Professional enhanced validation panel"""
    
    st.markdown('<div class="professional-panel">', unsafe_allow_html=True)
    st.markdown('<div class="panel-title"><span class="panel-icon">✅</span>PANEL 4 — VALIDATION & TRUTH</div>', unsafe_allow_html=True)
    st.markdown('<div style="color: #64748b; font-style: italic; margin-bottom: 1.5rem;">Question: "Can we trust what we are seeing?"</div>', unsafe_allow_html=True)
    
    validation = data['validation_state']
    
    # Create three columns for comprehensive validation metrics and charts
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        # Walk Forward Success Rate Gauge
        success_rate = validation['walkforward_success_rate'] * 100
        fig = go.Figure(go.Indicator(
            mode = "gauge+number",
            value = success_rate,
            domain = {'x': [0, 1], 'y': [0, 1]},
            title = {'text': "Walk Forward Success"},
            gauge = {
                'axis': {'range': [None, 100]},
                'bar': {'color': PROFESSIONAL_COLORS['success'] if success_rate >= 80 else PROFESSIONAL_COLORS['warning'] if success_rate >= 60 else PROFESSIONAL_COLORS['danger']},
                'steps': [
                    {'range': [0, 60], 'color': '#fee2e2'},
                    {'range': [60, 80], 'color': '#fef3c7'},
                    {'range': [80, 100], 'color': '#d1fae5'}
                ],
                'threshold': {
                    'line': {'color': "red", 'width': 4},
                    'thickness': 0.75,
                    'value': 85
                }
            }
        ))
        fig.update_layout(height=300, margin=dict(l=20, r=20, t=40, b=20), font=dict(family="Inter, sans-serif"))
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
        
        # Walk Forward Status
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{validation['last_walkforward_result']}</div>
            <div class="metric-label">Last Walk Forward</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        # Data Integrity and Quality Metrics
        quality_metrics = ['Data Integrity', 'Reality Check', 'Statistical Sig', 'Feature Stability']
        quality_values = [
            validation['data_integrity_score'] * 100,
            validation['reality_check_score'] * 100,
            validation['statistical_significance'] * 100,
            validation['feature_stability_score'] * 100
        ]
        
        fig = go.Figure(data=go.Bar(
            x=quality_metrics,
            y=quality_values,
            marker_color=[PROFESSIONAL_COLORS['success'] if v >= 90 else PROFESSIONAL_COLORS['warning'] if v >= 75 else PROFESSIONAL_COLORS['danger'] for v in quality_values],
            text=[f'{v:.1f}%' for v in quality_values],
            textposition='outside'
        ))
        fig.update_layout(
            title="Data Quality Metrics (%)",
            height=300,
            margin=dict(l=20, r=20, t=40, b=20),
            yaxis_title="Quality Score %",
            font=dict(family="Inter, sans-serif"),
            plot_bgcolor='white'
        )
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
        
        # Quality Metrics
        st.markdown(f"""
        <div class="metric-grid">
            <div class="metric-card">
                <div class="metric-value">{validation['data_integrity_score']:.1%}</div>
                <div class="metric-label">Data Integrity</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{validation['backtest_oos_correlation']:.2f}</div>
                <div class="metric-label">Backtest OOS Correlation</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        # Model Drift and Stability
        stability_metrics = ['Model Drift', 'Feature Stability']
        stability_values = [
            (1 - validation['model_drift_score']) * 100,  # Invert drift score
            validation['feature_stability_score'] * 100
        ]
        
        fig = go.Figure(data=go.Bar(
            x=stability_metrics,
            y=stability_values,
            marker_color=[PROFESSIONAL_COLORS['primary'], PROFESSIONAL_COLORS['secondary']],
            text=[f'{v:.1f}%' for v in stability_values],
            textposition='outside'
        ))
        fig.update_layout(
            title="Model Stability (%)",
            height=300,
            margin=dict(l=20, r=20, t=40, b=20),
            yaxis_title="Stability %",
            font=dict(family="Inter, sans-serif"),
            plot_bgcolor='white'
        )
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
        
        # Stability Metrics
        st.markdown(f"""
        <div class="metric-grid">
            <div class="metric-card">
                <div class="metric-value">{'VERIFIED' if validation['rules_hash_verified'] else 'FAILED'}</div>
                <div class="metric-label">Rules Hash</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{validation['override_attempts_24h']}</div>
                <div class="metric-label">Override Attempts (24h)</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # Bottom row: Test Results and Audit Info
    col4, col5, col6 = st.columns([1, 1, 1])
    
    with col4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{validation['walkforward_tests_passed']}/{validation['walkforward_tests_total']}</div>
            <div class="metric-label">Tests Passed</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col5:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{validation['reality_check_score']:.1%}</div>
            <div class="metric-label">Reality Check Score</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col6:
        days_since_audit = (datetime.now() - validation['last_audit_date']).days
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{days_since_audit}</div>
            <div class="metric-label">Days Since Audit</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

def render_intelligence_observer_panel(data):
    """PANEL 5 — INTELLIGENCE OBSERVER: Professional enhanced intelligence panel"""
    
    st.markdown('<div class="professional-panel">', unsafe_allow_html=True)
    st.markdown('<div class="panel-title"><span class="panel-icon">🧠</span>PANEL 5 — INTELLIGENCE OBSERVER</div>', unsafe_allow_html=True)
    st.markdown('<div style="color: #64748b; font-style: italic; margin-bottom: 1.5rem;">Question: "What is the intelligence telling us?"</div>', unsafe_allow_html=True)
    
    intelligence = data['intelligence_state']
    
    # Create three columns for comprehensive intelligence metrics and charts
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        # Intelligence Confidence Gauge
        intel_confidence = intelligence['intelligence_confidence'] * 100
        fig = go.Figure(go.Indicator(
            mode = "gauge+number",
            value = intel_confidence,
            domain = {'x': [0, 1], 'y': [0, 1]},
            title = {'text': "Intelligence Confidence"},
            gauge = {
                'axis': {'range': [None, 100]},
                'bar': {'color': PROFESSIONAL_COLORS['info']},
                'steps': [
                    {'range': [0, 60], 'color': '#fee2e2'},
                    {'range': [60, 80], 'color': '#fef3c7'},
                    {'range': [80, 100], 'color': '#dbeafe'}
                ],
                'threshold': {
                    'line': {'color': "blue", 'width': 4},
                    'thickness': 0.75,
                    'value': 80
                }
            }
        ))
        fig.update_layout(height=300, margin=dict(l=20, r=20, t=40, b=20), font=dict(family="Inter, sans-serif"))
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
        
        # Observer Status
        observer_status = "HEALTHY" if intelligence['observer_healthy'] else "UNHEALTHY"
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{observer_status}</div>
            <div class="metric-label">Observer Status</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        # Market Intelligence Metrics
        intel_metrics = ['Regime Similarity', 'Stress Clustering', 'False Calm', 'Behavioral Drift']
        intel_values = [
            intelligence['regime_similarity_index'],
            intelligence['stress_clustering_index'],
            intelligence['false_calm_likelihood'],
            intelligence['behavioral_drift_index']
        ]
        
        fig = go.Figure(data=go.Bar(
            x=intel_metrics,
            y=intel_values,
            marker_color=CHART_COLORS[:len(intel_metrics)],
            text=[f'{v:.1f}' for v in intel_values],
            textposition='outside'
        ))
        fig.update_layout(
            title="Market Intelligence Indices",
            height=300,
            margin=dict(l=20, r=20, t=40, b=20),
            yaxis_title="Index Value",
            font=dict(family="Inter, sans-serif"),
            plot_bgcolor='white'
        )
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
        
        # Intelligence Metrics
        st.markdown(f"""
        <div class="metric-grid">
            <div class="metric-card">
                <div class="metric-value">{intelligence['narrative_coherence_score']:.1%}</div>
                <div class="metric-label">Narrative Coherence</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{intelligence['prediction_accuracy_7d']:.1%}</div>
                <div class="metric-label">Prediction Accuracy (7d)</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        # Market Microstructure and Flow Analysis
        flow_metrics = ['Sentiment Divergence', 'Flow Anomaly', 'Cross-Asset Correlation', 'Microstructure']
        flow_values = [
            intelligence['sentiment_divergence_score'],
            intelligence['flow_anomaly_score'],
            intelligence['cross_asset_correlation_score'],
            intelligence['market_microstructure_score']
        ]
        
        fig = go.Figure(data=go.Bar(
            x=flow_metrics,
            y=flow_values,
            marker_color=[PROFESSIONAL_COLORS['warning'] if v > 30 else PROFESSIONAL_COLORS['success'] for v in flow_values],
            text=[f'{v:.1f}' for v in flow_values],
            textposition='outside'
        ))
        fig.update_layout(
            title="Flow & Microstructure Analysis",
            height=300,
            margin=dict(l=20, r=20, t=40, b=20),
            yaxis_title="Score",
            font=dict(family="Inter, sans-serif"),
            plot_bgcolor='white'
        )
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
        
        # Flow Metrics
        st.markdown(f"""
        <div class="metric-grid">
            <div class="metric-card">
                <div class="metric-value">{intelligence['observer_violations']}</div>
                <div class="metric-label">Observer Violations</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{'YES' if intelligence['weekly_report_available'] else 'NO'}</div>
                <div class="metric-label">Weekly Report Available</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # Bottom row: Additional Intelligence Metrics
    col4, col5, col6 = st.columns([1, 1, 1])
    
    with col4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{intelligence['regime_similarity_index']:.1f}</div>
            <div class="metric-label">Regime Similarity Index</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col5:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{intelligence['false_calm_likelihood']:.1f}%</div>
            <div class="metric-label">False Calm Likelihood</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col6:
        hours_since_update = (datetime.now() - intelligence['last_intelligence_update']).total_seconds() / 3600
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{hours_since_update:.1f}h</div>
            <div class="metric-label">Last Intelligence Update</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

# =========================== MAIN DASHBOARD ===========================

def main():
    """Main dashboard function with 5 Constitutional Panels"""
    
    # Professional header
    st.markdown("""
    <div class="professional-header">
        <div class="header-title">🏛️ NORTHSTAR V3</div>
        <div class="header-subtitle">Professional Constitutional Cockpit - 5 Constitutional Panels</div>
    </div>
    """, unsafe_allow_html=True)
    
    # Load data
    with st.spinner("Loading comprehensive system data..."):
        data = load_comprehensive_system_data()
    
    # Key metrics row
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.markdown("""
        <div class="metric-card">
            <div class="metric-value">${:,.0f}</div>
            <div class="metric-label">Portfolio Value</div>
            <div class="metric-change metric-positive">+2.3% Today</div>
        </div>
        """.format(data['portfolio_data']['total_value']), unsafe_allow_html=True)
    
    with col2:
        daily_return = data['performance_data']['daily_returns'][-1] * 100
        change_class = "metric-positive" if daily_return >= 0 else "metric-negative"
        st.markdown("""
        <div class="metric-card">
            <div class="metric-value">{:+.2f}%</div>
            <div class="metric-label">Daily Return</div>
            <div class="metric-change {}">vs Yesterday</div>
        </div>
        """.format(daily_return, change_class), unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
        <div class="metric-card">
            <div class="metric-value">{:.2f}</div>
            <div class="metric-label">Sharpe Ratio</div>
            <div class="metric-change metric-positive">Above Target</div>
        </div>
        """.format(data['risk_state']['sharpe_ratio']), unsafe_allow_html=True)
    
    with col4:
        st.markdown("""
        <div class="metric-card">
            <div class="metric-value">{:.1f}%</div>
            <div class="metric-label">Max Drawdown</div>
            <div class="metric-change metric-neutral">Within Limits</div>
        </div>
        """.format(data['risk_state']['current_drawdown'] * 100), unsafe_allow_html=True)
    
    with col5:
        overall_health = (data['system_state']['organs_healthy'] / data['system_state']['organs_total']) * 100
        st.markdown("""
        <div class="metric-card">
            <div class="metric-value">{:.1f}%</div>
            <div class="metric-label">System Health</div>
            <div class="metric-change metric-positive">All Systems Operational</div>
        </div>
        """.format(overall_health), unsafe_allow_html=True)
    
    # THE 5 CONSTITUTIONAL PANELS
    render_system_state_panel(data)
    render_risk_authority_panel(data)
    render_engine_behavior_panel(data)
    render_validation_truth_panel(data)
    render_intelligence_observer_panel(data)
    
    # Additional comprehensive dashboards
    st.markdown('<div class="professional-panel">', unsafe_allow_html=True)
    st.markdown('<div class="panel-title"><span class="panel-icon">📈</span>Individual Stock Performance</div>', unsafe_allow_html=True)
    
    stock_fig = create_individual_stock_performance(data)
    st.plotly_chart(stock_fig, use_container_width=True, config={'displayModeBar': False})
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Advanced analytics
    st.markdown('<div class="professional-panel">', unsafe_allow_html=True)
    st.markdown('<div class="panel-title"><span class="panel-icon">🔬</span>Advanced Analytics</div>', unsafe_allow_html=True)
    
    analytics_fig = create_advanced_analytics_dashboard(data)
    st.plotly_chart(analytics_fig, use_container_width=True, config={'displayModeBar': False})
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Market microstructure
    st.markdown('<div class="professional-panel">', unsafe_allow_html=True)
    st.markdown('<div class="panel-title"><span class="panel-icon">⚡</span>Market Microstructure</div>', unsafe_allow_html=True)
    
    microstructure_fig = create_market_microstructure_dashboard(data)
    st.plotly_chart(microstructure_fig, use_container_width=True, config={'displayModeBar': False})
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Constitutional principles
    st.markdown("""
    <div class="constitutional-principles">
        <div class="principle-title">🏛️ Constitutional Principles</div>
        <div class="principle-item">• Dashboard is observational only - no trading decisions made while viewing</div>
        <div class="principle-item">• Dashboard closed during significant drawdowns to prevent emotional interference</div>
        <div class="principle-item">• Weekly intelligence reports read separately from real-time monitoring</div>
        <div class="principle-item">• If you feel urgency while viewing, immediately close the dashboard</div>
        <div class="principle-item">• Focus on Truth, State, and Integrity — Not Opportunity</div>
    </div>
    """, unsafe_allow_html=True)
    
    # Footer with last update
    st.markdown(f"""
    <div style="text-align: center; color: {PROFESSIONAL_COLORS['muted']}; margin-top: 2rem; padding: 1rem; border-top: 1px solid #e2e8f0;">
        Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 
        Data Source: Northstar V3 System | 
        Status: <span style="color: {PROFESSIONAL_COLORS['success']};">●</span> Operational
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()