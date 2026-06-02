from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

import scripts.kaggle.week_2026_03_29.common as weekly_common
from scripts.kaggle.export_weekly_raw_inputs import kaggle_safe_relative_path
from scripts.kaggle.week_2026_03_29.build_weekly_feature_export import _effective_split_config
from scripts.kaggle.week_2026_03_29.build_weekly_feature_export import _profile_overrides
from scripts.kaggle.week_2026_03_29.build_weekly_feature_export import _dataset_runtime_config
from scripts.kaggle.week_2026_03_29.build_weekly_feature_export import _validate_raw_bundle_support_artifacts
import scripts.kaggle.week_2026_03_29.nb01_fixed_baselines as nb01_module
from scripts.kaggle.week_2026_03_29.nb01_fixed_baselines import parse_args as parse_nb01_args
from scripts.kaggle.week_2026_03_29.nb01_fixed_baselines import _augment_training_features
from scripts.kaggle.week_2026_03_29.nb01_fixed_baselines import _drop_redundant_momentum_variants
from scripts.kaggle.week_2026_03_29.nb01_fixed_baselines import _ensure_nb00_report
from scripts.kaggle.week_2026_03_29.nb01_fixed_baselines import _force_include_training_features
from scripts.kaggle.week_2026_03_29.nb01_fixed_baselines import _prune_dead_features
from scripts.kaggle.week_2026_03_29.common import (
    MODEL_FEATURE_MANIFEST,
    build_feature_coverage_audit,
    build_feature_unit_registry,
    derive_size_rank,
    infer_feature_unit_kind,
    load_export_artifacts,
    prepare_runtime_project,
    resolve_export_dir,
    select_feature_columns,
    subset_feature_export,
)


def test_infer_feature_unit_kind_handles_screener_units_explicitly():
    assert infer_feature_unit_kind("screener_sales") == "absolute_scale"
    assert infer_feature_unit_kind("screener_roce_pct") == "percentage_points"
    assert infer_feature_unit_kind("screener_pat_growth_1y") == "percentage_points"
    assert infer_feature_unit_kind("screener_cfo_to_pat") == "ratio"
    assert infer_feature_unit_kind("screener_debtor_days") == "days"
    assert infer_feature_unit_kind("screener_eps_in_rs") == "inr_per_share"
    assert infer_feature_unit_kind("earnings_quality_ratio_cs_z") == "standardized_score"


def test_select_feature_columns_excludes_raw_absolute_features_from_model_export():
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-01-02", "2026-01-02"]),
            "ticker": ["AAA.NS", "BBB.NS"],
            "target_weekly_return": [0.1, -0.1],
            "revenue": [1000.0, 1200.0],
            "native_revenue": [1000.0, 1200.0],
            "screener_sales": [500.0, 600.0],
            "screener_eps_in_rs": [12.0, 15.0],
            "screener_roce_pct": [18.0, 14.0],
            "screener_pat_growth_1y": [22.0, 19.0],
            "screener_cfo_to_pat": [1.2, 0.9],
            "screener_debtor_days": [45.0, 60.0],
            "earnings_quality_ratio_cs_z": [0.5, -0.2],
            "market_cap_rank": [0.8, 0.2],
        }
    )

    selected = select_feature_columns(frame)

    assert "revenue" not in selected
    assert "native_revenue" not in selected
    assert "screener_sales" not in selected
    assert "screener_eps_in_rs" not in selected
    assert "screener_roce_pct" in selected
    assert "screener_pat_growth_1y" in selected
    assert "screener_cfo_to_pat" in selected
    assert "screener_debtor_days" in selected
    assert "earnings_quality_ratio_cs_z" in selected

    registry = build_feature_unit_registry(frame)
    registry_by_feature = {row["feature"]: row for row in registry}

    assert registry_by_feature["screener_roce_pct"]["unit_kind"] == "percentage_points"
    assert registry_by_feature["screener_cfo_to_pat"]["unit_kind"] == "ratio"
    assert registry_by_feature["screener_debtor_days"]["unit_kind"] == "days"
    assert registry_by_feature["earnings_quality_ratio_cs_z"]["model_safe"] is True


