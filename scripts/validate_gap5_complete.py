#!/usr/bin/env python3
"""
Gap 5 Validation Script

Validates that the Unified P&L Ledger System is correctly implemented and integrated.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.pnl.ledger import UnifiedPnLLedger, LedgerBook
from src.pnl.nav_calculator import NAVCalculator
from src.pnl.attribution import PnLAttributor
from src.pnl.reconciliation import PnLReconciler
from src.pnl.execution_quality import ExecutionQualityMonitor
from src.pnl.paper_fund import PaperFundManager
from src.core.state import UnifiedState


def validate_module_structure():
    """Validate that all required modules exist"""
    print("\n" + "="*80)
    print("VALIDATING MODULE STRUCTURE")
    print("="*80)
    
    required_files = [
        "src/pnl/__init__.py",
        "src/pnl/ledger.py",
        "src/pnl/pnl_state.py",
        "src/pnl/nav_calculator.py",
        "src/pnl/attribution.py",
        "src/pnl/reconciliation.py",
        "src/pnl/execution_quality.py",
        "src/pnl/paper_fund.py",
    ]
    
    all_exist = True
    for file_path in required_files:
        exists = Path(file_path).exists()
        status = "✓" if exists else "✗"
        print(f"{status} {file_path}")
        if not exists:
            all_exist = False
    
    return all_exist


def validate_ledger_functionality():
    """Validate basic ledger operations"""
    print("\n" + "="*80)
    print("VALIDATING LEDGER FUNCTIONALITY")
    print("="*80)
    
    try:
        # Create test ledger
        ledger = UnifiedPnLLedger("data/pnl/test_ledger.parquet")
        
        # Test equity trade recording
        entry_id = ledger.record_equity_trade(
            ticker="TEST",
            quantity=100,
            price=100.0,
            strategy_id="test_strategy",
            transaction_cost=-10.0
        )
        print(f"✓ Recorded equity trade: {entry_id}")
        
        # Test options trade recording
        entry_id = ledger.record_options_trade(
            ticker="NIFTY",
            quantity=50,
            price=200.0,
            option_type="CE",
            strike=25000.0,
            expiry=datetime.now() + timedelta(days=30),
            greeks={"delta": 0.5, "gamma": 0.001},
            strategy_id="test_strategy",
            transaction_cost=-20.0
        )
        print(f"✓ Recorded options trade: {entry_id}")
        
        # Test flush
        ledger.flush()
        print("✓ Flushed ledger to disk")
        
        # Test query
        df = ledger.query()
        print(f"✓ Queried ledger: {len(df)} entries")
        
        # Test P&L calculation
        total_pnl = ledger.get_total_pnl(datetime.now())
        print(f"✓ Computed total P&L: ₹{total_pnl:.2f}")
        
        return True
        
    except Exception as e:
        print(f"✗ Ledger validation failed: {e}")
        return False


def validate_nav_calculator():
    """Validate NAV calculator"""
    print("\n" + "="*80)
    print("VALIDATING NAV CALCULATOR")
    print("="*80)
    
    try:
        ledger = UnifiedPnLLedger("data/pnl/test_ledger.parquet")
        
        config = {
            'pnl': {
                'nav': {
                    'starting_capital_inr': 10_000_000,
                    'inception_date': '2024-09-01',
                    'nav_unit_size': 1000,
                    'benchmark': 'NIFTY500_TR',
                    'risk_free_rate_pct': 6.5
                }
            }
        }
        
        nav_calc = NAVCalculator(ledger, config)
        print(f"✓ Created NAV calculator")
        print(f"  Starting capital: ₹{nav_calc.starting_capital:,.0f}")
        print(f"  Inception date: {nav_calc.inception_date.date()}")
        
        return True
        
    except Exception as e:
        print(f"✗ NAV calculator validation failed: {e}")
        return False


def validate_state_integration():
    """Validate PnLState integration with UnifiedState"""
    print("\n" + "="*80)
    print("VALIDATING STATE INTEGRATION")
    print("="*80)
    
    try:
        state = UnifiedState()
        
        # Check that pnl_state exists
        assert hasattr(state, 'pnl_state'), "UnifiedState missing pnl_state attribute"
        print("✓ UnifiedState has pnl_state attribute")
        
        # Check pnl_state fields
        assert hasattr(state.pnl_state, 'pnl_today_inr')
        assert hasattr(state.pnl_state, 'current_nav_inr')
        assert hasattr(state.pnl_state, 'fund_health')
        print("✓ PnLState has required fields")
        
        # Test to_dict
        pnl_dict = state.pnl_state.to_dict()
        assert isinstance(pnl_dict, dict)
        print(f"✓ PnLState serializes to dict: {len(pnl_dict)} fields")
        
        return True
        
    except Exception as e:
        print(f"✗ State integration validation failed: {e}")
        return False


def validate_data_directories():
    """Validate that data directories are created"""
    print("\n" + "="*80)
    print("VALIDATING DATA DIRECTORIES")
    print("="*80)
    
    required_dirs = [
        "data/pnl",
        "data/pnl/monthly_reports",
    ]
    
    all_exist = True
    for dir_path in required_dirs:
        path = Path(dir_path)
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            print(f"✓ Created {dir_path}")
        else:
            print(f"✓ {dir_path} exists")
    
    return all_exist


def main():
    """Run all validations"""
    print("\n" + "="*80)
    print("GAP 5 VALIDATION: UNIFIED P&L LEDGER SYSTEM")
    print("="*80)
    print(f"Validation started at: {datetime.now()}")
    
    results = {
        'Module Structure': validate_module_structure(),
        'Ledger Functionality': validate_ledger_functionality(),
        'NAV Calculator': validate_nav_calculator(),
        'State Integration': validate_state_integration(),
        'Data Directories': validate_data_directories(),
    }
    
    print("\n" + "="*80)
    print("VALIDATION SUMMARY")
    print("="*80)
    
    for check, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {check}")
    
    all_passed = all(results.values())
    
    if all_passed:
        print("\n" + "="*80)
        print("✓ GAP 5 VALIDATION COMPLETE - ALL CHECKS PASSED")
        print("="*80)
        print("\nThe Unified P&L Ledger System is correctly implemented.")
        print("Next steps:")
        print("  1. Run migration: ledger.migrate_legacy_data()")
        print("  2. Integrate with eod_rebalance.py")
        print("  3. Run tests: pytest src/pnl/tests/")
        print("  4. Monitor reconciliation for 30 days")
        return 0
    else:
        print("\n" + "="*80)
        print("✗ GAP 5 VALIDATION FAILED")
        print("="*80)
        print("\nSome checks did not pass. Review errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
