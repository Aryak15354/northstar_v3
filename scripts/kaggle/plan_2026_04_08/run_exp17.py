#!/usr/bin/env python3
"""Separate runner for EXP-17."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.kaggle.plan_2026_04_08.lib import DOC_ANCHOR_FACTOR_ALIASES, main_for_experiment


SCRIPT_CONFIG = {
    "title": "EXP-17 - Factor Event Heat Map",
    "hypothesis": "The six compendium anchor factors should show clear event-level strengths and blind spots across the major-event table.",
    "factor_set": "compendium_doc",
    "factor_aliases": DOC_ANCHOR_FACTOR_ALIASES,
    "require_all_factors": False,
}


if __name__ == "__main__":
    raise SystemExit(main_for_experiment("EXP-17", SCRIPT_CONFIG))
