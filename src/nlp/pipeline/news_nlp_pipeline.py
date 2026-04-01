"""Master orchestrator for headline-level NLP scoring."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import pandas as pd

from src.nlp.models.event_classifier import EventClassification, EventClassifier
from src.nlp.models.finbert_scorer import FinBERTScorer, SentimentScore
from src.nlp.models.india_financial_ner import ExtractedEntity, IndiaFinancialNER

logger = logging.getLogger(__name__)


def normalize_symbol(value: str | None) -> str:
    return str(value or "").replace(".NS", "").replace(".BO", "").strip().upper()


@dataclass
class NLPDocumentResult:
    headline: str
    ticker: str | None
    published_at: datetime
    source: str
    sentiment: SentimentScore | None = None
    entities: list[ExtractedEntity] = field(default_factory=list)
    resolved_tickers: list[str] = field(default_factory=list)
    event: EventClassification | None = None
    availability_date: datetime | None = None
    polarity: float = 0.0
    conviction: float = 0.0
    is_market_moving: bool = False


class NewsNLPPipeline:
    """Runs sentiment, NER, and event classification in one pass."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self._config = config or {}
        pipeline_cfg = self._config.get("nlp", {}).get("pipeline", {})
        self._availability_lag_hours = int(pipeline_cfg.get("availability_lag_hours", 2))
        self._min_headline_length = int(pipeline_cfg.get("min_headline_length", 10))
        self._max_headline_length = int(pipeline_cfg.get("max_headline_length", 512))
        self._min_confidence = float(pipeline_cfg.get("min_confidence", 0.55))
        self._finbert = FinBERTScorer(self._config)
        self._ner = IndiaFinancialNER(self._config)
        self._event_classifier = EventClassifier(self._config)

    def process_document(
        self,
        headline: str,
        ticker: str | None = None,
        published_at: datetime | None = None,
        source: str = "unknown",
    ) -> NLPDocumentResult | None:
        clean = self._preprocess(headline)
        if len(clean) < self._min_headline_length:
            return None
        timestamp = published_at or datetime.now()
        sentiment = self._finbert.score_single(clean)
        entities = self._ner.extract_entities(clean)
        resolved_tickers = list(dict.fromkeys([normalize_symbol(ticker)] if normalize_symbol(ticker) else []))
        resolved_tickers.extend(
            ticker_root
            for ticker_root in [item.canonical_ticker for item in entities if item.entity_type == "ORG" and item.canonical_ticker]
            if ticker_root not in resolved_tickers
        )
        event = self._event_classifier.classify(clean)

        polarity = float(sentiment.polarity if sentiment else 0.0)
        conviction = float(sentiment.confidence if sentiment else 0.0)
        if event and event.expected_direction != "unknown" and event.confidence >= 0.70:
            event_polarity = {"positive": 1.0, "negative": -1.0, "neutral": 0.0}.get(event.expected_direction, 0.0)
            polarity = 0.70 * polarity + 0.30 * event_polarity
            conviction = max(conviction, event.confidence * 0.80)
        if conviction < self._min_confidence and (event is None or event.confidence < self._min_confidence):
            polarity = 0.0
            conviction = max(conviction, event.confidence if event else conviction)
        availability_date = self._compute_availability_date(timestamp)
        is_market_moving = bool(
            abs(polarity) >= 0.35
            and conviction >= max(self._min_confidence, 0.65)
            and event is not None
            and event.materiality == "high"
        )
        return NLPDocumentResult(
            headline=clean,
            ticker=ticker,
            published_at=timestamp,
            source=source,
            sentiment=sentiment,
            entities=entities,
            resolved_tickers=resolved_tickers,
            event=event,
            availability_date=availability_date,
            polarity=float(polarity),
            conviction=float(conviction),
            is_market_moving=is_market_moving,
        )

    def process_batch(
        self,
        headlines_df: pd.DataFrame,
        text_col: str = "headline",
        ticker_col: str = "ticker",
        date_col: str = "date",
        source_col: str = "source",
    ) -> pd.DataFrame:
        if headlines_df.empty:
            return headlines_df.copy()
        work = headlines_df.copy()
        work[text_col] = work[text_col].fillna("").astype(str)
        clean_headlines = work[text_col].map(self._preprocess)
        valid_mask = clean_headlines.str.len() >= self._min_headline_length
        work = work.loc[valid_mask].copy()
        clean_headlines = clean_headlines.loc[valid_mask]
        if work.empty:
            return headlines_df.copy()

        sentiments = self._finbert.score_batch(clean_headlines.tolist())
        records: list[dict[str, Any]] = []
        for (_, row), clean, sentiment in zip(work.iterrows(), clean_headlines.tolist(), sentiments):
            published_at = pd.to_datetime(row.get(date_col), errors="coerce")
            if pd.isna(published_at):
                published_at = pd.Timestamp(datetime.now())
            if getattr(published_at, "tzinfo", None) is not None:
                published_at = published_at.tz_localize(None)
            entities = self._ner.extract_entities(clean)
            resolved = list(dict.fromkeys([normalize_symbol(row.get(ticker_col))] if normalize_symbol(row.get(ticker_col)) else []))
            resolved.extend(
                ticker_root
                for ticker_root in [item.canonical_ticker for item in entities if item.entity_type == "ORG" and item.canonical_ticker]
                if ticker_root not in resolved
            )
            event = self._event_classifier.classify(clean)
            polarity = float(sentiment.polarity)
            conviction = float(sentiment.confidence)
            if event.expected_direction != "unknown" and event.confidence >= 0.70:
                event_polarity = {"positive": 1.0, "negative": -1.0, "neutral": 0.0}.get(event.expected_direction, 0.0)
                polarity = 0.70 * polarity + 0.30 * event_polarity
                conviction = max(conviction, event.confidence * 0.80)
            if conviction < self._min_confidence and event.confidence < self._min_confidence:
                polarity = 0.0
            records.append(
                {
                    "polarity": float(polarity),
                    "conviction": float(conviction),
                    "sentiment_label": sentiment.predicted_label,
                    "sentiment_confidence": float(sentiment.confidence),
                    "sentiment_model_version": sentiment.model_version,
                    "event_type": event.event_type,
                    "event_direction": event.expected_direction,
                    "event_materiality": event.materiality,
                    "event_confidence": float(event.confidence),
                    "resolved_tickers": ",".join(resolved),
                    "availability_date": self._compute_availability_date(published_at.to_pydatetime()),
                    "is_market_moving": bool(
                        abs(polarity) >= 0.35
                        and conviction >= max(self._min_confidence, 0.65)
                        and event.materiality == "high"
                    ),
                    "from_cache": bool(sentiment.from_cache),
                    "entity_count": len(entities),
                }
            )
        result_df = pd.DataFrame(records)
        base_df = work.reset_index(drop=True).drop(columns=[col for col in result_df.columns if col in work.columns], errors="ignore")
        scored = pd.concat([base_df, result_df], axis=1)
        return scored

    def _preprocess(self, text: str) -> str:
        value = str(text or "")
        value = re.sub(r"<[^>]+>", " ", value)
        value = re.sub(r"http\S+", " ", value)
        value = re.sub(r"\b(BSE|NSE)\s*[:|-]\s*", " ", value, flags=re.IGNORECASE)
        value = re.sub(r"source\s*:.*$", " ", value, flags=re.IGNORECASE)
        value = re.sub(r"\s+", " ", value).strip()
        if len(value) > self._max_headline_length:
            return value[: self._max_headline_length].rstrip()
        return value

    def _compute_availability_date(self, published_at: datetime) -> datetime:
        available = published_at + timedelta(hours=self._availability_lag_hours)
        while available.weekday() >= 5:
            available += timedelta(days=1)
        return available
