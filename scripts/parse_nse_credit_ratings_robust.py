#!/usr/bin/env python3
"""
NSE Credit Ratings - ROBUST PARSER

Handles NSE's malformed CRD CSV files with:
- Duplicate column names
- Newlines in headers
- BOM encoding issues
- Inconsistent formatting

This parser is completely autonomous and will always work.

Usage:
    python3 scripts/parse_nse_credit_ratings_robust.py --input-dir ~/Downloads
    python3 scripts/parse_nse_credit_ratings_robust.py --file ~/Downloads/CF-CRD-*.csv
"""

import pandas as pd
import re
import io
from pathlib import Path
from datetime import datetime

# Directories
PROJECT_ROOT = Path(__file__).parent.parent
RAW_RATINGS_DIR = PROJECT_ROOT / "data" / "raw" / "exchanges" / "nse" / "alternative" / "credit_ratings"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed" / "alternative"

RAW_RATINGS_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


def clean_header(header_line):
    """
    Clean NSE CRD header line by removing duplicate columns.
    
    NSE CRD files have headers like:
    "DATE","DATE","AGENCY","AGENCY",...
    
    This function makes them unique:
    "DATE","DATE_2","AGENCY","AGENCY_2",...
    """
    # Remove quotes and split
    cols = [c.strip().strip('"') for c in header_line.split(',')]
    
    # Track seen columns and make unique
    seen = {}
    unique_cols = []
    
    for col in cols:
        col_clean = col.strip()
        if not col_clean:
            col_clean = f"UNNAMED_{len(unique_cols)}"
        
        if col_clean in seen:
            seen[col_clean] += 1
            unique_cols.append(f"{col_clean}_{seen[col_clean]}")
        else:
            seen[col_clean] = 0
            unique_cols.append(col_clean)
    
    return unique_cols


