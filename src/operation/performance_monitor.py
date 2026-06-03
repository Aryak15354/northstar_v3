"""
Operation-layer performance monitor.

Restores the active contract used by the operation controller and the
Task 6 property tests.
"""

from __future__ import annotations

import logging
import threading
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import json

from .base_types import Alert, AlertLevel, HealthStatus, PerformanceMetrics, SystemHealthStatus


class PerformanceMonitor:
    """Real-time operation monitoring with alerting and emergency callbacks."""

    _DEVIATION_RULES: Dict[str, tuple[float, str]] = {
        "system_latency_ms": (100.0, "greater"),
        "data_quality_score": (0.95, "less"),
        "error_rate": (0.05, "greater"),
        "memory_usage": (0.80, "greater"),
        "cpu_usage": (0.80, "greater"),
    }

    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        self.is_monitoring = False
        self.start_time: Optional[datetime] = None
        self.alert_history: List[Alert] = []
        self.metrics_cache: Dict[str, Dict[str, Any]] = {}
        self.active_alerts: Dict[str, Alert] = {}
        self.emergency_callbacks: List[Callable[[str, Dict[str, Any]], None]] = []
        self.last_alert_times: Dict[str, datetime] = {}
        self.data_path = Path("data/monitoring")
        self.data_path.mkdir(parents=True, exist_ok=True)
        self.current_metrics = PerformanceMetrics()
        self.current_health = SystemHealthStatus(
            timestamp=datetime.now(),
            overall_health=HealthStatus.HEALTHY,
        )
        self._critical_alert_times: deque[datetime] = deque(maxlen=20)
        self._lock = threading.RLock()

    def start_monitoring(self) -> bool:
        with self._lock:
            self.is_monitoring = True
            self.start_time = datetime.now()
        return True

    def stop_monitoring(self) -> bool:
        with self._lock:
            self.is_monitoring = False
        return True

    def add_emergency_callback(self, callback: Callable[[str, Dict[str, Any]], None]) -> None:
        self.emergency_callbacks.append(callback)

    def track_performance_metric(
        self,
        metric_name: str,
        value: float,
        timestamp: Optional[datetime] = None,
    ) -> None:
        if not self.is_monitoring:
            return

        ts = timestamp or datetime.now()
        with self._lock:
            self.metrics_cache[metric_name] = {"value": value, "timestamp": ts}
            self._update_current_metrics(metric_name, value)
        self._check_performance_deviation(metric_name, value, ts)

    def trigger_alert(self, alert: Alert) -> bool:
        with self._lock:
            self.alert_history.append(alert)
            key = f"{alert.component}:{alert.message}"
            self.active_alerts[key] = alert
            if alert.level == AlertLevel.CRITICAL:
                self._critical_alert_times.append(alert.timestamp)
                recent = [ts for ts in self._critical_alert_times if (alert.timestamp - ts).total_seconds() <= 300]
                self._critical_alert_times = deque(recent, maxlen=20)
                if len(recent) >= 3:
                    self.execute_emergency_protocol(
                        "Multiple critical alerts detected",
                        {"critical_alert_count": len(recent), "latest_alert": alert.message},
                    )
        return True

    def execute_emergency_protocol(self, reason: str, details: Dict[str, Any]) -> bool:
        alert = Alert(
            timestamp=datetime.now(),
            level=AlertLevel.EMERGENCY,
            component="PerformanceMonitor",
            message=f"Emergency protocol executed: {reason}",
            details=dict(details),
        )
        with self._lock:
            self.alert_history.append(alert)
            self._persist_snapshot(reason, details)
        for callback in list(self.emergency_callbacks):
            callback(reason, details)
        return True

    def validate_system_health(self) -> SystemHealthStatus:
        with self._lock:
            unhealthy = any(alert.level in {AlertLevel.CRITICAL, AlertLevel.EMERGENCY} for alert in self.alert_history[-10:])
            self.current_health = SystemHealthStatus(
                timestamp=datetime.now(),
                overall_health=HealthStatus.CRITICAL if unhealthy else HealthStatus.HEALTHY,
                latency_metrics={
                    key: float(value["value"])
                    for key, value in self.metrics_cache.items()
                    if "latency" in key
                },
            )
            return self.current_health

    def get_current_metrics(self) -> PerformanceMetrics:
        return self.current_metrics

    def detect_performance_anomalies(self) -> List[Dict[str, Any]]:
        return []

    def _persist_snapshot(self, reason: str, details: Dict[str, Any]) -> None:
        payload = {
            "timestamp": datetime.now().isoformat(),
            "reason": reason,
            "details": details,
            "metrics_cache": {
                key: {
                    "value": value.get("value"),
                    "timestamp": value.get("timestamp").isoformat()
                    if isinstance(value.get("timestamp"), datetime)
                    else str(value.get("timestamp")),
                }
                for key, value in self.metrics_cache.items()
            },
        }
        path = self.data_path / f"emergency_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.json"
        path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    def _update_current_metrics(self, metric_name: str, value: float) -> None:
        if metric_name == "system_latency_ms":
            self.current_metrics.avg_turnover = float(value)
        elif metric_name == "data_quality_score":
            self.current_health.data_quality_score = float(value)
        elif metric_name == "error_rate":
            self.current_health.error_counts["error_rate"] = int(round(float(value) * 100))

    def _check_performance_deviation(self, metric_name: str, value: float, timestamp: datetime) -> None:
        rule = self._DEVIATION_RULES.get(metric_name)
        if not rule:
            return

        threshold, comparison = rule
        breached = value > threshold if comparison == "greater" else value < threshold
        if not breached:
            return

        last_alert = self.last_alert_times.get(metric_name)
        if last_alert and (timestamp - last_alert) < timedelta(minutes=5):
            return

        severe_breach = value > threshold * 1.5 if comparison == "greater" else value < threshold * 0.9
        level = AlertLevel.CRITICAL if severe_breach else AlertLevel.WARNING
        alert = Alert(
            timestamp=timestamp,
            level=level,
            component="PerformanceMonitor",
            message=f"Performance deviation detected for {metric_name}: {value}",
            details={"threshold": threshold, "comparison": comparison},
        )
        self.last_alert_times[metric_name] = timestamp
        self.trigger_alert(alert)
