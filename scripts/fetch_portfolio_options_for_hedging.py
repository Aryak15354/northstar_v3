#!/usr/bin/env python3
"""
Fetch options data for portfolio stocks to enable hedging and risk management
Integrates with valuation engine to identify undervalued opportunities
"""

import sys
sys.path.insert(0, 'src')

import os
import pandas as pd
import requests
import yaml
from datetime import datetime, timedelta
import json
from pathlib import Path
from typing import List, Dict

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

def load_stock_config():
    """Load stock options configuration"""
    with open('config/stock_options_mapping.yaml') as f:
        return yaml.safe_load(f)

def get_portfolio_stocks():
    """Get stocks from current portfolio (placeholder - integrate with your portfolio system)"""
    # TODO: Integrate with your actual portfolio/ledger system
    # For now, return top liquid stocks
    config = load_stock_config()
    return config['recommended_for_beginners'][:10]  # Top 10 liquid stocks

def get_next_tuesday():
    """Get next Tuesday expiry date"""
    today = datetime.now()
    days_ahead = 1 - today.weekday()  # Tuesday is 1
    if days_ahead <= 0:
        days_ahead += 7
    return (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

def get_last_thursday_of_month():
    """Get last Thursday of current month (monthly expiry for stocks)"""
    today = datetime.now()
    # Get last day of month
    if today.month == 12:
        last_day = datetime(today.year + 1, 1, 1) - timedelta(days=1)
    else:
        last_day = datetime(today.year, today.month + 1, 1) - timedelta(days=1)
    
    # Find last Thursday
    while last_day.weekday() != 3:  # 3 = Thursday
        last_day -= timedelta(days=1)
    
    return last_day.strftime("%Y-%m-%d")

def get_option_chain(instrument_key: str, expiry_date: str):
    """Fetch option chain for a stock"""
    url = f"{BASE_URL}/option/chain"
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {resolve_access_token()}"
    }
    params = {
        "instrument_key": instrument_key,
        "expiry_date": expiry_date
    }
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        print(f"  HTTP Error {e.response.status_code}: {e.response.text[:200]}")
        return None
    except Exception as e:
        print(f"  Error fetching chain: {e}")
        return None

def get_market_quote(instrument_keys: List[str]):
    """Get market quotes for multiple instruments"""
    if not instrument_keys:
        return {}
    
    url = f"{BASE_URL}/market-quote/quotes"
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {resolve_access_token()}"
    }
    params = {
        "instrument_key": ",".join(instrument_keys[:500])  # API limit
    }
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data.get('data', {})
    except Exception as e:
        print(f"  Error fetching quotes: {e}")
        return {}

def fetch_stock_options(symbol: str, stock_info: Dict, expiry_date: str):
    """Fetch options for a single stock"""
    # For options, use NSE_FO segment with symbol, not NSE_EQ with ISIN
    instrument_key = f"NSE_FO|{symbol}"
    
    print(f"\n{symbol} ({stock_info['name']})")
    print(f"  Instrument: {instrument_key}")
    
    # Get option chain
    chain_data = get_option_chain(instrument_key, expiry_date)
    if not chain_data:
        print(f"  ✗ API request failed")
        return None
    
    if 'data' not in chain_data:
        print(f"  ✗ No 'data' key in response")
        print(f"  Response keys: {list(chain_data.keys())}")
        if 'status' in chain_data:
            print(f"  Status: {chain_data['status']}")
        if 'errors' in chain_data:
            print(f"  Errors: {chain_data['errors']}")
        return None
    
    data = chain_data['data']
    if not isinstance(data, list):
        print(f"  ✗ Data is not a list, type: {type(data)}")
        print(f"  Data: {str(data)[:200]}")
        return None
    
    if len(data) == 0:
        print(f"  ✗ Empty option chain (0 strikes)")
        return None
    
    print(f"  ✓ Found {len(data)} strikes")
    
    # Build option list
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
                    'symbol': symbol,
                    'strike': strike,
                    'expiry': expiry,
                    'option_type': 'CE',
                    'instrument_key': call_key,
                    'lot_size': stock_info.get('lot_size', 0)
                })
        
        # Put option
        put_data = strike_data.get('put_options', {})
        if put_data:
            put_key = put_data.get('instrument_key')
            if put_key:
                instrument_keys.append(put_key)
                rows.append({
                    'symbol': symbol,
                    'strike': strike,
                    'expiry': expiry,
                    'option_type': 'PE',
                    'instrument_key': put_key,
                    'lot_size': stock_info.get('lot_size', 0)
                })
    
    # Get quotes
    print(f"  Fetching quotes for {len(instrument_keys)} options...")
    quotes = get_market_quote(instrument_keys)
    
    # Enrich with quote data
    enriched_rows = []
    for row in rows:
        key = row['instrument_key']
        if key in quotes:
            quote = quotes[key]
            greeks = quote.get('option_greeks', {})
            
            enriched_rows.append({
                **row,
                'ltp': quote.get('last_price', 0),
                'bid': quote.get('bid_price', 0),
                'ask': quote.get('ask_price', 0),
                'volume': quote.get('volume', 0),
                'oi': quote.get('oi', 0),
                'iv': greeks.get('iv', 0) if greeks else 0,
                'delta': greeks.get('delta', 0) if greeks else 0,
                'gamma': greeks.get('gamma', 0) if greeks else 0,
                'theta': greeks.get('theta', 0) if greeks else 0,
                'vega': greeks.get('vega', 0) if greeks else 0,
            })
        else:
            enriched_rows.append({
                **row,
                'ltp': 0, 'bid': 0, 'ask': 0, 'volume': 0, 'oi': 0,
                'iv': 0, 'delta': 0, 'gamma': 0, 'theta': 0, 'vega': 0,
            })
    
    print(f"  ✓ Enriched {len(enriched_rows)} options")
    return enriched_rows

