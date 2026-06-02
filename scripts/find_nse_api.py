#!/usr/bin/env python3
"""
NSE Data - FIND CORRECT API ENDPOINTS

This script helps discover the correct NSE API endpoints by:
1. Loading the page and examining network requests
2. Finding embedded API URLs in JavaScript
3. Testing common endpoint patterns
"""

import re
import json
from pathlib import Path

import requests
from bs4 import BeautifulSoup

NSE_BASE = "https://www.nseindia.com"
BULK_DEALS_PAGE = "/report-detail/display-bulk-and-block-deals"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def find_api_endpoints():
    """Find API endpoints in NSE page."""
    print("=" * 80)
    print("NSE API ENDPOINT DISCOVERY")
    print("=" * 80)
    
    session = requests.Session()
    session.headers.update(HEADERS)
    
    # Get homepage first (cookies)
    print("\n1. Initializing session...")
    try:
        session.get(NSE_BASE, timeout=15)
        print("   ✓ Session initialized")
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        return
    
    # Get bulk deals page
    print("\n2. Fetching bulk deals page...")
    url = f"{NSE_BASE}{BULK_DEALS_PAGE}"
    try:
        response = session.get(url, timeout=30)
        print(f"   Status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"   ✗ Page returned {response.status_code}")
            return
            
        print(f"   ✓ Page loaded ({len(response.text)} bytes)")
        
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        return
    
    # Parse HTML
    print("\n3. Analyzing page content...")
    soup = BeautifulSoup(response.text, "html.parser")
    
    # Find all script tags
    scripts = soup.find_all("script")
    print(f"   Found {len(scripts)} script tags")
    
    # Search for API URLs in scripts
    api_patterns = [
        r'["\'](/api/[^"\']+bulk[^"\']*)["\']',
        r'["\'](/api/[^"\']+deal[^"\']*)["\']',
        r'fetch\(["\'](/api/[^"\']+)["\']',
        r'axios\.get\(["\'](/api/[^"\']+)["\']',
        r'xhr\.open\(["\']GET["\'],\s*["\'](/api/[^"\']+)["\']',
    ]
    
    endpoints = set()
    
    for script in scripts:
        if script.string:
            for pattern in api_patterns:
                matches = re.findall(pattern, script.string, re.IGNORECASE)
                for match in matches:
                    endpoints.add(match)
    
    # Also search in inline JS and data attributes
    for pattern in api_patterns:
        matches = re.findall(pattern, response.text, re.IGNORECASE)
        for match in matches:
            endpoints.add(match)
    
    # Search for common endpoint patterns
    common_endpoints = [
        "/api/bulk-deal-block-deal",
        "/api/bulkDeals",
        "/api/bulk_deals",
        "/api/market-data/bulk-deal",
        "/api/reports/bulk-deals",
        "/api/series/bulk-deal",
        "/api/equity/bulk-deals",
    ]
    
    print(f"\n4. Testing common endpoints...")
    working_endpoints = []
    
    for endpoint in common_endpoints:
        test_url = f"{NSE_BASE}{endpoint}"
        try:
            resp = session.get(test_url, timeout=10)
            if resp.status_code == 200:
                print(f"   ✓ {endpoint} (Status: {resp.status_code}, Size: {len(resp.content)} bytes)")
                working_endpoints.append(endpoint)
            else:
                print(f"   - {endpoint} (Status: {resp.status_code})")
        except Exception as e:
            print(f"   - {endpoint} (Error: {e})")
    
    # Results
    print(f"\n{'=' * 60}")
    print("RESULTS")
    print(f"{'=' * 60}")
    
    if endpoints:
        print(f"\nDiscovered endpoints from page analysis:")
        for ep in endpoints:
            print(f"  - {ep}")
    
    if working_endpoints:
        print(f"\nWorking endpoints:")
        for ep in working_endpoints:
            print(f"  - {ep}")
    
    if not endpoints and not working_endpoints:
        print("\n⚠ No API endpoints found!")
        print("\nThis likely means:")
        print("1. NSE uses server-side rendering (no API)")
        print("2. API endpoints are obfuscated")
        print("3. Data is loaded via WebSocket")
        print("\nAlternative approaches:")
        print("1. Use browser automation (Selenium/Playwright)")
        print("2. Download CSV manually from the website")
        print("3. Use paid NSE data feed")


if __name__ == "__main__":
    find_api_endpoints()
