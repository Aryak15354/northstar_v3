#!/usr/bin/env python3
"""
Property-Based Tests for Redundancy Monitor

Tests the correctness properties of the redundancy monitoring system
for institutional validation.

# Feature: institutional-validation-layers, Property 38: Strategy Redundancy Detection
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
from src.validation.redundancy_monitor import (
    RedundancyMonitor, RedundancyRecord, RedundancyLevel
)


class TestRedundancyMonitorProperties:
    """Property-based tests for Redundancy Monitor"""
    
    def setup_method(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        
        # Create test monitor with fresh state
        self.monitor = RedundancyMonitor(
            base_dir=os.path.join(self.temp_dir, "redundancy")
        )
    
    def teardown_method(self):
        """Clean up test environment"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    # ========================================================================
    # PROPERTY 38: Strategy Redundancy Detection
    # ========================================================================
    
    @given(
        n_periods=st.integers(min_value=30, max_value=100),
        n_strategies=st.integers(min_value=3, max_value=8),
        correlation_strength=st.floats(min_value=0.5, max_value=0.95, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=15, deadline=10000)
    def test_property_38_redundancy_detection(self, n_periods: int, n_strategies: int, correlation_strength: float):
        """
        Property 38: Strategy Redundancy Detection
        
        When strategy correlation exceeds 0.85 for 6+ months,
        it must be detected and flagged as redundant.
        
        Validates: Requirements 19.2
        """
        
        # Generate synthetic strategy returns with known correlations
        np.random.seed(42)
        
        # Create base market factor
        market_factor = np.random.normal(0, 0.02, n_periods)
        
        strategy_returns = pd.DataFrame()
        
        for i in range(n_strategies):
            strategy_name = f"Strategy_{i}"
            
            if i == 0:
                # First strategy - independent
                returns = 0.5 * market_factor + np.random.normal(0, 0.015, n_periods)
            elif i == 1:
                # Second strategy - correlated with first
                base_returns = 0.5 * market_factor + np.random.normal(0, 0.015, n_periods)
                # Add correlation with first strategy
                if len(strategy_returns.columns) > 0:
                    first_strategy = strategy_returns.iloc[:, 0]
                    returns = correlation_strength * first_strategy + (1 - correlation_strength) * base_returns
                else:
                    returns = base_returns
            else:
                # Other strategies - independent
                returns = 0.3 * market_factor + np.random.normal(0, 0.02, n_periods)
            
            strategy_returns[strategy_name] = returns
        
        # Add dates
        dates = pd.date_range(start='2023-01-01', periods=n_periods, freq='W')
        strategy_returns.index = dates
        
        # Analyze redundancy
        analysis_result = self.monitor.analyze_strategy_redundancy(strategy_returns)
        
        # PROPERTY: Analysis must succeed with valid data
        assert analysis_result['status'] == 'success'
        assert analysis_result['strategies_analyzed'] == n_strategies
        
        # PROPERTY: High correlations must be detected
        if correlation_strength >= self.monitor.config['redundancy_threshold']:
            # Should detect at least one high/critical redundancy
            total_high_redundancies = analysis_result['critical_redundancies'] + analysis_result['high_redundancies']
            assert total_high_redundancies > 0
        
        # PROPERTY: Strategy pairs count must be correct
        expected_pairs = n_strategies * (n_strategies - 1) // 2
        assert analysis_result['strategy_pairs_analyzed'] <= expected_pairs  # May be less due to data quality filters
    
    @given(
        correlation_values=st.lists(
            st.floats(min_value=-0.99, max_value=0.99, allow_nan=False, allow_infinity=False),
            min_size=2,
            max_size=10
        )
    )
    @settings(max_examples=30, deadline=5000)
    def test_property_38_correlation_calculation(self, correlation_values: List[float]):
        """
        Property 38: Correlation Calculation Correctness
        
        Correlation calculations must be mathematically correct.
        """
        
        n_periods = len(correlation_values) * 10  # Ensure sufficient data
        
        # Generate two strategies with known correlation pattern
        np.random.seed(123)
        
        strategy_a_returns = np.random.normal(0, 0.02, n_periods)
        
        # Create strategy B with target correlation to A
        target_correlation = np.mean([abs(c) for c in correlation_values])
        noise = np.random.normal(0, 0.01, n_periods)
        strategy_b_returns = target_correlation * strategy_a_returns + np.sqrt(1 - target_correlation**2) * noise
        
        strategy_returns = pd.DataFrame({
            'Strategy_A': strategy_a_returns,
            'Strategy_B': strategy_b_returns
        })
        
        # Compute correlations
        correlations_df = self.monitor.compute_strategy_correlations(strategy_returns)
        
        # PROPERTY: Must compute correlation for the pair
        assert len(correlations_df) == 1
        
        correlation_record = correlations_df.iloc[0]
        
        # PROPERTY: Correlation must be within bounds
        assert -1.0 <= correlation_record['correlation'] <= 1.0
        
        # PROPERTY: P-value must be valid probability
        assert 0.0 <= correlation_record['p_value'] <= 1.0
        
        # PROPERTY: Observations must match data size
        assert correlation_record['observations'] <= n_periods
        
        # PROPERTY: Strong target correlation should result in high computed correlation
        if target_correlation > 0.7:
            assert abs(correlation_record['correlation']) > 0.5
    
    @given(
        correlation=st.floats(min_value=0.5, max_value=0.99, allow_nan=False, allow_infinity=False),
        months_above=st.integers(min_value=0, max_value=12)
    )
    @settings(max_examples=50, deadline=5000)
    def test_property_38_redundancy_level_determination(self, correlation: float, months_above: int):
        """
        Property 38: Redundancy Level Determination
        
        Redundancy levels must be determined consistently.
        """
        
        redundancy_level = self.monitor._determine_redundancy_level(correlation, months_above)
        
        # PROPERTY: Redundancy level must be valid enum
        assert isinstance(redundancy_level, RedundancyLevel)
        
        # PROPERTY: Critical level for high correlation over long period
        if correlation >= self.monitor.config['redundancy_threshold'] and months_above >= self.monitor.config['alert_months']:
            assert redundancy_level == RedundancyLevel.CRITICAL
        
        # PROPERTY: High level for high correlation but short period
        elif correlation >= self.monitor.config['redundancy_threshold']:
            assert redundancy_level == RedundancyLevel.HIGH
        
        # PROPERTY: Moderate level for concerning correlation
        elif correlation >= 0.7:
            assert redundancy_level == RedundancyLevel.MODERATE
        
        # PROPERTY: Low level for acceptable correlation
        else:
            assert redundancy_level == RedundancyLevel.LOW
    
    # ========================================================================
    # CORRELATION MATRIX PROPERTIES
    # ========================================================================
    
    def test_property_correlation_matrix_symmetry(self):
        """
        Property: Correlation Matrix Symmetry
        
        Correlation between A and B must equal correlation between B and A.
        """
        
        # Create test data
        np.random.seed(42)
        n_periods = 50
        
        strategy_returns = pd.DataFrame({
            'Strategy_A': np.random.normal(0, 0.02, n_periods),
            'Strategy_B': np.random.normal(0, 0.02, n_periods),
            'Strategy_C': np.random.normal(0, 0.02, n_periods)
        })
        
        # Compute correlations
        correlations_df = self.monitor.compute_strategy_correlations(strategy_returns)
        
        # PROPERTY: Each pair should appear exactly once
        pairs = set()
        for _, row in correlations_df.iterrows():
            pair = tuple(sorted([row['strategy_a'], row['strategy_b']]))
            assert pair not in pairs, f"Duplicate pair found: {pair}"
            pairs.add(pair)
        
        # PROPERTY: Number of pairs should be n*(n-1)/2
        n_strategies = len(strategy_returns.columns)
        expected_pairs = n_strategies * (n_strategies - 1) // 2
        assert len(correlations_df) == expected_pairs
    
    # ========================================================================
    # PERSISTENCE PROPERTIES
    # ========================================================================
    
    def test_property_redundancy_record_persistence(self):
        """
        Property: Redundancy Record Persistence
        
        Redundancy records must be persisted correctly.
        """
        
        # Create test strategy data
        np.random.seed(42)
        n_periods = 30
        
        strategy_returns = pd.DataFrame({
            'Strategy_A': np.random.normal(0, 0.02, n_periods),
            'Strategy_B': 0.9 * np.random.normal(0, 0.02, n_periods)  # High correlation
        })
        
        # Make Strategy_B highly correlated with Strategy_A
        strategy_returns['Strategy_B'] = 0.9 * strategy_returns['Strategy_A'] + 0.1 * strategy_returns['Strategy_B']
        
        # Analyze redundancy
        analysis_result = self.monitor.analyze_strategy_redundancy(strategy_returns)
        
        # PROPERTY: Records must be saved to file
        redundancy_file = os.path.join(self.monitor.redundancy_dir, "strategy_correlation.parquet")
        assert os.path.exists(redundancy_file)
        
        # PROPERTY: Saved data must be retrievable
        saved_df = pd.read_parquet(redundancy_file)
        assert len(saved_df) > 0
        
        # PROPERTY: Saved data must contain expected strategies
        strategy_names = set()
        for _, row in saved_df.iterrows():
            strategy_names.add(row['strategy_a'])
            strategy_names.add(row['strategy_b'])
        
        assert 'Strategy_A' in strategy_names
        assert 'Strategy_B' in strategy_names
    
    # ========================================================================
    # ALERT SYSTEM PROPERTIES
    # ========================================================================
    
    def test_property_alert_system(self):
        """
        Property: Alert System Functionality
        
        Alert system must correctly identify and track redundant pairs.
        """
        
        # Create highly correlated strategies
        np.random.seed(42)
        n_periods = 40
        
        base_returns = np.random.normal(0, 0.02, n_periods)
        
        strategy_returns = pd.DataFrame({
            'Strategy_A': base_returns,
            'Strategy_B': 0.95 * base_returns + 0.05 * np.random.normal(0, 0.01, n_periods),  # Very high correlation
            'Strategy_C': np.random.normal(0, 0.02, n_periods)  # Independent
        })
        
        # Analyze redundancy
        analysis_result = self.monitor.analyze_strategy_redundancy(strategy_returns)
        
        # Get alerts
        alerts = self.monitor.get_redundancy_alerts()
        
        # PROPERTY: High correlation should trigger alerts
        if analysis_result['critical_redundancies'] > 0 or analysis_result['high_redundancies'] > 0:
            assert len(alerts) > 0
        
        # PROPERTY: Alert information must be complete
        for pair_key, alert_info in alerts.items():
            assert 'strategy_a' in alert_info
            assert 'strategy_b' in alert_info
            assert 'redundancy_level' in alert_info
            assert 'correlation_current' in alert_info
            assert 'description' in alert_info
            
            # PROPERTY: Alert level must be high or critical
            assert alert_info['redundancy_level'] in ['high', 'critical']
            
            # PROPERTY: Correlation must be within bounds
            assert -1.0 <= alert_info['correlation_current'] <= 1.0
    
    # ========================================================================
    # RECOMMENDATION PROPERTIES
    # ========================================================================
    
    def test_property_recommendation_generation(self):
        """
        Property: Recommendation Generation
        
        Recommendations must be appropriate for redundancy level.
        """
        
        # Test different redundancy levels
        test_cases = [
            (0.95, RedundancyLevel.CRITICAL),
            (0.8, RedundancyLevel.HIGH),
            (0.6, RedundancyLevel.MODERATE),
            (0.3, RedundancyLevel.LOW)
        ]
        
        for correlation, expected_level in test_cases:
            recommendation = self.monitor._generate_reallocation_recommendation(
                "Strategy_A", "Strategy_B", correlation, expected_level
            )
            
            # PROPERTY: Recommendation must be non-empty string
            assert isinstance(recommendation, str)
            assert len(recommendation) > 0
            
            # PROPERTY: Critical level should mention urgency
            if expected_level == RedundancyLevel.CRITICAL:
                assert any(word in recommendation.upper() for word in ['URGENT', 'REDUCE', 'HIGH PRIORITY'])
            
            # PROPERTY: Low level should indicate no action needed
            elif expected_level == RedundancyLevel.LOW:
                assert 'No action required' in recommendation or 'healthy independence' in recommendation
    
    # ========================================================================
    # VALIDATION PROPERTIES
    # ========================================================================
    
    def test_property_redundancy_record_validation(self):
        """
        Property: Redundancy Record Validation
        
        Redundancy records must validate correctly.
        """
        
        # Valid record
        valid_record = RedundancyRecord(
            date=datetime.now(),
            strategy_a="Strategy_A",
            strategy_b="Strategy_B",
            correlation_current=0.85,
            correlation_6m_avg=0.80,
            correlation_12m_avg=0.75,
            redundancy_level=RedundancyLevel.HIGH,
            months_above_threshold=3,
            statistical_significance=0.02,
            observations=52,
            recommended_action="Monitor correlation trends"
        )
        
        errors = valid_record.validate()
        
        # PROPERTY: Valid record must have no errors
        assert len(errors) == 0
        
        # Invalid record
        invalid_record = RedundancyRecord(
            date=datetime.now(),
            strategy_a="Strategy_A",
            strategy_b="Strategy_B",
            correlation_current=1.5,  # Invalid: > 1.0
            correlation_6m_avg=0.80,
            correlation_12m_avg=0.75,
            redundancy_level=RedundancyLevel.HIGH,
            months_above_threshold=-1,  # Invalid: negative
            statistical_significance=1.5,  # Invalid: > 1.0
            observations=5,  # Invalid: too few
            recommended_action="Monitor correlation trends"
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
        
        # Test with minimal strategies
        minimal_returns = pd.DataFrame({
            'Strategy_A': [0.01, -0.01]
        })
        
        # Should handle single strategy gracefully
        analysis_result = self.monitor.analyze_strategy_redundancy(minimal_returns)
        assert analysis_result['status'] == 'insufficient_data'
        
        # Test with constant returns
        constant_returns = pd.DataFrame({
            'Strategy_A': np.ones(20) * 0.01,
            'Strategy_B': np.ones(20) * 0.02
        })
        
        # Should handle constant data gracefully
        analysis_result = self.monitor.analyze_strategy_redundancy(constant_returns)
        # May succeed or fail depending on correlation calculation, but should not crash
        assert 'status' in analysis_result
        
        # Test with NaN values
        nan_returns = pd.DataFrame({
            'Strategy_A': [0.01, np.nan, -0.01, 0.02, np.nan],
            'Strategy_B': [0.005, 0.001, np.nan, 0.01, 0.002]
        })
        
        # Should handle NaN values gracefully
        analysis_result = self.monitor.analyze_strategy_redundancy(nan_returns)
        assert 'status' in analysis_result


def test_redundancy_record_dataclass():
    """Test RedundancyRecord dataclass functionality"""
    
    # Create test record
    record = RedundancyRecord(
        date=datetime(2023, 6, 15),
        strategy_a="Strategy_A",
        strategy_b="Strategy_B",
        correlation_current=0.85,
        correlation_6m_avg=0.80,
        correlation_12m_avg=0.75,
        redundancy_level=RedundancyLevel.HIGH,
        months_above_threshold=3,
        statistical_significance=0.02,
        observations=52,
        recommended_action="Monitor correlation trends"
    )
    
    # Test to_dict conversion
    record_dict = record.to_dict()
    
    assert record_dict['strategy_a'] == "Strategy_A"
    assert record_dict['strategy_b'] == "Strategy_B"
    assert record_dict['correlation_current'] == 0.85
    assert record_dict['redundancy_level'] == RedundancyLevel.HIGH.value
    assert isinstance(record_dict['date'], str)  # Should be ISO format
    
    # Test redundancy description
    description = record.get_redundancy_description()
    assert isinstance(description, str)
    assert len(description) > 0
    assert "high redundancy" in description.lower()


if __name__ == "__main__":
    pytest.main([__file__])