#!/usr/bin/env python3
"""
NSE Data Processor - ROBUST

Processes raw NSE downloads into clean, analysis-ready files.
Handles:
- Bulk deals (fixes missing symbols)
- Credit ratings (parses complex NSE format)
- Deduplication
- Data quality validation

Usage:
    python3 scripts/process_nse_data_robust.py
"""

import pandas as pd
from pathlib import Path
from datetime import datetime

# Directories
PROJECT_ROOT = Path(__file__).parent.parent
RAW_BULK_DIR = PROJECT_ROOT / "data" / "raw" / "exchanges" / "nse" / "alternative" / "bulk_deals"
RAW_RATINGS_DIR = PROJECT_ROOT / "data" / "raw" / "exchanges" / "nse" / "alternative" / "credit_ratings"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed" / "alternative"

PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


def process_bulk_deals():
    """Process NSE bulk deals with robust symbol handling."""
    print("=" * 80)
    print("PROCESSING NSE BULK DEALS")
    print("=" * 80)
    
    # Find all raw CSV files
    raw_files = list(RAW_BULK_DIR.glob("*.csv"))
    print(f"\nFound {len(raw_files)} raw files")
    
    if not raw_files:
        print("⚠ No raw files found!")
        return False
    
    all_data = []
    
    for file_path in raw_files:
        try:
            # Skip if it's already a processed file
            if "all" in file_path.name or "recent" in file_path.name:
                continue
            
            df = pd.read_csv(file_path)
            
            # Validate columns
            required_cols = ['date', 'symbol', 'company_name']
            missing = [c for c in required_cols if c not in df.columns]
            
            if missing:
                print(f"  ⚠ {file_path.name}: Missing columns {missing}, skipping")
                continue
            
            # Check for missing symbols
            missing_symbols = df['symbol'].isna().sum()
            if missing_symbols > 0:
                print(f"  ⚠ {file_path.name}: {missing_symbols} missing symbols")
                # Try to extract from nse_ticker if available
                if 'nse_ticker' in df.columns:
                    df['symbol'] = df['symbol'].fillna(
                        df['nse_ticker'].str.replace('.NS', '', regex=False)
                    )
            
            # Only keep rows with valid symbols
            valid_mask = df['symbol'].notna() & (df['symbol'].str.strip() != '')
            if not valid_mask.all():
                invalid_count = (~valid_mask).sum()
                print(f"  ⚠ {file_path.name}: Removing {invalid_count} rows without symbols")
                df = df[valid_mask]
            
            if len(df) > 0:
                all_data.append(df)
                print(f"  ✓ {file_path.name}: {len(df)} rows")
                
        except Exception as e:
            print(f"  ✗ {file_path.name}: Error - {e}")
    
    if not all_data:
        print("\n⚠ No valid data to process!")
        return False
    
    # Combine all data
    combined = pd.concat(all_data, ignore_index=True)
    print(f"\nCombined: {len(combined):,} rows")
    
    # Remove duplicates
    before_dedup = len(combined)
    combined = combined.drop_duplicates(
        subset=['date', 'symbol', 'client_name', 'deal_type'],
        keep='last'
    )
    print(f"After deduplication: {len(combined):,} rows (removed {before_dedup - len(combined):,} duplicates)")
    
    # Convert types
    combined['date'] = pd.to_datetime(combined['date'], errors='coerce')
    combined['quantity'] = pd.to_numeric(
        combined['quantity'].astype(str).str.replace(',', ''),
        errors='coerce'
    )
    combined['price'] = pd.to_numeric(combined['price'], errors='coerce')
    
    # Ensure nse_ticker column
    if 'nse_ticker' not in combined.columns:
        combined['nse_ticker'] = combined['symbol'].apply(lambda x: f"{x}.NS")
    
    # Sort by date
    combined = combined.sort_values('date', ascending=False)
    
    # Validate
    print("\n=== DATA QUALITY ===")
    print(f"Total rows: {len(combined):,}")
    print(f"Unique symbols: {combined['symbol'].nunique()}")
    print(f"Date range: {combined['date'].min()} to {combined['date'].max()}")
    print(f"Missing symbols: {combined['symbol'].isna().sum()}")
    print(f"Missing dates: {combined['date'].isna().sum()}")
    
    if combined['symbol'].isna().sum() > 0:
        print("⚠ WARNING: Still have missing symbols!")
        # Remove rows without symbols
        combined = combined[combined['symbol'].notna()]
        print(f"After cleanup: {len(combined):,} rows")
    
    # Save
    output_path = PROCESSED_DIR / "bulk_deals_nse_all.csv"
    combined.to_csv(output_path, index=False)
    print(f"\n✓ Saved to {output_path}")
    
    # Save recent (last 90 days)
    recent_cutoff = datetime.now() - pd.Timedelta(days=90)
    recent = combined[combined['date'] >= recent_cutoff]
    recent_path = PROCESSED_DIR / "bulk_deals_nse_recent.csv"
    recent.to_csv(recent_path, index=False)
    print(f"✓ Saved recent ({len(recent):,} rows) to {recent_path}")
    
    # Save parquet
    parquet_path = PROCESSED_DIR / "bulk_deals_nse_all.parquet"
    combined.to_parquet(parquet_path, index=False)
    print(f"✓ Saved parquet to {parquet_path}")
    
    # Show top symbols
    print("\n=== TOP 20 SYMBOLS ===")
    top_symbols = combined['symbol'].value_counts().head(20)
    for symbol, count in top_symbols.items():
        print(f"  {symbol}: {count:,} deals")
    
    return True


