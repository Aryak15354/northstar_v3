"""
Property Tests for Reality Consistency Validation Accuracy

**Property 6: Reality Consistency Validation Accuracy**
**Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5, 4.6**

Tests that Phase 3 reality consistency validation correctly verifies:
- Phase 3 regime classifications match historical patterns
- Simulated tailwind patterns match historical distributions  
- NO_EDGE triggers occur at appropriate frequencies
- Anticipatory signals maintain proper lead-lag relationships
- Regime similarity calculations remain stable
- Detailed diagnostics are provided when inconsistencies are detected
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from hypothesis import given, strategies as st, settings, assume, HealthCheck
from typing import Dict, List, Tuple, Any
import logging

from src.validation.phase3_reality_validator import (
    Phase3RealityValidator,
    Phase3RealityValidationResult,
    RegimeConsistencyResult,
    TailwindConsistencyResult,
    NoEdgeConsistencyResult,
    AnticipatoryConsistencyResult
)

logger = logging.getLogger(__name__)

# Test data generation strategies
@st.composite
def regime_classification_strategy(draw):
    """Generate regime classification data"""
    regimes = ['bull_market', 'bear_market', 'sideways', 'volatile', 'calm']
    length = draw(st.integers(min_value=50, max_value=500))
    
    # Generate regime sequence with realistic transitions
    regime_sequence = []
    current_regime = draw(st.sampled_from(regimes))
    
    for _ in range(length):
        # 90% chance to stay in same regime, 10% chance to transition
        if draw(st.floats(min_value=0, max_value=1)) < 0.9:
            regime_sequence.append(current_regime)
        else:
            current_regime = draw(st.sampled_from(regimes))
            regime_sequence.append(current_regime)
    
    dates = pd.date_range(start='2020-01-01', periods=length, freq='D')
    return pd.Series(regime_sequence, index=dates, name='regime_classification')

@st.composite
def regime_similarity_strategy(draw):
    """Generate regime similarity scores"""
    length = draw(st.integers(min_value=50, max_value=500))
    
    # Generate similarity scores with realistic patterns
    base_similarity = draw(st.floats(min_value=0.3, max_value=0.9))
    noise_level = draw(st.floats(min_value=0.01, max_value=0.1))
    
    similarities = []
    for _ in range(length):
        noise = draw(st.floats(min_value=-noise_level, max_value=noise_level))
        similarity = np.clip(base_similarity + noise, 0.0, 1.0)
        similarities.append(similarity)
    
    dates = pd.date_range(start='2020-01-01', periods=length, freq='D')
    return pd.Series(similarities, index=dates, name='regime_similarity_score')

@st.composite
def tailwind_data_strategy(draw):
    """Generate tailwind data"""
    length = draw(st.integers(min_value=50, max_value=500))
    n_strategies = draw(st.integers(min_value=2, max_value=5))
    
    dates = pd.date_range(start='2020-01-01', periods=length, freq='D')
    tailwind_data = {}
    
    for i in range(n_strategies):
        strategy_name = f'strategy_{i}_tailwind'
        
        # Generate tailwind with persistence and mean reversion
        base_tailwind = draw(st.floats(min_value=-0.5, max_value=0.5))
        persistence = draw(st.floats(min_value=0.7, max_value=0.95))
        volatility = draw(st.floats(min_value=0.05, max_value=0.2))
        
        tailwinds = [base_tailwind]
        for _ in range(length - 1):
            shock = draw(st.floats(min_value=-2*volatility, max_value=2*volatility))
            new_tailwind = persistence * tailwinds[-1] + (1 - persistence) * base_tailwind + shock
            tailwinds.append(np.clip(new_tailwind, -1.0, 1.0))
        
        tailwind_data[strategy_name] = tailwinds
    
    return pd.DataFrame(tailwind_data, index=dates)

@st.composite
def no_edge_state_strategy(draw):
    """Generate NO_EDGE state data"""
    length = draw(st.integers(min_value=50, max_value=500))
    
    # Generate NO_EDGE states with realistic patterns
    no_edge_frequency = draw(st.floats(min_value=0.05, max_value=0.25))
    min_duration = draw(st.integers(min_value=1, max_value=5))
    max_duration = draw(st.integers(min_value=min_duration, max_value=20))
    
    no_edge_states = []
    in_no_edge = False
    remaining_duration = 0
    
    for _ in range(length):
        if in_no_edge:
            no_edge_states.append(True)
            remaining_duration -= 1
            if remaining_duration <= 0:
                in_no_edge = False
        else:
            if draw(st.floats(min_value=0, max_value=1)) < no_edge_frequency:
                in_no_edge = True
                remaining_duration = draw(st.integers(min_value=min_duration, max_value=max_duration))
                no_edge_states.append(True)
            else:
                no_edge_states.append(False)
    
    dates = pd.date_range(start='2020-01-01', periods=length, freq='D')
    return pd.Series(no_edge_states, index=dates, name='no_edge_state')

@st.composite
def no_edge_reasons_strategy(draw, no_edge_states):
    """Generate NO_EDGE trigger reasons"""
    reasons = ['high_volatility', 'regime_uncertainty', 'correlation_breakdown', 'liquidity_stress']
    
    no_edge_reasons = []
    for state in no_edge_states:
        if state:
            reason = draw(st.sampled_from(reasons))
            no_edge_reasons.append(reason)
        else:
            no_edge_reasons.append(None)
    
    return pd.Series(no_edge_reasons, index=no_edge_states.index, name='no_edge_reasons')

@st.composite
def anticipatory_signals_strategy(draw):
    """Generate anticipatory signal data"""
    length = draw(st.integers(min_value=50, max_value=500))
    n_signals = draw(st.integers(min_value=2, max_value=4))
    
    dates = pd.date_range(start='2020-01-01', periods=length, freq='D')
    signal_data = {}
    
    for i in range(n_signals):
        signal_name = f'anticipatory_signal_{i}'
        
        # Generate signals with lead-lag patterns
        signal_frequency = draw(st.floats(min_value=0.1, max_value=0.4))
        signal_strength = draw(st.floats(min_value=0.1, max_value=1.0))
        
        signals = []
        for _ in range(length):
            if draw(st.floats(min_value=0, max_value=1)) < signal_frequency:
                strength = draw(st.floats(min_value=-signal_strength, max_value=signal_strength))
                signals.append(strength)
            else:
                signals.append(0.0)
        
        signal_data[signal_name] = signals
    
    return pd.DataFrame(signal_data, index=dates)

@st.composite
def market_data_strategy(draw):
    """Generate complete market data with Phase 3 components - simplified version"""
    # Use much smaller data sizes to avoid timeout
    length = draw(st.integers(min_value=20, max_value=50))  # Much smaller
    
    dates = pd.date_range(start='2020-01-01', periods=length, freq='D')
    data = pd.DataFrame(index=dates)
    
    # Simple regime classification
    regimes = ['bull_market', 'bear_market', 'sideways']
    data['regime_classification'] = draw(st.lists(
        st.sampled_from(regimes), 
        min_size=length, 
        max_size=length
    ))
    
    # Simple similarity scores
    data['regime_similarity_score'] = draw(st.lists(
        st.floats(min_value=0.3, max_value=0.9), 
        min_size=length, 
        max_size=length
    ))
    
    # Simple NO_EDGE states
    data['no_edge_state'] = draw(st.lists(
        st.booleans(), 
        min_size=length, 
        max_size=length
    ))
    
    # Simple NO_EDGE reasons
    data['no_edge_reasons'] = [''] * length
    
    # Simple tailwind data (just 2 strategies)
    for i in range(2):
        data[f'strategy_{i}_tailwind'] = draw(st.lists(
            st.floats(min_value=-0.5, max_value=0.5), 
            min_size=length, 
            max_size=length
        ))
    
    # Simple anticipatory signals (just 2 signals)
    for i in range(2):
        data[f'anticipatory_signal_{i}'] = draw(st.lists(
            st.floats(min_value=-1.0, max_value=1.0), 
            min_size=length, 
            max_size=length
        ))
    
    return data

@st.composite
def validation_period_strategy(draw):
    """Generate validation period"""
    start_date = draw(st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2023, 1, 1)))
    duration_days = draw(st.integers(min_value=30, max_value=365))
    end_date = start_date + timedelta(days=duration_days)
    
    return (start_date, end_date)

class TestRealityConsistencyValidationAccuracy:
    """Test suite for Property 6: Reality Consistency Validation Accuracy"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.validator = Phase3RealityValidator()
    
    @given(
        simulation_data=market_data_strategy(),
        historical_data=market_data_strategy(),
        validation_period=validation_period_strategy()
    )
    @settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.large_base_example, HealthCheck.data_too_large, HealthCheck.too_slow])
    def test_property_6_reality_consistency_validation_accuracy(
        self,
        simulation_data: pd.DataFrame,
        historical_data: pd.DataFrame,
        validation_period: Tuple[datetime, datetime]
    ):
        """
        Feature: shadow-reality, Property 6: Reality Consistency Validation Accuracy
        
        For any reality consistency check, the validation should verify that Phase 3 
        regime classifications, tailwind patterns, NO_EDGE triggers, and anticipatory 
        signals maintain statistical consistency with historical patterns.
        """
        assume(len(simulation_data) >= 30)
        assume(len(historical_data) >= 30)
        
        # Execute reality consistency validation
        result = self.validator.validate_phase3_reality_consistency(
            simulation_data=simulation_data,
            historical_data=historical_data,
            validation_period=validation_period
        )
        
        # Verify validation result structure
        assert isinstance(result, Phase3RealityValidationResult)
        assert result.validation_timestamp is not None
        assert result.validation_period == validation_period
        
        # Verify regime consistency validation
        assert isinstance(result.regime_consistency, RegimeConsistencyResult)
        assert 0.0 <= result.regime_consistency.overall_consistency <= 1.0
        assert 0.0 <= result.regime_consistency.regime_frequency_match <= 1.0
        assert 0.0 <= result.regime_consistency.regime_duration_match <= 1.0
        assert 0.0 <= result.regime_consistency.regime_transition_match <= 1.0
        assert 0.0 <= result.regime_consistency.similarity_score_stability <= 1.0
        assert isinstance(result.regime_consistency.inconsistencies, list)
        
        # Verify tailwind consistency validation
        assert isinstance(result.tailwind_consistency, TailwindConsistencyResult)
        assert 0.0 <= result.tailwind_consistency.overall_consistency <= 1.0
        assert 0.0 <= result.tailwind_consistency.distribution_match <= 1.0
        assert 0.0 <= result.tailwind_consistency.correlation_structure_match <= 1.0
        assert 0.0 <= result.tailwind_consistency.persistence_pattern_match <= 1.0
        assert 0.0 <= result.tailwind_consistency.regime_relationship_match <= 1.0
        assert isinstance(result.tailwind_consistency.inconsistencies, list)
        
        # Verify NO_EDGE consistency validation
        assert isinstance(result.no_edge_consistency, NoEdgeConsistencyResult)
        assert 0.0 <= result.no_edge_consistency.overall_consistency <= 1.0
        assert 0.0 <= result.no_edge_consistency.trigger_frequency_match <= 1.0
        assert 0.0 <= result.no_edge_consistency.trigger_duration_match <= 1.0
        assert 0.0 <= result.no_edge_consistency.trigger_condition_match <= 1.0
        assert 0.0 <= result.no_edge_consistency.recovery_pattern_match <= 1.0
        assert isinstance(result.no_edge_consistency.inconsistencies, list)
        
        # Verify anticipatory consistency validation
        assert isinstance(result.anticipatory_consistency, AnticipatoryConsistencyResult)
        assert 0.0 <= result.anticipatory_consistency.overall_consistency <= 1.0
        assert 0.0 <= result.anticipatory_consistency.signal_timing_match <= 1.0
        assert 0.0 <= result.anticipatory_consistency.lead_lag_relationship_match <= 1.0
        assert 0.0 <= result.anticipatory_consistency.signal_strength_match <= 1.0
        assert 0.0 <= result.anticipatory_consistency.accuracy_pattern_match <= 1.0
        assert isinstance(result.anticipatory_consistency.inconsistencies, list)
        
        # Verify overall consistency calculation
        assert 0.0 <= result.overall_reality_consistency <= 1.0
        
        # Verify consistency is reasonable weighted average
        component_scores = [
            result.regime_consistency.overall_consistency,
            result.tailwind_consistency.overall_consistency,
            result.no_edge_consistency.overall_consistency,
            result.anticipatory_consistency.overall_consistency
        ]
        min_score = min(component_scores)
        max_score = max(component_scores)
        assert min_score <= result.overall_reality_consistency <= max_score
        
        # Verify critical inconsistencies are identified appropriately
        assert isinstance(result.critical_inconsistencies, list)
        
        # If overall consistency is low, should have critical inconsistencies
        if result.overall_reality_consistency < 0.70:
            assert len(result.critical_inconsistencies) > 0
        
        # Verify recommendations are provided
        assert isinstance(result.recommendations, list)
        assert len(result.recommendations) > 0
    
    @given(
        simulation_data=market_data_strategy(),
        historical_data=market_data_strategy()
    )
    @settings(max_examples=50, deadline=None)
    def test_regime_classification_consistency_detection(
        self,
        simulation_data: pd.DataFrame,
        historical_data: pd.DataFrame
    ):
        """Test that regime classification inconsistencies are properly detected"""
        assume(len(simulation_data) >= 30)
        assume(len(historical_data) >= 30)
        
        # Create deliberately inconsistent regime data
        inconsistent_sim_data = simulation_data.copy()
        if 'regime_classification' in inconsistent_sim_data.columns:
            # Make all regimes the same (highly inconsistent)
            inconsistent_sim_data['regime_classification'] = 'bull_market'
        
        validation_period = (datetime(2020, 1, 1), datetime(2020, 12, 31))
        
        result = self.validator.validate_phase3_reality_consistency(
            simulation_data=inconsistent_sim_data,
            historical_data=historical_data,
            validation_period=validation_period
        )
        
        # Should detect regime inconsistency
        if 'regime_classification' in historical_data.columns:
            hist_regimes = historical_data['regime_classification'].value_counts()
            if len(hist_regimes) > 1:  # Historical data has multiple regimes
                assert result.regime_consistency.regime_frequency_match < 0.9
                assert len(result.regime_consistency.inconsistencies) > 0
    
    @given(
        simulation_data=market_data_strategy(),
        historical_data=market_data_strategy()
    )
    @settings(max_examples=50, deadline=None)
    def test_no_edge_frequency_consistency_detection(
        self,
        simulation_data: pd.DataFrame,
        historical_data: pd.DataFrame
    ):
        """Test that NO_EDGE frequency inconsistencies are properly detected"""
        assume(len(simulation_data) >= 30)
        assume(len(historical_data) >= 30)
        
        # Create deliberately inconsistent NO_EDGE frequency
        inconsistent_sim_data = simulation_data.copy()
        if 'no_edge_state' in inconsistent_sim_data.columns:
            # Make NO_EDGE state always True (highly inconsistent)
            inconsistent_sim_data['no_edge_state'] = True
        
        validation_period = (datetime(2020, 1, 1), datetime(2020, 12, 31))
        
        result = self.validator.validate_phase3_reality_consistency(
            simulation_data=inconsistent_sim_data,
            historical_data=historical_data,
            validation_period=validation_period
        )
        
        # Should detect NO_EDGE frequency inconsistency
        if 'no_edge_state' in historical_data.columns:
            hist_frequency = historical_data['no_edge_state'].mean()
            if hist_frequency < 0.8:  # Historical frequency is reasonable
                assert result.no_edge_consistency.trigger_frequency_match < 0.5
                assert len(result.no_edge_consistency.inconsistencies) > 0
    
    @given(
        simulation_data=market_data_strategy(),
        historical_data=market_data_strategy()
    )
    @settings(max_examples=50, deadline=None)
    def test_tailwind_distribution_consistency_detection(
        self,
        simulation_data: pd.DataFrame,
        historical_data: pd.DataFrame
    ):
        """Test that tailwind distribution inconsistencies are properly detected"""
        assume(len(simulation_data) >= 30)
        assume(len(historical_data) >= 30)
        
        # Create deliberately inconsistent tailwind distributions
        inconsistent_sim_data = simulation_data.copy()
        tailwind_cols = [col for col in inconsistent_sim_data.columns if 'tailwind' in col.lower()]
        
        if tailwind_cols:
            # Make all tailwinds extremely positive (inconsistent with typical distributions)
            for col in tailwind_cols:
                inconsistent_sim_data[col] = 0.9
        
        validation_period = (datetime(2020, 1, 1), datetime(2020, 12, 31))
        
        result = self.validator.validate_phase3_reality_consistency(
            simulation_data=inconsistent_sim_data,
            historical_data=historical_data,
            validation_period=validation_period
        )
        
        # Should detect tailwind distribution inconsistency
        if tailwind_cols:
            hist_tailwind_cols = [col for col in historical_data.columns if 'tailwind' in col.lower()]
            if hist_tailwind_cols:
                # Check if historical tailwinds have reasonable variance
                hist_variance = historical_data[hist_tailwind_cols].var().mean()
                if hist_variance > 0.01:  # Historical data has reasonable variance
                    assert result.tailwind_consistency.distribution_match < 0.8
    
    @given(
        simulation_data=market_data_strategy(),
        historical_data=market_data_strategy()
    )
    @settings(max_examples=50, deadline=None)
    def test_anticipatory_signal_consistency_detection(
        self,
        simulation_data: pd.DataFrame,
        historical_data: pd.DataFrame
    ):
        """Test that anticipatory signal inconsistencies are properly detected"""
        assume(len(simulation_data) >= 30)
        assume(len(historical_data) >= 30)
        
        # Create deliberately inconsistent anticipatory signals
        inconsistent_sim_data = simulation_data.copy()
        signal_cols = [col for col in inconsistent_sim_data.columns if 'anticipatory' in col.lower()]
        
        if signal_cols:
            # Make all signals zero (no anticipatory activity)
            for col in signal_cols:
                inconsistent_sim_data[col] = 0.0
        
        validation_period = (datetime(2020, 1, 1), datetime(2020, 12, 31))
        
        result = self.validator.validate_phase3_reality_consistency(
            simulation_data=inconsistent_sim_data,
            historical_data=historical_data,
            validation_period=validation_period
        )
        
        # Should detect anticipatory signal inconsistency
        if signal_cols:
            hist_signal_cols = [col for col in historical_data.columns if 'anticipatory' in col.lower()]
            if hist_signal_cols:
                # Check if historical signals have activity
                hist_activity = (historical_data[hist_signal_cols] != 0).mean().mean()
                if hist_activity > 0.1:  # Historical data has signal activity
                    assert result.anticipatory_consistency.signal_timing_match < 0.8
    
    @given(market_data=market_data_strategy())
    @settings(max_examples=50, deadline=None)
    def test_identical_data_perfect_consistency(self, market_data: pd.DataFrame):
        """Test that identical simulation and historical data yield perfect consistency"""
        assume(len(market_data) >= 30)
        
        validation_period = (datetime(2020, 1, 1), datetime(2020, 12, 31))
        
        # Use identical data for simulation and historical
        result = self.validator.validate_phase3_reality_consistency(
            simulation_data=market_data,
            historical_data=market_data,
            validation_period=validation_period
        )
        
        # Should achieve high consistency scores
        assert result.overall_reality_consistency >= 0.8
        
        # Individual components should have high consistency
        if 'regime_classification' in market_data.columns:
            assert result.regime_consistency.regime_frequency_match >= 0.9
        
        if any('tailwind' in col.lower() for col in market_data.columns):
            assert result.tailwind_consistency.distribution_match >= 0.8
        
        if 'no_edge_state' in market_data.columns:
            assert result.no_edge_consistency.trigger_frequency_match >= 0.9
        
        if any('anticipatory' in col.lower() for col in market_data.columns):
            assert result.anticipatory_consistency.signal_timing_match >= 0.8
    
    @given(
        simulation_data=market_data_strategy(),
        historical_data=market_data_strategy()
    )
    @settings(max_examples=50, deadline=None)
    def test_missing_data_handling(
        self,
        simulation_data: pd.DataFrame,
        historical_data: pd.DataFrame
    ):
        """Test proper handling of missing Phase 3 component data"""
        assume(len(simulation_data) >= 30)
        assume(len(historical_data) >= 30)
        
        # Remove some Phase 3 components
        incomplete_sim_data = simulation_data.copy()
        incomplete_hist_data = historical_data.copy()
        
        # Remove regime data
        if 'regime_classification' in incomplete_sim_data.columns:
            incomplete_sim_data = incomplete_sim_data.drop('regime_classification', axis=1)
        if 'regime_classification' in incomplete_hist_data.columns:
            incomplete_hist_data = incomplete_hist_data.drop('regime_classification', axis=1)
        
        validation_period = (datetime(2020, 1, 1), datetime(2020, 12, 31))
        
        result = self.validator.validate_phase3_reality_consistency(
            simulation_data=incomplete_sim_data,
            historical_data=incomplete_hist_data,
            validation_period=validation_period
        )
        
        # Should handle missing data gracefully
        assert isinstance(result, Phase3RealityValidationResult)
        assert result.overall_reality_consistency >= 0.0
        
        # Should report missing data in inconsistencies
        assert len(result.regime_consistency.inconsistencies) > 0
        assert any('missing' in inconsistency.lower() for inconsistency in result.regime_consistency.inconsistencies)
    
    @given(
        simulation_data=market_data_strategy(),
        historical_data=market_data_strategy()
    )
    @settings(max_examples=50, deadline=None)
    def test_validation_determinism(
        self,
        simulation_data: pd.DataFrame,
        historical_data: pd.DataFrame
    ):
        """Test that validation results are deterministic for same inputs"""
        assume(len(simulation_data) >= 30)
        assume(len(historical_data) >= 30)
        
        validation_period = (datetime(2020, 1, 1), datetime(2020, 12, 31))
        
        # Run validation twice with same inputs
        result1 = self.validator.validate_phase3_reality_consistency(
            simulation_data=simulation_data,
            historical_data=historical_data,
            validation_period=validation_period
        )
        
        result2 = self.validator.validate_phase3_reality_consistency(
            simulation_data=simulation_data,
            historical_data=historical_data,
            validation_period=validation_period
        )
        
        # Results should be identical (excluding timestamps)
        assert result1.overall_reality_consistency == result2.overall_reality_consistency
        assert result1.regime_consistency.overall_consistency == result2.regime_consistency.overall_consistency
        assert result1.tailwind_consistency.overall_consistency == result2.tailwind_consistency.overall_consistency
        assert result1.no_edge_consistency.overall_consistency == result2.no_edge_consistency.overall_consistency
        assert result1.anticipatory_consistency.overall_consistency == result2.anticipatory_consistency.overall_consistency
    
    @given(
        simulation_data=market_data_strategy(),
        historical_data=market_data_strategy()
    )
    @settings(max_examples=50, deadline=None)
    def test_consistency_score_bounds(
        self,
        simulation_data: pd.DataFrame,
        historical_data: pd.DataFrame
    ):
        """Test that all consistency scores are properly bounded between 0 and 1"""
        assume(len(simulation_data) >= 30)
        assume(len(historical_data) >= 30)
        
        validation_period = (datetime(2020, 1, 1), datetime(2020, 12, 31))
        
        result = self.validator.validate_phase3_reality_consistency(
            simulation_data=simulation_data,
            historical_data=historical_data,
            validation_period=validation_period
        )
        
        # Check all consistency scores are bounded
        def check_bounds(score: float, name: str):
            assert 0.0 <= score <= 1.0, f"{name} score {score} is out of bounds [0, 1]"
        
        # Overall consistency
        check_bounds(result.overall_reality_consistency, "Overall reality consistency")
        
        # Regime consistency scores
        check_bounds(result.regime_consistency.overall_consistency, "Regime overall consistency")
        check_bounds(result.regime_consistency.regime_frequency_match, "Regime frequency match")
        check_bounds(result.regime_consistency.regime_duration_match, "Regime duration match")
        check_bounds(result.regime_consistency.regime_transition_match, "Regime transition match")
        check_bounds(result.regime_consistency.similarity_score_stability, "Similarity score stability")
        
        # Tailwind consistency scores
        check_bounds(result.tailwind_consistency.overall_consistency, "Tailwind overall consistency")
        check_bounds(result.tailwind_consistency.distribution_match, "Tailwind distribution match")
        check_bounds(result.tailwind_consistency.correlation_structure_match, "Tailwind correlation match")
        check_bounds(result.tailwind_consistency.persistence_pattern_match, "Tailwind persistence match")
        check_bounds(result.tailwind_consistency.regime_relationship_match, "Tailwind regime relationship match")
        
        # NO_EDGE consistency scores
        check_bounds(result.no_edge_consistency.overall_consistency, "NO_EDGE overall consistency")
        check_bounds(result.no_edge_consistency.trigger_frequency_match, "NO_EDGE frequency match")
        check_bounds(result.no_edge_consistency.trigger_duration_match, "NO_EDGE duration match")
        check_bounds(result.no_edge_consistency.trigger_condition_match, "NO_EDGE condition match")
        check_bounds(result.no_edge_consistency.recovery_pattern_match, "NO_EDGE recovery match")
        
        # Anticipatory consistency scores
        check_bounds(result.anticipatory_consistency.overall_consistency, "Anticipatory overall consistency")
        check_bounds(result.anticipatory_consistency.signal_timing_match, "Anticipatory timing match")
        check_bounds(result.anticipatory_consistency.lead_lag_relationship_match, "Anticipatory lead-lag match")
        check_bounds(result.anticipatory_consistency.signal_strength_match, "Anticipatory strength match")
        check_bounds(result.anticipatory_consistency.accuracy_pattern_match, "Anticipatory accuracy match")
    
    @given(
        simulation_data=market_data_strategy(),
        historical_data=market_data_strategy()
    )
    @settings(max_examples=50, deadline=None)
    def test_diagnostic_completeness(
        self,
        simulation_data: pd.DataFrame,
        historical_data: pd.DataFrame
    ):
        """Test that detailed diagnostics are provided when inconsistencies are detected"""
        assume(len(simulation_data) >= 30)
        assume(len(historical_data) >= 30)
        
        validation_period = (datetime(2020, 1, 1), datetime(2020, 12, 31))
        
        result = self.validator.validate_phase3_reality_consistency(
            simulation_data=simulation_data,
            historical_data=historical_data,
            validation_period=validation_period
        )
        
        # If overall consistency is low, should have detailed diagnostics
        if result.overall_reality_consistency < 0.70:
            # Should have critical inconsistencies identified
            assert len(result.critical_inconsistencies) > 0
            
            # Should have specific recommendations
            assert len(result.recommendations) > 0
            
            # At least one component should have inconsistencies reported
            total_inconsistencies = (
                len(result.regime_consistency.inconsistencies) +
                len(result.tailwind_consistency.inconsistencies) +
                len(result.no_edge_consistency.inconsistencies) +
                len(result.anticipatory_consistency.inconsistencies)
            )
            assert total_inconsistencies > 0
        
        # Recommendations should always be provided
        assert len(result.recommendations) > 0
        
        # All recommendation strings should be non-empty
        for recommendation in result.recommendations:
            assert isinstance(recommendation, str)
            assert len(recommendation.strip()) > 0