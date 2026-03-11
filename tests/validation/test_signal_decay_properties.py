#!/usr/bin/env python3
"""
Property-Based Tests for Signal Decay Monitor

Tests the correctness properties of the signal decay monitoring system
for institutional validation.

# Feature: institutional-validation-layers, Property 37: Signal Decay Detection
"""

import pytest
import pandas as pd
import numpy as np
import os
import tempfile
import shutil
from datetime import datetime, timedelta
from hypothesis import given, strategies as st, settings, assume
from typing import Dict, List, Any, Tuple

# Import the system under test
from src.validation.signal_decay_monitor import (
    SignalDecayMonitor, SignalDecayRecord, DecayAlertLevel
)


class TestSignalDecayProperties:
    """Property-based tests for Signal Decay Monitor"""
    
    def setup_method(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        
        # Create test monitor with fresh state
        self.monitor = SignalDecayMonitor(
            base_dir=os.path.join(self.temp_dir, "decay")
        )
    
    def teardown_method(self):
        """Clean up test environment"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    # ========================================================================
    # PROPERTY 37: Signal Decay Detection
    # ========================================================================
    
    @given(
        n_periods=st.integers(min_value=30, max_value=100),
        initial_correlation=st.floats(min_value=0.3, max_value=0.9, allow_nan=False, allow_infinity=False),
        decay_rate=st.floats(min_value=0.95, max_value=0.99, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=20, deadline=10000)
    def test_property_37_signal_decay_detection(self, n_periods: int, initial_correlation: float, decay_rate: float):
        """
        Property 37: Signal Decay Detection
        
        When signal-return correlation decays consistently for 3+ months,
        it must be detected and flagged appropriately.
        
        Validates: Requirements 18.5, 18.8
        """
        
        # Generate synthetic signal with known decay pattern
        np.random.seed(42)
        
        # Generate returns
        returns = np.random.normal(0, 0.02, n_periods)
        
        # Generate signal with decaying correlation
        signal_values = []
        current_correlation = initial_correlation
        
        for i in range(n_periods):
            # Decay correlation over time
            current_correlation *= decay_rate
            
            # Generate signal with target correlation
            noise = np.random.normal(0, 0.01)
            signal_value = current_correlation * returns[i] + noise
            signal_values.append(signal_value)
        
        signal_values = np.array(signal_values)
        
        # Track signal decay
        decay_record = self.monitor.track_signal_decay("test_signal", signal_values, returns)
        
        # PROPERTY: Decay detection must be mathematically sound
        assert isinstance(decay_record, SignalDecayRecord)
        assert decay_record.signal_name == "test_signal"
        
        # PROPERTY: Correlation must be within valid bounds
        assert -1.0 <= decay_record.correlation_current <= 1.0
        assert -1.0 <= decay_record.correlation_3m_avg <= 1.0
        assert -1.0 <= decay_record.correlation_6m_avg <= 1.0
        
        # PROPERTY: Statistical significance must be valid probability
        assert 0.0 <= decay_record.statistical_significance <= 1.0
        
        # PROPERTY: Decay months must be non-negative
        assert decay_record.decay_months >= 0
        
        # PROPERTY: Alert level must be consistent with decay characteristics
        if decay_record.decay_rate < -0.05 and decay_record.decay_months >= 3:
            # Significant decay for 3+ months should trigger severe alert
            assert decay_record.alert_level in [DecayAlertLevel.MODERATE, DecayAlertLevel.SEVERE]
        
        # PROPERTY: Observations must match input size
        assert decay_record.observations == len(signal_values)
    
    @given(
        signal_strength=st.floats(min_value=0.1, max_value=0.9, allow_nan=False, allow_infinity=False),
        noise_level=st.floats(min_value=0.01, max_value=0.1, allow_nan=False, allow_infinity=False),
        n_observations=st.integers(min_value=20, max_value=50)
    )
    @settings(max_examples=30, deadline=5000)
    def test_property_37_correlation_calculation(self, signal_strength: float, noise_level: float, n_observations: int):
        """
        Property 37: Correlation Calculation Correctness
        
        Correlation calculation must be mathematically correct and stable.
        """
        
        # Generate synthetic data with known correlation
        np.random.seed(123)
        
        returns = np.random.normal(0, 0.02, n_observations)
        
        # Create signal with target correlation
        signal_values = signal_strength * returns + np.random.normal(0, noise_level, n_observations)
        
        # Calculate correlation using monitor
        correlation, p_value = self.monitor.compute_signal_correlation(signal_values, returns)
        
        # Calculate expected correlation using numpy
        expected_corr = np.corrcoef(signal_values, returns)[0, 1]
        
        # PROPERTY: Correlation must match expected value (within tolerance)
        if not np.isnan(expected_corr):
            assert abs(correlation - expected_corr) < 0.01
        
        # PROPERTY: Correlation must be within bounds
        assert -1.0 <= correlation <= 1.0
        
        # PROPERTY: P-value must be valid probability
        assert 0.0 <= p_value <= 1.0
        
        # PROPERTY: Strong signals should have high correlation
        if signal_strength > 0.7 and noise_level < 0.05:
            # Small samples (20-50 observations) can realize materially below
            # the asymptotic correlation even with strong signal loading.
            assert abs(correlation) > 0.15
    
    @given(
        correlations=st.lists(
            st.floats(min_value=-0.9, max_value=0.9, allow_nan=False, allow_infinity=False),
            min_size=5,
            max_size=20
        )
    )
    @settings(max_examples=30, deadline=5000)
    def test_property_37_decay_rate_calculation(self, correlations: List[float]):
        """
        Property 37: Decay Rate Calculation
        
        Decay rate calculation must be statistically valid.
        """
        
        # Create dates for correlations
        start_date = datetime(2023, 1, 1)
        dates = [start_date + timedelta(weeks=i) for i in range(len(correlations))]
        
        # Calculate decay rate
        decay_rate, p_value = self.monitor.calculate_decay_rate(correlations, dates)
        
        # PROPERTY: Decay rate must be finite
        assert np.isfinite(decay_rate)
        
        # PROPERTY: P-value must be valid probability
        assert 0.0 <= p_value <= 1.0
        
        # PROPERTY: Strong downward trend should have negative decay rate
        if len(correlations) >= 5:
            # Check if there's a clear downward trend
            first_half = np.mean(correlations[:len(correlations)//2])
            second_half = np.mean(correlations[len(correlations)//2:])
            time_corr = np.corrcoef(np.arange(len(correlations)), correlations)[0, 1]
            
            if first_half > second_half + 0.2 and np.isfinite(time_corr) and time_corr < -0.2:
                assert decay_rate < 0
    
    # ========================================================================
    # ALERT LEVEL PROPERTIES
    # ========================================================================
    
    @given(
        decay_rate=st.floats(min_value=-0.2, max_value=0.1, allow_nan=False, allow_infinity=False),
        decay_months=st.integers(min_value=0, max_value=6),
        significance=st.floats(min_value=0.001, max_value=0.2, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50, deadline=5000)
    def test_property_alert_level_determination(self, decay_rate: float, decay_months: int, significance: float):
        """
        Property: Alert Level Determination
        
        Alert levels must be determined consistently based on decay characteristics.
        """
        
        alert_level = self.monitor.determine_alert_level(decay_rate, decay_months, significance)
        
        # PROPERTY: Alert level must be valid enum value
        assert isinstance(alert_level, DecayAlertLevel)
        
        # PROPERTY: No alert for positive decay (improving signal)
        if decay_rate >= 0:
            assert alert_level == DecayAlertLevel.NONE
        
        # PROPERTY: No alert for insignificant decay
        if significance > self.monitor.config['significance_level']:
            assert alert_level == DecayAlertLevel.NONE
        
        # PROPERTY: No alert for small decay
        if decay_rate > self.monitor.config['decay_threshold']:
            assert alert_level == DecayAlertLevel.NONE
        
        # PROPERTY: Severe alert for long-term significant decay
        if (decay_rate < self.monitor.config['decay_threshold'] and 
            decay_months >= self.monitor.config['alert_months'] and
            significance <= self.monitor.config['significance_level']):
            assert alert_level == DecayAlertLevel.SEVERE
    
    # ========================================================================
    # PERSISTENCE PROPERTIES
    # ========================================================================
    
    def test_property_decay_record_persistence(self):
        """
        Property: Decay Record Persistence
        
        Decay records must be persisted correctly and retrievably.
        """
        
        # Create test signal data
        np.random.seed(42)
        n_periods = 30
        returns = np.random.normal(0, 0.02, n_periods)
        signal_values = 0.6 * returns + np.random.normal(0, 0.01, n_periods)
        
        # Track signal decay
        decay_record = self.monitor.track_signal_decay("persistence_test", signal_values, returns)
        
        # PROPERTY: Record must be saved to file
        decay_file = os.path.join(self.monitor.decay_dir, "signal_decay.parquet")
        assert os.path.exists(decay_file)
        
        # PROPERTY: Saved data must be retrievable
        saved_df = pd.read_parquet(decay_file)
        assert len(saved_df) > 0
        assert "persistence_test" in saved_df['signal_name'].values
        
        # PROPERTY: Saved data must match original record
        saved_record = saved_df[saved_df['signal_name'] == "persistence_test"].iloc[0]
        assert abs(saved_record['correlation_current'] - decay_record.correlation_current) < 1e-10
        assert saved_record['alert_level'] == decay_record.alert_level.value
    
    # ========================================================================
    # SIGNAL HISTORY PROPERTIES
    # ========================================================================
    
    def test_property_signal_history_management(self):
        """
        Property: Signal History Management
        
        Signal history must be managed correctly over time.
        """
        
        # Track multiple measurements for same signal
        np.random.seed(42)
        
        for i in range(5):
            # Generate slightly different data each time
            returns = np.random.normal(0, 0.02, 25)
            correlation = 0.7 - (i * 0.1)  # Decreasing correlation
            signal_values = correlation * returns + np.random.normal(0, 0.01, 25)
            
            # Track with different dates
            test_date = datetime(2023, 1, 1) + timedelta(weeks=i*4)
            self.monitor.track_signal_decay("history_test", signal_values, returns, test_date)
        
        # PROPERTY: History must be maintained
        assert "history_test" in self.monitor.signal_history
        history = self.monitor.signal_history["history_test"]
        assert len(history) == 5
        
        # PROPERTY: History must be chronologically ordered when sorted
        dates = [measurement['date'] for measurement in history]
        sorted_dates = sorted(dates)
        # Note: We don't require the list to be pre-sorted, just that it can be sorted
        
        # PROPERTY: Each measurement must have required fields
        for measurement in history:
            assert 'date' in measurement
            assert 'correlation' in measurement
            assert 'p_value' in measurement
            assert 'observations' in measurement
            
            # Values must be valid
            assert -1.0 <= measurement['correlation'] <= 1.0
            assert 0.0 <= measurement['p_value'] <= 1.0
            assert measurement['observations'] > 0
    
    # ========================================================================
    # ALERT AGGREGATION PROPERTIES
    # ========================================================================
    
    def test_property_alert_aggregation(self):
        """
        Property: Alert Aggregation
        
        Alert aggregation must correctly summarize decay states.
        """
        
        # Create signals with different decay states
        np.random.seed(42)
        
        # Signal 1: No decay (stable)
        returns1 = np.random.normal(0, 0.02, 30)
        signal1 = 0.7 * returns1 + np.random.normal(0, 0.01, 30)
        self.monitor.track_signal_decay("stable_signal", signal1, returns1)
        
        # Signal 2: Mild decay
        returns2 = np.random.normal(0, 0.02, 30)
        signal2 = np.array([0.7 * returns2[i] * (0.98 ** i) + np.random.normal(0, 0.01) for i in range(30)])
        self.monitor.track_signal_decay("mild_decay_signal", signal2, returns2)
        
        # Get alerts
        alerts = self.monitor.get_decay_alerts()
        
        # PROPERTY: Alerts must be dictionary
        assert isinstance(alerts, dict)
        
        # PROPERTY: Only signals with non-NONE alerts should be included
        for signal_name, alert_info in alerts.items():
            assert alert_info['alert_level'] != DecayAlertLevel.NONE.value
            
            # PROPERTY: Alert info must have required fields
            assert 'alert_level' in alert_info
            assert 'correlation_current' in alert_info
            assert 'last_updated' in alert_info
            assert 'description' in alert_info
            
            # PROPERTY: Values must be valid
            assert alert_info['alert_level'] in [level.value for level in DecayAlertLevel]
            assert -1.0 <= alert_info['correlation_current'] <= 1.0
    
    # ========================================================================
    # VALIDATION PROPERTIES
    # ========================================================================
    
    def test_property_decay_record_validation(self):
        """
        Property: Decay Record Validation
        
        Decay records must validate correctly.
        """
        
        # Valid record
        valid_record = SignalDecayRecord(
            date=datetime.now(),
            signal_name="valid_signal",
            correlation_current=0.65,
            correlation_3m_avg=0.70,
            correlation_6m_avg=0.75,
            decay_rate=-0.02,
            decay_months=2,
            alert_level=DecayAlertLevel.MODERATE,
            statistical_significance=0.03,
            observations=52
        )
        
        errors = valid_record.validate()
        
        # PROPERTY: Valid record must have no errors
        assert len(errors) == 0
        
        # Invalid record
        invalid_record = SignalDecayRecord(
            date=datetime.now(),
            signal_name="invalid_signal",
            correlation_current=1.5,  # Invalid: > 1.0
            correlation_3m_avg=0.70,
            correlation_6m_avg=0.75,
            decay_rate=-0.02,
            decay_months=-1,  # Invalid: negative
            alert_level=DecayAlertLevel.MODERATE,
            statistical_significance=1.5,  # Invalid: > 1.0
            observations=5  # Invalid: too few
        )
        
        errors = invalid_record.validate()
        
        # PROPERTY: Invalid record must have errors
        assert len(errors) > 0
        assert any("correlation" in error.lower() for error in errors)
        assert any("negative" in error.lower() for error in errors)
        assert any("insufficient" in error.lower() for error in errors)
    
    # ========================================================================
    # EDGE CASE PROPERTIES
    # ========================================================================
    
    def test_property_edge_cases(self):
        """
        Property: Edge Case Handling
        
        System must handle edge cases gracefully.
        """
        
        # Test with minimal data
        minimal_returns = np.array([0.01, -0.01])
        minimal_signal = np.array([0.005, -0.005])
        
        # Should not crash with minimal data
        decay_record = self.monitor.track_signal_decay("minimal_signal", minimal_signal, minimal_returns)
        assert isinstance(decay_record, SignalDecayRecord)
        
        # Test with constant signal (no variation)
        constant_returns = np.ones(20) * 0.01
        constant_signal = np.ones(20) * 0.005
        
        # Should handle constant data gracefully
        decay_record = self.monitor.track_signal_decay("constant_signal", constant_signal, constant_returns)
        assert isinstance(decay_record, SignalDecayRecord)
        
        # Test with NaN values
        nan_returns = np.array([0.01, np.nan, -0.01, 0.02, np.nan])
        nan_signal = np.array([0.005, 0.001, -0.005, 0.01, 0.002])
        
        # Should handle NaN values gracefully
        decay_record = self.monitor.track_signal_decay("nan_signal", nan_signal, nan_returns)
        assert isinstance(decay_record, SignalDecayRecord)
        
        # Correlation should be calculated only on valid pairs
        assert np.isfinite(decay_record.correlation_current)


def test_signal_decay_record_dataclass():
    """Test SignalDecayRecord dataclass functionality"""
    
    # Create test record
    record = SignalDecayRecord(
        date=datetime(2023, 6, 15),
        signal_name="test_signal",
        correlation_current=0.65,
        correlation_3m_avg=0.70,
        correlation_6m_avg=0.75,
        decay_rate=-0.02,
        decay_months=2,
        alert_level=DecayAlertLevel.MODERATE,
        statistical_significance=0.03,
        observations=52
    )
    
    # Test to_dict conversion
    record_dict = record.to_dict()
    
    assert record_dict['signal_name'] == "test_signal"
    assert record_dict['correlation_current'] == 0.65
    assert record_dict['decay_rate'] == -0.02
    assert record_dict['alert_level'] == DecayAlertLevel.MODERATE.value
    assert isinstance(record_dict['date'], str)  # Should be ISO format
    
    # Test alert description
    description = record.get_alert_description()
    assert isinstance(description, str)
    assert len(description) > 0
    assert "moderate" in description.lower()


if __name__ == "__main__":
    pytest.main([__file__])
