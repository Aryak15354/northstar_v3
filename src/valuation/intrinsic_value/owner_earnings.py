"""
Owner Earnings Calculator
Implements Warren Buffett's concept of owner earnings
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional
from dataclasses import dataclass


@dataclass
class OwnerEarningsResult:
    """Container for owner earnings calculation"""
    owner_earnings: float
    owner_earnings_per_share: float
    owner_earnings_yield: float
    components: Dict[str, float]
    quality_score: float


class OwnerEarningsCalculator:
    """
    Calculate Buffett's Owner Earnings
    
    Owner Earnings = Net Income
                   + Depreciation & Amortization
                   - Maintenance Capex
                   - Working Capital Increase
                   - One-Time Items
    
    This represents the true cash that owners can extract from the business
    """
    
    def __init__(self):
        self.maintenance_capex_ratio = 0.70  # Default: 70% of total capex
    
    def estimate_maintenance_capex(
        self,
        total_capex: float,
        depreciation: float,
        revenue_growth: float,
        sector: str = 'Unknown'
    ) -> float:
        """
        Estimate maintenance capex vs growth capex
        
        Methods:
        1. Depreciation-based: Maintenance ≈ Depreciation
        2. Growth-adjusted: Higher growth = more growth capex
        3. Sector-adjusted: Asset-heavy sectors have higher maintenance
        """
        # Sector-specific maintenance ratios
        sector_ratios = {
            'Utilities': 1.0,
            'Industrials': 0.90,
            'Materials': 0.85,
            'Energy': 0.90,
            'Technology': 0.60,
            'Healthcare': 0.65,
            'Consumer': 0.75,
            'Financials': 0.50,
        }
        
        base_ratio = sector_ratios.get(sector, 0.75)
        
        # Adjust for growth
        # High growth companies have more growth capex
        if revenue_growth > 0.20:  # 20%+ growth
            growth_adjustment = 0.85
        elif revenue_growth > 0.10:  # 10-20% growth
            growth_adjustment = 0.90
        else:
            growth_adjustment = 1.0
        
        adjusted_ratio = base_ratio * growth_adjustment
        
        # Use depreciation as baseline, but cap at total capex
        maintenance_estimate = min(
            total_capex,
            depreciation * adjusted_ratio
        )
        
        return maintenance_estimate
    
    def calculate_working_capital_increase(
        self,
        current_wc: float,
        prior_wc: float,
        revenue: float,
        revenue_prior: float
    ) -> float:
        """
        Calculate working capital increase adjusted for growth
        
        Only penalize if WC is growing faster than revenue
        """
        wc_increase = current_wc - prior_wc
        
        # Adjust for revenue growth
        if revenue_prior > 0:
            revenue_growth = (revenue - revenue_prior) / revenue_prior
            expected_wc_increase = prior_wc * revenue_growth
            
            # Only penalize excess WC increase
            excess_wc_increase = max(0, wc_increase - expected_wc_increase)
            return excess_wc_increase
        
        return max(0, wc_increase)  # Only penalize increases
    
    def identify_one_time_items(
        self,
        net_income: float,
        operating_income: float,
        interest_expense: float,
        tax_expense: float,
        other_income: float,
        restructuring_charges: float = 0,
        impairment_charges: float = 0,
        gain_on_sale: float = 0
    ) -> float:
        """
        Identify and sum one-time items to remove from earnings
        """
        one_time_items = (
            restructuring_charges +
            impairment_charges -
            gain_on_sale +
            abs(other_income) * 0.5  # Assume 50% of other income is non-recurring
        )
        
        return one_time_items
    
    def calculate_owner_earnings(
        self,
        # Income statement
        net_income: float,
        depreciation: float,
        amortization: float,
        
        # Capex
        total_capex: float,
        maintenance_capex: Optional[float] = None,
        
        # Working capital
        current_wc: float = 0,
        prior_wc: float = 0,
        
        # Revenue (for adjustments)
        revenue: float = 0,
        revenue_prior: float = 0,
        revenue_growth: float = 0,
        
        # One-time items
        restructuring_charges: float = 0,
        impairment_charges: float = 0,
        gain_on_sale: float = 0,
        other_income: float = 0,
        
        # Market data
        shares_outstanding: float = 0,
        market_cap: float = 0,
        
        # Sector
        sector: str = 'Unknown'
    ) -> OwnerEarningsResult:
        """
        Calculate comprehensive owner earnings
        """
        # 1. Estimate maintenance capex if not provided
        if maintenance_capex is None:
            maintenance_capex = self.estimate_maintenance_capex(
                total_capex, depreciation, revenue_growth, sector
            )
        
        # 2. Calculate working capital increase
        wc_increase = self.calculate_working_capital_increase(
            current_wc, prior_wc, revenue, revenue_prior
        )
        
        # 3. Identify one-time items
        one_time = self.identify_one_time_items(
            net_income, 0, 0, 0, other_income,
            restructuring_charges, impairment_charges, gain_on_sale
        )
        
        # 4. Calculate owner earnings
        owner_earnings = (
            net_income +
            depreciation +
            amortization -
            maintenance_capex -
            wc_increase -
            one_time
        )
        
        # 5. Per share metrics
        if shares_outstanding > 0:
            owner_earnings_per_share = owner_earnings / shares_outstanding
        else:
            owner_earnings_per_share = 0
        
        # 6. Yield
        if market_cap > 0:
            owner_earnings_yield = owner_earnings / market_cap
        else:
            owner_earnings_yield = 0
        
        # 7. Quality score
        # Higher quality if:
        # - Owner earnings > net income (good cash generation)
        # - Low maintenance capex relative to depreciation
        # - Minimal working capital needs
        quality_factors = []
        
        if net_income > 0:
            oe_to_ni_ratio = owner_earnings / net_income
            quality_factors.append(min(100, max(0, oe_to_ni_ratio * 100)))
        else:
            quality_factors.append(50)
        
        if depreciation > 0:
            capex_efficiency = 1 - (maintenance_capex / (depreciation + 1))
            quality_factors.append(max(0, capex_efficiency * 100))
        else:
            quality_factors.append(50)
        
        if revenue > 0:
            wc_efficiency = 1 - (wc_increase / revenue)
            quality_factors.append(max(0, min(100, wc_efficiency * 100)))
        else:
            quality_factors.append(50)
        
        quality_score = np.mean(quality_factors)
        
        # Components breakdown
        components = {
            'net_income': net_income,
            'depreciation': depreciation,
            'amortization': amortization,
            'maintenance_capex': -maintenance_capex,
            'growth_capex': -(total_capex - maintenance_capex),
            'wc_increase': -wc_increase,
            'one_time_items': -one_time,
            'owner_earnings': owner_earnings
        }
        
        return OwnerEarningsResult(
            owner_earnings=owner_earnings,
            owner_earnings_per_share=owner_earnings_per_share,
            owner_earnings_yield=owner_earnings_yield,
            components=components,
            quality_score=quality_score
        )
    
    def calculate_normalized_owner_earnings(
        self,
        owner_earnings_history: pd.Series,
        method: str = 'median'
    ) -> float:
        """
        Calculate normalized owner earnings for cyclical businesses
        
        Args:
            owner_earnings_history: Historical owner earnings
            method: 'median', 'mean', or 'trimmed_mean'
        """
        if len(owner_earnings_history) < 3:
            return owner_earnings_history.iloc[-1] if len(owner_earnings_history) > 0 else 0
        
        if method == 'median':
            return owner_earnings_history.median()
        elif method == 'mean':
            return owner_earnings_history.mean()
        elif method == 'trimmed_mean':
            sorted_oe = owner_earnings_history.sort_values()
            trim_count = int(len(sorted_oe) * 0.1)
            if trim_count > 0:
                trimmed = sorted_oe.iloc[trim_count:-trim_count]
                return trimmed.mean()
            return sorted_oe.mean()
        else:
            return owner_earnings_history.median()
