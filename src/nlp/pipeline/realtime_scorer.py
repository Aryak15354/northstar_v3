"""Low-latency wrapper around the headline NLP pipeline."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime
from typing import Any

from src.nlp.pipeline.news_nlp_pipeline import NLPDocumentResult, NewsNLPPipeline

logger = logging.getLogger(__name__)


class RealtimeScorer:
    """Caches pipeline instances so market-hour scoring stays warm."""

    _instances: dict[str, "RealtimeScorer"] = {}

    def __new__(cls, config: dict[str, Any] | None = None) -> "RealtimeScorer":
        key = hashlib.md5(json.dumps(config or {}, sort_keys=True, default=str).encode("utf-8")).hexdigest()
        if key not in cls._instances:
            cls._instances[key] = super().__new__(cls)
            cls._instances[key]._initialized = False
        return cls._instances[key]

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        if getattr(self, "_initialized", False):
            return
        self._pipeline = NewsNLPPipeline(config or {})
        self._initialized = True
        try:
            self._pipeline._finbert._load_model()
        except Exception as exc:
            logger.info("RealtimeScorer warm-up fell back to heuristic mode: %s", exc)

    def score_single(
        self,
        headline: str,
        ticker: str | None = None,
        published_at: datetime | None = None,
        source: str = "realtime",
    ) -> NLPDocumentResult | None:
        return self._pipeline.process_document(
            headline=headline,
            ticker=ticker,
            published_at=published_at or datetime.now(),
            source=source,
        )

    def score_list(self, headlines: list[dict[str, Any]]) -> list[NLPDocumentResult | None]:
        return [
            self.score_single(
                headline=item.get("headline", item.get("text", "")),
                ticker=item.get("ticker"),
                published_at=item.get("published_at"),
                source=item.get("source", "realtime"),
            )
            for item in headlines
        ]
