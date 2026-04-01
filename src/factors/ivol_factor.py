"""Idiosyncratic volatility factor."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging

import numpy as np
import pandas as pd

from .base_factor import BaseFactor

logger = logging.getLogger(__name__)


class IVOLFactor(BaseFactor):
    """Low idiosyncratic volatility = positive expected-return signal."""

    FACTOR_NAME = "ivol"
    FACTOR_FAMILY = "RISK"

    def _compute_raw(self, as_of_date: datetime, tickers: list) -> pd.Series:
        lookback_days = int(self._factor_config.get('lookback_days', 252) or 252)
        min_obs = int(self._factor_config.get('min_observations', 120) or 120)
        start_date = as_of_date - timedelta(days=lookback_days + 30)

        try:
            prices = self._registry.market.load(
                as_of_date=as_of_date,
                tickers=tickers,
                start_date=start_date,
                fields=['adj_close'],
            )
            market = self._registry.market.load_index(
                as_of_date=as_of_date,
                index_name='NIFTY500',
                start_date=start_date,
                fields=['close'],
            )
        except Exception as exc:
            logger.warning("Failed loading inputs for IVOL: %s", exc)
            return pd.Series(np.nan, index=tickers)

        if prices.empty or market.empty or 'adj_close' not in prices.columns or 'close' not in market.columns:
            return pd.Series(np.nan, index=tickers)

        stock_returns = np.log(prices['adj_close']).unstack('Ticker').diff()
        market_returns = np.log(market['close']).diff()

        out = {}
        for ticker in tickers:
            if ticker not in stock_returns.columns:
                out[ticker] = np.nan
                continue
            r_i = stock_returns[ticker].dropna()
            r_m = market_returns.reindex(r_i.index).dropna()
            r_i = r_i.reindex(r_m.index)
            r_i = r_i[r_i.index <= pd.Timestamp(as_of_date)].iloc[-lookback_days:]
            r_m = r_m.reindex(r_i.index)
            if len(r_i) < min_obs:
                out[ticker] = np.nan
                continue
            X = np.column_stack([np.ones(len(r_m)), r_m.to_numpy(dtype=float)])
            y = r_i.to_numpy(dtype=float)
            try:
                beta = np.linalg.lstsq(X, y, rcond=None)[0]
                resid = y - X @ beta
                ivol = float(np.std(resid)) * np.sqrt(252.0)
                out[ticker] = -ivol
            except Exception as exc:
                logger.debug("IVOL failed for %s: %s", ticker, exc)
                out[ticker] = np.nan
        return pd.Series(out, index=tickers)
