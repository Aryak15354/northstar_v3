#!/usr/bin/env python3
"""Run all alternative data collection scripts in sequence."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd

try:
    from scripts.utils.progress_resume import Progress
except ModuleNotFoundError:  # direct script execution: python3 scripts/...
    from utils.progress_resume import Progress


SCRIPTS = [
    ("bulk_deals", "scripts/scrape_bse_bulk_deals.py"),
    ("pledge", "scripts/scrape_bse_promoter_pledge.py"),
    ("earnings", "scripts/scrape_bse_earnings_dates.py"),
    ("ratings", "scripts/scrape_credit_ratings.py"),
]

OPTIONAL_SCRIPTS = [
    ("announcements", "scripts/scrape_bse_announcements.py"),
]

PROCESSED_FILES = {
    "bulk_deals": ("data/processed/alternative/bulk_deals_all.csv", "date"),
    "pledge": ("data/processed/alternative/promoter_pledge_all.csv", "date"),
    "earnings": ("data/processed/alternative/earnings_dates_all.csv", "announcement_date"),
    "ratings": ("data/processed/alternative/credit_ratings_all.csv", "date"),
    "announcements": ("data/processed/alternative/announcements_all.csv", "date"),
}


def _row_count(stage_name: str) -> int:
    path, date_col = PROCESSED_FILES.get(stage_name, ("", None))
    if not path:
        return 0
    df = _safe_read(path, date_col=date_col)
    return int(len(df))


def _run(name: str, script: str, args: argparse.Namespace) -> tuple[int, float]:
    cmd = [sys.executable, script]
    if name in {"bulk_deals", "earnings", "ratings", "announcements"}:
        cmd.extend(["--start-year", str(args.start_year)])
        cmd.extend(["--end-year", str(args.end_year)])
    if args.resume:
        cmd.append("--resume")
    if name in {"bulk_deals", "earnings", "ratings", "announcements", "pledge"}:
        cmd.extend(["--delay-min", str(args.delay_min), "--delay-max", str(args.delay_max)])
    if name in {"bulk_deals", "earnings", "ratings", "announcements", "pledge"}:
        cmd.extend(["--log-every", str(args.log_every)])
    if name in {"earnings", "ratings", "announcements"}:
        cmd.extend(["--page-log-every", str(args.page_log_every)])
    if args.max_pages > 0 and name in {"earnings", "ratings", "announcements"}:
        cmd.extend(["--max-pages", str(args.max_pages)])
    if args.max_quarters > 0 and name == "earnings":
        cmd.extend(["--max-quarters", str(args.max_quarters)])
    if name == "earnings":
        cmd.extend(
            [
                "--request-timeout",
                str(args.request_timeout),
                "--max-retries",
                str(args.max_retries),
                "--max-consecutive-page-failures",
                str(args.max_consecutive_page_failures),
            ]
        )
    if name == "announcements":
        cmd.extend(
            [
                "--request-timeout",
                str(args.announcements_request_timeout),
                "--max-retries",
                str(args.announcements_max_retries),
                "--max-consecutive-page-failures",
                str(args.announcements_max_consecutive_page_failures),
                "--api-min-year",
                str(args.announcements_api_min_year),
            ]
        )

    print(f"[{name}] running: {' '.join(cmd)}")
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    t0 = time.time()
    proc = subprocess.run(cmd, text=True, env=env)
    dt = time.time() - t0
    return int(proc.returncode), float(dt)


def _safe_read(path: str, date_col: str | None = None) -> pd.DataFrame:
    p = Path(path)
    if not p.exists():
        return pd.DataFrame()
    try:
        if p.suffix.lower() == ".parquet":
            return pd.read_parquet(p)
        if date_col:
            return pd.read_csv(p, parse_dates=[date_col])
        return pd.read_csv(p)
    except Exception:
        return pd.DataFrame()


def _print_summary() -> None:
    bulk = _safe_read("data/processed/alternative/bulk_deals_all.csv", date_col="date")
    pledge = _safe_read("data/processed/alternative/promoter_pledge_all.csv", date_col="date")
    earnings = _safe_read("data/processed/alternative/earnings_dates_all.csv", date_col="announcement_date")
    ratings = _safe_read("data/processed/alternative/credit_ratings_all.csv", date_col="date")
    ann = _safe_read("data/processed/alternative/announcements_all.csv", date_col="date")

    if not bulk.empty and "date" in bulk.columns:
        yr_min = pd.to_datetime(bulk["date"], errors="coerce").dt.year.min()
        yr_max = pd.to_datetime(bulk["date"], errors="coerce").dt.year.max()
    else:
        yr_min = yr_max = "NA"
    print(f"[bulk_deals] completed: {len(list(Path('data/raw/alternative/bulk_deals').glob('bulk_deals_*.csv')))} files, {len(bulk)} rows, date range {yr_min}-{yr_max}")
    print(f"[pledge] completed: {pledge['bse_code'].nunique() if 'bse_code' in pledge.columns else 0} companies, {len(pledge)} rows")
    print(f"[earnings] completed: {len(earnings)} announcements, {earnings['nse_ticker'].nunique() if 'nse_ticker' in earnings.columns else 0} tickers covered")
    print(f"[ratings] completed: {len(ratings)} actions, {ratings['nse_ticker'].nunique() if 'nse_ticker' in ratings.columns else 0} tickers matched")
    print(f"[announcements] completed: {len(ann)} announcements, {ann['nse_ticker'].nunique() if 'nse_ticker' in ann.columns else 0} tickers")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Collect all alternative datasets.")
    p.add_argument("--start-year", type=int, default=2005)
    p.add_argument("--end-year", type=int, default=pd.Timestamp.today().year)
    p.add_argument("--resume", action="store_true", default=True)
    p.add_argument("--no-resume", action="store_false", dest="resume")
    p.add_argument("--delay-min", type=float, default=2.0)
    p.add_argument("--delay-max", type=float, default=5.0)
    p.add_argument("--log-every", type=int, default=1, help="Pass-through: print ingestion log every N chunks in each scraper.")
    p.add_argument("--page-log-every", type=int, default=25, help="Pass-through: page heartbeat cadence for paginated scrapers.")
    p.add_argument("--max-pages", type=int, default=0, help="Probe mode pass-through for paginated scrapers (0 = all pages).")
    p.add_argument("--max-quarters", type=int, default=0, help="Probe mode pass-through for earnings scraper (0 = all).")
    p.add_argument("--request-timeout", type=int, default=25, help="Pass-through: earnings page request timeout.")
    p.add_argument("--max-retries", type=int, default=4, help="Pass-through: earnings page retries.")
    p.add_argument(
        "--max-consecutive-page-failures",
        type=int,
        default=2,
        help="Pass-through: early-stop guard on repeated page failures (earnings/announcements).",
    )
    p.add_argument(
        "--announcements-api-min-year",
        type=int,
        default=2023,
        help="Pass-through: skip announcement years below this threshold.",
    )
    p.add_argument(
        "--announcements-request-timeout",
        type=int,
        default=60,
        help="Pass-through: announcements page request timeout.",
    )
    p.add_argument(
        "--announcements-max-retries",
        type=int,
        default=4,
        help="Pass-through: announcements page retries.",
    )
    p.add_argument(
        "--announcements-max-consecutive-page-failures",
        type=int,
        default=2,
        help="Pass-through: announcements early-stop guard on repeated page failures.",
    )
    p.add_argument(
        "--include-announcements",
        action="store_true",
        default=False,
        help="Include BSE order/capex/M&A announcement scraping stage (disabled by default due unstable history API).",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    stages = list(SCRIPTS)
    if bool(args.include_announcements):
        stages.extend(OPTIONAL_SCRIPTS)
    else:
        print("[collect_alternative] skipping announcements stage (use --include-announcements to enable).")

    with Progress(total=len(stages), desc="collect_alternative", unit="stage") as p:
        for name, script in stages:
            before_rows = _row_count(name)
            print(f"[{name}] ingest_precheck: rows_before={before_rows}")
            rc, elapsed = _run(name, script, args)
            after_rows = _row_count(name)
            delta = after_rows - before_rows
            status = "PASS" if delta > 0 else "NO_DELTA"
            print(
                f"[{name}] ingest_postcheck: rows_after={after_rows}, "
                f"delta_rows={delta}, stage_seconds={elapsed:.1f}, status={status}"
            )
            p.update(1)
            if rc != 0:
                print(f"[{name}] failed with rc={rc}")
                return rc
    _print_summary()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
