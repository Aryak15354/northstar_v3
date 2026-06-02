from __future__ import annotations

from datetime import datetime

import pandas as pd

from src.nlp.pipeline.news_nlp_pipeline import NewsNLPPipeline


def _config() -> dict:
    return {
        "nlp": {
            "models": {"sentiment": {"device": "cpu", "batch_size": 8, "max_length": 128}},
            "pipeline": {
                "availability_lag_hours": 2,
                "min_headline_length": 10,
                "max_headline_length": 256,
                "min_confidence": 0.55,
            },
        }
    }


def test_full_pipeline_single_headline():
    pipeline = NewsNLPPipeline(_config())
    result = pipeline.process_document(
        "Infosys beats Q3 estimates, revenue rises 15%",
        ticker="INFY.NS",
        published_at=datetime(2026, 3, 20, 9, 30),
        source="test",
    )
    assert result is not None
    assert result.sentiment is not None
    assert result.event is not None
    assert result.availability_date is not None


def test_availability_date_is_future_of_published_at():
    pipeline = NewsNLPPipeline(_config())
    published_at = datetime(2026, 3, 20, 14, 0)
    result = pipeline.process_document("Infosys beats Q3 estimates, revenue rises 15%", published_at=published_at)
    assert result.availability_date == datetime(2026, 3, 20, 16, 0)


def test_batch_matches_single():
    pipeline = NewsNLPPipeline(_config())
    df = pd.DataFrame(
        {
            "headline": [
                "Infosys beats Q3 estimates, revenue rises 15%",
                "Promoter arrested for fraud allegation",
            ],
            "ticker": ["INFY.NS", "RELIANCE.NS"],
            "date": [datetime(2026, 3, 20, 9, 30), datetime(2026, 3, 20, 10, 0)],
            "source": ["test", "test"],
        }
    )
    batch = pipeline.process_batch(df)
    single = [pipeline.process_document(row.headline, row.ticker, row.date, row.source) for row in df.itertuples(index=False)]
    assert [round(value, 6) for value in batch["polarity"].tolist()] == [round(item.polarity, 6) for item in single]


def test_market_moving_flag_set_correctly():
    pipeline = NewsNLPPipeline(_config())
    result = pipeline.process_document("RBI raises repo rate by 25 basis points", published_at=datetime(2026, 3, 20, 11, 0))
    assert result.is_market_moving is True


def test_low_confidence_not_market_moving():
    pipeline = NewsNLPPipeline(_config())
    result = pipeline.process_document("Board meeting scheduled for next week", published_at=datetime(2026, 3, 20, 11, 0))
    assert result.is_market_moving is False
