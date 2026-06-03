#!/usr/bin/env python3
"""Separate runner for EXP-25."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.kaggle.plan_2026_04_08.lib import main_for_experiment


SCRIPT_CONFIG = {
    "title": "EXP-25 - Conglomerate Co-Movement Signal Full Validation",
    "hypothesis": "Conglomerate peer returns should predict follow-through, especially in large groups and especially during the Adani stress event.",
    "params": {
        "min_group_size": 2,
        "lookback_weeks": 4,
        "adani_event_id": "E017",
        "overall_ic_gate": 0.015,
        "adani_ic_gate": 0.040,
    },
}


if __name__ == "__main__":
    raise SystemExit(main_for_experiment("EXP-25", SCRIPT_CONFIG))
