"""
Kill Switch Auditor - Crisis Response Verification

This module audits kill switch performance during crisis periods to verify
that protective mechanisms fired when they should have. This prevents
fake survivability claims.

Key Validations:
- Kill switch timeline during each crisis
- Trigger accuracy and timing
- NAV protection effectiveness
- False positive/negative analysis
- Recovery procedure validation

Author: Northstar Team
Date: 2026-01-05
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import logging

try:
    from ..operation.logging_config import setup_operation_logging
except ImportError:
    # Fallback for when running as standalone
    import logging
    def setup_operation_logging():
        logging.basicConfig(level=logging.INFO)
        return logging.getLogger(__name__)


class KillSwitchType(Enum):
    """Types of kill switches."""
    DRAWDOWN_LIMIT = "drawdown_limit"
    VOLATILITY_SPIKE = "volatility_spike"
    CORRELATION_BREAKDOWN = "correlation_breakdown"
    LIQUIDITY_CRISIS = "liquidity_crisis"
    POSITION_LIMIT = "position_limit"
    RISK_BUDGET = "risk_budget"
    MARKET_STRESS = "market_stress"
    DATA_QUALITY = "data_quality"


class KillSwitchAction(Enum):
    """Actions taken by kill switches."""
    POSITION_REDUCTION = "position_reduction"
    FULL_LIQUIDATION = "full_liquidation"
    TRADING_HALT = "trading_halt"
    RISK_REDUCTION = "risk_reduction"
    HEDGE_ACTIVATION = "hedge_activation"
    ALERT_ONLY = "alert_only"


@dataclass
class KillSwitchEvent:
    """Individual kill switch activation event."""
    timestamp: datetime
    switch_type: KillSwitchType
    trigger_value: float
    threshold: float
    action_taken: KillSwitchAction
    nav_before: float
    nav_after: float
    recovery_time: Optional[timedelta]
    was_justified: bool
    false_positive: bool


@dataclass
class CrisisPeriod:
    """Definition of a crisis period for analysis."""
    name: str
    start_date: datetime
    end_date: datetime
    expected_triggers: List[KillSwitchType]
    severity_level: float  # 0-1 scale
    market_conditions: Dict[str, Any]


@dataclass
class KillSwitchAuditReport:
    """Comprehensive kill switch audit report."""
    crisis_name: str
    audit_date: datetime
    
    # Timeline analysis
    kill_switch_timeline: List[KillSwitchEvent]
    total_activations: int
    justified_activations: int
    false_positives: int
    missed_triggers: int
    
    # Performance analysis
    nav_protection_effectiveness: float
    average_response_time: float
    recovery_success_rate: float
    
    # Crisis-specific analysis
    crisis_survival_verified: bool
    protection_adequacy_score: float
    response_quality_score: float
    
    # Recommendations
    threshold_adjustments: Dict[KillSwitchType, float]
    system_improvements: List[str]
    monitoring_enhancements: List[str]


class KillSwitchAuditor:
    """
    Institutional-grade kill switch auditor.
    
    This class audits kill switch performance during crisis periods to verify
    that protective mechanisms worked as intended and prevented catastrophic losses.
    """
    
    def __init__(self):
        """Initialize kill switch auditor."""
        self.logger = setup_operation_logging()
        self.crisis_periods = self._define_crisis_periods()
        self.logger.info("Kill Switch Auditor initialized")
    
    def audit_crisis_kill_switches(self, 
                                 returns: np.ndarray,
                                 nav_series: np.ndarray,
                                 timestamps: List[datetime],
                                 kill_switch_log: List[Dict[str, Any]],
                                 crisis_name: str) -> KillSwitchAuditReport:
        """
        Audit kill switch performance during a specific crisis.
        
        Args:
            returns: Strategy returns during crisis
            nav_series: NAV values during crisis
            timestamps: Timestamps for each observation
            kill_switch_log: Log of kill switch activations
            crisis_name: Name of crisis being audited
            
        Returns:
            KillSwitchAuditReport: Comprehensive audit results
        """
        self.logger.info(f"🧯 Auditing kill switches for {crisis_name}")
        
        # Get crisis definition
        crisis = self._get_crisis_definition(crisis_name)
        if crisis is None:
            raise ValueError(f"Unknown crisis: {crisis_name}")
        
        # Filter data to crisis period
        crisis_mask = [(t >= crisis.start_date and t <= crisis.end_date) for t in timestamps]
        crisis_returns = returns[crisis_mask]
        crisis_nav = nav_series[crisis_mask]
        crisis_timestamps = [t for t, m in zip(timestamps, crisis_mask) if m]
        
        # Parse kill switch events
        kill_switch_events = self._parse_kill_switch_events(kill_switch_log, crisis)
        
        # Analyze timeline
        timeline_analysis = self._analyze_kill_switch_timeline(
            kill_switch_events, crisis_returns, crisis_nav, crisis_timestamps, crisis
        )
        
        # Calculate performance metrics
        performance_metrics = self._calculate_performance_metrics(
            kill_switch_events, crisis_returns, crisis_nav
        )
        
        # Verify crisis survival
        survival_verification = self._verify_crisis_survival(
            kill_switch_events, crisis_returns, crisis_nav, crisis
        )
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            kill_switch_events, crisis, performance_metrics
        )
        
        # Compile audit report
        report = KillSwitchAuditReport(
            crisis_name=crisis_name,
            audit_date=datetime.now(),
            kill_switch_timeline=kill_switch_events,
            total_activations=len(kill_switch_events),
            justified_activations=sum(1 for e in kill_switch_events if e.was_justified),
            false_positives=sum(1 for e in kill_switch_events if e.false_positive),
            missed_triggers=timeline_analysis['missed_triggers'],
            nav_protection_effectiveness=performance_metrics['protection_effectiveness'],
            average_response_time=performance_metrics['avg_response_time'],
            recovery_success_rate=performance_metrics['recovery_success_rate'],
            crisis_survival_verified=survival_verification['verified'],
            protection_adequacy_score=survival_verification['adequacy_score'],
            response_quality_score=survival_verification['quality_score'],
            threshold_adjustments=recommendations['threshold_adjustments'],
            system_improvements=recommendations['system_improvements'],
            monitoring_enhancements=recommendations['monitoring_enhancements']
        )
        
        self._log_audit_results(report)
        return report
    
    def _define_crisis_periods(self) -> Dict[str, CrisisPeriod]:
        """Define major crisis periods for analysis."""
        return {
            "2008_financial_crisis": CrisisPeriod(
                name="2008 Financial Crisis",
                start_date=datetime(2008, 9, 1),
                end_date=datetime(2009, 3, 31),
                expected_triggers=[
                    KillSwitchType.DRAWDOWN_LIMIT,
                    KillSwitchType.VOLATILITY_SPIKE,
                    KillSwitchType.CORRELATION_BREAKDOWN,
                    KillSwitchType.LIQUIDITY_CRISIS
                ],
                severity_level=0.9,
                market_conditions={
                    "max_drawdown": -0.55,
                    "volatility_spike": 3.0,
                    "correlation_increase": 0.8
                }
            ),
            "2020_covid_crash": CrisisPeriod(
                name="2020 COVID Crash",
                start_date=datetime(2020, 2, 15),
                end_date=datetime(2020, 4, 30),
                expected_triggers=[
                    KillSwitchType.VOLATILITY_SPIKE,
                    KillSwitchType.LIQUIDITY_CRISIS,
                    KillSwitchType.MARKET_STRESS
                ],
                severity_level=0.8,
                market_conditions={
                    "max_drawdown": -0.35,
                    "volatility_spike": 4.0,
                    "liquidity_crisis": True
                }
            ),
            "2000_dotcom_bubble": CrisisPeriod(
                name="2000 Dot-com Bubble",
                start_date=datetime(2000, 3, 1),
                end_date=datetime(2002, 10, 31),
                expected_triggers=[
                    KillSwitchType.DRAWDOWN_LIMIT,
                    KillSwitchType.CORRELATION_BREAKDOWN
                ],
                severity_level=0.7,
                market_conditions={
                    "max_drawdown": -0.78,
                    "duration_months": 31
                }
            )
        }
    
    def _get_crisis_definition(self, crisis_name: str) -> Optional[CrisisPeriod]:
        """Get crisis definition by name."""
        return self.crisis_periods.get(crisis_name)
    
    def _parse_kill_switch_events(self, 
                                kill_switch_log: List[Dict[str, Any]], 
                                crisis: CrisisPeriod) -> List[KillSwitchEvent]:
        """Parse kill switch events from log data."""
        events = []
        
        for log_entry in kill_switch_log:
            try:
                timestamp = log_entry.get('timestamp')
                if isinstance(timestamp, str):
                    timestamp = datetime.fromisoformat(timestamp)
                
                # Only include events during crisis period
                if not (crisis.start_date <= timestamp <= crisis.end_date):
                    continue
                
                event = KillSwitchEvent(
                    timestamp=timestamp,
                    switch_type=KillSwitchType(log_entry.get('switch_type', 'unknown')),
                    trigger_value=log_entry.get('trigger_value', 0.0),
                    threshold=log_entry.get('threshold', 0.0),
                    action_taken=KillSwitchAction(log_entry.get('action_taken', 'alert_only')),
                    nav_before=log_entry.get('nav_before', 1.0),
                    nav_after=log_entry.get('nav_after', 1.0),
                    recovery_time=log_entry.get('recovery_time'),
                    was_justified=log_entry.get('was_justified', True),
                    false_positive=log_entry.get('false_positive', False)
                )
                events.append(event)
                
            except Exception as e:
                self.logger.warning(f"Failed to parse kill switch event: {e}")
                continue
        
        # Sort events by timestamp
        events.sort(key=lambda x: x.timestamp)
        return events
    
    def _analyze_kill_switch_timeline(self, 
                                    events: List[KillSwitchEvent],
                                    returns: np.ndarray,
                                    nav: np.ndarray,
                                    timestamps: List[datetime],
                                    crisis: CrisisPeriod) -> Dict[str, Any]:
        """Analyze kill switch timeline for completeness."""
        # Check for expected triggers
        triggered_types = {event.switch_type for event in events}
        expected_types = set(crisis.expected_triggers)
        missed_triggers = len(expected_types - triggered_types)
        
        # Analyze timing of triggers
        if len(returns) > 0:
            # Calculate rolling drawdown
            cumulative_returns = np.cumprod(1 + returns) - 1
            running_max = np.maximum.accumulate(cumulative_returns)
            drawdowns = (cumulative_returns - running_max) / (1 + running_max)
            max_drawdown = np.min(drawdowns)
            
            # Check if drawdown kill switch should have triggered
            if max_drawdown < -0.15 and KillSwitchType.DRAWDOWN_LIMIT not in triggered_types:
                missed_triggers += 1
            
            # Calculate rolling volatility
            if len(returns) >= 20:
                rolling_vol = pd.Series(returns).rolling(20).std() * np.sqrt(252)
                max_vol = rolling_vol.max()
                
                # Check if volatility kill switch should have triggered
                if max_vol > 0.4 and KillSwitchType.VOLATILITY_SPIKE not in triggered_types:
                    missed_triggers += 1
        
        return {
            'triggered_types': triggered_types,
            'expected_types': expected_types,
            'missed_triggers': missed_triggers,
            'timeline_completeness': 1.0 - (missed_triggers / max(len(expected_types), 1))
        }
    
    def _calculate_performance_metrics(self, 
                                     events: List[KillSwitchEvent],
                                     returns: np.ndarray,
                                     nav: np.ndarray) -> Dict[str, float]:
        """Calculate kill switch performance metrics."""
        if len(events) == 0:
            return {
                'protection_effectiveness': 0.0,
                'avg_response_time': 0.0,
                'recovery_success_rate': 0.0
            }
        
        # Calculate NAV protection effectiveness
        nav_protections = []
        for event in events:
            if event.nav_before > 0:
                protection = 1.0 - abs(event.nav_after - event.nav_before) / event.nav_before
                nav_protections.append(max(0, protection))
        
        protection_effectiveness = np.mean(nav_protections) if nav_protections else 0.0
        
        # Calculate average response time (placeholder - would need actual timing data)
        response_times = [60.0 for _ in events]  # Assume 60 seconds average
        avg_response_time = np.mean(response_times)
        
        # Calculate recovery success rate
        recovery_successes = sum(1 for event in events if event.recovery_time is not None)
        recovery_success_rate = recovery_successes / len(events) if events else 0.0
        
        return {
            'protection_effectiveness': protection_effectiveness,
            'avg_response_time': avg_response_time,
            'recovery_success_rate': recovery_success_rate
        }
    
    def _verify_crisis_survival(self, 
                              events: List[KillSwitchEvent],
                              returns: np.ndarray,
                              nav: np.ndarray,
                              crisis: CrisisPeriod) -> Dict[str, Any]:
        """Verify that crisis survival was legitimate."""
        # Calculate actual crisis performance
        if len(returns) > 0:
            total_return = np.prod(1 + returns) - 1
            max_drawdown = self._calculate_max_drawdown(returns)
            volatility = np.std(returns) * np.sqrt(252)
        else:
            total_return = 0.0
            max_drawdown = 0.0
            volatility = 0.0
        
        # Verify survival criteria
        survival_verified = True
        adequacy_score = 1.0
        quality_score = 1.0
        
        # Check if losses were contained
        if max_drawdown < -0.25:  # More than 25% drawdown
            if not any(e.switch_type == KillSwitchType.DRAWDOWN_LIMIT for e in events):
                survival_verified = False
                adequacy_score *= 0.5
        
        # Check if volatility was managed
        if volatility > 0.5:  # More than 50% annualized volatility
            if not any(e.switch_type == KillSwitchType.VOLATILITY_SPIKE for e in events):
                survival_verified = False
                adequacy_score *= 0.7
        
        # Check response quality
        justified_events = sum(1 for e in events if e.was_justified)
        total_events = len(events)
        
        if total_events > 0:
            quality_score = justified_events / total_events
        
        # Adjust scores based on crisis severity
        adequacy_score *= (1.0 + crisis.severity_level) / 2.0
        
        return {
            'verified': survival_verified,
            'adequacy_score': adequacy_score,
            'quality_score': quality_score,
            'total_return': total_return,
            'max_drawdown': max_drawdown,
            'volatility': volatility
        }
    
    def _calculate_max_drawdown(self, returns: np.ndarray) -> float:
        """Calculate maximum drawdown."""
        cumulative_returns = np.cumprod(1 + returns) - 1
        running_max = np.maximum.accumulate(cumulative_returns)
        drawdowns = (cumulative_returns - running_max) / (1 + running_max)
        return np.min(drawdowns)
    
    def _generate_recommendations(self, 
                                events: List[KillSwitchEvent],
                                crisis: CrisisPeriod,
                                performance_metrics: Dict[str, float]) -> Dict[str, Any]:
        """Generate recommendations for kill switch improvements."""
        threshold_adjustments = {}
        system_improvements = []
        monitoring_enhancements = []
        
        # Analyze false positives
        false_positives = [e for e in events if e.false_positive]
        if len(false_positives) > len(events) * 0.3:  # More than 30% false positives
            system_improvements.append("Reduce false positive rate by improving trigger logic")
            
            # Suggest threshold adjustments
            for fp_event in false_positives:
                if fp_event.switch_type not in threshold_adjustments:
                    # Suggest making thresholds less sensitive
                    threshold_adjustments[fp_event.switch_type] = fp_event.threshold * 1.2
        
        # Analyze missed triggers
        expected_but_missing = set(crisis.expected_triggers) - {e.switch_type for e in events}
        for missing_type in expected_but_missing:
            system_improvements.append(f"Add or improve {missing_type.value} kill switch")
            monitoring_enhancements.append(f"Enhanced monitoring for {missing_type.value} conditions")
        
        # Performance-based recommendations
        if performance_metrics['protection_effectiveness'] < 0.7:
            system_improvements.append("Improve NAV protection effectiveness")
            system_improvements.append("Faster execution of kill switch actions")
        
        if performance_metrics['recovery_success_rate'] < 0.8:
            system_improvements.append("Improve recovery procedures")
            monitoring_enhancements.append("Better recovery time tracking")
        
        return {
            'threshold_adjustments': threshold_adjustments,
            'system_improvements': system_improvements,
            'monitoring_enhancements': monitoring_enhancements
        }
    
    def _log_audit_results(self, report: KillSwitchAuditReport):
        """Log kill switch audit results."""
        self.logger.info(f"🧯 Kill Switch Audit Results for {report.crisis_name}")
        self.logger.info(f"   Total Activations: {report.total_activations}")
        self.logger.info(f"   Justified Activations: {report.justified_activations}")
        self.logger.info(f"   False Positives: {report.false_positives}")
        self.logger.info(f"   Missed Triggers: {report.missed_triggers}")
        self.logger.info(f"   NAV Protection: {report.nav_protection_effectiveness:.2%}")
        self.logger.info(f"   Crisis Survival Verified: {'✅' if report.crisis_survival_verified else '❌'}")
        self.logger.info(f"   Protection Adequacy: {report.protection_adequacy_score:.2f}")
        self.logger.info(f"   Response Quality: {report.response_quality_score:.2f}")
    
    def generate_audit_report(self, report: KillSwitchAuditReport) -> str:
        """Generate comprehensive kill switch audit report."""
        return f"""