def test_dataset_runtime_config_carries_effective_dataset_limits():
    payload = _dataset_runtime_config(
        policy_path=Path("/tmp/research_policy.yaml"),
        start_date="2018-01-01",
        end_date="2026-03-31",
        lookback_days=480,
        max_tickers=30,
        max_rows=30000,
        low_resource_mode="true",
        profile="smoke",
    )

    assert payload["lookback_days"] == 480
    assert payload["max_tickers"] == 30
    assert payload["max_rows"] == 30000
    assert payload["low_resource_mode"] == "true"
    assert payload["start_date"] == "2018-01-01"
    assert payload["end_date"] == "2026-03-31"
    assert payload["feature_pit_enforce"] is False
    assert len(payload["feature_pit_lags"]) > 0
    assert payload["feature_budget_enforce"] is False
    assert payload["feature_correlation_skip"] is True


def test_smoke_profile_overrides_disable_redundant_screener_rebuild():
    class Args:
        profile = "smoke"
        lookback_days = 3200
        max_tickers = 0
        max_rows = 0

    overrides = _profile_overrides(Args())

    assert overrides["lookback_days"] == 480
    assert overrides["max_tickers"] == 30
    assert overrides["max_rows"] == 30000
    assert overrides["low_resource_mode"] == "true"
    assert overrides["rebuild_screener"] == "false"


def test_effective_split_config_shrinks_windows_when_history_is_short():
    weekly_dates = pd.date_range("2025-01-03", periods=69, freq="W-FRI").tolist()
    config = _effective_split_config(
        weekly_dates,
        train_weeks=104,
        test_weeks=13,
        step_weeks=13,
        target_windows=20,
    )

    assert config["adjusted"] is True
    assert config["available_dates"] == 69
    assert int(config["train_weeks"]) + int(config["test_weeks"]) <= 69
    assert int(config["step_weeks"]) <= int(config["test_weeks"])
    assert int(config["target_windows"]) >= 1


def test_derive_size_rank_falls_back_to_close_when_market_cap_rank_missing():
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-01-02", "2026-01-02", "2026-01-09"]),
            "ticker": ["AAA.NS", "BBB.NS", "AAA.NS"],
            "close": [100.0, 200.0, 110.0],
        }
    )

    rank = derive_size_rank(frame)

    assert len(rank) == 3
    assert float(rank.iloc[0]) == 0.5
    assert float(rank.iloc[1]) == 1.0
    assert float(rank.iloc[2]) == 1.0


def test_validate_raw_bundle_support_artifacts_fails_fast_for_stale_bundle(tmp_path: Path):
    (tmp_path / "data" / "processed").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "processed" / "market_state.parquet").write_text("stub", encoding="utf-8")

    with pytest.raises(FileNotFoundError, match="weekly_raw_bundle_incomplete"):
        _validate_raw_bundle_support_artifacts(tmp_path)


def test_kaggle_safe_relative_path_sanitizes_unsafe_raw_filenames():
    assert str(kaggle_safe_relative_path(Path("data/raw/forex/USDINR=X.csv"))) == "data/raw/forex/USDINR_x3d_X.csv"
    assert (
        str(kaggle_safe_relative_path(Path("data/raw/vendors/screener/financials/M&M_annual_pl.csv")))
        == "data/raw/vendors/screener/financials/M_x26_M_annual_pl.csv"
    )


def test_prepare_runtime_project_copies_writable_tree_on_kaggle(tmp_path: Path, monkeypatch):
    raw_bundle = tmp_path / "bundle"
    source_file = raw_bundle / "data" / "canonical" / "fundamentals" / "fundamentals_annual_panel.csv"
    source_file.parent.mkdir(parents=True, exist_ok=True)
    source_file.write_text("ticker,value\nAAA.NS,1\n", encoding="utf-8")
    (raw_bundle / "universe").mkdir(parents=True, exist_ok=True)
    (raw_bundle / "config").mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr("scripts.kaggle.week_2026_03_29.common.is_kaggle", lambda: True)

    runtime_root = prepare_runtime_project(raw_bundle, tmp_path / "runtime")
    staged_file = runtime_root / "data" / "canonical" / "fundamentals" / "fundamentals_annual_panel.csv"

    assert staged_file.exists()
    assert not (runtime_root / "data").is_symlink()
    staged_file.write_text("ticker,value\nAAA.NS,2\n", encoding="utf-8")
    assert "2" in staged_file.read_text(encoding="utf-8")


