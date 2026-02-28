"""
Property-Based Tests for Gamma Scalping Engine

Tests universal correctness properties using Hypothesis:
- Property 10: Hedging reduces delta exposure
- Property 11: Realized variance is non-negative

**Validates: Requirements 5.2, 5.3**
"""

import pytest
import numpy as np
from datetime import datetime, date, timedelta
from hypothesis import given, strategies as st, settings, assume

from src.volatility.gamma_scalper import (
    GammaScalper,
    HedgingMode,
    Hedge,
    RealizedPnL
)
from src.volatility.greeks_aggregator import Position


# Strategy for generating valid positions
@st.composite
def gamma_position(draw):
    """Generate valid long gamma position for testing"""
    spot = draw(st.floats(min_value=50.0, max_value=500.0))
    strike = draw(st.floats(min_value=spot * 0.8, max_value=spot * 1.2))
    days_to_expiry = draw(st.integers(min_value=7, max_value=90))
    implied_vol = draw(st.floats(min_value=0.10, max_value=1.0))
    quantity = draw(st.integers(min_value=1, max_value=100))
    option_type = draw(st.sampled_from(['call', 'put']))
    
    expiry = date.today() + timedelta(days=days_to_expiry)
    
    position = Position(
        position_id=f"POS_{draw(st.integers(min_value=1000, max_value=9999))}",
        underlying="TEST",
        option_type=option_type,
        strike=strike,
        expiry=expiry,
        quantity=quantity,  # Long position
        spot_price=spot,
        implied_vol=implied_vol,
        risk_free_rate=0.05
    )
    
    return position, spot


# Property 10: Hedging reduces delta exposure
@given(position_and_spot=gamma_position())
@settings(max_examples=20, deadline=None)
def test_property_hedging_reduces_delta(position_and_spot):
    """
    Property 10: Hedging reduces delta exposure
    
    For any long gamma position, executing a hedge should reduce 
    absolute delta toward zero.
    
    **Validates: Requirements 5.2**
    """
    position, initial_spot = position_and_spot
    
    scalper = GammaScalper(transaction_cost_bps=5.0)
    
    # Simulate initial delta (simplified - using quantity as proxy)
    # In reality, would compute actual delta from Greeks
    if position.option_type == 'call':
        # Call delta is positive, roughly 0.5 ATM
        initial_delta = position.quantity * 0.5
    else:
        # Put delta is negative, roughly -0.5 ATM
        initial_delta = position.quantity * -0.5
    
    # Generate hedge order
    order = scalper.generate_hedge_order(
        position=position,
        current_delta=initial_delta,
        current_price=initial_spot,
        target_delta=0.0
    )
    
    # Verify hedge reduces delta
    # Hedge quantity should be opposite sign to delta
    if initial_delta > 0:
        # Positive delta -> need to sell (negative quantity)
        assert order.quantity < 0, \
            f"Positive delta {initial_delta} should generate sell order, got {order.quantity}"
    elif initial_delta < 0:
        # Negative delta -> need to buy (positive quantity)
        assert order.quantity > 0, \
            f"Negative delta {initial_delta} should generate buy order, got {order.quantity}"
    
    # After hedge, delta should be closer to zero
    delta_after_hedge = initial_delta + order.quantity
    
    assert abs(delta_after_hedge) < abs(initial_delta), \
        f"Hedge should reduce absolute delta: {abs(initial_delta):.4f} -> {abs(delta_after_hedge):.4f}"
    
    # For target_delta=0, should be approximately zero
    assert abs(delta_after_hedge) < 0.01, \
        f"Delta after hedge should be near zero, got {delta_after_hedge:.4f}"


