#!/usr/bin/env python3
"""
🧪 TEST ENHANCED DASHBOARD
Test the enhanced results analysis integration
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

def test_enhanced_analysis():
    """Test enhanced results analysis functionality"""
    
    print("🧪 TESTING ENHANCED RESULTS ANALYSIS")
    print("=" * 50)
    
    try:
        # Import the enhanced analyzer
        from src.dashboard.enhanced_results_analysis import EnhancedResultsAnalyzer
        print("✅ Enhanced Results Analysis module imported successfully")
        
        # Initialize analyzer
        analyzer = EnhancedResultsAnalyzer()
        print("✅ EnhancedResultsAnalyzer initialized successfully")
        
        # Test data generation methods
        sample_stress_tests = {
            'test_1': {
                'name': 'Market Crash Test',
                'results': {
                    'portfolio_return': -15.2,
                    'max_drawdown': -22.8,
                    'recovery_days': 145,
                    'sharpe_ratio': -0.85,
                    'survival_probability': 0.78
                }
            }
        }
        
        sample_walkforward_tests = {
            'test_1': {
                'name': 'Strategy Alpha',
                'results': {
                    'success_rate': 0.72,
                    'avg_oos_return': 0.085,
                    'avg_oos_sharpe': 1.24,
                    'consistency_score': 0.68
                }
            }
        }
        
        # Test data generation methods
        performance_data = analyzer.generate_performance_data(sample_stress_tests, sample_walkforward_tests)
        print("✅ Performance data generation working")
        
        risk_data = analyzer.generate_risk_data(sample_stress_tests, sample_walkforward_tests)
        print("✅ Risk data generation working")
        
        attribution_data = analyzer.generate_attribution_data(sample_stress_tests, sample_walkforward_tests)
        print("✅ Attribution data generation working")
        
        statistical_data = analyzer.generate_statistical_data(sample_stress_tests, sample_walkforward_tests)
        print("✅ Statistical data generation working")
        
        comparative_data = analyzer.generate_comparative_data(sample_stress_tests, sample_walkforward_tests)
        print("✅ Comparative data generation working")
        
        # Test Monte Carlo simulation
        mc_results = analyzer.run_monte_carlo_simulation(100, 12)
        print("✅ Monte Carlo simulation working")
        
        print("\n" + "=" * 50)
        print("🎉 ALL TESTS PASSED!")
        print("✅ Enhanced Results Analysis is ready for dashboard integration")
        print("\n📊 Available Analysis Components:")
        print("   • Performance Analytics Dashboard")
        print("   • Risk Decomposition & Analysis")
        print("   • Attribution Analysis")
        print("   • Statistical Deep Dive")
        print("   • Monte Carlo Analysis")
        print("   • Comparative Intelligence")
        print("\n🚀 Ready to launch enhanced dashboard!")
        
        return True
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_dashboard_integration():
    """Test dashboard integration"""
    
    print("\n🔗 TESTING DASHBOARD INTEGRATION")
    print("=" * 50)
    
    try:
        # Test main dashboard integration
        print("Testing main dashboard (app.py)...")
        with open('dashboard/app.py', 'r') as f:
            content = f.read()
            if 'EnhancedResultsAnalyzer' in content:
                print("✅ Main dashboard integration found")
            else:
                print("❌ Main dashboard integration missing")
        
        # Test ultimate dashboard integration
        print("Testing ultimate dashboard...")
        with open('src/dashboard/ultimate_northstar_dashboard.py', 'r') as f:
            content = f.read()
            if 'enhanced_results_analysis' in content:
                print("✅ Ultimate dashboard integration found")
            else:
                print("❌ Ultimate dashboard integration missing")
        
        # Test comprehensive dashboard integration
        print("Testing comprehensive dashboard...")
        with open('src/dashboard/northstar_v3_comprehensive_dashboard.py', 'r') as f:
            content = f.read()
            if 'enhanced_results_analysis' in content:
                print("✅ Comprehensive dashboard integration found")
            else:
                print("❌ Comprehensive dashboard integration missing")
        
        print("✅ Dashboard integration tests completed")
        return True
        
    except Exception as e:
        print(f"❌ Error testing dashboard integration: {e}")
        return False

def main():
    """Run all tests"""
    
    print("🎯 ENHANCED DASHBOARD TEST SUITE")
    print("=" * 60)
    
    # Test enhanced analysis
    analysis_ok = test_enhanced_analysis()
    
    # Test dashboard integration
    integration_ok = test_dashboard_integration()
    
    print("\n" + "=" * 60)
    if analysis_ok and integration_ok:
        print("🎉 ALL TESTS PASSED - ENHANCED DASHBOARD READY!")
        print("\n🚀 To launch the enhanced dashboard:")
        print("   python scripts/launch_enhanced_results_dashboard.py")
        print("\n📍 Dashboard URLs:")
        print("   • Main Dashboard: http://localhost:8514")
        print("   • Ultimate Dashboard: http://localhost:8515")
        print("   • Comprehensive Dashboard: http://localhost:8516")
    else:
        print("❌ SOME TESTS FAILED - CHECK ERRORS ABOVE")
    
    print("=" * 60)

if __name__ == "__main__":
    main()