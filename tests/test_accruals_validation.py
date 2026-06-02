"""
Unit tests for accruals calculation validation.

Tests ensure that:
1. Accruals formula is correctly implemented
2. Sign is NOT inverted (Indian market behavior)
3. Edge cases are handled properly
"""

import pytest
import numpy as np
import pandas as pd
from src.signal_engineering.accruals_validator import AccrualsValidator


class TestAccrualsCalculation:
    """Test suite for accruals ratio calculation."""
    
    def test_positive_accruals(self):
        """Test case where net income exceeds operating cash flow."""
        result = AccrualsValidator.calculate_accruals_ratio(
            net_income=1000,
            operating_cash_flow=500,
            total_assets=10000
        )
        expected = 0.05  # (1000 - 500) / 10000
        assert abs(result - expected) < 1e-6
    
    def test_negative_accruals(self):
        """Test case where operating cash flow exceeds net income."""
        result = AccrualsValidator.calculate_accruals_ratio(
            net_income=500,
            operating_cash_flow=1000,
            total_assets=10000
        )
        expected = -0.05  # (500 - 1000) / 10000
        assert abs(result - expected) < 1e-6
    
    def test_zero_accruals(self):
        """Test case where net income equals operating cash flow."""
        result = AccrualsValidator.calculate_accruals_ratio(
            net_income=1000,
            operating_cash_flow=1000,
            total_assets=10000
        )
        expected = 0.0
        assert abs(result - expected) < 1e-6
    
    def test_very_high_accruals(self):
        """Test case with very high accruals (no cash flow)."""
        result = AccrualsValidator.calculate_accruals_ratio(
            net_income=2000,
            operating_cash_flow=0,
            total_assets=10000
        )
        expected = 0.2  # (2000 - 0) / 10000
        assert abs(result - expected) < 1e-6
    
    def test_negative_cash_flow(self):
        """Test case with negative operating cash flow."""
        result = AccrualsValidator.calculate_accruals_ratio(
            net_income=1000,
            operating_cash_flow=-500,
            total_assets=10000
        )
        expected = 0.15  # (1000 - (-500)) / 10000
        assert abs(result - expected) < 1e-6
    
    def test_small_assets_with_epsilon(self):
        """Test that epsilon prevents division by zero."""
        result = AccrualsValidator.calculate_accruals_ratio(
            net_income=100,
            operating_cash_flow=50,
            total_assets=0,  # Would cause division by zero without epsilon
            eps=1e-12
        )
        # Should not raise exception and should return finite value
        assert np.isfinite(result)


class TestFormulaValidation:
    """Test suite for formula correctness validation."""
    
    def test_valid_calculation(self):
        """Test validation of correct accruals calculation."""
        net_income = 1000
        ocf = 500
        assets = 10000
        calculated = 0.05
        
        result = AccrualsValidator.validate_formula_correctness(
            net_income, ocf, assets, calculated
        )
        
        assert result['is_valid'] is True
        assert abs(result['expected'] - 0.05) < 1e-6
        assert abs(result['actual'] - 0.05) < 1e-6
        assert result['difference'] < 1e-6
    
    def test_invalid_calculation_wrong_sign(self):
        """Test detection of sign inversion error."""
        net_income = 1000
        ocf = 500
        assets = 10000
        calculated = -0.05  # Wrong sign!
        
        result = AccrualsValidator.validate_formula_correctness(
            net_income, ocf, assets, calculated
        )
        
        assert result['is_valid'] is False
        assert abs(result['expected'] - 0.05) < 1e-6
        assert abs(result['actual'] - (-0.05)) < 1e-6
        assert result['difference'] > 0.09  # Should be ~0.1
    
    def test_invalid_calculation_wrong_denominator(self):
        """Test detection of wrong denominator."""
        net_income = 1000
        ocf = 500
        assets = 10000
        calculated = 0.5  # Used wrong denominator (1000 instead of 10000)
        
        result = AccrualsValidator.validate_formula_correctness(
            net_income, ocf, assets, calculated
        )
        
        assert result['is_valid'] is False
        assert abs(result['difference'] - 0.45) < 1e-6


