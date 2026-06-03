"""Narrative momentum and topic-drift features from NLP outputs."""

from __future__ import annotations

import pandas as pd


def add_narrative_features(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    work = df.copy()
    work["headline_count"] = pd.to_numeric(work.get("headline_count", work.get("news_volume")), errors="coerce").fillna(0.0)
    work["sentiment_polarity"] = pd.to_numeric(work.get("sentiment_polarity"), errors="coerce").fillna(0.0)
    work["sentiment_conviction"] = pd.to_numeric(work.get("sentiment_conviction"), errors="coerce").fillna(0.0)
    if "ticker" in work.columns and "date" in work.columns:
        work = work.sort_values(["ticker", "date"], kind="mergesort")
        grouped = work.groupby("ticker", sort=False)
        work["narrative_momentum"] = grouped["sentiment_polarity"].transform(lambda series: series.ewm(span=5, adjust=False).mean() - series.ewm(span=20, adjust=False).mean())
        work["topic_drift"] = grouped["headline_count"].transform(lambda series: series.diff().fillna(0.0))
    else:
        work["narrative_momentum"] = 0.0
        work["topic_drift"] = 0.0
    work["narrative_strength"] = work["narrative_momentum"] * work["sentiment_conviction"]
    return work
