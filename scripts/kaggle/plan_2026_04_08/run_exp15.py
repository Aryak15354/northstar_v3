#!/usr/bin/env python3
"""Separate runner for EXP-15."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.kaggle.plan_2026_04_08.lib import main_for_experiment


SCRIPT_CONFIG = {
    "title": "EXP-15 - Capital Goods Sector Model",
    "hypothesis": "Capital Goods should respond more strongly to capex, commodity, and order-flow signals than the broad universe.",
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
    "required_cg_features": [
        "order_backlog_growth",
        "govt_capex_qoq",
        "steel_4w_return",
        "copper_4w_return",
        "infra_spending_index",
        "power_sector_capex",
    ],
    "proxy_cg_features": {
        "order_backlog_growth_proxy": [
            "order_win_count_90d_cs_z",
            "order_win_count_90d_cs_rank",
            "order_win_flag_30d_cs_z",
        ],
        "power_sector_capex_proxy": [
            "macro_power_3m_trend",
            "power_yoy_growth",
            "macro_power_yoy_growth",
        ],
        "infra_spending_index_proxy": [
            "macro_power_3m_trend",
        ],
        "govt_capex_qoq_proxy": [],
    },
}


if __name__ == "__main__":
    raise SystemExit(main_for_experiment("EXP-15", SCRIPT_CONFIG))
