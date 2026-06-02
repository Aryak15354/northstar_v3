#!/usr/bin/env python3
"""Canonical operational status report for Northstar V3."""

from __future__ import annotations

import json
import os
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


STATE_PATH = PROJECT_ROOT / "data" / "state" / "unified_state.json"
MARKET_STATE_PATH = PROJECT_ROOT / "data" / "processed" / "market_state.parquet"
MARKET_REFRESH_STATUS_PATH = PROJECT_ROOT / "data" / "processed" / "market_refresh_status.json"
SENTIMENT_STATUS_PATH = PROJECT_ROOT / "data" / "sentiment" / "v3" / "sentiment_loop_status.json"
ALT_STATUS_PATH = PROJECT_ROOT / "data" / "processed" / "alternative" / "alternative_pipeline_status.json"
ORCH_STATUS_PATH = PROJECT_ROOT / "data" / "options" / "live" / "trading_day_orchestrator_status.json"
HEARTBEAT_PATH = PROJECT_ROOT / "data" / "options" / "live" / "live_engine_heartbeat.json"
OPTIONS_LOOP_STATUS_PATH = PROJECT_ROOT / "data" / "options" / "live" / "options_loop_status.json"
RUNTIME_STATE_PATH = PROJECT_ROOT / "data" / "options" / "live" / "options_runtime_state.json"
RUNTIME_DB_PATH = PROJECT_ROOT / "data" / "runtime" / "portfolio_runtime.db"
REGISTRY_PATH = PROJECT_ROOT / "data" / "model_registry" / "strategy_registry.json"
ALPHA_POSTERIORS_PATH = PROJECT_ROOT / "data" / "processed" / "alpha_os_strategy_posteriors.parquet"
NAV_PATH = PROJECT_ROOT / "data" / "pnl" / "nav_history.parquet"
RECON_PATH = PROJECT_ROOT / "data" / "pnl" / "reconciliation_log.parquet"


@dataclass
class ComponentStatus:
    name: str
    status: str
    summary: str
    last_updated: str | None = None


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _safe_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _canonical_section(name: str) -> dict[str, Any]:
    payload = _safe_json(STATE_PATH)
    section = payload.get(name) or {}
    return section if isinstance(section, dict) else {}


def _parse_dt(value: Any) -> datetime | None:
    if value in (None, "", "None"):
        return None
    parsed = pd.to_datetime(value, errors="coerce", utc=True)
    if pd.isna(parsed):
        return None
    return pd.Timestamp(parsed).to_pydatetime()


def _age_hours(value: Any) -> float | None:
    dt_value = _parse_dt(value)
    if dt_value is None:
        return None
    return max((_now_utc() - dt_value).total_seconds() / 3600.0, 0.0)


def _format_age(age_hours: float | None) -> str:
    if age_hours is None:
        return "unknown age"
    if age_hours < 1.0:
        return f"{age_hours * 60.0:.0f}m old"
    return f"{age_hours:.1f}h old"


def _status_from_age(age_hours: float | None, *, ok_hours: float, warn_hours: float) -> str:
    if age_hours is None:
        return "FAIL"
    if age_hours <= ok_hours:
        return "PASS"
    if age_hours <= warn_hours:
        return "WARN"
    return "FAIL"


def _canonical_state_status() -> ComponentStatus:
    payload = _safe_json(STATE_PATH)
    if not payload:
        return ComponentStatus("canonical_state", "FAIL", "Canonical unified state missing", None)

    market = payload.get("market") or {}
    health = payload.get("health") or {}
    governor = payload.get("governor_state") or {}
    last_updated = _parse_dt(market.get("last_updated") or health.get("last_updated") or governor.get("last_morning_decision"))
    age = _age_hours(last_updated)
    status = _status_from_age(age, ok_hours=12.0, warn_hours=48.0)
    summary = (
        f"market_regime={market.get('regime', 'unknown')} "
        f"health={health.get('health_status', 'unknown')} "
        f"equity_budget={float(governor.get('equity_budget_inr', 0.0) or 0.0):,.0f}"
    )
    return ComponentStatus("canonical_state", status, summary, last_updated.isoformat() if last_updated else None)


