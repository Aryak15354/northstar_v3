#!/usr/bin/env python3
"""
Gap 5 Migration Script

Migrates legacy P&L data from 5 fragmented sources into the unified ledger.
"""

import sys
from pathlib import Path
from datetime import datetime
import json

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.pnl.ledger import UnifiedPnLLedger


def main():
    print("\n" + "="*80)
    print("GAP 5 MIGRATION: Legacy P&L Data to Unified Ledger")
    print("="*80)
    print(f"Migration started at: {datetime.now()}")
    
    # Create ledger
    print("\n1. Initializing unified ledger...")
    ledger = UnifiedPnLLedger("data/pnl/master_ledger.parquet")
    print(f"   ✓ Ledger initialized")
    
    # Check if already migrated
    existing_entries = ledger.query()
    if len(existing_entries) > 0:
        migrated_entries = existing_entries[existing_entries['source'] == 'MIGRATION']
        if len(migrated_entries) > 0:
            print(f"\n   ⚠ Warning: Found {len(migrated_entries)} existing migration entries")
            response = input("   Continue with migration? This will add more entries. (y/n): ")
            if response.lower() != 'y':
                print("   Migration cancelled.")
                return 0
    
    # Run migration
    print("\n2. Running migration from legacy sources...")
    print("   This may take a few minutes...")
    
    try:
        result = ledger.migrate_legacy_data()
        
        print("\n" + "="*80)
        print("MIGRATION COMPLETE")
        print("="*80)
        print(f"\n✓ Migrated entries: {result.migrated_count}")
        print(f"✓ Conflicts found: {result.conflict_count}")
        print(f"✓ Migration date: {result.migration_date}")
        
        if result.conflict_count > 0:
            print(f"\n⚠ CONFLICTS DETECTED")
            print(f"   {result.conflict_count} conflicts require manual review")
            print(f"   Conflicts written to: data/pnl/migration_conflicts.json")
            print("\n   Next steps:")
            print("   1. Review data/pnl/migration_conflicts.json")
            print("   2. For each conflict, determine authoritative source")
            print("   3. Record corrections using ledger.correct()")
            print("   4. Re-run validation")
        else:
            print(f"\n✓ NO CONFLICTS - Clean migration!")
        
        # Show summary by source
        print("\n" + "="*80)
        print("MIGRATION SUMMARY BY SOURCE")
        print("="*80)
        
        all_entries = ledger.query()
        migrated = all_entries[all_entries['source'] == 'MIGRATION']
        
        if len(migrated) > 0:
            print(f"\nTotal migrated entries: {len(migrated)}")
            print("\nBy entry type:")
            for entry_type, count in migrated['entry_type'].value_counts().items():
                print(f"   {entry_type}: {count}")
            
            print("\nBy book:")
            for book, count in migrated['book'].value_counts().items():
                print(f"   {book}: {count}")
        
        # Verify ledger integrity
        print("\n" + "="*80)
        print("VERIFYING LEDGER INTEGRITY")
        print("="*80)
        
        total_entries = len(all_entries)
        print(f"\n✓ Total ledger entries: {total_entries}")
        
        # Check for required fields
        null_checks = {
            'entry_id': all_entries['entry_id'].isnull().sum(),
            'trade_date': all_entries['trade_date'].isnull().sum(),
            'book': all_entries['book'].isnull().sum(),
        }
        
        integrity_ok = True
        for field, null_count in null_checks.items():
            if null_count > 0:
                print(f"   ✗ {field}: {null_count} null values")
                integrity_ok = False
            else:
                print(f"   ✓ {field}: No null values")
        
        if integrity_ok:
            print("\n✓ Ledger integrity verified")
        else:
            print("\n✗ Ledger integrity issues detected")
        
        # Next steps
        print("\n" + "="*80)
        print("NEXT STEPS")
        print("="*80)
        
        if result.conflict_count > 0:
            print("\n1. ⚠ RESOLVE CONFLICTS (Required)")
            print("   - Review: data/pnl/migration_conflicts.json")
            print("   - Resolve each conflict manually")
            print("   - Record corrections")
        else:
            print("\n1. ✓ No conflicts to resolve")
        
        print("\n2. Integrate with EOD process")
        print("   - Run: python scripts/integrate_gap5_eod.py")
        
        print("\n3. Start reconciliation monitoring")
        print("   - Run: python scripts/monitor_gap5_reconciliation.py")
        
        return 0 if result.conflict_count == 0 else 1
        
    except Exception as e:
        print(f"\n✗ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
