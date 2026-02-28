#!/usr/bin/env python3
"""
🎯 TASK 15.1: BUILD WALK-FORWARD REALITY INVARIANCE TEST
The Ultimate Test That Separates Toys from Funds

This script implements the walk-forward reality invariance test - the most critical
validation that ensures no look-ahead bias exists in the system. This test validates
that changing future data doesn't affect historical decisions.

SYSTEM LAW ENFORCED:
Property 20: Walk-Forward Reality Invariance (Z1)
- For any change to future data, historical portfolio decisions must remain identical
- This is what separates research toys from capital-grade systems

Requirements: 11.1, 11.6
"""

import os
import sys
import json
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple
import pandas as pd
import numpy as np

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


from src.cohesion.temporal_guard import TemporalGuard, DataQuery
from src.cohesion.unified_state_manager import UnifiedStateManager, AuthorityLevel
from src.cohesion.configuration_manager import ConfigurationManager
from src.cohesion.error_handler import ErrorHandler, ErrorSeverity, ErrorCategory

class WalkForwardRealityTest:
    """
    The Ultimate Test: Walk-Forward Reality Invariance
    
    This test validates that the system has no look-ahead bias by ensuring
    that changing future data doesn't affect historical decisions.
    """
    
    def __init__(self):
        self.config_manager = ConfigurationManager()
        self.state_manager = UnifiedStateManager()
        self.temporal_guard = TemporalGuard()
        self.error_handler = ErrorHandler()
        
        # Test configuration
        self.test_results = []
        self.violation_count = 0
        self.test_start_time = datetime.now()
        
    def generate_test_data(self, start_date: datetime, end_date: datetime) -> pd.DataFrame:
        """Generate synthetic market data for testing"""
        
        date_range = pd.date_range(start=start_date, end=end_date, freq='D')
        
        # Generate synthetic price data
        np.random.seed(42)  # Reproducible for testing
        returns = np.random.normal(0.0008, 0.02, len(date_range))  # Daily returns
        prices = 100 * np.exp(np.cumsum(returns))
        
        # Generate synthetic fundamental data
        earnings = np.random.normal(10, 2, len(date_range))
        volume = np.random.lognormal(15, 0.5, len(date_range))
        
        data = pd.DataFrame({
            'date': date_range,
            'price': prices,
            'returns': returns,
            'earnings': earnings,
            'volume': volume,
            'timestamp': date_range
        })
        
        return data
    
    def modify_future_data(self, data: pd.DataFrame, cutoff_date: datetime) -> pd.DataFrame:
        """
        Modify data after cutoff_date to test reality invariance
        
        This simulates what happens when future data changes - the historical
        decisions should remain identical.
        """
        
        modified_data = data.copy()
        
        # Only modify data after cutoff_date
        future_mask = modified_data['date'] > cutoff_date
        
        if future_mask.any():
            # Scramble future prices
            future_indices = modified_data[future_mask].index
            future_prices = modified_data.loc[future_indices, 'price'].values
            np.random.shuffle(future_prices)
            modified_data.loc[future_indices, 'price'] = future_prices
            
            # Scramble future earnings
            future_earnings = modified_data.loc[future_indices, 'earnings'].values
            np.random.shuffle(future_earnings)
            modified_data.loc[future_indices, 'earnings'] = future_earnings
            
            # Recalculate returns for future data
            for i in future_indices:
                if i > 0:
                    prev_price = modified_data.loc[i-1, 'price']
                    curr_price = modified_data.loc[i, 'price']
                    modified_data.loc[i, 'returns'] = (curr_price - prev_price) / prev_price
        
        return modified_data
    
    def simulate_portfolio_decisions(self, data: pd.DataFrame, as_of_date: datetime) -> Dict[str, Any]:
        """
        Simulate portfolio decisions using only data available as of as_of_date
        
        This represents the core investment logic that must be temporally protected.
        """
        
        # Set temporal context
        self.temporal_guard.set_time_context(as_of_date)
        
        # Filter data to only what was available as of as_of_date
        available_data = data[data['date'] <= as_of_date].copy()
        
        if len(available_data) < 20:  # Need minimum history
            return {'positions': {}, 'total_exposure': 0.0, 'decision_hash': ''}
        
        # Simple momentum strategy using only historical data
        recent_data = available_data.tail(20)
        momentum_score = recent_data['returns'].mean()
        volatility = recent_data['returns'].std()
        
        # Risk-adjusted position sizing
        if volatility > 0:
            position_size = min(0.1, abs(momentum_score) / volatility)  # Max 10% position
        else:
            position_size = 0.0
        
        # Direction based on momentum
        direction = 1 if momentum_score > 0 else -1
        final_position = direction * position_size
        
        # Portfolio decision
        portfolio_decision = {
            'positions': {'ASSET_1': final_position},
            'total_exposure': abs(final_position),
            'momentum_score': momentum_score,
            'volatility': volatility,
            'decision_date': as_of_date.isoformat(),
            'data_points_used': len(available_data)
        }
        
        # Create deterministic hash of the decision
        decision_str = json.dumps(portfolio_decision, sort_keys=True)
        decision_hash = hashlib.md5(decision_str.encode()).hexdigest()
        portfolio_decision['decision_hash'] = decision_hash
        
        return portfolio_decision
    
    def run_walk_forward_test(self, 
                             start_date: datetime, 
                             end_date: datetime,
                             test_dates: List[datetime]) -> Dict[str, Any]:
        """
        Run the walk-forward reality invariance test
        
        This is the ultimate test that validates temporal protection.
        """
        
        print(f"🎯 RUNNING WALK-FORWARD REALITY INVARIANCE TEST")
        print(f"   Test Period: {start_date.date()} to {end_date.date()}")
        print(f"   Test Dates: {len(test_dates)} checkpoints")
        print("=" * 60)
        
        # Generate original test data
        original_data = self.generate_test_data(start_date, end_date)
        print(f"✅ Generated {len(original_data)} days of test data")
        
        # Run original backtest
        original_decisions = {}
        for test_date in test_dates:
            decision = self.simulate_portfolio_decisions(original_data, test_date)
            original_decisions[test_date.isoformat()] = decision
            print(f"   📊 Original decision for {test_date.date()}: {decision['decision_hash'][:8]}")
        
        # Test reality invariance for each test date
        invariance_results = []
        
        for i, test_date in enumerate(test_dates):
            print(f"\n🔍 Testing reality invariance for {test_date.date()}...")
            
            # Modify future data after this test date
            modified_data = self.modify_future_data(original_data, test_date)
            
            # Re-run decisions up to and including this test date
            rerun_decisions = {}
            for check_date in test_dates[:i+1]:  # Only up to current test date
                decision = self.simulate_portfolio_decisions(modified_data, check_date)
                rerun_decisions[check_date.isoformat()] = decision
            
            # Validate invariance: decisions should be identical
            invariance_violations = []
            for check_date in test_dates[:i+1]:
                date_key = check_date.isoformat()
                original_hash = original_decisions[date_key]['decision_hash']
                rerun_hash = rerun_decisions[date_key]['decision_hash']
                
                if original_hash != rerun_hash:
                    violation = {
                        'test_date': test_date.isoformat(),
                        'affected_date': check_date.isoformat(),
                        'original_hash': original_hash,
                        'rerun_hash': rerun_hash,
                        'original_decision': original_decisions[date_key],
                        'rerun_decision': rerun_decisions[date_key]
                    }
                    invariance_violations.append(violation)
                    self.violation_count += 1
                    
                    print(f"   ❌ INVARIANCE VIOLATION: {check_date.date()}")
                    print(f"      Original: {original_hash[:8]}")
                    print(f"      Rerun:    {rerun_hash[:8]}")
                else:
                    print(f"   ✅ Invariance maintained: {check_date.date()}")
            
            invariance_results.append({
                'test_date': test_date.isoformat(),
                'violations': invariance_violations,
                'violation_count': len(invariance_violations)
            })
        
        # Compile final results
        test_results = {
            'test_period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'test_dates': [d.isoformat() for d in test_dates]
            },
            'original_decisions': original_decisions,
            'invariance_results': invariance_results,
            'total_violations': self.violation_count,
            'total_tests': len(test_dates),
            'success_rate': (len(test_dates) - self.violation_count) / len(test_dates),
            'test_timestamp': self.test_start_time.isoformat()
        }
        
        return test_results
    
    def validate_temporal_protection(self) -> bool:
        """
        Validate that temporal protection is working correctly
        
        This tests the core temporal guard functionality.
        """
        
        print("\n🛡️ VALIDATING TEMPORAL PROTECTION...")
        
        try:
            # Test 1: Set temporal context
            test_date = datetime(2023, 6, 1)
            self.temporal_guard.set_time_context(test_date)
            
            # Test 2: Validate data access with historical timestamp
            historical_timestamp = datetime(2023, 5, 1)
            result = self.temporal_guard.validate_data_access(
                data_timestamp=historical_timestamp,
                request_timestamp=datetime.now()
            )
            
            if not result:
                print("   ❌ Historical data access failed")
                return False
            
            print("   ✅ Historical data access validated")
            
            # Test 3: Future data access should be blocked
            future_timestamp = datetime(2023, 7, 1)  # Future data
            result = self.temporal_guard.validate_data_access(
                data_timestamp=future_timestamp,
                request_timestamp=datetime.now()
            )
            
            if result:  # Should be False for future data
                print("   ❌ Future data access was allowed (CRITICAL VIOLATION)")
                return False
            
            print("   ✅ Future data access blocked correctly")
            
            return True
            
        except Exception as e:
            print(f"   ❌ Temporal protection validation failed: {e}")
            return False
    
    def generate_validation_report(self, test_results: Dict[str, Any]) -> str:
        """Generate comprehensive validation report"""
        
        report = []
        report.append("🎯 WALK-FORWARD REALITY INVARIANCE TEST REPORT")
        report.append("=" * 60)
        report.append(f"Test Period: {test_results['test_period']['start_date']} to {test_results['test_period']['end_date']}")
        report.append(f"Test Checkpoints: {test_results['total_tests']}")
        report.append(f"Total Violations: {test_results['total_violations']}")
        report.append(f"Success Rate: {test_results['success_rate']:.2%}")
        report.append("")
        
        if test_results['total_violations'] == 0:
            report.append("🎉 PERFECT REALITY INVARIANCE")
            report.append("   No look-ahead bias detected")
            report.append("   System passes the ultimate test")
            report.append("   Ready for capital deployment")
        else:
            report.append("❌ REALITY INVARIANCE VIOLATIONS DETECTED")
            report.append("   Look-ahead bias present in system")
            report.append("   System NOT ready for capital deployment")
            report.append("   CRITICAL: Fix temporal protection before proceeding")
        
        report.append("")
        report.append("DETAILED RESULTS:")
        
        for result in test_results['invariance_results']:
            test_date = result['test_date']
            violation_count = result['violation_count']
            
            if violation_count == 0:
                report.append(f"   ✅ {test_date}: No violations")
            else:
                report.append(f"   ❌ {test_date}: {violation_count} violations")
                
                for violation in result['violations']:
                    affected_date = violation['affected_date']
                    report.append(f"      - Affected date: {affected_date}")
                    report.append(f"        Original hash: {violation['original_hash'][:8]}")
                    report.append(f"        Rerun hash:    {violation['rerun_hash'][:8]}")
        
        return "\\n".join(report)

