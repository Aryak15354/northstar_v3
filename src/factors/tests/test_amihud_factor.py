from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd

from src.factors.amihud_factor import AmihudFactor
from src.factors.tests.conftest import DummyMarketLoader, DummyRegistry, make_price_panel


def _build_registry():
    dates = pd.bdate_range("2024-06-01", periods=25)
    base_close = pd.Series(100 + np.linspace(0, 3, len(dates)), index=dates)

    close_map = {}
    volume_map = {}
    for i in range(10):
        close_map[f"FILLER{i}.NS"] = base_close * (1 + 0.001 * i)
        volume_map[f"FILLER{i}.NS"] = pd.Series(5_000_000 + i * 100_000, index=dates)

    close_map["LIQUID.NS"] = base_close
    volume_map["LIQUID.NS"] = pd.Series(20_000_000, index=dates)
    close_map["ILLIQ.NS"] = base_close * (1 + pd.Series(np.linspace(-0.04, 0.05, len(dates)), index=dates))
    volume_map["ILLIQ.NS"] = pd.Series(50_000, index=dates)
    return DummyRegistry(market=DummyMarketLoader(prices=make_price_panel(close_map, volume_map)))


def test_amihud_zero_volume_days_excluded():
    dates = pd.bdate_range("2024-06-01", periods=25)
    close_map = {"TEST.NS": pd.Series(100 + np.arange(len(dates)), index=dates)}
    volume = pd.Series(1_000_000, index=dates)
    volume.iloc[:5] = 0
    volume_map = {"TEST.NS": volume}
    for i in range(10):
        close_map[f"FILLER{i}.NS"] = pd.Series(100 + np.arange(len(dates)), index=dates)
        volume_map[f"FILLER{i}.NS"] = pd.Series(1_000_000 + i, index=dates)
    factor = AmihudFactor(DummyRegistry(market=DummyMarketLoader(prices=make_price_panel(close_map, volume_map))), {"factors": {"amihud": {"lookback_days": 21, "min_observations": 10}}})
    out = factor.compute(datetime(2024, 7, 15), list(close_map.keys()), use_cache=False)
    assert pd.notna(out.loc["TEST.NS", "amihud_raw"])


def test_amihud_log_transformation_and_liquidity_ordering():
    factor = AmihudFactor(_build_registry(), {"factors": {"amihud": {"lookback_days": 21, "min_observations": 10, "scaling": 1_000_000}}})
    tickers = [f"FILLER{i}.NS" for i in range(10)] + ["LIQUID.NS", "ILLIQ.NS"]
    out = factor.compute(datetime(2024, 7, 15), tickers, use_cache=False)
    assert out.loc["ILLIQ.NS", "amihud_raw"] > out.loc["LIQUID.NS", "amihud_raw"]
    assert out.loc["ILLIQ.NS", "amihud_zscore"] > out.loc["LIQUID.NS", "amihud_zscore"]
