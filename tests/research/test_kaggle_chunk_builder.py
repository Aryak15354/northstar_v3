from __future__ import annotations

from pathlib import Path

import pandas as pd

from scripts.kaggle.build_local_feature_chunks import (
    _apply_feature_hygiene,
    _canonical_feature_column_order,
    _merge_plan_signals,
    _stabilize_feature_chunk_schemas,
)


def test_merge_plan_signals_preserves_warmup_history_for_chunk_local_coverage(tmp_path: Path) -> None:
    dates = pd.date_range("2024-01-05", periods=16, freq="W-FRI")
    weekly_panel = pd.DataFrame(
        {
            "date": dates,
            "ticker": ["AAA.NS"] * len(dates),
            "close": [100.0 + idx for idx in range(len(dates))],
            "india_vix": [12.0 + idx for idx in range(len(dates))],
            "rbi_repo_rate_level": [6.5] * 6 + [6.75] * 10,
        }
    )

    warm_enriched, _ = _merge_plan_signals(
        weekly_panel,
        raw_bundle_dir=tmp_path,
        runtime_root=tmp_path,
        allow_proxies=False,
    )
    warm_trimmed = warm_enriched[warm_enriched["date"].between(dates[4], dates[12])].reset_index(drop=True)

    cold_input = weekly_panel[weekly_panel["date"].between(dates[4], dates[12])].reset_index(drop=True)
    cold_enriched, _ = _merge_plan_signals(
        cold_input,
        raw_bundle_dir=tmp_path,
        runtime_root=tmp_path,
        allow_proxies=False,
    )

    warm_vix_coverage = float(pd.to_numeric(warm_trimmed["vix_india_4w"], errors="coerce").notna().mean())
    cold_vix_coverage = float(pd.to_numeric(cold_enriched["vix_india_4w"], errors="coerce").notna().mean())
    warm_rbi_coverage = float(pd.to_numeric(warm_trimmed["rbi_rate_chg"], errors="coerce").notna().mean())
    cold_rbi_coverage = float(pd.to_numeric(cold_enriched["rbi_rate_chg"], errors="coerce").notna().mean())

    assert warm_vix_coverage >= (8.0 / 9.0)
    assert cold_vix_coverage < warm_vix_coverage
    assert warm_rbi_coverage >= (8.0 / 9.0)
    assert cold_rbi_coverage < warm_rbi_coverage


def test_apply_feature_hygiene_drops_dead_features_and_adds_sparse_defaults() -> None:
    panel = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-05", "2024-01-12"]),
            "ticker": ["AAA.NS", "BBB.NS"],
            "earnings_quality_ratio": [None, None],
            "earnings_quality_ratio_cs_z": [0.0, 0.0],
            "earnings_quality_ratio_cs_rank": [0.0, 0.0],
            "rating_numeric": [10.0, None],
        }
    )

    cleaned, audit = _apply_feature_hygiene(panel)

    assert "earnings_quality_ratio" not in cleaned.columns
    assert "earnings_quality_ratio_cs_z" not in cleaned.columns
    assert "earnings_quality_ratio_cs_rank" not in cleaned.columns
    assert cleaned["pledge_pct"].tolist() == [0.0, 0.0]
    assert cleaned["pledge_pct_available"].tolist() == [0.0, 0.0]
    assert cleaned["days_since_earnings"].tolist() == [0.0, 0.0]
    assert cleaned["days_since_earnings_available"].tolist() == [0.0, 0.0]
    assert cleaned["rating_numeric"].tolist() == [10.0, 0.0]
    assert cleaned["rating_numeric_available"].tolist() == [1.0, 0.0]
    assert cleaned["sector_dummy__NA_"].tolist() == [0.0, 0.0]
    assert "earnings_quality_ratio" in audit["dropped_dead_features"]
    assert "pledge_pct" in audit["added_schema_columns"]


def test_stabilize_feature_chunk_schemas_adds_missing_columns_and_orders_output(tmp_path: Path) -> None:
    feature_path = tmp_path / "chunk_000.parquet"
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-05"]),
            "ticker": ["AAA.NS"],
            "alpha_feature": [1.0],
            "target_weekly_return": [0.02],
        }
    )
    frame.to_parquet(feature_path, index=False)

    canonical = _canonical_feature_column_order(
        ["date", "ticker", "alpha_feature", "days_since_earnings", "target_weekly_return"]
    )
    audits = _stabilize_feature_chunk_schemas(
        chunk_rows=[
            {
                "chunk_id": 0,
                "files": {"features": str(feature_path)},
            }
        ],
        canonical_columns=canonical,
    )

    stabilized = pd.read_parquet(feature_path)
    assert stabilized.columns.tolist() == canonical
    assert float(stabilized.loc[0, "days_since_earnings"]) == 0.0
    assert audits[0]["added_columns"] == ["days_since_earnings"]
