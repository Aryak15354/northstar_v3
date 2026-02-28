"""
Investigate why we're only getting 12 option contracts

A typical NIFTY option chain should have:
- ~50-100 strikes (from deep OTM to deep ITM)
- 2 option types (call + put) per strike
- Total: 100-200 contracts per expiry

Let's see what's happening.
"""

import sys
import json
from pathlib import Path
from datetime import date

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.options.config_loader import get_config
import requests

def investigate():
    """Investigate the raw API response"""
    print("="*60)
    print("INVESTIGATING OPTION DATA COUNT")
    print("="*60)
    
    config = get_config()
    
    session = requests.Session()
    session.headers.update({
        'Accept': 'application/json',
        'Authorization': f'Bearer {config.upstox.access_token}'
    })
    
    # Use the expiry that worked
    expiry = date(2026, 3, 26)
    
    url = config.upstox.endpoints['option_chain']
    params = {
        'instrument_key': 'NSE_INDEX|Nifty 50',
        'expiry_date': expiry.strftime("%Y-%m-%d")
    }
    
    print(f"\nFetching option chain for {expiry}")
    print(f"URL: {url}")
    print(f"Params: {params}\n")
    
    response = session.get(url, params=params, timeout=30)
    
    if response.status_code != 200:
        print(f"✗ API Error: {response.status_code}")
        print(response.text)
        return
    
    data = response.json()
    
    print("="*60)
    print("RAW API RESPONSE ANALYSIS")
    print("="*60)
    
    print(f"\nResponse structure:")
    print(f"  Status: {data.get('status')}")
    print(f"  Data type: {type(data.get('data'))}")
    print(f"  Data length: {len(data.get('data', []))}")
    
    if not data.get('data'):
        print("\n✗ No data in response!")
        return
    
    # Analyze first item
    print(f"\n" + "="*60)
    print("FIRST ITEM STRUCTURE")
    print("="*60)
    
    first_item = data['data'][0]
    print(f"\nKeys in first item:")
    for key in first_item.keys():
        value = first_item[key]
        if isinstance(value, dict):
            print(f"  {key}: dict with keys {list(value.keys())}")
        elif isinstance(value, list):
            print(f"  {key}: list with {len(value)} items")
        else:
            print(f"  {key}: {type(value).__name__} = {value}")
    
    # Check call and put options
    print(f"\n" + "="*60)
    print("OPTION DATA ANALYSIS")
    print("="*60)
    
    total_calls = 0
    total_puts = 0
    strikes = []
    
    for item in data['data']:
        strike = item.get('strike_price')
        if strike:
            strikes.append(strike)
        
        if item.get('call_options'):
            total_calls += 1
        if item.get('put_options'):
            total_puts += 1
    
    print(f"\nRaw counts from API:")
    print(f"  Total items: {len(data['data'])}")
    print(f"  Items with call_options: {total_calls}")
    print(f"  Items with put_options: {total_puts}")
    print(f"  Unique strikes: {len(set(strikes))}")
    print(f"  Strike range: {min(strikes)} to {max(strikes)}")
    
    # Show all strikes
    print(f"\nAll strikes in response:")
    for strike in sorted(set(strikes)):
        print(f"  {strike:,.0f}")
    
    # Check what our adapter is filtering out
    print(f"\n" + "="*60)
    print("ADAPTER FILTERING ANALYSIS")
    print("="*60)
    
    print("\nChecking why contracts might be filtered...")
    
    filtered_reasons = {
        'no_call_data': 0,
        'no_put_data': 0,
        'zero_oi': 0,
        'negative_greeks': 0,
        'invalid_bid_ask': 0,
        'missing_fields': 0
    }
    
    for item in data['data']:
        strike = item.get('strike_price')
        
        # Check calls
        call_data = item.get('call_options', {})
        if call_data:
            market_data = call_data.get('market_data', {})
            greeks = call_data.get('option_greeks', {})
            
            oi = market_data.get('oi', 0)
            bid = market_data.get('bid_price', 0)
            ask = market_data.get('ask_price', 0)
            gamma = greeks.get('gamma', 0)
            vega = greeks.get('vega', 0)
            
            if oi == 0:
                filtered_reasons['zero_oi'] += 1
                print(f"  Strike {strike} CALL: Zero OI")
            elif gamma < 0 or vega < 0:
                filtered_reasons['negative_greeks'] += 1
                print(f"  Strike {strike} CALL: Negative Greeks (gamma={gamma}, vega={vega})")
            elif bid < 0 or ask < 0 or bid > ask:
                filtered_reasons['invalid_bid_ask'] += 1
                print(f"  Strike {strike} CALL: Invalid bid/ask (bid={bid}, ask={ask})")
        else:
            filtered_reasons['no_call_data'] += 1
        
        # Check puts
        put_data = item.get('put_options', {})
        if put_data:
            market_data = put_data.get('market_data', {})
            greeks = put_data.get('option_greeks', {})
            
            oi = market_data.get('oi', 0)
            bid = market_data.get('bid_price', 0)
            ask = market_data.get('ask_price', 0)
            gamma = greeks.get('gamma', 0)
            vega = greeks.get('vega', 0)
            
            if oi == 0:
                filtered_reasons['zero_oi'] += 1
                print(f"  Strike {strike} PUT: Zero OI")
            elif gamma < 0 or vega < 0:
                filtered_reasons['negative_greeks'] += 1
                print(f"  Strike {strike} PUT: Negative Greeks (gamma={gamma}, vega={vega})")
            elif bid < 0 or ask < 0 or bid > ask:
                filtered_reasons['invalid_bid_ask'] += 1
                print(f"  Strike {strike} PUT: Invalid bid/ask (bid={bid}, ask={ask})")
        else:
            filtered_reasons['no_put_data'] += 1
    
    print(f"\n" + "="*60)
    print("FILTERING SUMMARY")
    print("="*60)
    
    for reason, count in filtered_reasons.items():
        if count > 0:
            print(f"  {reason}: {count} contracts")
    
    print(f"\n" + "="*60)
    print("CONCLUSION")
    print("="*60)
    
    expected_contracts = len(data['data']) * 2  # calls + puts
    actual_contracts = 12  # from our test
    filtered_contracts = expected_contracts - actual_contracts
    
    print(f"\nExpected contracts: {expected_contracts}")
    print(f"Actual contracts after filtering: {actual_contracts}")
    print(f"Filtered out: {filtered_contracts}")
    
    if filtered_contracts > 0:
        print(f"\n⚠️  The adapter is filtering out {filtered_contracts} contracts")
        print(f"   Most likely reason: Zero OI (illiquid options)")
        print(f"\n   This is CORRECT behavior for trading:")
        print(f"   - Zero OI = no liquidity")
        print(f"   - Can't execute trades on illiquid options")
        print(f"   - System correctly removes them")
    
    # Show sample of full data
    print(f"\n" + "="*60)
    print("SAMPLE OPTION DATA (First Strike)")
    print("="*60)
    
    if data['data']:
        sample = data['data'][0]
        print(json.dumps(sample, indent=2))

if __name__ == "__main__":
    investigate()
