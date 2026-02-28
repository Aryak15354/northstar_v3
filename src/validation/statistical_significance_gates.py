"""
Statistical Significance Gates - Institutional Alpha Validation

This implements statistical significance testing that kills false alphas
before capital allocation. Prevents random luck from being mistaken for skill.

Key Tests:
- Bootstrap tests for return stability
- Permutation tests for signal randomness
- P-value validation for alpha significance
- T-statistic validation for mean returns

Requirements:
- IC p-value < 0.05
- Mean return > 2× std error
- T-stat > 2
- Bootstrap confidence intervals

Author: Northstar Team
Date: 2026-01-05
"""

import numpy as np
import pandas as pd
from scipy import stats
from scipy.stats import ttest_1samp, pearsonr
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
import logging
from datetime import datetime
import warnings

try:
    from ..operation.logging_config import setup_operation_logging
except ImportError:
    # Fallback for when running as standalone
    import logging
    def setup_operation_logging():
        logging.basicConfig(level=logging.INFO)
        return logging.getLogger(__name__)


@dataclass
class SignificanceTestResult:
    """Results from statistical significance testing."""
    test_name: str
    statistic: float
    p_value: float
    critical_value: float
    is_significant: bool
    confidence_interval: Tuple[float, float]
    effect_size: float
    sample_size: int
    power: float
    interpretation: str


@dataclass
class AlphaSignificanceReport:
    """Comprehensive alpha significance validation report."""
    alpha_name: str
    test_date: datetime
    
    # Core significance tests
    ic_test: SignificanceTestResult
    return_test: SignificanceTestResult
    bootstrap_test: SignificanceTestResult
    permutation_test: SignificanceTestResult
    
    # Summary metrics
    overall_significant: bool
    significance_score: float
    capital_allocation_approved: bool
    
    # Risk metrics
    false_discovery_rate: float
    multiple_testing_correction: str
    
    # Recommendations
    recommended_allocation: float
    confidence_level: float
    monitoring_frequency: str


