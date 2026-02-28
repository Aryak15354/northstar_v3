import pandas as pd

VOL = "data/processed/volatility_state.parquet"
SCORES = "data/processed/scores.parquet"
PRICES = "data/processed/prices.parquet"
OUT = "data/processed/stock_roles.parquet"

print("🛡 Building Risk Classification Engine...")

vol = pd.read_parquet(VOL)
scores = pd.read_parquet(SCORES)
prices = pd.read_parquet(PRICES)

# latest liquidity
liq = prices.sort_values("Date").groupby("ticker").tail(30)
liq = liq.groupby("ticker")["Volume"].mean().reset_index()
liq.columns = ["ticker", "avg_volume"]

df = scores.merge(vol, on="ticker").merge(liq, on="ticker")

def classify(row):
    if row["volatility_regime"] == "High":
        if row["northstar_score"] > 70:
            return "Directional"
        else:
            return "Speculative"
    else:
        if row["northstar_score"] > 70 and row["true_undervaluation"] > 60:
            return "Income"
        elif row["northstar_score"] > 60:
            return "Safe"
        else:
            return "Avoid"

df["stock_role"] = df.apply(classify, axis=1)

out = df[["ticker", "Industry", "stock_role", "northstar_score", "realized_vol", "volatility_regime"]]

out.to_parquet(OUT, index=False)

print(f"✅ Risk Classification built: {len(out)} stocks")
print("📁 Saved to data/processed/stock_roles.parquet")
