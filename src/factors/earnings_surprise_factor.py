"""Seasonal-random-walk earnings surprise factor."""

from __future__ import annotations

from datetime import datetime
import logging
import re

import numpy as np
import pandas as pd

from .base_factor import BaseFactor

logger = logging.getLogger(__name__)

_QUARTER_RE = re.compile(r"Q([1-4])[- ](\d{4})", re.IGNORECASE)


class EarningsSurpriseFactor(BaseFactor):
    """Standardized unexpected earnings based on PIT-safe announcement history."""

    FACTOR_NAME = "earnings_surprise"
    FACTOR_FAMILY = "QUALITY"

    def _compute_raw(self, as_of_date: datetime, tickers: list) -> pd.Series:
        min_history = int(self._factor_config.get('min_quarters_history', 6) or 6)
        safety_lag_days = int(self._factor_config.get('announcement_safety_lag_days', 2) or 2)

        history = self._registry.fundamentals.get_earnings_history(
            as_of_date=as_of_date,
            tickers=tickers,
            n_quarters=max(12, min_history + 4),
            safety_lag_days=safety_lag_days,
            date_field='announcement_date',
        )

        out = {}
        for ticker in tickers:
            records = history.get(ticker, [])
            if len(records) < min_history:
                out[ticker] = np.nan
                continue
            try:
                out[ticker] = self._compute_sue(records, min_history=min_history)
            except Exception as exc:
                logger.debug("Earnings surprise failed for %s: %s", ticker, exc)
                out[ticker] = np.nan
        return pd.Series(out, index=tickers)

    @staticmethod
    def _quarter_key(record: dict):
        quarter = str(record.get('quarter') or '').strip()
        match = _QUARTER_RE.match(quarter)
        if match:
            return int(match.group(2)), int(match.group(1))
        period_end = pd.to_datetime(record.get('period_end'), errors='coerce')
        if pd.isna(period_end):
            return None
        quarter_num = ((int(period_end.month) - 1) // 3) + 1
        return int(period_end.year), quarter_num

    def _compute_sue(self, history: list[dict], min_history: int = 6) -> float:
        series = pd.DataFrame(history).copy()
        if series.empty:
            return np.nan

        series['announcement_date'] = pd.to_datetime(series.get('announcement_date'), errors='coerce')
        series['period_end'] = pd.to_datetime(series.get('period_end'), errors='coerce')
        series['eps_actual'] = pd.to_numeric(series.get('eps_actual'), errors='coerce')
        series = series.dropna(subset=['announcement_date', 'eps_actual']).sort_values(
            ['announcement_date', 'period_end'],
            kind='mergesort',
        )
        if len(series) < max(min_history, 5):
            return np.nan

        records = series.to_dict(orient='records')
        prior_eps: dict[tuple[int, int], float] = {}
        surprises: list[float] = []
        yoy_growths: list[float] = []

        for rec in records:
            key = self._quarter_key(rec)
            if key is None:
                continue
            prev_key = (key[0] - 1, key[1])
            prev_eps = prior_eps.get(prev_key)
            eps = float(rec['eps_actual'])
            if prev_eps is not None and np.isfinite(prev_eps) and abs(prev_eps) > 1e-9:
                avg_yoy = float(np.mean(yoy_growths[-8:])) if yoy_growths else 0.0
                forecast = float(prev_eps) * (1.0 + avg_yoy)
                surprises.append(eps - forecast)
                yoy_growths.append((eps - float(prev_eps)) / abs(float(prev_eps)))
            prior_eps[key] = eps

        if len(surprises) < 2:
            return np.nan

        latest_surprise = float(surprises[-1])
        history_std = float(np.std(surprises[:-1] if len(surprises) > 2 else surprises))
        if history_std <= 1e-9:
            return np.nan
        return latest_surprise / history_std
