#!/usr/bin/env python3
"""
Test script for Northstar V3 components with proper Python path setup
"""

import os
import sys

# Add src directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(os.path.dirname(current_dir), 'src')
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

def test_components():
    """Test all components with proper imports"""
    
    print("🧪 Testing components with fixed imports...")
    
    test_results = {}
    
    # Test Market Brain
    try:
        from intelligence.market_brain.brain_orchestrator import MarketBrainOrchestrator
        brain = MarketBrainOrchestrator()
        test_results['market_brain'] = True
        print("   ✅ Market Brain Orchestrator: OK")
    except Exception as e:
        test_results['market_brain'] = False
        print(f"   ❌ Market Brain Orchestrator: {e}")
    
    # Test Intelligence Stack
    try:
        from intelligence.intelligence_stack import IntelligenceStack
        intelligence = IntelligenceStack()
        test_results['intelligence_stack'] = True
        print("   ✅ Intelligence Stack: OK")
    except Exception as e:
        test_results['intelligence_stack'] = False
        print(f"   ❌ Intelligence Stack: {e}")
    
    # Test Capital Allocator
    try:
        from intelligence.capital_allocator import CapitalAllocator
        allocator = CapitalAllocator()
        test_results['capital_allocator'] = True
        print("   ✅ Capital Allocator: OK")
    except Exception as e:
        test_results['capital_allocator'] = False
        print(f"   ❌ Capital Allocator: {e}")
    
    # Test Portfolio Governor
    try:
        from portfolio.portfolio_governor import PortfolioGovernor
        governor = PortfolioGovernor()
        test_results['portfolio_governor'] = True
        print("   ✅ Portfolio Governor: OK")
    except Exception as e:
        test_results['portfolio_governor'] = False
        print(f"   ❌ Portfolio Governor: {e}")
    
    # Test Strategy Intelligence
    try:
        from intelligence.strategy_intelligence import StrategyIntelligence
        strategy_intel = StrategyIntelligence()
        test_results['strategy_intelligence'] = True
        print("   ✅ Strategy Intelligence: OK")
    except Exception as e:
        test_results['strategy_intelligence'] = False
        print(f"   ❌ Strategy Intelligence: {e}")
    
    # Test Unified Intelligence Engine
    try:
        from src.volatility.intelligence_engine import UnifiedIntelligenceEngine
        unified_intel = UnifiedIntelligenceEngine()
        test_results['unified_intelligence'] = True
        print("   ✅ Unified Intelligence Engine: OK")
    except Exception as e:
        test_results['unified_intelligence'] = False
        print(f"   ❌ Unified Intelligence Engine: {e}")
    
    # Test Unified Portfolio Coordinator
    try:
        from portfolio.unified_portfolio_coordinator import UnifiedPortfolioCoordinator
        unified_portfolio = UnifiedPortfolioCoordinator()
        test_results['unified_portfolio'] = True
        print("   ✅ Unified Portfolio Coordinator: OK")
    except Exception as e:
        test_results['unified_portfolio'] = False
        print(f"   ❌ Unified Portfolio Coordinator: {e}")
    
    return test_results

def main():
    """Main test execution"""
    
    print("🧪 COMPONENT TESTING WITH FIXED IMPORTS")
    print("=" * 50)
    
    test_results = test_components()
    
    total_components = len(test_results)
    working_components = sum(test_results.values())
    
    print(f"\n📊 TEST RESULTS")
    print("=" * 30)
    print(f"Working Components: {working_components}/{total_components}")
    print(f"Success Rate: {working_components/total_components:.1%}")
    
    if working_components >= 5:
        print("\n🎉 IMPORT FIXES SUCCESSFUL!")
        print("Most components are now working correctly.")
        return True
    else:
        print("\n⚠️ SOME COMPONENTS STILL FAILING")
        print("Additional fixes may be needed.")
        return False

if __name__ == "__main__":
    main()
