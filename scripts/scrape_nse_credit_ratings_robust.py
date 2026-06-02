#!/usr/bin/env python3
"""
NSE Credit Ratings - ROBUST SCRAPER

Handles the malformed NSE CSV format with:
- BOM (Byte Order Mark)
- Newlines in column names
- Multiple date columns
- Complex nested data structure

Usage:
    python3 scripts/scrape_nse_credit_ratings_robust.py --period 1M
    python3 scripts/scrape_nse_credit_ratings_robust.py --from-date 2020-01-01 --to-date 2026-03-15
    python3 scripts/scrape_nse_credit_ratings_robust.py --all-history --start-year 2020
"""

import sys
from pathlib import Path
from datetime import datetime
import time

import pandas as pd

# Project root
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# NSE URL
CREDIT_RATINGS_URL = "https://www.nseindia.com/companies-listing/debt-centralised-database/crd"

# Output directory
OUTPUT_DIR = PROJECT_ROOT / "data" / "raw" / "exchanges" / "nse" / "alternative" / "credit_ratings"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Downloads folder
DOWNLOADS_FOLDER = OUTPUT_DIR / "_downloads"
DOWNLOADS_FOLDER.mkdir(parents=True, exist_ok=True)
from scripts.nse_csv_scraper_common import cleanup_download_dir, download_csv_via_nse_api, store_raw_download


API_URL = "https://www.nseindia.com/api/corporate-credit-rating"
FILE_PATTERN = "*CRD*.csv"


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


def _fetch_credit_ratings_csv(period=None, from_date=None, to_date=None) -> Path:
    if from_date and to_date:
        from_date_str = pd.Timestamp(from_date).strftime("%d-%m-%Y")
        to_date_str = pd.Timestamp(to_date).strftime("%d-%m-%Y")
    else:
        from_date_str, to_date_str = _period_window(period or "1D")

    cleanup_download_dir(DOWNLOADS_FOLDER, FILE_PATTERN)
    default_filename = f"CF-CRD-{from_date_str}-to-{to_date_str}.csv"
    return download_csv_via_nse_api(
        api_url=API_URL,
        referer=CREDIT_RATINGS_URL,
        download_dir=DOWNLOADS_FOLDER,
        default_filename=default_filename,
        params={
            "from_date": from_date_str,
            "to_date": to_date_str,
            "csv": "true",
        },
    )


