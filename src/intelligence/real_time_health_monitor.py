#!/usr/bin/env python3
"""
📊 REAL-TIME HEALTH MONITORING DASHBOARD - LAYER 12
Comprehensive real-time health monitoring for institutional alpha engine

This implements Layer 12 of the institutional alpha engine:
- Real-time tracking of IC, decay, crowding, regime fit
- Alert generation for metrics below 25th percentile
- Performance deviation flagging (>2 std dev)
- Regime confidence monitoring (<60% threshold)
- Survival protocol activation (volatility >95th percentile)
- Defensive mode triggers for multi-specialist degradation

Key Features:
1. Real-time health metrics tracking
2. Percentile-based alert system
3. Performance deviation detection
4. Regime confidence monitoring
5. Survival protocol activation
6. Multi-specialist degradation detection
7. Defensive mode coordination

Usage:
    try:
    from src.intelligence.real_time_health_monitor import RealTimeHealthMonitor
except ImportError:
    from RealTimeHealthMonitor import RealTimeHealthMonitor
    
    monitor = RealTimeHealthMonitor()
    health_status = monitor.monitor_system_health(specialists, market_data)
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import warnings
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from enum import Enum
import json
import threading
import time
from collections import deque

warnings.filterwarnings('ignore')

import sys
try:
    from src.volatility.regime_detector import VolatilityRegime, RegimeState
except ImportError:
    from src.volatility.regime_detector import VolatilityRegime, RegimeState

# Legacy alias for compatibility
MarketRegime = VolatilityRegime
RegimeContext = RegimeState

@dataclass
class HealthMetrics:
    """Health metrics for a specialist"""
    specialist_name: str
    information_coefficient: float
    decay_rate: float
    crowding_index: float
    regime_fit: float
    performance_deviation: float
    regime_confidence: float
    timestamp: datetime
    
    # Percentile rankings
    ic_percentile: float
    decay_percentile: float
    crowding_percentile: float
    regime_fit_percentile: float

@dataclass
class HealthAlert:
    """Health monitoring alert"""
    alert_id: str
    specialist_name: str
    alert_type: str
    severity: str  # 'low', 'medium', 'high', 'critical'
    metric_name: str
    current_value: float
    threshold_value: float
    percentile: float
    description: str
    recommendation: str
    timestamp: datetime
    auto_action_taken: Optional[str] = None

@dataclass
class SystemHealthStatus:
    """Overall system health status"""
    overall_health: str  # 'healthy', 'warning', 'critical', 'defensive'
    healthy_specialists: int
    warning_specialists: int
    critical_specialists: int
    active_alerts: List[HealthAlert]
    survival_protocol_active: bool
    defensive_mode_active: bool
    regime_confidence: float
    market_volatility_percentile: float
    timestamp: datetime

class AlertSeverity(Enum):
    """Alert severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class HealthMonitoringEngine:
    """
    Health Monitoring Engine
    
    Core engine for tracking specialist health metrics
    and generating alerts.
    """
    
    def __init__(self):
        self.historical_metrics = {}  # specialist_name -> deque of HealthMetrics
        self.alert_history = deque(maxlen=1000)
        self.percentile_lookback_days = 252  # 1 year of trading days
        
        # Thresholds
        self.alert_percentile_threshold = 25.0  # Below 25th percentile triggers alert
        self.performance_deviation_threshold = 2.0  # >2 std dev triggers alert
        self.regime_confidence_threshold = 60.0  # <60% triggers alert
        self.volatility_survival_threshold = 95.0  # >95th percentile triggers survival protocol
        
        print("📊 Health Monitoring Engine initialized")
    
    def update_specialist_metrics(self, specialist_name: str, metrics: Dict[str, float]):
        """Update health metrics for a specialist"""
        
        # Calculate percentiles based on historical data
        if specialist_name not in self.historical_metrics:
            self.historical_metrics[specialist_name] = deque(maxlen=self.percentile_lookback_days)
        
        history = self.historical_metrics[specialist_name]
        
        # Calculate percentiles (use 50th percentile if insufficient history)
        ic_percentile = self._calculate_percentile(
            [h.information_coefficient for h in history], 
            metrics.get('information_coefficient', 0.0)
        )
        
        decay_percentile = self._calculate_percentile(
            [h.decay_rate for h in history], 
            metrics.get('decay_rate', 0.0),
            reverse=True  # Lower decay is better
        )
        
        crowding_percentile = self._calculate_percentile(
            [h.crowding_index for h in history], 
            metrics.get('crowding_index', 0.0),
            reverse=True  # Lower crowding is better
        )
        
        regime_fit_percentile = self._calculate_percentile(
            [h.regime_fit for h in history], 
            metrics.get('regime_fit', 0.0)
        )
        
        # Create health metrics object
        health_metrics = HealthMetrics(
            specialist_name=specialist_name,
            information_coefficient=metrics.get('information_coefficient', 0.0),
            decay_rate=metrics.get('decay_rate', 0.0),
            crowding_index=metrics.get('crowding_index', 0.0),
            regime_fit=metrics.get('regime_fit', 0.0),
            performance_deviation=metrics.get('performance_deviation', 0.0),
            regime_confidence=metrics.get('regime_confidence', 0.0),
            timestamp=datetime.now(),
            ic_percentile=ic_percentile,
            decay_percentile=decay_percentile,
            crowding_percentile=crowding_percentile,
            regime_fit_percentile=regime_fit_percentile
        )
        
        # Add to history
        history.append(health_metrics)
        
        return health_metrics
    
    def _calculate_percentile(self, historical_values: List[float], current_value: float, 
                            reverse: bool = False) -> float:
        """Calculate percentile of current value vs historical values"""
        
        if len(historical_values) < 10:  # Insufficient history
            return 50.0  # Return neutral percentile
        
        values = np.array(historical_values + [current_value])
        
        if reverse:
            # For metrics where lower is better (decay, crowding)
            percentile = 100.0 - (np.searchsorted(np.sort(values), current_value) / len(values) * 100.0)
        else:
            # For metrics where higher is better (IC, regime fit)
            percentile = np.searchsorted(np.sort(values), current_value) / len(values) * 100.0
        
        return max(0.0, min(100.0, percentile))
    
    def generate_alerts(self, health_metrics: HealthMetrics) -> List[HealthAlert]:
        """Generate alerts based on health metrics"""
        
        alerts = []
        
        # IC below 25th percentile
        if health_metrics.ic_percentile < self.alert_percentile_threshold:
            alert = HealthAlert(
                alert_id=f"{health_metrics.specialist_name}_ic_{int(time.time())}",
                specialist_name=health_metrics.specialist_name,
                alert_type="information_coefficient_low",
                severity=AlertSeverity.MEDIUM.value,
                metric_name="Information Coefficient",
                current_value=health_metrics.information_coefficient,
                threshold_value=self.alert_percentile_threshold,
                percentile=health_metrics.ic_percentile,
                description=f"IC below {self.alert_percentile_threshold}th percentile",
                recommendation="Review signal generation and consider recalibration",
                timestamp=health_metrics.timestamp
            )
            alerts.append(alert)
        
        # Decay rate above 75th percentile (high decay is bad)
        if health_metrics.decay_percentile < self.alert_percentile_threshold:
            alert = HealthAlert(
                alert_id=f"{health_metrics.specialist_name}_decay_{int(time.time())}",
                specialist_name=health_metrics.specialist_name,
                alert_type="signal_decay_high",
                severity=AlertSeverity.HIGH.value,
                metric_name="Signal Decay Rate",
                current_value=health_metrics.decay_rate,
                threshold_value=self.alert_percentile_threshold,
                percentile=health_metrics.decay_percentile,
                description=f"Signal decay above {100-self.alert_percentile_threshold}th percentile",
                recommendation="Investigate signal degradation and consider factor refresh",
                timestamp=health_metrics.timestamp
            )
            alerts.append(alert)
        
        # Crowding index above 75th percentile (high crowding is bad)
        if health_metrics.crowding_percentile < self.alert_percentile_threshold:
            alert = HealthAlert(
                alert_id=f"{health_metrics.specialist_name}_crowding_{int(time.time())}",
                specialist_name=health_metrics.specialist_name,
                alert_type="crowding_high",
                severity=AlertSeverity.MEDIUM.value,
                metric_name="Crowding Index",
                current_value=health_metrics.crowding_index,
                threshold_value=self.alert_percentile_threshold,
                percentile=health_metrics.crowding_percentile,
                description=f"Crowding above {100-self.alert_percentile_threshold}th percentile",
                recommendation="Reduce position sizes and consider alternative signals",
                timestamp=health_metrics.timestamp
            )
            alerts.append(alert)
        
        # Regime fit below 25th percentile
        if health_metrics.regime_fit_percentile < self.alert_percentile_threshold:
            alert = HealthAlert(
                alert_id=f"{health_metrics.specialist_name}_regime_fit_{int(time.time())}",
                specialist_name=health_metrics.specialist_name,
                alert_type="regime_fit_low",
                severity=AlertSeverity.MEDIUM.value,
                metric_name="Regime Fit",
                current_value=health_metrics.regime_fit,
                threshold_value=self.alert_percentile_threshold,
                percentile=health_metrics.regime_fit_percentile,
                description=f"Regime fit below {self.alert_percentile_threshold}th percentile",
                recommendation="Review regime detection and specialist adaptation",
                timestamp=health_metrics.timestamp
            )
            alerts.append(alert)
        
        # Performance deviation > 2 std dev
        if abs(health_metrics.performance_deviation) > self.performance_deviation_threshold:
            severity = AlertSeverity.HIGH.value if abs(health_metrics.performance_deviation) > 3.0 else AlertSeverity.MEDIUM.value
            
            alert = HealthAlert(
                alert_id=f"{health_metrics.specialist_name}_perf_dev_{int(time.time())}",
                specialist_name=health_metrics.specialist_name,
                alert_type="performance_deviation",
                severity=severity,
                metric_name="Performance Deviation",
                current_value=health_metrics.performance_deviation,
                threshold_value=self.performance_deviation_threshold,
                percentile=0.0,  # Not percentile-based
                description=f"Performance deviation {health_metrics.performance_deviation:.1f} std dev",
                recommendation="Investigate performance anomaly and consider position adjustment",
                timestamp=health_metrics.timestamp
            )
            alerts.append(alert)
        
        # Regime confidence < 60%
        if health_metrics.regime_confidence < self.regime_confidence_threshold:
            alert = HealthAlert(
                alert_id=f"{health_metrics.specialist_name}_regime_conf_{int(time.time())}",
                specialist_name=health_metrics.specialist_name,
                alert_type="regime_confidence_low",
                severity=AlertSeverity.MEDIUM.value,
                metric_name="Regime Confidence",
                current_value=health_metrics.regime_confidence,
                threshold_value=self.regime_confidence_threshold,
                percentile=0.0,  # Not percentile-based
                description=f"Regime confidence {health_metrics.regime_confidence:.1f}% below threshold",
                recommendation="Increase diversification and reduce conviction",
                timestamp=health_metrics.timestamp
            )
            alerts.append(alert)
        
        # Store alerts in history
        for alert in alerts:
            self.alert_history.append(alert)
        
        return alerts


