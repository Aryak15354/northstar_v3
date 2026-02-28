#!/usr/bin/env python3
"""
🏭 SECTOR AGGREGATOR - MIE COMPONENT 7
Aggregate company-level macro sensitivities to sector level

Sector Beta:
β_{sector,k} = median(β_{i,k}) for i in sector

Reveals:
- Banking sensitive to liquidity
- Auto sensitive to rates
- IT sensitive to USD/INR
- FMCG sensitive to CPI
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
import warnings
warnings.filterwarnings('ignore')


class SectorAggregator:
    """
    Aggregate macro sensitivities from company to sector level
    """
    
    def __init__(self):
        print(f"🏭 Sector Aggregator initialized")
    
    def aggregate_to_sector(
        self,
        beta_df: pd.DataFrame,
        sector_map: Dict[str, str],
        agg_method: str = 'median'
    ) -> pd.DataFrame:
        """
        Aggregate company betas to sector level
        
        Args:
            beta_df: DataFrame with columns [ticker, macro_variable, lag, beta, ...]
            sector_map: Dict mapping ticker -> sector
            agg_method: 'median', 'mean', or 'weighted_mean'
        
        Returns:
            DataFrame with sector-level betas
        """
        # Add sector column
        beta_df['sector'] = beta_df['ticker'].map(sector_map)
        
        # Remove companies without sector mapping
        beta_df = beta_df.dropna(subset=['sector'])
        
        # Aggregate by sector, macro_variable, lag
        if agg_method == 'median':
            sector_betas = beta_df.groupby(['sector', 'macro_variable', 'lag']).agg({
                'beta': 'median',
                't_stat': lambda x: np.median(np.abs(x)),  # Median absolute t-stat
                'p_value': 'median',
                'ticker': 'count'  # Number of companies
            }).reset_index()
        elif agg_method == 'mean':
            sector_betas = beta_df.groupby(['sector', 'macro_variable', 'lag']).agg({
                'beta': 'mean',
                't_stat': lambda x: np.mean(np.abs(x)),
                'p_value': 'mean',
                'ticker': 'count'
            }).reset_index()
        else:
            raise ValueError(f"Unknown aggregation method: {agg_method}")
        
        sector_betas.rename(columns={'ticker': 'n_companies'}, inplace=True)
        
        return sector_betas
    
    def create_sector_heatmap_data(
        self,
        sector_betas: pd.DataFrame,
        top_n_vars: int = 20
    ) -> pd.DataFrame:
        """
        Create data for sector × macro variable heatmap
        
        Args:
            sector_betas: Sector-level beta DataFrame
            top_n_vars: Number of top macro variables to include
        
        Returns:
            Pivot table: sectors × macro_variables
        """
        # Select optimal lag for each sector-macro pair
        idx = sector_betas.groupby(['sector', 'macro_variable'])['t_stat'].idxmax()
        optimal_lag_betas = sector_betas.loc[idx]
        
        # Select top N most impactful macro variables
        macro_importance = optimal_lag_betas.groupby('macro_variable')['t_stat'].mean()
        top_macros = macro_importance.nlargest(top_n_vars).index
        
        # Filter to top macros
        filtered = optimal_lag_betas[optimal_lag_betas['macro_variable'].isin(top_macros)]
        
        # Pivot to heatmap format
        heatmap = filtered.pivot(
            index='sector',
            columns='macro_variable',
            values='beta'
        )
        
        return heatmap
    
    def identify_sector_macro_drivers(
        self,
        sector_betas: pd.DataFrame,
        sector: str,
        top_n: int = 5
    ) -> pd.DataFrame:
        """
        Identify top macro drivers for a specific sector
        
        Args:
            sector_betas: Sector-level beta DataFrame
            sector: Sector name
            top_n: Number of top drivers to return
        
        Returns:
            DataFrame with top macro drivers
        """
        sector_data = sector_betas[sector_betas['sector'] == sector].copy()
        
        # Rank by absolute t-statistic
        sector_data['abs_t_stat'] = sector_data['t_stat'].abs()
        top_drivers = sector_data.nlargest(top_n, 'abs_t_stat')
        
        return top_drivers[['macro_variable', 'lag', 'beta', 't_stat', 'p_value']]
