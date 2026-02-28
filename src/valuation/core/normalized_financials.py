"""
Financial Normalizer - Handles accounting differences across sectors
Adjusts for revenue recognition, capitalization policies, and reporting standards
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional
from dataclasses import dataclass


@dataclass
class FinancialAdjustments:
    """Container for financial adjustments"""
    adjusted_revenue: float
    adjusted_ebit: float
    adjusted_ebitda: float
    adjusted_capex: float
    maintenance_capex: float
    growth_capex: float
    adjusted_working_capital: float
    adjustments_made: Dict[str, str]


class FinancialNormalizer:
    """
    Normalizes financial statements across different accounting treatments
    
    Key adjustments:
    1. Revenue recognition differences (SaaS, construction, auto)
    2. R&D capitalization vs expensing
    3. Lease accounting (IFRS 16 impact)
    4. Depreciation policy normalization
    5. Working capital manipulation detection
    """
    
    def __init__(self):
        self.adjustments_log = []
    
    def normalize_financials(
        self,
        ticker: str,
        sector: str,
        revenue: float,
        ebit: float,
        ebitda: float,
        capex: float,
        depreciation: float,
        amortization: float,
        rd_expense: float,
        capitalized_rd: float,
        rd_amortization: float,
        receivables: float,
        inventory: float,
        payables: float,
        deferred_revenue: float,
        lease_liabilities: float,
        gross_ppe: float,
        **kwargs
    ) -> FinancialAdjustments:
        """
        Normalize financial statements with sector-aware adjustments
        """
        adjustments = {}
        
        # 1. Adjust for R&D capitalization
        if capitalized_rd > 0:
            # Expense capitalized R&D, add back amortization
            adjusted_ebit = ebit - capitalized_rd + rd_amortization
            adjustments['rd_adjustment'] = f"Expensed ${capitalized_rd/1e6:.1f}M capitalized R&D"
        else:
            adjusted_ebit = ebit
        
        # 2. Adjust EBITDA for lease accounting (IFRS 16)
        if lease_liabilities > 0:
            # Approximate lease expense from liability
            implied_lease_expense = lease_liabilities * 0.08  # Assume 8% rate
            adjusted_ebitda = ebitda - implied_lease_expense
            adjustments['lease_adjustment'] = f"Adjusted for ${implied_lease_expense/1e6:.1f}M lease expense"
        else:
            adjusted_ebitda = ebitda
        
        # 3. Revenue recognition adjustments
        adjusted_revenue = self._adjust_revenue_recognition(
            revenue, receivables, deferred_revenue, sector, adjustments
        )
        
        # 4. Separate maintenance vs growth capex
        maintenance_capex, growth_capex = self._split_capex(
            capex, depreciation, revenue, sector
        )
        adjustments['capex_split'] = f"Maintenance: ${maintenance_capex/1e6:.1f}M, Growth: ${growth_capex/1e6:.1f}M"
        
        # 5. Normalize depreciation if outlier
        adjusted_capex = self._normalize_depreciation_policy(
            capex, depreciation, gross_ppe, sector, adjustments
        )
        
        # 6. Working capital adjustments
        adjusted_wc = self._calculate_adjusted_working_capital(
            receivables, inventory, payables, revenue, sector, adjustments
        )
        
        return FinancialAdjustments(
            adjusted_revenue=adjusted_revenue,
            adjusted_ebit=adjusted_ebit,
            adjusted_ebitda=adjusted_ebitda,
            adjusted_capex=adjusted_capex,
            maintenance_capex=maintenance_capex,
            growth_capex=growth_capex,
            adjusted_working_capital=adjusted_wc,
            adjustments_made=adjustments
        )
    
    def _adjust_revenue_recognition(
        self,
        revenue: float,
        receivables: float,
        deferred_revenue: float,
        sector: str,
        adjustments: Dict
    ) -> float:
        """
        Adjust revenue for recognition timing differences
        """
        # Check for receivables growing faster than revenue (red flag)
        receivables_days = (receivables / revenue) * 365 if revenue > 0 else 0
        
        # Sector-specific thresholds
        normal_receivables_days = {
            'Technology': 60,
            'Healthcare': 70,
            'Industrials': 75,
            'Consumer': 45,
            'Financials': 30,
        }
        
        threshold = normal_receivables_days.get(sector, 60)
        
        if receivables_days > threshold * 1.5:
            # Potential revenue stuffing - adjust down
            adjustment_factor = threshold / receivables_days
            adjusted_revenue = revenue * adjustment_factor
            adjustments['revenue_quality'] = f"Adjusted for high receivables days ({receivables_days:.0f} vs {threshold})"
            return adjusted_revenue
        
        # Adjust for deferred revenue changes (SaaS, subscriptions)
        if deferred_revenue > revenue * 0.1:  # Material deferred revenue
            # This is actually good - revenue is more predictable
            adjustments['deferred_revenue'] = f"High deferred revenue: ${deferred_revenue/1e6:.1f}M (quality signal)"
        
        return revenue
    
    def _split_capex(
        self,
        capex: float,
        depreciation: float,
        revenue: float,
        sector: str
    ) -> tuple:
        """
        Split capex into maintenance and growth components
        
        Maintenance capex approximation:
        - Asset-heavy: ~100% of depreciation
        - Asset-light: ~70% of depreciation
        """
        if capex <= 0 or depreciation <= 0:
            return 0, capex
        
        # Sector-specific maintenance ratios
        maintenance_ratios = {
            'Utilities': 1.0,
            'Industrials': 0.95,
            'Materials': 0.90,
            'Energy': 0.95,
            'Technology': 0.70,
            'Healthcare': 0.75,
            'Consumer': 0.80,
        }
        
        ratio = maintenance_ratios.get(sector, 0.85)
        maintenance_capex = depreciation * ratio
        growth_capex = max(0, capex - maintenance_capex)
        
        return maintenance_capex, growth_capex
    
    def _normalize_depreciation_policy(
        self,
        capex: float,
        depreciation: float,
        gross_ppe: float,
        sector: str,
        adjustments: Dict
    ) -> float:
        """
        Check if depreciation policy is aggressive or conservative
        """
        if gross_ppe <= 0:
            return capex
        
        depreciation_rate = depreciation / gross_ppe
        
        # Sector-specific normal ranges
        normal_dep_rates = {
            'Technology': (0.15, 0.25),
            'Industrials': (0.08, 0.15),
            'Utilities': (0.04, 0.08),
            'Consumer': (0.10, 0.18),
        }
        
        low, high = normal_dep_rates.get(sector, (0.08, 0.15))
        
        if depreciation_rate < low:
            adjustments['depreciation'] = f"Conservative depreciation ({depreciation_rate:.1%} vs {low:.1%}-{high:.1%})"
        elif depreciation_rate > high:
            adjustments['depreciation'] = f"Aggressive depreciation ({depreciation_rate:.1%} vs {low:.1%}-{high:.1%})"
        
        return capex
    
    def _calculate_adjusted_working_capital(
        self,
        receivables: float,
        inventory: float,
        payables: float,
        revenue: float,
        sector: str,
        adjustments: Dict
    ) -> float:
        """
        Calculate working capital with quality adjustments
        """
        # Basic working capital
        wc = receivables + inventory - payables
        
        # Check for manipulation
        if revenue > 0:
            receivables_days = (receivables / revenue) * 365
            inventory_days = (inventory / revenue) * 365 if inventory > 0 else 0
            payables_days = (payables / revenue) * 365
            
            cash_conversion_cycle = receivables_days + inventory_days - payables_days
            
            # Sector benchmarks
            normal_ccc = {
                'Technology': 30,
                'Consumer': 45,
                'Industrials': 60,
                'Healthcare': 50,
            }
            
            benchmark = normal_ccc.get(sector, 50)
            
            if cash_conversion_cycle > benchmark * 1.5:
                adjustments['working_capital'] = f"High CCC: {cash_conversion_cycle:.0f} days vs {benchmark} benchmark"
            elif cash_conversion_cycle < 0:
                adjustments['working_capital'] = f"Negative CCC: {cash_conversion_cycle:.0f} days (strong position)"
        
        return wc
    
    def normalize_dataframe(self, df: pd.DataFrame, sector_col: str = 'sector') -> pd.DataFrame:
        """
        Normalize an entire dataframe of financial data
        """
        results = []
        
        for idx, row in df.iterrows():
            try:
                adj = self.normalize_financials(
                    ticker=row.get('ticker', ''),
                    sector=row.get(sector_col, 'Unknown'),
                    revenue=row.get('revenue', 0),
                    ebit=row.get('ebit', 0),
                    ebitda=row.get('ebitda', 0),
                    capex=row.get('capex', 0),
                    depreciation=row.get('depreciation', 0),
                    amortization=row.get('amortization', 0),
                    rd_expense=row.get('rd_expense', 0),
                    capitalized_rd=row.get('capitalized_rd', 0),
                    rd_amortization=row.get('rd_amortization', 0),
                    receivables=row.get('receivables', 0),
                    inventory=row.get('inventory', 0),
                    payables=row.get('payables', 0),
                    deferred_revenue=row.get('deferred_revenue', 0),
                    lease_liabilities=row.get('lease_liabilities', 0),
                    gross_ppe=row.get('gross_ppe', 0),
                )
                
                results.append({
                    'ticker': row.get('ticker', ''),
                    'adjusted_revenue': adj.adjusted_revenue,
                    'adjusted_ebit': adj.adjusted_ebit,
                    'adjusted_ebitda': adj.adjusted_ebitda,
                    'adjusted_capex': adj.adjusted_capex,
                    'maintenance_capex': adj.maintenance_capex,
                    'growth_capex': adj.growth_capex,
                    'adjusted_working_capital': adj.adjusted_working_capital,
                    'adjustments_count': len(adj.adjustments_made),
                })
            except Exception as e:
                print(f"Error normalizing {row.get('ticker', 'unknown')}: {e}")
                continue
        
        return pd.DataFrame(results)
