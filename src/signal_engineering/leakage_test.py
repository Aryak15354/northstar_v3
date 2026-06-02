"""
Leakage Test Framework

Automated detection of point-in-time violations through IC ratio analysis.
Compares IC with correct PIT alignment vs IC with forward-shifted data.

If IC improves significantly when using future data (IC_ratio >= 1.20),
the feature is leaking future information and must be rejected.
"""

from dataclasses import dataclass
from typing import Optional, Dict, List
import pandas as pd
import numpy as np
from scipy.stats import spearmanr
from datetime import datetime


@dataclass
class LeakageTestResult:
    """Result of leakage test for a feature
    
    Attributes:
        feature_name: Name of feature tested
        baseline_ic: IC with correct PIT alignment
        shifted_ic: IC with data shifted forward
        ic_ratio: shifted_ic / baseline_ic
        is_leaking: True if IC_ratio >= threshold
        test_period_start: Start of test period
        test_period_end: End of test period
        shift_days: Number of days data was shifted
        test_date: When test was executed
    """
    feature_name: str
    baseline_ic: float
    shifted_ic: float
    ic_ratio: float
    is_leaking: bool
    test_period_start: pd.Timestamp
    test_period_end: pd.Timestamp
    shift_days: int
    test_date: datetime
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        return {
            'feature_name': self.feature_name,
            'baseline_ic': self.baseline_ic,
            'shifted_ic': self.shifted_ic,
            'ic_ratio': self.ic_ratio,
            'is_leaking': self.is_leaking,
            'test_period_start': self.test_period_start.isoformat(),
            'test_period_end': self.test_period_end.isoformat(),
            'shift_days': self.shift_days,
            'test_date': self.test_date.isoformat()
        }
    
    def __str__(self) -> str:
        """Human-readable summary"""
        status = "LEAKING" if self.is_leaking else "CLEAN"
        return (
            f"Leakage Test: {self.feature_name}\n"
            f"  Status: {status}\n"
            f"  Baseline IC: {self.baseline_ic:.4f}\n"
            f"  Shifted IC: {self.shifted_ic:.4f}\n"
            f"  IC Ratio: {self.ic_ratio:.4f}\n"
            f"  Test Period: {self.test_period_start.date()} to {self.test_period_end.date()}"
        )


