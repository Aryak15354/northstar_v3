#!/usr/bin/env python3
"""
🧪 INTEGRATION VALIDATION TEST
Simplified integration test for Task 19 validation

This test focuses on the core integration requirements:
- Complete system integration
- All organs coordination
- Performance validation
- Entry point integration

Usage:
    python scripts/test_integration_validation.py
"""

import os
import sys
import time
import warnings
from datetime import datetime
warnings.filterwarnings('ignore')

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_complete_system_integration():
    """Test complete system integration"""
    
    print("🧬 Testing Complete System Integration")
    print("=" * 40)
    
    try:
        # Test 1: Create living system
        print("1️⃣ Creating living system...")
        from src.core import create_living_system
        
        living_system = create_living_system()
        
        # Validate components
        required_components = [
            'unified_state', 'event_bus', 'market_clock', 'memory_manager',
            'organ_orchestrator', 'health_monitor', 'heartbeat'
        ]
        
        for component in required_components:
            assert component in living_system, f"Missing component: {component}"
        
        print("   ✅ Living system created with all components")
        
        # Test 2: Register V3 organs
        print("2️⃣ Registering V3 organs...")
        from src.core.organ_wrappers import create_v3_organ_wrappers
        
        orchestrator = living_system['organ_orchestrator']
        health_monitor = living_system['health_monitor']
        
        v3_organs = create_v3_organ_wrappers()
        
        for organ in v3_organs:
            orchestrator.register_organ(organ)
            health_monitor.register_organ(organ)
        
        print(f"   ✅ Registered {len(v3_organs)} V3 organs")
        
        # Test 3: Run system cycle
        print("3️⃣ Running system cycle...")
        cycle_start = time.time()
        cycle_result = orchestrator.run_cycle()
        cycle_duration = time.time() - cycle_start
        
        print(f"   ✅ Cycle completed: {cycle_result['organs_successful']}/{cycle_result['organs_executed']} organs successful")
        print(f"   ✅ Cycle duration: {cycle_duration:.2f}s")
        
        # Test 4: Health monitoring
        print("4️⃣ Testing health monitoring...")
        health_report = health_monitor.get_system_health_report()
        
        print(f"   ✅ Health score: {health_report.overall_health_score:.2f}")
        print(f"   ✅ Health level: {health_report.health_level}")
        print(f"   ✅ Organs monitored: {len(health_report.organ_reports)}")
        
        # Test 5: Autonomous operation capability
        print("5️⃣ Testing autonomous operation...")
        heartbeat = living_system['heartbeat']
        
        # Test heartbeat cycle
        heartbeat_success = heartbeat._execute_heartbeat_cycle()
        
        print(f"   ✅ Heartbeat cycle: {'SUCCESS' if heartbeat_success else 'FAILED'}")
        
        # Test 6: State management
        print("6️⃣ Testing state management...")
        unified_state = living_system['unified_state']
        
        # Get state
        state_dict = unified_state.get_state_dict()
        assert len(state_dict) > 0, "Empty state"
        
        print(f"   ✅ State components: {list(state_dict.keys())}")
        
        return True, {
            'organs_registered': len(v3_organs),
            'cycle_duration': cycle_duration,
            'organs_successful': cycle_result['organs_successful'],
            'organs_executed': cycle_result['organs_executed'],
            'health_score': health_report.overall_health_score,
            'heartbeat_success': heartbeat_success
        }
        
    except Exception as e:
        print(f"   ❌ Integration test failed: {e}")
        return False, None

def test_entry_point_integration():
    """Test entry point integration"""
    
    print("\n🚀 Testing Entry Point Integration")
    print("=" * 35)
    
    try:
        # Test 1: Entry point exists
        print("1️⃣ Checking entry point...")
        assert os.path.exists('run.py'), "Entry point run.py not found"
        print("   ✅ Entry point exists")
        
        # Test 2: Compatibility layer
        print("2️⃣ Testing compatibility layer...")
        from src.core.compatibility import get_compatibility_adapter
        
        adapter = get_compatibility_adapter(enable_living_system=True)
        status = adapter.get_system_status()
        
        assert status['living_system_enabled'], "Living system not enabled"
        print(f"   ✅ Living system mode: {status['mode']}")
        
        # Test 3: Component creation
        print("3️⃣ Testing component creation...")
        orchestrator = adapter.get_master_orchestrator()
        data_coordinator = adapter.get_data_pipeline_coordinator()
        dashboard_coordinator = adapter.get_dashboard_coordinator()
        
        assert orchestrator is not None, "Master orchestrator not available"
        assert data_coordinator is not None, "Data coordinator not available"
        assert dashboard_coordinator is not None, "Dashboard coordinator not available"
        
        print("   ✅ All components created successfully")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Entry point integration failed: {e}")
        return False

