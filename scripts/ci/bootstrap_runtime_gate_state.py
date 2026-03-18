#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.options.state_io import StateIOManager

LIVE_DIR = ROOT / "data/options/live"
OPTIONS_DIR = ROOT / "data/options"
RUNTIME_DB = ROOT / "data/runtime/portfolio_runtime.db"
RUNTIME_MATERIALIZED_DIR = ROOT / "data/processed/runtime"
CODE_FREEZE_BASELINE_PATH = LIVE_DIR / "gate_code_freeze_baseline.json"
RUNNER_STATUS_PATH = LIVE_DIR / "full_gate_runner_status.json"
DAEMON_STATUS_PATH = LIVE_DIR / "northstar_daemon_status.json"

CODE_FREEZE_DIRS = [
    ROOT / "scripts",
    ROOT / "src/options",
    ROOT / "src/research",
    ROOT / "config",
]
CODE_FREEZE_SUFFIXES = {".py", ".yaml", ".yml", ".sh"}


def _hash_file(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _code_fingerprint() -> Dict[str, str]:
    fingerprints: Dict[str, str] = {}
    for root in CODE_FREEZE_DIRS:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in CODE_FREEZE_SUFFIXES:
                continue
            rel = str(path.relative_to(ROOT))
            try:
                fingerprints[rel] = _hash_file(path)
            except Exception:
                continue
    return dict(sorted(fingerprints.items()))


def _fingerprint_digest(file_map: Dict[str, str]) -> str:
    import hashlib

    digest = hashlib.sha256()
    for rel, value in file_map.items():
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(value.encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def _seed_runtime_payload(now: datetime) -> Dict[str, Any]:
    base_capital = 500_000.0
    risk_cap_value = 50_000.0
    now_iso = now.isoformat()
    return {
        "timestamp": now_iso,
        "schema_version": "2.1.0",
        "continuity_mode": True,
        "recovery_mode": False,
        "current_mode": "paper_trading",
        "base_capital": base_capital,
        "portfolio_risk_cap_pct": 0.10,
        "realized_net_pnl": 0.0,
        "unrealized_pnl": 0.0,
        "net_equity": base_capital,
        "week_start_equity": base_capital,
        "risk_cap_value": risk_cap_value,
        "risk_remaining": risk_cap_value,
        "last_reconciled_at": now_iso,
        "open_positions": [],
        "active_positions": [],
        "block_new_risk": False,
        "portfolio_risk_usage": {
            "total_risk": 0.0,
            "risk_cap": risk_cap_value,
            "risk_pct": 0.0,
            "risk_cap_pct": 0.10,
        },
        "trade_eligibility": {
            "signal_generated": False,
            "rejected": False,
            "violations": [],
            "timestamp": now_iso,
        },
        "last_trade_eligibility": {
            "signal_generated": False,
            "rejected": False,
            "violations": [],
            "timestamp": now_iso,
        },
        "last_kill_switch": {
            "active": False,
            "reason": "",
            "timestamp": now_iso,
        },
        "market_snapshot": {
            "timestamp": now_iso,
            "session": "CI_BOOTSTRAP",
            "underlying": "NIFTY",
            "spot": 0.0,
        },
        "iv_history": {
            "NIFTY": [
                {
                    "timestamp": now_iso,
                    "iv": 0.20,
                }
            ]
        },
        "greeks_history": [],
        "regime_history": [
            {
                "timestamp": (now - timedelta(days=1)).isoformat(),
                "routed_regime": "neutral",
            },
            {
                "timestamp": now_iso,
                "routed_regime": "neutral",
            },
        ],
    }


def _seed_trade_ledger(now: datetime) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "trade_id": f"CI_BOOTSTRAP_{now.strftime('%Y%m%d_%H%M%S')}",
                "timestamp": now.replace(tzinfo=None),
                "action": "bootstrap",
                "strategy_type": "system_bootstrap",
                "regime_at_entry": "neutral",
                "underlying": "NIFTY",
                "expiry": (now + timedelta(days=7)).replace(tzinfo=None),
                "legs": "[]",
                "entry_credit_debit": 0.0,
                "max_loss": 0.0,
                "max_profit": 0.0,
                "exit_value": 0.0,
                "gross_pnl": 0.0,
                "costs": 0.0,
                "tax": 0.0,
                "net_pnl": 0.0,
                "days_held": 0,
                "exit_reason": "ci_bootstrap_seed",
                "greeks_at_entry": "{}",
                "greeks_at_exit": "{}",
            }
        ]
    )


