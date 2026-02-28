import pandas as pd
import ta
import numpy as np

PRICE_FILE = "data/processed/prices.parquet"
OUTPUT_FILE = "data/processed/technicals.parquet"


def compute_indicators(df):
    df = df.sort_values("Date")

    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    volume = df["Volume"]

    # Trend
    df["ema20"] = ta.trend.EMAIndicator(close, 20).ema_indicator()
    df["ema50"] = ta.trend.EMAIndicator(close, 50).ema_indicator()
    df["ema200"] = ta.trend.EMAIndicator(close, 200).ema_indicator()
    df["adx"] = ta.trend.ADXIndicator(high, low, close).adx()

    # Momentum
    df["rsi"] = ta.momentum.RSIIndicator(close, 14).rsi()
    df["macd"] = ta.trend.MACD(close).macd()
    df["roc"] = ta.momentum.ROCIndicator(close, 10).roc()

    # Volatility
    df["atr"] = ta.volatility.AverageTrueRange(high, low, close).average_true_range()
    bb = ta.volatility.BollingerBands(close)
    df["bb_width"] = (bb.bollinger_hband() - bb.bollinger_lband()) / close

    # Breakout detection
    df["high_52w"] = close.rolling(252).max()
    df["breakout_strength"] = close / df["high_52w"]

    # Volume surge
    df["vol_avg"] = volume.rolling(50).mean()
    df["volume_surge"] = volume / df["vol_avg"]

    # Trend regime
    df["trend_regime"] = (
        (df["ema20"] > df["ema50"]) &
        (df["ema50"] > df["ema200"]) &
        (df["adx"] > 20)
    ).astype(int)

    return df


def main():
    prices = pd.read_parquet(PRICE_FILE)

    out = []

    for ticker, grp in prices.groupby("ticker"):
        try:
            ind = compute_indicators(grp)
            ind["ticker"] = ticker
            out.append(ind)
        except Exception as e:
            print(f"❌ {ticker}: {e}")

    tech = pd.concat(out)
    tech = tech.sort_values(["ticker", "Date"])

    tech.to_parquet(OUTPUT_FILE, index=False)
    print("✅ Advanced technicals created")


if __name__ == "__main__":
    main()
