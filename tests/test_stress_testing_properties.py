"""
Property-Based Tests for Stress Testing Framework

Tests universal correctness properties using Hypothesis:
- Property 16: Portfolio survives stress scenarios

Validates: Requirements 7.6
"""

import pytest
import numpy as np
from datetime import datetime
from hypothesis import given, strategies as st, settings, assume

from src.volatility.monte_carlo_engine import (
    MonteCarloEngine,
    StressScenario,
    StressTestResult
)


# Strategy for generating valid portfolio parameters
@st.composite
def portfolio_parameters(draw):
    """Generate valid parameters for portfolio stress testing"""
    spot = draw(st.floats(min_value=50.0, max_value=500.0))
    vol = draw(st.floats(min_value=0.15, max_value=0.40))
    portfolio_value = draw(st.floats(min_value=50000.0, max_value=500000.0))
    
    return {
        'spot': spot,
        'vol': vol,
        'portfolio_value': portfolio_value
    }


@st.composite
def stress_scenario_parameters(draw):
    """Generate valid stress scenario parameters"""
    spot_shock = draw(st.floats(min_value=-0.50, max_value=-0.10))
    vol_shock = draw(st.floats(min_value=0.20, max_value=0.80))
    correlation_shock = draw(st.floats(min_value=0.70, max_value=0.98))
    liquidity_multiplier = draw(st.floats(min_value=2.0, max_value=8.0))
    
    return StressScenario(
        name="custom_stress",
        spot_shock=spot_shock,
        vol_shock=vol_shock,
        correlation_shock=correlation_shock,
        liquidity_multiplier=liquidity_multiplier,
        description="Custom stress scenario"
    )


# Property 16: Portfolio survives stress scenarios
@given(params=portfolio_parameters())
@settings(max_examples=30, deadline=None)
def test_property_portfolio_survives_stress_scenarios(params):
    """
    **Validates: Requirements 7.6**
    
    Property 16: Portfolio survives stress scenarios
    
    For any portfolio configuration, stress test P&L should not exceed 
    maximum loss threshold. This ensures the portfolio can survive 
    extreme market conditions.
    """
    spot = params['spot']
    vol = params['vol']
    portfolio_value = params['portfolio_value']
    
    # Create engine
    engine = MonteCarloEngine(
        underlyings=['TEST'],
        risk_free_rate=0.05
    )
    
    # Run all predefined stress tests
    max_loss_threshold = -0.25  # 25% maximum loss
    
    stress_results = engine.run_all_stress_tests(
        spot_prices={'TEST': spot},
        volatilities={'TEST': vol},
        initial_portfolio_value=portfolio_value,
        max_loss_threshold=max_loss_threshold
    )
    
    # Check each stress scenario
    for scenario_name, result in stress_results.items():
        # P&L change should not exceed threshold
        assert result.pnl_change_pct > max_loss_threshold, \
            f"Portfolio fails {scenario_name}: loss {result.pnl_change_pct:.2%} exceeds " \
            f"threshold {max_loss_threshold:.2%}"
        
        # Survival flag should be consistent
        expected_survival = result.pnl_change_pct > max_loss_threshold
        assert result.survives == expected_survival, \
            f"Survival flag inconsistent for {scenario_name}: " \
            f"survives={result.survives}, pnl_change_pct={result.pnl_change_pct:.2%}"


