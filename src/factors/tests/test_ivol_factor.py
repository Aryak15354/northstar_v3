from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd

from src.factors.ivol_factor import IVOLFactor
from src.factors.tests.conftest import DummyMarketLoader, DummyRegistry, make_price_panel


def _registry():
    dates = pd.bdate_range("2024-01-01", periods=140)
    market_ret = pd.Series(np.linspace(-0.01, 0.012, len(dates)), index=dates)
    market_close = 100 * np.exp(market_ret.cumsum())

    close_map = {}
    for i in range(10):
        noise = 0.0005 * np.sin(np.arange(len(dates)) + i)
        ret = 1.0 * market_ret + noise
        close_map[f"FILLER{i}.NS"] = 100 * np.exp(ret.cumsum())

    low_noise = 0.0003 * np.sin(np.arange(len(dates)))
    high_noise = 0.01 * np.sin(np.arange(len(dates)) * 1.7)
    close_map["LOWIVOL.NS"] = 100 * np.exp((1.0 * market_ret + low_noise).cumsum())
    close_map["HIGHIVOL.NS"] = 100 * np.exp((1.0 * market_ret + high_noise).cumsum())

    return DummyRegistry(
        market=DummyMarketLoader(
            prices=make_price_panel(close_map),
            index_df=pd.DataFrame({"close": market_close}, index=dates),
        )
    )


def test_ivol_low_residual_vol_scores_better():
    factor = IVOLFactor(_registry(), {"factors": {"ivol": {"lookback_days": 126, "min_observations": 80}}})
    tickers = [f"FILLER{i}.NS" for i in range(10)] + ["LOWIVOL.NS", "HIGHIVOL.NS"]
    out = factor.compute(datetime(2024, 7, 15), tickers, use_cache=False)
    assert out.loc["LOWIVOL.NS", "ivol_zscore"] > out.loc["HIGHIVOL.NS", "ivol_zscore"]
