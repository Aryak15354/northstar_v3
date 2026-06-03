#!/usr/bin/env python3
"""
NSE Manual Downloads Processor

Integrates manually downloaded NSE CSV files into the system.
Processes bulk deals and credit ratings year-by-year downloads.

Usage:
    python3 scripts/process_nse_manual_downloads.py
    
Place your downloaded CSVs in:
- Bulk deals: data/raw/exchanges/nse/alternative/bulk_deals/manual/
- Credit ratings: data/raw/exchanges/nse/alternative/credit_ratings/manual/

Or specify custom directory:
    python3 scripts/process_nse_manual_downloads.py --input-dir ~/Downloads
"""

import pandas as pd
from pathlib import Path
from datetime import datetime
import shutil

# Project root
PROJECT_ROOT = Path(__file__).parent.parent

# Directories
RAW_BULK_DIR = PROJECT_ROOT / "data" / "raw" / "exchanges" / "nse" / "alternative" / "bulk_deals"
RAW_RATINGS_DIR = PROJECT_ROOT / "data" / "raw" / "exchanges" / "nse" / "alternative" / "credit_ratings"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed" / "alternative"

# Create directories
RAW_BULK_DIR.mkdir(parents=True, exist_ok=True)
RAW_RATINGS_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


def detect_file_type(file_path):
    """Detect if file is bulk deals or credit ratings."""
    try:
        # Read first few lines to detect
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            header = f.readline().lower()
            
            if 'symbol' in header and ('bulk' in file_path.name.lower() or 'deal' in header):
                return 'bulk_deals'
            elif 'agency' in header or 'rating' in header or 'crd' in file_path.name.lower():
                return 'credit_ratings'
            elif 'company name' in header and 'isin' in header:
                return 'credit_ratings'
            else:
                return 'unknown'
    except Exception as e:
        print(f"  ⚠ Error detecting {file_path.name}: {e}")
        return 'unknown'


def process_bulk_deals_file(file_path):
    """Process a single bulk deals CSV file."""
    try:
        # Try different encodings and parsers
        for encoding in ['utf-8-sig', 'utf-8', 'latin-1']:
            try:
                df = pd.read_csv(file_path, encoding=encoding, engine='python', on_bad_lines='warn')
                break
            except Exception:
                continue
        
        # Standardize column names
        column_map = {}
        for col in df.columns:
            col_clean = str(col).strip().upper()
            if col_clean == 'DATE':
                column_map[col] = 'date'
            elif col_clean == 'SYMBOL':
                column_map[col] = 'symbol'
            elif 'SECURITY NAME' in col_clean:
                column_map[col] = 'company_name'
            elif 'CLIENT NAME' in col_clean:
                column_map[col] = 'client_name'
            elif 'BUY' in col_clean or 'SELL' in col_clean:
                column_map[col] = 'deal_type'
            elif 'QUANTITY' in col_clean:
                column_map[col] = 'quantity'
            elif 'PRICE' in col_clean:
                column_map[col] = 'price'
            elif 'REMARKS' in col_clean:
                column_map[col] = 'remarks'
        
        df = df.rename(columns=column_map)
        
        # Validate required columns
        required = ['date', 'symbol']
        missing = [c for c in required if c not in df.columns]
        if missing:
            print(f"  ⚠ {file_path.name}: Missing columns {missing}")
            return None
        
        # Convert types
        df['date'] = pd.to_datetime(df['date'], format='%d-%b-%Y', errors='coerce')
        
        # Try alternative date format
        if df['date'].isna().all():
            df['date'] = pd.to_datetime(df['date'], format='%d-%m-%Y', errors='coerce')
        
        if 'quantity' in df.columns:
            df['quantity'] = pd.to_numeric(
                df['quantity'].astype(str).str.replace(',', ''),
                errors='coerce'
            )
        
        if 'price' in df.columns:
            df['price'] = pd.to_numeric(df['price'], errors='coerce')
        
        # Add NSE ticker
        if 'nse_ticker' not in df.columns and 'symbol' in df.columns:
            df['nse_ticker'] = df['symbol'].apply(lambda x: f"{x}.NS" if pd.notna(x) else None)
        
        # Add source
        df['source'] = 'NSE_MANUAL_DOWNLOAD'
        
        # Remove rows without symbols
        df = df[df['symbol'].notna() & (df['symbol'].str.strip() != '')]
        
        print(f"  ✓ {file_path.name}: {len(df):,} rows")
        return df
        
    except Exception as e:
        print(f"  ✗ {file_path.name}: Error - {e}")
        return None


