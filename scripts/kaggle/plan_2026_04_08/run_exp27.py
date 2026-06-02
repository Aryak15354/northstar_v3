#!/usr/bin/env python3
"""Separate runner for EXP-27."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.kaggle.plan_2026_04_08.lib import main_for_experiment


SCRIPT_CONFIG = {
    "title": "EXP-27 - India Earnings Quality Sign Deep Validation",
    "hypothesis": "The positive India earnings-quality sign should concentrate in smaller and more retail-heavy names and be stronger after Ind-AS, with accruals as the primary diagnostic lens.",
    "params": {
        "feature_candidates": ["accruals_ratio", "earnings_quality_ratio"],
        "regime_bucket_groups": {
            "stress": ["R4", "R7", "R8", "R9"],
            "bull_recovery": ["R1", "R2", "R5"],
        },
        "factor_aliases": {
            "accruals_ratio": ["accruals_ratio_cs_z", "accruals_ratio_cs_rank"],
            "earnings_quality_ratio": ["earnings_quality_ratio_cs_z", "earnings_quality_ratio_cs_rank"],
        },
    },
}


if __name__ == "__main__":
    raise SystemExit(main_for_experiment("EXP-27", SCRIPT_CONFIG))
