#!/usr/bin/env python3
"""Run ADE computation cycle and emit diagnostics artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.diagnostics.alpha_diagnostics_engine import AlphaDiagnosticsEngine, DiagnosticsPaths


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Northstar Alpha Diagnostics Engine")
    parser.add_argument("--runtime-db", default="data/runtime/portfolio_runtime.db")
    parser.add_argument("--diagnostics-db", default="data/diagnostics/alpha_diagnostics.db")
    parser.add_argument("--alpha-metrics", default="data/diagnostics/alpha_metrics.parquet")
    parser.add_argument("--strategy-metrics", default="data/diagnostics/strategy_metrics.parquet")
    parser.add_argument("--policy-json", default="data/diagnostics/policy_recommendations.json")
    args = parser.parse_args()

    engine = AlphaDiagnosticsEngine(
        DiagnosticsPaths(
            runtime_db=args.runtime_db,
            diagnostics_db=args.diagnostics_db,
            alpha_metrics_parquet=args.alpha_metrics,
            strategy_metrics_parquet=args.strategy_metrics,
            policy_recommendations_json=args.policy_json,
        )
    )
    try:
        trades = engine.compute_trade_diagnostics()
        strategies = engine.compute_strategy_diagnostics()
        portfolio = engine.compute_portfolio_diagnostics()
        print(
            json.dumps(
                {
                    "status": "ok",
                    "trade_rows": int(len(trades)),
                    "strategy_rows": int(len(strategies)),
                    "portfolio_rows": int(len(portfolio)),
                    "runtime_db": args.runtime_db,
                    "diagnostics_db": args.diagnostics_db,
                },
                indent=2,
            )
        )
        return 0
    finally:
        engine.close()


if __name__ == "__main__":
    raise SystemExit(main())
