#!/usr/bin/env python3
"""Controlled Day 3C rerun on the feature-updated research panel."""

from __future__ import annotations

import argparse
import importlib.util
import json
import logging
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


LOGGER = logging.getLogger("northstar.day3c_feature_updated_baseline")
DAY3B_RUNNER_PATH = PROJECT_ROOT / "scripts/research/run_day3b_tighter_regularization.py"
STABILITY_SCRIPT_PATH = PROJECT_ROOT / "scripts/research/analyze_day3_feature_stability.py"
DEFAULT_POLICY_PATH = PROJECT_ROOT / "config/research_policy.yaml"
DEFAULT_OUTPUT_ROOT = (
    PROJECT_ROOT / "data/results/research/experiments/week_2026_03_22/day3c_feature_updated_baseline"
)
DEFAULT_DAY3B_BASELINE_SUMMARY = (
    PROJECT_ROOT
    / "data/results/research/experiments/week_2026_03_22/day3b_tighter_regularization/20260325_204512_day3_model_comparison/summary.json"
)
RUN_SPECS = [
    ("run_a_full_sentiment", "full", "Run A: full sentiment mode with Gap 9 and raw macro rate features."),
    ("run_b_reduced_sentiment", "reduced", "Run B: reduced sentiment mode with Gap 9 and raw macro rate features."),
]
MODEL_ORDER = ["catboost", "xgboost"]


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable_to_load_module:{path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


DAY3B = _load_module("northstar_day3c_day3b_runner", DAY3B_RUNNER_PATH)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except Exception:
        return float(default)
    if not np.isfinite(out):
        return float(default)
    return float(out)


def _json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            return str(value)
    return str(value)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=_json_default), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _format_decimal(value: Any) -> str:
    v = _safe_float(value, np.nan)
    return "n/a" if not np.isfinite(v) else f"{v:.4f}"


def _format_pct(value: Any) -> str:
    v = _safe_float(value, np.nan)
    return "n/a" if not np.isfinite(v) else f"{v * 100.0:.2f}%"


def _format_ratio(value: Any) -> str:
    v = _safe_float(value, np.nan)
    return "n/a" if not np.isfinite(v) else f"{v:.2f}x"


def _load_summary(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"invalid_summary_json:{path}")
    return payload


def _write_policy_variant(base_policy_path: Path, out_path: Path, sentiment_mode: str) -> Path:
    payload = yaml.safe_load(base_policy_path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"invalid_policy_yaml:{base_policy_path}")
    dataset_cfg = payload.setdefault("historical_research", {}).setdefault("dataset", {})
    dataset_cfg["sentiment_feature_mode"] = str(sentiment_mode)
    dataset_cfg["use_gap9_academic_factors"] = True
    dataset_cfg["use_macro_features"] = True
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return out_path


def _build_runner_cfg(
    args: argparse.Namespace,
    *,
    policy_path: Path,
    run_dir: Path,
) -> Any:
    return DAY3B.BASE.RunnerConfig(
        policy_path=str(policy_path),
        output_dir=str(run_dir.parent),
        baseline_summary_path=None,
        resume_experiment_path=str(run_dir),
        resource_profile=str(args.resource_profile),
        preflight_only=bool(args.preflight_only),
        smoke=bool(args.smoke),
        models=["xgboost", "catboost"],
        max_seeds_per_model=args.max_seeds_per_model,
        max_windows_override=args.max_windows,
        log_level=str(args.log_level),
    )


def _mean_exposure_by_model(experiment_dir: Path) -> dict[str, float]:
    exposures: dict[str, list[float]] = {}
    for seed_path in sorted((experiment_dir / "seed_results").glob("*_seed_*.json")):
        payload = json.loads(seed_path.read_text(encoding="utf-8"))
        seed_summary = dict(payload.get("seed_summary", {}) or {})
        model_name = str(seed_summary.get("model", "")).strip().lower()
        if not model_name:
            continue
        snapshots = list((payload.get("full_result", {}) or {}).get("rebalance_snapshots", []) or [])
        gross = [
            _safe_float(snapshot.get("gross_exposure", np.nan), np.nan)
            for snapshot in snapshots
            if isinstance(snapshot, dict)
        ]
        gross = [value for value in gross if np.isfinite(value)]
        if gross:
            exposures.setdefault(model_name, []).append(float(np.mean(gross)))
    return {
        model_name: float(np.mean(values))
        for model_name, values in exposures.items()
        if values
    }


