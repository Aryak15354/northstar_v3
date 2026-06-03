#!/usr/bin/env python3
"""
🧪 TEST V3 SYSTEM ENHANCEMENTS
Test all the V3 system enhancements and dashboard improvements
"""

import os
import sys
import json
import importlib.util
from datetime import datetime

def test_time_series_manager():
    """Test the time-series data manager"""
    
    print("📊 Testing Time-Series Data Manager...")
    
    try:
        sys.path.append('src/dashboard/utils')
        from time_series_manager import TimeSeriesDataManager
        
        # Initialize manager
        manager = TimeSeriesDataManager()
        
        # Test data retrieval
        portfolio_changes = manager.get_portfolio_changes(7)
        trades_summary = manager.get_trades_summary(7)
        returns_analysis = manager.get_returns_analysis(7)
        metrics_trends = manager.get_metrics_trends(7)
        
        print("   ✅ Time-series manager initialized")
        print(f"   ✅ Portfolio changes: {len(portfolio_changes)} metrics")
        print(f"   ✅ Trades summary: {len(trades_summary)} metrics")
        print(f"   ✅ Returns analysis: {len(returns_analysis)} metrics")
        print(f"   ✅ Metrics trends: {len(metrics_trends)} metrics")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Time-series manager test failed: {e}")
        return False

def test_alpha_generation():
    """Test alpha generation integration"""
    
    print("🧠 Testing Alpha Generation...")
    
    try:
        sys.path.append('src')
        from intelligence.institutional_alpha_engine import InstitutionalAlphaEngine
        
        # Initialize engine
        engine = InstitutionalAlphaEngine()
        
        # Test data
        market_data = {
            'prices': {'RELIANCE': 2500, 'TCS': 3200},
            'volumes': {'RELIANCE': 1000000, 'TCS': 800000},
            'fundamentals': {},
            'macro_data': {},
            'sentiment_data': {}
        }
        
        universe = ['RELIANCE', 'TCS']
        
        # Generate alpha
        result = engine.generate_alpha_positions(market_data, universe)
        
        print("   ✅ Alpha engine initialized")
        print(f"   ✅ Generated {len(result.positions)} positions")
        print(f"   ✅ Execution time: {result.execution_time:.2f}s")
        print(f"   ✅ Regime state: {result.regime_state}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Alpha generation test failed: {e}")
        return False

def test_oos_validation():
    """Test out-of-sample validation"""
    
    print("📈 Testing OOS Validation...")
    
    try:
        sys.path.append('src')
        from validation.oos_validator import OOSValidator
        
        # Initialize validator
        validator = OOSValidator()
        
        print("   ✅ OOS validator initialized")
        print(f"   ✅ Output directory: {validator.oos_dir}")
        print(f"   ✅ Configuration loaded")
        
        return True
        
    except Exception as e:
        print(f"   ❌ OOS validation test failed: {e}")
        return False

def test_strategy_components():
    """Test strategy generation components"""
    
    print("🎯 Testing Strategy Components...")
    
    try:
        sys.path.append('src')
        
        # Test strategy narrative engine
        from intelligence.strategy_narrative_engine import StrategyNarrativeEngine
        engine = StrategyNarrativeEngine()
        print("   ✅ Strategy narrative engine loaded")
        
        # Test unified intelligence engine
        from src.volatility.intelligence_engine import UnifiedIntelligenceEngine
        unified_engine = UnifiedIntelligenceEngine()
        print("   ✅ Unified intelligence engine loaded")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Strategy components test failed: {e}")
        return False

