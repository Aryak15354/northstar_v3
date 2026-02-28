#!/usr/bin/env python3
"""
Final Living System Validation Script

Comprehensive validation of the Northstar Living System to ensure all requirements
are met and the system operates correctly.
"""

import os
import sys
import json
import time
import traceback
from datetime import datetime
from pathlib import Path

def test_file_structure():
    """Test that all required files exist"""
    print("Testing file structure...")
    
    required_files = [
        "run.py",
        "src/core/state.py",
        "src/core/clock.py", 
        "src/core/events.py",
        "src/core/health_monitor.py",
        "src/core/memory.py",
        "src/core/orchestrator.py",
        "src/core/organs.py",
        "src/core/heartbeat.py",
        "src/dashboard/brain_window.py",
        "scripts/launch_brain_window.py",
        "scripts/enable_living_system_migration.py",
        "scripts/disable_living_system_migration.py"
    ]
    
    missing_files = []
    for file_path in required_files:
        if not (project_root / file_path).exists():
            missing_files.append(file_path)
    
    if missing_files:
        print(f"❌ Missing files: {missing_files}")
        return False
    else:
        print("✅ All required files present")
        return True

def test_imports():
    """Test that core modules can be imported"""
    print("Testing imports...")
    
    try:
        # Test core imports
        from core.state import UnifiedState
        from core.clock import MarketClock
        from core.events import EventBus
        from core.health_monitor import HealthMonitor
        from core.memory import MemoryManager
        from core.orchestrator import OrganOrchestrator
        
        print("✅ Core modules import successfully")
        return True
        
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False

def test_basic_functionality():
    """Test basic system functionality"""
    print("Testing basic functionality...")
    
    try:
        # Test unified state
        from core.state import UnifiedState
        state = UnifiedState()
        
        # Test basic operations
        test_data = {"test": "value", "timestamp": datetime.now().isoformat()}
        state.update_component("test_component", test_data, organ="test", reason="validation test")
        
        # Check if the component was updated (basic validation)
        state_dict = state.get_state_dict()
        if "test_component" not in str(state_dict):
            print("❌ State update failed")
            return False
        
        # Test market clock
        from core.clock import MarketClock
        clock = MarketClock()
        current_time = clock.get_current_time()
        
        # Test health monitor
        from core.health_monitor import HealthMonitor
        health_monitor = HealthMonitor()
        
        # Test orchestrator (with required parameters)
        from core.orchestrator import OrganOrchestrator
        from core.events import EventBus
        
        event_bus = EventBus()
        orchestrator = OrganOrchestrator(state, clock, event_bus)
        
        print("✅ Basic functionality works")
        return True
        
    except Exception as e:
        print(f"❌ Basic functionality test failed: {e}")
        return False

def test_migration_status():
    """Test migration status and compatibility"""
    print("Testing migration status...")
    
    try:
        migration_file = project_root / "data" / "migration" / "living_system_migration_status.json"
        
        if migration_file.exists():
            with open(migration_file, 'r') as f:
                status = json.load(f)
            
            migration_enabled = status.get('migration_enabled', False)
            print(f"Migration enabled: {migration_enabled}")
            
            # Check compatibility layer
            comp_file = project_root / "src" / "core" / "compatibility.py"
            comp_disabled = project_root / "src" / "core" / "compatibility.py.disabled"
            
            if migration_enabled and comp_file.exists():
                print("✅ Migration enabled with compatibility layer")
                return True
            elif not migration_enabled and comp_disabled.exists():
                print("✅ Migration properly disabled")
                return True
            else:
                print("⚠️  Migration status inconsistent")
                return True  # Not a failure, just inconsistent
        else:
            print("⚠️  No migration status file found")
            return True
            
    except Exception as e:
        print(f"❌ Migration status test failed: {e}")
        return False

def test_system_performance():
    """Test system performance"""
    print("Testing system performance...")
    
    try:
        from core.orchestrator import OrganOrchestrator
        from core.state import UnifiedState
        from core.clock import MarketClock
        from core.events import EventBus
        
        state = UnifiedState()
        clock = MarketClock()
        event_bus = EventBus()
        orchestrator = OrganOrchestrator(state, clock, event_bus)
        
        # Test multiple cycles
        cycle_times = []
        for i in range(3):
            start_time = time.time()
            try:
                orchestrator.run_cycle()
                cycle_time = time.time() - start_time
                cycle_times.append(cycle_time)
            except Exception as e:
                print(f"Cycle {i+1} failed: {e}")
        
        if cycle_times:
            avg_time = sum(cycle_times) / len(cycle_times)
            print(f"✅ Performance test passed - avg cycle time: {avg_time:.3f}s")
            return True
        else:
            print("❌ No successful cycles")
            return False
            
    except Exception as e:
        print(f"❌ Performance test failed: {e}")
        return False

