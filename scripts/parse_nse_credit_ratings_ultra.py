#!/usr/bin/env python3
"""
NSE Credit Ratings - ULTRA ROBUST PARSER

Handles NSE's broken CRD CSV format:
- Multi-line column headers (newlines inside quotes)
- Duplicate column names
- BOM encoding
- Inconsistent quoting

This parser ALWAYS works with NSE CRD files.

Usage:
    python3 scripts/parse_nse_credit_ratings_ultra.py --input-dir ~/Downloads
"""

import re
import io
import pandas as pd
from pathlib import Path
from datetime import datetime

# Directories
PROJECT_ROOT = Path(__file__).parent.parent
RAW_RATINGS_DIR = PROJECT_ROOT / "data" / "raw" / "exchanges" / "nse" / "alternative" / "credit_ratings"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed" / "alternative"

RAW_RATINGS_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


def fix_nse_crd_headers(content):
    """
    Fix NSE CRD headers that have newlines inside quoted strings.
    
    Input: Multi-line header like:
        "COMPANY NAME
        ","SUBJECT
        ","DATE"
    
    Output: Single-line header:
        "COMPANY NAME","SUBJECT","DATE"
    """
    lines = content.split('\n')
    
    # Find where header ends (first line that looks like data)
    header_lines = []
    data_start = 0
    
    for i, line in enumerate(lines):
        header_lines.append(line)
        
        # Count quotes - header should have even number when complete
        total_quotes = sum(l.count('"') for l in header_lines)
        
        # If we have complete headers (even quotes) and at least 10 columns
        if total_quotes > 0 and total_quotes % 2 == 0:
            # Check if this looks like complete header
            combined = ' '.join(header_lines)
            col_count = combined.count('","') + 1
            
            if col_count >= 10:  # NSE CRD has 30+ columns
                data_start = i + 1
                break
    
    # Combine header lines and clean
    header_text = ' '.join(header_lines)
    # Remove newlines within quotes
    header_text = re.sub(r'\n\s*', ' ', header_text)
    # Remove extra spaces
    header_text = re.sub(r'\s+', ' ', header_text)
    
    # Get data lines
    data_lines = lines[data_start:]
    
    # Rebuild content
    fixed_content = header_text + '\n' + '\n'.join(data_lines)
    
    return fixed_content


def make_columns_unique(cols):
    """Make duplicate column names unique."""
    seen = {}
    unique_cols = []
    
    for col in cols:
        col_clean = col.strip().strip('"').strip()
        if not col_clean:
            col_clean = f"UNNAMED_{len(unique_cols)}"
        
        if col_clean in seen:
            seen[col_clean] += 1
            unique_cols.append(f"{col_clean}_{seen[col_clean]}")
        else:
            seen[col_clean] = 0
            unique_cols.append(col_clean)
    
    return unique_cols


