"""
Integration tests for Monte Carlo Engine

Tests the complete workflow of the Monte Carlo simulation engine.
"""

import pytest
import numpy as np
from datetime import datetime

from src.volatility.monte_carlo_engine import (
    MonteCarloEngine,
    HestonParams,
    SimulationResult,
    RiskMetrics
)


def test_single_asset_simulation():
    """Test basic single-asset Monte Carlo simulation"""
    # Create engine
    engine = MonteCarloEngine(
        underlyings=['SPY'],
        risk_free_rate=0.05
    )
    
    # Run simulation
    simulation = engine.simulate_portfolio(
        spot_prices={'SPY': 450.0},
        volatilities={'SPY': 0.20},
        initial_portfolio_value=100000.0,
        horizon_days=30,
        num_paths=1000,
        seed=42
    )
    
    # Verify simulation structure
    assert simulation.num_paths == 1000
    assert simulation.horizon_days == 30
    assert simulation.price_paths.shape == (1000, 30, 1)
    assert simulation.vol_paths.shape == (1000, 30)
    assert simulation.pnl_paths.shape == (1000, 30)
    
    # Verify all paths are valid
    assert not np.isnan(simulation.price_paths).any()
    assert not np.isnan(simulation.vol_paths).any()
    assert not np.isnan(simulation.pnl_paths).any()
    
    # Verify prices are positive
    assert (simulation.price_paths > 0).all()
    
    # Verify volatilities are non-negative
    assert (simulation.vol_paths >= 0).all()


def test_multi_asset_simulation():
    """Test multi-asset Monte Carlo simulation with correlation"""
    # Create correlation matrix
    correlation_matrix = np.array([
        [1.0, 0.6, 0.4],
        [0.6, 1.0, 0.5],
        [0.4, 0.5, 1.0]
    ])
    
    # Create engine
    engine = MonteCarloEngine(
        underlyings=['SPY', 'QQQ', 'IWM'],
        correlation_matrix=correlation_matrix,
        risk_free_rate=0.05
    )
    
    # Run simulation
    simulation = engine.simulate_portfolio(
        spot_prices={'SPY': 450.0, 'QQQ': 380.0, 'IWM': 200.0},
        volatilities={'SPY': 0.20, 'QQQ': 0.25, 'IWM': 0.30},
        initial_portfolio_value=100000.0,
        horizon_days=60,
        num_paths=500,
        seed=42
    )
    
    # Verify simulation structure
    assert simulation.num_paths == 500
    assert simulation.horizon_days == 60
    assert simulation.price_paths.shape == (500, 60, 3)
    
    # Verify all assets have positive prices
    for i in range(3):
        assert (simulation.price_paths[:, :, i] > 0).all()


def test_risk_metrics_computation():
    """Test risk metrics computation from simulation"""
    # Create engine
    engine = MonteCarloEngine(
        underlyings=['SPY'],
        risk_free_rate=0.05
    )
    
    # Run simulation
    simulation = engine.simulate_portfolio(
        spot_prices={'SPY': 450.0},
        volatilities={'SPY': 0.30},  # Higher vol for more interesting risk metrics
        initial_portfolio_value=100000.0,
        horizon_days=30,
        num_paths=10000,
        seed=42
    )
    
    # Compute risk metrics
    risk_metrics = engine.compute_risk_metrics(simulation)
    
    # Verify risk metrics structure
    assert isinstance(risk_metrics, RiskMetrics)
    assert hasattr(risk_metrics, 'var_95')
    assert hasattr(risk_metrics, 'var_99')
    assert hasattr(risk_metrics, 'var_999')
    assert hasattr(risk_metrics, 'cvar_95')
    assert hasattr(risk_metrics, 'cvar_99')
    assert hasattr(risk_metrics, 'max_drawdown')
    assert hasattr(risk_metrics, 'prob_ruin')
    
    # Verify VaR ordering: VaR99.9 <= VaR99 <= VaR95
    assert risk_metrics.var_999 <= risk_metrics.var_99
    assert risk_metrics.var_99 <= risk_metrics.var_95
    
    # Verify CVaR is more conservative than VaR
    assert risk_metrics.cvar_95 <= risk_metrics.var_95
    assert risk_metrics.cvar_99 <= risk_metrics.var_99
    
    # Verify max drawdown is negative or zero
    assert risk_metrics.max_drawdown <= 0
    
    # Verify probability of ruin is between 0 and 1
    assert 0 <= risk_metrics.prob_ruin <= 1


