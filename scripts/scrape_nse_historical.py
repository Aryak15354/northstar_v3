#!/usr/bin/env python3
"""
NSE Bulk Deals & Credit Ratings - HISTORICAL DATA BUILDER

Uses Custom date range to download full year data at once.
Clicks: Custom → Select From Date → Select To Date → Download

Usage:
    # Bulk deals - download last 5 years
    python3 scripts/scrape_nse_historical.py --type bulk-deals --years 5
    
    # Credit ratings - download from 2020
    python3 scripts/scrape_nse_historical.py --type credit-ratings --from-date 2020-01-01
    
    # Download specific date range
    python3 scripts/scrape_nse_historical.py --type bulk-deals --from-date 2021-01-01 --to-date 2021-12-31
"""

import os
import sys
import time
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


def set_custom_date_range(driver, from_date, to_date):
    """
    Set custom date range using date picker.
    
    1. Click 'Custom' button
    2. Find date input fields
    3. Set from and to dates
    4. Click Apply/Go
    """
    print(f"   Setting custom date range: {from_date.strftime('%d-%m-%Y')} to {to_date.strftime('%d-%m-%Y')}")
    
    # Step 1: Click Custom button
    print("   Clicking 'Custom'...")
    if not find_and_click(driver, ["CUSTOM", "CUSTOM DATE"]):
        print("   ⚠ Could not find Custom button")
        return False
    
    time.sleep(2)
    
    # Step 2: Find and set date inputs
    date_inputs = driver.find_elements(By.TAG_NAME, "input")
    from_input = None
    to_input = None
    
    for inp in date_inputs:
        try:
            inp_type = inp.get_attribute("type")
            inp_id = (inp.get_attribute("id") or "").lower()
            inp_class = (inp.get_attribute("class") or "").lower()
            
            if inp_type == "date":
                if "from" in inp_id or "start" in inp_id or "fromdate" in inp_id:
                    from_input = inp
                elif "to" in inp_id or "end" in inp_id or "todate" in inp_id:
                    to_input = inp
        except Exception:
            continue
    
    # Alternative: look for inputs near labels
    if not from_input or not to_input:
        all_elements = driver.find_elements(By.XPATH, "//*[contains(text(), 'From') or contains(text(), 'To')]")
        for elem in all_elements:
            try:
                text = elem.text.strip().upper()
                # Find associated input
                parent = elem.find_element(By.XPATH, "..")
                inputs = parent.find_elements(By.TAG_NAME, "input")
                if inputs:
                    if "FROM" in text:
                        from_input = inputs[0]
                    elif "TO" in text:
                        to_input = inputs[0]
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
            
            # Click Apply/Go button
            time.sleep(1)
            find_and_click(driver, ["APPLY", "GO", "SUBMIT"])
            time.sleep(3)  # Wait for data to load
            
            return True
        except Exception as e:
            print(f"   ✗ Error setting dates: {e}")
            return False
    else:
        print("   ⚠ Could not find date inputs")
        print("   Trying alternative method...")
        
        # Try clicking period buttons as fallback
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
        
        if current_csvs:
            latest = max(current_csvs, key=lambda p: p.stat().st_mtime)
            if time.time() - latest.stat().st_mtime < 30:
                return latest
        
        time.sleep(1)
    
    all_csvs = list(DOWNLOADS_FOLDER.glob(file_pattern))
    if all_csvs:
        return max(all_csvs, key=lambda p: p.stat().st_mtime)
    
    return None


