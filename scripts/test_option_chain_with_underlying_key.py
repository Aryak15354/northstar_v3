#!/usr/bin/env python3
"""
Test option chain with correct underlying_key
"""

import sys
import os
import requests
import json
import urllib.parse

access_token = os.getenv('UPSTOX_ACCESS_TOKEN')
if not access_token:
    print("ERROR: UPSTOX_ACCESS_TOKEN not found")
    sys.exit(1)

headers = {
    'Authorization': f'Bearer {access_token}',
    'Accept': 'application/json'
}

print("=" * 80)
print("TESTING OPTION CHAIN WITH UNDERLYING_KEY")
print("=" * 80)

# Use the underlying_key from the instrument master
underlying_key = "NSE_INDEX|Nifty 50"
expiry_date = "2026-02-19"

encoded_key = urllib.parse.quote(underlying_key)
url = f'https://api.upstox.com/v2/option/chain?instrument_key={encoded_key}&expiry_date={expiry_date}'

print(f"\nUnderlying Key: {underlying_key}")
print(f"Expiry Date: {expiry_date}")
print(f"URL: {url}")

response = requests.get(url, headers=headers)
print(f"\nStatus: {response.status_code}")

data = response.json()
print(f"Response status: {data.get('status')}")

chain_data = data.get('data', [])
print(f"Contracts returned: {len(chain_data)}")

if len(chain_data) > 0:
    print(f"\n✓ SUCCESS! Option chain data received")
    print(f"\nFirst 3 contracts:")
    for i, contract in enumerate(chain_data[:3]):
        print(f"\n{i+1}. {json.dumps(contract, indent=2)}")
else:
    print(f"\n✗ Empty option chain")
    print(f"Full response: {json.dumps(data, indent=2)}")
