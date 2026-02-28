#!/usr/bin/env python3
"""
📊 MULTI-TIMELINE VALIDATION RESULT - SHADOW REALITY PHASE 4.3
Data Model for Multi-Timeline Validation Results

This data model tracks validation results across all tested periods:
- Accuracy metrics for each Phase 3 component across timelines
- Overall consistency scoring and variance attribution
- Failed periods identification and recommendations
- Comprehensive validation reporting structure

Integration with Phase 3:
- Stores RegimeMemorySystem validation results across periods
- Tracks SimpleTailwindEngine performance consistency
- Records NoEdgeDetector appropriateness across stress levels
- Captures AnticipatoryCapitalAllocator effectiveness metrics

Used by: HistoricalPeriodValidator, Phase3ComponentValidator, CrossTimelineConsistencyChecker
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from enum import Enum
import json
import pandas as pd
import numpy as np

class ValidationStatus(Enum):
    """Validation status enumeration"""
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    NOT_TESTED = "not_tested"

class ConsistencyLevel(Enum):
    """Consistency level enumeration"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    VERY_LOW = "very_low"

class RegimeDependenceLevel(Enum):
    """Regime dependence level enumeration"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXTREME = "extreme"

class OverfittingRiskLevel(Enum):
    """Overfitting risk level enumeration"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

@dataclass
class ComponentValidationMetrics:
    """Validation metrics for a single component in a single period"""
    
    # Basic validation results
    validation_passed: bool
    overall_score: float
    confidence_score: float
    
    # Component-specific metrics
    accuracy_score: Optional[float] = None
    stability_score: Optional[float] = None
    appropriateness_score: Optional[float] = None
    performance_score: Optional[float] = None
    risk_adjusted_score: Optional[float] = None
    
    # Detailed metrics
    correlation_score: Optional[float] = None
    consistency_score: Optional[float] = None
    predictive_score: Optional[float] = None
    
    # Issues and diagnostics
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    # Additional metadata
    execution_time_ms: Optional[float] = None
    data_quality_score: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'validation_passed': self.validation_passed,
            'overall_score': self.overall_score,
            'confidence_score': self.confidence_score,
            'accuracy_score': self.accuracy_score,
            'stability_score': self.stability_score,
            'appropriateness_score': self.appropriateness_score,
            'performance_score': self.performance_score,
            'risk_adjusted_score': self.risk_adjusted_score,
            'correlation_score': self.correlation_score,
            'consistency_score': self.consistency_score,
            'predictive_score': self.predictive_score,
            'issues': self.issues,
            'warnings': self.warnings,
            'execution_time_ms': self.execution_time_ms,
            'data_quality_score': self.data_quality_score
        }

