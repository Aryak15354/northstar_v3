#!/usr/bin/env python3
"""Separate runner for EXP-10."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.kaggle.plan_2026_04_08.lib import main_for_experiment


SCRIPT_CONFIG = {
    "title": "EXP-10 - L2 Regularization Sweep",
    "hypothesis": "Increasing leaf regularization on top of the EXP-09 winner should improve generalization and move the ratio toward the 2.5x gate without breaking IC.",
    "ic_floor": 0.020,
    "ratio_gate": 2.5,
    "tree_base_params": {
        "depth": 4,
        "l2_leaf_reg": 15.0,
        "min_data_in_leaf": 40,
        "learning_rate": 0.02,
        "iterations": 800,
        "boosting_type": "Ordered",
        "od_wait": 30,
        "use_early_stopping": True,
        "apply_quality_weights": False,
    },
    "fallback_upstream": {
        "config_label": "depth_4_es_30",
        "window_years": 2,
        "params": {
            "depth": 4,
            "l2_leaf_reg": 15.0,
            "min_data_in_leaf": 40,
            "learning_rate": 0.02,
            "iterations": 800,
            "boosting_type": "Ordered",
            "od_wait": 30,
            "use_early_stopping": True,
            "apply_quality_weights": False,
        },
    },
    "l2_grid": [3, 5, 8, 10, 15, 20],
}


if __name__ == "__main__":
    raise SystemExit(main_for_experiment("EXP-10", SCRIPT_CONFIG))
