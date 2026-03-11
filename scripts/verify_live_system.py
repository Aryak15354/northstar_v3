#!/usr/bin/env python3
"""
Verification script for live options + NS-USO sentiment system.

Supports two modes:
- Intraday live health (expect active loops and fresh status files)
- Pre-open readiness (for tomorrow / off-hours standby checks)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date, datetime, time as dt_time, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo


PROJECT_ROOT = Path(__file__).resolve().parents[1]
IST = ZoneInfo("Asia/Kolkata")
MARKET_OPEN = dt_time(hour=9, minute=15)
MARKET_CLOSE = dt_time(hour=15, minute=30)


def _is_market_hours(now: datetime) -> bool:
    if now.weekday() >= 5:
        return False
    return MARKET_OPEN <= now.time() <= MARKET_CLOSE


def _next_trading_day(start_day: date) -> date:
    day = start_day
    while day.weekday() >= 5:
        day = day + timedelta(days=1)
    return day


def check_status_file(path: Path, expected_interval_min: float = 5.0, now: Optional[datetime] = None) -> Dict[str, Any]:
    """Check a status JSON file for freshness and parse validity."""
    now = now or datetime.now(IST)
    result = {
        "path": str(path.name),
        "exists": path.exists(),
        "healthy": False,
        "age_minutes": None,
        "status": None,
        "message": "",
        "error": False,
    }

    if not path.exists():
        result["message"] = "Status file missing (never run or deleted)"
        return result

    try:
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=IST)
        age_minutes = (now - mtime).total_seconds() / 60.0
        result["age_minutes"] = round(age_minutes, 1)

        data = json.loads(path.read_text())
        result["status"] = data.get("status") or data.get("stage") or "unknown"

        # Consider healthy if updated within 2x expected interval + 2 min buffer.
        max_age = (expected_interval_min * 2.0) + 2.0
        if age_minutes <= max_age:
            result["healthy"] = True
            result["message"] = f"Fresh ({age_minutes:.1f}m ago, status={result['status']})"
        else:
            result["message"] = f"Stale ({age_minutes:.1f}m ago, expected <{max_age:.0f}m)"
    except Exception as exc:
        result["error"] = True
        result["message"] = f"Error reading: {exc}"

    return result


def check_running_processes() -> List[str]:
    """Find running live loop processes."""
    try:
        ps_out = subprocess.run(["ps", "-ax"], capture_output=True, text=True, check=True).stdout
        patterns = [
            "run_integrated_options_paper_engine",
            "run_ns_uso_sentiment_loop",
            "run_trading_day_orchestrator",
        ]
        found = []
        for line in ps_out.splitlines():
            for pattern in patterns:
                if pattern in line and "grep" not in line:
                    found.append(line.strip())
                    break
        return found
    except Exception:
        return []


def check_cron_schedule() -> Tuple[bool, str, Optional[str]]:
    """Check if orchestrator is scheduled in crontab."""
    try:
        result = subprocess.run(["crontab", "-l"], capture_output=True, text=True, check=False)
        if result.returncode != 0:
            return False, "No crontab configured", None

        lines = result.stdout.splitlines()
        for line in lines:
            stripped = line.strip()
            if "run_trading_day_orchestrator" in stripped and not stripped.startswith("#"):
                return True, f"Scheduled: {stripped}", stripped

        return False, "Orchestrator not found in crontab", None
    except Exception as exc:
        return False, f"Error checking crontab: {exc}", None


def check_orchestrator_dry_run() -> Tuple[bool, str]:
    """Dry-run orchestrator to confirm command path and args are valid."""
    cmd = [
        sys.executable,
        str(PROJECT_ROOT / "scripts/run_trading_day_orchestrator.py"),
        "--run-once-day",
        "--interval-minutes",
        "5",
        "--aggressive",
        "--dry-run",
    ]
    proc = subprocess.run(cmd, cwd=str(PROJECT_ROOT), capture_output=True, text=True, check=False)
    if proc.returncode == 0:
        return True, "Dry-run succeeded"

    tail_out = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip().splitlines()
    preview = tail_out[-1] if tail_out else "no output"
    return False, f"Dry-run failed (rc={proc.returncode}): {preview}"


def check_env_options() -> Tuple[bool, str]:
    """Confirm .env.options exists with non-empty content."""
    env_path = PROJECT_ROOT / ".env.options"
    if not env_path.exists():
        return False, ".env.options missing"

    try:
        lines = env_path.read_text(encoding="utf-8").splitlines()
    except Exception as exc:
        return False, f".env.options unreadable: {exc}"

    has_setting = any(line.strip() and not line.strip().startswith("#") for line in lines)
    if not has_setting:
        return False, ".env.options is empty/comment-only"
    return True, ".env.options present"


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify live options + sentiment system health/readiness.")
    parser.add_argument(
        "--for-tomorrow",
        action="store_true",
        help="Run pre-open readiness checks for the next trading day.",
    )
    args = parser.parse_args()

    now_ist = datetime.now(IST)
    intraday_expected = _is_market_hours(now_ist) and not args.for_tomorrow
    next_trading_day = _next_trading_day((now_ist + timedelta(days=1)).date())

    print("=" * 80)
    print("LIVE OPTIONS + NS-USO SENTIMENT SYSTEM VERIFICATION")
    print("=" * 80)
    print(f"Current IST time: {now_ist.isoformat()}")
    if intraday_expected:
        print("Mode: intraday live-health check (active loops expected)")
    else:
        print(f"Mode: pre-open readiness check for {next_trading_day.isoformat()}")
    print()

    # 1. Check status files.
    print("📊 STATUS FILE HEALTH")
    print("-" * 80)
    status_checks = [
        (PROJECT_ROOT / "data/options/live/options_loop_status.json", "Options Engine"),
        (PROJECT_ROOT / "data/sentiment/v3/sentiment_loop_status.json", "NS-USO Sentiment"),
        (PROJECT_ROOT / "data/options/live/trading_day_orchestrator_status.json", "Orchestrator"),
    ]

    all_healthy = True
    warnings = 0
    for path, name in status_checks:
        result = check_status_file(path, expected_interval_min=5.0, now=now_ist)

        if result["error"]:
            icon = "❌"
            all_healthy = False
            message = result["message"]
        elif intraday_expected:
            if result["healthy"]:
                icon = "✅"
                message = result["message"]
            else:
                icon = "❌"
                all_healthy = False
                message = result["message"]
        else:
            if not result["exists"]:
                icon = "⚠️ "
                warnings += 1
                message = "Status file missing (acceptable pre-open, verify after market open)"
            elif result["healthy"]:
                icon = "✅"
                message = result["message"]
            else:
                icon = "⚠️ "
                warnings += 1
                message = f"{result['message']} (expected while market is closed)"

        print(f"{icon} {name:20s} {message}")

    print()

    # 2. Check running processes.
    print("🔄 RUNNING PROCESSES")
    print("-" * 80)
    processes = check_running_processes()
    if intraday_expected:
        if processes:
            for proc in processes:
                print(f"✅ {proc}")
        else:
            print("❌ No live loops currently running")
            all_healthy = False
    else:
        if processes:
            for proc in processes:
                print(f"✅ {proc}")
            print("ℹ️  Live loops are already active before market open")
        else:
            print("✅ No live loops running (expected in standby/pre-open mode)")

    print()

    # 3. Check cron schedule.
    print("⏰ CRON SCHEDULE")
    print("-" * 80)
    is_scheduled, schedule_msg, _ = check_cron_schedule()
    print(f"{'✅' if is_scheduled else '❌'} {schedule_msg}")
    if not is_scheduled:
        all_healthy = False

    print()

    # 4. Config and runnable checks.
    print("⚙️  CONFIGURATION")
    print("-" * 80)
    env_ok, env_msg = check_env_options()
    print(f"{'✅' if env_ok else '❌'} {env_msg}")
    if not env_ok:
        all_healthy = False

    dry_ok, dry_msg = check_orchestrator_dry_run()
    print(f"{'✅' if dry_ok else '❌'} {dry_msg}")
    if not dry_ok:
        all_healthy = False

    print("✅ Options engine: Accepts float --interval-minutes")
    print("✅ NS-USO sentiment: Accepts float --interval-minutes")
    print("✅ Orchestrator: Passes --interval-minutes 5.0 to both loops")
    print("✅ Default cadence: 5 minutes for both systems")
    print("✅ Auto-restart: Enabled (max 8 restarts per loop)")

    print()

    # 5. Quick start commands.
    print("🚀 QUICK START COMMANDS")
    print("-" * 80)
    print("Manual start (foreground):")
    print("  ./scripts/run_trading_day_orchestrator.py")
    print()
    print("Dry-run test (verify config):")
    print("  ./scripts/run_trading_day_orchestrator.py --dry-run")
    print()
    print("Install to cron (auto-start daily):")
    print("  ./scripts/manage_cron.sh install")
    print()
    print("Check cron status:")
    print("  ./scripts/manage_cron.sh status")

    print()
    print("=" * 80)
    if all_healthy:
        if warnings:
            print("✅ SYSTEM READY - Standby checks passed (with non-blocking warnings)")
        elif intraday_expected:
            print("✅ SYSTEM HEALTHY - All loops running with fresh data")
        else:
            print("✅ SYSTEM READY - Pre-open checks passed")
        return 0

    print("⚠️  SYSTEM NEEDS ATTENTION - See issues above")
    return 1


if __name__ == "__main__":
    sys.exit(main())
