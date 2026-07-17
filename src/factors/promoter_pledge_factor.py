"""Promoter pledge change factor."""

from __future__ import annotations

from datetime import datetime
import logging

import numpy as np
import pandas as pd

from src.core.panel_math import coalesce_rowwise
from .base_factor import BaseFactor

logger = logging.getLogger(__name__)


class PromoterPledgeFactor(BaseFactor):
    """Signal = negative quarterly change in promoter pledge percentage."""

    FACTOR_NAME = "promoter_pledge"
    FACTOR_FAMILY = "GOVERNANCE"

    def _compute_raw(self, as_of_date: datetime, tickers: list) -> pd.Series:
        safety_lag_days = int(self._factor_config.get('safety_lag_days', 25) or 25)
        history = self._registry.alternative.get_promoter_pledge_history(
            as_of_date=as_of_date,
            tickers=tickers,
            safety_lag_days=safety_lag_days,
        )

        out = {}
        for ticker in tickers:
            rows = history.get(ticker)
            if rows is None or rows.empty:
                out[ticker] = np.nan
                continue
            try:
                work = rows.copy()
                work['pledge_pct'] = pd.to_numeric(work.get('pledge_pct'), errors='coerce')
                # N10: per-row fallback where pledge_pct is missing but shares exist.
                if {'shares_pledged', 'total_promoter_shares'}.issubset(set(work.columns)):
                    pledged = pd.to_numeric(work.get('shares_pledged'), errors='coerce')
                    total = pd.to_numeric(work.get('total_promoter_shares'), errors='coerce').replace(0.0, np.nan)
                    work['pledge_pct'] = coalesce_rowwise(work['pledge_pct'], 100.0 * pledged / total)
                work = work.dropna(subset=['pledge_pct']).sort_values(['availability_date', 'quarter_end'], kind='mergesort')
                if len(work) < 2:
                    out[ticker] = np.nan
                    continue
                curr = float(work.iloc[-1]['pledge_pct'])
                prior = float(work.iloc[-2]['pledge_pct'])
                out[ticker] = -(curr - prior)
            except Exception as exc:
                logger.debug("Promoter pledge failed for %s: %s", ticker, exc)
                out[ticker] = np.nan
        return pd.Series(out, index=tickers)
