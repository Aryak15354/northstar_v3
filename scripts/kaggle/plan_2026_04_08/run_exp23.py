#!/usr/bin/env python3
"""Separate runner for EXP-23."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.kaggle.plan_2026_04_08.lib import main_for_experiment


SCRIPT_CONFIG = {
    "title": "EXP-23 - iTransformer on Sector and Cross-Asset Channels",
    "hypothesis": "Constraining iTransformer to the sector plus cross-asset co-movement problem should resolve the old OOM path and still yield a usable sector-level signal.",
    "params": {
        "model": "itransformer",
        "section_header_channel_count": 60,
        "intended_channel_count": 45,
        "lookback_weeks": 208,
        "output_feature_name": "itransformer_sector_signal",
        "oom_resolved_required": True,
        "derived_signal_ic_gate": 0.010,
        "feature_candidates": [
            "mom_20d_sector_rel_cs_z",
            "res_mom_20d_cs_z",
            "price_to_sma20_cs_z",
            "vol_z20_cs_z",
            "inrusd_4w_return",
            "crude_4w_return",
            "gold_4w_return",
            "copper_4w_return",
            "steel_4w_return",
            "coal_4w_return",
            "dxy_4w_return",
            "vix_india_4w",
            "rbi_rate_chg",
            "us_10y_4w",
            "commodity_basket",
        ],
    },
}


if __name__ == "__main__":
    raise SystemExit(main_for_experiment("EXP-23", SCRIPT_CONFIG))