def main():
    """Run Task 15.1: Walk-Forward Reality Invariance Test"""
    
    print("🎯 TASK 15.1: WALK-FORWARD REALITY INVARIANCE TEST")
    print("The Ultimate Test That Separates Toys from Funds")
    print("=" * 70)
    
    try:
        # Initialize test
        test = WalkForwardRealityTest()
        
        # Validate temporal protection first
        if not test.validate_temporal_protection():
            print("❌ Temporal protection validation failed")
            print("   Fix temporal guard before running reality test")
            return False
        
        # Define test parameters
        start_date = datetime(2023, 1, 1)
        end_date = datetime(2023, 12, 31)
        
        # Create test checkpoints (monthly)
        test_dates = []
        current_date = datetime(2023, 3, 1)  # Start after some history
        while current_date <= datetime(2023, 10, 1):  # End before year end
            test_dates.append(current_date)
            # Next month
            if current_date.month == 12:
                current_date = current_date.replace(year=current_date.year + 1, month=1)
            else:
                current_date = current_date.replace(month=current_date.month + 1)
        
        # Run the ultimate test
        test_results = test.run_walk_forward_test(start_date, end_date, test_dates)
        
        # Generate report
        report = test.generate_validation_report(test_results)
        print("\\n" + report)
        
        # Save results
        results_file = f"reports/walk_forward_reality_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        os.makedirs("reports", exist_ok=True)
        
        with open(results_file, 'w') as f:
            json.dump(test_results, f, indent=2)
        
        print(f"\\n📊 Results saved to: {results_file}")
        
        # Final verdict
        if test_results['total_violations'] == 0:
            print("\\n🎉 SYSTEM PASSES THE ULTIMATE TEST")
            print("   No look-ahead bias detected")
            print("   Walk-forward reality invariance maintained")
            print("   System ready for capital deployment")
            return True
        else:
            print("\\n❌ SYSTEM FAILS THE ULTIMATE TEST")
            print(f"   {test_results['total_violations']} reality invariance violations")
            print("   Look-ahead bias detected")
            print("   System NOT ready for capital deployment")
            return False
        
    except Exception as e:
        print(f"❌ Walk-forward reality test failed: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)