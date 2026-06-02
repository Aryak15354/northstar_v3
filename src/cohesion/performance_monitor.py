"""
Performance monitoring and alerting for cohesion-layer validation tests.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, List, Optional


class AlertSeverity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class PerformanceMetric:
    name: str
    value: float
    timestamp: datetime
    unit: str = ""
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class Alert:
    metric_name: str
    severity: AlertSeverity
    message: str
    value: float
    threshold: float
    timestamp: datetime
    resolved: bool = False


@dataclass
class PerformanceThreshold:
    metric_name: str
    warning_threshold: float
    critical_threshold: float
    comparison: str = "greater"
    window_size: int = 5

    def evaluate(self, values: List[float]) -> Optional[AlertSeverity]:
        if len(values) < self.window_size:
            return None
        recent = values[-self.window_size :]
        avg_value = sum(recent) / len(recent)
        if self.comparison == "greater":
            if avg_value >= self.critical_threshold:
                return AlertSeverity.CRITICAL
            if avg_value >= self.warning_threshold:
                return AlertSeverity.HIGH
        elif self.comparison == "less":
            if avg_value <= self.critical_threshold:
                return AlertSeverity.CRITICAL
            if avg_value <= self.warning_threshold:
                return AlertSeverity.HIGH
        return None


class PerformanceMonitor:
    """Minimal-but-functional metric store with threshold alerting."""

    def __init__(self, history_size: int = 1000, monitoring_interval: float = 10.0):
        self.history_size = history_size
        self.monitoring_interval = monitoring_interval
        self._metrics: Dict[str, deque[PerformanceMetric]] = defaultdict(lambda: deque(maxlen=history_size))
        self._thresholds: Dict[str, PerformanceThreshold] = {}
        self._alerts: List[Alert] = []
        self._lock = threading.RLock()
        self._monitoring_active = False

    def record_metric(self, name: str, value: float, unit: str = "", tags: Optional[Dict[str, str]] = None):
        with self._lock:
            self._metrics[name].append(
                PerformanceMetric(name=name, value=float(value), timestamp=datetime.now(), unit=unit, tags=tags or {})
            )
            if name in self._thresholds:
                self._check_threshold(name)

    def get_metrics(self, name: str, since: Optional[datetime] = None) -> List[PerformanceMetric]:
        with self._lock:
            metrics = list(self._metrics[name])
        if since is None:
            return metrics
        return [metric for metric in metrics if metric.timestamp >= since]

    def add_threshold(self, threshold: PerformanceThreshold):
        with self._lock:
            self._thresholds[threshold.metric_name] = threshold

    def get_active_alerts(self) -> List[Alert]:
        with self._lock:
            return [alert for alert in self._alerts if not alert.resolved]

    def start_monitoring(self):
        self._monitoring_active = True

    def stop_monitoring(self):
        self._monitoring_active = False

    def _check_threshold(self, metric_name: str) -> None:
        threshold = self._thresholds[metric_name]
        values = [metric.value for metric in self._metrics[metric_name]]
        severity = threshold.evaluate(values)
        if severity is None:
            return
        recent = values[-threshold.window_size :]
        avg_value = sum(recent) / len(recent)
        self._alerts.append(
            Alert(
                metric_name=metric_name,
                severity=severity,
                message=f"Threshold breach for {metric_name}",
                value=float(avg_value),
                threshold=float(
                    threshold.critical_threshold if severity == AlertSeverity.CRITICAL else threshold.warning_threshold
                ),
                timestamp=datetime.now(),
            )
        )


def cached(func: Callable[..., Any]) -> Callable[..., Any]:
    cache: Dict[tuple[Any, ...], Any] = {}

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        key = args + tuple(sorted(kwargs.items()))
        if key not in cache:
            cache[key] = func(*args, **kwargs)
        return cache[key]

    return wrapper


class PerformanceProfiler:
    """Very small profiler helper used by old cohesion callers."""

    def __init__(self, name: str = "profile"):
        self.name = name
        self.started_at: Optional[float] = None
        self.elapsed_seconds: Optional[float] = None

    def __enter__(self) -> "PerformanceProfiler":
        self.started_at = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.started_at is not None:
            self.elapsed_seconds = time.perf_counter() - self.started_at
