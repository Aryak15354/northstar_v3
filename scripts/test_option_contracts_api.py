#!/usr/bin/env python3
"""
Test option chain with CORRECT expiry date (Tuesday, not Thursday)
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
print("TESTING OPTION CHAIN WITH CORRECT EXPIRY (TUESDAY)")
print("=" * 80)

# Use the correct expiry - NIFTY expires on TUESDAY, not Thursday!
underlying_key = "NSE_INDEX|Nifty 50"
expiry_date = "2026-02-17"  # Next Tuesday

encoded_key = urllib.parse.quote(underlying_key)
url = f'https://api.upstox_date={expiry_date}'

print(f"\nUnderlying Key: {underlying_key}")
print(f"Expiry Date: {expiry_date} (TUESDAY - correct day!)")
print(f"URL: {url}")

response = requests.get(url, headers=headers)
print(f"\nStatus: {response.status_code}")

data = response.json()
print(f"Response status: {data.get('status')}")

chain_data = data.get('data', [])
print(f"Contracts returned: {len(chain_data)}")

if len(chain_data) > 0:
    print(f"\n✓ SUCCESS! Option chain data received")
    print(f"\nFirst 5 contracts:")
    for i, contract in enumerate(chain_data[:5]):
        print(f"\n{i+1}. Strike: {contract.get('strike_price')}, Type: {contract.get('option_type')}")
        print(f"   LTP: {contract.get('market_data', {}).get('ltp')}")
        print(f"   IV: {contract.get('option_greeks', {}).get('iv')}")
        print(f"   Delta: {contract.get('option_greeks', {}).get('delta')}")
else:
    print(f"\n✗ Empty option chain")
    print(f"Full response: {json.dumps(data, indent=2)}")

# Also test BANKNIFTY (expires Wednesday)
print("\n\n" + "=" * 80)
print("TESTING BANKNIFTY (expires WEDNESDAY)")
print("=" * 80)

banknifty_key = "NSE_INDEX|Nifty Bank"
banknifty_expiry = "2026-02-18"  # Next Wednesday

encoded_key = urllib.parse.quote(banknifty_key)
url = f'https://api.upstox.com/v2/option/chain?instrument_key={encoded_key}&expiry_date={banknifty_expiry}'

print(f"\nUnderlying Key: {banknifty_key}")
int(f"Expiry Date: {banknifty_expiry} (WEDNESDAY)")

response = requests.get(url, headersders)
data = response.json()

chain_data = data.get('data', [])
print(f"Contracts returned: {len(chain_data)}")

if len(chain_data) > 0:
    print(f"✓ BANKNIFTY option chain working!")
else:
    print(f"✗ Empty BANKNIFTY chain")
