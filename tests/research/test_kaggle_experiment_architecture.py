from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

import pandas as pd

from scripts.kaggle.week_2026_03_29.nb01_runner import (
    _preprocess,
    _resolve_registry_and_stage_dir,
    _runtime_regime_assets,
)
from scripts.kaggle.week_2026_03_29.run_weekly_suite import _build_stage_env, _build_suite_context
from src.research.compare_runs import compare
from src.research.config_loader import load_experiment_config
from src.research.experiment_logger import ExperimentLogger
from src.research.feature_filter import apply_dead_filter
from src.research.regime_assigner import RegimeAssigner
from src.research.reference_data import resolve_reference_root, validate_reference_bundle
from src.research.run_registry import RunRegistry


def _synthetic_windows(start: str = "2022-04-18", count: int = 20) -> list[dict[str, str]]:
    base = pd.Timestamp(start)
    windows: list[dict[str, str]] = []
    for idx in range(count):
        test_start = base + pd.Timedelta(weeks=13 * idx)
        test_end = test_start + pd.Timedelta(weeks=12)
        windows.append(
            {
                "window_id": idx + 1,
                "test_start": test_start.date().isoformat(),
                "test_end": test_end.date().isoformat(),
            }
        )
    return windows


def test_load_experiment_config_run_008_hydrates_model_and_regime_config() -> None:
    cfg = load_experiment_config("run_008")

    assert cfg["experiment"]["run_id"] == "v3_run_008_20260402"
    assert cfg["preprocessing"]["eps_sue_decay_ffill"] is True
    assert cfg["regime"]["version"] == "v2_tight_boundaries"
    assert cfg["models"]["catboost"]["depth"] == 4
    assert cfg["models"]["xgboost"]["objective"] == "reg:squarederror"
    assert cfg["_reference_bundle"]["status"] == "ok"
    assert "major_regime_xlsx" in cfg["_reference_bundle"]["document_sources"]


def test_regime_assigner_tight_boundaries_limit_r7_r8_windows() -> None:
    tight_cfg = load_experiment_config("run_008")["regime"]
    wide_cfg = load_experiment_config("run_007")["regime"]
    windows = _synthetic_windows()

    tight_labels = RegimeAssigner(tight_cfg).assign_all_windows(windows)
    wide_labels = RegimeAssigner(wide_cfg).assign_all_windows(windows)

    tight_count = sum(label in {"R7|Rate-Event", "R8|Election/Binary"} for label in tight_labels)
    wide_count = sum(label in {"R7|Rate-Event", "R8|Election/Binary"} for label in wide_labels)

    assert tight_count <= 5
    assert wide_count > 8


def test_experiment_logger_lifecycle_writes_valid_summary(tmp_path: Path) -> None:
    cfg = load_experiment_config("run_008")
    logger = ExperimentLogger("v3_run_test_001", cfg, output_root=tmp_path)

    for window_id in range(1, 21):
        logger.log_window(window_id, "catboost", 0.05, 0.02, 2.5, 0.55, "R1|Low-Vol Bull")
    logger.log_model_summary("catboost", 0.02, 0.60, 2.5, 0.55, "PROMOTE", windows_completed=20)
    logger.log_regime_breakdown("catboost", {"R1|Low-Vol Bull": {"mean_ic": 0.02, "n_windows": 20}}, 0.02, 0.60, 20)
    logger.log_deployment([{"window": 1, "exposure": 0.40}], 0.40, 8, 0)
    summary = logger.finalize("B_PROMOTE_LIMITED", "catboost")

    assert summary["run_id"] == "v3_run_test_001"
    assert (tmp_path / "v3_run_test_001" / "summary.json").exists()
    assert (tmp_path / "v3_run_test_001" / "full_log.json").exists()
    assert (tmp_path / "v3_run_test_001" / "window_events.jsonl").exists()
    assert json.loads((tmp_path / "v3_run_test_001" / "summary.json").read_text())["verdict"] == "B_PROMOTE_LIMITED"
    assert json.loads((tmp_path / "v3_run_test_001" / "full_log.json").read_text())["models"]["catboost"]["mean_ic"] == 0.02
    assert json.loads((tmp_path / "v3_run_test_001" / "summary.json").read_text())["windows_above_20pct"] == 8


