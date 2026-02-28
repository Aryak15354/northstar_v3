import yfinance as yf
import pandas as pd
import os

UNIVERSE_FILE = "universe/nifty500.csv"
RAW_FIN_DIR = "data/raw/financials_quarterly"

os.makedirs(RAW_FIN_DIR, exist_ok=True)


def normalize_ticker(t):
    t = str(t).strip().upper()
    if not t.endswith(".NS"):
        t = t + ".NS"
    return t


def save_statement(df, filename):
    if df is None or df.empty:
        return
    df = df.T
    df.index.name = "Date"
    df.reset_index(inplace=True)
    df["Date"] = df["Date"].dt.strftime('%Y-%m-%d')
    if os.path.exists(filename):
        old = pd.read_csv(filename)
        combined = pd.concat([old, df])
        combined.drop_duplicates(subset=["Date"], inplace=True)
    else:
        combined = df
    combined.sort_values("Date", inplace=True)
    combined.to_csv(filename, index=False)


def fetch_financials(symbol):
    ticker = normalize_ticker(symbol)
    print(f"📊 Fetching financials for {ticker}")

    stock = yf.Ticker(ticker)

    income = stock.quarterly_financials
    balance = stock.quarterly_balance_sheet
    cashflow = stock.quarterly_cashflow

    save_statement(income, f"{RAW_FIN_DIR}/{ticker}_income.csv")
    save_statement(balance, f"{RAW_FIN_DIR}/{ticker}_balance.csv")
    save_statement(cashflow, f"{RAW_FIN_DIR}/{ticker}_cashflow.csv")


def main():
    df = pd.read_csv(UNIVERSE_FILE)
    symbols = df["Symbol"]

    for sym in symbols:
        try:
            fetch_financials(sym)
        except Exception as e:
            print(f"❌ {sym}: {e}")


if __name__ == "__main__":
    main()
