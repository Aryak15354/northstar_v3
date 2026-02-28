#!/usr/bin/env python3
"""
🧪 PROPERTY TESTS FOR TASK 13 - AUTOMATED FAILURE DETECTION
Property-based tests for automated failure detection system

Tests the following properties:
- Property 38: Failure Detection Sensitivity
- Property 39: False Positive Rate Control
- Property 40: Severity Classification Accuracy

Usage:
    python -m pytest tests/validation/test_task13_automated_failure_detection_properties.py -v
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from hypothesis import given, strategies as st, settings
import warnings
warnings.filterwarnings('ignore')

import sys
import os
)))

from src.validation.automated_failure_detector import AutomatedFailureDetector, FailureSeverity

class TestTask13AutomatedFailureDetectionProperties:
    """Property tests for Task 13 - Automated Failure Detection"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.detector = AutomatedFailureDetector()
        
        # Establish baseline for testing
        baseline_data = {
            'performance_metrics': {
                'sharpe_ratio': [1.2, 1.1, 1.3, 1.0, 1.4],
                'returns': [0.08, 0.06, 0.09, 0.07, 0.08],
                'volatility': [0.15, 0.14, 0.16, 0.15, 0.17]
            },
            'accuracy_metrics': {
                'accuracy': [0.65, 0.62, 0.68, 0.64, 0.66]
            }
        }
        self.detector.establish_baseline(baseline_data)
        
    @given(
        performance_degradation=st.floats(min_value=0.0, max_value=0.5),
        noise_level=st.floats(min_value=0.0, max_value=0.2)
    )
    @settings(max_examples=20, deadline=5000)
    def test_property_38_failure_detection_sensitivity(self, performance_degradation, noise_level):
        """
        Property 38: Failure Detection Sensitivity
        
        System should detect failures when performance degrades significantly,
        but should not be overly sensitive to minor fluctuations.
        """
        
        # Create degraded metrics
        baseline_sharpe = 1.2
        degraded_sharpe = baseline_sharpe * (1 - performance_degradation)
        
        # Add some noise
        noisy_sharpe = degraded_sharpe + np.random.normal(0, noise_level)
        
        current_metrics = {
            'sharpe_ratio': noisy_sharpe,
            'returns': 0.08 * (1 - performance_degradation * 0.5),
            'volatility': 0.15 * (1 + performance_degradation)
        }
        
        # Run failure detection
        validation_results = {
            'current_metrics': current_metrics,
            'historical_metrics': []
        }
        
        alerts = self.detector.detect_failures(validation_results)
        
        # Property assertions
        if performance_degradation >= 0.2:  # Significant degradation
            # Should detect failure
            performance_alerts = [a for a in alerts if 'performance' in a.failure_type.lower()]
            assert len(performance_alerts) > 0, f"Should detect significant degradation ({performance_degradation:.1%})"
            
            # Severity should be appropriate
            if performance_degradation >= 0.3:
                critical_alerts = [a for a in performance_alerts if a.severity == 'CRITICAL']
                assert len(critical_alerts) > 0, "Should classify severe degradation as CRITICAL"
        
        elif performance_degradation <= 0.05:  # Minor fluctuation
            # Should not generate critical alerts for minor issues
            critical_alerts = [a for a in alerts if a.severity == 'CRITICAL']
            assert len(critical_alerts) == 0, f"Should not generate critical alerts for minor degradation ({performance_degradation:.1%})"
        
        # All alerts should have valid confidence scores
        for alert in alerts:
            assert 0.0 <= alert.confidence <= 1.0, f"Alert confidence {alert.confidence} not in valid range"
            assert alert.severity in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'], f"Invalid severity: {alert.severity}"
    
    @given(
        baseline_stability=st.floats(min_value=0.8, max_value=1.2),
        measurement_noise=st.floats(min_value=0.0, max_value=0.1)
    )
    @settings(max_examples=15, deadline=5000)
    def test_property_39_false_positive_rate_control(self, baseline_stability, measurement_noise):
        """
        Property 39: False Positive Rate Control
        
        System should maintain low false positive rate when metrics are
        within normal ranges, even with measurement noise.
        """
        
        # Create metrics within normal range
        current_metrics = {
            'sharpe_ratio': 1.2 * baseline_stability + np.random.normal(0, measurement_noise),
            'returns': 0.08 * baseline_stability + np.random.normal(0, measurement_noise * 0.01),
            'volatility': 0.15 * baseline_stability + np.random.normal(0, measurement_noise * 0.02)
        }
        
        accuracy_metrics = {
            'prediction_accuracy': 0.65 * baseline_stability + np.random.normal(0, measurement_noise * 0.1)
        }
        
        validation_results = {
            'current_metrics': current_metrics,
            'accuracy_metrics': accuracy_metrics,
            'historical_metrics': [],
            'recent_predictions': [0.02] * 20,
            'recent_outcomes': [0.018] * 20,  # Small bias
            'historical_volatility': [0.15] * 30
        }
        
        alerts = self.detector.detect_failures(validation_results)
        
        # Property assertions
        critical_alerts = [a for a in alerts if a.severity == 'CRITICAL']
        high_alerts = [a for a in alerts if a.severity == 'HIGH']
        
        # For stable metrics with low noise, should have minimal false positives
        if abs(baseline_stability - 1.0) <= 0.1 and measurement_noise <= 0.05:
            assert len(critical_alerts) == 0, "Should not generate critical alerts for stable metrics"
            assert len(high_alerts) <= 1, "Should have minimal high-severity false positives"
        
        # Total alerts should be reasonable
        assert len(alerts) <= 5, f"Too many alerts ({len(alerts)}) for stable system"
        
        # All alerts should have reasonable confidence
        for alert in alerts:
            if alert.severity in ['CRITICAL', 'HIGH']:
                assert alert.confidence >= 0.6, f"High-severity alert should have high confidence: {alert.confidence}"
    
    @given(
        degradation_magnitude=st.floats(min_value=0.05, max_value=0.4),
        metric_type=st.sampled_from(['sharpe_ratio', 'returns', 'volatility'])
    )
    @settings(max_examples=15, deadline=5000)
    def test_property_40_severity_classification_accuracy(self, degradation_magnitude, metric_type):
        """
        Property 40: Severity Classification Accuracy
        
        System should classify failure severity accurately based on
        the magnitude of degradation or deviation.
        """
        
        # Create metrics with specific degradation
        baseline_values = {
            'sharpe_ratio': 1.2,
            'returns': 0.08,
            'volatility': 0.15
        }
        
        current_metrics = baseline_values.copy()
        
        if metric_type == 'volatility':
            # For volatility, increase represents degradation
            current_metrics[metric_type] = baseline_values[metric_type] * (1 + degradation_magnitude)
        else:
            # For other metrics, decrease represents degradation
            current_metrics[metric_type] = baseline_values[metric_type] * (1 - degradation_magnitude)
        
        validation_results = {
            'current_metrics': current_metrics,
            'historical_metrics': []
        }
        
        alerts = self.detector.detect_failures(validation_results)
        
        # Find alerts related to the degraded metric
        relevant_alerts = [a for a in alerts if metric_type in a.metric_name.lower() or 
                          'performance' in a.failure_type.lower()]
        
        if relevant_alerts:
            # Property assertions based on degradation magnitude
            if degradation_magnitude >= 0.25:  # Severe degradation
                severe_alerts = [a for a in relevant_alerts if a.severity in ['CRITICAL', 'HIGH']]
                assert len(severe_alerts) > 0, f"Should classify {degradation_magnitude:.1%} degradation as severe"
                
            elif degradation_magnitude >= 0.15:  # Moderate degradation
                moderate_alerts = [a for a in relevant_alerts if a.severity in ['HIGH', 'MEDIUM']]
                assert len(moderate_alerts) > 0, f"Should classify {degradation_magnitude:.1%} degradation as moderate"
                
            elif degradation_magnitude >= 0.05:  # Minor degradation
                # Should detect but not classify as critical
                critical_alerts = [a for a in relevant_alerts if a.severity == 'CRITICAL']
                assert len(critical_alerts) == 0, f"Should not classify {degradation_magnitude:.1%} degradation as critical"
        
        # Severity ordering should be consistent
        severity_order = {'LOW': 1, 'MEDIUM': 2, 'HIGH': 3, 'CRITICAL': 4}
        
        for alert in alerts:
            # Higher deviation should not have lower severity than smaller deviation
            assert alert.severity in severity_order, f"Invalid severity: {alert.severity}"
            
            # Confidence should be reasonable for the severity level
            if alert.severity == 'CRITICAL':
                assert alert.confidence >= 0.7, "Critical alerts should have high confidence"
            elif alert.severity == 'HIGH':
                assert alert.confidence >= 0.6, "High severity alerts should have reasonable confidence"
    
    def test_property_38_failure_detection_sensitivity_deterministic(self):
        """Deterministic test for failure detection sensitivity"""
        
        # Test clear failure case
        current_metrics = {
            'sharpe_ratio': 0.6,  # 50% degradation from baseline 1.2
            'returns': 0.04,      # 50% degradation from baseline 0.08
            'volatility': 0.30    # 100% increase from baseline 0.15
        }
        
        validation_results = {
            'current_metrics': current_metrics,
            'historical_metrics': []
        }
        
        alerts = self.detector.detect_failures(validation_results)
        
        # Should detect multiple failures
        assert len(alerts) > 0, "Should detect clear failures"
        
        # Should have at least one high-severity alert
        high_severity_alerts = [a for a in alerts if a.severity in ['CRITICAL', 'HIGH']]
        assert len(high_severity_alerts) > 0, "Should classify clear failures as high severity"
    
    def test_property_39_false_positive_rate_control_deterministic(self):
        """Deterministic test for false positive rate control"""
        
        # Test normal operation case
        current_metrics = {
            'sharpe_ratio': 1.18,  # Very close to baseline 1.2
            'returns': 0.079,     # Very close to baseline 0.08
            'volatility': 0.151   # Very close to baseline 0.15
        }
        
        accuracy_metrics = {
            'prediction_accuracy': 0.64  # Close to baseline 0.65
        }
        
        validation_results = {
            'current_metrics': current_metrics,
            'accuracy_metrics': accuracy_metrics,
            'historical_metrics': [],
            'recent_predictions': [0.02] * 30,
            'recent_outcomes': [0.019] * 30,  # Very small bias
            'historical_volatility': [0.15] * 50
        }
        
        alerts = self.detector.detect_failures(validation_results)
        
        # Should have minimal or no alerts for normal operation
        critical_alerts = [a for a in alerts if a.severity == 'CRITICAL']
        assert len(critical_alerts) == 0, "Should not generate critical alerts for normal operation"
        
        # Total alerts should be minimal
        assert len(alerts) <= 2, f"Too many alerts ({len(alerts)}) for normal operation"
    
    def test_property_40_severity_classification_accuracy_deterministic(self):
        """Deterministic test for severity classification accuracy"""
        
        # Test different severity levels
        test_cases = [
            {
                'name': 'Critical Degradation',
                'sharpe_ratio': 0.8,  # 33% degradation
                'expected_min_severity': 'HIGH'
            },
            {
                'name': 'Moderate Degradation', 
                'sharpe_ratio': 1.0,  # 17% degradation
                'expected_min_severity': 'MEDIUM'
            },
            {
                'name': 'Minor Degradation',
                'sharpe_ratio': 1.15, # 4% degradation
                'expected_max_severity': 'MEDIUM'
            }
        ]
        
        severity_levels = {'LOW': 1, 'MEDIUM': 2, 'HIGH': 3, 'CRITICAL': 4}
        
        for case in test_cases:
            current_metrics = {
                'sharpe_ratio': case['sharpe_ratio'],
                'returns': 0.08,
                'volatility': 0.15
            }
            
            validation_results = {
                'current_metrics': current_metrics,
                'historical_metrics': []
            }
            
            alerts = self.detector.detect_failures(validation_results)
            
            if 'expected_min_severity' in case:
                # Should have at least this severity level
                min_level = severity_levels[case['expected_min_severity']]
                relevant_alerts = [a for a in alerts if severity_levels[a.severity] >= min_level]
                assert len(relevant_alerts) > 0, f"{case['name']}: Should have {case['expected_min_severity']} or higher severity"
            
            if 'expected_max_severity' in case:
                # Should not exceed this severity level
                max_level = severity_levels[case['expected_max_severity']]
                excessive_alerts = [a for a in alerts if severity_levels[a.severity] > max_level]
                assert len(excessive_alerts) == 0, f"{case['name']}: Should not exceed {case['expected_max_severity']} severity"
    
    def test_baseline_establishment(self):
        """Test baseline establishment functionality"""
        
        detector = AutomatedFailureDetector()
        
        historical_data = {
            'performance_metrics': {
                'sharpe_ratio': [1.0, 1.2, 1.1, 1.3, 1.0],
                'returns': [0.06, 0.08, 0.07, 0.09, 0.06],
                'volatility': [0.14, 0.16, 0.15, 0.17, 0.14]
            },
            'accuracy_metrics': {
                'accuracy': [0.60, 0.65, 0.62, 0.68, 0.60]
            }
        }
        
        detector.establish_baseline(historical_data)
        
        # Check that baseline metrics were established
        assert 'sharpe_ratio' in detector.baseline_metrics
        assert 'returns' in detector.baseline_metrics
        assert 'volatility' in detector.baseline_metrics
        assert 'prediction_accuracy' in detector.baseline_metrics
        
        # Check baseline values are reasonable
        sharpe_baseline = detector.baseline_metrics['sharpe_ratio']
        assert 0.8 <= sharpe_baseline['mean'] <= 1.5
        assert sharpe_baseline['std'] >= 0
        assert len(sharpe_baseline['percentiles']) == 4


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])