def _market_status() -> ComponentStatus:
    refresh = _safe_json(MARKET_REFRESH_STATUS_PATH)
    canonical = _canonical_section("market")
    refresh_last = _parse_dt(refresh.get("finished_at"))
    canonical_last = _parse_dt(canonical.get("last_updated"))
    if canonical and canonical_last and (refresh_last is None or canonical_last >= refresh_last):
        age = _age_hours(canonical_last)
        status = _status_from_age(age, ok_hours=12.0, warn_hours=48.0)
        summary = (
            "source=canonical "
            f"regime={canonical.get('regime', 'unknown')} "
            f"allowed_exposure={float(canonical.get('allowed_exposure', 0.0) or 0.0):.2f}"
        )
        return ComponentStatus("market", status, summary, canonical_last.isoformat())

    if refresh:
        last_updated = _parse_dt(refresh.get("finished_at"))
        age = _age_hours(last_updated)
        status = _status_from_age(age, ok_hours=12.0, warn_hours=48.0)
        market_state = refresh.get("market_state") or {}
        summary = (
            f"pipeline={refresh.get('pipeline_status', 'UNKNOWN')} "
            f"regime={market_state.get('regime', 'unknown')} "
            f"allowed_exposure={float(market_state.get('allowed_exposure', 0.0) or 0.0):.2f}"
        )
        return ComponentStatus("market", status, summary, last_updated.isoformat() if last_updated else None)

    if not MARKET_STATE_PATH.exists():
        return ComponentStatus("market", "FAIL", "Market state artifact missing", None)

    try:
        df = pd.read_parquet(MARKET_STATE_PATH)
    except Exception as exc:
        return ComponentStatus("market", "FAIL", f"Could not read market state: {exc}", None)
    if df.empty:
        return ComponentStatus("market", "FAIL", "Market state artifact empty", None)

    latest = df.iloc[-1].to_dict()
    last_updated = _parse_dt(latest.get("date"))
    age = _age_hours(last_updated)
    status = _status_from_age(age, ok_hours=24.0, warn_hours=72.0)
    summary = (
        f"regime={latest.get('regime', 'unknown')} "
        f"macro_regime={latest.get('macro_regime', 'unknown')} "
        f"allowed_exposure={float(latest.get('allowed_exposure', 0.0) or 0.0):.2f}"
    )
    return ComponentStatus("market", status, summary, last_updated.isoformat() if last_updated else None)


def _sentiment_status() -> ComponentStatus:
    payload = _safe_json(SENTIMENT_STATUS_PATH)
    canonical = payload.get("canonical_state") or {}
    last_updated = _parse_dt(payload.get("timestamp") or canonical.get("pipeline_last_run"))
    canonical_state = _canonical_section("sentiment")
    canonical_last = _parse_dt(canonical_state.get("last_updated") or canonical_state.get("pipeline_last_run"))
    if canonical_state and canonical_last and (last_updated is None or canonical_last >= last_updated):
        age = _age_hours(canonical_last)
        status = _status_from_age(age, ok_hours=6.0, warn_hours=36.0)
        if not bool(canonical_state.get("is_fresh", False)) and status == "PASS":
            status = "WARN"
        summary = (
            "status=SUCCESS "
            f"regime={canonical_state.get('market_sentiment_regime', 'unknown')} "
            f"fresh={canonical_state.get('is_fresh', False)} "
            f"coverage={int(canonical_state.get('companies_with_coverage', 0) or 0)}"
        )
        return ComponentStatus("sentiment", status, summary, canonical_last.isoformat())

    age = _age_hours(last_updated)
    status = _status_from_age(age, ok_hours=6.0, warn_hours=36.0)
    if canonical and not bool(canonical.get("is_fresh", False)) and status == "PASS":
        status = "WARN"
    summary = (
        f"status={payload.get('status', 'UNKNOWN')} "
        f"regime={canonical.get('market_sentiment_regime', 'unknown')} "
        f"fresh={canonical.get('is_fresh', False)} "
        f"coverage={int(canonical.get('companies_with_coverage', 0) or 0)}"
    )
    return ComponentStatus("sentiment", status, summary, last_updated.isoformat() if last_updated else None)


