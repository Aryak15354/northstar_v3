from __future__ import annotations

from typing import Any, Dict

import numpy as np
import pandas as pd

from .common import clamp, confidence_from_spread, f, infer_market_cap, variance_from_bounds


class IntrinsicFamilyEngine:
    """
    Multi-model intrinsic valuation family:
    - FCFF DCF
    - FCFE DCF
    - Multi-stage DDM
    - APV
    """

    def __init__(
        self,
        risk_free_rate: float = 0.07,
        equity_risk_premium: float = 0.06,
        terminal_growth_cap: float = 0.05,
    ) -> None:
        self.risk_free_rate = float(risk_free_rate)
        self.equity_risk_premium = float(equity_risk_premium)
        self.terminal_growth_cap = float(terminal_growth_cap)

    @staticmethod
    def _discounted_two_stage(
        cashflow_0: float,
        growth_high: float,
        growth_fade: float,
        years_high: int,
        years_fade: int,
        terminal_growth: float,
        discount_rate: float,
    ) -> float:
        if not np.isfinite(cashflow_0) or cashflow_0 <= 0:
            return np.nan
        discount_rate = max(discount_rate, 0.04)
        terminal_growth = min(terminal_growth, discount_rate - 0.01)
        value = 0.0
        cf = float(cashflow_0)
        t = 0
        for _ in range(max(years_high, 0)):
            t += 1
            cf = cf * (1.0 + growth_high)
            value += cf / ((1.0 + discount_rate) ** t)
        if years_fade > 0:
            for i in range(years_fade):
                t += 1
                w = (i + 1) / years_fade
                g = growth_high * (1.0 - w) + growth_fade * w
                cf = cf * (1.0 + g)
                value += cf / ((1.0 + discount_rate) ** t)
        terminal_cf = cf * (1.0 + terminal_growth)
        denom = (discount_rate - terminal_growth)
        if denom <= 1e-6:
            return value
        terminal_value = terminal_cf / denom
        value += terminal_value / ((1.0 + discount_rate) ** max(t, 1))
        return value

    def _compute_fcff_value(self, row: pd.Series) -> Dict[str, float]:
        market_cap = infer_market_cap(row)
        ebit = f(row.get("operating_income_ttm"), np.nan)
        tax_rate = clamp(f(row.get("tax_provision"), 0.25), 0.05, 0.40)
        dep = abs(f(row.get("depreciation_amortization_ttm"), 0.0))
        capex = abs(f(row.get("capex_ttm"), 0.0))
        wc_change = f(row.get("change_in_working_capital"), 0.0)
        growth = clamp(f(row.get("revenue_growth"), 0.02), -0.05, 0.18)
        debt = max(0.0, f(row.get("total_debt"), 0.0))
        cash = max(0.0, f(row.get("cash_and_equivalents"), 0.0))

        fcff = ebit * (1.0 - tax_rate) + dep - capex - wc_change
        if not np.isfinite(fcff) or fcff <= 0:
            return {
                "fcff_value": np.nan,
                "fcff_gap": np.nan,
                "fcff_variance": 1.0,
                "fcff_confidence": 0.20,
                "fcff_uncertainty_band": np.nan,
            }

        wacc = clamp(self.risk_free_rate + 1.0 * self.equity_risk_premium, 0.08, 0.16)
        term_growth = clamp(min(growth * 0.5, self.terminal_growth_cap), 0.01, self.terminal_growth_cap)
        base_ev = self._discounted_two_stage(
            cashflow_0=fcff,
            growth_high=max(growth, 0.0),
            growth_fade=max(growth * 0.5, 0.0),
            years_high=5,
            years_fade=5,
            terminal_growth=term_growth,
            discount_rate=wacc,
        )

        low_ev = self._discounted_two_stage(
            cashflow_0=fcff,
            growth_high=max(growth - 0.03, -0.02),
            growth_fade=max(growth * 0.3, -0.01),
            years_high=4,
            years_fade=4,
            terminal_growth=max(0.0, term_growth - 0.01),
            discount_rate=min(0.22, wacc + 0.01),
        )
        high_ev = self._discounted_two_stage(
            cashflow_0=fcff,
            growth_high=min(0.25, growth + 0.03),
            growth_fade=max(growth * 0.7, 0.0),
            years_high=6,
            years_fade=5,
            terminal_growth=min(self.terminal_growth_cap, term_growth + 0.01),
            discount_rate=max(0.06, wacc - 0.01),
        )
        if not np.isfinite(base_ev):
            base_ev = np.nan

        base_equity = base_ev - debt + cash if np.isfinite(base_ev) else np.nan
        low_equity = low_ev - debt + cash if np.isfinite(low_ev) else np.nan
        high_equity = high_ev - debt + cash if np.isfinite(high_ev) else np.nan

        band = np.nan
        if np.isfinite(low_equity) and np.isfinite(high_equity):
            band = max(0.0, high_equity - low_equity)
        spread_ratio = band / max(abs(base_equity), 1.0) if np.isfinite(base_equity) and np.isfinite(band) else 1.0
        conf = confidence_from_spread(spread_ratio, base=0.78)
        var = variance_from_bounds(low_equity, high_equity)

        gap = np.nan
        if np.isfinite(base_equity) and np.isfinite(market_cap) and market_cap > 0:
            gap = clamp((base_equity - market_cap) / market_cap, -2.0, 2.0)

        return {
            "fcff_value": base_equity,
            "fcff_gap": gap,
            "fcff_variance": var,
            "fcff_confidence": conf,
            "fcff_uncertainty_band": band,
        }

    def _compute_fcfe_value(self, row: pd.Series) -> Dict[str, float]:
        market_cap = infer_market_cap(row)
        net_income = f(row.get("net_income_ttm"), np.nan)
        dep = abs(f(row.get("depreciation_amortization_ttm"), 0.0))
        capex = abs(f(row.get("capex_ttm"), 0.0))
        wc_change = f(row.get("change_in_working_capital"), 0.0)
        debt = max(0.0, f(row.get("total_debt"), 0.0))
        debt_prev = debt * 0.95
        net_debt_issued = debt - debt_prev
        growth = clamp(f(row.get("revenue_growth"), 0.02), -0.05, 0.20)

        fcfe = net_income + dep - capex - wc_change + net_debt_issued
        if not np.isfinite(fcfe) or fcfe <= 0:
            return {
                "fcfe_value": np.nan,
                "fcfe_gap": np.nan,
                "fcfe_variance": 1.0,
                "fcfe_confidence": 0.20,
            }

        cost_of_equity = clamp(self.risk_free_rate + 1.1 * self.equity_risk_premium, 0.09, 0.18)
        term_growth = clamp(min(growth * 0.55, self.terminal_growth_cap), 0.0, self.terminal_growth_cap)
        base = self._discounted_two_stage(
            cashflow_0=fcfe,
            growth_high=max(growth, 0.0),
            growth_fade=max(growth * 0.4, -0.01),
            years_high=5,
            years_fade=5,
            terminal_growth=term_growth,
            discount_rate=cost_of_equity,
        )
        low = self._discounted_two_stage(
            cashflow_0=fcfe,
            growth_high=max(growth - 0.03, -0.03),
            growth_fade=max(growth * 0.2, -0.02),
            years_high=4,
            years_fade=4,
            terminal_growth=max(0.0, term_growth - 0.01),
            discount_rate=min(0.24, cost_of_equity + 0.01),
        )
        high = self._discounted_two_stage(
            cashflow_0=fcfe,
            growth_high=min(0.28, growth + 0.03),
            growth_fade=max(growth * 0.7, 0.0),
            years_high=6,
            years_fade=5,
            terminal_growth=min(self.terminal_growth_cap, term_growth + 0.01),
            discount_rate=max(0.07, cost_of_equity - 0.01),
        )

        spread_ratio = max(0.0, high - low) / max(abs(base), 1.0) if np.isfinite(base) and np.isfinite(low) and np.isfinite(high) else 1.0
        conf = confidence_from_spread(spread_ratio, base=0.72)
        var = variance_from_bounds(low, high)
        gap = np.nan
        if np.isfinite(base) and np.isfinite(market_cap) and market_cap > 0:
            gap = clamp((base - market_cap) / market_cap, -2.0, 2.0)
        return {
            "fcfe_value": base,
            "fcfe_gap": gap,
            "fcfe_variance": var,
            "fcfe_confidence": conf,
        }

    def _compute_ddm_value(self, row: pd.Series) -> Dict[str, float]:
        market_cap = infer_market_cap(row)
        net_income = f(row.get("net_income_ttm"), np.nan)
        fcf = f(row.get("free_cash_flow_ttm"), np.nan)
        if not np.isfinite(net_income) or net_income <= 0:
            return {"ddm_value": np.nan, "ddm_gap": np.nan, "ddm_variance": 1.0, "ddm_confidence": 0.20}

        payout_ratio = 0.25
        if np.isfinite(fcf) and fcf > 0:
            payout_ratio = clamp(fcf / max(net_income, 1e-6), 0.05, 0.75)
        dividend = net_income * payout_ratio
        growth = clamp(f(row.get("revenue_growth"), 0.02), -0.02, 0.12)
        required_return = clamp(self.risk_free_rate + 0.9 * self.equity_risk_premium, 0.08, 0.16)
        g1 = max(0.0, growth * 0.8)
        g2 = max(0.0, growth * 0.4)
        terminal_growth = clamp(min(g2, required_return - 0.01), 0.0, 0.045)

        # Explicit 10-year multi-stage DDM.
        value = 0.0
        d = dividend
        for year in range(1, 6):
            d = d * (1.0 + g1)
            value += d / ((1.0 + required_return) ** year)
        for year in range(6, 11):
            d = d * (1.0 + g2)
            value += d / ((1.0 + required_return) ** year)
        if required_return > terminal_growth:
            terminal = (d * (1.0 + terminal_growth)) / (required_return - terminal_growth)
            value += terminal / ((1.0 + required_return) ** 10)

        low = value * 0.82
        high = value * 1.18
        var = variance_from_bounds(low, high)
        conf = confidence_from_spread((high - low) / max(abs(value), 1.0), base=0.66)
        gap = np.nan
        if np.isfinite(value) and np.isfinite(market_cap) and market_cap > 0:
            gap = clamp((value - market_cap) / market_cap, -2.0, 2.0)
        return {"ddm_value": value, "ddm_gap": gap, "ddm_variance": var, "ddm_confidence": conf}

    def _compute_apv_value(self, row: pd.Series) -> Dict[str, float]:
        market_cap = infer_market_cap(row)
        ebit = f(row.get("operating_income_ttm"), np.nan)
        dep = abs(f(row.get("depreciation_amortization_ttm"), 0.0))
        capex = abs(f(row.get("capex_ttm"), 0.0))
        wc = f(row.get("change_in_working_capital"), 0.0)
        debt = max(0.0, f(row.get("total_debt"), 0.0))
        cash = max(0.0, f(row.get("cash_and_equivalents"), 0.0))
        tax_rate = clamp(f(row.get("tax_provision"), 0.25), 0.05, 0.40)
        growth = clamp(f(row.get("revenue_growth"), 0.02), -0.03, 0.15)

        ufcf = ebit * (1.0 - tax_rate) + dep - capex - wc
        if not np.isfinite(ufcf) or ufcf <= 0:
            return {"apv_value": np.nan, "apv_gap": np.nan, "apv_variance": 1.0, "apv_confidence": 0.20}

        unlevered_cost = clamp(self.risk_free_rate + 0.85 * self.equity_risk_premium, 0.08, 0.15)
        term_growth = clamp(min(growth * 0.5, self.terminal_growth_cap), 0.0, self.terminal_growth_cap)
        base_unlevered = self._discounted_two_stage(
            cashflow_0=ufcf,
            growth_high=max(growth, 0.0),
            growth_fade=max(growth * 0.4, 0.0),
            years_high=5,
            years_fade=4,
            terminal_growth=term_growth,
            discount_rate=unlevered_cost,
        )
        tax_shield = debt * tax_rate * 0.60
        apv = base_unlevered + tax_shield - debt + cash
        low = apv * 0.84
        high = apv * 1.16
        var = variance_from_bounds(low, high)
        conf = confidence_from_spread((high - low) / max(abs(apv), 1.0), base=0.70)
        gap = np.nan
        if np.isfinite(apv) and np.isfinite(market_cap) and market_cap > 0:
            gap = clamp((apv - market_cap) / market_cap, -2.0, 2.0)
        return {"apv_value": apv, "apv_gap": gap, "apv_variance": var, "apv_confidence": conf}

    def run(
        self,
        core_df: pd.DataFrame,
        history_by_ticker: Dict[str, Dict[str, pd.Series]] | None = None,
    ) -> pd.DataFrame:
        rows: list[dict[str, Any]] = []
        for _, row in core_df.iterrows():
            market_cap = infer_market_cap(row)
            core_value = f(row.get("intrinsic_value_estimate"), np.nan)
            core_gap = np.nan
            if np.isfinite(core_value) and np.isfinite(market_cap) and market_cap > 0:
                core_gap = clamp((core_value - market_cap) / market_cap, -2.0, 2.0)

            fcff = self._compute_fcff_value(row)
            fcfe = self._compute_fcfe_value(row)
            ddm = self._compute_ddm_value(row)
            apv = self._compute_apv_value(row)

            # Confidence fallback from quality block.
            quality_hint = clamp(f(row.get("earnings_quality_score_v2"), 50.0) / 100.0, 0.2, 0.95)
            core_conf = clamp(0.45 + 0.40 * quality_hint, 0.2, 0.95)
            rows.append(
                {
                    "ticker": row.get("ticker"),
                    "date": row.get("date"),
                    "price": f(row.get("Close"), np.nan),
                    "reference_value": market_cap,
                    "core_value": core_value,
                    "core_gap": core_gap,
                    "core_variance": variance_from_bounds(core_value * 0.9, core_value * 1.1) if np.isfinite(core_value) else 1.0,
                    "core_confidence": core_conf,
                    **fcff,
                    **fcfe,
                    **ddm,
                    **apv,
                }
            )
        return pd.DataFrame(rows)

