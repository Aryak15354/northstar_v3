from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from scripts.kaggle.export_weekly_raw_inputs import kaggle_safe_relative_path
from scripts.kaggle.week_2026_03_29.build_weekly_feature_export import _effective_split_config
from scripts.kaggle.week_2026_03_29.build_weekly_feature_export import _profile_overrides
from scripts.kaggle.week_2026_03_29.build_weekly_feature_export import _dataset_runtime_config
from scripts.kaggle.week_2026_03_29.build_weekly_feature_export import _validate_raw_bundle_support_artifacts
from scripts.kaggle.week_2026_03_29.common import (
    build_feature_unit_registry,
    derive_size_rank,
    infer_feature_unit_kind,
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
