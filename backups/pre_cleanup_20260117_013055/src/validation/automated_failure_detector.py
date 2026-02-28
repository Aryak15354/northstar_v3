#!/usr/bin/env python3
"""
🚨 AUTOMATED FAILURE DETECTION SYSTEM - TASK 13
Comprehensive failure detection and early warning system for walk-forward validation

This implements Task 13 with:
- Real-time anomaly detection in validation metrics
- Early warning system for degrading performance
- Automated failure classification and severity assessment
- Integration with existing validation systems
- Property-based failure detection rules

Usage:
    from src.validation.automated_failure_detector import AutomatedFailureDetector
    
    detector = AutomatedFailureDetector()
    failures = detector.detect_failures(validation_results, historical_data)
"""

import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass
from enum import Enum
import warnings
warnings.filterwarnings('ignore')

import sys
))

@dataclass
class FailureAlert:
    """Failure alert with severity and details"""
    failure_type: str
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW
    component: str
    metric_name: str
    current_value: float
    expected_range: Tuple[float, float]
    deviation_magnitude: float
    timestamp: datetime
    description: str
    recommended_action: str
    confidence: float  # 0-1

class FailureSeverity(Enum):
    """Failure severity levels"""
    CRITICAL = "CRITICAL"  # System failure, immediate action required
    HIGH = "HIGH"         # Significant degradation, urgent attention needed
    MEDIUM = "MEDIUM"     # Moderate issues, should be addressed soon
    LOW = "LOW"           # Minor anomalies, monitor closely

class FailureType(Enum):
    """Types of failures to detect"""
    PERFORMANCE_DEGRADATION = "performance_degradation"
    ACCURACY_DECLINE = "accuracy_decline"
    BIAS_DRIFT = "bias_drift"
    VOLATILITY_SPIKE = "volatility_spike"
    CORRELATION_BREAKDOWN = "correlation_breakdown"
    DATA_QUALITY_ISSUE = "data_quality_issue"
    SYSTEM_INSTABILITY = "system_instability"
    REGIME_MISCLASSIFICATION = "regime_misclassification"
    OVERFITTING_DETECTED = "overfitting_detected"
    UNDERFITTING_DETECTED = "underfitting_detected"