def _build_dashboard_payload(runtime_payload: Dict[str, Any]) -> Dict[str, Any]:
    timestamp = str(runtime_payload.get("timestamp") or datetime.now(timezone.utc).isoformat())
    trade_eligibility = dict(runtime_payload.get("trade_eligibility") or runtime_payload.get("last_trade_eligibility") or {})
    kill_switch = dict(runtime_payload.get("last_kill_switch") or {})
    return {
        "timestamp": timestamp,
        "schema_version": str(runtime_payload.get("schema_version") or "2.1.0"),
        "continuity_mode": runtime_payload.get("continuity_mode", True),
        "recovery_mode": bool(runtime_payload.get("recovery_mode", False)),
        "base_capital": float(runtime_payload.get("base_capital", 0.0) or 0.0),
        "net_equity": float(runtime_payload.get("net_equity", 0.0) or 0.0),
        "risk_cap_value": float(runtime_payload.get("risk_cap_value", 0.0) or 0.0),
        "risk_remaining": float(runtime_payload.get("risk_remaining", 0.0) or 0.0),
        "realized_net_pnl": float(runtime_payload.get("realized_net_pnl", 0.0) or 0.0),
        "unrealized_pnl": float(runtime_payload.get("unrealized_pnl", 0.0) or 0.0),
        "active_positions": list(runtime_payload.get("active_positions") or runtime_payload.get("open_positions") or []),
        "portfolio_greeks": {
            "delta": 0.0,
            "gamma": 0.0,
            "theta": 0.0,
            "vega": 0.0,
            "exposure": 0.0,
        },
        "portfolio_risk_usage": dict(runtime_payload.get("portfolio_risk_usage") or {}),
        "weekly_risk_usage": {
            "risk_used": 0.0,
            "risk_limit": float(runtime_payload.get("risk_cap_value", 0.0) or 0.0),
        },
        "trade_eligibility": trade_eligibility,
        "kill_switch_status": kill_switch,
        "iv_surface": [
            {
                "timestamp": point.get("timestamp", timestamp),
                "underlying": underlying,
                "iv": float(point.get("iv", 0.0) or 0.0),
            }
            for underlying, points in dict(runtime_payload.get("iv_history") or {}).items()
            for point in (points or [])
            if isinstance(point, dict)
        ],
        "greeks_history": list(runtime_payload.get("greeks_history") or []),
        "market_snapshot": dict(runtime_payload.get("market_snapshot") or {}),
        "market_state": dict(runtime_payload.get("market_snapshot") or {}),
        "data_sources": {"bootstrap": "ci_runtime_gate"},
        "data_quality": "REAL_DATA_ONLY",
        "current_regime": "neutral",
        "last_reconciled_at": str(runtime_payload.get("last_reconciled_at") or timestamp),
    }


def bootstrap_ci_runtime_state() -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    LIVE_DIR.mkdir(parents=True, exist_ok=True)
    OPTIONS_DIR.mkdir(parents=True, exist_ok=True)
    RUNTIME_DB.parent.mkdir(parents=True, exist_ok=True)
    RUNTIME_MATERIALIZED_DIR.mkdir(parents=True, exist_ok=True)

    manager = StateIOManager(LIVE_DIR)
    runtime_payload = _seed_runtime_payload(now)

    if not manager.write_runtime_state(runtime_payload):
        raise RuntimeError("failed to write canonical bootstrap runtime state")
    normalized_dashboard = _build_dashboard_payload(runtime_payload)
    if not manager.writer.write_json(LIVE_DIR / "options_dashboard_state.json", normalized_dashboard):
        raise RuntimeError("failed to write canonical bootstrap dashboard state")
    if not manager.write_ledger(_seed_trade_ledger(now)):
        raise RuntimeError("failed to write bootstrap trade ledger")

    if not manager.wal_path.exists():
        manager.wal_path.touch()

    fingerprints = _code_fingerprint()
    CODE_FREEZE_BASELINE_PATH.write_text(
        json.dumps(
            {
                "created_at": now.isoformat(),
                "created_by": "scripts/ci/bootstrap_runtime_gate_state.py",
                "fingerprint": _fingerprint_digest(fingerprints),
                "files": fingerprints,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    RUNNER_STATUS_PATH.write_text(
        json.dumps(
            {
                "status": "ci_bootstrap_ready",
                "started_at": now.isoformat(),
                "runner_pid": 0,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    DAEMON_STATUS_PATH.write_text(
        json.dumps(
            {
                "status": "ci_bootstrap_ready",
                "updated_at": now.isoformat(),
                "daemon_pid": 0,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    return {
        "status": "ok",
        "runtime_state_path": str(LIVE_DIR / "options_runtime_state.json"),
        "dashboard_state_path": str(LIVE_DIR / "options_dashboard_state.json"),
        "trade_ledger_path": str(OPTIONS_DIR / "trade_ledger.parquet"),
        "wal_path": str(manager.wal_path),
        "code_freeze_baseline_path": str(CODE_FREEZE_BASELINE_PATH),
        "runtime_db": str(RUNTIME_DB),
        "runtime_materialized_dir": str(RUNTIME_MATERIALIZED_DIR),
    }


def main() -> int:
    print(json.dumps(bootstrap_ci_runtime_state(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
