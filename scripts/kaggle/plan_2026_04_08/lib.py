#!/usr/bin/env python3
"""Shared helpers for separate EXP-09 through EXP-18 Kaggle scripts."""

from __future__ import annotations

import argparse
import importlib
import json
import re
import shutil
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

from notebooks.kaggle_sprint.shared.sprint_utils import (
    DEFAULT_REDUCED_EXCLUDE_REGEX,
    FactorICAnalyzer,
    top_ic_feature_names,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.kaggle.week_2026_03_29.common import resolve_export_dir as resolve_weekly_export_dir
from scripts.kaggle.plan_2026_04_05.catalog import ExperimentSpec, load_experiment_catalog, load_plan_info
from scripts.kaggle.plan_2026_04_05.common import (
    PlanDataset,
    augment_sector_conditionals,
    compute_ic_series,
    generate_anchored_weekly_splits,
    json_ready,
    load_major_events,
    load_plan_dataset,
    load_summary_if_exists,
    make_experiment_paths,
    pick_best_candidate,
    prepare_subset_export,
    run_track_a_model,
    summarize_ic_series,
    summarize_model_state,
    write_json,
    write_narrative,
    write_table,
)
from scripts.kaggle.plan_2026_04_05.model_redemption import run_redemption_experiment
from scripts.kaggle.plan_2026_04_05.regime_campaign import run_regime_experiment
from scripts.kaggle.plan_2026_04_05.signal_expansion import run_signal_experiment
from scripts.kaggle.plan_2026_04_05.signal_verification import run_verification_experiment


DEFAULT_LOCAL_EXPORT_DIR = PROJECT_ROOT / "tmp" / "kaggle_uploads" / "northstar_v3_feature_export_augmented_20260408"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "runs" / "compendium_separate_scripts_v1"
DEFAULT_VERSION = "apr08_v1"
DEFAULT_TEST_WINDOW_WEEKS = 26
DEFAULT_STEP_WEEKS = 26
DEFAULT_ANCHOR_START = "2019-01-01"
TARGET_COL = "target_weekly_return"
PLAN_INFO = load_plan_info()
EXPERIMENT_CATALOG = load_experiment_catalog()
DEFAULT_FAVORABLE_REGIMES = [
    "Low-Vol Bull",
    "Low-Vol Bear",
    "High-Vol Bear",
    "Sideways",
]
DEFAULT_QUALITY_WEIGHT_RULES = [
    ("2019-01-04", "2022-03-25", 0.35, "pre_safe_era"),
    ("2020-04-01", "2021-09-30", 0.15, "covid_delisting_bias"),
    ("2025-01-01", "2025-09-30", 0.75, "high_membership_drift"),
]
DEFAULT_EXP18_FIXED_EVENTS = ["E004", "E007", "E011", "E012", "E014"]
_CANONICAL_FACTOR_FALLBACKS = {
    "eps_sue_decay": ["eps_sue_decay_cs_z", "eps_sue_decay_cs_rank"],
    "eps_revision_accel": ["combined_revision_score_cs_z"],
    "rev_sue_decay": ["rev_sue_decay_cs_z", "rev_sue_decay_cs_rank"],
    "agreement_score": ["agreement_score_cs_z", "agreement_score_cs_rank"],
    "earnings_quality_ratio": ["earnings_quality_ratio_cs_z", "earnings_quality_ratio_cs_rank", "earnings_quality_ratio"],
    "accruals_ratio": ["accruals_ratio_cs_z", "accruals_ratio_cs_rank", "accruals_ratio"],
    "earnings_quality_ratio_cs_z": ["earnings_quality_ratio", "earnings_quality_ratio_cs_rank"],
    "agreement_score_cs_z": ["agreement_score", "agreement_score_cs_rank"],
    "piotroski_fscore_cs_z": ["piotroski_fscore", "piotroski_fscore_cs_rank"],
    "bulk_net_pressure_21d_cs_z": ["bulk_net_pressure_21d", "bulk_net_pressure_21d_cs_rank"],
}
DEFAULT_CANONICAL_FACTOR_ALIASES = {
    factor: list(_CANONICAL_FACTOR_FALLBACKS.get(factor, []))
    for factor in PLAN_INFO.anchor_factors
}
DOC_ANCHOR_FACTOR_ALIASES = {
    "eps_sue_decay": ["eps_sue_decay_cs_z", "eps_sue_decay_cs_rank"],
    "eps_revision_accel": ["combined_revision_score_cs_z"],
    "rev_sue_decay": ["rev_sue_decay_cs_z", "rev_sue_decay_cs_rank"],
    "agreement_score": ["agreement_score_cs_z", "agreement_score_cs_rank"],
    "earnings_quality_ratio": ["earnings_quality_ratio_cs_z", "earnings_quality_ratio_cs_rank"],
    "accruals_ratio": ["accruals_ratio_cs_z", "accruals_ratio_cs_rank"],
}
KAGGLE_EXPORT_CANDIDATES = [
    Path("/kaggle/input/northstar-v3-feature-export"),
    Path("/kaggle/input/northstar-v3-feature-export-1"),
    Path("/kaggle/input/northstar-v3-feature-export-2"),
]
NON_FEATURE_COLUMNS = {"date", "ticker", TARGET_COL}
COMPENDIUM_REFERENCE = {
    "expected_universe_tickers": 493,
    "expected_feature_matrix_columns": 458,
    "expected_walk_forward_windows": 20,
    "expected_sector_counts": {
        "Financial Services": 95,
        "Information Technology": 48,
        "Capital Goods": 64,
    },
}


def _slugify(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_") or "candidate"


def _normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _numeric_feature_names(frame: pd.DataFrame) -> list[str]:
    names: list[str] = []
    for column in frame.columns:
        if column in NON_FEATURE_COLUMNS:
            continue
        if pd.api.types.is_numeric_dtype(frame[column]):
            names.append(str(column))
    return sorted(dict.fromkeys(names))


def _resolve_export_dir(path: Path | None) -> Path:
    if path is not None:
        return resolve_weekly_export_dir(path).export_dir

    try:
        return resolve_weekly_export_dir(None).export_dir
    except Exception:
        pass

    if DEFAULT_LOCAL_EXPORT_DIR.exists():
        return DEFAULT_LOCAL_EXPORT_DIR.resolve()

    for candidate in KAGGLE_EXPORT_CANDIDATES:
        if candidate.exists():
            return candidate.resolve()

    kaggle_input = Path("/kaggle/input")
    if kaggle_input.exists():
        for feature_path in sorted(kaggle_input.rglob("northstar_features.parquet")):
            return feature_path.parent.resolve()

    raise FileNotFoundError("unable_to_resolve_feature_export_dir")


def _build_parser(exp_id: str, title: str, *, default_profile: str = "full") -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=f"Run {exp_id} - {title}")
    parser.add_argument("--export-dir", type=Path, default=None)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--profile", choices=["smoke", "full"], default=default_profile)
    parser.add_argument("--max-splits", type=int, default=None)
    parser.add_argument("--version", default=DEFAULT_VERSION)
    parser.add_argument("--fresh", action="store_true")
    parser.add_argument("--describe", action="store_true")
    parser.add_argument("--audit-dataset", action="store_true")
    parser.add_argument("--skip-dependencies", action="store_true")
    return parser


def _load_dataset(export_dir: Path) -> PlanDataset:
    return load_plan_dataset(export_dir)


def _load_dataset_for_args(args: argparse.Namespace) -> PlanDataset:
    cached = getattr(args, "_loaded_dataset", None)
    if cached is not None:
        return cached
    resolved = getattr(args, "_resolved_export_dir", None)
    if resolved is None:
        resolved = _resolve_export_dir(args.export_dir)
        args._resolved_export_dir = resolved
    dataset = _load_dataset(resolved)
    args._loaded_dataset = dataset
    return dataset


def _load_script_config(exp_id: str) -> dict[str, Any]:
    exp_num = int(str(exp_id).split("-", 1)[1])
    module_name = f"scripts.kaggle.plan_2026_04_08.run_exp{exp_num:02d}"
    module = importlib.import_module(module_name)
    return dict(getattr(module, "SCRIPT_CONFIG"))


def _collect_dependency_chain(exp_id: str, seen: set[str] | None = None) -> list[str]:
    seen = seen or set()
    ordered: list[str] = []
    spec = EXPERIMENT_CATALOG.get(exp_id)
    for dep_id in list(getattr(spec, "dependencies", ()) or ()):
        ordered.extend(_collect_dependency_chain(dep_id, seen))
        if dep_id not in seen:
            seen.add(dep_id)
            ordered.append(dep_id)
    return ordered


def _feature_frame_with_regimes(dataset: PlanDataset) -> pd.DataFrame:
    regime_cols = ["date", "plan_regime_label", "plan_regime_id", "major_event_id"]
    regime_frame = dataset.regimes[[col for col in regime_cols if col in dataset.regimes.columns]].drop_duplicates("date")
    return dataset.features.merge(regime_frame, on="date", how="left", sort=False)


def _feature_frame_with_meta(dataset: PlanDataset) -> pd.DataFrame:
    meta_cols = [
        "date",
        "ticker",
        "sector",
        "broad_sector",
        "subsector",
        "international_revenue_proxy",
        "oil_sensitivity_score",
        "steel_sensitivity_score",
        "copper_sensitivity_score",
        "gold_sensitivity_score",
        "fx_sensitivity_score",
        "rate_sensitivity_score",
    ]
    meta = dataset.metadata[[col for col in meta_cols if col in dataset.metadata.columns]].drop_duplicates(["date", "ticker"])
    return dataset.features.merge(meta, on=["date", "ticker"], how="left", sort=False)


def _dataset_min_date(dataset: PlanDataset) -> pd.Timestamp:
    return pd.Timestamp(pd.to_datetime(dataset.features["date"], errors="coerce").dropna().min()).normalize()


def _filter_feature_frame(
    dataset: PlanDataset,
    *,
    tickers: list[str] | None = None,
    allowed_regimes: list[str] | None = None,
    feature_frame: pd.DataFrame | None = None,
) -> pd.DataFrame:
    frame = feature_frame.copy() if feature_frame is not None else _feature_frame_with_regimes(dataset)
    if tickers:
        allowed = set(str(ticker) for ticker in tickers)
        frame = frame[frame["ticker"].astype(str).isin(allowed)].copy()
    if allowed_regimes:
        label_set = {_normalize_text(label) for label in allowed_regimes}
        if "plan_regime_label" not in frame.columns:
            frame = _feature_frame_with_regimes(dataset)
            if tickers:
                allowed = set(str(ticker) for ticker in tickers)
                frame = frame[frame["ticker"].astype(str).isin(allowed)].copy()
        labels = frame["plan_regime_label"].astype("string").fillna("").map(_normalize_text)
        frame = frame[labels.isin(label_set)].copy()
    return frame


def _aligned_canonical_splits(
    dataset: PlanDataset,
    years: int,
    *,
    test_weeks: int = DEFAULT_TEST_WINDOW_WEEKS,
    step_weeks: int = DEFAULT_STEP_WEEKS,
) -> list[dict[str, Any]]:
    canonical = list(dataset.splits or [])
    if canonical:
        min_date = _dataset_min_date(dataset)
        train_weeks = max(1, int(years) * 52)
        splits: list[dict[str, Any]] = []
        for split in canonical:
            train_end = pd.Timestamp(split["train_end"]).normalize()
            desired_start = (train_end - pd.Timedelta(weeks=train_weeks - 1)).normalize()
            train_start = max(desired_start, min_date)
            splits.append(
                {
                    "window_id": int(split.get("window_id") or len(splits) + 1),
                    "train_start": str(train_start.date()),
                    "train_end": str(train_end.date()),
                    "test_start": str(pd.Timestamp(split["test_start"]).normalize().date()),
                    "test_end": str(pd.Timestamp(split["test_end"]).normalize().date()),
                }
            )
        return splits

    weekly_dates = (
        pd.to_datetime(dataset.features["date"], errors="coerce")
        .dropna()
        .sort_values()
        .dt.normalize()
        .unique()
        .tolist()
    )
    return generate_anchored_weekly_splits(
        weekly_dates,
        anchor_start=DEFAULT_ANCHOR_START,
        train_weeks=int(years) * 52,
        test_weeks=int(test_weeks),
        step_weeks=int(step_weeks),
        target_windows=0,
    )


def _dataset_default_splits(dataset: PlanDataset) -> list[dict[str, Any]]:
    if dataset.splits:
        return list(dataset.splits)
    return _aligned_canonical_splits(dataset, 2)


def _write_candidate_payload(path: Path, payload: dict[str, Any]) -> None:
    write_json(path, payload)


def _finite_float(value: Any) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return float("nan")
    return numeric if np.isfinite(numeric) else float("nan")


def _model_windows(state: dict[str, Any], model_name: str) -> list[dict[str, Any]]:
    payload = dict((state.get("all_model_results") or {}).get(model_name) or {})
    if not payload:
        payload = dict(state.get(f"{_slugify(model_name)}_results") or {})
    return list(payload.get("windows") or [])


def _window_summary_fallback(state: dict[str, Any], model_name: str) -> dict[str, Any]:
    windows = [window for window in _model_windows(state, model_name) if "error" not in window]
    if not windows:
        return {}

    test_ics = np.asarray([_finite_float(window.get("test_ic")) for window in windows], dtype=float)
    ratios = np.asarray([_finite_float(window.get("train_test_ratio")) for window in windows], dtype=float)
    hit_rates = np.asarray([_finite_float(window.get("hit_rate")) for window in windows], dtype=float)
    spreads = np.asarray([_finite_float(window.get("quintile_spread")) for window in windows], dtype=float)

    def mean_or_nan(values: np.ndarray) -> float:
        clean = values[np.isfinite(values)]
        return float(clean.mean()) if clean.size else float("nan")

    mean_test_ic = mean_or_nan(test_ics)
    std_test_ic = float(np.nanstd(test_ics, ddof=1)) if np.isfinite(test_ics).sum() > 1 else float("nan")
    ic_ir = mean_test_ic / std_test_ic if np.isfinite(mean_test_ic) and np.isfinite(std_test_ic) and abs(std_test_ic) > 1e-12 else 0.0
    return {
        "mean_test_ic": mean_test_ic,
        "mean_train_test_ratio": mean_or_nan(ratios),
        "mean_hit_rate": mean_or_nan(hit_rates),
        "mean_quintile_spread": mean_or_nan(spreads),
        "ic_ir": float(ic_ir),
        "windows_completed": len(windows),
    }


def _run_catboost_candidate(
    *,
    dataset: PlanDataset,
    paths,
    label: str,
    profile: str,
    max_splits: int | None,
    params: dict[str, Any],
    feature_frame: pd.DataFrame | None = None,
    selected_features: list[str] | None = None,
    splits_override: list[dict[str, Any]] | None = None,
    tickers: list[str] | None = None,
    date_min: str | None = None,
    date_max: str | None = None,
    manifest_updates: dict[str, Any] | None = None,
    prepared_export_dir: Path | None = None,
    fresh: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    export_dir = prepared_export_dir or (paths.artifacts_dir / f"{_slugify(label)}_export")
    run_dir = paths.artifacts_dir / f"{_slugify(label)}_run"
    if fresh:
        if run_dir.exists():
            shutil.rmtree(run_dir)
        if prepared_export_dir is None and export_dir.exists():
            shutil.rmtree(export_dir)
    working_frame = feature_frame.copy() if feature_frame is not None else dataset.features.copy()
    working_features = list(selected_features or _numeric_feature_names(working_frame))
    if prepared_export_dir is None:
        prepare_subset_export(
            dataset=dataset,
            output_dir=export_dir,
            selected_features=working_features,
            feature_frame=working_frame,
            splits_override=splits_override,
            ticker_mask=tickers,
            date_min=date_min,
            date_max=date_max,
            manifest_updates=manifest_updates,
        )
    state = run_track_a_model(
        data_dir=export_dir,
        output_dir=run_dir,
        profile=profile,
        max_splits=max_splits,
        model_filter=["catboost"],
        tree_overrides=params,
        resume_from_checkpoint=not fresh,
    )
    summary = summarize_model_state(state, "CatBoost")
    fallback_summary = _window_summary_fallback(state, "CatBoost")
    summary_source = "engine"
    if fallback_summary and not np.isfinite(_finite_float(summary.get("mean_test_ic"))):
        for key, value in fallback_summary.items():
            if key not in summary or not np.isfinite(_finite_float(summary.get(key))):
                summary[key] = value
        summary_source = "window_fallback"
    stability = dict((state.get("all_stabilities") or {}).get("CatBoost") or {})
    promotion_verdict = str(summary.get("verdict") or "")
    display_verdict = (
        "WINDOW_ONLY_DIAGNOSTIC"
        if summary_source == "window_fallback" and promotion_verdict == "INSUFFICIENT_DATA"
        else promotion_verdict
    )
    row = {
        "config_label": label,
        "mean_test_ic": summary.get("mean_test_ic"),
        "mean_train_test_ratio": summary.get("mean_train_test_ratio"),
        "mean_ratio": summary.get("mean_train_test_ratio"),
        "ic_ir": summary.get("ic_ir"),
        "mean_hit_rate": summary.get("mean_hit_rate"),
        "windows_completed": summary.get("windows_completed"),
        "verdict": display_verdict,
        "promotion_verdict": promotion_verdict,
        "summary_source": summary_source,
        "params": dict(params),
        "feature_count": len(working_features),
        "top_features": list(stability.get("top_features_by_mean_importance") or [])[:15],
        "output_dir": str(run_dir),
        "export_dir": str(export_dir),
    }
    return row, state


def _prepare_shared_candidate_export(
    *,
    dataset: PlanDataset,
    paths,
    label: str,
    feature_frame: pd.DataFrame,
    selected_features: list[str],
    splits_override: list[dict[str, Any]] | None = None,
    tickers: list[str] | None = None,
    date_min: str | None = None,
    date_max: str | None = None,
    manifest_updates: dict[str, Any] | None = None,
    fresh: bool = False,
) -> Path:
    export_dir = paths.artifacts_dir / f"{_slugify(label)}_export"
    if fresh and export_dir.exists():
        shutil.rmtree(export_dir)
    if export_dir.exists():
        return export_dir
    prepare_subset_export(
        dataset=dataset,
        output_dir=export_dir,
        selected_features=list(selected_features),
        feature_frame=feature_frame.copy(),
        splits_override=splits_override,
        ticker_mask=tickers,
        date_min=date_min,
        date_max=date_max,
        manifest_updates=manifest_updates,
    )
    return export_dir


def _merged_tree_params(config: dict[str, Any], upstream: dict[str, Any] | None = None) -> dict[str, Any]:
    params = dict(config.get("tree_base_params") or {})
    params.update(dict((upstream or {}).get("params") or {}))
    params.update(dict(config.get("enforced_tree_params") or {}))
    return params


def _ratio_tier(
    row: dict[str, Any],
    *,
    ic_floor: float,
    strong_ratio: float,
    pass_ratio: float,
) -> tuple[float, float, float, float, float]:
    ic = _finite_float(row.get("mean_test_ic"))
    ratio = _finite_float(row.get("mean_train_test_ratio"))
    ic_ir = _finite_float(row.get("ic_ir"))
    meets_ic = float(np.isfinite(ic) and ic >= float(ic_floor))
    strong = float(meets_ic and np.isfinite(ratio) and ratio <= float(strong_ratio))
    passing = float(meets_ic and np.isfinite(ratio) and ratio <= float(pass_ratio))
    ratio_score = -ratio if np.isfinite(ratio) else float("-inf")
    return strong, passing, meets_ic, ratio_score + (ic_ir * 1e-6), ratio


def _select_exp09_best(rows: list[dict[str, Any]], ic_floor: float = 0.020) -> dict[str, Any]:
    if not rows:
        return {}

    def key_fn(row: dict[str, Any]) -> tuple[float, float, float, float, float]:
        strong, passing, meets_ic, ratio_score, _ = _ratio_tier(row, ic_floor=ic_floor, strong_ratio=3.0, pass_ratio=5.0)
        ic = _finite_float(row.get("mean_test_ic"))
        ic_ir = _finite_float(row.get("ic_ir"))
        return (strong, passing, meets_ic, ratio_score, ic + (ic_ir * 1e-3))

    return sorted(rows, key=key_fn, reverse=True)[0]


def _select_exp10_best(rows: list[dict[str, Any]], ic_floor: float = 0.020, ratio_gate: float = 2.5) -> dict[str, Any]:
    if not rows:
        return {}

    def key_fn(row: dict[str, Any]) -> tuple[float, float, float, float, float]:
        ic = _finite_float(row.get("mean_test_ic"))
        ratio = _finite_float(row.get("mean_train_test_ratio"))
        ic_ir = _finite_float(row.get("ic_ir"))
        meets_ic = float(np.isfinite(ic) and ic >= float(ic_floor))
        passing = float(meets_ic and np.isfinite(ratio) and ratio <= float(ratio_gate))
        fallback_ratio = -ratio if np.isfinite(ratio) else float("-inf")
        return (passing, meets_ic, ic, fallback_ratio, ic_ir)

    return sorted(rows, key=key_fn, reverse=True)[0]


def _select_exp12_best(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {}
    by_year = {int(row.get("window_years")): row for row in rows if row.get("window_years") is not None}
    current = by_year.get(2)
    if not current:
        return pick_best_candidate(rows) or rows[0]
    current_ic = _finite_float(current.get("mean_test_ic"))
    current_ratio = _finite_float(current.get("mean_train_test_ratio"))
    viable: list[dict[str, Any]] = []
    for years in [3, 4]:
        row = by_year.get(years)
        if not row:
            continue
        ic = _finite_float(row.get("mean_test_ic"))
        ratio = _finite_float(row.get("mean_train_test_ratio"))
        if np.isfinite(ratio) and np.isfinite(current_ratio) and ratio < current_ratio:
            if not np.isfinite(current_ic) or (np.isfinite(ic) and ic >= current_ic - 0.003):
                viable.append(row)
    if viable:
        return sorted(
            viable,
            key=lambda row: (
                _finite_float(row.get("mean_test_ic")),
                -_finite_float(row.get("mean_train_test_ratio")),
                _finite_float(row.get("ic_ir")),
            ),
            reverse=True,
        )[0]
    return current


def _resolve_feature_contract(
    columns: list[str],
    *,
    required: list[str] | None = None,
    proxy_map: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    required = list(required or [])
    proxy_map = {str(key): list(value or []) for key, value in dict(proxy_map or {}).items()}
    resolved_required = [name for name in required if name in columns]
    missing_required = [name for name in required if name not in columns]
    resolved_proxies: dict[str, str] = {}
    missing_proxies: list[str] = []
    for logical_name, candidates in proxy_map.items():
        resolved = _resolve_first_existing(columns, list(candidates))
        if resolved:
            resolved_proxies[logical_name] = resolved
        else:
            missing_proxies.append(logical_name)
    exact = not missing_required and not missing_proxies
    return {
        "required_requested": required,
        "required_available": resolved_required,
        "required_missing": missing_required,
        "proxy_candidates": proxy_map,
        "proxy_resolved": resolved_proxies,
        "proxy_missing": missing_proxies,
        "status": "exact" if exact else "partial_dataset_gap",
    }


def _build_reduced_feature_bundle(
    feature_frame: pd.DataFrame,
    *,
    base_feature_pool: list[str],
    reduced_feature_count: int,
    required_features: list[str] | None = None,
    proxy_map: dict[str, list[str]] | None = None,
    exclude_regex: str | None = DEFAULT_REDUCED_EXCLUDE_REGEX,
    min_abs_ic: float = 0.005,
) -> tuple[list[str], dict[str, Any]]:
    numeric_columns = _numeric_feature_names(feature_frame)
    base_numeric = [name for name in base_feature_pool if name in numeric_columns]
    analyzer = FactorICAnalyzer()
    ic_table = analyzer.compute_ic_table(
        feature_frame[["date", TARGET_COL] + base_numeric].copy(),
        base_numeric,
    )
    reduced = top_ic_feature_names(
        ic_table,
        base_numeric,
        limit=int(reduced_feature_count),
        min_abs_ic=float(min_abs_ic),
        exclude_regex=exclude_regex,
    )
    contract = _resolve_feature_contract(
        numeric_columns,
        required=list(required_features or []),
        proxy_map=dict(proxy_map or {}),
    )
    selected = list(reduced)
    for name in contract["required_available"]:
        if name not in selected:
            selected.append(name)
    for name in contract["proxy_resolved"].values():
        if name not in selected:
            selected.append(name)
    contract["reduced_feature_count_target"] = int(reduced_feature_count)
    contract["reduced_feature_count_actual"] = len(reduced)
    contract["reduced_feature_names"] = list(reduced)
    contract["selected_feature_count"] = len(selected)
    contract["selected_features"] = list(selected)
    contract["top_base_features"] = ic_table.head(20).to_dict(orient="records")
    return selected, contract


def _finalize_experiment(
    *,
    paths,
    exp_id: str,
    title: str,
    hypothesis: str,
    rows: list[dict[str, Any]],
    best_candidate: dict[str, Any] | None = None,
    notes: list[str] | None = None,
    extra_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    frame = pd.DataFrame(rows)
    if not frame.empty:
        write_table(paths.experiment_root / "candidate_table.csv", frame)
    best = dict(best_candidate or {}) or pick_best_candidate(rows) or (rows[0] if rows else {})
    payload: dict[str, Any] = {
        "exp_id": exp_id,
        "title": title,
        "hypothesis": hypothesis,
        "candidate_count": len(rows),
        "best_candidate": best,
        "candidates": rows,
    }
    if extra_payload:
        payload.update(extra_payload)
    write_json(paths.summary_path, payload)
    write_narrative(
        paths.narrative_path,
        exp_id=exp_id,
        title=title,
        hypothesis=hypothesis,
        metrics={
            "candidate_count": len(rows),
            "best_mean_test_ic": best.get("mean_test_ic"),
            "best_mean_train_test_ratio": best.get("mean_train_test_ratio"),
            "best_config_label": best.get("config_label"),
            "best_params": best.get("params"),
        },
        extra_notes=notes or [],
    )
    return payload


def _load_upstream_best(
    *,
    output_root: Path,
    version: str,
    dependency_ids: list[str],
    fallback: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    for exp_id in dependency_ids:
        payload = load_summary_if_exists(output_root, exp_id, version)
        candidate = dict((payload or {}).get("best_candidate") or {})
        if candidate:
            return candidate, exp_id
    return dict(fallback), "fallback"


def _metadata_lookup(dataset: PlanDataset) -> pd.DataFrame:
    meta_cols = [col for col in ["ticker", "sector", "subsector", "broad_sector"] if col in dataset.metadata.columns]
    return dataset.metadata[meta_cols].drop_duplicates("ticker").copy()


def _tickers_from_mask(lookup: pd.DataFrame, mask: pd.Series) -> list[str]:
    return sorted(lookup.loc[mask, "ticker"].dropna().astype(str).unique().tolist())


def resolve_financial_services_universes(dataset: PlanDataset) -> dict[str, list[str]]:
    lookup = _metadata_lookup(dataset)
    broad_lower = lookup.get("broad_sector", pd.Series("", index=lookup.index)).astype("string").fillna("").str.lower()
    sector_lower = lookup.get("sector", pd.Series("", index=lookup.index)).astype("string").fillna("").str.lower()
    subsector_lower = lookup.get("subsector", pd.Series("", index=lookup.index)).astype("string").fillna("").str.lower()
    include_mask = (
        broad_lower.eq("financial services")
        | sector_lower.str.contains("financial services", na=False)
        | subsector_lower.str.contains(
            r"\bbank|insurance|finance|housing finance|gold loan|broking|wealth|payments|exchange|asset management|lending",
            regex=True,
            na=False,
        )
    )
    exclude_mask = subsector_lower.str.contains("banking software|bfsi it|it services|insurance & travel focus", na=False)
    full_fs = _tickers_from_mask(lookup, include_mask & ~exclude_mask)
    banks = _tickers_from_mask(
        lookup,
        (include_mask & ~exclude_mask)
        & subsector_lower.str.contains(r"\bbank|small finance bank|private sector bank|public sector bank", regex=True, na=False),
    )
    nbfcs = _tickers_from_mask(
        lookup,
        (include_mask & ~exclude_mask)
        & subsector_lower.str.contains(
            r"nbfc|housing finance|consumer finance|gold loan|commercial vehicle.*finance|diversified financial",
            regex=True,
            na=False,
        ),
    )
    lenders = _tickers_from_mask(
        lookup,
        (include_mask & ~exclude_mask)
        & subsector_lower.str.contains(r"\bbank|nbfc|finance|housing finance|gold loan|vehicle finance|lending", regex=True, na=False),
    )
    insurance = _tickers_from_mask(lookup, (include_mask & ~exclude_mask) & subsector_lower.str.contains("insurance", na=False))
    other_financials = sorted(set(full_fs) - set(lenders) - set(insurance))
    return {
        "full_fs": full_fs,
        "banks": banks,
        "nbfcs": nbfcs,
        "lenders": lenders,
        "insurance": insurance,
        "other_financials": other_financials,
    }


def resolve_it_tickers(dataset: PlanDataset) -> list[str]:
    lookup = _metadata_lookup(dataset)
    broad_lower = lookup.get("broad_sector", pd.Series("", index=lookup.index)).astype("string").fillna("").str.lower()
    sector_lower = lookup.get("sector", pd.Series("", index=lookup.index)).astype("string").fillna("").str.lower()
    subsector_lower = lookup.get("subsector", pd.Series("", index=lookup.index)).astype("string").fillna("").str.lower()
    mask = broad_lower.eq("information technology") | (
        broad_lower.eq("") & (
            sector_lower.str.contains("information technology", na=False)
            | subsector_lower.str.contains("it services|software|kpo|bpo|technology", na=False)
        )
    )
    return _tickers_from_mask(lookup, mask)


def resolve_capital_goods_tickers(dataset: PlanDataset) -> list[str]:
    lookup = _metadata_lookup(dataset)
    broad_lower = lookup.get("broad_sector", pd.Series("", index=lookup.index)).astype("string").fillna("").str.lower()
    sector_lower = lookup.get("sector", pd.Series("", index=lookup.index)).astype("string").fillna("").str.lower()
    subsector_lower = lookup.get("subsector", pd.Series("", index=lookup.index)).astype("string").fillna("").str.lower()
    mask = broad_lower.eq("capital goods") | (
        broad_lower.eq("") & (
            sector_lower.str.contains("capital goods", na=False)
            | subsector_lower.str.contains(
                "capital goods|industrial|engineering|automation|defence|construction equipment|electrical equipment|cables|bearings|castings|conductors|aerospace",
                na=False,
            )
        )
    )
    return _tickers_from_mask(lookup, mask)


def _resolve_first_existing(columns: list[str], candidates: list[str]) -> str | None:
    lookup = {str(column).lower(): str(column) for column in columns}
    for candidate in candidates:
        resolved = lookup.get(candidate.lower())
        if resolved:
            return resolved
    return None


def _standalone_ic(frame: pd.DataFrame, feature_name: str | None) -> float:
    if not feature_name or feature_name not in frame.columns:
        return float("nan")
    summary = summarize_ic_series(compute_ic_series(frame, feature_name))
    return float(summary.get("mean_ic", float("nan")))


def _event_windows_from_dataset(dataset: PlanDataset) -> dict[str, tuple[pd.Timestamp, pd.Timestamp]]:
    frame = dataset.regimes.copy()
    if "major_event_id" not in frame.columns:
        return {}
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    windows: dict[str, tuple[pd.Timestamp, pd.Timestamp]] = {}
    for event_id, group in frame.dropna(subset=["major_event_id"]).groupby(frame["major_event_id"].astype(str), sort=True):
        windows[str(event_id)] = (
            pd.Timestamp(group["date"].min()).normalize(),
            pd.Timestamp(group["date"].max()).normalize(),
        )
    return windows


def _custom_split(
    *,
    train_start: Any,
    train_end: Any,
    test_start: Any,
    test_end: Any,
) -> list[dict[str, Any]]:
    return [
        {
            "window_id": 1,
            "train_start": str(pd.Timestamp(train_start).normalize().date()),
            "train_end": str(pd.Timestamp(train_end).normalize().date()),
            "test_start": str(pd.Timestamp(test_start).normalize().date()),
            "test_end": str(pd.Timestamp(test_end).normalize().date()),
        }
    ]


def _normal_window_for_event(start: pd.Timestamp, end: pd.Timestamp) -> tuple[pd.Timestamp, pd.Timestamp]:
    n_weeks = max(1, int(((end - start).days // 7) + 1))
    normal_end = start - pd.Timedelta(days=7)
    normal_start = normal_end - pd.Timedelta(weeks=n_weeks - 1)
    return normal_start.normalize(), normal_end.normalize()


def _collapse_score(event_ic: float, normal_ic: float) -> float:
    if not np.isfinite(event_ic) or not np.isfinite(normal_ic) or abs(normal_ic) < 1e-6:
        return float("nan")
    value = 1.0 - (float(event_ic) / float(normal_ic))
    return float(np.clip(value, 0.0, 1.5))


def _retention_score(event_ic: float, normal_ic: float) -> float:
    if not np.isfinite(event_ic) or not np.isfinite(normal_ic) or abs(normal_ic) < 1e-6:
        return float("nan")
    return float(event_ic / normal_ic)


def _split_by_rate_state(feature_frame: pd.DataFrame) -> dict[str, pd.DataFrame]:
    rate_feature = _resolve_first_existing(
        list(feature_frame.columns),
        ["rbi_repo_rate_change_13w", "rbi_rate_chg"],
    )
    if not rate_feature:
        return {}
    values = pd.to_numeric(feature_frame[rate_feature], errors="coerce")
    return {
        "rate_hike": feature_frame[values > 0].copy(),
        "rate_cut": feature_frame[values < 0].copy(),
        "rate_hold": feature_frame[values.fillna(0.0) == 0.0].copy(),
    }


def _resolve_it_proxy_groups(feature_frame: pd.DataFrame) -> dict[str, list[str]]:
    intl = pd.to_numeric(
        feature_frame.get("international_revenue_proxy", pd.Series(0.0, index=feature_frame.index)),
        errors="coerce",
    ).fillna(0.0)
    fx = pd.to_numeric(
        feature_frame.get("fx_sensitivity_score", pd.Series(0.0, index=feature_frame.index)),
        errors="coerce",
    ).fillna(0.0)
    exposure = pd.concat([intl, fx], axis=1).max(axis=1)
    offshore = sorted(feature_frame.loc[exposure > 0.5, "ticker"].dropna().astype(str).unique().tolist())
    domestic = sorted(feature_frame.loc[exposure <= 0.0, "ticker"].dropna().astype(str).unique().tolist())
    return {"offshore_heavy": offshore, "domestic_heavy": domestic}


def _augment_sector_identity_and_conditionals(
    dataset: PlanDataset,
    *,
    conditional_sectors: list[str],
    base_features: list[str],
) -> tuple[pd.DataFrame, list[str], list[str], list[str]]:
    merged = _feature_frame_with_meta(dataset)
    sector_series = merged.get("broad_sector", pd.Series("Other", index=merged.index)).astype("string").fillna("Other")
    indicator_features: list[str] = []
    for sector_name in sorted(sector_series.dropna().astype(str).unique().tolist()):
        indicator_name = f"plan_sector_is_{_slugify(sector_name)}"
        merged[indicator_name] = sector_series.map(lambda value: 1.0 if str(value) == sector_name else 0.0)
        indicator_features.append(indicator_name)
    added_features = list(indicator_features)
    missing_base = [feature for feature in base_features if feature not in merged.columns]
    for sector_name in conditional_sectors:
        indicator_name = f"plan_sector_is_{_slugify(sector_name)}"
        if indicator_name not in merged.columns:
            continue
        for feature in base_features:
            if feature not in merged.columns:
                continue
            interaction_name = f"{feature}__{_slugify(sector_name)}"
            merged[interaction_name] = (
                pd.to_numeric(merged[feature], errors="coerce").fillna(0.0)
                * pd.to_numeric(merged[indicator_name], errors="coerce").fillna(0.0)
            )
            added_features.append(interaction_name)
    return merged.drop(columns=["broad_sector"], errors="ignore"), added_features, indicator_features, missing_base


def run_exp09(args: argparse.Namespace, config: dict[str, Any]) -> dict[str, Any]:
    dataset = _load_dataset(_resolve_export_dir(args.export_dir))
    paths = make_experiment_paths(args.output_root, "EXP-09", args.version)
    rows: list[dict[str, Any]] = []
    shared_exports: dict[int, Path] = {}
    feature_frame = dataset.features.copy()
    selected_features = _numeric_feature_names(feature_frame)
    for spec in list(config.get("candidate_grid") or []):
        label = str(spec["label"])
        params = dict(config.get("tree_base_params") or {})
        params.update(dict(spec.get("params") or {}))
        window_years = int(spec.get("window_years") or config.get("train_window_years") or 2)
        if window_years not in shared_exports:
            shared_exports[window_years] = _prepare_shared_candidate_export(
                dataset=dataset,
                paths=paths,
                label=f"shared_window_{window_years}yr",
                feature_frame=feature_frame,
                selected_features=selected_features,
                splits_override=_aligned_canonical_splits(dataset, window_years),
                manifest_updates={
                    "plan_experiment": "EXP-09",
                    "shared_export_for": f"window_years_{window_years}",
                    "train_window_years": window_years,
                    "split_strategy": "aligned_canonical_test_windows",
                },
                fresh=args.fresh,
            )
        row, _ = _run_catboost_candidate(
            dataset=dataset,
            paths=paths,
            label=label,
            profile=args.profile,
            max_splits=args.max_splits,
            params=params,
            feature_frame=feature_frame,
            selected_features=selected_features,
            prepared_export_dir=shared_exports[window_years],
            fresh=args.fresh,
        )
        row["window_years"] = window_years
        row["split_strategy"] = "aligned_canonical_test_windows"
        row["notes"] = str(spec.get("notes") or "")
        _write_candidate_payload(paths.artifacts_dir / f"{_slugify(label)}_summary.json", row)
        rows.append(row)
    best = _select_exp09_best(rows, ic_floor=float(config.get("ic_floor") or 0.020))
    return _finalize_experiment(
        paths=paths,
        exp_id="EXP-09",
        title=str(config["title"]),
        hypothesis=str(config["hypothesis"]),
        rows=rows,
        best_candidate=best,
        notes=[
            "This script uses the compendium's 9-cell depth x early-stopping grid.",
            "Training windows are rebuilt as 2-year lookbacks aligned to the export's 20 canonical test windows so the comparisons stay apples-to-apples.",
        ],
        extra_payload={
            "ic_floor": float(config.get("ic_floor") or 0.020),
            "pass_ratio": 5.0,
            "strong_pass_ratio": 3.0,
        },
    )


def run_exp10(args: argparse.Namespace, config: dict[str, Any]) -> dict[str, Any]:
    dataset = _load_dataset(_resolve_export_dir(args.export_dir))
    paths = make_experiment_paths(args.output_root, "EXP-10", args.version)
    upstream, upstream_source = _load_upstream_best(
        output_root=args.output_root,
        version=args.version,
        dependency_ids=["EXP-09"],
        fallback=dict(config.get("fallback_upstream") or {}),
    )
    base_params = _merged_tree_params(config, upstream)
    rows: list[dict[str, Any]] = []
    window_years = int((upstream or {}).get("window_years") or config.get("fallback_window_years") or 2)
    feature_frame = dataset.features.copy()
    selected_features = _numeric_feature_names(feature_frame)
    shared_export = _prepare_shared_candidate_export(
        dataset=dataset,
        paths=paths,
        label=f"shared_l2_window_{window_years}yr",
        feature_frame=feature_frame,
        selected_features=selected_features,
        splits_override=_aligned_canonical_splits(dataset, window_years),
        manifest_updates={
            "plan_experiment": "EXP-10",
            "shared_export_for": f"window_years_{window_years}",
            "upstream_source": upstream_source,
            "train_window_years": window_years,
        },
        fresh=args.fresh,
    )
    for l2_value in list(config.get("l2_grid") or []):
        label = f"l2_{str(l2_value).replace('.', '_')}"
        params = dict(base_params)
        params["l2_leaf_reg"] = float(l2_value)
        row, _ = _run_catboost_candidate(
            dataset=dataset,
            paths=paths,
            label=label,
            profile=args.profile,
            max_splits=args.max_splits,
            params=params,
            feature_frame=feature_frame,
            selected_features=selected_features,
            prepared_export_dir=shared_export,
            fresh=args.fresh,
        )
        row["l2_leaf_reg"] = float(l2_value)
        row["window_years"] = window_years
        rows.append(row)
    best = _select_exp10_best(
        rows,
        ic_floor=float(config.get("ic_floor") or 0.020),
        ratio_gate=float(config.get("ratio_gate") or 2.5),
    )
    pareto = [
        row for row in rows
        if _finite_float(row.get("mean_test_ic")) >= float(config.get("ic_floor") or 0.020)
        and _finite_float(row.get("mean_train_test_ratio")) <= float(config.get("ratio_gate") or 2.5)
    ]
    return _finalize_experiment(
        paths=paths,
        exp_id="EXP-10",
        title=str(config["title"]),
        hypothesis=str(config["hypothesis"]),
        rows=rows,
        best_candidate=best,
        notes=[f"Upstream base configuration source: {upstream_source}."],
        extra_payload={
            "upstream_source": upstream_source,
            "ratio_gate": float(config.get("ratio_gate") or 2.5),
            "ic_floor": float(config.get("ic_floor") or 0.020),
            "pareto_frontier": pareto,
        },
    )


def run_exp11(args: argparse.Namespace, config: dict[str, Any]) -> dict[str, Any]:
    dataset = _load_dataset(_resolve_export_dir(args.export_dir))
    paths = make_experiment_paths(args.output_root, "EXP-11", args.version)
    upstream, upstream_source = _load_upstream_best(
        output_root=args.output_root,
        version=args.version,
        dependency_ids=["EXP-10", "EXP-09"],
        fallback=dict(config.get("fallback_upstream") or {}),
    )
    base_params = _merged_tree_params(config, upstream)
    rows: list[dict[str, Any]] = []
    window_years = int((upstream or {}).get("window_years") or config.get("fallback_window_years") or 2)
    feature_frame = dataset.features.copy()
    selected_features = _numeric_feature_names(feature_frame)
    shared_export = _prepare_shared_candidate_export(
        dataset=dataset,
        paths=paths,
        label=f"shared_boosting_window_{window_years}yr",
        feature_frame=feature_frame,
        selected_features=selected_features,
        splits_override=_aligned_canonical_splits(dataset, window_years),
        manifest_updates={
            "plan_experiment": "EXP-11",
            "shared_export_for": f"window_years_{window_years}",
            "upstream_source": upstream_source,
            "train_window_years": window_years,
        },
        fresh=args.fresh,
    )
    for spec in list(config.get("boosting_grid") or []):
        label = str(spec["label"])
        params = dict(base_params)
        params.update(dict(spec.get("params") or {}))
        row, _ = _run_catboost_candidate(
            dataset=dataset,
            paths=paths,
            label=label,
            profile=args.profile,
            max_splits=args.max_splits,
            params=params,
            feature_frame=feature_frame,
            selected_features=selected_features,
            prepared_export_dir=shared_export,
            fresh=args.fresh,
        )
        row["window_years"] = window_years
        rows.append(row)
    by_label = {str(row.get("config_label")): row for row in rows}
    ordered = by_label.get("ordered")
    plain = by_label.get("plain")
    plain_passes = False
    if ordered and plain:
        ordered_ratio = _finite_float(ordered.get("mean_train_test_ratio"))
        ordered_ic = _finite_float(ordered.get("mean_test_ic"))
        plain_ratio = _finite_float(plain.get("mean_train_test_ratio"))
        plain_ic = _finite_float(plain.get("mean_test_ic"))
        plain_passes = bool(
            np.isfinite(plain_ratio)
            and np.isfinite(ordered_ratio)
            and plain_ratio <= ordered_ratio
            and (
                (np.isfinite(plain_ic) and np.isfinite(ordered_ic) and plain_ic >= ordered_ic - 0.005)
                or (np.isfinite(plain_ic) and not np.isfinite(ordered_ic))
            )
        )
    best = dict(plain if plain_passes and plain else ordered or plain or (rows[0] if rows else {}))
    return _finalize_experiment(
        paths=paths,
        exp_id="EXP-11",
        title=str(config["title"]),
        hypothesis=str(config["hypothesis"]),
        rows=rows,
        best_candidate=best,
        notes=[
            f"Upstream base configuration source: {upstream_source}.",
            "Only boosting_type changes here; all other CatBoost parameters are inherited from the EXP-10 winner.",
        ],
        extra_payload={"upstream_source": upstream_source, "plain_passes": plain_passes},
    )


def run_exp12(args: argparse.Namespace, config: dict[str, Any]) -> dict[str, Any]:
    dataset = _load_dataset(_resolve_export_dir(args.export_dir))
    paths = make_experiment_paths(args.output_root, "EXP-12", args.version)
    upstream, upstream_source = _load_upstream_best(
        output_root=args.output_root,
        version=args.version,
        dependency_ids=["EXP-11", "EXP-10", "EXP-09"],
        fallback=dict(config.get("fallback_upstream") or {}),
    )
    base_params = _merged_tree_params(config, upstream)
    rows: list[dict[str, Any]] = []
    feature_frame = dataset.features.copy()
    selected_features = _numeric_feature_names(feature_frame)
    shared_exports: dict[int, Path] = {}
    for years in list(config.get("window_years_grid") or []):
        label = f"train_window_{int(years)}yr"
        if int(years) not in shared_exports:
            shared_exports[int(years)] = _prepare_shared_candidate_export(
                dataset=dataset,
                paths=paths,
                label=f"shared_train_window_{int(years)}yr",
                feature_frame=feature_frame,
                selected_features=selected_features,
                splits_override=_aligned_canonical_splits(dataset, int(years)),
                manifest_updates={
                    "plan_experiment": "EXP-12",
                    "shared_export_for": f"window_years_{int(years)}",
                    "upstream_source": upstream_source,
                    "train_window_years": int(years),
                },
                fresh=args.fresh,
            )
        row, _ = _run_catboost_candidate(
            dataset=dataset,
            paths=paths,
            label=label,
            profile=args.profile,
            max_splits=args.max_splits,
            params=dict(base_params),
            feature_frame=feature_frame,
            selected_features=selected_features,
            prepared_export_dir=shared_exports[int(years)],
            fresh=args.fresh,
        )
        row["window_years"] = int(years)
        rows.append(row)
    best = _select_exp12_best(rows)
    return _finalize_experiment(
        paths=paths,
        exp_id="EXP-12",
        title=str(config["title"]),
        hypothesis=str(config["hypothesis"]),
        rows=rows,
        best_candidate=best,
        notes=[f"Upstream base configuration source: {upstream_source}."],
        extra_payload={"upstream_source": upstream_source},
    )


def run_exp13(args: argparse.Namespace, config: dict[str, Any]) -> dict[str, Any]:
    dataset = _load_dataset(_resolve_export_dir(args.export_dir))
    paths = make_experiment_paths(args.output_root, "EXP-13", args.version)
    upstream, upstream_source = _load_upstream_best(
        output_root=args.output_root,
        version=args.version,
        dependency_ids=["EXP-12", "EXP-11", "EXP-10", "EXP-09"],
        fallback=dict(config.get("fallback_upstream") or {}),
    )
    base_params = _merged_tree_params(config, upstream)
    universes = resolve_financial_services_universes(dataset)
    if not universes["full_fs"]:
        raise RuntimeError("EXP-13 could not resolve the Financial Services universe from metadata.")
    full_frame = _filter_feature_frame(dataset, tickers=universes["full_fs"], feature_frame=_feature_frame_with_meta(dataset))
    feature_only_frame = full_frame[dataset.features.columns.intersection(full_frame.columns).tolist()].copy()
    selected_features, feature_contract = _build_reduced_feature_bundle(
        full_frame,
        base_feature_pool=_numeric_feature_names(dataset.features),
        reduced_feature_count=int(config.get("reduced_feature_count") or 60),
        required_features=list(config.get("required_fs_features") or []),
        proxy_map=dict(config.get("proxy_fs_features") or {}),
    )

    rows: list[dict[str, Any]] = []
    manifest_rows: list[dict[str, Any]] = []

    baseline_row, _ = _run_catboost_candidate(
        dataset=dataset,
        paths=paths,
        label="full_fs_baseline_same_tickers",
        profile=args.profile,
        max_splits=args.max_splits,
        params=dict(base_params),
        feature_frame=feature_only_frame,
        selected_features=_numeric_feature_names(feature_only_frame),
        manifest_updates={"plan_experiment": "EXP-13", "sub_universe": "full_fs", "variant": "baseline_same_tickers"},
        fresh=args.fresh,
    )
    baseline_row["sub_universe"] = "full_fs"
    baseline_row["variant"] = "baseline_same_tickers"
    baseline_row["ticker_count"] = len(universes["full_fs"])
    rows.append(baseline_row)
    manifest_rows.append(
        {
            "sub_universe": "full_fs",
            "variant": "baseline_same_tickers",
            "ticker_count": len(universes["full_fs"]),
            "tickers": list(universes["full_fs"]),
        }
    )

    sector_row, _ = _run_catboost_candidate(
        dataset=dataset,
        paths=paths,
        label="full_fs_sector_reduced_plus_fs_extras",
        profile=args.profile,
        max_splits=args.max_splits,
        params=dict(base_params),
        feature_frame=full_frame,
        selected_features=selected_features,
        manifest_updates={"plan_experiment": "EXP-13", "sub_universe": "full_fs", "variant": "sector_reduced_plus_fs_extras"},
        fresh=args.fresh,
    )
    sector_row["sub_universe"] = "full_fs"
    sector_row["variant"] = "sector_reduced_plus_fs_extras"
    sector_row["ticker_count"] = len(universes["full_fs"])
    sector_row["feature_contract_status"] = feature_contract["status"]
    sector_row["missing_required_features"] = list(feature_contract["required_missing"])
    sector_row["resolved_proxy_features"] = dict(feature_contract["proxy_resolved"])
    sector_row["baseline_ic_delta"] = _finite_float(sector_row.get("mean_test_ic")) - _finite_float(baseline_row.get("mean_test_ic"))
    rows.append(sector_row)
    manifest_rows.append(
        {
            "sub_universe": "full_fs",
            "variant": "sector_reduced_plus_fs_extras",
            "ticker_count": len(universes["full_fs"]),
            "tickers": list(universes["full_fs"]),
            "feature_contract_status": feature_contract["status"],
            "missing_required_features": list(feature_contract["required_missing"]),
            "resolved_proxy_features": dict(feature_contract["proxy_resolved"]),
        }
    )

    rate_state_rows: list[dict[str, Any]] = []
    for state_name, state_frame in _split_by_rate_state(full_frame).items():
        if state_frame.empty or state_frame["date"].nunique() < 8:
            rate_state_rows.append({"sub_universe": "full_fs", "variant": state_name, "status": "SKIPPED"})
            continue
        row, _ = _run_catboost_candidate(
            dataset=dataset,
            paths=paths,
            label=f"full_fs_{state_name}",
            profile=args.profile,
            max_splits=args.max_splits,
            params=dict(base_params),
            feature_frame=state_frame,
            selected_features=selected_features,
            manifest_updates={"plan_experiment": "EXP-13", "sub_universe": "full_fs", "variant": state_name},
            fresh=args.fresh,
        )
        row["sub_universe"] = "full_fs"
        row["variant"] = state_name
        row["ticker_count"] = len(universes["full_fs"])
        row["state_date_count"] = int(state_frame["date"].nunique())
        rate_state_rows.append(row)
    rows.extend(rate_state_rows)

    contingency_threshold = float(config.get("contingency_ic_threshold") or 0.020)
    contingency_triggered = bool(_finite_float(sector_row.get("mean_test_ic")) < contingency_threshold)
    contingency_rows: list[dict[str, Any]] = []
    min_tickers_by_universe = {str(key): int(value) for key, value in dict(config.get("min_tickers_by_universe") or {}).items()}
    if contingency_triggered:
        for sub_name in ["lenders", "other_financials", "banks", "nbfcs", "insurance"]:
            tickers = list(universes.get(sub_name) or [])
            minimum_tickers = int(min_tickers_by_universe.get(sub_name, config.get("min_sub_universe_tickers") or 20))
            if len(tickers) < minimum_tickers:
                contingency_rows.append({"sub_universe": sub_name, "status": "SKIPPED", "ticker_count": len(tickers)})
                continue
            sub_frame = _filter_feature_frame(dataset, tickers=tickers, feature_frame=_feature_frame_with_meta(dataset))
            sub_selected, sub_contract = _build_reduced_feature_bundle(
                sub_frame,
                base_feature_pool=_numeric_feature_names(dataset.features),
                reduced_feature_count=int(config.get("reduced_feature_count") or 60),
                required_features=list(config.get("required_fs_features") or []),
                proxy_map=dict(config.get("proxy_fs_features") or {}),
            )
            row, _ = _run_catboost_candidate(
                dataset=dataset,
                paths=paths,
                label=f"{sub_name}_sector_reduced_plus_fs_extras",
                profile=args.profile,
                max_splits=args.max_splits,
                params=dict(base_params),
                feature_frame=sub_frame,
                selected_features=sub_selected,
                manifest_updates={"plan_experiment": "EXP-13", "sub_universe": sub_name, "variant": "contingency_split"},
                fresh=args.fresh,
            )
            row["sub_universe"] = sub_name
            row["variant"] = "contingency_split"
            row["ticker_count"] = len(tickers)
            row["feature_contract_status"] = sub_contract["status"]
            row["missing_required_features"] = list(sub_contract["required_missing"])
            contingency_rows.append(row)
            manifest_rows.append(
                {
                    "sub_universe": sub_name,
                    "variant": "contingency_split",
                    "ticker_count": len(tickers),
                    "tickers": list(tickers),
                    "feature_contract_status": sub_contract["status"],
                    "missing_required_features": list(sub_contract["required_missing"]),
                }
            )
    rows.extend(contingency_rows)

    best_fs = sector_row
    best_lenders = pick_best_candidate([row for row in contingency_rows if row.get("sub_universe") == "lenders"]) or {}
    payload = _finalize_experiment(
        paths=paths,
        exp_id="EXP-13",
        title=str(config["title"]),
        hypothesis=str(config["hypothesis"]),
        rows=rows,
        best_candidate=pick_best_candidate([sector_row, *contingency_rows]) or sector_row,
        notes=[
            f"Upstream broad-universe configuration source: {upstream_source}.",
            "The main comparison is now baseline-on-the-same-tickers versus reduced-60 plus Financial Services extras.",
            "Banks/NBFC/insurance/lenders only run as a contingency if the full Financial Services sector model misses the compendium's 0.020 IC trigger.",
        ],
        extra_payload={
            "feature_contract": feature_contract,
            "contingency_triggered": contingency_triggered,
            "contingency_ic_threshold": contingency_threshold,
            "finance_universes": {key: len(value) for key, value in universes.items()},
            "best_full_fs_candidate": best_fs,
            "best_lenders_candidate": best_lenders,
        },
    )
    write_table(paths.experiment_root / "finance_subuniverse_table.csv", pd.DataFrame(rows))
    write_json(
        paths.experiment_root / "sector_subset_manifest.json",
        {
            "experiment": "EXP-13",
            "feature_contract": feature_contract,
            "universes": {key: {"ticker_count": len(value), "tickers": list(value)} for key, value in universes.items()},
            "candidate_subsets": manifest_rows,
        },
    )
    return payload


def run_exp14(args: argparse.Namespace, config: dict[str, Any]) -> dict[str, Any]:
    dataset = _load_dataset(_resolve_export_dir(args.export_dir))
    paths = make_experiment_paths(args.output_root, "EXP-14", args.version)
    upstream, upstream_source = _load_upstream_best(
        output_root=args.output_root,
        version=args.version,
        dependency_ids=["EXP-12", "EXP-11", "EXP-10", "EXP-09"],
        fallback=dict(config.get("fallback_upstream") or {}),
    )
    base_params = _merged_tree_params(config, upstream)
    tickers = resolve_it_tickers(dataset)
    if not tickers:
        raise RuntimeError("EXP-14 could not resolve any Information Technology tickers from metadata.")
    frame = _filter_feature_frame(dataset, tickers=tickers, feature_frame=_feature_frame_with_meta(dataset))
    feature_only_frame = frame[dataset.features.columns.intersection(frame.columns).tolist()].copy()
    selected_features, feature_contract = _build_reduced_feature_bundle(
        frame,
        base_feature_pool=_numeric_feature_names(dataset.features),
        reduced_feature_count=int(config.get("reduced_feature_count") or 60),
        required_features=list(config.get("required_it_features") or []),
        proxy_map=dict(config.get("proxy_it_features") or {}),
    )
    rows: list[dict[str, Any]] = []
    anchor_feature = _resolve_first_existing(list(frame.columns), list(config.get("anchor_feature_candidates") or []))
    if not anchor_feature:
        raise RuntimeError("EXP-14 requires an FX anchor feature in the export.")
    baseline_row, _ = _run_catboost_candidate(
        dataset=dataset,
        paths=paths,
        label="it_baseline_same_tickers",
        profile=args.profile,
        max_splits=args.max_splits,
        params=dict(base_params),
        feature_frame=feature_only_frame,
        selected_features=_numeric_feature_names(feature_only_frame),
        manifest_updates={"plan_experiment": "EXP-14", "variant": "baseline_same_tickers"},
        fresh=args.fresh,
    )
    baseline_row["ticker_count"] = len(tickers)
    baseline_row["variant"] = "baseline_same_tickers"
    rows.append(baseline_row)

    sector_row, state = _run_catboost_candidate(
        dataset=dataset,
        paths=paths,
        label="it_sector_reduced_plus_fx_extras",
        profile=args.profile,
        max_splits=args.max_splits,
        params=dict(base_params),
        feature_frame=frame,
        selected_features=selected_features,
        manifest_updates={"plan_experiment": "EXP-14", "variant": "sector_reduced_plus_fx_extras"},
        fresh=args.fresh,
    )
    stability = dict((state.get("all_stabilities") or {}).get("CatBoost") or {})
    importance_map = dict(stability.get("mean_importance_by_feature") or {})
    importance_rank = list(importance_map.keys())
    sector_row["ticker_count"] = len(tickers)
    sector_row["variant"] = "sector_reduced_plus_fx_extras"
    sector_row["fx_anchor_feature"] = anchor_feature
    sector_row["fx_anchor_standalone_ic"] = _standalone_ic(frame, anchor_feature)
    sector_row["fx_anchor_importance_rank"] = importance_rank.index(anchor_feature) + 1 if anchor_feature in importance_rank else None
    sector_row["baseline_ic_delta"] = _finite_float(sector_row.get("mean_test_ic")) - _finite_float(baseline_row.get("mean_test_ic"))
    sector_row["feature_contract_status"] = feature_contract["status"]
    sector_row["missing_required_features"] = list(feature_contract["required_missing"])
    rows.append(sector_row)

    subgroup_rows: list[dict[str, Any]] = []
    proxy_groups = _resolve_it_proxy_groups(frame)
    for group_name, group_tickers in proxy_groups.items():
        if len(group_tickers) < int(config.get("min_proxy_group_tickers") or 5):
            subgroup_rows.append({"variant": group_name, "status": "SKIPPED", "ticker_count": len(group_tickers)})
            continue
        subgroup_frame = _filter_feature_frame(dataset, tickers=group_tickers, feature_frame=frame)
        row, _ = _run_catboost_candidate(
            dataset=dataset,
            paths=paths,
            label=f"it_{group_name}_proxy_split",
            profile=args.profile,
            max_splits=args.max_splits,
            params=dict(base_params),
            feature_frame=subgroup_frame,
            selected_features=selected_features,
            manifest_updates={"plan_experiment": "EXP-14", "variant": group_name},
            fresh=args.fresh,
        )
        row["variant"] = group_name
        row["ticker_count"] = len(group_tickers)
        subgroup_rows.append(row)
    rows.extend(subgroup_rows)

    payload = _finalize_experiment(
        paths=paths,
        exp_id="EXP-14",
        title=str(config["title"]),
        hypothesis=str(config["hypothesis"]),
        rows=rows,
        best_candidate=pick_best_candidate([baseline_row, sector_row]) or sector_row,
        notes=[
            f"Upstream broad-universe configuration source: {upstream_source}.",
            "The main comparison is baseline-on-the-same-tickers versus reduced-60 plus IT/FX extras.",
            "Offshore-heavy vs domestic-heavy diagnostics use the export's FX and international-revenue proxies because the current metadata does not carry a cleaner revenue split.",
        ],
        extra_payload={
            "it_ticker_count": len(tickers),
            "fx_anchor_feature": anchor_feature,
            "feature_contract": feature_contract,
            "proxy_groups": {key: len(value) for key, value in proxy_groups.items()},
        },
    )
    write_json(
        paths.experiment_root / "sector_subset_manifest.json",
        {
            "experiment": "EXP-14",
            "sector": "Information Technology",
            "ticker_count": len(tickers),
            "tickers": list(tickers),
            "fx_anchor_feature": anchor_feature,
            "feature_contract": feature_contract,
            "proxy_groups": proxy_groups,
        },
    )
    return payload


def run_exp15(args: argparse.Namespace, config: dict[str, Any]) -> dict[str, Any]:
    dataset = _load_dataset(_resolve_export_dir(args.export_dir))
    paths = make_experiment_paths(args.output_root, "EXP-15", args.version)
    upstream, upstream_source = _load_upstream_best(
        output_root=args.output_root,
        version=args.version,
        dependency_ids=["EXP-12", "EXP-11", "EXP-10", "EXP-09"],
        fallback=dict(config.get("fallback_upstream") or {}),
    )
    base_params = _merged_tree_params(config, upstream)
    tickers = resolve_capital_goods_tickers(dataset)
    if not tickers:
        raise RuntimeError("EXP-15 could not resolve any Capital Goods tickers from metadata.")
    base_frame = _filter_feature_frame(dataset, tickers=tickers, feature_frame=_feature_frame_with_meta(dataset))
    feature_only_frame = base_frame[dataset.features.columns.intersection(base_frame.columns).tolist()].copy()
    selected_features, feature_contract = _build_reduced_feature_bundle(
        base_frame,
        base_feature_pool=_numeric_feature_names(dataset.features),
        reduced_feature_count=int(config.get("reduced_feature_count") or 60),
        required_features=list(config.get("required_cg_features") or []),
        proxy_map=dict(config.get("proxy_cg_features") or {}),
    )

    rows: list[dict[str, Any]] = []
    baseline_row, _ = _run_catboost_candidate(
        dataset=dataset,
        paths=paths,
        label="capital_goods_baseline_same_tickers",
        profile=args.profile,
        max_splits=args.max_splits,
        params=dict(base_params),
        feature_frame=feature_only_frame,
        selected_features=_numeric_feature_names(feature_only_frame),
        manifest_updates={"plan_experiment": "EXP-15", "variant": "baseline_same_tickers"},
        fresh=args.fresh,
    )
    baseline_row["ticker_count"] = len(tickers)
    baseline_row["variant"] = "baseline_same_tickers"
    rows.append(baseline_row)

    sector_row, _ = _run_catboost_candidate(
        dataset=dataset,
        paths=paths,
        label="capital_goods_sector_reduced_plus_extras",
        profile=args.profile,
        max_splits=args.max_splits,
        params=dict(base_params),
        feature_frame=base_frame,
        selected_features=selected_features,
        manifest_updates={"plan_experiment": "EXP-15", "variant": "sector_reduced_plus_extras"},
        fresh=args.fresh,
    )
    sector_row["ticker_count"] = len(tickers)
    sector_row["variant"] = "sector_reduced_plus_extras"
    sector_row["feature_contract_status"] = feature_contract["status"]
    sector_row["missing_required_features"] = list(feature_contract["required_missing"])
    sector_row["baseline_ic_delta"] = _finite_float(sector_row.get("mean_test_ic")) - _finite_float(baseline_row.get("mean_test_ic"))
    rows.append(sector_row)

    interaction_frame = base_frame.copy()
    interaction_features: list[str] = []
    interaction_source = "exact"
    order_driver = None
    if "order_backlog_growth" in interaction_frame.columns:
        order_driver = "order_backlog_growth"
    else:
        order_driver = str(dict(feature_contract.get("proxy_resolved") or {}).get("order_backlog_growth_proxy") or "")
        if order_driver:
            interaction_source = "proxy"
    if order_driver and "steel_4w_return" in interaction_frame.columns:
        interaction_name = "cg_order_driver_x_steel"
        interaction_frame[interaction_name] = (
            pd.to_numeric(interaction_frame[order_driver], errors="coerce").fillna(0.0)
            * pd.to_numeric(interaction_frame["steel_4w_return"], errors="coerce").fillna(0.0)
        )
        interaction_features.append(interaction_name)

    if interaction_features:
        interaction_selected = list(selected_features) + [name for name in interaction_features if name not in selected_features]
        interaction_row, _ = _run_catboost_candidate(
            dataset=dataset,
            paths=paths,
            label="capital_goods_interaction",
            profile=args.profile,
            max_splits=args.max_splits,
            params=dict(base_params),
            feature_frame=interaction_frame,
            selected_features=interaction_selected,
            manifest_updates={"plan_experiment": "EXP-15", "variant": "interaction"},
            fresh=args.fresh,
        )
        interaction_row["ticker_count"] = len(tickers)
        interaction_row["variant"] = "interaction"
        interaction_row["interaction_features"] = interaction_features
        interaction_row["interaction_source"] = interaction_source
        rows.append(interaction_row)

    payload = _finalize_experiment(
        paths=paths,
        exp_id="EXP-15",
        title=str(config["title"]),
        hypothesis=str(config["hypothesis"]),
        rows=rows,
        best_candidate=pick_best_candidate([row for row in rows if row.get("status") != "SKIPPED"]) or sector_row,
        notes=[
            f"Upstream broad-universe configuration source: {upstream_source}.",
            "The main comparison is baseline-on-the-same-tickers versus reduced-60 plus Capital Goods extras or proxies.",
            "The commodity interaction is only added when we can resolve an exact order-backlog feature or an explicit proxy from the current export.",
        ],
        extra_payload={
            "capital_goods_ticker_count": len(tickers),
            "interaction_features": interaction_features,
            "feature_contract": feature_contract,
        },
    )
    write_json(
        paths.experiment_root / "sector_subset_manifest.json",
        {
            "experiment": "EXP-15",
            "sector": "Capital Goods",
            "ticker_count": len(tickers),
            "tickers": list(tickers),
            "interaction_features": interaction_features,
            "feature_contract": feature_contract,
        },
    )
    return payload


def run_exp16(args: argparse.Namespace, config: dict[str, Any]) -> dict[str, Any]:
    dataset = _load_dataset(_resolve_export_dir(args.export_dir))
    paths = make_experiment_paths(args.output_root, "EXP-16", args.version)
    upstream, upstream_source = _load_upstream_best(
        output_root=args.output_root,
        version=args.version,
        dependency_ids=["EXP-15", "EXP-14", "EXP-13", "EXP-12", "EXP-11", "EXP-10", "EXP-09"],
        fallback=dict(config.get("fallback_upstream") or {}),
    )
    base_params = _merged_tree_params(config, upstream)
    include_sectors = list(config.get("sectors") or [])
    base_frame = dataset.features.copy()
    base_selected = _numeric_feature_names(base_frame)
    augmented_frame, added_features, sector_indicators, missing_base = _augment_sector_identity_and_conditionals(
        dataset,
        conditional_sectors=include_sectors,
        base_features=list(config.get("sector_conditional_base_features") or []),
    )
    blend_selected = _numeric_feature_names(augmented_frame)
    rows: list[dict[str, Any]] = []
    base_row, _ = _run_catboost_candidate(
        dataset=dataset,
        paths=paths,
        label="blend_without_sector_conditionals",
        profile=args.profile,
        max_splits=args.max_splits,
        params=dict(base_params),
        feature_frame=base_frame,
        selected_features=base_selected,
        manifest_updates={"plan_experiment": "EXP-16", "variant": "base"},
        fresh=args.fresh,
    )
    base_row["ticker_count"] = int(dataset.features["ticker"].nunique())
    rows.append(base_row)
    blend_row, _ = _run_catboost_candidate(
        dataset=dataset,
        paths=paths,
        label="blend_with_sector_conditionals",
        profile=args.profile,
        max_splits=args.max_splits,
        params=dict(base_params),
        feature_frame=augmented_frame,
        selected_features=blend_selected,
        manifest_updates={"plan_experiment": "EXP-16", "variant": "sector_conditionals"},
        fresh=args.fresh,
    )
    blend_row["ticker_count"] = int(dataset.features["ticker"].nunique())
    blend_row["added_feature_count"] = len(added_features)
    blend_row["sector_indicator_count"] = len(sector_indicators)
    rows.append(blend_row)
    payload = _finalize_experiment(
        paths=paths,
        exp_id="EXP-16",
        title=str(config["title"]),
        hypothesis=str(config["hypothesis"]),
        rows=rows,
        best_candidate=pick_best_candidate(rows) or blend_row,
        notes=[
            f"Upstream broad-universe configuration source: {upstream_source}.",
            "This run now uses the full export universe and adds explicit sector-identity indicators to approximate the compendium's sector_id categorical design.",
        ],
        extra_payload={
            "blend_ticker_count": int(dataset.features["ticker"].nunique()),
            "added_features": added_features,
            "sector_indicators": sector_indicators,
            "missing_sector_conditional_base_features": missing_base,
        },
    )
    write_json(
        paths.experiment_root / "augmented_feature_manifest.json",
        {
            "experiment": "EXP-16",
            "sectors": include_sectors,
            "ticker_count": int(dataset.features["ticker"].nunique()),
            "base_features": list(config.get("sector_conditional_base_features") or []),
            "added_features": added_features,
            "sector_indicators": sector_indicators,
            "missing_sector_conditional_base_features": missing_base,
        },
    )
    return payload


def _factor_alias_contract(columns: list[str], alias_map: dict[str, list[str]]) -> dict[str, Any]:
    factor_map: dict[str, str] = {}
    for factor_label, aliases in alias_map.items():
        candidates = [factor_label, *list(aliases or [])]
        resolved = _resolve_first_existing(columns, [str(value) for value in candidates])
        if resolved:
            factor_map[str(factor_label)] = resolved
    return {
        "factor_map": factor_map,
        "requested_factors": list(alias_map.keys()),
        "missing_factors": [factor for factor in alias_map if factor not in factor_map],
    }

def _resolve_factor_map(dataset: PlanDataset, config: dict[str, Any]) -> dict[str, str]:
    factor_set = str(config.get("factor_set") or "catalog_v1").strip().lower()
    if factor_set == "compendium_doc":
        alias_map = {factor: list(aliases) for factor, aliases in DOC_ANCHOR_FACTOR_ALIASES.items()}
    else:
        alias_map = {factor: list(aliases) for factor, aliases in DEFAULT_CANONICAL_FACTOR_ALIASES.items()}
    alias_map.update(
        {
            str(factor_label): [str(value) for value in list(aliases or [])]
            for factor_label, aliases in dict(config.get("factor_aliases") or {}).items()
        }
    )
    contract = _factor_alias_contract(list(dataset.features.columns), alias_map)
    if contract["missing_factors"] and bool(config.get("require_all_factors", True)):
        raise RuntimeError(f"Unresolved canonical factor aliases: {', '.join(contract['missing_factors'])}")
    return dict(contract["factor_map"])


def _factor_event_table(dataset: PlanDataset, factor_map: dict[str, str]) -> pd.DataFrame:
    events = load_major_events()
    rows: list[dict[str, Any]] = []
    for event in events.to_dict(orient="records"):
        start = pd.Timestamp(event["start_date"]).normalize()
        end = pd.Timestamp(event["end_date"]).normalize()
        event_frame = dataset.merged[dataset.merged["date"].between(start, end)].copy()
        for factor_label, column_name in factor_map.items():
            if event_frame.empty:
                summary = {"mean_ic": float("nan"), "ic_ir": float("nan"), "ic_tstat": float("nan"), "n_dates": 0}
                coverage_status = "event_not_in_export"
            else:
                summary = summarize_ic_series(compute_ic_series(event_frame, column_name))
                coverage_status = "covered"
            rows.append(
                {
                    "event_id": event["event_id"],
                    "event_name": event["event_name"],
                    "factor": factor_label,
                    "column_name": column_name,
                    "mean_ic": summary["mean_ic"],
                    "ic_ir": summary["ic_ir"],
                    "ic_tstat": summary["ic_tstat"],
                    "n_dates": summary["n_dates"],
                    "severity_score_1_10": event.get("severity_score_1_10"),
                    "model_collapse_risk": event.get("model_collapse_risk"),
                    "coverage_status": coverage_status,
                }
            )
    return pd.DataFrame(rows)


def run_exp17(args: argparse.Namespace, config: dict[str, Any]) -> dict[str, Any]:
    dataset = _load_dataset(_resolve_export_dir(args.export_dir))
    paths = make_experiment_paths(args.output_root, "EXP-17", args.version)
    factor_map = _resolve_factor_map(dataset, config)
    if not factor_map:
        raise RuntimeError("EXP-17 could not resolve any canonical anchor factors from the export.")
    catalog_contract = _factor_alias_contract(list(dataset.features.columns), DEFAULT_CANONICAL_FACTOR_ALIASES)
    doc_contract = _factor_alias_contract(list(dataset.features.columns), DOC_ANCHOR_FACTOR_ALIASES)
    long_df = _factor_event_table(dataset, factor_map)
    wide_df = (
        long_df.pivot(index="factor", columns="event_id", values="mean_ic").reset_index()
        if not long_df.empty
        else pd.DataFrame()
    )
    write_table(paths.experiment_root / "factor_event_heatmap.csv", long_df)
    write_table(paths.experiment_root / "factor_event_heatmap.parquet", long_df)
    write_table(paths.experiment_root / "factor_regime_ic_heatmap.csv", long_df)
    if not wide_df.empty:
        write_table(paths.experiment_root / "factor_event_heatmap_wide.csv", wide_df)
    covered = long_df[long_df["coverage_status"] == "covered"].copy() if not long_df.empty else pd.DataFrame()
    blind_spots = (
        covered.sort_values(["mean_ic", "ic_ir"], ascending=[True, True], kind="mergesort").head(12).to_dict(orient="records")
        if not covered.empty
        else []
    )
    payload = {
        "exp_id": "EXP-17",
        "title": str(config["title"]),
        "factor_set": str(config.get("factor_set") or "catalog_v1"),
        "factor_map": factor_map,
        "event_count": int(load_major_events()["event_id"].nunique()),
        "covered_event_count": int(covered["event_id"].nunique()) if not covered.empty else 0,
        "uncovered_event_count": int(long_df["event_id"].nunique() - covered["event_id"].nunique()) if not long_df.empty else 0,
        "factor_count": int(long_df["factor"].nunique()) if not long_df.empty else 0,
        "catalog_factor_contract": catalog_contract,
        "compendium_doc_factor_contract": doc_contract,
        "blind_spots": blind_spots,
    }
    write_json(paths.summary_path, payload)
    write_narrative(
        paths.narrative_path,
        exp_id="EXP-17",
        title=str(config["title"]),
        hypothesis=str(config["hypothesis"]),
        metrics={
            "event_count": payload["event_count"],
            "covered_event_count": payload["covered_event_count"],
            "factor_count": payload["factor_count"],
            "resolved_factor_columns": factor_map,
        },
        extra_notes=[
            "This separate script resolves aliases against the actual feature-export columns before building the heat map.",
            "Events that predate the current export are kept in the matrix with null ICs so coverage gaps are explicit rather than silently dropped.",
        ],
    )
    return payload


def run_exp18(args: argparse.Namespace, config: dict[str, Any]) -> dict[str, Any]:
    dataset = _load_dataset(_resolve_export_dir(args.export_dir))
    paths = make_experiment_paths(args.output_root, "EXP-18", args.version)
    upstream, upstream_source = _load_upstream_best(
        output_root=args.output_root,
        version=args.version,
        dependency_ids=["EXP-12", "EXP-11", "EXP-10", "EXP-09"],
        fallback=dict(config.get("fallback_upstream") or {}),
    )
    params = _merged_tree_params(config, upstream)

    factor_map = _resolve_factor_map(dataset, config)
    if not factor_map:
        raise RuntimeError("EXP-18 could not resolve any canonical anchor factors from the export.")
    exp17_table = _factor_event_table(dataset, factor_map)
    major_events = load_major_events()
    events_by_id = {str(row["event_id"]): row for row in major_events.to_dict(orient="records")}
    event_windows = _event_windows_from_dataset(dataset)
    rows: list[dict[str, Any]] = []
    fallback_features = [factor_map.get(factor) for factor in PLAN_INFO.anchor_factors if factor_map.get(factor)]
    fallback_features = sorted(dict.fromkeys(fallback_features))
    requested_ids = [str(value) for value in list(config.get("requested_event_ids") or DEFAULT_EXP18_FIXED_EVENTS)]
    selected_events: list[tuple[str, dict[str, Any], str]] = []
    for event_id in requested_ids:
        event = events_by_id.get(event_id)
        if event:
            selected_events.append((event_id, event, "requested_fixed"))
        else:
            rows.append({"event_id": event_id, "status": "SKIPPED", "reason": "event_not_found", "selection_source": "requested_fixed"})
    if bool(config.get("allow_supplemental_events", True)):
        supplements = major_events.copy()
        rank = supplements["model_collapse_risk"].astype("string").fillna("").map(
            lambda value: 2 if "EXTREME" in str(value).upper() else 1 if "HIGH" in str(value).upper() else 0
        )
        supplements["_collapse_rank"] = rank
        supplements = supplements.sort_values(
            ["_collapse_rank", "severity_score_1_10", "start_date"],
            ascending=[False, False, True],
            kind="mergesort",
        )
        for event in supplements.to_dict(orient="records"):
            event_id = str(event["event_id"])
            if event_id in requested_ids:
                continue
            if event_id not in event_windows:
                continue
            selected_events.append((event_id, event, "supplemental_export_era"))
            if len(selected_events) >= int(config.get("supplemental_target_count") or 5):
                break

    for event_id, event, selection_source in selected_events:
        if event_id in event_windows:
            event_start, event_end = event_windows[event_id]
        else:
            event_start = pd.Timestamp(event["start_date"]).normalize()
            event_end = pd.Timestamp(event["end_date"]).normalize()
        if event_end < pd.to_datetime(dataset.features["date"]).min():
            rows.append({"event_id": event_id, "event_name": event["event_name"], "status": "SKIPPED", "reason": "predates_export", "selection_source": selection_source})
            continue

        normal_start, normal_end = _normal_window_for_event(event_start, event_end)
        train_end = normal_start - pd.Timedelta(days=7)
        train_start = train_end - pd.Timedelta(weeks=int(config.get("train_window_weeks") or 104) - 1)
        if train_start < pd.to_datetime(dataset.features["date"]).min():
            rows.append({"event_id": event_id, "event_name": event["event_name"], "status": "SKIPPED", "reason": "insufficient_pre_event_history", "selection_source": selection_source})
            continue

        event_factor_rows = exp17_table[
            (exp17_table["event_id"].astype(str) == event_id)
            & (exp17_table["coverage_status"].astype(str) == "covered")
            & (pd.to_numeric(exp17_table["mean_ic"], errors="coerce") > float(config.get("regime_factor_threshold") or 0.010))
        ]
        regime_features = [str(value) for value in event_factor_rows["column_name"].dropna().astype(str).tolist()]
        regime_features = sorted(dict.fromkeys([feature for feature in regime_features if feature in dataset.features.columns]))
        if not regime_features:
            regime_features = fallback_features

        universal_event_row, _ = _run_catboost_candidate(
            dataset=dataset,
            paths=paths,
            label=f"{event_id}_universal_event",
            profile=args.profile,
            max_splits=1,
            params=dict(params),
            selected_features=_numeric_feature_names(dataset.features),
            splits_override=_custom_split(train_start=train_start, train_end=train_end, test_start=event_start, test_end=event_end),
            date_min=str(train_start.date()),
            date_max=str(event_end.date()),
            manifest_updates={"plan_experiment": "EXP-18", "event_id": event_id, "variant": "universal_event"},
            fresh=args.fresh,
        )
        universal_normal_row, _ = _run_catboost_candidate(
            dataset=dataset,
            paths=paths,
            label=f"{event_id}_universal_normal",
            profile=args.profile,
            max_splits=1,
            params=dict(params),
            selected_features=_numeric_feature_names(dataset.features),
            splits_override=_custom_split(train_start=train_start, train_end=train_end, test_start=normal_start, test_end=normal_end),
            date_min=str(train_start.date()),
            date_max=str(normal_end.date()),
            manifest_updates={"plan_experiment": "EXP-18", "event_id": event_id, "variant": "universal_normal"},
            fresh=args.fresh,
        )
        regime_event_row, _ = _run_catboost_candidate(
            dataset=dataset,
            paths=paths,
            label=f"{event_id}_regime_event",
            profile=args.profile,
            max_splits=1,
            params=dict(params),
            selected_features=list(regime_features),
            splits_override=_custom_split(train_start=train_start, train_end=train_end, test_start=event_start, test_end=event_end),
            date_min=str(train_start.date()),
            date_max=str(event_end.date()),
            manifest_updates={"plan_experiment": "EXP-18", "event_id": event_id, "variant": "regime_event"},
            fresh=args.fresh,
        )
        regime_normal_row, _ = _run_catboost_candidate(
            dataset=dataset,
            paths=paths,
            label=f"{event_id}_regime_normal",
            profile=args.profile,
            max_splits=1,
            params=dict(params),
            selected_features=list(regime_features),
            splits_override=_custom_split(train_start=train_start, train_end=train_end, test_start=normal_start, test_end=normal_end),
            date_min=str(train_start.date()),
            date_max=str(normal_end.date()),
            manifest_updates={"plan_experiment": "EXP-18", "event_id": event_id, "variant": "regime_normal"},
            fresh=args.fresh,
        )
        row = {
            "event_id": event_id,
            "event_name": event["event_name"],
            "status": "RUN",
            "selection_source": selection_source,
            "universal_event_ic": universal_event_row.get("mean_test_ic"),
            "universal_normal_ic": universal_normal_row.get("mean_test_ic"),
            "regime_event_ic": regime_event_row.get("mean_test_ic"),
            "regime_normal_ic": regime_normal_row.get("mean_test_ic"),
            "collapse_fraction_universal": _collapse_score(
                float(universal_event_row.get("mean_test_ic", float("nan"))),
                float(universal_normal_row.get("mean_test_ic", float("nan"))),
            ),
            "collapse_fraction_regime": _collapse_score(
                float(regime_event_row.get("mean_test_ic", float("nan"))),
                float(regime_normal_row.get("mean_test_ic", float("nan"))),
            ),
            "signal_retention_universal": _retention_score(
                float(universal_event_row.get("mean_test_ic", float("nan"))),
                float(universal_normal_row.get("mean_test_ic", float("nan"))),
            ),
            "signal_retention_regime": _retention_score(
                float(regime_event_row.get("mean_test_ic", float("nan"))),
                float(regime_normal_row.get("mean_test_ic", float("nan"))),
            ),
            "regime_features": regime_features,
        }
        row["best_signal_retention"] = np.nanmax([row["signal_retention_universal"], row["signal_retention_regime"]])
        row["best_collapse_fraction"] = np.nanmin([row["collapse_fraction_universal"], row["collapse_fraction_regime"]])
        rows.append(row)

    table = pd.DataFrame(rows)
    write_table(paths.experiment_root / "event_collapse_table.csv", table)
    write_json(paths.experiment_root / "collapse_scorecard.json", {"event_rows": rows})
    valid = table[table["status"] == "RUN"].copy() if not table.empty and "status" in table.columns else pd.DataFrame()
    mean_retention = float(pd.to_numeric(valid["best_signal_retention"], errors="coerce").mean()) if not valid.empty else float("nan")
    mean_collapse = float(pd.to_numeric(valid["best_collapse_fraction"], errors="coerce").mean()) if not valid.empty else float("nan")
    payload = {
        "exp_id": "EXP-18",
        "title": str(config["title"]),
        "upstream_source": upstream_source,
        "mean_best_signal_retention": mean_retention,
        "mean_best_collapse_fraction": mean_collapse,
        "tested_events": int(len(valid)),
        "skipped_events": int(len(table) - len(valid)) if not table.empty else 0,
        "requested_event_ids": requested_ids,
        "event_rows": rows,
    }
    write_json(paths.summary_path, payload)
    write_narrative(
        paths.narrative_path,
        exp_id="EXP-18",
        title=str(config["title"]),
        hypothesis=str(config["hypothesis"]),
        metrics={
            "upstream_source": upstream_source,
            "mean_best_signal_retention": mean_retention,
            "tested_events": payload["tested_events"],
        },
        extra_notes=[
            "This script first targets the compendium's fixed collapse events and then supplements them with export-era high-risk events when the 2019+ dataset cannot support the older windows.",
            "Because the compendium text mixes collapse-fraction and signal-retention language, the summary records both metrics explicitly.",
        ],
    )
    return payload


def _spec_with_script_overrides(exp_id: str, config: dict[str, Any]) -> ExperimentSpec:
    spec = EXPERIMENT_CATALOG[exp_id]
    merged_params = dict(spec.params)
    merged_params.update(dict(config.get("params") or {}))
    return replace(
        spec,
        title=str(config.get("title") or spec.title),
        hypothesis=str(config.get("hypothesis") or spec.hypothesis),
        params=merged_params,
    )


def _run_family_backed_experiment(
    args: argparse.Namespace,
    exp_id: str,
    config: dict[str, Any],
) -> dict[str, Any]:
    dataset = _load_dataset(_resolve_export_dir(args.export_dir))
    spec = _spec_with_script_overrides(exp_id, config)
    family_runners: dict[str, Callable[..., dict[str, Any]]] = {
        "regime": run_regime_experiment,
        "redemption": run_redemption_experiment,
        "signal": run_signal_experiment,
        "verification": run_verification_experiment,
    }
    runner = family_runners[spec.family]
    payload = runner(
        spec,
        dataset=dataset,
        output_root=args.output_root,
        profile=args.profile,
        max_splits=args.max_splits,
        version=args.version,
    )
    payload["script_config"] = json_ready(config)
    write_json(make_experiment_paths(args.output_root, exp_id, args.version).experiment_root / "script_config.json", config)
    return payload


def run_exp19(args: argparse.Namespace, config: dict[str, Any]) -> dict[str, Any]:
    return _run_family_backed_experiment(args, "EXP-19", config)


def run_exp20(args: argparse.Namespace, config: dict[str, Any]) -> dict[str, Any]:
    return _run_family_backed_experiment(args, "EXP-20", config)


def run_exp21(args: argparse.Namespace, config: dict[str, Any]) -> dict[str, Any]:
    return _run_family_backed_experiment(args, "EXP-21", config)


def run_exp22(args: argparse.Namespace, config: dict[str, Any]) -> dict[str, Any]:
    return _run_family_backed_experiment(args, "EXP-22", config)


def run_exp23(args: argparse.Namespace, config: dict[str, Any]) -> dict[str, Any]:
    return _run_family_backed_experiment(args, "EXP-23", config)


def run_exp24(args: argparse.Namespace, config: dict[str, Any]) -> dict[str, Any]:
    return _run_family_backed_experiment(args, "EXP-24", config)


def run_exp25(args: argparse.Namespace, config: dict[str, Any]) -> dict[str, Any]:
    return _run_family_backed_experiment(args, "EXP-25", config)


def run_exp26(args: argparse.Namespace, config: dict[str, Any]) -> dict[str, Any]:
    return _run_family_backed_experiment(args, "EXP-26", config)


def run_exp27(args: argparse.Namespace, config: dict[str, Any]) -> dict[str, Any]:
    return _run_family_backed_experiment(args, "EXP-27", config)


RUNNERS: dict[str, Callable[[argparse.Namespace, dict[str, Any]], dict[str, Any]]] = {
    "EXP-09": run_exp09,
    "EXP-10": run_exp10,
    "EXP-11": run_exp11,
    "EXP-12": run_exp12,
    "EXP-13": run_exp13,
    "EXP-14": run_exp14,
    "EXP-15": run_exp15,
    "EXP-16": run_exp16,
    "EXP-17": run_exp17,
    "EXP-18": run_exp18,
    "EXP-19": run_exp19,
    "EXP-20": run_exp20,
    "EXP-21": run_exp21,
    "EXP-22": run_exp22,
    "EXP-23": run_exp23,
    "EXP-24": run_exp24,
    "EXP-25": run_exp25,
    "EXP-26": run_exp26,
    "EXP-27": run_exp27,
}


def main_for_experiment(exp_id: str, script_config: dict[str, Any]) -> int:
    parser = _build_parser(exp_id, str(script_config["title"]), default_profile=str(script_config.get("default_profile") or "full"))
    args = parser.parse_args()
    if args.describe:
        print(json.dumps(json_ready(script_config), indent=2))
        return 0
    runner = RUNNERS[exp_id]
    payload = runner(args, script_config)
    print(json.dumps(json_ready(payload), indent=2))
    return 0
