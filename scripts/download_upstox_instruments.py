#!/usr/bin/env python3
"""
Download Upstox instruments file and find correct instrument keys for stock options
"""

import requests
import json
import pandas as pd
from pathlib import Path

def download_instruments():
    """Download complete NSE instruments file"""
    url = "https://assets.upstox.com/market-quote/instruments/exchange/complete.json.gz"
    
    print("Downloading Upstox instruments file...")
    print(f"URL: {url}")
    
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    
    # The file is gzipped JSON
    import gzip
    import io
    
    data = gzip.decompress(response.content)
    instruments = json.loads(data)
    
    print(f"✓ Downloaded {len(instruments)} instruments")
    
    # Save to file
    output_path = Path("data/instruments/upstox_complete.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump(instruments, f)
    
    print(f"✓ Saved to {output_path}")
    
    return instruments

def find_stock_options(instruments, symbol, expiry_date=None):
    """Find option contracts for a stock"""
    options = []
    
    for inst in instruments:
        # Look for NSE_FO segment with OPTSTK type
        if (inst.get('segment') == 'NSE_FO' and 
            inst.get('instrument_type') == 'OPTSTK' and
            symbol in inst.get('name', '')):
            
            # Filter by expiry if provided
            if expiry_date is None or inst.get('expiry') == expiry_date:
                options.append({
                    'instrument_key': inst['instrument_key'],
                    'name': inst['name'],
                    'trading_symbol': inst['trading_symbol'],
                    'expiry': inst.get('expiry'),
                    'strike': inst.get('strike'),
                    'option_type': inst.get('option_type'),
                    'lot_size': inst.get('lot_size')
                })
    
    return options

def main():
    print("=== Upstox Instruments Downloader ===\n")
    
    # Download instruments
    instruments = download_instruments()
    
    # Analyze structure
    print(f"\n=== ANALYSIS ===")
    
    # Count by segment
    segments = {}
    for inst in instruments:
        seg = inst.get('segment', 'unknown')
        segments[seg] = segments.get(seg, 0) + 1
    
    print(f"\nInstruments by segment:")
    for seg, count in sorted(segments.items(), key=lambda x: -x[1]):
        print(f"  {seg}: {count:,}")
    
    # Count NSE_FO by instrument type
    print(f"\nNSE_FO by instrument type:")
    nse_fo_types = {}
    for inst in instruments:
        if inst.get('segment') == 'NSE_FO':
            itype = inst.get('instrument_type', 'unknown')
            nse_fo_types[itype] = nse_fo_types.get(itype, 0) + 1
    
    for itype, count in sorted(nse_fo_types.items(), key=lambda x: -x[1]):
        print(f"  {itype}: {count:,}")
    
    # Find RELIANCE options as example
    print(f"\n=== EXAMPLE: RELIANCE OPTIONS ===")
    reliance_options = find_stock_options(instruments, "RELIANCE")
    
    if reliance_options:
        print(f"Found {len(reliance_options)} RELIANCE option contracts")
        
        # Show unique expiries
        expiries = sorted(set(opt['expiry'] for opt in reliance_options if opt['expiry']))
        print(f"Expiries: {expiries[:5]}...")  # Show first 5
        
        # Show sample contracts
        print(f"\nSample contracts:")
        for opt in reliance_options[:5]:
            print(f"  {opt['instrument_key']}")
            print(f"    Symbol: {opt['trading_symbol']}")
            print(f"    Expiry: {opt['expiry']}, Strike: {opt['strike']}, Type: {opt['option_type']}")
    else:
        print("No RELIANCE options found")
    
    print(f"\n✓ Instruments file ready for use")
    print(f"✓ Use this file to find correct instrument_key values")

if __name__ == "__main__":
    main()
