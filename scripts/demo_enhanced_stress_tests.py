#!/usr/bin/env python3
"""
📉 STRESS TESTS (REAL DATA ONLY)

Replays historical crisis scenarios against *available* real data using:
- Portfolio PnL: data/portfolio/pnl_on_paper.parquet
- Benchmark:      data/processed/nifty.parquet

Important:
- No synthetic/mock performance data is generated.
- Scenarios outside the available data range are skipped (expected).

Outputs:
- data/processed/performance_summary.parquet (for reuse by other components)
- reports/validation/stress_test_report_<timestamp>.json
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import numpy as np
import pandas as pd

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.validation.stress_test_engine import StressTestEngine


def _build_performance_df() -> pd.DataFrame:
    pnl_path = Path("data/portfolio/pnl_on_paper.parquet")
    nifty_path = Path("data/processed/nifty.parquet")

    if not pnl_path.exists():
        return pd.DataFrame()
    pnl = pd.read_parquet(pnl_path)
    if pnl is None or pnl.empty or "Date" not in pnl.columns:
        return pd.DataFrame()

    pnl = pnl.copy()
    pnl["date"] = pd.to_datetime(pnl["Date"], errors="coerce")
    pnl = pnl.dropna(subset=["date"]).sort_values("date").set_index("date")

    # Portfolio returns
    if "Return" in pnl.columns and pd.to_numeric(pnl["Return"], errors="coerce").notna().any():
        ns_ret = pd.to_numeric(pnl["Return"], errors="coerce")
    else:
        if "Equity" not in pnl.columns:
            return pd.DataFrame()
        eq = pd.to_numeric(pnl["Equity"], errors="coerce")
        ns_ret = eq.pct_change()
    ns_ret = ns_ret.dropna().astype(float)

    # Benchmark returns
    if not nifty_path.exists():
        return pd.DataFrame()
    nifty = pd.read_parquet(nifty_path)
    if nifty is None or nifty.empty or "close" not in nifty.columns:
        return pd.DataFrame()
    close = pd.to_numeric(nifty["close"], errors="coerce").dropna()
    close.index = pd.to_datetime(close.index)
    close = close.sort_index()
    nifty_ret = close.pct_change().reindex(ns_ret.index).dropna().astype(float)

    aligned = pd.concat([ns_ret.rename("northstar_return"), nifty_ret.rename("nifty_return")], axis=1, join="inner").dropna()
    if aligned.empty:
        return pd.DataFrame()

    out = aligned.reset_index().rename(columns={"index": "date"})
    # Optional fields used by some reporting (keep simple, real-data-only)
    out["northstar_exposure"] = np.nan
    out["active_share"] = np.nan
    out["turnover"] = np.nan
    out["volatility"] = aligned["northstar_return"].rolling(20).std() * np.sqrt(252)
    return out


def main() -> int:
    print("📉 STRESS TESTS (REAL DATA ONLY)")
    print("=" * 70)

    perf = _build_performance_df()
    if perf.empty:
        print("❌ Could not build performance dataset from real artifacts.")
        print("   Required: data/portfolio/pnl_on_paper.parquet and data/processed/nifty.parquet")
        return 1

    # Persist for other components to reuse
    Path("data/processed").mkdir(parents=True, exist_ok=True)
    perf.to_parquet("data/processed/performance_summary.parquet", index=False)

    engine = StressTestEngine()
    results = engine.run_all_stress_tests(performance_df=perf)
    engine.log_stress_test_results(results)
    summary = engine.generate_stress_test_summary(results)

    report: Dict[str, Any] = {
        "report_date": datetime.now().date().isoformat(),
        "generated_at": datetime.now().isoformat(),
        "status": "AVAILABLE",
        "data_range": {
            "start": str(pd.to_datetime(perf["date"]).min().date()),
            "end": str(pd.to_datetime(perf["date"]).max().date()),
            "rows": int(len(perf)),
        },
        "test_summary": summary,
        "scenarios_tested": [r.scenario for r in results],
    }

    out_dir = Path("reports/validation")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"stress_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out_path.write_text(json.dumps(report, indent=2, default=str))

    print(f"\n✅ Wrote stress test report: {out_path}")
    print(f"   Scenarios tested: {len(results)}")
    if summary:
        print(f"   Success rate: {summary.get('success_rate', 0):.1%}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

