#!/usr/bin/env python3
"""Refresh canonical shadow-reality artifacts from live shadow trading outputs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.live.shadow_reality_publisher import refresh_shadow_reality_from_live_artifacts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", help="Refresh a single YYYY-MM-DD trading date")
    parser.add_argument("--live-data-dir", default="data/live/shadow_trading")
    parser.add_argument("--reality-dir", default="data/shadow_reality")
    parser.add_argument("--shadow-positions-path", default="data/execution/shadow_positions.parquet")
    parser.add_argument("--shadow-state-current-path", default="data/processed/shadow_state_current.json")
    args = parser.parse_args()

    result = refresh_shadow_reality_from_live_artifacts(
        live_data_directory=args.live_data_dir,
        reality_directory=args.reality_dir,
        shadow_positions_path=args.shadow_positions_path,
        shadow_state_current_path=args.shadow_state_current_path,
        target_date=args.date,
    )
    print(json.dumps(result.__dict__, indent=2, default=str))
    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
