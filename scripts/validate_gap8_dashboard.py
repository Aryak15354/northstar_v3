#!/usr/bin/env python3
"""
Validate Gap 8 Dashboard Implementation

Checks:
1. All required files exist
2. Data contract can be imported
3. All tabs can be imported
4. Launch script is executable
5. Data contract methods are available
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

def check_files_exist():
    """Check that all required files exist"""
    print("📁 Checking file structure...")
    
    required_files = [
        "src/dashboard/app.py",
        "src/dashboard/data_contract.py",
        "src/dashboard/tabs/__init__.py",
        "src/dashboard/tabs/live_trading.py",
        "src/dashboard/tabs/portfolio_governor.py",
        "src/dashboard/tabs/intelligence_regime.py",
        "src/dashboard/tabs/performance.py",
        "src/dashboard/tabs/options_system.py",
        "src/dashboard/tabs/system_ops.py",
        "launch_dashboard.sh",
        "GAP8_DASHBOARD_CONSOLIDATION_COMPLETE.md"
    ]
    
    missing = []
    for file_path in required_files:
        full_path = PROJECT_ROOT / file_path
        if not full_path.exists():
            missing.append(file_path)
            print(f"   ❌ Missing: {file_path}")
        else:
            print(f"   ✅ Found: {file_path}")
    
    if missing:
        print(f"\n⚠️  {len(missing)} files missing!")
        return False
    
    print("\n✅ All required files exist")
    return True


def check_imports():
    """Check that modules can be imported"""
    print("\n📦 Checking imports...")
    
    try:
        from src.dashboard.data_contract import DashboardDataContract, LabeledValue, DataFreshness
        print("   ✅ data_contract imports successfully")
    except Exception as e:
        print(f"   ❌ data_contract import failed: {e}")
        return False
    
    try:
        from src.dashboard import tabs
        print("   ✅ tabs module imports successfully")
    except Exception as e:
        print(f"   ❌ tabs import failed: {e}")
        return False
    
    try:
        from src.dashboard.tabs import (
            live_trading, portfolio_governor, intelligence_regime,
            performance, options_system, system_ops
        )
        print("   ✅ All tab modules import successfully")
    except Exception as e:
        print(f"   ❌ Tab imports failed: {e}")
        return False
    
    print("\n✅ All imports successful")
    return True


def check_data_contract_methods():
    """Check that data contract has all required methods"""
    print("\n🔍 Checking DashboardDataContract methods...")
    
    from src.dashboard.data_contract import DashboardDataContract
    
    contract = DashboardDataContract()
    
    required_methods = [
        # Live Trading
        'get_equity_positions',
        'get_options_positions',
        'get_intraday_pnl',
        'get_options_greeks',
        # Portfolio & Governor
        'get_capital_structure',
        'get_governor_regime',
        'get_strategy_weights',
        # Intelligence & Regime
        'get_market_regime',
        'get_sentiment_state',
        'get_alternative_data_state',
        # Performance
        'get_nav_history',
        'get_performance_metrics',
        'get_paper_fund_status',
        # System Operations
        'get_system_health',
        'get_state_reconciliation_status'
    ]
    
    missing = []
    for method_name in required_methods:
        if not hasattr(contract, method_name):
            missing.append(method_name)
            print(f"   ❌ Missing method: {method_name}")
        else:
            print(f"   ✅ Found method: {method_name}")
    
    if missing:
        print(f"\n⚠️  {len(missing)} methods missing!")
        return False
    
    print("\n✅ All required methods exist")
    return True


def check_launch_script():
    """Check that launch script is executable"""
    print("\n🚀 Checking launch script...")
    
    launch_script = PROJECT_ROOT / "launch_dashboard.sh"
    
    if not launch_script.exists():
        print("   ❌ launch_dashboard.sh not found")
        return False
    
    import os
    if os.access(launch_script, os.X_OK):
        print("   ✅ launch_dashboard.sh is executable")
    else:
        print("   ⚠️  launch_dashboard.sh is not executable (run: chmod +x launch_dashboard.sh)")
        return False
    
    return True


def test_data_contract_instantiation():
    """Test that data contract can be instantiated"""
    print("\n🧪 Testing DashboardDataContract instantiation...")
    
    try:
        from src.dashboard.data_contract import DashboardDataContract
        
        contract = DashboardDataContract()
        print("   ✅ DashboardDataContract instantiated successfully")
        
        # Test a method call (should handle missing file gracefully)
        result = contract.get_system_health()
        print(f"   ✅ get_system_health() returned: is_available={result.is_available}")
        
        if not result.is_available:
            print(f"   ℹ️  Reason: {result.unavailability_reason}")
        
        return True
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


def main():
    """Run all validation checks"""
    print("=" * 60)
    print("GAP 8 DASHBOARD VALIDATION")
    print("=" * 60)
    
    checks = [
        ("File Structure", check_files_exist),
        ("Module Imports", check_imports),
        ("Data Contract Methods", check_data_contract_methods),
        ("Launch Script", check_launch_script),
        ("Data Contract Instantiation", test_data_contract_instantiation)
    ]
    
    results = []
    for check_name, check_func in checks:
        try:
            result = check_func()
            results.append((check_name, result))
        except Exception as e:
            print(f"\n❌ {check_name} check failed with exception: {e}")
            results.append((check_name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for check_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {check_name}")
    
    print(f"\nTotal: {passed}/{total} checks passed")
    
    if passed == total:
        print("\n🎉 Gap 8 Dashboard implementation is COMPLETE and VALID!")
        print("\nNext steps:")
        print("1. Run tests: pytest tests/test_dashboard_data_contract.py")
        print("2. Launch dashboard: ./launch_dashboard.sh --dev")
        print("3. Verify all tabs render correctly")
        return 0
    else:
        print("\n⚠️  Some checks failed. Please review the output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
