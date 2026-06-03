#!/usr/bin/env python3
"""Schedule Northstar reporting jobs."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.reporting.common import LOGGER
from src.reporting.daily_briefing import run_daily_briefing
from src.reporting.weekly_review import run_weekly_review


def _run_daily() -> None:
    today = datetime.now().date()
    path = run_daily_briefing(today)
    LOGGER.info("Scheduled daily briefing generated at %s", path)


def _run_weekly() -> None:
    today = datetime.now().date()
    path = run_weekly_review(today)
    LOGGER.info("Scheduled weekly review generated at %s", path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Schedule Northstar reporting jobs")
    parser.parse_args()
    try:
        from apscheduler.schedulers.blocking import BlockingScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "APScheduler is not installed in this environment. Install it or run "
            "`python3 -m src.reporting.report_runner --type daily|weekly` manually."
        ) from exc

    scheduler = BlockingScheduler(timezone="Asia/Kolkata")
    scheduler.add_job(_run_daily, CronTrigger(day_of_week="mon-fri", hour=9, minute=0))
    scheduler.add_job(_run_weekly, CronTrigger(day_of_week="fri", hour=17, minute=0))
    LOGGER.info("Northstar reporting scheduler started")
    scheduler.start()


if __name__ == "__main__":
    main()
