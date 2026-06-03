#!/usr/bin/env python3
"""
📐 LAGGED REGRESSION ENGINE - MIE COMPONENT 3
Multi-lag regression estimation with statistical rigor

Mathematical Specification:
For each company i:
    R_{i,t} = α_i + Σ β_{i,k,l} M_{k,t-l} + γ_i R_{market,t} + ε_{i,t}

Where:
- R_{i,t} = company return at time t
- M_{k,t-l} = macro variable k at lag l
- R_{market,t} = market return (control)
- β_{i,k,l} = macro sensitivity coefficient

Matrix Form:
    R_i = X θ_i + ε_i
    θ_i = (X'X)^{-1} X'R_i  (OLS estimator)

Statistical Controls:
- Newey-West HAC standard errors
- Multiple testing correction (FDR)
- R² decomposition
- Optimal lag selection
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from scipy import stats
import warnings
warnings.filterwarnings('ignore')


class LaggedRegressionEngine:
    """
    Multi-lag regression engine for macro-equity transmission
    
    Estimates:
    - Macro sensitivity coefficients (β)
    - Statistical significance (t-stats, p-values)
    - Optimal lags
    - R² contribution
    - Confidence intervals
    """
    
    def __init__(
        self,
        fdr_alpha: float = 0.05,  # False discovery rate
        min_observations: int = 52,  # Minimum 1 year of weekly data
        use_hac_se: bool = True  # Heteroskedasticity and autocorrelation consistent SE
    ):
        self.fdr_alpha = fdr_alpha
        self.min_observations = min_observations
        self.use_hac_se = use_hac_se
        
        # Results storage
        self.regression_results = {}
        self.optimal_lags = {}
        self.significant_relationships = {}
        
        print(f"📐 Lagged Regression Engine initialized")
        print(f"   FDR alpha: {self.fdr_alpha}")
        print(f"   Min observations: {self.min_observations}")
        print(f"   HAC standard errors: {self.use_hac_se}")
    
    def prepare_design_matrix(
        self,
        macro_lagged: pd.DataFrame,
        market_factor: Optional[pd.Series] = None,
        add_intercept: bool = True
    ) -> Tuple[np.ndarray, List[str]]:
        """
        Construct design matrix X for regression
        
        Args:
            macro_lagged: DataFrame with lagged macro variables
            market_factor: Market return for control (optional)
            add_intercept: Add intercept column
        
        Returns:
            Tuple of (X matrix, column names)
        """
        # Start with macro variables
        X_df = macro_lagged.copy()
        
        # Add market factor if provided
        if market_factor is not None:
            X_df['market_return'] = market_factor
        
        # Add intercept
        if add_intercept:
            X_df.insert(0, 'intercept', 1.0)
        
        # Convert to numpy array
        X = X_df.values
        column_names = X_df.columns.tolist()
        
        return X, column_names
    
    def estimate_ols(
        self,
        y: np.ndarray,
        X: np.ndarray,
        column_names: List[str]
    ) -> Dict:
        """
        Estimate OLS regression with robust standard errors
        
        Args:
            y: Dependent variable (company returns)
            X: Design matrix (macro variables + controls)
            column_names: Names of X columns
        
        Returns:
            Dictionary with regression results
        """
        # Remove NaN observations
        valid_idx = ~(np.isnan(y) | np.isnan(X).any(axis=1))
        y_clean = y[valid_idx]
        X_clean = X[valid_idx]
        
        n_obs = len(y_clean)
        
        if n_obs < self.min_observations:
            return {
                'success': False,
                'reason': 'insufficient_observations',
                'n_obs': n_obs
            }
        # Avoid underdetermined / near-underdetermined fits that produce unstable
        # inference and artificially large t-stats.
        k_cols = int(X_clean.shape[1])
        if n_obs <= (k_cols + 10):
            return {
                'success': False,
                'reason': 'insufficient_degrees_of_freedom',
                'n_obs': n_obs,
                'n_features': k_cols,
            }
        
        try:
            # OLS estimation: θ = (X'X)^{-1} X'y
            XtX = X_clean.T @ X_clean
            Xty = X_clean.T @ y_clean

            # Handle multicollinearity with light ridge regularization instead of failing.
            condition_number = float(np.linalg.cond(XtX))
            regularized = False
            if condition_number > 1e10:
                ridge_lambda = 1e-6 * (np.trace(XtX) / max(XtX.shape[0], 1))
                XtX = XtX + np.eye(XtX.shape[0]) * max(ridge_lambda, 1e-8)
                regularized = True

            theta = np.linalg.solve(XtX, Xty)
            
            # Fitted values and residuals
            y_fitted = X_clean @ theta
            residuals = y_clean - y_fitted
            
            # R-squared
            ss_total = np.sum((y_clean - y_clean.mean()) ** 2)
            ss_residual = np.sum(residuals ** 2)
            r_squared = 1 - (ss_residual / ss_total) if ss_total > 0 else 0
            
            # Adjusted R-squared
            n = len(y_clean)
            k = X_clean.shape[1]
            adj_r_squared = 1 - (1 - r_squared) * (n - 1) / (n - k - 1)
            
            # Standard errors
            if self.use_hac_se:
                # Newey-West HAC standard errors
                se = self._compute_hac_se(X_clean, residuals)
            else:
                # Homoskedastic standard errors
                sigma_squared = ss_residual / (n - k)
                try:
                    inv_x = np.linalg.inv(XtX)
                except np.linalg.LinAlgError:
                    inv_x = np.linalg.pinv(XtX)
                var_theta = sigma_squared * inv_x
                se = np.sqrt(np.diag(var_theta))

            invalid_se = (~np.isfinite(se)) | (se <= 1e-8)
            se = np.where(invalid_se, np.nan, se)

            # t-statistics and p-values (conservative guards for unstable SEs).
            t_stats = np.divide(theta, se, out=np.zeros_like(theta, dtype=float), where=np.isfinite(se))
            t_stats = np.clip(t_stats, -50.0, 50.0)
            dof = max(n - k, 1)
            p_values = 2 * (1 - stats.t.cdf(np.abs(t_stats), dof))
            p_values = np.where(np.isfinite(p_values), p_values, 1.0)
            p_values = np.where(invalid_se, 1.0, p_values)
            
            # Confidence intervals (95%)
            t_critical = stats.t.ppf(0.975, dof)
            ci_lower = np.where(np.isfinite(se), theta - t_critical * se, theta)
            ci_upper = np.where(np.isfinite(se), theta + t_critical * se, theta)
            
            return {
                'success': True,
                'n_obs': n_obs,
                'coefficients': theta,
                'std_errors': se,
                't_stats': t_stats,
                'p_values': p_values,
                'ci_lower': ci_lower,
                'ci_upper': ci_upper,
                'r_squared': r_squared,
                'adj_r_squared': adj_r_squared,
                'residuals': residuals,
                'fitted_values': y_fitted,
                'column_names': column_names,
                'condition_number': condition_number,
                'regularized': regularized,
            }
            
        except np.linalg.LinAlgError as e:
            return {
                'success': False,
                'reason': f'numerical_error: {str(e)}'
            }
    
    def _compute_hac_se(
        self,
        X: np.ndarray,
        residuals: np.ndarray,
        max_lags: int = 4
    ) -> np.ndarray:
        """
        Compute Newey-West HAC standard errors
        
        Args:
            X: Design matrix
            residuals: Regression residuals
            max_lags: Maximum lag for autocorrelation
        
        Returns:
            Array of standard errors
        """
        n, k = X.shape
        
        # Meat of sandwich estimator
        S = np.zeros((k, k))
        
        # Contemporaneous term
        for i in range(n):
            xi = X[i:i+1, :].T
            S += residuals[i]**2 * (xi @ xi.T)
        
        # Autocovariance terms with Bartlett kernel
        for lag in range(1, min(max_lags + 1, n)):
            weight = 1 - lag / (max_lags + 1)  # Bartlett kernel
            for i in range(n - lag):
                xi = X[i:i+1, :].T
                xj = X[i+lag:i+lag+1, :].T
                S += weight * residuals[i] * residuals[i+lag] * (xi @ xj.T + xj @ xi.T)
        
        # Bread of sandwich estimator
        try:
            XtX_inv = np.linalg.inv(X.T @ X)
        except np.linalg.LinAlgError:
            XtX_inv = np.linalg.pinv(X.T @ X)
        
        # Sandwich: (X'X)^{-1} S (X'X)^{-1}
        var_theta = XtX_inv @ S @ XtX_inv
        
        # Standard errors
        diag = np.diag(var_theta)
        diag = np.where(np.isfinite(diag) & (diag >= 0), diag, np.nan)
        se = np.sqrt(diag)
        
        return se
    
    def select_optimal_lag(
        self,
        results: Dict,
        macro_var_name: str
    ) -> Dict:
        """
        Select optimal lag for a macro variable based on t-statistic
        
        Args:
            results: Regression results dictionary
            macro_var_name: Base name of macro variable (without lag suffix)
        
        Returns:
            Dictionary with optimal lag info
        """
        if not results['success']:
            return {'optimal_lag': None, 'reason': 'regression_failed'}
        
        # Find all lags for this variable
        lag_results = []
        for i, col_name in enumerate(results['column_names']):
            if col_name.startswith(macro_var_name + '_lag'):
                lag_str = col_name.split('_lag')[-1]
                try:
                    lag = int(lag_str)
                    lag_results.append({
                        'lag': lag,
                        'coefficient': results['coefficients'][i],
                        't_stat': results['t_stats'][i],
                        'p_value': results['p_values'][i],
                        'abs_t_stat': abs(results['t_stats'][i])
                    })
                except ValueError:
                    continue
        
        if not lag_results:
            return {'optimal_lag': None, 'reason': 'no_lags_found'}
        
        # Select lag with highest absolute t-statistic
        optimal = max(lag_results, key=lambda x: x['abs_t_stat'])
        
        return {
            'optimal_lag': optimal['lag'],
            'coefficient': optimal['coefficient'],
            't_stat': optimal['t_stat'],
            'p_value': optimal['p_value'],
            'all_lags': lag_results
        }
    
    def apply_fdr_correction(
        self,
        p_values: np.ndarray,
        alpha: Optional[float] = None
    ) -> Tuple[np.ndarray, int]:
        """
        Apply Benjamini-Hochberg FDR correction
        
        Args:
            p_values: Array of p-values
            alpha: FDR level (default: self.fdr_alpha)
        
        Returns:
            Tuple of (rejected array, number of rejections)
        """
        if alpha is None:
            alpha = self.fdr_alpha
        
        m = len(p_values)
        
        # Sort p-values
        sorted_idx = np.argsort(p_values)
        sorted_p = p_values[sorted_idx]
        
        # Find largest k such that p_(k) <= (k/m) * alpha
        threshold_values = np.arange(1, m + 1) / m * alpha
        rejected_sorted = sorted_p <= threshold_values
        
        if rejected_sorted.any():
            max_k = np.where(rejected_sorted)[0][-1]
            threshold = sorted_p[max_k]
        else:
            threshold = 0
            max_k = -1
        
        # Map back to original order
        rejected = np.zeros(m, dtype=bool)
        if max_k >= 0:
            rejected[sorted_idx[:max_k + 1]] = True
        
        return rejected, int(rejected.sum())
    
    def run_company_regression(
        self,
        company_returns: pd.Series,
        macro_lagged: pd.DataFrame,
        market_factor: Optional[pd.Series] = None,
        ticker: str = ""
    ) -> Dict:
        """
        Run full regression analysis for one company
        
        Args:
            company_returns: Company return series
            macro_lagged: Lagged macro variables DataFrame
            market_factor: Market return for control
            ticker: Company ticker for logging
        
        Returns:
            Dictionary with complete regression results
        """
        # Prepare design matrix as DataFrame to preserve index alignment.
        X, column_names = self.prepare_design_matrix(
            macro_lagged,
            market_factor,
            add_intercept=True
        )
        X_df = pd.DataFrame(X, index=macro_lagged.index, columns=column_names)

        # Align in a deterministic index order.
        common_idx = macro_lagged.index.intersection(company_returns.index).sort_values()
        y = pd.to_numeric(company_returns.reindex(common_idx), errors="coerce").values
        X_aligned = X_df.reindex(common_idx).values
        
        # Estimate OLS
        results = self.estimate_ols(y, X_aligned, column_names)
        
        if not results['success']:
            return results
        
        # Apply FDR correction
        rejected, n_significant = self.apply_fdr_correction(results['p_values'])
        results['fdr_rejected'] = rejected
        results['n_significant'] = n_significant
        
        # Store results
        results['ticker'] = ticker
        
        return results
    
    def run_all_companies(
        self,
        returns_df: pd.DataFrame,
        macro_lagged: pd.DataFrame,
        market_factor: Optional[pd.Series] = None,
        max_companies: Optional[int] = None
    ) -> Dict[str, Dict]:
        """
        Run regression for all companies (vectorized where possible)
        
        Args:
            returns_df: DataFrame with company returns
            macro_lagged: Lagged macro variables
            market_factor: Market return for control
            max_companies: Limit number of companies (for testing)
        
        Returns:
            Dictionary mapping ticker -> regression results
        """
        print("=" * 80)
        print("📐 RUNNING LAGGED REGRESSIONS")
        print("=" * 80)
        
        tickers = returns_df.columns.tolist()
        if max_companies:
            tickers = tickers[:max_companies]
        
        print(f"\n   Companies: {len(tickers)}")
        print(f"   Macro variables: {len(macro_lagged.columns)}")
        
        all_results = {}
        
        for i, ticker in enumerate(tickers):
            if (i + 1) % 50 == 0:
                print(f"   Progress: {i+1}/{len(tickers)} companies")
            
            company_returns = returns_df[ticker]
            results = self.run_company_regression(
                company_returns,
                macro_lagged,
                market_factor,
                ticker
            )
            
            all_results[ticker] = results
        
        # Summary statistics
        successful = sum(1 for r in all_results.values() if r.get('success', False))
        
        print(f"\n✅ REGRESSIONS COMPLETE")
        print(f"   Successful: {successful}/{len(tickers)}")
        print(f"   Failed: {len(tickers) - successful}")
        print("=" * 80)
        
        self.regression_results = all_results
        return all_results
    
    def extract_macro_betas(
        self,
        results_dict: Dict[str, Dict],
        macro_var_name: str
    ) -> pd.DataFrame:
        """
        Extract beta coefficients for a specific macro variable across all companies
        
        Args:
            results_dict: Dictionary of regression results
            macro_var_name: Name of macro variable
        
        Returns:
            DataFrame with columns: ticker, lag, beta, t_stat, p_value, significant
        """
        rows = []
        
        for ticker, results in results_dict.items():
            if not results.get('success', False):
                continue
            
            # Find all lags for this variable
            for i, col_name in enumerate(results['column_names']):
                if col_name.startswith(macro_var_name + '_lag'):
                    lag_str = col_name.split('_lag')[-1]
                    try:
                        lag = int(lag_str)
                        rows.append({
                            'ticker': ticker,
                            'macro_variable': macro_var_name,
                            'lag': lag,
                            'beta': results['coefficients'][i],
                            't_stat': results['t_stats'][i],
                            'p_value': results['p_values'][i],
                            'significant': bool(
                                results['fdr_rejected'][i]
                                and np.isfinite(results['t_stats'][i])
                                and abs(float(results['t_stats'][i])) >= 2.0
                                and np.isfinite(results['p_values'][i])
                                and float(results['p_values'][i]) <= 0.05
                            ),
                            'ci_lower': results['ci_lower'][i],
                            'ci_upper': results['ci_upper'][i]
                        })
                    except (ValueError, IndexError):
                        continue
        
        return pd.DataFrame(rows)
