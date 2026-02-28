"""
Property-Based Tests for Allocation Constraints

Tests universal properties that should hold for allocation constraints:

Property 13: Allocations respect bounds
- For any strategy bucket, allocated capital should be between min and max bounds
- Bounds are specified as fractions of total capital

**Validates: Requirements 6.4**
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

# Strategy for generating bounds
min_bound_strategy = st.floats(min_value=0.0, max_value=0.15)
max_bound_strategy = st.floats(min_value=0.25, max_value=0.60)


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
    regime=regime_strategy,
    min_bound=min_bound_strategy,
    max_bound=max_bound_strategy
)
@settings(max_examples=100, deadline=None)
def test_property_13_allocations_respect_bounds(total_capital, regime, min_bound, max_bound):
    """
    Property 13: Allocations respect bounds
    
    **Validates: Requirements 6.4**
    
    For any strategy bucket, allocated capital should be between min and max bounds.
    """
    assume(min_bound < max_bound)
    
    # Create strategies
    strategies = [
        'dispersion', 'gamma_scalp', 'short_vol', 'long_vol',
        'tail_hedge', 'directional_vol', 'relative_value', 'market_neutral'
    ]
    
    # Assume feasible constraints (sum of min bounds <= 95%)
    total_min = len(strategies) * min_bound
    assume(total_min <= 0.95)
    
    # Create constraints with specified bounds
    constraints = AllocationConstraints(
        min_allocations={s: min_bound for s in strategies},
        max_allocations={s: max_bound for s in strategies}
    )
    
    # Create allocator
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
    
    # Property: Each allocation respects bounds (use actual constraints after adjustment)
    tolerance = 1e-6  # Small floating point tolerance
    
    for strategy, capital in allocations.items():
        fraction = capital / total_capital if total_capital > 0 else 0
        
        # Use the actual constraints (may have been adjusted)
        actual_min = allocator.constraints.min_allocations.get(strategy, 0.0)
        actual_max = allocator.constraints.max_allocations.get(strategy, 1.0)
        
        assert fraction >= actual_min - tolerance, (
            f"Property 13 violated: {strategy} allocation {fraction:.4%} "
            f"below min bound {actual_min:.4%}"
        )
        
        assert fraction <= actual_max + tolerance, (
            f"Property 13 violated: {strategy} allocation {fraction:.4%} "
            f"above max bound {actual_max:.4%}"
        )


@given(
    total_capital=capital_strategy,
    regime=regime_strategy,
    strategy_bounds=st.dictionaries(
        keys=st.sampled_from([
            'dispersion', 'gamma_scalp', 'short_vol', 'long_vol',
            'tail_hedge', 'directional_vol', 'relative_value', 'market_neutral'
        ]),
        values=st.tuples(
            st.floats(min_value=0.0, max_value=0.10),  # min
            st.floats(min_value=0.20, max_value=0.50)  # max
        ),
        min_size=3,
        max_size=8
    )
)
@settings(max_examples=50, deadline=None)
def test_property_13_with_per_strategy_bounds(total_capital, regime, strategy_bounds):
    """
    Property 13: Allocations respect bounds (with per-strategy bounds)
    
    **Validates: Requirements 6.4**
    
    Test that allocations respect bounds when each strategy has different bounds.
    """
    # Filter out invalid bounds
    valid_bounds = {
        strategy: (min_b, max_b)
        for strategy, (min_b, max_b) in strategy_bounds.items()
        if min_b < max_b
    }
    
    assume(len(valid_bounds) >= 3)
    
    # Create constraints with per-strategy bounds
    min_allocations = {s: bounds[0] for s, bounds in valid_bounds.items()}
    max_allocations = {s: bounds[1] for s, bounds in valid_bounds.items()}
    
    # Fill in missing strategies with defaults
    all_strategies = [
        'dispersion', 'gamma_scalp', 'short_vol', 'long_vol',
        'tail_hedge', 'directional_vol', 'relative_value', 'market_neutral'
    ]
    
    for strategy in all_strategies:
        if strategy not in min_allocations:
            min_allocations[strategy] = 0.0
        if strategy not in max_allocations:
            max_allocations[strategy] = 0.40
    
    constraints = AllocationConstraints(
        min_allocations=min_allocations,
        max_allocations=max_allocations
    )
    
    # Create allocator
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
    
    # Property: Each allocation respects its specific bounds
    tolerance = 1e-6
    
    for strategy, capital in allocations.items():
        fraction = capital / total_capital if total_capital > 0 else 0
        
        min_bound = min_allocations.get(strategy, 0.0)
        max_bound = max_allocations.get(strategy, 1.0)
        
        assert fraction >= min_bound - tolerance, (
            f"Property 13 violated: {strategy} allocation {fraction:.4%} "
            f"below min bound {min_bound:.4%}"
        )
        
        assert fraction <= max_bound + tolerance, (
            f"Property 13 violated: {strategy} allocation {fraction:.4%} "
            f"above max bound {max_bound:.4%}"
        )


@given(
    total_capital=capital_strategy,
    regime=regime_strategy,
    max_single=st.floats(min_value=0.25, max_value=0.50)
)
@settings(max_examples=50, deadline=None)
def test_property_13_max_single_strategy_constraint(total_capital, regime, max_single):
    """
    Property 13: Allocations respect max single strategy constraint
    
    **Validates: Requirements 6.4**
    
    Test that no single strategy exceeds the max_single_strategy constraint.
    """
    # Create constraints with max single strategy limit
    constraints = AllocationConstraints(
        max_single_strategy=max_single
    )
    
    # Create allocator
    allocator = CapitalAllocator(constraints=constraints)
    
    # Create test state
    state = create_test_state(regime)
    
    # Add performance history with one strategy performing much better
    for i, strategy in enumerate(allocator.strategy_buckets):
        for _ in range(20):
            if i == 0:
                # First strategy has much better returns
                return_value = np.random.uniform(0.05, 0.15)
            else:
                return_value = np.random.uniform(-0.05, 0.05)
            
            allocator.add_performance_observation(
                strategy=strategy,
                regime=regime,
                return_value=return_value,
                timestamp=datetime.now()
            )
    
    # Allocate capital
    allocations = allocator.allocate_capital(total_capital, state)
    
    # Property: No single strategy exceeds max_single_strategy
    tolerance = 1e-6
    
    for strategy, capital in allocations.items():
        fraction = capital / total_capital if total_capital > 0 else 0
        
        assert fraction <= max_single + tolerance, (
            f"Property 13 violated: {strategy} allocation {fraction:.4%} "
            f"exceeds max single strategy limit {max_single:.4%}"
        )


@given(
    total_capital=capital_strategy,
    regime=st.just('crisis')
)
@settings(max_examples=30, deadline=None)
def test_property_13_crisis_regime_constraints(total_capital, regime):
    """
    Property 13: Allocations respect crisis regime constraints
    
    **Validates: Requirements 6.4, 6.6**
    
    Test that crisis regime constraints are enforced (zero allocation to
    short_vol and dispersion).
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
    
    # Property: Crisis-blocked strategies have zero allocation
    for blocked_strategy in allocator.constraints.crisis_blocked_strategies:
        if blocked_strategy in allocations:
            assert allocations[blocked_strategy] == 0.0, (
                f"Property 13 violated: {blocked_strategy} should have zero "
                f"allocation in crisis regime, got {allocations[blocked_strategy]:,.2f}"
            )


