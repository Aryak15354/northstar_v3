import pandas as pd
import yfinance as yf
import os
from datetime import datetime, timedelta

UNIVERSE_FILE = "universe/nifty500.csv"
RAW_PRICE_DIR = "data/raw/prices_daily"

os.makedirs(RAW_PRICE_DIR, exist_ok=True)


def normalize_ticker(t):
    t = str(t).strip().upper()
    if not t.endswith(".NS"):
        t = t + ".NS"
    return t


def get_last_date(filepath):
    if not os.path.exists(filepath):
        return None
    df = pd.read_csv(filepath)
    if df.empty:
        return None
    return pd.to_datetime(df["Date"]).max()


def fetch_and_update(symbol):
    ticker = normalize_ticker(symbol)
    filepath = f"{RAW_PRICE_DIR}/{ticker}.csv"

    last_date = get_last_date(filepath)

    if last_date is None:
        start = datetime.today() - timedelta(days=365 * 5)
        print(f"⬇ Downloading 5y history for {ticker}")
    else:
        start = last_date + timedelta(days=1)
        if start >= datetime.today():
            print(f"✅ {ticker}: Already up to date")
            return
        print(f"🔄 Updating {ticker} from {start.date()}")

    end = datetime.today() + timedelta(days=1)

    start_str = start.strftime('%Y-%m-%d')
    end_str = end.strftime('%Y-%m-%d')

    data = yf.download(ticker, start=start_str, end=end_str, progress=False)

    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.droplevel(1)

    if data.empty:
        print(f"⚠ No data for {ticker}")
        return

    data.reset_index(inplace=True)
    data["Date"] = data["Date"].dt.strftime('%Y-%m-%d')
    data = data[["Date", "Open", "High", "Low", "Close", "Volume"]]

    if os.path.exists(filepath):
        old = pd.read_csv(filepath)
        combined = pd.concat([old, data])
        combined.drop_duplicates(subset=["Date"], inplace=True)
    else:
        combined = data

    combined.sort_values("Date", inplace=True)
    combined.to_csv(filepath, index=False)
    print(f"✅ {ticker}: {len(combined)} rows")


def main():
    df = pd.read_csv(UNIVERSE_FILE)
    symbols = df["Symbol"]

    print(f"🚀 Downloading prices for {len(symbols)} Nifty stocks")

    for sym in symbols:
        try:
            fetch_and_update(sym)
        except Exception as e:
            print(f"❌ {sym}: {e}")


if __name__ == "__main__":
    main()
