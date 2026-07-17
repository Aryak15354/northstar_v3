from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import numpy as np
import pandas as pd

from src.research.feature_factory import FeatureFactory
from src.signal_engineering.accruals_validator import AccrualsValidator
from src.valuation.valuation_feature_block import ValuationFeatureBlock


def _history() -> list[dict]:
    return [
        {
            "revenue": 800,
            "sales": 800,
            "net_profit": 80,
            "cash_from_operations": 90,
            "total_assets": 500,
            "total_borrowings": 120,
            "equity_capital": 10,
            "reserves": 250,
            "operating_profit": 130,
            "interest_expense": 10,
            "fixed_assets": 150,
            "debt_to_equity": 0.45,
            "roce_pct": 18,
        },
        {
            "revenue": 900,
            "sales": 900,
            "net_profit": 95,
            "cash_from_operations": 110,
            "total_assets": 540,
            "total_borrowings": 110,
            "equity_capital": 10,
            "reserves": 290,
            "operating_profit": 145,
            "interest_expense": 9,
            "fixed_assets": 160,
            "debt_to_equity": 0.37,
            "roce_pct": 20,
        },
        {
            "revenue": 1000,
            "sales": 1000,
            "net_profit": 100,
            "cash_from_operations": 120,
            "total_assets": 580,
            "total_borrowings": 100,
            "equity_capital": 10,
            "reserves": 320,
            "operating_profit": 155,
            "interest_expense": 8,
            "fixed_assets": 170,
            "debt_to_equity": 0.30,
            "roce_pct": 22,
        },
    ]


def test_accruals_validator_uses_real_cashflow():
    validator = AccrualsValidator({})
    validator._normalizer = SimpleNamespace(
        load_latest=lambda ticker, as_of_date, frequency="annual": _history()[-1],
        load_history=lambda ticker, as_of_date, n_periods=5, frequency="annual": _history(),
        get_source_paths=lambda ticker, frequency="annual": ["/tmp/source.csv"],
    )

    result = validator.validate("TEST.NS", datetime(2024, 6, 15))
    assert result["is_valid"] is True
    assert result["has_real_cashflow"] is True
    assert np.isfinite(result["accruals_ratio"])

    validator._normalizer = SimpleNamespace(
        load_latest=lambda ticker, as_of_date, frequency="annual": {"net_profit": 10, "total_assets": 100},
        load_history=lambda ticker, as_of_date, n_periods=5, frequency="annual": [{"total_assets": 90}, {"total_assets": 100}],
        get_source_paths=lambda ticker, frequency="annual": ["/tmp/source.csv"],
    )
    missing = validator.validate("TEST.NS", datetime(2024, 6, 15))
    assert missing["is_valid"] is False
    assert missing["status"] == "INSUFFICIENT_DATA"


def test_valuation_feature_block_all_columns(tmp_path, monkeypatch):
    monkeypatch.setattr(ValuationFeatureBlock, "CACHE_PATH", tmp_path / "valuation_scores.parquet")
    block = ValuationFeatureBlock({})

    def fake_compute_ticker(self, ticker, as_of_date, current_price):
        idx = int(str(ticker).split("_")[-1])
        return {
            "val_discount_to_fair_pct": idx * 1.0,
            "val_margin_of_safety": idx / 100.0,
            "val_owner_earnings_yield": idx / 200.0,
            "val_dcf_confidence": 0.4 + idx / 1000.0,
            "val_moat_score": 3.0 + idx / 10.0,
            "val_roce_5yr_avg": 10.0 + idx,
            "val_revenue_cagr_5yr": 5.0 + idx / 2.0,
            "val_earnings_consistency": 0.3 + idx / 100.0,
            "val_earnings_quality_score": 4.0 + idx / 10.0,
            "val_accruals_ratio": idx / 500.0,
            "val_debt_safety_score": 0.2 + idx / 100.0,
            "val_interest_coverage": 1.0 + idx,
            "val_composite_score": 40.0 + idx,
            "val_quality_composite": 4.0 + idx / 10.0,
            "val_safety_composite": 3.0 + idx / 10.0,
        }

    monkeypatch.setattr(ValuationFeatureBlock, "_compute_ticker", fake_compute_ticker)
    tickers = [f"TICKER_{i}" for i in range(20)]
    prices = {ticker: 100.0 + i for i, ticker in enumerate(tickers)}
    df = block.compute(datetime(2024, 6, 15), tickers, prices, use_cache=False)

    raw_cols = [c for c in block.FEATURE_NAMES if c in df.columns]
    z_cols = [f"{c}_zscore" for c in block.FEATURE_NAMES if f"{c}_zscore" in df.columns]
    assert len(raw_cols) == 15
    assert len(z_cols) == 15
    assert list(df.index) == tickers


