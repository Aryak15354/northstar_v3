#!/usr/bin/env python3
"""Publish truthful off-hours runtime standby status surfaces."""

from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime, time, timezone, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

INDIA_TZ = timezone(timedelta(hours=5, minutes=30))
LIVE_DIR = PROJECT_ROOT / "data/options/live"
RUNTIME_STATE_PATH = LIVE_DIR / "options_runtime_state.json"
LOOP_STATUS_PATH = LIVE_DIR / "options_loop_status.json"
ORCH_STATUS_PATH = LIVE_DIR / "trading_day_orchestrator_status.json"
DAEMON_STATUS_PATH = LIVE_DIR / "northstar_daemon_status.json"
RUNTIME_DB_PATH = PROJECT_ROOT / "data/runtime/portfolio_runtime.db"
NAV_PATH = PROJECT_ROOT / "data/pnl/nav_history.parquet"


def _now() -> datetime:
    return datetime.now(INDIA_TZ)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    tmp.replace(path)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _market_is_open(now: datetime) -> bool:
    current = now.timetz().replace(tzinfo=None)
    return time(9, 15) <= current <= time(15, 30)


def _runtime_db_summary() -> dict[str, Any]:
    if not RUNTIME_DB_PATH.exists():
        return {"available": False}
    con = sqlite3.connect(RUNTIME_DB_PATH)
    try:
        tables = {row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        event_rows = 0
        latest_event = None
        latest_control = None
        if "portfolio_events" in tables:
            event_rows, latest_event = con.execute("SELECT COUNT(*), MAX(timestamp_utc) FROM portfolio_events").fetchone()
        if "runtime_control" in tables:
            latest_control = con.execute("SELECT MAX(updated_at) FROM runtime_control").fetchone()[0]
    finally:
        con.close()
    return {
        "available": True,
        "tables": len(tables),
        "portfolio_events": int(event_rows or 0),
        "latest_event": latest_event,
        "latest_control": latest_control,
    }


def _nav_summary() -> dict[str, Any]:
    if not NAV_PATH.exists():
        return {"available": False}
    try:
        df = pd.read_parquet(NAV_PATH)
    except Exception as exc:
        return {"available": False, "error": str(exc)}
    if df.empty:
        return {"available": True, "rows": 0}
    date_col = next((col for col in df.columns if str(col).lower() == "date" or "timestamp" in str(col).lower()), None)
    latest = df.iloc[-1]
    return {
        "available": True,
        "rows": int(len(df)),
        "latest_date": str(latest.get(date_col)) if date_col else None,
        "latest_nav": float(pd.to_numeric(latest.get("nav_combined", latest.get("nav", 0.0)), errors="coerce") or 0.0),
    }


def main() -> int:
    now = _now()
    now_iso = now.isoformat()
    market_open = _market_is_open(now)
    stage = "ready_no_daemon" if market_open else "standby_off_hours"

    runtime = _read_json(RUNTIME_STATE_PATH)
    runtime.update(
        {
            "timestamp": now_iso,
            "last_reconciled_at": now_iso,
            "standby_status": stage,
            "standby_reason": "market_hours_active_no_daemon" if market_open else "market_closed_no_live_heartbeat_expected",
            "source": "scripts/runners/sync_runtime_standby_status.py",
        }
    )
    _write_json(RUNTIME_STATE_PATH, runtime)

    loop_status = _read_json(LOOP_STATUS_PATH)
    loop_status.update(
        {
            "timestamp": now_iso,
            "status": "ready" if market_open else "standby",
            "result_status": "ready" if market_open else "standby",
            "last_standby_at": now_iso,
            "source": "scripts/runners/sync_runtime_standby_status.py",
        }
    )
    _write_json(LOOP_STATUS_PATH, loop_status)

    orch_payload = {
        "timestamp": now_iso,
        "session_date": now.date().isoformat(),
        "stage": stage,
        "status": "ready" if market_open else "standby",
        "processes": [],
        "market_is_open": market_open,
        "reason": "live daemon not running; runtime/accounting surfaces synchronized",
        "runtime_db": _runtime_db_summary(),
        "nav": _nav_summary(),
        "source": "scripts/runners/sync_runtime_standby_status.py",
    }
    _write_json(ORCH_STATUS_PATH, orch_payload)

    daemon_payload = _read_json(DAEMON_STATUS_PATH)
    daemon_payload.update(
        {
            "timestamp": now_iso,
            "status": "stopped",
            "daemon_pid": None,
            "standby_status": stage,
            "source": "scripts/runners/sync_runtime_standby_status.py",
        }
    )
    _write_json(DAEMON_STATUS_PATH, daemon_payload)

    print(json.dumps({"status": "ok", "stage": stage, "timestamp": now_iso}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
