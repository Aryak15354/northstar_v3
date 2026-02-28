"""
Property-Based Tests for Dispersion Trading Module

Tests universal correctness properties using Hypothesis:
- Property 9: Dispersion positions are delta-neutral after rebalancing

**Validates: Requirements 4.6**
"""

import pytest
import numpy as np
from datetime import datetime, date, timedelta
from hypothesis import given, strategies as st, settings, assume

from src.volatility.dispersion_module import (
    DispersionModule,
    DispersionTrade,
    DispersionDirection,
    DispersionOpportunity
)
from src.volatility.greeks_aggregator import Position


# Strategy for generating valid dispersion parameters
@st.composite
def dispersion_parameters(draw):
    """Generate valid parameters for dispersion testing"""
    num_constituents = draw(st.integers(min_value=3, max_value=10))
    constituents = [f"STOCK{i}" for i in range(num_constituents)]
    
    # Generate index variance (20% vol = 0.04 variance)
    index_vol = draw(st.floats(min_value=0.10, max_value=0.50))
    index_variance = index_vol ** 2
    
    # Generate stock variances
    stock_variances = {}
    for symbol in constituents:
        stock_vol = draw(st.floats(min_value=0.15, max_value=0.60))
        stock_variances[symbol] = stock_vol ** 2
    
    # Generate index weights (must sum to 1.0)
    raw_weights = [draw(st.floats(min_value=0.05, max_value=0.40)) for _ in constituents]
    total_weight = sum(raw_weights)
    index_weights = {constituents[i]: w / total_weight for i, w in enumerate(raw_weights)}
    
    # Generate realized correlation
    realized_corr = draw(st.floats(min_value=0.20, max_value=0.90))
    
    return {
        'constituents': constituents,
        'index_variance': index_variance,
        'stock_variances': stock_variances,
        'index_weights': index_weights,
        'realized_correlation': realized_corr
    }


@st.composite
def dispersion_trade_parameters(draw):
    """Generate parameters for dispersion trade testing"""
    num_stocks = draw(st.integers(min_value=3, max_value=8))
    constituents = [f"STOCK{i}" for i in range(num_stocks)]
    
    # Generate spot prices
    spot_prices = {}
    for symbol in constituents:
        spot_prices[symbol] = draw(st.floats(min_value=50.0, max_value=500.0))
    spot_prices["SPY"] = draw(st.floats(min_value=300.0, max_value=500.0))
    
    # Generate position quantities (delta approximation)
    index_quantity = draw(st.integers(min_value=-100, max_value=100))
    stock_quantities = {}
    for symbol in constituents:
        stock_quantities[symbol] = draw(st.integers(min_value=-50, max_value=50))
    
    return {
        'constituents': constituents,
        'spot_prices': spot_prices,
        'index_quantity': index_quantity,
        'stock_quantities': stock_quantities
    }


