#!/usr/bin/env python3
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]


REQUIRED_RUNTIME_FIELDS = {
    "schema_version",
    "continuity_mode",
    "base_capital",
    "net_equity",
    "risk_cap_value",
    "risk_remaining",
    "timestamp",
}


def _require_file(path: Path) -> None:
    if not path.exists():
        raise RuntimeError(f"Missing required artifact: {path}")
    if path.stat().st_size <= 0:
        raise RuntimeError(f"Empty artifact: {path}")


def _validate_runtime_state() -> dict:
    path = ROOT / "data/options/live/options_runtime_state.json"
    _require_file(path)
    runtime = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(runtime, dict):
        raise RuntimeError("options_runtime_state must be an object")
    missing = sorted(REQUIRED_RUNTIME_FIELDS - set(runtime.keys()))
    if missing:
        raise RuntimeError(f"options_runtime_state missing fields: {missing}")
    if not any(key in runtime for key in ("active_positions", "open_positions")):
        raise RuntimeError("options_runtime_state missing position container (active_positions/open_positions)")
    if not any(key in runtime for key in ("trade_eligibility", "last_trade_eligibility")):
        raise RuntimeError("options_runtime_state missing trade eligibility payload")
    if not any(key in runtime for key in ("portfolio_risk_usage", "portfolio_risk_cap_pct")):
        raise RuntimeError("options_runtime_state missing portfolio risk payload")
    continuity_mode = str(runtime.get("continuity_mode", "")).strip().lower()
    if continuity_mode in {"fallback", "degraded", "recovery"}:
        raise RuntimeError(f"forbidden continuity_mode in strict runtime: {continuity_mode}")
    fallback_hits = []
    for key, value in runtime.items():
        key_l = str(key).lower()
        if "fallback" not in key_l:
            continue
        if isinstance(value, bool) and value:
            fallback_hits.append(key)
        elif isinstance(value, (int, float)) and float(value) > 0:
            fallback_hits.append(key)
        elif isinstance(value, str) and value.strip():
            fallback_hits.append(key)
    if fallback_hits:
        raise RuntimeError(f"fallback emissions present in options runtime: {sorted(fallback_hits)}")
    return {
        "continuity_mode": runtime.get("continuity_mode"),
        "net_equity": runtime.get("net_equity"),
        "risk_remaining": runtime.get("risk_remaining"),
    }


def _validate_dashboard_state() -> dict:
    path = ROOT / "data/options/live/options_dashboard_state.json"
    _require_file(path)
    state = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(state, dict):
        raise RuntimeError("options_dashboard_state must be an object")
    for key in ("timestamp", "schema_version", "net_equity", "risk_remaining"):
        if key not in state:
            raise RuntimeError(f"options_dashboard_state missing {key}")
    return {"keys": len(state.keys())}


def _validate_trade_ledger() -> dict:
    path = ROOT / "data/options/trade_ledger.parquet"
    _require_file(path)
    df = pd.read_parquet(path)
    if df.empty:
        raise RuntimeError("trade_ledger.parquet has zero rows")
    required = {"trade_id", "timestamp"}
    missing = sorted(required - set(df.columns))
    if missing:
        raise RuntimeError(f"trade_ledger missing columns: {missing}")
    if not any(col in df.columns for col in ("symbol", "underlying")):
        raise RuntimeError("trade_ledger missing instrument column (symbol/underlying)")
    return {"rows": int(len(df)), "columns": int(len(df.columns))}


def _validate_runtime_consistency() -> dict:
    runtime_path = ROOT / "data/options/live/options_runtime_state.json"
    runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
    runtime_open = int(len(runtime.get("open_positions") or runtime.get("active_positions") or []))

    ledger_path = ROOT / "data/options/trade_ledger.parquet"
    _require_file(ledger_path)
    ledger = pd.read_parquet(ledger_path)
    if ledger.empty:
        raise RuntimeError("trade_ledger.parquet has zero rows")
    if not {"trade_id", "action"}.issubset(ledger.columns):
        raise RuntimeError("trade_ledger missing trade_id/action columns")
    actions = ledger.copy()
    actions["action"] = actions["action"].astype(str).str.lower()
    grouped = actions.groupby("trade_id")["action"].agg(list)
    ledger_open = int(sum("open" in seq and "close" not in seq for seq in grouped))
    if runtime_open != ledger_open:
        raise RuntimeError(
            f"runtime open positions ({runtime_open}) do not match immutable trade ledger ({ledger_open})"
        )

    runtime_db = ROOT / "data/runtime/portfolio_runtime.db"
    if runtime_db.exists():
        con = sqlite3.connect(runtime_db)
        try:
            lifecycle_open = int(
                pd.read_sql_query(
                    "SELECT COUNT(*) AS n FROM position_lifecycle_table WHERE close_event_id IS NULL",
                    con,
                )["n"].iloc[0]
            )
        finally:
            con.close()
        if lifecycle_open != ledger_open:
            raise RuntimeError(
                f"runtime lifecycle open rows ({lifecycle_open}) do not match immutable trade ledger ({ledger_open})"
            )
    else:
        lifecycle_open = 0

    return {
        "runtime_open_positions": runtime_open,
        "ledger_open_positions": ledger_open,
        "lifecycle_open_positions": lifecycle_open,
    }


def main() -> int:
    report = {
        "check": "strict_options_runtime_check",
        "runtime": _validate_runtime_state(),
        "dashboard": _validate_dashboard_state(),
        "ledger": _validate_trade_ledger(),
        "consistency": _validate_runtime_consistency(),
    }
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
