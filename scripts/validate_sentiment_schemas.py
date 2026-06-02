#!/usr/bin/env python3
"""
Validate canonical sentiment artifact schemas.

Run this before research or live flows that depend on sentiment data.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.ingestion.sentiment_loader import CANONICAL_COMPANY_COLUMNS, CANONICAL_MARKET_COLUMNS


CHECKS = [
    {
        "path": Path("data/canonical/sentiment/company_sentiment_daily.parquet"),
        "required_columns": CANONICAL_COMPANY_COLUMNS,
        "name": "Company sentiment (canonical daily)",
    },
    {
        "path": Path("data/canonical/sentiment/market_sentiment_daily.parquet"),
        "required_columns": CANONICAL_MARKET_COLUMNS,
        "name": "Market sentiment (canonical daily)",
    },
]


def _validate_recent_data(df: pd.DataFrame, *, name: str, current_time: datetime) -> tuple[bool, str]:
    availability = pd.to_datetime(df.get("availability_date"), errors="coerce").dropna()
    if availability.empty:
        return False, f"FAIL: {name} - availability_date missing or unparsable"

    latest_available = availability.max()
    freshness_limit = current_time - timedelta(days=30)
    if latest_available.to_pydatetime() < freshness_limit:
        return False, (
            f"FAIL: {name} - latest availability_date {latest_available.date()} "
            "is older than 30 days"
        )

    return True, (
        f"PASS: {name} - {len(df)} rows, schema valid, "
        f"latest availability {latest_available.date()}"
    )


def main() -> int:
    all_pass = True
    now = datetime.now()

    for check in CHECKS:
        path = check["path"]
        if not path.exists():
            print(f"FAIL: {check['name']} - file not found at {path}")
            all_pass = False
            continue

        df = pd.read_parquet(path)
        missing = [col for col in check["required_columns"] if col not in df.columns]
        if missing:
            print(f"FAIL: {check['name']} - missing columns: {missing}")
            print(f"Actual columns: {list(df.columns)}")
            all_pass = False
            continue

        passed, message = _validate_recent_data(df, name=check["name"], current_time=now)
        print(message)
        all_pass = all_pass and passed

    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
