"""
Amihud Illiquidity Factor (Amihud, 2002)

The Amihud illiquidity measure for stock i in month m:
    ILLIQ_i = (1/D_im) × sum_{t=1}^{D_im} (|r_it| / VOLD_it)

Where:
    D_im = number of valid trading days in month m
    r_it = daily return for stock i on day t
    VOLD_it = daily rupee trading volume (price × shares)

The ILLIQ measure captures price impact: how much the price moves
per unit of rupee volume traded. Higher ILLIQ = less liquid.

Lookback: 1 calendar month (last 21 trading days)
Normalization: Log-transform before z-scoring (ILLIQ is right-skewed)
    ILLIQ_log = log(1 + ILLIQ × 10^6)

Output: AMIHUD_raw = log(1 + ILLIQ × 10^6)
Signal direction: HIGH Amihud = HIGH expected return (liquidity premium)
"""

from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import logging

from .base_factor import BaseFactor

logger = logging.getLogger(__name__)


class AmihudFactor(BaseFactor):
    """Amihud illiquidity factor implementation."""
    
    FACTOR_NAME = "amihud"
    FACTOR_FAMILY = "LIQUIDITY"
    LOOKAHEAD_SAFE = True
    
    def _compute_raw(self, as_of_date: datetime, tickers: list) -> pd.Series:
        """
        Returns log-transformed Amihud illiquidity for each ticker.
        """
        lookback_days = self._factor_config.get('lookback_days', 21)
        min_observations = self._factor_config.get('min_observations', 10)
        scaling = self._factor_config.get('scaling', 1_000_000)
        
        start_date = as_of_date - timedelta(days=lookback_days + 10)
        
        # Load price and volume data
        try:
            prices = self._registry.market.load(
                as_of_date=as_of_date,
                tickers=tickers,
                start_date=start_date,
                fields=['close', 'adj_close', 'volume']
            )
        except Exception as e:
            logger.warning(f"Failed to load price/volume data for Amihud: {e}")
            return pd.Series(np.nan, index=tickers)
        
        if prices.empty:
            return pd.Series(np.nan, index=tickers)
        
        # Pivot to wide format
        if 'Ticker' in prices.index.names:
            close_wide = prices['close'].unstack('Ticker')
            volume_wide = prices['volume'].unstack('Ticker')
        else:
            close_wide = prices.get('close', prices)
            volume_wide = prices.get('volume', pd.DataFrame())
        
        results = {}
        for ticker in tickers:
            if ticker not in close_wide.columns or ticker not in volume_wide.columns:
                results[ticker] = np.nan
                continue
            
            close = close_wide[ticker].dropna()
            volume = volume_wide[ticker].dropna()
            
            # Align and filter to as_of_date window
            common = close.index.intersection(volume.index)
            close = close.loc[common]
            close = close[close.index <= pd.Timestamp(as_of_date)].iloc[-lookback_days:]
            volume = volume.loc[close.index]
            
            if len(close) < min_observations:
                results[ticker] = np.nan
                continue
            
            # Daily log returns
            daily_returns = np.log(close).diff().dropna()
            volume = volume.reindex(daily_returns.index)
            
            # Rupee volume (price × shares)
            rupee_volume = close.reindex(daily_returns.index) * volume
            
            # Mask zero-volume days
            valid = rupee_volume > 0
            daily_returns = daily_returns[valid]
            rupee_volume = rupee_volume[valid]
            
            if len(daily_returns) < min_observations:
                results[ticker] = np.nan
                continue
            
            # Amihud ratio: |return| / rupee volume
            illiq = (daily_returns.abs() / rupee_volume).mean()
            
            # Log transform with scaling
            illiq_log = np.log(1 + illiq * scaling)
            results[ticker] = illiq_log
        
        return pd.Series(results)
