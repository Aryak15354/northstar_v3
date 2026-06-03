#!/usr/bin/env python3
"""
📊 12-MONTH PERFORMANCE REPORT (REAL DATA ONLY)

Generates a lightweight 12-month performance report using ONLY real artifacts:
- Portfolio PnL: data/portfolio/pnl_on_paper.parquet
- Benchmark:      data/processed/nifty.parquet

Outputs:
- reports/performance/performance_report_12m_<timestamp>.md
- reports/performance/performance_report_12m_<timestamp>.json
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd


def _max_drawdown(returns: pd.Series) -> float:
    if returns is None or returns.empty:
        return float("nan")
    equity = (1 + returns).cumprod()
    peak = equity.cummax()
    dd = equity / peak - 1
    return float(dd.min())


def _load_portfolio() -> pd.DataFrame:
    p = Path("data/portfolio/pnl_on_paper.parquet")
    if not p.exists():
        return pd.DataFrame()
    df = pd.read_parquet(p)
    if df is None or df.empty or "Date" not in df.columns:
        return pd.DataFrame()
    df = df.copy()
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"]).sort_values("Date")
    return df


def _load_benchmark_close() -> pd.Series:
    p = Path("data/processed/nifty.parquet")
    if not p.exists():
        return pd.Series(dtype="float64")
    df = pd.read_parquet(p)
    if df is None or df.empty or "close" not in df.columns:
        return pd.Series(dtype="float64")
    s = pd.to_numeric(df["close"], errors="coerce").dropna()
    s.index = pd.to_datetime(s.index)
    return s.sort_index()


def _metrics(returns: pd.Series) -> Dict[str, Any]:
    returns = returns.dropna().astype(float)
    if returns.empty:
        return {}
    total = float((1 + returns).prod() - 1)
    vol = float(returns.std() * np.sqrt(252)) if returns.std() > 0 else float("nan")
    sharpe = float(returns.mean() / returns.std() * np.sqrt(252)) if returns.std() > 0 else None
    mdd = _max_drawdown(returns)
    win = float((returns > 0).mean())
    return {
        "total_return": total,
        "volatility_ann": vol,
        "sharpe": sharpe,
        "max_drawdown": mdd,
        "win_rate": win,
        "avg_daily_return": float(returns.mean()),
    }


def main() -> int:
    print("📊 12-MONTH PERFORMANCE REPORT (REAL DATA ONLY)")
    print("=" * 70)

    pnl = _load_portfolio()
    if pnl.empty:
        print("❌ Missing portfolio PnL: data/portfolio/pnl_on_paper.parquet")
        return 1

    pnl = pnl.copy()
    pnl["Date"] = pd.to_datetime(pnl["Date"])
    last_date = pnl["Date"].max()
    start_date = last_date - timedelta(days=365)
    pnl_12m = pnl[pnl["Date"] >= start_date].copy()
    pnl_12m = pnl_12m.sort_values("Date").set_index("Date")

    if "Return" in pnl_12m.columns and pd.to_numeric(pnl_12m["Return"], errors="coerce").notna().any():
        port_rets = pd.to_numeric(pnl_12m["Return"], errors="coerce")
    else:
        port_rets = pd.to_numeric(pnl_12m["Equity"], errors="coerce").pct_change()
    port_rets = port_rets.dropna()

    bench_close = _load_benchmark_close()
    bench_rets = bench_close.pct_change().reindex(port_rets.index).dropna()

    port_m = _metrics(port_rets)
    bench_m = _metrics(bench_rets)

    excess = None
    if port_m and bench_m and port_m.get("total_return") is not None and bench_m.get("total_return") is not None:
        excess = float(port_m["total_return"] - bench_m["total_return"])

    report: Dict[str, Any] = {
        "report_date": datetime.now().date().isoformat(),
        "generated_at": datetime.now().isoformat(),
        "window": {"start": str(start_date.date()), "end": str(last_date.date())},
        "portfolio": port_m,
        "benchmark": bench_m,
        "excess_return": excess,
        "notes": "All metrics computed from real PnL + real NIFTY close series.",
    }

    out_dir = Path("reports/performance")
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = out_dir / f"performance_report_12m_{ts}.json"
    md_path = out_dir / f"performance_report_12m_{ts}.md"
    json_path.write_text(json.dumps(report, indent=2, default=str))

    def fmt_pct(x: Optional[float]) -> str:
        return "N/A" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.1%}"

    def fmt_num(x: Optional[float]) -> str:
        return "N/A" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.2f}"

    md = []
    md.append("# Northstar V3 — 12M Performance Report (Real Data)")
    md.append("")
    md.append(f"**Window:** `{report['window']['start']}` → `{report['window']['end']}`")
    md.append(f"**Generated:** `{report['generated_at']}`")
    md.append("")
    md.append("## Portfolio")
    md.append(f"- Total return: **{fmt_pct(port_m.get('total_return') if port_m else None)}**")
    md.append(f"- Sharpe: **{fmt_num(port_m.get('sharpe') if port_m else None)}**")
    md.append(f"- Vol (ann.): **{fmt_pct(port_m.get('volatility_ann') if port_m else None)}**")
    md.append(f"- Max drawdown: **{fmt_pct(port_m.get('max_drawdown') if port_m else None)}**")
    md.append(f"- Win rate: **{fmt_pct(port_m.get('win_rate') if port_m else None)}**")
    md.append("")
    md.append("## Benchmark (NIFTY 50)")
    md.append(f"- Total return: **{fmt_pct(bench_m.get('total_return') if bench_m else None)}**")
    md.append(f"- Sharpe: **{fmt_num(bench_m.get('sharpe') if bench_m else None)}**")
    md.append(f"- Vol (ann.): **{fmt_pct(bench_m.get('volatility_ann') if bench_m else None)}**")
    md.append(f"- Max drawdown: **{fmt_pct(bench_m.get('max_drawdown') if bench_m else None)}**")
    md.append("")
    md.append("## Excess Return")
    md.append(f"- Portfolio minus benchmark: **{fmt_pct(excess) if excess is not None else 'N/A'}**")
    md.append("")
    md_path.write_text("\n".join(md))

    print(f"✅ Wrote: {md_path}")
    print(f"✅ Wrote: {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

