#!/usr/bin/env python3
"""Run the updated Track A experiment set with reproducible configs."""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path


def _detect_root() -> Path:
    script_path = Path(__file__).resolve()
    for candidate in [script_path.parent, *script_path.parents]:
        if (candidate / "notebooks" / "kaggle_sprint" / "shared").exists():
            return candidate
    return Path("/kaggle/working") if Path("/kaggle").exists() else Path.cwd()


def _add_shared_paths() -> None:
    candidates = [
        Path.cwd(),
        Path.cwd() / "shared",
        Path.cwd().parent / "shared",
        Path.cwd() / "notebooks" / "kaggle_sprint" / "shared",
        Path.cwd().parent / "notebooks" / "kaggle_sprint" / "shared",
        Path("/kaggle/input"),
    ]
    script_dir = Path(__file__).resolve().parent
    candidates.extend(
        [
            script_dir,
            script_dir / "shared",
            script_dir.parent / "shared",
            script_dir / "notebooks" / "kaggle_sprint" / "shared",
            script_dir.parent / "notebooks" / "kaggle_sprint" / "shared",
        ]
    )
    kaggle_input = Path("/kaggle/input")
    if kaggle_input.exists():
        for pattern in ("track_a_runner.py", "sprint_utils.py", "track_b_runner.py"):
            for match in sorted(kaggle_input.rglob(pattern)):
                candidates.append(match.parent)

    seen: set[str] = set()
    for candidate in candidates:
        candidate_str = str(candidate)
        if candidate.exists() and candidate_str not in seen:
            sys.path.insert(0, candidate_str)
            seen.add(candidate_str)


ROOT = _detect_root()
_add_shared_paths()


def _find_module_file(filename: str) -> Path | None:
    candidates = [
        Path.cwd() / filename,
        Path.cwd() / "shared" / filename,
        Path(__file__).resolve().parent / filename,
        Path(__file__).resolve().parent / "shared" / filename,
        ROOT / "notebooks" / "kaggle_sprint" / "shared" / filename,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    kaggle_input = Path("/kaggle/input")
    if kaggle_input.exists():
        for match in sorted(kaggle_input.rglob(filename)):
            return match
    return None


def _load_module_from_file(module_name: str, file_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ModuleNotFoundError(f"Could not create import spec for {module_name} from {file_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


try:
    from track_a_runner import TrackARunConfig, run_track_a_notebook  # noqa: E402
except ModuleNotFoundError as exc:
    sprint_utils_path = _find_module_file("sprint_utils.py")
    track_a_runner_path = _find_module_file("track_a_runner.py")
    if sprint_utils_path is not None:
        _load_module_from_file("sprint_utils", sprint_utils_path)
    if track_a_runner_path is not None:
        track_a_module = _load_module_from_file("track_a_runner", track_a_runner_path)
        TrackARunConfig = track_a_module.TrackARunConfig
        run_track_a_notebook = track_a_module.run_track_a_notebook
    else:
        raise ModuleNotFoundError(
            "Could not find track_a_runner.py. Upload track_a_runner.py and sprint_utils.py "
            "into an attached Kaggle dataset, then rerun."
        ) from exc


def _run_experiment(
    *,
    name: str,
    data_dir: Path,
    output_root: Path,
    profile: str,
    max_splits: int | None,
    include_day1: bool,
    model_filter: list[str],
    feature_mode: str,
    normalize_raw_financials: bool,
    reduced_feature_count: int,
) -> dict:
    output_dir = output_root / name
    config = TrackARunConfig(
        data_dir=data_dir,
        output_dir=output_dir,
        skip_days=set() if include_day1 else {1},
        continue_on_error=True,
        resume_from_checkpoint=True,
        run_profile=profile,
        max_splits=max_splits,
        model_filter=model_filter,
        feature_mode=feature_mode,
        reduced_feature_count=reduced_feature_count,
        normalize_raw_financials=normalize_raw_financials,
        require_group_ranking=True,
    )
    print(f"\n=== Running {name} ===")
    print(f"output_dir={output_dir}")
    print(f"models={model_filter}")
    print(f"feature_mode={feature_mode}")
    print(f"normalize_raw_financials={normalize_raw_financials}")
    return run_track_a_notebook(config)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run updated Track A research experiments.")
    parser.add_argument("--data-dir", type=Path, required=True, help="Northstar Kaggle export directory.")
    parser.add_argument(
        "--output-root",
        type=Path,
        default=(
            Path("/kaggle/working/updated_track_a_experiments")
            if Path("/kaggle").exists()
            else ROOT / "tmp" / "updated_track_a_experiments"
        ),
        help="Root directory where experiment folders will be written.",
    )
    parser.add_argument(
        "--experiment",
        choices=["tree_baseline", "tree_reduced", "sequence_reduced", "all"],
        default="all",
        help="Which experiment preset to run.",
    )
    parser.add_argument("--profile", choices=["smoke", "full"], default="full")
    parser.add_argument("--max-splits", type=int, default=None, help="Optional limit on walk-forward windows.")
    parser.add_argument(
        "--include-day1",
        action="store_true",
        help="Run day 1 explicitly instead of letting reduced-feature runs bootstrap IC lazily.",
    )
    parser.add_argument(
        "--reduced-feature-count",
        type=int,
        default=60,
        help="Top-IC feature count used by the reduced presets.",
    )
    args = parser.parse_args()

    experiments: list[tuple[str, list[str], str, bool]]
    if args.experiment == "tree_baseline":
        experiments = [
            ("tree_baseline", ["xgboost", "lightgbm", "catboost"], "full", False),
        ]
    elif args.experiment == "tree_reduced":
        experiments = [
            ("tree_reduced", ["xgboost", "lightgbm", "catboost"], "reduced", True),
        ]
    elif args.experiment == "sequence_reduced":
        experiments = [
            ("sequence_reduced", ["lstm", "gru", "tcn", "transformer"], "reduced", True),
        ]
    else:
        experiments = [
            ("tree_baseline", ["xgboost", "lightgbm", "catboost"], "full", False),
            ("tree_reduced", ["xgboost", "lightgbm", "catboost"], "reduced", True),
            ("sequence_reduced", ["lstm", "gru", "tcn", "transformer"], "reduced", True),
        ]

    args.output_root.mkdir(parents=True, exist_ok=True)
    for name, model_filter, feature_mode, normalize_raw_financials in experiments:
        _run_experiment(
            name=name,
            data_dir=args.data_dir,
            output_root=args.output_root,
            profile=args.profile,
            max_splits=args.max_splits,
            include_day1=args.include_day1,
            model_filter=model_filter,
            feature_mode=feature_mode,
            normalize_raw_financials=normalize_raw_financials,
            reduced_feature_count=args.reduced_feature_count,
        )

    print("\nAll requested experiments completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
