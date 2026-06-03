#!/usr/bin/env python3
"""
Weekly-portfolio backtester and 6M walk-forward KPIs for live-on-paper portfolios.

Inputs:
- data/portfolio/pnl_on_paper.parquet (built by pnl_paper.py)
- data/processed/prices.parquet (for benchmark proxy)

Outputs:
- data/portfolio/pnl_kpis.json  (overall and last 6M window)
"""
import os
import json
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

PNL_FILE = 'data/portfolio/pnl_on_paper.parquet'
PRICES_FILE = 'data/processed/prices.parquet'
OUT_FILE = 'data/portfolio/pnl_kpis.json'

os.makedirs('data/portfolio', exist_ok=True)


def max_drawdown(series):
    cummax = np.maximum.accumulate(series)
    dd = (series / cummax) - 1.0
    return float(dd.min()) if len(dd) else 0.0


def kpis_from_returns(df):
    if df.empty:
        return {
            'period_days': 0,
            'total_return': 0.0,
            'ann_return': 0.0,
            'volatility': 0.0,
            'sharpe': 0.0,
            'max_drawdown': 0.0,
            'calmar': 0.0
        }
    ret = df['Return']
    total_ret = float((1 + ret).prod() - 1)
    days = len(ret)
    ann_return = float((1 + total_ret) ** (252 / max(1, days)) - 1) if days > 0 else 0.0
    vol = float(ret.std() * np.sqrt(252)) if days > 1 else 0.0
    sharpe = float(ann_return / vol) if vol > 1e-9 else 0.0
    eq = (1 + ret).cumprod()
    mdd = max_drawdown(eq)
    calmar = float(ann_return / abs(mdd)) if mdd < 0 else 0.0
    return {
        'period_days': days,
        'total_return': total_ret,
        'ann_return': ann_return,
        'volatility': vol,
        'sharpe': sharpe,
        'max_drawdown': mdd,
        'calmar': calmar
    }


def compute_benchmark_proxy(start_date=None, end_date=None):
    if not os.path.exists(PRICES_FILE):
        return None
    prices = pd.read_parquet(PRICES_FILE)
    prices['Date'] = pd.to_datetime(prices['Date'])
    if start_date:
        prices = prices[prices['Date'] >= start_date]
    if end_date:
        prices = prices[prices['Date'] <= end_date]
    # Proxy benchmark as equal-weight return across universe each day
    pivot = prices.pivot(index='Date', columns='ticker', values='Close').ffill()
    ret_tbl = pivot.pct_change().dropna(how='all')
    bench_ret = ret_tbl.mean(axis=1).fillna(0.0)
    return pd.DataFrame({'Date': bench_ret.index, 'Return': bench_ret.values})


def align_period(df, months=6):
    if df.empty:
        return df
    end = df['Date'].iloc[-1]
    start = end - pd.DateOffset(months=months)
    return df[df['Date'] >= start]


def main():
    if not os.path.exists(PNL_FILE):
        print('⚠️ pnl_on_paper not found')
        return
    pnl = pd.read_parquet(PNL_FILE)
    pnl['Date'] = pd.to_datetime(pnl['Date'])

    # Overall KPIs
    kpi_all = kpis_from_returns(pnl[['Date','Return']])

    # 6M walk-forward KPIs
    pnl_6m = align_period(pnl)
    kpi_6m = kpis_from_returns(pnl_6m[['Date','Return']])

    # Benchmark proxies
    bench_all = compute_benchmark_proxy(start_date=pnl['Date'].min(), end_date=pnl['Date'].max())
    bench_6m = compute_benchmark_proxy(start_date=pnl_6m['Date'].min() if not pnl_6m.empty else None,
                                       end_date=pnl['Date'].max())
    kpi_bench_all = kpis_from_returns(bench_all) if bench_all is not None else None
    kpi_bench_6m = kpis_from_returns(bench_6m) if bench_6m is not None else None

    out = {
        'generated': datetime.now().isoformat(),
        'kpis_all': kpi_all,
        'kpis_6m': kpi_6m,
        'benchmark_all': kpi_bench_all,
        'benchmark_6m': kpi_bench_6m
    }
    with open(OUT_FILE, 'w') as f:
        json.dump(out, f, indent=2)
    print(f"✅ KPIs saved: {OUT_FILE}")


if __name__ == '__main__':
    main()