def test_heston_volatility_paths():
    """Test Heston stochastic volatility path generation"""
    # Create custom Heston parameters
    heston_params = HestonParams(
        kappa=2.5,
        theta=0.04,  # 20% long-term vol
        sigma_v=0.3,
        rho=-0.7
    )
    
    # Create engine
    engine = MonteCarloEngine(
        underlyings=['SPY'],
        heston_params=heston_params
    )
    
    # Generate volatility paths
    vol_paths = engine.generate_volatility_paths(
        initial_variance=0.09,  # 30% initial vol
        horizon_days=252,  # 1 year
        num_paths=1000,
        seed=42
    )
    
    # Verify shape
    assert vol_paths.shape == (1000, 252)
    
    # Verify all volatilities are non-negative
    assert (vol_paths >= 0).all()
    
    # Verify no NaN or inf
    assert not np.isnan(vol_paths).any()
    assert not np.isinf(vol_paths).any()
    
    # Verify mean reversion toward theta
    terminal_variance = (vol_paths[:, -1] ** 2).mean()
    # Should be closer to theta than initial variance
    assert abs(terminal_variance - heston_params.theta) < abs(0.09 - heston_params.theta)


def test_fat_tailed_distributions():
    """Test that Student-t distribution produces fatter tails than normal"""
    # Create engine
    engine = MonteCarloEngine(
        underlyings=['SPY'],
        risk_free_rate=0.05
    )
    
    # Generate many paths to see tail behavior
    price_paths = engine.generate_price_paths(
        spot_prices={'SPY': 450.0},
        volatilities={'SPY': 0.20},
        horizon_days=30,
        num_paths=10000,
        seed=42
    )
    
    # Compute returns
    terminal_prices = price_paths[:, -1, 0]
    returns = (terminal_prices / 450.0) - 1.0
    
    # Check for extreme moves (fat tails)
    # With Student-t(5), we should see more extreme moves than normal distribution
    extreme_moves = np.abs(returns) > 0.15  # 15% moves
    num_extreme = extreme_moves.sum()
    
    # Should have some extreme moves (fat tails)
    assert num_extreme > 0, "No extreme moves detected - tails may not be fat enough"


def test_correlation_matrix_validation():
    """Test that invalid correlation matrices are rejected"""
    # Test with wrong shape
    with pytest.raises(ValueError, match="doesn't match number of underlyings"):
        engine = MonteCarloEngine(
            underlyings=['SPY', 'QQQ'],
            correlation_matrix=np.eye(3)  # Wrong size
        )


def test_price_path_reproducibility():
    """Test that simulations are reproducible with same seed"""
    engine = MonteCarloEngine(
        underlyings=['SPY'],
        risk_free_rate=0.05
    )
    
    # Generate paths twice with same seed
    paths1 = engine.generate_price_paths(
        spot_prices={'SPY': 450.0},
        volatilities={'SPY': 0.20},
        horizon_days=30,
        num_paths=100,
        seed=42
    )
    
    paths2 = engine.generate_price_paths(
        spot_prices={'SPY': 450.0},
        volatilities={'SPY': 0.20},
        horizon_days=30,
        num_paths=100,
        seed=42
    )
    
    # Should be identical
    np.testing.assert_array_equal(paths1, paths2)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
