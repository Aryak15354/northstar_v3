#!/usr/bin/env python3
"""
NSE Bulk Deals - SIMPLE CSV DOWNLOAD

Use the NSE historical bulk/block API directly and fall back only if needed.
"""

import sys
from pathlib import Path
from datetime import datetime

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.nse_csv_scraper_common import cleanup_download_dir, download_csv_via_nse_api, store_raw_download

# Output directory
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "raw" / "exchanges" / "nse" / "alternative" / "bulk_deals"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
DOWNLOADS_FOLDER = OUTPUT_DIR / "_downloads"
DOWNLOADS_FOLDER.mkdir(parents=True, exist_ok=True)
NSE_URL = "https://www.nseindia.com/report-detail/display-bulk-and-block-deals"
API_URL = "https://www.nseindia.com/api/historicalOR/bulk-block-short-deals"
FILE_PATTERN = "*Bulk*.csv"


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


def _fetch_bulk_deals_csv(period: str) -> Path:
    from_date, to_date = _period_window(period)
    default_filename = f"CF-Bulk-Deals-{from_date}-to-{to_date}.csv"
    cleanup_download_dir(DOWNLOADS_FOLDER, FILE_PATTERN)
    return download_csv_via_nse_api(
        api_url=API_URL,
        referer=NSE_URL,
        download_dir=DOWNLOADS_FOLDER,
        default_filename=default_filename,
        params={
            "optionType": "bulk_deals",
            "from": from_date,
            "to": to_date,
            "csv": "true",
        },
    )


def scrape_nse_bulk_deals(period="1D"):
    """Scrape NSE bulk deals."""
    print("=" * 80)
    print("NSE BULK DEALS - SIMPLE CSV DOWNLOAD")
    print("=" * 80)

    try:
        from_date, to_date = _period_window(period)
        print("\n1. Fetching NSE bulk deals CSV...")
        print(f"   Date window: {from_date} to {to_date}")
        csv_path = _fetch_bulk_deals_csv(period)
        
        print(f"   ✓ Downloaded: {csv_path.name}")
        raw_copy = store_raw_download(csv_path, OUTPUT_DIR)
        
        # Parse CSV
        print("\n2. Parsing CSV...")
        df = pd.read_csv(raw_copy)
        print(f"   ✓ Loaded {len(df)} rows")
        print(f"   Columns: {df.columns.tolist()}")
        
        # Strip whitespace from column names
        df.columns = df.columns.str.strip()
        
        # Standardize columns
        column_map = {
            "Date": "date",
            "Symbol": "symbol",
            "Security Name": "company_name",
            "Client Name": "client_name",
            "Buy / Sell": "deal_type",
            "Quantity Traded": "quantity",
            "Trade Price / Wght. Avg. Price": "price",
            "Remarks": "remarks",
        }
        df = df.rename(columns=column_map)
        
        # Convert types
        df["date"] = pd.to_datetime(df["date"], format="%d-%b-%Y", errors="coerce")
        df["quantity"] = pd.to_numeric(
            df["quantity"].astype(str).str.replace(",", ""), 
            errors="coerce"
        )
        df["price"] = pd.to_numeric(df["price"], errors="coerce")
        
        # Add NSE ticker
        df["nse_ticker"] = df["symbol"].apply(
            lambda x: f"{x}.NS" if pd.notna(x) and not str(x).endswith(".NS") else x
        )
        
        df["source"] = "NSE_DOWNLOAD"
        
        # Sort
        df = df.sort_values("date", ascending=False)
        
        # Save
        today = datetime.now().strftime("%Y%m%d")
        output_path = OUTPUT_DIR / f"nse_bulk_deals_{period}_{today}.csv"
        df.to_csv(output_path, index=False)
        print(f"\n   ✓ Saved to {output_path}")
        print(f"   ✓ Saved raw copy to {raw_copy}")
        
        # Also save to main file
        main_path = OUTPUT_DIR / "nse_bulk_deals_all.csv"
        df.to_csv(main_path, index=False)
        print(f"   ✓ Saved to {main_path}")
        
        # Stats
        print(f"\n{'=' * 60}")
        print("STATISTICS")
        print(f"{'=' * 60}")
        print(f"Total rows: {len(df)}")
        print(f"Unique symbols: {df['symbol'].nunique()}")
        print(f"Date range: {df['date'].min()} to {df['date'].max()}")
        
        if "deal_type" in df.columns:
            print(f"\nDeal types:")
            print(df["deal_type"].value_counts())
        
        # Sample
        print(f"\n{'=' * 60}")
        print("SAMPLE DATA")
        print(f"{'=' * 60}")
        print(df[["date", "symbol", "company_name", "deal_type", "quantity", "price"]].head(10).to_string())
        
        return df
        
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="NSE Bulk Deals Simple Scraper")
    parser.add_argument("--period", choices=["1D", "1W", "1M", "3M", "6M", "1Y"], default="1D")
    args = parser.parse_args()

    result = scrape_nse_bulk_deals(args.period)
    raise SystemExit(0 if result is not None else 1)
