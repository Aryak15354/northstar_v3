"""
Unit tests for Performance Monitor

Tests P&L attribution, alpha/beta separation, and regime-conditional statistics.
"""

import pytest
import numpy as np
from datetime import datetime, date, timedelta
from src.volatility.performance_monitor import (
    PerformanceMonitor,
    GreeksPnL,
    VariancePnL,
    PerformanceAttribution,
    RegimePerformance,
    PerformanceDegradation
)
from src.volatility.greeks_aggregator import (
    PortfolioGreeks,
    Position
)


@pytest.fixture
def monitor():
    """Create performance monitor instance"""
    return PerformanceMonitor()


@pytest.fixture
def sample_greeks():
    """Create sample portfolio Greeks"""
    return PortfolioGreeks(
        delta=100.0,
        gamma=5.0,
        vega=200.0,
        theta=-10.0,
        rho=50.0,
        vanna=1.0,
        volga=2.0,
        charm=0.5,
        vomma=2.0
    )


@pytest.fixture
def sample_position():
    """Create sample position"""
    return Position(
        position_id="TEST_1",
        underlying="SPY",
        option_type="call",
        strike=450.0,
        expiry=date.today() + timedelta(days=30),
        quantity=10,
        spot_price=450.0,
        implied_vol=0.20,
        risk_free_rate=0.05
    )


def test_greeks_pnl_decomposition(monitor, sample_greeks):
    """Test Greeks P&L decomposition accuracy"""
    # Create previous and current Greeks
    previous_greeks = sample_greeks
    current_greeks = PortfolioGreeks(
        delta=105.0,
        gamma=5.2,
        vega=210.0,
        theta=-11.0,
        rho=52.0,
        vanna=1.1,
        volga=2.1,
        charm=0.55,
        vomma=2.1
    )
    
    # Market moves
    spot_change = 5.0  # $5 move
    vol_change = 0.02  # 2% vol increase
    time_elapsed = 1.0  # 1 day
    
    # Compute P&L
    pnl = monitor.compute_greeks_pnl(
        current_greeks,
        previous_greeks,
        spot_change,
        vol_change,
        time_elapsed
    )
    
    # Verify components
    assert pnl.delta_pnl == pytest.approx(100.0 * 5.0)  # delta * spot_change
    assert pnl.gamma_pnl == pytest.approx(0.5 * 5.0 * 5.0 ** 2)  # 0.5 * gamma * spot_change^2
    assert pnl.vega_pnl == pytest.approx(200.0 * 0.02 * 100)  # vega * vol_change * 100
    assert pnl.theta_pnl == pytest.approx(-10.0 * 1.0)  # theta * time
    
    # Total should sum correctly
    expected_total = pnl.delta_pnl + pnl.gamma_pnl + pnl.vega_pnl + pnl.theta_pnl
    assert pnl.total_pnl == pytest.approx(expected_total)


def test_greeks_pnl_negative_moves(monitor, sample_greeks):
    """Test Greeks P&L with negative market moves"""
    previous_greeks = sample_greeks
    current_greeks = sample_greeks
    
    # Negative spot move
    spot_change = -10.0
    vol_change = -0.05
    time_elapsed = 1.0
    
    pnl = monitor.compute_greeks_pnl(
        current_greeks,
        previous_greeks,
        spot_change,
        vol_change,
        time_elapsed
    )
    
    # Delta P&L should be negative (positive delta, negative move)
    assert pnl.delta_pnl < 0
    
    # Gamma P&L should be positive (long gamma benefits from moves)
    assert pnl.gamma_pnl > 0
    
    # Vega P&L should be negative (positive vega, vol decrease)
    assert pnl.vega_pnl < 0


def test_variance_pnl_tracking(monitor, sample_position):
    """Test realized vs implied variance tracking"""
    # Create price history with known volatility
    np.random.seed(42)
    initial_price = 450.0
    num_days = 20
    daily_vol = 0.25 / np.sqrt(252)  # 25% annual vol
    
    prices = [initial_price]
    for _ in range(num_days):
        ret = np.random.normal(0, daily_vol)
        prices.append(prices[-1] * np.exp(ret))
    
    entry_iv = 0.20  # Entered at 20% IV
    
    var_pnl = monitor.track_variance_pnl(
        sample_position,
        prices,
        entry_iv
    )
    
    # Realized variance should be computed
    assert var_pnl.realized_variance > 0
    
    # Implied variance should match entry
    assert var_pnl.implied_variance == pytest.approx(entry_iv ** 2)
    
    # If realized > implied, variance P&L should be positive for long position
    if var_pnl.realized_variance > var_pnl.implied_variance:
        assert var_pnl.variance_pnl > 0


def test_alpha_beta_separation(monitor):
    """Test alpha/beta separation in performance attribution"""
    # Create correlated returns
    np.random.seed(42)
    market_returns = np.random.normal(0.001, 0.02, 100)
    
    # Portfolio with beta=1.5 and alpha=0.0005
    beta = 1.5
    alpha = 0.0005
    portfolio_returns = alpha + beta * market_returns + np.random.normal(0, 0.01, 100)
    
    attribution = monitor.compute_performance_attribution(
        portfolio_returns.tolist(),
        market_returns.tolist(),
        risk_free_rate=0.05
    )
    
    # Beta should be close to 1.5
    assert 1.0 < attribution.beta < 2.0
    
    # Alpha should be positive
    assert attribution.alpha > 0
    
    # Total return should be sum of returns
    assert attribution.total_return == pytest.approx(np.sum(portfolio_returns), rel=0.01)


