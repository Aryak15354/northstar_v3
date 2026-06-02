"""
Quick Stock Options Discovery

Quickly checks a sample of stocks to estimate how many have options.
Then provides option to run full discovery.
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
                lot_size = data['data'][0].get('lot_size', 0)
                num_contracts = len(data['data'])
                
                # Get expiries
                expiries = set()
                for contract in data['data'][:10]:
                    if 'expiry' in contract:
                        expiries.add(contract['expiry'])
                
                return True, lot_size, num_contracts, sorted(expiries)[:2]
        
        return False, 0, 0, []
    
    except Exception as e:
        return False, 0, 0, []


def main():
    if not TOKEN:
        raise SystemExit("UPSTOX_ACCESS_TOKEN not set. Export token before running.")

    print("=" * 80)
    print("QUICK STOCK OPTIONS DISCOVERY")
    print("=" * 80)
    
    # Read Nifty 500 CSV
    df = pd.read_csv('universe/nifty500.csv')
    print(f"\nTotal stocks in Nifty 500: {len(df)}")
    
    # Sample first 50 stocks (top by market cap typically)
    sample_size = 50
    sample_df = df.head(sample_size)
    
    print(f"\nChecking first {sample_size} stocks (typically highest market cap)...")
    print("This will take about 1 minute...\n")
    
    stocks_with_options = []
    
    for idx, row in sample_df.iterrows():
        symbol = row['Symbol']
        isin = row['ISIN Code']
        company_name = row['Company Name']
        industry = row['Industry']
        
        has_options, lot_size, num_contracts, expiries = check_stock_options(symbol, isin)
        
        if has_options:
            stocks_with_options.append({
                'symbol': symbol,
                'isin': isin,
                'name': company_name,
                'industry': industry,
                'lot_size': lot_size,
                'num_contracts': num_contracts,
                'expiries': expiries
            })
            expiry_str = ', '.join(expiries) if expiries else 'N/A'
            print(f"✅ {symbol:15} - Lot: {lot_size:5} Contracts: {num_contracts:4} Expiry: {expiry_str}")
        else:
            print(f"❌ {symbol:15} - No options")
        
        time.sleep(1.1)  # Rate limiting
    
    print("\n" + "=" * 80)
    print(f"SAMPLE RESULTS")
    print("=" * 80)
    print(f"\nStocks checked: {sample_size}")
    print(f"Stocks with options: {len(stocks_with_options)}")
    print(f"Percentage: {len(stocks_with_options)/sample_size*100:.1f}%")
    
    # Estimate for full Nifty 500
    estimated_total = int(len(stocks_with_options) / sample_size * len(df))
    print(f"\nEstimated stocks with options in full Nifty 500: ~{estimated_total}")
    print(f"Estimated time for full discovery: ~{len(df) * 1.1 / 60:.0f} minutes")
    
    # Show discovered stocks
    print("\n" + "=" * 80)
    print(f"DISCOVERED STOCKS WITH OPTIONS (Top {sample_size})")
    print("=" * 80)
    
    for stock in sorted(stocks_with_options, key=lambda x: x['num_contracts'], reverse=True):
        print(f"{stock['symbol']:15} - {stock['name']:40} Lot: {stock['lot_size']:5} Contracts: {stock['num_contracts']}")
    
    # Save sample results
    if stocks_with_options:
        results_df = pd.DataFrame(stocks_with_options)
        results_df.to_csv('data/options/stocks_with_options_sample.csv', index=False)
        print(f"\nSample results saved to: data/options/stocks_with_options_sample.csv")
        
        # Generate quick YAML for these stocks
        yaml_data = {'stocks': {}}
        for stock in stocks_with_options:
            yaml_data['stocks'][stock['symbol']] = {
                'isin': stock['isin'],
                'name': stock['name'],
                'lot_size': stock['lot_size'],
                'sector': stock['industry']
            }
        
        with open('config/stock_options_mapping_sample.yaml', 'w') as f:
            yaml.dump(yaml_data, f, default_flow_style=False)
        
        print(f"Sample YAML saved to: config/stock_options_mapping_sample.yaml")
    
    print("\n" + "=" * 80)
    print("NEXT STEPS")
    print("=" * 80)
    print("\n1. To discover ALL stocks with options (takes ~10 minutes):")
    print("   python scripts/discover_stock_options.py")
    print("\n2. To use the sample stocks discovered above:")
    print("   Update config_loader.py to use stock_options_mapping_sample.yaml")
    print("\n3. Current system supports:")
    print(f"   - 4 indices (NIFTY, BANKNIFTY, FINNIFTY, MIDCPNIFTY)")
    print(f"   - {len(stocks_with_options)} stocks (from sample)")
    print(f"   - Estimated ~{estimated_total} total stocks available")


if __name__ == '__main__':
    main()
