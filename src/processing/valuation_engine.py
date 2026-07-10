#!/usr/bin/env python3
"""
Northstar valuation engine (robust v2).

Builds sector-aware, cashflow-aware valuation features and scores:
- data/processed/valuation.parquet
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, Tuple

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from src.valuation import (
        AccountingDistortionDetector,
        AdjustedMetricsCalculator,
        DCFEngine,
        EarningsQualityAnalyzer,
        FinancialNormalizer,
        MoatScorer,
        OwnerEarningsCalculator,
        SectorMapper,
    )

    VALUATION_V2_AVAILABLE = True
    VALUATION_V2_IMPORT_ERROR = ""
except Exception as e:  # pragma: no cover
    VALUATION_V2_AVAILABLE = False
    VALUATION_V2_IMPORT_ERROR = str(e)

try:
    from src.valuation import (
        BayesianValuationAggregator,
        CreditFamilyEngine,
        IntrinsicFamilyEngine,
        MacroValuationFamilyEngine,
        PortfolioValuationStateEngine,
        RealOptionsFamilyEngine,
        ResidualIncomeFamilyEngine,
        TransactionFamilyEngine,
    )

    VALUATION_FAMILY_AVAILABLE = True
    VALUATION_FAMILY_IMPORT_ERROR = ""
except Exception as e:  # pragma: no cover
    VALUATION_FAMILY_AVAILABLE = False
    VALUATION_FAMILY_IMPORT_ERROR = str(e)


FUND_FILE = Path("data/processed/fundamentals.parquet")
PRICE_FILE = Path("data/processed/prices.parquet")
UNIVERSE_FILE = Path("universe/nifty500.csv")
OUTPUT_FILE = Path("data/processed/valuation.parquet")
FAMILIES_OUTPUT_FILE = Path("data/processed/valuation_families.parquet")
POSTERIOR_OUTPUT_FILE = Path("data/processed/valuation_posterior.parquet")
STATE_OUTPUT_FILE = Path("data/processed/portfolio_valuation_state.parquet")


FINANCIAL_KEYWORDS = ("financial", "bank", "insurance", "nbfc")


def safe_div(n, d):
    n = pd.to_numeric(n, errors="coerce")
    d = pd.to_numeric(d, errors="coerce")
    out = n / d
    if isinstance(out, (pd.Series, pd.DataFrame)):
        return out.replace([np.inf, -np.inf], np.nan)
    try:
        out_f = float(out)
    except Exception:
        return np.nan
    return out_f if np.isfinite(out_f) else np.nan


def pct_rank_by_industry(df: pd.DataFrame, col: str) -> pd.Series:
    if col not in df.columns:
        return pd.Series(index=df.index, data=0.5)
    return df.groupby("Industry")[col].rank(pct=True).fillna(0.5)


def _is_financial(industry: object) -> bool:
    text = str(industry).lower()
    return any(k in text for k in FINANCIAL_KEYWORDS)


def _f(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
        if not np.isfinite(out):
            return default
        return out
    except Exception:
        return default


def _sum_last(g: pd.DataFrame, col: str, n: int = 4, min_count: int = 2) -> float:
    if col not in g.columns:
        return np.nan
    s = pd.to_numeric(g[col], errors="coerce").dropna().tail(n)
    if len(s) < min_count:
        return np.nan
    return float(s.sum())


def _latest_non_null(g: pd.DataFrame, col: str) -> float:
    if col not in g.columns:
        return np.nan
    s = pd.to_numeric(g[col], errors="coerce").dropna()
    if s.empty:
        return np.nan
    return float(s.iloc[-1])


def _prev_value(g: pd.DataFrame, col: str, quarters_back: int = 1) -> float:
    if col not in g.columns:
        return np.nan
    try:
        s = pd.to_numeric(g[col], errors="coerce").dropna()
        if len(s) <= quarters_back:
            return np.nan
        return _f(s.iloc[-1 - quarters_back], np.nan)
    except Exception:
        return np.nan


def _fill_from_aliases(df: pd.DataFrame, target: str, aliases: list[str]) -> None:
    if target not in df.columns:
        df[target] = np.nan
    out = pd.to_numeric(df[target], errors="coerce")

    normalized_map = {str(c).strip().lower().replace(" ", "_"): c for c in df.columns}
    candidates: list[str] = []
    for alias in aliases:
        candidates.append(alias)
        key = str(alias).strip().lower().replace(" ", "_")
        if key in normalized_map:
            candidates.append(normalized_map[key])

    # Deterministic suffix bridge: _ttm <-> base field.
    if target.endswith("_ttm"):
        base = target[:-4]
        candidates.extend([base, base.lower(), base.upper()])
    else:
        candidates.extend([f"{target}_ttm", f"{target.lower()}_ttm"])

    seen: set[str] = set()
    for c in candidates:
        if c in seen:
            continue
        seen.add(c)
        if c not in df.columns:
            continue
        src = pd.to_numeric(df[c], errors="coerce")
        out = out.where(out.notna(), src)

    df[target] = out


def _normalize_financial_aliases(df: pd.DataFrame) -> pd.DataFrame:
    """
    Deterministic alias bridge so valuation engines work with either raw/non-_ttm
    or *_ttm naming conventions.
    """
    out = df.copy()
    alias_map: dict[str, list[str]] = {
        "revenue": ["total_revenue", "operating_revenue", "Revenue", "Total Revenue"],
        "gross_profit": ["Gross Profit", "grossprofit"],
        "cost_of_revenue": ["Cost Of Revenue", "Cost of Revenue"],
        "ebitda": ["EBITDA", "ebitda_ttm"],
        "operating_income": ["EBIT", "Operating Income", "operating_income_ttm"],
        "net_income": ["Net Income", "Net Income Common Stockholders", "net_income_ttm"],
        "tax_provision": ["Tax Provision", "Tax Expense"],
        "other_income": ["Other Non Operating Income Expenses", "Other Income Expense"],
        "restructuring_charges": ["Restructuring Charges", "Other Special Charges"],
        "impairment_charges": ["Asset Impairment Charge", "Write Off"],
        "bad_debt_expense": ["Provision For Doubtful Accounts", "Bad Debt Expense"],
        "total_assets": ["Total Assets"],
        "equity": ["Stockholders Equity", "Common Stock Equity", "balance_Common Stock Equity"],
        "total_debt": ["Total Debt", "balance_Total Debt", "Net Debt"],
        "minority_interest": ["Minority Interest"],
        "cash_and_equivalents": ["Cash And Cash Equivalents", "Cash", "Cash Financial"],
        "receivables": ["Accounts Receivable", "Gross Accounts Receivable", "Receivables"],
        "inventory": ["Inventory", "Inventories"],
        "payables": ["Payables", "Accounts Payable"],
        "working_capital": ["Working Capital"],
        "deferred_revenue": ["Deferred Revenue", "Current Deferred Revenue", "Non Current Deferred Revenue"],
        "lease_liabilities": ["Capital Lease Obligations", "Long Term Capital Lease Obligation", "Current Capital Lease Obligation"],
        "gross_ppe": ["Gross PPE", "Gross PP&E"],
        "operating_cash_flow": ["Operating Cash Flow", "Net Cash Provided by Operating Activities"],
        "capex": ["Capital Expenditure", "Capital Expenditures", "Purchase Of PPE"],
        "free_cash_flow": ["Free Cash Flow"],
        "shares_outstanding": ["Ordinary Shares Number", "Diluted Average Shares", "Basic Average Shares", "Common Shares Outstanding"],
        "depreciation_amortization": ["Depreciation And Amortization", "Depreciation and amortization"],
        "depreciation": ["Depreciation", "Depreciation Income Statement"],
        "amortization": ["Amortization", "Amortization Cash Flow"],
        "interest_expense": ["Interest Expense", "Net Interest Expense"],
        "change_in_working_capital": ["Change In Working Capital"],
        "interest_paid_cfo": ["Interest Paid Cfo", "Interest Paid CFO"],
        "interest_received_cfo": ["Interest Received Cfo", "Interest Received CFO"],
        "cash_dividends_paid": ["Cash Dividends Paid", "Common Stock Dividend Paid"],
        # Explicit family bridges
        "operating_income_ttm": ["operating_income", "EBIT"],
        "net_income_ttm": ["net_income", "Net Income"],
        "operating_cash_flow_ttm": ["operating_cash_flow"],
        "capex_ttm": ["capex", "Capital Expenditure"],
        "free_cash_flow_ttm": ["free_cash_flow"],
        "depreciation_amortization_ttm": ["depreciation_amortization", "depreciation"],
        "interest_expense_ttm": ["interest_expense"],
    }

    for target, aliases in alias_map.items():
        _fill_from_aliases(out, target, aliases)
    return out


def _history_bundle(g: pd.DataFrame) -> Dict[str, pd.Series]:
    g = g.sort_values("date").copy()
    def _series(col: str) -> pd.Series:
        if col not in g.columns:
            return pd.Series(dtype=float)
        return pd.to_numeric(g[col], errors="coerce")

    revenue = _series("revenue")
    operating_income = _series("operating_income")
    net_income = _series("net_income")
    ocf = _series("operating_cash_flow")
    equity = _series("equity")
    debt = _series("total_debt")
    cash = _series("cash_and_equivalents")
    invested_capital = (equity + debt - cash).replace(0, np.nan)
    roic = safe_div(operating_income * 0.75, invested_capital).replace([np.inf, -np.inf], np.nan).dropna().tail(20)
    gross_profit = _series("gross_profit")
    if gross_profit.notna().sum() > 0:
        gross_margin = safe_div(gross_profit, revenue).dropna().tail(20)
    else:
        gross_margin = safe_div(operating_income, revenue).dropna().tail(20)

    rev_growth = revenue.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan).dropna().tail(20)
    return {
        "roic_history": roic,
        "gross_margin_history": gross_margin,
        "revenue_growth_history": rev_growth,
        "earnings_history": net_income.dropna().tail(20),
        "ocf_history": ocf.dropna().tail(20),
        "revenue_history": revenue.dropna().tail(20),
    }


def _aggregate_quarterly(g: pd.DataFrame) -> Dict[str, float]:
    g = g.sort_values("date").copy()
    out: Dict[str, float] = {}
    last = g.iloc[-1]
    out["date"] = pd.to_datetime(last.get("date"), errors="coerce")
    for c in [
        "revenue",
        "gross_profit",
        "cost_of_revenue",
        "ebitda",
        "operating_income",
        "net_income",
        "total_assets",
        "equity",
        "total_debt",
        "minority_interest",
        "cash_and_equivalents",
        "receivables",
        "inventory",
        "payables",
        "working_capital",
        "deferred_revenue",
        "lease_liabilities",
        "gross_ppe",
        "operating_cash_flow",
        "capex",
        "free_cash_flow",
        "shares_outstanding",
        "depreciation_amortization",
        "depreciation",
        "amortization",
        "interest_expense",
        "change_in_working_capital",
        "other_income",
        "tax_provision",
        "restructuring_charges",
        "impairment_charges",
        "bad_debt_expense",
    ]:
        out[c] = _latest_non_null(g, c)

    out["revenue_ttm"] = _sum_last(g, "revenue", 4, 2)
    out["gross_profit_ttm"] = _sum_last(g, "gross_profit", 4, 2)
    out["cost_of_revenue_ttm"] = _sum_last(g, "cost_of_revenue", 4, 2)
    out["ebitda_ttm"] = _sum_last(g, "ebitda", 4, 2)
    out["operating_income_ttm"] = _sum_last(g, "operating_income", 4, 2)
    out["net_income_ttm"] = _sum_last(g, "net_income", 4, 2)
    out["operating_cash_flow_ttm"] = _sum_last(g, "operating_cash_flow", 4, 2)
    out["capex_ttm"] = _sum_last(g, "capex", 4, 2)
    out["free_cash_flow_ttm"] = _sum_last(g, "free_cash_flow", 4, 2)
    out["depreciation_amortization_ttm"] = _sum_last(g, "depreciation_amortization", 4, 2)
    out["interest_expense_ttm"] = _sum_last(g, "interest_expense", 4, 2)

    revenue_hist = pd.to_numeric(g.get("revenue"), errors="coerce").dropna().tail(20)
    if len(revenue_hist) >= 8:
        out["revenue_prev_ttm"] = float(revenue_hist.iloc[-8:-4].sum())
    else:
        out["revenue_prev_ttm"] = np.nan

    ni_hist = pd.to_numeric(g.get("net_income"), errors="coerce").dropna().tail(20)
    if len(ni_hist) >= 4:
        ni_std = float(ni_hist.std())
        ni_mean = float(np.abs(ni_hist.mean())) + 1e-12
        out["earnings_stability_raw"] = float(max(0.0, 1.0 - min(3.0, ni_std / ni_mean) / 3.0))
    else:
        out["earnings_stability_raw"] = np.nan

    out["maintenance_capex_ttm"] = np.abs(out["capex_ttm"]) * 0.7 if np.isfinite(out["capex_ttm"]) else np.nan
    out["owner_earnings_ttm"] = (
        out["net_income_ttm"]
        + (out["depreciation_amortization_ttm"] if np.isfinite(out["depreciation_amortization_ttm"]) else 0.0)
        - (out["maintenance_capex_ttm"] if np.isfinite(out["maintenance_capex_ttm"]) else 0.0)
    )

    # Prior-quarter forensic fields.
    out["revenue_prev_q"] = _prev_value(g, "revenue", 1)
    out["receivables_prev_q"] = _prev_value(g, "receivables", 1)
    out["inventory_prev_q"] = _prev_value(g, "inventory", 1)
    out["payables_prev_q"] = _prev_value(g, "payables", 1)
    out["deferred_revenue_prev_q"] = _prev_value(g, "deferred_revenue", 1)
    out["gross_profit_prev_q"] = _prev_value(g, "gross_profit", 1)
    out["total_assets_prev_q"] = _prev_value(g, "total_assets", 1)
    out["gross_ppe_prev_q"] = _prev_value(g, "gross_ppe", 1)
    out["depreciation_prev_q"] = _prev_value(g, "depreciation", 1)
    out["bad_debt_expense_prev_q"] = _prev_value(g, "bad_debt_expense", 1)
    out["restructuring_charges_prev_q"] = _prev_value(g, "restructuring_charges", 1)
    return out


def _apply_v2_modules(df: pd.DataFrame, history_by_ticker: Dict[str, Dict[str, pd.Series]]) -> pd.DataFrame:
    out = df.copy()
    if not VALUATION_V2_AVAILABLE:
        out["valuation_v2_status"] = f"unavailable:{VALUATION_V2_IMPORT_ERROR[:200]}"
        out["forensic_penalty"] = (1.0 - out["cashflow_quality_score"].fillna(0.5)).clip(lower=0, upper=1) * 100.0
        out["dcf_margin_of_safety_v2_pct"] = out["margin_of_safety_pct"].fillna(0.5)
        out["moat_score_v2"] = 50.0
        out["owner_earnings_quality_v2"] = 50.0
        out["earnings_quality_score_v2"] = 50.0
        out["distortion_severity_v2"] = 50.0
        out["institutional_sector_overlay"] = out["institutional_value_score"].fillna(50.0)
        out["buffett_overlay_score_v2"] = out["buffett_quality_score"].fillna(50.0)
        out["sector_category"] = "unknown"
        out["valuation_framework"] = "standard"
        return out

    sector_mapper = SectorMapper()
    normalizer = FinancialNormalizer()
    metrics_calc = AdjustedMetricsCalculator()
    quality_analyzer = EarningsQualityAnalyzer()
    distortion_detector = AccountingDistortionDetector()
    owner_earnings_calc = OwnerEarningsCalculator()
    moat_scorer = MoatScorer()
    dcf_engine = DCFEngine()

    out = sector_mapper.map_dataframe(out, industry_col="Industry")
    module_rows: list[dict[str, Any]] = []

    for _, row in out.iterrows():
        ticker = row.get("ticker")
        history = history_by_ticker.get(str(ticker), {})
        revenue = _f(row.get("revenue_ttm"))
        gross_profit = _f(row.get("gross_profit_ttm"), revenue - _f(row.get("cost_of_revenue_ttm")))
        if gross_profit == 0 and revenue > 0:
            gross_profit = revenue - _f(row.get("cost_of_revenue_ttm"))

        normalized = normalizer.normalize_financials(
            ticker=str(ticker),
            sector=str(row.get("sector_category", "consumer")).title(),
            revenue=revenue,
            ebit=_f(row.get("operating_income_ttm")),
            ebitda=_f(row.get("ebitda_ttm")),
            capex=abs(_f(row.get("capex_ttm"))),
            depreciation=abs(_f(row.get("depreciation_amortization_ttm"))),
            amortization=abs(_f(row.get("amortization"), 0.0)),
            rd_expense=0.0,
            capitalized_rd=0.0,
            rd_amortization=0.0,
            receivables=_f(row.get("receivables")),
            inventory=_f(row.get("inventory")),
            payables=_f(row.get("payables")),
            deferred_revenue=_f(row.get("deferred_revenue")),
            lease_liabilities=_f(row.get("lease_liabilities")),
            gross_ppe=max(_f(row.get("gross_ppe")), 1.0),
        )

        working_capital = _f(row.get("working_capital"), np.nan)
        if not np.isfinite(working_capital):
            working_capital = _f(row.get("receivables")) + _f(row.get("inventory")) - _f(row.get("payables"))

        adjusted_metrics = metrics_calc.calculate_all_metrics(
            revenue=normalized.adjusted_revenue,
            adjusted_ebit=normalized.adjusted_ebit,
            net_income=_f(row.get("net_income_ttm")),
            depreciation=abs(_f(row.get("depreciation_amortization_ttm"))),
            amortization=abs(_f(row.get("amortization"))),
            equity=max(_f(row.get("equity")), 0.0),
            debt=max(_f(row.get("total_debt")), 0.0),
            cash=max(_f(row.get("cash_and_equivalents")), 0.0),
            excess_cash=max(_f(row.get("cash_and_equivalents")) * 0.5, 0.0),
            lease_liabilities=max(_f(row.get("lease_liabilities")), 0.0),
            capitalized_rd=0.0,
            operating_cash_flow=_f(row.get("operating_cash_flow_ttm")),
            capex=abs(_f(row.get("capex_ttm"))),
            maintenance_capex=max(normalized.maintenance_capex, 0.0),
            working_capital_increase=max(_f(row.get("change_in_working_capital")), 0.0),
            market_cap=max(_f(row.get("market_cap")), 0.0),
            tax_rate=np.clip(_f(row.get("tax_provision"), 0.25), 0.05, 0.40),
            one_time_items=_f(row.get("restructuring_charges")) + _f(row.get("impairment_charges")),
            minority_interest=max(_f(row.get("minority_interest")), 0.0),
        )

        quality = quality_analyzer.analyze_earnings_quality(
            net_income=_f(row.get("net_income_ttm")),
            operating_cash_flow=_f(row.get("operating_cash_flow_ttm")),
            total_assets=max(_f(row.get("total_assets")), 1.0),
            receivables=_f(row.get("receivables")),
            revenue=revenue,
            gross_profit=gross_profit,
            ppe=max(_f(row.get("gross_ppe")), 1.0),
            depreciation=abs(_f(row.get("depreciation"))),
            sga=0.0,
            receivables_prior=_f(row.get("receivables_prev_q")),
            revenue_prior=_f(row.get("revenue_prev_q")),
            gross_profit_prior=_f(row.get("gross_profit_prev_q")),
            total_assets_prior=_f(row.get("total_assets_prev_q")),
            ppe_prior=_f(row.get("gross_ppe_prev_q")),
            depreciation_prior=_f(row.get("depreciation_prev_q")),
            sga_prior=0.0,
            earnings_history=history.get("earnings_history"),
            ocf_history=history.get("ocf_history"),
            revenue_history=history.get("revenue_history"),
        )

        distortion = distortion_detector.comprehensive_distortion_analysis(
            revenue=revenue,
            revenue_prior=_f(row.get("revenue_prev_q")),
            receivables=_f(row.get("receivables")),
            receivables_prior=_f(row.get("receivables_prev_q")),
            deferred_revenue=_f(row.get("deferred_revenue")),
            deferred_revenue_prior=_f(row.get("deferred_revenue_prev_q")),
            cash_from_customers=max(_f(row.get("operating_cash_flow_ttm")), 0.0),
            capex=abs(_f(row.get("capex_ttm"))),
            capex_prior=abs(_f(row.get("capex_ttm")) * 0.8),
            depreciation=abs(_f(row.get("depreciation"))),
            rd_capitalized=0.0,
            software_capitalized=0.0,
            restructuring_charges=_f(row.get("restructuring_charges")),
            restructuring_charges_prior=_f(row.get("restructuring_charges_prev_q")),
            impairment_charges=_f(row.get("impairment_charges")),
            warranty_reserves=0.0,
            warranty_reserves_prior=0.0,
            bad_debt_expense=_f(row.get("bad_debt_expense")),
            bad_debt_expense_prior=_f(row.get("bad_debt_expense_prev_q")),
            inventory=_f(row.get("inventory")),
            inventory_prior=_f(row.get("inventory_prev_q")),
            payables=_f(row.get("payables")),
            payables_prior=_f(row.get("payables_prev_q")),
            cogs=max(_f(row.get("cost_of_revenue_ttm")), 1.0),
            cogs_prior=max(_f(row.get("cost_of_revenue_ttm")) * 0.85, 1.0),
        )

        owner_earnings = owner_earnings_calc.calculate_owner_earnings(
            net_income=_f(row.get("net_income_ttm")),
            depreciation=abs(_f(row.get("depreciation"))),
            amortization=abs(_f(row.get("amortization"))),
            total_capex=abs(_f(row.get("capex_ttm"))),
            maintenance_capex=max(normalized.maintenance_capex, 0.0),
            current_wc=working_capital,
            prior_wc=_f(row.get("receivables_prev_q")) + _f(row.get("inventory_prev_q")) - _f(row.get("payables_prev_q")),
            revenue=revenue,
            revenue_prior=_f(row.get("revenue_prev_q")),
            revenue_growth=_f(row.get("revenue_growth")),
            restructuring_charges=_f(row.get("restructuring_charges")),
            impairment_charges=_f(row.get("impairment_charges")),
            gain_on_sale=0.0,
            other_income=_f(row.get("other_income")),
            shares_outstanding=max(_f(row.get("shares_outstanding")), 1.0),
            market_cap=max(_f(row.get("market_cap")), 1.0),
            sector=str(row.get("sector_category", "Unknown")).title(),
        )

        roic_history = history.get("roic_history")
        gross_margin_history = history.get("gross_margin_history")
        rev_growth_history = history.get("revenue_growth_history")
        if roic_history is None or len(roic_history) == 0:
            roic_history = pd.Series([adjusted_metrics.adjusted_roic] * 5)
        if gross_margin_history is None or len(gross_margin_history) == 0:
            gross_margin_history = pd.Series([safe_div(gross_profit, revenue) if revenue > 0 else 0.2] * 5)
        if rev_growth_history is None or len(rev_growth_history) == 0:
            rev_growth_history = pd.Series([_f(row.get("revenue_growth"), 0.02)] * 5)

        moat = moat_scorer.assess_moat(
            roic_history=pd.to_numeric(roic_history, errors="coerce").dropna(),
            gross_margin_history=pd.to_numeric(gross_margin_history, errors="coerce").dropna(),
            revenue_growth_history=pd.to_numeric(rev_growth_history, errors="coerce").dropna(),
            customer_concentration=0.30,
            contract_length_years=1.0,
            recurring_revenue_pct=0.20,
            customer_retention_rate=0.80,
            market_share=0.10,
            market_share_trend=0.0,
            user_growth_rate=max(_f(row.get("revenue_growth")), -0.20),
            platform_indicator=str(row.get("sector_category", "")).lower() == "technology",
            operating_margin=safe_div(_f(row.get("operating_income_ttm")), revenue) if revenue > 0 else 0.10,
            operating_margin_vs_peers=0.0,
            scale_indicator=0.50,
            vertical_integration=False,
        )

        dcf_result = dcf_engine.buffett_style_valuation(
            owner_earnings=owner_earnings.owner_earnings,
            roic_10y_avg=float(pd.to_numeric(roic_history, errors="coerce").dropna().mean() or adjusted_metrics.adjusted_roic),
            revenue_growth_5y=float(pd.to_numeric(rev_growth_history, errors="coerce").dropna().mean() or _f(row.get("revenue_growth"), 0.02)),
            shares_outstanding=max(_f(row.get("shares_outstanding")), 1.0),
            current_price=max(_f(row.get("Close")), 0.01),
            sector=str(row.get("sector_category", "Unknown")).title(),
            quality_score=quality.overall_score,
        )

        module_rows.append(
            {
                "ticker": ticker,
                "adjusted_revenue_v2": normalized.adjusted_revenue,
                "adjusted_ebit_v2": normalized.adjusted_ebit,
                "adjusted_ebitda_v2": normalized.adjusted_ebitda,
                "maintenance_capex_v2": normalized.maintenance_capex,
                "growth_capex_v2": normalized.growth_capex,
                "adjusted_working_capital_v2": normalized.adjusted_working_capital,
                "adjusted_roic_v2": adjusted_metrics.adjusted_roic,
                "adjusted_roe_v2": adjusted_metrics.adjusted_roe,
                "ev_adjusted_v2": adjusted_metrics.ev_adjusted,
                "owner_earnings_v2": owner_earnings.owner_earnings,
                "owner_earnings_yield_v2": owner_earnings.owner_earnings_yield,
                "owner_earnings_quality_v2": owner_earnings.quality_score,
                "earnings_quality_score_v2": quality.overall_score,
                "earnings_quality_grade_v2": quality.quality_grade,
                "earnings_red_flags_v2": len(quality.red_flags),
                "distortion_severity_v2": distortion.severity_score,
                "distortion_count_v2": len(distortion.distortions_found),
                "moat_score_v2": moat.overall_score,
                "moat_width_v2": moat.moat_width,
                "dcf_intrinsic_value_per_share_v2": dcf_result.intrinsic_value_per_share,
                "dcf_margin_of_safety_v2": dcf_result.margin_of_safety_pct,
                "dcf_upside_v2": dcf_result.upside_potential,
                "dcf_grade_v2": dcf_result.valuation_grade,
            }
        )

    v2 = pd.DataFrame(module_rows)
    out = out.merge(v2, on="ticker", how="left")
    out["valuation_v2_status"] = "ok"

    # Normalize module outputs for composite integration.
    for col in [
        "moat_score_v2",
        "owner_earnings_quality_v2",
        "earnings_quality_score_v2",
        "distortion_severity_v2",
        "dcf_margin_of_safety_v2",
    ]:
        out[col] = pd.to_numeric(out[col], errors="coerce")

    out["moat_score_v2_pct"] = pct_rank_by_industry(out, "moat_score_v2")
    out["owner_earnings_quality_v2_pct"] = pct_rank_by_industry(out, "owner_earnings_quality_v2")
    out["earnings_quality_score_v2_pct"] = pct_rank_by_industry(out, "earnings_quality_score_v2")
    out["distortion_severity_v2_pct"] = pct_rank_by_industry(out, "distortion_severity_v2")

    # Clip MoS into [-1, 1] then convert to [0,1] rank style.
    out["dcf_margin_of_safety_v2"] = out["dcf_margin_of_safety_v2"].clip(lower=-1, upper=1)
    out["dcf_margin_of_safety_v2_pct"] = ((out["dcf_margin_of_safety_v2"].fillna(0.0) + 1.0) / 2.0).clip(0, 1)

    out["forensic_penalty"] = (
        0.60 * (100.0 - out["earnings_quality_score_v2"].fillna(50.0))
        + 0.40 * out["distortion_severity_v2"].fillna(50.0)
    ).clip(lower=0, upper=100)
    out["institutional_sector_overlay"] = (
        (
            out["earnings_quality_score_v2_pct"].fillna(0.5)
            + (1.0 - out["distortion_severity_v2_pct"].fillna(0.5))
            + out["moat_score_v2_pct"].fillna(0.5)
        )
        / 3.0
    ) * 100.0
    out["buffett_overlay_score_v2"] = (
        0.45 * out["moat_score_v2"].fillna(50.0)
        + 0.35 * out["owner_earnings_quality_v2"].fillna(50.0)
        + 0.20 * (out["dcf_margin_of_safety_v2_pct"].fillna(0.5) * 100.0)
    ).clip(lower=0, upper=100)

    # Keep moat width categorical output robust even if upstream width labels are blank.
    moat_width_raw = (
        out.get("moat_width_v2", pd.Series(index=out.index, dtype="object"))
        .astype(str)
        .str.strip()
        .replace({"nan": np.nan, "NaN": np.nan, "None": np.nan, "<NA>": np.nan, "": np.nan})
    )
    moat_score_for_width = pd.to_numeric(out.get("moat_score_v2"), errors="coerce")
    moat_width_fallback = pd.Series(
        np.where(
            moat_score_for_width >= 75,
            "Wide",
            np.where(moat_score_for_width >= 55, "Narrow", "None"),
        ),
        index=out.index,
    )
    out["moat_width_v2"] = moat_width_raw.where(moat_width_raw.notna(), moat_width_fallback)
    return out


def _core_gap_from_index(core_df: pd.DataFrame) -> pd.Series:
    return ((pd.to_numeric(core_df.get("final_value_index"), errors="coerce").fillna(50.0) / 100.0) - 0.5) * 2.0


def _normalize_posterior_output(
    posterior_df: pd.DataFrame,
    core_df: pd.DataFrame,
    reference_value: pd.Series,
) -> pd.DataFrame:
    """
    Ensure strict non-null and bounded posterior outputs for schema gates.
    """
    out = core_df[["ticker", "date"]].copy()
    if isinstance(posterior_df, pd.DataFrame) and not posterior_df.empty:
        cols = [c for c in posterior_df.columns if c in [
            "ticker",
            "date",
            "posterior_gap",
            "posterior_value",
            "posterior_variance",
            "model_dispersion",
            "agreement_score",
            "regime_modifier",
            "macro_compression",
            "posterior_confidence",
            "regime_low_vol_prob",
            "regime_normal_prob",
            "regime_crisis_prob",
        ]]
        if cols:
            out = out.merge(posterior_df[cols], on=["ticker", "date"], how="left")

    core_gap = _core_gap_from_index(core_df)
    out["posterior_gap"] = pd.to_numeric(out.get("posterior_gap"), errors="coerce").fillna(core_gap).clip(lower=-2.0, upper=2.0)
    out["posterior_variance"] = pd.to_numeric(out.get("posterior_variance"), errors="coerce").fillna(0.25).clip(lower=1e-8, upper=100.0)
    out["model_dispersion"] = pd.to_numeric(out.get("model_dispersion"), errors="coerce").fillna(0.0).clip(lower=0.0, upper=100.0)
    out["agreement_score"] = pd.to_numeric(out.get("agreement_score"), errors="coerce").fillna(0.50).clip(lower=0.0, upper=1.0)
    out["regime_modifier"] = pd.to_numeric(out.get("regime_modifier"), errors="coerce").fillna(1.0).clip(lower=0.1, upper=3.0)
    out["macro_compression"] = pd.to_numeric(out.get("macro_compression"), errors="coerce").fillna(1.0).clip(lower=0.5, upper=1.5)
    out["posterior_confidence"] = pd.to_numeric(out.get("posterior_confidence"), errors="coerce").fillna(0.20).clip(lower=0.0, upper=1.0)
    out["regime_low_vol_prob"] = pd.to_numeric(out.get("regime_low_vol_prob"), errors="coerce").fillna(0.33).clip(lower=0.0, upper=1.0)
    out["regime_normal_prob"] = pd.to_numeric(out.get("regime_normal_prob"), errors="coerce").fillna(0.34).clip(lower=0.0, upper=1.0)
    out["regime_crisis_prob"] = pd.to_numeric(out.get("regime_crisis_prob"), errors="coerce").fillna(0.33).clip(lower=0.0, upper=1.0)

    probs_sum = out["regime_low_vol_prob"] + out["regime_normal_prob"] + out["regime_crisis_prob"]
    probs_sum = probs_sum.replace(0, np.nan)
    out["regime_low_vol_prob"] = (out["regime_low_vol_prob"] / probs_sum).fillna(0.33)
    out["regime_normal_prob"] = (out["regime_normal_prob"] / probs_sum).fillna(0.34)
    out["regime_crisis_prob"] = (out["regime_crisis_prob"] / probs_sum).fillna(0.33)

    ref = pd.to_numeric(reference_value, errors="coerce")
    out["posterior_value"] = pd.to_numeric(out.get("posterior_value"), errors="coerce")
    missing_val = out["posterior_value"].isna() & ref.notna()
    out.loc[missing_val, "posterior_value"] = ref[missing_val] * (1.0 + out.loc[missing_val, "posterior_gap"])
    return out


def _build_family_outputs(
    core_df: pd.DataFrame,
    history_by_ticker: Dict[str, Dict[str, pd.Series]],
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Build family-level valuation, Bayesian posterior, and portfolio valuation state.
    Falls back safely so legacy valuation output remains available even if family
    modules fail.
    """
    if not VALUATION_FAMILY_AVAILABLE:
        fallback_families = core_df[["ticker", "date", "Industry"]].copy()
        fallback_families["family_status"] = f"unavailable:{VALUATION_FAMILY_IMPORT_ERROR[:200]}"
        reference_value = pd.to_numeric(core_df.get("market_cap"), errors="coerce")
        fallback_families["reference_value"] = reference_value
        fallback_posterior = _normalize_posterior_output(pd.DataFrame(), core_df=core_df, reference_value=reference_value)
        fallback_state = pd.DataFrame(
            [
                {
                    "date": pd.to_datetime(core_df.get("date"), errors="coerce").max(),
                    "market_percentile": np.nan,
                    "sector_dispersion": np.nan,
                    "aggregate_gap_mean": np.nan,
                    "aggregate_gap_std": np.nan,
                    "bubble_probability": np.nan,
                    "valuation_regime": "unknown",
                    "state_status": f"unavailable:{VALUATION_FAMILY_IMPORT_ERROR[:200]}",
                }
            ]
        )
        return fallback_families, fallback_posterior, fallback_state

    try:
        intrinsic_engine = IntrinsicFamilyEngine()
        residual_engine = ResidualIncomeFamilyEngine()
        transaction_engine = TransactionFamilyEngine()
        macro_engine = MacroValuationFamilyEngine()
        credit_engine = CreditFamilyEngine()
        real_options_engine = RealOptionsFamilyEngine()
        aggregator = BayesianValuationAggregator()
        state_engine = PortfolioValuationStateEngine()

        intrinsic_df = intrinsic_engine.run(core_df, history_by_ticker)
        residual_df = residual_engine.run(core_df)
        transaction_df = transaction_engine.run(core_df)
        macro_df, macro_state_df = macro_engine.annotate(core_df)
        credit_df = credit_engine.run(core_df)
        real_options_df = real_options_engine.run(core_df)

        families_df = intrinsic_df.merge(residual_df, on="ticker", how="left")
        families_df = families_df.merge(transaction_df, on="ticker", how="left")
        families_df = families_df.merge(credit_df, on="ticker", how="left")
        families_df = families_df.merge(real_options_df, on="ticker", how="left")
        families_df = families_df.merge(macro_df, on="ticker", how="left")
        families_df = families_df.merge(core_df[["ticker", "Industry"]], on="ticker", how="left")
        families_df["family_status"] = "ok"
        reference_value = pd.to_numeric(families_df.get("reference_value"), errors="coerce")
        if reference_value.isna().all():
            reference_value = pd.to_numeric(core_df.get("market_cap"), errors="coerce")
            families_df["reference_value"] = reference_value

        # Robust fallback when market-cap reference is sparse:
        # derive a consistent reference from available family values so gap fields
        # remain informative instead of mostly null.
        value_cols = [
            "core_value",
            "fcff_value",
            "fcfe_value",
            "ddm_value",
            "apv_value",
            "residual_value",
            "transaction_value",
            "lbo_value",
            "credit_value",
            "real_option_value",
        ]
        present_value_cols = [c for c in value_cols if c in families_df.columns]
        if present_value_cols:
            value_frame = families_df[present_value_cols].apply(pd.to_numeric, errors="coerce")
            fallback_reference = value_frame.median(axis=1, skipna=True)
            reference_value = pd.to_numeric(families_df.get("reference_value"), errors="coerce")
            reference_value = reference_value.where(reference_value > 0.0, fallback_reference)
            reference_value = reference_value.where(reference_value > 0.0, np.nan)
            families_df["reference_value"] = reference_value

            if "core_value" in families_df.columns:
                core_value = pd.to_numeric(families_df["core_value"], errors="coerce")
                families_df["core_value"] = core_value.fillna(reference_value)

            gap_pairs = [
                ("core_value", "core_gap"),
                ("fcff_value", "fcff_gap"),
                ("fcfe_value", "fcfe_gap"),
                ("ddm_value", "ddm_gap"),
                ("apv_value", "apv_gap"),
                ("residual_value", "residual_gap"),
                ("transaction_value", "transaction_gap"),
                ("lbo_value", "lbo_gap"),
                ("credit_value", "credit_gap"),
                ("real_option_value", "real_option_gap"),
            ]
            valid_ref = reference_value.where(reference_value > 0.0, np.nan)
            for value_col, gap_col in gap_pairs:
                if value_col in families_df.columns and gap_col in families_df.columns:
                    val = pd.to_numeric(families_df[value_col], errors="coerce")
                    gap_existing = pd.to_numeric(families_df[gap_col], errors="coerce")
                    gap_fallback = ((val - valid_ref) / valid_ref).clip(lower=-2.0, upper=2.0)
                    families_df[gap_col] = gap_existing.fillna(gap_fallback)

            for col in [
                "core_confidence",
                "fcff_confidence",
                "fcfe_confidence",
                "ddm_confidence",
                "apv_confidence",
                "residual_confidence",
                "transaction_confidence",
                "lbo_confidence",
                "credit_confidence",
                "real_option_confidence",
            ]:
                if col in families_df.columns:
                    families_df[col] = pd.to_numeric(families_df[col], errors="coerce").fillna(0.20).clip(lower=0.0, upper=1.0)

            for col in [
                "core_variance",
                "fcff_variance",
                "fcfe_variance",
                "ddm_variance",
                "apv_variance",
                "residual_variance",
                "transaction_variance",
                "lbo_variance",
                "credit_variance",
                "real_option_variance",
            ]:
                if col in families_df.columns:
                    families_df[col] = pd.to_numeric(families_df[col], errors="coerce").fillna(1.0).clip(lower=1e-8, upper=100.0)

            # Hard guarantee: keep family gaps non-null for every ticker.
            core_gap_map = pd.Series(
                _core_gap_from_index(core_df).to_numpy(dtype=float),
                index=core_df["ticker"].astype(str),
            )
            core_gap_fallback = (
                families_df["ticker"].astype(str).map(core_gap_map).astype(float).fillna(0.0).clip(lower=-2.0, upper=2.0)
            )
            families_df["core_gap"] = pd.to_numeric(families_df.get("core_gap"), errors="coerce").fillna(core_gap_fallback).clip(lower=-2.0, upper=2.0)

            required_gap_cols = [
                "fcff_gap",
                "fcfe_gap",
                "ddm_gap",
                "apv_gap",
                "residual_gap",
                "transaction_gap",
                "lbo_gap",
                "credit_gap",
                "real_option_gap",
            ]
            for gap_col in required_gap_cols:
                if gap_col not in families_df.columns:
                    families_df[gap_col] = core_gap_fallback
                else:
                    families_df[gap_col] = (
                        pd.to_numeric(families_df[gap_col], errors="coerce")
                        .fillna(core_gap_fallback)
                        .clip(lower=-2.0, upper=2.0)
                    )

            # Keep companion value columns populated from reference × (1 + gap) when absent.
            value_gap_pairs = [
                ("fcff_value", "fcff_gap"),
                ("fcfe_value", "fcfe_gap"),
                ("ddm_value", "ddm_gap"),
                ("apv_value", "apv_gap"),
                ("residual_value", "residual_gap"),
                ("transaction_value", "transaction_gap"),
                ("lbo_value", "lbo_gap"),
                ("credit_value", "credit_gap"),
                ("real_option_value", "real_option_gap"),
            ]
            ref_nonnull = pd.to_numeric(families_df.get("reference_value"), errors="coerce").fillna(0.0)
            for value_col, gap_col in value_gap_pairs:
                target_from_gap = ref_nonnull * (1.0 + pd.to_numeric(families_df[gap_col], errors="coerce").fillna(0.0))
                if value_col not in families_df.columns:
                    families_df[value_col] = target_from_gap
                else:
                    families_df[value_col] = pd.to_numeric(families_df[value_col], errors="coerce").fillna(target_from_gap)

            # Backward-compatible aliases occasionally used in downstream notebooks/dashboards.
            families_df["adv_gap"] = pd.to_numeric(families_df.get("apv_gap"), errors="coerce").fillna(core_gap_fallback)
            families_df["ibo_gap"] = pd.to_numeric(families_df.get("lbo_gap"), errors="coerce").fillna(core_gap_fallback)

            reference_value = pd.to_numeric(families_df.get("reference_value"), errors="coerce")

        posterior_df = aggregator.combine(families_df)
        posterior_df = _normalize_posterior_output(posterior_df, core_df=core_df, reference_value=reference_value)
        state_df = state_engine.compute(
            posterior_df=posterior_df,
            families_df=families_df,
            macro_state_df=macro_state_df,
            industry_col="Industry",
        )
        state_df["state_status"] = "ok"
        return families_df, posterior_df, state_df
    except Exception as e:
        fallback_families = core_df[["ticker", "date", "Industry"]].copy()
        fallback_families["family_status"] = f"error:{str(e)[:200]}"
        reference_value = pd.to_numeric(core_df.get("market_cap"), errors="coerce")
        fallback_families["reference_value"] = reference_value
        fallback_posterior = _normalize_posterior_output(pd.DataFrame(), core_df=core_df, reference_value=reference_value)
        fallback_state = pd.DataFrame(
            [
                {
                    "date": pd.to_datetime(core_df.get("date"), errors="coerce").max(),
                    "market_percentile": np.nan,
                    "sector_dispersion": np.nan,
                    "aggregate_gap_mean": np.nan,
                    "aggregate_gap_std": np.nan,
                    "bubble_probability": np.nan,
                    "valuation_regime": "unknown",
                    "state_status": f"error:{str(e)[:200]}",
                }
            ]
        )
        return fallback_families, fallback_posterior, fallback_state


