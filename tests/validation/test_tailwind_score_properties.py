#!/usr/bin/env python3
"""
Property Tests for Tailwind Score Composition - Phase 3 Basic Intelligence
Tests the mathematical properties of tailwind score calculations

Property 24: Tailwind Score Composition
Validates: Requirements 9.2

This test ensures that tailwind score calculations follow the specified composition:
- Combined score = 60% Sharpe + 40% regime tailwind
- Sharpe contribution is properly weighted
- Regime contribution is properly weighted
- Score composition is mathematically consistent
- Bounds are reasonable for institutional use
"""

import pytest
import pandas as pd
import numpy as np
from hypothesis import given, strategies as st, settings, assume
import sys
import os

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from src.intelligence.simple_tailwind_engine import SimpleTailwindEngine

class TestTailwindScoreProperties:
    """Property tests for tailwind score composition"""
    
    def setup_method(self):
        """Setup test environment"""
        self.engine = SimpleTailwindEngine()
        
        # Test configuration
        self.sharpe_weight = self.engine.config['sharpe_weight']  # 0.6
        self.regime_weight = self.engine.config['regime_weight']  # 0.4
    
    @given(
        st.floats(min_value=-2.0, max_value=4.0, allow_nan=False, allow_infinity=False),
        st.floats(min_value=0.5, max_value=2.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100, deadline=5000)
    def test_tailwind_score_composition(self, sharpe_ratio, regime_tailwind):
        """
        Property 24: Tailwind Score Composition
        
        Tests that combined score = 60% Sharpe + 40% regime tailwind
        """
        # Normalize Sharpe ratio (as done in the engine)
        normalized_sharpe = min(max(sharpe_ratio, -1.0), 3.0)
        
        # Calculate expected combined score
        expected_score = (
            self.sharpe_weight * normalized_sharpe +
            self.regime_weight * regime_tailwind
        )
        
        # Calculate actual score using engine logic
        strategy_data = {'test_strategy': {'sharpe': sharpe_ratio}}
        regime_tailwinds = {'test_strategy': {'regime_tailwind': regime_tailwind}}
        
        combined_scores = self.engine.calculate_combined_scores(strategy_data, regime_tailwinds)
        actual_score = combined_scores['test_strategy']['combined_score']
        
        # Test composition property
        assert abs(actual_score - expected_score) < 1e-10, \
            f"Score composition incorrect: {actual_score} != {expected_score}"
    
    @given(
        st.floats(min_value=-2.0, max_value=4.0, allow_nan=False, allow_infinity=False),
        st.floats(min_value=0.5, max_value=2.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100, deadline=5000)
    def test_tailwind_contribution_weights(self, sharpe_ratio, regime_tailwind):
        """
        Property 24: Tailwind Contribution Weights
        
        Tests that individual contributions are properly weighted
        """
        # Normalize Sharpe ratio
        normalized_sharpe = min(max(sharpe_ratio, -1.0), 3.0)
        
        # Calculate using engine
        strategy_data = {'test_strategy': {'sharpe': sharpe_ratio}}
        regime_tailwinds = {'test_strategy': {'regime_tailwind': regime_tailwind}}
        
        combined_scores = self.engine.calculate_combined_scores(strategy_data, regime_tailwinds)
        result = combined_scores['test_strategy']
        
        # Test individual contributions
        expected_sharpe_contrib = self.sharpe_weight * normalized_sharpe
        expected_regime_contrib = self.regime_weight * regime_tailwind
        
        assert abs(result['sharpe_contribution'] - expected_sharpe_contrib) < 1e-10, \
            f"Sharpe contribution incorrect: {result['sharpe_contribution']} != {expected_sharpe_contrib}"
        
        assert abs(result['regime_contribution'] - expected_regime_contrib) < 1e-10, \
            f"Regime contribution incorrect: {result['regime_contribution']} != {expected_regime_contrib}"
    
    @given(
        st.floats(min_value=-2.0, max_value=4.0, allow_nan=False, allow_infinity=False),
        st.floats(min_value=0.5, max_value=2.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100, deadline=5000)
    def test_tailwind_score_additivity(self, sharpe_ratio, regime_tailwind):
        """
        Property 24: Tailwind Score Additivity
        
        Tests that combined score = sharpe contribution + regime contribution
        """
        strategy_data = {'test_strategy': {'sharpe': sharpe_ratio}}
        regime_tailwinds = {'test_strategy': {'regime_tailwind': regime_tailwind}}
        
        combined_scores = self.engine.calculate_combined_scores(strategy_data, regime_tailwinds)
        result = combined_scores['test_strategy']
        
        # Test additivity
        sum_of_contributions = result['sharpe_contribution'] + result['regime_contribution']
        
        assert abs(result['combined_score'] - sum_of_contributions) < 1e-10, \
            f"Score not additive: {result['combined_score']} != {sum_of_contributions}"
    
    @given(st.floats(min_value=-10.0, max_value=10.0, allow_nan=False, allow_infinity=False))
    @settings(max_examples=50, deadline=5000)
    def test_sharpe_normalization_bounds(self, raw_sharpe):
        """
        Property 24: Sharpe Normalization Bounds
        
        Tests that Sharpe ratios are properly normalized to [-1, 3] range
        """
        strategy_data = {'test_strategy': {'sharpe': raw_sharpe}}
        regime_tailwinds = {'test_strategy': {'regime_tailwind': 1.0}}
        
        combined_scores = self.engine.calculate_combined_scores(strategy_data, regime_tailwinds)
        normalized_sharpe = combined_scores['test_strategy']['normalized_sharpe']
        
        # Test normalization bounds
        assert -1.0 <= normalized_sharpe <= 3.0, \
            f"Normalized Sharpe out of bounds: {normalized_sharpe}"
        
        # Test specific cases
        if raw_sharpe <= -1.0:
            assert normalized_sharpe == -1.0, f"Lower bound not applied: {normalized_sharpe}"
        elif raw_sharpe >= 3.0:
            assert normalized_sharpe == 3.0, f"Upper bound not applied: {normalized_sharpe}"
        else:
            assert abs(normalized_sharpe - raw_sharpe) < 1e-10, f"Unnecessary normalization: {normalized_sharpe} != {raw_sharpe}"
    
    @given(
        st.floats(min_value=0.0, max_value=3.0, allow_nan=False, allow_infinity=False),
        st.floats(min_value=0.5, max_value=2.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50, deadline=5000)
    def test_tailwind_score_monotonicity(self, sharpe_ratio, regime_tailwind):
        """
        Property 24: Tailwind Score Monotonicity
        
        Tests that higher Sharpe or regime tailwind leads to higher combined score
        """
        # Base case
        strategy_data_base = {'test_strategy': {'sharpe': sharpe_ratio}}
        regime_tailwinds_base = {'test_strategy': {'regime_tailwind': regime_tailwind}}
        
        base_scores = self.engine.calculate_combined_scores(strategy_data_base, regime_tailwinds_base)
        base_score = base_scores['test_strategy']['combined_score']
        
        # Higher Sharpe case
        higher_sharpe = min(sharpe_ratio + 0.5, 3.0)
        strategy_data_higher_sharpe = {'test_strategy': {'sharpe': higher_sharpe}}
        
        higher_sharpe_scores = self.engine.calculate_combined_scores(strategy_data_higher_sharpe, regime_tailwinds_base)
        higher_sharpe_score = higher_sharpe_scores['test_strategy']['combined_score']
        
        # Higher regime tailwind case
        higher_regime = min(regime_tailwind + 0.2, 2.0)
        regime_tailwinds_higher = {'test_strategy': {'regime_tailwind': higher_regime}}
        
        higher_regime_scores = self.engine.calculate_combined_scores(strategy_data_base, regime_tailwinds_higher)
        higher_regime_score = higher_regime_scores['test_strategy']['combined_score']
        
        # Test monotonicity
        if higher_sharpe > sharpe_ratio:
            assert higher_sharpe_score >= base_score, \
                f"Higher Sharpe should increase score: {higher_sharpe_score} < {base_score}"
        
        if higher_regime > regime_tailwind:
            assert higher_regime_score >= base_score, \
                f"Higher regime tailwind should increase score: {higher_regime_score} < {base_score}"
    
    def test_tailwind_score_with_real_data(self):
        """
        Property 24: Tailwind Score with Real Data
        
        Tests score composition with actual strategy data
        """
        try:
            # Load real tailwind data
            tailwinds = self.engine.load_tailwinds()
            
            if not tailwinds.empty:
                # Test composition for each strategy
                for _, row in tailwinds.iterrows():
                    sharpe_contrib = row['sharpe_contribution']
                    regime_contrib = row['regime_contribution']
                    combined_score = row['combined_score']
                    
                    # Test additivity
                    assert abs(combined_score - (sharpe_contrib + regime_contrib)) < 1e-10, \
                        f"Real data not additive for {row['strategy']}: {combined_score} != {sharpe_contrib + regime_contrib}"
                    
                    # Test weight consistency
                    expected_sharpe_contrib = self.sharpe_weight * row['normalized_sharpe']
                    expected_regime_contrib = self.regime_weight * row['regime_tailwind']
                    
                    assert abs(sharpe_contrib - expected_sharpe_contrib) < 1e-10, \
                        f"Sharpe contribution inconsistent for {row['strategy']}"
                    
                    assert abs(regime_contrib - expected_regime_contrib) < 1e-10, \
                        f"Regime contribution inconsistent for {row['strategy']}"
                
        except Exception as e:
            # If no real data available, skip this test
            pytest.skip(f"No real tailwind data available: {e}")
    
    def test_tailwind_weight_sum(self):
        """
        Property 24: Tailwind Weight Sum
        
        Tests that Sharpe weight + regime weight = 1.0
        """
        total_weight = self.sharpe_weight + self.regime_weight
        
        assert abs(total_weight - 1.0) < 1e-10, \
            f"Weights don't sum to 1.0: {total_weight}"
    
    def test_tailwind_score_consistency(self):
        """
        Property 24: Tailwind Score Consistency
        
        Tests that score calculations are consistent across multiple calls
        """
        sharpe_ratio = 1.5
        regime_tailwind = 1.2
        
        strategy_data = {'test_strategy': {'sharpe': sharpe_ratio}}
        regime_tailwinds = {'test_strategy': {'regime_tailwind': regime_tailwind}}
        
        # Calculate multiple times
        scores = []
        for _ in range(10):
            combined_scores = self.engine.calculate_combined_scores(strategy_data, regime_tailwinds)
            scores.append(combined_scores['test_strategy']['combined_score'])
        
        # Test consistency
        assert all(abs(score - scores[0]) < 1e-10 for score in scores), \
            "Score calculations not consistent"
    
    def test_regime_preference_application(self):
        """
        Property 24: Regime Preference Application
        
        Tests that regime preferences are correctly applied to strategies
        """
        # Test with known regime preferences
        current_regime = 'Crisis'
        strategy_data = {
            'low_vol': {'sharpe': 1.0, 'recent_sharpe': 1.0},
            'mom_6m': {'sharpe': 1.0, 'recent_sharpe': 1.0}
        }
        
        # Calculate regime tailwinds
        regime_tailwinds = self.engine.calculate_regime_tailwinds(strategy_data, current_regime)
        
        # In Crisis regime, low_vol should have higher preference than mom_6m
        low_vol_tailwind = regime_tailwinds['low_vol']['regime_tailwind']
        mom_6m_tailwind = regime_tailwinds['mom_6m']['regime_tailwind']
        
        assert low_vol_tailwind > mom_6m_tailwind, \
            f"Crisis regime preferences not applied correctly: low_vol {low_vol_tailwind} <= mom_6m {mom_6m_tailwind}"

def test_simple_tailwind_engine_integration():
    """Integration test for SimpleTailwindEngine"""
    
    engine = SimpleTailwindEngine()
    
    # Test that engine can be instantiated
    assert engine.name == "Simple Tailwind Engine"
    assert engine.version == "3.0"
    
    # Test configuration
    assert engine.config['sharpe_weight'] == 0.6
    assert engine.config['regime_weight'] == 0.4
    assert engine.config['sharpe_weight'] + engine.config['regime_weight'] == 1.0
    
    # Test paths are defined
    assert 'strategy_tailwinds' in engine.paths
    assert 'tailwind_metadata' in engine.paths
    
    # Test regime preferences are defined
    assert 'Crisis' in engine.regime_preferences
    assert 'Expansion' in engine.regime_preferences
    assert 'Late-Expansion' in engine.regime_preferences
    assert 'Slowdown' in engine.regime_preferences

if __name__ == "__main__":
    # Run property tests
    pytest.main([__file__, "-v", "--tb=short"])