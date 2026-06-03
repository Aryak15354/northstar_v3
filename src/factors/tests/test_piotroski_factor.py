from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd

from src.factors.piotroski_factor import PiotroskiFactor
from src.factors.tests.conftest import DummyFundamentalLoader, DummyRegistry


def _full_pass_records():
    curr = {
        "net_profit": 120.0,
        "total_assets": 1000.0,
        "cash_from_operations": 150.0,
        "total_borrowings": 100.0,
        "current_assets": 300.0,
        "current_liabilities": 100.0,
        "shares_outstanding": 100.0,
        "revenue": 900.0,
        "cost_of_goods_sold": 500.0,
    }
    prior = {
        "net_profit": 80.0,
        "total_assets": 1000.0,
        "cash_from_operations": 70.0,
        "total_borrowings": 150.0,
        "current_assets": 250.0,
        "current_liabilities": 100.0,
        "shares_outstanding": 100.0,
        "revenue": 800.0,
        "cost_of_goods_sold": 500.0,
    }
    return curr, prior


def test_piotroski_all_nine_pass():
    factor = PiotroskiFactor(DummyRegistry(fundamentals=DummyFundamentalLoader()), {"factors": {"piotroski": {"min_tests_required": 6}}})
    curr, prior = _full_pass_records()
    assert factor._compute_fscore("TEST.NS", curr, prior) == 9


def test_piotroski_missing_data_returns_nan():
    factor = PiotroskiFactor(DummyRegistry(fundamentals=DummyFundamentalLoader()), {"factors": {"piotroski": {"min_tests_required": 6}}})
    curr = {"net_profit": 10.0, "total_assets": 100.0}
    prior = {"net_profit": 9.0, "total_assets": 100.0}
    assert np.isnan(factor._compute_fscore("TEST.NS", curr, prior))


def test_piotroski_dilution_tolerance():
    factor = PiotroskiFactor(DummyRegistry(fundamentals=DummyFundamentalLoader()), {"factors": {"piotroski": {"min_tests_required": 6}}})
    curr, prior = _full_pass_records()
    curr["shares_outstanding"] = 101.5
    assert factor._compute_fscore("TEST.NS", curr, prior) >= 8
    curr["shares_outstanding"] = 103.0
    assert factor._compute_fscore("TEST.NS", curr, prior) <= 8


def test_piotroski_compute_uses_factor_financial_adapter():
    curr, prior = _full_pass_records()
    registry = DummyRegistry(
        fundamentals=DummyFundamentalLoader(
            factor_financials={
                "TEST.NS": {"current": curr, "prior": prior},
                "MISS.NS": {},
            }
        )
    )
    factor = PiotroskiFactor(registry, {"factors": {"piotroski": {"min_tests_required": 6}}})
    out = factor.compute(datetime(2024, 6, 30), ["TEST.NS", "MISS.NS"] + [f"FILL{i}.NS" for i in range(10)], use_cache=False)
    assert pd.notna(out.loc["TEST.NS", "piotroski_raw"])
    assert pd.isna(out.loc["MISS.NS", "piotroski_raw"])
