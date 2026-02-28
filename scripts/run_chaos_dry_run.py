#!/usr/bin/env python3
"""72-hour resilience dry-run harness with controlled fault injections."""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd
import yaml
import fcntl


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.options.state_recovery import StateRecoveryManager
from src.options.runtime_guard import write_runtime_signature


LIVE_DIR = PROJECT_ROOT / "data/options/live"
RUNTIME_PATH = LIVE_DIR / "options_runtime_state.json"
HEARTBEAT_PATH = LIVE_DIR / "live_engine_heartbeat.json"
WAL_PATH = LIVE_DIR / "write_journal.log"
GOV_EVENTS_PATH = LIVE_DIR / "governance_events.parquet"
DRY_RUN_REPORT_PATH = LIVE_DIR / "chaos_dry_run_report.json"
LOG_PATH = PROJECT_ROOT / "logs/chaos_dry_run_daemon.log"


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        if path.exists():
            payload = json.loads(path.read_text())
            if isinstance(payload, dict):
                return payload
    except Exception:
        return {}
    return {}


def _write_json_atomic(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f"{path.suffix}.tmp")
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    tmp.replace(path)


def _append_wal_prepared(op_id: str, target_path: Path) -> None:
    WAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "op_id": op_id,
        "stage": "prepared",
        "target_path": str(target_path),
        "timestamp": datetime.now().isoformat(),
        "checksum_before": None,
        "checksum_after": None,
        "error": None,
    }
    with open(WAL_PATH, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry) + "\n")


def _inject_wal_interruption(events: List[Dict[str, Any]]) -> None:
    op_id = f"chaos_wal_{int(time.time())}"
    _append_wal_prepared(op_id, RUNTIME_PATH)
    events.append({"timestamp": datetime.now().isoformat(), "injection": "wal_interruption", "op_id": op_id})


def _inject_runtime_corruption(events: List[Dict[str, Any]]) -> None:
    if RUNTIME_PATH.exists():
        backup = LIVE_DIR / f"runtime_corrupt_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        backup.write_text(RUNTIME_PATH.read_text(), encoding="utf-8")
    RUNTIME_PATH.write_text("{\"corrupted_json\": ", encoding="utf-8")
    events.append({"timestamp": datetime.now().isoformat(), "injection": "runtime_corruption"})


def _inject_stale_heartbeat(events: List[Dict[str, Any]], stale_minutes: int = 30) -> None:
    payload = _read_json(HEARTBEAT_PATH)
    payload["timestamp"] = (datetime.now() - timedelta(minutes=stale_minutes)).isoformat()
    payload["status"] = "alive"
    _write_json_atomic(HEARTBEAT_PATH, payload)
    live_pid = None
    status_payload = _read_json(LIVE_DIR / "northstar_daemon_status.json")
    try:
        live_pid = int(
            ((status_payload.get("processes", {}) or {}).get("live_engine", {}) or {}).get("pid", 0)
            or 0
        )
    except Exception:
        live_pid = 0
    stopped = False
    if live_pid and live_pid > 0:
        try:
            os.kill(live_pid, signal.SIGSTOP)
            stopped = True
        except Exception:
            stopped = False
    events.append(
        {
            "timestamp": datetime.now().isoformat(),
            "injection": "stale_heartbeat",
            "live_pid": live_pid,
            "live_pid_sigstop": stopped,
        }
    )


def _ensure_runtime_for_injection(
    config_base_capital: float,
    portfolio_risk_cap_pct: float,
) -> Dict[str, Any]:
    runtime = _read_json(RUNTIME_PATH)
    required_keys = {
        "schema_version",
        "base_capital",
        "portfolio_risk_cap_pct",
        "net_equity",
        "open_positions",
    }
    if runtime and all(k in runtime for k in required_keys):
        return runtime

    base_cap = float(runtime.get("base_capital", config_base_capital) or config_base_capital)
    risk_cap = float(portfolio_risk_cap_pct or 0.10)
    StateRecoveryManager(LIVE_DIR).rebuild_from_ledger(
        recovery_mode=False,
        base_capital=base_cap,
        portfolio_risk_cap_pct=risk_cap,
    )
    return _read_json(RUNTIME_PATH)


