#!/usr/bin/env python3
"""
PANEL 4 — VALIDATION & TRUTH
"Is this system still honest?"

This panel exists to shut down self-deception.
Shows validation results, rules integrity, and override attempts.
"""

import streamlit as st
import plotly.graph_objects as go
from datetime import datetime, timedelta
from typing import Dict, Any

class ValidationPanel:
    """Validation Panel - Shows system honesty and integrity"""
    
    def __init__(self):
        self.name = "Validation Panel"
        self.version = "1.0.0"
    
    def render(self, snapshot):
        """Render validation & truth panel"""
        
        validation_state = snapshot.validation_state
        
        # Walk-Forward Validation Results
        self._render_walkforward_validation(validation_state)
        
        # Rules Hash Integrity
        self._render_rules_integrity(validation_state)
        
        # Override Attempts (should be 0)
        self._render_override_attempts(validation_state)
        
        # Data Integrity Status (5-layer checklist)
        self._render_data_integrity(validation_state)
    
    def _render_walkforward_validation(self, validation_state):
        """Render walk-forward validation status"""
        
        # Last validation result
        result_class = {
            'PASS': 'status-healthy',
            'FAIL': 'status-critical',
            'PENDING': 'status-neutral'
        }.get(validation_state.last_walkforward_result, 'status-neutral')
        
        st.markdown(f"""
        <div class="metric-row">
            <span class="metric-label">Last Walk-Forward:</span>
            <span class="metric-value {result_class}">{validation_state.last_walkforward_result}</span>
        </div>
        """, unsafe_allow_html=True)
        
        # Last validation date
        if validation_state.last_walkforward_date:
            validation_date = validation_state.last_walkforward_date.strftime("%Y-%m-%d")
            st.markdown(f"""
            <div class="metric-row">
                <span class="metric-label">Validation Date:</span>
                <span class="metric-value">{validation_date}</span>
            </div>
            """, unsafe_allow_html=True)
        
        # Success rate (historical honesty)
        success_class = "status-healthy" if validation_state.walkforward_success_rate >= 0.8 else "status-degraded" if validation_state.walkforward_success_rate >= 0.6 else "status-critical"
        
        st.markdown(f"""
        <div class="metric-row">
            <span class="metric-label">Success Rate:</span>
            <span class="metric-value {success_class}">{validation_state.walkforward_success_rate:.1%}</span>
        </div>
        """, unsafe_allow_html=True)
    
    def _render_rules_integrity(self, validation_state):
        """Render rules hash integrity"""
        
        # Rules hash verification
        hash_class = "status-healthy" if validation_state.rules_hash_verified else "status-critical"
        hash_status = "Verified ✅" if validation_state.rules_hash_verified else "CORRUPTED ❌"
        
        st.markdown(f"""
        <div class="metric-row">
            <span class="metric-label">Rules Hash:</span>
            <span class="metric-value {hash_class}">{hash_status}</span>
        </div>
        """, unsafe_allow_html=True)
        
        # Current rules hash (for audit)
        st.markdown(f"""
        <div class="metric-row">
            <span class="metric-label">Hash Value:</span>
            <span class="metric-value" style="font-family: monospace; font-size: 0.8rem;">{validation_state.current_rules_hash}</span>
        </div>
        """, unsafe_allow_html=True)
    
    def _render_override_attempts(self, validation_state):
        """Render override attempts (should be 0)"""
        
        # Override attempts in last 24h (should be 0)
        attempts_24h_class = "status-healthy" if validation_state.override_attempts_24h == 0 else "status-critical"
        
        st.markdown(f"""
        <div class="metric-row">
            <span class="metric-label">Override Attempts (24h):</span>
            <span class="metric-value {attempts_24h_class}">{validation_state.override_attempts_24h}</span>
        </div>
        """, unsafe_allow_html=True)
        
        # Total override attempts (should be 0)
        attempts_total_class = "status-healthy" if validation_state.override_attempts_total == 0 else "status-critical"
        
        st.markdown(f"""
        <div class="metric-row">
            <span class="metric-label">Total Override Attempts:</span>
            <span class="metric-value {attempts_total_class}">{validation_state.override_attempts_total}</span>
        </div>
        """, unsafe_allow_html=True)
        
        # Warning if overrides detected
        if validation_state.override_attempts_total > 0:
            st.markdown("""
            <div style="background: #fef2f2; border: 1px solid #fecaca; border-radius: 4px; padding: 0.5rem; margin: 0.5rem 0;">
                <span style="color: #dc2626; font-weight: bold;">⚠️ INTEGRITY VIOLATION</span><br>
                <span style="color: #7f1d1d; font-size: 0.9rem;">Override attempts detected. System integrity compromised.</span>
            </div>
            """, unsafe_allow_html=True)
    
    def _render_data_integrity(self, validation_state):
        """Render data integrity 5-layer checklist"""
        
        st.markdown("**Data Integrity (5-Layer Checklist):**")
        
        # Render each integrity layer
        for layer, status in validation_state.data_integrity_layers.items():
            status_class = "status-healthy" if status else "status-critical"
            status_icon = "✅" if status else "❌"
            
            st.markdown(f"""
            <div class="metric-row">
                <span class="metric-label">{layer.title()}:</span>
                <span class="metric-value {status_class}">{status_icon}</span>
            </div>
            """, unsafe_allow_html=True)
        
        # Overall integrity score
        integrity_class = "status-healthy" if validation_state.data_integrity_score >= 0.95 else "status-degraded" if validation_state.data_integrity_score >= 0.8 else "status-critical"
        
        st.markdown(f"""
        <div class="metric-row">
            <span class="metric-label">Overall Integrity:</span>
            <span class="metric-value {integrity_class}">{validation_state.data_integrity_score:.1%}</span>
        </div>
        """, unsafe_allow_html=True)
        
        # Panel summary note
        st.markdown("""
        <div style="margin-top: 1rem; padding: 0.5rem; background: #f9fafb; border-radius: 4px; font-size: 0.8rem; color: #6b7280;">
            <strong>Panel Purpose:</strong> This panel exists to shut down self-deception.
            Shows validation results, rules integrity, and override attempts. Truth over comfort.
        </div>
        """, unsafe_allow_html=True)