"""
Earnings Quality Factor (Accruals)

The Sloan accruals ratio for stock i:
    ACCRUAL_i = (Net Income - Operating Cash Flow) / Average Total Assets

Northstar defaults to the India-correct sign from Sehgal et al. (2012):
high accruals are treated as a positive expected-return signal unless
config explicitly requests the US-style negative sign.

Composite version uses three components:
1. Sloan accruals ratio (weight: 0.40)
2. Cash conversion quality: OCF / Net Income (weight: 0.30)
3. Operating Working Capital change (weight: 0.30)

PIT compliance: Fundamental data only. Reporting lag applies.
Output: EQ_raw = sign_multiplier × composite_accruals_score
"""

from datetime import datetime
import pandas as pd
import numpy as np
import logging

from .base_factor import BaseFactor

logger = logging.getLogger(__name__)


class EarningsQualityFactor(BaseFactor):
    """Earnings Quality (Accruals) factor implementation."""
    
    FACTOR_NAME = "earnings_quality"
    FACTOR_FAMILY = "QUALITY"
    LOOKAHEAD_SAFE = True
    
    def _compute_raw(self, as_of_date: datetime, tickers: list) -> pd.Series:
        """
        Compute composite earnings quality score for each ticker.
        """
        fundamentals = self._registry.fundamentals.get_factor_financials(
            as_of_date=as_of_date,
            tickers=tickers,
            frequency='annual',
            periods=2,
            reporting_lag_days=self._factor_config.get('reporting_lag_days'),
        )
        india_sign = str(self._factor_config.get('india_accrual_sign', 'positive')).strip().lower()
        sign_multiplier = 1.0 if india_sign == 'positive' else -1.0

        results = {}
        for ticker in tickers:
            try:
                fin = fundamentals.get(ticker, {})
                current = fin.get('current', {})
                prior = fin.get('prior', {})
                if not current or not prior:
                    results[ticker] = np.nan
                    continue
                eq_score = self._compute_eq_score(ticker, current, prior)
                results[ticker] = (eq_score * sign_multiplier) if not np.isnan(eq_score) else np.nan
            except Exception as e:
                logger.debug(f"Earnings Quality failed for {ticker}: {e}")
                results[ticker] = np.nan

        return pd.Series(results, index=tickers)
    
    def _compute_eq_score(self, ticker: str, curr: dict, prior: dict) -> float:
        """
        Compute composite earnings quality score.
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
        
        # Extract required fields
        def get_field(data, *names):
            for name in names:
                if name in data and data[name] is not None:
                    return data[name]
                lower_name = name.lower()
                for key in data.keys():
                    if key.lower() == lower_name:
                        return data[key]
            return None
        
        net_income = get_field(curr, 'net_profit', 'Net Profit', 'net_income', 'Net Income')
        ocf = get_field(curr, 'cash_from_operations', 'Operating Cash Flow',
                       'cash_from_operations', 'CFO')
        assets_curr = get_field(curr, 'total_assets', 'Total Assets', 'assets', 'Assets')
        assets_prior = get_field(prior, 'total_assets', 'Total Assets', 'assets', 'Assets')
        
        if any(v is None for v in [net_income, ocf, assets_curr, assets_prior]):
            return np.nan
        
        if pd.isna(assets_prior) or assets_prior == 0:
            return np.nan
        
        avg_assets = (float(assets_curr) + float(assets_prior)) / 2
        
        # Component 1: Sloan accruals ratio
        sloan = (float(net_income) - float(ocf)) / avg_assets if avg_assets > 0 else np.nan
        
        # Component 2: Cash conversion quality (OCF / Net Income)
        if float(net_income) != 0:
            ccq = min(float(ocf) / float(net_income), 3.0)  # Cap at 3.0
        else:
            ccq = np.nan
        
        # Component 3: Operating Working Capital change
        ca_curr = get_field(curr, 'current_assets', 'Current Assets') or 0
        cash_curr = get_field(curr, 'cash_and_equivalents', 'Cash', 'Cash and Equivalents') or 0
        cl_curr = get_field(curr, 'current_liabilities', 'Current Liabilities') or 0
        std_curr = get_field(curr, 'short_term_debt', 'Short Term Debt', 'ST Debt') or 0
        
        ca_prior = get_field(prior, 'current_assets', 'Current Assets') or 0
        cash_prior = get_field(prior, 'cash_and_equivalents', 'Cash', 'Cash and Equivalents') or 0
        cl_prior = get_field(prior, 'current_liabilities', 'Current Liabilities') or 0
        std_prior = get_field(prior, 'short_term_debt', 'Short Term Debt', 'ST Debt') or 0
        
        owc_curr = (float(ca_curr) - float(cash_curr)) - (float(cl_curr) - float(std_curr))
        owc_prior = (float(ca_prior) - float(cash_prior)) - (float(cl_prior) - float(std_prior))
        
        delta_owc = (owc_curr - owc_prior) / avg_assets if avg_assets > 0 else np.nan
        
        # Weight components
        components = []
        weights = []
        
        if not np.isnan(sloan):
            components.append(sloan)
            weights.append(0.40)
        if not np.isnan(ccq):
            components.append(-ccq)  # Flip: high CCQ = high quality = negative accrual signal
            weights.append(0.30)
        if not np.isnan(delta_owc):
            components.append(delta_owc)
            weights.append(0.30)
        
        if len(components) < 2:
            return np.nan
        
        # Renormalize weights to sum to 1.0
        total_weight = sum(weights)
        composite = sum(c * w / total_weight for c, w in zip(components, weights))
        
        return composite
