#!/usr/bin/env python3
"""Analyze per-window feature-importance stability for Day 3 / Day 3B runs."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.research.feature_stability import compute_feature_stability_report


DEFAULT_DAY3B_ROOT = PROJECT_ROOT / "data/results/research/experiments/week_2026_03_22/day3b_tighter_regularization"
DEFAULT_DAY3_ROOT = PROJECT_ROOT / "data/results/research/experiments/week_2026_03_22/day3_model_comparison"


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


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _resolve_latest_experiment() -> Path:
    candidates: list[Path] = []
    for root in [DEFAULT_DAY3B_ROOT, DEFAULT_DAY3_ROOT]:
        if not root.exists():
            continue
        candidates.extend([p for p in root.glob("*_day3_model_comparison") if p.is_dir()])
    if not candidates:
        raise FileNotFoundError("no_day3_or_day3b_experiment_found")
    return sorted(candidates, key=lambda path: path.stat().st_mtime, reverse=True)[0]


def _parse_models(raw: str | None) -> set[str]:
    if raw is None or not str(raw).strip():
        return set()
    return {str(x).strip().lower() for x in str(raw).split(",") if str(x).strip()}


def _aggregate_feature_rows(
    reports: list[dict[str, Any]],
    *,
    key: str,
    metric_key: str,
    output_key: str,
    limit: int,
) -> list[dict[str, Any]]:
    bucket: dict[str, dict[str, Any]] = {}
    for report in reports:
        for row in list(report.get(key, []) or []):
            feature = str(row.get("feature", "") or "").strip()
            if not feature:
                continue
            rec = bucket.setdefault(
                feature,
                {
                    "feature": feature,
                    "_metric_values": [],
                },
            )
            value = _safe_float(row.get(metric_key, np.nan), np.nan)
            if np.isfinite(value):
                rec["_metric_values"].append(float(value))
    rows: list[dict[str, Any]] = []
    for feature, rec in bucket.items():
        vals = np.asarray(rec.pop("_metric_values", []), dtype=float)
        rows.append(
            {
                "feature": feature,
                output_key: float(np.mean(vals)) if len(vals) else 0.0,
                "seed_support": int(len(vals)),
            }
        )
    rows.sort(key=lambda row: (-_safe_float(row.get(output_key, 0.0)), row.get("feature", "")))
    return rows[: max(1, int(limit))]


def _mean_ok(rows: list[dict[str, Any]], key: str) -> float | None:
    vals = [_safe_float(row.get(key, np.nan), np.nan) for row in rows]
    vals = [v for v in vals if np.isfinite(v)]
    return float(np.mean(vals)) if vals else None


def _stability_band(mean_corr: float | None, stable_threshold: float, mixed_threshold: float) -> tuple[str, str]:
    if mean_corr is None:
        return "unknown", "No stability result available yet. Rerun after the upgraded pipeline logs per-window importances."
    if mean_corr >= stable_threshold:
        return "stable", "Proceed to Track B hyperparameter tuning."
    if mean_corr >= mixed_threshold:
        return "mixed", "Mixed signal. Pair targeted tuning with a feature audit."
    return "unstable", "Feature-side instability likely dominates. Audit features before more tuning."


def _load_seed_payload(path: Path, top_k: int) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    full_result = dict(payload.get("full_result", {}) or {})
    stability = dict(full_result.get("feature_stability", {}) or {})
    if not stability:
        stability = compute_feature_stability_report(list(full_result.get("windows", []) or []), top_k=top_k)
    seed_summary = dict(payload.get("seed_summary", {}) or {})
    return {
        "seed_file": str(path),
        "seed_summary": seed_summary,
        "feature_stability": stability,
    }


def _render_md(report: dict[str, Any]) -> str:
    lines: list[str] = [
        "# Day 3 Feature Stability Diagnosis",
        "",
        f"- Created: {report.get('created_at')}",
        f"- Experiment Dir: `{report.get('experiment_dir')}`",
        f"- Overall Recommendation: `{report.get('overall_recommendation')}`",
        "",
        "## Model Summary",
        "",
        "| Model | Seeds Analyzed | Mean Pairwise Corr | Mean Top-K Jaccard | Mean Test IC | Mean Train/Test Ratio | Stability | Action |",
        "|---|---:|---:|---:|---:|---:|---|---|",
    ]
    for row in list(report.get("models", []) or []):
        lines.append(
            "| {model} | {seed_count} | {corr} | {jaccard} | {test_ic} | {ratio} | {band} | {action} |".format(
                model=row.get("model", "unknown"),
                seed_count=int(row.get("analyzed_seed_count", 0)),
                corr="n/a" if row.get("mean_pairwise_rank_correlation") is None else f"{float(row.get('mean_pairwise_rank_correlation')):.4f}",
                jaccard="n/a" if row.get("mean_top_feature_jaccard") is None else f"{float(row.get('mean_top_feature_jaccard')):.4f}",
                test_ic=f"{_safe_float(row.get('mean_test_ic', 0.0)):.4f}",
                ratio=f"{_safe_float(row.get('mean_train_test_ratio', 0.0)):.4f}",
                band=row.get("stability_band", "unknown"),
                action=row.get("next_action", ""),
            )
        )

        unstable = list(row.get("most_unstable_features", []) or [])
        if unstable:
            preview = ", ".join(
                f"{item.get('feature')} ({_safe_float(item.get('mean_importance_cv', 0.0)):.2f})"
                for item in unstable[:5]
            )
            lines.extend(["", f"- `{row.get('model')}` most unstable features: {preview}"])

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze Day 3 / Day 3B feature stability from per-window importances")
    parser.add_argument("--experiment-dir", default=None, help="Path to a Day 3 or Day 3B experiment directory")
    parser.add_argument("--models", default=None, help="Optional comma-separated model filter")
    parser.add_argument("--output-dir", default=None, help="Defaults to <experiment-dir>/feature_stability")
    parser.add_argument("--top-k", type=int, default=15)
    parser.add_argument("--stable-threshold", type=float, default=0.70)
    parser.add_argument("--mixed-threshold", type=float, default=0.40)
    args = parser.parse_args()

    experiment_dir = Path(str(args.experiment_dir)).expanduser().resolve() if args.experiment_dir else _resolve_latest_experiment()
    output_dir = Path(str(args.output_dir)).expanduser().resolve() if args.output_dir else experiment_dir / "feature_stability"
    output_dir.mkdir(parents=True, exist_ok=True)

    model_filter = _parse_models(args.models)
    seed_files = sorted((experiment_dir / "seed_results").glob("*_seed_*.json"))
    if not seed_files:
        raise FileNotFoundError(f"no_seed_results_found:{experiment_dir}")

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for path in seed_files:
        payload = _load_seed_payload(path, top_k=int(args.top_k))
        model_name = str(payload.get("seed_summary", {}).get("model", "")).strip().lower()
        if not model_name:
            continue
        if model_filter and model_name not in model_filter:
            continue
        grouped[model_name].append(payload)

    model_rows: list[dict[str, Any]] = []
    for model_name in sorted(grouped):
        seed_payloads = grouped[model_name]
        ok_reports = [
            dict(row.get("feature_stability", {}) or {})
            for row in seed_payloads
            if str(row.get("feature_stability", {}).get("status", "")).lower() == "ok"
        ]
        mean_corr = _mean_ok(ok_reports, "mean_pairwise_rank_correlation")
        mean_jaccard = _mean_ok(ok_reports, "mean_top_feature_jaccard")
        band, next_action = _stability_band(
            mean_corr,
            stable_threshold=float(args.stable_threshold),
            mixed_threshold=float(args.mixed_threshold),
        )
        model_rows.append(
            {
                "model": model_name,
                "seed_count": int(len(seed_payloads)),
                "analyzed_seed_count": int(len(ok_reports)),
                "mean_pairwise_rank_correlation": mean_corr,
                "mean_top_feature_jaccard": mean_jaccard,
                "mean_test_ic": float(
                    np.mean(
                        [
                            _safe_float(row.get("seed_summary", {}).get("mean_ic", 0.0))
                            for row in seed_payloads
                        ]
                    )
                ),
                "mean_train_test_ratio": float(
                    np.mean(
                        [
                            _safe_float(row.get("seed_summary", {}).get("train_test_ratio", 0.0))
                            for row in seed_payloads
                        ]
                    )
                ),
                "stability_band": band,
                "next_action": next_action,
                "most_unstable_features": _aggregate_feature_rows(
                    ok_reports,
                    key="most_unstable_features",
                    metric_key="importance_cv",
                    output_key="mean_importance_cv",
                    limit=int(args.top_k),
                ),
                "top_features_by_mean_importance": _aggregate_feature_rows(
                    ok_reports,
                    key="top_features_by_mean_importance",
                    metric_key="mean_importance",
                    output_key="mean_importance",
                    limit=int(args.top_k),
                ),
                "seed_reports": [
                    {
                        "seed": int(row.get("seed_summary", {}).get("seed", 0)),
                        "test_ic": _safe_float(row.get("seed_summary", {}).get("mean_ic", 0.0)),
                        "train_test_ratio": _safe_float(row.get("seed_summary", {}).get("train_test_ratio", 0.0)),
                        "feature_stability": dict(row.get("feature_stability", {}) or {}),
                        "seed_file": row.get("seed_file"),
                    }
                    for row in seed_payloads
                ],
            }
        )

    stable_models = [row["model"] for row in model_rows if row.get("stability_band") == "stable"]
    mixed_models = [row["model"] for row in model_rows if row.get("stability_band") == "mixed"]
    if stable_models:
        overall_recommendation = f"Run Track B tuning for: {', '.join(stable_models)}"
    elif mixed_models:
        overall_recommendation = f"Do a feature audit first; only then consider limited tuning for: {', '.join(mixed_models)}"
    else:
        overall_recommendation = "Feature instability dominates. Audit features before any Phase 1 hyperparameter sweep."

    report = {
        "created_at": _utc_now(),
        "experiment_dir": str(experiment_dir),
        "output_dir": str(output_dir),
        "stable_threshold": float(args.stable_threshold),
        "mixed_threshold": float(args.mixed_threshold),
        "overall_recommendation": overall_recommendation,
        "models": model_rows,
    }
    _write_json(output_dir / "feature_stability_report.json", report)
    _write_text(output_dir / "feature_stability_report.md", _render_md(report))

    print(f"Experiment: {experiment_dir}")
    print(f"Feature stability report: {output_dir / 'feature_stability_report.json'}")
    for row in model_rows:
        corr = row.get("mean_pairwise_rank_correlation")
        corr_txt = "n/a" if corr is None else f"{float(corr):.4f}"
        print(
            f"{row.get('model')}: corr={corr_txt} ratio={_safe_float(row.get('mean_train_test_ratio', 0.0)):.4f} "
            f"band={row.get('stability_band')} action={row.get('next_action')}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
