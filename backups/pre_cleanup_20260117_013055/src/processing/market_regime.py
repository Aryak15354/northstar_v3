import pandas as pd
import numpy as np

PRICES = "data/processed/prices.parquet"
TECH = "data/processed/technicals.parquet"
OUT = "data/processed/market_regime.parquet"

print("📊 Building Market Regime Engine...")


import pandas as pd
import numpy as np

PRICES = "data/processed/prices.parquet"
TECH = "data/processed/technicals.parquet"
OUT = "data/processed/market_regime.parquet"

print("📊 Building Market Regime Engine...")

prices = pd.read_parquet(PRICES)
tech = pd.read_parquet(TECH)

# Merge price & technicals
df = prices.merge(tech, on=["ticker", "Date"], how="left")
df = df.sort_values(["Date", "ticker"])
dates = sorted(df["Date"].unique())
records = []

window = 30
for i in range(window, len(dates)):
    d = dates[i]
    window_dates = dates[i-window:i]
    window_df = df[df["Date"].isin(window_dates)]
    day = df[df["Date"] == d]

    if len(day) < 300:
        continue

    # Breadth
    breadth = (day["Close_x"] > day["ema200"]).mean()

    # Participation (stocks near 3-month highs)
    highs = window_df.groupby("ticker")["Close_x"].max()
    cur = day.set_index("ticker")["Close_x"]
    common_tickers = cur.index.intersection(highs.index)
    participation = (cur.loc[common_tickers] >= highs.loc[common_tickers] * 0.97).mean()

    # Volatility (rolling std of returns)
    window_df = window_df.sort_values(["ticker", "Date"])
    returns = window_df.groupby("ticker")["Close_x"].pct_change()
    volatility = returns.std()

    # Correlation (fragility) - rolling window
    wide = window_df.pivot(index="Date", columns="ticker", values="Close_x")
    try:
        corr = wide.pct_change(fill_method=None).corr().mean().mean()
    except Exception:
        corr = 0

    # Regime Scoring
    risk_on = (breadth * 0.4 + participation * 0.6)
    fragility = corr
    panic = volatility * 100 if not np.isnan(volatility) else 0

    if risk_on > 0.6 and panic < 2:
        regime = "Bull"
    elif risk_on > 0.5 and fragility > 0.6:
        regime = "Fragile"
    elif panic > 3:
        regime = "Panic"
    else:
        regime = "Bear"

    records.append({
        "Date": d,
        "breadth": round(breadth, 3),
        "participation": round(participation, 3),
        "volatility": round(volatility, 4) if not np.isnan(volatility) else 0,
        "correlation": round(fragility, 3) if not np.isnan(fragility) else 0,
        "risk_on_score": round(risk_on, 3),
        "market_regime": regime
    })
