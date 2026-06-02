"""
Portfolio Governor Tab - Portfolio Construction and Risk Management
Displays portfolio weights, correlation, Kelly sizing, and risk contribution
"""

import streamlit as st
import pandas as pd
from typing import Optional
from ..charts.chart_library import (
    chart_portfolio_weights,
    chart_cluster_exposure,
    chart_eigenvalue_spectrum,
    chart_correlation_heatmap,
    chart_kelly_multiplier,
    chart_exposure_multiplier,
    chart_gross_target_evolution,
    chart_capital_allocation_by_strategy,
    chart_risk_contribution,
    chart_sector_exposure
)


def render_governor_tab(data_contract):
    """Render the Portfolio Governor tab"""
    
    st.header("🏛️ Portfolio Governor")
    st.caption("Portfolio construction, risk management, and capital allocation")
    
    # Get governor data
    positions_df = data_contract.get_equity_positions()
    capital_structure = data_contract.get_capital_structure()
    governor_regime = data_contract.get_governor_regime()
    portfolio_history = data_contract.get_portfolio_history(lookback_days=30)
    sector_mapping = data_contract.get_sector_mapping()
    
    # Key metrics row
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if governor_regime.is_available:
            regime = governor_regime.value.get('regime', 'Unknown')
            st.metric("Governor Regime", regime)
        else:
            st.metric("Governor Regime", "N/A")
    
    with col2:
        if capital_structure.is_available:
            kelly_mult = capital_structure.value.get('kelly_multiplier', 0)
            st.metric("Kelly Multiplier", f"{kelly_mult:.2f}x")
        else:
            st.metric("Kelly Multiplier", "N/A")
    
    with col3:
        if capital_structure.is_available:
            exposure_mult = capital_structure.value.get('exposure_multiplier', 0)
            st.metric("Exposure Multiplier", f"{exposure_mult:.2f}x")
        else:
            st.metric("Exposure Multiplier", "N/A")
    
    with col4:
        if capital_structure.is_available:
            gross_target = capital_structure.value.get('gross_target', 0)
            st.metric("Gross Target", f"₹{gross_target/1e6:.1f}M")
        else:
            st.metric("Gross Target", "N/A")
    
    st.divider()
    
    # Portfolio Weights and Cluster Exposure
    st.subheader("Portfolio Composition")
    col1, col2 = st.columns(2)
    
    with col1:
        if positions_df.is_available and not positions_df.value.empty:
            fig = chart_portfolio_weights(positions_df.value)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Portfolio weights not available")
        else:
            st.info("No positions available")
    
    with col2:
        if positions_df.is_available and not positions_df.value.empty:
            fig = chart_cluster_exposure(positions_df.value)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Cluster exposure not available")
        else:
            st.info("No positions available")
    
    # Correlation Analysis
    st.subheader("Correlation & Risk Structure")
    
    # Get returns data for correlation
    returns_df = data_contract.get_portfolio_history(lookback_days=60)
    
    col1, col2 = st.columns(2)
    
    with col1:
        if returns_df.is_available and not returns_df.value.empty:
            fig = chart_correlation_heatmap(returns_df.value, crisis_mode=False)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Correlation heatmap not available")
        else:
            st.info("Insufficient data for correlation analysis")
    
    with col2:
        if returns_df.is_available and not returns_df.value.empty:
            fig = chart_eigenvalue_spectrum(returns_df.value)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Eigenvalue spectrum not available")
        else:
            st.info("Insufficient data for PCA analysis")
    
    # Kelly and Exposure Multipliers
    st.subheader("Capital Allocation Multipliers")
    col1, col2 = st.columns(2)
    
    with col1:
        if portfolio_history.is_available and not portfolio_history.value.empty:
            fig = chart_kelly_multiplier(portfolio_history.value)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Kelly multiplier history not available")
        else:
            st.info("No portfolio history")
    
    with col2:
        if portfolio_history.is_available and not portfolio_history.value.empty:
            fig = chart_exposure_multiplier(portfolio_history.value)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Exposure multiplier history not available")
        else:
            st.info("No portfolio history")
    
    # Gross Target and Capital Allocation
    col1, col2 = st.columns(2)
    
    with col1:
        if portfolio_history.is_available and not portfolio_history.value.empty:
            fig = chart_gross_target_evolution(portfolio_history.value)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Gross target evolution not available")
        else:
            st.info("No portfolio history")
    
    with col2:
        strategy_weights = data_contract.get_strategy_weights()
        if strategy_weights.is_available:
            # Convert to DataFrame for chart
            strategy_df = pd.DataFrame([strategy_weights.value])
            fig = chart_capital_allocation_by_strategy(strategy_df)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Capital allocation not available")
        else:
            st.info("No strategy weights available")
    
    # Risk Contribution and Sector Exposure
    st.subheader("Risk Analysis")
    col1, col2 = st.columns(2)
    
    with col1:
        if positions_df.is_available and not positions_df.value.empty:
            fig = chart_risk_contribution(positions_df.value)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Risk contribution not available")
        else:
            st.info("No positions available")
    
    with col2:
        if positions_df.is_available and not positions_df.value.empty:
            fig = chart_sector_exposure(positions_df.value, sector_mapping)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Sector exposure not available")
        else:
            st.info("No positions available")
    
    # Governor Decisions Log
    st.subheader("Recent Governor Decisions")
    governor_decisions = data_contract.get_governor_decisions(last_n=20)
    if governor_decisions.is_available and governor_decisions.value:
        decisions_df = pd.DataFrame(governor_decisions.value)
        st.dataframe(
            decisions_df,
            use_container_width=True,
            height=300
        )
    else:
        st.info("No governor decisions available")
    
    # Current Capital Structure
    st.subheader("Current Capital Structure")
    if capital_structure.is_available:
        col1, col2 = st.columns(2)
        
        with col1:
            st.json(capital_structure.value)
        
        with col2:
            if governor_regime.is_available:
                st.json(governor_regime.value)
    else:
        st.info("Capital structure not available")
