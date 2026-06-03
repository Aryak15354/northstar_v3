"""
Adjusted Metrics Calculator
Computes forensically-adjusted valuation metrics accounting for distortions
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional
from dataclasses import dataclass


@dataclass
class AdjustedMetrics:
    """Container for adjusted valuation metrics"""
    adjusted_roic: float
    adjusted_roe: float
    adjusted_fcf: float
    fcf_conversion: float
    ev_adjusted: float
    owner_earnings: float
    metrics: Dict[str, float]


class AdjustedMetricsCalculator:
    """
    Calculate adjusted valuation metrics that account for:
    1. R&D capitalization distortions
    2. Lease accounting (IFRS 16)
    3. Working capital quality
    4. Cash flow vs earnings quality
    """
    
    def __init__(self):
        self.tax_rate_default = 0.25  # 25% default tax rate
    
    def calculate_adjusted_roic(
        self,
        adjusted_ebit: float,
        equity: float,
        debt: float,
        excess_cash: float,
        capitalized_rd: float,
        tax_rate: Optional[float] = None
    ) -> float:
        """
        Calculate R&D-adjusted ROIC
        
        ROIC = NOPAT / Invested Capital
        where:
        - NOPAT = Adjusted EBIT × (1 - Tax Rate)
        - Invested Capital = Equity + Debt - Excess Cash + Capitalized R&D
        """
        if tax_rate is None:
            tax_rate = self.tax_rate_default
        
        nopat = adjusted_ebit * (1 - tax_rate)
        invested_capital = equity + debt - excess_cash + capitalized_rd
        
        if invested_capital <= 0:
            return 0.0
        
        return nopat / invested_capital
    
    def calculate_adjusted_roe(
        self,
        net_income: float,
        equity: float,
        capitalized_rd: float,
        one_time_items: float = 0
    ) -> float:
        """
        Calculate adjusted ROE removing one-time items
        
        ROE = (Net Income - One-Time Items) / (Equity + Capitalized R&D)
        """
        adjusted_ni = net_income - one_time_items
        adjusted_equity = equity + capitalized_rd
        
        if adjusted_equity <= 0:
            return 0.0
        
        return adjusted_ni / adjusted_equity
    
    def calculate_fcf_conversion(
        self,
        operating_cash_flow: float,
        capex: float,
        net_income: float
    ) -> tuple:
        """
        Calculate Free Cash Flow and FCF Conversion
        
        FCF = Operating Cash Flow - Capex
        FCF Conversion = FCF / Net Income
        
        Returns: (fcf, fcf_conversion)
        """
        fcf = operating_cash_flow - capex
        
        if net_income <= 0:
            fcf_conversion = 0.0
        else:
            fcf_conversion = fcf / net_income
        
        return fcf, fcf_conversion
    
    def calculate_lease_adjusted_ev(
        self,
        market_cap: float,
        debt: float,
        cash: float,
        lease_liabilities: float,
        minority_interest: float = 0
    ) -> float:
        """
        Calculate lease-adjusted Enterprise Value
        
        EV = Market Cap + Debt + Lease Liabilities + Minority Interest - Cash
        """
        ev = market_cap + debt + lease_liabilities + minority_interest - cash
        return max(0, ev)  # EV cannot be negative
    
    def calculate_owner_earnings(
        self,
        net_income: float,
        depreciation: float,
        amortization: float,
        maintenance_capex: float,
        working_capital_increase: float,
        one_time_items: float = 0
    ) -> float:
        """
        Calculate Buffett's Owner Earnings
        
        Owner Earnings = Net Income
                       + Depreciation & Amortization
                       - Maintenance Capex
                       - Working Capital Increase
                       - One-Time Items
        """
        owner_earnings = (
            net_income
            + depreciation
            + amortization
            - maintenance_capex
            - working_capital_increase
            - one_time_items
        )
        
        return owner_earnings
    
    def calculate_all_metrics(
        self,
        # Income statement
        revenue: float,
        adjusted_ebit: float,
        net_income: float,
        depreciation: float,
        amortization: float,
        
        # Balance sheet
        equity: float,
        debt: float,
        cash: float,
        excess_cash: float,
        lease_liabilities: float,
        capitalized_rd: float,
        
        # Cash flow
        operating_cash_flow: float,
        capex: float,
        maintenance_capex: float,
        
        # Working capital
        working_capital_increase: float,
        
        # Market data
        market_cap: float,
        
        # Optional
        tax_rate: Optional[float] = None,
        one_time_items: float = 0,
        minority_interest: float = 0
    ) -> AdjustedMetrics:
        """
        Calculate all adjusted metrics at once
        """
        # ROIC
        roic = self.calculate_adjusted_roic(
            adjusted_ebit, equity, debt, excess_cash, capitalized_rd, tax_rate
        )
        
        # ROE
        roe = self.calculate_adjusted_roe(
            net_income, equity, capitalized_rd, one_time_items
        )
        
        # FCF and conversion
        fcf, fcf_conversion = self.calculate_fcf_conversion(
            operating_cash_flow, capex, net_income
        )
        
        # Adjusted EV
        ev_adjusted = self.calculate_lease_adjusted_ev(
            market_cap, debt, cash, lease_liabilities, minority_interest
        )
        
        # Owner Earnings
        owner_earnings = self.calculate_owner_earnings(
            net_income, depreciation, amortization,
            maintenance_capex, working_capital_increase, one_time_items
        )
        
        # Additional metrics
        metrics = {
            'roic': roic,
            'roe': roe,
            'fcf': fcf,
            'fcf_conversion': fcf_conversion,
            'ev_adjusted': ev_adjusted,
            'owner_earnings': owner_earnings,
            'ev_to_ebit': ev_adjusted / adjusted_ebit if adjusted_ebit > 0 else 0,
            'ev_to_owner_earnings': ev_adjusted / owner_earnings if owner_earnings > 0 else 0,
            'fcf_yield': fcf / market_cap if market_cap > 0 else 0,
            'owner_earnings_yield': owner_earnings / market_cap if market_cap > 0 else 0,
        }
        
        return AdjustedMetrics(
            adjusted_roic=roic,
            adjusted_roe=roe,
            adjusted_fcf=fcf,
            fcf_conversion=fcf_conversion,
            ev_adjusted=ev_adjusted,
            owner_earnings=owner_earnings,
            metrics=metrics
        )
    
    def calculate_mid_cycle_earnings(
        self,
        ebit_history: pd.Series,
        method: str = 'median'
    ) -> float:
        """
        Calculate mid-cycle earnings for cyclical industries
        
        Args:
            ebit_history: Historical EBIT series (10 years recommended)
            method: 'median', 'mean', or 'trimmed_mean'
        """
        if len(ebit_history) < 3:
            return ebit_history.iloc[-1] if len(ebit_history) > 0 else 0
        
        if method == 'median':
            return ebit_history.median()
        elif method == 'mean':
            return ebit_history.mean()
        elif method == 'trimmed_mean':
            # Remove top and bottom 10%
            sorted_ebit = ebit_history.sort_values()
            trim_count = int(len(sorted_ebit) * 0.1)
            if trim_count > 0:
                trimmed = sorted_ebit.iloc[trim_count:-trim_count]
                return trimmed.mean()
            return sorted_ebit.mean()
        else:
            return ebit_history.median()
    
    def calculate_metrics_dataframe(
        self,
        df: pd.DataFrame,
        required_cols: Optional[list] = None
    ) -> pd.DataFrame:
        """
        Calculate adjusted metrics for entire dataframe
        """
        results = []
        
        for idx, row in df.iterrows():
            try:
                metrics = self.calculate_all_metrics(
                    revenue=row.get('revenue', 0),
                    adjusted_ebit=row.get('adjusted_ebit', row.get('ebit', 0)),
                    net_income=row.get('net_income', 0),
                    depreciation=row.get('depreciation', 0),
                    amortization=row.get('amortization', 0),
                    equity=row.get('equity', 0),
                    debt=row.get('total_debt', 0),
                    cash=row.get('cash', 0),
                    excess_cash=row.get('excess_cash', row.get('cash', 0) * 0.5),
                    lease_liabilities=row.get('lease_liabilities', 0),
                    capitalized_rd=row.get('capitalized_rd', 0),
                    operating_cash_flow=row.get('operating_cash_flow', 0),
                    capex=row.get('capex', 0),
                    maintenance_capex=row.get('maintenance_capex', row.get('capex', 0) * 0.7),
                    working_capital_increase=row.get('working_capital_increase', 0),
                    market_cap=row.get('market_cap', 0),
                    tax_rate=row.get('tax_rate', None),
                    one_time_items=row.get('one_time_items', 0),
                    minority_interest=row.get('minority_interest', 0),
                )
                
                result = {
                    'ticker': row.get('ticker', ''),
                    **metrics.metrics
                }
                results.append(result)
                
            except Exception as e:
                print(f"Error calculating metrics for {row.get('ticker', 'unknown')}: {e}")
                continue
        
        return pd.DataFrame(results)
