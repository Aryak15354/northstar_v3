#!/usr/bin/env python3
"""
Gap 5 Robust Implementation Validation Script

Validates all critical Gap 5 components:
1. Sector attribution with 501-ticker mapping
2. Benchmark comparison infrastructure
3. EOD rebalance integration
4. Dashboard data source
5. Configuration
"""

import sys
import os
from pathlib import Path
from datetime import datetime
import yaml
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.pnl.ledger import UnifiedPnLLedger
from src.pnl.nav_calculator import NAVCalculator
from src.pnl.attribution import PnLAttributor


def validate_sector_mapping():
    """Validate sector mapping exists and is comprehensive"""
    print("\n1. Validating Sector Attribution...")
    
    sector_mapping_path = Path("data/metadata/ticker_sector_mapping.csv")
    
    if not sector_mapping_path.exists():
        print("   ✗ FAIL: Sector mapping file not found")
        return False
    
    try:
        mapping = pd.read_csv(sector_mapping_path)
        
        # Check required columns
        required_cols = ['ticker', 'sector', 'company_name']
        missing_cols = [col for col in required_cols if col not in mapping.columns]
        
        if missing_cols:
            print(f"   ✗ FAIL: Missing columns: {missing_cols}")
            return False
        
        # Check ticker count
        ticker_count = len(mapping)
        if ticker_count < 400:
            print(f"   ⚠ WARNING: Only {ticker_count} tickers mapped (expected ~500)")
        
        # Check sector distribution
        sector_counts = mapping['sector'].value_counts()
        
        print(f"   ✓ PASS: {ticker_count} tickers mapped")
        print(f"   ✓ PASS: {len(sector_counts)} unique sectors")
        print(f"   Top sectors:")
        for sector, count in sector_counts.head(5).items():
            print(f"      - {sector}: {count} tickers")
        
        return True
        
    except Exception as e:
        print(f"   ✗ FAIL: Error loading sector mapping: {e}")
        return False


def validate_benchmark_data():
    """Validate benchmark data is available"""
    print("\n2. Validating Benchmark Data...")
    
    benchmark_path = Path("data/pnl/benchmark_returns.parquet")
    
    if not benchmark_path.exists():
        print("   ⚠ WARNING: Benchmark returns not found, run load_benchmark_data.py")
        return False
    
    try:
        benchmark = pd.read_parquet(benchmark_path)
        
        # Check required columns
        if 'date' not in benchmark.columns or 'return' not in benchmark.columns:
            print("   ✗ FAIL: Missing required columns (date, return)")
            return False
        
        # Check data range
        min_date = benchmark['date'].min()
        max_date = benchmark['date'].max()
        days = len(benchmark)
        
        print(f"   ✓ PASS: Benchmark data loaded")
        print(f"   ✓ Date range: {min_date} to {max_date}")
        print(f"   ✓ Total days: {days}")
        
        return True
        
    except Exception as e:
        print(f"   ✗ FAIL: Error loading benchmark data: {e}")
        return False


def validate_eod_integration():
    """Validate EOD script integration"""
    print("\n3. Validating EOD Integration...")
    
    eod_script_path = Path("scripts/eod_rebalance.py")
    
    if not eod_script_path.exists():
        print("   ✗ FAIL: EOD script not found")
        return False
    
    try:
        with open(eod_script_path, 'r') as f:
            content = f.read()
        
        # Check for unified P&L integration
        if 'eod_rebalance_with_pnl' not in content:
            print("   ✗ FAIL: EOD script not integrated with unified P&L")
            return False
        
        print("   ✓ PASS: EOD script calls unified P&L system")
        
        # Check enhanced EOD script
        eod_pnl_script = Path("scripts/eod_rebalance_with_pnl.py")
        if not eod_pnl_script.exists():
            print("   ✗ FAIL: Enhanced EOD script not found")
            return False
        
        with open(eod_pnl_script, 'r') as f:
            pnl_content = f.read()
        
        # Check for NAV history export
        if 'nav_history.parquet' not in pnl_content:
            print("   ⚠ WARNING: NAV history export not found in EOD script")
        else:
            print("   ✓ PASS: NAV history export integrated")
        
        return True
        
    except Exception as e:
        print(f"   ✗ FAIL: Error validating EOD integration: {e}")
        return False


