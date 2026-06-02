#!/usr/bin/env python3
"""Section runner for the regime campaign."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.kaggle.plan_2026_04_08_sections.lib import build_section_parser, execute_standard_section


SCRIPT_CONFIG = {
    "section_slug": "section_regime_17_19",
    "title": "Section 5 - Regime Campaign (EXP-17..19)",
    "requested_experiments": ["EXP-17", "EXP-18", "EXP-19"],
    "notes": [
        "This section pulls in the ratio prerequisites for EXP-18 automatically.",
        "EXP-19 is now enforced as regime-conditional CatBoost routing, not the older cross-model CatBoost/LSTM/TCN approximation.",
    ],
}


def main() -> int:
    parser = build_section_parser(SCRIPT_CONFIG["title"])
    args = parser.parse_args()
    if args.describe:
        print(json.dumps(SCRIPT_CONFIG, indent=2))
        return 0
    execute_standard_section(
        section_slug=SCRIPT_CONFIG["section_slug"],
        section_title=SCRIPT_CONFIG["title"],
        requested_exp_ids=list(SCRIPT_CONFIG["requested_experiments"]),
        args=args,
        extra_notes=list(SCRIPT_CONFIG["notes"]),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
