"""Point-in-time safe scoring helpers."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd

from src.nlp.pipeline.news_nlp_pipeline import NewsNLPPipeline


class PITSafeScorer:
    """Ensures only tradeable NLP outputs are exposed to research/backtests."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self._pipeline = NewsNLPPipeline(config or {})

    def score_historical_frame(
        self,
        headlines_df: pd.DataFrame,
        *,
        as_of_date: datetime,
        text_col: str = "headline",
        ticker_col: str = "ticker",
        date_col: str = "date",
        source_col: str = "source",
    ) -> pd.DataFrame:
        scored = self._pipeline.process_batch(
            headlines_df,
            text_col=text_col,
            ticker_col=ticker_col,
            date_col=date_col,
            source_col=source_col,
        )
        return self.filter_tradeable(scored, as_of_date=as_of_date)

    def filter_tradeable(self, scored_df: pd.DataFrame, *, as_of_date: datetime) -> pd.DataFrame:
        if scored_df.empty:
            return scored_df.copy()
        work = scored_df.copy()
        as_of_ts = pd.Timestamp(as_of_date).tz_localize(None) if pd.Timestamp(as_of_date).tzinfo else pd.Timestamp(as_of_date)
        work["availability_date"] = pd.to_datetime(work["availability_date"], errors="coerce")
        return work[work["availability_date"] <= as_of_ts].copy()
