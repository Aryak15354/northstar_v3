from __future__ import annotations

from datetime import datetime

import pandas as pd

from src.nlp.pipeline.news_nlp_pipeline import NewsNLPPipeline
from src.nlp.pipeline.pit_safe_scorer import PITSafeScorer


def _config() -> dict:
    return {"nlp": {"pipeline": {"availability_lag_hours": 2, "min_headline_length": 10, "min_confidence": 0.55}}}


def test_availability_date_enforced_in_aggregation():
    pipeline = NewsNLPPipeline(_config())
    published_at = datetime(2026, 3, 20, 14, 0)
    result = pipeline.process_document("Infosys beats Q3 estimates, revenue rises 15%", published_at=published_at)
    assert result.availability_date == datetime(2026, 3, 20, 16, 0)


def test_future_headlines_excluded():
    scorer = PITSafeScorer(_config())
    df = pd.DataFrame(
        {
            "headline": ["Infosys beats Q3 estimates, revenue rises 15%"],
            "ticker": ["INFY.NS"],
            "date": [datetime(2026, 3, 24, 9, 0)],
            "source": ["test"],
        }
    )
    scored = scorer.score_historical_frame(df, as_of_date=datetime(2026, 3, 23, 15, 0))
    assert scored.empty


def test_no_weekend_news_bleeds_into_friday():
    pipeline = NewsNLPPipeline(_config())
    published_at = datetime(2026, 3, 21, 14, 0)
    result = pipeline.process_document("Infosys beats Q3 estimates, revenue rises 15%", published_at=published_at)
    assert result.availability_date.weekday() == 0
    assert result.availability_date.date().isoformat() == "2026-03-23"
