#!/usr/bin/env python3
"""
NSE Historical Data - LOOP METHOD

Uses the working scrape_nse_complete.py scraper in a loop to build historical data.
More reliable than trying to automate the Custom date picker.

Usage:
    python3 scripts/build_nse_historical_loop.py --type bulk-deals --start-year 2010
    python3 scripts/build_nse_historical_loop.py --type credit-ratings --start-year 2015
"""

import subprocess
import sys
import time
from pathlib import Path
from datetime import datetime

# Project root
PROJECT_ROOT = Path(__file__).parent.parent
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "scrape_nse_complete.py"


def download_year_loop(data_type, year):
    """Download a specific year by running the scraper multiple times."""
    print(f"\n{'=' * 60}")
    print(f"DOWNLOADING YEAR: {year}")
    print(f"{'=' * 60}")
    
    # We'll download in chunks using different periods
    # Since 1Y gives us ~1 year of data, we use that
    
    cmd = [
        sys.executable,
        str(SCRIPT_PATH),
        "--type", data_type,
        "--period", "1Y"
    ]
    
    print(f"   Running: {' '.join(cmd)}")
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode == 0:
        print(f"   ✓ Download complete")
        return True
    else:
        print(f"   ✗ Error: {result.stderr[:200] if result.stderr else 'Unknown error'}")
        return False


def combine_downloads(data_type, output_name):
    """Combine all downloaded files into one."""
    print(f"\n{'=' * 60}")
    print("COMBINING DOWNLOADS")
    print(f"{'=' * 60}")
    
    if data_type == "bulk-deals":
        raw_dir = PROJECT_ROOT / "data" / "raw" / "exchanges" / "nse" / "alternative" / "bulk_deals"
    else:
        raw_dir = PROJECT_ROOT / "data" / "raw" / "exchanges" / "nse" / "alternative" / "credit_ratings"
    
    processed_dir = PROJECT_ROOT / "data" / "processed" / "alternative"
    
    # Find all CSV files
    csv_files = list(raw_dir.glob("*.csv"))
    
    if not csv_files:
        print("   ⚠ No files to combine!")
        return None
    
    print(f"   Found {len(csv_files)} files")
    
    all_data = []
    for f in csv_files:
        try:
            if data_type == "bulk-deals":
                df = pd.read_csv(f)
            else:
                df = pd.read_csv(f, encoding='utf-8-sig', engine='python', on_bad_lines='warn')
            
            all_data.append(df)
            print(f"   ✓ {f.name}: {len(df):,} rows")
        except Exception as e:
            print(f"   ⚠ {f.name}: Error - {e}")
    
    if not all_data:
        return None
    
    # Combine
    combined = pd.concat(all_data, ignore_index=True)
    print(f"\n   Combined: {len(combined):,} rows")
    
    # Remove duplicates
    before = len(combined)
    if data_type == "bulk-deals":
        combined = combined.drop_duplicates(subset=['date', 'symbol', 'client_name'], keep='last')
    else:
        combined = combined.drop_duplicates(subset=['date', 'isin', 'agency'], keep='last')
    
    print(f"   After dedup: {len(combined):,} rows (removed {before - len(combined):,})")
    
    # Save
    output_file = processed_dir / f"{output_name}.csv"
    combined.to_csv(output_file, index=False)
    print(f"\n   ✓ Saved to {output_file.name}")
    
    return combined


def build_historical_loop(data_type, start_year=2010, iterations=3):
    """Build historical data by running scraper multiple times."""
    import pandas as pd
    
    print("=" * 80)
    print(f"NSE HISTORICAL DATA BUILDER - LOOP METHOD")
    print(f"Data type: {data_type}")
    print(f"Starting year: {start_year}")
    print(f"Iterations: {iterations}")
    print("=" * 80)
    
    end_year = datetime.now().year
    years_needed = end_year - start_year + 1
    
    print(f"\nTarget: {start_year} to {end_year} ({years_needed} years)")
    print(f"Each 1Y download gets ~1 year of data")
    print(f"Running {iterations} iterations...")
    
    for i in range(iterations):
        print(f"\n{'=' * 60}")
        print(f"ITERATION {i + 1}/{iterations}")
        print(f"{'=' * 60}")
        
        success = download_year_loop(data_type, start_year + i)
        
        if success:
            # Wait between downloads
            wait_time = 10
            print(f"   Waiting {wait_time}s...")
            time.sleep(wait_time)
        else:
            print(f"   ⚠ Failed, retrying in 30s...")
            time.sleep(30)
            download_year_loop(data_type, start_year + i)
            time.sleep(10)
    
    # Combine all downloads
    output_name = f"{data_type}_nse_historical_{start_year}_{end_year}"
    combine_downloads(data_type, output_name)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="NSE Historical Data - Loop Method")
    parser.add_argument("--type", choices=["bulk-deals", "credit-ratings"], required=True)
    parser.add_argument("--start-year", type=int, default=2010)
    parser.add_argument("--iterations", type=int, default=3, help="Number of 1Y downloads")
    
    args = parser.parse_args()
    
    build_historical_loop(
        args.type,
        start_year=args.start_year,
        iterations=args.iterations
    )
