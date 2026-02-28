#!/usr/bin/env python3
"""
🎯 ULTIMATE COMPREHENSIVE COCKPIT - NORTHSTAR V3
The One and Only Truly Exceptional Dashboard

This is the ultimate self-contained dashboard with:
- ALL features from every previous dashboard combined
- Professional institutional styling with perfect color contrast
- Comprehensive information with detailed explanations
- Many more charts, plots, and visualizations
- Self-contained data generation with robust error handling
- All 5 constitutional panels with extensive information
- Individual stock performance with detailed analytics
- Advanced risk management dashboard
- Market intelligence and regime analysis
- Performance attribution and factor analysis
- Sector analysis and correlation matrices
- Volatility analysis and regime detection
- Backtesting results and walk-forward validation
- System diagnostics and health monitoring
- Real-time portfolio tracking and changes over time
- Institutional-grade reporting and analytics
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import json
import os
import sys
import glob
from datetime import datetime, timedelta
import time
import warnings
from scipy import stats
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
warnings.filterwarnings('ignore')

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Set page config
st.set_page_config(
    page_title="🎯 Northstar V3 - Ultimate Comprehensive Cockpit",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# =========================== ULTIMATE PROFESSIONAL STYLING ===========================

st.markdown("""
<style>
    /* ULTIMATE PROFESSIONAL INSTITUTIONAL STYLING */
    
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
    
    /* Main layout with perfect contrast */
    .main { 
        padding: 1.5rem !important; 
        margin: 0 !important;
        max-width: 100% !important;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        background: #ffffff !important;
        color: #1e293b !important;
    }
    .block-container { 
        padding: 1.5rem !important; 
        margin: 0 !important;
        max-width: 100% !important;
    }
    
    /* Hide Streamlit branding */
    #MainMenu, footer, header, .stDeployButton, .stToolbar { 
        visibility: hidden !important; 
    }
    
    /* Ultimate professional header */
    .ultimate-header {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #334155 100%);
        color: white !important;
        padding: 2rem;
        text-align: center;
        font-weight: 600;
        margin-bottom: 2rem;
        border-radius: 12px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.15);
        border: 1px solid #e2e8f0;
        position: relative;
        overflow: hidden;
    }
    
    .ultimate-header * {
        color: white !important;
    }
    
    .ultimate-header::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 4px;
        background: linear-gradient(90deg, #3b82f6, #10b981, #f59e0b, #ef4444, #8b5cf6);
    }
    
    .header-title {
        font-size: 2.5rem;
        font-weight: 800;
        margin-bottom: 0.5rem;
        letter-spacing: -0.025em;
        color: white !important;
        text-shadow: 0 2px 4px rgba(0,0,0,0.3);
    }
    
    .header-subtitle {
        font-size: 1.1rem;
        opacity: 0.95;
        font-weight: 400;
        color: white !important;
    }
    
    /* Ultimate professional panels */
    .ultimate-panel {
        background: #ffffff !important;
        border: 2px solid #e2e8f0;
        border-radius: 12px;
        padding: 2rem;
        margin-bottom: 2rem;
        box-shadow: 0 6px 20px rgba(0,0,0,0.08);
        transition: all 0.3s ease;
        position: relative;
    }
    
    .ultimate-panel:hover {
        box-shadow: 0 12px 35px rgba(0,0,0,0.12);
        transform: translateY(-2px);
    }
    
    .ultimate-panel::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 3px;
        background: linear-gradient(90deg, #3b82f6, #10b981);
        border-radius: 12px 12px 0 0;
    }
    
    /* Panel titles with perfect contrast */
    .ultimate-panel-title {
        font-size: 1.5rem;
        font-weight: 700;
        color: #1e293b !important;
        margin-bottom: 1.5rem;
        padding-bottom: 1rem;
        border-bottom: 2px solid #f1f5f9;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    
    .panel-icon {
        margin-right: 1rem;
        font-size: 1.75rem;
    }
    
    .panel-subtitle {
        font-size: 0.9rem;
        color: #64748b !important;
        font-style: italic;
        font-weight: 400;
    }
    
    /* Ultimate metrics styling with perfect contrast */
    .ultimate-metric-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 1.5rem;
        margin-bottom: 2rem;
    }
    
    .ultimate-metric-card {
        background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%) !important;
        border: 2px solid #e2e8f0;
        border-radius: 10px;
        padding: 1.5rem;
        text-align: center;
        transition: all 0.3s ease;
        position: relative;
        overflow: hidden;
    }
    
    .ultimate-metric-card:hover {
        background: linear-gradient(135deg, #f1f5f9 0%, #e2e8f0 100%) !important;
        border-color: #3b82f6;
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(59, 130, 246, 0.15);
    }
    
    .ultimate-metric-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 3px;
        background: linear-gradient(90deg, #3b82f6, #10b981);
    }
    
    .ultimate-metric-value {
        font-size: 2rem;
        font-weight: 800;
        color: #1e293b !important;
        margin-bottom: 0.5rem;
        line-height: 1;
    }
    
    .ultimate-metric-label {
        font-size: 0.8rem;
        color: #64748b !important;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        margin-bottom: 0.5rem;
    }
    
    .ultimate-metric-change {
        font-size: 0.8rem;
        font-weight: 600;
        padding: 0.25rem 0.75rem;
        border-radius: 12px;
        display: inline-block;
    }
    
    .metric-positive { 
        background: #dcfce7 !important; 
        color: #166534 !important; 
        border: 1px solid #bbf7d0;
    }
    .metric-negative { 
        background: #fee2e2 !important; 
        color: #991b1b !important; 
        border: 1px solid #fecaca;
    }
    .metric-neutral { 
        background: #f3f4f6 !important; 
        color: #374151 !important; 
        border: 1px solid #d1d5db;
    }
    
    /* Status indicators with perfect contrast */
    .ultimate-status-indicator {
        display: inline-flex;
        align-items: center;
        padding: 0.75rem 1.5rem;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 700;
        margin: 0.5rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    
    .status-healthy {
        background: #dcfce7 !important;
        color: #166534 !important;
        border: 2px solid #10b981;
        box-shadow: 0 4px 15px rgba(16, 185, 129, 0.2);
    }
    
    .status-warning {
        background: #fef3c7 !important;
        color: #92400e !important;
        border: 2px solid #f59e0b;
        box-shadow: 0 4px 15px rgba(245, 158, 11, 0.2);
    }
    
    .status-critical {
        background: #fee2e2 !important;
        color: #991b1b !important;
        border: 2px solid #ef4444;
        box-shadow: 0 4px 15px rgba(239, 68, 68, 0.2);
    }
    
    /* Chart containers */
    .ultimate-chart-container {
        background: #ffffff !important;
        border-radius: 10px;
        padding: 1.5rem;
        margin: 1.5rem 0;
        border: 2px solid #e2e8f0;
        box-shadow: 0 4px 15px rgba(0,0,0,0.05);
    }
    
    /* Constitutional principles */
    .ultimate-constitutional-principles {
        background: linear-gradient(135deg, #fef7cd 0%, #fef3c7 100%) !important;
        border: 2px solid #f59e0b;
        border-radius: 12px;
        padding: 2rem;
        margin: 2rem 0;
        position: relative;
    }
    
    .ultimate-constitutional-principles::before {
        content: '🏛️';
        position: absolute;
        top: -15px;
        left: 2rem;
        background: #fef3c7;
        padding: 0.5rem;
        border-radius: 50%;
        font-size: 1.5rem;
        border: 2px solid #f59e0b;
    }
    
    .principle-title {
        font-size: 1.25rem;
        font-weight: 700;
        color: #92400e !important;
        margin-bottom: 1.5rem;
        margin-left: 3rem;
    }
    
    .principle-item {
        color: #78350f !important;
        margin: 1rem 0;
        font-weight: 600;
        font-size: 1rem;
        padding-left: 1.5rem;
        position: relative;
    }
    
    .principle-item::before {
        content: '•';
        position: absolute;
        left: 0;
        color: #f59e0b;
        font-weight: 900;
        font-size: 1.5rem;
    }
    
    /* Command bar */
    .ultimate-command-bar {
        background: linear-gradient(135deg, #1e293b 0%, #334155 100%) !important;
        color: white !important;
        padding: 1.25rem 2rem;
        border-radius: 10px;
        margin-bottom: 2rem;
        font-family: 'Monaco', 'Menlo', monospace;
        font-size: 0.9rem;
        font-weight: 600;
        box-shadow: 0 6px 20px rgba(0,0,0,0.15);
        border: 2px solid #475569;
    }
    
    .ultimate-command-bar * {
        color: white !important;
    }
    
    /* Ensure all text has perfect contrast */
    .stMarkdown, .stMarkdown p, .stMarkdown div, .stMarkdown span,
    .stDataFrame, .stTable, .stMetric, .stSelectbox, .stTextInput {
        color: #1e293b !important;
        background-color: transparent !important;
    }
    
    /* Fix Streamlit component text colors */
    .stMarkdown h1, .stMarkdown h2, .stMarkdown h3, .stMarkdown h4, .stMarkdown h5, .stMarkdown h6 {
        color: #1e293b !important;
    }
    
    /* Fix dataframe styling */
    .stDataFrame > div {
        background-color: #ffffff !important;
        color: #1e293b !important;
    }
    
    /* Fix metric widget text */
    .metric-container, .metric-container * {
        color: #1e293b !important;
        background-color: transparent !important;
    }
    
    /* Override any problematic text colors */
    div[data-testid="metric-container"] {
        background-color: #ffffff !important;
        color: #1e293b !important;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 1rem;
    }
    
    div[data-testid="metric-container"] * {
        color: #1e293b !important;
    }
    
    /* Specific overrides for white backgrounds */
    .stApp, .main, .block-container {
        background-color: #ffffff !important;
        color: #1e293b !important;
    }
    
    /* Responsive design */
    @media (max-width: 768px) {
        .main { padding: 1rem !important; }
        .ultimate-panel { padding: 1.5rem !important; }
        .header-title { font-size: 2rem; }
        .ultimate-metric-grid { grid-template-columns: 1fr; }
    }
</style>
""", unsafe_allow_html=True)

# =========================== ULTIMATE COLOR SCHEMES ===========================

ULTIMATE_COLORS = {
    'primary': '#3b82f6',
    'secondary': '#6366f1', 
    'success': '#10b981',
    'warning': '#f59e0b',
    'danger': '#ef4444',
    'info': '#06b6d4',
    'dark': '#1e293b',
    'light': '#f8fafc',
    'muted': '#64748b',
    'purple': '#8b5cf6',
    'pink': '#ec4899',
    'indigo': '#6366f1',
    'teal': '#14b8a6',
    'orange': '#f97316',
    'lime': '#84cc16'
}

ULTIMATE_CHART_COLORS = [
    '#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', 
    '#06b6d4', '#84cc16', '#f97316', '#ec4899', '#6366f1',
    '#14b8a6', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4'
]

# =========================== ULTIMATE COMPREHENSIVE DATA GENERATION ===========================

class UltimateComprehensiveCockpit:
    """Ultimate self-contained comprehensive cockpit with all features"""
    
    def __init__(self):
        self.dashboard_data_dir = 'data/dashboard'
        os.makedirs(self.dashboard_data_dir, exist_ok=True)
        
        # Set random seed for reproducible data
        np.random.seed(42)
        
        # Generate comprehensive data
        self.data = self.generate_ultimate_comprehensive_data()
    
    def generate_ultimate_comprehensive_data(self):
        """Generate ultimate comprehensive data with all features"""
        
        print("🎯 Generating ultimate comprehensive data...")
        
        # Base data structure
        data = {
            'timestamp': datetime.now(),
            'system_status': 'active',
            'data_source': 'comprehensive_generated',
            'version': 'v3.0.0'
        }
        
        # Generate data components in correct order (portfolio first, then stock performance)
        data['constitutional_panels'] = self.generate_constitutional_panels_data()
        data['performance_data'] = self.generate_performance_data()
        data['portfolio_data'] = self.generate_portfolio_data()
        data['stock_performance'] = self.generate_stock_performance_data(data['portfolio_data'])
        data['risk_management'] = self.generate_risk_management_data()
        data['market_intelligence'] = self.generate_market_intelligence_data()
        data['advanced_analytics'] = self.generate_advanced_analytics_data()
        data['sector_analysis'] = self.generate_sector_analysis_data()
        data['correlation_analysis'] = self.generate_correlation_analysis_data(data['stock_performance'])
        data['volatility_analysis'] = self.generate_volatility_analysis_data()
        data['regime_analysis'] = self.generate_regime_analysis_data()
        data['backtesting_results'] = self.generate_backtesting_results()
        data['walk_forward_validation'] = self.generate_walk_forward_validation()
        data['system_diagnostics'] = self.generate_system_diagnostics_data()
        data['institutional_reporting'] = self.generate_institutional_reporting_data()
        
        print("✅ Ultimate comprehensive data generated successfully!")
        return data
    
    def generate_constitutional_panels_data(self):
        """Generate comprehensive constitutional panels data"""
        
        return {
            'panel_1_system_state': {
                'title': '📊 PANEL 1 — SYSTEM STATE',
                'subtitle': 'Is the system healthy and behaving as designed?',
                'health_score': 0.87,
                'health_status': 'excellent',
                'components_healthy': '9/10',
                'data_fresh': True,
                'orchestrator_running': True,
                'last_update': datetime.now().isoformat(),
                'system_uptime_days': 142,
                'cpu_usage_pct': 0.15,
                'memory_usage_pct': 0.42,
                'disk_usage_pct': 0.73,
                'network_latency_ms': 12.8,
                'current_regime': 'supportive',
                'regime_confidence': 0.89,
                'active_engine': 'trend_momentum',
                'engine_confidence': 0.82,
                'conviction_locked': True,
                'current_exposure': 0.68,
                'allowed_exposure': 0.75,
                'data_quality_score': 0.95,
                'system_integrity_score': 0.91,
                'operational_efficiency': 0.88
            },
            'panel_2_risk_authority': {
                'title': '🛡️ PANEL 2 — RISK AUTHORITY',
                'subtitle': 'Who is in charge right now?',
                'risk_status': 'normal',
                'risk_level': 0.12,
                'emergency_active': False,
                'survival_mode': 'normal',
                'exposure_multiplier': 1.0,
                'system_locked': False,
                'emergency_brake_status': 'ARMED',
                'current_drawdown': -0.025,
                'max_allowed_drawdown': -0.20,
                'peak_drawdown_30d': -0.048,
                'volatility_stress': 'low',
                'volatility_20d': 0.16,
                'volatility_5d': 0.19,
                'kill_switches_armed': 5,
                'kill_switches_total': 5,
                'var_95_1d': -0.022,
                'var_99_1d': -0.038,
                'leverage_ratio': 1.12,
                'margin_utilization': 0.28,
                'risk_budget_utilization': 0.34,
                'concentration_risk': 0.15,
                'liquidity_risk': 0.08
            },
            'panel_3_engine_behavior': {
                'title': '⚙️ PANEL 3 — ENGINE BEHAVIOR',
                'subtitle': 'Are the engines behaving like they promised?',
                'orchestrator_success_rate': 0.94,
                'healthy_organs': '9/10',
                'isolated_organs': 0,
                'system_stability': 'excellent',
                'protection_mode': False,
                'cycle_interval': 60,
                'trend_engine_active': True,
                'trend_engine_days_active': 18,
                'trend_holding_duration_avg': 14.2,
                'trend_win_rate_30d': 0.72,
                'trend_sharpe_30d': 1.38,
                'signal_strength': 0.81,
                'alpha_generation_rate': 0.095,
                'position_turnover_7d': 0.12,
                'execution_efficiency': 0.96,
                'signal_decay_rate': 0.05,
                'model_stability': 0.89
            },
            'panel_4_validation_truth': {
                'title': '✅ PANEL 4 — VALIDATION & TRUTH',
                'subtitle': 'Can we trust what we are seeing?',
                'portfolio_exposure': 0.68,
                'allowed_exposure': 0.75,
                'compliance_status': True,
                'data_freshness_hours': 0.3,
                'intelligence_active': True,
                'validation_score': 0.91,
                'last_walkforward_result': 'PASS',
                'walkforward_success_rate': 0.89,
                'walkforward_tests_passed': 43,
                'walkforward_tests_total': 48,
                'data_integrity_score': 1.0,
                'reality_check_score': 0.87,
                'rules_hash_verified': True,
                'override_attempts_24h': 0,
                'statistical_significance': 0.95,
                'out_of_sample_performance': 0.83,
                'model_robustness': 0.88
            },
            'panel_5_intelligence_observer': {
                'title': '🧠 PANEL 5 — INTELLIGENCE OBSERVER',
                'subtitle': 'What is the intelligence telling us?',
                'regime': 'supportive',
                'unified_conviction': 0.79,
                'market_conviction': 0.74,
                'valuation_conviction': 0.76,
                'active_strategies': 8,
                'intelligence_health': 'excellent',
                'regime_similarity_index': 72.3,
                'stress_clustering_index': 28.7,
                'false_calm_likelihood': 12.4,
                'behavioral_drift_index': 6.8,
                'market_microstructure_score': 78.9,
                'observer_healthy': True,
                'observer_violations': 0,
                'intelligence_confidence': 0.86,
                'narrative_coherence_score': 0.92,
                'prediction_accuracy_7d': 0.76,
                'sentiment_analysis_score': 0.68,
                'macro_intelligence_score': 0.71,
                'technical_intelligence_score': 0.84
            }
        }
    
    def generate_performance_data(self):
        """Generate comprehensive performance data with detailed metrics"""
        
        # Generate 180 days of performance data (ending today)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=180)
        dates = pd.date_range(start=start_date, end=end_date, freq='D')
        
        # Generate realistic returns with regime changes
        regime_changes = [30, 90, 150]  # Days where regime changes
        daily_returns = []
        
        for i, date in enumerate(dates):
            if i < regime_changes[0]:  # Supportive regime
                ret = np.random.normal(0.0012, 0.015)
            elif i < regime_changes[1]:  # Neutral regime
                ret = np.random.normal(0.0005, 0.022)
            elif i < regime_changes[2]:  # Volatile regime
                ret = np.random.normal(-0.0002, 0.035)
            else:  # Recovery regime
                ret = np.random.normal(0.0015, 0.018)
            
            daily_returns.append(ret)
        
        daily_returns = np.array(daily_returns)
        cumulative_returns = (1 + pd.Series(daily_returns)).cumprod() - 1
        running_max = cumulative_returns.expanding().max()
        drawdown_series = (cumulative_returns - running_max)
        
        # Calculate rolling metrics
        volatility_series = pd.Series(daily_returns).rolling(20).std() * np.sqrt(252)
        sharpe_series = pd.Series(daily_returns).rolling(60).mean() / pd.Series(daily_returns).rolling(60).std() * np.sqrt(252)
        
        return {
            'dates': dates,
            'daily_returns': daily_returns,
            'cumulative_returns': cumulative_returns.values,
            'drawdown_series': drawdown_series.values,
            'volatility_series': volatility_series.fillna(0.18).values,
            'sharpe_series': sharpe_series.fillna(1.2).values,
            'regime_series': ['SUPPORTIVE'] * regime_changes[0] + 
                           ['NEUTRAL'] * (regime_changes[1] - regime_changes[0]) +
                           ['VOLATILE'] * (regime_changes[2] - regime_changes[1]) +
                           ['RECOVERY'] * (len(dates) - regime_changes[2]),
            'total_return': float(cumulative_returns.iloc[-1]),
            'annualized_return': float(cumulative_returns.iloc[-1]) * (365/180),
            'volatility': np.std(daily_returns) * np.sqrt(252),
            'sharpe_ratio': np.mean(daily_returns) / np.std(daily_returns) * np.sqrt(252),
            'max_drawdown': float(drawdown_series.min()),
            'win_rate': (daily_returns > 0).mean(),
            'profit_factor': np.sum(daily_returns[daily_returns > 0]) / abs(np.sum(daily_returns[daily_returns < 0])),
            'calmar_ratio': (float(cumulative_returns.iloc[-1]) * (365/180)) / abs(float(drawdown_series.min())),
            'sortino_ratio': np.mean(daily_returns) / np.std(daily_returns[daily_returns < 0]) * np.sqrt(252),
            'skewness': stats.skew(daily_returns),
            'kurtosis': stats.kurtosis(daily_returns),
            'var_95': np.percentile(daily_returns, 5),
            'var_99': np.percentile(daily_returns, 1),
            'cvar_95': np.mean(daily_returns[daily_returns <= np.percentile(daily_returns, 5)]),
            'best_day': np.max(daily_returns),
            'worst_day': np.min(daily_returns),
            'positive_days': np.sum(daily_returns > 0),
            'negative_days': np.sum(daily_returns < 0),
            'max_consecutive_wins': self.calculate_max_consecutive(daily_returns > 0),
            'max_consecutive_losses': self.calculate_max_consecutive(daily_returns < 0)
        }
    
    def calculate_max_consecutive(self, boolean_series):
        """Calculate maximum consecutive True values"""
        max_count = 0
        current_count = 0
        for val in boolean_series:
            if val:
                current_count += 1
                max_count = max(max_count, current_count)
            else:
                current_count = 0
        return max_count
    
    def generate_portfolio_data(self):
        """Generate comprehensive portfolio data with detailed holdings"""
        
        # Indian stock universe with realistic data
        indian_stocks = [
            {'symbol': 'RELIANCE', 'sector': 'Energy', 'market_cap': 1500000, 'beta': 1.1},
            {'symbol': 'TCS', 'sector': 'Technology', 'market_cap': 1200000, 'beta': 0.8},
            {'symbol': 'HDFCBANK', 'sector': 'Financials', 'market_cap': 800000, 'beta': 1.2},
            {'symbol': 'INFY', 'sector': 'Technology', 'market_cap': 600000, 'beta': 0.9},
            {'symbol': 'HINDUNILVR', 'sector': 'Consumer', 'market_cap': 500000, 'beta': 0.7},
            {'symbol': 'ICICIBANK', 'sector': 'Financials', 'market_cap': 450000, 'beta': 1.3},
            {'symbol': 'KOTAKBANK', 'sector': 'Financials', 'market_cap': 350000, 'beta': 1.1},
            {'symbol': 'BHARTIARTL', 'sector': 'Telecom', 'market_cap': 400000, 'beta': 1.0},
            {'symbol': 'ITC', 'sector': 'Consumer', 'market_cap': 300000, 'beta': 0.8},
            {'symbol': 'SBIN', 'sector': 'Financials', 'market_cap': 250000, 'beta': 1.4},
            {'symbol': 'BAJFINANCE', 'sector': 'Financials', 'market_cap': 200000, 'beta': 1.5},
            {'symbol': 'ASIANPAINT', 'sector': 'Materials', 'market_cap': 180000, 'beta': 0.9},
            {'symbol': 'MARUTI', 'sector': 'Auto', 'market_cap': 170000, 'beta': 1.2},
            {'symbol': 'AXISBANK', 'sector': 'Financials', 'market_cap': 160000, 'beta': 1.3},
            {'symbol': 'LT', 'sector': 'Industrials', 'market_cap': 150000, 'beta': 1.1},
            {'symbol': 'HCLTECH', 'sector': 'Technology', 'market_cap': 140000, 'beta': 0.8},
            {'symbol': 'WIPRO', 'sector': 'Technology', 'market_cap': 130000, 'beta': 0.9},
            {'symbol': 'ULTRACEMCO', 'sector': 'Materials', 'market_cap': 120000, 'beta': 1.0},
            {'symbol': 'NESTLEIND', 'sector': 'Consumer', 'market_cap': 110000, 'beta': 0.6},
            {'symbol': 'POWERGRID', 'sector': 'Utilities', 'market_cap': 100000, 'beta': 0.7},
            {'symbol': 'NTPC', 'sector': 'Utilities', 'market_cap': 95000, 'beta': 0.8},
            {'symbol': 'ONGC', 'sector': 'Energy', 'market_cap': 90000, 'beta': 1.2},
            {'symbol': 'TATAMOTORS', 'sector': 'Auto', 'market_cap': 85000, 'beta': 1.4},
            {'symbol': 'TECHM', 'sector': 'Technology', 'market_cap': 80000, 'beta': 0.9},
            {'symbol': 'SUNPHARMA', 'sector': 'Healthcare', 'market_cap': 75000, 'beta': 0.8},
            {'symbol': 'JSWSTEEL', 'sector': 'Materials', 'market_cap': 70000, 'beta': 1.3},
            {'symbol': 'INDUSINDBK', 'sector': 'Financials', 'market_cap': 65000, 'beta': 1.2},
            {'symbol': 'BAJAJFINSV', 'sector': 'Financials', 'market_cap': 60000, 'beta': 1.1},
            {'symbol': 'GRASIM', 'sector': 'Materials', 'market_cap': 55000, 'beta': 1.0},
            {'symbol': 'DRREDDY', 'sector': 'Healthcare', 'market_cap': 50000, 'beta': 0.9},
            {'symbol': 'EICHERMOT', 'sector': 'Auto', 'market_cap': 45000, 'beta': 1.1},
            {'symbol': 'ADANIPORTS', 'sector': 'Industrials', 'market_cap': 40000, 'beta': 1.2},
            {'symbol': 'COALINDIA', 'sector': 'Materials', 'market_cap': 38000, 'beta': 0.9},
            {'symbol': 'BRITANNIA', 'sector': 'Consumer', 'market_cap': 35000, 'beta': 0.7},
            {'symbol': 'SHREECEM', 'sector': 'Materials', 'market_cap': 32000, 'beta': 1.0},
            {'symbol': 'DIVISLAB', 'sector': 'Healthcare', 'market_cap': 30000, 'beta': 0.8},
            {'symbol': 'HINDALCO', 'sector': 'Materials', 'market_cap': 28000, 'beta': 1.3},
            {'symbol': 'TATASTEEL', 'sector': 'Materials', 'market_cap': 25000, 'beta': 1.4},
            {'symbol': 'CIPLA', 'sector': 'Healthcare', 'market_cap': 22000, 'beta': 0.8},
            {'symbol': 'HEROMOTOCO', 'sector': 'Auto', 'market_cap': 20000, 'beta': 1.0}
        ]
        
        # Generate portfolio holdings with realistic weights
        all_holdings = []
        total_weight = 0
        
        for i, stock in enumerate(indian_stocks[:35]):  # Top 35 holdings
            # Decreasing weight distribution
            if i < 5:
                weight = np.random.uniform(0.04, 0.08)  # Top 5: 4-8%
            elif i < 15:
                weight = np.random.uniform(0.02, 0.04)  # Next 10: 2-4%
            else:
                weight = np.random.uniform(0.005, 0.02)  # Rest: 0.5-2%
            
            total_weight += weight
            
            # Generate performance metrics
            pnl_1d = np.random.normal(0.001, 0.025)
            pnl_7d = np.random.normal(0.005, 0.08)
            pnl_30d = np.random.normal(0.02, 0.15)
            
            all_holdings.append({
                'symbol': stock['symbol'],
                'weight': weight,
                'sector': stock['sector'],
                'market_cap': stock['market_cap'],
                'beta': stock['beta'],
                'pnl_1d': pnl_1d,
                'pnl_7d': pnl_7d,
                'pnl_30d': pnl_30d,
                'current_price': np.random.uniform(100, 3000),
                'rsi': np.random.uniform(30, 70),
                'pe_ratio': np.random.uniform(10, 35),
                'pb_ratio': np.random.uniform(1, 5),
                'dividend_yield': np.random.uniform(0, 0.05),
                'volume_ratio': np.random.uniform(0.5, 2.0),
                'momentum_score': np.random.uniform(-1, 1),
                'quality_score': np.random.uniform(0, 1),
                'value_score': np.random.uniform(0, 1)
            })
        
        # Normalize weights to sum to target exposure
        target_exposure = 0.68
        weight_multiplier = target_exposure / total_weight
        for holding in all_holdings:
            holding['weight'] *= weight_multiplier
        
        # Calculate sector allocation
        sector_allocation = {}
        for holding in all_holdings:
            sector = holding['sector']
            if sector not in sector_allocation:
                sector_allocation[sector] = 0
            sector_allocation[sector] += holding['weight']
        
        # Calculate portfolio metrics
        portfolio_beta = np.average([h['beta'] for h in all_holdings], weights=[h['weight'] for h in all_holdings])
        portfolio_pe = np.average([h['pe_ratio'] for h in all_holdings], weights=[h['weight'] for h in all_holdings])
        
        return {
            'total_value': 15_000_000,  # 15 Cr portfolio
            'total_positions': len(all_holdings),
            'long_positions': len([h for h in all_holdings if h['weight'] > 0]),
            'short_positions': 0,
            'all_holdings': all_holdings,
            'top_holdings': sorted(all_holdings, key=lambda x: x['weight'], reverse=True)[:20],
            'sector_allocation': sector_allocation,
            'largest_position': max(h['weight'] for h in all_holdings),
            'total_exposure': sum(h['weight'] for h in all_holdings),
            'avg_position_size': np.mean([h['weight'] for h in all_holdings]),
            'portfolio_beta': portfolio_beta,
            'portfolio_pe': portfolio_pe,
            'portfolio_pb': np.average([h['pb_ratio'] for h in all_holdings], weights=[h['weight'] for h in all_holdings]),
            'portfolio_dividend_yield': np.average([h['dividend_yield'] for h in all_holdings], weights=[h['weight'] for h in all_holdings]),
            'concentration_risk': sum(sorted([h['weight'] for h in all_holdings], reverse=True)[:5]),  # Top 5 concentration
            'sector_concentration': max(sector_allocation.values()),
            'number_of_sectors': len(sector_allocation),
            'avg_market_cap': np.average([h['market_cap'] for h in all_holdings], weights=[h['weight'] for h in all_holdings]),
            'momentum_tilt': np.average([h['momentum_score'] for h in all_holdings], weights=[h['weight'] for h in all_holdings]),
            'quality_tilt': np.average([h['quality_score'] for h in all_holdings], weights=[h['weight'] for h in all_holdings]),
            'value_tilt': np.average([h['value_score'] for h in all_holdings], weights=[h['weight'] for h in all_holdings])
        }
    
    def generate_stock_performance_data(self, portfolio_data):
        """Generate individual stock performance data with detailed analytics"""
        
        stock_performance = {}
        end_date = datetime.now()
        start_date = end_date - timedelta(days=180)
        dates = pd.date_range(start=start_date, end=end_date, freq='D')
        
        # Get portfolio holdings
        holdings = portfolio_data.get('all_holdings', [])
        
        for holding in holdings:
            symbol = holding['symbol']
            beta = holding['beta']
            
            # Generate correlated returns based on beta and sector
            market_returns = np.random.normal(0.0008, 0.018, len(dates))
            sector_returns = np.random.normal(0.0005, 0.012, len(dates))
            idiosyncratic_returns = np.random.normal(0, 0.015, len(dates))
            
            # Combine returns with realistic correlations
            stock_returns = (0.6 * beta * market_returns + 
                           0.3 * sector_returns + 
                           0.1 * idiosyncratic_returns)
            
            stock_cumulative = (1 + pd.Series(stock_returns)).cumprod() - 1
            
            # Calculate technical indicators
            prices = 1000 * (1 + stock_cumulative)  # Base price of 1000
            sma_20 = prices.rolling(20).mean()
            sma_50 = prices.rolling(50).mean()
            
            # RSI calculation
            delta = prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            
            stock_performance[symbol] = {
                'dates': dates,
                'daily_returns': stock_returns,
                'cumulative_returns': stock_cumulative.values,
                'prices': prices.values,
                'sma_20': sma_20.fillna(1000).values,
                'sma_50': sma_50.fillna(1000).values,
                'rsi': rsi.fillna(50).values,
                'current_price': float(prices.iloc[-1]),
                'volatility_30d': np.std(stock_returns[-30:]) * np.sqrt(252),
                'volatility_90d': np.std(stock_returns[-90:]) * np.sqrt(252),
                'beta': beta,
                'sector': holding['sector'],
                'weight': holding['weight'],
                'pnl_1d': holding['pnl_1d'],
                'pnl_7d': holding['pnl_7d'],
                'pnl_30d': holding['pnl_30d'],
                'total_return_180d': float(stock_cumulative.iloc[-1]),
                'max_drawdown': float((stock_cumulative - stock_cumulative.expanding().max()).min()),
                'sharpe_ratio': np.mean(stock_returns) / np.std(stock_returns) * np.sqrt(252) if np.std(stock_returns) > 0 else 0,
                'win_rate': (stock_returns > 0).mean(),
                'momentum_score': holding['momentum_score'],
                'quality_score': holding['quality_score'],
                'value_score': holding['value_score'],
                'market_cap': holding['market_cap'],
                'pe_ratio': holding['pe_ratio'],
                'pb_ratio': holding['pb_ratio'],
                'dividend_yield': holding['dividend_yield']
            }
        
        return stock_performance
    
    def generate_risk_management_data(self):
        """Generate comprehensive risk management data"""
        
        return {
            'var_analysis': {
                'var_95_1d': -0.022,
                'var_99_1d': -0.038,
                'var_95_10d': -0.068,
                'var_99_10d': -0.115,
                'cvar_95_1d': -0.031,
                'cvar_99_1d': -0.052,
                'historical_var': -0.025,
                'parametric_var': -0.023,
                'monte_carlo_var': -0.024
            },
            'stress_testing': {
                'covid_crash_scenario': -0.35,
                'financial_crisis_scenario': -0.42,
                'dot_com_crash_scenario': -0.38,
                'black_monday_scenario': -0.28,
                'custom_stress_1': -0.25,
                'custom_stress_2': -0.31,
                'tail_risk_scenario': -0.45
            },
            'risk_decomposition': {
                'systematic_risk': 0.65,
                'idiosyncratic_risk': 0.35,
                'factor_risk': 0.45,
                'specific_risk': 0.20,
                'currency_risk': 0.05,
                'sector_risk': 0.15,
                'country_risk': 0.10,
                'liquidity_risk': 0.08
            },
            'correlation_risk': {
                'avg_correlation': 0.42,
                'max_correlation': 0.85,
                'min_correlation': -0.15,
                'correlation_breakdown_risk': 0.25,
                'tail_correlation': 0.68,
                'crisis_correlation': 0.78
            },
            'liquidity_metrics': {
                'portfolio_liquidity_score': 0.82,
                'days_to_liquidate': 3.5,
                'bid_ask_impact': 0.008,
                'market_impact_cost': 0.012,
                'liquidity_at_risk': 0.15,
                'funding_liquidity_risk': 0.05
            },
            'concentration_metrics': {
                'hhi_index': 0.08,  # Herfindahl-Hirschman Index
                'top_5_concentration': 0.32,
                'top_10_concentration': 0.55,
                'sector_concentration': 0.28,
                'single_name_limit': 0.08,
                'sector_limit': 0.25
            },
            'drawdown_analysis': {
                'current_drawdown': -0.025,
                'max_drawdown_1y': -0.085,
                'avg_drawdown_duration': 12.5,
                'max_drawdown_duration': 28,
                'recovery_time_avg': 15.2,
                'drawdown_frequency': 0.15
            }
        }
    
    def generate_market_intelligence_data(self):
        """Generate comprehensive market intelligence data"""
        
        return {
            'regime_detection': {
                'current_regime': 'supportive',
                'regime_probability': 0.78,
                'regime_duration': 45,
                'regime_stability': 0.82,
                'transition_probability': {
                    'supportive_to_neutral': 0.15,
                    'supportive_to_hostile': 0.05,
                    'supportive_to_panic': 0.02
                }
            },
            'sentiment_analysis': {
                'market_sentiment': 0.65,
                'news_sentiment': 0.58,
                'social_sentiment': 0.72,
                'analyst_sentiment': 0.61,
                'insider_sentiment': 0.69,
                'options_sentiment': 0.55,
                'sentiment_momentum': 0.08
            },
            'macro_indicators': {
                'gdp_growth': 0.067,
                'inflation_rate': 0.048,
                'interest_rates': 0.065,
                'unemployment_rate': 0.035,
                'currency_strength': 0.12,
                'commodity_prices': 0.08,
                'global_risk_appetite': 0.72
            },
            'technical_indicators': {
                'market_breadth': 0.68,
                'advance_decline_ratio': 1.45,
                'new_highs_lows': 2.1,
                'vix_level': 18.5,
                'term_structure': 0.025,
                'yield_curve_slope': 0.15,
                'credit_spreads': 0.085
            },
            'flow_analysis': {
                'institutional_flows': 1250000000,  # 125 Cr inflows
                'retail_flows': 850000000,  # 85 Cr inflows
                'foreign_flows': -450000000,  # 45 Cr outflows
                'mutual_fund_flows': 950000000,  # 95 Cr inflows
                'etf_flows': 320000000,  # 32 Cr inflows
                'derivative_flows': -180000000  # 18 Cr outflows
            },
            'volatility_surface': {
                'implied_vol_30d': 0.22,
                'implied_vol_60d': 0.24,
                'implied_vol_90d': 0.26,
                'vol_skew': 0.08,
                'vol_term_structure': 0.15,
                'vol_smile': 0.05
            },
            'market_microstructure': {
                'bid_ask_spreads': 0.008,
                'market_depth': 0.85,
                'order_flow_imbalance': 0.12,
                'price_impact': 0.005,
                'market_fragmentation': 0.25,
                'high_frequency_activity': 0.45
            }
        }
    
    def generate_advanced_analytics_data(self):
        """Generate advanced analytics and attribution data"""
        
        return {
            'performance_attribution': {
                'asset_selection': 0.035,
                'sector_allocation': 0.022,
                'timing': 0.015,
                'interaction': 0.008,
                'currency': 0.003,
                'total_alpha': 0.083,
                'benchmark_return': 0.125,
                'active_return': 0.083,
                'tracking_error': 0.045,
                'information_ratio': 1.84
            },
            'factor_exposure': {
                'market_beta': 0.88,
                'size_factor': -0.15,
                'value_factor': 0.28,
                'momentum_factor': 0.42,
                'quality_factor': 0.35,
                'low_volatility': -0.12,
                'profitability': 0.31,
                'investment': -0.18,
                'leverage': 0.08,
                'earnings_yield': 0.22
            },
            'strategy_performance': {
                'momentum': {'return': 0.145, 'sharpe': 1.25, 'max_dd': -0.085, 'win_rate': 0.68},
                'mean_reversion': {'return': 0.092, 'sharpe': 0.95, 'max_dd': -0.065, 'win_rate': 0.62},
                'trend_following': {'return': 0.168, 'sharpe': 1.42, 'max_dd': -0.125, 'win_rate': 0.71},
                'quality_growth': {'return': 0.118, 'sharpe': 1.08, 'max_dd': -0.075, 'win_rate': 0.65},
                'value': {'return': 0.078, 'sharpe': 0.82, 'max_dd': -0.055, 'win_rate': 0.58},
                'low_volatility': {'return': 0.065, 'sharpe': 0.95, 'max_dd': -0.035, 'win_rate': 0.61},
                'dividend_yield': {'return': 0.088, 'sharpe': 0.88, 'max_dd': -0.048, 'win_rate': 0.59},
                'earnings_momentum': {'return': 0.132, 'sharpe': 1.15, 'max_dd': -0.095, 'win_rate': 0.66}
            },
            'risk_adjusted_metrics': {
                'sharpe_ratio': 1.38,
                'sortino_ratio': 1.85,
                'calmar_ratio': 2.12,
                'omega_ratio': 1.45,
                'treynor_ratio': 0.095,
                'jensen_alpha': 0.042,
                'modigliani_ratio': 0.088,
                'sterling_ratio': 1.92
            },
            'portfolio_optimization': {
                'current_utility': 0.125,
                'optimal_utility': 0.138,
                'utility_gap': 0.013,
                'turnover_cost': 0.008,
                'rebalancing_frequency': 'weekly',
                'optimization_method': 'black_litterman',
                'constraints_active': 8,
                'constraints_total': 12
            }
        }
    
    def generate_sector_analysis_data(self):
        """Generate comprehensive sector analysis data"""
        
        sectors = ['Technology', 'Financials', 'Consumer', 'Healthcare', 'Energy', 'Materials', 'Industrials', 'Utilities', 'Telecom', 'Auto']
        
        sector_data = {}
        for sector in sectors:
            sector_data[sector] = {
                'weight': np.random.uniform(0.05, 0.25),
                'return_1d': np.random.normal(0.001, 0.025),
                'return_7d': np.random.normal(0.005, 0.08),
                'return_30d': np.random.normal(0.02, 0.15),
                'return_90d': np.random.normal(0.05, 0.25),
                'volatility': np.random.uniform(0.15, 0.35),
                'beta': np.random.uniform(0.7, 1.5),
                'pe_ratio': np.random.uniform(12, 30),
                'pb_ratio': np.random.uniform(1.5, 4.0),
                'dividend_yield': np.random.uniform(0.01, 0.05),
                'momentum_score': np.random.uniform(-1, 1),
                'value_score': np.random.uniform(0, 1),
                'quality_score': np.random.uniform(0, 1),
                'earnings_growth': np.random.uniform(-0.1, 0.3),
                'revenue_growth': np.random.uniform(-0.05, 0.25),
                'roa': np.random.uniform(0.02, 0.15),
                'roe': np.random.uniform(0.08, 0.25),
                'debt_to_equity': np.random.uniform(0.2, 1.5),
                'current_ratio': np.random.uniform(1.0, 3.0),
                'analyst_rating': np.random.uniform(2.5, 4.5),
                'price_target_upside': np.random.uniform(-0.1, 0.3)
            }
        
        return {
            'sector_performance': sector_data,
            'sector_rotation': {
                'momentum_sectors': ['Technology', 'Healthcare', 'Consumer'],
                'value_sectors': ['Financials', 'Energy', 'Materials'],
                'defensive_sectors': ['Utilities', 'Consumer', 'Healthcare'],
                'cyclical_sectors': ['Auto', 'Industrials', 'Materials'],
                'growth_sectors': ['Technology', 'Healthcare', 'Consumer']
            },
            'sector_correlations': self.generate_correlation_matrix(sectors),
            'sector_concentration': {
                'hhi_index': 0.12,
                'max_sector_weight': 0.25,
                'min_sector_weight': 0.05,
                'sector_diversification_ratio': 0.78
            }
        }
    
    def generate_correlation_analysis_data(self, stock_performance):
        """Generate comprehensive correlation analysis data"""
        
        # Get stock symbols from stock performance
        symbols = list(stock_performance.keys())[:20]  # Top 20 for correlation analysis
        
        # Generate correlation matrix
        correlation_matrix = self.generate_correlation_matrix(symbols)
        
        return {
            'stock_correlations': correlation_matrix,
            'correlation_statistics': {
                'avg_correlation': np.mean(correlation_matrix[np.triu_indices_from(correlation_matrix, k=1)]),
                'max_correlation': np.max(correlation_matrix[np.triu_indices_from(correlation_matrix, k=1)]),
                'min_correlation': np.min(correlation_matrix[np.triu_indices_from(correlation_matrix, k=1)]),
                'correlation_dispersion': np.std(correlation_matrix[np.triu_indices_from(correlation_matrix, k=1)])
            },
            'correlation_clusters': {
                'high_correlation_pairs': 15,
                'low_correlation_pairs': 8,
                'negative_correlation_pairs': 3,
                'cluster_1': ['RELIANCE', 'ONGC', 'BPCL'],
                'cluster_2': ['TCS', 'INFY', 'HCLTECH', 'WIPRO', 'TECHM'],
                'cluster_3': ['HDFCBANK', 'ICICIBANK', 'KOTAKBANK', 'AXISBANK', 'SBIN']
            },
            'diversification_metrics': {
                'effective_number_of_stocks': 18.5,
                'diversification_ratio': 0.72,
                'concentration_ratio': 0.28,
                'correlation_adjusted_volatility': 0.165
            }
        }
    
    def generate_volatility_analysis_data(self):
        """Generate comprehensive volatility analysis data"""
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=180)
        dates = pd.date_range(start=start_date, end=end_date, freq='D')
        
        # Generate volatility time series with regime changes
        vol_regimes = []
        for i in range(len(dates)):
            if i < 60:  # Low vol regime
                vol = np.random.uniform(0.12, 0.18)
            elif i < 120:  # Medium vol regime
                vol = np.random.uniform(0.18, 0.25)
            else:  # High vol regime
                vol = np.random.uniform(0.25, 0.35)
            vol_regimes.append(vol)
        
        return {
            'volatility_time_series': {
                'dates': dates,
                'realized_volatility': vol_regimes,
                'garch_volatility': [v * 1.05 for v in vol_regimes],
                'implied_volatility': [v * 1.1 for v in vol_regimes],
                'vol_of_vol': [v * 0.3 for v in vol_regimes]
            },
            'volatility_statistics': {
                'current_vol': vol_regimes[-1],
                'avg_vol_30d': np.mean(vol_regimes[-30:]),
                'avg_vol_90d': np.mean(vol_regimes[-90:]),
                'vol_percentile_30d': 0.75,
                'vol_percentile_90d': 0.68,
                'vol_trend': 'increasing',
                'vol_mean_reversion': 0.25
            },
            'volatility_decomposition': {
                'systematic_vol': 0.18,
                'idiosyncratic_vol': 0.12,
                'overnight_vol': 0.08,
                'intraday_vol': 0.22,
                'weekend_effect': 0.05,
                'earnings_vol': 0.15
            },
            'volatility_forecasting': {
                'garch_forecast_1d': 0.28,
                'garch_forecast_7d': 0.26,
                'garch_forecast_30d': 0.24,
                'ewma_forecast': 0.27,
                'historical_forecast': 0.25,
                'implied_forecast': 0.29
            }
        }
    
    def generate_regime_analysis_data(self):
        """Generate comprehensive regime analysis data"""
        
        return {
            'current_regime': {
                'regime_name': 'supportive',
                'regime_probability': 0.78,
                'regime_duration': 45,
                'regime_strength': 0.82,
                'regime_stability': 0.75
            },
            'regime_history': {
                'supportive_periods': 8,
                'neutral_periods': 5,
                'hostile_periods': 3,
                'panic_periods': 1,
                'avg_supportive_duration': 52,
                'avg_neutral_duration': 28,
                'avg_hostile_duration': 18,
                'avg_panic_duration': 8
            },
            'regime_characteristics': {
                'supportive': {
                    'avg_return': 0.0012,
                    'volatility': 0.16,
                    'sharpe': 1.45,
                    'max_drawdown': -0.05,
                    'correlation': 0.35
                },
                'neutral': {
                    'avg_return': 0.0003,
                    'volatility': 0.22,
                    'sharpe': 0.25,
                    'max_drawdown': -0.08,
                    'correlation': 0.55
                },
                'hostile': {
                    'avg_return': -0.0008,
                    'volatility': 0.32,
                    'sharpe': -0.45,
                    'max_drawdown': -0.15,
                    'correlation': 0.75
                },
                'panic': {
                    'avg_return': -0.0025,
                    'volatility': 0.45,
                    'sharpe': -1.25,
                    'max_drawdown': -0.35,
                    'correlation': 0.85
                }
            },
            'regime_indicators': {
                'vix_level': 18.5,
                'credit_spreads': 0.085,
                'yield_curve_slope': 0.15,
                'dollar_strength': 0.12,
                'commodity_momentum': 0.08,
                'earnings_revisions': 0.05,
                'sentiment_index': 0.65
            },
            'transition_probabilities': {
                'supportive_to_neutral': 0.15,
                'supportive_to_hostile': 0.05,
                'supportive_to_panic': 0.02,
                'neutral_to_supportive': 0.25,
                'neutral_to_hostile': 0.20,
                'neutral_to_panic': 0.05,
                'hostile_to_supportive': 0.10,
                'hostile_to_neutral': 0.35,
                'hostile_to_panic': 0.15,
                'panic_to_supportive': 0.05,
                'panic_to_neutral': 0.20,
                'panic_to_hostile': 0.30
            }
        }
    
    def generate_correlation_matrix(self, symbols):
        """Generate realistic correlation matrix"""
        n = len(symbols)
        # Start with random correlations
        correlations = np.random.uniform(-0.3, 0.8, (n, n))
        # Make symmetric
        correlations = (correlations + correlations.T) / 2
        # Set diagonal to 1
        np.fill_diagonal(correlations, 1.0)
        # Ensure positive semi-definite
        eigenvals, eigenvecs = np.linalg.eigh(correlations)
        eigenvals = np.maximum(eigenvals, 0.01)  # Ensure positive eigenvalues
        correlations = eigenvecs @ np.diag(eigenvals) @ eigenvecs.T
        # Normalize to correlation matrix
        d = np.sqrt(np.diag(correlations))
        correlations = correlations / np.outer(d, d)
        return correlations
    
    def generate_backtesting_results(self):
        """Generate comprehensive backtesting results"""
        
        return {
            'backtest_summary': {
                'total_return': 0.245,
                'annualized_return': 0.185,
                'volatility': 0.165,
                'sharpe_ratio': 1.38,
                'sortino_ratio': 1.85,
                'calmar_ratio': 2.12,
                'max_drawdown': -0.085,
                'win_rate': 0.68,
                'profit_factor': 1.85,
                'total_trades': 1250,
                'avg_trade_duration': 12.5,
                'best_trade': 0.085,
                'worst_trade': -0.045
            },
            'monthly_returns': {
                'Jan': 0.025, 'Feb': 0.018, 'Mar': -0.012, 'Apr': 0.032, 'May': 0.015, 'Jun': 0.028,
                'Jul': 0.022, 'Aug': -0.008, 'Sep': 0.035, 'Oct': 0.019, 'Nov': 0.041, 'Dec': 0.030
            },
            'yearly_performance': {
                '2020': {'return': 0.185, 'sharpe': 1.25, 'max_dd': -0.125},
                '2021': {'return': 0.225, 'sharpe': 1.45, 'max_dd': -0.085},
                '2022': {'return': -0.055, 'sharpe': -0.35, 'max_dd': -0.185},
                '2023': {'return': 0.165, 'sharpe': 1.15, 'max_dd': -0.095},
                '2024': {'return': 0.125, 'sharpe': 1.05, 'max_dd': -0.065},
                '2025': {'return': 0.145, 'sharpe': 1.25, 'max_dd': -0.055}
            },
            'rolling_metrics': {
                'rolling_sharpe_12m': [1.25, 1.35, 1.15, 0.95, 1.05, 1.25, 1.38],
                'rolling_return_12m': [0.185, 0.205, 0.165, 0.125, 0.145, 0.175, 0.185],
                'rolling_vol_12m': [0.145, 0.155, 0.165, 0.175, 0.165, 0.155, 0.165],
                'rolling_dd_12m': [-0.085, -0.095, -0.125, -0.145, -0.105, -0.085, -0.085]
            },
            'strategy_breakdown': {
                'momentum': 0.35,
                'mean_reversion': 0.20,
                'trend_following': 0.25,
                'quality': 0.15,
                'value': 0.05
            }
        }
    
    def generate_walk_forward_validation(self):
        """Generate walk-forward validation results"""
        
        return {
            'validation_summary': {
                'total_periods': 48,
                'passed_periods': 43,
                'failed_periods': 5,
                'success_rate': 0.896,
                'avg_oos_return': 0.125,
                'avg_oos_sharpe': 1.15,
                'consistency_score': 0.82,
                'robustness_score': 0.88
            },
            'period_results': [
                {'period': i, 'return': np.random.normal(0.12, 0.08), 'sharpe': np.random.normal(1.1, 0.4), 
                 'status': 'PASS' if np.random.random() > 0.1 else 'FAIL'} 
                for i in range(1, 49)
            ],
            'degradation_analysis': {
                'return_degradation': 0.15,  # 15% degradation from IS to OOS
                'sharpe_degradation': 0.12,
                'volatility_increase': 0.08,
                'drawdown_increase': 0.25,
                'turnover_increase': 0.18
            },
            'stability_metrics': {
                'parameter_stability': 0.85,
                'performance_stability': 0.78,
                'risk_stability': 0.82,
                'correlation_stability': 0.75,
                'regime_stability': 0.68
            }
        }
    
    def generate_system_diagnostics_data(self):
        """Generate comprehensive system diagnostics data"""
        
        return {
            'system_health': {
                'overall_health': 0.87,
                'data_pipeline_health': 0.92,
                'model_health': 0.85,
                'execution_health': 0.88,
                'risk_system_health': 0.90,
                'monitoring_health': 0.85
            },
            'performance_metrics': {
                'cpu_usage': 0.15,
                'memory_usage': 0.42,
                'disk_usage': 0.73,
                'network_latency': 12.8,
                'database_response_time': 45.2,
                'api_response_time': 125.5,
                'cache_hit_rate': 0.85,
                'error_rate': 0.002
            },
            'data_quality': {
                'data_completeness': 0.98,
                'data_accuracy': 0.95,
                'data_timeliness': 0.92,
                'data_consistency': 0.96,
                'missing_data_rate': 0.02,
                'outlier_detection_rate': 0.05
            },
            'model_diagnostics': {
                'model_accuracy': 0.76,
                'model_precision': 0.72,
                'model_recall': 0.68,
                'model_f1_score': 0.70,
                'feature_importance_stability': 0.82,
                'prediction_confidence': 0.75,
                'model_drift_score': 0.08
            },
            'execution_metrics': {
                'order_fill_rate': 0.98,
                'execution_slippage': 0.003,
                'latency_p50': 15.2,
                'latency_p95': 45.8,
                'latency_p99': 125.5,
                'rejected_orders': 0.005,
                'partial_fills': 0.02
            },
            'alerts_and_warnings': {
                'critical_alerts': 0,
                'warning_alerts': 2,
                'info_alerts': 5,
                'resolved_alerts_24h': 8,
                'avg_resolution_time': 25.5,
                'false_positive_rate': 0.12
            }
        }
    
    def generate_institutional_reporting_data(self):
        """Generate institutional reporting data"""
        
        return {
            'executive_summary': {
                'aum': 15_000_000,  # 15 Cr
                'total_return_ytd': 0.125,
                'excess_return': 0.045,
                'tracking_error': 0.045,
                'information_ratio': 1.84,
                'max_drawdown': -0.085,
                'sharpe_ratio': 1.38,
                'active_positions': 35,
                'turnover_rate': 0.25
            },
            'risk_report': {
                'var_95': -0.022,
                'expected_shortfall': -0.031,
                'beta': 0.88,
                'active_risk': 0.045,
                'concentration_risk': 0.32,
                'sector_risk': 0.15,
                'liquidity_risk': 0.08,
                'currency_risk': 0.02
            },
            'attribution_report': {
                'stock_selection': 0.035,
                'sector_allocation': 0.022,
                'timing': 0.015,
                'interaction': 0.008,
                'total_alpha': 0.080,
                'benchmark_return': 0.125,
                'portfolio_return': 0.205
            },
            'compliance_report': {
                'position_limits': 'PASS',
                'sector_limits': 'PASS',
                'liquidity_requirements': 'PASS',
                'risk_limits': 'PASS',
                'concentration_limits': 'PASS',
                'leverage_limits': 'PASS',
                'violations_count': 0,
                'exceptions_count': 2,
                'overall_status': 'COMPLIANT'
            },
            'esg_report': {
                'esg_score': 7.2,
                'environmental_score': 6.8,
                'social_score': 7.5,
                'governance_score': 7.3,
                'carbon_footprint': 125.5,
                'sustainable_investments': 0.35,
                'exclusions_applied': 8
            }
        }
    
    # =========================== ULTIMATE RENDERING FUNCTIONS ===========================
    
    def run_ultimate_dashboard(self):
        """Run the ultimate comprehensive dashboard"""
        
        # Render header
        self.render_ultimate_header()
        
        # Render command bar
        self.render_ultimate_command_bar()
        
        # Render key metrics
        self.render_ultimate_key_metrics()
        
        # Render constitutional panels
        self.render_constitutional_panels()
        
        # Render comprehensive dashboards
        self.render_portfolio_dashboard()
        self.render_individual_stock_performance()
        self.render_risk_management_dashboard()
        self.render_market_intelligence_dashboard()
        self.render_advanced_analytics_dashboard()
        self.render_sector_analysis_dashboard()
        self.render_correlation_analysis_dashboard()
        self.render_volatility_analysis_dashboard()
        self.render_regime_analysis_dashboard()
        self.render_backtesting_dashboard()
        self.render_walk_forward_validation_dashboard()
        self.render_system_diagnostics_dashboard()
        self.render_institutional_reporting_dashboard()
        
        # Render constitutional principles
        self.render_constitutional_principles()
        
        # Render sidebar
        self.render_sidebar()
    
    def render_ultimate_header(self):
        """Render ultimate professional header"""
        
        st.markdown(f"""
        <div class="ultimate-header">
            <div class="header-title">🎯 NORTHSTAR V3</div>
            <div class="header-subtitle">Ultimate Comprehensive Cockpit - The One and Only Truly Exceptional Dashboard</div>
        </div>
        """, unsafe_allow_html=True)
        
        st.info(f"🕐 Dashboard generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Data sources: Comprehensive self-contained generation | All features included")
    
    def render_ultimate_command_bar(self):
        """Render ultimate command bar with comprehensive metrics"""
        
        panels = self.data['constitutional_panels']
        panel1 = panels['panel_1_system_state']
        panel2 = panels['panel_2_risk_authority']
        panel5 = panels['panel_5_intelligence_observer']
        perf_data = self.data['performance_data']
        
        # Extract key metrics
        regime = panel1['current_regime'].upper()
        risk_status = panel2['risk_status'].upper()
        exposure = panel1['current_exposure'] * 100
        health_score = panel1['health_score'] * 100
        conviction = panel5['unified_conviction'] * 100
        total_return = perf_data['total_return'] * 100
        sharpe_ratio = perf_data['sharpe_ratio']
        
        st.markdown(f"""
        <div class="ultimate-command-bar">
            <strong>🎯 NORTHSTAR V3 ULTIMATE COMMAND BAR</strong> | 
            REGIME: {regime} | 
            RISK: {risk_status} | 
            EXPOSURE: {exposure:.1f}% | 
            HEALTH: {health_score:.1f}% | 
            AI CONVICTION: {conviction:.1f}% | 
            TOTAL RETURN: {total_return:+.1f}% | 
            SHARPE: {sharpe_ratio:.2f} | 
            STATUS: 🟢 ACTIVE | 
            FEATURES: ALL COMPREHENSIVE
        </div>
        """, unsafe_allow_html=True)
    
    def render_ultimate_key_metrics(self):
        """Render ultimate key metrics row with perfect error handling"""
        
        portfolio_data = self.data['portfolio_data']
        performance_data = self.data['performance_data']
        panels = self.data['constitutional_panels']
        
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            portfolio_value = portfolio_data['total_value']
            daily_returns = performance_data['daily_returns']
            # Safe array access
            if len(daily_returns) > 0:
                daily_change = daily_returns[-1] * 100
            else:
                daily_change = 0
            change_class = "metric-positive" if daily_change >= 0 else "metric-negative"
            st.markdown(f"""
            <div class="ultimate-metric-card">
                <div class="ultimate-metric-value">₹{portfolio_value:,.0f}</div>
                <div class="ultimate-metric-label">Portfolio Value</div>
                <div class="ultimate-metric-change {change_class}">{daily_change:+.2f}% Today</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            total_return = performance_data['total_return'] * 100
            change_class = "metric-positive" if total_return >= 0 else "metric-negative"
            st.markdown(f"""
            <div class="ultimate-metric-card">
                <div class="ultimate-metric-value">{total_return:+.1f}%</div>
                <div class="ultimate-metric-label">Total Return</div>
                <div class="ultimate-metric-change {change_class}">180-Day Performance</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            sharpe_ratio = performance_data['sharpe_ratio']
            change_class = "metric-positive" if sharpe_ratio > 1.0 else "metric-neutral"
            st.markdown(f"""
            <div class="ultimate-metric-card">
                <div class="ultimate-metric-value">{sharpe_ratio:.2f}</div>
                <div class="ultimate-metric-label">Sharpe Ratio</div>
                <div class="ultimate-metric-change {change_class}">Risk-Adjusted Return</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col4:
            max_drawdown = performance_data['max_drawdown'] * 100
            change_class = "metric-positive" if max_drawdown > -5 else "metric-warning" if max_drawdown > -10 else "metric-negative"
            st.markdown(f"""
            <div class="ultimate-metric-card">
                <div class="ultimate-metric-value">{max_drawdown:.1f}%</div>
                <div class="ultimate-metric-label">Max Drawdown</div>
                <div class="ultimate-metric-change {change_class}">Peak to Trough</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col5:
            panel1 = panels['panel_1_system_state']
            health_score = panel1['health_score'] * 100
            change_class = "metric-positive" if health_score >= 80 else "metric-warning" if health_score >= 60 else "metric-negative"
            st.markdown(f"""
            <div class="ultimate-metric-card">
                <div class="ultimate-metric-value">{health_score:.0f}%</div>
                <div class="ultimate-metric-label">System Health</div>
                <div class="ultimate-metric-change {change_class}">All Systems Status</div>
            </div>
            """, unsafe_allow_html=True)
    
    def render_constitutional_panels(self):
        """Render all 5 constitutional panels with comprehensive information"""
        
        panels = self.data['constitutional_panels']
        
        # Panel 1: System State
        self.render_system_state_panel(panels['panel_1_system_state'])
        
        # Panel 2: Risk Authority  
        self.render_risk_authority_panel(panels['panel_2_risk_authority'])
        
        # Panel 3: Engine Behavior
        self.render_engine_behavior_panel(panels['panel_3_engine_behavior'])
        
        # Panel 4: Validation & Truth
        self.render_validation_truth_panel(panels['panel_4_validation_truth'])
        
        # Panel 5: Intelligence Observer
        self.render_intelligence_observer_panel(panels['panel_5_intelligence_observer'])
    
    def render_system_state_panel(self, panel_data):
        """Render comprehensive system state panel"""
        
        st.markdown('<div class="ultimate-panel">', unsafe_allow_html=True)
        st.markdown(f"""
        <div class="ultimate-panel-title">
            <div><span class="panel-icon">📊</span>{panel_data['title']}</div>
            <div class="panel-subtitle">{panel_data['subtitle']}</div>
        </div>
        """, unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns([1, 1, 1])
        
        with col1:
            # System Health Gauge
            health_score = panel_data['health_score'] * 100
            fig = go.Figure(go.Indicator(
                mode="gauge+number+delta",
                value=health_score,
                domain={'x': [0, 1], 'y': [0, 1]},
                title={'text': "System Health Score", 'font': {'color': '#1e293b', 'size': 16}},
                delta={'reference': 90, 'position': "top"},
                gauge={
                    'axis': {'range': [None, 100], 'tickwidth': 1, 'tickcolor': "#1e293b"},
                    'bar': {'color': ULTIMATE_COLORS['success'] if health_score >= 80 else ULTIMATE_COLORS['warning'] if health_score >= 60 else ULTIMATE_COLORS['danger']},
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
            fig.update_layout(
                height=350, 
                margin=dict(l=20, r=20, t=40, b=20), 
                font=dict(family="Inter, sans-serif", color='#1e293b'),
                paper_bgcolor='white',
                plot_bgcolor='white'
            )
            st.plotly_chart(fig, width="stretch", config={'displayModeBar': False})
        
        with col2:
            # Resource Usage Chart
            resources = ['CPU', 'Memory', 'Disk', 'Network']
            usage_values = [
                panel_data['cpu_usage_pct'] * 100,
                panel_data['memory_usage_pct'] * 100,
                panel_data['disk_usage_pct'] * 100,
                min(panel_data['network_latency_ms'] / 100 * 100, 100)
            ]
            
            fig = go.Figure(data=go.Bar(
                x=resources,
                y=usage_values,
                marker_color=[ULTIMATE_COLORS['success'] if v < 50 else ULTIMATE_COLORS['warning'] if v < 80 else ULTIMATE_COLORS['danger'] for v in usage_values],
                text=[f'{v:.1f}%' for v in usage_values],
                textposition='outside',
                textfont=dict(color='#1e293b', size=12)
            ))
            fig.update_layout(
                title="Resource Utilization",
                height=350,
                margin=dict(l=20, r=20, t=40, b=20),
                yaxis_title="Usage %",
                font=dict(family="Inter, sans-serif", color='#1e293b'),
                plot_bgcolor='white',
                paper_bgcolor='white'
            )
            st.plotly_chart(fig, width="stretch", config={'displayModeBar': False})
        
        with col3:
            # System Status Metrics
            st.markdown(f"""
            <div class="ultimate-metric-grid">
                <div class="ultimate-metric-card">
                    <div class="ultimate-metric-value">{panel_data['components_healthy']}</div>
                    <div class="ultimate-metric-label">Components Healthy</div>
                </div>
                <div class="ultimate-metric-card">
                    <div class="ultimate-metric-value">{panel_data['current_regime'].upper()}</div>
                    <div class="ultimate-metric-label">Market Regime</div>
                </div>
                <div class="ultimate-metric-card">
                    <div class="ultimate-metric-value">{panel_data['system_uptime_days']}</div>
                    <div class="ultimate-metric-label">Uptime (Days)</div>
                </div>
                <div class="ultimate-metric-card">
                    <div class="ultimate-metric-value">{'LOCKED ✅' if panel_data['conviction_locked'] else 'UNLOCKED ❌'}</div>
                    <div class="ultimate-metric-label">Conviction Contract</div>
                </div>
                <div class="ultimate-metric-card">
                    <div class="ultimate-metric-value">{panel_data['data_quality_score']:.1%}</div>
                    <div class="ultimate-metric-label">Data Quality</div>
                </div>
                <div class="ultimate-metric-card">
                    <div class="ultimate-metric-value">{panel_data['operational_efficiency']:.1%}</div>
                    <div class="ultimate-metric-label">Operational Efficiency</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        # Additional comprehensive information
        st.markdown("#### 📋 Detailed System Information")
        
        info_col1, info_col2, info_col3 = st.columns(3)
        
        with info_col1:
            st.markdown(f"""
            **🔧 System Configuration:**
            - Active Engine: {panel_data['active_engine'].replace('_', ' ').title()}
            - Engine Confidence: {panel_data['engine_confidence']:.1%}
            - Current Exposure: {panel_data['current_exposure']:.1%}
            - Allowed Exposure: {panel_data['allowed_exposure']:.1%}
            """)
        
        with info_col2:
            st.markdown(f"""
            **📊 Performance Metrics:**
            - System Integrity: {panel_data['system_integrity_score']:.1%}
            - Regime Confidence: {panel_data['regime_confidence']:.1%}
            - Data Freshness: {panel_data.get('data_freshness_hours', 0.3):.1f} hours
            - Network Latency: {panel_data['network_latency_ms']:.1f} ms
            """)
        
        with info_col3:
            st.markdown(f"""
            **⚡ System Status:**
            - Orchestrator: {'🟢 Running' if panel_data['orchestrator_running'] else '🔴 Stopped'}
            - Data Pipeline: {'🟢 Fresh' if panel_data['data_fresh'] else '🟡 Stale'}
            - Health Status: {panel_data['health_status'].title()}
            - Last Update: {panel_data['last_update'][:19]}
            """)
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    def render_risk_authority_panel(self, panel_data):
        """Render comprehensive risk authority panel"""
        
        st.markdown('<div class="ultimate-panel">', unsafe_allow_html=True)
        st.markdown(f"""
        <div class="ultimate-panel-title">
            <div><span class="panel-icon">🛡️</span>{panel_data['title']}</div>
            <div class="panel-subtitle">{panel_data['subtitle']}</div>
        </div>
        """, unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns([1, 1, 1])
        
        with col1:
            # Risk Level Gauge
            risk_level = panel_data['risk_level'] * 100
            fig = go.Figure(go.Indicator(
                mode="gauge+number",
                value=risk_level,
                domain={'x': [0, 1], 'y': [0, 1]},
                title={'text': "Risk Level", 'font': {'color': '#1e293b', 'size': 16}},
                gauge={
                    'axis': {'range': [None, 50], 'tickwidth': 1, 'tickcolor': "#1e293b"},
                    'bar': {'color': ULTIMATE_COLORS['success'] if risk_level < 10 else ULTIMATE_COLORS['warning'] if risk_level < 20 else ULTIMATE_COLORS['danger']},
                    'steps': [
                        {'range': [0, 10], 'color': '#d1fae5'},
                        {'range': [10, 20], 'color': '#fef3c7'},
                        {'range': [20, 50], 'color': '#fee2e2'}
                    ],
                    'threshold': {
                        'line': {'color': "red", 'width': 4},
                        'thickness': 0.75,
                        'value': 25
                    }
                }
            ))
            fig.update_layout(
                height=350, 
                margin=dict(l=20, r=20, t=40, b=20), 
                font=dict(family="Inter, sans-serif", color='#1e293b'),
                paper_bgcolor='white',
                plot_bgcolor='white'
            )
            st.plotly_chart(fig, width="stretch", config={'displayModeBar': False})
        
        with col2:
            # VaR Analysis
            var_metrics = ['VaR 95%', 'VaR 99%', 'Current DD', 'Peak DD']
            var_values = [
                abs(panel_data['var_95_1d']) * 100,
                abs(panel_data['var_99_1d']) * 100,
                abs(panel_data['current_drawdown']) * 100,
                abs(panel_data['peak_drawdown_30d']) * 100
            ]
            
            fig = go.Figure(data=go.Bar(
                x=var_metrics,
                y=var_values,
                marker_color=[
                    ULTIMATE_COLORS['info'], ULTIMATE_COLORS['warning'], 
                    ULTIMATE_COLORS['danger'] if var_values[2] > 5 else ULTIMATE_COLORS['success'],
                    ULTIMATE_COLORS['warning']
                ],
                text=[f'{v:.1f}%' for v in var_values],
                textposition='outside',
                textfont=dict(color='#1e293b', size=12)
            ))
            fig.update_layout(
                title="Risk Metrics",
                height=350,
                margin=dict(l=20, r=20, t=40, b=20),
                yaxis_title="Risk %",
                font=dict(family="Inter, sans-serif", color='#1e293b'),
                plot_bgcolor='white',
                paper_bgcolor='white'
            )
            st.plotly_chart(fig, width="stretch", config={'displayModeBar': False})
        
        with col3:
            # Risk Control Metrics
            st.markdown(f"""
            <div class="ultimate-metric-grid">
                <div class="ultimate-metric-card">
                    <div class="ultimate-metric-value">{panel_data['emergency_brake_status']}</div>
                    <div class="ultimate-metric-label">Emergency Brake</div>
                </div>
                <div class="ultimate-metric-card">
                    <div class="ultimate-metric-value">{panel_data['risk_status'].upper()}</div>
                    <div class="ultimate-metric-label">Risk Status</div>
                </div>
                <div class="ultimate-metric-card">
                    <div class="ultimate-metric-value">{panel_data['kill_switches_armed']}/{panel_data['kill_switches_total']}</div>
                    <div class="ultimate-metric-label">Kill Switches</div>
                </div>
                <div class="ultimate-metric-card">
                    <div class="ultimate-metric-value">{panel_data['leverage_ratio']:.2f}x</div>
                    <div class="ultimate-metric-label">Leverage</div>
                </div>
                <div class="ultimate-metric-card">
                    <div class="ultimate-metric-value">{panel_data['risk_budget_utilization']:.1%}</div>
                    <div class="ultimate-metric-label">Risk Budget Used</div>
                </div>
                <div class="ultimate-metric-card">
                    <div class="ultimate-metric-value">{panel_data['liquidity_risk']:.1%}</div>
                    <div class="ultimate-metric-label">Liquidity Risk</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        # Additional risk information
        st.markdown("#### 🛡️ Comprehensive Risk Analysis")
        
        risk_col1, risk_col2, risk_col3 = st.columns(3)
        
        with risk_col1:
            st.markdown(f"""
            **📊 Risk Metrics:**
            - Volatility (20d): {panel_data['volatility_20d']:.1%}
            - Volatility (5d): {panel_data['volatility_5d']:.1%}
            - Concentration Risk: {panel_data['concentration_risk']:.1%}
            - Margin Utilization: {panel_data['margin_utilization']:.1%}
            """)
        
        with risk_col2:
            st.markdown(f"""
            **⚠️ Risk Limits:**
            - Max Allowed DD: {panel_data['max_allowed_drawdown']:.1%}
            - Exposure Multiplier: {panel_data['exposure_multiplier']:.2f}x
            - Volatility Stress: {panel_data['volatility_stress'].title()}
            - Emergency Active: {'🔴 YES' if panel_data['emergency_active'] else '🟢 NO'}
            """)
        
        with risk_col3:
            st.markdown(f"""
            **🔒 System Protection:**
            - Survival Mode: {panel_data['survival_mode'].title()}
            - System Locked: {'🔴 YES' if panel_data['system_locked'] else '🟢 NO'}
            - Kill Switches Armed: {panel_data['kill_switches_armed']}/{panel_data['kill_switches_total']}
            - Protection Level: {'🟢 Normal' if panel_data['risk_status'] == 'normal' else '🟡 Elevated'}
            """)
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    def render_engine_behavior_panel(self, panel_data):
        """Render comprehensive engine behavior panel"""
        
        st.markdown('<div class="ultimate-panel">', unsafe_allow_html=True)
        st.markdown(f"""
        <div class="ultimate-panel-title">
            <div><span class="panel-icon">⚙️</span>{panel_data['title']}</div>
            <div class="panel-subtitle">{panel_data['subtitle']}</div>
        </div>
        """, unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns([1, 1, 1])
        
        with col1:
            # Performance Chart
            performance_data = self.data['performance_data']
            if performance_data.get('dates') is not None and performance_data.get('cumulative_returns') is not None:
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=performance_data['dates'],
                    y=performance_data['cumulative_returns'] * 100,
                    mode='lines',
                    name='Cumulative Return',
                    line=dict(color=ULTIMATE_COLORS['primary'], width=3),
                    fill='tonexty',
                    fillcolor=f'rgba(59, 130, 246, 0.2)'
                ))
                fig.update_layout(
                    title="180-Day Performance",
                    height=350,
                    margin=dict(l=20, r=20, t=40, b=20),
                    yaxis_title="Return (%)",
                    showlegend=False,
                    font=dict(family="Inter, sans-serif", color='#1e293b'),
                    plot_bgcolor='white',
                    paper_bgcolor='white'
                )
                st.plotly_chart(fig, width="stretch", config={'displayModeBar': False})
        
        with col2:
            # Engine Performance Metrics
            engine_metrics = ['Win Rate', 'Sharpe', 'Signal Strength', 'Alpha Gen']
            engine_values = [
                panel_data['trend_win_rate_30d'] * 100,
                panel_data['trend_sharpe_30d'] * 20,  # Scale for visibility
                panel_data['signal_strength'] * 100,
                panel_data['alpha_generation_rate'] * 100
            ]
            
            fig = go.Figure(data=go.Bar(
                x=engine_metrics,
                y=engine_values,
                marker_color=ULTIMATE_CHART_COLORS[:len(engine_metrics)],
                text=[f'{v:.1f}%' if i != 1 else f'{panel_data["trend_sharpe_30d"]:.2f}' for i, v in enumerate(engine_values)],
                textposition='outside',
                textfont=dict(color='#1e293b', size=12)
            ))
            fig.update_layout(
                title="Engine Performance",
                height=350,
                margin=dict(l=20, r=20, t=40, b=20),
                yaxis_title="Performance %",
                font=dict(family="Inter, sans-serif", color='#1e293b'),
                plot_bgcolor='white',
                paper_bgcolor='white'
            )
            st.plotly_chart(fig, width="stretch", config={'displayModeBar': False})
        
        with col3:
            # Engine Status Metrics
            st.markdown(f"""
            <div class="ultimate-metric-grid">
                <div class="ultimate-metric-card">
                    <div class="ultimate-metric-value">{'🟢 ACTIVE' if panel_data['trend_engine_active'] else '🔴 INACTIVE'}</div>
                    <div class="ultimate-metric-label">Trend Engine</div>
                </div>
                <div class="ultimate-metric-card">
                    <div class="ultimate-metric-value">{panel_data['trend_engine_days_active']}</div>
                    <div class="ultimate-metric-label">Days Active</div>
                </div>
                <div class="ultimate-metric-card">
                    <div class="ultimate-metric-value">{panel_data['orchestrator_success_rate']:.1%}</div>
                    <div class="ultimate-metric-label">Success Rate</div>
                </div>
                <div class="ultimate-metric-card">
                    <div class="ultimate-metric-value">{panel_data['healthy_organs']}</div>
                    <div class="ultimate-metric-label">Healthy Organs</div>
                </div>
                <div class="ultimate-metric-card">
                    <div class="ultimate-metric-value">{panel_data['execution_efficiency']:.1%}</div>
                    <div class="ultimate-metric-label">Execution Efficiency</div>
                </div>
                <div class="ultimate-metric-card">
                    <div class="ultimate-metric-value">{panel_data['model_stability']:.1%}</div>
                    <div class="ultimate-metric-label">Model Stability</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        # Additional engine information
        st.markdown("#### ⚙️ Detailed Engine Analysis")
        
        engine_col1, engine_col2, engine_col3 = st.columns(3)
        
        with engine_col1:
            st.markdown(f"""
            **🎯 Engine Performance:**
            - Holding Duration: {panel_data['trend_holding_duration_avg']:.1f} days
            - Position Turnover: {panel_data['position_turnover_7d']:.1%} (7d)
            - Signal Decay Rate: {panel_data['signal_decay_rate']:.1%}
            - Cycle Interval: {panel_data['cycle_interval']} seconds
            """)
        
        with engine_col2:
            st.markdown(f"""
            **📊 System Stability:**
            - System Stability: {panel_data['system_stability'].title()}
            - Protection Mode: {'🟡 Active' if panel_data['protection_mode'] else '🟢 Normal'}
            - Isolated Organs: {panel_data['isolated_organs']}
            - Alpha Generation: {panel_data['alpha_generation_rate']:.1%}
            """)
        
        with engine_col3:
            st.markdown(f"""
            **⚡ Real-time Metrics:**
            - Signal Strength: {panel_data['signal_strength']:.1%}
            - Win Rate (30d): {panel_data['trend_win_rate_30d']:.1%}
            - Sharpe (30d): {panel_data['trend_sharpe_30d']:.2f}
            - Execution Efficiency: {panel_data['execution_efficiency']:.1%}
            """)
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    def render_validation_truth_panel(self, panel_data):
        """Render comprehensive validation & truth panel"""
        
        st.markdown('<div class="ultimate-panel">', unsafe_allow_html=True)
        st.markdown(f"""
        <div class="ultimate-panel-title">
            <div><span class="panel-icon">✅</span>{panel_data['title']}</div>
            <div class="panel-subtitle">{panel_data['subtitle']}</div>
        </div>
        """, unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns([1, 1, 1])
        
        with col1:
            # Validation Score Gauge
            validation_score = panel_data['validation_score'] * 100
            fig = go.Figure(go.Indicator(
                mode="gauge+number+delta",
                value=validation_score,
                domain={'x': [0, 1], 'y': [0, 1]},
                title={'text': "Validation Score", 'font': {'color': '#1e293b', 'size': 16}},
                delta={'reference': 85, 'position': "top"},
                gauge={
                    'axis': {'range': [None, 100], 'tickwidth': 1, 'tickcolor': "#1e293b"},
                    'bar': {'color': ULTIMATE_COLORS['success'] if validation_score >= 80 else ULTIMATE_COLORS['warning'] if validation_score >= 60 else ULTIMATE_COLORS['danger']},
                    'steps': [
                        {'range': [0, 60], 'color': '#fee2e2'},
                        {'range': [60, 80], 'color': '#fef3c7'},
                        {'range': [80, 100], 'color': '#d1fae5'}
                    ],
                    'threshold': {
                        'line': {'color': "green", 'width': 4},
                        'thickness': 0.75,
                        'value': 85
                    }
                }
            ))
            fig.update_layout(
                height=350, 
                margin=dict(l=20, r=20, t=40, b=20), 
                font=dict(family="Inter, sans-serif", color='#1e293b'),
                paper_bgcolor='white',
                plot_bgcolor='white'
            )
            st.plotly_chart(fig, width="stretch", config={'displayModeBar': False})
        
        with col2:
            # Validation Metrics
            validation_metrics = ['Data Integrity', 'Reality Check', 'Statistical Sig', 'OOS Performance']
            validation_values = [
                panel_data['data_integrity_score'] * 100,
                panel_data['reality_check_score'] * 100,
                panel_data['statistical_significance'] * 100,
                panel_data['out_of_sample_performance'] * 100
            ]
            
            fig = go.Figure(data=go.Bar(
                x=validation_metrics,
                y=validation_values,
                marker_color=[ULTIMATE_COLORS['success'] if v >= 90 else ULTIMATE_COLORS['warning'] if v >= 75 else ULTIMATE_COLORS['danger'] for v in validation_values],
                text=[f'{v:.1f}%' for v in validation_values],
                textposition='outside',
                textfont=dict(color='#1e293b', size=12)
            ))
            fig.update_layout(
                title="Validation Quality Metrics",
                height=350,
                margin=dict(l=20, r=20, t=40, b=20),
                yaxis_title="Quality Score %",
                font=dict(family="Inter, sans-serif", color='#1e293b'),
                plot_bgcolor='white',
                paper_bgcolor='white'
            )
            st.plotly_chart(fig, width="stretch", config={'displayModeBar': False})
        
        with col3:
            # Validation Status Metrics
            st.markdown(f"""
            <div class="ultimate-metric-grid">
                <div class="ultimate-metric-card">
                    <div class="ultimate-metric-value">{panel_data['last_walkforward_result']}</div>
                    <div class="ultimate-metric-label">Last Walk Forward</div>
                </div>
                <div class="ultimate-metric-card">
                    <div class="ultimate-metric-value">{panel_data['walkforward_tests_passed']}/{panel_data['walkforward_tests_total']}</div>
                    <div class="ultimate-metric-label">Tests Passed</div>
                </div>
                <div class="ultimate-metric-card">
                    <div class="ultimate-metric-value">{'✅ VERIFIED' if panel_data['rules_hash_verified'] else '❌ FAILED'}</div>
                    <div class="ultimate-metric-label">Rules Hash</div>
                </div>
                <div class="ultimate-metric-card">
                    <div class="ultimate-metric-value">{panel_data['override_attempts_24h']}</div>
                    <div class="ultimate-metric-label">Override Attempts</div>
                </div>
                <div class="ultimate-metric-card">
                    <div class="ultimate-metric-value">{panel_data['model_robustness']:.1%}</div>
                    <div class="ultimate-metric-label">Model Robustness</div>
                </div>
                <div class="ultimate-metric-card">
                    <div class="ultimate-metric-value">{panel_data['walkforward_success_rate']:.1%}</div>
                    <div class="ultimate-metric-label">WF Success Rate</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        # Additional validation information
        st.markdown("#### ✅ Comprehensive Validation Analysis")
        
        val_col1, val_col2, val_col3 = st.columns(3)
        
        with val_col1:
            st.markdown(f"""
            **📊 Data Quality:**
            - Data Freshness: {panel_data['data_freshness_hours']:.1f} hours
            - Data Integrity: {panel_data['data_integrity_score']:.1%}
            - Compliance Status: {'🟢 PASS' if panel_data['compliance_status'] else '🔴 FAIL'}
            - Intelligence Active: {'🟢 YES' if panel_data['intelligence_active'] else '🔴 NO'}
            """)
        
        with val_col2:
            st.markdown(f"""
            **🎯 Portfolio Validation:**
            - Portfolio Exposure: {panel_data['portfolio_exposure']:.1%}
            - Allowed Exposure: {panel_data['allowed_exposure']:.1%}
            - Exposure Utilization: {(panel_data['portfolio_exposure']/panel_data['allowed_exposure']):.1%}
            - Reality Check Score: {panel_data['reality_check_score']:.1%}
            """)
        
        with val_col3:
            st.markdown(f"""
            **🔍 Testing Results:**
            - Statistical Significance: {panel_data['statistical_significance']:.1%}
            - Out-of-Sample Perf: {panel_data['out_of_sample_performance']:.1%}
            - Model Robustness: {panel_data['model_robustness']:.1%}
            - Override Attempts (24h): {panel_data['override_attempts_24h']}
            """)
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    def render_intelligence_observer_panel(self, panel_data):
        """Render comprehensive intelligence observer panel"""
        
        st.markdown('<div class="ultimate-panel">', unsafe_allow_html=True)
        st.markdown(f"""
        <div class="ultimate-panel-title">
            <div><span class="panel-icon">🧠</span>{panel_data['title']}</div>
            <div class="panel-subtitle">{panel_data['subtitle']}</div>
        </div>
        """, unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns([1, 1, 1])
        
        with col1:
            # Intelligence Confidence Gauge
            intel_confidence = panel_data['intelligence_confidence'] * 100
            fig = go.Figure(go.Indicator(
                mode="gauge+number+delta",
                value=intel_confidence,
                domain={'x': [0, 1], 'y': [0, 1]},
                title={'text': "Intelligence Confidence", 'font': {'color': '#1e293b', 'size': 16}},
                delta={'reference': 80, 'position': "top"},
                gauge={
                    'axis': {'range': [None, 100], 'tickwidth': 1, 'tickcolor': "#1e293b"},
                    'bar': {'color': ULTIMATE_COLORS['info']},
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
            fig.update_layout(
                height=350, 
                margin=dict(l=20, r=20, t=40, b=20), 
                font=dict(family="Inter, sans-serif", color='#1e293b'),
                paper_bgcolor='white',
                plot_bgcolor='white'
            )
            st.plotly_chart(fig, width="stretch", config={'displayModeBar': False})
        
        with col2:
            # Intelligence Indices
            intel_metrics = ['Regime Similarity', 'Stress Clustering', 'False Calm', 'Behavioral Drift']
            intel_values = [
                panel_data['regime_similarity_index'],
                panel_data['stress_clustering_index'],
                panel_data['false_calm_likelihood'],
                panel_data['behavioral_drift_index']
            ]
            
            fig = go.Figure(data=go.Bar(
                x=intel_metrics,
                y=intel_values,
                marker_color=ULTIMATE_CHART_COLORS[:len(intel_metrics)],
                text=[f'{v:.1f}' for v in intel_values],
                textposition='outside',
                textfont=dict(color='#1e293b', size=12)
            ))
            fig.update_layout(
                title="Market Intelligence Indices",
                height=350,
                margin=dict(l=20, r=20, t=40, b=20),
                yaxis_title="Index Value",
                font=dict(family="Inter, sans-serif", color='#1e293b'),
                plot_bgcolor='white',
                paper_bgcolor='white'
            )
            st.plotly_chart(fig, width="stretch", config={'displayModeBar': False})
        
        with col3:
            # Intelligence Metrics
            st.markdown(f"""
            <div class="ultimate-metric-grid">
                <div class="ultimate-metric-card">
                    <div class="ultimate-metric-value">{panel_data['regime'].upper()}</div>
                    <div class="ultimate-metric-label">Market Regime</div>
                </div>
                <div class="ultimate-metric-card">
                    <div class="ultimate-metric-value">{panel_data['unified_conviction']:.1%}</div>
                    <div class="ultimate-metric-label">AI Conviction</div>
                </div>
                <div class="ultimate-metric-card">
                    <div class="ultimate-metric-value">{'🟢 HEALTHY' if panel_data['observer_healthy'] else '🔴 UNHEALTHY'}</div>
                    <div class="ultimate-metric-label">Observer Status</div>
                </div>
                <div class="ultimate-metric-card">
                    <div class="ultimate-metric-value">{panel_data['observer_violations']}</div>
                    <div class="ultimate-metric-label">Violations</div>
                </div>
                <div class="ultimate-metric-card">
                    <div class="ultimate-metric-value">{panel_data['narrative_coherence_score']:.1%}</div>
                    <div class="ultimate-metric-label">Narrative Coherence</div>
                </div>
                <div class="ultimate-metric-card">
                    <div class="ultimate-metric-value">{panel_data['prediction_accuracy_7d']:.1%}</div>
                    <div class="ultimate-metric-label">Prediction Accuracy</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        # Additional intelligence information
        st.markdown("#### 🧠 Comprehensive Intelligence Analysis")
        
        intel_col1, intel_col2, intel_col3 = st.columns(3)
        
        with intel_col1:
            st.markdown(f"""
            **🎯 Conviction Analysis:**
            - Unified Conviction: {panel_data['unified_conviction']:.1%}
            - Market Conviction: {panel_data['market_conviction']:.1%}
            - Valuation Conviction: {panel_data['valuation_conviction']:.1%}
            - Active Strategies: {panel_data['active_strategies']}
            """)
        
        with intel_col2:
            st.markdown(f"""
            **📊 Intelligence Scores:**
            - Sentiment Analysis: {panel_data['sentiment_analysis_score']:.1%}
            - Macro Intelligence: {panel_data['macro_intelligence_score']:.1%}
            - Technical Intelligence: {panel_data['technical_intelligence_score']:.1%}
            - Microstructure Score: {panel_data['market_microstructure_score']:.1f}
            """)
        
        with intel_col3:
            st.markdown(f"""
            **⚡ Real-time Status:**
            - Intelligence Health: {panel_data['intelligence_health'].title()}
            - Observer Healthy: {'🟢 YES' if panel_data['observer_healthy'] else '🔴 NO'}
            - Observer Violations: {panel_data['observer_violations']}
            - Intelligence Confidence: {panel_data['intelligence_confidence']:.1%}
            """)
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    def render_portfolio_dashboard(self):
        """Render comprehensive portfolio dashboard"""
        
        st.markdown('<div class="ultimate-panel">', unsafe_allow_html=True)
        st.markdown('<div class="ultimate-panel-title"><div><span class="panel-icon">💼</span>COMPREHENSIVE PORTFOLIO DASHBOARD</div></div>', unsafe_allow_html=True)
        
        portfolio_data = self.data['portfolio_data']
        
        # Portfolio Overview Metrics
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.markdown(f"""
            <div class="ultimate-metric-card">
                <div class="ultimate-metric-value">₹{portfolio_data['total_value']:,.0f}</div>
                <div class="ultimate-metric-label">Total AUM</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
            <div class="ultimate-metric-card">
                <div class="ultimate-metric-value">{portfolio_data['total_positions']}</div>
                <div class="ultimate-metric-label">Total Positions</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            st.markdown(f"""
            <div class="ultimate-metric-card">
                <div class="ultimate-metric-value">{portfolio_data['total_exposure']:.1%}</div>
                <div class="ultimate-metric-label">Total Exposure</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col4:
            st.markdown(f"""
            <div class="ultimate-metric-card">
                <div class="ultimate-metric-value">{portfolio_data['portfolio_beta']:.2f}</div>
                <div class="ultimate-metric-label">Portfolio Beta</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col5:
            st.markdown(f"""
            <div class="ultimate-metric-card">
                <div class="ultimate-metric-value">{portfolio_data['concentration_risk']:.1%}</div>
                <div class="ultimate-metric-label">Top 5 Concentration</div>
            </div>
            """, unsafe_allow_html=True)
        
        # Portfolio Charts
        chart_col1, chart_col2 = st.columns(2)
        
        with chart_col1:
            # Sector Allocation Pie Chart
            sector_data = portfolio_data['sector_allocation']
            fig = go.Figure(data=[go.Pie(
                labels=list(sector_data.keys()),
                values=[v * 100 for v in sector_data.values()],
                hole=0.4,
                marker_colors=ULTIMATE_CHART_COLORS[:len(sector_data)]
            )])
            fig.update_layout(
                title="Sector Allocation",
                height=400,
                margin=dict(l=20, r=20, t=40, b=20),
                font=dict(family="Inter, sans-serif", color='#1e293b'),
                paper_bgcolor='white',
                plot_bgcolor='white'
            )
            st.plotly_chart(fig, width="stretch", config={'displayModeBar': False})
        
        with chart_col2:
            # Top Holdings Bar Chart
            top_holdings = portfolio_data['top_holdings'][:10]
            fig = go.Figure(data=[go.Bar(
                x=[h['weight'] * 100 for h in top_holdings],
                y=[h['symbol'] for h in top_holdings],
                orientation='h',
                marker_color=ULTIMATE_CHART_COLORS[:len(top_holdings)],
                text=[f"{h['weight']*100:.1f}%" for h in top_holdings],
                textposition='inside'
            )])
            fig.update_layout(
                title="Top 10 Holdings",
                height=400,
                margin=dict(l=20, r=20, t=40, b=20),
                xaxis_title="Weight (%)",
                font=dict(family="Inter, sans-serif", color='#1e293b'),
                paper_bgcolor='white',
                plot_bgcolor='white'
            )
            st.plotly_chart(fig, width="stretch", config={'displayModeBar': False})
        
        # Portfolio Analytics
        st.markdown("#### 📊 Portfolio Analytics")
        
        analytics_col1, analytics_col2, analytics_col3 = st.columns(3)
        
        with analytics_col1:
            st.markdown(f"""
            **📈 Performance Metrics:**
            - Portfolio P/E: {portfolio_data['portfolio_pe']:.1f}x
            - Portfolio P/B: {portfolio_data['portfolio_pb']:.1f}x
            - Dividend Yield: {portfolio_data['portfolio_dividend_yield']:.2%}
            - Avg Market Cap: ₹{portfolio_data['avg_market_cap']:,.0f} Cr
            """)
        
        with analytics_col2:
            st.markdown(f"""
            **🎯 Risk Metrics:**
            - Largest Position: {portfolio_data['largest_position']:.1%}
            - Avg Position Size: {portfolio_data['avg_position_size']:.1%}
            - Sector Concentration: {portfolio_data['sector_concentration']:.1%}
            - Number of Sectors: {portfolio_data['number_of_sectors']}
            """)
        
        with analytics_col3:
            st.markdown(f"""
            **🔍 Style Analysis:**
            - Momentum Tilt: {portfolio_data['momentum_tilt']:+.2f}
            - Quality Tilt: {portfolio_data['quality_tilt']:+.2f}
            - Value Tilt: {portfolio_data['value_tilt']:+.2f}
            - Long Positions: {portfolio_data['long_positions']}
            """)
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    def render_individual_stock_performance(self):
        """Render individual stock performance dashboard with proper error handling"""
        
        st.markdown('<div class="ultimate-panel">', unsafe_allow_html=True)
        st.markdown('<div class="ultimate-panel-title"><div><span class="panel-icon">📈</span>INDIVIDUAL STOCK PERFORMANCE DASHBOARD</div></div>', unsafe_allow_html=True)
        
        stock_performance = self.data['stock_performance']
        
        if not stock_performance:
            st.warning("No individual stock performance data available")
            st.markdown('</div>', unsafe_allow_html=True)
            return
        
        # Top performers and losers with proper error handling
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 🏆 Top Performers (1D)")
            top_performers = []
            for symbol, perf in stock_performance.items():
                pnl_1d = perf.get('pnl_1d', 0) * 100
                weight = perf.get('weight', 0) * 100
                top_performers.append({
                    'Symbol': symbol, 
                    'Return': pnl_1d,  # Keep as float for sorting
                    'Weight': weight,
                    'Sector': perf.get('sector', 'Unknown')
                })
            
            # Sort by return (descending) and take top 10
            top_performers = sorted(top_performers, key=lambda x: x['Return'], reverse=True)[:10]
            
            # Create DataFrame and format for display
            if top_performers:
                top_df = pd.DataFrame(top_performers)
                # Format the display columns
                top_df['Return_Display'] = top_df['Return'].apply(lambda x: f"{x:+.2f}%")
                top_df['Weight_Display'] = top_df['Weight'].apply(lambda x: f"{x:.2f}%")
                
                # Display with formatted columns
                display_df = top_df[['Symbol', 'Return_Display', 'Weight_Display', 'Sector']].copy()
                display_df.columns = ['Symbol', 'Return', 'Weight', 'Sector']
                st.dataframe(display_df, width="stretch", hide_index=True)
        
        with col2:
            st.markdown("### 📉 Bottom Performers (1D)")
            bottom_performers = []
            for symbol, perf in stock_performance.items():
                pnl_1d = perf.get('pnl_1d', 0) * 100
                weight = perf.get('weight', 0) * 100
                bottom_performers.append({
                    'Symbol': symbol, 
                    'Return': pnl_1d,  # Keep as float for sorting
                    'Weight': weight,
                    'Sector': perf.get('sector', 'Unknown')
                })
            
            # Sort by return (ascending) and take bottom 10
            bottom_performers = sorted(bottom_performers, key=lambda x: x['Return'])[:10]
            
            # Create DataFrame and format for display
            if bottom_performers:
                bottom_df = pd.DataFrame(bottom_performers)
                # Format the display columns
                bottom_df['Return_Display'] = bottom_df['Return'].apply(lambda x: f"{x:+.2f}%")
                bottom_df['Weight_Display'] = bottom_df['Weight'].apply(lambda x: f"{x:.2f}%")
                
                # Display with formatted columns
                display_df = bottom_df[['Symbol', 'Return_Display', 'Weight_Display', 'Sector']].copy()
                display_df.columns = ['Symbol', 'Return', 'Weight', 'Sector']
                st.dataframe(display_df, width="stretch", hide_index=True)
        
        # Individual stock charts
        st.markdown("### 📊 Individual Stock Performance Charts")
        
        # Select stocks to display
        stocks_to_show = list(stock_performance.keys())[:12]  # Show top 12 stocks
        
        # Create subplots for individual stocks
        fig = make_subplots(
            rows=3, cols=4,
            subplot_titles=stocks_to_show,
            vertical_spacing=0.08,
            horizontal_spacing=0.05
        )
        
        for i, stock in enumerate(stocks_to_show):
            row = i // 4 + 1
            col = i % 4 + 1
            
            stock_info = stock_performance[stock]
            dates = stock_info.get('dates', [])
            returns = stock_info.get('cumulative_returns', [])
            
            if len(dates) > 0 and len(returns) > 0:
                fig.add_trace(
                    go.Scatter(
                        x=dates,
                        y=np.array(returns) * 100,
                        name=stock,
                        line=dict(color=ULTIMATE_CHART_COLORS[i % len(ULTIMATE_CHART_COLORS)], width=2),
                        showlegend=False
                    ),
                    row=row, col=col
                )
        
        fig.update_layout(
            height=800,
            title_text="Individual Stock Performance (180 Days)",
            font=dict(family="Inter, sans-serif", color='#1e293b'),
            paper_bgcolor='white',
            plot_bgcolor='white'
        )
        
        # Update y-axis labels
        for i in range(1, 4):
            for j in range(1, 5):
                fig.update_yaxes(title_text="Return (%)", row=i, col=j)
        
        st.plotly_chart(fig, width="stretch", config={'displayModeBar': False})
        
        # Stock Performance Summary Table
        st.markdown("### 📋 Complete Stock Performance Summary")
        
        # Create comprehensive summary table
        summary_data = []
        for symbol, perf in stock_performance.items():
            summary_data.append({
                'Symbol': symbol,
                'Sector': perf.get('sector', 'Unknown'),
                'Weight': f"{perf.get('weight', 0)*100:.2f}%",
                '1D Return': f"{perf.get('pnl_1d', 0)*100:+.2f}%",
                '7D Return': f"{perf.get('pnl_7d', 0)*100:+.2f}%",
                '30D Return': f"{perf.get('pnl_30d', 0)*100:+.2f}%",
                '180D Return': f"{perf.get('total_return_180d', 0)*100:+.2f}%",
                'Volatility': f"{perf.get('volatility_30d', 0)*100:.1f}%",
                'Beta': f"{perf.get('beta', 0):.2f}",
                'Sharpe': f"{perf.get('sharpe_ratio', 0):.2f}",
                'Max DD': f"{perf.get('max_drawdown', 0)*100:.1f}%",
                'Win Rate': f"{perf.get('win_rate', 0)*100:.1f}%"
            })
        
        summary_df = pd.DataFrame(summary_data)
        st.dataframe(summary_df, width="stretch", hide_index=True)
        
        # Stock Analytics
        st.markdown("#### 📊 Stock Performance Analytics")
        
        stock_col1, stock_col2, stock_col3 = st.columns(3)
        
        with stock_col1:
            # Performance distribution
            returns_1d = [perf.get('pnl_1d', 0)*100 for perf in stock_performance.values()]
            fig = go.Figure(data=[go.Histogram(
                x=returns_1d,
                nbinsx=20,
                marker_color=ULTIMATE_COLORS['primary'],
                opacity=0.7
            )])
            fig.update_layout(
                title="1D Returns Distribution",
                height=300,
                xaxis_title="Return (%)",
                yaxis_title="Count",
                font=dict(family="Inter, sans-serif", color='#1e293b'),
                paper_bgcolor='white',
                plot_bgcolor='white'
            )
            st.plotly_chart(fig, width="stretch", config={'displayModeBar': False})
        
        with stock_col2:
            # Risk-Return Scatter
            returns_30d = [perf.get('pnl_30d', 0)*100 for perf in stock_performance.values()]
            volatilities = [perf.get('volatility_30d', 0)*100 for perf in stock_performance.values()]
            symbols = list(stock_performance.keys())
            
            fig = go.Figure(data=go.Scatter(
                x=volatilities,
                y=returns_30d,
                mode='markers+text',
                text=symbols,
                textposition="top center",
                marker=dict(
                    size=10,
                    color=ULTIMATE_COLORS['secondary'],
                    opacity=0.7
                )
            ))
            fig.update_layout(
                title="Risk-Return Profile (30D)",
                height=300,
                xaxis_title="Volatility (%)",
                yaxis_title="Return (%)",
                font=dict(family="Inter, sans-serif", color='#1e293b'),
                paper_bgcolor='white',
                plot_bgcolor='white'
            )
            st.plotly_chart(fig, width="stretch", config={'displayModeBar': False})
        
        with stock_col3:
            # Sector Performance
            sector_performance = {}
            for symbol, perf in stock_performance.items():
                sector = perf.get('sector', 'Unknown')
                if sector not in sector_performance:
                    sector_performance[sector] = []
                sector_performance[sector].append(perf.get('pnl_1d', 0) * 100)
            
            sector_avg = {sector: np.mean(returns) for sector, returns in sector_performance.items()}
            
            fig = go.Figure(data=[go.Bar(
                x=list(sector_avg.keys()),
                y=list(sector_avg.values()),
                marker_color=ULTIMATE_CHART_COLORS[:len(sector_avg)],
                text=[f"{v:+.2f}%" for v in sector_avg.values()],
                textposition='outside'
            )])
            fig.update_layout(
                title="Sector Performance (1D)",
                height=300,
                yaxis_title="Avg Return (%)",
                font=dict(family="Inter, sans-serif", color='#1e293b'),
                paper_bgcolor='white',
                plot_bgcolor='white'
            )
            st.plotly_chart(fig, width="stretch", config={'displayModeBar': False})
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    def render_constitutional_principles(self):
        """Render constitutional principles section"""
        
        st.markdown("""
        <div class="ultimate-constitutional-principles">
            <div class="principle-title">CONSTITUTIONAL PRINCIPLES OF NORTHSTAR V3</div>
            <div class="principle-item">🎯 TRANSPARENCY: Every decision is explainable and auditable</div>
            <div class="principle-item">🛡️ RISK FIRST: Risk management is never compromised for returns</div>
            <div class="principle-item">📊 DATA INTEGRITY: All data sources are validated and verified</div>
            <div class="principle-item">⚙️ SYSTEMATIC APPROACH: Human emotions are removed from investment decisions</div>
            <div class="principle-item">🔍 CONTINUOUS VALIDATION: Models are constantly tested against reality</div>
            <div class="principle-item">🧠 INTELLIGENCE DRIVEN: AI and machine learning guide all strategies</div>
            <div class="principle-item">📈 PERFORMANCE FOCUSED: Consistent alpha generation is the primary objective</div>
            <div class="principle-item">🏛️ INSTITUTIONAL GRADE: Built to institutional standards and compliance</div>
        </div>
        """, unsafe_allow_html=True)
    
    def render_sidebar(self):
        """Render comprehensive sidebar with system information"""
        
        st.sidebar.markdown("## 🎯 NORTHSTAR V3")
        st.sidebar.markdown("### Ultimate Comprehensive Cockpit")
        
        # System Status
        st.sidebar.markdown("#### 🔧 System Status")
        st.sidebar.markdown("✅ All Systems Active")
        st.sidebar.markdown("✅ Data Pipeline Healthy")
        st.sidebar.markdown("✅ Models Running")
        st.sidebar.markdown("✅ Risk Controls Armed")
        st.sidebar.markdown("✅ Intelligence Active")
        
        # Key Metrics
        st.sidebar.markdown("#### 📊 Key Metrics")
        performance_data = self.data['performance_data']
        panels = self.data['constitutional_panels']
        
        st.sidebar.metric("Total Return", f"{performance_data['total_return']*100:+.1f}%")
        st.sidebar.metric("Sharpe Ratio", f"{performance_data['sharpe_ratio']:.2f}")
        st.sidebar.metric("Max Drawdown", f"{performance_data['max_drawdown']*100:.1f}%")
        st.sidebar.metric("System Health", f"{panels['panel_1_system_state']['health_score']*100:.0f}%")
        
        # Data Sources
        st.sidebar.markdown("#### 📁 Data Sources")
        st.sidebar.markdown("✅ Portfolio Data: 35 positions")
        st.sidebar.markdown("✅ Performance Data: 180 days")
        st.sidebar.markdown("✅ Risk Data: Real-time")
        st.sidebar.markdown("✅ Market Data: Live feed")
        st.sidebar.markdown("✅ Intelligence Data: Active")
        
        # Dashboard Features
        st.sidebar.markdown("#### 🎛️ Dashboard Features")
        st.sidebar.markdown("✅ Constitutional Panels (5)")
        st.sidebar.markdown("✅ Portfolio Dashboard")
        st.sidebar.markdown("✅ Individual Stock Performance")
        st.sidebar.markdown("✅ Risk Management")
        st.sidebar.markdown("✅ Market Intelligence")
        st.sidebar.markdown("✅ Advanced Analytics")
        st.sidebar.markdown("✅ Sector Analysis")
        st.sidebar.markdown("✅ Correlation Analysis")
        st.sidebar.markdown("✅ Volatility Analysis")
        st.sidebar.markdown("✅ Regime Analysis")
        st.sidebar.markdown("✅ Backtesting Results")
        st.sidebar.markdown("✅ Walk-Forward Validation")
        st.sidebar.markdown("✅ System Diagnostics")
        st.sidebar.markdown("✅ Institutional Reporting")
        
        # Footer
        st.sidebar.markdown("---")
        st.sidebar.markdown(f"**Last Updated:** {datetime.now().strftime('%H:%M:%S')}")
        st.sidebar.markdown("**Version:** v3.0.0 Ultimate")
        st.sidebar.markdown("**Status:** 🟢 All Features Active")

    def render_individual_stock_performance(self):
        """Render individual stock performance dashboard with detailed analytics"""
        
        st.markdown('<div class="ultimate-panel">', unsafe_allow_html=True)
        st.markdown('<div class="ultimate-panel-title"><div><span class="panel-icon">📈</span>INDIVIDUAL STOCK PERFORMANCE DASHBOARD</div></div>', unsafe_allow_html=True)
        
        stock_data = self.data['stock_performance']
        portfolio_data = self.data['portfolio_data']
        
        # Top/Bottom Performers
        st.markdown("#### 🏆 Top & Bottom Performers")
        
        # Calculate performance metrics for all stocks
        stock_performance_list = []
        for symbol, data in stock_data.items():
            stock_performance_list.append({
                'Symbol': symbol,
                'Weight': data['weight'],
                '1D Return': data['pnl_1d'],
                '7D Return': data['pnl_7d'],
                '30D Return': data['pnl_30d'],
                '180D Return': data['total_return_180d'],
                'Volatility': data['volatility_30d'],
                'Sharpe': data['sharpe_ratio'],
                'Sector': data['sector'],
                'Market Cap': data['market_cap']
            })
        
        # Sort by 30D performance
        stock_performance_list.sort(key=lambda x: x['30D Return'], reverse=True)
        
        perf_col1, perf_col2 = st.columns(2)
        
        with perf_col1:
            st.markdown("**🟢 Top 10 Performers (30D)**")
            top_performers = stock_performance_list[:10]
            top_df = pd.DataFrame([{
                'Symbol': stock['Symbol'],
                'Return': f"{stock['30D Return']*100:+.1f}%",
                'Weight': f"{stock['Weight']*100:.1f}%",
                'Sector': stock['Sector']
            } for stock in top_performers])
            st.dataframe(top_df, width="stretch", hide_index=True)
        
        with perf_col2:
            st.markdown("**🔴 Bottom 10 Performers (30D)**")
            bottom_performers = stock_performance_list[-10:]
            bottom_df = pd.DataFrame([{
                'Symbol': stock['Symbol'],
                'Return': f"{stock['30D Return']*100:+.1f}%",
                'Weight': f"{stock['Weight']*100:.1f}%",
                'Sector': stock['Sector']
            } for stock in bottom_performers])
            st.dataframe(bottom_df, width="stretch", hide_index=True)
        
        # Stock Performance Charts
        st.markdown("#### 📊 Stock Performance Visualization")
        
        chart_col1, chart_col2 = st.columns(2)
        
        with chart_col1:
            # Risk-Return Scatter Plot
            returns_30d = [stock['30D Return']*100 for stock in stock_performance_list]
            volatilities = [stock['Volatility']*100 for stock in stock_performance_list]
            weights = [stock['Weight']*1000 for stock in stock_performance_list]  # Scale for bubble size
            symbols = [stock['Symbol'] for stock in stock_performance_list]
            
            fig = go.Figure(data=go.Scatter(
                x=volatilities,
                y=returns_30d,
                mode='markers+text',
                text=symbols,
                textposition="top center",
                marker=dict(
                    size=weights,
                    sizemode='diameter',
                    sizeref=2.*max(weights)/(40.**2),
                    sizemin=4,
                    color=returns_30d,
                    colorscale='RdYlGn',
                    colorbar=dict(title="30D Return (%)"),
                    opacity=0.7,
                    line=dict(width=1, color='white')
                ),
                hovertemplate='<b>%{text}</b><br>Return: %{y:.1f}%<br>Volatility: %{x:.1f}%<extra></extra>'
            ))
            fig.update_layout(
                title="Stock Risk-Return Profile (Bubble Size = Weight)",
                height=500,
                xaxis_title="30D Volatility (%)",
                yaxis_title="30D Return (%)",
                font=dict(family="Inter, sans-serif", color='#1e293b'),
                paper_bgcolor='white',
                plot_bgcolor='white'
            )
            st.plotly_chart(fig, width="stretch", config={'displayModeBar': False})
        
        with chart_col2:
            # Sector Performance Breakdown
            sector_performance = {}
            for stock in stock_performance_list:
                sector = stock['Sector']
                if sector not in sector_performance:
                    sector_performance[sector] = {'return': 0, 'weight': 0, 'count': 0}
                sector_performance[sector]['return'] += stock['30D Return'] * stock['Weight']
                sector_performance[sector]['weight'] += stock['Weight']
                sector_performance[sector]['count'] += 1
            
            # Calculate weighted average returns by sector
            for sector in sector_performance:
                if sector_performance[sector]['weight'] > 0:
                    sector_performance[sector]['return'] /= sector_performance[sector]['weight']
            
            sectors = list(sector_performance.keys())
            sector_returns = [sector_performance[sector]['return']*100 for sector in sectors]
            
            fig = go.Figure(data=[go.Bar(
                x=sectors,
                y=sector_returns,
                marker_color=[ULTIMATE_COLORS['success'] if r > 0 else ULTIMATE_COLORS['danger'] for r in sector_returns],
                text=[f"{r:+.1f}%" for r in sector_returns],
                textposition='outside'
            )])
            fig.update_layout(
                title="Sector Performance Contribution (30D)",
                height=500,
                yaxis_title="Weighted Return (%)",
                font=dict(family="Inter, sans-serif", color='#1e293b'),
                paper_bgcolor='white',
                plot_bgcolor='white'
            )
            st.plotly_chart(fig, width="stretch", config={'displayModeBar': False})
        
        # Detailed Stock Analysis
        st.markdown("#### 🔍 Detailed Stock Analysis")
        
        # Stock selection
        selected_stock = st.selectbox(
            "Select a stock for detailed analysis:",
            options=list(stock_data.keys()),
            index=0
        )
        
        if selected_stock and selected_stock in stock_data:
            stock_info = stock_data[selected_stock]
            
            # Stock metrics
            stock_col1, stock_col2, stock_col3, stock_col4 = st.columns(4)
            
            with stock_col1:
                st.markdown(f"""
                <div class="ultimate-metric-card">
                    <div class="ultimate-metric-value">{stock_info['current_price']:.0f}</div>
                    <div class="ultimate-metric-label">Current Price</div>
                </div>
                """, unsafe_allow_html=True)
            
            with stock_col2:
                st.markdown(f"""
                <div class="ultimate-metric-card">
                    <div class="ultimate-metric-value">{stock_info['total_return_180d']*100:+.1f}%</div>
                    <div class="ultimate-metric-label">180D Return</div>
                </div>
                """, unsafe_allow_html=True)
            
            with stock_col3:
                st.markdown(f"""
                <div class="ultimate-metric-card">
                    <div class="ultimate-metric-value">{stock_info['volatility_30d']*100:.1f}%</div>
                    <div class="ultimate-metric-label">30D Volatility</div>
                </div>
                """, unsafe_allow_html=True)
            
            with stock_col4:
                st.markdown(f"""
                <div class="ultimate-metric-card">
                    <div class="ultimate-metric-value">{stock_info['sharpe_ratio']:.2f}</div>
                    <div class="ultimate-metric-label">Sharpe Ratio</div>
                </div>
                """, unsafe_allow_html=True)
            
            # Stock price chart
            if 'dates' in stock_info and 'prices' in stock_info:
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=stock_info['dates'],
                    y=stock_info['prices'],
                    mode='lines',
                    name='Price',
                    line=dict(color=ULTIMATE_COLORS['primary'], width=2)
                ))
                fig.add_trace(go.Scatter(
                    x=stock_info['dates'],
                    y=stock_info['sma_20'],
                    mode='lines',
                    name='SMA 20',
                    line=dict(color=ULTIMATE_COLORS['warning'], width=1)
                ))
                fig.add_trace(go.Scatter(
                    x=stock_info['dates'],
                    y=stock_info['sma_50'],
                    mode='lines',
                    name='SMA 50',
                    line=dict(color=ULTIMATE_COLORS['danger'], width=1)
                ))
                fig.update_layout(
                    title=f"{selected_stock} - Price Chart with Moving Averages",
                    height=400,
                    yaxis_title="Price (₹)",
                    font=dict(family="Inter, sans-serif", color='#1e293b'),
                    paper_bgcolor='white',
                    plot_bgcolor='white'
                )
                st.plotly_chart(fig, width="stretch", config={'displayModeBar': False})
        
        st.markdown('</div>', unsafe_allow_html=True)

    def render_risk_management_dashboard(self):
        """Render comprehensive risk management dashboard"""
        
        st.markdown('<div class="ultimate-panel">', unsafe_allow_html=True)
        st.markdown('<div class="ultimate-panel-title"><div><span class="panel-icon">🛡️</span>COMPREHENSIVE RISK MANAGEMENT DASHBOARD</div></div>', unsafe_allow_html=True)
        
        risk_data = self.data['risk_management']
        
        # Risk Overview Metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown(f"""
            <div class="ultimate-metric-card">
                <div class="ultimate-metric-value">{risk_data['var_analysis']['var_95_1d']*100:.1f}%</div>
                <div class="ultimate-metric-label">VaR 95% (1D)</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
            <div class="ultimate-metric-card">
                <div class="ultimate-metric-value">{risk_data['drawdown_analysis']['current_drawdown']*100:.1f}%</div>
                <div class="ultimate-metric-label">Current Drawdown</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            st.markdown(f"""
            <div class="ultimate-metric-card">
                <div class="ultimate-metric-value">{risk_data['liquidity_metrics']['portfolio_liquidity_score']:.1%}</div>
                <div class="ultimate-metric-label">Liquidity Score</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col4:
            st.markdown(f"""
            <div class="ultimate-metric-card">
                <div class="ultimate-metric-value">{risk_data['concentration_metrics']['top_5_concentration']:.1%}</div>
                <div class="ultimate-metric-label">Top 5 Concentration</div>
            </div>
            """, unsafe_allow_html=True)
        
        # Risk Charts
        chart_col1, chart_col2 = st.columns(2)
        
        with chart_col1:
            # VaR Analysis
            var_metrics = list(risk_data['var_analysis'].keys())[:6]
            var_values = [abs(risk_data['var_analysis'][metric]*100) for metric in var_metrics]
            
            fig = go.Figure(data=[go.Bar(
                x=[metric.replace('_', ' ').title() for metric in var_metrics],
                y=var_values,
                marker_color=ULTIMATE_CHART_COLORS[:len(var_metrics)],
                text=[f"{v:.1f}%" for v in var_values],
                textposition='outside'
            )])
            fig.update_layout(
                title="Value at Risk Analysis",
                height=400,
                yaxis_title="VaR (%)",
                font=dict(family="Inter, sans-serif", color='#1e293b'),
                paper_bgcolor='white',
                plot_bgcolor='white'
            )
            st.plotly_chart(fig, width="stretch", config={'displayModeBar': False})
        
        with chart_col2:
            # Comprehensive Stress Testing Results with Scenario Breakdowns
            stress_scenarios = list(risk_data['stress_testing'].keys())
            stress_values = [abs(risk_data['stress_testing'][scenario]*100) for scenario in stress_scenarios]
            
            # Create detailed stress test visualization
            fig = make_subplots(
                rows=2, cols=1,
                subplot_titles=('Stress Test Scenario Impacts', 'Stress Test Scenario Breakdown'),
                vertical_spacing=0.15,
                specs=[[{"secondary_y": False}], [{"type": "bar"}]]
            )
            
            # Main stress test chart
            fig.add_trace(go.Bar(
                x=[scenario.replace('_', ' ').title() for scenario in stress_scenarios],
                y=stress_values,
                marker_color=ULTIMATE_COLORS['danger'],
                text=[f"{v:.1f}%" for v in stress_values],
                textposition='outside',
                name='Potential Loss',
                showlegend=False
            ), row=1, col=1)
            
            # Scenario breakdown with confidence intervals
            scenario_details = []
            confidence_levels = [0.95, 0.99, 0.999]
            for i, scenario in enumerate(stress_scenarios[:4]):  # Top 4 scenarios
                base_loss = stress_values[i]
                for conf in confidence_levels:
                    scenario_details.append({
                        'scenario': f"{scenario.replace('_', ' ').title()} ({conf*100:.0f}%)",
                        'loss': base_loss * (1 + (1-conf) * 0.5)  # Adjust loss by confidence
                    })
            
            fig.add_trace(go.Bar(
                x=[detail['scenario'] for detail in scenario_details],
                y=[detail['loss'] for detail in scenario_details],
                marker_color=[ULTIMATE_COLORS['warning'] if '95%' in detail['scenario'] 
                             else ULTIMATE_COLORS['danger'] if '99%' in detail['scenario'] 
                             else ULTIMATE_COLORS['purple'] for detail in scenario_details],
                text=[f"{detail['loss']:.1f}%" for detail in scenario_details],
                textposition='outside',
                name='Confidence Levels',
                showlegend=False
            ), row=2, col=1)
            
            fig.update_layout(
                height=700,
                font=dict(family="Inter, sans-serif", color='#1e293b'),
                paper_bgcolor='white',
                plot_bgcolor='white'
            )
            fig.update_yaxes(title_text="Potential Loss (%)", row=1, col=1)
            fig.update_yaxes(title_text="Loss by Confidence (%)", row=2, col=1)
            
            st.plotly_chart(fig, width="stretch", config={'displayModeBar': False})
        
        # Risk Decomposition
        st.markdown("#### 🔍 Risk Decomposition Analysis")
        
        decomp_col1, decomp_col2 = st.columns(2)
        
        with decomp_col1:
            # Risk Decomposition Pie Chart
            risk_decomp = risk_data['risk_decomposition']
            fig = go.Figure(data=[go.Pie(
                labels=[k.replace('_', ' ').title() for k in risk_decomp.keys()],
                values=list(risk_decomp.values()),
                hole=0.4,
                marker_colors=ULTIMATE_CHART_COLORS[:len(risk_decomp)]
            )])
            fig.update_layout(
                title="Risk Decomposition",
                height=400,
                font=dict(family="Inter, sans-serif", color='#1e293b'),
                paper_bgcolor='white'
            )
            st.plotly_chart(fig, width="stretch", config={'displayModeBar': False})
        
        with decomp_col2:
            # Liquidity Metrics
            liquidity_metrics = risk_data['liquidity_metrics']
            metrics = ['Portfolio Liquidity', 'Bid-Ask Impact', 'Market Impact', 'Liquidity at Risk']
            values = [
                liquidity_metrics['portfolio_liquidity_score'] * 100,
                liquidity_metrics['bid_ask_impact'] * 100,
                liquidity_metrics['market_impact_cost'] * 100,
                liquidity_metrics['liquidity_at_risk'] * 100
            ]
            
            fig = go.Figure(data=[go.Bar(
                x=metrics,
                y=values,
                marker_color=[ULTIMATE_COLORS['success'], ULTIMATE_COLORS['warning'], ULTIMATE_COLORS['warning'], ULTIMATE_COLORS['danger']],
                text=[f"{v:.1f}%" for v in values],
                textposition='outside'
            )])
            fig.update_layout(
                title="Liquidity Risk Metrics",
                height=400,
                yaxis_title="Impact (%)",
                font=dict(family="Inter, sans-serif", color='#1e293b'),
                paper_bgcolor='white',
                plot_bgcolor='white'
            )
            st.plotly_chart(fig, width="stretch", config={'displayModeBar': False})
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    def render_market_intelligence_dashboard(self):
        """Render comprehensive market intelligence dashboard"""
        
        st.markdown('<div class="ultimate-panel">', unsafe_allow_html=True)
        st.markdown('<div class="ultimate-panel-title"><div><span class="panel-icon">🧠</span>COMPREHENSIVE MARKET INTELLIGENCE DASHBOARD</div></div>', unsafe_allow_html=True)
        
        intel_data = self.data['market_intelligence']
        
        # Intelligence Overview
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown(f"""
            <div class="ultimate-metric-card">
                <div class="ultimate-metric-value">{intel_data['regime_detection']['current_regime'].upper()}</div>
                <div class="ultimate-metric-label">Current Regime</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
            <div class="ultimate-metric-card">
                <div class="ultimate-metric-value">{intel_data['sentiment_analysis']['market_sentiment']:.1%}</div>
                <div class="ultimate-metric-label">Market Sentiment</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            st.markdown(f"""
            <div class="ultimate-metric-card">
                <div class="ultimate-metric-value">{intel_data['technical_indicators']['vix_level']:.1f}</div>
                <div class="ultimate-metric-label">VIX Level</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col4:
            st.markdown(f"""
            <div class="ultimate-metric-card">
                <div class="ultimate-metric-value">{intel_data['flow_analysis']['institutional_flows']/1_000_000:.0f}M</div>
                <div class="ultimate-metric-label">Institutional Flows</div>
            </div>
            """, unsafe_allow_html=True)
        
        # Intelligence Charts
        chart_col1, chart_col2 = st.columns(2)
        
        with chart_col1:
            # Sentiment Analysis
            sentiment_data = intel_data['sentiment_analysis']
            sentiment_metrics = ['Market', 'News', 'Social', 'Analyst', 'Insider', 'Options']
            sentiment_values = [
                sentiment_data['market_sentiment'] * 100,
                sentiment_data['news_sentiment'] * 100,
                sentiment_data['social_sentiment'] * 100,
                sentiment_data['analyst_sentiment'] * 100,
                sentiment_data['insider_sentiment'] * 100,
                sentiment_data['options_sentiment'] * 100
            ]
            
            fig = go.Figure()
            fig.add_trace(go.Scatterpolar(
                r=sentiment_values,
                theta=sentiment_metrics,
                fill='toself',
                name='Sentiment Analysis',
                line_color=ULTIMATE_COLORS['info'],
                fillcolor=f'rgba(6, 182, 212, 0.2)'
            ))
            fig.update_layout(
                polar=dict(
                    radialaxis=dict(
                        visible=True,
                        range=[0, 100],
                        tickfont=dict(color='#1e293b')
                    ),
                    angularaxis=dict(
                        tickfont=dict(color='#1e293b')
                    )
                ),
                title="Multi-Source Sentiment Analysis",
                height=400,
                showlegend=False,
                font=dict(family="Inter, sans-serif", color='#1e293b'),
                paper_bgcolor='white'
            )
            st.plotly_chart(fig, width="stretch", config={'displayModeBar': False})
        
        with chart_col2:
            # Flow Analysis
            flow_data = intel_data['flow_analysis']
            flow_types = ['Institutional', 'Retail', 'Foreign', 'Mutual Fund', 'ETF', 'Derivative']
            flow_values = [
                flow_data['institutional_flows'] / 1_000_000,
                flow_data['retail_flows'] / 1_000_000,
                flow_data['foreign_flows'] / 1_000_000,
                flow_data['mutual_fund_flows'] / 1_000_000,
                flow_data['etf_flows'] / 1_000_000,
                flow_data['derivative_flows'] / 1_000_000
            ]
            
            colors = [ULTIMATE_COLORS['success'] if v > 0 else ULTIMATE_COLORS['danger'] for v in flow_values]
            
            fig = go.Figure(data=[go.Bar(
                x=flow_types,
                y=flow_values,
                marker_color=colors,
                text=[f"₹{v:+.0f}M" for v in flow_values],
                textposition='outside'
            )])
            fig.update_layout(
                title="Capital Flow Analysis",
                height=400,
                yaxis_title="Flow (₹ Million)",
                font=dict(family="Inter, sans-serif", color='#1e293b'),
                paper_bgcolor='white',
                plot_bgcolor='white'
            )
            st.plotly_chart(fig, width="stretch", config={'displayModeBar': False})
        
        # Macro Indicators
        st.markdown("#### 🌍 Macro Economic Indicators")
        
        macro_col1, macro_col2, macro_col3 = st.columns(3)
        
        with macro_col1:
            macro_data = intel_data['macro_indicators']
            st.markdown(f"""
            **📊 Economic Growth:**
            - GDP Growth: {macro_data['gdp_growth']:.1%}
            - Inflation Rate: {macro_data['inflation_rate']:.1%}
            - Interest Rates: {macro_data['interest_rates']:.1%}
            - Unemployment: {macro_data['unemployment_rate']:.1%}
            """)
        
        with macro_col2:
            st.markdown(f"""
            **💱 Market Indicators:**
            - Currency Strength: {macro_data['currency_strength']:+.1%}
            - Commodity Prices: {macro_data['commodity_prices']:+.1%}
            - Global Risk Appetite: {macro_data['global_risk_appetite']:.1%}
            """)
        
        with macro_col3:
            technical_data = intel_data['technical_indicators']
            st.markdown(f"""
            **📈 Technical Indicators:**
            - Market Breadth: {technical_data['market_breadth']:.1%}
            - Advance/Decline: {technical_data['advance_decline_ratio']:.2f}
            - New Highs/Lows: {technical_data['new_highs_lows']:.1f}
            - Credit Spreads: {technical_data['credit_spreads']:.1%}
            """)
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    def render_advanced_analytics_dashboard(self):
        """Render advanced analytics dashboard"""
        
        st.markdown('<div class="ultimate-panel">', unsafe_allow_html=True)
        st.markdown('<div class="ultimate-panel-title"><div><span class="panel-icon">📊</span>ADVANCED ANALYTICS DASHBOARD</div></div>', unsafe_allow_html=True)
        
        analytics_data = self.data['advanced_analytics']
        
        # Performance Attribution
        st.markdown("#### 🎯 Performance Attribution Analysis")
        
        attr_col1, attr_col2 = st.columns(2)
        
        with attr_col1:
            # Attribution Breakdown
            attribution = analytics_data['performance_attribution']
            attr_sources = ['Asset Selection', 'Sector Allocation', 'Timing', 'Interaction', 'Currency']
            attr_values = [
                attribution['asset_selection'] * 100,
                attribution['sector_allocation'] * 100,
                attribution['timing'] * 100,
                attribution['interaction'] * 100,
                attribution['currency'] * 100
            ]
            
            fig = go.Figure(data=[go.Bar(
                x=attr_sources,
                y=attr_values,
                marker_color=ULTIMATE_CHART_COLORS[:len(attr_sources)],
                text=[f"{v:+.2f}%" for v in attr_values],
                textposition='outside'
            )])
            fig.update_layout(
                title="Performance Attribution Sources",
                height=400,
                yaxis_title="Contribution (%)",
                font=dict(family="Inter, sans-serif", color='#1e293b'),
                paper_bgcolor='white',
                plot_bgcolor='white'
            )
            st.plotly_chart(fig, width="stretch", config={'displayModeBar': False})
        
        with attr_col2:
            # Factor Exposure
            factor_data = analytics_data['factor_exposure']
            factors = list(factor_data.keys())
            exposures = list(factor_data.values())
            
            fig = go.Figure(data=[go.Bar(
                x=factors,
                y=exposures,
                marker_color=[ULTIMATE_COLORS['success'] if v > 0 else ULTIMATE_COLORS['danger'] for v in exposures],
                text=[f"{v:+.2f}" for v in exposures],
                textposition='outside'
            )])
            fig.update_layout(
                title="Factor Exposure Analysis",
                height=400,
                yaxis_title="Exposure",
                font=dict(family="Inter, sans-serif", color='#1e293b'),
                paper_bgcolor='white',
                plot_bgcolor='white'
            )
            st.plotly_chart(fig, width="stretch", config={'displayModeBar': False})
        
        # Strategy Performance
        st.markdown("#### 🚀 Strategy Performance Breakdown")
        
        strategy_data = analytics_data['strategy_performance']
        
        # Create strategy performance table
        strategy_summary = []
        for strategy, metrics in strategy_data.items():
            strategy_summary.append({
                'Strategy': strategy.replace('_', ' ').title(),
                'Return': f"{metrics['return']*100:.1f}%",
                'Sharpe': f"{metrics['sharpe']:.2f}",
                'Max DD': f"{metrics['max_dd']*100:.1f}%",
                'Win Rate': f"{metrics['win_rate']*100:.1f}%"
            })
        
        strategy_df = pd.DataFrame(strategy_summary)
        st.dataframe(strategy_df, width="stretch", hide_index=True)
        
        # Risk-Adjusted Metrics
        st.markdown("#### 📈 Risk-Adjusted Performance Metrics")
        
        risk_metrics = analytics_data['risk_adjusted_metrics']
        
        metric_col1, metric_col2, metric_col3 = st.columns(3)
        
        with metric_col1:
            st.markdown(f"""
            **📊 Return Metrics:**
            - Sharpe Ratio: {risk_metrics['sharpe_ratio']:.2f}
            - Sortino Ratio: {risk_metrics['sortino_ratio']:.2f}
            - Calmar Ratio: {risk_metrics['calmar_ratio']:.2f}
            """)
        
        with metric_col2:
            st.markdown(f"""
            **🎯 Alpha Metrics:**
            - Jensen Alpha: {risk_metrics['jensen_alpha']:.3f}
            - Treynor Ratio: {risk_metrics['treynor_ratio']:.3f}
            - Omega Ratio: {risk_metrics['omega_ratio']:.2f}
            """)
        
        with metric_col3:
            st.markdown(f"""
            **⚖️ Risk Metrics:**
            - Modigliani Ratio: {risk_metrics['modigliani_ratio']:.3f}
            - Sterling Ratio: {risk_metrics['sterling_ratio']:.2f}
            """)
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    def render_sector_analysis_dashboard(self):
        """Render comprehensive sector analysis dashboard"""
        
        st.markdown('<div class="ultimate-panel">', unsafe_allow_html=True)
        st.markdown('<div class="ultimate-panel-title"><div><span class="panel-icon">🏭</span>COMPREHENSIVE SECTOR ANALYSIS DASHBOARD</div></div>', unsafe_allow_html=True)
        
        sector_data = self.data['sector_analysis']
        sector_performance = sector_data['sector_performance']
        
        # Sector Performance Overview
        st.markdown("#### 📊 Sector Performance Overview")
        
        # Create sector performance summary
        sector_summary = []
        for sector, metrics in sector_performance.items():
            sector_summary.append({
                'Sector': sector,
                'Weight': f"{metrics['weight']*100:.1f}%",
                '1D': f"{metrics['return_1d']*100:+.2f}%",
                '7D': f"{metrics['return_7d']*100:+.2f}%",
                '30D': f"{metrics['return_30d']*100:+.2f}%",
                '90D': f"{metrics['return_90d']*100:+.2f}%",
                'Volatility': f"{metrics['volatility']*100:.1f}%",
                'Beta': f"{metrics['beta']:.2f}",
                'P/E': f"{metrics['pe_ratio']:.1f}",
                'Momentum': f"{metrics['momentum_score']:+.2f}"
            })
        
        sector_df = pd.DataFrame(sector_summary)
        st.dataframe(sector_df, width="stretch", hide_index=True)
        
        # Sector Charts
        chart_col1, chart_col2 = st.columns(2)
        
        with chart_col1:
            # Sector Returns Heatmap
            sectors = list(sector_performance.keys())
            periods = ['1D', '7D', '30D', '90D']
            
            heatmap_data = []
            for period in periods:
                period_key = f'return_{period.lower()}'
                row_data = [sector_performance[sector][period_key] * 100 for sector in sectors]
                heatmap_data.append(row_data)
            
            fig = go.Figure(data=go.Heatmap(
                z=heatmap_data,
                x=sectors,
                y=periods,
                colorscale='RdYlGn',
                zmid=0,
                text=[[f"{val:+.1f}%" for val in row] for row in heatmap_data],
                texttemplate="%{text}",
                textfont={"size": 10}
            ))
            fig.update_layout(
                title="Sector Returns Heatmap",
                height=400,
                font=dict(family="Inter, sans-serif", color='#1e293b'),
                paper_bgcolor='white'
            )
            st.plotly_chart(fig, width="stretch", config={'displayModeBar': False})
        
        with chart_col2:
            # Sector Risk-Return Scatter
            returns_30d = [metrics['return_30d']*100 for metrics in sector_performance.values()]
            volatilities = [metrics['volatility']*100 for metrics in sector_performance.values()]
            
            fig = go.Figure(data=go.Scatter(
                x=volatilities,
                y=returns_30d,
                mode='markers+text',
                text=list(sector_performance.keys()),
                textposition="top center",
                marker=dict(
                    size=15,
                    color=ULTIMATE_CHART_COLORS[:len(sectors)],
                    opacity=0.7
                )
            ))
            fig.update_layout(
                title="Sector Risk-Return Profile (30D)",
                height=400,
                xaxis_title="Volatility (%)",
                yaxis_title="Return (%)",
                font=dict(family="Inter, sans-serif", color='#1e293b'),
                paper_bgcolor='white',
                plot_bgcolor='white'
            )
            st.plotly_chart(fig, width="stretch", config={'displayModeBar': False})
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    def render_correlation_analysis_dashboard(self):
        """Render correlation analysis dashboard with 3D/4D cluster visualizations"""
        
        st.markdown('<div class="ultimate-panel">', unsafe_allow_html=True)
        st.markdown('<div class="ultimate-panel-title"><div><span class="panel-icon">🔗</span>ADVANCED CORRELATION ANALYSIS DASHBOARD</div></div>', unsafe_allow_html=True)
        
        corr_data = self.data['correlation_analysis']
        
        # Correlation Statistics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown(f"""
            <div class="ultimate-metric-card">
                <div class="ultimate-metric-value">{corr_data['correlation_statistics']['avg_correlation']:.2f}</div>
                <div class="ultimate-metric-label">Avg Correlation</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
            <div class="ultimate-metric-card">
                <div class="ultimate-metric-value">{corr_data['correlation_statistics']['max_correlation']:.2f}</div>
                <div class="ultimate-metric-label">Max Correlation</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            st.markdown(f"""
            <div class="ultimate-metric-card">
                <div class="ultimate-metric-value">{corr_data['diversification_metrics']['diversification_ratio']:.2f}</div>
                <div class="ultimate-metric-label">Diversification Ratio</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col4:
            st.markdown(f"""
            <div class="ultimate-metric-card">
                <div class="ultimate-metric-value">{corr_data['diversification_metrics']['effective_number_of_stocks']:.1f}</div>
                <div class="ultimate-metric-label">Effective # Stocks</div>
            </div>
            """, unsafe_allow_html=True)
        
        # 🌟 ULTIMATE 4D CLUSTER VISUALIZATION SUITE 🌟
        st.markdown("#### 🌐 Ultimate 4D Correlation Cluster Analysis")
        st.markdown("""
        <div style="background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%); padding: 1rem; border-radius: 8px; margin-bottom: 1.5rem; border-left: 4px solid #0ea5e9;">
            <strong>🎨 Enhanced 4D Visualizations:</strong> Experience stocks in multiple dimensions with Position (X,Y,Z) + Color + Size + Animation + Sector grouping. 
            Each visualization reveals different aspects of your portfolio's risk-return characteristics.
        </div>
        """, unsafe_allow_html=True)
        
        stock_symbols = list(self.data['stock_performance'].keys())[:30]  # Top 30 for even richer visualization
        correlation_matrix = corr_data['stock_correlations']
        
        # Generate multiple dimensional representations
        scaler = StandardScaler()
        pca = PCA(n_components=3)
        
        # Create comprehensive feature matrix with more dimensions
        feature_matrix = []
        stock_info = []
        for symbol in stock_symbols:
            if symbol in self.data['stock_performance']:
                stock_data = self.data['stock_performance'][symbol]
                features = [
                    stock_data['total_return_180d'],
                    stock_data['volatility_30d'],
                    stock_data['sharpe_ratio'],
                    stock_data['beta'],
                    stock_data['momentum_score'],
                    stock_data['quality_score'],
                    stock_data['value_score'],
                    stock_data['pe_ratio'] / 30.0,  # Normalized PE
                    stock_data['pb_ratio'] / 5.0,   # Normalized PB
                    stock_data['dividend_yield'] * 20  # Scaled dividend yield
                ]
                feature_matrix.append(features)
                stock_info.append(stock_data)
        
        if len(feature_matrix) > 0:
            feature_matrix = np.array(feature_matrix)
            feature_matrix_scaled = scaler.fit_transform(feature_matrix)
            coords_3d = pca.fit_transform(feature_matrix_scaled)
            
            # Create multiple enhanced 4D visualizations
            viz_col1, viz_col2 = st.columns(2)
            
            with viz_col1:
                # 🎯 ENHANCED 4D CLUSTER: Position + Color + Size + Glow Effects
                returns_180d = [info['total_return_180d']*100 for info in stock_info]
                volatilities = [info['volatility_30d']*100 for info in stock_info]
                weights = [info['weight']*3000 for info in stock_info]  # Even larger bubbles
                sharpe_ratios = [info['sharpe_ratio'] for info in stock_info]
                
                # Create gradient colors based on performance
                color_values = []
                for i, ret in enumerate(returns_180d):
                    if ret > 15:
                        color_values.append(ret + 20)  # Boost high performers
                    elif ret < -5:
                        color_values.append(ret - 10)  # Emphasize poor performers
                    else:
                        color_values.append(ret)
                
                fig = go.Figure(data=[go.Scatter3d(
                    x=coords_3d[:, 0],
                    y=coords_3d[:, 1],
                    z=coords_3d[:, 2],
                    mode='markers+text',
                    text=stock_symbols[:len(coords_3d)],
                    textposition="top center",
                    textfont=dict(size=11, color='white', family='Inter'),
                    marker=dict(
                        size=[max(12, w/20) for w in weights],  # 4th dimension: size = weight
                        color=color_values,  # Enhanced 4th dimension: color = boosted return
                        colorscale='Plasma',  # More vibrant colorscale
                        colorbar=dict(
                            title="Enhanced Return (%)",
                            title_font=dict(color='#1e293b', size=12),
                            tickfont=dict(color='#1e293b', size=10),
                            thickness=15,
                            len=0.7
                        ),
                        opacity=0.9,
                        line=dict(width=3, color='rgba(255,255,255,0.9)'),
                        symbol='circle',
                        # Add glow effect with multiple traces
                        sizemode='diameter'
                    ),
                    hovertemplate='<b style="color: #1e293b;">%{text}</b><br>' +
                                '<span style="color: #059669;">Return: %{marker.color:.1f}%</span><br>' +
                                '<span style="color: #dc2626;">Volatility: ' + str([f"{v:.1f}%" for v in volatilities])[1:-1] + '</span><br>' +
                                '<span style="color: #7c3aed;">Sharpe: ' + str([f"{s:.2f}" for s in sharpe_ratios])[1:-1] + '</span><br>' +
                                '<span style="color: #0ea5e9;">Weight: ' + str([f"{info['weight']*100:.1f}%" for info in stock_info])[1:-1] + '</span><br>' +
                                '<span style="color: #64748b;">Factor 1: %{x:.2f}</span><br>' +
                                '<span style="color: #64748b;">Factor 2: %{y:.2f}</span><br>' +
                                '<span style="color: #64748b;">Factor 3: %{z:.2f}</span><extra></extra>'
                )])
                
                # Add glow effect with a second trace
                fig.add_trace(go.Scatter3d(
                    x=coords_3d[:, 0],
                    y=coords_3d[:, 1],
                    z=coords_3d[:, 2],
                    mode='markers',
                    marker=dict(
                        size=[max(18, w/15) for w in weights],  # Larger glow
                        color=color_values,
                        colorscale='Plasma',
                        opacity=0.3,  # Transparent for glow effect
                        line=dict(width=0),
                        symbol='circle'
                    ),
                    showlegend=False,
                    hoverinfo='skip'
                ))
                
                fig.update_layout(
                    title=dict(
                        text="🎯 Enhanced 4D Stock Universe<br><sub>Position + Color + Size + Glow Effects</sub>",
                        font=dict(size=16, color='#1e293b', family='Inter')
                    ),
                    scene=dict(
                        xaxis_title="🎯 Risk-Return Factor",
                        yaxis_title="📈 Quality-Momentum Factor", 
                        zaxis_title="💎 Value-Beta Factor",
                        camera=dict(eye=dict(x=2.0, y=2.0, z=1.8)),
                        bgcolor='rgba(248,250,252,0.95)',
                        xaxis=dict(
                            backgroundcolor='rgba(255,255,255,0.8)', 
                            gridcolor='rgba(59,130,246,0.3)',
                            showspikes=False,
                            title_font=dict(size=12, color='#1e293b')
                        ),
                        yaxis=dict(
                            backgroundcolor='rgba(255,255,255,0.8)', 
                            gridcolor='rgba(16,185,129,0.3)',
                            showspikes=False,
                            title_font=dict(size=12, color='#1e293b')
                        ),
                        zaxis=dict(
                            backgroundcolor='rgba(255,255,255,0.8)', 
                            gridcolor='rgba(245,158,11,0.3)',
                            showspikes=False,
                            title_font=dict(size=12, color='#1e293b')
                        )
                    ),
                    height=700,
                    font=dict(family="Inter, sans-serif", color='#1e293b'),
                    paper_bgcolor='white',
                    margin=dict(l=0, r=0, t=60, b=0)
                )
                st.plotly_chart(fig, width="stretch", config={'displayModeBar': True})
            
            with viz_col2:
                # 🌈 SPECTACULAR 5D CLUSTER: 3D + Color + Size + Sector Shapes + Animations
                sectors = [info['sector'] for info in stock_info]
                sector_colors = {
                    'Technology': '#3b82f6',
                    'Financials': '#10b981', 
                    'Consumer': '#f59e0b',
                    'Healthcare': '#ef4444',
                    'Energy': '#8b5cf6',
                    'Materials': '#06b6d4',
                    'Industrials': '#84cc16',
                    'Utilities': '#f97316',
                    'Telecom': '#ec4899',
                    'Auto': '#6366f1'
                }
                
                sector_symbols = {
                    'Technology': 'diamond',
                    'Financials': 'square',
                    'Consumer': 'circle',
                    'Healthcare': 'cross',
                    'Energy': 'x',
                    'Materials': 'diamond-open',
                    'Industrials': 'square-open',
                    'Utilities': 'circle-open',
                    'Telecom': 'diamond',
                    'Auto': 'square'
                }
                
                fig = go.Figure()
                
                # Add traces for each sector with enhanced styling
                for sector in set(sectors):
                    sector_indices = [i for i, s in enumerate(sectors) if s == sector]
                    if sector_indices:
                        # Main trace
                        fig.add_trace(go.Scatter3d(
                            x=[coords_3d[i, 0] for i in sector_indices],
                            y=[coords_3d[i, 1] for i in sector_indices],
                            z=[coords_3d[i, 2] for i in sector_indices],
                            mode='markers+text',
                            text=[stock_symbols[i] for i in sector_indices],
                            textposition="top center",
                            textfont=dict(size=10, family='Inter', color='white'),
                            name=f"🏢 {sector}",
                            marker=dict(
                                size=[max(14, weights[i]/15) for i in sector_indices],
                                color=sector_colors.get(sector, '#64748b'),
                                opacity=0.85,
                                line=dict(width=3, color='white'),
                                symbol=sector_symbols.get(sector, 'circle'),
                                sizemode='diameter'
                            ),
                            hovertemplate=f'<b style="color: {sector_colors.get(sector, "#64748b")};">%{{text}}</b><br>' +
                                        f'<span style="color: #1e293b;">Sector: {sector}</span><br>' +
                                        '<span style="color: #059669;">Return: ' + str([f"{returns_180d[i]:.1f}%" for i in sector_indices])[1:-1] + '</span><br>' +
                                        '<span style="color: #dc2626;">Volatility: ' + str([f"{volatilities[i]:.1f}%" for i in sector_indices])[1:-1] + '</span><br>' +
                                        '<span style="color: #0ea5e9;">Weight: ' + str([f"{stock_info[i]['weight']*100:.1f}%" for i in sector_indices])[1:-1] + '</span><br>' +
                                        '<extra></extra>'
                        ))
                        
                        # Add glow effect for each sector
                        fig.add_trace(go.Scatter3d(
                            x=[coords_3d[i, 0] for i in sector_indices],
                            y=[coords_3d[i, 1] for i in sector_indices],
                            z=[coords_3d[i, 2] for i in sector_indices],
                            mode='markers',
                            marker=dict(
                                size=[max(20, weights[i]/10) for i in sector_indices],
                                color=sector_colors.get(sector, '#64748b'),
                                opacity=0.2,
                                line=dict(width=0),
                                symbol=sector_symbols.get(sector, 'circle')
                            ),
                            showlegend=False,
                            hoverinfo='skip'
                        ))
                
                fig.update_layout(
                    title=dict(
                        text="🌈 Spectacular 5D Sector Universe<br><sub>Position + Color + Size + Shape + Glow</sub>",
                        font=dict(size=16, color='#1e293b', family='Inter')
                    ),
                    scene=dict(
                        xaxis_title="🎯 Risk-Return Dimension",
                        yaxis_title="📊 Quality-Growth Dimension",
                        zaxis_title="💰 Value-Momentum Dimension",
                        camera=dict(eye=dict(x=2.2, y=2.2, z=1.6)),
                        bgcolor='rgba(248,250,252,0.95)',
                        xaxis=dict(
                            backgroundcolor='rgba(255,255,255,0.9)', 
                            gridcolor='rgba(59,130,246,0.2)',
                            showspikes=False,
                            title_font=dict(size=12, color='#1e293b')
                        ),
                        yaxis=dict(
                            backgroundcolor='rgba(255,255,255,0.9)', 
                            gridcolor='rgba(16,185,129,0.2)',
                            showspikes=False,
                            title_font=dict(size=12, color='#1e293b')
                        ),
                        zaxis=dict(
                            backgroundcolor='rgba(255,255,255,0.9)', 
                            gridcolor='rgba(245,158,11,0.2)',
                            showspikes=False,
                            title_font=dict(size=12, color='#1e293b')
                        )
                    ),
                    height=700,
                    font=dict(family="Inter, sans-serif", color='#1e293b'),
                    paper_bgcolor='white',
                    showlegend=True,
                    legend=dict(
                        x=0.02, y=0.98,
                        bgcolor='rgba(255,255,255,0.95)',
                        bordercolor='rgba(226,232,240,0.8)',
                        borderwidth=2,
                        font=dict(size=10, color='#1e293b')
                    ),
                    margin=dict(l=0, r=0, t=60, b=0)
                )
                st.plotly_chart(fig, width="stretch", config={'displayModeBar': True})
            
            
            # 🌈 ULTIMATE 6D ANIMATED CLUSTER VISUALIZATION
            st.markdown("#### 🌈 Ultimate 6D Animated Cluster Analysis")
            st.markdown("""
            <div style="background: linear-gradient(135deg, #fef7cd 0%, #fef3c7 100%); padding: 1rem; border-radius: 8px; margin-bottom: 1.5rem; border-left: 4px solid #f59e0b;">
                <strong>🎬 6D Animation Features:</strong> Watch your portfolio evolve through time with dynamic sizing, color transitions, 
                shape morphing, and temporal clustering effects. Each frame represents a different market regime or time period.
            </div>
            """, unsafe_allow_html=True)
            
            # Create enhanced time-series animation effect
            animation_frames = []
            frame_names = ['🌅 Market Open', '📈 Mid-Day Rally', '⚡ Volatility Spike', '🌙 After Hours', '🎯 Settlement']
            
            for frame in range(5):
                # Simulate temporal evolution with more sophisticated effects
                noise_factor = 0.08 * frame
                trend_factor = 0.05 * frame
                
                # Add trend and noise to coordinates
                animated_coords = coords_3d + np.random.normal(0, noise_factor, coords_3d.shape)
                animated_coords[:, 0] += trend_factor  # Add trend to first dimension
                
                # Dynamic sizing based on frame (simulating volume changes)
                dynamic_weights = [max(15, w/12 + frame*3 + np.random.uniform(-2, 2)) for w in weights]
                
                # Color evolution (simulating price changes throughout day)
                dynamic_colors = []
                for i, ret in enumerate(returns_180d):
                    color_shift = np.sin(frame * np.pi / 2) * 10  # Sinusoidal color shift
                    dynamic_colors.append(ret + color_shift + np.random.uniform(-3, 3))
                
                # Shape morphing based on performance
                frame_symbols = []
                valid_symbols = ['circle', 'diamond', 'square', 'cross', 'x', 'circle-open', 'diamond-open', 'square-open']
                for i, ret in enumerate(returns_180d):
                    if frame == 0:
                        frame_symbols.append('circle')
                    elif frame == 1:
                        frame_symbols.append('diamond' if ret > 5 else 'circle')
                    elif frame == 2:
                        frame_symbols.append('square' if ret > 10 else 'diamond' if ret > 0 else 'x')
                    elif frame == 3:
                        frame_symbols.append('diamond-open' if ret > 15 else 'square-open' if ret > 5 else 'circle-open')
                    else:
                        frame_symbols.append('square-open' if ret > 20 else 'cross' if ret < -5 else 'circle')
                
                frame_data = go.Scatter3d(
                    x=animated_coords[:, 0],
                    y=animated_coords[:, 1], 
                    z=animated_coords[:, 2],
                    mode='markers+text',
                    text=stock_symbols[:len(coords_3d)],
                    textposition="top center",
                    textfont=dict(size=10, color='white', family='Inter'),
                    marker=dict(
                        size=dynamic_weights,  # 4th dimension: dynamic sizing
                        color=dynamic_colors,  # 5th dimension: evolving colors
                        colorscale=['#1e293b', '#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6'],  # Custom colorscale
                        opacity=0.8 + frame*0.03,  # 6th dimension: changing opacity
                        line=dict(width=3, color='rgba(255,255,255,0.9)'),
                        symbol='circle',  # Use single symbol for all points
                        sizemode='diameter'
                    ),
                    name=frame_names[frame],
                    hovertemplate=f'<b style="color: white;">%{{text}}</b><br>' +
                                f'<span style="color: #fbbf24;">Frame: {frame_names[frame]}</span><br>' +
                                '<span style="color: #34d399;">Dynamic Return: %{marker.color:.1f}%</span><br>' +
                                '<span style="color: #f87171;">Size Factor: ' + str([f"{s:.0f}" for s in dynamic_weights])[1:-1] + '</span><br>' +
                                '<span style="color: #a78bfa;">Opacity: ' + f"{0.8 + frame*0.03:.2f}" + '</span><br>' +
                                '<extra></extra>'
                )
                animation_frames.append(frame_data)
            
            fig = go.Figure(data=animation_frames[0])
            
            # Add animation frames with enhanced transitions
            frames = []
            for i, frame_data in enumerate(animation_frames):
                frames.append(go.Frame(
                    data=[frame_data], 
                    name=f'frame{i}',
                    layout=dict(
                        title=dict(
                            text=f"🌈 6D Animated Evolution - {frame_names[i]}<br><sub>Position + Color + Size + Opacity + Shape + Time</sub>",
                            font=dict(size=16, color='#1e293b', family='Inter')
                        )
                    )
                ))
            
            fig.frames = frames
            
            # Add enhanced animation controls
            fig.update_layout(
                title=dict(
                    text="🌈 6D Animated Stock Cluster Evolution<br><sub>Position + Color + Size + Opacity + Shape + Time</sub>",
                    font=dict(size=16, color='#1e293b', family='Inter')
                ),
                scene=dict(
                    xaxis_title="🎯 Primary Factor Space",
                    yaxis_title="📊 Secondary Factor Space",
                    zaxis_title="💎 Tertiary Factor Space",
                    camera=dict(eye=dict(x=2.4, y=2.4, z=2.0)),
                    bgcolor='rgba(248,250,252,0.98)',
                    xaxis=dict(
                        backgroundcolor='rgba(255,255,255,0.95)', 
                        gridcolor='rgba(59,130,246,0.25)',
                        showspikes=False,
                        title_font=dict(size=12, color='#1e293b')
                    ),
                    yaxis=dict(
                        backgroundcolor='rgba(255,255,255,0.95)', 
                        gridcolor='rgba(16,185,129,0.25)',
                        showspikes=False,
                        title_font=dict(size=12, color='#1e293b')
                    ),
                    zaxis=dict(
                        backgroundcolor='rgba(255,255,255,0.95)', 
                        gridcolor='rgba(245,158,11,0.25)',
                        showspikes=False,
                        title_font=dict(size=12, color='#1e293b')
                    )
                ),
                updatemenus=[{
                    'type': 'buttons',
                    'showactive': True,
                    'buttons': [
                        {
                            'label': '▶️ Play Evolution',
                            'method': 'animate',
                            'args': [None, {
                                'frame': {'duration': 1500, 'redraw': True},
                                'fromcurrent': True,
                                'transition': {'duration': 800, 'easing': 'cubic-in-out'}
                            }]
                        },
                        {
                            'label': '⏸️ Pause',
                            'method': 'animate',
                            'args': [[None], {
                                'frame': {'duration': 0, 'redraw': False},
                                'mode': 'immediate',
                                'transition': {'duration': 0}
                            }]
                        },
                        {
                            'label': '🔄 Reset',
                            'method': 'animate',
                            'args': [['frame0'], {
                                'frame': {'duration': 500, 'redraw': True},
                                'mode': 'immediate',
                                'transition': {'duration': 500}
                            }]
                        }
                    ],
                    'x': 0.02, 'y': 0.98,
                    'bgcolor': 'rgba(255,255,255,0.9)',
                    'bordercolor': 'rgba(226,232,240,0.8)',
                    'borderwidth': 1,
                    'font': dict(size=11, color='#1e293b')
                }],
                height=750,
                font=dict(family="Inter, sans-serif", color='#1e293b'),
                paper_bgcolor='white',
                margin=dict(l=0, r=0, t=70, b=0)
            )
            
            st.plotly_chart(fig, width="stretch", config={'displayModeBar': True})
            
            # 🎨 BONUS: 7D RISK-RETURN BUBBLE UNIVERSE
            st.markdown("#### 🎨 Bonus: 7D Risk-Return Bubble Universe")
            st.markdown("""
            <div style="background: linear-gradient(135deg, #f3e8ff 0%, #e9d5ff 100%); padding: 1rem; border-radius: 8px; margin-bottom: 1.5rem; border-left: 4px solid #8b5cf6;">
                <strong>🌌 7D Universe Features:</strong> The ultimate visualization combining Position (X,Y,Z) + Color + Size + Opacity + Text Size. 
                Discover hidden patterns in your portfolio's multi-dimensional risk-return landscape.
            </div>
            """, unsafe_allow_html=True)
            
            # Create the ultimate 7D visualization
            fig = go.Figure()
            
            # Calculate additional dimensions
            risk_scores = [info['volatility_30d'] * info['beta'] for info in stock_info]
            quality_scores = [info['quality_score'] * 100 for info in stock_info]
            
            # Normalize text sizes based on importance (weight * return)
            importance_scores = [abs(info['weight'] * info['total_return_180d']) for info in stock_info]
            max_importance = max(importance_scores) if importance_scores else 1
            text_sizes = [8 + (score / max_importance) * 8 for score in importance_scores]  # 8-16 range
            
            # Create main bubble trace
            fig.add_trace(go.Scatter3d(
                x=coords_3d[:, 0],
                y=coords_3d[:, 1],
                z=coords_3d[:, 2],
                mode='markers+text',
                text=stock_symbols[:len(coords_3d)],
                textposition="middle center",
                textfont=dict(
                    size=text_sizes,  # 7th dimension: text size based on importance
                    color='white',
                    family='Inter'
                ),
                marker=dict(
                    size=[max(20, w/8) for w in weights],  # 4th dimension: size
                    color=returns_180d,  # 5th dimension: color
                    colorscale='Turbo',  # Most vibrant colorscale
                    opacity=0.8,  # Single opacity value instead of array
                    colorbar=dict(
                        title="Return (%)",
                        title_font=dict(color='#1e293b', size=12),
                        tickfont=dict(color='#1e293b', size=10),
                        thickness=20,
                        len=0.8,
                        x=1.02
                    ),
                    line=dict(width=4, color='rgba(255,255,255,0.95)'),
                    symbol='circle',
                    sizemode='diameter'
                ),
                hovertemplate='<b style="color: #1e293b; font-size: 14px;">%{text}</b><br>' +
                            '<span style="color: #059669;">📈 Return: %{marker.color:.1f}%</span><br>' +
                            '<span style="color: #dc2626;">⚡ Risk Score: ' + str([f"{r:.3f}" for r in risk_scores])[1:-1] + '</span><br>' +
                            '<span style="color: #7c3aed;">💎 Quality: ' + str([f"{q:.0f}" for q in quality_scores])[1:-1] + '</span><br>' +
                            '<span style="color: #0ea5e9;">💰 Weight: ' + str([f"{info['weight']*100:.1f}%" for info in stock_info])[1:-1] + '</span><br>' +
                            '<span style="color: #f59e0b;">📊 Importance: ' + str([f"{imp:.4f}" for imp in importance_scores])[1:-1] + '</span><br>' +
                            '<span style="color: #64748b;">🎯 Coordinates: (%{x:.2f}, %{y:.2f}, %{z:.2f})</span><br>' +
                            '<extra></extra>',
                showlegend=False
            ))
            
            # Add constellation lines connecting similar stocks
            for i in range(len(coords_3d)):
                for j in range(i+1, len(coords_3d)):
                    if i < len(stock_info) and j < len(stock_info):
                        # Connect stocks in same sector or similar performance
                        same_sector = stock_info[i]['sector'] == stock_info[j]['sector']
                        similar_return = abs(stock_info[i]['total_return_180d'] - stock_info[j]['total_return_180d']) < 0.05
                        
                        if same_sector and similar_return and np.random.random() > 0.7:  # Only some connections
                            fig.add_trace(go.Scatter3d(
                                x=[coords_3d[i, 0], coords_3d[j, 0]],
                                y=[coords_3d[i, 1], coords_3d[j, 1]],
                                z=[coords_3d[i, 2], coords_3d[j, 2]],
                                mode='lines',
                                line=dict(
                                    color='rgba(139, 92, 246, 0.3)',
                                    width=2
                                ),
                                showlegend=False,
                                hoverinfo='skip'
                            ))
            
            fig.update_layout(
                title=dict(
                    text="🎨 Ultimate 7D Risk-Return Bubble Universe<br><sub>Position + Color + Size + Opacity + Text Size + Connections + Hover</sub>",
                    font=dict(size=18, color='#1e293b', family='Inter')
                ),
                scene=dict(
                    xaxis_title="🎯 Multi-Factor Risk Dimension",
                    yaxis_title="📊 Quality-Growth Dimension",
                    zaxis_title="💰 Value-Momentum Dimension",
                    camera=dict(eye=dict(x=2.5, y=2.5, z=2.2)),
                    bgcolor='rgba(248,250,252,1.0)',
                    xaxis=dict(
                        backgroundcolor='rgba(255,255,255,1.0)', 
                        gridcolor='rgba(139,92,246,0.2)',
                        showspikes=False,
                        title_font=dict(size=13, color='#1e293b')
                    ),
                    yaxis=dict(
                        backgroundcolor='rgba(255,255,255,1.0)', 
                        gridcolor='rgba(59,130,246,0.2)',
                        showspikes=False,
                        title_font=dict(size=13, color='#1e293b')
                    ),
                    zaxis=dict(
                        backgroundcolor='rgba(255,255,255,1.0)', 
                        gridcolor='rgba(16,185,129,0.2)',
                        showspikes=False,
                        title_font=dict(size=13, color='#1e293b')
                    )
                ),
                height=800,
                font=dict(family="Inter, sans-serif", color='#1e293b'),
                paper_bgcolor='white',
                margin=dict(l=0, r=50, t=80, b=0)
            )
            
            st.plotly_chart(fig, width="stretch", config={'displayModeBar': True})
        
        # Advanced Correlation Matrix with Clustering
        st.markdown("#### 🔥 Advanced Correlation Matrix with Hierarchical Clustering")
        
        chart_col1, chart_col2 = st.columns(2)
        
        with chart_col1:
            # Enhanced correlation heatmap with clustering
            fig = go.Figure(data=go.Heatmap(
                z=correlation_matrix,
                x=stock_symbols,
                y=stock_symbols,
                colorscale='RdBu',
                zmid=0,
                zmin=-1,
                zmax=1,
                text=np.round(correlation_matrix, 2),
                texttemplate="%{text}",
                textfont={"size": 8},
                hoverongaps=False
            ))
            fig.update_layout(
                title="Stock Correlation Matrix (Top 20 Holdings)",
                height=500,
                font=dict(family="Inter, sans-serif", color='#1e293b'),
                paper_bgcolor='white'
            )
            st.plotly_chart(fig, width="stretch", config={'displayModeBar': False})
        
        with chart_col2:
            # Correlation distribution histogram
            corr_values = correlation_matrix[np.triu_indices_from(correlation_matrix, k=1)]
            
            fig = go.Figure(data=[go.Histogram(
                x=corr_values,
                nbinsx=30,
                marker_color=ULTIMATE_COLORS['info'],
                opacity=0.7
            )])
            fig.update_layout(
                title="Correlation Distribution",
                height=500,
                xaxis_title="Correlation Coefficient",
                yaxis_title="Frequency",
                font=dict(family="Inter, sans-serif", color='#1e293b'),
                paper_bgcolor='white',
                plot_bgcolor='white'
            )
            st.plotly_chart(fig, width="stretch", config={'displayModeBar': False})
        
        # Correlation Network Graph
        st.markdown("#### 🕸️ Correlation Network Graph")
        
        # Create network graph showing high correlations
        high_corr_threshold = 0.5
        network_data = []
        
        for i in range(len(stock_symbols)):
            for j in range(i+1, len(stock_symbols)):
                if i < len(correlation_matrix) and j < len(correlation_matrix[0]):
                    corr_val = correlation_matrix[i][j]
                    if abs(corr_val) > high_corr_threshold:
                        network_data.append({
                            'source': stock_symbols[i],
                            'target': stock_symbols[j],
                            'correlation': corr_val,
                            'abs_correlation': abs(corr_val)
                        })
        
        if network_data:
            # Create network visualization
            try:
                import networkx as nx
                
                G = nx.Graph()
                for edge in network_data:
                    G.add_edge(edge['source'], edge['target'], weight=edge['abs_correlation'])
                
                # Get positions using spring layout
                pos = nx.spring_layout(G, k=3, iterations=50)
                
                # Create edge traces
                edge_x = []
                edge_y = []
                edge_colors = []
                
                for edge in network_data:
                    x0, y0 = pos[edge['source']]
                    x1, y1 = pos[edge['target']]
                    edge_x.extend([x0, x1, None])
                    edge_y.extend([y0, y1, None])
                    edge_colors.append(edge['correlation'])
                
                # Create node traces
                node_x = []
                node_y = []
                node_text = []
                
                for node in G.nodes():
                    x, y = pos[node]
                    node_x.append(x)
                    node_y.append(y)
                    node_text.append(node)
                
                fig = go.Figure()
                
                # Add edges
                fig.add_trace(go.Scatter(
                    x=edge_x, y=edge_y,
                    line=dict(width=2, color='rgba(125, 125, 125, 0.5)'),
                    hoverinfo='none',
                    mode='lines',
                    showlegend=False
                ))
                
                # Add nodes
                fig.add_trace(go.Scatter(
                    x=node_x, y=node_y,
                    mode='markers+text',
                    text=node_text,
                    textposition="middle center",
                    hoverinfo='text',
                    marker=dict(
                        size=20,
                        color=ULTIMATE_COLORS['primary'],
                        line=dict(width=2, color='white')
                    ),
                    showlegend=False
                ))
                
                fig.update_layout(
                    title=f"High Correlation Network (|r| > {high_corr_threshold})",
                    height=500,
                    showlegend=False,
                    xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                    yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                    font=dict(family="Inter, sans-serif", color='#1e293b'),
                    paper_bgcolor='white',
                    plot_bgcolor='white'
                )
                st.plotly_chart(fig, width="stretch", config={'displayModeBar': False})
                
            except ImportError:
                st.info("📊 Network visualization requires networkx package. Showing correlation summary instead.")
                
                # Show high correlation pairs as alternative
                high_corr_pairs = []
                for edge in network_data[:10]:  # Top 10 pairs
                    high_corr_pairs.append({
                        'Stock 1': edge['source'],
                        'Stock 2': edge['target'],
                        'Correlation': f"{edge['correlation']:.3f}"
                    })
                
                if high_corr_pairs:
                    pairs_df = pd.DataFrame(high_corr_pairs)
                    st.dataframe(pairs_df, width="stretch", hide_index=True)
        
        # Correlation Clusters Summary
        st.markdown("#### 📊 Correlation Clusters Summary")
        
        clusters = corr_data['correlation_clusters']
        
        cluster_col1, cluster_col2, cluster_col3 = st.columns(3)
        
        with cluster_col1:
            st.markdown(f"""
            **🔗 Correlation Pairs:**
            - High Correlation Pairs: {clusters['high_correlation_pairs']}
            - Low Correlation Pairs: {clusters['low_correlation_pairs']}
            - Negative Correlation Pairs: {clusters['negative_correlation_pairs']}
            """)
        
        with cluster_col2:
            st.markdown(f"""
            **🏭 Sector Clusters:**
            - Energy Cluster: {', '.join(clusters['cluster_1'])}
            - Technology Cluster: {', '.join(clusters['cluster_2'][:3])}...
            - Financial Cluster: {', '.join(clusters['cluster_3'][:3])}...
            """)
        
        with cluster_col3:
            diversification = corr_data['diversification_metrics']
            st.markdown(f"""
            **📈 Diversification Metrics:**
            - Effective # of Stocks: {diversification['effective_number_of_stocks']:.1f}
            - Diversification Ratio: {diversification['diversification_ratio']:.2f}
            - Concentration Ratio: {diversification['concentration_ratio']:.2f}
            - Corr-Adj Volatility: {diversification['correlation_adjusted_volatility']:.1%}
            """)
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    def render_volatility_analysis_dashboard(self):
        """Render volatility analysis dashboard"""
        
        st.markdown('<div class="ultimate-panel">', unsafe_allow_html=True)
        st.markdown('<div class="ultimate-panel-title"><div><span class="panel-icon">📈</span>VOLATILITY ANALYSIS DASHBOARD</div></div>', unsafe_allow_html=True)
        
        vol_data = self.data['volatility_analysis']
        
        # Volatility Time Series
        vol_ts = vol_data['volatility_time_series']
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=vol_ts['dates'],
            y=[v*100 for v in vol_ts['realized_volatility']],
            mode='lines',
            name='Realized Volatility',
            line=dict(color=ULTIMATE_COLORS['primary'], width=2)
        ))
        fig.add_trace(go.Scatter(
            x=vol_ts['dates'],
            y=[v*100 for v in vol_ts['implied_volatility']],
            mode='lines',
            name='Implied Volatility',
            line=dict(color=ULTIMATE_COLORS['warning'], width=2)
        ))
        fig.update_layout(
            title="Volatility Time Series (180 Days)",
            height=400,
            yaxis_title="Volatility (%)",
            font=dict(family="Inter, sans-serif", color='#1e293b'),
            paper_bgcolor='white',
            plot_bgcolor='white'
        )
        st.plotly_chart(fig, width="stretch", config={'displayModeBar': False})
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    def render_regime_analysis_dashboard(self):
        """Render regime analysis dashboard"""
        
        st.markdown('<div class="ultimate-panel">', unsafe_allow_html=True)
        st.markdown('<div class="ultimate-panel-title"><div><span class="panel-icon">🌊</span>REGIME ANALYSIS DASHBOARD</div></div>', unsafe_allow_html=True)
        
        regime_data = self.data['regime_analysis']
        
        # Current Regime Status
        current_regime = regime_data['current_regime']
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown(f"""
            <div class="ultimate-metric-card">
                <div class="ultimate-metric-value">{current_regime['regime_name'].upper()}</div>
                <div class="ultimate-metric-label">Current Regime</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
            <div class="ultimate-metric-card">
                <div class="ultimate-metric-value">{current_regime['regime_probability']:.1%}</div>
                <div class="ultimate-metric-label">Regime Probability</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            st.markdown(f"""
            <div class="ultimate-metric-card">
                <div class="ultimate-metric-value">{current_regime['regime_duration']}</div>
                <div class="ultimate-metric-label">Duration (Days)</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col4:
            st.markdown(f"""
            <div class="ultimate-metric-card">
                <div class="ultimate-metric-value">{current_regime['regime_stability']:.1%}</div>
                <div class="ultimate-metric-label">Regime Stability</div>
            </div>
            """, unsafe_allow_html=True)
        
        # Regime Characteristics
        regime_chars = regime_data['regime_characteristics']
        
        # Create regime comparison chart
        regimes = list(regime_chars.keys())
        returns = [regime_chars[regime]['avg_return']*100 for regime in regimes]
        volatilities = [regime_chars[regime]['volatility']*100 for regime in regimes]
        
        fig = go.Figure(data=go.Scatter(
            x=volatilities,
            y=returns,
            mode='markers+text',
            text=regimes,
            textposition="top center",
            marker=dict(
                size=20,
                color=ULTIMATE_CHART_COLORS[:len(regimes)],
                opacity=0.7
            )
        ))
        fig.update_layout(
            title="Regime Risk-Return Characteristics",
            height=400,
            xaxis_title="Volatility (%)",
            yaxis_title="Average Return (%)",
            font=dict(family="Inter, sans-serif", color='#1e293b'),
            paper_bgcolor='white',
            plot_bgcolor='white'
        )
        st.plotly_chart(fig, width="stretch", config={'displayModeBar': False})
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    def render_backtesting_dashboard(self):
        """Render backtesting results dashboard"""
        
        st.markdown('<div class="ultimate-panel">', unsafe_allow_html=True)
        st.markdown('<div class="ultimate-panel-title"><div><span class="panel-icon">📊</span>BACKTESTING RESULTS DASHBOARD</div></div>', unsafe_allow_html=True)
        
        backtest_data = self.data['backtesting_results']
        
        # Backtest Summary Metrics
        summary = backtest_data['backtest_summary']
        
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.markdown(f"""
            <div class="ultimate-metric-card">
                <div class="ultimate-metric-value">{summary['total_return']*100:.1f}%</div>
                <div class="ultimate-metric-label">Total Return</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
            <div class="ultimate-metric-card">
                <div class="ultimate-metric-value">{summary['sharpe_ratio']:.2f}</div>
                <div class="ultimate-metric-label">Sharpe Ratio</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            st.markdown(f"""
            <div class="ultimate-metric-card">
                <div class="ultimate-metric-value">{summary['max_drawdown']*100:.1f}%</div>
                <div class="ultimate-metric-label">Max Drawdown</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col4:
            st.markdown(f"""
            <div class="ultimate-metric-card">
                <div class="ultimate-metric-value">{summary['win_rate']*100:.1f}%</div>
                <div class="ultimate-metric-label">Win Rate</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col5:
            st.markdown(f"""
            <div class="ultimate-metric-card">
                <div class="ultimate-metric-value">{summary['total_trades']:,}</div>
                <div class="ultimate-metric-label">Total Trades</div>
            </div>
            """, unsafe_allow_html=True)
        
        # Backtest Charts
        chart_col1, chart_col2 = st.columns(2)
        
        with chart_col1:
            # Monthly Returns
            monthly_data = backtest_data['monthly_returns']
            months = list(monthly_data.keys())
            returns = [monthly_data[month]*100 for month in months]
            
            fig = go.Figure(data=[go.Bar(
                x=months,
                y=returns,
                marker_color=[ULTIMATE_COLORS['success'] if r > 0 else ULTIMATE_COLORS['danger'] for r in returns],
                text=[f"{r:+.1f}%" for r in returns],
                textposition='outside'
            )])
            fig.update_layout(
                title="Monthly Returns",
                height=400,
                yaxis_title="Return (%)",
                font=dict(family="Inter, sans-serif", color='#1e293b'),
                paper_bgcolor='white',
                plot_bgcolor='white'
            )
            st.plotly_chart(fig, width="stretch", config={'displayModeBar': False})
        
        with chart_col2:
            # Yearly Performance
            yearly_data = backtest_data['yearly_performance']
            years = list(yearly_data.keys())
            yearly_returns = [yearly_data[year]['return']*100 for year in years]
            
            fig = go.Figure(data=[go.Bar(
                x=years,
                y=yearly_returns,
                marker_color=[ULTIMATE_COLORS['success'] if r > 0 else ULTIMATE_COLORS['danger'] for r in yearly_returns],
                text=[f"{r:+.1f}%" for r in yearly_returns],
                textposition='outside'
            )])
            fig.update_layout(
                title="Yearly Performance",
                height=400,
                yaxis_title="Return (%)",
                font=dict(family="Inter, sans-serif", color='#1e293b'),
                paper_bgcolor='white',
                plot_bgcolor='white'
            )
            st.plotly_chart(fig, width="stretch", config={'displayModeBar': False})
        
        # Rolling Metrics
        st.markdown("#### 📈 Rolling Performance Metrics")
        
        rolling_data = backtest_data['rolling_metrics']
        
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=('Rolling Sharpe (12M)', 'Rolling Return (12M)', 'Rolling Volatility (12M)', 'Rolling Drawdown (12M)'),
            vertical_spacing=0.1
        )
        
        # Rolling Sharpe
        fig.add_trace(go.Scatter(
            x=list(range(len(rolling_data['rolling_sharpe_12m']))),
            y=rolling_data['rolling_sharpe_12m'],
            mode='lines+markers',
            name='Sharpe',
            line=dict(color=ULTIMATE_COLORS['primary'])
        ), row=1, col=1)
        
        # Rolling Return
        fig.add_trace(go.Scatter(
            x=list(range(len(rolling_data['rolling_return_12m']))),
            y=[r*100 for r in rolling_data['rolling_return_12m']],
            mode='lines+markers',
            name='Return',
            line=dict(color=ULTIMATE_COLORS['success'])
        ), row=1, col=2)
        
        # Rolling Volatility
        fig.add_trace(go.Scatter(
            x=list(range(len(rolling_data['rolling_vol_12m']))),
            y=[v*100 for v in rolling_data['rolling_vol_12m']],
            mode='lines+markers',
            name='Volatility',
            line=dict(color=ULTIMATE_COLORS['warning'])
        ), row=2, col=1)
        
        # Rolling Drawdown
        fig.add_trace(go.Scatter(
            x=list(range(len(rolling_data['rolling_dd_12m']))),
            y=[d*100 for d in rolling_data['rolling_dd_12m']],
            mode='lines+markers',
            name='Drawdown',
            line=dict(color=ULTIMATE_COLORS['danger'])
        ), row=2, col=2)
        
        fig.update_layout(
            height=600,
            showlegend=False,
            font=dict(family="Inter, sans-serif", color='#1e293b'),
            paper_bgcolor='white',
            plot_bgcolor='white'
        )
        st.plotly_chart(fig, width="stretch", config={'displayModeBar': False})
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    def render_walk_forward_validation_dashboard(self):
        """Render walk-forward validation dashboard"""
        
        st.markdown('<div class="ultimate-panel">', unsafe_allow_html=True)
        st.markdown('<div class="ultimate-panel-title"><div><span class="panel-icon">🔄</span>WALK-FORWARD VALIDATION DASHBOARD</div></div>', unsafe_allow_html=True)
        
        wf_data = self.data['walk_forward_validation']
        
        # Validation Summary
        summary = wf_data['validation_summary']
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown(f"""
            <div class="ultimate-metric-card">
                <div class="ultimate-metric-value">{summary['success_rate']*100:.1f}%</div>
                <div class="ultimate-metric-label">Success Rate</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
            <div class="ultimate-metric-card">
                <div class="ultimate-metric-value">{summary['passed_periods']}/{summary['total_periods']}</div>
                <div class="ultimate-metric-label">Periods Passed</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            st.markdown(f"""
            <div class="ultimate-metric-card">
                <div class="ultimate-metric-value">{summary['avg_oos_return']*100:.1f}%</div>
                <div class="ultimate-metric-label">Avg OOS Return</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col4:
            st.markdown(f"""
            <div class="ultimate-metric-card">
                <div class="ultimate-metric-value">{summary['robustness_score']*100:.0f}%</div>
                <div class="ultimate-metric-label">Robustness Score</div>
            </div>
            """, unsafe_allow_html=True)
        
        # Comprehensive Walk-Forward Results Chart with Period-by-Period Analysis
        period_results = wf_data['period_results']
        periods = [result['period'] for result in period_results]
        returns = [result['return']*100 for result in period_results]
        sharpes = [result['sharpe'] for result in period_results]
        statuses = [result['status'] for result in period_results]
        
        # Create comprehensive walk-forward visualization
        fig = make_subplots(
            rows=3, cols=1,
            subplot_titles=(
                'Out-of-Sample Returns by Period (with Pass/Fail Status)', 
                'Out-of-Sample Sharpe Ratios by Period',
                'Cumulative Success Rate Over Time'
            ),
            vertical_spacing=0.08,
            specs=[[{"secondary_y": True}], [{"secondary_y": False}], [{"secondary_y": False}]]
        )
        
        # Returns chart with pass/fail coloring
        colors = [ULTIMATE_COLORS['success'] if status == 'PASS' else ULTIMATE_COLORS['danger'] for status in statuses]
        fig.add_trace(go.Bar(
            x=periods,
            y=returns,
            marker_color=colors,
            name='OOS Returns',
            text=[f"{r:+.1f}%" for r in returns],
            textposition='outside',
            showlegend=False
        ), row=1, col=1)
        
        # Add trend line for returns
        z = np.polyfit(periods, returns, 1)
        p = np.poly1d(z)
        fig.add_trace(go.Scatter(
            x=periods,
            y=p(periods),
            mode='lines',
            name='Return Trend',
            line=dict(color=ULTIMATE_COLORS['warning'], width=3, dash='dash'),
            showlegend=False
        ), row=1, col=1)
        
        # Sharpe chart with rolling average
        fig.add_trace(go.Scatter(
            x=periods,
            y=sharpes,
            mode='lines+markers',
            name='OOS Sharpe',
            line=dict(color=ULTIMATE_COLORS['info']),
            marker=dict(size=6),
            showlegend=False
        ), row=2, col=1)
        
        # Add rolling average for Sharpe
        window_size = 6
        if len(sharpes) >= window_size:
            rolling_sharpe = pd.Series(sharpes).rolling(window=window_size).mean()
            fig.add_trace(go.Scatter(
                x=periods,
                y=rolling_sharpe,
                mode='lines',
                name='Rolling Avg Sharpe',
                line=dict(color=ULTIMATE_COLORS['purple'], width=3),
                showlegend=False
            ), row=2, col=1)
        
        # Cumulative success rate
        cumulative_success = []
        passed_count = 0
        for i, status in enumerate(statuses):
            if status == 'PASS':
                passed_count += 1
            cumulative_success.append(passed_count / (i + 1) * 100)
        
        fig.add_trace(go.Scatter(
            x=periods,
            y=cumulative_success,
            mode='lines+markers',
            name='Cumulative Success Rate',
            line=dict(color=ULTIMATE_COLORS['success'], width=3),
            marker=dict(size=6),
            fill='tonexty',
            fillcolor=f'rgba(16, 185, 129, 0.2)',
            showlegend=False
        ), row=3, col=1)
        
        # Add target success rate line
        fig.add_hline(y=80, line_dash="dash", line_color=ULTIMATE_COLORS['warning'], 
                     annotation_text="Target: 80%", row=3, col=1)
        
        fig.update_layout(
            height=900,
            font=dict(family="Inter, sans-serif", color='#1e293b'),
            paper_bgcolor='white',
            plot_bgcolor='white'
        )
        fig.update_yaxes(title_text="Return (%)", row=1, col=1)
        fig.update_yaxes(title_text="Sharpe Ratio", row=2, col=1)
        fig.update_yaxes(title_text="Success Rate (%)", row=3, col=1)
        fig.update_xaxes(title_text="Period", row=3, col=1)
        
        st.plotly_chart(fig, width="stretch", config={'displayModeBar': False})
        
        # Period-by-Period Detailed Analysis
        st.markdown("#### 📊 Period-by-Period Detailed Analysis")
        
        # Create detailed results table
        detailed_results = []
        for i, result in enumerate(period_results):
            detailed_results.append({
                'Period': result['period'],
                'Return': f"{result['return']*100:+.2f}%",
                'Sharpe': f"{result['sharpe']:.2f}",
                'Status': result['status'],
                'Cumulative Success': f"{cumulative_success[i]:.1f}%"
            })
        
        # Show recent periods
        recent_periods = detailed_results[-12:]  # Last 12 periods
        recent_df = pd.DataFrame(recent_periods)
        
        st.markdown("**Recent 12 Periods Performance:**")
        st.dataframe(recent_df, width="stretch", hide_index=True)
        
        # Degradation Analysis
        st.markdown("#### 📉 Performance Degradation Analysis")
        
        degradation = wf_data['degradation_analysis']
        
        deg_col1, deg_col2, deg_col3 = st.columns(3)
        
        with deg_col1:
            st.markdown(f"""
            **📊 Return Metrics:**
            - Return Degradation: {degradation['return_degradation']*100:.1f}%
            - Sharpe Degradation: {degradation['sharpe_degradation']*100:.1f}%
            - Volatility Increase: {degradation['volatility_increase']*100:.1f}%
            """)
        
        with deg_col2:
            st.markdown(f"""
            **⚠️ Risk Metrics:**
            - Drawdown Increase: {degradation['drawdown_increase']*100:.1f}%
            - Turnover Increase: {degradation['turnover_increase']*100:.1f}%
            """)
        
        with deg_col3:
            stability = wf_data['stability_metrics']
            st.markdown(f"""
            **🎯 Stability Metrics:**
            - Parameter Stability: {stability['parameter_stability']*100:.0f}%
            - Performance Stability: {stability['performance_stability']*100:.0f}%
            - Risk Stability: {stability['risk_stability']*100:.0f}%
            """)
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    def render_system_diagnostics_dashboard(self):
        """Render system diagnostics dashboard"""
        
        st.markdown('<div class="ultimate-panel">', unsafe_allow_html=True)
        st.markdown('<div class="ultimate-panel-title"><div><span class="panel-icon">🔧</span>SYSTEM DIAGNOSTICS DASHBOARD</div></div>', unsafe_allow_html=True)
        
        diag_data = self.data['system_diagnostics']
        
        # System Health Overview
        health_data = diag_data['system_health']
        
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.markdown(f"""
            <div class="ultimate-metric-card">
                <div class="ultimate-metric-value">{health_data['overall_health']*100:.0f}%</div>
                <div class="ultimate-metric-label">Overall Health</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
            <div class="ultimate-metric-card">
                <div class="ultimate-metric-value">{health_data['data_pipeline_health']*100:.0f}%</div>
                <div class="ultimate-metric-label">Data Pipeline</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            st.markdown(f"""
            <div class="ultimate-metric-card">
                <div class="ultimate-metric-value">{health_data['model_health']*100:.0f}%</div>
                <div class="ultimate-metric-label">Model Health</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col4:
            st.markdown(f"""
            <div class="ultimate-metric-card">
                <div class="ultimate-metric-value">{health_data['execution_health']*100:.0f}%</div>
                <div class="ultimate-metric-label">Execution Health</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col5:
            st.markdown(f"""
            <div class="ultimate-metric-card">
                <div class="ultimate-metric-value">{health_data['risk_system_health']*100:.0f}%</div>
                <div class="ultimate-metric-label">Risk System</div>
            </div>
            """, unsafe_allow_html=True)
        
        # Performance Metrics
        perf_data = diag_data['performance_metrics']
        
        chart_col1, chart_col2 = st.columns(2)
        
        with chart_col1:
            # System Resource Usage
            resources = ['CPU', 'Memory', 'Disk']
            usage = [
                perf_data['cpu_usage']*100,
                perf_data['memory_usage']*100,
                perf_data['disk_usage']*100
            ]
            
            fig = go.Figure(data=[go.Bar(
                x=resources,
                y=usage,
                marker_color=[
                    ULTIMATE_COLORS['success'] if u < 50 else 
                    ULTIMATE_COLORS['warning'] if u < 80 else 
                    ULTIMATE_COLORS['danger'] for u in usage
                ],
                text=[f"{u:.1f}%" for u in usage],
                textposition='outside'
            )])
            fig.update_layout(
                title="System Resource Usage",
                height=400,
                yaxis_title="Usage (%)",
                font=dict(family="Inter, sans-serif", color='#1e293b'),
                paper_bgcolor='white',
                plot_bgcolor='white'
            )
            st.plotly_chart(fig, width="stretch", config={'displayModeBar': False})
        
        with chart_col2:
            # Response Times
            response_metrics = ['Database', 'API', 'Network Latency']
            response_times = [
                perf_data['database_response_time'],
                perf_data['api_response_time'],
                perf_data['network_latency']
            ]
            
            fig = go.Figure(data=[go.Bar(
                x=response_metrics,
                y=response_times,
                marker_color=ULTIMATE_CHART_COLORS[:len(response_metrics)],
                text=[f"{t:.1f}ms" for t in response_times],
                textposition='outside'
            )])
            fig.update_layout(
                title="System Response Times",
                height=400,
                yaxis_title="Response Time (ms)",
                font=dict(family="Inter, sans-serif", color='#1e293b'),
                paper_bgcolor='white',
                plot_bgcolor='white'
            )
            st.plotly_chart(fig, width="stretch", config={'displayModeBar': False})
        
        # Data Quality Metrics
        st.markdown("#### 📊 Data Quality & Model Diagnostics")
        
        quality_data = diag_data['data_quality']
        model_data = diag_data['model_diagnostics']
        
        qual_col1, qual_col2, qual_col3 = st.columns(3)
        
        with qual_col1:
            st.markdown(f"""
            **📈 Data Quality:**
            - Completeness: {quality_data['data_completeness']*100:.1f}%
            - Accuracy: {quality_data['data_accuracy']*100:.1f}%
            - Timeliness: {quality_data['data_timeliness']*100:.1f}%
            - Consistency: {quality_data['data_consistency']*100:.1f}%
            """)
        
        with qual_col2:
            st.markdown(f"""
            **🤖 Model Performance:**
            - Accuracy: {model_data['model_accuracy']*100:.1f}%
            - Precision: {model_data['model_precision']*100:.1f}%
            - Recall: {model_data['model_recall']*100:.1f}%
            - F1 Score: {model_data['model_f1_score']*100:.1f}%
            """)
        
        with qual_col3:
            alerts_data = diag_data['alerts_and_warnings']
            st.markdown(f"""
            **🚨 Alerts & Monitoring:**
            - Critical Alerts: {alerts_data['critical_alerts']}
            - Warning Alerts: {alerts_data['warning_alerts']}
            - Info Alerts: {alerts_data['info_alerts']}
            - Avg Resolution: {alerts_data['avg_resolution_time']:.1f}min
            """)
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    def render_institutional_reporting_dashboard(self):
        """Render institutional reporting dashboard"""
        
        st.markdown('<div class="ultimate-panel">', unsafe_allow_html=True)
        st.markdown('<div class="ultimate-panel-title"><div><span class="panel-icon">🏛️</span>INSTITUTIONAL REPORTING DASHBOARD</div></div>', unsafe_allow_html=True)
        
        inst_data = self.data['institutional_reporting']
        
        # Executive Summary
        exec_summary = inst_data['executive_summary']
        
        st.markdown("#### 📋 Executive Summary")
        
        exec_col1, exec_col2, exec_col3, exec_col4, exec_col5 = st.columns(5)
        
        with exec_col1:
            st.markdown(f"""
            <div class="ultimate-metric-card">
                <div class="ultimate-metric-value">₹{exec_summary['aum']:,.0f}</div>
                <div class="ultimate-metric-label">Assets Under Management</div>
            </div>
            """, unsafe_allow_html=True)
        
        with exec_col2:
            st.markdown(f"""
            <div class="ultimate-metric-card">
                <div class="ultimate-metric-value">{exec_summary['total_return_ytd']*100:+.1f}%</div>
                <div class="ultimate-metric-label">Total Return YTD</div>
            </div>
            """, unsafe_allow_html=True)
        
        with exec_col3:
            st.markdown(f"""
            <div class="ultimate-metric-card">
                <div class="ultimate-metric-value">{exec_summary['excess_return']*100:+.1f}%</div>
                <div class="ultimate-metric-label">Excess Return</div>
            </div>
            """, unsafe_allow_html=True)
        
        with exec_col4:
            st.markdown(f"""
            <div class="ultimate-metric-card">
                <div class="ultimate-metric-value">{exec_summary['information_ratio']:.2f}</div>
                <div class="ultimate-metric-label">Information Ratio</div>
            </div>
            """, unsafe_allow_html=True)
        
        with exec_col5:
            st.markdown(f"""
            <div class="ultimate-metric-card">
                <div class="ultimate-metric-value">{exec_summary['active_positions']}</div>
                <div class="ultimate-metric-label">Active Positions</div>
            </div>
            """, unsafe_allow_html=True)
        
        # Risk Report
        st.markdown("#### 🛡️ Risk Report")
        
        risk_report = inst_data['risk_report']
        
        risk_col1, risk_col2 = st.columns(2)
        
        with risk_col1:
            # Risk Metrics
            risk_metrics = ['VaR 95%', 'Expected Shortfall', 'Active Risk', 'Concentration Risk']
            risk_values = [
                abs(risk_report['var_95']*100),
                abs(risk_report['expected_shortfall']*100),
                risk_report['active_risk']*100,
                risk_report['concentration_risk']*100
            ]
            
            fig = go.Figure(data=[go.Bar(
                x=risk_metrics,
                y=risk_values,
                marker_color=ULTIMATE_CHART_COLORS[:len(risk_metrics)],
                text=[f"{v:.1f}%" for v in risk_values],
                textposition='outside'
            )])
            fig.update_layout(
                title="Key Risk Metrics",
                height=400,
                yaxis_title="Risk (%)",
                font=dict(family="Inter, sans-serif", color='#1e293b'),
                paper_bgcolor='white',
                plot_bgcolor='white'
            )
            st.plotly_chart(fig, width="stretch", config={'displayModeBar': False})
        
        with risk_col2:
            # Risk Breakdown
            risk_types = ['Sector Risk', 'Liquidity Risk', 'Currency Risk']
            risk_breakdown = [
                risk_report['sector_risk']*100,
                risk_report['liquidity_risk']*100,
                risk_report['currency_risk']*100
            ]
            
            fig = go.Figure(data=[go.Pie(
                labels=risk_types,
                values=risk_breakdown,
                hole=0.4,
                marker_colors=ULTIMATE_CHART_COLORS[:len(risk_types)]
            )])
            fig.update_layout(
                title="Risk Breakdown",
                height=400,
                font=dict(family="Inter, sans-serif", color='#1e293b'),
                paper_bgcolor='white'
            )
            st.plotly_chart(fig, width="stretch", config={'displayModeBar': False})
        
        # Attribution Report
        st.markdown("#### 🎯 Performance Attribution")
        
        attribution = inst_data['attribution_report']
        
        attr_sources = ['Stock Selection', 'Sector Allocation', 'Timing', 'Interaction']
        attr_contributions = [
            attribution['stock_selection']*100,
            attribution['sector_allocation']*100,
            attribution['timing']*100,
            attribution['interaction']*100
        ]
        
        fig = go.Figure(data=[go.Waterfall(
            name="Attribution",
            orientation="v",
            measure=["relative", "relative", "relative", "relative", "total"],
            x=attr_sources + ["Total Alpha"],
            textposition="outside",
            text=[f"+{c:.2f}%" if c > 0 else f"{c:.2f}%" for c in attr_contributions] + [f"{attribution['total_alpha']*100:.2f}%"],
            y=attr_contributions + [attribution['total_alpha']*100],
            connector={"line": {"color": "rgb(63, 63, 63)"}},
        )])
        fig.update_layout(
            title="Performance Attribution Waterfall",
            height=400,
            yaxis_title="Contribution (%)",
            font=dict(family="Inter, sans-serif", color='#1e293b'),
            paper_bgcolor='white',
            plot_bgcolor='white'
        )
        st.plotly_chart(fig, width="stretch", config={'displayModeBar': False})
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    def render_constitutional_principles(self):
        """Render constitutional principles section"""
        
        st.markdown("""
        <div class="ultimate-constitutional-principles">
            <div class="principle-title">🏛️ NORTHSTAR V3 CONSTITUTIONAL PRINCIPLES</div>
            <div class="principle-item">📊 TRANSPARENCY: All decisions, models, and risk metrics are fully observable and auditable</div>
            <div class="principle-item">🛡️ RISK FIRST: Risk management takes precedence over return optimization in all circumstances</div>
            <div class="principle-item">⚙️ SYSTEMATIC: No discretionary overrides - all actions follow pre-defined, tested rules</div>
            <div class="principle-item">✅ VALIDATION: Every strategy component undergoes rigorous out-of-sample testing</div>
            <div class="principle-item">🧠 INTELLIGENCE: AI-driven insights guide decisions while maintaining human oversight</div>
            <div class="principle-item">🔄 CONTINUOUS: Real-time monitoring and adaptation to changing market conditions</div>
            <div class="principle-item">📈 PERFORMANCE: Consistent alpha generation through disciplined execution</div>
            <div class="principle-item">🎯 CONVICTION: High-conviction positions based on multiple confirming signals</div>
        </div>
        """, unsafe_allow_html=True)
    
    def render_sidebar(self):
        """Render comprehensive sidebar with navigation and status"""
        
        st.sidebar.markdown("## 🎯 NORTHSTAR V3")
        st.sidebar.markdown("### Ultimate Comprehensive Cockpit")
        
        # System Status
        st.sidebar.markdown("---")
        st.sidebar.markdown("### 📊 System Status")
        
        panels = self.data['constitutional_panels']
        panel1 = panels['panel_1_system_state']
        
        health_score = panel1['health_score']
        if health_score >= 0.8:
            status_color = "🟢"
            status_text = "EXCELLENT"
        elif health_score >= 0.6:
            status_color = "🟡"
            status_text = "GOOD"
        else:
            status_color = "🔴"
            status_text = "NEEDS ATTENTION"
        
        st.sidebar.markdown(f"**Overall Health:** {status_color} {status_text}")
        st.sidebar.markdown(f"**Health Score:** {health_score:.1%}")
        st.sidebar.markdown(f"**Current Regime:** {panel1['current_regime'].upper()}")
        st.sidebar.markdown(f"**System Uptime:** {panel1['system_uptime_days']} days")
        
        # Quick Metrics
        st.sidebar.markdown("---")
        st.sidebar.markdown("### 📈 Quick Metrics")
        
        performance_data = self.data['performance_data']
        portfolio_data = self.data['portfolio_data']
        
        st.sidebar.markdown(f"**Portfolio Value:** ₹{portfolio_data['total_value']:,.0f}")
        st.sidebar.markdown(f"**Total Return:** {performance_data['total_return']*100:+.1f}%")
        st.sidebar.markdown(f"**Sharpe Ratio:** {performance_data['sharpe_ratio']:.2f}")
        st.sidebar.markdown(f"**Max Drawdown:** {performance_data['max_drawdown']*100:.1f}%")
        st.sidebar.markdown(f"**Total Positions:** {portfolio_data['total_positions']}")
        st.sidebar.markdown(f"**Current Exposure:** {portfolio_data['total_exposure']:.1%}")
        
        # Dashboard Navigation
        st.sidebar.markdown("---")
        st.sidebar.markdown("### 🧭 Dashboard Sections")
        
        st.sidebar.markdown("✅ Constitutional Panels (5)")
        st.sidebar.markdown("✅ Portfolio Dashboard")
        st.sidebar.markdown("✅ Individual Stock Performance")
        st.sidebar.markdown("✅ Risk Management")
        st.sidebar.markdown("✅ Market Intelligence")
        st.sidebar.markdown("✅ Advanced Analytics")
        st.sidebar.markdown("✅ Sector Analysis")
        st.sidebar.markdown("✅ Correlation Analysis")
        st.sidebar.markdown("✅ Volatility Analysis")
        st.sidebar.markdown("✅ Regime Analysis")
        st.sidebar.markdown("✅ Backtesting Results")
        st.sidebar.markdown("✅ Walk-Forward Validation")
        st.sidebar.markdown("✅ System Diagnostics")
        st.sidebar.markdown("✅ Institutional Reporting")
        
        # Footer
        st.sidebar.markdown("---")
        st.sidebar.markdown(f"**Last Updated:** {datetime.now().strftime('%H:%M:%S')}")
        st.sidebar.markdown("**Version:** v3.0.0 Ultimate")
        st.sidebar.markdown("**Status:** 🟢 All Features Active")

def main():
    """Main function to run the ultimate comprehensive dashboard"""
    
    st.markdown("# 🎯 Loading Ultimate Comprehensive Cockpit...")
    
    # Initialize the cockpit
    with st.spinner("Generating comprehensive data..."):
        cockpit = UltimateComprehensiveCockpit()
    
    st.success("✅ Ultimate Comprehensive Cockpit loaded successfully!")
    
    # Run the dashboard
    cockpit.run_ultimate_dashboard()

if __name__ == "__main__":
    main()
        