class AutomatedFailureDetector:
    """
    Automated Failure Detection System for Task 13
    
    Provides comprehensive failure detection including:
    1. Real-time anomaly detection in validation metrics
    2. Early warning system for performance degradation
    3. Automated failure classification and severity assessment
    4. Integration with walk-forward validation pipeline
    5. Property-based failure detection rules
    """
    
    def __init__(self):
        self.name = "Automated Failure Detection System"
        self.version = "1.0"
        
        # Detection thresholds
        self.thresholds = {
            'performance_degradation': {
                'critical': 0.20,  # 20% performance drop
                'high': 0.15,      # 15% performance drop
                'medium': 0.10,    # 10% performance drop
                'low': 0.05        # 5% performance drop
            },
            'accuracy_decline': {
                'critical': 0.15,  # 15% accuracy drop
                'high': 0.10,      # 10% accuracy drop
                'medium': 0.07,    # 7% accuracy drop
                'low': 0.05        # 5% accuracy drop
            },
            'volatility_spike': {
                'critical': 3.0,   # 3x normal volatility
                'high': 2.5,       # 2.5x normal volatility
                'medium': 2.0,     # 2x normal volatility
                'low': 1.5         # 1.5x normal volatility
            },
            'bias_drift': {
                'critical': 0.10,  # 10% bias drift
                'high': 0.07,      # 7% bias drift
                'medium': 0.05,    # 5% bias drift
                'low': 0.03        # 3% bias drift
            }
        }
        
        # Historical data for baseline comparison
        self.baseline_metrics = {}
        self.failure_history = []
        
        # Detection windows
        self.short_window = 30   # 30 days for short-term detection
        self.medium_window = 90  # 90 days for medium-term detection
        self.long_window = 252   # 252 days for long-term detection
        
        print("🚨 Automated Failure Detection System initialized - Monitoring active")
    
    def establish_baseline(self, historical_data: Dict[str, Any]) -> None:
        """Establish baseline metrics for failure detection"""
        
        print("📊 Establishing baseline metrics...")
        
        # Extract key metrics from historical data
        if 'performance_metrics' in historical_data:
            perf_data = historical_data['performance_metrics']
            
            self.baseline_metrics['sharpe_ratio'] = {
                'mean': np.mean(perf_data.get('sharpe_ratio', [1.0])),
                'std': np.std(perf_data.get('sharpe_ratio', [1.0])),
                'percentiles': np.percentile(perf_data.get('sharpe_ratio', [1.0]), [5, 25, 75, 95])
            }
            
            self.baseline_metrics['returns'] = {
                'mean': np.mean(perf_data.get('returns', [0.01])),
                'std': np.std(perf_data.get('returns', [0.01])),
                'percentiles': np.percentile(perf_data.get('returns', [0.01]), [5, 25, 75, 95])
            }
            
            self.baseline_metrics['volatility'] = {
                'mean': np.mean(perf_data.get('volatility', [0.15])),
                'std': np.std(perf_data.get('volatility', [0.15])),
                'percentiles': np.percentile(perf_data.get('volatility', [0.15]), [5, 25, 75, 95])
            }
        
        # Extract accuracy metrics
        if 'accuracy_metrics' in historical_data:
            acc_data = historical_data['accuracy_metrics']
            
            self.baseline_metrics['prediction_accuracy'] = {
                'mean': np.mean(acc_data.get('accuracy', [0.6])),
                'std': np.std(acc_data.get('accuracy', [0.6])),
                'percentiles': np.percentile(acc_data.get('accuracy', [0.6]), [5, 25, 75, 95])
            }
        
        print(f"   ✅ Baseline established for {len(self.baseline_metrics)} metric categories")
    
    def detect_performance_degradation(self, current_metrics: Dict[str, float], 
                                     historical_metrics: List[Dict[str, float]]) -> List[FailureAlert]:
        """Detect performance degradation patterns"""
        
        alerts = []
        
        # Check Sharpe ratio degradation
        if 'sharpe_ratio' in current_metrics and 'sharpe_ratio' in self.baseline_metrics:
            current_sharpe = current_metrics['sharpe_ratio']
            baseline_sharpe = self.baseline_metrics['sharpe_ratio']['mean']
            
            if baseline_sharpe > 0:  # Avoid division by zero
                degradation = (baseline_sharpe - current_sharpe) / baseline_sharpe
                
                severity = self._classify_severity('performance_degradation', degradation)
                
                if severity != 'none':
                    alerts.append(FailureAlert(
                        failure_type=FailureType.PERFORMANCE_DEGRADATION.value,
                        severity=severity.upper(),
                        component="Portfolio Performance",
                        metric_name="sharpe_ratio",
                        current_value=current_sharpe,
                        expected_range=(baseline_sharpe * 0.9, baseline_sharpe * 1.1),
                        deviation_magnitude=degradation,
                        timestamp=datetime.now(),
                        description=f"Sharpe ratio degraded by {degradation:.1%} from baseline",
                        recommended_action="Review strategy parameters and market conditions",
                        confidence=0.8
                    ))
        
        # Check return degradation
        if 'returns' in current_metrics and 'returns' in self.baseline_metrics:
            current_returns = current_metrics['returns']
            baseline_returns = self.baseline_metrics['returns']['mean']
            
            if abs(baseline_returns) > 0.001:  # Meaningful baseline
                degradation = abs(baseline_returns - current_returns) / abs(baseline_returns)
                
                severity = self._classify_severity('performance_degradation', degradation)
                
                if severity != 'none':
                    alerts.append(FailureAlert(
                        failure_type=FailureType.PERFORMANCE_DEGRADATION.value,
                        severity=severity.upper(),
                        component="Portfolio Returns",
                        metric_name="returns",
                        current_value=current_returns,
                        expected_range=(baseline_returns * 0.8, baseline_returns * 1.2),
                        deviation_magnitude=degradation,
                        timestamp=datetime.now(),
                        description=f"Returns deviated by {degradation:.1%} from baseline",
                        recommended_action="Analyze return drivers and adjust allocation",
                        confidence=0.7
                    ))
        
        return alerts
    
    def detect_accuracy_decline(self, current_accuracy: Dict[str, float], 
                              historical_accuracy: List[Dict[str, float]]) -> List[FailureAlert]:
        """Detect accuracy decline in predictions"""
        
        alerts = []
        
        if 'prediction_accuracy' in current_accuracy and 'prediction_accuracy' in self.baseline_metrics:
            current_acc = current_accuracy['prediction_accuracy']
            baseline_acc = self.baseline_metrics['prediction_accuracy']['mean']
            
            decline = (baseline_acc - current_acc) / baseline_acc if baseline_acc > 0 else 0
            
            severity = self._classify_severity('accuracy_decline', decline)
            
            if severity != 'none':
                alerts.append(FailureAlert(
                    failure_type=FailureType.ACCURACY_DECLINE.value,
                    severity=severity.upper(),
                    component="Prediction System",
                    metric_name="prediction_accuracy",
                    current_value=current_acc,
                    expected_range=(baseline_acc * 0.9, baseline_acc * 1.1),
                    deviation_magnitude=decline,
                    timestamp=datetime.now(),
                    description=f"Prediction accuracy declined by {decline:.1%}",
                    recommended_action="Retrain models and validate data quality",
                    confidence=0.85
                ))
        
        return alerts
    
    def detect_volatility_anomalies(self, current_volatility: float, 
                                   historical_volatility: List[float]) -> List[FailureAlert]:
        """Detect unusual volatility patterns"""
        
        alerts = []
        
        if 'volatility' in self.baseline_metrics and len(historical_volatility) > 0:
            baseline_vol = self.baseline_metrics['volatility']['mean']
            recent_vol_avg = np.mean(historical_volatility[-30:]) if len(historical_volatility) >= 30 else np.mean(historical_volatility)
            
            # Check for volatility spike
            if baseline_vol > 0:
                vol_ratio = current_volatility / baseline_vol
                
                severity = self._classify_severity('volatility_spike', vol_ratio)
                
                if severity != 'none':
                    alerts.append(FailureAlert(
                        failure_type=FailureType.VOLATILITY_SPIKE.value,
                        severity=severity.upper(),
                        component="Risk Management",
                        metric_name="volatility",
                        current_value=current_volatility,
                        expected_range=(baseline_vol * 0.5, baseline_vol * 1.5),
                        deviation_magnitude=vol_ratio - 1.0,
                        timestamp=datetime.now(),
                        description=f"Volatility spike: {vol_ratio:.1f}x baseline level",
                        recommended_action="Reduce position sizes and increase cash allocation",
                        confidence=0.9
                    ))
        
        return alerts
    
    def detect_bias_drift(self, current_predictions: List[float], 
                         actual_outcomes: List[float]) -> List[FailureAlert]:
        """Detect systematic bias drift in predictions"""
        
        alerts = []
        
        if len(current_predictions) >= 30 and len(actual_outcomes) >= 30:
            # Calculate prediction bias
            prediction_errors = np.array(current_predictions) - np.array(actual_outcomes)
            current_bias = np.mean(prediction_errors)
            
            # Compare with historical bias (assume near-zero baseline)
            baseline_bias = 0.0
            bias_drift = abs(current_bias - baseline_bias)
            
            severity = self._classify_severity('bias_drift', bias_drift)
            
            if severity != 'none':
                alerts.append(FailureAlert(
                    failure_type=FailureType.BIAS_DRIFT.value,
                    severity=severity.upper(),
                    component="Prediction System",
                    metric_name="prediction_bias",
                    current_value=current_bias,
                    expected_range=(-0.02, 0.02),  # ±2% acceptable bias
                    deviation_magnitude=bias_drift,
                    timestamp=datetime.now(),
                    description=f"Systematic bias detected: {current_bias:.3f}",
                    recommended_action="Recalibrate models and check for data drift",
                    confidence=0.75
                ))
        
        return alerts
    
    def detect_system_instability(self, validation_results: Dict[str, Any]) -> List[FailureAlert]:
        """Detect system instability patterns"""
        
        alerts = []
        
        # Check for high variance in key metrics
        if 'metric_history' in validation_results:
            metric_history = validation_results['metric_history']
            
            for metric_name, values in metric_history.items():
                if len(values) >= 10:
                    recent_values = values[-10:]
                    coefficient_of_variation = np.std(recent_values) / (abs(np.mean(recent_values)) + 1e-8)
                    
                    # High coefficient of variation indicates instability
                    if coefficient_of_variation > 0.5:  # 50% CV threshold
                        alerts.append(FailureAlert(
                            failure_type=FailureType.SYSTEM_INSTABILITY.value,
                            severity="HIGH",
                            component="System Stability",
                            metric_name=metric_name,
                            current_value=coefficient_of_variation,
                            expected_range=(0.0, 0.3),
                            deviation_magnitude=coefficient_of_variation - 0.3,
                            timestamp=datetime.now(),
                            description=f"High variability in {metric_name}: CV={coefficient_of_variation:.2f}",
                            recommended_action="Investigate parameter stability and data consistency",
                            confidence=0.7
                        ))
        
        return alerts
    
    def detect_failures(self, validation_results: Dict[str, Any], 
                       historical_data: Optional[Dict[str, Any]] = None) -> List[FailureAlert]:
        """Main failure detection method"""
        
        print("🚨 Running automated failure detection...")
        
        all_alerts = []
        
        # Establish baseline if historical data provided
        if historical_data and not self.baseline_metrics:
            self.establish_baseline(historical_data)
        
        # Extract current metrics
        current_metrics = validation_results.get('current_metrics', {})
        historical_metrics = validation_results.get('historical_metrics', [])
        
        # Run detection algorithms
        print("   🔍 Detecting performance degradation...")
        perf_alerts = self.detect_performance_degradation(current_metrics, historical_metrics)
        all_alerts.extend(perf_alerts)
        
        print("   🔍 Detecting accuracy decline...")
        acc_alerts = self.detect_accuracy_decline(
            validation_results.get('accuracy_metrics', {}),
            validation_results.get('historical_accuracy', [])
        )
        all_alerts.extend(acc_alerts)
        
        print("   🔍 Detecting volatility anomalies...")
        vol_alerts = self.detect_volatility_anomalies(
            current_metrics.get('volatility', 0.15),
            validation_results.get('historical_volatility', [])
        )
        all_alerts.extend(vol_alerts)
        
        print("   🔍 Detecting bias drift...")
        bias_alerts = self.detect_bias_drift(
            validation_results.get('recent_predictions', []),
            validation_results.get('recent_outcomes', [])
        )
        all_alerts.extend(bias_alerts)
        
        print("   🔍 Detecting system instability...")
        stability_alerts = self.detect_system_instability(validation_results)
        all_alerts.extend(stability_alerts)
        
        # Store failure history
        self.failure_history.extend(all_alerts)
        
        # Summary
        critical_count = sum(1 for alert in all_alerts if alert.severity == 'CRITICAL')
        high_count = sum(1 for alert in all_alerts if alert.severity == 'HIGH')
        medium_count = sum(1 for alert in all_alerts if alert.severity == 'MEDIUM')
        low_count = sum(1 for alert in all_alerts if alert.severity == 'LOW')
        
        print(f"\n📊 FAILURE DETECTION SUMMARY")
        print(f"   Total alerts: {len(all_alerts)}")
        print(f"   Critical: {critical_count}, High: {high_count}, Medium: {medium_count}, Low: {low_count}")
        
        if critical_count > 0:
            print(f"   🚨 CRITICAL FAILURES DETECTED - Immediate action required")
        elif high_count > 0:
            print(f"   ⚠️ HIGH SEVERITY ISSUES - Urgent attention needed")
        elif len(all_alerts) > 0:
            print(f"   ℹ️ Issues detected - Monitor and address as needed")
        else:
            print(f"   ✅ No failures detected - System operating normally")
        
        return all_alerts
    
    def generate_failure_report(self, alerts: List[FailureAlert]) -> Dict[str, Any]:
        """Generate comprehensive failure report"""
        
        if not alerts:
            return {
                'status': 'HEALTHY',
                'total_alerts': 0,
                'summary': 'No failures detected',
                'recommendations': ['Continue monitoring']
            }
        
        # Categorize alerts by severity
        severity_counts = {'CRITICAL': 0, 'HIGH': 0, 'MEDIUM': 0, 'LOW': 0}
        component_issues = {}
        
        for alert in alerts:
            severity_counts[alert.severity] += 1
            
            if alert.component not in component_issues:
                component_issues[alert.component] = []
            component_issues[alert.component].append(alert)
        
        # Determine overall status
        if severity_counts['CRITICAL'] > 0:
            status = 'CRITICAL'
        elif severity_counts['HIGH'] > 0:
            status = 'DEGRADED'
        elif severity_counts['MEDIUM'] > 0:
            status = 'WARNING'
        else:
            status = 'MINOR_ISSUES'
        
        # Generate recommendations
        recommendations = []
        if severity_counts['CRITICAL'] > 0:
            recommendations.append('Immediate system shutdown and investigation required')
        if severity_counts['HIGH'] > 0:
            recommendations.append('Urgent review of affected components')
        if 'Portfolio Performance' in component_issues:
            recommendations.append('Review and adjust portfolio strategy')
        if 'Prediction System' in component_issues:
            recommendations.append('Retrain models and validate data quality')
        
        return {
            'status': status,
            'total_alerts': len(alerts),
            'severity_breakdown': severity_counts,
            'affected_components': list(component_issues.keys()),
            'component_details': component_issues,
            'recommendations': recommendations,
            'timestamp': datetime.now().isoformat()
        }
    
    def _classify_severity(self, failure_type: str, magnitude: float) -> str:
        """Classify failure severity based on magnitude"""
        
        if failure_type not in self.thresholds:
            return 'medium'  # Default severity
        
        thresholds = self.thresholds[failure_type]
        
        if magnitude >= thresholds['critical']:
            return 'critical'
        elif magnitude >= thresholds['high']:
            return 'high'
        elif magnitude >= thresholds['medium']:
            return 'medium'
        elif magnitude >= thresholds['low']:
            return 'low'
        else:
            return 'none'


