#!/usr/bin/env python3
"""
Final Living System Validation Script

This script performs comprehensive validation of the complete Northstar Living System
to ensure all requirements are met, the system operates correctly, and demonstrates
autonomy and resilience.

Usage:
    python scripts/test_final_living_system_validation.py [--verbose] [--quick]
"""

import os
import sys
import json
import time
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Tuple

# Add src to path for imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

class LivingSystemValidator:
    """Comprehensive validation of the living system"""
    
    def __init__(self, verbose=False, quick=False):
        self.verbose = verbose
        self.quick = quick
        self.results = {
            'validation_start': datetime.now().isoformat(),
            'tests': {},
            'requirements_validation': {},
            'system_metrics': {},
            'issues': [],
            'recommendations': []
        }
        
    def log(self, message, level="INFO"):
        """Log message with timestamp"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] [{level}] {message}"
        print(formatted_message)
        
        if self.verbose or level in ["ERROR", "WARNING"]:
            # Store in results for reporting
            if 'logs' not in self.results:
                self.results['logs'] = []
            self.results['logs'].append({
                'timestamp': timestamp,
                'level': level,
                'message': message
            })
    
    def test_core_infrastructure(self) -> bool:
        """Test core living system infrastructure"""
        self.log("Testing core infrastructure...")
        
        try:
            # Test unified state
            from core.state import UnifiedState
            state = UnifiedState()
            
            # Test basic state operations
            test_data = {'test_key': 'test_value', 'timestamp': datetime.now().isoformat()}
            state.set('test_component', test_data)
            retrieved = state.get('test_component')
            
            if retrieved != test_data:
                self.results['issues'].append("Unified state get/set operations failed")
                return False
            
            # Test market clock
            from core.clock import MarketClock
            clock = MarketClock()
            current_time = clock.get_current_time()
            
            if not current_time:
                self.results['issues'].append("Market clock not functioning")
                return False
            
            # Test event bus
            from core.events import EventBus
            event_bus = EventBus()
            
            # Test health monitor
            from core.health_monitor import HealthMonitor
            health_monitor = HealthMonitor()
            system_health = health_monitor.get_system_health()
            
            if not system_health:
                self.results['issues'].append("Health monitor not functioning")
                return False
            
            # Test memory manager
            from core.memory import MemoryManager
            memory = MemoryManager()
            
            # Test orchestrator
            from core.orchestrator import OrganOrchestrator
            orchestrator = OrganOrchestrator()
            
            self.results['tests']['core_infrastructure'] = {
                'status': 'PASSED',
                'components_tested': [
                    'UnifiedState', 'MarketClock', 'EventBus', 
                    'HealthMonitor', 'MemoryManager', 'OrganOrchestrator'
                ],
                'system_health_score': system_health.get('health_score', 0.0)
            }
            
            self.log("✅ Core infrastructure tests passed")
            return True
            
        except Exception as e:
            self.log(f"❌ Core infrastructure test failed: {e}", "ERROR")
            self.results['tests']['core_infrastructure'] = {
                'status': 'FAILED',
                'error': str(e),
                'traceback': traceback.format_exc()
            }
            return False
    
    def test_organ_system(self) -> bool:
        """Test organ system functionality"""
        self.log("Testing organ system...")
        
        try:
            from src.core.orchestrator import OrganOrchestrator
            from src.core.state import UnifiedState
            
            orchestrator = OrganOrchestrator()
            state = UnifiedState()
            
            # Get registered organs
            organs = orchestrator.get_registered_organs()
            organ_count = len(organs)
            
            if organ_count == 0:
                self.results['issues'].append("No organs registered in orchestrator")
                return False
            
            # Test organ execution
            start_time = time.time()
            cycle_result = orchestrator.run_cycle(state)
            cycle_duration = time.time() - start_time
            
            # Check organ health
            organ_health = {}
            for organ in organs:
                try:
                    health = organ.get_health_metrics()
                    organ_name = organ.__class__.__name__
                    organ_health[organ_name] = health
                except Exception as e:
                    self.log(f"Warning: Could not get health for {organ.__class__.__name__}: {e}", "WARNING")
            
            self.results['tests']['organ_system'] = {
                'status': 'PASSED',
                'organs_registered': organ_count,
                'cycle_duration': cycle_duration,
                'organ_health': organ_health,
                'cycle_result': str(cycle_result) if cycle_result else 'No result'
            }
            
            self.log(f"✅ Organ system tests passed - {organ_count} organs registered")
            return True
            
        except Exception as e:
            self.log(f"❌ Organ system test failed: {e}", "ERROR")
            self.results['tests']['organ_system'] = {
                'status': 'FAILED',
                'error': str(e),
                'traceback': traceback.format_exc()
            }
            return False
    
    def test_migration_compatibility(self) -> bool:
        """Test migration compatibility layer"""
        self.log("Testing migration compatibility...")
        
        try:
            # Check migration status
            migration_status_file = Path("data/migration/living_system_migration_status.json")
            
            if not migration_status_file.exists():
                self.results['issues'].append("Migration status file not found")
                return False
            
            with open(migration_status_file, 'r') as f:
                migration_status = json.load(f)
            
            migration_enabled = migration_status.get('migration_enabled', False)
            
            if not migration_enabled:
                self.log("Migration not enabled - testing legacy mode", "WARNING")
                self.results['tests']['migration_compatibility'] = {
                    'status': 'PASSED',
                    'migration_enabled': False,
                    'mode': 'legacy'
                }
                return True
            
            # Test compatibility layer
            try:
                from core.compatibility import get_compatibility_adapter
                adapter = get_compatibility_adapter()
                
                if not adapter:
                    self.results['issues'].append("Compatibility adapter not available")
                    return False
                
                # Test adapter functionality
                system_status = adapter.get_system_status()
                
                self.results['tests']['migration_compatibility'] = {
                    'status': 'PASSED',
                    'migration_enabled': True,
                    'compatibility_adapter': True,
                    'system_status': system_status,
                    'migration_date': migration_status.get('migration_date'),
                    'patched_components': migration_status.get('patched_components', [])
                }
                
                self.log("✅ Migration compatibility tests passed")
                return True
                
            except ImportError:
                # Compatibility layer not available - check if migration is disabled
                self.log("Compatibility layer not available - checking if properly disabled", "WARNING")
                
                # Check if compatibility files are disabled
                comp_file = Path("src/core/compatibility.py")
                disabled_comp = Path("src/core/compatibility.py.disabled")
                
                if disabled_comp.exists() and not comp_file.exists():
                    self.results['tests']['migration_compatibility'] = {
                        'status': 'PASSED',
                        'migration_enabled': False,
                        'properly_disabled': True
                    }
                    self.log("✅ Migration properly disabled")
                    return True
                else:
                    self.results['issues'].append("Migration status inconsistent with file state")
                    return False
            
        except Exception as e:
            self.log(f"❌ Migration compatibility test failed: {e}", "ERROR")
            self.results['tests']['migration_compatibility'] = {
                'status': 'FAILED',
                'error': str(e),
                'traceback': traceback.format_exc()
            }
            return False
    
    def test_system_resilience(self) -> bool:
        """Test system resilience and failure handling"""
        self.log("Testing system resilience...")
        
        try:
            from src.core.orchestrator import OrganOrchestrator
            from src.core.state import UnifiedState
            from src.core.health_monitor import HealthMonitor
            
            orchestrator = OrganOrchestrator()
            state = UnifiedState()
            health_monitor = HealthMonitor()
            
            # Test multiple cycles to check stability
            cycle_times = []
            success_count = 0
            
            test_cycles = 3 if self.quick else 5
            
            for i in range(test_cycles):
                try:
                    start_time = time.time()
                    result = orchestrator.run_cycle(state)
                    cycle_time = time.time() - start_time
                    cycle_times.append(cycle_time)
                    success_count += 1
                    
                    if self.verbose:
                        self.log(f"Cycle {i+1}: {cycle_time:.3f}s")
                        
                except Exception as e:
                    self.log(f"Cycle {i+1} failed: {e}", "WARNING")
            
            # Calculate resilience metrics
            success_rate = success_count / test_cycles
            avg_cycle_time = sum(cycle_times) / len(cycle_times) if cycle_times else 0
            
            # Test health monitoring
            system_health = health_monitor.get_system_health()
            health_score = system_health.get('health_score', 0.0) if system_health else 0.0
            
            # Test state persistence
            state.save()
            
            resilience_passed = (
                success_rate >= 0.8 and  # At least 80% success rate
                avg_cycle_time < 5.0 and  # Reasonable performance
                health_score > 0.5  # Decent health score
            )
            
            self.results['tests']['system_resilience'] = {
                'status': 'PASSED' if resilience_passed else 'FAILED',
                'success_rate': success_rate,
                'avg_cycle_time': avg_cycle_time,
                'health_score': health_score,
                'cycles_tested': test_cycles,
                'successful_cycles': success_count
            }
            
            if resilience_passed:
                self.log(f"✅ System resilience tests passed - {success_rate:.1%} success rate")
                return True
            else:
                self.log(f"❌ System resilience tests failed - {success_rate:.1%} success rate", "ERROR")
                return False
            
        except Exception as e:
            self.log(f"❌ System resilience test failed: {e}", "ERROR")
            self.results['tests']['system_resilience'] = {
                'status': 'FAILED',
                'error': str(e),
                'traceback': traceback.format_exc()
            }
            return False
    
    def test_entry_points(self) -> bool:
        """Test system entry points"""
        self.log("Testing system entry points...")
        
        try:
            # Test main entry point exists
            main_entry = Path("run.py")
            if not main_entry.exists():
                self.results['issues'].append("Main entry point run.py not found")
                return False
            
            # Test legacy entry points exist
            legacy_entry = Path("scripts/northstar_v3_unified.py")
            if not legacy_entry.exists():
                self.results['issues'].append("Legacy entry point not found")
                return False
            
            # Test key scripts exist
            key_scripts = [
                "scripts/launch_brain_window.py",
                "scripts/test_migration_compatibility.py",
                "scripts/enable_living_system_migration.py",
                "scripts/disable_living_system_migration.py"
            ]
            
            missing_scripts = []
            for script in key_scripts:
                if not Path(script).exists():
                    missing_scripts.append(script)
            
            if missing_scripts:
                self.results['issues'].extend([f"Missing script: {script}" for script in missing_scripts])
                return False
            
            self.results['tests']['entry_points'] = {
                'status': 'PASSED',
                'main_entry_point': str(main_entry),
                'legacy_entry_point': str(legacy_entry),
                'key_scripts_found': len(key_scripts) - len(missing_scripts),
                'total_key_scripts': len(key_scripts)
            }
            
            self.log("✅ Entry points tests passed")
            return True
            
        except Exception as e:
            self.log(f"❌ Entry points test failed: {e}", "ERROR")
            self.results['tests']['entry_points'] = {
                'status': 'FAILED',
                'error': str(e),
                'traceback': traceback.format_exc()
            }
            return False
    
    def validate_requirements(self) -> Dict[str, bool]:
        """Validate all living system requirements"""
        self.log("Validating requirements...")
        
        requirements_status = {}
        
        try:
            # Requirement 1: Unified Nervous System
            try:
                from src.core.state import UnifiedState
                from src.core.orchestrator import OrganOrchestrator
                from src.core.clock import MarketClock
                from src.core.memory import MemoryManager
                from src.core.events import EventBus
                
                state = UnifiedState()
                requirements_status['req_1_unified_nervous_system'] = True
                self.log("✅ Requirement 1: Unified Nervous System - PASSED")
                
            except Exception as e:
                requirements_status['req_1_unified_nervous_system'] = False
                self.log(f"❌ Requirement 1: Unified Nervous System - FAILED: {e}", "ERROR")
            
            # Requirement 2: Organ Transformation
            try:
                from src.core.orchestrator import OrganOrchestrator
                orchestrator = OrganOrchestrator()
                organs = orchestrator.get_registered_organs()
                
                # Check if organs implement standard interface
                organ_interface_valid = True
                for organ in organs:
                    if not all(hasattr(organ, method) for method in ['read_state', 'think', 'write_state']):
                        organ_interface_valid = False
                        break
                
                requirements_status['req_2_organ_transformation'] = len(organs) > 0 and organ_interface_valid
                self.log(f"✅ Requirement 2: Organ Transformation - {'PASSED' if requirements_status['req_2_organ_transformation'] else 'FAILED'}")
                
            except Exception as e:
                requirements_status['req_2_organ_transformation'] = False
                self.log(f"❌ Requirement 2: Organ Transformation - FAILED: {e}", "ERROR")
            
            # Requirement 3: Time as First-Class Citizen
            try:
                from src.core.clock import MarketClock
                clock = MarketClock()
                current_time = clock.get_current_time()
                
                requirements_status['req_3_time_first_class'] = current_time is not None
                self.log(f"✅ Requirement 3: Time as First-Class Citizen - {'PASSED' if requirements_status['req_3_time_first_class'] else 'FAILED'}")
                
            except Exception as e:
                requirements_status['req_3_time_first_class'] = False
                self.log(f"❌ Requirement 3: Time as First-Class Citizen - FAILED: {e}", "ERROR")
            
            # Requirement 4: Absolute Risk Authority
            try:
                from src.core.state import UnifiedState
                state = UnifiedState()
                
                # Test emergency lock functionality
                state.emergency_lock("Test lock")
                is_locked = state.is_locked()
                state.emergency_unlock("Test unlock")
                
                requirements_status['req_4_risk_authority'] = is_locked
                self.log(f"✅ Requirement 4: Absolute Risk Authority - {'PASSED' if requirements_status['req_4_risk_authority'] else 'FAILED'}")
                
            except Exception as e:
                requirements_status['req_4_risk_authority'] = False
                self.log(f"❌ Requirement 4: Absolute Risk Authority - FAILED: {e}", "ERROR")
            
            # Requirement 5: State Memory Integration
            try:
                from src.core.memory import MemoryManager
                memory = MemoryManager()
                
                requirements_status['req_5_memory_integration'] = True
                self.log("✅ Requirement 5: State Memory Integration - PASSED")
                
            except Exception as e:
                requirements_status['req_5_memory_integration'] = False
                self.log(f"❌ Requirement 5: State Memory Integration - FAILED: {e}", "ERROR")
            
            # Requirement 6: Brain Window Dashboard
            try:
                brain_window_exists = Path("src/dashboard/brain_window.py").exists()
                launcher_exists = Path("scripts/launch_brain_window.py").exists()
                
                requirements_status['req_6_brain_window'] = brain_window_exists and launcher_exists
                self.log(f"✅ Requirement 6: Brain Window Dashboard - {'PASSED' if requirements_status['req_6_brain_window'] else 'FAILED'}")
                
            except Exception as e:
                requirements_status['req_6_brain_window'] = False
                self.log(f"❌ Requirement 6: Brain Window Dashboard - FAILED: {e}", "ERROR")
            
            # Requirement 7: Continuous Organism Heartbeat
            try:
                heartbeat_exists = Path("src/core/heartbeat.py").exists()
                
                requirements_status['req_7_heartbeat'] = heartbeat_exists
                self.log(f"✅ Requirement 7: Continuous Organism Heartbeat - {'PASSED' if requirements_status['req_7_heartbeat'] else 'FAILED'}")
                
            except Exception as e:
                requirements_status['req_7_heartbeat'] = False
                self.log(f"❌ Requirement 7: Continuous Organism Heartbeat - FAILED: {e}", "ERROR")
            
            # Requirement 8: Zero-Rewrite Migration
            try:
                migration_status_file = Path("data/migration/living_system_migration_status.json")
                compatibility_exists = (
                    Path("src/core/compatibility.py").exists() or 
                    Path("src/core/compatibility.py.disabled").exists()
                )
                
                requirements_status['req_8_zero_rewrite'] = migration_status_file.exists() and compatibility_exists
                self.log(f"✅ Requirement 8: Zero-Rewrite Migration - {'PASSED' if requirements_status['req_8_zero_rewrite'] else 'FAILED'}")
                
            except Exception as e:
                requirements_status['req_8_zero_rewrite'] = False
                self.log(f"❌ Requirement 8: Zero-Rewrite Migration - FAILED: {e}", "ERROR")
            
            # Requirement 9: Event-Driven Architecture
            try:
                from src.core.events import EventBus
                event_bus = EventBus()
                
                requirements_status['req_9_event_driven'] = True
                self.log("✅ Requirement 9: Event-Driven Architecture - PASSED")
                
            except Exception as e:
                requirements_status['req_9_event_driven'] = False
                self.log(f"❌ Requirement 9: Event-Driven Architecture - FAILED: {e}", "ERROR")
            
            # Requirement 10: Organ Health Monitoring
            try:
                from src.core.health_monitor import HealthMonitor
                health_monitor = HealthMonitor()
                system_health = health_monitor.get_system_health()
                
                requirements_status['req_10_health_monitoring'] = system_health is not None
                self.log(f"✅ Requirement 10: Organ Health Monitoring - {'PASSED' if requirements_status['req_10_health_monitoring'] else 'FAILED'}")
                
            except Exception as e:
                requirements_status['req_10_health_monitoring'] = False
                self.log(f"❌ Requirement 10: Organ Health Monitoring - FAILED: {e}", "ERROR")
            
        except Exception as e:
            self.log(f"❌ Requirements validation failed: {e}", "ERROR")
        
        self.results['requirements_validation'] = requirements_status
        
        # Calculate overall requirements compliance
        passed_requirements = sum(1 for passed in requirements_status.values() if passed)
        total_requirements = len(requirements_status)
        compliance_rate = passed_requirements / total_requirements if total_requirements > 0 else 0
        
        self.log(f"Requirements compliance: {passed_requirements}/{total_requirements} ({compliance_rate:.1%})")
        
        return requirements_status
    
    def collect_system_metrics(self) -> Dict[str, Any]:
        """Collect comprehensive system metrics"""
        self.log("Collecting system metrics...")
        
        metrics = {}
        
        try:
            # Health metrics
            from src.core.health_monitor import HealthMonitor
            health_monitor = HealthMonitor()
            system_health = health_monitor.get_system_health()
            
            if system_health:
                metrics['health'] = system_health
            
            # Organ metrics
            from src.core.orchestrator import OrganOrchestrator
            orchestrator = OrganOrchestrator()
            organs = orchestrator.get_registered_organs()
            
            metrics['organs'] = {
                'count': len(organs),
                'names': [organ.__class__.__name__ for organ in organs]
            }
            
            # Performance metrics
            start_time = time.time()
            orchestrator.run_cycle(UnifiedState())
            cycle_time = time.time() - start_time
            
            metrics['performance'] = {
                'cycle_time': cycle_time,
                'timestamp': datetime.now().isoformat()
            }
            
            # Migration status
            migration_status_file = Path("data/migration/living_system_migration_status.json")
            if migration_status_file.exists():
                with open(migration_status_file, 'r') as f:
                    migration_status = json.load(f)
                metrics['migration'] = migration_status
            
            # File system metrics
            metrics['files'] = {
                'core_components': len(list(Path("src/core").glob("*.py"))),
                'documentation': len(list(Path("docs").glob("*.md"))),
                'scripts': len(list(Path("scripts").glob("*.py")))
            }
            
        except Exception as e:
            self.log(f"Warning: Could not collect all metrics: {e}", "WARNING")
            metrics['error'] = str(e)
        
        self.results['system_metrics'] = metrics
        return metrics
    
    def generate_recommendations(self) -> List[str]:
        """Generate recommendations based on validation results"""
        recommendations = []
        
        # Check requirements compliance
        requirements = self.results.get('requirements_validation', {})
        failed_requirements = [req for req, passed in requirements.items() if not passed]
        
        if failed_requirements:
            recommendations.append(f"Address failed requirements: {', '.join(failed_requirements)}")
        
        # Check system health
        health_score = self.results.get('system_metrics', {}).get('health', {}).get('health_score', 0)
        if health_score < 0.8:
            recommendations.append(f"Improve system health score (current: {health_score:.2f})")
        
        # Check performance
        cycle_time = self.results.get('system_metrics', {}).get('performance', {}).get('cycle_time', 0)
        if cycle_time > 1.0:
            recommendations.append(f"Optimize system performance (cycle time: {cycle_time:.2f}s)")
        
        # Check organ count
        organ_count = self.results.get('system_metrics', {}).get('organs', {}).get('count', 0)
        if organ_count < 5:
            recommendations.append(f"Consider adding more organs (current: {organ_count})")
        
        # Check test results
        failed_tests = [test for test, result in self.results.get('tests', {}).items() 
                       if result.get('status') != 'PASSED']
        
        if failed_tests:
            recommendations.append(f"Fix failed tests: {', '.join(failed_tests)}")
        
        if not recommendations:
            recommendations.append("System validation passed - no immediate recommendations")
        
        self.results['recommendations'] = recommendations
        return recommendations
    
    def run_validation(self) -> Dict[str, Any]:
        """Run complete living system validation"""
        self.log("=" * 60)
        self.log("STARTING FINAL LIVING SYSTEM VALIDATION")
        self.log("=" * 60)
        
        # Run all validation tests
        tests = [
            ("Core Infrastructure", self.test_core_infrastructure),
            ("Organ System", self.test_organ_system),
            ("Migration Compatibility", self.test_migration_compatibility),
            ("System Resilience", self.test_system_resilience),
            ("Entry Points", self.test_entry_points)
        ]
        
        passed_tests = 0
        total_tests = len(tests)
        
        for test_name, test_func in tests:
            self.log(f"\n--- {test_name} ---")
            try:
                if test_func():
                    passed_tests += 1
            except Exception as e:
                self.log(f"Test {test_name} crashed: {e}", "ERROR")
        
        # Validate requirements
        self.log("\n--- Requirements Validation ---")
        requirements_status = self.validate_requirements()
        
        # Collect system metrics
        self.log("\n--- System Metrics ---")
        system_metrics = self.collect_system_metrics()
        
        # Generate recommendations
        self.log("\n--- Recommendations ---")
        recommendations = self.generate_recommendations()
        
        # Calculate overall validation score
        test_score = passed_tests / total_tests
        requirements_score = sum(1 for passed in requirements_status.values() if passed) / len(requirements_status)
        overall_score = (test_score + requirements_score) / 2
        
        self.results.update({
            'validation_end': datetime.now().isoformat(),
            'overall_score': overall_score,
            'test_score': test_score,
            'requirements_score': requirements_score,
            'passed_tests': passed_tests,
            'total_tests': total_tests,
            'validation_status': 'PASSED' if overall_score >= 0.8 else 'FAILED'
        })
        
        # Print summary
        self.log("\n" + "=" * 60)
        self.log("VALIDATION SUMMARY")
        self.log("=" * 60)
        self.log(f"Overall Score: {overall_score:.1%}")
        self.log(f"Tests Passed: {passed_tests}/{total_tests} ({test_score:.1%})")
        self.log(f"Requirements Met: {sum(requirements_status.values())}/{len(requirements_status)} ({requirements_score:.1%})")
        self.log(f"Validation Status: {self.results['validation_status']}")
        
        if self.results['issues']:
            self.log(f"\nIssues Found: {len(self.results['issues'])}")
            for issue in self.results['issues']:
                self.log(f"  - {issue}")
        
        if recommendations:
            self.log(f"\nRecommendations:")
            for rec in recommendations:
                self.log(f"  - {rec}")
        
        # Save results
        results_file = Path("data/validation/final_living_system_validation.json")
        results_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(results_file, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)
        
        self.log(f"\nValidation results saved to: {results_file}")
        
        return self.results

def main():
    """Main validation script"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Final Living System Validation")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument("--quick", action="store_true", help="Run quick validation (fewer test cycles)")
    
    args = parser.parse_args()
    
    # Run validation
    validator = LivingSystemValidator(verbose=args.verbose, quick=args.quick)
    results = validator.run_validation()
    
    # Return appropriate exit code
    if results['validation_status'] == 'PASSED':
        print("\n🎯 Final Living System Validation: ✅ PASSED")
        return 0
    else:
        print("\n❌ Final Living System Validation: FAILED")
        return 1

if __name__ == "__main__":
    sys.exit(main())