def main():
    print("=== Portfolio Options Fetcher for Hedging ===\n")
    print("This script fetches options data for stocks in your portfolio")
    print("to enable hedging, risk management, and profit opportunities.\n")
    
    # Load configuration
    config = load_stock_config()
    stocks_config = config['stocks']
    
    # Get portfolio stocks (or use recommended)
    portfolio_stocks = get_portfolio_stocks()
    print(f"Portfolio stocks to fetch: {', '.join(portfolio_stocks)}\n")
    
    # Get expiry date - stocks have monthly expiry (last Thursday)
    expiry_date = get_last_thursday_of_month()
    print(f"Expiry date: {expiry_date} (last Thursday of month - monthly expiry)\n")
    print("=" * 60)
    
    # Fetch options for each stock
    all_options = []
    successful = 0
    failed = 0
    
    for symbol in portfolio_stocks:
        if symbol not in stocks_config:
            print(f"\n{symbol}: ✗ Not in configuration")
            failed += 1
            continue
        
        stock_info = stocks_config[symbol]
        options = fetch_stock_options(symbol, stock_info, expiry_date)
        
        if options:
            all_options.extend(options)
            successful += 1
        else:
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"\n=== SUMMARY ===")
    print(f"Stocks processed: {successful + failed}")
    print(f"  Successful: {successful}")
    print(f"  Failed: {failed}")
    print(f"Total options fetched: {len(all_options)}")
    
    if not all_options:
        print("\n✗ No options data fetched")
        return
    
    # Create DataFrame
    df = pd.DataFrame(all_options)
    
    print(f"\n=== OPTIONS DATA ===")
    print(f"Stocks: {df['symbol'].nunique()}")
    print(f"Total options: {len(df)}")
    print(f"Strikes per stock: {len(df) / df['symbol'].nunique():.0f} avg")
    
    # Save to parquet
    output_path = Path("data/options/portfolio_options.parquet")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output_path, index=False)
    print(f"\n✓ Saved to {output_path}")
    
    # Create summary by stock
    summary = df.groupby('symbol').agg({
        'strike': 'count',
        'volume': 'sum',
        'oi': 'sum',
        'lot_size': 'first'
    }).rename(columns={'strike': 'num_options'})
    
    summary_path = Path("data/options/portfolio_options_summary.csv")
    summary.to_csv(summary_path)
    print(f"✓ Saved summary to {summary_path}")
    
    # Show summary
    print(f"\n=== BY STOCK ===")
    print(summary.to_string())
    
    # Create hedging recommendations (placeholder)
    print(f"\n=== HEDGING RECOMMENDATIONS ===")
    print("To generate hedging recommendations, integrate with:")
    print("  1. Portfolio positions (from ledger/state)")
    print("  2. Valuation engine (undervalued stocks)")
    print("  3. Risk metrics (portfolio Greeks)")
    print("  4. Market regime (from intelligence engine)")
    
    print(f"\n✓ Options data ready for dashboard and hedging system")

if __name__ == "__main__":
    main()
