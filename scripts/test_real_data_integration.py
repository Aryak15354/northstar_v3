#!/usr/bin/env python3
"""
Real Data Integration Test

Tests the complete integration with Upstox API:
1. Market data feed
2. Option chain loading
3. Greeks calculation
4. IV surface construction
5. Risk metrics computation
6. Broker execution interface (paper trading mode)
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import logging
from datetime import date, timedelta
from pathlib import Path
import pandas as pd

from src.volatility.market_data_feed import create_market_data_feed
from src.volatility.broker_execution import BrokerExecutionInterface, OrderSide, OrderType, ProductType
from src.volatility.greeks_aggregator import GreeksAggregator
from src.volatility.iv_surface import IVSurface
from src.volatility.risk_authority import UnifiedRiskAuthority
from src.volatility.config import ConfigurationManager

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_market_data_feed(access_token: str):
    """Test market data feed"""
    logger.info("=" * 80)
    logger.info("TEST 1: Market Data Feed")
    logger.info("=" * 80)
    
    try:
        # Create feed
        feed = create_market_data_feed(access_token)
        
        # Test 1: Get underlying price
        logger.info("\n1.1 Testing underlying price fetch...")
        nifty_price = feed.get_underlying_price("NIFTY")
        logger.info(f"✓ NIFTY Price: ₹{nifty_price:,.2f}")
        
        banknifty_price = feed.get_underlying_price("BANKNIFTY")
        logger.info(f"✓ BANKNIFTY Price: ₹{banknifty_price:,.2f}")
        
        # Test 2: Get next expiries
        logger.info("\n1.2 Testing expiry date calculation...")
        expiries = feed.get_next_expiries("NIFTY", 3)
        logger.info(f"✓ Next 3 expiries: {expiries}")
        
        # Test 3: Get option chain
        logger.info("\n1.3 Testing option chain fetch...")
        df = feed.get_option_chain("NIFTY", expiries[0])
        
        if not df.empty:
            logger.info(f"✓ Fetched {len(df)} option contracts")
            logger.info(f"  Strikes: {df['strike'].min():.0f} to {df['strike'].max():.0f}")
            logger.info(f"  Avg IV: {df['iv'].mean():.2%}")
            logger.info(f"  Total OI: {df['oi'].sum():,.0f}")
            
            # Show sample data
            logger.info("\n  Sample data (first 5 contracts):")
            sample = df[['strike', 'option_type', 'ltp', 'iv', 'delta', 'oi']].head()
            logger.info(f"\n{sample.to_string()}")
        else:
            logger.warning("✗ Empty option chain")
        
        # Test 4: Get ATM options
        logger.info("\n1.4 Testing ATM options fetch...")
        df_atm = feed.get_atm_options("NIFTY", expiries[0], num_strikes=3)
        
        if not df_atm.empty:
            logger.info(f"✓ Fetched {len(df_atm)} ATM contracts")
            logger.info(f"  ATM strike: {df_atm['strike'].median():.0f}")
        else:
            logger.warning("✗ Empty ATM options")
        
        # Test 5: Get IV surface
        logger.info("\n1.5 Testing IV surface construction...")
        iv_surface = feed.get_iv_surface("NIFTY", expiries[:2])
        
        if not iv_surface.empty:
            logger.info(f"✓ IV surface: {len(iv_surface)} points")
            logger.info(f"  Moneyness range: {iv_surface['moneyness'].min():.2f} to {iv_surface['moneyness'].max():.2f}")
            logger.info(f"  IV range: {iv_surface['iv'].min():.2%} to {iv_surface['iv'].max():.2%}")
        else:
            logger.warning("✗ Empty IV surface")
        
        # Test 6: Data quality validation
        logger.info("\n1.6 Testing data quality validation...")
        validation = feed.validate_data_quality(df)
        logger.info(f"  Valid: {validation['valid']}")
        logger.info(f"  Metrics:")
        for key, value in validation['metrics'].items():
            if isinstance(value, float):
                logger.info(f"    {key}: {value:.4f}")
            else:
                logger.info(f"    {key}: {value}")
        
        if validation.get('issues'):
            logger.warning(f"  Issues: {validation['issues']}")
        
        logger.info("\n✓ Market Data Feed Test PASSED")
        return True
    
    except Exception as e:
        logger.error(f"\n✗ Market Data Feed Test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_greeks_calculation(access_token: str):
    """Test Greeks calculation"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 2: Greeks Calculation")
    logger.info("=" * 80)
    
    try:
        # Get market data
        feed = create_market_data_feed(access_token)
        expiries = feed.get_next_expiries("NIFTY", 1)
        df = feed.get_atm_options("NIFTY", expiries[0], num_strikes=2)
        
        if df.empty:
            logger.warning("✗ No data for Greeks calculation")
            return False
        
        # Create Greeks aggregator
        logger.info("\n2.1 Testing portfolio Greeks aggregation...")
        aggregator = GreeksAggregator()
        
        # Add positions (simulate)
        positions = []
        for _, row in df.head(4).iterrows():
            position = {
                'symbol': row['symbol'],
                'strike': row['strike'],
                'expiry': row['expiry'],
                'option_type': row['option_type'],
                'quantity': 50 if row['option_type'] == 'CE' else -50,  # Long calls, short puts
                'spot': row['underlying_price'],
                'iv': row['iv'],
                'time_to_expiry': row['days_to_expiry'] / 365.0,
                'rate': 0.06
            }
            positions.append(position)
        
        # Calculate portfolio Greeks
        portfolio_greeks = aggregator.calculate_portfolio_greeks(positions)
        
        logger.info(f"✓ Portfolio Greeks:")
        logger.info(f"  Delta: {portfolio_greeks['delta']:.2f}")
        logger.info(f"  Gamma: {portfolio_greeks['gamma']:.4f}")
        logger.info(f"  Vega: {portfolio_greeks['vega']:.2f}")
        logger.info(f"  Theta: {portfolio_greeks['theta']:.2f}")
        
        # Test scenario analysis
        logger.info("\n2.2 Testing scenario analysis...")
        scenarios = aggregator.scenario_analysis(
            positions,
            spot_shifts=[-0.02, 0, 0.02],
            iv_shifts=[-0.10, 0, 0.10]
        )
        
        logger.info(f"✓ Scenario analysis: {len(scenarios)} scenarios")
        
        logger.info("\n✓ Greeks Calculation Test PASSED")
        return True
    
    except Exception as e:
        logger.error(f"\n✗ Greeks Calculation Test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_risk_metrics(access_token: str):
    """Test risk metrics computation"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 3: Risk Metrics Computation")
    logger.info("=" * 80)
    
    try:
        # Load configuration
        logger.info("\n3.1 Testing configuration loading...")
        config_manager = ConfigurationManager(Path("config/production_upstox.yaml"))
        config = config_manager.load_config()
        logger.info(f"✓ Configuration loaded")
        logger.info(f"  VaR 95% limit: ₹{config.risk.var_95:,.0f}")
        logger.info(f"  Max drawdown: {config.risk.max_drawdown:.1%}")
        
        # Create risk authority
        logger.info("\n3.2 Testing risk authority...")
        risk_authority = UnifiedRiskAuthority(config)
        
        # Mock state for testing
        mock_state = {
            'portfolio_greeks': {
                'delta': 300,
                'gamma': 150,
                'vega': 3000,
                'theta': -200
            },
            'positions': [
                {'symbol': 'NIFTY', 'quantity': 50, 'value': 100000},
                {'symbol': 'BANKNIFTY', 'quantity': 30, 'value': 80000}
            ],
            'total_capital': 1000000,
            'current_pnl': -5000
        }
        
        # Validate risk limits
        validation = risk_authority.validate_risk_limits(mock_state)
        logger.info(f"✓ Risk validation: {validation['approved']}")
        
        if not validation['approved']:
            logger.warning(f"  Violations: {validation['violations']}")
        
        logger.info("\n✓ Risk Metrics Test PASSED")
        return True
    
    except Exception as e:
        logger.error(f"\n✗ Risk Metrics Test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_broker_interface(api_key: str, api_secret: str, access_token: str):
    """Test broker execution interface (read-only)"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 4: Broker Execution Interface")
    logger.info("=" * 80)
    
    try:
        # Create broker interface
        logger.info("\n4.1 Testing broker interface initialization...")
        broker = BrokerExecutionInterface(api_key, api_secret, access_token)
        logger.info(f"✓ Broker interface initialized")
        
        # Test get positions (read-only)
        logger.info("\n4.2 Testing position retrieval...")
        try:
            positions = broker.get_positions()
            logger.info(f"✓ Retrieved {len(positions)} positions")
            
            for pos in positions[:5]:  # Show first 5
                logger.info(f"  {pos.instrument_key}: {pos.quantity} @ ₹{pos.average_price:.2f}, P&L: ₹{pos.pnl:.2f}")
        
        except Exception as e:
            logger.warning(f"  Could not retrieve positions: {e}")
        
        # Test execution metrics
        logger.info("\n4.3 Testing execution metrics...")
        metrics = broker.get_execution_metrics()
        logger.info(f"✓ Execution metrics:")
        logger.info(f"  Total orders: {metrics['total_orders']}")
        logger.info(f"  Fill rate: {metrics['fill_rate']:.2%}")
        logger.info(f"  Avg slippage: {metrics['avg_slippage']:.4f}")
        
        logger.info("\n✓ Broker Interface Test PASSED")
        logger.info("\nNOTE: Order placement not tested (requires paper trading mode)")
        return True
    
    except Exception as e:
        logger.error(f"\n✗ Broker Interface Test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all integration tests"""
    logger.info("=" * 80)
    logger.info("UNIFIED VOLATILITY ENGINE - REAL DATA INTEGRATION TEST")
    logger.info("=" * 80)
    
    # Get credentials from environment
    api_key = os.getenv('UPSTOX_API_KEY', '')
    api_secret = os.getenv('UPSTOX_API_SECRET', '')
    access_token = os.getenv('UPSTOX_ACCESS_TOKEN', '').strip()
    
    if not access_token:
        logger.error("ERROR: UPSTOX_ACCESS_TOKEN not found in environment")
        logger.error("Please set the access token:")
        logger.error("  export UPSTOX_ACCESS_TOKEN='your_token_here'")
        return 1
    
    logger.info(f"\nUsing access token: {access_token[:20]}...")
    
    # Run tests
    results = {}
    
    results['market_data'] = test_market_data_feed(access_token)
    results['greeks'] = test_greeks_calculation(access_token)
    results['risk_metrics'] = test_risk_metrics(access_token)
    
    if api_key and api_secret:
        results['broker'] = test_broker_interface(api_key, api_secret, access_token)
    else:
        logger.warning("\nSkipping broker interface test (credentials not found)")
        results['broker'] = None
    
    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("TEST SUMMARY")
    logger.info("=" * 80)
    
    passed = sum(1 for v in results.values() if v is True)
    failed = sum(1 for v in results.values() if v is False)
    skipped = sum(1 for v in results.values() if v is None)
    
    for test_name, result in results.items():
        status = "✓ PASSED" if result is True else "✗ FAILED" if result is False else "⊘ SKIPPED"
        logger.info(f"  {test_name:20s}: {status}")
    
    logger.info(f"\nTotal: {passed} passed, {failed} failed, {skipped} skipped")
    
    if failed > 0:
        logger.error("\n✗ INTEGRATION TEST FAILED")
        return 1
    else:
        logger.info("\n✓ INTEGRATION TEST PASSED")
        return 0


if __name__ == "__main__":
    exit(main())