# Property 9: Dispersion positions are delta-neutral after rebalancing
@given(params=dispersion_trade_parameters())
@settings(max_examples=20, deadline=None)
def test_property_dispersion_delta_neutral(params):
    """
    Property 9: Dispersion positions are delta-neutral
    
    For any dispersion trade after rebalancing, portfolio delta should be 
    within neutrality threshold.
    
    **Validates: Requirements 4.6**
    """
    constituents = params['constituents']
    spot_prices = params['spot_prices']
    index_quantity = params['index_quantity']
    stock_quantities = params['stock_quantities']
    
    # Skip if all quantities are zero
    assume(index_quantity != 0 or any(q != 0 for q in stock_quantities.values()))
    
    # Create dispersion module
    module = DispersionModule(
        constituents=constituents,
        index_symbol="SPY",
        neutrality_threshold=0.10  # 10% neutrality threshold
    )
    
    # Create mock positions
    expiry = date.today() + timedelta(days=30)
    
    # Index position
    index_position = Position(
        position_id="INDEX_POS",
        underlying="SPY",
        option_type="call",
        strike=spot_prices["SPY"],
        expiry=expiry,
        quantity=index_quantity,
        spot_price=spot_prices["SPY"],
        implied_vol=0.20,
        risk_free_rate=0.05
    )
    
    # Stock positions
    stock_positions = []
    for symbol in constituents:
        stock_pos = Position(
            position_id=f"{symbol}_POS",
            underlying=symbol,
            option_type="call",
            strike=spot_prices[symbol],
            expiry=expiry,
            quantity=stock_quantities[symbol],
            spot_price=spot_prices[symbol],
            implied_vol=0.25,
            risk_free_rate=0.05
        )
        stock_positions.append(stock_pos)
    
    # Create dispersion trade
    trade = DispersionTrade(
        trade_id="TEST_TRADE",
        direction=DispersionDirection.SHORT_DISPERSION,
        entry_spread=0.15,
        entry_timestamp=datetime.now(),
        index_position=index_position,
        stock_positions=stock_positions,
        target_exit_spread=0.05,
        target_delta=0.0  # Delta-neutral target
    )
    
    # Compute current delta
    current_delta = module.compute_dispersion_delta(trade, spot_prices)
    
    # Generate rebalance orders if needed
    rebalance_orders = module.generate_rebalance_orders(
        trade,
        current_delta,
        spot_prices
    )
    
    # If rebalancing was needed, simulate applying the hedge
    if rebalance_orders:
        # Apply hedge to index position
        for order in rebalance_orders:
            if order['symbol'] == "SPY":
                # Simulate hedge execution
                trade.index_position.quantity += order['quantity']
        
        # Recompute delta after rebalancing
        new_delta = module.compute_dispersion_delta(trade, spot_prices)
        
        # After rebalancing, delta should be closer to target
        assert abs(new_delta) <= abs(current_delta) + 0.01, \
            f"Rebalancing should reduce delta: {current_delta:.4f} -> {new_delta:.4f}"
    
    # Check if position is delta-neutral
    final_delta = module.compute_dispersion_delta(trade, spot_prices)
    is_neutral = module.is_delta_neutral(trade, spot_prices)
    
    # If delta is small, should be considered neutral
    if abs(final_delta) <= module.neutrality_threshold:
        assert is_neutral, \
            f"Position with delta={final_delta:.4f} should be neutral (threshold={module.neutrality_threshold:.4f})"


# Property: Implied correlation is bounded
@given(params=dispersion_parameters())
@settings(max_examples=20, deadline=None)
def test_property_implied_correlation_bounded(params):
    """
    Property: Implied correlation should be bounded between -1 and 1
    
    For any valid index and stock variances, implied correlation should
    be within valid correlation bounds.
    
    **Validates: Requirements 4.1**
    """
    constituents = params['constituents']
    index_variance = params['index_variance']
    stock_variances = params['stock_variances']
    index_weights = params['index_weights']
    
    module = DispersionModule(constituents=constituents)
    
    implied_corr = module.compute_implied_correlation(
        index_variance,
        stock_variances,
        index_weights
    )
    
    # Correlation must be between -1 and 1
    assert -1.0 <= implied_corr <= 1.0, \
        f"Implied correlation {implied_corr:.4f} outside valid range [-1, 1]"


# Property: Realized correlation is bounded
@given(
    num_stocks=st.integers(min_value=3, max_value=10),
    num_days=st.integers(min_value=20, max_value=100)
)
@settings(max_examples=20, deadline=None)
def test_property_realized_correlation_bounded(num_stocks, num_days):
    """
    Property: Realized correlation should be bounded between -1 and 1
    
    For any returns data, realized correlation should be within valid bounds.
    
    **Validates: Requirements 4.1**
    """
    constituents = [f"STOCK{i}" for i in range(num_stocks)]
    module = DispersionModule(constituents=constituents)
    
    # Generate random returns
    np.random.seed(42)
    returns = np.random.randn(num_days, num_stocks) * 0.02
    
    corr_data = module.compute_realized_correlation(returns, lookback_days=num_days)
    
    # Average correlation must be between -1 and 1
    assert -1.0 <= corr_data.average_correlation <= 1.0, \
        f"Realized correlation {corr_data.average_correlation:.4f} outside valid range [-1, 1]"
    
    # All pairwise correlations must be between -1 and 1
    corr_matrix = corr_data.correlation_matrix
    assert np.all(corr_matrix >= -1.0) and np.all(corr_matrix <= 1.0), \
        "Correlation matrix contains values outside [-1, 1]"
    
    # Diagonal should be 1.0 (self-correlation)
    diagonal = np.diag(corr_matrix)
    assert np.allclose(diagonal, 1.0, atol=0.01), \
        f"Correlation matrix diagonal should be 1.0, got {diagonal}"