# Property 11: Realized variance is non-negative
@given(
    num_hedges=st.integers(min_value=2, max_value=20),
    initial_price=st.floats(min_value=50.0, max_value=500.0),
    volatility=st.floats(min_value=0.10, max_value=1.0)
)
@settings(max_examples=20, deadline=None)
def test_property_realized_variance_non_negative(num_hedges, initial_price, volatility):
    """
    Property 11: Realized variance is non-negative
    
    For any sequence of hedges, computed realized variance should be non-negative.
    
    **Validates: Requirements 5.3**
    """
    scalper = GammaScalper(transaction_cost_bps=5.0)
    
    position_id = "TEST_POS_001"
    
    # Simulate a sequence of hedges with realistic price movements
    current_price = initial_price
    
    for i in range(num_hedges):
        # Simulate price movement (geometric Brownian motion)
        dt = 1/252  # Daily
        z = np.random.randn()
        price_change = current_price * volatility * np.sqrt(dt) * z
        current_price = max(current_price + price_change, initial_price * 0.5)  # Floor at 50% of initial
        
        # Record hedge
        hedge = Hedge(
            timestamp=datetime.now() + timedelta(days=i),
            position_id=position_id,
            underlying="TEST",
            price=current_price,
            delta_before=0.5,
            delta_after=0.0,
            hedge_quantity=10.0,
            transaction_cost=5.0,
            pnl=0.0
        )
        
        if position_id not in scalper.hedge_history:
            scalper.hedge_history[position_id] = []
        scalper.hedge_history[position_id].append(hedge)
    
    # Compute realized variance
    realized_var = scalper.compute_realized_variance(position_id)
    
    # Realized variance must be non-negative
    assert realized_var >= 0, \
        f"Realized variance must be non-negative, got {realized_var:.6f}"


# Additional property: Hedging threshold is positive
@given(position_and_spot=gamma_position())
@settings(max_examples=20, deadline=None)
def test_property_hedging_threshold_positive(position_and_spot):
    """
    Additional property: Hedging threshold is always positive
    
    For any position with positive gamma, the hedging threshold should be positive.
    """
    position, spot = position_and_spot
    
    scalper = GammaScalper(transaction_cost_bps=5.0)
    
    # Compute threshold for different modes
    for mode in [HedgingMode.NORMAL, HedgingMode.HIGH_FREQUENCY, HedgingMode.LOW_FREQUENCY]:
        threshold = scalper.compute_hedging_threshold(position, spot, mode)
        
        assert threshold > 0, \
            f"Hedging threshold should be positive for mode {mode.value}, got {threshold}"


# Additional property: High frequency mode has lower threshold
@given(position_and_spot=gamma_position())
@settings(max_examples=20, deadline=None)
def test_property_high_freq_lower_threshold(position_and_spot):
    """
    Additional property: High frequency mode should have lower threshold than normal mode
    
    This ensures more frequent hedging when realized vol exceeds implied vol.
    """
    position, spot = position_and_spot
    
    scalper = GammaScalper(transaction_cost_bps=5.0)
    
    threshold_normal = scalper.compute_hedging_threshold(position, spot, HedgingMode.NORMAL)
    threshold_high_freq = scalper.compute_hedging_threshold(position, spot, HedgingMode.HIGH_FREQUENCY)
    
    assert threshold_high_freq < threshold_normal, \
        f"High frequency threshold {threshold_high_freq:.6f} should be lower than normal {threshold_normal:.6f}"


# Additional property: Low frequency mode has higher threshold
@given(position_and_spot=gamma_position())
@settings(max_examples=20, deadline=None)
def test_property_low_freq_higher_threshold(position_and_spot):
    """
    Additional property: Low frequency mode should have higher threshold than normal mode
    
    This ensures less frequent hedging when realized vol is below implied vol.
    """
    position, spot = position_and_spot
    
    scalper = GammaScalper(transaction_cost_bps=5.0)
    
    threshold_normal = scalper.compute_hedging_threshold(position, spot, HedgingMode.NORMAL)
    threshold_low_freq = scalper.compute_hedging_threshold(position, spot, HedgingMode.LOW_FREQUENCY)
    
    assert threshold_low_freq > threshold_normal, \
        f"Low frequency threshold {threshold_low_freq:.6f} should be higher than normal {threshold_normal:.6f}"


