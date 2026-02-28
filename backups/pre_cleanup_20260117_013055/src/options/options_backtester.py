#!/usr/bin/env python3
import os
import pandas as pd
import numpy as np

CHAIN = "data/options/chains/nifty_options.parquet"
STRATEGY = "data/options/strategy_book.parquet"
OUT = "data/options/options_backtest.parquet"

# Backtest controls
MAX_DAYS = 10
STOP_LOSS = -0.30  # -30% of premium outlay
# Transaction costs and slippage
TC_RATE = 0.001  # 10 bps per leg trade notional
SLIPPAGE = 0.0015  # 15 bps slippage on entry/exit prices

os.makedirs(os.path.dirname(OUT), exist_ok=True)


def run():
    print("📉 Running options backtest")

    if not (os.path.exists(CHAIN) and os.path.exists(STRATEGY)):
        print("❌ Missing inputs for backtest")
        return

    chain = pd.read_parquet(CHAIN)
    chain['date'] = pd.to_datetime(chain['date'], errors='coerce')
    chain['expiry'] = pd.to_datetime(chain['expiry'], errors='coerce')

    strategies = pd.read_parquet(STRATEGY)
    strategies['date'] = pd.to_datetime(strategies['date'], errors='coerce')

    results = []

    # Group trades by date/strategy/symbol so we evaluate legs together
    group_cols = ['date','strategy'] + (['symbol'] if 'symbol' in strategies.columns else [])
    for keys, legs in strategies.groupby(group_cols):
        if isinstance(keys, tuple):
            trade_date, strat_name, *rest = keys
            symbol = rest[0] if rest else 'NIFTY'
        else:
            trade_date, strat_name = keys, legs['strategy'].iloc[0]
            symbol = legs['symbol'].iloc[0] if 'symbol' in legs.columns else 'NIFTY'
        # initial cost (premium)
        cost = 0.0
        tc_entry = 0.0
        for _, leg in legs.iterrows():
            q = float(leg['qty'])
            # entry price
            px0 = chain[(chain['date']==trade_date) &
                        (chain['expiry']==leg['expiry']) &
                        (chain['strike']==leg['strike']) &
                        (chain['option_type']==leg['option_type'])]['close']
            if len(px0):
                price = float(px0.iloc[0]) * (1 + SLIPPAGE * np.sign(q))
                cost += price * q
                tc_entry += abs(price * q) * TC_RATE
        if cost == 0:
            continue

        cur_date = trade_date
        days = 0
        pnl = 0.0
        while days < MAX_DAYS:
            day_chain = chain[chain['date']==cur_date]
            cur_val = 0.0
            tc_exit = 0.0
            for _, leg in legs.iterrows():
                px = day_chain[(day_chain['expiry']==leg['expiry']) &
                               (day_chain['strike']==leg['strike']) &
                               (day_chain['option_type']==leg['option_type'])]['close']
                if len(px):
                    price = float(px.iloc[0]) * (1 - SLIPPAGE * np.sign(leg['qty']))
                    cur_val += price * float(leg['qty'])
                    tc_exit += abs(price * float(leg['qty'])) * TC_RATE
            gross_pnl = cur_val - cost
            total_tc = tc_entry + tc_exit
            pnl = gross_pnl - total_tc
            # stop-loss on return basis
            ret = pnl / abs(cost) if cost != 0 else 0
            if ret < STOP_LOSS:
                break
            days += 1
            cur_date = cur_date + pd.Timedelta(days=1)
            # exit if all legs expired
            if all(cur_date >= pd.to_datetime(leg['expiry']) for _, leg in legs.iterrows()):
                break

        results.append({
            'date': trade_date,
            'strategy': strat_name,
            'symbol': symbol,
            'days_held': days,
            'gross_pnl': gross_pnl,
            'tc': total_tc,
            'net_pnl': pnl,
            'gross_return': gross_pnl/abs(cost) if cost!=0 else 0,
            'net_return': pnl/abs(cost) if cost!=0 else 0
        })

    out = pd.DataFrame(results)
    out.to_parquet(OUT)

    print("✅ Backtest complete →", OUT)
    if not out.empty:
        print(out.groupby(['strategy'])['net_return'].mean())


if __name__ == "__main__":
    run()
