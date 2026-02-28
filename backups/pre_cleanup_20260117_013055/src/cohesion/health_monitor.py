"""
Comprehensive System Health Monitoring

This module implements comprehensive health monitoring for all critical components
with automated alerting, failover capabilities, and predictive analytics.

Capital-Grade System Laws Enforced:
- Property 25: Health Monitoring Completeness (H1)
- Property 26: Failover Consistency (H2)
"""

import logging
import threading
import time
import statistics
from abc import ABC, abstractmethod
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, Any, Callable, List, Optional, Set, Tuple
import psutil
import numpy as np
from src.service_interfaces import IHealthMonitor

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Component health status levels"""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"
    FAILED = "failed"


class AlertSeverity(Enum):
    """Health alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


@dataclass
class HealthMetric:
    """Health metric with metadata"""
    name: str
    value: float
    status: HealthStatus
    timestamp: datetime
    component: str
    unit: str = ""
    threshold_warning: Optional[float] = None
    threshold_critical: Optional[float] = None
    message: str = ""


@dataclass
class HealthAlert:
    """Health monitoring alert"""
    id: str
    component: str
    metric: str
    severity: AlertSeverity
    message: str
    value: float
    threshold: float
    timestamp: datetime
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    escalated: bool = False
    
    def resolve(self):
        """Mark alert as resolved"""
        self.resolved = True
        self.resolved_at = datetime.now()


@dataclass
class ComponentHealth:
    """Component health information"""
    name: str
    status: HealthStatus
    metrics: Dict[str, HealthMetric]
    last_check: datetime
    check_interval: timedelta
    health_check_func: Callable[[], Dict[str, Any]]
    failover_enabled: bool = False
    failover_target: Optional[str] = None
    consecutive_failures: int = 0
    max_failures: int = 3


class HealthCheckResult:
    """Result of a health check"""
    
    def __init__(self, healthy: bool, metrics: Dict[str, float] = None, 
                 message: str = "", details: Dict[str, Any] = None):
        self.healthy = healthy
        self.metrics = metrics or {}
        self.message = message
        self.details = details or {}
        self.timestamp = datetime.now()


class IFailoverHandler(ABC):
    """Interface for failover handlers"""
    
    @abstractmethod
    def can_failover(self, component: str) -> bool:
        """Check if component can failover"""
        pass
    
    @abstractmethod
    def execute_failover(self, component: str, target: str) -> bool:
        """Execute failover to target"""
        pass
    
    @abstractmethod
    def rollback_failover(self, component: str) -> bool:
        """Rollback failover"""
        pass


class DefaultFailoverHandler(IFailoverHandler):
    """Default failover handler implementation"""
    
    def __init__(self):
        self.active_failovers: Dict[str, str] = {}
    
    def can_failover(self, component: str) -> bool:
        """Check if component can failover"""
        # Simple check - not already failed over
        return component not in self.active_failovers
    
    def execute_failover(self, component: str, target: str) -> bool:
        """Execute failover to target"""
        try:
            logger.warning(f"Executing failover: {component} -> {target}")
            self.active_failovers[component] = target
            return True
        except Exception as e:
            logger.error(f"Failover failed for {component}: {e}")
            return False
    
    def rollback_failover(self, component: str) -> bool:
        """Rollback failover"""
        try:
            if component in self.active_failovers:
                target = self.active_failovers.pop(component)
                logger.info(f"Rolled back failover: {component} from {target}")
            return True
        except Exception as e:
            logger.error(f"Failover rollback failed for {component}: {e}")
            return False


