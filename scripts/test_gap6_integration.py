#!/usr/bin/env python3
"""
Test Gap 6 Integration - Verify Governor Affects Allocations

Tests that Portfolio Governor decisions actually affect capital allocation.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datetime import datetime
from src.core.state import UnifiedState
from src.portfolio.governor import PortfolioGovernor
from src.portfolio.convex_allocator import ConvexPortfolioAllocator


def test_crash_scenario():
    """Test that Governor reduces equity in crash"""
    print("=" * 80)
    print("CRASH SCENARIO TEST - Governor Integration")
    print("=" * 80)
    
    # Setup crash conditions
    state = UnifiedState()
    state.pnl_state.current_nav_inr = 10_000_000  # ₹10M NAV
    state.pnl_state.current_drawdown_pct = -12.0  # 12% drawdown
    state.market.regime = 'CRISIS'
    # Note: VIX is not a direct attribute, Governor uses market stress and regime
    
    # Step 1: Governor computes capital structure
    print("\n1. Governor Computing Capital Structure...")
    governor = PortfolioGovernor(config={'starting_capital_inr': 10_000_000})
    capital_structure = governor.compute_capital_structure(state)
    
    print(f"   Regime: {capital_structure.capital_structure_regime}")
    print(f"   Equity: {capital_structure.equity_fraction*100:.1f}% (₹{capital_structure.equity_budget_inr:,.0f})")
    print(f"   Options: {capital_structure.options_fraction*100:.1f}% (₹{capital_structure.options_budget_inr:,.0f})")
    print(f"   Cash: {capital_structure.cash_fraction*100:.1f}% (₹{capital_structure.cash_reserve_inr:,.0f})")
    
    # Verify Governor reduced equity
    if capital_structure.equity_fraction >= 0.70:
        print(f"   ✗ FAIL: Governor did not reduce equity (still {capital_structure.equity_fraction*100:.1f}%)")
        return False
    
    print(f"   ✓ PASS: Governor reduced equity to {capital_structure.equity_fraction*100:.1f}%")
    
    # Step 2: Test allocator respects budget
    print("\n2. Testing Allocator with Capital Budget...")
    allocator = ConvexPortfolioAllocator()
    
    # Mock allocation inputs
    strategy_ids = ['momentum', 'value', 'quality']
    expected_edges = {'momentum': 0.15, 'value': 0.12, 'quality': 0.10}
    covariance = {
        'momentum': {'momentum': 0.04, 'value': 0.02, 'quality': 0.01},
        'value': {'momentum': 0.02, 'value': 0.03, 'quality': 0.015},
        'quality': {'momentum': 0.01, 'value': 0.015, 'quality': 0.025},
    }
    capacity_caps = {'momentum': 0.4, 'value': 0.4, 'quality': 0.4}
    
    # Test WITHOUT budget (baseline)
    print("\n   a) Baseline allocation (no budget constraint):")
    result_no_budget = allocator.optimize(
        strategy_ids=strategy_ids,
        expected_edges=expected_edges,
        covariance=covariance,
        capacity_caps=capacity_caps,
        leverage_limit=1.0,
    )
    
    total_no_budget = sum(result_no_budget.weights.values())
    print(f"      Total allocation: {total_no_budget:.2%}")
    
    # Test WITH budget (Governor constraint)
    print("\n   b) With Governor capital budget:")
    result_with_budget = allocator.optimize(
        strategy_ids=strategy_ids,
        expected_edges=expected_edges,
        covariance=covariance,
        capacity_caps=capacity_caps,
        leverage_limit=1.0,
        equity_capital_budget_inr=capital_structure.equity_budget_inr,
        total_nav_inr=state.pnl_state.current_nav_inr,
    )
    
    total_with_budget = sum(result_with_budget.weights.values())
    print(f"      Total allocation: {total_with_budget:.2%}")
    print(f"      Expected max: {capital_structure.equity_fraction:.2%}")
    
    # Step 3: Verify allocation respects budget
    print("\n3. Verification...")
    
    # Check that budget reduced allocation
    if total_with_budget >= total_no_budget - 0.01:
        print(f"   ✗ FAIL: Budget did not reduce allocation")
        print(f"      Without budget: {total_no_budget:.2%}")
        print(f"      With budget: {total_with_budget:.2%}")
        return False
    
    # Check that allocation respects budget limit
    budget_limit = capital_structure.equity_fraction
    if total_with_budget > budget_limit + 0.02:  # 2% tolerance
        print(f"   ✗ FAIL: Allocation exceeds capital budget")
        print(f"      Allocated: {total_with_budget:.2%}")
        print(f"      Budget limit: {budget_limit:.2%}")
        return False
    
    print(f"   ✓ PASS: Allocation respects capital budget")
    print(f"   ✓ Without budget: {total_no_budget:.2%}")
    print(f"   ✓ With budget: {total_with_budget:.2%}")
    print(f"   ✓ Reduction: {(total_no_budget - total_with_budget)*100:.1f}%")
    
    return True


def test_normal_scenario():
    """Test that Governor allows full deployment in normal conditions"""
    print("\n" + "=" * 80)
    print("NORMAL SCENARIO TEST - Governor Integration")
    print("=" * 80)
    
    # Setup normal conditions
    state = UnifiedState()
    state.pnl_state.current_nav_inr = 10_000_000
    state.pnl_state.current_drawdown_pct = -2.0  # Small drawdown
    state.market.regime = 'NORMAL'
    state.market.market_stress = 0.1  # Low stress
    
    # Governor computes capital structure
    print("\n1. Governor Computing Capital Structure...")
    governor = PortfolioGovernor(config={'starting_capital_inr': 10_000_000})
    capital_structure = governor.compute_capital_structure(state)
    
    print(f"   Regime: {capital_structure.capital_structure_regime}")
    print(f"   Equity: {capital_structure.equity_fraction*100:.1f}%")
    
    # Verify Governor allows high equity allocation
    if capital_structure.equity_fraction < 0.70:
        print(f"   ✗ FAIL: Governor too conservative in normal conditions")
        return False
    
    print(f"   ✓ PASS: Governor allows {capital_structure.equity_fraction*100:.1f}% equity in normal conditions")
    
    return True


def main():
    """Run all integration tests"""
    print("=" * 80)
    print("GAP 6 INTEGRATION TESTS")
    print("=" * 80)
    
    results = []
    
    # Test 1: Crash scenario
    try:
        results.append(("Crash Scenario", test_crash_scenario()))
    except Exception as e:
        print(f"\n✗ Crash scenario test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Crash Scenario", False))
    
    # Test 2: Normal scenario
    try:
        results.append(("Normal Scenario", test_normal_scenario()))
    except Exception as e:
        print(f"\n✗ Normal scenario test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Normal Scenario", False))
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\n{passed}/{total} tests passed")
    
    if passed == total:
        print("\n✅ Gap 6 integration is WORKING")
        print("   Governor decisions affect allocations")
        print("   Capital budgets are respected")
        return 0
    else:
        print(f"\n✗ {total - passed} integration tests failed")
        print("   Governor is still disconnected from allocations")
        return 1


if __name__ == "__main__":
    sys.exit(main())
