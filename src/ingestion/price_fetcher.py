import argparse
import os
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf

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

def get_first_date(filepath):
    if not os.path.exists(filepath):
        return None
    df = pd.read_csv(filepath)
    if df.empty:
        return None
    return pd.to_datetime(df["Date"]).min()


def _download_slice(ticker, start_dt, end_dt):
    if start_dt >= end_dt:
        return pd.DataFrame()
    data = yf.download(
        ticker,
        start=start_dt.strftime("%Y-%m-%d"),
        end=end_dt.strftime("%Y-%m-%d"),
        progress=False,
    )
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.droplevel(1)
    if data.empty:
        return pd.DataFrame()
    data.reset_index(inplace=True)
    data["Date"] = data["Date"].dt.strftime("%Y-%m-%d")
    return data[["Date", "Open", "High", "Low", "Close", "Volume"]]


def fetch_and_update(symbol, *, start_year=None, history_years=5):
    ticker = normalize_ticker(symbol)
    filepath = f"{RAW_PRICE_DIR}/{ticker}.csv"

    start_floor = None
    if start_year is not None:
        start_floor = datetime(int(start_year), 1, 1)
    else:
        start_floor = datetime.today() - timedelta(days=365 * int(history_years))

    last_date = get_last_date(filepath)
    first_date = get_first_date(filepath)

    parts = []
    if os.path.exists(filepath):
        old = pd.read_csv(filepath)
        if not old.empty:
            parts.append(old)

    # Backfill earlier history if requested.
    if start_floor is not None and first_date is not None and first_date > start_floor:
        backfill_end = first_date - timedelta(days=1)
        print(f"⬇ Backfilling {ticker} from {start_floor.date()} to {backfill_end.date()}")
        backfill = _download_slice(ticker, start_floor, backfill_end + timedelta(days=1))
        if not backfill.empty:
            parts.append(backfill)

    # Forward update (or initial fetch).
    if last_date is None:
        forward_start = start_floor
        print(f"⬇ Downloading history for {ticker} from {forward_start.date()}")
    else:
        forward_start = last_date + timedelta(days=1)
        if forward_start >= datetime.today():
            print(f"✅ {ticker}: Already up to date")
            forward_start = None
        else:
            print(f"🔄 Updating {ticker} from {forward_start.date()}")

    if forward_start is not None:
        forward = _download_slice(ticker, forward_start, datetime.today() + timedelta(days=1))
        if not forward.empty:
            parts.append(forward)

    if not parts:
        print(f"⚠ No data for {ticker}")
        return
    combined = pd.concat(parts, ignore_index=True)
    combined.drop_duplicates(subset=["Date"], inplace=True)

    combined.sort_values("Date", inplace=True)
    combined.to_csv(filepath, index=False)
    print(f"✅ {ticker}: {len(combined)} rows")


def main():
    ap = argparse.ArgumentParser(description="Fetch daily price history for the Nifty universe.")
    ap.add_argument("--start-year", type=int, default=None, help="Backfill history starting from this year.")
    ap.add_argument("--history-years", type=int, default=5, help="Default history length if no start-year.")
    ap.add_argument("--max-tickers", type=int, default=0, help="Probe mode: limit tickers processed (0 = all).")
    args = ap.parse_args()

    df = pd.read_csv(UNIVERSE_FILE)
    symbols = df["Symbol"].tolist()
    if int(args.max_tickers) > 0:
        symbols = symbols[: int(args.max_tickers)]

    print(f"🚀 Downloading prices for {len(symbols)} Nifty stocks")

    for sym in symbols:
        try:
            fetch_and_update(sym, start_year=args.start_year, history_years=args.history_years)
        except Exception as e:
            print(f"❌ {sym}: {e}")


if __name__ == "__main__":
    main()
