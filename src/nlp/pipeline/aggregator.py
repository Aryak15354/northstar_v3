"""Daily aggregation helpers for headline-level NLP outputs."""

from __future__ import annotations

from collections import Counter
from typing import Any

import numpy as np
import pandas as pd


def normalize_symbol(value: Any) -> str:
    return str(value or "").replace(".NS", "").replace(".BO", "").strip().upper()


def storage_ticker(root: str, preferred: Any = None) -> str:
    preferred_text = str(preferred or "").strip()
    if preferred_text:
        if preferred_text.endswith(".NS") or preferred_text.endswith(".BO"):
            return preferred_text
        if "." in preferred_text:
            return preferred_text
        return f"{normalize_symbol(preferred_text)}.NS"
    return f"{normalize_symbol(root)}.NS" if root else ""


def _weighted_average(values: pd.Series, weights: pd.Series) -> float:
    work_values = pd.to_numeric(values, errors="coerce").fillna(0.0)
    work_weights = pd.to_numeric(weights, errors="coerce").fillna(0.0)
    if float(work_weights.sum()) <= 0.0:
        work_weights = pd.Series(np.ones(len(work_values)), index=work_values.index)
    return float(np.average(work_values, weights=work_weights))


def aggregate_company_daily(scored_df: pd.DataFrame) -> pd.DataFrame:
    if scored_df.empty:
        return pd.DataFrame(
            columns=[
                "ticker",
                "date",
                "availability_date",
                "sentiment_polarity",
                "sentiment_conviction",
                "news_volume",
                "source",
                "sentiment_surprise",
                "sentiment_uncertainty",
                "headline_count",
                "dominant_event_type",
                "dominant_event_direction",
                "market_moving_count",
                "nlp_model_version",
            ]
        )

    work = scored_df.copy()
    work["date"] = pd.to_datetime(work["date"], errors="coerce")
    work["availability_date"] = pd.to_datetime(work["availability_date"], errors="coerce")
    work["ticker_root"] = work.get("ticker").map(normalize_symbol)
    if "resolved_tickers" in work.columns:
        work["resolved_ticker_list"] = work["resolved_tickers"].fillna("").map(
            lambda value: [item.strip() for item in str(value).split(",") if item.strip()]
        )
    else:
        work["resolved_ticker_list"] = [[] for _ in range(len(work))]
    work["ticker_list"] = work.apply(
        lambda row: row["resolved_ticker_list"] if row["resolved_ticker_list"] else ([row["ticker_root"]] if row["ticker_root"] else []),
        axis=1,
    )
    work = work.explode("ticker_list")
    work = work[work["ticker_list"].notna() & work["ticker_list"].astype(str).ne("")]
    if work.empty:
        return pd.DataFrame()

    work["ticker"] = work.apply(lambda row: storage_ticker(row["ticker_list"], row.get("ticker")), axis=1)
    work["date"] = work["date"].dt.normalize()
    work["availability_date"] = work["availability_date"].dt.normalize()

    def build_group(group: pd.DataFrame) -> pd.Series:
        event_counts = Counter(group.get("event_type", pd.Series(dtype=str)).fillna("unknown").astype(str))
        dominant_event, _ = event_counts.most_common(1)[0] if event_counts else ("unknown", 0)
        dominant_rows = group[group.get("event_type", "").astype(str) == dominant_event]
        dominant_direction = (
            str(dominant_rows["event_direction"].iloc[0])
            if not dominant_rows.empty and "event_direction" in dominant_rows.columns
            else "neutral"
        )
        source_mode = group["source"].mode()
        model_mode = group.get("sentiment_model_version", pd.Series(dtype=str)).mode()
        return pd.Series(
            {
                "sentiment_polarity": _weighted_average(group["polarity"], group["sentiment_confidence"]),
                "sentiment_conviction": float(pd.to_numeric(group["sentiment_confidence"], errors="coerce").fillna(0.0).mean()),
                "news_volume": int(len(group)),
                "source": str(source_mode.iloc[0]) if not source_mode.empty else "nlp_pipeline",
                "availability_date": group["availability_date"].min(),
                "headline_count": int(len(group)),
                "dominant_event_type": dominant_event,
                "dominant_event_direction": dominant_direction,
                "market_moving_count": int(pd.to_numeric(group["is_market_moving"], errors="coerce").fillna(0).sum()),
                "nlp_model_version": str(model_mode.iloc[0]) if not model_mode.empty else "heuristic_finance_v1",
            }
        )

    grouped = work.groupby(["ticker", "date"], dropna=False)
    daily = (
        _group_apply(grouped, build_group)
        .reset_index()
        .sort_values(["ticker", "date"], kind="mergesort")
        .reset_index(drop=True)
    )
    daily["sentiment_uncertainty"] = (1.0 - daily["sentiment_conviction"]).clip(0.0, 1.0)
    daily["sentiment_surprise"] = (
        daily.groupby("ticker")["sentiment_polarity"].transform(lambda series: series - series.rolling(20, min_periods=5).mean())
    ).fillna(0.0)
    return daily


