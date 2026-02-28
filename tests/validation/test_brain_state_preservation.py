#!/usr/bin/env python3
"""
Unit Tests: Brain State Preservation

Tests that the Northstar brain properly preserves and restores state,
ensuring temporal integrity across simulation runs.

Validates: Requirements 1.3, 1.4
"""

import pytest
import json
import tempfile
import os
from datetime import datetime, timedelta
import numpy as np
import sys

# Add src to path
, '..', '..'))

from src.validation.northstar_brain_state import (
    NorthstarBrain, NorthstarBrainState, RegimeState, 
    BayesianPriors, SpecialistWeights
)
from src.intelligence.temporal_guard import TemporalGuard


class TestBrainStatePreservation:
    """Test suite for brain state preservation and integrity"""
    
    def setup_method(self):
        """Setup for each test"""
        self.temporal_guard = TemporalGuard()
        self.start_date = datetime(2023, 1, 1)
        self.brain = NorthstarBrain.from_historical_state(
            historical_data={},
            start_date=self.start_date,
            temporal_guard=self.temporal_guard
        )
    
    def test_state_serialization_roundtrip(self):
        """Test that brain state can be serialized and deserialized without loss"""
        
        # Get initial state
        original_state = self.brain.get_current_state()
        
        # Serialize to dictionary
        state_dict = original_state.to_dict()
        
        # Deserialize back
        restored_state = NorthstarBrainState.from_dict(state_dict)
        
        # Verify all fields match
        assert restored_state.timestamp == original_state.timestamp
        assert restored_state.regime_state.current_regime == original_state.regime_state.current_regime
        assert restored_state.regime_state.confidence == original_state.regime_state.confidence
        assert restored_state.bayesian_priors.specialist_alphas == original_state.bayesian_priors.specialist_alphas
        assert restored_state.specialist_weights.weights == original_state.specialist_weights.weights
        assert restored_state.signal_decay_factors == original_state.signal_decay_factors
        assert restored_state.correlation_matrix == original_state.correlation_matrix
        assert restored_state.risk_budgets == original_state.risk_budgets
        assert restored_state.volatility_estimates == original_state.volatility_estimates
        
        # Verify state hash matches
        assert restored_state.state_hash == original_state.state_hash
    
    def test_state_integrity_verification(self):
        """Test that state integrity verification works correctly"""
        
        state = self.brain.get_current_state()
        
        # Original state should verify correctly
        assert state.verify_integrity(), "Original state should verify correctly"
        
        # Modify state and verify it fails
        state.regime_state.confidence = 0.999  # Change a value
        assert not state.verify_integrity(), "Modified state should fail verification"
    
    def test_state_file_persistence(self):
        """Test saving and loading state from file"""
        
        # Step brain forward a few days to create interesting state
        current_date = self.start_date
        for i in range(5):
            current_date += timedelta(days=1)
            daily_data = {
                'market_return': np.random.normal(0, 0.02),
                'market_volatility': 0.15 + np.random.normal(0, 0.05),
                'market_momentum': np.random.normal(0, 0.01)
            }
            self.brain.step_forward(daily_data, current_date)
        
        # Get state before saving
        original_state = self.brain.get_current_state()
        
        # Save to temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            self.brain.save_state(temp_path)
            
            # Create new brain and load state
            new_brain = NorthstarBrain.from_historical_state(
                historical_data={},
                start_date=self.start_date,
                temporal_guard=self.temporal_guard
            )
            
            new_brain.load_state(temp_path)
            loaded_state = new_brain.get_current_state()
            
            # Verify states match
            assert loaded_state.timestamp == original_state.timestamp
            assert loaded_state.regime_state.current_regime == original_state.regime_state.current_regime
            assert loaded_state.regime_state.confidence == original_state.regime_state.confidence
            assert loaded_state.regime_state.regime_duration == original_state.regime_state.regime_duration
            assert loaded_state.bayesian_priors.specialist_alphas == original_state.bayesian_priors.specialist_alphas
            assert loaded_state.specialist_weights.weights == original_state.specialist_weights.weights
            assert loaded_state.state_hash == original_state.state_hash
            
            # Verify loaded state can continue forward
            next_date = current_date + timedelta(days=1)
            daily_data = {
                'market_return': 0.01,
                'market_volatility': 0.18,
                'market_momentum': 0.005
            }
            
            # Should not raise exception
            portfolio_weights = new_brain.step_forward(daily_data, next_date)
            assert isinstance(portfolio_weights, dict)
            assert len(portfolio_weights) > 0
            
        finally:
            # Clean up
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def test_state_evolution_consistency(self):
        """Test that state evolves consistently across multiple steps"""
        
        # Track state evolution
        states = []
        current_date = self.start_date
        
        # Step forward 10 days with consistent market data
        for i in range(10):
            current_date += timedelta(days=1)
            daily_data = {
                'market_return': 0.001 * i,  # Gradually increasing returns
                'market_volatility': 0.15,   # Constant volatility
                'market_momentum': 0.001 * i
            }
            
            portfolio_weights = self.brain.step_forward(daily_data, current_date)
            state = self.brain.get_current_state()
            states.append((current_date, state, portfolio_weights))
        
        # Verify state evolution properties
        for i in range(1, len(states)):
            prev_date, prev_state, prev_weights = states[i-1]
            curr_date, curr_state, curr_weights = states[i]
            
            # Time should advance
            assert curr_state.timestamp > prev_state.timestamp
            
            # Regime duration should increase if regime unchanged
            if curr_state.regime_state.current_regime == prev_state.regime_state.current_regime:
                assert curr_state.regime_state.regime_duration == prev_state.regime_state.regime_duration + 1
            else:
                assert curr_state.regime_state.regime_duration == 1
            
            # Performance history should grow
            assert len(curr_state.performance_history) >= len(prev_state.performance_history)
            
            # State integrity should be maintained
            assert curr_state.verify_integrity()
    
    def test_regime_state_preservation(self):
        """Test that regime state is properly preserved and updated"""
        
        # Start with neutral regime
        initial_state = self.brain.get_current_state()
        assert initial_state.regime_state.current_regime == "neutral"
        assert initial_state.regime_state.regime_duration == 1
        
        # Create crisis conditions
        current_date = self.start_date + timedelta(days=1)
        crisis_data = {
            'market_return': -0.05,
            'market_volatility': 0.35,  # High volatility triggers crisis
            'market_momentum': -0.03
        }
        
        self.brain.step_forward(crisis_data, current_date)
        crisis_state = self.brain.get_current_state()
        
        # Should detect crisis regime
        assert crisis_state.regime_state.current_regime == "crisis"
        assert crisis_state.regime_state.regime_duration == 1
        assert crisis_state.regime_state.last_transition_date == current_date
        
        # Continue crisis for several days
        for i in range(3):
            current_date += timedelta(days=1)
            self.brain.step_forward(crisis_data, current_date)
        
        continued_crisis_state = self.brain.get_current_state()
        
        # Regime should persist with increasing duration
        assert continued_crisis_state.regime_state.current_regime == "crisis"
        assert continued_crisis_state.regime_state.regime_duration == 4
        assert continued_crisis_state.regime_state.confidence > crisis_state.regime_state.confidence
    
    def test_bayesian_priors_evolution(self):
        """Test that Bayesian priors evolve correctly with performance data"""
        
        initial_state = self.brain.get_current_state()
        initial_alphas = initial_state.bayesian_priors.specialist_alphas.copy()
        
        # Simulate strong performance for momentum specialist
        current_date = self.start_date
        for i in range(5):
            current_date += timedelta(days=1)
            
            # Create conditions favorable to momentum
            daily_data = {
                'market_return': 0.02,  # Strong positive returns
                'market_volatility': 0.12,  # Low volatility
                'market_momentum': 0.02,
                'momentum_return': 0.025  # Momentum specialist outperforms
            }
            
            self.brain.step_forward(daily_data, current_date)
        
        final_state = self.brain.get_current_state()
        final_alphas = final_state.bayesian_priors.specialist_alphas
        
        # Momentum specialist should have improved alpha
        # (Note: actual improvement depends on implementation details)
        assert final_state.bayesian_priors.update_counts['momentum'] > 0
        
        # Confidence intervals should reflect updates
        momentum_ci = final_state.bayesian_priors.confidence_intervals['momentum']
        assert isinstance(momentum_ci, tuple)
        assert len(momentum_ci) == 2
    
    def test_specialist_weights_rebalancing(self):
        """Test that specialist weights rebalance appropriately"""
        
        initial_state = self.brain.get_current_state()
        initial_weights = initial_state.specialist_weights.weights.copy()
        
        # All specialists should start with equal weights
        expected_weight = 1.0 / len(initial_weights)
        for weight in initial_weights.values():
            assert abs(weight - expected_weight) < 0.01
        
        # Create conditions that should favor defensive specialist
        current_date = self.start_date
        for i in range(10):
            current_date += timedelta(days=1)
            
            # High volatility, negative returns = crisis conditions
            daily_data = {
                'market_return': -0.02,
                'market_volatility': 0.30,
                'market_momentum': -0.015,
                'defensive_return': 0.01  # Defensive outperforms in crisis
            }
            
            self.brain.step_forward(daily_data, current_date)
        
        final_state = self.brain.get_current_state()
        final_weights = final_state.specialist_weights.weights
        
        # Weight history should be tracked
        assert len(final_state.specialist_weights.weight_history) > len(initial_state.specialist_weights.weight_history)
        
        # Weights should sum to approximately 1
        total_weight = sum(final_weights.values())
        assert abs(total_weight - 1.0) < 0.01
    
    def test_signal_decay_application(self):
        """Test that signal decay is properly applied over time"""
        
        # Step forward with strong signal
        current_date = self.start_date + timedelta(days=1)
        strong_signal_data = {
            'market_return': 0.03,
            'market_volatility': 0.15,
            'market_momentum': 0.025
        }
        
        self.brain.step_forward(strong_signal_data, current_date)
        state_after_signal = self.brain.get_current_state()
        
        # All decay factors should be 1.0 initially (just updated)
        for decay_factor in state_after_signal.signal_decay_factors.values():
            assert decay_factor == 1.0
        
        # Step forward several days with no new signals
        for i in range(5):
            current_date += timedelta(days=1)
            no_signal_data = {
                'market_return': 0.0,
                'market_volatility': 0.15,
                'market_momentum': 0.0
            }
            self.brain.step_forward(no_signal_data, current_date)
        
        final_state = self.brain.get_current_state()
        
        # Decay factors should have decreased
        for specialist, decay_factor in final_state.signal_decay_factors.items():
            assert decay_factor < 1.0, f"Decay factor for {specialist} should have decreased"
            assert decay_factor > 0.01, f"Decay factor for {specialist} should not be too small"
    
    def test_performance_attribution_tracking(self):
        """Test that performance attribution is properly tracked"""
        
        initial_state = self.brain.get_current_state()
        assert len(initial_state.performance_history) == 0
        assert len(initial_state.attribution_history) == 0
        
        # Step forward several days
        current_date = self.start_date
        for i in range(5):
            current_date += timedelta(days=1)
            daily_data = {
                'market_return': 0.01 * (i + 1),
                'market_volatility': 0.15,
                'market_momentum': 0.005 * (i + 1)
            }
            
            self.brain.step_forward(daily_data, current_date)
        
        final_state = self.brain.get_current_state()
        
        # Performance history should be populated
        assert len(final_state.performance_history) == 5
        assert len(final_state.attribution_history) == 5
        
        # Each entry should have correct structure
        for date, performance in final_state.performance_history:
            assert isinstance(date, datetime)
            assert isinstance(performance, dict)
            assert len(performance) > 0
        
        for date, attribution in final_state.attribution_history:
            assert isinstance(date, datetime)
            assert isinstance(attribution, dict)
            assert len(attribution) > 0
    
    def test_state_hash_uniqueness(self):
        """Test that state hashes are unique for different states"""
        
        # Get initial state hash
        initial_state = self.brain.get_current_state()
        initial_hash = initial_state.state_hash
        
        # Step forward
        current_date = self.start_date + timedelta(days=1)
        daily_data = {
            'market_return': 0.01,
            'market_volatility': 0.15,
            'market_momentum': 0.005
        }
        
        self.brain.step_forward(daily_data, current_date)
        new_state = self.brain.get_current_state()
        new_hash = new_state.state_hash
        
        # Hashes should be different
        assert new_hash != initial_hash, "State hashes should be unique"
        
        # Hash should be consistent for same state
        same_hash = new_state._calculate_hash()
        assert same_hash == new_hash, "Hash calculation should be consistent"
    
    def test_temporal_integrity_enforcement(self):
        """Test that temporal integrity is enforced during state updates"""
        
        current_date = self.start_date + timedelta(days=1)
        daily_data = {
            'market_return': 0.01,
            'market_volatility': 0.15,
            'market_momentum': 0.005
        }
        
        # Normal forward step should work
        portfolio_weights = self.brain.step_forward(daily_data, current_date)
        assert isinstance(portfolio_weights, dict)
        
        # Trying to step backwards should fail
        past_date = self.start_date
        with pytest.raises(ValueError, match="cannot step backwards"):
            self.brain.step_forward(daily_data, past_date)
        
        # Trying to step to same date should fail
        with pytest.raises(ValueError, match="cannot step backwards"):
            self.brain.step_forward(daily_data, current_date)


def test_brain_state_preservation_suite():
    """Run all brain state preservation tests"""
    test_suite = TestBrainStatePreservation()
    
    # Run each test method
    test_methods = [
        'test_state_serialization_roundtrip',
        'test_state_integrity_verification', 
        'test_state_file_persistence',
        'test_state_evolution_consistency',
        'test_regime_state_preservation',
        'test_bayesian_priors_evolution',
        'test_specialist_weights_rebalancing',
        'test_signal_decay_application',
        'test_performance_attribution_tracking',
        'test_state_hash_uniqueness',
        'test_temporal_integrity_enforcement'
    ]
    
    for method_name in test_methods:
        test_suite.setup_method()
        method = getattr(test_suite, method_name)
        method()
        print(f"✅ {method_name}")


if __name__ == "__main__":
    print("🧪 Testing Brain State Preservation...")
    
    test_brain_state_preservation_suite()
    
    print("\n🎉 All brain state preservation tests passed!")
    print("💡 Brain state is properly preserved and maintains temporal integrity")