#!/usr/bin/env python3
"""
🧠 BRAIN WINDOW - LIVING SYSTEM DASHBOARD
Pure Display Interface for the Northstar Living System

This is the Brain Window that reads exclusively from Unified State without
computing its own version of truth. Like Bloomberg terminals that display
but don't compute.

Key Features:
- Reads exclusively from UnifiedState (single source of truth)
- Never computes truth independently
- Sends intents to living system (rebalance, override, pause)
- Real-time visualization of system's thinking
- Bloomberg-style professional interface
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
# Import living system components
from src.core.state import UnifiedState
from src.core.events import EventBus
from src.core.clock import MarketClock

# =========================== BRAIN WINDOW CONFIGURATION ===========================

st.set_page_config(
    layout="wide", 
    page_title="🧠 Northstar Brain Window - Living System Interface",
    initial_sidebar_state="collapsed"
)

# =========================== BRAIN WINDOW STYLING ===========================

st.markdown("""
<style>
    /* BRAIN WINDOW THEME - Bloomberg Style */
    .main { padding: 0.3rem; }
    .block-container { padding: 0.5rem; max-width: 100%; }
    
    /* SYSTEM STATUS BAR - Shows living system vitals */
    .brain-status-bar {
        background: linear-gradient(90deg, #000011, #001122, #002233);
        color: #00ff88;
        padding: 1rem 1.5rem;
        border-bottom: 3px solid #00ff88;
        position: sticky;
        top: 0;
        z-index: 1000;
        display: grid;
        grid-template-columns: repeat(8, 1fr);
        gap: 0.8rem;
        font-size: 0.85rem;
        font-weight: 700;
        box-shadow: 0 4px 15px rgba(0, 255, 136, 0.4);
        border-radius: 10px;
        margin-bottom: 1rem;
    }
    
    .brain-metric {
        text-align: center;
        padding: 0.5rem;
        background: rgba(0, 255, 136, 0.1);
        border-radius: 8px;
        border: 1px solid rgba(0, 255, 136, 0.3);
        transition: all 0.3s ease;
    }
    
    .brain-metric:hover {
        background: rgba(0, 255, 136, 0.2);
        border-color: #00ff88;
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0, 255, 136, 0.3);
    }
    
    .brain-metric h5 {
        margin: 0;
        font-size: 0.65rem;
        color: #a0aec0;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    
    .brain-metric h3 {
        margin: 0.2rem 0 0 0;
        font-size: 1rem;
        font-weight: 900;
    }
    
    /* EMERGENCY INDICATOR */
    .emergency-active {
        background: linear-gradient(90deg, #ff0000, #cc0000) !important;
        color: white !important;
        animation: pulse 1s infinite;
    }
    
    @keyframes pulse {
        0% { opacity: 1; }
        50% { opacity: 0.7; }
        100% { opacity: 1; }
    }
    
    /* SYSTEM LOCKED INDICATOR */
    .system-locked {
        background: linear-gradient(90deg, #ff6600, #cc4400) !important;
        color: white !important;
    }
    
    /* ORGAN PANELS */
    .organ-panel {
        background: linear-gradient(135deg, #1a1a2e, #16213e);
        border: 2px solid #00ff88;
        border-radius: 12px;
        padding: 1rem;
        margin: 0.5rem 0;
    }
    
    .organ-panel h3 {
        color: #00ff88;
        margin: 0 0 1rem 0;
        font-size: 1.1rem;
        font-weight: 900;
        text-align: center;
    }
    
    /* INTENT BUTTONS */
    .intent-button {
        background: linear-gradient(135deg, #0066cc, #004499);
        color: white;
        border: none;
        padding: 0.8rem 1.5rem;
        border-radius: 8px;
        font-weight: 700;
        cursor: pointer;
        transition: all 0.3s ease;
        margin: 0.3rem;
    }
    
    .intent-button:hover {
        background: linear-gradient(135deg, #0088ff, #0066cc);
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0, 136, 255, 0.3);
    }
    
    .intent-button-danger {
        background: linear-gradient(135deg, #cc0000, #990000);
    }
    
    .intent-button-danger:hover {
        background: linear-gradient(135deg, #ff0000, #cc0000);
    }
    
    /* BRAIN VISUALIZATION */
    .brain-viz {
        background: radial-gradient(circle, #001122, #000011);
        border: 2px solid #00ff88;
        border-radius: 12px;
        padding: 1rem;
        margin: 0.5rem 0;
    }
</style>
""", unsafe_allow_html=True)

# =========================== BRAIN WINDOW DATA INTERFACE ===========================

class BrainWindowInterface:
    """
    Brain Window Interface - Pure Display System
    
    Reads exclusively from UnifiedState without computing truth.
    Sends intents to the living system for actions.
    """
    
    def __init__(self):
        self.name = "Brain Window"
        self.version = "1.0"
        
        # Initialize living system components (read-only)
        self.unified_state = UnifiedState()
        self.event_bus = EventBus()
        self.market_clock = MarketClock()
        
        # Intent queue for sending commands to living system
        self.intent_queue = []
        
        # Load current state from unified state
        self.refresh_state()
    
    def refresh_state(self):
        """Refresh state from unified state (single source of truth)"""
        
        try:
            # Load from legacy sources for compatibility during transition
            self.unified_state.load_from_legacy_sources()
            
            # Get dashboard-formatted state
            self.dashboard_state = self.unified_state.get_dashboard_state()
            
            return True
            
        except Exception as e:
            st.error(f"⚠️ Error refreshing state from unified state: {e}")
            return False
    
    def send_intent(self, intent_type: str, parameters: dict = None):
        """Send intent to living system"""
        
        intent = {
            'timestamp': datetime.now().isoformat(),
            'type': intent_type,
            'parameters': parameters or {},
            'source': 'brain_window',
            'status': 'pending'
        }
        
        self.intent_queue.append(intent)
        
        # Save intent to file for living system to process
        try:
            intent_file = 'data/intents/brain_window_intents.json'
            os.makedirs(os.path.dirname(intent_file), exist_ok=True)
            
            # Load existing intents
            if os.path.exists(intent_file):
                with open(intent_file, 'r') as f:
                    existing_intents = json.load(f)
            else:
                existing_intents = {'intents': []}
            
            # Add new intent
            existing_intents['intents'].append(intent)
            
            # Keep only recent intents
            existing_intents['intents'] = existing_intents['intents'][-100:]
            
            # Save intents
            with open(intent_file, 'w') as f:
                json.dump(existing_intents, f, indent=2, default=str)
            
            st.success(f"✅ Intent sent: {intent_type}")
            return True
            
        except Exception as e:
            st.error(f"❌ Failed to send intent: {e}")
            return False

# Initialize Brain Window Interface
@st.cache_resource
def get_brain_interface():
    return BrainWindowInterface()

# =========================== BRAIN WINDOW COMPONENTS ===========================

def render_brain_status_bar(dashboard_state):
    """Render the brain status bar showing living system vitals"""
    
    command_bar = dashboard_state.get('command_bar', {})
    system_health = dashboard_state.get('system_health', {})
    
    # Determine status classes
    emergency_class = "emergency-active" if command_bar.get('emergency_active', False) else ""
    locked_class = "system-locked" if dashboard_state.get('locked', False) else ""
    
    st.markdown(f"""
    <div class="brain-status-bar">
        <div class="brain-metric {emergency_class}">
            <h5>Emergency</h5>
            <h3>{'🚨 ACTIVE' if command_bar.get('emergency_active', False) else '✅ NORMAL'}</h3>
            <p style="margin:0; font-size:0.6rem; color:#a0aec0;">Risk Authority</p>
        </div>
        <div class="brain-metric {locked_class}">
            <h5>System</h5>
            <h3>{'🔒 LOCKED' if dashboard_state.get('locked', False) else '🔓 ACTIVE'}</h3>
            <p style="margin:0; font-size:0.6rem; color:#a0aec0;">State</p>
        </div>
        <div class="brain-metric">
            <h5>Regime</h5>
            <h3>{command_bar.get('regime', 'Unknown').title()}</h3>
            <p style="margin:0; font-size:0.6rem; color:#a0aec0;">Market</p>
        </div>
        <div class="brain-metric">
            <h5>Exposure</h5>
            <h3>{command_bar.get('exposure', 0):.1f}%</h3>
            <p style="margin:0; font-size:0.6rem; color:#a0aec0;">Portfolio</p>
        </div>
        <div class="brain-metric">
            <h5>AI Conviction</h5>
            <h3>{command_bar.get('ai_conviction', 0):.0f}%</h3>
            <p style="margin:0; font-size:0.6rem; color:#60a5fa;">{'🤖 ACTIVE' if command_bar.get('ai_active', False) else '💤 IDLE'}</p>
        </div>
        <div class="brain-metric">
            <h5>Risk Level</h5>
            <h3>{command_bar.get('risk_level', 'normal').upper()}</h3>
            <p style="margin:0; font-size:0.6rem; color:#ff6b6b;">Authority</p>
        </div>
        <div class="brain-metric">
            <h5>Health</h5>
            <h3>{system_health.get('overall_health_score', 0):.0%}</h3>
            <p style="margin:0; font-size:0.6rem; color:#10b981;">{system_health.get('health_status', 'unknown').title()}</p>
        </div>
        <div class="brain-metric">
            <h5>Time</h5>
            <h3>{datetime.now().strftime("%H:%M")}</h3>
            <p style="margin:0; font-size:0.6rem; color:#a0aec0;">{datetime.now().strftime("%m/%d")}</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

def render_intent_control_panel(brain_interface):
    """Render intent control panel for sending commands to living system"""
    
    st.markdown("""
    <div class="organ-panel">
        <h3>🎯 INTENT CONTROL PANEL</h3>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("🔄 Force Rebalance", key="rebalance_intent"):
            brain_interface.send_intent("force_rebalance", {
                "reason": "Manual rebalance requested from Brain Window",
                "timestamp": datetime.now().isoformat()
            })
    
    with col2:
        if st.button("⏸️ Pause System", key="pause_intent"):
            brain_interface.send_intent("pause_system", {
                "reason": "System pause requested from Brain Window",
                "duration_minutes": 60
            })
    
    with col3:
        if st.button("🛡️ Override Risk", key="risk_override_intent"):
            brain_interface.send_intent("override_risk", {
                "reason": "Risk override requested from Brain Window",
                "new_exposure_cap": 0.8
            })
    
    with col4:
        if st.button("🚨 Emergency Stop", key="emergency_intent"):
            brain_interface.send_intent("emergency_stop", {
                "reason": "Emergency stop requested from Brain Window",
                "authority": "EMERGENCY"
            })
    
    # Show recent intents
    if brain_interface.intent_queue:
        st.subheader("Recent Intents")
        for intent in brain_interface.intent_queue[-5:]:
            st.write(f"• {intent['timestamp']}: {intent['type']} - {intent.get('status', 'pending')}")

def render_market_brain_visualization(dashboard_state):
    """Render market brain visualization"""
    
    market_state = dashboard_state.get('market_state', {})
    intelligence_state = dashboard_state.get('intelligence_state', {})
    
    st.markdown("""
    <div class="brain-viz">
        <h3 style="color: #00ff88; text-align: center;">🧠 MARKET BRAIN VISUALIZATION</h3>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Market regime gauge
        regime_score = market_state.get('risk_on_probability', 0.5)
        
        fig_regime = go.Figure(go.Indicator(
            mode="gauge+number",
            value=regime_score * 100,
            title={'text': "Risk-On Probability"},
            gauge={
                'axis': {'range': [0, 100]},
                'bar': {'color': "lightgreen" if regime_score > 0.6 else "orange" if regime_score > 0.4 else "red"},
                'steps': [
                    {'range': [0, 40], 'color': "lightgray"},
                    {'range': [40, 60], 'color': "yellow"},
                    {'range': [60, 100], 'color': "lightgreen"}
                ],
                'threshold': {
                    'line': {'color': "red", 'width': 4},
                    'thickness': 0.75,
                    'value': 90
                }
            }
        ))
        fig_regime.update_layout(height=300, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig_regime, width='stretch')
    
    with col2:
        # AI conviction gauge
        beliefs = intelligence_state.get('beliefs', {})
        ai_conviction = beliefs.get('unified_conviction', 0.0)
        
        fig_conviction = go.Figure(go.Indicator(
            mode="gauge+number",
            value=ai_conviction * 100,
            title={'text': "AI Unified Conviction"},
            gauge={
                'axis': {'range': [0, 100]},
                'bar': {'color': "lightblue" if ai_conviction > 0.6 else "orange" if ai_conviction > 0.3 else "red"},
                'steps': [
                    {'range': [0, 30], 'color': "lightgray"},
                    {'range': [30, 60], 'color': "yellow"},
                    {'range': [60, 100], 'color': "lightblue"}
                ]
            }
        ))
        fig_conviction.update_layout(height=300, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig_conviction, width='stretch')
    
    # Market state metrics
    st.subheader("Market Brain State")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Market Regime", market_state.get('regime', 'unknown').title())
    
    with col2:
        allowed_exp = market_state.get('allowed_exposure', 0.35)
        st.metric("Allowed Exposure", f"{allowed_exp:.1%}")
    
    with col3:
        market_stress = market_state.get('market_stress', 0.0)
        st.metric("Market Stress", f"{market_stress:.1%}")
    
    with col4:
        volatility_regime = market_state.get('volatility_regime', 'normal')
        st.metric("Volatility Regime", volatility_regime.title())

def render_portfolio_organism(dashboard_state):
    """Render portfolio organism visualization"""
    
    portfolio_state = dashboard_state.get('portfolio_state', {})
    
    st.markdown("""
    <div class="organ-panel">
        <h3>🎯 PORTFOLIO ORGANISM</h3>
    </div>
    """, unsafe_allow_html=True)
    
    # Portfolio metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_positions = portfolio_state.get('total_positions', 0)
        st.metric("Total Positions", total_positions)
    
    with col2:
        total_exposure = portfolio_state.get('total_exposure', 0.0)
        st.metric("Total Exposure", f"{total_exposure:.1%}")
    
    with col3:
        max_position = portfolio_state.get('max_position', 0.0)
        st.metric("Max Position", f"{max_position:.2%}")
    
    with col4:
        compliance_status = portfolio_state.get('compliance_status', True)
        st.metric("Compliance", "✅ OK" if compliance_status else "❌ VIOLATION")
    
    # Portfolio health visualization
    if total_positions > 0:
        # Create portfolio health radar
        categories = ['Exposure', 'Diversification', 'Risk', 'Performance', 'Compliance']
        
        # Calculate health scores (normalized to 0-1)
        exposure_health = min(total_exposure / 0.6, 1.0)  # Target 60% exposure
        diversification_health = min(total_positions / 50, 1.0)  # Target 50 positions
        risk_health = 1.0 - min(max_position / 0.1, 1.0)  # Penalize large positions
        performance_health = max((portfolio_state.get('sharpe_ratio', 0.0) + 1) / 3, 0.0)  # Normalize Sharpe
        compliance_health = 1.0 if compliance_status else 0.0
        
        values = [exposure_health, diversification_health, risk_health, performance_health, compliance_health]
        
        fig_radar = go.Figure()
        
        fig_radar.add_trace(go.Scatterpolar(
            r=values,
            theta=categories,
            fill='toself',
            name='Portfolio Health',
            line_color='lightblue'
        ))
        
        fig_radar.update_layout(
            polar=dict(
                radialaxis=dict(
                    visible=True,
                    range=[0, 1]
                )),
            showlegend=True,
            height=400,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)'
        )
        
        st.plotly_chart(fig_radar, width='stretch')

def render_risk_spinal_cord(dashboard_state):
    """Render risk spinal cord (absolute authority system)"""
    
    risk_state = dashboard_state.get('risk_state', {})
    
    st.markdown("""
    <div class="organ-panel" style="border-color: #ff6b6b;">
        <h3 style="color: #ff6b6b;">🛡️ RISK SPINAL CORD (ABSOLUTE AUTHORITY)</h3>
    </div>
    """, unsafe_allow_html=True)
    
    # Risk authority metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        emergency_active = risk_state.get('emergency_active', False)
        st.metric("Emergency Status", "🚨 ACTIVE" if emergency_active else "✅ NORMAL")
    
    with col2:
        risk_status = risk_state.get('status', 'normal')
        if hasattr(risk_status, 'value'):
            status_display = risk_status.value.upper()
        else:
            status_display = str(risk_status).upper()
        st.metric("Risk Status", status_display)
    
    with col3:
        system_stress = risk_state.get('system_stress', 0.0)
        st.metric("System Stress", f"{system_stress:.1%}")
    
    with col4:
        survival_mode = risk_state.get('survival_mode', 'normal')
        st.metric("Survival Mode", survival_mode.upper())
    
    # Risk authority visualization
    if emergency_active:
        st.error("🚨 EMERGENCY BRAKE ACTIVE - Risk system has absolute authority over all decisions")
        
        # Show emergency details
        st.subheader("Emergency State Details")
        brake_conditions = risk_state.get('brake_conditions', 0)
        st.write(f"• Triggered conditions: {brake_conditions}")
        
        exposure_multiplier = risk_state.get('exposure_multiplier', 1.0)
        st.write(f"• Exposure multiplier: {exposure_multiplier:.2f}")
        
        kill_switches = risk_state.get('kill_switches', {})
        if kill_switches:
            st.write("• Active kill switches:")
            for switch, active in kill_switches.items():
                if active:
                    st.write(f"  - {switch}: ACTIVE")
    else:
        st.success("✅ Normal operations - Risk system monitoring but not intervening")

def render_system_events_log(dashboard_state):
    """Render recent system events from unified state"""
    
    recent_events = dashboard_state.get('recent_events', [])
    
    st.subheader("🔄 Recent System Events")
    
    if recent_events:
        # Create events DataFrame for better display
        events_data = []
        for event in recent_events[-10:]:  # Show last 10 events
            events_data.append({
                'Time': event.get('timestamp', 'unknown'),
                'Organ': event.get('organ', 'unknown'),
                'Component': event.get('component', 'unknown'),
                'Field': event.get('field', 'unknown'),
                'New Value': str(event.get('new_value', 'unknown')),
                'Reason': event.get('reason', 'unknown')
            })
        
        if events_data:
            events_df = pd.DataFrame(events_data)
            st.dataframe(events_df, width='stretch')
    else:
        st.info("No recent events available. System may be initializing.")

# =========================== MAIN BRAIN WINDOW ===========================

def main_brain_window():
    """Main Brain Window Interface"""
    
    # Get brain interface
    brain_interface = get_brain_interface()
    
    # Refresh state from unified state
    if not brain_interface.refresh_state():
        st.error("❌ Failed to connect to living system unified state")
        return
    
    dashboard_state = brain_interface.dashboard_state
    
    # Brain Window header
    st.markdown("""
    <div style="text-align: center; margin-bottom: 1rem;">
        <h1 style="color: #00ff88; font-size: 2.5rem; margin: 0;">🧠 NORTHSTAR BRAIN WINDOW</h1>
        <p style="color: #a0aec0; font-size: 1.1rem; margin: 0.3rem 0;">
            Living System Interface • Pure Display • No Independent Computation
        </p>
        <p style="color: #60a5fa; font-size: 0.9rem; margin: 0;">
            Reading from Unified State • Sending Intents to Living System
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Brain status bar
    render_brain_status_bar(dashboard_state)
    
    # Main interface layout
    tab1, tab2, tab3, tab4 = st.tabs(["🧠 Brain Visualization", "🎯 Portfolio Organism", "🛡️ Risk Authority", "🔄 System Events"])
    
    with tab1:
        render_intent_control_panel(brain_interface)
        render_market_brain_visualization(dashboard_state)
    
    with tab2:
        render_portfolio_organism(dashboard_state)
    
    with tab3:
        render_risk_spinal_cord(dashboard_state)
    
    with tab4:
        render_system_events_log(dashboard_state)
        
        # Show system health details
        st.subheader("🏥 System Health Details")
        system_health = dashboard_state.get('system_health', {})
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            data_fresh = system_health.get('data_fresh', False)
            st.metric("Data Freshness", "✅ Fresh" if data_fresh else "⚠️ Stale")
        
        with col2:
            component_availability = system_health.get('component_availability', 0.0)
            st.metric("Component Availability", f"{component_availability:.0%}")
        
        with col3:
            components_healthy = system_health.get('components_healthy', 0)
            total_components = system_health.get('total_components', 0)
            st.metric("Healthy Components", f"{components_healthy}/{total_components}")
    
    # Auto-refresh every 30 seconds
    if st.button("🔄 Refresh State"):
        brain_interface.refresh_state()
        st.rerun()

# =========================== MAIN EXECUTION ===========================

if __name__ == "__main__":
    main_brain_window()