def test_build_feature_coverage_audit_flags_dead_features():
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-01-02"] * 3 + ["2026-01-09"] * 3),
            "ticker": ["AAA.NS", "BBB.NS", "CCC.NS"] * 2,
            "alive_feature": [1.0, 2.0, 3.0, 1.5, 2.5, 3.5],
            "dead_feature": [1.0] * 6,
            "mostly_null_feature": [1.0, None, None, None, None, None],
        }
    )

    audit = build_feature_coverage_audit(frame, ["alive_feature", "dead_feature", "mostly_null_feature"]).set_index("feature")

    assert bool(audit.loc["alive_feature", "likely_dead"]) is False
    assert bool(audit.loc["dead_feature", "likely_dead"]) is True
    assert "low_unique_values" in str(audit.loc["dead_feature", "dead_reason"])
    assert bool(audit.loc["mostly_null_feature", "likely_dead"]) is True
    assert "high_null_rate" in str(audit.loc["mostly_null_feature", "dead_reason"])


def test_repair_dead_quality_factor_families_uses_live_valuation_proxies():
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-01-02", "2026-01-02", "2026-01-09", "2026-01-09"]),
            "ticker": ["AAA.NS", "BBB.NS", "AAA.NS", "BBB.NS"],
            "earnings_quality_ratio": [0.0, 0.0, 0.0, 0.0],
            "earnings_quality_ratio_cs_z": [0.0, 0.0, 0.0, 0.0],
            "earnings_quality_ratio_cs_rank": [0.001, 0.001, 0.001, 0.001],
            "accruals_ratio": [0.0, 0.0, 0.0, 0.0],
            "accruals_ratio_cs_z": [0.0, 0.0, 0.0, 0.0],
            "accruals_ratio_cs_rank": [0.0, 0.0, 0.0, 0.0],
            "val_earnings_quality_score_zscore": [0.8, -0.3, 0.6, -0.4],
            "val_accruals_ratio_zscore": [-0.7, 0.2, -0.5, 0.4],
        }
    )

    repaired, repairs = weekly_common.repair_dead_quality_factor_families(frame)

    assert repaired["earnings_quality_ratio_cs_z"].nunique(dropna=True) > 1
    assert repaired["earnings_quality_ratio_cs_rank"].abs().max() > 0.0
    assert repaired["accruals_ratio_cs_z"].nunique(dropna=True) > 1
    assert repaired["accruals_ratio_cs_rank"].abs().max() > 0.0
    assert {row["family"] for row in repairs} == {"earnings_quality_ratio", "accruals_ratio"}


def test_repair_missing_revision_factor_family_derives_live_revision_columns():
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(
                [
                    "2026-01-02",
                    "2026-01-09",
                    "2026-01-16",
                    "2026-01-23",
                    "2026-01-30",
                    "2026-02-06",
                    "2026-02-13",
                    "2026-02-20",
                ]
            ),
            "ticker": ["AAA.NS"] * 8,
            "eps_sue": [0.1, 0.1, 0.3, 0.3, 0.9, 0.9, 1.8, 1.8],
            "rev_sue": [0.05, 0.05, 0.15, 0.15, 0.4, 0.4, 0.8, 0.8],
        }
    )

    repaired, repairs = weekly_common.repair_missing_revision_factor_families(frame)

    assert "eps_revision_accel" in repaired.columns
    assert "combined_revision_score_cs_z" in repaired.columns
    assert repaired["combined_revision_score"].notna().sum() > 0
    assert repaired["combined_revision_score_cs_rank"].notna().sum() > 0
    assert repairs and repairs[0]["family"] == "eps_revision"