def _inject_mode_transition(
    events: List[Dict[str, Any]],
    config_base_capital: float,
    portfolio_risk_cap_pct: float,
) -> None:
    runtime = _ensure_runtime_for_injection(
        config_base_capital=config_base_capital,
        portfolio_risk_cap_pct=portfolio_risk_cap_pct,
    )
    if not runtime:
        events.append(
            {
                "timestamp": datetime.now().isoformat(),
                "injection": "mode_transition",
                "status": "skipped_runtime_unavailable",
            }
        )
        return
    runtime.setdefault("alpha_os", {})
    runtime["alpha_os"]["fallback_tier"] = 2
    runtime["alpha_os"]["diagnostics"] = {
        "drift": {"severity": "high"},
        "shadow_divergence_index": {"sdi": 0.55},
        "regime_snapshot": {"probabilities": {"CRISIS": 0.78}},
    }
    runtime["convexity_breach"] = True
    _write_json_atomic(RUNTIME_PATH, runtime)
    write_runtime_signature(RUNTIME_PATH)
    events.append({"timestamp": datetime.now().isoformat(), "injection": "mode_transition"})


def _inject_drawdown(
    events: List[Dict[str, Any]],
    config_base_capital: float,
    portfolio_risk_cap_pct: float,
) -> None:
    runtime = _ensure_runtime_for_injection(
        config_base_capital=config_base_capital,
        portfolio_risk_cap_pct=portfolio_risk_cap_pct,
    )
    if not runtime:
        events.append(
            {
                "timestamp": datetime.now().isoformat(),
                "injection": "drawdown_descaling",
                "status": "skipped_runtime_unavailable",
            }
        )
        return
    net_equity = float(runtime.get("net_equity", runtime.get("base_capital", 100000.0)) or 100000.0)
    runtime["capital_scaling"] = {
        "equity_high_water_mark": float(max(net_equity / 0.82, net_equity + 1.0)),
        "current_equity": float(net_equity),
    }
    runtime["survival_mode_activations_recent"] = 6
    runtime["high_drift_duration_minutes"] = 360
    _write_json_atomic(RUNTIME_PATH, runtime)
    write_runtime_signature(RUNTIME_PATH)
    events.append({"timestamp": datetime.now().isoformat(), "injection": "drawdown_descaling"})


def _trigger_freeze_research_check(events: List[Dict[str, Any]]) -> None:
    cmd = [
        sys.executable,
        str(PROJECT_ROOT / "scripts/run_research_worker.py"),
        "--once",
        "--config",
        str(PROJECT_ROOT / "config/research_policy.yaml"),
    ]
    proc = subprocess.run(cmd, cwd=str(PROJECT_ROOT), capture_output=True, text=True, check=False)
    events.append(
        {
            "timestamp": datetime.now().isoformat(),
            "injection": "research_freeze_trigger",
            "returncode": proc.returncode,
        }
    )


def _start_daemon(config: Path, profile: str) -> subprocess.Popen:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    handle = open(LOG_PATH, "a", encoding="utf-8")
    cmd = [
        sys.executable,
        str(PROJECT_ROOT / "scripts/northstar_daemon.py"),
        "--config",
        str(config),
        "--system-profile",
        profile,
    ]
    proc = subprocess.Popen(cmd, cwd=str(PROJECT_ROOT), stdout=handle, stderr=subprocess.STDOUT, text=True)
    handle.close()
    return proc


def _prepare_effective_config(config: Path, quick: bool) -> Path:
    if not quick:
        return config
    payload = yaml.safe_load(config.read_text())
    if not isinstance(payload, dict):
        raise RuntimeError(f"Invalid daemon config: {config}")
    payload.setdefault("live_engine", {})
    payload.setdefault("resource_limits", {})
    payload["governance_interval_minutes"] = 0.5
    payload["live_engine"]["interval_seconds"] = 30
    payload["live_engine"]["market_hours_only"] = False
    payload["resource_limits"]["heartbeat_timeout_multiplier"] = 1.2
    payload["resource_limits"]["cpu_threshold"] = 90.0
    payload["resource_limits"]["memory_threshold"] = 95.0

    tmp = LIVE_DIR / "northstar_daemon.chaos_quick.yaml"
    with open(tmp, "w", encoding="utf-8") as handle:
        yaml.safe_dump(payload, handle, sort_keys=False)
    return tmp