def test_valuation_feature_block_recovers_from_corrupt_cache(tmp_path, monkeypatch):
    cache_path = tmp_path / "valuation_scores.parquet"
    cache_path.write_bytes(b"not-a-valid-parquet-file")
    monkeypatch.setattr(ValuationFeatureBlock, "CACHE_PATH", cache_path)
    block = ValuationFeatureBlock({})

    def fake_compute_ticker(self, ticker, as_of_date, current_price):
        return {
            "val_discount_to_fair_pct": 1.0,
            "val_margin_of_safety": 0.1,
            "val_owner_earnings_yield": 0.05,
            "val_dcf_confidence": 0.7,
            "val_moat_score": 6.0,
            "val_roce_5yr_avg": 18.0,
            "val_revenue_cagr_5yr": 11.0,
            "val_earnings_consistency": 0.8,
            "val_earnings_quality_score": 7.0,
            "val_accruals_ratio": 0.02,
            "val_debt_safety_score": 0.6,
            "val_interest_coverage": 8.0,
            "val_composite_score": 63.0,
            "val_quality_composite": 6.5,
            "val_safety_composite": 6.0,
        }

    monkeypatch.setattr(ValuationFeatureBlock, "_compute_ticker", fake_compute_ticker)

    tickers = ["AAA.NS", "BBB.NS"]
    df = block.compute(datetime(2024, 6, 15), tickers, {"AAA.NS": 100.0, "BBB.NS": 110.0}, use_cache=True)
    # The cache now flushes to disk in batches (I.1); force a flush to assert the
    # persisted contents. Quarantine of the corrupt file happens on read,
    # independent of flushing.
    block.flush_cache()

    assert list(df.index) == tickers
    assert cache_path.exists()
    repaired = pd.read_parquet(cache_path)
    assert not repaired.empty
    quarantined = list(tmp_path.glob("valuation_scores.corrupt_*.parquet"))
    assert quarantined


def test_valuation_cache_partial_ticker_reuse(tmp_path, monkeypatch):
    """I.2: a second call with an overlapping + new ticker set must reuse the
    cached tickers and only recompute the genuinely-new one — not the whole set.
    """
    monkeypatch.setattr(ValuationFeatureBlock, "CACHE_PATH", tmp_path / "valuation_scores.parquet")
    block = ValuationFeatureBlock({})
    computed_calls: list[str] = []

    def fake_compute_ticker(self, ticker, as_of_date, current_price):
        computed_calls.append(str(ticker))
        return {name: 1.0 for name in self.FEATURE_NAMES}

    monkeypatch.setattr(ValuationFeatureBlock, "_compute_ticker", fake_compute_ticker)

    when = datetime(2024, 6, 15)
    block.compute(when, ["A.NS", "B.NS"], {"A.NS": 100.0, "B.NS": 100.0}, use_cache=True)
    assert sorted(computed_calls) == ["A.NS", "B.NS"]

    computed_calls.clear()
    df = block.compute(when, ["A.NS", "B.NS", "C.NS"], {"A.NS": 100.0, "B.NS": 100.0, "C.NS": 100.0}, use_cache=True)
    # Only the new ticker is recomputed; A and B are served from cache.
    assert computed_calls == ["C.NS"]
    assert list(df.index) == ["A.NS", "B.NS", "C.NS"]


def test_valuation_feature_block_negative_margin_of_safety(monkeypatch):
    block = ValuationFeatureBlock({})
    block._normalizer = SimpleNamespace(
        load_latest=lambda ticker, as_of_date, frequency="annual": _history()[-1],
        load_history=lambda ticker, as_of_date, n_periods=10, frequency="annual": _history(),
    )
    block._dcf = SimpleNamespace(
        run=lambda **kwargs: {
            "fair_value": 80.0,
            "owner_earnings_yield": 0.07,
            "confidence": 0.8,
        }
    )
    block._moat = SimpleNamespace(score=lambda **kwargs: {"moat_score": 6.0})
    block._eq = SimpleNamespace(analyze=lambda **kwargs: {"quality_score": 70.0})

    result = block._compute_ticker("TEST.NS", datetime(2024, 6, 15), 100.0)
    assert result["val_margin_of_safety"] < 0


def test_feature_factory_includes_valuation_features():
    factory = FeatureFactory(config={"valuation": {"features_enabled": True}})
    feature_names = list(ValuationFeatureBlock.FEATURE_NAMES)

    class DummyValuationBlock:
        FEATURE_NAMES = feature_names

        def compute(self, as_of_date, tickers, market_prices, use_cache=True):
            df = pd.DataFrame(index=tickers)
            for idx, name in enumerate(self.FEATURE_NAMES, start=1):
                df[name] = float(idx)
                df[f"{name}_zscore"] = float(idx) / 10.0
            return df

    factory._valuation_block = DummyValuationBlock()

    panel = pd.DataFrame(
        {
            "date": [pd.Timestamp("2024-06-14"), pd.Timestamp("2024-06-14")],
            "ticker": ["AAA.NS", "BBB.NS"],
            "close": [100.0, 110.0],
        }
    )
    enriched = factory._add_valuation_features(panel, datetime(2024, 6, 14))
    assert "val_discount_to_fair_pct_zscore" in enriched.columns
    assert "val_moat_score_zscore" in enriched.columns
    assert "val_composite_score_zscore" in enriched.columns
    assert enriched["val_composite_score_zscore"].notna().all()
