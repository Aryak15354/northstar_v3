"""
DCF Engine - Conservative Discounted Cash Flow valuation
Implements Buffett-style conservative DCF with margin of safety
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple
from dataclasses import dataclass

from src.valuation.core.normalized_financials import FinancialNormalizer


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
    # True when intrinsic_value* was NOT produced by the real DCF calculation
    # (buffett_style_valuation raised, or returned a non-positive per-share
    # value) and was instead substituted with a price-anchored placeholder.
    # Downstream consumers must not treat a fallback result as equivalent to
    # a genuine valuation -- it's a tautology (fair value derived from the
    # current price itself), not an independent estimate.
    is_fallback: bool = False


class DCFEngine:
    """
    Conservative DCF Engine following Buffett principles
    
    Key features:
    1. Conservative growth assumptions
    2. Two-stage model (growth + terminal)
    3. ROIC-based growth sustainability
    4. Margin of safety requirement
    5. Sensitivity analysis
    
    GAP 3 INTEGRATION: Now uses live credit ratings for discount rate adjustments
    """
    
    def __init__(self, registry=None, config: dict = None):
        self._config = dict(config or {})
        self.risk_free_rate = 0.07  # 7% risk-free rate
        self.equity_risk_premium = 0.06  # 6% equity risk premium
        self.min_margin_of_safety = 0.30  # 30% minimum MOS
        self.gdp_growth_cap = 0.06  # 6% GDP growth cap
        
        # GAP 3: Initialize valuation bridge for live credit spreads
        self.valuation_bridge = None
        self.use_live_credit = False
        self._normalizer = FinancialNormalizer(self._config)
        if registry is not None:
            try:
                from src.alternative_data import ValuationAlternativeBridge
                self.valuation_bridge = ValuationAlternativeBridge(registry, config or {})
                self.use_live_credit = True
                print("🟢 Live credit ratings enabled in DCF Engine")
            except Exception as e:
                print(f"⚠️ Could not initialize credit ratings: {e}")

    @staticmethod
    def _history_cagr(history: list[dict], field: str, years: int = 5) -> float:
        if len(history) < years + 1:
            return 0.03
        start = pd.to_numeric(history[-(years + 1)].get(field), errors="coerce")
        end = pd.to_numeric(history[-1].get(field), errors="coerce")
        if pd.isna(start) or pd.isna(end) or float(start) <= 0:
            return 0.03
        return max(min((float(end) / float(start)) ** (1.0 / years) - 1.0, 0.20), 0.0)

    @staticmethod
    def _avg_roic(history: list[dict]) -> float:
        roics: list[float] = []
        for fin in history[-10:]:
            roce = pd.to_numeric(fin.get("roce_pct"), errors="coerce")
            if pd.notna(roce):
                roics.append(float(roce) / 100.0)
                continue
            op = pd.to_numeric(fin.get("operating_profit"), errors="coerce")
            debt = pd.to_numeric(fin.get("total_borrowings"), errors="coerce")
            equity = pd.to_numeric(fin.get("equity_capital"), errors="coerce")
            reserves = pd.to_numeric(fin.get("reserves"), errors="coerce")
            capital = (0.0 if pd.isna(equity) else float(equity)) + (0.0 if pd.isna(reserves) else float(reserves)) + (0.0 if pd.isna(debt) else float(debt))
            if pd.notna(op) and capital > 0:
                roics.append(float(op) / capital)
        return float(np.mean(roics)) if roics else 0.12

    def run(
        self,
        ticker: str,
        fin: Optional[dict] = None,
        as_of_date: Optional[pd.Timestamp] = None,
        history: Optional[list[dict]] = None,
        current_price: Optional[float] = None,
    ) -> dict:
        """Run a Screener-backed DCF for one ticker and return a flat result dict."""
        as_of_ts = pd.Timestamp(as_of_date or pd.Timestamp.utcnow()).to_pydatetime()
        fin_data = dict(fin or self._normalizer.load_latest(ticker, as_of_ts, "annual"))
        hist = list(history or self._normalizer.load_history(ticker, as_of_ts, n_periods=10, frequency="annual"))
        if not fin_data:
            return {
                "fair_value": np.nan,
                "confidence": 0.0,
                "owner_earnings_yield": np.nan,
                "margin_of_safety": np.nan,
                "valuation_grade": "NA",
            }

        price = pd.to_numeric(
            current_price if current_price is not None else fin_data.get("current_price"),
            errors="coerce",
        )
        market_cap = pd.to_numeric(fin_data.get("market_cap"), errors="coerce")
        shares_outstanding = pd.to_numeric(fin_data.get("shares_outstanding"), errors="coerce")
        if (pd.isna(shares_outstanding) or float(shares_outstanding) <= 0.0) and pd.notna(price) and float(price) > 0 and pd.notna(market_cap):
            shares_outstanding = float(market_cap) / float(price)

        ocf = pd.to_numeric(fin_data.get("cash_from_operations"), errors="coerce")
        net_income = pd.to_numeric(fin_data.get("net_profit"), errors="coerce")
        depreciation = pd.to_numeric(fin_data.get("depreciation"), errors="coerce")
        owner_earnings = (
            float(ocf)
            if pd.notna(ocf)
            else float((0.0 if pd.isna(net_income) else net_income) + (0.0 if pd.isna(depreciation) else depreciation))
        )
        if not np.isfinite(owner_earnings):
            owner_earnings = 0.0

        roic_10y_avg = self._avg_roic(hist)
        revenue_growth_5y = self._history_cagr(hist, "revenue", years=5)
        quality_inputs = [
            fin_data.get("cash_from_operations"),
            fin_data.get("net_profit"),
            fin_data.get("total_assets"),
            fin_data.get("interest_expense"),
            fin_data.get("total_borrowings"),
        ]
        quality_score = 50.0 + 10.0 * sum(v is not None and not pd.isna(v) for v in quality_inputs)
        quality_score = float(np.clip(quality_score, 30.0, 90.0))

        safe_shares = max(float(shares_outstanding) if pd.notna(shares_outstanding) else 1.0, 1.0)
        safe_price = float(price) if pd.notna(price) else 0.0
        try:
            result = self.buffett_style_valuation(
                owner_earnings=max(owner_earnings, 0.0),
                roic_10y_avg=max(roic_10y_avg, 0.01),
                revenue_growth_5y=max(revenue_growth_5y, 0.0),
                shares_outstanding=safe_shares,
                current_price=safe_price,
                sector=str(fin_data.get("sector", fin_data.get("industry", "Unknown"))),
                quality_score=quality_score,
                ticker=ticker,
                as_of_date=pd.Timestamp(as_of_ts),
            )
        except Exception:
            fallback_total = max(owner_earnings, 0.0) * max(8.0, min((1.0 + max(revenue_growth_5y, 0.0)) * 10.0, 20.0))
            fallback_per_share = fallback_total / safe_shares
            margin_of_safety_pct = ((fallback_per_share - safe_price) / safe_price) if safe_price > 0 else 0.0
            result = DCFResult(
                intrinsic_value=float(fallback_total),
                intrinsic_value_per_share=float(fallback_per_share),
                current_price=float(safe_price),
                margin_of_safety=float(margin_of_safety_pct),
                margin_of_safety_pct=float(margin_of_safety_pct),
                upside_potential=float(margin_of_safety_pct),
                valuation_grade="C",
                assumptions={},
                sensitivity={},
                is_fallback=True,
            )
        if float(result.intrinsic_value_per_share) <= 0.0 and safe_price > 0.0:
            # Price-anchored placeholder: fair_value is derived from
            # current_price itself, so margin_of_safety is tautologically
            # bounded to roughly [-20%, +20%] and carries no independent
            # valuation signal. is_fallback=True flags this explicitly.
            fallback_multiplier = float(np.clip(0.80 + (quality_score / 100.0) * 0.40, 0.80, 1.20))
            fallback_per_share = safe_price * fallback_multiplier
            fallback_total = fallback_per_share * safe_shares
            margin_of_safety_pct = (fallback_per_share - safe_price) / safe_price
            result = DCFResult(
                intrinsic_value=float(fallback_total),
                intrinsic_value_per_share=float(fallback_per_share),
                current_price=float(safe_price),
                margin_of_safety=float(margin_of_safety_pct),
                margin_of_safety_pct=float(margin_of_safety_pct),
                upside_potential=float(margin_of_safety_pct),
                valuation_grade="C",
                assumptions={},
                sensitivity={},
                is_fallback=True,
            )
        owner_earnings_yield = np.nan
        if pd.notna(market_cap) and float(market_cap) > 0:
            owner_earnings_yield = owner_earnings / float(market_cap)

        present_fields = sum(
            fin_data.get(field) is not None and not pd.isna(fin_data.get(field))
            for field in [
                "revenue",
                "net_profit",
                "cash_from_operations",
                "total_assets",
                "total_borrowings",
                "interest_expense",
                "shares_outstanding",
            ]
        )
        confidence = float(np.clip(present_fields / 7.0, 0.1, 1.0))
        if result.is_fallback:
            # Field-presence-based confidence measures nothing about whether
            # the DCF calculation actually succeeded -- a fallback/placeholder
            # value could otherwise report confidence=1.0 indistinguishable
            # from a genuine, fully-computed valuation. Cap it hard.
            confidence = min(confidence, 0.2)
        return {
            "fair_value": float(result.intrinsic_value_per_share),
            "fair_value_total": float(result.intrinsic_value),
            "owner_earnings_yield": float(owner_earnings_yield) if np.isfinite(owner_earnings_yield) else np.nan,
            "confidence": confidence,
            "margin_of_safety": float(result.margin_of_safety_pct),
            "valuation_grade": result.valuation_grade,
            "upside_potential": float(result.upside_potential),
            "is_fallback": bool(result.is_fallback),
        }
    
    def calculate_discount_rate(
        self,
        risk_free_rate: Optional[float] = None,
        beta: float = 1.0,
        size_premium: float = 0.0,
        quality_adjustment: float = 0.0,
        ticker: Optional[str] = None,  # GAP 3: For live credit lookup
        as_of_date: Optional[pd.Timestamp] = None  # GAP 3: For PIT credit data
    ) -> float:
        """
        Calculate required return (discount rate)
        
        Required Return = Risk-Free Rate + Beta × ERP + Size Premium - Quality Adjustment + Credit Spread
        
        GAP 3 INTEGRATION: Now adds credit spread adjustment from live ratings
        """
        if risk_free_rate is None:
            risk_free_rate = self.risk_free_rate
        
        required_return = (
            risk_free_rate +
            beta * self.equity_risk_premium +
            size_premium -
            quality_adjustment
        )
        
        # GAP 3: Add credit spread adjustment if available
        if self.use_live_credit and ticker is not None and as_of_date is not None:
            try:
                credit_inputs = self.valuation_bridge.get_credit_inputs_for_valuation(
                    as_of_date, [ticker]
                )
                if ticker in credit_inputs.index:
                    credit_risk_adj = credit_inputs.loc[ticker, 'credit_risk_adjustment']
                    required_return += credit_risk_adj / 100.0  # Convert from % to decimal
            except Exception as e:
                pass  # Graceful degradation: use base rate if credit data unavailable
        
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
        quality_score: float = 50,
        ticker: Optional[str] = None,  # GAP 3: For live credit/pledge lookup
        as_of_date: Optional[pd.Timestamp] = None  # GAP 3: For PIT data
    ) -> DCFResult:
        """
        Simplified Buffett-style valuation with conservative assumptions
        
        GAP 3 INTEGRATION: Now applies distress haircuts from credit/pledge data
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
            quality_adjustment=quality_adjustment,
            ticker=ticker,  # GAP 3: Pass ticker for credit lookup
            as_of_date=as_of_date  # GAP 3: Pass date for PIT data
        )
        
        # Reinvestment rate estimate
        if roic_10y_avg > 0:
            reinvestment_rate = growth_stage1 / roic_10y_avg
        else:
            reinvestment_rate = 0.5
        
        # Calculate base DCF
        dcf_result = self.two_stage_dcf(
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
        
        # GAP 3: Apply distress haircut if available
        if self.use_live_credit and ticker is not None and as_of_date is not None:
            try:
                distress_scores = self.valuation_bridge.get_combined_distress_score(
                    as_of_date, [ticker]
                )
                if ticker in distress_scores.index:
                    distress_data = distress_scores.loc[ticker]
                    
                    # Apply haircut based on distress
                    if distress_data['recommended_action'] == 'EXCLUDE':
                        # Set intrinsic value to zero for excluded companies
                        dcf_result.intrinsic_value = 0.0
                        dcf_result.intrinsic_value_per_share = 0.0
                        dcf_result.valuation_grade = 'F'
                        dcf_result.assumptions['distress_exclusion'] = True
                    elif distress_data['recommended_action'] == 'HAIRCUT':
                        # Apply haircut based on distress score
                        haircut = distress_data['distress_score'] * 0.3  # Up to 30% haircut
                        dcf_result.intrinsic_value *= (1.0 - haircut)
                        dcf_result.intrinsic_value_per_share *= (1.0 - haircut)
                        dcf_result.assumptions['distress_haircut'] = haircut
                        
                        # Recalculate margin of safety
                        if dcf_result.intrinsic_value_per_share > 0:
                            dcf_result.margin_of_safety = dcf_result.intrinsic_value_per_share - current_price
                            dcf_result.margin_of_safety_pct = dcf_result.margin_of_safety / dcf_result.intrinsic_value_per_share
                            dcf_result.upside_potential = (dcf_result.intrinsic_value_per_share / current_price - 1) if current_price > 0 else 0
            except Exception as e:
                pass  # Graceful degradation: use base valuation if distress data unavailable
        
        return dcf_result
