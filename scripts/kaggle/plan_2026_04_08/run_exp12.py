#!/usr/bin/env python3
"""Separate runner for EXP-12."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.kaggle.plan_2026_04_08.lib import main_for_experiment


SCRIPT_CONFIG = {
    "title": "EXP-12 - Training Window Length Extension",
    "hypothesis": "Extending the training history from 2 to 3 or 4 years should improve stability only if older cross-sections are still regime-relevant.",
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
        "config_label": "ordered",
        "params": {
            "depth": 4,
            "l2_leaf_reg": 8.0,
            "min_data_in_leaf": 40,
            "learning_rate": 0.02,
            "iterations": 800,
            "boosting_type": "Ordered",
            "grow_policy": "SymmetricTree",
            "od_wait": 30,
            "use_early_stopping": True,
            "apply_quality_weights": False,
        },
    },
    "window_years_grid": [2, 3, 4],
}


if __name__ == "__main__":
    raise SystemExit(main_for_experiment("EXP-12", SCRIPT_CONFIG))
