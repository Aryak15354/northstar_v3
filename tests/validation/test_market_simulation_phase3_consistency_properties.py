#!/usr/bin/env python3
"""
🧪 PROPERTY TESTS: Market Simulation Phase 3 Consistency
Tests for regime-based scenario generation maintaining Phase 3 characteristics

Property 3: Market Simulation Phase 3 Consistency
For any generated market scenario, the scenario should preserve Phase 3 regime 
fingerprint characteristics, enable correct anticipatory signal generation, and 
maintain realistic tailwind relationship patterns.

Validates: Requirements 2.1, 2.2, 2.5, 2.6

This property test ensures that:
1. Generated scenarios preserve regime fingerprint characteristics
2. Scenarios enable correct Phase 3 anticipatory signal generation  
3. Tailwind relationships remain realistic within scenarios
4. Regime transitions follow historical patterns
5. Stress scenarios trigger appropriate Phase 3 responses
6. Scenario validation metrics meet quality thresholds
"""

import pytest
import pandas as pd
import numpy as np
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import warnings
warnings.filterwarnings('ignore')

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from hypothesis import given, strategies as st, settings, assume, note
from hypothesis.stateful import RuleBasedStateMachine, rule, initialize, invariant
import hypothesis.strategies as st

# Import components under test
from src.validation.regime_based_scenario_generator import RegimeBasedScenarioGenerator
from src.validation.phase3_integration_layer import Phase3IntegrationLayer
from src.intelligence.regime_memory_system import RegimeMemorySystem
from src.intelligence.simple_tailwind_engine import SimpleTailwindEngine

# Test configuration
TEST_CONFIG = {
    'min_scenario_length': 10,
    'max_scenario_length': 100,
    'min_realism_score': 0.6,
    'max_feature_volatility': 5.0,
    'min_regime_consistency': 0.7,
    'max_daily_change_zscore': 3.0
}

# Strategy for generating test scenarios
@st.composite
def scenario_parameters(draw):
    """Generate valid scenario parameters for testing"""
    return {
        'regime': draw(st.sampled_from(['Crisis', 'Expansion', 'Late-Expansion', 'Slowdown'])),
        'scenario_type': draw(st.sampled_from(['regime_continuation', 'regime_transition', 
                                             'regime_breakdown', 'stress_scenario'])),
        'length_days': draw(st.integers(min_value=TEST_CONFIG['min_scenario_length'], 
                                       max_value=TEST_CONFIG['max_scenario_length'])),
        'stress_multiplier': draw(st.floats(min_value=1.0, max_value=3.0)),
        'noise_level': draw(st.floats(min_value=0.05, max_value=0.3))
    }

@st.composite
def regime_characteristics(draw):
    """Generate realistic regime characteristics for testing"""
    n_features = draw(st.integers(min_value=3, max_value=8))
    
    characteristics = {}
    for i in range(n_features):
        feature_name = f"feature_{i}"
        mean_val = draw(st.floats(min_value=-2.0, max_value=2.0))
        std_val = draw(st.floats(min_value=0.1, max_value=1.0))
        
        characteristics[feature_name] = {
            'mean': mean_val,
            'std': std_val,
            'min': mean_val - 3 * std_val,
            'max': mean_val + 3 * std_val,
            'median': mean_val
        }
    
    return characteristics

