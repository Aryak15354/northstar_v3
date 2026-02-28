"""
Property-Based Tests for Task 9: Intelligence Engine with Correctness Laws

These tests validate the correctness properties for the intelligence engine
as defined in the design document.

**Feature: northstar-v3-system-cohesion, Property 17: Regime Consistency (I1)**
**Feature: northstar-v3-system-cohesion, Property 18: Signal Decay Enforcement (I2)**
**Feature: northstar-v3-system-cohesion, Property 19: Intelligence State Consistency (I3)**
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from datetime import datetime, timedelta
from typing import Dict, Any, List
import logging
import numpy as np
import pandas as pd

# Import the intelligence engine system
from src.volatility.intelligence_engine import (
    UnifiedIntelligenceEngine, MarketRegime, SignalType, IntelligenceState, SignalHistory
)
from src.cohesion.unified_state_manager import UnifiedStateManager, AuthorityLevel

logger = logging.getLogger(__name__)

# Strategies for property testing
@st.composite
def market_data_strategy(draw):
    """Generate realistic market data"""
    num_days = draw(st.integers(min_value=10, max_value=100))
    
    # Generate returns with realistic properties
    returns = []
    for _ in range(num_days):
        daily_return = draw(st.floats(min_value=-0.10, max_value=0.10))
        returns.append(daily_return)
    
    # Generate other market metrics
    advances = draw(st.integers(min_value=100, max_value=2000))
    declines = draw(st.integers(min_value=100, max_value=2000))
    vix = draw(st.floats(min_value=10.0, max_value=80.0))
    
    data = {
        'returns': returns,
        'advances': [advances] * num_days,
        'declines': [declines] * num_days,
        'vix': [vix] * num_days
    }
    
    return pd.DataFrame(data)

@st.composite
def signal_history_strategy(draw):
    """Generate signal history for testing"""
    num_points = draw(st.integers(min_value=30, max_value=200))
    
    timestamps = []
    values = []
    ics = []
    
    base_date = datetime.now() - timedelta(days=num_points)
    
    # Generate signal with realistic decay
    initial_ic = draw(st.floats(min_value=0.05, max_value=0.20))
    decay_rate = draw(st.floats(min_value=-0.001, max_value=0.0005))
    
    for i in range(num_points):
        timestamp = base_date + timedelta(days=i)
        value = draw(st.floats(min_value=-1.0, max_value=1.0))
        
        # IC should decay over time (with some noise)
        ic = initial_ic + (decay_rate * i) + draw(st.floats(min_value=-0.02, max_value=0.02))
        ic = max(-0.5, min(0.5, ic))  # Bound IC
        
        timestamps.append(timestamp)
        values.append(value)
        ics.append(ic)
    
    return pd.DataFrame({
        'signal': values,
        'returns': [draw(st.floats(min_value=-0.05, max_value=0.05)) for _ in range(num_points)]
    }), timestamps, ics

@st.composite
def intelligence_state_strategy(draw):
    """Generate intelligence state for testing"""
    regime = draw(st.sampled_from(list(MarketRegime)))
    confidence = draw(st.floats(min_value=0.0, max_value=1.0))
    risk_on_prob = draw(st.floats(min_value=0.0, max_value=1.0))
    
    # Generate regime-appropriate strategy allocations
    # This ensures the test data respects regime constraints
    allocations = _generate_regime_appropriate_allocations(regime, draw)
    
    # Generate signal strengths
    signal_strengths = {}
    for signal_type in SignalType:
        signal_strengths[signal_type] = draw(st.floats(min_value=-1.0, max_value=1.0))
    
    return IntelligenceState(
        market_regime=regime,
        regime_confidence=confidence,
        risk_on_probability=risk_on_prob,
        volatility_regime=draw(st.sampled_from(['Low', 'Normal', 'High', 'Extreme'])),
        market_stress=draw(st.floats(min_value=0.0, max_value=1.0)),
        breadth_metrics={
            'advance_decline': draw(st.floats(min_value=0.0, max_value=1.0)),
            'new_highs_lows': draw(st.floats(min_value=-1.0, max_value=1.0)),
            'sector_rotation': draw(st.floats(min_value=0.0, max_value=1.0))
        },
        signal_strengths=signal_strengths,
        strategy_allocations=allocations,
        timestamp=datetime.now(),
        version=draw(st.integers(min_value=1, max_value=1000))
    )

def _generate_regime_appropriate_allocations(regime: MarketRegime, draw) -> Dict[str, float]:
    """Generate strategy allocations that respect regime constraints"""
    
    # Define max allocation per strategy to ensure no single strategy > 50%
    MAX_ALLOCATION = 0.50
    MIN_ALLOCATION = 0.10
    
    if regime == MarketRegime.CRISIS:
        # Crisis: momentum ≤ 20%, volatility should be high
        momentum = draw(st.floats(min_value=0.05, max_value=0.20))
        volatility = draw(st.floats(min_value=0.25, max_value=0.40))  # Cap at 40%
        
        # Distribute remaining between mean_reversion and carry
        remaining = 1.0 - momentum - volatility
        mean_reversion = draw(st.floats(min_value=MIN_ALLOCATION, max_value=min(MAX_ALLOCATION, remaining - MIN_ALLOCATION)))
        carry = remaining - mean_reversion
        
        # Ensure carry is within bounds
        if carry > MAX_ALLOCATION or carry < MIN_ALLOCATION:
            # Adjust mean_reversion to make carry reasonable
            carry = max(MIN_ALLOCATION, min(MAX_ALLOCATION, carry))
            mean_reversion = remaining - carry
        
        return {
            'momentum': momentum,
            'mean_reversion': mean_reversion,
            'carry': carry,
            'volatility': volatility
        }
    
    elif regime == MarketRegime.BEAR_MARKET:
        # Bear: mean_reversion should be >= momentum
        momentum = draw(st.floats(min_value=MIN_ALLOCATION, max_value=0.25))
        mean_reversion = draw(st.floats(min_value=momentum, max_value=min(MAX_ALLOCATION, momentum + 0.20)))
        
        # Distribute remaining between carry and volatility
        remaining = 1.0 - momentum - mean_reversion
        carry = draw(st.floats(min_value=MIN_ALLOCATION, max_value=min(MAX_ALLOCATION, remaining - MIN_ALLOCATION)))
        volatility = remaining - carry
        
        # Ensure volatility is within bounds
        if volatility > MAX_ALLOCATION or volatility < MIN_ALLOCATION:
            # Adjust carry to make volatility reasonable
            volatility = max(MIN_ALLOCATION, min(MAX_ALLOCATION, volatility))
            carry = remaining - volatility
        
        return {
            'momentum': momentum,
            'mean_reversion': mean_reversion,
            'carry': carry,
            'volatility': volatility
        }
    
    elif regime == MarketRegime.BULL_MARKET:
        # Bull: momentum should be >= 25%
        momentum = draw(st.floats(min_value=0.25, max_value=MAX_ALLOCATION))
        
        # Distribute remaining among others
        remaining = 1.0 - momentum
        mean_reversion = draw(st.floats(min_value=MIN_ALLOCATION, max_value=min(MAX_ALLOCATION, remaining - 2 * MIN_ALLOCATION)))
        carry = draw(st.floats(min_value=MIN_ALLOCATION, max_value=min(MAX_ALLOCATION, remaining - mean_reversion - MIN_ALLOCATION)))
        volatility = remaining - mean_reversion - carry
        
        # Ensure volatility is within bounds
        if volatility > MAX_ALLOCATION or volatility < MIN_ALLOCATION:
            # Rescale proportionally
            total_others = mean_reversion + carry + volatility
            scale = remaining / total_others
            mean_reversion *= scale
            carry *= scale
            volatility *= scale
        
        return {
            'momentum': momentum,
            'mean_reversion': mean_reversion,
            'carry': carry,
            'volatility': volatility
        }
    
    else:
        # Normal/Recovery/Bubble: balanced allocations
        # Use a simpler approach to avoid floating point precision issues
        base_allocation = 0.25  # Start with equal 25% each
        
        # Add small random variations
        variations = []
        for i in range(3):  # Generate 3 variations
            variation = draw(st.floats(min_value=-0.10, max_value=0.10))
            variations.append(variation)
        
        # Calculate allocations
        momentum = base_allocation + variations[0]
        mean_reversion = base_allocation + variations[1]
        carry = base_allocation + variations[2]
        volatility = 1.0 - momentum - mean_reversion - carry
        
        # Ensure all are within bounds
        allocations = [momentum, mean_reversion, carry, volatility]
        
        # If any allocation is out of bounds, normalize
        if any(a < MIN_ALLOCATION or a > MAX_ALLOCATION for a in allocations):
            # Clamp to bounds
            allocations = [max(MIN_ALLOCATION, min(MAX_ALLOCATION, a)) for a in allocations]
            # Normalize to sum to 1
            total = sum(allocations)
            allocations = [a / total for a in allocations]
        
        return {
            'momentum': allocations[0],
            'mean_reversion': allocations[1],
            'carry': allocations[2],
            'volatility': allocations[3]
        }

class TestIntelligenceEngineProperties:
    """Property-based tests for intelligence engine system"""
    
    def setup_method(self):
        """Set up test fixtures"""
        # Use a temporary directory for test state to avoid persistence issues
        import tempfile
        temp_dir = tempfile.mkdtemp()
        self.state_manager = UnifiedStateManager(persistence_dir=temp_dir)
        
        # Initialize state manager with test state
        self.state_manager.update_state(
            component='intelligence',
            updates={
                'regime': 'Normal',
                'confidence': 0.5
            },
            authority=AuthorityLevel.SYSTEM,
            reason="Test initialization"
        )
        
        self.intelligence_engine = IntelligenceEngine(self.state_manager)
    
    @given(intelligence_state_strategy())
    @settings(max_examples=100, deadline=5000)
    def test_property_17_regime_consistency(self, intelligence_state):
        """
        Property 17: Regime Consistency (I1)
        
        For any market regime, strategy allocations must be consistent with 
        regime characteristics. If market.regime == "Crisis" then momentum_weight ≤ 0.2
        
        **Validates: Requirements 3.4**
        """
        # Test regime-specific allocation constraints
        regime = intelligence_state.market_regime
        allocations = intelligence_state.strategy_allocations
        
        # Validate allocations sum to 1 (within tolerance)
        total_allocation = sum(allocations.values())
        assert abs(total_allocation - 1.0) <= 0.01, f"Allocations sum to {total_allocation}, not 1.0"
        
        # Test regime-specific constraints
        momentum_allocation = allocations.get('momentum', 0.0)
        
        if regime == MarketRegime.CRISIS:
            # Crisis regime should have low momentum allocation
            assert momentum_allocation <= 0.20, f"Crisis regime momentum {momentum_allocation:.1%} > 20%"
            
            # Crisis should favor volatility strategies
            volatility_allocation = allocations.get('volatility', 0.0)
            assert volatility_allocation >= 0.25, "Crisis should have high volatility allocation"
        
        elif regime == MarketRegime.BULL_MARKET:
            # Bull market can have higher momentum
            assert momentum_allocation >= 0.25, f"Bull market momentum {momentum_allocation:.1%} too low"
        
        elif regime == MarketRegime.BEAR_MARKET:
            # Bear market should favor mean reversion
            mean_reversion_allocation = allocations.get('mean_reversion', 0.0)
            assert mean_reversion_allocation >= momentum_allocation, "Bear market should favor mean reversion"
        
        # Test that allocations are reasonable (no single strategy > 60%)
        for strategy, allocation in allocations.items():
            assert 0.0 <= allocation <= 0.60, f"Strategy {strategy} allocation {allocation:.1%} unreasonable"
        
        # Test state consistency
        validation_result = intelligence_state.validate_consistency()
        
        # Should pass basic consistency checks
        if not validation_result.is_valid:
            # Only fail if there are actual errors (warnings are OK)
            assert len(validation_result.errors) == 0, f"State consistency errors: {validation_result.errors}"
        
        # Test that the engine generates consistent allocations for this regime
        engine_allocations = self.intelligence_engine._calculate_regime_allocations(regime)
        
        # Engine allocations should also follow regime rules
        engine_momentum = engine_allocations.get('momentum', 0.0)
        
        if regime == MarketRegime.CRISIS:
            assert engine_momentum <= 0.20, f"Engine crisis momentum {engine_momentum:.1%} > 20%"
        elif regime == MarketRegime.BULL_MARKET:
            assert engine_momentum >= 0.30, f"Engine bull momentum {engine_momentum:.1%} too low"
        elif regime == MarketRegime.BEAR_MARKET:
            engine_mean_reversion = engine_allocations.get('mean_reversion', 0.0)
            assert engine_mean_reversion >= engine_momentum, "Engine bear should favor mean reversion"
        
        # Engine allocations should sum to 1
        engine_total = sum(engine_allocations.values())
        assert abs(engine_total - 1.0) < 0.001, f"Engine allocations sum to {engine_total}, not 1.0"
    
    @given(signal_history_strategy())
    @settings(max_examples=50, deadline=10000)
    def test_property_18_signal_decay_enforcement(self, signal_data):
        """
        Property 18: Signal Decay Enforcement (I2)
        
        For any predictive signal, information content must decay over time.
        IC[t+180] < IC[t+30] - if not → overfitting
        
        **Validates: Requirements 5.4**
        """
        signal_history_df, timestamps, ics = signal_data
        
        # Test signal decay validation
        validation_result = self.intelligence_engine.detect_overfitting(signal_history_df)
        
        # Should always return a valid result
        assert isinstance(validation_result.is_valid, bool)
        
        if len(ics) >= 60:  # Enough data for meaningful analysis
            # Calculate early vs late IC
            third = len(ics) // 3
            early_ics = ics[:third]
            late_ics = ics[-third:]
            
            early_mean = np.mean(early_ics)
            late_mean = np.mean(late_ics)
            
            # If signal shows proper decay, validation should pass or warn
            if late_mean < early_mean:  # Proper decay
                # Should not have errors about lack of decay
                decay_errors = [e for e in validation_result.errors if 'decay' in e.lower()]
                assert len(decay_errors) == 0, "Should not error on proper signal decay"
            
            # Test signal strength bounds
            for signal_type in SignalType:
                success = self.intelligence_engine.update_signal_strength(
                    signal_type=signal_type,
                    strength=0.5,  # Valid strength
                    information_coefficient=0.1  # Valid IC
                )
                assert success, f"Valid signal update should succeed for {signal_type}"
                
                # Test invalid strength bounds
                success = self.intelligence_engine.update_signal_strength(
                    signal_type=signal_type,
                    strength=1.5,  # Invalid - outside [-1, 1]
                    information_coefficient=0.1
                )
                assert not success, "Invalid signal strength should be rejected"
        
        # Test signal consistency validation
        consistency_result = self.intelligence_engine.validate_signal_consistency()
        assert isinstance(consistency_result.is_valid, bool)
        
        # Should not have critical errors for reasonable signals
        critical_errors = [e for e in consistency_result.errors if 'critical' in e.lower()]
        assert len(critical_errors) == 0, "Should not have critical signal errors"
    
    @given(market_data_strategy())
    @settings(max_examples=50, deadline=10000)
    def test_property_19_intelligence_state_consistency(self, market_data):
        """
        Property 19: Intelligence State Consistency (I3)
        
        For any intelligence update, all derived states must be recalculated consistently.
        When intelligence state changes, all dependent calculations must update.
        
        **Validates: Requirements 3.2**
        """
        # Get initial state version
        initial_state = self.intelligence_engine.get_intelligence_state()
        initial_version = initial_state['version']
        
        # Update market regime
        as_of_time = datetime.now()
        updated_state = self.intelligence_engine.update_market_regime(market_data, as_of_time)
        
        # State should be updated
        assert isinstance(updated_state, dict)
        assert 'market_regime' in updated_state
        assert 'timestamp' in updated_state
        assert 'version' in updated_state
        
        # Version should increment
        new_version = updated_state['version']
        assert new_version > initial_version, "State version should increment on update"
        
        # Timestamp should be updated
        updated_timestamp = updated_state['timestamp']
        assert updated_timestamp == as_of_time, "Timestamp should match update time"
        
        # Get strategy allocations for the new state
        allocations = self.intelligence_engine.get_strategy_allocations(updated_state)
        
        # Allocations should be consistent with regime
        regime = MarketRegime(updated_state['market_regime'])
        
        # Test regime-allocation consistency
        momentum_allocation = allocations.get('momentum', 0.0)
        
        if regime == MarketRegime.CRISIS:
            assert momentum_allocation <= 0.20, "Crisis regime should limit momentum"
        elif regime == MarketRegime.BULL_MARKET:
            assert momentum_allocation >= 0.25, "Bull market should favor momentum"
        
        # Test that all allocations sum to 1
        total_allocation = sum(allocations.values())
        assert abs(total_allocation - 1.0) <= 0.01, "Strategy allocations must sum to 1"
        
        # Test state consistency after update
        current_state = self.intelligence_engine.current_intelligence_state
        validation_result = current_state.validate_consistency()
        
        # State should be consistent after update
        if not validation_result.is_valid:
            # Should not have critical consistency errors
            critical_errors = [e for e in validation_result.errors 
                             if any(word in e.lower() for word in ['bound', 'sum', 'invalid'])]
            assert len(critical_errors) == 0, f"Critical consistency errors: {critical_errors}"
        
        # Test that state manager is updated consistently
        state_manager_state = self.state_manager.get_component_state('intelligence')
        
        # State manager should have the updated intelligence state
        assert state_manager_state is not None, "State manager should have intelligence state"
        
        # Key fields should match
        if 'market_regime' in state_manager_state:
            # Compare the string values since state manager stores strings
            expected_regime = updated_state['market_regime']
            if hasattr(expected_regime, 'value'):
                expected_regime = expected_regime.value
            assert state_manager_state['market_regime'] == expected_regime
    
    @given(st.sampled_from(list(MarketRegime)))
    @settings(max_examples=20, deadline=3000)
    def test_regime_allocation_consistency(self, regime):
        """
        Test that regime-specific allocations are mathematically consistent.
        
        For any market regime, strategy allocations should follow regime rules
        and sum to exactly 1.0.
        """
        # Get allocations for regime
        allocations = self.intelligence_engine._calculate_regime_allocations(regime)
        
        # Test basic properties
        assert isinstance(allocations, dict)
        assert len(allocations) >= 3, "Should have multiple strategies"
        
        # Test allocation bounds
        for strategy, allocation in allocations.items():
            assert 0.0 <= allocation <= 1.0, f"Allocation {allocation} for {strategy} out of bounds"
        
        # Test sum to 1
        total = sum(allocations.values())
        assert abs(total - 1.0) < 0.001, f"Allocations sum to {total}, not 1.0"
        
        # Test regime-specific rules
        momentum_alloc = allocations.get('momentum', 0.0)
        volatility_alloc = allocations.get('volatility', 0.0)
        mean_reversion_alloc = allocations.get('mean_reversion', 0.0)
        
        if regime == MarketRegime.CRISIS:
            # Crisis should have low momentum, high volatility
            assert momentum_alloc <= 0.20, f"Crisis momentum {momentum_alloc:.1%} too high"
            assert volatility_alloc >= 0.25, f"Crisis volatility {volatility_alloc:.1%} too low"
        
        elif regime == MarketRegime.BULL_MARKET:
            # Bull market should favor momentum
            assert momentum_alloc >= 0.30, f"Bull momentum {momentum_alloc:.1%} too low"
        
        elif regime == MarketRegime.BEAR_MARKET:
            # Bear market should favor mean reversion
            assert mean_reversion_alloc >= momentum_alloc, "Bear should favor mean reversion over momentum"
    
    def test_signal_strength_validation(self):
        """
        Test signal strength validation and bounds checking.
        
        Signal strengths must be within [-1, 1] bounds and updates
        should maintain consistency.
        """
        # Test valid signal updates
        for signal_type in SignalType:
            # Test valid bounds
            for strength in [-1.0, -0.5, 0.0, 0.5, 1.0]:
                success = self.intelligence_engine.update_signal_strength(
                    signal_type=signal_type,
                    strength=strength,
                    information_coefficient=0.1
                )
                assert success, f"Valid strength {strength} should be accepted"
            
            # Test invalid bounds
            for invalid_strength in [-1.1, 1.1, -2.0, 2.0]:
                success = self.intelligence_engine.update_signal_strength(
                    signal_type=signal_type,
                    strength=invalid_strength,
                    information_coefficient=0.1
                )
                assert not success, f"Invalid strength {invalid_strength} should be rejected"
        
        # Test signal consistency after updates
        validation_result = self.intelligence_engine.validate_signal_consistency()
        assert isinstance(validation_result.is_valid, bool)
    
    def test_intelligence_state_validation(self):
        """
        Test intelligence state validation rules.
        
        Intelligence state must maintain consistency across all fields
        and validate probability bounds.
        """
        # Test valid state
        valid_state = IntelligenceState(
            market_regime=MarketRegime.NORMAL,
            regime_confidence=0.75,
            risk_on_probability=0.60,
            volatility_regime="Normal",
            market_stress=0.15,
            breadth_metrics={'advance_decline': 0.55},
            signal_strengths={signal: 0.1 for signal in SignalType},
            strategy_allocations={
                'momentum': 0.25,
                'mean_reversion': 0.25,
                'carry': 0.25,
                'volatility': 0.25
            },
            timestamp=datetime.now(),
            version=1
        )
        
        validation_result = valid_state.validate_consistency()
        assert validation_result.is_valid, f"Valid state should pass: {validation_result.errors}"
        
        # Test invalid probability bounds
        invalid_state = IntelligenceState(
            market_regime=MarketRegime.NORMAL,
            regime_confidence=1.5,  # Invalid - > 1.0
            risk_on_probability=0.60,
            volatility_regime="Normal",
            market_stress=0.15,
            breadth_metrics={'advance_decline': 0.55},
            signal_strengths={signal: 0.1 for signal in SignalType},
            strategy_allocations={
                'momentum': 0.25,
                'mean_reversion': 0.25,
                'carry': 0.25,
                'volatility': 0.25
            },
            timestamp=datetime.now(),
            version=1
        )
        
        validation_result = invalid_state.validate_consistency()
        assert not validation_result.is_valid, "Invalid confidence should fail validation"
        assert any("confidence" in error.lower() for error in validation_result.errors)
        
        # Test invalid allocation sum
        invalid_allocations_state = IntelligenceState(
            market_regime=MarketRegime.NORMAL,
            regime_confidence=0.75,
            risk_on_probability=0.60,
            volatility_regime="Normal",
            market_stress=0.15,
            breadth_metrics={'advance_decline': 0.55},
            signal_strengths={signal: 0.1 for signal in SignalType},
            strategy_allocations={
                'momentum': 0.30,
                'mean_reversion': 0.30,
                'carry': 0.30,
                'volatility': 0.30  # Sum = 1.2, not 1.0
            },
            timestamp=datetime.now(),
            version=1
        )
        
        validation_result = invalid_allocations_state.validate_consistency()
        assert not validation_result.is_valid, "Invalid allocation sum should fail"
        assert any("sum" in error.lower() for error in validation_result.errors)
    
    def test_engine_health_monitoring(self):
        """
        Test intelligence engine health monitoring.
        
        Health status should reflect the current state of the engine
        and signal quality.
        """
        # Get initial health status
        health_status = self.intelligence_engine.get_health_status()
        
        assert isinstance(health_status, dict)
        assert 'healthy' in health_status
        assert 'current_regime' in health_status
        assert 'regime_confidence' in health_status
        
        # Health should be boolean
        assert isinstance(health_status['healthy'], bool)
        
        # Should have regime information
        assert health_status['current_regime'] in [regime.value for regime in MarketRegime]
        
        # Should have signal information
        assert 'healthy_signals' in health_status
        assert 'total_signals' in health_status
        assert health_status['total_signals'] == len(SignalType)

if __name__ == "__main__":
    # Run the property tests
    pytest.main([__file__, "-v", "--tb=short"])