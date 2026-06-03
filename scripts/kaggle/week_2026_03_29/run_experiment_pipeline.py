#!/usr/bin/env python3
"""Run export -> NB00 -> NB01 as a single resumable Kaggle pipeline."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import traceback
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.kaggle.week_2026_03_29.nb01_runner import run_experiment  # noqa: E402
from src.research.config_loader import load_experiment_config  # noqa: E402
from src.research.run_registry import RunRegistry, json_ready  # noqa: E402


FEATURE_EXPORT_REQUIRED_FILES = (
    "northstar_features.parquet",
    "northstar_walk_forward_splits.json",
    "northstar_regime_labels.parquet",
    "northstar_metadata.parquet",
    "weekly_export_manifest.json",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Kaggle export, NB00, and NB01 in one resumable pipeline.")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=Path("/kaggle/working/pipeline"))
    parser.add_argument("--profile", choices=["smoke", "full"], default="full")
    parser.add_argument("--max-splits", type=int, default=None)
    parser.add_argument("--compare-run-id", action="append", default=[])

    parser.add_argument("--lookback-days", type=int, default=3200)
    parser.add_argument("--max-tickers", type=int, default=500)
    parser.add_argument("--max-rows", type=int, default=0)
    parser.add_argument("--low-resource-mode", choices=["auto", "true", "false"], default="false")
    parser.add_argument("--rebuild-screener", choices=["auto", "true", "false"], default="false")

    parser.add_argument("--force-export", action="store_true")
    parser.add_argument("--force-nb00", action="store_true")
    parser.add_argument("--force-nb01", action="store_true")
    return parser.parse_args()


def _run_python(command: list[str]) -> None:
    print(f"[pipeline] running: {' '.join(command)}", flush=True)
    subprocess.run(command, check=True)


def _clear_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def _is_valid_export_dir(path: Path) -> bool:
    base = path.expanduser().resolve()
    if not base.exists():
        return False
    return all((base / name).exists() for name in FEATURE_EXPORT_REQUIRED_FILES)


def _nb00_report_path(path: Path) -> Path:
    return path.expanduser().resolve() / "feature_health_report.json"


def _nb01_summary_path(runs_root: Path, resolved_run_id: str) -> Path:
    return runs_root.expanduser().resolve() / resolved_run_id / "summary.json"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    args = parse_args()
    cfg = load_experiment_config(args.run_id)
    resolved_run_id = str((cfg.get("experiment") or {}).get("run_id", args.run_id) or args.run_id)

    registry = RunRegistry(resolved_run_id, cfg=cfg, output_root=args.output_root)
    registry.initialize(cfg)

    workspace = registry.run_dir
    export_dir = workspace / "00_export"
    nb00_dir = workspace / "nb00_feature_health"
    runs_root = workspace / "runs"
    runs_root.mkdir(parents=True, exist_ok=True)

    registry.write_run_manifest(
        {
            "pipeline": {
                "workspace": str(workspace),
                "export_dir": str(export_dir),
                "nb00_dir": str(nb00_dir),
                "runs_root": str(runs_root),
                "profile": args.profile,
            }
        }
    )

    try:
        if args.force_export or not _is_valid_export_dir(export_dir):
            registry.mark_stage_started(
                "export",
                command=[
                    sys.executable,
                    str(PROJECT_ROOT / "scripts" / "kaggle" / "week_2026_03_29" / "build_weekly_feature_export.py"),
                ],
                metadata={"profile": args.profile},
            )
            _clear_dir(export_dir)
            export_cmd = [
                sys.executable,
                str(PROJECT_ROOT / "scripts" / "kaggle" / "week_2026_03_29" / "build_weekly_feature_export.py"),
                "--data-dir",
                str(args.data_dir.expanduser().resolve()),
                "--output-dir",
                str(export_dir),
                "--profile",
                args.profile,
                "--rebuild-screener",
                args.rebuild_screener,
                "--low-resource-mode",
                args.low_resource_mode,
                "--lookback-days",
                str(args.lookback_days),
                "--max-tickers",
                str(args.max_tickers),
                "--max-rows",
                str(args.max_rows),
            ]
            _run_python(export_cmd)
            if not _is_valid_export_dir(export_dir):
                raise FileNotFoundError(f"pipeline_export_invalid:{export_dir}")
            registry.register_artifact("export", "export_dir", export_dir)
            registry.register_artifact("export", "manifest", export_dir / "weekly_export_manifest.json")
            registry.mark_stage_completed("export", metadata={"export_dir": str(export_dir)})
        else:
            print(f"[pipeline] export already available at {export_dir}; skipping", flush=True)

        nb00_report = _nb00_report_path(nb00_dir)
        if args.force_nb00 or not nb00_report.exists():
            registry.mark_stage_started(
                "nb00",
                command=[
                    sys.executable,
                    str(PROJECT_ROOT / "scripts" / "kaggle" / "week_2026_03_29" / "nb00_feature_health.py"),
                ],
                metadata={"export_dir": str(export_dir)},
            )
            _clear_dir(nb00_dir)
            nb00_cmd = [
                sys.executable,
                str(PROJECT_ROOT / "scripts" / "kaggle" / "week_2026_03_29" / "nb00_feature_health.py"),
                "--export-dir",
                str(export_dir),
                "--output-dir",
                str(nb00_dir),
            ]
            _run_python(nb00_cmd)
            if not nb00_report.exists():
                raise FileNotFoundError(f"pipeline_nb00_missing_report:{nb00_report}")
            registry.register_artifact("nb00", "report", nb00_report)
            registry.mark_stage_completed("nb00", metadata={"report": str(nb00_report)})
        else:
            print(f"[pipeline] NB00 report already available at {nb00_report}; skipping", flush=True)

        summary_path = _nb01_summary_path(runs_root, resolved_run_id)
        if args.force_nb01 or not summary_path.exists():
            registry.mark_stage_started(
                "nb01",
                metadata={
                    "export_dir": str(export_dir),
                    "nb00_report": str(nb00_report),
                    "runs_root": str(runs_root),
                    "profile": args.profile,
                },
            )
            result = run_experiment(
                args.run_id,
                export_dir=export_dir,
                nb00_report=nb00_report,
                output_dir=runs_root,
                profile=args.profile,
                max_splits=args.max_splits,
                compare_run_ids=list(args.compare_run_id or []),
            )
            if not summary_path.exists():
                raise FileNotFoundError(f"pipeline_nb01_missing_summary:{summary_path}")
            registry.register_artifact("nb01", "summary", summary_path)
            registry.mark_stage_completed("nb01", metadata={"result": json_ready(result)})
        else:
            print(f"[pipeline] NB01 summary already available at {summary_path}; skipping", flush=True)
            result = _load_json(summary_path)

        pipeline_summary = {
            "run_id": resolved_run_id,
            "workspace": str(workspace),
            "export_dir": str(export_dir),
            "nb00_report": str(nb00_report),
            "summary_path": str(summary_path),
            "profile": args.profile,
            "result": json_ready(result),
        }
        (workspace / "pipeline_summary.json").write_text(
            json.dumps(json_ready(pipeline_summary), indent=2),
            encoding="utf-8",
        )
        print(json.dumps(json_ready(pipeline_summary), indent=2), flush=True)
        return 0
    except Exception as exc:  # noqa: BLE001
        error = "".join(traceback.format_exception_only(type(exc), exc)).strip()
        current = registry._load_stage_status().get("stages", {})
        running = [name for name, payload in current.items() if payload.get("status") == "running"]
        if running:
            registry.mark_stage_failed(running[-1], error=error)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
