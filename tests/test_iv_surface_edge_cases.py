"""
Unit Tests for IV Surface Edge Cases

Tests:
- Surface fitting with sparse data
- Extrapolation behavior at extreme strikes
- Fallback to simpler models when fit fails

Validates: Requirements 10.3, 10.4
"""

import numpy as np
from datetime import datetime, date, timedelta
from src.volatility import IVSurface, OptionQuote, SurfaceModel, create_iv_surface_from_quotes


def create_sparse_quotes(underlying="SPY", spot=450.0, num_quotes=5):
    """Create sparse option quotes"""
    quotes = []
    base_date = datetime.now().date()
    expiry = base_date + timedelta(days=30)
    
    # Only a few strikes
    strikes = np.linspace(spot * 0.95, spot * 1.05, num_quotes)
    
    for strike in strikes:
        vol = 0.20 + 0.02 * abs(strike - spot) / spot
        
        quote = OptionQuote(
            underlying=underlying,
            strike=strike,
            expiry=expiry,
            option_type='call',
            implied_vol=vol,
            bid=0.0,
            ask=0.0,
            mid_price=0.0,
            volume=100,
            open_interest=1000,
            timestamp=datetime.now()
        )
        quotes.append(quote)
    
    return quotes


def test_sparse_data_fitting():
    """
    Test surface fitting with sparse data.
    
    With insufficient data, should fallback to simpler model.
    Validates: Requirements 10.3
    """
    print("🧪 Test 1: Sparse Data Fitting")
    
    # Create surface with very few quotes
    quotes = create_sparse_quotes(num_quotes=3)
    surface = create_iv_surface_from_quotes(
        underlying="SPY",
        spot_price=450.0,
        quotes=quotes,
        model=SurfaceModel.SVI
    )
    
    # Should fallback to FLAT model
    assert surface.fitted_model == SurfaceModel.FLAT, \
        f"Expected FLAT model, got {surface.fitted_model}"
    print("   ✅ Correctly fell back to FLAT model with 3 quotes")
    
    # Should still be able to get vols
    expiry = datetime.now().date() + timedelta(days=30)
    vol = surface.get_vol(450.0, expiry)
    assert 0.10 < vol < 0.50, f"Vol {vol} out of reasonable range"
    print(f"   ✅ Can retrieve vol: {vol:.4f}")


