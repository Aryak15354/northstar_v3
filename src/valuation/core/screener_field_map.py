"""Canonical Screener-to-internal financial field mappings."""

from __future__ import annotations

SCREENER_TO_INTERNAL = {
    # Income statement
    "Sales": "revenue",
    "Net Profit": "net_profit",
    "Operating Profit": "operating_profit",
    "Other Income": "other_income",
    "Interest": "interest_expense",
    "Depreciation": "depreciation",
    "EPS in Rs": "eps",
    "Tax %": "tax_rate_pct",
    "Profit before tax": "profit_before_tax",
    "Expenses": "total_expenses",
    "OPM %": "opm_pct",
    "NPM %": "npm_pct",
    "ROE %": "roe_pct",
    "ROCE %": "roce_pct",
    "Asset Turnover": "asset_turnover",
    "Debt to equity": "debt_to_equity",
    "Current ratio": "current_ratio",
    "Dividend Payout %": "dividend_payout_pct",
    # Balance sheet
    "Equity Capital": "equity_capital",
    "Reserves": "reserves",
    "Borrowings": "total_borrowings",
    "Other Liabilities": "other_liabilities",
    "Fixed Assets": "fixed_assets",
    "CWIP": "cwip",
    "Investments": "investments",
    "Other Assets": "other_assets",
    "Total Assets": "total_assets",
    "Total Liabilities": "total_liabilities",
    "Deposits": "deposits",
    # Cashflow statement
    "Cash from Operating Activity": "cash_from_operations",
    "Cash from Investing Activity": "cash_from_investing",
    "Cash from Financing Activity": "cash_from_financing",
    "Net Cash Flow": "net_cash_flow",
    # Working-capital / efficiency
    "Debtor Days": "debtor_days",
    "Inventory Days": "inventory_days",
    "Days Payable": "days_payable",
    "Cash Conversion Cycle": "cash_conversion_cycle",
    "Working Capital Days": "working_capital_days",
    # Financial / sector-specific extras
    "Financing Profit": "financing_profit",
    "Financing Margin %": "financing_margin_pct",
}

SCREENER_ALIASES_TO_INTERNAL = {
    "Revenue": "revenue",
    "Borrowing": "total_borrowings",
    "Cash from Operations": "cash_from_operations",
    "Cash from Operating Activities": "cash_from_operations",
    "Cash from Investing": "cash_from_investing",
    "Cash from Investing Activities": "cash_from_investing",
    "Cash from Financing": "cash_from_financing",
    "Cash from Financing Activities": "cash_from_financing",
    "NPM %": "npm_pct",
}

# Keep the invertible canonical map separate from aliases/variants above.
INTERNAL_TO_SCREENER = {}
for screener_name, internal_name in SCREENER_TO_INTERNAL.items():
    INTERNAL_TO_SCREENER.setdefault(internal_name, screener_name)

REQUIRED_FOR_DCF = [
    "revenue",
    "net_profit",
    "cash_from_operations",
    "depreciation",
    "total_assets",
    "equity_capital",
    "total_borrowings",
    "interest_expense",
    "tax_rate_pct",
]

REQUIRED_FOR_MOAT = [
    "revenue",
    "operating_profit",
    "net_profit",
    "total_assets",
    "equity_capital",
    "reserves",
    "roce_pct",
    "roe_pct",
]

REQUIRED_FOR_ACCRUALS = [
    "net_profit",
    "cash_from_operations",
    "total_assets",
]

REQUIRED_FOR_RESIDUAL_INCOME = [
    "net_profit",
    "equity_capital",
    "reserves",
    "roe_pct",
    "total_assets",
]

REQUIRED_FOR_MULTIPLES = [
    "eps",
    "net_profit",
    "revenue",
    "operating_profit",
    "total_assets",
    "equity_capital",
    "total_borrowings",
]
