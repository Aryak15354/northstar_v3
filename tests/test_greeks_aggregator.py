"""
Unit tests for Portfolio Greeks Aggregator

Tests basic Greeks computation, portfolio aggregation, and constraint checking.
"""

import pytest
import numpy as np
from datetime import datetime, date, timedelta
from src.volatility.greeks_aggregator import (
    GreeksAggregator,
    Greeks,
    PortfolioGreeks,
    Position,
    GreeksLimits,
    ConstraintViolation,
    Scenario
)


@pytest.fixture
def aggregator():
    """Create Greeks aggregator instance"""
    return GreeksAggregator()


@pytest.fixture
def sample_call_position():
    """Create sample call position"""
    return Position(
        position_id="CALL_1",
        underlying="SPY",
        option_type="call",
        strike=450.0,
        expiry=date.today() + timedelta(days=30),
        quantity=10,
        spot_price=450.0,  # ATM
        implied_vol=0.20,
        risk_free_rate=0.05
    )


@pytest.fixture
def sample_put_position():
    """Create sample put position"""
    return Position(
        position_id="PUT_1",
        underlying="SPY",
        option_type="put",
        strike=450.0,
        expiry=date.today() + timedelta(days=30),
        quantity=10,
        spot_price=450.0,  # ATM
        implied_vol=0.20,
        risk_free_rate=0.05
    )


def test_greeks_zero():
    """Test zero Greeks creation"""
    greeks = Greeks.zero()
    assert greeks.delta == 0.0
    assert greeks.gamma == 0.0
    assert greeks.vega == 0.0
    assert greeks.theta == 0.0
    assert greeks.rho == 0.0


def test_greeks_addition():
    """Test Greeks addition"""
    g1 = Greeks(delta=0.5, gamma=0.1, vega=10.0, theta=-5.0, rho=2.0,
                vanna=0.01, volga=0.02, charm=0.001, vomma=0.02)
    g2 = Greeks(delta=0.3, gamma=0.05, vega=5.0, theta=-3.0, rho=1.0,
                vanna=0.005, volga=0.01, charm=0.0005, vomma=0.01)
    
    result = g1 + g2
    assert result.delta == pytest.approx(0.8)
    assert result.gamma == pytest.approx(0.15)
    assert result.vega == pytest.approx(15.0)
    assert result.theta == pytest.approx(-8.0)


def test_greeks_multiplication():
    """Test Greeks scalar multiplication"""
    g = Greeks(delta=0.5, gamma=0.1, vega=10.0, theta=-5.0, rho=2.0,
               vanna=0.01, volga=0.02, charm=0.001, vomma=0.02)
    
    result = g * 10
    assert result.delta == pytest.approx(5.0)
    assert result.gamma == pytest.approx(1.0)
    assert result.vega == pytest.approx(100.0)
    assert result.theta == pytest.approx(-50.0)


def test_compute_call_greeks_atm(aggregator, sample_call_position):
    """Test Greeks computation for ATM call"""
    greeks = aggregator.compute_position_greeks(sample_call_position)
    
    # ATM call should have delta around 0.5
    assert 0.4 < greeks.delta < 0.6
    
    # Gamma should be positive
    assert greeks.gamma > 0
    
    # Vega should be positive
    assert greeks.vega > 0
    
    # Theta should be negative (time decay)
    assert greeks.theta < 0


def test_compute_put_greeks_atm(aggregator, sample_put_position):
    """Test Greeks computation for ATM put"""
    greeks = aggregator.compute_position_greeks(sample_put_position)
    
    # ATM put should have delta around -0.5
    assert -0.6 < greeks.delta < -0.4
    
    # Gamma should be positive
    assert greeks.gamma > 0
    
    # Vega should be positive
    assert greeks.vega > 0
    
    # Theta should be negative (time decay)
    assert greeks.theta < 0


def test_expired_option_greeks(aggregator):
    """Test Greeks for expired option"""
    expired_position = Position(
        position_id="EXPIRED_1",
        underlying="SPY",
        option_type="call",
        strike=450.0,
        expiry=date.today() - timedelta(days=1),  # Expired
        quantity=10,
        spot_price=450.0,
        implied_vol=0.20,
        risk_free_rate=0.05
    )
    
    greeks = aggregator.compute_position_greeks(expired_position)
    
    # All Greeks should be zero for expired option
    assert greeks.delta == 0.0
    assert greeks.gamma == 0.0
    assert greeks.vega == 0.0
    assert greeks.theta == 0.0


def test_portfolio_greeks_single_position(aggregator, sample_call_position):
    """Test portfolio Greeks with single position"""
    portfolio_greeks = aggregator.compute_portfolio_greeks([sample_call_position])
    
    # Should have non-zero Greeks
    assert portfolio_greeks.delta != 0.0
    assert portfolio_greeks.gamma > 0
    assert portfolio_greeks.vega > 0
    
    # Should track by underlying
    assert "SPY" in portfolio_greeks.delta_by_underlying
    assert portfolio_greeks.delta_by_underlying["SPY"] != 0.0
    
    # Metadata
    assert portfolio_greeks.num_positions == 1


def test_portfolio_greeks_multiple_positions(aggregator, sample_call_position, sample_put_position):
    """Test portfolio Greeks with multiple positions"""
    positions = [sample_call_position, sample_put_position]
    portfolio_greeks = aggregator.compute_portfolio_greeks(positions)
    
    # Call and put at same strike should have offsetting deltas
    # Portfolio delta should be close to zero (straddle)
    assert abs(portfolio_greeks.delta) < 1.0
    
    # Gamma should be positive (sum of both)
    assert portfolio_greeks.gamma > 0
    
    # Vega should be positive (sum of both)
    assert portfolio_greeks.vega > 0
    
    # Should have 2 positions
    assert portfolio_greeks.num_positions == 2