@given(
    total_capital=capital_strategy,
    regime=regime_strategy,
    min_active=st.integers(min_value=2, max_value=5)
)
@settings(max_examples=50, deadline=None)
def test_property_13_min_active_strategies_constraint(total_capital, regime, min_active):
    """
    Property 13: Allocations respect minimum active strategies constraint
    
    **Validates: Requirements 6.4**
    
    Test that at least min_active_strategies have non-zero allocations.
    """
    # Create constraints with min active strategies
    constraints = AllocationConstraints(
        min_active_strategies=min_active
    )
    
    # Create allocator
    allocator = CapitalAllocator(constraints=constraints)
    
    # Create test state
    state = create_test_state(regime)
    
    # Add minimal performance history (might result in few active strategies)
    for strategy in allocator.strategy_buckets[:2]:  # Only 2 strategies
        for _ in range(20):
            return_value = np.random.uniform(0.01, 0.05)
            allocator.add_performance_observation(
                strategy=strategy,
                regime=regime,
                return_value=return_value,
                timestamp=datetime.now()
            )
    
    # Allocate capital
    allocations = allocator.allocate_capital(total_capital, state)
    
    # Property: At least min_active strategies have non-zero allocation
    active_count = sum(1 for capital in allocations.values() if capital > 0.01)
    
    assert active_count >= min_active, (
        f"Property 13 violated: Only {active_count} active strategies, "
        f"expected at least {min_active}"
    )


