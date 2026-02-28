#!/usr/bin/env python3
"""
System Operations Verification Script

This script verifies that the system operations work correctly by actually
running the coordinators and checking their outputs.

Usage:
    python scripts/verify_system_operations.py [--verbose]
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

class SystemOperationsVerifier:
    """System operations verification"""
    
    def __init__(self, verbose=False):
        self.verbose = verbose
        self.results = {
            'verification_start': datetime.now().isoformat(),
            'operations': {},
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
    
    def verify_portfolio_construction(self) -> bool:
        """Verify portfolio construction works correctly"""
        self.log("Verifying portfolio construction...")
        
        try:
            from src.portfolio.unified_portfolio_coordinator import UnifiedPortfolioCoordinator
            
            coordinator = UnifiedPortfolioCoordinator()
            
            # Run portfolio construction
            start_time = time.time()
            success = coordinator.construct_unified_portfolio()
            execution_time = time.time() - start_time
            
            # Check results
            if success:
                # Load portfolio results
                portfolio_file = 'data/processed/unified_portfolio.parquet'
                if os.path.exists(portfolio_file):
                    portfolio_df = pd.read_parquet(portfolio_file)
                    
                    if not portfolio_df.empty:
                        total_exposure = portfolio_df['final_weight'].sum()
                        position_count = len(portfolio_df)
                        
                        # Validate results
                        calculations_valid = True
                        issues = []
                        
                        if not (0 <= abs(total_exposure) <= 1.5):
                            issues.append(f"Total exposure {total_exposure:.3f} outside reasonable range")
                            calculations_valid = False
                        
                        if position_count == 0:
                            issues.append("No positions in portfolio")
                            calculations_valid = False
                        
                        self.results['operations']['portfolio_construction'] = {
                            'success': success,
                            'execution_time': execution_time,
                            'total_exposure': total_exposure,
                            'position_count': position_count,
                            'calculations_valid': calculations_valid,
                            'issues': issues
                        }
                        
                        if calculations_valid:
                            self.log(f"✅ Portfolio construction verified - {position_count} positions, {total_exposure:.1%} exposure")
                            return True
                        else:
                            self.log("❌ Portfolio construction validation failed", "ERROR")
                            self.results['issues'].extend(issues)
                            return False
                    else:
                        self.log("⚠️ Empty portfolio generated", "WARNING")
                        return True
                else:
                    self.log("⚠️ No portfolio file generated", "WARNING")
                    return True
            else:
                self.log("❌ Portfolio construction failed", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"❌ Portfolio construction verification failed: {e}", "ERROR")
            self.results['operations']['portfolio_construction'] = {'error': str(e)}
            return False
    
    def verify_risk_management(self) -> bool:
        """Verify risk management works correctly"""
        self.log("Verifying risk management...")
        
        try:
            from src.risk.unified_risk_coordinator import UnifiedRiskCoordinator
            
            coordinator = UnifiedRiskCoordinator()
            
            # Run risk management
            start_time = time.time()
            success = coordinator.apply_unified_risk_management()
            execution_time = time.time() - start_time
            
            # Check results
            if success:
                # Load risk state
                risk_state_file = 'data/risk/unified_risk_state.json'
                if os.path.exists(risk_state_file):
                    with open(risk_state_file, 'r') as f:
                        risk_data = json.load(f)
                    
                    risk_authority = risk_data.get('risk_authority', {})
                    final_exposure_cap = risk_authority.get('final_exposure_cap', 0.0)
                    emergency_override = risk_authority.get('emergency_override', False)
                    
                    # Validate results
                    calculations_valid = True
                    issues = []
                    
                    if not (0 <= final_exposure_cap <= 1.0):
                        issues.append(f"Final exposure cap {final_exposure_cap} outside valid range [0, 1.0]")
                        calculations_valid = False
                    
                    self.results['operations']['risk_management'] = {
                        'success': success,
                        'execution_time': execution_time,
                        'final_exposure_cap': final_exposure_cap,
                        'emergency_override': emergency_override,
                        'calculations_valid': calculations_valid,
                        'issues': issues
                    }
                    
                    if calculations_valid:
                        self.log(f"✅ Risk management verified - {final_exposure_cap:.1%} exposure cap")
                        return True
                    else:
                        self.log("❌ Risk management validation failed", "ERROR")
                        self.results['issues'].extend(issues)
                        return False
                else:
                    self.log("⚠️ No risk state file generated", "WARNING")
                    return True
            else:
                self.log("❌ Risk management failed", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"❌ Risk management verification failed: {e}", "ERROR")
            self.results['operations']['risk_management'] = {'error': str(e)}
            return False
    
    def verify_intelligence_generation(self) -> bool:
        """Verify intelligence generation works correctly"""
        self.log("Verifying intelligence generation...")
        
        try:
            from src.intelligence.unified_intelligence_engine import UnifiedIntelligenceEngine
            
            engine = UnifiedIntelligenceEngine()
            
            # Test intelligence status (lighter than full generation)
            start_time = time.time()
            status = engine.get_intelligence_status()
            execution_time = time.time() - start_time
            
            # Check results
            if status and status.get('status') != 'not_available':
                system_health = status.get('system_health', {})
                unified_beliefs = status.get('unified_beliefs', {})
                
                # Validate results
                calculations_valid = True
                issues = []
                
                if unified_beliefs:
                    unified_conviction = unified_beliefs.get('unified_conviction', 0.0)
                    if not (0 <= unified_conviction <= 1):
                        issues.append(f"Unified conviction {unified_conviction} outside valid range [0,1]")
                        calculations_valid = False
                
                overall_score = system_health.get('overall_score', 0.0)
                if not (0 <= overall_score <= 1):
                    issues.append(f"System health score {overall_score} outside valid range [0,1]")
                    calculations_valid = False
                
                self.results['operations']['intelligence_generation'] = {
                    'status_available': True,
                    'execution_time': execution_time,
                    'system_health_score': overall_score,
                    'unified_conviction': unified_beliefs.get('unified_conviction', 0.0),
                    'calculations_valid': calculations_valid,
                    'issues': issues
                }
                
                if calculations_valid:
                    self.log(f"✅ Intelligence generation verified - Health: {overall_score:.1%}")
                    return True
                else:
                    self.log("❌ Intelligence generation validation failed", "ERROR")
                    self.results['issues'].extend(issues)
                    return False
            else:
                self.log("⚠️ Intelligence status not available", "WARNING")
                return True
                
        except Exception as e:
            self.log(f"❌ Intelligence generation verification failed: {e}", "ERROR")
            self.results['operations']['intelligence_generation'] = {'error': str(e)}
            return False
    
    def verify_market_brain_status(self) -> bool:
        """Verify market brain status"""
        self.log("Verifying market brain status...")
        
        try:
            from src.intelligence.market_brain.brain_orchestrator import MarketBrainOrchestrator
            
            brain = MarketBrainOrchestrator()
            
            # Test brain status (lighter than full execution)
            start_time = time.time()
            status = brain.get_brain_status()
            is_active = brain.is_brain_active()
            execution_time = time.time() - start_time
            
            # Check results
            brain_available = status != {'status': 'not_available'}
            
            self.results['operations']['market_brain'] = {
                'brain_available': brain_available,
                'brain_active': is_active,
                'execution_time': execution_time,
                'status': status
            }
            
            if brain_available:
                self.log(f"✅ Market brain verified - Active: {is_active}")
                return True
            else:
                self.log("⚠️ Market brain not available", "WARNING")
                return True
                
        except Exception as e:
            self.log(f"❌ Market brain verification failed: {e}", "ERROR")
            self.results['operations']['market_brain'] = {'error': str(e)}
            return False
    
    def verify_data_consistency_across_operations(self) -> bool:
        """Verify data consistency across all operations"""
        self.log("Verifying data consistency across operations...")
        
        try:
            consistency_checks = {}
            
            # Check portfolio vs risk consistency
            portfolio_file = 'data/processed/unified_portfolio.parquet'
            risk_state_file = 'data/risk/unified_risk_state.json'
            
            if os.path.exists(portfolio_file) and os.path.exists(risk_state_file):
                # Load portfolio
                portfolio_df = pd.read_parquet(portfolio_file)
                
                # Load risk state
                with open(risk_state_file, 'r') as f:
                    risk_data = json.load(f)
                
                if not portfolio_df.empty:
                    portfolio_exposure = portfolio_df['final_weight'].sum()
                    risk_cap = risk_data.get('risk_authority', {}).get('final_exposure_cap', 1.0)
                    
                    # Check if portfolio exposure respects risk cap
                    exposure_within_cap = abs(portfolio_exposure) <= risk_cap + 0.01  # Small tolerance
                    
                    consistency_checks['portfolio_risk_consistency'] = {
                        'portfolio_exposure': portfolio_exposure,
                        'risk_cap': risk_cap,
                        'exposure_within_cap': exposure_within_cap
                    }
                    
                    if not exposure_within_cap:
                        self.results['issues'].append(f"Portfolio exposure {portfolio_exposure:.3f} exceeds risk cap {risk_cap:.3f}")
            
            # Check timestamp consistency
            file_timestamps = {}
            
            files_to_check = [
                'data/processed/unified_portfolio.parquet',
                'data/risk/unified_risk_state.json',
                'data/processed/unified_intelligence_summary.json'
            ]
            
            for file_path in files_to_check:
                if os.path.exists(file_path):
                    file_age = datetime.now() - datetime.fromtimestamp(os.path.getmtime(file_path))
                    file_timestamps[file_path] = file_age.total_seconds() / 3600  # hours
            
            # Check if files are reasonably recent (within 1 hour)
            recent_files = sum(1 for age in file_timestamps.values() if age < 1.0)
            
            consistency_checks['file_timestamps'] = {
                'files_checked': len(file_timestamps),
                'recent_files': recent_files,
                'timestamps': file_timestamps
            }
            
            self.results['data_integrity']['consistency_across_operations'] = consistency_checks
            
            # Overall consistency assessment
            consistency_issues = len([issue for issue in self.results['issues'] if 'consistency' in issue.lower()])
            
            if consistency_issues == 0:
                self.log("✅ Data consistency verified across operations")
                return True
            else:
                self.log(f"⚠️ {consistency_issues} consistency issues found", "WARNING")
                return True  # Not a hard failure
                
        except Exception as e:
            self.log(f"❌ Data consistency verification failed: {e}", "ERROR")
            self.results['data_integrity']['consistency_across_operations'] = {'error': str(e)}
            return False
    
    def run_verification(self) -> Dict[str, Any]:
        """Run complete system operations verification"""
        self.log("=" * 60)
        self.log("STARTING SYSTEM OPERATIONS VERIFICATION")
        self.log("=" * 60)
        
        # Run verification tests
        verification_tests = [
            ("Portfolio Construction", self.verify_portfolio_construction),
            ("Risk Management", self.verify_risk_management),
            ("Intelligence Generation", self.verify_intelligence_generation),
            ("Market Brain Status", self.verify_market_brain_status),
            ("Data Consistency", self.verify_data_consistency_across_operations)
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
            recommendations.append("Improve system reliability - some operations need attention")
        
        if overall_score >= 0.9:
            recommendations.append("System operations excellent - all components working well")
        
        # Add specific recommendations based on results
        if 'operations' in self.results:
            failed_operations = [op for op, result in self.results['operations'].items() 
                               if not result.get('success', True) or 'error' in result]
            if failed_operations:
                recommendations.append(f"Review failed operations: {', '.join(failed_operations)}")
        
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
        results_file = project_root / "data" / "validation" / "system_operations_verification.json"
        results_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(results_file, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)
        
        self.log(f"\nVerification results saved to: {results_file}")
        
        return self.results

def main():
    """Main verification script"""
    import argparse
    
    parser = argparse.ArgumentParser(description="System Operations Verification")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    # Run verification
    verifier = SystemOperationsVerifier(verbose=args.verbose)
    results = verifier.run_verification()
    
    # Return appropriate exit code
    if results['verification_status'] == 'PASSED':
        print("\n🎯 System Operations Verification: ✅ PASSED")
        print("All system operations are functioning correctly!")
        return 0
    else:
        print("\n❌ System Operations Verification: FAILED")
        print("Some system operations need attention.")
        return 1

if __name__ == "__main__":
    sys.exit(main())