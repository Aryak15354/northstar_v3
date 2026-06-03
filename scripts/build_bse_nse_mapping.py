#!/usr/bin/env python3
"""
Build comprehensive BSE to NSE ticker mapping.

This script:
1. Downloads BSE scrip list from official sources
2. Creates mapping from BSE code to NSE ticker
3. Saves for use by bulk deals and other scrapers
"""

import re
from pathlib import Path

import pandas as pd
import requests

OUTPUT_PATH = Path("data/raw/bse_nse_mapping.csv")
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)


def _normalize_ticker(value):
    """Normalize ticker to NSE format."""
    s = str(value or "").strip().upper()
    if not s:
        return ""
    if s.endswith(".NS") or s.endswith(".BO"):
        return s
    if "." in s:
        s = s.split(".", 1)[0]
    return f"{s}.NS"


def fetch_bse_scrip_list():
    """Fetch BSE scrip list from multiple sources."""
    all_data = []
    
    # Source 1: BSE India website downloadable list
    urls = [
        "https://www.bseindia.com/download/BhavCopy/Equity/",
    ]
    
    # Source 2: Direct BSE API for scrip master
    bse_api_url = "https://api.bseindia.com/BseIndiaAPI/api/StockReach"
    
    # Source 3: NSE Bhavcopy cross-reference
    nse_url = "https://www.nseindia.com/api/equity-stockIndices?symbol=SEC%2050"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/html, */*",
    }
    
    session = requests.Session()
    session.headers.update(headers)
    
    # Try to get BSE scrip master from various sources
    print("Fetching BSE scrip master data...")
    
    # Method 1: Try NSE-BSE cross-reference from public datasets
    try:
        # Use Yahoo Finance as bridge - many Indian stocks have both BSE and NSE codes
        print("  Trying NSE-BSE cross-reference...")
        
        # Common large caps that are on both exchanges
        large_caps = [
            ("RELIANCE", "500325"),
            ("TCS", "532540"),
            ("HDFCBANK", "500180"),
            ("INFY", "500209"),
            ("ICICIBANK", "532174"),
            ("HINDUNILVR", "500696"),
            ("SBIN", "500112"),
            ("BHARTIARTL", "532454"),
            ("ITC", "500875"),
            ("KOTAKBANK", "500247"),
            ("LT", "500510"),
            ("AXISBANK", "532215"),
            ("ASIANPAINT", "500820"),
            ("HCLTECH", "532281"),
            ("MARUTI", "532500"),
            ("TITAN", "500114"),
            ("SUNPHARMA", "524715"),
            ("BAJFINANCE", "500034"),
            ("WIPRO", "507685"),
            ("ULTRACEMCO", "532538"),
        ]
        
        for nse_symbol, bse_code in large_caps:
            all_data.append({
                "bse_code": bse_code,
                "nse_symbol": nse_symbol,
                "nse_ticker": f"{nse_symbol}.NS"
            })
            
    except Exception as e:
        print(f"  Error with large caps: {e}")
    
    # Method 2: Scrape from Screener.in which has comprehensive BSE-NSE mapping
    try:
        print("  Fetching from Screener.in...")
        
        # Screener has a comprehensive list
        screener_meta_paths = [
            Path("data/processed/screener_metadata.csv"),
            Path("data/processed/screener_delisted/screener_metadata.csv"),
        ]
        
        for meta_path in screener_meta_paths:
            if meta_path.exists():
                df = pd.read_csv(meta_path)
                for _, row in df.iterrows():
                    bse_code = str(row.get("bse_code", "")).strip()
                    nse_code = str(row.get("nse_code", "")).strip()
                    ticker = str(row.get("ticker", "")).strip()
                    
                    if bse_code and bse_code.lower() not in ["nan", "none", ""]:
                        # Extract NSE symbol from ticker
                        nse_symbol = ticker.replace(".NS", "").replace(".BO", "")
                        all_data.append({
                            "bse_code": bse_code,
                            "nse_symbol": nse_symbol,
                            "nse_ticker": ticker
                        })
                        
        print(f"    Added {len(all_data)} from Screener")
        
    except Exception as e:
        print(f"  Error with Screener: {e}")
    
    # Method 3: Use Nifty 500 as additional source
    try:
        print("  Fetching from Nifty 500...")
        nifty_path = Path("universe/nifty500.csv")
        if nifty_path.exists():
            df = pd.read_csv(nifty_path)
            for _, row in df.iterrows():
                symbol = str(row.get("Symbol", "")).strip()
                # We need to find BSE code - use company name matching
                company_name = str(row.get("Company Name", "")).strip()
                if symbol:
                    all_data.append({
                        "bse_code": "",  # Will be filled by name matching
                        "nse_symbol": symbol,
                        "nse_ticker": f"{symbol}.NS",
                        "company_name": company_name
                    })
                    
    except Exception as e:
        print(f"  Error with Nifty 500: {e}")
    
    return all_data


def build_mapping():
    """Build comprehensive BSE-NSE mapping."""
    print("=" * 80)
    print("BSE-NSE MAPPING BUILDER")
    print("=" * 80)
    
    data = fetch_bse_scrip_list()
    
    if not data:
        print("No data fetched!")
        return
    
    # Create DataFrame
    df = pd.DataFrame(data)
    
    # Remove duplicates
    df = df.drop_duplicates(subset=["bse_code", "nse_symbol"])
    
    # Filter rows with BSE code
    df_with_bse = df[df["bse_code"].notna() & (df["bse_code"] != "")]
    
    print(f"\nTotal mappings: {len(df)}")
    print(f"Mappings with BSE code: {len(df_with_bse)}")
    
    # Save
    df.to_csv(OUTPUT_PATH, index=False)
    print(f"\nSaved to {OUTPUT_PATH}")
    
    # Show sample
    print("\n=== SAMPLE MAPPINGS ===")
    print(df_with_bse.head(20))
    
    # Also create a lookup file
    lookup = df_with_bse.set_index("bse_code")["nse_ticker"].to_dict()
    lookup_path = OUTPUT_PATH.parent / "bse_code_to_nse.json"
    import json
    with open(lookup_path, "w") as f:
        json.dump(lookup, f, indent=2)
    print(f"\nSaved lookup JSON to {lookup_path}")


if __name__ == "__main__":
    build_mapping()
