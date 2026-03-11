#!/usr/bin/env python3
"""Build unified historical news dataset + sentiment features for Northstar v3."""

from __future__ import annotations

import argparse
import atexit
import os
from datetime import date
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in os.sys.path:
    os.sys.path.insert(0, str(REPO_ROOT))

from src.signals.news_sentiment import NewsSentimentBuilder


def _pid_is_running(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(int(pid), 0)
    except Exception:
        return False
    return True


def _acquire_lock(raw_dir: Path) -> tuple[Path, bool]:
    lock_path = raw_dir / ".news_build.lock"
    if lock_path.exists():
        try:
            payload = lock_path.read_text().strip().split(",")
            old_pid = int(payload[0]) if payload else -1
        except Exception:
            old_pid = -1
        if _pid_is_running(old_pid):
            print(
                f"[lock] another news build is running (pid={old_pid}). "
                "Stop it or wait before launching a second run."
            )
            return lock_path, False
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(f"{os.getpid()},{pd.Timestamp.utcnow().isoformat()}\n")
    return lock_path, True


def _release_lock(lock_path: Path) -> None:
    try:
        if lock_path.exists():
            payload = lock_path.read_text().strip().split(",")
            pid = int(payload[0]) if payload else -1
            if pid == os.getpid():
                lock_path.unlink(missing_ok=True)
    except Exception:
        pass


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build historical news sentiment dataset.")
    p.add_argument("--start-year", type=int, default=2010)
    p.add_argument("--end-year", type=int, default=date.today().year)
    p.add_argument("--resume", action="store_true", default=True)
    p.add_argument("--no-resume", action="store_false", dest="resume")
    p.add_argument("--sources", type=str, default="bse,gdelt,rss", help="Comma list: bse,gdelt,rss")
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--gdelt-max-records", type=int, default=250)
    p.add_argument(
        "--gdelt-min-interval",
        type=float,
        default=5.2,
        help="Global minimum seconds between GDELT requests to avoid 429 throttling.",
    )
    p.add_argument("--delay-min", type=float, default=0.2)
    p.add_argument("--delay-max", type=float, default=0.8)
    p.add_argument("--log-every", type=int, default=100)
    p.add_argument("--max-tickers", type=int, default=0, help="Probe mode limit (0=all)")
    p.add_argument("--max-months", type=int, default=0, help="Probe mode limit for month windows (0=all)")
    p.add_argument("--rss-lookback-days", type=int, default=30)
    p.add_argument("--sentiment-model", type=str, default="auto", choices=["auto", "lexicon", "finbert"])
    p.add_argument(
        "--include-bulk-deals",
        action="store_true",
        default=True,
        help="Include bulk-deal events in BSE structured news (default: enabled).",
    )
    p.add_argument(
        "--exclude-bulk-deals",
        action="store_false",
        dest="include_bulk_deals",
        help="Disable bulk-deal event inclusion.",
    )
    p.add_argument(
        "--include-legacy",
        action="store_true",
        default=True,
        help="Include cleaned legacy news if available (default: enabled).",
    )
    p.add_argument(
        "--exclude-legacy",
        action="store_false",
        dest="include_legacy",
        help="Disable legacy news inclusion.",
    )
    p.add_argument(
        "--legacy-news-path",
        type=str,
        default="data/processed/news/legacy_news_clean.parquet",
    )
    p.add_argument("--universe-path", type=str, default="universe/nifty500.csv")
    p.add_argument("--raw-dir", type=str, default="data/raw/news_sentiment")
    p.add_argument("--processed-news-dir", type=str, default="data/processed/news")
    p.add_argument("--processed-sentiment-dir", type=str, default="data/processed/sentiment")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    lock_path, locked = _acquire_lock(Path(args.raw_dir))
    if not locked:
        return 2
    atexit.register(_release_lock, lock_path)

    source_tuple = tuple([s.strip().lower() for s in str(args.sources).split(",") if s.strip()])

    print("=== News Sentiment Build ===")
    print(
        f"[config] years={args.start_year}-{args.end_year} resume={args.resume} "
        f"sources={source_tuple} workers={args.workers} model={args.sentiment_model} "
        f"gdelt_min_interval={args.gdelt_min_interval}s"
    )
    print(
        f"[config] probe_limits max_tickers={args.max_tickers} max_months={args.max_months} "
        f"rss_lookback_days={args.rss_lookback_days}"
    )

    builder = NewsSentimentBuilder(
        universe_path=args.universe_path,
        raw_dir=args.raw_dir,
        processed_news_dir=args.processed_news_dir,
        processed_sentiment_dir=args.processed_sentiment_dir,
        legacy_news_path=args.legacy_news_path,
    )

    stats = builder.run(
        start_year=int(args.start_year),
        end_year=int(args.end_year),
        resume=bool(args.resume),
        sources=source_tuple,
        workers=int(args.workers),
        gdelt_max_records=int(args.gdelt_max_records),
        gdelt_min_interval=float(args.gdelt_min_interval),
        delay_min=float(args.delay_min),
        delay_max=float(args.delay_max),
        log_every=int(args.log_every),
        max_tickers=int(args.max_tickers),
        max_months=int(args.max_months),
        rss_lookback_days=int(args.rss_lookback_days),
        sentiment_model=str(args.sentiment_model),
        include_bulk_deals=bool(args.include_bulk_deals),
        include_legacy=bool(args.include_legacy),
    )
    print(
        f"[done] news_rows={stats.get('news_rows', 0)} "
        f"ticker_daily_rows={stats.get('ticker_daily_rows', 0)} "
        f"market_daily_rows={stats.get('market_daily_rows', 0)} "
        f"weekly_rows={stats.get('weekly_rows', 0)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
