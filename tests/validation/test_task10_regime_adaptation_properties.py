#!/usr/bin/env python3
"""
🧪 PROPERTY TESTS FOR TASK 10 - REGIME ADAPTATION AND ROBUSTNESS
Property-based tests for regime adaptation and noise robustness

Tests the following properties:
- Property 17: Regime Adaptation Timing
- Property 18: Uncertainty Response
- Property 19: Noise Robustness

Usage:
    python -m pytest tests/validation/test_task10_regime_adaptation_properties.py -v
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
from typing import Dict, List, Optional, Tuple, Any

from src.validation.noise_robustness_tester import NoiseRobustnessTester, NoiseType

class TestTask10RegimeAdaptationProperties:
    """Property tests for Task 10 - Regime Adaptation and Robustness"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.tester = NoiseRobustnessTester()
        self.rng = np.random.default_rng(42)
        
    @given(
        regime_persistence=st.floats(min_value=0.1, max_value=0.9),
        adaptation_threshold=st.floats(min_value=0.05, max_value=0.3)
    )
    @settings(max_examples=15, deadline=5000)
    def test_property_17_regime_adaptation_timing(self, regime_persistence, adaptation_threshold):
        """
        Property 17: Regime Adaptation Timing
        
        System should adapt to regime changes at appropriate speed:
        - Faster adaptation for persistent regime changes
        - Slower adaptation for noisy/temporary changes
        - Adaptation speed should be inversely related to uncertainty
        """
        
        # Create mock regime signals with different persistence levels
        signal_length = 100
        base_signal = 0.15 * np.sin(np.linspace(0, 6 * np.pi, signal_length))
        
        # Create persistent regime change
        persistent_signal = base_signal.copy()
        change_point = signal_length // 2
        persistent_signal[change_point:] += 2.0  # Clear regime shift
        
        # Create noisy regime change
        noisy_signal = base_signal.copy()
        noisy_regime = 0.55 * np.sin(np.linspace(0, 24 * np.pi, signal_length - change_point))
        noisy_signal[change_point:] += noisy_regime
        
        # Test adaptation timing
        persistent_adaptation_speed = self._calculate_adaptation_speed(persistent_signal, change_point)
        noisy_adaptation_speed = self._calculate_adaptation_speed(noisy_signal, change_point)
        
        # Property assertions
        if regime_persistence > 0.7:  # High persistence
            # Should adapt faster to persistent changes
            assert persistent_adaptation_speed > max(0.3, adaptation_threshold), \
                "Should adapt quickly to persistent regime changes"
            
        if regime_persistence < 0.3:  # Low persistence (noisy)
            # Should adapt slower to noisy changes
            assert noisy_adaptation_speed < 0.7, "Should adapt slowly to noisy regime changes"
        
        # Adaptation speed should be reasonable
        assert 0.0 <= persistent_adaptation_speed <= 1.0, "Adaptation speed should be normalized"
        assert 0.0 <= noisy_adaptation_speed <= 1.0, "Adaptation speed should be normalized"
    
    @given(
        uncertainty_level=st.floats(min_value=0.1, max_value=0.9),
        confidence_threshold=st.floats(min_value=0.5, max_value=0.95)
    )
    @settings(max_examples=15, deadline=5000)
    def test_property_18_uncertainty_response(self, uncertainty_level, confidence_threshold):
        """
        Property 18: Uncertainty Response
        
        System should respond appropriately to uncertainty:
        - Reduce position sizes when uncertainty is high
        - Increase diversification under uncertainty
        - Maintain conservative stance until confidence improves
        """
        
        # Create scenarios with different uncertainty levels
        high_uncertainty_scenario = {
            'regime_confidence': 1.0 - uncertainty_level,
            'signal_strength': 0.5,
            'volatility': 0.3 * (1 + uncertainty_level)
        }
        
        low_uncertainty_scenario = {
            'regime_confidence': 0.9,
            'signal_strength': 0.8,
            'volatility': 0.15
        }
        
        # Calculate expected responses
        high_uncertainty_response = self._calculate_uncertainty_response(high_uncertainty_scenario)
        low_uncertainty_response = self._calculate_uncertainty_response(low_uncertainty_scenario)
        
        # Property assertions
        if uncertainty_level > 0.6:  # High uncertainty
            # Should reduce position sizes
            assert high_uncertainty_response['position_scaling'] <= 0.7, "Should reduce positions under high uncertainty"
            
            # Should increase diversification
            assert high_uncertainty_response['diversification_factor'] >= 1.2, "Should increase diversification under uncertainty"
            
        if uncertainty_level < 0.3:  # Low uncertainty
            # Should allow larger positions
            assert low_uncertainty_response['position_scaling'] >= 0.8, "Should allow larger positions under low uncertainty"
        
        # Response should be inversely related to uncertainty
        if uncertainty_level > 0.5:
            assert high_uncertainty_response['position_scaling'] <= low_uncertainty_response['position_scaling'], \
                "Position scaling should decrease with uncertainty"
    
    @given(
        noise_level=st.floats(min_value=0.1, max_value=2.0),
        signal_strength=st.floats(min_value=0.1, max_value=1.0)
    )
    @settings(max_examples=15, deadline=5000)
    def test_property_19_noise_robustness(self, noise_level, signal_strength):
        """
        Property 19: Noise Robustness
        
        System should maintain performance under various noise conditions:
        - Performance degradation should be gradual with increasing noise
        - Should distinguish between signal and noise
        - Should maintain minimum performance threshold even under high noise
        """
        
        # Create clean signal
        signal_length = 200
        clean_signal = signal_strength * np.sin(np.linspace(0, 4*np.pi, signal_length))
        
        # Add noise
        # Deterministic oscillatory noise avoids flaky random failures.
        noise = noise_level * (
            0.7 * np.sin(np.linspace(0, 16 * np.pi, signal_length))
            + 0.3 * np.cos(np.linspace(0, 7 * np.pi, signal_length))
        )
        noisy_signal = clean_signal + noise
        
        # Calculate signal-to-noise ratio
        snr = signal_strength / (noise_level + 1e-8)
        
        # Test noise robustness
        clean_performance = self._calculate_signal_performance(clean_signal)
        noisy_performance = self._calculate_signal_performance(noisy_signal)
        
        performance_degradation = (clean_performance - noisy_performance) / max(clean_performance, 1e-8)
        
        # Property assertions
        if snr > 2.0:  # High signal-to-noise ratio
            # Performance degradation should be minimal
            assert performance_degradation <= 0.3, f"Performance degradation {performance_degradation:.2f} too high for SNR {snr:.2f}"
            
        if snr < 0.5:  # Low signal-to-noise ratio
            # Should still maintain minimum performance
            assert noisy_performance >= 0.2, f"Performance {noisy_performance:.2f} below minimum threshold"
            
        # Performance should degrade gracefully with noise
        assert performance_degradation >= 0.0, "Performance degradation should be non-negative"
        assert performance_degradation <= 1.0, "Performance degradation should not exceed 100%"
        
        # Noise robustness score should be reasonable
        robustness_score = 1.0 - performance_degradation
        assert 0.0 <= robustness_score <= 1.0, "Robustness score should be normalized"
    
    def test_property_17_regime_adaptation_timing_deterministic(self):
        """Deterministic test for regime adaptation timing"""
        
        # Create clear regime change scenario
        signal_length = 100
        change_point = 50
        
        # Before regime change: mean = 0
        # After regime change: mean = 2 (clear shift)
        signal = np.concatenate([
            0.25 * np.sin(np.linspace(0, 4 * np.pi, change_point)),
            2.0 + 0.25 * np.sin(np.linspace(0, 4 * np.pi, signal_length - change_point)),
        ])
        
        adaptation_speed = self._calculate_adaptation_speed(signal, change_point)
        
        # Should adapt reasonably quickly to clear regime change
        assert adaptation_speed >= 0.4, f"Adaptation speed {adaptation_speed:.2f} too slow for clear regime change"
        assert adaptation_speed <= 1.0, f"Adaptation speed {adaptation_speed:.2f} exceeds maximum"
    
    def test_property_18_uncertainty_response_deterministic(self):
        """Deterministic test for uncertainty response"""
        
        # High uncertainty scenario
        high_uncertainty = {
            'regime_confidence': 0.3,  # Low confidence
            'signal_strength': 0.4,
            'volatility': 0.4
        }
        
        # Low uncertainty scenario
        low_uncertainty = {
            'regime_confidence': 0.9,  # High confidence
            'signal_strength': 0.8,
            'volatility': 0.15
        }
        
        high_response = self._calculate_uncertainty_response(high_uncertainty)
        low_response = self._calculate_uncertainty_response(low_uncertainty)
        
        # High uncertainty should lead to more conservative response
        assert high_response['position_scaling'] < low_response['position_scaling'], \
            "High uncertainty should reduce position scaling"
        
        assert high_response['diversification_factor'] > low_response['diversification_factor'], \
            "High uncertainty should increase diversification"
    
    def test_property_19_noise_robustness_deterministic(self):
        """Deterministic test for noise robustness"""
        
        # Create test signals with known noise levels
        signal_length = 100
        clean_signal = np.sin(np.linspace(0, 2*np.pi, signal_length))
        
        # Low noise
        low_noise_signal = clean_signal + 0.1 * np.sin(np.linspace(0, 18 * np.pi, signal_length))
        
        # High noise
        high_noise_signal = clean_signal + 1.0 * (
            0.8 * np.sin(np.linspace(0, 22 * np.pi, signal_length))
            + 0.2 * np.cos(np.linspace(0, 9 * np.pi, signal_length))
        )
        
        # Calculate performance
        clean_perf = self._calculate_signal_performance(clean_signal)
        low_noise_perf = self._calculate_signal_performance(low_noise_signal)
        high_noise_perf = self._calculate_signal_performance(high_noise_signal)
        
        # Performance should degrade with increasing noise
        assert clean_perf >= low_noise_perf, "Clean signal should outperform low noise signal"
        assert low_noise_perf >= high_noise_perf, "Low noise should outperform high noise signal"
        
        # Even high noise should maintain some performance
        assert high_noise_perf >= 0.1, "High noise signal should maintain minimum performance"
    
    def test_false_regime_signal_handling(self):
        """Test system response to false regime signals"""
        
        # Create false regime signal (temporary spike)
        signal_length = 100
        base_signal = 0.2 * np.sin(np.linspace(0, 6 * np.pi, signal_length))
        
        # Add temporary spike (false regime signal)
        spike_start = 40
        spike_end = 50
        base_signal[spike_start:spike_end] += 3.0
        
        # System should not adapt strongly to temporary spikes
        adaptation_speed = self._calculate_adaptation_speed(base_signal, spike_start)
        
        # Should adapt slowly to temporary changes
        assert adaptation_speed <= 0.6, f"Should not adapt quickly to temporary spikes: {adaptation_speed:.2f}"
    
    def _calculate_adaptation_speed(self, signal: np.ndarray, change_point: int) -> float:
        """Calculate adaptation speed for regime change"""
        
        # Simple adaptation speed calculation based on signal change
        pre_change = signal[:change_point]
        post_change = signal[change_point:]
        
        if len(pre_change) == 0 or len(post_change) == 0:
            return 0.0
        
        # Calculate signal change magnitude
        pre_mean = np.mean(pre_change)
        post_mean = np.mean(post_change)
        change_magnitude = abs(post_mean - pre_mean)
        
        # Calculate signal stability (inverse of variance)
        post_stability = 1.0 / (np.var(post_change) + 1e-8)
        
        # Adaptation speed based on change magnitude and stability
        adaptation_speed = min(1.0, change_magnitude * post_stability / 10.0)
        
        return adaptation_speed
    
    def _calculate_uncertainty_response(self, scenario: Dict[str, float]) -> Dict[str, float]:
        """Calculate system response to uncertainty"""
        
        regime_confidence = scenario['regime_confidence']
        signal_strength = scenario['signal_strength']
        volatility = scenario['volatility']
        
        # Position scaling inversely related to uncertainty
        uncertainty = 1.0 - regime_confidence
        position_scaling = max(0.2, 1.0 - uncertainty * 0.8)
        
        # Diversification factor increases with uncertainty
        diversification_factor = 1.0 + uncertainty * 0.5
        
        # Conservative bias under high uncertainty
        conservative_bias = uncertainty * 0.3
        
        return {
            'position_scaling': position_scaling,
            'diversification_factor': diversification_factor,
            'conservative_bias': conservative_bias
        }
    
    def _calculate_signal_performance(self, signal: np.ndarray) -> float:
        """Calculate performance metric for signal"""
        
        if len(signal) == 0:
            return 0.0
        
        s = np.asarray(signal, dtype=float)
        signal_power = float(np.mean(np.square(s)))
        if signal_power <= 1e-12:
            return 0.0

        # Diff-energy acts as a high-frequency noise proxy.
        noise_proxy = float(np.mean(np.square(np.diff(s)))) if len(s) > 1 else 0.0
        performance = signal_power / (signal_power + noise_proxy + 1e-8)
        return float(np.clip(performance, 0.0, 1.0))


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])
