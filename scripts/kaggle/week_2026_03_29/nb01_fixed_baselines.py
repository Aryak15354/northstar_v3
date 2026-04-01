#!/usr/bin/env python3
"""NB-01: run the fixed tree-model baselines on the weekly export."""

from __future__ import annotations

import argparse
import importlib.util
import os
import sys
from pathlib import Path
from typing import Any

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SHARED_DIR = PROJECT_ROOT / "notebooks" / "kaggle_sprint" / "shared"
os.environ.setdefault("MPLCONFIGDIR", str((PROJECT_ROOT / "tmp" / ".mplconfig").resolve()))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_DIR))

def _load_shared_module(module_name: str):
    try:
        return __import__(module_name)
    except ModuleNotFoundError:
        module_path = SHARED_DIR / f"{module_name}.py"
        if not module_path.exists():
            raise FileNotFoundError(f"missing_shared_kaggle_module:{module_path}")
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"unable_to_load_shared_kaggle_module:{module_path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module


_track_a_runner = _load_shared_module("track_a_runner")
TrackARunConfig = _track_a_runner.TrackARunConfig
run_track_a_notebook = _track_a_runner.run_track_a_notebook

from scripts.kaggle.week_2026_03_29.common import (  # noqa: E402
    build_feature_coverage_audit,
    json_ready,
    load_export_artifacts,
    make_run_dir,
    read_json,
    resolve_export_dir,
    select_feature_columns,
    subset_feature_export,
    write_json,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run NB-01 fixed baseline models.")
    parser.add_argument("--export-dir", type=Path, required=True)
    parser.add_argument("--nb00-report", type=Path, default=None, help="feature_health_report.json from NB-00.")
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--profile", choices=["smoke", "full"], default="full")
    parser.add_argument("--max-splits", type=int, default=None)
    parser.add_argument("--catboost-depth", type=int, default=4)
    parser.add_argument("--catboost-min-leaf", type=int, default=40)
    parser.add_argument("--catboost-l2", type=float, default=15.0)
    parser.add_argument("--catboost-iterations", type=int, default=800)
    parser.add_argument("--xgboost-mode", choices=["ranking", "regression"], default="regression")
    parser.add_argument("--dead-feature-null-threshold", type=float, default=0.80)
    parser.add_argument("--dead-feature-min-unique", type=int, default=1)
    parser.add_argument("--dead-feature-min-cs-std", type=float, default=1e-8)
    parser.add_argument("--dead-feature-min-abs-ic", type=float, default=0.002)
    parser.add_argument("--dead-feature-min-abs-tstat", type=float, default=1.5)
    parser.add_argument("--disable-dead-feature-filter", action="store_true")
    return parser.parse_args()


def _selected_features(export_dir: Path, nb00_report: Path | None) -> list[str]:
    if nb00_report is None:
        guessed = export_dir / "feature_health_report.json"
        nb00_report = guessed if guessed.exists() else None
    if nb00_report is None or not nb00_report.exists():
        return []
    payload = read_json(nb00_report)
    tier_lists = dict(payload.get("tier_lists") or {})
    return list(dict.fromkeys([*(tier_lists.get("TIER_1") or []), *(tier_lists.get("TIER_2") or [])]))


def _decision(summary: dict[str, Any]) -> str:
    mean_ic = float(summary.get("mean_test_ic", float("nan")) or float("nan"))
    ratio = float(summary.get("mean_train_test_ratio", float("nan")) or float("nan"))
    hit_rate = float(summary.get("mean_hit_rate", float("nan")) or float("nan"))
    if mean_ic > 0.015 and ratio < 2.5 and hit_rate > 0.51:
        return "PROMOTE"
    if mean_ic > 0.010 and ratio < 8.0:
        return "INVESTIGATE"
    return "REJECT"


def _load_feature_health_table(nb00_report: Path | None) -> pd.DataFrame:
    if nb00_report is None:
        return pd.DataFrame()
    nb00_dir = nb00_report.parent
    for candidate in [
        nb00_dir / "feature_health_table.parquet",
        nb00_dir / "feature_health_table.csv",
    ]:
        if not candidate.exists():
            continue
        if candidate.suffix == ".parquet":
            return pd.read_parquet(candidate)
        return pd.read_csv(candidate)
    return pd.DataFrame()


def _diagnostic_feature_extras(full_features: pd.DataFrame) -> list[str]:
    tokens = (
        "fii",
        "dii",
        "pledge",
        "bulk",
        "earnings_quality",
        "power",
        "piotroski",
        "bab",
        "amihud",
        "max_ret_20d",
        "eps_sue",
        "rev_sue",
        "combined_sue",
    )
    extras: list[str] = []
    for column in full_features.columns:
        name = str(column)
        if name in {"date", "ticker", "target_weekly_return", "forward_return_5d"}:
            continue
        if not pd.api.types.is_numeric_dtype(full_features[name]):
            continue
        if any(token in name.lower() for token in tokens):
            extras.append(name)
    return list(dict.fromkeys(extras))


def _prune_dead_features(
    candidate_features: list[str],
    coverage_audit: pd.DataFrame,
    feature_health: pd.DataFrame,
    *,
    disable_filter: bool,
    min_abs_ic: float,
    min_abs_tstat: float,
) -> tuple[list[str], list[str], list[str]]:
    if disable_filter:
        return list(candidate_features), [], []

    audit_lookup = coverage_audit.set_index("feature").to_dict(orient="index") if not coverage_audit.empty else {}
    health_lookup = feature_health.set_index("feature").to_dict(orient="index") if not feature_health.empty else {}
    kept: list[str] = []
    removed: list[str] = []
    protected: list[str] = []

    for feature in candidate_features:
        audit_row = audit_lookup.get(feature, {})
        likely_dead = bool(audit_row.get("likely_dead", False))
        if not likely_dead:
            kept.append(feature)
            continue

        health_row = health_lookup.get(feature, {})
        mean_ic = abs(float(health_row.get("mean_ic", 0.0) or 0.0))
        ic_tstat = abs(float(health_row.get("ic_tstat", 0.0) or 0.0))
        tier = str(health_row.get("tier", ""))
        has_statistical_support = bool(
            mean_ic >= float(min_abs_ic)
            or ic_tstat >= float(min_abs_tstat)
            or tier in {"TIER_1", "TIER_2"}
        )
        if has_statistical_support:
            kept.append(feature)
            protected.append(feature)
        else:
            removed.append(feature)

    return kept, removed, protected


def main() -> int:
    args = parse_args()
    export_artifacts = resolve_export_dir(args.export_dir)
    output_dir = args.output_dir.expanduser().resolve() if args.output_dir else make_run_dir(None, "nb01_fixed_baselines")
    output_dir.mkdir(parents=True, exist_ok=True)

    selected = _selected_features(export_artifacts.export_dir, args.nb00_report)
    full_features, _, _, _ = load_export_artifacts(export_artifacts.export_dir)
    candidate_features = selected if selected else select_feature_columns(full_features)
    coverage_audit = build_feature_coverage_audit(
        full_features,
        candidate_features,
        null_threshold=args.dead_feature_null_threshold,
        min_unique=args.dead_feature_min_unique,
        min_cross_sectional_std=args.dead_feature_min_cs_std,
    )
    feature_health = _load_feature_health_table(args.nb00_report)
    filtered_selected, dead_features, protected_dead_features = _prune_dead_features(
        candidate_features,
        coverage_audit,
        feature_health,
        disable_filter=args.disable_dead_feature_filter,
        min_abs_ic=args.dead_feature_min_abs_ic,
        min_abs_tstat=args.dead_feature_min_abs_tstat,
    )
    write_json(output_dir / "feature_coverage_audit.json", coverage_audit.to_dict(orient="records"))
    coverage_audit.to_csv(output_dir / "feature_coverage_audit.csv", index=False)

    diagnostic_extras = [feature for feature in _diagnostic_feature_extras(full_features) if feature not in set(filtered_selected)]
    filtered_export_dir = output_dir / "tier12_export"
    subset_feature_export(
        source_dir=export_artifacts.export_dir,
        output_dir=filtered_export_dir,
        selected_features=[*filtered_selected, *diagnostic_extras] if filtered_selected else None,
        model_feature_names=filtered_selected,
    )

    config = TrackARunConfig(
        data_dir=filtered_export_dir,
        output_dir=output_dir / "track_a_tree_baseline",
        skip_days=set(),
        continue_on_error=True,
        resume_from_checkpoint=True,
        run_profile=args.profile,
        max_splits=args.max_splits,
        model_filter=["xgboost", "lightgbm", "catboost"],
        feature_mode="full",
        normalize_raw_financials=True,
        require_group_ranking=True,
        catboost_depth=args.catboost_depth,
        catboost_min_data_in_leaf=args.catboost_min_leaf,
        catboost_l2_leaf_reg=args.catboost_l2,
        catboost_iterations=args.catboost_iterations,
        xgboost_mode=args.xgboost_mode,
    )
    state = run_track_a_notebook(config)

    rows = []
    for state_key, model_name in [
        ("xgb_summary", "XGBoost"),
        ("lightgbm_summary", "LightGBM"),
        ("catboost_summary", "CatBoost"),
    ]:
        summary = dict(state.get(state_key) or {})
        if not summary:
            continue
        rows.append(
            {
                "model": model_name,
                "mean_ic": float(summary.get("mean_test_ic", float("nan"))),
                "ic_ir": float(summary.get("ic_ir", float("nan"))),
                "ratio": float(summary.get("mean_train_test_ratio", float("nan"))),
                "hit_rate": float(summary.get("mean_hit_rate", float("nan"))),
                "windows_completed": int(summary.get("windows_completed", 0) or 0),
                "verdict": str(summary.get("verdict", "UNKNOWN")),
                "decision": _decision(summary),
            }
        )

    payload = {
        "generated_at": state.get("run_started_at") if isinstance(state, dict) else None,
        "source_export_dir": str(export_artifacts.export_dir),
        "filtered_export_dir": str(filtered_export_dir),
        "selected_feature_count": len(filtered_selected),
        "selected_features": filtered_selected,
        "candidate_feature_count": len(candidate_features),
        "dead_feature_count": len(dead_features),
        "dead_features": dead_features,
        "protected_dead_feature_count": len(protected_dead_features),
        "protected_dead_features": protected_dead_features,
        "diagnostic_extra_count": len(diagnostic_extras),
        "diagnostic_extras": diagnostic_extras,
        "models": rows,
    }
    write_json(output_dir / "baseline_results.json", payload)
    print(json_ready({"models": rows, "filtered_export_dir": str(filtered_export_dir)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
