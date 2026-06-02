#!/usr/bin/env python3
"""Merge active + delisted Screener processed files with active-row priority."""

from __future__ import annotations

from pathlib import Path
from typing import Tuple

import pandas as pd


def _quarter_sort_key(label: object) -> tuple[int, int]:
    s = str(label or "").strip().upper()
    try:
        q_part, y_part = s.split("-", 1)
        q = int(q_part.replace("Q", ""))
        y = int(y_part)
        return y, q
    except Exception:
        return (0, 0)


def _merge_with_priority(
    active_path: Path,
    delisted_path: Path,
    key_cols: list[str],
    sort_cols: list[str],
) -> pd.DataFrame:
    active = pd.read_csv(active_path)
    delisted = pd.read_csv(delisted_path)

    active["is_delisted"] = False
    delisted["is_delisted"] = True

    merged = pd.concat([active, delisted], ignore_index=True, sort=False)
    merged = merged.drop_duplicates(subset=key_cols, keep="first").copy()
    merged = merged.sort_values(sort_cols, kind="mergesort").reset_index(drop=True)
    return merged


def _annual_summary(df: pd.DataFrame) -> tuple[int, int, int, int, int]:
    total_tickers = int(df["ticker"].astype(str).nunique()) if "ticker" in df.columns else 0
    active_tickers = int(df.loc[df["is_delisted"] == False, "ticker"].astype(str).nunique()) if "ticker" in df.columns else 0
    delisted_tickers = int(df.loc[df["is_delisted"] == True, "ticker"].astype(str).nunique()) if "ticker" in df.columns else 0
    fy = pd.to_numeric(df.get("fiscal_year", pd.Series(dtype=float)), errors="coerce")
    min_year = int(fy.min()) if not fy.empty and fy.notna().any() else 0
    max_year = int(fy.max()) if not fy.empty and fy.notna().any() else 0
    return total_tickers, active_tickers, delisted_tickers, min_year, max_year


def _shareholding_summary(df: pd.DataFrame) -> tuple[int, int, int, str, str]:
    total_tickers = int(df["ticker"].astype(str).nunique()) if "ticker" in df.columns else 0
    active_tickers = int(df.loc[df["is_delisted"] == False, "ticker"].astype(str).nunique()) if "ticker" in df.columns else 0
    delisted_tickers = int(df.loc[df["is_delisted"] == True, "ticker"].astype(str).nunique()) if "ticker" in df.columns else 0

    qvals = [q for q in df.get("quarter", pd.Series(dtype=object)).astype(str).tolist() if q]
    if not qvals:
        return total_tickers, active_tickers, delisted_tickers, "NA", "NA"
    q_sorted = sorted(qvals, key=_quarter_sort_key)
    return total_tickers, active_tickers, delisted_tickers, q_sorted[0], q_sorted[-1]


def main() -> int:
    annual_active_path = Path("data/processed/screener_fundamentals_annual.csv")
    annual_delisted_path = Path("data/processed/screener_delisted/screener_fundamentals_annual.csv")
    share_active_path = Path("data/processed/screener_shareholding.csv")
    share_delisted_path = Path("data/processed/screener_delisted/screener_shareholding.csv")

    annual = _merge_with_priority(
        active_path=annual_active_path,
        delisted_path=annual_delisted_path,
        key_cols=["ticker", "fiscal_year"],
        sort_cols=["ticker", "fiscal_year"],
    )
    annual.to_csv(annual_active_path, index=False)

    share = _merge_with_priority(
        active_path=share_active_path,
        delisted_path=share_delisted_path,
        key_cols=["ticker", "quarter"],
        sort_cols=["ticker", "quarter"],
    )
    share.to_csv(share_active_path, index=False)

    at, aa, ad, ymin, ymax = _annual_summary(annual)
    st, sa, sd, qmin, qmax = _shareholding_summary(share)

    print("=== Merge Summary ===")
    print("Annual fundamentals:")
    print(f"  Total tickers: {at}")
    print(f"  Active tickers: {aa}")
    print(f"  Delisted tickers: {ad}")
    print(f"  Year range: {ymin} to {ymax}")
    print(f"  Total rows: {len(annual)}")
    print()
    print("Shareholding:")
    print(f"  Total tickers: {st}")
    print(f"  Active tickers: {sa}")
    print(f"  Delisted tickers: {sd}")
    print(f"  Quarter range: {qmin} to {qmax}")
    print(f"  Total rows: {len(share)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
