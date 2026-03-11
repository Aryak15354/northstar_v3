#!/usr/bin/env python3
"""Export NS-USO sentiment artifacts into v3 processed sentiment files."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in os.sys.path:
    os.sys.path.insert(0, str(REPO_ROOT))

from src.signals.sentiment_bridge import SentimentBridge


def _validate_ticker(df: pd.DataFrame) -> tuple[bool, list[str]]:
    issues: list[str] = []
    if df.empty:
        return True, issues

    date_s = pd.to_datetime(df.get("date"), errors="coerce")
    avail_s = pd.to_datetime(df.get("availability_date"), errors="coerce")
    if not (avail_s > date_s).fillna(False).all():
        issues.append("availability_date_not_after_date")

    req = ["ticker", "date", "availability_date", "sentiment_polarity", "sentiment_conviction"]
    for c in req:
        if c not in df.columns:
            issues.append(f"missing_col:{c}")
            continue
        if df[c].isna().any() and c in {"ticker", "date", "availability_date"}:
            issues.append(f"nulls_in:{c}")

    if "ticker" in df.columns:
        bad = ~df["ticker"].astype(str).str.endswith(".NS")
        if bool(bad.any()):
            issues.append("ticker_suffix_invalid")

    # Soft gap check: large discontinuities usually indicate missing exports.
    by_ticker = df.copy()
    by_ticker["date"] = date_s
    if "ticker" in by_ticker.columns and by_ticker["date"].notna().any():
        by_ticker = by_ticker.dropna(subset=["ticker", "date"]).sort_values(["ticker", "date"], kind="mergesort")
        max_gap = (
            by_ticker.groupby("ticker", sort=False)["date"]
            .diff()
            .dt.days
            .dropna()
            .max()
        )
        if pd.notna(max_gap) and float(max_gap) > 60.0:
            issues.append("large_date_gap_detected")

    return len(issues) == 0, issues


def _validate_market(df: pd.DataFrame) -> tuple[bool, list[str]]:
    issues: list[str] = []
    if df.empty:
        return True, issues
    date_s = pd.to_datetime(df.get("date"), errors="coerce")
    avail_s = pd.to_datetime(df.get("availability_date"), errors="coerce")
    if not (avail_s > date_s).fillna(False).all():
        issues.append("availability_date_not_after_date")
    if date_s.notna().any():
        max_gap = date_s.sort_values(kind="mergesort").diff().dt.days.dropna().max()
        if pd.notna(max_gap) and float(max_gap) > 60.0:
            issues.append("large_date_gap_detected")
    return len(issues) == 0, issues


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Export sentiment bridge outputs to v3.")
    p.add_argument("--duckdb-path", type=str, default="data/sentiment.duckdb")
    p.add_argument("--output-dir", type=str, default="data/processed/sentiment")
    p.add_argument("--start-date", type=str, default="2020-01-01")
    p.add_argument("--incremental", action="store_true")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    ticker_path = out_dir / "ticker_sentiment_daily.parquet"
    market_path = out_dir / "market_sentiment_daily.parquet"

    start_date = args.start_date
    if args.incremental and ticker_path.exists():
        try:
            old = pd.read_parquet(ticker_path)
            if not old.empty:
                last = pd.to_datetime(old["date"], errors="coerce").max()
                if pd.notna(last):
                    start_date = str((pd.Timestamp(last) + pd.Timedelta(days=1)).date())
        except Exception:
            pass

    bridge = SentimentBridge(duckdb_path=args.duckdb_path, output_dir=args.output_dir)

    t_existing = pd.read_parquet(ticker_path) if args.incremental and ticker_path.exists() else pd.DataFrame()
    m_existing = pd.read_parquet(market_path) if args.incremental and market_path.exists() else pd.DataFrame()

    exports = bridge.export_all(start_date=start_date)
    t_new = exports.get("ticker", pd.DataFrame())
    m_new = exports.get("market", pd.DataFrame())

    if args.incremental:
        t_out = (
            pd.concat([t_existing, t_new], ignore_index=True)
            .drop_duplicates(subset=["ticker", "date", "source"], keep="last")
            .sort_values(["ticker", "date", "source"], kind="mergesort")
            if not t_existing.empty or not t_new.empty
            else pd.DataFrame()
        )
        m_out = (
            pd.concat([m_existing, m_new], ignore_index=True)
            .drop_duplicates(subset=["date"], keep="last")
            .sort_values(["date"], kind="mergesort")
            if not m_existing.empty or not m_new.empty
            else pd.DataFrame()
        )
        t_out.to_parquet(ticker_path, index=False)
        m_out.to_parquet(market_path, index=False)
    else:
        t_out = t_new
        m_out = m_new

    ok_t, issues_t = _validate_ticker(t_out)
    ok_m, issues_m = _validate_market(m_out)

    pit_ok = ok_t and ok_m

    if not t_out.empty:
        t_start = pd.to_datetime(t_out["date"], errors="coerce").min().date()
        t_end = pd.to_datetime(t_out["date"], errors="coerce").max().date()
        n_tickers = int(t_out["ticker"].nunique())
        print(f"[sentiment-bridge] ticker sentiment: {n_tickers} tickers, date range {t_start} to {t_end}")
    else:
        print("[sentiment-bridge] ticker sentiment: 0 tickers, date range NA to NA")

    if not m_out.empty:
        m_start = pd.to_datetime(m_out["date"], errors="coerce").min().date()
        m_end = pd.to_datetime(m_out["date"], errors="coerce").max().date()
        print(f"[sentiment-bridge] market sentiment: date range {m_start} to {m_end}")
    else:
        print("[sentiment-bridge] market sentiment: date range NA to NA")

    if pit_ok:
        print("[sentiment-bridge] PIT check: PASS (no future leakage detected)")
    else:
        print(f"[sentiment-bridge] PIT check: FAIL ({','.join(issues_t + issues_m)})")

    universe_path = Path("universe/nifty500.csv")
    universe_n = 0
    if universe_path.exists() and not t_out.empty:
        try:
            uni = pd.read_csv(universe_path)
            universe_n = int(uni["Symbol"].astype(str).nunique())
        except Exception:
            universe_n = 0
    covered = int(t_out["ticker"].nunique()) if not t_out.empty else 0
    coverage = (100.0 * covered / universe_n) if universe_n > 0 else 0.0
    print(f"[sentiment-bridge] coverage: {coverage:.1f}% of universe tickers have sentiment data")

    return 0 if pit_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