def _alternative_status() -> ComponentStatus:
    payload = _safe_json(ALT_STATUS_PATH)
    state_sync = payload.get("state_sync") or {}
    last_updated = _parse_dt(payload.get("finished_at"))
    canonical = _canonical_section("alternative_data")
    canonical_last = _parse_dt(canonical.get("last_updated"))
    if canonical and canonical_last and (last_updated is None or canonical_last >= last_updated):
        age = _age_hours(canonical_last)
        status = _status_from_age(age, ok_hours=24.0, warn_hours=96.0)
        # Alternative sources run on mixed daily/weekly/monthly cadences.
        # Do not degrade the whole system just because one slow series (for
        # example GST) has not rolled to a new monthly print yet.
        if not bool(canonical.get("any_source_fresh", False)) and status == "PASS":
            status = "WARN"
        summary = (
            "source=canonical "
            f"fresh_any={canonical.get('any_source_fresh', False)} "
            f"fresh_all={canonical.get('all_sources_fresh', False)} "
            f"regime={canonical.get('economic_activity_regime', 'UNKNOWN')}"
        )
        return ComponentStatus("alternative_data", status, summary, canonical_last.isoformat())

    age = _age_hours(last_updated)
    status = _status_from_age(age, ok_hours=24.0, warn_hours=96.0)
    if state_sync and not bool(state_sync.get("any_source_fresh", False)) and status == "PASS":
        status = "WARN"
    summary = (
        f"collection={payload.get('collection', {}).get('status', 'UNKNOWN')} "
        f"pipeline={state_sync.get('pipeline_status', 'UNKNOWN')} "
        f"fresh_any={state_sync.get('any_source_fresh', False)} "
        f"fresh_all={state_sync.get('all_sources_fresh', False)}"
    )
    return ComponentStatus("alternative_data", status, summary, last_updated.isoformat() if last_updated else None)


def _runtime_status() -> ComponentStatus:
    heartbeat = _safe_json(HEARTBEAT_PATH)
    runtime = _safe_json(RUNTIME_STATE_PATH)
    orchestrator = _safe_json(ORCH_STATUS_PATH)
    loop_status = _safe_json(OPTIONS_LOOP_STATUS_PATH)

    hb_age = _age_hours(heartbeat.get("timestamp"))
    orch_age = _age_hours(orchestrator.get("timestamp"))
    runtime_age = _age_hours(runtime.get("timestamp"))
    loop_age = _age_hours(loop_status.get("last_success_at") or loop_status.get("timestamp"))

    age_candidates = [value for value in [hb_age, orch_age, runtime_age, loop_age] if value is not None]
    freshest = min(age_candidates) if age_candidates else None
    status = _status_from_age(freshest, ok_hours=18.0, warn_hours=48.0)

    stage = orchestrator.get("stage", "unknown")
    mode = runtime.get("current_mode", runtime.get("continuity_mode", "unknown"))
    loop_result = str(loop_status.get("status", "unknown") or "unknown")
    if stage == "day_failed" and status == "PASS":
        status = "WARN"
    summary = (
        f"heartbeat={_format_age(hb_age)} "
        f"loop={_format_age(loop_age)} "
        f"runtime={_format_age(runtime_age)} "
        f"orchestrator_stage={stage} "
        f"loop_status={loop_result} "
        f"mode={mode}"
    )

    last_updated = None
    for value in [
        heartbeat.get("timestamp"),
        runtime.get("timestamp"),
        orchestrator.get("timestamp"),
        loop_status.get("last_success_at") or loop_status.get("timestamp"),
    ]:
        parsed = _parse_dt(value)
        if parsed and (last_updated is None or parsed > last_updated):
            last_updated = parsed
    return ComponentStatus("runtime", status, summary, last_updated.isoformat() if last_updated else None)