@given(params=portfolio_parameters(), scenario=stress_scenario_parameters())
@settings(max_examples=30, deadline=None)
def test_property_stress_pnl_bounded(params, scenario):
    """
    **Validates: Requirements 7.6**
    
    Property 16 (extended): Stress P&L is bounded
    
    For any stress scenario, the P&L change should be bounded by the 
    spot shock magnitude. A 40% price decline cannot cause more than 
    100% portfolio loss (assuming no leverage).
    """
    spot = params['spot']
    vol = params['vol']
    portfolio_value = params['portfolio_value']
    
    # Create engine
    engine = MonteCarloEngine(
        underlyings=['TEST'],
        risk_free_rate=0.05
    )
    
    # Execute stress test
    result = engine.execute_stress_test(
        scenario=scenario,
        spot_prices={'TEST': spot},
        volatilities={'TEST': vol},
        initial_portfolio_value=portfolio_value,
        max_loss_threshold=-0.25
    )
    
    # P&L change should be bounded
    # Maximum loss should not exceed 100% (total portfolio wipeout)
    assert result.pnl_change_pct > -1.0, \
        f"Stress P&L exceeds 100% loss: {result.pnl_change_pct:.2%}"
    
    # P&L change should be related to spot shock magnitude
    # (allowing for volatility effects)
    max_expected_loss = abs(scenario.spot_shock) * 2.0  # 2x buffer for vol effects
    assert result.pnl_change_pct > -max_expected_loss, \
        f"Stress P&L {result.pnl_change_pct:.2%} exceeds expected bound " \
        f"{-max_expected_loss:.2%} for spot shock {scenario.spot_shock:.2%}"


@given(params=portfolio_parameters())
@settings(max_examples=30, deadline=None)
def test_property_combined_crisis_worst_case(params):
    """
    **Validates: Requirements 7.6**
    
    Property 16 (extended): Combined crisis has largest shocks
    
    The combined crisis scenario should have the most severe market shocks
    (largest spot decline, highest volatility, highest correlation).
    """
    spot = params['spot']
    vol = params['vol']
    portfolio_value = params['portfolio_value']
    
    # Create engine
    engine = MonteCarloEngine(
        underlyings=['TEST'],
        risk_free_rate=0.05
    )
    
    # Get scenarios
    crisis_2008 = engine.create_crisis_2008_scenario()
    crisis_2020 = engine.create_crisis_2020_scenario()
    combined_crisis = engine.create_combined_crisis_scenario()
    
    # Combined crisis should have worst shocks
    assert combined_crisis.spot_shock <= crisis_2008.spot_shock, \
        f"Combined crisis spot shock ({combined_crisis.spot_shock:.2%}) should be worse than " \
        f"2008 crisis ({crisis_2008.spot_shock:.2%})"
    
    assert combined_crisis.spot_shock <= crisis_2020.spot_shock, \
        f"Combined crisis spot shock ({combined_crisis.spot_shock:.2%}) should be worse than " \
        f"2020 crisis ({crisis_2020.spot_shock:.2%})"
    
    assert combined_crisis.vol_shock >= crisis_2008.vol_shock, \
        f"Combined crisis vol shock ({combined_crisis.vol_shock:.2f}) should be >= " \
        f"2008 crisis ({crisis_2008.vol_shock:.2f})"
    
    assert combined_crisis.vol_shock >= crisis_2020.vol_shock, \
        f"Combined crisis vol shock ({combined_crisis.vol_shock:.2f}) should be >= " \
        f"2020 crisis ({crisis_2020.vol_shock:.2f})"
    
    assert combined_crisis.correlation_shock >= crisis_2008.correlation_shock, \
        f"Combined crisis correlation ({combined_crisis.correlation_shock:.2f}) should be >= " \
        f"2008 crisis ({crisis_2008.correlation_shock:.2f})"


@given(params=portfolio_parameters())
@settings(max_examples=30, deadline=None)
def test_property_stress_test_deterministic(params):
    """
    **Validates: Requirements 7.6**
    
    Additional property: Stress tests are deterministic
    
    Running the same stress test twice with the same seed should 
    produce identical results.
    """
    spot = params['spot']
    vol = params['vol']
    portfolio_value = params['portfolio_value']
    
    # Create engine
    engine = MonteCarloEngine(
        underlyings=['TEST'],
        risk_free_rate=0.05
    )
    
    scenario = engine.create_crisis_2008_scenario()
    
    # Run stress test twice
    result1 = engine.execute_stress_test(
        scenario=scenario,
        spot_prices={'TEST': spot},
        volatilities={'TEST': vol},
        initial_portfolio_value=portfolio_value
    )
    
    result2 = engine.execute_stress_test(
        scenario=scenario,
        spot_prices={'TEST': spot},
        volatilities={'TEST': vol},
        initial_portfolio_value=portfolio_value
    )
    
    # Results should be identical (within floating point precision)
    assert abs(result1.pnl_change - result2.pnl_change) < 1e-6, \
        f"Stress test not deterministic: {result1.pnl_change:.2f} vs {result2.pnl_change:.2f}"
    
    assert abs(result1.pnl_change_pct - result2.pnl_change_pct) < 1e-9, \
        f"Stress test not deterministic: {result1.pnl_change_pct:.6%} vs {result2.pnl_change_pct:.6%}"


