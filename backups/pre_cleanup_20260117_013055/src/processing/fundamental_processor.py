import pandas as pd
import os

RAW_FIN_DIR = "data/raw/financials_quarterly"
OUTPUT_FILE = "data/processed/fundamentals.parquet"


def load_statement(path):
    if not os.path.exists(path):
        return None
    df = pd.read_csv(path)
    if df.empty:
        return None
    df["Date"] = pd.to_datetime(df["Date"])
    return df


def get_value(df, date, column):
    if df is None or column not in df.columns:
        return None
    row = df[df["Date"] == date]
    if row.empty:
        return None
    return row.iloc[0][column]

def get_value_any(df, date, columns):
    if df is None:
        return None
    for col in columns:
        if col in df.columns:
            val = get_value(df, date, col)
            if val is not None:
                return val
    return None


def main():
    records = []

    files = os.listdir(RAW_FIN_DIR)
    tickers = set([f.split("_")[0] for f in files])

    for ticker in tickers:
        try:
            income = load_statement(f"{RAW_FIN_DIR}/{ticker}_income.csv")
            balance = load_statement(f"{RAW_FIN_DIR}/{ticker}_balance.csv")
            cashflow = load_statement(f"{RAW_FIN_DIR}/{ticker}_cashflow.csv")

            if income is None:
                continue

            for date in income["Date"]:
                ocf = get_value_any(cashflow, date, [
                    "Operating Cash Flow",
                    "Net Cash Provided by Operating Activities",
                    "Net cash provided by operating activities"
                ])
                capex = get_value_any(cashflow, date, [
                    "Capital Expenditure",
                    "Capital Expenditures",
                    "Purchase of Property, Plant and Equipment",
                    "Investments in property, plant, and equipment",
                    "Purchases of property and equipment"
                ])
                fcf = get_value_any(cashflow, date, [
                    "Free Cash Flow",
                    "Free cash flow"
                ])
                if fcf is None and ocf is not None and capex is not None:
                    try:
                        fcf = float(ocf) - float(capex)
                    except Exception:
                        fcf = None

                cash = get_value_any(balance, date, [
                    "Cash and cash equivalents",
                    "Cash And Cash Equivalents",
                    "Cash",
                    "Cash & Equivalents"
                ])

                rec = {
                    "ticker": ticker,
                    "date": date,
                    "revenue": get_value_any(income, date, ["Total Revenue", "Revenue"]),
                    "ebitda": get_value_any(income, date, ["EBITDA", "Ebitda"]),
                    "net_income": get_value_any(income, date, ["Net Income", "Net income"]),
                    "total_assets": get_value_any(balance, date, ["Total Assets", "Total assets"]),
                    "equity": get_value_any(balance, date, ["Stockholders Equity", "Total Equity", "Shareholders Equity"]),
                    "total_debt": get_value_any(balance, date, ["Total Debt", "Total debt", "Total Liabilities Net Minority Interest"]),
                    "cash_and_equivalents": cash,
                    "operating_cash_flow": ocf,
                    "capex": capex,
                    "free_cash_flow": fcf,
                    "shares_outstanding": get_value_any(balance, date, ["Ordinary Shares Number", "Common Shares Outstanding"])
                }
                records.append(rec)

        except Exception as e:
            print(f"❌ {ticker}: {e}")

    df = pd.DataFrame(records)
    df = df.sort_values(["ticker", "date"])
    num_cols = [
        "revenue","ebitda","net_income","total_assets","equity","total_debt",
        "cash_and_equivalents","operating_cash_flow","capex","free_cash_flow","shares_outstanding"
    ]
    for c in num_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df.to_parquet(OUTPUT_FILE, index=False)

    print(f"✅ Fundamentals saved: {len(df)} rows")


if __name__ == "__main__":
    main()
