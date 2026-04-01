from __future__ import annotations

from datetime import datetime

from src.factors.earnings_surprise_factor import EarningsSurpriseFactor
from src.factors.tests.conftest import DummyFundamentalLoader, DummyRegistry


def _history(base_eps: float, latest_eps: float) -> list[dict]:
    quarters = [
        ("Q3-2022", "2022-09-30", "2022-11-16", base_eps - 1.0),
        ("Q4-2022", "2022-12-31", "2023-02-16", base_eps),
        ("Q1-2023", "2023-03-31", "2023-05-16", base_eps + 0.2),
        ("Q2-2023", "2023-06-30", "2023-08-16", base_eps + 0.1),
        ("Q3-2023", "2023-09-30", "2023-11-16", base_eps + 0.3),
        ("Q4-2023", "2023-12-31", "2024-02-16", base_eps + 0.4),
        ("Q1-2024", "2024-03-31", "2024-05-16", latest_eps),
    ]
    return [
        {
            "ticker": "TEST",
            "quarter": q,
            "period_end": pe,
            "announcement_date": ad,
            "eps_actual": eps,
        }
        for q, pe, ad, eps in quarters
    ]


def test_earnings_surprise_orders_positive_and_negative_surprises():
    earnings_history = {}
    for i in range(10):
        earnings_history[f"FILLER{i}.NS"] = _history(10.0 + 0.2 * i, 10.4 + 0.2 * i)
    earnings_history["BEAT.NS"] = _history(12.0, 15.0)
    earnings_history["MISS.NS"] = _history(12.0, 9.5)

    factor = EarningsSurpriseFactor(
        DummyRegistry(fundamentals=DummyFundamentalLoader(earnings_history=earnings_history)),
        {"factors": {"earnings_surprise": {"announcement_safety_lag_days": 2, "min_quarters_history": 6}}},
    )
    tickers = list(earnings_history.keys())
    out = factor.compute(datetime(2024, 6, 30), tickers, use_cache=False)
    assert out.loc["BEAT.NS", "earnings_surprise_zscore"] > out.loc["MISS.NS", "earnings_surprise_zscore"]