def _collect_run_metrics(experiment_dir: Path) -> dict[str, dict[str, Any]]:
    summary = _load_summary(experiment_dir / "summary.json")
    rows = {
        str(row.get("model", "")).strip().lower(): dict(row)
        for row in list(summary.get("model_comparison", []) or [])
        if str(row.get("model", "")).strip()
    }
    exposures = _mean_exposure_by_model(experiment_dir)
    for model_name, mean_exposure in exposures.items():
        rows.setdefault(model_name, {})
        rows[model_name]["mean_exposure"] = float(mean_exposure)
    return rows


def _compare_direction(new_value: float, baseline_value: float) -> str:
    if not np.isfinite(new_value) or not np.isfinite(baseline_value):
        return "not measurable"
    if new_value < baseline_value - 1e-9:
        return "improved"
    if new_value > baseline_value + 1e-9:
        return "worsened"
    return "matched"


def _choose_recommended_config(
    run_a_rows: dict[str, dict[str, Any]],
    run_b_rows: dict[str, dict[str, Any]],
) -> tuple[str, str]:
    def _score(rows: dict[str, dict[str, Any]]) -> tuple[float, float, float]:
        cat = dict(rows.get("catboost", {}) or {})
        xgb = dict(rows.get("xgboost", {}) or {})
        ratio = _safe_float(cat.get("train_test_ratio", float("inf")), float("inf"))
        mean_ic = -_safe_float(cat.get("mean_ic", -999.0), -999.0)
        xgb_ic = -_safe_float(xgb.get("mean_ic", -999.0), -999.0)
        return (ratio, mean_ic, xgb_ic)

    full_score = _score(run_a_rows)
    reduced_score = _score(run_b_rows)
    if reduced_score < full_score:
        return (
            "reduced_sentiment",
            "Reduced sentiment delivered the better CatBoost train/test ratio, with CatBoost mean IC as the first tiebreaker and XGBoost mean IC as the second.",
        )
    return (
        "full_sentiment",
        "Full sentiment delivered the better CatBoost train/test ratio, with CatBoost mean IC as the first tiebreaker and XGBoost mean IC as the second.",
    )


def _decision_gate(
    baseline_rows: dict[str, dict[str, Any]],
    run_a_rows: dict[str, dict[str, Any]],
    run_b_rows: dict[str, dict[str, Any]],
    recommended_config: str,
) -> dict[str, Any]:
    baseline_cat_ratio = _safe_float(
        dict(baseline_rows.get("catboost", {}) or {}).get("train_test_ratio", np.nan),
        np.nan,
    )
    run_a_cat_ratio = _safe_float(dict(run_a_rows.get("catboost", {}) or {}).get("train_test_ratio", np.nan), np.nan)
    run_b_cat_ratio = _safe_float(dict(run_b_rows.get("catboost", {}) or {}).get("train_test_ratio", np.nan), np.nan)
    ratios = [value for value in [run_a_cat_ratio, run_b_cat_ratio] if np.isfinite(value)]
    best_ratio = min(ratios) if ratios else float("inf")
    best_config = "full_sentiment" if np.isfinite(run_a_cat_ratio) and run_a_cat_ratio <= run_b_cat_ratio else "reduced_sentiment"

    if np.isfinite(baseline_cat_ratio) and np.isfinite(best_ratio) and best_ratio > baseline_cat_ratio + 1e-9:
        return {
            "verdict": "feature_update_hurt",
            "recommended_next_step": "Revert to the Day 3B feature configuration for promotion work and flag sentiment features as the likely cause.",
            "best_config_for_day3c": recommended_config,
        }
    if best_ratio < 3.0:
        return {
            "verdict": "promotion_eligible",
            "recommended_next_step": f"Proceed to full Day 4 regime analysis and the Day 7 memo using `{best_config}`.",
            "best_config_for_day3c": best_config,
        }
    if best_ratio < 5.0:
        return {
            "verdict": "proceed_day4_regime_analysis",
            "recommended_next_step": f"Proceed to Day 4 regime analysis using `{best_config}`.",
            "best_config_for_day3c": best_config,
        }
    return {
        "verdict": "feature_update_helped_partially",
        "recommended_next_step": f"Document `{recommended_config}` as the preferred Day 3C config and proceed to the Kaggle sprint as planned.",
        "best_config_for_day3c": recommended_config,
    }


