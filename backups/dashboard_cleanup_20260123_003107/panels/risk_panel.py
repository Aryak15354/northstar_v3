#!/usr/bin/env python3
"""
PANEL 2 — RISK AUTHORITY
"Who is in charge right now?"

This panel shows risk authority status without anticipatory panic.
Red only if already triggered. No "approaching danger" colors.
"""

import streamlit as st
import plotly.graph_objects as go
from datetime import datetime, timedelta
from typing import Dict, Any

class RiskPanel:
    """Risk Panel - Shows who is in charge right now"""
    
    def __init__(self):
        self.name = "Risk Panel"
        self.version = "1.0.0"
    
    def render(self, snapshot):
        """Render risk authority panel"""
        
        risk_state = snapshot.risk_state
        
        # Emergency Brake Status
        self._render_emergency_brake(risk_state)
        
        # Drawdown vs Covenant
        self._render_drawdown_status(risk_state)
        
        # Kill Switch Status
        self._render_kill_switches(risk_state)
        
        # Volatility Stress Level
        self._render_volatility_stress(risk_state)
        
        # Last Risk Intervention
        self._render_last_intervention(risk_state)
    
    def _render_emergency_brake(self, risk_state):
        """Render emergency brake status"""
        
        # Emergency brake status
        brake_class = "status-healthy" if risk_state.emergency_brake_status == "ARMED" else "status-critical"
        
        st.markdown(f"""
        <div class="metric-row">
            <span class="metric-label">Emergency Brake:</span>
            <span class="metric-value {brake_class}">{risk_state.emergency_brake_status}</span>
        </div>
        """, unsafe_allow_html=True)
        
        # Emergency active (red only if triggered)
        if risk_state.emergency_active:
            st.markdown(f"""
            <div class="metric-row">
                <span class="metric-label">Emergency Status:</span>
                <span class="metric-value status-critical">ACTIVE ⚠️</span>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="metric-row">
                <span class="metric-label">Emergency Status:</span>
                <span class="metric-value status-neutral">Normal</span>
            </div>
            """, unsafe_allow_html=True)
    
    def _render_drawdown_status(self, risk_state):
        """Render drawdown vs covenant status"""
        
        # Current drawdown (red only if covenant breached)
        drawdown_breached = risk_state.drawdown_covenant_ratio >= 1.0
        drawdown_class = "status-critical" if drawdown_breached else "status-neutral"
        
        st.markdown(f"""
        <div class="metric-row">
            <span class="metric-label">Current Drawdown:</span>
            <span class="metric-value {drawdown_class}">{risk_state.current_drawdown:.1%}</span>
        </div>
        """, unsafe_allow_html=True)
        
        # Drawdown covenant
        st.markdown(f"""
        <div class="metric-row">
            <span class="metric-label">Drawdown Covenant:</span>
            <span class="metric-value">{risk_state.max_allowed_drawdown:.1%}</span>
        </div>
        """, unsafe_allow_html=True)
        
        # Covenant utilization (red only if breached)
        covenant_class = "status-critical" if drawdown_breached else "status-neutral"
        
        st.markdown(f"""
        <div class="metric-row">
            <span class="metric-label">Covenant Utilization:</span>
            <span class="metric-value {covenant_class}">{risk_state.drawdown_covenant_ratio:.1%}</span>
        </div>
        """, unsafe_allow_html=True)
    
    def _render_kill_switches(self, risk_state):
        """Render kill switch status"""
        
        # Kill switches armed
        switches_class = "status-healthy" if risk_state.kill_switches_armed == risk_state.kill_switches_total else "status-degraded"
        
        st.markdown(f"""
        <div class="metric-row">
            <span class="metric-label">Kill Switches Armed:</span>
            <span class="metric-value {switches_class}">{risk_state.kill_switches_armed}/{risk_state.kill_switches_total}</span>
        </div>
        """, unsafe_allow_html=True)
        
        # Last kill switch activation
        if risk_state.last_kill_switch_activation:
            activation_date = risk_state.last_kill_switch_activation.strftime("%Y-%m-%d %H:%M")
            st.markdown(f"""
            <div class="metric-row">
                <span class="metric-label">Last Activation:</span>
                <span class="metric-value status-critical">{activation_date}</span>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="metric-row">
                <span class="metric-label">Last Activation:</span>
                <span class="metric-value status-healthy">None</span>
            </div>
            """, unsafe_allow_html=True)
    
    def _render_volatility_stress(self, risk_state):
        """Render volatility stress level"""
        
        # Volatility stress level
        stress_class = {
            'low': 'status-healthy',
            'medium': 'status-neutral',
            'high': 'status-degraded',
            'extreme': 'status-critical'
        }.get(risk_state.volatility_stress, 'status-neutral')
        
        st.markdown(f"""
        <div class="metric-row">
            <span class="metric-label">Volatility Stress:</span>
            <span class="metric-value {stress_class}">{risk_state.volatility_stress.title()}</span>
        </div>
        """, unsafe_allow_html=True)
        
        # 20-day volatility
        vol_class = "status-critical" if risk_state.volatility_20d > 0.30 else "status-degraded" if risk_state.volatility_20d > 0.20 else "status-neutral"
        
        st.markdown(f"""
        <div class="metric-row">
            <span class="metric-label">Volatility (20d):</span>
            <span class="metric-value {vol_class}">{risk_state.volatility_20d:.1%}</span>
        </div>
        """, unsafe_allow_html=True)
    
    def _render_last_intervention(self, risk_state):
        """Render last risk intervention"""
        
        if risk_state.last_intervention:
            intervention_date = risk_state.last_intervention.strftime("%Y-%m-%d %H:%M")
            intervention_type = risk_state.intervention_type or "Unknown"
            
            st.markdown(f"""
            <div class="metric-row">
                <span class="metric-label">Last Intervention:</span>
                <span class="metric-value status-critical">{intervention_date}</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">Intervention Type:</span>
                <span class="metric-value status-critical">{intervention_type}</span>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="metric-row">
                <span class="metric-label">Last Intervention:</span>
                <span class="metric-value status-healthy">None</span>
            </div>
            """, unsafe_allow_html=True)
        
        # Panel summary note
        st.markdown("""
        <div style="margin-top: 1rem; padding: 0.5rem; background: #f9fafb; border-radius: 4px; font-size: 0.8rem; color: #6b7280;">
            <strong>Design Rule:</strong> Red only if already triggered. No "approaching danger" colors.
            This prevents anticipatory panic and shows actual authority status.
        </div>
        """, unsafe_allow_html=True)