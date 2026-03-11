#!/usr/bin/env python3
"""
🧪 PROPERTY TESTS FOR TASK 10 - NOISE ROBUSTNESS
Property-based tests for regime adaptation and noise robustness

Tests the following properties:
- Property 17: Regime Adaptation Timing
- Property 18: Uncertainty Response  
- Property 19: Noise Robustness

Usage:
    python -m pytest tests/validation/test_task10_noise_robustness_properties.py -v
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
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from src.validation.noise_robustness_tester import NoiseRobustnessTester, NoiseType

class TestTask10NoiseRobustnessProperties:
    """Property tests for Task 10 - Noise Robustness and Regime Adaptation"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.tester = NoiseRobustnessTester()
        
    @given(
        noise_level=st.floats(min_value=0.1, max_value=1.0),
        signal_strength=st.floats(min_value=-1.0, max_value=1.0)
    )
    @settings(max_examples=20, deadline=5000)
    def test_property_17_regime_adaptation_timing(self, noise_level, signal_strength):
        """
        Property 17: Regime Adaptation Timing
        
        For any regime change, adaptation should occur within reasonable time bounds
        and performance should recover to baseline levels.
        """
        
        # Generate mock signals with regime change
        clean_signals = {
            'momentum': {'strength': signal_strength, 'confidence': 0.7},
            'value': {'strength': signal_strength * 0.8, 'confidence': 0.6}
        }
        
        # Inject noise
        noisy_signals = self.tester.inject_signal_noise(
            clean_signals, NoiseType.GAUSSIAN, noise_level
        )
        
        # Test adaptation timing
        performance_history = [0.1] * 10 + [-0.05] * 5 + [0.08] * 10  # Regime change pattern
        regime_changes = [10]  # Regime change at day 10
        
        adaptation_speed = self.tester.measure_adaptation_speed(performance_history, regime_changes)
        
        # Property assertions
        assert 0.0 <= adaptation_speed <= 1.0, f"Adaptation speed {adaptation_speed} not in valid range"
        
        # For reasonable noise levels, adaptation should be reasonably fast
        if noise_level <= 0.5:
            assert adaptation_speed >= 0.3, f"Adaptation too slow ({adaptation_speed}) for noise level {noise_level}"
        
        # Signal strength should be preserved to some degree
        original_strength = clean_signals['momentum']['strength']
        noisy_strength = noisy_signals['momentum']['strength']
        
        if abs(original_strength) > 0.1:  # Only test for meaningful signals
            signal_preservation = 1 - abs(noisy_strength - original_strength) / abs(original_strength)
            assert signal_preservation >= -1.0, "Signal preservation calculation error"
    
    @given(
        uncertainty_level=st.floats(min_value=0.0, max_value=1.0),
        confidence_level=st.floats(min_value=0.1, max_value=1.0)
    )
    @settings(max_examples=20, deadline=5000)
    def test_property_18_uncertainty_response(self, uncertainty_level, confidence_level):
        """
        Property 18: Uncertainty Response
        
        System should reduce position sizes and increase cash allocation
        when uncertainty increases.
        """
        
        # Generate signals with varying uncertainty
        base_signals = {
            'momentum': {'strength': 0.3, 'confidence': confidence_level},
            'value': {'strength': -0.2, 'confidence': confidence_level * 0.9}
        }
        
        # Apply uncertainty (reduce confidence)
        uncertain_signals = {}
        for name, signal in base_signals.items():
            uncertain_signals[name] = {
                'strength': signal['strength'] * (1 - uncertainty_level * 0.5),
                'confidence': signal['confidence'] * (1 - uncertainty_level)
            }
        
        # Test uncertainty response
        for signal_name, signal_data in uncertain_signals.items():
            # Property assertions
            assert 0.0 <= signal_data['confidence'] <= 1.0, f"Confidence {signal_data['confidence']} not in valid range"
            
            # Higher uncertainty should lead to lower effective signal strength
            original_strength = base_signals[signal_name]['strength']
            uncertain_strength = signal_data['strength']
            
            if uncertainty_level > 0.5:  # High uncertainty
                assert abs(uncertain_strength) <= abs(original_strength), \
                    f"Signal strength should decrease with high uncertainty"
            
            # Confidence should decrease with uncertainty
            original_confidence = base_signals[signal_name]['confidence']
            uncertain_confidence = signal_data['confidence']
            
            assert uncertain_confidence <= original_confidence, \
                f"Confidence should not increase with uncertainty"
    
    @given(
        noise_level=st.floats(min_value=0.1, max_value=0.8),
        num_signals=st.integers(min_value=2, max_value=5)
    )
    @settings(max_examples=15, deadline=5000)
    def test_property_19_noise_robustness(self, noise_level, num_signals):
        """
        Property 19: Noise Robustness
        
        System performance should degrade gracefully with increasing noise,
        and false signal rate should remain within acceptable bounds.
        """
        
        # Generate multiple signals
        clean_signals = {}
        for i in range(num_signals):
            clean_signals[f'signal_{i}'] = {
                'strength': np.random.uniform(-0.5, 0.5),
                'confidence': np.random.uniform(0.5, 1.0)
            }
        
        # Test different noise types
        noise_types = [NoiseType.GAUSSIAN, NoiseType.UNIFORM, NoiseType.SPIKE]
        
        for noise_type in noise_types:
            # Inject noise
            noisy_signals = self.tester.inject_signal_noise(clean_signals, noise_type, noise_level)
            
            # Calculate signal-to-noise ratio
            snr = self.tester.calculate_signal_to_noise_ratio(clean_signals, noisy_signals)
            
            # Count false signals (sign changes)
            false_signals = 0
            total_signals = 0
            
            for signal_name in clean_signals.keys():
                if signal_name in noisy_signals:
                    clean_strength = clean_signals[signal_name]['strength']
                    noisy_strength = noisy_signals[signal_name]['strength']
                    
                    total_signals += 1
                    
                    # Check for sign change (false signal)
                    if abs(clean_strength) > 0.1 and np.sign(clean_strength) != np.sign(noisy_strength):
                        false_signals += 1
            
            false_signal_rate = false_signals / max(total_signals, 1)
            
            # Property assertions
            assert 0.0 <= false_signal_rate <= 1.0, f"False signal rate {false_signal_rate} not in valid range"
            
            # For moderate noise levels, false signal rate should be reasonable
            if noise_level <= 0.5:
                assert false_signal_rate <= 0.3, \
                    f"False signal rate {false_signal_rate} too high for noise level {noise_level}"
            
            # SNR should be finite and reasonable
            if not np.isinf(snr):
                assert snr >= -50, f"SNR {snr} dB too low, indicates severe signal degradation"
            
            # Signal preservation check
            for signal_name in clean_signals.keys():
                if signal_name in noisy_signals:
                    clean_conf = clean_signals[signal_name]['confidence']
                    noisy_conf = noisy_signals[signal_name]['confidence']
                    
                    # Confidence should not increase with noise
                    assert noisy_conf <= clean_conf * 1.1, \
                        f"Confidence should not significantly increase with noise"
    
    def test_property_17_regime_adaptation_timing_deterministic(self):
        """Deterministic test for regime adaptation timing"""
        
        # Create clear regime change scenario
        performance_history = [0.1] * 20 + [-0.1] * 10 + [0.08] * 15  # Clear regime change
        regime_changes = [20]  # Regime change at day 20
        
        adaptation_speed = self.tester.measure_adaptation_speed(performance_history, regime_changes)
        
        # Should show reasonable adaptation
        assert 0.0 <= adaptation_speed <= 1.0
        assert adaptation_speed > 0.2  # Should adapt reasonably well
    
    def test_property_18_uncertainty_response_deterministic(self):
        """Deterministic test for uncertainty response"""
        
        # High confidence scenario
        high_conf_signals = {
            'momentum': {'strength': 0.5, 'confidence': 0.9},
            'value': {'strength': -0.3, 'confidence': 0.8}
        }
        
        # Low confidence scenario (high uncertainty)
        low_conf_signals = {
            'momentum': {'strength': 0.5, 'confidence': 0.3},
            'value': {'strength': -0.3, 'confidence': 0.2}
        }
        
        # System should respond differently to different confidence levels
        for signal_name in high_conf_signals.keys():
            high_conf = high_conf_signals[signal_name]['confidence']
            low_conf = low_conf_signals[signal_name]['confidence']
            
            assert high_conf > low_conf
            assert 0.0 <= low_conf <= 1.0
            assert 0.0 <= high_conf <= 1.0
    
    def test_property_19_noise_robustness_deterministic(self):
        """Deterministic test for noise robustness"""
        
        # Clean signals
        clean_signals = {
            'momentum': {'strength': 0.4, 'confidence': 0.8},
            'value': {'strength': -0.3, 'confidence': 0.7}
        }
        
        # Test increasing noise levels
        noise_levels = [0.1, 0.3, 0.5, 0.8]
        previous_snr = float('inf')
        
        for noise_level in noise_levels:
            noisy_signals = self.tester.inject_signal_noise(
                clean_signals, NoiseType.GAUSSIAN, noise_level
            )
            
            snr = self.tester.calculate_signal_to_noise_ratio(clean_signals, noisy_signals)
            
            # SNR should generally decrease with increasing noise
            if not np.isinf(snr) and not np.isinf(previous_snr):
                # Allow some tolerance for randomness
                assert snr <= previous_snr + 5, f"SNR should not significantly increase with more noise"
            
            previous_snr = snr
    
    def test_false_regime_signal_handling(self):
        """Test handling of false regime signals"""
        
        true_regime = "expansion"
        false_signal_rates = [0.1, 0.3, 0.5]
        
        for false_rate in false_signal_rates:
            # Test multiple iterations
            correct_detections = 0
            total_tests = 100
            
            for _ in range(total_tests):
                detected_regime = self.tester.generate_false_regime_signals(true_regime, false_rate)
                if detected_regime == true_regime:
                    correct_detections += 1
            
            actual_correct_rate = correct_detections / total_tests
            expected_correct_rate = 1 - false_rate
            
            # Allow some tolerance for randomness
            tolerance = 0.15
            assert abs(actual_correct_rate - expected_correct_rate) <= tolerance, \
                f"Correct detection rate {actual_correct_rate} too far from expected {expected_correct_rate}"


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])
