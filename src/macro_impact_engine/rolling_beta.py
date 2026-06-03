#!/usr/bin/env python3
"""
📊 ROLLING BETA ESTIMATOR - MIE COMPONENT 5
Estimate time-varying macro sensitivities

Rolling Window Regression:
β_{i,k,t} = estimated over window [t-W, t]

Stability Metric:
S_{i,k} = std(β_{i,k,t}) / |mean(β_{i,k,t})|

Low S = stable relationship
High S = regime-dependent relationship
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
import warnings
warnings.filterwarnings('ignore')


class RollingBetaEstimator:
    """
    Estimate time-varying macro sensitivities using rolling windows
    """
    
    def __init__(
        self,
        window_sizes: List[int] = [156, 260],  # 3 years, 5 years (weekly)
        min_periods: int = 52
    ):
        self.window_sizes = window_sizes
        self.min_periods = min_periods
        print(f"📊 Rolling Beta Estimator initialized")
        print(f"   Window sizes: {window_sizes} periods")
    
    def estimate_rolling_beta(
        self,
        y: pd.Series,
        x: pd.Series,
        window: int,
        min_periods: Optional[int] = None
    ) -> pd.Series:
        """
        Estimate rolling beta coefficient
        
        Args:
            y: Dependent variable (company returns)
            x: Independent variable (macro variable)
            window: Rolling window size
            min_periods: Minimum observations required
        
        Returns:
            Series of rolling beta estimates
        """
        if min_periods is None:
            min_periods = self.min_periods
        
        # Align series
        common_idx = y.index.intersection(x.index)
        y_aligned = y.loc[common_idx]
        x_aligned = x.loc[common_idx]
        
        # Rolling covariance and variance
        rolling_cov = y_aligned.rolling(window, min_periods=min_periods).cov(x_aligned)
        rolling_var = x_aligned.rolling(window, min_periods=min_periods).var()
        
        # Beta = Cov(y,x) / Var(x)
        rolling_beta = rolling_cov / rolling_var
        
        return rolling_beta
    
    def compute_stability(self, rolling_beta: pd.Series) -> Dict:
        """
        Compute stability metrics for rolling beta
        
        Returns:
            Dict with stability statistics
        """
        beta_clean = rolling_beta.dropna()
        
        if len(beta_clean) < 10:
            return {
                'stability': np.nan,
                'mean_beta': np.nan,
                'std_beta': np.nan,
                'reason': 'insufficient_data'
            }
        
        mean_beta = beta_clean.mean()
        std_beta = beta_clean.std()
        
        # Stability = std / |mean|
        if abs(mean_beta) > 1e-6:
            stability = std_beta / abs(mean_beta)
        else:
            stability = np.inf
        
        return {
            'stability': stability,
            'mean_beta': mean_beta,
            'std_beta': std_beta,
            'min_beta': beta_clean.min(),
            'max_beta': beta_clean.max(),
            'sign_changes': (np.diff(np.sign(beta_clean)) != 0).sum()
        }
    
    def estimate_all_windows(
        self,
        y: pd.Series,
        x: pd.Series
    ) -> Dict[int, Dict]:
        """
        Estimate rolling beta for all window sizes
        
        Returns:
            Dict mapping window_size -> results
        """
        results = {}
        
        for window in self.window_sizes:
            rolling_beta = self.estimate_rolling_beta(y, x, window)
            stability = self.compute_stability(rolling_beta)
            
            results[window] = {
                'rolling_beta': rolling_beta,
                'stability': stability
            }
        
        return results
