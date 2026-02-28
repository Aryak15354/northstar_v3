import pandas as pd
import numpy as np

PRICES = "data/processed/prices.parquet"
OUT = "data/processed/volatility_state.parquet"

print("⚡ Building Volatility Intelligence Engine...")

df = pd.read_parquet(PRICES)
df = df.sort_values(["ticker", "Date"])

records = []

for ticker, g in df.groupby("ticker"):
    g["ret"] = g["Close"].pct_change()
    g["vol"] = g["ret"].rolling(30).std() * np.sqrt(252)
    g["atr"] = (g["High"] - g["Low"]).rolling(14).mean()

    g["vol_pct"] = g["vol"].rank(pct=True)

    latest = g.tail(1).iloc[0]

    if pd.isna(latest["vol"]):
        continue

    if latest["vol_pct"] < 0.33:
        regime = "Low"
    elif latest["vol_pct"] < 0.66:
        regime = "Normal"
    else:
        regime = "High"

    records.append({
        "ticker": ticker,
        "realized_vol": round(latest["vol"], 3),
        "volatility_percentile": round(latest["vol_pct"], 3),
        "atr": round(latest["atr"], 2),
        "volatility_regime": regime
    })

out = pd.DataFrame(records)
out.to_parquet(OUT, index=False)

print(f"✅ Volatility state built: {len(out)} stocks")
print("📁 Saved to data/processed/volatility_state.parquet")