@dataclass
class PeriodValidationResult:
    """Validation results for all components in a single period"""
    
    # Period identification
    period_name: str
    period_description: str
    start_date: str
    end_date: str
    
    # Expected characteristics
    expected_regime: str
    stress_level: str
    volatility_expectation: str
    tailwind_stability: str
    
    # Overall period results
    validation_status: ValidationStatus
    overall_score: float
    components_passed: int
    total_components: int
    
    # Component-specific results
    regime_memory_metrics: Optional[ComponentValidationMetrics] = None
    tailwind_engine_metrics: Optional[ComponentValidationMetrics] = None
    no_edge_detector_metrics: Optional[ComponentValidationMetrics] = None
    capital_allocator_metrics: Optional[ComponentValidationMetrics] = None
    
    # Period-level issues
    period_issues: List[str] = field(default_factory=list)
    data_availability: Dict[str, bool] = field(default_factory=dict)
    
    # Timing information
    validation_timestamp: Optional[str] = None
    validation_duration_ms: Optional[float] = None
    
    def get_component_metrics(self, component_name: str) -> Optional[ComponentValidationMetrics]:
        """Get metrics for a specific component"""
        component_mapping = {
            'regime_memory': self.regime_memory_metrics,
            'regime_memory_system': self.regime_memory_metrics,
            'tailwind_engine': self.tailwind_engine_metrics,
            'simple_tailwind_engine': self.tailwind_engine_metrics,
            'no_edge_detector': self.no_edge_detector_metrics,
            'capital_allocator': self.capital_allocator_metrics,
            'anticipatory_capital_allocator': self.capital_allocator_metrics
        }
        return component_mapping.get(component_name)
    
    def get_all_component_metrics(self) -> Dict[str, ComponentValidationMetrics]:
        """Get all component metrics as dictionary"""
        components = {}
        if self.regime_memory_metrics:
            components['regime_memory_system'] = self.regime_memory_metrics
        if self.tailwind_engine_metrics:
            components['simple_tailwind_engine'] = self.tailwind_engine_metrics
        if self.no_edge_detector_metrics:
            components['no_edge_detector'] = self.no_edge_detector_metrics
        if self.capital_allocator_metrics:
            components['anticipatory_capital_allocator'] = self.capital_allocator_metrics
        return components
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'period_name': self.period_name,
            'period_description': self.period_description,
            'start_date': self.start_date,
            'end_date': self.end_date,
            'expected_regime': self.expected_regime,
            'stress_level': self.stress_level,
            'volatility_expectation': self.volatility_expectation,
            'tailwind_stability': self.tailwind_stability,
            'validation_status': self.validation_status.value,
            'overall_score': self.overall_score,
            'components_passed': self.components_passed,
            'total_components': self.total_components,
            'regime_memory_metrics': self.regime_memory_metrics.to_dict() if self.regime_memory_metrics else None,
            'tailwind_engine_metrics': self.tailwind_engine_metrics.to_dict() if self.tailwind_engine_metrics else None,
            'no_edge_detector_metrics': self.no_edge_detector_metrics.to_dict() if self.no_edge_detector_metrics else None,
            'capital_allocator_metrics': self.capital_allocator_metrics.to_dict() if self.capital_allocator_metrics else None,
            'period_issues': self.period_issues,
            'data_availability': self.data_availability,
            'validation_timestamp': self.validation_timestamp,
            'validation_duration_ms': self.validation_duration_ms
        }

@dataclass
class ComponentConsistencyAnalysis:
    """Cross-timeline consistency analysis for a single component"""
    
    component_name: str
    
    # Consistency metrics
    consistency_level: ConsistencyLevel
    consistency_score: float
    coefficient_of_variation: float
    score_range: float
    score_range_normalized: float
    
    # Performance statistics
    mean_score: float
    std_score: float
    min_score: float
    max_score: float
    pass_rate: float
    pass_consistency: float
    
    # Period analysis
    periods_analyzed: int
    best_period: Optional[tuple] = None  # (period_name, score)
    worst_period: Optional[tuple] = None  # (period_name, score)
    period_scores: Dict[str, Dict[str, Union[float, bool]]] = field(default_factory=dict)
    
    # Regime dependence
    regime_dependence_level: Optional[RegimeDependenceLevel] = None
    regime_dependence_score: Optional[float] = None
    regime_variance: Optional[float] = None
    regime_range: Optional[float] = None
    best_regime: Optional[tuple] = None  # (regime_name, score)
    worst_regime: Optional[tuple] = None  # (regime_name, score)
    
    # Overfitting analysis
    overfitting_risk_level: Optional[OverfittingRiskLevel] = None
    overfitting_risk_score: Optional[float] = None
    risk_factors: List[str] = field(default_factory=list)
    temporal_correlation: Optional[float] = None
    outlier_periods: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'component_name': self.component_name,
            'consistency_level': self.consistency_level.value,
            'consistency_score': self.consistency_score,
            'coefficient_of_variation': self.coefficient_of_variation,
            'score_range': self.score_range,
            'score_range_normalized': self.score_range_normalized,
            'mean_score': self.mean_score,
            'std_score': self.std_score,
            'min_score': self.min_score,
            'max_score': self.max_score,
            'pass_rate': self.pass_rate,
            'pass_consistency': self.pass_consistency,
            'periods_analyzed': self.periods_analyzed,
            'best_period': self.best_period,
            'worst_period': self.worst_period,
            'period_scores': self.period_scores,
            'regime_dependence_level': self.regime_dependence_level.value if self.regime_dependence_level else None,
            'regime_dependence_score': self.regime_dependence_score,
            'regime_variance': self.regime_variance,
            'regime_range': self.regime_range,
            'best_regime': self.best_regime,
            'worst_regime': self.worst_regime,
            'overfitting_risk_level': self.overfitting_risk_level.value if self.overfitting_risk_level else None,
            'overfitting_risk_score': self.overfitting_risk_score,
            'risk_factors': self.risk_factors,
            'temporal_correlation': self.temporal_correlation,
            'outlier_periods': self.outlier_periods
        }

