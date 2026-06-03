import pandas as pd

IN = "data/processed/market_regime.parquet"
OUT = "data/processed/regime_momentum.parquet"

df = pd.read_parquet(IN).sort_values("Date")

# 20-day deltas
for col, newc in [("breadth", "breadth_delta"), ("volatility", "volatility_delta"), ("correlation", "correlation_delta")]:
    if col in df.columns:
        df[newc] = df[col].diff(20)
    else:
        df[newc] = 0.0

# Regime momentum score
df["regime_momentum"] = (
    df.get("breadth_delta", 0) - df.get("volatility_delta", 0) - df.get("correlation_delta", 0)
)

# Classify
try:
    df["regime_state"] = pd.cut(
        df["regime_momentum"],
        [-10, -0.01, 0.01, 10],
        labels=["Cracking", "Neutral", "Healing"]
    )
except Exception:
    df["regime_state"] = "Neutral"

df.to_parquet(OUT, index=False)
print("✅ Regime Momentum saved")