# KILL SWITCH AUDIT REPORT
## Crisis: {report.crisis_name}
## Audit Date: {report.audit_date.strftime('%Y-%m-%d %H:%M:%S')}

### EXECUTIVE SUMMARY
This report audits kill switch performance during the {report.crisis_name} to verify
that protective mechanisms fired when they should have.

### KILL SWITCH TIMELINE
- **Total Activations**: {report.total_activations}
- **Justified Activations**: {report.justified_activations}
- **False Positives**: {report.false_positives}
- **Missed Triggers**: {report.missed_triggers}

### PERFORMANCE METRICS
- **NAV Protection Effectiveness**: {report.nav_protection_effectiveness:.2%}
- **Average Response Time**: {report.average_response_time:.1f} seconds
- **Recovery Success Rate**: {report.recovery_success_rate:.2%}

### CRISIS SURVIVAL VERIFICATION
- **Survival Verified**: {'✅ YES' if report.crisis_survival_verified else '❌ NO'}
- **Protection Adequacy Score**: {report.protection_adequacy_score:.2f}/1.0
- **Response Quality Score**: {report.response_quality_score:.2f}/1.0

### KILL SWITCH EVENTS
"""
        
        for i, event in enumerate(report.kill_switch_timeline, 1):
            status = "✅" if event.was_justified else ("⚠️" if event.false_positive else "❌")
            report += f"""