@dataclass
class VarianceAttributionAnalysis:
    """Variance attribution analysis across components"""
    
    # Overall variance metrics
    overall_variance: float
    overall_std: float
    overall_cv: float
    
    # System-level metrics
    periods_analyzed: int
    total_contribution: float
    unexplained_variance: float
    
    # Component contributions
    component_variance_contribution: Dict[str, Dict[str, float]] = field(default_factory=dict)
    variance_attribution_pct: Dict[str, float] = field(default_factory=dict)
    high_variance_components: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'overall_variance': self.overall_variance,
            'overall_std': self.overall_std,
            'overall_cv': self.overall_cv,
            'component_variance_contribution': self.component_variance_contribution,
            'variance_attribution_pct': self.variance_attribution_pct,
            'high_variance_components': self.high_variance_components,
            'periods_analyzed': self.periods_analyzed,
            'total_contribution': self.total_contribution,
            'unexplained_variance': self.unexplained_variance
        }

@dataclass
class ValidationRecommendation:
    """Recommendation for improving validation results"""
    
    recommendation_type: str  # 'consistency', 'regime_dependence', 'overfitting', 'variance', 'system'
    priority: str  # 'high', 'medium', 'low'
    component: Optional[str] = None
    issue_description: str = ""
    recommendation_text: str = ""
    expected_impact: Optional[str] = None
    implementation_effort: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'recommendation_type': self.recommendation_type,
            'priority': self.priority,
            'component': self.component,
            'issue_description': self.issue_description,
            'recommendation_text': self.recommendation_text,
            'expected_impact': self.expected_impact,
            'implementation_effort': self.implementation_effort
        }

