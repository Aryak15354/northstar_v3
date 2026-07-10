#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd
import streamlit as st

from src.dashboard.data.live_data_manager import live_status_from_bundle
from src.dashboard.layout.terminal_theme import TERM, delta_color, ticker_tape


def inject_dashboard_styles() -> None:
    # Bloomberg-style terminal theme: near-black, flat, dense, monospace,
    # high-contrast amber/green/red. Class names match the existing sections
    # so every tab is restyled without touching each chart module.
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=IBM+Plex+Sans:wght@400;500;600&display=swap');
        html, body, [class*="css"] { font-family: "IBM Plex Sans", sans-serif; }
        h1,h2,h3,h4,h5 { font-family: "JetBrains Mono", monospace; letter-spacing: -0.01em; color:#e6edf5; }
        .stApp { background: #080a0d; color: #c9d3df; }
        .block-container { padding-top: 0.6rem; padding-bottom: 1.6rem; max-width: 110rem; }

        /* ---- top command bar ---- */
        .ns-global-bar {
            position: sticky; top: 0; z-index: 1000;
            padding: 0.55rem 0.85rem; border-radius: 4px;
            border: 1px solid #232a33; border-top: 2px solid #ffb000;
            background: #0e1116; margin-bottom: 0.55rem;
        }
        .ns-global-title {
            font-family: "JetBrains Mono", monospace; font-size: 1.02rem; font-weight: 700;
            color:#ffb000; letter-spacing: 0.04em; text-transform: uppercase; margin-bottom:0.1rem;
        }
        .ns-global-subtitle { color:#7d8899; font-size:0.72rem; margin-bottom:0.55rem; }

        /* ---- ticker tape ---- */
        .ns-ticker { overflow:hidden; white-space:nowrap; border-top:1px solid #232a33;
            border-bottom:1px solid #232a33; background:#0a0c10; padding:0.3rem 0; margin:0.4rem 0 0.1rem 0; }
        .ns-ticker-track { display:inline-block; padding-left:100%; animation: ns-marquee 42s linear infinite;
            font-family:"JetBrains Mono",monospace; font-size:0.78rem; }
        .ns-ticker:hover .ns-ticker-track { animation-play-state: paused; }
        @keyframes ns-marquee { 0%{transform:translateX(0);} 100%{transform:translateX(-50%);} }
        .ns-tick-l { color:#7d8899; } .ns-tick-v { color:#e6edf5; font-weight:600; }
        .ns-tick-sep { color:#39424e; margin:0 0.9rem; }

        /* ---- KPI strip ---- */
        .ns-metric-grid { display:grid; grid-template-columns: repeat(auto-fit, minmax(9.5rem,1fr)); gap:1px;
            background:#232a33; border:1px solid #232a33; border-radius:4px; overflow:hidden; }
        .ns-metric-card { background:#0e1116; padding:0.5rem 0.7rem; min-height:3.4rem; }
        .ns-metric-label { color:#7d8899; font-size:0.62rem; letter-spacing:0.09em; text-transform:uppercase; margin-bottom:0.2rem; }
        .ns-metric-value { font-family:"JetBrains Mono",monospace; font-size:1.02rem; font-weight:600; color:#e6edf5; }
        .ns-metric-subvalue { color:#7d8899; font-size:0.66rem; margin-top:0.12rem; }

        .ns-live-status { display:inline-flex; align-items:center; gap:0.4rem; font-weight:600; }
        .ns-live-dot { width:8px; height:8px; border-radius:50%; display:inline-block;
            box-shadow:0 0 8px currentColor; animation: ns-pulse 1.6s infinite; }
        @keyframes ns-pulse { 0%{opacity:0.55;} 50%{opacity:1;} 100%{opacity:0.55;} }

        /* ---- panels / cards (flat terminal) ---- */
        .ns-visual-card, .ns-narrative-block, .ns-section-shell {
            border:1px solid #232a33; border-radius:4px; background:#0e1116; box-shadow:none;
        }
        .ns-section-shell { padding:0.55rem 0.8rem; border-left:2px solid #ffb000; margin:0.15rem 0 0.6rem 0; }
        .ns-section-title { font-family:"JetBrains Mono",monospace; font-size:1.02rem; font-weight:700; color:#e6edf5; text-transform:uppercase; letter-spacing:0.03em; }
        .ns-section-subtitle { color:#7d8899; font-size:0.76rem; margin-top:0.15rem; }
        .ns-narrative-block { padding:0.6rem 0.8rem; margin-bottom:0.7rem; border-left:2px solid #38bdf8; }
        .ns-narrative-title { font-family:"JetBrains Mono",monospace; font-size:0.82rem; font-weight:700; color:#38bdf8; margin-bottom:0.35rem; text-transform:uppercase; letter-spacing:0.03em; }
        .ns-narrative-line { color:#b6c2d1; font-size:0.84rem; margin-bottom:0.25rem; }
        .ns-visual-card { padding:0.55rem 0.7rem 0.35rem 0.7rem; margin-bottom:0.6rem; }
        .ns-visual-title { font-family:"JetBrains Mono",monospace; font-size:0.86rem; font-weight:600; color:#e6edf5; margin-bottom:0.1rem; }
        .ns-visual-description, .ns-visual-meta, .ns-placeholder-body { color:#7d8899; font-size:0.72rem; }
        .ns-visual-description { margin-bottom:0.2rem; }
        .ns-visual-meta { margin-bottom:0.4rem; font-family:"JetBrains Mono",monospace; color:#5b6675; }
        .ns-visual-freshness { font-family:"JetBrains Mono",monospace; margin-bottom:0.2rem; }
        .ns-visual-stale { border-left:3px solid #f85149; background:rgba(248,81,73,0.04); }
        .ns-placeholder-card { min-height:11rem; }
        .ns-placeholder-title { color:#e6edf5; font-size:0.84rem; font-weight:600; margin-bottom:0.25rem; }

        /* ---- tabs as terminal function keys ---- */
        .stTabs [data-baseweb="tab-list"] { gap:2px; border-bottom:1px solid #232a33; }
        .stTabs [data-baseweb="tab"] {
            background:#0e1116; border-radius:3px 3px 0 0; border:1px solid #232a33; border-bottom:none;
            padding:0.35rem 0.8rem; font-family:"JetBrains Mono",monospace; font-size:0.8rem; color:#7d8899;
        }
        .stTabs [aria-selected="true"] { background:#161b22 !important; color:#ffb000 !important; border-top:2px solid #ffb000 !important; }

        /* dataframes -> terminal grid */
        [data-testid="stDataFrame"] { border:1px solid #232a33; border-radius:4px; }
        [data-testid="stDataFrame"] * { font-family:"JetBrains Mono",monospace !important; font-size:0.76rem !important; }
        section[data-testid="stSidebar"] { background:#0a0c10; border-right:1px solid #232a33; }
        @media (max-width:1100px){ .ns-metric-grid{ grid-template-columns: repeat(auto-fit, minmax(8rem,1fr)); } }
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


def _latest_market_state(bundle: dict[str, Any]) -> dict[str, Any]:
    """Freshest market-state row. Prefers the rich market_state.parquet
    (regime, breadth, risk-on, stress, volatility) over the often-stale
    unified_state.json where regime can read 'unknown'."""
    df = bundle.get("market_state")
    if not isinstance(df, pd.DataFrame) or df.empty:
        try:
            from pathlib import Path
            p = Path(__file__).resolve().parents[3] / "data/processed/market_state.parquet"
            df = pd.read_parquet(p) if p.exists() else None
        except Exception:
            df = None
    if isinstance(df, pd.DataFrame) and not df.empty:
        sort_col = "timestamp" if "timestamp" in df.columns else ("date" if "date" in df.columns else None)
        row = (df.sort_values(sort_col) if sort_col else df).iloc[-1]
        return {k: row.get(k) for k in row.index}
    return {}


def _resolve_regime(state_market: dict[str, Any], ms: dict[str, Any]) -> str:
    for cand in (ms.get("regime_name"), ms.get("regime"), ms.get("macro_regime"), state_market.get("regime")):
        s = str(cand or "").strip()
        if s and s.lower() not in {"unknown", "nan", "none", ""}:
            return s
    return "unknown"


def _format_last_updated(bundle: dict[str, Any]) -> str:
    freshness = bundle.get("pipeline_freshness")
    if isinstance(freshness, pd.DataFrame) and not freshness.empty and "timestamp" in freshness.columns:
        timestamps = pd.to_datetime(freshness["timestamp"], errors="coerce").dropna()
        if not timestamps.empty:
            return timestamps.max().strftime("%d %b %Y %H:%M")
    return datetime.now().strftime("%d %b %Y %H:%M")


def _upstox_token_tick() -> tuple[str, str, float]:
    """Ticker cell for the manually-generated Upstox token's freshness.

    The options live-chain provider degrades silently when the token in
    .env.options goes stale (>20h per refresh_cadence.yaml); surface its age
    so a stale token is impossible to miss (audit finding M6)."""
    from pathlib import Path
    from datetime import datetime
    env_path = Path(__file__).resolve().parents[3] / ".env.options"
    if not env_path.exists():
        return ("UPSTOX", "no token", -1.0)
    age_h = (datetime.now().timestamp() - env_path.stat().st_mtime) / 3600.0
    if age_h <= 20:
        return ("UPSTOX", f"token {age_h:.0f}h", 1.0)
    return ("UPSTOX", f"TOKEN STALE {age_h/24:.0f}d", -1.0)


def render_global_bar(bundle: dict[str, Any]) -> None:
    state = bundle.get("state") or {}
    market = state.get("market") or {}
    risk = state.get("risk") or {}
    portfolio = state.get("portfolio") or {}
    perf = bundle.get("performance_metrics") or {}
    health = bundle.get("system_health") or {}
    live_color_name, live_label, live_color = live_status_from_bundle(bundle)

    ms = _latest_market_state(bundle)
    nav_value = f"₹{_safe_number(perf.get('current_nav')):,.0f}"
    regime_value = _resolve_regime(market, ms)
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

    # Ticker tape from the freshest market-state row (defensive).
    day_ret = _safe_number(perf.get("daily_return_pct", perf.get("return_today_pct", 0.0)))
    dd = _safe_number(perf.get("current_drawdown_pct", perf.get("max_drawdown_pct", 0.0)))
    breadth = _safe_number(ms.get("breadth_pct", market.get("breadth_pct", 0.0)))
    if breadth and breadth <= 1.0:
        breadth *= 100.0
    risk_on = _safe_number(ms.get("risk_on_probability", market.get("risk_on_probability", 0.0))) * 100.0
    stress = _safe_number(ms.get("stress_score", ms.get("stress_level", 0.0)))
    macro = str(ms.get("macro_regime", "") or "").strip()
    vol_regime = str(ms.get("volatility_regime", "") or "").strip()
    participation = _safe_number(ms.get("participation_score", 0.0)) * (100.0 if _safe_number(ms.get("participation_score", 0.0)) <= 1 else 1.0)
    tick_items = [
        ("NAV", nav_value, day_ret),
        ("REGIME", regime_value.upper(), 0.0),
        ("MACRO", macro.upper() or "n/a", 0.0),
        ("VOL", vol_regime.upper() or "n/a", 0.0),
        ("EXPOSURE", exposure_value, 0.0),
        ("DRAWDOWN", f"{dd:.2f}%", dd),
        ("BREADTH", f"{breadth:.1f}%" if breadth else "n/a", breadth - 50.0 if breadth else 0.0),
        ("RISK-ON", f"{risk_on:.0f}%" if risk_on else "n/a", risk_on - 50.0 if risk_on else 0.0),
        ("STRESS", f"{stress:.2f}" if stress else "n/a", -stress),
        ("HEALTH", health_value, _safe_number(health.get("overall_health_score")) * 100 - 50),
    ]
    tick_items.append(_upstox_token_tick())
    tape = ticker_tape(tick_items)

    st.markdown(
        f"""
        <div class="ns-global-bar">
            <div class="ns-global-title">NORTHSTAR&nbsp;V3&nbsp;· TERMINAL</div>
            <div class="ns-global-subtitle">Indian equities & index/stock options · canonical state · ledger · runtime · research</div>
            <div class="ns-metric-grid">{cards}</div>
            {tape}
        </div>
        """,
        unsafe_allow_html=True,
    )
