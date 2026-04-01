from __future__ import annotations

from datetime import datetime

import pandas as pd

from src.factors.promoter_pledge_factor import PromoterPledgeFactor
from src.factors.tests.conftest import DummyAlternativeLoader, DummyRegistry


def _pledge_history(curr: float, prior: float) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"ticker": "TEST", "quarter_end": "2023-12-31", "availability_date": "2024-02-14", "pledge_pct": prior},
            {"ticker": "TEST", "quarter_end": "2024-03-31", "availability_date": "2024-05-15", "pledge_pct": curr},
        ]
    )


def test_promoter_pledge_signal_direction():
    pledge_history = {}
    for i in range(10):
        pledge_history[f"FILLER{i}.NS"] = _pledge_history(10.0 + i * 0.1, 10.2 + i * 0.1)
    pledge_history["DECREASING.NS"] = _pledge_history(8.0, 14.0)
    pledge_history["INCREASING.NS"] = _pledge_history(18.0, 11.0)

    factor = PromoterPledgeFactor(
        DummyRegistry(alternative=DummyAlternativeLoader(pledge_history=pledge_history)),
        {"factors": {"promoter_pledge": {"safety_lag_days": 25}}},
    )
    tickers = list(pledge_history.keys())
    out = factor.compute(datetime(2024, 6, 30), tickers, use_cache=False)
    assert out.loc["DECREASING.NS", "promoter_pledge_zscore"] > out.loc["INCREASING.NS", "promoter_pledge_zscore"]
