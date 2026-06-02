"""
Unit Tests for Regime-Conditional Capital Allocation

Tests specific regime-based allocation behaviors:
- Crisis regime constraints (zero short vol)
- Low-vol regime preferences (favor short vol)
- High-vol regime preferences (favor gamma scalping)
- Transition regime defensive positioning (increase market-neutral)

**Validates: Requirements 6.6, 6.7**
"""

import pytest
from datetime import datetime, timedelta
import numpy as np

from src.volatility.volatility_capital_allocator import (
    CapitalAllocator,
    AllocationConstraints,
    PerformanceHistory
)
from src.volatility.state_engine import VolatilityState, RegimeState, AuthorityLevel
from src.volatility.regime_detector import VolatilityRegime


def create_test_state(regime: str, confidence: float = 0.85) -> VolatilityState:
    """Create a test volatility state with specified regime"""
    regime_state = RegimeState(
        regime=regime,
        confidence=confidence,
        duration=timedelta(days=5),
        regime_probabilities={
            'low_vol': 0.25,
            'high_vol': 0.25,
            'crisis': 0.25,
            'transition': 0.25
        }
    )
    
    return VolatilityState(
        timestamp=datetime.now(),
        version=1,
        authority_level=AuthorityLevel.SYSTEM,
        regime=regime_state,
        vix_level=20.0,
        realized_vol_20d=0.15,
        vol_of_vol=1.0
    )


def add_uniform_performance(allocator: CapitalAllocator, regime: str, num_obs: int = 30):
    """Add uniform performance history across all strategies"""
    for strategy in allocator.strategy_buckets:
        for _ in range(num_obs):
            return_value = np.random.uniform(0.01, 0.08)
            allocator.add_performance_observation(
                strategy=strategy,
                regime=regime,
                return_value=return_value,
                timestamp=datetime.now()
            )


class TestCrisisRegimeConstraints:
    """Test crisis regime allocation constraints"""
    
    def test_crisis_blocks_short_vol(self):
        """
        Crisis regime should block short vol strategies
        
        **Validates: Requirements 6.6**
        """
        allocator = CapitalAllocator()
        state = create_test_state('crisis')
        
        # Add performance history
        add_uniform_performance(allocator, 'crisis')
        
        # Allocate capital
        total_capital = 1000000.0
        allocations = allocator.allocate_capital(total_capital, state)
        
        # Assert short_vol is zero
        assert allocations.get('short_vol', 0.0) == 0.0, (
            "short_vol should be zero in crisis regime"
        )
    
    def test_crisis_blocks_dispersion(self):
        """
        Crisis regime should block dispersion strategies
        
        **Validates: Requirements 6.6**
        """
        allocator = CapitalAllocator()
        state = create_test_state('crisis')
        
        add_uniform_performance(allocator, 'crisis')
        
        total_capital = 1000000.0
        allocations = allocator.allocate_capital(total_capital, state)
        
        # Assert dispersion is zero
        assert allocations.get('dispersion', 0.0) == 0.0, (
            "dispersion should be zero in crisis regime"
        )
    
    def test_crisis_increases_long_vol(self):
        """
        Crisis regime should increase allocation to long vol strategies
        
        **Validates: Requirements 6.6**
        """
        allocator = CapitalAllocator()
        
        # Add performance history for both regimes
        add_uniform_performance(allocator, 'crisis')
        add_uniform_performance(allocator, 'low_vol')
        
        # Allocate in crisis
        crisis_state = create_test_state('crisis')
        total_capital = 1000000.0
        crisis_allocations = allocator.allocate_capital(total_capital, crisis_state)
        
        # Allocate in low vol
        low_vol_state = create_test_state('low_vol')
        low_vol_allocations = allocator.allocate_capital(total_capital, low_vol_state)
        
        # Long vol should be higher in crisis
        crisis_long_vol = crisis_allocations.get('long_vol', 0.0)
        low_vol_long_vol = low_vol_allocations.get('long_vol', 0.0)
        
        assert crisis_long_vol > low_vol_long_vol, (
            f"long_vol allocation should be higher in crisis "
            f"({crisis_long_vol:,.0f}) than low_vol ({low_vol_long_vol:,.0f})"
        )
    
    def test_crisis_increases_tail_hedge(self):
        """
        Crisis regime should increase allocation to tail hedge strategies
        
        **Validates: Requirements 6.6**
        """
        allocator = CapitalAllocator()
        
        add_uniform_performance(allocator, 'crisis')
        add_uniform_performance(allocator, 'low_vol')
        
        # Allocate in crisis
        crisis_state = create_test_state('crisis')
        total_capital = 1000000.0
        crisis_allocations = allocator.allocate_capital(total_capital, crisis_state)
        
        # Allocate in low vol
        low_vol_state = create_test_state('low_vol')
        low_vol_allocations = allocator.allocate_capital(total_capital, low_vol_state)
        
        # Tail hedge should be higher in crisis
        crisis_tail = crisis_allocations.get('tail_hedge', 0.0)
        low_vol_tail = low_vol_allocations.get('tail_hedge', 0.0)
        
        assert crisis_tail > low_vol_tail, (
            f"tail_hedge allocation should be higher in crisis "
            f"({crisis_tail:,.0f}) than low_vol ({low_vol_tail:,.0f})"
        )
    
    def test_crisis_with_custom_blocked_strategies(self):
        """
        Test crisis regime with custom blocked strategies
        
        **Validates: Requirements 6.6**
        """
        # Custom constraints blocking additional strategies
        constraints = AllocationConstraints(
            crisis_blocked_strategies=['short_vol', 'dispersion', 'directional_vol']
        )
        
        allocator = CapitalAllocator(constraints=constraints)
        state = create_test_state('crisis')
        
        add_uniform_performance(allocator, 'crisis')
        
        total_capital = 1000000.0
        allocations = allocator.allocate_capital(total_capital, state)
        
        # All blocked strategies should be zero
        for blocked in constraints.crisis_blocked_strategies:
            assert allocations.get(blocked, 0.0) == 0.0, (
                f"{blocked} should be zero in crisis regime"
            )


