#!/usr/bin/env python3
"""Fetch India VIX daily history and write to data/processed/india_vix.parquet."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Download India VIX daily history via yfinance.")
    p.add_argument("--start", default="2008-01-01", help="Start date (YYYY-MM-DD).")
    p.add_argument("--end", default="", help="End date (YYYY-MM-DD).")
    p.add_argument("--out", default="data/processed/india_vix.parquet", help="Output parquet path.")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        import yfinance as yf
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(f"yfinance not available: {exc}") from exc

    end = args.end.strip() or None
    data = yf.download("^INDIAVIX", start=args.start, end=end, progress=False)
    if data is None or data.empty:
        print("No India VIX data returned.")
        return 1

    df = data.reset_index().rename(columns={"Date": "date", "Close": "vix"})
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["vix"] = pd.to_numeric(df["vix"], errors="coerce")
    df = df.dropna(subset=["date", "vix"]).sort_values("date")

    df.to_parquet(out_path, index=False)
    csv_path = out_path.with_suffix(".csv")
    df.to_csv(csv_path, index=False)
    print(f"Saved India VIX to {out_path} ({len(df)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
