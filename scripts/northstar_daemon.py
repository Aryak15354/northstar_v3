#!/usr/bin/env python3
"""Northstar daemon: live + governance + research orchestration."""

from __future__ import annotations

import argparse
import errno
import json
import logging
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

import psutil
import numpy as np
import pandas as pd
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.options.accounting_integrity import AccountingIntegrityChecker
from src.options.capital_policy import CapitalPolicyManager
from src.options.clock_guard import ClockGuard
from src.options.governance_events import (
    GovernanceEventTypes,
    GovernanceSeverity,
    create_governance_logger,
)
from src.options.mode_controller import ModeController, SystemMode
from src.options.state_io import ProcessLock, StateIOManager
from src.options.state_recovery import StateRecoveryManager

LOGGER = logging.getLogger("northstar.daemon")


@dataclass
class ProcInfo:
    name: str
    process: subprocess.Popen
    cmd: list[str]
    started_at: datetime
    log_path: Optional[Path] = None
    restarts: int = 0
    env: Optional[Dict[str, str]] = None
    nice: Optional[int] = None


class ProcessManager:
    def __init__(self) -> None:
        self._procs: Dict[str, ProcInfo] = {}
        self._last_exit: Dict[str, Dict[str, Any]] = {}

    def start(
        self,
        name: str,
        cmd: list[str],
        cwd: Path,
        log_path: Optional[Path] = None,
        env: Optional[Dict[str, str]] = None,
        nice: Optional[int] = None,
    ) -> bool:
        self.stop(name, intentional=True)
        log_handle = None
        stdout_target: Any = subprocess.DEVNULL
        preexec_fn = None
        nice_value: Optional[int] = None
        if os.name == "posix" and nice is not None:
            try:
                parsed_nice = int(nice)
            except Exception:
                parsed_nice = 0
            if parsed_nice > 0:
                nice_value = parsed_nice

                def _set_nice() -> None:
                    try:
                        os.nice(parsed_nice)
                    except Exception:
                        pass

                preexec_fn = _set_nice
        try:
            if log_path:
                log_path.parent.mkdir(parents=True, exist_ok=True)
                log_handle = open(log_path, "ab")
                stdout_target = log_handle
            proc = subprocess.Popen(
                cmd,
                cwd=str(cwd),
                stdout=stdout_target,
                stderr=subprocess.STDOUT,
                text=False,
                env=env,
                preexec_fn=preexec_fn,
            )
            self._procs[name] = ProcInfo(
                name=name,
                process=proc,
                cmd=list(cmd),
                started_at=datetime.now(),
                log_path=log_path,
                restarts=0,
                env=env,
                nice=nice_value,
            )
            self._last_exit.pop(name, None)
            LOGGER.info("Started process %s pid=%s", name, proc.pid)
            return True
        except Exception as exc:
            LOGGER.error("Failed to start %s: %s", name, exc)
            return False
        finally:
            if log_handle:
                log_handle.close()

    def stop(self, name: str, intentional: bool = True) -> None:
        info = self._procs.get(name)
        if not info:
            return
        proc = info.process
        return_code: Optional[int] = proc.poll()
        try:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)
                return_code = proc.poll()
        except Exception as exc:
            LOGGER.warning("Error stopping %s: %s", name, exc)
        finally:
            if return_code is None:
                return_code = proc.poll()
            self._last_exit[name] = {
                "timestamp": datetime.now().isoformat(),
                "returncode": return_code,
                "intentional": bool(intentional),
            }
        self._procs.pop(name, None)

    def restart(self, name: str, cwd: Path) -> bool:
        info = self._procs.get(name)
        if not info:
            return False
        cmd = list(info.cmd)
        restarts = info.restarts + 1
        log_path = info.log_path
        env = dict(info.env) if info.env is not None else None
        nice = info.nice
        self.stop(name, intentional=True)
        ok = self.start(name, cmd, cwd, log_path=log_path, env=env, nice=nice)
        if ok:
            self._procs[name].restarts = restarts
        return ok

    def running(self, name: str) -> bool:
        info = self._procs.get(name)
        return bool(info and info.process.poll() is None)

    def status(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for name, info in self._procs.items():
            out[name] = {
                "running": info.process.poll() is None,
                "pid": info.process.pid,
                "started_at": info.started_at.isoformat(),
                "restarts": int(info.restarts),
                "log_path": str(info.log_path) if info.log_path else None,
                "nice": info.nice,
            }
        for name, last_exit in self._last_exit.items():
            if name in out:
                out[name]["last_exit"] = last_exit
                continue
            out[name] = {
                "running": False,
                "pid": None,
                "started_at": None,
                "restarts": 0,
                "log_path": None,
                "last_exit": last_exit,
            }
        return out

    def uptime_seconds(self, name: str) -> Optional[float]:
        info = self._procs.get(name)
        if not info:
            return None
        return float((datetime.now() - info.started_at).total_seconds())

    def poll_exits(self) -> list[Dict[str, Any]]:
        exited: list[Dict[str, Any]] = []
        for name, info in list(self._procs.items()):
            rc = info.process.poll()
            if rc is None:
                continue
            evt = {
                "name": name,
                "returncode": int(rc),
                "pid": int(info.process.pid),
                "started_at": info.started_at.isoformat(),
                "timestamp": datetime.now().isoformat(),
            }
            self._last_exit[name] = {
                "timestamp": evt["timestamp"],
                "returncode": int(rc),
                "intentional": False,
            }
            exited.append(evt)
            self._procs.pop(name, None)
        return exited

    def get_last_exit(self, name: str) -> Optional[Dict[str, Any]]:
        return self._last_exit.get(name)

    def cleanup(self) -> None:
        for name in list(self._procs.keys()):
            self.stop(name, intentional=True)


class NorthstarDaemon:
    def __init__(
        self,
        config_path: Path,
        cli_profile: Optional[str],
        cli_recovery: bool,
        cli_low_power: bool = False,
    ) -> None:
        self.config_path = config_path
        self.config = self._load_config(config_path)
        if cli_profile:
            self.config["system_profile"] = cli_profile
        if cli_low_power:
            rl = self.config.setdefault("resource_limits", {})
            rl["low_power_mode"] = True
            rl.setdefault("cpu_threshold_off_hours", 45.0)
            rl.setdefault("research_pause_seconds_on_cpu_throttle", 900.0)
            rl.setdefault("daemon_loop_sleep_seconds", 20.0)
            rl.setdefault("research_throttle_release_margin", 8.0)
            research_cfg = self.config.setdefault("research_engine", {})
            research_cfg.setdefault("max_cpu_cores", 1)
            research_cfg.setdefault("max_blas_threads", 1)
            research_cfg.setdefault("nice_increment", 15)
            try:
                research_cfg["interval_seconds"] = max(
                    1800,
                    int(research_cfg.get("interval_seconds", 1800)),
                )
            except Exception:
                research_cfg["interval_seconds"] = 1800
        self.manual_recovery_requested = bool(cli_recovery or self.config.get("recovery_mode", False))
        if cli_recovery:
            self.config["recovery_mode"] = True

        self.system_profile = str(self.config.get("system_profile", "minimal")).strip().lower()
        if self.system_profile not in {"minimal", "full"}:
            LOGGER.warning("Invalid system_profile=%s; defaulting to minimal", self.system_profile)
            self.system_profile = "minimal"
        self.recovery_mode = bool(self.config.get("recovery_mode", False) or self.manual_recovery_requested)
        self.running = False
        self.started_at = datetime.now()

        # Core state paths
        self.live_dir = PROJECT_ROOT / "data/options/live"
        self.live_dir.mkdir(parents=True, exist_ok=True)
        self.status_path = self.live_dir / "northstar_daemon_status.json"
        self.runtime_path = self.live_dir / "options_runtime_state.json"
        self.recovery_mode_report_path = self.live_dir / "recovery_mode_report.json"
        self.proc_log_dir = PROJECT_ROOT / "logs/daemon_managed"
        self.proc_log_dir.mkdir(parents=True, exist_ok=True)

        # Managers
        self.proc_manager = ProcessManager()
        self.state_io = StateIOManager(self.live_dir)
        self.recovery = StateRecoveryManager(self.live_dir)
        self.accounting = AccountingIntegrityChecker()
        self.mode_controller = ModeController()
        self.mode_controller.constraints_active = self.mode_controller._get_mode_constraints(
            SystemMode.NORMAL_OPERATION
        )
        self.capital_policy = CapitalPolicyManager(
            base_capital=float(self.config.get("operational_limits", {}).get("base_capital", 100000.0))
        )

        # Daemon-specific lock to avoid conflicting with engine lock.
        self.daemon_lock = ProcessLock(self.live_dir / "northstar_daemon.lock")

        # Clock guard
        time_cfg = self.config.get("time_config", {})
        self.clock_guard = ClockGuard(
            target_timezone=str(time_cfg.get("target_timezone", "Asia/Kolkata")),
            drift_threshold_seconds=float(time_cfg.get("drift_threshold_seconds", 5.0)),
            reference_sources=time_cfg.get("reference_sources"),
        )

        # Governance event logger
        self.gov_logger = create_governance_logger(
            self.config.get("governance_logging", {})
        )

        # Timing + thresholds
        self.governance_interval = timedelta(
            minutes=float(self.config.get("governance_interval_minutes", 5.0))
        )
        self.last_governance = datetime.min

        rl = self.config.get("resource_limits", {})
        self.low_power_mode = bool(rl.get("low_power_mode", False))
        self.memory_threshold = float(rl.get("memory_threshold", 85.0))
        base_cpu_threshold = float(rl.get("cpu_threshold", 70.0))
        self.cpu_threshold_market_hours = max(
            5.0,
            float(rl.get("cpu_threshold_market_hours", base_cpu_threshold)),
        )
        self.cpu_threshold_off_hours = max(
            5.0,
            float(rl.get("cpu_threshold_off_hours", self.cpu_threshold_market_hours)),
        )
        # Retain legacy field used in diagnostics/dashboard surfaces.
        self.cpu_threshold = self.cpu_threshold_market_hours
        self.research_throttle_release_margin = max(
            1.0,
            float(rl.get("research_throttle_release_margin", 8.0)),
        )
        self.research_pause_seconds_on_cpu_throttle = max(
            30.0,
            float(
                rl.get(
                    "research_pause_seconds_on_cpu_throttle",
                    900.0 if self.low_power_mode else 180.0,
                )
            ),
        )
        self.heartbeat_multiplier = float(rl.get("heartbeat_timeout_multiplier", 2.0))
        self.daemon_loop_sleep_seconds = max(
            5.0,
            float(
                rl.get(
                    "daemon_loop_sleep_seconds",
                    20.0 if self.low_power_mode else 15.0,
                )
            ),
        )
        self.research_restart_cooldown = timedelta(
            seconds=float(rl.get("research_restart_cooldown_seconds", 3600.0))
        )
        self.research_min_uptime_for_restart = timedelta(
            seconds=float(rl.get("research_min_uptime_for_restart_seconds", 900.0))
        )
        self.research_process_memory_threshold = float(
            rl.get("research_process_memory_threshold_percent", 30.0)
        )

        self.cpu_samples: list[float] = []
        self.memory_violations = 0
        self.research_throttled = False
        self._last_research_restart = datetime.min
        self._last_interrupted_count = 0
        self._wal_recovery_applied = False
        self._file_recovery_applied = False
        recovery_cfg = self.config.get("recovery_controls", {})
        self.recovery_auto_exit_clean_cycles = max(
            1,
            int(recovery_cfg.get("auto_exit_clean_cycles", 3) or 3),
        )
        self._recovery_clean_cycles = 0
        self._last_recovery_blockers: list[str] = []
        self._last_file_integrity_status = "unknown"
        self._last_live_restart = datetime.min
        live_interval = float(self.config.get("live_engine", {}).get("interval_seconds", 300) or 300.0)
        self.live_restart_cooldown = timedelta(seconds=max(30.0, live_interval * 0.5))
        self.last_regime_sync = datetime.min
        self.regime_sync_interval = timedelta(
            seconds=float(self.config.get("regime_sync_interval_seconds", 300) or 300.0)
        )
        self.progress_log_interval = timedelta(
            seconds=float(self.config.get("progress_log_interval_seconds", 60) or 60.0)
        )
        research_cfg = self.config.get("research_engine", {})
        default_research_cpu_cap = 1 if self.low_power_mode else max(1, (os.cpu_count() or 2) - 1)
        self.research_max_cpu_cores = max(
            1,
            int(research_cfg.get("max_cpu_cores", default_research_cpu_cap)),
        )
        self.research_max_blas_threads = max(
            1,
            int(research_cfg.get("max_blas_threads", 1)),
        )
        self.research_nice_increment = max(
            0,
            int(research_cfg.get("nice_increment", 15 if self.low_power_mode else 8)),
        )
        self._research_throttle_until = datetime.min
        self.last_progress_log = datetime.min

        # Cadence-aware daily data refresh (scripts/daily_data_refresh.py). Spawned
        # at most once per calendar day, after the configured hour (post-close so
        # daily datasets have published), as a detached subprocess so it never
        # blocks the daemon loop. The refresh script itself decides which sources
        # are due (daily/weekly/monthly/quarterly) via config/refresh_cadence.yaml.
        data_refresh_cfg = self.config.get("data_refresh", {}) or {}
        self.data_refresh_enabled = bool(data_refresh_cfg.get("enabled", True))
        self.data_refresh_after_hour = int(data_refresh_cfg.get("after_hour", 18))
        self.last_data_refresh_date: Optional[date] = None
        self._data_refresh_proc: Optional[subprocess.Popen] = None
        self._active_alert_flags: Dict[str, bool] = {}
        self._active_event_ids: Dict[str, str] = {}

        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    @staticmethod
    def _pid_alive(pid: int) -> bool:
        if pid <= 0:
            return False
        try:
            os.kill(pid, 0)
            return True
        except PermissionError:
            return True
        except OSError as exc:
            if getattr(exc, "errno", None) == errno.EPERM:
                return True
            return False

    def _lock_snapshot(self, lock_path: Path) -> Dict[str, Any]:
        snap: Dict[str, Any] = {
            "path": str(lock_path),
            "exists": bool(lock_path.exists()),
            "pid": None,
            "pid_alive": False,
            "acquired_at": None,
        }
        if not lock_path.exists():
            return snap
        try:
            payload = json.loads(lock_path.read_text())
            pid = int(payload.get("pid", 0) or 0)
            snap.update(
                {
                    "pid": pid if pid > 0 else None,
                    "pid_alive": self._pid_alive(pid),
                    "acquired_at": payload.get("acquired_at"),
                }
            )
            return snap
        except Exception as exc:
            snap["error"] = str(exc)
            return snap

    @staticmethod
    def _tail_file(path: Path, max_lines: int = 20) -> list[str]:
        if not path.exists():
            return []
        try:
            lines = path.read_text(errors="replace").splitlines()
            return lines[-max_lines:]
        except Exception:
            return []

    def diagnostic_snapshot(self) -> Dict[str, Any]:
        runtime = self._load_runtime_state()
        integrity = self.recovery.check_state_integrity()
        portfolio_risk_cap_pct = float(self.config.get("portfolio_risk_cap_pct", 0.10) or 0.10)
        accounting = (
            self.accounting.generate_integrity_summary(runtime, portfolio_risk_cap_pct)
            if runtime
            else {"overall_status": "missing_runtime", "block_new_risk": True}
        )
        interrupted = self.state_io.check_interrupted_operations()

        ledger_path = PROJECT_ROOT / "data/options/trade_ledger.parquet"
        ledger_info: Dict[str, Any] = {
            "path": str(ledger_path),
            "exists": bool(ledger_path.exists()),
            "last_modified": None,
            "last_row": None,
        }
        if ledger_path.exists():
            try:
                ledger_info["last_modified"] = datetime.fromtimestamp(
                    ledger_path.stat().st_mtime
                ).isoformat()
                import pandas as pd

                ledger = pd.read_parquet(ledger_path)
                if not ledger.empty:
                    last = ledger.sort_values("timestamp").iloc[-1].to_dict()
                    ledger_info["last_row"] = {
                        "trade_id": last.get("trade_id"),
                        "action": last.get("action"),
                        "timestamp": str(last.get("timestamp")),
                        "underlying": last.get("underlying"),
                    }
            except Exception as exc:
                ledger_info["error"] = str(exc)

        daemon_status_payload = {}
        try:
            if self.status_path.exists():
                daemon_status_payload = json.loads(self.status_path.read_text())
        except Exception as exc:
            daemon_status_payload = {"error": str(exc)}

        process_status = self.proc_manager.status()
        for proc_name, proc_state in process_status.items():
            log_path_raw = proc_state.get("log_path")
            if not log_path_raw:
                continue
            log_path = Path(str(log_path_raw))
            proc_state["log_tail"] = self._tail_file(log_path, max_lines=20)
            proc_state["last_exit"] = proc_state.get("last_exit") or self.proc_manager.get_last_exit(proc_name)

        runtime_recovery_mode = bool(runtime.get("recovery_mode", False)) if isinstance(runtime, dict) else False
        status_recovery_mode = bool(daemon_status_payload.get("recovery_mode", False)) if isinstance(daemon_status_payload, dict) else False
        effective_recovery_mode = bool(runtime_recovery_mode or status_recovery_mode or self.recovery_mode)

        return {
            "timestamp": datetime.now().isoformat(),
            "system_profile": self.system_profile,
            "recovery_mode": effective_recovery_mode,
            "recovery_mode_runtime_flag": runtime_recovery_mode,
            "recovery_mode_status_flag": status_recovery_mode,
            "manual_recovery_requested": bool(self.manual_recovery_requested),
            "current_mode": str(runtime.get("current_mode", "unknown")) if runtime else "unknown",
            "mode_constraints": runtime.get("mode_constraints", {}) if isinstance(runtime, dict) else {},
            "block_new_risk": bool(runtime.get("block_new_risk", False)) if isinstance(runtime, dict) else True,
            "processes": process_status,
            "locks": {
                "daemon_lock": self._lock_snapshot(self.live_dir / "northstar_daemon.lock"),
                "engine_lock": self._lock_snapshot(self.live_dir / "options_engine.lock"),
            },
            "wal": {
                "interrupted_count": len(interrupted),
                "interrupted_operations": interrupted[:10],
            },
            "runtime_integrity": integrity,
            "accounting_integrity": accounting,
            "ledger": ledger_info,
            "daemon_status_file": daemon_status_payload,
        }

    @staticmethod
    def _load_config(path: Path) -> Dict[str, Any]:
        if not path.exists():
            return {}
        try:
            data = yaml.safe_load(path.read_text())
            return data if isinstance(data, dict) else {}
        except Exception as exc:
            LOGGER.error("Failed to load config %s: %s", path, exc)
            return {}

    def _signal_handler(self, signum: int, _frame: Any) -> None:
        LOGGER.info("Received signal %s; stopping daemon", signum)
        self.running = False

    def startup_checks(self) -> bool:
        if not self.daemon_lock.acquire(timeout=3.0):
            LOGGER.error("Daemon lock unavailable; another daemon instance may be running")
            return False

        try:
            # Time checks
            dev_cfg = self.config.get("development", {})
            skip_time_checks = bool(dev_cfg.get("skip_time_checks", False))
            if skip_time_checks:
                LOGGER.warning("Skipping clock/time checks (development.skip_time_checks=true)")
            else:
                time_check = self.clock_guard.comprehensive_time_check()
                if not bool(time_check.get("trading_safe", False)):
                    LOGGER.error("Clock/timezone checks failed: %s", time_check)
                    self.gov_logger.log_event(
                        event_type=GovernanceEventTypes.CLOCK_DRIFT_EXCESSIVE,
                        severity=GovernanceSeverity.ERROR,
                        details=time_check,
                    )
                    self.daemon_lock.release()
                    return False

            interrupted = self.state_io.check_interrupted_operations()
            if interrupted:
                details = self.recovery.handle_interrupted_operations(interrupted)
                self.gov_logger.log_event(
                    event_type=GovernanceEventTypes.WAL_INTERRUPTION,
                    severity=GovernanceSeverity.WARNING,
                    details={"interrupted_operations": len(interrupted), "recovery_actions": details},
                )
                self.recovery_mode = True
                self._recovery_clean_cycles = 0
                self._last_recovery_blockers = ["wal_interruption"]
                self.state_io.resolve_interrupted_operations(
                    interrupted,
                    reason="reconciled_on_daemon_startup",
                )

            integrity = self.recovery.check_state_integrity()
            if integrity.get("overall_status") == "corrupted":
                self.recovery_mode = True
                self._recovery_clean_cycles = 0
                self._last_recovery_blockers = ["state_corruption"]
                self.gov_logger.log_event(
                    event_type=GovernanceEventTypes.STATE_CORRUPTION,
                    severity=GovernanceSeverity.ERROR,
                    details=integrity,
                )

            if self.recovery_mode:
                report = self._rebuild_runtime_state_from_ledger(recovery_mode=True)
                self.state_io.writer.write_json(self.recovery_mode_report_path, report)
                self.mode_controller.transition_to_mode(
                    SystemMode.RECOVERY_MODE,
                    ["startup_recovery_mode"],
                )
                self.gov_logger.log_event(
                    event_type=GovernanceEventTypes.RECOVERY_MODE_ENTRY,
                    severity=GovernanceSeverity.WARNING,
                    details={
                        "recovery_report": report,
                        "manual_recovery_requested": bool(self.manual_recovery_requested),
                        "recovery_blockers": list(self._last_recovery_blockers),
                    },
                )

            return True
        except Exception:
            self.daemon_lock.release()
            raise

    def _build_live_cmd(self) -> list[str]:
        live_cfg = self.config.get("live_engine", {})
        underlyings = live_cfg.get("underlyings", ["NIFTY", "BANKNIFTY", "FINNIFTY"])
        if isinstance(underlyings, list):
            underlyings_arg = ",".join(str(x).strip() for x in underlyings if str(x).strip())
        else:
            underlyings_arg = str(underlyings)

        cmd = [
            sys.executable,
            str(PROJECT_ROOT / "scripts/run_integrated_options_paper_engine.py"),
            "--mode",
            "continuous",
            "--interval-seconds",
            str(float(live_cfg.get("interval_seconds", 300))),
            "--underlyings",
            underlyings_arg,
            "--no-start-fresh-today",
        ]
        if bool(live_cfg.get("market_hours_only", True)):
            cmd.append("--market-hours-only")
        if bool(live_cfg.get("aggressive_mode", False)):
            cmd.append("--aggressive")
        if bool(live_cfg.get("disable_portfolio_overlay", False)):
            cmd.append("--disable-portfolio-overlay")
        else:
            cmd.extend([
                "--portfolio-overlay-max-stocks",
                str(int(live_cfg.get("portfolio_overlay_max_stocks", 6))),
            ])
        if self.recovery_mode:
            cmd.append("--recovery-mode")
        return cmd

    def _build_research_cmd(self) -> list[str]:
        cfg = self.config.get("research_engine", {})
        interval = int(cfg.get("interval_seconds", 1800))
        policy_cfg = str(cfg.get("policy_config", "config/research_policy.yaml"))
        log_level = str(cfg.get("log_level", self.config.get("logging", {}).get("level", "INFO")))
        cmd = [
            sys.executable,
            str(PROJECT_ROOT / "scripts/run_research_worker.py"),
            "--config",
            str((PROJECT_ROOT / policy_cfg).resolve() if not Path(policy_cfg).is_absolute() else Path(policy_cfg)),
            "--interval-seconds",
            str(interval),
            "--log-level",
            log_level,
        ]
        return cmd

    def _build_research_env(self) -> Dict[str, str]:
        cfg = self.config.get("research_engine", {})
        max_cpu_cores = max(1, int(cfg.get("max_cpu_cores", self.research_max_cpu_cores)))
        max_threads = max(1, int(cfg.get("max_blas_threads", self.research_max_blas_threads)))
        env = os.environ.copy()
        env.update(
            {
                "LOKY_MAX_CPU_COUNT": str(max_cpu_cores),
                "OMP_NUM_THREADS": str(max_threads),
                "OPENBLAS_NUM_THREADS": str(max_threads),
                "MKL_NUM_THREADS": str(max_threads),
                "NUMEXPR_NUM_THREADS": str(max_threads),
                "VECLIB_MAXIMUM_THREADS": str(max_threads),
                "NORTHSTAR_LOW_RESOURCE_PROFILE": "1" if self.low_power_mode else str(env.get("NORTHSTAR_LOW_RESOURCE_PROFILE", "0")),
            }
        )
        if bool(cfg.get("disable_mps", self.low_power_mode)):
            env["NORTHSTAR_DISABLE_MPS"] = "1"
        return env

    def _ensure_live_running(self) -> None:
        if not self.proc_manager.running("live_engine"):
            self.proc_manager.start(
                "live_engine",
                self._build_live_cmd(),
                PROJECT_ROOT,
                log_path=self.proc_log_dir / "live_engine.log",
            )

    def _ensure_live_state(self, is_market_hours: bool) -> None:
        live_cfg = self.config.get("live_engine", {})
        market_hours_only = bool(live_cfg.get("market_hours_only", True))
        should_run_live = bool((not market_hours_only) or is_market_hours)

        if not should_run_live:
            self.proc_manager.stop("live_engine", intentional=True)
            return

        self._ensure_live_running()

    def _ensure_research_state(self, is_market_hours: bool, constraints: Dict[str, Any]) -> None:
        research_cfg = self.config.get("research_engine", {})
        research_enabled = (
            self.system_profile == "full"
            and bool(research_cfg.get("enabled", True))
            and not self.recovery_mode
        )
        if constraints.get("disable_research", False):
            research_enabled = False

        should_pause = bool(is_market_hours or self.research_throttled)
        if not research_enabled or should_pause:
            self.proc_manager.stop("research_engine")
            return

        if not self.proc_manager.running("research_engine"):
            self.proc_manager.start(
                "research_engine",
                self._build_research_cmd(),
                PROJECT_ROOT,
                log_path=self.proc_log_dir / "research_engine.log",
                env=self._build_research_env(),
                nice=self.research_nice_increment,
            )

    def _cpu_report(self) -> Dict[str, float]:
        cpu_now = float(psutil.cpu_percent(interval=1.0))
        self.cpu_samples.append(cpu_now)
        if len(self.cpu_samples) > 12:
            self.cpu_samples.pop(0)
        cpu_avg = float(sum(self.cpu_samples) / len(self.cpu_samples)) if self.cpu_samples else cpu_now
        return {"current": cpu_now, "average": cpu_avg}

    def _memory_report(self) -> Dict[str, float]:
        vm = psutil.virtual_memory()
        return {
            "percent": float(vm.percent),
            "available_gb": float(vm.available / (1024 ** 3)),
        }

    def _process_memory_percent(self, name: str) -> float:
        info = self.proc_manager._procs.get(name)  # local module-level access
        if not info:
            return 0.0
        try:
            proc = psutil.Process(info.process.pid)
            return float(proc.memory_percent())
        except Exception:
            return 0.0

    def _monitor_resources(self, is_market_hours: bool) -> None:
        cpu = self._cpu_report()
        mem = self._memory_report()
        research_mem_pct = self._process_memory_percent("research_engine")

        if mem["percent"] > self.memory_threshold:
            self.memory_violations += 1
        else:
            self.memory_violations = 0

        if self.memory_violations >= 3 and self.proc_manager.running("research_engine"):
            now = datetime.now()
            uptime_sec = float(self.proc_manager.uptime_seconds("research_engine") or 0.0)
            min_uptime_sec = float(self.research_min_uptime_for_restart.total_seconds())
            cooldown_sec = float(self.research_restart_cooldown.total_seconds())

            if research_mem_pct < self.research_process_memory_threshold:
                # Global memory pressure alone is not enough to kill active research cycles.
                self.memory_violations = 0
            elif uptime_sec < min_uptime_sec:
                LOGGER.info(
                    "Memory pressure detected but skipping research restart "
                    "(uptime=%.1fs < min_uptime=%.1fs, system_mem=%.1f%%, research_mem=%.2f%%)",
                    uptime_sec,
                    min_uptime_sec,
                    mem["percent"],
                    research_mem_pct,
                )
            elif now - self._last_research_restart < self.research_restart_cooldown:
                LOGGER.info(
                    "Memory pressure restart suppressed by cooldown "
                    "(cooldown=%.1fs, system_mem=%.1f%%, research_mem=%.2f%%)",
                    cooldown_sec,
                    mem["percent"],
                    research_mem_pct,
                )
            else:
                self.proc_manager.restart("research_engine", PROJECT_ROOT)
                self._last_research_restart = now
                self.memory_violations = 0
                self.gov_logger.log_event(
                    event_type=GovernanceEventTypes.MEMORY_PRESSURE,
                    severity=GovernanceSeverity.WARNING,
                    details={
                        "memory_percent": mem["percent"],
                        "research_process_memory_percent": research_mem_pct,
                        "action": "restart_research",
                    },
                )

        cpu_threshold = self.cpu_threshold_market_hours if is_market_hours else self.cpu_threshold_off_hours
        release_threshold = max(5.0, cpu_threshold - self.research_throttle_release_margin)
        now = datetime.now()
        if cpu["average"] > cpu_threshold:
            self._research_throttle_until = max(
                self._research_throttle_until,
                now + timedelta(seconds=self.research_pause_seconds_on_cpu_throttle),
            )
            if not self.research_throttled:
                self.research_throttled = True
                self.gov_logger.log_event(
                    event_type=GovernanceEventTypes.CPU_THROTTLE,
                    severity=GovernanceSeverity.WARNING,
                    details={
                        "cpu_average": cpu["average"],
                        "threshold": cpu_threshold,
                        "scope": "market_hours" if is_market_hours else "off_hours",
                        "pause_seconds": self.research_pause_seconds_on_cpu_throttle,
                    },
                )
        elif (
            self.research_throttled
            and now >= self._research_throttle_until
            and cpu["average"] < release_threshold
        ):
            self.research_throttled = False

    def _monitor_process_exits(self) -> None:
        for exit_evt in self.proc_manager.poll_exits():
            name = str(exit_evt.get("name") or "unknown")
            self.gov_logger.log_event(
                event_type=GovernanceEventTypes.PROCESS_RESTART,
                severity=GovernanceSeverity.WARNING,
                details={
                    "process": name,
                    "returncode": exit_evt.get("returncode"),
                    "pid": exit_evt.get("pid"),
                    "started_at": exit_evt.get("started_at"),
                    "detected_at": exit_evt.get("timestamp"),
                },
            )

    def _monitor_live_heartbeat(self) -> None:
        if not self.proc_manager.running("live_engine"):
            return

        hb_path = self.live_dir / "live_engine_heartbeat.json"
        expected = float(self.config.get("live_engine", {}).get("interval_seconds", 300))
        timeout = expected * self.heartbeat_multiplier
        uptime = self.proc_manager.uptime_seconds("live_engine") or 0.0
        if uptime < timeout:
            # Allow first heartbeat to appear after startup/restart.
            return
        stale = True
        age = None

        try:
            if hb_path.exists():
                payload = json.loads(hb_path.read_text())
                ts = datetime.fromisoformat(str(payload.get("timestamp")))
                now_ref = datetime.now(ts.tzinfo) if ts.tzinfo else datetime.now()
                age = (now_ref - ts).total_seconds()
                stale = age > timeout
        except Exception:
            stale = True

        if stale:
            now = datetime.now()
            if now - self._last_live_restart < self.live_restart_cooldown:
                return
            self.proc_manager.restart("live_engine", PROJECT_ROOT)
            self._last_live_restart = now
            self.gov_logger.log_event(
                event_type=GovernanceEventTypes.HEARTBEAT_STALE,
                severity=GovernanceSeverity.ERROR,
                details={"age_seconds": age, "timeout_seconds": timeout, "action": "restart_live"},
            )

    def _load_runtime_state(self) -> Dict[str, Any]:
        try:
            if self.runtime_path.exists():
                payload = json.loads(self.runtime_path.read_text())
                if isinstance(payload, dict):
                    return payload
        except Exception as exc:
            LOGGER.warning("Failed reading runtime state: %s", exc)
        return {}

    def _sync_market_regime_artifact(self) -> None:
        """Keep market_regime parquet aligned with fresh market_state + regime feed."""
        processed_dir = PROJECT_ROOT / "data/processed"
        out_path = processed_dir / "market_regime.parquet"
        state_paths = [
            processed_dir / "intelligent_market_state.parquet",
            processed_dir / "market_state.parquet",
        ]
        state_df: Optional[pd.DataFrame] = None
        for p in state_paths:
            if not p.exists():
                continue
            try:
                df = pd.read_parquet(p)
                if isinstance(df, pd.DataFrame) and not df.empty:
                    state_df = df
                    break
            except Exception:
                continue
        if state_df is None or state_df.empty:
            return

        date_col = next((c for c in ["date", "Date", "timestamp", "intelligence_timestamp_str"] if c in state_df.columns), None)
        if date_col is None:
            return
        sdf = state_df.copy()
        sdf["Date"] = pd.to_datetime(sdf[date_col], errors="coerce")
        sdf = sdf.dropna(subset=["Date"]).sort_values("Date")
        if sdf.empty:
            return
        latest = sdf.iloc[-1]

        feed_regime = ""
        feed_path = processed_dir / "regime_intelligence_feed.json"
        if feed_path.exists():
            try:
                payload = json.loads(feed_path.read_text())
                if isinstance(payload, dict):
                    current = payload.get("current_regime", {})
                    if isinstance(current, dict):
                        feed_regime = str(current.get("name", "") or "").strip()
            except Exception:
                pass

        row = {
            "Date": pd.to_datetime(latest.get("Date"), errors="coerce"),
            "breadth": float(pd.to_numeric(latest.get("breadth", latest.get("breadth_pct", 0.0)), errors="coerce") or 0.0),
            "participation": float(pd.to_numeric(latest.get("participation", latest.get("participation_score", 0.0)), errors="coerce") or 0.0),
            "volatility": float(pd.to_numeric(latest.get("volatility", latest.get("stress_score", 0.0)), errors="coerce") or 0.0),
            "correlation": float(pd.to_numeric(latest.get("correlation", 0.0), errors="coerce") or 0.0),
            "risk_on_score": float(pd.to_numeric(latest.get("risk_on_score", latest.get("risk_on_probability", latest.get("risk_on", 0.0))), errors="coerce") or 0.0),
            "market_regime": (
                feed_regime
                or str(latest.get("market_regime", latest.get("macro_regime", latest.get("regime", latest.get("regime_name", "Unknown")))) or "Unknown")
            ),
        }
        if pd.isna(row["Date"]):
            return

        existing = pd.DataFrame(columns=list(row.keys()))
        if out_path.exists():
            try:
                old = pd.read_parquet(out_path)
                if isinstance(old, pd.DataFrame):
                    existing = old.copy()
            except Exception:
                existing = pd.DataFrame(columns=list(row.keys()))

        for c in row.keys():
            if c not in existing.columns:
                existing[c] = np.nan
        existing = existing[list(row.keys())]

        # Skip rewrite when the latest row is unchanged (avoids WAL/parquet churn).
        if not existing.empty:
            try:
                ex = existing.copy()
                ex["Date"] = pd.to_datetime(ex["Date"], errors="coerce")
                ex = ex.dropna(subset=["Date"]).sort_values("Date")
                if not ex.empty:
                    last = ex.iloc[-1]
                    same_date = pd.Timestamp(last["Date"]) == pd.Timestamp(row["Date"])
                    same_regime = str(last.get("market_regime", "")) == str(row.get("market_regime", ""))
                    same_numeric = True
                    for c in ["breadth", "participation", "volatility", "correlation", "risk_on_score"]:
                        lv = float(pd.to_numeric(last.get(c), errors="coerce") or 0.0)
                        rv = float(pd.to_numeric(row.get(c), errors="coerce") or 0.0)
                        if not np.isclose(lv, rv, rtol=0.0, atol=1e-9):
                            same_numeric = False
                            break
                    if same_date and same_regime and same_numeric:
                        return
            except Exception:
                pass

        combined = pd.concat([existing, pd.DataFrame([row])], ignore_index=True)
        combined["Date"] = pd.to_datetime(combined["Date"], errors="coerce")
        combined = combined.dropna(subset=["Date"]).sort_values("Date")
        combined = combined.drop_duplicates(subset=["Date"], keep="last").tail(10000).reset_index(drop=True)
        if combined.empty:
            return
        self.state_io.writer.write_parquet(out_path, combined)

    def _rebuild_runtime_state_from_ledger(self, recovery_mode: bool) -> Dict[str, Any]:
        runtime = self._load_runtime_state()
        configured_base = float(
            self.config.get("operational_limits", {}).get("base_capital", 100000.0) or 100000.0
        )
        runtime_base_raw = runtime.get("base_capital") if isinstance(runtime, dict) else None
        try:
            runtime_base = float(runtime_base_raw) if runtime_base_raw is not None else configured_base
        except Exception:
            runtime_base = configured_base
        if runtime_base <= 0.0:
            runtime_base = configured_base if configured_base > 0.0 else 100000.0

        portfolio_risk_cap_pct = float(self.config.get("portfolio_risk_cap_pct", 0.10) or 0.10)
        return self.recovery.rebuild_from_ledger(
            recovery_mode=bool(recovery_mode),
            base_capital=float(runtime_base),
            portfolio_risk_cap_pct=float(portfolio_risk_cap_pct),
        )

    @staticmethod
    def _drawdown_from_runtime(runtime: Dict[str, Any]) -> float:
        try:
            scaling = runtime.get("capital_scaling", {}) if isinstance(runtime.get("capital_scaling"), dict) else {}
            hwm = float(scaling.get("equity_high_water_mark", 0.0) or 0.0)
            eq = float(runtime.get("net_equity", scaling.get("current_equity", 0.0)) or 0.0)
            if hwm <= 0:
                return 0.0
            return max(0.0, (hwm - eq) / hwm)
        except Exception:
            return 0.0

    def _build_system_state(self, runtime: Dict[str, Any], integrity: Dict[str, Any]) -> Dict[str, Any]:
        alpha = runtime.get("alpha_os", {}) if isinstance(runtime.get("alpha_os"), dict) else {}
        diagnostics = alpha.get("diagnostics", {}) if isinstance(alpha.get("diagnostics"), dict) else {}
        drift = diagnostics.get("drift", {}) if isinstance(diagnostics.get("drift"), dict) else {}
        sdi = diagnostics.get("shadow_divergence_index", {}) if isinstance(diagnostics.get("shadow_divergence_index"), dict) else {}
        regime_snapshot = (
            alpha.get("regime_snapshot", {}) if isinstance(alpha.get("regime_snapshot"), dict) else {}
        )
        if not regime_snapshot and isinstance(diagnostics.get("regime_snapshot"), dict):
            regime_snapshot = diagnostics.get("regime_snapshot", {})
        probs = regime_snapshot.get("probabilities", {}) if isinstance(regime_snapshot.get("probabilities"), dict) else {}

        interrupted = self.state_io.check_interrupted_operations()
        return {
            "integrity_status": str(integrity.get("overall_status", "unknown") or "unknown"),
            "interrupted_operations": interrupted,
            "current_drawdown": self._drawdown_from_runtime(runtime),
            "drift_level": str(drift.get("severity", "normal") or "normal"),
            "fallback_tier": int(alpha.get("fallback_tier", 0) or 0),
            "sdi": float(sdi.get("sdi", 0.0) or 0.0),
            "crisis_probability": float(probs.get("CRISIS", 0.0) or 0.0),
            "convexity_breach": bool(runtime.get("convexity_breach", False)),
            "gap_shock_detected": bool(runtime.get("gap_shock_detected", False)),
            "survival_mode_activations_recent": int(runtime.get("survival_mode_activations_recent", 0) or 0),
            "high_drift_duration_minutes": int(runtime.get("high_drift_duration_minutes", 0) or 0),
            "current_mode": str(runtime.get("current_mode", "normal_operation") or "normal_operation"),
            "days_since_last_incident": int(runtime.get("days_since_last_incident", 0) or 0),
            "max_drawdown_stability_period": float(runtime.get("max_drawdown_stability_period", 0.0) or 0.0),
            "sharpe_ratio_recent": float(runtime.get("sharpe_ratio_recent", 0.0) or 0.0),
            "days_without_governance_constraints": int(runtime.get("days_without_governance_constraints", 0) or 0),
        }

    def _emit_threshold_event(
        self,
        *,
        key: str,
        active: bool,
        event_type: str,
        severity: str,
        details: Dict[str, Any],
    ) -> None:
        """Emit only on condition edge transitions to avoid event-log floods."""
        prev = bool(self._active_alert_flags.get(key, False))
        if active and not prev:
            event_id = self.gov_logger.log_event(
                event_type=event_type,
                severity=severity,
                details=details,
            )
            self._active_event_ids[key] = str(event_id)
        elif not active and prev:
            event_id = self._active_event_ids.get(key)
            if event_id:
                try:
                    self.gov_logger.resolve_event(event_id)
                except Exception:
                    pass
                self._active_event_ids.pop(key, None)
        self._active_alert_flags[key] = bool(active)

    def _governance_loop(self) -> None:
        runtime = self._load_runtime_state()
        if not runtime:
            LOGGER.warning("Runtime state unavailable; attempting ledger rebuild")
            self.recovery_mode = True
            self._recovery_clean_cycles = 0
            self._last_recovery_blockers = ["runtime_state_missing"]
            report = self._rebuild_runtime_state_from_ledger(recovery_mode=True)
            self.state_io.writer.write_json(self.recovery_mode_report_path, report)
            self.gov_logger.log_event(
                event_type=GovernanceEventTypes.STATE_CORRUPTION,
                severity=GovernanceSeverity.WARNING,
                details={
                    "reason": "runtime_state_missing",
                    "recovery_report": report,
                },
            )
            runtime = self._load_runtime_state()
            if not runtime:
                LOGGER.error("Runtime state still unavailable after rebuild; governance loop skipped")
                return
        was_recovery_mode = bool(self.recovery_mode)

        portfolio_risk_cap_pct = float(self.config.get("portfolio_risk_cap_pct", 0.10) or 0.10)
        integrity = self.accounting.generate_integrity_summary(runtime, portfolio_risk_cap_pct)
        file_integrity = self.recovery.check_state_integrity()
        file_integrity_status = str(file_integrity.get("overall_status", "unknown") or "unknown").lower()
        previous_file_status = self._last_file_integrity_status
        if file_integrity_status != previous_file_status:
            LOGGER.info(
                "Runtime file integrity state changed: %s -> %s",
                previous_file_status,
                file_integrity_status,
            )
            if file_integrity_status == "incomplete":
                self.gov_logger.log_event(
                    event_type=GovernanceEventTypes.STATE_CORRUPTION,
                    severity=GovernanceSeverity.WARNING,
                    details={
                        "file_integrity_status": file_integrity_status,
                        "issues_found": file_integrity.get("issues_found", []),
                    },
                )
        self._last_file_integrity_status = file_integrity_status

        system_state = self._build_system_state(runtime, integrity)
        if file_integrity_status in {"corrupted", "incomplete"}:
            system_state["integrity_status"] = file_integrity_status
            if not self._file_recovery_applied:
                self.recovery_mode = True
                self._recovery_clean_cycles = 0
                self._last_recovery_blockers = [f"state_{file_integrity_status}"]
                report = self._rebuild_runtime_state_from_ledger(recovery_mode=True)
                self.state_io.writer.write_json(self.recovery_mode_report_path, report)
                self.gov_logger.log_event(
                    event_type=GovernanceEventTypes.STATE_CORRUPTION,
                    severity=(
                        GovernanceSeverity.ERROR
                        if file_integrity_status == "corrupted"
                        else GovernanceSeverity.WARNING
                    ),
                    details={
                        "file_integrity_status": file_integrity_status,
                        "issues_found": file_integrity.get("issues_found", []),
                        "recovery_report": report,
                    },
                )
                runtime = self._load_runtime_state()
                if not runtime:
                    LOGGER.error("Recovery wrote no runtime state; governance cycle cannot proceed")
                    return
                integrity = self.accounting.generate_integrity_summary(runtime, portfolio_risk_cap_pct)
                file_integrity = self.recovery.check_state_integrity()
                file_integrity_status = str(file_integrity.get("overall_status", "unknown") or "unknown").lower()
                self._last_file_integrity_status = file_integrity_status
                system_state = self._build_system_state(runtime, integrity)
                system_state["integrity_status"] = file_integrity_status
                self._file_recovery_applied = True
        else:
            self._file_recovery_applied = False

        system_state["file_integrity_status"] = file_integrity_status
        system_state["file_integrity_issues"] = file_integrity.get("issues_found", [])
        interrupted_ops = system_state.get("interrupted_operations", []) if isinstance(system_state.get("interrupted_operations"), list) else []
        interrupted_count = len(interrupted_ops)

        if interrupted_count > 0 and interrupted_count != self._last_interrupted_count:
            self.gov_logger.log_event(
                event_type=GovernanceEventTypes.WAL_INTERRUPTION,
                severity=GovernanceSeverity.WARNING,
                details={"interrupted_operations": interrupted_count},
            )
        self._last_interrupted_count = interrupted_count

        if interrupted_count > 0 and not self._wal_recovery_applied:
            self.recovery_mode = True
            self._recovery_clean_cycles = 0
            self._last_recovery_blockers = ["wal_interruption"]
            report = self._rebuild_runtime_state_from_ledger(recovery_mode=True)
            self.state_io.writer.write_json(self.recovery_mode_report_path, report)
            self.state_io.resolve_interrupted_operations(
                interrupted_ops,
                reason="reconciled_in_governance_loop",
            )
            self._wal_recovery_applied = True
            system_state["interrupted_operations"] = []
        elif interrupted_count == 0:
            self._wal_recovery_applied = False

        recovery_blockers: list[str] = []
        if file_integrity_status in {"corrupted", "incomplete"}:
            recovery_blockers.append(f"file_integrity:{file_integrity_status}")
        if interrupted_count > 0:
            recovery_blockers.append("wal_interruption")
        if str(system_state.get("integrity_status", "")).lower() == "corrupted":
            recovery_blockers.append("runtime_integrity_corrupted")

        if recovery_blockers:
            self.recovery_mode = True
            self._recovery_clean_cycles = 0
            self._last_recovery_blockers = list(recovery_blockers)
        elif self.recovery_mode and not self.manual_recovery_requested:
            self._recovery_clean_cycles += 1
            if self._recovery_clean_cycles >= self.recovery_auto_exit_clean_cycles:
                self.recovery_mode = False
                self._recovery_clean_cycles = 0
                self.gov_logger.log_event(
                    event_type=GovernanceEventTypes.RECOVERY_MODE_EXIT,
                    severity=GovernanceSeverity.INFO,
                    details={
                        "auto_exit": True,
                        "clean_cycles_observed": self.recovery_auto_exit_clean_cycles,
                        "last_recovery_blockers": list(self._last_recovery_blockers),
                    },
                )
                self._last_recovery_blockers = []
        elif not self.recovery_mode:
            self._recovery_clean_cycles = 0

        if self.recovery_mode and not was_recovery_mode:
            self.gov_logger.log_event(
                event_type=GovernanceEventTypes.RECOVERY_MODE_ENTRY,
                severity=GovernanceSeverity.WARNING,
                details={
                    "source": "governance_loop",
                    "recovery_blockers": list(self._last_recovery_blockers),
                    "manual_recovery_requested": bool(self.manual_recovery_requested),
                },
            )

        if self.recovery_mode != was_recovery_mode and self.proc_manager.running("live_engine"):
            self.proc_manager.restart("live_engine", PROJECT_ROOT)
            self.gov_logger.log_event(
                event_type=GovernanceEventTypes.PROCESS_RESTART,
                severity=GovernanceSeverity.WARNING,
                details={
                    "process": "live_engine",
                    "reason": "recovery_mode_changed",
                    "recovery_mode_before": bool(was_recovery_mode),
                    "recovery_mode_after": bool(self.recovery_mode),
                },
            )

        fallback_tier = int(system_state.get("fallback_tier", 0) or 0)
        self._emit_threshold_event(
            key="fallback_tier_alert",
            active=fallback_tier >= 2,
            event_type="fallback_tier_alert",
            severity=GovernanceSeverity.WARNING,
            details={"fallback_tier": fallback_tier},
        )
        sdi_val = float(system_state.get("sdi", 0.0) or 0.0)
        self._emit_threshold_event(
            key="sdi_alert",
            active=sdi_val > 0.4,
            event_type="sdi_alert",
            severity=GovernanceSeverity.WARNING,
            details={"sdi": sdi_val},
        )
        drawdown_val = float(system_state.get("current_drawdown", 0.0) or 0.0)
        self._emit_threshold_event(
            key="drawdown_alert",
            active=drawdown_val > 0.10,
            event_type=GovernanceEventTypes.DRAWDOWN_ALERT,
            severity=GovernanceSeverity.WARNING,
            details={"drawdown": drawdown_val},
        )
        drift_level = str(system_state.get("drift_level", "normal")).lower()
        self._emit_threshold_event(
            key="drift_alert",
            active=drift_level in {"elevated", "high"},
            event_type="drift_alert",
            severity=GovernanceSeverity.WARNING,
            details={"drift_level": drift_level},
        )

        if self.recovery_mode:
            transition = self.mode_controller.transition_to_mode(
                SystemMode.RECOVERY_MODE,
                ["daemon_recovery_mode_active"],
            )
        else:
            new_mode, reasons = self.mode_controller.evaluate_mode_transition(system_state)
            transition = self.mode_controller.transition_to_mode(new_mode, reasons)
        if transition.get("transitioned"):
            self.gov_logger.log_event(
                event_type=GovernanceEventTypes.MODE_TRANSITION,
                severity=GovernanceSeverity.WARNING,
                details=transition,
                mode_before=transition.get("from_mode"),
                mode_after=transition.get("to_mode"),
            )
            if transition.get("to_mode") == SystemMode.SURVIVAL_CORE.value:
                self.gov_logger.log_event(
                    event_type=GovernanceEventTypes.SURVIVAL_MODE_ACTIVATION,
                    severity=GovernanceSeverity.ERROR,
                    details={"transition": transition},
                )

        if integrity.get("block_new_risk", False):
            alerts = integrity.get("alerts", []) if isinstance(integrity.get("alerts"), list) else []
            event_type = (
                GovernanceEventTypes.RISK_LIMIT_EXCEEDED
                if any("risk limit" in str(a).lower() for a in alerts)
                else GovernanceEventTypes.ACCOUNTING_MISMATCH
            )
            self._emit_threshold_event(
                key="integrity_block_new_risk",
                active=True,
                event_type=event_type,
                severity=GovernanceSeverity.ERROR,
                details={
                    **integrity,
                    "mode_before": self.mode_controller.current_mode.value,
                    "mode_after": self.mode_controller.current_mode.value,
                },
            )
        else:
            self._emit_threshold_event(
                key="integrity_block_new_risk",
                active=False,
                event_type=GovernanceEventTypes.ACCOUNTING_MISMATCH,
                severity=GovernanceSeverity.ERROR,
                details={"cleared": True},
            )

        # Auto de-scaling symmetry
        try:
            current_tier = int(runtime.get("capital_tier", self.capital_policy.current_tier.value) or self.capital_policy.current_tier.value)
            if 1 <= current_tier <= 5:
                self.capital_policy.current_tier = self.capital_policy.current_tier.__class__(current_tier)
        except Exception as exc:
            LOGGER.warning("Invalid runtime capital_tier value: %s", exc)

        descaling = self.capital_policy.evaluate_descaling_triggers(system_state)
        if descaling.get("should_descale"):
            tier_change = self.capital_policy.execute_tier_change(
                int(descaling.get("target_tier", self.capital_policy.current_tier.value)),
                reason="auto_descale_trigger",
                operator_override=False,
            )
            if tier_change.get("changed"):
                self.gov_logger.log_event(
                    event_type=GovernanceEventTypes.DRAWDOWN_ALERT,
                    severity=GovernanceSeverity.WARNING,
                    details={"tier_change": tier_change, "triggers": descaling.get("triggers_met", [])},
                )

        # Runtime governance fields
        constraints = self.mode_controller.constraints_active
        runtime["current_mode"] = self.mode_controller.current_mode.value
        runtime["mode_entered_at"] = self.mode_controller.mode_entered_at.isoformat()
        runtime["mode_constraints"] = constraints
        runtime["block_new_risk"] = bool(integrity.get("block_new_risk", False) or constraints.get("block_new_risk", False))
        runtime["last_governance_check"] = datetime.now().isoformat()
        runtime["integrity_status"] = str(system_state.get("integrity_status", integrity.get("overall_status", "unknown")))
        runtime["file_integrity_status"] = file_integrity_status
        runtime["file_integrity_issues"] = file_integrity.get("issues_found", [])
        runtime["research_throttled"] = bool(self.research_throttled)
        runtime["capital_tier"] = int(self.capital_policy.current_tier.value)
        runtime["recovery_mode"] = bool(self.recovery_mode)
        runtime["portfolio_risk_cap_pct"] = float(portfolio_risk_cap_pct)

        if not self.state_io.write_runtime_state(runtime):
            LOGGER.error("Failed writing runtime state from governance loop")

    def _update_status(self) -> None:
        market = self.clock_guard.get_market_time_info()
        throttle_until = (
            self._research_throttle_until.isoformat()
            if self.research_throttled and self._research_throttle_until > datetime.min
            else None
        )
        payload = {
            "timestamp": datetime.now().isoformat(),
            "daemon_pid": os.getpid(),
            "uptime_seconds": (datetime.now() - self.started_at).total_seconds(),
            "system_profile": self.system_profile,
            "recovery_mode": bool(self.recovery_mode),
            "mode": self.mode_controller.current_mode.value,
            "research_throttled": bool(self.research_throttled),
            "research_throttle_until": throttle_until,
            "market_status": market,
            "processes": self.proc_manager.status(),
            "file_integrity_status": self._last_file_integrity_status,
            "resource_limits": {
                "low_power_mode": bool(self.low_power_mode),
                "cpu_threshold_market_hours": float(self.cpu_threshold_market_hours),
                "cpu_threshold_off_hours": float(self.cpu_threshold_off_hours),
                "research_pause_seconds_on_cpu_throttle": float(
                    self.research_pause_seconds_on_cpu_throttle
                ),
            },
            "resource_usage": {
                "cpu_percent": float(psutil.cpu_percent()),
                "memory_percent": float(psutil.virtual_memory().percent),
            },
            "last_governance_check": self.last_governance.isoformat() if self.last_governance != datetime.min else None,
        }
        self.state_io.writer.write_json(self.status_path, payload)

    @staticmethod
    def _simple_bar(frac: float, width: int = 18) -> str:
        f = max(0.0, min(1.0, float(frac)))
        fill = int(round(width * f))
        return f"[{'#' * fill}{'.' * (width - fill)}] {int(f * 100):3d}%"

    def _market_progress(self, market_info: Dict[str, Any]) -> tuple[float, str]:
        try:
            status = str(market_info.get("market_status", "unknown"))
            open_raw = market_info.get("market_open")
            close_raw = market_info.get("market_close")
            if not open_raw or not close_raw:
                return 0.0, status
            open_ts = datetime.fromisoformat(str(open_raw))
            close_ts = datetime.fromisoformat(str(close_raw))
            now_ts = datetime.now(open_ts.tzinfo) if open_ts.tzinfo else datetime.now()
            if now_ts <= open_ts:
                return 0.0, status
            if now_ts >= close_ts:
                return 1.0, status
            frac = (now_ts - open_ts).total_seconds() / max(1.0, (close_ts - open_ts).total_seconds())
            return float(frac), status
        except Exception:
            return 0.0, str(market_info.get("market_status", "unknown"))

    def _log_loop_status(self, market_info: Dict[str, Any]) -> None:
        procs = self.proc_manager.status()
        live_on = bool(procs.get("live_engine", {}).get("running", False))
        research_on = bool(procs.get("research_engine", {}).get("running", False))
        frac, status = self._market_progress(market_info)
        mode = self.mode_controller.current_mode.value
        cpu = float(psutil.cpu_percent())
        mem = float(psutil.virtual_memory().percent)
        LOGGER.info(
            "Daemon Status market=%s %s mode=%s live=%s research=%s throttled=%s recovery=%s cpu=%.1f%% mem=%.1f%%",
            status,
            self._simple_bar(frac),
            mode,
            live_on,
            research_on,
            bool(self.research_throttled),
            bool(self.recovery_mode),
            cpu,
            mem,
        )

    def _maybe_run_data_refresh(self) -> None:
        """Spawn the cadence-aware data refresh once per calendar day (detached)."""
        if not self.data_refresh_enabled:
            return

        # Reap a finished prior run and log its outcome.
        if self._data_refresh_proc is not None:
            rc = self._data_refresh_proc.poll()
            if rc is None:
                return  # still running; don't overlap
            LOGGER.info("Daily data refresh finished (exit=%s)", rc)
            self._data_refresh_proc = None

        now = datetime.now()
        if now.hour < self.data_refresh_after_hour:
            return
        if self.last_data_refresh_date == now.date():
            return

        log_path = self.proc_log_dir / "data_refresh.log"
        try:
            log_fh = open(log_path, "a", encoding="utf-8")
            log_fh.write(f"\n===== data refresh spawned {now.isoformat()} =====\n")
            log_fh.flush()
            self._data_refresh_proc = subprocess.Popen(
                [sys.executable, str(PROJECT_ROOT / "scripts" / "daily_data_refresh.py")],
                cwd=str(PROJECT_ROOT),
                stdout=log_fh,
                stderr=subprocess.STDOUT,
            )
            self.last_data_refresh_date = now.date()
            LOGGER.info("Spawned daily data refresh (pid=%s, log=%s)", self._data_refresh_proc.pid, log_path)
        except Exception as exc:  # noqa: BLE001
            LOGGER.error("Failed to spawn daily data refresh: %s", exc)

    def run(self) -> int:
        if not self.startup_checks():
            return 1

        self.running = True

        try:
            while self.running:
                market_info = self.clock_guard.get_market_time_info()
                is_market_hours = bool(market_info.get("is_market_hours", False))

                self._monitor_process_exits()
                self._ensure_live_state(is_market_hours=is_market_hours)
                if self.proc_manager.running("live_engine"):
                    self._monitor_live_heartbeat()
                self._monitor_resources(is_market_hours=is_market_hours)

                if datetime.now() - self.last_governance >= self.governance_interval:
                    self._governance_loop()
                    self.last_governance = datetime.now()

                if datetime.now() - self.last_regime_sync >= self.regime_sync_interval:
                    try:
                        self._sync_market_regime_artifact()
                    except Exception as exc:
                        LOGGER.warning("Regime artifact sync failed: %s", exc)
                    self.last_regime_sync = datetime.now()

                self._ensure_research_state(
                    is_market_hours=is_market_hours,
                    constraints=self.mode_controller.constraints_active,
                )

                self._maybe_run_data_refresh()

                self._update_status()
                if datetime.now() - self.last_progress_log >= self.progress_log_interval:
                    self._log_loop_status(market_info=market_info)
                    self.last_progress_log = datetime.now()
                time.sleep(self.daemon_loop_sleep_seconds)
        except Exception as exc:
            LOGGER.error("Daemon loop failed: %s", exc, exc_info=True)
            return 1
        finally:
            self.proc_manager.cleanup()
            self.daemon_lock.release()
            if self.recovery_mode:
                self.gov_logger.log_event(
                    event_type=GovernanceEventTypes.RECOVERY_MODE_EXIT,
                    severity=GovernanceSeverity.INFO,
                    details={"daemon_stopped": True},
                )

        return 0


def configure_logging(level: str) -> None:
    logs_dir = PROJECT_ROOT / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(logs_dir / "northstar_daemon.log"),
            logging.StreamHandler(),
        ],
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Northstar daemon")
    parser.add_argument(
        "--config",
        type=Path,
        default=PROJECT_ROOT / "config/northstar_daemon.yaml",
        help="Daemon config path",
    )
    parser.add_argument("--system-profile", choices=["minimal", "full"], default=None)
    parser.add_argument("--recovery-mode", action="store_true")
    parser.add_argument(
        "--diagnostic-mode",
        action="store_true",
        help="Print one-shot structured health snapshot and exit",
    )
    parser.add_argument(
        "--low-power",
        action="store_true",
        help="Enable laptop-safe throttling defaults (slower cadence, lower research CPU footprint).",
    )
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    configure_logging(args.log_level)

    daemon = NorthstarDaemon(
        config_path=args.config,
        cli_profile=args.system_profile,
        cli_recovery=bool(args.recovery_mode),
        cli_low_power=bool(args.low_power),
    )
    if bool(args.diagnostic_mode):
        print(json.dumps(daemon.diagnostic_snapshot(), indent=2, default=str))
        return 0
    return daemon.run()


if __name__ == "__main__":
    raise SystemExit(main())
