#!/usr/bin/env python3
"""Run the post-Day-3B targeted Phase 1 tree-model sweep."""

from __future__ import annotations

import argparse
import importlib.util
import json
import logging
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np


os.environ.setdefault("LOKY_MAX_CPU_COUNT", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")
os.environ.setdefault("VECLIB_MAXIMUM_THREADS", "1")
os.environ.setdefault("TORCH_NUM_THREADS", "1")
os.environ.setdefault("TORCH_NUM_INTEROP_THREADS", "1")
os.environ.setdefault("NORTHSTAR_DISABLE_MPS", "1")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.research.research_controller import ResearchController
from src.research.training_pipeline import TrainingPipeline


LOGGER = logging.getLogger("northstar.day3c_tree_phase1_sweep")
BASE_RUNNER_PATH = PROJECT_ROOT / "scripts/research/run_day3_model_comparison.py"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "data/results/research/experiments/week_2026_03_22/day3c_tree_phase1_sweep"
DEFAULT_POLICY_PATH = PROJECT_ROOT / "config/research_policy.yaml"
DEFAULT_SOURCE_ROOT = PROJECT_ROOT / "data/results/research/experiments/week_2026_03_22/day3b_tighter_regularization"


def _load_base_runner():
    spec = importlib.util.spec_from_file_location("northstar_day3_base_runner_for_sweep", BASE_RUNNER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable_to_load_base_runner:{BASE_RUNNER_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


BASE = _load_base_runner()


@dataclass(frozen=True)
class SweepEntry:
    config_id: str
    model_type: str
    params: dict[str, Any]
    notes: str


XGBOOST_BASE = {
    "n_estimators": 200,
    "max_depth": 3,
    "min_child_weight": 30.0,
    "learning_rate": 0.03,
    "subsample": 0.60,
    "colsample_bytree": 0.50,
    "reg_alpha": 0.30,
    "reg_lambda": 3.0,
    "objective": "reg:squarederror",
    "n_jobs": 1,
}

CATBOOST_BASE = {
    "iterations": 300,
    "depth": 4,
    "learning_rate": 0.02,
    "l2_leaf_reg": 10.0,
    "min_data_in_leaf": 25,
    "subsample": 0.70,
    "loss_function": "RMSE",
    "boosting_type": "Ordered",
    "thread_count": 1,
    "allow_writing_files": False,
    "random_strength": 1.0,
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except Exception:
        return float(default)
    if not np.isfinite(out):
        return float(default)
    return float(out)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _parse_csv(raw: str) -> list[str]:
    return [str(x).strip().lower() for x in str(raw).split(",") if str(x).strip()]


def _parse_seeds(raw: str) -> list[int]:
    seeds = []
    for token in str(raw).split(","):
        token = str(token).strip()
        if not token:
            continue
        seeds.append(int(token))
    if not seeds:
        raise ValueError("no_seeds_requested")
    return seeds


def _resolve_latest_source_experiment() -> Path | None:
    if not DEFAULT_SOURCE_ROOT.exists():
        return None
    candidates = [p for p in DEFAULT_SOURCE_ROOT.glob("*_day3_model_comparison") if p.is_dir()]
    if not candidates:
        return None
    return sorted(candidates, key=lambda path: path.stat().st_mtime, reverse=True)[0]


def _load_stability_report(experiment_dir: Path | None) -> dict[str, Any] | None:
    if experiment_dir is None:
        return None
    report_path = experiment_dir / "feature_stability" / "feature_stability_report.json"
    if not report_path.exists():
        return None
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def _module_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def _guard_backends(models: list[str], *, allow_catboost_fallback: bool) -> None:
    if "xgboost" in models and not _module_available("xgboost"):
        raise RuntimeError("native_xgboost_not_installed")
    if "catboost" in models and not _module_available("catboost") and not allow_catboost_fallback:
        raise RuntimeError("native_catboost_not_installed")


def _phase1_entries(models: list[str]) -> list[SweepEntry]:
    entries: list[SweepEntry] = []
    if "xgboost" in models:
        xgb_phase1 = [
            ("xgb_p1_d2_mcw30_l5", {"max_depth": 2, "min_child_weight": 30.0, "reg_lambda": 5.0}),
            ("xgb_p1_d2_mcw50_l5", {"max_depth": 2, "min_child_weight": 50.0, "reg_lambda": 5.0}),
            ("xgb_p1_d3_mcw30_l5", {"max_depth": 3, "min_child_weight": 30.0, "reg_lambda": 5.0}),
            ("xgb_p1_d3_mcw50_l5", {"max_depth": 3, "min_child_weight": 50.0, "reg_lambda": 5.0}),
            ("xgb_p1_d3_mcw30_l8", {"max_depth": 3, "min_child_weight": 30.0, "reg_lambda": 8.0}),
        ]
        for config_id, override in xgb_phase1:
            params = {**XGBOOST_BASE, **override}
            entries.append(
                SweepEntry(
                    config_id=config_id,
                    model_type="xgboost",
                    params=params,
                    notes="Targeted Phase 1 XGBoost sweep around the Day 3B regularization baseline.",
                )
            )
    if "catboost" in models:
        cat_phase1 = [
            ("cat_p1_d3_l210_m20", {"depth": 3, "l2_leaf_reg": 10.0, "min_data_in_leaf": 20}),
            ("cat_p1_d3_l220_m20", {"depth": 3, "l2_leaf_reg": 20.0, "min_data_in_leaf": 20}),
            ("cat_p1_d4_l210_m40", {"depth": 4, "l2_leaf_reg": 10.0, "min_data_in_leaf": 40}),
            ("cat_p1_d4_l220_m40", {"depth": 4, "l2_leaf_reg": 20.0, "min_data_in_leaf": 40}),
            ("cat_p1_d5_l220_m40", {"depth": 5, "l2_leaf_reg": 20.0, "min_data_in_leaf": 40}),
        ]
        for config_id, override in cat_phase1:
            params = {**CATBOOST_BASE, **override}
            entries.append(
                SweepEntry(
                    config_id=config_id,
                    model_type="catboost",
                    params=params,
                    notes="Targeted Phase 1 CatBoost sweep on depth, L2 leaf regularization, and min data in leaf.",
                )
            )
    return entries


def _build_research_config(
    *,
    policy_path: Path,
    experiment_dir: Path,
    resource_profile: str,
    smoke: bool,
    models: list[str],
    max_windows: int | None,
) -> dict[str, Any]:
    return BASE._build_historical_research_config(
        policy_path,
        experiment_dir=experiment_dir,
        resource_profile=resource_profile,
        smoke=smoke,
        models=models,
        max_windows_override=max_windows,
    )


def _build_dataset_and_preflight(hr_config: dict[str, Any]) -> tuple[ResearchController, Any, dict[str, Any]]:
    controller = ResearchController(config=hr_config, project_root=PROJECT_ROOT)
    dataset = controller.dataset_manager.build_research_dataset()
    dataset, ic_payload = controller._run_ic_diagnostics_gate(dataset)
    dataset.frame = controller.pipeline._ensure_regime_labels(dataset.frame, dataset, "regime")
    preflight = {
        "created_at": _utc_now(),
        "dataset_rows": int(dataset.metadata.get("n_rows", len(dataset.frame))),
        "dataset_tickers": int(dataset.metadata.get("n_tickers", 0)),
        "features_after_ic_prune": int(dataset.metadata.get("n_features_after_ic_prune", len(dataset.feature_names))),
        "selected_features_preview": list((ic_payload or {}).get("top_features", [])[:10]) if isinstance(ic_payload, dict) else [],
        "max_windows": int(hr_config.get("training", {}).get("max_windows", 20)),
    }
    return controller, dataset, preflight


def _pipeline_from_config(hr_config: dict[str, Any]) -> TrainingPipeline:
    training = dict(hr_config.get("training", {}) or {})
    return TrainingPipeline(
        train_periods=int(training.get("train_periods", 260)),
        valid_periods=int(training.get("valid_periods", 5)),
        test_periods=int(training.get("test_periods", 60)),
        step_periods=int(training.get("step_periods", 20)),
        min_tickers_per_date=int(training.get("min_tickers_per_date", 50) or 50),
        max_windows=int(training.get("max_windows", 20)),
        start_window=int(training.get("start_window", 0) or 0),
        portfolio_cfg=dict(hr_config.get("portfolio_construction", {}) or {}),
        holdout_train_end_date=training.get("holdout_train_end_date"),
        holdout_test_start_date=training.get("holdout_test_start_date"),
        holdout_test_end_date=training.get("holdout_test_end_date"),
        holdout_valid_periods=training.get("holdout_valid_periods"),
        holdout_min_train_periods=int(training.get("holdout_min_train_periods", 120)),
        disable_model_specific_window_caps=True,
        emit_train_metrics=True,
    )


def _seed_summary(model_type: str, config_id: str, seed: int, runtime: float, result: dict[str, Any]) -> dict[str, Any]:
    agg = dict(result.get("aggregate_metrics", {}) or {})
    train_agg = dict(result.get("aggregate_train_metrics", {}) or {})
    overfit = dict(result.get("overfit_diagnostics", {}) or {})
    stability = dict(result.get("feature_stability", {}) or {})
    return {
        "model": model_type,
        "config_id": config_id,
        "seed": int(seed),
        "runtime_seconds": float(runtime),
        "status": str(result.get("status", "unknown")),
        "windows": int(len(result.get("windows", []) or [])),
        "test_ic": _safe_float(agg.get("ic_mean", 0.0)),
        "train_ic": _safe_float(train_agg.get("ic_mean", 0.0)),
        "test_ic_ir": _safe_float(agg.get("ic_mean", 0.0)) / max(_safe_float(agg.get("ic_std", 0.0), 0.0), 1e-12),
        "hit_rate": _safe_float(agg.get("avg_hit_rate", 0.0)),
        "turnover": _safe_float(agg.get("avg_turnover", 0.0)),
        "avg_sharpe": _safe_float(agg.get("avg_sharpe", 0.0)),
        "avg_max_drawdown": _safe_float(agg.get("avg_max_drawdown", 0.0)),
        "train_test_ratio": _safe_float(overfit.get("train_test_ic_mean_ratio", float("inf")), float("inf")),
        "feature_rank_corr": _safe_float(stability.get("mean_pairwise_rank_correlation", np.nan), np.nan),
        "feature_stability_band": str(stability.get("stability_band", "") or ""),
    }


def _mean_metric(rows: list[dict[str, Any]], key: str) -> float:
    vals = [_safe_float(row.get(key, np.nan), np.nan) for row in rows]
    vals = [v for v in vals if np.isfinite(v)]
    return float(np.mean(vals)) if vals else 0.0


def _aggregate_config_summary(entry: SweepEntry, seed_rows: list[dict[str, Any]]) -> dict[str, Any]:
    summary = {
        "config_id": entry.config_id,
        "model_type": entry.model_type,
        "params": entry.params,
        "notes": entry.notes,
        "seed_count": int(len(seed_rows)),
        "status": "ok" if seed_rows else "failed",
        "test_ic": _mean_metric(seed_rows, "test_ic"),
        "train_ic": _mean_metric(seed_rows, "train_ic"),
        "hit_rate": _mean_metric(seed_rows, "hit_rate"),
        "train_test_ratio": _mean_metric(seed_rows, "train_test_ratio"),
        "turnover": _mean_metric(seed_rows, "turnover"),
        "avg_sharpe": _mean_metric(seed_rows, "avg_sharpe"),
        "avg_max_drawdown": _mean_metric(seed_rows, "avg_max_drawdown"),
        "feature_rank_corr": _mean_metric(seed_rows, "feature_rank_corr"),
        "feature_stability_band": next((str(x.get("feature_stability_band")) for x in seed_rows if x.get("feature_stability_band")), ""),
        "runtime_seconds": float(sum(_safe_float(row.get("runtime_seconds", 0.0)) for row in seed_rows)),
        "seed_summaries": seed_rows,
    }
    summary["promotion_eligible"] = bool(
        _safe_float(summary.get("train_test_ratio", float("inf")), float("inf")) < 2.5
        and _safe_float(summary.get("test_ic", 0.0)) > 0.015
    )
    return summary


def _best_config(configs: list[dict[str, Any]]) -> dict[str, Any] | None:
    eligible = [row for row in configs if str(row.get("status", "")) == "ok"]
    if not eligible:
        return None
    promotion = [row for row in eligible if bool(row.get("promotion_eligible", False))]
    source = promotion if promotion else eligible
    ranked = sorted(
        source,
        key=lambda row: (
            _safe_float(row.get("train_test_ratio", float("inf")), float("inf")),
            -_safe_float(row.get("test_ic", -999.0), -999.0),
        ),
    )
    return ranked[0] if ranked else None


def _model_outcome(configs: list[dict[str, Any]]) -> dict[str, Any]:
    ok_configs = [row for row in configs if str(row.get("status", "")) == "ok"]
    if not ok_configs:
        return {
            "outcome": "no_results",
            "action": "No completed configs.",
            "best_config_id": None,
        }
    best = _best_config(ok_configs)
    best_ratio = min(_safe_float(row.get("train_test_ratio", float("inf")), float("inf")) for row in ok_configs)
    if any(bool(row.get("promotion_eligible", False)) for row in ok_configs):
        return {
            "outcome": "promotion_eligible",
            "action": "Promotion-eligible. Proceed to Day 4 regime analysis.",
            "best_config_id": best.get("config_id") if best else None,
        }
    if 3.0 <= best_ratio <= 4.0:
        return {
            "outcome": "gate_reconsideration",
            "action": "Best ratio landed in the 3-4x band. Document the best config and flag gate reconsideration.",
            "best_config_id": best.get("config_id") if best else None,
        }
    if all(_safe_float(row.get("train_test_ratio", 0.0)) > 5.0 for row in ok_configs):
        return {
            "outcome": "feature_audit",
            "action": "All configs stayed above 5x. Recommend a feature audit before further tuning.",
            "best_config_id": best.get("config_id") if best else None,
        }
    return {
        "outcome": "needs_follow_up",
        "action": "Keep the best config, but more tuning or a feature audit is still needed.",
        "best_config_id": best.get("config_id") if best else None,
    }


def _render_summary_md(summary: dict[str, Any]) -> str:
    lines: list[str] = [
        "# Day 3C Phase 1 Tree Sweep",
        "",
        f"- Created: {summary.get('created_at')}",
        f"- Experiment Dir: `{summary.get('experiment_dir')}`",
        f"- Source Experiment Dir: `{summary.get('source_experiment_dir')}`",
        "",
    ]
    for model_row in list(summary.get("models", []) or []):
        lines.extend(
            [
                f"## {str(model_row.get('model', '')).upper()}",
                "",
                f"- Stability Gate: `{model_row.get('stability_gate_status')}`",
                f"- Action: `{model_row.get('outcome', {}).get('action')}`",
                "",
                "| Config | Test IC | Train IC | Ratio | Hit Rate | Feature Corr | Status |",
                "|---|---:|---:|---:|---:|---:|---|",
            ]
        )
        for row in list(model_row.get("configs", []) or []):
            lines.append(
                "| {config} | {test_ic:.4f} | {train_ic:.4f} | {ratio:.4f} | {hit_rate:.4f} | {feature_corr:.4f} | {status} |".format(
                    config=row.get("config_id"),
                    test_ic=_safe_float(row.get("test_ic", 0.0)),
                    train_ic=_safe_float(row.get("train_ic", 0.0)),
                    ratio=_safe_float(row.get("train_test_ratio", 0.0)),
                    hit_rate=_safe_float(row.get("hit_rate", 0.0)),
                    feature_corr=_safe_float(row.get("feature_rank_corr", 0.0)),
                    status=row.get("status", "unknown"),
                )
            )
        lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Day 3C targeted Phase 1 tree sweep")
    parser.add_argument("--policy-path", default=str(DEFAULT_POLICY_PATH))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--source-experiment-dir", default=None, help="Day 3B experiment dir used for the stability gate")
    parser.add_argument("--models", default="xgboost,catboost")
    parser.add_argument("--seeds", default="42")
    parser.add_argument("--resource-profile", choices=["laptop_safe", "strict_plan"], default="laptop_safe")
    parser.add_argument("--max-windows", type=int, default=None)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--stable-threshold", type=float, default=0.70)
    parser.add_argument("--force", action="store_true", help="Run even if the stability gate says the features are unstable")
    parser.add_argument("--allow-catboost-fallback", action="store_true")
    parser.add_argument("--stop-on-promotion", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, str(args.log_level).upper(), logging.INFO), format="%(asctime)s | %(levelname)s | %(message)s")

    models = _parse_csv(args.models)
    if not models:
        raise ValueError("no_models_requested")
    seeds = _parse_seeds(args.seeds)
    if args.smoke:
        seeds = seeds[:1]
        if args.max_windows is None:
            args.max_windows = 1

    _guard_backends(models, allow_catboost_fallback=bool(args.allow_catboost_fallback))
    source_experiment_dir = (
        Path(str(args.source_experiment_dir)).expanduser().resolve()
        if args.source_experiment_dir
        else _resolve_latest_source_experiment()
    )
    stability_report = _load_stability_report(source_experiment_dir)
    stability_rows = {
        str(row.get("model", "")).strip().lower(): row
        for row in list((stability_report or {}).get("models", []) or [])
        if str(row.get("model", "")).strip()
    }

    experiment_dir = Path(str(args.output_dir)).expanduser().resolve() / f"{_timestamp()}_day3c_tree_phase1_sweep"
    experiment_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "created_at": _utc_now(),
        "experiment_dir": str(experiment_dir),
        "source_experiment_dir": str(source_experiment_dir) if source_experiment_dir else None,
        "models": models,
        "seeds": seeds,
        "resource_profile": str(args.resource_profile),
        "stable_threshold": float(args.stable_threshold),
        "force": bool(args.force),
    }
    _write_json(experiment_dir / "run_manifest.json", manifest)

    precomputed_model_rows: list[dict[str, Any]] = []
    runnable_models: list[str] = []
    for model_type in models:
        stability_row = stability_rows.get(model_type, {})
        mean_corr = _safe_float(stability_row.get("mean_pairwise_rank_correlation", np.nan), np.nan)
        gate_pass = bool(np.isfinite(mean_corr) and mean_corr >= float(args.stable_threshold))
        if stability_row and (not gate_pass) and not bool(args.force):
            precomputed_model_rows.append(
                {
                    "model": model_type,
                    "stability_gate_status": "skipped_unstable_features",
                    "stability_report_snapshot": stability_row,
                    "configs": [],
                    "best_config": None,
                    "outcome": {
                        "outcome": "skipped",
                        "action": "Skipped because the feature stability gate failed.",
                        "best_config_id": None,
                    },
                }
            )
            continue
        runnable_models.append(model_type)

    hr_config = None
    dataset = None
    preflight = {
        "created_at": _utc_now(),
        "status": "skipped_before_dataset_build" if not runnable_models else "ready",
        "reason": "all_requested_models_failed_stability_gate" if not runnable_models else "",
    }
    if runnable_models:
        hr_config = _build_research_config(
            policy_path=Path(str(args.policy_path)).expanduser().resolve(),
            experiment_dir=experiment_dir,
            resource_profile=str(args.resource_profile),
            smoke=bool(args.smoke),
            models=runnable_models,
            max_windows=args.max_windows,
        )
        _, dataset, preflight = _build_dataset_and_preflight(hr_config)
    _write_json(experiment_dir / "preflight_report.json", preflight)

    grouped_entries: dict[str, list[SweepEntry]] = {}
    for entry in _phase1_entries(models):
        grouped_entries.setdefault(entry.model_type, []).append(entry)

    model_summaries: list[dict[str, Any]] = list(precomputed_model_rows)
    for model_type in runnable_models:
        stability_row = stability_rows.get(model_type, {})
        mean_corr = _safe_float(stability_row.get("mean_pairwise_rank_correlation", np.nan), np.nan)
        gate_pass = bool(np.isfinite(mean_corr) and mean_corr >= float(args.stable_threshold))

        configs: list[dict[str, Any]] = []
        if hr_config is None or dataset is None:
            raise RuntimeError("dataset_not_built_for_runnable_models")
        pipeline = _pipeline_from_config(hr_config)
        for entry in grouped_entries.get(model_type, []):
            LOGGER.info("Running %s", entry.config_id)
            seed_rows: list[dict[str, Any]] = []
            for seed in seeds:
                params = dict(entry.params)
                params["random_state"] = int(seed)
                model = ResearchController._build_model(entry.model_type, params)
                started = time.perf_counter()
                result = pipeline.run(model=model, dataset=dataset, regime_policy={})
                runtime = time.perf_counter() - started
                seed_summary = _seed_summary(entry.model_type, entry.config_id, seed, runtime, result)
                seed_rows.append(seed_summary)
                seed_path = experiment_dir / "runs" / entry.model_type / entry.config_id / f"seed_{seed}.json"
                _write_json(
                    seed_path,
                    {
                        "seed_summary": seed_summary,
                        "params": params,
                        "full_result": result,
                    },
                )
                LOGGER.info(
                    "%s seed=%s test_ic=%.4f ratio=%.4f hit=%.4f feature_corr=%.4f",
                    entry.config_id,
                    seed,
                    _safe_float(seed_summary.get("test_ic", 0.0)),
                    _safe_float(seed_summary.get("train_test_ratio", 0.0)),
                    _safe_float(seed_summary.get("hit_rate", 0.0)),
                    _safe_float(seed_summary.get("feature_rank_corr", 0.0)),
                )

            config_summary = _aggregate_config_summary(entry, seed_rows)
            configs.append(config_summary)
            _write_json(experiment_dir / "config_summaries" / f"{entry.config_id}.json", config_summary)

            if bool(args.stop_on_promotion) and bool(config_summary.get("promotion_eligible", False)):
                LOGGER.info("Stopping %s early because %s became promotion-eligible", model_type, entry.config_id)
                break

        outcome = _model_outcome(configs)
        model_summaries.append(
            {
                "model": model_type,
                "stability_gate_status": "passed" if gate_pass or not stability_row else "forced",
                "stability_report_snapshot": stability_row or None,
                "configs": configs,
                "best_config": _best_config(configs),
                "outcome": outcome,
            }
        )

    summary = {
        "created_at": _utc_now(),
        "experiment_dir": str(experiment_dir),
        "source_experiment_dir": str(source_experiment_dir) if source_experiment_dir else None,
        "preflight_report": preflight,
        "models": model_summaries,
    }
    _write_json(experiment_dir / "summary.json", summary)
    _write_text(experiment_dir / "summary.md", _render_summary_md(summary))

    print(f"Experiment dir: {experiment_dir}")
    print(f"Summary JSON:   {experiment_dir / 'summary.json'}")
    print(f"Summary MD:     {experiment_dir / 'summary.md'}")
    for row in model_summaries:
        best = dict(row.get("best_config", {}) or {})
        outcome = dict(row.get("outcome", {}) or {})
        if best:
            print(
                f"{row.get('model')}: best={best.get('config_id')} "
                f"test_ic={_safe_float(best.get('test_ic', 0.0)):.4f} "
                f"ratio={_safe_float(best.get('train_test_ratio', 0.0)):.4f} "
                f"action={outcome.get('action')}"
            )
        else:
            print(f"{row.get('model')}: action={outcome.get('action')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
