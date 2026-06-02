#!/usr/bin/env python3
"""
NSE Bulk Deals - DIRECT API SCRAPER

Scrapes bulk deals directly from NSE API endpoint that powers:
https://www.nseindia.com/report-detail/display-bulk-and-block-deals

This bypasses the web interface and gets data directly.
"""

import json
import time
from pathlib import Path
from datetime import datetime, timedelta

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Project root
PROJECT_ROOT = Path(__file__).parent.parent

# NSE API Endpoints (extracted from network traffic on the page)
NSE_BASE = "https://www.nseindia.com"
NSE_BULK_DEALS_API = "/api/bulk-deal-block-deal"

# Output
OUTPUT_DIR = PROJECT_ROOT / "data" / "raw" / "exchanges" / "nse" / "alternative" / "bulk_deals"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Headers - mimicking browser
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Referer": f"{NSE_BASE}/report-detail/display-bulk-and-block-deals",
    "X-Requested-With": "XMLHttpRequest",
}


def create_session():
    """Create robust session with retries."""
    session = requests.Session()
    session.headers.update(HEADERS)
    
    # Retry strategy
    retry = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    # Initialize with homepage (get cookies)
    try:
        session.get(NSE_BASE, timeout=15)
        print("✓ Session initialized with NSE")
        return session
    except Exception as e:
        print(f"✗ Session init failed: {e}")
        return None


def fetch_bulk_deals(session, from_date, to_date):
    """
    Fetch bulk deals from NSE API.
    
    Dates in DD-MM-YYYY format.
    """
    print(f"\n=== Fetching Bulk Deals ===")
    print(f"From: {from_date} | To: {to_date}")
    
    url = f"{NSE_BASE}{NSE_BULK_DEALS_API}"
    
    params = {
        "fromDate": from_date,
        "toDate": to_date,
    }
    
    try:
        print(f"GET {url}")
        response = session.get(url, params=params, timeout=30)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            # Check content type
            content_type = response.headers.get('Content-Type', '')
            print(f"Content-Type: {content_type}")
            
            # Try JSON
            if 'json' in content_type.lower():
                try:
                    data = response.json()
                    return parse_nse_response(data)
                except json.JSONDecodeError as e:
                    print(f"JSON parse error: {e}")
                    print(f"Response: {response.text[:500]}")
            else:
                # HTML response - might have embedded data
                print(f"HTML response ({len(response.text)} bytes)")
                print(f"Preview: {response.text[:500]}")
        else:
            print(f"Error {response.status_code}")
            print(f"Response: {response.text[:500]}")
            
    except Exception as e:
        print(f"Exception: {e}")
        import traceback
        traceback.print_exc()
    
    return []


def parse_nse_response(data):
    """Parse NSE API response."""
    deals = []
    
    # Handle different response structures
    if isinstance(data, dict):
        # Try common keys
        for key in ['data', 'bulkDeals', 'bulk_deals', 'records', 'result']:
            if key in data:
                data = data[key]
                break
    
    if isinstance(data, list):
        for item in data:
            deal = parse_deal_item(item)
            if deal:
                deals.append(deal)
    
    print(f"✓ Parsed {len(deals)} deals")
    return deals


def parse_deal_item(item):
    """Parse single deal item from API response."""
    if not isinstance(item, dict):
        return None
    
    # Map various possible field names
    deal = {
        "date": item.get("tradeDate") or item.get("date") or item.get("announcementDate"),
        "symbol": item.get("symbol") or item.get("securityId") or item.get("scripName"),
        "company_name": item.get("companyName") or item.get("securityName") or item.get("company_name"),
        "client_name": item.get("clientName") or item.get("client_name") or item.get("buyer") or item.get("seller"),
        "deal_type": item.get("buySell") or item.get("dealType") or item.get("type"),
        "quantity": item.get("quantityTraded") or item.get("quantity") or item.get("qty"),
        "price": item.get("tradePrice") or item.get("price"),
        "value": item.get("turnoverValue") or item.get("value") or item.get("turnover"),
        "source": "NSE_API",
    }
    
    if not deal["symbol"]:
        return None
    
    # Normalize
    deal["nse_ticker"] = f"{deal['symbol']}.NS" if not deal["symbol"].endswith(".NS") else deal["symbol"]
    
    return deal


