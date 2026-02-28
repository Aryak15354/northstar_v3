#!/usr/bin/env python3
"""
📄 MACRO IMPACT REPORT GENERATOR - MIE COMPONENT 8
Generate institutional-grade reports and visualizations

Outputs:
1. Company Macro Fingerprint
2. Sector Macro Sensitivity Map
3. Portfolio Macro Exposure Report
4. Macro Stress Test Results
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional
import json
import re
import warnings
warnings.filterwarnings('ignore')


class MacroImpactReportGenerator:
    """
    Generate comprehensive macro impact reports
    """
    
    def __init__(self, output_dir: str = "reports/macro_impact"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        print(f"📄 Report Generator initialized")
        print(f"   Output directory: {self.output_dir}")
    
    def generate_company_fingerprint(
        self,
        ticker: str,
        regression_results: Dict,
        top_n: int = 10
    ) -> Dict:
        """
        Generate macro fingerprint for a company
        
        Returns:
            Dict with top macro drivers and their characteristics
        """
        if not regression_results.get('success', False):
            return {'ticker': ticker, 'error': 'regression_failed'}
        
        # Extract significant relationships
        significant_idx = regression_results['fdr_rejected']
        
        if not significant_idx.any():
            return {'ticker': ticker, 'top_drivers': [], 'message': 'no_significant_relationships'}
        
        # Create DataFrame of results
        results_df = pd.DataFrame({
            'variable': regression_results['column_names'],
            'beta': regression_results['coefficients'],
            't_stat': regression_results['t_stats'],
            'p_value': regression_results['p_values'],
            'significant': significant_idx
        })
        
        # Filter to significant and sort by absolute t-stat
        significant_df = results_df[results_df['significant']].copy()
        significant_df['abs_t_stat'] = significant_df['t_stat'].abs()
        top_drivers = significant_df.nlargest(top_n, 'abs_t_stat')

        top_driver_rows = []
        top_driver_text_parts: List[str] = []
        for rec in top_drivers.to_dict('records'):
            var_raw = str(rec.get('variable', ''))
            lag_match = re.search(r"_lag(\d+)$", var_raw)
            lag_val = int(lag_match.group(1)) if lag_match else 0
            base_var = re.sub(r"_lag\d+$", "", var_raw)
            beta_val = float(pd.to_numeric(rec.get('beta'), errors='coerce') or 0.0)
            t_val = float(pd.to_numeric(rec.get('t_stat'), errors='coerce') or 0.0)
            p_val = float(pd.to_numeric(rec.get('p_value'), errors='coerce') or 1.0)
            row = {
                'variable': base_var,
                'lag': lag_val,
                'beta': beta_val,
                't_stat': t_val,
                'p_value': p_val,
            }
            top_driver_rows.append(row)
            top_driver_text_parts.append(
                f"{base_var} (lag {lag_val}, beta {beta_val:+.3f}, t {t_val:+.2f})"
            )
        
        fingerprint = {
            'ticker': ticker,
            'n_obs': regression_results['n_obs'],
            'r_squared': regression_results['r_squared'],
            'adj_r_squared': regression_results['adj_r_squared'],
            'n_significant': int(significant_idx.sum()),
            'top_drivers': top_driver_rows,
            'top_drivers_text': " | ".join(top_driver_text_parts)
        }
        
        return fingerprint
    
    def generate_sector_report(
        self,
        sector: str,
        sector_betas: pd.DataFrame,
        top_n: int = 10
    ) -> Dict:
        """
        Generate macro sensitivity report for a sector
        
        Returns:
            Dict with sector macro profile
        """
        sector_data = sector_betas[sector_betas['sector'] == sector].copy()
        
        if len(sector_data) == 0:
            return {'sector': sector, 'error': 'no_data'}
        
        # Top drivers
        sector_data['abs_t_stat'] = sector_data['t_stat'].abs()
        top_drivers = sector_data.nlargest(top_n, 'abs_t_stat')
        
        report = {
            'sector': sector,
            'n_companies': int(sector_data['n_companies'].iloc[0]),
            'top_macro_drivers': top_drivers[['macro_variable', 'lag', 'beta', 't_stat']].to_dict('records'),
            'average_lag': float(sector_data['lag'].mean()),
            'median_beta': float(sector_data['beta'].median())
        }
        
        return report
    
    def generate_portfolio_exposure_report(
        self,
        portfolio_weights: Dict[str, float],
        company_betas: pd.DataFrame
    ) -> Dict:
        """
        Calculate portfolio-level macro exposures
        
        Args:
            portfolio_weights: Dict mapping ticker -> weight
            company_betas: DataFrame with company-level betas
        
        Returns:
            Dict with portfolio macro exposures
        """
        # Filter to portfolio companies
        portfolio_tickers = list(portfolio_weights.keys())
        portfolio_betas = company_betas[company_betas['ticker'].isin(portfolio_tickers)].copy()
        
        # Add weights
        portfolio_betas['weight'] = portfolio_betas['ticker'].map(portfolio_weights)
        
        # Calculate weighted average beta for each macro variable
        portfolio_betas['weighted_beta'] = portfolio_betas['beta'] * portfolio_betas['weight']
        
        portfolio_exposure = portfolio_betas.groupby('macro_variable').agg({
            'weighted_beta': 'sum',
            'ticker': 'count'
        }).reset_index()
        
        portfolio_exposure.rename(columns={
            'weighted_beta': 'portfolio_beta',
            'ticker': 'n_holdings'
        }, inplace=True)
        
        # Sort by absolute exposure
        portfolio_exposure['abs_beta'] = portfolio_exposure['portfolio_beta'].abs()
        portfolio_exposure = portfolio_exposure.sort_values('abs_beta', ascending=False)
        
        report = {
            'portfolio_size': len(portfolio_weights),
            'macro_exposures': portfolio_exposure.to_dict('records'),
            'top_positive_exposure': portfolio_exposure.nlargest(1, 'portfolio_beta').to_dict('records')[0],
            'top_negative_exposure': portfolio_exposure.nsmallest(1, 'portfolio_beta').to_dict('records')[0]
        }
        
        return report
    
    def save_report(self, report: Dict, filename: str):
        """Save report to JSON file"""
        output_path = self.output_dir / filename
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        print(f"   ✓ Saved: {output_path}")
    
    def save_dataframe(self, df: pd.DataFrame, filename: str):
        """Save DataFrame to CSV"""
        output_path = self.output_dir / filename
        df.to_csv(output_path, index=False)
        print(f"   ✓ Saved: {output_path}")
