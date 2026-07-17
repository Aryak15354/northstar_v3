#!/usr/bin/env python3
from __future__ import annotations

import streamlit as st

from src.dashboard.registry import TAB_ORDER, visual_counts_by_tab

TAB_STATE_KEY = "northstar_active_tab"


def _format_tab_label(tab: str, counts: dict[str, int]) -> str:
    n = counts.get(tab, 0)
    # Function pages (e.g. Security/DES) have no registry visuals — plain label.
    return f"{tab} ({n})" if n else tab


def _normalize_active_tab() -> str:
    selected = st.session_state.get(TAB_STATE_KEY)
    if selected in TAB_ORDER:
        return selected

    fallback = TAB_ORDER[0]
    st.session_state[TAB_STATE_KEY] = fallback
    return fallback


def render_tab_router() -> str:
    counts = visual_counts_by_tab()
    _normalize_active_tab()
    selected = st.segmented_control(
        "Dashboard Surface",
        options=TAB_ORDER,
        format_func=lambda tab: _format_tab_label(tab, counts),
        key=TAB_STATE_KEY,
    )
    if selected in TAB_ORDER:
        return selected
    return _normalize_active_tab()
