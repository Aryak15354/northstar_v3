from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from src.research.feature_factory import FeatureFactory
from src.valuation.valuation_feature_block import ValuationFeatureBlock


REQUIRED_VALUATION_ZSCORES = [
    "val_discount_to_fair_pct_zscore",
    "val_margin_of_safety_zscore",
    "val_owner_earnings_yield_zscore",
    "val_moat_score_zscore",
    "val_roce_5yr_avg_zscore",
    "val_earnings_quality_score_zscore",
    "val_debt_safety_score_zscore",
    "val_composite_score_zscore",
]


def test_feature_matrix_includes_valuation_zscore_columns_when_data_exists() -> None:
    factory = FeatureFactory(config={"valuation": {"features_enabled": True, "feature_columns": "zscore_only"}})

    class DummyValuationBlock:
        FEATURE_NAMES = [name.replace("_zscore", "") for name in REQUIRED_VALUATION_ZSCORES]

        def compute(self, as_of_date, tickers, market_prices, use_cache=True):
            df = pd.DataFrame(index=tickers)
            for idx, column in enumerate(REQUIRED_VALUATION_ZSCORES, start=1):
                df[column] = float(idx) / 10.0
            return df

    factory._valuation_block = DummyValuationBlock()
    panel = pd.DataFrame(
        {
            "date": [pd.Timestamp("2026-03-20"), pd.Timestamp("2026-03-20")],
            "ticker": ["AAA.NS", "BBB.NS"],
            "close": [100.0, 105.0],
        }
    )

    enriched = factory._add_valuation_features(panel, datetime(2026, 3, 20))

    for column in REQUIRED_VALUATION_ZSCORES:
        assert column in enriched.columns
        assert enriched[column].notna().all()


def test_feature_matrix_continues_without_valuation_columns_when_data_missing() -> None:
    factory = FeatureFactory(config={"valuation": {"features_enabled": True, "feature_columns": "zscore_only"}})

    class BrokenValuationBlock:
        FEATURE_NAMES = []

        def compute(self, as_of_date, tickers, market_prices, use_cache=True):
            raise RuntimeError("valuation source missing")

    factory._valuation_block = BrokenValuationBlock()
    panel = pd.DataFrame(
        {
            "date": [pd.Timestamp("2026-03-20")],
            "ticker": ["AAA.NS"],
            "close": [100.0],
        }
    )

    enriched = factory._add_valuation_features(panel, datetime(2026, 3, 20))

    assert list(enriched.columns) == list(panel.columns)


def test_valuation_cache_prevents_future_data_from_altering_historical_features(
    tmp_path: Path,
    monkeypatch,
) -> None:
    cache_path = tmp_path / "valuation_scores.parquet"
    monkeypatch.setattr(ValuationFeatureBlock, "CACHE_PATH", cache_path)

    pd.DataFrame(
        [
            {
                "ticker": "AAA.NS",
                "date": pd.Timestamp("2026-03-19"),
                "val_composite_score_zscore": 0.25,
            },
            {
                "ticker": "AAA.NS",
                "date": pd.Timestamp("2026-03-25"),
                "val_composite_score_zscore": 9.99,
            },
        ]
    ).to_parquet(cache_path, index=False)

    block = ValuationFeatureBlock({"valuation": {"allow_prior_cache_fallback": True, "max_cache_fallback_age_days": 30}})
    loaded = block._load_from_cache(datetime(2026, 3, 20), ["AAA.NS"])

    assert loaded is not None
    assert float(loaded.loc["AAA.NS", "val_composite_score_zscore"]) == 0.25