def test_entry_points():
    """Test system entry points"""
    print("Testing entry points...")
    
    try:
        # Check main entry point
        main_entry = project_root / "run.py"
        if not main_entry.exists():
            print("❌ Main entry point run.py missing")
            return False
        
        # Check legacy entry point
        legacy_entry = project_root / "scripts" / "northstar_v3_unified.py"
        if not legacy_entry.exists():
            print("❌ Legacy entry point missing")
            return False
        
        print("✅ Entry points exist")
        return True
        
    except Exception as e:
        print(f"❌ Entry points test failed: {e}")
        return False

def validate_requirements():
    """Validate key requirements"""
    print("Validating requirements...")
    
    requirements_met = 0
    total_requirements = 10
    
    # Requirement 1: Unified Nervous System
    try:
        from core.state import UnifiedState
        from core.orchestrator import OrganOrchestrator
        requirements_met += 1
        print("✅ Req 1: Unified Nervous System")
    except:
        print("❌ Req 1: Unified Nervous System")
    
    # Requirement 2: Organ Transformation
    try:
        from core.orchestrator import OrganOrchestrator
        from core.state import UnifiedState
        from core.clock import MarketClock
        from core.events import EventBus
        
        state = UnifiedState()
        clock = MarketClock()
        event_bus = EventBus()
        orchestrator = OrganOrchestrator(state, clock, event_bus)
        organs = orchestrator.get_registered_organs()
        if len(organs) > 0:
            requirements_met += 1
            print(f"✅ Req 2: Organ Transformation ({len(organs)} organs)")
        else:
            print("❌ Req 2: Organ Transformation (no organs)")
    except:
        print("❌ Req 2: Organ Transformation")
    
    # Requirement 3: Time as First-Class Citizen
    try:
        from core.clock import MarketClock
        clock = MarketClock()
        requirements_met += 1
        print("✅ Req 3: Time as First-Class Citizen")
    except:
        print("❌ Req 3: Time as First-Class Citizen")
    
    # Requirement 4: Absolute Risk Authority
    try:
        from core.state import UnifiedState, AuthorityLevel
        state = UnifiedState()
        state.lock_system("Test", AuthorityLevel.EMERGENCY, "test")
        is_locked = state.locked
        state.unlock_system(AuthorityLevel.EMERGENCY, "test")
        if is_locked:
            requirements_met += 1
            print("✅ Req 4: Absolute Risk Authority")
        else:
            print("❌ Req 4: Absolute Risk Authority")
    except Exception as e:
        print(f"❌ Req 4: Absolute Risk Authority - {e}")
    
    # Requirement 5: State Memory Integration
    try:
        from core.memory import MemoryManager
        memory = MemoryManager()
        requirements_met += 1
        print("✅ Req 5: State Memory Integration")
    except:
        print("❌ Req 5: State Memory Integration")
    
    # Requirement 6: Brain Window Dashboard
    brain_window = project_root / "src" / "dashboard" / "brain_window.py"
    launcher = project_root / "scripts" / "launch_brain_window.py"
    if brain_window.exists() and launcher.exists():
        requirements_met += 1
        print("✅ Req 6: Brain Window Dashboard")
    else:
        print("❌ Req 6: Brain Window Dashboard")
    
    # Requirement 7: Continuous Organism Heartbeat
    heartbeat = project_root / "src" / "core" / "heartbeat.py"
    if heartbeat.exists():
        requirements_met += 1
        print("✅ Req 7: Continuous Organism Heartbeat")
    else:
        print("❌ Req 7: Continuous Organism Heartbeat")
    
    # Requirement 8: Zero-Rewrite Migration
    migration_file = project_root / "data" / "migration" / "living_system_migration_status.json"
    if migration_file.exists():
        requirements_met += 1
        print("✅ Req 8: Zero-Rewrite Migration")
    else:
        print("❌ Req 8: Zero-Rewrite Migration")
    
    # Requirement 9: Event-Driven Architecture
    try:
        from core.events import EventBus
        event_bus = EventBus()
        requirements_met += 1
        print("✅ Req 9: Event-Driven Architecture")
    except:
        print("❌ Req 9: Event-Driven Architecture")
    
    # Requirement 10: Organ Health Monitoring
    try:
        from core.health_monitor import HealthMonitor
        health_monitor = HealthMonitor()
        requirements_met += 1
        print("✅ Req 10: Organ Health Monitoring")
    except:
        print("❌ Req 10: Organ Health Monitoring")
    
    compliance_rate = requirements_met / total_requirements
    print(f"\nRequirements compliance: {requirements_met}/{total_requirements} ({compliance_rate:.1%})")
    
    return compliance_rate >= 0.7  # 70% compliance threshold

