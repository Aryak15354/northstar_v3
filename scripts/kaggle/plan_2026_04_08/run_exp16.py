#!/usr/bin/env python3
"""Separate runner for EXP-16."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.kaggle.plan_2026_04_05.catalog import load_plan_info
from scripts.kaggle.plan_2026_04_08.lib import main_for_experiment


SCRIPT_CONFIG = {
    "title": "EXP-16 - Sector Blend Model with Sector-Conditional Features",
    "hypothesis": "A single CatBoost with sector identity and sector-conditional features should capture sector structure while preserving full-universe cross-sectional diversity.",
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
    "sectors": [
        "Financial Services",
        "Information Technology",
        "Capital Goods",
        "Healthcare",
        "Oil Gas & Consumable Fuels",
        "Fast Moving Consumer Goods",
    ],
    "sector_conditional_base_features": list(load_plan_info().sector_conditional_features),
}


if __name__ == "__main__":
    raise SystemExit(main_for_experiment("EXP-16", SCRIPT_CONFIG))
