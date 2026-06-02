#!/usr/bin/env python3
"""Download NSE equity announcements CSVs and merge them into canonical history."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.nse_corporate_filings_processors import (  # noqa: E402
    RAW_ANNOUNCEMENTS_DIR,
    merge_announcements_history,
    parse_nse_announcements_csv,
)
from scripts.nse_csv_scraper_common import (  # noqa: E402
    cleanup_download_dir,
    create_nse_session,
    nse_request,
    store_raw_download,
)


NSE_URL = "https://www.nseindia.com/companies-listing/corporate-filings-announcements"
DOWNLOAD_DIR = RAW_ANNOUNCEMENTS_DIR / "_downloads"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
FILE_PATTERN = "*AN-equities*.csv"
API_URL = "https://www.nseindia.com/api/corporate-announcements"


def _period_window(period: str) -> tuple[str, str]:
    end = pd.Timestamp.today().normalize()
    if period == "1D":
        start = end - pd.Timedelta(days=1)
    elif period == "1W":
        start = end - pd.Timedelta(days=7)
    elif period == "1M":
        start = end - pd.DateOffset(months=1)
    elif period == "3M":
        start = end - pd.DateOffset(months=3)
    elif period == "6M":
        start = end - pd.DateOffset(months=6)
    elif period == "1Y":
        start = end - pd.DateOffset(years=1)
    else:
        raise ValueError(f"Unsupported period: {period}")
    return start.strftime("%d-%m-%Y"), end.strftime("%d-%m-%Y")


def _fetch_announcements_csv(period: str) -> Path:
    from_date, to_date = _period_window(period)
    session = create_nse_session(referer=NSE_URL)
    response = nse_request(
        session,
        API_URL,
        params={
            "index": "equities",
            "from_date": from_date,
            "to_date": to_date,
            "reqXbrl": "false",
        },
        referer=NSE_URL,
        timeout=(30, 180),
    )

    payload = response.json()
    if not isinstance(payload, list):
        raise RuntimeError(f"Unexpected NSE announcements response: {type(payload).__name__}")

    frame = pd.DataFrame(payload)
    if frame.empty:
        export = pd.DataFrame(
            columns=[
                "SYMBOL",
                "COMPANY NAME",
                "SUBJECT",
                "DETAILS",
                "BROADCAST DATE/TIME",
                "RECEIPT",
                "DISSEMINATION",
                "DIFFERENCE",
                "ATTACHMENT",
            ]
        )
    else:
        empty = pd.Series("", index=frame.index, dtype=object)
        export = pd.DataFrame(
            {
                "SYMBOL": frame.get("symbol", empty),
                "COMPANY NAME": frame.get("sm_name", empty),
                "SUBJECT": frame.get("desc", empty),
                "DETAILS": frame.get("attchmntText", empty),
                "BROADCAST DATE/TIME": frame.get("an_dt", empty),
                "RECEIPT": frame.get("an_dt", empty),
                "DISSEMINATION": frame.get("exchdisstime", empty),
                "DIFFERENCE": frame.get("difference", empty),
                "ATTACHMENT": frame.get("attchmntFile", empty),
            }
        )

    filename = f"CF-AN-equities-{from_date}-to-{to_date}.csv"
    download_path = DOWNLOAD_DIR / filename
    export.to_csv(download_path, index=False)
    return download_path


def scrape_nse_announcements(period: str = "1D"):
    print("=" * 80)
    print("NSE ANNOUNCEMENTS - CSV DOWNLOAD")
    print("=" * 80)

    try:
        from_date, to_date = _period_window(period)
        print("\n1. Fetching NSE announcements export...")
        cleanup_download_dir(DOWNLOAD_DIR, FILE_PATTERN)
        print(f"   Date window: {from_date} to {to_date}")
        csv_path = _fetch_announcements_csv(period)
        print(f"   ✓ Downloaded: {csv_path.name}")

        raw_copy = store_raw_download(csv_path, RAW_ANNOUNCEMENTS_DIR)
        parsed = parse_nse_announcements_csv(raw_copy)
        merged = merge_announcements_history(parsed)

        today = datetime.now().strftime("%Y%m%d")
        snapshot_path = RAW_ANNOUNCEMENTS_DIR / f"nse_announcements_{period}_{today}.csv"
        parsed.to_csv(snapshot_path, index=False)

        print(f"\n   ✓ Parsed rows: {len(parsed):,}")
        print(f"   ✓ Saved raw copy to {raw_copy}")
        print(f"   ✓ Saved normalized snapshot to {snapshot_path}")
        print(f"   ✓ Updated canonical history rows: {len(merged):,}")

        if not parsed.empty and "date" in parsed.columns:
            print(f"   ✓ Date range: {parsed['date'].min()} to {parsed['date'].max()}")

        return parsed

    except Exception as exc:  # noqa: BLE001
        print(f"\nERROR: {exc}")
        import traceback

        traceback.print_exc()
        return None


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="NSE announcements CSV scraper")
    parser.add_argument("--period", choices=["1D", "1W", "1M", "3M", "6M", "1Y"], default="1D")
    args = parser.parse_args()
    result = scrape_nse_announcements(args.period)
    raise SystemExit(0 if result is not None else 1)
