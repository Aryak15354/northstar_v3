#!/usr/bin/env python3
"""
Run multi-horizon option-universe builds:
1) Daily candles for short/medium horizon
2) Weekly candles for long horizon
3) 5-minute candles for recent horizon
"""

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List


IST = timezone(timedelta(hours=5, minutes=30))


def _today_ist() -> str:
    return datetime.now(IST).date().isoformat()


def _days_ago_iso(end_date: str, days: int) -> str:
    end = datetime.strptime(end_date, "%Y-%m-%d").date()
    return (end - timedelta(days=max(1, int(days)))).isoformat()


def _run(cmd: List[str]) -> None:
    print("\n" + "=" * 100)
    print("RUN:", " ".join(shlex.quote(x) for x in cmd))
    print("=" * 100)
    subprocess.run(cmd, check=True)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build multi-horizon offline option universe")
    parser.add_argument("--provider", type=str, choices=["groww", "upstox"], default="groww")
    parser.add_argument("--end-date", type=str, default=_today_ist(), help="End date YYYY-MM-DD (default: today IST)")
    parser.add_argument("--underlyings", type=str, default="NIFTY500_PLUS_INDICES")
    parser.add_argument("--output-dir", type=str, default="data/options/historical")
    parser.add_argument("--daily-years", type=int, default=3, help="Daily horizon in years")
    parser.add_argument("--weekly-years", type=int, default=26, help="Weekly horizon in years (use 26 for ~2000-start requests)")
    parser.add_argument(
        "--weekly-start-date",
        type=str,
        default="",
        help="Optional explicit weekly start date YYYY-MM-DD (overrides --weekly-years for weekly pass)",
    )
    parser.add_argument("--intraday-days", type=int, default=90, help="5-minute horizon in days")
    parser.add_argument("--request-interval-seconds", type=float, default=0.80)
    parser.add_argument("--max-retries", type=int, default=6)
    parser.add_argument("--max-underlyings", type=int, default=0)
    parser.add_argument("--max-contracts-per-underlying", type=int, default=0)
    parser.add_argument("--progress-every-contracts", type=int, default=50)
    parser.add_argument("--future-expiry-days", type=int, default=45)
    parser.add_argument(
        "--contract-listing-lookback-days",
        type=int,
        default=365,
        help="Max assumed listing window before expiry (set 0 to disable clamp)",
    )
    parser.add_argument("--no-resume", action="store_true")
    parser.add_argument("--resume-dir", type=str, default="")
    parser.add_argument("--refresh-instruments", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--use-python-sdk", action="store_true")
    parser.add_argument("--sdk-only", action="store_true")
    parser.add_argument("--no-contracts-api", action="store_true")
    parser.add_argument("--upstox-access-token", type=str, default="")
    parser.add_argument("--extra-contracts-file", action="append", default=[])
    parser.add_argument("--skip-daily", action="store_true")
    parser.add_argument("--skip-weekly", action="store_true")
    parser.add_argument("--skip-intraday", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def _base_cmd(args: argparse.Namespace) -> List[str]:
    root = Path(__file__).resolve().parent
    cmd = [
        sys.executable,
        str(root / "build_groww_option_universe.py"),
        "--provider",
        args.provider,
        "--end-date",
        args.end_date,
        "--underlyings",
        args.underlyings,
        "--output-dir",
        args.output_dir,
        "--request-interval-seconds",
        str(args.request_interval_seconds),
        "--max-retries",
        str(args.max_retries),
        "--future-expiry-days",
        str(args.future_expiry_days),
        "--contract-listing-lookback-days",
        str(args.contract_listing_lookback_days),
    ]
    if args.provider == "groww" and args.use_python_sdk:
        cmd.append("--use-python-sdk")
    if args.provider == "groww" and args.sdk_only:
        cmd.append("--sdk-only")
    if args.no_contracts_api:
        cmd.append("--no-contracts-api")
    if str(args.upstox_access_token or "").strip():
        cmd.extend(["--upstox-access-token", str(args.upstox_access_token).strip()])
    if args.max_underlyings > 0:
        cmd.extend(["--max-underlyings", str(args.max_underlyings)])
    if args.max_contracts_per_underlying > 0:
        cmd.extend(["--max-contracts-per-underlying", str(args.max_contracts_per_underlying)])
    if args.progress_every_contracts > 0:
        cmd.extend(["--progress-every-contracts", str(args.progress_every_contracts)])
    if args.no_resume:
        cmd.append("--no-resume")
    if str(args.resume_dir or "").strip():
        cmd.extend(["--resume-dir", str(args.resume_dir)])
    if args.refresh_instruments:
        cmd.append("--refresh-instruments")
    if args.overwrite:
        cmd.append("--overwrite")
    if args.verbose:
        cmd.append("--verbose")
    for p in args.extra_contracts_file:
        cmd.extend(["--extra-contracts-file", str(p)])
    return cmd


def main() -> int:
    args = _parse_args()
    base = _base_cmd(args)

    # 1) Daily history (default output dir)
    if not args.skip_daily:
        daily_days = int(args.daily_years) * 365
        cmd = list(base) + [
            "--start-date",
            _days_ago_iso(args.end_date, daily_days),
            "--candle-interval",
            "1day",
        ]
        _run(cmd)

    # 2) Weekly long history (stored under output_dir/1w by builder)
    if not args.skip_weekly:
        weekly_start = str(args.weekly_start_date or "").strip()
        if weekly_start:
            start_for_weekly = weekly_start
        else:
            weekly_days = int(args.weekly_years) * 365
            start_for_weekly = _days_ago_iso(args.end_date, weekly_days)
        cmd = list(base) + [
            "--start-date",
            start_for_weekly,
            "--candle-interval",
            "1week",
        ]
        _run(cmd)

    # 3) Recent intraday history (stored under output_dir/5m by builder)
    if not args.skip_intraday:
        cmd = list(base) + [
            "--start-date",
            _days_ago_iso(args.end_date, int(args.intraday_days)),
            "--candle-interval",
            "5minute",
        ]
        _run(cmd)

    print("\nMulti-horizon build complete.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except subprocess.CalledProcessError as exc:
        print(f"Build failed: command exited with {exc.returncode}")
        sys.exit(exc.returncode)
