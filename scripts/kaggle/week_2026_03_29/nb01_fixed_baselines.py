#!/usr/bin/env python3
"""NB-01: run the fixed tree-model baselines on the weekly export."""

from __future__ import annotations

import argparse
import importlib.util
import os
import sys
from pathlib import Path
from typing import Any

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
    json_ready,
    make_run_dir,
    read_json,
    resolve_export_dir,
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


def main() -> int:
    args = parse_args()
    export_artifacts = resolve_export_dir(args.export_dir)
    output_dir = args.output_dir.expanduser().resolve() if args.output_dir else make_run_dir(None, "nb01_fixed_baselines")
    output_dir.mkdir(parents=True, exist_ok=True)

    selected = _selected_features(export_artifacts.export_dir, args.nb00_report)
    filtered_export_dir = output_dir / "tier12_export"
    subset_feature_export(
        source_dir=export_artifacts.export_dir,
        output_dir=filtered_export_dir,
        selected_features=selected if selected else None,
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
        "selected_feature_count": len(selected),
        "selected_features": selected,
        "models": rows,
    }
    write_json(output_dir / "baseline_results.json", payload)
    print(json_ready({"models": rows, "filtered_export_dir": str(filtered_export_dir)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
