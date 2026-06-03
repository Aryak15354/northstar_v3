from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd

from src.factors.bab_factor import BABFactor
from src.factors.tests.conftest import DummyMarketLoader, DummyRegistry, make_price_panel


def _build_bab_registry():
    dates = pd.bdate_range("2024-01-01", periods=140)
    market_ret = pd.Series(np.linspace(-0.01, 0.012, len(dates)), index=dates)
    market_close = 100 * np.exp(market_ret.cumsum())

    close_map = {}
    for i in range(10):
        beta = 0.8 + i * 0.05
        ret = beta * market_ret + 0.0001 * np.sin(np.arange(len(dates)))
        close_map[f"FILLER{i}.NS"] = 100 * np.exp(ret.cumsum())

    low_ret = 0.35 * market_ret
    high_ret = 1.8 * market_ret
    close_map["LOW.NS"] = 100 * np.exp(low_ret.cumsum())
    close_map["HIGH.NS"] = 100 * np.exp(high_ret.cumsum())
    close_map["SHORT.NS"] = pd.Series(100 * np.exp((0.9 * market_ret.iloc[:60]).cumsum()), index=dates[:60])

    prices = make_price_panel(close_map)
    index_df = pd.DataFrame({"close": market_close}, index=dates)
    return DummyRegistry(market=DummyMarketLoader(prices=prices, index_df=index_df))


def test_bab_low_beta_positive_score():
    factor = BABFactor(_build_bab_registry(), {"factors": {"bab": {"lookback_days": 126, "min_observations": 80, "vol_lookback_days": 21}}})
    tickers = [f"FILLER{i}.NS" for i in range(10)] + ["LOW.NS", "HIGH.NS"]
    out = factor.compute(datetime(2024, 7, 15), tickers, use_cache=False)
    assert out.loc["LOW.NS", "bab_zscore"] > 0


def test_bab_high_beta_negative_score():
    factor = BABFactor(_build_bab_registry(), {"factors": {"bab": {"lookback_days": 126, "min_observations": 80, "vol_lookback_days": 21}}})
    tickers = [f"FILLER{i}.NS" for i in range(10)] + ["LOW.NS", "HIGH.NS"]
    out = factor.compute(datetime(2024, 7, 15), tickers, use_cache=False)
    assert out.loc["HIGH.NS", "bab_zscore"] < 0


def test_bab_insufficient_data_returns_nan():
    factor = BABFactor(_build_bab_registry(), {"factors": {"bab": {"lookback_days": 126, "min_observations": 80, "vol_lookback_days": 21}}})
    out = factor.compute(datetime(2024, 7, 15), ["SHORT.NS"] + [f"FILLER{i}.NS" for i in range(10)], use_cache=False)
    assert pd.isna(out.loc["SHORT.NS", "bab_raw"])


def test_bab_full_universe_coverage():
    registry = _build_bab_registry()
    factor = BABFactor(registry, {"factors": {"bab": {"lookback_days": 126, "min_observations": 80, "vol_lookback_days": 21}}})
    tickers = [f"FILLER{i}.NS" for i in range(10)] + ["LOW.NS", "HIGH.NS", "MISSING.NS"]
    out = factor.compute(datetime(2024, 7, 15), tickers, use_cache=False)
    assert len(out) == len(tickers)
    assert pd.isna(out.loc["MISSING.NS", "bab_zscore"])
