#!/usr/bin/env python3
"""
Test Upstox API Connection

Tests connection to Upstox API and provides detailed diagnostics.
Works even when market is closed.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import logging
from datetime import datetime, time
import requests

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def load_access_token() -> tuple[str, str]:
    """Load Upstox token using the same precedence as the live adapter."""
    try:
        from src.options.config_loader import get_config
        from src.options.upstox_adapter import UpstoxAdapter

        config = get_config(reload=True)
        adapter = UpstoxAdapter(config.upstox)
        token = adapter._load_access_token_from_sources(
            prefer_files=True,
            current_token=config.upstox.access_token,
        )
        token = str(token or config.upstox.access_token or "").strip()
        if token:
            return token, "options credential sources"
    except Exception as exc:
        logger.warning(f"Warning: failed loading token from options config: {exc}")

    token = os.getenv('UPSTOX_ACCESS_TOKEN', '').strip()
    if token:
        return token, "environment"
    return "", "unavailable"


def check_market_hours():
    """Check if market is currently open"""
    now = datetime.now()
    current_time = now.time()
    
    # IST market hours: 9:15 AM - 3:30 PM
    market_open = time(9, 15)
    market_close = time(15, 30)
    
    # Check if it's a weekday
    is_weekday = now.weekday() < 5  # Monday = 0, Friday = 4
    
    # Check if within market hours
    is_market_hours = market_open <= current_time <= market_close
    
    return is_weekday and is_market_hours


def test_api_authentication(access_token):
    """Test API authentication"""
    logger.info("\n1. Testing API Authentication...")
    
    try:
        headers = {
            'Accept': 'application/json',
            'Authorization': f'Bearer {access_token}'
        }
        
        # Test with a simple API call (user profile)
        url = "https://api.upstox.com/v2/user/profile"
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'success':
                user_data = data.get('data', {})
                logger.info(f"✓ Authentication successful!")
                logger.info(f"  User ID: {user_data.get('user_id', 'N/A')}")
                logger.info(f"  User Name: {user_data.get('user_name', 'N/A')}")
                logger.info(f"  Email: {user_data.get('email', 'N/A')}")
                return True
            else:
                logger.error(f"✗ API returned non-success status: {data}")
                return False
        
        elif response.status_code == 401:
            logger.error(f"✗ Authentication failed: Invalid or expired token")
            logger.error(f"  Please generate a new access token from Upstox")
            return False
        
        else:
            logger.error(f"✗ API request failed: {response.status_code}")
            logger.error(f"  Response: {response.text}")
            return False
    
    except requests.RequestException as e:
        logger.error(f"✗ Connection error: {e}")
        return False


def test_market_data_access(access_token):
    """Test market data access"""
    logger.info("\n2. Testing Market Data Access...")
    
    is_market_open = check_market_hours()
    
    if not is_market_open:
        logger.warning("⚠ Market is currently CLOSED")
        logger.info("  Market hours: 9:15 AM - 3:30 PM IST (Mon-Fri)")
        logger.info("  Some data may not be available outside market hours")
    else:
        logger.info("✓ Market is currently OPEN")
    
    try:
        headers = {
            'Accept': 'application/json',
            'Authorization': f'Bearer {access_token}'
        }
        
        # Try to fetch NIFTY quote
        instrument_key = "NSE_INDEX|Nifty 50"
        url = f"https://api.upstox.com/v2/market-quote/quotes"
        params = {'instrument_key': instrument_key}
        
        response = requests.get(url, headers=headers, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'success':
                quote_data = data.get('data', {}).get(instrument_key, {})
                
                if quote_data:
                    ltp = quote_data.get('last_price', 0)
                    logger.info(f"✓ Market data access successful!")
                    logger.info(f"  NIFTY Last Price: ₹{ltp:,.2f}")
                    
                    # Show additional data if available
                    ohlc = quote_data.get('ohlc', {})
                    if ohlc:
                        logger.info(f"  Open: ₹{ohlc.get('open', 0):,.2f}")
                        logger.info(f"  High: ₹{ohlc.get('high', 0):,.2f}")
                        logger.info(f"  Low: ₹{ohlc.get('low', 0):,.2f}")
                        logger.info(f"  Close: ₹{ohlc.get('close', 0):,.2f}")
                    
                    return True
                else:
                    logger.warning("⚠ No quote data returned (market may be closed)")
                    return True  # Auth worked, just no data
            else:
                logger.error(f"✗ API returned non-success status: {data}")
                return False
        
        elif response.status_code == 401:
            logger.error(f"✗ Authentication failed for market data")
            return False
        
        else:
            logger.error(f"✗ Market data request failed: {response.status_code}")
            logger.error(f"  Response: {response.text}")
            return False
    
    except requests.RequestException as e:
        logger.error(f"✗ Connection error: {e}")
        return False


def test_option_chain_access(access_token):
    """Test option chain access"""
    logger.info("\n3. Testing Option Chain Access...")
    
    try:
        headers = {
            'Accept': 'application/json',
            'Authorization': f'Bearer {access_token}'
        }
        
        # Try to fetch NIFTY option chain for next expiry
        from datetime import date, timedelta
        
        # Find next Thursday (NIFTY expiry)
        today = date.today()
        days_ahead = (3 - today.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7
        next_expiry = today + timedelta(days=days_ahead)
        
        instrument_key = "NSE_INDEX|Nifty 50"
        url = "https://api.upstox.com/v2/option/chain"
        params = {
            'instrument_key': instrument_key,
            'expiry_date': next_expiry.strftime("%Y-%m-%d")
        }
        
        logger.info(f"  Fetching option chain for expiry: {next_expiry}")
        
        response = requests.get(url, headers=headers, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'success':
                chain_data = data.get('data', [])
                
                if chain_data:
                    logger.info(f"✓ Option chain access successful!")
                    logger.info(f"  Retrieved {len(chain_data)} strike prices")
                    
                    # Show sample strike
                    if len(chain_data) > 0:
                        sample = chain_data[0]
                        logger.info(f"  Sample strike: {sample.get('strike_price', 0)}")
                        logger.info(f"  Spot price: ₹{sample.get('underlying_spot_price', 0):,.2f}")
                    
                    return True
                else:
                    logger.warning("⚠ Empty option chain (market may be closed)")
                    return True  # Auth worked, just no data
            else:
                logger.error(f"✗ API returned non-success status: {data}")
                return False
        
        elif response.status_code == 401:
            logger.error(f"✗ Authentication failed for option chain")
            return False
        
        else:
            logger.error(f"✗ Option chain request failed: {response.status_code}")
            logger.error(f"  Response: {response.text}")
            return False
    
    except Exception as e:
        logger.error(f"✗ Error: {e}")
        return False


def main():
    """Run connection tests"""
    logger.info("=" * 60)
    logger.info("Upstox API Connection Test")
    logger.info("=" * 60)
    
    access_token, token_source = load_access_token()
    
    if not access_token:
        logger.error("\n✗ ERROR: UPSTOX_ACCESS_TOKEN not found in environment")
        logger.error("Please refresh or configure the token:")
        logger.error("  python3 scripts/refresh_upstox_token.py")
        return 1
    
    logger.info(f"\nUsing access token from {token_source}: {access_token[:20]}...")
    
    # Check current time
    now = datetime.now()
    logger.info(f"Current time: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    
    is_market_open = check_market_hours()
    if is_market_open:
        logger.info("Market status: 🟢 OPEN")
    else:
        logger.info("Market status: 🔴 CLOSED")
        logger.info("Note: Some tests may show warnings due to market being closed")
    
    # Run tests
    results = {}
    
    results['authentication'] = test_api_authentication(access_token)
    results['market_data'] = test_market_data_access(access_token)
    results['option_chain'] = test_option_chain_access(access_token)
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("Test Summary")
    logger.info("=" * 60)
    
    for test_name, result in results.items():
        status = "✓ PASSED" if result else "✗ FAILED"
        logger.info(f"  {test_name:20s}: {status}")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    logger.info(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("\n✓ CONNECTION TEST PASSED")
        logger.info("\nYour Upstox API credentials are working correctly!")
        
        if not is_market_open:
            logger.info("\nNote: Market is currently closed.")
            logger.info("Run this test again during market hours (9:15 AM - 3:30 PM IST)")
            logger.info("to verify live data access.")
        
        return 0
    else:
        logger.error("\n✗ CONNECTION TEST FAILED")
        logger.error("\nPlease check:")
        logger.error("1. Your access token is valid (not expired)")
        logger.error("2. You have API access enabled in Upstox")
        logger.error("3. Your internet connection is working")
        logger.error("\nTo generate a new token:")
        logger.error("  Visit: https://account.upstox.com/developer/apps")
        return 1


if __name__ == "__main__":
    exit(main())
