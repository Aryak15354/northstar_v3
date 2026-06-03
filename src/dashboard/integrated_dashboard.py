#!/usr/bin/env python3
from __future__ import annotations

from typing import Callable

import pandas as pd
import streamlit as st

from src.dashboard.data.data_manager import (
    apply_dashboard_filters,
    compose_dashboard_bundle,
    load_intraday_market_sentiment_data,
    load_live_options_data,
    load_risk_runtime_data,
    load_static_data,
)
from src.dashboard.data.live_data_manager import maybe_refresh_live_data
from src.dashboard.layout.global_bar import inject_dashboard_styles, render_global_bar
from src.dashboard.layout.sidebar_filters import render_sidebar_filters
from src.dashboard.layout.tab_router import render_tab_router
from src.dashboard.registry import LIVE_TABS, TAB_ORDER, VISUALS
from src.dashboard.sections import (
    render_alpha_os,
    render_market,
    render_options,
    render_overview,
    render_performance,
    render_portfolio,
    render_research,
    render_risk,
    render_sentiment,
)

SECTION_RENDERERS: dict[str, Callable[[dict], tuple[int, int]]] = {
    "Overview": render_overview,
    "Performance": render_performance,
    "Market": render_market,
    "Sentiment": render_sentiment,
    "Portfolio": render_portfolio,
    "Risk": render_risk,
    "Options": render_options,
    "Research": render_research,
    "Alpha OS": render_alpha_os,
}


def _render_data_manifest(bundle: dict) -> None:
    manifest = bundle.get("pipeline_freshness")
    if not isinstance(manifest, pd.DataFrame) or manifest.empty:
        return
    st.dataframe(
        manifest.sort_values("age_hours", ascending=True),
        width="stretch",
        hide_index=True,
    )


@st.fragment(run_every=300)
def _render_global_bar_fragment(static_bundle: dict) -> None:
    maybe_refresh_live_data(force=False)
    intraday_bundle = load_intraday_market_sentiment_data()
    runtime_bundle = load_risk_runtime_data()
    bundle = compose_dashboard_bundle(static_bundle, intraday_bundle=intraday_bundle, runtime_bundle=runtime_bundle)
    render_global_bar(bundle)


@st.fragment(run_every=300)
def _render_live_tab_fragment(active_tab: str, static_bundle: dict, filters) -> tuple[int, int]:
    if filters.auto_live_refresh:
        maybe_refresh_live_data(force=False)
    current_static_bundle = load_static_data()
    intraday_bundle = load_intraday_market_sentiment_data()
    live_bundle = load_live_options_data()
    runtime_bundle = load_risk_runtime_data()
    bundle = compose_dashboard_bundle(
        current_static_bundle or static_bundle,
        intraday_bundle=intraday_bundle,
        live_bundle=live_bundle,
        runtime_bundle=runtime_bundle,
    )
    filtered = apply_dashboard_filters(bundle, filters)
    return SECTION_RENDERERS[active_tab](filtered)


def render_dashboard() -> None:
    inject_dashboard_styles()
    st.session_state["dashboard_visual_issues"] = []

    static_bundle = load_static_data()
    filters = render_sidebar_filters(static_bundle)
    active_tab = render_tab_router()

    _render_global_bar_fragment(static_bundle)

    if filters.show_manifest:
        with st.expander("Data Manifest & Freshness", expanded=False):
            _render_data_manifest(
                compose_dashboard_bundle(
                    static_bundle,
                    intraday_bundle=load_intraday_market_sentiment_data(),
                    runtime_bundle=load_risk_runtime_data(),
                )
            )

    if active_tab in LIVE_TABS:
        rendered, total = _render_live_tab_fragment(active_tab, static_bundle, filters)
    else:
        intraday_bundle = load_intraday_market_sentiment_data()
        runtime_bundle = load_risk_runtime_data()
        bundle = compose_dashboard_bundle(static_bundle, intraday_bundle=intraday_bundle, runtime_bundle=runtime_bundle)
        filtered = apply_dashboard_filters(bundle, filters)
        rendered, total = SECTION_RENDERERS[active_tab](filtered)

    issues = len(st.session_state.get("dashboard_visual_issues", []))
    st.markdown("---")
    st.caption(
        f"Rendered `{rendered}` of `{total}` active visuals for `{active_tab}`. "
        f"Canonical dashboard registry contains `{len(VISUALS)}` real-data modules across `{len(TAB_ORDER)}` sections. "
        f"Unavailable panels this run: `{issues}`."
    )