def _render_model_table(
    *,
    model_name: str,
    baseline_row: dict[str, Any],
    run_a_row: dict[str, Any],
    run_b_row: dict[str, Any],
) -> list[str]:
    return [
        f"## {model_name.upper()}",
        "",
        "| Metric | Day 3B baseline | Run A full sentiment | Run B reduced sentiment |",
        "|---|---:|---:|---:|",
        f"| Mean IC | {_format_decimal(baseline_row.get('mean_ic'))} | {_format_decimal(run_a_row.get('mean_ic'))} | {_format_decimal(run_b_row.get('mean_ic'))} |",
        f"| IC IR | {_format_decimal(baseline_row.get('ic_ir'))} | {_format_decimal(run_a_row.get('ic_ir'))} | {_format_decimal(run_b_row.get('ic_ir'))} |",
        f"| Hit rate | {_format_pct(baseline_row.get('hit_rate'))} | {_format_pct(run_a_row.get('hit_rate'))} | {_format_pct(run_b_row.get('hit_rate'))} |",
        f"| Train/test ratio | {_format_ratio(baseline_row.get('train_test_ratio'))} | {_format_ratio(run_a_row.get('train_test_ratio'))} | {_format_ratio(run_b_row.get('train_test_ratio'))} |",
        f"| Mean exposure | {_format_pct(baseline_row.get('mean_exposure'))} | {_format_pct(run_a_row.get('mean_exposure'))} | {_format_pct(run_b_row.get('mean_exposure'))} |",
        "",
    ]


def _render_stability_section(stability_report: dict[str, Any] | None, run_dir: Path) -> list[str]:
    lines = [
        "## Reduced Sentiment Stability",
        "",
        f"- Stability source: `{run_dir / 'feature_stability' / 'feature_stability_report.json'}`",
    ]
    if not stability_report:
        lines.extend(["", "No stability report was produced.", ""])
        return lines

    lines.extend(
        [
            f"- Overall recommendation: `{stability_report.get('overall_recommendation', '')}`",
            "",
            "| Model | Mean pairwise corr | Mean top-k Jaccard | Mean test IC | Mean train/test ratio | Stability | Action |",
            "|---|---:|---:|---:|---:|---|---|",
        ]
    )
    for row in list(stability_report.get("models", []) or []):
        lines.append(
            "| {model} | {corr} | {jaccard} | {test_ic} | {ratio} | {band} | {action} |".format(
                model=row.get("model", "unknown"),
                corr=_format_decimal(row.get("mean_pairwise_rank_correlation")),
                jaccard=_format_decimal(row.get("mean_top_feature_jaccard")),
                test_ic=_format_decimal(row.get("mean_test_ic")),
                ratio=_format_ratio(row.get("mean_train_test_ratio")),
                band=row.get("stability_band", "unknown"),
                action=row.get("next_action", ""),
            )
        )
    lines.append("")
    return lines


