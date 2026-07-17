from datetime import datetime

import pandas as pd

from src.nlp.pipeline.pit_safe_scorer import PITSafeScorer


def test_pit_safe_scorer_filters_unavailable_news() -> None:
    scorer = PITSafeScorer({"nlp": {"pipeline": {"availability_lag_hours": 2}}})
    scored = pd.DataFrame(
        [
            {"headline": "available", "availability_date": datetime(2026, 1, 2, 10, 0)},
            {"headline": "future", "availability_date": datetime(2026, 1, 2, 12, 0)},
        ]
    )

    tradeable = scorer.filter_tradeable(scored, as_of_date=datetime(2026, 1, 2, 10, 30))

    assert tradeable["headline"].tolist() == ["available"]
