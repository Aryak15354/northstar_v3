"""Batch and incremental historical scoring for the NLP sentiment system."""

from __future__ import annotations

import gc
import json
import logging
import math
from datetime import datetime
from datetime import date as dt_date
from pathlib import Path
from typing import Any

import pandas as pd

from src.nlp.pipeline.aggregator import aggregate_company_daily, aggregate_market_daily, merge_daily_frames
from src.nlp.pipeline.news_nlp_pipeline import NewsNLPPipeline

logger = logging.getLogger(__name__)

try:
    from tqdm.auto import tqdm
except Exception:  # pragma: no cover - tqdm is optional at runtime
    tqdm = None


class BatchHistoricalScorer:
    """Scores historical news and writes canonical + processed sentiment artifacts."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self._config = config or {}
        self._pipeline: NewsNLPPipeline | None = None

    def _get_pipeline(self) -> NewsNLPPipeline:
        if self._pipeline is None:
            self._pipeline = NewsNLPPipeline(self._config)
        return self._pipeline

    def score_company_news_history(
        self,
        input_path: str = "data/canonical/news/company_news_history.parquet",
        output_path: str = "data/canonical/sentiment/company_sentiment_daily.parquet",
        checkpoint_every: int | None = None,
        resume_from_checkpoint: bool = True,
    ) -> pd.DataFrame:
        news = self._standardize_columns(pd.read_parquet(input_path))
        daily = self._score_company_daily_in_batches(
            news,
            checkpoint_every=checkpoint_every or self._historical_chunk_size(),
            resume_from_checkpoint=resume_from_checkpoint,
        )
        self._write_company_outputs(daily, canonical_output=output_path)
        return daily

    def score_market_news_history(
        self,
        input_path: str = "data/canonical/news/market_news_history.parquet",
        output_path: str = "data/canonical/sentiment/market_sentiment_daily.parquet",
        checkpoint_every: int | None = None,
        resume_from_checkpoint: bool = True,
    ) -> pd.DataFrame:
        news = self._standardize_columns(pd.read_parquet(input_path), require_ticker=False)
        daily = self._score_market_daily_in_batches(
            news,
            checkpoint_every=checkpoint_every or self._historical_chunk_size(),
            resume_from_checkpoint=resume_from_checkpoint,
        )
        self._write_market_outputs(daily, canonical_output=output_path)
        return daily

    def score_incremental(
        self,
        since_date: dt_date | datetime | str,
        company_input_path: str = "data/canonical/news/company_news_history.parquet",
        market_input_path: str = "data/canonical/news/market_news_history.parquet",
        company_output_path: str = "data/canonical/sentiment/company_sentiment_daily.parquet",
        market_output_path: str = "data/canonical/sentiment/market_sentiment_daily.parquet",
    ) -> dict[str, pd.DataFrame]:
        since_ts = pd.Timestamp(since_date).normalize()
        company_news = self._standardize_columns(pd.read_parquet(company_input_path))
        company_slice = company_news[pd.to_datetime(company_news["date"], errors="coerce").dt.normalize() >= since_ts].copy()
        market_news = self._standardize_columns(pd.read_parquet(market_input_path), require_ticker=False)
        market_slice = market_news[pd.to_datetime(market_news["date"], errors="coerce").dt.normalize() >= since_ts].copy()

        company_daily = pd.DataFrame()
        if not company_slice.empty:
            company_scored = self._get_pipeline().process_batch(company_slice, text_col="headline", ticker_col="ticker", date_col="date", source_col="source")
            company_daily = aggregate_company_daily(company_scored)
            existing_company = self._read_parquet_if_exists(company_output_path)
            merged_company = merge_daily_frames(existing_company, company_daily, ["ticker", "date"])
            self._write_company_outputs(merged_company, canonical_output=company_output_path)
            company_daily = merged_company

        market_daily = pd.DataFrame()
        if not market_slice.empty:
            market_scored = self._get_pipeline().process_batch(market_slice, text_col="headline", ticker_col="ticker", date_col="date", source_col="source")
            market_daily = aggregate_market_daily(market_scored)
            existing_market = self._read_parquet_if_exists(market_output_path)
            merged_market = merge_daily_frames(existing_market, market_daily, ["date"])
            self._write_market_outputs(merged_market, canonical_output=market_output_path)
            market_daily = merged_market

        return {"company": company_daily, "market": market_daily}

    def _score_company_daily_in_batches(
        self,
        news_df: pd.DataFrame,
        *,
        checkpoint_every: int,
        resume_from_checkpoint: bool,
    ) -> pd.DataFrame:
        if news_df.empty:
            return aggregate_company_daily(pd.DataFrame())
        pipeline = self._get_pipeline()
        checkpoint_path = Path("data/nlp/cache/company_daily_checkpoint.parquet")
        progress_path = Path("data/nlp/cache/company_daily_progress.json")
        work = news_df.reset_index(drop=True)
        daily = self._read_parquet_if_exists(str(checkpoint_path)) if resume_from_checkpoint else pd.DataFrame()
        start_offset = self._load_progress(progress_path).get("next_start", 0) if resume_from_checkpoint else 0
        start_offset = min(int(start_offset), len(work))

        if not resume_from_checkpoint:
            self._clear_checkpoint_files(checkpoint_path, progress_path)

        total = len(work)
        progress = self._build_progress_bar(
            total=total,
            start_offset=start_offset,
            checkpoint_every=checkpoint_every,
            desc="Company NLP",
        )
        self._log_batch_plan(
            label="company",
            total=total,
            start_offset=start_offset,
            checkpoint_every=checkpoint_every,
            checkpoint_path=checkpoint_path,
            progress_path=progress_path,
            existing_daily_rows=len(daily),
        )
        for start in range(start_offset, total, checkpoint_every):
            batch = work.iloc[start : start + checkpoint_every].copy()
            if batch.empty:
                continue
            logger.info("Scoring NLP batch rows %s-%s of %s", start, min(start + checkpoint_every, total), total)
            scored = pipeline.process_batch(batch, text_col="headline", ticker_col="ticker", date_col="date", source_col="source")
            batch_daily = aggregate_company_daily(scored)
            daily = merge_daily_frames(daily, batch_daily, ["ticker", "date"]) if not daily.empty else batch_daily
            daily = self._refresh_company_daily_features(daily)
            checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
            daily.to_parquet(checkpoint_path, index=False)
            self._save_progress(progress_path, next_start=start + len(batch), total=total)
            self._update_progress_bar(
                progress,
                advance=len(batch),
                processed=min(start + len(batch), total),
                total=total,
                daily_rows=len(daily),
                checkpoint_path=checkpoint_path,
            )
            self._flush_pipeline_memory()
            del batch, scored, batch_daily
            gc.collect()
        self._save_progress(progress_path, next_start=total, total=total)
        self._close_progress_bar(progress)
        logger.info(
            "Company NLP scoring complete: processed=%s rows, daily_rows=%s, checkpoint=%s",
            total,
            len(daily),
            checkpoint_path,
        )
        return self._refresh_company_daily_features(daily)

    def _score_market_daily_in_batches(
        self,
        news_df: pd.DataFrame,
        *,
        checkpoint_every: int,
        resume_from_checkpoint: bool,
    ) -> pd.DataFrame:
        if news_df.empty:
            return aggregate_market_daily(pd.DataFrame())
        pipeline = self._get_pipeline()
        checkpoint_path = Path("data/nlp/cache/market_daily_checkpoint.parquet")
        progress_path = Path("data/nlp/cache/market_daily_progress.json")
        work = news_df.reset_index(drop=True)
        daily = self._read_parquet_if_exists(str(checkpoint_path)) if resume_from_checkpoint else pd.DataFrame()
        start_offset = self._load_progress(progress_path).get("next_start", 0) if resume_from_checkpoint else 0
        start_offset = min(int(start_offset), len(work))

        if not resume_from_checkpoint:
            self._clear_checkpoint_files(checkpoint_path, progress_path)

        total = len(work)
        progress = self._build_progress_bar(
            total=total,
            start_offset=start_offset,
            checkpoint_every=checkpoint_every,
            desc="Market NLP",
        )
        self._log_batch_plan(
            label="market",
            total=total,
            start_offset=start_offset,
            checkpoint_every=checkpoint_every,
            checkpoint_path=checkpoint_path,
            progress_path=progress_path,
            existing_daily_rows=len(daily),
        )
        for start in range(start_offset, total, checkpoint_every):
            batch = work.iloc[start : start + checkpoint_every].copy()
            if batch.empty:
                continue
            logger.info("Scoring market NLP batch rows %s-%s of %s", start, min(start + checkpoint_every, total), total)
            scored = pipeline.process_batch(batch, text_col="headline", ticker_col="ticker", date_col="date", source_col="source")
            batch_daily = aggregate_market_daily(scored)
            daily = merge_daily_frames(daily, batch_daily, ["date"]) if not daily.empty else batch_daily
            checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
            daily.to_parquet(checkpoint_path, index=False)
            self._save_progress(progress_path, next_start=start + len(batch), total=total)
            self._update_progress_bar(
                progress,
                advance=len(batch),
                processed=min(start + len(batch), total),
                total=total,
                daily_rows=len(daily),
                checkpoint_path=checkpoint_path,
            )
            self._flush_pipeline_memory()
            del batch, scored, batch_daily
            gc.collect()
        self._save_progress(progress_path, next_start=total, total=total)
        self._close_progress_bar(progress)
        logger.info(
            "Market NLP scoring complete: processed=%s rows, daily_rows=%s, checkpoint=%s",
            total,
            len(daily),
            checkpoint_path,
        )
        return daily.sort_values(["date"], kind="mergesort").reset_index(drop=True) if not daily.empty else daily

    def _write_company_outputs(self, daily: pd.DataFrame, *, canonical_output: str) -> None:
        canonical_path = Path(canonical_output)
        processed_path = Path("data/processed/sentiment/ticker_sentiment_daily.parquet")
        canonical_path.parent.mkdir(parents=True, exist_ok=True)
        processed_path.parent.mkdir(parents=True, exist_ok=True)
        daily.to_parquet(canonical_path, index=False)
        daily.to_parquet(processed_path, index=False)

    def _write_market_outputs(self, daily: pd.DataFrame, *, canonical_output: str) -> None:
        canonical_path = Path(canonical_output)
        processed_path = Path("data/processed/sentiment/market_sentiment_daily.parquet")
        canonical_path.parent.mkdir(parents=True, exist_ok=True)
        processed_path.parent.mkdir(parents=True, exist_ok=True)
        daily.to_parquet(canonical_path, index=False)
        daily.to_parquet(processed_path, index=False)

    def _standardize_columns(self, df: pd.DataFrame, *, require_ticker: bool = True) -> pd.DataFrame:
        rename_map = {
            "text": "headline",
            "title": "headline",
            "news": "headline",
            "symbol": "ticker",
            "published": "date",
            "timestamp": "date",
            "provider": "source",
            "publisher": "source",
        }
        work = df.rename(columns={key: value for key, value in rename_map.items() if key in df.columns}).copy()
        if "headline" not in work.columns:
            raise ValueError(f"Missing headline column in news frame: {list(work.columns)}")
        if "date" not in work.columns:
            raise ValueError(f"Missing date column in news frame: {list(work.columns)}")
        if "source" not in work.columns:
            work["source"] = "unknown"
        if require_ticker and "ticker" not in work.columns:
            work["ticker"] = None
        elif "ticker" not in work.columns:
            work["ticker"] = None
        work["date"] = pd.to_datetime(work["date"], errors="coerce")
        if "availability_date" not in work.columns:
            work["availability_date"] = work["date"] + pd.offsets.BDay(1)
        work = work.dropna(subset=["date", "headline"]).copy()
        work["headline"] = work["headline"].astype(str)
        return work[work["headline"].str.len() >= 10].copy()

    def _historical_chunk_size(self) -> int:
        configured = self._config.get("nlp", {}).get("pipeline", {}).get("historical_chunk_size", 1000)
        return max(100, int(configured))

    @staticmethod
    def _refresh_company_daily_features(daily: pd.DataFrame) -> pd.DataFrame:
        if daily is None or daily.empty:
            return aggregate_company_daily(pd.DataFrame())
        refreshed = daily.copy()
        refreshed["date"] = pd.to_datetime(refreshed["date"], errors="coerce")
        refreshed = refreshed.sort_values(["ticker", "date"], kind="mergesort").reset_index(drop=True)
        refreshed["sentiment_uncertainty"] = (
            1.0 - pd.to_numeric(refreshed["sentiment_conviction"], errors="coerce").fillna(0.0)
        ).clip(0.0, 1.0)
        refreshed["sentiment_surprise"] = (
            refreshed.groupby("ticker")["sentiment_polarity"].transform(
                lambda series: series - series.rolling(20, min_periods=5).mean()
            )
        ).fillna(0.0)
        return refreshed

    @staticmethod
    def _load_progress(path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    @staticmethod
    def _save_progress(path: Path, *, next_start: int, total: int) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"next_start": int(next_start), "total": int(total)}, indent=2), encoding="utf-8")

    @staticmethod
    def _clear_checkpoint_files(*paths: Path) -> None:
        for path in paths:
            try:
                path.unlink()
            except FileNotFoundError:
                continue

    def _flush_pipeline_memory(self) -> None:
        finbert = getattr(self._get_pipeline(), "_finbert", None)
        if finbert is not None and hasattr(finbert, "flush_cache"):
            finbert.flush_cache()

    @staticmethod
    def _build_progress_bar(*, total: int, start_offset: int, checkpoint_every: int, desc: str):
        if tqdm is None:
            return None
        remaining = max(0, int(total) - int(start_offset))
        total_batches = math.ceil(remaining / max(1, int(checkpoint_every))) if remaining else 0
        return tqdm(
            total=max(1, total) if total else 1,
            initial=min(start_offset, total),
            desc=desc,
            unit="headline",
            mininterval=1.0,
            smoothing=0.05,
            dynamic_ncols=True,
            leave=True,
            disable=(total <= 0),
            bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]",
            postfix={"batches": total_batches},
        )

    @staticmethod
    def _update_progress_bar(progress, *, advance: int, processed: int, total: int, daily_rows: int, checkpoint_path: Path) -> None:
        if progress is None:
            return
        progress.update(advance)
        progress.set_postfix(
            {
                "processed": f"{processed}/{total}",
                "daily_rows": daily_rows,
                "ckpt": checkpoint_path.name,
            },
            refresh=False,
        )

    @staticmethod
    def _close_progress_bar(progress) -> None:
        if progress is not None:
            progress.close()

    @staticmethod
    def _log_batch_plan(
        *,
        label: str,
        total: int,
        start_offset: int,
        checkpoint_every: int,
        checkpoint_path: Path,
        progress_path: Path,
        existing_daily_rows: int,
    ) -> None:
        remaining = max(0, total - start_offset)
        batches = math.ceil(remaining / max(1, checkpoint_every)) if remaining else 0
        resume_mode = "resume" if start_offset > 0 else "fresh"
        logger.info(
            "%s NLP %s run: total_rows=%s, start_offset=%s, remaining_rows=%s, batch_size=%s, remaining_batches=%s, checkpoint=%s, progress=%s, daily_rows_cached=%s",
            label.capitalize(),
            resume_mode,
            total,
            start_offset,
            remaining,
            checkpoint_every,
            batches,
            checkpoint_path,
            progress_path,
            existing_daily_rows,
        )

    @staticmethod
    def _read_parquet_if_exists(path: str) -> pd.DataFrame:
        file_path = Path(path)
        if not file_path.exists():
            return pd.DataFrame()
        return pd.read_parquet(file_path)
