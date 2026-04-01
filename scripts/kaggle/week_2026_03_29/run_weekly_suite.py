#!/usr/bin/env python3
"""Run the full 2026-03-29 Kaggle weekly sprint stack in order."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[3]
THIS_DIR = Path(__file__).resolve().parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the weekly Kaggle sprint suite.")
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument("--output-root", type=Path, default=None)
    parser.add_argument("--profile", choices=["smoke", "full"], default="full")
    parser.add_argument("--max-splits", type=int, default=None)
    parser.add_argument("--continue-on-error", action="store_true")
    parser.add_argument("--patchtst-result-path", type=Path, default=None)
    return parser.parse_args()


def _run_step(step_name: str, command: list[str], failures: list[dict[str, object]], continue_on_error: bool) -> bool:
    print(f"\n=== {step_name} ===", flush=True)
    print(" ".join(command), flush=True)
    proc = subprocess.run(command, cwd=PROJECT_ROOT)
    if proc.returncode == 0:
        return True
    failures.append({"step": step_name, "returncode": int(proc.returncode), "command": command})
    if not continue_on_error:
        return False
    return True


def main() -> int:
    args = parse_args()
    output_root = (args.output_root.expanduser().resolve() if args.output_root else PROJECT_ROOT / "tmp" / "weekly_suite_runs")
    suite_root = output_root / pd.Timestamp.utcnow().tz_localize(None).strftime("%Y%m%d_%H%M%S")
    suite_root.mkdir(parents=True, exist_ok=True)

    export_dir = suite_root / "00_export"
    nb00_dir = suite_root / "01_nb00"
    nb01_dir = suite_root / "02_nb01"
    nb02_dir = suite_root / "03_nb02"
    nb03_dir = suite_root / "04_nb03"
    nb04_dir = suite_root / "05_nb04"
    nb05_dir = suite_root / "06_nb05"
    nb06_dir = suite_root / "07_nb06"
    nb07_dir = suite_root / "08_nb07"

    python = sys.executable
    failures: list[dict[str, object]] = []
    skipped: list[dict[str, object]] = []
    max_split_args = ["--max-splits", str(args.max_splits)] if args.max_splits is not None else []
    data_args = ["--data-dir", str(args.data_dir)] if args.data_dir is not None else []

    steps = [
        {
            "name": "build_export",
            "deps": [],
            "command": [
                python,
                str(THIS_DIR / "build_weekly_feature_export.py"),
                "--output-dir",
                str(export_dir),
                "--profile",
                args.profile,
                *data_args,
            ],
        },
        {
            "name": "nb00",
            "deps": ["build_export"],
            "command": [
                python,
                str(THIS_DIR / "nb00_feature_health.py"),
                "--export-dir",
                str(export_dir),
                "--output-dir",
                str(nb00_dir),
            ],
        },
        {
            "name": "nb01",
            "deps": ["build_export", "nb00"],
            "command": [
                python,
                str(THIS_DIR / "nb01_fixed_baselines.py"),
                "--export-dir",
                str(export_dir),
                "--nb00-report",
                str(nb00_dir / "feature_health_report.json"),
                "--output-dir",
                str(nb01_dir),
                "--profile",
                args.profile,
                *max_split_args,
            ],
        },
        {
            "name": "nb02",
            "deps": ["build_export", "nb00", "nb01"],
            "command": [
                python,
                str(THIS_DIR / "nb02_failed_model_autopsy.py"),
                "--export-dir",
                str(export_dir),
                "--nb00-report",
                str(nb00_dir / "feature_health_report.json"),
                "--nb01-dir",
                str(nb01_dir),
                "--output-dir",
                str(nb02_dir),
                "--profile",
                args.profile,
                *max_split_args,
                *(["--patchtst-result-path", str(args.patchtst_result_path)] if args.patchtst_result_path is not None else []),
            ],
        },
        {
            "name": "nb03",
            "deps": ["build_export", "nb00"],
            "command": [
                python,
                str(THIS_DIR / "nb03_regime_dictionary.py"),
                "--export-dir",
                str(export_dir),
                "--nb00-report",
                str(nb00_dir / "feature_health_report.json"),
                "--output-dir",
                str(nb03_dir),
            ],
        },
        {
            "name": "nb04",
            "deps": ["build_export"],
            "command": [
                python,
                str(THIS_DIR / "nb04_company_attribution.py"),
                "--export-dir",
                str(export_dir),
                "--output-dir",
                str(nb04_dir),
            ],
        },
        {
            "name": "nb05",
            "deps": ["build_export"],
            "command": [
                python,
                str(THIS_DIR / "nb05_cross_asset_tests.py"),
                "--export-dir",
                str(export_dir),
                "--output-dir",
                str(nb05_dir),
                *data_args,
            ],
        },
        {
            "name": "nb06",
            "deps": ["build_export"],
            "command": [
                python,
                str(THIS_DIR / "nb06_india_hypothesis_battery.py"),
                "--export-dir",
                str(export_dir),
                "--output-dir",
                str(nb06_dir),
                *data_args,
            ],
        },
        {
            "name": "nb07",
            "deps": ["build_export", "nb01", "nb02", "nb03", "nb05", "nb06"],
            "command": [
                python,
                str(THIS_DIR / "nb07_ensemble_tra_deployment.py"),
                "--export-dir",
                str(export_dir),
                "--nb01-dir",
                str(nb01_dir),
                "--nb02-dir",
                str(nb02_dir),
                "--nb03-dir",
                str(nb03_dir),
                "--nb05-dir",
                str(nb05_dir),
                "--nb06-dir",
                str(nb06_dir),
                "--output-dir",
                str(nb07_dir),
            ],
        },
    ]

    completed: set[str] = set()
    failed: set[str] = set()
    for step in steps:
        step_name = str(step["name"])
        deps = list(step.get("deps") or [])
        missing_deps = [dep for dep in deps if dep not in completed]
        if missing_deps:
            reason = f"dependency_failed_or_skipped:{','.join(missing_deps)}"
            print(f"\n=== {step_name} ===", flush=True)
            print(f"[skip] {reason}", flush=True)
            skipped.append({"step": step_name, "reason": reason, "deps": deps})
            failed.add(step_name)
            continue
        ok = _run_step(step_name, list(step["command"]), failures, args.continue_on_error)
        if not ok:
            failed.add(step_name)
            break
        if not any(item["step"] == step_name for item in failures):
            completed.add(step_name)
        else:
            failed.add(step_name)

    manifest = {
        "suite_root": str(suite_root),
        "profile": args.profile,
        "failures": failures,
        "skipped": skipped,
        "status": "pass" if not failures else ("partial" if args.continue_on_error else "fail"),
        "outputs": {
            "export_dir": str(export_dir),
            "nb00_dir": str(nb00_dir),
            "nb01_dir": str(nb01_dir),
            "nb02_dir": str(nb02_dir),
            "nb03_dir": str(nb03_dir),
            "nb04_dir": str(nb04_dir),
            "nb05_dir": str(nb05_dir),
            "nb06_dir": str(nb06_dir),
            "nb07_dir": str(nb07_dir),
        },
    }
    (suite_root / "suite_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0 if manifest["status"] != "fail" else 1


if __name__ == "__main__":
    raise SystemExit(main())
