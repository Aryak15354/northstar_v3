#!/usr/bin/env python3
"""Download NSE promoter-pledge snapshots and merge them into canonical history."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.nse_corporate_filings_processors import (  # noqa: E402
    RAW_PLEDGE_DIR,
    merge_promoter_pledge_history,
    parse_nse_promoter_pledge_csv,
)
from scripts.nse_csv_scraper_common import (  # noqa: E402
    cleanup_download_dir,
    create_nse_session,
    nse_request,
    store_raw_download,
)


NSE_URL = "https://www.nseindia.com/companies-listing/corporate-filings-pledged-data"
API_URL = "https://www.nseindia.com/api/corporate-pledgedata"
DOWNLOAD_DIR = RAW_PLEDGE_DIR / "_downloads"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
FILE_PATTERN = "*Pledged-Data*.csv"


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


def _snapshot_filename() -> str:
    return f"CF-SAST-Pledged-Data-{pd.Timestamp.today().strftime('%d-%b-%Y')}.csv"


def _fetch_pledge_csv() -> Path:
    session = create_nse_session(referer=NSE_URL)
    response = nse_request(
        session,
        API_URL,
        params={"index": "equities"},
        referer=NSE_URL,
        timeout=(30, 120),
    )

    payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError(f"Unexpected NSE pledge response: {type(payload).__name__}")

    records = payload.get("data", [])
    frame = pd.DataFrame(records)
    if frame.empty:
        export = pd.DataFrame(
            columns=[
                "NAME OF COMPANY",
                "TOTAL NO. OF ISSUED SHARES A+B+C",
                "TOTAL PROMOTER HOLDING NO. OF SHARES (A)",
                "TOTAL PROMOTER HOLDING % A /(A+B+C)",
                "TOTAL PUBLIC HOLDING B",
                "PROMOTER SHARES ENCUMBERED AS OF LAST QUARTER NO. OF SHARES (X)",
                "PROMOTER SHARES ENCUMBERED AS OF LAST QUARTER % OF PROMOTER SHARES (X/A)",
                "PROMOTER SHARES ENCUMBERED AS OF LAST QUARTER % OF TOTAL SHARES [X/(A+B+C)]",
                "PROMOTER SHARES ENCUMBERED AS OF LAST QUARTER VALUES(RS.CR.)=NO. OF SHARES ENCUMBERED [X] * LAST AVAILABLE CLOSING PRICE OF THE SCRIP",
                "DISCLOSURE MADE BY PROMOTERS",
                "NO. OF SHARES PLEDGED IN THE DEPOSITORY SYSTEM NO. OF SHARES PLEDGED",
                "NO. OF SHARES PLEDGED IN THE DEPOSITORY SYSTEM TOTAL NO. OF DEMAT SHARES",
                "(%) PLEDGE / DEMAT",
                "Values(Rs. Cr.)",
                "BROADCAST DATE",
            ]
        )
    else:
        empty = pd.Series("", index=frame.index, dtype=object)
        export = pd.DataFrame(
            {
                "NAME OF COMPANY": frame.get("comName", empty),
                "TOTAL NO. OF ISSUED SHARES A+B+C": frame.get("totIssuedShares", empty),
                "TOTAL PROMOTER HOLDING NO. OF SHARES (A)": frame.get("totPromoterHolding", empty),
                "TOTAL PROMOTER HOLDING % A /(A+B+C)": frame.get("percPromoterHolding", empty),
                "TOTAL PUBLIC HOLDING B": frame.get("totPublicHolding", empty),
                "PROMOTER SHARES ENCUMBERED AS OF LAST QUARTER NO. OF SHARES (X)": frame.get("totPromoterShares", empty),
                "PROMOTER SHARES ENCUMBERED AS OF LAST QUARTER % OF PROMOTER SHARES (X/A)": frame.get("percPromoterShares", empty),
                "PROMOTER SHARES ENCUMBERED AS OF LAST QUARTER % OF TOTAL SHARES [X/(A+B+C)]": frame.get("percTotShares", empty),
                "PROMOTER SHARES ENCUMBERED AS OF LAST QUARTER VALUES(RS.CR.)=NO. OF SHARES ENCUMBERED [X] * LAST AVAILABLE CLOSING PRICE OF THE SCRIP": frame.get("noOfPledgeShare", empty),
                "DISCLOSURE MADE BY PROMOTERS": frame.get("broadcastDt", empty),
                "NO. OF SHARES PLEDGED IN THE DEPOSITORY SYSTEM NO. OF SHARES PLEDGED": frame.get("numSharesPledged", empty),
                "NO. OF SHARES PLEDGED IN THE DEPOSITORY SYSTEM TOTAL NO. OF DEMAT SHARES": frame.get("totDematShares", empty),
                "(%) PLEDGE / DEMAT": frame.get("percSharesPledged", empty),
                "Values(Rs. Cr.)": frame.get("noOfSecPledgeShare", empty),
                "BROADCAST DATE": frame.get("broadcastDt", empty),
            }
        )

    download_path = DOWNLOAD_DIR / _snapshot_filename()
    export.to_csv(download_path, index=False)
    return download_path


def scrape_nse_promoter_pledge(period: str = "1D"):
    print("=" * 80)
    print("NSE PROMOTER PLEDGE - CSV DOWNLOAD")
    print("=" * 80)

    try:
        from_date, to_date = _period_window(period)
        print("\n1. Fetching NSE promoter pledge snapshot...")
        cleanup_download_dir(DOWNLOAD_DIR, FILE_PATTERN)
        print(f"   Requested window: {from_date} to {to_date}")
        print("   ⚠ NSE currently serves the same full pledge snapshot for 1D/1W/1M/1Y requests.")
        csv_path = _fetch_pledge_csv()
        print(f"   ✓ Downloaded: {csv_path.name}")

        raw_copy = store_raw_download(csv_path, RAW_PLEDGE_DIR)
        parsed = parse_nse_promoter_pledge_csv(raw_copy)
        merged = merge_promoter_pledge_history(parsed)

        today = datetime.now().strftime("%Y%m%d")
        snapshot_path = RAW_PLEDGE_DIR / f"nse_promoter_pledge_{period}_{today}.csv"
        parsed.to_csv(snapshot_path, index=False)

        print(f"\n   ✓ Parsed rows: {len(parsed):,}")
        matched = int(parsed["nse_ticker"].astype(str).str.len().gt(0).sum()) if not parsed.empty else 0
        print(f"   ✓ Ticker-mapped rows: {matched:,}")
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

    parser = argparse.ArgumentParser(description="NSE promoter pledge snapshot scraper")
    parser.add_argument("--period", choices=["1D", "1W", "1M", "3M", "6M", "1Y"], default="1D")
    args = parser.parse_args()
    result = scrape_nse_promoter_pledge(args.period)
    raise SystemExit(0 if result is not None else 1)
