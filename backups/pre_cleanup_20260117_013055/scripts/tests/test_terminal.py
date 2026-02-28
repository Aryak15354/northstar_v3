#!/usr/bin/env python3
"""
🧭 TEST TERMINAL - Minimal version to test functionality
"""

import streamlit as st
import pandas as pd
import sys
import os

# Add src to path


st.set_page_config(
    layout="wide", 
    page_title="🧭 Northstar Test Terminal",
    initial_sidebar_state="collapsed"
)

st.markdown("# 🧭 NORTHSTAR UNIFIED TERMINAL")
st.markdown("## Test Version")

# Test data loading
try:
    from dashboard.data_loader import load_unified_snapshot
    
    with st.spinner("Loading snapshot..."):
        snapshot = load_unified_snapshot()
    
    st.success("✅ Snapshot loaded successfully!")
    
    # Display basic info
    st.json({
        "timestamp": str(snapshot.get('timestamp', 'Unknown')),
        "market_regime": snapshot.get('market', {}).get('regime', 'Unknown'),
        "portfolio_exposure": f"{snapshot.get('portfolio', {}).get('total_exposure', 0):.1f}%",
        "ai_status": snapshot.get('intelligence', {}).get('status', 'Unknown'),
        "system_health": snapshot.get('health', {}).get('grade', 'Unknown')
    })
    
except Exception as e:
    st.error(f"❌ Error loading snapshot: {e}")
    st.code(str(e))

st.markdown("---")
st.markdown("If you can see this, the basic terminal is working!")