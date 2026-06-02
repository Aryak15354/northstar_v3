"""Compare Northstar Kaggle experiment runs side by side."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from src.research.run_registry import RunRegistry


def load_summary(run_id: str, runs_root: str | Path | None = None) -> dict[str, Any]:
    root = Path(runs_root or RunRegistry.default_output_root()).expanduser().resolve()
    candidates = [
        root / str(run_id) / "summary.json",
        Path("runs") / str(run_id) / "summary.json",
    ]
    for path in candidates:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    raise FileNotFoundError(f"No summary found for {run_id}")


def _format_metric(value: Any, kind: str) -> str:
    if value is None:
        return "-"
    if kind == "pct":
        return f"{float(value) * 100.0:.1f}%"
    if kind == "float4":
        return f"{float(value):.4f}"
    if kind == "float3":
        return f"{float(value):.3f}"
    if kind == "ratio":
        return f"{float(value):.2f}x"
    return str(value)


def compare(run_ids: list[str], runs_root: str | Path | None = None) -> str:
    summaries: dict[str, dict[str, Any]] = {}
    warnings: list[str] = []
    for run_id in run_ids:
        try:
            summaries[run_id] = load_summary(run_id, runs_root=runs_root)
        except FileNotFoundError as exc:
            warnings.append(f"WARNING: {exc}")

    if not summaries:
        output = "\n".join([*warnings, "No runs found."]).strip()
        return output if output else "No runs found."

    metrics = [
        ("Verdict", lambda payload: _format_metric(payload.get("verdict"), "text")),
        ("Best model", lambda payload: _format_metric(payload.get("best_model"), "text")),
        ("Regime cfg", lambda payload: _format_metric(payload.get("regime_config_version"), "text")),
        ("CatBoost mean IC", lambda payload: _format_metric((payload.get("catboost") or {}).get("mean_ic"), "float4")),
        ("CatBoost IC IR", lambda payload: _format_metric((payload.get("catboost") or {}).get("ic_ir"), "float3")),
        ("CatBoost ratio", lambda payload: _format_metric((payload.get("catboost") or {}).get("train_test_ratio"), "ratio")),
        ("XGBoost mean IC", lambda payload: _format_metric((payload.get("xgboost") or {}).get("mean_ic"), "float4")),
        ("XGBoost IC IR", lambda payload: _format_metric((payload.get("xgboost") or {}).get("ic_ir"), "float3")),
        ("LightGBM mean IC", lambda payload: _format_metric((payload.get("lightgbm") or {}).get("mean_ic"), "float4")),
        ("LightGBM IC IR", lambda payload: _format_metric((payload.get("lightgbm") or {}).get("ic_ir"), "float3")),
        ("IC IR excl R7/R8", lambda payload: _format_metric(payload.get("excl_r7_r8_ir"), "float3")),
        ("Mean exposure", lambda payload: _format_metric(payload.get("mean_exposure"), "pct")),
        ("Windows >20%", lambda payload: _format_metric(payload.get("windows_above_20pct"), "text")),
        ("Duration (min)", lambda payload: _format_metric(payload.get("duration_minutes"), "text")),
    ]

    col_width = max(20, max(len(run_id) for run_id in summaries))
    header = f"{'Metric':<25}" + "".join(f"{run_id:>{col_width}}" for run_id in summaries)
    rows = [header, "-" * len(header)]
    for label, formatter in metrics:
        row = f"{label:<25}"
        for run_id, payload in summaries.items():
            try:
                value = formatter(payload)
            except Exception:
                value = "ERR"
            row += f"{value:>{col_width}}"
        rows.append(row)
    if warnings:
        rows.extend(warnings)
    return "\n".join(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare Northstar Kaggle runs.")
    parser.add_argument("run_ids", nargs="+", help="Run ids to compare.")
    parser.add_argument("--runs-root", type=Path, default=None)
    args = parser.parse_args(argv)
    print(compare(args.run_ids, runs_root=args.runs_root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
