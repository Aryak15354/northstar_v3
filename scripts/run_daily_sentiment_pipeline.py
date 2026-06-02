#!/usr/bin/env python3
"""Daily sentiment operational pipeline."""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import date
from pathlib import Path

import pandas as pd


def _resolve_date(value: str) -> pd.Timestamp:
    if str(value).strip().lower() == "today":
        return pd.Timestamp.today().normalize()
    return pd.to_datetime(value, errors="coerce").normalize()


def _run_export(duckdb_path: str) -> int:
    cmd = [
        sys.executable,
        "scripts/export_sentiment_to_v3.py",
        "--duckdb-path",
        duckdb_path,
        "--output-dir",
        "data/processed/sentiment",
        "--incremental",
    ]
    return int(subprocess.run(cmd).returncode)


def _run_news_builder(args: argparse.Namespace) -> int:
    cmd = [
        sys.executable,
        "scripts/build_news_sentiment_dataset.py",
        "--start-year",
        str(args.news_start_year),
        "--end-year",
        str(args.news_end_year),
        "--sources",
        str(args.news_sources),
        "--workers",
        str(args.news_workers),
        "--delay-min",
        str(args.news_delay_min),
        "--delay-max",
        str(args.news_delay_max),
        "--log-every",
        str(args.news_log_every),
        "--rss-lookback-days",
        str(args.news_rss_lookback_days),
        "--sentiment-model",
        str(args.news_sentiment_model),
    ]
    if bool(args.news_resume):
        cmd.append("--resume")
    else:
        cmd.append("--no-resume")
    if int(args.news_max_tickers) > 0:
        cmd.extend(["--max-tickers", str(args.news_max_tickers)])
    if int(args.news_max_months) > 0:
        cmd.extend(["--max-months", str(args.news_max_months)])
    if bool(args.news_include_bulk_deals):
        cmd.append("--include-bulk-deals")
    print(f"[daily-sentiment] running news builder: {' '.join(cmd)}")
    return int(subprocess.run(cmd).returncode)


def _load_as_of(as_of: pd.Timestamp) -> tuple[pd.DataFrame, pd.DataFrame]:
    t_path = Path("data/processed/sentiment/ticker_sentiment_daily.parquet")
    m_path = Path("data/processed/sentiment/market_sentiment_daily.parquet")

    ticker = pd.read_parquet(t_path) if t_path.exists() else pd.DataFrame()
    market = pd.read_parquet(m_path) if m_path.exists() else pd.DataFrame()

    if not ticker.empty:
        ticker["availability_date"] = pd.to_datetime(ticker.get("availability_date", ticker.get("date")), errors="coerce")
        ticker = ticker[ticker["availability_date"] <= as_of].copy()
        ticker = ticker.sort_values(["ticker", "availability_date"], kind="mergesort").groupby("ticker", as_index=False).tail(1)

    if not market.empty:
        market["availability_date"] = pd.to_datetime(market.get("availability_date", market.get("date")), errors="coerce")
        market = market[market["availability_date"] <= as_of].copy()
        market = market.sort_values("availability_date", kind="mergesort").tail(1)

    return ticker, market


def _state_label(p: float) -> str:
    if p >= 0.2:
        return "POSITIVE"
    if p <= -0.2:
        return "NEGATIVE"
    return "NEUTRAL"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run daily sentiment bridge pipeline.")
    p.add_argument("--date", type=str, default="today")
    p.add_argument("--duckdb-path", type=str, default="data/sentiment.duckdb")
    p.add_argument("--include-news-builder", action="store_true", default=False)
    p.add_argument("--news-start-year", type=int, default=2010)
    p.add_argument("--news-end-year", type=int, default=date.today().year)
    p.add_argument("--news-sources", type=str, default="nse,rss")
    p.add_argument("--news-workers", type=int, default=4)
    p.add_argument("--news-delay-min", type=float, default=0.2)
    p.add_argument("--news-delay-max", type=float, default=0.8)
    p.add_argument("--news-log-every", type=int, default=100)
    p.add_argument("--news-rss-lookback-days", type=int, default=30)
    p.add_argument("--news-sentiment-model", type=str, default="auto", choices=["auto", "lexicon", "finbert"])
    p.add_argument("--news-max-tickers", type=int, default=0)
    p.add_argument("--news-max-months", type=int, default=0)
    p.add_argument("--news-resume", action="store_true", default=True)
    p.add_argument("--no-news-resume", action="store_false", dest="news_resume")
    p.add_argument("--news-include-bulk-deals", action="store_true", default=False)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    as_of = _resolve_date(args.date)

    if bool(args.include_news_builder):
        rc = _run_news_builder(args)
        if rc != 0:
            return rc

    rc = _run_export(args.duckdb_path)
    if rc != 0:
        return rc

    ticker, market = _load_as_of(as_of)

    print(f"=== Daily Sentiment Pipeline - {as_of.date()} ===")
    print()

    if market.empty:
        print("Market Sentiment: NA")
    else:
        row = market.iloc[-1]
        pol = float(pd.to_numeric(row.get("india_market_polarity"), errors="coerce") or 0.0)
        conv = float(pd.to_numeric(row.get("india_market_conviction"), errors="coerce") or 0.0)
        unc = float(pd.to_numeric(row.get("india_market_uncertainty"), errors="coerce") or 0.0)
        print(f"Market Sentiment: {_state_label(pol)} ({pol:+.2f}) | Conviction: {conv:.2f} | Uncertainty: {unc:.2f}")

    print()
    print("Top Positive Tickers:")
    if ticker.empty:
        print("  NA")
    else:
        pos = ticker.sort_values("sentiment_polarity", ascending=False).head(10)
        for _, r in pos.iterrows():
            print(
                f"  {str(r.get('ticker','')):<14}: {float(pd.to_numeric(r.get('sentiment_polarity'), errors='coerce') or 0.0):+0.2f} "
                f"(conviction: {float(pd.to_numeric(r.get('sentiment_conviction'), errors='coerce') or 0.0):0.2f}, "
                f"articles: {int(pd.to_numeric(r.get('news_volume'), errors='coerce') or 0)})"
            )

    print()
    print("Top Negative Tickers:")
    if ticker.empty:
        print("  NA")
    else:
        neg = ticker.sort_values("sentiment_polarity", ascending=True).head(10)
        for _, r in neg.iterrows():
            print(
                f"  {str(r.get('ticker','')):<14}: {float(pd.to_numeric(r.get('sentiment_polarity'), errors='coerce') or 0.0):+0.2f} "
                f"(conviction: {float(pd.to_numeric(r.get('sentiment_conviction'), errors='coerce') or 0.0):0.2f}, "
                f"articles: {int(pd.to_numeric(r.get('news_volume'), errors='coerce') or 0)})"
            )

    print()
    print("DISTRESS ALERTS (strong negative + high conviction):")
    if ticker.empty:
        print("  NA")
    else:
        alerts = ticker[
            (pd.to_numeric(ticker["sentiment_polarity"], errors="coerce") < -0.5)
            & (pd.to_numeric(ticker["sentiment_conviction"], errors="coerce") > 0.7)
        ]
        if alerts.empty:
            print("  None")
        else:
            for _, r in alerts.sort_values("sentiment_polarity").iterrows():
                print(
                    f"  {str(r.get('ticker','')):<14}: {float(pd.to_numeric(r.get('sentiment_polarity'), errors='coerce') or 0.0):+0.2f}, "
                    f"conviction {float(pd.to_numeric(r.get('sentiment_conviction'), errors='coerce') or 0.0):0.2f} - POSITION ZEROED"
                )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
