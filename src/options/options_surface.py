#!/usr/bin/env python3
import os
import pandas as pd
import numpy as np

CHAIN = "data/options/chains/nifty_options.parquet"
OUT = "data/options/options_surface.parquet"

os.makedirs(os.path.dirname(OUT), exist_ok=True)


def run():
    print("📊 Building Options Surface")

    if not os.path.exists(CHAIN):
        print(f"❌ Options chain not found: {CHAIN}")
        return

    df = pd.read_parquet(CHAIN)

    # Expected columns: date, expiry, strike, option_type (C/P), iv, close, spot
    # Basic validation
    req = {"date","expiry","strike","option_type","iv","close","spot"}
    missing = [c for c in req if c not in df.columns]
    if missing:
        print(f"⚠️ Missing columns in chain: {missing}")

    # Normalize dtypes
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df['expiry'] = pd.to_datetime(df['expiry'], errors='coerce')

    # Moneyness and tenor
    df["moneyness"] = df["strike"] / df["spot"].replace(0, np.nan)
    df["days_to_expiry"] = (df["expiry"] - df["date"]).dt.days

    # Cross-sectional buckets for IV Rank
    # Use rolling history per (option_type, m_bucket) to compute rank in [0,1]
    df["m_bucket"] = pd.cut(df["moneyness"], [0.6,0.8,0.9,0.97,1.03,1.1,1.25,1.5])

    def iv_rank(s: pd.Series) -> pd.Series:
        window = 60
        rolling_min = s.rolling(window).min()
        rolling_max = s.rolling(window).max()
        denom = (rolling_max - rolling_min).replace(0, np.nan)
        rank = (s - rolling_min) / (denom + 1e-9)
        return rank.clip(0, 1)

    df = df.sort_values(["option_type","m_bucket","date"]).reset_index(drop=True)
    df["iv_rank"] = df.groupby(["option_type","m_bucket"], dropna=False)["iv"].transform(iv_rank)

    # Skew per (date, expiry): mean OTM put IV minus mean OTM call IV
    puts = df[(df["option_type"]=="P") & (df["moneyness"] < 0.95)]
    calls = df[(df["option_type"]=="C") & (df["moneyness"] > 1.05)]
    skew = (
        puts.groupby(["date","expiry"])['iv'].mean()
        - calls.groupby(["date","expiry"])['iv'].mean()
    ).rename('skew').reset_index()

    df = df.merge(skew, on=["date","expiry"], how="left")

    # Term structure per date: near vs far IV
    iv_term = df.groupby(["date","expiry"])['iv'].mean().reset_index()
    iv_term = iv_term.sort_values(["date","expiry"])  # for clarity

    # Persist surface
    df.to_parquet(OUT)
    print("✅ Options surface saved →", OUT)


if __name__ == "__main__":
    run()