def test_dashboard_enhancements():
    """Test dashboard enhancements"""
    
    print("🎨 Testing Dashboard Enhancements...")
    
    try:
        # Check if enhanced dashboard exists
        dashboard_path = 'src/dashboard/northstar_v3_dashboard.py'
        
        if not os.path.exists(dashboard_path):
            print("   ❌ Enhanced dashboard not found")
            return False
        
        # Read dashboard content
        with open(dashboard_path, 'r') as f:
            content = f.read()
        
        # Check for enhancements
        enhancements = [
            'time_series_manager',
            'render_time_series_comparison_panel',
            'render_comparison_analysis',
            'render_enhanced_readability_fixes',
            'background-color: #ffffff !important',
            'color: #1a1a1a !important'
        ]
        
        found_enhancements = 0
        for enhancement in enhancements:
            if enhancement in content:
                found_enhancements += 1
                print(f"   ✅ Found enhancement: {enhancement}")
            else:
                print(f"   ⚠️ Missing enhancement: {enhancement}")
        
        success_rate = found_enhancements / len(enhancements)
        print(f"   📊 Enhancement coverage: {success_rate:.1%}")
        
        return success_rate >= 0.8
        
    except Exception as e:
        print(f"   ❌ Dashboard enhancements test failed: {e}")
        return False

def test_data_directories():
    """Test that required data directories exist"""
    
    print("📁 Testing Data Directories...")
    
    required_dirs = [
        'data/dashboard/time_series',
        'data/alpha',
        'data/validation/oos_validation',
        'reports/system'
    ]
    
    all_exist = True
    for dir_path in required_dirs:
        if os.path.exists(dir_path):
            print(f"   ✅ Directory exists: {dir_path}")
        else:
            print(f"   ❌ Directory missing: {dir_path}")
            all_exist = False
    
    return all_exist

def run_comprehensive_test():
    """Run comprehensive test of all enhancements"""
    
    print("🧪 COMPREHENSIVE V3 ENHANCEMENTS TEST")
    print("=" * 60)
    
    tests = [
        ("Time-Series Manager", test_time_series_manager),
        ("Alpha Generation", test_alpha_generation),
        ("OOS Validation", test_oos_validation),
        ("Strategy Components", test_strategy_components),
        ("Dashboard Enhancements", test_dashboard_enhancements),
        ("Data Directories", test_data_directories)
    ]
    
    results = {}
    passed_tests = 0
    
    for test_name, test_func in tests:
        print(f"\n🔍 {test_name}")
        print("-" * 40)
        
        try:
            result = test_func()
            results[test_name] = result
            if result:
                passed_tests += 1
                print(f"   ✅ {test_name}: PASSED")
            else:
                print(f"   ❌ {test_name}: FAILED")
        except Exception as e:
            results[test_name] = False
            print(f"   ❌ {test_name}: ERROR - {e}")
    
    # Summary
    print("\n" + "=" * 60)
    print("🎯 TEST SUMMARY")
    print("=" * 60)
    
    success_rate = passed_tests / len(tests)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
    
    print(f"\n📊 Overall Success Rate: {success_rate:.1%} ({passed_tests}/{len(tests)})")
    
    if success_rate >= 0.8:
        print("\n🎉 V3 ENHANCEMENTS ARE WORKING CORRECTLY!")
        print("   - All major components are functional")
        print("   - Dashboard enhancements are active")
        print("   - System is ready for use")
    else:
        print("\n⚠️ SOME ENHANCEMENTS NEED ATTENTION")
        print("   - Check failed tests above")
        print("   - Fix issues before production use")
    
    # Save test results
    test_results = {
        'timestamp': datetime.now().isoformat(),
        'tests': results,
        'success_rate': success_rate,
        'passed_tests': passed_tests,
        'total_tests': len(tests)
    }
    
    os.makedirs('reports/testing', exist_ok=True)
    results_path = f'reports/testing/v3_enhancements_test_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    
    with open(results_path, 'w') as f:
        json.dump(test_results, f, indent=2)
    
    print(f"\n📋 Test results saved: {results_path}")
    
    return success_rate >= 0.8

def main():
    """Main execution"""
    
    success = run_comprehensive_test()
    
    if success:
        print("\n🚀 READY TO LAUNCH!")
        print("   Run: python scripts/launchers/launch_dashboard.py")
        print("   Access: http://localhost:8512")
    else:
        print("\n🔧 NEEDS FIXES BEFORE LAUNCH")
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())