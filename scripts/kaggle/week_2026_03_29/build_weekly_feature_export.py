#!/usr/bin/env python3
"""Build a weekly Kaggle-ready Northstar feature export from the raw weekly bundle."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.research.dataset_manager import DatasetManager  # noqa: E402
from scripts.load_screener_to_pipeline import build_pipeline_files  # noqa: E402

from scripts.kaggle.week_2026_03_29.common import (  # noqa: E402
    attach_universe_annotations,
    build_feature_unit_registry,
    build_market_cap_fields,
    build_plan_regime_labels,
    build_screener_metric_unit_registry,
    cast_feature_frame,
    cast_metadata_frame,
    generate_anchored_weekly_splits,
    json_ready,
    make_run_dir,
    merge_regimes_into_panel,
    now_utc_iso,
    prepare_runtime_project,
    resample_daily_panel_to_weekly,
    resolve_raw_bundle_dir,
    select_feature_columns,
    working_directory,
    write_json,
    write_runtime_policy,
)

REQUIRED_WEEKLY_BUNDLE_PATHS = (
    "data/processed/intelligent_market_state.parquet",
    "data/processed/market_state.parquet",
    "data/processed/regime_labels.parquet",
    "data/processed/sector_mapping.csv",
    "data/processed/valuation_posterior.parquet",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the weekly Kaggle feature export from raw inputs.")
    parser.add_argument("--data-dir", type=Path, default=None, help="Attached weekly raw bundle root.")
    parser.add_argument("--output-dir", type=Path, default=None, help="Directory where the weekly export will be written.")
    parser.add_argument("--lookback-days", type=int, default=3200)
    parser.add_argument("--max-tickers", type=int, default=0)
    parser.add_argument("--max-rows", type=int, default=0)
    parser.add_argument("--start-date", type=str, default="2018-01-01")
    parser.add_argument("--end-date", type=str, default=None)
    parser.add_argument("--train-weeks", type=int, default=104)
    parser.add_argument("--test-weeks", type=int, default=13)
    parser.add_argument("--step-weeks", type=int, default=13)
    parser.add_argument("--target-windows", type=int, default=20)
    parser.add_argument("--low-resource-mode", choices=["auto", "true", "false"], default="false")
    parser.add_argument("--rebuild-screener", choices=["auto", "true", "false"], default="auto")
    parser.add_argument("--profile", choices=["smoke", "full"], default="full")
    return parser.parse_args()


def _validate_raw_bundle_support_artifacts(raw_bundle_dir: Path) -> None:
    missing = [rel for rel in REQUIRED_WEEKLY_BUNDLE_PATHS if not (raw_bundle_dir / rel).exists()]
    if not missing:
        return

    raise FileNotFoundError(
        "weekly_raw_bundle_incomplete: missing required support artifacts "
        f"{missing} under {raw_bundle_dir}. "
        "Rebuild the Kaggle raw bundle with "
        "`python3 scripts/kaggle/export_weekly_raw_inputs.py --output-dir ...` "
        "from the latest repo state and version the dataset again."
    )


def _profile_overrides(args: argparse.Namespace) -> dict[str, int | str]:
    if args.profile != "smoke":
        return {}
    return {
        "lookback_days": min(int(args.lookback_days), 480),
        "max_tickers": int(args.max_tickers or 30),
        "max_rows": int(args.max_rows or 30000),
        "low_resource_mode": "true",
        "rebuild_screener": "false",
    }


def _effective_split_config(
    weekly_dates: list[pd.Timestamp] | list[object],
    *,
    train_weeks: int,
    test_weeks: int,
    step_weeks: int,
    target_windows: int,
) -> dict[str, int | bool]:
    dates = (
        pd.Series(pd.to_datetime(list(weekly_dates), errors="coerce"))
        .dropna()
        .drop_duplicates()
        .sort_values()
        .tolist()
    )
    available = int(len(dates))
    config = {
        "train_weeks": int(max(1, train_weeks)),
        "test_weeks": int(max(1, test_weeks)),
        "step_weeks": int(max(1, step_weeks)),
        "target_windows": int(max(1, target_windows)),
        "adjusted": False,
        "available_dates": available,
    }
    if available >= config["train_weeks"] + config["test_weeks"]:
        return config

    test_eff = min(config["test_weeks"], max(4, min(13, max(1, available // 5))))
    train_cap = max(8, available - test_eff)
    train_eff = min(config["train_weeks"], max(12, train_cap))
    if train_eff + test_eff > available:
        train_eff = max(8, available - test_eff)
    if train_eff + test_eff > available:
        test_eff = max(1, available - train_eff)
    step_eff = min(config["step_weeks"], max(1, min(test_eff, max(1, available // 8))))
    remaining = max(0, available - train_eff - test_eff)
    window_cap = max(1, (remaining // max(1, step_eff)) + 1)

    config.update(
        {
            "train_weeks": int(max(8, train_eff)),
            "test_weeks": int(max(1, test_eff)),
            "step_weeks": int(max(1, step_eff)),
            "target_windows": int(min(max(1, target_windows), window_cap)),
            "adjusted": True,
        }
    )
    return config


def _weekly_feature_pit_lag_rules() -> list[dict[str, object]]:
    return [
        {"pattern": "sector_dummy", "lag": "price"},
        {"pattern": "re:^(open|high|low|close|adj_close|volume|turnover|vwap|ret_.*|mom_.*|vol_.*|beta.*|bab.*|amihud.*|max_ret_.*|drawdown.*|price_.*|nifty_.*|india_vix.*|size_x_amihud)$", "lag": "price"},
        {"pattern": "re:^(days_since_earnings|earnings_.*|eps_.*|rev_.*|combined_sue.*)$", "lag": "earnings"},
        {"pattern": "re:^(revenue|sales|gross_profit|operating_cash_flow|free_cash_flow|net_income|equity|total_assets|total_debt|working_capital|shares_outstanding|gross_margin.*|operating_margin.*|ebitda_margin.*|interest_coverage.*|asset_turnover.*|cash_conversion.*|accruals_ratio.*|debt_to_equity.*|roe.*|roa.*|piotroski.*|earnings_quality.*|sector_quality_composite.*)$", "lag": "fundamental"},
        {"pattern": "re:^(bulk_.*|order_.*|rating_.*|announcement_.*|announcements_.*)$", "lag": "bulk"},
        {"pattern": "re:^(pledge_.*|promoter_.*|fii_.*|dii_.*|public_.*|institutional_.*|free_float.*|ownership.*)$", "lag": "shareholding"},
        {"pattern": "re:^(cpi_.*|wpi_.*|iip_.*|pmi_.*|repo_.*|macro_.*|fx_.*|rate_.*|policy_.*|credit_.*|oil_.*|gold_.*|copper_.*|steel_.*|inr_.*|dxy_.*|political_.*|india_domestic_.*|gold_consumption_drag.*|oil_sector_impact.*|copper_activity_signal.*|dxy_fii_proxy.*|macro_linkage_score.*)$", "lag": "macro"},
        {"pattern": "re:^(posterior_.*|agreement_score.*|val_.*)$", "lag": "market"},
    ]


def _dataset_runtime_config(
    *,
    policy_path: Path,
    start_date: str | None,
    end_date: str | None,
    lookback_days: int,
    max_tickers: int,
    max_rows: int,
    low_resource_mode: str,
    profile: str,
) -> dict[str, object]:
    valuation_enabled = str(profile).strip().lower() != "smoke"
    smoke_profile = str(profile).strip().lower() == "smoke"
    return {
        "policy_config_path": str(policy_path),
        "prices_path": "data/canonical/prices/equity_prices_daily.parquet",
        "fundamentals_path": "data/canonical/fundamentals/fundamentals_annual_panel.parquet",
        "macro_features_path": "data/canonical/macro/macro_regime_features.parquet",
        "valuation_posterior_path": "data/processed/valuation_posterior.parquet",
        "screener_fundamentals_path": "data/canonical/fundamentals/fundamentals_annual_panel.csv",
        "screener_quarterly_path": "data/canonical/fundamentals/fundamentals_quarterly_panel.csv",
        "screener_shareholding_path": "data/canonical/fundamentals/shareholding_quarterly.csv",
        "alternative_data_path": "data/canonical/alternative",
        "announcement_dates_path": "data/processed/alternative/earnings_dates_all.csv",
        "use_sentiment_features": False,
        "use_screener_features": True,
        "use_alternative_features": True,
        "use_macro_features": True,
        "enable_macro_features": True,
        "use_gap9_academic_factors": True,
        "strict_real_data_only": True,
        "feature_pit_enforce": False,
        "feature_pit_lags": _weekly_feature_pit_lag_rules(),
        "pit_announcement_plus_days": 1,
        "pit_earnings_announcement_plus_days": 1,
        "pit_financials_plus_days": 1,
        "pit_fundamental_lag_days": 60,
        "pit_shareholding_lag_days": 2,
        "pit_bulk_deal_lag_days": 1,
        "pit_macro_lag_days": 1,
        "feature_budget_enforce": False,
        "feature_budget": 320 if smoke_profile else 500,
        "feature_correlation_enforce": False,
        "feature_correlation_skip": True,
        "lookback_days": int(max(180, lookback_days)),
        "max_tickers": int(max(0, max_tickers)),
        "max_rows": int(max(0, max_rows)),
        "low_resource_mode": str(low_resource_mode),
        "start_date": start_date,
        "end_date": end_date,
        "valuation": {
            "features_enabled": valuation_enabled,
            "feature_columns": "zscore_only",
            "allow_prior_cache_fallback": True,
            "max_cache_fallback_age_days": 7,
        },
    }


def _build_dataset_frame(
    runtime_root: Path,
    *,
    policy_path: Path,
    start_date: str | None,
    end_date: str | None,
    lookback_days: int,
    max_tickers: int,
    max_rows: int,
    low_resource_mode: str,
    profile: str,
) -> tuple[pd.DataFrame, dict[str, object]]:
    config_payload = _dataset_runtime_config(
        policy_path=policy_path,
        start_date=start_date,
        end_date=end_date,
        lookback_days=lookback_days,
        max_tickers=max_tickers,
        max_rows=max_rows,
        low_resource_mode=low_resource_mode,
        profile=profile,
    )
    with working_directory(runtime_root):
        manager = DatasetManager(project_root=runtime_root, config=config_payload)
        dataset = manager.build_research_dataset()
    return dataset.frame.copy(), dict(dataset.metadata or {})


def _maybe_rebuild_screener(runtime_root: Path, mode: str) -> dict[str, object]:
    raw_dir = runtime_root / "data" / "raw" / "vendors" / "screener"
    canonical_dir = runtime_root / "data" / "canonical" / "fundamentals"
    canonical_dir.mkdir(parents=True, exist_ok=True)
    scratch_dir = runtime_root / "reports" / "screener_rebuild"
    scratch_dir.mkdir(parents=True, exist_ok=True)

    enabled = str(mode).strip().lower()
    should_rebuild = enabled == "true" or (enabled == "auto" and raw_dir.exists())
    report: dict[str, object] = {
        "mode": enabled,
        "raw_dir_exists": raw_dir.exists(),
        "enabled": should_rebuild,
        "files": {},
    }
    if not should_rebuild or not raw_dir.exists():
        return report

    prior_stats: dict[str, dict[str, object]] = {}
    for filename in ["fundamentals_annual_panel.csv", "fundamentals_quarterly_panel.csv", "shareholding_quarterly.csv"]:
        path = canonical_dir / filename
        if not path.exists():
            continue
        try:
            prior = pd.read_csv(path)
            prior_stats[filename] = {"rows": int(len(prior)), "cols": int(len(prior.columns))}
        except Exception:
            prior_stats[filename] = {"rows": 0, "cols": 0}

    built = build_pipeline_files(raw_dir=raw_dir, output_dir=scratch_dir)
    mapping = {
        "annual": canonical_dir / "fundamentals_annual_panel.csv",
        "quarterly": canonical_dir / "fundamentals_quarterly_panel.csv",
        "shareholding": canonical_dir / "shareholding_quarterly.csv",
    }
    file_reports: dict[str, object] = {}
    for key, dest in mapping.items():
        frame = built.get(key)
        if not isinstance(frame, pd.DataFrame) or frame.empty:
            file_reports[key] = {"written": False, "rows": 0, "cols": 0}
            continue
        frame.to_csv(dest, index=False)
        file_reports[key] = {
            "written": True,
            "rows": int(len(frame)),
            "cols": int(len(frame.columns)),
            "destination": str(dest),
            "prior_rows": int(prior_stats.get(dest.name, {}).get("rows", 0)),
            "prior_cols": int(prior_stats.get(dest.name, {}).get("cols", 0)),
        }
    report["files"] = file_reports
    return report


def main() -> int:
    args = parse_args()
    raw_bundle_dir = resolve_raw_bundle_dir(args.data_dir)
    _validate_raw_bundle_support_artifacts(raw_bundle_dir)
    export_dir = (args.output_dir.expanduser().resolve() if args.output_dir else make_run_dir(None, "feature_export"))
    export_dir.mkdir(parents=True, exist_ok=True)

    print("[stage] prepare_runtime_project", flush=True)
    runtime_root = prepare_runtime_project(raw_bundle_dir, export_dir / "_runtime_root")
    print("[stage] rebuild_screener", flush=True)
    overrides = _profile_overrides(args)
    effective_lookback_days = int(overrides.get("lookback_days", args.lookback_days))
    effective_max_tickers = int(overrides.get("max_tickers", args.max_tickers))
    effective_max_rows = int(overrides.get("max_rows", args.max_rows))
    effective_low_resource_mode = str(overrides.get("low_resource_mode", args.low_resource_mode))
    effective_rebuild_screener = str(overrides.get("rebuild_screener", args.rebuild_screener))
    screener_rebuild = _maybe_rebuild_screener(runtime_root, effective_rebuild_screener)
    write_json(export_dir / "screener_rebuild_validation.json", screener_rebuild)
    policy_path = write_runtime_policy(
        runtime_root,
        start_date=str(args.start_date) if args.start_date else None,
        end_date=str(args.end_date) if args.end_date else None,
        lookback_days=effective_lookback_days,
        max_tickers=effective_max_tickers,
        max_rows=effective_max_rows,
        low_resource_mode=effective_low_resource_mode,
        profile=args.profile,
    )

    screener_unit_registry = build_screener_metric_unit_registry(runtime_root)
    if not screener_unit_registry.empty:
        screener_unit_registry.to_csv(export_dir / "screener_metric_unit_registry.csv", index=False)
        write_json(export_dir / "screener_metric_unit_registry.json", screener_unit_registry.to_dict("records"))

    print("[stage] build_dataset_frame", flush=True)
    panel, dataset_meta = _build_dataset_frame(
        runtime_root,
        policy_path=policy_path,
        start_date=str(args.start_date) if args.start_date else None,
        end_date=str(args.end_date) if args.end_date else None,
        lookback_days=effective_lookback_days,
        max_tickers=effective_max_tickers,
        max_rows=effective_max_rows,
        low_resource_mode=effective_low_resource_mode,
        profile=args.profile,
    )
    if "date" not in panel.columns and "Date" in panel.columns:
        panel = panel.rename(columns={"Date": "date"})
    panel["date"] = pd.to_datetime(panel["date"], errors="coerce").dt.normalize()
    panel["ticker"] = panel["ticker"].astype("string")
    panel = panel.dropna(subset=["date", "ticker"]).sort_values(["date", "ticker"], kind="mergesort")

    print("[stage] build_weekly_panel", flush=True)
    weekly_panel = resample_daily_panel_to_weekly(panel)
    weekly_panel = attach_universe_annotations(weekly_panel, runtime_root)
    weekly_panel = build_market_cap_fields(weekly_panel)
    regimes_df = build_plan_regime_labels(weekly_panel, runtime_root)
    weekly_panel = merge_regimes_into_panel(weekly_panel, regimes_df)

    feature_cols = select_feature_columns(weekly_panel)
    features_df = cast_feature_frame(weekly_panel, feature_cols)
    metadata_df = cast_metadata_frame(weekly_panel)
    split_config = _effective_split_config(
        features_df["date"].tolist(),
        train_weeks=int(args.train_weeks),
        test_weeks=int(args.test_weeks),
        step_weeks=int(args.step_weeks),
        target_windows=int(args.target_windows),
    )
    splits = generate_anchored_weekly_splits(
        features_df["date"].tolist(),
        train_weeks=int(split_config["train_weeks"]),
        test_weeks=int(split_config["test_weeks"]),
        step_weeks=int(split_config["step_weeks"]),
        target_windows=int(split_config["target_windows"]),
    )

    features_path = export_dir / "northstar_features.parquet"
    metadata_path = export_dir / "northstar_metadata.parquet"
    splits_path = export_dir / "northstar_walk_forward_splits.json"
    regimes_path = export_dir / "northstar_regime_labels.parquet"

    features_df.to_parquet(features_path, index=False)
    metadata_df.to_parquet(metadata_path, index=False)
    regimes_df.to_parquet(regimes_path, index=False)
    write_json(splits_path, splits)
    write_json(export_dir / "feature_unit_registry.json", build_feature_unit_registry(features_df))
    write_json(
        export_dir / "feature_pit_registry_summary.json",
        {
            "feature_pit_registry_enforced": bool(dataset_meta.get("feature_pit_registry_enforced", False)),
            "feature_pit_registry_base_features": int(dataset_meta.get("feature_pit_registry_base_features", 0) or 0),
            "feature_pit_registry_missing_count": int(dataset_meta.get("feature_pit_registry_missing_count", 0) or 0),
            "feature_pit_registry_coverage_pct": float(dataset_meta.get("feature_pit_registry_coverage_pct", 0.0) or 0.0),
            "feature_pit_registry_missing_sample": list(dataset_meta.get("feature_pit_registry_missing_sample") or []),
        },
    )

    manifest = {
        "generated_at": now_utc_iso(),
        "raw_bundle_dir": str(raw_bundle_dir),
        "runtime_root": str(runtime_root),
        "profile": args.profile,
        "effective_limits": {
            "lookback_days": effective_lookback_days,
            "max_tickers": effective_max_tickers,
            "max_rows": effective_max_rows,
            "low_resource_mode": effective_low_resource_mode,
        },
        "effective_split_config": split_config,
        "features_rows": int(len(features_df)),
        "metadata_rows": int(len(metadata_df)),
        "feature_count": int(len(feature_cols)),
        "ticker_count": int(features_df["ticker"].nunique()),
        "date_min": str(features_df["date"].min().date()),
        "date_max": str(features_df["date"].max().date()),
        "target_non_null_pct": float(features_df["target_weekly_return"].notna().mean()),
        "n_windows": int(len(splits)),
        "model_safe_feature_count": int(len(feature_cols)),
        "screener_rebuild": screener_rebuild,
        "dataset_metadata": json_ready(dataset_meta),
        "files": {
            "features": str(features_path),
            "metadata": str(metadata_path),
            "splits": str(splits_path),
            "regimes": str(regimes_path),
            "policy": str(policy_path),
        },
    }
    write_json(export_dir / "weekly_export_manifest.json", manifest)

    print(
        json.dumps(
            json_ready(
                {
                    "export_dir": str(export_dir),
                    "features_rows": int(len(features_df)),
                    "feature_count": int(len(feature_cols)),
                    "ticker_count": int(features_df["ticker"].nunique()),
                    "target_non_null_pct": round(float(features_df["target_weekly_return"].notna().mean()), 6),
                    "n_windows": int(len(splits)),
                    "screener_rebuild_enabled": bool(screener_rebuild.get("enabled")),
                    "feature_pit_missing_count": int(dataset_meta.get("feature_pit_registry_missing_count", 0) or 0),
                    "feature_pit_coverage_pct": round(float(dataset_meta.get("feature_pit_registry_coverage_pct", 0.0) or 0.0), 3),
                    "split_config_adjusted": bool(split_config["adjusted"]),
                }
            ),
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
