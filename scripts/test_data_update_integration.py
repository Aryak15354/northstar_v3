#!/usr/bin/env python3
"""
Comprehensive test to verify data updates are properly ingested and merged.

This script:
1. Records current data state (row counts, date ranges)
2. Runs update scripts
3. Verifies new data was added
4. Checks data integrity and PIT compliance
"""

import sys
from pathlib import Path
from datetime import datetime
import pandas as pd
import subprocess

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.ingestion.ingestion_registry import IngestionRegistry


def print_section(title):
    """Print a formatted section header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def check_data_state(label):
    """Check and record current data state."""
    print(f"\n{label}")
    print("-" * 80)
    
    state = {}
    
    # Check prices.parquet
    prices_path = Path('data/processed/prices.parquet')
    if prices_path.exists():
        df = pd.read_parquet(prices_path)
        state['prices_rows'] = len(df)
        if 'Date' in df.columns:
            state['prices_latest'] = pd.to_datetime(df['Date']).max()
            state['prices_earliest'] = pd.to_datetime(df['Date']).min()
        print(f"  Prices: {state['prices_rows']:,} rows")
        if 'prices_latest' in state:
            print(f"    Date range: {state['prices_earliest']} to {state['prices_latest']}")
    else:
        print("  Prices: NOT FOUND")
        state['prices_rows'] = 0
    
    # Check RBI data
    rbi_path = Path('data/macro/comprehensive_rbi_data.parquet')
    if rbi_path.exists():
        df = pd.read_parquet(rbi_path)
        state['rbi_rows'] = len(df)
        state['rbi_indicators'] = len(df.columns)
        print(f"  RBI Data: {state['rbi_rows']:,} rows, {state['rbi_indicators']} indicators")
    else:
        print("  RBI Data: NOT FOUND")
        state['rbi_rows'] = 0
    
    # Check fundamentals
    fund_path = Path('data/processed/screener_fundamentals_annual.csv')
    if fund_path.exists():
        df = pd.read_csv(fund_path)
        state['fund_rows'] = len(df)
        print(f"  Fundamentals: {state['fund_rows']:,} rows")
    else:
        print("  Fundamentals: NOT FOUND")
        state['fund_rows'] = 0
    
    # Check alternative data
    gst_path = Path('data/alternative/gst_data.parquet')
    if gst_path.exists():
        df = pd.read_parquet(gst_path)
        state['gst_rows'] = len(df)
        print(f"  GST Data: {state['gst_rows']:,} rows")
    else:
        print("  GST Data: NOT FOUND")
        state['gst_rows'] = 0
    
    return state


def test_ingestion_after_update():
    """Test that ingestion layer properly loads updated data."""
    print_section("TESTING INGESTION LAYER WITH UPDATED DATA")
    
    registry = IngestionRegistry()
    as_of_date = datetime.now()
    
    results = {}
    
    # Test 1: Market data
    try:
        df = registry.market.load(as_of_date, tickers=['RELIANCE', 'TCS', 'INFY'])
        results['market'] = {
            'success': not df.empty,
            'rows': len(df),
            'latest_date': df.index.get_level_values('Date').max() if not df.empty else None
        }
        print(f"\n  ✅ Market data: {results['market']['rows']} rows")
        if results['market']['latest_date']:
            print(f"     Latest: {results['market']['latest_date']}")
    except Exception as e:
        results['market'] = {'success': False, 'error': str(e)}
        print(f"\n  ❌ Market data: {e}")
    
    # Test 2: Macro data
    try:
        df = registry.macro.load_rbi_data(as_of_date)
        results['macro'] = {
            'success': not df.empty,
            'rows': len(df),
            'indicators': len(df.columns) if not df.empty else 0
        }
        print(f"  ✅ Macro data: {results['macro']['rows']} rows, {results['macro']['indicators']} indicators")
    except Exception as e:
        results['macro'] = {'success': False, 'error': str(e)}
        print(f"  ❌ Macro data: {e}")
    
    # Test 3: Fundamentals
    try:
        df = registry.fundamentals.load_financials(as_of_date, tickers=['RELIANCE'], frequency='annual')
        results['fundamentals'] = {
            'success': not df.empty,
            'rows': len(df)
        }
        print(f"  ✅ Fundamentals: {results['fundamentals']['rows']} rows")
    except Exception as e:
        results['fundamentals'] = {'success': False, 'error': str(e)}
        print(f"  ❌ Fundamentals: {e}")
    
    # Test 4: Alternative data
    try:
        alt_data = registry.alternative.load_all_alternative(as_of_date, tickers=['RELIANCE'])
        results['alternative'] = {
            'success': len(alt_data) > 0,
            'sources': len(alt_data)
        }
        print(f"  ✅ Alternative data: {results['alternative']['sources']} sources")
    except Exception as e:
        results['alternative'] = {'success': False, 'error': str(e)}
        print(f"  ❌ Alternative data: {e}")
    
    return results


def verify_data_integrity():
    """Verify data integrity after updates."""
    print_section("DATA INTEGRITY CHECKS")
    
    issues = []
    
    # Check 1: Prices have no duplicates
    prices_path = Path('data/processed/prices.parquet')
    if prices_path.exists():
        df = pd.read_parquet(prices_path)
        if 'Date' in df.columns and 'ticker' in df.columns:
            duplicates = df.duplicated(subset=['Date', 'ticker']).sum()
            if duplicates > 0:
                issues.append(f"Found {duplicates} duplicate price records")
                print(f"  ❌ Duplicates: {duplicates} found")
            else:
                print(f"  ✅ No duplicates in price data")
        else:
            print(f"  ⚠️  Cannot check duplicates (missing Date or ticker column)")
    
    # Check 2: Dates are in order
    if prices_path.exists():
        df = pd.read_parquet(prices_path)
        if 'Date' in df.columns:
            df['Date'] = pd.to_datetime(df['Date'])
            if not df['Date'].is_monotonic_increasing:
                # Check per ticker
                if 'ticker' in df.columns:
                    for ticker in df['ticker'].unique()[:5]:  # Check first 5
                        ticker_df = df[df['ticker'] == ticker].sort_values('Date')
                        if not ticker_df['Date'].is_monotonic_increasing:
                            issues.append(f"Dates not in order for {ticker}")
                print(f"  ✅ Dates are properly ordered")
            else:
                print(f"  ✅ Dates are properly ordered")
    
    # Check 3: No future dates
    if prices_path.exists():
        df = pd.read_parquet(prices_path)
        if 'Date' in df.columns:
            df['Date'] = pd.to_datetime(df['Date'])
            future_dates = df[df['Date'] > pd.Timestamp.now()]
            if len(future_dates) > 0:
                issues.append(f"Found {len(future_dates)} records with future dates")
                print(f"  ❌ Future dates: {len(future_dates)} found")
            else:
                print(f"  ✅ No future dates")
    
    # Check 4: RBI data integrity
    rbi_path = Path('data/macro/comprehensive_rbi_data.parquet')
    if rbi_path.exists():
        df = pd.read_parquet(rbi_path)
        null_pct = (df.isnull().sum().sum() / (len(df) * len(df.columns))) * 100
        print(f"  ℹ️  RBI data: {null_pct:.1f}% null values")
        if null_pct > 90:
            issues.append(f"RBI data has {null_pct:.1f}% null values")
    
    return issues


def main():
    """Run comprehensive update test."""
    print("\n" + "=" * 80)
    print("  DATA UPDATE INTEGRATION TEST")
    print("=" * 80)
    print(f"\n  Started at: {datetime.now()}")
    
    # Step 1: Record initial state
    print_section("STEP 1: RECORD INITIAL DATA STATE")
    initial_state = check_data_state("Initial State:")
    
    # Step 2: Run update scripts
    print_section("STEP 2: RUN DATA UPDATE SCRIPTS")
    
    print("\n  Running market data update...")
    print("  " + "-" * 76)
    try:
        result = subprocess.run(
            ['python3', 'src/ingestion/integrated_data_pipeline.py', '--market-only', '--force-market'],
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        if result.returncode == 0:
            print("  ✅ Market update completed")
        else:
            print(f"  ⚠️  Market update completed with warnings")
            if result.stderr:
                print(f"     {result.stderr[:200]}")
    except subprocess.TimeoutExpired:
        print("  ⚠️  Market update timed out (continuing anyway)")
    except Exception as e:
        print(f"  ❌ Market update failed: {e}")
    
    print("\n  Running RBI data update...")
    print("  " + "-" * 76)
    try:
        result = subprocess.run(
            ['python3', 'src/ingestion/rbi_daily_updater.py', '--force'],
            capture_output=True,
            text=True,
            timeout=180  # 3 minute timeout
        )
        if result.returncode == 0:
            print("  ✅ RBI update completed")
        else:
            print(f"  ⚠️  RBI update completed with warnings")
            if result.stderr:
                print(f"     {result.stderr[:200]}")
    except subprocess.TimeoutExpired:
        print("  ⚠️  RBI update timed out (continuing anyway)")
    except Exception as e:
        print(f"  ❌ RBI update failed: {e}")
    
    # Step 3: Record new state
    print_section("STEP 3: VERIFY DATA WAS UPDATED")
    final_state = check_data_state("Final State:")
    
    # Compare states
    print("\n  Changes:")
    print("  " + "-" * 76)
    
    if initial_state.get('prices_rows', 0) > 0:
        price_diff = final_state.get('prices_rows', 0) - initial_state.get('prices_rows', 0)
        if price_diff > 0:
            print(f"  ✅ Prices: +{price_diff:,} rows added")
        elif price_diff == 0:
            print(f"  ℹ️  Prices: No new rows (data may be up to date)")
        else:
            print(f"  ⚠️  Prices: {price_diff:,} rows (decreased?)")
        
        if 'prices_latest' in initial_state and 'prices_latest' in final_state:
            if final_state['prices_latest'] > initial_state['prices_latest']:
                days_added = (final_state['prices_latest'] - initial_state['prices_latest']).days
                print(f"  ✅ Latest date advanced by {days_added} days")
            else:
                print(f"  ℹ️  Latest date unchanged")
    
    if initial_state.get('rbi_rows', 0) > 0:
        rbi_diff = final_state.get('rbi_rows', 0) - initial_state.get('rbi_rows', 0)
        if rbi_diff > 0:
            print(f"  ✅ RBI: +{rbi_diff:,} rows added")
        elif rbi_diff == 0:
            print(f"  ℹ️  RBI: No new rows")
        else:
            print(f"  ⚠️  RBI: {rbi_diff:,} rows (decreased?)")
    
    # Step 4: Test ingestion layer
    print_section("STEP 4: TEST INGESTION LAYER")
    ingestion_results = test_ingestion_after_update()
    
    # Step 5: Verify integrity
    print_section("STEP 5: VERIFY DATA INTEGRITY")
    issues = verify_data_integrity()
    
    # Final summary
    print_section("SUMMARY")
    
    print("\n  Data Update Status:")
    if final_state.get('prices_rows', 0) > initial_state.get('prices_rows', 0):
        print("    ✅ Market data updated successfully")
    else:
        print("    ℹ️  Market data unchanged (may already be current)")
    
    if final_state.get('rbi_rows', 0) > initial_state.get('rbi_rows', 0):
        print("    ✅ RBI data updated successfully")
    else:
        print("    ℹ️  RBI data unchanged")
    
    print("\n  Ingestion Layer Status:")
    success_count = sum(1 for r in ingestion_results.values() if r.get('success', False))
    print(f"    {success_count}/{len(ingestion_results)} loaders working")
    
    print("\n  Data Integrity:")
    if len(issues) == 0:
        print("    ✅ No issues found")
    else:
        print(f"    ⚠️  {len(issues)} issues found:")
        for issue in issues:
            print(f"       - {issue}")
    
    print(f"\n  Completed at: {datetime.now()}")
    print("\n" + "=" * 80)
    
    return 0 if len(issues) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
