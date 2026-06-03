#!/usr/bin/env python3
"""Weekend maintenance runner for Northstar live operations."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATUS_PATH = PROJECT_ROOT / "data/runtime/automation/weekend_maintenance_status.json"
DEFAULT_LOG_PATH = PROJECT_ROOT / "logs/weekend_maintenance.log"


@dataclass
class WeekendStep:
    name: str
    command: List[str]
    timeout_seconds: int
    critical: bool = True


def _write_status(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _run_step(log_path: Path, step: WeekendStep) -> tuple[bool, str]:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    started = datetime.now()
    with open(log_path, "a", encoding="utf-8") as handle:
        handle.write("\n" + "=" * 120 + "\n")
        handle.write(f"[{started.isoformat()}] STEP={step.name}\n")
        handle.write("CMD=" + " ".join(step.command) + "\n\n")
        try:
            proc = subprocess.run(
                step.command,
                cwd=str(PROJECT_ROOT),
                stdout=handle,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=step.timeout_seconds,
                check=False,
            )
            message = f"return_code={proc.returncode}"
            handle.write(f"\nRETURN_CODE={proc.returncode}\n")
            return proc.returncode == 0, message
        except subprocess.TimeoutExpired:
            handle.write(f"\nTIMEOUT after {step.timeout_seconds}s\n")
            return False, f"timeout_after={step.timeout_seconds}s"
        except Exception as exc:
            handle.write(f"\nERROR: {exc}\n")
            return False, str(exc)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run weekend maintenance for Northstar live operations")
    parser.add_argument("--python-bin", default=sys.executable)
    parser.add_argument("--status-path", default=str(DEFAULT_STATUS_PATH))
    parser.add_argument("--log-path", default=str(DEFAULT_LOG_PATH))
    parser.add_argument(
        "--backup-destination-root",
        default=os.environ.get("NORTHSTAR_BACKUP_ROOT", str(Path.home() / "northstar_backups" / "northstar_v3")),
    )
    parser.add_argument("--backup-retention-days", type=int, default=21)
    parser.add_argument("--nse-period", choices=["1D", "1W", "1M", "3M", "6M", "1Y"], default="1W")
    parser.add_argument("--quick", action="store_true", help="Use quick artifact refresh instead of full weekend refresh")
    parser.add_argument("--macro-heavy", action="store_true", help="Use heavier macro refresh profile")
    parser.add_argument("--skip-backup", action="store_true")
    parser.add_argument("--skip-weekly-rebalance", action="store_true")
    parser.add_argument("--skip-verify-live", action="store_true")
    parser.add_argument("--force-weekday", action="store_true")
    args = parser.parse_args()

    status_path = Path(args.status_path)
    log_path = Path(args.log_path)
    now = datetime.now()

    if now.weekday() < 5 and not args.force_weekday:
        _write_status(
            status_path,
            {
                "timestamp": now.isoformat(),
                "status": "skipped",
                "reason": "weekend_only",
                "log_path": str(log_path),
            },
        )
        return 0

    refresh_cmd = [
        args.python_bin,
        str(PROJECT_ROOT / "scripts/runners/refresh_v3_artifacts.py"),
        "--skip-index",
    ]
    if args.quick:
        refresh_cmd.append("--quick")
    if args.macro_heavy:
        refresh_cmd.append("--macro-heavy")

    steps: List[WeekendStep] = [
        WeekendStep(
            "runtime_book_sync",
            [args.python_bin, str(PROJECT_ROOT / "scripts/runners/sync_live_books_to_runtime.py")],
            600,
        ),
        WeekendStep(
            "runtime_accounting_refresh",
            [args.python_bin, str(PROJECT_ROOT / "scripts/runners/refresh_runtime_accounting.py")],
            900,
        ),
        WeekendStep(
            "alternative_data_refresh",
            [
                args.python_bin,
                str(PROJECT_ROOT / "scripts/daily_alternative_data_pipeline.py"),
                "--nse-period",
                args.nse_period,
            ],
            3600,
        ),
        WeekendStep("artifact_refresh", refresh_cmd, 4 * 3600),
        WeekendStep(
            "periodic_reports_generation",
            [
                args.python_bin,
                str(PROJECT_ROOT / "scripts/generate_periodic_reports.py"),
                "--timezone",
                "Asia/Kolkata",
            ],
            3600,
        ),
        WeekendStep(
            "strict_system_update_check",
            [args.python_bin, str(PROJECT_ROOT / "scripts/ci/strict_system_update_check.py")],
            900,
        ),
    ]

    if not args.skip_weekly_rebalance:
        steps.append(
            WeekendStep(
                "weekly_rebalance",
                [args.python_bin, str(PROJECT_ROOT / "src/live/weekly_rebalance.py")],
                1800,
            )
        )

    if not args.skip_verify_live:
        steps.append(
            WeekendStep(
                "verify_live_readiness",
                [args.python_bin, str(PROJECT_ROOT / "scripts/verify_live_system.py"), "--for-tomorrow"],
                900,
            )
        )

    if not args.skip_backup:
        steps.append(
            WeekendStep(
                "backup_local_state",
                [
                    args.python_bin,
                    str(PROJECT_ROOT / "scripts/backup_northstar_data.py"),
                    "--destination-root",
                    args.backup_destination_root,
                    "--retention-days",
                    str(args.backup_retention_days),
                    "--verify",
                ],
                3600,
                critical=False,
            )
        )

    results: List[Dict[str, Any]] = []
    overall_status = "success"
    for step in steps:
        ok, message = _run_step(log_path, step)
        results.append(
            {
                "step": step.name,
                "critical": bool(step.critical),
                "ok": bool(ok),
                "message": message,
                "timestamp": datetime.now().isoformat(),
            }
        )
        if ok:
            continue
        if step.critical:
            overall_status = "failed"
            break
        overall_status = "warning"

    _write_status(
        status_path,
        {
            "timestamp": datetime.now().isoformat(),
            "status": overall_status,
            "results": results,
            "log_path": str(log_path),
        },
    )
    return 0 if overall_status in {"success", "warning"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
