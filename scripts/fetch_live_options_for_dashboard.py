#!/usr/bin/env python3
"""
Fetch live NIFTY options data from Upstox and save for dashboard
"""

import sys
sys.path.insert(0, 'src')

import os
import pandas as pd
import requests
from datetime import datetime, timedelta
import json
from pathlib import Path

BASE_URL = "https://api.upstox.com/v2"

def resolve_access_token() -> str:
    """Load the Upstox token from the environment or local .env.options file."""
    token = os.getenv("UPSTOX_ACCESS_TOKEN", "").strip()
    env_file = Path(os.getenv("UPSTOX_ENV_FILE", ".env.options"))
    if not token and env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            key, sep, value = line.partition("=")
            if sep and key.strip() == "UPSTOX_ACCESS_TOKEN":
                token = value.strip()
                break
    if not token or token in {"your_access_token_here", "ROTATE_REQUIRED"}:
        raise RuntimeError("Set UPSTOX_ACCESS_TOKEN or update .env.options before fetching live options.")
    return token

def get_option_chain(instrument_key: str, expiry_date: str):
    """Fetch option chain data from Upstox"""
    url = f"{BASE_URL}/option/chain"
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {resolve_access_token()}"
    }
    params = {
        "instrument_key": instrument_key,
        "expiry_date": expiry_date
    }
    
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    return response.json()

def get_market_quote(instrument_keys: list):
    """Get market quotes for multiple instruments"""
    url = f"{BASE_URL}/market-quote/quotes"
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {resolve_access_token()}"
    }
    params = {
        "instrument_key": ",".join(instrument_keys)
    }
    
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    return response.json()

def main():
    print("=== Fetching Live NIFTY Options Data ===\n")
    
    # NIFTY 50 instrument key
    nifty_key = "NSE_INDEX|Nifty 50"
    
    # Get next Tuesday (weekly expiry - changed from Thursday in Sept 2025)
    today = datetime.now()
    days_ahead = 1 - today.weekday()  # Tuesday is 1 (Monday=0, Tuesday=1, ...)
    if days_ahead <= 0:
        days_ahead += 7
    next_tuesday = today + timedelta(days=days_ahead)
    expiry_date = next_tuesday.strftime("%Y-%m-%d")
    
    print(f"Using expiry date (next Tuesday): {expiry_date}")
    
    try:
        # Get option chain
        print("Fetching option chain...")
        chain_data = get_option_chain(nifty_key, expiry_date)
        
        if 'data' not in chain_data:
            print(f"Error: No data in response: {chain_data}")
            return
        
        # Extract option chain data - data is a list of strikes
        data = chain_data['data']
        
        if not isinstance(data, list):
            print(f"Unexpected data format: {type(data)}")
            print(f"Data: {data}")
            return
        
        print(f"Found {len(data)} strike prices")
        
        # Build DataFrame
        rows = []
        instrument_keys = []
        
        for strike_data in data:
            strike = strike_data.get('strike_price')
            expiry = strike_data.get('expiry', expiry_date)
            
            # Call option
            call_data = strike_data.get('call_options', {})
            if call_data:
                call_key = call_data.get('instrument_key')
                if call_key:
                    instrument_keys.append(call_key)
                    rows.append({
                        'strike': strike,
                        'expiry': expiry,
                        'option_type': 'CE',
                        'instrument_key': call_key
                    })
            
            # Put option
            put_data = strike_data.get('put_options', {})
            if put_data:
                put_key = put_data.get('instrument_key')
                if put_key:
                    instrument_keys.append(put_key)
                    rows.append({
                        'strike': strike,
                        'expiry': expiry,
                        'option_type': 'PE',
                        'instrument_key': put_key
                    })
        
        print(f"\nFetching quotes for {len(instrument_keys)} options...")
        
        # Get market quotes in batches (API limit)
        batch_size = 500
        all_quotes = {}
        
        for i in range(0, len(instrument_keys), batch_size):
            batch = instrument_keys[i:i+batch_size]
            print(f"  Batch {i//batch_size + 1}: {len(batch)} instruments")
            quotes_response = get_market_quote(batch)
            
            if 'data' in quotes_response:
                all_quotes.update(quotes_response['data'])
        
        print(f"Received quotes for {len(all_quotes)} instruments")
        
        # Enrich rows with quote data
        enriched_rows = []
        for row in rows:
            key = row['instrument_key']
            if key in all_quotes:
                quote = all_quotes[key]
                
                # Extract relevant fields
                ohlc = quote.get('ohlc', {})
                greeks = quote.get('option_greeks', {})  # Changed from 'greeks'
                
                enriched_rows.append({
                    'strike': row['strike'],
                    'expiry': row['expiry'],
                    'option_type': row['option_type'],
                    'instrument_key': key,
                    'ltp': quote.get('last_price', 0),
                    'bid': quote.get('bid_price', 0),  # Changed from ohlc
                    'ask': quote.get('ask_price', 0),  # Changed from ohlc
                    'volume': quote.get('volume', 0),
                    'oi': quote.get('oi', 0),
                    'iv': greeks.get('iv', 0) if greeks else 0,
                    'delta': greeks.get('delta', 0) if greeks else 0,
                    'gamma': greeks.get('gamma', 0) if greeks else 0,
                    'theta': greeks.get('theta', 0) if greeks else 0,
                    'vega': greeks.get('vega', 0) if greeks else 0,
                })
            else:
                # Add row even without quote data
                enriched_rows.append({
                    'strike': row['strike'],
                    'expiry': row['expiry'],
                    'option_type': row['option_type'],
                    'instrument_key': key,
                    'ltp': 0,
                    'bid': 0,
                    'ask': 0,
                    'volume': 0,
                    'oi': 0,
                    'iv': 0,
                    'delta': 0,
                    'gamma': 0,
                    'theta': 0,
                    'vega': 0,
                })
        
        # Create DataFrame
        df = pd.DataFrame(enriched_rows)
        
        print(f"\n=== Options Data Summary ===")
        print(f"Total options: {len(df)}")
        print(f"Strikes: {df['strike'].nunique()}")
        print(f"Expiries: {df['expiry'].nunique()}")
        print(f"\nSample data:")
        print(df.head(10))
        
        # Save to parquet
        output_path = Path("data/options/live_option_chain.parquet")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(output_path, index=False)
        print(f"\n✓ Saved to {output_path}")
        
        # Also save summary for dashboard
        summary = {
            'timestamp': datetime.now().isoformat(),
            'total_options': len(df),
            'strikes': int(df['strike'].nunique()),
            'expiries': df['expiry'].unique().tolist(),
            'total_volume': int(df['volume'].sum()),
            'total_oi': int(df['oi'].sum()),
            'atm_strike': int(df['strike'].median()),
        }
        
        summary_path = Path("data/options/live_options_summary.json")
        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=2)
        print(f"✓ Saved summary to {summary_path}")
        
        # Create aggregated greeks for dashboard
        greeks_df = df.groupby('option_type').agg({
            'delta': 'sum',
            'gamma': 'sum',
            'theta': 'sum',
            'vega': 'sum',
            'oi': 'sum',
            'volume': 'sum'
        }).reset_index()
        
        greeks_path = Path("data/options/live_greeks.parquet")
        greeks_df.to_parquet(greeks_path, index=False)
        print(f"✓ Saved greeks to {greeks_path}")
        
        print("\n=== SUCCESS ===")
        print("Live options data fetched and saved for dashboard")
        
    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error: {e}")
        print(f"Response: {e.response.text if hasattr(e, 'response') else 'N/A'}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
