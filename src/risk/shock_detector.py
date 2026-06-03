#!/usr/bin/env python3
import os
import pandas as pd
import numpy as np

MACRO = "data/macro/factors/macro_score.parquet"
MARKET = "data/processed/market_regime.parquet"
OUT_DIR = "data/risk"
OUT = os.path.join(OUT_DIR, "shock_state.parquet")

os.makedirs(OUT_DIR, exist_ok=True)


def run():
    print("⚡ Building Shock State")
    if not (os.path.exists(MACRO) and os.path.exists(MARKET)):
        print("❌ Missing macro/market inputs for shock detection")
        return

    macro = pd.read_parquet(MACRO)
    if not isinstance(macro.index, pd.DatetimeIndex) and 'Date' in macro.columns:
        macro['Date'] = pd.to_datetime(macro['Date'], errors='coerce')
        macro = macro.set_index('Date')

    market = pd.read_parquet(MARKET)
    if 'Date' in market.columns:
        market['Date'] = pd.to_datetime(market['Date'], errors='coerce')
        market = market.set_index('Date')

    # Align weekly with macro index
    mk = market.copy()
    mk = mk.resample('W-FRI').last()
    df = macro.join(mk, how='inner')

    # Inputs that may exist from earlier work
    ms = df.get('MarketStress_z', pd.Series(index=df.index, data=np.nan))
    breadth = df.get('breadth', pd.Series(index=df.index, data=np.nan))
    participation = df.get('participation', pd.Series(index=df.index, data=np.nan))
    corr = df.get('correlation', pd.Series(index=df.index, data=np.nan))
    vol = df.get('volatility', pd.Series(index=df.index, data=np.nan))

    # Define shock level 0-3 based on stress/internals
    level = pd.Series(index=df.index, dtype=int)
    level[:] = 0
    # Level 3: extreme stress
    level[(ms > 1.0) | ((breadth < 0.35) & (participation < 0.25)) | ((corr > 0.7) & (vol > vol.rolling(12).median()))] = 3
    # Level 2: high stress
    lvl2 = (ms > 0.5) | (breadth < 0.45) | (participation < 0.30) | (corr > 0.6)
    level[lvl2 & (level < 2)] = 2
    # Level 1: elevated
    lvl1 = (ms > 0.0) | (breadth < 0.55) | (participation < 0.35)
    level[lvl1 & (level < 1)] = 1

    # Map to max exposure caps
    cap_map = {0: 1.00, 1: 0.80, 2: 0.60, 3: 0.40}
    shock_cap = level.map(cap_map).astype(float)

    out = pd.DataFrame({
        'Shock_Level': level,
        'Shock_Max_Exposure': shock_cap
    }, index=df.index)

    out.to_parquet(OUT)
    print(f"✅ Shock state saved → {OUT}")


if __name__ == "__main__":
    run()
