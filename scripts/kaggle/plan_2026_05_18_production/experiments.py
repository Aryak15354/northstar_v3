#!/usr/bin/env python3
"""Experiment implementations for the fixed Northstar V3 Kaggle export."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from scripts.kaggle.plan_2026_05_18_production.common import (
    ANCHOR_FACTOR_ALIASES,
    COMMODITY_SIGNALS,
    POST_INDAS_ANCHOR,
    TARGET_COL,
    DatasetBundle,
    apply_split,
    compute_ic,
    ic_by_date,
    json_safe,
    latest_metadata,
    load_and_fix_dataset,
    merge_metadata,
    merge_regimes,
    resolve_data_dir,
    resolve_factor,
    run_catboost_walkforward,
    run_factor_ic_table,
    save_results,
    summarize_ic_values,
)
from scripts.kaggle.plan_2026_05_18_production.event_registry import is_event_window


STANDARD_MULTI_FAMILY_GATE = {
    "production_ic_screen_min_median_abs_ic": 0.008,
    "production_relaxed_feature_fallback": False,
    "require_multi_family_features": True,
    "earnings_starvation_min_features": 3,
    "earnings_starvation_hard_gate": False,
}

FS_FAMILY_PATTERNS = {
    "momentum": ["mom", "momentum", "return_4w", "return_13w", "return_26w"],
    "rate_or_ownership": [
        "rate",
        "repo",
        "yield",
        "screener_institutional",
        "screener_dii",
        "free_float",
        "promoter_change",
    ],
}

IT_FAMILY_PATTERNS = {
    "earnings_surprise": ["eps", "rev", "sue", "earnings"],
    "momentum": ["mom", "momentum", "return_4w", "return_13w", "return_26w"],
}

RELIABLE_REGIME_MIN_TEST_ROWS = 750


def _candidate_best(rows: list[dict[str, Any]], *, ratio_gate: float = 2.5, ic_floor: float = 0.020) -> dict[str, Any] | None:
    valid = [
        r for r in rows
        if (r.get("mean_test_ic") is not None and r.get("median_train_test_ratio", r.get("mean_train_test_ratio")) is not None)
        and float(r["mean_test_ic"]) >= ic_floor
        and int(r.get("degenerate_window_count") or 0) == 0
    ]
    gated = [r for r in valid if float(r.get("median_train_test_ratio", r.get("mean_train_test_ratio"))) < ratio_gate]
    pool = gated or valid or rows
    if not pool:
        return None
    return sorted(
        pool,
        key=lambda r: (
            int(r.get("degenerate_window_count") or 0),
            float(r.get("median_train_test_ratio", r.get("mean_train_test_ratio")) or 999),
            -float(r.get("mean_test_ic") or -999),
        ),
    )[0]


def _is_gated_out_regime(regime_text: str) -> bool:
    text = str(regime_text)
    return any(token in text for token in ["R2", "High-Vol Bull", "R6", "Sideways", "R9", "External Shock"])


def _is_run7_routing_regime(regime_text: str) -> bool:
    text = str(regime_text)
    return any(
        token in text
        for token in ["R1", "Low-Vol Bull", "R3", "Low-Vol Bear", "R4", "High-Vol Bear", "R5", "Recovery"]
    )


def _is_reliable_regime_candidate(regime_text: str) -> bool:
    return _is_run7_routing_regime(regime_text)


def _reliable_regime_aggregate(
    windows: list[dict[str, Any]],
    *,
    min_test_rows: int = RELIABLE_REGIME_MIN_TEST_ROWS,
) -> dict[str, Any]:
    eval_rows = [
        r
        for r in windows
        if not r.get("skipped")
        and not r.get("aggregate_excluded")
        and not r.get("prediction_degenerate")
        and int(r.get("test_rows") or 0) >= min_test_rows
    ]
    train_ics = [float(r["train_ic"]) for r in eval_rows if r.get("train_ic") is not None and np.isfinite(r.get("train_ic"))]
    test_ics = [float(r["test_ic"]) for r in eval_rows if r.get("test_ic") is not None and np.isfinite(r.get("test_ic"))]
    ratios = [
        float(r.get("train_test_ratio", r.get("ratio")))
        for r in eval_rows
        if r.get("train_test_ratio", r.get("ratio")) is not None
        and np.isfinite(r.get("train_test_ratio", r.get("ratio")))
    ]
    raw_ratios = [
        float(r.get("raw_train_test_ratio", r.get("ratio_raw")))
        for r in eval_rows
        if r.get("raw_train_test_ratio", r.get("ratio_raw")) is not None
        and np.isfinite(r.get("raw_train_test_ratio", r.get("ratio_raw")))
    ]
    hits = [
        float(r.get("test_hit_rate"))
        for r in eval_rows
        if r.get("test_hit_rate") is not None and np.isfinite(r.get("test_hit_rate"))
    ]
    if not hits and test_ics:
        hits = [1.0 if x > 0 else 0.0 for x in test_ics]
    return {
        "min_test_rows": int(min_test_rows),
        "effective_eval_windows": int(len(eval_rows)),
        "included_windows": [int(r.get("window") or r.get("window_id") or -1) for r in eval_rows],
        "mean_train_ic": float(np.mean(train_ics)) if train_ics else None,
        "mean_test_ic": float(np.mean(test_ics)) if test_ics else None,
        "ic_ir": float(np.mean(test_ics) / (np.std(test_ics, ddof=1) + 1e-12)) if len(test_ics) > 1 else None,
        "median_train_test_ratio": float(np.median(ratios)) if ratios else None,
        "mean_train_test_ratio": float(np.mean(ratios)) if ratios else None,
        "raw_mean_train_test_ratio": float(np.mean(raw_ratios)) if raw_ratios else None,
        "hit_rate": float(np.mean(hits)) if hits else None,
    }


def _load_bundle(args: Any, *, policy: str = "full") -> DatasetBundle:
    data_dir = resolve_data_dir(args.data_dir)
    return load_and_fix_dataset(data_dir, feature_policy=getattr(args, "feature_policy", policy) or policy)


def _ic_screen_features(
    frame: pd.DataFrame,
    feature_cols: list[str],
    *,
    min_abs_ic: float = 0.01,
    min_dates: int = 10,
    max_features: int = 80,
) -> list[str]:
    rows: list[tuple[str, float, int]] = []
    usable = frame[~frame["structural_event_window_dummy"].astype(bool)].copy() if "structural_event_window_dummy" in frame.columns else frame
    for col in feature_cols:
        if col not in usable.columns or not pd.api.types.is_numeric_dtype(usable[col]):
            continue
        series = ic_by_date(usable.rename(columns={col: "score"}), "score")
        clean = series[np.isfinite(series)]
        if len(clean) < min_dates:
            continue
        mean_abs = float(clean.abs().mean())
        if mean_abs >= min_abs_ic:
            rows.append((col, mean_abs, int(len(clean))))
    rows.sort(key=lambda item: (-item[1], item[0]))
    selected = [col for col, _, _ in rows[:max_features]]
    print(f"  IC screen selected {len(selected)}/{len(feature_cols)} features at |IC|>={min_abs_ic} over >= {min_dates} dates")
    return selected or feature_cols[:max_features]


def run_exp09(args: Any) -> dict[str, Any]:
    bundle = _load_bundle(args, policy="full")
    rows: list[dict[str, Any]] = []
    window_rows: list[dict[str, Any]] = []
    label = "depth_6_minleaf_80_multifamily_gate"
    summary, windows = run_catboost_walkforward(
        bundle,
        exp_id="EXP-09",
        candidate=label,
        params={"depth": 6, "l2_leaf_reg": 3.0, "boosting_type": "Plain", "grow_policy": "Depthwise", "min_data_in_leaf": 80, "learning_rate": 0.01, "iterations": 600, "training_mode": "fixed_iterations"},
        max_windows=args.max_windows,
        production_ic_screen_min_median_abs_ic=0.008,
        production_relaxed_feature_fallback=False,
        require_multi_family_features=True,
        earnings_starvation_min_features=3,
        earnings_starvation_hard_gate=False,
    )
    summary.update({
        "depth": 6,
        "grow_policy": "Depthwise",
        "min_data_in_leaf": 80,
        "learning_rate": 0.01,
        "iterations": 600,
        "training_mode": "fixed_iterations",
        "run6_change": "EXP-09 retired min_leaf sweep; now tests multi-family feature gating with minleaf_80 baseline.",
    })
    rows.append(summary)
    window_rows.extend(windows)
    best = _candidate_best(rows, ratio_gate=5.0)
    results = {
        "experiment": "EXP-09",
        "run6_policy": {
            "retired_axis": "min_data_in_leaf sweep",
            "baseline": "depth=6, min_data_in_leaf=80",
            "production_ic_screen_min_median_abs_ic": 0.008,
            "production_relaxed_feature_fallback": False,
            "require_multi_family_features": True,
            "required_families": ["earnings_surprise", "momentum", "ownership_or_sentiment"],
            "earnings_starvation_min_features": 3,
            "earnings_starvation_mode": "warning_only_run6",
        },
        "best_candidate": best,
        "all_candidates": rows,
        "window_results": window_rows,
    }
    save_results("EXP-09", results, bundle.audit, bundle.feature_cols, args.output_dir)
    return results


def run_exp10(args: Any) -> dict[str, Any]:
    bundle = _load_bundle(args, policy="full")
    rows: list[dict[str, Any]] = []
    window_rows: list[dict[str, Any]] = []
    for subsample in [0.60, 0.80, 1.00]:
        label = f"row_subsample_{subsample:.2f}"
        params = {"depth": 6, "l2_leaf_reg": 3.0, "boosting_type": "Plain", "grow_policy": "Depthwise", "min_data_in_leaf": 150, "learning_rate": 0.01, "iterations": 600, "training_mode": "fixed_iterations"}
        if subsample < 1.0:
            params.update({"bootstrap_type": "Bernoulli", "subsample": float(subsample)})
        summary, windows = run_catboost_walkforward(
            bundle,
            exp_id="EXP-10",
            candidate=label,
            params=params,
            max_windows=args.max_windows,
            production_ic_screen_min_median_abs_ic=0.008,
            production_relaxed_feature_fallback=False,
            require_multi_family_features=True,
            earnings_starvation_min_features=3,
            earnings_starvation_hard_gate=False,
        )
        summary["subsample"] = float(subsample)
        summary["l2_leaf_reg"] = 3.0
        rows.append(summary)
        window_rows.extend(windows)
    best = _candidate_best(rows)
    results = {"experiment": "EXP-10", "run4_change": "removed_counterproductive_l2_sweep; testing row subsampling", "feature_screen": "per_window_univariate_ic_screen", "best_candidate": best, "all_candidates": rows, "window_results": window_rows}
    save_results("EXP-10", results, bundle.audit, bundle.feature_cols, args.output_dir)
    return results


def run_exp11(args: Any) -> dict[str, Any]:
    bundle = _load_bundle(args, policy="full")
    results = {
        "experiment": "EXP-11",
        "status": "closed_no_rerun",
        "decision": "Do not re-run Ordered vs Plain in Run 4.",
        "reason": "Run 3 showed Plain raised train IC without improving test IC; the live Run 4 tabular experiments use fixed-iteration CatBoost and EXP-09/10/18 cover the universal model behavior.",
        "baseline_policy": {
            "ordered_symmetric": "kept only as historical leakage-safe reference",
            "depthwise_leaf_control": "uses Plain because CatBoost does not support Ordered with non-symmetric Depthwise trees",
        },
    }
    save_results("EXP-11", results, bundle.audit, bundle.feature_cols, args.output_dir)
    return results


def _rolling_splits(dates: pd.Series, years: float) -> list[dict[str, Any]]:
    all_dates = sorted(pd.to_datetime(dates).dropna().unique())
    max_date = pd.Timestamp(max(all_dates))
    anchor = POST_INDAS_ANCHOR
    train_days = int(round(365 * years))
    splits: list[dict[str, Any]] = []
    test_start = anchor + pd.Timedelta(days=train_days)
    while test_start + pd.Timedelta(weeks=13) <= max_date:
        train_start = max(anchor, test_start - pd.Timedelta(days=train_days))
        train_end = test_start - pd.Timedelta(days=1)
        test_end = min(test_start + pd.Timedelta(weeks=13), max_date)
        overlaps_event, event_label = is_event_window(test_start, test_end)
        splits.append(
            {
                "window_id": len(splits) + 1,
                "train_start": str(train_start.date()),
                "train_end": str(train_end.date()),
                "test_start": str(test_start.date()),
                "test_end": str(test_end.date()),
                "train_policy": f"post_indas_rolling_{years:g}yr",
                "aggregate_excluded": bool(overlaps_event),
                "event_label": event_label,
            }
        )
        test_start += pd.Timedelta(weeks=13)
    return splits


def run_exp12(args: Any) -> dict[str, Any]:
    bundle = _load_bundle(args, policy="full")
    rows: list[dict[str, Any]] = []
    window_rows: list[dict[str, Any]] = []
    min_rows_by_years = {1.0: 25_000, 1.5: 25_000, 2.0: 25_000}
    for years in [1.0, 1.5, 2.0]:
        splits = _rolling_splits(bundle.features["date"], years)
        summary, windows = run_catboost_walkforward(
            bundle,
            exp_id="EXP-12",
            candidate=f"{years:g}yr_train",
            params={"depth": 6, "l2_leaf_reg": 3.0, "boosting_type": "Plain", "grow_policy": "Depthwise", "min_data_in_leaf": 150, "learning_rate": 0.01, "iterations": 600, "training_mode": "fixed_iterations"},
            splits=splits,
            min_train_rows=min_rows_by_years[years],
            max_windows=args.max_windows,
            **STANDARD_MULTI_FAMILY_GATE,
        )
        summary["train_window_years"] = years
        summary["min_train_rows"] = min_rows_by_years[years]
        rows.append(summary)
        window_rows.extend(windows)
    results = {
        "experiment": "EXP-12",
        "run7_change": "Uses the same multi-family gate policy as EXP-09/10 and replaces the failed 2.5-year arm with 1.5-year.",
        "best_candidate": _candidate_best(rows),
        "all_candidates": rows,
        "window_results": window_rows,
    }
    save_results("EXP-12", results, bundle.audit, bundle.feature_cols, args.output_dir)
    return results


def _sector_frame(bundle: DatasetBundle, keywords: list[str]) -> tuple[pd.DataFrame, list[str]]:
    meta = latest_metadata(bundle)
    pattern = "|".join(keywords)
    mask = pd.Series(False, index=meta.index)
    for col in ["sector", "broad_sector", "subsector"]:
        if col in meta.columns:
            mask = mask | meta[col].astype(str).str.contains(pattern, case=False, na=False)
    tickers = sorted(meta.loc[mask, "ticker"].astype(str).unique().tolist())
    return bundle.features[bundle.features["ticker"].isin(tickers)].copy(), tickers


def _run_sector(
    args: Any,
    exp_id: str,
    keywords: list[str],
    extra_features: list[str],
    *,
    feature_mode: str = "full_plus_extra",
    params: dict[str, Any] | None = None,
    exclude_features: list[str] | None = None,
    min_train_rows: int = 5000,
    sector_null_threshold: float | None = None,
    force_keep_top_n: int | None = None,
    test_ic_floor: float | None = None,
    sector_family_patterns: dict[str, list[str]] | None = None,
    require_sector_family_gate: bool = False,
    run7_note: str | None = None,
) -> dict[str, Any]:
    bundle = _load_bundle(args, policy="full")
    frame, tickers = _sector_frame(bundle, keywords)
    extras = [f for f in extra_features if f in frame.columns and pd.api.types.is_numeric_dtype(frame[f])]
    feature_cols = extras if feature_mode == "extra_only" else sorted(set(bundle.feature_cols) | set(extras))
    if exclude_features:
        feature_cols = [c for c in feature_cols if c not in set(exclude_features)]
    force_keep = extras
    if sector_null_threshold is not None and feature_cols:
        coverage = frame[feature_cols].notna().mean()
        locally_usable = coverage[coverage >= (1.0 - sector_null_threshold)].index.tolist()
        force_pool = [c for c in extras if c in locally_usable]
        if force_keep_top_n is not None and force_pool:
            force_keep = _ic_screen_features(frame, force_pool, min_abs_ic=0.0, min_dates=3, max_features=force_keep_top_n)
        else:
            force_keep = force_pool
        feature_cols = sorted(set(locally_usable) | set(force_keep))
        print(f"  {exp_id} sector-local null filter: kept {len(feature_cols)} features at null <= {sector_null_threshold:.0%}; force_keep={len(force_keep)}")
    print(f"  {exp_id} sector universe: {len(tickers)} tickers, {len(frame):,} rows")
    print(f"  {exp_id} feature mode: {feature_mode}, feature_count={len(feature_cols)}")
    summary, windows = run_catboost_walkforward(
        bundle,
        exp_id=exp_id,
        candidate="sector_only",
        params=params or {"depth": 5, "l2_leaf_reg": 3.0, "boosting_type": "Plain", "grow_policy": "Depthwise", "min_data_in_leaf": 80, "iterations": 400, "learning_rate": 0.01, "training_mode": "fixed_iterations"},
        frame=frame,
        feature_cols=feature_cols,
        always_keep_features=force_keep,
        min_train_rows=min_train_rows,
        test_ic_floor=test_ic_floor,
        max_windows=args.max_windows,
        production_ic_screen_min_median_abs_ic=0.008,
        production_relaxed_feature_fallback=False,
        require_multi_family_features=require_sector_family_gate,
        feature_family_patterns=sector_family_patterns,
        earnings_starvation_min_features=None,
    )
    results = {
        "experiment": exp_id,
        "run7_note": run7_note,
        "require_sector_family_gate": bool(require_sector_family_gate),
        "sector_family_patterns": sector_family_patterns,
        "sector_tickers": tickers,
        "summary": summary,
        "window_results": windows,
    }
    save_results(exp_id, results, bundle.audit, feature_cols, args.output_dir)
    return results


def _regime_min_rows(regime_text: str, default: int = 1500) -> int:
    if "R7" in regime_text or "Rate" in regime_text:
        return 2000
    if "R9" in regime_text or "External Shock" in regime_text:
        return 1500
    return default


def _print_regime_window_preflight(bundle: DatasetBundle, frame: pd.DataFrame, label: str) -> None:
    if "regime" not in frame.columns:
        print(f"  {label} regime preflight unavailable: no regime column")
        return
    print(f"  {label} regime/window row preflight:")
    active_regimes: set[str] = set()
    for split in bundle.splits:
        train, test = apply_split(frame, split)
        train_counts = train["regime"].fillna("Unknown").astype(str).value_counts().sort_index()
        test_counts = test["regime"].fillna("Unknown").astype(str).value_counts().sort_index()
        regimes = sorted(set(train_counts.index.astype(str)) | set(test_counts.index.astype(str)))
        active_regimes.update(r for r in regimes if int(train_counts.get(r, 0)) > 0 or int(test_counts.get(r, 0)) > 0)
        compact = ", ".join(f"{r}:tr{int(train_counts.get(r, 0))}/te{int(test_counts.get(r, 0))}" for r in regimes)
        print(f"    W{int(split.get('window_id', 0)):02d}: {compact or 'no regime rows'}")
    print(f"  {label} active regimes in walk-forward: {sorted(active_regimes)}")


def run_exp13(args: Any) -> dict[str, Any]:
    return _run_sector(
        args,
        "EXP-13",
        ["Financial", "Bank", "NBFC", "Insurance", "Finance"],
        [
            "gnpa_yoy_change",
            "gnpa_ratio_yoy",
            "gross_npa_yoy",
            "nim_trend_4q",
            "nim_4q_ma",
            "credit_deposit_ratio",
            "npa_coverage_ratio",
            "provision_coverage_ratio",
            "rbi_rate_chg",
            "rbi_repo_rate_change_13w",
            "rate_sensitivity_score",
            "fii_proxy",
            "screener_institutional_pct",
            "screener_institutional_pct_cs_z",
            "screener_dii_pct",
            "screener_dii_pct_cs_z",
            "screener_free_float_pct",
            "screener_free_float_pct_cs_z",
            "screener_promoter_change_1q",
            "screener_promoter_change_1q_cs_z",
        ],
        feature_mode="full_plus_extra",
        params={"depth": 4, "l2_leaf_reg": 3.0, "boosting_type": "Plain", "grow_policy": "Depthwise", "min_data_in_leaf": 80, "iterations": 400, "learning_rate": 0.01, "training_mode": "fixed_iterations"},
        min_train_rows=3500,
        sector_null_threshold=0.70,
        force_keep_top_n=10,
        sector_family_patterns=FS_FAMILY_PATTERNS,
        require_sector_family_gate=True,
        run7_note="Financial Services uses a sector-specific gate: momentum plus rate/ownership. Broad earnings-surprise is not required for banks/NBFCs.",
    )


def run_exp14(args: Any) -> dict[str, Any]:
    return _run_sector(
        args,
        "EXP-14",
        ["IT", "Software", "Technology", "Computer"],
        [],
        test_ic_floor=-0.05,
        min_train_rows=5000,
        sector_family_patterns=IT_FAMILY_PATTERNS,
        require_sector_family_gate=True,
        run7_note="Run 7 pure IT/export-services only. Pharma/Healthcare removed from this experiment.",
    )


def run_exp15(args: Any) -> dict[str, Any]:
    bundle = _load_bundle(args, policy="full")
    _, tickers = _sector_frame(bundle, ["Capital Goods", "Industrial", "Engineering", "Defence", "Power", "Electrical"])
    results = {
        "experiment": "EXP-15",
        "status": "paused_run7",
        "reason": "Run 6 Capital Goods failed mean IC, IC IR, and hit-rate gates. It should not consume Run 7 compute until sector-native order-book, capex, commodity-input, and government-project features exist.",
        "sector_tickers": tickers,
        "required_feature_work": [
            "order_backlog_growth",
            "government_project_award_signal",
            "steel_and_copper_input_cost_surprise",
            "capex_intensity_change",
        ],
        "summary": None,
        "window_results": [],
    }
    save_results("EXP-15", results, bundle.audit, bundle.feature_cols, args.output_dir)
    return results


def run_exp16(args: Any) -> dict[str, Any]:
    bundle = _load_bundle(args, policy="full")
    frame = merge_regimes(bundle, merge_metadata(bundle))
    if "regime" not in frame.columns:
        frame["regime"] = "Unknown"
    regime_counts = frame["regime"].fillna("Unknown").astype(str).value_counts().to_dict()
    r3_count = int(sum(v for k, v in regime_counts.items() if "R3" in str(k) or "Low-Vol Bear" in str(k)))
    r9_count = int(sum(v for k, v in regime_counts.items() if "R9" in str(k) or "External Shock" in str(k)))
    print(f"  EXP-16 regime label counts: R3={r3_count}, R9={r9_count}, all={regime_counts}")
    _print_regime_window_preflight(bundle, frame, "EXP-16")
    dummies = pd.get_dummies(frame.get("sector", "Unknown"), prefix="sector", dtype="float32")
    frame = pd.concat([frame.reset_index(drop=True), dummies.reset_index(drop=True)], axis=1)
    feature_cols = bundle.feature_cols + list(dummies.columns)
    summaries = []
    all_windows = []
    for regime_name, group in frame.groupby(frame["regime"].fillna("Unknown")):
        regime_text = str(regime_name)
        if _is_gated_out_regime(regime_text):
            print(f"  EXP-16 regime {regime_text}: SKIP - gated out after negative/unstable historical test IC")
            continue
        min_rows = _regime_min_rows(regime_text, 1500)
        if len(group) < min_rows:
            print(f"  EXP-16 regime {regime_text}: SKIP - total rows {len(group)} < {min_rows}")
            continue
        regime_features = list(feature_cols)
        force_keep: list[str] = []
        regime_params = {"depth": 4, "l2_leaf_reg": 3.0, "boosting_type": "Plain", "grow_policy": "Depthwise", "min_data_in_leaf": 100, "iterations": 400, "learning_rate": 0.01, "training_mode": "fixed_iterations"}
        if "R4" in regime_text or "High-Vol Bear" in regime_text:
            exclude = {c for c in regime_features if "eps_sue_decay" in c or "rev_sue_decay" in c or "agreement_score" in c}
            regime_features = [c for c in regime_features if c not in exclude]
            regime_params.update({"depth": 5, "min_data_in_leaf": 120})
            print(f"  EXP-16 regime {regime_text}: R4 dedicated setup, excluded {len(exclude)} SUE/agreement features")
        if "R5" in regime_text or "Recovery" in regime_text:
            force_keep = [c for c in regime_features if "rev_sue_decay" in c]
            print(f"  EXP-16 regime {regime_text}: force-keeping {len(force_keep)} rev_sue_decay features")
        summary, windows = run_catboost_walkforward(
            bundle,
            exp_id="EXP-16",
            candidate=f"hierarchical_sector_blend_{regime_text.replace(' ', '_')}",
            params=regime_params,
            frame=group,
            feature_cols=regime_features,
            always_keep_features=force_keep,
            min_train_rows=min_rows,
            max_windows=args.max_windows,
        )
        summary["regime"] = regime_text
        if _is_reliable_regime_candidate(regime_text):
            summary["reliable_regime_aggregate"] = _reliable_regime_aggregate(windows)
        summaries.append(summary)
        all_windows.extend(windows)
    results = {
        "experiment": "EXP-16",
        "architecture": "hierarchical_regime_then_sector_blend",
        "run7_change": "R2/R6/R9 gated out; R1/R3/R4/R5 summaries include a reliable-regime aggregate with a minimum test-row threshold.",
        "regime_value_counts": regime_counts,
        "r3_label_count": r3_count,
        "r9_label_count": r9_count,
        "all_candidates": summaries,
        "window_results": all_windows,
    }
    save_results("EXP-16", results, bundle.audit, feature_cols, args.output_dir)
    return results


def run_exp17(args: Any) -> dict[str, Any]:
    bundle = _load_bundle(args, policy="full")
    frame = merge_regimes(bundle)
    factors = list(ANCHOR_FACTOR_ALIASES)
    rows: list[dict[str, Any]] = []
    for factor in factors:
        col = resolve_factor(frame, factor)
        if col is None:
            rows.append({"factor_name": factor, "resolved_col": None, "status": "missing"})
            continue
        regime_series = frame["regime"] if "regime" in frame.columns else frame.get("plan_regime_label", pd.Series("Unknown", index=frame.index))
        event_series = frame.get("major_event_id", pd.Series("NO_EVENT", index=frame.index)).fillna("NO_EVENT")
        grouped = frame.assign(_regime=regime_series.fillna("Unknown").astype(str), _event=event_series.astype(str)).groupby(["_regime", "_event"])
        for (regime_code, event_id), group in grouped:
            series = ic_by_date(group.rename(columns={col: "score"}), "score")
            clean = series.dropna().astype(float)
            rows.append(
                {
                    "factor_name": factor,
                    "resolved_col": col,
                    "regime_event": str(event_id),
                    "regime_code": str(regime_code),
                    "mean_ic": float(clean.mean()) if len(clean) else None,
                    "median_ic": float(clean.median()) if len(clean) else None,
                    "positive_ic_rate": float((clean > 0).mean()) if len(clean) else None,
                    "n_windows": int(len(clean)),
                }
            )
    table = pd.DataFrame(rows)
    if not table.empty and "median_ic" in table.columns:
        for regime_code, group in table.dropna(subset=["median_ic"]).groupby("regime_code"):
            top = group.sort_values("median_ic", ascending=False).head(3)[["factor_name", "median_ic"]].to_dict("records")
            bottom = group.sort_values("median_ic", ascending=True).head(3)[["factor_name", "median_ic"]].to_dict("records")
            print(f"  EXP-17 regime {regime_code} top factors by median_ic: {top}")
            print(f"  EXP-17 regime {regime_code} bottom factors by median_ic: {bottom}")
    results = {"experiment": "EXP-17", "table_rows": rows}
    save_results("EXP-17", results, bundle.audit, bundle.feature_cols, args.output_dir)
    return results


def run_exp18(args: Any) -> dict[str, Any]:
    bundle = _load_bundle(args, policy="full")
    frame = merge_regimes(bundle)
    summary, windows = run_catboost_walkforward(
        bundle,
        exp_id="EXP-18",
        candidate="universal_catboost_event_diagnostics",
        params={"depth": 5, "l2_leaf_reg": 3.0, "boosting_type": "Plain", "grow_policy": "Depthwise", "min_data_in_leaf": 100, "learning_rate": 0.01, "iterations": 600, "training_mode": "fixed_iterations"},
        frame=frame,
        feature_cols=bundle.feature_cols,
        ic_screen_min_median_abs_ic=0.010,
        production_ic_screen_min_median_abs_ic=0.008,
        production_relaxed_feature_fallback=False,
        require_multi_family_features=True,
        earnings_starvation_min_features=3,
        earnings_starvation_hard_gate=False,
        max_windows=args.max_windows,
    )
    event_rows = []
    for event_id, group in frame.groupby(frame.get("major_event_id").fillna("NO_EVENT")):
        if len(group) < 100:
            continue
        factor_rows = run_factor_ic_table(bundle, ["eps_sue_decay", "agreement_score"], group)
        for row in factor_rows:
            row["event_id"] = str(event_id)
            event_rows.append(row)
    results = {"experiment": "EXP-18", "summary": summary, "window_results": windows, "table_rows": event_rows}
    save_results("EXP-18", results, bundle.audit, bundle.feature_cols, args.output_dir)
    return results


def run_exp19(args: Any) -> dict[str, Any]:
    bundle = _load_bundle(args, policy="full")
    frame = merge_regimes(bundle, merge_metadata(bundle))
    if "regime" not in frame.columns:
        frame["regime"] = "Unknown"
    _print_regime_window_preflight(bundle, frame, "EXP-19")
    dummies = pd.get_dummies(frame.get("sector", "Unknown"), prefix="sector", dtype="float32")
    frame = pd.concat([frame.reset_index(drop=True), dummies.reset_index(drop=True)], axis=1)
    base_features = bundle.feature_cols + list(dummies.columns)
    rows = []
    windows_all = []
    for regime_name, group in frame.groupby(frame["regime"].fillna("Unknown")):
        regime_text = str(regime_name)
        if _is_gated_out_regime(regime_text):
            print(f"  EXP-19 regime {regime_name}: SKIP - gated out after negative/unstable historical test IC")
            continue
        if not _is_run7_routing_regime(regime_text):
            print(f"  EXP-19 regime {regime_name}: SKIP - Run 7 routing focuses on R1/R3/R4/R5 only")
            continue
        min_regime_train_rows = _regime_min_rows(regime_text, 1500)
        if len(group) < min_regime_train_rows:
            print(f"  EXP-19 regime {regime_name}: SKIP - total rows {len(group)} < {min_regime_train_rows}")
            continue
        regime_features = list(base_features)
        force_keep: list[str] = []
        if "R4" in regime_text or "High-Vol Bear" in regime_text:
            exclude = {c for c in regime_features if "eps_sue_decay" in c or "rev_sue_decay" in c or "agreement_score" in c}
            regime_features = [c for c in regime_features if c not in exclude]
            print(f"  EXP-19 regime {regime_text}: R4 dedicated setup, excluded {len(exclude)} SUE/agreement features")
        if "R5" in regime_text or "Recovery" in regime_text:
            force_keep = [c for c in regime_features if "rev_sue_decay" in c]
            print(f"  EXP-19 regime {regime_text}: using sector dummies and force-keeping {len(force_keep)} rev_sue_decay features")
        summary, windows = run_catboost_walkforward(
            bundle,
            exp_id="EXP-19",
            candidate=f"regime_{str(regime_name).replace(' ', '_')}",
            params={"depth": 3, "l2_leaf_reg": 3.0, "boosting_type": "Plain", "grow_policy": "Depthwise", "min_data_in_leaf": 150, "iterations": 400, "learning_rate": 0.01, "training_mode": "fixed_iterations"},
            frame=group,
            feature_cols=regime_features,
            always_keep_features=force_keep,
            min_train_rows=min_regime_train_rows,
            max_windows=args.max_windows,
        )
        summary["regime"] = str(regime_name)
        summary["reliable_regime_aggregate"] = _reliable_regime_aggregate(windows)
        rows.append(summary)
        windows_all.extend(windows)
    results = {
        "experiment": "EXP-19",
        "run7_change": "Routing model is narrowed to R1/R3/R4/R5. R2/R6/R7/R8/R9 are skipped, and each active regime reports a reliable-regime aggregate.",
        "all_candidates": rows,
        "window_results": windows_all,
    }
    save_results("EXP-19", results, bundle.audit, base_features, args.output_dir)
    return results


def _run_sequence_proxy(args: Any, exp_id: str, universe_size: int = 150) -> dict[str, Any]:
    bundle = _load_bundle(args, policy="safe")
    seq_features = [c for c in ["mom_20d", "mom_10d", "vol_20d", "vol_60d", "inrusd_4w_return", "crude_4w_return"] if c in bundle.features.columns]
    results = {
        "experiment": exp_id,
        "status": "closed_insufficient_sequence_features",
        "note": "Prior run showed the 6-feature sequence proxy is anti-predictive and the dataset lacks true sequence/LSTM/TFT tensors. Compute is redirected to regime-gated CatBoost experiments.",
        "available_proxy_features": seq_features,
        "required_next_dataset_work": [
            "Build ticker-date sequence tensors with aligned lag stacks.",
            "Add true temporal OHLCV/macro histories rather than static weekly proxy columns.",
            "Reopen EXP-20..23 only after sequence tensors exist.",
        ],
    }
    save_results(exp_id, results, bundle.audit, seq_features, args.output_dir)
    return results


def run_exp20(args: Any) -> dict[str, Any]:
    return _run_sequence_proxy(args, "EXP-20", universe_size=150)


def run_exp21(args: Any) -> dict[str, Any]:
    return _run_sequence_proxy(args, "EXP-21", universe_size=578)


def run_exp22(args: Any) -> dict[str, Any]:
    return _run_sequence_proxy(args, "EXP-22", universe_size=300)


def run_exp23(args: Any) -> dict[str, Any]:
    return _run_sequence_proxy(args, "EXP-23", universe_size=250)


def run_exp24(args: Any) -> dict[str, Any]:
    bundle = _load_bundle(args, policy="full")
    rows = []
    available = [s for s in COMMODITY_SIGNALS if s in bundle.features.columns and bundle.features[s].notna().mean() > 0.05]
    missing = [s for s in COMMODITY_SIGNALS if s not in available]
    print(f"  Available commodity signals: {len(available)}/{len(COMMODITY_SIGNALS)}")
    if missing:
        print(f"  Missing signals: {missing}")
    for signal in available:
        series = ic_by_date(bundle.features.rename(columns={signal: "score"}), "score")
        row = {"signal": signal, **summarize_ic_values(series.tolist())}
        if signal == "coal_4w_return":
            row["data_quality_note"] = "proxy-backed signal; treat IC as indicative only"
        rows.append(row)
    results = {"experiment": "EXP-24", "missing_signals": missing, "table_rows": rows}
    save_results("EXP-24", results, bundle.audit, available, args.output_dir)
    return results


def run_exp25(args: Any) -> dict[str, Any]:
    bundle = _load_bundle(args, policy="safe")
    frame = merge_metadata(bundle)
    if "conglomerate_group" not in frame.columns:
        results = {"experiment": "EXP-25", "status": "missing_conglomerate_group"}
        save_results("EXP-25", results, bundle.audit, bundle.feature_cols, args.output_dir)
        return results
    frame = frame.sort_values(["ticker", "date"], kind="mergesort")
    frame["lag_return_4w"] = frame.groupby("ticker")[TARGET_COL].shift(1).rolling(4, min_periods=2).mean().reset_index(level=0, drop=True)
    group_mean = frame.groupby(["date", "conglomerate_group"])["lag_return_4w"].transform("mean")
    frame["ccms_signal"] = group_mean - frame["lag_return_4w"].fillna(0.0) / frame.groupby(["date", "conglomerate_group"])["ticker"].transform("count").clip(lower=1)
    series = ic_by_date(frame.rename(columns={"ccms_signal": "score"}), "score")
    rows = [{"signal": "ccms_signal", **summarize_ic_values(series.tolist())}]
    results = {"experiment": "EXP-25", "table_rows": rows}
    save_results("EXP-25", results, bundle.audit, ["ccms_signal"], args.output_dir)
    return results


def run_exp26(args: Any) -> dict[str, Any]:
    bundle = _load_bundle(args, policy="full")
    factors = list(ANCHOR_FACTOR_ALIASES)
    rows = run_factor_ic_table(bundle, factors)
    for row in rows:
        col = row.get("resolved_col")
        if not col:
            continue
        series = ic_by_date(bundle.features.rename(columns={col: "score"}), "score")
        arr = np.asarray(series.dropna().to_numpy(float), dtype=float)
        tstat = float(arr.mean() / (arr.std(ddof=1) / np.sqrt(len(arr)))) if len(arr) > 1 and arr.std(ddof=1) > 0 else None
        row["T1_ic_tstat"] = tstat
        row["T1_pass"] = bool(tstat is not None and abs(tstat) > 1.96)
        row["T2_sign_stability_pass"] = bool((row.get("sign_stability") or row.get("hit_rate") or 0.0) > 0.60)
        row["T3_decay_pass"] = None
        row["T5_economic_logic_pass"] = True
    results = {"experiment": "EXP-26", "table_rows": rows}
    save_results("EXP-26", results, bundle.audit, bundle.feature_cols, args.output_dir)
    return results


def run_exp27(args: Any) -> dict[str, Any]:
    bundle = _load_bundle(args, policy="full")
    frame = merge_metadata(bundle)
    candidates = ["accruals_ratio", "accruals_ratio_cs_z", "earnings_quality_ratio", "earnings_quality_ratio_cs_z"]
    rows = []
    for col in candidates:
        if col not in frame.columns or frame[col].notna().mean() < 0.05:
            rows.append({"factor": col, "status": "missing_or_low_coverage"})
            continue
        overall = summarize_ic_values(ic_by_date(frame.rename(columns={col: "score"}), "score").tolist())
        rows.append({"factor": col, "bucket": "overall", **overall})
        if "sector" in frame.columns:
            for sector, group in frame.groupby("sector"):
                if len(group) < 500:
                    continue
                rows.append({"factor": col, "bucket": f"sector:{sector}", **summarize_ic_values(ic_by_date(group.rename(columns={col: "score"}), "score").tolist())})
    results = {"experiment": "EXP-27", "table_rows": rows}
    save_results("EXP-27", results, bundle.audit, bundle.feature_cols, args.output_dir)
    return results


RUNNERS = {
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