def test_check_constraints_no_violations(aggregator, sample_call_position):
    """Test constraint checking with no violations"""
    portfolio_greeks = aggregator.compute_portfolio_greeks([sample_call_position])
    
    limits = GreeksLimits(
        max_delta=1000.0,
        max_gamma=100.0,
        max_vega=5000.0,
        max_theta=-500.0
    )
    
    violations = aggregator.check_constraints(portfolio_greeks, limits)
    assert len(violations) == 0


def test_check_constraints_delta_violation(aggregator):
    """Test constraint checking with delta violation"""
    # Create position with large delta
    large_position = Position(
        position_id="LARGE_1",
        underlying="SPY",
        option_type="call",
        strike=450.0,
        expiry=date.today() + timedelta(days=30),
        quantity=1000,  # Large quantity
        spot_price=450.0,
        implied_vol=0.20,
        risk_free_rate=0.05
    )
    
    portfolio_greeks = aggregator.compute_portfolio_greeks([large_position])
    
    limits = GreeksLimits(
        max_delta=100.0,  # Low limit
        max_gamma=1000.0,
        max_vega=50000.0
    )
    
    violations = aggregator.check_constraints(portfolio_greeks, limits)
    
    # Should have delta violation
    assert len(violations) > 0
    assert any(v.metric == "delta" for v in violations)


def test_scenario_greeks_spot_shift(aggregator, sample_call_position):
    """Test scenario Greeks with spot price shift"""
    scenario = Scenario(
        name="spot_up_10pct",
        spot_shift_pct=10.0,  # 10% up
        vol_shift_abs=0.0,
        time_shift_days=0
    )
    
    base_greeks = aggregator.compute_portfolio_greeks([sample_call_position])
    scenario_greeks = aggregator.scenario_greeks([sample_call_position], scenario)
    
    # Call delta should increase when spot goes up
    assert scenario_greeks.delta > base_greeks.delta


def test_scenario_greeks_vol_shift(aggregator, sample_call_position):
    """Test scenario Greeks with volatility shift"""
    scenario = Scenario(
        name="vol_up_5pct",
        spot_shift_pct=0.0,
        vol_shift_abs=0.05,  # +5% vol
        time_shift_days=0
    )
    
    base_greeks = aggregator.compute_portfolio_greeks([sample_call_position])
    scenario_greeks = aggregator.scenario_greeks([sample_call_position], scenario)
    
    # Vega should remain similar (vega doesn't change much with vol)
    # But option value would increase
    assert scenario_greeks.vega > 0


def test_scenario_greeks_time_decay(aggregator, sample_call_position):
    """Test scenario Greeks with time decay"""
    scenario = Scenario(
        name="one_day_forward",
        spot_shift_pct=0.0,
        vol_shift_abs=0.0,
        time_shift_days=1
    )
    
    base_greeks = aggregator.compute_portfolio_greeks([sample_call_position])
    scenario_greeks = aggregator.scenario_greeks([sample_call_position], scenario)
    
    # Vega should decrease as time passes (less time value)
    assert scenario_greeks.vega < base_greeks.vega


def test_greeks_decomposition(aggregator, sample_call_position, sample_put_position):
    """Test Greeks decomposition by position"""
    positions = [sample_call_position, sample_put_position]
    decomposition = aggregator.greeks_decomposition(positions)
    
    # Should have entry for each position
    assert "CALL_1" in decomposition
    assert "PUT_1" in decomposition
    
    # Each should have Greeks
    assert decomposition["CALL_1"].delta != 0.0
    assert decomposition["PUT_1"].delta != 0.0


def test_detect_anomalies_no_history(aggregator, sample_call_position):
    """Test anomaly detection with insufficient history"""
    current_greeks = aggregator.compute_portfolio_greeks([sample_call_position])
    historical_greeks = []  # No history
    
    anomalies = aggregator.detect_anomalies(current_greeks, historical_greeks)
    
    # Should return empty list with insufficient history
    assert len(anomalies) == 0


def test_detect_anomalies_normal(aggregator, sample_call_position):
    """Test anomaly detection with normal values"""
    current_greeks = aggregator.compute_portfolio_greeks([sample_call_position])
    
    # Create historical Greeks similar to current
    historical_greeks = [
        PortfolioGreeks(
            delta=current_greeks.delta + np.random.randn() * 0.1,
            gamma=current_greeks.gamma + np.random.randn() * 0.01,
            vega=current_greeks.vega + np.random.randn() * 1.0,
            theta=current_greeks.theta,
            rho=current_greeks.rho,
            vanna=0.0, volga=0.0, charm=0.0, vomma=0.0
        )
        for _ in range(20)
    ]
    
    anomalies = aggregator.detect_anomalies(current_greeks, historical_greeks)
    
    # Should not detect anomalies for normal values
    assert len(anomalies) == 0


def test_computation_performance(aggregator):
    """Test that Greeks computation meets performance target (<50ms)"""
    # Create 100 positions
    positions = [
        Position(
            position_id=f"POS_{i}",
            underlying="SPY",
            option_type="call" if i % 2 == 0 else "put",
            strike=450.0 + i,
            expiry=date.today() + timedelta(days=30),
            quantity=10,
            spot_price=450.0,
            implied_vol=0.20,
            risk_free_rate=0.05
        )
        for i in range(100)
    ]
    
    start = datetime.now()
    portfolio_greeks = aggregator.compute_portfolio_greeks(positions)
    elapsed_ms = (datetime.now() - start).total_seconds() * 1000
    
    # Should complete in under 50ms
    assert elapsed_ms < 50, f"Computation took {elapsed_ms:.1f}ms (target <50ms)"
    assert portfolio_greeks.num_positions == 100