def parse_csv(csv_path, data_type):
    """Parse downloaded CSV file."""
    print(f"\n   Parsing {csv_path.name}...")
    
    if data_type == "bulk_deals":
        try:
            df = pd.read_csv(csv_path, engine='python', on_bad_lines='warn')
        except Exception:
            df = pd.read_csv(csv_path, on_bad_lines='skip')
        
        print(f"   ✓ Loaded {len(df)} rows")
        
        # Strip whitespace from column names
        df.columns = df.columns.str.strip()
        
        # Map columns
        column_map = {}
        for col in df.columns:
            col_upper = col.upper().strip()
            if col_upper == "DATE":
                column_map[col] = "date"
            elif col_upper == "SYMBOL":
                column_map[col] = "symbol"
            elif "SECURITY NAME" in col_upper:
                column_map[col] = "company_name"
            elif "CLIENT NAME" in col_upper:
                column_map[col] = "client_name"
            elif "BUY" in col_upper or "SELL" in col_upper:
                column_map[col] = "deal_type"
            elif "QUANTITY" in col_upper:
                column_map[col] = "quantity"
            elif "PRICE" in col_upper:
                column_map[col] = "price"
        
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
        # Read with BOM handling
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            content = f.read()
        
        # Clean newlines in column names
        lines = content.split('\n')
        cleaned_lines = []
        current_line = ""
        in_quotes = False
        
        for line in lines:
            quote_count = line.count('"')
            if in_quotes:
                current_line += " " + line
                if quote_count % 2 == 1:
                    cleaned_lines.append(current_line)
                    current_line = ""
                    in_quotes = False
            else:
                if quote_count % 2 == 1:
                    current_line = line
                    in_quotes = True
                else:
                    cleaned_lines.append(line)
        
        if current_line:
            cleaned_lines.append(current_line)
        
        # Write and read cleaned file
        cleaned_path = csv_path.with_suffix('.cleaned.csv')
        with open(cleaned_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(cleaned_lines))
        
        try:
            df = pd.read_csv(cleaned_path, engine='python', on_bad_lines='warn')
        except Exception:
            df = pd.read_csv(cleaned_path, on_bad_lines='skip')
        
        try:
            cleaned_path.unlink()
        except Exception:
            pass
        
        print(f"   ✓ Loaded {len(df)} rows")
        
        # Map columns
        column_mapping = {
            'date': None,
            'isin': None,
            'company_name': None,
            'agency': None,
            'rating': None,
            'rating_action': None,
            'outlook': None,
        }
        
        date_candidates = []
        
        for col in df.columns:
            col_clean = str(col).strip().upper().replace('\n', ' ').replace('  ', ' ')
            
            if 'DATE OF CREDIT RATING' in col_clean and 'EARLIER' not in col_clean and 'VERIFICATION' not in col_clean:
                date_candidates.insert(0, col)
            elif 'DATE' in col_clean and 'EARLIER' not in col_clean and 'VERIFICATION' not in col_clean:
                date_candidates.append(col)
            
            if 'ISIN' in col_clean and 'EARLIER' not in col_clean:
                column_mapping['isin'] = col
            if 'COMPANY NAME' in col_clean:
                column_mapping['company_name'] = col
            if 'AGENCY' in col_clean and 'EARLIER' not in col_clean and 'VERIFICATION' not in col_clean:
                column_mapping['agency'] = col
            if col_clean == 'CREDIT RATING' or (col_clean == 'RATING' and 'ACTION' not in col_clean):
                column_mapping['rating'] = col
            if 'RATING ACTION' in col_clean and 'EARLIER' not in col_clean:
                column_mapping['rating_action'] = col
            if col_clean == 'OUTLOOK':
                column_mapping['outlook'] = col
        
        column_mapping['date'] = date_candidates[0] if date_candidates else None
        
        rename_map = {v: k for k, v in column_mapping.items() if v is not None}
        df = df.rename(columns=rename_map)
        
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'], format='%d-%m-%Y', errors='coerce')
        
        df['instrument_type'] = 'Debt'
        df['source'] = 'NSE_CREDIT_RATINGS'
    
    df = df.sort_values('date', ascending=False)
    return df


