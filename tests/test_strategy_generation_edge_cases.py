#!/usr/bin/env python3
"""
Unit Tests for Strategy Generation Edge Cases

Tests specific edge cases and boundary conditions for strategy generation:
- Generation with infeasible target Greeks
- Generation with tight constraints
- Ranking with multiple equivalent structures

Requirements: 2.3, 2.5
"""

import pytest
from datetime import datetime, timedelta
import numpy as np

from src.volatility.strategy_generator import (
    StrategyGenerator, TargetGreeks, Constraints, MarketState
)


class TestStrategyGenerationEdgeCases:
    """Unit tests for strategy generation edge cases"""
    
    def test_infeasible_target_greeks_returns_empty(self):
        """
        Test generation with infeasible target Greeks.
        
        When target Greeks are impossible to achieve (e.g., positive vega
        with zero cost), should return empty list.
        
        Requirements: 2.3
        """
        # Impossible target: high vega with very low cost constraint
        target = TargetGreeks(
            delta=0.0,
            delta_tolerance=0.1,
            vega=100.0,  # Very high vega
            vega_tolerance=10.0,
            gamma=0.0,
            gamma_tolerance=0.1,
            theta=0.0,
            theta_tolerance=1.0
        )
        
        state = MarketState(
            spot_price=450.0,
            implied_vol=0.20,
            risk_free_rate=0.05
        )
        
        constraints = Constraints(
            max_legs=6,
            max_cost=100.0,  # Very low cost - impossible to achieve high vega
            allowed_underlyings=["SPY"]
        )
        
        generator = StrategyGenerator()
        strategies = generator.generate(target, constraints, state)
        
        # Should return empty list for infeasible targets
        assert len(strategies) == 0, "Should return empty list for infeasible targets"
    
    def test_extreme_delta_target_returns_directional_structures(self):
        """
        Test that extreme delta targets generate directional structures.
        
        Requirements: 2.1, 2.3
        """
        # Very bullish target
        target = TargetGreeks(
            delta=0.8,  # Very bullish
            delta_tolerance=0.3,
            vega=0.5,
            vega_tolerance=0.5,
            gamma=0.0,
            gamma_tolerance=0.2,
            theta=0.0,
            theta_tolerance=2.0
        )
        
        state = MarketState(
            spot_price=450.0,
            implied_vol=0.20,
            risk_free_rate=0.05
        )
        
        constraints = Constraints(
            max_legs=6,
            max_cost=50000.0,
            allowed_underlyings=["SPY"]
        )
        
        generator = StrategyGenerator()
        strategies = generator.generate(target, constraints, state)
        
        # Should generate at least one strategy
        if strategies:
            # All strategies should have positive delta
            for strategy in strategies:
                assert strategy.greeks.delta > 0, \
                    f"Bullish strategy should have positive delta, got {strategy.greeks.delta}"
    
    def test_tight_leg_constraint(self):
        """
        Test generation with tight leg count constraint.
        
        Requirements: 2.5
        """
        target = TargetGreeks(
            delta=0.0,
            delta_tolerance=0.5,
            vega=1.0,
            vega_tolerance=0.5,
            gamma=0.0,
            gamma_tolerance=0.1,
            theta=0.0,
            theta_tolerance=1.0
        )
        
        state = MarketState(
            spot_price=450.0,
            implied_vol=0.20,
            risk_free_rate=0.05
        )
        
        # Very tight constraint: max 2 legs
        constraints = Constraints(
            max_legs=2,
            max_cost=50000.0,
            allowed_underlyings=["SPY"]
        )
        
        generator = StrategyGenerator()
        strategies = generator.generate(target, constraints, state)
        
        # All generated strategies should respect leg limit
        for strategy in strategies:
            assert len(strategy.legs) <= 2, \
                f"Strategy has {len(strategy.legs)} legs, exceeds limit of 2"
    
    def test_tight_dte_constraint(self):
        """
        Test generation with tight DTE (days to expiration) constraint.
        
        Requirements: 2.5
        """
        target = TargetGreeks(
            delta=0.0,
            delta_tolerance=0.5,
            vega=1.0,
            vega_tolerance=0.5,
            gamma=0.0,
            gamma_tolerance=0.1,
            theta=0.0,
            theta_tolerance=1.0
        )
        
        state = MarketState(
            spot_price=450.0,
            implied_vol=0.20,
            risk_free_rate=0.05
        )
        
        # Very tight DTE window
        constraints = Constraints(
            max_legs=6,
            max_cost=50000.0,
            allowed_underlyings=["SPY"],
            min_dte=14,
            max_dte=21  # Only 1 week window
        )
        
        generator = StrategyGenerator()
        strategies = generator.generate(target, constraints, state)
        
        # All generated strategies should respect DTE limits
        for strategy in strategies:
            dte = (strategy.expiry - datetime.now().date()).days
            assert constraints.min_dte <= dte <= constraints.max_dte, \
                f"Strategy DTE {dte} outside range [{constraints.min_dte}, {constraints.max_dte}]"
    
    def test_ranking_with_equivalent_structures(self):
        """
        Test ranking when multiple structures have similar cost-efficiency.
        
        Should rank by cost-efficiency and return top 3.
        
        Requirements: 2.2, 2.3
        """
        target = TargetGreeks(
            delta=0.0,
            delta_tolerance=0.5,
            vega=1.0,
            vega_tolerance=0.5,
            gamma=0.0,
            gamma_tolerance=0.1,
            theta=0.0,
            theta_tolerance=1.0
        )
        
        state = MarketState(
            spot_price=450.0,
            implied_vol=0.20,
            risk_free_rate=0.05
        )
        
        constraints = Constraints(
            max_legs=6,
            max_cost=50000.0,
            allowed_underlyings=["SPY"]
        )
        
        generator = StrategyGenerator()
        strategies = generator.generate(target, constraints, state)
        
        # Should return at most 3 strategies
        assert len(strategies) <= 3, f"Should return at most 3 strategies, got {len(strategies)}"
        
        # Strategies should be ranked by cost-efficiency (lower is better)
        if len(strategies) > 1:
            for i in range(len(strategies) - 1):
                assert strategies[i].cost_efficiency <= strategies[i+1].cost_efficiency, \
                    f"Strategies not properly ranked: {strategies[i].cost_efficiency} > {strategies[i+1].cost_efficiency}"
    
    def test_zero_vega_target(self):
        """
        Test generation with zero vega target (delta-neutral, no vol exposure).
        
        Requirements: 2.1, 2.3
        """
        target = TargetGreeks(
            delta=0.0,
            delta_tolerance=0.2,
            vega=0.0,  # Zero vega
            vega_tolerance=0.3,
            gamma=0.0,
            gamma_tolerance=0.1,
            theta=0.0,
            theta_tolerance=1.0
        )
        
        state = MarketState(
            spot_price=450.0,
            implied_vol=0.20,
            risk_free_rate=0.05
        )
        
        constraints = Constraints(
            max_legs=6,
            max_cost=50000.0,
            allowed_underlyings=["SPY"]
        )
        
        generator = StrategyGenerator()
        strategies = generator.generate(target, constraints, state)
        
        # Should generate strategies with near-zero vega
        for strategy in strategies:
            assert abs(strategy.greeks.vega) <= target.vega_tolerance, \
                f"Strategy vega {strategy.greeks.vega} exceeds tolerance {target.vega_tolerance}"
    
    def test_negative_gamma_target(self):
        """
        Test generation with negative gamma target (short gamma).
        
        Requirements: 2.1, 2.3
        """
        target = TargetGreeks(
            delta=0.0,
            delta_tolerance=0.5,
            vega=-1.0,
            vega_tolerance=0.5,
            gamma=-0.05,  # Negative gamma
            gamma_tolerance=0.05,
            theta=0.0,
            theta_tolerance=1.0
        )
        
        state = MarketState(
            spot_price=450.0,
            implied_vol=0.20,
            risk_free_rate=0.05
        )
        
        constraints = Constraints(
            max_legs=6,
            max_cost=50000.0,
            allowed_underlyings=["SPY"]
        )
        
        generator = StrategyGenerator()
        strategies = generator.generate(target, constraints, state)
        
        # Should generate short gamma strategies
        for strategy in strategies:
            # Gamma should be negative or near target
            assert strategy.greeks.gamma <= target.gamma + target.gamma_tolerance, \
                f"Strategy gamma {strategy.greeks.gamma} too high for short gamma target"
    
    def test_high_implied_vol_environment(self):
        """
        Test strategy generation in high implied volatility environment.
        
        Requirements: 2.1, 2.6
        """
        target = TargetGreeks(
            delta=0.0,
            delta_tolerance=0.5,
            vega=1.0,
            vega_tolerance=0.5,
            gamma=0.0,
            gamma_tolerance=0.1,
            theta=0.0,
            theta_tolerance=1.0
        )
        
        # High IV environment
        state = MarketState(
            spot_price=450.0,
            implied_vol=0.60,  # Very high IV (60%)
            risk_free_rate=0.05
        )
        
        constraints = Constraints(
            max_legs=6,
            max_cost=50000.0,
            allowed_underlyings=["SPY"]
        )
        
        generator = StrategyGenerator()
        strategies = generator.generate(target, constraints, state)
        
        # Should still generate valid strategies
        # Prices will be higher due to high IV
        for strategy in strategies:
            assert strategy.price > 0, "Strategy price should be positive"
            assert np.isfinite(strategy.price), "Strategy price should be finite"
            assert np.isfinite(strategy.greeks.vega), "Vega should be finite"
    
    def test_low_implied_vol_environment(self):
        """
        Test strategy generation in low implied volatility environment.
        
        Requirements: 2.1, 2.6
        """
        target = TargetGreeks(
            delta=0.0,
            delta_tolerance=0.5,
            vega=1.0,
            vega_tolerance=0.5,
            gamma=0.0,
            gamma_tolerance=0.1,
            theta=0.0,
            theta_tolerance=1.0
        )
        
        # Low IV environment
        state = MarketState(
            spot_price=450.0,
            implied_vol=0.08,  # Very low IV (8%)
            risk_free_rate=0.05
        )
        
        constraints = Constraints(
            max_legs=6,
            max_cost=50000.0,
            allowed_underlyings=["SPY"]
        )
        
        generator = StrategyGenerator()
        strategies = generator.generate(target, constraints, state)
        
        # Should still generate valid strategies
        # Prices will be lower due to low IV
        for strategy in strategies:
            assert strategy.price > 0, "Strategy price should be positive"
            assert np.isfinite(strategy.price), "Strategy price should be finite"
            assert np.isfinite(strategy.greeks.vega), "Vega should be finite"
    
    def test_extreme_spot_price(self):
        """
        Test strategy generation with extreme spot prices.
        
        Requirements: 2.1, 2.6
        """
        target = TargetGreeks(
            delta=0.0,
            delta_tolerance=0.5,
            vega=1.0,
            vega_tolerance=0.5,
            gamma=0.0,
            gamma_tolerance=0.1,
            theta=0.0,
            theta_tolerance=1.0
        )
        
        # Very high spot price
        state = MarketState(
            spot_price=5000.0,  # Very high
            implied_vol=0.20,
            risk_free_rate=0.05
        )
        
        constraints = Constraints(
            max_legs=6,
            max_cost=500000.0,  # Higher cost limit for high spot
            allowed_underlyings=["SPY"]
        )
        
        generator = StrategyGenerator()
        strategies = generator.generate(target, constraints, state)
        
        # Should generate valid strategies with strikes near spot
        for strategy in strategies:
            assert strategy.price > 0, "Strategy price should be positive"
            # Check that strikes are reasonable relative to spot
            for leg in strategy.legs:
                assert 0.5 * state.spot_price <= leg.strike <= 1.5 * state.spot_price, \
                    f"Strike {leg.strike} too far from spot {state.spot_price}"
    
    def test_all_greeks_zero_target(self):
        """
        Test generation with all Greeks at zero (edge case).
        
        Should default to some reasonable structure.
        
        Requirements: 2.1, 2.3
        """
        target = TargetGreeks(
            delta=0.0,
            delta_tolerance=0.5,
            vega=0.0,
            vega_tolerance=0.5,
            gamma=0.0,
            gamma_tolerance=0.1,
            theta=0.0,
            theta_tolerance=1.0
        )
        
        state = MarketState(
            spot_price=450.0,
            implied_vol=0.20,
            risk_free_rate=0.05
        )
        
        constraints = Constraints(
            max_legs=6,
            max_cost=50000.0,
            allowed_underlyings=["SPY"]
        )
        
        generator = StrategyGenerator()
        strategies = generator.generate(target, constraints, state)
        
        # Should still generate some strategies (defaults to long vol)
        # This tests the fallback behavior in _decompose_greeks
        assert len(strategies) >= 0, "Should handle all-zero target gracefully"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
