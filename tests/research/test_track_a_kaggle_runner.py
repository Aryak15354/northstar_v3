from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
SHARED_DIR = ROOT / "notebooks" / "kaggle_sprint" / "shared"
if str(SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_DIR))

from sprint_utils import FactorICAnalyzer, SectorICAnalyzer, SprintDataLoader, SprintWalkForward  # noqa: E402
from track_a_runner import TrackARunConfig, TrackARunner, run_track_a_notebook  # noqa: E402


def _build_synthetic_export(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    dates = pd.date_range("2022-01-07", periods=11, freq="W-FRI")
    tickers = [f"TICKER_{idx:02d}" for idx in range(12)]
    sectors = ["FIN", "TECH", "INDIA"]
    rows: list[dict] = []

    for date_idx, date in enumerate(dates):
        for ticker_idx, ticker in enumerate(tickers):
            base = 0.15 * date_idx + 0.08 * ticker_idx
            cyc = np.sin(date_idx / 2.0) + np.cos(ticker_idx / 3.0)
            noise = ((ticker_idx % 3) - 1) * 0.01
            earnings_quality = 0.35 * base + 0.10 * cyc + noise
            momentum = 0.20 * cyc - 0.05 * ticker_idx
            target = 0.45 * earnings_quality - 0.20 * momentum + 0.03 * np.sin(date_idx + ticker_idx)
            rows.append(
                {
                    "date": date,
                    "ticker": ticker,
                    "sector": sectors[ticker_idx % len(sectors)],
                    "target_weekly_return": target,
                    "forward_return_5d": target,
                    "earnings_quality_signal": earnings_quality,
                    "pledge_signal": -0.10 * base + 0.05 * cyc,
                    "bulk_signal": 0.07 * base - 0.03 * cyc,
                    "fii_flow_signal": 0.04 * date_idx + 0.01 * ticker_idx,
                    "fii_pressure_signal": 0.03 * date_idx - 0.02 * ticker_idx,
                    "sue_signal": 0.11 * cyc + 0.02 * ticker_idx,
                    "power_consumption_lag": 0.05 * base + 0.03 * date_idx,
                    "piotroski_signal": 0.06 * base + 0.02 * cyc,
                    "bab_signal": -0.04 * base + 0.02 * cyc,
                    "amihud_signal": 0.09 * ticker_idx - 0.02 * date_idx,
                    "max_ret_20d": 0.13 * cyc + 0.01 * ticker_idx,
                }
            )

    features_df = pd.DataFrame(rows)
    features_df.to_parquet(root / "northstar_features.parquet", index=False)

    metadata_df = features_df[["date", "ticker", "target_weekly_return"]].copy()
    metadata_df["broad_sector"] = metadata_df["ticker"].map(
        lambda ticker: "BANKS" if str(ticker).endswith(("00", "01", "02", "03")) else "TECH"
    )
    metadata_df["fii_pct"] = np.linspace(5.0, 15.0, len(metadata_df))
    metadata_df["power_yoy_growth"] = np.linspace(0.1, 0.9, len(metadata_df))
    metadata_df.to_parquet(root / "northstar_metadata.parquet", index=False)

    splits = []
    for offset, window_id in enumerate((1, 2, 3), start=0):
        splits.append(
            {
                "window_id": window_id,
                "train_start": str(dates[offset].date()),
                "train_end": str(dates[offset + 5].date()),
                "test_start": str(dates[offset + 6].date()),
                "test_end": str(dates[offset + 6].date()),
            }
        )
    (root / "northstar_walk_forward_splits.json").write_text(json.dumps(splits, indent=2), encoding="utf-8")

    regime_df = pd.DataFrame(
        {
            "date": dates,
            "regime": ["bull"] * 6 + ["bear"] * 5,
        }
    )
    regime_df.to_parquet(root / "northstar_regime_labels.parquet", index=False)
    return root


def test_sprint_walk_forward_resumes_from_checkpoint(tmp_path):
    data_dir = _build_synthetic_export(tmp_path / "export")
    loader = SprintDataLoader()
    features_df, splits, regime_df = loader.load(data_dir)
    feature_names = loader.get_feature_names(features_df)
    engine = SprintWalkForward()
    calls: list[int] = []

    def model_factory(X_train, y_train, X_test, feature_names, config):
        calls.append(int(config["window_id"]))
        return X_train[:, 0], X_test[:, 0], np.ones(len(feature_names), dtype=float)

    config = {"output_dir": str(tmp_path / "output"), "resume_from_checkpoint": True}
    first = engine.run("SmokeModel", model_factory, features_df, splits, regime_df, feature_names, config)
    second = engine.run("SmokeModel", model_factory, features_df, splits, regime_df, feature_names, config)

    assert len(first["windows"]) == 3
    assert len(second["windows"]) == 3
    assert calls == [1, 2, 3]


def test_track_a_runner_smoke_profile_skips_day1_and_finishes(tmp_path):
    data_dir = _build_synthetic_export(tmp_path / "export")
    output_dir = tmp_path / "results"
    config = TrackARunConfig(
        data_dir=data_dir,
        output_dir=output_dir,
        skip_days={1},
        continue_on_error=True,
        resume_from_checkpoint=True,
        run_profile="smoke",
        max_splits=3,
    )

    state = run_track_a_notebook(config)
    combined = json.loads((output_dir / "track_a_classical_full_results.json").read_text(encoding="utf-8"))

    assert state["run_summary"]["day_status"]["day1"]["status"] == "skipped"
    assert combined["run_state"]["day_status"]["day7"]["status"] == "completed"
    assert "day1_ic_table" in combined
    assert "day7_verdict" in combined
    assert "all_model_stabilities" in combined
    assert (output_dir / "track_a_promotion_memo.md").exists()

    expected_model_artifacts = [
        "xgboost_final.json",
        "lightgbm_final.json",
        "catboost_final.json",
        "lstm_final.json",
        "gru_final.json",
        "tcn_final.json",
        "transformer_final.json",
    ]
    for filename in expected_model_artifacts:
        payload = json.loads((output_dir / filename).read_text(encoding="utf-8"))
        assert "summary" in payload
        assert "stability" in payload
        assert "windows" in payload


def test_group_relevance_labels_clip_to_lgbm_safe_range():
    y_values = np.linspace(-1.0, 1.0, 64, dtype=float)
    labels = TrackARunner._to_group_relevance_labels(y_values, [32, 32])

    assert labels.dtype == np.int32
    assert int(labels.min()) == 0
    assert int(labels.max()) <= 30


def test_group_rank_percentiles_stay_in_unit_interval():
    labels = TrackARunner._to_group_rank_percentiles(np.linspace(-1.0, 1.0, 6), [3, 3])

    assert labels.dtype == np.float32
    assert float(labels.min()) >= 0.0
    assert float(labels.max()) <= 1.0
    assert labels.tolist() == [0.0, 0.5, 1.0, 0.0, 0.5, 1.0]


def test_decay_check_ignores_dead_zero_ic_features():
    dates = pd.to_datetime(
        ["2022-12-16"] * 10
        + ["2022-12-23"] * 10
        + ["2023-01-06"] * 10
        + ["2023-01-13"] * 10
    )
    tickers = [f"T{idx:02d}" for idx in range(10)] * 4
    target = np.tile(np.linspace(-1.0, 1.0, 10), 4)
    decaying = np.concatenate(
        [
            np.linspace(-1.0, 1.0, 10),
            np.linspace(-0.8, 0.8, 10),
            np.array([0.0, 1.0] * 5, dtype=float),
            np.array([1.0, 0.0] * 5, dtype=float),
        ]
    )
    features_df = pd.DataFrame(
        {
            "date": dates,
            "ticker": tickers,
            "target_weekly_return": target,
            "dead_feature": np.zeros(len(dates), dtype=float),
            "decaying_feature": decaying,
        }
    )

    decay_df = FactorICAnalyzer().decay_check(
        features_df,
        ["dead_feature", "decaying_feature"],
        split_date="2023-01-01",
    ).set_index("feature")

    assert bool(decay_df.loc["dead_feature", "decay_alert"]) is False
    assert np.isnan(float(decay_df.loc["dead_feature", "decay_ratio"]))
    assert bool(decay_df.loc["decaying_feature", "decay_alert"]) is True


def test_sector_ic_analyzer_falls_back_to_broad_sector():
    dates = pd.to_datetime(["2024-01-05"] * 20 + ["2024-01-12"] * 20)
    tickers = [f"T{idx:02d}" for idx in range(20)] * 2
    sectors = (["BANKS"] * 10 + ["TECH"] * 10) * 2
    feature_signal = np.tile(np.linspace(-1.0, 1.0, 20), 2)
    target = feature_signal * 0.5 + np.tile(np.linspace(-0.2, 0.2, 20), 2)
    features_df = pd.DataFrame(
        {
            "date": dates,
            "ticker": tickers,
            "broad_sector": sectors,
            "target_weekly_return": target,
            "quality_signal": feature_signal,
        }
    )

    sector_df = SectorICAnalyzer().compute(features_df, ["quality_signal"])

    assert not sector_df.empty
    assert set(sector_df["sector"]) == {"BANKS", "TECH"}


def test_sprint_data_loader_merges_metadata_without_expanding_model_feature_set(tmp_path):
    data_dir = _build_synthetic_export(tmp_path / "export")
    loader = SprintDataLoader()
    features_df, _, _ = loader.load(data_dir)
    feature_names = loader.get_feature_names(features_df)

    assert "broad_sector" in features_df.columns
    assert "fii_pct" in features_df.columns
    assert "power_yoy_growth" in features_df.columns
    assert "broad_sector" not in feature_names
    assert "fii_pct" not in feature_names
    assert "power_yoy_growth" not in feature_names


def test_sprint_data_loader_honors_model_feature_manifest(tmp_path):
    data_dir = _build_synthetic_export(tmp_path / "export")
    (data_dir / "northstar_model_feature_names.json").write_text('["earnings_quality_signal","pledge_signal"]', encoding="utf-8")

    loader = SprintDataLoader()
    features_df, _, _ = loader.load(data_dir)
    feature_names = loader.get_feature_names(features_df)

    assert feature_names == ["earnings_quality_signal", "pledge_signal"]
