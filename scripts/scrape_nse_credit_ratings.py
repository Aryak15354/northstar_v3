#!/usr/bin/env python3
"""
NSE Credit Ratings Scraper - OFFICIAL NSE API

Scrapes credit rating announcements directly from NSE website.
This captures ALL rating actions (CRISIL, ICRA, CARE) from NSE announcements.

Run daily to keep data fresh.
"""

import json
import time
import random
import re
from pathlib import Path
from datetime import datetime, timedelta

import pandas as pd
import requests

# Project root
PROJECT_ROOT = Path(__file__).parent.parent

# NSE API Endpoints
NSE_BASE_URL = "https://www.nseindia.com"
NSE_ANNOUNCEMENTS_API = "/api/corporate-announcements"

# Output directories
RAW_DIR = PROJECT_ROOT / "data" / "raw" / "exchanges" / "nse" / "alternative" / "credit_ratings"
RAW_DIR.mkdir(parents=True, exist_ok=True)

# Headers
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
}


def get_nse_session():
    """Create NSE session with proper cookies."""
    session = requests.Session()
    session.headers.update(HEADERS)
    
    try:
        resp = session.get(NSE_BASE_URL, timeout=15)
        resp.raise_for_status()
        print("✓ NSE session initialized")
        return session
    except Exception as e:
        print(f"✗ Failed to initialize NSE session: {e}")
        return None


def _extract_rating_from_text(text):
    """Extract rating information from announcement text."""
    if not text:
        return None, None, None
    
    text = str(text).upper()
    
    # Rating patterns
    rating_pattern = r'\b(AAA|AA\+|AA-|AA|A\+|A-|A|BBB\+|BBB-|BBB|BB\+|BB-|BB|B\+|B-|B|C|D)\b'
    ratings = re.findall(rating_pattern, text)
    
    old_rating = ratings[0] if len(ratings) > 0 else None
    new_rating = ratings[1] if len(ratings) > 1 else old_rating
    
    # Action type
    action = "AFFIRM"
    if "UPGRADE" in text or "UPGRADED" in text:
        action = "UPGRADE"
    elif "DOWNGRADE" in text or "DOWNGRADED" in text:
        action = "DOWNGRADE"
    elif "WITHDRAW" in text or "WITHDRAWN" in text:
        action = "WITHDRAW"
    
    # Outlook
    outlook = None
    if "NEGATIVE" in text:
        outlook = "NEGATIVE"
    elif "POSITIVE" in text:
        outlook = "POSITIVE"
    elif "STABLE" in text:
        outlook = "STABLE"
    
    return old_rating, new_rating, action


def _extract_agency_from_text(text):
    """Extract rating agency from text."""
    if not text:
        return None
    
    text = str(text).upper()
    
    if "CRISIL" in text:
        return "CRISIL"
    elif "ICRA" in text:
        return "ICRA"
    elif "CARE" in text:
        return "CARE"
    elif "INDIA RATINGS" in text or "INDIA RATING" in text:
        return "INDIA RATINGS"
    elif "BRICKWORK" in text:
        return "BRICKWORK"
    
    return None


def fetch_credit_ratings_from_api(session, from_date, to_date):
    """
    Fetch credit rating announcements from NSE API.
    """
    print(f"\n=== Fetching NSE Credit Ratings ===")
    print(f"Date range: {from_date} to {to_date}")
    
    all_ratings = []
    
    try:
        # NSE corporate announcements endpoint
        url = f"{NSE_BASE_URL}{NSE_ANNOUNCEMENTS_API}"
        
        params = {
            "fromDate": from_date,
            "toDate": to_date,
            "category": "Credit Rating",
        }
        
        print(f"Requesting: {url}")
        resp = session.get(url, params=params, timeout=30)
        
        print(f"Response status: {resp.status_code}")
        
        if resp.status_code == 200:
            try:
                data = resp.json()
                
                # Handle response format
                if isinstance(data, dict):
                    if 'data' in data:
                        data = data['data']
                    if 'announcements' in data:
                        data = data['announcements']
                
                if isinstance(data, list):
                    for item in data:
                        # Extract rating info from announcement text
                        announcement_text = item.get("announcement") or item.get("text") or item.get("description") or ""
                        old_rating, new_rating, action = _extract_rating_from_text(announcement_text)
                        agency = _extract_agency_from_text(announcement_text)
                        
                        rating = {
                            "date": item.get("announcementDate") or item.get("date"),
                            "symbol": item.get("symbol") or item.get("securityId"),
                            "company_name": item.get("companyName") or item.get("securityName"),
                            "agency": agency,
                            "old_rating": old_rating,
                            "new_rating": new_rating,
                            "action_type": action,
                            "announcement_text": announcement_text[:500] if announcement_text else "",
                            "source": "NSE_API",
                        }
                        
                        if rating["symbol"]:
                            all_ratings.append(rating)
                    
                    print(f"✓ Parsed {len(all_ratings)} rating announcements")
                    
                    # Show agency distribution
                    if all_ratings:
                        agencies = [r["agency"] for r in all_ratings if r["agency"]]
                        print(f"  Agencies found: {set(agencies)}")
                        
                else:
                    print(f"Unexpected data format: {type(data)}")
                    
            except json.JSONDecodeError as e:
                print(f"JSON parse error: {e}")
                print(f"Response: {resp.text[:500]}")
        else:
            print(f"API returned status {resp.status_code}")
            
    except Exception as e:
        print(f"API error: {e}")
        import traceback
        traceback.print_exc()
    
    return all_ratings


