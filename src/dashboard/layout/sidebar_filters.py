#!/usr/bin/env python3
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from src.dashboard.models import DashboardFilters


ASSET_CLASS_OPTIONS = ("Equity", "Options", "Macro", "Sentiment", "Alternatives", "Research", "Alpha OS")


def _date_bounds(bundle: dict) -> tuple[date, date]:
    dates: list[pd.Series] = []
    for key in ["nav", "market_state", "daily_sentiment", "allocation_history", "state_history", "alpha_os_timeseries"]:
        df = bundle.get(key)
        if not isinstance(df, pd.DataFrame) or df.empty:
            continue
        for column in ["date", "Date", "timestamp"]:
            if column in df.columns:
                series = pd.to_datetime(df[column], errors="coerce").dropna()
                if not series.empty:
                    dates.append(series.dt.date)
                    break
    if not dates:
        today = date.today()
        return (today - timedelta(days=180), today)
    all_dates = pd.concat(dates, ignore_index=True)
    return (all_dates.min(), all_dates.max())


def _regime_options(bundle: dict) -> list[str]:
    options: set[str] = set()
    for key in ["market_state", "regime_history"]:
        df = bundle.get(key)
        if not isinstance(df, pd.DataFrame) or df.empty:
            continue
        for column in ["regime", "market_regime", "regime_name", "volatility_regime"]:
            if column in df.columns:
                options.update(df[column].dropna().astype(str).tolist())
    return sorted(option for option in options if option and option.lower() != "nan")


def _strategy_options(bundle: dict) -> list[str]:
    options: set[str] = set()
    for key, column in [("strategy_performance", "strategy_name"), ("strategy_beliefs", "strategy"), ("strategy_regret", "strategy_name"), ("strategy_weights", "strategy")]:
        df = bundle.get(key)
        if isinstance(df, pd.DataFrame) and not df.empty and column in df.columns:
            options.update(df[column].dropna().astype(str).tolist())
    allocation = bundle.get("allocation_history")
    if isinstance(allocation, pd.DataFrame) and not allocation.empty:
        meta_cols = {"date", "regime", "timestamp", "regime_name", "regime_stability", "exposure_cap", "total_exposure", "freeze_active", "cash", "momentum", "quality", "value"}
        options.update([col for col in allocation.columns if col not in meta_cols and allocation[col].dtype.kind in {"i", "u", "f"}])
    return sorted(option for option in options if option and option.lower() != "nan")


def render_sidebar_filters(bundle: dict) -> DashboardFilters:
    st.sidebar.markdown("## Control Tower")
    min_date, max_date = _date_bounds(bundle)
    default_start = max(min_date, max_date - timedelta(days=180))
    start_date, end_date = st.sidebar.date_input(
        "Date Range",
        value=(default_start, max_date),
        min_value=min_date,
        max_value=max_date,
    )
    regimes = st.sidebar.multiselect("Regime Filter", options=_regime_options(bundle))
    strategies = st.sidebar.multiselect("Strategy Filter", options=_strategy_options(bundle))
    asset_classes = st.sidebar.multiselect("Asset Class Filter", options=list(ASSET_CLASS_OPTIONS), default=list(ASSET_CLASS_OPTIONS))
    st.sidebar.markdown("---")
    show_manifest = st.sidebar.toggle("Show Data Manifest", value=False)
    auto_live_refresh = st.sidebar.toggle("Auto-refresh Live Tabs", value=True)
    if st.sidebar.button("Refresh All Dashboard Data", width="stretch"):
        st.cache_data.clear()
        st.cache_resource.clear()
        st.rerun()
    return DashboardFilters(
        start_date=start_date,
        end_date=end_date,
        regimes=tuple(regimes),
        strategies=tuple(strategies),
        asset_classes=tuple(asset_classes),
        show_manifest=show_manifest,
        auto_live_refresh=auto_live_refresh,
    )
