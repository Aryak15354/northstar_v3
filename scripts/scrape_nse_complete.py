#!/usr/bin/env python3
"""
NSE Bulk Deals & Credit Ratings - COMPLETE HISTORICAL SCRAPER

Features:
1. Pre-set periods: 1D, 1W, 1M, 3M, 6M, 1Y
2. Custom date range for historical data
3. Download CSV and parse automatically
4. Build complete historical database

Usage:
    # Pre-set periods
    python3 scripts/scrape_nse_complete.py --type bulk-deals --period 1W
    python3 scripts/scrape_nse_complete.py --type credit-ratings --period 1M
    
    # Custom date range (for historical database)
    python3 scripts/scrape_nse_complete.py --type bulk-deals --from-date 2020-01-01 --to-date 2026-03-15
    python3 scripts/scrape_nse_complete.py --type credit-ratings --from-date 2020-01-01 --to-date 2026-03-15
    
    # Download all historical data (chunks by year)
    python3 scripts/scrape_nse_complete.py --type bulk-deals --all-history
    python3 scripts/scrape_nse_complete.py --type credit-ratings --all-history
"""

import os
import sys
import time
import glob
from pathlib import Path
from datetime import datetime, timedelta

import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
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

# Downloads folder
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


def find_and_click_button(driver, text_options):
    """Find and click a button by text."""
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
    
    # Try links
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


def set_custom_date_range(driver, from_date, to_date):
    """Set custom date range using date inputs."""
    print(f"   Setting date range: {from_date} to {to_date}")
    
    # Find date input fields
    date_inputs = driver.find_elements(By.TAG_NAME, "input")
    from_input = None
    to_input = None
    
    for inp in date_inputs:
        try:
            inp_type = inp.get_attribute("type")
            if inp_type == "date":
                inp_id = inp.get_attribute("id") or ""
                if "from" in inp_id.lower() or "start" in inp_id.lower():
                    from_input = inp
                elif "to" in inp_id.lower() or "end" in inp_id.lower():
                    to_input = inp
        except Exception:
            continue
    
    # Try alternative selectors
    if not from_input or not to_input:
        # Look for inputs near "From" or "To" labels
        all_elements = driver.find_elements(By.TAG_NAME, "*")
        for elem in all_elements:
            try:
                text = elem.text.strip().upper()
                if "FROM" in text or "START" in text:
                    # Find next input
                    next_input = elem.find_element(By.XPATH, ".//following::input[1]")
                    if next_input:
                        from_input = next_input
                elif "TO" in text or "END" in text:
                    next_input = elem.find_element(By.XPATH, ".//following::input[1]")
                    if next_input:
                        to_input = next_input
            except Exception:
                continue
    
    if from_input and to_input:
        try:
            # Clear and set dates
            from_input.clear()
            from_input.send_keys(from_date.strftime("%Y-%m-%d"))
            time.sleep(0.5)
            
            to_input.clear()
            to_input.send_keys(to_date.strftime("%Y-%m-%d"))
            time.sleep(0.5)
            
            print(f"   ✓ Date range set")
            return True
        except Exception as e:
            print(f"   ✗ Error setting dates: {e}")
            return False
    else:
        print("   ⚠ Could not find date inputs")
        return False


def wait_for_csv_download(timeout=30, file_pattern="*Bulk*.csv"):
    """Wait for CSV download to complete."""
    print(f"   Waiting for CSV download...")
    
    initial_csvs = set(DOWNLOADS_FOLDER.glob(file_pattern))
    
    start = time.time()
    while time.time() - start < timeout:
        current_csvs = set(DOWNLOADS_FOLDER.glob(file_pattern))
        new_csvs = current_csvs - initial_csvs
        
        if new_csvs:
            time.sleep(2)
            return list(new_csvs)[0]
        
        # Fallback: use most recent
        if current_csvs:
            latest = max(current_csvs, key=lambda p: p.stat().st_mtime)
            if time.time() - latest.stat().st_mtime < 30:
                return latest
        
        time.sleep(1)
    
    # Final fallback
    all_csvs = list(DOWNLOADS_FOLDER.glob(file_pattern))
    if all_csvs:
        return max(all_csvs, key=lambda p: p.stat().st_mtime)
    
    return None


