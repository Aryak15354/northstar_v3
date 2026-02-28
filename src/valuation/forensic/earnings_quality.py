"""
Earnings Quality Analyzer
Detects earnings manipulation and assesses cash flow quality
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional
from dataclasses import dataclass


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
    
    def __init__(self):
        self.red_flag_threshold = 3  # Number of red flags before downgrade
    
    def calculate_accrual_ratio(
        self,
        net_income: float,
        operating_cash_flow: float,
        total_assets: float
    ) -> float:
        """
        Calculate Accrual Ratio (Sloan 1996)
        
        Accruals = (Net Income - Operating Cash Flow) / Total Assets
        
        High accruals indicate potential earnings manipulation
        Threshold: > 0.10 is concerning
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
        if abs(accrual_ratio) > 0.10:
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
        accrual_score = max(0, 100 - abs(accrual_ratio) * 500)  # Penalty for high accruals
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
            accrual_quality=100 - abs(accrual_ratio) * 500,
            cash_conversion=cash_conv['avg_conversion'] * 100,
            earnings_stability=stability['margin_stability'] * 100,
            red_flags=red_flags,
            quality_grade=grade
        )
