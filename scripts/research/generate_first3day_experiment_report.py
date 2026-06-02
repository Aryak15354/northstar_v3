#!/usr/bin/env python3
"""Generate a detailed report for the runnable first-three-day research experiments."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[2]
WEEK_ROOT = PROJECT_ROOT / "data/results/research/experiments/week_2026_03_22"

DEFAULT_DAY2_ROOT = WEEK_ROOT / "day2_clean_baseline"
DEFAULT_DAY2B_ROOT = WEEK_ROOT / "day2b_centering_patch"
DEFAULT_DAY3_ROOT = WEEK_ROOT / "day3_model_comparison"
DEFAULT_DAY3B_ROOT = WEEK_ROOT / "day3b_tighter_regularization"
DEFAULT_DAY3C_ROOT = WEEK_ROOT / "day3c_feature_updated_baseline"

DEFAULT_REPORT_MD = WEEK_ROOT / "first3day_experiment_report.md"
DEFAULT_REPORT_JSON = WEEK_ROOT / "first3day_experiment_report.json"

MODEL_STAGE_ORDER = ["xgboost", "catboost", "lstm", "tcn", "transformer"]
TREE_MODEL_ORDER = ["xgboost", "catboost"]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_float(value: Any, default: float = np.nan) -> float:
    try:
        out = float(value)
    except Exception:
        return float(default)
    if not np.isfinite(out):
        return float(default)
    return float(out)


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"invalid_json_object:{path}")
    return payload


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _format_decimal(value: Any, digits: int = 4) -> str:
    v = _safe_float(value, np.nan)
    return "n/a" if not np.isfinite(v) else f"{v:.{digits}f}"


def _format_number(value: Any, digits: int = 2) -> str:
    v = _safe_float(value, np.nan)
    return "n/a" if not np.isfinite(v) else f"{v:.{digits}f}"


def _format_pct(value: Any, digits: int = 2) -> str:
    v = _safe_float(value, np.nan)
    return "n/a" if not np.isfinite(v) else f"{v * 100.0:.{digits}f}%"


def _format_exposure(value: Any, digits: int = 2) -> str:
    v = _safe_float(value, np.nan)
    if not np.isfinite(v):
        return "n/a"
    if abs(v) <= 1.5:
        return f"{v * 100.0:.{digits}f}%"
    return f"{v:.{digits}f}%"


def _format_ratio(value: Any, digits: int = 2) -> str:
    v = _safe_float(value, np.nan)
    return "n/a" if not np.isfinite(v) else f"{v:.{digits}f}x"


def _format_path(path: Path | None) -> str:
    if path is None:
        return "`not found`"
    return f"`{path}`"


def _stage_link(label: str, path: Path | None) -> str:
    if path is None:
        return f"{label}: `not found`"
    return f"{label}: [{path.name}]({path})"


def _latest_child_with_file(root: Path, filename: str) -> Path | None:
    if not root.exists():
        return None
    candidates = [child for child in root.iterdir() if child.is_dir() and (child / filename).exists()]
    if not candidates:
        return None
    candidates.sort(key=lambda path: (path.name, path.stat().st_mtime), reverse=True)
    return candidates[0]


def _resolve_day3c_root(explicit: str | None) -> Path | None:
    if explicit:
        path = Path(explicit).expanduser().resolve()
        return path if (path / "comparison.json").exists() else None
    if (DEFAULT_DAY3C_ROOT / "comparison.json").exists():
        return DEFAULT_DAY3C_ROOT
    return None


def _resolve_stage_dir(explicit: str | None, default_root: Path, required_file: str) -> Path | None:
    if explicit:
        path = Path(explicit).expanduser().resolve()
        return path if (path / required_file).exists() else None
    return _latest_child_with_file(default_root, required_file)


def _mean_exposure_by_model(experiment_dir: Path | None) -> dict[str, float]:
    if experiment_dir is None:
        return {}
    seed_dir = experiment_dir / "seed_results"
    if not seed_dir.exists():
        return {}
    exposures: dict[str, list[float]] = {}
    for seed_path in sorted(seed_dir.glob("*_seed_*.json")):
        payload = _load_json(seed_path)
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


def _collect_model_rows(summary: dict[str, Any], experiment_dir: Path | None) -> dict[str, dict[str, Any]]:
    rows = {
        str(row.get("model", "")).strip().lower(): dict(row)
        for row in list(summary.get("model_comparison", []) or [])
        if str(row.get("model", "")).strip()
    }
    for model_name, exposure in _mean_exposure_by_model(experiment_dir).items():
        rows.setdefault(model_name, {})
        rows[model_name]["mean_exposure"] = float(exposure)
    return rows


def _extract_preflight(summary: dict[str, Any], experiment_dir: Path | None) -> dict[str, Any]:
    inline = summary.get("preflight_report")
    if isinstance(inline, dict) and inline:
        return dict(inline)
    if experiment_dir is not None:
        path = experiment_dir / "preflight_report.json"
        if path.exists():
            return _load_json(path)
    return {}


def _best_model_by_mean_ic(rows: dict[str, dict[str, Any]]) -> tuple[str, dict[str, Any]] | None:
    ranked = [
        (model_name, row)
        for model_name, row in rows.items()
        if np.isfinite(_safe_float(row.get("mean_ic", np.nan), np.nan))
    ]
    if not ranked:
        return None
    ranked.sort(key=lambda item: _safe_float(item[1].get("mean_ic", -999.0), -999.0), reverse=True)
    return ranked[0]


def _best_model_by_ratio(rows: dict[str, dict[str, Any]]) -> tuple[str, dict[str, Any]] | None:
    ranked = [
        (model_name, row)
        for model_name, row in rows.items()
        if np.isfinite(_safe_float(row.get("train_test_ratio", np.nan), np.nan))
    ]
    if not ranked:
        return None
    ranked.sort(key=lambda item: _safe_float(item[1].get("train_test_ratio", float("inf")), float("inf")))
    return ranked[0]


def _build_day2_payload(experiment_dir: Path | None) -> dict[str, Any]:
    if experiment_dir is None:
        return {"status": "missing"}
    summary_path = experiment_dir / "summary.json"
    if not summary_path.exists():
        return {"status": "missing", "experiment_dir": str(experiment_dir)}
    summary = _load_json(summary_path)
    window_rows = list(summary.get("window_results", []) or [])
    weakest_windows = sorted(
        [
            {
                "window_id": row.get("window_id"),
                "mean_exposure": _safe_float(row.get("mean_exposure", np.nan), np.nan),
                "total_return": _safe_float(row.get("total_return", np.nan), np.nan),
                "sharpe": _safe_float(row.get("sharpe", np.nan), np.nan),
            }
            for row in window_rows
            if isinstance(row, dict)
        ],
        key=lambda row: row["mean_exposure"] if np.isfinite(row["mean_exposure"]) else float("inf"),
    )[:3]
    return {
        "status": "ok",
        "experiment_dir": str(experiment_dir),
        "summary_path": str(summary_path),
        "resolved_model": summary.get("resolved_model"),
        "governor_standard": summary.get("governor_standard"),
        "windows_processed": summary.get("windows_processed"),
        "metrics": dict(summary.get("metrics", {}) or {}),
        "comparison_against_prior": dict(summary.get("comparison_against_prior", {}) or {}),
        "verdict": summary.get("verdict"),
        "weakest_windows": weakest_windows,
    }


def _build_day2b_payload(experiment_dir: Path | None) -> dict[str, Any]:
    if experiment_dir is None:
        return {"status": "missing"}
    comparison_path = experiment_dir / "comparison.json"
    summary_path = experiment_dir / "summary.json"
    if not comparison_path.exists():
        return {"status": "missing", "experiment_dir": str(experiment_dir)}
    comparison = _load_json(comparison_path)
    summary = _load_json(summary_path) if summary_path.exists() else {}
    return {
        "status": "ok",
        "experiment_dir": str(experiment_dir),
        "comparison_path": str(comparison_path),
        "summary_path": str(summary_path) if summary_path.exists() else None,
        "resolved_model": comparison.get("resolved_model") or summary.get("resolved_model"),
        "metrics": dict((comparison.get("summary", {}) or {}).get("metrics", {}) or {}),
        "window_comparison": list(comparison.get("window_comparison", []) or []),
        "min_window_exposure_patched": comparison.get("min_window_exposure_patched"),
        "pass_threshold_exposure": comparison.get("pass_threshold_exposure"),
        "verdict": comparison.get("verdict"),
    }


def _build_day3_stage_payload(stage_name: str, experiment_dir: Path | None) -> dict[str, Any]:
    if experiment_dir is None:
        return {"status": "missing", "stage_name": stage_name}
    summary_path = experiment_dir / "summary.json"
    if not summary_path.exists():
        return {"status": "missing", "stage_name": stage_name, "experiment_dir": str(experiment_dir)}
    summary = _load_json(summary_path)
    preflight = _extract_preflight(summary, experiment_dir)
    rows = _collect_model_rows(summary, experiment_dir)
    best_ic = _best_model_by_mean_ic(rows)
    best_ratio = _best_model_by_ratio(rows)
    return {
        "status": "ok",
        "stage_name": stage_name,
        "experiment_dir": str(experiment_dir),
        "summary_path": str(summary_path),
        "preflight_report_path": str(experiment_dir / "preflight_report.json") if (experiment_dir / "preflight_report.json").exists() else None,
        "resource_profile": summary.get("resource_profile"),
        "smoke": summary.get("smoke"),
        "decision": dict(summary.get("decision", {}) or {}),
        "preflight_report": preflight,
        "model_rows": rows,
        "best_by_mean_ic": {
            "model": best_ic[0],
            "mean_ic": best_ic[1].get("mean_ic"),
            "train_test_ratio": best_ic[1].get("train_test_ratio"),
        } if best_ic else None,
        "best_by_train_test_ratio": {
            "model": best_ratio[0],
            "mean_ic": best_ratio[1].get("mean_ic"),
            "train_test_ratio": best_ratio[1].get("train_test_ratio"),
        } if best_ratio else None,
    }


def _build_day3b_delta(day3_payload: dict[str, Any], day3b_dir: Path | None) -> list[dict[str, Any]]:
    if day3b_dir is None:
        return []
    comparison_path = day3b_dir / "comparison_against_day3.json"
    if comparison_path.exists():
        payload = _load_json(comparison_path)
        rows = list(payload.get("comparison", []) or [])
        return [dict(row) for row in rows if isinstance(row, dict)]

    prior_rows = dict(day3_payload.get("model_rows", {}) or {})
    current_rows = dict(_build_day3_stage_payload("day3b", day3b_dir).get("model_rows", {}) or {})
    out: list[dict[str, Any]] = []
    for model_name in TREE_MODEL_ORDER:
        prior = dict(prior_rows.get(model_name, {}) or {})
        current = dict(current_rows.get(model_name, {}) or {})
        if not prior or not current:
            continue
        out.append(
            {
                "model": model_name,
                "day3_mean_ic": prior.get("mean_ic"),
                "day3b_mean_ic": current.get("mean_ic"),
                "mean_ic_change": _safe_float(current.get("mean_ic", np.nan), np.nan) - _safe_float(prior.get("mean_ic", np.nan), np.nan),
                "day3_ic_ir": prior.get("ic_ir"),
                "day3b_ic_ir": current.get("ic_ir"),
                "ic_ir_change": _safe_float(current.get("ic_ir", np.nan), np.nan) - _safe_float(prior.get("ic_ir", np.nan), np.nan),
                "day3_train_test_ratio": prior.get("train_test_ratio"),
                "day3b_train_test_ratio": current.get("train_test_ratio"),
                "ratio_change": _safe_float(current.get("train_test_ratio", np.nan), np.nan) - _safe_float(prior.get("train_test_ratio", np.nan), np.nan),
                "day3_turnover": prior.get("turnover"),
                "day3b_turnover": current.get("turnover"),
                "turnover_change": _safe_float(current.get("turnover", np.nan), np.nan) - _safe_float(prior.get("turnover", np.nan), np.nan),
            }
        )
    return out


def _build_day3c_payload(root_dir: Path | None) -> dict[str, Any]:
    if root_dir is None:
        return {"status": "pending"}
    comparison_path = root_dir / "comparison.json"
    if not comparison_path.exists():
        return {"status": "pending", "experiment_dir": str(root_dir)}
    comparison = _load_json(comparison_path)
    run_a_dir = root_dir / "run_a_full_sentiment"
    run_b_dir = root_dir / "run_b_reduced_sentiment"
    run_a = _build_day3_stage_payload("day3c_run_a_full_sentiment", run_a_dir if run_a_dir.exists() else None)
    run_b = _build_day3_stage_payload("day3c_run_b_reduced_sentiment", run_b_dir if run_b_dir.exists() else None)
    return {
        "status": "ok",
        "experiment_dir": str(root_dir),
        "comparison_path": str(comparison_path),
        "comparison": comparison,
        "run_a": run_a,
        "run_b": run_b,
    }


def _render_artifact_inventory(resolved: dict[str, Path | None]) -> list[str]:
    return [
        "## Artifact Inventory",
        "",
        f"- {_stage_link('Day 2 clean baseline', resolved.get('day2'))}",
        f"- {_stage_link('Day 2B centering patch', resolved.get('day2b'))}",
        f"- {_stage_link('Day 3 model comparison', resolved.get('day3'))}",
        f"- {_stage_link('Day 3B tighter regularization', resolved.get('day3b'))}",
        f"- {_stage_link('Day 3C feature-updated baseline', resolved.get('day3c'))}",
        "",
        "Note: the repository does not expose a standalone Day 1 experiment runner, so this report starts from the first runnable research stage already captured in the experiment stack.",
        "",
    ]


def _render_day2_section(day2: dict[str, Any]) -> list[str]:
    lines = ["## Day 2 Clean Baseline", ""]
    if day2.get("status") != "ok":
        lines.extend(["Day 2 artifacts were not found.", ""])
        return lines
    metrics = dict(day2.get("metrics", {}) or {})
    prior = dict(day2.get("comparison_against_prior", {}) or {})
    lines.extend(
        [
            f"- Experiment dir: `{day2['experiment_dir']}`",
            f"- Resolved model: `{day2.get('resolved_model')}`",
            f"- Governor standard: `{day2.get('governor_standard')}`",
            f"- Windows processed: `{day2.get('windows_processed')}`",
            f"- Verdict: `{day2.get('verdict')}`",
            "",
            "| Metric | Day 2 result | Prior baseline | Delta |",
            "|---|---:|---:|---:|",
            f"| Mean return | {_format_number(metrics.get('mean_return'))}% | {_format_number((prior.get('mean_return') or {}).get('prior'))}% | {_format_number((prior.get('mean_return') or {}).get('change'))}% |",
            f"| Return std | {_format_number(metrics.get('return_std'))} | {_format_number((prior.get('return_std') or {}).get('prior'))} | {_format_number((prior.get('return_std') or {}).get('change'))} |",
            f"| Mean Sharpe | {_format_number(metrics.get('mean_sharpe'))} | {_format_number((prior.get('mean_sharpe') or {}).get('prior'))} | {_format_number((prior.get('mean_sharpe') or {}).get('change'))} |",
            f"| Mean drawdown | {_format_number(metrics.get('mean_drawdown'))}% | {_format_number((prior.get('mean_drawdown') or {}).get('prior'))}% | {_format_number((prior.get('mean_drawdown') or {}).get('change'))}% |",
            f"| Mean exposure | {_format_exposure(metrics.get('mean_exposure'))} | {_format_exposure((prior.get('mean_exposure') or {}).get('prior'))} | {_format_exposure((prior.get('mean_exposure') or {}).get('change'))} |",
            f"| Violations | {_format_number(metrics.get('violations'), 0)} | {_format_number((prior.get('violations') or {}).get('prior'), 0)} | {_format_number((prior.get('violations') or {}).get('change'), 0)} |",
            "",
            "Weakest windows by mean exposure:",
            "",
            "| Window | Mean exposure | Total return | Sharpe |",
            "|---|---:|---:|---:|",
        ]
    )
    for row in list(day2.get("weakest_windows", []) or []):
        lines.append(
            f"| {row.get('window_id', 'n/a')} | {_format_exposure(row.get('mean_exposure'))} | {_format_number(row.get('total_return'))}% | {_format_number(row.get('sharpe'))} |"
        )
    lines.append("")
    return lines


def _render_day2b_section(day2b: dict[str, Any]) -> list[str]:
    lines = ["## Day 2B Centering Patch", ""]
    if day2b.get("status") != "ok":
        lines.extend(["Day 2B artifacts were not found.", ""])
        return lines
    metrics = dict(day2b.get("metrics", {}) or {})
    lines.extend(
        [
            f"- Experiment dir: `{day2b['experiment_dir']}`",
            f"- Resolved model: `{day2b.get('resolved_model')}`",
            f"- Minimum patched window exposure: {_format_exposure(day2b.get('min_window_exposure_patched'))}",
            f"- Pass threshold exposure: {_format_exposure(day2b.get('pass_threshold_exposure'))}",
            f"- Verdict: `{day2b.get('verdict')}`",
            "",
            "| Metric | Day 2B result |",
            "|---|---:|",
            f"| Mean return | {_format_number(metrics.get('mean_return'))}% |",
            f"| Return std | {_format_number(metrics.get('return_std'))} |",
            f"| Mean Sharpe | {_format_number(metrics.get('mean_sharpe'))} |",
            f"| Mean drawdown | {_format_number(metrics.get('mean_drawdown'))}% |",
            f"| Mean exposure | {_format_exposure(metrics.get('mean_exposure'))} |",
            f"| Violations | {_format_number(metrics.get('violations'), 0)} |",
            "",
            "Restored dead-window comparison:",
            "",
            "| Window | Prior exposure | Patched exposure | Exposure delta | Prior return | Patched return | Prior Sharpe | Patched Sharpe |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in list(day2b.get("window_comparison", []) or []):
        lines.append(
            "| {window} | {prior_exp} | {patched_exp} | {delta_exp} | {prior_ret} | {patched_ret} | {prior_sharpe} | {patched_sharpe} |".format(
                window=row.get("window_id", "n/a"),
                prior_exp=_format_exposure(row.get("mean_exposure_prior")),
                patched_exp=_format_exposure(row.get("mean_exposure_patched")),
                delta_exp=_format_exposure(row.get("exposure_change")),
                prior_ret=_format_number(row.get("total_return_prior")) + "%",
                patched_ret=_format_number(row.get("total_return_patched")) + "%",
                prior_sharpe=_format_number(row.get("sharpe_prior")),
                patched_sharpe=_format_number(row.get("sharpe_patched")),
            )
        )
    lines.append("")
    return lines


def _render_model_table(title: str, rows: dict[str, dict[str, Any]], model_order: list[str] | None = None) -> list[str]:
    ordered = model_order or MODEL_STAGE_ORDER
    lines = [
        title,
        "",
        "| Model | Mean IC | IC IR | Hit rate | Train/test ratio | Turnover | Mean exposure | Avg Sharpe | Avg max DD | Runtime (s) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for model_name in ordered:
        row = dict(rows.get(model_name, {}) or {})
        if not row:
            continue
        lines.append(
            "| {model} | {mean_ic} | {ic_ir} | {hit_rate} | {ratio} | {turnover} | {exposure} | {sharpe} | {drawdown} | {runtime} |".format(
                model=model_name,
                mean_ic=_format_decimal(row.get("mean_ic")),
                ic_ir=_format_decimal(row.get("ic_ir")),
                hit_rate=_format_pct(row.get("hit_rate")),
                ratio=_format_ratio(row.get("train_test_ratio")),
                turnover=_format_decimal(row.get("turnover")),
                exposure=_format_exposure(row.get("mean_exposure")),
                sharpe=_format_decimal(row.get("avg_sharpe")),
                drawdown=_format_decimal(row.get("avg_max_drawdown")),
                runtime=_format_number(row.get("runtime_seconds")),
            )
        )
    lines.append("")
    return lines


def _render_preflight_block(preflight: dict[str, Any]) -> list[str]:
    dataset = dict(preflight.get("dataset", {}) or {})
    walk = dict(preflight.get("walk_forward", {}) or {})
    libraries = dict(preflight.get("libraries", {}) or {})
    return [
        "- Dataset rows: `{}`".format(dataset.get("n_rows", "n/a")),
        "- Tickers: `{}`".format(dataset.get("n_tickers", "n/a")),
        "- Features before IC prune: `{}`".format(dataset.get("n_features_before_ic_prune", "n/a")),
        "- Features after IC prune: `{}`".format(dataset.get("n_features_after_ic_prune", "n/a")),
        "- Eligible dates: `{}`".format(dataset.get("eligible_dates", "n/a")),
        "- Date span: `{}` to `{}`".format(dataset.get("start_date", "n/a"), dataset.get("end_date", "n/a")),
        "- Walk-forward windows: requested `{}`, available `{}`".format(walk.get("requested_windows", "n/a"), walk.get("available_windows", "n/a")),
        "- Train/valid/test periods: `{}` / `{}` / `{}`".format(walk.get("train_periods", "n/a"), walk.get("valid_periods", "n/a"), walk.get("test_periods", "n/a")),
        "- Library availability: XGBoost=`{}`, CatBoost=`{}`, Torch=`{}`".format(libraries.get("xgboost", "n/a"), libraries.get("catboost", "n/a"), libraries.get("torch", "n/a")),
    ]


def _render_day3_section(day3: dict[str, Any]) -> list[str]:
    lines = ["## Day 3 Model Comparison", ""]
    if day3.get("status") != "ok":
        lines.extend(["Day 3 artifacts were not found.", ""])
        return lines
    decision = dict(day3.get("decision", {}) or {})
    lines.extend(
        [
            f"- Experiment dir: `{day3['experiment_dir']}`",
            f"- Resource profile: `{day3.get('resource_profile')}`",
            f"- Decision reason: `{decision.get('reason')}`",
            f"- Selected model: `{decision.get('selected_model')}`",
            "",
            "Preflight snapshot:",
        ]
    )
    lines.extend(_render_preflight_block(dict(day3.get("preflight_report", {}) or {})))
    lines.append("")
    lines.extend(_render_model_table("Model comparison:", dict(day3.get("model_rows", {}) or {})))
    best_ic = dict(day3.get("best_by_mean_ic", {}) or {})
    best_ratio = dict(day3.get("best_by_train_test_ratio", {}) or {})
    if best_ic:
        lines.append(
            "Best mean IC on Day 3 was `{}` at {} with train/test ratio {}.".format(
                best_ic.get("model"),
                _format_decimal(best_ic.get("mean_ic")),
                _format_ratio(best_ic.get("train_test_ratio")),
            )
        )
    if best_ratio:
        lines.append(
            "Best train/test ratio on Day 3 was `{}` at {}, with mean IC {}.".format(
                best_ratio.get("model"),
                _format_ratio(best_ratio.get("train_test_ratio")),
                _format_decimal(best_ratio.get("mean_ic")),
            )
        )
    lines.append("")
    return lines


def _render_day3b_section(day3b: dict[str, Any], day3b_delta: list[dict[str, Any]]) -> list[str]:
    lines = ["## Day 3B Tighter Regularization", ""]
    if day3b.get("status") != "ok":
        lines.extend(["Day 3B artifacts were not found.", ""])
        return lines
    decision = dict(day3b.get("decision", {}) or {})
    lines.extend(
        [
            f"- Experiment dir: `{day3b['experiment_dir']}`",
            f"- Resource profile: `{day3b.get('resource_profile')}`",
            f"- Decision reason: `{decision.get('reason')}`",
            f"- Selected model: `{decision.get('selected_model')}`",
            "",
            "Preflight snapshot:",
        ]
    )
    lines.extend(_render_preflight_block(dict(day3b.get("preflight_report", {}) or {})))
    lines.append("")
    lines.extend(_render_model_table("Model comparison:", dict(day3b.get("model_rows", {}) or {})))
    lines.extend(
        [
            "Comparison versus Day 3:",
            "",
            "| Model | Day 3 mean IC | Day 3B mean IC | Delta IC | Day 3 IC IR | Day 3B IC IR | Delta IR | Day 3 ratio | Day 3B ratio | Delta ratio |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in day3b_delta:
        lines.append(
            "| {model} | {d3_ic} | {d3b_ic} | {delta_ic} | {d3_ir} | {d3b_ir} | {delta_ir} | {d3_ratio} | {d3b_ratio} | {delta_ratio} |".format(
                model=row.get("model", "n/a"),
                d3_ic=_format_decimal(row.get("day3_mean_ic")),
                d3b_ic=_format_decimal(row.get("day3b_mean_ic")),
                delta_ic=_format_decimal(row.get("mean_ic_change")),
                d3_ir=_format_decimal(row.get("day3_ic_ir")),
                d3b_ir=_format_decimal(row.get("day3b_ic_ir")),
                delta_ir=_format_decimal(row.get("ic_ir_change")),
                d3_ratio=_format_ratio(row.get("day3_train_test_ratio")),
                d3b_ratio=_format_ratio(row.get("day3b_train_test_ratio")),
                delta_ratio=_format_decimal(row.get("ratio_change")),
            )
        )
    lines.append("")
    return lines


def _render_day3c_section(day3c: dict[str, Any]) -> list[str]:
    lines = ["## Day 3C Feature-Updated Baseline", ""]
    if day3c.get("status") != "ok":
        lines.extend(
            [
                "Day 3C artifacts are not present yet. This section will populate automatically after `run_day3c_feature_updated_baseline.py` completes.",
                "",
            ]
        )
        return lines
    comparison = dict(day3c.get("comparison", {}) or {})
    recommended = dict(comparison.get("recommended_config", {}) or {})
    interpretation = dict(comparison.get("interpretation", {}) or {})
    gate = dict(comparison.get("decision_gate", {}) or {})
    lines.extend(
        [
            f"- Experiment dir: `{day3c['experiment_dir']}`",
            f"- Recommended config: `{recommended.get('name')}`",
            f"- Recommendation rationale: {recommended.get('rationale', 'n/a')}",
            f"- Decision gate verdict: `{gate.get('verdict')}`",
            f"- Recommended next step: {gate.get('recommended_next_step', 'n/a')}",
            "",
            "Interpretation:",
            "",
            f"- {interpretation.get('gap9_effect', 'n/a')}",
            f"- {interpretation.get('sentiment_effect', 'n/a')}",
            "",
        ]
    )
    run_a = dict(day3c.get("run_a", {}) or {})
    run_b = dict(day3c.get("run_b", {}) or {})
    if run_a.get("status") == "ok":
        lines.extend(
            [
                "Run A preflight:",
            ]
        )
        lines.extend(_render_preflight_block(dict(run_a.get("preflight_report", {}) or {})))
        lines.append("")
        lines.extend(_render_model_table("Run A full sentiment:", dict(run_a.get("model_rows", {}) or {}), TREE_MODEL_ORDER))
    if run_b.get("status") == "ok":
        lines.extend(
            [
                "Run B preflight:",
            ]
        )
        lines.extend(_render_preflight_block(dict(run_b.get("preflight_report", {}) or {})))
        lines.append("")
        lines.extend(_render_model_table("Run B reduced sentiment:", dict(run_b.get("model_rows", {}) or {}), TREE_MODEL_ORDER))

    stability = dict(comparison.get("stability_report", {}) or {})
    model_rows = list(stability.get("models", []) or [])
    lines.extend(
        [
            "Reduced-sentiment stability analysis:",
            "",
            f"- Overall recommendation: `{stability.get('overall_recommendation', 'n/a')}`",
            "",
            "| Model | Mean pairwise corr | Mean top-k Jaccard | Mean test IC | Mean train/test ratio | Stability band | Action |",
            "|---|---:|---:|---:|---:|---|---|",
        ]
    )
    for row in model_rows:
        lines.append(
            "| {model} | {corr} | {jaccard} | {test_ic} | {ratio} | {band} | {action} |".format(
                model=row.get("model", "n/a"),
                corr=_format_decimal(row.get("mean_pairwise_rank_correlation")),
                jaccard=_format_decimal(row.get("mean_top_feature_jaccard")),
                test_ic=_format_decimal(row.get("mean_test_ic")),
                ratio=_format_ratio(row.get("mean_train_test_ratio")),
                band=row.get("stability_band", "n/a"),
                action=row.get("next_action", "n/a"),
            )
        )
    lines.extend(
        [
            "",
            "Recommended config JSON:",
            "",
            "```json",
            json.dumps({"recommended_config": recommended}, indent=2),
            "```",
            "",
        ]
    )
    return lines


def _render_cross_stage_section(
    day2: dict[str, Any],
    day2b: dict[str, Any],
    day3: dict[str, Any],
    day3b: dict[str, Any],
    day3c: dict[str, Any],
) -> list[str]:
    lines = ["## Cross-Stage Progression", ""]

    day2_metrics = dict(day2.get("metrics", {}) or {})
    day2b_metrics = dict(day2b.get("metrics", {}) or {})
    lines.extend(
        [
            "Exposure restoration path:",
            "",
            "| Stage | Mean return | Mean Sharpe | Mean drawdown | Mean exposure | Verdict |",
            "|---|---:|---:|---:|---:|---|",
            f"| Day 2 | {_format_number(day2_metrics.get('mean_return'))}% | {_format_number(day2_metrics.get('mean_sharpe'))} | {_format_number(day2_metrics.get('mean_drawdown'))}% | {_format_exposure(day2_metrics.get('mean_exposure'))} | {day2.get('verdict', 'n/a')} |",
            f"| Day 2B | {_format_number(day2b_metrics.get('mean_return'))}% | {_format_number(day2b_metrics.get('mean_sharpe'))} | {_format_number(day2b_metrics.get('mean_drawdown'))}% | {_format_exposure(day2b_metrics.get('mean_exposure'))} | {day2b.get('verdict', 'n/a')} |",
            "",
            "Tree-model progression:",
            "",
            "| Stage | Model | Mean IC | IC IR | Hit rate | Train/test ratio | Turnover | Mean exposure |",
            "|---|---|---:|---:|---:|---:|---:|---:|",
        ]
    )

    tree_stage_rows: list[tuple[str, str, dict[str, Any]]] = []
    for stage_label, payload in [("Day 3", day3), ("Day 3B", day3b)]:
        rows = dict(payload.get("model_rows", {}) or {})
        for model_name in TREE_MODEL_ORDER:
            row = dict(rows.get(model_name, {}) or {})
            if row:
                tree_stage_rows.append((stage_label, model_name, row))

    if day3c.get("status") == "ok":
        for stage_label, payload in [
            ("Day 3C Run A", dict(day3c.get("run_a", {}) or {})),
            ("Day 3C Run B", dict(day3c.get("run_b", {}) or {})),
        ]:
            rows = dict(payload.get("model_rows", {}) or {})
            for model_name in TREE_MODEL_ORDER:
                row = dict(rows.get(model_name, {}) or {})
                if row:
                    tree_stage_rows.append((stage_label, model_name, row))

    for stage_label, model_name, row in tree_stage_rows:
        lines.append(
            "| {stage} | {model} | {mean_ic} | {ic_ir} | {hit_rate} | {ratio} | {turnover} | {exposure} |".format(
                stage=stage_label,
                model=model_name,
                mean_ic=_format_decimal(row.get("mean_ic")),
                ic_ir=_format_decimal(row.get("ic_ir")),
                hit_rate=_format_pct(row.get("hit_rate")),
                ratio=_format_ratio(row.get("train_test_ratio")),
                turnover=_format_decimal(row.get("turnover")),
                exposure=_format_exposure(row.get("mean_exposure")),
            )
        )

    lines.extend(
        [
            "",
            "Feature-matrix progression:",
            "",
            "| Stage | Features before prune | Features after prune | Tickers | Rows | CatBoost available | Sentiment mode |",
            "|---|---:|---:|---:|---:|---|---|",
        ]
    )

    def _feature_row(stage_label: str, payload: dict[str, Any], sentiment_mode: str) -> str:
        preflight = dict(payload.get("preflight_report", {}) or {})
        dataset = dict(preflight.get("dataset", {}) or {})
        libs = dict(preflight.get("libraries", {}) or {})
        return "| {stage} | {before} | {after} | {tickers} | {rows} | {catboost} | {sentiment} |".format(
            stage=stage_label,
            before=dataset.get("n_features_before_ic_prune", "n/a"),
            after=dataset.get("n_features_after_ic_prune", "n/a"),
            tickers=dataset.get("n_tickers", "n/a"),
            rows=dataset.get("n_rows", "n/a"),
            catboost=libs.get("catboost", "n/a"),
            sentiment=sentiment_mode,
        )

    if day3.get("status") == "ok":
        lines.append(_feature_row("Day 3", day3, "full"))
    if day3b.get("status") == "ok":
        lines.append(_feature_row("Day 3B", day3b, "full"))
    if day3c.get("status") == "ok":
        run_a = dict(day3c.get("run_a", {}) or {})
        run_b = dict(day3c.get("run_b", {}) or {})
        if run_a.get("status") == "ok":
            lines.append(_feature_row("Day 3C Run A", run_a, "full"))
        if run_b.get("status") == "ok":
            lines.append(_feature_row("Day 3C Run B", run_b, "reduced"))
    lines.append("")
    return lines


def _render_executive_summary(
    day2: dict[str, Any],
    day2b: dict[str, Any],
    day3: dict[str, Any],
    day3b: dict[str, Any],
    day3c: dict[str, Any],
) -> list[str]:
    lines = ["## Executive Summary", ""]
    if day2.get("status") == "ok":
        lines.append(
            "Day 2 restored the clean baseline to mean return {} with mean exposure {}, and it closed with verdict `{}`.".format(
                _format_number((day2.get("metrics") or {}).get("mean_return")) + "%",
                _format_exposure((day2.get("metrics") or {}).get("mean_exposure")),
                day2.get("verdict"),
            )
        )
    if day2b.get("status") == "ok":
        window_rows = list(day2b.get("window_comparison", []) or [])
        improved_windows = ", ".join(str(row.get("window_id")) for row in window_rows) if window_rows else "n/a"
        lines.append(
            "Day 2B specifically reanimated {} and raised the minimum patched exposure to {}, producing verdict `{}`.".format(
                improved_windows,
                _format_exposure(day2b.get("min_window_exposure_patched")),
                day2b.get("verdict"),
            )
        )
    if day3.get("status") == "ok":
        best_ic = dict(day3.get("best_by_mean_ic", {}) or {})
        best_ratio = dict(day3.get("best_by_train_test_ratio", {}) or {})
        lines.append(
            "Day 3 found the strongest raw IC in `{}` at {}, while the best train/test ratio belonged to `{}` at {}; the gating decision remained `{}`.".format(
                best_ic.get("model", "n/a"),
                _format_decimal(best_ic.get("mean_ic")),
                best_ratio.get("model", "n/a"),
                _format_ratio(best_ratio.get("train_test_ratio")),
                (day3.get("decision") or {}).get("reason"),
            )
        )
    if day3b.get("status") == "ok":
        best_ic = dict(day3b.get("best_by_mean_ic", {}) or {})
        best_ratio = dict(day3b.get("best_by_train_test_ratio", {}) or {})
        lines.append(
            "Day 3B tightened regularization and shifted the tree-model profile: best IC was `{}` at {}, while best ratio was `{}` at {}.".format(
                best_ic.get("model", "n/a"),
                _format_decimal(best_ic.get("mean_ic")),
                best_ratio.get("model", "n/a"),
                _format_ratio(best_ratio.get("train_test_ratio")),
            )
        )
    if day3c.get("status") == "ok":
        comparison = dict(day3c.get("comparison", {}) or {})
        recommended = dict(comparison.get("recommended_config", {}) or {})
        interpretation = dict(comparison.get("interpretation", {}) or {})
        lines.append(
            "Day 3C reran the tree stack on the updated feature matrix and recommended `{}`. Gap 9 verdict: {} Sentiment verdict: {}.".format(
                recommended.get("name", "n/a"),
                interpretation.get("gap9_effect", "n/a"),
                interpretation.get("sentiment_effect", "n/a"),
            )
        )
    else:
        lines.append("Day 3C has not been run yet, so the feature-update rerun verdict is still pending.")
    lines.append("")
    return lines


def _build_report_payload(args: argparse.Namespace) -> dict[str, Any]:
    resolved = {
        "day2": _resolve_stage_dir(args.day2_dir, DEFAULT_DAY2_ROOT, "summary.json"),
        "day2b": _resolve_stage_dir(args.day2b_dir, DEFAULT_DAY2B_ROOT, "comparison.json"),
        "day3": _resolve_stage_dir(args.day3_dir, DEFAULT_DAY3_ROOT, "summary.json"),
        "day3b": _resolve_stage_dir(args.day3b_dir, DEFAULT_DAY3B_ROOT, "summary.json"),
        "day3c": _resolve_day3c_root(args.day3c_dir),
    }

    day2 = _build_day2_payload(resolved["day2"])
    day2b = _build_day2b_payload(resolved["day2b"])
    day3 = _build_day3_stage_payload("day3", resolved["day3"])
    day3b = _build_day3_stage_payload("day3b", resolved["day3b"])
    day3b_delta = _build_day3b_delta(day3, resolved["day3b"])
    day3c = _build_day3c_payload(resolved["day3c"])

    payload = {
        "created_at": _utc_now(),
        "resolved_artifacts": {key: str(path) if path is not None else None for key, path in resolved.items()},
        "day2": day2,
        "day2b": day2b,
        "day3": day3,
        "day3b": day3b,
        "day3b_vs_day3": day3b_delta,
        "day3c": day3c,
    }

    lines: list[str] = [
        "# First Three-Day Experiment Report",
        "",
        f"- Created: {payload['created_at']}",
        f"- Output JSON: `{Path(str(args.output_json)).expanduser().resolve()}`",
        "",
    ]
    lines.extend(_render_artifact_inventory(resolved))
    lines.extend(_render_executive_summary(day2, day2b, day3, day3b, day3c))
    lines.extend(_render_day2_section(day2))
    lines.extend(_render_day2b_section(day2b))
    lines.extend(_render_day3_section(day3))
    lines.extend(_render_day3b_section(day3b, day3b_delta))
    lines.extend(_render_day3c_section(day3c))
    lines.extend(_render_cross_stage_section(day2, day2b, day3, day3b, day3c))

    return {
        "payload": payload,
        "markdown": "\n".join(lines),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a detailed report for the runnable first-three-day experiment stack.")
    parser.add_argument("--day2-dir", default=None, help="Explicit Day 2 experiment directory containing summary.json")
    parser.add_argument("--day2b-dir", default=None, help="Explicit Day 2B experiment directory containing comparison.json")
    parser.add_argument("--day3-dir", default=None, help="Explicit Day 3 experiment directory containing summary.json")
    parser.add_argument("--day3b-dir", default=None, help="Explicit Day 3B experiment directory containing summary.json")
    parser.add_argument("--day3c-dir", default=None, help="Explicit Day 3C root directory containing comparison.json")
    parser.add_argument("--output", default=str(DEFAULT_REPORT_MD), help="Markdown report output path")
    parser.add_argument("--output-json", default=str(DEFAULT_REPORT_JSON), help="Structured JSON report output path")
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    result = _build_report_payload(args)
    output_md = Path(str(args.output)).expanduser().resolve()
    output_json = Path(str(args.output_json)).expanduser().resolve()
    _write_text(output_md, str(result["markdown"]))
    _write_json(output_json, result["payload"])
    print(f"Report MD:   {output_md}")
    print(f"Report JSON: {output_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
