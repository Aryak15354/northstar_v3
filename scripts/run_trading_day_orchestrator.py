#!/usr/bin/env python3
"""
Northstar trading-day orchestrator.

Intraday (trading hours):
- Runs canonical market refresh loop (5m cadence by default)
- Runs Upstox options engine loop (5m cadence by default)
- Runs canonical sentiment loop (5m cadence by default)
- Restarts loops if a process exits unexpectedly

End-of-day:
- Force market ingestion from yfinance
- Force RBI scraper -> processor -> cleaner chain
- Recompute integrated market state
- Run complete Northstar V3 computation stack
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime, time as dt_time, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from zoneinfo import ZoneInfo


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_UNDERLYINGS = "NIFTY,BANKNIFTY,FINNIFTY,RELIANCE,TCS,HDFCBANK,INFY,ICICIBANK,SBIN"
DEFAULT_STATUS_PATH = PROJECT_ROOT / "data/options/live/trading_day_orchestrator_status.json"
DEFAULT_EOD_STATE_PATH = PROJECT_ROOT / "data/options/live/trading_day_orchestrator_eod_state.json"
DEFAULT_LOCK_PATH = PROJECT_ROOT / "data/options/live/trading_day_orchestrator.lock"
OPTIONS_LOOP_STATUS_PATH = PROJECT_ROOT / "data/options/live/options_loop_status.json"
OPTIONS_HEARTBEAT_PATH = PROJECT_ROOT / "data/options/live/live_engine_heartbeat.json"
SENTIMENT_STATUS_PATH = PROJECT_ROOT / "data/sentiment/v3/sentiment_loop_status.json"
MARKET_STATUS_PATH = PROJECT_ROOT / "data/processed/market_refresh_status.json"
ACCOUNTING_SNAPSHOT_PATH = PROJECT_ROOT / "data/pnl/accounting_snapshot.json"


@dataclass
class ManagedProcess:
    name: str
    command: List[str]
    log_path: Path
    process: Optional[subprocess.Popen] = None
    restart_count: int = 0

    def is_running(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def start(self, logger: logging.Logger) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        log_file = open(self.log_path, "a", encoding="utf-8")
        self.process = subprocess.Popen(
            self.command,
            cwd=str(PROJECT_ROOT),
            stdout=log_file,
            stderr=subprocess.STDOUT,
            text=True,
        )
        logger.info("%s started pid=%s", self.name, self.process.pid)

    def stop(self, logger: logging.Logger, timeout_seconds: float = 15.0) -> None:
        if self.process is None:
            return
        proc = self.process
        if proc.poll() is None:
            logger.info("Stopping %s pid=%s", self.name, proc.pid)
            try:
                proc.terminate()
                proc.wait(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                logger.warning("%s did not stop gracefully; killing pid=%s", self.name, proc.pid)
                proc.kill()
                proc.wait(timeout=5)
            except Exception as exc:
                logger.warning("Error stopping %s: %s", self.name, exc)
        self.process = None


class InstanceLock:
    def __init__(self, path: Path, payload: Dict[str, Any]):
        self.path = path
        self.payload = payload
        self.acquired = False

    @staticmethod
    def _pid_alive(pid: int) -> bool:
        if pid <= 0:
            return False
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        while True:
            try:
                fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                try:
                    existing = json.loads(self.path.read_text(encoding="utf-8"))
                except Exception:
                    existing = {}
                existing_pid = int(existing.get("pid", 0) or 0)
                if self._pid_alive(existing_pid):
                    raise RuntimeError(
                        f"trading_day_orchestrator already running with pid={existing_pid}"
                    )
                self.path.unlink(missing_ok=True)
                continue

            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(json.dumps(self.payload, indent=2))
            self.acquired = True
            return

    def release(self) -> None:
        if self.acquired:
            self.path.unlink(missing_ok=True)
            self.acquired = False


def _parse_hhmm(value: str) -> dt_time:
    parts = value.strip().split(":")
    if len(parts) != 2:
        raise ValueError(f"Invalid HH:MM time: {value}")
    hour = int(parts[0])
    minute = int(parts[1])
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        raise ValueError(f"Invalid HH:MM time: {value}")
    return dt_time(hour=hour, minute=minute)


def _load_holidays(path: Path) -> Set[date]:
    holidays: Set[date] = set()
    if not path.exists():
        return holidays
    try:
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            token = line.split(",")[0].strip()
            try:
                holidays.add(date.fromisoformat(token))
            except ValueError:
                continue
    except Exception:
        return set()
    return holidays


def _is_trading_day(day: date, holidays: Set[date]) -> bool:
    return day.weekday() < 5 and day not in holidays


def _next_trading_day(start_day: date, holidays: Set[date]) -> date:
    day = start_day
    while not _is_trading_day(day, holidays):
        day = day + timedelta(days=1)
    return day


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _parse_timestamp(value: Any) -> Optional[datetime]:
    if value in (None, "", "None"):
        return None
    try:
        return datetime.fromisoformat(str(value))
    except Exception:
        return None


def _json_age_seconds(path: Path, timestamp_keys: List[str]) -> Optional[float]:
    payload = _read_json(path)
    if not payload:
        return None
    for key in timestamp_keys:
        ts = _parse_timestamp(payload.get(key))
        if ts is None:
            continue
        now = datetime.now(ts.tzinfo) if ts.tzinfo is not None else datetime.now()
        return max(0.0, (now - ts).total_seconds())
    return None


def _status_value(path: Path, key: str) -> Optional[str]:
    payload = _read_json(path)
    if not payload:
        return None
    value = payload.get(key)
    if value is None:
        return None
    return str(value)


def _sleep_until(target: datetime, check_seconds: float = 30.0) -> None:
    while True:
        now = datetime.now(target.tzinfo)
        if now >= target:
            return
        remaining = (target - now).total_seconds()
        time.sleep(max(1.0, min(check_seconds, remaining)))


def _configure_logger(log_path: Path) -> logging.Logger:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("northstar.trading_day_orchestrator")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    fmt = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    fh = logging.FileHandler(log_path)
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    if sys.stdout.isatty():
        sh = logging.StreamHandler()
        sh.setFormatter(fmt)
        logger.addHandler(sh)
    return logger


def _build_options_command(args: argparse.Namespace) -> List[str]:
    cmd: List[str] = [
        args.python_bin,
        str(PROJECT_ROOT / "scripts/run_integrated_options_paper_engine.py"),
        "--mode",
        "continuous",
        "--interval-minutes",
        str(args.interval_minutes),
        "--underlyings",
        args.underlyings,
        "--market-hours-only",
        "--portfolio-overlay-max-stocks",
        str(args.portfolio_overlay_max_stocks),
    ]
    if args.aggressive:
        cmd.append("--aggressive")
    if args.no_max_trades_limit:
        cmd.append("--no-max-trades-limit")
    if args.max_trades_per_week is not None:
        cmd.extend(["--max-trades-per-week", str(args.max_trades_per_week)])
    if args.portfolio_risk_cap_pct is not None:
        cmd.extend(["--portfolio-risk-cap-pct", str(args.portfolio_risk_cap_pct)])
    if args.disable_portfolio_overlay:
        cmd.append("--disable-portfolio-overlay")
    if args.start_fresh_today:
        cmd.append("--start-fresh-today")
    else:
        cmd.append("--no-start-fresh-today")
    return cmd


def _build_market_command(args: argparse.Namespace) -> List[str]:
    return [
        args.python_bin,
        str(PROJECT_ROOT / "scripts/run_5min_market_updates.py"),
        "--interval-minutes",
        str(args.interval_minutes),
    ]


def _build_market_once_command(args: argparse.Namespace) -> List[str]:
    return [
        args.python_bin,
        str(PROJECT_ROOT / "scripts/run_5min_market_updates.py"),
        "--once",
        "--allow-outside-market-hours",
    ]


def _build_sentiment_command(args: argparse.Namespace) -> List[str]:
    return [
        args.python_bin,
        str(PROJECT_ROOT / "scripts/run_ns_uso_sentiment_loop.py"),
        "--interval-minutes",
        str(args.interval_minutes),
    ]


def _build_no_edge_command(args: argparse.Namespace, session_date: date) -> List[str]:
    return [
        args.python_bin,
        str(PROJECT_ROOT / "src/intelligence/no_edge_detector.py"),
        "--recalculate",
        "--date",
        session_date.isoformat(),
    ]


def _build_canonical_sync_command(args: argparse.Namespace, session_date: date, run_label: str) -> List[str]:
    return [
        args.python_bin,
        str(PROJECT_ROOT / "scripts/runners/sync_canonical_state.py"),
        "--date",
        session_date.isoformat(),
        "--run-label",
        run_label,
    ]


def _run_step(
    logger: logging.Logger,
    step_name: str,
    cmd: List[str],
    log_path: Path,
    timeout_seconds: Optional[int],
) -> bool:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    start = datetime.now()
    logger.info("EOD step start: %s", step_name)
    logger.info("Command: %s", " ".join(cmd))
    with open(log_path, "a", encoding="utf-8") as f:
        f.write("\n" + "=" * 120 + "\n")
        f.write(f"[{start.isoformat()}] STEP={step_name}\n")
        f.write("CMD=" + " ".join(cmd) + "\n\n")
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(PROJECT_ROOT),
                stdout=f,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
            ok = proc.returncode == 0
            f.write(f"\nRETURN_CODE={proc.returncode}\n")
        except subprocess.TimeoutExpired:
            ok = False
            f.write(f"\nTIMEOUT after {timeout_seconds}s\n")
        except Exception as exc:
            ok = False
            f.write(f"\nERROR: {exc}\n")
    elapsed = (datetime.now() - start).total_seconds()
    if ok:
        logger.info("EOD step done: %s (%.1fs)", step_name, elapsed)
    else:
        logger.error("EOD step failed: %s (%.1fs)", step_name, elapsed)
    return ok


def _run_market_fast_recovery(
    logger: logging.Logger,
    args: argparse.Namespace,
    session_date: date,
    status_path: Path,
    *,
    reason: str,
) -> bool:
    runtime_log = PROJECT_ROOT / "logs/trading_day_runtime_sync.log"
    ok = _run_step(
        logger,
        "market_fast_recovery_refresh",
        _build_market_once_command(args),
        runtime_log,
        min(args.runtime_sync_timeout_seconds, 900),
    )
    _update_runtime_status(
        status_path,
        args.timezone,
        session_date,
        "intraday_market_fast_recovery",
        [],
        {
            "reason": reason,
            "market_fast_recovery_ok": bool(ok),
        },
    )
    return ok


def _run_preflight(
    logger: logging.Logger,
    args: argparse.Namespace,
    session_date: date,
    status_path: Path,
) -> bool:
    preflight_log = PROJECT_ROOT / "logs/trading_day_preflight.log"
    steps = [
        (
            "upstox_connection_check",
            [
                args.python_bin,
                str(PROJECT_ROOT / "scripts/test_upstox_connection.py"),
            ],
            min(args.preflight_timeout_seconds, 300),
        ),
        (
            "sentiment_preflight_refresh",
            [
                args.python_bin,
                str(PROJECT_ROOT / "scripts/run_ns_uso_sentiment_loop.py"),
                "--once",
            ],
            min(args.preflight_timeout_seconds, 900),
        ),
        (
            "alternative_data_preflight",
            [
                args.python_bin,
                str(PROJECT_ROOT / "scripts/daily_alternative_data_pipeline.py"),
                "--nse-period",
                "1D",
            ],
            args.preflight_timeout_seconds,
        ),
        (
            "runtime_book_sync_preflight",
            [
                args.python_bin,
                str(PROJECT_ROOT / "scripts/runners/sync_live_books_to_runtime.py"),
            ],
            min(args.preflight_timeout_seconds, 600),
        ),
        (
            "runtime_accounting_preflight",
            [
                args.python_bin,
                str(PROJECT_ROOT / "scripts/runners/refresh_runtime_accounting.py"),
            ],
            min(args.preflight_timeout_seconds, 900),
        ),
        (
            "current_positions_snapshot_preflight",
            [
                args.python_bin,
                str(PROJECT_ROOT / "scripts/runners/sync_current_positions.py"),
            ],
            min(args.preflight_timeout_seconds, 600),
        ),
        (
            "no_edge_refresh_preflight",
            _build_no_edge_command(args, session_date),
            min(args.preflight_timeout_seconds, 900),
        ),
        (
            "canonical_state_sync_preflight",
            _build_canonical_sync_command(args, session_date, "preflight"),
            min(args.preflight_timeout_seconds, 1200),
        ),
        (
            "strict_options_runtime_check",
            [
                args.python_bin,
                str(PROJECT_ROOT / "scripts/ci/strict_options_runtime_check.py"),
            ],
            min(args.preflight_timeout_seconds, 300),
        ),
        (
            "preopen_guardrail_check",
            [
                args.python_bin,
                str(PROJECT_ROOT / "scripts/preopen_checks.py"),
            ],
            min(args.preflight_timeout_seconds, 900),
        ),
    ]

    logger.info("Running preflight checks for %s", session_date.isoformat())
    results: List[Dict[str, Any]] = []
    overall_ok = True
    for step_name, cmd, timeout_seconds in steps:
        ok = _run_step(logger, step_name, cmd, preflight_log, timeout_seconds)
        results.append(
            {
                "step": step_name,
                "ok": bool(ok),
                "timestamp": datetime.now(ZoneInfo(args.timezone)).isoformat(),
            }
        )
        if not ok:
            overall_ok = False
            break

    _update_runtime_status(
        status_path,
        args.timezone,
        session_date,
        "preflight_ok" if overall_ok else "preflight_failed",
        [],
        {"preflight_results": results},
    )
    return overall_ok


def _intraday_guard_status(now: datetime, args: argparse.Namespace) -> Dict[str, Any]:
    return {
        "market_status_age_seconds": _json_age_seconds(MARKET_STATUS_PATH, ["finished_at", "timestamp"]),
        "options_status_age_seconds": _json_age_seconds(
            OPTIONS_LOOP_STATUS_PATH,
            ["last_cycle_finished_at", "last_success_at", "timestamp"],
        ),
        "options_heartbeat_age_seconds": _json_age_seconds(OPTIONS_HEARTBEAT_PATH, ["timestamp"]),
        "sentiment_status_age_seconds": _json_age_seconds(
            SENTIMENT_STATUS_PATH,
            ["finished_at", "timestamp"],
        ),
        "accounting_snapshot_age_seconds": _json_age_seconds(ACCOUNTING_SNAPSHOT_PATH, ["timestamp"]),
        "options_status": _status_value(OPTIONS_LOOP_STATUS_PATH, "status"),
        "sentiment_status": _status_value(SENTIMENT_STATUS_PATH, "status"),
        "market_pipeline_status": _status_value(MARKET_STATUS_PATH, "pipeline_status"),
    }


def _run_runtime_sync_bundle(
    logger: logging.Logger,
    args: argparse.Namespace,
    session_date: date,
    status_path: Path,
) -> None:
    runtime_log = PROJECT_ROOT / "logs/trading_day_runtime_sync.log"
    sync_ok = _run_step(
        logger,
        "runtime_book_sync",
        [args.python_bin, str(PROJECT_ROOT / "scripts/runners/sync_live_books_to_runtime.py")],
        runtime_log,
        min(args.runtime_sync_timeout_seconds, 600),
    )
    accounting_ok = _run_step(
        logger,
        "runtime_accounting_refresh",
        [args.python_bin, str(PROJECT_ROOT / "scripts/runners/refresh_runtime_accounting.py")],
        runtime_log,
        min(args.runtime_sync_timeout_seconds, 900),
    )
    positions_ok = _run_step(
        logger,
        "current_positions_snapshot",
        [args.python_bin, str(PROJECT_ROOT / "scripts/runners/sync_current_positions.py")],
        runtime_log,
        min(args.runtime_sync_timeout_seconds, 600),
    )
    no_edge_ok = _run_step(
        logger,
        "no_edge_refresh",
        _build_no_edge_command(args, session_date),
        runtime_log,
        min(args.runtime_sync_timeout_seconds, 900),
    )
    canonical_sync_ok = _run_step(
        logger,
        "canonical_state_sync",
        _build_canonical_sync_command(args, session_date, "intraday"),
        runtime_log,
        min(args.runtime_sync_timeout_seconds, 1200),
    )
    strict_ok = _run_step(
        logger,
        "strict_options_runtime_check",
        [args.python_bin, str(PROJECT_ROOT / "scripts/ci/strict_options_runtime_check.py")],
        runtime_log,
        min(args.runtime_sync_timeout_seconds, 300),
    )
    _update_runtime_status(
        status_path,
        args.timezone,
        session_date,
        "intraday_runtime_sync",
        [],
        {
            "runtime_book_sync_ok": bool(sync_ok),
            "runtime_accounting_ok": bool(accounting_ok),
            "current_positions_snapshot_ok": bool(positions_ok),
            "no_edge_refresh_ok": bool(no_edge_ok),
            "canonical_state_sync_ok": bool(canonical_sync_ok),
            "strict_options_runtime_ok": bool(strict_ok),
        },
    )


def _run_intraday_intelligence_cycle(
    logger: logging.Logger,
    args: argparse.Namespace,
    session_date: date,
    status_path: Path,
) -> None:
    """Run the news brain intraday and trigger an emergency sync on high-severity shocks."""
    try:
        from scripts.run_complete_v3_system import load_system_config
        from src.intelligence.news_brain.news_brain import NewsBrain

        config = load_system_config()
        brain = NewsBrain(config)
        intel_state = brain.run_cycle(as_of_datetime=datetime.now(ZoneInfo(args.timezone)))
        if intel_state is None or not getattr(intel_state, "available", False):
            return
        if getattr(intel_state, "is_stale", False):
            logger.info("Intraday intelligence cycle returned stale state; skipping escalation")
            return

        if intel_state.shock_severity.value >= 3:
            flag_payload = {
                "shock_type": intel_state.primary_shock_type.value,
                "severity": intel_state.shock_severity.name,
                "requires_immediate_hedge": bool(intel_state.requires_immediate_hedge),
                "written_at": datetime.now(ZoneInfo(args.timezone)).isoformat(),
            }
            flag_path = PROJECT_ROOT / "data" / "intelligence" / "urgent_shock_flag.json"
            _write_json(flag_path, flag_payload)
            logger.warning(
                "INTRADAY SHOCK DETECTED: %s severity=%s confidence=%.2f",
                intel_state.primary_shock_type.value,
                intel_state.shock_severity.name,
                float(getattr(intel_state, "shock_confidence", 0.0) or 0.0),
            )
            _run_runtime_sync_bundle(logger, args, session_date, status_path)
    except Exception as exc:
        logger.error("Intraday intelligence cycle failed: %s", exc)


def _update_governor_recovery_state(logger: logging.Logger) -> bool:
    """Refresh governor recovery bookkeeping after the EOD pipeline succeeds."""
    try:
        from scripts.run_complete_v3_system import load_system_config
        from src.core.state import UnifiedState
        from src.portfolio.governor import PortfolioGovernor

        state_path = PROJECT_ROOT / "data" / "state" / "unified_state.json"
        if not state_path.exists():
            logger.error("Governor recovery update skipped: unified state not found at %s", state_path)
            return False

        state = UnifiedState.load_snapshot_file(state_path)
        governor = PortfolioGovernor(config=load_system_config(), data_dir=str(PROJECT_ROOT / "data"))

        current_drawdown = float(getattr(state.pnl_state, "current_drawdown_pct", 0.0) or 0.0)
        current_regime = str(
            getattr(state.governor_state, "capital_structure_regime", None)
            or governor.persistent_state.get("last_decision_regime", "STANDARD")
        )

        if current_drawdown < -8.0:
            governor.reset_recovery_counter()
            logger.info("Governor recovery state reset after EOD drawdown %.2f%%", current_drawdown)
        elif current_drawdown > -3.0:
            governor.increment_recovery_counter(current_drawdown, current_regime=current_regime)
        else:
            logger.info(
                "Governor recovery state unchanged after EOD drawdown %.2f%% (between trigger and activation)",
                current_drawdown,
            )
        return True
    except Exception as exc:
        logger.error("Governor recovery update failed: %s", exc)
        return False


def _run_eod_pipeline(
    logger: logging.Logger,
    args: argparse.Namespace,
    session_date: date,
    eod_state_path: Path,
) -> bool:
    state = _read_json(eod_state_path)
    if (
        not args.force_eod
        and state.get("date") == session_date.isoformat()
        and state.get("status") == "success"
    ):
        logger.info("EOD pipeline already completed for %s; skipping", session_date.isoformat())
        return True

    eod_log = PROJECT_ROOT / "logs/trading_day_eod.log"
    refresh_cmd: List[str] = [
        args.python_bin,
        str(PROJECT_ROOT / "scripts/runners/refresh_v3_artifacts.py"),
        "--quick" if args.eod_v3_mode == "quick" else "",
        "--skip-index",
        "--skip-integrity-audit",
    ]
    refresh_cmd = [token for token in refresh_cmd if token]

    steps = [
        (
            "runtime_book_sync",
            [
                args.python_bin,
                str(PROJECT_ROOT / "scripts/runners/sync_live_books_to_runtime.py"),
            ],
            min(args.eod_step_timeout_seconds, 600),
        ),
        (
            "runtime_accounting_refresh",
            [
                args.python_bin,
                str(PROJECT_ROOT / "scripts/runners/refresh_runtime_accounting.py"),
            ],
            min(args.eod_step_timeout_seconds, 900),
        ),
        (
            "current_positions_snapshot",
            [
                args.python_bin,
                str(PROJECT_ROOT / "scripts/runners/sync_current_positions.py"),
            ],
            min(args.eod_step_timeout_seconds, 600),
        ),
        (
            "market_refresh",
            [
                args.python_bin,
                str(PROJECT_ROOT / "scripts/force_market_update.py"),
            ],
            args.eod_step_timeout_seconds,
        ),
        (
            "rbi_forced_update",
            [
                args.python_bin,
                str(PROJECT_ROOT / "src/ingestion/rbi_daily_updater.py"),
                "--force",
            ],
            args.eod_step_timeout_seconds,
        ),
        (
            "market_state_integration",
            [
                args.python_bin,
                str(PROJECT_ROOT / "src/ingestion/integrated_data_pipeline.py"),
                "--integrate-only",
            ],
            args.eod_step_timeout_seconds,
        ),
        (
            "alternative_data_refresh",
            [
                args.python_bin,
                str(PROJECT_ROOT / "scripts/daily_alternative_data_pipeline.py"),
                "--nse-period",
                "1D",
            ],
            args.eod_step_timeout_seconds,
        ),
        (
            "artifact_refresh",
            refresh_cmd,
            args.eod_full_timeout_seconds,
        ),
    ]
    if not args.skip_periodic_reports:
        steps.append(
            (
                "periodic_reports_generation",
                [
                    args.python_bin,
                    str(PROJECT_ROOT / "scripts/generate_periodic_reports.py"),
                    "--timezone",
                    args.timezone,
                ],
                args.eod_step_timeout_seconds,
            )
        )
    if not args.skip_options_backtest:
        steps.append(
            (
                "options_backtester_refresh",
                [
                    args.python_bin,
                    str(PROJECT_ROOT / "scripts/run_options_backtester.py"),
                    "--underlyings",
                    args.underlyings,
                ],
                args.eod_step_timeout_seconds,
            )
        )
    steps.append(
        (
            "strict_system_update_check",
            [
                args.python_bin,
                str(PROJECT_ROOT / "scripts/ci/strict_system_update_check.py"),
            ],
            min(args.eod_step_timeout_seconds, 900),
        )
    )

    results: List[Dict[str, Any]] = []
    overall_ok = True
    for step_name, cmd, timeout_seconds in steps:
        ok = _run_step(logger, step_name, cmd, eod_log, timeout_seconds)
        results.append(
            {
                "step": step_name,
                "ok": bool(ok),
                "timestamp": datetime.now(ZoneInfo(args.timezone)).isoformat(),
            }
        )
        if not ok:
            overall_ok = False
            break

    if overall_ok:
        recovery_ok = _update_governor_recovery_state(logger)
        results.append(
            {
                "step": "governor_recovery_state_update",
                "ok": bool(recovery_ok),
                "timestamp": datetime.now(ZoneInfo(args.timezone)).isoformat(),
            }
        )
        overall_ok = overall_ok and recovery_ok

    _write_json(
        eod_state_path,
        {
            "date": session_date.isoformat(),
            "status": "success" if overall_ok else "failed",
            "timestamp": datetime.now(ZoneInfo(args.timezone)).isoformat(),
            "results": results,
            "log_path": str(eod_log),
        },
    )
    return overall_ok


def _session_window(day: date, tz: ZoneInfo, open_t: dt_time, close_t: dt_time) -> tuple[datetime, datetime]:
    start = datetime.combine(day, open_t, tzinfo=tz)
    end = datetime.combine(day, close_t, tzinfo=tz)
    return start, end


def _update_runtime_status(
    status_path: Path,
    timezone_name: str,
    session_date: date,
    stage: str,
    processes: List[ManagedProcess],
    details: Optional[Dict[str, Any]] = None,
) -> None:
    payload: Dict[str, Any] = {
        "timestamp": datetime.now(ZoneInfo(timezone_name)).isoformat(),
        "session_date": session_date.isoformat(),
        "stage": stage,
        "processes": [
            {
                "name": p.name,
                "pid": p.process.pid if p.process is not None else None,
                "running": p.is_running(),
                "restart_count": p.restart_count,
                "log_path": str(p.log_path),
            }
            for p in processes
        ],
    }
    if details:
        payload["details"] = details
    _write_json(status_path, payload)


def _run_intraday(
    logger: logging.Logger,
    args: argparse.Namespace,
    session_date: date,
    close_dt: datetime,
    status_path: Path,
) -> bool:
    loops = [
        ManagedProcess(
            name="market_loop",
            command=_build_market_command(args),
            log_path=PROJECT_ROOT / "logs/market_loop.log",
        ),
        ManagedProcess(
            name="sentiment_loop",
            command=_build_sentiment_command(args),
            log_path=PROJECT_ROOT / "logs/sentiment_loop.log",
        ),
    ]
    if not args.skip_options_loop:
        loops.insert(
            1,
            ManagedProcess(
                name="options_engine",
                command=_build_options_command(args),
                log_path=PROJECT_ROOT / "logs/options_engine_loop.log",
            ),
        )

    logger.info("Starting intraday loops for %s", session_date.isoformat())
    for loop in loops:
        loop.start(logger)
    _update_runtime_status(status_path, args.timezone, session_date, "intraday_running", loops)
    next_runtime_sync_at = time.time() + max(60.0, float(args.runtime_sync_minutes) * 60.0)
    next_intelligence_cycle_at = time.time()

    intraday_ok = True
    try:
        while datetime.now(close_dt.tzinfo) <= close_dt:
            for loop in loops:
                if loop.is_running():
                    continue
                intraday_ok = False
                rc = loop.process.returncode if loop.process is not None else None
                logger.warning("%s exited unexpectedly (rc=%s)", loop.name, rc)
                if loop.restart_count >= args.max_loop_restarts:
                    logger.error(
                        "%s restart limit reached (%s); not restarting",
                        loop.name,
                        args.max_loop_restarts,
                    )
                    continue
                loop.restart_count += 1
                time.sleep(max(1.0, float(args.restart_cooldown_seconds)))
                loop.start(logger)

            guard_status = _intraday_guard_status(datetime.now(close_dt.tzinfo), args)
            options_heartbeat_age = guard_status.get("options_heartbeat_age_seconds")
            if (
                options_heartbeat_age is not None
                and options_heartbeat_age > float(args.options_stale_minutes) * 60.0
            ):
                for loop in loops:
                    if loop.name != "options_engine":
                        continue
                    logger.warning(
                        "Options heartbeat stale for %.1fs; recycling options engine",
                        float(options_heartbeat_age),
                    )
                    intraday_ok = False
                    loop.stop(logger)
                    if loop.restart_count < args.max_loop_restarts:
                        loop.restart_count += 1
                        time.sleep(max(1.0, float(args.restart_cooldown_seconds)))
                        loop.start(logger)
                    break

            sentiment_status = str(guard_status.get("sentiment_status") or "").strip().lower()
            sentiment_age = guard_status.get("sentiment_status_age_seconds")
            if (
                sentiment_status == "failed"
                or (
                    sentiment_age is not None
                    and sentiment_age > float(args.sentiment_stale_minutes) * 60.0
                )
            ):
                for loop in loops:
                    if loop.name != "sentiment_loop":
                        continue
                    logger.warning(
                        "Sentiment loop stale/failed (status=%s age=%.1fs); recycling sentiment loop",
                        sentiment_status or "unknown",
                        float(sentiment_age or 0.0),
                    )
                    intraday_ok = False
                    loop.stop(logger)
                    if loop.restart_count < args.max_loop_restarts:
                        loop.restart_count += 1
                        time.sleep(max(1.0, float(args.restart_cooldown_seconds)))
                        loop.start(logger)
                    break

            market_status = str(guard_status.get("market_pipeline_status") or "").strip().upper()
            market_age = guard_status.get("market_status_age_seconds")
            if market_status == "FAILED" or (
                market_age is not None
                and market_age > float(args.market_stale_minutes) * 60.0
            ):
                recovery_reason = (
                    f"status={market_status or 'UNKNOWN'}"
                    if market_status == "FAILED"
                    else f"stale_age_seconds={float(market_age or 0.0):.1f}"
                )
                recovery_ok = _run_market_fast_recovery(
                    logger,
                    args,
                    session_date,
                    status_path,
                    reason=recovery_reason,
                )
                for loop in loops:
                    if loop.name != "market_loop":
                        continue
                    logger.warning(
                        "Market loop stale/failed (status=%s age=%.1fs recovery_ok=%s); recycling market loop",
                        market_status or "UNKNOWN",
                        float(market_age or 0.0),
                        recovery_ok,
                    )
                    intraday_ok = False
                    loop.stop(logger)
                    if loop.restart_count < args.max_loop_restarts:
                        loop.restart_count += 1
                        time.sleep(max(1.0, float(args.restart_cooldown_seconds)))
                        loop.start(logger)
                    break

            if time.time() >= next_runtime_sync_at:
                _run_runtime_sync_bundle(logger, args, session_date, status_path)
                next_runtime_sync_at = time.time() + max(60.0, float(args.runtime_sync_minutes) * 60.0)

            if time.time() >= next_intelligence_cycle_at:
                _run_intraday_intelligence_cycle(logger, args, session_date, status_path)
                next_intelligence_cycle_at = time.time() + 15.0 * 60.0

            _update_runtime_status(
                status_path,
                args.timezone,
                session_date,
                "intraday_running",
                loops,
                details={"market_close": close_dt.isoformat(), "guards": guard_status},
            )
            time.sleep(max(5.0, float(args.monitor_seconds)))
    finally:
        logger.info("Market window closed; stopping intraday loops")
        for loop in loops:
            loop.stop(logger)
        _update_runtime_status(status_path, args.timezone, session_date, "intraday_stopped", loops)

    return intraday_ok


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Northstar trading-day orchestration.")
    parser.add_argument("--timezone", type=str, default="Asia/Kolkata")
    parser.add_argument("--market-open", type=str, default="09:15")
    parser.add_argument("--market-close", type=str, default="15:30")
    parser.add_argument("--interval-minutes", type=float, default=15.0)
    parser.add_argument("--monitor-seconds", type=float, default=20.0)
    parser.add_argument("--restart-cooldown-seconds", type=float, default=10.0)
    parser.add_argument("--max-loop-restarts", type=int, default=8)
    parser.add_argument("--run-once-day", action="store_true")
    parser.add_argument("--force-eod", action="store_true")
    parser.add_argument("--holidays-file", type=str, default="config/nse_holidays.txt")
    parser.add_argument("--python-bin", type=str, default=sys.executable)
    parser.add_argument("--underlyings", type=str, default=DEFAULT_UNDERLYINGS)
    parser.add_argument("--aggressive", action="store_true")
    parser.add_argument("--max-trades-per-week", type=int, default=None)
    parser.add_argument("--portfolio-risk-cap-pct", type=float, default=None)
    parser.add_argument("--no-max-trades-limit", action="store_true")
    parser.add_argument("--disable-portfolio-overlay", action="store_true")
    parser.add_argument("--portfolio-overlay-max-stocks", type=int, default=6)
    parser.add_argument("--skip-options-loop", action="store_true")
    parser.add_argument(
        "--start-fresh-today",
        dest="start_fresh_today",
        action="store_true",
        help="Reset options runtime/ledger state when pre-today entries are detected",
    )
    parser.add_argument(
        "--no-start-fresh-today",
        dest="start_fresh_today",
        action="store_false",
        help="Disable automatic trading-day state reset checks for the options loop",
    )
    parser.set_defaults(start_fresh_today=False)
    parser.add_argument("--eod-step-timeout-seconds", type=int, default=3600)
    parser.add_argument("--eod-full-timeout-seconds", type=int, default=4 * 3600)
    parser.add_argument("--eod-v3-mode", type=str, choices=["quick", "full"], default="quick")
    parser.add_argument("--eod-force-data", action="store_true")
    parser.add_argument("--eod-skip-integration-alignment", action="store_true")
    parser.add_argument("--skip-periodic-reports", action="store_true")
    parser.add_argument("--skip-options-backtest", action="store_true")
    parser.add_argument("--status-path", type=str, default=str(DEFAULT_STATUS_PATH))
    parser.add_argument("--eod-state-path", type=str, default=str(DEFAULT_EOD_STATE_PATH))
    parser.add_argument("--lock-path", type=str, default=str(DEFAULT_LOCK_PATH))
    parser.add_argument("--log-path", type=str, default=str(PROJECT_ROOT / "logs/trading_day_orchestrator.log"))
    parser.add_argument("--preflight-timeout-seconds", type=int, default=1800)
    parser.add_argument("--runtime-sync-timeout-seconds", type=int, default=1200)
    parser.add_argument("--runtime-sync-minutes", type=float, default=15.0)
    parser.add_argument("--market-stale-minutes", type=float, default=15.0)
    parser.add_argument("--options-stale-minutes", type=float, default=15.0)
    parser.add_argument("--sentiment-stale-minutes", type=float, default=15.0)
    parser.add_argument("--skip-preflight", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Print resolved schedule and commands, then exit")
    args = parser.parse_args()

    tz = ZoneInfo(args.timezone)
    open_t = _parse_hhmm(args.market_open)
    close_t = _parse_hhmm(args.market_close)
    status_path = Path(args.status_path)
    eod_state_path = Path(args.eod_state_path)
    lock_path = Path(args.lock_path)
    logger = _configure_logger(Path(args.log_path))
    holidays = _load_holidays(PROJECT_ROOT / args.holidays_file)
    instance_lock = InstanceLock(
        lock_path,
        {
            "pid": os.getpid(),
            "started_at": datetime.now(tz).isoformat(),
            "script": str(PROJECT_ROOT / "scripts/run_trading_day_orchestrator.py"),
        },
    )

    logger.info("Trading-day orchestrator started")
    logger.info("Timezone=%s open=%s close=%s interval=%.1fmin", args.timezone, args.market_open, args.market_close, args.interval_minutes)
    logger.info("Underlyings=%s", args.underlyings)
    try:
        instance_lock.acquire()
    except Exception as exc:
        logger.error("Could not acquire orchestrator lock: %s", exc)
        return 1

    try:
        if args.dry_run:
            logger.info("Dry-run mode enabled; no processes will be started.")
            if args.skip_options_loop:
                logger.info("Options loop command: disabled (--skip-options-loop)")
            else:
                logger.info("Options loop command: %s", " ".join(_build_options_command(args)))
            logger.info("Market loop command: %s", " ".join(_build_market_command(args)))
            logger.info("Sentiment loop command: %s", " ".join(_build_sentiment_command(args)))
            logger.info(
                "EOD step command[artifact_refresh]: %s",
                " ".join(
                    [
                        args.python_bin,
                        str(PROJECT_ROOT / "scripts/runners/refresh_v3_artifacts.py"),
                    ]
                    + (["--quick"] if args.eod_v3_mode == "quick" else [])
                    + ["--skip-index", "--skip-integrity-audit"]
                ),
            )
            return 0

        while True:
            now = datetime.now(tz)
            today = now.date()
            if not _is_trading_day(today, holidays):
                if args.run_once_day:
                    logger.info("Today (%s) is not a trading day. Exiting due to --run-once-day.", today.isoformat())
                    return 0
                next_day = _next_trading_day(today + timedelta(days=1), holidays)
                next_open, _ = _session_window(next_day, tz, open_t, close_t)
                logger.info("Non-trading day. Sleeping until next trading open: %s", next_open.isoformat())
                _sleep_until(next_open)
                continue

            open_dt, close_dt = _session_window(today, tz, open_t, close_t)
            if now < open_dt:
                logger.info("Waiting for market open at %s", open_dt.isoformat())
                _update_runtime_status(status_path, args.timezone, today, "waiting_market_open", [], {"market_open": open_dt.isoformat()})
                if not args.skip_preflight:
                    preflight_ok = _run_preflight(logger, args, today, status_path)
                    if not preflight_ok:
                        logger.error("Preflight failed for %s", today.isoformat())
                        if args.run_once_day:
                            return 1
                _sleep_until(open_dt)
                now = datetime.now(tz)

            intraday_ok = True
            if now <= close_dt:
                intraday_ok = _run_intraday(logger, args, today, close_dt, status_path)
            else:
                logger.info("Market already closed for today; skipping intraday loops")
                _update_runtime_status(status_path, args.timezone, today, "market_closed_skip_intraday", [])

            _update_runtime_status(status_path, args.timezone, today, "running_eod", [], {"intraday_ok": intraday_ok})
            eod_ok = _run_eod_pipeline(logger, args, today, eod_state_path)
            _update_runtime_status(
                status_path,
                args.timezone,
                today,
                "day_complete" if eod_ok else "day_failed",
                [],
                {"intraday_ok": intraday_ok, "eod_ok": eod_ok},
            )

            if args.run_once_day:
                return 0 if eod_ok else 1

            next_day = _next_trading_day(today + timedelta(days=1), holidays)
            next_open, _ = _session_window(next_day, tz, open_t, close_t)
            logger.info("Sleeping until next trading day open: %s", next_open.isoformat())
            _sleep_until(next_open)
    finally:
        instance_lock.release()


if __name__ == "__main__":
    raise SystemExit(main())
