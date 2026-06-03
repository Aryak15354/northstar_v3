#!/usr/bin/env python3
"""Separate runner for EXP-21."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.kaggle.plan_2026_04_08.lib import main_for_experiment


SCRIPT_CONFIG = {
    "title": "EXP-21 - TFT as Macro Signal Distillation Engine",
    "hypothesis": "TFT should work here only as a macro regime distiller, with regime probabilities fed back into CatBoost rather than as a stock ranker.",
    "params": {
        "model": "tft",
        "training_panel": {"start_year": 2010, "end_year": 2025},
        "lookback_weeks": 52,
        "forecast_horizon_weeks": 4,
        "known_future_inputs": ["rbi_calendar_flag", "earnings_season_flag"],
        "observed_inputs": ["rbi_rate_chg", "inrusd_4w_return", "vix_india_4w", "fii_proxy", "us_10y_4w"],
        "output_probabilities": [
            "macro_regime_p_crisis",
            "macro_regime_p_bear",
            "macro_regime_p_neutral",
            "macro_regime_p_bull",
        ],
        "incremental_ic_gate": 0.003,
        "val_loss_gate": 0.01,
        "convergence_epoch_cap": 50,
    },
}


if __name__ == "__main__":
    raise SystemExit(main_for_experiment("EXP-21", SCRIPT_CONFIG))
