"""
Performance Tab - Historical Returns and Risk Metrics
Displays capital curve, Sharpe ratio, drawdown, and performance statistics
"""

import streamlit as st
import pandas as pd
from typing import Optional
from ..charts.chart_library import (
    chart_capital_curve,
    chart_rolling_sharpe,
    chart_max_drawdown,
    chart_survival_probability,
    chart_daily_returns_dist,
    chart_monthly_returns_heatmap,
    chart_cumulative_vs_benchmark,
    chart_rolling_volatility,
    chart_win_rate,
    chart_profit_factor,
    chart_risk_adjusted_returns,
    chart_drawdown_duration,
    chart_nav_history,
    chart_underwater_plot,
    chart_returns_quantiles
)


def render_performance_tab(data_contract):
    """Render the Performance tab with historical metrics"""
    
    st.header("📈 Performance Analysis")
    st.caption("Historical returns, risk metrics, and performance statistics")
    
    # Get performance data
    nav_df = data_contract.get_nav_history(lookback_days=180)
    perf_metrics = data_contract.get_performance_metrics()
    benchmark_df = data_contract.get_benchmark_returns(lookback_days=180)
    
    if not nav_df.is_available or nav_df.value.empty:
        st.warning("⚠️ No performance data available")
        return
    
    # Key metrics row
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if perf_metrics.is_available:
            total_return = perf_metrics.value.get('total_return_pct', 0)
            st.metric("Total Return", f"{total_return:.2f}%")
        else:
            st.metric("Total Return", "N/A")
    
    with col2:
        if perf_metrics.is_available:
            sharpe = perf_metrics.value.get('sharpe_ratio', 0)
            st.metric("Sharpe Ratio", f"{sharpe:.2f}")
        else:
            st.metric("Sharpe Ratio", "N/A")
    
    with col3:
        if perf_metrics.is_available:
            max_dd = perf_metrics.value.get('max_drawdown_pct', 0)
            st.metric("Max Drawdown", f"{max_dd:.2f}%")
        else:
            st.metric("Max Drawdown", "N/A")
    
    with col4:
        if perf_metrics.is_available:
            win_rate = perf_metrics.value.get('win_rate_pct', 0)
            st.metric("Win Rate", f"{win_rate:.1f}%")
        else:
            st.metric("Win Rate", "N/A")
    
    st.divider()
    
    # Capital Curve and Sharpe Ratio
    st.subheader("Capital Growth & Risk-Adjusted Returns")
    col1, col2 = st.columns(2)
    
    with col1:
        fig = chart_capital_curve(nav_df.value)
        if fig:
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Capital curve not available")
    
    with col2:
        fig = chart_rolling_sharpe(nav_df.value)
        if fig:
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Rolling Sharpe not available")
    
    # Drawdown Analysis
    st.subheader("Drawdown Analysis")
    col1, col2 = st.columns(2)
    
    with col1:
        fig = chart_max_drawdown(nav_df.value)
        if fig:
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Drawdown chart not available")
    
    with col2:
        fig = chart_underwater_plot(nav_df.value)
        if fig:
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Underwater plot not available")
    
    # Returns Distribution
    st.subheader("Returns Distribution")
    col1, col2 = st.columns(2)
    
    with col1:
        fig = chart_daily_returns_dist(nav_df.value)
        if fig:
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Returns distribution not available")
    
    with col2:
        fig = chart_returns_quantiles(nav_df.value)
        if fig:
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Returns quantiles not available")
    
    # Monthly Heatmap
    st.subheader("Monthly Returns Heatmap")
    fig = chart_monthly_returns_heatmap(nav_df.value)
    if fig:
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Monthly heatmap not available")
    
    # Benchmark Comparison
    st.subheader("Benchmark Comparison")
    if benchmark_df.is_available and not benchmark_df.value.empty:
        fig = chart_cumulative_vs_benchmark(nav_df.value, benchmark_df.value)
        if fig:
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Benchmark comparison not available")
    else:
        st.info("Benchmark data not available")
    
    # Volatility and Win Rate
    st.subheader("Volatility & Win Rate")
    col1, col2 = st.columns(2)
    
    with col1:
        fig = chart_rolling_volatility(nav_df.value)
        if fig:
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Rolling volatility not available")
    
    with col2:
        fig = chart_win_rate(nav_df.value)
        if fig:
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Win rate chart not available")
    
    # Profit Factor and Risk-Adjusted Returns
    col1, col2 = st.columns(2)
    
    with col1:
        fig = chart_profit_factor(nav_df.value)
        if fig:
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Profit factor not available")
    
    with col2:
        fig = chart_risk_adjusted_returns(nav_df.value)
        if fig:
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Risk-adjusted returns not available")
    
    # Drawdown Duration and Survival Probability
    col1, col2 = st.columns(2)
    
    with col1:
        fig = chart_drawdown_duration(nav_df.value)
        if fig:
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Drawdown duration not available")
    
    with col2:
        fig = chart_survival_probability(nav_df.value)
        if fig:
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Survival probability not available")
    
    # NAV History Table
    st.subheader("NAV History")
    if nav_df.is_available and not nav_df.value.empty:
        display_cols = ['date', 'nav', 'daily_return', 'cumulative_return']
        display_cols = [col for col in display_cols if col in nav_df.value.columns]
        
        st.dataframe(
            nav_df.value[display_cols].tail(30).sort_values('date', ascending=False),
            use_container_width=True,
            height=300
        )
    else:
        st.info("NAV history not available")
