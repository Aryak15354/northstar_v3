#!/usr/bin/env python3
"""
🕒 NORTHSTAR V3 DAILY SCHEDULER
Run the full V3 pipeline at a fixed local time every day.

Example:
  python3 scripts/northstar_daily_scheduler.py --hour 18 --minute 30
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_RUNNER = PROJECT_ROOT / "scripts" / "run_complete_v3_system.py"
DASHBOARD_LAUNCHER = PROJECT_ROOT / "launch_dashboard.py"


def next_run_time(hour: int, minute: int) -> datetime:
    now = datetime.now()
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target = target + timedelta(days=1)
    return target


def run_pipeline(quick: bool, launch_dashboard: bool, skip_options_cycle: bool) -> int:
    cmd = [sys.executable, str(CANONICAL_RUNNER)]
    if quick:
        cmd.append("--quick")
    if skip_options_cycle:
        print("Compatibility note: --with-options-cycle no longer affects the canonical daily runner.")
    rc = subprocess.call(cmd, cwd=str(PROJECT_ROOT))
    if rc == 0 and launch_dashboard:
        rc = subprocess.call(
            [sys.executable, str(DASHBOARD_LAUNCHER), "--port", "8517"],
            cwd=str(PROJECT_ROOT),
        )
    return rc


def main() -> None:
    parser = argparse.ArgumentParser(description="Northstar V3 daily scheduler")
    parser.add_argument("--hour", type=int, default=18, help="Hour to run (local time)")
    parser.add_argument("--minute", type=int, default=0, help="Minute to run (local time)")
    parser.add_argument("--quick", action="store_true", help="Run quick update")
    parser.add_argument("--dashboard", action="store_true", help="Launch dashboard after each scheduled run")
    parser.add_argument("--with-options-cycle", action="store_true", help="Run integrated options single-cycle in scheduled runs")
    args = parser.parse_args()

    print("🕒 Northstar V3 Daily Scheduler")
    print(f"Target time: {args.hour:02d}:{args.minute:02d} local")

    while True:
        target = next_run_time(args.hour, args.minute)
        wait_seconds = (target - datetime.now()).total_seconds()
        print(f"Next run at: {target.isoformat()} (in {wait_seconds/3600:.2f} hours)")
        time.sleep(max(1, wait_seconds))
        print("\n🚀 Running scheduled pipeline...")
        rc = run_pipeline(
            args.quick,
            launch_dashboard=bool(args.dashboard),
            skip_options_cycle=not bool(args.with_options_cycle),
        )
        print(f"✅ Run complete (exit code {rc})")


if __name__ == "__main__":
    main()
