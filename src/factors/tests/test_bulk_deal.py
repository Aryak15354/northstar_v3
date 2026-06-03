from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd

from src.factors.bulk_deal_factor import BulkDealFactor
from src.factors.tests.conftest import DummyAlternativeLoader, DummyFundamentalLoader, DummyMarketLoader, DummyRegistry, make_price_panel


def _market_registry():
    dates = pd.bdate_range("2024-05-01", periods=30)
    close_map = {}
    volume_map = {}
    free_float = {}
    bulk_history = {}

    for i in range(10):
        ticker = f"FILLER{i}.NS"
        close_map[ticker] = pd.Series(100 + np.linspace(0, 3 + i * 0.1, len(dates)), index=dates)
        volume_map[ticker] = pd.Series(1_500_000 + i * 50_000, index=dates)
        free_float[ticker] = {"free_float_shares": 20_000_000.0, "free_float_pct": 60.0, "market_cap": 2_000_000_000.0}
        bulk_history[ticker] = pd.DataFrame()

    close_map["BUY.NS"] = pd.Series(120 + np.linspace(0, 4, len(dates)), index=dates)
    volume_map["BUY.NS"] = pd.Series(2_000_000, index=dates)
    free_float["BUY.NS"] = {"free_float_shares": 25_000_000.0, "free_float_pct": 50.0, "market_cap": 3_000_000_000.0}
    bulk_history["BUY.NS"] = pd.DataFrame(
        [
            {"ticker": "BUY.NS", "date": dates[-4], "quantity": 2_000_000, "price": 130.0, "signed_qty": 2_000_000, "notional": 260_000_000, "client_name": "PROMOTER GROUP HOLDINGS"},
            {"ticker": "BUY.NS", "date": dates[-3], "quantity": 1_200_000, "price": 131.0, "signed_qty": 1_200_000, "notional": 157_200_000, "client_name": "HSBC GLOBAL FUND"},
            {"ticker": "BUY.NS", "date": dates[-2], "quantity": 800_000, "price": 132.0, "signed_qty": 800_000, "notional": 105_600_000, "client_name": "AXIS MUTUAL FUND"},
        ]
    )

    close_map["SELL.NS"] = pd.Series(118 + np.linspace(0, 2, len(dates)), index=dates)
    volume_map["SELL.NS"] = pd.Series(2_100_000, index=dates)
    free_float["SELL.NS"] = {"free_float_shares": 25_000_000.0, "free_float_pct": 50.0, "market_cap": 2_800_000_000.0}
    bulk_history["SELL.NS"] = pd.DataFrame(
        [
            {"ticker": "SELL.NS", "date": dates[-4], "quantity": 1_500_000, "price": 126.0, "signed_qty": -1_500_000, "notional": 189_000_000, "client_name": "OVERSEAS FUND"},
            {"ticker": "SELL.NS", "date": dates[-3], "quantity": 1_000_000, "price": 125.0, "signed_qty": -1_000_000, "notional": 125_000_000, "client_name": "GLOBAL CAPITAL LLP"},
        ]
    )

    registry = DummyRegistry(
        market=DummyMarketLoader(prices=make_price_panel(close_map, volume_map)),
        fundamentals=DummyFundamentalLoader(free_float=free_float),
        alternative=DummyAlternativeLoader(bulk_history=bulk_history),
    )
    tickers = [f"FILLER{i}.NS" for i in range(10)] + ["BUY.NS", "SELL.NS"]
    return registry, tickers


def test_bulk_deal_signal_direction_and_identity_gate(tmp_path):
    registry, tickers = _market_registry()
    entity_table = tmp_path / "bulk_deal_entities.csv"
    entity_table.write_text(
        "raw_name_fragment,category,validated_accuracy\n"
        "PROMOTER GROUP,Promoter,0.95\n"
        "HSBC,FII,0.95\n"
        "AXIS MUTUAL FUND,DII,0.95\n"
    )

    factor = BulkDealFactor(
        registry,
        {"factors": {"bulk_deal": {"entity_table_path": str(entity_table), "min_classification_accuracy": 0.90}}},
    )
    out = factor.compute(datetime(2024, 6, 12), tickers, use_cache=False)
    assert out.loc["BUY.NS", "bulk_net_buy_adv_zscore"] > out.loc["SELL.NS", "bulk_net_buy_adv_zscore"]
    assert out.loc["BUY.NS", "bulk_promoter_buy_flag"] == 1.0
    assert out.loc["BUY.NS", "bulk_institutional_count"] >= 2.0


def test_bulk_deal_identity_features_zero_when_accuracy_gate_fails(tmp_path):
    registry, tickers = _market_registry()
    entity_table = tmp_path / "bulk_deal_entities.csv"
    entity_table.write_text(
        "raw_name_fragment,category,validated_accuracy\n"
        "PROMOTER GROUP,Promoter,0.85\n"
    )

    factor = BulkDealFactor(
        registry,
        {"factors": {"bulk_deal": {"entity_table_path": str(entity_table), "min_classification_accuracy": 0.90}}},
    )
    out = factor.compute(datetime(2024, 6, 12), tickers, use_cache=False)
    assert out.loc["BUY.NS", "bulk_promoter_buy_flag"] == 0.0
    assert out.loc["BUY.NS", "bulk_institutional_count"] == 0.0
