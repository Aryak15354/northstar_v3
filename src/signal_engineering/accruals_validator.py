"""
Accruals Calculation Validator for Indian Market

This module validates that accruals calculations follow the correct formula
for the Indian market, where high accruals predict HIGHER returns (opposite of US).

Formula: accruals_ratio = (Net_Income - Operating_Cash_Flow) / Total_Assets

Key Insight (Indian Market):
- High accruals → Higher future returns
- This is OPPOSITE to US market behavior (Sloan 1996)
- Do NOT invert the sign of this calculation

References:
- Northstar V3 Signal Engineering Plan, Requirement 19
- Task 1.2: Accruals calculation validation
"""

from datetime import datetime
import numpy as np
import pandas as pd
from typing import Dict, Optional

from src.valuation.core.normalized_financials import FinancialNormalizer


class AccrualsValidator:
    """
    Validates accruals calculations for Indian market behavior.
    
    The Indian market exhibits opposite accruals behavior compared to US markets:
    - US: High accruals → Lower returns (Sloan 1996)
    - India: High accruals → Higher returns
    
    This validator ensures the formula is correctly applied without sign inversion.
    """

    def __init__(self, config: Optional[dict] = None):
        self._config = dict(config or {})
        self._normalizer = FinancialNormalizer(self._config)
    
    @staticmethod
    def calculate_accruals_ratio(
        net_income: float,
        operating_cash_flow: float,
        total_assets: float,
        eps: float = 1e-12
    ) -> float:
        """
        Calculate accruals ratio using the standard formula.
        
        Formula: (Net_Income - Operating_Cash_Flow) / Total_Assets
        
        Args:
            net_income: Net income for the period
            operating_cash_flow: Operating cash flow for the period
            total_assets: Total assets at period end
            eps: Small epsilon to avoid division by zero
            
        Returns:
            Accruals ratio (can be positive or negative)
            
        Note:
            For Indian market: High positive values predict HIGHER returns
        """
        return (net_income - operating_cash_flow) / (total_assets + eps)

    def validate(self, ticker: str, as_of_date: datetime) -> Dict[str, any]:
        """
        Validate accruals using real Screener-backed cashflow data.
        """
        current = self._normalizer.load_latest(ticker, as_of_date, "annual")
        history = self._normalizer.load_history(ticker, as_of_date, n_periods=5, frequency="annual")

        has_real_cashflow = (
            bool(current)
            and "cash_from_operations" in current
            and current["cash_from_operations"] is not None
            and not pd.isna(current["cash_from_operations"])
        )
        if not current or len(history) < 2:
            return {
                "status": "INSUFFICIENT_DATA",
                "reason": "historical financials unavailable for accruals validation",
                "accruals_ratio": np.nan,
                "is_valid": False,
                "has_real_cashflow": has_real_cashflow,
                "data_source_paths": [str(p) for p in self._normalizer.get_source_paths(ticker, "annual")],
            }

        if not has_real_cashflow:
            return {
                "status": "INSUFFICIENT_DATA",
                "reason": "cash_from_operations not available — cannot validate accruals",
                "accruals_ratio": np.nan,
                "is_valid": False,
                "has_real_cashflow": False,
                "data_source_paths": [str(p) for p in self._normalizer.get_source_paths(ticker, "annual")],
            }

        prior = history[-2]
        net_income = pd.to_numeric(current.get("net_profit"), errors="coerce")
        operating_cash_flow = pd.to_numeric(current.get("cash_from_operations"), errors="coerce")
        assets_current = pd.to_numeric(current.get("total_assets"), errors="coerce")
        assets_prior = pd.to_numeric(prior.get("total_assets"), errors="coerce")
        assets_values = [v for v in [assets_current, assets_prior] if pd.notna(v)]
        avg_assets = float(np.mean(assets_values)) if assets_values else np.nan

        if not np.isfinite(avg_assets) or avg_assets <= 0:
            return {
                "status": "INSUFFICIENT_DATA",
                "reason": "total_assets unavailable — cannot validate accruals",
                "accruals_ratio": np.nan,
                "is_valid": False,
                "has_real_cashflow": has_real_cashflow,
                "data_source_paths": [str(p) for p in self._normalizer.get_source_paths(ticker, "annual")],
            }

        accruals_ratio = self.calculate_accruals_ratio(
            float(net_income),
            float(operating_cash_flow),
            float(avg_assets),
        )
        return {
            "status": "VALID",
            "reason": "validated using Screener cashflow data",
            "accruals_ratio": float(accruals_ratio),
            "is_valid": True,
            "has_real_cashflow": True,
            "data_source_paths": [str(p) for p in self._normalizer.get_source_paths(ticker, "annual")],
        }
    
    @staticmethod
    def validate_formula_correctness(
        net_income: float,
        operating_cash_flow: float,
        total_assets: float,
        calculated_accruals: float,
        tolerance: float = 1e-6
    ) -> Dict[str, any]:
        """
        Validate that a calculated accruals ratio matches the expected formula.
        
        Args:
            net_income: Net income used in calculation
            operating_cash_flow: Operating cash flow used in calculation
            total_assets: Total assets used in calculation
            calculated_accruals: The accruals ratio that was calculated
            tolerance: Acceptable difference for floating point comparison
            
        Returns:
            Dictionary with validation results:
            - is_valid: bool
            - expected: float
            - actual: float
            - difference: float
            - message: str
        """
        expected = AccrualsValidator.calculate_accruals_ratio(
            net_income, operating_cash_flow, total_assets
        )
        
        difference = abs(calculated_accruals - expected)
        is_valid = difference < tolerance
        
        return {
            'is_valid': is_valid,
            'expected': expected,
            'actual': calculated_accruals,
            'difference': difference,
            'message': 'Valid' if is_valid else f'Mismatch: expected {expected:.6f}, got {calculated_accruals:.6f}'
        }
    
    @staticmethod
    def validate_indian_market_behavior(
        accruals_series: pd.Series,
        forward_returns_series: pd.Series,
        min_correlation: float = 0.0
    ) -> Dict[str, any]:
        """
        Validate that accruals exhibit expected Indian market behavior.
        
        In Indian market, high accruals should correlate with HIGHER returns.
        This is opposite to US market behavior.
        
        Args:
            accruals_series: Series of accruals ratios
            forward_returns_series: Series of forward returns (aligned)
            min_correlation: Minimum expected correlation (should be >= 0 for India)
            
        Returns:
            Dictionary with validation results:
            - correlation: float
            - is_positive: bool
            - meets_threshold: bool
            - message: str
        """
        # Remove NaN values
        valid_mask = accruals_series.notna() & forward_returns_series.notna()
        accruals_clean = accruals_series[valid_mask]
        returns_clean = forward_returns_series[valid_mask]
        
        if len(accruals_clean) < 10:
            return {
                'correlation': np.nan,
                'is_positive': False,
                'meets_threshold': False,
                'message': 'Insufficient data for correlation analysis'
            }
        
        correlation = accruals_clean.corr(returns_clean)
        is_positive = correlation > 0
        meets_threshold = correlation >= min_correlation
        
        message = f"Correlation: {correlation:.4f}"
        if is_positive:
            message += " (Positive - consistent with Indian market)"
        else:
            message += " (Negative - WARNING: inconsistent with Indian market)"
        
        return {
            'correlation': correlation,
            'is_positive': is_positive,
            'meets_threshold': meets_threshold,
            'message': message
        }
    
    @staticmethod
    def create_test_cases() -> list:
        """
        Create test cases for accruals calculation validation.
        
        Returns:
            List of test case dictionaries with inputs and expected outputs
        """
        return [
            {
                'name': 'High accruals (positive)',
                'net_income': 1000,
                'operating_cash_flow': 500,
                'total_assets': 10000,
                'expected_accruals': 0.05,  # (1000 - 500) / 10000
                'interpretation': 'High accruals - predicts HIGHER returns in Indian market'
            },
            {
                'name': 'Low accruals (negative)',
                'net_income': 500,
                'operating_cash_flow': 1000,
                'total_assets': 10000,
                'expected_accruals': -0.05,  # (500 - 1000) / 10000
                'interpretation': 'Low accruals - predicts LOWER returns in Indian market'
            },
            {
                'name': 'Zero accruals',
                'net_income': 1000,
                'operating_cash_flow': 1000,
                'total_assets': 10000,
                'expected_accruals': 0.0,  # (1000 - 1000) / 10000
                'interpretation': 'Zero accruals - neutral signal'
            },
            {
                'name': 'Very high accruals',
                'net_income': 2000,
                'operating_cash_flow': 0,
                'total_assets': 10000,
                'expected_accruals': 0.2,  # (2000 - 0) / 10000
                'interpretation': 'Very high accruals - strong positive signal in Indian market'
            }
        ]


def run_validation_tests() -> bool:
    """
    Run all validation tests for accruals calculation.
    
    Returns:
        True if all tests pass, False otherwise
    """
    validator = AccrualsValidator()
    test_cases = validator.create_test_cases()
    
    all_passed = True
    print("Running Accruals Calculation Validation Tests")
    print("=" * 60)
    
    for test_case in test_cases:
        result = validator.calculate_accruals_ratio(
            test_case['net_income'],
            test_case['operating_cash_flow'],
            test_case['total_assets']
        )
        
        expected = test_case['expected_accruals']
        passed = abs(result - expected) < 1e-6
        all_passed = all_passed and passed
        
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"\n{status}: {test_case['name']}")
        print(f"  Expected: {expected:.6f}")
        print(f"  Got: {result:.6f}")
        print(f"  Interpretation: {test_case['interpretation']}")
    
    print("\n" + "=" * 60)
    print(f"Overall: {'All tests passed' if all_passed else 'Some tests failed'}")
    
    return all_passed


if __name__ == "__main__":
    success = run_validation_tests()
    exit(0 if success else 1)
