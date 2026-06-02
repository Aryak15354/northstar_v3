#!/usr/bin/env python3
"""
COMPATIBILITY WRAPPER - NOT THE PRIMARY IMPLEMENTATION.

This script exists only to preserve the legacy live-engine entrypoint.
The actual implementation lives in scripts/run_integrated_options_paper_engine.py.
Do not add business logic here.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_ENGINE = PROJECT_ROOT / "scripts" / "run_integrated_options_paper_engine.py"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Launch the canonical V3 live engine with dashboard/runtime state outputs."
    )
    parser.add_argument("--update-interval", type=int, default=30, help="Seconds between cycles.")
    parser.add_argument("--underlyings", type=str, default="NIFTY,BANKNIFTY,FINNIFTY")
    parser.add_argument("--aggressive", action="store_true")
    parser.add_argument("--no-aggressive", action="store_true")
    parser.add_argument("--start-fresh-today", action="store_true")
    parser.add_argument("--recovery-mode", action="store_true")
    return parser.parse_args()


def build_command(args: argparse.Namespace) -> list[str]:
    interval_minutes = max(float(args.update_interval) / 60.0, 10.0 / 60.0)
    cmd = [
        sys.executable,
        str(CANONICAL_ENGINE),
        "--mode",
        "continuous",
        "--interval-minutes",
        str(interval_minutes),
        "--underlyings",
        args.underlyings,
        "--market-hours-only",
    ]
    if args.aggressive:
        cmd.append("--aggressive")
    if args.no_aggressive:
        cmd.append("--no-aggressive")
    if args.start_fresh_today:
        cmd.append("--start-fresh-today")
    if args.recovery_mode:
        cmd.append("--recovery-mode")
    return cmd


def main() -> int:
    if not CANONICAL_ENGINE.exists():
        raise FileNotFoundError(f"Canonical options engine missing: {CANONICAL_ENGINE}")
    os.execv(sys.executable, build_command(parse_args()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
