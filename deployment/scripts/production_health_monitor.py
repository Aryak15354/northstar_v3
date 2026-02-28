#!/usr/bin/env python3
"""
Production Health Monitoring Dashboard
Real-time system health monitoring and alerting
"""

import os
import sys
import json
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum

class AlertLevel(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"

@dataclass
class HealthMetric:
    """System health metric"""
    name: str
    value: float
    threshold: float
    status: str
    timestamp: datetime
    alert_level: AlertLevel

@dataclass
class SystemHealth:
    """Overall system health status"""
    overall_status: str
    metrics: List[HealthMetric]
    alerts: List[str]
    last_update: datetime

class ProductionHealthMonitor:
    """Production health monitoring system"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config = self._load_config(config_path)
        self.logger = self._setup_logging()
        self.metrics_history = []
        
    def _load_config(self, config_path: Optional[str]) -> Dict[str, Any]:
        """Load monitoring configuration"""
        
        default_config = {
            "monitoring": {
                "check_interval": 60,  # seconds
                "alert_thresholds": {
                    "cpu_usage": 80.0,
                    "memory_usage": 85.0,
                    "disk_usage": 90.0,
                    "error_rate": 5.0,
                    "response_time": 10.0
                },
                "alert_channels": ["log", "email"],
                "retention_days": 30
            }
        }
        
        if config_path and os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config = json.load(f)
            return {**default_config, **config}
        
        return default_config
    
    def _setup_logging(self) -> logging.Logger:
        """Setup monitoring logger"""
        
        logger = logging.getLogger("production_monitor")
        logger.setLevel(logging.INFO)
        
        # File handler
        log_dir = "logs"
        os.makedirs(log_dir, exist_ok=True)
        
        file_handler = logging.FileHandler(
            os.path.join(log_dir, "production_health.log")
        )
        file_handler.setLevel(logging.INFO)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.WARNING)
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        return logger
    
    def check_system_health(self) -> SystemHealth:
        """Check overall system health"""
        
        metrics = []
        alerts = []
        
        # Check CPU usage
        cpu_metric = self._check_cpu_usage()
        metrics.append(cpu_metric)
        if cpu_metric.alert_level != AlertLevel.INFO:
            alerts.append(f"CPU usage: {cpu_metric.value:.1f}%")
        
        # Check memory usage
        memory_metric = self._check_memory_usage()
        metrics.append(memory_metric)
        if memory_metric.alert_level != AlertLevel.INFO:
            alerts.append(f"Memory usage: {memory_metric.value:.1f}%")
        
        # Check disk usage
        disk_metric = self._check_disk_usage()
        metrics.append(disk_metric)
        if disk_metric.alert_level != AlertLevel.INFO:
            alerts.append(f"Disk usage: {disk_metric.value:.1f}%")
        
        # Check application health
        app_metrics = self._check_application_health()
        metrics.extend(app_metrics)
        
        # Determine overall status
        critical_alerts = [m for m in metrics if m.alert_level == AlertLevel.CRITICAL]
        warning_alerts = [m for m in metrics if m.alert_level == AlertLevel.WARNING]
        
        if critical_alerts:
            overall_status = "CRITICAL"
        elif warning_alerts:
            overall_status = "WARNING"
        else:
            overall_status = "HEALTHY"
        
        health = SystemHealth(
            overall_status=overall_status,
            metrics=metrics,
            alerts=alerts,
            last_update=datetime.now()
        )
        
        # Log health status
        self.logger.info(f"System health check: {overall_status}")
        if alerts:
            for alert in alerts:
                self.logger.warning(f"Health alert: {alert}")
        
        return health
    
    def _check_cpu_usage(self) -> HealthMetric:
        """Check CPU usage"""
        
        try:
            import psutil
            cpu_percent = psutil.cpu_percent(interval=1)
        except ImportError:
            # Fallback if psutil not available
            cpu_percent = 0.0
        
        threshold = self.config["monitoring"]["alert_thresholds"]["cpu_usage"]
        
        if cpu_percent > threshold:
            alert_level = AlertLevel.CRITICAL if cpu_percent > threshold * 1.2 else AlertLevel.WARNING
            status = "HIGH"
        else:
            alert_level = AlertLevel.INFO
            status = "NORMAL"
        
        return HealthMetric(
            name="cpu_usage",
            value=cpu_percent,
            threshold=threshold,
            status=status,
            timestamp=datetime.now(),
            alert_level=alert_level
        )
    
    def _check_memory_usage(self) -> HealthMetric:
        """Check memory usage"""
        
        try:
            import psutil
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
        except ImportError:
            memory_percent = 0.0
        
        threshold = self.config["monitoring"]["alert_thresholds"]["memory_usage"]
        
        if memory_percent > threshold:
            alert_level = AlertLevel.CRITICAL if memory_percent > threshold * 1.1 else AlertLevel.WARNING
            status = "HIGH"
        else:
            alert_level = AlertLevel.INFO
            status = "NORMAL"
        
        return HealthMetric(
            name="memory_usage",
            value=memory_percent,
            threshold=threshold,
            status=status,
            timestamp=datetime.now(),
            alert_level=alert_level
        )
    
    def _check_disk_usage(self) -> HealthMetric:
        """Check disk usage"""
        
        try:
            import psutil
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
        except ImportError:
            disk_percent = 0.0
        
        threshold = self.config["monitoring"]["alert_thresholds"]["disk_usage"]
        
        if disk_percent > threshold:
            alert_level = AlertLevel.CRITICAL if disk_percent > threshold * 1.05 else AlertLevel.WARNING
            status = "HIGH"
        else:
            alert_level = AlertLevel.INFO
            status = "NORMAL"
        
        return HealthMetric(
            name="disk_usage",
            value=disk_percent,
            threshold=threshold,
            status=status,
            timestamp=datetime.now(),
            alert_level=alert_level
        )
    
    def _check_application_health(self) -> List[HealthMetric]:
        """Check application-specific health metrics"""
        
        metrics = []
        
        # Check if key files exist
        key_files = [
            "src/intelligence/institutional_alpha_engine.py",
            "src/cohesion/unified_state_manager.py",
            "src/cohesion/temporal_guard.py"
        ]
        
        missing_files = 0
        for file_path in key_files:
            if not os.path.exists(file_path):
                missing_files += 1
        
        file_health = HealthMetric(
            name="core_files_available",
            value=((len(key_files) - missing_files) / len(key_files)) * 100,
            threshold=100.0,
            status="CRITICAL" if missing_files > 0 else "NORMAL",
            timestamp=datetime.now(),
            alert_level=AlertLevel.CRITICAL if missing_files > 0 else AlertLevel.INFO
        )
        metrics.append(file_health)
        
        return metrics
    
    def start_monitoring(self, duration_minutes: Optional[int] = None):
        """Start continuous monitoring"""
        
        print("🔍 Starting production health monitoring...")
        print(f"Check interval: {self.config['monitoring']['check_interval']} seconds")
        
        start_time = datetime.now()
        check_count = 0
        
        try:
            while True:
                # Check if duration limit reached
                if duration_minutes:
                    elapsed = (datetime.now() - start_time).total_seconds() / 60
                    if elapsed >= duration_minutes:
                        break
                
                # Perform health check
                health = self.check_system_health()
                check_count += 1
                
                # Display status
                status_icon = "🟢" if health.overall_status == "HEALTHY" else "🟡" if health.overall_status == "WARNING" else "🔴"
                print(f"{status_icon} [{datetime.now().strftime('%H:%M:%S')}] System Status: {health.overall_status}")
                
                if health.alerts:
                    for alert in health.alerts:
                        print(f"  ⚠️ {alert}")
                
                # Store metrics
                self.metrics_history.append(health)
                
                # Sleep until next check
                time.sleep(self.config["monitoring"]["check_interval"])
                
        except KeyboardInterrupt:
            print("\n🛑 Monitoring stopped by user")
        
        print(f"\n📊 Monitoring completed: {check_count} health checks performed")

def main():
    """Health monitoring main function"""
    
    import argparse
    
    parser = argparse.ArgumentParser(description="Northstar V3 Production Health Monitor")
    parser.add_argument("--config", help="Monitoring configuration file")
    parser.add_argument("--duration", type=int, help="Monitoring duration in minutes")
    parser.add_argument("--single-check", action="store_true", help="Perform single health check")
    
    args = parser.parse_args()
    
    monitor = ProductionHealthMonitor(args.config)
    
    if args.single_check:
        health = monitor.check_system_health()
        print(f"\nSystem Health: {health.overall_status}")
        print(f"Metrics: {len(health.metrics)}")
        print(f"Alerts: {len(health.alerts)}")
        
        for metric in health.metrics:
            status_icon = "🟢" if metric.alert_level == AlertLevel.INFO else "🟡" if metric.alert_level == AlertLevel.WARNING else "🔴"
            print(f"  {status_icon} {metric.name}: {metric.value:.1f} (threshold: {metric.threshold})")
    else:
        monitor.start_monitoring(args.duration)

if __name__ == "__main__":
    main()