def _stop_daemon(proc: subprocess.Popen, timeout_seconds: int = 30) -> None:
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=10)


def _collect_validations(daemon_proc: subprocess.Popen, started_at: datetime) -> Dict[str, Any]:
    validations: Dict[str, Any] = {
        "daemon_exit_code": daemon_proc.poll(),
        "recovery_report_exists": bool((LIVE_DIR / "state_recovery_report.json").exists()),
        "runtime_exists": bool(RUNTIME_PATH.exists()),
        "governance_events_exists": bool(GOV_EVENTS_PATH.exists()),
        "mode_transition_seen": False,
        "heartbeat_stale_seen": False,
        "wal_interruption_seen": False,
        "descale_or_drawdown_seen": False,
        "no_orphan_locks": True,
        "ledger_open_trade_ids_count": 0,
        "runtime_open_positions_count": 0,
        "runtime_ledger_open_count_match": True,
        "runtime_ledger_open_id_match": True,
    }

    if GOV_EVENTS_PATH.exists():
        try:
            df = pd.read_parquet(GOV_EVENTS_PATH)
            if not df.empty and "event_type" in df.columns:
                ts = pd.to_datetime(df.get("timestamp"), errors="coerce", utc=True)
                cutoff = pd.Timestamp(started_at, tz="UTC")
                recent = df[ts >= cutoff]
                events = set(str(x) for x in recent["event_type"].dropna().tolist())
                validations["mode_transition_seen"] = "mode_transition" in events
                validations["heartbeat_stale_seen"] = "heartbeat_stale" in events
                validations["wal_interruption_seen"] = "wal_interruption" in events
                validations["descale_or_drawdown_seen"] = (
                    "drawdown_alert" in events or "risk_limit_exceeded" in events
                )
        except Exception:
            pass

    for lock_file in [LIVE_DIR / "options_engine.lock", LIVE_DIR / "northstar_daemon.lock"]:
        if not lock_file.exists():
            continue
        try:
            with open(lock_file, "r", encoding="utf-8") as handle:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except OSError:
            validations["no_orphan_locks"] = False
        except Exception:
            validations["no_orphan_locks"] = False

    recovery = StateRecoveryManager(LIVE_DIR).check_state_integrity()
    validations["runtime_integrity_status"] = recovery.get("overall_status")
    try:
        ledger_path = LIVE_DIR.parent / "trade_ledger.parquet"
        runtime_payload = _read_json(RUNTIME_PATH)
        runtime_open_positions = runtime_payload.get("open_positions", []) if isinstance(runtime_payload, dict) else []
        runtime_open_ids = {
            str((row or {}).get("position_id") or "").strip()
            for row in runtime_open_positions
            if isinstance(row, dict) and str((row or {}).get("position_id") or "").strip()
        }
        validations["runtime_open_positions_count"] = int(len(runtime_open_ids))

        ledger_open_ids = set()
        if ledger_path.exists():
            ledger = pd.read_parquet(ledger_path)
            if not ledger.empty and "action" in ledger.columns and "trade_id" in ledger.columns:
                action = ledger["action"].astype(str).str.lower()
                opened = {
                    str(x).strip()
                    for x in ledger.loc[action == "open", "trade_id"].astype(str).tolist()
                    if str(x).strip()
                }
                closed = {
                    str(x).strip()
                    for x in ledger.loc[action == "close", "trade_id"].astype(str).tolist()
                    if str(x).strip()
                }
                ledger_open_ids = {x for x in opened if x not in closed}
        validations["ledger_open_trade_ids_count"] = int(len(ledger_open_ids))
        validations["runtime_ledger_open_count_match"] = int(len(runtime_open_ids)) == int(len(ledger_open_ids))
        validations["runtime_ledger_open_id_match"] = runtime_open_ids == ledger_open_ids
    except Exception:
        validations["runtime_ledger_open_count_match"] = False
        validations["runtime_ledger_open_id_match"] = False
    return validations


