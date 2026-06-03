#!/usr/bin/env python3
"""
PANEL 5 — INTELLIGENCE OBSERVER
"What should I understand — not act on?"

This panel is quiet by design. No alerts, no popups, no flashing indicators.
Shows intelligence scores and provides link to weekly intelligence report.
"""

import streamlit as st
import plotly.graph_objects as go
from datetime import datetime, timedelta
from typing import Dict, Any

class IntelligencePanel:
    """Intelligence Panel - Shows understanding, not actions"""
    
    def __init__(self):
        self.name = "Intelligence Panel"
        self.version = "1.0.0"
    
    def render(self, snapshot):
        """Render intelligence observer panel"""
        
        intelligence_state = snapshot.intelligence_state
        
        # Observer Health Status
        self._render_observer_health(intelligence_state)
        
        # Intelligence Scores (quiet, non-actionable)
        self._render_intelligence_scores(intelligence_state)
        
        # Intelligence Metadata
        self._render_intelligence_metadata(intelligence_state)
        
        # Weekly Report Access
        self._render_weekly_report(intelligence_state)
    
    def _render_observer_health(self, intelligence_state):
        """Render observer health status"""
        
        # Observer health
        health_class = "status-healthy" if intelligence_state.observer_healthy else "status-critical"
        health_status = "Healthy" if intelligence_state.observer_healthy else "Degraded"
        
        st.markdown(f"""
        <div class="metric-row">
            <span class="metric-label">Observer Status:</span>
            <span class="metric-value {health_class}">{health_status}</span>
        </div>
        """, unsafe_allow_html=True)
        
        # Observer violations
        violations_class = "status-healthy" if intelligence_state.observer_violations == 0 else "status-critical"
        
        st.markdown(f"""
        <div class="metric-row">
            <span class="metric-label">Authority Violations:</span>
            <span class="metric-value {violations_class}">{intelligence_state.observer_violations}</span>
        </div>
        """, unsafe_allow_html=True)
        
        # Observer suspended status
        if intelligence_state.observer_suspended:
            st.markdown(f"""
            <div class="metric-row">
                <span class="metric-label">Observer Status:</span>
                <span class="metric-value status-critical">SUSPENDED</span>
            </div>
            """, unsafe_allow_html=True)
    
    def _render_intelligence_scores(self, intelligence_state):
        """Render intelligence scores (quiet, non-actionable)"""
        
        st.markdown("**Intelligence Indices:**")
        
        # Regime Similarity Index
        regime_class = self._get_intelligence_class(intelligence_state.regime_similarity_index)
        
        st.markdown(f"""
        <div class="metric-row">
            <span class="metric-label">Regime Similarity:</span>
            <span class="metric-value {regime_class}">{intelligence_state.regime_similarity_index:.1f}/100</span>
        </div>
        """, unsafe_allow_html=True)
        
        # Stress Clustering Index
        stress_class = self._get_intelligence_class(intelligence_state.stress_clustering_index)
        
        st.markdown(f"""
        <div class="metric-row">
            <span class="metric-label">Stress Clustering:</span>
            <span class="metric-value {stress_class}">{intelligence_state.stress_clustering_index:.1f}/100</span>
        </div>
        """, unsafe_allow_html=True)
        
        # False Calm Likelihood
        calm_class = self._get_intelligence_class(intelligence_state.false_calm_likelihood)
        
        st.markdown(f"""
        <div class="metric-row">
            <span class="metric-label">False Calm Likelihood:</span>
            <span class="metric-value {calm_class}">{intelligence_state.false_calm_likelihood:.1f}/100</span>
        </div>
        """, unsafe_allow_html=True)
        
        # Behavioral Drift Index
        drift_class = self._get_intelligence_class(intelligence_state.behavioral_drift_index)
        
        st.markdown(f"""
        <div class="metric-row">
            <span class="metric-label">Behavioral Drift:</span>
            <span class="metric-value {drift_class}">{intelligence_state.behavioral_drift_index:.1f}/100</span>
        </div>
        """, unsafe_allow_html=True)
    
    def _render_intelligence_metadata(self, intelligence_state):
        """Render intelligence metadata"""
        
        # Intelligence confidence
        confidence_class = "status-healthy" if intelligence_state.intelligence_confidence >= 0.8 else "status-neutral"
        
        st.markdown(f"""
        <div class="metric-row">
            <span class="metric-label">Intelligence Confidence:</span>
            <span class="metric-value {confidence_class}">{intelligence_state.intelligence_confidence:.1%}</span>
        </div>
        """, unsafe_allow_html=True)
        
        # Last intelligence update
        if intelligence_state.last_intelligence_update:
            update_time = intelligence_state.last_intelligence_update.strftime("%Y-%m-%d %H:%M")
            st.markdown(f"""
            <div class="metric-row">
                <span class="metric-label">Last Update:</span>
                <span class="metric-value">{update_time}</span>
            </div>
            """, unsafe_allow_html=True)
    
    def _render_weekly_report(self, intelligence_state):
        """Render weekly report access (quiet)"""
        
        # Weekly report availability
        if intelligence_state.weekly_report_available:
            st.markdown(f"""
            <div class="metric-row">
                <span class="metric-label">Weekly Report:</span>
                <span class="metric-value status-healthy">Available</span>
            </div>
            """, unsafe_allow_html=True)
            
            # Report path (for manual access)
            if intelligence_state.weekly_report_path:
                st.markdown(f"""
                <div class="metric-row">
                    <span class="metric-label">Report Path:</span>
                    <span class="metric-value" style="font-family: monospace; font-size: 0.8rem;">{intelligence_state.weekly_report_path}</span>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="metric-row">
                <span class="metric-label">Weekly Report:</span>
                <span class="metric-value status-neutral">Pending</span>
            </div>
            """, unsafe_allow_html=True)
        
        # Panel summary note
        st.markdown("""
        <div style="margin-top: 1rem; padding: 0.5rem; background: #f9fafb; border-radius: 4px; font-size: 0.8rem; color: #6b7280;">
            <strong>Design Principle:</strong> This panel is quiet by design. No alerts, no popups, 
            no flashing indicators. Intelligence exists to understand, not to act.
            Weekly intelligence is read separately from this dashboard.
        </div>
        """, unsafe_allow_html=True)
    
    def _get_intelligence_class(self, score: float) -> str:
        """Get CSS class for intelligence score (neutral styling)"""
        # All intelligence scores use neutral styling to avoid action bias
        return "status-neutral"