def test_prune_dead_features_keeps_sparse_feature_with_real_ic_signal():
    coverage = pd.DataFrame(
        [
            {"feature": "eps_sue_decay_cs_z", "likely_dead": True},
            {"feature": "truly_dead_feature", "likely_dead": True},
            {"feature": "alive_feature", "likely_dead": False},
        ]
    )
    health = pd.DataFrame(
        [
            {"feature": "eps_sue_decay_cs_z", "mean_ic": 0.0047, "ic_tstat": 3.35, "tier": "TIER_2"},
            {"feature": "truly_dead_feature", "mean_ic": 0.0001, "ic_tstat": 0.2, "tier": "NOISE"},
        ]
    )

    kept, removed, protected = _prune_dead_features(
        ["eps_sue_decay_cs_z", "truly_dead_feature", "alive_feature"],
        coverage,
        health,
        disable_filter=False,
        min_abs_ic=0.002,
        min_abs_tstat=1.5,
    )

    assert "eps_sue_decay_cs_z" in kept
    assert "eps_sue_decay_cs_z" in protected
    assert "truly_dead_feature" in removed
    assert "alive_feature" in kept


def test_nb01_cli_defaults_match_track_a_catboost_defaults(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "sys.argv",
        [
            "nb01_fixed_baselines.py",
            "--export-dir",
            "/tmp/export",
        ],
    )

    args = parse_nb01_args()

    assert args.catboost_depth == 4
    assert args.catboost_min_leaf == 40
    assert args.catboost_l2 == 15.0
    assert args.catboost_iterations == 800


def test_drop_redundant_momentum_variants_keeps_canonical_signals():
    kept, dropped = _drop_redundant_momentum_variants(
        [
            "res_mom_5d",
            "res_mom_5d_cs_rank",
            "res_mom_5d_cs_z",
            "ret_5d",
            "ret_5d_cs_rank",
            "other_feature",
        ]
    )

    assert kept == ["res_mom_5d", "ret_5d", "other_feature"]
    assert dropped == ["res_mom_5d_cs_rank", "res_mom_5d_cs_z", "ret_5d_cs_rank"]


def test_force_include_training_features_adds_india_diagnostics_when_present():
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-01-02"]),
            "ticker": ["AAA.NS"],
            "target_weekly_return": [0.01],
            "eps_sue_decay": [0.4],
            "screener_fii_pct": [12.0],
            "val_earnings_quality_score_zscore": [0.2],
        }
    )

    combined, forced = _force_include_training_features(["ret_5d"], frame)

    assert combined == ["ret_5d", "val_earnings_quality_score_zscore", "eps_sue_decay", "screener_fii_pct"]
    assert forced == ["val_earnings_quality_score_zscore", "eps_sue_decay", "screener_fii_pct"]


def test_augment_training_features_derives_fii_interaction_from_raw_inputs():
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-01-02"]),
            "ticker": ["AAA.NS"],
            "target_weekly_return": [0.01],
            "screener_fii_pct": [10.0],
            "screener_fii_change_1q": [0.2],
        }
    )

    augmented, derived = _augment_training_features(frame)

    assert derived == ["fii_interaction"]
    assert float(augmented.loc[0, "fii_interaction"]) == pytest.approx(2.0)


def test_ensure_nb00_report_autogenerates_when_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    export_dir = tmp_path / "00_export"
    export_dir.mkdir(parents=True, exist_ok=True)
    output_dir = tmp_path / "02_nb01"
    output_dir.mkdir(parents=True, exist_ok=True)

    def fake_run(cmd, cwd=None, check=None):
        autogen_dir = output_dir.parent / "01_nb00_autogen"
        autogen_dir.mkdir(parents=True, exist_ok=True)
        (autogen_dir / "feature_health_report.json").write_text('{"tier_lists":{"TIER_1":[],"TIER_2":[]}}', encoding="utf-8")
        return None

    monkeypatch.setattr(nb01_module.subprocess, "run", fake_run)

    report = _ensure_nb00_report(export_dir, output_dir / "missing.json", output_dir)

    assert report == (output_dir.parent / "01_nb00_autogen" / "feature_health_report.json").resolve()


