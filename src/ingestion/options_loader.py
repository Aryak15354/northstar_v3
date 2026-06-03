"""
OptionsLoader — Load options chain data (historical and live).

Data sources:
- data/options/historical/ — Historical option chains
- data/options/eod/ — End-of-day collections
- data/options/chains_cache/ — Cached chain data
- Live data: Upstox API (via src/options/upstox_adapter.py)

Supports both historical (backtesting) and live (trading) modes.
"""

import logging
from datetime import datetime, time as dt_time
from pathlib import Path
from typing import List, Optional

import pandas as pd

from .base_loader import BaseLoader, DataNotFoundError

logger = logging.getLogger(__name__)


class MarketClosedError(Exception):
    """Raised when attempting to fetch live data outside market hours."""
    pass


class OptionsLoader(BaseLoader):
    """Loads option chain data with dual historical/live modes."""
    
    def load(self, as_of_date: datetime, **kwargs) -> pd.DataFrame:
        """
        Load options data (delegates to load_historical_chains).
        
        Args:
            as_of_date: Point-in-time date
            **kwargs: Additional parameters for load_historical_chains
            
        Returns:
            DataFrame with options data
        """
        return self.load_historical_chains(as_of_date, **kwargs)
    
    def load_historical_chains(
        self,
        as_of_date: datetime,
        underlying: str = 'NIFTY',
        expiry: Optional[datetime] = None
    ) -> pd.DataFrame:
        """
        Load historical option chain as of a specific date.
        
        Args:
            as_of_date: Point-in-time date
            underlying: 'NIFTY', 'BANKNIFTY', or stock ticker
            expiry: Specific expiry date (None = nearest expiry)
            
        Returns:
            DataFrame with (Strike, OptionType, Expiry) as index
        """
        start_time = pd.Timestamp.now()
        
        try:
            # Construct file path
            hist_dir = Path(self.paths_config.get('options_historical', 'data/options/historical'))
            file_path = hist_dir / f"{underlying.lower()}_option_chains.parquet"
            
            if not file_path.exists():
                logger.warning(f"Historical option chains not found: {file_path}")
                return pd.DataFrame()
            
            df = pd.read_parquet(file_path)
            
            # Standardize column names
            if 'date' in df.columns:
                df = df.rename(columns={'date': 'Date'})
            if 'expiry' in df.columns:
                df = df.rename(columns={'expiry': 'Expiry'})
            if 'strike' in df.columns:
                df = df.rename(columns={'strike': 'Strike'})
            if 'option_type' in df.columns:
                df = df.rename(columns={'option_type': 'OptionType'})
            
            # Convert dates
            if 'Date' in df.columns:
                df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
            if 'Expiry' in df.columns:
                df['Expiry'] = pd.to_datetime(df['Expiry'], errors='coerce')
            
            # PIT enforcement
            if 'Date' in df.columns:
                df = df[df['Date'] <= as_of_date].copy()
                self._validate_pit(df, 'Date', as_of_date)
                
                # Get data for the specific date (or closest before)
                available_dates = df['Date'].unique()
                if len(available_dates) > 0:
                    closest_date = max([d for d in available_dates if d <= pd.Timestamp(as_of_date)])
                    df = df[df['Date'] == closest_date]
            
            if df.empty:
                logger.warning(f"No option chain data for {underlying} on {as_of_date}")
                return df
            
            # Filter by expiry if specified
            if expiry and 'Expiry' in df.columns:
                df = df[df['Expiry'] == expiry]
            elif 'Expiry' in df.columns:
                # Get nearest expiry
                nearest_expiry = df['Expiry'].min()
                df = df[df['Expiry'] == nearest_expiry]
            
            # Set index if columns exist
            index_cols = [c for c in ['Strike', 'OptionType', 'Expiry'] if c in df.columns]
            if len(index_cols) >= 2:
                df = df.set_index(index_cols)
            
            elapsed_ms = (pd.Timestamp.now() - start_time).total_seconds() * 1000
            self._log_load(len(df), len(df.columns), str(file_path), elapsed_ms, as_of_date)
            
            return df
            
        except Exception as e:
            logger.error(f"Error loading historical option chains: {e}")
            return pd.DataFrame()
    
    def load_iv_history(
        self,
        as_of_date: datetime,
        underlying: str = 'NIFTY',
        start_date: Optional[datetime] = None
    ) -> pd.DataFrame:
        """
        Load historical IV data.
        
        Args:
            as_of_date: Point-in-time date
            underlying: Underlying symbol
            start_date: Start date for history
            
        Returns:
            DataFrame with Date as index and IV metrics
        """
        try:
            iv_path = Path(self.paths_config.get('options_historical', 'data/options')) / 'iv_history.parquet'
            
            if not iv_path.exists():
                logger.warning("IV history not found")
                return pd.DataFrame()
            
            df = pd.read_parquet(iv_path)
            
            # Filter by underlying
            if 'underlying' in df.columns:
                df = df[df['underlying'] == underlying]
            
            # Ensure date column
            if 'date' in df.columns:
                df = df.rename(columns={'date': 'Date'})
            df['Date'] = pd.to_datetime(df['Date'])
            
            # PIT enforcement
            df = df[df['Date'] <= as_of_date].copy()
            self._validate_pit(df, 'Date', as_of_date)
            
            # Filter by start date
            if start_date:
                df = df[df['Date'] >= start_date]
            
            df = df.set_index('Date')
            
            return df
            
        except Exception as e:
            logger.error(f"Error loading IV history: {e}")
            return pd.DataFrame()
    
    def load_live_chain(
        self,
        underlying: str = 'NIFTY',
        expiry: Optional[datetime] = None
    ) -> pd.DataFrame:
        """
        Load live option chain from Upstox API.
        
        CRITICAL: Only valid during market hours (9:15-15:30 IST).
        
        Args:
            underlying: Underlying symbol
            expiry: Specific expiry (None = nearest)
            
        Returns:
            DataFrame with live option chain
            
        Raises:
            MarketClosedError: If called outside market hours
        """
        # Check market hours
        if not self._is_market_open():
            raise MarketClosedError("Cannot fetch live data outside market hours (9:15-15:30 IST)")
        
        try:
            # Import upstox adapter
            from src.options.upstox_adapter import UpstoxAdapter
            
            adapter = UpstoxAdapter(self.config)
            
            # Fetch live chain
            df = adapter.get_option_chain(underlying, expiry)
            
            logger.info(f"Fetched live option chain for {underlying}: {len(df)} options")
            
            return df
            
        except ImportError:
            logger.error("Upstox adapter not available")
            return pd.DataFrame()
        except Exception as e:
            logger.error(f"Error fetching live option chain: {e}")
            return pd.DataFrame()
    
    def load_stock_options(
        self,
        as_of_date: datetime,
        ticker: str,
        expiry: Optional[datetime] = None
    ) -> pd.DataFrame:
        """
        Load stock option chains (not index options).
        
        Args:
            as_of_date: Point-in-time date
            ticker: Stock ticker
            expiry: Specific expiry (None = nearest)
            
        Returns:
            DataFrame with stock option chain
        """
        try:
            # Use stock options loader
            from src.options.stock_options_loader import get_stock_loader
            
            stock_loader = get_stock_loader()
            stock_info = stock_loader.get_stock(ticker)
            
            if not stock_info:
                logger.warning(f"Stock {ticker} not found in options mapping")
                return pd.DataFrame()
            
            # Load historical chains for this stock
            return self.load_historical_chains(as_of_date, ticker, expiry)
            
        except ImportError:
            logger.error("Stock options loader not available")
            return pd.DataFrame()
        except Exception as e:
            logger.error(f"Error loading stock options: {e}")
            return pd.DataFrame()
    
    def _is_market_open(self) -> bool:
        """Check if market is currently open."""
        try:
            # Import clock guard
            from src.options.clock_guard import ClockGuard
            
            clock = ClockGuard(self.config)
            return clock.is_market_open()
            
        except ImportError:
            # Fall back to simple time check
            now = datetime.now()
            
            # Check if weekday
            if now.weekday() >= 5:  # Saturday or Sunday
                return False
            
            # Check time (9:15 AM - 3:30 PM IST)
            market_open = dt_time(9, 15)
            market_close = dt_time(15, 30)
            current_time = now.time()
            
            return market_open <= current_time <= market_close
        except Exception as e:
            logger.error(f"Error checking market hours: {e}")
            return False
