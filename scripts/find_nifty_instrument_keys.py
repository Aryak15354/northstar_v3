#!/usr/bin/env python3
"""
Find correct NIFTY instrument keys from Upstox master file
"""

import requests
import json

print("Downloading Upstox instrument master file...")
print("=" * 80)

# Download the complete instrument file (all exchanges)
url = "https://assets.upstox.com/market-quote/instruments/exchange/complete.json.gz"

try:
    import gzip
    import io
    
    response = requests.get(url)
    print(f"Downloaded {len(response.content)} bytes")
    
    # Decompress gzip
    with gzip.GzipFile(fileobj=io.BytesIO(response.content)) as f:
        data = json.load(f)
    
    print(f"Loaded {len(data)} instruments")
    
    # Find NIFTY related instruments
    print("\n" + "=" * 80)
    print("NIFTY INDEX:")
    print("=" * 80)
    
    for inst in data:
        if inst.get('name', '').upper() == 'NIFTY 50' or inst.get('trading_symbol', '').upper() == 'NIFTY 50':
            print(json.dumps(inst, indent=2))
    
    print("\n" + "=" * 80)
    print("NIFTY OPTIONS (first 10):")
    print("=" * 80)
    
    nifty_options = [inst for inst in data if 
                     'NIFTY' in inst.get('trading_symbol', '').upper() and
                     inst.get('segment') == 'NSE_FO']
    
    print(f"Found {len(nifty_options)} NIFTY FO contracts")
    
    # Show unique instrument types
    inst_types = set(inst.get('instrument_type') for inst in nifty_options)
    print(f"Instrument types: {inst_types}")
    
    # Filter for options only
    nifty_options = [inst for inst in nifty_options if inst.get('instrument_type') in ['OPTIDX', 'CE', 'PE']]
    print(f"NIFTY options after filtering: {len(nifty_options)}")
    
    for inst in nifty_options[:10]:
        print(f"\n{inst.get('trading_symbol')}:")
        print(f"  instrument_key: {inst.get('instrument_key')}")
        print(f"  name: {inst.get('name')}")
        print(f"  expiry: {inst.get('expiry')}")
        print(f"  strike: {inst.get('strike')}")
        print(f"  option_type: {inst.get('option_type')}")
    
    # Find BANKNIFTY
    print("\n" + "=" * 80)
    print("BANKNIFTY INDEX:")
    print("=" * 80)
    
    for inst in data:
        if 'BANK' in inst.get('name', '').upper() and 'NIFTY' in inst.get('name', '').upper() and inst.get('instrument_type') == 'INDEX':
            print(json.dumps(inst, indent=2))
    
    # Find what underlying_key to use
    print("\n" + "=" * 80)
    print("CHECKING FOR UNDERLYING_KEY FIELD:")
    print("=" * 80)
    
    sample_option = nifty_options[0] if nifty_options else None
    if sample_option:
        print("Sample option contract fields:")
        for key in sample_option.keys():
            print(f"  {key}: {sample_option[key]}")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
