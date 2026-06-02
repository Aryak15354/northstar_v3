#!/usr/bin/env python3
"""Separate runner for EXP-26."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.kaggle.plan_2026_04_08.lib import DOC_ANCHOR_FACTOR_ALIASES, main_for_experiment


SCRIPT_CONFIG = {
    "title": "EXP-26 - Anchor Factor Verification Full 5-Test Battery",
    "hypothesis": "All six anchor factors need to survive the full five-test battery, including decay and Ind-AS continuity checks, before we freeze the production shortlist.",
    "params": {
        "tests": ["T1", "T2", "T3", "T4", "T5"],
        "anchor_factors": [
            "eps_sue_decay",
            "eps_revision_accel",
            "rev_sue_decay",
            "agreement_score",
            "earnings_quality_ratio",
            "accruals_ratio",
        ],
        "ind_as_pre_period": [2015, 2017],
        "ind_as_post_period": [2018, 2025],
        "factor_aliases": DOC_ANCHOR_FACTOR_ALIASES,
    },
}


if __name__ == "__main__":
    raise SystemExit(main_for_experiment("EXP-26", SCRIPT_CONFIG))
