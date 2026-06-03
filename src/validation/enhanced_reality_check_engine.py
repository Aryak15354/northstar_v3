"""
Enhanced Reality Check Engine - Phase 4 Integration

Builds upon the existing RealityCheckEngine with Phase 3 component validation
and advanced simulation fidelity monitoring. Integrates with:
- Phase3RealityValidator
- StatisticalConsistencyChecker  
- SimulationFidelityMonitor
- DiagnosticReporter

This enhanced engine provides institutional-grade validation that ensures
Phase 3 components maintain statistical consistency and simulation fidelity.
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Union
import logging
import json
from pathlib import Path

from src.validation.reality_check_engine import RealityCheckEngine
from src.validation.phase3_reality_validator import Phase3RealityValidator
from src.validation.statistical_consistency_checker import StatisticalConsistencyChecker
from src.validation.simulation_fidelity_monitor import SimulationFidelityMonitor
from src.validation.diagnostic_reporter import DiagnosticReporter

logger = logging.getLogger(__name__)

class EnhancedRealityCheckEngine(RealityCheckEngine):
    """
    Enhanced Reality Check Engine with Phase 3 Integration
    
    Extends the original 12 critical constraints with Phase 3 component validation:
    - Phase 3 regime memory validation
    - Phase 3 tailwind engine validation
    - Phase 3 NO_EDGE detector validation
    - Phase 3 anticipatory capital allocator validation
    - Advanced simulation fidelity monitoring
    - Statistical consistency validation
    - Comprehensive diagnostic reporting
    """
    
    def __init__(self, output_directory: Optional[str] = None):
        super().__init__()
        
        self.name = "Enhanced Reality Check Engine"
        self.version = "2.0"
        
        # Initialize Phase 3 validation components
        self.phase3_validator = Phase3RealityValidator()
        self.statistical_checker = StatisticalConsistencyChecker()
        self.fidelity_monitor = SimulationFidelityMonitor()
        self.diagnostic_reporter = DiagnosticReporter(output_directory)
        
        # Enhanced constraint thresholds for Phase 3 components
        self.phase3_constraints = {
            'regime_memory_accuracy_min': 0.75,           # Min 75% regime classification accuracy
            'tailwind_calculation_accuracy_min': 0.80,    # Min 80% tailwind calculation accuracy
            'no_edge_detection_precision_min': 0.70,      # Min 70% NO_EDGE detection precision
            'anticipatory_positioning_accuracy_min': 0.65, # Min 65% anticipatory positioning accuracy
            'simulation_fidelity_min': 0.70,              # Min 70% simulation fidelity score
            'statistical_consistency_min': 0.75,          # Min 75% statistical consistency
            'phase3_component_health_min': 0.80           # Min 80% Phase 3 component health
        }
        
        # Update paths for enhanced validation
        self.paths.update({
            'phase3_validation_results': 'data/validation/phase3_validation_results.json',
            'simulation_fidelity_results': 'data/validation/simulation_fidelity_results.json',
            'statistical_consistency_results': 'data/validation/statistical_consistency_results.json',
            'diagnostic_reports': 'data/validation/diagnostic_reports/',
            'enhanced_validation_summary': 'data/validation/enhanced_validation_summary.json'
        })
        
        # Create enhanced validation directories
        Path('data/validation/diagnostic_reports').mkdir(parents=True, exist_ok=True)
        
        logger.info(f"🔍 {self.name} v{self.version} initialized with Phase 3 integration")
        logger.info(f"💡 Enhanced components: Phase3Validator, StatisticalChecker, FidelityMonitor, DiagnosticReporter")
    
    def run_enhanced_validation(
        self,
        backtest_results: Dict,
        validation_data: Dict,
        simulation_data: Optional[pd.DataFrame] = None,
        historical_reference: Optional[pd.DataFrame] = None,
        phase3_signals: Optional[Dict[str, pd.Series]] = None
    ) -> Dict[str, Any]:
        """
        Run enhanced validation with Phase 3 component validation
        
        Args:
            backtest_results: Standard backtest results
            validation_data: Standard validation data
            simulation_data: Simulated market data for fidelity checking
            historical_reference: Historical data for consistency checking
            phase3_signals: Phase 3 component signals for validation
            
        Returns:
            Comprehensive enhanced validation results
        """
        logger.info(f"🔍 {self.name} - Running Enhanced Validation with Phase 3 Integration")
        logger.info("=" * 80)
        
        validation_timestamp = datetime.now()
        
        # Run original 12 constraints
        logger.info("📋 Running Original 12 Critical Constraints...")
        original_results = super().run_full_validation(backtest_results, validation_data)
        
        # Run Phase 3 component validation
        logger.info("\n🧠 Running Phase 3 Component Validation...")
        phase3_results = self._run_phase3_validation(
            backtest_results,
            validation_data,
            simulation_data=simulation_data,
            historical_reference=historical_reference,
            phase3_signals=phase3_signals,
        )
        
        # Run simulation fidelity monitoring
        fidelity_results = None
        if simulation_data is not None and historical_reference is not None:
            logger.info("\n📊 Running Simulation Fidelity Monitoring...")
            fidelity_results = self._run_simulation_fidelity_monitoring(
                simulation_data, historical_reference, phase3_signals
            )
        
        # Run statistical consistency checking
        statistical_results = None
        if simulation_data is not None and historical_reference is not None:
            logger.info("\n📈 Running Statistical Consistency Checking...")
            statistical_results = self._run_statistical_consistency_checking(
                simulation_data, historical_reference
            )
        
        # Generate comprehensive diagnostic report
        logger.info("\n📝 Generating Comprehensive Diagnostic Report...")
        diagnostic_report = self._generate_enhanced_diagnostic_report(
            original_results, phase3_results, fidelity_results, statistical_results
        )
        
        # Calculate enhanced validation status
        enhanced_status = self._calculate_enhanced_validation_status(
            original_results, phase3_results, fidelity_results, statistical_results
        )
        
        # Compile enhanced results
        enhanced_results = {
            'validation_timestamp': validation_timestamp,
            'enhanced_validation_status': enhanced_status,
            'original_validation': original_results,
            'phase3_validation': phase3_results,
            'simulation_fidelity': fidelity_results,
            'statistical_consistency': statistical_results,
            'diagnostic_report': diagnostic_report,
            'enhanced_recommendations': self._generate_enhanced_recommendations(
                original_results, phase3_results, fidelity_results, statistical_results
            ),
            'phase3_component_health': self._assess_phase3_component_health(
                phase3_results, fidelity_results
            )
        }
        
        # Save enhanced results
        self._save_enhanced_validation_results(enhanced_results)
        
        # Print enhanced summary
        self._print_enhanced_validation_summary(enhanced_results)
        
        return enhanced_results
    
    def _run_phase3_validation(
        self,
        backtest_results: Dict,
        validation_data: Dict,
        simulation_data: Optional[pd.DataFrame],
        historical_reference: Optional[pd.DataFrame],
        phase3_signals: Optional[Dict[str, pd.Series]],
    ) -> Dict[str, Any]:
        """Run Phase 3 component validation"""
        
        try:
            if simulation_data is None or simulation_data.empty:
                raise ValueError("simulation_data is required for Phase 3 validation in real-data-only mode")
            if historical_reference is None or historical_reference.empty:
                raise ValueError("historical_reference is required for Phase 3 validation in real-data-only mode")
            if not phase3_signals:
                phase3_data = validation_data.get("phase3_data", {}) if isinstance(validation_data, dict) else {}
                phase3_signals = phase3_data.get("phase3_signals") if isinstance(phase3_data, dict) else None
            if not phase3_signals:
                raise ValueError("phase3_signals missing; mock Phase 3 signal generation is disabled")

            # Prepare validation period
            validation_period = (
                pd.Timestamp(simulation_data.index.min()).to_pydatetime(),
                pd.Timestamp(simulation_data.index.max()).to_pydatetime(),
            )
            
            # Run Phase 3 reality validation
            phase3_validation_result = self.phase3_validator.validate_phase3_reality_consistency(
                simulation_data, historical_reference, validation_period, phase3_signals
            )
            
            # Check Phase 3 constraints
            phase3_constraint_results = self._check_phase3_constraints(phase3_validation_result)
            
            return {
                'validation_result': phase3_validation_result,
                'constraint_results': phase3_constraint_results,
                'overall_phase3_status': self._determine_phase3_status(phase3_constraint_results),
                'phase3_component_scores': self._extract_phase3_component_scores(phase3_validation_result)
            }
            
        except Exception as e:
            logger.error(f"Phase 3 validation failed: {str(e)}")
            return {
                'validation_result': None,
                'constraint_results': [],
                'overall_phase3_status': 'FAILED',
                'error': str(e)
            }
    
    def _run_simulation_fidelity_monitoring(
        self,
        simulation_data: pd.DataFrame,
        historical_reference: pd.DataFrame,
        phase3_signals: Optional[Dict[str, pd.Series]]
    ) -> Dict[str, Any]:
        """Run simulation fidelity monitoring"""
        
        try:
            simulation_id = f"SIM_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            simulation_period = (
                simulation_data.index[0] if len(simulation_data) > 0 else datetime.now() - timedelta(days=30),
                simulation_data.index[-1] if len(simulation_data) > 0 else datetime.now()
            )
            
            fidelity_result = self.fidelity_monitor.monitor_simulation_fidelity(
                simulation_id, simulation_data, historical_reference, 
                simulation_period, phase3_signals
            )
            
            # Check fidelity constraints
            fidelity_constraint_results = self._check_fidelity_constraints(fidelity_result)
            
            return {
                'fidelity_result': fidelity_result,
                'constraint_results': fidelity_constraint_results,
                'overall_fidelity_status': fidelity_result.overall_fidelity_rating,
                'simulation_approved': fidelity_result.simulation_approved
            }
            
        except Exception as e:
            logger.error(f"Simulation fidelity monitoring failed: {str(e)}")
            return {
                'fidelity_result': None,
                'constraint_results': [],
                'overall_fidelity_status': 'FAILED',
                'simulation_approved': False,
                'error': str(e)
            }
    
    def _run_statistical_consistency_checking(
        self,
        simulation_data: pd.DataFrame,
        historical_reference: pd.DataFrame
    ) -> Dict[str, Any]:
        """Run statistical consistency checking"""
        
        try:
            validation_period = (
                simulation_data.index[0] if len(simulation_data) > 0 else datetime.now() - timedelta(days=30),
                simulation_data.index[-1] if len(simulation_data) > 0 else datetime.now()
            )
            
            statistical_result = self.statistical_checker.check_statistical_consistency(
                simulation_data, historical_reference, validation_period
            )
            
            # Check statistical constraints
            statistical_constraint_results = self._check_statistical_constraints(statistical_result)
            
            return {
                'statistical_result': statistical_result,
                'constraint_results': statistical_constraint_results,
                'overall_statistical_status': self._determine_statistical_status(statistical_constraint_results),
                'consistency_score': statistical_result.overall_statistical_consistency
            }
            
        except Exception as e:
            logger.error(f"Statistical consistency checking failed: {str(e)}")
            return {
                'statistical_result': None,
                'constraint_results': [],
                'overall_statistical_status': 'FAILED',
                'consistency_score': 0.0,
                'error': str(e)
            }
    
    def _generate_enhanced_diagnostic_report(
        self,
        original_results: Dict,
        phase3_results: Dict,
        fidelity_results: Optional[Dict],
        statistical_results: Optional[Dict]
    ) -> Dict[str, Any]:
        """Generate comprehensive diagnostic report"""
        
        try:
            # Only generate diagnostic report if we have fidelity results
            if fidelity_results and fidelity_results.get('fidelity_result'):
                fidelity_result = fidelity_results['fidelity_result']
                statistical_result = statistical_results.get('statistical_result') if statistical_results else None
                
                diagnostic_report = self.diagnostic_reporter.generate_diagnostic_report(
                    fidelity_result, statistical_result, {
                        'original_validation': original_results,
                        'phase3_validation': phase3_results
                    }
                )
                
                return {
                    'report_generated': True,
                    'report_id': diagnostic_report.report_id,
                    'executive_summary': diagnostic_report.executive_summary,
                    'overall_severity': diagnostic_report.diagnostic_summary.overall_severity,
                    'recommendation_priority': diagnostic_report.diagnostic_summary.recommendation_priority,
                    'affected_components': diagnostic_report.diagnostic_summary.affected_phase3_components
                }
            else:
                return {
                    'report_generated': False,
                    'reason': 'Insufficient data for diagnostic report generation'
                }
                
        except Exception as e:
            logger.error(f"Diagnostic report generation failed: {str(e)}")
            return {
                'report_generated': False,
                'error': str(e)
            }
    
    def _check_phase3_constraints(self, phase3_result) -> List[Dict[str, Any]]:
        """Check Phase 3 component constraints"""
        
        constraint_results = []
        
        if not phase3_result:
            return constraint_results
        
        # Check regime memory accuracy
        regime_accuracy = phase3_result.regime_memory_accuracy
        constraint_results.append({
            'constraint_name': 'Phase 3 Regime Memory Accuracy',
            'passed': regime_accuracy >= self.phase3_constraints['regime_memory_accuracy_min'],
            'value': regime_accuracy,
            'threshold': self.phase3_constraints['regime_memory_accuracy_min'],
            'severity': 'HIGH' if regime_accuracy < self.phase3_constraints['regime_memory_accuracy_min'] else 'PASS'
        })
        
        # Check tailwind calculation accuracy
        tailwind_accuracy = phase3_result.tailwind_calculation_accuracy
        constraint_results.append({
            'constraint_name': 'Phase 3 Tailwind Calculation Accuracy',
            'passed': tailwind_accuracy >= self.phase3_constraints['tailwind_calculation_accuracy_min'],
            'value': tailwind_accuracy,
            'threshold': self.phase3_constraints['tailwind_calculation_accuracy_min'],
            'severity': 'HIGH' if tailwind_accuracy < self.phase3_constraints['tailwind_calculation_accuracy_min'] else 'PASS'
        })
        
        # Check NO_EDGE detection precision
        no_edge_precision = phase3_result.no_edge_detection_precision
        constraint_results.append({
            'constraint_name': 'Phase 3 NO_EDGE Detection Precision',
            'passed': no_edge_precision >= self.phase3_constraints['no_edge_detection_precision_min'],
            'value': no_edge_precision,
            'threshold': self.phase3_constraints['no_edge_detection_precision_min'],
            'severity': 'MEDIUM' if no_edge_precision < self.phase3_constraints['no_edge_detection_precision_min'] else 'PASS'
        })
        
        # Check anticipatory positioning accuracy
        anticipatory_accuracy = phase3_result.anticipatory_positioning_accuracy
        constraint_results.append({
            'constraint_name': 'Phase 3 Anticipatory Positioning Accuracy',
            'passed': anticipatory_accuracy >= self.phase3_constraints['anticipatory_positioning_accuracy_min'],
            'value': anticipatory_accuracy,
            'threshold': self.phase3_constraints['anticipatory_positioning_accuracy_min'],
            'severity': 'MEDIUM' if anticipatory_accuracy < self.phase3_constraints['anticipatory_positioning_accuracy_min'] else 'PASS'
        })
        
        return constraint_results
    
    def _check_fidelity_constraints(self, fidelity_result) -> List[Dict[str, Any]]:
        """Check simulation fidelity constraints"""
        
        constraint_results = []
        
        if not fidelity_result:
            return constraint_results
        
        # Check overall simulation fidelity
        fidelity_score = fidelity_result.consistency_score.overall_score
        constraint_results.append({
            'constraint_name': 'Simulation Fidelity Score',
            'passed': fidelity_score >= self.phase3_constraints['simulation_fidelity_min'],
            'value': fidelity_score,
            'threshold': self.phase3_constraints['simulation_fidelity_min'],
            'severity': 'CRITICAL' if fidelity_score < self.phase3_constraints['simulation_fidelity_min'] * 0.7 else 'HIGH'
        })
        
        # Check for critical unrealistic behaviors
        critical_behaviors = [b for b in fidelity_result.unrealistic_behaviors if b.severity == 'critical']
        constraint_results.append({
            'constraint_name': 'Critical Unrealistic Behaviors',
            'passed': len(critical_behaviors) == 0,
            'value': len(critical_behaviors),
            'threshold': 0,
            'severity': 'CRITICAL' if len(critical_behaviors) > 0 else 'PASS'
        })
        
        return constraint_results
    
    def _check_statistical_constraints(self, statistical_result) -> List[Dict[str, Any]]:
        """Check statistical consistency constraints"""
        
        constraint_results = []
        
        if not statistical_result:
            return constraint_results
        
        # Check overall statistical consistency
        consistency_score = statistical_result.overall_statistical_consistency
        constraint_results.append({
            'constraint_name': 'Statistical Consistency Score',
            'passed': consistency_score >= self.phase3_constraints['statistical_consistency_min'],
            'value': consistency_score,
            'threshold': self.phase3_constraints['statistical_consistency_min'],
            'severity': 'HIGH' if consistency_score < self.phase3_constraints['statistical_consistency_min'] else 'PASS'
        })
        
        # Check for critical violations
        critical_violations = len(statistical_result.critical_violations)
        constraint_results.append({
            'constraint_name': 'Critical Statistical Violations',
            'passed': critical_violations == 0,
            'value': critical_violations,
            'threshold': 0,
            'severity': 'CRITICAL' if critical_violations > 0 else 'PASS'
        })
        
        return constraint_results
    
    def _calculate_enhanced_validation_status(
        self,
        original_results: Dict,
        phase3_results: Dict,
        fidelity_results: Optional[Dict],
        statistical_results: Optional[Dict]
    ) -> str:
        """Calculate overall enhanced validation status"""
        
        # Start with original validation status
        original_status = original_results.get('validation_status', 'FAILED')
        
        # Check Phase 3 status
        phase3_status = phase3_results.get('overall_phase3_status', 'FAILED')
        
        # Check fidelity status
        fidelity_status = 'PASSED'
        if fidelity_results:
            fidelity_status = 'PASSED' if fidelity_results.get('simulation_approved', False) else 'FAILED'
        
        # Check statistical status
        statistical_status = statistical_results.get('overall_statistical_status', 'PASSED') if statistical_results else 'PASSED'
        
        # Determine overall status (all must pass for overall pass)
        all_statuses = [original_status, phase3_status, fidelity_status, statistical_status]
        
        if all(status == 'PASSED' for status in all_statuses):
            return 'PASSED'
        elif any(status == 'FAILED' for status in all_statuses):
            return 'FAILED'
        else:
            return 'WARNING'
    
    def _generate_enhanced_recommendations(
        self,
        original_results: Dict,
        phase3_results: Dict,
        fidelity_results: Optional[Dict],
        statistical_results: Optional[Dict]
    ) -> List[str]:
        """Generate enhanced recommendations"""
        
        recommendations = []
        
        # Add original recommendations
        recommendations.extend(original_results.get('recommendations', []))
        
        # Add Phase 3 specific recommendations
        if phase3_results.get('overall_phase3_status') != 'PASSED':
            recommendations.append("Improve Phase 3 component accuracy through parameter tuning and validation")
            recommendations.append("Review Phase 3 regime memory system for historical accuracy")
            recommendations.append("Calibrate Phase 3 tailwind engine calculations")
        
        # Add fidelity recommendations
        if fidelity_results and not fidelity_results.get('simulation_approved', False):
            recommendations.append("Address simulation fidelity issues before using for decision making")
            recommendations.append("Improve market simulation model to reduce unrealistic behaviors")
        
        # Add statistical recommendations
        if statistical_results and statistical_results.get('overall_statistical_status') != 'PASSED':
            recommendations.append("Improve statistical consistency of simulation models")
            recommendations.append("Address critical statistical violations in simulation")
        
        return list(set(recommendations))  # Remove duplicates
    
    def _assess_phase3_component_health(
        self,
        phase3_results: Dict,
        fidelity_results: Optional[Dict]
    ) -> Dict[str, str]:
        """Assess health of Phase 3 components"""
        
        component_health = {}
        
        # Default health assessment based on Phase 3 results
        if phase3_results.get('phase3_component_scores'):
            scores = phase3_results['phase3_component_scores']
            
            for component, score in scores.items():
                if score >= 0.85:
                    health = 'excellent'
                elif score >= 0.75:
                    health = 'good'
                elif score >= 0.60:
                    health = 'acceptable'
                elif score >= 0.40:
                    health = 'poor'
                else:
                    health = 'critical'
                
                component_health[component] = health
        
        # Override with fidelity results if available
        if fidelity_results and fidelity_results.get('fidelity_result'):
            fidelity_result = fidelity_results['fidelity_result']
            for impact in fidelity_result.phase3_component_impacts:
                component_health[impact.component_name] = impact.impact_severity
        
        return component_health
    
    def _determine_phase3_status(self, constraint_results: List[Dict]) -> str:
        """Determine Phase 3 validation status"""
        
        if not constraint_results:
            return 'FAILED'
        
        failed_constraints = [c for c in constraint_results if not c['passed']]
        critical_failures = [c for c in failed_constraints if c['severity'] == 'CRITICAL']
        
        if critical_failures:
            return 'FAILED'
        elif len(failed_constraints) > len(constraint_results) / 2:
            return 'WARNING'
        else:
            return 'PASSED'
    
    def _determine_statistical_status(self, constraint_results: List[Dict]) -> str:
        """Determine statistical consistency status"""
        
        if not constraint_results:
            return 'FAILED'
        
        failed_constraints = [c for c in constraint_results if not c['passed']]
        critical_failures = [c for c in failed_constraints if c['severity'] == 'CRITICAL']
        
        if critical_failures:
            return 'FAILED'
        elif failed_constraints:
            return 'WARNING'
        else:
            return 'PASSED'
    
    def _extract_phase3_component_scores(self, phase3_result) -> Dict[str, float]:
        """Extract Phase 3 component scores"""
        
        if not phase3_result:
            return {}
        
        return {
            'regime_memory_system': phase3_result.regime_memory_accuracy,
            'simple_tailwind_engine': phase3_result.tailwind_calculation_accuracy,
            'no_edge_detector': phase3_result.no_edge_detection_precision,
            'anticipatory_capital_allocator': phase3_result.anticipatory_positioning_accuracy
        }
    
    def _save_enhanced_validation_results(self, enhanced_results: Dict) -> None:
        """Save enhanced validation results"""
        
        try:
            # Create serializable version
            serializable_results = self._make_json_serializable(enhanced_results)
            
            with open(self.paths['enhanced_validation_summary'], 'w') as f:
                json.dump(serializable_results, f, indent=2)
            
            logger.info(f"💾 Enhanced validation results saved to {self.paths['enhanced_validation_summary']}")
            
        except Exception as e:
            logger.error(f"Failed to save enhanced validation results: {str(e)}")
    
    def _print_enhanced_validation_summary(self, enhanced_results: Dict) -> None:
        """Print enhanced validation summary"""
        
        print(f"\n📊 ENHANCED VALIDATION SUMMARY:")
        print("=" * 60)
        
        # Overall status
        status = enhanced_results['enhanced_validation_status']
        print(f"   Overall Status: {status}")
        
        # Component statuses
        original_status = enhanced_results['original_validation']['validation_status']
        phase3_status = enhanced_results['phase3_validation']['overall_phase3_status']
        
        print(f"   Original 12 Constraints: {original_status}")
        print(f"   Phase 3 Components: {phase3_status}")
        
        if enhanced_results.get('simulation_fidelity'):
            fidelity_approved = enhanced_results['simulation_fidelity']['simulation_approved']
            fidelity_status = "APPROVED" if fidelity_approved else "NOT APPROVED"
            print(f"   Simulation Fidelity: {fidelity_status}")
        
        if enhanced_results.get('statistical_consistency'):
            statistical_status = enhanced_results['statistical_consistency']['overall_statistical_status']
            print(f"   Statistical Consistency: {statistical_status}")
        
        # Component health
        component_health = enhanced_results.get('phase3_component_health', {})
        if component_health:
            print(f"\n🧠 PHASE 3 COMPONENT HEALTH:")
            for component, health in component_health.items():
                print(f"   {component}: {health.upper()}")
        
        # Diagnostic report
        diagnostic_info = enhanced_results.get('diagnostic_report', {})
        if diagnostic_info.get('report_generated'):
            print(f"\n📝 DIAGNOSTIC REPORT:")
            print(f"   Report ID: {diagnostic_info['report_id']}")
            print(f"   Severity: {diagnostic_info['overall_severity'].upper()}")
            print(f"   Priority: {diagnostic_info['recommendation_priority'].upper()}")
        
        # Top recommendations
        recommendations = enhanced_results.get('enhanced_recommendations', [])
        if recommendations:
            print(f"\n💡 TOP RECOMMENDATIONS:")
            for i, rec in enumerate(recommendations[:5], 1):
                print(f"   {i}. {rec}")
        
        print("=" * 60)