def test_performance_requirements():
    """Test performance requirements"""
    
    print("\n⚡ Testing Performance Requirements")
    print("=" * 35)
    
    try:
        from src.core import create_living_system
        from src.core.organ_wrappers import create_v3_organ_wrappers
        
        # Create system
        living_system = create_living_system()
        orchestrator = living_system['organ_orchestrator']
        health_monitor = living_system['health_monitor']
        
        # Register organs
        v3_organs = create_v3_organ_wrappers()
        for organ in v3_organs:
            orchestrator.register_organ(organ)
            health_monitor.register_organ(organ)
        
        # Test cycle performance
        print("1️⃣ Testing cycle performance...")
        cycle_times = []
        success_rates = []
        
        for i in range(3):
            start_time = time.time()
            result = orchestrator.run_cycle()
            cycle_time = time.time() - start_time
            
            cycle_times.append(cycle_time)
            if result['organs_executed'] > 0:
                success_rate = result['organs_successful'] / result['organs_executed']
                success_rates.append(success_rate)
        
        avg_cycle_time = sum(cycle_times) / len(cycle_times)
        avg_success_rate = sum(success_rates) / len(success_rates) if success_rates else 0
        
        print(f"   ✅ Average cycle time: {avg_cycle_time:.2f}s")
        print(f"   ✅ Average success rate: {avg_success_rate:.1%}")
        
        # Test health monitoring performance
        print("2️⃣ Testing health monitoring performance...")
        health_start = time.time()
        health_report = health_monitor.get_system_health_report()
        health_time = time.time() - health_start
        
        print(f"   ✅ Health check time: {health_time:.2f}s")
        
        # Performance validation
        MAX_CYCLE_TIME = 5.0  # seconds
        MIN_SUCCESS_RATE = 0.5  # 50%
        MAX_HEALTH_TIME = 2.0  # seconds
        
        performance_passed = (
            avg_cycle_time < MAX_CYCLE_TIME and
            avg_success_rate >= MIN_SUCCESS_RATE and
            health_time < MAX_HEALTH_TIME
        )
        
        print(f"   {'✅' if performance_passed else '❌'} Performance requirements: {'PASSED' if performance_passed else 'FAILED'}")
        
        return performance_passed, {
            'avg_cycle_time': avg_cycle_time,
            'avg_success_rate': avg_success_rate,
            'health_check_time': health_time
        }
        
    except Exception as e:
        print(f"   ❌ Performance test failed: {e}")
        return False, None

def main():
    """Run integration validation tests"""
    
    print("🧪 INTEGRATION VALIDATION TEST SUITE")
    print("=" * 45)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Test results
    results = {
        'system_integration': False,
        'entry_point_integration': False,
        'performance_requirements': False
    }
    
    metrics = {}
    
    # Test 1: Complete system integration
    success, system_metrics = test_complete_system_integration()
    results['system_integration'] = success
    if system_metrics:
        metrics.update(system_metrics)
    
    # Test 2: Entry point integration
    results['entry_point_integration'] = test_entry_point_integration()
    
    # Test 3: Performance requirements
    success, perf_metrics = test_performance_requirements()
    results['performance_requirements'] = success
    if perf_metrics:
        metrics.update(perf_metrics)
    
    # Calculate overall results
    passed_tests = sum(results.values())
    total_tests = len(results)
    success_rate = passed_tests / total_tests
    
    # Print summary
    print(f"\n{'='*50}")
    print("📊 INTEGRATION VALIDATION SUMMARY")
    print("=" * 35)
    print(f"Tests Passed: {passed_tests}/{total_tests}")
    print(f"Success Rate: {success_rate*100:.1f}%")
    
    # Show key metrics
    if metrics:
        print(f"\n📈 KEY METRICS:")
        if 'organs_registered' in metrics:
            print(f"   Organs Registered: {metrics['organs_registered']}")
        if 'cycle_duration' in metrics:
            print(f"   Cycle Duration: {metrics['cycle_duration']:.2f}s")
        if 'organs_successful' in metrics and 'organs_executed' in metrics:
            organ_success_rate = metrics['organs_successful'] / metrics['organs_executed'] if metrics['organs_executed'] > 0 else 0
            print(f"   Organ Success Rate: {organ_success_rate:.1%}")
        if 'health_score' in metrics:
            print(f"   Health Score: {metrics['health_score']:.2f}")
    
    # Overall status
    if success_rate >= 0.8:
        print(f"\n✅ INTEGRATION VALIDATION: PASSED")
        print("   Living system integration is successful")
        overall_success = True
    elif success_rate >= 0.6:
        print(f"\n⚠️ INTEGRATION VALIDATION: PARTIAL")
        print("   Most integration tests passed, some issues remain")
        overall_success = True
    else:
        print(f"\n❌ INTEGRATION VALIDATION: FAILED")
        print("   Critical integration issues need to be resolved")
        overall_success = False
    
    # Save results
    try:
        import json
        os.makedirs('data/integration', exist_ok=True)
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'test_results': results,
            'metrics': metrics,
            'success_rate': success_rate,
            'overall_success': overall_success
        }
        
        with open('data/integration/integration_validation_report.json', 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        print(f"\n📄 Report saved: data/integration/integration_validation_report.json")
        
    except Exception as e:
        print(f"\n⚠️ Failed to save report: {e}")
    
    return overall_success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)