def _runtime_db_status() -> ComponentStatus:
    if not RUNTIME_DB_PATH.exists():
        return ComponentStatus("runtime_db", "FAIL", "portfolio_runtime.db missing", None)

    try:
        conn = sqlite3.connect(RUNTIME_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
        event_rows = 0
        latest_event = None
        latest_control = None
        if "portfolio_events" in tables:
            cursor.execute("SELECT COUNT(*), MAX(timestamp_utc) FROM portfolio_events")
            event_rows, latest_event = cursor.fetchone()
        if "runtime_control" in tables:
            cursor.execute("SELECT MAX(updated_at) FROM runtime_control")
            latest_control = cursor.fetchone()[0]
        conn.close()
    except Exception as exc:
        return ComponentStatus("runtime_db", "FAIL", f"Runtime DB unreadable: {exc}", None)

    latest_dt = None
    for candidate in (latest_event, latest_control):
        parsed = _parse_dt(candidate)
        if parsed and (latest_dt is None or parsed > latest_dt):
            latest_dt = parsed

    age = _age_hours(latest_dt)
    event_age = _age_hours(latest_event)
    control_age = _age_hours(latest_control)
    status = "PASS" if tables and event_rows >= 0 else "FAIL"
    if status == "PASS" and age is not None and age > 48.0:
        status = "WARN"
    summary = (
        f"tables={len(tables)} portfolio_events={event_rows} "
        f"events={_format_age(event_age)} control={_format_age(control_age)}"
    )
    last_updated = latest_dt
    return ComponentStatus("runtime_db", status, summary, last_updated.isoformat() if last_updated else None)


def _alpha_os_status() -> ComponentStatus:
    registry = _safe_json(REGISTRY_PATH)
    last_updated = _parse_dt(registry.get("last_updated"))
    if last_updated is None and ALPHA_POSTERIORS_PATH.exists():
        last_updated = _parse_dt(datetime.fromtimestamp(ALPHA_POSTERIORS_PATH.stat().st_mtime, tz=timezone.utc).isoformat())
    age = _age_hours(last_updated)
    status = _status_from_age(age, ok_hours=72.0, warn_hours=240.0)
    strategies = registry.get("strategies") or {}
    active = sum(1 for item in strategies.values() if str(item.get("status", "")).upper() == "ACTIVE")
    summary = f"strategies={len(strategies)} active={active} posterior_file={'yes' if ALPHA_POSTERIORS_PATH.exists() else 'no'}"
    return ComponentStatus("alpha_os", status, summary, last_updated.isoformat() if last_updated else None)


def _pnl_status() -> ComponentStatus:
    if not NAV_PATH.exists():
        return ComponentStatus("pnl", "FAIL", "NAV history missing", None)
    try:
        nav_df = pd.read_parquet(NAV_PATH)
    except Exception as exc:
        return ComponentStatus("pnl", "FAIL", f"Could not read NAV history: {exc}", None)
    if nav_df.empty:
        return ComponentStatus("pnl", "FAIL", "NAV history empty", None)

    date_col = next((col for col in nav_df.columns if col.lower() == "date" or "timestamp" in col.lower()), None)
    last_updated = _parse_dt(nav_df.iloc[-1].get(date_col) if date_col else None)
    age = _age_hours(last_updated)
    status = _status_from_age(age, ok_hours=48.0, warn_hours=168.0)
    latest = nav_df.iloc[-1]
    nav_value = latest.get("nav_combined", latest.get("nav", 0.0))

    recon_suffix = "recon=missing"
    if RECON_PATH.exists():
        try:
            recon_df = pd.read_parquet(RECON_PATH)
            if not recon_df.empty:
                recon_latest = recon_df.iloc[-1]
                recon_suffix = f"recon={recon_latest.get('overall_status', recon_latest.get('status', 'UNKNOWN'))}"
        except Exception:
            recon_suffix = "recon=error"

    summary = f"nav={float(pd.to_numeric(nav_value, errors='coerce') or 0.0):,.0f} {recon_suffix}"
    return ComponentStatus("pnl", status, summary, last_updated.isoformat() if last_updated else None)


def _process_running(pid: Any) -> bool:
    try:
        os.kill(int(pid), 0)
        return True
    except Exception:
        return False


def _launch_surface_status() -> ComponentStatus:
    orchestrator = _safe_json(ORCH_STATUS_PATH)
    daemon = _safe_json(PROJECT_ROOT / "data" / "options" / "live" / "northstar_daemon_status.json")

    process_entries = orchestrator.get("processes") or []
    active = [entry for entry in process_entries if _process_running(entry.get("pid"))]
    daemon_pid = daemon.get("daemon_pid")
    daemon_running = _process_running(daemon_pid) if daemon_pid else False

    last_updated = _parse_dt(orchestrator.get("timestamp") or daemon.get("timestamp"))
    age = _age_hours(last_updated)
    status = "PASS" if active or daemon_running else _status_from_age(age, ok_hours=24.0, warn_hours=72.0)
    summary = f"active_processes={len(active)} daemon_running={daemon_running} stage={orchestrator.get('stage', 'unknown')}"
    return ComponentStatus("launch_surface", status, summary, last_updated.isoformat() if last_updated else None)


def collect_statuses() -> list[ComponentStatus]:
    return [
        _canonical_state_status(),
        _market_status(),
        _sentiment_status(),
        _alternative_status(),
        _runtime_status(),
        _runtime_db_status(),
        _alpha_os_status(),
        _pnl_status(),
        _launch_surface_status(),
    ]


def _status_score(status: str) -> float:
    normalized = str(status or "").upper()
    if normalized == "PASS":
        return 1.0
    if normalized == "WARN":
        return 0.6
    return 0.0


def _status_label(status: str) -> str:
    normalized = str(status or "").upper()
    if normalized == "PASS":
        return "healthy"
    if normalized == "WARN":
        return "degraded"
    return "down"


def build_health_snapshot(
    statuses: list[ComponentStatus] | None = None,
    *,
    state_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build an operational health payload for dashboards and canonical state.

    This intentionally uses the same readiness surfaces that govern live trading
    rather than the older intraday-only freshness heuristics. Off-hours standby
    should stay healthy when the system is behaving normally.
    """

    status_rows = statuses or collect_statuses()
    state_payload = state_payload if isinstance(state_payload, dict) else _safe_json(STATE_PATH)

    component_status = {item.name: _status_label(item.status) for item in status_rows}
    total_components = len(status_rows)
    pass_count = sum(1 for item in status_rows if item.status == "PASS")
    available_count = sum(1 for item in status_rows if item.status != "FAIL")

    scores = [_status_score(item.status) for item in status_rows]
    overall_health_score = float(sum(scores) / len(scores)) if scores else 0.0

    if overall_health_score >= 0.9:
        health_status = "excellent"
    elif overall_health_score >= 0.75:
        health_status = "good"
    elif overall_health_score >= 0.55:
        health_status = "fair"
    elif overall_health_score > 0.0:
        health_status = "degraded"
    else:
        health_status = "critical"

    freshness_hours: list[float] = []
    latest_dt: datetime | None = None
    warning_summaries: list[str] = []
    for item in status_rows:
        parsed = _parse_dt(item.last_updated)
        if parsed is not None:
            freshness_hours.append(max((_now_utc() - parsed).total_seconds() / 3600.0, 0.0))
            if latest_dt is None or parsed > latest_dt:
                latest_dt = parsed
        if item.status == "WARN":
            warning_summaries.append(f"{item.name}: {item.summary}")

    portfolio = state_payload.get("portfolio") or {}
    governor = state_payload.get("governor_state") or {}
    sentiment = state_payload.get("sentiment") or {}

    total_exposure = float(pd.to_numeric(portfolio.get("total_exposure", 0.0), errors="coerce") or 0.0)
    equity_budget = float(pd.to_numeric(governor.get("equity_budget_inr", 0.0), errors="coerce") or 0.0)
    options_budget = float(pd.to_numeric(governor.get("options_budget_inr", 0.0), errors="coerce") or 0.0)
    sentiment_fresh = bool(sentiment.get("is_fresh", False))
    sentiment_ok = any(item.name == "sentiment" and item.status != "FAIL" for item in status_rows)

    return {
        "overall_health_score": overall_health_score,
        "health_status": health_status,
        "data_fresh": all(item.status != "FAIL" for item in status_rows),
        "data_freshness_hours": float(max(freshness_hours)) if freshness_hours else 0.0,
        "component_availability": float(available_count / total_components) if total_components else 0.0,
        "components_healthy": int(pass_count),
        "total_components": int(total_components),
        "portfolio_active": bool(total_exposure > 0.0 or equity_budget > 0.0 or options_budget > 0.0),
        "intelligence_active": bool(sentiment_fresh or sentiment_ok),
        "last_updated": (latest_dt or _now_utc()).isoformat(),
        "component_status": component_status,
        "status_counts": {
            "pass": int(pass_count),
            "warn": int(sum(1 for item in status_rows if item.status == "WARN")),
            "fail": int(sum(1 for item in status_rows if item.status == "FAIL")),
        },
        "active_warnings": warning_summaries,
        "source_mode": "operational_status_report",
    }


def print_report(statuses: list[ComponentStatus]) -> int:
    now = datetime.now().astimezone()
    print("NORTHSTAR V3 SYSTEM STATUS")
    print("=" * 72)
    print(f"Generated: {now.isoformat()}")
    print()

    for item in statuses:
        updated = item.last_updated or "unknown"
        print(f"[{item.status:<4}] {item.name:<16} {item.summary}")
        print(f"       last_updated={updated}")

    fail_count = sum(1 for item in statuses if item.status == "FAIL")
    warn_count = sum(1 for item in statuses if item.status == "WARN")
    pass_count = sum(1 for item in statuses if item.status == "PASS")

    overall = "PASS"
    if fail_count:
        overall = "FAIL"
    elif warn_count:
        overall = "WARN"

    print()
    print("-" * 72)
    print(f"Overall: {overall}")
    print(f"PASS={pass_count} WARN={warn_count} FAIL={fail_count}")
    return 0 if overall != "FAIL" else 1


def main() -> int:
    return print_report(collect_statuses())


if __name__ == "__main__":
    raise SystemExit(main())