class PerformanceMonitor:
    """
    Performance Monitor
    
    Monitors performance deviations and survival protocols.
    """
    
    def __init__(self):
        self.performance_history = {}  # specialist_name -> deque of performance values
        self.volatility_history = deque(maxlen=252)  # 1 year of volatility data
        self.survival_protocol_active = False
        self.defensive_mode_active = False
        
        print("📈 Performance Monitor initialized")
    
    def update_performance_metrics(self, specialist_name: str, performance: float, 
                                 market_volatility: float):
        """Update performance metrics for a specialist"""
        
        # Initialize history if needed
        if specialist_name not in self.performance_history:
            self.performance_history[specialist_name] = deque(maxlen=252)
        
        # Add to history
        self.performance_history[specialist_name].append(performance)
        self.volatility_history.append(market_volatility)
        
        # Calculate performance deviation
        perf_history = list(self.performance_history[specialist_name])
        if len(perf_history) > 30:  # Need sufficient history
            mean_perf = np.mean(perf_history)
            std_perf = np.std(perf_history)
            deviation = (performance - mean_perf) / (std_perf + 1e-8)  # Avoid division by zero
        else:
            deviation = 0.0
        
        return deviation
    
    def check_survival_protocol(self, market_volatility: float) -> bool:
        """Check if survival protocol should be activated"""
        
        if len(self.volatility_history) < 10:  # Reduced minimum history requirement
            # If insufficient history, use simple threshold
            vol_threshold = 0.40  # 40% volatility threshold
            should_activate = market_volatility > vol_threshold
        else:
            # Calculate volatility percentile
            vol_percentile = np.percentile(list(self.volatility_history), 95)
            should_activate = market_volatility > vol_percentile
        
        if should_activate and not self.survival_protocol_active:
            print(f"🚨 SURVIVAL PROTOCOL ACTIVATED: Volatility {market_volatility:.3f} exceeds threshold")
            self.survival_protocol_active = True
        elif not should_activate and self.survival_protocol_active:
            print(f"✅ SURVIVAL PROTOCOL DEACTIVATED: Volatility normalized")
            self.survival_protocol_active = False
        
        return self.survival_protocol_active
    
    def check_defensive_mode(self, specialist_alerts: Dict[str, List[HealthAlert]]) -> bool:
        """Check if defensive mode should be activated"""
        
        # Count specialists with high/critical alerts
        specialists_with_issues = 0
        total_specialists = len(specialist_alerts)
        
        for specialist, alerts in specialist_alerts.items():
            has_serious_alert = any(
                alert.severity in ['high', 'critical'] 
                for alert in alerts
            )
            # Also count specialists with multiple medium alerts as having issues
            has_multiple_medium = len([a for a in alerts if a.severity == 'medium']) >= 2
            
            if has_serious_alert or has_multiple_medium:
                specialists_with_issues += 1
        
        # Activate defensive mode if >50% of specialists have issues OR if survival protocol is active
        issue_ratio = specialists_with_issues / max(total_specialists, 1)
        should_activate = issue_ratio > 0.5 or self.survival_protocol_active
        
        if should_activate and not self.defensive_mode_active:
            print(f"🛡️ DEFENSIVE MODE ACTIVATED: {specialists_with_issues}/{total_specialists} specialists degraded")
            self.defensive_mode_active = True
        elif not should_activate and self.defensive_mode_active:
            print(f"✅ DEFENSIVE MODE DEACTIVATED: System health restored")
            self.defensive_mode_active = False
        
        return self.defensive_mode_active


