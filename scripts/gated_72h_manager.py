#!/usr/bin/env python3
"""Enforce quick preflight pass before launching 72h gate soak."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LIVE_DIR = PROJECT_ROOT / "data/options/live"
BASELINE_PATH = LIVE_DIR / "gate_code_freeze_baseline.json"
REPORT_PATH = LIVE_DIR / "chaos_dry_run_report.json"

CODE_FREEZE_DIRS = [
    PROJECT_ROOT / "scripts",
    PROJECT_ROOT / "src/options",
    PROJECT_ROOT / "src/research",
    PROJECT_ROOT / "config",
]
CODE_FREEZE_SUFFIXES = {".py", ".yaml", ".yml", ".sh"}


def _run(cmd: List[str], check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(PROJECT_ROOT), text=True, capture_output=True, check=check)


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        if path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                return payload
    except Exception:
        return {}
    return {}


def _quick_report_passed() -> Dict[str, Any]:
    report = _read_json(REPORT_PATH)
    validations = report.get("validations", {}) if isinstance(report.get("validations"), dict) else {}
    failures: List[str] = []
    if not report:
        failures.append("report_missing")
    if not bool(validations.get("no_orphan_locks", False)):
        failures.append("orphan_locks")
    if str(validations.get("runtime_integrity_status", "")).lower() == "corrupted":
        failures.append("runtime_corrupted")
    if not bool(validations.get("constraints_propagated", False)):
        failures.append("constraints_not_propagated")
    if not bool(validations.get("mode_transition_observed_in_runtime", False)):
        failures.append("mode_transition_not_observed")
    if bool(validations.get("daemon_exited_early", False)):
        failures.append("daemon_exited_early")
    if not bool(validations.get("runtime_ledger_open_count_match", False)):
        failures.append("runtime_ledger_open_count_mismatch")
    if not bool(validations.get("runtime_ledger_open_id_match", False)):
        failures.append("runtime_ledger_open_id_mismatch")

    return {
        "report_exists": bool(report),
        "report_started_at": report.get("started_at"),
        "report_ended_at": report.get("ended_at"),
        "pass": len(failures) == 0,
        "failures": failures,
    }


def _hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


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
    h = hashlib.sha256()
    for rel, checksum in file_map.items():
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        h.update(checksum.encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()


def _write_baseline() -> Dict[str, Any]:
    file_map = _compute_code_map()
    payload = {
        "created_at": datetime.now().isoformat(),
        "fingerprint": _digest(file_map),
        "file_count": len(file_map),
        "files": file_map,
    }
    BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
    BASELINE_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Quick-gated 72h launcher")
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "config/northstar_daemon.yaml")
    parser.add_argument("--system-profile", choices=["minimal", "full"], default="minimal")
    parser.add_argument("--quick-duration-hours", type=float, default=0.20)
    parser.add_argument("--quick-max-wait-minutes", type=float, default=30.0)
    parser.add_argument("--duration-hours", type=float, default=72.0)
    parser.add_argument("--no-caffeinate", action="store_true")
    parser.add_argument("--max-daemon-restarts", type=int, default=25)
    parser.add_argument("--daemon-restart-cooldown-seconds", type=float, default=8.0)
    parser.add_argument("--skip-stop-existing", action="store_true")
    args = parser.parse_args()

    steps: List[Dict[str, Any]] = []

    if not args.skip_stop_existing:
        stop_cmd = [sys.executable, "scripts/full_gate_manager.py", "stop"]
        stop = _run(stop_cmd)
        steps.append({"step": "stop_existing", "returncode": stop.returncode, "stdout": stop.stdout.strip()})

    quick_cmd = [
        sys.executable,
        "scripts/full_gate_manager.py",
        "run",
        "--duration-hours",
        str(float(args.quick_duration_hours)),
        "--quick",
        "--system-profile",
        str(args.system_profile),
        "--config",
        str(args.config),
        "--max-wait-minutes",
        str(float(args.quick_max_wait_minutes)),
        "--poll-seconds",
        "20",
        "--report-grace-seconds",
        "180",
        "--",
        "--max-daemon-restarts",
        str(int(args.max_daemon_restarts)),
        "--daemon-restart-cooldown-seconds",
        str(float(args.daemon_restart_cooldown_seconds)),
    ]
    if args.no_caffeinate:
        quick_cmd.insert(3, "--no-caffeinate")
    quick = _run(quick_cmd)
    quick_report = _quick_report_passed()
    steps.append(
        {
            "step": "quick_preflight",
            "returncode": quick.returncode,
            "stdout_tail": quick.stdout.splitlines()[-40:],
            "stderr_tail": quick.stderr.splitlines()[-20:],
            "report_eval": quick_report,
        }
    )
    quick_passed = bool(quick_report.get("pass", False))
    if quick.returncode != 0 and not quick_passed:
        triage = _run([sys.executable, "scripts/gate_triage.py", "--strict"])
        steps.append(
            {
                "step": "triage_after_preflight_failure",
                "returncode": triage.returncode,
                "stdout": triage.stdout.strip(),
                "stderr": triage.stderr.strip(),
            }
        )
        print(json.dumps({"status": "preflight_failed", "steps": steps}, indent=2))
        return 1
    if quick.returncode != 0 and quick_passed:
        steps.append(
            {
                "step": "quick_preflight_override",
                "reason": "monitor_returncode_nonzero_but_report_passed",
            }
        )

    baseline = _write_baseline()
    steps.append(
        {
            "step": "code_freeze_baseline",
            "path": str(BASELINE_PATH),
            "fingerprint": baseline.get("fingerprint"),
            "file_count": baseline.get("file_count"),
        }
    )

    launch_cmd = [
        sys.executable,
        "scripts/full_gate_manager.py",
        "launch",
        "--duration-hours",
        str(float(args.duration_hours)),
        "--system-profile",
        str(args.system_profile),
        "--config",
        str(args.config),
        "--",
        "--max-daemon-restarts",
        str(int(args.max_daemon_restarts)),
        "--daemon-restart-cooldown-seconds",
        str(float(args.daemon_restart_cooldown_seconds)),
    ]
    if args.no_caffeinate:
        launch_cmd.insert(3, "--no-caffeinate")
    launch = _run(launch_cmd)
    steps.append(
        {
            "step": "launch_72h",
            "returncode": launch.returncode,
            "stdout_tail": launch.stdout.splitlines()[-60:],
            "stderr_tail": launch.stderr.splitlines()[-20:],
        }
    )
    if launch.returncode != 0:
        print(json.dumps({"status": "launch_failed", "steps": steps}, indent=2))
        return 1

    status = _run([sys.executable, "scripts/full_gate_manager.py", "status"])
    steps.append(
        {
            "step": "post_launch_status",
            "returncode": status.returncode,
            "stdout": status.stdout.strip(),
            "stderr": status.stderr.strip(),
        }
    )

    print(json.dumps({"status": "launched", "steps": steps}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
