#!/usr/bin/env python3
"""
Generate comprehensive ticker-sector mapping from Nifty 500 universe
"""

import pandas as pd
from pathlib import Path

def generate_mapping():
    """Generate ticker-sector mapping from nifty500.csv"""
    
    # Read nifty500.csv
    nifty500_path = Path("universe/nifty500.csv")
    
    if not nifty500_path.exists():
        print(f"✗ {nifty500_path} not found")
        return False
    
    df = pd.read_csv(nifty500_path)
    
    print(f"✓ Loaded {len(df)} companies from Nifty 500")
    print(f"  Columns: {list(df.columns)}")
    
    # Create mapping with .NS suffix for NSE tickers
    mapping = pd.DataFrame({
        'ticker': df['Symbol'].astype(str) + '.NS',
        'sector': df['Industry'],
        'company_name': df['Company Name']
    })
    
    # Sort by ticker
    mapping = mapping.sort_values('ticker').reset_index(drop=True)
    
    # Save to metadata
    output_path = Path("data/metadata/ticker_sector_mapping.csv")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    mapping.to_csv(output_path, index=False)
    
    print(f"\n✓ Generated mapping for {len(mapping)} tickers")
    print(f"✓ Saved to {output_path}")
    
    # Show sector distribution
    print(f"\nSector distribution:")
    sector_counts = mapping['sector'].value_counts()
    for sector, count in sector_counts.head(10).items():
        print(f"  {sector}: {count}")
    
    return True

if __name__ == "__main__":
    success = generate_mapping()
    exit(0 if success else 1)