def download_year_range(data_type, from_date, to_date):
    """Download data for a specific date range (up to 1 year)."""
    print(f"\n{'=' * 60}")
    print(f"DOWNLOADING: {from_date.date()} to {to_date.date()}")
    print(f"{'=' * 60}")
    
    # Check if range is more than 365 days
    days_diff = (to_date - from_date).days
    if days_diff > 365:
        print(f"   ⚠ Date range ({days_diff} days) exceeds 365 days")
        print(f"   Splitting into smaller chunks...")
        
        # Split into multiple requests
        all_data = []
        current_from = from_date
        while current_from < to_date:
            current_to = min(current_from + timedelta(days=364), to_date)
            df = download_year_range(data_type, current_from, current_to)
            if df is not None:
                all_data.append(df)
            current_from = current_to + timedelta(days=1)
        
        if all_data:
            combined = pd.concat(all_data, ignore_index=True)
            combined = combined.drop_duplicates(subset=['date', 'symbol' if 'symbol' in combined.columns else 'isin'], keep='last')
            return combined
        return None
    
    # Set URL and file pattern
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
        
        # Set custom date range
        if not set_custom_date_range(driver, from_date, to_date):
            print("   ⚠ Custom date range failed, trying default data")
        
        # Click Download
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
        
        # Parse CSV
        df = parse_csv(csv_path, data_type)
        
        if df is None or len(df) == 0:
            print("   ✗ No data parsed")
            return None
        
        print(f"   ✓ Parsed {len(df)} rows")
        
        return df
        
    except Exception as e:
        print(f"   ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return None
        
    finally:
        if driver:
            driver.quit()


def build_historical_database(data_type, start_year=2020, end_year=None):
    """Build complete historical database year by year."""
    print("=" * 80)
    print(f"BUILDING HISTORICAL DATABASE: {data_type.upper()}")
    print("=" * 80)
    
    if end_year is None:
        end_year = datetime.now().year
    
    all_data = []
    
    for year in range(start_year, end_year + 1):
        from_dt = datetime(year, 1, 1)
        to_dt = datetime(year, 12, 31)
        
        # Don't download future dates
        if from_dt > datetime.now():
            break
        
        # Adjust end date if current year
        if year == datetime.now().year:
            to_dt = datetime.now()
        
        df = download_year_range(data_type, from_dt, to_dt)
        
        if df is not None and len(df) > 0:
            all_data.append(df)
            print(f"   ✓ Year {year}: {len(df)} rows")
            time.sleep(3)  # Wait between requests
    
    if all_data:
        combined = pd.concat(all_data, ignore_index=True)
        combined = combined.drop_duplicates(
            subset=['date', 'symbol' if 'symbol' in combined.columns else 'isin'], 
            keep='last'
        )
        combined = combined.sort_values('date', ascending=False)
        
        # Save
        today = datetime.now().strftime("%Y%m%d")
        if data_type == "bulk_deals":
            output_dir = BULK_DEALS_DIR
        else:
            output_dir = CREDIT_RATINGS_DIR
        
        output_path = output_dir / f"nse_{data_type}_historical_{start_year}_{today}.csv"
        combined.to_csv(output_path, index=False)
        print(f"\n{'=' * 60}")
        print(f"HISTORICAL DATABASE COMPLETE")
        print(f"{'=' * 60}")
        print(f"Total rows: {len(combined):,}")
        print(f"Date range: {combined['date'].min()} to {combined['date'].max()}")
        print(f"Saved to: {output_path}")
        
        # Also save as main file
        main_path = output_dir / f"nse_{data_type}_all.csv"
        combined.to_csv(main_path, index=False)
        print(f"Also saved to: {main_path}")
        
        return combined
    
    return None


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="NSE Historical Data Builder")
    parser.add_argument("--type", choices=["bulk-deals", "credit-ratings"], required=True)
    parser.add_argument("--from-date", type=str, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--to-date", type=str, help="End date (YYYY-MM-DD)")
    parser.add_argument("--years", type=int, default=5, help="Number of years to download")
    parser.add_argument("--start-year", type=int, default=2020, help="Start year")
    parser.add_argument("--end-year", type=int, help="End year (default: current year)")
    
    args = parser.parse_args()
    
    if args.from_date and args.to_date:
        # Specific date range
        from_dt = datetime.strptime(args.from_date, "%Y-%m-%d")
        to_dt = datetime.strptime(args.to_date, "%Y-%m-%d")
        build_historical_database(
            args.type.replace("-", "_"),
            start_year=from_dt.year,
            end_year=to_dt.year
        )
    else:
        # Download last N years
        end_year = args.end_year or datetime.now().year
        start_year = end_year - args.years + 1
        build_historical_database(
            args.type.replace("-", "_"),
            start_year=max(start_year, args.start_year),
            end_year=end_year
        )
