#!/usr/bin/env python3
import os
import re
import pandas as pd
from pathlib import Path

RAW_ROOT = Path("data/raw")
OUT_DIR = Path("data/market")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Expected folder layout (flexible):
# data/raw/prices/*.csv           -> per-ticker OHLCV or Close time series
# data/raw/technicals/*.csv       -> per-ticker feature time series
# data/raw/financials/*.csv       -> per-ticker financial snapshot time series
# Also supports flat: data/raw/daily_prices.csv, technicals.csv, financials.csv

PRICE_OUT = OUT_DIR / "daily_prices.parquet"
TECH_OUT = OUT_DIR / "technicals.parquet"
FIN_OUT = OUT_DIR / "financials.parquet"


def read_glob_csv(folder: Path, infer_ticker_from_filename: bool = True, recursive: bool = False) -> pd.DataFrame:
    if not folder.exists():
        return pd.DataFrame()
    parts = []
    pattern = "**/*.csv" if recursive else "*.csv"
    for fp in folder.glob(pattern):
        try:
            df = pd.read_csv(fp)
            # unify date col
            if 'Date' not in df.columns and 'date' in df.columns:
                df = df.rename(columns={'date': 'Date'})
            if 'Date' not in df.columns:
                # skip if no date
                continue
            df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
            df = df.dropna(subset=['Date'])
            # ensure ticker
            if 'ticker' not in df.columns and 'Ticker' in df.columns:
                df = df.rename(columns={'Ticker': 'ticker'})
            if 'ticker' not in df.columns and infer_ticker_from_filename:
                # infer from filename (strip extension)
                t = fp.stem.upper()
                # simple cleanup
                t = re.sub(r"[^A-Z0-9._-]", "", t)
                df['ticker'] = t
            parts.append(df)
        except Exception:
            continue
    if not parts:
        return pd.DataFrame()
    df = pd.concat(parts, ignore_index=True)
    # de-dup
    if {'Date','ticker'}.issubset(df.columns):
        df = df.sort_values(['ticker','Date']).drop_duplicates(subset=['ticker','Date'], keep='last')
    return df


def read_flat_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(path)
        if 'Date' not in df.columns and 'date' in df.columns:
            df = df.rename(columns={'date': 'Date'})
        if 'Date' in df.columns:
            df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
            df = df.dropna(subset=['Date'])
        return df
    except Exception:
        return pd.DataFrame()


