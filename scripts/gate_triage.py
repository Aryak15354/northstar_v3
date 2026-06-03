#!/usr/bin/env python3
"""Ordered gate triage checks for Northstar dry-run debugging."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LIVE_DIR = PROJECT_ROOT / "data/options/live"
RUNTIME_PATH = LIVE_DIR / "options_runtime_state.json"
WAL_PATH = LIVE_DIR / "write_journal.log"
DAEMON_STATUS_PATH = LIVE_DIR / "northstar_daemon_status.json"
RUNNER_STATUS_PATH = LIVE_DIR / "full_gate_runner_status.json"
GOV_EVENTS_PATH = LIVE_DIR / "governance_events.parquet"
DAEMON_LOCK_PATH = LIVE_DIR / "northstar_daemon.lock"
ENGINE_LOCK_PATH = LIVE_DIR / "options_engine.lock"
CODE_FREEZE_BASELINE_PATH = LIVE_DIR / "gate_code_freeze_baseline.json"

REQUIRED_RUNTIME_FIELDS = [
    "schema_version",
    "continuity_mode",
    "base_capital",
    "portfolio_risk_cap_pct",
    "realized_net_pnl",
    "unrealized_pnl",
    "net_equity",
    "week_start_equity",
    "risk_cap_value",
    "risk_remaining",
    "last_reconciled_at",
    "open_positions",
]

CODE_FREEZE_DIRS = [
    PROJECT_ROOT / "scripts",
    PROJECT_ROOT / "src/options",
    PROJECT_ROOT / "src/research",
    PROJECT_ROOT / "config",
]
CODE_FREEZE_SUFFIXES = {".py", ".yaml", ".yml", ".sh"}
LOCK_PROBE_ATTEMPTS = max(1, int(os.getenv("NORTHSTAR_LOCK_PROBE_ATTEMPTS", "12")))
LOCK_PROBE_RETRY_MS = max(1, int(os.getenv("NORTHSTAR_LOCK_PROBE_RETRY_MS", "20")))


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        if path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                return payload
    except Exception:
        return {}
    return {}


def _safe_iso(ts: Any) -> Optional[datetime]:
    try:
        if ts is None:
            return None
        return datetime.fromisoformat(str(ts))
    except Exception:
        return None


def _pid_alive(pid: Any) -> bool:
    try:
        pid_int = int(pid)
    except Exception:
        return False
    if pid_int <= 0:
        return False
    try:
        os.kill(pid_int, 0)
        return True
    except PermissionError:
        return True
    except OSError:
        return False


def _hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _code_fingerprint() -> Dict[str, str]:
    file_map: Dict[str, str] = {}
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
                file_map[rel] = _hash_file(path)
            except Exception:
                continue
    return dict(sorted(file_map.items()))


def _fingerprint_digest(file_map: Dict[str, str]) -> str:
    h = hashlib.sha256()
    for rel, digest in file_map.items():
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        h.update(digest.encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()


def _check_runtime_schema() -> Dict[str, Any]:
    runtime = _read_json(RUNTIME_PATH)
    if not runtime:
        return {"status": "fail", "details": {"error": "runtime_missing_or_unreadable"}}
    missing = [k for k in REQUIRED_RUNTIME_FIELDS if k not in runtime]
    if missing:
        return {"status": "fail", "details": {"missing_fields": missing}}
    return {
        "status": "pass",
        "details": {
            "current_mode": runtime.get("current_mode"),
            "net_equity": runtime.get("net_equity"),
            "block_new_risk": runtime.get("block_new_risk"),
        },
    }


def _check_wal() -> Dict[str, Any]:
    if not WAL_PATH.exists():
        return {"status": "warn", "details": {"warning": "wal_missing"}}
    prepared: Dict[str, int] = {}
    committed: set[str] = set()
    failed: set[str] = set()
    total = 0
    try:
        with open(WAL_PATH, "r", encoding="utf-8") as handle:
            for line in handle:
                total += 1
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                op_id = str(obj.get("op_id", "")).strip()
                stage = str(obj.get("stage", "")).strip().lower()
                if not op_id:
                    continue
                if stage == "prepared":
                    prepared[op_id] = prepared.get(op_id, 0) + 1
                elif stage == "committed":
                    committed.add(op_id)
                elif stage == "failed":
                    failed.add(op_id)
    except Exception as exc:
        return {"status": "fail", "details": {"error": f"wal_read_failed:{exc}"}}

    interrupted = sorted([op for op in prepared if op not in committed and op not in failed])
    if interrupted:
        return {
            "status": "fail",
            "details": {
                "interrupted_count": len(interrupted),
                "interrupted_sample": interrupted[:10],
                "total_lines": total,
            },
        }
    return {"status": "pass", "details": {"interrupted_count": 0, "total_lines": total}}


def _lock_probe(lock_path: Path) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "path": str(lock_path),
        "exists": lock_path.exists(),
        "pid": None,
        "pid_alive": False,
        "exclusive_lock_available": None,
        "probe_attempts": 0,
    }
    if not lock_path.exists():
        result["exclusive_lock_available"] = True
        return result

    payload = _read_json(lock_path)
    pid = payload.get("pid")
    result["pid"] = pid
    result["pid_alive"] = _pid_alive(pid)

    for attempt in range(LOCK_PROBE_ATTEMPTS):
        result["probe_attempts"] = attempt + 1
        try:
            with open(lock_path, "a+", encoding="utf-8") as handle:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                result["exclusive_lock_available"] = True
                break
        except OSError:
            result["exclusive_lock_available"] = False
        except Exception:
            result["exclusive_lock_available"] = False

        if attempt + 1 < LOCK_PROBE_ATTEMPTS:
            time.sleep(LOCK_PROBE_RETRY_MS / 1000.0)

    return result


def _check_locks() -> Dict[str, Any]:
    daemon = _lock_probe(DAEMON_LOCK_PATH)
    engine = _lock_probe(ENGINE_LOCK_PATH)

    issues: List[str] = []
    warnings: List[str] = []
    if daemon.get("exists") and daemon.get("pid") and not daemon.get("pid_alive"):
        if daemon.get("exclusive_lock_available") is False:
            issues.append("daemon_lock_stale_and_blocking")
        else:
            warnings.append("daemon_lock_stale_metadata")
    if engine.get("exists") and engine.get("pid") and not engine.get("pid_alive"):
        if engine.get("exclusive_lock_available") is False:
            issues.append("engine_lock_stale_and_blocking")
        else:
            warnings.append("engine_lock_stale_metadata")

    status = "fail" if issues else "pass"
    return {
        "status": status,
        "details": {
            "issues": issues,
            "warnings": warnings,
            "daemon_lock": daemon,
            "engine_lock": engine,
        },
    }


def _events_since(started_at: Optional[datetime]) -> pd.DataFrame:
    if not GOV_EVENTS_PATH.exists():
        return pd.DataFrame()
    try:
        df = pd.read_parquet(GOV_EVENTS_PATH)
        if df.empty or "timestamp" not in df.columns:
            return pd.DataFrame()
        ts = pd.to_datetime(df["timestamp"], errors="coerce")
        df = df.loc[~ts.isna()].copy()
        df["_ts"] = pd.to_datetime(df["timestamp"], errors="coerce")
        if started_at is not None:
            cutoff = pd.Timestamp(started_at)
            df = df.loc[df["_ts"] >= cutoff]
        return df
    except Exception:
        return pd.DataFrame()


def _check_process_exits() -> Dict[str, Any]:
    runner = _read_json(RUNNER_STATUS_PATH)
    daemon = _read_json(DAEMON_STATUS_PATH)
    started_at = _safe_iso(runner.get("started_at"))
    events = _events_since(started_at)
    process_restart_count = 0
    if not events.empty and "event_type" in events.columns:
        process_restart_count = int((events["event_type"].astype(str) == "process_restart").sum())

    daemon_pid = daemon.get("daemon_pid")
    daemon_alive = _pid_alive(daemon_pid)
    runner_pid = runner.get("runner_pid")
    runner_active = str(runner.get("status", "")).lower() == "running" and _pid_alive(runner_pid)
    if not daemon_alive:
        status = "fail" if runner_active else "warn"
        return {
            "status": status,
            "details": {
                "daemon_pid": daemon_pid,
                "daemon_alive": daemon_alive,
                "runner_active": runner_active,
                "process_restart_events": process_restart_count,
            },
        }

    status = "warn" if process_restart_count > 5 else "pass"
    return {
        "status": status,
        "details": {
            "daemon_pid": daemon_pid,
            "daemon_alive": daemon_alive,
            "process_restart_events": process_restart_count,
        },
    }


def _check_mode_transitions() -> Dict[str, Any]:
    runtime = _read_json(RUNTIME_PATH)
    runner = _read_json(RUNNER_STATUS_PATH)
    started_at = _safe_iso(runner.get("started_at"))
    events = _events_since(started_at)
    transition_count = 0
    if not events.empty and "event_type" in events.columns:
        transition_count = int((events["event_type"].astype(str) == "mode_transition").sum())

    current_mode = runtime.get("current_mode") if isinstance(runtime, dict) else None
    if not current_mode:
        return {
            "status": "fail",
            "details": {"error": "current_mode_missing", "mode_transition_events": transition_count},
        }
    return {
        "status": "pass",
        "details": {"current_mode": current_mode, "mode_transition_events": transition_count},
    }


def _check_code_freeze() -> Dict[str, Any]:
    baseline = _read_json(CODE_FREEZE_BASELINE_PATH)
    if not baseline:
        return {"status": "warn", "details": {"warning": "code_freeze_baseline_missing"}}
    baseline_map = baseline.get("files")
    if not isinstance(baseline_map, dict) or not baseline_map:
        return {"status": "warn", "details": {"warning": "code_freeze_baseline_invalid"}}

    current_map = _code_fingerprint()
    changed = sorted(
        path
        for path in set(baseline_map.keys()) | set(current_map.keys())
        if baseline_map.get(path) != current_map.get(path)
    )
    if changed:
        return {
            "status": "warn",
            "details": {
                "changed_files_count": len(changed),
                "changed_files_sample": changed[:30],
                "baseline_created_at": baseline.get("created_at"),
            },
        }
    return {
        "status": "pass",
        "details": {
            "baseline_created_at": baseline.get("created_at"),
            "fingerprint": _fingerprint_digest(current_map),
            "file_count": len(current_map),
        },
    }


def run_triage() -> Dict[str, Any]:
    checks = [
        ("runtime_schema", _check_runtime_schema()),
        ("wal", _check_wal()),
        ("lock_acquisition", _check_locks()),
        ("process_exits", _check_process_exits()),
        ("mode_transitions", _check_mode_transitions()),
        ("code_freeze", _check_code_freeze()),
    ]
    status_rank = {"pass": 0, "warn": 1, "fail": 2}
    overall = "pass"
    for _, result in checks:
        if status_rank.get(result.get("status", "fail"), 2) > status_rank[overall]:
            overall = str(result.get("status", "fail"))
    ordered = [
        {
            "order": idx,
            "check": name,
            "status": result.get("status"),
            "details": result.get("details", {}),
        }
        for idx, (name, result) in enumerate(checks, start=1)
    ]
    fail_reasons = [item["check"] for item in ordered if item["status"] == "fail"]
    warn_reasons = [item["check"] for item in ordered if item["status"] == "warn"]
    return {
        "timestamp": datetime.now().isoformat(),
        "overall_status": overall,
        "fail_reasons": fail_reasons,
        "warn_reasons": warn_reasons,
        "strict_exit_code": 0 if overall == "pass" else (2 if overall == "warn" else 1),
        "checks": ordered,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Ordered gate triage")
    parser.add_argument("--strict", action="store_true", help="Return non-zero on fail/warn")
    args = parser.parse_args()

    report = run_triage()
    print(json.dumps(report, indent=2))

    overall = str(report.get("overall_status", "fail"))
    if overall == "pass":
        return 0
    if overall == "warn":
        return 2 if args.strict else 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
