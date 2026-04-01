"""
MAX Lottery Factor (Bali, Cakici, Whitelaw, 2011)

For stock i in month m:
    MAX5_i = mean of top 5 daily returns in prior month

The MAX factor captures the lottery premium: investors irrationally
overpay for stocks with high positive skewness (the chance of a 
big single-day gain), depressing their future expected return.

Signal direction is NEGATIVE:
    HIGH MAX (big prior-month spike) → NEGATIVE expected return
    LOW MAX (no big prior-month spike) → POSITIVE expected return

So the factor score: MAX_raw = -MAX5

Lookback: 21 trading days (1 calendar month) ending on as_of_date - 1
"""

from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import logging

from .base_factor import BaseFactor

logger = logging.getLogger(__name__)


class MAXFactor(BaseFactor):
    """MAX lottery factor implementation."""
    
    FACTOR_NAME = "max"
    FACTOR_FAMILY = "RISK"
    LOOKAHEAD_SAFE = True
    
    def _compute_raw(self, as_of_date: datetime, tickers: list) -> pd.Series:
        """
        Returns -MAX5 for each ticker (negative MAX = positive signal).
        """
        lookback_days = self._factor_config.get('lookback_days', 21)
        top_n = self._factor_config.get('top_n_days', 5)
        min_observations = self._factor_config.get('min_observations', 15)
        
        # Use as_of_date - 1 day to avoid same-day data
        effective_date = as_of_date - timedelta(days=1)
        start_date = effective_date - timedelta(days=lookback_days + 10)
        
        # Load price data
        try:
            prices = self._registry.market.load(
                as_of_date=effective_date,
                tickers=tickers,
                start_date=start_date,
                fields=['adj_close']
            )
        except Exception as e:
            logger.warning(f"Failed to load price data for MAX: {e}")
            return pd.Series(np.nan, index=tickers)
        
        if prices.empty:
            return pd.Series(np.nan, index=tickers)
        
        # Pivot to wide format
        if 'Ticker' in prices.index.names:
            close_wide = prices['adj_close'].unstack('Ticker')
        else:
            close_wide = prices.get('adj_close', prices)
        
        results = {}
        for ticker in tickers:
            if ticker not in close_wide.columns:
                results[ticker] = np.nan
                continue
            
            close = close_wide[ticker].dropna()
            close = close[close.index <= pd.Timestamp(effective_date)].iloc[-lookback_days:]
            
            if len(close) < min_observations:
                results[ticker] = np.nan
                continue
            
            # Daily returns
            daily_returns = close.pct_change().dropna()
            
            if len(daily_returns) < top_n:
                results[ticker] = np.nan
                continue
            
            # MAX5: average of top 5 daily returns
            top5_mean = daily_returns.nlargest(top_n).mean()
            
            # Signal direction: NEGATIVE MAX (high lottery = expected underperformer)
            results[ticker] = -top5_mean
        
        return pd.Series(results)