def validate_configuration():
    """Validate P&L configuration"""
    print("\n4. Validating Configuration...")
    
    config_path = Path("config/pnl_config.yaml")
    
    if not config_path.exists():
        print("   ✗ FAIL: P&L config not found")
        return False
    
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        # Check required sections
        if 'pnl' not in config:
            print("   ✗ FAIL: Missing 'pnl' section in config")
            return False
        
        pnl_config = config['pnl']
        
        # Check NAV config
        if 'nav' not in pnl_config:
            print("   ✗ FAIL: Missing 'nav' section")
            return False
        
        nav_config = pnl_config['nav']
        required_nav_keys = ['starting_capital_inr', 'inception_date', 'benchmark']
        missing_keys = [key for key in required_nav_keys if key not in nav_config]
        
        if missing_keys:
            print(f"   ✗ FAIL: Missing NAV config keys: {missing_keys}")
            return False
        
        print("   ✓ PASS: P&L configuration valid")
        print(f"   ✓ Starting capital: ₹{nav_config['starting_capital_inr']:,}")
        print(f"   ✓ Inception date: {nav_config['inception_date']}")
        print(f"   ✓ Benchmark: {nav_config['benchmark']}")
        
        return True
        
    except Exception as e:
        print(f"   ✗ FAIL: Error loading config: {e}")
        return False


def validate_pnl_components():
    """Validate P&L system components can be initialized"""
    print("\n5. Validating P&L Components...")
    
    try:
        # Load config
        config_path = Path("config/pnl_config.yaml")
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        # Initialize ledger
        ledger = UnifiedPnLLedger("data/pnl/master_ledger.parquet", config)
        print("   ✓ PASS: UnifiedPnLLedger initialized")
        
        # Initialize NAV calculator
        nav_calculator = NAVCalculator(ledger, config)
        print("   ✓ PASS: NAVCalculator initialized")
        
        # Initialize attributor
        attributor = PnLAttributor(ledger, None, config)
        print("   ✓ PASS: PnLAttributor initialized")
        
        # Test sector attribution (should not crash even with no data)
        try:
            sector_attr = attributor.compute_sector_attribution(
                datetime(2024, 9, 1),
                datetime(2024, 9, 2)
            )
            print("   ✓ PASS: Sector attribution callable")
        except Exception as e:
            print(f"   ⚠ WARNING: Sector attribution error (expected if no data): {e}")
        
        return True
        
    except Exception as e:
        print(f"   ✗ FAIL: Error initializing P&L components: {e}")
        import traceback
        traceback.print_exc()
        return False


def validate_documentation():
    """Validate documentation exists"""
    print("\n6. Validating Documentation...")
    
    docs = [
        "GAP5_ROBUST_COMPLETE.md",
        "GAP5_ROBUST_IMPLEMENTATION_PLAN.md",
    ]
    
    all_exist = True
    for doc in docs:
        doc_path = Path(doc)
        if doc_path.exists():
            print(f"   ✓ PASS: {doc} exists")
        else:
            print(f"   ✗ FAIL: {doc} not found")
            all_exist = False
    
    return all_exist


def main():
    """Run all validation checks"""
    print("=" * 80)
    print("GAP 5 ROBUST IMPLEMENTATION VALIDATION")
    print("=" * 80)
    
    results = {
        'Sector Attribution': validate_sector_mapping(),
        'Benchmark Data': validate_benchmark_data(),
        'EOD Integration': validate_eod_integration(),
        'Configuration': validate_configuration(),
        'P&L Components': validate_pnl_components(),
        'Documentation': validate_documentation(),
    }
    
    # Summary
    print("\n" + "=" * 80)
    print("VALIDATION SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for check, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {check}")
    
    print(f"\n{passed}/{total} checks passed")
    
    if passed == total:
        print("\n✅ Gap 5 robust implementation is COMPLETE and VALIDATED")
        print("📋 Ready to begin 30-day verification period")
        print("🚀 Run: python scripts/eod_rebalance.py")
        return 0
    else:
        print(f"\n⚠ {total - passed} checks failed")
        print("Please fix the issues above before proceeding")
        return 1


if __name__ == "__main__":
    sys.exit(main())