def test_subset_feature_export_writes_model_feature_manifest(tmp_path: Path):
    source_dir = tmp_path / "source"
    source_dir.mkdir(parents=True, exist_ok=True)
    features = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-01-02", "2026-01-09"]),
            "ticker": ["AAA.NS", "AAA.NS"],
            "target_weekly_return": [0.01, 0.02],
            "train_feature": [1.0, 2.0],
            "diagnostic_feature": [3.0, 4.0],
        }
    )
    features.to_parquet(source_dir / "northstar_features.parquet", index=False)
    pd.DataFrame({"date": pd.to_datetime(["2026-01-02", "2026-01-09"]), "regime": ["R1", "R1"]}).to_parquet(
        source_dir / "northstar_regime_labels.parquet", index=False
    )
    pd.DataFrame({"date": pd.to_datetime(["2026-01-02", "2026-01-09"]), "ticker": ["AAA.NS", "AAA.NS"]}).to_parquet(
        source_dir / "northstar_metadata.parquet", index=False
    )
    (source_dir / "northstar_walk_forward_splits.json").write_text(
        '[{"window_id": 1, "train_start": "2026-01-02", "train_end": "2026-01-02", "test_start": "2026-01-09", "test_end": "2026-01-09"}]',
        encoding="utf-8",
    )

    output_dir = tmp_path / "subset"
    subset_feature_export(
        source_dir=source_dir,
        output_dir=output_dir,
        selected_features=["train_feature", "diagnostic_feature"],
        model_feature_names=["train_feature"],
    )

    manifest = json.loads((output_dir / MODEL_FEATURE_MANIFEST).read_text(encoding="utf-8"))
    assert manifest == ["train_feature"]


def test_resolve_export_dir_falls_back_to_sibling_valid_export(tmp_path: Path):
    valid_export = tmp_path / "week_run_v6" / "00_export"
    valid_export.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-01-02"]),
            "ticker": ["AAA.NS"],
            "target_weekly_return": [0.01],
        }
    ).to_parquet(valid_export / "northstar_features.parquet", index=False)
    pd.DataFrame({"date": pd.to_datetime(["2026-01-02"]), "regime": ["R1"]}).to_parquet(
        valid_export / "northstar_regime_labels.parquet", index=False
    )
    pd.DataFrame({"date": pd.to_datetime(["2026-01-02"]), "ticker": ["AAA.NS"]}).to_parquet(
        valid_export / "northstar_metadata.parquet", index=False
    )
    (valid_export / "northstar_walk_forward_splits.json").write_text(
        '[{"window_id": 1, "train_start": "2026-01-02", "train_end": "2026-01-02", "test_start": "2026-01-09", "test_end": "2026-01-09"}]',
        encoding="utf-8",
    )

    missing_export = tmp_path / "week_run_v3" / "00_export"
    artifacts = resolve_export_dir(missing_export)

    assert artifacts.export_dir == valid_export.resolve()


def test_resolve_export_dir_missing_message_mentions_rerun(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    missing_export = tmp_path / "week_run_v3" / "00_export"
    isolated_root = tmp_path / "isolated_results"
    isolated_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(weekly_common, "PROJECT_ROOT", tmp_path / "project_root")
    monkeypatch.setattr(weekly_common, "default_results_root", lambda: isolated_root)
    monkeypatch.chdir(tmp_path)

    with pytest.raises(FileNotFoundError, match="rerun build_weekly_feature_export.py first"):
        resolve_export_dir(missing_export)


def test_load_export_artifacts_reconstructs_missing_splits_and_regimes(tmp_path: Path):
    export_dir = tmp_path / "augmented_only_export"
    export_dir.mkdir(parents=True, exist_ok=True)
    dates = pd.date_range("2019-01-04", periods=140, freq="W-FRI")
    features = pd.DataFrame(
        {
            "date": dates,
            "ticker": ["AAA.NS"] * len(dates),
            "close": [100.0 + idx for idx in range(len(dates))],
            "target_weekly_return": [0.01] * len(dates),
        }
    )
    metadata = pd.DataFrame(
        {
            "date": dates,
            "ticker": ["AAA.NS"] * len(dates),
            "broad_sector": ["Financial Services"] * len(dates),
        }
    )
    features.to_parquet(export_dir / "northstar_features.parquet", index=False)
    metadata.to_parquet(export_dir / "northstar_metadata.parquet", index=False)

    resolved = resolve_export_dir(export_dir)
    loaded_features, splits, regimes, loaded_metadata = load_export_artifacts(export_dir)

    assert resolved.export_dir == export_dir.resolve()
    assert not loaded_features.empty
    assert not loaded_metadata.empty
    assert len(splits) > 0
    assert not regimes.empty
    assert "plan_regime_id" in regimes.columns
