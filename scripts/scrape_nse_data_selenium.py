#!/usr/bin/env python3
"""
NSE Bulk Deals & Credit Ratings - SELENIUM SCRAPER

Uses Selenium to scrape NSE website for:
1. Bulk Deals data
2. Block Deals data  
3. Credit Ratings (from corporate announcements)

Similar to how RBI data is scraped from DBIE.
Requires: selenium, webdriver-manager

Usage:
    python3 scripts/scrape_nse_data_selenium.py
    python3 scripts/scrape_nse_data_selenium.py --data-type bulk-deals
    python3 scripts/scrape_nse_data_selenium.py --data-type credit-ratings
"""

import argparse
import time
import json
from pathlib import Path
from datetime import datetime, timedelta

import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# Project root
PROJECT_ROOT = Path(__file__).parent.parent

# NSE URLs
NSE_BULK_DEALS_URL = "https://www.nseindia.com/report-detail/display-bulk-and-block-deals"
NSE_ANNOUNCEMENTS_URL = "https://www.nseindia.com/corporates/corporate-announcements-credit-rating"

# Output directories
BULK_DEALS_DIR = PROJECT_ROOT / "data" / "raw" / "exchanges" / "nse" / "alternative" / "bulk_deals"
CREDIT_RATINGS_DIR = PROJECT_ROOT / "data" / "raw" / "exchanges" / "nse" / "alternative" / "credit_ratings"
BULK_DEALS_DIR.mkdir(parents=True, exist_ok=True)
CREDIT_RATINGS_DIR.mkdir(parents=True, exist_ok=True)


