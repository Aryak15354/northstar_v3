#!/usr/bin/env python3
"""Section runner for the sector campaign."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.kaggle.plan_2026_04_08_sections.lib import build_section_parser, execute_standard_section


SCRIPT_CONFIG = {
    "section_slug": "section_sector_13_16",
    "title": "Section 4 - Sector Campaign (EXP-13..16)",
    "requested_experiments": ["EXP-13", "EXP-14", "EXP-15", "EXP-16"],
    "notes": [
        "This section auto-runs the ratio prerequisites because the sector models depend on the CatBoost configuration frozen by EXP-12.",
        "Financial Services keeps the rate-state split and contingency sub-universes, IT keeps the FX/export diagnostics, Capital Goods keeps the order-backlog interaction test, and EXP-16 keeps the sector-conditional blend comparison.",
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
