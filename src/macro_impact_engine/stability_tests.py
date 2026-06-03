#!/usr/bin/env python3
"""
🔍 STABILITY ANALYZER - MIE COMPONENT 6
Test stability of macro-equity relationships across regimes

Tests:
1. Chow test for structural breaks
2. Regime-conditional betas
3. Crisis vs expansion sensitivity
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from scipy import stats
import warnings
warnings.filterwarnings('ignore')


class StabilityAnalyzer:
    """
    Analyze stability of macro sensitivities across time and regimes
    """
    
    def __init__(self):
        print(f"🔍 Stability Analyzer initialized")
    
    def chow_test(
        self,
        y: pd.Series,
        x: pd.Series,
        breakpoint: pd.Timestamp
    ) -> Dict:
        """
        Chow test for structural break at specified date
        
        Returns:
            Dict with F-statistic and p-value
        """
        # Split data at breakpoint
        y1 = y[y.index < breakpoint]
        x1 = x[x.index < breakpoint]
        y2 = y[y.index >= breakpoint]
        x2 = x[x.index >= breakpoint]
        
        if len(y1) < 20 or len(y2) < 20:
            return {'success': False, 'reason': 'insufficient_data'}
        
        # Estimate full model
        X_full = np.column_stack([np.ones(len(x)), x.values])
        theta_full = np.linalg.lstsq(X_full, y.values, rcond=None)[0]
        rss_full = np.sum((y.values - X_full @ theta_full) ** 2)
        
        # Estimate split models
        X1 = np.column_stack([np.ones(len(x1)), x1.values])
        theta1 = np.linalg.lstsq(X1, y1.values, rcond=None)[0]
        rss1 = np.sum((y1.values - X1 @ theta1) ** 2)
        
        X2 = np.column_stack([np.ones(len(x2)), x2.values])
        theta2 = np.linalg.lstsq(X2, y2.values, rcond=None)[0]
        rss2 = np.sum((y2.values - X2 @ theta2) ** 2)
        
        # Chow F-statistic
        k = 2  # Number of parameters
        n = len(y)
        f_stat = ((rss_full - (rss1 + rss2)) / k) / ((rss1 + rss2) / (n - 2*k))
        p_value = 1 - stats.f.cdf(f_stat, k, n - 2*k)
        
        return {
            'success': True,
            'f_statistic': f_stat,
            'p_value': p_value,
            'structural_break': p_value < 0.05,
            'beta_before': theta1[1],
            'beta_after': theta2[1]
        }
    
    def regime_conditional_beta(
        self,
        y: pd.Series,
        x: pd.Series,
        regime: pd.Series
    ) -> Dict[str, float]:
        """
        Estimate beta conditional on regime
        
        Args:
            y: Company returns
            x: Macro variable
            regime: Regime labels (e.g., 'expansion', 'crisis')
        
        Returns:
            Dict mapping regime -> beta
        """
        regime_betas = {}
        
        for regime_name in regime.unique():
            mask = regime == regime_name
            y_regime = y[mask]
            x_regime = x[mask]
            
            if len(y_regime) < 20:
                regime_betas[regime_name] = np.nan
                continue
            
            # Simple OLS
            X = np.column_stack([np.ones(len(x_regime)), x_regime.values])
            theta = np.linalg.lstsq(X, y_regime.values, rcond=None)[0]
            regime_betas[regime_name] = theta[1]
        
        return regime_betas
