#!/usr/bin/env python3
"""Separate runner for EXP-13."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.kaggle.plan_2026_04_08.lib import main_for_experiment


SCRIPT_CONFIG = {
    "title": "EXP-13 - Financial Services Sector Model",
    "hypothesis": "A dedicated Financial Services model should outperform the broad-universe CatBoost on Financial Services stocks because rates and balance-sheet structure are more homogeneous inside the sector.",
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
    "required_fs_features": [
        "nim_4q_trend",
        "npa_net_4q",
        "provision_coverage",
        "credit_deposit_ratio",
        "rbi_rate_chg",
        "loan_growth_yoy",
        "casa_ratio",
        "gnpa_yoy",
    ],
    "contingency_ic_threshold": 0.020,
    "min_sub_universe_tickers": 20,
    "min_tickers_by_universe": {
        "lenders": 20,
        "other_financials": 20,
        "banks": 8,
        "nbfcs": 8,
        "insurance": 4,
    },
}


if __name__ == "__main__":
    raise SystemExit(main_for_experiment("EXP-13", SCRIPT_CONFIG))