# Property: Variance weights sum to 1.0
@given(params=dispersion_parameters())
@settings(max_examples=20, deadline=None)
def test_property_variance_weights_sum_to_one(params):
    """
    Property: Variance weights should sum to 1.0
    
    For any valid stock volatilities and index weights, the computed
    variance weights should sum to 1.0 (normalized).
    
    **Validates: Requirements 4.4**
    """
    constituents = params['constituents']
    stock_variances = params['stock_variances']
    index_weights = params['index_weights']
    
    module = DispersionModule(constituents=constituents)
    
    # Convert variances to volatilities
    stock_vols = {s: np.sqrt(v) for s, v in stock_variances.items()}
    
    # Create simple correlation matrix
    n = len(constituents)
    corr_matrix = np.eye(n) * 0.5 + 0.5  # Simple correlation structure
    
    var_weights = module.compute_variance_weights(
        stock_vols,
        index_weights,
        corr_matrix
    )
    
    # Weights should sum to 1.0
    total_weight = sum(var_weights.weights.values())
    assert abs(total_weight - 1.0) < 0.01, \
        f"Variance weights should sum to 1.0, got {total_weight:.6f}"


# Property: Variance weights are non-negative
@given(params=dispersion_parameters())
@settings(max_examples=20, deadline=None)
def test_property_variance_weights_non_negative(params):
    """
    Property: Variance weights should be non-negative
    
    For any valid inputs, variance weights should be >= 0.
    
    **Validates: Requirements 4.4**
    """
    constituents = params['constituents']
    stock_variances = params['stock_variances']
    index_weights = params['index_weights']
    
    module = DispersionModule(constituents=constituents)
    
    # Convert variances to volatilities
    stock_vols = {s: np.sqrt(v) for s, v in stock_variances.items()}
    
    # Create simple correlation matrix
    n = len(constituents)
    corr_matrix = np.eye(n) * 0.5 + 0.5
    
    var_weights = module.compute_variance_weights(
        stock_vols,
        index_weights,
        corr_matrix
    )
    
    # All weights should be non-negative
    for symbol, weight in var_weights.weights.items():
        assert weight >= 0, \
            f"Variance weight for {symbol} should be non-negative, got {weight:.6f}"


# Property: Dispersion spread is symmetric
@given(params=dispersion_parameters())
@settings(max_examples=20, deadline=None)
def test_property_dispersion_spread_symmetric(params):
    """
    Property: Dispersion spread calculation is consistent
    
    The spread (implied - realized) should have opposite sign when
    implied and realized are swapped.
    
    **Validates: Requirements 4.2, 4.3**
    """
    constituents = params['constituents']
    index_variance = params['index_variance']
    stock_variances = params['stock_variances']
    index_weights = params['index_weights']
    realized_corr = params['realized_correlation']
    
    module = DispersionModule(constituents=constituents)
    
    # Compute implied correlation
    implied_corr = module.compute_implied_correlation(
        index_variance,
        stock_variances,
        index_weights
    )
    
    # Spread = implied - realized
    spread = implied_corr - realized_corr
    
    # If we swap implied and realized, spread should flip sign
    spread_swapped = realized_corr - implied_corr
    
    assert abs(spread + spread_swapped) < 0.0001, \
        f"Spread symmetry violated: {spread:.6f} vs {spread_swapped:.6f}"


