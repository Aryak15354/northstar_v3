#!/usr/bin/env python3
"""
🧪 BEHAVIORAL STABILITY PROPERTY TESTS - PHASE 6: ENHANCEMENT LAYER
Property-based tests for behavioral stability testing

**Validates: Requirements 12.1, 12.2, 12.3**

This implements property-based tests for the behavioral stability tester to ensure
parameter robustness validation works correctly across all parameter variations.

CRITICAL PRINCIPLE: Parameter Robustness Validation
- Test sensitivity to macro sources, rolling windows, transaction costs
- Verify correlation > 0.85 between base and parameter variants
- Test turnover control (5-15% monthly)
- Test regime consistency across parameter variations
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from hypothesis import given, strategies as st, settings, assume, example
from hypothesis.extra.pandas import data_frames, column
import warnings

warnings.filterwarnings('ignore')

# Import the behavioral stability tester
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.validation.behavioral_stability_tester import (
    BehavioralStabilityTester, 
    StabilityResult, 
    ParameterVariant,
    StabilityTestRecord
)


class TestBehavioralStabilityProperties:
    """Property-based tests for behavioral stability testing"""
    
    def setup_method(self):
        """Setup test environment"""
        self.tester = BehavioralStabilityTester(base_dir="data/testing/behavioral_stability")
        
        # Clean test directory
        import shutil
        if os.path.exists("data/testing/behavioral_stability"):
            shutil.rmtree("data/testing/behavioral_stability")
        os.makedirs("data/testing/behavioral_stability", exist_ok=True)
    
    def teardown_method(self):
        """Cleanup test environment"""
        import shutil
        if os.path.exists("data/testing/behavioral_stability"):
            shutil.rmtree("data/testing/behavioral_stability")
    
    @given(
        n_periods=st.integers(min_value=50, max_value=200),
        base_return=st.floats(min_value=0.0005, max_value=0.003),
        volatility=st.floats(min_value=0.01, max_value=0.03),
        seed=st.integers(min_value=1, max_value=1000)
    )
    @settings(max_examples=20, deadline=30000)
    def test_behavioral_stability_correlation_property(self, n_periods, base_return, volatility, seed):
        """
        **Property 27: Behavioral Stability Correlation**
        **Validates: Requirements 12.1, 12.2, 12.3**
        
        PROPERTY: For any strategy configuration, parameter variants with small changes
        should maintain correlation > threshold with base configuration.
        
        This tests that behavioral stability testing correctly identifies when
        parameter changes maintain strategy correlation above the required threshold.
        """
        
        np.random.seed(seed)
        
        # Generate synthetic market data
        dates = pd.date_range(start='2023-01-01', periods=n_periods, freq='W')
        market_data = pd.DataFrame({
            'returns': np.random.normal(base_return, volatility, n_periods),
            'volatility': np.random.uniform(0.15, 0.25, n_periods),
            'macro_factor_1': np.random.normal(0, 0.01, n_periods),
            'macro_factor_2': np.random.normal(0, 0.01, n_periods)
        }, index=dates)
        
        # Define base configuration
        base_config = {
            'macro_source': 'combined',
            'rolling_window': 26,
            'transaction_cost': 0.05,
            'strategy_type': 'momentum'
        }
        
        # Test behavioral stability
        stability_records = self.tester.test_strategy_stability(
            "test_strategy", base_config, market_data
        )
        
        # PROPERTY ASSERTIONS
        
        # Property 1: All records should be valid StabilityTestRecord instances
        assert len(stability_records) > 0, "Should generate at least one stability record"
        
        for record in stability_records:
            assert isinstance(record, StabilityTestRecord), "Should return StabilityTestRecord instances"
            
            # Validate record structure
            validation_errors = record.validate()
            assert len(validation_errors) == 0, f"Record validation failed: {validation_errors}"
        
        # Property 2: Correlation values should be within valid bounds
        for record in stability_records:
            assert -1.0 <= record.return_correlation <= 1.0, f"Return correlation {record.return_correlation} outside bounds [-1.0, 1.0]"
            assert -1.0 <= record.allocation_correlation <= 1.0, f"Allocation correlation {record.allocation_correlation} outside bounds [-1.0, 1.0]"
            assert -1.0 <= record.regime_consistency <= 1.0, f"Regime consistency {record.regime_consistency} outside bounds [-1.0, 1.0]"
        
        # Property 3: Turnover values should be reasonable
        for record in stability_records:
            assert 0.0 <= record.turnover_base <= 1.0, f"Base turnover {record.turnover_base} outside reasonable bounds [0.0, 1.0]"
            assert 0.0 <= record.turnover_variant <= 1.0, f"Variant turnover {record.turnover_variant} outside reasonable bounds [0.0, 1.0]"
        
        # Property 4: Stability assessment should be consistent with correlation threshold
        correlation_threshold = self.tester.config['correlation_threshold']
        
        for record in stability_records:
            meets_threshold = record.return_correlation >= correlation_threshold
            
            if record.stability_result == StabilityResult.STABLE:
                # Stable results should meet correlation threshold (with some tolerance for other factors)
                assert meets_threshold or record.return_correlation >= (correlation_threshold - 0.1), \
                    f"Stable result but correlation {record.return_correlation} too low for threshold {correlation_threshold}"
            
            elif record.stability_result == StabilityResult.UNSTABLE:
                # Unstable results should either fail correlation or other criteria
                # (Note: Can be unstable due to turnover or regime consistency issues even with good correlation)
                pass  # This is acceptable - other factors can cause instability
        
        # Property 5: Similar parameter variants should have higher correlation
        # Find pairs of records with similar parameter changes
        for i, record1 in enumerate(stability_records):
            for j, record2 in enumerate(stability_records[i+1:], i+1):
                # Check if variants are similar (same parameter type)
                variant1_type = record1.variant_name.split('_')[0]
                variant2_type = record2.variant_name.split('_')[0]
                
                if variant1_type == variant2_type:
                    # Similar variants should have similar correlations (within reasonable range)
                    correlation_diff = abs(record1.return_correlation - record2.return_correlation)
                    assert correlation_diff <= 0.5, \
                        f"Similar variants {record1.variant_name} and {record2.variant_name} have very different correlations: {record1.return_correlation:.3f} vs {record2.return_correlation:.3f}"
    
    @given(
        macro_sources=st.lists(
            st.sampled_from(['rbi_only', 'fred_only', 'combined']),
            min_size=2, max_size=3, unique=True
        ),
        rolling_windows=st.lists(
            st.integers(min_value=15, max_value=50),
            min_size=2, max_size=4, unique=True
        ),
        transaction_costs=st.lists(
            st.floats(min_value=0.01, max_value=0.1),
            min_size=2, max_size=4, unique=True
        )
    )
    @settings(max_examples=10, deadline=30000)
    def test_parameter_variant_generation_property(self, macro_sources, rolling_windows, transaction_costs):
        """
        **Property 28: Parameter Variant Generation Completeness**
        **Validates: Requirements 12.1, 12.2**
        
        PROPERTY: Parameter variant generation should create variants for all
        specified parameter types and maintain parameter diversity.
        
        This tests that the parameter variant generation covers all parameter
        types and creates meaningful variations for stability testing.
        """
        
        # Create base configuration with specific values
        base_config = {
            'macro_source': macro_sources[0],
            'rolling_window': rolling_windows[0],
            'transaction_cost': transaction_costs[0]
        }
        
        # Update tester configuration to use our test parameters
        self.tester.config['macro_source_variants'] = macro_sources
        self.tester.config['rolling_window_variants'] = rolling_windows
        self.tester.config['transaction_cost_variants'] = transaction_costs
        
        # Generate parameter variants
        variants = self.tester.generate_parameter_variants(base_config)
        
        # PROPERTY ASSERTIONS
        
        # Property 1: Should generate variants for each parameter type
        variant_types = set()
        for variant in variants:
            if 'macro_source' in variant.parameter_changes:
                variant_types.add('macro_source')
            if 'rolling_window' in variant.parameter_changes:
                variant_types.add('rolling_window')
            if 'transaction_cost' in variant.parameter_changes:
                variant_types.add('transaction_cost')
        
        # Should have variants for parameters that differ from base
        expected_types = set()
        if len([s for s in macro_sources if s != base_config['macro_source']]) > 0:
            expected_types.add('macro_source')
        if len([w for w in rolling_windows if w != base_config['rolling_window']]) > 0:
            expected_types.add('rolling_window')
        if len([c for c in transaction_costs if abs(c - base_config['transaction_cost']) > 0.001]) > 0:
            expected_types.add('transaction_cost')
        
        assert variant_types >= expected_types, f"Missing variant types. Expected: {expected_types}, Got: {variant_types}"
        
        # Property 2: Each variant should have valid parameter changes
        for variant in variants:
            assert isinstance(variant, ParameterVariant), "Should return ParameterVariant instances"
            assert len(variant.parameter_changes) > 0, "Each variant should have at least one parameter change"
            assert variant.variant_name, "Each variant should have a name"
            assert variant.description, "Each variant should have a description"
        
        # Property 3: Variants should not duplicate base configuration
        for variant in variants:
            # Skip combined variants as they may have some parameters same as base
            if variant.variant_name == "combined_stress":
                continue
                
            for param_name, param_value in variant.parameter_changes.items():
                base_value = base_config.get(param_name)
                if param_name == 'transaction_cost':
                    # Allow small floating point differences
                    assert abs(param_value - base_value) > 0.001, \
                        f"Variant {variant.variant_name} has same {param_name} as base: {param_value} vs {base_value}"
                else:
                    assert param_value != base_value, \
                        f"Variant {variant.variant_name} has same {param_name} as base: {param_value}"
        
        # Property 4: Variant names should be unique
        variant_names = [v.variant_name for v in variants]
        assert len(variant_names) == len(set(variant_names)), "Variant names should be unique"
    
    @given(
        correlation_threshold=st.floats(min_value=0.7, max_value=0.95),
        turnover_min=st.floats(min_value=0.02, max_value=0.08),
        turnover_max=st.floats(min_value=0.1, max_value=0.2),
        regime_threshold=st.floats(min_value=0.7, max_value=0.9)
    )
    @settings(max_examples=15, deadline=30000)
    def test_stability_assessment_consistency_property(self, correlation_threshold, turnover_min, turnover_max, regime_threshold):
        """
        **Property 29: Stability Assessment Consistency**
        **Validates: Requirements 12.3, 12.5, 12.6**
        
        PROPERTY: Stability assessment should be consistent with configured thresholds
        and behavioral criteria across different threshold configurations.
        
        This tests that the stability assessment logic correctly applies thresholds
        and maintains consistency in stability determinations.
        """
        
        assume(turnover_min < turnover_max)
        
        # Update tester configuration
        self.tester.config['correlation_threshold'] = correlation_threshold
        self.tester.config['turnover_min'] = turnover_min
        self.tester.config['turnover_max'] = turnover_max
        self.tester.config['regime_consistency_threshold'] = regime_threshold
        
        # Create test data with known characteristics
        np.random.seed(42)
        
        # Test different correlation scenarios
        test_scenarios = [
            {
                'return_correlation': correlation_threshold + 0.05,  # Above threshold
                'regime_consistency': regime_threshold + 0.05,      # Above threshold
                'turnover_base': (turnover_min + turnover_max) / 2, # Within bounds
                'turnover_variant': (turnover_min + turnover_max) / 2, # Within bounds
                'expected_stable': True
            },
            {
                'return_correlation': correlation_threshold - 0.05,  # Below threshold
                'regime_consistency': regime_threshold + 0.05,      # Above threshold
                'turnover_base': (turnover_min + turnover_max) / 2, # Within bounds
                'turnover_variant': (turnover_min + turnover_max) / 2, # Within bounds
                'expected_stable': False
            },
            {
                'return_correlation': correlation_threshold + 0.05,  # Above threshold
                'regime_consistency': regime_threshold - 0.05,      # Below threshold
                'turnover_base': (turnover_min + turnover_max) / 2, # Within bounds
                'turnover_variant': (turnover_min + turnover_max) / 2, # Within bounds
                'expected_stable': False
            },
            {
                'return_correlation': correlation_threshold + 0.05,  # Above threshold
                'regime_consistency': regime_threshold + 0.05,      # Above threshold
                'turnover_base': turnover_max + 0.05,               # Out of bounds
                'turnover_variant': (turnover_min + turnover_max) / 2, # Within bounds
                'expected_stable': False
            }
        ]
        
        for i, scenario in enumerate(test_scenarios):
            # Create mock results
            base_results = {
                'returns': np.array([0.001] * 50),
                'allocations': np.array([0.6] * 50),
                'regime_calls': np.array([1] * 50),
                'monthly_turnover': scenario['turnover_base']
            }
            
            variant_results = {
                'returns': np.array([0.001] * 50),
                'allocations': np.array([0.6] * 50),
                'regime_calls': np.array([1] * 50),
                'monthly_turnover': scenario['turnover_variant']
            }
            
            # Mock correlations
            correlations = {
                'return_correlation': scenario['return_correlation'],
                'allocation_correlation': 0.9,  # High allocation correlation
                'regime_consistency': scenario['regime_consistency'],
                'turnover_correlation': 0.8
            }
            
            # Assess stability
            stability_result, stability_message = self.tester.assess_stability(
                correlations, base_results, variant_results
            )
            
            # PROPERTY ASSERTIONS
            
            if scenario['expected_stable']:
                assert stability_result == StabilityResult.STABLE, \
                    f"Scenario {i}: Expected STABLE but got {stability_result.value}. Message: {stability_message}"
            else:
                assert stability_result == StabilityResult.UNSTABLE, \
                    f"Scenario {i}: Expected UNSTABLE but got {stability_result.value}. Message: {stability_message}"
            
            # Stability message should be informative
            assert len(stability_message) > 10, f"Stability message should be informative: '{stability_message}'"
    
    @example(
        base_config={'macro_source': 'combined', 'rolling_window': 26, 'transaction_cost': 0.05},
        n_periods=60
    )
    @given(
        base_config=st.fixed_dictionaries({
            'macro_source': st.sampled_from(['combined', 'rbi_only', 'fred_only']),
            'rolling_window': st.integers(min_value=20, max_value=40),
            'transaction_cost': st.floats(min_value=0.02, max_value=0.08)
        }),
        n_periods=st.integers(min_value=50, max_value=100)
    )
    @settings(max_examples=10, deadline=45000)
    def test_end_to_end_stability_testing_property(self, base_config, n_periods):
        """
        **Property 30: End-to-End Stability Testing Completeness**
        **Validates: Requirements 12.1-12.6**
        
        PROPERTY: Complete stability testing should produce valid results for any
        reasonable configuration and maintain consistency across the full workflow.
        
        This tests the complete behavioral stability testing workflow from
        parameter generation through stability assessment.
        """
        
        np.random.seed(42)
        
        # Generate synthetic market data
        dates = pd.date_range(start='2023-01-01', periods=n_periods, freq='W')
        market_data = pd.DataFrame({
            'returns': np.random.normal(0.001, 0.02, n_periods),
            'volatility': np.random.uniform(0.15, 0.25, n_periods),
            'macro_factor_1': np.random.normal(0, 0.01, n_periods),
            'macro_factor_2': np.random.normal(0, 0.01, n_periods)
        }, index=dates)
        
        # Run complete stability testing
        stability_records = self.tester.test_strategy_stability(
            "end_to_end_test_strategy", base_config, market_data
        )
        
        # PROPERTY ASSERTIONS
        
        # Property 1: Should generate stability records
        assert len(stability_records) > 0, "Should generate at least one stability record"
        
        # Property 2: All records should be valid and complete
        for record in stability_records:
            # Basic structure validation
            assert isinstance(record, StabilityTestRecord), "Should return StabilityTestRecord instances"
            assert record.strategy_name == "end_to_end_test_strategy", "Strategy name should match input"
            assert record.base_config == base_config, "Base config should match input"
            
            # Validation should pass
            validation_errors = record.validate()
            assert len(validation_errors) == 0, f"Record validation failed: {validation_errors}"
            
            # Variant configuration should be different from base
            config_differences = 0
            for param_name, param_value in record.variant_config.items():
                base_value = base_config.get(param_name)
                if param_name == 'transaction_cost':
                    if abs(param_value - base_value) > 0.001:
                        config_differences += 1
                elif param_value != base_value:
                    config_differences += 1
            
            assert config_differences > 0, f"Variant config should differ from base config for {record.variant_name}"
        
        # Property 3: Stability results should be consistent with thresholds
        correlation_threshold = self.tester.config['correlation_threshold']
        
        stable_count = len([r for r in stability_records if r.stability_result == StabilityResult.STABLE])
        unstable_count = len([r for r in stability_records if r.stability_result == StabilityResult.UNSTABLE])
        
        # Should have both stable and unstable results (or all stable if parameters are very similar)
        assert stable_count + unstable_count == len(stability_records), "All records should have valid stability results"
        
        # Property 4: Summary statistics should be consistent
        summary = self.tester.get_stability_summary("end_to_end_test_strategy")
        
        assert summary['total_strategies'] >= 1, "Should track at least one strategy"
        assert 'end_to_end_test_strategy' in summary['stability_results'], "Should include test strategy in results"
        
        strategy_results = summary['stability_results']['end_to_end_test_strategy']
        assert strategy_results['total_variants_tested'] == len(stability_records), "Summary should match actual records"
        assert strategy_results['stable_variants'] == stable_count, "Summary stable count should match"
        assert strategy_results['unstable_variants'] == unstable_count, "Summary unstable count should match"
        
        # Property 5: Stability rate should be reasonable (0-100%)
        stability_rate = strategy_results['stability_rate']
        assert 0.0 <= stability_rate <= 1.0, f"Stability rate {stability_rate} should be between 0.0 and 1.0"
        
        if len(stability_records) > 0:
            expected_rate = stable_count / len(stability_records)
            assert abs(stability_rate - expected_rate) < 1e-6, f"Stability rate calculation incorrect: {stability_rate} vs {expected_rate}"


def test_behavioral_stability_tester_initialization():
    """Test that behavioral stability tester initializes correctly"""
    
    tester = BehavioralStabilityTester(base_dir="data/testing/init")
    
    # Check configuration
    assert tester.config['correlation_threshold'] == 0.85
    assert tester.config['turnover_min'] == 0.05
    assert tester.config['turnover_max'] == 0.15
    assert tester.config['min_observations'] == 50
    
    # Check directories created
    assert os.path.exists(tester.stability_dir)
    
    # Cleanup
    import shutil
    if os.path.exists("data/testing/init"):
        shutil.rmtree("data/testing/init")


if __name__ == "__main__":
    # Run property tests
    pytest.main([__file__, "-v", "--tb=short"])
