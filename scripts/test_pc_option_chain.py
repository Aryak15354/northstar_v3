#!/usr/bin/env python3
"""
Test Put/Call Option Chain API
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
print("TESTING PUT/CALL OPTION CHAIN API")
print("=" * 80)

# Test NIFTY
underlying_key = "NSE_INDEX|Nifty 50"
expiry_date = "2026-02-19"

encoded_key = urllib.parse.quote(underlying_key)
url = f'https://api.upstox.com/v2/option/chain?instrument_key={encoded_key}&expiry_date={expiry_date}'

print(f"\nUnderlying Key: {underlying_key}")
print(f"Expiry Date: {expiry_date}")
print(f"URL: {url}")

response = requests.get(url, headers=headers)
print(f"Status: {response.status_code}")

data = response.json()
print(f"Response status: {data.get('status')}")

chain_data = data.get('data', [])
print(f"Strikes returned: {len(chain_data)}")

if len(chain_data) > 0:
    print(f"\n✓ SUCCESS! Option chain data received")
    print(f"\nFirst 3 strikes:")
    for i, strike_data in enumerate(chain_data[:3]):
        print(f"\n{i+1}. Strike: {strike_data.get('strike_price')}")
        print(f"   PCR: {strike_data.get('pcr')}")
        print(f"   Spot: {strike_data.get('underlying_spot_price')}")
        
        call = strike_data.get('call_options', {})
        if call:
            call_market = call.get('market_data', {})
            print(f"   Call LTP: {call_market.get('ltp')}, OI: {call_market.get('oi')}")
        
        put = strike_data.get('put_options', {})
        if put:
            put_market = put.get('market_data', {})
            print(f"   Put LTP: {put_market.get('ltp')}, OI: {put_market.get('oi')}")
else:
    print(f"\n✗ Empty option chain")
    print(f"Full response: {json.dumps(data, indent=2)}")

print("\n" + "=" * 80)
