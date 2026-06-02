#!/usr/bin/env python3
"""
NSE Historical Data Builder - SIMPLE & ROBUST

Downloads historical data year by year using the working 1Y button.
No complex custom date picking - just reliable year-by-year downloads.

Usage:
    python3 scripts/build_nse_historical_simple.py --type bulk-deals --start-year 2010
    python3 scripts/build_nse_historical_simple.py --type credit-ratings --start-year 2015
"""

import os
import sys
import time
from pathlib import Path
from datetime import datetime

import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# Project root
PROJECT_ROOT = Path(__file__).parent.parent

# NSE URLs
BULK_DEALS_URL = "https://www.nseindia.com/report-detail/display-bulk-and-block-deals"
CREDIT_RATINGS_URL = "https://www.nseindia.com/companies-listing/debt-centralised-database/crd"

# Output directories
BULK_DEALS_DIR = PROJECT_ROOT / "data" / "raw" / "exchanges" / "nse" / "alternative" / "bulk_deals"
CREDIT_RATINGS_DIR = PROJECT_ROOT / "data" / "raw" / "exchanges" / "nse" / "alternative" / "credit_ratings"
BULK_DEALS_DIR.mkdir(parents=True, exist_ok=True)
CREDIT_RATINGS_DIR.mkdir(parents=True, exist_ok=True)

DOWNLOADS_FOLDER = Path.home() / "Downloads"


def create_driver():
    """Create Chrome WebDriver."""
    chrome_options = Options()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
    
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=chrome_options
    )
    return driver


def find_and_click(driver, text_options):
    """Find and click button by text."""
    buttons = driver.find_elements(By.TAG_NAME, "button")
    for btn in buttons:
        try:
            btn_text = btn.text.strip().upper()
            for text in text_options:
                if text.upper() in btn_text:
                    driver.execute_script("arguments[0].click();", btn)
                    print(f"   ✓ Clicked: {btn_text}")
                    return True
        except Exception:
            continue
    
    links = driver.find_elements(By.TAG_NAME, "a")
    for link in links:
        try:
            link_text = link.text.strip().upper()
            for text in text_options:
                if text.upper() in link_text:
                    driver.execute_script("arguments[0].click();", link)
                    print(f"   ✓ Clicked: {link_text}")
                    return True
        except Exception:
            continue
    
    return False


def wait_for_csv_download(timeout=40, file_pattern="*Bulk*.csv"):
    """Wait for CSV download."""
    print(f"   Waiting for download...")
    
    initial_csvs = set(DOWNLOADS_FOLDER.glob(file_pattern))
    
    start = time.time()
    while time.time() - start < timeout:
        current_csvs = set(DOWNLOADS_FOLDER.glob(file_pattern))
        new_csvs = current_csvs - initial_csvs
        
        if new_csvs:
            time.sleep(2)
            return list(new_csvs)[0]
        
        if current_csvs:
            latest = max(current_csvs, key=lambda p: p.stat().st_mtime)
            if time.time() - latest.stat().st_mtime < 30:
                return latest
        
        time.sleep(1)
    
    all_csvs = list(DOWNLOADS_FOLDER.glob(file_pattern))
    if all_csvs:
        return max(all_csvs, key=lambda p: p.stat().st_mtime)
    
    return None


def download_year(data_type, year):
    """Download data for a specific year using 1Y button."""
    print(f"\n{'=' * 60}")
    print(f"DOWNLOADING YEAR: {year}")
    print(f"{'=' * 60}")
    
    if data_type == "bulk_deals":
        url = BULK_DEALS_URL
        file_pattern = "*Bulk*.csv"
    else:
        url = CREDIT_RATINGS_URL
        file_pattern = "*CRD*.csv"
    
    driver = None
    try:
        # Open page
        driver = create_driver()
        driver.get(url)
        driver.maximize_window()
        
        # Wait for page
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.TAG_NAME, "table"))
        )
        time.sleep(3)
        
        # Click 1Y button
        print(f"   Clicking 1Y button...")
        if not find_and_click(driver, ["1Y", "1 YEAR", "ONE YEAR"]):
            print("   ⚠ Could not click 1Y, using default data")
        
        time.sleep(5)  # Wait for data to load
        
        # Download CSV
        print("   Clicking Download CSV...")
        if not find_and_click(driver, ["DOWNLOAD", "CSV", "DOWNLOAD (.CSV)"]):
            print("   ⚠ Could not find Download button")
            return None
        
        # Wait for download
        csv_path = wait_for_csv_download(timeout=40, file_pattern=file_pattern)
        
        if not csv_path:
            print("   ✗ Download timed out")
            return None
        
        print(f"   ✓ Downloaded: {csv_path.name}")
        
        # Move to year-specific file
        if data_type == "bulk_deals":
            output_dir = BULK_DEALS_DIR
        else:
            output_dir = CREDIT_RATINGS_DIR
        
        year_file = output_dir / f"nse_{data_type}_{year}.csv"
        
        # Copy file
        import shutil
        shutil.copy(csv_path, year_file)
        print(f"   ✓ Saved to {year_file.name}")
        
        return year_file
        
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return None
        
    finally:
        if driver:
            driver.quit()


