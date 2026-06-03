#!/usr/bin/env python3
"""Run the current Northstar system entrypoints using existing local artifacts.

This runner is intentionally thin: it delegates to `run.py` so command behavior
stays consistent with the canonical runtime contract.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _run(cmd: list[str]) -> bool:
    print(f"[run_system_with_current_data] {' '.join(cmd)}")
    proc = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
    return proc.returncode == 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Northstar with current local data")
    parser.add_argument("--quick", action="store_true", help="Quick update mode")
    parser.add_argument("--dashboard", action="store_true", help="Launch dashboard mode")
    parser.add_argument("--health-only", action="store_true", help="Run only health checks")
    parser.add_argument("--no-dashboard", action="store_true", help="Skip dashboard launch after update")
    parser.add_argument("--dashboard-profile", default="brain", choices=["brain", "unified"], help="Dashboard profile")
    args = parser.parse_args()

    if args.health_only:
        return 0 if _run([sys.executable, "run.py", "--mode", "health"]) else 1

    if args.dashboard:
        return 0 if _run(
            [sys.executable, "run.py", "--mode", "dashboard", "--dashboard", args.dashboard_profile]
        ) else 1

    update_cmd = [sys.executable, "run.py", "--mode", "update"]
    if args.quick:
        update_cmd.append("--quick")

    ok = _run(update_cmd)
    if not ok:
        return 1

    if not args.no_dashboard:
        ok = _run([sys.executable, "run.py", "--mode", "dashboard", "--dashboard", args.dashboard_profile])

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
