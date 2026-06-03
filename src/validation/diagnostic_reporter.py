"""
Diagnostic Reporter

Generates detailed diagnostics when inconsistencies are detected in simulations.
Identifies specific Phase 3 components affected, provides actionable recommendations
for improvement, and creates institutional-grade diagnostic reports.

This reporter provides:
- Detailed diagnostic reports for simulation inconsistencies
- Phase 3 component impact analysis
- Actionable recommendations for improvement
- Institutional-grade documentation
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, asdict
import json
import logging
from pathlib import Path

from src.utils.data_standards import validate_schema, standardize_dataframe
from src.validation.simulation_fidelity_monitor import (
    SimulationFidelityResult, UnrealisticBehaviorDetection, 
    Phase3ComponentImpact, DiagnosticInformation, ConsistencyScore
)
from src.validation.statistical_consistency_checker import StatisticalConsistencyResult

logger = logging.getLogger(__name__)

@dataclass
class DiagnosticSummary:
    """Summary of diagnostic findings"""
    total_inconsistencies: int
    critical_inconsistencies: int
    high_severity_inconsistencies: int
    affected_phase3_components: List[str]
    primary_root_causes: List[str]
    overall_severity: str
    recommendation_priority: str

@dataclass
class ComponentDiagnostic:
    """Diagnostic information for specific component"""
    component_name: str
    health_status: str  # 'healthy', 'degraded', 'impaired', 'critical'
    specific_issues: List[str]
    impact_on_functionality: List[str]
    recommended_fixes: List[str]
    estimated_fix_effort: str  # 'low', 'medium', 'high', 'extensive'

@dataclass
class InstitutionalDiagnosticReport:
    """Institutional-grade diagnostic report"""
    report_id: str
    generation_timestamp: datetime
    simulation_id: str
    executive_summary: str
    diagnostic_summary: DiagnosticSummary
    detailed_findings: Dict[str, Any]
    component_diagnostics: List[ComponentDiagnostic]
    statistical_evidence: Dict[str, Any]
    remediation_plan: Dict[str, Any]
    risk_assessment: Dict[str, Any]
    compliance_notes: List[str]
    appendices: Dict[str, Any]

class DiagnosticReporter:
    """
    Generates comprehensive diagnostic reports for simulation inconsistencies
    
    Provides detailed analysis of inconsistencies, their impact on Phase 3 components,
    and actionable recommendations for improvement.
    """
    
    def __init__(self, output_directory: Optional[str] = None):
        self.output_directory = Path(output_directory) if output_directory else Path("data/diagnostics")
        self.output_directory.mkdir(parents=True, exist_ok=True)
        
        # Severity classification thresholds
        self.severity_thresholds = {
            'critical': 0.90,  # Issues that make simulation unusable
            'high': 0.75,      # Issues that significantly impact reliability
            'medium': 0.50,    # Issues that moderately impact quality
            'low': 0.25        # Minor issues that slightly impact quality
        }
        
        # Component health classification
        self.health_thresholds = {
            'healthy': 0.85,
            'degraded': 0.70,
            'impaired': 0.50,
            'critical': 0.30
        }
        
        # Fix effort estimation
        self.fix_effort_mapping = {
            'parameter_adjustment': 'low',
            'model_recalibration': 'medium',
            'algorithm_modification': 'high',
            'architecture_change': 'extensive'
        }
        
    def generate_diagnostic_report(
        self,
        simulation_fidelity_result: SimulationFidelityResult,
        statistical_consistency_result: Optional[StatisticalConsistencyResult] = None,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> InstitutionalDiagnosticReport:
        """
        Generate comprehensive diagnostic report
        
        Args:
            simulation_fidelity_result: Results from simulation fidelity monitoring
            statistical_consistency_result: Results from statistical consistency checking
            additional_context: Additional context information
            
        Returns:
            Complete institutional-grade diagnostic report
        """
        logger.info(f"Generating diagnostic report for simulation {simulation_fidelity_result.simulation_id}")
        
        try:
            # Generate report ID
            report_id = f"DIAG_{simulation_fidelity_result.simulation_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # Create diagnostic summary
            diagnostic_summary = self._create_diagnostic_summary(
                simulation_fidelity_result, statistical_consistency_result
            )
            
            # Generate executive summary
            executive_summary = self._generate_executive_summary(
                simulation_fidelity_result, diagnostic_summary
            )
            
            # Create detailed findings
            detailed_findings = self._create_detailed_findings(
                simulation_fidelity_result, statistical_consistency_result
            )
            
            # Generate component diagnostics
            component_diagnostics = self._generate_component_diagnostics(
                simulation_fidelity_result.phase3_component_impacts
            )
            
            # Compile statistical evidence
            statistical_evidence = self._compile_statistical_evidence(
                simulation_fidelity_result, statistical_consistency_result
            )
            
            # Create remediation plan
            remediation_plan = self._create_remediation_plan(
                simulation_fidelity_result, component_diagnostics
            )
            
            # Perform risk assessment
            risk_assessment = self._perform_risk_assessment(
                simulation_fidelity_result, diagnostic_summary
            )
            
            # Generate compliance notes
            compliance_notes = self._generate_compliance_notes(
                simulation_fidelity_result, diagnostic_summary
            )
            
            # Create appendices
            appendices = self._create_appendices(
                simulation_fidelity_result, statistical_consistency_result, additional_context
            )
            
            # Assemble final report
            report = InstitutionalDiagnosticReport(
                report_id=report_id,
                generation_timestamp=datetime.now(),
                simulation_id=simulation_fidelity_result.simulation_id,
                executive_summary=executive_summary,
                diagnostic_summary=diagnostic_summary,
                detailed_findings=detailed_findings,
                component_diagnostics=component_diagnostics,
                statistical_evidence=statistical_evidence,
                remediation_plan=remediation_plan,
                risk_assessment=risk_assessment,
                compliance_notes=compliance_notes,
                appendices=appendices
            )
            
            # Save report
            self._save_report(report)
            
            logger.info(f"Diagnostic report {report_id} generated successfully")
            return report
            
        except Exception as e:
            logger.error(f"Diagnostic report generation failed: {str(e)}")
            raise
    
    def _create_diagnostic_summary(
        self,
        fidelity_result: SimulationFidelityResult,
        statistical_result: Optional[StatisticalConsistencyResult]
    ) -> DiagnosticSummary:
        """Create summary of diagnostic findings"""
        
        # Count inconsistencies by severity
        total_inconsistencies = len(fidelity_result.unrealistic_behaviors)
        critical_inconsistencies = len([b for b in fidelity_result.unrealistic_behaviors if b.severity == 'critical'])
        high_severity_inconsistencies = len([b for b in fidelity_result.unrealistic_behaviors if b.severity == 'high'])
        
        # Identify affected Phase 3 components
        affected_components = [impact.component_name for impact in fidelity_result.phase3_component_impacts]
        
        # Identify primary root causes
        primary_causes = []
        if fidelity_result.diagnostic_information:
            primary_causes.append(fidelity_result.diagnostic_information.root_cause_analysis)
        
        # Add statistical consistency issues
        if statistical_result and statistical_result.critical_violations:
            primary_causes.extend(statistical_result.critical_violations[:3])  # Top 3
        
        # Determine overall severity
        if critical_inconsistencies > 0:
            overall_severity = 'critical'
        elif high_severity_inconsistencies > 2:
            overall_severity = 'high'
        elif total_inconsistencies > 5:
            overall_severity = 'medium'
        else:
            overall_severity = 'low'
        
        # Determine recommendation priority
        if overall_severity in ['critical', 'high']:
            recommendation_priority = 'immediate'
        elif overall_severity == 'medium':
            recommendation_priority = 'high'
        else:
            recommendation_priority = 'normal'
        
        return DiagnosticSummary(
            total_inconsistencies=total_inconsistencies,
            critical_inconsistencies=critical_inconsistencies,
            high_severity_inconsistencies=high_severity_inconsistencies,
            affected_phase3_components=affected_components,
            primary_root_causes=primary_causes,
            overall_severity=overall_severity,
            recommendation_priority=recommendation_priority
        )
    
    def _generate_executive_summary(
        self,
        fidelity_result: SimulationFidelityResult,
        diagnostic_summary: DiagnosticSummary
    ) -> str:
        """Generate executive summary"""
        
        summary_parts = []
        
        # Overall assessment
        summary_parts.append(f"Simulation {fidelity_result.simulation_id} fidelity assessment: {fidelity_result.overall_fidelity_rating.upper()}")
        
        # Key findings
        if diagnostic_summary.critical_inconsistencies > 0:
            summary_parts.append(f"CRITICAL: {diagnostic_summary.critical_inconsistencies} critical inconsistencies detected that render simulation results unreliable.")
        elif diagnostic_summary.high_severity_inconsistencies > 0:
            summary_parts.append(f"HIGH PRIORITY: {diagnostic_summary.high_severity_inconsistencies} high-severity issues detected that significantly impact simulation quality.")
        elif diagnostic_summary.total_inconsistencies > 0:
            summary_parts.append(f"MODERATE: {diagnostic_summary.total_inconsistencies} inconsistencies detected with moderate impact on simulation quality.")
        else:
            summary_parts.append("No significant inconsistencies detected. Simulation quality is acceptable.")
        
        # Phase 3 component impact
        if diagnostic_summary.affected_phase3_components:
            components_str = ", ".join(diagnostic_summary.affected_phase3_components)
            summary_parts.append(f"Phase 3 components affected: {components_str}")
        
        # Recommendation urgency
        if diagnostic_summary.recommendation_priority == 'immediate':
            summary_parts.append("IMMEDIATE ACTION REQUIRED: Simulation should not be used until critical issues are resolved.")
        elif diagnostic_summary.recommendation_priority == 'high':
            summary_parts.append("HIGH PRIORITY: Issues should be addressed before relying on simulation results.")
        else:
            summary_parts.append("NORMAL PRIORITY: Issues should be addressed in next maintenance cycle.")
        
        # Approval status
        approval_status = "APPROVED" if fidelity_result.simulation_approved else "NOT APPROVED"
        summary_parts.append(f"Simulation approval status: {approval_status}")
        
        return " ".join(summary_parts)
    
    def _create_detailed_findings(
        self,
        fidelity_result: SimulationFidelityResult,
        statistical_result: Optional[StatisticalConsistencyResult]
    ) -> Dict[str, Any]:
        """Create detailed findings section"""
        
        findings = {}
        
        # Fidelity findings
        findings['fidelity_assessment'] = {
            'overall_rating': fidelity_result.overall_fidelity_rating,
            'consistency_scores': asdict(fidelity_result.consistency_score),
            'approval_status': fidelity_result.simulation_approved
        }
        
        # Unrealistic behavior findings
        findings['unrealistic_behaviors'] = []
        for behavior in fidelity_result.unrealistic_behaviors:
            findings['unrealistic_behaviors'].append({
                'type': behavior.behavior_type,
                'severity': behavior.severity,
                'description': behavior.description,
                'affected_assets': behavior.affected_assets,
                'statistical_evidence': behavior.statistical_evidence,
                'detection_time': behavior.detection_timestamp.isoformat()
            })
        
        # Statistical consistency findings
        if statistical_result:
            findings['statistical_consistency'] = {
                'overall_consistency': statistical_result.overall_statistical_consistency,
                'correlation_consistency': asdict(statistical_result.correlation_consistency),
                'volatility_consistency': asdict(statistical_result.volatility_consistency),
                'distribution_consistency': asdict(statistical_result.distribution_consistency),
                'regime_similarity_stability': asdict(statistical_result.regime_similarity_stability),
                'critical_violations': statistical_result.critical_violations
            }
        
        # Diagnostic information
        if fidelity_result.diagnostic_information:
            findings['diagnostic_analysis'] = {
                'inconsistency_type': fidelity_result.diagnostic_information.inconsistency_type,
                'root_cause_analysis': fidelity_result.diagnostic_information.root_cause_analysis,
                'statistical_tests': fidelity_result.diagnostic_information.statistical_tests,
                'data_quality_issues': fidelity_result.diagnostic_information.data_quality_issues,
                'model_parameter_issues': fidelity_result.diagnostic_information.model_parameter_issues,
                'temporal_issues': fidelity_result.diagnostic_information.temporal_issues
            }
        
        return findings
    
    def _generate_component_diagnostics(
        self,
        phase3_impacts: List[Phase3ComponentImpact]
    ) -> List[ComponentDiagnostic]:
        """Generate diagnostics for each affected component"""
        
        diagnostics = []
        
        for impact in phase3_impacts:
            # Determine health status
            health_status = self._determine_component_health(impact)
            
            # Extract specific issues
            specific_issues = [impact.impact_description]
            
            # Map functionality impacts
            impact_on_functionality = impact.affected_functionality
            
            # Map recommended fixes
            recommended_fixes = impact.recommended_actions
            
            # Estimate fix effort
            fix_effort = self._estimate_fix_effort(impact)
            
            diagnostic = ComponentDiagnostic(
                component_name=impact.component_name,
                health_status=health_status,
                specific_issues=specific_issues,
                impact_on_functionality=impact_on_functionality,
                recommended_fixes=recommended_fixes,
                estimated_fix_effort=fix_effort
            )
            
            diagnostics.append(diagnostic)
        
        return diagnostics
    
    def _determine_component_health(self, impact: Phase3ComponentImpact) -> str:
        """Determine component health status"""
        
        severity_to_health = {
            'critical': 'critical',
            'high': 'impaired',
            'medium': 'degraded',
            'low': 'degraded',
            'none': 'healthy'
        }
        
        return severity_to_health.get(impact.impact_severity, 'degraded')
    
    def _estimate_fix_effort(self, impact: Phase3ComponentImpact) -> str:
        """Estimate effort required to fix component issues"""
        
        # Analyze recommended actions to estimate effort
        actions = [action.lower() for action in impact.recommended_actions]
        
        if any('architecture' in action or 'redesign' in action for action in actions):
            return 'extensive'
        elif any('algorithm' in action or 'methodology' in action for action in actions):
            return 'high'
        elif any('calibrate' in action or 'model' in action for action in actions):
            return 'medium'
        else:
            return 'low'
    
    def _compile_statistical_evidence(
        self,
        fidelity_result: SimulationFidelityResult,
        statistical_result: Optional[StatisticalConsistencyResult]
    ) -> Dict[str, Any]:
        """Compile statistical evidence"""
        
        evidence = {}
        
        # Fidelity evidence
        evidence['consistency_scores'] = asdict(fidelity_result.consistency_score)
        
        # Behavior evidence
        evidence['behavior_statistics'] = {}
        for behavior in fidelity_result.unrealistic_behaviors:
            behavior_type = behavior.behavior_type
            if behavior_type not in evidence['behavior_statistics']:
                evidence['behavior_statistics'][behavior_type] = []
            evidence['behavior_statistics'][behavior_type].append(behavior.statistical_evidence)
        
        # Statistical consistency evidence
        if statistical_result:
            evidence['statistical_tests'] = {
                'overall_consistency': statistical_result.overall_statistical_consistency,
                'component_scores': {
                    'correlation': statistical_result.correlation_consistency.overall_correlation_consistency,
                    'volatility': statistical_result.volatility_consistency.overall_volatility_consistency,
                    'distribution': statistical_result.distribution_consistency.overall_distribution_consistency,
                    'regime_similarity': statistical_result.regime_similarity_stability.overall_similarity_stability
                }
            }
        
        # Diagnostic test results
        if fidelity_result.diagnostic_information and fidelity_result.diagnostic_information.statistical_tests:
            evidence['diagnostic_tests'] = fidelity_result.diagnostic_information.statistical_tests
        
        return evidence
    
    def _create_remediation_plan(
        self,
        fidelity_result: SimulationFidelityResult,
        component_diagnostics: List[ComponentDiagnostic]
    ) -> Dict[str, Any]:
        """Create remediation plan"""
        
        plan = {
            'immediate_actions': [],
            'short_term_actions': [],
            'long_term_actions': [],
            'monitoring_recommendations': [],
            'validation_requirements': []
        }
        
        # Categorize actions by urgency
        critical_components = [d for d in component_diagnostics if d.health_status == 'critical']
        impaired_components = [d for d in component_diagnostics if d.health_status == 'impaired']
        
        # Immediate actions for critical issues
        if critical_components:
            plan['immediate_actions'].append("Suspend use of simulation until critical issues resolved")
            for comp in critical_components:
                plan['immediate_actions'].extend(comp.recommended_fixes)
        
        # Short-term actions for high-priority issues
        if impaired_components:
            for comp in impaired_components:
                plan['short_term_actions'].extend(comp.recommended_fixes)
        
        # Long-term actions for general improvements
        degraded_components = [d for d in component_diagnostics if d.health_status == 'degraded']
        for comp in degraded_components:
            plan['long_term_actions'].extend(comp.recommended_fixes)
        
        # Add general recommendations
        if fidelity_result.diagnostic_information:
            plan['long_term_actions'].extend(fidelity_result.diagnostic_information.recommendations)
        
        # Monitoring recommendations
        plan['monitoring_recommendations'] = [
            "Implement continuous fidelity monitoring",
            "Set up automated alerts for consistency score degradation",
            "Regular validation against historical data",
            "Monitor Phase 3 component performance metrics"
        ]
        
        # Validation requirements
        plan['validation_requirements'] = [
            "Re-run fidelity assessment after implementing fixes",
            "Validate against multiple historical periods",
            "Perform stress testing of corrected components",
            "Document all changes and their impact"
        ]
        
        return plan
    
    def _perform_risk_assessment(
        self,
        fidelity_result: SimulationFidelityResult,
        diagnostic_summary: DiagnosticSummary
    ) -> Dict[str, Any]:
        """Perform risk assessment"""
        
        assessment = {
            'operational_risk': 'low',
            'model_risk': 'low',
            'reputational_risk': 'low',
            'regulatory_risk': 'low',
            'risk_factors': [],
            'mitigation_strategies': []
        }
        
        # Assess operational risk
        if diagnostic_summary.critical_inconsistencies > 0:
            assessment['operational_risk'] = 'high'
            assessment['risk_factors'].append("Critical simulation inconsistencies could lead to poor decision making")
        elif diagnostic_summary.high_severity_inconsistencies > 2:
            assessment['operational_risk'] = 'medium'
            assessment['risk_factors'].append("Multiple high-severity issues could impact operational effectiveness")
        
        # Assess model risk
        if not fidelity_result.simulation_approved:
            assessment['model_risk'] = 'high'
            assessment['risk_factors'].append("Unapproved simulation poses significant model risk")
        elif fidelity_result.overall_fidelity_rating in ['poor', 'unacceptable']:
            assessment['model_risk'] = 'medium'
            assessment['risk_factors'].append("Poor simulation fidelity increases model uncertainty")
        
        # Assess reputational risk
        if diagnostic_summary.overall_severity == 'critical':
            assessment['reputational_risk'] = 'medium'
            assessment['risk_factors'].append("Critical simulation issues could impact institutional credibility")
        
        # Assess regulatory risk
        if diagnostic_summary.affected_phase3_components:
            assessment['regulatory_risk'] = 'medium'
            assessment['risk_factors'].append("Phase 3 component issues could affect regulatory compliance")
        
        # Mitigation strategies
        assessment['mitigation_strategies'] = [
            "Implement immediate remediation plan",
            "Enhance validation procedures",
            "Increase monitoring frequency",
            "Document all issues and resolutions",
            "Consider alternative simulation approaches"
        ]
        
        return assessment
    
    def _generate_compliance_notes(
        self,
        fidelity_result: SimulationFidelityResult,
        diagnostic_summary: DiagnosticSummary
    ) -> List[str]:
        """Generate compliance-related notes"""
        
        notes = []
        
        # Simulation approval status
        if fidelity_result.simulation_approved:
            notes.append("Simulation meets minimum fidelity requirements for operational use")
        else:
            notes.append("WARNING: Simulation does not meet minimum fidelity requirements")
        
        # Documentation requirements
        notes.append("All diagnostic findings have been documented per institutional standards")
        
        # Validation requirements
        if diagnostic_summary.overall_severity in ['critical', 'high']:
            notes.append("Enhanced validation required before simulation can be approved for use")
        
        # Monitoring requirements
        notes.append("Continuous monitoring of simulation fidelity is required")
        
        # Reporting requirements
        notes.append("Diagnostic report will be retained per institutional record-keeping policies")
        
        return notes
    
    def _create_appendices(
        self,
        fidelity_result: SimulationFidelityResult,
        statistical_result: Optional[StatisticalConsistencyResult],
        additional_context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Create report appendices"""
        
        appendices = {}
        
        # Appendix A: Technical Details
        appendices['technical_details'] = {
            'simulation_period': fidelity_result.simulation_period,
            'monitoring_timestamp': fidelity_result.monitoring_timestamp.isoformat(),
            'fidelity_thresholds': {
                'excellent': 0.90,
                'good': 0.80,
                'acceptable': 0.70,
                'poor': 0.60,
                'unacceptable': 0.50
            }
        }
        
        # Appendix B: Statistical Test Results
        if statistical_result:
            appendices['statistical_tests'] = {
                'validation_period': statistical_result.validation_period,
                'validation_timestamp': statistical_result.validation_timestamp.isoformat(),
                'detailed_results': {
                    'correlation': asdict(statistical_result.correlation_consistency),
                    'volatility': asdict(statistical_result.volatility_consistency),
                    'distribution': asdict(statistical_result.distribution_consistency),
                    'regime_similarity': asdict(statistical_result.regime_similarity_stability)
                }
            }
        
        # Appendix C: Raw Data Summary
        appendices['data_summary'] = {
            'unrealistic_behaviors_count': len(fidelity_result.unrealistic_behaviors),
            'phase3_impacts_count': len(fidelity_result.phase3_component_impacts),
            'behavior_types': list(set([b.behavior_type for b in fidelity_result.unrealistic_behaviors]))
        }
        
        # Appendix D: Additional Context
        if additional_context:
            appendices['additional_context'] = additional_context
        
        return appendices
    
    def _save_report(self, report: InstitutionalDiagnosticReport) -> None:
        """Save diagnostic report to file"""
        
        try:
            # Create filename
            filename = f"{report.report_id}.json"
            filepath = self.output_directory / filename
            
            # Convert report to dictionary
            report_dict = asdict(report)
            
            # Handle datetime serialization
            report_dict['generation_timestamp'] = report.generation_timestamp.isoformat()
            
            # Save to JSON file
            with open(filepath, 'w') as f:
                json.dump(report_dict, f, indent=2, default=str)
            
            logger.info(f"Diagnostic report saved to {filepath}")
            
            # Also save a human-readable summary
            self._save_human_readable_summary(report)
            
        except Exception as e:
            logger.error(f"Failed to save diagnostic report: {str(e)}")
            raise
    
    def _save_human_readable_summary(self, report: InstitutionalDiagnosticReport) -> None:
        """Save human-readable summary"""
        
        try:
            filename = f"{report.report_id}_summary.md"
            filepath = self.output_directory / filename
            
            with open(filepath, 'w') as f:
                f.write(f"# Diagnostic Report Summary\n\n")
                f.write(f"**Report ID:** {report.report_id}\n")
                f.write(f"**Simulation ID:** {report.simulation_id}\n")
                f.write(f"**Generated:** {report.generation_timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                
                f.write(f"## Executive Summary\n\n")
                f.write(f"{report.executive_summary}\n\n")
                
                f.write(f"## Key Findings\n\n")
                f.write(f"- Total Inconsistencies: {report.diagnostic_summary.total_inconsistencies}\n")
                f.write(f"- Critical Issues: {report.diagnostic_summary.critical_inconsistencies}\n")
                f.write(f"- High Severity Issues: {report.diagnostic_summary.high_severity_inconsistencies}\n")
                f.write(f"- Overall Severity: {report.diagnostic_summary.overall_severity.upper()}\n")
                f.write(f"- Recommendation Priority: {report.diagnostic_summary.recommendation_priority.upper()}\n\n")
                
                if report.diagnostic_summary.affected_phase3_components:
                    f.write(f"## Affected Phase 3 Components\n\n")
                    for component in report.diagnostic_summary.affected_phase3_components:
                        f.write(f"- {component}\n")
                    f.write("\n")
                
                f.write(f"## Component Health Status\n\n")
                for diagnostic in report.component_diagnostics:
                    f.write(f"### {diagnostic.component_name}\n")
                    f.write(f"- **Health Status:** {diagnostic.health_status.upper()}\n")
                    f.write(f"- **Fix Effort:** {diagnostic.estimated_fix_effort.upper()}\n")
                    f.write(f"- **Issues:** {'; '.join(diagnostic.specific_issues)}\n\n")
                
                f.write(f"## Immediate Actions Required\n\n")
                for action in report.remediation_plan.get('immediate_actions', []):
                    f.write(f"- {action}\n")
                f.write("\n")
                
                f.write(f"## Risk Assessment\n\n")
                f.write(f"- **Operational Risk:** {report.risk_assessment['operational_risk'].upper()}\n")
                f.write(f"- **Model Risk:** {report.risk_assessment['model_risk'].upper()}\n")
                f.write(f"- **Reputational Risk:** {report.risk_assessment['reputational_risk'].upper()}\n")
                f.write(f"- **Regulatory Risk:** {report.risk_assessment['regulatory_risk'].upper()}\n\n")
            
            logger.info(f"Human-readable summary saved to {filepath}")
            
        except Exception as e:
            logger.warning(f"Failed to save human-readable summary: {str(e)}")
    
    def generate_trend_report(
        self,
        reports: List[InstitutionalDiagnosticReport],
        period_start: datetime,
        period_end: datetime
    ) -> Dict[str, Any]:
        """Generate trend analysis report across multiple diagnostic reports"""
        
        if not reports:
            return {'error': 'No reports provided for trend analysis'}
        
        # Filter reports by date range
        filtered_reports = [
            r for r in reports 
            if period_start <= r.generation_timestamp <= period_end
        ]
        
        if not filtered_reports:
            return {'error': 'No reports found in specified date range'}
        
        # Analyze trends
        trend_analysis = {
            'period': {'start': period_start.isoformat(), 'end': period_end.isoformat()},
            'total_reports': len(filtered_reports),
            'fidelity_trends': self._analyze_fidelity_trends(filtered_reports),
            'issue_trends': self._analyze_issue_trends(filtered_reports),
            'component_health_trends': self._analyze_component_health_trends(filtered_reports),
            'recommendations': self._generate_trend_recommendations(filtered_reports)
        }
        
        return trend_analysis
    
    def _analyze_fidelity_trends(self, reports: List[InstitutionalDiagnosticReport]) -> Dict[str, Any]:
        """Analyze fidelity trends across reports"""
        
        fidelity_ratings = [r.detailed_findings['fidelity_assessment']['overall_rating'] for r in reports]
        consistency_scores = [r.detailed_findings['fidelity_assessment']['consistency_scores']['overall_score'] for r in reports]
        
        return {
            'rating_distribution': {rating: fidelity_ratings.count(rating) for rating in set(fidelity_ratings)},
            'average_consistency_score': np.mean(consistency_scores),
            'consistency_score_trend': 'improving' if len(consistency_scores) > 1 and consistency_scores[-1] > consistency_scores[0] else 'declining',
            'best_score': max(consistency_scores),
            'worst_score': min(consistency_scores)
        }
    
    def _analyze_issue_trends(self, reports: List[InstitutionalDiagnosticReport]) -> Dict[str, Any]:
        """Analyze issue trends across reports"""
        
        total_issues = [r.diagnostic_summary.total_inconsistencies for r in reports]
        critical_issues = [r.diagnostic_summary.critical_inconsistencies for r in reports]
        
        return {
            'average_total_issues': np.mean(total_issues),
            'average_critical_issues': np.mean(critical_issues),
            'issue_trend': 'improving' if len(total_issues) > 1 and total_issues[-1] < total_issues[0] else 'worsening',
            'most_common_issues': self._find_most_common_issues(reports)
        }
    
    def _analyze_component_health_trends(self, reports: List[InstitutionalDiagnosticReport]) -> Dict[str, Any]:
        """Analyze component health trends"""
        
        all_components = {}
        for report in reports:
            for diagnostic in report.component_diagnostics:
                component = diagnostic.component_name
                if component not in all_components:
                    all_components[component] = []
                all_components[component].append(diagnostic.health_status)
        
        component_trends = {}
        for component, statuses in all_components.items():
            if len(statuses) > 1:
                # Simple trend analysis
                health_scores = {'healthy': 4, 'degraded': 3, 'impaired': 2, 'critical': 1}
                scores = [health_scores.get(status, 0) for status in statuses]
                trend = 'improving' if scores[-1] > scores[0] else 'declining' if scores[-1] < scores[0] else 'stable'
                component_trends[component] = {
                    'trend': trend,
                    'current_status': statuses[-1],
                    'status_history': statuses
                }
        
        return component_trends
    
    def _find_most_common_issues(self, reports: List[InstitutionalDiagnosticReport]) -> List[str]:
        """Find most common issues across reports"""
        
        issue_counts = {}
        for report in reports:
            behaviors = report.detailed_findings.get('unrealistic_behaviors', [])
            for behavior in behaviors:
                issue_type = behavior['type']
                issue_counts[issue_type] = issue_counts.get(issue_type, 0) + 1
        
        # Return top 5 most common issues
        sorted_issues = sorted(issue_counts.items(), key=lambda x: x[1], reverse=True)
        return [issue for issue, count in sorted_issues[:5]]
    
    def _generate_trend_recommendations(self, reports: List[InstitutionalDiagnosticReport]) -> List[str]:
        """Generate recommendations based on trends"""
        
        recommendations = []
        
        # Analyze overall trend
        recent_reports = reports[-3:] if len(reports) >= 3 else reports
        avg_recent_issues = np.mean([r.diagnostic_summary.total_inconsistencies for r in recent_reports])
        
        if avg_recent_issues > 5:
            recommendations.append("Consider comprehensive review of simulation models due to persistent issues")
        
        # Check for recurring critical issues
        critical_reports = [r for r in recent_reports if r.diagnostic_summary.critical_inconsistencies > 0]
        if len(critical_reports) > len(recent_reports) * 0.5:
            recommendations.append("Implement enhanced quality control measures to prevent critical issues")
        
        # Component-specific recommendations
        component_trends = self._analyze_component_health_trends(reports)
        declining_components = [comp for comp, trend in component_trends.items() if trend['trend'] == 'declining']
        
        if declining_components:
            recommendations.append(f"Focus improvement efforts on declining components: {', '.join(declining_components)}")
        
        if not recommendations:
            recommendations.append("Continue current monitoring and improvement practices")
        
        return recommendations