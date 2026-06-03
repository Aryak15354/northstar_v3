#!/usr/bin/env python3
"""
NSE Bulk Deals - SELENIUM CSV DOWNLOAD

Simple approach:
1. Open NSE bulk deals page
2. Click time period (1D, 1W, 1M, 3M, 6M, 1Y)
3. Click "Download (.csv)" button
4. Parse downloaded CSV

Just like RBI DBIE scraper.
"""

import os
import time
import glob
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

# NSE URL
NSE_URL = "https://www.nseindia.com/report-detail/display-bulk-and-block-deals"

# Output directories
OUTPUT_DIR = PROJECT_ROOT / "data" / "raw" / "exchanges" / "nse" / "alternative" / "bulk_deals"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Download directory
DOWNLOAD_DIR = OUTPUT_DIR / "downloads"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)


def create_driver():
    """Create Chrome WebDriver with download preferences."""
    chrome_options = Options()
    
    # Set download directory
    prefs = {
        "download.default_directory": str(DOWNLOAD_DIR.absolute()),
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True,
        "plugins.always_open_pdf_externally": True,
    }
    chrome_options.add_experimental_option("prefs", prefs)
    
    # Standard options
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
    
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=chrome_options
    )
    return driver


def wait_for_download(download_dir, timeout=30):
    """Wait for CSV file to finish downloading."""
    print(f"Waiting for download (max {timeout}s)...")
    
    start_time = time.time()
    while time.time() - start_time < timeout:
        # Check for CSV files
        csv_files = list(download_dir.glob("*.csv"))
        # Check for partial downloads (.crdownload or .part files)
        part_files = list(download_dir.glob("*.crdownload")) + list(download_dir.glob("*.part"))
        
        if csv_files and not part_files:
            # CSV exists and no partial downloads
            time.sleep(2)  # Extra wait for write completion
            return csv_files[0]
        
        time.sleep(1)
    
    return None


