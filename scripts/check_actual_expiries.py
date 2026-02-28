#!/usr/bin/env python3
"""
Check what expiry dates actually exist in the Upstox instrument master
"""

import requests
import json
import gzip
import io
from datetime import datetime

print("Downloading instrument master...")
url = "https://assets.upstox.com/market-quote/instruments/exchange/complete.json.gz"

response = requests.get(url)
with gzip.GzipFile(fileobj=io.BytesIO(response.content)) as f:
    data = json.load(f)

print(f"Loaded {len(data)} instruments")

# Find NIFTY options and their expiries
nifty_options = [inst for inst in data if 
                 'NIFTY' in inst.get('trading_symbol', '').upper() and
                 inst.get('segment') == 'NSE_FO' and
                 inst.get('instrument_type') in ['CE', 'PE'] and
                 'BANK' not in inst.get('trading_symbol', '').upper()]

print(f"\nFound {len(nifty_options)} NIFTY option contracts")

# Get unique expiries
expiries = set()
for opt in nifty_options:
    expiry_ts = opt.get('expiry')
    if expiry_ts:
        # Convert milliseconds to datetime
        expiry_dt = datetime.fromtimestamp(expiry_ts / 1000)
        expiries.add(expiry_dt.strftime('%Y-%m-%d'))

expiries = sorted(list(expiries))

print(f"\nAvailable NIFTY expiry dates ({len(expiries)} total):")
print("=" * 80)

# Show first 20 expiries
for i, expiry in enumerate(expiries[:20]):
    # Parse date
    exp_dt = datetime.strptime(expiry, '%Y-%m-%d')
    day_name = exp_dt.strftime('%A')
    
    # Count contracts for this expiry
    count = sum(1 for opt in nifty_options if 
                datetime.fromtimestamp(opt.get('expiry', 0) / 1000).strftime('%Y-%m-%d') == expiry)
    
    print(f"{i+1:2d}. {expiry} ({day_name}) - {count} contracts")

# Check today's date
today = datetime.now().strftime('%Y-%m-%d')
print(f"\nToday's date: {today}")

# Find nearest expiry
print(f"\nNearest upcoming expiries:")
for expiry in expiries[:5]:
    if expiry >= today:
        print(f"  {expiry}")