def process_credit_ratings():
    """Process NSE credit ratings with robust parsing."""
    print("\n" + "=" * 80)
    print("PROCESSING NSE CREDIT RATINGS")
    print("=" * 80)
    
    raw_files = list(RAW_RATINGS_DIR.glob("*.csv"))
    print(f"\nFound {len(raw_files)} raw files")
    
    if not raw_files:
        print("⚠ No raw files found!")
        return False
    
    all_data = []
    
    for file_path in raw_files:
        try:
            # Skip processed files
            if "all" in file_path.name or "recent" in file_path.name:
                continue
            
            # Read with BOM handling
            df = pd.read_csv(file_path, encoding='utf-8-sig', engine='python', on_bad_lines='warn')
            
            if len(df) == 0:
                continue
            
            # Map columns
            column_map = {}
            for col in df.columns:
                col_clean = str(col).strip().upper()
                
                if 'DATE OF CREDIT RATING' in col_clean and 'EARLIER' not in col_clean:
                    column_map[col] = 'date'
                elif 'ISIN' in col_clean and 'EARLIER' not in col_clean:
                    column_map[col] = 'isin'
                elif 'COMPANY NAME' in col_clean:
                    column_map[col] = 'company_name'
                elif 'AGENCY' in col_clean and 'EARLIER' not in col_clean:
                    column_map[col] = 'agency'
                elif col_clean == 'CREDIT RATING':
                    column_map[col] = 'rating'
                elif 'RATING ACTION' in col_clean and 'EARLIER' not in col_clean:
                    column_map[col] = 'rating_action'
                elif col_clean == 'OUTLOOK':
                    column_map[col] = 'outlook'
            
            df = df.rename(columns=column_map)
            
            # Convert date
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'], format='%d-%m-%Y', errors='coerce')
            
            df['source'] = 'NSE_CREDIT_RATINGS'
            df['instrument_type'] = 'Debt'
            
            if len(df) > 0:
                all_data.append(df)
                print(f"  ✓ {file_path.name}: {len(df)} rows")
                
        except Exception as e:
            print(f"  ✗ {file_path.name}: Error - {e}")
    
    if not all_data:
        print("\n⚠ No valid data to process!")
        return False
    
    # Combine
    combined = pd.concat(all_data, ignore_index=True)
    print(f"\nCombined: {len(combined):,} rows")
    
    # Remove duplicates
    before_dedup = len(combined)
    if 'isin' in combined.columns:
        combined = combined.drop_duplicates(
            subset=['date', 'isin', 'agency'],
            keep='last'
        )
    print(f"After deduplication: {len(combined):,} rows")
    
    # Sort
    if 'date' in combined.columns:
        combined = combined.sort_values('date', ascending=False)
    
    # Validate
    print("\n=== DATA QUALITY ===")
    print(f"Total rows: {len(combined):,}")
    if 'company_name' in combined.columns:
        print(f"Unique companies: {combined['company_name'].nunique()}")
    if 'isin' in combined.columns:
        print(f"Unique ISINs: {combined['isin'].nunique()}")
    if 'date' in combined.columns:
        print(f"Date range: {combined['date'].min()} to {combined['date'].max()}")
    if 'agency' in combined.columns:
        print(f"Agencies: {combined['agency'].nunique()}")
    
    # Save
    output_path = PROCESSED_DIR / "credit_ratings_nse_all.csv"
    combined.to_csv(output_path, index=False)
    print(f"\n✓ Saved to {output_path}")
    
    return True


if __name__ == "__main__":
    print("=" * 80)
    print("NSE DATA PROCESSOR - ROBUST")
    print("=" * 80)
    
    bulk_ok = process_bulk_deals()
    ratings_ok = process_credit_ratings()
    
    print("\n" + "=" * 80)
    print("PROCESSING COMPLETE")
    print("=" * 80)
    
    if bulk_ok and ratings_ok:
        print("✓ All data processed successfully!")
    elif bulk_ok:
        print("⚠ Bulk deals processed, credit ratings failed")
    elif ratings_ok:
        print("⚠ Credit ratings processed, bulk deals failed")
    else:
        print("✗ Processing failed")
