"""
BAB Factor — Betting Against Beta (Frazzini & Pedersen, 2014)

Cross-sectional factor: rank stocks by their market beta. The BAB signal
is the negative of beta — low-beta stocks receive high (positive) scores
and are expected to outperform. High-beta stocks receive low (negative) scores.

Data required:
- Daily returns: from market_loader via IngestionRegistry
- NIFTY 500 index daily returns: used as the market proxy
- Lookback: 1 year of daily returns (252 trading days)
- Minimum observations: 120 days

Beta estimation (Frazzini-Pedersen two-step):
    Beta_i = rho(r_i, r_m) × (sigma_i / sigma_m)
Where:
    rho = 1-year rolling correlation
    sigma_i = 1-month rolling annualized volatility of stock i
    sigma_m = 1-month rolling annualized volatility of NIFTY 500

PIT safety: Beta is estimated using only returns up to as_of_date.
Output: BAB_raw = -beta (so low beta → high score)
"""

from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import logging

from .base_factor import BaseFactor

logger = logging.getLogger(__name__)


class BABFactor(BaseFactor):
    """Betting Against Beta factor implementation."""
    
    FACTOR_NAME = "bab"
    FACTOR_FAMILY = "RISK"
    LOOKAHEAD_SAFE = True
    
    def _compute_raw(self, as_of_date: datetime, tickers: list) -> pd.Series:
        """
        Returns -beta for each ticker (negative beta = BAB signal direction).
        """
        lookback_days = self._factor_config.get('lookback_days', 252)
        min_observations = self._factor_config.get('min_observations', 120)
        vol_lookback_days = self._factor_config.get('vol_lookback_days', 21)
        
        start_date = as_of_date - timedelta(days=lookback_days + 30)  # buffer
        
        # Load price data via IngestionRegistry (PIT-safe)
        try:
            prices = self._registry.market.load(
                as_of_date=as_of_date,
                tickers=tickers,
                start_date=start_date,
                fields=['close', 'adj_close']
            )
        except Exception as e:
            logger.warning(f"Failed to load price data for BAB: {e}")
            return pd.Series(np.nan, index=tickers)
        
        # Load market index returns (NIFTY 500)
        try:
            market_prices = self._registry.market.load_index(
                as_of_date=as_of_date,
                index='NIFTY500',
                start_date=start_date,
                fields=['close']
            )
        except Exception as e:
            logger.warning(f"Failed to load market index for BAB: {e}")
            return pd.Series(np.nan, index=tickers)
        
        # Compute log returns
        if prices.empty or market_prices.empty:
            return pd.Series(np.nan, index=tickers)
        
        # Pivot prices to wide format
        if 'Ticker' in prices.index.names:
            prices_wide = prices['adj_close'].unstack('Ticker')
        else:
            prices_wide = prices
        
        if 'Ticker' in market_prices.index.names:
            market_wide = market_prices['close'].unstack('Ticker')
        else:
            market_wide = market_prices
        
        # Compute log returns
        stock_returns = np.log(prices_wide).diff()
        
        # Get market returns (should be single column)
        if isinstance(market_wide, pd.DataFrame):
            if len(market_wide.columns) > 0:
                market_returns = np.log(market_wide.iloc[:, 0]).diff()
            else:
                return pd.Series(np.nan, index=tickers)
        else:
            market_returns = np.log(market_wide).diff()
        
        # Align on common dates
        common_dates = stock_returns.index.intersection(market_returns.index)
        stock_returns = stock_returns.loc[common_dates]
        market_returns = market_returns.loc[common_dates]
        
        # Keep only last lookback_days observations up to as_of_date
        stock_returns = stock_returns[stock_returns.index <= pd.Timestamp(as_of_date)].iloc[-lookback_days:]
        market_returns = market_returns[market_returns.index <= pd.Timestamp(as_of_date)].iloc[-lookback_days:]
        
        results = {}
        for ticker in tickers:
            if ticker not in stock_returns.columns:
                results[ticker] = np.nan
                continue
            
            r_i = stock_returns[ticker].dropna()
            r_m = market_returns.reindex(r_i.index).dropna()
            
            # Realign after dropping NaN
            common = r_i.index.intersection(r_m.index)
            r_i = r_i.loc[common]
            r_m = r_m.loc[common]
            
            if len(r_i) < min_observations:
                results[ticker] = np.nan
                continue
            
            # Two-step Frazzini-Pedersen beta estimator
            # Step 1: correlation over full window
            rho = r_i.corr(r_m)
            
            # Step 2: volatilities over shorter window (last vol_lookback_days)
            sigma_i = r_i.iloc[-vol_lookback_days:].std() * np.sqrt(252)
            sigma_m = r_m.iloc[-vol_lookback_days:].std() * np.sqrt(252)
            
            if sigma_m < 1e-9 or pd.isna(sigma_m):
                results[ticker] = np.nan
                continue
            
            beta = rho * (sigma_i / sigma_m)
            results[ticker] = -beta  # BAB signal: low beta = high score
        
        return pd.Series(results)
