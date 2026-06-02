#!/usr/bin/env python3
"""Compatibility launcher for the canonical integrated options engine."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_ENGINE = PROJECT_ROOT / "scripts" / "run_integrated_options_paper_engine.py"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Launch the canonical Northstar V3 options engine in continuous mode."
    )
    parser.add_argument("--interval-minutes", type=float, default=1.0)
    parser.add_argument(
        "--underlyings",
        type=str,
        default="NIFTY,BANKNIFTY,FINNIFTY,RELIANCE,TCS,HDFCBANK,INFY,ICICIBANK,SBIN",
    )
    parser.add_argument("--aggressive", action="store_true")
    parser.add_argument("--no-aggressive", action="store_true")
    parser.add_argument("--max-trades-per-week", type=int, default=None)
    parser.add_argument("--portfolio-risk-cap-pct", type=float, default=None)
    parser.add_argument("--no-max-trades-limit", action="store_true")
    parser.add_argument("--disable-portfolio-overlay", action="store_true")
    parser.add_argument("--portfolio-overlay-max-stocks", type=int, default=6)
    parser.add_argument("--start-fresh-today", action="store_true")
    parser.add_argument("--recovery-mode", action="store_true")
    return parser.parse_args()


def build_command(args: argparse.Namespace) -> list[str]:
    cmd = [
        sys.executable,
        str(CANONICAL_ENGINE),
        "--mode",
        "continuous",
        "--interval-minutes",
        str(args.interval_minutes),
        "--underlyings",
        args.underlyings,
        "--market-hours-only",
        "--portfolio-overlay-max-stocks",
        str(args.portfolio_overlay_max_stocks),
    ]
    if args.aggressive:
        cmd.append("--aggressive")
    if args.no_aggressive:
        cmd.append("--no-aggressive")
    if args.max_trades_per_week is not None:
        cmd.extend(["--max-trades-per-week", str(args.max_trades_per_week)])
    if args.portfolio_risk_cap_pct is not None:
        cmd.extend(["--portfolio-risk-cap-pct", str(args.portfolio_risk_cap_pct)])
    if args.no_max_trades_limit:
        cmd.append("--no-max-trades-limit")
    if args.disable_portfolio_overlay:
        cmd.append("--disable-portfolio-overlay")
    if args.start_fresh_today:
        cmd.append("--start-fresh-today")
    if args.recovery_mode:
        cmd.append("--recovery-mode")
    return cmd


def main() -> int:
    if not CANONICAL_ENGINE.exists():
        raise FileNotFoundError(f"Canonical options engine missing: {CANONICAL_ENGINE}")
    args = parse_args()
    os.execv(sys.executable, build_command(args))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