class LeakageTest:
    """Automated leakage detection through IC ratio analysis
    
    Compares IC with correct PIT alignment vs IC with forward-shifted data.
    A significant IC improvement with shifted data indicates leakage.
    """
    
    def __init__(
        self, 
        shift_days: int = 5,
        ic_ratio_threshold: float = 1.20
    ):
        """Initialize leakage test
        
        Args:
            shift_days: Number of trading days to shift data forward
            ic_ratio_threshold: Threshold for flagging leakage (default 1.20 = 20% improvement)
        """
        self.shift_days = shift_days
        self.ic_ratio_threshold = ic_ratio_threshold
    
    def calculate_ic(
        self,
        features: pd.DataFrame,
        returns: pd.DataFrame,
        feature_col: str,
        return_col: str = 'forward_return'
    ) -> float:
        """Calculate Information Coefficient (Spearman rank correlation)
        
        Args:
            features: DataFrame with feature values (date, stock, feature_col)
            returns: DataFrame with forward returns (date, stock, return_col)
            feature_col: Name of feature column
            return_col: Name of return column
            
        Returns:
            Mean IC across all dates
        """
        # Merge features and returns
        merged = pd.merge(
            features[['date', 'stock', feature_col]],
            returns[['date', 'stock', return_col]],
            on=['date', 'stock'],
            how='inner'
        )
        
        # Calculate IC for each date
        ic_by_date = []
        for date, group in merged.groupby('date'):
            # Remove NaN values
            valid = group[[feature_col, return_col]].dropna()
            
            if len(valid) < 10:  # Need minimum observations
                continue
            
            # Calculate Spearman correlation
            ic, _ = spearmanr(valid[feature_col], valid[return_col])
            
            if not np.isnan(ic):
                ic_by_date.append(ic)
        
        # Return mean IC
        return np.mean(ic_by_date) if ic_by_date else 0.0
    
    def shift_feature_forward(
        self,
        features: pd.DataFrame,
        feature_col: str,
        shift_days: int
    ) -> pd.DataFrame:
        """Shift feature data forward by specified days
        
        Simulates using future information by shifting feature values forward.
        
        Args:
            features: DataFrame with feature values
            feature_col: Name of feature column to shift
            shift_days: Number of days to shift forward
            
        Returns:
            DataFrame with shifted feature values
        """
        shifted = features.copy()
        
        # Group by stock and shift feature values forward
        shifted[feature_col] = shifted.groupby('stock')[feature_col].shift(-shift_days)
        
        return shifted
    
    def test_feature(
        self,
        feature_name: str,
        features: pd.DataFrame,
        returns: pd.DataFrame,
        feature_col: Optional[str] = None,
        return_col: str = 'forward_return',
        test_period_start: Optional[pd.Timestamp] = None,
        test_period_end: Optional[pd.Timestamp] = None
    ) -> LeakageTestResult:
        """Test a feature for PIT leakage
        
        Args:
            feature_name: Name of feature being tested
            features: DataFrame with feature values (date, stock, feature_col)
            returns: DataFrame with forward returns (date, stock, return_col)
            feature_col: Name of feature column (defaults to feature_name)
            return_col: Name of return column
            test_period_start: Start of test period (optional)
            test_period_end: End of test period (optional)
            
        Returns:
            LeakageTestResult with test results
        """
        feature_col = feature_col or feature_name
        
        # Filter to test period if specified
        if test_period_start is not None:
            features = features[features['date'] >= test_period_start]
            returns = returns[returns['date'] >= test_period_start]
        
        if test_period_end is not None:
            features = features[features['date'] <= test_period_end]
            returns = returns[returns['date'] <= test_period_end]
        
        # Determine actual test period
        actual_start = features['date'].min()
        actual_end = features['date'].max()
        
        # Calculate baseline IC with correct PIT alignment
        baseline_ic = self.calculate_ic(
            features, returns, feature_col, return_col
        )
        
        # Shift feature data forward
        shifted_features = self.shift_feature_forward(
            features, feature_col, self.shift_days
        )
        
        # Calculate shifted IC
        shifted_ic = self.calculate_ic(
            shifted_features, returns, feature_col, return_col
        )
        
        # Calculate IC ratio
        ic_ratio = shifted_ic / (abs(baseline_ic) + 1e-8)
        
        # Flag if leaking
        is_leaking = ic_ratio >= self.ic_ratio_threshold
        
        return LeakageTestResult(
            feature_name=feature_name,
            baseline_ic=baseline_ic,
            shifted_ic=shifted_ic,
            ic_ratio=ic_ratio,
            is_leaking=is_leaking,
            test_period_start=actual_start,
            test_period_end=actual_end,
            shift_days=self.shift_days,
            test_date=datetime.now()
        )
    
    def test_multiple_features(
        self,
        feature_names: List[str],
        features: pd.DataFrame,
        returns: pd.DataFrame,
        return_col: str = 'forward_return'
    ) -> Dict[str, LeakageTestResult]:
        """Test multiple features for leakage
        
        Args:
            feature_names: List of feature names to test
            features: DataFrame with all feature values
            returns: DataFrame with forward returns
            return_col: Name of return column
            
        Returns:
            Dictionary mapping feature names to LeakageTestResult
        """
        results = {}
        
        for feature_name in feature_names:
            if feature_name not in features.columns:
                print(f"Warning: Feature '{feature_name}' not found in data")
                continue
            
            result = self.test_feature(
                feature_name=feature_name,
                features=features,
                returns=returns,
                feature_col=feature_name,
                return_col=return_col
            )
            
            results[feature_name] = result
        
        return results
    
    def generate_report(
        self,
        results: Dict[str, LeakageTestResult]
    ) -> Dict:
        """Generate summary report of leakage test results
        
        Args:
            results: Dictionary of LeakageTestResult by feature name
            
        Returns:
            Summary report dictionary
        """
        total = len(results)
        leaking = sum(1 for r in results.values() if r.is_leaking)
        clean = total - leaking
        
        leaking_features = [
            name for name, result in results.items() 
            if result.is_leaking
        ]
        
        return {
            'total_features': total,
            'clean_features': clean,
            'leaking_features': leaking,
            'pass_rate': clean / total if total > 0 else 0.0,
            'leaking_feature_names': leaking_features,
            'test_date': datetime.now().isoformat(),
            'shift_days': self.shift_days,
            'ic_ratio_threshold': self.ic_ratio_threshold
        }
    
    def print_report(
        self,
        results: Dict[str, LeakageTestResult]
    ) -> None:
        """Print human-readable report
        
        Args:
            results: Dictionary of LeakageTestResult by feature name
        """
        report = self.generate_report(results)
        
        print("\n" + "="*60)
        print("LEAKAGE TEST REPORT")
        print("="*60)
        print(f"Total Features Tested: {report['total_features']}")
        print(f"Clean Features: {report['clean_features']}")
        print(f"Leaking Features: {report['leaking_features']}")
        print(f"Pass Rate: {report['pass_rate']:.1%}")
        print(f"IC Ratio Threshold: {report['ic_ratio_threshold']}")
        print(f"Shift Days: {report['shift_days']}")
        
        if report['leaking_feature_names']:
            print("\nLEAKING FEATURES (REJECTED):")
            for name in report['leaking_feature_names']:
                result = results[name]
                print(f"  - {name}: IC ratio = {result.ic_ratio:.4f}")
        
        print("\nDETAILED RESULTS:")
        for name, result in results.items():
            status = "❌ LEAKING" if result.is_leaking else "✅ CLEAN"
            print(f"\n{status} {name}")
            print(f"  Baseline IC: {result.baseline_ic:.4f}")
            print(f"  Shifted IC: {result.shifted_ic:.4f}")
            print(f"  IC Ratio: {result.ic_ratio:.4f}")
        
        print("\n" + "="*60)


def run_leakage_test_suite(
    features: pd.DataFrame,
    returns: pd.DataFrame,
    feature_names: Optional[List[str]] = None,
    shift_days: int = 5,
    ic_ratio_threshold: float = 1.20
) -> Dict[str, LeakageTestResult]:
    """Convenience function to run complete leakage test suite
    
    Args:
        features: DataFrame with feature values (date, stock, feature columns)
        returns: DataFrame with forward returns (date, stock, forward_return)
        feature_names: List of feature names to test (defaults to all numeric columns)
        shift_days: Number of days to shift data forward
        ic_ratio_threshold: Threshold for flagging leakage
        
    Returns:
        Dictionary of LeakageTestResult by feature name
    """
    # Default to all numeric columns except date and stock
    if feature_names is None:
        feature_names = [
            col for col in features.columns 
            if col not in ['date', 'stock'] and pd.api.types.is_numeric_dtype(features[col])
        ]
    
    # Create leakage test instance
    tester = LeakageTest(shift_days=shift_days, ic_ratio_threshold=ic_ratio_threshold)
    
    # Run tests
    results = tester.test_multiple_features(
        feature_names=feature_names,
        features=features,
        returns=returns
    )
    
    # Print report
    tester.print_report(results)
    
    return results
