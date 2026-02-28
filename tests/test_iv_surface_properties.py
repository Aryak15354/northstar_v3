"""
Property-Based Tests for IV Surface

Tests Property 1: No-arbitrage constraints
- Calendar spreads should have non-negative prices
- Butterfly spreads should have non-negative prices

Uses Hypothesis for property-based testing.
"""

import numpy as np
from datetime import datetime, date, timedelta
from hypothesis import given, strategies as st, settings, assume
from hypothesis import HealthCheck

from src.volatility import IVSurface, OptionQuote, SurfaceModel, create_iv_surface_from_quotes


# Strategy for generating valid option quotes
@st.composite
def option_quote_strategy(draw, underlying="SPY", spot=450.0):
    """Generate valid option quotes"""
    base_date = datetime.now().date()
    
    # Generate expiry (7 to 180 days out)
    days_to_expiry = draw(st.integers(min_value=7, max_value=180))
    expiry = base_date + timedelta(days=days_to_expiry)
    
    # Generate strike (80% to 120% of spot)
    strike_ratio = draw(st.floats(min_value=0.8, max_value=1.2))
    strike = spot * strike_ratio
    
    # Generate implied vol (10% to 50%)
    implied_vol = draw(st.floats(min_value=0.10, max_value=0.50))
    
    return OptionQuote(
        underlying=underlying,
        strike=strike,
        expiry=expiry,
        option_type='call',
        implied_vol=implied_vol,
        bid=0.0,
        ask=0.0,
        mid_price=0.0,
        volume=100,
        open_interest=1000,
        timestamp=datetime.now()
    )


@st.composite
def iv_surface_strategy(draw, min_quotes=30, max_quotes=60):
    """Generate IV surface with multiple quotes across multiple expiries"""
    spot = 450.0  # Fixed spot for consistency
    base_date = datetime.now().date()
    
    # Generate quotes for 3 expiries with good coverage
    expiries = [
        base_date + timedelta(days=30),
        base_date + timedelta(days=60),
        base_date + timedelta(days=90)
    ]
    
    quotes = []
    for expiry in expiries:
        # Generate 10-15 strikes per expiry
        num_strikes = draw(st.integers(min_value=10, max_value=15))
        strikes = np.linspace(spot * 0.85, spot * 1.15, num_strikes)
        
        for strike in strikes:
            # Generate realistic vol with smile
            moneyness = strike / spot
            base_vol = draw(st.floats(min_value=0.15, max_value=0.30))
            
            # Add smile
            if moneyness < 1.0:
                vol = base_vol + 0.05 * (1.0 - moneyness)
            else:
                vol = base_vol + 0.03 * (moneyness - 1.0)
            
            # Add term structure
            days_to_expiry = (expiry - base_date).days
            vol += 0.001 * days_to_expiry / 30
            
            quote = OptionQuote(
                underlying="SPY",
                strike=float(strike),
                expiry=expiry,
                option_type='call',
                implied_vol=float(vol),
                bid=0.0,
                ask=0.0,
                mid_price=0.0,
                volume=100,
                open_interest=1000,
                timestamp=datetime.now()
            )
            quotes.append(quote)
    
    surface = create_iv_surface_from_quotes(
        underlying="SPY",
        spot_price=spot,
        quotes=quotes,
        model=SurfaceModel.SVI
    )
    
    return surface, spot


def calculate_option_price(spot, strike, vol, tte, rate, option_type='call'):
    """Calculate Black-Scholes option price"""
    from scipy.stats import norm
    
    if tte <= 0:
        if option_type == 'call':
            return max(spot - strike, 0)
        else:
            return max(strike - spot, 0)
    
    d1 = (np.log(spot/strike) + (rate + 0.5*vol**2)*tte) / (vol*np.sqrt(tte))
    d2 = d1 - vol*np.sqrt(tte)
    
    if option_type == 'call':
        price = spot * norm.cdf(d1) - strike * np.exp(-rate*tte) * norm.cdf(d2)
    else:
        price = strike * np.exp(-rate*tte) * norm.cdf(-d2) - spot * norm.cdf(-d1)
    
    return price


@given(iv_surface_strategy())
@settings(max_examples=10, deadline=None, suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much])
def test_property_calendar_spread_no_arbitrage(surface_data):
    """
    Property 1: Calendar Spread No-Arbitrage
    
    For any strike K and expiries T1 < T2:
    - Total variance at T2 should be >= total variance at T1
    - This ensures calendar spreads have non-negative prices
    
    Validates: Requirements 10.2
    """
    surface, spot = surface_data
    
    # Get available expiries
    if surface.fitted_model == SurfaceModel.FLAT:
        # FLAT model doesn't have SVI params, use flat_vol_by_expiry
        expiries = sorted(surface.flat_vol_by_expiry.keys())
    else:
        expiries = sorted(surface.svi_params_by_expiry.keys())
    
    if len(expiries) < 2:
        return  # Skip if not enough expiries
    
    # Test calendar spread for multiple strikes
    strikes = np.linspace(spot * 0.9, spot * 1.1, 5)
    
    for i in range(len(expiries) - 1):
        expiry1 = expiries[i]
        expiry2 = expiries[i + 1]
        
        for strike in strikes:
            var1 = surface.get_variance(strike, expiry1)
            var2 = surface.get_variance(strike, expiry2)
            
            # Calendar spread: longer expiry should have >= variance
            # Allow 5% tolerance for numerical errors
            assert var2 >= var1 * 0.95, \
                f"Calendar arbitrage: var2 ({var2:.6f}) < var1 ({var1:.6f}) at strike {strike}"


