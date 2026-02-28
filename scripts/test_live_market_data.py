#!/usr/bin/env python3
"""
Simple Live Market Data Test

Tests that we can fetch real market data from Upstox during market hours.
Run this during market hours (9:30 AM - 3:30 PM IST) to verify data flow.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import logging
from datetime import datetime
import pytz

from src.volatility.market_data_feed import create_market_data_feed

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_market_hours():
    """Check if market is currently open"""
    ist = pytz.timezone('Asia/Kolkata')
    now = datetime.now(ist)
    
    # Market hours: 9:15 AM - 3:30 PM IST, Monday-Friday
    if now.weekday() >= 5:  # Saturday or Sunday
        return False, "Market closed (weekend)"
    
    market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
    market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
    
    if now < market_open:
        return False, f"Market opens at 9:15 AM IST (in {(market_open - now).seconds // 60} minutes)"
    elif now > market_close:
        return False, "Market closed for the day"
    else:
        return True, f"Market is OPEN (closes at 3:30 PM IST)"

def main():
    logger.info("=" * 80)
    logger.info("LIVE MARKET DATA TEST")
    logger.info("=" * 80)
    
    # Check market hours
    is_open, status = check_market_hours()
    logger.info(f"\nMarket Status: {status}")
    
    if not is_open:
        logger.warning("\n⚠️  Market is currently closed.")
        logger.warning("This test should be run during market hours (9:15 AM - 3:30 PM IST)")
        logger.warning("Data may be stale or unavailable.\n")
    
    # Get access token
    access_token = os.getenv('UPSTOX_ACCESS_TOKEN')
    if not access_token:
        logger.error("❌ UPSTOX_ACCESS_TOKEN not found in environment")
        logger.error("Run: source .env.options")
        return False
    
    logger.info(f"\nUsing token: {access_token[:20]}...")
    
    try:
        # Create market data feed
        logger.info("\n1. Creating market data feed...")
        feed = create_market_data_feed(access_token)
        logger.info("✓ Market data feed created")
        
        # Test underlying prices
        logger.info("\n2. Fetching underlying prices...")
        
        for symbol in ["NIFTY", "BANKNIFTY", "FINNIFTY"]:
            try:
                price = feed.get_underlying_price(symbol)
                logger.info(f"✓ {symbol:12s}: ₹{price:,.2f}")
            except Exception as e:
                logger.warning(f"⚠ {symbol:12s}: {str(e)}")
        
        # Test expiry dates
        logger.info("\n3. Getting next expiry dates...")
        try:
            expiries = feed.get_next_expiries("NIFTY", 3)
            logger.info(f"✓ Next 3 NIFTY expiries: {expiries}")
        except Exception as e:
            logger.warning(f"⚠ Could not get expiries: {e}")
        
        # Test option chain
        logger.info("\n4. Fetching option chain sample...")
        try:
            expiries = feed.get_next_expiries("NIFTY", 1)
            if expiries:
                chain = feed.get_option_chain("NIFTY", expiries[0])
                logger.info(f"✓ Option chain loaded: {len(chain)} contracts")
                
                if len(chain) > 0:
                    logger.info(f"  Sample contract: {chain.iloc[0]['instrument_key']}")
                    logger.info(f"  Strike: {chain.iloc[0]['strike']}")
                    logger.info(f"  Type: {chain.iloc[0]['option_type']}")
                else:
                    logger.warning("  ⚠ Option chain is empty (may be too early in session)")
        except Exception as e:
            logger.warning(f"⚠ Could not fetch option chain: {e}")
        
        logger.info("\n" + "=" * 80)
        logger.info("✓ TEST COMPLETED")
        logger.info("=" * 80)
        
        if not is_open:
            logger.info("\n💡 TIP: Run this test during market hours for full data validation")
        else:
            logger.info("\n✓ Market is open - data should be live and current")
        
        return True
        
    except Exception as e:
        logger.error(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
