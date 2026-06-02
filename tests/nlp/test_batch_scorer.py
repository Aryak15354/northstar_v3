from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.nlp.pipeline.batch_scorer import BatchHistoricalScorer


def _config() -> dict:
    return {
        "nlp": {
            "models": {"sentiment": {"device": "cpu", "batch_size": 8, "max_length": 128}},
            "pipeline": {"availability_lag_hours": 2, "min_headline_length": 10, "max_headline_length": 256, "min_confidence": 0.55},
        }
    }


def test_score_incremental_writes_canonical_and_processed_outputs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    company_news_path = Path("data/canonical/news/company_news_history.parquet")
    market_news_path = Path("data/canonical/news/market_news_history.parquet")
    company_news_path.parent.mkdir(parents=True, exist_ok=True)
    market_news_path.parent.mkdir(parents=True, exist_ok=True)

    pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-03-20 09:00:00", "2026-03-20 10:00:00"]),
            "availability_date": pd.to_datetime(["2026-03-20 11:00:00", "2026-03-20 12:00:00"]),
            "ticker": ["INFY.NS", "RELIANCE.NS"],
            "headline": ["Infosys beats Q3 estimates, revenue rises 15%", "Promoter arrested for fraud allegation"],
            "source": ["rss", "rss"],
        }
    ).to_parquet(company_news_path, index=False)
    pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-03-20 09:15:00"]),
            "availability_date": pd.to_datetime(["2026-03-20 11:15:00"]),
            "headline": ["RBI raises repo rate by 25 basis points"],
            "source": ["rss"],
        }
    ).to_parquet(market_news_path, index=False)

    existing_company = Path("data/canonical/sentiment/company_sentiment_daily.parquet")
    existing_company.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "ticker": ["INFY.NS"],
            "date": pd.to_datetime(["2026-03-19"]),
            "availability_date": pd.to_datetime(["2026-03-20"]),
            "sentiment_polarity": [0.1],
            "sentiment_conviction": [0.4],
            "news_volume": [1],
            "source": ["legacy"],
            "sentiment_surprise": [0.0],
            "sentiment_uncertainty": [0.6],
            "headline_count": [1],
            "dominant_event_type": ["neutral_corporate"],
            "dominant_event_direction": ["neutral"],
            "market_moving_count": [0],
            "nlp_model_version": ["legacy"],
        }
    ).to_parquet(existing_company, index=False)

    scorer = BatchHistoricalScorer(_config())
    outputs = scorer.score_incremental(since_date="2026-03-20")

    company_out = pd.read_parquet("data/canonical/sentiment/company_sentiment_daily.parquet")
    company_processed = pd.read_parquet("data/processed/sentiment/ticker_sentiment_daily.parquet")
    market_out = pd.read_parquet("data/canonical/sentiment/market_sentiment_daily.parquet")
    market_processed = pd.read_parquet("data/processed/sentiment/market_sentiment_daily.parquet")

    assert not outputs["company"].empty
    assert not outputs["market"].empty
    assert {"headline_count", "dominant_event_type", "nlp_model_version"}.issubset(company_out.columns)
    assert {"dominant_shock_type", "shock_severity_numeric", "shock_confidence"}.issubset(market_out.columns)
    assert len(company_out[company_out["date"] == pd.Timestamp("2026-03-20")]) == 2
    assert company_processed.equals(company_out)
    assert market_processed.equals(market_out)


def test_score_incremental_replaces_same_day_keys_without_duplicates(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    company_news_path = Path("data/canonical/news/company_news_history.parquet")
    market_news_path = Path("data/canonical/news/market_news_history.parquet")
    company_news_path.parent.mkdir(parents=True, exist_ok=True)
    market_news_path.parent.mkdir(parents=True, exist_ok=True)

    base_company = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-03-20 09:00:00"]),
            "availability_date": pd.to_datetime(["2026-03-20 11:00:00"]),
            "ticker": ["INFY.NS"],
            "headline": ["Infosys beats Q3 estimates, revenue rises 15%"],
            "source": ["rss"],
        }
    )
    base_company.to_parquet(company_news_path, index=False)
    pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-03-20 09:15:00"]),
            "availability_date": pd.to_datetime(["2026-03-20 11:15:00"]),
            "headline": ["RBI raises repo rate by 25 basis points"],
            "source": ["rss"],
        }
    ).to_parquet(market_news_path, index=False)

    scorer = BatchHistoricalScorer(_config())
    scorer.score_incremental(since_date="2026-03-20")

    updated_company = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-03-20 09:00:00", "2026-03-20 11:00:00"]),
            "availability_date": pd.to_datetime(["2026-03-20 11:00:00", "2026-03-20 13:00:00"]),
            "ticker": ["INFY.NS", "INFY.NS"],
            "headline": ["Infosys beats Q3 estimates, revenue rises 15%", "Infosys wins large banking transformation deal"],
            "source": ["rss", "rss"],
        }
    )
    updated_company.to_parquet(company_news_path, index=False)
    scorer.score_incremental(since_date="2026-03-20")

    company_out = pd.read_parquet("data/canonical/sentiment/company_sentiment_daily.parquet")
    same_day = company_out[company_out["date"] == pd.Timestamp("2026-03-20")]
    assert len(same_day[same_day["ticker"] == "INFY.NS"]) == 1


def test_score_company_news_history_writes_daily_checkpoint_without_headline_accumulation(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    company_news_path = Path("data/canonical/news/company_news_history.parquet")
    company_news_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-03-20 09:00:00", "2026-03-21 09:00:00"]),
            "ticker": ["INFY.NS", "RELIANCE.NS"],
            "headline": ["Infosys beats Q3 estimates, revenue rises 15%", "Promoter arrested for fraud allegation"],
            "source": ["rss", "rss"],
        }
    ).to_parquet(company_news_path, index=False)

    scorer = BatchHistoricalScorer(_config())
    daily = scorer.score_company_news_history(checkpoint_every=1, resume_from_checkpoint=False)

    assert len(daily) == 2
    assert Path("data/nlp/cache/company_daily_checkpoint.parquet").exists()
    progress = Path("data/nlp/cache/company_daily_progress.json").read_text()
    assert '"next_start": 2' in progress
    assert Path("data/canonical/sentiment/company_sentiment_daily.parquet").exists()


def test_score_market_news_history_writes_daily_checkpoint(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    market_news_path = Path("data/canonical/news/market_news_history.parquet")
    market_news_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-03-20 09:15:00", "2026-03-21 10:30:00"]),
            "headline": ["RBI raises repo rate by 25 basis points", "Brent crude jumps 9% after supply disruption fears"],
            "source": ["rss", "rss"],
        }
    ).to_parquet(market_news_path, index=False)

    scorer = BatchHistoricalScorer(_config())
    daily = scorer.score_market_news_history(checkpoint_every=1, resume_from_checkpoint=False)

    assert len(daily) == 2
    assert Path("data/nlp/cache/market_daily_checkpoint.parquet").exists()
    progress = Path("data/nlp/cache/market_daily_progress.json").read_text()
    assert '"next_start": 2' in progress
    assert Path("data/canonical/sentiment/market_sentiment_daily.parquet").exists()