@given(params=portfolio_parameters())
@settings(max_examples=30, deadline=None)
def test_property_max_drawdown_consistency(params):
    """
    **Validates: Requirements 7.6**
    
    Additional property: Max drawdown consistency
    
    Maximum drawdown from stress test should be consistent with P&L change.
    """
    spot = params['spot']
    vol = params['vol']
    portfolio_value = params['portfolio_value']
    
    # Create engine
    engine = MonteCarloEngine(
        underlyings=['TEST'],
        risk_free_rate=0.05
    )
    
    # Run stress test
    result = engine.execute_stress_test(
        scenario=engine.create_combined_crisis_scenario(),
        spot_prices={'TEST': spot},
        volatilities={'TEST': vol},
        initial_portfolio_value=portfolio_value
    )
    
    # Max drawdown should be negative (loss)
    assert result.max_drawdown <= 0, \
        f"Max drawdown should be negative: {result.max_drawdown:.2%}"
    
    # Max drawdown should be at least as bad as terminal P&L change
    # (drawdown captures worst point, which could be worse than terminal)
    assert result.max_drawdown <= result.pnl_change_pct, \
        f"Max drawdown ({result.max_drawdown:.2%}) should be <= terminal P&L " \
        f"({result.pnl_change_pct:.2%})"


@given(params=portfolio_parameters())
@settings(max_examples=30, deadline=None)
def test_property_correlation_shock_effect(params):
    """
    **Validates: Requirements 7.6**
    
    Additional property: Correlation shock increases losses
    
    Higher correlation shocks should lead to worse or equal losses 
    (all assets moving together amplifies risk).
    """
    spot = params['spot']
    vol = params['vol']
    portfolio_value = params['portfolio_value']
    
    # Create engine with multiple assets
    underlyings = ['ASSET1', 'ASSET2']
    correlation_matrix = np.array([
        [1.0, 0.5],
        [0.5, 1.0]
    ])
    
    engine = MonteCarloEngine(
        underlyings=underlyings,
        correlation_matrix=correlation_matrix,
        risk_free_rate=0.05
    )
    
    spot_prices = {u: spot for u in underlyings}
    volatilities = {u: vol for u in underlyings}
    
    # Test with low correlation shock
    low_corr_scenario = StressScenario(
        name="low_correlation",
        spot_shock=-0.30,
        vol_shock=0.40,
        correlation_shock=0.70,
        liquidity_multiplier=3.0,
        description="Low correlation shock"
    )
    
    # Test with high correlation shock
    high_corr_scenario = StressScenario(
        name="high_correlation",
        spot_shock=-0.30,  # Same spot shock
        vol_shock=0.40,  # Same vol shock
        correlation_shock=0.95,  # Higher correlation
        liquidity_multiplier=3.0,
        description="High correlation shock"
    )
    
    result_low = engine.execute_stress_test(
        scenario=low_corr_scenario,
        spot_prices=spot_prices,
        volatilities=volatilities,
        initial_portfolio_value=portfolio_value
    )
    
    result_high = engine.execute_stress_test(
        scenario=high_corr_scenario,
        spot_prices=spot_prices,
        volatilities=volatilities,
        initial_portfolio_value=portfolio_value
    )
    
    # Higher correlation should lead to worse or equal losses
    # (allowing small tolerance for simulation variance)
    assert result_high.pnl_change_pct <= result_low.pnl_change_pct + 0.05, \
        f"High correlation ({result_high.pnl_change_pct:.2%}) should produce worse " \
        f"losses than low correlation ({result_low.pnl_change_pct:.2%})"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