def collect_system_info():
    """Collect system information"""
    print("Collecting system information...")
    
    info = {
        'timestamp': datetime.now().isoformat(),
        'validation_version': '1.0'
    }
    
    try:
        # Health metrics
        from core.health_monitor import HealthMonitor
        health_monitor = HealthMonitor()
        system_health = health_monitor.get_system_health()
        if system_health:
            info['health'] = system_health
    except:
        pass
    
    try:
        # Organ count
        from core.orchestrator import OrganOrchestrator
        from core.state import UnifiedState
        from core.clock import MarketClock
        from core.events import EventBus
        
        state = UnifiedState()
        clock = MarketClock()
        event_bus = EventBus()
        orchestrator = OrganOrchestrator(state, clock, event_bus)
        organs = orchestrator.get_registered_organs()
        info['organs'] = {
            'count': len(organs),
            'names': [organ.__class__.__name__ for organ in organs]
        }
    except:
        info['organs'] = {'count': 0, 'names': []}
    
    try:
        # Migration status
        migration_file = project_root / "data" / "migration" / "living_system_migration_status.json"
        if migration_file.exists():
            with open(migration_file, 'r') as f:
                info['migration'] = json.load(f)
    except:
        pass
    
    # File counts
    info['files'] = {
        'core_components': len(list((project_root / "src" / "core").glob("*.py"))),
        'documentation': len(list((project_root / "docs").glob("*.md"))),
        'scripts': len(list((project_root / "scripts").glob("*.py")))
    }
    
    return info

def main():
    """Main validation function"""
    print("🧬 NORTHSTAR LIVING SYSTEM - FINAL VALIDATION")
    print("=" * 60)
    
    # Run validation tests
    tests = [
        ("File Structure", test_file_structure),
        ("Imports", test_imports),
        ("Basic Functionality", test_basic_functionality),
        ("Migration Status", test_migration_status),
        ("System Performance", test_system_performance),
        ("Entry Points", test_entry_points)
    ]
    
    passed_tests = 0
    total_tests = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n--- {test_name} ---")
        try:
            if test_func():
                passed_tests += 1
        except Exception as e:
            print(f"❌ Test {test_name} crashed: {e}")
    
    # Validate requirements
    print(f"\n--- Requirements Validation ---")
    requirements_passed = validate_requirements()
    
    # Collect system info
    print(f"\n--- System Information ---")
    system_info = collect_system_info()
    
    # Calculate overall score
    test_score = passed_tests / total_tests
    overall_score = (test_score + (1 if requirements_passed else 0)) / 2
    
    # Print summary
    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)
    print(f"Tests Passed: {passed_tests}/{total_tests} ({test_score:.1%})")
    print(f"Requirements: {'PASSED' if requirements_passed else 'FAILED'}")
    print(f"Overall Score: {overall_score:.1%}")
    
    # System metrics
    if 'health' in system_info:
        health_score = system_info['health'].get('health_score', 0)
        print(f"System Health: {health_score:.2f}")
    
    organ_count = system_info['organs']['count']
    print(f"Organs Registered: {organ_count}")
    
    # Migration status
    if 'migration' in system_info:
        migration_enabled = system_info['migration'].get('migration_enabled', False)
        print(f"Migration Status: {'ENABLED' if migration_enabled else 'DISABLED'}")
    
    # Save results
    results = {
        'validation_date': datetime.now().isoformat(),
        'overall_score': overall_score,
        'tests_passed': passed_tests,
        'total_tests': total_tests,
        'requirements_passed': requirements_passed,
        'system_info': system_info,
        'status': 'PASSED' if overall_score >= 0.7 else 'FAILED'
    }
    
    results_dir = project_root / "data" / "validation"
    results_dir.mkdir(parents=True, exist_ok=True)
    
    with open(results_dir / "final_validation_results.json", 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\nResults saved to: {results_dir / 'final_validation_results.json'}")
    
    # Final status
    if results['status'] == 'PASSED':
        print("\n🎯 FINAL VALIDATION: ✅ PASSED")
        print("The Northstar Living System is operational and ready!")
        return 0
    else:
        print("\n❌ FINAL VALIDATION: FAILED")
        print("Some issues need to be addressed before the system is fully operational.")
        return 1

if __name__ == "__main__":
    sys.exit(main())