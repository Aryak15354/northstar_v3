"""
DCF Engine - Conservative Discounted Cash Flow valuation
Implements Buffett-style conservative DCF with margin of safety
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple
from dataclasses import dataclass


@dataclass
class DCFResult:
    """Container for DCF valuation result"""
    intrinsic_value: float
    intrinsic_value_per_share: float
    current_price: float
    margin_of_safety: float
    margin_of_safety_pct: float
    upside_potential: float
    valuation_grade: str
    assumptions: Dict[str, float]
    sensitivity: Dict[str, float]


class DCFEngine:
    """
    Conservative DCF Engine following Buffett principles
    
    Key features:
    1. Conservative growth assumptions
    2. Two-stage model (growth + terminal)
    3. ROIC-based growth sustainability
    4. Margin of safety requirement
    5. Sensitivity analysis
    """
    
    def __init__(self):
        self.risk_free_rate = 0.07  # 7% risk-free rate
        self.equity_risk_premium = 0.06  # 6% equity risk premium
        self.min_margin_of_safety = 0.30  # 30% minimum MOS
        self.gdp_growth_cap = 0.06  # 6% GDP growth cap
    
    def calculate_discount_rate(
        self,
        risk_free_rate: Optional[float] = None,
        beta: float = 1.0,
        size_premium: float = 0.0,
        quality_adjustment: float = 0.0
    ) -> float:
        """
        Calculate required return (discount rate)
        
        Required Return = Risk-Free Rate + Beta × ERP + Size Premium - Quality Adjustment
        """
        if risk_free_rate is None:
            risk_free_rate = self.risk_free_rate
        
        required_return = (
            risk_free_rate +
            beta * self.equity_risk_premium +
            size_premium -
            quality_adjustment
        )
        
        return max(0.08, required_return)  # Minimum 8% required return
    
    def estimate_sustainable_growth(
        self,
        historical_growth: float,
        roic: float,
        reinvestment_rate: float,
        industry_growth: float = 0.05
    ) -> float:
        """
        Estimate sustainable growth rate
        
        Sustainable Growth = min(
            Historical Growth,
            ROIC × Reinvestment Rate,
            GDP Growth Cap,
            Industry Growth × 1.5
        )
        """
        # ROIC-based growth
        roic_growth = roic * reinvestment_rate
        
        # Cap at GDP growth
        gdp_capped = min(historical_growth, self.gdp_growth_cap)
        
        # Industry growth with premium
        industry_capped = industry_growth * 1.5
        
        # Take conservative estimate
        sustainable_growth = min(
            gdp_capped,
            roic_growth,
            industry_capped
        )
        
        return max(0, sustainable_growth)
    
    def calculate_terminal_value(
        self,
        terminal_cash_flow: float,
        terminal_growth: float,
        discount_rate: float,
        roic: float
    ) -> float:
        """
        Calculate terminal value using Gordon Growth Model
        
        Terminal Value = Terminal CF × (1 + g) / (r - g)
        
        With ROIC-based sanity check
        """
        # Ensure terminal growth < discount rate
        terminal_growth = min(terminal_growth, discount_rate - 0.02)
        
        # Cap terminal growth based on ROIC
        # If ROIC is low, terminal growth should be low
        if roic < 0.12:
            terminal_growth = min(terminal_growth, 0.03)  # 3% max
        elif roic < 0.15:
            terminal_growth = min(terminal_growth, 0.04)  # 4% max
        
        # Gordon Growth Model
        if discount_rate <= terminal_growth:
            # Fallback to exit multiple
            terminal_value = terminal_cash_flow * 15  # 15x exit multiple
        else:
            terminal_value = (terminal_cash_flow * (1 + terminal_growth)) / (discount_rate - terminal_growth)
        
        return terminal_value
    
    def two_stage_dcf(
        self,
        # Current financials
        current_owner_earnings: float,
        
        # Growth assumptions
        growth_rate_stage1: float,
        growth_years_stage1: int,
        terminal_growth: float,
        
        # Discount rate
        discount_rate: float,
        
        # Quality metrics
        roic: float,
        reinvestment_rate: float,
        
        # Market data
        shares_outstanding: float,
        current_price: float,
        include_sensitivity: bool = True,
    ) -> DCFResult:
        """
        Two-stage DCF valuation
        
        Stage 1: Explicit forecast (5-10 years)
        Stage 2: Terminal value (perpetuity)
        """
        # Validate growth assumptions
        sustainable_growth = self.estimate_sustainable_growth(
            growth_rate_stage1, roic, reinvestment_rate
        )
        
        # Use more conservative growth
        growth_rate_stage1 = min(growth_rate_stage1, sustainable_growth)
        
        # Stage 1: Explicit forecast
        stage1_pv = 0
        cash_flows = []
        
        for year in range(1, growth_years_stage1 + 1):
            # Project cash flow
            cf = current_owner_earnings * ((1 + growth_rate_stage1) ** year)
            
            # Discount to present
            pv = cf / ((1 + discount_rate) ** year)
            stage1_pv += pv
            
            cash_flows.append({
                'year': year,
                'cash_flow': cf,
                'discount_factor': 1 / ((1 + discount_rate) ** year),
                'present_value': pv
            })
        
        # Terminal year cash flow
        terminal_cf = current_owner_earnings * ((1 + growth_rate_stage1) ** growth_years_stage1)
        
        # Stage 2: Terminal value
        terminal_value = self.calculate_terminal_value(
            terminal_cf, terminal_growth, discount_rate, roic
        )
        
        # Discount terminal value to present
        terminal_pv = terminal_value / ((1 + discount_rate) ** growth_years_stage1)
        
        # Total intrinsic value
        intrinsic_value = stage1_pv + terminal_pv
        
        # Per share
        if shares_outstanding > 0:
            intrinsic_value_per_share = intrinsic_value / shares_outstanding
        else:
            intrinsic_value_per_share = 0
        
        # Margin of safety
        if intrinsic_value_per_share > 0:
            margin_of_safety = intrinsic_value_per_share - current_price
            margin_of_safety_pct = margin_of_safety / intrinsic_value_per_share
            upside_potential = (intrinsic_value_per_share / current_price - 1) if current_price > 0 else 0
        else:
            margin_of_safety = 0
            margin_of_safety_pct = 0
            upside_potential = 0
        
        # Valuation grade
        if margin_of_safety_pct >= 0.40:
            grade = 'A'  # Excellent value
        elif margin_of_safety_pct >= 0.30:
            grade = 'B'  # Good value
        elif margin_of_safety_pct >= 0.20:
            grade = 'C'  # Fair value
        elif margin_of_safety_pct >= 0:
            grade = 'D'  # Fully valued
        else:
            grade = 'F'  # Overvalued
        
        # Assumptions
        assumptions = {
            'current_owner_earnings': current_owner_earnings,
            'growth_rate_stage1': growth_rate_stage1,
            'growth_years_stage1': growth_years_stage1,
            'terminal_growth': terminal_growth,
            'discount_rate': discount_rate,
            'roic': roic,
            'stage1_pv': stage1_pv,
            'terminal_pv': terminal_pv,
            'terminal_value': terminal_value
        }
        
        # Sensitivity analysis
        if include_sensitivity:
            sensitivity = self._calculate_sensitivity(
                current_owner_earnings,
                growth_rate_stage1,
                growth_years_stage1,
                terminal_growth,
                discount_rate,
                roic,
                reinvestment_rate,
                shares_outstanding,
            )
        else:
            sensitivity = {}
        
        return DCFResult(
            intrinsic_value=intrinsic_value,
            intrinsic_value_per_share=intrinsic_value_per_share,
            current_price=current_price,
            margin_of_safety=margin_of_safety,
            margin_of_safety_pct=margin_of_safety_pct,
            upside_potential=upside_potential,
            valuation_grade=grade,
            assumptions=assumptions,
            sensitivity=sensitivity
        )
    
    def _calculate_sensitivity(
        self,
        current_oe: float,
        growth: float,
        years: int,
        terminal_growth: float,
        discount_rate: float,
        roic: float,
        reinvestment_rate: float,
        shares: float
    ) -> Dict[str, float]:
        """
        Calculate sensitivity to key assumptions
        """
        base_dcf = self.two_stage_dcf(
            current_oe, growth, years, terminal_growth,
            discount_rate, roic, reinvestment_rate, shares, 0, include_sensitivity=False
        )
        base_value = base_dcf.intrinsic_value_per_share
        
        sensitivity = {}
        
        # Growth rate sensitivity (+/- 2%)
        if growth > 0.02:
            low_growth_dcf = self.two_stage_dcf(
                current_oe, growth - 0.02, years, terminal_growth,
                discount_rate, roic, reinvestment_rate, shares, 0, include_sensitivity=False
            )
            sensitivity['growth_minus_2pct'] = low_growth_dcf.intrinsic_value_per_share / base_value - 1

        high_growth_dcf = self.two_stage_dcf(
            current_oe, growth + 0.02, years, terminal_growth,
            discount_rate, roic, reinvestment_rate, shares, 0, include_sensitivity=False
        )
        sensitivity['growth_plus_2pct'] = high_growth_dcf.intrinsic_value_per_share / base_value - 1
        
        # Discount rate sensitivity (+/- 1%)
        if discount_rate > 0.01:
            low_dr_dcf = self.two_stage_dcf(
                current_oe, growth, years, terminal_growth,
                discount_rate - 0.01, roic, reinvestment_rate, shares, 0, include_sensitivity=False
            )
            sensitivity['discount_minus_1pct'] = low_dr_dcf.intrinsic_value_per_share / base_value - 1

        high_dr_dcf = self.two_stage_dcf(
            current_oe, growth, years, terminal_growth,
            discount_rate + 0.01, roic, reinvestment_rate, shares, 0, include_sensitivity=False
        )
        sensitivity['discount_plus_1pct'] = high_dr_dcf.intrinsic_value_per_share / base_value - 1
        
        return sensitivity
    
    def buffett_style_valuation(
        self,
        owner_earnings: float,
        roic_10y_avg: float,
        revenue_growth_5y: float,
        shares_outstanding: float,
        current_price: float,
        sector: str = 'Unknown',
        quality_score: float = 50
    ) -> DCFResult:
        """
        Simplified Buffett-style valuation with conservative assumptions
        """
        # Conservative growth estimate
        # Cap at 15% even for high-growth companies
        growth_stage1 = min(0.15, revenue_growth_5y * 0.7)  # 70% of historical
        
        # Shorter growth period for lower quality
        if quality_score >= 80:
            growth_years = 10
        elif quality_score >= 60:
            growth_years = 7
        else:
            growth_years = 5
        
        # Terminal growth based on ROIC
        if roic_10y_avg >= 0.20:
            terminal_growth = 0.05  # 5% perpetual
        elif roic_10y_avg >= 0.15:
            terminal_growth = 0.04  # 4% perpetual
        else:
            terminal_growth = 0.03  # 3% perpetual (GDP growth)
        
        # Discount rate based on quality
        quality_adjustment = (quality_score - 50) / 1000  # Max 5% adjustment
        discount_rate = self.calculate_discount_rate(
            quality_adjustment=quality_adjustment
        )
        
        # Reinvestment rate estimate
        if roic_10y_avg > 0:
            reinvestment_rate = growth_stage1 / roic_10y_avg
        else:
            reinvestment_rate = 0.5
        
        return self.two_stage_dcf(
            current_owner_earnings=owner_earnings,
            growth_rate_stage1=growth_stage1,
            growth_years_stage1=growth_years,
            terminal_growth=terminal_growth,
            discount_rate=discount_rate,
            roic=roic_10y_avg,
            reinvestment_rate=reinvestment_rate,
            shares_outstanding=shares_outstanding,
            current_price=current_price
        )
