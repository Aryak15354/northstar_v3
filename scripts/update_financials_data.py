#!/usr/bin/env python3
"""
On-demand financials refresh pipeline.

Runs:
1) src/ingestion/financials_fetcher.py
2) src/processing/fundamental_processor.py
3) src/processing/valuation_engine.py
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _run(cmd: list[str], timeout: int) -> tuple[bool, str]:
    try:
        res = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        msg = (res.stdout or "").strip() or (res.stderr or "").strip()
        return res.returncode == 0, msg
    except Exception as e:
        return False, str(e)


def _has_cached_raw_financials() -> bool:
    raw_dir = PROJECT_ROOT / "data/raw/financials_quarterly"
    return raw_dir.exists() and any(raw_dir.glob("*_income.csv"))


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Update yfinance quarterly financials and valuation artifacts")
    p.add_argument("--tickers", type=str, default="", help="Comma-separated ticker list; defaults to full universe")
    p.add_argument("--max-tickers", type=int, default=0, help="Optional cap for ad-hoc runs")
    p.add_argument("--sleep-seconds", type=float, default=0.0, help="Sleep between yfinance requests")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    fetch_cmd = [sys.executable, "src/ingestion/financials_fetcher.py"]
    if args.tickers.strip():
        fetch_cmd += ["--tickers", args.tickers]
    if args.max_tickers and args.max_tickers > 0:
        fetch_cmd += ["--max-tickers", str(args.max_tickers)]
    if args.sleep_seconds > 0:
        fetch_cmd += ["--sleep-seconds", str(args.sleep_seconds)]

    print("▶ financials_fetcher")
    ok, msg = _run(fetch_cmd, timeout=7200)
    print(msg[:1200] if msg else "completed")
    if not ok:
        if _has_cached_raw_financials():
            print("⚠️ financials_fetcher returned no fresh rows; proceeding with cached raw financials")
        else:
            print("❌ financials_fetcher failed and no cached raw financials were found")
            return 1

    print("▶ fundamental_processor")
    ok, msg = _run([sys.executable, "src/processing/fundamental_processor.py"], timeout=1800)
    print(msg[:1200] if msg else "completed")
    if not ok:
        print("❌ fundamental_processor failed")
        return 1

    print("▶ valuation_engine")
    ok, msg = _run([sys.executable, "src/processing/valuation_engine.py"], timeout=1800)
    print(msg[:1200] if msg else "completed")
    if not ok:
        print("❌ valuation_engine failed")
        return 1

    print("✅ Financials refresh pipeline complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
