#!/usr/bin/env python3
"""Backfill NSE corporate-filings datasets from downloaded CSVs."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.nse_corporate_filings_processors import (
    RAW_ANNOUNCEMENTS_DIR,
    RAW_PLEDGE_DIR,
    merge_announcements_history,
    merge_promoter_pledge_history,
    parse_nse_announcements_csv,
    parse_nse_promoter_pledge_csv,
)
from scripts.nse_csv_scraper_common import store_raw_download


def _backfill_pledges(paths: list[Path]) -> int:
    if not paths:
        return 0
    total_rows = 0
    for path in paths:
        raw_copy = store_raw_download(path, RAW_PLEDGE_DIR)
        parsed = parse_nse_promoter_pledge_csv(raw_copy)
        merged = merge_promoter_pledge_history(parsed)
        total_rows += int(len(parsed))
        print(
            f"[pledge-backfill] file={raw_copy.name} parsed_rows={len(parsed)} "
            f"ticker_mapped={int(parsed['nse_ticker'].astype(str).str.len().gt(0).sum()) if not parsed.empty else 0} "
            f"canonical_rows={len(merged)}"
        )
    return total_rows


def _backfill_announcements(paths: list[Path]) -> int:
    if not paths:
        return 0
    total_rows = 0
    for path in paths:
        raw_copy = store_raw_download(path, RAW_ANNOUNCEMENTS_DIR)
        parsed = parse_nse_announcements_csv(raw_copy)
        merged = merge_announcements_history(parsed)
        total_rows += int(len(parsed))
        print(
            f"[announcements-backfill] file={raw_copy.name} parsed_rows={len(parsed)} "
            f"canonical_rows={len(merged)}"
        )
    return total_rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill NSE promoter pledge / announcements CSV downloads.")
    parser.add_argument("--pledge-file", action="append", default=[], help="Path to a downloaded NSE pledge CSV.")
    parser.add_argument("--announcement-file", action="append", default=[], help="Path to a downloaded NSE announcements CSV.")
    args = parser.parse_args()

    pledge_paths = [Path(path).expanduser().resolve() for path in args.pledge_file]
    announcement_paths = [Path(path).expanduser().resolve() for path in args.announcement_file]

    for path in pledge_paths + announcement_paths:
        if not path.exists():
            raise FileNotFoundError(path)

    pledge_rows = _backfill_pledges(pledge_paths)
    announcement_rows = _backfill_announcements(announcement_paths)
    print(
        f"[nse-backfill] completed pledge_rows={pledge_rows} "
        f"announcement_rows={announcement_rows}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
