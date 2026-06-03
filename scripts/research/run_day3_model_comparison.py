#!/usr/bin/env python3
"""Day 3 model comparison runner.

This script wires the weekly sprint Day 3 task into one experiment-dir-only
runner with:

- one shared walk-forward configuration across all candidate models
- fresh train-scope IC feature pruning to the selected 40 features
- detailed stdout progress at model / seed / window granularity
- preflight and smoke modes so laptop overnight runs are safer
- final comparison artifacts ready for Day 4 and the freeze review memo
"""

from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import logging
import os
import sys
import time
import warnings
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml
try:
    from scipy.stats import ConstantInputWarning
except Exception:  # pragma: no cover - scipy is expected, but keep startup robust
    ConstantInputWarning = None

# Keep the overnight run predictable on a small laptop host.
os.environ.setdefault("LOKY_MAX_CPU_COUNT", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")
os.environ.setdefault("VECLIB_MAXIMUM_THREADS", "1")
os.environ.setdefault("TORCH_NUM_THREADS", "1")
os.environ.setdefault("TORCH_NUM_INTEROP_THREADS", "1")
os.environ.setdefault("NORTHSTAR_LOW_RESOURCE_PROFILE", "0")
os.environ.setdefault("NORTHSTAR_DISABLE_MPS", "1")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.research.research_controller import ResearchController
from src.research.splits import eligible_trading_dates, rolling_time_splits
from src.research.training_pipeline import TrainingPipeline


LOGGER = logging.getLogger("northstar.day3_model_comparison")
DEFAULT_OUTPUT_ROOT = (
    PROJECT_ROOT / "data/results/research/experiments/week_2026_03_22/day3_model_comparison"
)
DEFAULT_POLICY_PATH = PROJECT_ROOT / "config/research_policy.yaml"
MODEL_ORDER = ["xgboost", "catboost", "lstm", "tcn", "transformer"]


@dataclass(frozen=True)
class ModelPlan:
    name: str
    params: dict[str, Any]
    seeds: list[int]
    notes: str


@dataclass(frozen=True)
class RunnerConfig:
    policy_path: str
    output_dir: str
    baseline_summary_path: str | None
    resume_experiment_path: str | None
    resource_profile: str
    preflight_only: bool
    smoke: bool
    models: list[str]
    max_seeds_per_model: int | None
    max_windows_override: int | None
    log_level: str


DAY3_MODEL_PLANS: dict[str, ModelPlan] = {
    "xgboost": ModelPlan(
        name="xgboost",
        params={
            "n_estimators": 300,
            "max_depth": 4,
            "min_child_weight": 20.0,
            "learning_rate": 0.03,
            "subsample": 0.70,
            "colsample_bytree": 0.60,
            "reg_alpha": 0.10,
            "reg_lambda": 2.0,
            # Repo-safe choice: the adapter uses XGBRegressor rather than a grouped rank objective.
            "objective": "reg:squarederror",
            "n_jobs": 1,
        },
        seeds=[42, 123, 456, 789, 1337],
        notes="Baseline tree model with shallow depth and strong regularization.",
    ),
    "catboost": ModelPlan(
        name="catboost",
        params={
            "iterations": 400,
            "depth": 5,
            "learning_rate": 0.02,
            "l2_leaf_reg": 5.0,
            "min_data_in_leaf": 15,
            "thread_count": 1,
        },
        seeds=[42, 123, 456, 789, 1337],
        notes="Ordered-boosting candidate approximated via repo-supported CatBoost adapter params.",
    ),
    "lstm": ModelPlan(
        name="lstm",
        params={
            # Repo adapters interpret lookback as sequence length, so keep the week-count scale directly.
            "lookback": 12,
            "hidden_dim": 64,
            "epochs": 18,
            "lr": 1e-3,
            "max_iter": 300,
        },
        seeds=[42, 123, 456],
        notes="Sequence baseline with laptop-safe epochs.",
    ),
    "tcn": ModelPlan(
        name="tcn",
        params={
            "lookback": 26,
            "channels": 32,
            "epochs": 20,
            "dilations": [1, 2, 4, 8],
            "dropout": 0.2,
            "lr": 1e-3,
            "patience": 10,
        },
        seeds=[42, 123, 456],
        notes="Dilated-convolution sequence model with laptop-safe channel width.",
    ),
    "transformer": ModelPlan(
        name="transformer",
        params={
            "lookback": 12,
            "epochs": 12,
            "d_model": 32,
            "nhead": 4,
            "num_layers": 2,
            "dim_feedforward": 64,
            "dropout": 0.3,
            "batch_size": 64,
            "patience": 10,
            "lr": 3e-4,
            "device": "cpu",
        },
        seeds=[42, 123, 456],
        notes="Small transformer consistent with the weekly plan's small-data guidance.",
    ),
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


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


def _json_default(value: Any) -> Any:
    if isinstance(value, (datetime, pd.Timestamp)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    return str(value)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=_json_default))


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _format_pct(value: Any) -> str:
    v = _safe_float(value, np.nan)
    return "n/a" if not np.isfinite(v) else f"{v:.4f}"


def _format_runtime(seconds: Any) -> str:
    sec = max(0.0, _safe_float(seconds, 0.0))
    if sec < 60.0:
        return f"{sec:.1f}s"
    if sec < 3600.0:
        return f"{sec / 60.0:.1f}m"
    return f"{sec / 3600.0:.2f}h"


def _module_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def _resolve_latest_day2_baseline() -> Path | None:
    candidates: list[Path] = []
    for root in [
        PROJECT_ROOT / "data/results/research/experiments/week_2026_03_22/day2b_full_centered",
        PROJECT_ROOT / "data/results/research/experiments/week_2026_03_22/day2_clean_baseline",
    ]:
        if not root.exists():
            continue
        for path in sorted(root.glob("*/summary.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            candidates.append(path)
    return candidates[0] if candidates else None


def _resolve_latest_incomplete_experiment(output_root: Path) -> Path | None:
    candidates = sorted(
        output_root.glob("*_day3_model_comparison"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for path in candidates:
        if not path.is_dir():
            continue
        if (path / "summary.json").exists():
            continue
        if (path / "preflight_report.json").exists() or (path / "run_manifest.json").exists():
            return path
    return None


def _load_baseline_summary(path: Path | None) -> dict[str, Any] | None:
    if path is None or (not path.exists()):
        return None
    try:
        payload = json.loads(path.read_text())
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    return {
        "path": str(path),
        "payload": payload,
        "metrics": payload.get("metrics", {}),
        "comparison_against_prior": payload.get("comparison_against_prior", {}),
        "verdict": payload.get("verdict"),
    }


def _load_json_dict(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text())
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _selected_model_plans(cfg: RunnerConfig) -> list[ModelPlan]:
    plans: list[ModelPlan] = []
    for model in cfg.models:
        name = str(model).strip().lower()
        if name not in DAY3_MODEL_PLANS:
            raise ValueError(f"unsupported_day3_model:{model}")
        plan = DAY3_MODEL_PLANS[name]
        if cfg.max_seeds_per_model is None:
            seeds = list(plan.seeds)
        else:
            seeds = list(plan.seeds[: max(1, int(cfg.max_seeds_per_model))])
        plans.append(ModelPlan(name=plan.name, params=dict(plan.params), seeds=seeds, notes=plan.notes))
    return plans


def _build_historical_research_config(
    policy_path: Path,
    *,
    experiment_dir: Path,
    resource_profile: str,
    smoke: bool,
    models: list[str],
    max_windows_override: int | None,
) -> dict[str, Any]:
    payload = yaml.safe_load(policy_path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"invalid_policy_yaml:{policy_path}")

    if "historical_research" not in payload or not isinstance(payload["historical_research"], dict):
        raise ValueError("policy_missing_historical_research")

    hr = copy.deepcopy(payload["historical_research"])
    hr["low_resource_mode"] = False
    hr["enable_deep_models"] = True
    hr["enable_hyperopt"] = False
    hr["enabled_models"] = list(models)

    training_cfg = hr.setdefault("training", {})
    training_cfg["train_periods"] = 52 * 5
    training_cfg["valid_periods"] = 1 * 5
    training_cfg["test_periods"] = 12 * 5
    training_cfg["step_periods"] = 4 * 5
    training_cfg["max_windows"] = int(max_windows_override if max_windows_override is not None else (1 if smoke else 20))
    training_cfg["holdout_train_end_date"] = None
    training_cfg["holdout_test_start_date"] = None
    training_cfg["holdout_test_end_date"] = None
    training_cfg["holdout_valid_periods"] = None
    training_cfg["holdout_min_train_periods"] = max(120, int(training_cfg["train_periods"] * 0.60))

    dataset_cfg = hr.setdefault("dataset", {})
    dataset_cfg["strict_real_data_only"] = True
    dataset_cfg["use_et500_universe_filter"] = True
    dataset_cfg["use_et500_features"] = bool(dataset_cfg.get("use_et500_features", False))
    dataset_cfg["target_horizon_days"] = 5
    dataset_cfg["target_col"] = "forward_return_5d"
    # Day 3 intentionally starts from the broader research panel and then
    # applies train-scope IC pruning down to 40 features. Keep the budget
    # metric for reporting, but do not block dataset construction before
    # pruning can run.
    dataset_cfg["feature_budget_enforce"] = False
    dataset_cfg["feature_correlation_warn_limit"] = 25
    dataset_cfg.setdefault("lookback_days", 2200)
    dataset_cfg.setdefault("max_rows", 200000)
    dataset_cfg.setdefault("max_tickers", 250)
    dataset_cfg["duckdb_threads"] = 1
    dataset_cfg["duckdb_memory_limit_mb"] = 768 if resource_profile == "laptop_safe" else int(dataset_cfg.get("duckdb_memory_limit_mb", 1024))

    if resource_profile == "laptop_safe":
        dataset_cfg["max_rows"] = min(int(dataset_cfg.get("max_rows", 200000)), 120000)
        dataset_cfg["max_tickers"] = min(int(dataset_cfg.get("max_tickers", 250)), 120)
        dataset_cfg["lookback_days"] = min(int(dataset_cfg.get("lookback_days", 2200)), 2200)
    else:
        dataset_cfg["max_rows"] = min(int(dataset_cfg.get("max_rows", 200000)), 200000)
        dataset_cfg["max_tickers"] = min(int(dataset_cfg.get("max_tickers", 250)), 250)

    if smoke:
        dataset_cfg["max_rows"] = min(int(dataset_cfg.get("max_rows", 120000)), 45000)
        dataset_cfg["max_tickers"] = min(int(dataset_cfg.get("max_tickers", 120)), 80)
        training_cfg["max_windows"] = 1

    ic_cfg = hr.setdefault("ic_diagnostics", {})
    ic_cfg["enabled"] = True
    ic_cfg["prune_features"] = True
    ic_cfg["scope_mode"] = "train_only"
    ic_cfg["max_keep_features"] = 40
    ic_cfg["min_keep_features"] = 15
    ic_cfg["output_dir"] = str(experiment_dir / "ic_diagnostics")

    shap_cfg = hr.setdefault("shap_validation", {})
    shap_cfg["enabled"] = False

    alpha_factory_cfg = hr.setdefault("alpha_factory", {})
    alpha_factory_cfg["enabled"] = False

    cert_cfg = hr.setdefault("certification", {})
    cert_cfg["enabled"] = False

    portfolio_cfg = hr.setdefault("portfolio_construction", {})
    portfolio_cfg["long_short_quantile"] = 0.20
    portfolio_cfg["min_assets_per_day"] = 8
    portfolio_cfg["max_weight_per_asset"] = 0.10
    portfolio_cfg["use_vol_scaling"] = True
    portfolio_cfg["rebalance_frequency_days"] = 5
    portfolio_cfg["sector_neutralize"] = False
    portfolio_cfg["max_sector_weight"] = 1.0
    portfolio_cfg["transaction_cost_bps_per_side"] = float(portfolio_cfg.get("transaction_cost_bps_per_side", 5.0) or 5.0)
    portfolio_cfg["prediction_transform"] = "zscore"
    portfolio_cfg["turnover_cap"] = 0.60
    portfolio_cfg["label_embargo_periods"] = 2 * 5

    hr["day3_run_metadata"] = {
        "resource_profile": resource_profile,
        "smoke": bool(smoke),
        "shared_walk_forward": {
            "train_weeks": 52,
            "test_weeks": 12,
            "step_size_weeks": 4,
            "purge_gap_weeks": 1,
            "embargo_weeks": 2,
            "n_windows": int(training_cfg["max_windows"]),
            "target_horizon_days": 5,
            "target_type": "cross_sectional_rank",
            "selected_feature_budget": 40,
        },
    }
    return hr


def _ic_ir(metrics: dict[str, Any]) -> float:
    mean_ic = _safe_float(metrics.get("ic_mean", 0.0), 0.0)
    std_ic = _safe_float(metrics.get("ic_std", 0.0), 0.0)
    if abs(std_ic) < 1e-12:
        return 0.0
    return float(mean_ic / std_ic)


def _mean_of(records: list[dict[str, Any]], key: str) -> float:
    vals = [_safe_float(r.get(key, np.nan), np.nan) for r in records]
    vals = [v for v in vals if np.isfinite(v)]
    return float(np.mean(vals)) if vals else 0.0


def _most_common_label(records: list[dict[str, Any]], key: str) -> str | None:
    counts: dict[str, int] = {}
    for row in records:
        label = str(row.get(key, "") or "").strip()
        if not label:
            continue
        counts[label] = int(counts.get(label, 0) + 1)
    if not counts:
        return None
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]


class Day3ModelComparisonRunner:
    def __init__(self, cfg: RunnerConfig):
        self.cfg = cfg
        self.output_root = Path(cfg.output_dir).expanduser().resolve()
        self.resume_mode = bool(cfg.resume_experiment_path)
        if self.resume_mode:
            self.experiment_dir = Path(str(cfg.resume_experiment_path)).expanduser().resolve()
            if not self.experiment_dir.exists():
                raise FileNotFoundError(f"resume_experiment_not_found:{self.experiment_dir}")
        else:
            self.experiment_dir = self.output_root / f"{_timestamp()}_day3_model_comparison"
        self.experiment_dir.mkdir(parents=True, exist_ok=True)
        self.heartbeat_path = self.experiment_dir / "heartbeat.json"
        self.partial_summary_path = self.experiment_dir / "comparison_live.md"
        self.progress_events_path = self.experiment_dir / "progress_events.ndjson"
        self.policy_path = Path(cfg.policy_path).expanduser().resolve()
        self.baseline_summary_path = (
            Path(cfg.baseline_summary_path).expanduser().resolve()
            if cfg.baseline_summary_path
            else _resolve_latest_day2_baseline()
        )
        self.baseline_summary = _load_baseline_summary(self.baseline_summary_path)
        self.plans = _selected_model_plans(cfg)
        self.hr_config = _build_historical_research_config(
            self.policy_path,
            experiment_dir=self.experiment_dir,
            resource_profile=cfg.resource_profile,
            smoke=cfg.smoke,
            models=[p.name for p in self.plans],
            max_windows_override=cfg.max_windows_override,
        )
        self.controller = ResearchController(config=self.hr_config, project_root=PROJECT_ROOT)
        self.dataset = None
        self.ic_payload: dict[str, Any] | None = None
        self.preflight_report: dict[str, Any] | None = None
        self.completed_models: list[dict[str, Any]] = []
        self.completed_model_names: set[str] = set()
        if self.resume_mode:
            self._restore_resume_state()
        self._write_manifest()
        if self.resume_mode:
            self._write_heartbeat(
                {
                    "phase": "resume_loaded",
                    "completed_models": sorted(self.completed_model_names),
                }
            )

    def _write_manifest(self) -> None:
        manifest = {
            "created_at": _utc_now().isoformat(),
            "experiment_dir": str(self.experiment_dir),
            "policy_path": str(self.policy_path),
            "baseline_summary_path": str(self.baseline_summary_path) if self.baseline_summary_path else None,
            "runner_config": {
                "resource_profile": self.cfg.resource_profile,
                "preflight_only": bool(self.cfg.preflight_only),
                "smoke": bool(self.cfg.smoke),
                "models": [p.name for p in self.plans],
                "max_seeds_per_model": self.cfg.max_seeds_per_model,
                "max_windows_override": self.cfg.max_windows_override,
            },
            "model_plans": [
                {
                    "name": p.name,
                    "params": p.params,
                    "seeds": p.seeds,
                    "notes": p.notes,
                }
                for p in self.plans
            ],
            "historical_research_config": self.hr_config,
        }
        if self.resume_mode and (self.experiment_dir / "run_manifest.json").exists():
            _write_json(
                self.experiment_dir / "resume_invocations" / f"{_timestamp()}.json",
                {
                    "resumed_at": _utc_now().isoformat(),
                    "experiment_dir": str(self.experiment_dir),
                    "runner_config": manifest["runner_config"],
                    "models": [p.name for p in self.plans],
                },
            )
            return
        _write_json(self.experiment_dir / "run_manifest.json", manifest)

    def _seed_result_path(self, model_name: str, seed: int) -> Path:
        return self.experiment_dir / "seed_results" / f"{model_name}_seed_{seed}.json"

    def _model_summary_path(self, model_name: str) -> Path:
        return self.experiment_dir / "model_summaries" / f"{model_name}.json"

    def _load_existing_seed_payload(self, model_name: str, seed: int) -> dict[str, Any] | None:
        payload = _load_json_dict(self._seed_result_path(model_name, int(seed)))
        if not payload:
            return None
        seed_summary = payload.get("seed_summary")
        if not isinstance(seed_summary, dict):
            return None
        if str(seed_summary.get("status", "")).lower() != "ok":
            return None
        return {
            "seed_summary": seed_summary,
            "result_path": str(self._seed_result_path(model_name, int(seed))),
        }

    def _load_existing_seed_payloads(self, plan: ModelPlan) -> dict[int, dict[str, Any]]:
        out: dict[int, dict[str, Any]] = {}
        for seed in plan.seeds:
            payload = self._load_existing_seed_payload(plan.name, int(seed))
            if payload is not None:
                out[int(seed)] = payload
        return out

    def _load_existing_model_summary(self, model_name: str) -> dict[str, Any] | None:
        payload = _load_json_dict(self._model_summary_path(model_name))
        if not payload:
            return None
        if str(payload.get("status", "")).lower() != "ok":
            return None
        return payload

    def _restore_resume_state(self) -> None:
        restored_map: dict[str, dict[str, Any]] = {}
        for path in sorted((self.experiment_dir / "model_summaries").glob("*.json")):
            payload = _load_json_dict(path)
            if not payload:
                continue
            model_name = str(payload.get("model", "")).strip()
            if not model_name:
                continue
            if str(payload.get("status", "")).lower() != "ok":
                continue
            restored_map[model_name] = payload
        for plan in self.plans:
            existing_seed_payloads = self._load_existing_seed_payloads(plan)
            if len(existing_seed_payloads) != len(plan.seeds):
                continue
            summary = restored_map.get(plan.name) or self._load_existing_model_summary(plan.name)
            if summary is None:
                summary = self._aggregate_model_summary(
                    plan,
                    [existing_seed_payloads[int(seed)] for seed in plan.seeds],
                )
            restored_map[plan.name] = summary
        restored = [
            restored_map[name]
            for name in MODEL_ORDER
            if name in restored_map
        ]
        restored.extend(
            restored_map[name]
            for name in sorted(restored_map)
            if name not in MODEL_ORDER
        )
        self.completed_models = restored
        self.completed_model_names = {str(row.get("model")) for row in restored if row.get("model")}
        if restored:
            self._write_partial_summary()

    def _append_progress_event(self, payload: dict[str, Any]) -> None:
        line = json.dumps(payload, default=_json_default)
        self.progress_events_path.parent.mkdir(parents=True, exist_ok=True)
        with self.progress_events_path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")

    def _write_heartbeat(self, payload: dict[str, Any]) -> None:
        heartbeat = {
            "updated_at": _utc_now().isoformat(),
            "experiment_dir": str(self.experiment_dir),
            **payload,
        }
        _write_json(self.heartbeat_path, heartbeat)
        self._append_progress_event(heartbeat)

    def _write_partial_summary(self) -> None:
        lines: list[str] = [
            "# Day 3 Model Comparison (Live)",
            "",
            f"- Updated: {_utc_now().isoformat()}",
            f"- Experiment Dir: `{self.experiment_dir}`",
            f"- Models Completed: `{len(self.completed_models)}/{len(self.plans)}`",
            "",
            "| Model | Mean IC | IC IR | Hit Rate | Train/Test ratio | Feature Corr | Turnover | Run time | Status |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---|",
        ]
        for row in self.completed_models:
            lines.append(
                "| {model} | {ic} | {ir} | {hit} | {ratio} | {feature_corr} | {turn} | {runtime} | {status} |".format(
                    model=row.get("model", "unknown"),
                    ic=_format_pct(row.get("mean_ic")),
                    ir=_format_pct(row.get("ic_ir")),
                    hit=_format_pct(row.get("hit_rate")),
                    ratio=_format_pct(row.get("train_test_ratio")),
                    feature_corr=_format_pct(row.get("feature_rank_corr")),
                    turn=_format_pct(row.get("turnover")),
                    runtime=_format_runtime(row.get("runtime_seconds")),
                    status=row.get("status", "unknown"),
                )
            )
        _write_text(self.partial_summary_path, "\n".join(lines) + "\n")

    def build_dataset_and_preflight(self) -> dict[str, Any]:
        if self.preflight_report is not None:
            return self.preflight_report

        LOGGER.info("Building research dataset for Day 3 comparison")
        self._write_heartbeat({"phase": "building_dataset"})
        dataset = self.controller.dataset_manager.build_research_dataset()
        LOGGER.info(
            "Dataset built rows=%s tickers=%s raw_features=%s start=%s end=%s",
            dataset.metadata.get("n_rows"),
            dataset.metadata.get("n_tickers"),
            dataset.metadata.get("n_features"),
            dataset.metadata.get("start_date"),
            dataset.metadata.get("end_date"),
        )
        self._write_heartbeat(
            {
                "phase": "dataset_built",
                "dataset_rows": int(dataset.metadata.get("n_rows", len(dataset.frame))),
                "dataset_tickers": int(dataset.metadata.get("n_tickers", 0)),
                "dataset_features": int(dataset.metadata.get("n_features", len(dataset.feature_names))),
            }
        )
        LOGGER.info("Running train-scope IC diagnostics and pruning to the selected feature budget")
        self._write_heartbeat({"phase": "running_ic_pruning"})
        dataset, ic_payload = self.controller._run_ic_diagnostics_gate(dataset)
        dataset.frame = self.controller.pipeline._ensure_regime_labels(dataset.frame, dataset, "regime")
        self.dataset = dataset
        self.ic_payload = ic_payload

        training_cfg = dict(self.hr_config.get("training", {}))
        eligible_dates = eligible_trading_dates(
            dataset.frame,
            date_col="date",
            ticker_col="ticker",
            min_tickers_per_date=int(training_cfg.get("min_tickers_per_date", 50) or 50),
        )
        all_splits = list(
            rolling_time_splits(
                dataset.frame,
                date_col="date",
                ticker_col="ticker",
                train_periods=int(training_cfg.get("train_periods", 260)),
                valid_periods=int(training_cfg.get("valid_periods", 5)),
                test_periods=int(training_cfg.get("test_periods", 60)),
                step_periods=int(training_cfg.get("step_periods", 20)),
                min_tickers_per_date=int(training_cfg.get("min_tickers_per_date", 50) or 50),
            )
        )
        requested_windows = int(training_cfg.get("max_windows", 20))

        libs = {
            "xgboost": _module_available("xgboost"),
            "catboost": _module_available("catboost"),
            "torch": _module_available("torch"),
        }
        dataset_meta = dict(dataset.metadata or {})
        selected_features = []
        if isinstance(ic_payload, dict):
            selected_features = [str(x) for x in (ic_payload.get("top_features", []) or [])]

        ready = bool(len(all_splits) >= requested_windows and int(dataset_meta.get("n_features_after_ic_prune", 0) or 0) > 0)
        report = {
            "ready_for_day3": ready,
            "created_at": _utc_now().isoformat(),
            "experiment_dir": str(self.experiment_dir),
            "dataset": {
                "n_rows": int(dataset_meta.get("n_rows", len(dataset.frame))),
                "n_tickers": int(dataset_meta.get("n_tickers", len(pd.Series(dataset.frame.get("ticker", pd.Series(dtype=str))).drop_duplicates()))),
                "n_features_before_ic_prune": int(dataset_meta.get("n_features_before_ic_prune", len(dataset.feature_names))),
                "n_features_after_ic_prune": int(dataset_meta.get("n_features_after_ic_prune", len(dataset.feature_names))),
                "start_date": dataset_meta.get("start_date"),
                "end_date": dataset_meta.get("end_date"),
                "use_et500_universe_filter": bool(dataset_meta.get("use_et500_universe_filter", False)),
                "target_mode": dataset_meta.get("target_mode"),
                "eligible_dates": int(len(eligible_dates)),
            },
            "walk_forward": {
                "requested_windows": requested_windows,
                "available_windows": int(len(all_splits)),
                "train_periods": int(training_cfg.get("train_periods", 260)),
                "valid_periods": int(training_cfg.get("valid_periods", 5)),
                "test_periods": int(training_cfg.get("test_periods", 60)),
                "step_periods": int(training_cfg.get("step_periods", 20)),
                "first_window": {
                    "train_start": all_splits[0]["train_start"],
                    "train_end": all_splits[0]["train_end"],
                    "test_start": all_splits[0]["test_start"],
                    "test_end": all_splits[0]["test_end"],
                } if all_splits else None,
                "last_window": {
                    "train_start": all_splits[min(len(all_splits), requested_windows) - 1]["train_start"],
                    "train_end": all_splits[min(len(all_splits), requested_windows) - 1]["train_end"],
                    "test_start": all_splits[min(len(all_splits), requested_windows) - 1]["test_start"],
                    "test_end": all_splits[min(len(all_splits), requested_windows) - 1]["test_end"],
                } if all_splits else None,
            },
            "libraries": libs,
            "selected_features_preview": selected_features[:10],
            "baseline_summary": self.baseline_summary,
            "models": [
                {
                    "name": plan.name,
                    "seed_count": len(plan.seeds),
                    "params": plan.params,
                    "notes": plan.notes,
                }
                for plan in self.plans
            ],
            "warnings": [],
        }
        if not libs["catboost"]:
            report["warnings"].append("catboost_not_installed_adapter_will_fallback")
        if not libs["xgboost"]:
            report["warnings"].append("xgboost_not_installed_adapter_will_fallback")
        if not libs["torch"]:
            report["warnings"].append("torch_not_installed_deep_models_will_use_fallbacks")

        self.preflight_report = report
        _write_json(self.experiment_dir / "preflight_report.json", report)
        self._write_heartbeat(
            {
                "phase": "preflight_complete",
                "ready_for_day3": bool(ready),
                "available_windows": int(len(all_splits)),
                "requested_windows": requested_windows,
            }
        )
        return report

    def _progress_callback(
        self,
        *,
        model_name: str,
        seed: int,
        seed_index: int,
        seed_total: int,
        model_index: int,
        model_total: int,
        seed_started_at: float,
    ):
        def callback(event: str, index: int, total: int, model: str, metrics: dict[str, Any] | None = None) -> None:
            elapsed = time.perf_counter() - seed_started_at
            if event == "window_start":
                LOGGER.info(
                    "Model %d/%d %s | seed %d/%d (%d) | window %d/%d START",
                    model_index,
                    model_total,
                    model_name,
                    seed_index,
                    seed_total,
                    seed,
                    index,
                    total,
                )
                self._write_heartbeat(
                    {
                        "phase": "window_start",
                        "current_model": model_name,
                        "current_seed": seed,
                        "current_window": int(index),
                        "window_total": int(total),
                        "elapsed_seconds_for_seed": elapsed,
                    }
                )
                return

            metric_map = dict(metrics or {})
            LOGGER.info(
                "Model %d/%d %s | seed %d/%d (%d) | window %d/%d DONE | ic=%.4f sharpe=%.4f hit=%.4f turnover=%.4f dd=%.4f",
                model_index,
                model_total,
                model_name,
                seed_index,
                seed_total,
                seed,
                index,
                total,
                _safe_float(metric_map.get("ic", 0.0)),
                _safe_float(metric_map.get("sharpe", 0.0)),
                _safe_float(metric_map.get("hit_rate", 0.0)),
                _safe_float(metric_map.get("avg_turnover", 0.0)),
                _safe_float(metric_map.get("max_drawdown", 0.0)),
            )
            self._write_heartbeat(
                {
                    "phase": "window_done",
                    "current_model": model_name,
                    "current_seed": seed,
                    "current_window": int(index),
                    "window_total": int(total),
                    "elapsed_seconds_for_seed": elapsed,
                    "window_metrics": {
                        "ic": _safe_float(metric_map.get("ic", 0.0)),
                        "sharpe": _safe_float(metric_map.get("sharpe", 0.0)),
                        "hit_rate": _safe_float(metric_map.get("hit_rate", 0.0)),
                        "avg_turnover": _safe_float(metric_map.get("avg_turnover", 0.0)),
                        "max_drawdown": _safe_float(metric_map.get("max_drawdown", 0.0)),
                    },
                }
            )

        return callback

    def _run_one_seed(
        self,
        *,
        plan: ModelPlan,
        model_index: int,
        model_total: int,
        seed: int,
        seed_index: int,
        seed_total: int,
    ) -> dict[str, Any]:
        if self.dataset is None:
            raise RuntimeError("dataset_not_built")

        params = dict(plan.params)
        params["random_state"] = int(seed)
        params.setdefault("n_jobs", 1)
        params.setdefault("thread_count", 1)
        window_artifact_dir = None
        if str(plan.name).strip().lower() == "transformer":
            window_artifact_dir = self.experiment_dir / "window_artifacts" / "transformer" / f"seed_{int(seed)}"
        pipeline = TrainingPipeline(
            train_periods=int(self.hr_config.get("training", {}).get("train_periods", 260)),
            valid_periods=int(self.hr_config.get("training", {}).get("valid_periods", 5)),
            test_periods=int(self.hr_config.get("training", {}).get("test_periods", 60)),
            step_periods=int(self.hr_config.get("training", {}).get("step_periods", 20)),
            min_tickers_per_date=int(self.hr_config.get("training", {}).get("min_tickers_per_date", 50) or 50),
            max_windows=int(self.hr_config.get("training", {}).get("max_windows", 20)),
            start_window=int(self.hr_config.get("training", {}).get("start_window", 0) or 0),
            portfolio_cfg=dict(self.hr_config.get("portfolio_construction", {})),
            holdout_train_end_date=self.hr_config.get("training", {}).get("holdout_train_end_date"),
            holdout_test_start_date=self.hr_config.get("training", {}).get("holdout_test_start_date"),
            holdout_test_end_date=self.hr_config.get("training", {}).get("holdout_test_end_date"),
            holdout_valid_periods=self.hr_config.get("training", {}).get("holdout_valid_periods"),
            holdout_min_train_periods=int(self.hr_config.get("training", {}).get("holdout_min_train_periods", 120)),
            disable_model_specific_window_caps=True,
            emit_train_metrics=True,
            window_artifact_dir=str(window_artifact_dir) if window_artifact_dir is not None else None,
        )
        model = ResearchController._build_model(plan.name, params)
        started = time.perf_counter()
        callback = self._progress_callback(
            model_name=plan.name,
            seed=seed,
            seed_index=seed_index,
            seed_total=seed_total,
            model_index=model_index,
            model_total=model_total,
            seed_started_at=started,
        )
        result = pipeline.run(model=model, dataset=self.dataset, progress_callback=callback)
        runtime = time.perf_counter() - started
        agg = dict(result.get("aggregate_metrics", {}) or {})
        train_agg = dict(result.get("aggregate_train_metrics", {}) or {})
        overfit = dict(result.get("overfit_diagnostics", {}) or {})
        feature_stability = dict(result.get("feature_stability", {}) or {})
        seed_summary = {
            "model": plan.name,
            "seed": int(seed),
            "runtime_seconds": float(runtime),
            "status": str(result.get("status", "unknown")),
            "windows": int(len(result.get("windows", []) or [])),
            "mean_ic": _safe_float(agg.get("ic_mean", 0.0)),
            "ic_ir": _ic_ir(agg),
            "hit_rate": _safe_float(agg.get("avg_hit_rate", 0.0)),
            "turnover": _safe_float(agg.get("avg_turnover", 0.0)),
            "avg_sharpe": _safe_float(agg.get("avg_sharpe", 0.0)),
            "avg_max_drawdown": _safe_float(agg.get("avg_max_drawdown", 0.0)),
            "train_mean_ic": _safe_float(train_agg.get("ic_mean", 0.0)),
            "train_ic_ir": _ic_ir(train_agg),
            "train_test_ratio": _safe_float(overfit.get("train_test_ic_mean_ratio", float("inf")), float("inf")),
            "train_test_ir_ratio": _safe_float(overfit.get("train_test_ic_ir_ratio", float("inf")), float("inf")),
            "feature_rank_corr": _safe_float(feature_stability.get("mean_pairwise_rank_correlation", np.nan), np.nan),
            "feature_top_jaccard": _safe_float(feature_stability.get("mean_top_feature_jaccard", np.nan), np.nan),
            "feature_stability_band": str(feature_stability.get("stability_band", "") or ""),
        }
        result_path = self.experiment_dir / "seed_results" / f"{plan.name}_seed_{seed}.json"
        _write_json(
            result_path,
            {
                "seed_summary": seed_summary,
                "params": params,
                "window_artifact_dir": str(window_artifact_dir) if window_artifact_dir is not None else None,
                "full_result": result,
            },
        )
        LOGGER.info(
            "Completed %s seed %d/%d (%d) | windows=%d mean_ic=%.4f ic_ir=%.4f hit=%.4f train/test=%.4f runtime=%s",
            plan.name,
            seed_index,
            seed_total,
            seed,
            int(seed_summary["windows"]),
            seed_summary["mean_ic"],
            seed_summary["ic_ir"],
            seed_summary["hit_rate"],
            seed_summary["train_test_ratio"],
            _format_runtime(runtime),
        )
        self._write_heartbeat(
            {
                "phase": "seed_complete",
                "current_model": plan.name,
                "current_seed": int(seed),
                "seed_summary": seed_summary,
            }
        )
        return {
            "seed_summary": seed_summary,
            "result_path": str(result_path),
        }

    def _aggregate_model_summary(self, plan: ModelPlan, seed_payloads: list[dict[str, Any]]) -> dict[str, Any]:
        seeds = [dict(p.get("seed_summary", {}) or {}) for p in seed_payloads]
        model_summary = {
            "model": plan.name,
            "status": "ok" if seeds else "failed",
            "seed_count": int(len(seeds)),
            "mean_ic": _mean_of(seeds, "mean_ic"),
            "ic_ir": _mean_of(seeds, "ic_ir"),
            "hit_rate": _mean_of(seeds, "hit_rate"),
            "train_test_ratio": _mean_of(seeds, "train_test_ratio"),
            "train_test_ir_ratio": _mean_of(seeds, "train_test_ir_ratio"),
            "feature_rank_corr": _mean_of(seeds, "feature_rank_corr"),
            "feature_top_jaccard": _mean_of(seeds, "feature_top_jaccard"),
            "feature_stability_band": _most_common_label(seeds, "feature_stability_band"),
            "turnover": _mean_of(seeds, "turnover"),
            "avg_sharpe": _mean_of(seeds, "avg_sharpe"),
            "avg_max_drawdown": _mean_of(seeds, "avg_max_drawdown"),
            "runtime_seconds": float(sum(_safe_float(s.get("runtime_seconds", 0.0)) for s in seeds)),
            "mean_seed_runtime_seconds": _mean_of(seeds, "runtime_seconds"),
            "seed_summaries": seeds,
            "notes": plan.notes,
        }
        _write_json(self.experiment_dir / "model_summaries" / f"{plan.name}.json", model_summary)
        return model_summary

    def _pick_best_model(self, completed_models: list[dict[str, Any]]) -> dict[str, Any]:
        eligible = [
            row
            for row in completed_models
            if str(row.get("status", "")) == "ok" and _safe_float(row.get("train_test_ratio", float("inf")), float("inf")) < 2.5
        ]
        if not eligible:
            return {
                "selected_model": None,
                "reason": "no_model_passed_train_test_ratio_gate",
                "eligible_models": [],
            }

        ranked = sorted(eligible, key=lambda row: _safe_float(row.get("ic_ir", -999.0), -999.0), reverse=True)
        best = ranked[0]
        tied = [
            row for row in ranked
            if abs(_safe_float(row.get("ic_ir", 0.0)) - _safe_float(best.get("ic_ir", 0.0))) <= 0.005
        ]
        if len(tied) > 1:
            tied = sorted(tied, key=lambda row: _safe_float(row.get("turnover", float("inf")), float("inf")))
            best = tied[0]
            reason = "ic_ir_within_0.005_tiebroken_by_lower_turnover"
        else:
            reason = "highest_ic_ir_under_train_test_ratio_gate"
        return {
            "selected_model": str(best.get("model")),
            "reason": reason,
            "eligible_models": [str(x.get("model")) for x in eligible],
        }

    def _render_summary_md(self, completed_models: list[dict[str, Any]], decision: dict[str, Any]) -> str:
        lines: list[str] = [
            "# Day 3 Model Comparison",
            "",
            f"- Created: {_utc_now().isoformat()}",
            f"- Experiment Dir: `{self.experiment_dir}`",
            f"- Resource Profile: `{self.cfg.resource_profile}`",
            f"- Smoke Mode: `{self.cfg.smoke}`",
            "",
            "## Comparison Table",
            "",
            "| Model | Mean IC | IC IR | Hit Rate | Train/Test ratio | Feature Corr | Turnover | Run time |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
        for row in completed_models:
            lines.append(
                "| {model} | {ic} | {ir} | {hit} | {ratio} | {feature_corr} | {turn} | {runtime} |".format(
                    model=row.get("model", "unknown"),
                    ic=_format_pct(row.get("mean_ic")),
                    ir=_format_pct(row.get("ic_ir")),
                    hit=_format_pct(row.get("hit_rate")),
                    ratio=_format_pct(row.get("train_test_ratio")),
                    feature_corr=_format_pct(row.get("feature_rank_corr")),
                    turn=_format_pct(row.get("turnover")),
                    runtime=_format_runtime(row.get("runtime_seconds")),
                )
            )

        lines.extend(
            [
                "",
                "## Decision",
                "",
                f"- Selected model: `{decision.get('selected_model')}`",
                f"- Reason: `{decision.get('reason')}`",
            ]
        )

        if self.baseline_summary is not None:
            metrics = dict(self.baseline_summary.get("metrics", {}) or {})
            lines.extend(
                [
                    "",
                    "## Certified Baseline Reference",
                    "",
                    f"- Source: `{self.baseline_summary.get('path')}`",
                    f"- Mean exposure: `{_format_pct(metrics.get('mean_exposure'))}`",
                    f"- Mean Sharpe: `{_format_pct(metrics.get('mean_sharpe'))}`",
                    f"- Mean return: `{_format_pct(metrics.get('mean_return'))}`",
                    f"- Mean drawdown: `{_format_pct(metrics.get('mean_drawdown'))}`",
                ]
            )
        return "\n".join(lines) + "\n"

    def run(self) -> dict[str, Any]:
        preflight = self.build_dataset_and_preflight()
        LOGGER.info(
            "Preflight ready=%s rows=%s tickers=%s features=%s windows=%s/%s",
            preflight.get("ready_for_day3"),
            preflight.get("dataset", {}).get("n_rows"),
            preflight.get("dataset", {}).get("n_tickers"),
            preflight.get("dataset", {}).get("n_features_after_ic_prune"),
            preflight.get("walk_forward", {}).get("available_windows"),
            preflight.get("walk_forward", {}).get("requested_windows"),
        )
        if not bool(preflight.get("ready_for_day3", False)):
            raise RuntimeError("day3_preflight_failed")
        if self.cfg.preflight_only:
            return {
                "status": "preflight_only",
                "preflight_report": preflight,
                "experiment_dir": str(self.experiment_dir),
            }

        self._write_heartbeat(
            {
                "phase": "model_comparison_start",
                "models": [p.name for p in self.plans],
                "resume_mode": bool(self.resume_mode),
                "completed_models": sorted(self.completed_model_names),
            }
        )
        for model_index, plan in enumerate(self.plans, start=1):
            existing_seed_payloads = self._load_existing_seed_payloads(plan)
            completed_seed_ids = [int(seed) for seed in plan.seeds if int(seed) in existing_seed_payloads]
            remaining_seed_ids = [int(seed) for seed in plan.seeds if int(seed) not in existing_seed_payloads]

            if plan.name in self.completed_model_names and not remaining_seed_ids:
                LOGGER.info(
                    "Skipping model %d/%d: %s | already complete in %s",
                    model_index,
                    len(self.plans),
                    plan.name,
                    self.experiment_dir,
                )
                continue

            seed_payloads: list[dict[str, Any]] = [existing_seed_payloads[int(seed)] for seed in plan.seeds if int(seed) in existing_seed_payloads]
            if completed_seed_ids:
                LOGGER.info(
                    "Resuming model %d/%d: %s | completed_seeds=%s remaining_seeds=%s",
                    model_index,
                    len(self.plans),
                    plan.name,
                    completed_seed_ids,
                    remaining_seed_ids,
                )
            else:
                LOGGER.info(
                    "Starting model %d/%d: %s | seeds=%s | notes=%s",
                    model_index,
                    len(self.plans),
                    plan.name,
                    plan.seeds,
                    plan.notes,
                )

            if not remaining_seed_ids and seed_payloads:
                summary = self._load_existing_model_summary(plan.name)
                if summary is None:
                    summary = self._aggregate_model_summary(plan, seed_payloads)
                if plan.name not in self.completed_model_names:
                    self.completed_models.append(summary)
                    self.completed_model_names.add(plan.name)
                    self._write_partial_summary()
                continue

            for seed_index, seed in enumerate(plan.seeds, start=1):
                if int(seed) in existing_seed_payloads:
                    LOGGER.info(
                        "Skipping %s seed %d/%d (%d) | already complete in %s",
                        plan.name,
                        seed_index,
                        len(plan.seeds),
                        seed,
                        self._seed_result_path(plan.name, int(seed)),
                    )
                    continue
                seed_payloads.append(
                    self._run_one_seed(
                        plan=plan,
                        model_index=model_index,
                        model_total=len(self.plans),
                        seed=seed,
                        seed_index=seed_index,
                        seed_total=len(plan.seeds),
                    )
                )
            summary = self._aggregate_model_summary(plan, seed_payloads)
            self.completed_models = [row for row in self.completed_models if str(row.get("model")) != plan.name]
            self.completed_models.append(summary)
            self.completed_model_names.add(plan.name)
            self._write_partial_summary()

        decision = self._pick_best_model(self.completed_models)
        summary = {
            "status": "completed",
            "created_at": _utc_now().isoformat(),
            "experiment_dir": str(self.experiment_dir),
            "resource_profile": self.cfg.resource_profile,
            "smoke": bool(self.cfg.smoke),
            "preflight_report": self.preflight_report,
            "baseline_summary": self.baseline_summary,
            "model_comparison": self.completed_models,
            "decision": decision,
        }
        _write_json(self.experiment_dir / "summary.json", summary)
        _write_text(self.experiment_dir / "summary.md", self._render_summary_md(self.completed_models, decision))
        self._write_heartbeat(
            {
                "phase": "completed",
                "decision": decision,
                "completed_models": [row.get("model") for row in self.completed_models],
            }
        )
        return summary


def _parse_args() -> RunnerConfig:
    parser = argparse.ArgumentParser(description="Run Day 3 weekly research model comparison")
    parser.add_argument("--policy-path", default=str(DEFAULT_POLICY_PATH))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--baseline-summary", default=None)
    parser.add_argument("--resume-experiment", default=None, help="Reuse an existing Day 3 experiment directory and skip completed seeds/models.")
    parser.add_argument("--resume-latest-incomplete", action="store_true", help="Resume the most recent incomplete Day 3 experiment under the output dir.")
    parser.add_argument("--resource-profile", choices=["laptop_safe", "strict_plan"], default="laptop_safe")
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--smoke", action="store_true", help="Run a 1-window, 1-seed smoke pass across all five models.")
    parser.add_argument(
        "--models",
        default="xgboost,catboost,lstm,tcn,transformer",
        help="Comma-separated Day 3 model list.",
    )
    parser.add_argument("--max-seeds-per-model", type=int, default=None)
    parser.add_argument("--max-windows", type=int, default=None)
    parser.add_argument("--log-level", default="INFO")
    ns = parser.parse_args()
    output_root = Path(str(ns.output_dir)).expanduser().resolve()
    resume_path = str(ns.resume_experiment).strip() if ns.resume_experiment else None
    if ns.resume_latest_incomplete and not resume_path:
        latest = _resolve_latest_incomplete_experiment(output_root)
        if latest is None:
            raise ValueError(f"no_incomplete_day3_experiment_under:{output_root}")
        resume_path = str(latest)
    models = [x.strip().lower() for x in str(ns.models).split(",") if x.strip()]
    if ns.smoke:
        if ns.max_seeds_per_model is None:
            ns.max_seeds_per_model = 1
        if ns.max_windows is None:
            ns.max_windows = 1
    return RunnerConfig(
        policy_path=str(ns.policy_path),
        output_dir=str(ns.output_dir),
        baseline_summary_path=str(ns.baseline_summary) if ns.baseline_summary else None,
        resume_experiment_path=resume_path,
        resource_profile=str(ns.resource_profile),
        preflight_only=bool(ns.preflight_only),
        smoke=bool(ns.smoke),
        models=models,
        max_seeds_per_model=ns.max_seeds_per_model,
        max_windows_override=ns.max_windows,
        log_level=str(ns.log_level),
    )


def main() -> int:
    cfg = _parse_args()
    if ConstantInputWarning is not None:
        warnings.filterwarnings("ignore", category=ConstantInputWarning)
    logging.basicConfig(
        level=getattr(logging, cfg.log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(message)s",
    )
    # Keep the overnight log readable: dataset build progress is useful, but
    # per-date valuation cache fallbacks create thousands of low-signal lines.
    logging.getLogger("src.valuation.valuation_feature_block").setLevel(logging.WARNING)
    runner = Day3ModelComparisonRunner(cfg)
    if runner.resume_mode:
        LOGGER.info("Resuming experiment dir: %s", runner.experiment_dir)
    result = runner.run()
    LOGGER.info("Experiment dir: %s", runner.experiment_dir)
    if result.get("status") == "completed":
        LOGGER.info("Summary JSON: %s", runner.experiment_dir / "summary.json")
        LOGGER.info("Summary MD:   %s", runner.experiment_dir / "summary.md")
        LOGGER.info("Selected model: %s", result.get("decision", {}).get("selected_model"))
    else:
        LOGGER.info("Preflight report: %s", runner.experiment_dir / "preflight_report.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