def create_driver(headless=True):
    """Create Chrome WebDriver with proper options."""
    chrome_options = Options()
    
    if headless:
        chrome_options.add_argument("--headless")
    
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    # Additional anti-detection
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)
    
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=chrome_options
    )
    
    # Execute CDP to hide automation
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            })
        """
    })
    
    return driver


def scrape_bulk_deals(driver, days=30):
    """Scrape bulk deals from NSE using Selenium."""
    print(f"\n{'=' * 60}")
    print(f"SCRAPING NSE BULK DEALS (Last {days} days)")
    print(f"{'=' * 60}")
    
    driver.get(NSE_BULK_DEALS_URL)
    
    # Wait for page to load
    print("Waiting for page to load...")
    WebDriverWait(driver, 30).until(
        EC.presence_of_element_located((By.ID, "symbol"))
    )
    time.sleep(3)  # Extra wait for dynamic content
    
    # Set date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    print(f"Setting date range: {start_date.strftime('%d-%m-%Y')} to {end_date.strftime('%d-%m-%Y')}")
    
    # Find and fill date fields
    try:
        from_date_input = driver.find_element(By.ID, "fromDate")
        to_date_input = driver.find_element(By.ID, "toDate")
        
        from_date_input.clear()
        from_date_input.send_keys(start_date.strftime("%d-%m-%Y"))
        
        to_date_input.clear()
        to_date_input.send_keys(end_date.strftime("%d-%m-%Y"))
        
        time.sleep(2)
        
        # Click GO button
        print("Clicking GO button...")
        go_button = driver.find_element(By.XPATH, "//button[contains(text(), 'GO') or contains(@id, 'submit')]")
        go_button.click()
        
        # Wait for data to load
        print("Waiting for data to load...")
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.TAG_NAME, "table"))
        )
        time.sleep(5)
        
    except Exception as e:
        print(f"Error setting date range: {e}")
        # Try downloading CSV directly
        return download_csv_direct(driver)
    
    # Extract data from table
    deals = []
    try:
        table = driver.find_element(By.TAG_NAME, "table")
        rows = table.find_elements(By.TAG_NAME, "tr")[1:]  # Skip header
        
        for row in rows:
            cols = row.find_elements(By.TAG_NAME, "td")
            if len(cols) >= 7:
                deal = {
                    "date": cols[0].text.strip(),
                    "symbol": cols[1].text.strip(),
                    "company_name": cols[2].text.strip(),
                    "client_name": cols[3].text.strip(),
                    "deal_type": cols[4].text.strip().upper(),
                    "quantity": cols[5].text.strip().replace(",", ""),
                    "price": cols[6].text.strip().replace(",", ""),
                    "value": cols[7].text.strip().replace(",", "") if len(cols) > 7 else "",
                    "source": "NSE_SELENIUM",
                }
                deals.append(deal)
        
        print(f"✓ Scraped {len(deals)} bulk deals")
        
    except Exception as e:
        print(f"Error extracting table data: {e}")
        # Try CSV download
        return download_csv_direct(driver)
    
    return deals


def download_csv_direct(driver):
    """Try to download CSV file directly."""
    print("\nTrying CSV download method...")
    
    try:
        # Find and click download button
        download_btn = driver.find_element(
            By.XPATH, 
            "//button[contains(text(), 'Download') or contains(text(), 'CSV') or contains(@onclick, 'download')]"
        )
        download_btn.click()
        
        print("✓ CSV download initiated")
        print("  Check your Downloads folder for the CSV file")
        print("  Then run: python3 scripts/process_nse_csv.py <downloaded_file.csv>")
        
    except Exception as e:
        print(f"CSV download failed: {e}")
    
    return []


def scrape_credit_ratings(driver, days=90):
    """Scrape credit ratings from NSE announcements."""
    print(f"\n{'=' * 60}")
    print(f"SCRAPING NSE CREDIT RATINGS (Last {days} days)")
    print(f"{'=' * 60}")
    
    driver.get(NSE_ANNOUNCEMENTS_URL)
    
    # Wait for page to load
    print("Waiting for page to load...")
    WebDriverWait(driver, 30).until(
        EC.presence_of_element_located((By.ID, "symbol"))
    )
    time.sleep(3)
    
    # Set date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    print(f"Setting date range: {start_date.strftime('%d-%m-%Y')} to {end_date.strftime('%d-%m-%Y')}")
    
    try:
        from_date_input = driver.find_element(By.ID, "fromDate")
        to_date_input = driver.find_element(By.ID, "toDate")
        
        from_date_input.clear()
        from_date_input.send_keys(start_date.strftime("%d-%m-%Y"))
        
        to_date_input.clear()
        to_date_input.send_keys(end_date.strftime("%d-%m-%Y"))
        
        time.sleep(2)
        
        # Click GO
        go_button = driver.find_element(By.XPATH, "//button[contains(text(), 'GO') or contains(@id, 'submit')]")
        go_button.click()
        
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.TAG_NAME, "table"))
        )
        time.sleep(5)
        
    except Exception as e:
        print(f"Error setting date range: {e}")
        return []
    
    # Extract ratings
    ratings = []
    try:
        table = driver.find_element(By.TAG_NAME, "table")
        rows = table.find_elements(By.TAG_NAME, "tr")[1:]
        
        for row in rows:
            cols = row.find_elements(By.TAG_NAME, "td")
            if len(cols) >= 5:
                rating = {
                    "date": cols[0].text.strip(),
                    "symbol": cols[1].text.strip(),
                    "company_name": cols[2].text.strip(),
                    "agency": extract_agency(cols[3].text if len(cols) > 3 else ""),
                    "rating_action": cols[4].text.strip() if len(cols) > 4 else "",
                    "source": "NSE_SELENIUM",
                }
                ratings.append(rating)
        
        print(f"✓ Scraped {len(ratings)} credit ratings")
        
    except Exception as e:
        print(f"Error extracting ratings: {e}")
    
    return ratings


def extract_agency(text):
    """Extract rating agency from text."""
    text = str(text).upper()
    if "CRISIL" in text:
        return "CRISIL"
    elif "ICRA" in text:
        return "ICRA"
    elif "CARE" in text:
        return "CARE"
    elif "INDIA RATING" in text:
        return "INDIA RATINGS"
    return ""


def save_data(data, data_type, filename):
    """Save scraped data to CSV."""
    if not data:
        print("  No data to save")
        return None
    
    df = pd.DataFrame(data)
    
    # Convert types
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], format="%d-%m-%Y", errors="coerce")
    
    # Add NSE ticker
    if "symbol" in df.columns:
        df["nse_ticker"] = df["symbol"].apply(lambda x: f"{x}.NS" if x and not x.endswith(".NS") else x)
    
    # Sort
    if "date" in df.columns:
        df = df.sort_values("date", ascending=False)
    
    # Save
    if data_type == "bulk_deals":
        output_dir = BULK_DEALS_DIR
    else:
        output_dir = CREDIT_RATINGS_DIR
    
    output_path = output_dir / filename
    df.to_csv(output_path, index=False)
    print(f"  Saved: {output_path}")
    
    return df


def main():
    parser = argparse.ArgumentParser(description="NSE Data Scraper (Selenium)")
    parser.add_argument("--data-type", choices=["bulk-deals", "credit-ratings", "both"], default="both")
    parser.add_argument("--days", type=int, default=30, help="Days of data to fetch")
    parser.add_argument("--headless", action="store_true", default=True)
    parser.add_argument("--no-headless", dest="headless", action="store_false")
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("NSE DATA SCRAPER (SELENIUM)")
    print("=" * 80)
    
    driver = None
    try:
        # Create driver
        print("\nInitializing Chrome WebDriver...")
        driver = create_driver(headless=args.headless)
        print("✓ WebDriver ready")
        
        # Scrape requested data
        if args.data_type in ["bulk-deals", "both"]:
            deals = scrape_bulk_deals(driver, days=args.days)
            if deals:
                today = datetime.now().strftime("%Y%m%d")
                save_data(deals, "bulk_deals", f"nse_bulk_deals_{today}.csv")
                save_data(deals, "bulk_deals", "nse_bulk_deals_all.csv")
        
        if args.data_type in ["credit-ratings", "both"]:
            ratings = scrape_credit_ratings(driver, days=args.days)
            if ratings:
                today = datetime.now().strftime("%Y%m%d")
                save_data(ratings, "credit_ratings", f"nse_credit_ratings_{today}.csv")
                save_data(ratings, "credit_ratings", "nse_credit_ratings_all.csv")
        
        print("\n" + "=" * 60)
        print("SCRAPING COMPLETE")
        print("=" * 60)
        
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        if driver:
            print("\nClosing browser...")
            driver.quit()
            print("✓ Browser closed")


if __name__ == "__main__":
    main()
