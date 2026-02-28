#!/usr/bin/env python3
"""
Valuation Engine v2 - Comprehensive Demo
Demonstrates the complete valuation workflow
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pandas as pd
import numpy as np
from src.valuation.core.normalized_financials import FinancialNormalizer
from src.valuation.core.adjusted_metrics import AdjustedMetricsCalculator
from src.valuation.core.sector_mapper import SectorMapper, SectorCategory
from src.valuation.forensic.earnings_quality import EarningsQualityAnalyzer
from src.valuation.forensic.accounting_distortions import AccountingDistortionDetector
from src.valuation.intrinsic_value.owner_earnings import OwnerEarningsCalculator
from src.valuation.intrinsic_value.dcf_engine import DCFEngine
from src.valuation.buffett_module.moat_score import MoatScorer


def demo_tech_company():
    """
    Demo: Technology company valuation
    Example: High-growth SaaS company
    """
    print("\n" + "="*80)
    print("DEMO 1: Technology Company (SaaS)")
    print("="*80)
    
    # Company data
    ticker = "TECH.NS"
    sector = "Technology"
    
    # Financials (in millions)
    revenue = 10000
    ebit = 2000
    ebitda = 2500
    net_income = 1500
    depreciation = 300
    amortization = 200
    
    # Balance sheet
    equity = 8000
    debt = 2000
    cash = 3000
    receivables = 2000
    total_assets = 15000
    
    # Cash flow
    operating_cash_flow = 1800
    capex = 500
    
    # Market data
    market_cap = 50000
    shares_outstanding = 1000
    current_price = 50
    
    # Historical data
    roic_history = pd.Series([0.22, 0.23, 0.21, 0.24, 0.23, 0.25, 0.24, 0.26, 0.25, 0.27])
    gross_margin_history = pd.Series([0.75, 0.76, 0.77, 0.76, 0.78, 0.79, 0.78, 0.80, 0.79, 0.81])
    revenue_growth_history = pd.Series([0.25, 0.28, 0.22, 0.30, 0.27, 0.25, 0.28, 0.26, 0.29, 0.27])
    
    print(f"\nCompany: {ticker}")
    print(f"Sector: {sector}")
    print(f"Revenue: ${revenue}M")
    print(f"Market Cap: ${market_cap}M")
    print(f"Current Price: ${current_price}")
    
    # Step 1: Normalize financials
    print("\n" + "-"*80)
    print("STEP 1: Financial Normalization")
    print("-"*80)
    
    normalizer = FinancialNormalizer()
    adjusted = normalizer.normalize_financials(
        ticker=ticker,
        sector=sector,
        revenue=revenue,
        ebit=ebit,
        ebitda=ebitda,
        capex=capex,
        depreciation=depreciation,
        amortization=amortization,
        rd_expense=500,
        capitalized_rd=0,
        rd_amortization=0,
        receivables=receivables,
        inventory=0,
        payables=500,
        deferred_revenue=1000,
        lease_liabilities=0,
        gross_ppe=2000
    )
    
    print(f"Adjusted Revenue: ${adjusted.adjusted_revenue:.0f}M")
    print(f"Adjusted EBIT: ${adjusted.adjusted_ebit:.0f}M")
    print(f"Maintenance Capex: ${adjusted.maintenance_capex:.0f}M")
    print(f"Growth Capex: ${adjusted.growth_capex:.0f}M")
    print(f"Adjustments made: {len(adjusted.adjustments_made)}")
    for key, value in adjusted.adjustments_made.items():
        print(f"  - {key}: {value}")
    
    # Step 2: Calculate adjusted metrics
    print("\n" + "-"*80)
    print("STEP 2: Adjusted Metrics")
    print("-"*80)
    
    metrics_calc = AdjustedMetricsCalculator()
    metrics = metrics_calc.calculate_all_metrics(
        revenue=adjusted.adjusted_revenue,
        adjusted_ebit=adjusted.adjusted_ebit,
        net_income=net_income,
        depreciation=depreciation,
        amortization=amortization,
        equity=equity,
        debt=debt,
        cash=cash,
        excess_cash=cash * 0.5,
        lease_liabilities=0,
        capitalized_rd=0,
        operating_cash_flow=operating_cash_flow,
        capex=capex,
        maintenance_capex=adjusted.maintenance_capex,
        working_capital_increase=100,
        market_cap=market_cap
    )
    
    print(f"Adjusted ROIC: {metrics.adjusted_roic:.1%}")
    print(f"Adjusted ROE: {metrics.adjusted_roe:.1%}")
    print(f"FCF: ${metrics.adjusted_fcf:.0f}M")
    print(f"FCF Conversion: {metrics.fcf_conversion:.2f}")
    print(f"Owner Earnings: ${metrics.owner_earnings:.0f}M")
    print(f"Owner Earnings Yield: {metrics.metrics['owner_earnings_yield']:.1%}")
    
    # Step 3: Forensic analysis
    print("\n" + "-"*80)
    print("STEP 3: Forensic Accounting Analysis")
    print("-"*80)
    
    forensic = EarningsQualityAnalyzer()
    quality = forensic.analyze_earnings_quality(
        net_income=net_income,
        operating_cash_flow=operating_cash_flow,
        total_assets=total_assets,
        receivables=receivables,
        revenue=revenue,
        gross_profit=revenue * 0.78,
        ppe=2000,
        depreciation=depreciation,
        sga=3000,
        receivables_prior=1800,
        revenue_prior=8000,
        gross_profit_prior=6200,
        total_assets_prior=14000,
        ppe_prior=1900,
        depreciation_prior=280,
        sga_prior=2800
    )
    
    print(f"Earnings Quality Score: {quality.overall_score:.1f}/100")
    print(f"Quality Grade: {quality.quality_grade}")
    print(f"Accrual Quality: {quality.accrual_quality:.1f}")
    print(f"Cash Conversion: {quality.cash_conversion:.1f}")
    print(f"Earnings Stability: {quality.earnings_stability:.1f}")
    print(f"Red Flags: {len(quality.red_flags)}")
    for flag in quality.red_flags:
        print(f"  ⚠️  {flag}")
    
    # Step 4: Moat assessment
    print("\n" + "-"*80)
    print("STEP 4: Economic Moat Assessment (Buffett Module)")
    print("-"*80)
    
    moat_scorer = MoatScorer()
    moat = moat_scorer.assess_moat(
        roic_history=roic_history,
        gross_margin_history=gross_margin_history,
        revenue_growth_history=revenue_growth_history,
        recurring_revenue_pct=0.85,
        customer_retention_rate=0.95,
        market_share=0.15,
        market_share_trend=0.02,
        platform_indicator=True
    )
    
    print(f"Moat Width: {moat.moat_width}")
    print(f"Overall Moat Score: {moat.overall_score:.1f}/100")
    print(f"ROIC Consistency: {moat.roic_consistency:.1f}")
    print(f"Pricing Power: {moat.pricing_power:.1f}")
    print(f"Switching Costs: {moat.switching_costs:.1f}")
    print(f"Network Effects: {moat.network_effects:.1f}")
    print(f"Moat Sources: {', '.join(moat.moat_sources) if moat.moat_sources else 'None identified'}")
    
    # Step 5: Owner earnings
    print("\n" + "-"*80)
    print("STEP 5: Owner Earnings Calculation")
    print("-"*80)
    
    oe_calc = OwnerEarningsCalculator()
    owner_earnings_result = oe_calc.calculate_owner_earnings(
        net_income=net_income,
        depreciation=depreciation,
        amortization=amortization,
        total_capex=capex,
        maintenance_capex=adjusted.maintenance_capex,
        current_wc=2500,
        prior_wc=2400,
        revenue=revenue,
        revenue_prior=8000,
        revenue_growth=0.25,
        shares_outstanding=shares_outstanding,
        market_cap=market_cap,
        sector=sector
    )
    
    print(f"Owner Earnings: ${owner_earnings_result.owner_earnings:.0f}M")
    print(f"Owner Earnings per Share: ${owner_earnings_result.owner_earnings_per_share:.2f}")
    print(f"Owner Earnings Yield: {owner_earnings_result.owner_earnings_yield:.1%}")
    print(f"Quality Score: {owner_earnings_result.quality_score:.1f}/100")
    print("\nComponents:")
    for key, value in owner_earnings_result.components.items():
        print(f"  {key}: ${value:.0f}M")
    
    # Step 6: DCF valuation
    print("\n" + "-"*80)
    print("STEP 6: Intrinsic Value (Conservative DCF)")
    print("-"*80)
    
    dcf = DCFEngine()
    valuation = dcf.buffett_style_valuation(
        owner_earnings=owner_earnings_result.owner_earnings,
        roic_10y_avg=roic_history.mean(),
        revenue_growth_5y=revenue_growth_history.mean(),
        shares_outstanding=shares_outstanding,
        current_price=current_price,
        sector=sector,
        quality_score=quality.overall_score
    )
    
    print(f"Intrinsic Value per Share: ${valuation.intrinsic_value_per_share:.2f}")
    print(f"Current Price: ${valuation.current_price:.2f}")
    print(f"Margin of Safety: ${valuation.margin_of_safety:.2f} ({valuation.margin_of_safety_pct:.1%})")
    print(f"Upside Potential: {valuation.upside_potential:.1%}")
    print(f"Valuation Grade: {valuation.valuation_grade}")
    
    print("\nKey Assumptions:")
    for key, value in valuation.assumptions.items():
        if isinstance(value, float):
            if 'rate' in key or 'growth' in key or 'roic' in key:
                print(f"  {key}: {value:.1%}")
            else:
                print(f"  {key}: ${value:.0f}M" if value > 1000 else f"  {key}: {value:.2f}")
    
    print("\nSensitivity Analysis:")
    for key, value in valuation.sensitivity.items():
        print(f"  {key}: {value:+.1%}")
    
    # Final recommendation
    print("\n" + "="*80)
    print("FINAL ASSESSMENT")
    print("="*80)
    
    if valuation.margin_of_safety_pct >= 0.30 and quality.quality_grade in ['A', 'B'] and moat.moat_width in ['Wide', 'Narrow']:
        recommendation = "STRONG BUY"
        color = "🟢"
    elif valuation.margin_of_safety_pct >= 0.20 and quality.quality_grade in ['A', 'B', 'C']:
        recommendation = "BUY"
        color = "🟢"
    elif valuation.margin_of_safety_pct >= 0:
        recommendation = "HOLD"
        color = "🟡"
    else:
        recommendation = "SELL"
        color = "🔴"
    
    print(f"\n{color} Recommendation: {recommendation}")
    print(f"\nRationale:")
    print(f"  • Moat: {moat.moat_width} ({moat.overall_score:.0f}/100)")
    print(f"  • Quality: Grade {quality.quality_grade} ({quality.overall_score:.0f}/100)")
    print(f"  • Valuation: {valuation.margin_of_safety_pct:.0%} MOS (Grade {valuation.valuation_grade})")
    print(f"  • ROIC: {metrics.adjusted_roic:.1%} (Excellent)" if metrics.adjusted_roic > 0.20 else f"  • ROIC: {metrics.adjusted_roic:.1%}")
    print(f"  • FCF Conversion: {metrics.fcf_conversion:.2f}" + (" (Strong)" if metrics.fcf_conversion > 0.8 else ""))


def demo_financial_company():
    """
    Demo: Financial company valuation
    Example: Bank
    """
    print("\n\n" + "="*80)
    print("DEMO 2: Financial Company (Bank)")
    print("="*80)
    
    print("\nNote: Banks require different valuation framework")
    print("Primary metrics: P/B, ROE, NIM, Asset Quality")
    print("Ignore: EV/EBITDA, EV/EBIT (not applicable)")
    
    # Bank data
    ticker = "BANK.NS"
    sector = "Financials"
    
    # Key metrics
    book_value = 500
    market_cap = 1000
    net_income = 100
    equity = 500
    
    # Bank-specific
    nim = 0.035  # 3.5% Net Interest Margin
    gnpa_ratio = 0.02  # 2% Gross NPA
    loan_growth = 0.15  # 15% loan growth
    
    print(f"\nCompany: {ticker}")
    print(f"Book Value: ${book_value}M")
    print(f"Market Cap: ${market_cap}M")
    print(f"P/B Ratio: {market_cap/book_value:.2f}x")
    print(f"ROE: {net_income/equity:.1%}")
    print(f"NIM: {nim:.2%}")
    print(f"GNPA: {gnpa_ratio:.2%}")
    print(f"Loan Growth: {loan_growth:.1%}")
    
    # Fair P/B calculation
    roe = net_income / equity
    growth = 0.12  # 12% sustainable growth
    coe = 0.14  # 14% cost of equity
    
    fair_pb = (roe - growth) / (coe - growth)
    current_pb = market_cap / book_value
    
    print(f"\nFair P/B: {fair_pb:.2f}x")
    print(f"Current P/B: {current_pb:.2f}x")
    print(f"Valuation: {'Undervalued' if current_pb < fair_pb * 0.9 else 'Overvalued' if current_pb > fair_pb * 1.1 else 'Fair'}")


def main():
    """Run all demos"""
    print("\n" + "="*80)
    print("NORTHSTAR VALUATION ENGINE V2 - COMPREHENSIVE DEMO")
    print("Institutional-Grade Valuation with Forensic Accounting & Buffett Principles")
    print("="*80)
    
    # Demo 1: Tech company
    demo_tech_company()
    
    # Demo 2: Financial company
    demo_financial_company()
    
    print("\n" + "="*80)
    print("DEMO COMPLETE")
    print("="*80)
    print("\nFor more information:")
    print("  • Documentation: docs/VALUATION_ENGINE_V2_GUIDE.md")
    print("  • Rules Reference: docs/VALUATION_RULES_REFERENCE.md")
    print("  • Source Code: src/valuation/")
    print("\n")


if __name__ == "__main__":
    main()
