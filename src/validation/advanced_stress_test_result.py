"""
Advanced Stress Test Result Data Model

This module defines comprehensive data models for storing and analyzing results
from Phase 4.6 sophisticated stress testing framework. It provides structured
data models for tracking stress test outcomes, component performance, breakdown
scenarios, and recovery patterns.

The data models support institutional-grade reporting and analysis of stress
test results across multiple dimensions and time periods.

Author: Northstar V3 System
Date: 2025-01-17
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, field
from enum import Enum
import logging
import json

logger = logging.getLogger(__name__)


class StressTestType(Enum):
    """Types of stress tests conducted."""
    PHASE3_BREAKDOWN = "phase3_breakdown"
    EXTREME_SCENARIO = "extreme_scenario"
    CORRELATION_BREAKDOWN = "correlation_breakdown"
    RISK_MANAGEMENT_VALIDATION = "risk_management_validation"
    COMPREHENSIVE_STRESS = "comprehensive_stress"


class ComponentStatus(Enum):
    """Status of Phase 3 components during stress test."""
    OPERATIONAL = "operational"
    DEGRADED = "degraded"
    FAILED = "failed"
    RECOVERING = "recovering"
    UNKNOWN = "unknown"


@dataclass
class ComponentPerformanceMetrics:
    """Performance metrics for a Phase 3 component during stress test."""
    component_name: str
    baseline_performance: float
    stress_performance: float
    performance_degradation: float
    recovery_time: Optional[int]
    failure_mode: Optional[str]
    adaptation_success: bool
    lessons_learned: List[str] = field(default_factory=list)


@dataclass
class StressScenarioDetails:
    """Details of the stress scenario applied."""
    scenario_id: str
    scenario_type: str
    severity_level: float
    duration_days: int
    affected_components: List[str]
    trigger_conditions: Dict[str, Any]
    market_conditions: Dict[str, float]
    expected_outcomes: Dict[str, Any]


@dataclass
class RiskManagementResponse:
    """Risk management system response during stress test."""
    no_edge_triggered: bool
    no_edge_trigger_time: Optional[datetime]
    exposure_capping_activated: bool
    kill_switches_activated: List[str]
    emergency_brake_activated: bool
    max_drawdown_prevented: bool
    recovery_actions_taken: List[str]
    effectiveness_score: float


@dataclass
class PerformanceImpactAnalysis:
    """Analysis of performance impact during stress test."""
    max_drawdown: float
    volatility_increase: float
    sharpe_ratio_degradation: float
    var_95_breach_count: int
    var_99_breach_count: int
    correlation_breakdown_severity: float
    liquidity_impact_score: float
    recovery_time_days: Optional[int]


@dataclass
class ComponentBreakdownAnalysis:
    """Analysis of component breakdown patterns."""
    component_name: str
    breakdown_trigger: str
    breakdown_severity: float
    breakdown_duration: int
    cascade_effects: List[str]
    recovery_pattern: Optional[str]
    adaptation_mechanisms: List[str]
    failure_root_causes: List[str]


@dataclass
class StressTestValidationMetrics:
    """Validation metrics for stress test quality."""
    scenario_realism_score: float
    statistical_consistency_score: float
    component_coverage_score: float
    risk_management_coverage_score: float
    temporal_consistency_score: float
    overall_validation_score: float
    validation_warnings: List[str] = field(default_factory=list)


@dataclass
class RecoveryPatternAnalysis:
    """Analysis of recovery patterns after stress events."""
    recovery_type: str  # 'gradual', 'rapid', 'oscillating', 'incomplete'
    recovery_start_time: Optional[datetime]
    recovery_completion_time: Optional[datetime]
    recovery_duration_days: Optional[int]
    recovery_effectiveness: float
    recovery_stability: float
    lessons_for_improvement: List[str] = field(default_factory=list)


@dataclass
class InstitutionalReportingData:
    """Data required for institutional-grade stress test reporting."""
    executive_summary: str
    key_findings: List[str]
    risk_assessment: str
    regulatory_compliance_status: str
    recommendations: List[str]
    action_items: List[str]
    next_review_date: datetime
    report_confidence_level: float


@dataclass
class AdvancedStressTestResult:
    """
    Comprehensive result of advanced stress testing.
    
    This data model captures all aspects of sophisticated stress testing
    including component performance, risk management effectiveness, recovery
    patterns, and institutional reporting requirements.
    """
    
    # Test Identification
    test_id: str
    test_type: StressTestType
    test_description: str
    test_timestamp: datetime
    test_duration: timedelta
    
    # Scenario Details
    stress_scenario: StressScenarioDetails
    
    # Component Performance
    phase3_component_performance: Dict[str, ComponentPerformanceMetrics]
    component_breakdown_analysis: Dict[str, ComponentBreakdownAnalysis]
    component_interaction_effects: Dict[str, float]
    
    # Risk Management Analysis
    risk_management_response: RiskManagementResponse
    catastrophic_loss_prevention: bool
    risk_management_effectiveness: float
    
    # Performance Impact
    performance_impact: PerformanceImpactAnalysis
    
    # Recovery Analysis
    recovery_pattern: RecoveryPatternAnalysis
    
    # Validation and Quality
    validation_metrics: StressTestValidationMetrics
    test_success: bool
    
    # Lessons and Recommendations
    lessons_learned: List[str]
    system_improvements_identified: List[str]
    risk_management_enhancements: List[str]
    
    # Institutional Reporting
    institutional_reporting_data: InstitutionalReportingData
    
    # Raw Data and Metrics
    time_series_data: Optional[pd.DataFrame] = None
    detailed_metrics: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Post-initialization validation and setup."""
        self._validate_data_consistency()
        self._calculate_derived_metrics()
    
    def _validate_data_consistency(self):
        """Validate internal data consistency."""
        # Validate component performance data
        for component_name, performance in self.phase3_component_performance.items():
            if performance.performance_degradation < 0 or performance.performance_degradation > 1:
                logger.warning(f"Invalid performance degradation for {component_name}: {performance.performance_degradation}")
        
        # Validate risk management effectiveness
        if not (0.0 <= self.risk_management_effectiveness <= 1.0):
            logger.warning(f"Invalid risk management effectiveness: {self.risk_management_effectiveness}")
        
        # Validate performance impact metrics
        if self.performance_impact.max_drawdown > 0:
            logger.warning(f"Invalid max drawdown (should be negative): {self.performance_impact.max_drawdown}")
    
    def _calculate_derived_metrics(self):
        """Calculate derived metrics from base data."""
        # Calculate overall component health score
        if self.phase3_component_performance:
            component_scores = [
                perf.stress_performance for perf in self.phase3_component_performance.values()
            ]
            self.detailed_metrics['overall_component_health'] = np.mean(component_scores)
        
        # Calculate system resilience score
        resilience_factors = [
            self.risk_management_effectiveness,
            1.0 - abs(self.performance_impact.max_drawdown),  # Drawdown resilience
            self.recovery_pattern.recovery_effectiveness if self.recovery_pattern.recovery_effectiveness else 0.5
        ]
        self.detailed_metrics['system_resilience_score'] = np.mean(resilience_factors)
    
    def get_executive_summary(self) -> str:
        """Generate executive summary of stress test results."""
        summary_parts = []
        
        # Test overview
        summary_parts.append(f"Stress Test: {self.test_description}")
        summary_parts.append(f"Scenario: {self.stress_scenario.scenario_type} (Severity: {self.stress_scenario.severity_level:.1%})")
        summary_parts.append(f"Duration: {self.stress_scenario.duration_days} days")
        
        # Key results
        summary_parts.append(f"Risk Management Effectiveness: {self.risk_management_effectiveness:.1%}")
        summary_parts.append(f"Maximum Drawdown: {self.performance_impact.max_drawdown:.1%}")
        summary_parts.append(f"Catastrophic Loss Prevention: {'Success' if self.catastrophic_loss_prevention else 'Failed'}")
        
        # Component performance
        if self.phase3_component_performance:
            avg_component_performance = np.mean([
                perf.stress_performance for perf in self.phase3_component_performance.values()
            ])
            summary_parts.append(f"Average Component Performance: {avg_component_performance:.1%}")
        
        # Recovery
        if self.recovery_pattern.recovery_duration_days:
            summary_parts.append(f"Recovery Time: {self.recovery_pattern.recovery_duration_days} days")
        
        return "\n".join(summary_parts)
    
    def get_component_performance_summary(self) -> Dict[str, Dict[str, Any]]:
        """Get summary of component performance during stress test."""
        summary = {}
        
        for component_name, performance in self.phase3_component_performance.items():
            summary[component_name] = {
                'baseline_performance': performance.baseline_performance,
                'stress_performance': performance.stress_performance,
                'degradation': performance.performance_degradation,
                'recovery_time': performance.recovery_time,
                'adaptation_success': performance.adaptation_success,
                'status': self._determine_component_status(performance)
            }
        
        return summary
    
    def _determine_component_status(self, performance: ComponentPerformanceMetrics) -> ComponentStatus:
        """Determine component status based on performance metrics."""
        if performance.stress_performance > 0.8:
            return ComponentStatus.OPERATIONAL
        elif performance.stress_performance > 0.5:
            return ComponentStatus.DEGRADED
        elif performance.stress_performance > 0.2:
            return ComponentStatus.FAILED
        elif performance.recovery_time is not None:
            return ComponentStatus.RECOVERING
        else:
            return ComponentStatus.UNKNOWN
    
    def get_risk_management_summary(self) -> Dict[str, Any]:
        """Get summary of risk management performance."""
        return {
            'overall_effectiveness': self.risk_management_effectiveness,
            'no_edge_triggered': self.risk_management_response.no_edge_triggered,
            'exposure_capping_activated': self.risk_management_response.exposure_capping_activated,
            'kill_switches_activated': self.risk_management_response.kill_switches_activated,
            'emergency_brake_activated': self.risk_management_response.emergency_brake_activated,
            'catastrophic_loss_prevented': self.catastrophic_loss_prevention,
            'effectiveness_score': self.risk_management_response.effectiveness_score
        }
    
    def get_performance_impact_summary(self) -> Dict[str, Any]:
        """Get summary of performance impact during stress test."""
        return {
            'max_drawdown': self.performance_impact.max_drawdown,
            'volatility_increase': self.performance_impact.volatility_increase,
            'sharpe_degradation': self.performance_impact.sharpe_ratio_degradation,
            'var_breaches': {
                'var_95': self.performance_impact.var_95_breach_count,
                'var_99': self.performance_impact.var_99_breach_count
            },
            'correlation_breakdown': self.performance_impact.correlation_breakdown_severity,
            'liquidity_impact': self.performance_impact.liquidity_impact_score,
            'recovery_time': self.performance_impact.recovery_time_days
        }
    
    def get_lessons_learned_summary(self) -> Dict[str, List[str]]:
        """Get organized summary of lessons learned."""
        return {
            'general_lessons': self.lessons_learned,
            'system_improvements': self.system_improvements_identified,
            'risk_management_enhancements': self.risk_management_enhancements,
            'component_specific_lessons': [
                lesson for performance in self.phase3_component_performance.values()
                for lesson in performance.lessons_learned
            ]
        }
    
    def export_to_dict(self) -> Dict[str, Any]:
        """Export stress test result to dictionary format."""
        return {
            'test_identification': {
                'test_id': self.test_id,
                'test_type': self.test_type.value,
                'description': self.test_description,
                'timestamp': self.test_timestamp.isoformat(),
                'duration': str(self.test_duration)
            },
            'scenario_details': {
                'scenario_id': self.stress_scenario.scenario_id,
                'scenario_type': self.stress_scenario.scenario_type,
                'severity_level': self.stress_scenario.severity_level,
                'duration_days': self.stress_scenario.duration_days,
                'affected_components': self.stress_scenario.affected_components
            },
            'component_performance': self.get_component_performance_summary(),
            'risk_management': self.get_risk_management_summary(),
            'performance_impact': self.get_performance_impact_summary(),
            'recovery_analysis': {
                'recovery_type': self.recovery_pattern.recovery_type,
                'recovery_duration': self.recovery_pattern.recovery_duration_days,
                'recovery_effectiveness': self.recovery_pattern.recovery_effectiveness
            },
            'validation_metrics': {
                'scenario_realism': self.validation_metrics.scenario_realism_score,
                'statistical_consistency': self.validation_metrics.statistical_consistency_score,
                'overall_validation': self.validation_metrics.overall_validation_score
            },
            'lessons_learned': self.get_lessons_learned_summary(),
            'institutional_reporting': {
                'executive_summary': self.institutional_reporting_data.executive_summary,
                'key_findings': self.institutional_reporting_data.key_findings,
                'recommendations': self.institutional_reporting_data.recommendations
            },
            'test_success': self.test_success
        }
    
    def export_to_json(self, filepath: Optional[str] = None) -> str:
        """Export stress test result to JSON format."""
        data = self.export_to_dict()
        json_str = json.dumps(data, indent=2, default=str)
        
        if filepath:
            with open(filepath, 'w') as f:
                f.write(json_str)
            logger.info(f"Stress test result exported to {filepath}")
        
        return json_str
    
    def generate_institutional_report(self) -> str:
        """Generate institutional-grade stress test report."""
        report_sections = []
        
        # Executive Summary
        report_sections.append("# STRESS TEST REPORT")
        report_sections.append("## Executive Summary")
        report_sections.append(self.get_executive_summary())
        report_sections.append("")
        
        # Test Details
        report_sections.append("## Test Details")
        report_sections.append(f"**Test ID:** {self.test_id}")
        report_sections.append(f"**Test Type:** {self.test_type.value}")
        report_sections.append(f"**Test Date:** {self.test_timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        report_sections.append(f"**Scenario:** {self.stress_scenario.scenario_type}")
        report_sections.append(f"**Severity:** {self.stress_scenario.severity_level:.1%}")
        report_sections.append(f"**Duration:** {self.stress_scenario.duration_days} days")
        report_sections.append("")
        
        # Component Performance
        report_sections.append("## Component Performance Analysis")
        component_summary = self.get_component_performance_summary()
        for component, metrics in component_summary.items():
            report_sections.append(f"**{component}:**")
            report_sections.append(f"- Baseline Performance: {metrics['baseline_performance']:.1%}")
            report_sections.append(f"- Stress Performance: {metrics['stress_performance']:.1%}")
            report_sections.append(f"- Performance Degradation: {metrics['degradation']:.1%}")
            report_sections.append(f"- Status: {metrics['status'].value}")
            report_sections.append("")
        
        # Risk Management
        report_sections.append("## Risk Management Performance")
        risk_summary = self.get_risk_management_summary()
        report_sections.append(f"**Overall Effectiveness:** {risk_summary['overall_effectiveness']:.1%}")
        report_sections.append(f"**NO_EDGE Triggered:** {risk_summary['no_edge_triggered']}")
        report_sections.append(f"**Catastrophic Loss Prevented:** {risk_summary['catastrophic_loss_prevented']}")
        report_sections.append("")
        
        # Performance Impact
        report_sections.append("## Performance Impact")
        impact_summary = self.get_performance_impact_summary()
        report_sections.append(f"**Maximum Drawdown:** {impact_summary['max_drawdown']:.1%}")
        report_sections.append(f"**Volatility Increase:** {impact_summary['volatility_increase']:.1%}")
        report_sections.append(f"**Recovery Time:** {impact_summary['recovery_time']} days")
        report_sections.append("")
        
        # Key Findings
        report_sections.append("## Key Findings")
        for finding in self.institutional_reporting_data.key_findings:
            report_sections.append(f"- {finding}")
        report_sections.append("")
        
        # Recommendations
        report_sections.append("## Recommendations")
        for recommendation in self.institutional_reporting_data.recommendations:
            report_sections.append(f"- {recommendation}")
        report_sections.append("")
        
        # Lessons Learned
        report_sections.append("## Lessons Learned")
        lessons_summary = self.get_lessons_learned_summary()
        for category, lessons in lessons_summary.items():
            if lessons:
                report_sections.append(f"**{category.replace('_', ' ').title()}:**")
                for lesson in lessons:
                    report_sections.append(f"- {lesson}")
                report_sections.append("")
        
        return "\n".join(report_sections)
    
    def compare_with_baseline(self, baseline_result: 'AdvancedStressTestResult') -> Dict[str, Any]:
        """Compare this stress test result with a baseline result."""
        comparison = {}
        
        # Compare overall effectiveness
        comparison['risk_management_effectiveness_change'] = (
            self.risk_management_effectiveness - baseline_result.risk_management_effectiveness
        )
        
        # Compare component performance
        comparison['component_performance_changes'] = {}
        for component_name in self.phase3_component_performance:
            if component_name in baseline_result.phase3_component_performance:
                baseline_perf = baseline_result.phase3_component_performance[component_name].stress_performance
                current_perf = self.phase3_component_performance[component_name].stress_performance
                comparison['component_performance_changes'][component_name] = current_perf - baseline_perf
        
        # Compare performance impact
        comparison['max_drawdown_change'] = (
            self.performance_impact.max_drawdown - baseline_result.performance_impact.max_drawdown
        )
        
        # Compare recovery time
        if (self.recovery_pattern.recovery_duration_days is not None and 
            baseline_result.recovery_pattern.recovery_duration_days is not None):
            comparison['recovery_time_change'] = (
                self.recovery_pattern.recovery_duration_days - 
                baseline_result.recovery_pattern.recovery_duration_days
            )
        
        return comparison


@dataclass
class StressTestSuite:
    """Collection of related stress test results."""
    suite_id: str
    suite_description: str
    test_results: List[AdvancedStressTestResult]
    suite_timestamp: datetime
    
    def get_suite_summary(self) -> Dict[str, Any]:
        """Get summary of entire stress test suite."""
        if not self.test_results:
            return {}
        
        # Calculate aggregate metrics
        avg_risk_mgmt_effectiveness = np.mean([
            result.risk_management_effectiveness for result in self.test_results
        ])
        
        worst_drawdown = min([
            result.performance_impact.max_drawdown for result in self.test_results
        ])
        
        catastrophic_loss_prevention_rate = np.mean([
            result.catastrophic_loss_prevention for result in self.test_results
        ])
        
        avg_recovery_time = np.mean([
            result.recovery_pattern.recovery_duration_days 
            for result in self.test_results 
            if result.recovery_pattern.recovery_duration_days is not None
        ])
        
        return {
            'suite_id': self.suite_id,
            'total_tests': len(self.test_results),
            'successful_tests': sum(result.test_success for result in self.test_results),
            'avg_risk_management_effectiveness': avg_risk_mgmt_effectiveness,
            'worst_drawdown': worst_drawdown,
            'catastrophic_loss_prevention_rate': catastrophic_loss_prevention_rate,
            'avg_recovery_time': avg_recovery_time,
            'test_types': list(set(result.test_type.value for result in self.test_results))
        }
    
    def export_suite_to_json(self, filepath: str):
        """Export entire stress test suite to JSON."""
        suite_data = {
            'suite_summary': self.get_suite_summary(),
            'test_results': [result.export_to_dict() for result in self.test_results]
        }
        
        with open(filepath, 'w') as f:
            json.dump(suite_data, f, indent=2, default=str)
        
        logger.info(f"Stress test suite exported to {filepath}")


def create_sample_stress_test_result() -> AdvancedStressTestResult:
    """Create a sample stress test result for testing purposes."""
    
    # Sample scenario details
    scenario = StressScenarioDetails(
        scenario_id="sample_stress_001",
        scenario_type="extreme_drawdown",
        severity_level=0.8,
        duration_days=60,
        affected_components=["regime_memory", "tailwind_engine", "no_edge_detector"],
        trigger_conditions={"max_drawdown": -0.25, "volatility_spike": 0.08},
        market_conditions={"volatility": 0.35, "correlation": 0.9},
        expected_outcomes={"no_edge_trigger": True, "exposure_capping": True}
    )
    
    # Sample component performance
    component_performance = {
        "regime_memory": ComponentPerformanceMetrics(
            component_name="regime_memory",
            baseline_performance=0.8,
            stress_performance=0.4,
            performance_degradation=0.4,
            recovery_time=30,
            failure_mode="similarity_calculation_instability",
            adaptation_success=True,
            lessons_learned=["Regime memory needs stability enhancements"]
        ),
        "tailwind_engine": ComponentPerformanceMetrics(
            component_name="tailwind_engine",
            baseline_performance=0.75,
            stress_performance=0.3,
            performance_degradation=0.45,
            recovery_time=45,
            failure_mode="performance_relationship_breakdown",
            adaptation_success=False,
            lessons_learned=["Tailwind calculations need robustness improvements"]
        )
    }
    
    # Sample risk management response
    risk_response = RiskManagementResponse(
        no_edge_triggered=True,
        no_edge_trigger_time=datetime.now() - timedelta(days=50),
        exposure_capping_activated=True,
        kill_switches_activated=["drawdown_kill_switch"],
        emergency_brake_activated=False,
        max_drawdown_prevented=True,
        recovery_actions_taken=["exposure_reduction", "position_rebalancing"],
        effectiveness_score=0.85
    )
    
    # Sample performance impact
    performance_impact = PerformanceImpactAnalysis(
        max_drawdown=-0.22,
        volatility_increase=0.15,
        sharpe_ratio_degradation=0.3,
        var_95_breach_count=5,
        var_99_breach_count=2,
        correlation_breakdown_severity=0.6,
        liquidity_impact_score=0.4,
        recovery_time_days=35
    )
    
    # Sample recovery pattern
    recovery_pattern = RecoveryPatternAnalysis(
        recovery_type="gradual",
        recovery_start_time=datetime.now() - timedelta(days=30),
        recovery_completion_time=datetime.now() - timedelta(days=5),
        recovery_duration_days=25,
        recovery_effectiveness=0.8,
        recovery_stability=0.9,
        lessons_for_improvement=["Recovery could be accelerated with better risk management"]
    )
    
    # Sample validation metrics
    validation_metrics = StressTestValidationMetrics(
        scenario_realism_score=0.9,
        statistical_consistency_score=0.85,
        component_coverage_score=0.95,
        risk_management_coverage_score=0.9,
        temporal_consistency_score=0.88,
        overall_validation_score=0.89
    )
    
    # Sample institutional reporting data
    institutional_data = InstitutionalReportingData(
        executive_summary="Stress test successfully validated system resilience under extreme conditions",
        key_findings=[
            "Risk management systems performed effectively",
            "Component degradation was within acceptable limits",
            "Recovery mechanisms functioned as designed"
        ],
        risk_assessment="Medium risk with effective mitigation",
        regulatory_compliance_status="Compliant",
        recommendations=[
            "Enhance regime memory stability",
            "Improve tailwind calculation robustness"
        ],
        action_items=[
            "Implement stability enhancements by Q2",
            "Review tailwind calculation methodology"
        ],
        next_review_date=datetime.now() + timedelta(days=90),
        report_confidence_level=0.9
    )
    
    return AdvancedStressTestResult(
        test_id="sample_stress_test_001",
        test_type=StressTestType.COMPREHENSIVE_STRESS,
        test_description="Sample comprehensive stress test",
        test_timestamp=datetime.now(),
        test_duration=timedelta(days=60),
        stress_scenario=scenario,
        phase3_component_performance=component_performance,
        component_breakdown_analysis={},
        component_interaction_effects={},
        risk_management_response=risk_response,
        catastrophic_loss_prevention=True,
        risk_management_effectiveness=0.85,
        performance_impact=performance_impact,
        recovery_pattern=recovery_pattern,
        validation_metrics=validation_metrics,
        test_success=True,
        lessons_learned=[
            "System demonstrated good resilience under stress",
            "Risk management mechanisms functioned effectively",
            "Component recovery patterns were acceptable"
        ],
        system_improvements_identified=[
            "Regime memory stability enhancements",
            "Tailwind calculation robustness improvements"
        ],
        risk_management_enhancements=[
            "Faster NO_EDGE trigger response",
            "Enhanced exposure capping mechanisms"
        ],
        institutional_reporting_data=institutional_data
    )