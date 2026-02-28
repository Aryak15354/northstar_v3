#!/usr/bin/env python3
"""
Strategy Backtester: weekly rebalanced comparison across strategies.

Assumptions (current data availability):
- Uses current strategy selection/weights as the target weights.
- Rebalances to the same weights weekly over the chosen lookback.
- Daily prices from data/processed/prices.parquet.

Outputs:
- Equity curves per strategy (pd.DataFrame)
- KPIs per strategy (dict)
"""
import os
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

from src.strategies import compare_strategies

PRICES_FILE = "data/processed/prices.parquet"


def _load_prices_pivot() -> pd.DataFrame:
    if not os.path.exists(PRICES_FILE):
        raise FileNotFoundError(PRICES_FILE)
    px = pd.read_parquet(PRICES_FILE)
    px['Date'] = pd.to_datetime(px['Date'])
    pivot = px.pivot(index='Date', columns='ticker', values='Close').ffill()
    return pivot


def _kpis(returns: pd.Series) -> dict:
    if returns is None or returns.empty:
        return {'ann_return':0.0,'vol':0.0,'sharpe':0.0,'max_dd':0.0}
    r = returns
    total = float((1+r).prod() - 1)
    n = len(r)
    ann = float((1+total)**(252/max(1,n)) - 1)
    vol = float(r.std()*np.sqrt(252)) if n>1 else 0.0
    sharpe = float(ann/vol) if vol>1e-9 else 0.0
    eq = (1+r).cumprod()
    dd = float((eq/eq.cummax()-1).min())
    return {'ann_return':ann,'vol':vol,'sharpe':sharpe,'max_dd':dd}


def backtest_strategies(strategies: list[str], lookback_days: int = 252, max_names: int = 30) -> tuple[pd.DataFrame, dict]:
    pivot = _load_prices_pivot()
    if pivot.empty:
        return pd.DataFrame(), {}
    # Limit lookback window
    pivot = pivot.tail(lookback_days + 1)
    ret = pivot.pct_change().dropna(how='all')

    # Build static weights for each strategy via current data
    cfg = {'max_names': int(max_names)}
    port_map = compare_strategies(strategies, cfg)

    equity = pd.DataFrame(index=ret.index)
    kpis = {}
    for name, df in port_map.items():
        if not isinstance(df, pd.DataFrame) or df.empty or 'ticker' not in df.columns or 'weight' not in df.columns:
            continue
        w = df.set_index('ticker')['weight']
        # Map possible .NS differences
        common = ret.columns.intersection(w.index)
        if len(common) == 0:
            alt = w.copy()
            alt.index = [f"{t}.NS" if not str(t).endswith('.NS') else str(t) for t in alt.index]
            common = ret.columns.intersection(alt.index)
            w = alt
        if len(common) == 0:
            continue
        w = w.reindex(common).fillna(0.0)
        # Weekly rebalanced to same weights (static target)
        port_r = (ret[common] * w).sum(axis=1)
        equity[name] = (1 + port_r).cumprod()
        kpis[name] = _kpis(port_r)

    return equity, kpis


if __name__ == '__main__':
    eq, ks = backtest_strategies(['northstar','mom_6m','value_tilt'], lookback_days=252, max_names=30)
    print(eq.tail())
    print(ks)
