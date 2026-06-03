#!/usr/bin/env python3
"""Day 3B tighter-regularization rerun for the top tree candidates.

This wrapper reuses the proven Day 3 comparison engine, but narrows the
candidate set to XGBoost and CatBoost with stronger regularization. It keeps
the same detailed live progress artifacts:

- stdout model / seed / window progress
- heartbeat.json
- comparison_live.md

By default it requires native CatBoost to be installed. The original Day 3 run
used the repository's CatBoost adapter fallback because the package was not
present, which is not promotion-grade evidence for a CatBoost promotion
decision. A debug-only fallback can still be enabled explicitly.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import logging
import shutil
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

try:
    from scipy.stats import ConstantInputWarning
except Exception:  # pragma: no cover - keep startup robust
    ConstantInputWarning = None


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BASE_RUNNER_PATH = PROJECT_ROOT / "scripts/research/run_day3_model_comparison.py"
DEFAULT_OUTPUT_ROOT = (
    PROJECT_ROOT / "data/results/research/experiments/week_2026_03_22/day3b_tighter_regularization"
)
DEFAULT_DAY3_ROOT = (
    PROJECT_ROOT / "data/results/research/experiments/week_2026_03_22/day3_model_comparison"
)
DEFAULT_POLICY_PATH = PROJECT_ROOT / "config/research_policy.yaml"
LOGGER = logging.getLogger("northstar.day3b_tighter_regularization")


def _load_base_runner() -> ModuleType:
    spec = importlib.util.spec_from_file_location("northstar_day3_base_runner", BASE_RUNNER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable_to_load_base_runner:{BASE_RUNNER_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


BASE = _load_base_runner()


def _module_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _resolve_latest_day3_summary() -> Path | None:
    if not DEFAULT_DAY3_ROOT.exists():
        return None
    candidates = sorted(
        DEFAULT_DAY3_ROOT.glob("*_day3_model_comparison/summary.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def _parse_models(raw: str) -> list[str]:
    models = [x.strip().lower() for x in str(raw).split(",") if x.strip()]
    if not models:
        raise ValueError("no_models_requested")
    unsupported = [m for m in models if m not in {"xgboost", "catboost"}]
    if unsupported:
        raise ValueError(f"unsupported_day3b_models:{','.join(unsupported)}")
    return models


def _configure_day3b_plans() -> None:
    BASE.DAY3_MODEL_PLANS = {
        **BASE.DAY3_MODEL_PLANS,
        "xgboost": BASE.ModelPlan(
            name="xgboost",
            params={
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
            },
            seeds=[42, 123, 456, 789, 1337],
            notes="Day 3B tighter-regularization XGBoost rerun with shallower depth and stronger child/L1/L2 constraints.",
        ),
        "catboost": BASE.ModelPlan(
            name="catboost",
            params={
                "iterations": 300,
                "depth": 4,
                "learning_rate": 0.02,
                "l2_leaf_reg": 10.0,
                "min_data_in_leaf": 25,
                "subsample": 0.70,
                "loss_function": "RMSE",
                "boosting_type": "Ordered",
                "cat_features": ["sector"],
                "thread_count": 1,
                "allow_writing_files": False,
            },
            seeds=[42, 123, 456, 789, 1337],
            notes="Day 3B tighter-regularization CatBoost rerun. Requires native CatBoost for promotion-grade evidence.",
        ),
    }


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Day 3B tighter-regularization rerun for XGBoost and CatBoost")
    parser.add_argument("--policy-path", default=str(DEFAULT_POLICY_PATH))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--baseline-summary", default=None)
    parser.add_argument("--prior-day3-summary", default=None)
    parser.add_argument("--resume-experiment", default=None)
    parser.add_argument("--resume-latest-incomplete", action="store_true")
    parser.add_argument("--resource-profile", choices=["laptop_safe", "strict_plan"], default="laptop_safe")
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--models", default="xgboost,catboost")
    parser.add_argument("--max-seeds-per-model", type=int, default=None)
    parser.add_argument("--max-windows", type=int, default=None)
    parser.add_argument("--log-level", default="INFO")
    parser.add_argument(
        "--allow-catboost-fallback",
        action="store_true",
        help="Allow the repo's ExtraTrees fallback when native CatBoost is not installed. Debug-only, not promotion-grade.",
    )
    return parser


def _resolve_resume_path(output_dir: Path, requested: str | None, resume_latest: bool) -> str | None:
    if requested:
        return str(Path(requested).expanduser().resolve())
    if not resume_latest:
        return None
    latest = BASE._resolve_latest_incomplete_experiment(output_dir)
    if latest is None:
        raise ValueError(f"no_incomplete_day3b_experiment_under:{output_dir}")
    return str(latest)


def _guard_backends(models: list[str], *, allow_catboost_fallback: bool) -> None:
    if "xgboost" in models and not _module_available("xgboost"):
        raise RuntimeError(
            "native_xgboost_not_installed: Day 3B would fall back to RandomForest, so aborting to avoid a misleading overnight run."
        )
    if "catboost" in models and not _module_available("catboost"):
        if allow_catboost_fallback:
            LOGGER.warning(
                "Native CatBoost is not installed. The catboost slot will use the ExtraTrees fallback. "
                "This is useful for smoke/debug only and is not promotion-grade evidence."
            )
            return
        raise RuntimeError(
            "native_catboost_not_installed: Day 3B is meant to answer whether tighter regularization salvages CatBoost vs XGBoost. "
            "Aborting before dataset build to avoid wasting an overnight run on the ExtraTrees fallback. "
            "Install catboost or rerun with --allow-catboost-fallback for debug-only smoke runs."
        )


def _build_cfg(ns: argparse.Namespace, models: list[str], resume_path: str | None):
    return BASE.RunnerConfig(
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


def _copy_summary_aliases(experiment_dir: Path) -> None:
    summary_json = experiment_dir / "summary.json"
    summary_md = experiment_dir / "summary.md"
    if summary_json.exists():
        shutil.copyfile(summary_json, experiment_dir / "model_comparison_summary.json")
    if summary_md.exists():
        shutil.copyfile(summary_md, experiment_dir / "model_comparison_summary.md")


def _build_vs_day3_artifacts(experiment_dir: Path, prior_day3_summary_path: Path | None) -> None:
    if prior_day3_summary_path is None or not prior_day3_summary_path.exists():
        return
    current_path = experiment_dir / "summary.json"
    if not current_path.exists():
        return

    current = json.loads(current_path.read_text())
    prior = json.loads(prior_day3_summary_path.read_text())
    current_rows = {str(row.get("model")): row for row in current.get("model_comparison", [])}
    prior_rows = {str(row.get("model")): row for row in prior.get("model_comparison", [])}
    common = [name for name in ["xgboost", "catboost"] if name in current_rows and name in prior_rows]
    if not common:
        return

    rows: list[dict[str, Any]] = []
    for name in common:
        day3 = prior_rows[name]
        day3b = current_rows[name]
        rows.append(
            {
                "model": name,
                "day3_mean_ic": float(day3.get("mean_ic", 0.0)),
                "day3b_mean_ic": float(day3b.get("mean_ic", 0.0)),
                "mean_ic_change": float(day3b.get("mean_ic", 0.0)) - float(day3.get("mean_ic", 0.0)),
                "day3_ic_ir": float(day3.get("ic_ir", 0.0)),
                "day3b_ic_ir": float(day3b.get("ic_ir", 0.0)),
                "ic_ir_change": float(day3b.get("ic_ir", 0.0)) - float(day3.get("ic_ir", 0.0)),
                "day3_train_test_ratio": float(day3.get("train_test_ratio", 0.0)),
                "day3b_train_test_ratio": float(day3b.get("train_test_ratio", 0.0)),
                "ratio_change": float(day3b.get("train_test_ratio", 0.0)) - float(day3.get("train_test_ratio", 0.0)),
                "day3_turnover": float(day3.get("turnover", 0.0)),
                "day3b_turnover": float(day3b.get("turnover", 0.0)),
                "turnover_change": float(day3b.get("turnover", 0.0)) - float(day3.get("turnover", 0.0)),
            }
        )

    payload = {
        "created_at": BASE._utc_now().isoformat(),
        "prior_day3_summary_path": str(prior_day3_summary_path),
        "current_day3b_summary_path": str(current_path),
        "comparison": rows,
    }
    _write_json(experiment_dir / "comparison_against_day3.json", payload)

    lines = [
        "# Day 3B vs Day 3",
        "",
        f"- Prior Day 3 summary: `{prior_day3_summary_path}`",
        f"- Current Day 3B summary: `{current_path}`",
        "",
        "| Model | Day 3 IC | Day 3B IC | IC change | Day 3 ratio | Day 3B ratio | Ratio change | Day 3 IR | Day 3B IR | IR change |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            "| {model} | {day3_ic:.4f} | {day3b_ic:.4f} | {ic_change:.4f} | {day3_ratio:.4f} | {day3b_ratio:.4f} | {ratio_change:.4f} | {day3_ir:.4f} | {day3b_ir:.4f} | {ir_change:.4f} |".format(
                model=row["model"],
                day3_ic=row["day3_mean_ic"],
                day3b_ic=row["day3b_mean_ic"],
                ic_change=row["mean_ic_change"],
                day3_ratio=row["day3_train_test_ratio"],
                day3b_ratio=row["day3b_train_test_ratio"],
                ratio_change=row["ratio_change"],
                day3_ir=row["day3_ic_ir"],
                day3b_ir=row["day3b_ic_ir"],
                ir_change=row["ic_ir_change"],
            )
        )
    _write_text(experiment_dir / "comparison_against_day3.md", "\n".join(lines) + "\n")


def main() -> int:
    parser = _build_arg_parser()
    ns = parser.parse_args()

    if ConstantInputWarning is not None:
        import warnings

        warnings.filterwarnings("ignore", category=ConstantInputWarning)

    logging.basicConfig(
        level=getattr(logging, str(ns.log_level).upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(message)s",
    )
    logging.getLogger("src.valuation.valuation_feature_block").setLevel(logging.WARNING)

    models = _parse_models(ns.models)
    if ns.smoke:
        if ns.max_seeds_per_model is None:
            ns.max_seeds_per_model = 1
        if ns.max_windows is None:
            ns.max_windows = 1

    output_dir = Path(str(ns.output_dir)).expanduser().resolve()
    resume_path = _resolve_resume_path(output_dir, ns.resume_experiment, bool(ns.resume_latest_incomplete))
    prior_day3_summary = (
        Path(str(ns.prior_day3_summary)).expanduser().resolve()
        if ns.prior_day3_summary
        else _resolve_latest_day3_summary()
    )

    try:
        _guard_backends(models, allow_catboost_fallback=bool(ns.allow_catboost_fallback))
    except RuntimeError as exc:
        LOGGER.error("%s", exc)
        return 2
    _configure_day3b_plans()

    cfg = _build_cfg(ns, models, resume_path)
    runner = BASE.Day3ModelComparisonRunner(cfg)

    day3b_manifest = {
        "created_at": BASE._utc_now().isoformat(),
        "experiment_dir": str(runner.experiment_dir),
        "output_root": str(output_dir),
        "prior_day3_summary_path": str(prior_day3_summary) if prior_day3_summary else None,
        "requested_models": models,
        "native_backends": {
            "xgboost": _module_available("xgboost"),
            "catboost": _module_available("catboost"),
        },
        "allow_catboost_fallback": bool(ns.allow_catboost_fallback),
        "tighter_plans": {
            name: {
                "params": BASE.DAY3_MODEL_PLANS[name].params,
                "seeds": BASE.DAY3_MODEL_PLANS[name].seeds,
                "notes": BASE.DAY3_MODEL_PLANS[name].notes,
            }
            for name in models
        },
    }
    _write_json(runner.experiment_dir / "day3b_manifest.json", day3b_manifest)

    LOGGER.info("Day 3B experiment dir: %s", runner.experiment_dir)
    LOGGER.info("Day 3B models: %s", models)
    if prior_day3_summary is not None:
        LOGGER.info("Prior Day 3 summary: %s", prior_day3_summary)
    result = runner.run()
    LOGGER.info("Experiment dir: %s", runner.experiment_dir)

    if result.get("status") == "completed":
        _copy_summary_aliases(runner.experiment_dir)
        _build_vs_day3_artifacts(runner.experiment_dir, prior_day3_summary)
        LOGGER.info("Summary JSON: %s", runner.experiment_dir / "summary.json")
        LOGGER.info("Summary MD:   %s", runner.experiment_dir / "summary.md")
        LOGGER.info("Day 3B vs Day 3: %s", runner.experiment_dir / "comparison_against_day3.md")
        LOGGER.info("Selected model: %s", result.get("decision", {}).get("selected_model"))
    else:
        LOGGER.info("Preflight report: %s", runner.experiment_dir / "preflight_report.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