def scrape_with_download(period="1W"):
    """Scrape NSE bulk deals by downloading CSV."""
    print("=" * 80)
    print("NSE BULK DEALS - CSV DOWNLOAD METHOD")
    print("=" * 80)
    
    driver = None
    try:
        # Create driver
        print("\n1. Initializing WebDriver...")
        driver = create_driver()
        print("   ✓ Ready")
        
        # Navigate
        print(f"\n2. Opening NSE bulk deals page...")
        driver.get(NSE_URL)
        driver.maximize_window()
        
        # Wait for page load
        print("   Waiting for page to load...")
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.TAG_NAME, "table"))
        )
        time.sleep(5)
        print("   ✓ Page loaded")
        
        # Click time period button
        print(f"\n3. Clicking time period: {period}...")
        
        # Find all buttons and look for the time period ones
        buttons = driver.find_elements(By.TAG_NAME, "button")
        print(f"   Found {len(buttons)} buttons")
        
        clicked = False
        for btn in buttons:
            try:
                text = btn.text.strip().upper()
                if text == period.upper():
                    print(f"   Found '{period}' button")
                    driver.execute_script("arguments[0].scrollIntoView(true);", btn)
                    time.sleep(1)
                    btn.click()
                    clicked = True
                    print(f"   ✓ Clicked {period}")
                    time.sleep(3)  # Wait for data to refresh
                    break
            except Exception:
                continue
        
        if not clicked:
            print(f"   ⚠ Could not find {period} button, using default data")
        
        # Click Download CSV button
        print("\n4. Looking for Download CSV button...")
        
        # Try multiple strategies to find download button
        download_clicked = False
        
        # Strategy 1: Button with "Download" or "CSV" text
        buttons = driver.find_elements(By.TAG_NAME, "button")
        for btn in buttons:
            try:
                text = btn.text.strip().upper()
                if "DOWNLOAD" in text or "CSV" in text:
                    print(f"   Found download button: '{text}'")
                    driver.execute_script("arguments[0].scrollIntoView(true);", btn)
                    time.sleep(1)
                    btn.click()
                    download_clicked = True
                    print("   ✓ Clicked Download CSV")
                    break
            except Exception:
                continue
        
        # Strategy 2: Link with "Download" or "csv" in text/href
        if not download_clicked:
            links = driver.find_elements(By.TAG_NAME, "a")
            for link in links:
                try:
                    text = link.text.strip().upper()
                    href = link.get_attribute("href") or ""
                    if "DOWNLOAD" in text or "CSV" in text or "csv" in href.lower():
                        print(f"   Found download link: '{text}'")
                        driver.execute_script("arguments[0].scrollIntoView(true);", link)
                        time.sleep(1)
                        driver.execute_script("arguments[0].click();", link)  # Use JS click
                        download_clicked = True
                        print("   ✓ Clicked Download CSV")
                        break
                except Exception as e:
                    print(f"   Error clicking link: {e}")
                    continue
        
        # Strategy 3: Button with onclick containing "download"
        if not download_clicked:
            try:
                download_btn = driver.find_element(
                    By.XPATH, 
                    "//button[contains(@onclick, 'download') or contains(@onclick, 'csv')]"
                )
                driver.execute_script("arguments[0].scrollIntoView(true);", download_btn)
                time.sleep(1)
                download_btn.click()
                download_clicked = True
                print("   ✓ Clicked Download CSV (via onclick)")
            except Exception as e:
                print(f"   ⚠ Download button not found: {e}")
        
        if download_clicked:
            # Wait for download
            csv_path = wait_for_download(DOWNLOAD_DIR, timeout=30)
            
            if csv_path:
                print(f"\n5. Downloaded: {csv_path.name}")
                
                # Parse CSV
                print("\n6. Parsing CSV...")
                df = pd.read_csv(csv_path)
                print(f"   ✓ Loaded {len(df)} rows")
                print(f"   Columns: {df.columns.tolist()}")
                
                # Standardize columns
                column_map = {
                    "DATE": "date",
                    "SYMBOL": "symbol",
                    "SECURITY NAME": "company_name",
                    "CLIENT NAME": "client_name",
                    "BUY / SELL": "deal_type",
                    "QUANTITY TRADED": "quantity",
                    "TRADE PRICE / WGHT. AVG. PRICE": "price",
                    "REMARKS": "remarks",
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
                
                # Add source
                df["source"] = "NSE_SELENIUM_DOWNLOAD"
                
                # Sort by date
                df = df.sort_values("date", ascending=False)
                
                # Save
                today = datetime.now().strftime("%Y%m%d")
                output_path = OUTPUT_DIR / f"nse_bulk_deals_{period}_{today}.csv"
                df.to_csv(output_path, index=False)
                print(f"\n   ✓ Saved to {output_path}")
                
                # Also save to main file
                main_path = OUTPUT_DIR / "nse_bulk_deals_all.csv"
                df.to_csv(main_path, index=False)
                print(f"   ✓ Saved to {main_path}")
                
                # Statistics
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
            else:
                print("\n   ✗ Download timed out")
        else:
            print("\n   ✗ Could not find Download button")
        
        # Fallback: Extract from table if download failed
        print("\n7. Fallback: Extracting from table...")
        tables = driver.find_elements(By.TAG_NAME, "table")
        for i, table in enumerate(tables):
            rows = table.find_elements(By.TAG_NAME, "tr")
            if len(rows) > 10:
                print(f"   Found table with {len(rows)} rows")
                # Extract data (same as before)
                break
        
        return None
        
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


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="NSE Bulk Deals CSV Download")
    parser.add_argument("--period", choices=["1D", "1W", "1M", "3M", "6M", "1Y"], default="1W")
    parser.add_argument("--all-periods", action="store_true")
    
    args = parser.parse_args()
    
    if args.all_periods:
        all_data = []
        for period in ["1D", "1W", "1M", "3M", "6M", "1Y"]:
            print(f"\n{'=' * 80}")
            print(f"FETCHING: {period}")
            print(f"{'=' * 80}")
            df = scrape_with_download(period)
            if df is not None:
                all_data.append(df)
            time.sleep(3)
        
        if all_data:
            combined = pd.concat(all_data, ignore_index=True)
            combined = combined.drop_duplicates(subset=["date", "symbol", "client_name", "deal_type"])
            
            today = datetime.now().strftime("%Y%m%d")
            output_path = OUTPUT_DIR / f"nse_bulk_deals_all_periods_{today}.csv"
            combined.to_csv(output_path, index=False)
            print(f"\n✓ Combined: {output_path}")
            print(f"  Total rows: {len(combined)}")
    else:
        scrape_with_download(args.period)