def parse_csv(csv_path, data_type):
    """Parse downloaded CSV file."""
    print(f"\n   Parsing {csv_path.name}...")
    
    df = pd.read_csv(csv_path)
    print(f"   ✓ Loaded {len(df)} rows")
    
    # Strip whitespace from column names
    df.columns = df.columns.str.strip()
    print(f"   Columns: {df.columns.tolist()}")
    
    if data_type == "bulk_deals":
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
        df["nse_ticker"] = df["symbol"].apply(lambda x: f"{x}.NS" if pd.notna(x) and not str(x).endswith(".NS") else x)
        df["source"] = "NSE_BULK_DEALS"
        
    elif data_type == "credit_ratings":
        # Handle different possible column names
        column_map = {}
        date_mapped = False
        
        for col in df.columns:
            col_upper = col.upper().strip()
            
            # Map first date-like column to "date"
            if not date_mapped and ("CREATE DATE" in col_upper or "RATING DATE" in col_upper):
                column_map[col] = "date"
                date_mapped = True
            elif "SYMBOL" in col_upper or "IDENTIFIER" in col_upper:
                column_map[col] = "symbol"
            elif "COMPANY NAME" in col_upper:
                column_map[col] = "company_name"
            elif "AGENCY" in col_upper and "EARLIER" not in col_upper:
                column_map[col] = "agency"
            elif "RATING ACTION" in col_upper and "EARLIER" not in col_upper:
                column_map[col] = "rating_action"
            elif col_upper == "CREDIT RATING" and "EARLIER" not in col_upper and "OUTLOOK" not in col_upper:
                column_map[col] = "rating"
        
        df = df.rename(columns=column_map)
        
        # Convert types
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
        
        df["nse_ticker"] = df["symbol"].apply(lambda x: f"{x}.NS" if pd.notna(x) and not str(x).endswith(".NS") else x)
        df["source"] = "NSE_CREDIT_RATINGS"
    
    # Sort by date
    df = df.sort_values("date", ascending=False)
    
    return df


def scrape_nse_data(data_type, period=None, from_date=None, to_date=None):
    """
    Scrape NSE data (bulk deals or credit ratings).
    
    Args:
        data_type: 'bulk_deals' or 'credit_ratings'
        period: Pre-set period (1D, 1W, 1M, 3M, 6M, 1Y)
        from_date: Start date for custom range
        to_date: End date for custom range
    """
    print("=" * 80)
    print(f"NSE {'BULK DEALS' if data_type == 'bulk_deals' else 'CREDIT RATINGS'} SCRAPER")
    print("=" * 80)
    
    # Set URL and output directory
    if data_type == "bulk_deals":
        url = BULK_DEALS_URL
        output_dir = BULK_DEALS_DIR
        file_pattern = "*Bulk*.csv"
        period_buttons = {
            "1D": ["1D", "1 DAY"],
            "1W": ["1W", "1 WEEK"],
            "1M": ["1M", "1 MONTH"],
            "3M": ["3M", "3 MONTH"],
            "6M": ["6M", "6 MONTH"],
            "1Y": ["1Y", "1 YEAR"],
        }
    else:
        url = CREDIT_RATINGS_URL
        output_dir = CREDIT_RATINGS_DIR
        file_pattern = "*CRD*.csv"
        period_buttons = {
            "1D": ["1D", "1 DAY"],
            "1W": ["1W", "1 WEEK"],
            "1M": ["1M", "1 MONTH"],
            "3M": ["3M", "3 MONTH"],
            "6M": ["6M", "6 MONTH"],
            "1Y": ["1Y", "1 YEAR"],
        }
    
    driver = None
    try:
        # Open page
        print(f"\n1. Opening {url}...")
        driver = create_driver()
        driver.get(url)
        driver.maximize_window()
        
        # Wait for page
        print("   Waiting for page to load...")
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.TAG_NAME, "table"))
        )
        time.sleep(3)
        print("   ✓ Page loaded")
        
        # Set date range or click period button
        if from_date and to_date:
            print(f"\n2. Setting custom date range...")
            set_custom_date_range(driver, from_date, to_date)
            time.sleep(2)
        elif period:
            print(f"\n2. Clicking time period: {period}...")
            if not find_and_click_button(driver, period_buttons.get(period, [period])):
                print(f"   ⚠ Could not click {period}, using default")
            time.sleep(2)
        else:
            print("\n2. Using default date range...")
        
        # Click Download CSV
        print("\n3. Downloading CSV...")
        if not find_and_click_button(driver, ["DOWNLOAD", "CSV", "DOWNLOAD (.CSV)"]):
            print("   ⚠ Could not find Download button")
            return None
        
        # Wait for download
        csv_path = wait_for_csv_download(timeout=30, file_pattern=file_pattern)
        
        if not csv_path:
            print("   ✗ Download timed out")
            return None
        
        print(f"   ✓ Downloaded: {csv_path.name}")
        
        # Parse CSV
        df = parse_csv(csv_path, data_type)
        
        # Save
        today = datetime.now().strftime("%Y%m%d")
        if period:
            output_path = output_dir / f"nse_{data_type}_{period}_{today}.csv"
        elif from_date:
            output_path = output_dir / f"nse_{data_type}_{from_date.strftime('%Y%m%d')}_{to_date.strftime('%Y%m%d')}.csv"
        else:
            output_path = output_dir / f"nse_{data_type}_{today}.csv"
        
        df.to_csv(output_path, index=False)
        print(f"\n   ✓ Saved to {output_path}")
        
        # Also save to main file
        main_path = output_dir / f"nse_{data_type}_all.csv"
        df.to_csv(main_path, index=False)
        print(f"   ✓ Saved to {main_path}")
        
        # Statistics
        print(f"\n{'=' * 60}")
        print("STATISTICS")
        print(f"{'=' * 60}")
        print(f"Total rows: {len(df)}")
        print(f"Unique symbols: {df['symbol'].nunique()}")
        print(f"Date range: {df['date'].min()} to {df['date'].max()}")
        
        if data_type == "bulk_deals" and "deal_type" in df.columns:
            print(f"\nDeal types:")
            print(df["deal_type"].value_counts())
        elif data_type == "credit_ratings" and "agency" in df.columns:
            print(f"\nAgencies:")
            print(df["agency"].value_counts())
        
        # Sample
        print(f"\n{'=' * 60}")
        print("SAMPLE DATA")
        print(f"{'=' * 60}")
        if data_type == "bulk_deals":
            print(df[["date", "symbol", "company_name", "deal_type", "quantity", "price"]].head(10).to_string())
        else:
            print(df[["date", "symbol", "company_name", "agency", "rating_action"]].head(10).to_string())
        
        return df
        
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return None
        
    finally:
        if driver:
            print("\nClosing browser...")
            time.sleep(2)
            driver.quit()
            print("✓ Browser closed")