class StatisticalSignificanceGates:
    """
    Institutional-grade statistical significance testing for alpha validation.
    
    This class implements rigorous statistical tests to prevent false alphas
    from receiving capital allocation. All tests must pass before any signal
    is allowed into the portfolio.
    """
    
    def __init__(self, 
                 alpha_threshold: float = 0.05,
                 min_t_stat: float = 2.0,
                 min_ic_threshold: float = 0.05,
                 bootstrap_iterations: int = 10000,
                 permutation_iterations: int = 5000):
        """
        Initialize statistical significance gates.
        
        Args:
            alpha_threshold: Maximum p-value for significance (default: 0.05)
            min_t_stat: Minimum t-statistic for mean returns (default: 2.0)
            min_ic_threshold: Minimum Information Coefficient threshold
            bootstrap_iterations: Number of bootstrap samples
            permutation_iterations: Number of permutation tests
        """
        self.alpha_threshold = alpha_threshold
        self.min_t_stat = min_t_stat
        self.min_ic_threshold = min_ic_threshold
        self.bootstrap_iterations = bootstrap_iterations
        self.permutation_iterations = permutation_iterations
        
        self.logger = setup_operation_logging()
        self.logger.info("Statistical Significance Gates initialized")
    
    def validate_alpha_significance(self, 
                                  returns: np.ndarray,
                                  signals: np.ndarray,
                                  alpha_name: str) -> AlphaSignificanceReport:
        """
        Run complete statistical significance validation for an alpha.
        
        Args:
            returns: Array of forward returns
            signals: Array of alpha signals
            alpha_name: Name of the alpha being tested
            
        Returns:
            AlphaSignificanceReport: Comprehensive significance test results
        """
        self.logger.info(f"🔒 Running significance validation for {alpha_name}")
        
        # Validate inputs
        if len(returns) != len(signals):
            raise ValueError("Returns and signals must have same length")
        
        if len(returns) < 30:
            raise ValueError("Insufficient data for significance testing (minimum 30 observations)")
        
        # Remove NaN values
        valid_mask = ~(np.isnan(returns) | np.isnan(signals))
        returns_clean = returns[valid_mask]
        signals_clean = signals[valid_mask]
        
        if len(returns_clean) < 30:
            raise ValueError("Insufficient valid data after cleaning")
        
        # Run all significance tests
        ic_test = self._test_information_coefficient(returns_clean, signals_clean)
        return_test = self._test_mean_return_significance(returns_clean, signals_clean)
        bootstrap_test = self._bootstrap_confidence_test(returns_clean, signals_clean)
        permutation_test = self._permutation_randomness_test(returns_clean, signals_clean)
        
        # Calculate overall significance
        overall_significant = all([
            ic_test.is_significant,
            return_test.is_significant,
            bootstrap_test.is_significant,
            permutation_test.is_significant
        ])
        
        # Calculate significance score (0-1)
        significance_score = np.mean([
            1.0 - ic_test.p_value,
            1.0 - return_test.p_value,
            1.0 - bootstrap_test.p_value,
            1.0 - permutation_test.p_value
        ])
        
        # Determine capital allocation approval
        capital_allocation_approved = (
            overall_significant and
            ic_test.p_value < self.alpha_threshold and
            return_test.statistic > self.min_t_stat and
            abs(ic_test.statistic) > self.min_ic_threshold
        )
        
        # Calculate false discovery rate
        fdr = self._calculate_false_discovery_rate([
            ic_test.p_value,
            return_test.p_value,
            bootstrap_test.p_value,
            permutation_test.p_value
        ])
        
        # Determine recommended allocation
        if capital_allocation_approved:
            recommended_allocation = min(0.1, significance_score * 0.15)  # Max 10%, scaled by significance
        else:
            recommended_allocation = 0.0
        
        # Create comprehensive report
        report = AlphaSignificanceReport(
            alpha_name=alpha_name,
            test_date=datetime.now(),
            ic_test=ic_test,
            return_test=return_test,
            bootstrap_test=bootstrap_test,
            permutation_test=permutation_test,
            overall_significant=overall_significant,
            significance_score=significance_score,
            capital_allocation_approved=capital_allocation_approved,
            false_discovery_rate=fdr,
            multiple_testing_correction="Benjamini-Hochberg",
            recommended_allocation=recommended_allocation,
            confidence_level=0.95,
            monitoring_frequency="daily" if capital_allocation_approved else "weekly"
        )
        
        self._log_significance_results(report)
        return report
    
    def _test_information_coefficient(self, returns: np.ndarray, signals: np.ndarray) -> SignificanceTestResult:
        """Test Information Coefficient significance."""
        # Calculate IC (correlation between signals and forward returns)
        ic, p_value = pearsonr(signals, returns)
        
        # Calculate confidence interval
        n = len(returns)
        se = np.sqrt((1 - ic**2) / (n - 2))
        t_critical = stats.t.ppf(1 - self.alpha_threshold/2, n - 2)
        ci_lower = ic - t_critical * se
        ci_upper = ic + t_critical * se
        
        # Calculate effect size (Cohen's conventions for correlation)
        if abs(ic) >= 0.5:
            effect_size = "large"
        elif abs(ic) >= 0.3:
            effect_size = "medium"
        elif abs(ic) >= 0.1:
            effect_size = "small"
        else:
            effect_size = "negligible"
        
        # Statistical power calculation
        power = self._calculate_power_correlation(ic, n, self.alpha_threshold)
        
        return SignificanceTestResult(
            test_name="Information Coefficient",
            statistic=ic,
            p_value=p_value,
            critical_value=self.min_ic_threshold,
            is_significant=(p_value < self.alpha_threshold and abs(ic) > self.min_ic_threshold),
            confidence_interval=(ci_lower, ci_upper),
            effect_size=abs(ic),
            sample_size=n,
            power=power,
            interpretation=f"IC = {ic:.4f}, {effect_size} effect size"
        )
    
    def _test_mean_return_significance(self, returns: np.ndarray, signals: np.ndarray) -> SignificanceTestResult:
        """Test mean return significance with t-test."""
        # Calculate signal-weighted returns
        signal_returns = returns * np.sign(signals)  # Align returns with signal direction
        
        # One-sample t-test against zero
        t_stat, p_value = ttest_1samp(signal_returns, 0)
        
        # Calculate confidence interval
        n = len(signal_returns)
        se = stats.sem(signal_returns)
        t_critical = stats.t.ppf(1 - self.alpha_threshold/2, n - 1)
        mean_return = np.mean(signal_returns)
        ci_lower = mean_return - t_critical * se
        ci_upper = mean_return + t_critical * se
        
        # Effect size (Cohen's d)
        effect_size = mean_return / np.std(signal_returns)
        
        # Statistical power
        power = self._calculate_power_ttest(effect_size, n, self.alpha_threshold)
        
        return SignificanceTestResult(
            test_name="Mean Return T-Test",
            statistic=t_stat,
            p_value=p_value,
            critical_value=self.min_t_stat,
            is_significant=(p_value < self.alpha_threshold and abs(t_stat) > self.min_t_stat),
            confidence_interval=(ci_lower, ci_upper),
            effect_size=abs(effect_size),
            sample_size=n,
            power=power,
            interpretation=f"Mean return = {mean_return:.4f}, t-stat = {t_stat:.2f}"
        )
    
    def _bootstrap_confidence_test(self, returns: np.ndarray, signals: np.ndarray) -> SignificanceTestResult:
        """Bootstrap test for return stability."""
        n = len(returns)
        
        # Original IC
        original_ic, _ = pearsonr(signals, returns)
        
        # Bootstrap sampling
        bootstrap_ics = []
        for _ in range(self.bootstrap_iterations):
            # Resample with replacement
            indices = np.random.choice(n, size=n, replace=True)
            boot_returns = returns[indices]
            boot_signals = signals[indices]
            
            # Calculate bootstrap IC
            boot_ic, _ = pearsonr(boot_signals, boot_returns)
            bootstrap_ics.append(boot_ic)
        
        bootstrap_ics = np.array(bootstrap_ics)
        
        # Calculate confidence interval
        ci_lower = np.percentile(bootstrap_ics, 2.5)
        ci_upper = np.percentile(bootstrap_ics, 97.5)
        
        # Test if zero is in confidence interval
        zero_in_ci = ci_lower <= 0 <= ci_upper
        p_value = np.mean(np.abs(bootstrap_ics) <= abs(original_ic))
        
        return SignificanceTestResult(
            test_name="Bootstrap Confidence Test",
            statistic=original_ic,
            p_value=p_value,
            critical_value=0.0,
            is_significant=not zero_in_ci,
            confidence_interval=(ci_lower, ci_upper),
            effect_size=np.std(bootstrap_ics),
            sample_size=self.bootstrap_iterations,
            power=1.0 - p_value,
            interpretation=f"Bootstrap CI: [{ci_lower:.4f}, {ci_upper:.4f}]"
        )
    
    def _permutation_randomness_test(self, returns: np.ndarray, signals: np.ndarray) -> SignificanceTestResult:
        """Permutation test to check if signals are random."""
        # Original IC
        original_ic, _ = pearsonr(signals, returns)
        
        # Permutation test
        permuted_ics = []
        for _ in range(self.permutation_iterations):
            # Randomly permute signals (break any real relationship)
            permuted_signals = np.random.permutation(signals)
            
            # Calculate IC with permuted signals
            perm_ic, _ = pearsonr(permuted_signals, returns)
            permuted_ics.append(perm_ic)
        
        permuted_ics = np.array(permuted_ics)
        
        # P-value: fraction of permuted ICs with absolute value >= original
        p_value = np.mean(np.abs(permuted_ics) >= abs(original_ic))
        
        # Confidence interval from permutation distribution
        ci_lower = np.percentile(permuted_ics, 2.5)
        ci_upper = np.percentile(permuted_ics, 97.5)
        
        return SignificanceTestResult(
            test_name="Permutation Randomness Test",
            statistic=original_ic,
            p_value=p_value,
            critical_value=0.0,
            is_significant=p_value < self.alpha_threshold,
            confidence_interval=(ci_lower, ci_upper),
            effect_size=np.std(permuted_ics),
            sample_size=self.permutation_iterations,
            power=1.0 - p_value,
            interpretation=f"Signal vs random: p = {p_value:.4f}"
        )
    
    def _calculate_false_discovery_rate(self, p_values: List[float]) -> float:
        """Calculate False Discovery Rate using Benjamini-Hochberg procedure."""
        p_values = np.array(p_values)
        n = len(p_values)
        
        # Sort p-values
        sorted_p = np.sort(p_values)
        
        # Benjamini-Hochberg critical values
        bh_critical = np.arange(1, n + 1) / n * self.alpha_threshold
        
        # Find largest k where p(k) <= (k/n) * alpha
        significant_indices = sorted_p <= bh_critical
        
        if np.any(significant_indices):
            # FDR is the expected proportion of false discoveries
            k = np.max(np.where(significant_indices)[0]) + 1
            fdr = k / n * self.alpha_threshold
        else:
            fdr = 0.0
        
        return min(fdr, 1.0)
    
    def _calculate_power_correlation(self, r: float, n: int, alpha: float) -> float:
        """Calculate statistical power for correlation test."""
        # Fisher's z-transformation
        z_r = 0.5 * np.log((1 + r) / (1 - r))
        se_z = 1 / np.sqrt(n - 3)
        
        # Critical value
        z_critical = stats.norm.ppf(1 - alpha/2)
        
        # Power calculation
        power = 1 - stats.norm.cdf(z_critical - abs(z_r) / se_z)
        return min(power, 1.0)
    
    def _calculate_power_ttest(self, effect_size: float, n: int, alpha: float) -> float:
        """Calculate statistical power for t-test."""
        # Non-centrality parameter
        ncp = effect_size * np.sqrt(n)
        
        # Critical value
        t_critical = stats.t.ppf(1 - alpha/2, n - 1)
        
        # Power using non-central t-distribution
        power = 1 - stats.nct.cdf(t_critical, n - 1, ncp)
        return min(power, 1.0)
    
    def _log_significance_results(self, report: AlphaSignificanceReport):
        """Log significance test results."""
        self.logger.info(f"📊 Significance Results for {report.alpha_name}")
        self.logger.info(f"   IC Test: {'✅' if report.ic_test.is_significant else '❌'} "
                        f"(IC={report.ic_test.statistic:.4f}, p={report.ic_test.p_value:.4f})")
        self.logger.info(f"   Return Test: {'✅' if report.return_test.is_significant else '❌'} "
                        f"(t={report.return_test.statistic:.2f}, p={report.return_test.p_value:.4f})")
        self.logger.info(f"   Bootstrap Test: {'✅' if report.bootstrap_test.is_significant else '❌'} "
                        f"(p={report.bootstrap_test.p_value:.4f})")
        self.logger.info(f"   Permutation Test: {'✅' if report.permutation_test.is_significant else '❌'} "
                        f"(p={report.permutation_test.p_value:.4f})")
        self.logger.info(f"   Overall Significant: {'✅' if report.overall_significant else '❌'}")
        self.logger.info(f"   Capital Allocation: {'✅ APPROVED' if report.capital_allocation_approved else '❌ REJECTED'}")
        self.logger.info(f"   Recommended Allocation: {report.recommended_allocation:.2%}")
    
    def batch_validate_alphas(self, 
                            alpha_data: Dict[str, Tuple[np.ndarray, np.ndarray]]) -> Dict[str, AlphaSignificanceReport]:
        """
        Validate multiple alphas with multiple testing correction.
        
        Args:
            alpha_data: Dict mapping alpha names to (returns, signals) tuples
            
        Returns:
            Dict mapping alpha names to significance reports
        """
        self.logger.info(f"🔒 Running batch significance validation for {len(alpha_data)} alphas")
        
        reports = {}
        all_p_values = []
        
        # Run individual tests
        for alpha_name, (returns, signals) in alpha_data.items():
            report = self.validate_alpha_significance(returns, signals, alpha_name)
            reports[alpha_name] = report
            
            # Collect p-values for multiple testing correction
            all_p_values.extend([
                report.ic_test.p_value,
                report.return_test.p_value,
                report.bootstrap_test.p_value,
                report.permutation_test.p_value
            ])
        
        # Apply multiple testing correction
        corrected_fdr = self._calculate_false_discovery_rate(all_p_values)
        
        # Update reports with corrected FDR
        for report in reports.values():
            report.false_discovery_rate = corrected_fdr
            
            # Re-evaluate capital allocation with corrected FDR
            if corrected_fdr > 0.1:  # Conservative FDR threshold
                report.capital_allocation_approved = False
                report.recommended_allocation = 0.0
        
        self.logger.info(f"📊 Batch validation complete. FDR: {corrected_fdr:.4f}")
        return reports


def create_significance_gates() -> StatisticalSignificanceGates:
    """Create institutional-grade significance gates."""
    return StatisticalSignificanceGates(
        alpha_threshold=0.05,
        min_t_stat=2.0,
        min_ic_threshold=0.05,
        bootstrap_iterations=10000,
        permutation_iterations=5000
    )


if __name__ == "__main__":
    # Demo usage
    gates = create_significance_gates()
    
    # Generate sample data
    np.random.seed(42)
    n = 252  # One year of daily data
    
    # Create a signal with some predictive power
    true_signal = np.random.randn(n)
    noise = np.random.randn(n) * 2
    returns = 0.1 * true_signal + noise  # Signal explains some returns
    
    # Test significance
    report = gates.validate_alpha_significance(returns, true_signal, "demo_alpha")
    
    print(f"Alpha: {report.alpha_name}")
    print(f"Significant: {report.overall_significant}")
    print(f"Capital Approved: {report.capital_allocation_approved}")
    print(f"Recommended Allocation: {report.recommended_allocation:.2%}")