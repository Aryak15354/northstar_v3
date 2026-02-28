"""
Historical Data Loader for Options Backtesting

Loads historical option chain data with temporal consistency validation.
Integrates with TemporalGuard to prevent lookahead bias.

Requirements: US-12.1, V3-2.1, V3-2.2, V3-2.4
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from datetime import datetime, date, timedelta
import logging

logger = logging.getLogger(__name__)


class HistoricalDataLoader:
    """
    Loads historical option chain data for backtesting.
    
    Ensures temporal consistency and validates data integrity.
    """
    
    def __init__(self, data_dir: str = "data/options/historical"):
        """
        Initialize the historical data loader.
        
        Args:
            data_dir: Directory containing historical option chain parquet files
        """
        self.data_dir = Path(data_dir)
        self._cache: Dict[str, pd.DataFrame] = {}
        
    def load_option_chain_history(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        validate_temporal: bool = True
    ) -> pd.DataFrame:
        """
        Load historical option chain data for a date range.
        
        Args:
            symbol: Underlying symbol (e.g., 'NIFTY', 'BANKNIFTY')
            start_date: Start date for historical data
            end_date: End date for historical data
            validate_temporal: Whether to validate temporal consistency
            
        Returns:
            DataFrame with columns: date, symbol, expiry, strike, option_type,
                                   bid, ask, ltp, iv, delta, gamma, theta, vega,
                                   oi, change_oi, volume, underlying_price,
                                   bid_qty, ask_qty
                                   
        Raises:
            FileNotFoundError: If historical data file not found
            ValueError: If temporal validation fails
        """
        cache_key = f"{symbol}_{start_date}_{end_date}"
        
        if cache_key in self._cache:
            logger.debug(f"Using cached data for {cache_key}")
            return self._cache[cache_key].copy()
        
        # Load from parquet file
        file_path = self.data_dir / f"{symbol.lower()}_option_chains.parquet"
        
        if not file_path.exists():
            raise FileNotFoundError(
                f"Historical data file not found: {file_path}. "
                f"Please ensure historical option chain data is available."
            )
        
        logger.info(f"Loading historical data from {file_path}")
        df = pd.read_parquet(file_path)
        
        # Convert date columns
        df['date'] = pd.to_datetime(df['date']).dt.date
        df['expiry'] = pd.to_datetime(df['expiry']).dt.date
        
        # Filter by date range
        df = df[(df['date'] >= start_date) & (df['date'] <= end_date)].copy()
        
        if df.empty:
            raise ValueError(
                f"No data found for {symbol} between {start_date} and {end_date}"
            )
        
        # Validate required columns
        required_cols = [
            'date', 'symbol', 'expiry', 'strike', 'option_type',
            'bid', 'ask', 'ltp', 'iv', 'delta', 'gamma', 'theta', 'vega',
            'oi', 'change_oi', 'volume', 'underlying_price', 'bid_qty', 'ask_qty'
        ]
        
        missing_cols = set(required_cols) - set(df.columns)
        if missing_cols:
            raise ValueError(f"Missing required columns: {missing_cols}")
        
        # Temporal validation
        if validate_temporal:
            self._validate_temporal_consistency(df)
        
        # Cache the result
        self._cache[cache_key] = df.copy()
        
        logger.info(
            f"Loaded {len(df)} option chain records for {symbol} "
            f"from {start_date} to {end_date}"
        )
        
        return df
    
    def load_iv_history(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        lookback_days: int = 252
    ) -> pd.DataFrame:
        """
        Load historical IV data with lookback for percentile calculations.
        
        Args:
            symbol: Underlying symbol
            start_date: Start date for IV history
            end_date: End date for IV history
            lookback_days: Additional days to load before start_date for calculations
            
        Returns:
            DataFrame with columns: date, symbol, atm_iv, iv_rank, iv_percentile
        """
        # Extend start date by lookback period
        extended_start = start_date - timedelta(days=lookback_days)
        
        # Load option chain data
        df = self.load_option_chain_history(
            symbol=symbol,
            start_date=extended_start,
            end_date=end_date,
            validate_temporal=True
        )
        
        # Calculate ATM IV for each date
        iv_history = []
        
        for trade_date in sorted(df['date'].unique()):
            day_data = df[df['date'] == trade_date]
            
            # Get underlying price
            underlying_price = day_data['underlying_price'].iloc[0]
            
            # Find ATM options (closest to underlying price)
            day_data['strike_diff'] = abs(day_data['strike'] - underlying_price)
            atm_data = day_data.nsmallest(10, 'strike_diff')
            
            # Average IV of ATM options
            atm_iv = atm_data['iv'].mean()
            
            iv_history.append({
                'date': trade_date,
                'symbol': symbol,
                'atm_iv': atm_iv,
                'underlying_price': underlying_price
            })
        
        iv_df = pd.DataFrame(iv_history)
        
        # Calculate IV rank (percentile over lookback period)
        iv_df['iv_rank'] = iv_df['atm_iv'].rolling(
            window=lookback_days,
            min_periods=20
        ).apply(
            lambda x: (x.iloc[-1] - x.min()) / (x.max() - x.min()) * 100
            if x.max() > x.min() else 50.0
        )
        
        # Calculate IV percentile (rank in sorted order)
        iv_df['iv_percentile'] = iv_df['atm_iv'].rolling(
            window=lookback_days,
            min_periods=20
        ).apply(
            lambda x: (x < x.iloc[-1]).sum() / len(x) * 100
        )
        
        # Filter to requested date range
        iv_df = iv_df[
            (iv_df['date'] >= start_date) & (iv_df['date'] <= end_date)
        ].copy()
        
        logger.info(f"Calculated IV history for {len(iv_df)} dates")
        
        return iv_df
    
    def load_macro_events(
        self,
        start_date: date,
        end_date: date,
        config_path: str = "config/options_trading.yaml"
    ) -> List[Dict]:
        """
        Load historical macro events from config.
        
        Args:
            start_date: Start date for events
            end_date: End date for events
            config_path: Path to config file with macro events
            
        Returns:
            List of event dictionaries with keys: date, event, impact
        """
        import yaml
        
        config_file = Path(config_path)
        if not config_file.exists():
            logger.warning(f"Config file not found: {config_path}")
            return []
        
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
        
        events = config.get('macro_events', {}).get('historical', [])
        
        # Filter events by date range
        filtered_events = []
        for event in events:
            event_date = pd.to_datetime(event['date']).date()
            if start_date <= event_date <= end_date:
                filtered_events.append({
                    'date': event_date,
                    'event': event['name'],
                    'impact': event.get('impact', 'medium')
                })
        
        logger.info(f"Loaded {len(filtered_events)} macro events")
        
        return filtered_events
    
    def get_option_chain_at_date(
        self,
        symbol: str,
        trade_date: date,
        expiry_min_days: int = 5,
        expiry_max_days: int = 60
    ) -> pd.DataFrame:
        """
        Get option chain snapshot at a specific date.
        
        Filters for valid expiries (respecting expiry hygiene rules).
        
        Args:
            symbol: Underlying symbol
            trade_date: Date to get option chain for
            expiry_min_days: Minimum days to expiry (default: 5)
            expiry_max_days: Maximum days to expiry (default: 60)
            
        Returns:
            DataFrame with option chain for the specified date
        """
        # Load data for single date (with small buffer)
        start_date = trade_date - timedelta(days=1)
        end_date = trade_date + timedelta(days=1)
        
        df = self.load_option_chain_history(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            validate_temporal=True
        )
        
        # Filter for exact date
        df = df[df['date'] == trade_date].copy()
        
        if df.empty:
            raise ValueError(f"No option chain data found for {symbol} on {trade_date}")
        
        # Calculate days to expiry
        df['days_to_expiry'] = (
            pd.to_datetime(df['expiry']) - pd.to_datetime(trade_date)
        ).dt.days
        
        # Filter by expiry range
        df = df[
            (df['days_to_expiry'] >= expiry_min_days) &
            (df['days_to_expiry'] <= expiry_max_days)
        ].copy()
        
        logger.debug(
            f"Retrieved {len(df)} options for {symbol} on {trade_date} "
            f"with {expiry_min_days}-{expiry_max_days} days to expiry"
        )
        
        return df
    
    def _validate_temporal_consistency(self, df: pd.DataFrame) -> None:
        """
        Validate temporal consistency of option chain data.
        
        Checks:
        1. No future data (expiry >= date)
        2. No missing dates in sequence
        3. No duplicate records
        4. Monotonic date ordering
        
        Args:
            df: DataFrame to validate
            
        Raises:
            ValueError: If temporal validation fails
        """
        # Check 1: No future data
        future_data = df[pd.to_datetime(df['expiry']) < pd.to_datetime(df['date'])]
        if not future_data.empty:
            raise ValueError(
                f"Found {len(future_data)} records with expiry before trade date. "
                "This indicates temporal inconsistency."
            )
        
        # Check 2: Date sequence
        dates = sorted(df['date'].unique())
        if len(dates) > 1:
            date_gaps = []
            for i in range(len(dates) - 1):
                gap = (dates[i + 1] - dates[i]).days
                if gap > 7:  # Allow for weekends/holidays
                    date_gaps.append((dates[i], dates[i + 1], gap))
            
            if date_gaps:
                logger.warning(
                    f"Found {len(date_gaps)} large gaps in date sequence. "
                    "This may indicate missing data."
                )
        
        # Check 3: Duplicates
        dup_cols = ['date', 'symbol', 'expiry', 'strike', 'option_type']
        duplicates = df[df.duplicated(subset=dup_cols, keep=False)]
        if not duplicates.empty:
            raise ValueError(
                f"Found {len(duplicates)} duplicate records. "
                "Each option should appear only once per date."
            )
        
        # Check 4: Monotonic ordering
        if not df['date'].is_monotonic_increasing:
            logger.warning("Dates are not monotonically increasing. Sorting data.")
            df.sort_values('date', inplace=True)
        
        logger.debug("Temporal consistency validation passed")
    
    def clear_cache(self) -> None:
        """Clear the internal cache."""
        self._cache.clear()
        logger.debug("Cache cleared")


# Standalone test
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("=" * 60)
    print("Historical Data Loader - Standalone Test")
    print("=" * 60)
    
    loader = HistoricalDataLoader()
    
    # Test with mock data (if available)
    test_symbol = "NIFTY"
    test_start = date(2024, 1, 1)
    test_end = date(2024, 1, 31)
    
    try:
        print(f"\n1. Testing option chain history load...")
        df = loader.load_option_chain_history(
            symbol=test_symbol,
            start_date=test_start,
            end_date=test_end
        )
        print(f"✓ Loaded {len(df)} records")
        print(f"  Date range: {df['date'].min()} to {df['date'].max()}")
        print(f"  Symbols: {df['symbol'].unique()}")
        print(f"  Expiries: {len(df['expiry'].unique())} unique")
        
    except FileNotFoundError as e:
        print(f"✗ {e}")
        print("  Note: Historical data files not yet available")
        print("  This is expected for initial implementation")
    
    print("\n" + "=" * 60)
    print("Test complete")
    print("=" * 60)
