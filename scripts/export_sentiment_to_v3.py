#!/usr/bin/env python3
"""Export NS-USO sentiment artifacts into v3 processed sentiment files."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import pandas as pd
from pandas.tseries.offsets import BDay

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in os.sys.path:
    os.sys.path.insert(0, str(REPO_ROOT))

from src.signals.sentiment_bridge import SentimentBridge


def _normalize_export_ticker(value: object) -> str:
    s = str(value or "").strip().upper()
    return s


def _normalize_dates(values: object) -> pd.Series:
    out = pd.to_datetime(values, errors="coerce")
    try:
        out = out.dt.tz_convert(None)
    except Exception:
        try:
            out = out.dt.tz_localize(None)
        except Exception:
            pass
    return out.dt.normalize()


def _enforce_pit_availability(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "date" not in df.columns:
        return df.copy()

    out = df.copy()
    out["date"] = _normalize_dates(out["date"])
    if "availability_date" in out.columns:
        availability = _normalize_dates(out["availability_date"])
    else:
        availability = pd.Series(pd.NaT, index=out.index, dtype="datetime64[ns]")

    minimum_availability = out["date"] + BDay(1)
    invalid = availability.isna() | (availability < minimum_availability)
    out["availability_date"] = availability.where(~invalid, minimum_availability)
    return out


def _validate_ticker(df: pd.DataFrame) -> tuple[bool, list[str]]:
    issues: list[str] = []
    if df.empty:
        return True, issues

    date_s = _normalize_dates(df.get("date"))
    avail_s = _normalize_dates(df.get("availability_date"))
    min_availability = date_s + BDay(1)
    if not (avail_s >= min_availability).fillna(False).all():
        issues.append("availability_date_not_after_date")

    req = ["ticker", "date", "availability_date", "sentiment_polarity", "sentiment_conviction"]
    for c in req:
        if c not in df.columns:
            issues.append(f"missing_col:{c}")
            continue
        if df[c].isna().any() and c in {"ticker", "date", "availability_date"}:
            issues.append(f"nulls_in:{c}")

    if "ticker" in df.columns:
        ticker_s = df["ticker"].map(_normalize_export_ticker)
        if bool(ticker_s.eq("").any()):
            issues.append("empty_ticker")
        bad = ticker_s.ne("") & ~ticker_s.str.endswith(".NS")
        if bool(bad.any()):
            issues.append("ticker_suffix_invalid")

    return len(issues) == 0, issues


def _validate_market(df: pd.DataFrame) -> tuple[bool, list[str]]:
    issues: list[str] = []
    if df.empty:
        return True, issues
    date_s = _normalize_dates(df.get("date"))
    avail_s = _normalize_dates(df.get("availability_date"))
    min_availability = date_s + BDay(1)
    if not (avail_s >= min_availability).fillna(False).all():
        issues.append("availability_date_not_after_date")
    valid_dates = date_s.dropna().sort_values(kind="mergesort")
    if not valid_dates.empty:
        recent_cutoff = valid_dates.max() - pd.Timedelta(days=365)
        recent_dates = valid_dates[valid_dates >= recent_cutoff]
        max_gap = recent_dates.diff().dt.days.dropna().max()
        if pd.notna(max_gap) and float(max_gap) > 60.0:
            issues.append("large_date_gap_detected")
    return len(issues) == 0, issues


def _prepare_ticker_output(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    out = _enforce_pit_availability(df)
    if "ticker" in out.columns:
        out["ticker"] = out["ticker"].map(_normalize_export_ticker)
        out = out[out["ticker"].ne("")].copy()
    return out


def _prepare_market_output(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    return _enforce_pit_availability(df)


def _active_coverage_stats(ticker_df: pd.DataFrame, universe_path: Path) -> tuple[int, int, float, int]:
    if ticker_df.empty or not universe_path.exists():
        return 0, 0, 0.0, 0
    try:
        uni = pd.read_csv(universe_path)
    except Exception:
        return 0, 0, 0.0, 0

    if "Symbol" not in uni.columns:
        return 0, 0, 0.0, 0

    universe = set(uni["Symbol"].astype(str).str.strip().str.upper() + ".NS")
    if not universe:
        return 0, 0, 0.0, 0

    dates = pd.to_datetime(ticker_df.get("date"), errors="coerce")
    latest_date = dates.max()
    if pd.isna(latest_date):
        return 0, len(universe), 0.0, int(ticker_df["ticker"].nunique()) if "ticker" in ticker_df.columns else 0

    latest = ticker_df[dates.eq(latest_date)].copy()
    latest_tickers = set(latest["ticker"].astype(str).str.strip().str.upper())
    covered = len(latest_tickers & universe)
    coverage = 100.0 * covered / len(universe)
    historical = int(ticker_df["ticker"].nunique()) if "ticker" in ticker_df.columns else 0
    return covered, len(universe), coverage, historical


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

    t_out = _prepare_ticker_output(t_out)
    m_out = _prepare_market_output(m_out)

    t_out.to_parquet(ticker_path, index=False)
    m_out.to_parquet(market_path, index=False)

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

    covered, universe_n, coverage, historical = _active_coverage_stats(t_out, Path("universe/nifty500.csv"))
    print(
        f"[sentiment-bridge] coverage: {coverage:.1f}% of universe tickers have sentiment data "
        f"on latest date ({covered}/{universe_n}); historical_unique_tickers={historical}"
    )

    return 0 if pit_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
