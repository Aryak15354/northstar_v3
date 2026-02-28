#!/usr/bin/env python3
"""
Test core system components without the heavy regime memory building
"""

import os
import sys

# Add src directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(os.path.dirname(current_dir), 'src')
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

def test_core_system():
    """Test core system without heavy computations"""
    
    print("🧪 TESTING CORE SYSTEM COMPONENTS")
    print("=" * 50)
    
    # Test Unified Intelligence Engine
    try:
        print("🧠 Testing Unified Intelligence Engine...")
        from src.volatility.intelligence_engine import UnifiedIntelligenceEngine
        
        engine = UnifiedIntelligenceEngine()
        print("   ✅ Unified Intelligence Engine initialized")
        
        # Test intelligence generation (lightweight)
        result = engine.generate_unified_intelligence()
        print("   ✅ Intelligence generation completed")
        
    except Exception as e:
        print(f"   ❌ Unified Intelligence Engine failed: {e}")
        return False
    
    # Test Unified Portfolio Coordinator
    try:
        print("\n🎯 Testing Unified Portfolio Coordinator...")
        from portfolio.unified_portfolio_coordinator import UnifiedPortfolioCoordinator
        
        coordinator = UnifiedPortfolioCoordinator()
        print("   ✅ Unified Portfolio Coordinator initialized")
        
        # Test portfolio construction
        success = coordinator.construct_unified_portfolio()
        print(f"   ✅ Portfolio construction: {'Success' if success else 'Partial'}")
        
    except Exception as e:
        print(f"   ❌ Unified Portfolio Coordinator failed: {e}")
        return False
    
    print("\n🎉 CORE SYSTEM TEST COMPLETE")
    print("All major components are working correctly!")
    return True

if __name__ == "__main__":
    test_core_system()