#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, time as dt_time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from src.dashboard.data.data_manager import (
    load_intraday_market_sentiment_data,
    load_live_options_data,
    load_risk_runtime_data,
)

LIVE_REFRESH_SECONDS = 300
IST = ZoneInfo("Asia/Kolkata")
MARKET_OPEN = dt_time(9, 15)
MARKET_CLOSE = dt_time(15, 30)


def initialize_live_state() -> None:
    st.session_state.setdefault("last_live_update", None)
    st.session_state.setdefault("live_refresh_count", 0)
    st.session_state.setdefault("live_mode_active", False)


def _parse_timestamp(value: Any) -> datetime | None:
    if value in [None, "", "NaT"]:
        return None
    try:
        parsed = pd.to_datetime(value, errors="coerce", format="mixed")
        if pd.isna(parsed):
            return None
        if getattr(parsed, "tzinfo", None) is not None:
            try:
                parsed = parsed.tz_localize(None)
            except TypeError:
                parsed = parsed.tz_convert(None)
        return parsed.to_pydatetime()
    except Exception:
        return None


def _now_ist() -> datetime:
    return datetime.now(IST)


def market_hours_active(now: datetime | None = None) -> bool:
    current = now or _now_ist()
    if current.weekday() >= 5:
        return False
    return MARKET_OPEN <= current.timetz().replace(tzinfo=None) <= MARKET_CLOSE


def market_session_label(now: datetime | None = None) -> str:
    current = now or _now_ist()
    if current.weekday() >= 5:
        return "WEEKEND"
    current_time = current.timetz().replace(tzinfo=None)
    if current_time < MARKET_OPEN:
        return "PREOPEN"
    if current_time <= MARKET_CLOSE:
        return "LIVE"
    return "CLOSED"


def maybe_refresh_live_data(force: bool = False) -> bool:
    initialize_live_state()
    live_mode_active = market_hours_active()
    st.session_state["live_mode_active"] = live_mode_active
    last_live = _parse_timestamp(st.session_state.get("last_live_update"))
    now = _now_ist().replace(tzinfo=None)
    should_refresh = bool(force)
    if live_mode_active:
        should_refresh = should_refresh or last_live is None or (now - last_live) >= timedelta(seconds=LIVE_REFRESH_SECONDS)
    if should_refresh:
        load_live_options_data.clear()
        load_risk_runtime_data.clear()
        load_intraday_market_sentiment_data.clear()
        st.session_state["last_live_update"] = now.isoformat()
        st.session_state["live_refresh_count"] = int(st.session_state.get("live_refresh_count", 0)) + 1
    return should_refresh


def _runtime_down_days(bundle: dict[str, Any]) -> float | None:
    """Age (days) of the YOUNGEST runtime liveness signal, or None if unknown.

    Session labels like PREOPEN/CLOSED must never mask a dead engine: the
    daemon was stopped for 12 days while the badge showed 'PREOPEN' (audit
    finding H5 — heartbeats lie)."""
    freshness = bundle.get("pipeline_freshness")
    if not isinstance(freshness, pd.DataFrame) or freshness.empty:
        return None
    rows = freshness[freshness["source"].isin(["Heartbeat", "Orchestrator", "Options Runtime"])]
    if rows.empty:
        return None
    ages = pd.to_numeric(rows["age_hours"], errors="coerce").dropna()
    if ages.empty:
        return None
    return float(ages.min()) / 24.0


def live_status_from_bundle(bundle: dict[str, Any]) -> tuple[str, str, str]:
    session_label = market_session_label()
    orchestrator = bundle.get("orchestrator_status") or {}
    # Honesty first: if no runtime signal is younger than 2 days, the engine
    # is DOWN regardless of the market session.
    down_days = _runtime_down_days(bundle)
    if down_days is not None and down_days > 2.0:
        return ("RED", f"DOWN {down_days:.0f}d", "#ef4444")
    if session_label == "PREOPEN":
        return ("AMBER", "PREOPEN", "#f59e0b")
    if session_label in {"CLOSED", "WEEKEND"}:
        stage = str(orchestrator.get("stage", "")).strip().lower()
        if stage in {"day_complete", "intraday_stopped", "running_eod", "market_closed_skip_intraday"}:
            return ("AMBER", "CLOSED", "#94a3b8")
        return ("AMBER", session_label, "#94a3b8")

    freshness = bundle.get("pipeline_freshness")
    if not isinstance(freshness, pd.DataFrame) or freshness.empty:
        return ("RED", "STALE", "#ef4444")

    # During live market hours, the live-engine heartbeat is the most direct
    # liveness signal. The orchestrator and full runtime snapshots can lag by
    # an entire cycle while the engine is still actively scanning chains.
    heartbeat_rows = freshness[freshness["source"] == "Heartbeat"].copy()
    if not heartbeat_rows.empty:
        heartbeat_age = pd.to_numeric(heartbeat_rows["age_hours"], errors="coerce").dropna()
        heartbeat_statuses = heartbeat_rows["status"].astype(str).str.lower().tolist()
        if (
            not heartbeat_age.empty
            and float(heartbeat_age.min()) <= 0.2
            and any(status in {"alive", "healthy", "success"} for status in heartbeat_statuses)
        ):
            return ("GREEN", "LIVE", "#22c55e")

    orchestrator_rows = freshness[freshness["source"] == "Orchestrator"].copy()
    if not orchestrator_rows.empty:
        orchestrator_age = pd.to_numeric(orchestrator_rows["age_hours"], errors="coerce").dropna()
        orchestrator_statuses = orchestrator_rows["status"].astype(str).str.lower().tolist()
        if (
            not orchestrator_age.empty
            and float(orchestrator_age.min()) <= 0.2
            and any(status in {"intraday_running", "running_eod", "waiting_market_open"} for status in orchestrator_statuses)
        ):
            return ("GREEN", "LIVE", "#22c55e")
    runtime = freshness[freshness["source"].isin(["Options Runtime", "Heartbeat"])].copy()
    if runtime.empty:
        return ("RED", "STALE", "#ef4444")
    max_age = pd.to_numeric(runtime["age_hours"], errors="coerce").dropna().max()
    statuses = runtime["status"].astype(str).str.lower().tolist()
    if max_age is not None and max_age <= 0.2 and any(status in {"alive", "healthy", "success", "day_complete", "normal_operation"} for status in statuses):
        return ("GREEN", "LIVE", "#22c55e")
    if max_age is not None and max_age <= 6:
        return ("AMBER", "RECENT", "#f59e0b")
    return ("RED", "STALE", "#ef4444")
