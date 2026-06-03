#!/usr/bin/env python3
"""Run the repo's first-three-day experiment scripts in sequence.

There is no standalone Day 1 experiment runner in the repository. This launcher
therefore chains the concrete runnable scripts that cover the Day 2 -> Day 3C
stack in order.
"""

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPORT_SCRIPT = PROJECT_ROOT / "scripts/research/generate_first3day_experiment_report.py"


STEP_COMMANDS = {
    "day2": [sys.executable, str(PROJECT_ROOT / "scripts/research/run_day2_clean_baseline.py")],
    "day2b": [sys.executable, str(PROJECT_ROOT / "scripts/research/day2b_centering_patch_test.py")],
    "day3": [sys.executable, str(PROJECT_ROOT / "scripts/research/run_day3_model_comparison.py")],
    "day3b": [sys.executable, str(PROJECT_ROOT / "scripts/research/run_day3b_tighter_regularization.py")],
    "day3c": [sys.executable, str(PROJECT_ROOT / "scripts/research/run_day3c_feature_updated_baseline.py")],
}
DEFAULT_STEPS = ["day2", "day2b", "day3", "day3b", "day3c"]
STEP_OUTPUTS = {
    "day2": (PROJECT_ROOT / "data/results/research/experiments/week_2026_03_22/day2_clean_baseline", "summary.json"),
    "day2b": (PROJECT_ROOT / "data/results/research/experiments/week_2026_03_22/day2b_centering_patch", "comparison.json"),
    "day3": (PROJECT_ROOT / "data/results/research/experiments/week_2026_03_22/day3_model_comparison", "summary.json"),
    "day3b": (PROJECT_ROOT / "data/results/research/experiments/week_2026_03_22/day3b_tighter_regularization", "summary.json"),
    "day3c": (PROJECT_ROOT / "data/results/research/experiments/week_2026_03_22/day3c_feature_updated_baseline", "comparison.json"),
}
DEFAULT_REPORT_OUTPUT = PROJECT_ROOT / "data/results/research/experiments/week_2026_03_22/first3day_experiment_report.md"
DEFAULT_REPORT_JSON = PROJECT_ROOT / "data/results/research/experiments/week_2026_03_22/first3day_experiment_report.json"


def _parse_steps(raw: str) -> list[str]:
    steps = [str(token).strip().lower() for token in str(raw).split(",") if str(token).strip()]
    if not steps:
        raise ValueError("no_steps_requested")
    unknown = [step for step in steps if step not in STEP_COMMANDS]
    if unknown:
        raise ValueError(f"unknown_steps:{','.join(unknown)}")
    return steps


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the first-three-day Northstar research scripts sequentially.")
    parser.add_argument(
        "--steps",
        default=",".join(DEFAULT_STEPS),
        help="Comma-separated step list. Choices: day2,day2b,day3,day3b,day3c",
    )
    parser.add_argument("--smoke", action="store_true", help="Pass --smoke through to day3/day3b/day3c.")
    parser.add_argument("--max-windows", type=int, default=None, help="Pass --max-windows through to day3/day3b/day3c.")
    parser.add_argument("--allow-catboost-fallback", action="store_true", help="Pass through where supported.")
    parser.add_argument("--dry-run", action="store_true", help="Print the resolved commands without running them.")
    parser.add_argument("--skip-report", action="store_true", help="Skip the post-run consolidated markdown/JSON report.")
    parser.add_argument("--report-output", default=str(DEFAULT_REPORT_OUTPUT), help="Markdown report path.")
    parser.add_argument("--report-json-output", default=str(DEFAULT_REPORT_JSON), help="JSON report path.")
    return parser


def _resolve_command(step: str, args: argparse.Namespace) -> list[str]:
    cmd = list(STEP_COMMANDS[step])
    if step in {"day3", "day3b", "day3c"}:
        if bool(args.smoke):
            cmd.append("--smoke")
        if args.max_windows is not None:
            cmd.extend(["--max-windows", str(int(args.max_windows))])
        if bool(args.allow_catboost_fallback) and step in {"day3b", "day3c"}:
            cmd.append("--allow-catboost-fallback")
    return cmd


def _latest_child_with_file(root: Path, filename: str) -> Path | None:
    if not root.exists():
        return None
    if (root / filename).exists():
        return root
    candidates = [child for child in root.iterdir() if child.is_dir() and (child / filename).exists()]
    if not candidates:
        return None
    candidates.sort(key=lambda path: (path.name, path.stat().st_mtime), reverse=True)
    return candidates[0]


def _discover_artifact_dirs() -> dict[str, Path | None]:
    out: dict[str, Path | None] = {}
    for step, (root, filename) in STEP_OUTPUTS.items():
        out[step] = _latest_child_with_file(root, filename)
    return out


def _build_report_command(args: argparse.Namespace, artifact_dirs: dict[str, Path | None]) -> list[str]:
    cmd = [
        sys.executable,
        str(REPORT_SCRIPT),
        "--output",
        str(Path(str(args.report_output)).expanduser().resolve()),
        "--output-json",
        str(Path(str(args.report_json_output)).expanduser().resolve()),
    ]
    arg_names = {
        "day2": "--day2-dir",
        "day2b": "--day2b-dir",
        "day3": "--day3-dir",
        "day3b": "--day3b-dir",
        "day3c": "--day3c-dir",
    }
    for step, arg_name in arg_names.items():
        path = artifact_dirs.get(step)
        if path is not None:
            cmd.extend([arg_name, str(path)])
    return cmd


def main() -> int:
    args = build_arg_parser().parse_args()
    steps = _parse_steps(args.steps)

    for idx, step in enumerate(steps, start=1):
        cmd = _resolve_command(step, args)
        print(f"[{idx}/{len(steps)}] {step}: {shlex.join(cmd)}")
        if args.dry_run:
            continue
        subprocess.run(cmd, cwd=PROJECT_ROOT, check=True)

    artifact_dirs = _discover_artifact_dirs()
    report_cmd = _build_report_command(args, artifact_dirs)
    if not args.skip_report:
        print(f"[report] {shlex.join(report_cmd)}")
        if not args.dry_run:
            subprocess.run(report_cmd, cwd=PROJECT_ROOT, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
