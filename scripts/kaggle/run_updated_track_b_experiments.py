#!/usr/bin/env python3
"""Run the updated Track B frontier experiment set with reproducible configs."""

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
        for pattern in ("track_b_runner.py", "track_a_runner.py", "sprint_utils.py"):
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
    from track_b_runner import TrackBRunConfig, run_track_b_notebook  # noqa: E402
except ModuleNotFoundError as exc:
    sprint_utils_path = _find_module_file("sprint_utils.py")
    track_a_runner_path = _find_module_file("track_a_runner.py")
    track_b_runner_path = _find_module_file("track_b_runner.py")
    if sprint_utils_path is not None:
        _load_module_from_file("sprint_utils", sprint_utils_path)
    if track_a_runner_path is not None:
        _load_module_from_file("track_a_runner", track_a_runner_path)
    if track_b_runner_path is not None:
        track_b_module = _load_module_from_file("track_b_runner", track_b_runner_path)
        TrackBRunConfig = track_b_module.TrackBRunConfig
        run_track_b_notebook = track_b_module.run_track_b_notebook
    else:
        raise ModuleNotFoundError(
            "Could not find track_b_runner.py. Upload track_b_runner.py, track_a_runner.py, "
            "and sprint_utils.py into an attached Kaggle dataset, then rerun."
        ) from exc


def _parse_csv_list(raw: str | None) -> list[str]:
    if raw is None:
        return []
    return [token.strip() for token in raw.split(",") if token.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run updated Track B frontier experiments.")
    parser.add_argument("--data-dir", type=Path, required=True, help="Northstar Kaggle export directory.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=(
            Path("/kaggle/working/updated_track_b_experiments")
            if Path("/kaggle").exists()
            else ROOT / "tmp" / "updated_track_b_experiments"
        ),
        help="Directory where Track B results will be written.",
    )
    parser.add_argument("--profile", choices=["smoke", "full"], default="full")
    parser.add_argument("--max-splits", type=int, default=None, help="Optional limit on walk-forward windows.")
    parser.add_argument(
        "--patchtst-result-path",
        type=Path,
        default=None,
        help="Optional explicit path to patchtst_final.json for Track B comparisons.",
    )
    parser.add_argument(
        "--model-filter",
        type=str,
        default="",
        help="Optional comma-separated Track B model filter, for example 'tft,itransformer'.",
    )
    args = parser.parse_args()

    config = TrackBRunConfig(
        data_dir=args.data_dir,
        output_dir=args.output_dir,
        continue_on_error=True,
        resume_from_checkpoint=True,
        run_profile=args.profile,
        max_splits=args.max_splits,
        patchtst_result_path=args.patchtst_result_path,
        model_filter=_parse_csv_list(args.model_filter),
    )

    print("\n=== Running track_b_frontier ===")
    print(f"output_dir={args.output_dir}")
    print(f"profile={args.profile}")
    if args.patchtst_result_path is not None:
        print(f"patchtst_result_path={args.patchtst_result_path}")
    if config.model_filter:
        print(f"model_filter={config.model_filter}")

    run_track_b_notebook(config)
    print("\nTrack B run completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
