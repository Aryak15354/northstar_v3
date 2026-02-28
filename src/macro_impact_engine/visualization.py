#!/usr/bin/env python3
"""
📊 MACRO IMPACT VISUALIZATION - MIE COMPONENT 9
Create institutional-grade visualizations

Visualizations:
1. Company Macro Fingerprint (Radar Chart)
2. Sector Heatmap
3. Lag Distribution
4. Stability Map
5. Portfolio Exposure Panel
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
import warnings
warnings.filterwarnings('ignore')


class MacroImpactVisualizer:
    """
    Create visualizations for macro impact analysis
    
    Note: This module provides data preparation for visualization.
    Actual plotting requires matplotlib/plotly which should be
    installed separately.
    """
    
    def __init__(self):
        print(f"📊 Macro Impact Visualizer initialized")
    
    def prepare_radar_chart_data(
        self,
        ticker: str,
        regression_results: Dict,
        macro_categories: Dict[str, List[str]]
    ) -> Dict:
        """
        Prepare data for company macro fingerprint radar chart
        
        Args:
            ticker: Company ticker
            regression_results: Regression results for company
            macro_categories: Dict mapping category -> list of macro variables
                             e.g., {'Growth': ['gdp', 'iip'], 'Inflation': ['cpi', 'wpi']}
        
        Returns:
            Dict with radar chart data
        """
        if not regression_results.get('success', False):
            return {'error': 'regression_failed'}
        
        # Calculate average beta for each category
        category_betas = {}
        
        for category, variables in macro_categories.items():
            betas = []
            for i, col_name in enumerate(regression_results['column_names']):
                # Check if this column belongs to this category
                for var in variables:
                    if var in col_name.lower():
                        if regression_results['fdr_rejected'][i]:
                            betas.append(regression_results['coefficients'][i])
            
            if betas:
                category_betas[category] = np.mean(betas)
            else:
                category_betas[category] = 0.0
        
        return {
            'ticker': ticker,
            'categories': list(category_betas.keys()),
            'values': list(category_betas.values())
        }
    
    def prepare_heatmap_data(
        self,
        sector_betas: pd.DataFrame,
        top_n_vars: int = 20,
        top_n_sectors: int = 10
    ) -> pd.DataFrame:
        """
        Prepare data for sector × macro variable heatmap
        
        Args:
            sector_betas: Sector-level beta DataFrame
            top_n_vars: Number of top macro variables
            top_n_sectors: Number of top sectors
        
        Returns:
            Pivot table ready for heatmap
        """
        # Select optimal lag for each sector-macro pair
        idx = sector_betas.groupby(['sector', 'macro_variable'])['t_stat'].transform('max') == sector_betas['t_stat']
        optimal_lag_betas = sector_betas[idx]
        
        # Select top N most impactful macro variables
        macro_importance = optimal_lag_betas.groupby('macro_variable')['t_stat'].apply(lambda x: np.abs(x).mean())
        top_macros = macro_importance.nlargest(top_n_vars).index
        
        # Select top N sectors by number of companies
        top_sectors = sector_betas.groupby('sector')['n_companies'].first().nlargest(top_n_sectors).index
        
        # Filter
        filtered = optimal_lag_betas[
            (optimal_lag_betas['macro_variable'].isin(top_macros)) &
            (optimal_lag_betas['sector'].isin(top_sectors))
        ]
        
        # Pivot
        heatmap = filtered.pivot(
            index='sector',
            columns='macro_variable',
            values='beta'
        )
        
        return heatmap
    
    def prepare_lag_distribution_data(
        self,
        beta_df: pd.DataFrame,
        macro_variable: str
    ) -> Dict:
        """
        Prepare data for lag distribution chart
        
        Args:
            beta_df: Beta DataFrame with lag column
            macro_variable: Macro variable to analyze
        
        Returns:
            Dict with lag distribution data
        """
        var_data = beta_df[beta_df['macro_variable'] == macro_variable]
        
        if var_data.empty:
            return {'error': 'no_data'}
        
        # Count optimal lags
        lag_counts = var_data['lag'].value_counts().sort_index()
        
        return {
            'macro_variable': macro_variable,
            'lags': lag_counts.index.tolist(),
            'counts': lag_counts.values.tolist(),
            'median_lag': float(var_data['lag'].median()),
            'mean_lag': float(var_data['lag'].mean())
        }
    
    def prepare_stability_map_data(
        self,
        rolling_results: Dict[str, Dict],
        threshold_stable: float = 0.5
    ) -> pd.DataFrame:
        """
        Prepare data for stability map (bubble chart)
        
        Args:
            rolling_results: Dict mapping (ticker, macro_var) -> rolling results
            threshold_stable: Stability threshold (lower = more stable)
        
        Returns:
            DataFrame with columns: ticker, macro_var, mean_beta, stability, r_squared
        """
        rows = []
        
        for key, results in rolling_results.items():
            if '_' not in key:
                continue
            
            ticker, macro_var = key.rsplit('_', 1)
            
            # Get 3-year window results (156 weeks)
            if 156 in results:
                stability_info = results[156]['stability']
                
                rows.append({
                    'ticker': ticker,
                    'macro_variable': macro_var,
                    'mean_beta': stability_info['mean_beta'],
                    'stability': stability_info['stability'],
                    'is_stable': stability_info['stability'] < threshold_stable,
                    'sign_changes': stability_info['sign_changes']
                })
        
        return pd.DataFrame(rows)
    
    def prepare_portfolio_exposure_chart_data(
        self,
        portfolio_weights: Dict[str, float],
        company_betas: pd.DataFrame,
        top_n: int = 10
    ) -> Dict:
        """
        Prepare data for portfolio macro exposure bar chart
        
        Args:
            portfolio_weights: Dict mapping ticker -> weight
            company_betas: DataFrame with company-level betas
            top_n: Number of top exposures to show
        
        Returns:
            Dict with bar chart data
        """
        # Filter to portfolio companies
        portfolio_tickers = list(portfolio_weights.keys())
        portfolio_betas = company_betas[company_betas['ticker'].isin(portfolio_tickers)].copy()
        
        # Add weights
        portfolio_betas['weight'] = portfolio_betas['ticker'].map(portfolio_weights)
        
        # Calculate weighted average beta
        portfolio_betas['weighted_beta'] = portfolio_betas['beta'] * portfolio_betas['weight']
        
        # Aggregate by macro variable
        portfolio_exposure = portfolio_betas.groupby('macro_variable').agg({
            'weighted_beta': 'sum'
        }).reset_index()
        
        # Sort by absolute exposure
        portfolio_exposure['abs_beta'] = portfolio_exposure['weighted_beta'].abs()
        portfolio_exposure = portfolio_exposure.sort_values('abs_beta', ascending=False)
        
        # Top N
        top_exposures = portfolio_exposure.head(top_n)
        
        return {
            'macro_variables': top_exposures['macro_variable'].tolist(),
            'exposures': top_exposures['weighted_beta'].tolist(),
            'abs_exposures': top_exposures['abs_beta'].tolist()
        }
    
    def create_summary_table(
        self,
        regression_results: Dict[str, Dict],
        top_n: int = 20
    ) -> pd.DataFrame:
        """
        Create summary table of top companies by macro sensitivity
        
        Args:
            regression_results: Dict of regression results
            top_n: Number of top companies
        
        Returns:
            DataFrame with summary statistics
        """
        rows = []
        
        for ticker, results in regression_results.items():
            if not results.get('success', False):
                continue
            
            rows.append({
                'ticker': ticker,
                'r_squared': results['r_squared'],
                'adj_r_squared': results['adj_r_squared'],
                'n_significant': results['n_significant'],
                'n_obs': results['n_obs']
            })
        
        df = pd.DataFrame(rows)
        
        # Sort by R²
        df = df.sort_values('r_squared', ascending=False)
        
        return df.head(top_n)


# Example usage with matplotlib (optional)
def plot_example_radar_chart(data: Dict):
    """
    Example: Plot radar chart using matplotlib
    
    Requires: pip install matplotlib
    """
    try:
        import matplotlib.pyplot as plt
        from math import pi
        
        categories = data['categories']
        values = data['values']
        
        # Number of variables
        N = len(categories)
        
        # Compute angle for each axis
        angles = [n / float(N) * 2 * pi for n in range(N)]
        values += values[:1]  # Complete the circle
        angles += angles[:1]
        
        # Plot
        fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(projection='polar'))
        ax.plot(angles, values, 'o-', linewidth=2)
        ax.fill(angles, values, alpha=0.25)
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(categories)
        ax.set_title(f"Macro Fingerprint: {data['ticker']}", size=16, y=1.1)
        
        plt.tight_layout()
        return fig
    
    except ImportError:
        print("matplotlib not installed. Install with: pip install matplotlib")
        return None


def plot_example_heatmap(heatmap_df: pd.DataFrame):
    """
    Example: Plot heatmap using matplotlib/seaborn
    
    Requires: pip install matplotlib seaborn
    """
    try:
        import matplotlib.pyplot as plt
        import seaborn as sns
        
        fig, ax = plt.subplots(figsize=(12, 8))
        sns.heatmap(
            heatmap_df,
            annot=True,
            fmt='.2f',
            cmap='RdYlGn',
            center=0,
            cbar_kws={'label': 'Beta Coefficient'},
            ax=ax
        )
        ax.set_title('Sector Macro Sensitivity Heatmap', size=16)
        ax.set_xlabel('Macro Variable')
        ax.set_ylabel('Sector')
        
        plt.tight_layout()
        return fig
    
    except ImportError:
        print("matplotlib/seaborn not installed. Install with: pip install matplotlib seaborn")
        return None