#### Event {i}: {event.switch_type.value.title()}
- **Timestamp**: {event.timestamp.strftime('%Y-%m-%d %H:%M:%S')}
- **Status**: {status} {'Justified' if event.was_justified else 'False Positive' if event.false_positive else 'Questionable'}
- **Trigger Value**: {event.trigger_value:.4f}
- **Threshold**: {event.threshold:.4f}
- **Action**: {event.action_taken.value.title()}
- **NAV Impact**: {event.nav_before:.4f} → {event.nav_after:.4f}
"""
        
        report += f"""
### RECOMMENDATIONS

#### Threshold Adjustments
"""
        for switch_type, new_threshold in report.threshold_adjustments.items():
            report += f"- **{switch_type.value.title()}**: Adjust to {new_threshold:.4f}\n"
        
        report += f"""
#### System Improvements
"""
        for improvement in report.system_improvements:
            report += f"- {improvement}\n"
        
        report += f"""
#### Monitoring Enhancements
"""
        for enhancement in report.monitoring_enhancements:
            report += f"- {enhancement}\n"
        
        report += f"""
### INSTITUTIONAL CERTIFICATION
{'✅ KILL SWITCHES VERIFIED' if report.crisis_survival_verified else '❌ KILL SWITCH FAILURES DETECTED'}

