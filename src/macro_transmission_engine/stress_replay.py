#!/usr/bin/env python3
"""
🔴 MACRO STRESS REPLAY ENGINE
Simulate historical macro shocks on current portfolio

Scenarios:
- 2008 Financial Crisis
- 2013 Taper Tantrum
- 2020 COVID Shock
- Custom shock vectors

Output:
    - Stock-level impacts
    - Portfolio-level impact
    - Sector decomposition
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional
import warnings
warnings.filterwarnings('ignore')


class MacroStressReplay:
    """
    Replay historical macro shocks on current portfolio
    
    Formula:
        ΔR_i = β_i^T ΔM
        ΔR_portfolio = Σ w_i β_i^T ΔM
    """
    
    def __init__(self):
        # Predefined shock scenarios
        self.scenarios = {
            '2008_crisis': {
                'name': '2008 Financial Crisis',
                'description': 'Lehman collapse, credit freeze',
                'shocks': {}  # To be populated
            },
            '2013_taper': {
                'name': '2013 Taper Tantrum',
                'description': 'Fed taper announcement',
                'shocks': {}
            },
            '2020_covid': {
                'name': '2020 COVID Shock',
                'description': 'Pandemic lockdowns',
                'shocks': {}
            }
        }
        
        print(f"🔴 Macro Stress Replay Engine initialized")
    
    def define_shock(
        self,
        scenario_name: str,
        shock_vector: Dict[str, float]
    ):
        """
        Define custom shock scenario
        
        Args:
            scenario_name: Name of scenario
            shock_vector: Dict mapping macro_variable → shock size
        """
        self.scenarios[scenario_name] = {
            'name': scenario_name,
            'shocks': shock_vector
        }
    
    def replay_shock(
        self,
        scenario_name: str,
        beta_df: pd.DataFrame,
        portfolio_weights: Optional[Dict[str, float]] = None
    ) -> Dict:
        """
        Replay shock scenario
        
        Args:
            scenario_name: Name of scenario
            beta_df: Macro betas DataFrame
            portfolio_weights: Optional portfolio weights
        
        Returns:
            Dict with impact analysis
        """
        if scenario_name not in self.scenarios:
            raise ValueError(f"Unknown scenario: {scenario_name}")
        
        shock_vector = self.scenarios[scenario_name]['shocks']
        
        # Compute stock-level impacts
        stock_impacts = {}
        
        for ticker in beta_df['ticker'].unique():
            company_betas = beta_df[beta_df['ticker'] == ticker]
            
            impact = 0.0
            for _, row in company_betas.iterrows():
                macro_var = row['macro_variable']
                beta = row['beta']
                
                if macro_var in shock_vector:
                    impact += beta * shock_vector[macro_var]
            
            stock_impacts[ticker] = impact
        
        # Compute portfolio impact if weights provided
        portfolio_impact = None
        if portfolio_weights:
            portfolio_impact = sum(
                portfolio_weights.get(ticker, 0) * impact
                for ticker, impact in stock_impacts.items()
            )
        
        return {
            'scenario': scenario_name,
            'stock_impacts': stock_impacts,
            'portfolio_impact': portfolio_impact,
            'worst_stocks': sorted(stock_impacts.items(), key=lambda x: x[1])[:10],
            'best_stocks': sorted(stock_impacts.items(), key=lambda x: x[1], reverse=True)[:10]
        }
