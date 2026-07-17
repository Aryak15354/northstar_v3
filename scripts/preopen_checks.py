#!/usr/bin/env python3
"""
Pre-Open Checklist Script for Northstar V3

Performs comprehensive pre-market checks to ensure system readiness.
"""

import sys
import os
import json
import logging
import math
import sqlite3
from pathlib import Path
from datetime import datetime, time, timezone, timedelta, date
from typing import Dict, Any, List
import pandas as pd

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.options.clock_guard import ClockGuard
from src.options.state_io import StateIOManager
from src.options.state_recovery import StateRecoveryManager
from src.options.accounting_integrity import AccountingIntegrityChecker
from src.pnl.nav_calculator import NAVCalculator

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
INDIA_TZ = timezone(timedelta(hours=5, minutes=30))


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except Exception:
        return default
    return out if math.isfinite(out) else default


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with open(path, "r") as f:
            payload = json.load(f)
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _resolve_upstox_probe_token() -> tuple[str, str]:
    """
    Resolve the Upstox token using the same precedence as the live adapter.

    This avoids split-brain auth checks where pre-open probes read a different
    token source than the runtime adapter.
    """
    try:
        from src.options.config_loader import get_config
        from src.options.upstox_adapter import UpstoxAdapter

        config = get_config(reload=True)
        adapter = UpstoxAdapter(config.upstox)
        token = adapter._load_access_token_from_sources(
            prefer_files=True,
            current_token=config.upstox.access_token,
        )
        token = str(token or config.upstox.access_token or "").strip()
        if token:
            return token, "options credential sources"
    except Exception as exc:
        logger.warning("Failed resolving Upstox token via options config: %s", exc)

    access_token = os.getenv("UPSTOX_ACCESS_TOKEN", "").strip()
    env_file = PROJECT_ROOT / ".env.options"
    if not access_token and env_file.exists():
        content = env_file.read_text(encoding="utf-8", errors="ignore")
        for raw_line in content.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip() == "UPSTOX_ACCESS_TOKEN":
                access_token = value.strip()
                break
    return access_token, "legacy environment fallback"


def _positions_default_capital(current_positions_payload: Dict[str, Any]) -> float:
    performance = current_positions_payload.get("performance") or {}
    total_value = _safe_float(current_positions_payload.get("total_value"), default=float("nan"))
    total_pnl = _safe_float(performance.get("total_pnl"), default=float("nan"))
    if math.isfinite(total_value) and math.isfinite(total_pnl):
        starting_capital = total_value - total_pnl
        if starting_capital > 0.0:
            return float(starting_capital)
    return 10_000_000.0


def _load_runtime_holdings_count(runtime_db_path: Path) -> tuple[int, str]:
    if not runtime_db_path.exists():
        return 0, "runtime_db_missing"

    con = sqlite3.connect(runtime_db_path)
    try:
        row = con.execute(
            """
            SELECT state_json
            FROM portfolio_snapshots
            ORDER BY snapshot_id DESC
            LIMIT 1
            """
        ).fetchone()
    finally:
        con.close()

    if row is None:
        return 0, "runtime_snapshot_missing"

    try:
        state = json.loads(str(row[0] or "{}"))
    except Exception:
        return 0, "runtime_snapshot_invalid"

    holdings = state.get("holdings") if isinstance(state, dict) else {}
    if not isinstance(holdings, dict):
        return 0, "runtime_holdings_invalid"

    count = 0
    for position in holdings.values():
        if not isinstance(position, dict):
            continue
        instrument_type = str(position.get("instrument_type") or "equity").strip().lower()
        if instrument_type not in {"equity", "cash_equity"}:
            continue
        if abs(_safe_float(position.get("quantity"), 0.0)) <= 1e-9:
            continue
        count += 1
    return int(count), "ok"


def _core_sync_batch_summary(runtime_db_path: Path, trade_date_ist) -> Dict[str, Any]:
    if not runtime_db_path.exists():
        return {
            "trade_date_ist": str(trade_date_ist),
            "batch_count": 0,
            "event_count": 0,
            "reason": "runtime_db_missing",
        }

    con = sqlite3.connect(runtime_db_path)
    try:
        rows = pd.read_sql_query(
            """
            SELECT event_id, timestamp_utc
            FROM portfolio_events
            WHERE trigger_reason_code = 'rebalance.core.sync'
            ORDER BY timestamp_utc ASC, event_id ASC
            """,
            con,
        )
    finally:
        con.close()

    if rows.empty:
        return {
            "trade_date_ist": str(trade_date_ist),
            "batch_count": 0,
            "event_count": 0,
            "reason": "core_sync_missing",
        }

    rows["timestamp_utc"] = pd.to_datetime(rows["timestamp_utc"], errors="coerce", utc=True)
    rows = rows.dropna(subset=["timestamp_utc"]).copy()
    if rows.empty:
        return {
            "trade_date_ist": str(trade_date_ist),
            "batch_count": 0,
            "event_count": 0,
            "reason": "core_sync_invalid_timestamps",
        }

    rows["trade_date_ist"] = rows["timestamp_utc"].dt.tz_convert(INDIA_TZ).dt.date
    rows = rows.loc[rows["trade_date_ist"] == trade_date_ist].copy()
    if rows.empty:
        return {
            "trade_date_ist": str(trade_date_ist),
            "batch_count": 0,
            "event_count": 0,
            "reason": "core_sync_missing_for_trade_date",
        }

    rows = rows.sort_values(["timestamp_utc", "event_id"]).reset_index(drop=True)
    gaps = rows["timestamp_utc"].diff().dt.total_seconds().fillna(0.0)
    rows["batch_id"] = (gaps > 300.0).cumsum() + 1
    return {
        "trade_date_ist": str(trade_date_ist),
        "batch_count": int(rows["batch_id"].nunique()),
        "event_count": int(len(rows)),
        "reason": "ok",
        "first_event_utc": rows["timestamp_utc"].iloc[0].isoformat(),
        "last_event_utc": rows["timestamp_utc"].iloc[-1].isoformat(),
    }


