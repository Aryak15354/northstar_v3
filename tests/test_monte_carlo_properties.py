"""
Property-Based Tests for Monte Carlo Simulation Engine

Tests universal correctness properties using Hypothesis:
- Property 14: Simulated paths have correct mean (terminal price converges to forward price)
- Property 15: Volatility paths are non-negative (Heston model validation)

Validates: Requirements 7.1, 7.2, 13.4
"""

import pytest
import numpy as np
from datetime import datetime, date, timedelta
from hypothesis import given, strategies as st, settings, assume

from src.volatility.monte_carlo_engine import (
    MonteCarloEngine,
    HestonParams,
    SimulationResult
)


# Strategy for generating valid simulation parameters
@st.composite
def simulation_parameters(draw):
    """Generate valid parameters for Monte Carlo simulation"""
    spot = draw(st.floats(min_value=50.0, max_value=500.0))
    vol = draw(st.floats(min_value=0.10, max_value=0.60))
    horizon_days = draw(st.integers(min_value=5, max_value=60))
    risk_free_rate = draw(st.floats(min_value=0.0, max_value=0.10))
    
    return {
        'spot': spot,
        'vol': vol,
        'horizon_days': horizon_days,
        'risk_free_rate': risk_free_rate
    }


@st.composite
def heston_parameters(draw):
    """Generate valid Heston model parameters"""
    kappa = draw(st.floats(min_value=0.5, max_value=5.0))  # Mean reversion speed
    theta = draw(st.floats(min_value=0.01, max_value=0.10))  # Long-term variance
    sigma_v = draw(st.floats(min_value=0.1, max_value=0.8))  # Vol of vol
    rho = draw(st.floats(min_value=-0.9, max_value=-0.3))  # Correlation
    
    return HestonParams(
        kappa=kappa,
        theta=theta,
        sigma_v=sigma_v,
        rho=rho
    )


# Property 14: Simulated paths have correct mean
@given(params=simulation_parameters())
@settings(max_examples=50, deadline=None)
def test_property_terminal_price_mean_convergence(params):
    """
    **Validates: Requirements 7.1**
    
    Property 14: Simulated paths have correct mean
    
    For any large number of simulated price paths, the average terminal price 
    should converge to the forward price: E[S_T] = S_0 * exp(r*T)
    
    This validates that the drift in the geometric Brownian motion is correct.
    """
    spot = params['spot']
    vol = params['vol']
    horizon_days = params['horizon_days']
    risk_free_rate = params['risk_free_rate']
    
    # Create engine with single underlying
    engine = MonteCarloEngine(
        underlyings=['TEST'],
        risk_free_rate=risk_free_rate
    )
    
    # Generate price paths (use sufficient paths for convergence)
    num_paths = 1000
    price_paths = engine.generate_price_paths(
        spot_prices={'TEST': spot},
        volatilities={'TEST': vol},
        horizon_days=horizon_days,
        num_paths=num_paths,
        seed=42  # Fixed seed for reproducibility
    )
    
    # Extract terminal prices
    terminal_prices = price_paths[:, -1, 0]
    
    # Compute average terminal price
    avg_terminal_price = terminal_prices.mean()
    
    # Theoretical forward price: S_0 * exp(r*T)
    T = horizon_days / 252.0
    forward_price = spot * np.exp(risk_free_rate * T)
    
    # Check convergence (allow 10% tolerance due to finite sample size)
    relative_error = abs(avg_terminal_price - forward_price) / forward_price
    
    assert relative_error < 0.10, \
        f"Terminal price mean {avg_terminal_price:.2f} doesn't converge to forward price {forward_price:.2f} " \
        f"(relative error: {relative_error:.2%})"


