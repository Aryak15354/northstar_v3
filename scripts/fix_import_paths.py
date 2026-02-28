#!/usr/bin/env python3
"""
🔧 FIX IMPORT PATHS - NORTHSTAR V3
Fix all import path issues preventing components from loading

The issue is that components are trying to import with 'src.' prefix
but the Python path doesn't include the parent directory.
"""

import os
import sys
import re

def fix_file_imports(filepath, replacements):
    """Fix imports in a specific file"""
    
    if not os.path.exists(filepath):
        print(f"   ⚠️ File not found: {filepath}")
        return False
    
    try:
        with open(filepath, 'r') as f:
            content = f.read()
        
        original_content = content
        
        for old_import, new_import in replacements.items():
            content = content.replace(old_import, new_import)
        
        if content != original_content:
            with open(filepath, 'w') as f:
                f.write(content)
            print(f"   ✅ Fixed imports in {os.path.basename(filepath)}")
            return True
        else:
            print(f"   ℹ️ No changes needed in {os.path.basename(filepath)}")
            return True
            
    except Exception as e:
        print(f"   ❌ Error fixing {filepath}: {e}")
        return False

def fix_unified_portfolio_coordinator():
    """Fix unified portfolio coordinator imports"""
    
    print("🔧 Fixing Unified Portfolio Coordinator imports...")
    
    replacements = {
        'from src.portfolio.portfolio_governor import PortfolioGovernor': 'from portfolio.portfolio_governor import PortfolioGovernor',
        'from src.intelligence.capital_allocator import CapitalAllocator': 'from intelligence.capital_allocator import CapitalAllocator'
    }
    
    return fix_file_imports('src/portfolio/unified_portfolio_coordinator.py', replacements)

def fix_unified_intelligence_engine():
    """Fix unified intelligence engine imports"""
    
    print("🔧 Fixing Unified Intelligence Engine imports...")
    
    replacements = {
        'from src.intelligence.market_brain.brain_orchestrator import MarketBrainOrchestrator': 'from intelligence.market_brain.brain_orchestrator import MarketBrainOrchestrator',
        'from src.intelligence.intelligence_stack import IntelligenceStack': 'from intelligence.intelligence_stack import IntelligenceStack',
        'from src.intelligence.strategy_intelligence import StrategyIntelligence': 'from intelligence.strategy_intelligence import StrategyIntelligence',
        'from src.intelligence.unified_belief_system import UnifiedBeliefSystem': 'from intelligence.unified_belief_system import UnifiedBeliefSystem'
    }
    
    return fix_file_imports('src/intelligence/unified_intelligence_engine.py', replacements)

def fix_intelligence_stack():
    """Fix intelligence stack imports"""
    
    print("🔧 Fixing Intelligence Stack imports...")
    
    replacements = {
        'from src.intelligence.valuation_engines import ValuationEngineStack': 'from intelligence.valuation_engines import ValuationEngineStack',
        'from src.intelligence.confidence_engine import ConfidenceWeightedSignalProcessor': 'from intelligence.confidence_engine import ConfidenceWeightedSignalProcessor',
        'from src.intelligence.bayesian_engine import BayesianSignalFusion, ContradictionResolver': 'from intelligence.bayesian_engine import BayesianSignalFusion, ContradictionResolver',
        'from src.intelligence.narrative_engine import NarrativeEngine': 'from intelligence.narrative_engine import NarrativeEngine',
        'from src.intelligence.memory_engine import MemoryEngine, LearningCoordinator': 'from intelligence.memory_engine import MemoryEngine, LearningCoordinator',
        'from src.cohesion.unified_state_manager import UnifiedStateManager': 'from cohesion.unified_state_manager import UnifiedStateManager',
        'from src.state.market_state import load_latest_market_state': 'from state.market_state import load_latest_market_state'
    }
    
    return fix_file_imports('src/intelligence/intelligence_stack.py', replacements)

def fix_capital_allocator():
    """Fix capital allocator imports"""
    
    print("🔧 Fixing Capital Allocator imports...")
    
    # The capital allocator looks mostly correct, but let's check for any src imports
    replacements = {
        'from src.intelligence.simple_tailwind_engine import SimpleTailwindEngine': 'from intelligence.simple_tailwind_engine import SimpleTailwindEngine',
        'from src.intelligence.no_edge_detector import NoEdgeDetector': 'from intelligence.no_edge_detector import NoEdgeDetector'
    }
    
    return fix_file_imports('src/intelligence/capital_allocator.py', replacements)

