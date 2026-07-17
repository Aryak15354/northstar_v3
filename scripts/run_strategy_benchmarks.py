#!/usr/bin/env python3
"""
run_strategy_benchmarks.py — race V3 against the famous strategies on a level field.

Runs V3's live target and each canonical benchmark (Buffett, Magic Formula,
Piotroski, Graham) through the SAME ₹100cr PaperPortfolioEngine (identical
costs, taxes, caps, ADV limits), then aligns them with NIFTY-50. This is the
harness future Kaggle alpha gets judged on.

Outputs:
  data/pnl/strategy_benchmark_nav.parquet   (long: date, strategy, nav_per_unit, nav)
  data/pnl/strategy_benchmark_summary.parquet (per-strategy metrics)

Usage:
  python3 scripts/run_strategy_benchmarks.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.portfolio.paper_portfolio_engine import PaperPortfolioEngine, MarketData
from src.portfolio.famous_strategies import STRATEGIES

PNL_DIR = PROJECT_ROOT / "data" / "pnl"
V3_WEIGHTS = PROJECT_ROOT / "data" / "processed" / "portfolio_weights.parquet"
BENCHMARK = PROJECT_ROOT / "data" / "processed" / "benchmark" / "nifty50.parquet"


def _v3_target() -> pd.DataFrame:
    tw = pd.read_parquet(V3_WEIGHTS)
    return tw[[c for c in ("ticker", "Industry", "final_weight") if c in tw.columns]]


def _nifty_as_units(market: MarketData) -> pd.DataFrame:
    """NIFTY-50 rebased to the same 1,000/unit inception NAV for overlay."""
    if not BENCHMARK.exists():
        return pd.DataFrame()
    b = pd.read_parquet(BENCHMARK)[["date", "close"]].copy()
    b["date"] = pd.to_datetime(b["date"], errors="coerce").dt.normalize()
    b = b.dropna().sort_values("date")
    b = b[b["date"] >= pd.Timestamp("2024-09-01")]
    if b.empty:
        return pd.DataFrame()
    base = b["close"].iloc[0]
    b["nav_per_unit"] = 1000.0 * b["close"] / base
    b["nav"] = 1_000_000_000.0 * b["close"] / base
    b["strategy"] = "NIFTY50"
    return b[["date", "strategy", "nav_per_unit", "nav"]]


def main() -> int:
    print("=" * 72)
    print("STRATEGY BENCHMARK RACE — V3 vs famous strategies vs NIFTY (₹100cr each)")
    print("=" * 72)
    market = MarketData.get()

    targets: dict[str, pd.DataFrame] = {"v3": _v3_target()}
    for name, fn in STRATEGIES.items():
        try:
            targets[name] = fn(30)
        except Exception as exc:  # pragma: no cover
            print(f"  ! {name} failed to build: {exc}")

    nav_rows = []
    summary = []
    for name, tw in targets.items():
        if tw is None or tw.empty:
            print(f"  ! {name}: empty target, skipped")
            continue
        res = PaperPortfolioEngine(tw, strategy_id=name, market=market).simulate()
        n = res.nav_history[["date", "nav_per_unit", "nav_combined"]].copy()
        n = n.rename(columns={"nav_combined": "nav"})
        n["strategy"] = name
        nav_rows.append(n[["date", "strategy", "nav_per_unit", "nav"]])
        m = res.metrics
        summary.append(dict(strategy=name, **m, **res.cost_summary))
        print(f"  {name:16s} ret {m['total_return_pct']:+6.1f}%  ann {m['annualized_return_pct']:+6.1f}%  "
              f"Sharpe {m['sharpe']:+.2f}  maxDD {m['max_drawdown_pct']:6.1f}%  "
              f"cost {res.cost_summary['cost_drag_pct']:.1f}%")

    nifty = _nifty_as_units(market)
    if not nifty.empty:
        nav_rows.append(nifty)
        n_ret = nifty["nav_per_unit"].iloc[-1] / nifty["nav_per_unit"].iloc[0] - 1
        print(f"  {'NIFTY50':16s} ret {n_ret*100:+6.1f}%  (benchmark, to {nifty['date'].max().date()})")

    if nav_rows:
        allnav = pd.concat(nav_rows, ignore_index=True)
        PNL_DIR.mkdir(parents=True, exist_ok=True)
        allnav.to_parquet(PNL_DIR / "strategy_benchmark_nav.parquet", index=False)
        pd.DataFrame(summary).to_parquet(PNL_DIR / "strategy_benchmark_summary.parquet", index=False)
        print(f"  ✓ wrote strategy_benchmark_nav ({len(allnav)} rows) + summary")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
