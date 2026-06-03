from __future__ import annotations

from datetime import datetime

import pandas as pd

from src.factors.operating_profitability_factor import OperatingProfitabilityFactor
from src.factors.tests.conftest import DummyFundamentalLoader, DummyRegistry


def _records(op_income, assets, prior_op, prior_assets):
    return {
        "current": {"operating_income": op_income, "total_assets": assets, "revenue": op_income * 3.0},
        "prior": {"operating_income": prior_op, "total_assets": prior_assets, "revenue": prior_op * 3.0},
    }


def test_operating_profitability_signal_direction():
    factor_financials = {}
    for i in range(10):
        factor_financials[f"FILLER{i}.NS"] = _records(120 + i, 1000, 110 + i, 980)
    factor_financials["STRONG.NS"] = _records(260, 900, 180, 920)
    factor_financials["WEAK.NS"] = _records(70, 1100, 100, 1050)

    factor = OperatingProfitabilityFactor(
        DummyRegistry(fundamentals=DummyFundamentalLoader(factor_financials=factor_financials)),
        {"factors": {"operating_profitability": {"reporting_lag_days": 60}}},
    )
    tickers = list(factor_financials.keys())
    out = factor.compute(datetime(2024, 6, 30), tickers, use_cache=False)
    assert out.loc["STRONG.NS", "operating_profitability_zscore"] > out.loc["WEAK.NS", "operating_profitability_zscore"]
