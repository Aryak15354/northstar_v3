"""
Live Trading Tab - Real-Time Trading Activity
Displays current positions, intraday P&L, order flow, and execution quality
"""

import streamlit as st
import pandas as pd
from typing import Optional
from ..charts.chart_library import (
    chart_intraday_pnl,
    chart_position_tracking,
    chart_order_flow,
    chart_execution_quality,
    chart_slippage_analysis,
    chart_fill_rate,
    chart_market_impact,
    chart_execution_latency,
    chart_trade_size_distribution,
    chart_time_of_day_performance,
    chart_strategy_attribution_live,
    chart_realtime_risk_metrics
)


def render_live_trading_tab(data_contract):
    """Render the Live Trading tab with real-time metrics"""
    
    st.header("📊 Live Trading")
    st.caption("Real-time positions, P&L, and execution quality")
    
    # Get live trading data
    trades_df = data_contract.get_todays_trades()
    positions_df = data_contract.get_equity_positions()
    orders_df = data_contract.get_todays_orders()
    risk_df = data_contract.get_realtime_risk()
    
    # Key metrics row
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        intraday_pnl = data_contract.get_intraday_pnl()
        if intraday_pnl.is_available:
            pnl_value = intraday_pnl.value
            st.metric("Today's P&L", f"₹{pnl_value:,.0f}", 
                     delta=f"{(pnl_value/1000000):.2f}%" if pnl_value != 0 else None)
        else:
            st.metric("Today's P&L", "N/A")
    
    with col2:
        if trades_df.is_available and not trades_df.value.empty:
            trade_count = len(trades_df.value)
            st.metric("Trades Today", trade_count)
        else:
            st.metric("Trades Today", "0")
    
    with col3:
        if positions_df.is_available and not positions_df.value.empty:
            position_count = len(positions_df.value)
            total_notional = positions_df.value['notional_value'].sum() if 'notional_value' in positions_df.value.columns else 0
            st.metric("Open Positions", position_count, delta=f"₹{total_notional/1e6:.1f}M")
        else:
            st.metric("Open Positions", "0")
    
    with col4:
        if orders_df.is_available and not orders_df.value.empty:
            filled_orders = len(orders_df.value[orders_df.value['status'] == 'filled']) if 'status' in orders_df.value.columns else 0
            total_orders = len(orders_df.value)
            fill_rate = (filled_orders / total_orders * 100) if total_orders > 0 else 0
            st.metric("Fill Rate", f"{fill_rate:.1f}%", delta=f"{filled_orders}/{total_orders}")
        else:
            st.metric("Fill Rate", "N/A")
    
    st.divider()
    
    # Intraday P&L and Position Tracking
    st.subheader("Intraday Performance")
    col1, col2 = st.columns(2)
    
    with col1:
        if trades_df.is_available and not trades_df.value.empty:
            fig = chart_intraday_pnl(trades_df.value)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Intraday P&L chart not available")
        else:
            st.info("No trades today")
    
    with col2:
        if positions_df.is_available and not positions_df.value.empty:
            fig = chart_position_tracking(positions_df.value)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Position tracking chart not available")
        else:
            st.info("No open positions")
    
    # Order Flow and Execution Quality
    st.subheader("Order Flow & Execution")
    col1, col2 = st.columns(2)
    
    with col1:
        if orders_df.is_available and not orders_df.value.empty:
            fig = chart_order_flow(orders_df.value)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Order flow chart not available")
        else:
            st.info("No orders today")
    
    with col2:
        if trades_df.is_available and not trades_df.value.empty:
            fig = chart_execution_quality(trades_df.value)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Execution quality chart not available")
        else:
            st.info("No trades today")
    
    # Slippage and Fill Rate
    col1, col2 = st.columns(2)
    
    with col1:
        if trades_df.is_available and not trades_df.value.empty:
            fig = chart_slippage_analysis(trades_df.value)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Slippage analysis not available")
        else:
            st.info("No trades today")
    
    with col2:
        if orders_df.is_available and not orders_df.value.empty:
            fig = chart_fill_rate(orders_df.value)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Fill rate chart not available")
        else:
            st.info("No orders today")
    
    # Market Impact and Latency
    st.subheader("Execution Analytics")
    col1, col2 = st.columns(2)
    
    with col1:
        if trades_df.is_available and not trades_df.value.empty:
            fig = chart_market_impact(trades_df.value)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Market impact analysis not available")
        else:
            st.info("No trades today")
    
    with col2:
        if trades_df.is_available and not trades_df.value.empty:
            fig = chart_execution_latency(trades_df.value)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Execution latency chart not available")
        else:
            st.info("No trades today")
    
    # Trade Size and Time-of-Day Performance
    col1, col2 = st.columns(2)
    
    with col1:
        if trades_df.is_available and not trades_df.value.empty:
            fig = chart_trade_size_distribution(trades_df.value)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Trade size distribution not available")
        else:
            st.info("No trades today")
    
    with col2:
        if trades_df.is_available and not trades_df.value.empty:
            fig = chart_time_of_day_performance(trades_df.value)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Time-of-day performance not available")
        else:
            st.info("No trades today")
    
    # Strategy Attribution and Real-Time Risk
    st.subheader("Strategy & Risk")
    col1, col2 = st.columns(2)
    
    with col1:
        if trades_df.is_available and not trades_df.value.empty:
            fig = chart_strategy_attribution_live(trades_df.value)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Strategy attribution not available")
        else:
            st.info("No trades today")
    
    with col2:
        if risk_df.is_available and not risk_df.value.empty:
            fig = chart_realtime_risk_metrics(risk_df.value)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Real-time risk metrics not available")
        else:
            st.info("Risk metrics not available")
    
    # Detailed Trades Table
    st.subheader("Today's Trades")
    if trades_df.is_available and not trades_df.value.empty:
        display_cols = ['timestamp', 'ticker', 'side', 'quantity', 'execution_price', 'pnl']
        display_cols = [col for col in display_cols if col in trades_df.value.columns]
        
        st.dataframe(
            trades_df.value[display_cols].sort_values('timestamp', ascending=False),
            use_container_width=True,
            height=300
        )
    else:
        st.info("No trades today")
