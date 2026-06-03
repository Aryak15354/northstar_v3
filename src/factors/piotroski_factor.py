"""
Piotroski F-Score Factor (Piotroski, 2000)

Nine binary tests of fundamental financial health (range: 0-9):

PROFITABILITY (4 tests):
F1: ROA > 0                         (positive return on assets)
F2: Operating Cash Flow > 0         (positive cash generation)
F3: ROA_t > ROA_{t-1}               (improving profitability)
F4: Accruals: OCF/Assets > ROA      (cash quality of earnings)

LEVERAGE/LIQUIDITY (3 tests):
F5: Long-term debt ratio_t < Long-term debt ratio_{t-1}   (decreasing leverage)
F6: Current ratio_t > Current ratio_{t-1}                  (improving liquidity)
F7: No new shares issued in the year                       (no dilution)

OPERATING EFFICIENCY (2 tests):
F8: Gross margin_t > Gross margin_{t-1}                    (improving margins)
F9: Asset turnover_t > Asset turnover_{t-1}                (improving asset use)

PIT COMPLIANCE IS CRITICAL:
Fundamental data has a 60-90 day reporting lag. The fundamental_loader
handles this via reporting_lag_days. Always call through the registry.

Output: PIOTROSKI_raw = integer score 0-9
High score (8-9) = fundamentally strong = positive signal
"""

from datetime import datetime
import pandas as pd
import numpy as np
import logging

from .base_factor import BaseFactor

logger = logging.getLogger(__name__)


