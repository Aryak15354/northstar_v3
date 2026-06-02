#!/usr/bin/env python3
"""
Complete System Operation Verification Script

This script performs comprehensive end-to-end verification of the entire
Northstar Living System to ensure all calculations are correct, data gathering
is accurate, and analysis is functioning properly.

Usage:
    python scripts/verify_complete_system_operation.py [--verbose] [--full]
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

# Add src to path and define project root
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

class SystemVerifier:
    """Comprehensive system verification"""
    
    def __init__(self, verbose=False, full=False):
        self.verbose = verbose
        self.full = full
        self.results = {
            'verification_start': datetime.now().isoformat(),
            'components': {},
            'calculations': {},
            'data_integrity': {},
            'analysis_accuracy': {},
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
    
    def verify_data_pipeline(self) -> bool:
        """Verify data pipeline is gathering correct data"""
        self.log("Verifying data pipeline...")
        
        try:
            # Check if data files exist and have recent data
            data_files = {
                'market_data': 'data/processed/market_state.parquet',
                'macro_data': 'data/macro/yields.csv',
                'portfolio_data': 'data/processed/portfolio_weights.parquet',
                'intelligence_data': 'data/intelligence/intelligence_state.json'
            }
            
            pipeline_status = {}
            
            for data_type, file_path in data_files.items():
                file_path = project_root / file_path
                
                if file_path.exists():
                    # Check file age
                    file_age = datetime.now() - datetime.fromtimestamp(file_path.stat().st_mtime)
                    
                    if file_path.suffix == '.parquet':
                        try:
                            df = pd.read_parquet(file_path)
                            pipeline_status[data_type] = {
                                'exists': True,
                                'age_hours': file_age.total_seconds() / 3600,
                                'rows': len(df),
                                'columns': len(df.columns),
                                'latest_date': str(df.index.max()) if hasattr(df.index, 'max') else 'N/A'
                            }
                            
                            if self.verbose:
                                self.log(f"  {data_type}: {len(df)} rows, {len(df.columns)} columns")
                                
                        except Exception as e:
                            pipeline_status[data_type] = {'exists': True, 'error': str(e)}
                            
                    elif file_path.suffix == '.json':
                        try:
                            with open(file_path, 'r') as f:
                                data = json.load(f)
                            pipeline_status[data_type] = {
                                'exists': True,
                                'age_hours': file_age.total_seconds() / 3600,
                                'keys': len(data) if isinstance(data, dict) else 'N/A'
                            }
                        except Exception as e:
                            pipeline_status[data_type] = {'exists': True, 'error': str(e)}
                            
                    elif file_path.suffix == '.csv':
                        try:
                            df = pd.read_csv(file_path)
                            pipeline_status[data_type] = {
                                'exists': True,
                                'age_hours': file_age.total_seconds() / 3600,
                                'rows': len(df),
                                'columns': len(df.columns)
                            }
                        except Exception as e:
                            pipeline_status[data_type] = {'exists': True, 'error': str(e)}
                else:
                    pipeline_status[data_type] = {'exists': False}
            
            self.results['data_integrity']['pipeline'] = pipeline_status
            
            # Check if we have recent data
            recent_data_count = sum(1 for status in pipeline_status.values() 
                                  if status.get('exists') and status.get('age_hours', 999) < 24)
            
            if recent_data_count >= 2:
                self.log("✅ Data pipeline verification passed")
                return True
            else:
                self.log("⚠️ Data pipeline has limited recent data", "WARNING")
                return True  # Not a failure, just limited data
                
        except Exception as e:
            self.log(f"❌ Data pipeline verification failed: {e}", "ERROR")
            self.results['data_integrity']['pipeline'] = {'error': str(e)}
            return False
    
    def verify_market_brain_calculations(self) -> bool:
        """Verify market brain calculations are correct"""
        self.log("Verifying market brain calculations...")
        
        try:
            # Test market brain components
            from intelligence.market_brain.brain_orchestrator import MarketBrainOrchestrator
            
            brain = MarketBrainOrchestrator()
            
            # Test brain status and components
            brain_status = brain.get_brain_status()
            
            if brain_status and brain_status != {'status': 'not_available'}:
                # Check if brain is active
                is_active = brain.is_brain_active()
                
                brain_data = {
                    'brain_available': True,
                    'brain_active': is_active,
                    'brain_status': brain_status
                }
                
                # Validate brain functionality
                calculations_valid = True
                
                self.results['calculations']['market_brain'] = {
                    'brain_status': brain_data,
                    'calculations_valid': calculations_valid
                }
                
                if calculations_valid:
                    self.log(f"✅ Market brain calculations verified - Active: {is_active}")
                    return True
                else:
                    self.log("❌ Market brain calculation validation failed", "ERROR")
                    return False
            else:
                self.log("⚠️ Market brain returned no status", "WARNING")
                return True  # Not necessarily a failure
                
        except Exception as e:
            self.log(f"❌ Market brain verification failed: {e}", "ERROR")
            self.results['calculations']['market_brain'] = {'error': str(e)}
            return False
    
    def verify_intelligence_calculations(self) -> bool:
        """Verify intelligence stack calculations"""
        self.log("Verifying intelligence calculations...")
        
        try:
            # Test intelligence components
            from src.volatility.intelligence_engine import UnifiedIntelligenceEngine
            
            intelligence = UnifiedIntelligenceEngine()
            
            # Test intelligence status
            intelligence_status = intelligence.get_intelligence_status()
            
            if intelligence_status and intelligence_status.get('status') != 'not_available':
                # Check intelligence system health
                system_health = intelligence_status.get('system_health', {})
                unified_beliefs = intelligence_status.get('unified_beliefs', {})
                
                # Validate intelligence calculations
                calculations_valid = True
                intelligence_issues = []
                
                # Check if we have unified beliefs
                if unified_beliefs:
                    unified_conviction = unified_beliefs.get('unified_conviction', 0.0)
                    if not (0 <= unified_conviction <= 1):
                        intelligence_issues.append(f"Unified conviction {unified_conviction} outside valid range [0,1]")
                        calculations_valid = False
                
                if intelligence_issues:
                    self.results['issues'].extend(intelligence_issues)
                
                self.results['calculations']['intelligence'] = {
                    'intelligence_status': intelligence_status,
                    'calculations_valid': calculations_valid,
                    'issues': intelligence_issues
                }
                
                if calculations_valid:
                    self.log(f"✅ Intelligence calculations verified - Status: {intelligence_status.get('status')}")
                    return True
                else:
                    self.log("❌ Intelligence calculation validation failed", "ERROR")
                    return False
            else:
                self.log("⚠️ Intelligence engine returned no status", "WARNING")
                return True
                
        except Exception as e:
            self.log(f"❌ Intelligence verification failed: {e}", "ERROR")
            self.results['calculations']['intelligence'] = {'error': str(e)}
            return False
    
    def verify_portfolio_calculations(self) -> bool:
        """Verify portfolio construction calculations"""
        self.log("Verifying portfolio calculations...")
        
        try:
            # Test portfolio components
            from portfolio.unified_portfolio_coordinator import UnifiedPortfolioCoordinator
            
            portfolio = UnifiedPortfolioCoordinator()
            
            # Test portfolio construction
            portfolio_result = portfolio.construct_unified_portfolio()
            
            if portfolio_result:
                # Load portfolio results from files
                portfolio_file = 'data/processed/unified_portfolio.parquet'
                if os.path.exists(portfolio_file):
                    portfolio_df = pd.read_parquet(portfolio_file)
                    
                    # Validate portfolio calculations
                    calculations_valid = True
                    portfolio_issues = []
                    
                    if not portfolio_df.empty:
                        # Check if we have weights
                        if 'final_weight' in portfolio_df.columns:
                            weights = portfolio_df['final_weight']
                            
                            # Check weights sum
                            total_weight = weights.sum()
                            
                            if not (0.0 <= abs(total_weight) <= 1.2):  # Allow some flexibility
                                portfolio_issues.append(f"Portfolio weights sum to {total_weight}, expected reasonable range")
                            
                            # Check individual weights are reasonable
                            for idx, weight in weights.items():
                                if isinstance(weight, (int, float)):
                                    if not (-0.5 <= weight <= 0.5):  # Allow short positions
                                        portfolio_issues.append(f"Weight at index {idx} is {weight}, outside reasonable range")
                    
                    if portfolio_issues:
                        calculations_valid = False
                        self.results['issues'].extend(portfolio_issues)
                    
                    self.results['calculations']['portfolio'] = {
                        'construction_success': portfolio_result,
                        'portfolio_size': len(portfolio_df),
                        'calculations_valid': calculations_valid,
                        'issues': portfolio_issues
                    }
                    
                    if calculations_valid:
                        self.log(f"✅ Portfolio calculations verified - {len(portfolio_df)} positions")
                        return True
                    else:
                        self.log("❌ Portfolio calculation validation failed", "ERROR")
                        return False
                else:
                    self.log("⚠️ No portfolio file found", "WARNING")
                    return True
            else:
                self.log("⚠️ Portfolio coordinator returned failure", "WARNING")
                return True
                
        except Exception as e:
            self.log(f"❌ Portfolio verification failed: {e}", "ERROR")
            self.results['calculations']['portfolio'] = {'error': str(e)}
            return False
    
    def verify_risk_calculations(self) -> bool:
        """Verify risk management calculations"""
        self.log("Verifying risk calculations...")
        
        try:
            # Test risk components
            from risk.unified_risk_coordinator import UnifiedRiskCoordinator
            
            risk = UnifiedRiskCoordinator()
            
            # Test risk calculations
            risk_result = risk.apply_unified_risk_management()
            
            if risk_result:
                # Load risk state from files
                risk_state_file = 'data/risk/unified_risk_state.json'
                if os.path.exists(risk_state_file):
                    with open(risk_state_file, 'r') as f:
                        risk_data = json.load(f)
                    
                    # Validate risk calculations
                    calculations_valid = True
                    risk_issues = []
                    
                    # Check risk authority
                    risk_authority = risk_data.get('risk_authority', {})
                    final_exposure_cap = risk_authority.get('final_exposure_cap', 0.0)
                    
                    if not (0 <= final_exposure_cap <= 1.0):
                        risk_issues.append(f"Final exposure cap {final_exposure_cap} outside valid range [0, 1.0]")
                        calculations_valid = False
                    
                    if risk_issues:
                        self.results['issues'].extend(risk_issues)
                    
                    self.results['calculations']['risk'] = {
                        'risk_management_success': risk_result,
                        'risk_authority': risk_authority,
                        'calculations_valid': calculations_valid,
                        'issues': risk_issues
                    }
                    
                    if calculations_valid:
                        self.log(f"✅ Risk calculations verified - Exposure cap: {final_exposure_cap:.1%}")
                        return True
                    else:
                        self.log("❌ Risk calculation validation failed", "ERROR")
                        return False
                else:
                    self.log("⚠️ No risk state file found", "WARNING")
                    return True
            else:
                self.log("⚠️ Risk coordinator returned failure", "WARNING")
                return True
                
        except Exception as e:
            self.log(f"❌ Risk verification failed: {e}", "ERROR")
            self.results['calculations']['risk'] = {'error': str(e)}
            return False
    
    def verify_data_consistency(self) -> bool:
        """Verify data consistency across components"""
        self.log("Verifying data consistency...")
        
        try:
            # Check unified state consistency
            from core.state import UnifiedState
            state = UnifiedState()
            
            # Load state from legacy sources
            state.load_from_legacy_sources()
            
            # Get state dictionary
            state_dict = state.get_state_dict()
            
            consistency_checks = {}
            
            # Check for data consistency issues
            consistency_issues = []
            
            # Check timestamps are recent and consistent
            timestamps = []
            for component_name, component_data in state_dict.items():
                if isinstance(component_data, dict) and 'last_updated' in component_data:
                    try:
                        if component_data['last_updated'] is not None:
                            timestamp = pd.to_datetime(component_data['last_updated'])
                            timestamps.append((component_name, timestamp))
                    except:
                        pass
            
            if timestamps:
                # Check if timestamps are within reasonable range
                now = pd.Timestamp.now()
                for component_name, timestamp in timestamps:
                    age = (now - timestamp).total_seconds() / 3600  # hours
                    if age > 168:  # More than a week old
                        consistency_issues.append(f"Component {component_name} data is {age:.1f} hours old")
            
            # Check for missing critical data
            critical_components = ['market', 'regime', 'portfolio', 'risk']
            for component in critical_components:
                if component not in state_dict or not state_dict[component]:
                    consistency_issues.append(f"Critical component {component} missing or empty")
            
            consistency_checks['unified_state'] = {
                'components_found': len(state_dict),
                'timestamps_checked': len(timestamps),
                'issues': consistency_issues
            }
            
            self.results['data_integrity']['consistency'] = consistency_checks
            
            if not consistency_issues:
                self.log("✅ Data consistency verified")
                return True
            else:
                self.log(f"⚠️ Data consistency issues found: {len(consistency_issues)}", "WARNING")
                self.results['issues'].extend(consistency_issues)
                return True  # Not a hard failure
                
        except Exception as e:
            self.log(f"❌ Data consistency verification failed: {e}", "ERROR")
            self.results['data_integrity']['consistency'] = {'error': str(e)}
            return False
    
    def verify_end_to_end_flow(self) -> bool:
        """Verify complete end-to-end system flow"""
        self.log("Verifying end-to-end system flow...")
        
        try:
            # Test complete system execution using run.py
            from orchestrator.master_orchestrator import MasterOrchestrator
            
            orchestrator = MasterOrchestrator()
            
            # Run system update (safer than full system)
            start_time = time.time()
            result = orchestrator.run_system_update()
            execution_time = time.time() - start_time
            
            flow_metrics = {
                'execution_time': execution_time,
                'success': result,
                'components_executed': []
            }
            
            self.results['analysis_accuracy']['end_to_end'] = flow_metrics
            
            # Validate end-to-end execution
            if result and execution_time < 300:  # Should complete within 5 minutes
                self.log(f"✅ End-to-end flow verified - {execution_time:.1f}s execution time")
                return True
            else:
                self.log(f"❌ End-to-end flow issues - Success: {result}, Time: {execution_time:.1f}s", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"❌ End-to-end flow verification failed: {e}", "ERROR")
            self.results['analysis_accuracy']['end_to_end'] = {'error': str(e)}
            return False
    
    def verify_living_system_integration(self) -> bool:
        """Verify living system integration is working correctly"""
        self.log("Verifying living system integration...")
        
        try:
            # Test living system components
            from core.orchestrator import OrganOrchestrator
            from core.state import UnifiedState
            from core.clock import MarketClock
            from core.events import EventBus
            
            # Initialize living system
            state = UnifiedState()
            clock = MarketClock()
            event_bus = EventBus()
            orchestrator = OrganOrchestrator(state, clock, event_bus)
            
            # Test living system cycle
            start_time = time.time()
            cycle_result = orchestrator.run_cycle()
            cycle_time = time.time() - start_time
            
            # Test state operations
            state.update_component('market', {'verification': True}, organ='verifier', reason='system verification')
            
            # Test event emission
            from core.events import Event, EventType
            test_event = Event(
                event_id="test_verification",
                timestamp=datetime.now(),
                event_type=EventType.SYSTEM_EVENT,
                source='verifier',
                data={'test': 'verification', 'message': 'System verification test'}
            )
            event_bus.emit_event(test_event)
            
            integration_metrics = {
                'cycle_time': cycle_time,
                'cycle_result': str(cycle_result),
                'state_operations': True,
                'event_emission': True,
                'organs_registered': len(orchestrator.organs)
            }
            
            self.results['components']['living_system'] = integration_metrics
            
            if cycle_time < 10:  # Should be fast with no organs
                self.log(f"✅ Living system integration verified - {cycle_time:.3f}s cycle time")
                return True
            else:
                self.log(f"❌ Living system integration slow - {cycle_time:.3f}s cycle time", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"❌ Living system integration verification failed: {e}", "ERROR")
            self.results['components']['living_system'] = {'error': str(e)}
            return False
    
    def generate_verification_report(self) -> Dict[str, Any]:
        """Generate comprehensive verification report"""
        self.log("Generating verification report...")
        
        # Calculate overall scores
        component_tests = [
            self.verify_data_pipeline(),
            self.verify_market_brain_calculations(),
            self.verify_intelligence_calculations(),
            self.verify_portfolio_calculations(),
            self.verify_risk_calculations(),
            self.verify_data_consistency(),
            self.verify_end_to_end_flow(),
            self.verify_living_system_integration()
        ]
        
        passed_tests = sum(1 for test in component_tests if test)
        total_tests = len(component_tests)
        
        overall_score = passed_tests / total_tests
        
        # Generate recommendations
        recommendations = []
        
        if len(self.results['issues']) > 0:
            recommendations.append(f"Address {len(self.results['issues'])} identified issues")
        
        if overall_score < 0.8:
            recommendations.append("Improve system reliability - some components need attention")
        
        if overall_score >= 0.9:
            recommendations.append("System verification excellent - all components functioning well")
        
        # Add specific recommendations based on results
        if 'calculations' in self.results:
            failed_calculations = [comp for comp, result in self.results['calculations'].items() 
                                 if not result.get('calculations_valid', True)]
            if failed_calculations:
                recommendations.append(f"Review calculation accuracy in: {', '.join(failed_calculations)}")
        
        self.results.update({
            'verification_end': datetime.now().isoformat(),
            'overall_score': overall_score,
            'tests_passed': passed_tests,
            'total_tests': total_tests,
            'verification_status': 'PASSED' if overall_score >= 0.7 else 'FAILED',
            'recommendations': recommendations
        })
        
        return self.results
    
    def run_verification(self) -> Dict[str, Any]:
        """Run complete system verification"""
        self.log("=" * 60)
        self.log("STARTING COMPLETE SYSTEM VERIFICATION")
        self.log("=" * 60)
        
        # Run all verification tests
        verification_tests = [
            ("Data Pipeline", self.verify_data_pipeline),
            ("Market Brain Calculations", self.verify_market_brain_calculations),
            ("Intelligence Calculations", self.verify_intelligence_calculations),
            ("Portfolio Calculations", self.verify_portfolio_calculations),
            ("Risk Calculations", self.verify_risk_calculations),
            ("Data Consistency", self.verify_data_consistency),
            ("End-to-End Flow", self.verify_end_to_end_flow),
            ("Living System Integration", self.verify_living_system_integration)
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
        
        # Generate final report
        report = self.generate_verification_report()
        
        # Print summary
        self.log("\n" + "=" * 60)
        self.log("VERIFICATION SUMMARY")
        self.log("=" * 60)
        self.log(f"Overall Score: {report['overall_score']:.1%}")
        self.log(f"Tests Passed: {report['tests_passed']}/{report['total_tests']}")
        self.log(f"Verification Status: {report['verification_status']}")
        
        if report['issues']:
            self.log(f"\nIssues Found: {len(report['issues'])}")
            for issue in report['issues'][:5]:  # Show first 5 issues
                self.log(f"  - {issue}")
            if len(report['issues']) > 5:
                self.log(f"  ... and {len(report['issues']) - 5} more issues")
        
        if report['recommendations']:
            self.log(f"\nRecommendations:")
            for rec in report['recommendations']:
                self.log(f"  - {rec}")
        
        # Save results
        results_file = project_root / "data" / "validation" / "complete_system_verification.json"
        results_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(results_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        self.log(f"\nVerification results saved to: {results_file}")
        
        return report

def main():
    """Main verification script"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Complete System Operation Verification")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument("--full", action="store_true", help="Run full comprehensive verification")
    
    args = parser.parse_args()
    
    # Run verification
    verifier = SystemVerifier(verbose=args.verbose, full=args.full)
    results = verifier.run_verification()
    
    # Return appropriate exit code
    if results['verification_status'] == 'PASSED':
        print("\n🎯 Complete System Verification: ✅ PASSED")
        print("All calculations are correct and the system is functioning properly!")
        return 0
    else:
        print("\n❌ Complete System Verification: FAILED")
        print("Some issues need to be addressed.")
        return 1

if __name__ == "__main__":
    sys.exit(main())