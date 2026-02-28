"""
Manual test for Upstox adapter

Run this script to verify Upstox API integration works with real credentials.
This is NOT an automated test - it requires live API access.
"""

import sys
import logging
from datetime import date, timedelta
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.options.config_loader import get_config
from src.options.upstox_adapter import UpstoxAdapter

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def test_config_loading():
    """Test 1: Configuration loads successfully"""
    print("\n" + "="*60)
    print("TEST 1: Configuration Loading")
    print("="*60)
    
    try:
        config = get_config()
        print(f"✓ Configuration loaded successfully")
        print(f"  - API Key: {config.upstox.api_key[:20]}...")
        print(f"  - Rate limit: {config.upstox.rate_limit_per_second} req/sec")
        print(f"  - Max instruments: {config.upstox.max_instruments_per_request}")
        return config
    except Exception as e:
        print(f"✗ Configuration loading failed: {e}")
        return None


def test_adapter_initialization(config):
    """Test 2: Adapter initializes correctly"""
    print("\n" + "="*60)
    print("TEST 2: Adapter Initialization")
    print("="*60)
    
    try:
        adapter = UpstoxAdapter(config.upstox)
        print(f"✓ Adapter initialized successfully")
        print(f"  - Rate limiter configured: {adapter.rate_limiter.max_calls_per_second} req/sec")
        print(f"  - Session headers set")
        return adapter
    except Exception as e:
        print(f"✗ Adapter initialization failed: {e}")
        return None


def test_underlying_price(adapter):
    """Test 3: Fetch underlying price"""
    print("\n" + "="*60)
    print("TEST 3: Underlying Price Fetch")
    print("="*60)
    
    for symbol in ["NIFTY", "BANKNIFTY"]:
        try:
            price = adapter.get_underlying_price(symbol)
            print(f"✓ {symbol} price: ₹{price:,.2f}")
        except Exception as e:
            print(f"✗ Failed to fetch {symbol} price: {e}")
            return False
    
    return True