# Additional property: Adaptive hedging responds to variance ratio
@given(
    var_ratio=st.floats(min_value=0.5, max_value=2.5)
)
@settings(max_examples=20, deadline=None)
def test_property_adaptive_hedging_responds_to_variance_ratio(var_ratio):
    """
    Additional property: Adaptive hedging should adjust mode based on variance ratio
    
    - var_ratio > 1.5 -> HIGH_FREQUENCY
    - 1.1 < var_ratio <= 1.5 -> NORMAL
    - var_ratio <= 1.1 -> LOW_FREQUENCY
    """
    scalper = GammaScalper(transaction_cost_bps=5.0)
    
    # Create dummy position
    position = Position(
        position_id="TEST_POS",
        underlying="TEST",
        option_type="call",
        strike=100.0,
        expiry=date.today() + timedelta(days=30),
        quantity=10,
        spot_price=100.0,
        implied_vol=0.20,
        risk_free_rate=0.05
    )
    
    # Create performance with specific variance ratio
    implied_var = 0.20 ** 2  # 0.04
    realized_var = implied_var * var_ratio
    
    performance = RealizedPnL(
        total_pnl=0.0,
        option_pnl=0.0,
        hedge_pnl=0.0,
        variance_pnl=0.0,
        realized_var=realized_var,
        implied_var=implied_var,
        num_hedges=10,
        total_transaction_costs=0.0
    )
    
    # Adapt hedging frequency
    mode = scalper.adapt_hedging_frequency(position, performance)
    
    # Verify mode matches variance ratio
    if var_ratio > 1.5:
        assert mode == HedgingMode.HIGH_FREQUENCY, \
            f"Variance ratio {var_ratio:.2f} should trigger HIGH_FREQUENCY, got {mode.value}"
    elif var_ratio > 1.1:
        assert mode == HedgingMode.NORMAL, \
            f"Variance ratio {var_ratio:.2f} should trigger NORMAL, got {mode.value}"
    else:
        assert mode == HedgingMode.LOW_FREQUENCY, \
            f"Variance ratio {var_ratio:.2f} should trigger LOW_FREQUENCY, got {mode.value}"


# Additional property: Hedge history accumulates correctly
@given(
    num_hedges=st.integers(min_value=1, max_value=10)
)
@settings(max_examples=20, deadline=None)
def test_property_hedge_history_accumulates(num_hedges):
    """
    Additional property: Hedge history should accumulate correctly
    
    Recording N hedges should result in N entries in history.
    """
    scalper = GammaScalper(transaction_cost_bps=5.0)
    
    position = Position(
        position_id="TEST_POS",
        underlying="TEST",
        option_type="call",
        strike=100.0,
        expiry=date.today() + timedelta(days=30),
        quantity=10,
        spot_price=100.0,
        implied_vol=0.20,
        risk_free_rate=0.05
    )
    
    # Record multiple hedges
    for i in range(num_hedges):
        scalper.record_hedge(
            position=position,
            current_price=100.0 + i,
            delta_before=0.5,
            delta_after=0.0,
            hedge_quantity=-5.0,
            execution_price=100.0 + i
        )
    
    # Verify history length
    history = scalper.hedge_history.get(position.position_id, [])
    assert len(history) == num_hedges, \
        f"Expected {num_hedges} hedges in history, got {len(history)}"


# Additional property: Transaction costs are always positive
@given(position_and_spot=gamma_position())
@settings(max_examples=20, deadline=None)
def test_property_transaction_costs_positive(position_and_spot):
    """
    Additional property: Transaction costs should always be positive
    
    Any hedge execution should incur positive transaction costs.
    """
    position, spot = position_and_spot
    
    scalper = GammaScalper(transaction_cost_bps=5.0)
    
    # Record a hedge
    hedge = scalper.record_hedge(
        position=position,
        current_price=spot,
        delta_before=0.5,
        delta_after=0.0,
        hedge_quantity=10.0,
        execution_price=spot
    )
    
    assert hedge.transaction_cost >= 0, \
        f"Transaction cost should be non-negative, got {hedge.transaction_cost}"


# Additional property: Expiration proximity reduces threshold
@given(position_and_spot=gamma_position())
@settings(max_examples=20, deadline=None)
def test_property_expiration_reduces_threshold(position_and_spot):
    """
    Additional property: Positions near expiration should have lower hedging threshold
    
    This ensures more frequent hedging as gamma increases near expiration.
    """
    position, spot = position_and_spot
    
    # Skip if position is already near expiration
    days_to_expiry = (position.expiry - date.today()).days
    assume(days_to_expiry > 14)  # Need at least 14 days to test
    
    scalper = GammaScalper(
        transaction_cost_bps=5.0,
        expiration_days_threshold=7,
        expiration_threshold_multiplier=0.7
    )
    
    # Compute threshold for current position
    threshold_far = scalper.compute_hedging_threshold(position, spot)
    
    # Create near-expiration position (5 days)
    near_expiry_position = Position(
        position_id=position.position_id,
        underlying=position.underlying,
        option_type=position.option_type,
        strike=position.strike,
        expiry=date.today() + timedelta(days=5),
        quantity=position.quantity,
        spot_price=position.spot_price,
        implied_vol=position.implied_vol,
        risk_free_rate=position.risk_free_rate
    )
    
    threshold_near = scalper.compute_hedging_threshold(near_expiry_position, spot)
    
    assert threshold_near < threshold_far, \
        f"Near-expiration threshold {threshold_near:.6f} should be lower than far-expiration {threshold_far:.6f}"
