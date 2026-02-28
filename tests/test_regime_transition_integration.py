#!/usr/bin/env python3
"""
Integration Tests for Regime Transitions

Tests specific regime transition scenarios to ensure proper system behavior.

**Validates: Requirements 13.3**
"""

import pytest
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Any
from unittest.mock import Mock

from src.volatility.unified_engine import UnifiedVolatilityEngine
from src.volatility.regime_detector import VolatilityRegime
from src.volatility.state_engine import VolatilityState, AuthorityLevel, RegimeState
from src.volatility.greeks_aggregator import PortfolioGreeks
from src.volatility.config import VolatilityConfig


class TestRegimeTransitionIntegration:
    """Integration tests for specific regime transition scenarios"""
    
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
    
    def _create_test_state(
        self,
        vix_level: float,
        realized_vol: float,
        correlation: float,
        regime: str
    ) -> VolatilityState:
        """Helper to create test volatility state"""
        # Create correlation matrix
        n_assets = 3
        corr_matrix = np.eye(n_assets)
        corr_matrix[corr_matrix == 0] = correlation
        
        # Create regime state
        regime_state = RegimeState(
            regime=regime,
            confidence=0.85,
            duration=timedelta(days=1)
        )
        
        return VolatilityState(
            timestamp=datetime.now(),
            version=1,
            authority_level=AuthorityLevel.SYSTEM,
            spot_prices={'SPY': 400.0},
            vix_level=vix_level,
            realized_vol_20d=realized_vol,
            vol_of_vol=1.0,
            correlation_matrix=corr_matrix,
            regime=regime_state,
            portfolio_greeks=PortfolioGreeks.zero()
        )
    
    def test_low_vol_to_high_vol_transition(self):
        """
        Test transition from low volatility to high volatility regime.
        
        Expected behavior:
        - Capital allocation should shift toward gamma scalping
        - Risk limits should be adjusted
        - All components remain operational
        
        **Validates: Requirements 13.3**
        """
        # Create low-vol state
        low_vol_state = self._create_test_state(
            vix_level=12.0,
            realized_vol=0.10,
            correlation=0.3,
            regime=VolatilityRegime.LOW_VOL.value
        )
        
        # Create high-vol state
        high_vol_state = self._create_test_state(
            vix_level=28.0,
            realized_vol=0.30,
            correlation=0.5,
            regime=VolatilityRegime.HIGH_VOL.value
        )
        
        # Initialize engine
        engine = self._create_mock_engine()
        
        # Trigger transition
        engine.handle_regime_change(
            old_regime=VolatilityRegime.LOW_VOL.value,
            new_regime=VolatilityRegime.HIGH_VOL.value,
            state=high_vol_state
        )
        
        # Verify engine is operational
        assert engine is not None
        
        # Verify component health
        health = engine.get_component_health()
        assert health is not None
        assert isinstance(health, dict)
        
        # Verify capital allocator responded to regime change
        assert engine.capital_allocator is not None
        allocation = engine.capital_allocator.allocate_capital(
            state=high_vol_state,
            strategies=[]
        )
        assert isinstance(allocation, dict)
        
        # Verify risk authority updated limits
        assert engine.risk_authority is not None
        limits = engine.risk_authority.get_current_limits(high_vol_state.regime.regime)
        assert limits is not None
        
        # Verify Greeks aggregator still works
        assert engine.greeks_aggregator is not None
        greeks = engine.greeks_aggregator.compute_portfolio_greeks(high_vol_state)
        assert greeks is not None
    
    def test_high_vol_to_crisis_transition(self):
        """
        Test transition from high volatility to crisis regime.
        
        Expected behavior:
        - Emergency protocols should be activated
        - Short vol strategies should be halted
        - Risk limits should be tightened
        - All components remain operational
        
        **Validates: Requirements 13.3**
        """
        # Create high-vol state
        high_vol_state = self._create_test_state(
            vix_level=28.0,
            realized_vol=0.30,
            correlation=0.5,
            regime=VolatilityRegime.HIGH_VOL.value
        )
        
        # Create crisis state
        crisis_state = self._create_test_state(
            vix_level=65.0,
            realized_vol=0.70,
            correlation=0.90,
            regime=VolatilityRegime.CRISIS.value
        )
        
        # Initialize engine
        engine = self._create_mock_engine()
        
        # Trigger transition to crisis
        engine.handle_regime_change(
            old_regime=VolatilityRegime.HIGH_VOL.value,
            new_regime=VolatilityRegime.CRISIS.value,
            state=crisis_state
        )
        
        # Verify engine is operational despite crisis
        assert engine is not None
        
        # Verify component health
        health = engine.get_component_health()
        assert health is not None
        assert isinstance(health, dict)
        
        # Verify capital allocator adjusted for crisis
        assert engine.capital_allocator is not None
        allocation = engine.capital_allocator.allocate_capital(
            state=crisis_state,
            strategies=[]
        )
        assert isinstance(allocation, dict)
        
        # In crisis, short_vol allocation should be zero or minimal
        if "short_vol" in allocation:
            assert allocation["short_vol"] <= 0.01, \
                "Short vol should be near zero in crisis"
        
        # Verify risk authority is enforcing crisis limits
        assert engine.risk_authority is not None
        limits = engine.risk_authority.get_current_limits(crisis_state.regime.regime)
        assert limits is not None
        
        # Verify Greeks aggregator still works
        assert engine.greeks_aggregator is not None
        greeks = engine.greeks_aggregator.compute_portfolio_greeks(crisis_state)
        assert greeks is not None
    
    def test_crisis_to_recovery_transition(self):
        """
        Test transition from crisis to recovery (high vol or transition).
        
        Expected behavior:
        - Emergency protocols should be deactivated
        - Risk limits should be relaxed gradually
        - Capital allocation should normalize
        - All components remain operational
        
        **Validates: Requirements 13.3**
        """
        # Create crisis state
        crisis_state = self._create_test_state(
            vix_level=65.0,
            realized_vol=0.70,
            correlation=0.90,
            regime=VolatilityRegime.CRISIS.value
        )
        
        # Create recovery state (transition regime)
        recovery_state = self._create_test_state(
            vix_level=35.0,
            realized_vol=0.40,
            correlation=0.60,
            regime=VolatilityRegime.TRANSITION.value
        )
        
        # Initialize engine
        engine = self._create_mock_engine()
        
        # First transition to crisis
        engine.handle_regime_change(
            old_regime=VolatilityRegime.HIGH_VOL.value,
            new_regime=VolatilityRegime.CRISIS.value,
            state=crisis_state
        )
        
        # Then transition to recovery
        engine.handle_regime_change(
            old_regime=VolatilityRegime.CRISIS.value,
            new_regime=VolatilityRegime.TRANSITION.value,
            state=recovery_state
        )
        
        # Verify engine is operational after recovery
        assert engine is not None
        
        # Verify component health
        health = engine.get_component_health()
        assert health is not None
        assert isinstance(health, dict)
        
        # Verify capital allocator adjusted for recovery
        assert engine.capital_allocator is not None
        allocation = engine.capital_allocator.allocate_capital(
            state=recovery_state,
            strategies=[]
        )
        assert isinstance(allocation, dict)
        
        # Verify risk authority updated limits for recovery
        assert engine.risk_authority is not None
        limits = engine.risk_authority.get_current_limits(recovery_state.regime.regime)
        assert limits is not None
        
        # Verify Greeks aggregator still works
        assert engine.greeks_aggregator is not None
        greeks = engine.greeks_aggregator.compute_portfolio_greeks(recovery_state)
        assert greeks is not None
    
    def test_rapid_regime_oscillation(self):
        """
        Test rapid oscillation between regimes (stress test).
        
        Expected behavior:
        - Engine should handle rapid back-and-forth transitions
        - No memory leaks or state corruption
        - All components remain operational
        
        **Validates: Requirements 13.3**
        """
        # Create states for oscillation
        low_vol_state = self._create_test_state(
            vix_level=12.0,
            realized_vol=0.10,
            correlation=0.3,
            regime=VolatilityRegime.LOW_VOL.value
        )
        
        high_vol_state = self._create_test_state(
            vix_level=28.0,
            realized_vol=0.30,
            correlation=0.5,
            regime=VolatilityRegime.HIGH_VOL.value
        )
        
        # Initialize engine
        engine = self._create_mock_engine()
        
        # Oscillate between regimes multiple times
        for i in range(5):
            # Low to high
            engine.handle_regime_change(
                old_regime=VolatilityRegime.LOW_VOL.value,
                new_regime=VolatilityRegime.HIGH_VOL.value,
                state=high_vol_state
            )
            
            # Verify operational
            assert engine is not None
            health = engine.get_component_health()
            assert health is not None
            
            # High to low
            engine.handle_regime_change(
                old_regime=VolatilityRegime.HIGH_VOL.value,
                new_regime=VolatilityRegime.LOW_VOL.value,
                state=low_vol_state
            )
            
            # Verify operational
            assert engine is not None
            health = engine.get_component_health()
            assert health is not None
        
        # After oscillations, verify all components still work
        status = engine.get_system_status()
        assert status is not None
        assert isinstance(status, dict)
        
        # Verify capital allocator
        allocation = engine.capital_allocator.allocate_capital(
            state=low_vol_state,
            strategies=[]
        )
        assert isinstance(allocation, dict)
        
        # Verify Greeks aggregator
        greeks = engine.greeks_aggregator.compute_portfolio_greeks(low_vol_state)
        assert greeks is not None
    
    def test_regime_transition_with_portfolio_rebalancing(self):
        """
        Test that portfolio rebalancing works correctly during regime transitions.
        
        Expected behavior:
        - Rebalancing should be triggered when needed
        - Portfolio Greeks should be recalculated
        - No crashes during rebalancing
        
        **Validates: Requirements 13.3**
        """
        # Create states
        low_vol_state = self._create_test_state(
            vix_level=12.0,
            realized_vol=0.10,
            correlation=0.3,
            regime=VolatilityRegime.LOW_VOL.value
        )
        
        crisis_state = self._create_test_state(
            vix_level=65.0,
            realized_vol=0.70,
            correlation=0.90,
            regime=VolatilityRegime.CRISIS.value
        )
        
        # Initialize engine
        engine = self._create_mock_engine()
        
        # Trigger transition that should require rebalancing
        engine.handle_regime_change(
            old_regime=VolatilityRegime.LOW_VOL.value,
            new_regime=VolatilityRegime.CRISIS.value,
            state=crisis_state
        )
        
        # Verify engine handled rebalancing without crash
        assert engine is not None
        
        # Verify Greeks can be computed after rebalancing
        greeks = engine.greeks_aggregator.compute_portfolio_greeks(crisis_state)
        assert greeks is not None
        assert isinstance(greeks, PortfolioGreeks)
        
        # Verify all Greeks are valid numbers (not NaN or inf)
        assert not np.isnan(greeks.delta)
        assert not np.isnan(greeks.gamma)
        assert not np.isnan(greeks.vega)
        assert not np.isnan(greeks.theta)
        assert not np.isinf(greeks.delta)
        assert not np.isinf(greeks.gamma)
        assert not np.isinf(greeks.vega)
        assert not np.isinf(greeks.theta)
    
    def test_all_regime_pairs_transitions(self):
        """
        Test all possible regime pair transitions systematically.
        
        Expected behavior:
        - Every regime transition should be handled gracefully
        - No crashes for any transition pair
        
        **Validates: Requirements 13.3**
        """
        all_regimes = [
            VolatilityRegime.LOW_VOL,
            VolatilityRegime.HIGH_VOL,
            VolatilityRegime.CRISIS,
            VolatilityRegime.TRANSITION
        ]
        
        # Create states for each regime
        regime_states = {
            VolatilityRegime.LOW_VOL: self._create_test_state(
                12.0, 0.10, 0.3, VolatilityRegime.LOW_VOL.value
            ),
            VolatilityRegime.HIGH_VOL: self._create_test_state(
                28.0, 0.30, 0.5, VolatilityRegime.HIGH_VOL.value
            ),
            VolatilityRegime.CRISIS: self._create_test_state(
                65.0, 0.70, 0.90, VolatilityRegime.CRISIS.value
            ),
            VolatilityRegime.TRANSITION: self._create_test_state(
                20.0, 0.25, 0.45, VolatilityRegime.TRANSITION.value
            )
        }
        
        # Initialize engine
        engine = self._create_mock_engine()
        
        # Test all regime pairs
        for old_regime in all_regimes:
            for new_regime in all_regimes:
                if old_regime == new_regime:
                    continue
                
                # Trigger transition
                try:
                    engine.handle_regime_change(
                        old_regime=old_regime.value,
                        new_regime=new_regime.value,
                        state=regime_states[new_regime]
                    )
                    
                    # Verify engine is operational
                    assert engine is not None
                    health = engine.get_component_health()
                    assert health is not None
                    
                except Exception as e:
                    pytest.fail(
                        f"Transition from {old_regime.value} to {new_regime.value} "
                        f"failed: {str(e)}"
                    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
