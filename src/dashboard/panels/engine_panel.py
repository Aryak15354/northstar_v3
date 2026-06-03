#!/usr/bin/env python3
"""
PANEL 3 — ENGINE BEHAVIOR
"Are the engines behaving like they promised?"

This panel shows engine behavior, not performance.
Performance invites judgment. Behavior invites trust.
"""

import streamlit as st
import plotly.graph_objects as go
from datetime import datetime, timedelta
from typing import Dict, Any, List

class EnginePanel:
    """Engine Panel - Shows engine behavior, not performance"""
    
    def __init__(self):
        self.name = "Engine Panel"
        self.version = "1.0.0"
    
    def render(self, snapshot):
        """Render engine behavior panel"""
        
        engine_state = snapshot.engine_state
        
        # Engine Coordination Status
        self._render_engine_coordination(engine_state)
        
        # Trend Engine Behavior
        self._render_trend_engine_behavior(engine_state)
        
        # Crisis Engine Behavior
        self._render_crisis_engine_behavior(engine_state)
        
        # Engine Alignment
        self._render_engine_alignment(engine_state)
    
    def _render_engine_coordination(self, engine_state):
        """Render engine coordination status"""
        
        # Engine conflicts (must be 0)
        conflicts_class = "status-healthy" if engine_state.engine_conflicts == 0 else "status-critical"
        
        st.markdown(f"""
        <div class="metric-row">
            <span class="metric-label">Engine Conflicts:</span>
            <span class="metric-value {conflicts_class}">{engine_state.engine_conflicts}</span>
        </div>
        """, unsafe_allow_html=True)
        
        # Active engines (never both)
        both_active = engine_state.trend_engine_active and engine_state.crisis_engine_active
        coordination_class = "status-critical" if both_active else "status-healthy"
        coordination_text = "VIOLATION" if both_active else "Proper"
        
        st.markdown(f"""
        <div class="metric-row">
            <span class="metric-label">Engine Coordination:</span>
            <span class="metric-value {coordination_class}">{coordination_text}</span>
        </div>
        """, unsafe_allow_html=True)
    
    def _render_trend_engine_behavior(self, engine_state):
        """Render trend engine behavior (not performance)"""
        
        st.markdown("**Trend Engine:**")
        
        # Active status
        trend_class = "status-healthy" if engine_state.trend_engine_active else "status-neutral"
        trend_status = "Active" if engine_state.trend_engine_active else "Inactive"
        
        st.markdown(f"""
        <div class="metric-row">
            <span class="metric-label">Status:</span>
            <span class="metric-value {trend_class}">{trend_status}</span>
        </div>
        """, unsafe_allow_html=True)
        
        # Days active (behavior metric)
        st.markdown(f"""
        <div class="metric-row">
            <span class="metric-label">Days Active:</span>
            <span class="metric-value">{engine_state.trend_engine_days_active}</span>
        </div>
        """, unsafe_allow_html=True)
        
        # Holding duration distribution (behavior, not performance)
        duration_class = "status-healthy" if engine_state.trend_holding_duration_avg > 10 else "status-neutral"
        
        st.markdown(f"""
        <div class="metric-row">
            <span class="metric-label">Avg Holding Duration:</span>
            <span class="metric-value {duration_class}">{engine_state.trend_holding_duration_avg:.1f} days</span>
        </div>
        """, unsafe_allow_html=True)
        
        # Recent exits (structural only, no profit-taking)
        if engine_state.trend_recent_exits:
            exits_text = ", ".join(engine_state.trend_recent_exits)
            st.markdown(f"""
            <div class="metric-row">
                <span class="metric-label">Recent Exit Reasons:</span>
                <span class="metric-value">{exits_text}</span>
            </div>
            """, unsafe_allow_html=True)
    
    def _render_crisis_engine_behavior(self, engine_state):
        """Render crisis engine behavior (not performance)"""
        
        st.markdown("**Crisis Engine:**")
        
        # Active status
        crisis_class = "status-healthy" if engine_state.crisis_engine_active else "status-neutral"
        crisis_status = "Active" if engine_state.crisis_engine_active else "Armed"
        
        st.markdown(f"""
        <div class="metric-row">
            <span class="metric-label">Status:</span>
            <span class="metric-value {crisis_class}">{crisis_status}</span>
        </div>
        """, unsafe_allow_html=True)
        
        # Days active (should be low most of the time)
        st.markdown(f"""
        <div class="metric-row">
            <span class="metric-label">Days Active:</span>
            <span class="metric-value">{engine_state.crisis_engine_days_active}</span>
        </div>
        """, unsafe_allow_html=True)
        
        # Convexity integrity score (behavior metric)
        convexity_class = "status-healthy" if engine_state.crisis_convexity_score >= 0.8 else "status-degraded"
        
        st.markdown(f"""
        <div class="metric-row">
            <span class="metric-label">Convexity Integrity:</span>
            <span class="metric-value {convexity_class}">{engine_state.crisis_convexity_score:.1%}</span>
        </div>
        """, unsafe_allow_html=True)
        
        # Bleed vs payout ratio (historical behavior)
        bleed_class = "status-healthy" if engine_state.crisis_bleed_vs_payout <= 0.3 else "status-neutral"
        
        st.markdown(f"""
        <div class="metric-row">
            <span class="metric-label">Bleed vs Payout:</span>
            <span class="metric-value {bleed_class}">{engine_state.crisis_bleed_vs_payout:.1%}</span>
        </div>
        """, unsafe_allow_html=True)
    
    def _render_engine_alignment(self, engine_state):
        """Render regime-engine alignment"""
        
        # Regime alignment score
        alignment_class = "status-healthy" if engine_state.regime_engine_alignment >= 0.8 else "status-degraded"
        
        st.markdown(f"""
        <div class="metric-row">
            <span class="metric-label">Regime Alignment:</span>
            <span class="metric-value {alignment_class}">{engine_state.regime_engine_alignment:.1%}</span>
        </div>
        """, unsafe_allow_html=True)
        
        # Panel summary note
        st.markdown("""
        <div style="margin-top: 1rem; padding: 0.5rem; background: #f9fafb; border-radius: 4px; font-size: 0.8rem; color: #6b7280;">
            <strong>Key Rule:</strong> Show behavior, not performance. Performance invites judgment.
            Behavior invites trust. Focus on structural integrity and adherence to design.
        </div>
        """, unsafe_allow_html=True)