def _is_pre_market_ist(now: datetime | None = None) -> bool:
    current = now or datetime.now(INDIA_TZ)
    market_open = time(hour=9, minute=15)
    return current.timetz().replace(tzinfo=None) < market_open


def _ledger_cash_position(master_ledger_path: Path, default_capital: float) -> float | None:
    if not master_ledger_path.exists():
        return None
    try:
        ledger_df = pd.read_parquet(master_ledger_path)
    except Exception:
        return None
    if ledger_df.empty:
        return float(default_capital)
    has_explicit_funding = False
    if "entry_type" in ledger_df.columns:
        entry_types = ledger_df["entry_type"].astype(str).str.upper()
        has_explicit_funding = bool(
            entry_types.isin(
                NAVCalculator._CASH_IN_ENTRY_TYPES | NAVCalculator._CASH_OUT_ENTRY_TYPES
            ).any()
        )
    cash_flows = ledger_df.apply(NAVCalculator._cash_flow_for_entry, axis=1)
    base_capital = 0.0 if has_explicit_funding else float(default_capital)
    return float(base_capital + pd.to_numeric(cash_flows, errors="coerce").fillna(0.0).sum())


def compute_runtime_accounting_sanity(project_root: Path, trade_date_ist=None) -> Dict[str, Any]:
    runtime_db_path = project_root / "data/runtime/portfolio_runtime.db"
    master_ledger_path = project_root / "data/pnl/master_ledger.parquet"
    current_positions_path = project_root / "data/portfolio/current_positions.json"
    trade_date_ist = trade_date_ist or datetime.now(INDIA_TZ).date()
    current_positions = _read_json(current_positions_path)
    issues: List[str] = []
    skipped_checks: List[str] = []

    batch_summary = _core_sync_batch_summary(runtime_db_path, trade_date_ist)
    batch_count = int(batch_summary.get("batch_count", 0))
    if batch_count != 1:
        if _is_pre_market_ist() and batch_count == 0:
            skipped_checks.append("same_day_core_sync_not_expected_pre_market")
        else:
            issues.append(
                "rebalance.core.sync batch count "
                f"{batch_count} for trade_date={trade_date_ist}"
            )

    current_positions_count = int(
        current_positions.get("positions_count")
        or len(current_positions.get("positions") or {})
    )
    current_positions_cash = _safe_float(current_positions.get("cash"), default=float("nan"))
    if not current_positions:
        issues.append("current_positions.json missing or invalid")
    elif not math.isfinite(current_positions_cash):
        issues.append("current_positions cash missing or invalid")

    default_capital = _positions_default_capital(current_positions)
    ledger_cash = _ledger_cash_position(master_ledger_path, default_capital=default_capital)
    if ledger_cash is None:
        issues.append("master ledger missing or unreadable")
    elif math.isfinite(current_positions_cash) and not math.isclose(
        float(ledger_cash),
        float(current_positions_cash),
        rel_tol=0.0,
        abs_tol=1e-6,
    ):
        issues.append(
            "ledger cash mismatch "
            f"(ledger={float(ledger_cash):.6f}, current_positions={float(current_positions_cash):.6f})"
        )

    runtime_holdings_count, runtime_holdings_reason = _load_runtime_holdings_count(runtime_db_path)
    if runtime_holdings_reason != "ok":
        issues.append(f"runtime holdings unavailable ({runtime_holdings_reason})")
    elif int(runtime_holdings_count) != int(current_positions_count):
        issues.append(
            "runtime holdings count mismatch "
            f"(runtime={int(runtime_holdings_count)}, current_positions={int(current_positions_count)})"
        )

    return {
        "status": "SKIP" if skipped_checks and not issues else ("PASS" if not issues else "FAIL"),
        "trade_date_ist": str(trade_date_ist),
        "core_sync_batch_count": int(batch_summary.get("batch_count", 0)),
        "core_sync_event_count": int(batch_summary.get("event_count", 0)),
        "ledger_cash": None if ledger_cash is None else float(ledger_cash),
        "current_positions_cash": None if not math.isfinite(current_positions_cash) else float(current_positions_cash),
        "runtime_holdings_count": int(runtime_holdings_count),
        "current_positions_count": int(current_positions_count),
        "issues": issues,
        "skipped_checks": skipped_checks,
    }


def _artifact_trade_date_ist(path: Path) -> date | None:
    if not path.exists():
        return None
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, INDIA_TZ).date()
    except Exception:
        return None


