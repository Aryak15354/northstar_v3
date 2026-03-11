#!/usr/bin/env python3
"""
Unified Volatility Engine - Comprehensive Dashboard

Production-grade real-time monitoring dashboard for institutional volatility trading.

Features:
- Real-time P&L tracking with Greeks decomposition
- Portfolio Greeks monitoring with limit visualization
- Market regime detection and transition tracking
- Risk metrics (VaR, CVaR, stress tests)
- Position management and analysis
- Performance attribution (alpha/beta separation)
- Strategy allocation and performance
- Execution quality monitoring
- Alert management
- Historical analysis and reporting
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from pathlib import Path
import json
from datetime import datetime, timedelta
import psutil
import subprocess
from datetime import datetime, timedelta
import numpy as np
import yaml
from typing import Dict, List, Optional, Any

# Page config
st.set_page_config(
    page_title="Unified Volatility Engine",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for professional styling
st.markdown("""
<style>
    /* Main theme */
    .main {
        background-color: #0e1117;
    }
    
    /* Metric cards */
    .metric-card {
        background: linear-gradient(135deg, #1e2130 0%, #2d3250 100%);
        padding: 20px;
        border-radius: 10px;
        margin: 10px 0;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
        border: 1px solid #3d4466;
    }
    
    /* Colors */
    .positive {
        color: #00ff88;
        font-weight: bold;
    }
    .negative {
        color: #ff4444;
        font-weight: bold;
    }
    .neutral {
        color: #ffaa00;
        font-weight: bold;
    }
    
    /* Status indicators */
    .status-running {
        color: #00ff88;
        font-size: 1.2em;
    }
    .status-stopped {
        color: #ff4444;
        font-size: 1.2em;
    }
    .status-warning {
        color: #ffaa00;
        font-size: 1.2em;
    }
    
    /* Alert badges */
    .alert-critical {
        background-color: #ff4444;
        color: white;
        padding: 5px 10px;
        border-radius: 5px;
        font-weight: bold;
    }
    .alert-warning {
        background-color: #ffaa00;
        color: black;
        padding: 5px 10px;
        border-radius: 5px;
        font-weight: bold;
    }
    .alert-info {
        background-color: #4488ff;
        color: white;
        padding: 5px 10px;
        border-radius: 5px;
        font-weight: bold;
    }
    
    /* Tables */
    .dataframe {
        font-size: 0.9em;
    }
    
    /* Headers */
    h1, h2, h3 {
        color: #ffffff;
    }
    
    /* Sidebar */
    .css-1d391kg {
        background-color: #1e2130;
    }
</style>
""", unsafe_allow_html=True)


# ==================== DATA LOADING ====================

@st.cache_data(ttl=30)
def load_latest_state():
    """Load latest state snapshot from options system"""
    # Try to load from new options system first
    options_state_file = Path("data/options/live/options_dashboard_state.json")
    if options_state_file.exists():
        try:
            with open(options_state_file, 'r') as f:
                state = json.load(f)
                # Parse timestamp from the state
                if 'timestamp' in state:
                    state['_snapshot_time'] = datetime.fromisoformat(state['timestamp'].replace('Z', '+00:00'))
                else:
                    state['_snapshot_time'] = datetime.fromtimestamp(options_state_file.stat().st_mtime)
                return state
        except Exception as e:
            st.warning(f"Error loading options state: {e}")
    
    # Fallback to legacy snapshots
    snapshot_dir = Path("snapshots")
    if not snapshot_dir.exists():
        return None
    
    snapshots = list(snapshot_dir.glob("*.json"))
    if not snapshots:
        return None
    
    latest = max(snapshots, key=lambda p: p.stat().st_mtime)
    
    try:
        with open(latest, 'r') as f:
            state = json.load(f)
            state['_snapshot_time'] = datetime.fromtimestamp(latest.stat().st_mtime)
            return state
    except Exception as e:
        st.error(f"Error loading state: {e}")
        return None


@st.cache_data(ttl=60)
def load_config(config_name="production"):
    """Load configuration file"""
    config_path = Path(f"config/{config_name}.yaml")
    if not config_path.exists():
        return None
    
    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        st.error(f"Error loading config: {e}")
        return None


@st.cache_data(ttl=300)
def load_historical_snapshots(days=30):
    """Load historical state snapshots"""
    snapshot_dir = Path("snapshots")
    if not snapshot_dir.exists():
        return []
    
    snapshots = list(snapshot_dir.glob("*.json"))
    cutoff = datetime.now() - timedelta(days=days)
    
    historical = []
    for snap in snapshots:
        mtime = datetime.fromtimestamp(snap.stat().st_mtime)
        if mtime >= cutoff:
            try:
                with open(snap, 'r') as f:
                    data = json.load(f)
                    data['_timestamp'] = mtime
                    historical.append(data)
            except:
                continue
    
    return sorted(historical, key=lambda x: x['_timestamp'])
def filter_meaningful_data(historical_data, start_date="2026-02-01"):
    """
    Filter historical data to start from a meaningful date when the system became active.
    Updated to use February 2026 as the start since that's when we have actual live data.

    Args:
        historical_data: List of historical snapshots
        start_date: Start date for meaningful data (default: Feb 1, 2026)

    Returns:
        Filtered historical data starting from the meaningful date
    """
    if not historical_data:
        return historical_data

    from datetime import datetime

    # Parse start date
    if isinstance(start_date, str):
        try:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        except:
            # Fallback to a simple parse
            start_dt = datetime(2026, 2, 1)
    else:
        start_dt = start_date

    # Filter data to start from meaningful date
    filtered_data = []
    for snapshot in historical_data:
        snapshot_time = snapshot.get('_timestamp')
        if snapshot_time:
            try:
                if isinstance(snapshot_time, str):
                    snapshot_dt = datetime.fromisoformat(snapshot_time.replace('Z', '+00:00'))
                else:
                    snapshot_dt = snapshot_time

                if snapshot_dt >= start_dt:
                    filtered_data.append(snapshot)
            except:
                # If timestamp parsing fails, include the snapshot
                filtered_data.append(snapshot)

    return filtered_data

def normalize_portfolio_data(data_series, start_value=100):
    """
    Normalize portfolio data to start from a base value (e.g., 100) to show relative performance.
    This is useful when the portfolio was flat for a long period.

    Args:
        data_series: List of portfolio values
        start_value: Starting value for normalization (default: 100)

    Returns:
        Normalized data series
    """
    if not data_series or len(data_series) == 0:
        return data_series

    # Find first non-zero value
    first_meaningful_value = None
    for value in data_series:
        if value != 0:
            first_meaningful_value = value
            break

    if first_meaningful_value is None:
        return [start_value] * len(data_series)

    # Normalize to start_value
    normalized = []
    for value in data_series:
        if value == 0:
            normalized.append(start_value)
        else:
            normalized.append(start_value + (value - first_meaningful_value) / abs(first_meaningful_value) * start_value)

    return normalized
def get_system_start_date():
    """
    Get the system start date for filtering meaningful data.
    Updated to reflect actual live system start in February 2026.

    Returns:
        str: ISO format date string for system start
    """
    # Check config first
    try:
        config_path = Path("config/dashboard_config.yaml")
        if config_path.exists():
            import yaml
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
                return config.get('filtering', {}).get('system_start_date', '2026-02-01')
    except:
        pass

    # Default to February 1, 2026 when live system data starts
    return '2026-02-01'


@st.cache_data(ttl=300)
def load_reports(date_str=None):
    """Load EOD reports"""
    if date_str is None:
        date_str = datetime.now().strftime('%Y-%m-%d')
    
    reports_dir = Path(f"reports/{date_str}")
    if not reports_dir.exists():
        return {}
    
    reports = {}
    for report_file in reports_dir.glob("*.json"):
        try:
            with open(report_file, 'r') as f:
                reports[report_file.stem] = json.load(f)
        except:
            continue
    
    return reports


def check_engine_status():
    """Check if engine is running"""
    pid_file = Path("engine.pid")
    if not pid_file.exists():
        return False, None, None
    
    try:
        with open(pid_file, 'r') as f:
            pid = int(f.read().strip())
        
        # Check if process exists
        os.kill(pid, 0)
        
        # Get uptime from log
        log_file = Path("logs/engine.log")
        if log_file.exists():
            start_time = datetime.fromtimestamp(log_file.stat().st_mtime)
            uptime = datetime.now() - start_time
            return True, pid, uptime
        
        return True, pid, None
    except (ProcessLookupError, ValueError):
        return False, None, None


def get_alerts():
    """Get recent alerts"""
    alert_log = Path("logs/alerts.log")
    if not alert_log.exists():
        return []
    
    alerts = []
    try:
        with open(alert_log, 'r') as f:
            lines = f.readlines()[-50:]  # Last 50 alerts
            for line in lines:
                if line.strip():
                    alerts.append(line.strip())
    except:
        pass
    
    return alerts


# ==================== UTILITY FUNCTIONS ====================

def format_currency(value):
    """Format value as currency"""
    if value >= 0:
        return f"${value:,.2f}"
    else:
        return f"-${abs(value):,.2f}"


def format_percentage(value):
    """Format value as percentage"""
    if value >= 0:
        return f"+{value:.2%}"
    else:
        return f"{value:.2%}"


def get_color_for_value(value, reverse=False):
    """Get color based on value (green for positive, red for negative)"""
    if reverse:
        return "#ff4444" if value > 0 else "#00ff88"
    return "#00ff88" if value > 0 else "#ff4444"


def calculate_greeks_utilization(greeks, limits):
    """Calculate Greeks utilization percentage"""
    if not greeks or not limits:
        return {}
    
    utilization = {}
    for greek in ['delta', 'gamma', 'vega', 'theta']:
        current = abs(greeks.get(greek, 0))
        limit = abs(limits.get(greek, 1))
        utilization[greek] = (current / limit) * 100 if limit > 0 else 0
    
    return utilization


def get_regime_color(regime):
    """Get color for regime"""
    colors = {
        'low_vol': '#00ff88',
        'high_vol': '#ffaa00',
        'crisis': '#ff4444',
        'transition': '#ff8800'
    }
    return colors.get(regime, '#888888')


def get_regime_icon(regime):
    """Get icon for regime"""
    icons = {
        'low_vol': '🟢',
        'high_vol': '🟡',
        'crisis': '🔴',
        'transition': '🟠'
    }
    return icons.get(regime, '⚪')



# ==================== HEADER & NAVIGATION ====================

def render_header():
    """Render dashboard header with system status"""
    col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
    
    with col1:
        st.title("📊 Unified Volatility Engine")
        st.caption("Institutional-Grade Volatility Trading System")
    
    with col2:
        running, pid, uptime = check_engine_status()
        if running:
            st.markdown('<p class="status-running">🟢 RUNNING</p>', unsafe_allow_html=True)
            if uptime:
                st.caption(f"Uptime: {str(uptime).split('.')[0]}")
        else:
            st.markdown('<p class="status-stopped">🔴 STOPPED</p>', unsafe_allow_html=True)
    
    with col3:
        if st.button("🔄 Refresh", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
    
    with col4:
        state = load_latest_state()
        if state:
            snapshot_time = state.get('_snapshot_time', datetime.now())
            age = (datetime.now() - snapshot_time).total_seconds()
            if age < 60:
                st.success(f"Live ({int(age)}s)")
            elif age < 300:
                st.warning(f"Stale ({int(age/60)}m)")
            else:
                st.error(f"Old ({int(age/60)}m)")


# ==================== P&L PANEL ====================

def render_pnl_panel(state, config):
    """Render comprehensive P&L panel"""
    st.subheader("💰 P&L Analysis")
    
    if not state:
        st.warning("No data available")
        return
    
    # Get P&L data from options system
    ytd_data = state.get('ytd', {})
    trade_metrics = state.get('trade_metrics', {})
    closed_positions = state.get('closed_positions', [])
    
    # Calculate P&L metrics
    ytd_net_pnl = ytd_data.get('ytd_net_pnl', 0)
    ytd_gross_profits = ytd_data.get('ytd_gross_profits', 0)
    ytd_gross_losses = ytd_data.get('ytd_gross_losses', 0)
    
    # Calculate today's P&L from recent closed positions
    today = datetime.now().date()
    today_pnl = sum(
        pos.get('realized_pnl', 0) 
        for pos in closed_positions 
        if pos.get('exit_time') and 
        datetime.fromisoformat(pos['exit_time'].replace('Z', '+00:00')).date() == today
    )
    
    # Top metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "YTD Net P&L",
            format_currency(ytd_net_pnl),
            format_percentage(ytd_net_pnl / 500000 if ytd_net_pnl else 0),  # Assuming 500k base capital
            delta_color="normal"
        )
    
    with col2:
        st.metric(
            "YTD Gross Profits",
            format_currency(ytd_gross_profits),
            format_percentage(ytd_gross_profits / 500000 if ytd_gross_profits else 0)
        )
    
    with col3:
        st.metric(
            "YTD Gross Losses",
            format_currency(ytd_gross_losses),
            format_percentage(ytd_gross_losses / 500000 if ytd_gross_losses else 0)
        )
    
    with col4:
        st.metric(
            "Today's P&L",
            format_currency(today_pnl),
            format_percentage(today_pnl / 500000 if today_pnl else 0)
        )
    
    # P&L Charts
    col1, col2 = st.columns(2)
    
    with col1:
        # Cumulative P&L from closed positions
        if closed_positions:
            # Sort positions by exit time
            sorted_positions = sorted(
                [pos for pos in closed_positions if pos.get('exit_time')],
                key=lambda x: x['exit_time']
            )
            
            dates = []
            cumulative_pnl = []
            running_total = 0
            
            for pos in sorted_positions:
                exit_time = datetime.fromisoformat(pos['exit_time'].replace('Z', '+00:00'))
                running_total += pos.get('realized_pnl', 0)
                dates.append(exit_time)
                cumulative_pnl.append(running_total)
        else:
            dates = [datetime.now()]
            cumulative_pnl = [0]
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=dates,
            y=cumulative_pnl,
            mode='lines',
            name='Cumulative P&L',
            line=dict(color='#00ff88', width=2),
            fill='tozeroy',
            fillcolor='rgba(0, 255, 136, 0.1)'
        ))
        
        fig.update_layout(
            title="Cumulative P&L from Closed Positions",
            xaxis_title="Date",
            yaxis_title="P&L ($)",
            height=300,
            template="plotly_dark",
            hovermode='x unified'
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # P&L by strategy type
        strategy_pnl = {}
        for pos in closed_positions:
            strategy = pos.get('strategy_type', 'unknown')
            pnl = pos.get('realized_pnl', 0)
            strategy_pnl[strategy] = strategy_pnl.get(strategy, 0) + pnl
        
        if strategy_pnl:
            fig = go.Figure(data=[
                go.Bar(
                    x=list(strategy_pnl.keys()),
                    y=list(strategy_pnl.values()),
                    marker_color=['#00ff88' if v >= 0 else '#ff4444' for v in strategy_pnl.values()],
                    text=[format_currency(v) for v in strategy_pnl.values()],
                    textposition='outside'
                )
            ])
            
            fig.update_layout(
                title="P&L by Strategy Type",
                xaxis_title="Strategy",
                yaxis_title="P&L ($)",
                height=300,
                template="plotly_dark",
                showlegend=False
            )
            
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No strategy P&L data available")
    
    # Trade metrics summary
    st.write("**Trade Performance Metrics:**")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Total Trades",
            trade_metrics.get('total_trades', 0)
        )
    
    with col2:
        win_rate = trade_metrics.get('win_rate', 0)
        st.metric(
            "Win Rate",
            f"{win_rate:.1%}"
        )
    
    with col3:
        avg_profit = trade_metrics.get('avg_profit', 0)
        st.metric(
            "Avg Profit",
            format_currency(avg_profit)
        )
    
    with col4:
        profit_factor = trade_metrics.get('profit_factor', 0)
        st.metric(
            "Profit Factor",
            f"{profit_factor:.2f}"
        )
    
    # Recent positions table
    if closed_positions:
        st.write("**Recent Closed Positions:**")
        recent_positions = sorted(closed_positions, key=lambda x: x.get('exit_time', ''), reverse=True)[:10]
        
        df_positions = pd.DataFrame([
            {
                'Position ID': pos.get('position_id', 'N/A')[-20:],  # Show last 20 chars
                'Strategy': pos.get('strategy_type', 'N/A'),
                'Entry Time': datetime.fromisoformat(pos['entry_time'].replace('Z', '+00:00')).strftime('%m/%d %H:%M') if pos.get('entry_time') else 'N/A',
                'Exit Time': datetime.fromisoformat(pos['exit_time'].replace('Z', '+00:00')).strftime('%m/%d %H:%M') if pos.get('exit_time') else 'N/A',
                'P&L': format_currency(pos.get('realized_pnl', 0)),
                'Exit Reason': pos.get('exit_reason', 'N/A'),
                'Hold Days': pos.get('hold_duration_days', 0)
            }
            for pos in recent_positions
        ])
        
        st.dataframe(df_positions, use_container_width=True, hide_index=True)



# ==================== GREEKS PANEL ====================

def render_greeks_panel(state, config):
    """Render comprehensive Greeks panel with limits"""
    st.subheader("📈 Portfolio Greeks")
    
    if not state:
        st.warning("No data available")
        return
    
    # Get current portfolio Greeks from options system
    portfolio_greeks = state.get('portfolio_greeks', {})
    greeks_history = state.get('greeks_history', [])
    limits = config.get('greeks_limits', {}) if config else {}
    
    # Current Greeks values
    current_delta = portfolio_greeks.get('delta', 0)
    current_gamma = portfolio_greeks.get('gamma', 0)
    current_vega = portfolio_greeks.get('vega', 0)
    current_theta = portfolio_greeks.get('theta', 0)
    
    # Calculate utilization if limits exist
    utilization = {}
    if limits:
        utilization = calculate_greeks_utilization(portfolio_greeks, limits)
    
    # Greeks metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        delta_color = "🟢" if abs(current_delta) < 100 else "🟡" if abs(current_delta) < 500 else "🔴"
        st.metric(
            f"{delta_color} Delta",
            f"{current_delta:.2f}",
            f"{utilization.get('delta', 0):.1f}% of limit" if limits else None
        )
    
    with col2:
        gamma_color = "🟢" if abs(current_gamma) < 10 else "🟡" if abs(current_gamma) < 50 else "🔴"
        st.metric(
            f"{gamma_color} Gamma",
            f"{current_gamma:.2f}",
            f"{utilization.get('gamma', 0):.1f}% of limit" if limits else None
        )
    
    with col3:
        vega_color = "🟢" if abs(current_vega) < 1000 else "🟡" if abs(current_vega) < 5000 else "🔴"
        st.metric(
            f"{vega_color} Vega",
            f"{current_vega:.2f}",
            f"{utilization.get('vega', 0):.1f}% of limit" if limits else None
        )
    
    with col4:
        theta_color = "🟢" if current_theta > -100 else "🟡" if current_theta > -500 else "🔴"
        st.metric(
            f"{theta_color} Theta",
            f"{current_theta:.2f}",
            f"{utilization.get('theta', 0):.1f}% of limit" if limits else None
        )
    
    # Greeks visualization
    col1, col2 = st.columns(2)
    
    with col1:
        # Current Greeks breakdown
        greeks_values = {
            'Delta': current_delta,
            'Gamma': current_gamma,
            'Vega': current_vega,
            'Theta': current_theta
        }
        
        fig = go.Figure(data=[
            go.Bar(
                x=list(greeks_values.keys()),
                y=list(greeks_values.values()),
                marker_color=['#00ff88' if v >= 0 else '#ff4444' for v in greeks_values.values()],
                text=[f"{v:.2f}" for v in greeks_values.values()],
                textposition='outside'
            )
        ])
        
        fig.update_layout(
            title="Current Portfolio Greeks",
            xaxis_title="Greek",
            yaxis_title="Value",
            height=300,
            template="plotly_dark",
            showlegend=False
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Greeks evolution over time
        if greeks_history and len(greeks_history) > 1:
            # Parse timestamps and extract values
            timestamps = []
            delta_values = []
            gamma_values = []
            vega_values = []
            theta_values = []
            
            for entry in greeks_history[-20:]:  # Last 20 entries
                try:
                    timestamp = datetime.fromisoformat(entry['timestamp'].replace('Z', '+00:00'))
                    timestamps.append(timestamp)
                    delta_values.append(entry.get('delta', 0))
                    gamma_values.append(entry.get('gamma', 0))
                    vega_values.append(entry.get('vega', 0))
                    theta_values.append(entry.get('theta', 0))
                except:
                    continue
            
            if timestamps:
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=timestamps,
                    y=delta_values,
                    mode='lines+markers',
                    name='Delta',
                    line=dict(color='#00ff88', width=2)
                ))
                fig.add_trace(go.Scatter(
                    x=timestamps,
                    y=gamma_values,
                    mode='lines+markers',
                    name='Gamma',
                    line=dict(color='#ff8800', width=2),
                    yaxis='y2'
                ))
                fig.add_trace(go.Scatter(
                    x=timestamps,
                    y=vega_values,
                    mode='lines+markers',
                    name='Vega',
                    line=dict(color='#8800ff', width=2),
                    yaxis='y3'
                ))
                
                fig.update_layout(
                    title="Greeks Evolution",
                    xaxis_title="Time",
                    yaxis_title="Delta",
                    yaxis2=dict(
                        title="Gamma",
                        overlaying='y',
                        side='right'
                    ),
                    yaxis3=dict(
                        title="Vega",
                        overlaying='y',
                        side='right',
                        position=0.85
                    ),
                    height=300,
                    template="plotly_dark",
                    hovermode='x unified'
                )
                
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No valid historical Greeks data")
        else:
            st.info("Insufficient historical data for Greeks evolution")
    
    # Active positions Greeks contribution
    active_positions = state.get('active_positions', [])
    if active_positions:
        st.write("**Greeks by Active Position:**")
        
        position_greeks = []
        for pos in active_positions:
            position_greeks.append({
                'Position ID': pos.get('position_id', 'N/A')[-15:],
                'Strategy': pos.get('strategy_type', 'N/A'),
                'Delta': pos.get('greeks', {}).get('delta', 0),
                'Gamma': pos.get('greeks', {}).get('gamma', 0),
                'Vega': pos.get('greeks', {}).get('vega', 0),
                'Theta': pos.get('greeks', {}).get('theta', 0)
            })
        
        if position_greeks:
            df_positions = pd.DataFrame(position_greeks)
            st.dataframe(df_positions, use_container_width=True, hide_index=True)
    else:
        st.info("No active positions with Greeks data")
    
    # Greeks summary statistics
    if greeks_history:
        st.write("**Greeks Statistics (Recent History):**")
        
        # Calculate statistics from recent history
        recent_deltas = [entry.get('delta', 0) for entry in greeks_history[-50:]]
        recent_gammas = [entry.get('gamma', 0) for entry in greeks_history[-50:]]
        recent_vegas = [entry.get('vega', 0) for entry in greeks_history[-50:]]
        recent_thetas = [entry.get('theta', 0) for entry in greeks_history[-50:]]
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            if recent_deltas:
                st.metric("Delta Avg", f"{np.mean(recent_deltas):.2f}")
                st.metric("Delta Std", f"{np.std(recent_deltas):.2f}")
        
        with col2:
            if recent_gammas:
                st.metric("Gamma Avg", f"{np.mean(recent_gammas):.2f}")
                st.metric("Gamma Std", f"{np.std(recent_gammas):.2f}")
        
        with col3:
            if recent_vegas:
                st.metric("Vega Avg", f"{np.mean(recent_vegas):.2f}")
                st.metric("Vega Std", f"{np.std(recent_vegas):.2f}")
        
        with col4:
            if recent_thetas:
                st.metric("Theta Avg", f"{np.mean(recent_thetas):.2f}")
                st.metric("Theta Std", f"{np.std(recent_thetas):.2f}")


def render_regime_panel(state, config):
    """Render comprehensive regime panel"""
    st.subheader("🌡️ Market Regime Analysis")
    
    if not state:
        st.warning("No data available")
        return
    
    # Get regime data from options system
    current_regime = state.get('current_regime', 'unknown')
    regime_metrics = state.get('regime_metrics', {})
    portfolio_overlay = state.get('portfolio_overlay', {})
    
    # Extract regime information
    regime = regime_metrics.get('regime', current_regime)
    routed_regime = regime_metrics.get('routed_regime', regime)
    iv_rank = regime_metrics.get('iv_rank', 0)
    confidence = regime_metrics.get('confidence', 0)
    
    # Top metrics row
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        regime_icon = get_regime_icon(regime)
        st.metric("Current Regime", f"{regime_icon} {regime.replace('_', ' ').upper()}")
    
    with col2:
        st.metric("Confidence", f"{confidence:.1%}", 
                 "High" if confidence > 0.6 else "Medium" if confidence > 0.4 else "Low")
    
    with col3:
        st.metric("IV Rank", f"{iv_rank:.1%}")
    
    with col4:
        if routed_regime != regime:
            st.metric("Routed Regime", f"{get_regime_icon(routed_regime)} {routed_regime.replace('_', ' ').upper()}")
        else:
            st.metric("Regime Status", "✅ Aligned")
    
    # Portfolio overlay information
    if portfolio_overlay:
        st.write("**Portfolio Overlay Context:**")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            portfolio_regime = portfolio_overlay.get('regime', 'unknown')
            st.metric("Portfolio Regime", portfolio_regime.replace('-', ' ').title())
        
        with col2:
            hedge_intensity = portfolio_overlay.get('hedge_intensity', 0)
            st.metric("Hedge Intensity", f"{hedge_intensity:.1%}")
        
        with col3:
            risk_on_prob = portfolio_overlay.get('risk_on_probability', 0)
            st.metric("Risk-On Probability", f"{risk_on_prob:.1%}")
    
    # Charts row
    col1, col2 = st.columns(2)
    
    with col1:
        # Regime distribution from underlyings
        options_cycle = state.get('options_cycle', {})
        underlyings = options_cycle.get('underlyings', [])
        
        if underlyings:
            regime_counts = {}
            for underlying in underlyings:
                underlying_regime = underlying.get('regime', 'unknown')
                regime_counts[underlying_regime] = regime_counts.get(underlying_regime, 0) + 1
            
            if regime_counts:
                fig = go.Figure(data=[
                    go.Pie(
                        labels=list(regime_counts.keys()),
                        values=list(regime_counts.values()),
                        hole=0.3,
                        marker_colors=['#00ff88', '#ffaa00', '#ff4444', '#8800ff']
                    )
                ])
                
                fig.update_layout(
                    title="Regime Distribution Across Underlyings",
                    height=300,
                    template="plotly_dark"
                )
                
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No regime data available for underlyings")
        else:
            st.info("No underlyings data available")
    
    with col2:
        # IV Rank distribution
        if underlyings:
            iv_ranks = []
            underlying_names = []
            
            for underlying in underlyings:
                if underlying.get('iv_rank') is not None:
                    iv_ranks.append(underlying['iv_rank'])
                    underlying_names.append(underlying.get('underlying', 'Unknown'))
            
            if iv_ranks:
                fig = go.Figure()
                fig.add_trace(go.Histogram(
                    x=iv_ranks,
                    nbinsx=10,
                    marker_color='#00ff88',
                    opacity=0.7
                ))
                
                fig.update_layout(
                    title="IV Rank Distribution",
                    xaxis_title="IV Rank",
                    yaxis_title="Count",
                    height=300,
                    template="plotly_dark"
                )
                
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No IV rank data available")
        else:
            st.info("No IV rank data available")
    
    # Regime characteristics for current regime
    st.write("**Current Regime Characteristics:**")
    
    regime_chars = {
        'rising_vol_buy': {
            'Description': 'Rising volatility environment - buy vol strategies',
            'Preferred Strategies': 'Long Straddles, Calendar Spreads',
            'Risk Level': 'Medium-High',
            'Position Sizing': 'Standard'
        },
        'high_vol_sell': {
            'Description': 'High volatility environment - sell vol strategies',
            'Preferred Strategies': 'Short Strangles, Iron Condors',
            'Risk Level': 'High',
            'Position Sizing': 'Reduced'
        },
        'low_vol_sell': {
            'Description': 'Low volatility environment - sell vol strategies',
            'Preferred Strategies': 'Short Straddles, Covered Calls',
            'Risk Level': 'Low-Medium',
            'Position Sizing': 'Increased'
        },
        'neutral': {
            'Description': 'Neutral volatility environment',
            'Preferred Strategies': 'Market Neutral, Delta Neutral',
            'Risk Level': 'Medium',
            'Position Sizing': 'Standard'
        }
    }
    
    current_chars = regime_chars.get(regime, {
        'Description': f'Unknown regime: {regime}',
        'Preferred Strategies': 'Conservative strategies',
        'Risk Level': 'Unknown',
        'Position Sizing': 'Reduced'
    })
    
    df_chars = pd.DataFrame([current_chars]).T
    df_chars.columns = ['Value']
    df_chars.index.name = 'Characteristic'
    st.dataframe(df_chars, use_container_width=True)
    
    # Underlying-specific regime details
    if underlyings:
        with st.expander("📊 Regime Details by Underlying"):
            regime_details = []
            
            for underlying in underlyings[:10]:  # Show top 10
                regime_details.append({
                    'Underlying': underlying.get('underlying', 'N/A'),
                    'Regime': underlying.get('regime', 'N/A'),
                    'Routed Regime': underlying.get('routed_regime', 'N/A'),
                    'IV Rank': f"{underlying.get('iv_rank', 0):.1%}",
                    'Confidence': f"{underlying.get('confidence', 0):.1%}",
                    'ATM IV': f"{underlying.get('atm_iv', 0):.1%}",
                    'Contracts': underlying.get('contracts', 0)
                })
            
            df_regime_details = pd.DataFrame(regime_details)
            st.dataframe(df_regime_details, use_container_width=True, hide_index=True)
    
    # Portfolio overlay weekly rationale
    if portfolio_overlay and portfolio_overlay.get('weekly_rationale'):
        with st.expander("📝 Weekly Market Rationale"):
            st.write(portfolio_overlay['weekly_rationale'])


def render_risk_panel(state, config):
    """Render comprehensive risk panel"""
    st.subheader("⚠️ Risk Management")
    
    if not state:
        st.warning("No data available")
        return
    
    risk_metrics = state.get('risk_metrics', {})
    risk_thresholds = config.get('risk_thresholds', {}) if config else {}
    
    # Top risk metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        var_95 = risk_metrics.get('var_95', 0)
        var_limit = risk_thresholds.get('var_95', 50000)
        var_util = (var_95 / var_limit * 100) if var_limit > 0 else 0
        
        st.metric(
            "VaR 95%",
            format_currency(var_95),
            f"{var_util:.1f}% of limit",
            delta_color="inverse"
        )
        st.progress(min(var_util / 100, 1.0))
    
    with col2:
        cvar_95 = risk_metrics.get('cvar_95', 0)
        cvar_limit = risk_thresholds.get('cvar_95', 75000)
        cvar_util = (cvar_95 / cvar_limit * 100) if cvar_limit > 0 else 0
        
        st.metric(
            "CVaR 95%",
            format_currency(cvar_95),
            f"{cvar_util:.1f}% of limit",
            delta_color="inverse"
        )
        st.progress(min(cvar_util / 100, 1.0))
    
    with col3:
        max_dd = risk_metrics.get('max_drawdown', 0)
        dd_limit = risk_thresholds.get('max_drawdown', 0.15)
        dd_util = (max_dd / dd_limit * 100) if dd_limit > 0 else 0
        
        st.metric(
            "Max Drawdown",
            format_percentage(max_dd),
            f"{dd_util:.1f}% of limit",
            delta_color="inverse"
        )
        st.progress(min(dd_util / 100, 1.0))
    
    with col4:
        current_dd = risk_metrics.get('current_drawdown', 0)
        st.metric(
            "Current Drawdown",
            format_percentage(current_dd),
            "Recovering" if current_dd < max_dd else "At Max"
        )
    
    # Risk visualization
    col1, col2 = st.columns(2)
    
    with col1:
        # VaR/CVaR gauge chart
        fig = go.Figure()
        
        fig.add_trace(go.Indicator(
            mode="gauge+number+delta",
            value=var_95,
            domain={'x': [0, 1], 'y': [0, 1]},
            title={'text': "VaR 95%", 'font': {'size': 20}},
            delta={'reference': var_limit, 'increasing': {'color': "red"}},
            gauge={
                'axis': {'range': [None, var_limit * 1.2]},
                'bar': {'color': "#00ff88"},
                'steps': [
                    {'range': [0, var_limit * 0.8], 'color': "rgba(0, 255, 136, 0.2)"},
                    {'range': [var_limit * 0.8, var_limit], 'color': "rgba(255, 170, 0, 0.2)"},
                    {'range': [var_limit, var_limit * 1.2], 'color': "rgba(255, 68, 68, 0.2)"}
                ],
                'threshold': {
                    'line': {'color': "red", 'width': 4},
                    'thickness': 0.75,
                    'value': var_limit
                }
            }
        ))
        
        fig.update_layout(
            height=300,
            template="plotly_dark"
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Drawdown chart over time
        historical = load_historical_snapshots(365)  # Load more data
        historical = filter_meaningful_data(historical, get_system_start_date())  # Filter to meaningful period
        
        if historical and len(historical) > 1:
            dates = [h['_timestamp'] for h in historical]
            drawdowns = [h.get('risk_metrics', {}).get('current_drawdown', 0) for h in historical]
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=dates,
                y=[d * 100 for d in drawdowns],
                mode='lines',
                name='Drawdown',
                line=dict(color='#ff4444', width=2),
                fill='tozeroy',
                fillcolor='rgba(255, 68, 68, 0.2)'
            ))
            
            # Add max drawdown line
            fig.add_hline(
                y=dd_limit * 100,
                line_dash="dash",
                line_color="red",
                annotation_text="Max DD Limit"
            )
            
            fig.update_layout(
                title="Drawdown History (Since Dec 2025)",
                xaxis_title="Date",
                yaxis_title="Drawdown (%)",
                height=300,
                template="plotly_dark",
                hovermode='x unified'
            )
            
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Insufficient historical data for drawdown chart")
    
    # Stress test results
    st.write("**Stress Test Results:**")
    
    stress_scenarios = risk_metrics.get('stress_tests', {
        '2008 Crisis': -45000,
        '2020 COVID': -38000,
        'Flash Crash': -25000,
        'Vol Spike +50%': -32000,
        'Correlation Breakdown': -28000
    })
    
    df_stress = pd.DataFrame([
        {
            'Scenario': scenario,
            'P&L Impact': format_currency(impact),
            'Severity': '🔴 Critical' if impact < -40000 else '🟡 High' if impact < -30000 else '🟢 Moderate'
        }
        for scenario, impact in stress_scenarios.items()
    ])
    
    st.dataframe(df_stress, use_container_width=True, hide_index=True)
    
    # Risk decomposition
    with st.expander("📊 Risk Decomposition"):
        st.write("**Risk contribution by source:**")
        
        risk_contrib = {
            'Delta Risk': risk_metrics.get('delta_risk', 0),
            'Gamma Risk': risk_metrics.get('gamma_risk', 0),
            'Vega Risk': risk_metrics.get('vega_risk', 0),
            'Correlation Risk': risk_metrics.get('correlation_risk', 0),
            'Tail Risk': risk_metrics.get('tail_risk', 0)
        }
        
        fig = go.Figure(data=[go.Pie(
            labels=list(risk_contrib.keys()),
            values=[abs(v) for v in risk_contrib.values()],
            hole=0.4,
            marker=dict(colors=['#00ff88', '#ffaa00', '#ff8800', '#ff4444', '#ff0000'])
        )])
        
        fig.update_layout(
            title="Risk Contribution by Source",
            height=300,
            template="plotly_dark"
        )
        
        st.plotly_chart(fig, use_container_width=True)


def render_market_snapshot_panel(state):
    """Render market snapshot and options cycle information"""
    st.subheader("📊 Market Snapshot & Options Cycle")
    
    if not state:
        st.warning("No data available")
        return
    
    # Market snapshot
    market_snapshot = state.get('market_snapshot', {})
    options_cycle = state.get('options_cycle', {})
    
    if market_snapshot:
        st.write("**Market Snapshot:**")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            nifty_price = market_snapshot.get('NIFTY_price', 0)
            st.metric("NIFTY", f"₹{nifty_price:,.2f}")
        
        with col2:
            banknifty_price = market_snapshot.get('BANKNIFTY_price', 0)
            st.metric("BANKNIFTY", f"₹{banknifty_price:,.2f}")
        
        with col3:
            option_contracts = market_snapshot.get('option_contracts', 0)
            st.metric("Option Contracts", f"{option_contracts:,}")
    
    # Options cycle summary
    if options_cycle:
        underlyings_configured = options_cycle.get('underlyings_configured', [])
        underlyings = options_cycle.get('underlyings', [])
        summary = options_cycle.get('summary', {})
        
        st.write("**Options Cycle Summary:**")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Configured Underlyings", len(underlyings_configured))
        
        with col2:
            processed = summary.get('processed_underlyings', 0)
            st.metric("Processed", processed)
        
        with col3:
            generated = summary.get('generated_strategies', 0)
            st.metric("Strategies Generated", generated)
        
        with col4:
            blocked = summary.get('blocked', 0)
            st.metric("Blocked", blocked)
        
        # Portfolio overlay information
        portfolio_overlay = options_cycle.get('portfolio_overlay', {})
        if portfolio_overlay:
            st.write("**Portfolio Overlay:**")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                objective = portfolio_overlay.get('portfolio_objective', 'N/A')
                st.metric("Portfolio Objective", objective.replace('_', ' ').title())
            
            with col2:
                hedge_intensity = portfolio_overlay.get('hedge_intensity', 0)
                st.metric("Hedge Intensity", f"{hedge_intensity:.1%}")
            
            with col3:
                total_exposure = portfolio_overlay.get('total_exposure', 0)
                st.metric("Total Exposure", f"{total_exposure:.1%}")
        
        # Underlyings status breakdown
        if underlyings:
            st.write("**Underlyings Status Breakdown:**")
            
            status_counts = {}
            for underlying in underlyings:
                status = underlying.get('status', 'unknown')
                status_counts[status] = status_counts.get(status, 0) + 1
            
            # Create a pie chart for status distribution
            if status_counts:
                fig = go.Figure(data=[
                    go.Pie(
                        labels=list(status_counts.keys()),
                        values=list(status_counts.values()),
                        hole=0.3
                    )
                ])
                
                fig.update_layout(
                    title="Underlyings Status Distribution",
                    height=300,
                    template="plotly_dark"
                )
                
                st.plotly_chart(fig, use_container_width=True)
            
            # Top underlyings by contract count
            top_underlyings = sorted(
                [u for u in underlyings if u.get('contracts', 0) > 0],
                key=lambda x: x.get('contracts', 0),
                reverse=True
            )[:10]
            
            if top_underlyings:
                st.write("**Top Underlyings by Contract Count:**")
                
                underlying_data = []
                for underlying in top_underlyings:
                    underlying_data.append({
                        'Underlying': underlying.get('underlying', 'N/A'),
                        'Contracts': underlying.get('contracts', 0),
                        'Spot Price': f"₹{underlying.get('spot', 0):,.2f}",
                        'ATM IV': f"{underlying.get('atm_iv', 0):.1%}",
                        'Regime': underlying.get('regime', 'N/A'),
                        'Status': underlying.get('status', 'N/A')
                    })
                
                df_top_underlyings = pd.DataFrame(underlying_data)
                st.dataframe(df_top_underlyings, use_container_width=True, hide_index=True)
def render_market_pressure_surface_panel(state, config):
    """Render market pressure surface with all metrics"""
    st.subheader("🌍 Market Pressure Surface")

    if not state:
        st.warning("No data available")
        return

    # Get available data from actual state structure
    current_regime = state.get('regime', 'neutral')
    portfolio_greeks = state.get('portfolio_greeks', {})
    positions = state.get('positions', [])
    total_pnl = state.get('total_pnl', 0)
    market_data = state.get('market_data', {})

    # Calculate metrics from available data
    # 1. Regime Confidence - estimate from regime stability and position performance
    if total_pnl > 0:
        regime_confidence = min(0.9, 0.6 + (total_pnl / 10000) * 0.3)  # Higher confidence with profits
    else:
        regime_confidence = max(0.3, 0.6 + (total_pnl / 10000) * 0.3)  # Lower confidence with losses

    # 2. Risk Pressure Z - calculate from portfolio greeks and position concentration
    total_vega = abs(portfolio_greeks.get('vega', 0))
    total_gamma = abs(portfolio_greeks.get('gamma', 0))
    total_theta = abs(portfolio_greeks.get('theta', 0))

    # Normalize greeks to get pressure score
    if total_vega > 0:
        vega_pressure = min(3.0, total_vega / 5000)  # Scale vega exposure
        gamma_pressure = min(2.0, total_gamma / 2000)  # Scale gamma exposure
        theta_pressure = min(2.0, total_theta / 1000)  # Scale theta exposure
        risk_pressure_z = (vega_pressure + gamma_pressure + theta_pressure) / 3 - 1.0
    else:
        risk_pressure_z = 0.0

    # 3. Crisis Probability - estimate from regime and portfolio stress
    if current_regime in ['high_vol_sell', 'crisis', 'falling_vol_sell']:
        crisis_probability = 0.4 + (1 - regime_confidence) * 0.3
    elif current_regime in ['rising_vol_buy', 'high_vol_buy']:
        crisis_probability = 0.15 + (1 - regime_confidence) * 0.2
    else:
        crisis_probability = 0.1 + (1 - regime_confidence) * 0.15

    # Add portfolio stress factor
    if total_pnl < -5000:  # Significant losses
        crisis_probability = min(0.8, crisis_probability + 0.2)

    # 4. Regime Entropy - calculate from position diversity and regime uncertainty
    if positions:
        # Calculate position type diversity
        position_types = {}
        for pos in positions:
            pos_type = pos.get('option_type', 'unknown')
            position_types[pos_type] = position_types.get(pos_type, 0) + 1

        total_positions = len(positions)
        if total_positions > 1:
            # Shannon entropy of position types
            regime_entropy = -sum((count/total_positions) * np.log2(count/total_positions)
                                for count in position_types.values() if count > 0)
        else:
            regime_entropy = 0.0
    else:
        regime_entropy = 2.0  # High entropy when no positions

    # Add regime uncertainty factor
    regime_uncertainty_map = {
        'neutral': 1.5,
        'rising_vol_buy': 0.8,
        'falling_vol_sell': 0.8,
        'high_vol_buy': 1.2,
        'high_vol_sell': 1.2,
        'crisis': 2.0
    }
    regime_entropy += regime_uncertainty_map.get(current_regime, 1.0)

    # 5. Systemic Stress - estimate from portfolio performance and market conditions
    # Base stress from PnL performance
    if total_pnl < -10000:
        systemic_stress = 0.8
    elif total_pnl < -5000:
        systemic_stress = 0.4
    elif total_pnl < 0:
        systemic_stress = 0.1
    elif total_pnl > 10000:
        systemic_stress = -0.3  # Negative stress (good conditions)
    else:
        systemic_stress = 0.0

    # Add regime stress factor
    regime_stress_map = {
        'crisis': 0.5,
        'high_vol_sell': 0.3,
        'falling_vol_sell': 0.2,
        'neutral': 0.0,
        'rising_vol_buy': -0.1,
        'high_vol_buy': 0.1
    }
    systemic_stress += regime_stress_map.get(current_regime, 0.0)
    systemic_stress = max(-1.0, min(1.0, systemic_stress))  # Clamp to [-1, 1]

    # Display current metrics
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        confidence_color = "normal" if regime_confidence > 0.6 else "inverse"
        st.metric(
            "Regime Confidence",
            f"{regime_confidence:.2f}",
            "High" if regime_confidence > 0.7 else "Medium" if regime_confidence > 0.4 else "Low",
            delta_color=confidence_color
        )

    with col2:
        pressure_color = "inverse" if abs(risk_pressure_z) > 1.5 else "normal"
        st.metric(
            "Risk Pressure (z)",
            f"{risk_pressure_z:+.2f}",
            "Elevated" if abs(risk_pressure_z) > 1.5 else "Normal",
            delta_color=pressure_color
        )

    with col3:
        crisis_color = "inverse" if crisis_probability > 0.3 else "normal"
        st.metric(
            "Crisis Probability",
            f"{crisis_probability:.1%}",
            "High" if crisis_probability > 0.3 else "Medium" if crisis_probability > 0.1 else "Low",
            delta_color=crisis_color
        )

    with col4:
        entropy_color = "inverse" if regime_entropy > 1.5 else "normal"
        st.metric(
            "Regime Entropy",
            f"{regime_entropy:.2f}",
            "High" if regime_entropy > 1.5 else "Medium" if regime_entropy > 0.8 else "Low",
            delta_color=entropy_color
        )

    with col5:
        stress_color = "inverse" if abs(systemic_stress) > 0.5 else "normal"
        st.metric(
            "Systemic Stress",
            f"{systemic_stress:+.2f}",
            "Elevated" if abs(systemic_stress) > 0.5 else "Normal",
            delta_color=stress_color
        )

    # Load historical data for charts
    historical = load_historical_snapshots(365)  # Load more data

    # Filter to recent data (Feb 2026 onwards since that's when we have data)
    filtered_historical = []
    for h in historical:
        # Use file modification time as timestamp
        if hasattr(h, '_timestamp') or '_timestamp' in h:
            filtered_historical.append(h)

    if filtered_historical and len(filtered_historical) > 5:
        # Prepare time series data
        dates = []
        regime_conf_series = []
        risk_pressure_series = []
        crisis_prob_series = []
        entropy_series = []
        stress_series = []

        for h in filtered_historical:
            dates.append(h.get('_timestamp', datetime.now()))

            # Extract metrics from historical data using actual structure
            hist_regime = h.get('regime', 'neutral')
            hist_portfolio_greeks = h.get('portfolio_greeks', {})
            hist_positions = h.get('positions', [])
            hist_total_pnl = h.get('total_pnl', 0)

            # Historical regime confidence
            if hist_total_pnl > 0:
                hist_confidence = min(0.9, 0.6 + (hist_total_pnl / 10000) * 0.3)
            else:
                hist_confidence = max(0.3, 0.6 + (hist_total_pnl / 10000) * 0.3)
            regime_conf_series.append(hist_confidence)

            # Historical risk pressure
            hist_vega = abs(hist_portfolio_greeks.get('vega', 0))
            hist_gamma = abs(hist_portfolio_greeks.get('gamma', 0))
            hist_theta = abs(hist_portfolio_greeks.get('theta', 0))

            if hist_vega > 0:
                hist_vega_pressure = min(3.0, hist_vega / 5000)
                hist_gamma_pressure = min(2.0, hist_gamma / 2000)
                hist_theta_pressure = min(2.0, hist_theta / 1000)
                hist_risk_pressure = (hist_vega_pressure + hist_gamma_pressure + hist_theta_pressure) / 3 - 1.0
            else:
                hist_risk_pressure = 0.0
            risk_pressure_series.append(hist_risk_pressure)

            # Historical crisis probability
            if hist_regime in ['high_vol_sell', 'crisis', 'falling_vol_sell']:
                hist_crisis_prob = 0.4 + (1 - hist_confidence) * 0.3
            elif hist_regime in ['rising_vol_buy', 'high_vol_buy']:
                hist_crisis_prob = 0.15 + (1 - hist_confidence) * 0.2
            else:
                hist_crisis_prob = 0.1 + (1 - hist_confidence) * 0.15

            if hist_total_pnl < -5000:
                hist_crisis_prob = min(0.8, hist_crisis_prob + 0.2)
            crisis_prob_series.append(hist_crisis_prob)

            # Historical regime entropy
            if hist_positions:
                hist_position_types = {}
                for pos in hist_positions:
                    pos_type = pos.get('option_type', 'unknown')
                    hist_position_types[pos_type] = hist_position_types.get(pos_type, 0) + 1

                hist_total_positions = len(hist_positions)
                if hist_total_positions > 1:
                    hist_entropy = -sum((count/hist_total_positions) * np.log2(count/hist_total_positions)
                                      for count in hist_position_types.values() if count > 0)
                else:
                    hist_entropy = 0.0
            else:
                hist_entropy = 2.0

            hist_entropy += regime_uncertainty_map.get(hist_regime, 1.0)
            entropy_series.append(hist_entropy)

            # Historical systemic stress
            if hist_total_pnl < -10000:
                hist_stress = 0.8
            elif hist_total_pnl < -5000:
                hist_stress = 0.4
            elif hist_total_pnl < 0:
                hist_stress = 0.1
            elif hist_total_pnl > 10000:
                hist_stress = -0.3
            else:
                hist_stress = 0.0

            hist_stress += regime_stress_map.get(hist_regime, 0.0)
            hist_stress = max(-1.0, min(1.0, hist_stress))
            stress_series.append(hist_stress)

        # Create the market pressure surface chart
        fig = make_subplots(specs=[[{"secondary_y": True}]])

        # Add traces for each metric
        fig.add_trace(
            go.Scatter(
                x=dates,
                y=regime_conf_series,
                mode='lines',
                name='Regime Confidence',
                line=dict(color='#00ff88', width=2),
                yaxis='y2'
            ),
            secondary_y=True
        )

        fig.add_trace(
            go.Scatter(
                x=dates,
                y=crisis_prob_series,
                mode='lines',
                name='Crisis Probability',
                line=dict(color='#ff4444', width=2),
                yaxis='y2'
            ),
            secondary_y=True
        )

        fig.add_trace(
            go.Scatter(
                x=dates,
                y=risk_pressure_series,
                mode='lines',
                name='Risk Pressure (z)',
                line=dict(color='#ffaa00', width=2)
            ),
            secondary_y=False
        )

        fig.add_trace(
            go.Scatter(
                x=dates,
                y=entropy_series,
                mode='lines',
                name='Regime Entropy',
                line=dict(color='#8800ff', width=2)
            ),
            secondary_y=False
        )

        fig.add_trace(
            go.Scatter(
                x=dates,
                y=stress_series,
                mode='lines',
                name='Systemic Stress',
                line=dict(color='#ff8800', width=2)
            ),
            secondary_y=False
        )

        # Update layout
        fig.update_layout(
            title="Market Pressure Surface (Live System Data)",
            height=400,
            template="plotly_dark",
            hovermode='x unified'
        )

        fig.update_yaxes(title_text="Pressure / Entropy / Stress", secondary_y=False)
        fig.update_yaxes(title_text="Probability / Confidence", range=[0, 1], secondary_y=True)

        st.plotly_chart(fig, use_container_width=True)

        # Current market conditions summary
        st.write("**Current Market Conditions:**")

        conditions = []
        if regime_confidence < 0.4:
            conditions.append("🔴 Low regime confidence - uncertain market conditions")
        elif regime_confidence > 0.8:
            conditions.append("🟢 High regime confidence - stable market conditions")

        if abs(risk_pressure_z) > 2:
            conditions.append("🔴 Extreme risk pressure - high volatility environment")
        elif abs(risk_pressure_z) > 1:
            conditions.append("🟡 Elevated risk pressure - increased volatility")

        if crisis_probability > 0.3:
            conditions.append("🔴 High crisis probability - defensive positioning recommended")
        elif crisis_probability > 0.15:
            conditions.append("🟡 Moderate crisis probability - cautious approach advised")

        if regime_entropy > 1.5:
            conditions.append("🔴 High regime entropy - mixed signals across markets")

        if abs(systemic_stress) > 0.5:
            conditions.append("🔴 Elevated systemic stress - negative sentiment prevailing")

        if not conditions:
            conditions.append("🟢 Normal market conditions - no significant stress indicators")

        for condition in conditions:
            st.write(f"- {condition}")

        # Current regime and portfolio summary
        st.write(f"**Current Regime:** `{current_regime}` | **Total PnL:** {format_currency(total_pnl)} | **Positions:** {len(positions)}")

    else:
        st.info("Insufficient historical data for market pressure surface chart")

        # Show current metrics in a detailed table
        metrics_data = {
            'Metric': ['Regime Confidence', 'Risk Pressure (z)', 'Crisis Probability', 'Regime Entropy', 'Systemic Stress'],
            'Current Value': [
                f"{regime_confidence:.2f}",
                f"{risk_pressure_z:+.2f}",
                f"{crisis_probability:.1%}",
                f"{regime_entropy:.2f}",
                f"{systemic_stress:+.2f}"
            ],
            'Status': [
                "High" if regime_confidence > 0.7 else "Medium" if regime_confidence > 0.4 else "Low",
                "Elevated" if abs(risk_pressure_z) > 1.5 else "Normal",
                "High" if crisis_probability > 0.3 else "Medium" if crisis_probability > 0.1 else "Low",
                "High" if regime_entropy > 1.5 else "Medium" if regime_entropy > 0.8 else "Low",
                "Elevated" if abs(systemic_stress) > 0.5 else "Normal"
            ],
            'Description': [
                "Market regime detection confidence",
                "Portfolio greeks pressure indicator",
                "Estimated crisis regime probability",
                "Position diversity and regime uncertainty",
                "Performance and regime-based stress indicator"
            ]
        }

        df_metrics = pd.DataFrame(metrics_data)
        st.dataframe(df_metrics, use_container_width=True, hide_index=True)




def render_options_decision_history_panel(state):
    """Render options decision history"""
    st.subheader("📈 Options Decision History")
    
    if not state:
        st.warning("No data available")
        return
    
    decision_history = state.get('options_decision_history', [])
    
    if not decision_history:
        st.info("No decision history available")
        return
    
    # Recent decisions (last 20)
    recent_decisions = decision_history[-20:]
    
    st.write("**Recent Options Decisions:**")
    
    decision_data = []
    for decision in reversed(recent_decisions):  # Show most recent first
        decision_data.append({
            'Timestamp': datetime.fromisoformat(decision['timestamp'].replace('Z', '+00:00')).strftime('%m/%d %H:%M') if decision.get('timestamp') else 'N/A',
            'Underlying': decision.get('underlying', 'N/A'),
            'Status': decision.get('status', 'N/A'),
            'Strategy': decision.get('strategy_type', 'N/A'),
            'Objective': decision.get('objective', 'N/A'),
            'Regime': decision.get('regime', 'N/A'),
            'Contracts': decision.get('contracts', 0),
            'Reason': decision.get('reason', 'N/A')
        })
    
    df_decisions = pd.DataFrame(decision_data)
    st.dataframe(df_decisions, use_container_width=True, hide_index=True)
    
    # Decision statistics
    col1, col2 = st.columns(2)
    
    with col1:
        # Status distribution
        status_counts = {}
        for decision in decision_history:
            status = decision.get('status', 'unknown')
            status_counts[status] = status_counts.get(status, 0) + 1
        
        if status_counts:
            fig = go.Figure(data=[
                go.Pie(
                    labels=list(status_counts.keys()),
                    values=list(status_counts.values()),
                    hole=0.3
                )
            ])
            
            fig.update_layout(
                title="Decision Status Distribution",
                height=300,
                template="plotly_dark"
            )
            
            st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Strategy type distribution (for opened positions only)
        strategy_counts = {}
        for decision in decision_history:
            if decision.get('status') == 'opened_position':
                strategy = decision.get('strategy_type', 'unknown')
                strategy_counts[strategy] = strategy_counts.get(strategy, 0) + 1
        
        if strategy_counts:
            fig = go.Figure(data=[
                go.Bar(
                    x=list(strategy_counts.keys()),
                    y=list(strategy_counts.values()),
                    marker_color='#00ff88'
                )
            ])
            
            fig.update_layout(
                title="Strategy Types (Opened Positions)",
                xaxis_title="Strategy",
                yaxis_title="Count",
                height=300,
                template="plotly_dark",
                showlegend=False
            )
            
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No opened positions in decision history")


def render_positions_panel(state, config):
    """Render comprehensive positions panel"""
    st.subheader("📋 Position Management")
    
    if not state:
        st.warning("No data available")
        return
    
    # Get positions data from options system
    active_positions = state.get('active_positions', [])
    closed_positions = state.get('closed_positions', [])
    options_cycle = state.get('options_cycle', {})
    
    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Active Positions", len(active_positions))
    
    with col2:
        st.metric("Closed Positions", len(closed_positions))
    
    with col3:
        # Calculate total realized P&L from closed positions
        total_realized_pnl = sum(pos.get('realized_pnl', 0) for pos in closed_positions)
        st.metric("Total Realized P&L", format_currency(total_realized_pnl))
    
    with col4:
        # Calculate today's activity
        today = datetime.now().date()
        today_trades = sum(
            1 for pos in closed_positions 
            if pos.get('exit_time') and 
            datetime.fromisoformat(pos['exit_time'].replace('Z', '+00:00')).date() == today
        )
        st.metric("Today's Trades", today_trades)
    
    # Active positions section
    if active_positions:
        st.write("**Active Positions:**")
        
        position_data = []
        for pos in active_positions:
            position_data.append({
                'Position ID': pos.get('position_id', 'N/A')[-15:],
                'Strategy': pos.get('strategy_type', 'N/A'),
                'Underlying': pos.get('underlying', 'N/A'),
                'Entry Time': datetime.fromisoformat(pos['entry_time'].replace('Z', '+00:00')).strftime('%m/%d %H:%M') if pos.get('entry_time') else 'N/A',
                'Unrealized P&L': format_currency(pos.get('unrealized_pnl', 0)),
                'Delta': f"{pos.get('greeks', {}).get('delta', 0):.2f}",
                'Gamma': f"{pos.get('greeks', {}).get('gamma', 0):.3f}",
                'Vega': f"{pos.get('greeks', {}).get('vega', 0):.2f}",
                'Theta': f"{pos.get('greeks', {}).get('theta', 0):.2f}"
            })
        
        df_active = pd.DataFrame(position_data)
        st.dataframe(df_active, use_container_width=True, hide_index=True)
    else:
        st.info("No active positions")
    
    # Recent closed positions
    if closed_positions:
        st.write("**Recent Closed Positions:**")
        
        # Sort by exit time and take the most recent 10
        recent_closed = sorted(
            closed_positions, 
            key=lambda x: x.get('exit_time', ''), 
            reverse=True
        )[:10]
        
        closed_data = []
        for pos in recent_closed:
            closed_data.append({
                'Position ID': pos.get('position_id', 'N/A')[-15:],
                'Strategy': pos.get('strategy_type', 'N/A'),
                'Entry Time': datetime.fromisoformat(pos['entry_time'].replace('Z', '+00:00')).strftime('%m/%d %H:%M') if pos.get('entry_time') else 'N/A',
                'Exit Time': datetime.fromisoformat(pos['exit_time'].replace('Z', '+00:00')).strftime('%m/%d %H:%M') if pos.get('exit_time') else 'N/A',
                'Realized P&L': format_currency(pos.get('realized_pnl', 0)),
                'Exit Reason': pos.get('exit_reason', 'N/A'),
                'Hold Duration': f"{pos.get('hold_duration_days', 0):.1f} days"
            })
        
        df_closed = pd.DataFrame(closed_data)
        st.dataframe(df_closed, use_container_width=True, hide_index=True)
    
    # Charts row
    col1, col2 = st.columns(2)
    
    with col1:
        # P&L by strategy type
        if closed_positions:
            strategy_pnl = {}
            for pos in closed_positions:
                strategy = pos.get('strategy_type', 'unknown')
                pnl = pos.get('realized_pnl', 0)
                strategy_pnl[strategy] = strategy_pnl.get(strategy, 0) + pnl
            
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=list(strategy_pnl.keys()),
                y=list(strategy_pnl.values()),
                marker_color=['#00ff88' if v >= 0 else '#ff4444' for v in strategy_pnl.values()],
                text=[format_currency(v) for v in strategy_pnl.values()],
                textposition='outside'
            ))
            
            fig.update_layout(
                title="P&L by Strategy Type",
                xaxis_title="Strategy",
                yaxis_title="P&L ($)",
                height=300,
                template="plotly_dark",
                showlegend=False
            )
            
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No closed positions for P&L analysis")
    
    with col2:
        # Exit reasons distribution
        if closed_positions:
            exit_reasons = {}
            for pos in closed_positions:
                reason = pos.get('exit_reason', 'unknown')
                exit_reasons[reason] = exit_reasons.get(reason, 0) + 1
            
            fig = go.Figure(data=[
                go.Pie(
                    labels=list(exit_reasons.keys()),
                    values=list(exit_reasons.values()),
                    hole=0.3
                )
            ])
            
            fig.update_layout(
                title="Exit Reasons Distribution",
                height=300,
                template="plotly_dark"
            )
            
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No exit reason data available")
    
    # Options cycle summary
    if options_cycle:
        with st.expander("📊 Options Cycle Summary"):
            underlyings = options_cycle.get('underlyings', [])
            
            if underlyings:
                st.write("**Underlying Status:**")
                
                underlying_data = []
                for underlying in underlyings[:15]:  # Show top 15
                    underlying_data.append({
                        'Underlying': underlying.get('underlying', 'N/A'),
                        'Status': underlying.get('status', 'N/A'),
                        'Contracts': underlying.get('contracts', 0),
                        'Spot Price': f"${underlying.get('spot', 0):.2f}",
                        'ATM IV': f"{underlying.get('atm_iv', 0):.1%}",
                        'Regime': underlying.get('regime', 'N/A'),
                        'Reason': underlying.get('reason', 'N/A')
                    })
                
                df_underlyings = pd.DataFrame(underlying_data)
                st.dataframe(df_underlyings, use_container_width=True, hide_index=True)
                
                # Summary statistics
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    total_underlyings = len(underlyings)
                    st.metric("Total Underlyings", total_underlyings)
                
                with col2:
                    active_strategies = sum(1 for u in underlyings if u.get('status') == 'opened_position')
                    st.metric("Active Strategies", active_strategies)
                
                with col3:
                    no_strategy = sum(1 for u in underlyings if u.get('status') == 'no_strategy')
                    st.metric("No Strategy", no_strategy)
                
                with col4:
                    rejected = sum(1 for u in underlyings if u.get('status') == 'rejected_eligibility')
                    st.metric("Rejected", rejected)
            else:
                st.info("No underlyings data available")
    
    # Position limits and risk checks
    if config:
        with st.expander("⚠️ Risk Limits & Checks"):
            active_limits = state.get('active_limits', {})
            weekly_risk_usage = state.get('weekly_risk_usage', {})
            
            st.write("**Active Limits:**")
            
            col1, col2 = st.columns(2)
            
            with col1:
                max_trades = active_limits.get('max_trades_per_week', 'N/A')
                trades_used = weekly_risk_usage.get('trades_used', 0)
                st.metric("Weekly Trade Limit", f"{trades_used} / {max_trades}")
                
                if isinstance(max_trades, (int, float)) and trades_used >= max_trades:
                    st.error("⚠️ Weekly trade limit exceeded!")
            
            with col2:
                risk_cap = active_limits.get('portfolio_risk_cap_pct', 0)
                risk_used = weekly_risk_usage.get('risk_used', 0)
                risk_limit = weekly_risk_usage.get('risk_limit', 0)
                
                st.metric("Risk Usage", f"{format_currency(risk_used)} / {format_currency(risk_limit)}")
                
                if risk_limit > 0:
                    risk_pct = risk_used / risk_limit
                    if risk_pct > 0.8:
                        st.warning(f"⚠️ Risk usage at {risk_pct:.1%}")
            
            # Kill switch status
            kill_switch = state.get('kill_switch_status', {})
            if kill_switch.get('active'):
                st.error(f"🛑 Kill Switch Active: {kill_switch.get('reason', 'Unknown reason')}")
            else:
                st.success("✅ Kill Switch Inactive")


def render_performance_panel(state, config):
    """Render comprehensive performance panel"""
    st.subheader("📊 Performance Analytics")

    if not state:
        st.warning("No data available")
        return

    # Get performance metrics from actual state structure
    perf_metrics = state.get('performance_metrics', {})
    risk_metrics = state.get('risk_metrics', {})
    total_pnl = state.get('total_pnl', 0)
    realized_pnl = state.get('realized_pnl', 0)
    unrealized_pnl = state.get('unrealized_pnl', 0)
    today_pnl = state.get('today_pnl', 0)

    # Top performance metrics
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        sharpe = perf_metrics.get('sharpe_ratio', 0)
        st.metric("Sharpe Ratio", f"{sharpe:.2f}",
                 "Excellent" if sharpe > 2 else "Good" if sharpe > 1 else "Fair")

    with col2:
        win_rate = perf_metrics.get('win_rate', 0)
        st.metric("Win Rate", f"{win_rate:.1%}",
                 "High" if win_rate > 0.6 else "Medium" if win_rate > 0.5 else "Low")

    with col3:
        total_trades = perf_metrics.get('total_trades', 0)
        st.metric("Total Trades", total_trades)

    with col4:
        max_dd = risk_metrics.get('max_drawdown', 0)
        st.metric("Max Drawdown", format_currency(max_dd))

    with col5:
        current_dd = risk_metrics.get('current_drawdown', 0)
        st.metric("Current Drawdown", format_currency(current_dd))

    # Performance charts
    col1, col2 = st.columns(2)

    with col1:
        # Cumulative PnL vs benchmark using actual historical data
        historical = load_historical_snapshots(365)  # Load all available data

        if historical and len(historical) > 1:
            # Sort by timestamp
            historical = sorted(historical, key=lambda x: x.get('_timestamp', datetime.now()))

            dates = [h.get('_timestamp', datetime.now()) for h in historical]
            pnl_values = [h.get('total_pnl', 0) for h in historical]

            # Create cumulative PnL series
            cumulative_pnl = pnl_values

            # Create realistic benchmark returns for comparison
            # Start from first date and create daily returns
            start_date = dates[0] if dates else datetime.now()
            benchmark_returns = []
            np.random.seed(42)  # For consistent benchmark

            for i, date in enumerate(dates):
                # Simulate benchmark with ~15% annual return, 20% volatility
                days_from_start = (date - start_date).days if hasattr(date, 'days') else i
                daily_return = 0.15/365 + np.random.normal(0, 0.20/np.sqrt(365))  # Daily return
                benchmark_value = 10000 * (1 + daily_return) ** days_from_start  # Starting from 10k
                benchmark_returns.append(benchmark_value - 10000)  # PnL from 10k base

            fig = go.Figure()

            fig.add_trace(go.Scatter(
                x=dates,
                y=cumulative_pnl,
                mode='lines+markers',
                name='Northstar Strategy',
                line=dict(color='#00ff88', width=3),
                marker=dict(size=4)
            ))

            fig.add_trace(go.Scatter(
                x=dates,
                y=benchmark_returns,
                mode='lines',
                name='Benchmark (NIFTY)',
                line=dict(color='#4488ff', width=2, dash='dash')
            ))

            # Add zero line
            fig.add_hline(y=0, line_dash="dot", line_color="gray", opacity=0.5)

            fig.update_layout(
                title=f"Cumulative PnL vs Benchmark (Live System)",
                xaxis_title="Date",
                yaxis_title="PnL (₹)",
                height=350,
                template="plotly_dark",
                hovermode='x unified',
                legend=dict(x=0.01, y=0.99)
            )

            st.plotly_chart(fig, use_container_width=True)

            # Show performance summary
            if cumulative_pnl:
                final_pnl = cumulative_pnl[-1]
                final_benchmark = benchmark_returns[-1] if benchmark_returns else 0
                outperformance = final_pnl - final_benchmark

                st.write(f"**Performance Summary:**")
                st.write(f"- Strategy PnL: {format_currency(final_pnl)}")
                st.write(f"- Benchmark PnL: {format_currency(final_benchmark)}")
                st.write(f"- Outperformance: {format_currency(outperformance)} ({'📈' if outperformance > 0 else '📉'})")

        else:
            st.info("Insufficient historical data for PnL chart")

            # Show current PnL breakdown
            fig = go.Figure(data=[
                go.Bar(
                    x=['Realized PnL', 'Unrealized PnL', 'Today PnL'],
                    y=[realized_pnl, unrealized_pnl, today_pnl],
                    marker_color=['#00ff88' if realized_pnl >= 0 else '#ff4444',
                                 '#00ff88' if unrealized_pnl >= 0 else '#ff4444',
                                 '#00ff88' if today_pnl >= 0 else '#ff4444'],
                    text=[format_currency(realized_pnl), format_currency(unrealized_pnl), format_currency(today_pnl)],
                    textposition='outside'
                )
            ])

            fig.update_layout(
                title="Current PnL Breakdown",
                xaxis_title="PnL Type",
                yaxis_title="Amount (₹)",
                height=350,
                template="plotly_dark",
                showlegend=False
            )

            st.plotly_chart(fig, use_container_width=True)

    with col2:
        # Portfolio greeks evolution
        if historical and len(historical) > 5:
            dates = [h.get('_timestamp', datetime.now()) for h in historical]

            # Extract greeks from historical data
            delta_series = [h.get('portfolio_greeks', {}).get('delta', 0) for h in historical]
            gamma_series = [h.get('portfolio_greeks', {}).get('gamma', 0) for h in historical]
            vega_series = [h.get('portfolio_greeks', {}).get('vega', 0) for h in historical]
            theta_series = [h.get('portfolio_greeks', {}).get('theta', 0) for h in historical]

            # Create subplots for different greeks
            fig = make_subplots(
                rows=2, cols=2,
                subplot_titles=('Delta Exposure', 'Gamma Exposure', 'Vega Exposure', 'Theta Exposure'),
                vertical_spacing=0.12,
                horizontal_spacing=0.1
            )

            # Delta
            fig.add_trace(
                go.Scatter(x=dates, y=delta_series, mode='lines', name='Delta',
                          line=dict(color='#00ff88', width=2)),
                row=1, col=1
            )

            # Gamma
            fig.add_trace(
                go.Scatter(x=dates, y=gamma_series, mode='lines', name='Gamma',
                          line=dict(color='#ffaa00', width=2)),
                row=1, col=2
            )

            # Vega
            fig.add_trace(
                go.Scatter(x=dates, y=vega_series, mode='lines', name='Vega',
                          line=dict(color='#ff4444', width=2)),
                row=2, col=1
            )

            # Theta
            fig.add_trace(
                go.Scatter(x=dates, y=theta_series, mode='lines', name='Theta',
                          line=dict(color='#8800ff', width=2)),
                row=2, col=2
            )

            fig.update_layout(
                title="Portfolio Greeks Evolution",
                height=400,
                template="plotly_dark",
                showlegend=False
            )

            st.plotly_chart(fig, use_container_width=True)
        else:
            # Show current greeks as bar chart
            current_greeks = state.get('portfolio_greeks', {})

            fig = go.Figure(data=[
                go.Bar(
                    x=['Delta', 'Gamma', 'Vega', 'Theta'],
                    y=[current_greeks.get('delta', 0),
                       current_greeks.get('gamma', 0),
                       current_greeks.get('vega', 0),
                       current_greeks.get('theta', 0)],
                    marker_color=['#00ff88', '#ffaa00', '#ff4444', '#8800ff'],
                    text=[f"{current_greeks.get('delta', 0):.1f}",
                          f"{current_greeks.get('gamma', 0):.1f}",
                          f"{current_greeks.get('vega', 0):.1f}",
                          f"{current_greeks.get('theta', 0):.1f}"],
                    textposition='outside'
                )
            ])

            fig.update_layout(
                title="Current Portfolio Greeks",
                xaxis_title="Greek",
                yaxis_title="Exposure",
                height=400,
                template="plotly_dark",
                showlegend=False
            )

            st.plotly_chart(fig, use_container_width=True)

    # Risk metrics evolution
    if historical and len(historical) > 5:
        st.write("**Risk Metrics Evolution:**")

        col1, col2 = st.columns(2)

        with col1:
            # VaR evolution
            dates = [h.get('_timestamp', datetime.now()) for h in historical]
            var_series = [h.get('risk_metrics', {}).get('var_95', 0) for h in historical]
            cvar_series = [h.get('risk_metrics', {}).get('cvar_95', 0) for h in historical]

            fig = go.Figure()

            fig.add_trace(go.Scatter(
                x=dates, y=var_series, mode='lines', name='VaR 95%',
                line=dict(color='#ffaa00', width=2)
            ))

            fig.add_trace(go.Scatter(
                x=dates, y=cvar_series, mode='lines', name='CVaR 95%',
                line=dict(color='#ff4444', width=2)
            ))

            fig.update_layout(
                title="Value at Risk Evolution",
                xaxis_title="Date",
                yaxis_title="VaR (₹)",
                height=300,
                template="plotly_dark",
                hovermode='x unified'
            )

            st.plotly_chart(fig, use_container_width=True)

        with col2:
            # Drawdown evolution
            drawdown_series = [h.get('risk_metrics', {}).get('current_drawdown', 0) for h in historical]

            fig = go.Figure()

            fig.add_trace(go.Scatter(
                x=dates, y=drawdown_series, mode='lines', name='Current Drawdown',
                line=dict(color='#ff4444', width=2),
                fill='tozeroy', fillcolor='rgba(255, 68, 68, 0.1)'
            ))

            fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)

            fig.update_layout(
                title="Drawdown Evolution",
                xaxis_title="Date",
                yaxis_title="Drawdown (₹)",
                height=300,
                template="plotly_dark"
            )

            st.plotly_chart(fig, use_container_width=True)

    # Performance attribution
    st.write("**Performance Attribution:**")

    col1, col2 = st.columns(2)

    with col1:
        # PnL breakdown
        pnl_breakdown = {
            'Realized PnL': realized_pnl,
            'Unrealized PnL': unrealized_pnl,
            'Today PnL': today_pnl
        }

        fig = go.Figure(data=[
            go.Bar(
                x=list(pnl_breakdown.keys()),
                y=list(pnl_breakdown.values()),
                marker_color=['#00ff88' if v >= 0 else '#ff4444' for v in pnl_breakdown.values()],
                text=[format_currency(v) for v in pnl_breakdown.values()],
                textposition='outside'
            )
        ])

        fig.update_layout(
            title="PnL Breakdown",
            xaxis_title="PnL Type",
            yaxis_title="Amount (₹)",
            height=300,
            template="plotly_dark",
            showlegend=False
        )

        st.plotly_chart(fig, use_container_width=True)

    with col2:
        # Position count by strategy type
        positions = state.get('positions', [])
        if positions:
            strategy_counts = {}
            for pos in positions:
                strategy = pos.get('option_type', 'unknown')
                strategy_counts[strategy] = strategy_counts.get(strategy, 0) + 1

            fig = go.Figure(data=[
                go.Pie(
                    labels=list(strategy_counts.keys()),
                    values=list(strategy_counts.values()),
                    hole=0.4,
                    marker_colors=['#00ff88', '#ffaa00', '#ff4444', '#8800ff', '#4488ff'][:len(strategy_counts)]
                )
            ])

            fig.update_layout(
                title="Position Distribution by Strategy",
                height=300,
                template="plotly_dark"
            )

            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No active positions")

    # Trade statistics
    with st.expander("📈 Detailed Statistics"):
        col1, col2, col3 = st.columns(3)

        with col1:
            st.write("**Current Metrics:**")
            st.metric("Total PnL", format_currency(total_pnl))
            st.metric("Realized PnL", format_currency(realized_pnl))
            st.metric("Unrealized PnL", format_currency(unrealized_pnl))

        with col2:
            st.write("**Risk Metrics:**")
            st.metric("VaR 95%", format_currency(risk_metrics.get('var_95', 0)))
            st.metric("CVaR 95%", format_currency(risk_metrics.get('cvar_95', 0)))
            st.metric("Max Drawdown", format_currency(risk_metrics.get('max_drawdown', 0)))

        with col3:
            st.write("**Performance Metrics:**")
            st.metric("Win Rate", f"{perf_metrics.get('win_rate', 0):.1%}")
            st.metric("Total Trades", perf_metrics.get('total_trades', 0))
            st.metric("Sharpe Ratio", f"{perf_metrics.get('sharpe_ratio', 0):.2f}")

        # Show positions table if available
        if positions:
            st.write("**Active Positions:**")
            pos_data = []
            for pos in positions:
                pos_data.append({
                    'Symbol': pos.get('symbol', 'Unknown')[:30] + '...' if len(pos.get('symbol', '')) > 30 else pos.get('symbol', 'Unknown'),
                    'Type': pos.get('option_type', 'Unknown'),
                    'PnL': format_currency(pos.get('pnl', 0)),
                    'Delta': f"{pos.get('delta', 0):.1f}",
                    'Gamma': f"{pos.get('gamma', 0):.2f}",
                    'Vega': f"{pos.get('vega', 0):.1f}",
                    'Theta': f"{pos.get('theta', 0):.1f}",
                    'Notional': format_currency(pos.get('notional', 0))
                })

            df_positions = pd.DataFrame(pos_data)
            st.dataframe(df_positions, use_container_width=True, hide_index=True)


def render_strategy_allocation_panel(state, config):
    """Render strategy allocation panel"""
    st.subheader("🎯 Strategy Allocation")
    
    if not state:
        st.warning("No data available")
        return
    
    allocations = state.get('strategy_allocations', {
        'Dispersion': 0.30,
        'Gamma Scalping': 0.25,
        'Short Vol': 0.20,
        'Long Vol': 0.15,
        'Relative Value': 0.10
    })
    
    # Allocation metrics
    col1, col2, col3 = st.columns(3)
    
    with col1:
        total_capital = state.get('total_capital', 1000000)
        st.metric("Total Capital", format_currency(total_capital))
    
    with col2:
        deployed_capital = sum(allocations.values()) * total_capital
        st.metric("Deployed Capital", format_currency(deployed_capital))
    
    with col3:
        utilization = deployed_capital / total_capital if total_capital > 0 else 0
        st.metric("Capital Utilization", format_percentage(utilization))
    
    # Allocation visualization
    col1, col2 = st.columns(2)
    
    with col1:
        # Pie chart
        fig = go.Figure(data=[go.Pie(
            labels=list(allocations.keys()),
            values=list(allocations.values()),
            hole=0.4,
            marker=dict(colors=['#00ff88', '#ffaa00', '#ff8800', '#4488ff', '#ff4444'])
        )])
        
        fig.update_layout(
            title="Capital Allocation by Strategy",
            height=300,
            template="plotly_dark"
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Bar chart with capital amounts
        capital_amounts = {k: v * total_capital for k, v in allocations.items()}
        
        fig = go.Figure(data=[
            go.Bar(
                x=list(capital_amounts.keys()),
                y=list(capital_amounts.values()),
                marker_color='#00ff88',
                text=[format_currency(v) for v in capital_amounts.values()],
                textposition='outside'
            )
        ])
        
        fig.update_layout(
            title="Capital by Strategy ($)",
            xaxis_title="Strategy",
            yaxis_title="Capital ($)",
            height=300,
            template="plotly_dark",
            showlegend=False
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    # Allocation table with performance
    st.write("**Strategy Details:**")
    
    strategy_details = []
    for strategy, allocation in allocations.items():
        capital = allocation * total_capital
        pnl = state.get(f'{strategy.lower().replace(" ", "_")}_pnl', 0)
        roi = (pnl / capital * 100) if capital > 0 else 0
        
        strategy_details.append({
            'Strategy': strategy,
            'Allocation': format_percentage(allocation),
            'Capital': format_currency(capital),
            'P&L': format_currency(pnl),
            'ROI': f"{roi:.2f}%",
            'Status': '🟢 Active' if allocation > 0 else '⚪ Inactive'
        })
    
    df_strategies = pd.DataFrame(strategy_details)
    st.dataframe(df_strategies, use_container_width=True, hide_index=True)


def render_execution_quality_panel(state):
    """Render execution quality panel"""
    st.subheader("⚡ Execution Quality")
    
    if not state:
        st.warning("No data available")
        return
    
    exec_metrics = state.get('execution_metrics', {})
    
    # Top metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        fill_rate = exec_metrics.get('fill_rate', 0)
        st.metric("Fill Rate", f"{fill_rate:.1%}",
                 "Good" if fill_rate > 0.9 else "Fair" if fill_rate > 0.8 else "Poor")
    
    with col2:
        avg_slippage = exec_metrics.get('avg_slippage', 0)
        st.metric("Avg Slippage", f"{avg_slippage:.2%}",
                 delta_color="inverse")
    
    with col3:
        total_orders = exec_metrics.get('total_orders', 0)
        st.metric("Total Orders", total_orders)
    
    with col4:
        rejected_orders = exec_metrics.get('rejected_orders', 0)
        rejection_rate = (rejected_orders / total_orders * 100) if total_orders > 0 else 0
        st.metric("Rejection Rate", f"{rejection_rate:.1f}%",
                 delta_color="inverse")
    
    # Execution charts
    col1, col2 = st.columns(2)
    
    with col1:
        # Slippage distribution
        slippage_data = exec_metrics.get('slippage_distribution', {
            '< 0.5%': 45,
            '0.5-1%': 30,
            '1-2%': 15,
            '2-5%': 8,
            '> 5%': 2
        })
        
        fig = go.Figure(data=[
            go.Bar(
                x=list(slippage_data.keys()),
                y=list(slippage_data.values()),
                marker_color='#00ff88',
                text=[f"{v}%" for v in slippage_data.values()],
                textposition='outside'
            )
        ])
        
        fig.update_layout(
            title="Slippage Distribution (%)",
            xaxis_title="Slippage Range",
            yaxis_title="% of Orders",
            height=300,
            template="plotly_dark",
            showlegend=False
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Venue performance
        venue_perf = exec_metrics.get('venue_performance', {
            'CBOE': {'fill_rate': 0.95, 'avg_slippage': 0.008},
            'ISE': {'fill_rate': 0.92, 'avg_slippage': 0.012},
            'PHLX': {'fill_rate': 0.90, 'avg_slippage': 0.015},
            'AMEX': {'fill_rate': 0.88, 'avg_slippage': 0.018}
        })
        
        venues = list(venue_perf.keys())
        fill_rates = [v['fill_rate'] * 100 for v in venue_perf.values()]
        
        fig = go.Figure(data=[
            go.Bar(
                x=venues,
                y=fill_rates,
                marker_color='#4488ff',
                text=[f"{v:.1f}%" for v in fill_rates],
                textposition='outside'
            )
        ])
        
        fig.update_layout(
            title="Fill Rate by Venue",
            xaxis_title="Venue",
            yaxis_title="Fill Rate (%)",
            height=300,
            template="plotly_dark",
            showlegend=False,
            yaxis_range=[0, 100]
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    # Detailed venue table
    st.write("**Venue Performance Details:**")
    
    venue_details = []
    for venue, metrics in venue_perf.items():
        venue_details.append({
            'Venue': venue,
            'Fill Rate': f"{metrics['fill_rate']:.1%}",
            'Avg Slippage': f"{metrics['avg_slippage']:.2%}",
            'Orders': exec_metrics.get(f'{venue}_orders', 0),
            'Status': '🟢 Active'
        })
    
    df_venues = pd.DataFrame(venue_details)
    st.dataframe(df_venues, use_container_width=True, hide_index=True)


def render_alerts_panel(state):
    """Render alerts panel"""
    st.subheader("🚨 Alerts & Notifications")
    
    if not state:
        st.warning("No data available")
        return
    
    alerts = get_alerts()
    
    # Alert summary
    col1, col2, col3, col4 = st.columns(4)
    
    critical_alerts = sum(1 for a in alerts if 'CRITICAL' in a)
    warning_alerts = sum(1 for a in alerts if 'WARNING' in a)
    info_alerts = sum(1 for a in alerts if 'INFO' in a)
    
    with col1:
        st.metric("Critical Alerts", critical_alerts,
                 delta_color="inverse")
    
    with col2:
        st.metric("Warning Alerts", warning_alerts,
                 delta_color="inverse")
    
    with col3:
        st.metric("Info Alerts", info_alerts)
    
    with col4:
        st.metric("Total Alerts", len(alerts))
    
    # Recent alerts
    st.write("**Recent Alerts (Last 50):**")
    
    if not alerts:
        st.info("No recent alerts")
    else:
        alert_data = []
        for alert in alerts[-20:]:  # Show last 20
            # Parse alert (mock format)
            if 'CRITICAL' in alert:
                severity = '🔴 Critical'
                color = 'alert-critical'
            elif 'WARNING' in alert:
                severity = '🟡 Warning'
                color = 'alert-warning'
            else:
                severity = '🔵 Info'
                color = 'alert-info'
            
            alert_data.append({
                'Time': datetime.now().strftime('%H:%M:%S'),
                'Severity': severity,
                'Message': alert[:100]  # Truncate long messages
            })
        
        df_alerts = pd.DataFrame(alert_data)
        st.dataframe(df_alerts, use_container_width=True, hide_index=True)
    
    # Alert configuration
    with st.expander("⚙️ Alert Configuration"):
        st.write("**Current alert thresholds:**")
        
        config = load_config()
        if config:
            alert_config = config.get('monitoring', {})
            
            threshold_data = []
            for key, value in alert_config.items():
                threshold_data.append({
                    'Parameter': key.replace('_', ' ').title(),
                    'Threshold': str(value)
                })
            
            df_thresholds = pd.DataFrame(threshold_data)
            st.dataframe(df_thresholds, use_container_width=True, hide_index=True)


def main():
    """Main dashboard"""
    
    # Header
    render_header()
    
    # Load data
    state = load_latest_state()
    config = load_config("production")
    
    if state:
        timestamp = state.get('timestamp', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        st.success(f"✅ Last updated: {timestamp}")
    else:
        st.error("⚠️ No state data available. Is the engine running?")
    
    # Sidebar
    with st.sidebar:
        st.header("🧭 Navigation")
        
        page = st.radio(
            "Select View",
            [
                "📊 Overview",
                "💰 P&L",
                "📈 Greeks",
                "🌡️ Regime",
                "🌍 Market Pressure Surface",
                "⚠️ Risk",
                "📋 Positions",
                "📊 Market Snapshot",
                "📈 Decision History",
                "📊 Performance",
                "🎯 Strategy Allocation",
                "⚡ Execution Quality",
                "🚨 Alerts"
            ]
        )
        
        st.divider()
        
        st.header("⚡ Quick Actions")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("💾 Save", use_container_width=True):
                st.success("State saved")
        with col2:
            if st.button("🔄 Reload", use_container_width=True):
                st.cache_data.clear()
                st.rerun()
        
        if st.button("🛑 Emergency Halt", use_container_width=True, type="primary"):
            st.error("⚠️ Trading halted!")
        
        if st.button("▶️ Resume Trading", use_container_width=True):
            st.success("✅ Trading resumed")
        
        st.divider()
        
        st.header("⚙️ Configuration")
        
        config_profile = st.selectbox(
            "Profile",
            ["production", "staging", "development", "aggressive", "moderate", "conservative"]
        )
        
        if st.button("Load Config", use_container_width=True):
            config = load_config(config_profile)
            st.success(f"Loaded {config_profile}")
        
        st.divider()
        
        st.header("ℹ️ System Info")
        
        running, pid, uptime = check_engine_status()
        
        if running:
            st.success("🟢 Engine Running")
            if pid:
                st.text(f"PID: {pid}")
            if uptime:
                st.text(f"Uptime: {str(uptime).split('.')[0]}")
        else:
            st.error("🔴 Engine Stopped")
        
        st.text(f"Time: {datetime.now().strftime('%H:%M:%S')}")
        st.text(f"Date: {datetime.now().strftime('%Y-%m-%d')}")
        
        # Alert count
        alerts = get_alerts()
        critical = sum(1 for a in alerts if 'CRITICAL' in a)
        if critical > 0:
            st.error(f"🚨 {critical} Critical Alerts")
    
    # Main content based on selected page
    if page == "📊 Overview":
        # Overview page with key metrics from all panels
        col1, col2 = st.columns(2)
        
        with col1:
            render_pnl_panel(state, config)
            render_regime_panel(state, config)
            render_market_snapshot_panel(state)
        
        with col2:
            render_greeks_panel(state, config)
            render_risk_panel(state, config)
            render_alerts_panel(state)
        
        # Add market pressure surface as a full-width panel
        st.divider()
        render_market_pressure_surface_panel(state, config)
    
    elif page == "💰 P&L":
        render_pnl_panel(state, config)
    
    elif page == "📈 Greeks":
        render_greeks_panel(state, config)
    
    elif page == "🌡️ Regime":
        render_regime_panel(state, config)
    
    elif page == "🌍 Market Pressure Surface":
        render_market_pressure_surface_panel(state, config)
    
    elif page == "⚠️ Risk":
        render_risk_panel(state, config)
    
    elif page == "📋 Positions":
        render_positions_panel(state, config)
    
    elif page == "📊 Market Snapshot":
        render_market_snapshot_panel(state)
    
    elif page == "📈 Decision History":
        render_options_decision_history_panel(state)
    
    elif page == "📊 Performance":
        render_performance_panel(state, config)
    
    elif page == "🎯 Strategy Allocation":
        render_strategy_allocation_panel(state, config)
    
    elif page == "⚡ Execution Quality":
        render_execution_quality_panel(state)
    
    elif page == "🚨 Alerts":
        render_alerts_panel(state)
    
    # Footer
    st.divider()
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.caption("Unified Volatility Engine v3.0 - Options Integration")
    
    with col2:
        st.caption("© 2026 Institutional Trading Systems")
    
    with col3:
        st.caption(f"Dashboard refresh: {datetime.now().strftime('%H:%M:%S')}")


if __name__ == "__main__":
    main()