@dataclass
class MultiTimelineValidationResult:
    """
    Comprehensive Multi-Timeline Validation Result
    
    This is the main data model that aggregates all validation results
    across multiple timelines and provides comprehensive analysis.
    """
    
    # Validation metadata
    validation_id: str
    validation_timestamp: str
    validator_version: str
    
    # Overall validation results
    overall_validation_status: ValidationStatus
    overall_consistency_score: float
    overall_consistency_level: ConsistencyLevel
    
    # Period-level results
    periods_tested: int
    periods_passed: int
    periods_failed: int
    success_rate: float
    period_results: Dict[str, PeriodValidationResult] = field(default_factory=dict)
    
    # Component-level analysis
    components_analyzed: List[str] = field(default_factory=list)
    component_consistency: Dict[str, ComponentConsistencyAnalysis] = field(default_factory=dict)
    component_success_rates: Dict[str, float] = field(default_factory=dict)
    
    # Cross-timeline analysis
    variance_attribution: Optional[VarianceAttributionAnalysis] = None
    
    # Failed periods and issues
    failed_periods: List[str] = field(default_factory=list)
    critical_issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    # Recommendations
    recommendations: List[ValidationRecommendation] = field(default_factory=list)
    
    # Performance metrics
    total_validation_time_ms: Optional[float] = None
    average_period_validation_time_ms: Optional[float] = None
    
    def add_period_result(self, period_result: PeriodValidationResult):
        """Add a period validation result"""
        self.period_results[period_result.period_name] = period_result
        
        # Update counters
        if period_result.validation_status == ValidationStatus.PASSED:
            self.periods_passed += 1
        else:
            self.periods_failed += 1
            self.failed_periods.append(period_result.period_name)
        
        self.periods_tested = len(self.period_results)
        self.success_rate = self.periods_passed / self.periods_tested if self.periods_tested > 0 else 0.0
    
    def add_component_consistency(self, component_analysis: ComponentConsistencyAnalysis):
        """Add component consistency analysis"""
        self.component_consistency[component_analysis.component_name] = component_analysis
        self.component_success_rates[component_analysis.component_name] = component_analysis.pass_rate
        
        if component_analysis.component_name not in self.components_analyzed:
            self.components_analyzed.append(component_analysis.component_name)
    
    def add_recommendation(self, recommendation: ValidationRecommendation):
        """Add a validation recommendation"""
        self.recommendations.append(recommendation)
    
    def get_period_result(self, period_name: str) -> Optional[PeriodValidationResult]:
        """Get validation result for a specific period"""
        return self.period_results.get(period_name)
    
    def get_component_consistency(self, component_name: str) -> Optional[ComponentConsistencyAnalysis]:
        """Get consistency analysis for a specific component"""
        return self.component_consistency.get(component_name)
    
    def get_failed_periods(self) -> List[PeriodValidationResult]:
        """Get all failed period results"""
        return [result for result in self.period_results.values() 
                if result.validation_status != ValidationStatus.PASSED]
    
    def get_high_priority_recommendations(self) -> List[ValidationRecommendation]:
        """Get high priority recommendations"""
        return [rec for rec in self.recommendations if rec.priority == 'high']
    
    def get_component_recommendations(self, component_name: str) -> List[ValidationRecommendation]:
        """Get recommendations for a specific component"""
        return [rec for rec in self.recommendations if rec.component == component_name]
    
    def calculate_overall_metrics(self):
        """Calculate overall validation metrics from period results"""
        if not self.period_results:
            return
        
        # Calculate overall consistency score
        period_scores = [result.overall_score for result in self.period_results.values()]
        self.overall_consistency_score = np.mean(period_scores) if period_scores else 0.0
        
        # Determine overall consistency level
        if self.overall_consistency_score >= 0.8:
            self.overall_consistency_level = ConsistencyLevel.HIGH
        elif self.overall_consistency_score >= 0.6:
            self.overall_consistency_level = ConsistencyLevel.MEDIUM
        elif self.overall_consistency_score >= 0.4:
            self.overall_consistency_level = ConsistencyLevel.LOW
        else:
            self.overall_consistency_level = ConsistencyLevel.VERY_LOW
        
        # Determine overall validation status
        if self.success_rate >= 0.8:
            self.overall_validation_status = ValidationStatus.PASSED
        elif self.success_rate >= 0.6:
            self.overall_validation_status = ValidationStatus.WARNING
        else:
            self.overall_validation_status = ValidationStatus.FAILED
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'validation_id': self.validation_id,
            'validation_timestamp': self.validation_timestamp,
            'validator_version': self.validator_version,
            'overall_validation_status': self.overall_validation_status.value,
            'overall_consistency_score': self.overall_consistency_score,
            'overall_consistency_level': self.overall_consistency_level.value,
            'periods_tested': self.periods_tested,
            'periods_passed': self.periods_passed,
            'periods_failed': self.periods_failed,
            'success_rate': self.success_rate,
            'period_results': {name: result.to_dict() for name, result in self.period_results.items()},
            'components_analyzed': self.components_analyzed,
            'component_consistency': {name: analysis.to_dict() for name, analysis in self.component_consistency.items()},
            'component_success_rates': self.component_success_rates,
            'variance_attribution': self.variance_attribution.to_dict() if self.variance_attribution else None,
            'failed_periods': self.failed_periods,
            'critical_issues': self.critical_issues,
            'warnings': self.warnings,
            'recommendations': [rec.to_dict() for rec in self.recommendations],
            'total_validation_time_ms': self.total_validation_time_ms,
            'average_period_validation_time_ms': self.average_period_validation_time_ms
        }
    
    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), indent=indent)
    
    def save_to_file(self, filepath: str):
        """Save to JSON file"""
        with open(filepath, 'w') as f:
            f.write(self.to_json())
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MultiTimelineValidationResult':
        """Create instance from dictionary"""
        
        # Create main instance
        result = cls(
            validation_id=data['validation_id'],
            validation_timestamp=data['validation_timestamp'],
            validator_version=data['validator_version'],
            overall_validation_status=ValidationStatus(data['overall_validation_status']),
            overall_consistency_score=data['overall_consistency_score'],
            overall_consistency_level=ConsistencyLevel(data['overall_consistency_level']),
            periods_tested=data['periods_tested'],
            periods_passed=data['periods_passed'],
            periods_failed=data['periods_failed'],
            success_rate=data['success_rate'],
            components_analyzed=data['components_analyzed'],
            component_success_rates=data['component_success_rates'],
            failed_periods=data['failed_periods'],
            critical_issues=data['critical_issues'],
            warnings=data['warnings'],
            total_validation_time_ms=data.get('total_validation_time_ms'),
            average_period_validation_time_ms=data.get('average_period_validation_time_ms')
        )
        
        # Add period results
        for period_name, period_data in data['period_results'].items():
            # Reconstruct ComponentValidationMetrics
            def create_metrics(metrics_data):
                if not metrics_data:
                    return None
                return ComponentValidationMetrics(
                    validation_passed=metrics_data['validation_passed'],
                    overall_score=metrics_data['overall_score'],
                    confidence_score=metrics_data['confidence_score'],
                    accuracy_score=metrics_data.get('accuracy_score'),
                    stability_score=metrics_data.get('stability_score'),
                    appropriateness_score=metrics_data.get('appropriateness_score'),
                    performance_score=metrics_data.get('performance_score'),
                    risk_adjusted_score=metrics_data.get('risk_adjusted_score'),
                    correlation_score=metrics_data.get('correlation_score'),
                    consistency_score=metrics_data.get('consistency_score'),
                    predictive_score=metrics_data.get('predictive_score'),
                    issues=metrics_data.get('issues', []),
                    warnings=metrics_data.get('warnings', []),
                    execution_time_ms=metrics_data.get('execution_time_ms'),
                    data_quality_score=metrics_data.get('data_quality_score')
                )
            
            period_result = PeriodValidationResult(
                period_name=period_data['period_name'],
                period_description=period_data['period_description'],
                start_date=period_data['start_date'],
                end_date=period_data['end_date'],
                expected_regime=period_data['expected_regime'],
                stress_level=period_data['stress_level'],
                volatility_expectation=period_data['volatility_expectation'],
                tailwind_stability=period_data['tailwind_stability'],
                validation_status=ValidationStatus(period_data['validation_status']),
                overall_score=period_data['overall_score'],
                components_passed=period_data['components_passed'],
                total_components=period_data['total_components'],
                regime_memory_metrics=create_metrics(period_data.get('regime_memory_metrics')),
                tailwind_engine_metrics=create_metrics(period_data.get('tailwind_engine_metrics')),
                no_edge_detector_metrics=create_metrics(period_data.get('no_edge_detector_metrics')),
                capital_allocator_metrics=create_metrics(period_data.get('capital_allocator_metrics')),
                period_issues=period_data.get('period_issues', []),
                data_availability=period_data.get('data_availability', {}),
                validation_timestamp=period_data.get('validation_timestamp'),
                validation_duration_ms=period_data.get('validation_duration_ms')
            )
            result.period_results[period_name] = period_result
        
        # Add component consistency analysis
        for component_name, consistency_data in data['component_consistency'].items():
            consistency_analysis = ComponentConsistencyAnalysis(
                component_name=consistency_data['component_name'],
                consistency_level=ConsistencyLevel(consistency_data['consistency_level']),
                consistency_score=consistency_data['consistency_score'],
                coefficient_of_variation=consistency_data['coefficient_of_variation'],
                score_range=consistency_data['score_range'],
                score_range_normalized=consistency_data['score_range_normalized'],
                mean_score=consistency_data['mean_score'],
                std_score=consistency_data['std_score'],
                min_score=consistency_data['min_score'],
                max_score=consistency_data['max_score'],
                pass_rate=consistency_data['pass_rate'],
                pass_consistency=consistency_data['pass_consistency'],
                periods_analyzed=consistency_data['periods_analyzed'],
                best_period=consistency_data.get('best_period'),
                worst_period=consistency_data.get('worst_period'),
                period_scores=consistency_data.get('period_scores', {}),
                regime_dependence_level=RegimeDependenceLevel(consistency_data['regime_dependence_level']) if consistency_data.get('regime_dependence_level') else None,
                regime_dependence_score=consistency_data.get('regime_dependence_score'),
                regime_variance=consistency_data.get('regime_variance'),
                regime_range=consistency_data.get('regime_range'),
                best_regime=consistency_data.get('best_regime'),
                worst_regime=consistency_data.get('worst_regime'),
                overfitting_risk_level=OverfittingRiskLevel(consistency_data['overfitting_risk_level']) if consistency_data.get('overfitting_risk_level') else None,
                overfitting_risk_score=consistency_data.get('overfitting_risk_score'),
                risk_factors=consistency_data.get('risk_factors', []),
                temporal_correlation=consistency_data.get('temporal_correlation'),
                outlier_periods=consistency_data.get('outlier_periods', [])
            )
            result.component_consistency[component_name] = consistency_analysis
        
        # Add variance attribution
        if data.get('variance_attribution'):
            variance_data = data['variance_attribution']
            result.variance_attribution = VarianceAttributionAnalysis(
                overall_variance=variance_data['overall_variance'],
                overall_std=variance_data['overall_std'],
                overall_cv=variance_data['overall_cv'],
                component_variance_contribution=variance_data.get('component_variance_contribution', {}),
                variance_attribution_pct=variance_data.get('variance_attribution_pct', {}),
                high_variance_components=variance_data.get('high_variance_components', []),
                periods_analyzed=variance_data['periods_analyzed'],
                total_contribution=variance_data['total_contribution'],
                unexplained_variance=variance_data['unexplained_variance']
            )
        
        # Add recommendations
        for rec_data in data.get('recommendations', []):
            recommendation = ValidationRecommendation(
                recommendation_type=rec_data['recommendation_type'],
                priority=rec_data['priority'],
                component=rec_data.get('component'),
                issue_description=rec_data.get('issue_description', ''),
                recommendation_text=rec_data.get('recommendation_text', ''),
                expected_impact=rec_data.get('expected_impact'),
                implementation_effort=rec_data.get('implementation_effort')
            )
            result.recommendations.append(recommendation)
        
        return result
    
    @classmethod
    def from_json_file(cls, filepath: str) -> 'MultiTimelineValidationResult':
        """Load from JSON file"""
        with open(filepath, 'r') as f:
            data = json.load(f)
        return cls.from_dict(data)
    
    def to_dataframe(self) -> pd.DataFrame:
        """Convert to pandas DataFrame for analysis"""
        
        rows = []
        
        for period_name, period_result in self.period_results.items():
            for component_name, metrics in period_result.get_all_component_metrics().items():
                rows.append({
                    'period': period_name,
                    'component': component_name,
                    'validation_passed': metrics.validation_passed,
                    'overall_score': metrics.overall_score,
                    'confidence_score': metrics.confidence_score,
                    'accuracy_score': metrics.accuracy_score,
                    'stability_score': metrics.stability_score,
                    'appropriateness_score': metrics.appropriateness_score,
                    'performance_score': metrics.performance_score,
                    'risk_adjusted_score': metrics.risk_adjusted_score,
                    'correlation_score': metrics.correlation_score,
                    'consistency_score': metrics.consistency_score,
                    'predictive_score': metrics.predictive_score,
                    'issues_count': len(metrics.issues),
                    'warnings_count': len(metrics.warnings),
                    'period_overall_score': period_result.overall_score,
                    'period_status': period_result.validation_status.value,
                    'expected_regime': period_result.expected_regime,
                    'stress_level': period_result.stress_level,
                    'validation_timestamp': self.validation_timestamp
                })
        
        return pd.DataFrame(rows)
    
    def generate_summary_report(self) -> str:
        """Generate a human-readable summary report"""
        
        report = []
        report.append("=" * 70)
        report.append("📊 MULTI-TIMELINE VALIDATION SUMMARY REPORT")
        report.append("=" * 70)
        
        # Overall results
        report.append(f"🎯 Overall Status: {self.overall_validation_status.value.upper()}")
        report.append(f"📈 Overall Consistency: {self.overall_consistency_level.value.upper()} ({self.overall_consistency_score:.3f})")
        report.append(f"📊 Success Rate: {self.success_rate:.1%} ({self.periods_passed}/{self.periods_tested} periods)")
        
        # Period results
        report.append(f"\n📋 Period Results:")
        for period_name, period_result in self.period_results.items():
            status_icon = "✅" if period_result.validation_status == ValidationStatus.PASSED else "❌"
            report.append(f"   {status_icon} {period_result.period_description}: {period_result.overall_score:.3f}")
        
        # Component performance
        report.append(f"\n🔧 Component Performance:")
        for component_name, success_rate in self.component_success_rates.items():
            consistency = self.component_consistency.get(component_name)
            if consistency:
                report.append(f"   • {component_name}: {success_rate:.1%} success, {consistency.consistency_level.value} consistency")
        
        # High priority recommendations
        high_priority_recs = self.get_high_priority_recommendations()
        if high_priority_recs:
            report.append(f"\n⚠️ High Priority Recommendations:")
            for rec in high_priority_recs:
                report.append(f"   • {rec.component or 'System'}: {rec.issue_description}")
        
        # Failed periods
        if self.failed_periods:
            report.append(f"\n❌ Failed Periods:")
            for period_name in self.failed_periods:
                period_result = self.period_results[period_name]
                report.append(f"   • {period_result.period_description}: {len(period_result.period_issues)} issues")
        
        report.append("=" * 70)
        
        return "\n".join(report)

