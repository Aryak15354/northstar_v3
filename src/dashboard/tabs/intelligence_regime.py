"""
Intelligence & Regime Tab - Market Regime and Sentiment Analysis
Displays regime transitions, sentiment scores, and macro drivers
"""

import streamlit as st
import pandas as pd
from typing import Optional
from ..charts.chart_library import (
    chart_regime_timeline,
    chart_regime_transition_matrix,
    chart_sentiment_score,
    chart_sentiment_polarity,
    chart_sentiment_conviction,
    chart_narrative_strength,
    chart_macro_driver_heatmap,
    chart_macro_changes,
    chart_regime_stability,
    chart_intelligence_freshness,
    chart_sentiment_returns_correlation,
    chart_regime_duration_dist
)


def render_intelligence_tab(data_contract):
    """Render the Intelligence & Regime tab"""
    
    st.header("🧠 Intelligence & Regime Analysis")
    st.caption("Market regime detection, sentiment analysis, and macro drivers")
    
    # Get intelligence data
    regime_df = data_contract.get_regime_history(lookback_days=90)
    sentiment_state = data_contract.get_sentiment_state()
    macro_state = data_contract.get_macro_state()
    nav_df = data_contract.get_nav_history(lookback_days=90)
    
    # Key metrics row
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        current_regime = data_contract.get_market_regime()
        if current_regime.is_available:
            regime_name = current_regime.value.get('regime', 'Unknown')
            st.metric("Current Regime", regime_name)
        else:
            st.metric("Current Regime", "N/A")
    
    with col2:
        if sentiment_state.is_available:
            sentiment_score = sentiment_state.value.get('sentiment_score', 0)
            st.metric("Sentiment Score", f"{sentiment_score:.2f}")
        else:
            st.metric("Sentiment Score", "N/A")
    
    with col3:
        if sentiment_state.is_available:
            conviction = sentiment_state.value.get('conviction', 0)
            st.metric("Conviction", f"{conviction:.2f}")
        else:
            st.metric("Conviction", "N/A")
    
    with col4:
        if regime_df.is_available and not regime_df.value.empty:
            regime_changes = len(regime_df.value['regime'].unique()) if 'regime' in regime_df.value.columns else 0
            st.metric("Regime Changes (90d)", regime_changes)
        else:
            st.metric("Regime Changes", "N/A")
    
    st.divider()
    
    # Regime Timeline and Transition Matrix
    st.subheader("Regime Analysis")
    col1, col2 = st.columns(2)
    
    with col1:
        if regime_df.is_available and not regime_df.value.empty:
            fig = chart_regime_timeline(regime_df.value)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Regime timeline not available")
        else:
            st.info("No regime history available")
    
    with col2:
        if regime_df.is_available and not regime_df.value.empty:
            fig = chart_regime_transition_matrix(regime_df.value)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Transition matrix not available")
        else:
            st.info("No regime history available")
    
    # Sentiment Analysis
    st.subheader("Sentiment Analysis")
    
    # Create sentiment time series from regime data
    sentiment_df = regime_df.value if regime_df.is_available else pd.DataFrame()
    
    col1, col2 = st.columns(2)
    
    with col1:
        if not sentiment_df.empty:
            fig = chart_sentiment_score(sentiment_df)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Sentiment score chart not available")
        else:
            st.info("No sentiment data available")
    
    with col2:
        if not sentiment_df.empty:
            fig = chart_sentiment_polarity(sentiment_df)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Sentiment polarity not available")
        else:
            st.info("No sentiment data available")
    
    # Conviction and Narrative Strength
    col1, col2 = st.columns(2)
    
    with col1:
        if not sentiment_df.empty:
            fig = chart_sentiment_conviction(sentiment_df)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Conviction chart not available")
        else:
            st.info("No sentiment data available")
    
    with col2:
        if not sentiment_df.empty:
            fig = chart_narrative_strength(sentiment_df)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Narrative strength not available")
        else:
            st.info("No sentiment data available")
    
    # Macro Drivers
    st.subheader("Macro Drivers")
    col1, col2 = st.columns(2)
    
    with col1:
        if macro_state.is_available:
            # Convert macro state to DataFrame for heatmap
            macro_df = pd.DataFrame([macro_state.value])
            fig = chart_macro_driver_heatmap(macro_df)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Macro driver heatmap not available")
        else:
            st.info("No macro data available")
    
    with col2:
        if not sentiment_df.empty:
            fig = chart_macro_changes(sentiment_df)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Macro changes not available")
        else:
            st.info("No macro data available")
    
    # Regime Stability and Intelligence Freshness
    col1, col2 = st.columns(2)
    
    with col1:
        if not sentiment_df.empty:
            fig = chart_regime_stability(sentiment_df)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Regime stability not available")
        else:
            st.info("No regime data available")
    
    with col2:
        if not sentiment_df.empty:
            fig = chart_intelligence_freshness(sentiment_df)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Intelligence freshness not available")
        else:
            st.info("No intelligence data available")
    
    # Sentiment-Returns Correlation
    st.subheader("Sentiment-Returns Correlation")
    if not sentiment_df.empty and nav_df.is_available and not nav_df.value.empty:
        fig = chart_sentiment_returns_correlation(sentiment_df, nav_df.value)
        if fig:
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Correlation analysis not available")
    else:
        st.info("Insufficient data for correlation analysis")
    
    # Regime Duration Distribution
    st.subheader("Regime Duration Distribution")
    if not sentiment_df.empty:
        fig = chart_regime_duration_dist(sentiment_df)
        if fig:
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Regime duration distribution not available")
    else:
        st.info("No regime data available")
    
    # Current State Summary
    st.subheader("Current Intelligence State")
    col1, col2 = st.columns(2)
    
    with col1:
        if sentiment_state.is_available:
            st.json(sentiment_state.value)
        else:
            st.info("Sentiment state not available")
    
    with col2:
        if macro_state.is_available:
            st.json(macro_state.value)
        else:
            st.info("Macro state not available")