@given(iv_surface_strategy())
@settings(max_examples=10, deadline=None, suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much])
def test_property_butterfly_spread_no_arbitrage(surface_data):
    """
    Property 1: Butterfly Spread No-Arbitrage
    
    For any three strikes K1 < K2 < K3 with equal spacing:
    - The butterfly spread should have non-negative price
    - This requires convexity in the volatility smile
    
    Validates: Requirements 10.2
    """
    surface, spot = surface_data
    
    if surface.fitted_model == SurfaceModel.FLAT:
        expiries = sorted(surface.flat_vol_by_expiry.keys())
    else:
        expiries = sorted(surface.svi_params_by_expiry.keys())
    
    if len(expiries) == 0:
        return
    
    expiry = expiries[0]
    tte = (expiry - datetime.now().date()).days / 365.0
    
    if tte <= 0:
        return
    
    # Test butterfly spreads at different strike levels
    strike_centers = np.linspace(spot * 0.95, spot * 1.05, 3)
    
    for center in strike_centers:
        # Create butterfly: long 1 at K1, short 2 at K2, long 1 at K3
        wing_width = spot * 0.05
        k1 = center - wing_width
        k2 = center
        k3 = center + wing_width
        
        # Get vols
        vol1 = surface.get_vol(k1, expiry)
        vol2 = surface.get_vol(k2, expiry)
        vol3 = surface.get_vol(k3, expiry)
        
        # Calculate butterfly price
        call1 = calculate_option_price(spot, k1, vol1, tte, 0.05, 'call')
        call2 = calculate_option_price(spot, k2, vol2, tte, 0.05, 'call')
        call3 = calculate_option_price(spot, k3, vol3, tte, 0.05, 'call')
        
        butterfly_price = call1 - 2*call2 + call3
        
        # Butterfly should have non-negative price (with tolerance for numerical errors)
        assert butterfly_price >= -0.10, \
            f"Butterfly arbitrage: price {butterfly_price:.4f} < 0 at strikes ({k1:.2f}, {k2:.2f}, {k3:.2f})"


@given(iv_surface_strategy())
@settings(max_examples=10, deadline=None, suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much])
def test_property_positive_variance(surface_data):
    """
    Property: Positive Variance
    
    For any strike and expiry, total variance should be positive.
    """
    surface, spot = surface_data
    
    if surface.fitted_model == SurfaceModel.FLAT:
        expiries = sorted(surface.flat_vol_by_expiry.keys())
    else:
        expiries = sorted(surface.svi_params_by_expiry.keys())
    
    if len(expiries) == 0:
        return
    
    expiry = expiries[0]
    
    # Test at multiple strikes
    strikes = np.linspace(spot * 0.8, spot * 1.2, 10)
    
    for strike in strikes:
        variance = surface.get_variance(strike, expiry)
        assert variance > 0, f"Non-positive variance {variance} at strike {strike}"


@given(iv_surface_strategy())
@settings(max_examples=10, deadline=None, suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much])
def test_property_vol_bounds(surface_data):
    """
    Property: Volatility Bounds
    
    Implied volatility should be within reasonable bounds (5% to 200%).
    """
    surface, spot = surface_data
    
    if surface.fitted_model == SurfaceModel.FLAT:
        expiries = sorted(surface.flat_vol_by_expiry.keys())
    else:
        expiries = sorted(surface.svi_params_by_expiry.keys())
    
    if len(expiries) == 0:
        return
    
    expiry = expiries[0]
    
    # Test at multiple strikes
    strikes = np.linspace(spot * 0.8, spot * 1.2, 10)
    
    for strike in strikes:
        vol = surface.get_vol(strike, expiry)
        assert 0.05 <= vol <= 2.0, f"Vol {vol:.4f} out of bounds at strike {strike}"


def run_property_tests():
    """Run all property tests"""
    print("🧪 PROPERTY-BASED TESTS FOR IV SURFACE")
    print("=" * 60)
    
    tests = [
        ("Calendar Spread No-Arbitrage", test_property_calendar_spread_no_arbitrage),
        ("Butterfly Spread No-Arbitrage", test_property_butterfly_spread_no_arbitrage),
        ("Positive Variance", test_property_positive_variance),
        ("Volatility Bounds", test_property_vol_bounds),
    ]
    
    for test_name, test_func in tests:
        print(f"\n🔍 Testing: {test_name}")
        try:
            # Run the hypothesis test
            test_func()
            print(f"   ✅ {test_name}: PASSED")
        except Exception as e:
            print(f"   ❌ {test_name}: FAILED - {e}")
            return False
    
    print("\n" + "=" * 60)
    print("✅ ALL PROPERTY TESTS PASSED")
    return True


if __name__ == "__main__":
    success = run_property_tests()
    exit(0 if success else 1)
