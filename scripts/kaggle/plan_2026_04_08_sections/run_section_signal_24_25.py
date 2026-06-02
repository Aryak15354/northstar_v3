#!/usr/bin/env python3
"""Section runner for signal expansion."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.kaggle.plan_2026_04_08_sections.lib import build_section_parser, execute_standard_section


SCRIPT_CONFIG = {
    "section_slug": "section_signal_24_25",
    "title": "Section 7 - Signal Expansion (EXP-24..25)",
    "requested_experiments": ["EXP-24", "EXP-25"],
    "notes": [
        "Cross-asset and CCMS experiments are run directly on the current merged export and explicitly record any market-cap weighting gaps.",
        "The signal battery keeps the compendium's interaction-vs-raw comparison explicit, and CCMS keeps the Adani event and size-dependency checks explicit.",
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
