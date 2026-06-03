#!/usr/bin/env python3
"""Section runner for the ratio campaign."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.kaggle.plan_2026_04_08_sections.lib import build_section_parser, execute_standard_section


SCRIPT_CONFIG = {
    "section_slug": "section_ratio_09_12",
    "title": "Section 3 - Ratio Reduction Campaign (EXP-09..12)",
    "requested_experiments": ["EXP-09", "EXP-10", "EXP-11", "EXP-12"],
    "notes": [
        "This section is the ratio-gate campaign and uses the dedicated separate runners for EXP-09..12.",
        "The compendium pass structure is preserved here: EXP-09 hunts for a sub-5x setup, EXP-10 targets the 2.5x frontier, EXP-11 freezes Ordered vs Plain, and EXP-12 validates the longer train window plus the Verdict A seed check.",
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
