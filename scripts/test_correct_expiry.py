#!/usr/bin/env python3
import sys, os, requests, json, urllib.parse

access_token = os.getenv('UPSTOX_ACCESS_TOKEN')
headers = {'Authorization': f'Bearer {access_token}', 'Accept': 'application/json'}

print("=" * 80)
print("TESTING WITH CORRECT EXPIRY - TUESDAY 2026-02-17")
print("=" * 80)

underlying_key = "NSE_INDEX|Nifty 50"
expiry_date = "2026-02-17"  # TUESDAY!

encoded_key = urllib.parse.quote(underlying_key)
url = f'https://api.upstox.com/v2/option/chain?instrument_key={encoded_key}&expiry_date={expiry_date}'

print(f"\nExpiry: {expiry_date} (TUESDAY - NIFTY expires on Tuesdays!)")
response = requests.get(url, headers=headers)
data = response.json()

chain_data = data.get('data', [])
print(f"Contracts: {len(chain_data)}")

if len(chain_data) > 0:
    print(f"\n✓ SUCCESS!")
    for i, c in enumerate(chain_data[:3]):
        print(f"{i+1}. Strike {c.get('strike_price')} {c.get('option_type')}: LTP={c.get('market_data',{}).get('ltp')}")
else:
    print("✗ Empty")