def parse_credit_ratings_csv(csv_path):
    """
    Parse NSE Credit Ratings CSV with robust handling of malformed format.
    
    The NSE CSV has:
    - UTF-8 BOM
    - Newlines in column names
    - 33+ columns with complex names
    - Multiple date fields
    """
    print(f"\n   Parsing {csv_path.name}...")
    
    # Read raw file to handle BOM and newlines
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        content = f.read()
    
    # Replace newlines within quoted strings (column names)
    lines = content.split('\n')
    cleaned_lines = []
    current_line = ""
    in_quotes = False
    
    for line in lines:
        quote_count = line.count('"')
        
        if in_quotes:
            current_line += " " + line
            if quote_count % 2 == 1:  # Closing quote
                cleaned_lines.append(current_line)
                current_line = ""
                in_quotes = False
        else:
            if quote_count % 2 == 1:  # Opening quote, odd number
                current_line = line
                in_quotes = True
            else:
                cleaned_lines.append(line)
    
    if current_line:
        cleaned_lines.append(current_line)
    
    # Write cleaned content
    cleaned_content = '\n'.join(cleaned_lines)
    
    # Create temp cleaned file
    cleaned_path = csv_path.with_suffix('.cleaned.csv')
    with open(cleaned_path, 'w', encoding='utf-8') as f:
        f.write(cleaned_content)
    
    # Read cleaned CSV
    try:
        df = pd.read_csv(cleaned_path, engine='python', on_bad_lines='warn')
        print(f"   ✓ Loaded {len(df)} rows")
    except Exception as e:
        print(f"   ⚠ Error reading CSV: {e}")
        # Try alternative parsing
        df = pd.read_csv(cleaned_path, skiprows=0, header=0, on_bad_lines='skip')
        print(f"   ✓ Loaded {len(df)} rows (alternative method)")
    
    # Clean up temp file
    try:
        cleaned_path.unlink()
    except Exception:
        pass
    
    print(f"   Columns found: {len(df.columns)}")
    
    # Map columns - handle various possible names
    column_mapping = {
        'date': None,
        'isin': None,  # Use ISIN as identifier (debt instruments)
        'company_name': None,
        'agency': None,
        'rating': None,
        'rating_action': None,
        'outlook': None,
    }
    
    # First pass: collect all candidate columns
    date_candidates = []
    isin_candidates = []
    company_candidates = []
    agency_candidates = []
    rating_candidates = []
    action_candidates = []
    outlook_candidates = []
    
    for col in df.columns:
        col_clean = str(col).strip().upper().replace('\n', ' ').replace('  ', ' ')
        
        # Date candidates (prioritize DATE OF CREDIT RATING)
        if 'DATE OF CREDIT RATING' in col_clean and 'EARLIER' not in col_clean and 'VERIFICATION' not in col_clean:
            date_candidates.insert(0, col)  # Highest priority
        elif 'DATE' in col_clean and 'EARLIER' not in col_clean and 'VERIFICATION' not in col_clean:
            date_candidates.append(col)
        
        # ISIN
        if 'ISIN' in col_clean and 'EARLIER' not in col_clean:
            isin_candidates.append(col)
        
        # Company Name
        if 'COMPANY NAME' in col_clean:
            company_candidates.append(col)
        
        # Agency
        if 'AGENCY' in col_clean and 'EARLIER' not in col_clean and 'VERIFICATION' not in col_clean:
            agency_candidates.append(col)
        
        # Rating
        if col_clean == 'CREDIT RATING' or (col_clean == 'RATING' and 'ACTION' not in col_clean and 'OUTLOOK' not in col_clean):
            rating_candidates.append(col)
        
        # Rating Action
        if 'RATING ACTION' in col_clean and 'EARLIER' not in col_clean and 'SPECIFY' not in col_clean:
            action_candidates.append(col)
        
        # Outlook
        if col_clean == 'OUTLOOK':
            outlook_candidates.append(col)
    
    # Select best candidates
    column_mapping = {
        'date': date_candidates[0] if date_candidates else None,
        'isin': isin_candidates[0] if isin_candidates else None,
        'company_name': company_candidates[0] if company_candidates else None,
        'agency': agency_candidates[0] if agency_candidates else None,
        'rating': rating_candidates[0] if rating_candidates else None,
        'rating_action': action_candidates[0] if action_candidates else None,
        'outlook': outlook_candidates[0] if outlook_candidates else None,
    }
    
    # Rename columns
    rename_map = {v: k for k, v in column_mapping.items() if v is not None}
    df = df.rename(columns=rename_map)
    
    print(f"   Mapped columns: {list(rename_map.values())}")
    
    # Convert date - use dd-mm-yyyy format
    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'], format='%d-%m-%Y', errors='coerce')
    
    # Add instrument type indicator (debt instrument, not equity)
    df['instrument_type'] = 'Debt'
    df['source'] = 'NSE_CREDIT_RATINGS'
    
    # Sort by date
    if 'date' in df.columns:
        df = df.sort_values('date', ascending=False)
    
    return df


