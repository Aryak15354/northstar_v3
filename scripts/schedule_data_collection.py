#!/usr/bin/env python3
"""Schedule staggered Screener fundamentals collection jobs."""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


RAW_DIR = PROJECT_ROOT / "data" / "raw" / "screener" / "financials"
BUCKET_DIR = PROJECT_ROOT / "data" / "reference" / "screener_schedule"
UNIVERSE_FILE = PROJECT_ROOT / "universe" / "nifty500.csv"

WEEKDAY_BUCKETS = {
    "mon": ("A", "F"),
    "tue": ("G", "M"),
    "wed": ("N", "R"),
    "thu": ("S", "Z"),
}


def _normalize_ticker(value: object) -> str:
    text = str(value or "").strip().upper()
    if not text:
        return ""
    if text.endswith(".NS"):
        return text
    if "." in text:
        text = text.split(".", 1)[0]
    return f"{text}.NS"


def _load_universe_tickers() -> list[str]:
    if not UNIVERSE_FILE.exists():
        return []
    df = pd.read_csv(UNIVERSE_FILE)
    for col in ["ticker", "Ticker", "symbol", "Symbol", "nse_ticker"]:
        if col in df.columns:
            tickers = [_normalize_ticker(v) for v in df[col].tolist()]
            return [t for t in tickers if t]
    if df.shape[1] >= 1:
        tickers = [_normalize_ticker(v) for v in df.iloc[:, 0].tolist()]
        return [t for t in tickers if t]
    return []


def _select_bucket(day_key: str, tickers: list[str]) -> list[str]:
    if day_key == "fri":
        threshold = datetime.now() - timedelta(days=14)
        stale = []
        for ticker in tickers:
            slug = ticker.replace(".NS", "")
            annual_pl = RAW_DIR / f"{slug}_annual_pl.csv"
            if not annual_pl.exists() or datetime.fromtimestamp(annual_pl.stat().st_mtime) < threshold:
                stale.append(ticker)
        return stale

    start, end = WEEKDAY_BUCKETS[day_key]
    selected = []
    for ticker in tickers:
        head = ticker.replace(".NS", "")[:1]
        if start <= head <= end:
            selected.append(ticker)
    return selected


def _write_bucket_file(day_key: str, tickers: list[str]) -> Path:
    BUCKET_DIR.mkdir(parents=True, exist_ok=True)
    path = BUCKET_DIR / f"{day_key}_tickers.txt"
    path.write_text("\n".join(tickers) + ("\n" if tickers else ""), encoding="utf-8")
    return path


def _run_scrape(day_key: str) -> None:
    tickers = _load_universe_tickers()
    selected = _select_bucket(day_key, tickers)
    ticker_file = _write_bucket_file(day_key, selected)
    if not selected:
        print(f"No Screener tickers selected for {day_key}")
        return
    cmd = [
        sys.executable,
        "scripts/scrape_screener_financials.py",
        "--ticker-file",
        str(ticker_file),
        "--resume",
        "--max-tickers",
        str(len(selected)),
    ]
    subprocess.run(cmd, cwd=str(PROJECT_ROOT), check=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Schedule staggered Screener fundamentals collection.")
    parser.add_argument(
        "--run-once",
        choices=["mon", "tue", "wed", "thu", "fri"],
        help="Run one Screener bucket immediately instead of starting the scheduler.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.run_once:
        _run_scrape(args.run_once)
        return

    try:
        from apscheduler.schedulers.blocking import BlockingScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "APScheduler is not installed in this environment. Install it or run "
            "`python3 scripts/schedule_data_collection.py --run-once mon|tue|wed|thu|fri` manually."
        ) from exc

    scheduler = BlockingScheduler(timezone="Asia/Kolkata")
    scheduler.add_job(lambda: _run_scrape("mon"), CronTrigger(day_of_week="mon", hour=21, minute=0))
    scheduler.add_job(lambda: _run_scrape("tue"), CronTrigger(day_of_week="tue", hour=21, minute=0))
    scheduler.add_job(lambda: _run_scrape("wed"), CronTrigger(day_of_week="wed", hour=21, minute=0))
    scheduler.add_job(lambda: _run_scrape("thu"), CronTrigger(day_of_week="thu", hour=21, minute=0))
    scheduler.add_job(lambda: _run_scrape("fri"), CronTrigger(day_of_week="fri", hour=21, minute=0))
    print("Screener data-collection scheduler started")
    scheduler.start()


if __name__ == "__main__":
    main()
