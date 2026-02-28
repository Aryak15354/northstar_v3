#!/usr/bin/env python3
"""
⚖️ MACRO-ADJUSTED ALPHA WEIGHTING
Adjust raw signals based on macro environment

Formula:
    α_i^{adj} = α_i + λ · β_i^T E[ΔM]

Where:
    α_i = raw signal
    β_i = macro sensitivity vector
    E[ΔM] = expected macro change
    λ = adjustment strength

Output:
    - Macro-adjusted alpha
    - Macro contribution to signal
    - Risk-adjusted confidence
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional
import warnings
warnings.filterwarnings('ignore')


class MacroAlphaAdjuster:
    """
    Adjust alpha signals based on macro forecasts
    
    Integrates:
    - Raw alpha signals
    - Macro sensitivities (β)
    - Macro forecasts (E[ΔM])
    """
    
    def __init__(
        self,
        adjustment_strength: float = 0.5,
        use_conviction_weighting: bool = True
    ):
        self.adjustment_strength = adjustment_strength
        self.use_conviction_weighting = use_conviction_weighting
        
        print(f"⚖️ Macro Alpha Adjuster initialized")
        print(f"   Adjustment strength: {adjustment_strength}")
    
    def adjust_alpha(
        self,
        raw_alpha: pd.Series,
        beta_df: pd.DataFrame,
        expected_macro_change: pd.Series,
        conviction_scores: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """
        Adjust alpha signals with macro information
        
        Args:
            raw_alpha: Raw alpha signals (ticker → alpha)
            beta_df: Macro betas (ticker × macro_variable → beta)
            expected_macro_change: Expected macro changes (macro_variable → ΔM)
            conviction_scores: Optional conviction scores (ticker × macro_variable → conviction)
        
        Returns:
            DataFrame with adjusted alphas
        """
        results = []
        
        for ticker in raw_alpha.index:
            # Get company betas
            company_betas = beta_df[beta_df['ticker'] == ticker]
            
            if company_betas.empty:
                # No macro info, use raw alpha
                results.append({
                    'ticker': ticker,
                    'raw_alpha': raw_alpha[ticker],
                    'macro_adjustment': 0.0,
                    'adjusted_alpha': raw_alpha[ticker]
                })
                continue
            
            # Compute macro contribution
            macro_contrib = 0.0
            
            for _, row in company_betas.iterrows():
                macro_var = row['macro_variable']
                beta = pd.to_numeric(row.get('beta'), errors='coerce')
                if not np.isfinite(beta):
                    continue
                
                if macro_var in expected_macro_change.index:
                    delta_M = pd.to_numeric(expected_macro_change[macro_var], errors='coerce')
                    if not np.isfinite(delta_M):
                        continue
                    
                    # Weight by conviction if available
                    weight = 1.0
                    if self.use_conviction_weighting and conviction_scores is not None:
                        conv_row = conviction_scores[
                            (conviction_scores['ticker'] == ticker) &
                            (conviction_scores['macro_variable'] == macro_var)
                        ]
                        if not conv_row.empty:
                            weight = conv_row.iloc[0]['conviction']
                    
                    macro_contrib += weight * beta * delta_M
            
            # Adjust alpha
            macro_adjustment = self.adjustment_strength * macro_contrib
            if not np.isfinite(macro_adjustment):
                macro_adjustment = 0.0
            adjusted_alpha = pd.to_numeric(raw_alpha[ticker], errors='coerce') + macro_adjustment
            
            results.append({
                'ticker': ticker,
                'raw_alpha': raw_alpha[ticker],
                'macro_adjustment': macro_adjustment,
                'adjusted_alpha': adjusted_alpha
            })
        
        return pd.DataFrame(results)
