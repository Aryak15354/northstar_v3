#!/usr/bin/env python3
"""
🌟 INTEGRATED SHADOW TRADING DASHBOARD
Professional dashboard integrating all Northstar V3 features with shadow trading

Features:
- Real-time market intelligence and regime analysis
- Live shadow trading performance vs NIFTY
- Capital allocation and portfolio construction
- System health monitoring and alerts
- Professional institutional-grade interface
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# Page configuration
st.set_page_config(
    page_title="Northstar V3 - Integrated Shadow Trading Dashboard",
    page_icon="🌟",
    layout="wide",
    initial_sidebar_state="expanded"
)

class IntegratedShadowDashboard:
    """Integrated dashboard for Northstar V3 with shadow trading"""
    
    def __init__(self):
        self.base_path = Path("data/live/shadow_trading")
        self.data_path = Path("data/processed")
        self.intelligence_path = Path("data/intelligence")
        
        # Initialize session state
        if 'last_refresh' not in st.session_state:
            st.session_state.last_refresh = datetime.now()
        if 'auto_refresh' not in st.session_state:
            st.session_state.auto_refresh = True
            
    def load_shadow_trading_data(self):
        """Load shadow trading performance data"""
        try:
            # Load trading state
            state_file = self.base_path / "trading_state.json"
            if state_file.exists():
                with open(state_file, 'r') as f:
                    trading_state = json.load(f)
            else:
                trading_state = {}
                
            # Load recent daily logs
            current_month = datetime.now().strftime('%Y%m')
            log_file = self.base_path / f"daily_log_{current_month}.json"
            
            if log_file.exists():
                with open(log_file, 'r') as f:
                    daily_logs = json.load(f)
            else:
                daily_logs = []
                
            return {
                'trading_state': trading_state,
                'daily_logs': daily_logs,
                'status': 'active' if daily_logs else 'inactive'
            }
            
        except Exception as e:
            st.error(f"Error loading shadow trading data: {e}")
            return {'trading_state': {}, 'daily_logs': [], 'status': 'error'}
    
    def load_market_intelligence(self):
        """Load current market intelligence"""
        try:
            intelligence_data = {}
            
            # Load unified intelligence
            unified_file = self.data_path / "unified_intelligence_state.json"
            if unified_file.exists():
                with open(unified_file, 'r') as f:
                    intelligence_data['unified'] = json.load(f)
                    
            # Load market state
            market_file = self.data_path / "market_state.parquet"
            if market_file.exists():
                market_df = pd.read_parquet(market_file)
                intelligence_data['market_state'] = market_df.iloc[-1].to_dict() if not market_df.empty else {}
                
            # Load capital allocations
            allocation_file = self.data_path / "capital_allocations.json"
            if allocation_file.exists():
                with open(allocation_file, 'r') as f:
                    intelligence_data['allocations'] = json.load(f)
                    
            # Load portfolio analytics
            portfolio_file = self.data_path / "portfolio_analytics.json"
            if portfolio_file.exists():
                with open(portfolio_file, 'r') as f:
                    intelligence_data['portfolio'] = json.load(f)
                    
            return intelligence_data
            
        except Exception as e:
            st.error(f"Error loading market intelligence: {e}")
            return {}
    
    def load_system_health(self):
        """Load system health metrics"""
        try:
            health_data = {}
            
            # Load pulse state
            pulse_file = self.data_path / "pulse_state.json"
            if pulse_file.exists():
                with open(pulse_file, 'r') as f:
                    health_data['pulse'] = json.load(f)
                    
            # Load system stress
            stress_file = self.data_path / "system_stress.json"
            if stress_file.exists():
                with open(stress_file, 'r') as f:
                    health_data['stress'] = json.load(f)
                    
            # Load NO_EDGE state
            no_edge_file = self.intelligence_path / "no_edge_state.parquet"
            if no_edge_file.exists():
                no_edge_df = pd.read_parquet(no_edge_file)
                health_data['no_edge'] = no_edge_df.iloc[-1].to_dict() if not no_edge_df.empty else {}
                
            return health_data
            
        except Exception as e:
            st.error(f"Error loading system health: {e}")
            return {}
    
    def create_performance_chart(self, daily_logs):
        """Create performance comparison chart"""
        if not daily_logs:
            return go.Figure()
            
        dates = []
        northstar_returns = []
        nifty_returns = []
        northstar_cumulative = []
        nifty_cumulative = []
        
        cumulative_ns = 1.0
        cumulative_nifty = 1.0
        
        for log in daily_logs:
            dates.append(log['date'])
            
            pnl = log.get('pnl', {})
            nifty = log.get('nifty_performance', {})
            
            daily_return_ns = pnl.get('total_pnl_pct', 0.0) / 100
            daily_return_nifty = nifty.get('daily_return', 0.0) / 100
            
            northstar_returns.append(daily_return_ns * 100)
            nifty_returns.append(daily_return_nifty * 100)
            
            cumulative_ns *= (1 + daily_return_ns)
            cumulative_nifty *= (1 + daily_return_nifty)
            
            northstar_cumulative.append((cumulative_ns - 1) * 100)
            nifty_cumulative.append((cumulative_nifty - 1) * 100)
        
        fig = make_subplots(
            rows=2, cols=1,
            subplot_titles=('Cumulative Returns', 'Daily Returns'),
            vertical_spacing=0.1
        )
        
        # Cumulative returns
        fig.add_trace(
            go.Scatter(
                x=dates, y=northstar_cumulative,
                name='Northstar', line=dict(color='#2E86AB', width=3),
                hovertemplate='<b>Northstar</b><br>Date: %{x}<br>Return: %{y:.2f}%<extra></extra>'
            ),
            row=1, col=1
        )
        
        fig.add_trace(
            go.Scatter(
                x=dates, y=nifty_cumulative,
                name='NIFTY 50', line=dict(color='#A23B72', width=2),
                hovertemplate='<b>NIFTY 50</b><br>Date: %{x}<br>Return: %{y:.2f}%<extra></extra>'
            ),
            row=1, col=1
        )
        
        # Daily returns
        colors = ['#2E86AB' if r >= 0 else '#F18F01' for r in northstar_returns]
        fig.add_trace(
            go.Bar(
                x=dates, y=northstar_returns,
                name='Daily Returns', marker_color=colors,
                hovertemplate='<b>Daily Return</b><br>Date: %{x}<br>Return: %{y:.2f}%<extra></extra>'
            ),
            row=2, col=1
        )
        
        fig.update_layout(
            height=600,
            showlegend=True,
            title_text="Shadow Trading Performance",
            title_x=0.5
        )
        
        fig.update_xaxes(title_text="Date", row=2, col=1)
        fig.update_yaxes(title_text="Cumulative Return (%)", row=1, col=1)
        fig.update_yaxes(title_text="Daily Return (%)", row=2, col=1)
        
        return fig
    
    def create_allocation_chart(self, allocations):
        """Create capital allocation pie chart"""
        if not allocations or 'allocations' not in allocations:
            return go.Figure()
            
        strategies = list(allocations['allocations'].keys())
        weights = list(allocations['allocations'].values())
        
        # Add cash allocation
        total_allocated = sum(weights)
        cash_allocation = max(0, 1 - total_allocated)
        
        if cash_allocation > 0:
            strategies.append('Cash')
            weights.append(cash_allocation)
        
        fig = go.Figure(data=[
            go.Pie(
                labels=strategies,
                values=weights,
                hole=0.4,
                textinfo='label+percent',
                textposition='outside',
                marker=dict(
                    colors=px.colors.qualitative.Set3,
                    line=dict(color='#FFFFFF', width=2)
                )
            )
        ])
        
        fig.update_layout(
            title_text="Capital Allocation",
            title_x=0.5,
            height=400
        )
        
        return fig
    
    def create_regime_gauge(self, market_state):
        """Create market regime gauge"""
        if not market_state:
            return go.Figure()
            
        regime = market_state.get('regime', 'neutral')
        risk_on_prob = market_state.get('risk_on_probability', 0.5) * 100
        
        fig = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=risk_on_prob,
            domain={'x': [0, 1], 'y': [0, 1]},
            title={'text': f"Risk-On Probability<br><span style='font-size:0.8em;color:gray'>Regime: {regime.title()}</span>"},
            delta={'reference': 50},
            gauge={
                'axis': {'range': [None, 100]},
                'bar': {'color': "#2E86AB"},
                'steps': [
                    {'range': [0, 30], 'color': "#F18F01"},
                    {'range': [30, 70], 'color': "#FFC107"},
                    {'range': [70, 100], 'color': "#28A745"}
                ],
                'threshold': {
                    'line': {'color': "red", 'width': 4},
                    'thickness': 0.75,
                    'value': 90
                }
            }
        ))
        
        fig.update_layout(height=300)
        return fig
    
    def create_system_health_indicators(self, health_data):
        """Create system health indicator cards"""
        pulse = health_data.get('pulse', {})
        stress = health_data.get('stress', {})
        no_edge = health_data.get('no_edge', {})
        
        # Pulse intensity
        pulse_intensity = pulse.get('pulse_intensity', 0)
        pulse_color = "#28A745" if pulse_intensity < 3 else "#FFC107" if pulse_intensity < 5 else "#DC3545"
        
        # System stress
        system_stress = stress.get('system_stress', 0)
        stress_color = "#28A745" if system_stress < 0.3 else "#FFC107" if system_stress < 0.7 else "#DC3545"
        
        # NO_EDGE state
        no_edge_state = no_edge.get('state', 'NORMAL')
        no_edge_color = "#28A745" if no_edge_state == 'NORMAL' else "#DC3545"
        
        return {
            'pulse': {'value': pulse_intensity, 'color': pulse_color, 'status': 'Normal' if pulse_intensity < 3 else 'Elevated'},
            'stress': {'value': system_stress, 'color': stress_color, 'status': 'Low' if system_stress < 0.3 else 'High'},
            'no_edge': {'value': no_edge_state, 'color': no_edge_color, 'status': no_edge_state}
        }
    
    def render_header(self):
        """Render dashboard header"""
        st.markdown("""
        <div style='text-align: center; padding: 1rem; background: linear-gradient(90deg, #2E86AB, #A23B72); color: white; border-radius: 10px; margin-bottom: 2rem;'>
            <h1 style='margin: 0; font-size: 2.5rem;'>🌟 Northstar V3</h1>
            <h3 style='margin: 0; font-weight: 300;'>Integrated Shadow Trading Dashboard</h3>
            <p style='margin: 0.5rem 0 0 0; opacity: 0.9;'>Real-time Intelligence • Live Performance • System Health</p>
        </div>
        """, unsafe_allow_html=True)
    
    def render_sidebar(self):
        """Render sidebar controls"""
        st.sidebar.markdown("## 🎛️ Dashboard Controls")
        
        # Auto-refresh toggle
        auto_refresh = st.sidebar.checkbox("Auto Refresh", value=st.session_state.auto_refresh)
        st.session_state.auto_refresh = auto_refresh
        
        # Manual refresh button
        if st.sidebar.button("🔄 Refresh Now"):
            st.session_state.last_refresh = datetime.now()
            st.rerun()
        
        # Time range selector
        st.sidebar.markdown("## 📅 Time Range")
        time_range = st.sidebar.selectbox(
            "Select Range",
            ["Last 7 Days", "Last 30 Days", "Last 90 Days", "All Time"]
        )
        
        # System controls
        st.sidebar.markdown("## ⚙️ System Controls")
        
        if st.sidebar.button("🚀 Run Manual Trading"):
            st.sidebar.info("Manual trading initiated...")
            # This would trigger manual trading
            
        if st.sidebar.button("📊 Generate Report"):
            st.sidebar.info("Generating monthly report...")
            # This would trigger report generation
            
        # System status
        st.sidebar.markdown("## 📡 System Status")
        st.sidebar.markdown(f"**Last Refresh:** {st.session_state.last_refresh.strftime('%H:%M:%S')}")
        
        return time_range
    
    def render_main_dashboard(self):
        """Render main dashboard content"""
        # Load all data
        shadow_data = self.load_shadow_trading_data()
        intelligence_data = self.load_market_intelligence()
        health_data = self.load_system_health()
        
        # Render sidebar
        time_range = self.render_sidebar()
        
        # Main content
        col1, col2, col3, col4 = st.columns(4)
        
        # Key metrics cards
        with col1:
            total_return = 0
            if shadow_data['daily_logs']:
                # Calculate total return
                cumulative = 1.0
                for log in shadow_data['daily_logs']:
                    pnl_pct = log.get('pnl', {}).get('total_pnl_pct', 0.0)
                    cumulative *= (1 + pnl_pct / 100)
                total_return = (cumulative - 1) * 100
                
            st.metric(
                label="📈 Total Return",
                value=f"{total_return:.2f}%",
                delta=f"vs NIFTY" if total_return != 0 else None
            )
        
        with col2:
            current_capital = shadow_data['trading_state'].get('current_capital', 10000000)
            st.metric(
                label="💰 Portfolio Value",
                value=f"₹{current_capital:,.0f}",
                delta=f"{(current_capital/10000000-1)*100:.1f}%" if current_capital != 10000000 else None
            )
        
        with col3:
            active_positions = len(shadow_data['trading_state'].get('positions', {}))
            st.metric(
                label="📊 Active Positions",
                value=str(active_positions),
                delta="positions"
            )
        
        with col4:
            trading_days = len(shadow_data['daily_logs'])
            st.metric(
                label="📅 Trading Days",
                value=str(trading_days),
                delta="days recorded"
            )
        
        # Performance section
        st.markdown("## 📈 Shadow Trading Performance")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            perf_chart = self.create_performance_chart(shadow_data['daily_logs'])
            st.plotly_chart(perf_chart, use_container_width=True)
        
        with col2:
            if intelligence_data.get('allocations'):
                alloc_chart = self.create_allocation_chart(intelligence_data['allocations'])
                st.plotly_chart(alloc_chart, use_container_width=True)
            else:
                st.info("No allocation data available")
        
        # Market Intelligence section
        st.markdown("## 🧠 Market Intelligence")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if intelligence_data.get('market_state'):
                regime_gauge = self.create_regime_gauge(intelligence_data['market_state'])
                st.plotly_chart(regime_gauge, use_container_width=True)
            else:
                st.info("No market state data")
        
        with col2:
            st.markdown("### 🎯 Current Intelligence")
            unified = intelligence_data.get('unified', {})
            if unified:
                st.markdown(f"**Stance:** {unified.get('stance', 'Unknown')}")
                st.markdown(f"**Conviction:** {unified.get('conviction', 0):.1f}%")
                st.markdown(f"**Target Exposure:** {unified.get('target_exposure', 0):.1f}%")
                st.markdown(f"**Risk Level:** {unified.get('risk_level', 'Unknown')}")
            else:
                st.info("No intelligence data")
        
        with col3:
            st.markdown("### 📊 Portfolio Analytics")
            portfolio = intelligence_data.get('portfolio', {})
            if portfolio:
                st.markdown(f"**Total Positions:** {portfolio.get('total_positions', 0)}")
                st.markdown(f"**Total Exposure:** {portfolio.get('total_exposure', 0):.1f}%")
                st.markdown(f"**Sector Diversity:** {portfolio.get('sector_count', 0)} sectors")
                st.markdown(f"**Risk Score:** {portfolio.get('risk_score', 0):.2f}")
            else:
                st.info("No portfolio data")
        
        # System Health section
        st.markdown("## 🏥 System Health")
        
        health_indicators = self.create_system_health_indicators(health_data)
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            pulse_data = health_indicators['pulse']
            st.markdown(f"""
            <div style='padding: 1rem; background: {pulse_data['color']}20; border-left: 4px solid {pulse_data['color']}; border-radius: 5px;'>
                <h4 style='margin: 0; color: {pulse_data['color']};'>💓 Market Pulse</h4>
                <p style='margin: 0.5rem 0 0 0; font-size: 1.2rem; font-weight: bold;'>{pulse_data['value']:.1f}</p>
                <p style='margin: 0; color: gray;'>{pulse_data['status']}</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            stress_data = health_indicators['stress']
            st.markdown(f"""
            <div style='padding: 1rem; background: {stress_data['color']}20; border-left: 4px solid {stress_data['color']}; border-radius: 5px;'>
                <h4 style='margin: 0; color: {stress_data['color']};'>⚡ System Stress</h4>
                <p style='margin: 0.5rem 0 0 0; font-size: 1.2rem; font-weight: bold;'>{stress_data['value']:.2f}</p>
                <p style='margin: 0; color: gray;'>{stress_data['status']}</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            no_edge_data = health_indicators['no_edge']
            st.markdown(f"""
            <div style='padding: 1rem; background: {no_edge_data['color']}20; border-left: 4px solid {no_edge_data['color']}; border-radius: 5px;'>
                <h4 style='margin: 0; color: {no_edge_data['color']};'>🚨 NO_EDGE State</h4>
                <p style='margin: 0.5rem 0 0 0; font-size: 1.2rem; font-weight: bold;'>{no_edge_data['value']}</p>
                <p style='margin: 0; color: gray;'>{no_edge_data['status']}</p>
            </div>
            """, unsafe_allow_html=True)
        
        # Recent Activity section
        st.markdown("## 📋 Recent Activity")
        
        if shadow_data['daily_logs']:
            recent_logs = shadow_data['daily_logs'][-5:]  # Last 5 days
            
            activity_data = []
            for log in recent_logs:
                pnl = log.get('pnl', {})
                nifty = log.get('nifty_performance', {})
                
                activity_data.append({
                    'Date': log['date'],
                    'Northstar Return': f"{pnl.get('total_pnl_pct', 0):.2f}%",
                    'NIFTY Return': f"{nifty.get('daily_return', 0):.2f}%",
                    'Outperformance': f"{pnl.get('total_pnl_pct', 0) - nifty.get('daily_return', 0):.2f}%",
                    'Trades': len(log.get('trades', [])),
                    'Portfolio Value': f"₹{pnl.get('portfolio_value', 0):,.0f}"
                })
            
            activity_df = pd.DataFrame(activity_data)
            st.dataframe(activity_df, use_container_width=True)
        else:
            st.info("No recent trading activity")
        
        # Auto-refresh
        if st.session_state.auto_refresh:
            import time
            time.sleep(30)  # Refresh every 30 seconds
            st.rerun()
    
    def run(self):
        """Run the dashboard"""
        self.render_header()
        self.render_main_dashboard()

def main():
    """Main dashboard execution"""
    dashboard = IntegratedShadowDashboard()
    dashboard.run()

if __name__ == "__main__":
    main()