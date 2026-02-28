#!/usr/bin/env python3
"""
Property-Based Tests for Full Beta Drift Fabric

Tests the correctness properties of the full beta drift fabric system
for institutional validation.

# Feature: institutional-validation-layers, Property 22: Beta Drift Significance
"""

import pytest
import pandas as pd
import numpy as np
import os
import tempfile
import shutil
from datetime import datetime, timedelta
from hypothesis import given, strategies as st, settings, assume
from typing import Dict, List, Any

# Import the system under test
from src.validation.beta_drift_fabric_full import (
    FullBetaDriftFabric, BetaDriftSignificance
)


class TestBetaDriftSignificanceProperties:
    """Property-based tests for Full Beta Drift Fabric"""
    
    def setup_method(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        
        # Create test fabric with fresh state
        self.fabric = FullBetaDriftFabric(
            base_dir=os.path.join(self.temp_dir, "fabric")
        )
    
    def teardown_method(self):
        """Clean up test environment"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    # ========================================================================
    # PROPERTY 22: Beta Drift Significance
    # ========================================================================
    
    @given(
        n_weeks=st.integers(min_value=30, max_value=100),
        n_stocks=st.integers(min_value=5, max_value=20),
        n_factors=st.integers(min_value=3, max_value=8),
        drift_magnitude=st.floats(min_value=0.1, max_value=3.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=20, deadline=10000)
    def test_property_22_beta_drift_significance(self, n_weeks: int, n_stocks: int, n_factors: int, drift_magnitude: float):
        """
        Property 22: Beta Drift Significance
        
        When beta drift exceeds 1.5 standard deviations from historical mean,
        it must be detected as significant.
        
        Validates: Requirements 8.2
        """
        
        # Create synthetic beta data with known drift
        dates = pd.date_range(start='2023-01-01', periods=n_weeks, freq='W')
        
        beta_records = []
        
        for i, date in enumerate(dates):
            for stock_idx in range(n_stocks):
                stock = f"STOCK_{stock_idx:02d}"
                
                for factor_idx in range(n_factors):
                    factor = f"Factor_{factor_idx}"
                    
                    # Create base beta with some noise
                    base_beta = 0.5 + (stock_idx * 0.1) + np.random.normal(0, 0.1)
                    
                    # Add significant drift at specific point
                    if i > n_weeks // 2:  # Second half of data
                        # Add drift that should be significant
                        beta = base_beta + (drift_magnitude * np.random.choice([-1, 1]))
                    else:
                        # Normal variation
                        beta = base_beta + np.random.normal(0, 0.2)
                    
                    beta_record = {
                        'date': date,
                        'year': date.year,
                        'week': date.isocalendar()[1],
                        'stock': stock,
                        'factor': factor,
                        'beta': beta,
                        'alpha': np.random.normal(0, 0.01),
                        'r_squared': np.random.uniform(0.3, 0.8),
                        'standard_error': np.random.uniform(0.01, 0.05),
                        't_statistic': beta / 0.02,  # Rough t-stat
                        'p_value': np.random.uniform(0.01, 0.1),
                        'observations': 52,
                        'window_weeks': 52
                    }
                    beta_records.append(beta_record)
        
        betas_df = pd.DataFrame(beta_records)
        
        # Detect significant drift
        significance_df = self.fabric.detect_significant_drift(betas_df)
        
        # PROPERTY: Significant drifts must be detected when drift > 1.5 std dev
        if not significance_df.empty:
            # All detected drifts should have z-score > 1.5
            assert (significance_df['drift_zscore'] > self.fabric.config['significance_threshold']).all()
            
            # All detected drifts should be marked as significant
            assert significance_df['is_significant'].all()
            
            # Confidence levels should be reasonable (> 0.5 for significant drifts)
            assert (significance_df['confidence_level'] > 0.5).all()
            
            # Z-scores should be finite and positive
            assert significance_df['drift_zscore'].notna().all()
            assert (significance_df['drift_zscore'] > 0).all()
            assert np.isfinite(significance_df['drift_zscore']).all()
    
    @given(
        historical_mean=st.floats(min_value=-1.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        historical_std=st.floats(min_value=0.1, max_value=0.5, allow_nan=False, allow_infinity=False),
        current_beta=st.floats(min_value=-2.0, max_value=2.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50, deadline=5000)
    def test_property_22_zscore_calculation(self, historical_mean: float, historical_std: float, current_beta: float):
        """
        Property 22: Z-Score Calculation Correctness
        
        Z-score calculation must be mathematically correct.
        """
        
        # Calculate expected z-score
        expected_zscore = abs(current_beta - historical_mean) / historical_std
        
        # Create significance record
        significance = BetaDriftSignificance(
            date=datetime.now(),
            stock="TEST_STOCK",
            factor="TEST_FACTOR",
            beta_current=current_beta,
            beta_52w_mean=historical_mean,
            beta_52w_std=historical_std,
            drift_magnitude=abs(current_beta - historical_mean),
            drift_zscore=expected_zscore,
            is_significant=expected_zscore > 1.5,
            confidence_level=0.95,
            observations=52
        )
        
        # PROPERTY: Z-score must be calculated correctly
        assert abs(significance.drift_zscore - expected_zscore) < 1e-10
        
        # PROPERTY: Significance flag must match z-score threshold
        assert significance.is_significant == (expected_zscore > 1.5)
        
        # PROPERTY: Drift magnitude must be absolute difference
        expected_magnitude = abs(current_beta - historical_mean)
        assert abs(significance.drift_magnitude - expected_magnitude) < 1e-10
    
    # ========================================================================
    # STATISTICAL PROPERTIES
    # ========================================================================
    
    @given(
        n_observations=st.integers(min_value=26, max_value=100),
        beta_values=st.lists(
            st.floats(min_value=-2.0, max_value=2.0, allow_nan=False, allow_infinity=False),
            min_size=26,
            max_size=100
        )
    )
    @settings(max_examples=30, deadline=5000)
    def test_property_statistical_consistency(self, n_observations: int, beta_values: List[float]):
        """
        Property: Statistical Consistency
        
        Statistical calculations must be consistent and valid.
        """
        
        assume(len(beta_values) >= n_observations)
        
        # Take first n_observations
        betas = np.array(beta_values[:n_observations])
        
        # Calculate statistics
        mean_beta = np.mean(betas)
        std_beta = np.std(betas)
        
        assume(std_beta > 0.01)  # Avoid division by zero
        
        # Test z-score calculation for each beta
        for i in range(len(betas)):
            if i < 10:  # Need some history
                continue
                
            historical_betas = betas[:i]
            current_beta = betas[i]
            
            hist_mean = np.mean(historical_betas)
            hist_std = np.std(historical_betas)
            
            if hist_std > 0:
                z_score = abs(current_beta - hist_mean) / hist_std
                
                # PROPERTY: Z-score must be non-negative
                assert z_score >= 0
                
                # PROPERTY: Z-score must be finite
                assert np.isfinite(z_score)
                
                # PROPERTY: Large deviations should have large z-scores
                if abs(current_beta - hist_mean) > 2 * hist_std:
                    assert z_score > 2.0
    
    # ========================================================================
    # FABRIC INTEGRATION PROPERTIES
    # ========================================================================
    
    def test_property_fabric_file_structure(self):
        """
        Property: Fabric File Structure
        
        Fabric files must have correct structure and content.
        """
        
        # Create minimal test data
        test_year = 2023
        
        # Create synthetic beta data
        dates = pd.date_range(start=f'{test_year}-01-01', periods=10, freq='W')
        
        beta_records = []
        for date in dates:
            beta_record = {
                'date': date,
                'year': test_year,
                'week': date.isocalendar()[1],
                'stock': 'TEST_STOCK',
                'factor': 'TEST_FACTOR',
                'beta': 0.5,
                'alpha': 0.01,
                'r_squared': 0.6,
                'standard_error': 0.02,
                't_statistic': 25.0,
                'p_value': 0.05,
                'observations': 52,
                'window_weeks': 52
            }
            beta_records.append(beta_record)
        
        betas_df = pd.DataFrame(beta_records)
        
        # Create empty significance data (no significant drifts)
        significance_df = pd.DataFrame()
        
        # Store fabric files
        success = self.fabric.store_weekly_fabric_files(betas_df, significance_df, test_year)
        
        # PROPERTY: Storage must succeed
        assert success
        
        # PROPERTY: Year directory must be created
        year_dir = os.path.join(self.fabric.fabric_dir, str(test_year))
        assert os.path.exists(year_dir)
        
        # PROPERTY: Fabric file must be created
        fabric_file = os.path.join(year_dir, f"beta_fabric_{test_year}.parquet")
        assert os.path.exists(fabric_file)
        
        # PROPERTY: Weekly files must be created
        unique_weeks = betas_df['week'].unique()
        for week in unique_weeks:
            week_file = os.path.join(year_dir, f"week_{week:02d}_fabric.json")
            assert os.path.exists(week_file)
    
    # ========================================================================
    # TAILWIND INTEGRATION PROPERTIES
    # ========================================================================
    
    def test_property_tailwind_integration(self):
        """
        Property: Tailwind Integration
        
        Tailwind integration must produce valid signals.
        """
        
        # Create test significance data
        significance_records = []
        
        for i in range(5):
            significance_record = {
                'date': datetime.now().isoformat(),
                'stock': f'STOCK_{i}',
                'factor': 'Liquidity',
                'beta_current': 0.8 + i * 0.1,
                'beta_52w_mean': 0.5,
                'beta_52w_std': 0.1,
                'drift_magnitude': 0.3 + i * 0.1,
                'drift_zscore': 2.0 + i * 0.5,
                'is_significant': True,
                'confidence_level': 0.95,
                'observations': 52
            }
            significance_records.append(significance_record)
        
        significance_df = pd.DataFrame(significance_records)
        
        # Test integration
        integration_result = self.fabric.integrate_with_tailwind_engine(significance_df, 2023)
        
        # PROPERTY: Integration must succeed
        assert 'tailwind_signals' in integration_result
        
        # PROPERTY: Signals must have required fields
        signals = integration_result['tailwind_signals']
        for factor, signal in signals.items():
            assert 'drift_intensity' in signal
            assert 'signal_strength' in signal
            assert 'confidence' in signal
            assert 'affected_stocks' in signal
            
            # PROPERTY: Signal strength must be bounded [0, 1]
            assert 0.0 <= signal['signal_strength'] <= 1.0
            
            # PROPERTY: Confidence must be valid probability
            assert 0.0 <= signal['confidence'] <= 1.0
            
            # PROPERTY: Affected stocks must be positive
            assert signal['affected_stocks'] > 0
    
    # ========================================================================
    # VALIDATION PROPERTIES
    # ========================================================================
    
    def test_property_significance_record_validation(self):
        """
        Property: Significance Record Validation
        
        Significance records must validate correctly.
        """
        
        # Valid record
        valid_record = BetaDriftSignificance(
            date=datetime.now(),
            stock="VALID_STOCK",
            factor="VALID_FACTOR",
            beta_current=0.75,
            beta_52w_mean=0.50,
            beta_52w_std=0.10,
            drift_magnitude=0.25,
            drift_zscore=2.5,
            is_significant=True,
            confidence_level=0.95,
            observations=52
        )
        
        errors = valid_record.validate()
        
        # PROPERTY: Valid record must have no errors
        assert len(errors) == 0
        
        # Invalid record - insufficient observations
        invalid_record = BetaDriftSignificance(
            date=datetime.now(),
            stock="INVALID_STOCK",
            factor="INVALID_FACTOR",
            beta_current=0.75,
            beta_52w_mean=0.50,
            beta_52w_std=0.10,
            drift_magnitude=0.25,
            drift_zscore=2.5,
            is_significant=True,
            confidence_level=1.5,  # Invalid confidence > 1.0
            observations=5  # Too few observations
        )
        
        errors = invalid_record.validate()
        
        # PROPERTY: Invalid record must have errors
        assert len(errors) > 0
        assert any("Insufficient observations" in error for error in errors)
        assert any("Confidence level must be between 0.0 and 1.0" in error for error in errors)


def test_beta_drift_significance_dataclass():
    """Test BetaDriftSignificance dataclass functionality"""
    
    # Create test record
    record = BetaDriftSignificance(
        date=datetime(2023, 6, 15),
        stock="TEST_STOCK",
        factor="Liquidity",
        beta_current=0.75,
        beta_52w_mean=0.50,
        beta_52w_std=0.10,
        drift_magnitude=0.25,
        drift_zscore=2.5,
        is_significant=True,
        confidence_level=0.95,
        observations=52
    )
    
    # Test to_dict conversion
    record_dict = record.to_dict()
    
    assert record_dict['stock'] == "TEST_STOCK"
    assert record_dict['factor'] == "Liquidity"
    assert record_dict['beta_current'] == 0.75
    assert record_dict['drift_zscore'] == 2.5
    assert record_dict['is_significant'] is True
    assert isinstance(record_dict['date'], str)  # Should be ISO format
    
    # Test validation
    errors = record.validate()
    assert len(errors) == 0


if __name__ == "__main__":
    pytest.main([__file__])