def test_performance_metrics(monitor):
    """Test performance statistics computation"""
    # Create returns with known properties
    np.random.seed(42)
    returns = np.random.normal(0.001, 0.02, 100)
    market_returns = np.random.normal(0.0008, 0.015, 100)
    
    attribution = monitor.compute_performance_attribution(
        returns.tolist(),
        market_returns.tolist()
    )
    
    # Sharpe ratio should be computed
    assert attribution.sharpe_ratio != 0
    
    # Sortino ratio should be computed
    assert attribution.sortino_ratio != 0
    
    # Win rate should be between 0 and 1
    assert 0 <= attribution.win_rate <= 1
    
    # Max drawdown should be negative or zero
    assert attribution.max_drawdown <= 0


def test_regime_conditional_performance(monitor):
    """Test regime-conditional statistics"""
    # Track performance in different regimes
    low_vol_returns = [0.01, 0.02, 0.015, 0.01, 0.02]
    high_vol_returns = [-0.02, 0.03, -0.01, 0.04, -0.015]
    
    low_vol_perf = monitor.track_regime_performance("low_vol", low_vol_returns)
    high_vol_perf = monitor.track_regime_performance("high_vol", high_vol_returns)
    
    # Low vol should have positive total return
    assert low_vol_perf.total_return > 0
    
    # High vol should have higher volatility
    assert low_vol_perf.sharpe_ratio != 0
    assert high_vol_perf.sharpe_ratio != 0
    
    # Win rates should be computed
    assert 0 <= low_vol_perf.win_rate <= 1
    assert 0 <= high_vol_perf.win_rate <= 1
    
    # Number of trades should match
    assert low_vol_perf.num_trades == len(low_vol_returns)
    assert high_vol_perf.num_trades == len(high_vol_returns)


def test_performance_degradation_detection(monitor):
    """Test performance degradation detection"""
    # Build historical returns
    np.random.seed(42)
    historical_returns = np.random.normal(0.002, 0.01, 60)
    for ret in historical_returns:
        monitor.record_return(ret)
    
    # Recent returns are worse
    recent_returns = np.random.normal(-0.001, 0.015, 20).tolist()
    
    degradations = monitor.detect_performance_degradation(recent_returns)
    
    # Should detect degradation
    assert len(degradations) > 0
    
    # Check degradation properties
    for deg in degradations:
        assert deg.metric in ["average_return", "sharpe_ratio", "win_rate"]
        assert deg.severity in ["LOW", "MEDIUM", "HIGH"]
        assert deg.deviation_pct < 0  # Negative deviation
        assert len(deg.recommendation) > 0


def test_no_degradation_when_improving(monitor):
    """Test no degradation detected when performance improves"""
    # Build historical returns
    np.random.seed(42)
    historical_returns = np.random.normal(0.001, 0.01, 60)
    for ret in historical_returns:
        monitor.record_return(ret)
    
    # Recent returns are better
    recent_returns = np.random.normal(0.003, 0.008, 20).tolist()
    
    degradations = monitor.detect_performance_degradation(recent_returns)
    
    # Should not detect degradation
    assert len(degradations) == 0


def test_performance_summary(monitor):
    """Test performance summary generation"""
    # Record some returns
    np.random.seed(42)
    returns = np.random.normal(0.001, 0.02, 50)
    for ret in returns:
        monitor.record_return(ret)
    
    summary = monitor.get_performance_summary()
    
    # Should have all key metrics
    assert "total_return" in summary
    assert "avg_return" in summary
    assert "volatility" in summary
    assert "sharpe_ratio" in summary
    assert "win_rate" in summary
    assert "num_observations" in summary
    
    # Values should be reasonable
    assert summary["num_observations"] == 50
    assert 0 <= summary["win_rate"] <= 1


def test_insufficient_data_handling(monitor):
    """Test handling of insufficient data"""
    # Empty history
    attribution = monitor.compute_performance_attribution([], [])
    assert attribution.alpha == 0.0
    assert attribution.beta == 0.0
    
    # Insufficient history for degradation
    degradations = monitor.detect_performance_degradation([0.01, 0.02])
    assert len(degradations) == 0
    
    # Empty summary
    summary = monitor.get_performance_summary()
    assert summary == {}


def test_greeks_pnl_history_tracking(monitor, sample_greeks):
    """Test that P&L history is tracked correctly"""
    previous_greeks = sample_greeks
    
    # Compute multiple P&L snapshots
    for i in range(10):
        current_greeks = sample_greeks
        pnl = monitor.compute_greeks_pnl(
            current_greeks,
            previous_greeks,
            spot_change=float(i),
            vol_change=0.01,
            time_elapsed_days=1.0
        )
    
    # History should be tracked
    assert len(monitor.greeks_pnl_history) == 10


def test_variance_pnl_with_minimal_data(monitor, sample_position):
    """Test variance P&L with minimal price data"""
    prices = [450.0]  # Only one price
    
    var_pnl = monitor.track_variance_pnl(sample_position, prices, 0.20)
    
    # Should handle gracefully
    assert var_pnl.realized_variance == 0.0
    assert var_pnl.implied_variance == pytest.approx(0.04)


def test_regime_performance_accumulation(monitor):
    """Test that regime performance accumulates correctly"""
    # Add returns in multiple batches
    monitor.track_regime_performance("low_vol", [0.01, 0.02])
    monitor.track_regime_performance("low_vol", [0.015, 0.01])
    
    perf = monitor.track_regime_performance("low_vol", [0.02])
    
    # Should accumulate all returns
    assert perf.num_trades == 5
    assert perf.total_return == pytest.approx(0.01 + 0.02 + 0.015 + 0.01 + 0.02)