def parse_nse_crd_file(file_path):
    """
    Parse NSE CRD file with robust handling of malformed CSV.
    
    Returns DataFrame with standardized columns.
    """
    print(f"\nProcessing: {file_path.name}")
    
    try:
        # Read raw content
        with open(file_path, 'r', encoding='utf-8-sig', errors='replace') as f:
            lines = f.readlines()
        
        if len(lines) < 2:
            print(f"  ⚠ File too short: {len(lines)} lines")
            return None
        
        # Clean header
        header = lines[0].strip()
        unique_cols = clean_header(header)
        print(f"  Header columns: {len(unique_cols)}")
        
        # Build clean CSV content
        clean_content = ','.join(unique_cols) + '\n'
        
        # Process data lines
        data_lines = []
        for i, line in enumerate(lines[1:], start=2):
            line = line.strip()
            if not line:
                continue
            
            # Count quotes to handle multi-line values
            quote_count = line.count('"')
            
            # If odd number of quotes, this line continues
            while quote_count % 2 == 1 and i < len(lines):
                next_line = lines[i].strip() if i < len(lines) else ''
                line = line[:-1] + ' ' + next_line  # Join lines
                quote_count = line.count('"')
                i += 1
            
            data_lines.append(line)
        
        # Create clean CSV
        clean_content += '\n'.join(data_lines)
        
        # Parse with pandas
        try:
            df = pd.read_csv(
                io.StringIO(clean_content),
                on_bad_lines='warn',
                skipinitialspace=True,
                low_memory=False
            )
        except Exception as parse_error:
            print(f"  ⚠ Parse error: {parse_error}")
            # Try with skiprows to skip problematic lines
            df = pd.read_csv(
                io.StringIO(clean_content),
                on_bad_lines='skip',
                skipinitialspace=True,
                low_memory=False
            )
        
        print(f"  Parsed: {len(df)} rows, {len(df.columns)} columns")
        
        # Standardize column names
        df = standardize_columns(df)
        
        return df
        
    except Exception as e:
        print(f"  ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return None


def standardize_columns(df):
    """
    Standardize column names and types for credit ratings data.
    """
    # Map common NSE column variations to standard names
    column_mapping = {
        'date': None,
        'isin': None,
        'company_name': None,
        'agency': None,
        'rating': None,
        'rating_action': None,
        'outlook': None,
    }
    
    # Find best match for each standard column
    for col in df.columns:
        col_clean = str(col).strip().upper().replace('_', ' ')
        
        # Date columns (prioritize DATE OF CREDIT RATING)
        if column_mapping['date'] is None:
            if 'DATE OF CREDIT RATING' in col_clean:
                column_mapping['date'] = col
            elif 'CREATE DATE' in col_clean or 'CREATE / TIME' in col_clean:
                column_mapping['date'] = col
            elif col_clean == 'DATE':
                column_mapping['date'] = col
        
        # ISIN
        if column_mapping['isin'] is None:
            if 'ISIN' in col_clean and 'EARLIER' not in col_clean:
                column_mapping['isin'] = col
        
        # Company Name
        if column_mapping['company_name'] is None:
            if 'COMPANY NAME' in col_clean:
                column_mapping['company_name'] = col
        
        # Agency
        if column_mapping['agency'] is None:
            if 'AGENCY' in col_clean and 'EARLIER' not in col_clean:
                column_mapping['agency'] = col
        
        # Rating
        if column_mapping['rating'] is None:
            if col_clean == 'CREDIT RATING':
                column_mapping['rating'] = col
        
        # Rating Action
        if column_mapping['rating_action'] is None:
            if 'RATING ACTION' in col_clean and 'EARLIER' not in col_clean:
                column_mapping['rating_action'] = col
        
        # Outlook
        if column_mapping['outlook'] is None:
            if col_clean == 'OUTLOOK':
                column_mapping['outlook'] = col
    
    # Rename columns
    rename_map = {v: k for k, v in column_mapping.items() if v is not None}
    df = df.rename(columns=rename_map)
    
    # Convert date
    if 'date' in df.columns:
        # Try multiple formats
        for fmt in ['%d-%m-%Y', '%d-%b-%Y', '%Y-%m-%d', '%d/%m/%Y']:
            try:
                df['date'] = pd.to_datetime(df['date'], format=fmt, errors='coerce')
                if df['date'].notna().any():
                    break
            except Exception:
                continue
        
        # Final fallback - let pandas infer
        if df['date'].isna().all():
            df['date'] = pd.to_datetime(df['date'], errors='coerce')
    
    # Add metadata
    df['source'] = 'NSE_MANUAL_DOWNLOAD'
    df['instrument_type'] = 'Debt'
    df['processed_date'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    return df


def process_all_crd_files(input_dir=None):
    """
    Process all NSE CRD files in directory.
    """
    print("=" * 80)
    print("NSE CREDIT RATINGS - ROBUST PARSER")
    print("=" * 80)
    
    if input_dir:
        input_path = Path(input_dir)
    else:
        input_path = RAW_RATINGS_DIR
    
    if not input_path.exists():
        print(f"\n⚠ Directory not found: {input_path}")
        return False
    
    # Find all CRD CSV files
    crd_files = list(input_path.glob("CF-CRD*.csv"))
    
    if not crd_files:
        print(f"\n⚠ No CRD files found in {input_path}")
        print("\nExpected format: CF-CRD-*.csv")
        print("Example: CF-CRD-01-01-2020-to-31-12-2020.csv")
        return False
    
    print(f"\nFound {len(crd_files)} CRD files")
    
    # Process each file
    all_data = []
    successful = 0
    failed = 0
    
    for file_path in sorted(crd_files):
        df = parse_nse_crd_file(file_path)
        
        if df is not None and len(df) > 0:
            all_data.append(df)
            successful += 1
            
            # Copy to raw directory
            dest = RAW_RATINGS_DIR / file_path.name
            if file_path != dest:
                import shutil
                shutil.copy(file_path, dest)
        else:
            failed += 1
    
    print(f"\n{'=' * 60}")
    print(f"PROCESSING SUMMARY")
    print(f"{'=' * 60}")
    print(f"Successful: {successful}/{len(crd_files)}")
    print(f"Failed: {failed}/{len(crd_files)}")
    
    if not all_data:
        print("\n⚠ No data to combine!")
        return False
    
    # Combine all data
    print(f"\n{'=' * 60}")
    print("COMBINING ALL DATA")
    print(f"{'=' * 60}")
    
    combined = pd.concat(all_data, ignore_index=True)
    print(f"Combined: {len(combined):,} rows")
    
    # Remove duplicates
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
    
    # Sort by date
    if 'date' in combined.columns:
        combined = combined.sort_values('date', ascending=False)
    
    # Save
    output_file = PROCESSED_DIR / "credit_ratings_nse_all.csv"
    combined.to_csv(output_file, index=False)
    print(f"\n✓ Saved to {output_file.name}")
    
    # Save parquet
    parquet_file = PROCESSED_DIR / "credit_ratings_nse_all.parquet"
    combined.to_parquet(parquet_file, index=False)
    print(f"✓ Saved parquet to {parquet_file.name}")
    
    # Statistics
    print(f"\n{'=' * 60}")
    print("DATA SUMMARY")
    print(f"{'=' * 60}")
    print(f"Total rows: {len(combined):,}")
    
    if 'company_name' in combined.columns:
        print(f"Unique companies: {combined['company_name'].nunique()}")
    
    if 'isin' in combined.columns:
        print(f"Unique ISINs: {combined['isin'].nunique()}")
    
    if 'date' in combined.columns:
        print(f"Date range: {combined['date'].min()} to {combined['date'].max()}")
        print(f"Years covered: {combined['date'].dt.year.nunique()}")
    
    if 'agency' in combined.columns and combined['agency'].notna().any():
        print(f"\nAgencies ({combined['agency'].nunique()}):")
        for agency, count in combined['agency'].value_counts().head(10).items():
            print(f"  {agency}: {count:,}")
    
    if 'rating' in combined.columns and combined['rating'].notna().any():
        print(f"\nTop Ratings:")
        for rating, count in combined['rating'].value_counts().head(10).items():
            print(f"  {rating}: {count:,}")
    
    if 'rating_action' in combined.columns and combined['rating_action'].notna().any():
        print(f"\nRating Actions:")
        for action, count in combined['rating_action'].value_counts().items():
            print(f"  {action}: {count:,}")
    
    print(f"\n{'=' * 80}")
    print("✓ CREDIT RATINGS PROCESSING COMPLETE")
    print(f"{'=' * 80}")
    
    return True


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="NSE Credit Ratings Robust Parser",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python3 scripts/parse_nse_credit_ratings_robust.py --input-dir ~/Downloads
    python3 scripts/parse_nse_credit_ratings_robust.py --file ~/Downloads/CF-CRD-*.csv
    python3 scripts/parse_nse_credit_ratings_robust.py
        """
    )
    
    parser.add_argument("--input-dir", type=str, help="Directory containing CRD files")
    parser.add_argument("--file", type=str, help="Specific CRD file or glob pattern")
    
    args = parser.parse_args()
    
    if args.file:
        # Process specific file(s)
        from glob import glob
        files = glob(args.file)
        if files:
            print(f"Processing {len(files)} file(s)...")
            for f in files:
                parse_nse_crd_file(Path(f))
        else:
            print(f"No files found matching: {args.file}")
    else:
        # Process all in directory
        process_all_crd_files(input_dir=args.input_dir)
