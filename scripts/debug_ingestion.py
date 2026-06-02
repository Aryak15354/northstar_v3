#!/usr/bin/env python3
"""Debug script to test ingestion layer step by step."""

import sys
from pathlib import Path
from datetime import datetime
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ingestion import IngestionRegistry

print("=" * 80)
print("INGESTION LAYER DEBUG")
print("=" * 80)

# Initialize
print("\n1. Initializing registry...")
registry = IngestionRegistry()
print("   ✅ Registry initialized")

# Test market loader
print("\n2. Testing market loader...")
as_of_date = datetime(2024, 3, 1)
print(f"   As of date: {as_of_date}")

try:
    # Check if file exists
    prices_path = Path('data/processed/prices.parquet')
    print(f"   Prices file exists: {prices_path.exists()}")
    
    if prices_path.exists():
        # Load directly to see structure
        print("\n   Loading prices.parquet directly...")
        df_direct = pd.read_parquet(prices_path)
        print(f"   Shape: {df_direct.shape}")
        print(f"   Columns: {list(df_direct.columns)}")
        print(f"   Has 'Date': {'Date' in df_direct.columns}")
        print(f"   Has 'ticker': {'ticker' in df_direct.columns}")
        
        # Check date range
        if 'Date' in df_direct.columns:
            df_direct['Date'] = pd.to_datetime(df_direct['Date'])
            print(f"   Date range: {df_direct['Date'].min()} to {df_direct['Date'].max()}")
            
            # Check if as_of_date is in range
            in_range = (df_direct['Date'] <= as_of_date).any()
            print(f"   Data available for {as_of_date}: {in_range}")
        
        # Try loading via registry
        print("\n   Loading via registry...")
        df = registry.market.load(
            as_of_date=as_of_date,
            tickers=['RELIANCE', 'TCS']
        )
        
        if df.empty:
            print("   ❌ Registry returned empty DataFrame")
            
            # Debug: try with all tickers
            print("\n   Checking available tickers...")
            if 'ticker' in df_direct.columns:
                available_tickers = df_direct['ticker'].unique()
                print(f"   Total tickers in file: {len(available_tickers)}")
                print(f"   Sample tickers: {list(available_tickers[:10])}")
                
                # Check if RELIANCE exists
                reliance_variants = [t for t in available_tickers if 'RELIANCE' in t or 'RELI' in t]
                print(f"   RELIANCE variants: {reliance_variants}")
        else:
            print(f"   ✅ Loaded {len(df)} rows")
            print(f"   Index: {df.index.names}")
            print(f"   Columns: {list(df.columns)}")
            print("\n   Sample:")
            print(df.head(3))

except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()

# Test fundamental loader
print("\n3. Testing fundamental loader...")
try:
    fund_path = Path('data/processed/screener_fundamentals_annual.csv')
    print(f"   Fundamentals file exists: {fund_path.exists()}")
    
    if fund_path.exists():
        # Load directly
        print("\n   Loading screener_fundamentals_annual.csv directly...")
        df_direct = pd.read_csv(fund_path, nrows=10)
        print(f"   Shape: {df_direct.shape}")
        print(f"   Columns: {list(df_direct.columns)[:10]}")
        
        # Try loading via registry
        print("\n   Loading via registry...")
        df = registry.fundamentals.load_financials(
            as_of_date=as_of_date,
            tickers=['RELIANCE'],
            frequency='annual'
        )
        
        if df.empty:
            print("   ❌ Registry returned empty DataFrame")
        else:
            print(f"   ✅ Loaded {len(df)} rows")
            print(f"   Columns: {list(df.columns)[:10]}")

except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
print("DEBUG COMPLETE")
print("=" * 80)
