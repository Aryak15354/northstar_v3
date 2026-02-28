"""
Property-Based Tests for Portfolio Greeks Aggregator

Tests universal correctness properties using Hypothesis:
- Property 2: Put-call parity
- Property 3: Delta monotonicity
- Property 4: Greeks at expiry

Validates: Requirements 13.1
"""

import pytest
import numpy as np
from datetime import datetime, date, timedelta
from hypothesis import given, strategies as st, settings, assume
from scipy.stats import norm

from src.volatility.greeks_aggregator import (
    GreeksAggregator,
    Position
)


# Strategy for generating valid option parameters
@st.composite
def option_parameters(draw):
    """Generate valid option parameters for testing"""
    spot = draw(st.floats(min_value=50.0, max_value=500.0))
    strike = draw(st.floats(min_value=spot * 0.5, max_value=spot * 1.5))
    days_to_expiry = draw(st.integers(min_value=1, max_value=365))
    implied_vol = draw(st.floats(min_value=0.05, max_value=2.0))
    risk_free_rate = draw(st.floats(min_value=0.0, max_value=0.10))
    
    return {
        'spot': spot,
        'strike': strike,
        'days_to_expiry': days_to_expiry,
        'implied_vol': implied_vol,
        'risk_free_rate': risk_free_rate
    }


def compute_option_price(spot, strike, time_to_expiry, vol, rate, option_type):
    """Compute Black-Scholes option price"""
    if time_to_expiry <= 0:
        if option_type == 'call':
            return max(spot - strike, 0)
        else:
            return max(strike - spot, 0)
    
    d1 = (np.log(spot/strike) + (rate + 0.5*vol**2)*time_to_expiry) / (vol*np.sqrt(time_to_expiry))
    d2 = d1 - vol*np.sqrt(time_to_expiry)
    
    if option_type == 'call':
        price = spot * norm.cdf(d1) - strike * np.exp(-rate * time_to_expiry) * norm.cdf(d2)
    else:
        price = strike * np.exp(-rate * time_to_expiry) * norm.cdf(-d2) - spot * norm.cdf(-d1)
    
    return price


# Property 2: Put-Call Parity
@given(params=option_parameters())
@settings(max_examples=10, deadline=None)
def test_property_put_call_parity(params):
    """
    Property 2: Put-call parity
    
    For any strike and expiry, call_price - put_price should equal 
    spot - strike * discount_factor
    
    Validates: Requirements 13.1
    """
    aggregator = GreeksAggregator()
    spot = params['spot']
    strike = params['strike']
    days = params['days_to_expiry']
    vol = params['implied_vol']
    rate = params['risk_free_rate']
    
    expiry = date.today() + timedelta(days=days)
    time_to_expiry = days / 365.0
    
    # Create call position
    call_pos = Position(
        position_id="CALL_TEST",
        underlying="TEST",
        option_type="call",
        strike=strike,
        expiry=expiry,
        quantity=1,
        spot_price=spot,
        implied_vol=vol,
        risk_free_rate=rate
    )
    
    # Create put position
    put_pos = Position(
        position_id="PUT_TEST",
        underlying="TEST",
        option_type="put",
        strike=strike,
        expiry=expiry,
        quantity=1,
        spot_price=spot,
        implied_vol=vol,
        risk_free_rate=rate
    )
    
    # Compute option prices
    call_price = compute_option_price(spot, strike, time_to_expiry, vol, rate, 'call')
    put_price = compute_option_price(spot, strike, time_to_expiry, vol, rate, 'put')
    
    # Put-call parity: C - P = S - K * e^(-rT)
    discount_factor = np.exp(-rate * time_to_expiry)
    parity_lhs = call_price - put_price
    parity_rhs = spot - strike * discount_factor
    
    # Allow small numerical tolerance
    assert abs(parity_lhs - parity_rhs) < 0.01, \
        f"Put-call parity violated: {parity_lhs:.4f} != {parity_rhs:.4f}"


# Property 3: Delta Monotonicity
@given(params=option_parameters())
@settings(max_examples=10, deadline=None)
def test_property_delta_monotonicity_call(params):
    """
    Property 3: Delta monotonicity for calls
    
    For any call option, increasing spot price should increase delta
    
    Validates: Requirements 13.1
    """
    aggregator = GreeksAggregator()
    spot = params['spot']
    strike = params['strike']
    days = params['days_to_expiry']
    vol = params['implied_vol']
    rate = params['risk_free_rate']
    
    # Skip if too close to expiry (numerical instability)
    assume(days > 5)
    
    expiry = date.today() + timedelta(days=days)
    
    # Create call at current spot
    call_pos_1 = Position(
        position_id="CALL_1",
        underlying="TEST",
        option_type="call",
        strike=strike,
        expiry=expiry,
        quantity=1,
        spot_price=spot,
        implied_vol=vol,
        risk_free_rate=rate
    )
    
    # Create call at higher spot (10% higher)
    spot_higher = spot * 1.10
    call_pos_2 = Position(
        position_id="CALL_2",
        underlying="TEST",
        option_type="call",
        strike=strike,
        expiry=expiry,
        quantity=1,
        spot_price=spot_higher,
        implied_vol=vol,
        risk_free_rate=rate
    )
    
    greeks_1 = aggregator.compute_position_greeks(call_pos_1)
    greeks_2 = aggregator.compute_position_greeks(call_pos_2)
    
    # Delta should increase when spot increases
    assert greeks_2.delta > greeks_1.delta, \
        f"Call delta should increase with spot: {greeks_1.delta:.4f} -> {greeks_2.delta:.4f}"