def process_credit_ratings_file(file_path):
    """Process a single credit ratings CSV file."""
    try:
        # NSE CRD files have duplicate column names - need special handling
        # Read raw and clean up
        
        # First try reading with skipinitialspace
        try:
            df = pd.read_csv(
                file_path,
                encoding='utf-8-sig',
                engine='python',
                on_bad_lines='warn',
                skipinitialspace=True
            )
        except Exception as e1:
            # If that fails, try reading line by line
            try:
                with open(file_path, 'r', encoding='utf-8-sig') as f:
                    lines = f.readlines()
                
                # Clean header (remove duplicates)
                header = lines[0].strip()
                cols = header.split(',')
                seen = {}
                unique_cols = []
                for col in cols:
                    col = col.strip().strip('"')
                    if col in seen:
                        seen[col] += 1
                        unique_cols.append(f"{col}_{seen[col]}")
                    else:
                        seen[col] = 0
                        unique_cols.append(col)
                
                # Read data with unique columns
                import io
                new_header = ','.join(unique_cols)
                content = new_header + '\n' + ''.join(lines[1:])
                df = pd.read_csv(io.StringIO(content), on_bad_lines='warn')
                
            except Exception as e2:
                print(f"  ✗ {file_path.name}: Cannot parse - {e2}")
                return None
        
        # Standardize column names
        column_map = {}
        for col in df.columns:
            col_clean = str(col).strip().upper()
            
            # Date - prefer DATE OF CREDIT RATING
            if 'DATE OF CREDIT RATING' in col_clean and 'EARLIER' not in col_clean:
                column_map[col] = 'date'
            elif 'CREATE DATE' in col_clean or 'CREATE/ TIME' in col_clean:
                column_map[col] = 'date'
            elif col_clean == 'DATE' and column_map.get('date') is None:
                column_map[col] = 'date'
            
            # ISIN
            if 'ISIN' in col_clean and 'EARLIER' not in col_clean:
                column_map[col] = 'isin'
            
            # Company
            if 'COMPANY NAME' in col_clean:
                column_map[col] = 'company_name'
            
            # Agency
            if 'AGENCY' in col_clean and 'EARLIER' not in col_clean:
                column_map[col] = 'agency'
            
            # Rating
            if col_clean == 'CREDIT RATING':
                column_map[col] = 'rating'
            
            # Rating action
            if 'RATING ACTION' in col_clean and 'EARLIER' not in col_clean:
                column_map[col] = 'rating_action'
            
            # Outlook
            if col_clean == 'OUTLOOK':
                column_map[col] = 'outlook'
        
        df = df.rename(columns=column_map)
        
        # Convert date
        if 'date' in df.columns:
            # Try dd-mm-yyyy first (NSE format)
            df['date'] = pd.to_datetime(df['date'], format='%d-%m-%Y', errors='coerce')
            
            # Try alternative
            if df['date'].isna().all():
                df['date'] = pd.to_datetime(df['date'], format='%d-%b-%Y', errors='coerce')
        
        # Add source
        df['source'] = 'NSE_MANUAL_DOWNLOAD'
        df['instrument_type'] = 'Debt'
        
        print(f"  ✓ {file_path.name}: {len(df):,} rows")
        return df
        
    except Exception as e:
        print(f"  ✗ {file_path.name}: Error - {e}")
        return None


