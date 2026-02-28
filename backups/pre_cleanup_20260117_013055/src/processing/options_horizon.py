import pandas as pd

PRICES = "data/processed/prices.parquet"
OUT = "data/processed/options_horizon.parquet"

df = pd.read_parquet(PRICES)

rows = []

for tkr, g in df.groupby("ticker"):
    g = g.sort_values("Date").tail(120)
    returns = g["Close"].pct_change()

    vol = returns.std()
    avg_move = returns.abs().mean()

    if vol == 0:
        continue

    horizon = min(60, max(5, int(avg_move / vol * 30)))

    rows.append({
        "ticker": tkr,
        "expected_days": horizon
    })

pd.DataFrame(rows).to_parquet(OUT, index=False)
print("✅ options_horizon.parquet created")
