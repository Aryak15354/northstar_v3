#!/usr/bin/env python3
from __future__ import annotations

from collections import defaultdict

import pandas as pd
import streamlit as st

from src.dashboard.components.cards import render_section_intro
from src.dashboard.components.narrative_blocks import render_narrative_block
from src.dashboard.data.live_data_manager import live_status_from_bundle
from src.dashboard.registry import get_visuals_for_tab
from src.dashboard.sections.shared import render_visual


def _render_runtime_audit(bundle: dict) -> None:
    audit = bundle.get("options_runtime_audit") or {}
    if not isinstance(audit, dict) or not audit:
        return

    st.subheader("Runtime Consistency")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Runtime Open", f"{int(audit.get('runtime_open_positions', 0) or 0):,d}")
    col2.metric("Ledger Open", f"{int(audit.get('ledger_open_positions', 0) or 0):,d}")
    col3.metric("Repaired Rows", f"{int(audit.get('repaired_stale_lifecycle_rows', 0) or 0):,d}")
    col4.metric("Lifecycle Open", f"{int(audit.get('remaining_open_lifecycle_rows', 0) or 0):,d}")
    st.caption(f"Options runtime audit status: `{audit.get('status', 'unknown')}` at `{audit.get('timestamp', 'unknown')}`")


def _render_position_tables(bundle: dict) -> None:
    active_positions = bundle.get("active_option_positions")
    history = bundle.get("options_trade_history")

    st.subheader("Options Position Lifecycle")

    if isinstance(active_positions, pd.DataFrame) and not active_positions.empty:
        st.markdown("**Active Positions**")
        keep = [col for col in ["underlying", "strategy_type", "option_type", "strike", "quantity", "delta", "gamma", "theta", "vega"] if col in active_positions.columns]
        st.dataframe(active_positions[keep] if keep else active_positions, width="stretch", hide_index=True)
    else:
        st.info("No option positions are currently open.")

    if isinstance(history, pd.DataFrame) and not history.empty:
        st.markdown("**Recent Closed / Opened Trades**")
        keep = [col for col in ["status", "position_id", "underlying", "strategy_type", "entry_time", "exit_time", "objective", "reason", "exit_reason", "realized_pnl", "gross_pnl", "unrealized_pnl", "hedge_intensity", "protected_symbols_count"] if col in history.columns]
        st.dataframe(history[keep] if keep else history, width="stretch", hide_index=True)
    else:
        runtime = bundle.get("options_runtime_state") or {}
        closed_count = int(len(runtime.get("closed_positions") or []))
        if closed_count > 0:
            st.warning("Closed option positions exist in runtime state, but the published trade-history artifact is missing.")
        else:
            st.info("No option trade history has been published yet.")


def render(bundle: dict) -> tuple[int, int]:
    render_section_intro("Options", "Dedicated live options surface with market structure, flows, Greeks, and runtime overlays.")
    render_narrative_block("Options", bundle)

    _, freshness_label, _ = live_status_from_bundle(bundle)
    st.caption(f"Freshness badge: `{freshness_label}`")

    grouped = defaultdict(list)
    for spec in get_visuals_for_tab("Options"):
        grouped[spec.subsection].append(spec)

    # "Suggestions Cockpit" first: the v3-driven shorts/longs/hedges/opportunities.
    # Any subsection present in the registry but not pre-listed is appended so
    # new visual groups are never silently dropped.
    ordered = ["Suggestions Cockpit", "Market Surface", "Flow & Positioning", "Greeks Engine", "Risk Layer"]
    for sub in grouped:
        if sub not in ordered:
            ordered.append(sub)
    ordered = [s for s in ordered if grouped.get(s)]  # drop empty subsections
    tabs = st.tabs(ordered)
    rendered = 0
    total = 0
    for tab_container, subsection in zip(tabs, ordered):
        specs = grouped.get(subsection, [])
        with tab_container:
            # Suggestions Cockpit renders full-width (one per row) so the
            # book table and risk/reward map are large and legible.
            per_row = 1 if subsection == "Suggestions Cockpit" else 2
            for idx in range(0, len(specs), per_row):
                cols = st.columns(per_row)
                for col, spec in zip(cols, specs[idx : idx + per_row]):
                    with col:
                        rendered += 1 if render_visual(spec, bundle) else 0
                        total += 1

    # Runtime consistency + live position tables now sit BELOW the visual tabs.
    with st.expander("Runtime consistency & live positions", expanded=False):
        _render_runtime_audit(bundle)
        _render_position_tables(bundle)
    return rendered, total
