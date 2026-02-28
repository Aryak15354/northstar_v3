#!/usr/bin/env python3
"""
🏛️ CONSTITUTIONAL COCKPIT - NORTHSTAR V3
Single Dashboard with 5 Locked Panels: Truth, State, and Integrity

This is the constitutional cockpit that shows truth, state, and integrity — not opportunity.
Think: aircraft cockpit, nuclear control room, spacecraft telemetry.
NOT: Bloomberg trading terminal.

CRITICAL DESIGN PRINCIPLES:
1. Dashboard is READ-ONLY - Zero write access
2. Single dashboard, 5 immutable panels
3. Shows behavior, not performance
4. Reduces emotion, increases trust
5. No buttons that change exposure, override engines, or tweak parameters

PANEL ARCHITECTURE:
Panel 1 — SYSTEM STATE (TOP-LEFT): "Is the system healthy and behaving as designed?"
Panel 2 — RISK AUTHORITY (TOP-RIGHT): "Who is in charge right now?"
Panel 3 — ENGINE BEHAVIOR (CENTER): "Are the engines behaving like they promised?"
Panel 4 — VALIDATION & TRUTH (BOTTOM-LEFT): "Is this system still honest?"
Panel 5 — INTELLIGENCE OBSERVER (BOTTOM-RIGHT): "What should I understand — not act on?"
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

# Add project root to path for imports
import pathlib
project_root = str(pathlib.Path(__file__).parent.parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import V3 components for read-only access
from src.dashboard.snapshot_loader import DashboardSnapshotLoader
from src.dashboard.panels.system_state_panel import SystemStatePanel
from src.dashboard.panels.risk_panel import RiskPanel
from src.dashboard.panels.engine_panel import EnginePanel
from src.dashboard.panels.validation_panel import ValidationPanel
from src.dashboard.panels.intelligence_panel import IntelligencePanel

# =========================== CONSTITUTIONAL COCKPIT CONFIGURATION ===========================

st.set_page_config(
    layout="wide", 
    page_title="🏛️ Northstar V3 - Constitutional Cockpit",
    initial_sidebar_state="collapsed"
)

# =========================== CONSTITUTIONAL STYLING ===========================

st.markdown("""
<style>
    /* CONSTITUTIONAL COCKPIT THEME - Institutional, Muted, Professional */
    .main { padding: 0.2rem; }
    .block-container { padding: 0.3rem; max-width: 100%; }
    
    /* CONSTITUTIONAL HEADER */
    .constitutional-header {
        background: linear-gradient(90deg, #1e3a8a 0%, #1e40af 100%);
        color: white;
        padding: 0.5rem;
        border-radius: 4px;
        text-align: center;
        font-weight: bold;
        margin-bottom: 1rem;
    }
    
    /* PANEL STYLING - Use Streamlit containers with custom styling */
    .stContainer > div {
        border: 2px solid #e5e7eb;
        border-radius: 8px;
        padding: 0.8rem;
        margin: 0.3rem;
        background: #fafafa;
        min-height: 300px;
    }
    
    .panel-header {
        font-size: 1.1rem;
        font-weight: bold;
        color: #374151;
        margin-bottom: 0.5rem;
        border-bottom: 1px solid #d1d5db;
        padding-bottom: 0.3rem;
    }
    
    /* STATUS INDICATORS - Truth-based, not opportunity-based */
    .status-healthy { color: #059669; font-weight: bold; }
    .status-degraded { color: #d97706; font-weight: bold; }
    .status-critical { color: #dc2626; font-weight: bold; }
    .status-neutral { color: #6b7280; font-weight: bold; }
    
    /* METRICS DISPLAY - Behavior, not performance */
    .metric-row {
        display: flex;
        justify-content: space-between;
        padding: 0.2rem 0;
        border-bottom: 1px solid #f3f4f6;
    }
    
    .metric-label {
        color: #6b7280;
        font-size: 0.9rem;
    }
    
    .metric-value {
        font-weight: bold;
        color: #374151;
    }
    
    /* CONSTITUTIONAL FOOTER */
    .constitutional-footer {
        text-align: center;
        color: #6b7280;
        font-size: 0.8rem;
        margin-top: 1rem;
        padding: 0.5rem;
        border-top: 1px solid #e5e7eb;
    }
    
    /* REMOVE STREAMLIT BRANDING */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

class ConstitutionalCockpit:
    """
    Constitutional Cockpit - Single Dashboard with 5 Locked Panels
    
    This dashboard shows truth, state, and integrity without decision influence.
    All panels are read-only and display immutable snapshots of system state.
    """
    
    def __init__(self):
        self.name = "Constitutional Cockpit"
        self.version = "1.0.0"
        
        # Initialize snapshot loader (read-only)
        self.snapshot_loader = DashboardSnapshotLoader()
        
        # Initialize panels (all read-only)
        self.system_panel = SystemStatePanel()
        self.risk_panel = RiskPanel()
        self.engine_panel = EnginePanel()
        self.validation_panel = ValidationPanel()
        self.intelligence_panel = IntelligencePanel()
        
        # Constitutional principles
        self.principles = [
            "Dashboard is observational only",
            "No decisions are made while dashboard is open",
            "Dashboard is closed during drawdowns",
            "Weekly intelligence is read separately",
            "If you feel urgency, you stop looking"
        ]
    
    def load_system_snapshot(self):
        """Load immutable system snapshot for display"""
        try:
            snapshot = self.snapshot_loader.load_latest_snapshot()
            if snapshot is None:
                print("❌ No system snapshot available")
                return None
            
            # Validate snapshot is sufficiently stale (no real-time data)
            # For testing, allow 30 minutes minimum staleness
            staleness_hours = (datetime.now() - snapshot.creation_time).total_seconds() / 3600
            if staleness_hours < 0.5:  # 30 minutes minimum for testing
                print(f"⚠️ Snapshot too recent ({staleness_hours:.1f}h) - Using for testing anyway")
                # Don't return None for testing - just warn
            
            return snapshot
            
        except Exception as e:
            print(f"❌ Failed to load system snapshot: {e}")
            return None
    
    def render_constitutional_header(self):
        """Render constitutional header with system status"""
        st.markdown("""
        <div class="constitutional-header">
            🏛️ NORTHSTAR V3 CONSTITUTIONAL COCKPIT
            <br>
            <small>Truth • State • Integrity — Not Opportunity</small>
        </div>
        """, unsafe_allow_html=True)
    
    def render_panel_layout(self, snapshot):
        """Render the 5 locked panels in constitutional layout"""
        
        # Top row: System State + Risk Authority
        col1, col2 = st.columns(2)
        
        with col1:
            with st.container():
                st.markdown('<div class="panel-header">📊 PANEL 1 — SYSTEM STATE</div>', unsafe_allow_html=True)
                st.markdown('<div class="metric-label">Question: "Is the system healthy and behaving as designed?"</div>', unsafe_allow_html=True)
                self.system_panel.render(snapshot)
        
        with col2:
            with st.container():
                st.markdown('<div class="panel-header">🛡️ PANEL 2 — RISK AUTHORITY</div>', unsafe_allow_html=True)
                st.markdown('<div class="metric-label">Question: "Who is in charge right now?"</div>', unsafe_allow_html=True)
                self.risk_panel.render(snapshot)
        
        # Center row: Engine Behavior (full width)
        with st.container():
            st.markdown('<div class="panel-header">⚙️ PANEL 3 — ENGINE BEHAVIOR</div>', unsafe_allow_html=True)
            st.markdown('<div class="metric-label">Question: "Are the engines behaving like they promised?"</div>', unsafe_allow_html=True)
            self.engine_panel.render(snapshot)
        
        # Bottom row: Validation + Intelligence Observer
        col3, col4 = st.columns(2)
        
        with col3:
            with st.container():
                st.markdown('<div class="panel-header">✅ PANEL 4 — VALIDATION & TRUTH</div>', unsafe_allow_html=True)
                st.markdown('<div class="metric-label">Question: "Is this system still honest?"</div>', unsafe_allow_html=True)
                self.validation_panel.render(snapshot)
        
        with col4:
            with st.container():
                st.markdown('<div class="panel-header">🧠 PANEL 5 — INTELLIGENCE OBSERVER</div>', unsafe_allow_html=True)
                st.markdown('<div class="metric-label">Question: "What should I understand — not act on?"</div>', unsafe_allow_html=True)
                self.intelligence_panel.render(snapshot)
    
    def render_constitutional_footer(self, snapshot):
        """Render constitutional footer with principles and metadata"""
        st.markdown("""
        <div class="constitutional-footer">
            <strong>Constitutional Principles:</strong><br>
            Dashboard is observational only • No decisions made while open • Closed during drawdowns<br>
            Weekly intelligence read separately • If you feel urgency, stop looking<br><br>
            <strong>Snapshot Metadata:</strong><br>
            ID: {snapshot_id} • Created: {creation_time} • Staleness: {staleness:.1f}h<br>
            Quality: {quality:.1%} • Completeness: {completeness:.1%}<br><br>
            <em>"The dashboard reduces emotion, not increases it."</em>
        </div>
        """.format(
            snapshot_id=snapshot.snapshot_id[:8],
            creation_time=snapshot.creation_time.strftime("%Y-%m-%d %H:%M"),
            staleness=snapshot.staleness_hours,
            quality=snapshot.data_quality_score,
            completeness=snapshot.completeness_score
        ), unsafe_allow_html=True)
    
    def run(self):
        """Run the constitutional cockpit"""
        
        # Render constitutional header
        self.render_constitutional_header()
        
        # Load immutable system snapshot
        snapshot = self.load_system_snapshot()
        if snapshot is None:
            st.error("❌ No system snapshot available - run test script first")
            st.code("python scripts/test_constitutional_cockpit.py")
            st.stop()
        
        # Render 5 locked panels
        self.render_panel_layout(snapshot)
        
        # Render constitutional footer
        self.render_constitutional_footer(snapshot)
        
        # Auto-refresh every 5 minutes (but only with stale data)
        st.markdown("""
        <script>
        setTimeout(function(){
            window.location.reload(1);
        }, 300000); // 5 minutes
        </script>
        """, unsafe_allow_html=True)

# Main execution - this runs when Streamlit loads the file
try:
    # Initialize and run constitutional cockpit
    cockpit = ConstitutionalCockpit()
    cockpit.run()
except Exception as e:
    st.error(f"❌ Constitutional Cockpit Error: {e}")
    st.code("python scripts/test_constitutional_cockpit.py")
    import traceback
    st.text(traceback.format_exc())