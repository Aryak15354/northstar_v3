#!/usr/bin/env python3
"""Run 3 EXP-19: Regime-conditional model routing with clean rare-regime skips."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.kaggle.plan_2026_05_18_production.experiments import RUNNERS

EXP_ID = "EXP-19"
DESCRIPTION = "Regime-conditional CatBoost routing with zero-feature guards and stronger rare-regime skips."
RUN3_FIXES = [
    "does not crash when a regime has no labels in an early window",
    "uses 1,500-row regime preflight/skip behavior",
    "skips zero-feature IC-screen windows cleanly",
    "gates out the historically anti-predictive Sideways/R6 regime",
    "regularises rare regimes with depth=3/min_data_in_leaf=120/iterations=300",
    "uses EXP-17 heatmap output to interpret routing quality",
]


def _default_data_dir() -> str | None:
    path = Path("/kaggle/input/datasets/aryakghoshal/northstar-v3-feature-export-fixed")
    return str(path) if path.exists() else None


def _default_output_dir() -> str:
    path = Path("/kaggle/working/northstar_results_run3_exp19")
    return str(path) if Path("/kaggle/working").exists() else str(ROOT / "tmp" / "kaggle_results" / "run3_exp19")


def main() -> int:
    parser = argparse.ArgumentParser(description=DESCRIPTION)
    parser.add_argument("--data-dir", default=_default_data_dir())
    parser.add_argument("--output-dir", default=_default_output_dir())
    parser.add_argument("--max-windows", type=int, default=None)
    parser.add_argument("--feature-policy", choices=["safe", "full"], default="full")
    args = parser.parse_args()
    print(f"\nRunning {EXP_ID}: {DESCRIPTION}")
    for item in RUN3_FIXES:
        print(f"  - {item}")
    RUNNERS[EXP_ID](args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