@given(params=simulation_parameters())
@settings(max_examples=50, deadline=None)
def test_property_terminal_price_mean_convergence_multi_asset(params):
    """
    **Validates: Requirements 7.1**
    
    Property 14: Simulated paths have correct mean (multi-asset version)
    
    For multiple correlated assets, each should have terminal price mean 
    converging to its forward price independently.
    """
    spot = params['spot']
    vol = params['vol']
    horizon_days = params['horizon_days']
    risk_free_rate = params['risk_free_rate']
    
    # Create engine with multiple underlyings
    underlyings = ['ASSET1', 'ASSET2', 'ASSET3']
    correlation_matrix = np.array([
        [1.0, 0.5, 0.3],
        [0.5, 1.0, 0.4],
        [0.3, 0.4, 1.0]
    ])
    
    engine = MonteCarloEngine(
        underlyings=underlyings,
        correlation_matrix=correlation_matrix,
        risk_free_rate=risk_free_rate
    )
    
    # Generate price paths
    num_paths = 1000
    spot_prices = {u: spot * (1 + 0.1 * i) for i, u in enumerate(underlyings)}
    volatilities = {u: vol for u in underlyings}
    
    price_paths = engine.generate_price_paths(
        spot_prices=spot_prices,
        volatilities=volatilities,
        horizon_days=horizon_days,
        num_paths=num_paths,
        seed=42
    )
    
    # Check each asset
    T = horizon_days / 252.0
    for i, underlying in enumerate(underlyings):
        terminal_prices = price_paths[:, -1, i]
        avg_terminal_price = terminal_prices.mean()
        
        forward_price = spot_prices[underlying] * np.exp(risk_free_rate * T)
        relative_error = abs(avg_terminal_price - forward_price) / forward_price
        
        assert relative_error < 0.10, \
            f"Asset {underlying}: terminal price mean {avg_terminal_price:.2f} doesn't converge to " \
            f"forward price {forward_price:.2f} (relative error: {relative_error:.2%})"


# Property 15: Volatility paths are non-negative
@given(heston_params=heston_parameters())
@settings(max_examples=50, deadline=None)
def test_property_volatility_paths_non_negative(heston_params):
    """
    **Validates: Requirements 7.2**
    
    Property 15: Volatility paths are non-negative
    
    For any simulated volatility path using the Heston model, all volatility 
    values should be non-negative. This validates the full truncation scheme 
    in the Heston implementation.
    """
    # Create engine with Heston parameters
    engine = MonteCarloEngine(
        underlyings=['TEST'],
        heston_params=heston_params
    )
    
    # Generate volatility paths
    initial_variance = 0.04  # 20% vol
    horizon_days = 30
    num_paths = 100
    
    vol_paths = engine.generate_volatility_paths(
        initial_variance=initial_variance,
        horizon_days=horizon_days,
        num_paths=num_paths,
        seed=42
    )
    
    # Check all volatilities are non-negative
    min_vol = vol_paths.min()
    
    assert min_vol >= 0, \
        f"Volatility paths contain negative values: min = {min_vol:.6f}"
    
    # Also check no NaN or inf values
    assert not np.isnan(vol_paths).any(), "Volatility paths contain NaN values"
    assert not np.isinf(vol_paths).any(), "Volatility paths contain inf values"


@given(heston_params=heston_parameters())
@settings(max_examples=50, deadline=None)
def test_property_volatility_mean_reversion(heston_params):
    """
    **Validates: Requirements 7.2**
    
    Property 15 (extended): Volatility mean reversion
    
    For long-horizon simulations, the average volatility should converge 
    toward the long-term mean (theta) due to mean reversion.
    """
    # Create engine with Heston parameters
    engine = MonteCarloEngine(
        underlyings=['TEST'],
        heston_params=heston_params
    )
    
    # Generate long-horizon volatility paths
    initial_variance = 0.09  # 30% vol (far from theta)
    horizon_days = 252  # 1 year
    num_paths = 500
    
    vol_paths = engine.generate_volatility_paths(
        initial_variance=initial_variance,
        horizon_days=horizon_days,
        num_paths=num_paths,
        seed=42
    )
    
    # Compute average terminal variance
    terminal_vols = vol_paths[:, -1]
    avg_terminal_variance = (terminal_vols ** 2).mean()
    
    # Should be closer to theta than initial variance
    theta = heston_params.theta
    
    # Distance from theta
    initial_distance = abs(initial_variance - theta)
    terminal_distance = abs(avg_terminal_variance - theta)
    
    # Mean reversion should reduce distance (allow some tolerance)
    # For strong mean reversion (high kappa), this should be very effective
    if heston_params.kappa > 2.0:
        assert terminal_distance < initial_distance * 0.8, \
            f"Volatility didn't mean revert: initial distance {initial_distance:.4f}, " \
            f"terminal distance {terminal_distance:.4f}"


@given(params=simulation_parameters())
@settings(max_examples=50, deadline=None)
def test_property_price_paths_positive(params):
    """
    **Validates: Requirements 7.1**
    
    Additional property: Price paths are always positive
    
    Geometric Brownian motion should never produce negative prices.
    """
    spot = params['spot']
    vol = params['vol']
    horizon_days = params['horizon_days']
    risk_free_rate = params['risk_free_rate']
    
    # Create engine
    engine = MonteCarloEngine(
        underlyings=['TEST'],
        risk_free_rate=risk_free_rate
    )
    
    # Generate price paths
    num_paths = 100
    price_paths = engine.generate_price_paths(
        spot_prices={'TEST': spot},
        volatilities={'TEST': vol},
        horizon_days=horizon_days,
        num_paths=num_paths,
        seed=42
    )
    
    # Check all prices are positive
    min_price = price_paths.min()
    
    assert min_price > 0, \
        f"Price paths contain non-positive values: min = {min_price:.6f}"
    
    # Also check no NaN or inf values
    assert not np.isnan(price_paths).any(), "Price paths contain NaN values"
    assert not np.isinf(price_paths).any(), "Price paths contain inf values"