def normalize_prices(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    # Try to produce [Date, ticker, Close]
    # If Close not present, prefer Adj Close/close
    for c in ['Close','close','Adj Close','adj_close']:
        if c in df.columns:
            df = df.rename(columns={c: 'Close'})
            break
    # fallback: if only OHLC exists, compute Close from one of them
    if 'Close' not in df.columns:
        for c in ['AdjClose','CLOSE','LAST']:
            if c in df.columns:
                df = df.rename(columns={c: 'Close'})
                break
    # keep essential
    keep = ['Date','ticker','Close']
    keep = [c for c in keep if c in df.columns]
    return df[keep].copy()


def run():
    print("📥 Ingesting market CSVs from data/raw → data/market parquets")

    # PRICES
    prices = pd.DataFrame()
    # Try structured subfolder first, then recursive raw scan fallback
    # Prefer existing v3 folder names
    prices_glob = read_glob_csv(RAW_ROOT / 'prices_daily', recursive=True)
    if prices_glob.empty:
        prices_glob = read_glob_csv(RAW_ROOT / 'prices', recursive=True)
    prices_flat = read_flat_csv(RAW_ROOT / 'daily_prices.csv')
    if not prices_glob.empty:
        prices = prices_glob
    elif not prices_flat.empty:
        prices = prices_flat
    prices = normalize_prices(prices)
    if not prices.empty:
        prices.to_parquet(PRICE_OUT)
        print(f"✅ Prices → {PRICE_OUT} ({len(prices)} rows)")
    else:
        print("⚠️ No prices found under data/raw")

    # TECHNICALS
    tech = pd.DataFrame()
    tech_glob = read_glob_csv(RAW_ROOT / 'technicals', recursive=True)
    tech_flat = read_flat_csv(RAW_ROOT / 'technicals.csv')
    if not tech_glob.empty:
        tech = tech_glob
    elif not tech_flat.empty:
        tech = tech_flat
    if not tech.empty:
        tech.to_parquet(TECH_OUT)
        print(f"✅ Technicals → {TECH_OUT} ({len(tech)} rows)")
    else:
        print("⚠️ No technicals found under data/raw")

    # FINANCIALS
    fin = pd.DataFrame()
    fin_glob = read_glob_csv(RAW_ROOT / 'financials_quarterly', recursive=True)
    if fin_glob.empty:
        fin_glob = read_glob_csv(RAW_ROOT / 'financials', recursive=True)
    fin_flat = read_flat_csv(RAW_ROOT / 'financials.csv')
    if not fin_glob.empty:
        fin = fin_glob
    elif not fin_flat.empty:
        fin = fin_flat
    if not fin.empty:
        fin.to_parquet(FIN_OUT)
        print(f"✅ Financials → {FIN_OUT} ({len(fin)} rows)")
    else:
        print("⚠️ No financials found under data/raw")

    # If still empty, attempt a generic recursive scan and classify
    if prices.empty or tech.empty or fin.empty:
        print("🔍 Falling back to recursive raw scan and classification…")
        price_parts, tech_parts, fin_parts = [], [], []
        for fp in RAW_ROOT.glob("**/*.csv"):
            try:
                df = pd.read_csv(fp)
                df_columns = set([c.lower() for c in df.columns])
                is_price = any(c in df_columns for c in ['close','adj close','open','high','low'])
                is_fin = any(c in df_columns for c in ['total_assets','ebitda','net_income','revenue','book_value'])
                # Heuristic by folder name
                path_str = str(fp).lower()
                if 'price' in path_str or 'ohlc' in path_str:
                    is_price = True
                if 'fin' in path_str or 'financial' in path_str:
                    is_fin = True
                is_tech = (not is_price and not is_fin) or ('rsi' in df_columns or 'macd' in df_columns or 'atr' in df_columns)
                # unify
                if 'Date' not in df.columns and 'date' in df.columns:
                    df = df.rename(columns={'date':'Date'})
                if 'Date' in df.columns:
                    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
                    df = df.dropna(subset=['Date'])
                if 'ticker' not in df.columns and 'Ticker' in df.columns:
                    df = df.rename(columns={'Ticker':'ticker'})
                if 'ticker' not in df.columns:
                    t = fp.stem.upper()
                    df['ticker'] = t
                if is_price:
                    price_parts.append(df)
                elif is_fin:
                    fin_parts.append(df)
                else:
                    tech_parts.append(df)
            except Exception:
                continue
        if prices.empty and price_parts:
            prices = normalize_prices(pd.concat(price_parts, ignore_index=True))
            if not prices.empty:
                prices = prices.sort_values(['ticker','Date']).drop_duplicates(['ticker','Date'], keep='last')
                prices.to_parquet(PRICE_OUT)
                print(f"✅ Prices (fallback) → {PRICE_OUT} ({len(prices)} rows)")
        if tech.empty and tech_parts:
            tech = pd.concat(tech_parts, ignore_index=True)
            tech = tech.sort_values(['ticker','Date']).drop_duplicates(['ticker','Date'], keep='last')
            tech.to_parquet(TECH_OUT)
            print(f"✅ Technicals (fallback) → {TECH_OUT} ({len(tech)} rows)")
        if fin.empty and fin_parts:
            fin = pd.concat(fin_parts, ignore_index=True)
            fin = fin.sort_values(['ticker','Date']).drop_duplicates(['ticker','Date'], keep='last')
            fin.to_parquet(FIN_OUT)
            print(f"✅ Financials (fallback) → {FIN_OUT} ({len(fin)} rows)")

    print("📦 Ingestion complete")


if __name__ == "__main__":
    run()
