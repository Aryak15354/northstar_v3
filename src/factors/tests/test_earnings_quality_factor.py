from __future__ import annotations

from datetime import datetime

import pandas as pd

from src.factors.earnings_quality_factor import EarningsQualityFactor
from src.factors.tests.conftest import DummyFundamentalLoader, DummyRegistry


def _record(ni, ocf, assets=1000.0):
    return {
        "net_profit": ni,
        "cash_from_operations": ocf,
        "total_assets": assets,
        "current_assets": 300.0,
        "cash_and_equivalents": 50.0,
        "current_liabilities": 120.0,
        "short_term_debt": 20.0,
    }


def test_eq_india_positive_accrual_sign():
    factor_financials = {}
    for i in range(10):
        factor_financials[f"FILLER{i}.NS"] = {"current": _record(100 + i, 90 + i), "prior": _record(90 + i, 85 + i)}
    factor_financials["HIGH_ACCRUAL.NS"] = {"current": _record(200, 50), "prior": _record(120, 80)}
    factor_financials["LOW_ACCRUAL.NS"] = {"current": _record(80, 160), "prior": _record(70, 120)}

    factor = EarningsQualityFactor(
        DummyRegistry(fundamentals=DummyFundamentalLoader(factor_financials=factor_financials)),
        {"factors": {"earnings_quality": {"india_accrual_sign": "positive"}}},
    )
    tickers = list(factor_financials.keys())
    out = factor.compute(datetime(2024, 6, 30), tickers, use_cache=False)
    assert out.loc["HIGH_ACCRUAL.NS", "earnings_quality_zscore"] > out.loc["LOW_ACCRUAL.NS", "earnings_quality_zscore"]


def test_eq_missing_ocf_returns_nan():
    factor = EarningsQualityFactor(
        DummyRegistry(fundamentals=DummyFundamentalLoader(factor_financials={"MISS.NS": {"current": {"net_profit": 10, "total_assets": 100}, "prior": {"total_assets": 90}}})),
        {"factors": {"earnings_quality": {"india_accrual_sign": "positive"}}},
    )
    out = factor.compute(datetime(2024, 6, 30), ["MISS.NS"] + [f"FILL{i}.NS" for i in range(10)], use_cache=False)
    assert pd.isna(out.loc["MISS.NS", "earnings_quality_raw"])
