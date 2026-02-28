#!/usr/bin/env python3
"""
Builds PnL-on-paper equity curve from stored weekly portfolios and daily prices.

Inputs:
- data/portfolio/weekly/*.parquet (weights per ticker)
- data/processed/prices.parquet (columns: Date, ticker, Close)

Output:
- data/portfolio/pnl_on_paper.parquet with columns: Date, Equity, Return
"""
import os
import glob
import pandas as pd
import numpy as np

WEEKLY_DIR = 'data/portfolio/weekly'
PRICES_FILE = 'data/processed/prices.parquet'
OUT_FILE = 'data/portfolio/pnl_on_paper.parquet'

os.makedirs('data/portfolio', exist_ok=True)


def load_weekly_snapshots():
    files = sorted(glob.glob(os.path.join(WEEKLY_DIR, '*.parquet')))
    snapshots = []
    for f in files:
        try:
            df = pd.read_parquet(f)
            df = df[['ticker','weight','Industry']] if 'Industry' in df.columns else df[['ticker','weight']]
            date = pd.to_datetime(os.path.basename(f).replace('.parquet',''), errors='coerce')
            if pd.isna(date):
                continue
            df['date'] = date
            snapshots.append(df)
        except Exception:
            continue
    if not snapshots:
        return pd.DataFrame(columns=['date','ticker','weight'])
    all_snap = pd.concat(snapshots, ignore_index=True)
    return all_snap


def compute_equity_curve():
    weekly = load_weekly_snapshots()
    if weekly.empty:
        return pd.DataFrame(columns=['Date','Equity','Return'])

    prices = pd.read_parquet(PRICES_FILE)
    if 'Date' not in prices.columns:
        raise ValueError('prices.parquet must have Date')
    prices['Date'] = pd.to_datetime(prices['Date'])

    # Pivot prices to tickers for faster calc
    prices = prices.sort_values(['Date','ticker'])
    price_tbl = prices.pivot(index='Date', columns='ticker', values='Close').ffill()

    # Build weight schedule per day by forward filling weekly weights until next week
    weekly_pivot = weekly.pivot_table(index='date', columns='ticker', values='weight', fill_value=0.0)
    # Reindex to daily trading days in prices
    weight_daily = weekly_pivot.reindex(price_tbl.index, method='ffill').fillna(0.0)

    # Align columns
    common_cols = weight_daily.columns.intersection(price_tbl.columns)
    weight_daily = weight_daily[common_cols]
    price_tbl = price_tbl[common_cols]

    # Compute daily returns for each ticker
    ret_tbl = price_tbl.pct_change().fillna(0.0)

    # Portfolio daily return = sum(weights_prev_day * returns_today)
    weight_prev = weight_daily.shift(1).fillna(0.0)
    port_ret = (weight_prev * ret_tbl).sum(axis=1)
    equity = (1 + port_ret).cumprod()

    return pd.DataFrame({'Date': port_ret.index, 'Equity': equity.values, 'Return': port_ret.values})


def main():
    eq = compute_equity_curve()
    if not eq.empty:
        eq.to_parquet(OUT_FILE)
        print(f"✅ PnL-on-paper saved: {OUT_FILE}")
    else:
        print("⚠️ No weekly portfolios or prices to compute PnL-on-paper")


if __name__ == '__main__':
    main()
