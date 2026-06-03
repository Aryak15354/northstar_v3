#!/usr/bin/env python3
"""
Extract Nifty 50 benchmark data from existing price data.
Creates a dedicated benchmark file for P&L attribution.
"""
import pandas as pd
from pathlib import Path
import sys

def main():
    print("=" * 80)
    print("EXTRACTING NIFTY 50 BENCHMARK DATA")
    print("=" * 80)
    
    # Try multiple possible locations for Nifty data
    nifty_paths = [
        "data/raw/prices_daily/^NSEI.csv",
        "data/raw/prices_daily/Data/^NSEI.csv",
        "data/raw/prices_daily/NSEI.csv",
        "data/raw/prices_daily/Data/NSEI.csv",
    ]
    
    nifty_df = None
    found_path = None
    
    for path in nifty_paths:
        if Path(path).exists():
            try:
                nifty_df = pd.read_csv(path)
                found_path = path
                print(f"✓ Found Nifty data at: {path}")
                break
            except Exception as e:
                print(f"✗ Error reading {path}: {e}")
    
    if nifty_df is None:
        print("\n❌ Nifty 50 data not found in any expected location")
        print("Searched:")
        for p in nifty_paths:
            print(f"  - {p}")
        return 1
    
    # Standardize column names
    nifty_df.columns = [c.lower().strip() for c in nifty_df.columns]
    
    # Find date and close columns
    date_col = next((c for c in nifty_df.columns if 'date' in c), None)
    close_col = next((c for c in nifty_df.columns if 'close' in c or 'adj' in c), None)
    
    if not date_col or not close_col:
        print(f"\n❌ Could not find date or close columns")
        print(f"Available columns: {list(nifty_df.columns)}")
        return 1
    
    # Create benchmark DataFrame
    benchmark_df = pd.DataFrame({
        'date': pd.to_datetime(nifty_df[date_col]),
        'close': pd.to_numeric(nifty_df[close_col], errors='coerce'),
        'ticker': 'NIFTY50'
    })
    
    # Remove NaN values
    benchmark_df = benchmark_df.dropna(subset=['date', 'close'])
    
    # Sort by date
    benchmark_df = benchmark_df.sort_values('date').reset_index(drop=True)
    
    # Calculate returns
    benchmark_df['returns'] = benchmark_df['close'].pct_change()
    
    # Save to processed location
    output_dir = Path("data/processed/benchmark")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_file = output_dir / "nifty50.parquet"
    benchmark_df.to_parquet(output_file, index=False)
    
    print(f"\n✅ Created benchmark file: {output_file}")
    print(f"   Rows: {len(benchmark_df):,}")
    print(f"   Date range: {benchmark_df['date'].min().date()} to {benchmark_df['date'].max().date()}")
    print(f"   Columns: {list(benchmark_df.columns)}")
    
    # Show recent data
    print(f"\nRecent data:")
    print(benchmark_df[['date', 'close', 'returns']].tail(5).to_string(index=False))
    
    # Calculate statistics
    print(f"\nStatistics:")
    print(f"   Mean daily return: {benchmark_df['returns'].mean()*100:.3f}%")
    print(f"   Volatility (daily): {benchmark_df['returns'].std()*100:.3f}%")
    print(f"   Annualized return: {benchmark_df['returns'].mean()*252*100:.2f}%")
    print(f"   Annualized volatility: {benchmark_df['returns'].std()*(252**0.5)*100:.2f}%")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
