"""Validation tests for NS-USO sentiment bridge and integration."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.research.feature_factory import FeatureFactory
from src.signals.sentiment_bridge import SentimentBridge
from src.signals.sentiment_overlay import SentimentOverlay


SENTIMENT_FEATURES = [
    "sentiment_polarity",
    "sentiment_conviction",
    "sentiment_surprise",
    "sentiment_uncertainty",
    "sentiment_polarity_5d_ma",
    "sentiment_polarity_momentum",
    "sentiment_volume_spike",
    "sentiment_conviction_x_polarity",
]


def _prices_for_two_tickers() -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=14, freq="D")
    return pd.DataFrame(
        {
            "Date": list(dates) * 2,
            "ticker": ["AAA.NS"] * len(dates) + ["BBB.NS"] * len(dates),
            "Close": np.linspace(100.0, 110.0, len(dates)).tolist()
            + np.linspace(80.0, 96.0, len(dates)).tolist(),
            "Volume": [1000] * (2 * len(dates)),
        }
    )


def _write_sentiment_parquets(tmp_path: Path) -> tuple[Path, Path]:
    ticker_path = tmp_path / "ticker_sentiment_daily.parquet"
    market_path = tmp_path / "market_sentiment_daily.parquet"

    ticker_df = pd.DataFrame(
        {
            "ticker": ["AAA.NS", "BBB.NS", "AAA.NS", "BBB.NS"],
            "date": pd.to_datetime(["2024-01-01", "2024-01-01", "2024-01-05", "2024-01-05"]),
            "availability_date": pd.to_datetime(["2024-01-02", "2024-01-02", "2024-01-08", "2024-01-08"]),
            "sentiment_polarity": [0.2, -0.1, 0.6, -0.4],
            "sentiment_conviction": [0.5, 0.4, 0.8, 0.9],
            "sentiment_surprise": [0.3, 0.2, 0.7, 0.8],
            "sentiment_uncertainty": [0.5, 0.6, 0.2, 0.1],
            "news_volume": [5, 3, 10, 12],
            "source": ["news", "news", "news", "news"],
        }
    )
    market_df = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-01", "2024-01-05"]),
            "availability_date": pd.to_datetime(["2024-01-02", "2024-01-08"]),
            "india_market_polarity": [0.1, -0.5],
            "india_market_conviction": [0.5, 0.7],
            "india_market_uncertainty": [0.5, 0.3],
            "global_risk_sentiment": [0.0, -0.2],
            "news_volume_total": [20, 40],
        }
    )

    ticker_df.to_parquet(ticker_path, index=False)
    market_df.to_parquet(market_path, index=False)
    return ticker_path, market_path


def test_sentiment_bridge_initializes_without_error(tmp_path: Path) -> None:
    bridge = SentimentBridge(duckdb_path=str(tmp_path / "missing.duckdb"), output_dir=str(tmp_path / "out"))
    assert bridge.output_dir.exists()


def test_bridge_export_is_pit_safe_and_tickers_have_ns_suffix(tmp_path: Path) -> None:
    duckdb = pytest.importorskip("duckdb")
    db_path = tmp_path / "sentiment.duckdb"
    out_dir = tmp_path / "processed_sentiment"

    con = duckdb.connect(str(db_path))
    con.execute(
        """
        CREATE TABLE content_items (
            id INTEGER,
            metadata VARCHAR,
            published_at TIMESTAMP
        );
        """
    )
    con.execute(
        """
        CREATE TABLE sentiment_records (
            content_id INTEGER,
            polarity DOUBLE,
            conviction DOUBLE,
            surprise DOUBLE,
            uncertainty DOUBLE
        );
        """
    )
    con.execute(
        """
        CREATE TABLE aggregated_signals (
            generated_at TIMESTAMP,
            polarity DOUBLE,
            conviction DOUBLE,
            uncertainty DOUBLE,
            bias DOUBLE,
            market VARCHAR,
            asset_class VARCHAR
        );
        """
    )

    con.execute(
        "INSERT INTO content_items VALUES (1, '{\"ticker\":\"AAA\"}', '2024-01-03 10:00:00')"
    )
    con.execute(
        "INSERT INTO sentiment_records VALUES (1, 0.4, 0.7, 0.2, 0.3)"
    )
    con.execute(
        "INSERT INTO aggregated_signals VALUES ('2024-01-03 18:00:00', 0.2, 0.6, 0.4, 0.1, 'india', 'equities')"
    )
    con.close()

    bridge = SentimentBridge(duckdb_path=str(db_path), output_dir=str(out_dir))
    exports = bridge.export_all(start_date="2024-01-01")
    tdf = exports["ticker"]

    assert not tdf.empty
    assert (pd.to_datetime(tdf["availability_date"], errors="coerce") > pd.to_datetime(tdf["date"], errors="coerce")).all()
    assert tdf["ticker"].astype(str).str.endswith(".NS").all()


def test_feature_factory_adds_sentiment_features_when_enabled(tmp_path: Path) -> None:
    ticker_path, _ = _write_sentiment_parquets(tmp_path)
    prices = _prices_for_two_tickers()

    ff = FeatureFactory(
        config={
            "use_sentiment_features": True,
            "sentiment_path": str(ticker_path),
        }
    )
    panel = ff.build_features(prices=prices)

    for col in SENTIMENT_FEATURES:
        assert col in panel.columns
        assert f"{col}_cs_z" in panel.columns
        assert f"{col}_cs_rank" in panel.columns


def test_feature_factory_has_no_sentiment_features_when_flag_false(tmp_path: Path) -> None:
    ticker_path, _ = _write_sentiment_parquets(tmp_path)
    prices = _prices_for_two_tickers()

    ff = FeatureFactory(
        config={
            "use_sentiment_features": False,
            "sentiment_path": str(ticker_path),
        }
    )
    panel = ff.build_features(prices=prices)

    for col in SENTIMENT_FEATURES:
        assert col not in panel.columns


def test_sentiment_overlay_apply_returns_adjusted_score_and_bounds(tmp_path: Path) -> None:
    ticker_path, market_path = _write_sentiment_parquets(tmp_path)
    overlay = SentimentOverlay(
        {
            "sentiment_path": str(ticker_path),
            "market_sentiment_path": str(market_path),
        }
    )
    scores = pd.DataFrame({"ticker": ["AAA.NS", "BBB.NS"], "model_score": [1.0, 0.8]})

    out = overlay.apply(scores, as_of_date="2024-01-09")

    assert "adjusted_score" in out.columns
    assert (pd.to_numeric(out["adjusted_score"], errors="coerce") >= 0.0).all()
    assert (
        pd.to_numeric(out["adjusted_score"], errors="coerce")
        <= pd.to_numeric(out["model_score"], errors="coerce") * 1.5 + 1e-12
    ).all()


def test_market_negative_sentiment_reduces_all_multipliers(tmp_path: Path) -> None:
    ticker_path = tmp_path / "ticker_sentiment_daily.parquet"
    market_path = tmp_path / "market_sentiment_daily.parquet"

    pd.DataFrame(
        {
            "ticker": ["AAA.NS", "BBB.NS"],
            "date": pd.to_datetime(["2024-01-01", "2024-01-01"]),
            "availability_date": pd.to_datetime(["2024-01-02", "2024-01-02"]),
            "sentiment_polarity": [0.0, 0.05],
            "sentiment_conviction": [0.2, 0.2],
            "sentiment_surprise": [0.1, 0.1],
            "sentiment_uncertainty": [0.8, 0.8],
            "news_volume": [2, 2],
            "source": ["news", "news"],
        }
    ).to_parquet(ticker_path, index=False)

    pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-01"]),
            "availability_date": pd.to_datetime(["2024-01-02"]),
            "india_market_polarity": [-0.5],
            "india_market_conviction": [0.8],
            "india_market_uncertainty": [0.2],
            "global_risk_sentiment": [-0.2],
            "news_volume_total": [10],
        }
    ).to_parquet(market_path, index=False)

    overlay = SentimentOverlay(
        {
            "sentiment_path": str(ticker_path),
            "market_sentiment_path": str(market_path),
        }
    )
    scores = pd.DataFrame({"ticker": ["AAA.NS", "BBB.NS"], "model_score": [1.0, 1.0]})
    out = overlay.apply(scores, as_of_date="2024-01-03")

    assert np.allclose(pd.to_numeric(out["sentiment_multiplier"], errors="coerce"), 0.7)


def test_distress_override_sets_multiplier_zero(tmp_path: Path) -> None:
    ticker_path = tmp_path / "ticker_sentiment_daily.parquet"
    market_path = tmp_path / "market_sentiment_daily.parquet"

    pd.DataFrame(
        {
            "ticker": ["AAA.NS"],
            "date": pd.to_datetime(["2024-01-01"]),
            "availability_date": pd.to_datetime(["2024-01-02"]),
            "sentiment_polarity": [-0.8],
            "sentiment_conviction": [0.95],
            "sentiment_surprise": [0.9],
            "sentiment_uncertainty": [0.1],
            "news_volume": [20],
            "source": ["news"],
        }
    ).to_parquet(ticker_path, index=False)

    pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-01"]),
            "availability_date": pd.to_datetime(["2024-01-02"]),
            "india_market_polarity": [0.0],
            "india_market_conviction": [0.5],
            "india_market_uncertainty": [0.5],
            "global_risk_sentiment": [0.0],
            "news_volume_total": [10],
        }
    ).to_parquet(market_path, index=False)

    overlay = SentimentOverlay(
        {
            "sentiment_path": str(ticker_path),
            "market_sentiment_path": str(market_path),
        }
    )
    out = overlay.apply(pd.DataFrame({"ticker": ["AAA.NS"], "model_score": [1.0]}), as_of_date="2024-01-03")

    assert float(out.iloc[0]["sentiment_multiplier"]) == 0.0
    assert bool(out.iloc[0]["sentiment_override"]) is True
