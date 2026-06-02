#!/usr/bin/env python3
"""
Gap 5 Reconciliation Monitoring Script

Monitors daily reconciliation for 30 days and generates reports.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))


def load_reconciliation_log():
    """Load reconciliation log"""
    log_path = Path("data/pnl/reconciliation_log.parquet")
    if not log_path.exists():
        return pd.DataFrame()
    return pd.read_parquet(log_path)


def analyze_reconciliation_history(days=30):
    """Analyze reconciliation history"""
    df = load_reconciliation_log()
    
    if len(df) == 0:
        print("No reconciliation data available")
        return None
    
    # Ensure date column is datetime
    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'])
    
    # Filter to last N days
    cutoff_date = datetime.now() - timedelta(days=days)
    recent_df = df[df['date'] >= cutoff_date]
    
    return recent_df


def main():
    print("\n" + "="*80)
    print("GAP 5 RECONCILIATION MONITORING")
    print("="*80)
    print(f"Report generated at: {datetime.now()}")
    
    # Load data
    print("\n1. Loading reconciliation history...")
    df = analyze_reconciliation_history(30)
    
    if df is None or len(df) == 0:
        print("   ⚠ No reconciliation data found")
        print("\n   To start monitoring:")
        print("   1. Run migration: python scripts/run_gap5_migration.py")
        print("   2. Run EOD process: python scripts/eod_rebalance_with_pnl.py")
        print("   3. Run this monitor daily")
        return 1
    
    print(f"   ✓ Loaded {len(df)} reconciliation records")
    
    # Status summary
    print("\n2. Reconciliation Status Summary (Last 30 Days)")
    print("   " + "-"*60)
    
    status_counts = df['overall_status'].value_counts()
    for status, count in status_counts.items():
        pct = count / len(df) * 100
        symbol = "✓" if status == "CLEAN" else "⚠" if status == "WARNING" else "✗"
        print(f"   {symbol} {status}: {count} days ({pct:.1f}%)")
    
    # Clean streak
    print("\n3. Clean Reconciliation Streak")
    print("   " + "-"*60)
    
    # Sort by date descending
    df_sorted = df.sort_values('date', ascending=False)
    
    clean_streak = 0
    for _, row in df_sorted.iterrows():
        if row['overall_status'] == 'CLEAN':
            clean_streak += 1
        else:
            break
    
    if clean_streak >= 30:
        print(f"   ✓ {clean_streak} consecutive clean days - READY FOR PRODUCTION!")
    elif clean_streak >= 7:
        print(f"   ✓ {clean_streak} consecutive clean days - Good progress")
    else:
        print(f"   ⚠ {clean_streak} consecutive clean days - Continue monitoring")
    
    # Recent issues
    print("\n4. Recent Issues")
    print("   " + "-"*60)
    
    issues_df = df[df['overall_status'] != 'CLEAN'].tail(5)
    if len(issues_df) > 0:
        print(f"   Last {len(issues_df)} non-clean reconciliations:")
        for _, row in issues_df.iterrows():
            print(f"   - {row['date'].date()}: {row['overall_status']}")
            if 'actions' in row and row['actions']:
                print(f"     Actions: {row['actions']}")
    else:
        print("   ✓ No recent issues")
    
    # Discrepancy trends
    print("\n5. Discrepancy Trends")
    print("   " + "-"*60)
    
    if 'equity_options_discrepancy_inr' in df.columns:
        avg_eq_opt_disc = df['equity_options_discrepancy_inr'].abs().mean()
        print(f"   Avg Equity/Options discrepancy: ₹{avg_eq_opt_disc:.2f}")
    
    if 'live_shadow_discrepancy_pct' in df.columns:
        avg_live_shadow = df['live_shadow_discrepancy_pct'].abs().mean()
        print(f"   Avg Live/Shadow discrepancy: {avg_live_shadow:.3f}%")
    
    # Recommendations
    print("\n6. Recommendations")
    print("   " + "-"*60)
    
    if clean_streak >= 30:
        print("   ✓ 30+ days clean - Ready to archive legacy files")
        print("   ✓ Gap 5 is production-ready")
    elif clean_streak >= 7:
        print("   → Continue monitoring for", 30 - clean_streak, "more days")
    else:
        print("   → Investigate recent reconciliation failures")
        print("   → Review migration conflicts if any")
    
    print("\n" + "="*80)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
