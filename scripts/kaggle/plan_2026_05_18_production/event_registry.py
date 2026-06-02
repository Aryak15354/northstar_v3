#!/usr/bin/env python3
"""Date-range event registry for Northstar V3 aggregate gate exclusions."""

from __future__ import annotations

from datetime import datetime
from typing import Any


EVENT_WINDOWS: list[dict[str, str]] = [
    {
        "name": "budget_2024_ltcg_stt_buyback_tax_shock",
        "test_start": "2024-06-28",
        "test_end": "2024-09-20",
        "description": "July 23 Budget 2024: LTCG hike, STT increase, buy-back tax reclassification.",
    },
    {
        "name": "post_budget_2024_microstructure_repricing",
        "test_start": "2024-09-27",
        "test_end": "2024-12-20",
        "description": "Post-budget microstructure repricing. FII outflows, mid-cap de-rating.",
    },
    {
        "name": "post_nifty_peak_correction",
        "test_start": "2024-12-27",
        "test_end": "2025-06-20",
        "description": "Post-Nifty-26000-peak correction. Ends Jun 2025; do not extend past this date.",
    },
]


def _as_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if hasattr(value, "to_pydatetime"):
        return value.to_pydatetime()
    return datetime.strptime(str(value)[:10], "%Y-%m-%d")


def is_event_window(test_start_date: Any, test_end_date: Any) -> tuple[bool, str | None]:
    """Return whether a test period overlaps an active structural event range."""
    test_start = _as_datetime(test_start_date)
    test_end = _as_datetime(test_end_date)
    for event in EVENT_WINDOWS:
        ev_start = datetime.strptime(event["test_start"], "%Y-%m-%d")
        ev_end = datetime.strptime(event["test_end"], "%Y-%m-%d")
        if test_start <= ev_end and test_end >= ev_start:
            return True, event["name"]
    return False, None
