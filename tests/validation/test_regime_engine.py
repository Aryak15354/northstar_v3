"""Validation tests for regime engine cohesion components."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from src.research.regime_conditional_trainer import RegimeConditionalTrainer
from src.research.regime_engine import RegimeEngine
from src.scoring.daily_scorer import DailyScorer


def _synthetic_prices(start: str = "2024-01-01", periods: int = 720) -> pd.DataFrame:
    dates = pd.date_range(start, periods=periods, freq="D")
    rng = np.random.default_rng(42)
    rets = np.zeros(periods, dtype=float)
    segments = [
        (0, periods // 4, 0.0012, 0.004),
        (periods // 4, periods // 2, -0.0010, 0.018),
        (periods // 2, 3 * periods // 4, -0.0005, 0.005),
        (3 * periods // 4, periods, 0.0008, 0.020),
    ]
    for a, b, mu, sigma in segments:
        rets[a:b] = rng.normal(mu, sigma, size=max(0, b - a))
    close = 100.0 * np.cumprod(1.0 + rets)
    return pd.DataFrame({"date": dates, "NIFTY 50": close})


def _trainer_frame(
    *,
    n_neutral: int = 600,
    n_expansion: int = 120,
    seed: int = 7,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n = int(n_neutral + n_expansion)
    f1 = rng.normal(0.0, 1.0, size=n)
    f2 = rng.normal(0.0, 1.0, size=n)
    y = (0.35 * f1) - (0.18 * f2) + rng.normal(0.0, 0.10, size=n)
    regimes = (["low_vol|uptrend|neutral"] * n_neutral) + (["low_vol|uptrend|expansion"] * n_expansion)
    return pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=n, freq="D"),
            "ticker": [f"T{i:04d}" for i in range(n)],
            "f1": f1,
            "f2": f2,
            "target": y,
            "regime": regimes,
        }
    )


def test_regime_engine_produces_one_label_per_date_with_no_gaps() -> None:
    prices = _synthetic_prices(periods=540)
    engine = RegimeEngine(config={})
    labels = engine.build_historical_regimes(prices_df=prices, macro_df=None)

    expected_dates = pd.date_range(labels["date"].min(), labels["date"].max(), freq="D")
    got_dates = pd.DatetimeIndex(pd.to_datetime(labels["date"], errors="coerce"))

    assert len(labels) == len(prices)
    assert labels["date"].isna().sum() == 0
    assert labels["date"].duplicated().sum() == 0
    assert labels["regime"].astype(str).str.strip().ne("").all()
    assert len(got_dates) == len(expected_dates)
    assert np.array_equal(got_dates.to_numpy(), expected_dates.to_numpy())


def test_regime_engine_is_pit_safe_for_macro_availability() -> None:
    prices = _synthetic_prices(start="2024-01-01", periods=180)
    macro_df = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-01", "2024-02-01", "2024-03-01", "2024-04-01"]),
            "availability_date": pd.to_datetime(["2024-01-31", "2024-03-02", "2024-03-31", "2024-05-01"]),
            "macro_a": [1.0, 2.0, 1.4, 2.2],
            "macro_b": [3.0, 2.5, 3.3, 2.8],
        }
    )
    engine = RegimeEngine(config={"regime_pca_min_periods": 5})
    labels = engine.build_historical_regimes(prices_df=prices, macro_df=macro_df)

    pre_first_avail = labels[pd.to_datetime(labels["date"], errors="coerce") < pd.Timestamp("2024-01-31")]
    post_window = labels[pd.to_datetime(labels["date"], errors="coerce") >= pd.Timestamp("2024-03-20")]

    assert pre_first_avail["macro_activity_score"].isna().all()
    assert post_window["macro_activity_score"].notna().any()


def test_get_exposure_scale_bounds_for_valid_regimes() -> None:
    engine = RegimeEngine(config={})
    vals = [float(engine.get_exposure_scale(r)) for r in sorted(engine.EXPOSURE_MAP.keys())]
    vals += [float(engine.get_exposure_scale(r)) for r in sorted(engine.BASE_FALLBACK_NEUTRAL.keys())]
    assert all(0.1 <= v <= 1.0 for v in vals)


def test_regime_conditional_trainer_falls_back_to_base_regime_when_sparse(tmp_path: Path) -> None:
    model_dir = tmp_path / "regime_models"
    panel = _trainer_frame(n_neutral=620, n_expansion=140)
    trainer = RegimeConditionalTrainer(config={"min_obs_per_regime": 500}, model_dir=str(model_dir))
    _ = trainer.train_all_regimes(panel, feature_cols=["f1", "f2"], target_col="target", regime_col="regime")

    registry = json.loads((model_dir / "regime_model_registry.json").read_text())
    rec = registry["models"]["low_vol|uptrend|expansion"]
    assert rec["trained_on_regime"] == "low_vol|uptrend"
    assert rec["fallback_base"] == "low_vol|uptrend"


def test_daily_scorer_output_has_required_columns(tmp_path: Path) -> None:
    model_dir = tmp_path / "models"
    panel = _trainer_frame(n_neutral=620, n_expansion=50)
    trainer = RegimeConditionalTrainer(config={"min_obs_per_regime": 500}, model_dir=str(model_dir))
    trainer.train_all_regimes(panel, feature_cols=["f1", "f2"], target_col="target", regime_col="regime")

    labels_path = tmp_path / "regime_labels.parquet"
    pd.DataFrame(
        {
            "date": pd.date_range("2025-01-01", periods=20, freq="D"),
            "regime": ["low_vol|uptrend|neutral"] * 20,
        }
    ).to_parquet(labels_path, index=False)

    def _loader(as_of_date: pd.Timestamp) -> tuple[pd.DataFrame, list[str]]:
        _ = as_of_date
        frame = pd.DataFrame(
            {
                "ticker": [f"S{i:03d}.NS" for i in range(25)],
                "sector": ["BANKS"] * 10 + ["IT"] * 15,
                "f1": np.linspace(-1.0, 1.0, 25),
                "f2": np.linspace(1.0, -1.0, 25),
            }
        )
        return frame, ["f1", "f2"]

    scorer = DailyScorer(
        {
            "regime": {"regime_labels_path": str(labels_path)},
            "trainer": {"model_dir": str(model_dir), "min_obs_per_regime": 500},
            "data_loader": _loader,
            "portfolio_mandate": "long_only",
            "sentiment_overlay": {
                "sentiment_path": str(tmp_path / "missing_ticker_sentiment.parquet"),
                "market_sentiment_path": str(tmp_path / "missing_market_sentiment.parquet"),
                "macro_regime_path": str(tmp_path / "missing_macro.parquet"),
                "regime_labels_path": str(labels_path),
            },
        }
    )
    out = scorer.score("2025-01-10")
    required = {
        "ticker",
        "raw_model_score",
        "model_score",
        "regime",
        "sentiment_multiplier",
        "final_score",
        "suggested_weight",
        "quintile",
    }
    assert required.issubset(set(out.columns))
    assert not out.empty


def test_morning_pipeline_runs_without_error_on_synthetic_data(tmp_path: Path, monkeypatch, capsys) -> None:
    import scripts.run_morning_pipeline as morning

    class _FakeDailyScorer:
        def __init__(self, config: dict | None = None):
            self.config = dict(config or {})

        def score(self, as_of_date: object) -> pd.DataFrame:
            _ = as_of_date
            return pd.DataFrame(
                {
                    "ticker": ["AAA.NS", "BBB.NS", "CCC.NS"],
                    "model_score": [0.8, 0.6, -0.2],
                    "regime": ["low_vol|uptrend|expansion"] * 3,
                    "sentiment_multiplier": [1.0, 0.9, 0.0],
                    "final_score": [0.8, 0.54, 0.0],
                    "suggested_weight": [0.5, 0.5, 0.0],
                    "quintile": [5, 4, 1],
                    "sector": ["BANKS", "IT", "AUTO"],
                    "sentiment_override": [False, False, True],
                    "override_reason": ["", "", "strong_negative_sentiment"],
                }
            )

        def get_last_info(self) -> dict:
            return {
                "regime": "low_vol|uptrend|expansion",
                "exposure_scale": 1.0,
                "model_meta": {
                    "model_path": "models/regime_models/regime_low_vol_uptrend_expansion.pkl",
                    "train_ic": 0.0412,
                    "oos_ic": 0.0184,
                },
            }

    cfg = tmp_path / "research_policy.yaml"
    cfg.write_text("historical_research: {}\n")

    monkeypatch.setattr(morning, "DailyScorer", _FakeDailyScorer)
    monkeypatch.setattr(
        sys,
        "argv",
        ["run_morning_pipeline.py", "--date", "2025-01-10", "--config", str(cfg)],
    )

    rc = morning.main()
    stdout = capsys.readouterr().out
    assert rc == 0
    assert "Northstar v3 Morning Pipeline" in stdout
    assert "Current Regime" in stdout


def test_regime_distribution_sanity_no_single_regime_exceeds_sixty_percent() -> None:
    prices = _synthetic_prices(periods=720)
    engine = RegimeEngine(config={})
    labels = engine.build_historical_regimes(prices_df=prices, macro_df=None)
    max_share = float(labels["regime"].astype(str).value_counts(normalize=True).max())
    assert max_share < 0.60
