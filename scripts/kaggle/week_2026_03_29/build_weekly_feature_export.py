#!/usr/bin/env python3
"""Build a weekly Kaggle-ready Northstar feature export from the raw weekly bundle.

DEPRECATED as the source of truth. The chunked build path
(``build_local_feature_chunks.py`` -> ``merge_chunked_feature_dataset.py``) is
the canonical dataset builder: it is memory-bounded and additionally computes the
~14-column macro/commodity plan-signal block (``crude_4w_return`` ...
``stock_x_inrusd``) that this direct path does not. Use this script only for a
quick single-shot export on a machine with enough RAM; the shipped Kaggle dataset
must come from the chunked path. See ``path_status`` in the emitted manifest.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.research.dataset_manager import DatasetManager  # noqa: E402
from src.research.reference_data import resolve_reference_root, validate_reference_bundle  # noqa: E402
from scripts.load_screener_to_pipeline import build_pipeline_files  # noqa: E402

from scripts.kaggle.week_2026_03_29.common import (  # noqa: E402
    FAMILY_AUDIT_SPECS,
    attach_universe_annotations,
    apply_export_quality_repairs,
    build_regime_window_audit,
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
    repair_runtime_factor_families,
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
    "data/processed/macro/rbi_macro_weekly.parquet",
    "data/processed/sector_financials/credit_quarterly.parquet",
    "data/processed/screener_fundamentals_quarterly.csv",
    "data/processed/regime_labels.parquet",
    "data/processed/sector_mapping.csv",
    "data/processed/valuation_posterior.parquet",
)


def _merge_active_with_delisted(
    active: pd.DataFrame | None,
    delisted_path: Path,
    *,
    key_cols: list[str],
    sort_cols: list[str],
) -> pd.DataFrame:
    active_df = active.copy() if isinstance(active, pd.DataFrame) else pd.DataFrame()
    delisted_df = pd.read_csv(delisted_path, low_memory=False) if delisted_path.exists() else pd.DataFrame()
    frames: list[pd.DataFrame] = []
    if not active_df.empty:
        active_df["is_delisted"] = False
        active_df["record_origin"] = "active_screener"
        frames.append(active_df)
    if not delisted_df.empty:
        delisted_df = delisted_df.copy()
        delisted_df["is_delisted"] = True
        delisted_df["record_origin"] = "delisted_screener"
        frames.append(delisted_df)
    if not frames:
        return pd.DataFrame()
    merged = pd.concat(frames, ignore_index=True, sort=False)
    keep_keys = [col for col in key_cols if col in merged.columns]
    if keep_keys:
        merged = merged.drop_duplicates(subset=keep_keys, keep="first")
    keep_sort = [col for col in sort_cols if col in merged.columns]
    if keep_sort:
        merged = merged.sort_values(keep_sort, kind="mergesort")
    return merged.reset_index(drop=True)


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
    parser.add_argument("--forward-buffer-days", type=int, default=10)
    parser.add_argument("--target-horizon-days", type=int, default=5)
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
    forward_buffer_days: int = 10,
    target_horizon_days: int = 5,
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
    embargo_weeks = int(math.ceil(max(0, int(forward_buffer_days) + int(target_horizon_days)) / 7.0))
    config["embargo_weeks"] = embargo_weeks
    if available >= config["train_weeks"] + config["test_weeks"] + embargo_weeks:
        return config

    test_eff = min(config["test_weeks"], max(4, min(13, max(1, available // 5))))
    train_cap = max(8, available - test_eff - embargo_weeks)
    train_eff = min(config["train_weeks"], max(12, train_cap))
    if train_eff + test_eff + embargo_weeks > available:
        train_eff = max(8, available - test_eff - embargo_weeks)
    if train_eff + test_eff + embargo_weeks > available:
        test_eff = max(1, available - train_eff - embargo_weeks)
    step_eff = min(config["step_weeks"], max(1, min(test_eff, max(1, available // 8))))
    remaining = max(0, available - train_eff - test_eff - embargo_weeks)
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
        {"pattern": "re:^(open|high|low|close|adj_close|volume|turnover|vwap|ret_.*|mom_.*|res_mom.*|vol_.*|beta.*|bab.*|amihud.*|max_ret_.*|drawdown.*|price_.*|nifty_.*|india_vix.*|size_x_amihud|mom[0-9]+_x_.*)$", "lag": "price"},
        {"pattern": "re:^(days_since_earnings|days_since_earnings_available|earnings_.*|eps_.*|rev_.*|combined_sue.*)$", "lag": "earnings"},
        {"pattern": "re:^(revenue|sales|gross_profit|ebitda|operating_income|operating_cash_flow|free_cash_flow|net_income|equity|total_assets|total_debt|working_capital|shares_outstanding|gross_margin.*|ni_margin.*|operating_margin.*|ebitda_margin.*|interest_expense|interest_coverage.*|asset_turnover.*|cash_conversion.*|fcf_to_ocf.*|accruals_ratio.*|debt_to_equity.*|roe.*|roa.*|piotroski.*|earnings_quality.*|sector_quality_composite.*)$", "lag": "fundamental"},
        # ratings-family flags that do not start with "rating_" (see the same fix in
        # src/research/feature_pit_rules.py); missing here => feature_pit_lag_missing.
        {"pattern": "re:^(bulk_.*|order_.*|rating_.*|recent_upgrade_flag|recent_downgrade_flag|watch_negative_flag|investment_grade_flag|announcement_.*|announcements_.*|insider_.*)$", "lag": "bulk"},
        {"pattern": "re:^(screener_.*(promoter|fii|dii|public|govt|institutional|free_float|ownership).*)$", "lag": "shareholding"},
        {"pattern": "re:^(pledge_.*|promoter_.*|fii_.*|dii_.*|public_.*|institutional_.*|free_float.*|ownership.*)$", "lag": "shareholding"},
        {"pattern": "re:^(screener_.*)$", "lag": "fundamental"},
        {"pattern": "re:^(mkt_sent_.*|macro_sent_.*|macro_sentiment_.*|sent_.*|sentiment_.*|event_.*|narrative_.*|topic_.*)$", "lag": "sentiment"},
        {"pattern": "re:^(cpi_.*|wpi_.*|iip_.*|pmi_.*|repo_.*|macro_.*|fx_.*|rate_.*|policy_.*|credit_.*|oil_.*|gold_.*|copper_.*|steel_.*|coal_.*|crude_.*|inr_.*|inrusd_.*|dxy_.*|vix_.*|rbi_.*|gst_.*|power_.*|us_10y_.*|yield_curve_.*|commodity_basket|fii_proxy|stock_x_.*|political_.*|india_domestic_.*|gold_consumption_drag.*|oil_sector_impact.*|copper_activity_signal.*|dxy_fii_proxy.*|macro_linkage_score.*|regime_.*|.*_x_regime_modifier)$", "lag": "macro"},
        {"pattern": "re:^(international_revenue_proxy|.*_sensitivity_score|business_cycle_bucket)$", "lag": "market"},
        {"pattern": "re:^(posterior_.*|agreement_score.*|val_.*)$", "lag": "market"},
    ]


def _feature_family_audit(features_df: pd.DataFrame) -> dict[str, object]:
    specs = FAMILY_AUDIT_SPECS  # C.7: single source of truth shared with the merge path
    rows: dict[str, object] = {}
    for family, spec in specs.items():
        prefixes = tuple(spec["prefixes"])
        cols = [c for c in features_df.columns if str(c).startswith(prefixes)]
        coverage = pd.Series(dtype=float)
        if cols:
            coverage = features_df[cols].notna().mean().sort_values(ascending=False)
        core_prefixes = tuple(spec.get("core_prefixes", ()))
        core_cols = [c for c in cols if str(c).startswith(core_prefixes)] if core_prefixes else cols
        core_coverage = pd.Series(dtype=float)
        if core_cols:
            core_coverage = features_df[core_cols].notna().mean().sort_values(ascending=False)
        max_cov = float(coverage.iloc[0]) if len(coverage) else 0.0
        core_max_cov = float(core_coverage.iloc[0]) if len(core_coverage) else 0.0
        median_cov = float(coverage.median()) if len(coverage) else 0.0
        core_median_cov = float(core_coverage.median()) if len(core_coverage) else 0.0
        passing = len(cols) >= int(spec["min_columns"]) and core_median_cov >= float(spec["min_core_median_coverage"])
        rows[family] = {
            "columns": int(len(cols)),
            "core_columns": int(len(core_cols)),
            "min_columns": int(spec["min_columns"]),
            "max_coverage": max_cov,
            "core_max_coverage": core_max_cov,
            "core_median_coverage": core_median_cov,
            "median_coverage": median_cov,
            "min_core_median_coverage": float(spec["min_core_median_coverage"]),
            "source_scope": str(spec.get("source_scope", "full_history_expected")),
            "top_columns": coverage.head(12).round(6).to_dict() if len(coverage) else {},
            "top_core_columns": core_coverage.head(12).round(6).to_dict() if len(core_coverage) else {},
            "status": "PASS" if passing else "FAIL",
        }
    return rows


def _enforce_feature_family_audit(audit: dict[str, object], *, enforce: bool) -> None:
    failures = {
        family: row
        for family, row in audit.items()
        if isinstance(row, dict) and row.get("status") != "PASS"
    }
    if not failures:
        return
    message = "required_feature_families_missing_or_dead:" + json.dumps(json_ready(failures), sort_keys=True)
    if enforce:
        raise RuntimeError(message)
    print(f"[build_export] family audit warning: {message}", flush=True)


def _load_reference_universe() -> list[str]:
    """The Nifty-500 reference research universe (symbols, '.NS' normalised).
    Used to keep out-of-universe delisted-backfill names out of the export so it
    passes validate_reference_bundle. Returns [] if unreadable (filter no-ops)."""
    for rel in (
        "data/canonical/reference/universe/nifty500_universe_enriched.parquet",
        "data/canonical/reference/universe/nifty500_universe_enriched.csv",
    ):
        p = PROJECT_ROOT / rel if "PROJECT_ROOT" in globals() else Path(rel)
        try:
            if not p.exists():
                continue
            df = pd.read_parquet(p) if p.suffix == ".parquet" else pd.read_csv(p)
            col = next((c for c in ("symbol", "ticker", "nse_symbol") if c in df.columns), None)
            if col is None:
                continue
            syms = {str(s).strip().upper() for s in df[col].dropna() if str(s).strip()}
            return sorted(s if s.endswith(".NS") else f"{s}.NS" for s in syms)
        except Exception:
            continue
    return []


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
        "universe_whitelist": _load_reference_universe(),
        "downcast_float32_features": True,  # memory guard for 8GB laptops
        "prices_path": "data/canonical/prices/equity_prices_daily.parquet",
        "fundamentals_path": "data/canonical/fundamentals/fundamentals_annual_panel.parquet",
        "macro_features_path": "data/canonical/macro/macro_regime_features.parquet",
        "rbi_macro_weekly_path": "data/processed/macro/rbi_macro_weekly.parquet",
        "credit_quarterly_path": "data/processed/sector_financials/credit_quarterly.parquet",
        "valuation_posterior_path": "data/processed/valuation_posterior.parquet",
        "screener_fundamentals_path": "data/canonical/fundamentals/fundamentals_annual_panel.parquet",
        "screener_quarterly_path": "data/canonical/fundamentals/fundamentals_quarterly_panel.parquet",
        "screener_shareholding_path": "data/canonical/fundamentals/shareholding_quarterly.parquet",
        "alternative_data_path": "data/canonical/alternative",
        "announcement_dates_path": "data/processed/alternative/earnings_dates_all.csv",
        "use_sentiment_features": True,
        "use_screener_features": True,
        "use_alternative_features": True,
        "use_macro_features": True,
        "enable_macro_features": True,
        "use_gap9_academic_factors": True,
        "strict_real_data_only": True,
        # Enforcement ON: DatasetManager's PIT-registry and feature-budget
        # enforcement mechanisms default True and are validated against the
        # 14-rule lag catalog below; they were previously overridden to False,
        # which is exactly what let the export exceed its declared budget and
        # skip point-in-time validation.
        "feature_pit_enforce": True,
        "feature_pit_lags": _weekly_feature_pit_lag_rules(),
        "pit_announcement_plus_days": 1,
        "pit_earnings_announcement_plus_days": 1,
        "pit_financials_plus_days": 1,
        "pit_fundamental_lag_days": 60,
        "pit_shareholding_lag_days": 2,
        "pit_bulk_deal_lag_days": 1,
        "pit_macro_lag_days": 1,
        "feature_budget_enforce": True,
        # This budget applies to the PRE-REPAIR daily panel (before the merge-time
        # RBI cap to 120 and dedup), where the RBI weekly pack alone contributes
        # ~930 base columns — so it is a hard regression ceiling against unbounded
        # growth, not the export budget. The declared 500-feature budget for the
        # FINAL export is enforced in merge_chunked_feature_dataset.py after all
        # repairs (measured 254 base names on the last real export).
        "feature_budget": 1200 if smoke_profile else 1600,
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
            # This config only feeds weekly exports; daily-cadence valuation
            # work is discarded by the weekly resample (tail(1) per week).
            # Without this the from-scratch recompute cannot fit Kaggle's 12h
            # cap (observed 2026-07-16: chunk 1 valuation alone > 1h).
            "compute_cadence": "weekly_tail",
            # export builds run on the marker-attested precomputed cache; the
            # low-coverage retry would bypass it and recompute sparse dates
            # uncached (the v13 killer). Never enable for bundle-driven builds.
            "low_coverage_retry_enabled": False,
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
    delisted_dir = runtime_root / "data" / "processed" / "screener_delisted"
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
    built = {
        "annual": _merge_active_with_delisted(
            built.get("annual"),
            delisted_dir / "screener_fundamentals_annual.csv",
            key_cols=["ticker", "fiscal_year"],
            sort_cols=["ticker", "fiscal_year"],
        ),
        "quarterly": _merge_active_with_delisted(
            built.get("quarterly"),
            delisted_dir / "screener_fundamentals_quarterly.csv",
            key_cols=["ticker", "quarter"],
            sort_cols=["ticker", "quarter"],
        ),
        "shareholding": _merge_active_with_delisted(
            built.get("shareholding"),
            delisted_dir / "screener_shareholding.csv",
            key_cols=["ticker", "quarter"],
            sort_cols=["ticker", "quarter"],
        ),
    }
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
    weekly_panel, runtime_factor_repairs = repair_runtime_factor_families(weekly_panel)
    weekly_panel, export_quality_audit = apply_export_quality_repairs(weekly_panel)

    feature_cols = select_feature_columns(weekly_panel)
    features_df = cast_feature_frame(weekly_panel, feature_cols)
    metadata_df = cast_metadata_frame(weekly_panel)
    family_audit = _feature_family_audit(features_df)
    write_json(export_dir / "dataset_family_audit.json", family_audit)
    write_json(export_dir / "export_quality_audit.json", export_quality_audit)
    _enforce_feature_family_audit(
        family_audit,
        enforce=args.profile != "smoke" and int(effective_max_tickers) == 0,
    )
    reference_root = resolve_reference_root(runtime_root, required=False)
    reference_audit = validate_reference_bundle(
        reference_root,
        features_df=features_df,
        metadata_df=metadata_df,
        strict=args.profile != "smoke" and int(effective_max_tickers) == 0,
        expected_universe_size=500,
    )
    split_config = _effective_split_config(
        features_df["date"].tolist(),
        train_weeks=int(args.train_weeks),
        test_weeks=int(args.test_weeks),
        step_weeks=int(args.step_weeks),
        target_windows=int(args.target_windows),
        forward_buffer_days=int(args.forward_buffer_days),
        target_horizon_days=int(args.target_horizon_days),
    )
    splits = generate_anchored_weekly_splits(
        features_df["date"].tolist(),
        train_weeks=int(split_config["train_weeks"]),
        test_weeks=int(split_config["test_weeks"]),
        step_weeks=int(split_config["step_weeks"]),
        target_windows=int(split_config["target_windows"]),
        forward_buffer_days=int(args.forward_buffer_days),
        target_horizon_days=int(args.target_horizon_days),
    )
    regime_window_audit = build_regime_window_audit(regimes_df, splits)
    for warning in regime_window_audit.get("warnings", []):
        print(f"[build_export] regime audit warning: {warning}", flush=True)

    features_path = export_dir / "northstar_features.parquet"
    metadata_path = export_dir / "northstar_metadata.parquet"
    splits_path = export_dir / "northstar_walk_forward_splits.json"
    regimes_path = export_dir / "northstar_regime_labels.parquet"

    features_df.to_parquet(features_path, index=False)
    metadata_df.to_parquet(metadata_path, index=False)
    regimes_df.to_parquet(regimes_path, index=False)
    write_json(splits_path, splits)
    write_json(export_dir / "regime_window_audit.json", regime_window_audit)
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
        "builder": "build_weekly_feature_export.py",
        "path_status": "deprecated_use_chunked",
        "universe_annotation_pit": "current_snapshot_static",
        "path_status_note": (
            "Direct single-shot export. Canonical dataset is built via the chunked "
            "path (build_local_feature_chunks.py -> merge_chunked_feature_dataset.py), "
            "which also emits the plan-signal macro/commodity block absent here."
        ),
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
        "dataset_family_audit": json_ready(family_audit),
        "runtime_factor_repairs": json_ready(runtime_factor_repairs),
        "export_quality_audit": json_ready(export_quality_audit),
        "reference_audit": json_ready(reference_audit),
        "regime_window_audit": regime_window_audit,
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
                    "restricted_regime_windows": int(regime_window_audit.get("restricted_window_count", 0) or 0),
                    "restricted_regime_window_limit": int(regime_window_audit.get("restricted_window_limit", 0) or 0),
                    "screener_rebuild_enabled": bool(screener_rebuild.get("enabled")),
                    "feature_pit_missing_count": int(dataset_meta.get("feature_pit_registry_missing_count", 0) or 0),
                    "feature_pit_coverage_pct": round(float(dataset_meta.get("feature_pit_registry_coverage_pct", 0.0) or 0.0), 3),
                    "dataset_family_audit": family_audit,
                    "export_quality_audit": export_quality_audit,
                    "split_config_adjusted": bool(split_config["adjusted"]),
                    "regime_window_warnings": list(regime_window_audit.get("warnings") or []),
                }
            ),
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