def download_all_history(data_type, start_year=2020):
    """Download complete historical data year by year."""
    print("=" * 80)
    print(f"DOWNLOADING COMPLETE HISTORICAL DATA ({data_type})")
    print("=" * 80)
    
    end_date = datetime.now()
    all_data = []
    
    # Download year by year
    for year in range(start_year, end_date.year + 1):
        from_dt = datetime(year, 1, 1)
        to_dt = datetime(year, 12, 31) if year < end_date.year else end_date
        
        print(f"\n{'=' * 60}")
        print(f"DOWNLOADING: {from_dt.date()} to {to_dt.date()}")
        print(f"{'=' * 60}")
        
        df = scrape_nse_data(data_type, from_date=from_dt, to_date=to_dt)
        
        if df is not None:
            all_data.append(df)
            time.sleep(3)  # Wait between requests
    
    # Combine all
    if all_data:
        combined = pd.concat(all_data, ignore_index=True)
        combined = combined.drop_duplicates(subset=["date", "symbol", "client_name" if "client_name" in combined.columns else "agency"], keep="last")
        combined = combined.sort_values("date", ascending=False)
        
        today = datetime.now().strftime("%Y%m%d")
        output_path = BULK_DEALS_DIR / f"nse_{data_type}_historical_{start_year}_{today}.csv" if data_type == "bulk_deals" else CREDIT_RATINGS_DIR / f"nse_{data_type}_historical_{start_year}_{today}.csv"
        combined.to_csv(output_path, index=False)
        print(f"\n✓ Complete historical data saved: {output_path}")
        print(f"  Total rows: {len(combined)}")
        
        return combined
    
    return None


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="NSE Complete Historical Scraper")
    parser.add_argument("--type", choices=["bulk-deals", "credit-ratings"], required=True)
    parser.add_argument("--period", choices=["1D", "1W", "1M", "3M", "6M", "1Y"])
    parser.add_argument("--from-date", type=str, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--to-date", type=str, help="End date (YYYY-MM-DD)")
    parser.add_argument("--all-history", action="store_true", help="Download all historical data")
    parser.add_argument("--start-year", type=int, default=2020, help="Start year for historical download")
    
    args = parser.parse_args()
    
    if args.all_history:
        download_all_history(args.type.replace("-", "_"), start_year=args.start_year)
    else:
        from_date = datetime.strptime(args.from_date, "%Y-%m-%d") if args.from_date else None
        to_date = datetime.strptime(args.to_date, "%Y-%m-%d") if args.to_date else None
        
        scrape_nse_data(
            args.type.replace("-", "_"),
            period=args.period,
            from_date=from_date,
            to_date=to_date
        )
