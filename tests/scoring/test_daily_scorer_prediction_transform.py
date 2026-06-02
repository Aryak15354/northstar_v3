from __future__ import annotations

import numpy as np
import pandas as pd

from src.scoring.daily_scorer import DailyScorer


def _neutral_overlay(frame: pd.DataFrame, as_of_date=None) -> pd.DataFrame:
    _ = as_of_date
    return pd.DataFrame(
        {
            "ticker": frame["ticker"].astype(str),
            "sentiment_multiplier": np.ones(len(frame), dtype=float),
            "sentiment_override": np.zeros(len(frame), dtype=bool),
            "override_reason": [""] * len(frame),
            "sentiment_polarity": np.zeros(len(frame), dtype=float),
            "sentiment_conviction": np.zeros(len(frame), dtype=float),
            "news_volume": np.zeros(len(frame), dtype=float),
        }
    )


def test_cross_sectional_zscore_transform_centers_scores() -> None:
    scores = pd.Series([-4.0, -3.0, -1.0, 2.0], dtype=float)
    transformed = DailyScorer._apply_cross_sectional_prediction_transform(scores, mode="zscore")

    assert np.isclose(float(transformed.mean()), 0.0, atol=1e-12)
    assert np.isclose(float(transformed.std(ddof=0)), 1.0, atol=1e-12)
    assert transformed.sort_values().index.tolist() == scores.sort_values().index.tolist()


def test_cross_sectional_zscore_returns_zero_for_degenerate_cross_section() -> None:
    scores = pd.Series([0.75, 0.75, 0.75], dtype=float)
    transformed = DailyScorer._apply_cross_sectional_prediction_transform(scores, mode="zscore")

    assert transformed.eq(0.0).all()


def test_daily_scorer_recovers_positive_names_from_all_negative_raw_predictions(tmp_path) -> None:
    labels_path = tmp_path / "regime_labels.parquet"
    pd.DataFrame(
        {
            "date": pd.date_range("2025-01-01", periods=5, freq="D"),
            "regime": ["low_vol|uptrend|expansion"] * 5,
        }
    ).to_parquet(labels_path, index=False)

    scorer = DailyScorer(
        {
            "regime": {"regime_labels_path": str(labels_path)},
            "portfolio_mandate": "long_only",
            "prediction_transform": "zscore",
            "sentiment_overlay": {
                "sentiment_path": str(tmp_path / "missing_ticker_sentiment.parquet"),
                "market_sentiment_path": str(tmp_path / "missing_market_sentiment.parquet"),
                "macro_regime_path": str(tmp_path / "missing_macro.parquet"),
                "regime_labels_path": str(labels_path),
            },
        }
    )
    scorer.regime_engine.get_exposure_scale = lambda regime: 1.0
    scorer._load_latest_universe_frame = lambda dt, regime=None: (
        pd.DataFrame(
            {
                "ticker": [f"T{i}.NS" for i in range(4)],
                "sector": ["BANKS", "IT", "AUTO", "PHARMA"],
                "feature_1": [1.0, 2.0, 3.0, 4.0],
            }
        ),
        ["feature_1"],
    )
    scorer.overlay.apply = _neutral_overlay
    scorer._build_weights = lambda frame, exposure_scale, mandate, apply_turnover=True: pd.Series(
        np.where(frame["final_score"] > 0, 0.5, 0.0),
        index=frame.index,
        dtype=float,
    )
    scorer._save_prev_portfolio = lambda portfolio: None
    scorer.trainer.predict = lambda frame, regime=None: np.array([-4.0, -3.0, -2.0, -1.0], dtype=float)

    out = scorer.score("2025-01-03")

    assert out["raw_model_score"].lt(0).all()
    assert int((out["model_score"] > 0).sum()) == 2
    assert int((out["final_score"] > 0).sum()) == 2