def combine_all_years(data_type, start_year, end_year):
    """Combine all year files into one master file."""
    print(f"\n{'=' * 60}")
    print("COMBINING ALL YEARS")
    print(f"{'=' * 60}")
    
    if data_type == "bulk_deals":
        output_dir = BULK_DEALS_DIR
        processed_dir = PROJECT_ROOT / "data" / "processed" / "alternative"
    else:
        output_dir = CREDIT_RATINGS_DIR
        processed_dir = PROJECT_ROOT / "data" / "processed" / "alternative"
    
    all_data = []
    
    for year in range(start_year, end_year + 1):
        year_file = output_dir / f"nse_{data_type}_{year}.csv"
        if year_file.exists():
            try:
                if data_type == "bulk_deals":
                    df = pd.read_csv(year_file)
                else:
                    df = pd.read_csv(year_file, encoding='utf-8-sig', engine='python', on_bad_lines='warn')
                
                all_data.append(df)
                print(f"   ✓ Year {year}: {len(df):,} rows")
            except Exception as e:
                print(f"   ⚠ Year {year}: Error - {e}")
    
    if not all_data:
        print("   ⚠ No data to combine!")
        return None
    
    # Combine
    combined = pd.concat(all_data, ignore_index=True)
    print(f"\n   Combined: {len(combined):,} rows")
    
    # Remove duplicates
    before = len(combined)
    if data_type == "bulk_deals":
        combined = combined.drop_duplicates(subset=['date', 'symbol', 'client_name'], keep='last')
    else:
        combined = combined.drop_duplicates(subset=['date', 'isin', 'agency'], keep='last')
    
    print(f"   After deduplication: {len(combined):,} rows (removed {before - len(combined):,} duplicates)")
    
    # Save to processed
    output_file = processed_dir / f"{data_type}_nse_historical_{start_year}_{end_year}.csv"
    combined.to_csv(output_file, index=False)
    print(f"\n   ✓ Saved to {output_file.name}")
    
    # Also save as main file
    main_file = processed_dir / f"{data_type}_nse_all.csv"
    combined.to_csv(main_file, index=False)
    print(f"   ✓ Saved to {main_file.name}")
    
    return combined


def build_historical(data_type, start_year=2010, end_year=None):
    """Build historical database year by year."""
    print("=" * 80)
    print(f"NSE HISTORICAL DATA BUILDER - {data_type.upper()}")
    print("=" * 80)
    
    if end_year is None:
        end_year = datetime.now().year
    
    print(f"\nDownloading from {start_year} to {end_year}...")
    print(f"Total years: {end_year - start_year + 1}")
    
    # Download each year
    for year in range(start_year, end_year + 1):
        # Check if already downloaded
        if data_type == "bulk_deals":
            output_dir = BULK_DEALS_DIR
        else:
            output_dir = CREDIT_RATINGS_DIR
        
        year_file = output_dir / f"nse_{data_type}_{year}.csv"
        
        if year_file.exists() and year_file.stat().st_size > 1000:
            print(f"\n   ⊘ Year {year}: Already exists, skipping")
            continue
        
        csv_path = download_year(data_type, year)
        
        if csv_path:
            # Wait between downloads
            wait_time = 5
            print(f"   Waiting {wait_time}s before next download...")
            time.sleep(wait_time)
        else:
            print(f"   ⚠ Failed to download year {year}")
            # Retry once
            print(f"   Retrying year {year}...")
            time.sleep(10)
            download_year(data_type, year)
            time.sleep(5)
    
    # Combine all years
    combine_all_years(data_type, start_year, end_year)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="NSE Historical Data Builder - Simple")
    parser.add_argument("--type", choices=["bulk-deals", "credit-ratings"], required=True)
    parser.add_argument("--start-year", type=int, default=2010, help="Start year")
    parser.add_argument("--end-year", type=int, help="End year (default: current year)")
    
    args = parser.parse_args()
    
    end_year = args.end_year or datetime.now().year
    
    build_historical(
        args.type.replace("-", "_"),
        start_year=args.start_year,
        end_year=end_year
    )