class RealTimeHealthMonitor:
    """
    Real-Time Health Monitoring Dashboard
    
    Main orchestrator for real-time health monitoring
    of the institutional alpha engine.
    """
    
    def __init__(self):
        self.health_engine = HealthMonitoringEngine()
        self.performance_monitor = PerformanceMonitor()
        self.monitoring_active = False
        self.monitoring_thread = None
        self.update_interval = 60  # Update every 60 seconds
        
        print("📊 Real-Time Health Monitor initialized")
    
    def monitor_system_health(self, specialists_data: Dict[str, Any], 
                            market_data: Dict[str, Any]) -> SystemHealthStatus:
        """Monitor comprehensive system health"""
        
        print("📊 Running real-time health monitoring")
        print("=" * 50)
        
        all_alerts = {}
        specialist_health_metrics = {}
        
        # Monitor each specialist
        print("\n📈 SPECIALIST HEALTH MONITORING")
        print("-" * 40)
        
        for specialist_name, data in specialists_data.items():
            print(f"   Monitoring {specialist_name} specialist...")
            
            # Extract health metrics
            metrics = {
                'information_coefficient': data.get('ic', 0.0),
                'decay_rate': data.get('decay_rate', 0.0),
                'crowding_index': data.get('crowding_index', 0.0),
                'regime_fit': data.get('regime_fit', 0.0),
                'regime_confidence': data.get('regime_confidence', 0.0)
            }
            
            # Calculate performance deviation
            performance = data.get('recent_performance', 0.0)
            market_volatility = market_data.get('volatility', 0.0)
            
            performance_deviation = self.performance_monitor.update_performance_metrics(
                specialist_name, performance, market_volatility
            )
            metrics['performance_deviation'] = performance_deviation
            
            # Update health metrics
            health_metrics = self.health_engine.update_specialist_metrics(specialist_name, metrics)
            specialist_health_metrics[specialist_name] = health_metrics
            
            # Generate alerts
            alerts = self.health_engine.generate_alerts(health_metrics)
            all_alerts[specialist_name] = alerts
            
            # Report health status
            alert_count = len(alerts)
            if alert_count == 0:
                print(f"      ✅ {specialist_name}: Healthy")
            else:
                severities = [a.severity for a in alerts]
                if 'critical' in severities:
                    print(f"      🚨 {specialist_name}: Critical ({alert_count} alerts)")
                elif 'high' in severities:
                    print(f"      ⚠️ {specialist_name}: Warning ({alert_count} alerts)")
                else:
                    print(f"      ⚡ {specialist_name}: Minor issues ({alert_count} alerts)")
        
        # Check survival protocol
        print(f"\n🚨 SURVIVAL PROTOCOL MONITORING")
        print("-" * 40)
        
        market_volatility = market_data.get('volatility', 0.0)
        survival_active = self.performance_monitor.check_survival_protocol(market_volatility)
        
        if survival_active:
            print(f"   🚨 SURVIVAL PROTOCOL: ACTIVE")
            print(f"      Market volatility: {market_volatility:.3f}")
        else:
            print(f"   ✅ SURVIVAL PROTOCOL: Inactive")
        
        # Check defensive mode (pass survival protocol status)
        print(f"\n🛡️ DEFENSIVE MODE MONITORING")
        print("-" * 40)
        
        # Update performance monitor with survival status
        self.performance_monitor.survival_protocol_active = survival_active
        defensive_active = self.performance_monitor.check_defensive_mode(all_alerts)
        
        if defensive_active:
            print(f"   🛡️ DEFENSIVE MODE: ACTIVE")
        else:
            print(f"   ✅ DEFENSIVE MODE: Inactive")
        
        # Calculate overall health
        healthy_count = sum(1 for alerts in all_alerts.values() if len(alerts) == 0)
        warning_count = sum(1 for alerts in all_alerts.values() 
                          if len(alerts) > 0 and not any(a.severity in ['high', 'critical'] for a in alerts))
        critical_count = sum(1 for alerts in all_alerts.values() 
                           if any(a.severity in ['high', 'critical'] for a in alerts))
        
        # Determine overall health status
        if survival_active or defensive_active:
            overall_health = "defensive"
        elif critical_count > 0:
            overall_health = "critical"
        elif warning_count > 0:
            overall_health = "warning"
        else:
            overall_health = "healthy"
        
        # Flatten all alerts
        flat_alerts = []
        for alerts in all_alerts.values():
            flat_alerts.extend(alerts)
        
        # Calculate market volatility percentile
        vol_history = list(self.performance_monitor.volatility_history)
        if len(vol_history) > 10:
            vol_percentile = (np.searchsorted(np.sort(vol_history), market_volatility) / len(vol_history)) * 100
        else:
            vol_percentile = 50.0
        
        # Create system health status
        system_health = SystemHealthStatus(
            overall_health=overall_health,
            healthy_specialists=healthy_count,
            warning_specialists=warning_count,
            critical_specialists=critical_count,
            active_alerts=flat_alerts,
            survival_protocol_active=survival_active,
            defensive_mode_active=defensive_active,
            regime_confidence=market_data.get('regime_confidence', 0.0),
            market_volatility_percentile=vol_percentile,
            timestamp=datetime.now()
        )
        
        # Generate health report
        self._generate_health_report(system_health, specialist_health_metrics)
        
        return system_health
    
    def _generate_health_report(self, system_health: SystemHealthStatus, 
                              specialist_metrics: Dict[str, HealthMetrics]):
        """Generate comprehensive health report"""
        
        print(f"\n📋 SYSTEM HEALTH REPORT")
        print("=" * 40)
        
        # Overall status
        status_emoji = {
            'healthy': '✅',
            'warning': '⚠️',
            'critical': '🚨',
            'defensive': '🛡️'
        }
        
        print(f"Overall Health: {status_emoji.get(system_health.overall_health, '❓')} {system_health.overall_health.upper()}")
        print(f"Healthy Specialists: {system_health.healthy_specialists}")
        print(f"Warning Specialists: {system_health.warning_specialists}")
        print(f"Critical Specialists: {system_health.critical_specialists}")
        print(f"Active Alerts: {len(system_health.active_alerts)}")
        print(f"Survival Protocol: {'🚨 ACTIVE' if system_health.survival_protocol_active else '✅ Inactive'}")
        print(f"Defensive Mode: {'🛡️ ACTIVE' if system_health.defensive_mode_active else '✅ Inactive'}")
        print(f"Regime Confidence: {system_health.regime_confidence:.1f}%")
        print(f"Market Volatility: {system_health.market_volatility_percentile:.1f}th percentile")
        
        # Alert summary
        if system_health.active_alerts:
            print(f"\n⚠️ ACTIVE ALERTS")
            print("-" * 30)
            
            for alert in system_health.active_alerts[:5]:  # Show top 5 alerts
                severity_emoji = {
                    'low': '⚡',
                    'medium': '⚠️',
                    'high': '🚨',
                    'critical': '💥'
                }
                
                print(f"{severity_emoji.get(alert.severity, '❓')} {alert.specialist_name}: {alert.description}")
                print(f"   Recommendation: {alert.recommendation}")
        
        # System recommendations
        print(f"\n💡 SYSTEM RECOMMENDATIONS")
        print("-" * 30)
        
        if system_health.overall_health == 'healthy':
            print("✅ System operating normally - continue monitoring")
        elif system_health.overall_health == 'warning':
            print("⚠️ Monitor specialist performance closely")
            print("⚠️ Consider reducing position sizes if issues persist")
        elif system_health.overall_health == 'critical':
            print("🚨 Immediate attention required")
            print("🚨 Consider activating defensive protocols")
        elif system_health.overall_health == 'defensive':
            print("🛡️ Defensive protocols active")
            print("🛡️ Reduce risk exposure and monitor for stabilization")
    
    def start_continuous_monitoring(self, specialists_data: Dict[str, Any], 
                                  market_data: Dict[str, Any]):
        """Start continuous health monitoring in background thread"""
        
        if self.monitoring_active:
            print("⚠️ Monitoring already active")
            return
        
        self.monitoring_active = True
        
        def monitoring_loop():
            while self.monitoring_active:
                try:
                    self.monitor_system_health(specialists_data, market_data)
                    time.sleep(self.update_interval)
                except Exception as e:
                    print(f"❌ Monitoring error: {e}")
                    time.sleep(self.update_interval)
        
        self.monitoring_thread = threading.Thread(target=monitoring_loop, daemon=True)
        self.monitoring_thread.start()
        
        print(f"🔄 Continuous monitoring started (update interval: {self.update_interval}s)")
    
    def stop_continuous_monitoring(self):
        """Stop continuous health monitoring"""
        
        if not self.monitoring_active:
            print("⚠️ Monitoring not active")
            return
        
        self.monitoring_active = False
        
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)
        
        print("⏹️ Continuous monitoring stopped")


