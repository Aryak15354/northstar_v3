#!/usr/bin/env python3
"""Separate runner for EXP-11."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.kaggle.plan_2026_04_08.lib import main_for_experiment


SCRIPT_CONFIG = {
    "title": "EXP-11 - Ordered vs Plain Boosting",
    "hypothesis": "Ordered boosting should remain safer, but Plain needs a controlled comparison before freezing the CatBoost setup.",
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
        "config_label": "l2_8",
        "window_years": 2,
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
    "boosting_grid": [
        {"label": "ordered", "params": {"boosting_type": "Ordered", "grow_policy": "SymmetricTree"}},
        {"label": "plain", "params": {"boosting_type": "Plain", "grow_policy": "SymmetricTree"}},
    ],
}


if __name__ == "__main__":
    raise SystemExit(main_for_experiment("EXP-11", SCRIPT_CONFIG))
