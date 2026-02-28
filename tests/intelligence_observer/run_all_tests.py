#!/usr/bin/env python3
"""
Intelligence Observer Test Runner

Runs all Intelligence Observer tests and provides comprehensive reporting
on the test results, coverage, and system validation.
"""

import os
import sys
import subprocess
import time
from datetime import datetime
import json

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

def run_test_suite():
    """Run the complete Intelligence Observer test suite"""
    
    print("🧠 INTELLIGENCE OBSERVER TEST SUITE")
    print("=" * 60)
    print("Running comprehensive tests for Intelligence Observer Layer")
    print("=" * 60)
    
    test_files = [
        "test_authority_firewall.py",
        "test_observer_core.py", 
        "test_question_engines.py",
        "test_output_artifacts.py",
        "test_northstar_integration.py",
        "test_comprehensive_system.py"
    ]
    
    test_results = {}
    total_start_time = time.time()
    
    for test_file in test_files:
        print(f"\n📋 Running {test_file}")
        print("-" * 40)
        
        start_time = time.time()
        
        try:
            # Run pytest for this test file
            result = subprocess.run([
                sys.executable, "-m", "pytest", 
                f"tests/intelligence_observer/{test_file}",
                "-v", "--tb=short"
            ], capture_output=True, text=True, cwd=project_root)
            
            end_time = time.time()
            duration = end_time - start_time
            
            # Parse results
            output_lines = result.stdout.split('\n')
            
            # Count passed/failed tests
            passed_count = len([line for line in output_lines if "PASSED" in line])
            failed_count = len([line for line in output_lines if "FAILED" in line])
            error_count = len([line for line in output_lines if "ERROR" in line])
            
            test_results[test_file] = {
                'passed': passed_count,
                'failed': failed_count,
                'errors': error_count,
                'duration': duration,
                'return_code': result.returncode,
                'output': result.stdout,
                'stderr': result.stderr
            }
            
            if result.returncode == 0:
                print(f"✅ {test_file}: {passed_count} passed in {duration:.2f}s")
            else:
                print(f"❌ {test_file}: {failed_count} failed, {error_count} errors in {duration:.2f}s")
                if result.stderr:
                    print(f"   Errors: {result.stderr[:200]}...")
            
        except Exception as e:
            print(f"💥 {test_file}: Exception during execution: {e}")
            test_results[test_file] = {
                'passed': 0,
                'failed': 0,
                'errors': 1,
                'duration': 0,
                'return_code': -1,
                'exception': str(e)
            }
    
    total_end_time = time.time()
    total_duration = total_end_time - total_start_time
    
    # Generate summary report
    print("\n" + "=" * 60)
    print("📊 TEST SUITE SUMMARY")
    print("=" * 60)
    
    total_passed = sum(r['passed'] for r in test_results.values())
    total_failed = sum(r['failed'] for r in test_results.values())
    total_errors = sum(r['errors'] for r in test_results.values())
    total_tests = total_passed + total_failed + total_errors
    
    print(f"Total Tests: {total_tests}")
    print(f"✅ Passed: {total_passed}")
    print(f"❌ Failed: {total_failed}")
    print(f"💥 Errors: {total_errors}")
    print(f"⏱️  Total Duration: {total_duration:.2f}s")
    
    if total_failed == 0 and total_errors == 0:
        print(f"\n🎉 ALL TESTS PASSED!")
        print(f"Intelligence Observer Layer is fully validated")
    else:
        print(f"\n⚠️  SOME TESTS FAILED")
        print(f"Review failed tests and fix issues")
    
    # Detailed results by test file
    print(f"\n📋 DETAILED RESULTS BY TEST FILE:")
    for test_file, results in test_results.items():
        status = "✅ PASS" if results['return_code'] == 0 else "❌ FAIL"
        print(f"   {test_file}: {status} ({results['passed']}P/{results['failed']}F/{results['errors']}E) - {results['duration']:.2f}s")
    
    # Test coverage analysis
    print(f"\n🔍 TEST COVERAGE ANALYSIS:")
    coverage_areas = {
        "Authority Firewall": "test_authority_firewall.py",
        "Observer Core": "test_observer_core.py",
        "Question Engines": "test_question_engines.py", 
        "Output Artifacts": "test_output_artifacts.py",
        "Northstar Integration": "test_northstar_integration.py",
        "System Integration": "test_comprehensive_system.py"
    }
    
    for area, test_file in coverage_areas.items():
        if test_file in test_results:
            result = test_results[test_file]
            if result['return_code'] == 0:
                print(f"   ✅ {area}: Fully Tested")
            else:
                print(f"   ❌ {area}: Issues Found")
        else:
            print(f"   ⚠️  {area}: Not Tested")
    
    # Critical validations
    print(f"\n🔒 CRITICAL VALIDATIONS:")
    
    critical_checks = [
        ("Authority Boundaries", test_results.get("test_authority_firewall.py", {}).get('return_code') == 0),
        ("Observer Core Functionality", test_results.get("test_observer_core.py", {}).get('return_code') == 0),
        ("Intelligence Generation", test_results.get("test_question_engines.py", {}).get('return_code') == 0),
        ("Output Sanitization", test_results.get("test_output_artifacts.py", {}).get('return_code') == 0),
        ("V3 Integration", test_results.get("test_northstar_integration.py", {}).get('return_code') == 0),
        ("System Reliability", test_results.get("test_comprehensive_system.py", {}).get('return_code') == 0)
    ]
    
    all_critical_passed = True
    for check_name, passed in critical_checks:
        status = "✅ VALIDATED" if passed else "❌ FAILED"
        print(f"   {check_name}: {status}")
        if not passed:
            all_critical_passed = False
    
    # Final verdict
    print(f"\n" + "=" * 60)
    if all_critical_passed and total_failed == 0 and total_errors == 0:
        print("🎯 INTELLIGENCE OBSERVER LAYER: PRODUCTION READY")
        print("✅ All authority boundaries maintained")
        print("✅ All components functioning correctly") 
        print("✅ Integration with V3 architecture validated")
        print("✅ System reliability confirmed")
        print("\nThe Intelligence Observer makes you wiser, not braver.")
    else:
        print("⚠️  INTELLIGENCE OBSERVER LAYER: NEEDS ATTENTION")
        print("❌ Some critical validations failed")
        print("🔧 Review and fix issues before deployment")
    
    print("=" * 60)
    
    # Save detailed results
    results_file = f"tests/intelligence_observer/test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    try:
        with open(results_file, 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'total_duration': total_duration,
                'summary': {
                    'total_tests': total_tests,
                    'passed': total_passed,
                    'failed': total_failed,
                    'errors': total_errors
                },
                'test_results': test_results,
                'critical_validations': dict(critical_checks)
            }, f, indent=2)
        print(f"📄 Detailed results saved to: {results_file}")
    except Exception as e:
        print(f"⚠️  Could not save results file: {e}")
    
    return all_critical_passed and total_failed == 0 and total_errors == 0

def run_specific_test(test_name):
    """Run a specific test file"""
    
    print(f"🧪 Running specific test: {test_name}")
    
    try:
        result = subprocess.run([
            sys.executable, "-m", "pytest",
            f"tests/intelligence_observer/{test_name}",
            "-v", "-s"
        ], cwd=project_root)
        
        return result.returncode == 0
        
    except Exception as e:
        print(f"Error running test {test_name}: {e}")
        return False

def main():
    """Main test runner function"""
    
    if len(sys.argv) > 1:
        # Run specific test
        test_name = sys.argv[1]
        if not test_name.endswith('.py'):
            test_name += '.py'
        
        success = run_specific_test(test_name)
        sys.exit(0 if success else 1)
    else:
        # Run full test suite
        success = run_test_suite()
        sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()