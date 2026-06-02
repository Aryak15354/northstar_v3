#!/usr/bin/env python3
"""Compute historical factor scores for the canonical Gap 9 factor library."""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.factors import FactorRegistry, FactorStore
from src.ingestion import IngestionRegistry


def parse_args():
    parser = argparse.ArgumentParser(description="Compute historical factor scores")
    parser.add_argument("--start", type=str, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--factors", nargs="+", default=None)
    parser.add_argument("--frequency", choices=["daily", "weekly", "monthly"], default="weekly")
    parser.add_argument("--resume", action="store_true", help="Skip already-computed dates")
    parser.add_argument("--status", action="store_true", help="Show store status and exit")
    parser.add_argument("--config", type=str, default="config/factors_config.yaml")
    return parser.parse_args()


def load_config(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {
            "factors": {
                "enabled": True,
                "enabled_factors": [
                    "bab",
                    "amihud",
                    "piotroski",
                    "max",
                    "earnings_quality",
                    "operating_profitability",
                    "earnings_surprise",
                    "promoter_pledge",
                    "bulk_deal",
                ],
            }
        }
    with open(p, "r") as f:
        return yaml.safe_load(f) or {}


def iter_dates(start_date: datetime, end_date: datetime, frequency: str) -> list[datetime]:
    if frequency == "daily":
        idx = pd.date_range(start_date, end_date, freq="B")
    elif frequency == "monthly":
        idx = pd.date_range(start_date, end_date, freq="M")
    else:
        idx = pd.date_range(start_date, end_date, freq="W-FRI")
    return [d.to_pydatetime() for d in idx]


def main() -> int:
    args = parse_args()
    cfg = load_config(args.config)

    registry = IngestionRegistry(cfg)
    factor_registry = FactorRegistry(registry, cfg)
    store = FactorStore(factor_registry, cfg)

    if args.status:
        status = store.get_store_status()
        print("FACTOR STORE STATUS")
        print("=" * 60)
        print(f"Total dates: {status['total_dates']}")
        print(f"Total tickers: {status['total_tickers']}")
        print(f"Date range: {status['date_range']}")
        for factor, info in status["factors"].items():
            print(f"{factor}: {info}")
        return 0

    if not args.start:
        raise SystemExit("--start is required unless --status is used")

    start_date = datetime.strptime(args.start, "%Y-%m-%d")
    end_date = datetime.strptime(args.end, "%Y-%m-%d")
    dates = iter_dates(start_date, end_date, args.frequency)

    if args.resume:
        missing = set(store.get_missing_dates(start_date, end_date, frequency=args.frequency))
        dates = [d for d in dates if d in missing]

    factors = list(args.factors or factor_registry.get_enabled_factors())
    started = time.time()
    errors = []
    computed = 0

    print(f"Computing factors from {start_date.date()} to {end_date.date()} ({args.frequency})")
    print(f"Factors: {', '.join(factors)}")
    print(f"Dates queued: {len(dates)}")

    for idx, as_of_date in enumerate(dates, start=1):
        tickers = registry.market.get_universe_as_of(as_of_date)
        if not tickers:
            errors.append(f"{as_of_date.date()}: empty_universe")
            continue

        try:
            result = factor_registry.compute_all(as_of_date, tickers, use_cache=True)
            store._save_factor_data(as_of_date, result, factors)  # canonical persistence path
            computed += 1
            if idx == 1 or idx % 10 == 0 or idx == len(dates):
                elapsed = time.time() - started
                print(
                    f"[{idx}/{len(dates)}] {as_of_date.date()} universe={len(tickers)} "
                    f"computed={computed} elapsed_min={elapsed/60:.1f}"
                )
        except Exception as exc:
            errors.append(f"{as_of_date.date()}: {exc}")

    elapsed = time.time() - started
    print("=" * 60)
    print("COMPUTATION SUMMARY")
    print("=" * 60)
    print(f"Dates attempted: {len(dates)}")
    print(f"Dates computed: {computed}")
    print(f"Elapsed minutes: {elapsed / 60:.1f}")
    if errors:
        print("Errors:")
        for err in errors[:10]:
            print(f"  - {err}")
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more")

    status = store.get_store_status()
    print(f"Final status: total_dates={status['total_dates']} total_tickers={status['total_tickers']} date_range={status['date_range']}")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
