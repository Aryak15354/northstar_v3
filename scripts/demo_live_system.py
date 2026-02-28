#!/usr/bin/env python3
"""
Live System Demo

Demonstrates the system working with live Upstox data
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import logging
from datetime import datetime
import time

from src.volatility.market_data_feed import create_market_data_feed

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    logger.info("=" * 80)
    logger.info("UNIFIED VOLATILITY ENGINE - LIVE DEMO")
    logger.info("=" * 80)
    
    # Get access token
    access_token = os.getenv('UPSTOX_ACCESS_TOKEN')
    if not access_token:
        logger.error("UPSTOX_ACCESS_TOKEN not found in environment")
        logger.error("Run: source .env.options")
        return 1
    
    logger.info(f"Token: {access_token[:30]}...")
    
    # Create market data feed
    logger.info("\nInitializing market data feed...")
    feed = create_market_data_feed(access_token)
    logger.info("✓ Market data feed initialized")
    logger.info(f"  System ready for live trading")
    
    # Continuous monitoring loop
    logger.info("\n" + "=" * 80)
    logger.info("LIVE MONITORING (Press Ctrl+C to stop)")
    logger.info("=" * 80)
    
    try:
        iteration = 0
        while True:
            iteration += 1
            logger.info(f"\n--- Update #{iteration} at {datetime.now().strftime('%H:%M:%S')} ---")
            
            # Fetch live prices
            try:
                nifty_price = feed.get_underlying_price("NIFTY")
                banknifty_price = feed.get_underlying_price("BANKNIFTY")
                finnifty_price = feed.get_underlying_price("FINNIFTY")
                
                logger.info(f"NIFTY:     ₹{nifty_price:,.2f}")
                logger.info(f"BANKNIFTY: ₹{banknifty_price:,.2f}")
                logger.info(f"FINNIFTY:  ₹{finnifty_price:,.2f}")
                
            except Exception as e:
                logger.error(f"Error fetching prices: {e}")
            
            # Fetch option chain sample
            try:
                expiries = feed.get_next_expiries("NIFTY", 1)
                if expiries:
                    chain = feed.get_option_chain("NIFTY", expiries[0])
                    logger.info(f"Option contracts: {len(chain)}")
                    
                    if len(chain) > 0:
                        avg_iv = chain['iv'].mean()
                        logger.info(f"Average IV: {avg_iv:.2%}")
                        
            except Exception as e:
                logger.error(f"Error fetching option chain: {e}")
            
            # Wait before next update
            time.sleep(30)  # Update every 30 seconds
            
    except KeyboardInterrupt:
        logger.info("\n\nStopping monitoring...")
        logger.info("System stopped")
        return 0

if __name__ == "__main__":
    sys.exit(main())
