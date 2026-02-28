"""
Performance Monitoring and Alerting System

This module provides comprehensive performance monitoring with alerting
for the Northstar V3 system.

Implements Requirement 9.6: Performance monitoring and alerting
"""

import logging
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple
import psutil
import pandas as pd
from enum import Enum

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class PerformanceMetric:
    """Performance metric with metadata"""
    name: str
    value: float
    timestamp: datetime
    unit: str = ""
    tags: Dict[str, str] = field(default_factory=dict)
    
    def __str__(self):
        return f"{self.name}: {self.value}{self.unit} at {self.timestamp}"


@dataclass
class Alert:
    """Performance alert"""
    metric_name: str
    severity: AlertSeverity
    message: str
    value: float
    threshold: float
    timestamp: datetime
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    
    def resolve(self):
        """Mark alert as resolved"""
        self.resolved = True
        self.resolved_at = datetime.now()


@dataclass
class PerformanceThreshold:
    """Performance threshold configuration"""
    metric_name: str
    warning_threshold: float
    critical_threshold: float
    comparison: str = "greater"  # "greater", "less", "equal"
    window_size: int = 5  # Number of samples to consider
    
    def check_threshold(self, values: List[float]) -> Optional[AlertSeverity]:
        """Check if values breach threshold"""
        if len(values) < self.window_size:
            return None
        
        # Use average of recent values
        avg_value = sum(values[-self.window_size:]) / self.window_size
        
        if self.comparison == "greater":
            if avg_value >= self.critical_threshold:
                return AlertSeverity.CRITICAL
            elif avg_value >= self.warning_threshold:
                return AlertSeverity.HIGH
        elif self.comparison == "less":
            if avg_value <= self.critical_threshold:
                return AlertSeverity.CRITICAL
            elif avg_value <= self.warning_threshold:
                return AlertSeverity.HIGH
        
        return None