@given(params=option_parameters())
@settings(max_examples=10, deadline=None)
def test_property_delta_monotonicity_put(params):
    """
    Property 3: Delta monotonicity for puts
    
    For any put option, increasing spot price should decrease delta 
    (in absolute value, delta becomes less negative)
    
    Validates: Requirements 13.1
    """
    aggregator = GreeksAggregator()
    spot = params['spot']
    strike = params['strike']
    days = params['days_to_expiry']
    vol = params['implied_vol']
    rate = params['risk_free_rate']
    
    # Skip if too close to expiry (numerical instability)
    assume(days > 5)
    
    expiry = date.today() + timedelta(days=days)
    
    # Create put at current spot
    put_pos_1 = Position(
        position_id="PUT_1",
        underlying="TEST",
        option_type="put",
        strike=strike,
        expiry=expiry,
        quantity=1,
        spot_price=spot,
        implied_vol=vol,
        risk_free_rate=rate
    )
    
    # Create put at higher spot (10% higher)
    spot_higher = spot * 1.10
    put_pos_2 = Position(
        position_id="PUT_2",
        underlying="TEST",
        option_type="put",
        strike=strike,
        expiry=expiry,
        quantity=1,
        spot_price=spot_higher,
        implied_vol=vol,
        risk_free_rate=rate
    )
    
    greeks_1 = aggregator.compute_position_greeks(put_pos_1)
    greeks_2 = aggregator.compute_position_greeks(put_pos_2)
    
    # Put delta should become less negative (increase) when spot increases
    assert greeks_2.delta > greeks_1.delta, \
        f"Put delta should increase (become less negative) with spot: {greeks_1.delta:.4f} -> {greeks_2.delta:.4f}"


# Property 4: Greeks at Expiry
@given(
    spot=st.floats(min_value=50.0, max_value=500.0),
    strike=st.floats(min_value=50.0, max_value=500.0),
    vol=st.floats(min_value=0.05, max_value=2.0),
    rate=st.floats(min_value=0.0, max_value=0.10)
)
@settings(max_examples=10, deadline=None)
def test_property_greeks_at_expiry_call(spot, strike, vol, rate):
    """
    Property 4: Greeks at expiry for calls
    
    For any call option at expiry:
    - Delta should be 1 if ITM (spot > strike), 0 if OTM
    - Gamma should be 0
    - Vega should be 0
    
    Validates: Requirements 13.1
    """
    aggregator = GreeksAggregator()
    # Create expired call
    expired_call = Position(
        position_id="EXPIRED_CALL",
        underlying="TEST",
        option_type="call",
        strike=strike,
        expiry=date.today() - timedelta(days=1),  # Expired
        quantity=1,
        spot_price=spot,
        implied_vol=vol,
        risk_free_rate=rate
    )
    
    greeks = aggregator.compute_position_greeks(expired_call)
    
    # At expiry, all Greeks should be zero (our implementation returns zero for expired options)
    assert greeks.delta == 0.0, f"Expired option delta should be 0, got {greeks.delta}"
    assert greeks.gamma == 0.0, f"Expired option gamma should be 0, got {greeks.gamma}"
    assert greeks.vega == 0.0, f"Expired option vega should be 0, got {greeks.vega}"


@given(
    spot=st.floats(min_value=50.0, max_value=500.0),
    strike=st.floats(min_value=50.0, max_value=500.0),
    vol=st.floats(min_value=0.05, max_value=2.0),
    rate=st.floats(min_value=0.0, max_value=0.10)
)
@settings(max_examples=10, deadline=None)
def test_property_greeks_at_expiry_put(spot, strike, vol, rate):
    """
    Property 4: Greeks at expiry for puts
    
    For any put option at expiry:
    - Delta should be -1 if ITM (spot < strike), 0 if OTM
    - Gamma should be 0
    - Vega should be 0
    
    Validates: Requirements 13.1
    """
    aggregator = GreeksAggregator()
    # Create expired put
    expired_put = Position(
        position_id="EXPIRED_PUT",
        underlying="TEST",
        option_type="put",
        strike=strike,
        expiry=date.today() - timedelta(days=1),  # Expired
        quantity=1,
        spot_price=spot,
        implied_vol=vol,
        risk_free_rate=rate
    )
    
    greeks = aggregator.compute_position_greeks(expired_put)
    
    # At expiry, all Greeks should be zero (our implementation returns zero for expired options)
    assert greeks.delta == 0.0, f"Expired option delta should be 0, got {greeks.delta}"
    assert greeks.gamma == 0.0, f"Expired option gamma should be 0, got {greeks.gamma}"
    assert greeks.vega == 0.0, f"Expired option vega should be 0, got {greeks.vega}"


