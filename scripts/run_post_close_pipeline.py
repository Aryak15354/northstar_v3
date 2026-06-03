#!/usr/bin/env python3
"""Canonical post-close refresh and recalibration workflow for Northstar V3.

This runner is intended for automated weekday execution after the India market
close. It performs:

1. A weekly NSE alternative-data pass (1W) to avoid missing infrequent updates.
2. The full daily refresh and recalibration runner.
3. A standby verification pass for the next trading session.
4. A final health snapshot.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, time as dt_time, timedelta
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
IST = ZoneInfo("Asia/Kolkata")
MARKET_CLOSE = dt_time(15, 30)
LIVE_OPTIONS_DIR = PROJECT_ROOT / "data" / "options" / "live"
LIVE_HEARTBEAT_PATH = LIVE_OPTIONS_DIR / "live_engine_heartbeat.json"
LIVE_LOCK_PATH = LIVE_OPTIONS_DIR / "options_engine.lock"


@dataclass
class StageResult:
    name: str
    status: str
    required: bool
    command: list[str]
    started_at: str
    finished_at: str
    duration_seconds: float
    returncode: int
    log_path: str


def resolve_date(raw: str) -> pd.Timestamp:
    if str(raw).strip().lower() == "today":
        return pd.Timestamp.now(tz=IST).normalize().tz_localize(None)
    value = pd.to_datetime(raw, errors="coerce")
    if pd.isna(value):
        raise ValueError(f"invalid --date: {raw}")
    return pd.Timestamp(value).normalize()


def market_close_deadline(grace_minutes: int) -> datetime:
    now = datetime.now(IST)
    close_dt = datetime.combine(now.date(), MARKET_CLOSE, tzinfo=IST)
    return close_dt + timedelta(minutes=max(int(grace_minutes), 0))


def ensure_post_close(grace_minutes: int) -> None:
    now = datetime.now(IST)
    allowed_after = market_close_deadline(grace_minutes)
    if now < allowed_after:
        raise RuntimeError(
            "post-close runner blocked before market-close guard window: "
            f"now={now.isoformat(timespec='seconds')} "
            f"allowed_after={allowed_after.isoformat(timespec='seconds')}"
        )


def build_stage_plan(args: argparse.Namespace) -> list[dict[str, object]]:
    deep_sentiment = [
        sys.executable,
        "scripts/run_daily_sentiment_pipeline.py",
        "--date",
        args.date,
        "--include-news-builder",
        "--news-sources",
        args.news_sources,
    ]
    if args.news_max_tickers > 0:
        deep_sentiment.extend(["--news-max-tickers", str(args.news_max_tickers)])
    if args.news_max_months > 0:
        deep_sentiment.extend(["--news-max-months", str(args.news_max_months)])

    full_runner = [
        sys.executable,
        "scripts/run_complete_v3_system.py",
        "--date",
        args.date,
        "--quick",
        "--proof-level",
        args.proof_level,
        "--alt-start-year",
        str(args.alt_start_year),
        "--alt-end-year",
        str(args.alt_end_year),
        "--news-sources",
        args.news_sources,
    ]
    if args.force_gst:
        full_runner.append("--force-gst")
    if args.news_max_tickers > 0:
        full_runner.extend(["--news-max-tickers", str(args.news_max_tickers)])
    if args.news_max_months > 0:
        full_runner.extend(["--news-max-months", str(args.news_max_months)])

    weekly_alt = [
        sys.executable,
        "scripts/daily_alternative_data_pipeline.py",
        "--start-year",
        str(args.alt_start_year),
        "--end-year",
        str(args.alt_end_year),
        "--resume",
        "--nse-period",
        "1W",
    ]

    return [
        {
            "name": "Stop Live Options Engine",
            "required": True,
            "func": stop_live_options_engine if args.stop_live_engine else None,
        },
        {
            "name": "Alternative Data Weekly Pass",
            "required": True,
            "command": weekly_alt,
        },
        {
            "name": "News And Sentiment Deep Refresh",
            "required": True,
            "command": deep_sentiment,
        },
        {
            "name": "Full Daily Refresh And Recalibration",
            "required": True,
            "command": full_runner,
        },
        {
            "name": "Standby Verification",
            "required": True,
            "command": [sys.executable, "scripts/verify_live_system.py", "--for-tomorrow"],
        },
        {
            "name": "Health Snapshot",
            "required": False,
            "command": [sys.executable, "run.py", "--mode", "health"],
        },
    ]


def run_stage(stage: dict[str, object], logs_dir: Path) -> StageResult:
    name = str(stage["name"])
    command = [str(part) for part in list(stage.get("command", []))]
    required = bool(stage["required"])
    slug = "".join(ch.lower() if ch.isalnum() else "_" for ch in name).strip("_")
    log_path = logs_dir / f"{slug}.log"
    started = datetime.now(IST)
    with log_path.open("w", encoding="utf-8") as handle:
        handle.write(f"[runner] stage={name}\n")
        handle.write(f"[runner] started_at={started.isoformat()}\n")
        if command:
            handle.write(f"[runner] command={' '.join(command)}\n\n")
            proc = subprocess.Popen(
                command,
                cwd=str(PROJECT_ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            try:
                if proc.stdout is not None:
                    for line in proc.stdout:
                        handle.write(line)
                        handle.flush()
                        print(line, end="", flush=True)
                returncode = int(proc.wait())
            except KeyboardInterrupt:
                handle.write("\n[runner] received KeyboardInterrupt; forwarding SIGINT to child\n")
                handle.flush()
                if proc.poll() is None:
                    proc.send_signal(signal.SIGINT)
                    try:
                        proc.wait(timeout=15)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait()
                raise
        else:
            func = stage.get("func")
            if func is None:
                raise RuntimeError(f"stage has neither command nor func: {name}")
            payload = func()
            handle.write(json.dumps(payload, indent=2, default=str))
            handle.write("\n")
            returncode = 0
        handle.write(f"\n[runner] returncode={returncode}\n")
    finished = datetime.now(IST)
    return StageResult(
        name=name,
        status="PASS" if returncode == 0 else "FAIL",
        required=required,
        command=command,
        started_at=started.isoformat(),
        finished_at=finished.isoformat(),
        duration_seconds=round((finished - started).total_seconds(), 3),
        returncode=returncode,
        log_path=str(log_path),
    )


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def stop_live_options_engine() -> dict[str, Any]:
    heartbeat = _read_json(LIVE_HEARTBEAT_PATH)
    pid = int(heartbeat.get("pid") or 0)
    if pid <= 0:
        return {"status": "noop", "reason": "no_live_engine_pid"}
    if not _pid_alive(pid):
        return {"status": "noop", "reason": "pid_not_running", "pid": pid}

    os.kill(pid, signal.SIGINT)
    deadline = datetime.now(IST) + timedelta(seconds=90)
    while datetime.now(IST) < deadline:
        if (not _pid_alive(pid)) and (not LIVE_LOCK_PATH.exists()):
            return {"status": "stopped", "pid": pid, "signal": "SIGINT"}
        time.sleep(1.0)

    if _pid_alive(pid):
        os.kill(pid, signal.SIGTERM)
    deadline = datetime.now(IST) + timedelta(seconds=30)
    while datetime.now(IST) < deadline:
        if (not _pid_alive(pid)) and (not LIVE_LOCK_PATH.exists()):
            return {"status": "stopped", "pid": pid, "signal": "SIGTERM"}
        time.sleep(1.0)

    raise RuntimeError(f"live_options_engine_stop_timeout pid={pid}")


def write_summary(run_dir: Path, args: argparse.Namespace, results: list[StageResult]) -> None:
    payload = {
        "runner": "post_close_pipeline",
        "date": args.date,
        "proof_level": args.proof_level,
        "skip_close_guard": bool(args.skip_close_guard),
        "grace_minutes": int(args.grace_minutes),
        "generated_at": datetime.now(IST).isoformat(),
        "failed_required_stage_count": sum(1 for item in results if item.required and item.status == "FAIL"),
        "failed_optional_stage_count": sum(1 for item in results if (not item.required) and item.status == "FAIL"),
        "stage_results": [asdict(item) for item in results],
    }
    (run_dir / "summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the canonical post-close Northstar V3 refresh workflow.")
    parser.add_argument("--date", type=str, default="today")
    parser.add_argument("--proof-level", choices=["none", "standard", "full"], default="standard")
    parser.add_argument("--alt-start-year", type=int, default=2024)
    parser.add_argument("--alt-end-year", type=int, default=datetime.now().year)
    parser.add_argument("--news-sources", type=str, default="nse,rss")
    parser.add_argument("--news-max-tickers", type=int, default=0)
    parser.add_argument("--news-max-months", type=int, default=0)
    parser.add_argument("--force-gst", action="store_true")
    parser.add_argument("--grace-minutes", type=int, default=30, help="Delay after 15:30 IST before the workflow may start.")
    parser.add_argument("--skip-close-guard", action="store_true", help="Allow manual runs before the post-close guard window.")
    parser.add_argument("--stop-live-engine", action="store_true", default=True, help="Stop the live options engine before post-close processing.")
    parser.add_argument("--no-stop-live-engine", action="store_false", dest="stop_live_engine")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    resolve_date(args.date)
    if not args.skip_close_guard:
        ensure_post_close(args.grace_minutes)

    run_id = datetime.now(IST).strftime("%Y%m%d_%H%M%S")
    run_dir = PROJECT_ROOT / "data" / "operations" / "post_close_runs" / run_id
    logs_dir = run_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    stages = build_stage_plan(args)
    print("=" * 88)
    print("NORTHSTAR V3 POST-CLOSE PIPELINE")
    print("=" * 88)
    print(f"Run ID: {run_id}")
    print(f"Date: {args.date}")
    print(f"Artifacts: {run_dir}")

    if args.dry_run:
        print("\nPlanned stages:")
        for stage in stages:
            command = list(stage.get("command", []))
            if command:
                detail = " ".join(command)
            else:
                detail = f"function:{getattr(stage.get('func'), '__name__', 'unknown')}"
            print(f"- {stage['name']}: {detail}")
        return 0

    results: list[StageResult] = []
    try:
        for stage in stages:
            name = str(stage["name"])
            command = list(stage.get("command", []))
            if command:
                print(f"[{name}] START")
                print(f"[{name}] command: {' '.join(command)}")
            else:
                print(f"[{name}] START")
            result = run_stage(stage, logs_dir)
            results.append(result)
            print(f"[{result.name}] {result.status} ({result.duration_seconds:.1f}s)")
            print(f"[{result.name}] log: {result.log_path}")
            if result.required and result.status == "FAIL":
                write_summary(run_dir, args, results)
                return 1
    except KeyboardInterrupt:
        interrupted_at = datetime.now(IST)
        interrupted_log = logs_dir / "runner_interrupted.log"
        interrupted_log.write_text(
            json.dumps(
                {
                    "status": "INTERRUPTED",
                    "timestamp": interrupted_at.isoformat(),
                    "message": "Post-close pipeline interrupted by user",
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        results.append(
            StageResult(
                name="Runner Interrupted",
                status="INTERRUPTED",
                required=True,
                command=[],
                started_at=interrupted_at.isoformat(),
                finished_at=interrupted_at.isoformat(),
                duration_seconds=0.0,
                returncode=130,
                log_path=str(interrupted_log),
            )
        )
        write_summary(run_dir, args, results)
        print("[Runner] INTERRUPTED")
        print(f"[Runner] log: {interrupted_log}")
        return 130

    write_summary(run_dir, args, results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
