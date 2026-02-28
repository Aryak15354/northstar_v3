#!/usr/bin/env python3
"""
Pre-Open Checklist Script for Northstar V2

Performs comprehensive pre-market checks to ensure system readiness.
"""

import sys
import os
import json
import logging
from pathlib import Path
from datetime import datetime, time, timezone
from typing import Dict, Any, List
import pandas as pd

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.options.clock_guard import ClockGuard
from src.options.state_io import StateIOManager
from src.options.state_recovery import StateRecoveryManager
from src.options.accounting_integrity import AccountingIntegrityChecker

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


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
    
    def run_all_checks(self) -> Dict[str, Any]:
        """Run all pre-open checks"""
        logger.info("=" * 60)
        logger.info("NORTHSTAR V2 PRE-OPEN CHECKLIST")
        logger.info("=" * 60)
        
        start_time = datetime.now()
        
        # Run individual checks
        self.check_system_time()
        self.check_daemon_status()
        self.check_process_locks()
        self.check_heartbeats()
        self.check_state_integrity()
        self.check_ledger_underlying_attribution()
        self.check_wal_status()
        self.check_governance_events()
        self.check_market_data_connectivity()
        self.check_disk_space()
        self.check_log_files()
        
        # Generate summary
        summary = self.generate_summary(start_time)
        
        # Print results
        self.print_results(summary)
        
        return summary
    
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
            
            if not status_file.exists():
                self.failures.append({
                    'check': 'daemon_status',
                    'status': 'FAIL',
                    'message': 'Daemon status file not found - daemon not running'
                })
                return
            
            with open(status_file, 'r') as f:
                status = json.load(f)
            
            # Check if daemon PID is still running
            daemon_pid = status.get('daemon_pid')
            if daemon_pid:
                try:
                    os.kill(daemon_pid, 0)  # Check if process exists
                    self.checks.append({
                        'check': 'daemon_status',
                        'status': 'PASS',
                        'message': f'Daemon running (PID: {daemon_pid})'
                    })
                except OSError:
                    self.failures.append({
                        'check': 'daemon_status',
                        'status': 'FAIL',
                        'message': f'Daemon PID {daemon_pid} not found - process died'
                    })
            else:
                self.failures.append({
                    'check': 'daemon_status',
                    'status': 'FAIL',
                    'message': 'No daemon PID in status file'
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
                    self.warnings.append({
                        'check': 'process_locks',
                        'status': 'WARN',
                        'message': f'Stale process lock file detected (PID: {lock_pid})'
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
            
            if not heartbeat_file.exists():
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
    
    def check_market_data_connectivity(self):
        """Check market data connectivity"""
        logger.info("8. Checking market data connectivity...")
        
        try:
            # Check if .env.options exists
            env_file = PROJECT_ROOT / ".env.options"
            if not env_file.exists():
                self.failures.append({
                    'check': 'market_data',
                    'status': 'FAIL',
                    'message': '.env.options file not found'
                })
                return
            
            # Check for access token
            with open(env_file, 'r') as f:
                content = f.read()
            
            if 'UPSTOX_ACCESS_TOKEN=' in content and 'your_access_token' not in content:
                self.checks.append({
                    'check': 'market_data',
                    'status': 'PASS',
                    'message': 'Upstox credentials configured'
                })
            else:
                self.warnings.append({
                    'check': 'market_data',
                    'status': 'WARN',
                    'message': 'Upstox access token not configured'
                })
                
        except Exception as e:
            self.failures.append({
                'check': 'market_data',
                'status': 'ERROR',
                'message': f"Market data check failed: {e}"
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
