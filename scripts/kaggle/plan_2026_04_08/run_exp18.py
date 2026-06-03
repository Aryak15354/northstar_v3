#!/usr/bin/env python3
"""Separate runner for EXP-18."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.kaggle.plan_2026_04_08.lib import (
    DOC_ANCHOR_FACTOR_ALIASES,
    DEFAULT_EXP18_FIXED_EVENTS,
    main_for_experiment,
)


SCRIPT_CONFIG = {
    "title": "EXP-18 - Model Collapse Quantification on High-Risk Events",
    "hypothesis": "Even the best CatBoost setup should degrade on high-risk events, and event-conditioned factor subsets should retain more signal than the universal feature set.",
    "tree_base_params": {
        "depth": 4,
        "l2_leaf_reg": 8.0,
        "min_data_in_leaf": 40,
        "learning_rate": 0.02,
        "iterations": 800,
        "boosting_type": "Ordered",
        "od_wait": 30,
        "use_early_stopping": True,
        "apply_quality_weights": False,
    },
    "fallback_upstream": {
        "params": {
            "depth": 4,
            "l2_leaf_reg": 8.0,
            "min_data_in_leaf": 40,
            "learning_rate": 0.02,
            "iterations": 800,
            "boosting_type": "Ordered",
            "od_wait": 30,
            "use_early_stopping": True,
            "apply_quality_weights": False,
        },
    },
    "factor_set": "compendium_doc",
    "requested_event_ids": DEFAULT_EXP18_FIXED_EVENTS,
    "allow_supplemental_events": True,
    "supplemental_target_count": 5,
    "train_window_weeks": 104,
    "regime_factor_threshold": 0.010,
    "factor_aliases": DOC_ANCHOR_FACTOR_ALIASES,
    "require_all_factors": False,
}


if __name__ == "__main__":
    raise SystemExit(main_for_experiment("EXP-18", SCRIPT_CONFIG))
