"""
Options System Tab - Options Greeks, IV Surface, and Hedge Analysis
Displays options positions, Greeks, volatility analysis, and hedge effectiveness
"""

import streamlit as st
import pandas as pd
from typing import Optional
from ..charts.chart_library import (
    chart_greeks_heatmap,
    chart_iv_surface_3d,
    chart_implied_vs_realized_vol,
    chart_volatility_smile,
    chart_options_pnl_attribution,
    chart_hedge_effectiveness,
    chart_gamma_exposure_by_strike,
    chart_vega_exposure_by_expiry,
    chart_theta_decay_timeline,
    chart_options_position_sizing,
    chart_strike_distribution,
    chart_expiry_calendar,
    chart_volatility_regime,
    chart_options_strategy_performance,
    chart_greeks_evolution
)


def render_options_tab(data_contract):
    """Render the Options System tab"""
    
    st.header("⚡ Options System")
    st.caption("Options Greeks, IV surface, volatility analysis, and hedge effectiveness")
    
    # Get options data
    options_positions = data_contract.get_options_positions()
    greeks = data_contract.get_options_greeks()
    iv_surface = data_contract.get_iv_surface_data()
    greeks_history = data_contract.get_greeks_history(lookback_days=30)
    
    # Key metrics row
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if options_positions.is_available:
            # Handle both dict and DataFrame
            if isinstance(options_positions.value, dict):
                position_count = len(options_positions.value)
            elif hasattr(options_positions.value, 'empty') and not options_positions.value.empty:
                position_count = len(options_positions.value)
            else:
                position_count = 0
            st.metric("Options Positions", position_count)
        else:
            st.metric("Options Positions", "0")
    
    with col2:
        if greeks.is_available:
            net_delta = greeks.value.get('delta', 0)
            st.metric("Net Delta", f"{net_delta:.2f}")
        else:
            st.metric("Net Delta", "N/A")
    
    with col3:
        if greeks.is_available:
            net_gamma = greeks.value.get('gamma', 0)
            st.metric("Net Gamma", f"{net_gamma:.4f}")
        else:
            st.metric("Net Gamma", "N/A")
    
    with col4:
        if greeks.is_available:
            net_vega = greeks.value.get('vega', 0)
            st.metric("Net Vega", f"{net_vega:.2f}")
        else:
            st.metric("Net Vega", "N/A")
    
    st.divider()
    
    # Greeks Heatmap and IV Surface
    st.subheader("Greeks & Implied Volatility")
    col1, col2 = st.columns(2)
    
    with col1:
        if options_positions.is_available and not options_positions.value.empty:
            fig = chart_greeks_heatmap(options_positions.value)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Greeks heatmap not available")
        else:
            st.info("No options positions")
    
    with col2:
        if iv_surface.is_available and not iv_surface.value.empty:
            fig = chart_iv_surface_3d(iv_surface.value)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("IV surface not available")
        else:
            st.info("No IV surface data")
    
    # Volatility Analysis
    st.subheader("Volatility Analysis")
    col1, col2 = st.columns(2)
    
    with col1:
        if iv_surface.is_available and not iv_surface.value.empty:
            fig = chart_implied_vs_realized_vol(iv_surface.value)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Implied vs realized vol not available")
        else:
            st.info("No volatility data")
    
    with col2:
        if iv_surface.is_available and not iv_surface.value.empty:
            fig = chart_volatility_smile(iv_surface.value)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Volatility smile not available")
        else:
            st.info("No volatility data")
    
    # P&L Attribution and Hedge Effectiveness
    st.subheader("P&L & Hedge Analysis")
    col1, col2 = st.columns(2)
    
    with col1:
        if options_positions.is_available and not options_positions.value.empty:
            fig = chart_options_pnl_attribution(options_positions.value)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("P&L attribution not available")
        else:
            st.info("No options positions")
    
    with col2:
        if options_positions.is_available and not options_positions.value.empty:
            fig = chart_hedge_effectiveness(options_positions.value)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Hedge effectiveness not available")
        else:
            st.info("No options positions")
    
    # Greeks Exposure by Strike and Expiry
    st.subheader("Greeks Exposure Distribution")
    col1, col2 = st.columns(2)
    
    with col1:
        if options_positions.is_available and not options_positions.value.empty:
            fig = chart_gamma_exposure_by_strike(options_positions.value)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Gamma exposure not available")
        else:
            st.info("No options positions")
    
    with col2:
        if options_positions.is_available and not options_positions.value.empty:
            fig = chart_vega_exposure_by_expiry(options_positions.value)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Vega exposure not available")
        else:
            st.info("No options positions")
    
    # Theta Decay and Position Sizing
    col1, col2 = st.columns(2)
    
    with col1:
        if options_positions.is_available and not options_positions.value.empty:
            fig = chart_theta_decay_timeline(options_positions.value)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Theta decay not available")
        else:
            st.info("No options positions")
    
    with col2:
        if options_positions.is_available and not options_positions.value.empty:
            fig = chart_options_position_sizing(options_positions.value)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Position sizing not available")
        else:
            st.info("No options positions")
    
    # Strike Distribution and Expiry Calendar
    st.subheader("Position Distribution")
    col1, col2 = st.columns(2)
    
    with col1:
        if options_positions.is_available and not options_positions.value.empty:
            fig = chart_strike_distribution(options_positions.value)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Strike distribution not available")
        else:
            st.info("No options positions")
    
    with col2:
        if options_positions.is_available and not options_positions.value.empty:
            fig = chart_expiry_calendar(options_positions.value)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Expiry calendar not available")
        else:
            st.info("No options positions")
    
    # Volatility Regime and Strategy Performance
    col1, col2 = st.columns(2)
    
    with col1:
        if iv_surface.is_available and not iv_surface.value.empty:
            fig = chart_volatility_regime(iv_surface.value)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Volatility regime not available")
        else:
            st.info("No volatility data")
    
    with col2:
        if options_positions.is_available and not options_positions.value.empty:
            fig = chart_options_strategy_performance(options_positions.value)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Strategy performance not available")
        else:
            st.info("No options positions")
    
    # Greeks Evolution
    st.subheader("Greeks Evolution Over Time")
    if greeks_history.is_available and not greeks_history.value.empty:
        fig = chart_greeks_evolution(greeks_history.value)
        if fig:
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Greeks evolution not available")
    else:
        st.info("No Greeks history available")
    
    # Options Positions Table
    st.subheader("Current Options Positions")
    if options_positions.is_available and not options_positions.value.empty:
        display_cols = ['symbol', 'strike', 'expiry', 'option_type', 'quantity', 'delta', 'gamma', 'vega', 'theta']
        display_cols = [col for col in display_cols if col in options_positions.value.columns]
        
        st.dataframe(
            options_positions.value[display_cols],
            use_container_width=True,
            height=300
        )
    else:
        st.info("No options positions")