class PerformanceMonitor:
    """
    Comprehensive performance monitoring system
    
    Implements Requirement 9.6: Performance monitoring and alerting
    """
    
    def __init__(self, 
                 history_size: int = 1000,
                 monitoring_interval: float = 10.0):
        self.history_size = history_size
        self.monitoring_interval = monitoring_interval
        
        # Metric storage
        self._metrics: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=history_size)
        )
        self._lock = threading.RLock()
        
        # Alerting
        self._thresholds: Dict[str, PerformanceThreshold] = {}
        self._alerts: List[Alert] = []
        self._alert_callbacks: List[Callable[[Alert], None]] = []
        
        # Monitoring state
        self._monitoring_active = False
        self._custom_collectors: Dict[str, Callable[[], Dict[str, float]]] = {}
        
        # Default thresholds
        self._setup_default_thresholds()
        
        logger.info("Initialized PerformanceMonitor")
    
    def record_metric(self, name: str, value: float, 
                     unit: str = "", tags: Dict[str, str] = None):
        """Record a performance metric"""
        with self._lock:
            metric = PerformanceMetric(
                name=name,
                value=value,
                timestamp=datetime.now(),
                unit=unit,
                tags=tags or {}
            )
            
            self._metrics[name].append(metric)
            
            # Check thresholds
            if name in self._thresholds:
                self._check_threshold(name)
    
    def get_metrics(self, name: str, 
                   since: datetime = None) -> List[PerformanceMetric]:
        """Get metrics for a specific name"""
        with self._lock:
            metrics = list(self._metrics[name])
            
            if since:
                metrics = [m for m in metrics if m.timestamp >= since]
            
            return metrics
    
    def get_metric_summary(self, name: str, 
                          window: timedelta = None) -> Dict[str, float]:
        """Get summary statistics for a metric"""
        window = window or timedelta(minutes=30)
        since = datetime.now() - window
        
        metrics = self.get_metrics(name, since)
        if not metrics:
            return {}
        
        values = [m.value for m in metrics]
        
        return {
            "count": len(values),
            "min": min(values),
            "max": max(values),
            "mean": sum(values) / len(values),
            "latest": values[-1] if values else 0,
            "trend": self._calculate_trend(values)
        }
    
    def add_threshold(self, threshold: PerformanceThreshold):
        """Add performance threshold"""
        with self._lock:
            self._thresholds[threshold.metric_name] = threshold
            logger.info(f"Added threshold for {threshold.metric_name}")
    
    def add_alert_callback(self, callback: Callable[[Alert], None]):
        """Add alert callback function"""
        self._alert_callbacks.append(callback)
    
    def get_active_alerts(self) -> List[Alert]:
        """Get all active (unresolved) alerts"""
        return [alert for alert in self._alerts if not alert.resolved]
    
    def get_all_alerts(self, since: datetime = None) -> List[Alert]:
        """Get all alerts since specified time"""
        alerts = self._alerts
        if since:
            alerts = [a for a in alerts if a.timestamp >= since]
        return alerts
    
    def resolve_alert(self, alert_id: int):
        """Resolve an alert by index"""
        if 0 <= alert_id < len(self._alerts):
            self._alerts[alert_id].resolve()
            logger.info(f"Resolved alert: {self._alerts[alert_id].message}")
    
    def start_monitoring(self):
        """Start background performance monitoring"""
        if self._monitoring_active:
            return
        
        self._monitoring_active = True
        
        def monitor_loop():
            while self._monitoring_active:
                try:
                    self._collect_system_metrics()
                    self._collect_custom_metrics()
                    time.sleep(self.monitoring_interval)
                except Exception as e:
                    logger.error(f"Monitoring error: {e}")
                    time.sleep(self.monitoring_interval * 2)  # Back off on error
        
        monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        monitor_thread.start()
        
        logger.info("Started performance monitoring")
    
    def stop_monitoring(self):
        """Stop background monitoring"""
        self._monitoring_active = False
        logger.info("Stopped performance monitoring")
    
    def add_custom_collector(self, name: str, 
                           collector: Callable[[], Dict[str, float]]):
        """Add custom metric collector"""
        self._custom_collectors[name] = collector
        logger.info(f"Added custom collector: {name}")
    
    def _setup_default_thresholds(self):
        """Setup default performance thresholds"""
        thresholds = [
            PerformanceThreshold(
                metric_name="cpu_percent",
                warning_threshold=70.0,
                critical_threshold=90.0,
                comparison="greater"
            ),
            PerformanceThreshold(
                metric_name="memory_percent",
                warning_threshold=80.0,
                critical_threshold=95.0,
                comparison="greater"
            ),
            PerformanceThreshold(
                metric_name="disk_usage_percent",
                warning_threshold=85.0,
                critical_threshold=95.0,
                comparison="greater"
            ),
            PerformanceThreshold(
                metric_name="cache_hit_rate",
                warning_threshold=0.7,
                critical_threshold=0.5,
                comparison="less"
            ),
            PerformanceThreshold(
                metric_name="response_time_ms",
                warning_threshold=1000.0,
                critical_threshold=5000.0,
                comparison="greater"
            )
        ]
        
        for threshold in thresholds:
            self._thresholds[threshold.metric_name] = threshold
    
    def _collect_system_metrics(self):
        """Collect system performance metrics"""
        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            self.record_metric("cpu_percent", cpu_percent, "%")
            
            # Memory metrics
            memory = psutil.virtual_memory()
            self.record_metric("memory_percent", memory.percent, "%")
            self.record_metric("memory_used_gb", memory.used / (1024**3), "GB")
            self.record_metric("memory_available_gb", memory.available / (1024**3), "GB")
            
            # Disk metrics
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            self.record_metric("disk_usage_percent", disk_percent, "%")
            self.record_metric("disk_free_gb", disk.free / (1024**3), "GB")
            
            # Network metrics (if available)
            try:
                net_io = psutil.net_io_counters()
                self.record_metric("network_bytes_sent", net_io.bytes_sent, "bytes")
                self.record_metric("network_bytes_recv", net_io.bytes_recv, "bytes")
            except:
                pass  # Network stats not available on all systems
            
        except Exception as e:
            logger.error(f"System metrics collection error: {e}")
    
    def _collect_custom_metrics(self):
        """Collect custom metrics from registered collectors"""
        for name, collector in self._custom_collectors.items():
            try:
                metrics = collector()
                for metric_name, value in metrics.items():
                    self.record_metric(f"{name}_{metric_name}", value)
            except Exception as e:
                logger.error(f"Custom collector {name} error: {e}")
    
    def _check_threshold(self, metric_name: str):
        """Check if metric breaches threshold"""
        threshold = self._thresholds[metric_name]
        metrics = list(self._metrics[metric_name])
        
        if len(metrics) < threshold.window_size:
            return
        
        values = [m.value for m in metrics[-threshold.window_size:]]
        severity = threshold.check_threshold(values)
        
        if severity:
            # Check if we already have an active alert for this metric
            active_alerts = [a for a in self._alerts 
                           if a.metric_name == metric_name and not a.resolved]
            
            if not active_alerts or active_alerts[-1].severity != severity:
                # Create new alert
                avg_value = sum(values) / len(values)
                alert = Alert(
                    metric_name=metric_name,
                    severity=severity,
                    message=f"{metric_name} {severity.value}: {avg_value:.2f} "
                           f"(threshold: {threshold.warning_threshold if severity == AlertSeverity.HIGH else threshold.critical_threshold})",
                    value=avg_value,
                    threshold=threshold.warning_threshold if severity == AlertSeverity.HIGH else threshold.critical_threshold,
                    timestamp=datetime.now()
                )
                
                self._alerts.append(alert)
                
                # Notify callbacks
                for callback in self._alert_callbacks:
                    try:
                        callback(alert)
                    except Exception as e:
                        logger.error(f"Alert callback error: {e}")
                
                logger.warning(f"Performance alert: {alert.message}")
    
    def _calculate_trend(self, values: List[float]) -> str:
        """Calculate trend direction for values"""
        if len(values) < 2:
            return "stable"
        
        # Simple trend calculation using first and last values
        first_half = values[:len(values)//2]
        second_half = values[len(values)//2:]
        
        first_avg = sum(first_half) / len(first_half)
        second_avg = sum(second_half) / len(second_half)
        
        change_percent = ((second_avg - first_avg) / first_avg) * 100
        
        if change_percent > 10:
            return "increasing"
        elif change_percent < -10:
            return "decreasing"
        else:
            return "stable"
    
    def export_metrics(self, format: str = "csv") -> str:
        """Export metrics to file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if format == "csv":
            filename = f"performance_metrics_{timestamp}.csv"
            
            # Collect all metrics
            all_metrics = []
            with self._lock:
                for metric_name, metrics in self._metrics.items():
                    for metric in metrics:
                        all_metrics.append({
                            'metric_name': metric.name,
                            'value': metric.value,
                            'timestamp': metric.timestamp,
                            'unit': metric.unit,
                            'tags': str(metric.tags)
                        })
            
            # Create DataFrame and save
            df = pd.DataFrame(all_metrics)
            df.to_csv(filename, index=False)
            
            logger.info(f"Exported metrics to {filename}")
            return filename
        
        else:
            raise ValueError(f"Unsupported export format: {format}")


class PerformanceProfiler:
    """
    Code performance profiler for identifying bottlenecks
    """
    
    def __init__(self, monitor: PerformanceMonitor):
        self.monitor = monitor
        self._active_profiles: Dict[str, datetime] = {}
    
    def start_profile(self, name: str):
        """Start profiling a code section"""
        self._active_profiles[name] = datetime.now()
    
    def end_profile(self, name: str):
        """End profiling and record duration"""
        if name not in self._active_profiles:
            logger.warning(f"No active profile found for: {name}")
            return
        
        start_time = self._active_profiles.pop(name)
        duration = (datetime.now() - start_time).total_seconds() * 1000  # ms
        
        self.monitor.record_metric(f"profile_{name}_duration", duration, "ms")
    
    def profile(self, name: str):
        """Context manager for profiling"""
        return ProfileContext(self, name)


class ProfileContext:
    """Context manager for performance profiling"""
    
    def __init__(self, profiler: PerformanceProfiler, name: str):
        self.profiler = profiler
        self.name = name
    
    def __enter__(self):
        self.profiler.start_profile(self.name)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.profiler.end_profile(self.name)


def profile_function(monitor: PerformanceMonitor, name: str = None):
    """Decorator for profiling function execution time"""
    def decorator(func):
        profile_name = name or f"function_{func.__name__}"
        
        def wrapper(*args, **kwargs):
            start_time = datetime.now()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration = (datetime.now() - start_time).total_seconds() * 1000
                monitor.record_metric(f"profile_{profile_name}_duration", duration, "ms")
        
        return wrapper
    return decorator


# Global performance monitor instance
_global_performance_monitor = None

def get_global_performance_monitor() -> PerformanceMonitor:
    """Get global performance monitor instance"""
    global _global_performance_monitor
    if _global_performance_monitor is None:
        _global_performance_monitor = PerformanceMonitor()
        _global_performance_monitor.start_monitoring()
    return _global_performance_monitor