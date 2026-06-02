#!/usr/bin/env python3
"""Zero-argument Kaggle entrypoint for the updated Track A experiment suite.

Use this file as the Kaggle script/notebook source.
Attach a dataset that contains:
  - northstar_features.parquet
  - northstar_walk_forward_splits.json
  - northstar_regime_labels.parquet
  - track_a_runner.py
  - sprint_utils.py
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


PROFILE = "full"
INCLUDE_DAY1 = False
REDUCED_FEATURE_COUNT = 60
OUTPUT_ROOT = Path("/kaggle/working/updated_track_a_experiments")


REQUIRED_EXPORT_FILES = (
    "northstar_features.parquet",
    "northstar_walk_forward_splits.json",
    "northstar_regime_labels.parquet",
)


def _looks_like_export_dir(path: Path) -> bool:
    return path.is_dir() and all((path / filename).exists() for filename in REQUIRED_EXPORT_FILES)


def _find_data_dir() -> Path:
    preferred = [
        Path("/kaggle/input/northstar-v4-validation-data"),
        Path("/kaggle/input/datasets/aryakghoshal/northstar-v4-validation-data"),
    ]
    for candidate in preferred:
        if _looks_like_export_dir(candidate):
            return candidate

    kaggle_input = Path("/kaggle/input")
    if kaggle_input.exists():
        for candidate in sorted(kaggle_input.rglob("*")):
            if _looks_like_export_dir(candidate):
                return candidate

    raise RuntimeError(
        "Could not find a Northstar export directory in /kaggle/input. "
        "Attach the dataset containing northstar_features.parquet, "
        "northstar_walk_forward_splits.json, and northstar_regime_labels.parquet."
    )


def _find_module_file(filename: str) -> Path:
    kaggle_input = Path("/kaggle/input")
    if kaggle_input.exists():
        for match in sorted(kaggle_input.rglob(filename)):
            return match
    raise FileNotFoundError(
        f"Could not find {filename} in /kaggle/input. "
        f"Upload {filename} into the attached Kaggle dataset and rerun."
    )


def _load_module_from_file(module_name: str, file_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ModuleNotFoundError(f"Could not create import spec for {module_name} from {file_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _load_track_a_runner():
    sprint_utils_path = _find_module_file("sprint_utils.py")
    track_a_runner_path = _find_module_file("track_a_runner.py")
    _load_module_from_file("sprint_utils", sprint_utils_path)
    track_a_module = _load_module_from_file("track_a_runner", track_a_runner_path)
    return track_a_module.TrackARunConfig, track_a_module.run_track_a_notebook


def _run_experiment(
    TrackARunConfig,
    run_track_a_notebook,
    *,
    name: str,
    data_dir: Path,
    model_filter: list[str],
    feature_mode: str,
    normalize_raw_financials: bool,
) -> dict:
    output_dir = OUTPUT_ROOT / name
    config = TrackARunConfig(
        data_dir=data_dir,
        output_dir=output_dir,
        skip_days=set() if INCLUDE_DAY1 else {1},
        continue_on_error=True,
        resume_from_checkpoint=True,
        run_profile=PROFILE,
        model_filter=model_filter,
        feature_mode=feature_mode,
        reduced_feature_count=REDUCED_FEATURE_COUNT,
        normalize_raw_financials=normalize_raw_financials,
        require_group_ranking=True,
    )
    print(f"\n=== Running {name} ===", flush=True)
    print(f"data_dir={data_dir}", flush=True)
    print(f"output_dir={output_dir}", flush=True)
    print(f"models={model_filter}", flush=True)
    print(f"feature_mode={feature_mode}", flush=True)
    print(f"normalize_raw_financials={normalize_raw_financials}", flush=True)
    return run_track_a_notebook(config)


def main() -> int:
    data_dir = _find_data_dir()
    TrackARunConfig, run_track_a_notebook = _load_track_a_runner()
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    _run_experiment(
        TrackARunConfig,
        run_track_a_notebook,
        name="tree_baseline",
        data_dir=data_dir,
        model_filter=["xgboost", "lightgbm", "catboost"],
        feature_mode="full",
        normalize_raw_financials=False,
    )
    _run_experiment(
        TrackARunConfig,
        run_track_a_notebook,
        name="tree_reduced",
        data_dir=data_dir,
        model_filter=["xgboost", "lightgbm", "catboost"],
        feature_mode="reduced",
        normalize_raw_financials=True,
    )
    _run_experiment(
        TrackARunConfig,
        run_track_a_notebook,
        name="sequence_reduced",
        data_dir=data_dir,
        model_filter=["lstm", "gru", "tcn", "transformer"],
        feature_mode="reduced",
        normalize_raw_financials=True,
    )

    print("\nUpdated Track A suite completed.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
