#!/usr/bin/env python3
"""
🔬 GRANGER CAUSALITY TESTER - MIE COMPONENT 4
Test if macro variables have predictive power for company returns

Granger Causality Test:
Does M_k improve forecast of R_i beyond autoregressive model?

H0: M_k does not Granger-cause R_i
H1: M_k Granger-causes R_i
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from scipy import stats
import warnings
warnings.filterwarnings('ignore')


class GrangerCausalityTester:
    """
    Test predictive causality from macro variables to company returns
    """
    
    def __init__(self, max_lags: int = 12, alpha: float = 0.05):
        self.max_lags = max_lags
        self.alpha = alpha
        print(f"🔬 Granger Causality Tester initialized (max_lags={max_lags})")
    
    def granger_test(
        self,
        y: pd.Series,
        x: pd.Series,
        max_lag: Optional[int] = None
    ) -> Dict:
        """
        Perform Granger causality test
        
        Returns:
            Dict with F-statistic, p-value, and causality decision
        """
        from statsmodels.tsa.stattools import grangercausalitytests
        
        if max_lag is None:
            max_lag = self.max_lags
        
        # Align series
        common_idx = y.index.intersection(x.index)
        y_aligned = y.loc[common_idx].dropna()
        x_aligned = x.loc[common_idx].dropna()
        
        # Combine into DataFrame
        data = pd.DataFrame({'y': y_aligned, 'x': x_aligned}).dropna()
        
        if len(data) < max_lag + 20:
            return {'success': False, 'reason': 'insufficient_data'}
        
        try:
            # Run Granger test
            results = grangercausalitytests(data[['y', 'x']], max_lag, verbose=False)
            
            # Extract results for each lag
            lag_results = []
            for lag in range(1, max_lag + 1):
                test_result = results[lag][0]
                f_stat = test_result['ssr_ftest'][0]
                p_value = test_result['ssr_ftest'][1]
                
                lag_results.append({
                    'lag': lag,
                    'f_statistic': f_stat,
                    'p_value': p_value,
                    'granger_causes': p_value < self.alpha
                })
            
            # Find best lag (lowest p-value)
            best_lag = min(lag_results, key=lambda x: x['p_value'])
            
            return {
                'success': True,
                'granger_causes': best_lag['granger_causes'],
                'best_lag': best_lag['lag'],
                'best_p_value': best_lag['p_value'],
                'all_lags': lag_results
            }
            
        except Exception as e:
            return {'success': False, 'reason': str(e)}
    
    def test_all_macro_vars(
        self,
        company_returns: pd.Series,
        macro_df: pd.DataFrame,
        ticker: str = ""
    ) -> pd.DataFrame:
        """
        Test Granger causality for all macro variables
        
        Returns:
            DataFrame with test results
        """
        results = []
        
        for macro_var in macro_df.columns:
            test_result = self.granger_test(company_returns, macro_df[macro_var])
            
            if test_result['success']:
                results.append({
                    'ticker': ticker,
                    'macro_variable': macro_var,
                    'granger_causes': test_result['granger_causes'],
                    'best_lag': test_result['best_lag'],
                    'p_value': test_result['best_p_value']
                })
        
        return pd.DataFrame(results)
