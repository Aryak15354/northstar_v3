from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

import src.intelligence.news_brain.layers.company_news_layer as company_layer_module
from src.intelligence.news_brain.layers.company_news_layer import CompanyNewsLayer
from src.intelligence.news_brain.news_signal_state import ShockDirection


def _write_company_fixture_tree(root: Path) -> None:
    (root / "data/canonical/news").mkdir(parents=True, exist_ok=True)
    (root / "data/canonical/sentiment").mkdir(parents=True, exist_ok=True)
    (root / "data/processed").mkdir(parents=True, exist_ok=True)

    pd.DataFrame(
        {
            "ticker": ["INFY.NS", "HDFCBANK.NS"],
            "Industry": ["Information Technology", "Financial Services"],
        }
    ).to_parquet(root / "data/processed/portfolio_weights.parquet", index=False)

    pd.DataFrame(
        {
            "ticker": ["INFY.NS", "HDFCBANK.NS"],
            "date": pd.to_datetime(["2026-03-20", "2026-03-20"]),
            "availability_date": pd.to_datetime(["2026-03-21", "2026-03-21"]),
            "sentiment_polarity": [0.65, -0.75],
            "sentiment_conviction": [0.85, 0.90],
            "source": ["daily_nlp", "daily_nlp"],
            "dominant_event_type": ["earnings_beat", "fraud_allegation"],
        }
    ).to_parquet(root / "data/canonical/sentiment/company_sentiment_daily.parquet", index=False)

    pd.DataFrame(
        {
            "ticker": ["INFY.NS"],
            "headline": ["Infosys beats Q3 estimates, revenue rises 15%"],
            "source": ["rss"],
            "date": pd.to_datetime(["2026-03-20 09:00:00"]),
            "availability_date": pd.to_datetime(["2026-03-20 11:00:00"]),
        }
    ).to_parquet(root / "data/canonical/news/company_news_history.parquet", index=False)


def test_company_news_layer_combines_realtime_nlp_and_daily_sentiment(tmp_path, monkeypatch):
    _write_company_fixture_tree(tmp_path)
    monkeypatch.setattr(company_layer_module, "PROJECT_ROOT", tmp_path)

    layer = CompanyNewsLayer(
        {
            "news_brain": {
                "company_layer": {
                    "sentiment_negative_threshold": -0.30,
                    "sentiment_positive_threshold": 0.30,
                    "sentiment_conviction_threshold": 0.60,
                    "bellwether_tickers": ["INFY", "HDFCBANK"],
                }
            },
            "nlp": {
                "models": {"sentiment": {"device": "cpu", "batch_size": 8, "max_length": 128}},
                "pipeline": {"availability_lag_hours": 2, "min_headline_length": 10, "max_headline_length": 256, "min_confidence": 0.55},
            },
        }
    )

    signals = layer.run(datetime(2026, 3, 21, 12, 0))
    signal_types = {(signal.ticker, signal.signal_type) for signal in signals}

    assert ("INFY.NS", "earnings_beat") in signal_types
    assert ("HDFCBANK.NS", "fraud_allegation") in signal_types
    assert any(signal.direction == ShockDirection.BULLISH for signal in signals if signal.ticker == "INFY.NS")
    assert any(signal.direction == ShockDirection.BEARISH for signal in signals if signal.ticker == "HDFCBANK.NS")
