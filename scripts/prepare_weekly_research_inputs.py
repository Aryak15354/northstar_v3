#!/usr/bin/env python3
"""Store and normalize the weekly manual research inputs inside Northstar V3."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOWNLOADS_DIR = Path.home() / "Downloads"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.research.manual_input_registry import prepare_research_inputs  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare weekly manual research inputs.")
    parser.add_argument(
        "--major-regime-xlsx",
        type=Path,
        default=DOWNLOADS_DIR / "northstar_v3_nse_regime_events_2005_2026.xlsx",
    )
    parser.add_argument(
        "--subtle-regime-xlsx",
        type=Path,
        default=DOWNLOADS_DIR / "northstar_v3_subtle_periods_2005_2026.xlsx",
    )
    parser.add_argument(
        "--universe-master-xlsx",
        type=Path,
        default=DOWNLOADS_DIR / "Nifty500_Universe_Master.xlsx",
    )
    parser.add_argument(
        "--universe-master-csv",
        type=Path,
        default=DOWNLOADS_DIR / "nifty500_universe.csv",
    )
    parser.add_argument(
        "--weekly-sprint-docx",
        type=Path,
        default=DOWNLOADS_DIR / "northstar_v3_weekly_sprint_2026_03_29.docx",
    )
    parser.add_argument(
        "--research-plan-docx",
        type=Path,
        default=DOWNLOADS_DIR / "northstar_v3_comprehensive_research_plan.docx",
    )
    parser.add_argument(
        "--raw-destination-root",
        type=Path,
        default=PROJECT_ROOT / "data/raw/shared/research_inputs/week_2026_03_29",
    )
    parser.add_argument(
        "--canonical-reference-root",
        type=Path,
        default=PROJECT_ROOT / "data/canonical/reference",
    )
    parser.add_argument(
        "--legacy-universe-path",
        type=Path,
        default=PROJECT_ROOT / "universe/nifty500.csv",
    )
    parser.add_argument(
        "--news-master-path",
        type=Path,
        default=PROJECT_ROOT / "data/raw/historical_news_datasets/nifty500_companies_master.csv",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = prepare_research_inputs(
        major_regime_xlsx=args.major_regime_xlsx.expanduser().resolve(),
        subtle_regime_xlsx=args.subtle_regime_xlsx.expanduser().resolve(),
        universe_master_xlsx=args.universe_master_xlsx.expanduser().resolve(),
        universe_master_csv=args.universe_master_csv.expanduser().resolve(),
        weekly_sprint_docx=args.weekly_sprint_docx.expanduser().resolve(),
        research_plan_docx=args.research_plan_docx.expanduser().resolve(),
        raw_destination_root=args.raw_destination_root.expanduser().resolve(),
        canonical_reference_root=args.canonical_reference_root.expanduser().resolve(),
        legacy_universe_path=args.legacy_universe_path.expanduser().resolve(),
        news_master_path=args.news_master_path.expanduser().resolve(),
    )
    print(json.dumps(manifest, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