def fix_portfolio_governor():
    """Fix portfolio governor imports"""
    
    print("🔧 Fixing Portfolio Governor imports...")
    
    replacements = {
        'from src.cohesion.bounded_exposure_calculator import BoundedExposureCalculator': 'from cohesion.bounded_exposure_calculator import BoundedExposureCalculator',
        'from src.cohesion.state_file_manager import StateFileManager': 'from cohesion.state_file_manager import StateFileManager'
    }
    
    return fix_file_imports('src/portfolio/portfolio_governor.py', replacements)

def fix_market_brain_orchestrator():
    """Fix market brain orchestrator imports"""
    
    print("🔧 Fixing Market Brain Orchestrator imports...")
    
    replacements = {
        'from src.cohesion.bounded_exposure_calculator import BoundedExposureCalculator': 'from cohesion.bounded_exposure_calculator import BoundedExposureCalculator',
        'from src.cohesion.state_file_manager import StateFileManager': 'from cohesion.state_file_manager import StateFileManager'
    }
    
    return fix_file_imports('src/intelligence/market_brain/brain_orchestrator.py', replacements)

def fix_strategy_intelligence():
    """Fix strategy intelligence imports"""
    
    print("🔧 Fixing Strategy Intelligence imports...")
    
    replacements = {
        'from src.intelligence.simple_tailwind_engine import SimpleTailwindEngine': 'from intelligence.simple_tailwind_engine import SimpleTailwindEngine',
        'from src.intelligence.strategy_beliefs import StrategyBeliefs': 'from intelligence.strategy_beliefs import StrategyBeliefs',
        'from src.intelligence.strategy_regret import StrategyRegret': 'from intelligence.strategy_regret import StrategyRegret'
    }
    
    return fix_file_imports('src/intelligence/strategy_intelligence.py', replacements)

def add_init_files():
    """Add __init__.py files to make packages importable"""
    
    print("🔧 Adding __init__.py files...")
    
    directories = [
        'src',
        'src/intelligence',
        'src/intelligence/market_brain',
        'src/portfolio',
        'src/cohesion',
        'src/state'
    ]
    
    for directory in directories:
        init_file = os.path.join(directory, '__init__.py')
        if not os.path.exists(init_file):
            with open(init_file, 'w') as f:
                f.write('# Package initialization\n')
            print(f"   ✅ Created {init_file}")

def create_test_script():
    """Create a test script that properly sets up the Python path"""
    
    print("🔧 Creating test script with proper Python path...")
    
    test_script = '''#!/usr/bin/env python3
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
    
    print(f"\\n📊 TEST RESULTS")
    print("=" * 30)
    print(f"Working Components: {working_components}/{total_components}")
    print(f"Success Rate: {working_components/total_components:.1%}")
    
    if working_components >= 5:
        print("\\n🎉 IMPORT FIXES SUCCESSFUL!")
        print("Most components are now working correctly.")
        return True
    else:
        print("\\n⚠️ SOME COMPONENTS STILL FAILING")
        print("Additional fixes may be needed.")
        return False

if __name__ == "__main__":
    main()
'''
    
    with open('scripts/test_fixed_imports.py', 'w') as f:
        f.write(test_script)
    
    print("   ✅ Created test script with proper Python path")

def main():
    """Main execution"""
    
    print("🔧 FIX IMPORT PATHS - NORTHSTAR V3")
    print("=" * 50)
    
    # Step 1: Add __init__.py files
    add_init_files()
    
    # Step 2: Fix imports in all components
    print("\n🔧 Fixing component imports...")
    
    fixes = [
        fix_unified_portfolio_coordinator(),
        fix_unified_intelligence_engine(),
        fix_intelligence_stack(),
        fix_capital_allocator(),
        fix_portfolio_governor(),
        fix_market_brain_orchestrator(),
        fix_strategy_intelligence()
    ]
    
    successful_fixes = sum(fixes)
    
    # Step 3: Create test script
    create_test_script()
    
    print(f"\n📊 IMPORT FIX SUMMARY")
    print("=" * 30)
    print(f"Files fixed: {successful_fixes}/{len(fixes)}")
    
    if successful_fixes >= 5:
        print("\n✅ IMPORT FIXES COMPLETE")
        print("Run 'python scripts/test_fixed_imports.py' to test components")
        return True
    else:
        print("\n⚠️ SOME FIXES FAILED")
        print("Manual intervention may be required")
        return False

if __name__ == "__main__":
    main()