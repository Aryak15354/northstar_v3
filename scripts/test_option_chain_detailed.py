#!/usr/bin/env python3
"""
Detailed Option Chain Investigation

Test different API endpoints and parameters to get option chain data
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import requests
import json
from datetime import datetime, date
import pytz

# Get token
access_token = os.getenv('UPSTOX_ACCESS_TOKEN')
if not access_token:
    print("ERROR: UPSTOX_ACCESS_TOKEN not found")
    sys.exit(1)

print("=" * 80)
print("OPTION CHAIN DETAILED INVESTIGATION")
print("=" * 80)

headers = {
    'Authorization': f'Bearer {access_token}',
    'Accept': 'application/json'
}

# Test different expiry dates
expiry_dates = [
    "2026-02-13",  # Tomorrow
    "2026-02-19",  # Next Thursday
    "2026-02-20",  # Next Friday
    "2026-02-26",  # Week after
]

# Test different instrument keys
instrument_keys = [
    "NSE_INDEX|Nifty 50",
    "NSE_INDEX|Nifty Bank",
    "NSE_FO|NIFTY",
    "NSE_FO|BANKNIFTY",
]

print("\nTesting Option Chain API...")
print("=" * 80)

for inst_key in instrument_keys:
    print(f"\n\nInstrument: {inst_key}")
    print("-" * 80)
    
    for expiry in expiry_dates:
        print(f"\n  Expiry: {expiry}")
        
        try:
            # URL encode the instrument key
            import urllib.parse
            encoded_key = urllib.parse.quote(inst_key)
            
            url = f'https://api.upstox.com/v2/option/chain?instrument_key={encoded_key}&expiry_date={expiry}'
            print(f"  URL: {url}")
            
            response = requests.get(url, headers=headers)
            print(f"  Status: {response.status_code}")
            
            data = response.json()
            
            if data.get('status') == 'success':
                chain_data = data.get('data', [])
                print(f"  ✓ Success! Contracts: {len(chain_data)}")
                
                if len(chain_data) > 0:
                    print(f"\n  First 3 contracts:")
                    for i, contract in enumerate(chain_data[:3]):
                        print(f"    {i+1}. {json.dumps(contract, indent=6)}")
                    break  # Found data, stop trying expiries for this instrument
                else:
                    print(f"  ⚠ Empty chain")
            else:
                print(f"  ✗ Failed: {data}")
                
        except Exception as e:
            print(f"  ✗ Error: {e}")

# Try the option contract endpoint directly
print("\n\n" + "=" * 80)
print("Testing Option Contract Endpoint")
print("=" * 80)

# Try to get a specific option contract
option_symbols = [
    "NSE_FO|NIFTY26FEB25800CE",
    "NSE_FO|NIFTY26FEB25800PE",
    "NSE_FO|NIFTY2621925800CE",
    "NSE_FO|NIFTY2621925800PE",
]

for symbol in option_symbols:
    print(f"\nTrying: {symbol}")
    try:
        import urllib.parse
        encoded = urllib.parse.quote(symbol)
        url = f'https://api.upstox.com/v2/market-quote/quotes?instrument_key={encoded}'
        
        response = requests.get(url, headers=headers)
        print(f"  Status: {response.status_code}")
        
        data = response.json()
        if data.get('status') == 'success' and data.get('data'):
            print(f"  ✓ SUCCESS! Found option contract")
            print(f"  Data: {json.dumps(data, indent=4)}")
            break
        else:
            print(f"  ✗ Not found: {data}")
    except Exception as e:
        print(f"  Error: {e}")

# Try market quote ltp endpoint
print("\n\n" + "=" * 80)
print("Testing Market Quote LTP Endpoint")
print("=" * 80)

try:
    url = 'https://api.upstox.com/v2/market-quote/ltp'
    params = {
        'instrument_key': 'NSE_INDEX|Nifty 50'
    }
    
    response = requests.get(url, headers=headers, params=params)
    print(f"Status: {response.status_code}")
    data = response.json()
    print(f"Response: {json.dumps(data, indent=2)}")
except Exception as e:
    print(f"Error: {e}")

print("\n" + "=" * 80)
print("INVESTIGATION COMPLETE")
print("=" * 80)
