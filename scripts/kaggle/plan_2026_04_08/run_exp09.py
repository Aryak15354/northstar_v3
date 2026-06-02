#!/usr/bin/env python3
"""Separate runner for EXP-09."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.kaggle.plan_2026_04_08.lib import (
    main_for_experiment,
)


SCRIPT_CONFIG = {
    "title": "EXP-09 - CatBoost Depth Ablation + Early Stopping",
    "hypothesis": "Lower tree depth plus chronological early stopping should reduce the train/test ratio without sacrificing the 0.020 IC floor.",
    "train_window_years": 2,
    "ic_floor": 0.020,
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
    "candidate_grid": [
        {"label": "depth_3_es_20", "params": {"depth": 3, "od_wait": 20}},
        {"label": "depth_3_es_30", "params": {"depth": 3, "od_wait": 30}},
        {"label": "depth_3_es_50", "params": {"depth": 3, "od_wait": 50}},
        {"label": "depth_4_es_20", "params": {"depth": 4, "od_wait": 20}},
        {"label": "depth_4_es_30", "params": {"depth": 4, "od_wait": 30}},
        {"label": "depth_4_es_50", "params": {"depth": 4, "od_wait": 50}},
        {"label": "depth_5_es_20", "params": {"depth": 5, "od_wait": 20}},
        {"label": "depth_5_es_30", "params": {"depth": 5, "od_wait": 30}},
        {"label": "depth_5_es_50", "params": {"depth": 5, "od_wait": 50}},
    ],
}


if __name__ == "__main__":
    raise SystemExit(main_for_experiment("EXP-09", SCRIPT_CONFIG))