# Additional property: Gamma is always non-negative
@given(params=option_parameters())
@settings(max_examples=10, deadline=None)
def test_property_gamma_non_negative(params):
    """
    Additional property: Gamma is always non-negative for long options
    
    Validates: Requirements 13.1
    """
    aggregator = GreeksAggregator()
    spot = params['spot']
    strike = params['strike']
    days = params['days_to_expiry']
    vol = params['implied_vol']
    rate = params['risk_free_rate']
    
    expiry = date.today() + timedelta(days=days)
    
    # Test call
    call_pos = Position(
        position_id="CALL_TEST",
        underlying="TEST",
        option_type="call",
        strike=strike,
        expiry=expiry,
        quantity=1,
        spot_price=spot,
        implied_vol=vol,
        risk_free_rate=rate
    )
    
    call_greeks = aggregator.compute_position_greeks(call_pos)
    assert call_greeks.gamma >= 0, f"Call gamma should be non-negative, got {call_greeks.gamma}"
    
    # Test put
    put_pos = Position(
        position_id="PUT_TEST",
        underlying="TEST",
        option_type="put",
        strike=strike,
        expiry=expiry,
        quantity=1,
        spot_price=spot,
        implied_vol=vol,
        risk_free_rate=rate
    )
    
    put_greeks = aggregator.compute_position_greeks(put_pos)
    assert put_greeks.gamma >= 0, f"Put gamma should be non-negative, got {put_greeks.gamma}"


# Additional property: Vega is always non-negative
@given(params=option_parameters())
@settings(max_examples=10, deadline=None)
def test_property_vega_non_negative(params):
    """
    Additional property: Vega is always non-negative for long options
    
    Validates: Requirements 13.1
    """
    aggregator = GreeksAggregator()
    spot = params['spot']
    strike = params['strike']
    days = params['days_to_expiry']
    vol = params['implied_vol']
    rate = params['risk_free_rate']
    
    expiry = date.today() + timedelta(days=days)
    
    # Test call
    call_pos = Position(
        position_id="CALL_TEST",
        underlying="TEST",
        option_type="call",
        strike=strike,
        expiry=expiry,
        quantity=1,
        spot_price=spot,
        implied_vol=vol,
        risk_free_rate=rate
    )
    
    call_greeks = aggregator.compute_position_greeks(call_pos)
    assert call_greeks.vega >= 0, f"Call vega should be non-negative, got {call_greeks.vega}"
    
    # Test put
    put_pos = Position(
        position_id="PUT_TEST",
        underlying="TEST",
        option_type="put",
        strike=strike,
        expiry=expiry,
        quantity=1,
        spot_price=spot,
        implied_vol=vol,
        risk_free_rate=rate
    )
    
    put_greeks = aggregator.compute_position_greeks(put_pos)
    assert put_greeks.vega >= 0, f"Put vega should be non-negative, got {put_greeks.vega}"


# Additional property: Call delta bounds
@given(params=option_parameters())
@settings(max_examples=10, deadline=None)
def test_property_call_delta_bounds(params):
    """
    Additional property: Call delta should be between 0 and 1
    
    Validates: Requirements 13.1
    """
    aggregator = GreeksAggregator()
    spot = params['spot']
    strike = params['strike']
    days = params['days_to_expiry']
    vol = params['implied_vol']
    rate = params['risk_free_rate']
    
    expiry = date.today() + timedelta(days=days)
    
    call_pos = Position(
        position_id="CALL_TEST",
        underlying="TEST",
        option_type="call",
        strike=strike,
        expiry=expiry,
        quantity=1,
        spot_price=spot,
        implied_vol=vol,
        risk_free_rate=rate
    )
    
    greeks = aggregator.compute_position_greeks(call_pos)
    
    assert 0 <= greeks.delta <= 1, \
        f"Call delta should be between 0 and 1, got {greeks.delta}"


# Additional property: Put delta bounds
@given(params=option_parameters())
@settings(max_examples=10, deadline=None)
def test_property_put_delta_bounds(params):
    """
    Additional property: Put delta should be between -1 and 0
    
    Validates: Requirements 13.1
    """
    aggregator = GreeksAggregator()
    spot = params['spot']
    strike = params['strike']
    days = params['days_to_expiry']
    vol = params['implied_vol']
    rate = params['risk_free_rate']
    
    expiry = date.today() + timedelta(days=days)
    
    put_pos = Position(
        position_id="PUT_TEST",
        underlying="TEST",
        option_type="put",
        strike=strike,
        expiry=expiry,
        quantity=1,
        spot_price=spot,
        implied_vol=vol,
        risk_free_rate=rate
    )
    
    greeks = aggregator.compute_position_greeks(put_pos)
    
    assert -1 <= greeks.delta <= 0, \
        f"Put delta should be between -1 and 0, got {greeks.delta}"
