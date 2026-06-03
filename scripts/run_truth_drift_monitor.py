#!/usr/bin/env python3
"""Launch continuous truth-drift monitoring for PRS."""

from __future__ import annotations

import argparse

from src.runtime import PortfolioRuntimeService
from src.runtime.truth_drift_service import TruthDriftService


def main() -> int:
    parser = argparse.ArgumentParser(description="Run PRS truth-drift monitor")
    parser.add_argument("--db", default="data/runtime/portfolio_runtime.db")
    parser.add_argument("--materialized", default="data/processed/runtime")
    parser.add_argument("--shadow-state", default="data/processed/shadow_state_current.json")
    parser.add_argument("--interval", type=float, default=30.0)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()

    prs = PortfolioRuntimeService(
        db_path=args.db,
        materialized_output_dir=args.materialized,
    )
    svc = TruthDriftService(
        prs,
        shadow_state_path=args.shadow_state,
        poll_interval_seconds=args.interval,
    )
    if args.once:
        svc.run_once()
        return 0
    svc.run_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