class PiotroskiFactor(BaseFactor):
    """Piotroski F-Score factor implementation."""
    
    FACTOR_NAME = "piotroski"
    FACTOR_FAMILY = "QUALITY"
    LOOKAHEAD_SAFE = True
    
    def _compute_raw(self, as_of_date: datetime, tickers: list) -> pd.Series:
        """
        Compute Piotroski F-Score for each ticker using PIT-compliant fundamentals.
        """
        fundamentals = self._registry.fundamentals.get_factor_financials(
            as_of_date=as_of_date,
            tickers=tickers,
            frequency='annual',
            periods=2,
            reporting_lag_days=self._factor_config.get('reporting_lag_days'),
        )

        results = {}
        for ticker in tickers:
            try:
                fin = fundamentals.get(ticker, {})
                current = fin.get('current', {})
                prior = fin.get('prior', {})
                if not current or not prior:
                    results[ticker] = np.nan
                    continue
                score = self._compute_fscore(ticker, current, prior)
                results[ticker] = float(score) if not np.isnan(score) else np.nan
            except Exception as e:
                logger.debug(f"Piotroski failed for {ticker}: {e}")
                results[ticker] = np.nan

        return pd.Series(results, index=tickers)
    
    def _compute_fscore(self, ticker: str, curr: dict, prior: dict) -> float:
        """
        Compute the nine-component F-Score. Each component is 0 or 1.
        Returns integer 0-9, or NaN if insufficient data.
        """
        # Helper: safe division
        def safe_div(num, denom, default=np.nan):
            if denom is None or denom == 0 or pd.isna(denom):
                return default
            if num is None or pd.isna(num):
                return default
            try:
                return float(num) / float(denom)
            except (ValueError, TypeError):
                return default
        
        score = 0
        tests_available = 0
        
        # Extract required fields (handle various column name formats)
        def get_field(data, *names):
            for name in names:
                if name in data and data[name] is not None:
                    return data[name]
                # Try lowercase
                lower_name = name.lower()
                for key in data.keys():
                    if key.lower() == lower_name:
                        return data[key]
            return None
        
        # --- PROFITABILITY ---
        
        # F1: ROA > 0
        net_profit = get_field(curr, 'net_profit', 'Net Profit', 'net_income', 'Net Income')
        total_assets = get_field(curr, 'total_assets', 'Total Assets', 'assets', 'Assets')
        roa_curr = safe_div(net_profit, total_assets)
        
        if not np.isnan(roa_curr):
            score += int(roa_curr > 0)
            tests_available += 1
        
        # F2: Operating Cash Flow > 0
        ocf_curr = get_field(curr, 'cash_from_operations', 'Operating Cash Flow', 
                            'operating_cash_flow', 'CFO')
        if ocf_curr is not None and not np.isnan(ocf_curr):
            score += int(ocf_curr > 0)
            tests_available += 1
        
        # F3: ROA improving
        net_profit_prior = get_field(prior, 'net_profit', 'Net Profit', 'net_income')
        total_assets_prior = get_field(prior, 'total_assets', 'Total Assets', 'assets')
        roa_prior = safe_div(net_profit_prior, total_assets_prior)
        
        if not np.isnan(roa_curr) and not np.isnan(roa_prior):
            score += int(roa_curr > roa_prior)
            tests_available += 1
        
        # F4: Accruals — OCF/Assets > ROA
        if ocf_curr is not None and total_assets is not None and not np.isnan(roa_curr):
            ocf_roa = safe_div(ocf_curr, total_assets)
            if not np.isnan(ocf_roa):
                score += int(ocf_roa > roa_curr)
                tests_available += 1
        
        # --- LEVERAGE / LIQUIDITY ---
        
        # F5: Leverage decreasing
        debt_curr = get_field(curr, 'total_borrowings', 'Total Borrowings', 
                             'long_term_debt', 'Long Term Debt', 'total_debt')
        debt_prior = get_field(prior, 'total_borrowings', 'Total Borrowings',
                              'long_term_debt', 'Long Term Debt', 'total_debt')
        
        lev_curr = safe_div(debt_curr, total_assets)
        lev_prior = safe_div(debt_prior, total_assets_prior)
        
        if not np.isnan(lev_curr) and not np.isnan(lev_prior):
            score += int(lev_curr < lev_prior)
            tests_available += 1
        
        # F6: Current ratio improving
        ca_curr = get_field(curr, 'current_assets', 'Current Assets')
        cl_curr = get_field(curr, 'current_liabilities', 'Current Liabilities')
        ca_prior = get_field(prior, 'current_assets', 'Current Assets')
        cl_prior = get_field(prior, 'current_liabilities', 'Current Liabilities')
        
        cr_curr = safe_div(ca_curr, cl_curr)
        cr_prior = safe_div(ca_prior, cl_prior)
        
        if not np.isnan(cr_curr) and not np.isnan(cr_prior):
            score += int(cr_curr > cr_prior)
            tests_available += 1
        
        # F7: No dilution
        shares_curr = get_field(curr, 'shares_outstanding', 'Shares Outstanding',
                               'equity_shares', 'Equity Shares')
        shares_prior = get_field(prior, 'shares_outstanding', 'Shares Outstanding',
                                'equity_shares', 'Equity Shares')
        
        if shares_curr is not None and shares_prior is not None and shares_prior > 0:
            try:
                dilution_ratio = float(shares_curr) / float(shares_prior)
                score += int(dilution_ratio <= 1.02)  # Allow 2% tolerance
                tests_available += 1
            except (ValueError, TypeError):
                pass
        
        # --- OPERATING EFFICIENCY ---
        
        # F8: Gross margin improving
        revenue_curr = get_field(curr, 'revenue', 'Revenue', 'sales', 'Sales', 'total_revenue')
        revenue_prior = get_field(prior, 'revenue', 'Revenue', 'sales', 'Sales', 'total_revenue')
        
        cogs_curr = get_field(curr, 'cost_of_goods_sold', 'Cost of Goods Sold',
                             'cogs', 'COGS', 'total_expenses')
        cogs_prior = get_field(prior, 'cost_of_goods_sold', 'Cost of Goods Sold',
                              'cogs', 'COGS', 'total_expenses')
        
        gm_curr = safe_div(float(revenue_curr or 0) - float(cogs_curr or 0), revenue_curr)
        gm_prior = safe_div(float(revenue_prior or 0) - float(cogs_prior or 0), revenue_prior)
        
        if not np.isnan(gm_curr) and not np.isnan(gm_prior):
            score += int(gm_curr > gm_prior)
            tests_available += 1
        
        # F9: Asset turnover improving
        at_curr = safe_div(revenue_curr, total_assets)
        at_prior = safe_div(revenue_prior, total_assets_prior)
        
        if not np.isnan(at_curr) and not np.isnan(at_prior):
            score += int(at_curr > at_prior)
            tests_available += 1
        
        # Require minimum 6 of 9 tests to have valid data
        min_tests_required = int(self._factor_config.get('min_tests_required', 6))
        if tests_available < min_tests_required:
            return np.nan
        
        return score