def test_extreme_strike_extrapolation():
    """
    Test extrapolation behavior at extreme strikes.
    
    Should handle deep OTM/ITM strikes gracefully.
    Validates: Requirements 10.4
    """
    print("\n🧪 Test 2: Extreme Strike Extrapolation")
    
    # Create surface with normal data
    quotes = []
    base_date = datetime.now().date()
    expiry = base_date + timedelta(days=30)
    spot = 450.0
    
    # Normal strikes around ATM
    strikes = np.linspace(spot * 0.9, spot * 1.1, 15)
    
    for strike in strikes:
        moneyness = strike / spot
        vol = 0.20 + 0.05 * abs(moneyness - 1.0)
        
        quote = OptionQuote(
            underlying="SPY",
            strike=strike,
            expiry=expiry,
            option_type='call',
            implied_vol=vol,
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
    
    # Test deep OTM call (strike = 2x spot)
    deep_otm_strike = spot * 2.0
    deep_otm_vol = surface.get_vol(deep_otm_strike, expiry)
    assert 0.05 < deep_otm_vol < 1.0, f"Deep OTM vol {deep_otm_vol} out of range"
    print(f"   ✅ Deep OTM (K={deep_otm_strike:.0f}): vol={deep_otm_vol:.4f}")
    
    # Test deep ITM call (strike = 0.5x spot)
    deep_itm_strike = spot * 0.5
    deep_itm_vol = surface.get_vol(deep_itm_strike, expiry)
    assert 0.05 < deep_itm_vol < 1.0, f"Deep ITM vol {deep_itm_vol} out of range"
    print(f"   ✅ Deep ITM (K={deep_itm_strike:.0f}): vol={deep_itm_vol:.4f}")
    
    # Extrapolated vols should be reasonable (not exploding)
    assert abs(deep_otm_vol - deep_itm_vol) < 0.5, \
        "Extrapolated vols differ too much"
    print("   ✅ Extrapolation is stable")


def test_single_expiry_surface():
    """
    Test surface with only one expiry.
    
    Should handle single expiry gracefully.
    Validates: Requirements 10.3
    """
    print("\n🧪 Test 3: Single Expiry Surface")
    
    quotes = []
    base_date = datetime.now().date()
    expiry = base_date + timedelta(days=30)
    spot = 450.0
    
    # Multiple strikes, single expiry
    strikes = np.linspace(spot * 0.85, spot * 1.15, 20)
    
    for strike in strikes:
        vol = 0.20 + 0.03 * abs(strike - spot) / spot
        
        quote = OptionQuote(
            underlying="SPY",
            strike=strike,
            expiry=expiry,
            option_type='call',
            implied_vol=vol,
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
    
    # Should fit successfully
    assert surface.fitted_model in [SurfaceModel.SVI, SurfaceModel.FLAT], \
        f"Unexpected model: {surface.fitted_model}"
    print(f"   ✅ Fitted with model: {surface.fitted_model.value}")
    
    # Should be able to get vols for that expiry
    vol = surface.get_vol(spot, expiry)
    assert 0.10 < vol < 0.50, f"Vol {vol} out of range"
    print(f"   ✅ ATM vol: {vol:.4f}")


def test_missing_expiry_interpolation():
    """
    Test interpolation for missing expiries.
    
    Should interpolate between available expiries.
    Validates: Requirements 10.4
    """
    print("\n🧪 Test 4: Missing Expiry Interpolation")
    
    quotes = []
    base_date = datetime.now().date()
    spot = 450.0
    
    # Create quotes for 30 and 90 days
    expiries = [
        base_date + timedelta(days=30),
        base_date + timedelta(days=90)
    ]
    
    for expiry in expiries:
        strikes = np.linspace(spot * 0.9, spot * 1.1, 15)
        
        for strike in strikes:
            vol = 0.20 + 0.001 * (expiry - base_date).days / 30
            
            quote = OptionQuote(
                underlying="SPY",
                strike=strike,
                expiry=expiry,
                option_type='call',
                implied_vol=vol,
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
    
    # Request vol for 60 days (between 30 and 90)
    missing_expiry = base_date + timedelta(days=60)
    vol_60d = surface.get_vol(spot, missing_expiry)
    
    # Get vols for known expiries
    vol_30d = surface.get_vol(spot, expiries[0])
    vol_90d = surface.get_vol(spot, expiries[1])
    
    # Interpolated vol should be between the two
    assert vol_30d <= vol_60d <= vol_90d or vol_90d <= vol_60d <= vol_30d, \
        f"Interpolated vol {vol_60d:.4f} not between {vol_30d:.4f} and {vol_90d:.4f}"
    print(f"   ✅ 30d vol: {vol_30d:.4f}")
    print(f"   ✅ 60d vol (interpolated): {vol_60d:.4f}")
    print(f"   ✅ 90d vol: {vol_90d:.4f}")


def test_zero_quotes():
    """
    Test surface with no quotes.
    
    Should return default vol.
    Validates: Requirements 10.3
    """
    print("\n🧪 Test 5: Zero Quotes")
    
    surface = IVSurface(underlying="SPY", spot_price=450.0)
    
    # Try to fit with no data
    success = surface.fit_surface(SurfaceModel.SVI)
    assert not success, "Should fail with no data"
    print("   ✅ Correctly failed to fit with no data")
    
    # Should return default vol
    expiry = datetime.now().date() + timedelta(days=30)
    vol = surface.get_vol(450.0, expiry)
    assert vol == 0.20, f"Expected default vol 0.20, got {vol}"
    print(f"   ✅ Returns default vol: {vol:.4f}")


def test_expired_options():
    """
    Test handling of expired options.
    
    Should return 0 vol for expired options.
    Validates: Requirements 10.4
    """
    print("\n🧪 Test 6: Expired Options")
    
    quotes = create_sparse_quotes(num_quotes=10)
    surface = create_iv_surface_from_quotes(
        underlying="SPY",
        spot_price=450.0,
        quotes=quotes,
        model=SurfaceModel.SVI
    )
    
    # Request vol for past expiry
    past_expiry = datetime.now().date() - timedelta(days=1)
    vol = surface.get_vol(450.0, past_expiry)
    
    assert vol == 0.0, f"Expected 0 vol for expired option, got {vol}"
    print("   ✅ Returns 0 vol for expired options")


def test_extreme_volatility_values():
    """
    Test handling of extreme volatility values in input.
    
    Should handle very high/low vols gracefully.
    Validates: Requirements 10.3
    """
    print("\n🧪 Test 7: Extreme Volatility Values")
    
    quotes = []
    base_date = datetime.now().date()
    expiry = base_date + timedelta(days=30)
    spot = 450.0
    
    # Create quotes with extreme vols
    strikes = np.linspace(spot * 0.9, spot * 1.1, 10)
    
    for i, strike in enumerate(strikes):
        # Alternate between very high and very low vols
        if i % 2 == 0:
            vol = 0.05  # Very low
        else:
            vol = 0.80  # Very high
        
        quote = OptionQuote(
            underlying="SPY",
            strike=strike,
            expiry=expiry,
            option_type='call',
            implied_vol=vol,
            bid=0.0,
            ask=0.0,
            mid_price=0.0,
            volume=100,
            open_interest=1000,
            timestamp=datetime.now()
        )
        quotes.append(quote)
    
    # Should handle extreme values
    surface = create_iv_surface_from_quotes(
        underlying="SPY",
        spot_price=spot,
        quotes=quotes,
        model=SurfaceModel.SVI
    )
    
    # Should fit (possibly with fallback)
    assert surface.fitted_model is not None, "Failed to fit with extreme vols"
    print(f"   ✅ Fitted with model: {surface.fitted_model.value}")
    
    # Should return reasonable vol
    vol = surface.get_vol(spot, expiry)
    assert 0.05 <= vol <= 1.0, f"Vol {vol} out of reasonable range"
    print(f"   ✅ Returns reasonable vol: {vol:.4f}")


def main():
    """Run all edge case tests"""
    print("🧪 IV SURFACE EDGE CASE TESTS")
    print("=" * 60)
    
    try:
        test_sparse_data_fitting()
        test_extreme_strike_extrapolation()
        test_single_expiry_surface()
        test_missing_expiry_interpolation()
        test_zero_quotes()
        test_expired_options()
        test_extreme_volatility_values()
        
        print("\n" + "=" * 60)
        print("✅ ALL EDGE CASE TESTS PASSED")
        return True
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        return False
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
