#!/usr/bin/env python3
"""
🏃 Northstar V3 Daily Runner (Hands-Off)

This is the scheduler-friendly entrypoint used by `src/automation/northstar_scheduler.py`.
It runs the V3 pipeline in a predictable, non-interactive way and writes logs.

Defaults:
- daily: quick update (no long backtests)
- weekly: full run (trigger via --full)
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
CANONICAL_RUNNER = PROJECT_ROOT / "scripts" / "run_complete_v3_system.py"
DASHBOARD_LAUNCHER = PROJECT_ROOT / "launch_dashboard.py"


def _log_dir() -> Path:
    p = PROJECT_ROOT / "data" / "automation" / "logs"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _run(cmd: list[str]) -> int:
    # Stream output to console (scheduler will capture to file) and keep Python unbuffered.
    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")
    return subprocess.call(cmd, cwd=str(PROJECT_ROOT), env=env)


def main() -> int:
    parser = argparse.ArgumentParser(description="Northstar V3 daily runner")
    parser.add_argument("--full", action="store_true", help="Run full pipeline (slower)")
    parser.add_argument("--quick", action="store_true", help="Run quick pipeline (default)")
    parser.add_argument("--dashboard", action="store_true", help="Launch dashboard at the end (manual runs only)")
    parser.add_argument("--port", type=int, default=8517, help="Dashboard port (if --dashboard)")
    parser.add_argument(
        "--sentiment-cycles",
        type=int,
        default=1,
        help="Legacy compatibility flag retained for scheduler CLI stability.",
    )
    parser.add_argument(
        "--sentiment-interval-minutes",
        type=int,
        default=180,
        help="Legacy compatibility flag retained for scheduler CLI stability.",
    )
    parser.add_argument(
        "--block-sentiment-cycles",
        action="store_true",
        help="Legacy compatibility flag retained for scheduler CLI stability.",
    )
    args = parser.parse_args()

    quick = True
    if args.full:
        quick = False
    if args.quick:
        quick = True

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = _log_dir() / f"daily_run_{stamp}.log"

    cmd = [sys.executable, "-u", str(CANONICAL_RUNNER)]
    if quick:
        cmd.append("--quick")

    # For scheduler usage, redirect to logfile; keep a short header for forensics.
    with log_path.open("w") as f:
        f.write(f"Northstar V3 Daily Runner\n")
        f.write(f"timestamp: {datetime.now().isoformat(timespec='seconds')}\n")
        f.write(f"command: {' '.join(cmd)}\n")
        if not quick and (
            int(args.sentiment_cycles) != 1
            or int(args.sentiment_interval_minutes) != 180
            or bool(args.block_sentiment_cycles)
        ):
            f.write("compat_note: legacy sentiment-cycle flags are no longer forwarded to the canonical runner\n")
        f.write("-" * 80 + "\n")
        f.flush()
        rc = subprocess.call(cmd, cwd=str(PROJECT_ROOT), env={**os.environ, "PYTHONUNBUFFERED": "1"}, stdout=f, stderr=subprocess.STDOUT)

    print(f"🧾 Log: {log_path}")
    if rc == 0 and args.dashboard:
        rc = subprocess.call(
            [sys.executable, str(DASHBOARD_LAUNCHER), "--port", str(int(args.port))],
            cwd=str(PROJECT_ROOT),
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
    return int(rc)


if __name__ == "__main__":
    raise SystemExit(main())
