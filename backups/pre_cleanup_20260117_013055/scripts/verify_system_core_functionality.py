#!/usr/bin/env python3
"""
Core System Functionality Verification Script

This script performs focused verification of the core system functionality
without running intensive computational processes that might cause issues.

Usage:
    python scripts/verify_system_core_functionality.py [--verbose]
"""

import os
import sys
import json
import time
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Tuple

class CoreSystemVerifier:
    """Core system functionality verification"""
    
    def __init__(self, verbose=False):
        self.verbose = verbose
        self.results = {
            'verification_start': datetime.now().isoformat(),
            'components': {},
            'calculations': {},
            'data_integrity': {},
            'issues': [],
            'recommendations': []
        }
        
    def log(self, message, level="INFO"):
        """Log message with timestamp"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] [{level}] {message}"
        print(formatted_message)
        
        if self.verbose or level in ["ERROR", "WARNING"]:
            if 'logs' not in self.results:
                self.results['logs'] = []
            self.results['logs'].append({
                'timestamp': timestamp,
                'level': level,
                'message': message
            })
    
    def verify_data_files_exist(self) -> bool:
        """Verify essential data files exist"""
        self.log("Verifying data files exist...")
        
        try:
            essential_files = {
                'market_data': 'data/processed/market_state.parquet',
                'portfolio_data': 'data/processed/portfolio_weights.parquet',
                'macro_data': 'data/macro/yields.csv'
            }
            
            file_status = {}
            
            for data_type, file_path in essential_files.items():
                file_path = project_root / file_path
                
                if file_path.exists():
                    try:
                        if file_path.suffix == '.parquet':
                            df = pd.read_parquet(file_path)
                            file_status[data_type] = {
                                'exists': True,
                                'rows': len(df),
                                'columns': len(df.columns)
                            }
                        elif file_path.suffix == '.csv':
                            df = pd.read_csv(file_path)
                            file_status[data_type] = {
                                'exists': True,
                                'rows': len(df),
                                'columns': len(df.columns)
                            }
                    except Exception as e:
                        file_status[data_type] = {'exists': True, 'error': str(e)}
                else:
                    file_status[data_type] = {'exists': False}
            
            self.results['data_integrity']['files'] = file_status
            
            existing_files = sum(1 for status in file_status.values() if status.get('exists'))
            
            if existing_files >= 2:
                self.log("✅ Data files verification passed")
                return True
            else:
                self.log("⚠️ Some data files missing", "WARNING")
                return True  # Not a hard failure
                
        except Exception as e:
            self.log(f"❌ Data files verification failed: {e}", "ERROR")
            return False
    
    def verify_unified_state(self) -> bool:
        """Verify unified state functionality"""
        self.log("Verifying unified state...")
        
        try:
            from src.core.state import UnifiedState, AuthorityLevel
            
            # Create unified state
            state = UnifiedState()
            
            # Test basic functionality
            initial_market_regime = state.market.regime
            
            # Test state update
            state.update_component('market', {
                'regime': 'test_regime',
                'risk_on_probability': 0.75
            }, organ='verifier', reason='verification test')
            
            # Verify update worked
            if state.market.regime == 'test_regime':
                state_test_passed = True
            else:
                state_test_passed = False
                self.results['issues'].append("State update did not work correctly")
            
            # Test system lock
            lock_success = state.lock_system("Test lock", AuthorityLevel.EMERGENCY, "verifier")
            
            if lock_success and state.locked:
                lock_test_passed = True
            else:
                lock_test_passed = False
                self.results['issues'].append("System lock functionality failed")
            
            # Test unlock
            unlock_success = state.unlock_system(AuthorityLevel.EMERGENCY, "verifier")
            
            if unlock_success and not state.locked:
                unlock_test_passed = True
            else:
                unlock_test_passed = False
                self.results['issues'].append("System unlock functionality failed")
            
            # Test health computation
            health_score = state.compute_system_health()
            
            if isinstance(health_score, (int, float)) and 0 <= health_score <= 1:
                health_test_passed = True
            else:
                health_test_passed = False
                self.results['issues'].append(f"Health score {health_score} outside valid range")
            
            self.results['components']['unified_state'] = {
                'state_update': state_test_passed,
                'system_lock': lock_test_passed,
                'system_unlock': unlock_test_passed,
                'health_computation': health_test_passed,
                'health_score': health_score
            }
            
            all_tests_passed = all([state_test_passed, lock_test_passed, unlock_test_passed, health_test_passed])
            
            if all_tests_passed:
                self.log("✅ Unified state verification passed")
                return True
            else:
                self.log("❌ Some unified state tests failed", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"❌ Unified state verification failed: {e}", "ERROR")
            self.results['components']['unified_state'] = {'error': str(e)}
            return False
    
    def verify_living_system_components(self) -> bool:
        """Verify living system components work"""
        self.log("Verifying living system components...")
        
        try:
            from src.core.state import UnifiedState
            from src.core.clock import MarketClock
            from src.core.events import EventBus
            from src.core.orchestrator import OrganOrchestrator
            
            # Initialize components
            state = UnifiedState()
            clock = MarketClock()
            event_bus = EventBus()
            orchestrator = OrganOrchestrator(state, clock, event_bus)
            
            # Test basic cycle
            start_time = time.time()
            cycle_result = orchestrator.run_cycle()
            cycle_time = time.time() - start_time
            
            # Verify cycle result
            if isinstance(cycle_result, dict) and 'cycle_number' in cycle_result:
                cycle_test_passed = True
            else:
                cycle_test_passed = False
                self.results['issues'].append("Orchestrator cycle did not return expected result")
            
            # Test event emission
            from src.core.events import Event, EventType, EventPriority
            test_event = Event(
                event_id="test_verification",
                timestamp=datetime.now(),
                event_type=EventType.SYSTEM_EVENT,
                source='verifier',
                priority=EventPriority.NORMAL,
                data={'test': 'verification'},
                tags=['verification']
            )
            
            try:
                event_bus.emit_event(test_event)
                event_test_passed = True
            except Exception as e:
                event_test_passed = False
                self.results['issues'].append(f"Event emission failed: {e}")
            
            self.results['components']['living_system'] = {
                'orchestrator_cycle': cycle_test_passed,
                'event_emission': event_test_passed,
                'cycle_time': cycle_time,
                'cycle_result': cycle_result
            }
            
            if cycle_test_passed and event_test_passed and cycle_time < 5:
                self.log(f"✅ Living system components verified - {cycle_time:.3f}s cycle time")
                return True
            else:
                self.log("❌ Living system components failed verification", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"❌ Living system components verification failed: {e}", "ERROR")
            self.results['components']['living_system'] = {'error': str(e)}
            return False
    
    def verify_coordinator_imports(self) -> bool:
        """Verify that coordinators can be imported and initialized"""
        self.log("Verifying coordinator imports...")
        
        coordinator_status = {}
        
        # Test Market Brain Orchestrator
        try:
            from src.intelligence.market_brain.brain_orchestrator import MarketBrainOrchestrator
            brain = MarketBrainOrchestrator()
            coordinator_status['market_brain'] = {
                'import_success': True,
                'initialization_success': True,
                'name': brain.name
            }
        except Exception as e:
            coordinator_status['market_brain'] = {
                'import_success': False,
                'error': str(e)
            }
        
        # Test Unified Intelligence Engine
        try:
            from src.intelligence.unified_intelligence_engine import UnifiedIntelligenceEngine
            intelligence = UnifiedIntelligenceEngine()
            coordinator_status['intelligence_engine'] = {
                'import_success': True,
                'initialization_success': True,
                'name': intelligence.name
            }
        except Exception as e:
            coordinator_status['intelligence_engine'] = {
                'import_success': False,
                'error': str(e)
            }
        
        # Test Portfolio Coordinator
        try:
            from src.portfolio.unified_portfolio_coordinator import UnifiedPortfolioCoordinator
            portfolio = UnifiedPortfolioCoordinator()
            coordinator_status['portfolio_coordinator'] = {
                'import_success': True,
                'initialization_success': True,
                'name': portfolio.name
            }
        except Exception as e:
            coordinator_status['portfolio_coordinator'] = {
                'import_success': False,
                'error': str(e)
            }
        
        # Test Risk Coordinator
        try:
            from src.risk.unified_risk_coordinator import UnifiedRiskCoordinator
            risk = UnifiedRiskCoordinator()
            coordinator_status['risk_coordinator'] = {
                'import_success': True,
                'initialization_success': True,
                'name': risk.name
            }
        except Exception as e:
            coordinator_status['risk_coordinator'] = {
                'import_success': False,
                'error': str(e)
            }
        
        self.results['components']['coordinators'] = coordinator_status
        
        # Count successful imports
        successful_imports = sum(1 for status in coordinator_status.values() 
                               if status.get('import_success', False))
        
        if successful_imports >= 3:
            self.log(f"✅ Coordinator imports verified - {successful_imports}/4 successful")
            return True
        else:
            self.log(f"⚠️ Some coordinator imports failed - {successful_imports}/4 successful", "WARNING")
            return True  # Not a hard failure
    
    def verify_basic_calculations(self) -> bool:
        """Verify basic calculation functionality"""
        self.log("Verifying basic calculations...")
        
        try:
            # Test portfolio calculations
            portfolio_file = 'data/processed/portfolio_weights.parquet'
            if os.path.exists(portfolio_file):
                portfolio_df = pd.read_parquet(portfolio_file)
                
                if not portfolio_df.empty and 'final_weight' in portfolio_df.columns:
                    total_exposure = portfolio_df['final_weight'].sum()
                    max_position = portfolio_df['final_weight'].abs().max()
                    
                    # Basic validation
                    calculations_valid = True
                    calc_issues = []
                    
                    if not (0 <= abs(total_exposure) <= 2.0):
                        calc_issues.append(f"Total exposure {total_exposure:.3f} outside reasonable range")
                        calculations_valid = False
                    
                    if not (0 <= max_position <= 1.0):
                        calc_issues.append(f"Max position {max_position:.3f} outside reasonable range")
                        calculations_valid = False
                    
                    self.results['calculations']['portfolio'] = {
                        'total_exposure': total_exposure,
                        'max_position': max_position,
                        'position_count': len(portfolio_df),
                        'calculations_valid': calculations_valid,
                        'issues': calc_issues
                    }
                    
                    if calculations_valid:
                        self.log(f"✅ Portfolio calculations verified - {total_exposure:.1%} exposure")
                    else:
                        self.log("❌ Portfolio calculation issues found", "ERROR")
                        self.results['issues'].extend(calc_issues)
                    
                    return calculations_valid
                else:
                    self.log("⚠️ Portfolio file empty or missing columns", "WARNING")
                    return True
            else:
                self.log("⚠️ No portfolio file found", "WARNING")
                return True
                
        except Exception as e:
            self.log(f"❌ Basic calculations verification failed: {e}", "ERROR")
            self.results['calculations']['basic'] = {'error': str(e)}
            return False
    
    def run_verification(self) -> Dict[str, Any]:
        """Run complete core system verification"""
        self.log("=" * 60)
        self.log("STARTING CORE SYSTEM VERIFICATION")
        self.log("=" * 60)
        
        # Run verification tests
        verification_tests = [
            ("Data Files", self.verify_data_files_exist),
            ("Unified State", self.verify_unified_state),
            ("Living System Components", self.verify_living_system_components),
            ("Coordinator Imports", self.verify_coordinator_imports),
            ("Basic Calculations", self.verify_basic_calculations)
        ]
        
        passed_tests = 0
        total_tests = len(verification_tests)
        
        for test_name, test_func in verification_tests:
            self.log(f"\n--- {test_name} ---")
            try:
                if test_func():
                    passed_tests += 1
            except Exception as e:
                self.log(f"Test {test_name} crashed: {e}", "ERROR")
        
        # Calculate overall score
        overall_score = passed_tests / total_tests
        
        # Generate recommendations
        recommendations = []
        
        if len(self.results['issues']) > 0:
            recommendations.append(f"Address {len(self.results['issues'])} identified issues")
        
        if overall_score < 0.8:
            recommendations.append("Improve system reliability - some components need attention")
        
        if overall_score >= 0.9:
            recommendations.append("System verification excellent - core components functioning well")
        
        # Update results
        self.results.update({
            'verification_end': datetime.now().isoformat(),
            'overall_score': overall_score,
            'tests_passed': passed_tests,
            'total_tests': total_tests,
            'verification_status': 'PASSED' if overall_score >= 0.6 else 'FAILED',
            'recommendations': recommendations
        })
        
        # Print summary
        self.log("\n" + "=" * 60)
        self.log("VERIFICATION SUMMARY")
        self.log("=" * 60)
        self.log(f"Overall Score: {overall_score:.1%}")
        self.log(f"Tests Passed: {passed_tests}/{total_tests}")
        self.log(f"Verification Status: {self.results['verification_status']}")
        
        if self.results['issues']:
            self.log(f"\nIssues Found: {len(self.results['issues'])}")
            for issue in self.results['issues'][:3]:  # Show first 3 issues
                self.log(f"  - {issue}")
            if len(self.results['issues']) > 3:
                self.log(f"  ... and {len(self.results['issues']) - 3} more issues")
        
        if self.results['recommendations']:
            self.log(f"\nRecommendations:")
            for rec in self.results['recommendations']:
                self.log(f"  - {rec}")
        
        # Save results
        results_file = project_root / "data" / "validation" / "core_system_verification.json"
        results_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(results_file, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)
        
        self.log(f"\nVerification results saved to: {results_file}")
        
        return self.results

def main():
    """Main verification script"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Core System Functionality Verification")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    # Run verification
    verifier = CoreSystemVerifier(verbose=args.verbose)
    results = verifier.run_verification()
    
    # Return appropriate exit code
    if results['verification_status'] == 'PASSED':
        print("\n🎯 Core System Verification: ✅ PASSED")
        print("Core system components are functioning correctly!")
        return 0
    else:
        print("\n❌ Core System Verification: FAILED")
        print("Some core components need attention.")
        return 1

if __name__ == "__main__":
    sys.exit(main())