"""
Discover Stock Options from Nifty 500

Checks which stocks from Nifty 500 have options trading available
and generates a comprehensive stock options mapping.
"""

import pandas as pd
import requests
import yaml
import time
import os
from pathlib import Path

TOKEN = os.getenv("UPSTOX_ACCESS_TOKEN", "").strip()

def check_stock_options(symbol, isin):
    """Check if a stock has options available"""
    url = 'https://api.upstox.com/v2/option/contract'
    headers = {'Authorization': f'Bearer {TOKEN}', 'Accept': 'application/json'}
    params = {'instrument_key': f'NSE_EQ|{isin}'}
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            if 'data' in data and len(data['data']) > 0:
                # Get lot size from first contract
                lot_size = data['data'][0].get('lot_size', 0)
                num_contracts = len(data['data'])
                return True, lot_size, num_contracts
        
        return False, 0, 0
    
    except Exception as e:
        print(f"Error checking {symbol}: {e}")
        return False, 0, 0


def main():
    if not TOKEN:
        raise SystemExit("UPSTOX_ACCESS_TOKEN not set. Export token before running.")

    print("=" * 80)
    print("DISCOVERING STOCK OPTIONS FROM NIFTY 500")
    print("=" * 80)
    
    # Read Nifty 500 CSV
    df = pd.read_csv('universe/nifty500.csv')
    print(f"\nTotal stocks in Nifty 500: {len(df)}")
    
    # Check each stock for options
    stocks_with_options = []
    
    print("\nChecking stocks for options availability...")
    print("(This may take a few minutes due to rate limiting)\n")
    
    for idx, row in df.iterrows():
        symbol = row['Symbol']
        isin = row['ISIN Code']
        company_name = row['Company Name']
        industry = row['Industry']
        
        # Check if options available
        has_options, lot_size, num_contracts = check_stock_options(symbol, isin)
        
        if has_options:
            stocks_with_options.append({
                'symbol': symbol,
                'isin': isin,
                'name': company_name,
                'industry': industry,
                'lot_size': lot_size,
                'num_contracts': num_contracts
            })
            print(f"✅ {symbol:15} - {company_name:50} Lot: {lot_size:5} Contracts: {num_contracts}")
        else:
            print(f"❌ {symbol:15} - No options")
        
        # Rate limiting (1 request per second)
        time.sleep(1.1)
        
        # Progress update every 50 stocks
        if (idx + 1) % 50 == 0:
            print(f"\nProgress: {idx + 1}/{len(df)} stocks checked")
            print(f"Found {len(stocks_with_options)} stocks with options so far\n")
    
    print("\n" + "=" * 80)
    print(f"DISCOVERY COMPLETE")
    print("=" * 80)
    print(f"\nTotal stocks checked: {len(df)}")
    print(f"Stocks with options: {len(stocks_with_options)}")
    print(f"Percentage: {len(stocks_with_options)/len(df)*100:.1f}%")
    
    # Save results to CSV
    results_df = pd.DataFrame(stocks_with_options)
    results_df.to_csv('data/options/stocks_with_options.csv', index=False)
    print(f"\nResults saved to: data/options/stocks_with_options.csv")
    
    # Generate YAML mapping
    generate_yaml_mapping(stocks_with_options)
    
    # Show top stocks by contract count
    print("\n" + "=" * 80)
    print("TOP 20 STOCKS BY CONTRACT COUNT (HIGHEST LIQUIDITY)")
    print("=" * 80)
    
    top_stocks = sorted(stocks_with_options, key=lambda x: x['num_contracts'], reverse=True)[:20]
    for i, stock in enumerate(top_stocks, 1):
        print(f"{i:2}. {stock['symbol']:15} - {stock['name']:40} Contracts: {stock['num_contracts']:4} Lot: {stock['lot_size']}")
    
    # Show by industry
    print("\n" + "=" * 80)
    print("STOCKS WITH OPTIONS BY INDUSTRY")
    print("=" * 80)
    
    by_industry = {}
    for stock in stocks_with_options:
        industry = stock['industry']
        if industry not in by_industry:
            by_industry[industry] = []
        by_industry[industry].append(stock)
    
    for industry in sorted(by_industry.keys()):
        print(f"\n{industry}: {len(by_industry[industry])} stocks")
        for stock in sorted(by_industry[industry], key=lambda x: x['num_contracts'], reverse=True)[:5]:
            print(f"  {stock['symbol']:15} - {stock['name']:40} Lot: {stock['lot_size']}")


def generate_yaml_mapping(stocks_with_options):
    """Generate YAML mapping file"""
    
    # Group by industry
    by_industry = {}
    for stock in stocks_with_options:
        industry = stock['industry']
        if industry not in by_industry:
            by_industry[industry] = []
        by_industry[industry].append(stock)
    
    # Create YAML structure
    yaml_data = {
        'stocks': {},
        'selection_criteria': {
            'min_market_cap_cr': 10000,
            'min_avg_daily_volume': 1000000,
            'min_option_oi': 10000,
            'max_bid_ask_spread_pct': 0.10,
            'min_contracts_available': 50
        }
    }
    
    # Add all stocks
    for stock in stocks_with_options:
        yaml_data['stocks'][stock['symbol']] = {
            'isin': stock['isin'],
            'name': stock['name'],
            'lot_size': stock['lot_size'],
            'sector': stock['industry']
        }
    
    # Add top liquid stocks as recommended
    top_liquid = sorted(stocks_with_options, key=lambda x: x['num_contracts'], reverse=True)[:20]
    yaml_data['recommended_for_beginners'] = [s['symbol'] for s in top_liquid]
    
    # Save to file
    output_path = Path('config/stock_options_mapping_complete.yaml')
    with open(output_path, 'w') as f:
        yaml.dump(yaml_data, f, default_flow_style=False, sort_keys=False)
    
    print(f"\nYAML mapping saved to: {output_path}")
    print(f"Total stocks in mapping: {len(yaml_data['stocks'])}")


if __name__ == '__main__':
    main()
