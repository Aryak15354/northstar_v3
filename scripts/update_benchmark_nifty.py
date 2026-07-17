#!/usr/bin/env python3
"""Update the canonical NIFTY-50 benchmark (data/processed/benchmark/nifty50.parquet).

The 2026-07-06 audit found the benchmark had NO ingestion source — it froze at
2026-01-30 and 'NAV vs NIFTY' died with it (finding M4). This fetches ^NSEI
via yfinance, appends only genuinely new rows to the canonical index-level
series, and refuses to mix scales (levels only, no rebased inputs).

Runs daily from config/refresh_cadence.yaml. Exit 1 on download failure.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CANONICAL = PROJECT_ROOT / "data" / "processed" / "benchmark" / "nifty50.parquet"


def main() -> int:
    import yfinance as yf

    canon = pd.DataFrame()
    last_date = None
    if CANONICAL.exists():
        canon = pd.read_parquet(CANONICAL)
        canon["date"] = pd.to_datetime(canon["date"], errors="coerce").dt.normalize()
        canon = canon.dropna(subset=["date", "close"]).sort_values("date")
        # levels only — drop any residual wrong-scale rows (index ~ thousands)
        floor = canon["close"].median() * 0.1
        canon = canon[canon["close"] >= floor]
        last_date = canon["date"].max()

    start = (last_date + pd.Timedelta(days=1)).strftime("%Y-%m-%d") if last_date is not None else "2020-01-01"
    try:
        df = yf.download("^NSEI", start=start, progress=False, timeout=30, auto_adjust=True)
    except Exception as exc:
        print(f"❌ NIFTY download failed: {exc}")
        return 1
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.droplevel(1)
    if df.empty:
        print(f"✅ NIFTY benchmark already current (last {last_date.date() if last_date is not None else '—'})")
        return 0

    fresh = df.reset_index()[["Date", "Close"]].rename(columns={"Date": "date", "Close": "close"})
    fresh["date"] = pd.to_datetime(fresh["date"], errors="coerce").dt.normalize()
    fresh = fresh.dropna()
    merged = (pd.concat([canon[["date", "close"]], fresh], ignore_index=True)
              if not canon.empty else fresh)
    merged = merged.drop_duplicates(subset=["date"], keep="last").sort_values("date")
    merged["ticker"] = "NIFTY50"
    merged["returns"] = merged["close"].pct_change().fillna(0.0)
    CANONICAL.parent.mkdir(parents=True, exist_ok=True)
    merged.to_parquet(CANONICAL, index=False)
    print(f"✅ NIFTY benchmark: +{len(fresh)} rows → {merged['date'].max().date()} ({len(merged)} total)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