def test_run_registry_writes_stage_status_and_artifacts(tmp_path: Path) -> None:
    cfg = load_experiment_config("run_008")
    registry = RunRegistry("v3_run_registry_test", cfg=cfg, output_root=tmp_path)
    registry.initialize(cfg)
    registry.mark_stage_started("nb01", command=["python3", "nb01_runner.py"])
    registry.mark_stage_completed("nb01", metadata={"verdict": "B_INVESTIGATE"})
    artifact_path = tmp_path / "artifact.json"
    artifact_path.write_text("{}")
    registry.register_artifact("nb01", "payload", artifact_path)

    stage_status = json.loads((tmp_path / "v3_run_registry_test" / "stage_status.json").read_text())
    assert stage_status["stages"]["nb01"]["status"] == "completed"
    assert stage_status["artifacts"]["nb01"]["payload"]["path"] == str(artifact_path.resolve())


def test_apply_dead_filter_keeps_supported_feature_and_removes_dead_feature() -> None:
    features_df = pd.DataFrame(
        {
            "date": pd.date_range("2024-01-05", periods=12, freq="W-FRI").repeat(2),
            "ticker": ["AAA.NS", "BBB.NS"] * 12,
            "target_weekly_return": [0.01, -0.01] * 12,
            "good_feature": [1.0, 2.0] * 12,
            "weak_but_real": [0.1, None] * 12,
            "dead_feature": [None] * 24,
        }
    )
    feature_health = pd.DataFrame(
        [
            {"feature": "good_feature", "mean_ic": 0.03, "ic_tstat": 2.0, "tier": "TIER_1"},
            {"feature": "weak_but_real", "mean_ic": 0.004, "ic_tstat": 2.1, "tier": "TIER_2"},
            {"feature": "dead_feature", "mean_ic": 0.0, "ic_tstat": 0.1, "tier": "NOISE"},
        ]
    )
    cfg = load_experiment_config("run_008")

    result = apply_dead_filter(features_df, ["good_feature", "weak_but_real", "dead_feature"], cfg, feature_health=feature_health)

    assert "good_feature" in result.selected_features
    assert "weak_but_real" in result.selected_features
    assert "weak_but_real" in result.protected_features
    assert "dead_feature" in result.removed_features


def test_nb01_preprocess_forward_fills_sparse_eps_sue_and_adds_flag() -> None:
    dates = pd.date_range("2024-01-05", periods=20, freq="W-FRI")
    left_values = [1.0 if idx % 2 == 0 else None for idx in range(20)]
    right_values = [None] + [2.0 if idx % 2 == 1 else None for idx in range(1, 20)]
    df = pd.DataFrame(
        {
            "date": list(dates) + list(dates),
            "ticker": ["AAA.NS"] * 20 + ["BBB.NS"] * 20,
            "eps_sue_decay": left_values + right_values,
        }
    )
    cfg = load_experiment_config("run_008")

    before_null_rate = float(pd.to_numeric(df["eps_sue_decay"], errors="coerce").isna().mean())
    processed, derived, audit = _preprocess(df, cfg)
    after_null_rate = float(pd.to_numeric(processed["eps_sue_decay"], errors="coerce").isna().mean())

    assert before_null_rate == 0.5
    assert after_null_rate < 0.05
    assert "eps_sue_decay_raw_available" in derived
    assert audit[0]["coverage_after"] > audit[0]["coverage_before"]
    bbb = processed[processed["ticker"] == "BBB.NS"].reset_index(drop=True)
    assert bbb.loc[0, "eps_sue_decay_raw_available"] == 0.0
    assert bbb.loc[1, "eps_sue_decay_raw_available"] == 1.0


def test_runtime_regime_assets_apply_yaml_window_labels_and_caps() -> None:
    cfg = load_experiment_config("run_008")
    splits = _synthetic_windows()
    dates = pd.date_range("2022-04-01", "2026-06-30", freq="W-FRI")
    regime_frame = pd.DataFrame(
        {
            "date": dates,
            "plan_regime_id": ["R6"] * len(dates),
            "plan_regime_label": ["Sideways"] * len(dates),
            "regime": ["R6|Sideways"] * len(dates),
        }
    )

    runtime_splits, runtime_regimes, audit = _runtime_regime_assets(splits, regime_frame, cfg)

    assert len(runtime_splits) == 20
    assert all("regime" in split for split in runtime_splits)
    assert all("regime_cap" in split for split in runtime_splits)
    assert audit["r7_r8_count"] <= 5
    assert "window_id" in runtime_regimes.columns


