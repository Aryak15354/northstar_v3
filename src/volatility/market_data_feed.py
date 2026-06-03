#!/usr/bin/env python3
"""
Real-Time Market Data Feed for Unified Volatility Engine

Integrates with Upstox API to provide live market data for volatility trading.
Handles option chains, underlying prices, Greeks, and IV surface data.
"""

import logging
import time
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import pandas as pd
import numpy as np

from src.options.upstox_adapter import UpstoxAdapter
from src.options.config_loader import get_config
from src.options.stock_options_loader import get_stock_loader

logger = logging.getLogger(__name__)


@dataclass
class MarketDataSnapshot:
    """Snapshot of market data at a point in time"""
    timestamp: datetime
    underlying_prices: Dict[str, float]
    option_chains: Dict[str, pd.DataFrame]
    iv_surface: Dict[str, pd.DataFrame]
    correlation_matrix: Optional[pd.DataFrame] = None


class MarketDataFeed:
    """
    Real-time market data feed using Upstox API
    
    Features:
    - Live option chain data with Greeks
    - Underlying price tracking
    - IV surface construction
    - Correlation matrix updates
    - Data caching and validation
    """
    
    def __init__(self, access_token: str):
        """
        Initialize market data feed
        
        Args:
            access_token: Upstox API access token
        """
        # Load configuration
        config = get_config()
        config.upstox.access_token = access_token
        
        # Initialize Upstox adapter
        self.adapter = UpstoxAdapter(config.upstox)
        
        # Initialize stock loader
        self.stock_loader = get_stock_loader()
        
        # Cache
        self.last_snapshot: Optional[MarketDataSnapshot] = None
        self.last_update_time: Optional[datetime] = None
        
        # Supported underlyings
        self.supported_indices = ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"]
        self.supported_stocks = self.stock_loader.get_all_symbols()
        
        logger.info(f"MarketDataFeed initialized with {len(self.supported_indices)} indices and {len(self.supported_stocks)} stocks")
    
    def get_underlying_price(self, symbol: str) -> float:
        """
        Get current price of underlying
        
        Args:
            symbol: Symbol (index or stock)
        
        Returns:
            Current price
        """
        try:
            if symbol in self.supported_indices:
                return self.adapter.get_underlying_price(symbol)
            else:
                # For stocks, use instrument key
                instrument_key = self.stock_loader.get_instrument_key(symbol)
                if not instrument_key:
                    raise ValueError(f"Unknown symbol: {symbol}")
                raise NotImplementedError(
                    f"Stock price fetch is not implemented for {symbol}. "
                    "Configure a real stock market data source before using the volatility engine."
                )
        
        except Exception as e:
            logger.error(f"Error fetching price for {symbol}: {e}")
            raise
    
    def get_option_chain(
        self,
        underlying: str,
        expiry: date,
        strike_range: Optional[Tuple[float, float]] = None
    ) -> pd.DataFrame:
        """
        Get option chain for underlying and expiry
        
        Args:
            underlying: Underlying symbol
            expiry: Expiry date
            strike_range: Optional (min_strike, max_strike) to filter
        
        Returns:
            DataFrame with option chain data
        """
        try:
            # Determine instrument key
            instrument_key = None
            if underlying not in self.supported_indices:
                instrument_key = self.stock_loader.get_instrument_key(underlying)
                if not instrument_key:
                    raise ValueError(f"Unknown underlying: {underlying}")
            
            # Fetch option chain
            df = self.adapter.fetch_option_chain(underlying, expiry, instrument_key)
            
            if df.empty:
                logger.warning(f"Empty option chain for {underlying} {expiry}")
                return df
            
            # Filter by strike range if provided
            if strike_range:
                min_strike, max_strike = strike_range
                df = df[(df['strike'] >= min_strike) & (df['strike'] <= max_strike)]
            
            logger.info(f"Fetched {len(df)} options for {underlying} {expiry}")
            return df
        
        except Exception as e:
            logger.error(f"Error fetching option chain for {underlying} {expiry}: {e}")
            raise
    
    def get_atm_options(
        self,
        underlying: str,
        expiry: date,
        num_strikes: int = 5
    ) -> pd.DataFrame:
        """
        Get ATM options (centered around current spot)
        
        Args:
            underlying: Underlying symbol
            expiry: Expiry date
            num_strikes: Number of strikes on each side of ATM
        
        Returns:
            DataFrame with ATM options
        """
        # Get spot price
        spot = self.get_underlying_price(underlying)
        
        # Get option chain
        df = self.get_option_chain(underlying, expiry)
        
        if df.empty:
            return df
        
        # Find ATM strike
        strikes = sorted(df['strike'].unique())
        atm_strike = min(strikes, key=lambda x: abs(x - spot))
        atm_idx = strikes.index(atm_strike)
        
        # Get strikes around ATM
        start_idx = max(0, atm_idx - num_strikes)
        end_idx = min(len(strikes), atm_idx + num_strikes + 1)
        selected_strikes = strikes[start_idx:end_idx]
        
        # Filter dataframe
        df_atm = df[df['strike'].isin(selected_strikes)]
        
        logger.info(f"ATM options for {underlying}: {len(df_atm)} contracts around strike {atm_strike}")
        return df_atm
    
    def get_iv_surface(
        self,
        underlying: str,
        expiries: List[date]
    ) -> pd.DataFrame:
        """
        Construct IV surface from option chains
        
        Args:
            underlying: Underlying symbol
            expiries: List of expiry dates
        
        Returns:
            DataFrame with IV surface (strike, expiry, iv, moneyness)
        """
        all_data = []
        spot = self.get_underlying_price(underlying)
        
        for expiry in expiries:
            df = self.get_option_chain(underlying, expiry)
            
            if df.empty:
                continue
            
            # Calculate moneyness
            df['moneyness'] = df['strike'] / spot
            
            # Average IV for calls and puts at same strike
            iv_data = df.groupby('strike').agg({
                'iv': 'mean',
                'moneyness': 'first',
                'days_to_expiry': 'first'
            }).reset_index()
            
            iv_data['expiry'] = expiry
            iv_data['underlying'] = underlying
            
            all_data.append(iv_data)
        
        if not all_data:
            logger.warning(f"No IV surface data for {underlying}")
            return pd.DataFrame()
        
        iv_surface = pd.concat(all_data, ignore_index=True)
        
        logger.info(f"IV surface for {underlying}: {len(iv_surface)} points across {len(expiries)} expiries")
        return iv_surface
    
    def get_market_snapshot(
        self,
        underlyings: List[str],
        expiries: Dict[str, List[date]]
    ) -> MarketDataSnapshot:
        """
        Get complete market data snapshot
        
        Args:
            underlyings: List of underlying symbols
            expiries: Dict mapping underlying to list of expiry dates
        
        Returns:
            MarketDataSnapshot with all data
        """
        timestamp = datetime.now()
        
        # Get underlying prices
        underlying_prices = {}
        for symbol in underlyings:
            try:
                underlying_prices[symbol] = self.get_underlying_price(symbol)
            except Exception as e:
                logger.error(f"Failed to fetch price for {symbol}: {e}")
                underlying_prices[symbol] = None
        
        # Get option chains
        option_chains = {}
        for symbol in underlyings:
            symbol_expiries = expiries.get(symbol, [])
            for expiry in symbol_expiries:
                key = f"{symbol}_{expiry}"
                try:
                    option_chains[key] = self.get_option_chain(symbol, expiry)
                except Exception as e:
                    logger.error(f"Failed to fetch option chain for {symbol} {expiry}: {e}")
                    option_chains[key] = pd.DataFrame()
        
        # Get IV surfaces
        iv_surface = {}
        for symbol in underlyings:
            symbol_expiries = expiries.get(symbol, [])
            if symbol_expiries:
                try:
                    iv_surface[symbol] = self.get_iv_surface(symbol, symbol_expiries)
                except Exception as e:
                    logger.error(f"Failed to construct IV surface for {symbol}: {e}")
                    iv_surface[symbol] = pd.DataFrame()
        
        # Create snapshot
        snapshot = MarketDataSnapshot(
            timestamp=timestamp,
            underlying_prices=underlying_prices,
            option_chains=option_chains,
            iv_surface=iv_surface
        )
        
        self.last_snapshot = snapshot
        self.last_update_time = timestamp
        
        logger.info(f"Market snapshot created at {timestamp}")
        return snapshot
    
    def get_next_expiries(
        self,
        underlying: str,
        num_expiries: int = 3
    ) -> List[date]:
        """
        Get next N expiry dates for underlying
        
        Args:
            underlying: Underlying symbol
            num_expiries: Number of expiries to return
        
        Returns:
            List of expiry dates
        """
        # Indian market expiry days (as of 2026):
        # NIFTY: Tuesday (1)
        # BANKNIFTY: Wednesday (2)  
        # FINNIFTY: Tuesday (1)
        # MIDCPNIFTY: Monday (0)
        
        expiry_day_map = {
            'NIFTY': 1,  # Tuesday
            'BANKNIFTY': 2,  # Wednesday
            'FINNIFTY': 1,  # Tuesday
            'MIDCPNIFTY': 0,  # Monday
        }
        
        expiry_day = expiry_day_map.get(underlying, 1)  # Default to Tuesday
        
        today = date.today()
        expiries = []
        
        # Find next expiry day
        days_ahead = (expiry_day - today.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7  # If today is the expiry day, get next week
        
        next_expiry = today + timedelta(days=days_ahead)
        
        # Get next N expiries
        for i in range(num_expiries):
            expiry = next_expiry + timedelta(weeks=i)
            expiries.append(expiry)
        
        logger.info(f"Next {num_expiries} expiries for {underlying}: {expiries}")
        return expiries
    
    def validate_data_quality(self, df: pd.DataFrame) -> Dict[str, any]:
        """
        Validate option chain data quality
        
        Args:
            df: Option chain DataFrame
        
        Returns:
            Dict with validation results
        """
        if df.empty:
            return {
                'valid': False,
                'reason': 'Empty dataframe',
                'metrics': {}
            }
        
        metrics = {
            'total_contracts': len(df),
            'avg_bid_ask_spread': ((df['ask'] - df['bid']) / df['ltp']).mean(),
            'zero_oi_pct': (df['oi'] == 0).sum() / len(df) * 100,
            'zero_volume_pct': (df['volume'] == 0).sum() / len(df) * 100,
            'avg_iv': df['iv'].mean(),
            'iv_std': df['iv'].std()
        }
        
        # Validation checks
        issues = []
        
        if metrics['avg_bid_ask_spread'] > 0.10:  # 10% spread
            issues.append(f"High bid-ask spread: {metrics['avg_bid_ask_spread']:.2%}")
        
        if metrics['zero_oi_pct'] > 50:
            issues.append(f"High zero OI percentage: {metrics['zero_oi_pct']:.1f}%")
        
        if metrics['avg_iv'] < 0.05 or metrics['avg_iv'] > 2.0:
            issues.append(f"Unusual IV level: {metrics['avg_iv']:.2%}")
        
        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'metrics': metrics
        }


