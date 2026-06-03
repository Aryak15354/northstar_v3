#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd
import streamlit as st

from src.dashboard.data.live_data_manager import live_status_from_bundle


def inject_dashboard_styles() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=IBM+Plex+Sans:wght@400;500;600&display=swap');
        html, body, [class*="css"] {
            font-family: "IBM Plex Sans", sans-serif;
        }
        h1, h2, h3, h4, h5 {
            font-family: "Space Grotesk", sans-serif;
            letter-spacing: -0.03em;
        }
        .stApp {
            background:
                radial-gradient(circle at top right, rgba(56, 189, 248, 0.11), transparent 26%),
                radial-gradient(circle at top left, rgba(34, 197, 94, 0.08), transparent 22%),
                linear-gradient(180deg, #0b0f14 0%, #091018 100%);
            color: #e2e8f0;
        }
        .block-container {
            padding-top: 1.15rem;
            padding-bottom: 2.25rem;
            max-width: 96rem;
        }
        .ns-global-bar {
            position: sticky;
            top: 0.5rem;
            z-index: 1000;
            padding: 0.95rem 1.05rem;
            border-radius: 22px;
            border: 1px solid rgba(148, 163, 184, 0.16);
            background: linear-gradient(135deg, rgba(15, 23, 42, 0.92), rgba(12, 18, 28, 0.90));
            box-shadow: 0 20px 45px rgba(0, 0, 0, 0.18);
            backdrop-filter: blur(18px);
            margin-bottom: 1rem;
        }
        .ns-global-title {
            font-family: "Space Grotesk", sans-serif;
            font-size: 1.42rem;
            font-weight: 700;
            margin-bottom: 0.2rem;
            color: #f8fafc;
        }
        .ns-global-subtitle {
            color: #94a3b8;
            font-size: 0.88rem;
            margin-bottom: 0.8rem;
        }
        .ns-metric-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(11rem, 1fr));
            gap: 0.75rem;
        }
        .ns-metric-card,
        .ns-visual-card,
        .ns-narrative-block,
        .ns-section-shell {
            border-radius: 18px;
            border: 1px solid rgba(148, 163, 184, 0.14);
            background: linear-gradient(180deg, rgba(15, 23, 42, 0.92), rgba(15, 23, 42, 0.72));
            box-shadow: 0 16px 32px rgba(0, 0, 0, 0.14);
        }
        .ns-metric-card {
            padding: 0.8rem 0.9rem;
            min-height: 5.8rem;
        }
        .ns-metric-label {
            color: #94a3b8;
            font-size: 0.72rem;
            letter-spacing: 0.06em;
            text-transform: uppercase;
            margin-bottom: 0.35rem;
        }
        .ns-metric-value {
            font-family: "Space Grotesk", sans-serif;
            font-size: 1.15rem;
            font-weight: 600;
            color: #f8fafc;
        }
        .ns-metric-subvalue {
            color: #cbd5e1;
            font-size: 0.76rem;
            margin-top: 0.2rem;
        }
        .ns-live-status {
            display: inline-flex;
            align-items: center;
            gap: 0.45rem;
            font-weight: 600;
        }
        .ns-live-dot {
            width: 10px;
            height: 10px;
            border-radius: 999px;
            display: inline-block;
            box-shadow: 0 0 12px currentColor;
            animation: ns-pulse 1.6s infinite;
        }
        @keyframes ns-pulse {
            0% { transform: scale(0.9); opacity: 0.6; }
            50% { transform: scale(1.15); opacity: 1; }
            100% { transform: scale(0.9); opacity: 0.6; }
        }
        .ns-section-shell {
            padding: 0.95rem 1rem;
            margin-top: 0.2rem;
            margin-bottom: 0.9rem;
        }
        .ns-section-title {
            font-family: "Space Grotesk", sans-serif;
            font-size: 1.26rem;
            font-weight: 700;
            color: #f8fafc;
        }
        .ns-section-subtitle {
            color: #94a3b8;
            font-size: 0.88rem;
            margin-top: 0.25rem;
        }
        .ns-narrative-block {
            padding: 0.95rem 1rem;
            margin-bottom: 1rem;
        }
        .ns-narrative-title {
            font-family: "Space Grotesk", sans-serif;
            font-size: 0.96rem;
            font-weight: 700;
            color: #e2e8f0;
            margin-bottom: 0.45rem;
        }
        .ns-narrative-line {
            color: #cbd5e1;
            font-size: 0.9rem;
            margin-bottom: 0.3rem;
        }
        .ns-visual-card {
            padding: 0.85rem 0.95rem 0.55rem 0.95rem;
            margin-bottom: 0.95rem;
        }
        .ns-visual-title {
            font-family: "Space Grotesk", sans-serif;
            font-size: 1rem;
            font-weight: 600;
            color: #f8fafc;
            margin-bottom: 0.18rem;
        }
        .ns-visual-description,
        .ns-visual-meta,
        .ns-placeholder-body {
            color: #94a3b8;
            font-size: 0.82rem;
        }
        .ns-visual-description {
            margin-bottom: 0.28rem;
        }
        .ns-visual-meta {
            margin-bottom: 0.55rem;
        }
        .ns-placeholder-card {
            min-height: 14rem;
        }
        .ns-placeholder-title {
            color: #f8fafc;
            font-size: 0.92rem;
            font-weight: 600;
            margin-bottom: 0.3rem;
        }
        .stTabs [data-baseweb="tab-list"] {
            gap: 0.5rem;
        }
        .stTabs [data-baseweb="tab"] {
            background: rgba(15, 23, 42, 0.55);
            border-radius: 999px;
            border: 1px solid rgba(148, 163, 184, 0.14);
            padding: 0.45rem 0.95rem;
        }
        @media (max-width: 1100px) {
            .ns-metric-grid {
                grid-template-columns: repeat(auto-fit, minmax(9.5rem, 1fr));
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _safe_number(value: Any) -> float:
    try:
        numeric = pd.to_numeric(value, errors="coerce")
        return 0.0 if pd.isna(numeric) else float(numeric)
    except Exception:
        return 0.0


def _format_last_updated(bundle: dict[str, Any]) -> str:
    freshness = bundle.get("pipeline_freshness")
    if isinstance(freshness, pd.DataFrame) and not freshness.empty and "timestamp" in freshness.columns:
        timestamps = pd.to_datetime(freshness["timestamp"], errors="coerce").dropna()
        if not timestamps.empty:
            return timestamps.max().strftime("%d %b %Y %H:%M")
    return datetime.now().strftime("%d %b %Y %H:%M")


def render_global_bar(bundle: dict[str, Any]) -> None:
    state = bundle.get("state") or {}
    market = state.get("market") or {}
    risk = state.get("risk") or {}
    portfolio = state.get("portfolio") or {}
    perf = bundle.get("performance_metrics") or {}
    health = bundle.get("system_health") or {}
    live_color_name, live_label, live_color = live_status_from_bundle(bundle)

    nav_value = f"₹{_safe_number(perf.get('current_nav')):,.0f}"
    regime_value = str(market.get("regime", "unknown"))
    risk_value = str(risk.get("overall_risk_level", risk.get("status", "unknown")))
    exposure_value = f"{_safe_number(portfolio.get('total_exposure')):.1%}"
    health_value = f"{_safe_number(health.get('overall_health_score')):.1%}"
    last_updated = _format_last_updated(bundle)

    metrics = [
        ("NAV", nav_value, "Canonical combined NAV"),
        ("Current Regime", regime_value, "Top-down market state"),
        ("Risk State", risk_value, "Canonical runtime risk"),
        ("Exposure %", exposure_value, "Current portfolio exposure"),
        ("Health Score", health_value, "System health composite"),
        (
            "Live Status",
            f'<span class="ns-live-status" style="color:{live_color};"><span class="ns-live-dot"></span>{live_label}</span>',
            f"{live_color_name} runtime heartbeat",
        ),
        ("Last Updated", last_updated, "Persisted artifact freshness"),
    ]

    cards = "".join(
        f"""
        <div class="ns-metric-card">
            <div class="ns-metric-label">{label}</div>
            <div class="ns-metric-value">{value}</div>
            <div class="ns-metric-subvalue">{subvalue}</div>
        </div>
        """
        for label, value, subvalue in metrics
    )

    st.markdown(
        f"""
        <div class="ns-global-bar">
            <div class="ns-global-title">Northstar V3 Institutional Intelligence Dashboard</div>
            <div class="ns-global-subtitle">Integrated static and live surfaces with canonical state, ledger, runtime, and research views.</div>
            <div class="ns-metric-grid">{cards}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