def create_sample_validation_result() -> MultiTimelineValidationResult:
    """Create a sample validation result for testing"""
    
    from uuid import uuid4
    
    # Create main result
    result = MultiTimelineValidationResult(
        validation_id=str(uuid4()),
        validation_timestamp=datetime.now().isoformat(),
        validator_version="4.3.1",
        overall_validation_status=ValidationStatus.PASSED,
        overall_consistency_score=0.75,
        overall_consistency_level=ConsistencyLevel.MEDIUM,
        periods_tested=0,
        periods_passed=0,
        periods_failed=0,
        success_rate=0.0
    )
    
    # Add sample period result
    sample_metrics = ComponentValidationMetrics(
        validation_passed=True,
        overall_score=0.8,
        confidence_score=0.75,
        accuracy_score=0.8,
        issues=[]
    )
    
    sample_period = PeriodValidationResult(
        period_name="crisis_2008",
        period_description="Financial Crisis 2008",
        start_date="2008-09-01",
        end_date="2009-03-31",
        expected_regime="Crisis",
        stress_level="very_high",
        volatility_expectation="high",
        tailwind_stability="low",
        validation_status=ValidationStatus.PASSED,
        overall_score=0.75,
        components_passed=3,
        total_components=4,
        regime_memory_metrics=sample_metrics,
        validation_timestamp=datetime.now().isoformat()
    )
    
    result.add_period_result(sample_period)
    
    # Add sample component consistency
    sample_consistency = ComponentConsistencyAnalysis(
        component_name="regime_memory_system",
        consistency_level=ConsistencyLevel.HIGH,
        consistency_score=0.85,
        coefficient_of_variation=0.15,
        score_range=0.2,
        score_range_normalized=0.25,
        mean_score=0.8,
        std_score=0.12,
        min_score=0.7,
        max_score=0.9,
        pass_rate=0.8,
        pass_consistency=0.9,
        periods_analyzed=5
    )
    
    result.add_component_consistency(sample_consistency)
    
    # Add sample recommendation
    sample_recommendation = ValidationRecommendation(
        recommendation_type="consistency",
        priority="medium",
        component="simple_tailwind_engine",
        issue_description="Moderate consistency across periods",
        recommendation_text="Consider adaptive thresholds for different market regimes"
    )
    
    result.add_recommendation(sample_recommendation)
    
    result.calculate_overall_metrics()
    
    return result