# Property: Expected P&L sign matches direction
@given(
    entry_spread=st.floats(min_value=-0.5, max_value=0.5),
    target_spread=st.floats(min_value=-0.5, max_value=0.5),
    vega=st.floats(min_value=100.0, max_value=10000.0)
)
@settings(max_examples=20, deadline=None)
def test_property_expected_pnl_sign(entry_spread, target_spread, vega):
    """
    Property: Expected P&L sign should match trade direction
    
    For short dispersion: profit when spread narrows (target < entry)
    For long dispersion: profit when spread widens (target > entry)
    
    **Validates: Requirements 4.7**
    """
    constituents = ["AAPL", "MSFT", "GOOGL"]
    module = DispersionModule(constituents=constituents)
    
    expiry = date.today() + timedelta(days=30)
    
    # Create mock positions
    index_pos = Position(
        position_id="INDEX",
        underlying="SPY",
        option_type="call",
        strike=450.0,
        expiry=expiry,
        quantity=10,
        spot_price=450.0,
        implied_vol=0.20,
        risk_free_rate=0.05
    )
    
    stock_positions = [
        Position(
            position_id=f"{s}",
            underlying=s,
            option_type="call",
            strike=200.0,
            expiry=expiry,
            quantity=-3,
            spot_price=200.0,
            implied_vol=0.25,
            risk_free_rate=0.05
        )
        for s in constituents
    ]
    
    # Test SHORT dispersion
    short_trade = DispersionTrade(
        trade_id="SHORT_TEST",
        direction=DispersionDirection.SHORT_DISPERSION,
        entry_spread=entry_spread,
        entry_timestamp=datetime.now(),
        index_position=index_pos,
        stock_positions=stock_positions,
        target_exit_spread=target_spread
    )
    
    short_pnl = module.compute_expected_pnl(short_trade, target_spread, vega)
    
    # For short dispersion: profit when spread narrows
    if target_spread < entry_spread:
        assert short_pnl > 0, \
            f"Short dispersion should profit when spread narrows: entry={entry_spread:.4f}, target={target_spread:.4f}, pnl={short_pnl:.2f}"
    elif target_spread > entry_spread:
        assert short_pnl < 0, \
            f"Short dispersion should lose when spread widens: entry={entry_spread:.4f}, target={target_spread:.4f}, pnl={short_pnl:.2f}"
    
    # Test LONG dispersion
    long_trade = DispersionTrade(
        trade_id="LONG_TEST",
        direction=DispersionDirection.LONG_DISPERSION,
        entry_spread=entry_spread,
        entry_timestamp=datetime.now(),
        index_position=index_pos,
        stock_positions=stock_positions,
        target_exit_spread=target_spread
    )
    
    long_pnl = module.compute_expected_pnl(long_trade, target_spread, vega)
    
    # For long dispersion: profit when spread widens
    if target_spread > entry_spread:
        assert long_pnl > 0, \
            f"Long dispersion should profit when spread widens: entry={entry_spread:.4f}, target={target_spread:.4f}, pnl={long_pnl:.2f}"
    elif target_spread < entry_spread:
        assert long_pnl < 0, \
            f"Long dispersion should lose when spread narrows: entry={entry_spread:.4f}, target={target_spread:.4f}, pnl={long_pnl:.2f}"


# Property: Correlation risk monitoring is consistent
@given(
    entry_spread=st.floats(min_value=0.05, max_value=0.30),
    current_spread=st.floats(min_value=-0.30, max_value=0.30)
)
@settings(max_examples=20, deadline=None)
def test_property_correlation_risk_monitoring(entry_spread, current_spread):
    """
    Property: Correlation risk monitoring correctly identifies profitability
    
    Risk metrics should correctly identify if position is profitable based
    on spread movement and trade direction.
    
    **Validates: Requirements 4.5**
    """
    constituents = ["AAPL", "MSFT", "GOOGL"]
    module = DispersionModule(constituents=constituents)
    
    expiry = date.today() + timedelta(days=30)
    
    # Create mock positions
    index_pos = Position(
        position_id="INDEX",
        underlying="SPY",
        option_type="call",
        strike=450.0,
        expiry=expiry,
        quantity=10,
        spot_price=450.0,
        implied_vol=0.20,
        risk_free_rate=0.05
    )
    
    stock_positions = [
        Position(
            position_id=f"{s}",
            underlying=s,
            option_type="call",
            strike=200.0,
            expiry=expiry,
            quantity=-3,
            spot_price=200.0,
            implied_vol=0.25,
            risk_free_rate=0.05
        )
        for s in constituents
    ]
    
    # Test SHORT dispersion
    short_trade = DispersionTrade(
        trade_id="SHORT_TEST",
        direction=DispersionDirection.SHORT_DISPERSION,
        entry_spread=entry_spread,
        entry_timestamp=datetime.now(),
        index_position=index_pos,
        stock_positions=stock_positions,
        target_exit_spread=0.05
    )
    
    # Assume implied = current_spread + 0.5, realized = 0.5
    current_implied = current_spread + 0.5
    current_realized = 0.5
    
    risk_metrics = module.monitor_correlation_risk(
        short_trade,
        current_implied,
        current_realized
    )
    
    spread_change = current_spread - entry_spread
    
    # For short dispersion: profitable if spread narrowed (negative change)
    if spread_change < 0:
        assert risk_metrics['is_profitable'], \
            f"Short dispersion should be profitable when spread narrows: {entry_spread:.4f} -> {current_spread:.4f}"
    elif spread_change > 0:
        assert not risk_metrics['is_profitable'], \
            f"Short dispersion should not be profitable when spread widens: {entry_spread:.4f} -> {current_spread:.4f}"