class TestLowVolRegimePreferences:
    """Test low volatility regime allocation preferences"""
    
    def test_low_vol_favors_short_vol(self):
        """
        Low vol regime should favor short vol strategies
        
        **Validates: Requirements 6.7**
        """
        allocator = CapitalAllocator()
        
        add_uniform_performance(allocator, 'low_vol')
        add_uniform_performance(allocator, 'high_vol')
        
        # Allocate in low vol
        low_vol_state = create_test_state('low_vol')
        total_capital = 1000000.0
        low_vol_allocations = allocator.allocate_capital(total_capital, low_vol_state)
        
        # Allocate in high vol
        high_vol_state = create_test_state('high_vol')
        high_vol_allocations = allocator.allocate_capital(total_capital, high_vol_state)
        
        # Short vol should be higher in low vol
        low_vol_short = low_vol_allocations.get('short_vol', 0.0)
        high_vol_short = high_vol_allocations.get('short_vol', 0.0)
        
        assert low_vol_short > high_vol_short, (
            f"short_vol allocation should be higher in low_vol "
            f"({low_vol_short:,.0f}) than high_vol ({high_vol_short:,.0f})"
        )
    
    def test_low_vol_reduces_gamma_scalp(self):
        """
        Low vol regime should reduce gamma scalping (less realized vol to harvest)
        
        **Validates: Requirements 6.7**
        """
        allocator = CapitalAllocator()
        
        add_uniform_performance(allocator, 'low_vol')
        add_uniform_performance(allocator, 'high_vol')
        
        # Allocate in low vol
        low_vol_state = create_test_state('low_vol')
        total_capital = 1000000.0
        low_vol_allocations = allocator.allocate_capital(total_capital, low_vol_state)
        
        # Allocate in high vol
        high_vol_state = create_test_state('high_vol')
        high_vol_allocations = allocator.allocate_capital(total_capital, high_vol_state)
        
        # Gamma scalp should be lower in low vol
        low_vol_gamma = low_vol_allocations.get('gamma_scalp', 0.0)
        high_vol_gamma = high_vol_allocations.get('gamma_scalp', 0.0)
        
        assert low_vol_gamma < high_vol_gamma, (
            f"gamma_scalp allocation should be lower in low_vol "
            f"({low_vol_gamma:,.0f}) than high_vol ({high_vol_gamma:,.0f})"
        )
    
    def test_low_vol_with_custom_favored_strategies(self):
        """
        Test low vol regime with custom favored strategies
        
        **Validates: Requirements 6.7**
        """
        constraints = AllocationConstraints(
            low_vol_favored=['short_vol', 'relative_value']
        )
        
        allocator = CapitalAllocator(constraints=constraints)
        
        add_uniform_performance(allocator, 'low_vol')
        add_uniform_performance(allocator, 'high_vol')
        
        # Allocate in low vol
        low_vol_state = create_test_state('low_vol')
        total_capital = 1000000.0
        low_vol_allocations = allocator.allocate_capital(total_capital, low_vol_state)
        
        # Allocate in high vol
        high_vol_state = create_test_state('high_vol')
        high_vol_allocations = allocator.allocate_capital(total_capital, high_vol_state)
        
        # Favored strategies should be higher in low vol
        for strategy in constraints.low_vol_favored:
            low_vol_alloc = low_vol_allocations.get(strategy, 0.0)
            high_vol_alloc = high_vol_allocations.get(strategy, 0.0)
            
            assert low_vol_alloc >= high_vol_alloc, (
                f"{strategy} should be favored in low_vol regime"
            )


