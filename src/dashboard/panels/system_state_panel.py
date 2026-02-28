#!/usr/bin/env python3
"""
PANEL 1 — SYSTEM STATE
"Is the system healthy and behaving as designed?"

This panel shows system health and behavior without any opportunity signals.
Displays current regime, active engine, exposure state, and conviction status.
"""

import streamlit as st
import plotly.graph_objects as go
from datetime import datetime, timedelta
from typing import Dict, Any

class SystemStatePanel:
    """System State Panel - Shows system health and behavior"""
    
    def __init__(self):
        self.name = "System State Panel"
        self.version = "1.0.0"
    
    def render(self, snapshot):
        """Render system state panel"""
        
        system_state = snapshot.system_state
        
        # System Health Status
        self._render_system_health(system_state)
        
        # Current Regime (explicitly NOT shown: trade signals, forecasts, suggestions)
        self._render_regime_status(system_state)
        
        # Active Engine Status
        self._render_engine_status(system_state)
        
        # Exposure State
        self._render_exposure_status(system_state)
        
        # Conviction Contract Status
        self._render_conviction_status(system_state)
    
    def _render_system_health(self, system_state):
        """Render system health indicators"""
        
        # System status with appropriate styling
        status_class = f"status-{system_state.system_status.replace('_', '-')}"
        
        st.markdown(f"""
        <div class="metric-row">
            <span class="metric-label">System Status:</span>
            <span class="metric-value {status_class}">{system_state.system_status.upper()}</span>
        </div>
        """, unsafe_allow_html=True)
        
        # Organ health
        organ_health_pct = (system_state.organs_healthy / system_state.organs_total) * 100
        health_class = "status-healthy" if organ_health_pct >= 80 else "status-degraded" if organ_health_pct >= 60 else "status-critical"
        
        st.markdown(f"""
        <div class="metric-row">
            <span class="metric-label">Organs Healthy:</span>
            <span class="metric-value {health_class}">{system_state.organs_healthy}/{system_state.organs_total} ({organ_health_pct:.0f}%)</span>
        </div>
        """, unsafe_allow_html=True)
    
    def _render_regime_status(self, system_state):
        """Render current regime status (NOT forecasts or signals)"""
        
        # Current regime classification
        regime_class = "status-healthy" if system_state.current_regime == "SUPPORTIVE" else "status-neutral" if system_state.current_regime == "HOSTILE" else "status-critical"
        
        st.markdown(f"""
        <div class="metric-row">
            <span class="metric-label">Current Regime:</span>
            <span class="metric-value {regime_class}">{system_state.current_regime}</span>
        </div>
        """, unsafe_allow_html=True)
        
        # Regime confidence (behavior, not performance)
        confidence_class = "status-healthy" if system_state.regime_confidence >= 0.8 else "status-neutral"
        
        st.markdown(f"""
        <div class="metric-row">
            <span class="metric-label">Regime Confidence:</span>
            <span class="metric-value {confidence_class}">{system_state.regime_confidence:.1%}</span>
        </div>
        """, unsafe_allow_html=True)
        
        # Regime duration (stability indicator)
        st.markdown(f"""
        <div class="metric-row">
            <span class="metric-label">Regime Duration:</span>
            <span class="metric-value">{system_state.regime_duration_days} days</span>
        </div>
        """, unsafe_allow_html=True)
        
        # Last regime change timestamp
        if system_state.last_regime_change:
            change_date = system_state.last_regime_change.strftime("%Y-%m-%d")
            st.markdown(f"""
            <div class="metric-row">
                <span class="metric-label">Last Regime Change:</span>
                <span class="metric-value">{change_date}</span>
            </div>
            """, unsafe_allow_html=True)
    
    def _render_engine_status(self, system_state):
        """Render active engine status"""
        
        # Active engine
        engine_class = "status-healthy" if system_state.active_engine != "none" else "status-neutral"
        
        st.markdown(f"""
        <div class="metric-row">
            <span class="metric-label">Active Engine:</span>
            <span class="metric-value {engine_class}">{system_state.active_engine.title()}</span>
        </div>
        """, unsafe_allow_html=True)
        
        # Engine confidence
        confidence_class = "status-healthy" if system_state.engine_confidence >= 0.7 else "status-neutral"
        
        st.markdown(f"""
        <div class="metric-row">
            <span class="metric-label">Engine Confidence:</span>
            <span class="metric-value {confidence_class}">{system_state.engine_confidence:.1%}</span>
        </div>
        """, unsafe_allow_html=True)
    
    def _render_exposure_status(self, system_state):
        """Render exposure state (lagged, not current)"""
        
        # Exposure state
        exposure_class = "status-healthy" if system_state.exposure_state == "RISK_ON" else "status-neutral" if system_state.exposure_state == "NEUTRAL" else "status-critical"
        
        st.markdown(f"""
        <div class="metric-row">
            <span class="metric-label">Exposure State:</span>
            <span class="metric-value {exposure_class}">{system_state.exposure_state}</span>
        </div>
        """, unsafe_allow_html=True)
        
        # Allowed exposure (policy, not current)
        st.markdown(f"""
        <div class="metric-row">
            <span class="metric-label">Allowed Exposure:</span>
            <span class="metric-value">{system_state.allowed_exposure:.1%}</span>
        </div>
        """, unsafe_allow_html=True)
    
    def _render_conviction_status(self, system_state):
        """Render conviction contract status"""
        
        # Conviction locked status
        locked_class = "status-healthy" if system_state.conviction_locked else "status-critical"
        locked_text = "LOCKED ✅" if system_state.conviction_locked else "UNLOCKED ❌"
        
        st.markdown(f"""
        <div class="metric-row">
            <span class="metric-label">Conviction Contract:</span>
            <span class="metric-value {locked_class}">{locked_text}</span>
        </div>
        """, unsafe_allow_html=True)
        
        # Conviction violations (should be 0)
        violations_class = "status-healthy" if system_state.conviction_violations == 0 else "status-critical"
        
        st.markdown(f"""
        <div class="metric-row">
            <span class="metric-label">Conviction Violations:</span>
            <span class="metric-value {violations_class}">{system_state.conviction_violations}</span>
        </div>
        """, unsafe_allow_html=True)
        
        # Panel summary note
        st.markdown("""
        <div style="margin-top: 1rem; padding: 0.5rem; background: #f9fafb; border-radius: 4px; font-size: 0.8rem; color: #6b7280;">
            <strong>Panel Purpose:</strong> This panel replaces anxiety with situational clarity.
            Shows system behavior, not performance. No trade signals, forecasts, or suggestions.
        </div>
        """, unsafe_allow_html=True)