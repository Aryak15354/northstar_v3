"""Event-based daily features from NLP-enriched sentiment artifacts."""

from __future__ import annotations

import pandas as pd


POSITIVE_EVENTS = {
    "earnings_beat",
    "order_win",
    "capex_announcement",
    "regulatory_action_positive",
    "buyback_announcement",
    "dividend_announcement",
}
NEGATIVE_EVENTS = {
    "earnings_miss",
    "fraud_allegation",
    "regulatory_action_negative",
    "order_loss",
    "management_change_negative",
    "promoter_pledge_increase",
}


def add_event_features(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    work = df.copy()
    dominant = work.get("dominant_event_type", pd.Series(index=work.index, dtype=str)).fillna("unknown").astype(str)
    market_moving = work.get("market_moving_count", pd.Series(0.0, index=work.index, dtype=float))
    work["event_positive_flag"] = dominant.isin(POSITIVE_EVENTS).astype(float)
    work["event_negative_flag"] = dominant.isin(NEGATIVE_EVENTS).astype(float)
    work["event_macro_flag"] = dominant.str.startswith("macro_").astype(float)
    work["event_market_moving_intensity"] = pd.to_numeric(market_moving, errors="coerce").fillna(0.0)
    return work