class TestIndianMarketBehavior:
    """Test suite for Indian market specific behavior validation."""
    
    def test_positive_correlation_expected(self):
        """Test that high accruals correlate with higher returns in Indian market."""
        # Create synthetic data with positive correlation
        np.random.seed(42)
        accruals = pd.Series(np.random.randn(100))
        # Returns should be positively correlated with accruals
        returns = accruals * 0.5 + np.random.randn(100) * 0.3
        
        result = AccrualsValidator.validate_indian_market_behavior(
            accruals, returns, min_correlation=0.0
        )
        
        assert bool(result['is_positive']) is True
        assert result['correlation'] > 0
        assert bool(result['meets_threshold']) is True
    
    def test_negative_correlation_warning(self):
        """Test warning when correlation is negative (inconsistent with Indian market)."""
        # Create synthetic data with negative correlation
        np.random.seed(42)
        accruals = pd.Series(np.random.randn(100))
        # Returns negatively correlated (US-style behavior)
        returns = -accruals * 0.5 + np.random.randn(100) * 0.3
        
        result = AccrualsValidator.validate_indian_market_behavior(
            accruals, returns, min_correlation=0.0
        )
        
        assert bool(result['is_positive']) is False
        assert result['correlation'] < 0
        assert 'WARNING' in result['message']
    
    def test_insufficient_data(self):
        """Test handling of insufficient data."""
        accruals = pd.Series([1, 2, 3])
        returns = pd.Series([0.1, 0.2, 0.3])
        
        result = AccrualsValidator.validate_indian_market_behavior(
            accruals, returns
        )
        
        assert np.isnan(result['correlation'])
        assert result['is_positive'] is False
        assert 'Insufficient data' in result['message']


class TestEdgeCases:
    """Test suite for edge cases and boundary conditions."""
    
    def test_nan_handling(self):
        """Test that NaN values are handled gracefully."""
        result = AccrualsValidator.calculate_accruals_ratio(
            net_income=np.nan,
            operating_cash_flow=500,
            total_assets=10000
        )
        assert np.isnan(result)
    
    def test_infinity_handling(self):
        """Test that infinity values are handled."""
        result = AccrualsValidator.calculate_accruals_ratio(
            net_income=np.inf,
            operating_cash_flow=500,
            total_assets=10000
        )
        assert np.isinf(result)
    
    def test_zero_total_assets(self):
        """Test behavior with zero total assets (uses epsilon)."""
        result = AccrualsValidator.calculate_accruals_ratio(
            net_income=100,
            operating_cash_flow=50,
            total_assets=0
        )
        # Should not crash and should return very large value
        assert np.isfinite(result)
        assert abs(result) > 1e10  # Very large due to small denominator


class TestRealWorldScenarios:
    """Test suite with realistic Indian market scenarios."""
    
    def test_high_growth_company(self):
        """Test high-growth company with high accruals."""
        # High growth companies often have high accruals
        result = AccrualsValidator.calculate_accruals_ratio(
            net_income=5000,  # High earnings
            operating_cash_flow=2000,  # Lower cash flow (investing in growth)
            total_assets=50000
        )
        expected = 0.06  # (5000 - 2000) / 50000
        assert abs(result - expected) < 1e-6
        assert result > 0  # Positive accruals
    
    def test_mature_company(self):
        """Test mature company with low accruals."""
        # Mature companies often have cash flow > earnings
        result = AccrualsValidator.calculate_accruals_ratio(
            net_income=3000,
            operating_cash_flow=4000,  # Higher cash flow
            total_assets=50000
        )
        expected = -0.02  # (3000 - 4000) / 50000
        assert abs(result - expected) < 1e-6
        assert result < 0  # Negative accruals
    
    def test_distressed_company(self):
        """Test distressed company with negative earnings."""
        result = AccrualsValidator.calculate_accruals_ratio(
            net_income=-1000,  # Losses
            operating_cash_flow=-500,  # Negative cash flow
            total_assets=50000
        )
        expected = -0.01  # (-1000 - (-500)) / 50000
        assert abs(result - expected) < 1e-6


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
