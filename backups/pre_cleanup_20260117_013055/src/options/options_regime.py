#!/usr/bin/env python3
import pandas as pd
import numpy as np
import os

VIX_FILE = "data/market/india_vix.parquet"
MARKET_STATE = "data/processed/market_regime.parquet"
MACRO = "data/macro/factors/macro_score.parquet"
OUT = "data/options/options_regime.parquet"

os.makedirs(os.path.dirname(OUT), exist_ok=True)


def run():
    print("🧠 Computing Options Regime")

    if not (os.path.exists(VIX_FILE) and os.path.exists(MARKET_STATE) and os.path.exists(MACRO)):
        print("❌ Missing required inputs for options regime.")
        return

    vix = pd.read_parquet(VIX_FILE)
    # Ensure index datetime
    if not isinstance(vix.index, pd.DatetimeIndex):
        if 'Date' in vix.columns:
            vix['Date'] = pd.to_datetime(vix['Date'], errors='coerce')
            vix = vix.set_index('Date')
    vix = vix.sort_index()

    market = pd.read_parquet(MARKET_STATE)
    if 'Date' in market.columns:
        market['Date'] = pd.to_datetime(market['Date'], errors='coerce')
        market = market.sort_values('Date')
        market = market.set_index('Date')

    macro = pd.read_parquet(MACRO)
    if not isinstance(macro.index, pd.DatetimeIndex):
        if 'Date' in macro.columns:
            macro['Date'] = pd.to_datetime(macro['Date'], errors='coerce')
            macro = macro.set_index('Date')

    # Align dates
    df = vix.join(market, how="inner")
    df = df.join(macro, how="inner")

    # Expect VIX column name; fallback to first column
    if 'VIX' not in df.columns:
        # try common names
        vix_col = None
        for c in df.columns:
            if c.lower() in ('vix', 'india_vix', 'ivix'):
                vix_col = c
                break
        if vix_col is None:
            vix_col = df.columns[0]
        df = df.rename(columns={vix_col: 'VIX'})

    # Volatility metrics
    df["vix_ma20"] = df["VIX"].rolling(20).mean()
    df["vix_trend"] = df["VIX"] - df["vix_ma20"]

    # Realized volatility proxy from market_regime
    # Expect 'volatility' column
    if 'volatility' not in df.columns:
        print("⚠️ No realized volatility in market_regime; setting to VIX/2 as proxy")
        df['realized_vol'] = df['VIX'] / 2.0
    else:
        df['realized_vol'] = df['volatility']

    # Stress proxy
    corr = df.get('correlation', pd.Series(index=df.index, data=np.nan))
    vol = df.get('volatility', pd.Series(index=df.index, data=np.nan))
    df["stress"] = (corr.fillna(0) * vol.fillna(0)).clip(lower=0)

    def classify(row):
        if row["stress"] > 0.20 or row.get("MacroScore", 0) < -1:
            return "CRASH_HEDGE"
        if (row["VIX"] < row["realized_vol"]) and (row["vix_trend"] <= 0):
            return "LOW_VOL_SELL"
        if (row["vix_trend"] > 0) and (row["VIX"] > row["realized_vol"]):
            return "RISING_VOL_BUY"
        if row["VIX"] > row["realized_vol"] * 1.5:
            return "HIGH_VOL_SELL"
        return "NEUTRAL"

    df["options_regime"] = df.apply(classify, axis=1)

    cols = [c for c in ["VIX","realized_vol","stress","options_regime"] if c in df.columns]
    df[cols].to_parquet(OUT)

    print("✅ Options regime saved →", OUT)


if __name__ == "__main__":
    run()
