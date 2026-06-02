from __future__ import annotations

from pathlib import Path

import pandas as pd

from scripts.validate_sentiment_schemas import main as validate_sentiment_schemas_main
from src.ingestion.sentiment_loader import SentimentLoader


def _loader_config(company_path: Path, market_path: Path) -> dict:
    return {
        "ingestion": {
            "paths": {
                "company_sentiment_path": str(company_path),
                "market_sentiment_path": str(market_path),
            },
            "pit": {
                "enabled": True,
                "strict_mode": True,
            },
        }
    }


def test_loader_returns_empty_dataframe_with_correct_columns_when_schema_mismatch(tmp_path: Path) -> None:
    company_path = tmp_path / "company_sentiment_daily.parquet"
    market_path = tmp_path / "market_sentiment_daily.parquet"

    pd.DataFrame(
        {
            "ticker": ["RELIANCE.NS"],
            "date": [pd.Timestamp("2026-03-19")],
            "availability_date": [pd.Timestamp("2026-03-20")],
            "wrong_sentiment_column": [0.4],
            "sentiment_conviction": [0.8],
        }
    ).to_parquet(company_path, index=False)

    pd.DataFrame(
        {
            "date": [pd.Timestamp("2026-03-19")],
            "availability_date": [pd.Timestamp("2026-03-20")],
            "india_market_polarity": [0.1],
            "india_market_conviction": [0.7],
        }
    ).to_parquet(market_path, index=False)

    loader = SentimentLoader(_loader_config(company_path, market_path))
    out = loader.load_company_sentiment(pd.Timestamp("2026-03-21").to_pydatetime())

    assert out.empty
    assert list(out.index.names) == ["Ticker", "Date"]
    assert {"AvailabilityDate", "sentiment_polarity", "sentiment_conviction", "sentiment_score"}.issubset(out.columns)


def test_loader_does_not_use_heuristic_column_matching(tmp_path: Path) -> None:
    company_path = tmp_path / "company_sentiment_daily.parquet"
    market_path = tmp_path / "market_sentiment_daily.parquet"

    pd.DataFrame(
        {
            "ticker": ["INFY.NS"],
            "date": [pd.Timestamp("2026-03-19")],
            "availability_date": [pd.Timestamp("2026-03-20")],
            "headline_sentiment_score": [0.9],
            "sentiment_conviction": [0.5],
        }
    ).to_parquet(company_path, index=False)

    pd.DataFrame(
        {
            "date": [pd.Timestamp("2026-03-19")],
            "availability_date": [pd.Timestamp("2026-03-20")],
            "india_market_polarity": [0.1],
            "india_market_conviction": [0.7],
        }
    ).to_parquet(market_path, index=False)

    loader = SentimentLoader(_loader_config(company_path, market_path))
    out = loader.load_company_sentiment(pd.Timestamp("2026-03-21").to_pydatetime())

    assert out.empty
    assert "headline_sentiment_score" not in out.columns


def test_validate_sentiment_schemas_passes_against_current_canonical_files(monkeypatch) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    monkeypatch.chdir(repo_root)

    assert validate_sentiment_schemas_main() == 0
