#!/usr/bin/env python3
"""
Fix Sector Mapping to Match Real Ledger Data

The sector mapping uses Yahoo Finance format (TICKER.NS) but the ledger
uses NSE format (TICKER). This script creates a mapping that works with both.
"""

import pandas as pd
from pathlib import Path


def main():
    print("=" * 60)
    print("FIXING SECTOR MAPPING FOR REAL DATA")
    print("=" * 60)
    
    # Load existing mapping
    mapping_path = Path("data/metadata/ticker_sector_mapping.csv")
    mapping = pd.read_csv(mapping_path)
    
    print(f"\n1. Original mapping: {len(mapping)} tickers")
    print(f"   Format: {mapping['ticker'].iloc[0]}")
    
    # Create NSE format (without .NS suffix)
    mapping['ticker_nse'] = mapping['ticker'].str.replace('.NS', '', regex=False)
    
    # Create both formats
    nse_mapping = mapping[['ticker_nse', 'company_name', 'sector']].copy()
    nse_mapping.columns = ['ticker', 'company_name', 'sector']
    
    yahoo_mapping = mapping[['ticker', 'company_name', 'sector']].copy()
    
    # Combine both
    combined = pd.concat([nse_mapping, yahoo_mapping], ignore_index=True)
    combined = combined.drop_duplicates(subset=['ticker'])
    
    print(f"\n2. Combined mapping: {len(combined)} tickers")
    print(f"   NSE format: {nse_mapping['ticker'].iloc[0]}")
    print(f"   Yahoo format: {yahoo_mapping['ticker'].iloc[0]}")
    
    # Save combined mapping
    output_path = Path("data/metadata/ticker_sector_mapping.csv")
    combined.to_csv(output_path, index=False)
    
    print(f"\n3. Saved to: {output_path}")
    
    # Test with real ledger tickers
    ledger_path = Path("data/pnl/master_ledger.parquet")
    if ledger_path.exists():
        ledger = pd.read_parquet(ledger_path)
        ledger_tickers = set(ledger['ticker'].unique())
        mapped_tickers = set(combined['ticker'].unique())
        
        overlap = ledger_tickers & mapped_tickers
        
        print(f"\n4. Testing with real ledger:")
        print(f"   Ledger tickers: {len(ledger_tickers)}")
        print(f"   Mapped tickers: {len(mapped_tickers)}")
        print(f"   Overlap: {len(overlap)} tickers")
        
        if len(overlap) > 0:
            print(f"   ✓ SUCCESS - {len(overlap)} tickers can be attributed")
            print(f"   Matched tickers: {list(overlap)}")
        else:
            print(f"   ⚠ Still no overlap")
            print(f"   Ledger: {list(ledger_tickers)[:10]}")
            print(f"   Mapped: {list(mapped_tickers)[:10]}")
    
    print("\n✅ Sector mapping fixed")
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