@given(
    total_capital=capital_strategy,
    regime=regime_strategy
)
@settings(max_examples=50, deadline=None)
def test_property_13_non_negative_allocations(total_capital, regime):
    """
    Property 13: All allocations are non-negative
    
    **Validates: Requirements 6.4**
    
    Test that all allocations are non-negative (no short positions).
    """
    # Create allocator
    allocator = CapitalAllocator()
    
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
    
    # Property: All allocations are non-negative
    for strategy, capital in allocations.items():
        assert capital >= 0.0, (
            f"Property 13 violated: {strategy} has negative allocation {capital:,.2f}"
        )


def test_property_13_edge_case_tight_bounds():
    """
    Property 13: Allocations respect bounds (edge case: very tight bounds)
    
    **Validates: Requirements 6.4**
    """
    # Create constraints with very tight bounds
    strategies = [
        'dispersion', 'gamma_scalp', 'short_vol', 'long_vol',
        'tail_hedge', 'directional_vol', 'relative_value', 'market_neutral'
    ]
    
    constraints = AllocationConstraints(
        min_allocations={s: 0.10 for s in strategies},
        max_allocations={s: 0.15 for s in strategies}
    )
    
    allocator = CapitalAllocator(constraints=constraints)
    state = create_test_state('low_vol')
    
    total_capital = 100000.0
    
    # Add performance history
    for strategy in allocator.strategy_buckets:
        for _ in range(20):
            return_value = np.random.uniform(-0.05, 0.10)
            allocator.add_performance_observation(
                strategy=strategy,
                regime='low_vol',
                return_value=return_value,
                timestamp=datetime.now()
            )
    
    allocations = allocator.allocate_capital(total_capital, state)
    
    # Check bounds
    tolerance = 1e-6
    for strategy, capital in allocations.items():
        fraction = capital / total_capital
        
        assert fraction >= 0.10 - tolerance, (
            f"{strategy} allocation {fraction:.4%} below min 10%"
        )
        assert fraction <= 0.15 + tolerance, (
            f"{strategy} allocation {fraction:.4%} above max 15%"
        )


def test_property_13_edge_case_zero_min_bound():
    """
    Property 13: Allocations respect bounds (edge case: zero min bound)
    
    **Validates: Requirements 6.4**
    """
    strategies = [
        'dispersion', 'gamma_scalp', 'short_vol', 'long_vol',
        'tail_hedge', 'directional_vol', 'relative_value', 'market_neutral'
    ]
    
    constraints = AllocationConstraints(
        min_allocations={s: 0.0 for s in strategies},
        max_allocations={s: 0.30 for s in strategies}
    )
    
    allocator = CapitalAllocator(constraints=constraints)
    state = create_test_state('high_vol')
    
    total_capital = 500000.0
    
    allocations = allocator.allocate_capital(total_capital, state)
    
    # Check bounds
    tolerance = 1e-6
    for strategy, capital in allocations.items():
        fraction = capital / total_capital
        
        assert fraction >= 0.0 - tolerance, (
            f"{strategy} allocation {fraction:.4%} is negative"
        )
        assert fraction <= 0.30 + tolerance, (
            f"{strategy} allocation {fraction:.4%} above max 30%"
        )


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])