def save_deals(deals, filename):
    """Save deals to CSV."""
    if not deals:
        print("  No deals to save")
        return None
    
    df = pd.DataFrame(deals)
    
    # Convert types
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    
    # Standardize deal type
    df["deal_type"] = df["deal_type"].astype(str).str.upper()
    df["deal_type"] = df["deal_type"].replace({"P": "BUY", "B": "BUY", "S": "SELL"})
    
    # Sort
    df = df.sort_values(["date", "symbol"])
    
    # Save
    output_path = OUTPUT_DIR / filename
    df.to_csv(output_path, index=False)
    print(f"  Saved: {output_path}")
    
    return df


def main():
    """Main function."""
    print("=" * 80)
    print("NSE BULK DEALS - DIRECT API SCRAPER")
    print("=" * 80)
    print("Target: https://www.nseindia.com/report-detail/display-bulk-and-block-deals")
    
    # Create session
    session = create_session()
    if not session:
        print("\nERROR: Could not create NSE session")
        print("This usually means NSE is blocking requests.")
        return
    
    # Date ranges to fetch
    end_date = datetime.now()
    
    # Fetch last 30 days
    start_date = end_date - timedelta(days=30)
    from_date = start_date.strftime("%d-%m-%Y")
    to_date = end_date.strftime("%d-%m-%Y")
    
    print(f"\n{'=' * 60}")
    print("FETCHING LAST 30 DAYS")
    print(f"{'=' * 60}")
    
    deals_30d = fetch_bulk_deals(session, from_date, to_date)
    
    # Fetch last 90 days
    start_date = end_date - timedelta(days=90)
    from_date = start_date.strftime("%d-%m-%Y")
    to_date = end_date.strftime("%d-%m-%Y")
    
    print(f"\n{'=' * 60}")
    print("FETCHING LAST 90 DAYS")
    print(f"{'=' * 60}")
    
    deals_90d = fetch_bulk_deals(session, from_date, to_date)
    
    # Combine
    all_deals = deals_30d + deals_90d
    
    if all_deals:
        # Deduplicate
        df = pd.DataFrame(all_deals)
        df = df.drop_duplicates(subset=["date", "symbol", "client_name", "deal_type"])
        
        print(f"\n{'=' * 60}")
        print("RESULTS")
        print(f"{'=' * 60}")
        print(f"Total deals: {len(df)}")
        print(f"Unique symbols: {df['symbol'].nunique()}")
        print(f"Date range: {df['date'].min()} to {df['date'].max()}")
        
        # Deal type distribution
        if "deal_type" in df.columns:
            print(f"\nDeal types:")
            print(df["deal_type"].value_counts())
        
        # Save
        today = datetime.now().strftime("%Y%m%d")
        save_deals(df.to_dict("records"), f"nse_bulk_deals_{today}.csv")
        save_deals(df.to_dict("records"), "nse_bulk_deals_all.csv")
        
        # Sample
        print(f"\n{'=' * 60}")
        print("SAMPLE DEALS")
        print(f"{'=' * 60}")
        cols = ["date", "symbol", "company_name", "deal_type", "quantity", "price"]
        print(df[cols].head(15).to_string())
        
    else:
        print("\n" + "=" * 60)
        print("NO DATA RETRIEVED")
        print("=" * 60)
        print("\nPossible reasons:")
        print("1. NSE API is down or blocking requests")
        print("2. No bulk deals in the date range")
        print("3. API endpoint has changed")
        print("\nTroubleshooting:")
        print("1. Visit https://www.nseindia.com/report-detail/display-bulk-and-block-deals manually")
        print("2. Check if data loads in browser")
        print("3. Try again later (NSE may rate-limit)")


if __name__ == "__main__":
    main()