def scrape_credit_ratings(period=None, from_date=None, to_date=None):
    """Scrape NSE credit ratings."""
    print("=" * 80)
    print("NSE CREDIT RATINGS - ROBUST SCRAPER")
    print("=" * 80)
    
    try:
        if from_date and to_date:
            print(f"\n1. Fetching custom date range: {from_date.date()} to {to_date.date()}")
            period = None
        else:
            selected_period = period or "1D"
            print(f"\n1. Fetching time period: {selected_period}...")
            period = selected_period
        csv_path = _fetch_credit_ratings_csv(period=period, from_date=from_date, to_date=to_date)
        
        print(f"   ✓ Downloaded: {csv_path.name}")
        raw_copy = store_raw_download(csv_path, OUTPUT_DIR)
        
        # Parse CSV
        df = parse_credit_ratings_csv(raw_copy)
        
        if df is None:
            print("   ✗ No data parsed")
            return None

        if len(df) == 0:
            print("   ✓ No credit rating rows for requested window")
            print("   ✓ Treating valid empty NSE response as successful no-op")
            return df
        
        # Save
        today = datetime.now().strftime("%Y%m%d")
        if period:
            output_path = OUTPUT_DIR / f"nse_credit_ratings_{period}_{today}.csv"
        elif from_date:
            output_path = OUTPUT_DIR / f"nse_credit_ratings_{from_date.strftime('%Y%m%d')}_{to_date.strftime('%Y%m%d')}.csv"
        else:
            output_path = OUTPUT_DIR / f"nse_credit_ratings_{today}.csv"
        
        df.to_csv(output_path, index=False)
        print(f"\n   ✓ Saved to {output_path}")
        print(f"   ✓ Saved raw copy to {raw_copy}")
        
        # Also save to main file
        main_path = OUTPUT_DIR / "nse_credit_ratings_all.csv"
        df.to_csv(main_path, index=False)
        print(f"   ✓ Saved to {main_path}")
        
        # Statistics
        print(f"\n{'=' * 60}")
        print("STATISTICS")
        print(f"{'=' * 60}")
        print(f"Total rows: {len(df)}")
        
        if 'isin' in df.columns:
            print(f"Unique ISINs: {df['isin'].nunique()}")
        
        if 'company_name' in df.columns:
            print(f"Unique companies: {df['company_name'].nunique()}")
        
        if 'date' in df.columns:
            print(f"Date range: {df['date'].min()} to {df['date'].max()}")
        
        if 'agency' in df.columns and df['agency'].notna().any():
            print(f"\nTop agencies:")
            print(df['agency'].value_counts().head(10))
        
        if 'rating_action' in df.columns and df['rating_action'].notna().any():
            print(f"\nRating actions:")
            print(df['rating_action'].value_counts())
        
        if 'rating' in df.columns and df['rating'].notna().any():
            print(f"\nRating distribution:")
            print(df['rating'].value_counts().head(15))
        
        # Sample
        print(f"\n{'=' * 60}")
        print("SAMPLE DATA")
        print(f"{'=' * 60}")
        sample_cols = ['date', 'company_name', 'isin', 'agency', 'rating', 'rating_action', 'outlook']
        available_cols = [c for c in sample_cols if c in df.columns]
        if available_cols:
            print(df[available_cols].head(10).to_string())
        
        return df
        
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return None


def download_all_history(start_year=2020):
    """Download complete historical data year by year."""
    print("=" * 80)
    print("DOWNLOADING COMPLETE HISTORICAL CREDIT RATINGS")
    print("=" * 80)
    
    end_date = datetime.now()
    all_data = []
    
    for year in range(start_year, end_date.year + 1):
        from_dt = datetime(year, 1, 1)
        to_dt = datetime(year, 12, 31) if year < end_date.year else end_date
        
        print(f"\n{'=' * 60}")
        print(f"DOWNLOADING: {from_dt.date()} to {to_dt.date()}")
        print(f"{'=' * 60}")
        
        df = scrape_credit_ratings(from_date=from_dt, to_date=to_dt)
        
        if df is not None and len(df) > 0:
            all_data.append(df)
            time.sleep(3)
    
    if all_data:
        combined = pd.concat(all_data, ignore_index=True)
        combined = combined.drop_duplicates(subset=['date', 'symbol', 'agency'], keep='last')
        combined = combined.sort_values('date', ascending=False)
        
        today = datetime.now().strftime("%Y%m%d")
        output_path = OUTPUT_DIR / f"nse_credit_ratings_historical_{start_year}_{today}.csv"
        combined.to_csv(output_path, index=False)
        print(f"\n✓ Complete historical data saved: {output_path}")
        print(f"  Total rows: {len(combined)}")
        
        return combined
    
    return None


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="NSE Credit Ratings Robust Scraper")
    parser.add_argument("--period", choices=["1D", "1W", "1M", "3M", "6M", "1Y"], default=None)
    parser.add_argument("--from-date", type=str, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--to-date", type=str, help="End date (YYYY-MM-DD)")
    parser.add_argument("--all-history", action="store_true", help="Download all historical data")
    parser.add_argument("--start-year", type=int, default=2020, help="Start year for historical download")
    
    args = parser.parse_args()

    if args.all_history:
        result = download_all_history(start_year=args.start_year)
    else:
        from_date = datetime.strptime(args.from_date, "%Y-%m-%d") if args.from_date else None
        to_date = datetime.strptime(args.to_date, "%Y-%m-%d") if args.to_date else None

        result = scrape_credit_ratings(
            period=args.period,
            from_date=from_date,
            to_date=to_date
        )

    raise SystemExit(0 if result is not None else 1)