def run_dry_run(
    duration_hours: float,
    config: Path,
    profile: str,
    quick: bool,
    max_daemon_restarts: int = 8,
    daemon_restart_cooldown_seconds: float = 10.0,
) -> Dict[str, Any]:
    start_time = datetime.now()
    end_time = start_time + timedelta(hours=duration_hours)
    injections: List[Dict[str, Any]] = []
    effective_config = _prepare_effective_config(config=config, quick=quick)
    effective_payload: Dict[str, Any] = {}
    try:
        loaded = yaml.safe_load(Path(effective_config).read_text())
        if isinstance(loaded, dict):
            effective_payload = loaded
    except Exception:
        effective_payload = {}
    configured_base_capital = float(
        ((effective_payload.get("operational_limits", {}) or {}).get("base_capital", 500000.0) or 500000.0)
    )
    configured_risk_cap_pct = float(effective_payload.get("portfolio_risk_cap_pct", 0.10) or 0.10)
    proc = _start_daemon(config=effective_config, profile=profile)
    daemon_restart_count = 0
    daemon_exit_events = 0
    hard_daemon_failure = False

    # Injection schedule in seconds from start.
    if quick:
        schedule: List[Tuple[int, str]] = [
            (45, "wal"),
            (90, "runtime"),
            (135, "heartbeat"),
            (180, "mode"),
            (225, "freeze"),
            (270, "drawdown"),
        ]
    else:
        schedule = [
            (5 * 60, "wal"),
            (10 * 60, "runtime"),
            (15 * 60, "heartbeat"),
            (20 * 60, "mode"),
            (25 * 60, "freeze"),
            (30 * 60, "drawdown"),
        ]
    pending = list(schedule)
    observed = {
        "block_new_risk_seen": False,
        "non_normal_mode_seen": False,
    }

    try:
        while datetime.now() < end_time:
            if proc.poll() is not None:
                daemon_exit_events += 1
                injections.append(
                    {
                        "timestamp": datetime.now().isoformat(),
                        "event": "daemon_exit_detected",
                        "returncode": proc.returncode,
                        "restart_attempt": int(daemon_restart_count + 1),
                    }
                )
                if daemon_restart_count >= int(max_daemon_restarts):
                    hard_daemon_failure = True
                    injections.append(
                        {
                            "timestamp": datetime.now().isoformat(),
                            "event": "daemon_exited_early",
                            "returncode": proc.returncode,
                            "restart_budget_exhausted": True,
                            "max_daemon_restarts": int(max_daemon_restarts),
                        }
                    )
                    break
                time.sleep(max(0.0, float(daemon_restart_cooldown_seconds)))
                proc = _start_daemon(config=effective_config, profile=profile)
                daemon_restart_count += 1
                injections.append(
                    {
                        "timestamp": datetime.now().isoformat(),
                        "event": "daemon_restarted",
                        "daemon_pid": int(proc.pid),
                        "daemon_restart_count": int(daemon_restart_count),
                    }
                )
                continue

            elapsed = int((datetime.now() - start_time).total_seconds())
            runtime_snapshot = _read_json(RUNTIME_PATH)
            if isinstance(runtime_snapshot, dict):
                if bool(runtime_snapshot.get("block_new_risk", False)):
                    observed["block_new_risk_seen"] = True
                if str(runtime_snapshot.get("current_mode", "normal_operation")) != "normal_operation":
                    observed["non_normal_mode_seen"] = True
            while pending and elapsed >= pending[0][0]:
                _, action = pending.pop(0)
                if action == "wal":
                    _inject_wal_interruption(injections)
                elif action == "runtime":
                    _inject_runtime_corruption(injections)
                elif action == "heartbeat":
                    _inject_stale_heartbeat(injections)
                elif action == "mode":
                    _inject_mode_transition(
                        injections,
                        config_base_capital=configured_base_capital,
                        portfolio_risk_cap_pct=configured_risk_cap_pct,
                    )
                elif action == "freeze":
                    _trigger_freeze_research_check(injections)
                elif action == "drawdown":
                    _inject_drawdown(
                        injections,
                        config_base_capital=configured_base_capital,
                        portfolio_risk_cap_pct=configured_risk_cap_pct,
                    )
            time.sleep(10 if quick else 20)
    finally:
        _stop_daemon(proc)
        for evt in injections:
            if not isinstance(evt, dict):
                continue
            if evt.get("injection") != "stale_heartbeat":
                continue
            if not bool(evt.get("live_pid_sigstop", False)):
                continue
            pid = int(evt.get("live_pid", 0) or 0)
            if pid <= 0:
                continue
            try:
                os.kill(pid, signal.SIGCONT)
            except Exception:
                pass
            try:
                os.kill(pid, signal.SIGTERM)
            except Exception:
                pass
        # Ensure test harness leaves runtime in valid state.
        integrity = StateRecoveryManager(LIVE_DIR).check_state_integrity()
        if integrity.get("overall_status") == "corrupted":
            StateRecoveryManager(LIVE_DIR).rebuild_from_ledger(recovery_mode=False)
        runtime = _ensure_runtime_for_injection(
            config_base_capital=configured_base_capital,
            portfolio_risk_cap_pct=configured_risk_cap_pct,
        )
        if runtime:
            runtime["recovery_mode"] = False
            runtime["current_mode"] = "normal_operation"
            runtime["mode_constraints"] = {}
            runtime["block_new_risk"] = False
            runtime["convexity_breach"] = False
            runtime["gap_shock_detected"] = False
            runtime["survival_mode_activations_recent"] = 0
            runtime["high_drift_duration_minutes"] = 0
            alpha = runtime.get("alpha_os", {})
            if isinstance(alpha, dict):
                alpha["fallback_tier"] = 0
                runtime["alpha_os"] = alpha
            _write_json_atomic(RUNTIME_PATH, runtime)
            write_runtime_signature(RUNTIME_PATH)
        if quick and effective_config != config and effective_config.exists():
            effective_config.unlink(missing_ok=True)

    validations = _collect_validations(proc, started_at=start_time)
    validations["daemon_restart_count"] = int(daemon_restart_count)
    validations["daemon_exit_events"] = int(daemon_exit_events)
    validations["daemon_restart_budget"] = int(max_daemon_restarts)
    validations["hard_daemon_failure"] = bool(hard_daemon_failure)
    report = {
        "timestamp": datetime.now().isoformat(),
        "started_at": start_time.isoformat(),
        "ended_at": datetime.now().isoformat(),
        "duration_hours": duration_hours,
        "system_profile": profile,
        "quick_mode": bool(quick),
        "injections": injections,
        "observed": observed,
        "validations": validations,
        "daemon_log": str(LOG_PATH),
        "effective_config": str(effective_config),
    }
    report["validations"]["constraints_propagated"] = bool(observed["block_new_risk_seen"])
    report["validations"]["mode_transition_observed_in_runtime"] = bool(observed["non_normal_mode_seen"])
    report["validations"]["daemon_exited_early"] = any(
        isinstance(evt, dict) and evt.get("event") == "daemon_exited_early"
        for evt in injections
    )
    _write_json_atomic(DRY_RUN_REPORT_PATH, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Northstar resilience dry-run with fault injections")
    parser.add_argument("--duration-hours", type=float, default=72.0)
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "config/northstar_daemon.yaml")
    parser.add_argument("--system-profile", choices=["minimal", "full"], default="minimal")
    parser.add_argument("--quick", action="store_true", help="Run accelerated injection schedule for validation")
    parser.add_argument("--max-daemon-restarts", type=int, default=8)
    parser.add_argument("--daemon-restart-cooldown-seconds", type=float, default=10.0)
    args = parser.parse_args()

    report = run_dry_run(
        duration_hours=float(args.duration_hours),
        config=args.config,
        profile=args.system_profile,
        quick=bool(args.quick),
        max_daemon_restarts=int(args.max_daemon_restarts),
        daemon_restart_cooldown_seconds=float(args.daemon_restart_cooldown_seconds),
    )
    print(json.dumps(report, indent=2))

    validations = report.get("validations", {})
    hard_fail = [
        not bool(validations.get("no_orphan_locks", False)),
        validations.get("runtime_integrity_status") == "corrupted",
        not bool(validations.get("constraints_propagated", False)),
        not bool(validations.get("mode_transition_observed_in_runtime", False)),
        bool(validations.get("daemon_exited_early", False)),
        not bool(validations.get("runtime_ledger_open_count_match", False)),
        not bool(validations.get("runtime_ledger_open_id_match", False)),
    ]
    return 1 if any(hard_fail) else 0


if __name__ == "__main__":
    raise SystemExit(main())
