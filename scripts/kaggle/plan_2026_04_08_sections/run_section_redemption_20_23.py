#!/usr/bin/env python3
"""Section runner for the failed-model redemption programme."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.kaggle.plan_2026_04_08_sections.lib import build_section_parser, execute_standard_section


SCRIPT_CONFIG = {
    "section_slug": "section_redemption_20_23",
    "title": "Section 6 - Model Redemption (EXP-20..23)",
    "requested_experiments": ["EXP-20", "EXP-21", "EXP-22", "EXP-23"],
    "notes": [
        "This section uses the current weekly export as the execution substrate and records any proxy-vs-compendium gaps in the section audit.",
        "Each experiment keeps the compendium's intended role explicit: LSTM as large-cap temporal momentum, TFT as macro regime distillation, TCN as sector rotation, and iTransformer as constrained cross-asset co-movement.",
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
