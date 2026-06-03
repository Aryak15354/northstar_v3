#!/usr/bin/env python3
"""Separate runner for EXP-22."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.kaggle.plan_2026_04_08.lib import main_for_experiment


SCRIPT_CONFIG = {
    "title": "EXP-22 - TCN for Sector Momentum and Rotation Detection",
    "hypothesis": "A TCN on sector-return channels should capture rotation cycles that are too temporal for the cross-sectional factor stack alone.",
    "params": {
        "model": "tcn",
        "sector_count": 21,
        "lookback_weeks": 104,
        "forecast_horizon_weeks": 4,
        "dilations": [1, 2, 4, 8],
        "kernel_size": 3,
        "layers": 4,
        "output_feature_name": "sector_tcn_momentum",
        "standalone_ic_gate": 0.015,
        "incremental_ic_gate": 0.002,
    },
}


if __name__ == "__main__":
    raise SystemExit(main_for_experiment("EXP-22", SCRIPT_CONFIG))
