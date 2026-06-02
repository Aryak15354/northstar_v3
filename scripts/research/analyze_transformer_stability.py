#!/usr/bin/env python3
"""Analyze Transformer walk-forward stability from saved window artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.research.transformer_stability import (
    compute_seed_transformer_stability,
    discover_transformer_artifacts,
    resolve_transformer_ratio,
    safe_float,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _mean_ok(rows: list[dict[str, Any]], key: str) -> float | None:
    vals = [safe_float(row.get(key, np.nan), np.nan) for row in rows]
    vals = [v for v in vals if np.isfinite(v)]
    return float(np.mean(vals)) if vals else None


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
            rec = bucket.setdefault(feature, {"feature": feature, "_values": []})
            value = safe_float(row.get(metric_key, np.nan), np.nan)
            if np.isfinite(value):
                rec["_values"].append(float(value))
    rows: list[dict[str, Any]] = []
    for feature, rec in bucket.items():
        vals = np.asarray(rec.pop("_values", []), dtype=float)
        rows.append(
            {
                "feature": feature,
                output_key: float(np.mean(vals)) if len(vals) else 0.0,
                "seed_support": int(len(vals)),
            }
        )
    rows.sort(key=lambda row: (-safe_float(row.get(output_key, 0.0)), row.get("feature", "")))
    return rows[: max(1, int(limit))]


def _band_and_action(mean_corr: float | None, *, stable_threshold: float, mixed_threshold: float) -> tuple[str, str, str]:
    if mean_corr is None:
        return (
            "unknown",
            "unknown",
            "No stability result available because no valid Transformer window bundles were found.",
        )
    if mean_corr >= stable_threshold:
        return (
            "stable",
            "stable",
            "Transformer is a legitimate Day 4 candidate. Proceed to Day 4 regime analysis.",
        )
    if mean_corr >= mixed_threshold:
        action = (
            "Cautious. Manual review required before Day 4."
            if mean_corr >= 0.60
            else "Drop Transformer. Day 4 runs with CatBoost only."
        )
        return ("cautious", "mixed", action)
    return ("unstable", "unstable", "Drop Transformer. Day 4 runs with CatBoost only.")


def _render_md(report: dict[str, Any]) -> str:
    row = dict((report.get("models") or [{}])[0] or {})
    lines = [
        "# Transformer Stability Diagnosis",
        "",
        f"- Created: {report.get('created_at')}",
        f"- Experiment Dir: `{report.get('experiment_dir')}`",
        f"- Artifact Status: `{report.get('artifact_status')}`",
        f"- Overall Recommendation: `{report.get('overall_recommendation')}`",
        "",
        "## Summary",
        "",
        "| Model | Seeds Analyzed | Mean Pairwise Corr | Mean Top-K Jaccard | Mean Test IC | Mean Train/Test Ratio | Band | Action |",
        "|---|---:|---:|---:|---:|---:|---|---|",
        "| {model} | {seed_count} | {corr} | {jaccard} | {test_ic} | {ratio} | {band} | {action} |".format(
            model=row.get("model", "transformer"),
            seed_count=int(row.get("analyzed_seed_count", 0)),
            corr="n/a" if row.get("mean_pairwise_rank_correlation") is None else f"{float(row.get('mean_pairwise_rank_correlation')):.4f}",
            jaccard="n/a" if row.get("mean_top_feature_jaccard") is None else f"{float(row.get('mean_top_feature_jaccard')):.4f}",
            test_ic=f"{safe_float(row.get('mean_test_ic', 0.0)):.4f}",
            ratio="n/a" if row.get("mean_train_test_ratio") is None else f"{float(row.get('mean_train_test_ratio')):.4f}",
            band=row.get("stability_band", "unknown"),
            action=row.get("next_action", ""),
        ),
    ]
    unstable = list(row.get("most_unstable_features", []) or [])
    if unstable:
        preview = ", ".join(
            f"{item.get('feature')} ({safe_float(item.get('mean_importance_cv', 0.0)):.2f})"
            for item in unstable[:5]
        )
        lines.extend(["", f"- Most unstable features: {preview}"])
    return "\n".join(lines) + "\n"


def _print_discovery(discovery: dict[str, Any]) -> None:
    print(f"Experiment: {discovery.get('experiment_dir')}")
    print("Transformer artifact search:")
    for root in list(discovery.get("existing_search_roots", []) or []):
        print(f"  root: {root}")
    for seed_file in list(discovery.get("seed_files", []) or []):
        print(f"  seed_file: {seed_file}")
    for ref_dir in list(discovery.get("referenced_artifact_dirs", []) or []):
        print(f"  referenced_dir: {ref_dir}")
    files = list(discovery.get("window_bundle_files", []) or [])
    if files:
        preview = files[:10]
        for path in preview:
            print(f"  bundle: {path}")
        if len(files) > len(preview):
            print(f"  bundle: ... ({len(files) - len(preview)} more)")


def _build_report(
    *,
    experiment_dir: Path,
    output_dir: Path,
    discovery: dict[str, Any],
    ratio: float | None,
    stable_threshold: float,
    mixed_threshold: float,
    method: str,
    permutation_max_features: int,
    row: dict[str, Any],
    artifact_status: str,
    overall_recommendation: str,
) -> dict[str, Any]:
    return {
        "created_at": _utc_now(),
        "experiment_dir": str(experiment_dir),
        "output_dir": str(output_dir),
        "artifact_status": artifact_status,
        "stable_threshold": float(stable_threshold),
        "mixed_threshold": float(mixed_threshold),
        "method": str(method),
        "permutation_max_features": int(permutation_max_features),
        "artifact_discovery": discovery,
        "overall_recommendation": overall_recommendation,
        "models": [
            {
                **row,
                "mean_train_test_ratio": (float(ratio) if ratio is not None and np.isfinite(float(ratio)) else None),
            }
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze Transformer stability from saved Day 3 / Day 3B window bundles")
    parser.add_argument("--experiment-dir", required=True, help="Path to a Day 3 or Day 3B experiment directory")
    parser.add_argument("--output-dir", default=None, help="Defaults to <experiment-dir>/feature_stability")
    parser.add_argument("--method", choices=["auto", "permutation", "gradient"], default="auto")
    parser.add_argument("--top-k", type=int, default=15)
    parser.add_argument("--stable-threshold", type=float, default=0.70)
    parser.add_argument("--mixed-threshold", type=float, default=0.40)
    parser.add_argument("--permutation-max-features", type=int, default=64)
    args = parser.parse_args()

    experiment_dir = Path(str(args.experiment_dir)).expanduser().resolve()
    output_dir = Path(str(args.output_dir)).expanduser().resolve() if args.output_dir else experiment_dir / "feature_stability"
    output_dir.mkdir(parents=True, exist_ok=True)

    discovery = discover_transformer_artifacts(experiment_dir)
    _print_discovery(discovery)
    ratio = resolve_transformer_ratio(experiment_dir)

    seed_files = [Path(path) for path in list(discovery.get("seed_files", []) or [])]
    if not seed_files:
        band = "unknown"
        next_action = "No stability result available because no valid Transformer window bundles were found."
        row = {
            "model": "transformer",
            "seed_count": 0,
            "analyzed_seed_count": 0,
            "mean_pairwise_rank_correlation": None,
            "mean_top_feature_jaccard": None,
            "mean_test_ic": 0.0,
            "stability_band": band,
            "tree_compatible_stability_band": "unknown",
            "next_action": next_action,
            "most_unstable_features": [],
            "top_features_by_mean_importance": [],
            "seed_reports": [],
        }
        report = _build_report(
            experiment_dir=experiment_dir,
            output_dir=output_dir,
            discovery=discovery,
            ratio=ratio,
            stable_threshold=float(args.stable_threshold),
            mixed_threshold=float(args.mixed_threshold),
            method=str(args.method),
            permutation_max_features=int(args.permutation_max_features),
            row=row,
            artifact_status="missing_transformer_seed_results",
            overall_recommendation=next_action,
        )
        _write_json(output_dir / "transformer_stability_report.json", report)
        _write_text(output_dir / "transformer_stability_report.md", _render_md(report))
        ratio_txt = "n/a" if ratio is None or not np.isfinite(float(ratio)) else f"{float(ratio):.4f}"
        print(f"   transformer: corr=n/a ratio={ratio_txt} band={band} action={next_action}")
        print(
            "Transformer analysis could not proceed: no transformer seed results were found. "
            f"Looked under {experiment_dir / 'seed_results'} and transformer-specific artifact roots."
        )
        return 2

    seed_reports: list[dict[str, Any]] = []
    for seed_file in seed_files:
        try:
            payload = json.loads(seed_file.read_text(encoding="utf-8"))
        except Exception as exc:
            seed_reports.append(
                {
                    "seed_file": str(seed_file),
                    "status": "unreadable_seed_file",
                    "reason": str(exc),
                }
            )
            continue
        seed_summary = dict(payload.get("seed_summary", {}) or {})
        window_paths = []
        raw_dir = str(payload.get("window_artifact_dir", "") or "").strip()
        if raw_dir:
            bundle_dir = Path(raw_dir).expanduser().resolve()
            if bundle_dir.exists():
                window_paths.extend(sorted(bundle_dir.glob("window_*.pt")))
        full_result = dict(payload.get("full_result", {}) or {})
        for window in list(full_result.get("windows", []) or []):
            raw_path = str(window.get("artifact_path", "") or "").strip()
            if raw_path:
                artifact_path = Path(raw_path).expanduser().resolve()
                if artifact_path.exists():
                    window_paths.append(artifact_path)
        window_paths = sorted({path.resolve() for path in window_paths})
        if not window_paths:
            seed_reports.append(
                {
                    "seed_file": str(seed_file),
                    "seed": int(seed_summary.get("seed", 0)),
                    "status": "missing_window_artifacts",
                    "reason": (
                        "Transformer seed result exists, but no saved window bundles were found. "
                        f"Looked for {raw_dir or (experiment_dir / 'window_artifacts' / 'transformer')}"
                    ),
                    "seed_summary": seed_summary,
                }
            )
            continue
        try:
            stability = compute_seed_transformer_stability(
                [str(path) for path in window_paths],
                method=str(args.method),
                top_k=int(args.top_k),
                permutation_max_features=int(args.permutation_max_features),
                random_state=int(seed_summary.get("seed", 42) or 42),
            )
            seed_reports.append(
                {
                    "seed_file": str(seed_file),
                    "seed": int(seed_summary.get("seed", 0)),
                    "status": str(stability.get("status", "unknown")),
                    "seed_summary": seed_summary,
                    "feature_stability": stability,
                    "window_bundle_files": [str(path) for path in window_paths],
                }
            )
        except Exception as exc:
            seed_reports.append(
                {
                    "seed_file": str(seed_file),
                    "seed": int(seed_summary.get("seed", 0)),
                    "status": "analysis_failed",
                    "reason": str(exc),
                    "seed_summary": seed_summary,
                    "window_bundle_files": [str(path) for path in window_paths],
                }
            )

    ok_reports = [
        dict(row.get("feature_stability", {}) or {})
        for row in seed_reports
        if str(row.get("status", "")).lower() == "ok"
    ]
    mean_corr = _mean_ok(ok_reports, "mean_pairwise_rank_correlation")
    mean_jaccard = _mean_ok(ok_reports, "mean_top_feature_jaccard")
    band, tree_band, next_action = _band_and_action(
        mean_corr,
        stable_threshold=float(args.stable_threshold),
        mixed_threshold=float(args.mixed_threshold),
    )

    row = {
        "model": "transformer",
        "seed_count": int(len(seed_reports)),
        "analyzed_seed_count": int(len(ok_reports)),
        "mean_pairwise_rank_correlation": mean_corr,
        "mean_top_feature_jaccard": mean_jaccard,
        "mean_test_ic": float(
            np.mean(
                [
                    safe_float(dict(row.get("seed_summary", {}) or {}).get("mean_ic", 0.0))
                    for row in seed_reports
                    if isinstance(row, dict)
                ]
            )
        ) if seed_reports else 0.0,
        "mean_train_test_ratio": (float(ratio) if ratio is not None and np.isfinite(float(ratio)) else None),
        "stability_band": band,
        "tree_compatible_stability_band": tree_band,
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
        "seed_reports": seed_reports,
    }

    report = _build_report(
        experiment_dir=experiment_dir,
        output_dir=output_dir,
        discovery=discovery,
        ratio=ratio,
        stable_threshold=float(args.stable_threshold),
        mixed_threshold=float(args.mixed_threshold),
        method=str(args.method),
        permutation_max_features=int(args.permutation_max_features),
        row=row,
        artifact_status=("ok" if ok_reports else "missing_required_transformer_artifacts"),
        overall_recommendation=next_action,
    )
    _write_json(output_dir / "transformer_stability_report.json", report)
    _write_text(output_dir / "transformer_stability_report.md", _render_md(report))

    corr_txt = "n/a" if mean_corr is None else f"{float(mean_corr):.4f}"
    ratio_txt = "n/a" if ratio is None or not np.isfinite(float(ratio)) else f"{float(ratio):.4f}"
    print(f"   transformer: corr={corr_txt} ratio={ratio_txt} band={band} action={next_action}")

    if not ok_reports:
        print(
            "Transformer analysis could not proceed because the run does not contain saved per-window Transformer bundles. "
            "Rerun the Transformer candidate with the upgraded runner so it writes window artifacts under "
            f"{experiment_dir / 'window_artifacts' / 'transformer'}."
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