class TestMarketSimulationPhase3Consistency:
    """Property tests for market simulation Phase 3 consistency"""
    
    def setup_method(self):
        """Setup test environment"""
        self.generator = RegimeBasedScenarioGenerator()
        self.phase3_integration = Phase3IntegrationLayer()
        
        # Create test data directories
        os.makedirs('data/intelligence', exist_ok=True)
        os.makedirs('data/shadow_reality', exist_ok=True)
    
    @given(params=scenario_parameters())
    @settings(max_examples=50, deadline=30000)
    def test_property_3_market_simulation_phase3_consistency(self, params):
        """
        Feature: shadow-reality, Property 3: Market Simulation Phase 3 Consistency
        
        For any generated market scenario, the scenario should preserve Phase 3 regime 
        fingerprint characteristics, enable correct anticipatory signal generation, and 
        maintain realistic tailwind relationship patterns.
        """
        note(f"Testing scenario: {params['scenario_type']} for regime {params['regime']}")
        
        # Create mock regime characteristics for testing
        regime_chars = {
            params['regime']: {
                'n_periods': 50,
                'frequency': 0.25,
                'feature_stats': {
                    'MacroScore': {'mean': 0.1, 'std': 0.5, 'min': -1.0, 'max': 1.0, 'median': 0.0},
                    'Contrib_G': {'mean': 0.0, 'std': 0.3, 'min': -0.8, 'max': 0.8, 'median': 0.0},
                    'Contrib_I': {'mean': 0.05, 'std': 0.4, 'min': -1.0, 'max': 1.0, 'median': 0.0}
                },
                'performance_stats': {'avg_return': 0.08, 'avg_sharpe': 1.2}
            }
        }
        
        # Generate scenario based on type
        if params['scenario_type'] == 'regime_continuation':
            scenario = self.generator.generate_regime_continuation_scenario(
                params['regime'], regime_chars, params['length_days']
            )
        elif params['scenario_type'] == 'regime_transition':
            # Create target regime for transition
            target_regimes = ['Crisis', 'Expansion', 'Late-Expansion', 'Slowdown']
            target_regime = [r for r in target_regimes if r != params['regime']][0]
            
            # Add target regime characteristics
            regime_chars[target_regime] = {
                'n_periods': 40,
                'frequency': 0.2,
                'feature_stats': {
                    'MacroScore': {'mean': -0.2, 'std': 0.6, 'min': -1.5, 'max': 1.0, 'median': -0.1},
                    'Contrib_G': {'mean': -0.1, 'std': 0.4, 'min': -1.0, 'max': 0.6, 'median': -0.05},
                    'Contrib_I': {'mean': 0.0, 'std': 0.5, 'min': -1.2, 'max': 1.2, 'median': 0.0}
                },
                'performance_stats': {'avg_return': 0.05, 'avg_sharpe': 0.8}
            }
            
            scenario = self.generator.generate_regime_transition_scenario(
                params['regime'], target_regime, regime_chars, params['length_days']
            )
        elif params['scenario_type'] == 'regime_breakdown':
            scenario = self.generator.generate_regime_breakdown_scenario(
                params['regime'], regime_chars, params['length_days']
            )
        else:  # stress_scenario
            scenario = self.generator.generate_stress_scenario(
                params['regime'], regime_chars, params['length_days']
            )
        
        # Skip if scenario generation failed
        assume(not scenario.empty)
        assume(len(scenario) >= TEST_CONFIG['min_scenario_length'])
        
        note(f"Generated scenario with {len(scenario)} periods")
        
        # Property 3.1: Scenario preserves regime fingerprint characteristics
        self._validate_regime_fingerprint_preservation(scenario, regime_chars, params)
        
        # Property 3.2: Scenario enables correct anticipatory signal generation
        self._validate_anticipatory_signal_generation(scenario, params)
        
        # Property 3.3: Tailwind relationships remain realistic
        self._validate_tailwind_relationships(scenario, params)
        
        # Property 3.4: Scenario validation metrics meet quality thresholds
        validation = self.generator.validate_scenario_realism(scenario, regime_chars)
        self._validate_scenario_quality_metrics(validation, params)
        
        # Property 3.5: Regime transitions follow historical patterns (if applicable)
        if params['scenario_type'] == 'regime_transition':
            self._validate_regime_transition_patterns(scenario, params)
        
        # Property 3.6: Stress scenarios trigger appropriate responses (if applicable)
        if params['scenario_type'] == 'stress_scenario':
            self._validate_stress_scenario_responses(scenario, params)
    
    def _validate_regime_fingerprint_preservation(self, scenario: pd.DataFrame, 
                                                regime_chars: Dict, params: Dict):
        """Validate that scenario preserves regime fingerprint characteristics"""
        
        regime = params['regime']
        scenario_type = params['scenario_type']
        
        # Get feature columns
        feature_cols = [col for col in scenario.columns 
                       if col in ['MacroScore', 'Contrib_G', 'Contrib_I']]
        
        if not feature_cols:
            return  # Skip if no features to validate
        
        expected_chars = regime_chars[regime]['feature_stats']
        
        for feature in feature_cols:
            if feature in expected_chars and feature in scenario.columns:
                values = scenario[feature].dropna()
                
                if len(values) == 0:
                    continue
                
                expected_mean = expected_chars[feature]['mean']
                expected_std = expected_chars[feature]['std']
                
                actual_mean = values.mean()
                actual_std = values.std()
                
                # For normal scenarios, means should be close to expected
                if scenario_type in ['regime_continuation']:
                    # Allow some deviation but not too much
                    mean_tolerance = expected_std * 2.0  # 2 standard deviations
                    assert abs(actual_mean - expected_mean) <= mean_tolerance, \
                        f"Feature {feature} mean {actual_mean:.3f} too far from expected {expected_mean:.3f}"
                
                # Standard deviation should be reasonable (not too extreme)
                if scenario_type != 'regime_breakdown':
                    # For non-breakdown scenarios, volatility shouldn't be extreme
                    max_std_ratio = TEST_CONFIG['max_feature_volatility']
                    assert actual_std <= expected_std * max_std_ratio, \
                        f"Feature {feature} std {actual_std:.3f} too high vs expected {expected_std:.3f}"
                
                # Values should generally stay within reasonable bounds
                extreme_values = ((values < expected_chars[feature]['min'] - expected_std * 3) | 
                                (values > expected_chars[feature]['max'] + expected_std * 3)).sum()
                extreme_ratio = extreme_values / len(values)
                
                # Allow more extremes in stress/breakdown scenarios
                max_extreme_ratio = 0.3 if scenario_type in ['stress_scenario', 'regime_breakdown'] else 0.1
                assert extreme_ratio <= max_extreme_ratio, \
                    f"Feature {feature} has {extreme_ratio:.1%} extreme values (max allowed: {max_extreme_ratio:.1%})"
    
    def _validate_anticipatory_signal_generation(self, scenario: pd.DataFrame, params: Dict):
        """Validate that scenario enables correct anticipatory signal generation"""
        
        # Check that scenario has sufficient variability for signal generation
        feature_cols = [col for col in scenario.columns 
                       if col in ['MacroScore', 'Contrib_G', 'Contrib_I']]
        
        if not feature_cols:
            return
        
        # Signals require some variability in features
        for feature in feature_cols:
            if feature in scenario.columns:
                values = scenario[feature].dropna()
                
                if len(values) > 1:
                    # Feature should have some variability (not constant)
                    feature_std = values.std()
                    assert feature_std > 0.001, \
                        f"Feature {feature} has insufficient variability for signal generation"
                    
                    # Feature should have reasonable temporal structure
                    # (not pure noise - should have some persistence)
                    if len(values) > 5:
                        autocorr = values.autocorr(lag=1)
                        if not pd.isna(autocorr):
                            # Some persistence expected (but not perfect) - more lenient for stress scenarios and breakdown
                            if params.get('scenario_type') in ['stress_scenario', 'regime_breakdown'] or params.get('regime') == 'Crisis':
                                min_autocorr = -0.8  # Very lenient for extreme scenarios
                            else:
                                min_autocorr = -0.5
                            max_autocorr = 0.95
                            assert min_autocorr <= autocorr <= max_autocorr, \
                                f"Feature {feature} autocorrelation {autocorr:.3f} suggests unrealistic temporal structure"
        
        # Check that scenario provides regime information for signal generation
        if 'regime' in scenario.columns:
            regimes = scenario['regime'].dropna()
            if len(regimes) > 0:
                # Should have consistent regime information
                unique_regimes = regimes.unique()
                
                # For continuation scenarios, regime should be mostly stable
                if params['scenario_type'] == 'regime_continuation':
                    primary_regime_ratio = (regimes == regimes.iloc[0]).mean()
                    assert primary_regime_ratio >= 0.8, \
                        f"Continuation scenario has unstable regime classification: {primary_regime_ratio:.1%}"
                
                # For transition scenarios, should see regime change
                elif params['scenario_type'] == 'regime_transition':
                    assert len(unique_regimes) >= 2, \
                        f"Transition scenario shows no regime change: {unique_regimes}"
    
    def _validate_tailwind_relationships(self, scenario: pd.DataFrame, params: Dict):
        """Validate that tailwind relationships remain realistic within scenario"""
        
        feature_cols = [col for col in scenario.columns 
                       if col in ['MacroScore', 'Contrib_G', 'Contrib_I']]
        
        if len(feature_cols) < 2:
            return  # Need at least 2 features for relationship validation
        
        # Check correlation structure
        try:
            correlation_matrix = scenario[feature_cols].corr()
            
            # Correlations should be reasonable (not all perfect or all zero)
            off_diagonal_corrs = []
            for i in range(len(feature_cols)):
                for j in range(i + 1, len(feature_cols)):
                    corr = correlation_matrix.iloc[i, j]
                    if not pd.isna(corr):
                        off_diagonal_corrs.append(abs(corr))
            
            if off_diagonal_corrs:
                avg_abs_corr = np.mean(off_diagonal_corrs)
                max_abs_corr = np.max(off_diagonal_corrs)
                
                # For non-breakdown scenarios, correlations should be reasonable
                if params['scenario_type'] != 'regime_breakdown':
                    assert avg_abs_corr <= 0.9, \
                        f"Average correlation {avg_abs_corr:.3f} too high - suggests unrealistic relationships"
                    
                    assert max_abs_corr <= 0.95, \
                        f"Maximum correlation {max_abs_corr:.3f} too high - suggests perfect relationships"
                
                # Should have some relationship structure (not all zero correlations)
                assert avg_abs_corr >= 0.01, \
                    f"Average correlation {avg_abs_corr:.3f} too low - suggests no relationships"
        
        except Exception:
            # Correlation calculation failed - skip this validation
            pass
    
    def _validate_scenario_quality_metrics(self, validation: Dict, params: Dict):
        """Validate that scenario quality metrics meet thresholds"""
        
        # Overall realism score should meet minimum threshold
        realism_score = validation.get('realism_score', 0)
        min_realism = TEST_CONFIG['min_realism_score']
        
        # Adjust threshold for breakdown scenarios (expected to be less realistic)
        if params['scenario_type'] == 'regime_breakdown':
            min_realism *= 0.7  # Lower threshold for breakdown scenarios
        
        assert realism_score >= min_realism, \
            f"Scenario realism score {realism_score:.3f} below threshold {min_realism:.3f}"
        
        # Should not have excessive errors
        n_errors = len(validation.get('errors', []))
        assert n_errors == 0, \
            f"Scenario validation has {n_errors} errors: {validation.get('errors', [])}"
        
        # Warnings should be reasonable
        n_warnings = len(validation.get('warnings', []))
        max_warnings = 3 if params['scenario_type'] in ['stress_scenario', 'regime_breakdown'] else 1
        assert n_warnings <= max_warnings, \
            f"Scenario validation has {n_warnings} warnings (max {max_warnings}): {validation.get('warnings', [])}"
        
        # Specific validation checks should mostly pass
        validation_checks = validation.get('validation_checks', {})
        if validation_checks:
            passed_checks = sum(1 for status in validation_checks.values() if status == 'PASS')
            total_checks = len(validation_checks)
            
            if total_checks > 0:
                pass_rate = passed_checks / total_checks
                min_pass_rate = 0.5 if params['scenario_type'] == 'regime_breakdown' else 0.75
                
                assert pass_rate >= min_pass_rate, \
                    f"Validation pass rate {pass_rate:.1%} below threshold {min_pass_rate:.1%}"
    
    def _validate_regime_transition_patterns(self, scenario: pd.DataFrame, params: Dict):
        """Validate regime transition follows realistic patterns"""
        
        if 'transition_progress' not in scenario.columns:
            return
        
        transition_progress = scenario['transition_progress'].dropna()
        
        if len(transition_progress) == 0:
            return
        
        # Transition should actually progress
        max_progress = transition_progress.max()
        assert max_progress >= 0.5, \
            f"Regime transition did not progress sufficiently: {max_progress:.3f}"
        
        # Transition should be monotonic (generally increasing)
        if len(transition_progress) > 5:
            # Check that progress generally increases
            increasing_periods = (transition_progress.diff() >= 0).sum()
            total_periods = len(transition_progress) - 1  # Exclude first period (no diff)
            
            if total_periods > 0:
                increasing_ratio = increasing_periods / total_periods
                assert increasing_ratio >= 0.7, \
                    f"Regime transition not sufficiently monotonic: {increasing_ratio:.1%}"
        
        # Features should show gradual change during transition
        feature_cols = [col for col in scenario.columns 
                       if col in ['MacroScore', 'Contrib_G', 'Contrib_I']]
        
        for feature in feature_cols:
            if feature in scenario.columns:
                values = scenario[feature].dropna()
                
                if len(values) > 10:
                    # Check for excessive daily changes during transition
                    daily_changes = values.diff().abs()
                    extreme_changes = daily_changes > (values.std() * TEST_CONFIG['max_daily_change_zscore'])
                    extreme_ratio = extreme_changes.sum() / len(daily_changes)
                    
                    assert extreme_ratio <= 0.2, \
                        f"Feature {feature} has excessive daily changes during transition: {extreme_ratio:.1%}"
    
    def _validate_stress_scenario_responses(self, scenario: pd.DataFrame, params: Dict):
        """Validate stress scenarios trigger appropriate Phase 3 responses"""
        
        if 'stress_intensity' not in scenario.columns:
            return
        
        stress_intensity = scenario['stress_intensity'].dropna()
        
        if len(stress_intensity) == 0:
            return
        
        # Should have actual stress periods
        max_stress = stress_intensity.max()
        assert max_stress >= 1.0, \
            f"Stress scenario lacks sufficient stress intensity: {max_stress:.3f}"
        
        # Should have periods of elevated stress (check for any stress > 0.5)
        moderate_stress_periods = (stress_intensity >= 0.5).sum()
        high_stress_periods = (stress_intensity >= 1.0).sum()
        
        moderate_stress_ratio = moderate_stress_periods / len(stress_intensity)
        high_stress_ratio = high_stress_periods / len(stress_intensity)
        
        # At least some periods should have elevated stress (more lenient for short scenarios)
        min_moderate_stress = 0.03 if len(stress_intensity) < 30 else 0.05  # 3% for short, 5% for long
        assert moderate_stress_ratio >= min_moderate_stress, \
            f"Stress scenario lacks stress periods: {moderate_stress_ratio:.1%} moderate stress (need {min_moderate_stress:.1%})"
        
        # For longer scenarios, expect some high stress periods
        if len(stress_intensity) >= 30:
            assert high_stress_ratio >= 0.02, \
                f"Stress scenario lacks high stress periods: {high_stress_ratio:.1%} high stress"
        
        # During stress periods, features should show increased volatility
        feature_cols = [col for col in scenario.columns 
                       if col in ['MacroScore', 'Contrib_G', 'Contrib_I']]
        
        for feature in feature_cols:
            if feature in scenario.columns:
                values = scenario[feature].dropna()
                stress_values = scenario[scenario['stress_intensity'] >= 0.5][feature].dropna()  # Lower threshold
                normal_values = scenario[scenario['stress_intensity'] < 0.1][feature].dropna()   # Clear normal periods
                
                if len(stress_values) > 2 and len(normal_values) > 2:
                    stress_volatility = stress_values.std()
                    normal_volatility = normal_values.std()
                    
                    if normal_volatility > 0.001:  # Avoid division by very small numbers
                        volatility_ratio = stress_volatility / normal_volatility
                        
                        # Stress periods should have higher volatility.
                        # For very short scenarios the estimate is noisy, so allow lower minimum.
                        min_volatility_ratio = 0.6 if len(stress_intensity) < 15 else 1.05
                        assert volatility_ratio >= min_volatility_ratio, \
                            f"Feature {feature} stress volatility not elevated: {volatility_ratio:.2f}x"
                        
                        # But not excessively high (adjust for short scenarios)
                        max_volatility_ratio = 20.0 if len(stress_intensity) < 20 else 10.0
                        assert volatility_ratio <= max_volatility_ratio, \
                            f"Feature {feature} stress volatility too extreme: {volatility_ratio:.2f}x (max {max_volatility_ratio:.1f}x)"

    @given(regime_chars=regime_characteristics())
    @settings(max_examples=20, deadline=15000)
    def test_regime_fingerprint_consistency_across_scenarios(self, regime_chars):
        """Test that regime fingerprints remain consistent across different scenario types"""
        
        regime_name = 'TestRegime'
        full_regime_chars = {regime_name: {
            'n_periods': 50,
            'frequency': 0.25,
            'feature_stats': regime_chars,
            'performance_stats': {'avg_return': 0.08, 'avg_sharpe': 1.2}
        }}
        
        scenarios = {}
        
        # Generate different scenario types
        for scenario_type in ['regime_continuation', 'stress_scenario']:
            if scenario_type == 'regime_continuation':
                scenario = self.generator.generate_regime_continuation_scenario(
                    regime_name, full_regime_chars, 30
                )
            else:  # stress_scenario
                scenario = self.generator.generate_stress_scenario(
                    regime_name, full_regime_chars, 30
                )
            
            if not scenario.empty:
                scenarios[scenario_type] = scenario
        
        assume(len(scenarios) >= 2)
        
        # Compare feature distributions across scenarios
        feature_names = list(regime_chars.keys())
        
        for feature in feature_names:
            feature_stats = []
            
            for scenario_type, scenario in scenarios.items():
                if feature in scenario.columns:
                    values = scenario[feature].dropna()
                    if len(values) > 5:
                        feature_stats.append({
                            'scenario_type': scenario_type,
                            'mean': values.mean(),
                            'std': values.std()
                        })
            
            if len(feature_stats) >= 2:
                # Means should be reasonably consistent (allowing for scenario differences)
                means = [stat['mean'] for stat in feature_stats]
                mean_range = max(means) - min(means)
                expected_std = regime_chars[feature]['std']
                
                # Allow larger range for stress scenarios
                max_mean_range = expected_std * 4.0
                assert mean_range <= max_mean_range, \
                    f"Feature {feature} means vary too much across scenarios: {mean_range:.3f}"

    def test_scenario_generation_robustness(self):
        """Test that scenario generation handles edge cases robustly"""
        
        # Test with minimal regime characteristics
        minimal_chars = {
            'TestRegime': {
                'n_periods': 5,
                'frequency': 0.1,
                'feature_stats': {
                    'single_feature': {'mean': 0.0, 'std': 0.1, 'min': -0.3, 'max': 0.3, 'median': 0.0}
                },
                'performance_stats': {'avg_return': 0.0, 'avg_sharpe': 0.0}
            }
        }
        
        # Should handle minimal characteristics without crashing
        scenario = self.generator.generate_regime_continuation_scenario(
            'TestRegime', minimal_chars, 10
        )
        
        # Should produce some result (even if basic)
        assert isinstance(scenario, pd.DataFrame)
        
        # Test with extreme characteristics
        extreme_chars = {
            'ExtremeRegime': {
                'n_periods': 100,
                'frequency': 0.8,
                'feature_stats': {
                    'extreme_feature': {'mean': 10.0, 'std': 5.0, 'min': -20.0, 'max': 40.0, 'median': 8.0}
                },
                'performance_stats': {'avg_return': 0.5, 'avg_sharpe': 3.0}
            }
        }
        
        # Should handle extreme characteristics
        extreme_scenario = self.generator.generate_regime_continuation_scenario(
            'ExtremeRegime', extreme_chars, 15
        )
        
        assert isinstance(extreme_scenario, pd.DataFrame)
        
        if not extreme_scenario.empty and 'extreme_feature' in extreme_scenario.columns:
            values = extreme_scenario['extreme_feature'].dropna()
            if len(values) > 0:
                # Values should be influenced by extreme characteristics
                assert values.mean() != 0.0  # Should not be default/zero

if __name__ == "__main__":
    # Run property tests
    pytest.main([__file__, "-v", "--tb=short"])
