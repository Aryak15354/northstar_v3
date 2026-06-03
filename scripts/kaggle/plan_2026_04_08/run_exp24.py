#!/usr/bin/env python3
"""Separate runner for EXP-24."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.kaggle.plan_2026_04_08.lib import main_for_experiment


SCRIPT_CONFIG = {
    "title": "EXP-24 - Full Forex x Commodity Signal IC Battery",
    "hypothesis": "The interaction signals should beat the raw commodity and FX moves because they combine the macro move with stock-level exposure.",
    "params": {
        "signal_count": 16,
        "interaction_signals": ["stock_x_crude", "stock_x_inrusd"],
        "standalone_ic_gate": 0.015,
        "targeted_sectors": {
            "inrusd_4w_return": ["Information Technology", "Healthcare"],
            "crude_4w_return": ["Oil Gas & Consumable Fuels", "Healthcare", "Fast Moving Consumer Goods"],
            "steel_4w_return": ["Capital Goods", "Construction", "Construction Materials"],
            "copper_4w_return": ["Capital Goods", "Power", "Consumer Durables"],
            "coal_4w_return": ["Power", "Construction Materials"],
            "stock_x_crude": ["Oil Gas & Consumable Fuels"],
            "stock_x_inrusd": ["Information Technology", "Healthcare"],
        },
    },
}


if __name__ == "__main__":
    raise SystemExit(main_for_experiment("EXP-24", SCRIPT_CONFIG))
