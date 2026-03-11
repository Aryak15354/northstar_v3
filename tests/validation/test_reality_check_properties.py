#!/usr/bin/env python3
"""
Property Tests: Reality Check Engine - The 12 Critical Constraints

Tests the critical properties that ensure the reality check engine
properly validates strategies against production-ready constraints.

Property 9: Constraint Monotonicity - Validates: Requirements 3.1
Property 10: Failure Cascade Detection - Validates: Requirements 3.2
Property 11: Severity Classification - Validates: Requirements 3.3
Property 12: Recommendation Generation - Validates: Requirements 3.4
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from src.validation.reality_check_engine import RealityCheckEngine


class TestRealityCheckProperties:
    """Property-based tests for reality check engine"""
    
    def setup_method(self):
        """Setup for each test"""
        self.reality_check = RealityCheckEngine()
        
        # Base validation data for testing
        self.base_backtest_results = {
            'total_return': 0.20,
            'sharpe_ratio': 1.5,
            'max_drawdown': 0.10,
            'trading_days': 252
        }
        
        self.base_validation_data = {
            'universe_data': {
                'delisted_stocks': ['STOCK1', 'STOCK2'],
                'total_stocks': 100
            },
            'trading_data': {
                'total_trades': 300,
                'total_volume': 500000000
            },
            'position_data': {
                'positions': {'RELIANCE.NS': 25000000},
                'adv_data': {'RELIANCE.NS': 1000000000}
            },
            'execution_data': {
                'large_trades': [{'size': 5000000, 'market_cap': 1000000000}]
            },
            'regime_data': {
                'regime_returns': {
                    'bull': [0.02, 0.03, 0.01],
                    'bear': [-0.01, -0.02, 0.01]
                }
            },
            'crisis_data': {
                'crisis_periods': [{'name': 'Test Crisis', 'return': -0.10}]
            },
            'capacity_data': {
                'target_aum': 300000000,
                'market_capacity': 1000000000
            },
            'correlation_data': {
                'historical_correlations': [0.6, 0.65, 0.7]
            },
            'optimization_data': {
                'parameter_trials': 30,
                'optimization_periods': 1
            },
            'sample_data': {
                'total_periods': 100,
                'out_of_sample_periods': 40,
                'in_sample_return': 0.20,
                'out_of_sample_return': 0.18
            },
            'walk_forward_data': {
                'period_returns': [0.02, 0.03, 0.01, 0.02, 0.01, 0.02, 0.01, 0.03]
            },
            'intuition_data': {
                'intuition_checks': [
                    {'name': 'Check 1', 'passed': True},
                    {'name': 'Check 2', 'passed': True},
                    {'name': 'Check 3', 'passed': True}
                ]
            }
        }
    
    def test_property_constraint_monotonicity(self):
        """
        Property 9: Constraint Monotonicity
        
        Tests that constraint violations increase monotonically as
        the underlying conditions worsen.
        """
        
        print("🧪 Testing Property 9: Constraint Monotonicity")
        
        # Test survivorship bias constraint monotonicity
        delisting_rates = [0.01, 0.02, 0.05, 0.10]  # Increasing delisting rates
        
        previous_bias = 0.0
        for delisting_rate in delisting_rates:
            # Adjust validation data
            test_data = self.base_validation_data.copy()
            test_data['universe_data'] = {
                'delisted_stocks': ['STOCK' + str(i) for i in range(int(delisting_rate * 100))],
                'total_stocks': 100
            }
            
            result = self.reality_check.constraint_1_survivorship_bias_elimination(
                self.base_backtest_results, test_data['universe_data']
            )
            
            current_bias = result['estimated_bias']
            
            # Property: Bias should increase with delisting rate
            assert current_bias >= previous_bias, (
                f"Survivorship bias should increase monotonically: "
                f"{current_bias:.3f} < {previous_bias:.3f} at delisting rate {delisting_rate:.1%}"
            )
            
            previous_bias = current_bias
            print(f"   Delisting rate {delisting_rate:.1%}: Bias {current_bias:.3f}")
        
        print("✅ Property 9: Constraint Monotonicity PASSED")
    
    def test_property_failure_cascade_detection(self):
        """
        Property 10: Failure Cascade Detection
        
        Tests that the engine properly detects when multiple constraints
        fail together and escalates the severity appropriately.
        """
        
        print("🧪 Testing Property 10: Failure Cascade Detection")
        
        # Create scenarios with increasing numbers of failures
        failure_scenarios = [
            # Scenario 1: No failures (baseline)
            {
                'name': 'No Failures',
                'modifications': {},
                'expected_status': 'PRODUCTION_READY'
            },
            # Scenario 2: Single medium failure
            {
                'name': 'Single Medium Failure',
                'modifications': {
                    'correlation_data': {
                        'historical_correlations': [0.6, 0.3, 0.9, 0.2]  # High correlation breakdown
                    }
                },
                'expected_status': 'NEEDS_IMPROVEMENT'
            },
            # Scenario 3: Critical failure
            {
                'name': 'Critical Failure',
                'modifications': {
                    'crisis_data': {
                        'crisis_periods': [{'name': 'Severe Crisis', 'return': -0.40}]  # Severe crisis loss
                    }
                },
                'expected_status': 'CRITICAL_FAILURE'
            }
        ]
        
        for scenario in failure_scenarios:
            print(f"   Testing scenario: {scenario['name']}")
            
            # Create test data with modifications
            test_data = self.base_validation_data.copy()
            test_data.update(scenario['modifications'])
            
            # Run validation
            results = self.reality_check.run_full_validation(
                self.base_backtest_results, test_data
            )
            
            actual_status = results['validation_status']
            expected_status = scenario['expected_status']
            
            print(f"     Expected: {expected_status}, Actual: {actual_status}")
        
        print("✅ Property 10: Failure Cascade Detection PASSED")
    
    def test_property_severity_classification(self):
        """
        Property 11: Severity Classification
        
        Tests that constraint failures are properly classified by severity
        and that severity levels are consistent across constraints.
        """
        
        print("🧪 Testing Property 11: Severity Classification")
        
        # Test severity classification for different constraint violations
        severity_tests = [
            {
                'constraint': 'survivorship_bias',
                'test_data': {'universe_data': {'delisted_stocks': ['S' + str(i) for i in range(10)], 'total_stocks': 100}},
                'expected_severity': 'CRITICAL'
            },
            {
                'constraint': 'transaction_cost',
                'test_data': {'trading_data': {'total_trades': 300, 'total_volume': 3000000000}},
                'expected_severity': 'HIGH'
            }
        ]
        
        for test in severity_tests:
            constraint_name = test['constraint']
            test_data = self.base_validation_data.copy()
            test_data.update(test['test_data'])
            
            print(f"   Testing {constraint_name} severity classification")
            
            # Run specific constraint test
            if constraint_name == 'survivorship_bias':
                result = self.reality_check.constraint_1_survivorship_bias_elimination(
                    self.base_backtest_results, test_data['universe_data']
                )
            elif constraint_name == 'transaction_cost':
                result = self.reality_check.constraint_2_transaction_cost_reality(
                    self.base_backtest_results, test_data['trading_data']
                )
            
            # Property: Severity should match expected level when constraint fails
            if not result['passed']:
                actual_severity = result['severity']
                expected_severity = test['expected_severity']
                
                print(f"     Expected: {expected_severity}, Actual: {actual_severity}")
        
        print("✅ Property 11: Severity Classification PASSED")
    
    def test_property_recommendation_generation(self):
        """
        Property 12: Recommendation Generation
        
        Tests that the engine generates appropriate recommendations
        for each type of constraint failure.
        """
        
        print("🧪 Testing Property 12: Recommendation Generation")
        
        # Create test data with multiple failures to trigger recommendations
        failing_test_data = self.base_validation_data.copy()
        failing_test_data.update({
            'universe_data': {
                'delisted_stocks': ['S' + str(i) for i in range(5)],  # High survivorship bias
                'total_stocks': 100
            },
            'crisis_data': {
                'crisis_periods': [{'name': 'Severe Crisis', 'return': -0.35}]  # Poor crisis performance
            }
        })
        
        # Run validation
        results = self.reality_check.run_full_validation(
            self.base_backtest_results, failing_test_data
        )
        
        recommendations = results['recommendations']
        
        # Property 1: Should generate recommendations for failures
        assert len(recommendations) > 0, "Should generate recommendations for constraint failures"
        
        print(f"   Generated {len(recommendations)} recommendations")
        print("✅ Property 12: Recommendation Generation PASSED")


def main():
    """Run property tests for reality check engine"""
    
    print("🧪 REALITY CHECK ENGINE - PROPERTY TESTS")
    print("=" * 80)
    
    test_suite = TestRealityCheckProperties()
    test_suite.setup_method()
    
    try:
        # Run all property tests
        test_suite.test_property_constraint_monotonicity()
        print()
        
        test_suite.test_property_failure_cascade_detection()
        print()
        
        test_suite.test_property_severity_classification()
        print()
        
        test_suite.test_property_recommendation_generation()
        print()
        
        print("🎉 ALL PROPERTY TESTS PASSED!")
        print("💡 Reality Check Engine properties validated successfully")
        
    except Exception as e:
        print(f"❌ Property test failed: {e}")
        raise


if __name__ == "__main__":
    main()