def main():
    """Demonstrate Automated Failure Detection System"""
    
    print("🚨 AUTOMATED FAILURE DETECTION SYSTEM - TASK 13")
    print("=" * 70)
    
    detector = AutomatedFailureDetector()
    
    # Mock validation results with some failures
    validation_results = {
        'current_metrics': {
            'sharpe_ratio': 0.8,  # Lower than baseline
            'returns': 0.05,
            'volatility': 0.25    # Higher than normal
        },
        'accuracy_metrics': {
            'prediction_accuracy': 0.55  # Lower accuracy
        },
        'recent_predictions': [0.02, 0.01, 0.03, -0.01, 0.02] * 10,
        'recent_outcomes': [0.015, 0.008, 0.025, -0.008, 0.018] * 10,
        'historical_volatility': [0.15] * 50 + [0.25] * 10,  # Recent spike
        'metric_history': {
            'sharpe_ratio': [1.2, 1.1, 0.9, 1.3, 0.8, 1.0, 0.7, 1.1, 0.9, 0.8]  # Unstable
        }
    }
    
    # Mock historical data for baseline
    historical_data = {
        'performance_metrics': {
            'sharpe_ratio': [1.2, 1.1, 1.3, 1.0, 1.4, 1.1, 1.2],
            'returns': [0.08, 0.06, 0.09, 0.07, 0.08],
            'volatility': [0.15, 0.14, 0.16, 0.15, 0.17]
        },
        'accuracy_metrics': {
            'accuracy': [0.65, 0.62, 0.68, 0.64, 0.66]
        }
    }
    
    # Run failure detection
    alerts = detector.detect_failures(validation_results, historical_data)
    
    # Generate report
    report = detector.generate_failure_report(alerts)
    
    print(f"\n📊 FAILURE DETECTION RESULTS")
    print("=" * 40)
    print(f"   System Status: {report['status']}")
    print(f"   Total Alerts: {report['total_alerts']}")
    
    if alerts:
        print(f"\n⚠️ DETECTED FAILURES:")
        for i, alert in enumerate(alerts[:5], 1):  # Show first 5 alerts
            print(f"   {i}. {alert.severity}: {alert.description}")
            print(f"      Component: {alert.component}")
            print(f"      Action: {alert.recommended_action}")
            print()
    
    print(f"\n💡 RECOMMENDATIONS:")
    for rec in report['recommendations']:
        print(f"   • {rec}")
    
    print(f"\n✅ Automated Failure Detection System demonstration complete")


if __name__ == "__main__":
    main()