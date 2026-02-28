#!/usr/bin/env python3
"""
Production Grade Dashboard

A clean, minimal dashboard focused on production grade features:
- Edge Half-Life Tracking
- Liquidity Risk Management
- Kill Switch Status
- Real data only (no mock/synthetic data)
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import json
from datetime import datetime, timedelta
from pathlib import Path
import warnings

# Suppress warnings
warnings.filterwarnings('ignore')

# Import production grade components
try:
    from src.dashboard.components.production_grade_panel import ProductionGradeDashboardPanel
    PRODUCTION_GRADE_AVAILABLE = True
except ImportError:
    PRODUCTION_GRADE_AVAILABLE = False

class ProductionGradeDashboard:
    """
    Production Grade Dashboard
    
    Clean, focused dashboard for production grade risk management features.
    """
    
    def __init__(self):
        self.data_dir = Path("data")
        
    def run(self):
        """Run the dashboard"""
        
        # Page configuration
        st.set_page_config(
            page_title="🧬 Production Grade Dashboard",
            layout="wide",
            initial_sidebar_state="expanded"
        )
        
        # Apply styling
        self.apply_styling()
        
        # Header
        self.render_header()
        
        # Main content
        if PRODUCTION_GRADE_AVAILABLE:
            self.render_production_content()
        else:
            self.render_setup_guide()
    
    def apply_styling(self):
        """Apply dashboard styling"""
        
        st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
        
        .stApp {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            font-family: 'Inter', sans-serif;
        }
        
        .main-header {
            background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%);
            color: white;
            padding: 2rem;
            border-radius: 12px;
            margin-bottom: 2rem;
            box-shadow: 0 8px 32px rgba(0,0,0,0.1);
        }
        
        .metric-card {
            background: white;
            border-radius: 8px;
            padding: 1rem;
            text-align: center;
            box-shadow: 0 2px 8px rgba(0,0,0,0.05);
            margin: 0.5rem 0;
        }
        
        .status-indicator {
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 8px;
        }
        
        .status-active { background-color: #16a34a; }
        .status-warning { background-color: #f59e0b; }
        .status-error { background-color: #ef4444; }
        </style>
        """, unsafe_allow_html=True)
    
    def render_header(self):
        """Render dashboard header"""
        
        st.markdown("""
        <div class="main-header">
            <h1 style="margin: 0; font-size: 2.5rem; font-weight: 800;">
                🧬 Production Grade Risk Management
            </h1>
            <p style="margin: 0.5rem 0 0 0; opacity: 0.9; font-size: 1.2rem;">
                Edge Half-Life Tracking • Liquidity-Aware Risk Controls • Real Data Only
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        # System status bar
        self.render_system_status()
    
    def render_system_status(self):
        """Render system status indicators"""
        
        col1, col2, col3, col4, col5 = st.columns(5)
        
        # Load production metrics for status
        prod_metrics = self.load_production_metrics()
        
        with col1:
            if prod_metrics:
                status = prod_metrics.get('overall_status', 'UNKNOWN')
                if status == 'HEALTHY':
                    status_class = "status-active"
                    status_color = "#16a34a"
                else:
                    status_class = "status-warning"
                    status_color = "#f59e0b"
            else:
                status = "NO DATA"
                status_class = "status-error"
                status_color = "#ef4444"
            
            st.markdown(f"""
            <div class="metric-card">
                <div class="status-indicator {status_class}"></div>
                <strong>System Status</strong><br>
                <span style="color: {status_color};">{status}</span>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            if prod_metrics:
                edge_enabled = prod_metrics.get('edge_integration_enabled', False)
                edge_status = "ENABLED" if edge_enabled else "DISABLED"
                edge_class = "status-active" if edge_enabled else "status-warning"
                edge_color = "#16a34a" if edge_enabled else "#f59e0b"
            else:
                edge_status = "NO DATA"
                edge_class = "status-error"
                edge_color = "#ef4444"
            
            st.markdown(f"""
            <div class="metric-card">
                <div class="status-indicator {edge_class}"></div>
                <strong>Edge Tracking</strong><br>
                <span style="color: {edge_color};">{edge_status}</span>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            if prod_metrics:
                liquidity_enabled = prod_metrics.get('liquidity_integration_enabled', False)
                liquidity_status = "ENABLED" if liquidity_enabled else "DISABLED"
                liquidity_class = "status-active" if liquidity_enabled else "status-warning"
                liquidity_color = "#16a34a" if liquidity_enabled else "#f59e0b"
            else:
                liquidity_status = "NO DATA"
                liquidity_class = "status-error"
                liquidity_color = "#ef4444"
            
            st.markdown(f"""
            <div class="metric-card">
                <div class="status-indicator {liquidity_class}"></div>
                <strong>Liquidity Risk</strong><br>
                <span style="color: {liquidity_color};">{liquidity_status}</span>
            </div>
            """, unsafe_allow_html=True)
        
        with col4:
            # Kill switch status
            kill_switch_data = self.load_kill_switch_data()
            if kill_switch_data:
                ks_status = kill_switch_data.get('status', 'UNKNOWN')
                if ks_status == 'ACTIVE':
                    ks_class = "status-active"
                    ks_color = "#16a34a"
                else:
                    ks_class = "status-warning"
                    ks_color = "#f59e0b"
            else:
                ks_status = "NO DATA"
                ks_class = "status-error"
                ks_color = "#ef4444"
            
            st.markdown(f"""
            <div class="metric-card">
                <div class="status-indicator {ks_class}"></div>
                <strong>Kill Switch</strong><br>
                <span style="color: {ks_color};">{ks_status}</span>
            </div>
            """, unsafe_allow_html=True)
        
        with col5:
            current_time = datetime.now().strftime('%H:%M:%S')
            st.markdown(f"""
            <div class="metric-card">
                <strong>Last Update</strong><br>
                <span style="color: #3b82f6;">{current_time}</span>
            </div>
            """, unsafe_allow_html=True)
    
    def render_production_content(self):
        """Render main production grade content"""
        
        # Initialize production panel
        production_panel = ProductionGradeDashboardPanel()
        
        # Render the panel
        production_panel.render_production_grade_panel()
        
        # Additional controls
        st.markdown("---")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("🔄 Refresh Data", type="primary"):
                st.success("Data refreshed!")
                st.rerun()
        
        with col2:
            if st.button("📊 Generate New Data", type="secondary"):
                # Run the data generation script
                import subprocess
                try:
                    subprocess.run(["python", "scripts/generate_dashboard_production_data.py"], check=True)
                    st.success("New production data generated!")
                    st.rerun()
                except subprocess.CalledProcessError:
                    st.error("Failed to generate new data")
        
        with col3:
            if st.button("📈 System Report", type="secondary"):
                self.show_system_report()
    
    def render_setup_guide(self):
        """Render setup guide when components are not available"""
        
        st.error("❌ Production Grade components not available")
        
        st.markdown("""
        ## Setup Required
        
        To use the Production Grade Dashboard, you need to:
        
        ### 1. Install Production Components
        ```bash
        # Ensure the production grade components are available
        python -c "from src.dashboard.components.production_grade_panel import ProductionGradeDashboardPanel"
        ```
        
        ### 2. Generate Production Data
        ```bash
        python scripts/generate_dashboard_production_data.py
        ```
        
        ### 3. Check Data Files
        The following files should exist:
        - `data/state/edge_metrics.json`
        - `data/risk/liquidity_metrics.json`
        - `data/risk/kill_switch_status.json`
        - `data/state/production_metrics.json`
        
        ### 4. Restart Dashboard
        ```bash
        streamlit run src/dashboard/production_grade_dashboard.py
        ```
        """)
    
    def show_system_report(self):
        """Show comprehensive system report"""
        
        st.markdown("### 📈 System Report")
        
        # Load all data
        edge_data = self.load_edge_data()
        liquidity_data = self.load_liquidity_data()
        kill_switch_data = self.load_kill_switch_data()
        prod_metrics = self.load_production_metrics()
        
        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            if edge_data:
                portfolio_edge = edge_data.get('portfolio_edge_score', 0)
                st.metric("Portfolio Edge Score", f"{portfolio_edge:.3f}")
            else:
                st.metric("Portfolio Edge Score", "No Data")
        
        with col2:
            if liquidity_data:
                portfolio_liquidity = liquidity_data.get('portfolio_liquidity_score', 0)
                st.metric("Portfolio Liquidity", f"{portfolio_liquidity:.2%}")
            else:
                st.metric("Portfolio Liquidity", "No Data")
        
        with col3:
            if prod_metrics:
                strategies_tracked = prod_metrics.get('edge_strategies_tracked', 0)
                st.metric("Strategies Tracked", strategies_tracked)
            else:
                st.metric("Strategies Tracked", "No Data")
        
        with col4:
            if prod_metrics:
                symbols_tracked = prod_metrics.get('liquidity_symbols_tracked', 0)
                st.metric("Symbols Tracked", symbols_tracked)
            else:
                st.metric("Symbols Tracked", "No Data")
        
        # Data availability status
        st.markdown("### 📊 Data Availability")
        
        data_status = {
            "Edge Health Data": "✅ Available" if edge_data else "❌ Missing",
            "Liquidity Data": "✅ Available" if liquidity_data else "❌ Missing",
            "Kill Switch Data": "✅ Available" if kill_switch_data else "❌ Missing",
            "Production Metrics": "✅ Available" if prod_metrics else "❌ Missing"
        }
        
        for item, status in data_status.items():
            st.markdown(f"- **{item}**: {status}")
    
    def load_edge_data(self):
        """Load edge health data"""
        edge_file = self.data_dir / "state" / "edge_metrics.json"
        if edge_file.exists():
            try:
                with open(edge_file, 'r') as f:
                    return json.load(f)
            except Exception:
                return None
        return None
    
    def load_liquidity_data(self):
        """Load liquidity data"""
        liquidity_file = self.data_dir / "risk" / "liquidity_metrics.json"
        if liquidity_file.exists():
            try:
                with open(liquidity_file, 'r') as f:
                    return json.load(f)
            except Exception:
                return None
        return None
    
    def load_kill_switch_data(self):
        """Load kill switch data"""
        kill_switch_file = self.data_dir / "risk" / "kill_switch_status.json"
        if kill_switch_file.exists():
            try:
                with open(kill_switch_file, 'r') as f:
                    return json.load(f)
            except Exception:
                return None
        return None
    
    def load_production_metrics(self):
        """Load production metrics"""
        prod_file = self.data_dir / "state" / "production_metrics.json"
        if prod_file.exists():
            try:
                with open(prod_file, 'r') as f:
                    return json.load(f)
            except Exception:
                return None
        return None

def main():
    """Main function"""
    dashboard = ProductionGradeDashboard()
    dashboard.run()

if __name__ == "__main__":
    main()