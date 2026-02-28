#!/usr/bin/env python3
import os
import pandas as pd
import numpy as np

REGIME = "data/options/options_regime.parquet"
SURFACE = "data/options/options_surface.parquet"
RISK = "data/macro/factors/risk_budget.parquet"
OUT = "data/options/strategy_book.parquet"

os.makedirs(os.path.dirname(OUT), exist_ok=True)


def pick_atm(chain: pd.DataFrame) -> pd.DataFrame:
    if chain.empty:
        return chain
    idx = (chain["moneyness"] - 1).abs().argsort()
    return chain.iloc[[idx.iloc[0]]]


def build_straddle(chain):
    atm = pick_atm(chain)
    if atm.empty:
        return None, None
    strike = float(atm["strike"].iloc[0])
    expiry = atm["expiry"].iloc[0]
    legs = [
        ("C", strike, expiry, 1),
        ("P", strike, expiry, 1)
    ]
    return legs, "LONG_STRADDLE"


def build_iron_condor(chain):
    atm = pick_atm(chain)
    if atm.empty:
        return None, None
    s = float(atm["strike"].iloc[0])
    expiry = atm["expiry"].iloc[0]
    legs = [
        ("P", round(s*0.95, 2), expiry, -1),
        ("P", round(s*0.90, 2), expiry, 1),
        ("C", round(s*1.05, 2), expiry, -1),
        ("C", round(s*1.10, 2), expiry, 1),
    ]
    return legs, "IRON_CONDOR"


def build_calendar(chain):
    # Choose ATM; sell near, buy far with same strike and option type
    atm = pick_atm(chain)
    if atm.empty:
        return None, None
    strike = float(atm["strike"].iloc[0])
    # get option type with higher liquidity; assume calls
    option_type = "C"
    # choose near/far expiries
    expiries = sorted(chain["expiry"].unique())
    if len(expiries) < 2:
        return None, None
    near, far = expiries[0], expiries[-1]
    legs = [
        (option_type, strike, near, -1),
        (option_type, strike, far, 1)
    ]
    return legs, "CALENDAR"


def build_put_ratio(chain):
    puts = chain[(chain["option_type"]=="P") & (chain["moneyness"]<1)]
    if puts.empty:
        return None, None
    otm = puts.sort_values("moneyness").iloc[0]
    atm = pick_atm(puts)
    if atm.empty:
        return None, None
    expiry = atm["expiry"].iloc[0]
    legs = [
        ("P", float(atm["strike"].iloc[0]), expiry, 1),
        ("P", float(otm["strike"]), expiry, -2)
    ]
    return legs, "PUT_RATIO"


def run():
    print("🧠 Generating option strategies")
    if not (os.path.exists(REGIME) and os.path.exists(SURFACE)):
        print("❌ Missing inputs for strategy generation")
        return

    regime_df = pd.read_parquet(REGIME)
    regime = regime_df.iloc[-1]["options_regime"]
    # Aggressiveness by options regime (fraction of budget)
    aggr_map = {
        "LOW_VOL_SELL": 0.8,
        "RISING_VOL_BUY": 0.6,
        "HIGH_VOL_SELL": 0.5,
        "CRASH_HEDGE": 0.3,
        "NEUTRAL": 0.0,
    }
    aggr = aggr_map.get(regime, 0.0)
    # Pull latest macro risk budget
    budget = 0.5
    if os.path.exists(RISK):
        try:
            rb = pd.read_parquet(RISK)
            budget = float(rb.iloc[-1]["Max_Equity_Exposure"]) if not rb.empty else 0.5
        except Exception:
            pass

    surface = pd.read_parquet(SURFACE)
    today = surface["date"].max()
    chain = surface[surface["date"] == today].copy()

    # Support multi-symbol chains via 'symbol' column (default 'NIFTY')
    symbols = chain['symbol'].unique().tolist() if 'symbol' in chain.columns else ['NIFTY']
    if 'symbol' not in chain.columns:
        chain['symbol'] = 'NIFTY'

    books = []
    for sym in symbols:
        sym_chain = chain[chain['symbol'] == sym]
        legs = None
        name = None
        if regime == "LOW_VOL_SELL":
            legs, name = build_iron_condor(sym_chain)
        elif regime == "RISING_VOL_BUY":
            legs, name = build_straddle(sym_chain)
        elif regime == "HIGH_VOL_SELL":
            legs, name = build_calendar(sym_chain)
        elif regime == "CRASH_HEDGE":
            legs, name = build_put_ratio(sym_chain)
        else:
            continue

        if legs is None:
            continue

        # Regime-aware sizing: qty multiplier proportional to budget*aggr
        qty_mult = max(0, int(round(budget * aggr * 10)))
        if qty_mult == 0:
            qty_mult = 1  # place minimal structure for tracking

        trade = pd.DataFrame(legs, columns=["option_type","strike","expiry","qty"])
        trade["qty"] = trade["qty"].astype(float) * qty_mult
        trade["strategy"] = name
        trade["date"] = today
        trade["symbol"] = sym
        trade["risk_budget"] = budget
        trade["options_regime"] = regime
        books.append(trade)

    if not books:
        print("NEUTRAL or no viable chains: no trade")
        return
    book = pd.concat(books, ignore_index=True)
    book.to_parquet(OUT)
    print(f"✅ Strategy generated for {len(symbols)} symbols, regime={regime}, budget={budget:.2f}")
    print(book.head())


if __name__ == "__main__":
    run()
