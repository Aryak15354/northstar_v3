"""Canonical feature → point-in-time availability-lag ruleset.

Every research feature must declare when it becomes knowable (price close vs
T+60 fundamentals vs T+1 announcements…), or the DatasetManager's strict PIT
guard refuses to build the panel. This ruleset was proven in the weekly Kaggle
export (scripts/kaggle/week_2026_03_29/build_weekly_feature_export.py); it is
shared here so every trainer applies the SAME temporal discipline instead of
each runner inventing (or forgetting) its own — the regime-model retrain was
failing with 216 unregistered features because it passed no rules at all.
"""

from __future__ import annotations


def default_feature_pit_lags() -> list[dict[str, object]]:
    return [
        {"pattern": "sector_dummy", "lag": "price"},
        {"pattern": "re:^(open|high|low|close|adj_close|volume|turnover|vwap|ret_.*|mom_.*|res_mom.*|vol_.*|beta.*|bab.*|amihud.*|max_ret_.*|drawdown.*|price_.*|nifty_.*|india_vix.*|size_x_amihud|mom[0-9]+_x_.*)$", "lag": "price"},
        {"pattern": "re:^(days_since_earnings|days_since_earnings_available|earnings_.*|eps_.*|rev_.*|combined_sue.*)$", "lag": "earnings"},
        {"pattern": "re:^(revenue|sales|gross_profit|operating_cash_flow|free_cash_flow|net_income|equity|total_assets|total_debt|working_capital|shares_outstanding|gross_margin.*|operating_margin.*|ebitda_margin.*|interest_coverage.*|asset_turnover.*|cash_conversion.*|accruals_ratio.*|debt_to_equity.*|roe.*|roa.*|piotroski.*|earnings_quality.*|sector_quality_composite.*)$", "lag": "fundamental"},
        # balance-sheet / income-statement items not covered above
        {"pattern": "re:^(cash_and_equivalents|cost_of_revenue|deferred_revenue|ebitda|ebit|inventory|receivables|payables|capex|book_value.*|fcf_to_ocf.*|ocf_.*|interest_expense|depreciation.*|amortization.*|minority_interest|lease_liabilities|gross_ppe|tax_provision|ni_margin.*|operating_income.*)(_sector_z)?$", "lag": "fundamental"},
        # recent_(up|down)grade_flag / watch_negative_flag / investment_grade_flag are
        # the ratings family (src/signals/feature_builder.py "ratings") but do not start
        # with "rating_", so they fell through every pattern and tripped
        # feature_pit_lag_missing once feature_pit_enforce went True (2026-07-17).
        # Same source + availability as rating_.* -> same "bulk" (T+1) lag.
        {"pattern": "re:^(bulk_.*|order_.*|rating_.*|recent_upgrade_flag|recent_downgrade_flag|watch_negative_flag|investment_grade_flag|announcement_.*|announcements_.*|insider_.*)$", "lag": "bulk"},
        {"pattern": "re:^(screener_.*(promoter|fii|dii|public|govt|institutional|free_float|ownership).*)$", "lag": "shareholding"},
        {"pattern": "re:^(pledge_.*|promoter_.*|fii_.*|dii_.*|public_.*|institutional_.*|free_float.*|ownership.*)$", "lag": "shareholding"},
        {"pattern": "re:^(screener_.*)$", "lag": "fundamental"},
        {"pattern": "re:^(mkt_sent_.*|macro_sent_.*|sent_.*|event_.*|narrative_.*|topic_.*)$", "lag": "sentiment"},
        {"pattern": "re:^(cpi_.*|wpi_.*|iip_.*|pmi_.*|repo_.*|macro_.*|fx_.*|rate_.*|policy_.*|credit_.*|oil_.*|gold_.*|copper_.*|steel_.*|coal_.*|crude_.*|inr_.*|inrusd_.*|dxy_.*|vix_.*|rbi_.*|gst_.*|power_.*|us_10y_.*|yield_curve_.*|commodity_basket|fii_proxy|stock_x_.*|political_.*|india_domestic_.*|gold_consumption_drag.*|oil_sector_impact.*|copper_activity_signal.*|dxy_fii_proxy.*|macro_linkage_score.*|regime_.*|.*_x_regime_modifier)$", "lag": "macro"},
        {"pattern": "re:^(international_revenue_proxy|.*_sensitivity_score|business_cycle_bucket)$", "lag": "market"},
        {"pattern": "re:^(posterior_.*|agreement_score.*|val_.*)$", "lag": "market"},
        # generic sector-z transforms inherit the fundamental lag (conservative)
        {"pattern": "re:^.*_sector_z$", "lag": "fundamental"},
    ]


def default_pit_day_config() -> dict[str, object]:
    return {
        "pit_announcement_plus_days": 1,
        "pit_earnings_announcement_plus_days": 1,
        "pit_financials_plus_days": 1,
        "pit_fundamental_lag_days": 60,
        "pit_shareholding_lag_days": 2,
        "pit_bulk_deal_lag_days": 1,
        "pit_macro_lag_days": 1,
        "pit_sentiment_lag_days": 1,
    }