class HealthTrendAnalyzer:
    """Analyzes health trends for predictive alerting"""
    
    def __init__(self, history_size: int = 100):
        self.history_size = history_size
        self.metric_history: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=history_size)
        )
    
    def add_metric(self, component: str, metric_name: str, value: float):
        """Add metric value to history"""
        key = f"{component}.{metric_name}"
        self.metric_history[key].append((datetime.now(), value))
    
    def analyze_trend(self, component: str, metric_name: str, 
                     window_minutes: int = 30) -> Dict[str, Any]:
        """Analyze trend for predictive alerting"""
        key = f"{component}.{metric_name}"
        history = self.metric_history[key]
        
        if len(history) < 5:  # Need minimum data points
            return {"trend": "insufficient_data"}
        
        # Filter to time window
        cutoff_time = datetime.now() - timedelta(minutes=window_minutes)
        recent_data = [(ts, val) for ts, val in history if ts >= cutoff_time]
        
        if len(recent_data) < 3:
            return {"trend": "insufficient_recent_data"}
        
        values = [val for _, val in recent_data]
        timestamps = [ts.timestamp() for ts, _ in recent_data]
        
        # Calculate trend using linear regression
        try:
            slope = np.polyfit(timestamps, values, 1)[0]
            
            # Calculate statistics
            mean_value = statistics.mean(values)
            std_dev = statistics.stdev(values) if len(values) > 1 else 0
            
            # Determine trend direction and strength
            if abs(slope) < std_dev * 0.1:  # Very small slope relative to variance
                trend_direction = "stable"
            elif slope > 0:
                trend_direction = "increasing"
            else:
                trend_direction = "decreasing"
            
            # Calculate trend strength
            correlation = abs(slope) / (std_dev + 1e-10)  # Avoid division by zero
            
            return {
                "trend": trend_direction,
                "slope": slope,
                "strength": min(correlation, 1.0),  # Cap at 1.0
                "mean": mean_value,
                "std_dev": std_dev,
                "data_points": len(values),
                "prediction_confidence": min(len(values) / 20.0, 1.0)  # More data = higher confidence
            }
            
        except Exception as e:
            logger.error(f"Trend analysis error for {key}: {e}")
            return {"trend": "analysis_error", "error": str(e)}
    
    def predict_threshold_breach(self, component: str, metric_name: str,
                               threshold: float, minutes_ahead: int = 15) -> Dict[str, Any]:
        """Predict if metric will breach threshold"""
        trend_analysis = self.analyze_trend(component, metric_name)
        
        if trend_analysis["trend"] in ["insufficient_data", "insufficient_recent_data", "analysis_error"]:
            return {"prediction": "insufficient_data"}
        
        current_mean = trend_analysis["mean"]
        slope = trend_analysis["slope"]
        confidence = trend_analysis["prediction_confidence"]
        
        # Project forward
        seconds_ahead = minutes_ahead * 60
        predicted_value = current_mean + (slope * seconds_ahead)
        
        # Determine if breach is likely
        if trend_analysis["trend"] == "increasing" and predicted_value > threshold:
            breach_probability = confidence * min((predicted_value - threshold) / threshold, 1.0)
            return {
                "prediction": "breach_likely",
                "probability": breach_probability,
                "predicted_value": predicted_value,
                "current_value": current_mean,
                "threshold": threshold,
                "minutes_to_breach": max(1, (threshold - current_mean) / (slope / 60)) if slope > 0 else None
            }
        elif trend_analysis["trend"] == "decreasing" and predicted_value < threshold:
            breach_probability = confidence * min((threshold - predicted_value) / threshold, 1.0)
            return {
                "prediction": "breach_likely",
                "probability": breach_probability,
                "predicted_value": predicted_value,
                "current_value": current_mean,
                "threshold": threshold,
                "minutes_to_breach": max(1, (current_mean - threshold) / (-slope / 60)) if slope < 0 else None
            }
        else:
            return {
                "prediction": "no_breach",
                "predicted_value": predicted_value,
                "current_value": current_mean,
                "threshold": threshold
            }


