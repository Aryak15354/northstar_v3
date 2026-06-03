#!/usr/bin/env python3
"""
Fix Gap 6 Integration - Wire Governor into Live System

Critical fixes:
1. Integrate Governor into orchestrator
2. Update ConvexPortfolioAllocator to accept capital budget
3. Update CapitalPolicyManager for options budget
4. Add Governor status to preopen_checks.py
5. Wire compute_and_apply() into the critical path
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def main():
    print("=" * 80)
    print("GAP 6 INTEGRATION FIX - WIRING GOVERNOR INTO LIVE SYSTEM")
    print("=" * 80)
    
    print("\n⚠️  CRITICAL INTEGRATION GAPS IDENTIFIED:")
    print("   1. Governor never called by orchestrator")
    print("   2. ConvexPortfolioAllocator doesn't accept equity_capital_budget_inr")
    print("   3. CapitalPolicyManager doesn't accept options_capital_budget_inr")
    print("   4. preopen_checks.py doesn't log Governor status")
    print("   5. Capital structure decisions have ZERO effect on allocations")
    
    print("\n" + "=" * 80)
    print("IMPLEMENTATION PLAN")
    print("=" * 80)
    
    print("\n1. Update ConvexPortfolioAllocator")
    print("   - Add equity_capital_budget_inr parameter to optimize()")
    print("   - Scale leverage_limit by (budget / total_nav)")
    print("   - Ensure allocations respect capital budget")
    
    print("\n2. Update CapitalPolicyManager")
    print("   - Add options_capital_budget_inr parameter")
    print("   - Scale options deployment by budget")
    print("   - Respect Governor's options allocation")
    
    print("\n3. Integrate Governor into Orchestrator")
    print("   - Call Governor.compute_and_apply() BEFORE allocation")
    print("   - Pass capital structure to allocators")
    print("   - Log Governor decisions")
    
    print("\n4. Update preopen_checks.py")
    print("   - Load Governor status")
    print("   - Log capital structure for the day")
    print("   - Alert if DEFENSIVE mode active")
    
    print("\n5. Create Integration Test")
    print("   - Simulate crash scenario")
    print("   - Verify Governor reduces equity allocation")
    print("   - Confirm allocator respects budget")
    
    print("\n" + "=" * 80)
    print("CRITICAL WIRING POINTS")
    print("=" * 80)
    
    print("\nBEFORE (Broken):")
    print("   Orchestrator → ConvexAllocator → 90% equity deployment")
    print("   Governor computes DEFENSIVE → IGNORED")
    
    print("\nAFTER (Fixed):")
    print("   Orchestrator → Governor.compute_and_apply()")
    print("   Governor → CapitalStructure(equity=40%, options=20%, cash=40%)")
    print("   Orchestrator → ConvexAllocator(equity_budget=₹4M)")
    print("   ConvexAllocator → Respects ₹4M limit")
    
    print("\n" + "=" * 80)
    print("FILES TO MODIFY")
    print("=" * 80)
    
    files_to_modify = [
        ("src/portfolio/convex_allocator.py", "Add equity_capital_budget_inr parameter"),
        ("src/options/capital_policy.py", "Add options_capital_budget_inr parameter"),
        ("src/core/orchestrator.py", "Call Governor before allocation"),
        ("scripts/preopen_checks.py", "Log Governor status"),
        ("src/portfolio/governor.py", "Ensure compute_and_apply() is called"),
    ]
    
    for file_path, change in files_to_modify:
        status = "✓" if Path(file_path).exists() else "✗"
        print(f"   {status} {file_path}")
        print(f"      → {change}")
    
    print("\n" + "=" * 80)
    print("NEXT STEPS")
    print("=" * 80)
    
    print("\n1. Review this plan")
    print("2. Implement each integration point")
    print("3. Test with crash scenario")
    print("4. Verify Governor decisions affect allocations")
    print("5. Deploy to production")
    
    print("\n⚠️  WITHOUT THESE FIXES:")
    print("   - Governor is DEAD CODE")
    print("   - Capital structure decisions are IGNORED")
    print("   - System deploys 90% equity even in crashes")
    print("   - All 18 tests pass but system behavior is WRONG")
    
    print("\n✅ WITH THESE FIXES:")
    print("   - Governor controls capital allocation")
    print("   - DEFENSIVE mode reduces equity exposure")
    print("   - Operators see capital structure at preopen")
    print("   - System behavior matches design")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
