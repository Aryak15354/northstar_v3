#!/usr/bin/env python3
"""Build the MICRO-002 scrape-target universe -- entirely from local data, no network.

Combines:
  * data/reference/nse_universe_history.parquet -- full tradeable-universe history
    (ticker, listing_date, delisting_date), the broadest source of *which* tickers
    need coverage for 2010-2022, active or since-delisted.
  * data/processed/screener_metadata.csv + data/processed/screener_delisted/
    screener_metadata.csv -- BSE scrip codes, where known.
  * data/universe/symbol_migration_map.parquet -- ISIN, for names that changed
    symbol/delisted (useful as a secondary key if a future BSE code lookup step
    is added; not required by the fetchers here).

Coverage is disclosed honestly, not silently assumed: BSE-code coverage is only
available for a minority of delisted names (real gap, not a bug) -- the NSE path
covers the full universe by symbol alone, the BSE path only where a code exists.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class Target:
    ticker: str          # e.g. "RELIANCE.NS"
    nse_symbol: str       # e.g. "RELIANCE"
    bse_code: str | None  # e.g. "500325", or None if unknown
    isin: str | None
    listing_date: pd.Timestamp | None
    delisting_date: pd.Timestamp | None


def _nse_symbol(ticker: str) -> str:
    return str(ticker).strip().upper().removesuffix(".NS").removesuffix(".BO")


def _load_bse_codes() -> dict[str, str]:
    """ticker -> bse_code, from whichever local metadata files are present."""
    out: dict[str, str] = {}
    for rel in ("data/processed/screener_metadata.csv",
               "data/processed/screener_delisted/screener_metadata.csv"):
        p = REPO / rel
        if not p.exists():
            continue
        df = pd.read_csv(p, usecols=lambda c: c in {"ticker", "bse_code"})
        for _, row in df.iterrows():
            code = row.get("bse_code")
            if pd.notna(code) and str(code).strip() and str(code).strip().lower() != "nan":
                # bse_code sometimes loads as float (520155.0) -- normalize to a clean int string
                try:
                    code_s = str(int(float(code)))
                except (ValueError, TypeError):
                    code_s = str(code).strip()
                out[str(row["ticker"]).strip().upper()] = code_s
    return out


def _load_isin_map() -> dict[str, str]:
    out: dict[str, str] = {}
    p = REPO / "data/universe/symbol_migration_map.parquet"
    if p.exists():
        df = pd.read_parquet(p, columns=["mapped_ticker", "isin"])
        for _, row in df.iterrows():
            if pd.notna(row["isin"]):
                out[str(row["mapped_ticker"]).strip().upper()] = str(row["isin"]).strip()
    p2 = REPO / "data/canonical/reference/universe/nifty500_universe_enriched.csv"
    if p2.exists():
        df2 = pd.read_csv(p2, usecols=["ticker", "isin"])
        for _, row in df2.iterrows():
            if pd.notna(row["isin"]):
                out.setdefault(str(row["ticker"]).strip().upper(), str(row["isin"]).strip())
    return out


def build_universe(start: str = "2010-01-01", end: str = "2022-12-31") -> pd.DataFrame:
    """One row per ticker that was tradeable at any point in [start, end].

    Source: `data/kaggle_upload/panel_a_weekly.parquet` -- checked directly, not assumed. Two other
    candidates were tried first and rejected: `data/reference/nse_universe_history.parquet` and
    `data/universe/universe_snapshots.parquet` both only cover 2021+ (a recent snapshot window, not
    2010-2022 history), which would have silently under-covered exactly the delisted names this
    scrape exists to reach. The panel itself -- built with the delisted-name backfill already
    integrated -- is the broadest real source of "who was tradeable when" back to 2010.
    """
    panel_path = REPO / "data/kaggle_upload/panel_a_weekly.parquet"
    if not panel_path.exists():
        raise FileNotFoundError(f"{panel_path} not found.")
    hist = pd.read_parquet(panel_path, columns=["date", "ticker", "is_delisted"])
    hist["date"] = pd.to_datetime(hist["date"])
    start_ts, end_ts = pd.Timestamp(start), pd.Timestamp(end)
    in_range = hist[(hist["date"] >= start_ts) & (hist["date"] <= end_ts)]
    per_ticker = in_range.groupby("ticker").agg(
        listing_date=("date", "min"), delisting_date=("date", "max")).reset_index()

    bse_codes = _load_bse_codes()
    isin_map = _load_isin_map()

    rows = []
    for _, r in per_ticker.iterrows():
        tk = str(r["ticker"]).strip().upper()
        rows.append(Target(
            ticker=tk, nse_symbol=_nse_symbol(tk),
            bse_code=bse_codes.get(tk), isin=isin_map.get(tk),
            listing_date=pd.Timestamp(r["listing_date"]) if pd.notna(r["listing_date"]) else None,
            delisting_date=pd.Timestamp(r["delisting_date"]) if pd.notna(r["delisting_date"]) else None,
        ))

    df = pd.DataFrame([vars(t) for t in rows]).sort_values("ticker").reset_index(drop=True)
    return df


def coverage_report(df: pd.DataFrame) -> str:
    n = len(df)
    n_bse = df["bse_code"].notna().sum()
    n_isin = df["isin"].notna().sum()
    return (f"universe: {n} tickers ({df['ticker'].str.endswith('.NS').all()!s} all .NS)\n"
           f"  BSE code known : {n_bse} ({n_bse/n:.0%}) -- BSE path covers only these\n"
           f"  ISIN known     : {n_isin} ({n_isin/n:.0%})\n"
           f"  NSE path covers all {n} by symbol alone (no code required)")


if __name__ == "__main__":
    u = build_universe()
    print(coverage_report(u))
    out = REPO / "scripts/microstructure/bse_nse_shareholding_scraper/universe_targets.csv"
    u.to_csv(out, index=False)
    print(f"wrote {out}")
