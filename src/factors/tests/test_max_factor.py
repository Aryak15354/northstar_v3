from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd

from src.factors.max_factor import MAXFactor
from src.factors.tests.conftest import DummyMarketLoader, DummyRegistry, make_price_panel


def _registry():
    dates = pd.bdate_range("2024-05-01", periods=30)
    close_map = {}
    for i in range(10):
        close_map[f"FILLER{i}.NS"] = pd.Series(100 + np.linspace(0, 2 + i * 0.1, len(dates)), index=dates)
    spike_returns = pd.Series([0.0] * len(dates), index=dates)
    spike_returns.iloc[-10] = 0.15
    low_returns = pd.Series([0.001] * len(dates), index=dates)
    close_map["SPIKE.NS"] = 100 * (1 + spike_returns).cumprod()
    close_map["CALM.NS"] = 100 * (1 + low_returns).cumprod()
    return DummyRegistry(market=DummyMarketLoader(prices=make_price_panel(close_map)))


def test_max_signal_direction():
    factor = MAXFactor(_registry(), {"factors": {"max": {"lookback_days": 21, "top_n_days": 5, "min_observations": 15}}})
    tickers = [f"FILLER{i}.NS" for i in range(10)] + ["SPIKE.NS", "CALM.NS"]
    out = factor.compute(datetime(2024, 6, 12), tickers, use_cache=False)
    assert out.loc["SPIKE.NS", "max_zscore"] < out.loc["CALM.NS", "max_zscore"]


def test_max_avoids_same_day_data():
    factor = MAXFactor(_registry(), {"factors": {"max": {"lookback_days": 21, "top_n_days": 5, "min_observations": 15}}})
    tickers = [f"FILLER{i}.NS" for i in range(10)] + ["SPIKE.NS", "CALM.NS"]
    out = factor.compute(datetime(2024, 6, 12), tickers, use_cache=False)
    assert pd.notna(out.loc["SPIKE.NS", "max_raw"])
