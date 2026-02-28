"""
Governance Events Module for Northstar V2

Handles governance event logging, alerts, and audit trail.
"""

import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import pandas as pd
import json
import fcntl

logger = logging.getLogger(__name__)


class GovernanceEventLogger:
    """Logs governance events and manages alerts"""
    
    def __init__(self, log_path: Path, email_config: Optional[Dict[str, Any]] = None):
        self.log_path = log_path
        self.lock_path = self.log_path.with_suffix(f"{self.log_path.suffix}.lock")
        self.email_config = email_config or {}
        self.alert_cooldowns = {}  # Track alert cooldowns
        
        # Ensure log directory exists
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize log file if it doesn't exist
        if not self.log_path.exists():
            self._initialize_log_file()

    def _acquire_write_lock(self):
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        handle = open(self.lock_path, "w", encoding="utf-8")
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        return handle

    @staticmethod
    def _release_write_lock(handle) -> None:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except Exception:
            pass
        handle.close()

    def _read_events_df(self) -> pd.DataFrame:
        try:
            return pd.read_parquet(self.log_path)
        except Exception:
            return pd.DataFrame(
                columns=[
                    "event_id",
                    "timestamp",
                    "cycle_id",
                    "event_type",
                    "severity",
                    "mode_before",
                    "mode_after",
                    "details",
                    "resolved_at",
                    "operator_override",
                    "alert_sent",
                ]
            )

    def _write_events_df(self, df: pd.DataFrame) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.log_path.with_suffix(f"{self.log_path.suffix}.tmp")
        df.to_parquet(tmp_path, index=False)
        tmp_path.replace(self.log_path)
    
    def _initialize_log_file(self):
        """Initialize empty governance events log"""
        empty_df = pd.DataFrame(columns=[
            'event_id', 'timestamp', 'cycle_id', 'event_type', 'severity',
            'mode_before', 'mode_after', 'details', 'resolved_at',
            'operator_override', 'alert_sent'
        ])
        lock_handle = self._acquire_write_lock()
        try:
            self._write_events_df(empty_df)
        finally:
            self._release_write_lock(lock_handle)
        logger.info(f"Initialized governance events log: {self.log_path}")
    
    def log_event(self, event_type: str, severity: str, details: Dict[str, Any],
                  cycle_id: Optional[str] = None, mode_before: Optional[str] = None,
                  mode_after: Optional[str] = None) -> str:
        """
        Log a governance event
        
        Returns: event_id for tracking
        """
        event_id = f"{event_type}_{int(datetime.now().timestamp() * 1000)}"
        
        event_record = {
            'event_id': event_id,
            'timestamp': datetime.now(),
            'cycle_id': cycle_id,
            'event_type': event_type,
            'severity': severity,  # info, warning, error, critical
            'mode_before': mode_before,
            'mode_after': mode_after,
            'details': json.dumps(details),
            'resolved_at': None,
            'operator_override': False,
            'alert_sent': False
        }

        lock_handle = self._acquire_write_lock()
        try:
            # Load existing log
            df = self._read_events_df()

            # Append new event
            new_df = pd.DataFrame([event_record])
            if df.empty:
                df = new_df
            else:
                df = pd.concat([df, new_df], ignore_index=True)

            # Save updated log
            self._write_events_df(df)
        finally:
            self._release_write_lock(lock_handle)
        
        logger.info(f"Governance event logged: {event_type} ({severity}) - {event_id}")
        
        # Send alert if configured and needed
        if self._should_send_alert(event_type, severity):
            self._send_alert(event_record)
        
        return event_id
    
    def resolve_event(self, event_id: str, operator_override: bool = False) -> bool:
        """Mark an event as resolved"""
        try:
            lock_handle = self._acquire_write_lock()
            try:
                df = self._read_events_df()

                # Find and update the event
                mask = df['event_id'] == event_id
                if not mask.any():
                    logger.warning(f"Event not found for resolution: {event_id}")
                    return False

                df.loc[mask, 'resolved_at'] = datetime.now()
                df.loc[mask, 'operator_override'] = operator_override

                # Save updated log
                self._write_events_df(df)
            finally:
                self._release_write_lock(lock_handle)
            
            logger.info(f"Event resolved: {event_id} (operator_override: {operator_override})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to resolve event {event_id}: {e}")
            return False
    
    def _should_send_alert(self, event_type: str, severity: str) -> bool:
        """Determine if alert should be sent based on cooldown and severity"""
        if not self.email_config.get('enabled', False):
            return False
        
        # Only send alerts for warning and above
        if severity not in ['warning', 'error', 'critical']:
            return False
        
        # Check cooldown
        cooldown_key = f"{event_type}_{severity}"
        cooldown_minutes = self.email_config.get('cooldown_minutes', 60)
        
        if cooldown_key in self.alert_cooldowns:
            last_sent = self.alert_cooldowns[cooldown_key]
            if datetime.now() - last_sent < timedelta(minutes=cooldown_minutes):
                logger.debug(f"Alert suppressed due to cooldown: {cooldown_key}")
                return False
        
        return True
    
    def _send_alert(self, event_record: Dict[str, Any]) -> bool:
        """Send email alert for governance event"""
        try:
            if not self.email_config.get('enabled', False):
                return False
            
            # Create email content
            subject = f"Northstar Governance Alert: {event_record['event_type']} ({event_record['severity']})"
            
            body = f"""
Northstar Governance Alert

Event Type: {event_record['event_type']}
Severity: {event_record['severity']}
Timestamp: {event_record['timestamp']}
Cycle ID: {event_record.get('cycle_id', 'N/A')}

Mode Transition:
  From: {event_record.get('mode_before', 'N/A')}
  To: {event_record.get('mode_after', 'N/A')}

Details:
{json.dumps(json.loads(event_record['details']), indent=2)}

Event ID: {event_record['event_id']}

This is an automated alert from the Northstar trading system.
"""
            
            # Send email
            msg = MIMEMultipart()
            msg['From'] = self.email_config.get('from_address', 'northstar@localhost')
            msg['Subject'] = subject
            
            recipients = self.email_config.get('recipients', [])
            if not recipients:
                logger.warning("No email recipients configured")
                return False
            
            msg['To'] = ', '.join(recipients)
            msg.attach(MIMEText(body, 'plain'))
            
            # Send via SMTP
            smtp_server = self.email_config.get('smtp_server')
            smtp_port = self.email_config.get('smtp_port', 587)
            username = self.email_config.get('username')
            password = self.email_config.get('password')
            
            if not smtp_server:
                logger.warning("SMTP server not configured")
                return False
            
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                if username and password:
                    server.starttls()
                    server.login(username, password)
                
                server.send_message(msg)
            
            # Update cooldown
            cooldown_key = f"{event_record['event_type']}_{event_record['severity']}"
            self.alert_cooldowns[cooldown_key] = datetime.now()
            
            # Mark alert as sent in log
            self._mark_alert_sent(event_record['event_id'])
            
            logger.info(f"Governance alert sent: {event_record['event_id']}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send governance alert: {e}")
            return False
    
    def _mark_alert_sent(self, event_id: str):
        """Mark alert as sent in the log"""
        try:
            lock_handle = self._acquire_write_lock()
            try:
                df = self._read_events_df()
                mask = df['event_id'] == event_id
                if mask.any():
                    df.loc[mask, 'alert_sent'] = True
                    self._write_events_df(df)
            finally:
                self._release_write_lock(lock_handle)
        except Exception as e:
            logger.error(f"Failed to mark alert as sent: {e}")
    
    def get_recent_events(self, hours: int = 24, severity_filter: Optional[List[str]] = None) -> pd.DataFrame:
        """Get recent governance events"""
        try:
            df = self._read_events_df()
            
            if df.empty:
                return df
            
            # Filter by time
            cutoff_time = datetime.now() - timedelta(hours=hours)
            df = df[pd.to_datetime(df['timestamp']) >= cutoff_time]
            
            # Filter by severity if specified
            if severity_filter:
                df = df[df['severity'].isin(severity_filter)]
            
            return df.sort_values('timestamp', ascending=False)
            
        except Exception as e:
            logger.error(f"Failed to get recent events: {e}")
            return pd.DataFrame()
    
    def get_unresolved_events(self) -> pd.DataFrame:
        """Get unresolved governance events"""
        try:
            df = self._read_events_df()
            
            if df.empty:
                return df
            
            # Filter unresolved events
            unresolved = df[df['resolved_at'].isna()]
            
            return unresolved.sort_values('timestamp', ascending=False)
            
        except Exception as e:
            logger.error(f"Failed to get unresolved events: {e}")
            return pd.DataFrame()
    
    def get_event_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get summary of governance events"""
        try:
            df = self.get_recent_events(hours)
            
            if df.empty:
                return {
                    'total_events': 0,
                    'by_severity': {},
                    'by_type': {},
                    'unresolved_count': 0,
                    'alerts_sent': 0
                }
            
            summary = {
                'total_events': len(df),
                'by_severity': df['severity'].value_counts().to_dict(),
                'by_type': df['event_type'].value_counts().to_dict(),
                'unresolved_count': df['resolved_at'].isna().sum(),
                'alerts_sent': df['alert_sent'].sum() if 'alert_sent' in df.columns else 0,
                'time_range_hours': hours
            }
            
            return summary
            
        except Exception as e:
            logger.error(f"Failed to get event summary: {e}")
            return {'error': str(e)}


class GovernanceEventTypes:
    """Standard governance event types"""
    
    # Mode transitions
    MODE_TRANSITION = "mode_transition"
    
    # Risk and integrity
    EQUITY_INTEGRITY_VIOLATION = "equity_integrity_violation"
    RISK_LIMIT_EXCEEDED = "risk_limit_exceeded"
    ACCOUNTING_MISMATCH = "accounting_mismatch"
    
    # System health
    HEARTBEAT_STALE = "heartbeat_stale"
    PROCESS_RESTART = "process_restart"
    MEMORY_PRESSURE = "memory_pressure"
    CPU_THROTTLE = "cpu_throttle"
    
    # Market and data
    CLOCK_DRIFT_EXCESSIVE = "clock_drift_excessive"
    DATA_FEED_FAILURE = "data_feed_failure"
    MARKET_ANOMALY = "market_anomaly"
    
    # Trading and positions
    POSITION_BREACH = "position_breach"
    DRAWDOWN_ALERT = "drawdown_alert"
    SURVIVAL_MODE_ACTIVATION = "survival_mode_activation"
    
    # Recovery and maintenance
    RECOVERY_MODE_ENTRY = "recovery_mode_entry"
    RECOVERY_MODE_EXIT = "recovery_mode_exit"
    STATE_CORRUPTION = "state_corruption"
    WAL_INTERRUPTION = "wal_interruption"
    
    # Operator actions
    MANUAL_OVERRIDE = "manual_override"
    EMERGENCY_STOP = "emergency_stop"
    PARAMETER_CHANGE = "parameter_change"


class GovernanceSeverity:
    """Standard severity levels"""
    
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


def create_governance_logger(config: Dict[str, Any]) -> GovernanceEventLogger:
    """Factory function to create governance logger"""
    log_path = Path(config.get('log_file', 'data/options/live/governance_events.parquet'))
    email_config = config.get('email_alerts', {})
    
    return GovernanceEventLogger(log_path, email_config)
