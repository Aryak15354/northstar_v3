"""
Performance Monitor - Real-time monitoring of system performance and health.
"""

import logging
import threading
import time
import queue
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from pathlib import Path
import json
import numpy as np
from dataclasses import asdict

from .base_types import (
    SystemHealthStatus, Alert, AlertLevel, HealthStatus,
    PerformanceMetrics, SystemHealthLevel
)


class AnomalyDetector:
    """Simple anomaly detector using statistical methods."""
    
    def __init__(self):
        self.sensitivity = 2.0
    
    def detect_anomalies(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Detect anomalies in performance data."""
        anomalies = []
        
        # Group data by metric
        metrics = {}
        for item in data:
            metric_name = item["metric_name"]
            if metric_name not in metrics:
                metrics[metric_name] = []
            metrics[metric_name].append(item)
        
        # Detect anomalies for each metric
        for metric_name, metric_data in metrics.items():
            values = [item["value"] for item in metric_data]
            
            if len(values) < 10:
                continue
            
            mean_val = np.mean(values)
            std_val = np.std(values)
            
            if std_val == 0:
                continue
            
            # Check for anomalies
            for item in metric_data:
                z_score = abs(item["value"] - mean_val) / std_val
                
                if z_score > self.sensitivity:
                    severity = "critical" if z_score > 3.0 else "high" if z_score > 2.5 else "medium"
                    
                    anomalies.append({
                        "timestamp": item["timestamp"],
                        "metric_name": metric_name,
                        "value": item["value"],
                        "expected_range": [mean_val - 2*std_val, mean_val + 2*std_val],
                        "severity": severity,
                        "deviation_score": z_score
                    })
        
        return anomalies


class PerformanceMonitor:
    """Real-time performance monitoring system."""
    
    PERFORMANCE_THRESHOLDS = {
        "max_latency_ms": 100.0,
        "min_data_quality": 0.95,
        "max_error_rate": 0.05,
        "max_memory_usage": 0.85,
        "max_cpu_usage": 0.80,
        "alert_cooldown_minutes": 5,
        "emergency_threshold_count": 3
    }
    
    MONITORING_INTERVALS = {
        "performance_check_seconds": 10,
        "health_check_seconds": 30,
    }
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """Initialize the performance monitor."""
        self.logger = logger or logging.getLogger(__name__)
        
        # Monitoring state
        self.is_monitoring = False
        self.start_time = None
        self.monitoring_threads = []
        
        # Data storage
        self.performance_data = queue.Queue(maxsize=10000)
        self.health_history = []
        self.alert_history = []
        self.metrics_cache = {}
        
        # Alert management
        self.active_alerts = {}
        self.alert_callbacks = []
        self.emergency_callbacks = []
        self.last_alert_times = {}
        
        # Performance tracking
        self.current_metrics = PerformanceMetrics()
        self.anomaly_detector = AnomalyDetector()
        
        # System health tracking
        self.current_health = SystemHealthStatus(
            timestamp=datetime.now(),
            overall_health=HealthStatus.HEALTHY
        )
        
        # Data persistence
        self.data_path = Path("data/monitoring")
        self.data_path.mkdir(parents=True, exist_ok=True)
        
        self.logger.info("Performance Monitor initialized")
    
    def start_monitoring(self) -> bool:
        """Start real-time performance monitoring."""
        if self.is_monitoring:
            return True
        
        try:
            self.is_monitoring = True
            self.start_time = datetime.now()
            self._start_monitoring_threads()
            return True
        except Exception as e:
            self.logger.error(f"Failed to start monitoring: {str(e)}")
            self.is_monitoring = False
            return False
    
    def stop_monitoring(self) -> bool:
        """Stop real-time performance monitoring."""
        if not self.is_monitoring:
            return True
        
        try:
            self.is_monitoring = False
            for thread in self.monitoring_threads:
                if thread.is_alive():
                    thread.join(timeout=5.0)
            return True
        except Exception as e:
            self.logger.error(f"Error stopping monitoring: {str(e)}")
            return False
    
    def track_performance_metric(self, metric_name: str, value: float, 
                                timestamp: Optional[datetime] = None) -> None:
        """Track a performance metric in real-time."""
        if not self.is_monitoring:
            return
        
        timestamp = timestamp or datetime.now()
        
        try:
            metric_data = {
                "timestamp": timestamp,
                "metric_name": metric_name,
                "value": value,
                "component": "performance_monitor"
            }
            
            try:
                self.performance_data.put_nowait(metric_data)
            except queue.Full:
                try:
                    self.performance_data.get_nowait()
                    self.performance_data.put_nowait(metric_data)
                except queue.Empty:
                    pass
            
            self._update_current_metrics(metric_name, value)
            self._check_performance_deviation(metric_name, value, timestamp)
            
        except Exception as e:
            self.logger.error(f"Error tracking metric {metric_name}: {str(e)}")
    
    def detect_performance_anomalies(self) -> List[Dict[str, Any]]:
        """Detect performance anomalies using statistical analysis."""
        if not self.is_monitoring:
            return []
        
        try:
            recent_data = self._get_recent_performance_data(minutes=30)
            if not recent_data:
                return []
            
            anomalies = self.anomaly_detector.detect_anomalies(recent_data)
            
            processed_anomalies = []
            for anomaly in anomalies:
                processed_anomaly = {
                    "timestamp": anomaly.get("timestamp", datetime.now()),
                    "metric_name": anomaly.get("metric_name", "unknown"),
                    "value": anomaly.get("value", 0),
                    "expected_range": anomaly.get("expected_range", [0, 0]),
                    "severity": anomaly.get("severity", "medium"),
                    "deviation_score": anomaly.get("deviation_score", 0)
                }
                processed_anomalies.append(processed_anomaly)
                
                if processed_anomaly["severity"] in ["high", "critical"]:
                    self._generate_anomaly_alert(processed_anomaly)
            
            return processed_anomalies
            
        except Exception as e:
            self.logger.error(f"Error detecting anomalies: {str(e)}")
            return []
    
    def validate_system_health(self) -> SystemHealthStatus:
        """Validate current system health status."""
        try:
            health_metrics = self._collect_health_metrics()
            overall_score = self._calculate_health_score(health_metrics)
            
            if overall_score >= 0.9:
                health_status = HealthStatus.HEALTHY
            elif overall_score >= 0.7:
                health_status = HealthStatus.WARNING
            else:
                health_status = HealthStatus.CRITICAL
            
            current_health = SystemHealthStatus(
                timestamp=datetime.now(),
                overall_health=health_status,
                component_status=health_metrics.get("components", {}),
                performance_score=health_metrics.get("performance_score", 0.0),
                data_quality_score=health_metrics.get("data_quality_score", 0.0),
                latency_metrics=health_metrics.get("latency_metrics", {}),
                error_counts=health_metrics.get("error_counts", {}),
                alert_level=self._determine_alert_level(health_status),
                recommended_actions=self._generate_health_recommendations(health_metrics)
            )
            
            self.current_health = current_health
            self.health_history.append(current_health)
            
            if len(self.health_history) > 1000:
                self.health_history = self.health_history[-1000:]
            
            self._check_health_degradation(current_health)
            return current_health
            
        except Exception as e:
            self.logger.error(f"Error validating health: {str(e)}")
            return SystemHealthStatus(
                timestamp=datetime.now(),
                overall_health=HealthStatus.CRITICAL
            )
    
    def trigger_alert(self, alert: Alert) -> bool:
        """Trigger a performance or health alert."""
        try:
            alert_key = f"{alert.component}_{alert.message}"
            last_alert_time = self.last_alert_times.get(alert_key)
            
            if last_alert_time:
                time_since_last = (datetime.now() - last_alert_time).total_seconds() / 60
                if time_since_last < self.PERFORMANCE_THRESHOLDS["alert_cooldown_minutes"]:
                    return False
            
            self.last_alert_times[alert_key] = datetime.now()
            self.active_alerts[alert_key] = alert
            self.alert_history.append(alert)
            
            if len(self.alert_history) > 1000:
                self.alert_history = self.alert_history[-1000:]
            
            for callback in self.alert_callbacks:
                try:
                    callback(alert)
                except Exception as e:
                    self.logger.error(f"Error executing alert callback: {str(e)}")
            
            self._check_emergency_conditions()
            self.logger.warning(f"Alert triggered: {alert.level.value} - {alert.message}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error triggering alert: {str(e)}")
            return False
    
    def execute_emergency_protocol(self, reason: str, details: Dict[str, Any]) -> bool:
        """Execute emergency protocols for critical system issues."""
        try:
            self.logger.critical(f"EXECUTING EMERGENCY PROTOCOL: {reason}")
            
            emergency_alert = Alert(
                timestamp=datetime.now(),
                level=AlertLevel.EMERGENCY,
                component="PerformanceMonitor",
                message=f"Emergency protocol executed: {reason}",
                details=details
            )
            
            self.trigger_alert(emergency_alert)
            
            for callback in self.emergency_callbacks:
                try:
                    callback(reason, details)
                except Exception as e:
                    self.logger.error(f"Error executing emergency callback: {str(e)}")
            
            # Emergency actions
            self._emergency_save_critical_data(reason, details)
            
            self.logger.critical("Emergency protocol execution completed")
            return True
            
        except Exception as e:
            self.logger.critical(f"CRITICAL ERROR in emergency protocol: {str(e)}")
            return False
    
    def get_performance_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get performance summary for the specified time period."""
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            recent_data = self._get_recent_performance_data(hours=hours)
            
            if not recent_data:
                return {"error": "No performance data available"}
            
            summary = {
                "period": {
                    "start_time": cutoff_time.isoformat(),
                    "end_time": datetime.now().isoformat(),
                    "duration_hours": hours
                },
                "metrics": self._calculate_performance_summary(recent_data),
                "health": {
                    "current_status": self.current_health.overall_health.value,
                    "average_score": np.mean([h.performance_score for h in self.health_history[-100:]]) if self.health_history else 0,
                    "health_trend": self._calculate_health_trend()
                },
                "alerts": {
                    "total_alerts": len([a for a in self.alert_history if a.timestamp >= cutoff_time]),
                    "critical_alerts": len([a for a in self.alert_history if a.timestamp >= cutoff_time and a.level == AlertLevel.CRITICAL]),
                    "active_alerts": len(self.active_alerts)
                },
                "anomalies": len(self.detect_performance_anomalies()),
                "uptime_hours": (datetime.now() - self.start_time).total_seconds() / 3600 if self.start_time else 0
            }
            
            return summary
            
        except Exception as e:
            self.logger.error(f"Error generating summary: {str(e)}")
            return {"error": str(e)}
    
    def add_alert_callback(self, callback: Callable[[Alert], None]) -> None:
        """Add callback function for alert notifications."""
        self.alert_callbacks.append(callback)
    
    def add_emergency_callback(self, callback: Callable[[str, Dict[str, Any]], None]) -> None:
        """Add callback function for emergency notifications."""
        self.emergency_callbacks.append(callback)
    
    def get_current_health(self) -> SystemHealthStatus:
        """Get current system health status."""
        return self.current_health
    
    def get_recent_alerts(self, hours: int = 24) -> List[Alert]:
        """Get recent alerts within the specified time period."""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        return [alert for alert in self.alert_history if alert.timestamp >= cutoff_time]
    
    def clear_resolved_alerts(self) -> int:
        """Clear resolved alerts from active alerts."""
        resolved_count = 0
        resolved_keys = []
        
        for key, alert in self.active_alerts.items():
            if alert.resolved:
                resolved_keys.append(key)
                resolved_count += 1
        
        for key in resolved_keys:
            del self.active_alerts[key]
        
        return resolved_count
    
    # Private helper methods
    
    def _start_monitoring_threads(self):
        """Start background monitoring threads."""
        perf_thread = threading.Thread(
            target=self._performance_monitoring_loop,
            name="PerformanceMonitor",
            daemon=True
        )
        perf_thread.start()
        self.monitoring_threads.append(perf_thread)
    
    def _performance_monitoring_loop(self):
        """Main performance monitoring loop."""
        while self.is_monitoring:
            try:
                self._collect_performance_metrics()
                time.sleep(self.MONITORING_INTERVALS["performance_check_seconds"])
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {str(e)}")
                time.sleep(5)
    
    def _collect_performance_metrics(self):
        """Collect current performance metrics."""
        import random
        
        # Simulate realistic metrics
        latency = random.uniform(20, 80)
        self.track_performance_metric("system_latency_ms", latency)
        
        data_quality = random.uniform(0.92, 0.99)
        self.track_performance_metric("data_quality_score", data_quality)
        
        error_rate = random.uniform(0.001, 0.02)
        self.track_performance_metric("error_rate", error_rate)
    
    def _collect_health_metrics(self) -> Dict[str, Any]:
        """Collect system health metrics."""
        import random
        
        return {
            "components": {
                "data_pipeline": "healthy" if random.random() > 0.1 else "warning",
                "intelligence_engines": "healthy" if random.random() > 0.05 else "warning",
                "risk_management": "healthy" if random.random() > 0.02 else "warning",
            },
            "performance_score": random.uniform(0.75, 0.95),
            "data_quality_score": random.uniform(0.90, 0.99),
            "latency_metrics": {
                "avg_latency_ms": random.uniform(30, 70),
            },
            "error_counts": {
                "total_errors": random.randint(0, 5),
                "critical_errors": random.randint(0, 1),
            }
        }
    
    def _calculate_health_score(self, health_metrics: Dict[str, Any]) -> float:
        """Calculate overall health score from metrics."""
        component_scores = []
        for component, status in health_metrics.get("components", {}).items():
            if status == "healthy":
                component_scores.append(1.0)
            elif status == "warning":
                component_scores.append(0.7)
            else:
                component_scores.append(0.3)
        
        component_score = np.mean(component_scores) if component_scores else 0.5
        performance_score = health_metrics.get("performance_score", 0.5)
        data_quality_score = health_metrics.get("data_quality_score", 0.5)
        
        overall_score = (
            0.4 * component_score +
            0.3 * performance_score +
            0.3 * data_quality_score
        )
        
        return max(0.0, min(1.0, overall_score))
    
    def _determine_alert_level(self, health_status: HealthStatus) -> AlertLevel:
        """Determine alert level based on health status."""
        if health_status == HealthStatus.CRITICAL:
            return AlertLevel.CRITICAL
        elif health_status == HealthStatus.WARNING:
            return AlertLevel.WARNING
        else:
            return AlertLevel.INFO
    
    def _generate_health_recommendations(self, health_metrics: Dict[str, Any]) -> List[str]:
        """Generate health improvement recommendations."""
        recommendations = []
        
        components = health_metrics.get("components", {})
        unhealthy_components = [comp for comp, status in components.items() if status != "healthy"]
        
        if unhealthy_components:
            recommendations.append(f"Review and fix issues in: {', '.join(unhealthy_components)}")
        
        performance_score = health_metrics.get("performance_score", 1.0)
        if performance_score < 0.8:
            recommendations.append("Investigate performance degradation")
        
        return recommendations
    
    def _update_current_metrics(self, metric_name: str, value: float):
        """Update current performance metrics."""
        self.metrics_cache[metric_name] = {
            "value": value,
            "timestamp": datetime.now()
        }
    
    def _check_performance_deviation(self, metric_name: str, value: float, timestamp: datetime):
        """Check for performance deviations and trigger alerts."""
        threshold_checks = {
            "system_latency_ms": ("max_latency_ms", "greater"),
            "data_quality_score": ("min_data_quality", "less"),
            "error_rate": ("max_error_rate", "greater"),
            "memory_usage": ("max_memory_usage", "greater"),
            "cpu_usage": ("max_cpu_usage", "greater")
        }
        
        if metric_name in threshold_checks:
            threshold_key, comparison = threshold_checks[metric_name]
            threshold_value = self.PERFORMANCE_THRESHOLDS.get(threshold_key)
            
            if threshold_value is not None:
                deviation_detected = False
                
                if comparison == "greater" and value > threshold_value:
                    deviation_detected = True
                elif comparison == "less" and value < threshold_value:
                    deviation_detected = True
                
                if deviation_detected:
                    alert = Alert(
                        timestamp=timestamp,
                        level=AlertLevel.WARNING,
                        component="PerformanceMonitor",
                        message=f"Performance deviation detected: {metric_name}",
                        details={
                            "metric_name": metric_name,
                            "current_value": value,
                            "threshold_value": threshold_value,
                            "deviation_type": comparison
                        }
                    )
                    self.trigger_alert(alert)
    
    def _check_health_degradation(self, current_health: SystemHealthStatus):
        """Check for health degradation and initiate diagnostics."""
        if current_health.overall_health == HealthStatus.CRITICAL:
            alert = Alert(
                timestamp=current_health.timestamp,
                level=AlertLevel.CRITICAL,
                component="HealthMonitor",
                message="System health is critical",
                details={
                    "health_score": current_health.performance_score,
                    "component_status": current_health.component_status,
                }
            )
            self.trigger_alert(alert)
    
    def _check_emergency_conditions(self):
        """Check if emergency conditions are met."""
        recent_critical_alerts = [
            alert for alert in self.alert_history
            if (alert.level == AlertLevel.CRITICAL and
                (datetime.now() - alert.timestamp).total_seconds() < 600)
        ]
        
        if len(recent_critical_alerts) >= self.PERFORMANCE_THRESHOLDS["emergency_threshold_count"]:
            self.execute_emergency_protocol(
                "Multiple critical alerts detected",
                {
                    "critical_alert_count": len(recent_critical_alerts),
                    "time_window_minutes": 10,
                    "recent_alerts": [alert.message for alert in recent_critical_alerts[-3:]]
                }
            )
    
    def _generate_anomaly_alert(self, anomaly: Dict[str, Any]):
        """Generate alert for detected anomaly."""
        severity_mapping = {
            "low": AlertLevel.INFO,
            "medium": AlertLevel.WARNING,
            "high": AlertLevel.WARNING,
            "critical": AlertLevel.CRITICAL
        }
        
        alert = Alert(
            timestamp=anomaly["timestamp"],
            level=severity_mapping.get(anomaly["severity"], AlertLevel.WARNING),
            component="AnomalyDetector",
            message=f"Performance anomaly detected in {anomaly['metric_name']}",
            details=anomaly
        )
        
        self.trigger_alert(alert)
    
    def _get_recent_performance_data(self, minutes: Optional[int] = None, 
                                   hours: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get recent performance data from queue."""
        if minutes:
            cutoff_time = datetime.now() - timedelta(minutes=minutes)
        elif hours:
            cutoff_time = datetime.now() - timedelta(hours=hours)
        else:
            cutoff_time = datetime.now() - timedelta(hours=1)
        
        data = []
        temp_queue = queue.Queue()
        
        while not self.performance_data.empty():
            try:
                item = self.performance_data.get_nowait()
                if item["timestamp"] >= cutoff_time:
                    data.append(item)
                temp_queue.put(item)
            except queue.Empty:
                break
        
        while not temp_queue.empty():
            try:
                self.performance_data.put_nowait(temp_queue.get_nowait())
            except (queue.Empty, queue.Full):
                break
        
        return data
    
    def _calculate_performance_summary(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate performance summary from data."""
        if not data:
            return {}
        
        metrics = {}
        for item in data:
            metric_name = item["metric_name"]
            if metric_name not in metrics:
                metrics[metric_name] = []
            metrics[metric_name].append(item["value"])
        
        summary = {}
        for metric_name, values in metrics.items():
            summary[metric_name] = {
                "count": len(values),
                "mean": np.mean(values),
                "std": np.std(values),
                "min": np.min(values),
                "max": np.max(values),
                "p50": np.percentile(values, 50),
                "p95": np.percentile(values, 95),
                "p99": np.percentile(values, 99)
            }
        
        return summary
    
    def _calculate_health_trend(self) -> str:
        """Calculate health trend from recent history."""
        if len(self.health_history) < 2:
            return "stable"
        
        recent_scores = [h.performance_score for h in self.health_history[-10:]]
        
        if len(recent_scores) < 2:
            return "stable"
        
        trend = np.polyfit(range(len(recent_scores)), recent_scores, 1)[0]
        
        if trend > 0.01:
            return "improving"
        elif trend < -0.01:
            return "degrading"
        else:
            return "stable"
    
    def _emergency_save_critical_data(self, reason: str, details: Dict[str, Any]):
        """Emergency action: Save critical data."""
        self.logger.critical("Emergency action: Saving critical data")
        try:
            if self.alert_history:
                alert_path = self.data_path / f"emergency_alerts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                alert_data = [asdict(a) for a in self.alert_history[-100:]]
                with open(alert_path, 'w') as f:
                    json.dump(alert_data, f, indent=2, default=str)
        except Exception as e:
            self.logger.error(f"Error saving emergency data: {str(e)}")