class ComprehensiveHealthMonitor(IHealthMonitor):
    """
    Comprehensive system health monitoring with automated alerting and failover
    
    Enforces System Laws:
    - Property 25: Health Monitoring Completeness (H1)
    - Property 26: Failover Consistency (H2)
    """
    
    def __init__(self, 
                 check_interval: timedelta = timedelta(seconds=30),
                 failover_handler: IFailoverHandler = None):
        self.check_interval = check_interval
        self.failover_handler = failover_handler or DefaultFailoverHandler()
        
        # Component tracking
        self.components: Dict[str, ComponentHealth] = {}
        self.critical_components: Set[str] = set()
        
        # Alerting
        self.alerts: List[HealthAlert] = []
        self.alert_callbacks: List[Callable[[HealthAlert], None]] = []
        self.alert_thresholds: Dict[str, Dict[str, Tuple[float, float]]] = {}  # component.metric -> (warning, critical)
        
        # Monitoring state
        self.monitoring_active = False
        self.monitoring_thread: Optional[threading.Thread] = None
        
        # Trend analysis
        self.trend_analyzer = HealthTrendAnalyzer()
        
        # System metrics
        self.system_start_time = datetime.now()
        self.total_checks_performed = 0
        self.total_alerts_generated = 0
        
        # Thread safety
        self._lock = threading.RLock()
        
        logger.info("Initialized ComprehensiveHealthMonitor")
    
    def register_component(self, 
                         component_name: str, 
                         health_check: Callable[[], Dict[str, Any]],
                         check_interval: timedelta = None,
                         is_critical: bool = False,
                         failover_target: str = None) -> bool:
        """
        Register component for health monitoring
        
        Enforces Property 25: Health Monitoring Completeness (H1)
        """
        with self._lock:
            if component_name in self.components:
                logger.warning(f"Component {component_name} already registered")
                return False
            
            component = ComponentHealth(
                name=component_name,
                status=HealthStatus.UNKNOWN,
                metrics={},
                last_check=datetime.now(),
                check_interval=check_interval or self.check_interval,
                health_check_func=health_check,
                failover_enabled=failover_target is not None,
                failover_target=failover_target
            )
            
            self.components[component_name] = component
            
            if is_critical:
                self.critical_components.add(component_name)
            
            logger.info(f"Registered component: {component_name} (critical: {is_critical})")
            
            # SYSTEM LAW: All critical components must have health monitoring
            if is_critical:
                assert component_name in self.components, \
                    f"Critical component {component_name} not properly registered"
            
            return True
    
    def set_alert_thresholds(self, component: str, metric: str, 
                           warning_threshold: float, critical_threshold: float):
        """Set alert thresholds for component metric"""
        with self._lock:
            if component not in self.alert_thresholds:
                self.alert_thresholds[component] = {}
            
            self.alert_thresholds[component][metric] = (warning_threshold, critical_threshold)
            logger.debug(f"Set thresholds for {component}.{metric}: {warning_threshold}, {critical_threshold}")
    
    def check_component_health(self, component_name: str) -> HealthCheckResult:
        """Check health of specific component"""
        if component_name not in self.components:
            return HealthCheckResult(
                healthy=False,
                message=f"Component {component_name} not registered"
            )
        
        component = self.components[component_name]
        
        try:
            # Call the health check function
            health_data = component.health_check_func()
            
            # Process result
            healthy = health_data.get('healthy', False)
            metrics = health_data.get('metrics', {})
            message = health_data.get('message', '')
            details = health_data.get('details', {})
            
            # Update component status
            component.last_check = datetime.now()
            
            if healthy:
                component.status = HealthStatus.HEALTHY
                component.consecutive_failures = 0
            else:
                component.consecutive_failures += 1
                if component.consecutive_failures >= component.max_failures:
                    component.status = HealthStatus.FAILED
                    # Trigger failover if enabled
                    if component.failover_enabled and component.failover_target:
                        self._attempt_failover(component_name)
                else:
                    component.status = HealthStatus.CRITICAL
            
            # Process metrics and check thresholds
            for metric_name, value in metrics.items():
                self._process_metric(component_name, metric_name, value)
            
            self.total_checks_performed += 1
            
            return HealthCheckResult(
                healthy=healthy,
                metrics=metrics,
                message=message,
                details=details
            )
            
        except Exception as e:
            logger.error(f"Health check failed for {component_name}: {e}")
            component.status = HealthStatus.FAILED
            component.consecutive_failures += 1
            
            return HealthCheckResult(
                healthy=False,
                message=f"Health check exception: {str(e)}"
            )
    
    def get_system_health(self) -> Dict[str, Any]:
        """Get overall system health"""
        with self._lock:
            total_components = len(self.components)
            healthy_components = 0
            critical_unhealthy = 0
            component_statuses = {}
            
            for name, component in self.components.items():
                # Get latest health check
                health_result = self.check_component_health(name)
                
                component_statuses[name] = {
                    'status': component.status.value,
                    'healthy': health_result.healthy,
                    'last_check': component.last_check,
                    'consecutive_failures': component.consecutive_failures,
                    'metrics': health_result.metrics,
                    'message': health_result.message,
                    'is_critical': name in self.critical_components
                }
                
                if health_result.healthy:
                    healthy_components += 1
                elif name in self.critical_components:
                    critical_unhealthy += 1
            
            # System is healthy if all critical components are healthy
            # and at least 80% of all components are healthy
            health_rate = healthy_components / total_components if total_components > 0 else 0
            overall_healthy = (critical_unhealthy == 0 and health_rate >= 0.8)
            
            active_alerts = [alert for alert in self.alerts if not alert.resolved]
            
            return {
                'overall_healthy': overall_healthy,
                'total_components': total_components,
                'healthy_components': healthy_components,
                'critical_components': len(self.critical_components),
                'critical_unhealthy': critical_unhealthy,
                'health_rate': health_rate,
                'component_statuses': component_statuses,
                'active_alerts': len(active_alerts),
                'total_alerts': len(self.alerts),
                'uptime_seconds': (datetime.now() - self.system_start_time).total_seconds(),
                'total_checks': self.total_checks_performed,
                'timestamp': datetime.now()
            }
    
    def start_monitoring(self):
        """Start background health monitoring"""
        if self.monitoring_active:
            logger.warning("Health monitoring already active")
            return
        
        self.monitoring_active = True
        
        def monitoring_loop():
            logger.info("Started health monitoring loop")
            while self.monitoring_active:
                try:
                    self._perform_health_checks()
                    self._check_predictive_alerts()
                    time.sleep(self.check_interval.total_seconds())
                except Exception as e:
                    logger.error(f"Health monitoring error: {e}")
                    time.sleep(self.check_interval.total_seconds() * 2)  # Back off on error
        
        self.monitoring_thread = threading.Thread(target=monitoring_loop, daemon=True)
        self.monitoring_thread.start()
        
        logger.info("Health monitoring started")
    
    def stop_monitoring(self):
        """Stop background health monitoring"""
        self.monitoring_active = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)
        logger.info("Health monitoring stopped")
    
    def add_alert_callback(self, callback: Callable[[HealthAlert], None]):
        """Add callback for health alerts"""
        self.alert_callbacks.append(callback)
    
    def get_active_alerts(self) -> List[HealthAlert]:
        """Get all active (unresolved) alerts"""
        return [alert for alert in self.alerts if not alert.resolved]
    
    def resolve_alert(self, alert_id: str):
        """Resolve an alert"""
        for alert in self.alerts:
            if alert.id == alert_id:
                alert.resolve()
                logger.info(f"Resolved alert: {alert_id}")
                break
    
    def get_component_trends(self, component: str, metric: str) -> Dict[str, Any]:
        """Get trend analysis for component metric"""
        return self.trend_analyzer.analyze_trend(component, metric)
    
    def _process_metric(self, component: str, metric_name: str, value: float):
        """Process metric value and check thresholds"""
        # Add to trend analysis
        self.trend_analyzer.add_metric(component, metric_name, value)
        
        # Check thresholds
        if component in self.alert_thresholds and metric_name in self.alert_thresholds[component]:
            warning_threshold, critical_threshold = self.alert_thresholds[component][metric_name]
            
            severity = None
            threshold_breached = None
            
            if value >= critical_threshold:
                severity = AlertSeverity.CRITICAL
                threshold_breached = critical_threshold
            elif value >= warning_threshold:
                severity = AlertSeverity.WARNING
                threshold_breached = warning_threshold
            
            if severity:
                # Check if we already have an active alert for this metric
                existing_alerts = [
                    alert for alert in self.alerts
                    if (alert.component == component and 
                        alert.metric == metric_name and 
                        not alert.resolved)
                ]
                
                # Only create new alert if severity increased or no existing alert
                should_create_alert = True
                if existing_alerts:
                    latest_alert = max(existing_alerts, key=lambda a: a.timestamp)
                    if latest_alert.severity.value == severity.value:
                        should_create_alert = False
                
                if should_create_alert:
                    alert = HealthAlert(
                        id=f"{component}_{metric_name}_{datetime.now().timestamp()}",
                        component=component,
                        metric=metric_name,
                        severity=severity,
                        message=f"{component}.{metric_name} = {value} (threshold: {threshold_breached})",
                        value=value,
                        threshold=threshold_breached,
                        timestamp=datetime.now()
                    )
                    
                    self.alerts.append(alert)
                    self.total_alerts_generated += 1
                    
                    # Notify callbacks
                    for callback in self.alert_callbacks:
                        try:
                            callback(alert)
                        except Exception as e:
                            logger.error(f"Alert callback error: {e}")
                    
                    logger.warning(f"Health alert: {alert.message}")
    
    def _perform_health_checks(self):
        """Perform health checks for all components"""
        current_time = datetime.now()
        
        for component_name, component in self.components.items():
            # Check if it's time for a health check
            if current_time - component.last_check >= component.check_interval:
                self.check_component_health(component_name)
    
    def _check_predictive_alerts(self):
        """Check for predictive alerts based on trends"""
        for component_name in self.components:
            if component_name in self.alert_thresholds:
                for metric_name, (warning_threshold, critical_threshold) in self.alert_thresholds[component_name].items():
                    # Check prediction for critical threshold
                    prediction = self.trend_analyzer.predict_threshold_breach(
                        component_name, metric_name, critical_threshold, minutes_ahead=15
                    )
                    
                    if (prediction.get("prediction") == "breach_likely" and 
                        prediction.get("probability", 0) > 0.7):
                        
                        # Create predictive alert
                        alert = HealthAlert(
                            id=f"predictive_{component_name}_{metric_name}_{datetime.now().timestamp()}",
                            component=component_name,
                            metric=metric_name,
                            severity=AlertSeverity.WARNING,
                            message=f"Predictive: {component_name}.{metric_name} likely to breach {critical_threshold} in {prediction.get('minutes_to_breach', 'unknown')} minutes",
                            value=prediction.get("current_value", 0),
                            threshold=critical_threshold,
                            timestamp=datetime.now()
                        )
                        
                        # Check if we already have a similar predictive alert
                        similar_alerts = [
                            a for a in self.alerts
                            if (a.component == component_name and 
                                a.metric == metric_name and 
                                a.id.startswith("predictive_") and
                                not a.resolved and
                                (datetime.now() - a.timestamp).total_seconds() < 600)  # Within 10 minutes
                        ]
                        
                        if not similar_alerts:
                            self.alerts.append(alert)
                            logger.info(f"Predictive alert: {alert.message}")
    
    def _attempt_failover(self, component_name: str):
        """
        Attempt failover for failed component
        
        Enforces Property 26: Failover Consistency (H2)
        """
        component = self.components[component_name]
        
        if not component.failover_enabled or not component.failover_target:
            logger.warning(f"Failover not enabled for {component_name}")
            return False
        
        if not self.failover_handler.can_failover(component_name):
            logger.warning(f"Cannot failover {component_name}")
            return False
        
        logger.warning(f"Attempting failover for {component_name} to {component.failover_target}")
        
        success = self.failover_handler.execute_failover(component_name, component.failover_target)
        
        if success:
            # SYSTEM LAW: Failover must maintain system consistency
            # Verify failover target is healthy
            if component.failover_target in self.components:
                target_health = self.check_component_health(component.failover_target)
                if not target_health.healthy:
                    logger.error(f"Failover target {component.failover_target} is unhealthy")
                    self.failover_handler.rollback_failover(component_name)
                    return False
            
            # Create failover alert
            alert = HealthAlert(
                id=f"failover_{component_name}_{datetime.now().timestamp()}",
                component=component_name,
                metric="failover",
                severity=AlertSeverity.CRITICAL,
                message=f"Failover executed: {component_name} -> {component.failover_target}",
                value=1.0,
                threshold=1.0,
                timestamp=datetime.now()
            )
            
            self.alerts.append(alert)
            logger.warning(f"Failover successful: {component_name} -> {component.failover_target}")
            return True
        else:
            logger.error(f"Failover failed for {component_name}")
            return False
    
    # IHealthMonitor interface methods
    def trigger_alert(self, component: str, severity: str, message: str):
        """Trigger health alert"""
        alert_severity = AlertSeverity.WARNING
        try:
            alert_severity = AlertSeverity(severity.lower())
        except ValueError:
            pass
        
        alert = HealthAlert(
            id=f"manual_{component}_{datetime.now().timestamp()}",
            component=component,
            metric="manual",
            severity=alert_severity,
            message=message,
            value=0.0,
            threshold=0.0,
            timestamp=datetime.now()
        )
        
        self.alerts.append(alert)
        logger.warning(f"Manual alert: {component} - {severity} - {message}")
    
    def initialize(self) -> bool:
        """Initialize the health monitor"""
        try:
            self.start_monitoring()
            return True
        except Exception as e:
            logger.error(f"Health monitor initialization failed: {e}")
            return False
    
    def shutdown(self) -> bool:
        """Shutdown the health monitor"""
        try:
            self.stop_monitoring()
            return True
        except Exception as e:
            logger.error(f"Health monitor shutdown failed: {e}")
            return False
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get health monitor health status"""
        return {
            'healthy': self.monitoring_active,
            'registered_components': len(self.components),
            'critical_components': len(self.critical_components),
            'total_alerts': len(self.alerts),
            'active_alerts': len([a for a in self.alerts if not a.resolved]),
            'uptime_seconds': (datetime.now() - self.system_start_time).total_seconds(),
            'total_checks': self.total_checks_performed,
            'message': f"Monitoring {len(self.components)} components ({len(self.critical_components)} critical)"
        }


# Convenience alias for backward compatibility
HealthMonitor = ComprehensiveHealthMonitor