def _build_comparison_payload(
    *,
    baseline_summary_path: Path,
    run_a_dir: Path,
    run_b_dir: Path,
    stability_report: dict[str, Any] | None,
) -> tuple[dict[str, Any], str]:
    baseline_rows = _collect_run_metrics(baseline_summary_path.parent)
    run_a_rows = _collect_run_metrics(run_a_dir)
    run_b_rows = _collect_run_metrics(run_b_dir)

    recommended_config, recommendation_rationale = _choose_recommended_config(run_a_rows, run_b_rows)
    gate = _decision_gate(baseline_rows, run_a_rows, run_b_rows, recommended_config)

    cat_baseline = dict(baseline_rows.get("catboost", {}) or {})
    cat_a = dict(run_a_rows.get("catboost", {}) or {})
    cat_b = dict(run_b_rows.get("catboost", {}) or {})
    xgb_baseline = dict(baseline_rows.get("xgboost", {}) or {})
    xgb_a = dict(run_a_rows.get("xgboost", {}) or {})
    xgb_b = dict(run_b_rows.get("xgboost", {}) or {})

    best_cat_ratio = min(
        _safe_float(cat_a.get("train_test_ratio", float("inf")), float("inf")),
        _safe_float(cat_b.get("train_test_ratio", float("inf")), float("inf")),
    )
    best_xgb_ratio = min(
        _safe_float(xgb_a.get("train_test_ratio", float("inf")), float("inf")),
        _safe_float(xgb_b.get("train_test_ratio", float("inf")), float("inf")),
    )
    gap9_sentence = (
        f"Against the Day 3B baseline, CatBoost ratio { _compare_direction(best_cat_ratio, _safe_float(cat_baseline.get('train_test_ratio', np.nan), np.nan)) } "
        f"from {_format_ratio(cat_baseline.get('train_test_ratio'))} to {_format_ratio(best_cat_ratio)}, and XGBoost ratio "
        f"{ _compare_direction(best_xgb_ratio, _safe_float(xgb_baseline.get('train_test_ratio', np.nan), np.nan)) } "
        f"from {_format_ratio(xgb_baseline.get('train_test_ratio'))} to {_format_ratio(best_xgb_ratio)}."
    )

    cat_ic_delta = _safe_float(cat_b.get("mean_ic", np.nan), np.nan) - _safe_float(cat_a.get("mean_ic", np.nan), np.nan)
    xgb_ic_delta = _safe_float(xgb_b.get("mean_ic", np.nan), np.nan) - _safe_float(xgb_a.get("mean_ic", np.nan), np.nan)
    sentiment_sentence = (
        f"Reducing sentiment {'helped' if cat_ic_delta > 0 else 'hurt' if cat_ic_delta < 0 else 'left unchanged'} "
        f"CatBoost mean IC by {_format_decimal(cat_ic_delta)} and "
        f"{'helped' if xgb_ic_delta > 0 else 'hurt' if xgb_ic_delta < 0 else 'left unchanged'} "
        f"XGBoost mean IC by {_format_decimal(xgb_ic_delta)}."
    )

    payload = {
        "created_at": _utc_now(),
        "baseline_summary_path": str(baseline_summary_path),
        "run_a_dir": str(run_a_dir),
        "run_b_dir": str(run_b_dir),
        "runs": {
            "day3b_baseline": baseline_rows,
            "run_a_full_sentiment": run_a_rows,
            "run_b_reduced_sentiment": run_b_rows,
        },
        "decision_gate": gate,
        "recommended_config": {
            "name": recommended_config,
            "rationale": recommendation_rationale,
        },
        "interpretation": {
            "gap9_effect": gap9_sentence,
            "sentiment_effect": sentiment_sentence,
            "verdict": gate["verdict"],
            "recommended_next_step": gate["recommended_next_step"],
        },
        "stability_report": stability_report or {},
    }

    lines: list[str] = [
        "# Day 3C Feature-Updated Baseline",
        "",
        f"- Created: {payload['created_at']}",
        f"- Day 3B baseline summary: `{baseline_summary_path}`",
        f"- Run A dir: `{run_a_dir}`",
        f"- Run B dir: `{run_b_dir}`",
        "",
        "## Side-By-Side Comparison",
        "",
    ]
    for model_name in MODEL_ORDER:
        lines.extend(
            _render_model_table(
                model_name=model_name,
                baseline_row=dict(baseline_rows.get(model_name, {}) or {}),
                run_a_row=dict(run_a_rows.get(model_name, {}) or {}),
                run_b_row=dict(run_b_rows.get(model_name, {}) or {}),
            )
        )

    lines.extend(
        [
            "## Interpretation",
            "",
            gap9_sentence,
            "",
            sentiment_sentence,
            "",
            f"Verdict: `{gate['verdict']}`. {gate['recommended_next_step']}",
            "",
        ]
    )

    lines.extend(_render_stability_section(stability_report, run_b_dir))

    lines.extend(
        [
            "## Recommended Config",
            "",
            "```json",
            json.dumps(
                {
                    "recommended_config": recommended_config,
                    "rationale": recommendation_rationale,
                },
                indent=2,
            ),
            "```",
            "",
        ]
    )

    return payload, "\n".join(lines)


