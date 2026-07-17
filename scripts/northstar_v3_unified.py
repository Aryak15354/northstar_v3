#!/usr/bin/env python3
"""Northstar V3 unified compatibility launcher.

This script preserves the historical CLI while delegating to the current
``src.orchestrator.master_orchestrator.MasterOrchestrator`` facade.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Northstar V3 unified operator launcher",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 scripts/northstar_v3_unified.py --mode update --quick
  python3 scripts/northstar_v3_unified.py --mode dashboard
  python3 scripts/northstar_v3_unified.py --mode backtest --strategy momentum
        """,
    )
    parser.add_argument("--mode", choices=["dashboard", "update", "live", "backtest", "status"], default="dashboard")
    parser.add_argument(
        "--dashboard",
        choices=["unified", "trading-desk", "professional", "intelligence", "react"],
        default="unified",
        help="Accepted for backwards compatibility; all dashboard modes route to the canonical app.",
    )
    parser.add_argument("--quick", action="store_true", help="Use quick mode for update workflows.")
    parser.add_argument("--strategy", type=str, help="Strategy name for backtesting.")
    parser.add_argument("--verbose", "-v", action="store_true")
    return parser.parse_args()


def print_startup_banner(args: argparse.Namespace) -> None:
    print("NORTHSTAR V3 UNIFIED LAUNCHER")
    print("=" * 70)
    print(f"Mode: {args.mode}")
    if args.mode == "dashboard":
        print(f"Dashboard: {args.dashboard}")
    if args.quick:
        print("Update Type: quick")
    if args.strategy:
        print(f"Strategy: {args.strategy}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)


def main() -> int:
    args = parse_args()
    print_startup_banner(args)

    from src.orchestrator.master_orchestrator import MasterOrchestrator

    orchestrator = MasterOrchestrator(verbose=args.verbose)
    if args.mode == "status":
        import json

        print(json.dumps(orchestrator.get_system_status(), indent=2))
        return 0
    if args.mode == "dashboard":
        return 0 if orchestrator.run_dashboard(args.dashboard) else 1
    if args.mode == "update":
        return 0 if orchestrator.run_system_update(quick=args.quick) else 1
    if args.mode == "live":
        return 0 if orchestrator.run_live_trading() else 1
    if args.mode == "backtest":
        return 0 if orchestrator.run_backtest(strategy=args.strategy) else 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