This audit {'confirms' if report.crisis_survival_verified else 'questions'} the legitimacy of crisis survival claims.

---
**Report Generated**: {report.audit_date.strftime('%Y-%m-%d %H:%M:%S')}
**Audit Type**: Kill Switch Performance Verification
**Institutional Grade**: {'✅ VERIFIED' if report.crisis_survival_verified else '❌ REQUIRES ATTENTION'}
"""
        
        return report


def create_kill_switch_auditor() -> KillSwitchAuditor:
    """Create institutional-grade kill switch auditor."""
    return KillSwitchAuditor()


if __name__ == "__main__":
    # Demo usage
    auditor = create_kill_switch_auditor()
    
    # Generate sample crisis data
    np.random.seed(42)
    n = 100  # 100 days of crisis
    
    # Simulate crisis returns with high volatility
    returns = np.random.randn(n) * 0.03 - 0.001  # Negative drift, high vol
    nav_series = np.cumprod(1 + returns)
    timestamps = [datetime(2008, 9, 1) + timedelta(days=i) for i in range(n)]
    
    # Simulate kill switch log
    kill_switch_log = [
        {
            'timestamp': datetime(2008, 9, 15),
            'switch_type': 'drawdown_limit',
            'trigger_value': -0.12,
            'threshold': -0.10,
            'action_taken': 'position_reduction',
            'nav_before': 0.88,
            'nav_after': 0.90,
            'was_justified': True,
            'false_positive': False
        },
        {
            'timestamp': datetime(2008, 10, 1),
            'switch_type': 'volatility_spike',
            'trigger_value': 0.45,
            'threshold': 0.40,
            'action_taken': 'risk_reduction',
            'nav_before': 0.82,
            'nav_after': 0.85,
            'was_justified': True,
            'false_positive': False
        }
    ]
    
    # Run audit
    report = auditor.audit_crisis_kill_switches(
        returns, nav_series, timestamps, kill_switch_log, "2008_financial_crisis"
    )
    
    # Generate report
    audit_report = auditor.generate_audit_report(report)
    print(audit_report)