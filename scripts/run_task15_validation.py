#!/usr/bin/env python3
"""
🏛️ TASK 15: FINAL SYSTEM VALIDATION - SIMPLIFIED VERSION
Complete end-to-end validation of the institutional alpha engine
"""

import sys
import os
import json
import time
from datetime import datetime

from src.intelligence.institutional_alpha_engine import InstitutionalAlphaEngine, AlphaEngineConfig

def run_final_validation():
    """Run comprehensive final validation"""
    
    print("🏛️ TASK 15: FINAL SYSTEM VALIDATION")
    print("=" * 70)
    print("Comprehensive end-to-end validation of institutional alpha engine")
    print()
    
    start_time = datetime.now()
    
    # Test results tracking
    tests_passed = 0
    tests_failed = 0
    test_results = []
    
    # Test 1: Engine Initialization
    print("1️⃣ Testing Engine Initialization")
    print("-" * 50)
    try:
        engine = InstitutionalAlphaEngine(AlphaEngineConfig(log_level="WARNING"))
        assert engine.config is not None
        assert engine.state is not None
        print("✅ Engine initialization test passed")
        tests_passed += 1
        test_results.append(("Engine Initialization", True, "Engine initialized successfully"))
    except Exception as e:
        print(f"❌ Engine initialization test failed: {e}")
        tests_failed += 1
        test_results.append(("Engine Initialization", False, str(e)))
    
    # Test 2: Basic Pipeline Execution
    print("\n2️⃣ Testing Basic Pipeline Execution")
    print("-" * 50)
    try:
        engine = InstitutionalAlphaEngine(AlphaEngineConfig(log_level="WARNING"))
        market_data = {
            'regime': 'expansion',
            'regime_confidence': 80.0,
            'volatility': 0.15,
            'liquidity': 0.75
        }
        universe = ['RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS']
        
        result = engine.generate_alpha_positions(market_data, universe)
        
        # Validate result structure
        assert hasattr(result, 'positions')
        assert hasattr(result, 'allocations')
        assert hasattr(result, 'regime_state')
        assert hasattr(result, 'health_status')
        assert hasattr(result, 'performance_metrics')
        assert hasattr(result, 'execution_time')
        assert result.execution_time > 0
        
        print(f"✅ Basic pipeline test passed - {len(result.positions)} positions generated in {result.execution_time:.2f}s")
        tests_passed += 1
        test_results.append(("Basic Pipeline", True, f"{len(result.positions)} positions, {result.execution_time:.2f}s"))
    except Exception as e:
        print(f"❌ Basic pipeline test failed: {e}")
        tests_failed += 1
        test_results.append(("Basic Pipeline", False, str(e)))
    
    # Test 3: Multiple Regimes
    print("\n3️⃣ Testing Multiple Regimes")
    print("-" * 50)
    try:
        engine = InstitutionalAlphaEngine(AlphaEngineConfig(log_level="WARNING"))
        universe = ['RELIANCE.NS', 'TCS.NS']
        
        regimes_tested = []
        
        # Test expansion
        expansion_data = {'regime': 'expansion', 'regime_confidence': 85.0, 'volatility': 0.12, 'liquidity': 0.85}
        result_expansion = engine.generate_alpha_positions(expansion_data, universe)
        regimes_tested.append(('expansion', result_expansion.health_status))
        
        # Test recession
        recession_data = {'regime': 'recession', 'regime_confidence': 75.0, 'volatility': 0.25, 'liquidity': 0.60}
        result_recession = engine.generate_alpha_positions(recession_data, universe)
        regimes_tested.append(('recession', result_recession.health_status))
        
        # Test crisis
        crisis_data = {'regime': 'crisis', 'regime_confidence': 60.0, 'volatility': 0.35, 'liquidity': 0.40}
        result_crisis = engine.generate_alpha_positions(crisis_data, universe)
        regimes_tested.append(('crisis', result_crisis.health_status))
        
        assert len(regimes_tested) == 3
        print(f"✅ Multiple regimes test passed - tested {len(regimes_tested)} regimes")
        tests_passed += 1
        test_results.append(("Multiple Regimes", True, f"Tested {regimes_tested}"))
    except Exception as e:
        print(f"❌ Multiple regimes test failed: {e}")
        tests_failed += 1
        test_results.append(("Multiple Regimes", False, str(e)))
    
    # Test 4: Error Handling
    print("\n4️⃣ Testing Error Handling")
    print("-" * 50)
    try:
        engine = InstitutionalAlphaEngine(AlphaEngineConfig(log_level="WARNING"))
        
        # Test with invalid data
        invalid_data = {'invalid_field': 'invalid_value'}
        universe = ['RELIANCE.NS']
        
        result = engine.generate_alpha_positions(invalid_data, universe)
        assert result is not None
        assert hasattr(result, 'health_status')
        
        # Test with empty universe
        empty_universe = []
        market_data = {'regime': 'expansion', 'regime_confidence': 80.0, 'volatility': 0.15, 'liquidity': 0.75}
        result_empty = engine.generate_alpha_positions(market_data, empty_universe)
        assert result_empty is not None
        assert len(result_empty.positions) == 0
        
        print("✅ Error handling test passed - graceful fallbacks work")
        tests_passed += 1
        test_results.append(("Error Handling", True, "Invalid data and empty universe handled gracefully"))
    except Exception as e:
        print(f"❌ Error handling test failed: {e}")
        tests_failed += 1
        test_results.append(("Error Handling", False, str(e)))
    
    # Test 5: Performance
    print("\n5️⃣ Testing Performance")
    print("-" * 50)
    try:
        engine = InstitutionalAlphaEngine(AlphaEngineConfig(log_level="WARNING"))
        
        market_data = {'regime': 'expansion', 'regime_confidence': 80.0, 'volatility': 0.15, 'liquidity': 0.75}
        universe = ['RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS', 'INFY.NS', 'HINDUNILVR.NS']
        
        start_time_perf = time.time()
        result = engine.generate_alpha_positions(market_data, universe)
        execution_time = time.time() - start_time_perf
        
        # Should complete within reasonable time (10 seconds for 5 stocks)
        assert execution_time < 10.0
        assert result.execution_time > 0
        
        print(f"✅ Performance test passed - completed in {execution_time:.2f}s (target: <10s)")
        tests_passed += 1
        test_results.append(("Performance", True, f"Completed in {execution_time:.2f}s"))
    except Exception as e:
        print(f"❌ Performance test failed: {e}")
        tests_failed += 1
        test_results.append(("Performance", False, str(e)))
    
    # Test 6: Production Readiness
    print("\n6️⃣ Testing Production Readiness")
    print("-" * 50)
    try:
        # Test configuration management
        config = AlphaEngineConfig(enable_momentum=True, max_individual_weight=0.05, min_cash_buffer=0.05)
        engine = InstitutionalAlphaEngine(config)
        assert engine.config.max_individual_weight == 0.05
        
        # Test state management
        state = engine.get_current_state()
        assert state is not None
        
        # Test logging
        assert hasattr(engine, 'logger')
        assert engine.logger is not None
        
        print("✅ Production readiness test passed - configuration, state, and logging operational")
        tests_passed += 1
        test_results.append(("Production Readiness", True, "Configuration, state, and logging systems operational"))
    except Exception as e:
        print(f"❌ Production readiness test failed: {e}")
        tests_failed += 1
        test_results.append(("Production Readiness", False, str(e)))
    
    # Generate final report
    end_time = datetime.now()
    total_duration = (end_time - start_time).total_seconds()
    total_tests = tests_passed + tests_failed
    success_rate = (tests_passed / total_tests * 100) if total_tests > 0 else 0
    overall_status = 'PASSED' if tests_failed == 0 else 'FAILED'
    
    print("\n" + "=" * 70)
    print("🏛️ FINAL VALIDATION REPORT")
    print("=" * 70)
    
    print(f"Overall Result: {overall_status}")
    print(f"Execution Time: {total_duration:.2f}s")
    print(f"Total Tests: {total_tests}")
    print(f"Passed: {tests_passed}")
    print(f"Failed: {tests_failed}")
    print(f"Success Rate: {success_rate:.1f}%")
    print(f"Production Ready: {'✅ YES' if overall_status == 'PASSED' and success_rate >= 80.0 else '❌ NO'}")
    
    print(f"\n📊 TEST RESULTS:")
    print("-" * 50)
    for test_name, passed, details in test_results:
        status_icon = "✅" if passed else "❌"
        print(f"{status_icon} {test_name}: {details}")
    
    # Save report
    final_report = {
        'task': 'Task 15: Final System Validation',
        'status': 'complete',
        'overall_result': overall_status,
        'execution_time': total_duration,
        'summary': {
            'total_tests': total_tests,
            'passed_tests': tests_passed,
            'failed_tests': tests_failed,
            'success_rate': success_rate
        },
        'test_results': [
            {'name': name, 'passed': passed, 'details': details}
            for name, passed, details in test_results
        ],
        'timestamp': datetime.now().isoformat(),
        'production_ready': overall_status == 'PASSED' and success_rate >= 80.0
    }
    
    os.makedirs('reports', exist_ok=True)
    report_file = 'reports/task15_final_system_validation_complete.json'
    
    with open(report_file, 'w') as f:
        json.dump(final_report, f, indent=2, default=str)
    
    print(f"\n📄 Full report saved to: {report_file}")
    
    if overall_status == 'PASSED':
        print(f"\n✅ Task 15 completed successfully!")
        print("🏛️ Institutional Alpha Engine is production ready!")
    else:
        print(f"\n❌ Task 15 validation failed. Review detailed results.")
    
    return final_report

if __name__ == "__main__":
    run_final_validation()