def create_market_data_feed(access_token: str) -> MarketDataFeed:
    """
    Factory function to create market data feed
    
    Args:
        access_token: Upstox API access token
    
    Returns:
        MarketDataFeed instance
    """
    return MarketDataFeed(access_token)


if __name__ == "__main__":
    # Test market data feed
    import logging
    import os
    
    logging.basicConfig(level=logging.INFO)
    
    # Get access token from environment only.
    access_token = os.getenv('UPSTOX_ACCESS_TOKEN', '').strip()
    if not access_token:
        raise RuntimeError("UPSTOX_ACCESS_TOKEN is required in environment")
    
    feed = create_market_data_feed(access_token)
    
    # Test underlying price
    try:
        nifty_price = feed.get_underlying_price("NIFTY")
        print(f"\nNIFTY Price: {nifty_price}")
    except Exception as e:
        print(f"Error: {e}")
    
    # Test option chain
    try:
        expiries = feed.get_next_expiries("NIFTY", 2)
        print(f"\nNext expiries: {expiries}")
        
        df = feed.get_atm_options("NIFTY", expiries[0], num_strikes=3)
        print(f"\nATM Options ({len(df)} contracts):")
        print(df[['strike', 'option_type', 'ltp', 'iv', 'delta', 'oi']].head(10))
        
        # Validate data quality
        validation = feed.validate_data_quality(df)
        print(f"\nData Quality:")
        print(f"  Valid: {validation['valid']}")
        print(f"  Metrics: {validation['metrics']}")
        if validation.get('issues'):
            print(f"  Issues: {validation['issues']}")
    
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