def build_valuation_bundle(
    fund_path: Path,
    price_path: Path,
    universe_path: Path,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    fundamentals = pd.read_parquet(fund_path).copy()
    fundamentals = _normalize_financial_aliases(fundamentals)
    fundamentals["date"] = pd.to_datetime(fundamentals["date"], errors="coerce")
    fundamentals = fundamentals.dropna(subset=["ticker", "date"]).sort_values(["ticker", "date"])

    rows: list[dict[str, Any]] = []
    history_by_ticker: Dict[str, Dict[str, pd.Series]] = {}
    for ticker, g in fundamentals.groupby("ticker", sort=False):
        rec = _aggregate_quarterly(g)
        rec["ticker"] = ticker
        rows.append(rec)
        history_by_ticker[ticker] = _history_bundle(g)
    agg = pd.DataFrame(rows)

    prices = pd.read_parquet(price_path).copy()
    prices["Date"] = pd.to_datetime(prices["Date"], errors="coerce")
    latest_price = prices.sort_values("Date").groupby("ticker", as_index=False).tail(1)[["ticker", "Close"]]

    universe = pd.read_csv(universe_path).copy()
    universe["ticker"] = universe["Symbol"].astype(str).str.upper().map(
        lambda s: s if s.endswith(".NS") else f"{s}.NS"
    )
    industry_cols = [c for c in ["Industry", "Sector", "sector", "industry"] if c in universe.columns]
    ind_col = industry_cols[0] if industry_cols else None
    if ind_col:
        industry = universe[["ticker", ind_col]].rename(columns={ind_col: "Industry"})
    else:
        industry = universe[["ticker"]].copy()
        industry["Industry"] = "Unknown"

    df = agg.merge(latest_price, on="ticker", how="left").merge(industry, on="ticker", how="left")
    df = _normalize_financial_aliases(df)
    df["Industry"] = df["Industry"].fillna("Unknown")

    # Growth
    df["revenue_growth"] = safe_div(df["revenue_ttm"] - df["revenue_prev_ttm"], df["revenue_prev_ttm"])

    # Core capital structure
    df["market_cap"] = pd.to_numeric(df["Close"], errors="coerce") * pd.to_numeric(df["shares_outstanding"], errors="coerce")
    df["enterprise_value"] = (
        pd.to_numeric(df["market_cap"], errors="coerce")
        + pd.to_numeric(df["total_debt"], errors="coerce")
        - pd.to_numeric(df["cash_and_equivalents"], errors="coerce")
    )

    # Ratios (TTM-first)
    df["pe"] = safe_div(df["market_cap"], df["net_income_ttm"]).clip(lower=-120, upper=250)
    df["pb"] = safe_div(df["market_cap"], df["equity"]).clip(lower=-30, upper=60)
    df["ev_ebitda"] = safe_div(df["enterprise_value"], df["ebitda_ttm"]).clip(lower=-120, upper=200)
    df["ev_sales"] = safe_div(df["enterprise_value"], df["revenue_ttm"]).clip(lower=-50, upper=80)
    df["fcf_yield"] = safe_div(df["free_cash_flow_ttm"], df["market_cap"]).clip(lower=-2, upper=2)
    df["cfo_yield"] = safe_div(df["operating_cash_flow_ttm"], df["market_cap"]).clip(lower=-2, upper=2)
    df["owner_earnings_yield"] = safe_div(df["owner_earnings_ttm"], df["market_cap"]).clip(lower=-2, upper=2)
    growth_denom = df["revenue_growth"].where(df["revenue_growth"].abs() > 1e-6)
    df["peg"] = safe_div(df["pe"], growth_denom * 100).clip(lower=-30, upper=30)
    df["roe"] = safe_div(df["net_income_ttm"], df["equity"]).clip(lower=-2, upper=2)
    df["debt_equity"] = safe_div(df["total_debt"], df["equity"]).clip(lower=0, upper=12)
    df["cash_to_debt"] = safe_div(df["cash_and_equivalents"], df["total_debt"]).clip(lower=0, upper=5)
    df["fcf_conversion"] = safe_div(df["free_cash_flow_ttm"], df["net_income_ttm"]).clip(lower=-3, upper=3)
    df["cfo_to_ni"] = safe_div(df["operating_cash_flow_ttm"], df["net_income_ttm"]).clip(lower=-3, upper=3)
    # Accruals (Sloan 1996 accrual anomaly): (Net_Income − Operating_Cash_Flow)
    # / Total_Assets. HIGH accruals = earnings not backed by cash = lower earnings
    # quality → historically LOWER future returns. This holds in Indian equities
    # as in most markets. The balance_sheet_score below therefore uses
    # (1 − accrual_ratio_pct), i.e. it PENALISES high accruals — the standard,
    # validated direction. (A prior comment here claimed India inverts this and
    # said "do not invert", but the code has always penalised high accruals and
    # that unverified inversion claim contradicted both the code and the
    # literature; comment corrected 2026-07 to match the actual, correct code.)
    df["accrual_ratio"] = safe_div(
        pd.to_numeric(df["net_income_ttm"], errors="coerce") - pd.to_numeric(df["operating_cash_flow_ttm"], errors="coerce"),
        df["total_assets"],
    ).clip(lower=-1, upper=1)

    # Sector-aware ranking
    rank_cols = [
        "pe", "pb", "ev_ebitda", "ev_sales", "fcf_yield", "cfo_yield", "owner_earnings_yield",
        "peg", "roe", "debt_equity", "cash_to_debt", "fcf_conversion", "cfo_to_ni",
        "accrual_ratio", "revenue_growth", "earnings_stability_raw",
    ]
    for c in rank_cols:
        df[f"{c}_pct"] = pct_rank_by_industry(df, c)

    # Core component scores [0,1]
    df["valuation_multiple_score"] = (
        (1 - df["pe_pct"]) + (1 - df["pb_pct"]) + (1 - df["ev_ebitda_pct"]) + (1 - df["ev_sales_pct"])
    ) / 4.0
    df["cashflow_quality_score"] = (
        df["fcf_yield_pct"] + df["cfo_yield_pct"] + df["fcf_conversion_pct"] + df["cfo_to_ni_pct"]
    ) / 4.0
    df["balance_sheet_score"] = (
        df["roe_pct"] + (1 - df["debt_equity_pct"]) + df["cash_to_debt_pct"] + (1 - df["accrual_ratio_pct"])
    ) / 4.0
    df["growth_score"] = (
        0.42 * df["revenue_growth_pct"].fillna(0.5)
        + 0.28 * (1 - df["peg_pct"]).fillna(0.5)
        + 0.20 * df["earnings_stability_raw_pct"].fillna(0.5)
        + 0.10 * df["owner_earnings_yield_pct"].fillna(0.5)
    ).clip(lower=0.0, upper=1.0)
    # Guard against degenerate growth composites when one percentile family collapses.
    if float(pd.to_numeric(df["growth_score"], errors="coerce").std(skipna=True) or 0.0) < 1e-4:
        df["growth_score"] = (
            0.50 * df["revenue_growth_pct"].fillna(0.5)
            + 0.30 * df["roe_pct"].fillna(0.5)
            + 0.20 * df["cfo_to_ni_pct"].fillna(0.5)
        ).clip(lower=0.0, upper=1.0)

    df["is_financial"] = df["Industry"].map(_is_financial)
    non_fin = ~df["is_financial"]

    # Institutional score (sector-aware)
    df["institutional_value_score_raw"] = np.nan
    df.loc[non_fin, "institutional_value_score_raw"] = (
        0.28 * df.loc[non_fin, "valuation_multiple_score"]
        + 0.27 * df.loc[non_fin, "cashflow_quality_score"]
        + 0.23 * df.loc[non_fin, "balance_sheet_score"]
        + 0.22 * df.loc[non_fin, "growth_score"]
    )
    df.loc[~non_fin, "institutional_value_score_raw"] = (
        0.45 * (1 - df.loc[~non_fin, "pb_pct"])
        + 0.30 * df.loc[~non_fin, "roe_pct"]
        + 0.15 * (1 - df.loc[~non_fin, "debt_equity_pct"])
        + 0.10 * (1 - df.loc[~non_fin, "pe_pct"])
    )

    # Buffett-like durability score
    df["buffett_quality_score_raw"] = (
        0.30 * df["balance_sheet_score"]
        + 0.25 * df["cashflow_quality_score"]
        + 0.20 * df["earnings_stability_raw_pct"]
        + 0.15 * df["owner_earnings_yield_pct"]
        + 0.10 * (1 - df["accrual_ratio_pct"])
    )

    # Conservative intrinsic anchor from owner earnings
    growth = df["revenue_growth"].clip(lower=-0.05, upper=0.15).fillna(0.02)
    multiple = 10.0 + (growth * 30.0)  # 8.5x..14.5x around typical range
    df["intrinsic_value_estimate"] = pd.to_numeric(df["owner_earnings_ttm"], errors="coerce") * multiple
    df["margin_of_safety"] = safe_div(
        df["intrinsic_value_estimate"] - df["market_cap"],
        df["intrinsic_value_estimate"].abs(),
    ).clip(lower=-2, upper=2)
    df["margin_of_safety_pct"] = pct_rank_by_industry(df, "margin_of_safety")

    # Base scores
    df["institutional_value_score"] = (df["institutional_value_score_raw"] * 100).clip(lower=0, upper=100)
    df["buffett_quality_score"] = (df["buffett_quality_score_raw"] * 100).clip(lower=0, upper=100)

    # Integrate valuation-v2 modules (forensic + Buffett + DCF).
    df = _apply_v2_modules(df, history_by_ticker)

    # Blend base and module overlays while preserving compatibility.
    df["sector_adjusted_valuation_score"] = (
        0.80 * df["institutional_value_score"].fillna(50.0)
        + 0.20 * df["institutional_sector_overlay"].fillna(df["institutional_value_score"].fillna(50.0))
    ).clip(lower=0, upper=100)
    df["buffett_quality_score"] = (
        0.70 * df["buffett_quality_score"].fillna(50.0)
        + 0.30 * df["buffett_overlay_score_v2"].fillna(df["buffett_quality_score"].fillna(50.0))
    ).clip(lower=0, upper=100)

    intrinsic_component = df["dcf_margin_of_safety_v2_pct"].fillna(df["margin_of_safety_pct"]).clip(lower=0, upper=1)
    forensic_penalty_norm = (df["forensic_penalty"].fillna(50.0) / 100.0).clip(lower=0, upper=1)
    df["final_value_index"] = (
        (
            0.40 * (df["sector_adjusted_valuation_score"] / 100.0)
            + 0.30 * (df["buffett_quality_score"] / 100.0)
            + 0.20 * intrinsic_component
            - 0.10 * forensic_penalty_norm
        )
        .clip(lower=0, upper=1)
        * 100.0
    )
    df["true_undervaluation"] = df["final_value_index"]

    # Backward compatibility outputs
    df["asset_value"] = 1 - df["pb_pct"]
    df["earnings_value"] = 1 - df["pe_pct"]
    df["cash_value"] = (df["fcf_yield_pct"] + df["cfo_yield_pct"]) / 2.0
    df["enterprise_value_score"] = (1 - df["ev_ebitda_pct"] + 1 - df["ev_sales_pct"]) / 2.0
    df["growth_value"] = 1 - df["peg_pct"]
    df["balance_sheet"] = df["balance_sheet_score"]

    # Preserve core score before posterior blend.
    df["final_value_index_core"] = df["final_value_index"]

    families_df, posterior_df, state_df = _build_family_outputs(df, history_by_ticker)

    if not posterior_df.empty:
        posterior_cols = [
            "ticker",
            "posterior_gap",
            "posterior_value",
            "posterior_variance",
            "agreement_score",
            "posterior_confidence",
            "regime_modifier",
            "macro_compression",
            "regime_low_vol_prob",
            "regime_normal_prob",
            "regime_crisis_prob",
        ]
        posterior_cols = [c for c in posterior_cols if c in posterior_df.columns]
        df = df.merge(posterior_df[posterior_cols], on="ticker", how="left")
    else:
        df["posterior_gap"] = np.nan
        df["posterior_value"] = np.nan
        df["posterior_variance"] = np.nan
        df["agreement_score"] = np.nan
        df["posterior_confidence"] = np.nan
        df["regime_modifier"] = np.nan
        df["macro_compression"] = np.nan

    if not families_df.empty:
        family_cols = [
            "ticker",
            "core_value",
            "core_gap",
            "core_variance",
            "core_confidence",
            "fcff_value",
            "fcff_gap",
            "fcff_variance",
            "fcff_confidence",
            "fcff_uncertainty_band",
            "fcfe_value",
            "fcfe_gap",
            "fcfe_variance",
            "fcfe_confidence",
            "ddm_value",
            "ddm_gap",
            "ddm_variance",
            "ddm_confidence",
            "apv_value",
            "apv_gap",
            "adv_gap",
            "apv_variance",
            "apv_confidence",
            "residual_value",
            "residual_gap",
            "residual_variance",
            "residual_confidence",
            "transaction_value",
            "transaction_gap",
            "transaction_variance",
            "transaction_confidence",
            "lbo_value",
            "lbo_gap",
            "ibo_gap",
            "lbo_variance",
            "lbo_confidence",
            "credit_value",
            "credit_gap",
            "credit_variance",
            "credit_confidence",
            "default_probability",
            "credit_stress_score",
            "real_option_value",
            "real_option_gap",
            "real_option_variance",
            "real_option_confidence",
            "real_option_premium",
            "macro_percentile",
            "macro_adjustment_factor",
            "macro_valuation_state",
            "family_status",
        ]
        family_cols = [c for c in family_cols if c in families_df.columns]
        df = df.merge(families_df[family_cols], on="ticker", how="left")

    # Final blended index (backward compatible field names retained).
    posterior_component = ((pd.to_numeric(df.get("posterior_gap"), errors="coerce").clip(-1, 1).fillna(0.0) + 1.0) / 2.0) * 100.0
    intrinsic_anchor_component = intrinsic_component * 100.0
    df["final_value_index"] = (
        0.30 * pd.to_numeric(df["final_value_index_core"], errors="coerce").fillna(50.0)
        + 0.50 * posterior_component
        + 0.20 * intrinsic_anchor_component
    ).clip(lower=0, upper=100)
    df["true_undervaluation"] = df["final_value_index"]

    valuation_df = df.sort_values("true_undervaluation", ascending=False).reset_index(drop=True)
    families_df = families_df.sort_values("ticker").reset_index(drop=True) if not families_df.empty else families_df
    posterior_df = posterior_df.sort_values("ticker").reset_index(drop=True) if not posterior_df.empty else posterior_df
    state_df = state_df.reset_index(drop=True) if not state_df.empty else state_df
    return valuation_df, families_df, posterior_df, state_df


def build_valuation(fund_path: Path, price_path: Path, universe_path: Path) -> pd.DataFrame:
    valuation_df, _, _, _ = build_valuation_bundle(
        fund_path=fund_path,
        price_path=price_path,
        universe_path=universe_path,
    )
    return valuation_df


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build robust valuation parquet")
    p.add_argument("--fundamentals", type=str, default=str(FUND_FILE))
    p.add_argument("--prices", type=str, default=str(PRICE_FILE))
    p.add_argument("--universe", type=str, default=str(UNIVERSE_FILE))
    p.add_argument("--output", type=str, default=str(OUTPUT_FILE))
    p.add_argument("--families-output", type=str, default=str(FAMILIES_OUTPUT_FILE))
    p.add_argument("--posterior-output", type=str, default=str(POSTERIOR_OUTPUT_FILE))
    p.add_argument("--state-output", type=str, default=str(STATE_OUTPUT_FILE))
    p.add_argument(
        "--disable-v2-modules",
        action="store_true",
        help="Disable src.valuation v2 forensic/Buffett integration and run base valuation only",
    )
    p.add_argument(
        "--disable-family-modules",
        action="store_true",
        help="Disable valuation family engines and posterior/state outputs",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    global VALUATION_V2_AVAILABLE, VALUATION_FAMILY_AVAILABLE
    if args.disable_v2_modules:
        VALUATION_V2_AVAILABLE = False
    if args.disable_family_modules:
        VALUATION_FAMILY_AVAILABLE = False

    out, families_df, posterior_df, state_df = build_valuation_bundle(
        fund_path=Path(args.fundamentals),
        price_path=Path(args.prices),
        universe_path=Path(args.universe),
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(output, index=False)
    fam_output = Path(args.families_output)
    fam_output.parent.mkdir(parents=True, exist_ok=True)
    families_df.to_parquet(fam_output, index=False)

    posterior_output = Path(args.posterior_output)
    posterior_output.parent.mkdir(parents=True, exist_ok=True)
    posterior_df.to_parquet(posterior_output, index=False)

    state_output = Path(args.state_output)
    state_output.parent.mkdir(parents=True, exist_ok=True)
    state_df.to_parquet(state_output, index=False)

    print(
        "✅ Robust valuation model built: "
        f"{len(out)} rows -> {output}; "
        f"families={len(families_df)} -> {fam_output}; "
        f"posterior={len(posterior_df)} -> {posterior_output}; "
        f"state={len(state_df)} -> {state_output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
