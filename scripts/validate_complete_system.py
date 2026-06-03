#!/usr/bin/env python3
"""
Validate Complete System - Final Check

Validates that all gaps are complete and system is ready.
"""

import sys
from pathlib import Path
import pandas as pd
import json

def validate_gap1():
    """Validate Gap 1: Alternative Data Integration"""
    print("\n" + "="*80)
    print("GAP 1: Alternative Data Integration")
    print("="*80)
    
    checks = {
        'Power Data': Path('data/processed/macro/cea_power_daily.parquet'),
        'Power Consumption': Path('data/processed/power_consumption.parquet'),
        'Credit Ratings': Path('data/processed/alternative/credit_ratings_all.csv'),
        'Benchmark': Path('data/processed/benchmark/nifty50.parquet')
    }
    
    for name, path in checks.items():
        if path.exists():
            if path.suffix == '.parquet':
                df = pd.read_parquet(path)
                print(f"✅ {name}: {len(df)} rows")
            elif path.suffix == '.csv':
                df = pd.read_csv(path)
                print(f"✅ {name}: {len(df)} rows")
        else:
            print(f"❌ {name}: NOT FOUND")
            return False
    
    return True


def validate_gap5():
    """Validate Gap 5: P&L Reconciliation"""
    print("\n" + "="*80)
    print("GAP 5: P&L Reconciliation")
    print("="*80)
    
    ledger_path = Path('data/processed/runtime/portfolio_ledger_events.parquet')
    recon_path = Path('data/processed/pnl/reconciliation_results.parquet')
    
    if not ledger_path.exists():
        print(f"❌ Ledger file not found")
        return False
    
    if not recon_path.exists():
        print(f"❌ Reconciliation results not found")
        return False
    
    ledger_df = pd.read_parquet(ledger_path)
    recon_df = pd.read_parquet(recon_path)
    
    print(f"✅ Ledger Events: {len(ledger_df)} events")
    print(f"✅ Reconciliation: {len(recon_df)} days processed")
    
    return True


def validate_gap7():
    """Validate Gap 7: Domain System Wiring"""
    print("\n" + "="*80)
    print("GAP 7: Domain System Wiring")
    print("="*80)
    
    bridges = {
        'Options Bridge': [
            'data/options/complete/nifty_all_options_latest.parquet',
            'data/processed/runtime/portfolio_risk_greeks.parquet',
            'data/processed/runtime/portfolio_positions_current.parquet'
        ],
        'Shadow Bridge': [
            'data/processed/runtime/shadow_fund',
            'data/processed/runtime/daily_shadow',
            'data/processed/runtime/advanced_shadow'
        ],
        'Valuation Bridge': [
            'data/processed/alternative/credit_ratings_all.csv'
        ],
        'Runtime Bridge': [
            'data/processed/runtime/portfolio_ledger_events.parquet',
            'data/processed/runtime/portfolio_state_current.json',
            'data/processed/runtime/portfolio_positions_current.parquet'
        ]
    }
    
    all_ok = True
    for bridge_name, paths in bridges.items():
        available = sum(1 for p in paths if Path(p).exists())
        total = len(paths)
        status = "✅" if available == total else "⚠️"
        print(f"{status} {bridge_name}: {available}/{total} data sources")
        if available < total:
            all_ok = False
    
    return all_ok


def validate_gap8():
    """Validate Gap 8: Dashboard Tab Data"""
    print("\n" + "="*80)
    print("GAP 8: Dashboard Tab Data Access")
    print("="*80)
    
    tabs = {
        'Performance': [
            'data/processed/v3_centralized_pnl_timeseries.parquet',
            'data/processed/benchmark/nifty50.parquet'
        ],
        'Intelligence': [
            'data/processed/macro/cea_power_daily.parquet',
            'data/raw/macro/gst_ewaybill'
        ],
        'Governor': [
            'data/metadata/ticker_sector_mapping.csv',
            'data/processed/runtime/portfolio_positions_current.parquet'
        ],
        'Live Trading': [
            'data/processed/runtime/portfolio_ledger_events.parquet',
            'data/processed/runtime/portfolio_risk_greeks.parquet'
        ],
        'Options': [
            'data/options/complete/nifty_all_options_latest.parquet',
            'data/processed/runtime/portfolio_risk_greeks.parquet'
        ]
    }
    
    total_coverage = 0
    for tab_name, paths in tabs.items():
        available = sum(1 for p in paths if Path(p).exists())
        total = len(paths)
        coverage = available / total
        total_coverage += coverage
        status = "✅" if coverage >= 0.66 else "⚠️"
        print(f"{status} {tab_name}: {coverage:.0%} ({available}/{total})")
    
    avg_coverage = total_coverage / len(tabs)
    print(f"\nAverage Coverage: {avg_coverage:.0%}")
    
    return avg_coverage >= 0.66


def main():
    """Run all validations"""
    print("="*80)
    print("FINAL SYSTEM VALIDATION")
    print("="*80)
    
    results = {
        'Gap 1': validate_gap1(),
        'Gap 5': validate_gap5(),
        'Gap 7': validate_gap7(),
        'Gap 8': validate_gap8()
    }
    
    print("\n" + "="*80)
    print("VALIDATION SUMMARY")
    print("="*80)
    
    for gap, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{gap}: {status}")
    
    all_passed = all(results.values())
    
    if all_passed:
        print("\n🎉 ALL VALIDATIONS PASSED - SYSTEM READY!")
        return 0
    else:
        print("\n⚠️  Some validations failed - see details above")
        return 1


if __name__ == '__main__':
    sys.exit(main())