def _pre_market_standby_ready(project_root: Path, trade_date_ist=None) -> tuple[bool, str]:
    """
    Return whether pre-market idle state is acceptable.

    Before launch, the live options engine is not expected to hold a fresh lock
    or heartbeat if today's scoring artifacts have already been refreshed.
    """
    trade_date_ist = trade_date_ist or datetime.now(INDIA_TZ).date()
    if not _is_pre_market_ist():
        return False, ""

    scores_history = project_root / "data/processed/score_history" / f"scores_{trade_date_ist:%Y%m%d}.parquet"
    scores_latest = project_root / "data/processed/scores.parquet"

    if scores_history.exists():
        return True, f"Pre-market standby: today's scores snapshot exists ({scores_history.name})"

    latest_trade_date = _artifact_trade_date_ist(scores_latest)
    if latest_trade_date == trade_date_ist:
        return True, "Pre-market standby: scores.parquet refreshed for today's session"

    return False, ""


class PreOpenChecker:
    """Pre-market system readiness checker"""
    
    def __init__(self):
        self.checks = []
        self.failures = []
        self.warnings = []
        
        # Initialize components
        self.clock_guard = ClockGuard()
        self.state_io = StateIOManager(PROJECT_ROOT / "data/options/live")
        self.recovery_manager = StateRecoveryManager(PROJECT_ROOT / "data/options/live")
        self.integrity_checker = AccountingIntegrityChecker()

    @staticmethod
    def _read_json(path: Path) -> Dict[str, Any]:
        return _read_json(path)

    @staticmethod
    def _is_pid_running(pid: Any) -> bool:
        try:
            os.kill(int(pid), 0)
            return True
        except Exception:
            return False

    @staticmethod
    def _parse_timestamp(raw_value: Any) -> datetime | None:
        try:
            parsed = pd.to_datetime(raw_value, errors="coerce")
            if pd.isna(parsed):
                return None
            return pd.Timestamp(parsed).to_pydatetime()
        except Exception:
            return None
    
    def run_all_checks(self) -> Dict[str, Any]:
        """Run all pre-open checks"""
        logger.info("=" * 60)
        logger.info("NORTHSTAR V3 PRE-OPEN CHECKLIST")
        logger.info("=" * 60)
        
        start_time = datetime.now()

        # Run individual checks
        self.check_trading_halt()
        self.check_system_time()
        self.check_daemon_status()
        self.check_process_locks()
        self.check_heartbeats()
        self.check_state_integrity()
        self.check_ledger_underlying_attribution()
        self.check_wal_status()
        self.check_governance_events()
        self.check_governor_capital_structure()  # NEW: Check Portfolio Governor
        self.check_runtime_accounting_sanity()
        self.check_market_data_connectivity()
        self.check_alternative_data_freshness()
        self.check_sentiment_data_freshness()
        self.check_disk_space()
        self.check_log_files()
        
        # Generate summary
        summary = self.generate_summary(start_time)
        
        # Print results
        self.print_results(summary)
        
        return summary
    
    def check_trading_halt(self):
        """Fail pre-open if the TRADING_HALTED flag is set.

        The flag is raised by scripts/emergency_halt.py or by a CRITICAL EOD
        reconciliation failure, and cleared by scripts/resume_trading.py. It
        also blocks new orders at the runtime execution gate; surfacing it here
        makes the halt visible to an operator before the session starts.
        """
        logger.info("0. Checking trading-halt flag...")
        try:
            from src.execution.trading_halt import is_trading_halted, halt_reason

            if is_trading_halted():
                self.failures.append({
                    'check': 'trading_halt',
                    'status': 'FAIL',
                    'message': f"TRADING_HALTED flag is set: {halt_reason()}. "
                               f"Resolve and run scripts/resume_trading.py before trading."
                })
            else:
                self.checks.append({
                    'check': 'trading_halt',
                    'status': 'PASS',
                    'message': 'No trading halt in effect'
                })
        except Exception as e:
            self.failures.append({
                'check': 'trading_halt',
                'status': 'ERROR',
                'message': f"Trading-halt check failed: {e}"
            })

    def check_system_time(self):
        """Check system time and timezone"""
        logger.info("1. Checking system time and timezone...")
        
        try:
            time_check = self.clock_guard.comprehensive_time_check()
            
            if time_check['trading_safe']:
                self.checks.append({
                    'check': 'system_time',
                    'status': 'PASS',
                    'message': 'Time verification passed - trading safe'
                })
            else:
                self.failures.append({
                    'check': 'system_time',
                    'status': 'FAIL',
                    'message': f"Time issues detected: {time_check['alerts']}"
                })
            
        except Exception as e:
            self.failures.append({
                'check': 'system_time',
                'status': 'ERROR',
                'message': f"Time check failed: {e}"
            })
    
    def check_daemon_status(self):
        """Check if Northstar daemon is running"""
        logger.info("2. Checking daemon status...")
        
        try:
            status_file = PROJECT_ROOT / "data/options/live/northstar_daemon_status.json"
            orchestrator_file = PROJECT_ROOT / "data/options/live/trading_day_orchestrator_status.json"
            heartbeat_file = PROJECT_ROOT / "data/options/live/live_engine_heartbeat.json"
            runtime_file = PROJECT_ROOT / "data/options/live/options_runtime_state.json"
            
            status = self._read_json(status_file)
            orchestrator_status = self._read_json(orchestrator_file)
            heartbeat = self._read_json(heartbeat_file)
            runtime = self._read_json(runtime_file)

            daemon_pid = status.get('daemon_pid')
            daemon_running = self._is_pid_running(daemon_pid) if daemon_pid else False

            process_entries = orchestrator_status.get("processes") or []
            active_processes = [
                entry.get("name", "unknown")
                for entry in process_entries
                if self._is_pid_running(entry.get("pid"))
            ]

            hb_ts = self._parse_timestamp(heartbeat.get("timestamp"))
            runtime_ts = self._parse_timestamp(runtime.get("timestamp"))
            orch_ts = self._parse_timestamp(orchestrator_status.get("timestamp"))
            freshness_candidates = [value for value in [hb_ts, runtime_ts, orch_ts] if value is not None]
            freshest = max(freshness_candidates, key=lambda value: value.timestamp()) if freshness_candidates else None

            if daemon_running:
                self.checks.append({
                    'check': 'daemon_status',
                    'status': 'PASS',
                    'message': f'Legacy daemon running (PID: {daemon_pid})'
                })
                return

            if active_processes:
                self.checks.append({
                    'check': 'daemon_status',
                    'status': 'PASS',
                    'message': f"Canonical launch surface active: {', '.join(active_processes)}"
                })
                return

            standby_ready, standby_msg = _pre_market_standby_ready(PROJECT_ROOT)
            if standby_ready:
                self.checks.append({
                    'check': 'daemon_status',
                    'status': 'PASS',
                    'message': standby_msg + " - live engine not expected before launch window"
                })
                return

            if freshest is not None:
                age_hours = (datetime.now(freshest.tzinfo) - freshest).total_seconds() / 3600
                stage = orchestrator_status.get("stage", "unknown")
                self.warnings.append({
                    'check': 'daemon_status',
                    'status': 'WARN',
                    'message': f'No live process currently running, but runtime artifacts are present ({age_hours:.1f}h old, stage={stage})'
                })
                return

            self.warnings.append({
                'check': 'daemon_status',
                'status': 'WARN',
                'message': 'No daemon or orchestrator status found yet - start canonical live stack before market open'
            })
                
        except Exception as e:
            self.failures.append({
                'check': 'daemon_status',
                'status': 'ERROR',
                'message': f"Daemon status check failed: {e}"
            })
    
    def check_process_locks(self):
        """Check process lock files"""
        logger.info("3. Checking process locks...")
        
        try:
            lock_file = PROJECT_ROOT / "data/options/live/options_engine.lock"
            standby_ready, standby_msg = _pre_market_standby_ready(PROJECT_ROOT)
            
            if lock_file.exists():
                with open(lock_file, 'r') as f:
                    lock_info = json.load(f)
                lock_pid = int(lock_info.get("pid", 0) or 0)
                lock_pid_running = False
                if lock_pid > 0:
                    try:
                        os.kill(lock_pid, 0)
                        lock_pid_running = True
                    except OSError:
                        lock_pid_running = False

                if lock_pid_running:
                    self.checks.append({
                        'check': 'process_locks',
                        'status': 'PASS',
                        'message': f'Process lock active (PID: {lock_pid})'
                    })
                else:
                    if standby_ready:
                        self.checks.append({
                            'check': 'process_locks',
                            'status': 'PASS',
                            'message': standby_msg + f" - ignoring stale pre-market lock placeholder (PID: {lock_pid})"
                        })
                    else:
                        self.warnings.append({
                            'check': 'process_locks',
                            'status': 'WARN',
                            'message': f'Stale process lock file detected (PID: {lock_pid})'
                        })
            else:
                if standby_ready:
                    self.checks.append({
                        'check': 'process_locks',
                        'status': 'PASS',
                        'message': standby_msg + " - no live lock expected before engine launch"
                    })
                else:
                    self.warnings.append({
                        'check': 'process_locks',
                        'status': 'WARN',
                        'message': 'No process lock file found'
                    })
                
        except Exception as e:
            self.failures.append({
                'check': 'process_locks',
                'status': 'ERROR',
                'message': f"Process lock check failed: {e}"
            })
    
    def check_heartbeats(self):
        """Check system heartbeats"""
        logger.info("4. Checking heartbeats...")
        
        try:
            heartbeat_file = PROJECT_ROOT / "data/options/live/live_engine_heartbeat.json"
            orchestrator_file = PROJECT_ROOT / "data/options/live/trading_day_orchestrator_status.json"
            standby_ready, standby_msg = _pre_market_standby_ready(PROJECT_ROOT)
            
            if not heartbeat_file.exists():
                if standby_ready:
                    self.checks.append({
                        'check': 'heartbeats',
                        'status': 'PASS',
                        'message': standby_msg + " - no live heartbeat expected before launch"
                    })
                else:
                    orchestrator_status = self._read_json(orchestrator_file)
                    orch_ts = self._parse_timestamp(orchestrator_status.get("timestamp"))
                    if orch_ts is not None:
                        age_hours = (datetime.now(orch_ts.tzinfo) - orch_ts).total_seconds() / 3600
                        self.warnings.append({
                            'check': 'heartbeats',
                            'status': 'WARN',
                            'message': f'No live heartbeat file found, but trading-day orchestrator updated {age_hours:.1f}h ago'
                        })
                    else:
                        self.warnings.append({
                            'check': 'heartbeats',
                            'status': 'WARN',
                            'message': 'No heartbeat file found'
                        })
                return
            
            with open(heartbeat_file, 'r') as f:
                heartbeat = json.load(f)
            
            last_heartbeat = datetime.fromisoformat(heartbeat['timestamp'])
            now_ref = datetime.now(last_heartbeat.tzinfo) if last_heartbeat.tzinfo else datetime.now()
            age_minutes = (now_ref - last_heartbeat).total_seconds() / 60
            
            if age_minutes < 10:  # Fresh within 10 minutes
                self.checks.append({
                    'check': 'heartbeats',
                    'status': 'PASS',
                    'message': f'Heartbeat fresh ({age_minutes:.1f} minutes old)'
                })
            else:
                if standby_ready:
                    self.checks.append({
                        'check': 'heartbeats',
                        'status': 'PASS',
                        'message': standby_msg + f" - prior-session heartbeat acceptable pre-market ({age_minutes:.1f} minutes old)"
                    })
                else:
                    self.warnings.append({
                        'check': 'heartbeats',
                        'status': 'WARN',
                        'message': f'Heartbeat stale ({age_minutes:.1f} minutes old)'
                    })
                
        except Exception as e:
            self.failures.append({
                'check': 'heartbeats',
                'status': 'ERROR',
                'message': f"Heartbeat check failed: {e}"
            })
    
    def check_state_integrity(self):
        """Check state file integrity"""
        logger.info("5. Checking state integrity...")
        
        try:
            integrity_report = self.recovery_manager.check_state_integrity()
            
            if integrity_report['overall_status'] == 'healthy':
                self.checks.append({
                    'check': 'state_integrity',
                    'status': 'PASS',
                    'message': 'All state files healthy'
                })
            elif integrity_report['overall_status'] == 'incomplete':
                self.warnings.append({
                    'check': 'state_integrity',
                    'status': 'WARN',
                    'message': f"Missing files: {integrity_report['issues_found']}"
                })
            else:
                self.failures.append({
                    'check': 'state_integrity',
                    'status': 'FAIL',
                    'message': f"State corruption: {integrity_report['issues_found']}"
                })
                
        except Exception as e:
            self.failures.append({
                'check': 'state_integrity',
                'status': 'ERROR',
                'message': f"State integrity check failed: {e}"
            })
    
    def check_wal_status(self):
        """Check Write-Ahead Log status"""
        logger.info("6. Checking WAL status...")
        
        try:
            interrupted_ops = self.state_io.check_interrupted_operations()
            
            if not interrupted_ops:
                self.checks.append({
                    'check': 'wal_status',
                    'status': 'PASS',
                    'message': 'No interrupted operations'
                })
            else:
                self.warnings.append({
                    'check': 'wal_status',
                    'status': 'WARN',
                    'message': f'{len(interrupted_ops)} interrupted operations found'
                })
                
        except Exception as e:
            self.failures.append({
                'check': 'wal_status',
                'status': 'ERROR',
                'message': f"WAL check failed: {e}"
            })

    def check_ledger_underlying_attribution(self):
        """Check for generic/invalid ledger underlyings that break concentration controls."""
        logger.info("6b. Checking ledger underlying attribution...")
        try:
            ledger_path = PROJECT_ROOT / "data/options/trade_ledger.parquet"
            if not ledger_path.exists():
                self.warnings.append({
                    'check': 'ledger_underlying_attribution',
                    'status': 'WARN',
                    'message': 'Trade ledger missing; cannot audit underlying attribution'
                })
                return

            df = pd.read_parquet(ledger_path)
            if df.empty or 'underlying' not in df.columns:
                self.warnings.append({
                    'check': 'ledger_underlying_attribution',
                    'status': 'WARN',
                    'message': 'No underlying column data available for attribution audit'
                })
                return

            generic_tokens = {'NSE', 'NSE_EQ', 'NSE_FO', 'NSE_INDEX', 'NFO', 'BSE', 'BSE_EQ', 'BSE_FO', 'UNKNOWN'}
            u = df['underlying'].astype(str).str.strip().str.upper()
            generic_rows = int(u.isin(generic_tokens).sum())
            ratio = float(generic_rows / len(df)) if len(df) > 0 else 0.0
            if ratio > 0.10:
                self.warnings.append({
                    'check': 'ledger_underlying_attribution',
                    'status': 'WARN',
                    'message': (
                        f'Generic underlying ratio high: {generic_rows}/{len(df)} '
                        f'({ratio:.1%}). Run scripts/audit_underlying_attribution.py'
                    )
                })
            else:
                self.checks.append({
                    'check': 'ledger_underlying_attribution',
                    'status': 'PASS',
                    'message': f'Underlying attribution healthy ({ratio:.1%} generic rows)'
                })
        except Exception as e:
            self.warnings.append({
                'check': 'ledger_underlying_attribution',
                'status': 'WARN',
                'message': f'Underlying attribution audit failed: {e}'
            })
    
    def check_governance_events(self):
        """Check recent governance events"""
        logger.info("7. Checking governance events...")
        
        try:
            events_file = PROJECT_ROOT / "data/options/live/governance_events.parquet"
            
            if not events_file.exists():
                self.warnings.append({
                    'check': 'governance_events',
                    'status': 'WARN',
                    'message': 'No governance events file found'
                })
                return
            
            df = pd.read_parquet(events_file)
            
            # Check for recent critical events
            ts = pd.to_datetime(df['timestamp'], errors='coerce', utc=True)
            cutoff = pd.Timestamp(datetime.now(timezone.utc)) - pd.Timedelta(hours=24)
            recent_events = df[ts > cutoff]
            critical_events = recent_events[recent_events['severity'] == 'critical']
            
            if critical_events.empty:
                self.checks.append({
                    'check': 'governance_events',
                    'status': 'PASS',
                    'message': f'{len(recent_events)} recent events, no critical issues'
                })
            else:
                self.warnings.append({
                    'check': 'governance_events',
                    'status': 'WARN',
                    'message': f'{len(critical_events)} critical events in last 24h'
                })
                
        except Exception as e:
            self.failures.append({
                'check': 'governance_events',
                'status': 'ERROR',
                'message': f"Governance events check failed: {e}"
            })
    
    def check_governor_capital_structure(self):
        """Check Portfolio Governor capital structure for today"""
        logger.info("8. Checking Portfolio Governor capital structure...")
        
        try:
            from src.portfolio.governor import PortfolioGovernor
            from src.core.state import UnifiedState
            
            # Initialize
            state = UnifiedState()
            state_snapshot = PROJECT_ROOT / "data" / "state" / "unified_state.json"
            if state_snapshot.exists():
                with open(state_snapshot, 'r') as f:
                    state.load_snapshot(json.load(f))
            governor = PortfolioGovernor(config={'starting_capital_inr': 10_000_000})
            
            # Compute today's capital structure
            capital_structure = governor.compute_capital_structure(state)
            regime = capital_structure.capital_structure_regime.value
            
            # Log the structure
            logger.info(f"   Regime: {regime}")
            logger.info(f"   Equity: {capital_structure.equity_fraction * 100:.1f}% (₹{capital_structure.equity_budget_inr:,.0f})")
            logger.info(f"   Options: {capital_structure.options_fraction * 100:.1f}% (₹{capital_structure.options_budget_inr:,.0f})")
            logger.info(f"   Cash: {capital_structure.cash_fraction * 100:.1f}% (₹{capital_structure.cash_reserve_inr:,.0f})")
            
            # Alert if defensive or crisis
            if regime in ['DEFENSIVE', 'CAPITAL_PRESERVATION']:
                self.warnings.append({
                    'check': 'governor_capital_structure',
                    'status': 'WARN',
                    'message': f"{regime} MODE - Equity reduced to {capital_structure.equity_fraction * 100:.1f}%"
                })
            else:
                self.checks.append({
                    'check': 'governor_capital_structure',
                    'status': 'PASS',
                    'message': f"{regime} regime - Equity {capital_structure.equity_fraction * 100:.1f}%"
                })
                
        except Exception as e:
            self.warnings.append({
                'check': 'governor_capital_structure',
                'status': 'WARN',
                'message': f"Governor check failed (non-critical): {e}"
            })

    def check_runtime_accounting_sanity(self):
        """Assert the canonical runtime, ledger, and current positions views reconcile."""
        logger.info("8b. Checking runtime accounting sanity...")

        try:
            report = compute_runtime_accounting_sanity(PROJECT_ROOT)
            if report["status"] == "PASS":
                self.checks.append({
                    'check': 'runtime_accounting_sanity',
                    'status': 'PASS',
                    'message': (
                        f"1 core sync batch, cash matched at ₹{float(report['ledger_cash'] or 0.0):,.2f}, "
                        f"runtime holdings={int(report['runtime_holdings_count'])}"
                    )
                })
            elif report["status"] == "SKIP":
                self.checks.append({
                    'check': 'runtime_accounting_sanity',
                    'status': 'SKIP',
                    'message': 'Pre-market: same-day rebalance.core.sync batch is not yet expected'
                })
            else:
                self.failures.append({
                    'check': 'runtime_accounting_sanity',
                    'status': 'FAIL',
                    'message': '; '.join(report.get("issues") or ['runtime accounting sanity failed'])
                })
        except Exception as e:
            self.failures.append({
                'check': 'runtime_accounting_sanity',
                'status': 'ERROR',
                'message': f"Runtime accounting sanity check failed: {e}"
            })
    
    def check_market_data_connectivity(self):
        """Check market data connectivity"""
        logger.info("8. Checking market data connectivity...")
        
        try:
            import requests

            access_token, token_source = _resolve_upstox_probe_token()
            env_file = Path(str(os.getenv("UPSTOX_ENV_FILE", PROJECT_ROOT / ".env.options")).strip())
            token_age_hours = None
            if env_file.exists():
                token_age_hours = max(
                    0.0,
                    (datetime.now().timestamp() - env_file.stat().st_mtime) / 3600.0,
                )

            if access_token and access_token not in {"your_access_token", "your_token_here", "ROTATE_REQUIRED"}:
                response = requests.get(
                    "https://api.upstox.com/v2/user/profile",
                    headers={
                        "Accept": "application/json",
                        "Authorization": f"Bearer {access_token}",
                    },
                    timeout=10,
                )
                if response.status_code == 200:
                    self.checks.append({
                        'check': 'market_data',
                        'status': 'PASS',
                        'message': 'Upstox credentials configured and authenticated'
                    })
                elif response.status_code == 401:
                    detail = (
                        f"Upstox access token from {token_source} was rejected by broker API; "
                        "daily token rotation is required. Run `python3 scripts/refresh_upstox_token.py`."
                    )
                    if token_age_hours is not None:
                        detail += f" Credential file age: {token_age_hours:.1f}h."
                    self.failures.append({
                        'check': 'market_data',
                        'status': 'FAIL',
                        'message': detail
                    })
                else:
                    self.warnings.append({
                        'check': 'market_data',
                        'status': 'WARN',
                        'message': f'Upstox auth probe returned HTTP {response.status_code}'
                    })
            else:
                self.warnings.append({
                    'check': 'market_data',
                    'status': 'WARN',
                    'message': 'Upstox access token not configured in active credential sources'
                })
                
        except requests.RequestException as e:
            self.warnings.append({
                'check': 'market_data',
                'status': 'WARN',
                'message': f"Upstox connectivity probe failed: {e}"
            })
        except Exception as e:
            self.failures.append({
                'check': 'market_data',
                'status': 'ERROR',
                'message': f"Market data check failed: {e}"
            })
    
    def check_alternative_data_freshness(self):
        """Check alternative data freshness and systemic risk"""
        logger.info("9. Checking alternative data freshness...")
        
        try:
            from src.alternative_data.alternative_pipeline_runner import AlternativePipelineRunner
            from src.alternative_data.risk_alternative_bridge import RiskAlternativeBridge
            from src.ingestion import IngestionRegistry
            from datetime import datetime
            
            # Initialize components
            config = {
                'alternative_data': {
                    'freshness_thresholds': {
                    'bulk_deals_max_age_days': 2,
                    'power_data_max_age_days': 3,
                    'credit_ratings_max_age_days': 7,
                    'gst_data_max_age_months': 1.5,
                    'promoter_pledges_max_age_days': 100
                    }
                }
            }
            
            runner = AlternativePipelineRunner(config, event_bus=None)
            registry = IngestionRegistry()
            risk_bridge = RiskAlternativeBridge(registry, config)
            
            # Check source freshness
            as_of_date = datetime.now()
            sources = ['gst', 'power', 'credit', 'bulk', 'pledge']
            fresh_sources = []
            stale_sources = []
            
            for source in sources:
                if runner.is_source_fresh(source, as_of_date):
                    fresh_sources.append(source)
                else:
                    stale_sources.append(source)
            
            # Check systemic risk
            systemic_risk = risk_bridge.get_systemic_risk_signals(as_of_date)
            escalation_level = systemic_risk.get('escalation_level', 'NORMAL')
            
            # Determine status
            if escalation_level in ['CRISIS', 'SEVERE']:
                self.failures.append({
                    'check': 'alternative_data',
                    'status': 'FAIL',
                    'message': f"Systemic risk escalation: {escalation_level}"
                })
            elif escalation_level == 'ELEVATED' or len(stale_sources) > 3:
                self.warnings.append({
                    'check': 'alternative_data',
                    'status': 'WARN',
                    'message': f"Fresh: {len(fresh_sources)}/5 sources, Risk: {escalation_level}"
                })
            else:
                self.checks.append({
                    'check': 'alternative_data',
                    'status': 'PASS',
                    'message': f"Fresh: {len(fresh_sources)}/5 sources, Risk: {escalation_level}"
                })
                
        except Exception as e:
            self.warnings.append({
                'check': 'alternative_data',
                'status': 'WARN',
                'message': f"Alternative data check failed (non-critical): {e}"
            })
    
    def check_sentiment_data_freshness(self):
        """Check sentiment data freshness and history depth"""
        logger.info("10. Checking sentiment data freshness...")
        
        try:
            from pathlib import Path
            import pandas as pd
            from datetime import datetime, timedelta
            
            ticker_path = Path("data/processed/sentiment/ticker_sentiment_daily.parquet")
            market_path = Path("data/processed/sentiment/market_sentiment_daily.parquet")
            
            if not ticker_path.exists() or not market_path.exists():
                self.failures.append({
                    'check': 'sentiment_data',
                    'status': 'FAIL',
                    'message': 'Sentiment data files missing'
                })
                return
            
            # Load data
            ticker_df = pd.read_parquet(ticker_path)
            market_df = pd.read_parquet(market_path)
            
            # Check ticker sentiment
            ticker_df['date'] = pd.to_datetime(ticker_df.get('availability_date', ticker_df.get('date')))
            latest_ticker = ticker_df['date'].max()
            oldest_ticker = ticker_df['date'].min()
            ticker_days = (latest_ticker - oldest_ticker).days
            ticker_count = len(ticker_df)
            
            # Check market sentiment
            market_df['date'] = pd.to_datetime(market_df.get('availability_date', market_df.get('date')))
            latest_market = market_df['date'].max()
            oldest_market = market_df['date'].min()
            market_days = (latest_market - oldest_market).days
            market_count = len(market_df)
            
            # Check freshness (should be within 1 day)
            now = pd.Timestamp.now()
            ticker_age_days = (now - latest_ticker).days
            market_age_days = (now - latest_market).days
            
            # Check history depth (need 60+ days for regime classifier)
            min_history_days = 60
            
            # Determine status
            issues = []
            if ticker_age_days > 1:
                issues.append(f"Ticker data {ticker_age_days}d old")
            if market_age_days > 1:
                issues.append(f"Market data {market_age_days}d old")
            if ticker_days < min_history_days:
                issues.append(f"Ticker history only {ticker_days}d (need {min_history_days}+)")
            if market_days < min_history_days:
                issues.append(f"Market history only {market_days}d (need {min_history_days}+)")
            
            if issues:
                if ticker_days < min_history_days or market_days < min_history_days:
                    self.failures.append({
                        'check': 'sentiment_data',
                        'status': 'FAIL',
                        'message': f"Insufficient history: {', '.join(issues)}"
                    })
                else:
                    self.warnings.append({
                        'check': 'sentiment_data',
                        'status': 'WARN',
                        'message': f"Stale data: {', '.join(issues)}"
                    })
            else:
                self.checks.append({
                    'check': 'sentiment_data',
                    'status': 'PASS',
                    'message': f"Ticker: {ticker_count} rows, {ticker_days}d history | Market: {market_count} rows, {market_days}d history"
                })
                
        except Exception as e:
            self.failures.append({
                'check': 'sentiment_data',
                'status': 'FAIL',
                'message': f"Sentiment check failed: {e}"
            })
    
    def check_disk_space(self):
        """Check available disk space"""
        logger.info("9. Checking disk space...")
        
        try:
            import shutil
            
            total, used, free = shutil.disk_usage(PROJECT_ROOT)
            free_gb = free / (1024**3)
            free_pct = (free / total) * 100
            
            if free_gb > 5 and free_pct > 10:
                self.checks.append({
                    'check': 'disk_space',
                    'status': 'PASS',
                    'message': f'{free_gb:.1f} GB free ({free_pct:.1f}%)'
                })
            elif free_gb > 1:
                self.warnings.append({
                    'check': 'disk_space',
                    'status': 'WARN',
                    'message': f'Low disk space: {free_gb:.1f} GB free ({free_pct:.1f}%)'
                })
            else:
                self.failures.append({
                    'check': 'disk_space',
                    'status': 'FAIL',
                    'message': f'Critical disk space: {free_gb:.1f} GB free ({free_pct:.1f}%)'
                })
                
        except Exception as e:
            self.failures.append({
                'check': 'disk_space',
                'status': 'ERROR',
                'message': f"Disk space check failed: {e}"
            })
    
    def check_log_files(self):
        """Check log file status"""
        logger.info("10. Checking log files...")
        
        try:
            logs_dir = PROJECT_ROOT / "logs"
            
            if not logs_dir.exists():
                self.warnings.append({
                    'check': 'log_files',
                    'status': 'WARN',
                    'message': 'Logs directory not found'
                })
                return
            
            # Check for recent log activity
            log_files = list(logs_dir.glob("*.log"))
            
            if log_files:
                # Check most recent log file
                latest_log = max(log_files, key=lambda f: f.stat().st_mtime)
                age_hours = (datetime.now().timestamp() - latest_log.stat().st_mtime) / 3600
                
                if age_hours < 24:
                    self.checks.append({
                        'check': 'log_files',
                        'status': 'PASS',
                        'message': f'Recent log activity ({len(log_files)} files)'
                    })
                else:
                    self.warnings.append({
                        'check': 'log_files',
                        'status': 'WARN',
                        'message': f'No recent log activity ({age_hours:.1f}h old)'
                    })
            else:
                self.warnings.append({
                    'check': 'log_files',
                    'status': 'WARN',
                    'message': 'No log files found'
                })
                
        except Exception as e:
            self.failures.append({
                'check': 'log_files',
                'status': 'ERROR',
                'message': f"Log files check failed: {e}"
            })
    
    def generate_summary(self, start_time: datetime) -> Dict[str, Any]:
        """Generate check summary"""
        total_checks = len(self.checks) + len(self.warnings) + len(self.failures)
        duration = (datetime.now() - start_time).total_seconds()
        
        # Determine overall status
        if self.failures:
            overall_status = "FAIL"
        elif self.warnings:
            overall_status = "WARN"
        else:
            overall_status = "PASS"
        
        return {
            'timestamp': datetime.now().isoformat(),
            'duration_seconds': duration,
            'overall_status': overall_status,
            'total_checks': total_checks,
            'passed': len(self.checks),
            'warnings': len(self.warnings),
            'failures': len(self.failures),
            'checks': self.checks,
            'warnings_list': self.warnings,
            'failures_list': self.failures,
            'ready_for_trading': overall_status != "FAIL"
        }
    
    def print_results(self, summary: Dict[str, Any]):
        """Print check results"""
        logger.info("=" * 60)
        logger.info("PRE-OPEN CHECK RESULTS")
        logger.info("=" * 60)
        
        # Print passed checks
        for check in self.checks:
            logger.info(f"✅ {check['check'].upper()}: {check['message']}")
        
        # Print warnings
        for warning in self.warnings:
            logger.warning(f"⚠️  {warning['check'].upper()}: {warning['message']}")
        
        # Print failures
        for failure in self.failures:
            logger.error(f"❌ {failure['check'].upper()}: {failure['message']}")
        
        # Print summary
        logger.info("=" * 60)
        logger.info(f"SUMMARY: {summary['overall_status']}")
        logger.info(f"Passed: {summary['passed']}, Warnings: {summary['warnings']}, Failures: {summary['failures']}")
        logger.info(f"Duration: {summary['duration_seconds']:.1f}s")
        
        if summary['ready_for_trading']:
            logger.info("🟢 SYSTEM READY FOR TRADING")
        else:
            logger.error("🔴 SYSTEM NOT READY - RESOLVE FAILURES BEFORE TRADING")
        
        logger.info("=" * 60)


def main():
    """Main entry point"""
    checker = PreOpenChecker()
    summary = checker.run_all_checks()
    
    # Save results
    results_file = PROJECT_ROOT / "data/options/live/preopen_check_results.json"
    results_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(results_file, 'w') as f:
        json.dump(summary, f, indent=2, default=str)
    
    # Exit with appropriate code
    return 0 if summary['ready_for_trading'] else 1


if __name__ == "__main__":
    sys.exit(main())
