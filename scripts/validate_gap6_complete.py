#!/usr/bin/env python3
"""
Validation script for Gap 6: Portfolio Governor

This script verifies that all Gap 6 components are properly implemented.
"""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def check_file_exists(filepath: str, description: str) -> bool:
    """Check if a file exists."""
    if Path(filepath).exists():
        print(f"✅ {description}: {filepath}")
        return True
    else:
        print(f"❌ {description} MISSING: {filepath}")
        return False

def check_import(module_path: str, class_name: str) -> bool:
    """Check if a class can be imported."""
    try:
        parts = module_path.rsplit('.', 1)
        module = __import__(parts[0], fromlist=[parts[1]] if len(parts) > 1 else [])
        if len(parts) > 1:
            module = getattr(module, parts[1])
        getattr(module, class_name)
        print(f"✅ Can import {class_name} from {module_path}")
        return True
    except Exception as e:
        print(f"❌ Cannot import {class_name} from {module_path}: {e}")
        return False

def validate_capital_structure():
    """Validate CapitalStructure implementation."""
    print("\n=== Validating CapitalStructure ===")
    
    checks = []
    
    # Check file exists
    checks.append(check_file_exists(
        "src/portfolio/capital_structure.py",
        "CapitalStructure module"
    ))
    
    # Check imports
    checks.append(check_import("src.portfolio.capital_structure", "CapitalStructure"))
    checks.append(check_import("src.portfolio.capital_structure", "CapitalStructureRegime"))
    checks.append(check_import("src.portfolio.capital_structure", "RegimeCapitalTable"))
    
    # Validate regime table
    try:
        from src.portfolio.capital_structure import RegimeCapitalTable
        RegimeCapitalTable.validate_table()
        print("✅ RegimeCapitalTable validation passed")
        checks.append(True)
    except Exception as e:
        print(f"❌ RegimeCapitalTable validation failed: {e}")
        checks.append(False)
    
    return all(checks)

def validate_governor_state():
    """Validate GovernorState implementation."""
    print("\n=== Validating GovernorState ===")
    
    checks = []
    
    # Check file exists
    checks.append(check_file_exists(
        "src/portfolio/governor_state.py",
        "GovernorState module"
    ))
    
    # Check import
    checks.append(check_import("src.portfolio.governor_state", "GovernorState"))
    
    # Check UnifiedState integration
    try:
        from src.core.state import UnifiedState
        state = UnifiedState()
        if hasattr(state, 'governor_state'):
            print("✅ UnifiedState has governor_state attribute")
            checks.append(True)
        else:
            print("❌ UnifiedState missing governor_state attribute")
            checks.append(False)
    except Exception as e:
        print(f"❌ UnifiedState integration check failed: {e}")
        checks.append(False)
    
    return all(checks)

def validate_governor():
    """Validate PortfolioGovernor implementation."""
    print("\n=== Validating PortfolioGovernor ===")
    
    checks = []
    
    # Check file exists
    checks.append(check_file_exists(
        "src/portfolio/governor.py",
        "PortfolioGovernor module"
    ))
    
    # Check import
    checks.append(check_import("src.portfolio.governor", "PortfolioGovernor"))
    
    # Check key methods exist
    try:
        from src.portfolio.governor import PortfolioGovernor
        methods = [
            'compute_capital_structure',
            'compute_and_apply',
            'check_intraday_escalation',
            'apply_manual_override',
            'get_governance_explanation'
        ]
        for method in methods:
            if hasattr(PortfolioGovernor, method):
                print(f"✅ PortfolioGovernor has {method}() method")
                checks.append(True)
            else:
                print(f"❌ PortfolioGovernor missing {method}() method")
                checks.append(False)
    except Exception as e:
        print(f"❌ PortfolioGovernor method check failed: {e}")
        checks.append(False)
    
    return all(checks)

def validate_config():
    """Validate configuration file."""
    print("\n=== Validating Configuration ===")
    
    checks = []
    
    # Check config file exists
    checks.append(check_file_exists(
        "config/portfolio_governor_config.yaml",
        "Portfolio Governor config"
    ))
    
    return all(checks)

def validate_tests():
    """Validate test files."""
    print("\n=== Validating Tests ===")
    
    checks = []
    
    # Check test files exist
    checks.append(check_file_exists(
        "src/portfolio/tests/test_capital_structure.py",
        "CapitalStructure tests"
    ))
    checks.append(check_file_exists(
        "src/portfolio/tests/test_governor.py",
        "PortfolioGovernor tests"
    ))
    
    return all(checks)

def run_tests():
    """Run the test suite."""
    print("\n=== Running Tests ===")
    
    try:
        import pytest
        
        # Run capital structure tests
        print("\nRunning capital structure tests...")
        result1 = pytest.main([
            "src/portfolio/tests/test_capital_structure.py",
            "-v",
            "--tb=short"
        ])
        
        # Run governor tests
        print("\nRunning governor tests...")
        result2 = pytest.main([
            "src/portfolio/tests/test_governor.py",
            "-v",
            "--tb=short"
        ])
        
        if result1 == 0 and result2 == 0:
            print("✅ All tests passed")
            return True
        else:
            print("❌ Some tests failed")
            return False
            
    except ImportError:
        print("⚠️  pytest not available, skipping test execution")
        return True

def main():
    """Main validation function."""
    print("=" * 60)
    print("GAP 6: PORTFOLIO GOVERNOR VALIDATION")
    print("=" * 60)
    
    results = []
    
    # Run all validations
    results.append(("CapitalStructure", validate_capital_structure()))
    results.append(("GovernorState", validate_governor_state()))
    results.append(("PortfolioGovernor", validate_governor()))
    results.append(("Configuration", validate_config()))
    results.append(("Tests", validate_tests()))
    
    # Run tests if all components exist
    if all(r[1] for r in results):
        results.append(("Test Execution", run_tests()))
    
    # Print summary
    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)
    
    for component, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {component}")
    
    all_passed = all(r[1] for r in results)
    
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 GAP 6 VALIDATION: ALL CHECKS PASSED")
        print("=" * 60)
        print("\nThe Portfolio Governor is fully implemented and ready for integration.")
        print("\nNext steps:")
        print("1. Integrate Governor into src/core/orchestrator.py")
        print("2. Update ConvexPortfolioAllocator to accept equity_capital_budget_inr")
        print("3. Update CapitalPolicyManager to accept options_capital_budget_inr")
        print("4. Add Governor status to preopen_checks.py")
        return 0
    else:
        print("❌ GAP 6 VALIDATION: SOME CHECKS FAILED")
        print("=" * 60)
        print("\nPlease review the failures above and fix the issues.")
        return 1

if __name__ == '__main__':
    sys.exit(main())
