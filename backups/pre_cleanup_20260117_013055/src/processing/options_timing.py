import pandas as pd

PRICES = "data/processed/prices.parquet"
TECH = "data/processed/technicals.parquet"
OUT = "data/processed/options_timing.parquet"

df = pd.read_parquet(PRICES).merge(
    pd.read_parquet(TECH),
    on=["ticker", "Date"],
    how="left"
)

signals = []

for tkr, g in df.groupby("ticker"):
    g = g.sort_values("Date").tail(120)
    try:
        price = g["Close_x"].iloc[-1]
        sma50 = g["sma50"].iloc[-1] if "sma50" in g else g["ema50"].iloc[-1] if "ema50" in g else g["Close_x"].iloc[-1]
        sma200 = g["sma200"].iloc[-1] if "sma200" in g else g["ema200"].iloc[-1] if "ema200" in g else g["Close_x"].iloc[-1]
        rsi = g["rsi"].iloc[-1] if "rsi" in g else 50
        pullback = (price > sma50) and (price < sma50 * 1.03)
        breakout = price > g["High_x"].rolling(60).max().iloc[-2]
        overbought = rsi > 70
        signals.append({
            "ticker": tkr,
            "pullback": pullback,
            "breakout": breakout,
            "overbought": overbought
        })
    except KeyError as e:
        continue

pd.DataFrame(signals).to_parquet(OUT, index=False)
print("✅ options_timing.parquet created")
