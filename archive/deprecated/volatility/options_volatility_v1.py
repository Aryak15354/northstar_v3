import pandas as pd

PRICES = "data/processed/prices.parquet"
OUT = "data/processed/options_volatility.parquet"

df = pd.read_parquet(PRICES)

vols = []

for tkr, g in df.groupby("ticker"):
    g = g.sort_values("Date").tail(60)

    returns = g["Close"].pct_change()
    realized = returns.std() * (252 ** 0.5)
    atr = (g["High"] - g["Low"]).rolling(14).mean().iloc[-1]

    vols.append({
        "ticker": tkr,
        "realized_vol": realized,
        "atr": atr
    })

pd.DataFrame(vols).to_parquet(OUT, index=False)
print("✅ options_volatility.parquet created")