def fetch_nse_credit_ratings(session, days=90):
    """Fetch credit ratings for the last N days."""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    # NSE expects DD-MM-YYYY
    from_date = start_date.strftime("%d-%m-%Y")
    to_date = end_date.strftime("%d-%m-%Y")
    
    ratings = fetch_credit_ratings_from_api(session, from_date, to_date)
    
    return ratings


def save_ratings(ratings, filename):
    """Save ratings to CSV."""
    if not ratings:
        print(f"  No ratings to save")
        return None
    
    df = pd.DataFrame(ratings)
    
    # Convert date
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    
    # Add NSE ticker
    df["nse_ticker"] = df["symbol"].apply(lambda x: f"{x}.NS" if x and not str(x).endswith(".NS") else x)
    
    # Sort
    df = df.sort_values(["date", "symbol"])
    
    # Save
    output_path = RAW_DIR / filename
    df.to_csv(output_path, index=False)
    print(f"  Saved to {output_path}")
    
    return df


def main():
    """Main scraping function."""
    print("=" * 80)
    print("NSE CREDIT RATINGS SCRAPER (OFFICIAL NSE API)")
    print("=" * 80)
    
    # Initialize session
    session = get_nse_session()
    if not session:
        print("ERROR: Could not initialize NSE session")
        return
    
    # Fetch recent data (last 90 days)
    print("\nFetching last 90 days...")
    recent_ratings = fetch_nse_credit_ratings(session, days=90)
    
    # Fetch historical data (last 365 days)
    print("\nFetching last 365 days...")
    historical_ratings = fetch_nse_credit_ratings(session, days=365)
    
    # Combine and deduplicate
    if recent_ratings or historical_ratings:
        all_ratings = recent_ratings + historical_ratings
        
        # Remove duplicates
        df = pd.DataFrame(all_ratings)
        df = df.drop_duplicates(subset=["date", "symbol", "action_type"])
        
        print(f"\n{'=' * 60}")
        print("STATISTICS")
        print(f"{'=' * 60}")
        print(f"Total NSE credit ratings: {len(df):,}")
        print(f"Unique symbols: {df['symbol'].nunique()}")
        print(f"Date range: {df['date'].min()} to {df['date'].max()}")
        
        # Rating distribution
        if "action_type" in df.columns:
            print(f"\nAction type distribution:")
            print(df["action_type"].value_counts())
        
        # Agency distribution
        if "agency" in df.columns:
            agencies = df["agency"].dropna().unique()
            print(f"\nAgencies found: {agencies}")
        
        # Ratings with actual values
        with_ratings = df[df["new_rating"].notna()]
        print(f"\nRatings with explicit values: {len(with_ratings)} ({len(with_ratings)/len(df)*100:.1f}%)")
        
        # Save
        today = datetime.now().strftime("%Y%m%d")
        save_ratings(df.to_dict("records"), f"nse_credit_ratings_{today}.csv")
        save_ratings(df.to_dict("records"), "nse_credit_ratings_all.csv")
        
        # Show sample
        print(f"\n{'=' * 60}")
        print("SAMPLE RATINGS")
        print(f"{'=' * 60}")
        cols = ["date", "symbol", "company_name", "agency", "old_rating", "new_rating", "action_type"]
        print(df[cols].head(15))
        
    else:
        print("\n✗ No data fetched from NSE")
        print("\nTroubleshooting:")
        print("1. Check internet connection")
        print("2. NSE website may be down")
        print("3. Try again later")


if __name__ == "__main__":
    main()
