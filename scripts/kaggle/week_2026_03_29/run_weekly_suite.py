#!/usr/bin/env python3
"""Run the full 2026-03-29 Kaggle weekly sprint stack in order."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.research.config_loader import load_experiment_config  # noqa: E402
from src.research.run_registry import RunRegistry  # noqa: E402

THIS_DIR = Path(__file__).resolve().parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the weekly Kaggle sprint suite.")
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument("--output-root", type=Path, default=None)
    parser.add_argument("--profile", choices=["smoke", "full"], default="full")
    parser.add_argument("--max-splits", type=int, default=None)
    parser.add_argument("--continue-on-error", action="store_true")
    parser.add_argument("--patchtst-result-path", type=Path, default=None)
    parser.add_argument("--run-id", type=str, default=None, help="Optional config-driven run id for registry-backed outputs.")
    return parser.parse_args()


def _run_step(
    step_name: str,
    command: list[str],
    failures: list[dict[str, object]],
    continue_on_error: bool,
    *,
    env: dict[str, str] | None = None,
) -> bool:
    print(f"\n=== {step_name} ===", flush=True)
    print(" ".join(command), flush=True)
    proc = subprocess.run(command, cwd=PROJECT_ROOT, env=env)
    if proc.returncode == 0:
        return True
    failures.append({"step": step_name, "returncode": int(proc.returncode), "command": command})
    if not continue_on_error:
        return False
    return True


def _collect_stage_outputs(stage_dir: Path) -> dict[str, object]:
    stage_dir = stage_dir.expanduser().resolve()
    files: list[str] = []
    if stage_dir.exists():
        for path in sorted(stage_dir.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix.lower() in {".json", ".txt", ".md", ".parquet", ".csv", ".yaml", ".yml"}:
                files.append(str(path))
    return {
        "stage_dir": str(stage_dir),
        "exists": stage_dir.exists(),
        "file_count": int(len(files)),
        "files": files[:200],
    }


def _build_suite_context(
    *,
    args: argparse.Namespace,
    suite_root: Path,
    registry: RunRegistry | None,
    cfg: dict[str, object] | None,
) -> dict[str, object]:
    reference_bundle = dict((cfg or {}).get("_reference_bundle") or {})
    return {
        "suite": "weekly_2026_03_29",
        "profile": args.profile,
        "input_run_id": args.run_id,
        "resolved_run_id": registry.run_id if registry is not None else None,
        "suite_root": str(suite_root),
        "run_root": str(registry.run_dir) if registry is not None else str(suite_root),
        "config_snapshot_path": str(registry.run_dir / "config_snapshot.yaml") if registry is not None else None,
        "reference_bundle": reference_bundle,
    }


def _build_stage_env(
    *,
    step_name: str,
    suite_context: dict[str, object],
) -> dict[str, str]:
    env = dict(os.environ)
    env["NORTHSTAR_SUITE_NAME"] = str(suite_context.get("suite") or "weekly_2026_03_29")
    env["NORTHSTAR_STAGE_NAME"] = str(step_name)
    env["NORTHSTAR_PROFILE"] = str(suite_context.get("profile") or "full")
    env["NORTHSTAR_SUITE_ROOT"] = str(suite_context.get("suite_root") or "")
    env["NORTHSTAR_RUN_ROOT"] = str(suite_context.get("run_root") or suite_context.get("suite_root") or "")
    resolved_run_id = str(suite_context.get("resolved_run_id") or "").strip()
    if resolved_run_id:
        env["NORTHSTAR_RUN_ID"] = resolved_run_id
    config_snapshot_path = str(suite_context.get("config_snapshot_path") or "").strip()
    if config_snapshot_path:
        env["NORTHSTAR_CONFIG_SNAPSHOT"] = config_snapshot_path
    reference_bundle = dict(suite_context.get("reference_bundle") or {})
    reference_root = str(reference_bundle.get("reference_root") or "").strip()
    manifest_path = str(reference_bundle.get("manifest_path") or "").strip()
    if reference_root:
        env["NORTHSTAR_REFERENCE_ROOT"] = reference_root
    if manifest_path:
        env["NORTHSTAR_REFERENCE_MANIFEST"] = manifest_path
    return env


def main() -> int:
    args = parse_args()
    registry: RunRegistry | None = None
    cfg: dict[str, object] | None = None
    if args.run_id:
        cfg = load_experiment_config(args.run_id)
        resolved_run_id = str((cfg.get("experiment") or {}).get("run_id", args.run_id) or args.run_id)
        registry = RunRegistry(resolved_run_id, cfg=cfg, output_root=args.output_root)
        suite_root = registry.initialize(cfg)
        registry.write_run_manifest(
            {
                "suite": "weekly_2026_03_29",
                "experiment_id": args.run_id,
                "profile": args.profile,
                "continue_on_error": bool(args.continue_on_error),
            }
        )
    else:
        output_root = (args.output_root.expanduser().resolve() if args.output_root else PROJECT_ROOT / "tmp" / "weekly_suite_runs")
        suite_root = output_root / pd.Timestamp.utcnow().tz_localize(None).strftime("%Y%m%d_%H%M%S")
        suite_root.mkdir(parents=True, exist_ok=True)

    suite_context = _build_suite_context(args=args, suite_root=suite_root, registry=registry, cfg=cfg)
    suite_context_path = suite_root / "suite_context.json"
    suite_context_path.write_text(json.dumps(suite_context, indent=2), encoding="utf-8")
    if registry is not None:
        registry.write_run_manifest({"suite_context": suite_context})
        registry.register_artifact("suite", "suite_context", suite_context_path)

    export_dir = suite_root / "00_export"
    nb00_dir = suite_root / "nb00"
    nb01_dir = suite_root / "nb01"
    nb02_dir = suite_root / "nb02"
    nb03_dir = suite_root / "nb03"
    nb04_dir = suite_root / "nb04"
    nb05_dir = suite_root / "nb05"
    nb06_dir = suite_root / "nb06"
    nb07_dir = suite_root / "nb07"

    python = sys.executable
    failures: list[dict[str, object]] = []
    skipped: list[dict[str, object]] = []
    stage_artifacts: dict[str, dict[str, object]] = {}
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
                str(THIS_DIR / ("nb01_runner.py" if args.run_id else "nb01_fixed_baselines.py")),
                *(
                    ["--run-id", str(args.run_id)]
                    if args.run_id
                    else []
                ),
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
            if registry is not None:
                registry.mark_stage_failed(step_name, error=reason)
            continue
        if registry is not None:
            registry.mark_stage_started(step_name, command=list(step["command"]))
        ok = _run_step(
            step_name,
            list(step["command"]),
            failures,
            args.continue_on_error,
            env=_build_stage_env(step_name=step_name, suite_context=suite_context),
        )
        if not ok:
            failed.add(step_name)
            if registry is not None:
                failure = next((item for item in failures if item["step"] == step_name), None)
                registry.mark_stage_failed(
                    step_name,
                    error=f"returncode:{failure['returncode']}" if failure else "unknown_failure",
                    returncode=int(failure["returncode"]) if failure else None,
                )
            break
        if not any(item["step"] == step_name for item in failures):
            completed.add(step_name)
            inventory = _collect_stage_outputs(Path(step["command"][step["command"].index("--output-dir") + 1]) if "--output-dir" in step["command"] else suite_root / step_name)
            stage_artifacts[step_name] = inventory
            if registry is not None:
                registry.mark_stage_completed(step_name, metadata={"artifact_count": int(inventory["file_count"])})
                registry.register_artifact(step_name, f"{step_name}_dir", Path(str(inventory["stage_dir"])))
        else:
            failed.add(step_name)
            if registry is not None:
                failure = next((item for item in failures if item["step"] == step_name), None)
                registry.mark_stage_failed(
                    step_name,
                    error=f"returncode:{failure['returncode']}" if failure else "unknown_failure",
                    returncode=int(failure["returncode"]) if failure else None,
                )

    manifest = {
        "suite_root": str(suite_root),
        "profile": args.profile,
        "suite_context_path": str(suite_context_path),
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
        "stage_artifacts": stage_artifacts,
    }
    (suite_root / "suite_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    if registry is not None:
        registry.write_run_manifest({"suite_manifest": manifest})
        registry.register_artifact("suite", "suite_manifest", suite_root / "suite_manifest.json")
    print(json.dumps(manifest, indent=2))
    return 0 if manifest["status"] != "fail" else 1


if __name__ == "__main__":
    raise SystemExit(main())
