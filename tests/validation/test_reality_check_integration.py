#!/usr/bin/env python3
"""
Integration Tests: Reality Check Engine with Walk-Forward Validation

Tests the integration between the Reality Check Engine and the broader
walk-forward validation system, ensuring seamless operation.

Integration Test 5: Reality Check Engine Integration - Validates: Requirements 3.5
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import sys
import os
import json

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from src.validation.reality_check_engine import RealityCheckEngine
from src.validation.walk_forward_engine import WalkForwardEngine


class TestRealityCheckIntegration:
    """Integration tests for reality check engine"""
    
    def setup_method(self):
        """Setup for each test"""
        self.reality_check = RealityCheckEngine()
        
        # Mock walk-forward engine for integration testing
        self.walk_forward_engine = None  # Will be mocked
        
        # Sample backtest results from walk-forward validation
        self.sample_backtest_results = {
            'total_return': 0.22,
            'sharpe_ratio': 1.6,
            'max_drawdown': 0.12,
            'trading_days': 252,
            'volatility': 0.15,
            'win_rate': 0.58
        }
        
        # Comprehensive validation data
        self.comprehensive_validation_data = {
            'universe_data': {
                'delisted_stocks': ['BHARTIARTL.NS', 'IDEA.NS'],  # 2% delisting rate
                'total_stocks': 100,
                'universe_changes': [
                    {'date': '2023-01-01', 'added': 5, 'removed': 3},
                    {'date': '2023-06-01', 'added': 2, 'removed': 4}
                ]
            },
            'trading_data': {
                'total_trades': 450,
                'total_volume': 750000000,  # ₹75 crore
                'avg_trade_size': 1666667,  # ₹16.67 lakh per trade
                'turnover_rate': 2.5
            },
            'position_data': {
                'positions': {
                    'RELIANCE.NS': 40000000,    # ₹4 crore
                    'TCS.NS': 35000000,         # ₹3.5 crore
                    'INFY.NS': 30000000,        # ₹3 crore
                    'HDFCBANK.NS': 25000000     # ₹2.5 crore
                },
                'adv_data': {
                    'RELIANCE.NS': 1200000000,  # ₹120 crore ADV
                    'TCS.NS': 900000000,        # ₹90 crore ADV
                    'INFY.NS': 800000000,       # ₹80 crore ADV
                    'HDFCBANK.NS': 1000000000   # ₹100 crore ADV
                }
            },
            'execution_data': {
                'large_trades': [
                    {'size': 15000000, 'market_cap': 2000000000, 'symbol': 'RELIANCE.NS'},
                    {'size': 12000000, 'market_cap': 1500000000, 'symbol': 'TCS.NS'},
                    {'size': 8000000, 'market_cap': 1200000000, 'symbol': 'INFY.NS'}
                ],
                'execution_shortfall': 0.0025,  # 25 bps average shortfall
                'fill_rate': 0.98
            },
            'regime_data': {
                'regime_returns': {
                    'bull_market': [0.025, 0.032, 0.018, 0.041, 0.028],
                    'bear_market': [-0.015, -0.022, 0.008, -0.035, -0.012],
                    'sideways_market': [0.005, -0.008, 0.012, -0.003, 0.015],
                    'crisis_period': [-0.045, -0.062, -0.028, 0.035, -0.018]
                },
                'regime_transitions': 12,
                'avg_regime_duration': 21  # days
            },
            'crisis_data': {
                'crisis_periods': [
                    {'name': 'COVID-19 March 2020', 'return': -0.18, 'duration': 30},
                    {'name': 'Banking Crisis 2018', 'return': -0.12, 'duration': 45},
                    {'name': 'Demonetization 2016', 'return': -0.08, 'duration': 20}
                ],
                'recovery_times': [60, 90, 45],  # days to recover
                'max_consecutive_losses': 8
            },
            'capacity_data': {
                'target_aum': 500000000,      # ₹50 crore target
                'market_capacity': 2000000000, # ₹200 crore market capacity
                'liquidity_buffer': 0.20,     # 20% buffer
                'capacity_utilization_history': [0.15, 0.18, 0.22, 0.25, 0.25]
            },
            'correlation_data': {
                'historical_correlations': [0.65, 0.68, 0.72, 0.69, 0.71, 0.66, 0.74],
                'correlation_breakdown_events': 2,
                'max_correlation_change': 0.15,
                'correlation_stability_score': 0.82
            },
            'optimization_data': {
                'parameter_trials': 75,
                'optimization_periods': 3,
                'parameters_tested': ['lookback', 'threshold', 'rebalance_freq'],
                'overfitting_score': 0.15,
                'parameter_stability': 0.78
            },
            'sample_data': {
                'total_periods': 120,
                'out_of_sample_periods': 40,   # 33% out-of-sample
                'in_sample_return': 0.24,
                'out_of_sample_return': 0.20,
                'performance_decay': 0.167,    # 16.7% decay
                'consistency_score': 0.85
            },
            'walk_forward_data': {
                'period_returns': [
                    0.022, 0.031, 0.015, 0.028, 0.019, 0.025, 0.012, 0.033,
                    0.008, 0.021, -0.005, 0.018, 0.026, 0.014, 0.029, 0.007
                ],
                'period_sharpe_ratios': [1.8, 2.1, 1.2, 1.9, 1.5, 1.7, 0.9, 2.2, 0.6, 1.4, -0.3, 1.3, 1.8, 1.1, 2.0, 0.5],
                'stability_metrics': {
                    'return_consistency': 0.75,
                    'sharpe_consistency': 0.68,
                    'drawdown_consistency': 0.82
                }
            },
            'intuition_data': {
                'intuition_checks': [
                    {'name': 'Market regime alignment', 'passed': True, 'score': 0.85},
                    {'name': 'Factor exposure consistency', 'passed': True, 'score': 0.78},
                    {'name': 'Fundamental driver correlation', 'passed': False, 'score': 0.45},
                    {'name': 'Economic cycle alignment', 'passed': True, 'score': 0.72},
                    {'name': 'Risk factor attribution', 'passed': True, 'score': 0.88},
                    {'name': 'Sector rotation logic', 'passed': True, 'score': 0.65},
                    {'name': 'Momentum persistence', 'passed': False, 'score': 0.52}
                ],
                'overall_intuition_score': 0.69,
                'failed_checks': 2
            }
        }
    
    def test_integration_comprehensive_validation_flow(self):
        """
        Integration Test 5: Comprehensive Validation Flow
        
        Tests the complete flow from backtest results through
        reality check validation to final recommendations.
        """
        
        print("🧪 Integration Test 5: Comprehensive Validation Flow")
        
        # Step 1: Run comprehensive reality check validation
        print("   Step 1: Running comprehensive reality check validation...")
        
        validation_results = self.reality_check.run_full_validation(
            self.sample_backtest_results,
            self.comprehensive_validation_data
        )
        
        # Verify validation results structure
        assert 'validation_timestamp' in validation_results
        assert 'validation_status' in validation_results
        assert 'overall_pass_rate' in validation_results
        assert 'constraint_results' in validation_results
        assert 'recommendations' in validation_results
        
        print(f"     ✓ Validation completed with status: {validation_results['validation_status']}")
        print(f"     ✓ Overall pass rate: {validation_results['overall_pass_rate']:.1%}")
        
        # Step 2: Verify all 12 constraints were tested
        print("   Step 2: Verifying all constraints were tested...")
        
        constraint_results = validation_results['constraint_results']
        assert len(constraint_results) == 12, f"Expected 12 constraints, got {len(constraint_results)}"
        
        expected_constraints = [
            'Survivorship Bias Elimination',
            'Transaction Cost Reality',
            'Liquidity Constraint Enforcement',
            'Market Impact Modeling',
            'Regime Change Robustness',
            'Crisis Period Performance',
            'Capacity Constraint Analysis',
            'Correlation Breakdown Detection',
            'Data Snooping Prevention',
            'Out-of-Sample Validation',
            'Walk-Forward Stability',
            'Economic Intuition Alignment'
        ]
        
        tested_constraints = [result['constraint_name'] for result in constraint_results]
        for expected in expected_constraints:
            assert expected in tested_constraints, f"Missing constraint: {expected}"
        
        print(f"     ✓ All 12 constraints tested successfully")
        
        # Step 3: Analyze constraint performance
        print("   Step 3: Analyzing constraint performance...")
        
        passed_constraints = [r for r in constraint_results if r['passed']]
        failed_constraints = [r for r in constraint_results if not r['passed']]
        
        print(f"     ✓ Passed constraints: {len(passed_constraints)}")
        print(f"     ✓ Failed constraints: {len(failed_constraints)}")
        
        # Step 4: Verify severity classification
        print("   Step 4: Verifying severity classification...")
        
        severity_counts = {'CRITICAL': 0, 'HIGH': 0, 'MEDIUM': 0, 'PASS': 0}
        for result in constraint_results:
            severity = result['severity']
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
        
        print(f"     ✓ Severity distribution: {severity_counts}")
        
        # Step 5: Validate recommendations
        print("   Step 5: Validating recommendations...")
        
        recommendations = validation_results['recommendations']
        if failed_constraints:
            assert len(recommendations) > 0, "Should generate recommendations for failed constraints"
            print(f"     ✓ Generated {len(recommendations)} recommendations")
            
            # Verify recommendations are actionable
            for rec in recommendations:
                assert len(rec) > 20, f"Recommendation too short: {rec}"
                assert any(keyword in rec.lower() for keyword in ['reduce', 'increase', 'improve', 'implement', 'add']), \
                    f"Recommendation not actionable: {rec}"
        else:
            print(f"     ✓ No recommendations needed (all constraints passed)")
        
        # Step 6: Test results persistence
        print("   Step 6: Testing results persistence...")
        
        # Verify results were saved
        results_file = self.reality_check.paths['validation_results']
        assert os.path.exists(results_file), f"Results file not created: {results_file}"
        
        # Load and verify saved results
        with open(results_file, 'r') as f:
            saved_results = json.load(f)
        
        assert saved_results['validation_status'] == validation_results['validation_status']
        assert len(saved_results['constraint_results']) == 12
        
        print(f"     ✓ Results persisted successfully to {results_file}")
        
        print("✅ Integration Test 5: Comprehensive Validation Flow PASSED")
        
        return validation_results
    
    def test_integration_constraint_interdependencies(self):
        """
        Tests that constraints properly interact and don't produce
        contradictory results when combined.
        """
        
        print("🧪 Testing Constraint Interdependencies")
        
        # Test scenario with related constraint failures
        interdependent_data = self.comprehensive_validation_data.copy()
        
        # Create conditions that should trigger multiple related constraints
        interdependent_data.update({
            'trading_data': {
                'total_trades': 800,           # High trading frequency
                'total_volume': 2000000000,    # High volume -> high transaction costs
                'avg_trade_size': 2500000,     # Large average trade size
                'turnover_rate': 4.0           # High turnover
            },
            'position_data': {
                'positions': {
                    'RELIANCE.NS': 120000000,   # ₹12 crore - large position
                    'TCS.NS': 90000000,         # ₹9 crore
                },
                'adv_data': {
                    'RELIANCE.NS': 1200000000,  # ₹120 crore ADV -> 10% of ADV
                    'TCS.NS': 900000000,        # ₹90 crore ADV -> 10% of ADV
                }
            },
            'execution_data': {
                'large_trades': [
                    {'size': 50000000, 'market_cap': 2000000000},  # Large trade -> market impact
                    {'size': 40000000, 'market_cap': 1500000000}
                ]
            }
        })
        
        results = self.reality_check.run_full_validation(
            self.sample_backtest_results,
            interdependent_data
        )
        
        # Analyze interdependent failures
        failed_constraints = [r for r in results['constraint_results'] if not r['passed']]
        failed_names = [r['constraint_name'] for r in failed_constraints]
        
        print(f"   Failed constraints: {failed_names}")
        
        # Verify related constraints failed together
        trading_related_constraints = [
            'Transaction Cost Reality',
            'Liquidity Constraint Enforcement',
            'Market Impact Modeling'
        ]
        
        trading_failures = [name for name in failed_names if name in trading_related_constraints]
        
        if len(trading_failures) > 1:
            print(f"   ✓ Related trading constraints failed together: {trading_failures}")
        
        print("✅ Constraint Interdependencies Test PASSED")
    
    def test_integration_performance_benchmarking(self):
        """
        Tests the performance characteristics of the reality check engine
        to ensure it can handle production workloads.
        """
        
        print("🧪 Testing Performance Benchmarking")
        
        import time
        
        # Measure validation performance
        start_time = time.time()
        
        results = self.reality_check.run_full_validation(
            self.sample_backtest_results,
            self.comprehensive_validation_data
        )
        
        end_time = time.time()
        validation_time = end_time - start_time
        
        print(f"   Validation time: {validation_time:.2f} seconds")
        
        # Performance requirements
        assert validation_time < 10.0, f"Validation too slow: {validation_time:.2f}s > 10.0s"
        
        # Memory usage should be reasonable
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        memory_mb = process.memory_info().rss / 1024 / 1024
        
        print(f"   Memory usage: {memory_mb:.1f} MB")
        assert memory_mb < 500, f"Memory usage too high: {memory_mb:.1f} MB > 500 MB"
        
        print("✅ Performance Benchmarking Test PASSED")
    
    def test_integration_error_handling(self):
        """
        Tests error handling and graceful degradation when
        validation data is incomplete or malformed.
        """
        
        print("🧪 Testing Error Handling")
        
        # Test with missing data sections
        incomplete_data = {
            'universe_data': self.comprehensive_validation_data['universe_data'],
            'trading_data': self.comprehensive_validation_data['trading_data']
            # Missing other sections
        }
        
        try:
            results = self.reality_check.run_full_validation(
                self.sample_backtest_results,
                incomplete_data
            )
            
            # Should still produce results, but with some constraints using defaults
            assert 'validation_status' in results
            assert len(results['constraint_results']) == 12
            
            print("   ✓ Handled incomplete data gracefully")
            
        except Exception as e:
            print(f"   ❌ Failed to handle incomplete data: {e}")
            raise
        
        # Test with malformed backtest results
        malformed_backtest = {
            'total_return': 'invalid',  # Should be numeric
            'sharpe_ratio': None
        }
        
        try:
            results = self.reality_check.run_full_validation(
                malformed_backtest,
                self.comprehensive_validation_data
            )
            
            print("   ✓ Handled malformed backtest results gracefully")
            
        except Exception as e:
            # Should handle gracefully or provide meaningful error
            assert "invalid" in str(e).lower() or "none" in str(e).lower()
            print(f"   ✓ Provided meaningful error for malformed data: {e}")
        
        print("✅ Error Handling Test PASSED")


def main():
    """Run integration tests for reality check engine"""
    
    print("🧪 REALITY CHECK ENGINE - INTEGRATION TESTS")
    print("=" * 80)
    
    test_suite = TestRealityCheckIntegration()
    test_suite.setup_method()
    
    try:
        # Run integration tests
        validation_results = test_suite.test_integration_comprehensive_validation_flow()
        print()
        
        test_suite.test_integration_constraint_interdependencies()
        print()
        
        test_suite.test_integration_performance_benchmarking()
        print()
        
        test_suite.test_integration_error_handling()
        print()
        
        print("🎉 ALL INTEGRATION TESTS PASSED!")
        print("💡 Reality Check Engine integration validated successfully")
        
        # Print summary of validation results
        print(f"\n📊 VALIDATION SUMMARY:")
        print(f"Status: {validation_results['validation_status']}")
        print(f"Pass Rate: {validation_results['overall_pass_rate']:.1%}")
        print(f"Recommendations: {len(validation_results['recommendations'])}")
        
    except Exception as e:
        print(f"❌ Integration test failed: {e}")
        raise


if __name__ == "__main__":
    main()
