"""
Alert and Diagnostic System

Comprehensive alert and diagnostic system for Phase 3 intelligence monitoring:
- Real-time anomaly detection and alerting
- Phase 3 component diagnostic analysis
- Performance divergence threshold monitoring
- Actionable diagnostic information and recommendations

This system provides proactive monitoring and diagnostic capabilities to ensure
optimal Phase 3 intelligence performance and early detection of issues.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Union, Callable
from dataclasses import dataclass, field
from collections import deque, defaultdict
from enum import Enum
import numpy as np
import pandas as pd
import json

from src.validation.phase3_intelligence_monitor import Phase3IntelligenceMonitor, Phase3IntelligenceSnapshot
from src.validation.shadow_portfolio_dashboard import ShadowPortfolioDashboard, DashboardSnapshot
from src.validation.performance_attribution_display import PerformanceAttributionDisplay, AttributionDisplaySnapshot
from src.core.events import EventBus

logger = logging.getLogger(__name__)

class AlertSeverity(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"

class AlertCategory(Enum):
    """Alert categories"""
    PERFORMANCE = "performance"
    REGIME = "regime"
    COMPONENT = "component"
    RISK = "risk"
    SYSTEM = "system"
    ATTRIBUTION = "attribution"

@dataclass
class Alert:
    """Individual alert data"""
    id: str
    timestamp: datetime
    severity: AlertSeverity
    category: AlertCategory
    title: str
    message: str
    details: Dict[str, Any]
    recommendations: List[str]
    affected_components: List[str]
    threshold_breached: Optional[Dict[str, float]] = None
    auto_resolve: bool = False
    resolved: bool = False
    resolution_timestamp: Optional[datetime] = None

@dataclass
class DiagnosticResult:
    """Diagnostic analysis result"""
    component_name: str
    health_score: float
    issues_detected: List[str]
    performance_impact: float
    confidence_level: float
    recommendations: List[str]
    detailed_analysis: Dict[str, Any]
    trend_analysis: Dict[str, str]

@dataclass
class SystemHealthReport:
    """Comprehensive system health report"""
    timestamp: datetime
    overall_health_score: float
    component_health: Dict[str, float]
    active_alerts: List[Alert]
    diagnostic_results: List[DiagnosticResult]
    performance_summary: Dict[str, float]
    risk_indicators: Dict[str, float]
    recommendations: List[str]

class AlertAndDiagnosticSystem:
    """
    Comprehensive alert and diagnostic system for Phase 3 intelligence
    
    Provides:
    - Real-time anomaly detection and alerting
    - Component-specific diagnostic analysis
    - Performance threshold monitoring
    - Actionable recommendations and remediation guidance
    """
    
    def __init__(self,
                 intelligence_monitor: Phase3IntelligenceMonitor,
                 portfolio_dashboard: ShadowPortfolioDashboard,
                 attribution_display: PerformanceAttributionDisplay,
                 event_bus: EventBus,
                 alert_history_size: int = 1000):
        """
        Initialize alert and diagnostic system
        
        Args:
            intelligence_monitor: Phase 3 intelligence monitor
            portfolio_dashboard: Shadow portfolio dashboard
            attribution_display: Performance attribution display
            event_bus: System event bus
            alert_history_size: Number of alerts to maintain in history
        """
        self.intelligence_monitor = intelligence_monitor
        self.portfolio_dashboard = portfolio_dashboard
        self.attribution_display = attribution_display
        self.event_bus = event_bus
        self.alert_history_size = alert_history_size
        
        # Alert and diagnostic state
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_history: deque = deque(maxlen=alert_history_size)
        self.diagnostic_history: deque = deque(maxlen=100)
        
        # Alert thresholds and rules
        self.alert_thresholds = self._initialize_alert_thresholds()
        self.diagnostic_rules = self._initialize_diagnostic_rules()
        
        # Alert suppression and rate limiting
        self.alert_suppression: Dict[str, datetime] = {}
        self.suppression_duration = timedelta(minutes=15)  # Suppress duplicate alerts for 15 minutes
        
        # Performance tracking
        self.total_alerts_generated = 0
        self.alerts_by_category = defaultdict(int)
        self.alerts_by_severity = defaultdict(int)
        
        # Custom alert handlers
        self.custom_alert_handlers: Dict[str, Callable] = {}
        
        logger.info("AlertAndDiagnosticSystem initialized")
    
    def _initialize_alert_thresholds(self) -> Dict[str, Dict[str, float]]:
        """Initialize alert thresholds for different metrics"""
        return {
            "regime_confidence": {
                "warning": 0.3,
                "critical": 0.2
            },
            "health_score": {
                "warning": 0.4,
                "critical": 0.3
            },
            "portfolio_divergence": {
                "warning": 0.05,  # 5%
                "critical": 0.10   # 10%
            },
            "drawdown": {
                "warning": 0.10,  # 10%
                "critical": 0.20   # 20%
            },
            "no_edge_duration": {
                "warning": 10,
                "critical": 20
            },
            "attribution_quality": {
                "warning": 0.5,
                "critical": 0.3
            },
            "sharpe_ratio": {
                "warning": -0.5,
                "critical": -1.0
            },
            "volatility": {
                "warning": 0.25,  # 25%
                "critical": 0.40   # 40%
            }
        }
    
    def _initialize_diagnostic_rules(self) -> Dict[str, Dict[str, Any]]:
        """Initialize diagnostic rules for component analysis"""
        return {
            "regime_memory": {
                "health_indicators": ["confidence_score", "similarity_score", "transition_frequency"],
                "performance_weight": 0.3,
                "critical_thresholds": {"confidence_score": 0.2, "transition_frequency": 0.3}
            },
            "tailwind_engine": {
                "health_indicators": ["momentum_consistency", "change_frequency", "component_balance"],
                "performance_weight": 0.25,
                "critical_thresholds": {"change_frequency": 0.4, "momentum_consistency": 0.2}
            },
            "no_edge_detector": {
                "health_indicators": ["activation_frequency", "duration_appropriateness", "trigger_diversity"],
                "performance_weight": 0.2,
                "critical_thresholds": {"activation_frequency": 0.3, "duration_appropriateness": 0.1}
            },
            "anticipatory_allocator": {
                "health_indicators": ["confidence_scores", "accuracy_scores", "position_stability"],
                "performance_weight": 0.25,
                "critical_thresholds": {"confidence_scores": 0.3, "accuracy_scores": 0.4}
            }
        }
    
    def process_monitoring_update(self, 
                                intelligence_snapshot: Phase3IntelligenceSnapshot,
                                dashboard_snapshot: Optional[DashboardSnapshot] = None,
                                attribution_snapshot: Optional[AttributionDisplaySnapshot] = None) -> SystemHealthReport:
        """
        Process monitoring updates and generate alerts/diagnostics
        
        Args:
            intelligence_snapshot: Latest intelligence monitoring snapshot
            dashboard_snapshot: Latest dashboard snapshot (optional)
            attribution_snapshot: Latest attribution snapshot (optional)
            
        Returns:
            Comprehensive system health report
        """
        try:
            timestamp = datetime.now()
            
            # Generate alerts based on current state
            new_alerts = self._generate_alerts(
                intelligence_snapshot, dashboard_snapshot, attribution_snapshot
            )
            
            # Process and store new alerts
            for alert in new_alerts:
                self._process_alert(alert)
            
            # Run diagnostic analysis
            diagnostic_results = self._run_diagnostic_analysis(
                intelligence_snapshot, dashboard_snapshot, attribution_snapshot
            )
            
            # Calculate overall health score
            overall_health = self._calculate_overall_health_score(
                intelligence_snapshot, dashboard_snapshot, attribution_snapshot
            )
            
            # Generate component health scores
            component_health = self._calculate_component_health_scores(intelligence_snapshot)
            
            # Generate performance summary
            performance_summary = self._generate_performance_summary(
                dashboard_snapshot, attribution_snapshot
            )
            
            # Calculate risk indicators
            risk_indicators = self._calculate_risk_indicators(
                intelligence_snapshot, dashboard_snapshot
            )
            
            # Generate system-level recommendations
            recommendations = self._generate_system_recommendations(
                intelligence_snapshot, dashboard_snapshot, attribution_snapshot, diagnostic_results
            )
            
            # Create health report
            health_report = SystemHealthReport(
                timestamp=timestamp,
                overall_health_score=overall_health,
                component_health=component_health,
                active_alerts=list(self.active_alerts.values()),
                diagnostic_results=diagnostic_results,
                performance_summary=performance_summary,
                risk_indicators=risk_indicators,
                recommendations=recommendations
            )
            
            # Store diagnostic results
            self.diagnostic_history.append(health_report)
            
            # Emit system health event
            self.event_bus.emit('system_health_updated', {
                'health_report': health_report,
                'new_alerts': new_alerts,
                'overall_health': overall_health
            })
            
            logger.debug(f"System health processed - Health: {overall_health:.3f}, "
                        f"Active alerts: {len(self.active_alerts)}, "
                        f"New alerts: {len(new_alerts)}")
            
            return health_report
            
        except Exception as e:
            logger.error(f"Error processing monitoring update: {e}")
            raise
    
    def _generate_alerts(self, 
                        intelligence_snapshot: Phase3IntelligenceSnapshot,
                        dashboard_snapshot: Optional[DashboardSnapshot],
                        attribution_snapshot: Optional[AttributionDisplaySnapshot]) -> List[Alert]:
        """Generate alerts based on current system state"""
        alerts = []
        
        try:
            # Regime confidence alerts
            if intelligence_snapshot.regime_state.confidence_score < self.alert_thresholds["regime_confidence"]["critical"]:
                alerts.append(self._create_alert(
                    "regime_confidence_critical",
                    AlertSeverity.CRITICAL,
                    AlertCategory.REGIME,
                    "Critical Regime Confidence",
                    f"Regime confidence critically low: {intelligence_snapshot.regime_state.confidence_score:.3f}",
                    {
                        "current_confidence": intelligence_snapshot.regime_state.confidence_score,
                        "threshold": self.alert_thresholds["regime_confidence"]["critical"],
                        "current_regime": intelligence_snapshot.regime_state.current_regime
                    },
                    [
                        "Review regime classification parameters",
                        "Check market data quality",
                        "Consider regime model recalibration"
                    ],
                    ["regime_memory"]
                ))
            elif intelligence_snapshot.regime_state.confidence_score < self.alert_thresholds["regime_confidence"]["warning"]:
                alerts.append(self._create_alert(
                    "regime_confidence_warning",
                    AlertSeverity.WARNING,
                    AlertCategory.REGIME,
                    "Low Regime Confidence",
                    f"Regime confidence below warning threshold: {intelligence_snapshot.regime_state.confidence_score:.3f}",
                    {
                        "current_confidence": intelligence_snapshot.regime_state.confidence_score,
                        "threshold": self.alert_thresholds["regime_confidence"]["warning"]
                    },
                    ["Monitor regime stability", "Review recent market conditions"],
                    ["regime_memory"]
                ))
            
            # Health score alerts
            if intelligence_snapshot.overall_health_score < self.alert_thresholds["health_score"]["critical"]:
                alerts.append(self._create_alert(
                    "system_health_critical",
                    AlertSeverity.CRITICAL,
                    AlertCategory.SYSTEM,
                    "Critical System Health",
                    f"Overall system health critically low: {intelligence_snapshot.overall_health_score:.3f}",
                    {"health_score": intelligence_snapshot.overall_health_score},
                    ["Immediate system review required", "Check all component health"],
                    ["system"]
                ))
            
            # NO_EDGE duration alerts
            if intelligence_snapshot.no_edge_state.no_edge_duration > self.alert_thresholds["no_edge_duration"]["critical"]:
                alerts.append(self._create_alert(
                    "no_edge_extended_critical",
                    AlertSeverity.CRITICAL,
                    AlertCategory.RISK,
                    "Extended NO_EDGE State",
                    f"NO_EDGE state active for {intelligence_snapshot.no_edge_state.no_edge_duration} periods",
                    {
                        "duration": intelligence_snapshot.no_edge_state.no_edge_duration,
                        "triggers": intelligence_snapshot.no_edge_state.activation_triggers
                    },
                    [
                        "Review NO_EDGE triggers",
                        "Check market conditions",
                        "Consider manual intervention"
                    ],
                    ["no_edge_detector"]
                ))
            
            # Portfolio performance alerts
            if dashboard_snapshot:
                # Drawdown alerts
                if (dashboard_snapshot.performance_metrics.max_drawdown < 
                    -self.alert_thresholds["drawdown"]["critical"]):
                    alerts.append(self._create_alert(
                        "drawdown_critical",
                        AlertSeverity.CRITICAL,
                        AlertCategory.PERFORMANCE,
                        "Critical Drawdown",
                        f"Portfolio drawdown: {dashboard_snapshot.performance_metrics.max_drawdown:.3f}",
                        {"drawdown": dashboard_snapshot.performance_metrics.max_drawdown},
                        ["Review risk management", "Consider position reduction"],
                        ["portfolio"]
                    ))
                
                # Divergence alerts
                if dashboard_snapshot.shadow_vs_live_divergence > self.alert_thresholds["portfolio_divergence"]["critical"]:
                    alerts.append(self._create_alert(
                        "divergence_critical",
                        AlertSeverity.CRITICAL,
                        AlertCategory.PERFORMANCE,
                        "High Portfolio Divergence",
                        f"Shadow vs live divergence: {dashboard_snapshot.shadow_vs_live_divergence:.3f}",
                        {"divergence": dashboard_snapshot.shadow_vs_live_divergence},
                        ["Investigate divergence causes", "Review execution quality"],
                        ["execution"]
                    ))
                
                # Sharpe ratio alerts
                if (dashboard_snapshot.performance_metrics.sharpe_ratio < 
                    self.alert_thresholds["sharpe_ratio"]["critical"]):
                    alerts.append(self._create_alert(
                        "sharpe_critical",
                        AlertSeverity.WARNING,
                        AlertCategory.PERFORMANCE,
                        "Poor Risk-Adjusted Performance",
                        f"Sharpe ratio: {dashboard_snapshot.performance_metrics.sharpe_ratio:.2f}",
                        {"sharpe_ratio": dashboard_snapshot.performance_metrics.sharpe_ratio},
                        ["Review strategy performance", "Analyze risk factors"],
                        ["strategy"]
                    ))
            
            # Attribution quality alerts
            if attribution_snapshot:
                if (attribution_snapshot.attribution_breakdown.attribution_quality_score < 
                    self.alert_thresholds["attribution_quality"]["critical"]):
                    alerts.append(self._create_alert(
                        "attribution_quality_critical",
                        AlertSeverity.WARNING,
                        AlertCategory.ATTRIBUTION,
                        "Poor Attribution Quality",
                        f"Attribution quality: {attribution_snapshot.attribution_breakdown.attribution_quality_score:.3f}",
                        {
                            "quality_score": attribution_snapshot.attribution_breakdown.attribution_quality_score,
                            "unexplained_alpha": attribution_snapshot.attribution_breakdown.unexplained_alpha
                        },
                        ["Review attribution model", "Check component contributions"],
                        ["attribution"]
                    ))
            
            # Intelligence anomaly alerts
            for anomaly in intelligence_snapshot.anomaly_flags:
                alerts.append(self._create_alert(
                    f"intelligence_anomaly_{hash(anomaly)}",
                    AlertSeverity.WARNING,
                    AlertCategory.COMPONENT,
                    "Intelligence Anomaly Detected",
                    f"Anomaly: {anomaly}",
                    {"anomaly_description": anomaly},
                    ["Investigate anomaly cause", "Monitor component behavior"],
                    ["intelligence"]
                ))
            
        except Exception as e:
            logger.warning(f"Error generating alerts: {e}")
        
        return alerts
    
    def _create_alert(self, 
                     alert_id: str,
                     severity: AlertSeverity,
                     category: AlertCategory,
                     title: str,
                     message: str,
                     details: Dict[str, Any],
                     recommendations: List[str],
                     affected_components: List[str]) -> Alert:
        """Create a new alert"""
        return Alert(
            id=alert_id,
            timestamp=datetime.now(),
            severity=severity,
            category=category,
            title=title,
            message=message,
            details=details,
            recommendations=recommendations,
            affected_components=affected_components,
            auto_resolve=category in [AlertCategory.PERFORMANCE, AlertCategory.SYSTEM]
        )
    
    def _process_alert(self, alert: Alert):
        """Process and store a new alert"""
        try:
            # Check for alert suppression
            if self._is_alert_suppressed(alert):
                return
            
            # Add to active alerts
            self.active_alerts[alert.id] = alert
            
            # Add to history
            self.alert_history.append(alert)
            
            # Update statistics
            self.total_alerts_generated += 1
            self.alerts_by_category[alert.category.value] += 1
            self.alerts_by_severity[alert.severity.value] += 1
            
            # Set suppression
            self.alert_suppression[alert.id] = alert.timestamp
            
            # Execute custom handlers
            if alert.category.value in self.custom_alert_handlers:
                try:
                    self.custom_alert_handlers[alert.category.value](alert)
                except Exception as e:
                    logger.warning(f"Error in custom alert handler: {e}")
            
            # Emit alert event
            self.event_bus.emit('alert_generated', {
                'alert': alert,
                'severity': alert.severity.value,
                'category': alert.category.value
            })
            
            logger.info(f"Alert generated: {alert.severity.value} - {alert.title}")
            
        except Exception as e:
            logger.error(f"Error processing alert: {e}")
    
    def _is_alert_suppressed(self, alert: Alert) -> bool:
        """Check if alert should be suppressed due to rate limiting"""
        if alert.id in self.alert_suppression:
            last_alert_time = self.alert_suppression[alert.id]
            if datetime.now() - last_alert_time < self.suppression_duration:
                return True
        return False
    
    def _run_diagnostic_analysis(self, 
                               intelligence_snapshot: Phase3IntelligenceSnapshot,
                               dashboard_snapshot: Optional[DashboardSnapshot],
                               attribution_snapshot: Optional[AttributionDisplaySnapshot]) -> List[DiagnosticResult]:
        """Run comprehensive diagnostic analysis on all components"""
        diagnostic_results = []
        
        try:
            # Diagnose regime memory system
            regime_diagnostic = self._diagnose_regime_memory(intelligence_snapshot)
            diagnostic_results.append(regime_diagnostic)
            
            # Diagnose tailwind engine
            tailwind_diagnostic = self._diagnose_tailwind_engine(intelligence_snapshot)
            diagnostic_results.append(tailwind_diagnostic)
            
            # Diagnose NO_EDGE detector
            no_edge_diagnostic = self._diagnose_no_edge_detector(intelligence_snapshot)
            diagnostic_results.append(no_edge_diagnostic)
            
            # Diagnose anticipatory allocator
            anticipatory_diagnostic = self._diagnose_anticipatory_allocator(intelligence_snapshot)
            diagnostic_results.append(anticipatory_diagnostic)
            
            # Diagnose portfolio performance (if available)
            if dashboard_snapshot:
                portfolio_diagnostic = self._diagnose_portfolio_performance(dashboard_snapshot)
                diagnostic_results.append(portfolio_diagnostic)
            
            # Diagnose attribution quality (if available)
            if attribution_snapshot:
                attribution_diagnostic = self._diagnose_attribution_quality(attribution_snapshot)
                diagnostic_results.append(attribution_diagnostic)
            
        except Exception as e:
            logger.warning(f"Error running diagnostic analysis: {e}")
        
        return diagnostic_results
    
    def _diagnose_regime_memory(self, intelligence_snapshot: Phase3IntelligenceSnapshot) -> DiagnosticResult:
        """Diagnose regime memory system health"""
        try:
            regime_state = intelligence_snapshot.regime_state
            
            # Calculate health score
            confidence_score = regime_state.confidence_score
            similarity_score = regime_state.similarity_score
            transition_frequency = regime_state.transition_frequency
            
            # Health indicators
            health_indicators = [confidence_score, similarity_score, 1.0 - min(transition_frequency, 1.0)]
            health_score = np.mean(health_indicators)
            
            # Detect issues
            issues = []
            if confidence_score < 0.3:
                issues.append("Low regime classification confidence")
            if similarity_score < 0.4:
                issues.append("Poor regime similarity matching")
            if transition_frequency > 0.3:
                issues.append("Excessive regime transitions")
            
            # Performance impact (simplified)
            performance_impact = 1.0 - health_score
            
            # Recommendations
            recommendations = []
            if confidence_score < 0.3:
                recommendations.append("Recalibrate regime classification parameters")
            if similarity_score < 0.4:
                recommendations.append("Review regime similarity calculation")
            if transition_frequency > 0.3:
                recommendations.append("Increase regime stability thresholds")
            
            return DiagnosticResult(
                component_name="regime_memory",
                health_score=health_score,
                issues_detected=issues,
                performance_impact=performance_impact,
                confidence_level=confidence_score,
                recommendations=recommendations,
                detailed_analysis={
                    "confidence_score": confidence_score,
                    "similarity_score": similarity_score,
                    "transition_frequency": transition_frequency,
                    "regime_duration": regime_state.regime_duration
                },
                trend_analysis={"confidence": "stable"}  # Simplified
            )
            
        except Exception as e:
            logger.warning(f"Error diagnosing regime memory: {e}")
            return DiagnosticResult(
                component_name="regime_memory",
                health_score=0.0,
                issues_detected=["Diagnostic error"],
                performance_impact=1.0,
                confidence_level=0.0,
                recommendations=["Check regime memory system"],
                detailed_analysis={},
                trend_analysis={}
            )
    
    def _diagnose_tailwind_engine(self, intelligence_snapshot: Phase3IntelligenceSnapshot) -> DiagnosticResult:
        """Diagnose tailwind engine health"""
        try:
            tailwind_state = intelligence_snapshot.tailwind_state
            
            # Calculate health indicators
            momentum_consistency = 0.8  # Placeholder - would calculate from momentum history
            change_frequency = tailwind_state.change_frequency
            component_balance = 0.7  # Placeholder - would calculate from component distribution
            
            health_indicators = [momentum_consistency, 1.0 - min(change_frequency, 1.0), component_balance]
            health_score = np.mean(health_indicators)
            
            # Detect issues
            issues = []
            if change_frequency > 0.4:
                issues.append("High tailwind change frequency")
            if momentum_consistency < 0.5:
                issues.append("Inconsistent tailwind momentum")
            if component_balance < 0.5:
                issues.append("Unbalanced component contributions")
            
            # Performance impact
            performance_impact = change_frequency * 0.5  # High change frequency impacts performance
            
            # Recommendations
            recommendations = []
            if change_frequency > 0.4:
                recommendations.append("Increase tailwind stability parameters")
            if momentum_consistency < 0.5:
                recommendations.append("Review momentum calculation methodology")
            
            return DiagnosticResult(
                component_name="tailwind_engine",
                health_score=health_score,
                issues_detected=issues,
                performance_impact=performance_impact,
                confidence_level=momentum_consistency,
                recommendations=recommendations,
                detailed_analysis={
                    "change_frequency": change_frequency,
                    "momentum_consistency": momentum_consistency,
                    "component_balance": component_balance,
                    "current_tailwinds": dict(tailwind_state.current_tailwinds)
                },
                trend_analysis={"momentum": "stable"}
            )
            
        except Exception as e:
            logger.warning(f"Error diagnosing tailwind engine: {e}")
            return DiagnosticResult(
                component_name="tailwind_engine",
                health_score=0.0,
                issues_detected=["Diagnostic error"],
                performance_impact=1.0,
                confidence_level=0.0,
                recommendations=["Check tailwind engine system"],
                detailed_analysis={},
                trend_analysis={}
            )
    
    def _diagnose_no_edge_detector(self, intelligence_snapshot: Phase3IntelligenceSnapshot) -> DiagnosticResult:
        """Diagnose NO_EDGE detector health"""
        try:
            no_edge_state = intelligence_snapshot.no_edge_state
            
            # Calculate health indicators
            activation_frequency = no_edge_state.no_edge_frequency
            duration_appropriateness = 1.0 - min(no_edge_state.no_edge_duration / 20.0, 1.0)  # Penalize long durations
            trigger_diversity = len(set(no_edge_state.activation_triggers)) / max(len(no_edge_state.activation_triggers), 1)
            
            health_indicators = [1.0 - min(activation_frequency, 1.0), duration_appropriateness, trigger_diversity]
            health_score = np.mean(health_indicators)
            
            # Detect issues
            issues = []
            if activation_frequency > 0.3:
                issues.append("Excessive NO_EDGE activations")
            if no_edge_state.no_edge_duration > 15:
                issues.append("Extended NO_EDGE duration")
            if trigger_diversity < 0.3:
                issues.append("Limited trigger diversity")
            
            # Performance impact
            performance_impact = activation_frequency * 0.3 + (no_edge_state.no_edge_duration / 20.0) * 0.2
            
            # Recommendations
            recommendations = []
            if activation_frequency > 0.3:
                recommendations.append("Review NO_EDGE trigger sensitivity")
            if no_edge_state.no_edge_duration > 15:
                recommendations.append("Implement automatic NO_EDGE exit conditions")
            
            return DiagnosticResult(
                component_name="no_edge_detector",
                health_score=health_score,
                issues_detected=issues,
                performance_impact=performance_impact,
                confidence_level=duration_appropriateness,
                recommendations=recommendations,
                detailed_analysis={
                    "activation_frequency": activation_frequency,
                    "current_duration": no_edge_state.no_edge_duration,
                    "is_active": no_edge_state.is_no_edge,
                    "trigger_frequency": dict(no_edge_state.trigger_frequency)
                },
                trend_analysis={"activation": "stable"}
            )
            
        except Exception as e:
            logger.warning(f"Error diagnosing NO_EDGE detector: {e}")
            return DiagnosticResult(
                component_name="no_edge_detector",
                health_score=0.0,
                issues_detected=["Diagnostic error"],
                performance_impact=1.0,
                confidence_level=0.0,
                recommendations=["Check NO_EDGE detector system"],
                detailed_analysis={},
                trend_analysis={}
            )
    
    def _diagnose_anticipatory_allocator(self, intelligence_snapshot: Phase3IntelligenceSnapshot) -> DiagnosticResult:
        """Diagnose anticipatory allocator health"""
        try:
            anticipatory_state = intelligence_snapshot.anticipatory_state
            
            # Calculate health indicators
            avg_confidence = np.mean(list(anticipatory_state.confidence_scores.values())) if anticipatory_state.confidence_scores else 0.0
            avg_accuracy = np.mean(list(anticipatory_state.accuracy_scores.values())) if anticipatory_state.accuracy_scores else 0.0
            position_stability = 0.7  # Placeholder - would calculate from position change history
            
            health_indicators = [avg_confidence, avg_accuracy, position_stability]
            health_score = np.mean(health_indicators)
            
            # Detect issues
            issues = []
            if avg_confidence < 0.4:
                issues.append("Low anticipatory confidence")
            if avg_accuracy < 0.5:
                issues.append("Poor anticipatory accuracy")
            if position_stability < 0.5:
                issues.append("Unstable position allocations")
            
            # Performance impact
            performance_impact = (1.0 - avg_confidence) * 0.4 + (1.0 - avg_accuracy) * 0.4
            
            # Recommendations
            recommendations = []
            if avg_confidence < 0.4:
                recommendations.append("Review anticipatory signal generation")
            if avg_accuracy < 0.5:
                recommendations.append("Recalibrate anticipatory models")
            
            return DiagnosticResult(
                component_name="anticipatory_allocator",
                health_score=health_score,
                issues_detected=issues,
                performance_impact=performance_impact,
                confidence_level=avg_confidence,
                recommendations=recommendations,
                detailed_analysis={
                    "avg_confidence": avg_confidence,
                    "avg_accuracy": avg_accuracy,
                    "position_stability": position_stability,
                    "current_positions": dict(anticipatory_state.current_positions)
                },
                trend_analysis={"confidence": "stable", "accuracy": "stable"}
            )
            
        except Exception as e:
            logger.warning(f"Error diagnosing anticipatory allocator: {e}")
            return DiagnosticResult(
                component_name="anticipatory_allocator",
                health_score=0.0,
                issues_detected=["Diagnostic error"],
                performance_impact=1.0,
                confidence_level=0.0,
                recommendations=["Check anticipatory allocator system"],
                detailed_analysis={},
                trend_analysis={}
            )
    
    def _diagnose_portfolio_performance(self, dashboard_snapshot: DashboardSnapshot) -> DiagnosticResult:
        """Diagnose portfolio performance health"""
        try:
            perf_metrics = dashboard_snapshot.performance_metrics
            
            # Calculate health indicators
            return_health = max(0.0, min(1.0, (perf_metrics.total_return + 0.2) / 0.4))  # Scale -20% to +20%
            sharpe_health = max(0.0, min(1.0, (perf_metrics.sharpe_ratio + 1.0) / 2.0))  # Scale -1 to +1
            drawdown_health = max(0.0, 1.0 + perf_metrics.max_drawdown / 0.2)  # Scale 0% to -20%
            
            health_indicators = [return_health, sharpe_health, drawdown_health]
            health_score = np.mean(health_indicators)
            
            # Detect issues
            issues = []
            if perf_metrics.total_return < -0.1:
                issues.append("Negative portfolio returns")
            if perf_metrics.sharpe_ratio < 0:
                issues.append("Negative risk-adjusted returns")
            if perf_metrics.max_drawdown < -0.15:
                issues.append("High portfolio drawdown")
            if perf_metrics.win_rate < 0.4:
                issues.append("Low win rate")
            
            # Performance impact is direct
            performance_impact = max(0.0, -perf_metrics.total_return)
            
            # Recommendations
            recommendations = []
            if perf_metrics.sharpe_ratio < 0:
                recommendations.append("Review risk management parameters")
            if perf_metrics.max_drawdown < -0.15:
                recommendations.append("Implement stricter position sizing")
            if perf_metrics.win_rate < 0.4:
                recommendations.append("Analyze losing trades for patterns")
            
            return DiagnosticResult(
                component_name="portfolio_performance",
                health_score=health_score,
                issues_detected=issues,
                performance_impact=performance_impact,
                confidence_level=sharpe_health,
                recommendations=recommendations,
                detailed_analysis={
                    "total_return": perf_metrics.total_return,
                    "sharpe_ratio": perf_metrics.sharpe_ratio,
                    "max_drawdown": perf_metrics.max_drawdown,
                    "win_rate": perf_metrics.win_rate,
                    "volatility": perf_metrics.volatility
                },
                trend_analysis={"performance": "stable"}
            )
            
        except Exception as e:
            logger.warning(f"Error diagnosing portfolio performance: {e}")
            return DiagnosticResult(
                component_name="portfolio_performance",
                health_score=0.0,
                issues_detected=["Diagnostic error"],
                performance_impact=1.0,
                confidence_level=0.0,
                recommendations=["Check portfolio performance system"],
                detailed_analysis={},
                trend_analysis={}
            )
    
    def _diagnose_attribution_quality(self, attribution_snapshot: AttributionDisplaySnapshot) -> DiagnosticResult:
        """Diagnose attribution quality health"""
        try:
            attribution = attribution_snapshot.attribution_breakdown
            
            # Calculate health indicators
            quality_score = attribution.attribution_quality_score
            explained_ratio = 1.0 - abs(attribution.unexplained_alpha) / max(abs(attribution.total_return), 0.001)
            confidence_correlation = attribution_snapshot.confidence_correlation.overall_correlation
            
            health_indicators = [quality_score, explained_ratio, abs(confidence_correlation)]
            health_score = np.mean(health_indicators)
            
            # Detect issues
            issues = []
            if quality_score < 0.5:
                issues.append("Poor attribution quality")
            if abs(attribution.unexplained_alpha) > 0.05:
                issues.append("High unexplained alpha")
            if abs(confidence_correlation) < 0.2:
                issues.append("Weak confidence-performance correlation")
            
            # Performance impact
            performance_impact = abs(attribution.unexplained_alpha)
            
            # Recommendations
            recommendations = []
            if quality_score < 0.5:
                recommendations.append("Review attribution model parameters")
            if abs(attribution.unexplained_alpha) > 0.05:
                recommendations.append("Investigate sources of unexplained alpha")
            
            return DiagnosticResult(
                component_name="attribution_quality",
                health_score=health_score,
                issues_detected=issues,
                performance_impact=performance_impact,
                confidence_level=quality_score,
                recommendations=recommendations,
                detailed_analysis={
                    "quality_score": quality_score,
                    "unexplained_alpha": attribution.unexplained_alpha,
                    "confidence_correlation": confidence_correlation,
                    "regime_attribution": dict(attribution.regime_attribution),
                    "component_attribution": dict(attribution.component_attribution)
                },
                trend_analysis={"quality": "stable"}
            )
            
        except Exception as e:
            logger.warning(f"Error diagnosing attribution quality: {e}")
            return DiagnosticResult(
                component_name="attribution_quality",
                health_score=0.0,
                issues_detected=["Diagnostic error"],
                performance_impact=1.0,
                confidence_level=0.0,
                recommendations=["Check attribution quality system"],
                detailed_analysis={},
                trend_analysis={}
            )
    
    def _calculate_overall_health_score(self, 
                                      intelligence_snapshot: Phase3IntelligenceSnapshot,
                                      dashboard_snapshot: Optional[DashboardSnapshot],
                                      attribution_snapshot: Optional[AttributionDisplaySnapshot]) -> float:
        """Calculate overall system health score"""
        try:
            health_components = []
            
            # Intelligence health (40% weight)
            intelligence_health = intelligence_snapshot.overall_health_score
            health_components.append((intelligence_health, 0.4))
            
            # Portfolio performance health (30% weight)
            if dashboard_snapshot:
                perf_health = max(0.0, min(1.0, (dashboard_snapshot.performance_metrics.sharpe_ratio + 1.0) / 2.0))
                health_components.append((perf_health, 0.3))
            
            # Attribution quality health (20% weight)
            if attribution_snapshot:
                attr_health = attribution_snapshot.attribution_breakdown.attribution_quality_score
                health_components.append((attr_health, 0.2))
            
            # Risk health (10% weight)
            risk_health = 1.0  # Default
            if dashboard_snapshot:
                risk_health = max(0.0, 1.0 + dashboard_snapshot.performance_metrics.max_drawdown / 0.2)
            health_components.append((risk_health, 0.1))
            
            # Calculate weighted average
            total_weight = sum(weight for _, weight in health_components)
            if total_weight > 0:
                weighted_health = sum(health * weight for health, weight in health_components) / total_weight
            else:
                weighted_health = 0.5
            
            return max(0.0, min(1.0, weighted_health))
            
        except Exception as e:
            logger.warning(f"Error calculating overall health score: {e}")
            return 0.0
    
    def _calculate_component_health_scores(self, intelligence_snapshot: Phase3IntelligenceSnapshot) -> Dict[str, float]:
        """Calculate individual component health scores"""
        try:
            component_health = {}
            
            # Regime memory health
            regime_confidence = intelligence_snapshot.regime_state.confidence_score
            regime_stability = 1.0 - min(intelligence_snapshot.regime_state.transition_frequency, 1.0)
            component_health["regime_memory"] = np.mean([regime_confidence, regime_stability])
            
            # Tailwind engine health
            tailwind_consistency = 0.8  # Placeholder
            tailwind_balance = 0.7  # Placeholder
            component_health["tailwind_engine"] = np.mean([tailwind_consistency, tailwind_balance])
            
            # NO_EDGE detector health
            no_edge_frequency = intelligence_snapshot.no_edge_state.no_edge_frequency
            no_edge_appropriateness = 1.0 - min(no_edge_frequency, 1.0)
            component_health["no_edge_detector"] = no_edge_appropriateness
            
            # Anticipatory allocator health
            if intelligence_snapshot.anticipatory_state.confidence_scores:
                anticipatory_confidence = np.mean(list(intelligence_snapshot.anticipatory_state.confidence_scores.values()))
                component_health["anticipatory_allocator"] = anticipatory_confidence
            else:
                component_health["anticipatory_allocator"] = 0.5
            
            return component_health
            
        except Exception as e:
            logger.warning(f"Error calculating component health scores: {e}")
            return {}
    
    def _generate_performance_summary(self, 
                                    dashboard_snapshot: Optional[DashboardSnapshot],
                                    attribution_snapshot: Optional[AttributionDisplaySnapshot]) -> Dict[str, float]:
        """Generate performance summary metrics"""
        try:
            summary = {}
            
            if dashboard_snapshot:
                summary.update({
                    "total_return": dashboard_snapshot.performance_metrics.total_return,
                    "sharpe_ratio": dashboard_snapshot.performance_metrics.sharpe_ratio,
                    "max_drawdown": dashboard_snapshot.performance_metrics.max_drawdown,
                    "volatility": dashboard_snapshot.performance_metrics.volatility,
                    "win_rate": dashboard_snapshot.performance_metrics.win_rate
                })
            
            if attribution_snapshot:
                summary.update({
                    "attribution_quality": attribution_snapshot.attribution_breakdown.attribution_quality_score,
                    "unexplained_alpha": attribution_snapshot.attribution_breakdown.unexplained_alpha,
                    "confidence_correlation": attribution_snapshot.confidence_correlation.overall_correlation
                })
            
            return summary
            
        except Exception as e:
            logger.warning(f"Error generating performance summary: {e}")
            return {}
    
    def _calculate_risk_indicators(self, 
                                 intelligence_snapshot: Phase3IntelligenceSnapshot,
                                 dashboard_snapshot: Optional[DashboardSnapshot]) -> Dict[str, float]:
        """Calculate risk indicator metrics"""
        try:
            indicators = {}
            
            # Intelligence-based risk indicators
            indicators["regime_confidence_risk"] = 1.0 - intelligence_snapshot.regime_state.confidence_score
            indicators["no_edge_frequency_risk"] = intelligence_snapshot.no_edge_state.no_edge_frequency
            indicators["system_health_risk"] = 1.0 - intelligence_snapshot.overall_health_score
            
            # Portfolio-based risk indicators
            if dashboard_snapshot:
                indicators["drawdown_risk"] = abs(dashboard_snapshot.performance_metrics.max_drawdown)
                indicators["volatility_risk"] = dashboard_snapshot.performance_metrics.volatility
                indicators["divergence_risk"] = dashboard_snapshot.shadow_vs_live_divergence
            
            return indicators
            
        except Exception as e:
            logger.warning(f"Error calculating risk indicators: {e}")
            return {}
    
    def _generate_system_recommendations(self, 
                                       intelligence_snapshot: Phase3IntelligenceSnapshot,
                                       dashboard_snapshot: Optional[DashboardSnapshot],
                                       attribution_snapshot: Optional[AttributionDisplaySnapshot],
                                       diagnostic_results: List[DiagnosticResult]) -> List[str]:
        """Generate system-level recommendations"""
        recommendations = []
        
        try:
            # High-priority recommendations based on critical issues
            critical_components = [dr for dr in diagnostic_results if dr.health_score < 0.3]
            
            if critical_components:
                recommendations.append("URGENT: Critical component health detected - immediate review required")
                for component in critical_components:
                    recommendations.extend(component.recommendations[:2])  # Top 2 recommendations
            
            # Performance-based recommendations
            if dashboard_snapshot and dashboard_snapshot.performance_metrics.sharpe_ratio < 0:
                recommendations.append("Review overall strategy performance and risk management")
            
            # Attribution-based recommendations
            if (attribution_snapshot and 
                attribution_snapshot.attribution_breakdown.attribution_quality_score < 0.5):
                recommendations.append("Improve attribution model quality and component analysis")
            
            # Intelligence-based recommendations
            if intelligence_snapshot.overall_health_score < 0.4:
                recommendations.append("Comprehensive Phase 3 intelligence system review needed")
            
            # Limit to top 5 recommendations
            return recommendations[:5]
            
        except Exception as e:
            logger.warning(f"Error generating system recommendations: {e}")
            return ["System diagnostic error - manual review required"]
    
    def get_alert_summary(self) -> Dict[str, Any]:
        """Get comprehensive alert summary"""
        try:
            return {
                "active_alerts": len(self.active_alerts),
                "total_alerts_generated": self.total_alerts_generated,
                "alerts_by_severity": dict(self.alerts_by_severity),
                "alerts_by_category": dict(self.alerts_by_category),
                "recent_alerts": [
                    {
                        "id": alert.id,
                        "timestamp": alert.timestamp.isoformat(),
                        "severity": alert.severity.value,
                        "category": alert.category.value,
                        "title": alert.title,
                        "message": alert.message
                    }
                    for alert in list(self.alert_history)[-10:]
                ],
                "critical_alerts": [
                    {
                        "id": alert.id,
                        "title": alert.title,
                        "message": alert.message,
                        "recommendations": alert.recommendations
                    }
                    for alert in self.active_alerts.values()
                    if alert.severity == AlertSeverity.CRITICAL
                ]
            }
            
        except Exception as e:
            logger.error(f"Error generating alert summary: {e}")
            return {"error": str(e)}
    
    def resolve_alert(self, alert_id: str, resolution_note: str = ""):
        """Manually resolve an alert"""
        try:
            if alert_id in self.active_alerts:
                alert = self.active_alerts[alert_id]
                alert.resolved = True
                alert.resolution_timestamp = datetime.now()
                
                # Remove from active alerts
                del self.active_alerts[alert_id]
                
                # Emit resolution event
                self.event_bus.emit('alert_resolved', {
                    'alert_id': alert_id,
                    'resolution_note': resolution_note,
                    'resolved_by': 'manual'
                })
                
                logger.info(f"Alert resolved: {alert_id}")
                
        except Exception as e:
            logger.error(f"Error resolving alert {alert_id}: {e}")
    
    def add_custom_alert_handler(self, category: str, handler: Callable[[Alert], None]):
        """Add custom alert handler for specific category"""
        self.custom_alert_handlers[category] = handler
        logger.info(f"Custom alert handler added for category: {category}")
    
    def reset_system(self):
        """Reset alert and diagnostic system (for testing)"""
        self.active_alerts.clear()
        self.alert_history.clear()
        self.diagnostic_history.clear()
        self.alert_suppression.clear()
        
        self.total_alerts_generated = 0
        self.alerts_by_category.clear()
        self.alerts_by_severity.clear()
        
        logger.info("Alert and diagnostic system reset")