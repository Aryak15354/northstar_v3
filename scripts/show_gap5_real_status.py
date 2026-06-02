#!/usr/bin/env python3
"""
Show Gap 5 REAL Status - No BS, Just Facts

Checks actual data files and shows what's really happening.
"""

import sys
import os
from pathlib import Path
from datetime import datetime
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def check_ledger():
    """Check master ledger real data"""
    print("\n1. MASTER LEDGER (Real Data)")
    print("=" * 60)
    
    ledger_path = Path("data/pnl/master_ledger.parquet")
    if not ledger_path.exists():
        print("   ✗ Master ledger does not exist")
        return False
    
    df = pd.read_parquet(ledger_path)
    print(f"   Entries: {len(df)}")
    print(f"   Date range: {df['trade_date'].min()} to {df['trade_date'].max()}")
    print(f"   Total P&L: ₹{df['net_pnl'].sum():,.2f}")
    print(f"   Books: {df['book'].unique().tolist()}")
    print(f"   Strategies: {df['strategy_id'].nunique()} unique")
    
    # Check tickers
    tickers = df['ticker'].unique()
    print(f"   Tickers: {len(tickers)} unique")
    print(f"   Sample tickers: {list(tickers[:10])}")
    
    return True


def check_nav_history():
    """Check NAV history real data"""
    print("\n2. NAV HISTORY (Real Data)")
    print("=" * 60)
    
    nav_path = Path("data/pnl/nav_history.parquet")
    if not nav_path.exists():
        print("   ✗ NAV history does not exist")
        return False
    
    df = pd.read_parquet(nav_path)
    nav_col = 'nav_combined' if 'nav_combined' in df.columns else 'nav'
    print(f"   Days: {len(df)}")
    print(f"   Date range: {df['date'].min()} to {df['date'].max()}")
    print(f"   Starting NAV: ₹{df[nav_col].iloc[0]:,.2f}")
    print(f"   Current NAV: ₹{df[nav_col].iloc[-1]:,.2f}")
    
    total_return = (df[nav_col].iloc[-1] / df[nav_col].iloc[0] - 1) * 100
    print(f"   Total Return: {total_return:.2f}%")
    
    # Sharpe approximation
    if 'return' in df.columns:
        sharpe = df['return'].mean() / df['return'].std() * 15.87 if df['return'].std() > 0 else 0
        print(f"   Sharpe Ratio: {sharpe:.2f}")
    
    return True


def check_reconciliation():
    """Check reconciliation status"""
    print("\n3. RECONCILIATION STATUS")
    print("=" * 60)
    
    recon_path = Path("data/pnl/reconciliation_log.parquet")
    if not recon_path.exists():
        print("   ✗ No reconciliation log")
        return False
    
    df = pd.read_parquet(recon_path)
    print(f"   Total runs: {len(df)}")
    print(f"   Date range: {df['date'].min()} to {df['date'].max()}")
    print(f"   Status counts:")
    for status, count in df['overall_status'].value_counts().items():
        print(f"      {status}: {count}")
    
    clean_days = (df['overall_status'] == 'CLEAN').sum()
    print(f"\n   Clean days: {clean_days}/30 required for operational status")
    
    if clean_days < 30:
        print(f"   ⚠ Need {30 - clean_days} more clean days")
    
    return clean_days >= 30


def check_sector_attribution():
    """Check if sector attribution can work"""
    print("\n4. SECTOR ATTRIBUTION")
    print("=" * 60)
    
    # Check sector mapping
    mapping_path = Path("data/metadata/ticker_sector_mapping.csv")
    if not mapping_path.exists():
        print("   ✗ Sector mapping does not exist")
        return False
    
    mapping = pd.read_csv(mapping_path)
    print(f"   Tickers mapped: {len(mapping)}")
    print(f"   Sectors: {mapping['sector'].nunique()}")
    
    # Check if ledger tickers are in mapping
    ledger_path = Path("data/pnl/master_ledger.parquet")
    if ledger_path.exists():
        ledger = pd.read_parquet(ledger_path)
        ledger_tickers = set(ledger['ticker'].unique())
        mapped_tickers = set(mapping['ticker'].unique())
        
        overlap = ledger_tickers & mapped_tickers
        print(f"\n   Ledger tickers: {len(ledger_tickers)}")
        print(f"   Mapped tickers: {len(mapped_tickers)}")
        print(f"   Overlap: {len(overlap)} tickers")
        
        if len(overlap) == 0:
            print(f"   ⚠ NO OVERLAP - Sector attribution won't work")
            print(f"   Ledger tickers: {list(ledger_tickers)[:10]}")
            print(f"   Mapped tickers: {list(mapped_tickers)[:10]}")
            return False
        else:
            print(f"   ✓ {len(overlap)} tickers can be attributed to sectors")
    
    return True


