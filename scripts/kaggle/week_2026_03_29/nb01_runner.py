#!/usr/bin/env python3
"""NB-01 thick runner for config-driven Kaggle baseline experiments."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import traceback
from pathlib import Path
from typing import Any
from collections import Counter

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


def _track_a_symbols():
    module = _load_shared_module("track_a_runner")
    return module.TrackARunConfig, module.run_track_a_notebook

from scripts.kaggle.week_2026_03_29.common import (  # noqa: E402
    json_ready,
    load_export_artifacts,
    load_export_manifest,
    read_json,
    resolve_export_dir,
    subset_feature_export,
    write_json,
)
from src.research.compare_runs import compare as compare_runs  # noqa: E402
from src.research.config_loader import load_experiment_config  # noqa: E402
from src.research.experiment_logger import ExperimentLogger  # noqa: E402
from src.research.feature_filter import (  # noqa: E402
    apply_dead_filter,
    resolve_feature_candidates,
)
from src.research.regime_assigner import RegimeAssigner  # noqa: E402
from src.research.reference_data import resolve_reference_root, validate_reference_bundle  # noqa: E402
from src.research.run_registry import RunRegistry  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run NB-01 via config-driven Kaggle architecture.")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--export-dir", type=Path, default=None)
    parser.add_argument("--nb00-report", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--profile", choices=["smoke", "full"], default="full")
    parser.add_argument("--max-splits", type=int, default=None)
    parser.add_argument("--compare-run-id", action="append", default=[])
    return parser.parse_args()


def _resolve_nb00_report(cfg: dict[str, Any], export_dir: Path, provided: Path | None) -> Path | None:
    candidates: list[Path] = []
    if provided is not None:
        candidates.append(provided.expanduser().resolve())
    data_cfg = dict(cfg.get("data") or {})
    configured = str(data_cfg.get("nb00_report", "") or "").strip()
    if configured:
        candidates.append(Path(configured).expanduser().resolve())
    candidates.extend(
        [
            export_dir / "feature_health_report.json",
            export_dir.parent / "01_nb00" / "feature_health_report.json",
            export_dir.parent / "nb00" / "feature_health_report.json",
        ]
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _load_feature_health_table(nb00_report: Path | None) -> pd.DataFrame:
    if nb00_report is None:
        return pd.DataFrame()
    nb00_dir = nb00_report.parent
    for candidate in [nb00_dir / "feature_health_table.parquet", nb00_dir / "feature_health_table.csv"]:
        if not candidate.exists():
            continue
        if candidate.suffix == ".parquet":
            return pd.read_parquet(candidate)
        return pd.read_csv(candidate)
    return pd.DataFrame()


def _load_nb00_selected_features(nb00_report: Path | None, cfg: dict[str, Any]) -> list[str]:
    if nb00_report is None or not nb00_report.exists():
        return []
    payload = read_json(nb00_report)
    tier_lists = dict(payload.get("tier_lists") or {})
    requested_tiers = [str(tier) for tier in (cfg.get("features", {}) or {}).get("nb00_tiers") or ["TIER_1", "TIER_2"]]
    selected: list[str] = []
    for tier in requested_tiers:
        selected.extend(str(feature) for feature in tier_lists.get(tier) or [])
    return list(dict.fromkeys(selected))


def _preprocess(df: pd.DataFrame, cfg: dict[str, Any]) -> tuple[pd.DataFrame, list[str], list[dict[str, Any]]]:
    prep = dict(cfg.get("preprocessing") or {})
    work = df.copy()
    derived_features: list[str] = []
    audit_rows: list[dict[str, Any]] = []
    if not prep.get("eps_sue_decay_ffill", False):
        return work, derived_features, audit_rows

    if "eps_sue_decay" not in work.columns:
        return work, derived_features, audit_rows

    work["date"] = pd.to_datetime(work["date"], errors="coerce").dt.normalize()
    work = work.sort_values(["ticker", "date"], kind="mergesort").reset_index(drop=True)
    original = pd.to_numeric(work["eps_sue_decay"], errors="coerce")
    raw_available = original.notna()
    filled = original.groupby(work["ticker"], sort=False).ffill()
    work["eps_sue_decay"] = filled.astype("float32")
    if prep.get("eps_sue_decay_availability_flag", False):
        flag_name = "eps_sue_decay_raw_available"
        work[flag_name] = raw_available.astype("float32")
        derived_features.append(flag_name)
    audit_rows.append(
        {
            "feature": "eps_sue_decay",
            "coverage_before": float(raw_available.mean()),
            "coverage_after": float(pd.to_numeric(work["eps_sue_decay"], errors="coerce").notna().mean()),
            "flag_column": derived_features[0] if derived_features else None,
        }
    )
    return work, derived_features, audit_rows


def _build_track_a_config(
    cfg: dict[str, Any],
    *,
    data_dir: Path,
    output_dir: Path,
    profile: str,
    max_splits: int | None,
) -> Any:
    TrackARunConfig, _ = _track_a_symbols()
    models_cfg = dict(cfg.get("models") or {})
    preprocessing_cfg = dict(cfg.get("preprocessing") or {})
    deployment_cfg = dict(cfg.get("deployment") or {})
    catboost_cfg = dict(models_cfg.get("catboost") or {})
    xgboost_cfg = dict(models_cfg.get("xgboost") or {})
    return TrackARunConfig(
        data_dir=data_dir,
        output_dir=output_dir,
        skip_days=set(),
        continue_on_error=bool((cfg.get("runtime") or {}).get("continue_on_error", True)),
        resume_from_checkpoint=bool((cfg.get("runtime") or {}).get("resume_from_checkpoint", True)),
        run_profile=profile,
        max_splits=max_splits,
        model_filter=[str(model) for model in models_cfg.get("run") or ["xgboost", "lightgbm", "catboost"]],
        feature_mode="full",
        normalize_raw_financials=bool(preprocessing_cfg.get("normalize_raw_financials", True)),
        require_group_ranking=True,
        catboost_depth=int(catboost_cfg.get("depth", 4) or 4),
        catboost_min_data_in_leaf=int(catboost_cfg.get("min_data_in_leaf", 40) or 40),
        catboost_l2_leaf_reg=float(catboost_cfg.get("l2_leaf_reg", 15.0) or 15.0),
        catboost_iterations=int(catboost_cfg.get("iterations", 800) or 800),
        xgboost_mode=str(xgboost_cfg.get("mode", "regression") or "regression"),
        regime_caps=dict((cfg.get("regime") or {}).get("exposure_caps") or {"default": 0.40}),
        deployment_thresholds={
            "high_ic": float(dict(deployment_cfg.get("ic_thresholds") or {}).get("high", 0.015) or 0.015),
            "medium_ic": float(dict(deployment_cfg.get("ic_thresholds") or {}).get("medium", 0.005) or 0.005),
            "high_exposure": float(dict(deployment_cfg.get("exposures") or {}).get("high", 0.40) or 0.40),
            "medium_exposure": float(dict(deployment_cfg.get("exposures") or {}).get("medium", 0.20) or 0.20),
            "low_exposure": float(dict(deployment_cfg.get("exposures") or {}).get("low", 0.05) or 0.05),
        },
    )


def _decision(summary: dict[str, Any], cfg: dict[str, Any]) -> str:
    gates = dict(cfg.get("promotion_gates") or {})
    investigate = dict(gates.get("investigate_band") or {})
    mean_ic = float(summary.get("mean_test_ic", float("nan")) or float("nan"))
    ratio = float(summary.get("mean_train_test_ratio", float("nan")) or float("nan"))
    hit_rate = float(summary.get("mean_hit_rate", float("nan")) or float("nan"))
    ic_ir = float(summary.get("ic_ir", float("nan")) or float("nan"))
    if (
        mean_ic >= float(gates.get("mean_ic_min", 0.020) or 0.020)
        and ic_ir >= float(gates.get("ic_ir_min", 0.500) or 0.500)
        and ratio <= float(gates.get("train_test_ratio_max", 2.50) or 2.50)
        and hit_rate >= float(gates.get("hit_rate_min", 0.50) or 0.50)
    ):
        return "B_PROMOTE_LIMITED"
    if ic_ir >= float(investigate.get("ic_ir_min", 0.500) or 0.500) and ratio <= float(
        investigate.get("train_test_ratio_max", 3.50) or 3.50
    ):
        return "B_INVESTIGATE"
    return "C_DO_NOT_PROMOTE"


def _regime_breakdown(windows: list[dict[str, Any]]) -> tuple[dict[str, Any], float, float, int]:
    frame = pd.DataFrame(windows)
    if frame.empty or "regime" not in frame.columns:
        return {}, float("nan"), float("nan"), 0
    grouped = frame.groupby("regime", dropna=False)["test_ic"].agg(["mean", "count"]).reset_index()
    by_regime = {
        str(row["regime"]): {"mean_ic": float(row["mean"]), "n_windows": int(row["count"])}
        for _, row in grouped.iterrows()
    }
    clean = frame[~frame["regime"].isin(["R7|Rate-Event", "R8|Election/Binary"])].copy()
    if clean.empty:
        return by_regime, float("nan"), float("nan"), 0
    mean_ic = float(pd.to_numeric(clean["test_ic"], errors="coerce").mean())
    std_ic = float(pd.to_numeric(clean["test_ic"], errors="coerce").std(ddof=1)) if len(clean) > 1 else 0.0
    ic_ir = float(mean_ic / std_ic) if abs(std_ic) > 1e-12 else 0.0
    return by_regime, mean_ic, ic_ir, int(len(clean))


def _resolve_registry_and_stage_dir(
    resolved_run_id: str,
    cfg: dict[str, Any],
    output_dir: Path | None,
    *,
    stage_name: str,
) -> tuple[RunRegistry, Path]:
    if output_dir is None:
        registry = RunRegistry(resolved_run_id, cfg=cfg)
        registry.initialize(cfg)
        return registry, registry.stage_output_dir(stage_name)

    requested = output_dir.expanduser().resolve()
    if requested.name == stage_name:
        output_root = requested.parent.parent if requested.parent.name == resolved_run_id else requested.parent
    elif requested.name == resolved_run_id:
        output_root = requested.parent
    else:
        output_root = requested
    registry = RunRegistry(resolved_run_id, cfg=cfg, output_root=output_root)
    registry.initialize(cfg)
    return registry, registry.stage_output_dir(stage_name)


def _runtime_regime_assets(
    splits: list[dict[str, Any]],
    regimes_df: pd.DataFrame,
    cfg: dict[str, Any],
) -> tuple[list[dict[str, Any]], pd.DataFrame, dict[str, Any]]:
    regime_assigner = RegimeAssigner(cfg["regime"])
    runtime_labels = regime_assigner.assign_all_windows(splits, regime_frame=regimes_df)
    runtime_splits: list[dict[str, Any]] = []
    for idx, (split, label) in enumerate(zip(splits, runtime_labels, strict=False), start=1):
        payload = dict(split)
        payload["window_id"] = int(payload.get("window_id", idx) or idx)
        payload["regime"] = label
        payload["regime_cap"] = regime_assigner.get_exposure_cap(label)
        runtime_splits.append(payload)
    runtime_regimes = regime_assigner.apply_window_regimes(regimes_df, runtime_splits, labels=runtime_labels)
    counts = Counter(runtime_labels)
    audit = {
        "regime_config_version": str(cfg.get("_regime_validation", {}).get("version", "") or ""),
        "window_rows": [
            {
                "window_id": int(split["window_id"]),
                "test_start": str(split.get("test_start")),
                "test_end": str(split.get("test_end")),
                "regime": str(split.get("regime")),
                "regime_cap": float(split.get("regime_cap", 0.40) or 0.40),
            }
            for split in runtime_splits
        ],
        "regime_counts": {str(label): int(count) for label, count in sorted(counts.items())},
        "r7_r8_count": int(counts.get("R7|Rate-Event", 0) + counts.get("R8|Election/Binary", 0)),
    }
    return runtime_splits, runtime_regimes, audit


def run_experiment(
    run_id: str,
    *,
    export_dir: Path | None = None,
    nb00_report: Path | None = None,
    output_dir: Path | None = None,
    profile: str = "full",
    max_splits: int | None = None,
    compare_run_ids: list[str] | None = None,
) -> dict[str, Any]:
    cfg = load_experiment_config(run_id)
    resolved_run_id = str((cfg.get("experiment") or {}).get("run_id", run_id) or run_id)
    registry, stage_dir = _resolve_registry_and_stage_dir(resolved_run_id, cfg, output_dir, stage_name="nb01")
    logger = ExperimentLogger(run_id=resolved_run_id, cfg=cfg, registry=registry)
    logger.snapshot_config("merged_config.yaml")

    stage_dir.mkdir(parents=True, exist_ok=True)
    registry.mark_stage_started(
        "nb01",
        metadata={"profile": profile, "max_splits": max_splits, "output_dir": str(stage_dir)},
    )

    try:
        data_cfg = dict(cfg.get("data") or {})
        configured_export = Path(str(data_cfg.get("export_dir", "") or "")).expanduser() if data_cfg.get("export_dir") else None
        requested_export = export_dir.expanduser().resolve() if export_dir is not None else configured_export
        export_artifacts = resolve_export_dir(requested_export)
        source_export_manifest = load_export_manifest(export_artifacts.export_dir)
        full_features, splits, regimes_df, _ = load_export_artifacts(export_artifacts.export_dir)
        nb00_report_path = _resolve_nb00_report(cfg, export_artifacts.export_dir, nb00_report)
        nb00_selected = _load_nb00_selected_features(nb00_report_path, cfg)
        feature_health = _load_feature_health_table(nb00_report_path)

        preprocessed_features, derived_features, preprocess_audit = _preprocess(full_features, cfg)
        candidate_features = resolve_feature_candidates(
            preprocessed_features,
            cfg,
            nb00_selected_features=nb00_selected,
        )
        filter_result = apply_dead_filter(
            preprocessed_features,
            candidate_features,
            cfg,
            feature_health=feature_health,
        )
        selected_features = list(dict.fromkeys([*filter_result.selected_features, *derived_features]))
        runtime_splits, runtime_regimes_df, runtime_regime_audit = _runtime_regime_assets(splits, regimes_df, cfg)

        reference_root = resolve_reference_root(export_artifacts.export_dir, cfg=cfg, required=False)
        reference_audit = dict(source_export_manifest.get("reference_audit") or {})
        if reference_root is not None:
            reference_audit = validate_reference_bundle(
                reference_root,
                features_df=preprocessed_features,
                strict=profile != "smoke",
                expected_universe_size=int(
                    dict(cfg.get("reference") or {}).get(
                        "required_universe_size",
                        dict(cfg.get("data") or {}).get("expected_universe_size", 500),
                    )
                    or 500
                ),
            )
        logger.log_day("reference_data", reference_audit)
        logger.log_day("runtime_regime_assignment", runtime_regime_audit)

        filtered_export_dir = stage_dir / "tier12_export"
        subset_feature_export(
            source_dir=export_artifacts.export_dir,
            output_dir=filtered_export_dir,
            selected_features=selected_features,
            model_feature_names=selected_features,
            feature_frame=preprocessed_features,
            splits_override=runtime_splits,
            regime_frame=runtime_regimes_df,
            manifest_updates={
                "experiment_run_id": resolved_run_id,
                "regime_config_version": cfg.get("_regime_validation", {}).get("version"),
                "reference_audit": reference_audit,
                "runtime_regime_assignment": runtime_regime_audit,
            },
        )

        _, run_track_a_notebook = _track_a_symbols()
        track_config = _build_track_a_config(
            cfg,
            data_dir=filtered_export_dir,
            output_dir=stage_dir / "track_a_tree_baseline",
            profile=profile,
            max_splits=max_splits,
        )
        state = run_track_a_notebook(track_config)
        deployment_summary = dict(state.get("deployment_summary") or {})
        deployment_simulation = list(state.get("deployment_simulation") or [])
        if deployment_summary:
            logger.log_deployment(
                deployment_simulation,
                mean_exposure=float(deployment_summary.get("mean_exposure", float("nan")) or float("nan")),
                windows_above_20pct=int(deployment_summary.get("windows_above_20pct", 0) or 0),
                windows_in_hold=int(deployment_summary.get("windows_in_hold_5pct", 0) or 0),
            )

        model_map = [
            ("xgboost", "xgb_results", "xgb_summary"),
            ("lightgbm", "lightgbm_results", "lightgbm_summary"),
            ("catboost", "catboost_results", "catboost_summary"),
        ]
        rows: list[dict[str, Any]] = []
        model_results: dict[str, Any] = {}
        for model_key, results_key, summary_key in model_map:
            result_payload = dict(state.get(results_key) or {})
            summary_payload = dict(state.get(summary_key) or {})
            if not summary_payload:
                continue
            for window in result_payload.get("windows") or []:
                logger.log_window(
                    window_num=int(window.get("window_id", 0) or 0),
                    model=model_key,
                    train_ic=float(window.get("train_ic", float("nan")) or float("nan")),
                    test_ic=float(window.get("test_ic", float("nan")) or float("nan")),
                    ratio=float(window.get("train_test_ratio", float("nan")) or float("nan")),
                    hit_rate=float(window.get("hit_rate", float("nan")) or float("nan")),
                    regime=str(window.get("regime", "unknown") or "unknown"),
                )
            logger.log_model_summary(
                model=model_key,
                mean_ic=float(summary_payload.get("mean_test_ic", float("nan")) or float("nan")),
                ic_ir=float(summary_payload.get("ic_ir", float("nan")) or float("nan")),
                ratio=float(summary_payload.get("mean_train_test_ratio", float("nan")) or float("nan")),
                hit_rate=float(summary_payload.get("mean_hit_rate", float("nan")) or float("nan")),
                verdict=str(summary_payload.get("verdict", "UNKNOWN") or "UNKNOWN"),
                windows_completed=int(summary_payload.get("windows_completed", 0) or 0),
            )
            breakdown, excl_mean_ic, excl_ic_ir, excl_windows = _regime_breakdown(list(result_payload.get("windows") or []))
            logger.log_regime_breakdown(model_key, breakdown, excl_mean_ic, excl_ic_ir, excl_windows)
            decision = _decision(summary_payload, cfg)
            rows.append(
                {
                    "model": model_key,
                    "mean_ic": float(summary_payload.get("mean_test_ic", float("nan")) or float("nan")),
                    "ic_ir": float(summary_payload.get("ic_ir", float("nan")) or float("nan")),
                    "ratio": float(summary_payload.get("mean_train_test_ratio", float("nan")) or float("nan")),
                    "hit_rate": float(summary_payload.get("mean_hit_rate", float("nan")) or float("nan")),
                    "windows_completed": int(summary_payload.get("windows_completed", 0) or 0),
                    "verdict": str(summary_payload.get("verdict", "UNKNOWN") or "UNKNOWN"),
                    "decision": decision,
                }
            )
            model_results[model_key] = {
                "summary": summary_payload,
                "decision": decision,
            }

        best_row = max(rows, key=lambda row: (float(row.get("ic_ir", float("-inf"))), float(row.get("mean_ic", float("-inf")))))
        verdict = str(best_row.get("decision", "C_DO_NOT_PROMOTE"))
        best_model = str(best_row["model"])
        summary = logger.finalize(verdict=verdict, best_model=best_model)

        comparison_ids = [str(run) for run in compare_run_ids or [] if str(run).strip()]
        based_on = str((cfg.get("experiment") or {}).get("based_on", "") or "").strip()
        if based_on and based_on not in comparison_ids:
            try:
                comparison_ids.insert(0, str((load_experiment_config(based_on).get("experiment") or {}).get("run_id", based_on)))
            except Exception:
                comparison_ids.insert(0, based_on)
        comparison_path: Path | None = None
        if comparison_ids:
            comparison_table = compare_runs([*comparison_ids, resolved_run_id], runs_root=registry.output_root)
            comparison_path = stage_dir / "compare_runs.txt"
            comparison_path.write_text(comparison_table + "\n", encoding="utf-8")
            logger.log_artifact("compare_runs", comparison_path, stage="nb01")

        payload = {
            "experiment_id": run_id,
            "run_id": resolved_run_id,
            "source_export_dir": str(export_artifacts.export_dir),
            "filtered_export_dir": str(filtered_export_dir),
            "nb00_report": None if nb00_report_path is None else str(nb00_report_path),
            "preprocess_audit": preprocess_audit,
            "candidate_feature_count": len(filter_result.candidate_features),
            "selected_feature_count": len(selected_features),
            "selected_features": selected_features,
            "removed_features": filter_result.removed_features,
            "protected_dead_features": filter_result.protected_features,
            "forced_features": filter_result.forced_features,
            "dropped_redundant_features": filter_result.dropped_redundant_features,
            "reference_audit": reference_audit,
            "runtime_regime_assignment": runtime_regime_audit,
            "models": rows,
            "summary": summary,
            "comparison_path": None if comparison_path is None else str(comparison_path),
        }
        nb01_output_path = stage_dir / "nb01_output.json"
        write_json(nb01_output_path, payload)
        logger.log_artifact("nb01_output", nb01_output_path, stage="nb01")
        logger.log_day("nb01", payload)
        registry.mark_stage_completed(
            "nb01",
            metadata={
                "verdict": verdict,
                "best_model": best_model,
                "selected_feature_count": len(selected_features),
            },
        )
        return {
            "verdict": verdict,
            "best_model": best_model,
            "duration_minutes": float(summary.get("duration_minutes", 0.0) or 0.0),
            "models": model_results,
            "summary_path": str(logger.summary_path),
            "run_dir": str(registry.run_dir),
        }
    except Exception as exc:
        registry.mark_stage_failed("nb01", error=str(exc), metadata={"traceback": traceback.format_exc()})
        raise


def main() -> int:
    args = parse_args()
    result = run_experiment(
        args.run_id,
        export_dir=args.export_dir,
        nb00_report=args.nb00_report,
        output_dir=args.output_dir,
        profile=args.profile,
        max_splits=args.max_splits,
        compare_run_ids=list(args.compare_run_id),
    )
    print(json.dumps(json_ready(result), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
