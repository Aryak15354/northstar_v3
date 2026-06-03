#!/usr/bin/env python3
from __future__ import annotations

from collections import defaultdict
from typing import Iterable

import streamlit as st

from src.dashboard.components.cards import render_placeholder_card, render_section_intro
from src.dashboard.components.narrative_blocks import render_narrative_block
from src.dashboard.registry import ADVANCED, PRIMARY, SECONDARY, DashboardVisualSpec, get_visuals_for_tab


def _metadata_text(spec: DashboardVisualSpec) -> str:
    return f"{spec.refresh_frequency} | {spec.data_source}"


def render_visual(spec: DashboardVisualSpec, bundle: dict) -> bool:
    fig = spec.builder(bundle)
    if fig is None:
        issues = st.session_state.setdefault("dashboard_visual_issues", [])
        issues.append(spec.visual_id)
        render_placeholder_card(spec.title, "The required real-data surface is missing, sparse, or currently stale for this panel.", _metadata_text(spec))
        return False

    st.markdown(
        f"""
        <div class="ns-visual-card">
            <div class="ns-visual-title">{spec.title}</div>
            <div class="ns-visual-description">{spec.description}</div>
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
    for idx in range(0, len(spec_list), 2):
        cols = st.columns(2)
        for col, spec in zip(cols, spec_list[idx : idx + 2]):
            with col:
                rendered += 1 if render_visual(spec, bundle) else 0
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
