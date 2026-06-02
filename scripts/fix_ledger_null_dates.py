#!/usr/bin/env python3
"""
Fix Null Trade Dates in Ledger

Investigates and fixes null trade_date entries in the unified ledger.
"""

import sys
from pathlib import Path
from datetime import datetime
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.pnl.ledger import UnifiedPnLLedger


def investigate_null_dates():
    """Investigate null trade_date entries"""
    print("\n" + "="*80)
    print("INVESTIGATING NULL TRADE DATES")
    print("="*80)
    
    # Load ledger
    ledger = UnifiedPnLLedger("data/pnl/master_ledger.parquet")
    df = ledger.query()
    
    print(f"\nTotal entries: {len(df)}")
    
    # Check for nulls
    null_trade_dates = df['trade_date'].isnull().sum()
    print(f"Null trade_dates: {null_trade_dates}")
    
    if null_trade_dates == 0:
        print("\n✓ No null trade_dates found!")
        return True
    
    # Analyze null entries
    print("\n" + "-"*80)
    print("ANALYZING NULL ENTRIES")
    print("-"*80)
    
    null_df = df[df['trade_date'].isnull()]
    
    print(f"\nNull entries by source:")
    print(null_df['source'].value_counts())
    
    print(f"\nNull entries by entry_type:")
    print(null_df['entry_type'].value_counts())
    
    print(f"\nNull entries by book:")
    print(null_df['book'].value_counts())
    
    # Show sample
    print(f"\nSample null entries:")
    print(null_df[['entry_id', 'entry_type', 'book', 'source', 'ticker', 'recorded_at']].head(10))
    
    return False


def fix_null_dates():
    """Fix null trade_date entries"""
    print("\n" + "="*80)
    print("FIXING NULL TRADE DATES")
    print("="*80)
    
    # Load raw parquet
    ledger_path = Path("data/pnl/master_ledger.parquet")
    df = pd.read_parquet(ledger_path)
    
    print(f"\nTotal entries: {len(df)}")
    null_count = df['trade_date'].isnull().sum()
    print(f"Null trade_dates: {null_count}")
    
    if null_count == 0:
        print("\n✓ No null trade_dates to fix!")
        return True
    
    # Strategy: Use recorded_at as fallback for trade_date
    print("\n1. Using recorded_at as fallback for null trade_dates...")
    
    null_mask = df['trade_date'].isnull()
    
    # Check if recorded_at is available
    if 'recorded_at' in df.columns:
        # Convert recorded_at to datetime if needed
        if not pd.api.types.is_datetime64_any_dtype(df['recorded_at']):
            df['recorded_at'] = pd.to_datetime(df['recorded_at'], format='mixed', errors='coerce')
        
        # Fill null trade_dates with recorded_at
        df.loc[null_mask, 'trade_date'] = df.loc[null_mask, 'recorded_at']
        
        print(f"   ✓ Filled {null_mask.sum()} null trade_dates with recorded_at")
    
    # Check if any nulls remain
    remaining_nulls = df['trade_date'].isnull().sum()
    
    if remaining_nulls > 0:
        print(f"\n2. {remaining_nulls} nulls remain, using current date as fallback...")
        df.loc[df['trade_date'].isnull(), 'trade_date'] = datetime.now()
        print(f"   ✓ Filled remaining nulls with current date")
    
    # Also fix settlement_date if null
    if 'settlement_date' in df.columns:
        settlement_nulls = df['settlement_date'].isnull().sum()
        if settlement_nulls > 0:
            print(f"\n3. Fixing {settlement_nulls} null settlement_dates...")
            df.loc[df['settlement_date'].isnull(), 'settlement_date'] = df.loc[df['settlement_date'].isnull(), 'trade_date']
            print(f"   ✓ Filled null settlement_dates with trade_date")
    
    # Backup original
    backup_path = ledger_path.parent / f"master_ledger_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.parquet"
    print(f"\n4. Creating backup: {backup_path}")
    df_original = pd.read_parquet(ledger_path)
    df_original.to_parquet(backup_path, index=False)
    print(f"   ✓ Backup created")
    
    # Write fixed ledger
    print(f"\n5. Writing fixed ledger...")
    df.to_parquet(ledger_path, index=False)
    print(f"   ✓ Fixed ledger written")
    
    # Verify
    print(f"\n6. Verifying fix...")
    df_verify = pd.read_parquet(ledger_path)
    final_nulls = df_verify['trade_date'].isnull().sum()
    
    if final_nulls == 0:
        print(f"   ✓ Verification passed: 0 null trade_dates")
        return True
    else:
        print(f"   ✗ Verification failed: {final_nulls} null trade_dates remain")
        return False


def main():
    print("\n" + "="*80)
    print("LEDGER NULL DATE FIX UTILITY")
    print("="*80)
    print(f"Started at: {datetime.now()}")
    
    # Step 1: Investigate
    clean = investigate_null_dates()
    
    if clean:
        print("\n" + "="*80)
        print("✓ LEDGER IS CLEAN - NO ACTION NEEDED")
        print("="*80)
        return 0
    
    # Step 2: Ask for confirmation
    print("\n" + "="*80)
    print("FIX RECOMMENDATION")
    print("="*80)
    print("\nThe script will:")
    print("  1. Create a backup of the current ledger")
    print("  2. Fill null trade_dates with recorded_at timestamps")
    print("  3. Fill any remaining nulls with current date")
    print("  4. Fix null settlement_dates")
    print("  5. Verify the fix")
    
    response = input("\nProceed with fix? (y/n): ")
    
    if response.lower() != 'y':
        print("\nFix cancelled.")
        return 1
    
    # Step 3: Fix
    success = fix_null_dates()
    
    if success:
        print("\n" + "="*80)
        print("✓ FIX COMPLETE")
        print("="*80)
        print("\nNext steps:")
        print("  1. Run validation: python scripts/validate_gap5_complete.py")
        print("  2. Run EOD process: python scripts/eod_rebalance_with_pnl.py")
        print("  3. Monitor reconciliation: python scripts/monitor_gap5_reconciliation.py")
        return 0
    else:
        print("\n" + "="*80)
        print("✗ FIX FAILED")
        print("="*80)
        print("\nManual intervention required.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
