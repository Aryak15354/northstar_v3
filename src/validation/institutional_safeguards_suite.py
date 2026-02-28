"""
Institutional Safeguards Suite - Complete Integration

This module integrates all 8 institutional-grade safeguards into a unified
system that prevents the "silent killers" that separate real institutional
systems from academic exercises.

The 8 Institutional Safeguards:
1. Truth Mode Validator - Prevents cherry-picking and bias
2. Statistical Significance Gates - Kills false alphas
3. Alpha/Leverage Separator - Separates signal from sizing tricks
4. Kill Switch Auditor - Verifies crisis protection
5. Adversarial Testing Suite - Tests system resilience
6. Death by Thousand Cuts Detector - Catches gradual decay
7. Alpha Genome Tracker - Maps alpha dependencies
8. Audit-Grade Reproducibility - Enables byte-for-byte reproduction

Author: Northstar Team
Date: 2026-01-05
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import logging
import json
from pathlib import Path

from .truth_mode_validator import TruthModeValidator, SystemFreeze
from .statistical_significance_gates import StatisticalSignificanceGates, AlphaSignificanceReport
from .alpha_leverage_separator import AlphaLeverageSeparator, AlphaLeverageMetrics
from .kill_switch_auditor import KillSwitchAuditor, KillSwitchAuditReport
from .adversarial_testing_suite import AdversarialTestingEngine, AdversarialTestSuite
from .death_by_thousand_cuts_detector import DeathByThousandCutsDetector, ThousandCutsReport
from .alpha_genome_tracker import AlphaGenomeTracker, AlphaGenomeSnapshot, AlphaSurvivalAnalysis
from .audit_grade_reproducibility import AuditGradeReproducibility, ReproducibilityArchive

try:
    from ..operation.logging_config import setup_operation_logging
except ImportError:
    # Fallback for when running as standalone
    import logging
    def setup_operation_logging():
        logging.basicConfig(level=logging.INFO)
        return logging.getLogger(__name__)


@dataclass
class InstitutionalValidationReport:
    """Comprehensive institutional validation report."""
    validation_date: datetime
    system_name: str
    
    # Truth mode results
    truth_mode_passed: bool
    truth_mode_run_id: str
    system_freeze_verified: bool
    
    # Statistical significance results
    significance_gates_passed: bool
    alpha_significance_reports: Dict[str, AlphaSignificanceReport]
    false_alpha_rate: float
    
    # Alpha/leverage separation results
    leverage_separation_completed: bool
    pure_signal_quality: float
    leverage_efficiency: float
    
    # Kill switch audit results
    kill_switch_audit_passed: bool
    crisis_survival_verified: bool
    kill_switch_effectiveness: float
    
    # Adversarial testing results
    adversarial_testing_passed: bool
    system_resilience_score: float
    vulnerability_count: int
    
    # Thousand cuts detection results
    thousand_cuts_clear: bool
    decay_score: float
    critical_decay_detected: bool
    
    # Alpha genome results
    alpha_genome_healthy: bool
    alpha_diversification_score: float
    survival_without_top_alpha: float
    
    # Reproducibility results
    reproducibility_verified: bool
    archive_created: bool
    byte_for_byte_verified: bool
    
    # Overall assessment
    institutional_grade_achieved: bool
    overall_score: float
    critical_failures: List[str]
    recommendations: List[str]


class InstitutionalSafeguardsSuite:
    """
    Complete institutional safeguards integration system.
    
    This class orchestrates all 8 institutional safeguards to provide
    comprehensive validation that prevents silent system failures.
    """
    
    def __init__(self):
        """Initialize institutional safeguards suite."""
        self.logger = setup_operation_logging()
        
        # Initialize all safeguard systems
        self.truth_mode = TruthModeValidator()
        self.significance_gates = StatisticalSignificanceGates()
        self.leverage_separator = AlphaLeverageSeparator()
        self.kill_switch_auditor = KillSwitchAuditor()
        self.adversarial_engine = AdversarialTestingEngine()
        self.thousand_cuts_detector = DeathByThousandCutsDetector()
        self.alpha_genome_tracker = AlphaGenomeTracker()
        self.reproducibility_system = AuditGradeReproducibility()
        
        self.logger.info("🏛️ Institutional Safeguards Suite initialized")
        self.logger.info("All 8 safeguards loaded and ready")
    
    def run_complete_institutional_validation(self, 
                                            system_name: str,
                                            returns: np.ndarray,
                                            signals: Dict[str, np.ndarray],
                                            costs: np.ndarray,
                                            market_data: Dict[str, np.ndarray],
                                            timestamps: List[datetime],
                                            kill_switch_log: List[Dict[str, Any]],
                                            crisis_periods: Optional[List[str]] = None) -> InstitutionalValidationReport:
        """
        Run complete institutional validation across all 8 safeguards.
        
        Args:
            system_name: Name of system being validated
            returns: Strategy returns
            signals: Dictionary of alpha signals
            costs: Transaction costs
            market_data: Market data for analysis
            timestamps: Timestamps for observations
            kill_switch_log: Kill switch activation log
            crisis_periods: Optional list of crisis periods to analyze
            
        Returns:
            InstitutionalValidationReport: Comprehensive validation results
        """
        self.logger.info("🏛️ STARTING COMPLETE INSTITUTIONAL VALIDATION")
        self.logger.info("=" * 80)
        self.logger.info(f"System: {system_name}")
        self.logger.info(f"Data Points: {len(returns)}")
        self.logger.info(f"Alpha Sources: {len(signals)}")
        self.logger.info("Running all 8 institutional safeguards...")
        
        # Start reproducible run
        run_id = self.reproducibility_system.start_reproducible_run(
            f"Institutional validation of {system_name}",
            tags=["institutional", "validation", "complete"]
        )
        
        validation_results = {}
        critical_failures = []
        
        try:
            # 1. Truth Mode Validation
            self.logger.info("🧠 Running Truth Mode Validation...")
            truth_results = self._run_truth_mode_validation()
            validation_results['truth_mode'] = truth_results
            
            if not truth_results['passed']:
                critical_failures.append("Truth Mode validation failed")
            
            # 2. Statistical Significance Gates
            self.logger.info("🔒 Running Statistical Significance Gates...")
            significance_results = self._run_significance_validation(returns, signals)
            validation_results['significance'] = significance_results
            
            if not significance_results['passed']:
                critical_failures.append("Statistical significance validation failed")
            
            # 3. Alpha/Leverage Separation
            self.logger.info("🧮 Running Alpha/Leverage Separation...")
            leverage_results = self._run_leverage_separation(returns, signals)
            validation_results['leverage'] = leverage_results
            
            # 4. Kill Switch Audit
            self.logger.info("🧯 Running Kill Switch Audit...")
            kill_switch_results = self._run_kill_switch_audit(
                returns, timestamps, kill_switch_log, crisis_periods
            )
            validation_results['kill_switch'] = kill_switch_results
            
            if not kill_switch_results['passed']:
                critical_failures.append("Kill switch audit failed")
            
            # 5. Adversarial Testing
            self.logger.info("🧪 Running Adversarial Testing...")
            adversarial_results = self._run_adversarial_testing(
                returns, signals, market_data
            )
            validation_results['adversarial'] = adversarial_results
            
            if not adversarial_results['passed']:
                critical_failures.append("Adversarial testing failed")
            
            # 6. Death by Thousand Cuts Detection
            self.logger.info("📉 Running Thousand Cuts Detection...")
            thousand_cuts_results = self._run_thousand_cuts_detection(
                returns, signals, costs, timestamps
            )
            validation_results['thousand_cuts'] = thousand_cuts_results
            
            if not thousand_cuts_results['passed']:
                critical_failures.append("Critical decay detected")
            
            # 7. Alpha Genome Tracking
            self.logger.info("🧬 Running Alpha Genome Analysis...")
            genome_results = self._run_alpha_genome_analysis(
                returns, signals, market_data, timestamps
            )
            validation_results['alpha_genome'] = genome_results
            
            # 8. Finalize Reproducibility
            self.logger.info("🧾 Finalizing Reproducibility Archive...")
            repro_results = self._finalize_reproducibility(run_id, validation_results)
            validation_results['reproducibility'] = repro_results
            
            if not repro_results['verified']:
                critical_failures.append("Reproducibility verification failed")
            
            # Calculate overall assessment
            overall_assessment = self._calculate_overall_assessment(
                validation_results, critical_failures
            )
            
            # Generate comprehensive report
            report = self._generate_institutional_report(
                system_name, validation_results, overall_assessment, critical_failures
            )
            
            self._log_final_results(report)
            return report
            
        except Exception as e:
            self.logger.error(f"Institutional validation failed: {e}")
            critical_failures.append(f"System error: {e}")
            
            # Still try to create a failure report
            return self._generate_failure_report(system_name, critical_failures, str(e))
    
    def _run_truth_mode_validation(self) -> Dict[str, Any]:
        """Run truth mode validation."""
        try:
            # Create system freeze
            freeze = self.truth_mode.create_system_freeze()
            
            # Validate freeze integrity
            integrity_verified = self.truth_mode.validate_freeze_integrity(freeze)
            
            return {
                'passed': integrity_verified,
                'run_id': freeze.run_id,
                'freeze_verified': integrity_verified,
                'freeze': freeze
            }
        except Exception as e:
            self.logger.error(f"Truth mode validation failed: {e}")
            return {
                'passed': False,
                'error': str(e),
                'run_id': None,
                'freeze_verified': False
            }
    
    def _run_significance_validation(self, returns: np.ndarray, signals: Dict[str, np.ndarray]) -> Dict[str, Any]:
        """Run statistical significance validation."""
        try:
            alpha_reports = {}
            passed_count = 0
            total_count = len(signals)
            
            for alpha_name, signal_data in signals.items():
                # Ensure same length
                min_length = min(len(returns), len(signal_data))
                returns_clean = returns[-min_length:]
                signals_clean = signal_data[-min_length:]
                
                # Run significance test
                report = self.significance_gates.validate_alpha_significance(
                    returns_clean, signals_clean, alpha_name
                )
                
                alpha_reports[alpha_name] = report
                
                if report.capital_allocation_approved:
                    passed_count += 1
            
            false_alpha_rate = 1.0 - (passed_count / total_count) if total_count > 0 else 1.0
            
            return {
                'passed': passed_count > 0,  # At least one alpha must pass
                'alpha_reports': alpha_reports,
                'false_alpha_rate': false_alpha_rate,
                'passed_count': passed_count,
                'total_count': total_count
            }
        except Exception as e:
            self.logger.error(f"Significance validation failed: {e}")
            return {
                'passed': False,
                'error': str(e),
                'alpha_reports': {},
                'false_alpha_rate': 1.0
            }
    
    def _run_leverage_separation(self, returns: np.ndarray, signals: Dict[str, np.ndarray]) -> Dict[str, Any]:
        """Run alpha/leverage separation."""
        try:
            # Use first signal for demonstration
            if not signals:
                return {'completed': False, 'error': 'No signals provided'}
            
            first_signal_name = list(signals.keys())[0]
            first_signal = signals[first_signal_name]
            
            # Ensure same length
            min_length = min(len(returns), len(first_signal))
            returns_clean = returns[-min_length:]
            signals_clean = first_signal[-min_length:]
            
            # Run separation analysis
            metrics = self.leverage_separator.separate_alpha_leverage(
                returns_clean, signals_clean, strategy_name=first_signal_name
            )
            
            return {
                'completed': True,
                'metrics': metrics,
                'pure_signal_quality': metrics.signal_quality_score,
                'leverage_efficiency': metrics.leverage_efficiency
            }
        except Exception as e:
            self.logger.error(f"Leverage separation failed: {e}")
            return {
                'completed': False,
                'error': str(e),
                'pure_signal_quality': 0.0,
                'leverage_efficiency': 0.0
            }
    
    def _run_kill_switch_audit(self, 
                             returns: np.ndarray,
                             timestamps: List[datetime],
                             kill_switch_log: List[Dict[str, Any]],
                             crisis_periods: Optional[List[str]]) -> Dict[str, Any]:
        """Run kill switch audit."""
        try:
            if not crisis_periods:
                crisis_periods = ["2008_financial_crisis"]  # Default
            
            audit_results = {}
            overall_passed = True
            
            for crisis_name in crisis_periods:
                # Create dummy NAV series
                nav_series = np.cumprod(1 + returns)
                
                try:
                    audit_report = self.kill_switch_auditor.audit_crisis_kill_switches(
                        returns, nav_series, timestamps, kill_switch_log, crisis_name
                    )
                    
                    audit_results[crisis_name] = audit_report
                    
                    if not audit_report.crisis_survival_verified:
                        overall_passed = False
                        
                except Exception as e:
                    self.logger.warning(f"Kill switch audit failed for {crisis_name}: {e}")
                    overall_passed = False
            
            return {
                'passed': overall_passed,
                'audit_results': audit_results,
                'crisis_survival_verified': overall_passed
            }
        except Exception as e:
            self.logger.error(f"Kill switch audit failed: {e}")
            return {
                'passed': False,
                'error': str(e),
                'crisis_survival_verified': False
            }
    
    def _run_adversarial_testing(self, 
                               returns: np.ndarray,
                               signals: Dict[str, np.ndarray],
                               market_data: Dict[str, np.ndarray]) -> Dict[str, Any]:
        """Run adversarial testing."""
        try:
            # Use first signal for testing
            if not signals:
                return {'passed': False, 'error': 'No signals provided'}
            
            first_signal = list(signals.values())[0]
            
            # Ensure same length
            min_length = min(len(returns), len(first_signal))
            returns_clean = returns[-min_length:]
            signals_clean = first_signal[-min_length:]
            
            # Run adversarial test suite
            test_results = self.adversarial_engine.run_adversarial_test_suite(
                returns_clean, signals_clean, market_data, {}
            )
            
            # Determine if passed (resilience score > 0.6)
            passed = test_results.overall_resilience_score > 0.6
            
            return {
                'passed': passed,
                'test_results': test_results,
                'resilience_score': test_results.overall_resilience_score,
                'vulnerability_count': len(test_results.vulnerability_assessment)
            }
        except Exception as e:
            self.logger.error(f"Adversarial testing failed: {e}")
            return {
                'passed': False,
                'error': str(e),
                'resilience_score': 0.0,
                'vulnerability_count': 999
            }
    
    def _run_thousand_cuts_detection(self, 
                                   returns: np.ndarray,
                                   signals: Dict[str, np.ndarray],
                                   costs: np.ndarray,
                                   timestamps: List[datetime]) -> Dict[str, Any]:
        """Run thousand cuts detection."""
        try:
            # Use first signal for analysis
            if not signals:
                return {'passed': False, 'error': 'No signals provided'}
            
            first_signal = list(signals.values())[0]
            
            # Ensure same length
            min_length = min(len(returns), len(first_signal), len(costs))
            returns_clean = returns[-min_length:]
            signals_clean = first_signal[-min_length:]
            costs_clean = costs[-min_length:]
            timestamps_clean = timestamps[-min_length:]
            
            # Run thousand cuts analysis
            report = self.thousand_cuts_detector.detect_thousand_cuts(
                returns_clean, signals_clean, costs_clean, timestamps_clean
            )
            
            # Pass if no critical decay detected
            passed = not report.critical_decay_detected
            
            return {
                'passed': passed,
                'report': report,
                'decay_score': report.overall_decay_score,
                'critical_decay_detected': report.critical_decay_detected
            }
        except Exception as e:
            self.logger.error(f"Thousand cuts detection failed: {e}")
            return {
                'passed': False,
                'error': str(e),
                'decay_score': 1.0,
                'critical_decay_detected': True
            }
    
    def _run_alpha_genome_analysis(self, 
                                 returns: np.ndarray,
                                 signals: Dict[str, np.ndarray],
                                 market_data: Dict[str, np.ndarray],
                                 timestamps: List[datetime]) -> Dict[str, Any]:
        """Run alpha genome analysis."""
        try:
            # Ensure same length for all signals
            min_length = min([len(returns)] + [len(s) for s in signals.values()])
            returns_clean = returns[-min_length:]
            signals_clean = {k: v[-min_length:] for k, v in signals.items()}
            timestamps_clean = timestamps[-min_length:]
            
            # Track alpha genome
            snapshot = self.alpha_genome_tracker.track_alpha_genome(
                returns_clean, signals_clean, market_data, timestamps_clean
            )
            
            # Analyze survival
            survival_analysis = self.alpha_genome_tracker.analyze_alpha_survival([snapshot])
            
            # Determine health (diversification > 0.5)
            healthy = snapshot.alpha_diversification_score > 0.5
            
            return {
                'healthy': healthy,
                'snapshot': snapshot,
                'survival_analysis': survival_analysis,
                'diversification_score': snapshot.alpha_diversification_score,
                'survival_without_top_alpha': survival_analysis.survival_without_top_alpha
            }
        except Exception as e:
            self.logger.error(f"Alpha genome analysis failed: {e}")
            return {
                'healthy': False,
                'error': str(e),
                'diversification_score': 0.0,
                'survival_without_top_alpha': 0.0
            }
    
    def _finalize_reproducibility(self, run_id: str, validation_results: Dict[str, Any]) -> Dict[str, Any]:
        """Finalize reproducibility archive."""
        try:
            # Create archive with validation results
            archive = self.reproducibility_system.finalize_reproducible_run(
                run_id, output_data=validation_results
            )
            
            # Verify archive integrity
            integrity_result = self.reproducibility_system.verify_archive_integrity(run_id)
            
            return {
                'verified': integrity_result['verified'],
                'archive': archive,
                'archive_created': True,
                'byte_for_byte_verified': integrity_result['verified']
            }
        except Exception as e:
            self.logger.error(f"Reproducibility finalization failed: {e}")
            return {
                'verified': False,
                'error': str(e),
                'archive_created': False,
                'byte_for_byte_verified': False
            }
    
    def _calculate_overall_assessment(self, 
                                    validation_results: Dict[str, Any],
                                    critical_failures: List[str]) -> Dict[str, Any]:
        """Calculate overall institutional assessment."""
        # Calculate component scores
        scores = {}
        
        # Truth mode (critical)
        scores['truth_mode'] = 1.0 if validation_results.get('truth_mode', {}).get('passed', False) else 0.0
        
        # Significance gates (critical)
        significance_data = validation_results.get('significance', {})
        scores['significance'] = 1.0 - significance_data.get('false_alpha_rate', 1.0)
        
        # Leverage separation
        leverage_data = validation_results.get('leverage', {})
        scores['leverage'] = leverage_data.get('pure_signal_quality', 0.0)
        
        # Kill switch audit (critical)
        kill_switch_data = validation_results.get('kill_switch', {})
        scores['kill_switch'] = 1.0 if kill_switch_data.get('passed', False) else 0.0
        
        # Adversarial testing (critical)
        adversarial_data = validation_results.get('adversarial', {})
        scores['adversarial'] = adversarial_data.get('resilience_score', 0.0)
        
        # Thousand cuts
        thousand_cuts_data = validation_results.get('thousand_cuts', {})
        scores['thousand_cuts'] = 1.0 - thousand_cuts_data.get('decay_score', 1.0)
        
        # Alpha genome
        genome_data = validation_results.get('alpha_genome', {})
        scores['alpha_genome'] = genome_data.get('diversification_score', 0.0)
        
        # Reproducibility (critical)
        repro_data = validation_results.get('reproducibility', {})
        scores['reproducibility'] = 1.0 if repro_data.get('verified', False) else 0.0
        
        # Calculate weighted overall score
        critical_weight = 0.2  # Critical components
        standard_weight = 0.1  # Standard components
        
        weighted_score = (
            scores['truth_mode'] * critical_weight +
            scores['significance'] * critical_weight +
            scores['kill_switch'] * critical_weight +
            scores['adversarial'] * critical_weight +
            scores['reproducibility'] * critical_weight +
            scores['leverage'] * standard_weight +
            scores['thousand_cuts'] * standard_weight +
            scores['alpha_genome'] * standard_weight
        )
        
        # Institutional grade requires:
        # 1. No critical failures
        # 2. Overall score > 0.8
        # 3. All critical components pass
        critical_components_pass = all([
            scores['truth_mode'] > 0.8,
            scores['significance'] > 0.5,
            scores['kill_switch'] > 0.8,
            scores['adversarial'] > 0.6,
            scores['reproducibility'] > 0.8
        ])
        
        institutional_grade = (
            len(critical_failures) == 0 and
            weighted_score > 0.8 and
            critical_components_pass
        )
        
        return {
            'scores': scores,
            'overall_score': weighted_score,
            'institutional_grade': institutional_grade,
            'critical_components_pass': critical_components_pass
        }
    
    def _generate_institutional_report(self, 
                                     system_name: str,
                                     validation_results: Dict[str, Any],
                                     overall_assessment: Dict[str, Any],
                                     critical_failures: List[str]) -> InstitutionalValidationReport:
        """Generate comprehensive institutional validation report."""
        # Extract data from validation results
        truth_data = validation_results.get('truth_mode', {})
        significance_data = validation_results.get('significance', {})
        leverage_data = validation_results.get('leverage', {})
        kill_switch_data = validation_results.get('kill_switch', {})
        adversarial_data = validation_results.get('adversarial', {})
        thousand_cuts_data = validation_results.get('thousand_cuts', {})
        genome_data = validation_results.get('alpha_genome', {})
        repro_data = validation_results.get('reproducibility', {})
        
        # Generate recommendations
        recommendations = self._generate_recommendations(validation_results, overall_assessment)
        
        return InstitutionalValidationReport(
            validation_date=datetime.now(),
            system_name=system_name,
            
            # Truth mode results
            truth_mode_passed=truth_data.get('passed', False),
            truth_mode_run_id=truth_data.get('run_id', ''),
            system_freeze_verified=truth_data.get('freeze_verified', False),
            
            # Statistical significance results
            significance_gates_passed=significance_data.get('passed', False),
            alpha_significance_reports=significance_data.get('alpha_reports', {}),
            false_alpha_rate=significance_data.get('false_alpha_rate', 1.0),
            
            # Alpha/leverage separation results
            leverage_separation_completed=leverage_data.get('completed', False),
            pure_signal_quality=leverage_data.get('pure_signal_quality', 0.0),
            leverage_efficiency=leverage_data.get('leverage_efficiency', 0.0),
            
            # Kill switch audit results
            kill_switch_audit_passed=kill_switch_data.get('passed', False),
            crisis_survival_verified=kill_switch_data.get('crisis_survival_verified', False),
            kill_switch_effectiveness=1.0 if kill_switch_data.get('passed', False) else 0.0,
            
            # Adversarial testing results
            adversarial_testing_passed=adversarial_data.get('passed', False),
            system_resilience_score=adversarial_data.get('resilience_score', 0.0),
            vulnerability_count=adversarial_data.get('vulnerability_count', 999),
            
            # Thousand cuts detection results
            thousand_cuts_clear=thousand_cuts_data.get('passed', False),
            decay_score=thousand_cuts_data.get('decay_score', 1.0),
            critical_decay_detected=thousand_cuts_data.get('critical_decay_detected', True),
            
            # Alpha genome results
            alpha_genome_healthy=genome_data.get('healthy', False),
            alpha_diversification_score=genome_data.get('diversification_score', 0.0),
            survival_without_top_alpha=genome_data.get('survival_without_top_alpha', 0.0),
            
            # Reproducibility results
            reproducibility_verified=repro_data.get('verified', False),
            archive_created=repro_data.get('archive_created', False),
            byte_for_byte_verified=repro_data.get('byte_for_byte_verified', False),
            
            # Overall assessment
            institutional_grade_achieved=overall_assessment['institutional_grade'],
            overall_score=overall_assessment['overall_score'],
            critical_failures=critical_failures,
            recommendations=recommendations
        )
    
    def _generate_failure_report(self, 
                               system_name: str,
                               critical_failures: List[str],
                               error_message: str) -> InstitutionalValidationReport:
        """Generate failure report when validation crashes."""
        return InstitutionalValidationReport(
            validation_date=datetime.now(),
            system_name=system_name,
            truth_mode_passed=False,
            truth_mode_run_id='',
            system_freeze_verified=False,
            significance_gates_passed=False,
            alpha_significance_reports={},
            false_alpha_rate=1.0,
            leverage_separation_completed=False,
            pure_signal_quality=0.0,
            leverage_efficiency=0.0,
            kill_switch_audit_passed=False,
            crisis_survival_verified=False,
            kill_switch_effectiveness=0.0,
            adversarial_testing_passed=False,
            system_resilience_score=0.0,
            vulnerability_count=999,
            thousand_cuts_clear=False,
            decay_score=1.0,
            critical_decay_detected=True,
            alpha_genome_healthy=False,
            alpha_diversification_score=0.0,
            survival_without_top_alpha=0.0,
            reproducibility_verified=False,
            archive_created=False,
            byte_for_byte_verified=False,
            institutional_grade_achieved=False,
            overall_score=0.0,
            critical_failures=critical_failures + [error_message],
            recommendations=["Fix system errors before attempting validation"]
        )
    
    def _generate_recommendations(self, 
                                validation_results: Dict[str, Any],
                                overall_assessment: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on validation results."""
        recommendations = []
        scores = overall_assessment['scores']
        
        # Truth mode recommendations
        if scores['truth_mode'] < 0.8:
            recommendations.append("Implement proper system freezing and bias prevention")
        
        # Significance recommendations
        if scores['significance'] < 0.5:
            recommendations.append("Improve alpha quality - too many false alphas detected")
        
        # Leverage recommendations
        if scores['leverage'] < 0.5:
            recommendations.append("Separate signal quality from position sizing effects")
        
        # Kill switch recommendations
        if scores['kill_switch'] < 0.8:
            recommendations.append("Fix kill switch mechanisms - crisis protection inadequate")
        
        # Adversarial recommendations
        if scores['adversarial'] < 0.6:
            recommendations.append("Improve system resilience against adversarial attacks")
        
        # Thousand cuts recommendations
        if scores['thousand_cuts'] < 0.5:
            recommendations.append("Address gradual performance decay issues")
        
        # Alpha genome recommendations
        if scores['alpha_genome'] < 0.5:
            recommendations.append("Diversify alpha sources to reduce single-source dependency")
        
        # Reproducibility recommendations
        if scores['reproducibility'] < 0.8:
            recommendations.append("Implement complete run archival and reproducibility")
        
        return recommendations
    
    def _log_final_results(self, report: InstitutionalValidationReport):
        """Log final institutional validation results."""
        self.logger.info("🏛️ INSTITUTIONAL VALIDATION COMPLETE")
        self.logger.info("=" * 80)
        self.logger.info(f"System: {report.system_name}")
        self.logger.info(f"Overall Score: {report.overall_score:.2f}")
        self.logger.info(f"Institutional Grade: {'✅ ACHIEVED' if report.institutional_grade_achieved else '❌ NOT ACHIEVED'}")
        
        # Log individual safeguard results
        self.logger.info("\n🔍 Individual Safeguard Results:")
        self.logger.info(f"   1. Truth Mode: {'✅' if report.truth_mode_passed else '❌'}")
        self.logger.info(f"   2. Significance Gates: {'✅' if report.significance_gates_passed else '❌'}")
        self.logger.info(f"   3. Leverage Separation: {'✅' if report.leverage_separation_completed else '❌'}")
        self.logger.info(f"   4. Kill Switch Audit: {'✅' if report.kill_switch_audit_passed else '❌'}")
        self.logger.info(f"   5. Adversarial Testing: {'✅' if report.adversarial_testing_passed else '❌'}")
        self.logger.info(f"   6. Thousand Cuts: {'✅' if report.thousand_cuts_clear else '❌'}")
        self.logger.info(f"   7. Alpha Genome: {'✅' if report.alpha_genome_healthy else '❌'}")
        self.logger.info(f"   8. Reproducibility: {'✅' if report.reproducibility_verified else '❌'}")
        
        # Log critical failures
        if report.critical_failures:
            self.logger.info(f"\n❌ Critical Failures ({len(report.critical_failures)}):")
            for failure in report.critical_failures:
                self.logger.info(f"   - {failure}")
        
        # Log recommendations
        if report.recommendations:
            self.logger.info(f"\n💡 Recommendations ({len(report.recommendations)}):")
            for rec in report.recommendations:
                self.logger.info(f"   - {rec}")
        
        self.logger.info("\n🏛️ INSTITUTIONAL VALIDATION SUMMARY")
        if report.institutional_grade_achieved:
            self.logger.info("✅ SYSTEM MEETS INSTITUTIONAL STANDARDS")
            self.logger.info("✅ READY FOR REAL CAPITAL ALLOCATION")
            self.logger.info("✅ ALL SILENT KILLERS ADDRESSED")
        else:
            self.logger.info("❌ SYSTEM DOES NOT MEET INSTITUTIONAL STANDARDS")
            self.logger.info("❌ NOT READY FOR REAL CAPITAL ALLOCATION")
            self.logger.info("❌ SILENT KILLERS DETECTED")


def create_institutional_safeguards_suite() -> InstitutionalSafeguardsSuite:
    """Create complete institutional safeguards suite."""
    return InstitutionalSafeguardsSuite()


if __name__ == "__main__":
    # Demo usage
    suite = create_institutional_safeguards_suite()
    
    # Generate sample data
    np.random.seed(42)
    n = 252  # One year of data
    
    returns = np.random.randn(n) * 0.02 + 0.0005
    signals = {
        'momentum': np.random.randn(n) * 0.5,
        'value': np.random.randn(n) * 0.3
    }
    costs = np.abs(np.random.randn(n) * 0.001)
    market_data = {'returns': np.random.randn(n) * 0.015}
    timestamps = [datetime(2023, 1, 1) + pd.Timedelta(days=i) for i in range(n)]
    kill_switch_log = []
    
    # Run complete validation
    report = suite.run_complete_institutional_validation(
        "Demo System", returns, signals, costs, market_data, timestamps, kill_switch_log
    )
    
    print(f"\nInstitutional Validation Complete:")
    print(f"Grade Achieved: {report.institutional_grade_achieved}")
    print(f"Overall Score: {report.overall_score:.2f}")
    print(f"Critical Failures: {len(report.critical_failures)}")