#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.runtime import RuntimeEventStore

LIVE_DIR = PROJECT_ROOT / "data/options/live"
BASELINE_PATH = LIVE_DIR / "gate_code_freeze_baseline.json"
BOOTSTRAP_MANIFEST_PATH = LIVE_DIR / "runtime_gate_ci_bootstrap.json"
RUNTIME_STATE_PATH = LIVE_DIR / "options_runtime_state.json"
DASHBOARD_STATE_PATH = LIVE_DIR / "options_dashboard_state.json"
GOVERNANCE_EVENTS_PATH = LIVE_DIR / "governance_events.parquet"
RUNNER_STATUS_PATH = LIVE_DIR / "full_gate_runner_status.json"
DAEMON_STATUS_PATH = LIVE_DIR / "northstar_daemon_status.json"
WAL_PATH = LIVE_DIR / "write_journal.log"
MARKET_DATA_PATH = LIVE_DIR / "market_data_latest.json"
TRADE_LEDGER_PATH = PROJECT_ROOT / "data/options/trade_ledger.parquet"
MASTER_LEDGER_PATH = PROJECT_ROOT / "data/pnl/master_ledger.parquet"
RUNTIME_DB_PATH = PROJECT_ROOT / "data/runtime/portfolio_runtime.db"
TEST_COUNT_BASELINE_PATH = PROJECT_ROOT / "data/processed/test_count_baseline.json"

CODE_FREEZE_DIRS = [
    PROJECT_ROOT / "scripts",
    PROJECT_ROOT / "src/options",
    PROJECT_ROOT / "src/research",
    PROJECT_ROOT / "config",
]
CODE_FREEZE_SUFFIXES = {".py", ".yaml", ".yml", ".sh"}


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _compute_code_map() -> Dict[str, str]:
    out: Dict[str, str] = {}
    for root in CODE_FREEZE_DIRS:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in CODE_FREEZE_SUFFIXES:
                continue
            rel = str(path.relative_to(PROJECT_ROOT))
            try:
                out[rel] = _hash_file(path)
            except Exception:
                continue
    return dict(sorted(out.items()))


