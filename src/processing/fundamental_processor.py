#!/usr/bin/env python3
"""
Quarterly fundamentals processor.

Converts raw yfinance statement CSVs into a unified panel:
data/processed/fundamentals.parquet
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import pandas as pd


RAW_FIN_DIR = Path("data/raw/financials_quarterly")
OUTPUT_FILE = Path("data/processed/fundamentals.parquet")


ALIASES: Dict[str, List[str]] = {
    "revenue": ["Total Revenue", "Revenue"],
    "gross_profit": ["Gross Profit"],
    "cost_of_revenue": ["Cost Of Revenue", "Cost of Revenue"],
    "ebitda": ["EBITDA", "Ebitda"],
    "operating_income": ["Operating Income", "OperatingIncome", "EBIT"],
    "net_income": ["Net Income", "Net income"],
    "tax_provision": ["Tax Provision", "Tax Expense"],
    "other_income": [
        "Other Non Operating Income Expenses",
        "Other Income Expense",
        "Other Income",
    ],
    "restructuring_charges": ["Restructuring Charges", "Other Special Charges"],
    "impairment_charges": ["Asset Impairment Charge", "Write Off"],
    "bad_debt_expense": ["Provision For Doubtful Accounts", "Bad Debt Expense"],
    "total_assets": ["Total Assets", "Total assets"],
    "equity": ["Stockholders Equity", "Total Equity", "Shareholders Equity"],
    "total_debt": ["Total Debt", "Total debt", "Total Liabilities Net Minority Interest"],
    "minority_interest": ["Minority Interest", "Non Controlling Interests"],
    "cash_and_equivalents": [
        "Cash and cash equivalents",
        "Cash And Cash Equivalents",
        "Cash",
        "Cash & Equivalents",
    ],
    "receivables": [
        "Accounts Receivable",
        "Gross Accounts Receivable",
        "Receivables",
    ],
    "inventory": ["Inventory", "Inventories"],
    "payables": ["Payables", "Accounts Payable", "Total Payables"],
    "working_capital": ["Working Capital"],
    "deferred_revenue": [
        "Deferred Revenue",
        "Current Deferred Revenue",
        "Non Current Deferred Revenue",
    ],
    "lease_liabilities": [
        "Capital Lease Obligations",
        "Long Term Capital Lease Obligation",
        "Current Capital Lease Obligation",
    ],
    "gross_ppe": ["Gross PPE", "Gross PP&E"],
    "operating_cash_flow": [
        "Operating Cash Flow",
        "Net Cash Provided by Operating Activities",
        "Net cash provided by operating activities",
    ],
    "capex": [
        "Capital Expenditure",
        "Capital Expenditures",
        "Purchase of Property, Plant and Equipment",
        "Investments in property, plant, and equipment",
        "Purchases of property and equipment",
    ],
    "free_cash_flow": ["Free Cash Flow", "Free cash flow"],
    "shares_outstanding": ["Ordinary Shares Number", "Common Shares Outstanding"],
    "depreciation_amortization": [
        "Depreciation And Amortization",
        "Depreciation and amortization",
        "Depreciation",
    ],
    "depreciation": ["Depreciation", "Depreciation Income Statement"],
    "amortization": ["Amortization", "Amortization Cash Flow"],
    "interest_expense": ["Interest Expense", "Net Interest Expense"],
    "change_in_working_capital": ["Change In Working Capital"],
    "interest_paid_cfo": ["Interest Paid Cfo", "Interest Paid CFO"],
    "interest_received_cfo": ["Interest Received Cfo", "Interest Received CFO"],
    "cash_dividends_paid": ["Cash Dividends Paid", "Common Stock Dividend Paid"],
}

INCOME_FEATURES = {
    "revenue",
    "gross_profit",
    "cost_of_revenue",
    "ebitda",
    "operating_income",
    "net_income",
    "tax_provision",
    "other_income",
    "restructuring_charges",
    "impairment_charges",
    "bad_debt_expense",
    "depreciation_amortization",
    "depreciation",
    "amortization",
    "interest_expense",
}

BALANCE_FEATURES = {
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
    "shares_outstanding",
}

CASHFLOW_FEATURES = {
    "operating_cash_flow",
    "capex",
    "free_cash_flow",
    "change_in_working_capital",
    "interest_paid_cfo",
    "interest_received_cfo",
    "cash_dividends_paid",
}


def _load_statement(path: Path) -> Optional[pd.DataFrame]:
    if not path.exists():
        return None
    df = pd.read_csv(path)
    if df.empty or "Date" not in df.columns:
        return None
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"]).sort_values("Date")
    return df


def _resolve_value(df: Optional[pd.DataFrame], date: pd.Timestamp, keys: Iterable[str]) -> Optional[float]:
    if df is None:
        return None
    row = df[df["Date"] == date]
    if row.empty:
        return None
    # Exact match first.
    for key in keys:
        if key in df.columns:
            val = row.iloc[0][key]
            if pd.notna(val):
                return val
    # Case-insensitive fallback.
    cols_lower = {str(c).strip().lower(): c for c in df.columns}
    for key in keys:
        col = cols_lower.get(str(key).strip().lower())
        if col:
            val = row.iloc[0][col]
            if pd.notna(val):
                return val
    return None


def _ticker_from_filename(name: str) -> str:
    return name.split("_")[0]


def _iter_tickers(raw_dir: Path) -> List[str]:
    files = list(raw_dir.glob("*.csv"))
    tickers = {_ticker_from_filename(f.name) for f in files}
    return sorted(tickers)


def _safe_float(v):
    try:
        return float(v)
    except Exception:
        return None


def process_ticker(ticker: str, raw_dir: Path) -> List[dict]:
    income = _load_statement(raw_dir / f"{ticker}_income.csv")
    balance = _load_statement(raw_dir / f"{ticker}_balance.csv")
    cashflow = _load_statement(raw_dir / f"{ticker}_cashflow.csv")

    dates = set()
    for df in (income, balance, cashflow):
        if df is not None:
            dates.update(df["Date"].tolist())
    if not dates:
        return []

    records: List[dict] = []
    for dt in sorted(dates):
        row = {"ticker": ticker, "date": pd.Timestamp(dt)}
        for feature, keys in ALIASES.items():
            source_df = (
                income if feature in INCOME_FEATURES else
                balance if feature in BALANCE_FEATURES else
                cashflow if feature in CASHFLOW_FEATURES else
                cashflow
            )
            row[feature] = _resolve_value(
                source_df,
                pd.Timestamp(dt),
                keys,
            )

        if row["free_cash_flow"] is None:
            ocf = _safe_float(row["operating_cash_flow"])
            capex = _safe_float(row["capex"])
            if ocf is not None and capex is not None:
                row["free_cash_flow"] = ocf - capex

        if row["depreciation_amortization"] is None:
            dep = _safe_float(row.get("depreciation"))
            amo = _safe_float(row.get("amortization"))
            if dep is not None or amo is not None:
                row["depreciation_amortization"] = (dep or 0.0) + (amo or 0.0)

        records.append(row)
    return records


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Process quarterly financial statements into fundamentals parquet")
    p.add_argument("--raw-dir", type=str, default=str(RAW_FIN_DIR))
    p.add_argument("--output-file", type=str, default=str(OUTPUT_FILE))
    return p.parse_args()


def main() -> int:
    args = parse_args()
    raw_dir = Path(args.raw_dir)
    out_file = Path(args.output_file)

    if not raw_dir.exists():
        raise FileNotFoundError(f"Raw financials directory missing: {raw_dir}")

    records: List[dict] = []
    for ticker in _iter_tickers(raw_dir):
        try:
            records.extend(process_ticker(ticker, raw_dir))
        except Exception as e:
            print(f"❌ {ticker}: {e}")

    if not records:
        raise RuntimeError(f"No fundamentals records built from {raw_dir}")

    df = pd.DataFrame(records)
    df = df.sort_values(["ticker", "date"]).drop_duplicates(subset=["ticker", "date"], keep="last")

    num_cols = [c for c in df.columns if c not in {"ticker", "date"}]
    for c in num_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    out_file.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_file, index=False)
    print(f"✅ Fundamentals saved: {len(df)} rows, {df['ticker'].nunique()} tickers -> {out_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
