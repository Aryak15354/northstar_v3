"""FeatureFactory-friendly sentiment features from NLP aggregates."""

from __future__ import annotations

import pandas as pd


def add_sentiment_features(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    work = df.copy()
    work["sentiment_polarity"] = pd.to_numeric(work.get("sentiment_polarity"), errors="coerce").fillna(0.0)
    work["sentiment_conviction"] = pd.to_numeric(work.get("sentiment_conviction"), errors="coerce").fillna(0.0)
    work["news_volume"] = pd.to_numeric(work.get("news_volume"), errors="coerce").fillna(0.0)
    if "date" in work.columns and "ticker" in work.columns:
        work = work.sort_values(["ticker", "date"], kind="mergesort")
        grouped = work.groupby("ticker", sort=False)
        work["sentiment_polarity_5d_ma"] = grouped["sentiment_polarity"].transform(lambda series: series.rolling(5, min_periods=1).mean())
        work["sentiment_polarity_momentum"] = grouped["sentiment_polarity"].transform(lambda series: series - series.shift(5))
        work["sentiment_volume_20d_avg"] = grouped["news_volume"].transform(lambda series: series.rolling(20, min_periods=1).mean())
    else:
        work["sentiment_polarity_5d_ma"] = work["sentiment_polarity"]
        work["sentiment_polarity_momentum"] = 0.0
        work["sentiment_volume_20d_avg"] = work["news_volume"]
    work["sentiment_volume_spike"] = work["news_volume"] / work["sentiment_volume_20d_avg"].replace(0.0, 1.0)
    work["sentiment_conviction_x_polarity"] = work["sentiment_conviction"] * work["sentiment_polarity"]
    return work
