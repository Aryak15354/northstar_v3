"""
Valuation Tab - Buffett-Style Intrinsic Value Analysis
Displays valuation metrics, moat scores, DCF analysis, and earnings quality
"""

import streamlit as st
import pandas as pd
from typing import Optional
from ..charts.chart_library import (
    chart_buffett_intrinsic_value,
    chart_moat_score,
    chart_owner_earnings,
    chart_dcf_waterfall,
    chart_earnings_quality,
    chart_accounting_distortions,
    chart_normalized_financials,
    chart_sector_valuation,
    chart_value_vs_growth,
    chart_margin_of_safety
)


def render_valuation_tab(data_contract):
    """Render the Valuation tab with Buffett-style analysis"""
    
    st.header("📊 Valuation Analysis")
    st.caption("Buffett-style intrinsic value, moat scores, and earnings quality")
    
    # Get valuation data
    valuation_df = data_contract.get_valuation_summary()
    sector_mapping = data_contract.get_sector_mapping()
    
    if valuation_df is None or valuation_df.empty:
        st.warning("⚠️ No valuation data available")
        return
    
    # Key metrics row
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        undervalued_count = len(valuation_df[valuation_df['margin_of_safety'] > 25]) if 'margin_of_safety' in valuation_df.columns else 0
        st.metric("Undervalued Stocks", undervalued_count, help="Stocks with >25% margin of safety")
    
    with col2:
        avg_moat = valuation_df['moat_score'].mean() if 'moat_score' in valuation_df.columns else 0
        st.metric("Avg Moat Score", f"{avg_moat:.2f}/10", help="Average economic moat score")
    
    with col3:
        high_quality = len(valuation_df[valuation_df['earnings_quality'] > 7]) if 'earnings_quality' in valuation_df.columns else 0
        st.metric("High Quality Earnings", high_quality, help="Stocks with earnings quality >7")
    
    with col4:
        median_pe = valuation_df['pe_ratio'].median() if 'pe_ratio' in valuation_df.columns else 0
        st.metric("Median P/E", f"{median_pe:.1f}x", help="Median P/E ratio across universe")
    
    st.divider()
    
    # Intrinsic Value Analysis
    st.subheader("Intrinsic Value vs Market Price")
    col1, col2 = st.columns(2)
    
    with col1:
        fig = chart_buffett_intrinsic_value(valuation_df)
        if fig:
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Intrinsic value data not available")
    
    with col2:
        fig = chart_margin_of_safety(valuation_df)
        if fig:
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Margin of safety data not available")
    
    # Economic Moat Analysis
    st.subheader("Economic Moat & Competitive Advantage")
    col1, col2 = st.columns(2)
    
    with col1:
        fig = chart_moat_score(valuation_df)
        if fig:
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Moat score data not available")
    
    with col2:
        fig = chart_value_vs_growth(valuation_df)
        if fig:
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Value vs growth data not available")
    
    # Earnings Quality
    st.subheader("Earnings Quality & Accounting Integrity")
    col1, col2 = st.columns(2)
    
    with col1:
        fig = chart_owner_earnings(valuation_df)
        if fig:
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Owner earnings data not available")
    
    with col2:
        fig = chart_earnings_quality(valuation_df)
        if fig:
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Earnings quality data not available")
    
    # Accounting Distortions & Normalized Metrics
    col1, col2 = st.columns(2)
    
    with col1:
        fig = chart_accounting_distortions(valuation_df)
        if fig:
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Accounting distortion data not available")
    
    with col2:
        fig = chart_normalized_financials(valuation_df, metric='roe')
        if fig:
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Normalized financials data not available")
    
    # Sector Analysis
    st.subheader("Sector Valuation Comparison")
    fig = chart_sector_valuation(valuation_df, sector_mapping)
    if fig:
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Sector valuation data not available")
    
    # DCF Waterfall (for selected stock)
    st.subheader("DCF Valuation Waterfall")
    
    if 'ticker' in valuation_df.columns:
        selected_ticker = st.selectbox(
            "Select stock for DCF analysis",
            options=valuation_df['ticker'].unique()[:50],  # Limit to first 50 for performance
            help="View detailed DCF breakdown for selected stock"
        )
        
        if selected_ticker:
            dcf_data = data_contract.get_dcf_components(selected_ticker)
            if dcf_data:
                fig = chart_dcf_waterfall(selected_ticker, dcf_data)
                if fig:
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info(f"DCF waterfall not available for {selected_ticker}")
            else:
                st.info(f"DCF components not available for {selected_ticker}")
    
    # Top Opportunities Table
    st.subheader("Top Investment Opportunities")
    st.caption("Stocks with high moat scores and attractive valuations")
    
    if all(col in valuation_df.columns for col in ['ticker', 'moat_score', 'margin_of_safety', 'earnings_quality']):
        opportunities = valuation_df[
            (valuation_df['moat_score'] > 6) &
            (valuation_df['margin_of_safety'] > 15) &
            (valuation_df['earnings_quality'] > 6)
        ].sort_values('margin_of_safety', ascending=False).head(20)
        
        if not opportunities.empty:
            display_cols = ['ticker', 'intrinsic_value', 'market_price', 'margin_of_safety', 
                          'moat_score', 'earnings_quality', 'pe_ratio']
            display_cols = [col for col in display_cols if col in opportunities.columns]
            
            st.dataframe(
                opportunities[display_cols].style.format({
                    'intrinsic_value': '₹{:.2f}',
                    'market_price': '₹{:.2f}',
                    'margin_of_safety': '{:.1f}%',
                    'moat_score': '{:.2f}',
                    'earnings_quality': '{:.2f}',
                    'pe_ratio': '{:.1f}x'
                }),
                use_container_width=True,
                height=400
            )
        else:
            st.info("No stocks currently meet the quality criteria")
    else:
        st.info("Opportunity screening data not available")
