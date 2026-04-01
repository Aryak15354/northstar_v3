"""Build weakly labeled sentiment datasets from price reactions."""

from __future__ import annotations

import logging
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


class TrainingDataBuilder:
    """Creates sentiment fine-tuning datasets from news and forward returns."""

    def __init__(
        self,
        news_path: str = "data/canonical/news/company_news_history.parquet",
        prices_path: str = "data/canonical/prices/equity_prices_daily.parquet",
        output_dir: str = "data/nlp/training/labeled_sentiment",
        config: dict[str, Any] | None = None,
    ) -> None:
        self._config = config or {}
        self._news_path = Path(news_path)
        self._prices_path = Path(prices_path)
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)
        training_cfg = self._config.get("nlp", {}).get("training", {})
        self._positive_threshold = float(training_cfg.get("auto_label_positive_threshold", 0.03))
        self._negative_threshold = float(training_cfg.get("auto_label_negative_threshold", -0.03))
        self._label_confidence = float(training_cfg.get("auto_label_confidence", 0.70))
        self._hq_positive_threshold = float(training_cfg.get("high_quality_positive_threshold", 0.04))
        self._hq_negative_threshold = float(training_cfg.get("high_quality_negative_threshold", -0.04))
        self._hq_neutral_abs_threshold = float(training_cfg.get("high_quality_neutral_abs_threshold", 0.005))
        self._teacher_min_confidence = float(training_cfg.get("teacher_min_confidence", 0.75))
        self._teacher_neutral_min_confidence = float(training_cfg.get("teacher_neutral_min_confidence", 0.45))
        self._teacher_neutral_max_abs_polarity = float(training_cfg.get("teacher_neutral_max_abs_polarity", 0.12))
        self._neutral_presample_size = int(training_cfg.get("high_quality_neutral_presample_size", 6000))
        self._max_examples_per_ticker_per_class = int(training_cfg.get("max_examples_per_ticker_per_class", 20))
        self._random_seed = int(training_cfg.get("random_seed", 42))
        self._deduplicate_training_text = bool(training_cfg.get("deduplicate_training_text", True))

    def build_auto_labeled_dataset(
        self,
        min_examples_per_class: int = 1000,
        max_total_examples: int = 10000,
        forward_return_days: int = 1,
    ) -> pd.DataFrame:
        news = pd.read_parquet(self._news_path)
        prices = pd.read_parquet(self._prices_path)
        news["date"] = pd.to_datetime(news["date"], errors="coerce").dt.normalize()
        prices["date"] = pd.to_datetime(prices["date"], errors="coerce").dt.normalize()
        prices["close"] = pd.to_numeric(prices["close"], errors="coerce")
        prices = prices.dropna(subset=["date", "ticker", "close"]).copy()

        price_pivot = prices.pivot(index="date", columns="ticker", values="close").sort_index()
        forward_returns = price_pivot.pct_change(periods=forward_return_days, fill_method=None).shift(-forward_return_days)

        labeled_rows: list[dict[str, Any]] = []
        for _, row in news.iterrows():
            ticker = str(row.get("ticker", "") or "").strip()
            headline = str(row.get("headline", "") or "").strip()
            news_date = row.get("date")
            if not ticker or len(headline) < 10 or pd.isna(news_date):
                continue
            if ticker not in forward_returns.columns:
                continue
            try:
                realized = forward_returns.loc[news_date, ticker]
            except Exception:
                continue
            if pd.isna(realized):
                continue
            if realized >= self._positive_threshold:
                label = "positive"
                confidence = self._label_confidence
            elif realized <= self._negative_threshold:
                label = "negative"
                confidence = self._label_confidence
            else:
                label = "neutral"
                confidence = min(0.65, self._label_confidence - 0.10)
            labeled_rows.append(
                {
                    "text": headline,
                    "label": label,
                    "confidence": float(confidence),
                    "source": "auto_price_reaction",
                    "ticker": ticker,
                    "date": news_date,
                    "forward_return": float(realized),
                }
            )

        labeled = pd.DataFrame(labeled_rows)
        if labeled.empty:
            return labeled
        samples = []
        for label in ("positive", "negative", "neutral"):
            subset = labeled[labeled["label"] == label]
            if subset.empty:
                continue
            take = min(min_examples_per_class, len(subset))
            samples.append(subset.sample(take, random_state=42))
        balanced = pd.concat(samples, ignore_index=True).sample(frac=1.0, random_state=42).head(max_total_examples)
        output_path = self._output_dir / "auto_labeled_dataset.parquet"
        balanced.to_parquet(output_path, index=False)
        logger.info("Saved auto-labeled NLP dataset to %s", output_path)
        return balanced

    def build_high_quality_dataset(
        self,
        min_examples_per_class: int = 1000,
        max_total_examples: int = 6000,
        forward_return_days: int = 1,
        output_name: str = "auto_labeled_dataset_high_quality.parquet",
    ) -> pd.DataFrame:
        """
        Build a cleaner teacher-filtered dataset:
        - stronger price thresholds
        - base FinBERT teacher agreement
        - low-return, low-polarity neutrals only
        - text deduplication and ticker diversification
        """
        labeled = self._build_labeled_frame(forward_return_days=forward_return_days)
        if labeled.empty:
            return labeled

        strong = labeled[
            (labeled["forward_return"] >= self._hq_positive_threshold)
            | (labeled["forward_return"] <= self._hq_negative_threshold)
        ].copy()
        neutral_pool = labeled[labeled["forward_return"].abs() <= self._hq_neutral_abs_threshold].copy()
        if len(neutral_pool) > self._neutral_presample_size:
            neutral_pool = neutral_pool.sample(self._neutral_presample_size, random_state=self._random_seed)
        candidates = pd.concat([strong, neutral_pool], ignore_index=True)
        if candidates.empty:
            return candidates

        teacher_scores = self._score_with_teacher(candidates["text"].tolist())
        teacher_df = pd.DataFrame(
            {
                "text": list(teacher_scores.keys()),
                "teacher_label": [score["label"] for score in teacher_scores.values()],
                "teacher_confidence": [score["confidence"] for score in teacher_scores.values()],
                "teacher_polarity": [score["polarity"] for score in teacher_scores.values()],
            }
        )
        candidates = candidates.merge(teacher_df, on="text", how="left")

        positive = candidates[
            (candidates["forward_return"] >= self._hq_positive_threshold)
            & (candidates["teacher_label"] == "positive")
            & (candidates["teacher_confidence"] >= self._teacher_min_confidence)
            & (candidates["teacher_polarity"] > 0.20)
        ].copy()
        negative = candidates[
            (candidates["forward_return"] <= self._hq_negative_threshold)
            & (candidates["teacher_label"] == "negative")
            & (candidates["teacher_confidence"] >= self._teacher_min_confidence)
            & (candidates["teacher_polarity"] < -0.20)
        ].copy()
        neutral = candidates[
            (candidates["forward_return"].abs() <= self._hq_neutral_abs_threshold)
            & (candidates["teacher_confidence"] >= self._teacher_neutral_min_confidence)
            & (
                (candidates["teacher_label"] == "neutral")
                | (candidates["teacher_polarity"].abs() <= self._teacher_neutral_max_abs_polarity)
            )
        ].copy()

        positive["label"] = "positive"
        negative["label"] = "negative"
        neutral["label"] = "neutral"

        high_quality = pd.concat([positive, negative, neutral], ignore_index=True)
        if high_quality.empty:
            return high_quality

        high_quality["selection_score"] = high_quality.apply(self._selection_score, axis=1)
        if self._deduplicate_training_text:
            high_quality["normalized_text"] = high_quality["text"].map(self._normalize_text)
            high_quality = (
                high_quality.sort_values("selection_score", ascending=False)
                .drop_duplicates(subset=["label", "normalized_text"], keep="first")
                .copy()
            )
        high_quality = self._cap_examples_per_ticker(high_quality)

        samples = []
        for label in ("positive", "negative", "neutral"):
            subset = high_quality[high_quality["label"] == label].sort_values("selection_score", ascending=False)
            if subset.empty:
                continue
            samples.append(subset.head(min_examples_per_class))
        curated = pd.concat(samples, ignore_index=True) if samples else pd.DataFrame()
        if curated.empty:
            return curated
        curated = curated.sort_values(["label", "selection_score"], ascending=[True, False]).head(max_total_examples)
        curated = curated.sample(frac=1.0, random_state=self._random_seed).reset_index(drop=True)
        curated["source"] = "teacher_price_agreement"
        output_path = self._output_dir / output_name
        curated.to_parquet(output_path, index=False)
        logger.info("Saved high-quality NLP dataset to %s", output_path)
        return curated

    def export_manual_label_batch(self, sample_size: int = 500) -> Path:
        news = pd.read_parquet(self._news_path)
        sample = news[["ticker", "headline", "date"]].dropna().sample(min(sample_size, len(news)), random_state=42)
        sample["label"] = ""
        sample["confidence"] = ""
        output_path = self._output_dir / "manual_label_batch.csv"
        sample.to_csv(output_path, index=False)
        return output_path

    def _build_labeled_frame(self, *, forward_return_days: int) -> pd.DataFrame:
        news = pd.read_parquet(self._news_path)
        prices = pd.read_parquet(self._prices_path)
        news["date"] = pd.to_datetime(news["date"], errors="coerce").dt.normalize()
        prices = self._standardize_price_columns(prices)
        prices["date"] = pd.to_datetime(prices["date"], errors="coerce").dt.normalize()
        prices["close"] = pd.to_numeric(prices["close"], errors="coerce")
        prices = prices.dropna(subset=["date", "ticker", "close"]).copy()

        price_pivot = prices.pivot(index="date", columns="ticker", values="close").sort_index()
        forward_returns = price_pivot.pct_change(periods=forward_return_days, fill_method=None).shift(-forward_return_days)

        labeled_rows: list[dict[str, Any]] = []
        for _, row in news.iterrows():
            ticker = str(row.get("ticker", "") or "").strip()
            headline = str(row.get("headline", row.get("text", "")) or "").strip()
            news_date = row.get("date")
            if not ticker or len(headline) < 10 or pd.isna(news_date):
                continue
            if ticker not in forward_returns.columns:
                continue
            try:
                realized = forward_returns.loc[news_date, ticker]
            except Exception:
                continue
            if pd.isna(realized):
                continue
            if realized >= self._positive_threshold:
                label = "positive"
                confidence = self._label_confidence
            elif realized <= self._negative_threshold:
                label = "negative"
                confidence = self._label_confidence
            else:
                label = "neutral"
                confidence = min(0.65, self._label_confidence - 0.10)
            labeled_rows.append(
                {
                    "text": headline,
                    "label": label,
                    "confidence": float(confidence),
                    "source": "auto_price_reaction",
                    "ticker": ticker,
                    "date": news_date,
                    "forward_return": float(realized),
                }
            )
        return pd.DataFrame(labeled_rows)

    def _build_teacher_scorer(self):
        from src.nlp.models.finbert_scorer import FinBERTScorer

        teacher_config = deepcopy(self._config)
        sentiment_cfg = teacher_config.setdefault("nlp", {}).setdefault("models", {}).setdefault("sentiment", {})
        sentiment_cfg["use_india_model_if_available"] = False
        return FinBERTScorer(teacher_config)

    def _score_with_teacher(self, texts: list[str]) -> dict[str, dict[str, float | str]]:
        unique_texts = list(dict.fromkeys(texts))
        scorer = self._build_teacher_scorer()
        scores = scorer.score_batch(unique_texts)
        return {
            score.text: {
                "label": score.predicted_label,
                "confidence": float(score.confidence),
                "polarity": float(score.polarity),
            }
            for score in scores
        }

    def _selection_score(self, row: pd.Series) -> float:
        teacher_conf = float(row.get("teacher_confidence", row.get("confidence", 0.0)) or 0.0)
        realized = abs(float(row.get("forward_return", 0.0) or 0.0))
        if str(row.get("label")) == "neutral":
            neutral_bonus = max(0.0, self._hq_neutral_abs_threshold - realized)
            return teacher_conf + neutral_bonus
        return teacher_conf + min(realized, 0.10)

    def _cap_examples_per_ticker(self, df: pd.DataFrame) -> pd.DataFrame:
        if self._max_examples_per_ticker_per_class <= 0 or df.empty:
            return df
        capped = (
            df.sort_values("selection_score", ascending=False)
            .groupby(["label", "ticker"], as_index=False, group_keys=False)
            .head(self._max_examples_per_ticker_per_class)
            .copy()
        )
        return capped

    @staticmethod
    def _normalize_text(text: str) -> str:
        normalized = re.sub(r"\s+", " ", str(text or "").lower()).strip()
        normalized = re.sub(r"[^a-z0-9% ]+", "", normalized)
        return normalized

    @staticmethod
    def _standardize_price_columns(prices: pd.DataFrame) -> pd.DataFrame:
        rename_map = {"Date": "date", "Close": "close", "ticker_symbol": "ticker", "Ticker": "ticker"}
        return prices.rename(columns={key: value for key, value in rename_map.items() if key in prices.columns})
