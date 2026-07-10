#!/usr/bin/env python3
from __future__ import annotations

from collections import defaultdict
from typing import Iterable

import streamlit as st

from src.dashboard.components.cards import render_placeholder_card, render_section_intro
from src.dashboard.components.narrative_blocks import render_narrative_block
from src.dashboard.layout.terminal_theme import apply_terminal_layout
from src.dashboard.registry import ADVANCED, PRIMARY, SECONDARY, DashboardVisualSpec, get_visuals_for_tab
from src.dashboard import freshness as _freshness


def _metadata_text(spec: DashboardVisualSpec) -> str:
    return f"{spec.refresh_frequency} | {spec.data_source}"


def _declutter(fig):
    """The card header already shows the title, so drop the in-figure title to
    stop it overlapping the plot. NOTE: setting title_text=None makes Plotly.js
    render the literal string "undefined" in the top-left, so we blank it with an
    empty string instead. Subplot-title figures get extra top margin + height so
    the per-panel headings don't collide with the traces."""
    if fig is None:
        return fig
    try:
        has_subplot_titles = bool(getattr(fig.layout, "annotations", None))
        fig.update_layout(title=dict(text=""), margin=dict(t=48 if has_subplot_titles else 18))
        if not fig.layout.height:
            fig.update_layout(height=460 if has_subplot_titles else 380)
    except Exception:
        return fig
    return fig


def _freshness_badge(spec: DashboardVisualSpec) -> tuple[str, str]:
    """(badge_html, status) — never let a badge computation break a panel."""
    try:
        fr = _freshness.spec_freshness(spec)
        # record stale/missing so the tab summary + Data Truth Panel can count them
        if fr["status"] in (_freshness.STATUS_STALE, _freshness.STATUS_MISSING):
            stale = st.session_state.setdefault("dashboard_stale_visuals", [])
            stale.append((spec.visual_id, fr["status"], fr.get("detail")))
        return _freshness.badge_html(fr), fr["status"]
    except Exception:
        return "", _freshness.STATUS_UNKNOWN


def render_visual(spec: DashboardVisualSpec, bundle: dict) -> bool:
    fig = spec.builder(bundle)
    fig = _declutter(apply_terminal_layout(fig))  # terminal look + no title overlap
    badge_html, status = _freshness_badge(spec)
    if fig is None:
        issues = st.session_state.setdefault("dashboard_visual_issues", [])
        issues.append(spec.visual_id)
        render_placeholder_card(spec.title, "The required real-data surface is missing, sparse, or currently stale for this panel.", _metadata_text(spec))
        return False

    stale_class = " ns-visual-stale" if status in (_freshness.STATUS_STALE, _freshness.STATUS_MISSING) else ""
    st.markdown(
        f"""
        <div class="ns-visual-card{stale_class}">
            <div class="ns-visual-title">{spec.title}</div>
            <div class="ns-visual-description">{spec.description}</div>
            <div class="ns-visual-freshness">{badge_html}</div>
            <div class="ns-visual-meta">{_metadata_text(spec)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.plotly_chart(
        fig,
        width="stretch",
        key=f"plotly_{spec.visual_id}",
        config={"displaylogo": False, "responsive": True},
    )
    return True


def _render_spec_grid(specs: Iterable[DashboardVisualSpec], bundle: dict) -> tuple[int, int]:
    spec_list = list(specs)
    rendered = 0
    total = len(spec_list)
    idx = 0
    while idx < len(spec_list):
        spec = spec_list[idx]
        # Multi-panel cockpits render full-width; everything else pairs up.
        if getattr(spec, "wide", False):
            rendered += 1 if render_visual(spec, bundle) else 0
            idx += 1
            continue
        pair = [spec]
        if idx + 1 < len(spec_list) and not getattr(spec_list[idx + 1], "wide", False):
            pair.append(spec_list[idx + 1])
        cols = st.columns(2)
        for col, s in zip(cols, pair):
            with col:
                rendered += 1 if render_visual(s, bundle) else 0
        idx += len(pair)
    return rendered, total


def render_visual_section(tab: str, bundle: dict, subtitle: str) -> tuple[int, int]:
    render_section_intro(tab, subtitle)
    render_narrative_block(tab, bundle)
    specs = get_visuals_for_tab(tab)
    primary = [spec for spec in specs if spec.level == PRIMARY]
    secondary = [spec for spec in specs if spec.level == SECONDARY]
    advanced = [spec for spec in specs if spec.level == ADVANCED]

    rendered = 0
    total = 0

    primary_rendered, primary_total = _render_spec_grid(primary, bundle)
    rendered += primary_rendered
    total += primary_total

    if secondary:
        with st.expander("Advanced Analytics", expanded=False):
            secondary_rendered, secondary_total = _render_spec_grid(secondary, bundle)
            rendered += secondary_rendered
            total += secondary_total

    if advanced:
        grouped: dict[str, list[DashboardVisualSpec]] = defaultdict(list)
        for spec in advanced:
            grouped[spec.subsection].append(spec)
        tabs = st.tabs(list(grouped.keys()))
        for tab_container, subsection in zip(tabs, grouped.keys()):
            with tab_container:
                advanced_rendered, advanced_total = _render_spec_grid(grouped[subsection], bundle)
                rendered += advanced_rendered
                total += advanced_total

    return rendered, total
