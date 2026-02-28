#!/usr/bin/env python3
"""
Debug Upstox API Responses

Direct API calls to understand what's being returned
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import requests
import json
from datetime import datetime
import pytz

# Get token
access_token = os.getenv('UPSTOX_ACCESS_TOKEN')
if not access_token:
    print("ERROR: UPSTOX_ACCESS_TOKEN not found")
    sys.exit(1)

print("=" * 80)
print("UPSTOX API DEBUG")
print("=" * 80)
print(f"\nToken: {access_token[:30]}...")

# Check time
ist = pytz.timezone('Asia/Kolkata')
now = datetime.now(ist)
print(f"Current time: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")

headers = {
    'Authorization': f'Bearer {access_token}',
    'Accept': 'application/json'
}

# Test 1: Get user profile
print("\n" + "=" * 80)
print("TEST 1: User Profile")
print("=" * 80)
try:
    response = requests.get(
        'https://api.upstox.com/v2/user/profile',
        headers=headers
    )
    print(f"Status: {response.status_code}")
    data = response.json()
    print(f"Response: {json.dumps(data, indent=2)}")
except Exception as e:
    print(f"Error: {e}")

# Test 2: Market quote for NIFTY index
print("\n" + "=" * 80)
print("TEST 2: NIFTY Index Quote")
print("=" * 80)

# Try different instrument keys for NIFTY
nifty_keys = [
    "NSE_INDEX|Nifty 50",
    "NSE_INDEX|NIFTY 50",
    "NSE_INDEX|Nifty50",
    "NSE_INDEX|NIFTY50",
    "NSE_INDEX|Nifty Bank",
    "NSE_INDEX|NIFTY BANK"
]

for key in nifty_keys:
    print(f"\nTrying: {key}")
    try:
        response = requests.get(
            f'https://api.upstox.com/v2/market-quote/quotes?instrument_key={key}',
            headers=headers
        )
        print(f"  Status: {response.status_code}")
        data = response.json()
        
        if response.status_code == 200 and data.get('status') == 'success':
            if data.get('data'):
                print(f"  ✓ SUCCESS!")
                print(f"  Data: {json.dumps(data, indent=4)}")
                break
            else:
                print(f"  Empty data: {data}")
        else:
            print(f"  Failed: {data}")
    except Exception as e:
        print(f"  Error: {e}")

# Test 3: Option chain
print("\n" + "=" * 80)
print("TEST 3: Option Chain")
print("=" * 80)

# Try NIFTY option chain
print("\nFetching NIFTY option chain...")
try:
    response = requests.get(
        'https://api.upstox.com/v2/option/chain?instrument_key=NSE_INDEX|Nifty%2050&expiry_date=2026-02-19',
        headers=headers
    )
    print(f"Status: {response.status_code}")
    data = response.json()
    print(f"Response keys: {data.keys()}")
    print(f"Status: {data.get('status')}")
    
    if data.get('data'):
        print(f"Data length: {len(data['data'])}")
        if len(data['data']) > 0:
            print(f"First item: {json.dumps(data['data'][0], indent=2)}")
    else:
        print(f"Full response: {json.dumps(data, indent=2)}")
        
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

# Test 4: Try getting market status
print("\n" + "=" * 80)
print("TEST 4: Market Status")
print("=" * 80)
try:
    response = requests.get(
        'https://api.upstox.com/v2/market/status/NSE',
        headers=headers
    )
    print(f"Status: {response.status_code}")
    data = response.json()
    print(f"Response: {json.dumps(data, indent=2)}")
except Exception as e:
    print(f"Error: {e}")

print("\n" + "=" * 80)
print("DEBUG COMPLETE")
print("=" * 80)
