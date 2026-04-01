from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from scripts.kaggle.export_weekly_raw_inputs import kaggle_safe_relative_path
from scripts.kaggle.week_2026_03_29.build_weekly_feature_export import _effective_split_config
from scripts.kaggle.week_2026_03_29.build_weekly_feature_export import _profile_overrides
from scripts.kaggle.week_2026_03_29.build_weekly_feature_export import _dataset_runtime_config
from scripts.kaggle.week_2026_03_29.build_weekly_feature_export import _validate_raw_bundle_support_artifacts
from scripts.kaggle.week_2026_03_29.nb01_fixed_baselines import _prune_dead_features
from scripts.kaggle.week_2026_03_29.common import (
    build_feature_coverage_audit,
    build_feature_unit_registry,
    derive_size_rank,
    infer_feature_unit_kind,
    prepare_runtime_project,
    select_feature_columns,
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
