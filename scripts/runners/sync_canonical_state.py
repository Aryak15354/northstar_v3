#!/usr/bin/env python3
"""Run the canonical unified-state assembly outside the full batch pipeline."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run_complete_v3_system import sync_canonical_state


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync canonical unified state")
    parser.add_argument("--date", default="today", help="As-of date forwarded to sync_canonical_state")
    parser.add_argument(
        "--run-label",
        default="intraday",
        help="Folder label under data/operations/canonical_state_sync_runs/",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = (
        PROJECT_ROOT
        / "data"
        / "operations"
        / "canonical_state_sync_runs"
        / str(args.run_label or "intraday")
        / run_id
    )
    run_dir.mkdir(parents=True, exist_ok=True)

    payload = sync_canonical_state(SimpleNamespace(date=args.date), run_dir)
    print(json.dumps(payload, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