def test_option_chain(adapter):
    """Test 4: Fetch option chain"""
    print("\n" + "="*60)
    print("TEST 4: Option Chain Fetch")
    print("="*60)
    
    # Use next Thursday (weekly expiry)
    today = date.today()
    days_until_thursday = (3 - today.weekday()) % 7
    if days_until_thursday == 0:
        days_until_thursday = 7  # Next week if today is Thursday
    expiry = today + timedelta(days=days_until_thursday)
    
    print(f"Fetching NIFTY option chain for expiry: {expiry}")
    
    try:
        df = adapter.fetch_option_chain("NIFTY", expiry)
        
        if df.empty:
            print(f"✗ Empty option chain returned")
            return False
        
        print(f"✓ Fetched {len(df)} option contracts")
        print(f"\nData Summary:")
        print(f"  - Strikes: {df['strike'].min():.0f} to {df['strike'].max():.0f}")
        print(f"  - Call options: {len(df[df['option_type'] == 'C'])}")
        print(f"  - Put options: {len(df[df['option_type'] == 'P'])}")
        print(f"  - Underlying price: ₹{df['underlying_price'].iloc[0]:,.2f}")
        print(f"  - Days to expiry: {df['days_to_expiry'].iloc[0]}")
        
        print(f"\nSample ATM options:")
        atm_strike = round(df['underlying_price'].iloc[0] / 50) * 50
        atm_options = df[df['strike'] == atm_strike]
        
        if not atm_options.empty:
            for _, row in atm_options.iterrows():
                print(f"  {row['strike']:.0f} {row['option_type']}: "
                      f"Bid={row['bid']:.2f}, Ask={row['ask']:.2f}, "
                      f"IV={row['iv']*100:.1f}%, Delta={row['delta']:.3f}")
        
        print(f"\nData Validation:")
        print(f"  - All bids <= asks: {(df['bid'] <= df['ask']).all()}")
        print(f"  - All strikes > 0: {(df['strike'] > 0).all()}")
        print(f"  - All gamma >= 0: {(df['gamma'] >= 0).all()}")
        print(f"  - All vega >= 0: {(df['vega'] >= 0).all()}")
        print(f"  - All IV >= 0: {(df['iv'] >= 0).all()}")
        print(f"  - All OI > 0: {(df['oi'] > 0).all()}")
        print(f"  - Bid_qty present: {df['bid_qty'].notna().all()}")
        print(f"  - Ask_qty present: {df['ask_qty'].notna().all()}")
        
        return True
        
    except Exception as e:
        print(f"✗ Option chain fetch failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_data_normalization(adapter):
    """Test 5: Data normalization"""
    print("\n" + "="*60)
    print("TEST 5: Data Normalization")
    print("="*60)
    
    try:
        expiry = date.today() + timedelta(days=7)
        df = adapter.fetch_option_chain("NIFTY", expiry)
        
        required_columns = [
            'timestamp', 'symbol', 'expiry', 'strike', 'option_type',
            'bid', 'ask', 'ltp', 'bid_qty', 'ask_qty', 'volume',
            'oi', 'prev_oi', 'change_oi', 'iv', 'delta', 'gamma',
            'theta', 'vega', 'underlying_price', 'days_to_expiry'
        ]
        
        missing_columns = set(required_columns) - set(df.columns)
        
        if missing_columns:
            print(f"✗ Missing columns: {missing_columns}")
            return False
        
        print(f"✓ All required columns present")
        print(f"  Columns: {', '.join(df.columns)}")
        
        # Check data types
        print(f"\nData Types:")
        print(f"  - strike: {df['strike'].dtype}")
        print(f"  - bid: {df['bid'].dtype}")
        print(f"  - iv: {df['iv'].dtype}")
        print(f"  - delta: {df['delta'].dtype}")
        
        return True
        
    except Exception as e:
        print(f"✗ Data normalization test failed: {e}")
        return False


def test_rate_limiting(adapter):
    """Test 6: Rate limiting"""
    print("\n" + "="*60)
    print("TEST 6: Rate Limiting")
    print("="*60)
    
    import time
    
    try:
        print("Making 3 consecutive requests...")
        start_time = time.time()
        
        for i in range(3):
            adapter.get_underlying_price("NIFTY")
            print(f"  Request {i+1} completed")
        
        elapsed = time.time() - start_time
        expected_min_time = 2.0  # 3 requests at 1 req/sec = 2 seconds minimum
        
        print(f"\nElapsed time: {elapsed:.2f}s")
        print(f"Expected minimum: {expected_min_time:.2f}s")
        
        if elapsed >= expected_min_time:
            print(f"✓ Rate limiting working correctly")
            return True
        else:
            print(f"✗ Rate limiting may not be working (too fast)")
            return False
            
    except Exception as e:
        print(f"✗ Rate limiting test failed: {e}")
        return False


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("UPSTOX ADAPTER VERIFICATION TESTS")
    print("="*60)
    print("\nThis script tests the Upstox adapter with live API calls.")
    print("Ensure you have valid credentials in .env.options")
    print("\nNote: Upstox access tokens expire daily.")
    print("If you get 401 errors, generate a new token from Upstox dashboard.")
    
    # Run tests
    config = test_config_loading()
    if not config:
        print("\n✗ FAILED: Configuration loading")
        return
    
    adapter = test_adapter_initialization(config)
    if not adapter:
        print("\n✗ FAILED: Adapter initialization")
        return
    
    # Test API calls
    results = {
        "Underlying Price": test_underlying_price(adapter),
        "Option Chain": test_option_chain(adapter),
        "Data Normalization": test_data_normalization(adapter),
        "Rate Limiting": test_rate_limiting(adapter)
    }
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {test_name}")
    
    all_passed = all(results.values())
    
    if all_passed:
        print("\n✓ ALL TESTS PASSED")
        print("\nUpstox adapter is working correctly!")
        print("You can now proceed to implement regime detection.")
    else:
        print("\n✗ SOME TESTS FAILED")
        print("\nPlease fix the issues before proceeding.")
        print("\nCommon issues:")
        print("  - Expired access token (generate new token from Upstox)")
        print("  - Invalid API credentials")
        print("  - Network connectivity issues")
        print("  - API rate limits exceeded")


if __name__ == "__main__":
    main()