def test_regime_assigner_prefers_export_regime_frame_over_event_midpoint_override() -> None:
    cfg = load_experiment_config("run_008")
    assigner = RegimeAssigner(cfg["regime"])
    splits = _synthetic_windows(start="2023-09-01", count=20)
    dates = pd.date_range("2023-09-01", "2026-03-31", freq="W-FRI")
    regime_frame = pd.DataFrame(
        {
            "date": dates,
            "plan_regime_id": ["R6"] * len(dates),
            "plan_regime_label": ["Sideways"] * len(dates),
            "regime": ["R6|Sideways"] * len(dates),
        }
    )
    regime_frame.loc[regime_frame["date"].between("2024-05-31", "2024-06-14"), "plan_regime_id"] = "R8"
    regime_frame.loc[regime_frame["date"].between("2024-05-31", "2024-06-14"), "plan_regime_label"] = "Election/Binary"
    regime_frame.loc[regime_frame["date"].between("2024-05-31", "2024-06-14"), "regime"] = "R8|Election/Binary"

    labels = assigner.assign_all_windows(splits, regime_frame=regime_frame)

    r7_r8_count = sum(label in {"R7|Rate-Event", "R8|Election/Binary"} for label in labels)
    assert r7_r8_count <= 1


def test_nb01_output_dir_resolution_keeps_single_run_root(tmp_path: Path) -> None:
    cfg = load_experiment_config("run_008")
    registry, stage_dir = _resolve_registry_and_stage_dir(
        "v3_run_008_20260402",
        cfg,
        tmp_path / "nb01",
        stage_name="nb01",
    )

    assert registry.run_dir == tmp_path / "v3_run_008_20260402"
    assert stage_dir == tmp_path / "v3_run_008_20260402" / "nb01"


def test_reference_bundle_uses_actual_manual_inputs() -> None:
    root = resolve_reference_root(required=True)
    audit = validate_reference_bundle(root, strict=True, expected_universe_size=500)

    assert audit["universe_ticker_count"] >= 500
    assert audit["major_regime_events_rows"] >= 20
    assert "major_regime_xlsx" in audit["document_sources"]
    assert "weekly_sprint_docx" in audit["document_sources"]
    assert "research_plan_docx" in audit["document_sources"]
    assert "universe_master_xlsx" in audit["document_sources"]
    assert "universe_master_csv" in audit["document_sources"]


def test_weekly_suite_stage_env_inherits_run_and_reference_context(tmp_path: Path) -> None:
    cfg = load_experiment_config("run_008")
    registry = RunRegistry("v3_run_008_20260402", cfg=cfg, output_root=tmp_path)
    suite_root = registry.initialize(cfg)
    args = Namespace(profile="smoke", run_id="run_008")

    suite_context = _build_suite_context(args=args, suite_root=suite_root, registry=registry, cfg=cfg)
    env = _build_stage_env(step_name="nb03", suite_context=suite_context)

    assert env["NORTHSTAR_RUN_ID"] == "v3_run_008_20260402"
    assert env["NORTHSTAR_STAGE_NAME"] == "nb03"
    assert env["NORTHSTAR_CONFIG_SNAPSHOT"].endswith("config_snapshot.yaml")
    assert env["NORTHSTAR_REFERENCE_ROOT"].endswith("data/canonical/reference")
    assert env["NORTHSTAR_REFERENCE_MANIFEST"].endswith("research_inputs_manifest.json")


def test_compare_runs_renders_side_by_side_table(tmp_path: Path) -> None:
    runs_root = tmp_path / "runs"
    for run_id, ic in [("v3_run_007_20260331", 0.019), ("v3_run_008_20260402", 0.024)]:
        run_dir = runs_root / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "summary.json").write_text(
            json.dumps(
                {
                    "run_id": run_id,
                    "verdict": "B_INVESTIGATE",
                    "best_model": "catboost",
                    "catboost": {"mean_ic": ic, "ic_ir": 0.58, "train_test_ratio": 2.9},
                    "xgboost": {"mean_ic": 0.01, "ic_ir": 0.30},
                    "lightgbm": {"mean_ic": 0.011, "ic_ir": 0.31},
                    "mean_exposure": 0.22,
                    "windows_above_20pct": 8,
                    "regime_config_version": "v2_tight_boundaries",
                    "duration_minutes": 11.5,
                }
            )
        )

    table = compare(["v3_run_007_20260331", "v3_run_008_20260402"], runs_root=runs_root)
    assert "CatBoost mean IC" in table
    assert "Regime cfg" in table
    assert "v3_run_008_20260402" in table
    assert "0.0240" in table
