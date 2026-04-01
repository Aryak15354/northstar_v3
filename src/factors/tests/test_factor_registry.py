from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd

from src.factors.factor_registry import FactorRegistry
from src.factors.tests.conftest import DummyFundamentalLoader, DummyMarketLoader, DummyRegistry, make_price_panel


def _factor_registry_fixture():
    dates = pd.bdate_range("2024-01-02", periods=140)
    market_ret = pd.Series(np.linspace(-0.01, 0.012, len(dates)), index=dates)
    market_close = 100 * np.exp(market_ret.cumsum())

    close_map = {}
    volume_map = {}
    factor_financials = {}

    for i in range(10):
        ticker = f"FILLER{i}.NS"
        beta = 0.75 + i * 0.05
        ret = beta * market_ret + 0.0002 * np.cos(np.arange(len(dates)))
        close_map[ticker] = 100 * np.exp(ret.cumsum())
        volume_map[ticker] = pd.Series(3_000_000 + i * 150_000, index=dates)
        factor_financials[ticker] = {
            "current": {
                "net_profit": 100 + i,
                "total_assets": 1000 + i * 10,
                "cash_from_operations": 110 + i,
                "total_borrowings": 140 - i,
                "current_assets": 320 + i,
                "current_liabilities": 120,
                "shares_outstanding": 100,
                "revenue": 900 + i * 5,
                "cost_of_goods_sold": 520,
                "cash_and_equivalents": 60,
                "short_term_debt": 15,
            },
            "prior": {
                "net_profit": 85 + i,
                "total_assets": 980 + i * 10,
                "cash_from_operations": 90 + i,
                "total_borrowings": 150 - i,
                "current_assets": 290 + i,
                "current_liabilities": 125,
                "shares_outstanding": 100,
                "revenue": 860 + i * 5,
                "cost_of_goods_sold": 515,
                "cash_and_equivalents": 55,
                "short_term_debt": 18,
            },
        }

    close_map["LOW.NS"] = 100 * np.exp((0.35 * market_ret).cumsum())
    close_map["HIGH.NS"] = 100 * np.exp((1.75 * market_ret).cumsum())
    volume_map["LOW.NS"] = pd.Series(18_000_000, index=dates)
    volume_map["HIGH.NS"] = pd.Series(80_000, index=dates)
    factor_financials["LOW.NS"] = {
        "current": {
            "net_profit": 75,
            "total_assets": 950,
            "cash_from_operations": 155,
            "total_borrowings": 80,
            "current_assets": 310,
            "current_liabilities": 140,
            "shares_outstanding": 100,
            "revenue": 760,
            "cost_of_goods_sold": 430,
            "cash_and_equivalents": 70,
            "short_term_debt": 10,
        },
        "prior": {
            "net_profit": 68,
            "total_assets": 930,
            "cash_from_operations": 120,
            "total_borrowings": 95,
            "current_assets": 275,
            "current_liabilities": 150,
            "shares_outstanding": 100,
            "revenue": 730,
            "cost_of_goods_sold": 425,
            "cash_and_equivalents": 65,
            "short_term_debt": 12,
        },
    }
    factor_financials["HIGH.NS"] = {
        "current": {
            "net_profit": 140,
            "total_assets": 980,
            "cash_from_operations": 60,
            "total_borrowings": 220,
            "current_assets": 260,
            "current_liabilities": 170,
            "shares_outstanding": 104,
            "revenue": 920,
            "cost_of_goods_sold": 610,
            "cash_and_equivalents": 35,
            "short_term_debt": 45,
        },
        "prior": {
            "net_profit": 135,
            "total_assets": 960,
            "cash_from_operations": 88,
            "total_borrowings": 210,
            "current_assets": 270,
            "current_liabilities": 160,
            "shares_outstanding": 100,
            "revenue": 915,
            "cost_of_goods_sold": 595,
            "cash_and_equivalents": 40,
            "short_term_debt": 42,
        },
    }

    registry = DummyRegistry(
        market=DummyMarketLoader(
            prices=make_price_panel(close_map, volume_map),
            index_df=pd.DataFrame({"close": market_close}, index=dates),
        ),
        fundamentals=DummyFundamentalLoader(factor_financials=factor_financials),
    )
    config = {
        "factors": {
            "enabled_factors": ["bab", "amihud", "piotroski", "max", "earnings_quality"],
            "bab": {"lookback_days": 126, "min_observations": 80, "vol_lookback_days": 21},
            "amihud": {"lookback_days": 21, "min_observations": 10, "scaling": 1_000_000},
            "piotroski": {"min_tests_required": 6},
            "max": {"lookback_days": 21, "top_n_days": 5, "min_observations": 15},
            "earnings_quality": {"india_accrual_sign": "positive"},
        }
    }
    tickers = [f"FILLER{i}.NS" for i in range(10)] + ["LOW.NS", "HIGH.NS"]
    return registry, config, tickers


def test_factor_registry_compute_all_returns_canonical_columns():
    registry, config, tickers = _factor_registry_fixture()
    factor_registry = FactorRegistry(registry, config)
    out = factor_registry.compute_all(datetime(2024, 6, 12), tickers, use_cache=False)

    expected = [
        "bab_raw", "bab_zscore", "bab_rank", "bab_available",
        "amihud_raw", "amihud_zscore", "amihud_rank", "amihud_available",
        "piotroski_raw", "piotroski_zscore", "piotroski_rank", "piotroski_available",
        "max_raw", "max_zscore", "max_rank", "max_available",
        "earnings_quality_raw", "earnings_quality_zscore", "earnings_quality_rank", "earnings_quality_available",
    ]
    assert list(out.index) == tickers
    for column in expected:
        assert column in out.columns


def test_factor_registry_feature_names_and_coverage_report():
    registry, config, tickers = _factor_registry_fixture()
    factor_registry = FactorRegistry(registry, config)

    feature_names = factor_registry.get_feature_names(include_raw=False)
    assert "bab_zscore" in feature_names
    assert "earnings_quality_rank" in feature_names
    assert "bab_raw" not in feature_names

    coverage = factor_registry.get_coverage_report(datetime(2024, 6, 12), tickers)
    assert set(coverage.keys()) == {"bab", "amihud", "piotroski", "max", "earnings_quality"}
    assert coverage["bab"]["universe_size"] == len(tickers)
