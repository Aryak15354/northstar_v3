"""
Test IV Surface Implementation

Tests SVI fitting, no-arbitrage constraints, and surface quality.
"""

import numpy as np
from datetime import datetime, date, timedelta
from src.volatility import IVSurface, OptionQuote, SurfaceModel, create_iv_surface_from_quotes


def create_sample_quotes(underlying: str = "SPY", spot: float = 450.0) -> list:
    """Create sample option quotes for testing"""
    quotes = []
    base_date = datetime.now().date()
    
    # Create quotes for 3 expiries
    expiries = [
        base_date + timedelta(days=30),
        base_date + timedelta(days=60),
        base_date + timedelta(days=90)
    ]
    
    # Create quotes for multiple strikes
    strikes = np.linspace(spot * 0.9, spot * 1.1, 11)
    
    for expiry in expiries:
        for strike in strikes:
            # Generate realistic implied vol (smile shape)
            moneyness = strike / spot
            base_vol = 0.20
            
            # Add smile: higher vol for OTM options
            if moneyness < 1.0:
                vol = base_vol + 0.05 * (1.0 - moneyness)
            else:
                vol = base_vol + 0.03 * (moneyness - 1.0)
            
            # Add term structure: longer expiries have slightly higher vol
            days_to_expiry = (expiry - base_date).days
            vol += 0.001 * days_to_expiry / 30
            
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


def test_iv_surface_creation():
    """Test basic IV surface creation"""
    print("🧪 Test 1: IV Surface Creation")
    
    surface = IVSurface(underlying="SPY", spot_price=450.0, risk_free_rate=0.05)
    assert surface.underlying == "SPY"
    assert surface.spot_price == 450.0
    print("   ✅ Surface created successfully")


def test_svi_fitting():
    """Test SVI model fitting"""
    print("\n🧪 Test 2: SVI Fitting")
    
    quotes = create_sample_quotes()
    surface = create_iv_surface_from_quotes(
        underlying="SPY",
        spot_price=450.0,
        quotes=quotes,
        model=SurfaceModel.SVI
    )
    
    assert surface.fitted_model == SurfaceModel.SVI
    assert len(surface.svi_params_by_expiry) > 0
    print(f"   ✅ SVI fitted to {len(surface.svi_params_by_expiry)} expiries")
    
    # Test parameter validation
    for expiry, params in surface.svi_params_by_expiry.items():
        assert params.validate(), f"Invalid SVI parameters for {expiry}"
    print("   ✅ All SVI parameters valid")


def test_vol_retrieval():
    """Test volatility retrieval"""
    print("\n🧪 Test 3: Volatility Retrieval")
    
    quotes = create_sample_quotes()
    surface = create_iv_surface_from_quotes(
        underlying="SPY",
        spot_price=450.0,
        quotes=quotes,
        model=SurfaceModel.SVI
    )
    
    # Test at-the-money vol
    expiry = datetime.now().date() + timedelta(days=30)
    atm_vol = surface.get_vol(450.0, expiry)
    assert 0.10 < atm_vol < 0.40, f"ATM vol {atm_vol} out of reasonable range"
    print(f"   ✅ ATM vol: {atm_vol:.4f}")
    
    # Test out-of-the-money vol
    otm_vol = surface.get_vol(500.0, expiry)
    assert 0.10 < otm_vol < 0.50, f"OTM vol {otm_vol} out of reasonable range"
    print(f"   ✅ OTM vol: {otm_vol:.4f}")


def test_no_arbitrage():
    """Test no-arbitrage constraints"""
    print("\n🧪 Test 4: No-Arbitrage Constraints")
    
    quotes = create_sample_quotes()
    surface = create_iv_surface_from_quotes(
        underlying="SPY",
        spot_price=450.0,
        quotes=quotes,
        model=SurfaceModel.SVI
    )
    
    # Test calendar spread: longer expiry should have >= variance
    expiry1 = datetime.now().date() + timedelta(days=30)
    expiry2 = datetime.now().date() + timedelta(days=60)
    
    strike = 450.0
    var1 = surface.get_variance(strike, expiry1)
    var2 = surface.get_variance(strike, expiry2)
    
    assert var2 >= var1, f"Calendar arbitrage: var2 ({var2}) < var1 ({var1})"
    print(f"   ✅ Calendar spread: var1={var1:.6f}, var2={var2:.6f}")
    
    # Check quality metrics
    if surface.quality:
        print(f"   ✅ Arbitrage violations: {surface.quality.arbitrage_violations}")
        assert surface.quality.arbitrage_violations < 10, "Too many arbitrage violations"


def test_surface_quality():
    """Test surface quality metrics"""
    print("\n🧪 Test 5: Surface Quality")
    
    quotes = create_sample_quotes()
    surface = create_iv_surface_from_quotes(
        underlying="SPY",
        spot_price=450.0,
        quotes=quotes,
        model=SurfaceModel.SVI
    )
    
    quality_score = surface.get_quality_score()
    assert 0.0 <= quality_score <= 1.0, f"Quality score {quality_score} out of range"
    print(f"   ✅ Quality score: {quality_score:.3f}")
    
    if surface.quality:
        print(f"   ✅ RMSE: {surface.quality.fit_rmse:.4f}")
        print(f"   ✅ R²: {surface.quality.fit_r_squared:.4f}")
        print(f"   ✅ Coverage: {surface.quality.data_coverage:.2%}")


def test_fallback_models():
    """Test fallback to simpler models"""
    print("\n🧪 Test 6: Fallback Models")
    
    # Create surface with insufficient data
    surface = IVSurface(underlying="SPY", spot_price=450.0)
    
    # Add only a few quotes
    quotes = create_sample_quotes()[:5]
    surface.add_quotes(quotes)
    
    # Try to fit - should fallback to FLAT
    success = surface.fit_surface(SurfaceModel.SVI)
    assert success, "Fallback should succeed"
    assert surface.fitted_model == SurfaceModel.FLAT, "Should fallback to FLAT model"
    print(f"   ✅ Fallback to {surface.fitted_model.value} model")


def main():
    """Run all tests"""
    print("🧪 IV SURFACE TESTS")
    print("=" * 50)
    
    try:
        test_iv_surface_creation()
        test_svi_fitting()
        test_vol_retrieval()
        test_no_arbitrage()
        test_surface_quality()
        test_fallback_models()
        
        print("\n" + "=" * 50)
        print("✅ ALL TESTS PASSED")
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