def main():
    """Demonstrate Real-Time Health Monitoring Dashboard"""
    
    print("📊 REAL-TIME HEALTH MONITORING DASHBOARD - LAYER 12")
    print("=" * 70)
    
    # Initialize health monitor
    monitor = RealTimeHealthMonitor()
    
    # Mock specialist data with various health conditions
    specialists_data = {
        'momentum': {
            'ic': 0.15,
            'decay_rate': 0.05,
            'crowding_index': 0.30,
            'regime_fit': 0.80,
            'regime_confidence': 85.0,
            'recent_performance': 0.12
        },
        'value': {
            'ic': 0.08,  # Low IC
            'decay_rate': 0.12,  # High decay
            'crowding_index': 0.25,
            'regime_fit': 0.65,
            'regime_confidence': 75.0,
            'recent_performance': -0.05  # Poor performance
        },
        'quality': {
            'ic': 0.18,
            'decay_rate': 0.03,
            'crowding_index': 0.15,
            'regime_fit': 0.90,
            'regime_confidence': 90.0,
            'recent_performance': 0.08
        },
        'macro': {
            'ic': 0.10,
            'decay_rate': 0.08,
            'crowding_index': 0.40,  # High crowding
            'regime_fit': 0.55,  # Poor regime fit
            'regime_confidence': 55.0,  # Low confidence
            'recent_performance': 0.02
        }
    }
    
    # Mock market data
    market_data = {
        'volatility': 0.35,  # High volatility
        'regime_confidence': 70.0,
        'liquidity': 0.75
    }
    
    # Run health monitoring
    health_status = monitor.monitor_system_health(specialists_data, market_data)
    
    print(f"\n✅ Real-Time Health Monitoring demonstration complete")
    print(f"   System Health: {health_status.overall_health}")
    print(f"   Active Alerts: {len(health_status.active_alerts)}")
    print(f"   Survival Protocol: {'Active' if health_status.survival_protocol_active else 'Inactive'}")

if __name__ == "__main__":
    main()