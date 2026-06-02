#!/usr/bin/env python3
from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st


def _safe_float(value: Any) -> float | None:
    try:
        numeric = pd.to_numeric(value, errors="coerce")
        if pd.isna(numeric):
            return None
        return float(numeric)
    except Exception:
        return None


def build_section_narrative(tab: str, bundle: dict[str, Any]) -> list[str]:
    state = bundle.get("state") or {}
    market = state.get("market") or {}
    governor = state.get("governor_state") or {}
    sentiment = state.get("sentiment") or {}
    alpha_os = state.get("alpha_os") or {}
    perf = bundle.get("performance_metrics") or {}
    lines: list[str] = []

    if tab == "Overview":
        regime = market.get("regime", "unknown")
        exposure = _safe_float((state.get("portfolio") or {}).get("total_exposure"))
        health = _safe_float((bundle.get("system_health") or {}).get("overall_health_score"))
        lines.append(f"Northstar is currently in `{regime}` with portfolio exposure at `{(exposure or 0.0):.1%}` and health at `{(health or 0.0):.1%}`.")
        if governor:
            lines.append(f"Governor capital structure is allocating `{_safe_float(governor.get('equity_fraction')) or 0.0:.1%}` to equity and `{_safe_float(governor.get('options_fraction')) or 0.0:.1%}` to options.")
    elif tab == "Performance":
        lines.append(
            f"Current NAV is `₹{_safe_float(perf.get('current_nav')) or 0.0:,.0f}` with total return `{_safe_float(perf.get('total_return')) or 0.0:.2f}%` and max drawdown `{_safe_float(perf.get('max_drawdown')) or 0.0:.2f}%`."
        )
    elif tab == "Market":
        lines.append(
            f"Macro and regime state are currently aligned around `{market.get('regime', 'unknown')}` with allowed exposure `{_safe_float(market.get('allowed_exposure')) or 0.0:.1%}`."
        )
    elif tab == "Sentiment":
        lines.append(
            f"Market sentiment regime is `{sentiment.get('market_sentiment_regime', sentiment.get('regime', 'UNAVAILABLE'))}` with conviction `{_safe_float(sentiment.get('regime_confidence')) or 0.0:.2f}`."
        )
        lines.append("Alternative data panels are tied directly to NSE-focused bulk deals, announcements, pledges, and Screener ownership surfaces.")
    elif tab == "Portfolio":
        lines.append(
            f"Portfolio construction is governed by the canonical budget layer, with equity fraction `{_safe_float(governor.get('equity_fraction')) or 0.0:.1%}` and cash reserve `{_safe_float(governor.get('cash_fraction')) or 0.0:.1%}`."
        )
    elif tab == "Risk":
        risk_frame = bundle.get("risk_frame")
        if isinstance(risk_frame, pd.DataFrame) and not risk_frame.empty:
            row = risk_frame.iloc[-1]
            lines.append(
                f"Runtime risk is reporting `{row.get('overall_risk_level', 'unknown')}` with system stress `{_safe_float(row.get('system_stress')) or 0.0:.2f}` and exposure multiplier `{_safe_float(row.get('exposure_multiplier')) or 0.0:.2f}`."
            )
        lines.append("Greek and margin surfaces update from live runtime artifacts and degrade honestly when the engine goes stale.")
    elif tab == "Options":
        lines.append("The live options surface is split into market structure, flow, Greeks, and runtime risk so we can monitor shape without clutter.")
        lines.append("When live artifacts are sparse, the dashboard falls back to the latest real snapshot instead of fabricating continuity.")
    elif tab == "Research":
        lines.append("Research visuals are driven entirely by persisted valuation, posterior, and cohesive alpha artifacts across the NSE 500 universe.")
    elif tab == "Alpha OS":
        lines.append(
            f"Alpha OS currently reports `{int(alpha_os.get('active_strategy_count', 0) or 0)}` active strategies, with registry, beliefs, regret, and operational freshness shown on one surface."
        )
    return [line for line in lines if line]


def render_narrative_block(tab: str, bundle: dict[str, Any]) -> None:
    lines = build_section_narrative(tab, bundle)
    if not lines:
        return
    body = "".join(f"<div class='ns-narrative-line'>{line}</div>" for line in lines)
    st.markdown(
        f"""
        <div class="ns-narrative-block">
            <div class="ns-narrative-title">Intelligence Layer</div>
            {body}
        </div>
        """,
        unsafe_allow_html=True,
    )