def _run_feature_stability(experiment_dir: Path) -> dict[str, Any] | None:
    cmd = [
        sys.executable,
        str(STABILITY_SCRIPT_PATH),
        "--experiment-dir",
        str(experiment_dir),
    ]
    subprocess.run(cmd, cwd=PROJECT_ROOT, check=True)
    report_path = experiment_dir / "feature_stability" / "feature_stability_report.json"
    if not report_path.exists():
        return None
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def _run_one_variant(
    args: argparse.Namespace,
    *,
    root_dir: Path,
    run_name: str,
    sentiment_mode: str,
    notes: str,
) -> dict[str, Any]:
    run_dir = root_dir / run_name
    run_dir.mkdir(parents=True, exist_ok=True)
    policy_variant_path = root_dir / "policy_variants" / f"{run_name}.yaml"
    _write_policy_variant(Path(str(args.policy_path)).expanduser().resolve(), policy_variant_path, sentiment_mode)

    cfg = _build_runner_cfg(args, policy_path=policy_variant_path, run_dir=run_dir)
    runner = DAY3B.BASE.Day3ModelComparisonRunner(cfg)
    manifest = {
        "created_at": _utc_now(),
        "run_name": run_name,
        "sentiment_mode": sentiment_mode,
        "notes": notes,
        "policy_variant_path": str(policy_variant_path),
        "experiment_dir": str(run_dir),
        "model_plans": {
            name: {
                "params": DAY3B.BASE.DAY3_MODEL_PLANS[name].params,
                "seeds": DAY3B.BASE.DAY3_MODEL_PLANS[name].seeds,
                "notes": DAY3B.BASE.DAY3_MODEL_PLANS[name].notes,
            }
            for name in ["xgboost", "catboost"]
        },
    }
    _write_json(run_dir / "day3c_manifest.json", manifest)

    LOGGER.info("Running %s with sentiment_mode=%s", run_name, sentiment_mode)
    result = runner.run()
    if result.get("status") != "completed":
        raise RuntimeError(f"day3c_run_not_completed:{run_name}:{result.get('status')}")
    return result


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the controlled Day 3C feature-updated baseline rerun.")
    parser.add_argument("--policy-path", default=str(DEFAULT_POLICY_PATH))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--baseline-summary", default=str(DEFAULT_DAY3B_BASELINE_SUMMARY))
    parser.add_argument("--resource-profile", choices=["laptop_safe", "strict_plan"], default="laptop_safe")
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--max-seeds-per-model", type=int, default=None)
    parser.add_argument("--max-windows", type=int, default=None)
    parser.add_argument("--allow-catboost-fallback", action="store_true")
    parser.add_argument("--log-level", default="INFO")
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()

    logging.basicConfig(
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    output_root = Path(str(args.output_dir)).expanduser().resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    baseline_summary_path = Path(str(args.baseline_summary)).expanduser().resolve()
    if not baseline_summary_path.exists():
        raise FileNotFoundError(f"day3b_baseline_summary_not_found:{baseline_summary_path}")

    DAY3B._guard_backends(["xgboost", "catboost"], allow_catboost_fallback=bool(args.allow_catboost_fallback))
    DAY3B._configure_day3b_plans()

    for run_name, sentiment_mode, notes in RUN_SPECS:
        _run_one_variant(
            args,
            root_dir=output_root,
            run_name=run_name,
            sentiment_mode=sentiment_mode,
            notes=notes,
        )

    if args.preflight_only:
        LOGGER.info("Preflight-only run completed for both Day 3C variants.")
        return 0

    run_a_dir = output_root / "run_a_full_sentiment"
    run_b_dir = output_root / "run_b_reduced_sentiment"
    stability_report = _run_feature_stability(run_b_dir)
    comparison_payload, comparison_md = _build_comparison_payload(
        baseline_summary_path=baseline_summary_path,
        run_a_dir=run_a_dir,
        run_b_dir=run_b_dir,
        stability_report=stability_report,
    )
    _write_json(output_root / "comparison.json", comparison_payload)
    _write_text(output_root / "comparison.md", comparison_md)

    LOGGER.info("Run A summary: %s", run_a_dir / "summary.json")
    LOGGER.info("Run B summary: %s", run_b_dir / "summary.json")
    LOGGER.info("Comparison report: %s", output_root / "comparison.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