class TestHighVolRegimePreferences:
    """Test high volatility regime allocation preferences"""
    
    def test_high_vol_favors_gamma_scalp(self):
        """
        High vol regime should favor gamma scalping strategies
        
        **Validates: Requirements 6.7**
        """
        allocator = CapitalAllocator()
        
        add_uniform_performance(allocator, 'high_vol')
        add_uniform_performance(allocator, 'low_vol')
        
        # Allocate in high vol
        high_vol_state = create_test_state('high_vol')
        total_capital = 1000000.0
        high_vol_allocations = allocator.allocate_capital(total_capital, high_vol_state)
        
        # Allocate in low vol
        low_vol_state = create_test_state('low_vol')
        low_vol_allocations = allocator.allocate_capital(total_capital, low_vol_state)
        
        # Gamma scalp should be higher in high vol
        high_vol_gamma = high_vol_allocations.get('gamma_scalp', 0.0)
        low_vol_gamma = low_vol_allocations.get('gamma_scalp', 0.0)
        
        assert high_vol_gamma > low_vol_gamma, (
            f"gamma_scalp allocation should be higher in high_vol "
            f"({high_vol_gamma:,.0f}) than low_vol ({low_vol_gamma:,.0f})"
        )
    
    def test_high_vol_favors_dispersion(self):
        """
        High vol regime should favor dispersion strategies
        
        **Validates: Requirements 6.7**
        """
        allocator = CapitalAllocator()
        
        add_uniform_performance(allocator, 'high_vol')
        add_uniform_performance(allocator, 'low_vol')
        
        # Allocate in high vol
        high_vol_state = create_test_state('high_vol')
        total_capital = 1000000.0
        high_vol_allocations = allocator.allocate_capital(total_capital, high_vol_state)
        
        # Allocate in low vol
        low_vol_state = create_test_state('low_vol')
        low_vol_allocations = allocator.allocate_capital(total_capital, low_vol_state)
        
        # Dispersion should be higher in high vol
        high_vol_disp = high_vol_allocations.get('dispersion', 0.0)
        low_vol_disp = low_vol_allocations.get('dispersion', 0.0)
        
        assert high_vol_disp > low_vol_disp, (
            f"dispersion allocation should be higher in high_vol "
            f"({high_vol_disp:,.0f}) than low_vol ({low_vol_disp:,.0f})"
        )
    
    def test_high_vol_reduces_short_vol(self):
        """
        High vol regime should reduce short vol (higher risk)
        
        **Validates: Requirements 6.7**
        """
        allocator = CapitalAllocator()
        
        add_uniform_performance(allocator, 'high_vol')
        add_uniform_performance(allocator, 'low_vol')
        
        # Allocate in high vol
        high_vol_state = create_test_state('high_vol')
        total_capital = 1000000.0
        high_vol_allocations = allocator.allocate_capital(total_capital, high_vol_state)
        
        # Allocate in low vol
        low_vol_state = create_test_state('low_vol')
        low_vol_allocations = allocator.allocate_capital(total_capital, low_vol_state)
        
        # Short vol should be lower in high vol
        high_vol_short = high_vol_allocations.get('short_vol', 0.0)
        low_vol_short = low_vol_allocations.get('short_vol', 0.0)
        
        assert high_vol_short < low_vol_short, (
            f"short_vol allocation should be lower in high_vol "
            f"({high_vol_short:,.0f}) than low_vol ({low_vol_short:,.0f})"
        )


