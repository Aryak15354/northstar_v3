#!/usr/bin/env python3
"""Separate runner for EXP-20."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.kaggle.plan_2026_04_08.lib import main_for_experiment


SCRIPT_CONFIG = {
    "title": "EXP-20 - LSTM on Nifty 150 Large-Cap Universe",
    "hypothesis": "The LSTM should recover once we keep it in the large-cap temporal-momentum lane it was designed for instead of forcing it over the noisy full cross-section.",
    "params": {
        "top_n_tickers": 150,
        "model": "lstm",
        "architecture": {
            "layers": 2,
            "hidden_size": 64,
            "dropout": 0.3,
            "batch_size": 64,
            "lookback_days": 60,
            "input_channels": ["daily_return", "daily_volume_zscore", "daily_volatility"],
            "forecast_horizon_days": 5,
            "training_mode_fix": "model.train_before_backward",
        },
        "favorable_events": ["E005", "E008", "E015"],
        "pass_ic_gate": 0.025,
        "pass_ratio_gate": 5.0,
        "pass_hit_rate_gate": 0.54,
    },
}


if __name__ == "__main__":
    raise SystemExit(main_for_experiment("EXP-20", SCRIPT_CONFIG))