@given(params=simulation_parameters())
@settings(max_examples=50, deadline=None)
def test_property_correlation_preserved(params):
    """
    **Validates: Requirements 7.1**
    
    Additional property: Correlation structure is preserved
    
    For correlated assets, the realized correlation should match 
    the input correlation matrix (approximately).
    """
    spot = params['spot']
    vol = params['vol']
    horizon_days = params['horizon_days']
    risk_free_rate = params['risk_free_rate']
    
    # Skip very short horizons (not enough data for correlation)
    assume(horizon_days >= 20)
    
    # Create engine with correlated assets
    underlyings = ['ASSET1', 'ASSET2']
    target_correlation = 0.7
    correlation_matrix = np.array([
        [1.0, target_correlation],
        [target_correlation, 1.0]
    ])
    
    engine = MonteCarloEngine(
        underlyings=underlyings,
        correlation_matrix=correlation_matrix,
        risk_free_rate=risk_free_rate
    )
    
    # Generate price paths
    num_paths = 500
    spot_prices = {u: spot for u in underlyings}
    volatilities = {u: vol for u in underlyings}
    
    price_paths = engine.generate_price_paths(
        spot_prices=spot_prices,
        volatilities=volatilities,
        horizon_days=horizon_days,
        num_paths=num_paths,
        seed=42
    )
    
    # Compute returns for each path
    returns1 = np.diff(np.log(price_paths[:, :, 0]), axis=1)
    returns2 = np.diff(np.log(price_paths[:, :, 1]), axis=1)
    
    # Compute realized correlation across all paths
    all_returns1 = returns1.flatten()
    all_returns2 = returns2.flatten()
    
    realized_correlation = np.corrcoef(all_returns1, all_returns2)[0, 1]
    
    # Check correlation is approximately preserved (allow 20% tolerance)
    correlation_error = abs(realized_correlation - target_correlation)
    
    assert correlation_error < 0.20, \
        f"Correlation not preserved: target {target_correlation:.2f}, " \
        f"realized {realized_correlation:.2f} (error: {correlation_error:.2f})"


@given(params=simulation_parameters())
@settings(max_examples=50, deadline=None)
def test_property_risk_metrics_consistency(params):
    """
    **Validates: Requirements 13.4**
    
    Additional property: Risk metrics consistency
    
    VaR and CVaR should satisfy: CVaR <= VaR (CVaR is more conservative)
    """
    spot = params['spot']
    vol = params['vol']
    horizon_days = params['horizon_days']
    risk_free_rate = params['risk_free_rate']
    
    # Create engine
    engine = MonteCarloEngine(
        underlyings=['TEST'],
        risk_free_rate=risk_free_rate
    )
    
    # Run simulation
    simulation = engine.simulate_portfolio(
        spot_prices={'TEST': spot},
        volatilities={'TEST': vol},
        initial_portfolio_value=100000.0,
        horizon_days=horizon_days,
        num_paths=1000,
        seed=42
    )
    
    # Compute risk metrics
    risk_metrics = engine.compute_risk_metrics(simulation)
    
    # CVaR should be <= VaR (more negative, i.e., worse loss)
    assert risk_metrics.cvar_95 <= risk_metrics.var_95, \
        f"CVaR95 ({risk_metrics.cvar_95:.2f}) should be <= VaR95 ({risk_metrics.var_95:.2f})"
    
    assert risk_metrics.cvar_99 <= risk_metrics.var_99, \
        f"CVaR99 ({risk_metrics.cvar_99:.2f}) should be <= VaR99 ({risk_metrics.var_99:.2f})"
    
    # VaR should be ordered: VaR99.9 <= VaR99 <= VaR95
    assert risk_metrics.var_999 <= risk_metrics.var_99, \
        f"VaR99.9 ({risk_metrics.var_999:.2f}) should be <= VaR99 ({risk_metrics.var_99:.2f})"
    
    assert risk_metrics.var_99 <= risk_metrics.var_95, \
        f"VaR99 ({risk_metrics.var_99:.2f}) should be <= VaR95 ({risk_metrics.var_95:.2f})"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
