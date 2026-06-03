#!/usr/bin/env python3
"""Synchronize the live equity and options books into the canonical PRS runtime."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.runtime import PortfolioRuntimeService
from src.runtime.live_book_sync import sync_live_books_from_disk


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync live equity/options books into PRS")
    parser.add_argument("--runtime-scope", default="live")
    args = parser.parse_args()

    prs = PortfolioRuntimeService(
        db_path=str(PROJECT_ROOT / "data" / "runtime" / "portfolio_runtime.db"),
        materialized_output_dir=str(PROJECT_ROOT / "data" / "processed" / "runtime"),
        starting_cash=10_000_000.0,
    )
    try:
        report = sync_live_books_from_disk(prs, runtime_scope=str(args.runtime_scope or "live"))
    finally:
        prs.close()

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