def _digest(file_map: Dict[str, str]) -> str:
    digest = hashlib.sha256()
    for rel, checksum in file_map.items():
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(checksum.encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _bootstrap_runtime_fixtures(now: datetime) -> dict:
    now_iso = now.isoformat()
    transition_ts = now.replace(microsecond=0).isoformat()

    runtime_payload = {
        "schema_version": "ci-bootstrap-v1",
        "timestamp": now_iso,
        "continuity_mode": "normal_operation",
        "current_mode": "normal_operation",
        "base_capital": 1_000_000.0,
        "portfolio_risk_cap_pct": 0.04,
        "portfolio_risk_usage": 0.0,
        "realized_net_pnl": 0.0,
        "unrealized_pnl": 0.0,
        "net_equity": 1_000_000.0,
        "week_start_equity": 1_000_000.0,
        "risk_cap_value": 40_000.0,
        "risk_remaining": 40_000.0,
        "last_reconciled_at": now_iso,
        "open_positions": [],
        "active_positions": [],
        "block_new_risk": False,
        "last_kill_switch": False,
        "mode_constraints": {},
        "trade_eligibility": {
            "eligible": True,
            "reason": "ci_bootstrap",
            "evaluated_at": now_iso,
        },
        "last_trade_eligibility": {
            "eligible": True,
            "reason": "ci_bootstrap",
            "evaluated_at": now_iso,
        },
        "source": "scripts/ci/bootstrap_runtime_gate_state.py",
    }
    _write_json(RUNTIME_STATE_PATH, runtime_payload)

    dashboard_payload = {
        "timestamp": now_iso,
        "schema_version": "ci-bootstrap-v1",
        "net_equity": runtime_payload["net_equity"],
        "risk_remaining": runtime_payload["risk_remaining"],
        "active_positions": [],
        "source": "scripts/ci/bootstrap_runtime_gate_state.py",
    }
    _write_json(DASHBOARD_STATE_PATH, dashboard_payload)

    market_payload = {
        "timestamp": now_iso,
        "market_state": "ci_bootstrap",
        "source": "scripts/ci/bootstrap_runtime_gate_state.py",
        "symbols": [],
    }
    _write_json(MARKET_DATA_PATH, market_payload)

    runner_payload = {
        "status": "idle",
        "started_at": now_iso,
        "runner_pid": None,
        "source": "scripts/ci/bootstrap_runtime_gate_state.py",
    }
    _write_json(RUNNER_STATUS_PATH, runner_payload)

    daemon_payload = {
        "status": "stopped",
        "timestamp": now_iso,
        "daemon_pid": None,
        "current_mode": runtime_payload["current_mode"],
        "source": "scripts/ci/bootstrap_runtime_gate_state.py",
    }
    _write_json(DAEMON_STATUS_PATH, daemon_payload)

    WAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    WAL_PATH.write_text("", encoding="utf-8")

    governance_events = pd.DataFrame(
        [
            {
                "timestamp": transition_ts,
                "event_type": "mode_transition",
                "mode_before": "ci_bootstrap",
                "mode_after": runtime_payload["current_mode"],
                "reason": "runtime_gate_bootstrap",
            }
        ]
    )
    GOVERNANCE_EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    governance_events.to_parquet(GOVERNANCE_EVENTS_PATH, index=False)

    trade_ledger = pd.DataFrame(
        [
            {
                "trade_id": "ci-bootstrap-1",
                "timestamp": transition_ts,
                "action": "open",
                "symbol": "NIFTY",
            },
            {
                "trade_id": "ci-bootstrap-1",
                "timestamp": now_iso,
                "action": "close",
                "symbol": "NIFTY",
            },
        ]
    )
    TRADE_LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    trade_ledger.to_parquet(TRADE_LEDGER_PATH, index=False)

    master_ledger = pd.DataFrame(
        [
            {
                "entry_id": "CI_BOOTSTRAP_CASH_IN",
                "entry_type": "CASH_IN",
                "amount": 1_000_000.0,
                "notional": 1_000_000.0,
                "transaction_cost": 0.0,
                "trade_date": now.date().isoformat(),
                "settlement_date": now.date().isoformat(),
                "recorded_at": now_iso,
                "description": "CI runtime gate bootstrap capital seed",
                "source": "scripts/ci/bootstrap_runtime_gate_state.py",
            }
        ]
    )
    MASTER_LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    master_ledger.to_parquet(MASTER_LEDGER_PATH, index=False)

    RUNTIME_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    store = RuntimeEventStore(str(RUNTIME_DB_PATH), writer_name="runtime_gate_bootstrap")
    store.close()

    test_count_payload = {
        "collected_tests": 1,
        "generated_at": now_iso,
        "source": "scripts/ci/bootstrap_runtime_gate_state.py",
        "mode": "contract_placeholder",
    }
    _write_json(TEST_COUNT_BASELINE_PATH, test_count_payload)

    manifest = {
        "generated_at": now_iso,
        "created_by": "scripts/ci/bootstrap_runtime_gate_state.py",
        "artifacts": {
            "runtime_state": str(RUNTIME_STATE_PATH),
            "dashboard_state": str(DASHBOARD_STATE_PATH),
            "market_data": str(MARKET_DATA_PATH),
            "governance_events": str(GOVERNANCE_EVENTS_PATH),
            "runner_status": str(RUNNER_STATUS_PATH),
            "daemon_status": str(DAEMON_STATUS_PATH),
            "wal": str(WAL_PATH),
            "trade_ledger": str(TRADE_LEDGER_PATH),
            "master_ledger": str(MASTER_LEDGER_PATH),
            "runtime_db": str(RUNTIME_DB_PATH),
            "test_count_baseline": str(TEST_COUNT_BASELINE_PATH),
        },
    }
    _write_json(BOOTSTRAP_MANIFEST_PATH, manifest)
    return manifest


def write_baseline() -> dict:
    file_map = _compute_code_map()
    bootstrap_now = datetime.now(timezone.utc)
    payload = {
        "created_at": bootstrap_now.isoformat(),
        "created_by": "scripts/ci/bootstrap_runtime_gate_state.py",
        "fingerprint": _digest(file_map),
        "file_count": len(file_map),
        "files": file_map,
    }
    BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
    BASELINE_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    manifest = _bootstrap_runtime_fixtures(bootstrap_now)
    payload["bootstrap_manifest"] = manifest
    return payload


def verify_baseline() -> dict:
    if not BASELINE_PATH.exists():
        raise RuntimeError(f"Missing code-freeze baseline: {BASELINE_PATH}")
    payload = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    baseline_map = payload.get("files")
    if not isinstance(baseline_map, dict) or not baseline_map:
        raise RuntimeError("Invalid code-freeze baseline payload")
    current_map = _compute_code_map()
    changed = sorted(
        path
        for path in set(baseline_map.keys()) | set(current_map.keys())
        if baseline_map.get(path) != current_map.get(path)
    )
    return {
        "created_at": payload.get("created_at"),
        "baseline_fingerprint": payload.get("fingerprint"),
        "current_fingerprint": _digest(current_map),
        "changed_files_count": len(changed),
        "changed_files_sample": changed[:50],
        "status": "pass" if not changed else "fail",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap or verify runtime gate state")
    parser.add_argument("--write", action="store_true", help="Write a fresh code-freeze baseline")
    parser.add_argument("--verify", action="store_true", help="Verify current code against baseline")
    args = parser.parse_args()

    if args.write == args.verify:
        parser.error("choose exactly one of --write or --verify")

    if args.write:
        report = write_baseline()
        manifest = report.get("bootstrap_manifest") if isinstance(report, dict) else {}
        summary = {
            "created_at": report.get("created_at"),
            "created_by": report.get("created_by"),
            "fingerprint": report.get("fingerprint"),
            "file_count": report.get("file_count"),
            "baseline_path": str(BASELINE_PATH),
            "bootstrap_manifest_path": str(BOOTSTRAP_MANIFEST_PATH),
            "bootstrap_artifact_count": len((manifest or {}).get("artifacts", {})),
        }
        print(json.dumps(summary, indent=2))
        return 0

    report = verify_baseline()
    print(json.dumps(report, indent=2))
    return 0 if report.get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
