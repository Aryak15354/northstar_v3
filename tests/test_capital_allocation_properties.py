"""
Property-Based Tests for Capital Allocation

Tests universal properties that should hold for all capital allocations:

Property 12: Allocations sum to total capital
- For any capital allocation result, the sum of all strategy allocations
  should equal total available capital (within floating point tolerance)

**Validates: Requirements 6.1**
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from datetime import datetime, timedelta
import numpy as np

from src.volatility.capital_allocator import (
    CapitalAllocator,
    AllocationConstraints,
    PerformanceHistory
)
from src.volatility.state_engine import VolatilityState, RegimeState, AuthorityLevel
from src.volatility.regime_detector import VolatilityRegime


# Strategy for generating valid capital amounts
capital_strategy = st.floats(min_value=10000.0, max_value=10000000.0)

# Strategy for generating regime states
regime_strategy = st.sampled_from([
    'low_vol',
    'high_vol',
    'crisis',
    'transition',
    VolatilityRegime.LOW_VOL.value,
    VolatilityRegime.HIGH_VOL.value,
    VolatilityRegime.CRISIS.value,
    VolatilityRegime.TRANSITION.value
])

# Strategy for generating performance returns
returns_strategy = st.lists(
    st.floats(min_value=-0.10, max_value=0.15),  # -10% to +15% returns
    min_size=10,
    max_size=100
)


def create_test_state(regime: str) -> VolatilityState:
    """Create a test volatility state with specified regime"""
    regime_state = RegimeState(
        regime=regime,
        confidence=0.85,
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


@given(
    total_capital=capital_strategy,
    regime=regime_strategy
)
@settings(max_examples=100, deadline=None)
def test_property_12_allocations_sum_to_total_capital(total_capital, regime):
    """
    Property 12: Allocations sum to total capital
    
    **Validates: Requirements 6.1**
    
    For any capital allocation result, the sum of all strategy allocations
    should equal total available capital.
    """
    # Create allocator
    allocator = CapitalAllocator()
    
    # Create test state
    state = create_test_state(regime)
    
    # Add some performance history to enable Kelly calculations
    for strategy in allocator.strategy_buckets:
        for _ in range(20):
            return_value = np.random.uniform(-0.05, 0.10)
            allocator.add_performance_observation(
                strategy=strategy,
                regime=regime,
                return_value=return_value,
                timestamp=datetime.now()
            )
    
    # Allocate capital
    allocations = allocator.allocate_capital(total_capital, state)
    
    # Property: Sum of allocations equals total capital
    total_allocated = sum(allocations.values())
    
    # Allow small floating point tolerance (0.01 = 1 cent)
    tolerance = 0.01
    
    assert abs(total_allocated - total_capital) < tolerance, (
        f"Property 12 violated: Allocations sum to {total_allocated:,.2f}, "
        f"expected {total_capital:,.2f} (diff: {abs(total_allocated - total_capital):,.2f})"
    )


@given(
    total_capital=capital_strategy,
    regime=regime_strategy,
    returns_data=st.dictionaries(
        keys=st.sampled_from([
            'dispersion', 'gamma_scalp', 'short_vol', 'long_vol',
            'tail_hedge', 'directional_vol', 'relative_value', 'market_neutral'
        ]),
        values=returns_strategy,
        min_size=3,
        max_size=8
    )
)
@settings(max_examples=50, deadline=None)
def test_property_12_with_performance_history(total_capital, regime, returns_data):
    """
    Property 12: Allocations sum to total capital (with varied performance history)
    
    **Validates: Requirements 6.1, 6.2**
    
    Test that allocations sum to total capital even with varied performance
    histories across strategies.
    """
    # Create allocator
    allocator = CapitalAllocator()
    
    # Create test state
    state = create_test_state(regime)
    
    # Add performance history from generated data
    for strategy, returns in returns_data.items():
        for i, return_value in enumerate(returns):
            timestamp = datetime.now() - timedelta(days=len(returns) - i)
            allocator.add_performance_observation(
                strategy=strategy,
                regime=regime,
                return_value=return_value,
                timestamp=timestamp
            )
    
    # Allocate capital
    allocations = allocator.allocate_capital(total_capital, state)
    
    # Property: Sum of allocations equals total capital
    total_allocated = sum(allocations.values())
    tolerance = 0.01
    
    assert abs(total_allocated - total_capital) < tolerance, (
        f"Property 12 violated with performance history: "
        f"Allocations sum to {total_allocated:,.2f}, expected {total_capital:,.2f}"
    )


@given(
    total_capital=capital_strategy,
    regime=regime_strategy,
    kelly_fraction=st.floats(min_value=0.1, max_value=0.5)
)
@settings(max_examples=50, deadline=None)
def test_property_12_with_different_kelly_fractions(total_capital, regime, kelly_fraction):
    """
    Property 12: Allocations sum to total capital (with different Kelly fractions)
    
    **Validates: Requirements 6.1, 6.3**
    
    Test that allocations sum to total capital regardless of Kelly fraction setting.
    """
    # Create allocator with custom Kelly fraction
    allocator = CapitalAllocator(kelly_fraction=kelly_fraction)
    
    # Create test state
    state = create_test_state(regime)
    
    # Add performance history
    for strategy in allocator.strategy_buckets:
        for _ in range(20):
            return_value = np.random.uniform(-0.05, 0.10)
            allocator.add_performance_observation(
                strategy=strategy,
                regime=regime,
                return_value=return_value,
                timestamp=datetime.now()
            )
    
    # Allocate capital
    allocations = allocator.allocate_capital(total_capital, state)
    
    # Property: Sum of allocations equals total capital
    total_allocated = sum(allocations.values())
    tolerance = 0.01
    
    assert abs(total_allocated - total_capital) < tolerance, (
        f"Property 12 violated with kelly_fraction={kelly_fraction}: "
        f"Allocations sum to {total_allocated:,.2f}, expected {total_capital:,.2f}"
    )


@given(
    total_capital=capital_strategy,
    regime=regime_strategy
)
@settings(max_examples=50, deadline=None)
def test_property_12_with_zero_allocations(total_capital, regime):
    """
    Property 12: Allocations sum to total capital (even with zero performance data)
    
    **Validates: Requirements 6.1**
    
    Test that allocations sum to total capital even when strategies have no
    performance history (should distribute equally).
    """
    # Create allocator with no performance history
    allocator = CapitalAllocator()
    
    # Create test state
    state = create_test_state(regime)
    
    # Allocate capital without any performance history
    allocations = allocator.allocate_capital(total_capital, state)
    
    # Property: Sum of allocations equals total capital
    total_allocated = sum(allocations.values())
    tolerance = 0.01
    
    assert abs(total_allocated - total_capital) < tolerance, (
        f"Property 12 violated with no performance data: "
        f"Allocations sum to {total_allocated:,.2f}, expected {total_capital:,.2f}"
    )


@given(
    total_capital=capital_strategy,
    regime=regime_strategy,
    min_bound=st.floats(min_value=0.0, max_value=0.1),
    max_bound=st.floats(min_value=0.3, max_value=0.5)
)
@settings(max_examples=50, deadline=None)
def test_property_12_with_custom_bounds(total_capital, regime, min_bound, max_bound):
    """
    Property 12: Allocations sum to total capital (with custom bounds)
    
    **Validates: Requirements 6.1, 6.4**
    
    Test that allocations sum to total capital even with custom min/max bounds.
    """
    assume(min_bound < max_bound)
    
    # Create constraints with custom bounds
    strategies = [
        'dispersion', 'gamma_scalp', 'short_vol', 'long_vol',
        'tail_hedge', 'directional_vol', 'relative_value', 'market_neutral'
    ]
    
    constraints = AllocationConstraints(
        min_allocations={s: min_bound for s in strategies},
        max_allocations={s: max_bound for s in strategies}
    )
    
    # Create allocator with custom constraints
    allocator = CapitalAllocator(constraints=constraints)
    
    # Create test state
    state = create_test_state(regime)
    
    # Add performance history
    for strategy in allocator.strategy_buckets:
        for _ in range(20):
            return_value = np.random.uniform(-0.05, 0.10)
            allocator.add_performance_observation(
                strategy=strategy,
                regime=regime,
                return_value=return_value,
                timestamp=datetime.now()
            )
    
    # Allocate capital
    allocations = allocator.allocate_capital(total_capital, state)
    
    # Property: Sum of allocations equals total capital
    total_allocated = sum(allocations.values())
    tolerance = 0.01
    
    assert abs(total_allocated - total_capital) < tolerance, (
        f"Property 12 violated with custom bounds [{min_bound:.2%}, {max_bound:.2%}]: "
        f"Allocations sum to {total_allocated:,.2f}, expected {total_capital:,.2f}"
    )


@given(
    total_capital=capital_strategy,
    regime=st.just('crisis')  # Test specifically in crisis regime
)
@settings(max_examples=30, deadline=None)
def test_property_12_in_crisis_regime(total_capital, regime):
    """
    Property 12: Allocations sum to total capital (in crisis regime)
    
    **Validates: Requirements 6.1, 6.6**
    
    Test that allocations sum to total capital even in crisis regime where
    certain strategies are blocked.
    """
    # Create allocator
    allocator = CapitalAllocator()
    
    # Create crisis state
    state = create_test_state(regime)
    
    # Add performance history
    for strategy in allocator.strategy_buckets:
        for _ in range(20):
            return_value = np.random.uniform(-0.05, 0.10)
            allocator.add_performance_observation(
                strategy=strategy,
                regime=regime,
                return_value=return_value,
                timestamp=datetime.now()
            )
    
    # Allocate capital
    allocations = allocator.allocate_capital(total_capital, state)
    
    # Property: Sum of allocations equals total capital
    total_allocated = sum(allocations.values())
    tolerance = 0.01
    
    assert abs(total_allocated - total_capital) < tolerance, (
        f"Property 12 violated in crisis regime: "
        f"Allocations sum to {total_allocated:,.2f}, expected {total_capital:,.2f}"
    )
    
    # Additional check: short_vol and dispersion should be zero in crisis
    assert allocations.get('short_vol', 0.0) == 0.0, (
        "short_vol should be zero in crisis regime"
    )
    assert allocations.get('dispersion', 0.0) == 0.0, (
        "dispersion should be zero in crisis regime"
    )


def test_property_12_edge_case_very_small_capital():
    """
    Property 12: Allocations sum to total capital (edge case: very small capital)
    
    **Validates: Requirements 6.1**
    """
    allocator = CapitalAllocator()
    state = create_test_state('low_vol')
    
    # Very small capital
    total_capital = 100.0
    
    allocations = allocator.allocate_capital(total_capital, state)
    
    total_allocated = sum(allocations.values())
    tolerance = 0.01
    
    assert abs(total_allocated - total_capital) < tolerance, (
        f"Property 12 violated with small capital: "
        f"Allocations sum to {total_allocated:,.2f}, expected {total_capital:,.2f}"
    )


def test_property_12_edge_case_very_large_capital():
    """
    Property 12: Allocations sum to total capital (edge case: very large capital)
    
    **Validates: Requirements 6.1**
    """
    allocator = CapitalAllocator()
    state = create_test_state('high_vol')
    
    # Very large capital
    total_capital = 1_000_000_000.0  # 1 billion
    
    allocations = allocator.allocate_capital(total_capital, state)
    
    total_allocated = sum(allocations.values())
    tolerance = 0.01
    
    assert abs(total_allocated - total_capital) < tolerance, (
        f"Property 12 violated with large capital: "
        f"Allocations sum to {total_allocated:,.2f}, expected {total_capital:,.2f}"
    )


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])
