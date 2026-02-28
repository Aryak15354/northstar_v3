"""
Moat Scorer - Quantifies durable competitive advantages
Based on Warren Buffett's concept of economic moats
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional
from dataclasses import dataclass


@dataclass
class MoatAssessment:
    """Container for moat assessment"""
    overall_score: float  # 0-100
    moat_width: str  # 'Wide', 'Narrow', 'None'
    roic_consistency: float
    pricing_power: float
    switching_costs: float
    network_effects: float
    cost_advantage: float
    moat_sources: list


class MoatScorer:
    """
    Quantify economic moat using observable metrics
    
    Moat indicators:
    1. ROIC > WACC consistently (10+ years)
    2. Gross margin stability and level
    3. Customer retention (low churn)
    4. Pricing power (price increases without volume loss)
    5. Market share stability
    """
    
    def __init__(self):
        self.min_roic_threshold = 0.15  # 15% ROIC minimum
        self.wacc_proxy = 0.10  # 10% WACC proxy
        self.moat_years_required = 7  # Years of high ROIC needed
    
    def calculate_roic_consistency(
        self,
        roic_history: pd.Series,
        wacc: float = None
    ) -> Dict[str, float]:
        """
        Assess ROIC consistency and excess returns
        
        Wide moat: ROIC > 15% for 10+ years
        Narrow moat: ROIC > 12% for 7+ years
        """
        if wacc is None:
            wacc = self.wacc_proxy
        
        if len(roic_history) < 3:
            return {
                'avg_roic': roic_history.iloc[-1] if len(roic_history) > 0 else 0,
                'consistency_score': 0,
                'years_above_threshold': 0,
                'excess_return': 0
            }
        
        avg_roic = roic_history.mean()
        years_above_threshold = (roic_history > self.min_roic_threshold).sum()
        consistency = 1 - (roic_history.std() / (avg_roic + 0.01))  # Lower volatility = higher score
        excess_return = avg_roic - wacc
        
        # Score based on years above threshold
        if years_above_threshold >= 10:
            consistency_score = 100
        elif years_above_threshold >= 7:
            consistency_score = 80
        elif years_above_threshold >= 5:
            consistency_score = 60
        else:
            consistency_score = 40
        
        # Adjust for consistency
        consistency_score *= max(0, min(1, consistency))
        
        return {
            'avg_roic': avg_roic,
            'consistency_score': consistency_score,
            'years_above_threshold': years_above_threshold,
            'excess_return': excess_return
        }
    
    def calculate_pricing_power(
        self,
        gross_margin_history: pd.Series,
        revenue_growth_history: pd.Series
    ) -> float:
        """
        Assess pricing power through margin stability and growth
        
        Strong pricing power:
        - Stable or expanding gross margins
        - Revenue growth without margin compression
        """
        margins = pd.to_numeric(gross_margin_history, errors="coerce").dropna().reset_index(drop=True)
        growth = pd.to_numeric(revenue_growth_history, errors="coerce").dropna().reset_index(drop=True)

        if len(margins) < 3:
            return 50  # Neutral

        # Margin trend
        x = np.arange(len(margins))
        margin_trend = np.polyfit(x, margins.values, 1)[0]

        # Margin stability
        margin_cv = margins.std() / (margins.mean() + 0.01)
        stability_score = max(0, 1 - margin_cv * 5)  # Lower CV = higher score

        # Margin level
        avg_margin = margins.mean()
        level_score = min(1, avg_margin / 0.50)  # 50% margin = full score

        # Growth without margin compression
        aligned_len = min(len(margins), len(growth))
        if aligned_len >= 3:
            margins_aligned = margins.tail(aligned_len).reset_index(drop=True)
            growth_aligned = growth.tail(aligned_len).reset_index(drop=True)
            growth_periods = growth_aligned > 0.10  # 10%+ growth
            if growth_periods.sum() > 0:
                margins_during_growth = margins_aligned[growth_periods.values]
                margin_resilience = (margins_during_growth >= margins_aligned.median()).mean()
            else:
                margin_resilience = 0.5
        else:
            margin_resilience = 0.5

        # Combined score
        pricing_power_score = (
            (margin_trend > 0) * 25 +  # Expanding margins
            stability_score * 35 +      # Stable margins
            level_score * 25 +          # High margins
            margin_resilience * 15      # Resilient margins
        )
        
        return min(100, pricing_power_score)
    
    def calculate_switching_costs(
        self,
        # Proxies for switching costs
        customer_concentration: float,  # Lower is better (diversified)
        contract_length_years: float,   # Longer is better
        recurring_revenue_pct: float,   # Higher is better
        customer_retention_rate: float  # Higher is better
    ) -> float:
        """
        Estimate switching costs from observable metrics
        
        High switching costs indicated by:
        - Long-term contracts
        - High recurring revenue
        - High customer retention
        - Low customer concentration (not dependent on few customers)
        """
        # Contract length score (0-25)
        contract_score = min(25, contract_length_years * 5)  # 5 years = full score
        
        # Recurring revenue score (0-35)
        recurring_score = recurring_revenue_pct * 35
        
        # Retention score (0-30)
        retention_score = customer_retention_rate * 30
        
        # Concentration score (0-10) - inverse relationship
        concentration_score = (1 - customer_concentration) * 10
        
        total_score = contract_score + recurring_score + retention_score + concentration_score
        
        return min(100, total_score)
    
    def calculate_network_effects(
        self,
        market_share: float,
        market_share_trend: float,  # Positive = gaining share
        user_growth_rate: float,
        platform_indicator: bool
    ) -> float:
        """
        Assess network effects
        
        Strong network effects:
        - High and growing market share
        - Platform business model
        - Accelerating user growth
        """
        # Market share score (0-40)
        share_score = market_share * 40
        
        # Share trend score (0-20)
        trend_score = min(20, max(0, market_share_trend * 100 + 10))
        
        # User growth score (0-30)
        growth_score = min(30, user_growth_rate * 100)
        
        # Platform bonus (0-10)
        platform_score = 10 if platform_indicator else 0
        
        total_score = share_score + trend_score + growth_score + platform_score
        
        return min(100, total_score)
    
    def calculate_cost_advantage(
        self,
        operating_margin: float,
        operating_margin_vs_peers: float,  # Positive = better than peers
        scale_indicator: float,  # Revenue or production volume
        vertical_integration: bool
    ) -> float:
        """
        Assess cost advantage moat
        
        Cost advantage indicated by:
        - Higher operating margins than peers
        - Scale advantages
        - Vertical integration
        """
        # Margin level score (0-30)
        margin_score = min(30, operating_margin * 100)
        
        # Relative margin score (0-40)
        relative_score = min(40, max(0, operating_margin_vs_peers * 200 + 20))
        
        # Scale score (0-20)
        # Normalize scale_indicator (assume it's a percentile)
        scale_score = scale_indicator * 20
        
        # Integration bonus (0-10)
        integration_score = 10 if vertical_integration else 0
        
        total_score = margin_score + relative_score + scale_score + integration_score
        
        return min(100, total_score)
    
    def assess_moat(
        self,
        # ROIC data
        roic_history: pd.Series,
        wacc: Optional[float] = None,
        
        # Pricing power
        gross_margin_history: Optional[pd.Series] = None,
        revenue_growth_history: Optional[pd.Series] = None,
        
        # Switching costs
        customer_concentration: float = 0.3,
        contract_length_years: float = 1.0,
        recurring_revenue_pct: float = 0.0,
        customer_retention_rate: float = 0.8,
        
        # Network effects
        market_share: float = 0.1,
        market_share_trend: float = 0.0,
        user_growth_rate: float = 0.0,
        platform_indicator: bool = False,
        
        # Cost advantage
        operating_margin: float = 0.1,
        operating_margin_vs_peers: float = 0.0,
        scale_indicator: float = 0.5,
        vertical_integration: bool = False,
    ) -> MoatAssessment:
        """
        Comprehensive moat assessment
        """
        # 1. ROIC consistency (most important)
        roic_metrics = self.calculate_roic_consistency(roic_history, wacc)
        roic_score = roic_metrics['consistency_score']
        
        # 2. Pricing power
        if gross_margin_history is not None and revenue_growth_history is not None:
            pricing_score = self.calculate_pricing_power(
                gross_margin_history, revenue_growth_history
            )
        else:
            pricing_score = 50  # Neutral
        
        # 3. Switching costs
        switching_score = self.calculate_switching_costs(
            customer_concentration, contract_length_years,
            recurring_revenue_pct, customer_retention_rate
        )
        
        # 4. Network effects
        network_score = self.calculate_network_effects(
            market_share, market_share_trend, user_growth_rate, platform_indicator
        )
        
        # 5. Cost advantage
        cost_score = self.calculate_cost_advantage(
            operating_margin, operating_margin_vs_peers,
            scale_indicator, vertical_integration
        )
        
        # Weighted overall score
        # ROIC consistency is most important (40%)
        overall_score = (
            roic_score * 0.40 +
            pricing_score * 0.20 +
            switching_score * 0.15 +
            network_score * 0.15 +
            cost_score * 0.10
        )
        
        # Determine moat width
        if overall_score >= 75 and roic_metrics['years_above_threshold'] >= 10:
            moat_width = 'Wide'
        elif overall_score >= 55 and roic_metrics['years_above_threshold'] >= 5:
            moat_width = 'Narrow'
        else:
            moat_width = 'None'
        
        # Identify moat sources
        moat_sources = []
        if pricing_score >= 70:
            moat_sources.append('Pricing Power')
        if switching_score >= 70:
            moat_sources.append('Switching Costs')
        if network_score >= 70:
            moat_sources.append('Network Effects')
        if cost_score >= 70:
            moat_sources.append('Cost Advantage')
        
        return MoatAssessment(
            overall_score=overall_score,
            moat_width=moat_width,
            roic_consistency=roic_score,
            pricing_power=pricing_score,
            switching_costs=switching_score,
            network_effects=network_score,
            cost_advantage=cost_score,
            moat_sources=moat_sources
        )
