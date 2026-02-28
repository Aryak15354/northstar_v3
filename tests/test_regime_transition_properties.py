#!/usr/bin/env python3
"""
Property-Based Tests for Regime Transitions

Tests universal properties that should hold during regime transitions.

Property 17: Strategy behavior stable across regime transitions
- For any rapid regime change, all strategy components should remain operational and not crash

**Validates: Requirements 13.3**
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from datetime import datetime, timedelta
import numpy as np
from typing import Dict, Any, List
from unittest.mock import Mock

from src.volatility.unified_engine import UnifiedVolatilityEngine
from src.volatility.regime_detector import VolatilityRegime, RegimeState
from src.volatility.state_engine import VolatilityState, AuthorityLevel
from src.volatility.greeks_aggregator import PortfolioGreeks
from src.volatility.config import VolatilityConfig


# Hypothesis strategies for generating test data

@st.composite
def regime_strategy(draw):
    """Generate random regime"""
    return draw(st.sampled_from([
        VolatilityRegime.LOW_VOL,
        VolatilityRegime.HIGH_VOL,
        VolatilityRegime.CRISIS,
        VolatilityRegime.TRANSITION
    ]))


@st.composite
def regime_state_strategy(draw):
    """Generate random regime state"""
    regime = draw(regime_strategy())
    confidence = draw(st.floats(min_value=0.6, max_value=1.0))
    
    # RegimeState expects a string regime, not VolatilityRegime enum
    return {
        'regime': regime.value,
        'confidence': confidence
    }


@st.composite
def volatility_state_strategy(draw):
    """Generate random but realistic volatility state"""
    spot_price = draw(st.floats(min_value=100.0, max_value=500.0))
    vix_level = draw(st.floats(min_value=10.0, max_value=80.0))
    realized_vol = draw(st.floats(min_value=0.10, max_value=0.80))
    vol_of_vol = draw(st.floats(min_value=0.5, max_value=2.5))
    
    # Generate correlation matrix (3x3 for simplicity)
    n_assets = 3
    # Generate random correlation matrix that is positive semi-definite
    A = np.random.randn(n_assets, n_assets)
    corr_matrix = A @ A.T
    # Normalize to correlation matrix
    d = np.sqrt(np.diag(corr_matrix))
    corr_matrix = corr_matrix / d[:, None] / d[None, :]
    
    regime_dict = draw(regime_state_strategy())
    
    # Create a simple RegimeState for VolatilityState
    from src.volatility.state_engine import RegimeState as StateRegimeState
    regime_state = StateRegimeState(
        regime=regime_dict['regime'],
        confidence=regime_dict['confidence'],
        duration=timedelta(days=1)
    )
    
    return VolatilityState(
        timestamp=datetime.now(),
        version=1,
        authority_level=AuthorityLevel.SYSTEM,
        spot_prices={'SPY': spot_price},
        vix_level=vix_level,
        realized_vol_20d=realized_vol,
        vol_of_vol=vol_of_vol,
        correlation_matrix=corr_matrix,
        regime=regime_state,
        portfolio_greeks=PortfolioGreeks.zero()
    )


@st.composite
def regime_transition_strategy(draw):
    """Generate a pair of different regimes for transition testing"""
    all_regimes = [
        VolatilityRegime.LOW_VOL,
        VolatilityRegime.HIGH_VOL,
        VolatilityRegime.CRISIS,
        VolatilityRegime.TRANSITION
    ]
    
    old_regime = draw(st.sampled_from(all_regimes))
    # Ensure new regime is different from old regime
    new_regime_choices = [r for r in all_regimes if r != old_regime]
    new_regime = draw(st.sampled_from(new_regime_choices))
    
    return old_regime, new_regime


class TestRegimeTransitionProperties:
    """Property-based tests for regime transitions"""
    
    def _create_mock_engine(self):
        """Create UnifiedVolatilityEngine with mocked components"""
        mock_components = {
            "state_engine": Mock(),
            "strategy_generator": Mock(),
            "greeks_aggregator": Mock(),
            "risk_authority": Mock(),
            "dispersion_module": Mock(),
            "gamma_scalper": Mock(),
            "capital_allocator": Mock(),
            "monte_carlo_engine": Mock(),
            "regime_detector": Mock(),
            "execution_interface": Mock(),
            "performance_monitor": Mock()
        }
        
        # Setup basic mock behaviors
        mock_components["greeks_aggregator"].compute_portfolio_greeks.return_value = PortfolioGreeks.zero()
        mock_components["capital_allocator"].allocate_capital.return_value = {}
        mock_components["risk_authority"].get_current_limits.return_value = Mock()
        
        return UnifiedVolatilityEngine(**mock_components)
    
    @given(
        old_new_regime=regime_transition_strategy(),
        state=volatility_state_strategy()
    )
    @settings(max_examples=50, deadline=5000)
    def test_property_17_strategy_behavior_stable_across_regime_transitions(
        self,
        old_new_regime: tuple,
        state: VolatilityState
    ):
        """
        Property 17: Strategy behavior stable across regime transitions
        
        For any rapid regime change, all strategy components should remain
        operational and not crash.
        
        **Validates: Requirements 13.3**
        """
        old_regime, new_regime = old_new_regime
        
        # Create engine with mocked components
        engine = self._create_mock_engine()
        
        # Test that handle_regime_change doesn't crash
        try:
            engine.handle_regime_change(
                old_regime=old_regime.value,
                new_regime=new_regime.value,
                state=state
            )
            
            # Verify engine is still operational
            assert engine is not None
            
            # Verify component health after transition
            health = engine.get_component_health()
            assert health is not None
            assert isinstance(health, dict)
            
            # Verify system status is still accessible
            status = engine.get_system_status()
            assert status is not None
            assert isinstance(status, dict)
            
        except Exception as e:
            pytest.fail(
                f"Regime transition from {old_regime.value} to {new_regime.value} "
                f"caused crash: {str(e)}"
            )
    
    @given(
        old_new_regime=regime_transition_strategy(),
        state=volatility_state_strategy()
    )
    @settings(max_examples=30, deadline=5000)
    def test_capital_allocator_survives_regime_transition(
        self,
        old_new_regime: tuple,
        state: VolatilityState
    ):
        """
        Test that capital allocator remains operational after regime change.
        
        **Validates: Requirements 13.3**
        """
        old_regime, new_regime = old_new_regime
        
        engine = self._create_mock_engine()
        
        # Trigger regime change
        engine.handle_regime_change(
            old_regime=old_regime.value,
            new_regime=new_regime.value,
            state=state
        )
        
        # Verify capital allocator is still functional
        try:
            # Capital allocator should be accessible
            assert engine.capital_allocator is not None
            
            # Should be able to call allocate_capital without crash
            allocation = engine.capital_allocator.allocate_capital(
                state=state,
                strategies=[]
            )
            
            # Allocation should be a valid dict
            assert isinstance(allocation, dict)
            
        except Exception as e:
            pytest.fail(
                f"Capital allocator failed after regime transition: {str(e)}"
            )
    
    @given(
        old_new_regime=regime_transition_strategy(),
        state=volatility_state_strategy()
    )
    @settings(max_examples=30, deadline=5000)
    def test_risk_authority_survives_regime_transition(
        self,
        old_new_regime: tuple,
        state: VolatilityState
    ):
        """
        Test that risk authority remains operational after regime change.
        
        **Validates: Requirements 13.3**
        """
        old_regime, new_regime = old_new_regime
        
        engine = self._create_mock_engine()
        
        # Trigger regime change
        engine.handle_regime_change(
            old_regime=old_regime.value,
            new_regime=new_regime.value,
            state=state
        )
        
        # Verify risk authority is still functional
        try:
            # Risk authority should be accessible
            assert engine.risk_authority is not None
            
            # Should be able to check limits without crash
            limits = engine.risk_authority.get_current_limits(state.regime)
            assert limits is not None
            
        except Exception as e:
            pytest.fail(
                f"Risk authority failed after regime transition: {str(e)}"
            )
    
    @given(
        old_new_regime=regime_transition_strategy(),
        state=volatility_state_strategy()
    )
    @settings(max_examples=30, deadline=5000)
    def test_greeks_aggregator_survives_regime_transition(
        self,
        old_new_regime: tuple,
        state: VolatilityState
    ):
        """
        Test that Greeks aggregator remains operational after regime change.
        
        **Validates: Requirements 13.3**
        """
        old_regime, new_regime = old_new_regime
        
        engine = self._create_mock_engine()
        
        # Trigger regime change
        engine.handle_regime_change(
            old_regime=old_regime.value,
            new_regime=new_regime.value,
            state=state
        )
        
        # Verify Greeks aggregator is still functional
        try:
            # Greeks aggregator should be accessible
            assert engine.greeks_aggregator is not None
            
            # Should be able to compute portfolio Greeks without crash
            greeks = engine.greeks_aggregator.compute_portfolio_greeks(state)
            assert greeks is not None
            assert isinstance(greeks, PortfolioGreeks)
            
        except Exception as e:
            pytest.fail(
                f"Greeks aggregator failed after regime transition: {str(e)}"
            )
    
    @given(
        old_new_regime=regime_transition_strategy(),
        state=volatility_state_strategy()
    )
    @settings(max_examples=30, deadline=5000)
    def test_strategy_generator_survives_regime_transition(
        self,
        old_new_regime: tuple,
        state: VolatilityState
    ):
        """
        Test that strategy generator remains operational after regime change.
        
        **Validates: Requirements 13.3**
        """
        old_regime, new_regime = old_new_regime
        
        engine = self._create_mock_engine()
        
        # Trigger regime change
        engine.handle_regime_change(
            old_regime=old_regime.value,
            new_regime=new_regime.value,
            state=state
        )
        
        # Verify strategy generator is still functional
        try:
            # Strategy generator should be accessible
            assert engine.strategy_generator is not None
            
            # Component should not be in error state
            health = engine.get_component_health()
            if "strategy_generator" in health:
                assert health["strategy_generator"]["status"] != "error"
            
        except Exception as e:
            pytest.fail(
                f"Strategy generator failed after regime transition: {str(e)}"
            )
    
    @given(
        regimes=st.lists(
            regime_strategy(),
            min_size=3,
            max_size=10
        ),
        state=volatility_state_strategy()
    )
    @settings(max_examples=20, deadline=10000)
    def test_multiple_rapid_regime_transitions(
        self,
        regimes: List[VolatilityRegime],
        state: VolatilityState
    ):
        """
        Test that engine survives multiple rapid regime transitions.
        
        **Validates: Requirements 13.3**
        """
        engine = self._create_mock_engine()
        
        # Simulate rapid regime changes
        try:
            for i in range(len(regimes) - 1):
                old_regime = regimes[i]
                new_regime = regimes[i + 1]
                
                engine.handle_regime_change(
                    old_regime=old_regime.value,
                    new_regime=new_regime.value,
                    state=state
                )
                
                # Verify engine is still operational after each transition
                assert engine is not None
                health = engine.get_component_health()
                assert health is not None
            
            # After all transitions, engine should still be functional
            status = engine.get_system_status()
            assert status is not None
            assert isinstance(status, dict)
            
        except Exception as e:
            pytest.fail(
                f"Multiple rapid regime transitions caused crash: {str(e)}"
            )
    
    @given(
        old_new_regime=regime_transition_strategy(),
        state=volatility_state_strategy()
    )
    @settings(max_examples=30, deadline=5000)
    def test_no_data_corruption_during_regime_transition(
        self,
        old_new_regime: tuple,
        state: VolatilityState
    ):
        """
        Test that regime transitions don't corrupt state data.
        
        **Validates: Requirements 13.3**
        """
        old_regime, new_regime = old_new_regime
        
        engine = self._create_mock_engine()
        
        # Capture state before transition
        initial_spot = state.spot_prices.get('SPY', 0)
        initial_vix = state.vix_level
        initial_vol = state.realized_vol_20d
        
        # Trigger regime change
        engine.handle_regime_change(
            old_regime=old_regime.value,
            new_regime=new_regime.value,
            state=state
        )
        
        # Verify state data is not corrupted
        assert state.spot_prices.get('SPY') == initial_spot, "Spot price was corrupted"
        assert state.vix_level == initial_vix, "VIX level was corrupted"
        assert state.realized_vol_20d == initial_vol, "Realized vol was corrupted"
        
        # Verify state is still valid
        assert state.spot_prices.get('SPY', 0) > 0, "Spot price became invalid"
        assert state.vix_level > 0, "VIX level became invalid"
        assert state.realized_vol_20d > 0, "Realized vol became invalid"
        assert not np.isnan(state.spot_prices.get('SPY', 0)), "Spot price became NaN"
        assert not np.isnan(state.vix_level), "VIX level became NaN"
        assert not np.isnan(state.realized_vol_20d), "Realized vol became NaN"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
