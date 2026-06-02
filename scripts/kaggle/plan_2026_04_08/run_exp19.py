#!/usr/bin/env python3
"""Separate runner for EXP-19."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.kaggle.plan_2026_04_08.lib import main_for_experiment


SCRIPT_CONFIG = {
    "title": "EXP-19 - Regime-Conditional CatBoost Routing",
    "hypothesis": "Routing among non-crisis, macro-bear, and currency-crisis CatBoost specialists should improve IC IR over the universal CatBoost without reviving the old uncentered-output bug.",
    "params": {
        "candidate_models": ["CatBoost"],
        "router_buckets": ["non_crisis", "macro_bear", "currency_crisis"],
        "bucket_train_weeks": 52,
        "bucket_test_weeks": 13,
        "bucket_step_weeks": 13,
        "currency_crisis_vix_threshold": 25.0,
        "currency_crisis_inrusd_4w_threshold": -0.03,
        "macro_bear_drawdown_threshold": -0.10,
        "macro_bear_drawdown_weeks": 8,
        "inference_center_outputs": True,
        "ic_ir_lift_gate": 0.10,
    },
}


if __name__ == "__main__":
    raise SystemExit(main_for_experiment("EXP-19", SCRIPT_CONFIG))
