import pandas as pd

scores = pd.read_parquet("data/processed/scores.parquet")
vol = pd.read_parquet("data/processed/options_volatility.parquet")
timing = pd.read_parquet("data/processed/options_timing.parquet")

df = scores.merge(vol, on="ticker").merge(timing, on="ticker")

def classify(r):
    if r["overbought"] or r["realized_vol"] > 0.5:
        return "Avoid"
    if r["true_undervaluation"] > 60 and r["realized_vol"] < 0.3:
        return "Income Safe"
    if r["market_score"] > 60:
        return "Directional"
    return "Neutral"

df["options_regime"] = df.apply(classify, axis=1)

df[["ticker", "options_regime", "realized_vol", "true_undervaluation", "market_score"]] \
  .to_parquet("data/processed/options_regime.parquet", index=False)

print("✅ options_regime.parquet created")