def main():
    """Demo the MultiTimelineValidationResult data model"""
    
    print("📊 MULTI-TIMELINE VALIDATION RESULT DATA MODEL DEMO")
    print("=" * 70)
    
    # Create sample validation result
    sample_result = create_sample_validation_result()
    
    print("✅ Created sample validation result")
    print(f"   Validation ID: {sample_result.validation_id}")
    print(f"   Overall Status: {sample_result.overall_validation_status.value}")
    print(f"   Consistency Level: {sample_result.overall_consistency_level.value}")
    print(f"   Periods Tested: {sample_result.periods_tested}")
    print(f"   Components Analyzed: {len(sample_result.components_analyzed)}")
    print(f"   Recommendations: {len(sample_result.recommendations)}")
    
    # Test serialization
    print(f"\n🔄 Testing serialization...")
    json_str = sample_result.to_json()
    print(f"   JSON length: {len(json_str)} characters")
    
    # Test deserialization
    reconstructed = MultiTimelineValidationResult.from_dict(json.loads(json_str))
    print(f"   ✅ Deserialization successful")
    print(f"   Reconstructed ID: {reconstructed.validation_id}")
    
    # Test DataFrame conversion
    print(f"\n📊 Testing DataFrame conversion...")
    df = sample_result.to_dataframe()
    print(f"   DataFrame shape: {df.shape}")
    print(f"   Columns: {list(df.columns)}")
    
    # Generate summary report
    print(f"\n📋 Generating summary report...")
    summary = sample_result.generate_summary_report()
    print(summary)
    
    print(f"\n✅ MultiTimelineValidationResult data model demo completed!")

if __name__ == "__main__":
    main()