def process_downloads(input_dir=None):
    """Process all manually downloaded files."""
    print("=" * 80)
    print("NSE MANUAL DOWNLOADS PROCESSOR")
    print("=" * 80)
    
    if input_dir:
        input_path = Path(input_dir)
        print(f"\nInput directory: {input_path}")
    else:
        input_path = RAW_BULK_DIR  # Default location
    
    # Find all CSV files
    if input_path.exists():
        csv_files = list(input_path.glob("*.csv"))
        # Exclude already processed files
        csv_files = [f for f in csv_files if 'all' not in f.name and 'recent' not in f.name]
    else:
        csv_files = []
    
    print(f"\nFound {len(csv_files)} CSV files")
    
    if not csv_files:
        print("⚠ No CSV files found!")
        print("\nPlease place your downloaded CSVs in:")
        print(f"  {RAW_BULK_DIR}")
        print("\nOr specify input directory:")
        print(f"  python3 scripts/process_nse_manual_downloads.py --input-dir ~/Downloads")
        return False
    
    # Separate by type
    bulk_files = []
    ratings_files = []
    
    for f in csv_files:
        file_type = detect_file_type(f)
        if file_type == 'bulk_deals':
            bulk_files.append(f)
        elif file_type == 'credit_ratings':
            ratings_files.append(f)
        else:
            print(f"  ? {f.name}: Unknown type")
    
    print(f"\nBulk deals files: {len(bulk_files)}")
    print(f"Credit ratings files: {len(ratings_files)}")
    
    # Process bulk deals
    bulk_data = []
    if bulk_files:
        print("\n" + "=" * 60)
        print("PROCESSING BULK DEALS")
        print("=" * 60)
        
        for f in sorted(bulk_files):
            df = process_bulk_deals_file(f)
            if df is not None and len(df) > 0:
                bulk_data.append(df)
        
        # Move processed files
        for f in bulk_files:
            dest = RAW_BULK_DIR / f.name
            if f != dest:
                shutil.copy(f, dest)
    
    # Process credit ratings
    ratings_data = []
    if ratings_files:
        print("\n" + "=" * 60)
        print("PROCESSING CREDIT RATINGS")
        print("=" * 60)
        
        for f in sorted(ratings_files):
            df = process_credit_ratings_file(f)
            if df is not None and len(df) > 0:
                ratings_data.append(df)
        
        # Move processed files
        for f in ratings_files:
            dest = RAW_RATINGS_DIR / f.name
            if f != dest:
                shutil.copy(f, dest)
    
    # Combine and save bulk deals
    if bulk_data:
        print("\n" + "=" * 60)
        print("COMBINING BULK DEALS")
        print("=" * 60)
        
        combined = pd.concat(bulk_data, ignore_index=True)
        print(f"Combined: {len(combined):,} rows")
        
        # Remove duplicates
        before = len(combined)
        combined = combined.drop_duplicates(
            subset=['date', 'symbol', 'client_name', 'deal_type'],
            keep='last'
        )
        print(f"After dedup: {len(combined):,} rows (removed {before - len(combined):,})")
        
        # Sort
        combined = combined.sort_values('date', ascending=False)
        
        # Save
        output_file = PROCESSED_DIR / "bulk_deals_nse_all.csv"
        combined.to_csv(output_file, index=False)
        print(f"\n✓ Saved to {output_file.name}")
        
        # Save parquet
        parquet_file = PROCESSED_DIR / "bulk_deals_nse_all.parquet"
        combined.to_parquet(parquet_file, index=False)
        print(f"✓ Saved parquet to {parquet_file.name}")
        
        # Save recent (last 90 days)
        recent_cutoff = datetime.now() - pd.Timedelta(days=90)
        recent = combined[combined['date'] >= recent_cutoff]
        recent_file = PROCESSED_DIR / "bulk_deals_nse_recent.csv"
        recent.to_csv(recent_file, index=False)
        print(f"✓ Saved recent ({len(recent):,} rows) to {recent_file.name}")
        
        # Stats
        print(f"\n=== BULK DEALS SUMMARY ===")
        print(f"Total rows: {len(combined):,}")
        print(f"Unique symbols: {combined['symbol'].nunique()}")
        print(f"Date range: {combined['date'].min()} to {combined['date'].max()}")
        print(f"Missing symbols: {combined['symbol'].isna().sum()}")
    
    # Combine and save credit ratings
    if ratings_data:
        print("\n" + "=" * 60)
        print("COMBINING CREDIT RATINGS")
        print("=" * 60)
        
        combined = pd.concat(ratings_data, ignore_index=True)
        print(f"Combined: {len(combined):,} rows")
        
        # Remove duplicates - only if columns exist
        before = len(combined)
        dedup_cols = []
        if 'date' in combined.columns:
            dedup_cols.append('date')
        if 'isin' in combined.columns:
            dedup_cols.append('isin')
        if 'agency' in combined.columns:
            dedup_cols.append('agency')
        
        if dedup_cols:
            combined = combined.drop_duplicates(subset=dedup_cols, keep='last')
            print(f"After dedup: {len(combined):,} rows (removed {before - len(combined):,})")
        else:
            print(f"No dedup columns found, keeping all {len(combined):,} rows")
        
        # Sort
        if 'date' in combined.columns:
            combined = combined.sort_values('date', ascending=False)
        
        # Save
        output_file = PROCESSED_DIR / "credit_ratings_nse_all.csv"
        combined.to_csv(output_file, index=False)
        print(f"\n✓ Saved to {output_file.name}")
        
        # Stats
        print(f"\n=== CREDIT RATINGS SUMMARY ===")
        print(f"Total rows: {len(combined):,}")
        if 'company_name' in combined.columns:
            print(f"Unique companies: {combined['company_name'].nunique()}")
        if 'isin' in combined.columns:
            print(f"Unique ISINs: {combined['isin'].nunique()}")
        if 'date' in combined.columns:
            print(f"Date range: {combined['date'].min()} to {combined['date'].max()}")
        if 'agency' in combined.columns:
            print(f"Agencies: {combined['agency'].nunique()}")
    
    print("\n" + "=" * 80)
    print("PROCESSING COMPLETE")
    print("=" * 80)
    
    return True


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Process NSE Manual Downloads")
    parser.add_argument("--input-dir", type=str, help="Directory containing downloaded CSVs")
    
    args = parser.parse_args()
    
    process_downloads(input_dir=args.input_dir)