def aggregate_market_daily(scored_df: pd.DataFrame) -> pd.DataFrame:
    if scored_df.empty:
        return pd.DataFrame(
            columns=[
                "date",
                "availability_date",
                "india_market_polarity",
                "india_market_conviction",
                "india_market_uncertainty",
                "global_risk_sentiment",
                "news_volume_total",
                "dominant_shock_type",
                "shock_severity_numeric",
                "shock_confidence",
                "nlp_model_version",
            ]
        )

    work = scored_df.copy()
    work["date"] = pd.to_datetime(work["date"], errors="coerce").dt.normalize()
    work["availability_date"] = pd.to_datetime(work["availability_date"], errors="coerce").dt.normalize()

    shock_map = {
        "macro_rate_hike": "rate_hike_rbi",
        "macro_rate_cut": "rate_cut_rbi",
        "macro_crude_spike": "oil_price_spike",
        "macro_geopolitical": "geopolitical_conflict",
        "macro_fii_outflow": "fii_outflow",
        "macro_fii_inflow": "fii_inflow",
        "macro_inflation_high": "inflation_surprise_high",
        "macro_inflation_low": "inflation_surprise_low",
    }

    def build_group(group: pd.DataFrame) -> pd.Series:
        polarity = _weighted_average(group["polarity"], group["sentiment_confidence"])
        conviction = float(pd.to_numeric(group["sentiment_confidence"], errors="coerce").fillna(0.0).mean())
        macro_rows = group[group.get("event_type", "").astype(str).str.startswith("macro_")]
        if macro_rows.empty:
            dominant_shock = "none"
            shock_confidence = 0.0
        else:
            top_idx = pd.to_numeric(macro_rows.get("event_confidence"), errors="coerce").fillna(0.0).idxmax()
            event_type = str(macro_rows.loc[top_idx, "event_type"])
            dominant_shock = shock_map.get(event_type, "unknown")
            shock_confidence = float(pd.to_numeric(macro_rows.loc[top_idx, "event_confidence"], errors="coerce") or 0.0)
        severity = min(
            5,
            int(
                abs(float(polarity)) * 3.0
                + float((group.get("event_materiality", pd.Series(dtype=str)) == "high").sum()) * 0.4
            ),
        )
        model_mode = group.get("sentiment_model_version", pd.Series(dtype=str)).mode()
        return pd.Series(
            {
                "availability_date": group["availability_date"].min(),
                "india_market_polarity": float(polarity),
                "india_market_conviction": conviction,
                "india_market_uncertainty": float(max(0.0, 1.0 - conviction)),
                "global_risk_sentiment": float(polarity),
                "news_volume_total": int(len(group)),
                "dominant_shock_type": dominant_shock,
                "shock_severity_numeric": int(severity),
                "shock_confidence": float(shock_confidence),
                "nlp_model_version": str(model_mode.iloc[0]) if not model_mode.empty else "heuristic_finance_v1",
            }
        )

    grouped = work.groupby("date", dropna=False)
    return (
        _group_apply(grouped, build_group)
        .reset_index()
        .sort_values("date", kind="mergesort")
        .reset_index(drop=True)
    )


def merge_daily_frames(existing: pd.DataFrame, incoming: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    if existing is None or existing.empty:
        return incoming.copy()
    if incoming is None or incoming.empty:
        return existing.copy()
    existing = existing.copy()
    incoming = incoming.copy()
    key_tuples = set(tuple(row) for row in incoming[keys].itertuples(index=False, name=None))
    filtered = existing[
        ~existing[keys].apply(lambda row: tuple(row.values.tolist()) in key_tuples, axis=1)
    ].copy()
    merged = pd.concat([filtered, incoming], ignore_index=True)
    return merged.sort_values(keys, kind="mergesort").reset_index(drop=True)


def _group_apply(grouped: pd.core.groupby.generic.DataFrameGroupBy, fn):
    try:
        return grouped.apply(fn, include_groups=False)
    except TypeError:
        return grouped.apply(fn)
