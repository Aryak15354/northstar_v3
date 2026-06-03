#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.dashboard.northstar_v3_ultimate_integrated_dashboard import _load_core_data_sources
from src.dashboard.view_model_loader import write_view_model


def main() -> int:
    parser = argparse.ArgumentParser(description="Build canonical dashboard view-model artifacts")
    parser.add_argument(
        "--mode",
        choices=["live", "research", "both"],
        default="both",
        help="Which dashboard payload modes to build",
    )
    args = parser.parse_args()

    data = _load_core_data_sources()
    if not isinstance(data, dict):
        raise RuntimeError("source loader did not return a dictionary")

    outputs = {}
    if args.mode in {"live", "both"}:
        outputs["live"] = write_view_model(data, mode="live")
    if args.mode in {"research", "both"}:
        outputs["research"] = write_view_model(data, mode="research")

    print(json.dumps({"check": "build_dashboard_view_model", "outputs": outputs}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
