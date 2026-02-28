#!/usr/bin/env python3
"""
Property-Based Tests for OOS Validator

Tests the correctness properties of the out-of-sample validation system
for institutional validation.

# Feature: institutional-validation-layers, Property 39: Out-of-Sample Validation
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
from src.validation.oos_validator import (
    OOSValidator, OOSValidationRecord, OOSResult
)


class TestOOSValidatorProperties:
    """Property-based tests for OOS Validator"""
    
    def setup_method(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        
        # Create test validator with fresh state
        self.validator = OOSValidator(
            base_dir=os.path.join(self.temp_dir, "oos")
        )
    
    def teardown_method(self):
        """Clean up test environment"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    # ========================================================================
    # PROPERTY 39: Out-of-Sample Validation
    # ========================================================================
    
    @given(
        train_sharpe=st.floats(min_value=0.5, max_value=2.0, allow_nan=False, allow_infinity=False),
        test_degradation=st.floats(min_value=0.3, max_value=1.2, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=20, deadline=10000)
    def test_property_39_oos_validation(self, train_sharpe: float, test_degradation: float):
        """
        Property 39: Out-of-Sample Validation
        
        When test Sharpe ratio is ≥ 70% of training Sharpe ratio,
        validation must pass. When below 70%, validation must fail.
        
        Validates: Requirements 20.2
        """
        
        # Generate synthetic returns with known Sharpe ratios
        np.random.seed(42)
        
        # Create date range spanning all periods
        start_date = datetime(2008, 1, 1)
        end_date = datetime(2025, 12, 31)
        dates = pd.date_range(start=start_date, end=end_date, freq='W')
        
        returns_data = []
        
        for date in dates:
            if date.year <= 2018:
                # Training period: Target Sharpe ratio
                # Sharpe = (return - rf) / volatility
                # Assume rf = 0.06, volatility = 0.15 (annualized)
                # Weekly return needed = (Sharpe * vol + rf) / 52
                weekly_return = (train_sharpe * 0.15 + 0.06) / 52
                volatility = 0.15 / np.sqrt(52)  # Weekly volatility
            elif date.year <= 2021:
                # Validation period: Moderate performance
                weekly_return = (train_sharpe * 0.8 * 0.15 + 0.06) / 52
                volatility = 0.15 / np.sqrt(52)
            else:
                # Test period: Degraded performance
                test_sharpe = train_sharpe * test_degradation
                weekly_return = (test_sharpe * 0.15 + 0.06) / 52
                volatility = 0.15 / np.sqrt(52)
            
            # Add noise
            actual_return = weekly_return + np.random.normal(0, volatility)
            returns_data.append(actual_return)
        
        strategy_returns = pd.Series(returns_data, index=dates)
        
        # Validate OOS performance
        validation_record = self.validator.validate_strategy_oos("test_strategy", strategy_returns)
        
        # PROPERTY: Validation must succeed with sufficient data
        assert validation_record.oos_result in [OOSResult.PASS, OOSResult.FAIL, OOSResult.INSUFFICIENT_DATA]
        
        # PROPERTY: If sufficient data, result must match degradation threshold
        if validation_record.oos_result in [OOSResult.PASS, OOSResult.FAIL]:
            threshold = self.validator.config['degradation_threshold']
            
            if validation_record.train_sharpe > 0:
                actual_ratio = validation_record.test_sharpe / validation_record.train_sharpe
                
                if actual_ratio >= threshold:
                    assert validation_record.oos_result == OOSResult.PASS
                else:
                    assert validation_record.oos_result == OOSResult.FAIL
        
        # PROPERTY: Degradation calculation must be correct
        if validation_record.train_sharpe != 0:
            expected_degradation = (validation_record.test_sharpe / validation_record.train_sharpe) - 1
            assert abs(validation_record.sharpe_degradation - expected_degradation) < 1e-6
    
    @given(
        n_train_obs=st.integers(min_value=20, max_value=200),
        n_test_obs=st.integers(min_value=10, max_value=100),
        mean_return=st.floats(min_value=-0.01, max_value=0.01, allow_nan=False, allow_infinity=False),
        volatility=st.floats(min_value=0.005, max_value=0.05, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=30, deadline=5000)
    def test_property_39_period_metrics_calculation(self, n_train_obs: int, n_test_obs: int, 
                                                  mean_return: float, volatility: float):
        """
        Property 39: Period Metrics Calculation
        
        Sharpe ratio calculation must be mathematically correct for each period.
        """
        
        # Generate synthetic returns
        np.random.seed(123)
        
        train_returns = np.random.normal(mean_return, volatility, n_train_obs)
        test_returns = np.random.normal(mean_return * 0.8, volatility * 1.1, n_test_obs)  # Slightly degraded
        
        # Create time series
        train_dates = pd.date_range(start='2010-01-01', periods=n_train_obs, freq='W')
        test_dates = pd.date_range(start='2022-01-01', periods=n_test_obs, freq='W')
        
        train_series = pd.Series(train_returns, index=train_dates)
        test_series = pd.Series(test_returns, index=test_dates)
        
        # Calculate metrics
        train_metrics = self.validator.calculate_period_metrics(train_series, "Train")
        test_metrics = self.validator.calculate_period_metrics(test_series, "Test")
        
        # PROPERTY: Metrics must be finite
        assert np.isfinite(train_metrics['sharpe_ratio'])
        assert np.isfinite(train_metrics['annual_return'])
        assert np.isfinite(train_metrics['annual_volatility'])
        
        assert np.isfinite(test_metrics['sharpe_ratio'])
        assert np.isfinite(test_metrics['annual_return'])
        assert np.isfinite(test_metrics['annual_volatility'])
        
        # PROPERTY: Observation counts must match
        assert train_metrics['observations'] == n_train_obs
        assert test_metrics['observations'] == n_test_obs
        
        # PROPERTY: Sharpe ratio calculation must be correct (approximately)
        if train_metrics['annual_volatility'] > 0:
            expected_sharpe = (train_metrics['annual_return'] - self.validator.config['risk_free_rate']) / train_metrics['annual_volatility']
            assert abs(train_metrics['sharpe_ratio'] - expected_sharpe) < 1e-10
    
    @given(
        train_sharpe=st.floats(min_value=0.1, max_value=2.0, allow_nan=False, allow_infinity=False),
        test_sharpe=st.floats(min_value=0.05, max_value=2.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50, deadline=5000)
    def test_property_39_validation_logic(self, train_sharpe: float, test_sharpe: float):
        """
        Property 39: Validation Logic Correctness
        
        Validation logic must correctly apply degradation threshold.
        """
        
        # Create mock metrics
        train_metrics = {
            'sharpe_ratio': train_sharpe,
            'annual_return': 0.12,
            'annual_volatility': 0.15,
            'observations': 100
        }
        
        test_metrics = {
            'sharpe_ratio': test_sharpe,
            'annual_return': 0.10,
            'annual_volatility': 0.16,
            'observations': 50
        }
        
        # Validate performance
        result, message = self.validator.validate_oos_performance(train_metrics, test_metrics)
        
        # PROPERTY: Result must be valid enum value
        assert isinstance(result, OOSResult)
        assert isinstance(message, str)
        assert len(message) > 0
        
        # PROPERTY: Logic must be consistent with threshold
        if (train_metrics['observations'] >= self.validator.config['min_train_observations'] and
            test_metrics['observations'] >= self.validator.config['min_test_observations'] and
            abs(train_sharpe) >= self.validator.config['min_sharpe_threshold']):
            
            threshold = self.validator.config['degradation_threshold']
            ratio = test_sharpe / train_sharpe
            
            if ratio >= threshold:
                assert result == OOSResult.PASS
                assert "PASS" in message
            else:
                assert result == OOSResult.FAIL
                assert "FAIL" in message
    
    # ========================================================================
    # DATA SPLITTING PROPERTIES
    # ========================================================================
    
    def test_property_data_splitting_correctness(self):
        """
        Property: Data Splitting Correctness
        
        Data must be split correctly into non-overlapping periods.
        """
        
        # Create test data spanning all periods
        start_date = datetime(2007, 1, 1)
        end_date = datetime(2026, 1, 1)
        dates = pd.date_range(start=start_date, end=end_date, freq='D')
        
        returns = pd.Series(np.random.normal(0, 0.01, len(dates)), index=dates)
        
        # Split data
        train_returns, validate_returns, test_returns = self.validator.split_data_by_periods(returns)
        
        # PROPERTY: Periods must not overlap
        if len(train_returns) > 0 and len(validate_returns) > 0:
            assert train_returns.index.max() < validate_returns.index.min()
        
        if len(validate_returns) > 0 and len(test_returns) > 0:
            assert validate_returns.index.max() < test_returns.index.min()
        
        # PROPERTY: Periods must be within expected date ranges
        if len(train_returns) > 0:
            assert train_returns.index.min() >= self.validator.config['train_start']
            assert train_returns.index.max() <= self.validator.config['train_end']
        
        if len(test_returns) > 0:
            assert test_returns.index.min() >= self.validator.config['test_start']
            assert test_returns.index.max() <= self.validator.config['test_end']
        
        # PROPERTY: Total observations should equal original (approximately)
        total_split = len(train_returns) + len(validate_returns) + len(test_returns)
        # Allow some difference due to date filtering
        assert abs(total_split - len(returns)) <= len(returns) * 0.1
    
    # ========================================================================
    # PERSISTENCE PROPERTIES
    # ========================================================================
    
    def test_property_validation_record_persistence(self):
        """
        Property: Validation Record Persistence
        
        Validation records must be persisted correctly.
        """
        
        # Create test strategy returns
        np.random.seed(42)
        
        # Generate returns spanning all periods
        start_date = datetime(2008, 1, 1)
        end_date = datetime(2025, 12, 31)
        dates = pd.date_range(start=start_date, end=end_date, freq='W')
        
        returns_data = np.random.normal(0.001, 0.02, len(dates))
        strategy_returns = pd.Series(returns_data, index=dates)
        
        # Validate strategy
        validation_record = self.validator.validate_strategy_oos("persistence_test", strategy_returns)
        
        # PROPERTY: Record must be saved to file
        oos_file = os.path.join(self.validator.oos_dir, "oos_results.parquet")
        assert os.path.exists(oos_file)
        
        # PROPERTY: Saved data must be retrievable
        saved_df = pd.read_parquet(oos_file)
        assert len(saved_df) > 0
        assert "persistence_test" in saved_df['strategy_name'].values
        
        # PROPERTY: Saved data must match original record
        saved_record = saved_df[saved_df['strategy_name'] == "persistence_test"].iloc[0]
        assert abs(saved_record['train_sharpe'] - validation_record.train_sharpe) < 1e-10
        assert abs(saved_record['test_sharpe'] - validation_record.test_sharpe) < 1e-10
        assert saved_record['oos_result'] == validation_record.oos_result.value
    
    # ========================================================================
    # SUMMARY PROPERTIES
    # ========================================================================
    
    def test_property_validation_summary(self):
        """
        Property: Validation Summary Correctness
        
        Validation summary must correctly aggregate results.
        """
        
        # Create multiple test strategies with different outcomes
        np.random.seed(42)
        
        strategies = [
            ("good_strategy", 0.002, 0.8),    # Should pass
            ("bad_strategy", 0.001, 0.5),     # Should fail
            ("marginal_strategy", 0.0015, 0.7) # Should pass (exactly at threshold)
        ]
        
        for strategy_name, base_return, test_ratio in strategies:
            # Generate returns
            start_date = datetime(2008, 1, 1)
            end_date = datetime(2025, 12, 31)
            dates = pd.date_range(start=start_date, end=end_date, freq='W')
            
            returns_data = []
            for date in dates:
                if date.year <= 2018:
                    # Training period
                    returns_data.append(base_return + np.random.normal(0, 0.015))
                else:
                    # Test period
                    returns_data.append(base_return * test_ratio + np.random.normal(0, 0.015))
            
            strategy_returns = pd.Series(returns_data, index=dates)
            self.validator.validate_strategy_oos(strategy_name, strategy_returns)
        
        # Get summary
        summary = self.validator.get_validation_summary()
        
        # PROPERTY: Summary must have correct structure
        assert 'total_strategies' in summary
        assert 'validation_results' in summary
        assert 'summary_stats' in summary
        
        # PROPERTY: Strategy count must match
        assert summary['total_strategies'] == len(strategies)
        
        # PROPERTY: All strategies must be in results
        for strategy_name, _, _ in strategies:
            assert strategy_name in summary['validation_results']
        
        # PROPERTY: Summary stats must add up
        stats = summary['summary_stats']
        total_results = stats['pass_count'] + stats['fail_count'] + stats['insufficient_data_count'] + stats['error_count']
        assert total_results == summary['total_strategies']
    
    # ========================================================================
    # VALIDATION PROPERTIES
    # ========================================================================
    
    def test_property_validation_record_validation(self):
        """
        Property: Validation Record Validation
        
        Validation records must validate correctly.
        """
        
        # Valid record
        valid_record = OOSValidationRecord(
            date=datetime.now(),
            strategy_name="valid_strategy",
            train_start=datetime(2008, 1, 1),
            train_end=datetime(2018, 12, 31),
            train_sharpe=1.2,
            train_return_annual=0.15,
            train_volatility_annual=0.12,
            train_observations=100,
            validate_start=datetime(2019, 1, 1),
            validate_end=datetime(2021, 12, 31),
            validate_sharpe=1.0,
            validate_return_annual=0.12,
            validate_volatility_annual=0.13,
            validate_observations=50,
            test_start=datetime(2022, 1, 1),
            test_end=datetime(2025, 12, 31),
            test_sharpe=0.9,
            test_return_annual=0.10,
            test_volatility_annual=0.14,
            test_observations=40,
            sharpe_degradation=-0.25,  # (0.9/1.2) - 1 = -0.25
            degradation_threshold=0.7,
            oos_result=OOSResult.PASS,
            validation_message="Test passed"
        )
        
        errors = valid_record.validate()
        
        # PROPERTY: Valid record must have no errors
        assert len(errors) == 0
        
        # Invalid record
        invalid_record = OOSValidationRecord(
            date=datetime.now(),
            strategy_name="invalid_strategy",
            train_start=datetime(2019, 1, 1),  # Invalid: after validate_start
            train_end=datetime(2018, 12, 31),
            train_sharpe=np.inf,  # Invalid: not finite
            train_return_annual=0.15,
            train_volatility_annual=0.12,
            train_observations=10,  # Invalid: too few
            validate_start=datetime(2019, 1, 1),
            validate_end=datetime(2021, 12, 31),
            validate_sharpe=1.0,
            validate_return_annual=0.12,
            validate_volatility_annual=0.13,
            validate_observations=50,
            test_start=datetime(2022, 1, 1),
            test_end=datetime(2025, 12, 31),
            test_sharpe=np.nan,  # Invalid: not finite
            test_return_annual=0.10,
            test_volatility_annual=0.14,
            test_observations=5,  # Invalid: too few
            sharpe_degradation=0.0,  # Invalid: doesn't match calculation
            degradation_threshold=0.7,
            oos_result=OOSResult.PASS,
            validation_message="Test passed"
        )
        
        errors = invalid_record.validate()
        
        # PROPERTY: Invalid record must have errors
        assert len(errors) > 0
        assert any("finite" in error.lower() for error in errors)
        assert any("insufficient" in error.lower() for error in errors)
    
    # ========================================================================
    # EDGE CASE PROPERTIES
    # ========================================================================
    
    def test_property_edge_cases(self):
        """
        Property: Edge Case Handling
        
        System must handle edge cases gracefully.
        """
        
        # Test with empty data
        empty_returns = pd.Series([], dtype=float)
        validation_record = self.validator.validate_strategy_oos("empty_strategy", empty_returns)
        assert validation_record.oos_result == OOSResult.INSUFFICIENT_DATA
        
        # Test with constant returns
        constant_dates = pd.date_range(start='2008-01-01', end='2025-12-31', freq='W')
        constant_returns = pd.Series(np.ones(len(constant_dates)) * 0.01, index=constant_dates)
        
        validation_record = self.validator.validate_strategy_oos("constant_strategy", constant_returns)
        # Should not crash, result may vary
        assert isinstance(validation_record, OOSValidationRecord)
        
        # Test with NaN values
        nan_dates = pd.date_range(start='2008-01-01', end='2025-12-31', freq='W')
        nan_returns = pd.Series([0.01 if i % 2 == 0 else np.nan for i in range(len(nan_dates))], index=nan_dates)
        
        validation_record = self.validator.validate_strategy_oos("nan_strategy", nan_returns)
        # Should handle NaN values gracefully
        assert isinstance(validation_record, OOSValidationRecord)


def test_oos_validation_record_dataclass():
    """Test OOSValidationRecord dataclass functionality"""
    
    # Create test record
    record = OOSValidationRecord(
        date=datetime(2023, 6, 15),
        strategy_name="test_strategy",
        train_start=datetime(2008, 1, 1),
        train_end=datetime(2018, 12, 31),
        train_sharpe=1.2,
        train_return_annual=0.15,
        train_volatility_annual=0.12,
        train_observations=100,
        validate_start=datetime(2019, 1, 1),
        validate_end=datetime(2021, 12, 31),
        validate_sharpe=1.0,
        validate_return_annual=0.12,
        validate_volatility_annual=0.13,
        validate_observations=50,
        test_start=datetime(2022, 1, 1),
        test_end=datetime(2025, 12, 31),
        test_sharpe=0.9,
        test_return_annual=0.10,
        test_volatility_annual=0.14,
        test_observations=40,
        sharpe_degradation=-0.25,
        degradation_threshold=0.7,
        oos_result=OOSResult.PASS,
        validation_message="Test passed"
    )
    
    # Test to_dict conversion
    record_dict = record.to_dict()
    
    assert record_dict['strategy_name'] == "test_strategy"
    assert record_dict['train_sharpe'] == 1.2
    assert record_dict['test_sharpe'] == 0.9
    assert record_dict['oos_result'] == OOSResult.PASS.value
    assert isinstance(record_dict['date'], str)  # Should be ISO format
    
    # Test validation summary
    summary = record.get_validation_summary()
    assert isinstance(summary, str)
    assert len(summary) > 0
    assert "PASS" in summary


if __name__ == "__main__":
    pytest.main([__file__])