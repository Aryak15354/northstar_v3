#!/usr/bin/env python3
"""
Legacy dashboard extension methods.
Kept intentionally lightweight and syntax-safe.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st


def render_dynamic_clustering(self) -> None:
    """Render a compact clustering view using adapter market series when available."""
    st.markdown("## Dynamic Clustering")

    if not hasattr(self, "adapter") or self.adapter is None:
        st.info("Adapter unavailable")
        return

    market_df = self.adapter.market_ts(window="3M")
    if market_df is None or market_df.empty:
        st.info("No market series available")
        return

    numeric = market_df.select_dtypes(include=["number"]).dropna(how="all")
    if numeric.shape[1] < 2 or len(numeric) < 5:
        st.info("Insufficient numeric features for clustering")
        return

    cols = numeric.columns[:2]
    plot_df = numeric[list(cols)].dropna().copy()
    if plot_df.empty:
        st.info("No clean data for plotting")
        return

    # Lightweight pseudo-cluster labels to avoid heavy dependencies in this legacy module.
    q = pd.qcut(plot_df[cols[0]].rank(method="first"), q=3, labels=["L", "M", "H"])
    plot_df["cluster"] = q.astype(str)

    fig = px.scatter(
        plot_df,
        x=cols[0],
        y=cols[1],
        color="cluster",
        title="Market Feature Clusters",
    )
    st.plotly_chart(fig, width="stretch")


def render_fallback_clustering(self, n_clusters: int, clustering_method: str) -> None:
    """Legacy fallback helper."""
    st.info(f"Fallback clustering: method={clustering_method}, clusters={n_clusters}")


def render_wave_analysis(self) -> None:
    """Render a simple wave/trend panel from NIFTY series."""
    st.markdown("## Wave Analysis")

    if not hasattr(self, "adapter") or self.adapter is None:
        st.info("Adapter unavailable")
        return

    ts = self.adapter.portfolio_ts(view="Absolute")
    if ts is None or ts.empty or "portfolio" not in ts.columns:
        st.info("No portfolio series available")
        return

    s = pd.to_numeric(ts["portfolio"], errors="coerce").dropna()
    if len(s) < 10:
        st.info("Insufficient history for wave analysis")
        return

    trend = s.rolling(5).mean()
    wave = s - trend

    st.metric("Latest Trend", f"{float(trend.iloc[-1]):.4f}")
    st.metric("Latest Wave", f"{float(wave.iloc[-1]):+.4f}")

    fig = px.line(
        pd.DataFrame({"portfolio": s, "trend": trend, "wave": wave}),
        y=["portfolio", "trend"],
        title="Portfolio vs Trend",
    )
    st.plotly_chart(fig, width="stretch")