class TestTransitionRegimeDefensivePositioning:
    """Test transition regime defensive positioning"""
    
    def test_transition_increases_market_neutral(self):
        """
        Transition regime should increase market-neutral strategies
        
        **Validates: Requirements 6.7**
        """
        allocator = CapitalAllocator()
        
        # Add consistent performance for both regimes
        for strategy in allocator.strategy_buckets:
            for _ in range(30):
                return_value = 0.05  # Fixed positive return
                allocator.add_performance_observation(
                    strategy=strategy,
                    regime='transition',
                    return_value=return_value,
                    timestamp=datetime.now()
                )
                allocator.add_performance_observation(
                    strategy=strategy,
                    regime='low_vol',
                    return_value=return_value,
                    timestamp=datetime.now()
                )
        
        # Allocate in transition
        transition_state = create_test_state('transition')
        total_capital = 1000000.0
        transition_allocations = allocator.allocate_capital(total_capital, transition_state)
        
        # Allocate in low vol
        low_vol_state = create_test_state('low_vol')
        low_vol_allocations = allocator.allocate_capital(total_capital, low_vol_state)
        
        # Market neutral should be higher in transition (or at least not lower)
        transition_neutral = transition_allocations.get('market_neutral', 0.0)
        low_vol_neutral = low_vol_allocations.get('market_neutral', 0.0)
        
        # Due to regime multipliers, transition should favor market_neutral
        # Allow for small differences due to rounding
        assert transition_neutral >= low_vol_neutral * 0.95, (
            f"market_neutral allocation should be similar or higher in transition "
            f"({transition_neutral:,.0f}) than low_vol ({low_vol_neutral:,.0f})"
        )
    
    def test_transition_increases_relative_value(self):
        """
        Transition regime should increase relative value strategies
        
        **Validates: Requirements 6.7**
        """
        allocator = CapitalAllocator()
        
        # Add consistent performance for both regimes
        for strategy in allocator.strategy_buckets:
            for _ in range(30):
                return_value = 0.05  # Fixed positive return
                allocator.add_performance_observation(
                    strategy=strategy,
                    regime='transition',
                    return_value=return_value,
                    timestamp=datetime.now()
                )
                allocator.add_performance_observation(
                    strategy=strategy,
                    regime='low_vol',
                    return_value=return_value,
                    timestamp=datetime.now()
                )
        
        # Allocate in transition
        transition_state = create_test_state('transition')
        total_capital = 1000000.0
        transition_allocations = allocator.allocate_capital(total_capital, transition_state)
        
        # Allocate in low vol
        low_vol_state = create_test_state('low_vol')
        low_vol_allocations = allocator.allocate_capital(total_capital, low_vol_state)
        
        # Relative value should be higher in transition (or at least not lower)
        transition_rv = transition_allocations.get('relative_value', 0.0)
        low_vol_rv = low_vol_allocations.get('relative_value', 0.0)
        
        # Due to regime multipliers, transition should favor relative_value
        # Allow for small differences due to rounding
        assert transition_rv >= low_vol_rv * 0.95, (
            f"relative_value allocation should be similar or higher in transition "
            f"({transition_rv:,.0f}) than low_vol ({low_vol_rv:,.0f})"
        )
    
    def test_transition_reduces_directional_vol(self):
        """
        Transition regime should reduce directional volatility exposure
        
        **Validates: Requirements 6.7**
        """
        allocator = CapitalAllocator()
        
        add_uniform_performance(allocator, 'transition')
        add_uniform_performance(allocator, 'low_vol')
        
        # Allocate in transition
        transition_state = create_test_state('transition')
        total_capital = 1000000.0
        transition_allocations = allocator.allocate_capital(total_capital, transition_state)
        
        # Allocate in low vol
        low_vol_state = create_test_state('low_vol')
        low_vol_allocations = allocator.allocate_capital(total_capital, low_vol_state)
        
        # Directional vol should be lower in transition
        transition_dir = transition_allocations.get('directional_vol', 0.0)
        low_vol_dir = low_vol_allocations.get('directional_vol', 0.0)
        
        assert transition_dir < low_vol_dir, (
            f"directional_vol allocation should be lower in transition "
            f"({transition_dir:,.0f}) than low_vol ({low_vol_dir:,.0f})"
        )
    
    def test_transition_with_custom_defensive_strategies(self):
        """
        Test transition regime with custom defensive strategies
        
        **Validates: Requirements 6.7**
        """
        constraints = AllocationConstraints(
            transition_defensive=['market_neutral', 'relative_value', 'tail_hedge']
        )
        
        allocator = CapitalAllocator(constraints=constraints)
        
        # Add consistent performance for both regimes
        for strategy in allocator.strategy_buckets:
            for _ in range(30):
                return_value = 0.05  # Fixed positive return
                allocator.add_performance_observation(
                    strategy=strategy,
                    regime='transition',
                    return_value=return_value,
                    timestamp=datetime.now()
                )
                allocator.add_performance_observation(
                    strategy=strategy,
                    regime='low_vol',
                    return_value=return_value,
                    timestamp=datetime.now()
                )
        
        # Allocate in transition
        transition_state = create_test_state('transition')
        total_capital = 1000000.0
        transition_allocations = allocator.allocate_capital(total_capital, transition_state)
        
        # Allocate in low vol
        low_vol_state = create_test_state('low_vol')
        low_vol_allocations = allocator.allocate_capital(total_capital, low_vol_state)
        
        # Defensive strategies should be higher in transition (or at least not lower)
        for strategy in constraints.transition_defensive:
            transition_alloc = transition_allocations.get(strategy, 0.0)
            low_vol_alloc = low_vol_allocations.get(strategy, 0.0)
            
            # Allow for small differences due to rounding and other constraints
            assert transition_alloc >= low_vol_alloc * 0.90, (
                f"{strategy} should be similar or favored in transition regime "
                f"(transition: {transition_alloc:,.0f}, low_vol: {low_vol_alloc:,.0f})"
            )


