#!/usr/bin/env python3
"""
Northstar trading-day orchestrator.

Intraday (trading hours):
- Runs Upstox options engine loop (5m cadence by default)
- Runs NS-USO sentiment loop (5m cadence by default)
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
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime, time as dt_time, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from zoneinfo import ZoneInfo


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_UNDERLYINGS = "NIFTY,BANKNIFTY,FINNIFTY,RELIANCE,TCS,HDFCBANK,INFY,ICICIBANK,SBIN"
DEFAULT_STATUS_PATH = PROJECT_ROOT / "data/options/live/trading_day_orchestrator_status.json"
DEFAULT_EOD_STATE_PATH = PROJECT_ROOT / "data/options/live/trading_day_orchestrator_eod_state.json"


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


def _build_sentiment_command(args: argparse.Namespace) -> List[str]:
    return [
        args.python_bin,
        str(PROJECT_ROOT / "scripts/run_ns_uso_sentiment_loop.py"),
        "--interval-minutes",
        str(args.interval_minutes),
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
    v3_cmd: List[str] = [
        args.python_bin,
        str(PROJECT_ROOT / "run_complete_v3_system.py"),
        "--no-dashboard",
        "--skip-options-cycle",
    ]
    if args.eod_v3_mode == "quick":
        v3_cmd.append("--quick")
    if args.eod_skip_integration_alignment:
        v3_cmd.append("--skip-integration-alignment")
    if args.eod_force_data:
        v3_cmd.append("--force-data")

    steps = [
        (
            "market_update_yfinance",
            [
                args.python_bin,
                str(PROJECT_ROOT / "src/ingestion/integrated_data_pipeline.py"),
                "--market-only",
                "--force-market",
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
            "complete_v3_system_run",
            v3_cmd,
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
            name="options_engine",
            command=_build_options_command(args),
            log_path=PROJECT_ROOT / "logs/options_engine_loop.log",
        ),
        ManagedProcess(
            name="ns_uso_sentiment",
            command=_build_sentiment_command(args),
            log_path=PROJECT_ROOT / "logs/ns_uso_sentiment_loop.log",
        ),
    ]

    logger.info("Starting intraday loops for %s", session_date.isoformat())
    for loop in loops:
        loop.start(logger)
    _update_runtime_status(status_path, args.timezone, session_date, "intraday_running", loops)

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

            _update_runtime_status(
                status_path,
                args.timezone,
                session_date,
                "intraday_running",
                loops,
                details={"market_close": close_dt.isoformat()},
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
    parser.add_argument("--interval-minutes", type=float, default=5.0)
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
    parser.add_argument("--log-path", type=str, default=str(PROJECT_ROOT / "logs/trading_day_orchestrator.log"))
    parser.add_argument("--dry-run", action="store_true", help="Print resolved schedule and commands, then exit")
    args = parser.parse_args()

    tz = ZoneInfo(args.timezone)
    open_t = _parse_hhmm(args.market_open)
    close_t = _parse_hhmm(args.market_close)
    status_path = Path(args.status_path)
    eod_state_path = Path(args.eod_state_path)
    logger = _configure_logger(Path(args.log_path))
    holidays = _load_holidays(PROJECT_ROOT / args.holidays_file)

    logger.info("Trading-day orchestrator started")
    logger.info("Timezone=%s open=%s close=%s interval=%.1fmin", args.timezone, args.market_open, args.market_close, args.interval_minutes)
    logger.info("Underlyings=%s", args.underlyings)

    if args.dry_run:
        logger.info("Dry-run mode enabled; no processes will be started.")
        logger.info("Options loop command: %s", " ".join(_build_options_command(args)))
        logger.info("Sentiment loop command: %s", " ".join(_build_sentiment_command(args)))
        logger.info(
            "EOD step command[market]: %s",
            " ".join(
                [
                    args.python_bin,
                    str(PROJECT_ROOT / "src/ingestion/integrated_data_pipeline.py"),
                    "--market-only",
                    "--force-market",
                ]
            ),
        )
        logger.info(
            "EOD step command[rbi]: %s",
            " ".join([args.python_bin, str(PROJECT_ROOT / "src/ingestion/rbi_daily_updater.py"), "--force"]),
        )
        logger.info(
            "EOD step command[integration]: %s",
            " ".join([args.python_bin, str(PROJECT_ROOT / "src/ingestion/integrated_data_pipeline.py"), "--integrate-only"]),
        )
        logger.info(
            "EOD step command[full]: %s",
            " ".join(
                [
                    args.python_bin,
                    str(PROJECT_ROOT / "run_complete_v3_system.py"),
                    "--no-dashboard",
                    "--skip-options-cycle",
                ]
                + (["--quick"] if args.eod_v3_mode == "quick" else [])
                + (["--force-data"] if args.eod_force_data else [])
                + (["--skip-integration-alignment"] if args.eod_skip_integration_alignment else [])
            ),
        )
        if not args.skip_periodic_reports:
            logger.info(
                "EOD step command[periodic_reports]: %s",
                " ".join(
                    [
                        args.python_bin,
                        str(PROJECT_ROOT / "scripts/generate_periodic_reports.py"),
                        "--timezone",
                        args.timezone,
                    ]
                ),
            )
        if not args.skip_options_backtest:
            logger.info(
                "EOD step command[options_backtester]: %s",
                " ".join(
                    [
                        args.python_bin,
                        str(PROJECT_ROOT / "scripts/run_options_backtester.py"),
                        "--underlyings",
                        args.underlyings,
                    ]
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


if __name__ == "__main__":
    raise SystemExit(main())
