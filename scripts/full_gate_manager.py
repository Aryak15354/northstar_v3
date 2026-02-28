#!/usr/bin/env python3
"""Launch and monitor full gate dry-runs locally with caffeinate + PID tracking."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import psutil

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LIVE_DIR = PROJECT_ROOT / "data/options/live"
LOG_DIR = PROJECT_ROOT / "logs"
DEFAULT_PID_PATH = LIVE_DIR / "full_gate_runner.pid"
DEFAULT_STATUS_PATH = LIVE_DIR / "full_gate_runner_status.json"
DEFAULT_REPORT_PATH = LIVE_DIR / "chaos_dry_run_report.json"
DEFAULT_DAEMON_STATUS_PATH = LIVE_DIR / "northstar_daemon_status.json"
DEFAULT_LOG_PATH = LOG_DIR / "full_gate_72h.log"
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config/northstar_daemon.yaml"


def _now_iso() -> str:
    return datetime.now().isoformat()


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, default=str)
        handle.flush()
        os.fsync(handle.fileno())
    tmp.replace(path)


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        if path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                return payload
    except Exception:
        pass
    return {}


def _tail(path: Path, max_lines: int = 20) -> List[str]:
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        return lines[-max_lines:]
    except Exception:
        return []


def _rotate_existing_report(report_path: Path) -> Optional[Path]:
    if not report_path.exists():
        return None
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    rotated = report_path.with_name(f"{report_path.stem}.prev_{ts}{report_path.suffix}")
    try:
        report_path.replace(rotated)
        return rotated
    except Exception:
        return None


def _rotate_existing_log(log_path: Path) -> Optional[Path]:
    if not log_path.exists():
        return None
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    rotated = log_path.with_name(f"{log_path.stem}.prev_{ts}{log_path.suffix}")
    try:
        log_path.replace(rotated)
        return rotated
    except Exception:
        return None


def _read_pid(pid_path: Path) -> Optional[int]:
    if not pid_path.exists():
        return None
    try:
        raw = pid_path.read_text(encoding="utf-8").strip()
        pid = int(raw)
        return pid if pid > 0 else None
    except Exception:
        return None


def _is_pid_running(pid: Optional[int]) -> bool:
    if not pid or pid <= 0:
        return False
    try:
        proc = psutil.Process(pid)
        if not bool(proc.is_running()):
            return False
        status = proc.status()
        if status == psutil.STATUS_ZOMBIE:
            return False
        return True
    except psutil.NoSuchProcess:
        return False
    except psutil.AccessDenied:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False
    except Exception:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


def _evaluate_report(report: Dict[str, Any]) -> Tuple[Optional[bool], List[str]]:
    if not report:
        return None, ["report_missing"]
    vals = report.get("validations", {}) if isinstance(report.get("validations"), dict) else {}
    failures: List[str] = []
    if not bool(vals.get("no_orphan_locks", False)):
        failures.append("orphan_locks")
    if str(vals.get("runtime_integrity_status", "")).lower() == "corrupted":
        failures.append("runtime_corrupted")
    if not bool(vals.get("constraints_propagated", False)):
        failures.append("constraints_not_propagated")
    if not bool(vals.get("mode_transition_observed_in_runtime", False)):
        failures.append("mode_transition_not_observed")
    if bool(vals.get("daemon_exited_early", False)):
        failures.append("daemon_exited_early")
    return len(failures) == 0, failures


def _augment_daemon_status(daemon_status: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(daemon_status, dict) or not daemon_status:
        return {}
    out = dict(daemon_status)
    daemon_pid = out.get("daemon_pid")
    daemon_alive = _is_pid_running(int(daemon_pid)) if str(daemon_pid).isdigit() else False
    out["daemon_pid_alive"] = bool(daemon_alive)

    processes = out.get("processes")
    if isinstance(processes, dict):
        proc_copy: Dict[str, Any] = {}
        for name, info in processes.items():
            if not isinstance(info, dict):
                proc_copy[name] = info
                continue
            i = dict(info)
            pid = i.get("pid")
            i["pid_alive"] = _is_pid_running(int(pid)) if str(pid).isdigit() else False
            proc_copy[name] = i
        out["processes"] = proc_copy
    return out


def _parse_iso(value: Any) -> Optional[datetime]:
    try:
        if value is None:
            return None
        return datetime.fromisoformat(str(value))
    except Exception:
        return None


def _is_report_fresh(report: Dict[str, Any], launcher_status: Dict[str, Any]) -> bool:
    if not report:
        return False
    if not launcher_status:
        return False
    launcher_started = _parse_iso(launcher_status.get("started_at"))
    if launcher_started is None:
        return False
    report_started = _parse_iso(report.get("started_at"))
    if report_started is None:
        return False
    return report_started >= launcher_started


def _runtime_snapshot(
    pid_path: Path,
    status_path: Path,
    report_path: Path,
    daemon_status_path: Path,
    log_path: Path,
) -> Dict[str, Any]:
    pid = _read_pid(pid_path)
    running = _is_pid_running(pid)
    launcher_status = _read_json(status_path)
    report = _read_json(report_path)
    daemon_status = _read_json(daemon_status_path)
    report_pass, report_failures = _evaluate_report(report)

    proc_stats: Dict[str, Any] = {}
    if running and pid:
        try:
            proc = psutil.Process(pid)
            proc_stats = {
                "name": proc.name(),
                "status": proc.status(),
                "create_time": datetime.fromtimestamp(proc.create_time()).isoformat(),
                "cpu_percent": float(proc.cpu_percent(interval=0.0)),
                "memory_mb": float(proc.memory_info().rss / (1024 ** 2)),
            }
        except Exception:
            proc_stats = {}

    started_at = launcher_status.get("started_at")
    elapsed_seconds = None
    if started_at:
        try:
            elapsed_seconds = max(
                0.0,
                (datetime.now() - datetime.fromisoformat(str(started_at))).total_seconds(),
            )
        except Exception:
            elapsed_seconds = None

    duration_hours = float(launcher_status.get("duration_hours", 0.0) or 0.0)
    target_seconds = duration_hours * 3600.0 if duration_hours > 0 else None
    progress = None
    if elapsed_seconds is not None and target_seconds:
        progress = min(1.0, elapsed_seconds / target_seconds)

    # During long-running gate execution the report is expected only at completion.
    if running and not report:
        report_failures = ["report_pending"]

    daemon_status = _augment_daemon_status(daemon_status)

    return {
        "timestamp": _now_iso(),
        "runner_pid": pid,
        "runner_running": running,
        "runner_stats": proc_stats,
        "launcher_status": launcher_status,
        "elapsed_seconds": elapsed_seconds,
        "target_duration_seconds": target_seconds,
        "progress_ratio": progress,
        "chaos_report_exists": bool(report),
        "chaos_report": report,
        "chaos_report_fresh": _is_report_fresh(report, launcher_status),
        "chaos_report_pass": report_pass,
        "chaos_report_failures": report_failures,
        "daemon_status": daemon_status,
        "log_path": str(log_path),
        "log_tail": _tail(log_path, max_lines=20),
    }


def _terminate_process_tree(pid: int, timeout_seconds: float) -> bool:
    try:
        parent = psutil.Process(pid)
    except Exception:
        return not _is_pid_running(pid)

    procs = parent.children(recursive=True)
    for p in procs:
        try:
            p.terminate()
        except Exception:
            pass
    try:
        parent.terminate()
    except Exception:
        pass

    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if not _is_pid_running(pid):
            return True
        time.sleep(0.25)

    for p in procs:
        try:
            p.kill()
        except Exception:
            pass
    try:
        parent.kill()
    except Exception:
        pass
    return not _is_pid_running(pid)


def launch(args: argparse.Namespace) -> int:
    existing_pid = _read_pid(args.pid_path)
    if _is_pid_running(existing_pid):
        print(
            json.dumps(
                {
                    "status": "already_running",
                    "runner_pid": existing_pid,
                    "pid_path": str(args.pid_path),
                },
                indent=2,
            )
        )
        return 2

    args.pid_path.parent.mkdir(parents=True, exist_ok=True)
    args.log_path.parent.mkdir(parents=True, exist_ok=True)
    rotated_report = _rotate_existing_report(args.report_path)
    rotated_log = None
    if not bool(getattr(args, "append_log", False)):
        rotated_log = _rotate_existing_log(args.log_path)

    cmd: List[str] = [
        sys.executable,
        str(PROJECT_ROOT / "scripts/run_chaos_dry_run.py"),
        "--duration-hours",
        str(float(args.duration_hours)),
        "--config",
        str(args.config),
        "--system-profile",
        str(args.system_profile),
    ]
    if args.quick:
        cmd.append("--quick")
    if args.extra_args:
        extras = list(args.extra_args)
        if extras and extras[0] == "--":
            extras = extras[1:]
        cmd.extend(extras)

    wrapped_cmd = cmd
    caffeinate_used = False
    if args.use_caffeinate and shutil.which("caffeinate"):
        wrapped_cmd = ["caffeinate", "-i"] + cmd
        caffeinate_used = True

    with open(args.log_path, "ab") as log_handle:
        proc = subprocess.Popen(
            wrapped_cmd,
            cwd=str(PROJECT_ROOT),
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            text=False,
        )

    # Short liveness check so "launch" fails fast on immediate startup errors.
    time.sleep(float(args.startup_grace_seconds))
    running = _is_pid_running(proc.pid)
    payload = {
        "timestamp": _now_iso(),
        "status": "running" if running else "failed_to_start",
        "runner_pid": int(proc.pid),
        "started_at": _now_iso(),
        "duration_hours": float(args.duration_hours),
        "system_profile": str(args.system_profile),
        "config_path": str(args.config),
        "quick_mode": bool(args.quick),
        "use_caffeinate": bool(caffeinate_used),
        "command": wrapped_cmd,
        "log_path": str(args.log_path),
        "report_path": str(args.report_path),
        "rotated_previous_report": str(rotated_report) if rotated_report else None,
        "rotated_previous_log": str(rotated_log) if rotated_log else None,
    }
    _write_json(args.status_path, payload)
    args.pid_path.write_text(str(proc.pid), encoding="utf-8")

    out = _runtime_snapshot(
        pid_path=args.pid_path,
        status_path=args.status_path,
        report_path=args.report_path,
        daemon_status_path=args.daemon_status_path,
        log_path=args.log_path,
    )
    print(json.dumps(out, indent=2, default=str))
    return 0 if running else 1


def status(args: argparse.Namespace) -> int:
    out = _runtime_snapshot(
        pid_path=args.pid_path,
        status_path=args.status_path,
        report_path=args.report_path,
        daemon_status_path=args.daemon_status_path,
        log_path=args.log_path,
    )
    print(json.dumps(out, indent=2, default=str))
    if out.get("runner_running"):
        return 0
    report_pass = out.get("chaos_report_pass")
    if report_pass is False:
        return 1
    return 0


def stop(args: argparse.Namespace) -> int:
    pid = _read_pid(args.pid_path)
    if not _is_pid_running(pid):
        payload = _read_json(args.status_path)
        payload["stopped_at"] = _now_iso()
        payload["status"] = "not_running"
        _write_json(args.status_path, payload)
        print(json.dumps({"status": "not_running", "runner_pid": pid}, indent=2))
        args.pid_path.unlink(missing_ok=True)
        return 0

    assert pid is not None
    timeout = float(args.stop_timeout_seconds)
    killed = False
    try:
        os.killpg(pid, signal.SIGTERM)
        deadline = time.time() + timeout
        while time.time() < deadline:
            if not _is_pid_running(pid):
                killed = True
                break
            time.sleep(0.5)
        if not killed and _is_pid_running(pid):
            os.killpg(pid, signal.SIGKILL)
            time.sleep(0.5)
            killed = not _is_pid_running(pid)
    except Exception:
        killed = _terminate_process_tree(pid, timeout_seconds=timeout)
        if not killed and _is_pid_running(pid):
            try:
                os.kill(pid, signal.SIGKILL)
            except Exception:
                pass

    final_running = _is_pid_running(pid)
    if not final_running:
        args.pid_path.unlink(missing_ok=True)

    payload = _read_json(args.status_path)
    payload["stopped_at"] = _now_iso()
    payload["status"] = "stopped" if not final_running else "stop_failed"
    _write_json(args.status_path, payload)

    print(
        json.dumps(
            {
                "status": payload["status"],
                "runner_pid": pid,
            },
            indent=2,
        )
    )
    return 0 if not final_running else 1


def monitor(args: argparse.Namespace) -> int:
    start = time.time()
    timeout = float(args.max_wait_minutes) * 60.0 if args.max_wait_minutes > 0 else None
    report_grace = max(0.0, float(getattr(args, "report_grace_seconds", 120.0)))
    last_running = None
    iterations = 0
    report_wait_started: Optional[float] = None
    while True:
        iterations += 1
        snapshot = _runtime_snapshot(
            pid_path=args.pid_path,
            status_path=args.status_path,
            report_path=args.report_path,
            daemon_status_path=args.daemon_status_path,
            log_path=args.log_path,
        )
        running = bool(snapshot.get("runner_running", False))
        launcher_status = snapshot.get("launcher_status", {})
        report_fresh = bool(snapshot.get("chaos_report_fresh", False))
        elapsed = int(time.time() - start)
        report_pass = snapshot.get("chaos_report_pass")
        report_failures = snapshot.get("chaos_report_failures", [])
        print(
            json.dumps(
                {
                    "timestamp": snapshot.get("timestamp"),
                    "running": running,
                    "pid": snapshot.get("runner_pid"),
                    "elapsed_seconds": elapsed,
                    "progress_ratio": snapshot.get("progress_ratio"),
                    "report_fresh": report_fresh,
                    "report_pass": report_pass,
                    "report_failures": report_failures,
                },
                indent=2,
            )
        )

        if not running and not launcher_status:
            return 3
        if last_running is True and not running:
            # Process just exited. Evaluate report and return.
            if report_fresh and report_pass is not None:
                return 0 if report_pass is not False else 1
            return 4
        if not running and report_fresh and report_pass is not None:
            return 0 if report_pass else 1
        if not running and launcher_status and iterations >= 2 and not report_fresh:
            if report_wait_started is None:
                report_wait_started = time.time()
            elif (time.time() - report_wait_started) >= report_grace:
                return 4
        else:
            report_wait_started = None

        if timeout is not None and (time.time() - start) > timeout:
            return 2

        last_running = running
        time.sleep(float(args.poll_seconds))


def run_launch_and_monitor(args: argparse.Namespace) -> int:
    rc = launch(args)
    if rc != 0:
        return rc
    mon_args = argparse.Namespace(
        pid_path=args.pid_path,
        status_path=args.status_path,
        report_path=args.report_path,
        daemon_status_path=args.daemon_status_path,
        log_path=args.log_path,
        poll_seconds=args.poll_seconds,
        max_wait_minutes=args.max_wait_minutes,
        report_grace_seconds=args.report_grace_seconds,
    )
    return monitor(mon_args)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Launch + monitor Northstar full gate dry-run")
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--pid-path", type=Path, default=DEFAULT_PID_PATH)
        p.add_argument("--status-path", type=Path, default=DEFAULT_STATUS_PATH)
        p.add_argument("--report-path", type=Path, default=DEFAULT_REPORT_PATH)
        p.add_argument("--daemon-status-path", type=Path, default=DEFAULT_DAEMON_STATUS_PATH)
        p.add_argument("--log-path", type=Path, default=DEFAULT_LOG_PATH)

    launch_p = sub.add_parser("launch", help="Launch detached full gate runner")
    common(launch_p)
    launch_p.add_argument("--duration-hours", type=float, default=72.0)
    launch_p.add_argument("--system-profile", choices=["minimal", "full"], default="minimal")
    launch_p.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    launch_p.add_argument("--quick", action="store_true")
    launch_p.add_argument("--no-caffeinate", action="store_true", help="Disable caffeinate wrapper")
    launch_p.add_argument("--append-log", action="store_true", help="Append to existing log instead of rotating it")
    launch_p.add_argument("--startup-grace-seconds", type=float, default=2.0)
    launch_p.add_argument("extra_args", nargs=argparse.REMAINDER)

    status_p = sub.add_parser("status", help="Print current gate runner status")
    common(status_p)

    monitor_p = sub.add_parser("monitor", help="Poll runner + report until completion")
    common(monitor_p)
    monitor_p.add_argument("--poll-seconds", type=float, default=30.0)
    monitor_p.add_argument("--max-wait-minutes", type=float, default=0.0, help="0 disables timeout")
    monitor_p.add_argument("--report-grace-seconds", type=float, default=120.0)

    run_p = sub.add_parser("run", help="Launch then monitor until completion")
    common(run_p)
    run_p.add_argument("--duration-hours", type=float, default=72.0)
    run_p.add_argument("--system-profile", choices=["minimal", "full"], default="minimal")
    run_p.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    run_p.add_argument("--quick", action="store_true")
    run_p.add_argument("--no-caffeinate", action="store_true")
    run_p.add_argument("--append-log", action="store_true")
    run_p.add_argument("--startup-grace-seconds", type=float, default=2.0)
    run_p.add_argument("--poll-seconds", type=float, default=30.0)
    run_p.add_argument("--max-wait-minutes", type=float, default=0.0)
    run_p.add_argument("--report-grace-seconds", type=float, default=120.0)
    run_p.add_argument("extra_args", nargs=argparse.REMAINDER)

    stop_p = sub.add_parser("stop", help="Stop running gate process")
    common(stop_p)
    stop_p.add_argument("--stop-timeout-seconds", type=float, default=8.0)

    return parser


def main() -> int:
    args = build_parser().parse_args()
    if hasattr(args, "no_caffeinate"):
        args.use_caffeinate = not bool(args.no_caffeinate)

    cmd = args.command
    if cmd == "launch":
        return launch(args)
    if cmd == "status":
        return status(args)
    if cmd == "monitor":
        return monitor(args)
    if cmd == "run":
        return run_launch_and_monitor(args)
    if cmd == "stop":
        return stop(args)
    raise ValueError(f"Unknown command: {cmd}")


if __name__ == "__main__":
    raise SystemExit(main())