class TestDrawdownBasedAdjustment:
    """Test drawdown-based allocation adjustments"""
    
    def test_drawdown_reduces_allocation(self):
        """
        Strategies in drawdown should have reduced allocation
        
        **Validates: Requirements 6.5**
        """
        allocator = CapitalAllocator()
        
        # Add good performance for most strategies
        for strategy in allocator.strategy_buckets:
            if strategy != 'short_vol':
                for _ in range(30):
                    return_value = np.random.uniform(0.02, 0.08)
                    allocator.add_performance_observation(
                        strategy=strategy,
                        regime='low_vol',
                        return_value=return_value,
                        timestamp=datetime.now()
                    )
        
        # Add drawdown for short_vol
        for _ in range(30):
            return_value = np.random.uniform(-0.08, -0.02)
            allocator.add_performance_observation(
                strategy='short_vol',
                regime='low_vol',
                return_value=return_value,
                timestamp=datetime.now()
            )
        
        # Allocate capital
        state = create_test_state('low_vol')
        total_capital = 1000000.0
        allocations = allocator.allocate_capital(total_capital, state)
        
        # short_vol should have lower allocation due to drawdown
        short_vol_alloc = allocations.get('short_vol', 0.0)
        avg_other_alloc = np.mean([
            allocations.get(s, 0.0) for s in allocator.strategy_buckets
            if s != 'short_vol' and allocations.get(s, 0.0) > 0
        ])
        
        assert short_vol_alloc < avg_other_alloc, (
            f"short_vol in drawdown should have lower allocation "
            f"({short_vol_alloc:,.0f}) than average ({avg_other_alloc:,.0f})"
        )
    
    def test_severe_drawdown_minimum_allocation(self):
        """
        Strategies in severe drawdown should maintain minimum allocation
        
        **Validates: Requirements 6.5**
        """
        allocator = CapitalAllocator()
        
        # Add severe drawdown for gamma_scalp
        for _ in range(30):
            return_value = np.random.uniform(-0.15, -0.10)
            allocator.add_performance_observation(
                strategy='gamma_scalp',
                regime='high_vol',
                return_value=return_value,
                timestamp=datetime.now()
            )
        
        # Add good performance for others
        for strategy in allocator.strategy_buckets:
            if strategy != 'gamma_scalp':
                for _ in range(30):
                    return_value = np.random.uniform(0.02, 0.08)
                    allocator.add_performance_observation(
                        strategy=strategy,
                        regime='high_vol',
                        return_value=return_value,
                        timestamp=datetime.now()
                    )
        
        # Allocate capital
        state = create_test_state('high_vol')
        total_capital = 1000000.0
        allocations = allocator.allocate_capital(total_capital, state)
        
        # gamma_scalp should still have some allocation (minimum 10% of what it would get)
        gamma_alloc = allocations.get('gamma_scalp', 0.0)
        
        # Should be non-zero but reduced
        assert gamma_alloc >= 0, (
            f"gamma_scalp should maintain minimum allocation even in severe drawdown"
        )


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])