def check_dashboard_source():
    """Check what the dashboard is actually reading"""
    print("\n5. DASHBOARD DATA SOURCE")
    print("=" * 60)
    
    legacy_path = Path("data/portfolio/pnl_on_paper.parquet")
    unified_path = Path("data/pnl/nav_history.parquet")
    
    print(f"   Legacy file (pnl_on_paper.parquet):")
    if legacy_path.exists():
        df = pd.read_parquet(legacy_path)
        print(f"      ✓ EXISTS - {len(df)} rows")
        print(f"      Last update: {legacy_path.stat().st_mtime}")
    else:
        print(f"      ✗ Does not exist")
    
    print(f"\n   Unified file (nav_history.parquet):")
    if unified_path.exists():
        df = pd.read_parquet(unified_path)
        print(f"      ✓ EXISTS - {len(df)} rows")
        print(f"      Last update: {unified_path.stat().st_mtime}")
    else:
        print(f"      ✗ Does not exist")
    
    # Check which is newer
    if legacy_path.exists() and unified_path.exists():
        legacy_time = legacy_path.stat().st_mtime
        unified_time = unified_path.stat().st_mtime
        
        if legacy_time > unified_time:
            print(f"\n   ⚠ LEGACY FILE IS NEWER - Dashboard likely reading legacy")
            return False
        else:
            print(f"\n   ✓ Unified file is newer")
            return True
    
    return False


def check_eod_integration():
    """Check if EOD script calls unified P&L"""
    print("\n6. EOD INTEGRATION")
    print("=" * 60)
    
    eod_path = Path("scripts/eod_rebalance.py")
    if not eod_path.exists():
        print("   ✗ EOD script does not exist")
        return False
    
    with open(eod_path, 'r') as f:
        content = f.read()
    
    if 'eod_rebalance_with_pnl' in content:
        print("   ✓ EOD script calls unified P&L system")
        return True
    else:
        print("   ✗ EOD script does NOT call unified P&L")
        print("   ⚠ Ledger will not receive EOD marks")
        return False


def check_benchmark_data():
    """Check benchmark data"""
    print("\n7. BENCHMARK DATA")
    print("=" * 60)
    
    benchmark_path = Path("data/pnl/benchmark_returns.parquet")
    if not benchmark_path.exists():
        print("   ✗ Benchmark data does not exist")
        return False
    
    df = pd.read_parquet(benchmark_path)
    print(f"   Days: {len(df)}")
    print(f"   Date range: {df['date'].min()} to {df['date'].max()}")
    
    return True


def main():
    """Show real Gap 5 status"""
    print("=" * 80)
    print("GAP 5 REAL STATUS - NO BS, JUST FACTS")
    print("=" * 80)
    
    results = {
        'Master Ledger': check_ledger(),
        'NAV History': check_nav_history(),
        'Reconciliation': check_reconciliation(),
        'Sector Attribution': check_sector_attribution(),
        'Dashboard Source': check_dashboard_source(),
        'EOD Integration': check_eod_integration(),
        'Benchmark Data': check_benchmark_data(),
    }
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    for check, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {check}")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    print(f"\n{passed}/{total} checks passed")
    
    # Honest assessment
    print("\n" + "=" * 80)
    print("HONEST ASSESSMENT")
    print("=" * 80)
    
    if passed == total:
        print("✅ Gap 5 is complete and operational")
    elif passed >= 5:
        print("⚠ Gap 5 is built but not fully operational")
        print("   Issues to fix:")
        for check, passed in results.items():
            if not passed:
                print(f"   - {check}")
    else:
        print("✗ Gap 5 has significant gaps")
        print("   Critical issues:")
        for check, passed in results.items():
            if not passed:
                print(f"   - {check}")
    
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
