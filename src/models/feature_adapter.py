"""Adapt canonical factor-store panels into model-ready datasets."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd

from src.ingestion import IngestionRegistry


class FeatureAdapter:
    def __init__(self, factor_store, config: dict, registry: Optional[IngestionRegistry] = None):
        self._store = factor_store
        self._config = dict(config or {})
        self._registry = registry or IngestionRegistry(self._config)

    def build_tabular_dataset(
        self,
        start_date: datetime,
        end_date: datetime,
        tickers: list[str],
        target_horizon_days: int = 5,
        feature_names: Optional[list[str]] = None,
    ) -> tuple[pd.DataFrame, pd.Series]:
        features = self._store.load_factor_features(start_date, end_date, tickers, factor_names=feature_names)
        if features.empty:
            return pd.DataFrame(), pd.Series(dtype=float)

        factor_cols = [c for c in features.columns if c.endswith("_zscore")]
        if feature_names:
            factor_cols = [c for c in factor_cols if c in feature_names]
        returns = self._load_forward_returns(tickers, start_date, end_date, target_horizon_days)
        if returns.empty:
            return pd.DataFrame(), pd.Series(dtype=float)

        X = features[factor_cols].copy()
        y = returns.reindex(X.index)
        valid = y.notna()
        return X.loc[valid], y.loc[valid]

    def _load_forward_returns(
        self,
        tickers: list[str],
        start_date: datetime,
        end_date: datetime,
        horizon_days: int,
    ) -> pd.Series:
        prices = self._registry.market.load(
            as_of_date=end_date + timedelta(days=int(max(5, horizon_days))),
            tickers=tickers,
            start_date=start_date - timedelta(days=5),
            fields=["close"],
        )
        if prices.empty:
            return pd.Series(dtype=float)
        frame = prices.reset_index()
        frame["Date"] = pd.to_datetime(frame["Date"], errors="coerce")
        frame = frame.sort_values(["Ticker", "Date"], kind="mergesort")
        frame["forward_return"] = frame.groupby("Ticker")["close"].shift(-horizon_days) / frame["close"] - 1.0
        frame = frame.set_index(["Date", "Ticker"])["forward_return"]
        frame.index = frame.index.set_names(["date", "ticker"])
        return frame
