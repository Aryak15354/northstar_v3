"""
Earnings Quality Analyzer
Detects earnings manipulation and assesses cash flow quality
"""

from datetime import datetime
import pandas as pd
import numpy as np
from typing import Dict, Optional
from dataclasses import dataclass

from src.valuation.core.normalized_financials import FinancialNormalizer


# Per Sehgal, Srivastava & Sharma (2012), higher accruals are a positive
# expected-return signal in India, unlike the canonical US interpretation.
INDIA_ACCRUAL_SIGN_POSITIVE = True


def _compute_accrual_quality_score(accrual_ratio: float) -> float:
    """Map accrual ratio to 0-100 quality score using the configured sign convention."""
    ratio = float(accrual_ratio or 0.0)
    if INDIA_ACCRUAL_SIGN_POSITIVE:
        return float(np.clip(50.0 + ratio * 500.0, 0.0, 100.0))
    return float(max(0.0, 100.0 - abs(ratio) * 500.0))


@dataclass
class EarningsQualityScore:
    """Container for earnings quality assessment"""
    overall_score: float  # 0-100, higher is better
    accrual_quality: float
    cash_conversion: float
    earnings_stability: float
    red_flags: list
    quality_grade: str  # A, B, C, D, F


class EarningsQualityAnalyzer:
    """
    Analyze earnings quality using forensic accounting techniques
    
    Key metrics:
    1. Accrual Ratio (Sloan 1996)
    2. Cash Flow to Earnings
    3. Earnings Stability
    4. Working Capital Quality
    5. Beneish M-Score components
    """
    
    def __init__(self, config: Optional[dict] = None):
        self._config = dict(config or {})
        self.red_flag_threshold = 3  # Number of red flags before downgrade
        self._normalizer = FinancialNormalizer(self._config)
    
    def calculate_accrual_ratio(
        self,
        net_income: float,
        operating_cash_flow: float,
        total_assets: float
    ) -> float:
        """
        Calculate Accrual Ratio (Sloan 1996)
        
        Accruals = (Net Income - Operating Cash Flow) / Total Assets
        
        CRITICAL FOR INDIAN MARKET:
        High accruals indicate potential earnings manipulation in US markets,
        but in Indian markets, high accruals predict HIGHER returns.
        
        DO NOT invert the sign of this calculation for Indian market.
        
        Threshold: > 0.10 is concerning in US, but positive signal in India
        
        Reference: Northstar V3 Signal Engineering Plan, Requirement 19
        """
        if total_assets <= 0:
            return 0.0
        
        accruals = (net_income - operating_cash_flow) / total_assets
        return accruals
    
    def calculate_cash_conversion_quality(
        self,
        operating_cash_flow: float,
        net_income: float,
        history_ocf: Optional[pd.Series] = None,
        history_ni: Optional[pd.Series] = None
    ) -> Dict[str, float]:
        """
        Assess cash conversion quality
        
        Returns:
            - current_conversion: OCF / NI for current period
            - avg_conversion: Average over history
            - consistency: Std dev of conversion ratio
        """
        current_conversion = operating_cash_flow / net_income if net_income > 0 else 0
        
        if history_ocf is not None and history_ni is not None:
            conversion_history = history_ocf / history_ni.replace(0, np.nan)
            avg_conversion = conversion_history.mean()
            consistency = 1 / (1 + conversion_history.std())  # Higher is better
        else:
            avg_conversion = current_conversion
            consistency = 0.5  # Neutral
        
        return {
            'current_conversion': current_conversion,
            'avg_conversion': avg_conversion,
            'consistency': consistency
        }
    
    def calculate_earnings_stability(
        self,
        earnings_history: pd.Series,
        revenue_history: Optional[pd.Series] = None
    ) -> Dict[str, float]:
        """
        Calculate earnings stability metrics
        
        Returns:
            - volatility: Coefficient of variation
            - trend: Linear trend slope
            - margin_stability: If revenue provided
        """
        if len(earnings_history) < 3:
            return {'volatility': 1.0, 'trend': 0.0, 'margin_stability': 0.5}
        
        # Coefficient of variation (lower is better)
        mean_earnings = earnings_history.mean()
        if mean_earnings > 0:
            cv = earnings_history.std() / mean_earnings
        else:
            cv = 999  # Very unstable
        
        # Trend
        x = np.arange(len(earnings_history))
        if len(x) > 1:
            trend = np.polyfit(x, earnings_history.values, 1)[0]
        else:
            trend = 0
        
        # Margin stability
        if revenue_history is not None and len(revenue_history) == len(earnings_history):
            margins = earnings_history / revenue_history.replace(0, np.nan)
            margin_stability = 1 / (1 + margins.std())
        else:
            margin_stability = 0.5
        
        return {
            'volatility': cv,
            'trend': trend,
            'margin_stability': margin_stability
        }
    
    def calculate_beneish_components(
        self,
        # Current period
        receivables: float,
        revenue: float,
        gross_profit: float,
        total_assets: float,
        ppe: float,
        depreciation: float,
        sga: float,
        
        # Prior period
        receivables_prior: float,
        revenue_prior: float,
        gross_profit_prior: float,
        total_assets_prior: float,
        ppe_prior: float,
        depreciation_prior: float,
        sga_prior: float,
    ) -> Dict[str, float]:
        """
        Calculate key Beneish M-Score components
        
        DSRI: Days Sales in Receivables Index
        GMI: Gross Margin Index
        AQI: Asset Quality Index
        SGI: Sales Growth Index
        """
        # DSRI - Receivables growing faster than sales
        dsri = 0
        if revenue_prior > 0 and receivables_prior > 0:
            receivables_ratio = (receivables / revenue) / (receivables_prior / revenue_prior)
            dsri = receivables_ratio
        
        # GMI - Gross margin deterioration
        gmi = 0
        if revenue_prior > 0 and revenue > 0:
            gm_prior = gross_profit_prior / revenue_prior
            gm_current = gross_profit / revenue
            if gm_current > 0:
                gmi = gm_prior / gm_current
        
        # AQI - Asset quality deterioration
        aqi = 0
        if total_assets_prior > 0 and total_assets > 0:
            # Non-current assets excluding PPE
            nca_prior = total_assets_prior - ppe_prior
            nca_current = total_assets - ppe
            
            aqi_prior = nca_prior / total_assets_prior if total_assets_prior > 0 else 0
            aqi_current = nca_current / total_assets if total_assets > 0 else 0
            
            if aqi_prior > 0:
                aqi = aqi_current / aqi_prior
        
        # SGI - Sales growth (high growth can indicate manipulation)
        sgi = revenue / revenue_prior if revenue_prior > 0 else 1
        
        # DEPI - Depreciation Index (lower depreciation = aggressive)
        depi = 0
        if ppe_prior > 0 and ppe > 0:
            dep_rate_prior = depreciation_prior / ppe_prior
            dep_rate_current = depreciation / ppe
            if dep_rate_current > 0:
                depi = dep_rate_prior / dep_rate_current
        
        return {
            'dsri': dsri,  # > 1.03 is concerning
            'gmi': gmi,    # > 1.04 is concerning
            'aqi': aqi,    # > 1.04 is concerning
            'sgi': sgi,    # > 1.25 is concerning
            'depi': depi,  # > 1.04 is concerning
        }
    
    def detect_red_flags(
        self,
        accrual_ratio: float,
        cash_conversion: float,
        beneish: Dict[str, float],
        earnings_volatility: float
    ) -> list:
        """
        Detect earnings quality red flags
        """
        red_flags = []
        
        # High accruals
        if (not INDIA_ACCRUAL_SIGN_POSITIVE) and abs(accrual_ratio) > 0.10:
            red_flags.append(f"High accruals: {accrual_ratio:.2%}")
        
        # Poor cash conversion
        if cash_conversion < 0.7:
            red_flags.append(f"Low cash conversion: {cash_conversion:.2f}")
        
        # Beneish flags
        if beneish.get('dsri', 0) > 1.03:
            red_flags.append(f"Receivables growing faster than sales: DSRI={beneish['dsri']:.2f}")
        
        if beneish.get('gmi', 0) > 1.04:
            red_flags.append(f"Gross margin deterioration: GMI={beneish['gmi']:.2f}")
        
        if beneish.get('aqi', 0) > 1.04:
            red_flags.append(f"Asset quality deterioration: AQI={beneish['aqi']:.2f}")
        
        if beneish.get('sgi', 0) > 1.50:
            red_flags.append(f"Aggressive sales growth: SGI={beneish['sgi']:.2f}")
        
        # High earnings volatility
        if earnings_volatility > 0.5:
            red_flags.append(f"High earnings volatility: CV={earnings_volatility:.2f}")
        
        return red_flags
    
    def calculate_quality_score(
        self,
        accrual_ratio: float,
        cash_conversion: float,
        earnings_stability: float,
        red_flag_count: int
    ) -> tuple:
        """
        Calculate overall earnings quality score (0-100)
        
        Returns: (score, grade)
        """
        # Component scores (0-100)
        accrual_score = _compute_accrual_quality_score(accrual_ratio)
        conversion_score = min(100, cash_conversion * 100)  # 1.0 = 100
        stability_score = earnings_stability * 100
        
        # Red flag penalty
        red_flag_penalty = red_flag_count * 10  # 10 points per flag
        
        # Weighted score
        raw_score = (
            accrual_score * 0.35 +
            conversion_score * 0.35 +
            stability_score * 0.30
        )
        
        final_score = max(0, raw_score - red_flag_penalty)
        
        # Grade
        if final_score >= 80:
            grade = 'A'
        elif final_score >= 65:
            grade = 'B'
        elif final_score >= 50:
            grade = 'C'
        elif final_score >= 35:
            grade = 'D'
        else:
            grade = 'F'
        
        return final_score, grade
    
    def analyze_earnings_quality(
        self,
        # Current period
        net_income: float,
        operating_cash_flow: float,
        total_assets: float,
        receivables: float,
        revenue: float,
        gross_profit: float,
        ppe: float,
        depreciation: float,
        sga: float,
        
        # Prior period
        receivables_prior: float = 0,
        revenue_prior: float = 0,
        gross_profit_prior: float = 0,
        total_assets_prior: float = 0,
        ppe_prior: float = 0,
        depreciation_prior: float = 0,
        sga_prior: float = 0,
        
        # Historical
        earnings_history: Optional[pd.Series] = None,
        ocf_history: Optional[pd.Series] = None,
        revenue_history: Optional[pd.Series] = None,
    ) -> EarningsQualityScore:
        """
        Comprehensive earnings quality analysis
        """
        # 1. Accrual ratio
        accrual_ratio = self.calculate_accrual_ratio(
            net_income, operating_cash_flow, total_assets
        )
        
        # 2. Cash conversion
        cash_conv = self.calculate_cash_conversion_quality(
            operating_cash_flow, net_income, ocf_history, 
            earnings_history if earnings_history is not None else pd.Series([net_income])
        )
        
        # 3. Earnings stability
        if earnings_history is not None and len(earnings_history) > 2:
            stability = self.calculate_earnings_stability(
                earnings_history, revenue_history
            )
        else:
            stability = {'volatility': 0.3, 'trend': 0, 'margin_stability': 0.5}
        
        # 4. Beneish components
        if revenue_prior > 0:
            beneish = self.calculate_beneish_components(
                receivables, revenue, gross_profit, total_assets, ppe, depreciation, sga,
                receivables_prior, revenue_prior, gross_profit_prior, 
                total_assets_prior, ppe_prior, depreciation_prior, sga_prior
            )
        else:
            beneish = {}
        
        # 5. Red flags
        red_flags = self.detect_red_flags(
            accrual_ratio,
            cash_conv['current_conversion'],
            beneish,
            stability['volatility']
        )
        
        # 6. Overall score
        score, grade = self.calculate_quality_score(
            accrual_ratio,
            cash_conv['avg_conversion'],
            stability['margin_stability'],
            len(red_flags)
        )
        
        return EarningsQualityScore(
            overall_score=score,
            accrual_quality=_compute_accrual_quality_score(accrual_ratio),
            cash_conversion=cash_conv['avg_conversion'] * 100,
            earnings_stability=stability['margin_stability'] * 100,
            red_flags=red_flags,
            quality_grade=grade
        )

    def analyze(
        self,
        ticker: str,
        as_of_date: Optional[datetime] = None,
        fin: Optional[dict] = None,
        fin_history: Optional[list[dict]] = None,
    ) -> dict:
        """
        Analyze earnings quality using PIT-safe Screener-backed financials.
        """
        as_of_ts = pd.Timestamp(as_of_date or pd.Timestamp.utcnow()).to_pydatetime()
        current = dict(fin or self._normalizer.load_latest(ticker, as_of_ts, "annual"))
        history = list(
            fin_history or self._normalizer.load_history(ticker, as_of_ts, n_periods=10, frequency="annual")
        )
        if not current:
            return {
                "quality_score": np.nan,
                "quality_grade": "NA",
                "accrual_quality": np.nan,
                "cash_conversion": np.nan,
                "earnings_stability": np.nan,
                "red_flags": [],
                "has_real_cashflow": False,
            }

        prior = history[-2] if len(history) >= 2 else {}
        revenue = pd.to_numeric(current.get("revenue", current.get("sales")), errors="coerce")
        total_expenses = pd.to_numeric(current.get("total_expenses"), errors="coerce")
        gross_profit = (
            float(revenue) - float(total_expenses)
            if pd.notna(revenue) and pd.notna(total_expenses)
            else float(revenue) * (1.0 - float(pd.to_numeric(current.get("opm_pct"), errors="coerce")) / 100.0)
            if pd.notna(revenue) and pd.notna(pd.to_numeric(current.get("opm_pct"), errors="coerce"))
            else 0.0
        )

        earnings_history = pd.Series(
            [pd.to_numeric(row.get("net_profit"), errors="coerce") for row in history],
            dtype=float,
        ).dropna()
        ocf_history = pd.Series(
            [pd.to_numeric(row.get("cash_from_operations"), errors="coerce") for row in history],
            dtype=float,
        ).dropna()
        revenue_history = pd.Series(
            [pd.to_numeric(row.get("revenue", row.get("sales")), errors="coerce") for row in history],
            dtype=float,
        ).dropna()

        assessment = self.analyze_earnings_quality(
            net_income=float(pd.to_numeric(current.get("net_profit"), errors="coerce") or 0.0),
            operating_cash_flow=float(pd.to_numeric(current.get("cash_from_operations"), errors="coerce") or 0.0),
            total_assets=float(pd.to_numeric(current.get("total_assets"), errors="coerce") or 0.0),
            receivables=float(pd.to_numeric(current.get("receivables"), errors="coerce") or 0.0),
            revenue=float(revenue or 0.0),
            gross_profit=float(gross_profit or 0.0),
            ppe=float(pd.to_numeric(current.get("fixed_assets"), errors="coerce") or 0.0),
            depreciation=float(pd.to_numeric(current.get("depreciation"), errors="coerce") or 0.0),
            sga=float(pd.to_numeric(current.get("other_liabilities"), errors="coerce") or 0.0),
            receivables_prior=float(pd.to_numeric(prior.get("receivables"), errors="coerce") or 0.0),
            revenue_prior=float(pd.to_numeric(prior.get("revenue", prior.get("sales")), errors="coerce") or 0.0),
            gross_profit_prior=float(
                (
                    pd.to_numeric(prior.get("revenue", prior.get("sales")), errors="coerce")
                    - pd.to_numeric(prior.get("total_expenses"), errors="coerce")
                )
                if pd.notna(pd.to_numeric(prior.get("revenue", prior.get("sales")), errors="coerce"))
                and pd.notna(pd.to_numeric(prior.get("total_expenses"), errors="coerce"))
                else 0.0
            ),
            total_assets_prior=float(pd.to_numeric(prior.get("total_assets"), errors="coerce") or 0.0),
            ppe_prior=float(pd.to_numeric(prior.get("fixed_assets"), errors="coerce") or 0.0),
            depreciation_prior=float(pd.to_numeric(prior.get("depreciation"), errors="coerce") or 0.0),
            sga_prior=float(pd.to_numeric(prior.get("other_liabilities"), errors="coerce") or 0.0),
            earnings_history=earnings_history if not earnings_history.empty else None,
            ocf_history=ocf_history if not ocf_history.empty else None,
            revenue_history=revenue_history if not revenue_history.empty else None,
        )

        return {
            "quality_score": float(assessment.overall_score),
            "quality_grade": assessment.quality_grade,
            "accrual_quality": float(assessment.accrual_quality),
            "cash_conversion": float(assessment.cash_conversion),
            "earnings_stability": float(assessment.earnings_stability),
            "red_flags": list(assessment.red_flags),
            "has_real_cashflow": bool(
                current.get("cash_from_operations") is not None
                and not pd.isna(current.get("cash_from_operations"))
            ),
        }
