"""CLI entry point for Northstar reporting."""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.reporting.common import LOGGER
from src.reporting.daily_briefing import run_daily_briefing
from src.reporting.weekly_review import run_weekly_review


def _parse_date(raw: str | None) -> date:
    if not raw:
        return date.today()
    return datetime.strptime(raw, "%Y-%m-%d").date()


def main() -> None:
    parser = argparse.ArgumentParser(description="Northstar V3 Report Runner")
    parser.add_argument("--type", choices=["daily", "weekly", "both"], required=True)
    parser.add_argument("--date", type=str, default=None, help="Report date YYYY-MM-DD (default: today)")
    args = parser.parse_args()

    report_date = _parse_date(args.date)
    if args.type in {"daily", "both"}:
        path = run_daily_briefing(report_date)
        LOGGER.info("Daily report written to %s", path)
        print(path)
    if args.type in {"weekly", "both"}:
        path = run_weekly_review(report_date)
        LOGGER.info("Weekly report written to %s", path)
        print(path)


if __name__ == "__main__":
    main()