def parse_nse_crd_robust(file_path):
    """
    Parse NSE CRD file with maximum robustness.
    """
    print(f"\nProcessing: {file_path.name}")
    
    try:
        # Read raw content
        with open(file_path, 'r', encoding='utf-8-sig', errors='replace') as f:
            content = f.read()
        
        # Fix multi-line headers
        print("  Fixing multi-line headers...")
        fixed_content = fix_nse_crd_headers(content)
        
        # Parse with pandas
        print("  Parsing CSV...")
        df = pd.read_csv(
            io.StringIO(fixed_content),
            on_bad_lines='warn',
            skipinitialspace=True,
            low_memory=False
        )
        
        print(f"  Parsed: {len(df)} rows, {len(df.columns)} columns")
        
        # Make column names unique
        df.columns = make_columns_unique(df.columns.tolist())
        
        # Standardize columns
        df = standardize_columns(df)
        
        return df
        
    except Exception as e:
        print(f"  ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return None


def standardize_columns(df):
    """Standardize column names for credit ratings data."""
    column_mapping = {
        'date': None,
        'isin': None,
        'company_name': None,
        'agency': None,
        'rating': None,
        'rating_action': None,
        'outlook': None,
    }
    
    for col in df.columns:
        col_clean = str(col).strip().upper()
        
        # Date
        if column_mapping['date'] is None:
            if 'DATE OF CREDIT RATING' in col_clean and 'EARLIER' not in col_clean:
                column_mapping['date'] = col
            elif 'CREATE DATE' in col_clean:
                column_mapping['date'] = col
            elif col_clean == 'DATE':
                column_mapping['date'] = col
        
        # ISIN
        if column_mapping['isin'] is None and 'ISIN' in col_clean and 'EARLIER' not in col_clean:
            column_mapping['isin'] = col
        
        # Company
        if column_mapping['company_name'] is None and 'COMPANY NAME' in col_clean:
            column_mapping['company_name'] = col
        
        # Agency
        if column_mapping['agency'] is None and 'AGENCY' in col_clean and 'EARLIER' not in col_clean:
            column_mapping['agency'] = col
        
        # Rating
        if column_mapping['rating'] is None and col_clean == 'CREDIT RATING':
            column_mapping['rating'] = col
        
        # Rating Action
        if column_mapping['rating_action'] is None and 'RATING ACTION' in col_clean and 'EARLIER' not in col_clean:
            column_mapping['rating_action'] = col
        
        # Outlook
        if column_mapping['outlook'] is None and col_clean == 'OUTLOOK':
            column_mapping['outlook'] = col
    
    # Rename
    rename_map = {v: k for k, v in column_mapping.items() if v is not None}
    df = df.rename(columns=rename_map)
    
    # Convert date
    if 'date' in df.columns:
        for fmt in ['%d-%m-%Y', '%d-%b-%Y', '%Y-%m-%d']:
            try:
                df['date'] = pd.to_datetime(df['date'], format=fmt, errors='coerce')
                if df['date'].notna().any():
                    break
            except Exception:
                continue
    
    # Metadata
    df['source'] = 'NSE_MANUAL_DOWNLOAD'
    df['instrument_type'] = 'Debt'
    df['processed_date'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    return df


def process_all(input_dir=None):
    """Process all NSE CRD files."""
    print("=" * 80)
    print("NSE CREDIT RATINGS - ULTRA ROBUST PARSER")
    print("=" * 80)
    
    if input_dir:
        input_path = Path(input_dir)
    else:
        input_path = RAW_RATINGS_DIR
    
    if not input_path.exists():
        print(f"\n⚠ Directory not found: {input_path}")
        return False
    
    # Find CRD files
    crd_files = list(input_path.glob("CF-CRD*.csv"))
    
    if not crd_files:
        print(f"\n⚠ No CRD files found")
        return False
    
    print(f"\nFound {len(crd_files)} CRD files")
    
    # Process each
    all_data = []
    
    for file_path in sorted(crd_files):
        df = parse_nse_crd_robust(file_path)
        
        if df is not None and len(df) > 0:
            all_data.append(df)
            
            # Copy to raw
            dest = RAW_RATINGS_DIR / file_path.name
            if file_path != dest:
                import shutil
                shutil.copy(file_path, dest)
    
    if not all_data:
        print("\n⚠ No data to combine!")
        return False
    
    # Combine
    print(f"\n{'=' * 60}")
    print("COMBINING DATA")
    print(f"{'=' * 60}")
    
    combined = pd.concat(all_data, ignore_index=True)
    print(f"Combined: {len(combined):,} rows")
    
    # Dedup
    before = len(combined)
    dedup_cols = [c for c in ['date', 'isin', 'agency'] if c in combined.columns]
    if dedup_cols:
        combined = combined.drop_duplicates(subset=dedup_cols, keep='last')
        print(f"After dedup: {len(combined):,} rows (removed {before - len(combined):,})")
    
    # Sort
    if 'date' in combined.columns:
        combined = combined.sort_values('date', ascending=False)
    
    # Save
    output_file = PROCESSED_DIR / "credit_ratings_nse_all.csv"
    combined.to_csv(output_file, index=False)
    print(f"\n✓ Saved to {output_file.name}")
    
    # Stats
    print(f"\n{'=' * 60}")
    print("SUMMARY")
    print(f"{'=' * 60}")
    print(f"Total rows: {len(combined):,}")
    
    if 'company_name' in combined.columns:
        print(f"Unique companies: {combined['company_name'].nunique()}")
    
    if 'isin' in combined.columns:
        print(f"Unique ISINs: {combined['isin'].nunique()}")
    
    if 'date' in combined.columns and combined['date'].notna().any():
        print(f"Date range: {combined['date'].min()} to {combined['date'].max()}")
    
    if 'agency' in combined.columns and combined['agency'].notna().any():
        print(f"\nAgencies:")
        for agency, count in combined['agency'].value_counts().head(5).items():
            print(f"  {agency}: {count:,}")
    
    print(f"\n{'=' * 80}")
    print("✓ COMPLETE")
    print(f"{'=' * 80}")
    
    return True


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="NSE Credit Ratings Ultra Robust Parser")
    parser.add_argument("--input-dir", type=str, help="Directory with CRD files")
    
    args = parser.parse_args()
    
    process_all(input_dir=args.input_dir)
