"""Operating profitability factor."""

from __future__ import annotations

from datetime import datetime
import logging

import numpy as np
import pandas as pd

from .base_factor import BaseFactor

logger = logging.getLogger(__name__)


class OperatingProfitabilityFactor(BaseFactor):
    """Standalone operating profitability signal built from PIT-safe annual fundamentals."""

    FACTOR_NAME = "operating_profitability"
    FACTOR_FAMILY = "QUALITY"

    def _compute_raw(self, as_of_date: datetime, tickers: list) -> pd.Series:
        fundamentals = self._registry.fundamentals.get_factor_financials(
            as_of_date=as_of_date,
            tickers=tickers,
            frequency='annual',
            periods=2,
            reporting_lag_days=self._factor_config.get('reporting_lag_days'),
        )

        out = {}
        for ticker in tickers:
            fin = fundamentals.get(ticker, {})
            current = fin.get('current', {})
            prior = fin.get('prior', {})
            if not current:
                out[ticker] = np.nan
                continue
            try:
                out[ticker] = self._score(current, prior)
            except Exception as exc:
                logger.debug("Operating profitability failed for %s: %s", ticker, exc)
                out[ticker] = np.nan
        return pd.Series(out, index=tickers)

    @staticmethod
    def _pick(data: dict, *names: str):
        for name in names:
            if name in data and data[name] is not None and not pd.isna(data[name]):
                return data[name]
        lower = {str(k).lower(): v for k, v in data.items()}
        for name in names:
            value = lower.get(str(name).lower())
            if value is not None and not pd.isna(value):
                return value
        return None

    def _score(self, current: dict, prior: dict) -> float:
        op_current = self._pick(current, 'operating_income', 'ebit', 'operating_profit')
        if op_current is None:
            revenue = self._pick(current, 'revenue')
            expenses = self._pick(current, 'total_expenses', 'cost_of_goods_sold')
            if revenue is not None and expenses is not None:
                op_current = float(revenue) - float(expenses)

        assets_current = self._pick(current, 'total_assets')
        if op_current is None or assets_current in (None, 0):
            return np.nan

        roa_current = float(op_current) / float(assets_current)

        op_prior = self._pick(prior, 'operating_income', 'ebit', 'operating_profit') if prior else None
        if op_prior is None and prior:
            revenue_prior = self._pick(prior, 'revenue')
            expenses_prior = self._pick(prior, 'total_expenses', 'cost_of_goods_sold')
            if revenue_prior is not None and expenses_prior is not None:
                op_prior = float(revenue_prior) - float(expenses_prior)

        assets_prior = self._pick(prior, 'total_assets') if prior else None
        if op_prior is not None and assets_prior not in (None, 0):
            roa_prior = float(op_prior) / float(assets_prior)
            roa_trend = roa_current - roa_prior
        else:
            roa_trend = 0.0

        return 0.6 * float(roa_current) + 0.4 * float(roa_trend)
