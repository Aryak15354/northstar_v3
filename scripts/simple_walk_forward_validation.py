#!/usr/bin/env python3
"""
🧪 WALK-FORWARD VALIDATION (REAL DATA ONLY)

This script produces a walk-forward style report using ONLY real artifacts:
- Portfolio PnL: data/portfolio/pnl_on_paper.parquet
- Benchmark:      data/processed/nifty.parquet (NIFTY 50 close)

No synthetic/random performance data is generated. If there is insufficient
history to form windows, the script exits gracefully.

Output:
- reports/validation/walk_forward_analysis_report_<timestamp>.json
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd


@dataclass
class WindowMetrics:
    window_id: str
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    n_train_days: int
    n_test_days: int
    total_return: float
    avg_daily_return: float
    volatility_ann: float
    sharpe: Optional[float]
    max_drawdown: float
    win_rate: float
    benchmark_return: float
    excess_return: float
    degradation_detected: bool


def _max_drawdown(returns: pd.Series) -> float:
    if returns is None or returns.empty:
        return float("nan")
    equity = (1 + returns).cumprod()
    peak = equity.cummax()
    dd = equity / peak - 1
    return float(dd.min())


def _load_portfolio_returns() -> pd.Series:
    pnl_path = Path("data/portfolio/pnl_on_paper.parquet")
    if not pnl_path.exists():
        return pd.Series(dtype="float64")
    df = pd.read_parquet(pnl_path)
    if df is None or df.empty:
        return pd.Series(dtype="float64")
    if "Date" not in df.columns:
        return pd.Series(dtype="float64")
    df = df.copy()
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"]).sort_values("Date").set_index("Date")

    if "Return" in df.columns and pd.to_numeric(df["Return"], errors="coerce").notna().any():
        rets = pd.to_numeric(df["Return"], errors="coerce")
    elif "Equity" in df.columns:
        eq = pd.to_numeric(df["Equity"], errors="coerce")
        rets = eq.pct_change()
    else:
        return pd.Series(dtype="float64")

    rets = rets.dropna().astype(float)
    rets.index = pd.to_datetime(rets.index)
    return rets.sort_index()


def _load_benchmark_returns(index: pd.DatetimeIndex) -> pd.Series:
    nifty_path = Path("data/processed/nifty.parquet")
    if not nifty_path.exists():
        return pd.Series(index=index, dtype="float64")
    df = pd.read_parquet(nifty_path)
    if df is None or df.empty or "close" not in df.columns:
        return pd.Series(index=index, dtype="float64")
    s = pd.to_numeric(df["close"], errors="coerce").dropna()
    s.index = pd.to_datetime(s.index)
    s = s.sort_index()
    brets = s.pct_change().reindex(index)
    return brets.astype(float)


def main() -> int:
    print("🧪 WALK-FORWARD VALIDATION (REAL DATA ONLY)")
    print("=" * 70)

    rets = _load_portfolio_returns()
    if rets.empty or len(rets) < 300:
        print("⚠️ Not enough portfolio return history to build walk-forward windows.")
        print("   Need ~300+ trading days in data/portfolio/pnl_on_paper.parquet.")
        return 1

    bench = _load_benchmark_returns(rets.index)

    # Window design: 1y train (252d), 3m test (63d), step 1m (21d)
    train_days = 252
    test_days = 63
    step_days = 21
    max_windows = 6

    results: List[WindowMetrics] = []
    last_idx = rets.index.sort_values()
    last_date = last_idx.max()

    for i in range(max_windows):
        test_end = last_date - pd.Timedelta(days=int(i * step_days))
        # Snap to nearest available trading day <= test_end
        test_end = last_idx[last_idx <= test_end].max()
        if pd.isna(test_end):
            continue
        eligible = last_idx[last_idx <= test_end]
        if len(eligible) < test_days:
            continue
        test_slice = eligible[-test_days:]
        if len(test_slice) < test_days:
            continue
        test_start = test_slice.min()
        train_end = last_idx[last_idx < test_start].max()
        if pd.isna(train_end):
            continue
        eligible_train = last_idx[last_idx <= train_end]
        if len(eligible_train) < train_days:
            continue
        train_slice = eligible_train[-train_days:]
        if len(train_slice) < train_days:
            continue
        train_start = train_slice.min()

        test_rets = rets.loc[test_slice]
        if test_rets.empty:
            continue

        total_return = float((1 + test_rets).prod() - 1)
        avg_daily = float(test_rets.mean())
        vol_ann = float(test_rets.std() * np.sqrt(252)) if test_rets.std() > 0 else float("nan")
        sharpe = None
        if test_rets.std() > 0:
            sharpe = float(test_rets.mean() / test_rets.std() * np.sqrt(252))
        mdd = _max_drawdown(test_rets)
        win_rate = float((test_rets > 0).mean())

        bench_rets = bench.loc[test_slice].dropna()
        bench_total = float((1 + bench_rets).prod() - 1) if not bench_rets.empty else float("nan")
        excess = float(total_return - bench_total) if not np.isnan(bench_total) else float("nan")

        # Conservative degradation flag: materially negative return or negative Sharpe.
        degradation = bool((not np.isnan(total_return) and total_return < -0.05) or (sharpe is not None and sharpe < 0))

        results.append(
            WindowMetrics(
                window_id=f"W{i+1:02d}",
                train_start=str(pd.to_datetime(train_start).date()),
                train_end=str(pd.to_datetime(train_end).date()),
                test_start=str(pd.to_datetime(test_start).date()),
                test_end=str(pd.to_datetime(test_end).date()),
                n_train_days=int(len(train_slice)),
                n_test_days=int(len(test_slice)),
                total_return=total_return,
                avg_daily_return=avg_daily,
                volatility_ann=vol_ann,
                sharpe=sharpe,
                max_drawdown=mdd,
                win_rate=win_rate,
                benchmark_return=bench_total,
                excess_return=excess,
                degradation_detected=degradation,
            )
        )

    if not results:
        print("⚠️ Could not construct any walk-forward windows from available data.")
        return 1

    # Summary (derived from real window outputs)
    sharpe_vals = [r.sharpe for r in results if r.sharpe is not None]
    ret_vals = [r.total_return for r in results if not np.isnan(r.total_return)]
    degradations = sum(1 for r in results if r.degradation_detected)

    report: Dict[str, Any] = {
        "report_date": datetime.now().date().isoformat(),
        "generated_at": datetime.now().isoformat(),
        "status": "AVAILABLE",
        "window_config": {"train_days": train_days, "test_days": test_days, "step_days": step_days, "max_windows": max_windows},
        "window_results": [
            {
                **asdict(r),
                # Keep compatibility fields that some dashboards look for
                "avg_out_of_sample_return": r.total_return,
                "oos_sharpe": r.sharpe,
            }
            for r in results
        ],
        "summary": {
            "windows": len(results),
            "avg_total_return": float(np.mean(ret_vals)) if ret_vals else None,
            "avg_sharpe": float(np.mean(sharpe_vals)) if sharpe_vals else None,
            "degradation_rate": degradations / len(results) if results else None,
        },
    }

    out_dir = Path("reports/validation")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"walk_forward_analysis_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out_path.write_text(json.dumps(report, indent=2))

    print(f"✅ Wrote walk-forward report: {out_path}")
    print(f"   Windows: {len(results)}")
    if report["summary"]["avg_total_return"] is not None:
        print(f"   Avg OOS return: {report['summary']['avg_total_return']:.2%}")
    if report["summary"]["avg_sharpe"] is not None:
        print(f"   Avg OOS Sharpe: {report['summary']['avg_sharpe']:.2f}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
