#!/usr/bin/env python3
"""Separate runner for EXP-14."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.kaggle.plan_2026_04_08.lib import main_for_experiment


SCRIPT_CONFIG = {
    "title": "EXP-14 - IT Services Sector Model",
    "hypothesis": "An IT-focused model should benefit from export sensitivity and FX-linked features that are diluted in the broad cross-section.",
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
    "reduced_feature_count": 60,
    "required_it_features": [
        "inrusd_4w_return",
        "inrusd_vol_4w",
        "deal_TCV_qoq",
        "attrition_rate",
        "headcount_growth",
        "us_tech_index_4w",
    ],
    "anchor_feature_candidates": [
        "inrusd_4w_return",
        "stock_x_inrusd",
        "fx_sensitivity_score",
        "international_revenue_proxy",
        "dxy_4w_return",
    ],
    "min_proxy_group_tickers": 5,
}


if __name__ == "__main__":
    raise SystemExit(main_for_experiment("EXP-14", SCRIPT_CONFIG))
