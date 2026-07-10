#!/usr/bin/env python3
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from math import log
from typing import Any

import pandas as pd
import streamlit as st

from src.dashboard.data_contract import DashboardDataContract
from src.dashboard.models import DashboardFilters
from src.dashboard.v3_data_hub import V3DataHub
from src.dashboard.visual_catalog import (
    PROJECT_ROOT,
    _df_or_empty,
    _ensure_datetime,
    _frame,
    _latest_per_group,
    _normalize_nav,
    _normalize_state_history,
    _normalize_unified_daily,
    _parse_component_status,
    _parse_governor_budgets,
    _parse_options_active_positions,
    _parse_options_iv_history,
    _parse_pipeline_freshness,
    _parse_state_log,
    _parse_strategy_weights,
    _read_csv,
    _read_json,
    _read_jsonl,
    _read_parquet,
)


def _enrich_portfolio_weights(weights: pd.DataFrame, unified_portfolio: pd.DataFrame) -> pd.DataFrame:
    if weights is None or weights.empty:
        return pd.DataFrame()
    working = weights.copy()
    if "weight" not in working.columns and "final_weight" in working.columns:
        working["weight"] = pd.to_numeric(working["final_weight"], errors="coerce")
    if "date" in working.columns:
        working["date"] = pd.to_datetime(working["date"], errors="coerce")

    if unified_portfolio is None or unified_portfolio.empty or "ticker" not in unified_portfolio.columns:
        return working

    enrich_cols = [col for col in ["ticker", "Industry", "Company Name", "position_role", "northstar_score", "mispricing"] if col in unified_portfolio.columns]
    latest = unified_portfolio[enrich_cols].drop_duplicates(subset=["ticker"], keep="last")
    merged = working.merge(
        latest.rename(
            columns={
                "Industry": "industry_lookup",
                "Company Name": "company_lookup",
                "position_role": "role_lookup",
                "northstar_score": "northstar_score_lookup",
                "mispricing": "mispricing_lookup",
            }
        ),
        on="ticker",
        how="left",
    )
    if "Industry" not in merged.columns:
        merged["Industry"] = merged.get("industry_lookup")
    else:
        merged["Industry"] = merged["Industry"].replace({"Unknown": pd.NA, "nan": pd.NA}).combine_first(merged.get("industry_lookup"))
        merged["Industry"] = merged["Industry"].fillna("Unknown")
    if "Company Name" not in merged.columns and "company_lookup" in merged.columns:
        merged["Company Name"] = merged["company_lookup"]
    if "position_role" in merged.columns and "role_lookup" in merged.columns:
        merged["position_role"] = merged["position_role"].fillna(merged["role_lookup"])
    if "northstar_score_lookup" in merged.columns and "northstar_score" not in merged.columns:
        merged["northstar_score"] = merged["northstar_score_lookup"]
    if "mispricing_lookup" in merged.columns and "mispricing" not in merged.columns:
        merged["mispricing"] = merged["mispricing_lookup"]
    return merged.drop(columns=[col for col in ["industry_lookup", "company_lookup", "role_lookup", "northstar_score_lookup", "mispricing_lookup"] if col in merged.columns])


def _load_sentiment_frames() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    market_sentiment = _ensure_datetime(_read_parquet(PROJECT_ROOT / "data/processed/sentiment/market_sentiment_daily.parquet"), "date", "availability_date")
    ticker_sentiment = _ensure_datetime(_read_parquet(PROJECT_ROOT / "data/processed/sentiment/ticker_sentiment_daily.parquet"), "date", "availability_date")
    daily_sentiment = _ensure_datetime(_read_parquet(PROJECT_ROOT / "data/processed/sentiment/daily_sentiment_aggregated.parquet"), "date")

    ticker_sentiment_fallback = pd.DataFrame()
    if not ticker_sentiment.empty:
        ticker_sentiment_fallback = (
            ticker_sentiment.groupby("date", dropna=False)
            .agg(
                india_market_polarity=("sentiment_polarity", "mean"),
                india_market_conviction=("sentiment_conviction", "mean"),
                india_market_uncertainty=("sentiment_uncertainty", "mean"),
                news_volume_total=("news_volume", "sum"),
            )
            .reset_index()
        )

    if not daily_sentiment.empty:
        daily_fallback = daily_sentiment[["date", "sentiment_mean", "conviction_mean", "uncertainty_mean", "headline_count"]].copy()
        daily_fallback = daily_fallback.rename(
            columns={
                "sentiment_mean": "india_market_polarity",
                "conviction_mean": "india_market_conviction",
                "uncertainty_mean": "india_market_uncertainty",
                "headline_count": "news_volume_total",
            }
        )
        if market_sentiment.empty:
            market_sentiment = ticker_sentiment_fallback.copy() if not ticker_sentiment_fallback.empty else daily_fallback.copy()
        else:
            for fallback_df, suffix in [
                (ticker_sentiment_fallback, "__ticker_fallback"),
                (daily_fallback, "__daily_fallback"),
            ]:
                if fallback_df.empty:
                    continue
                market_sentiment = market_sentiment.merge(fallback_df, on="date", how="outer", suffixes=("", suffix))
            for column in [
                "india_market_polarity",
                "india_market_conviction",
                "india_market_uncertainty",
                "news_volume_total",
            ]:
                for fallback_col in [f"{column}__ticker_fallback", f"{column}__daily_fallback"]:
                    if fallback_col in market_sentiment.columns:
                        if column not in market_sentiment.columns:
                            market_sentiment[column] = market_sentiment[fallback_col]
                        else:
                            market_sentiment[column] = market_sentiment[column].combine_first(market_sentiment[fallback_col])
                        market_sentiment = market_sentiment.drop(columns=[fallback_col])
            if "availability_date" not in market_sentiment.columns:
                market_sentiment["availability_date"] = market_sentiment["date"]
        market_sentiment = market_sentiment.sort_values("date")

    latest_ticker_sentiment = _latest_per_group(ticker_sentiment, "ticker", "date")
    return market_sentiment, ticker_sentiment, daily_sentiment, latest_ticker_sentiment


def _normalize_strategy_performance(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    working = df.copy()
    if "strategy_name" not in working.columns:
        for source in ["strategy", "strategy_id"]:
            if source in working.columns:
                working["strategy_name"] = working[source].astype(str)
                break
    if "sharpe_ratio" not in working.columns and "sharpe" in working.columns:
        working["sharpe_ratio"] = pd.to_numeric(working["sharpe"], errors="coerce")
    if "total_return" in working.columns:
        working["total_return"] = pd.to_numeric(working["total_return"], errors="coerce")
    if "max_drawdown" in working.columns:
        working["max_drawdown"] = pd.to_numeric(working["max_drawdown"], errors="coerce")
    if "final_equity" in working.columns:
        working["final_equity"] = pd.to_numeric(working["final_equity"], errors="coerce")
    return working


def _normalize_strategy_regret(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    working = df.copy()
    if "strategy_name" not in working.columns:
        for source in ["strategy", "strategy_id"]:
            if source in working.columns:
                working["strategy_name"] = working[source].astype(str)
                break
    if "regret_score" not in working.columns:
        for source in ["regret_30d", "normalized_regret", "regret", "penalty_score"]:
            if source in working.columns:
                working["regret_score"] = pd.to_numeric(working[source], errors="coerce")
                break
    if "date" in working.columns:
        working = _latest_per_group(working, "strategy_name", "date")
    return working


def _safe_float(value: Any) -> float | None:
    try:
        numeric = pd.to_numeric(value, errors="coerce")
        if pd.isna(numeric):
            return None
        return float(numeric)
    except Exception:
        return None


def _safe_datetime(value: Any) -> datetime | None:
    if value in [None, "", "NaT", "None"]:
        return None
    try:
        parsed = pd.to_datetime(value, errors="coerce", format="mixed")
    except TypeError:
        parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None
    if getattr(parsed, "tzinfo", None) is not None:
        try:
            parsed = parsed.tz_localize(None)
        except TypeError:
            parsed = parsed.tz_convert(None)
    return parsed.to_pydatetime()


def _clip_unit_interval(value: Any) -> float | None:
    numeric = _safe_float(value)
    if numeric is None:
        return None
    return max(0.0, min(1.0, numeric))


def _first_non_null(*values: Any) -> Any:
    for value in values:
        if value is None:
            continue
        if isinstance(value, float) and pd.isna(value):
            continue
        return value
    return None


def _first_positive(*values: Any) -> float | None:
    for value in values:
        numeric = _safe_float(value)
        if numeric is not None and numeric > 0:
            return numeric
    return None


def _latest_row(df: pd.DataFrame, *date_cols: str) -> pd.Series | None:
    if df is None or df.empty:
        return None
    working = df.copy()
    for column in date_cols:
        if column in working.columns:
            working[column] = pd.to_datetime(working[column], errors="coerce")
            working = working.dropna(subset=[column]).sort_values(column)
            if not working.empty:
                return working.iloc[-1]
    return working.iloc[-1] if not working.empty else None


def _latest_market_row(bundle: dict[str, Any]) -> pd.Series | None:
    intelligent = _frame(bundle, "intelligent_market_state")
    row = _latest_row(intelligent, "date", "Date", "timestamp")
    if row is not None:
        return row
    market = _frame(bundle, "market_state")
    return _latest_row(market, "date", "Date", "timestamp")


def _coerce_datetime_series(series: pd.Series, *, normalize: bool = False) -> pd.Series:
    parsed = pd.to_datetime(series, errors="coerce", utc=True)
    if normalize:
        return parsed.dt.tz_convert(None).dt.normalize()
    return parsed.dt.tz_convert(None)


def _frame_last_timestamp(df: pd.DataFrame, *cols: str) -> datetime | None:
    if df is None or df.empty:
        return None
    for column in cols:
        if column not in df.columns:
            continue
        parsed = _coerce_datetime_series(df[column], normalize=False).dropna()
        if not parsed.empty:
            return parsed.max().to_pydatetime()
    return None


def _normalize_keyed_frame(df: pd.DataFrame, key: str, *, normalize_daily: bool = False) -> pd.DataFrame:
    if df is None or df.empty or key not in df.columns:
        return pd.DataFrame()
    working = df.copy()
    working[key] = _coerce_datetime_series(working[key], normalize=normalize_daily)
    working = working.dropna(subset=[key]).sort_values(key)
    if working.empty:
        return pd.DataFrame()
    return working.groupby(key, dropna=False).last().reset_index()


def _overlay_frame(base: pd.DataFrame, overlay: pd.DataFrame, key: str, *, normalize_daily: bool = False) -> pd.DataFrame:
    base_norm = _normalize_keyed_frame(base, key, normalize_daily=normalize_daily)
    overlay_norm = _normalize_keyed_frame(overlay, key, normalize_daily=normalize_daily)
    if base_norm.empty:
        return overlay_norm
    if overlay_norm.empty:
        return base_norm
    merged = base_norm.merge(overlay_norm, on=key, how="outer", suffixes=("", "__overlay"))
    for column in overlay_norm.columns:
        if column == key:
            continue
        overlay_col = f"{column}__overlay"
        if overlay_col not in merged.columns:
            continue
        if column not in merged.columns:
            merged[column] = merged[overlay_col]
        else:
            merged[column] = merged[overlay_col].where(merged[overlay_col].notna(), merged[column])
        merged = merged.drop(columns=[overlay_col])
    return merged.sort_values(key).reset_index(drop=True)


def _concat_dedup_frames(
    frames: list[pd.DataFrame],
    *,
    subset: list[str],
    sort_cols: list[str],
) -> pd.DataFrame:
    usable = [frame.copy() for frame in frames if isinstance(frame, pd.DataFrame) and not frame.empty]
    if not usable:
        return pd.DataFrame()
    combined = pd.concat(usable, ignore_index=True)
    for column in sort_cols:
        if column in combined.columns:
            combined[column] = _coerce_datetime_series(combined[column], normalize=False)
    present_subset = [column for column in subset if column in combined.columns]
    combined = combined.sort_values([column for column in sort_cols if column in combined.columns] or present_subset or combined.columns.tolist())
    if present_subset:
        combined = combined.drop_duplicates(subset=present_subset, keep="last")
    return combined.reset_index(drop=True)


def _status_is_healthy(source: str, status: str, age_hours: float | None) -> bool:
    normalized = (status or "").strip().lower()
    if source == "Alternative":
        max_age_hours = 24.0
        healthy_statuses = {"success", "ok", "healthy"}
    elif source in {"Orchestrator", "Options Runtime", "Heartbeat", "Alpha OS"}:
        max_age_hours = 0.5
        healthy_statuses = {
            "alive",
            "healthy",
            "success",
            "intraday_running",
            "running_eod",
            "waiting_market_open",
            "normal_operation",
            "day_complete",
        }
    else:
        max_age_hours = 6.0
        healthy_statuses = {"success", "ok", "healthy"}
    return age_hours is not None and age_hours <= max_age_hours and normalized in healthy_statuses


def _derive_sentiment_regime(polarity: Any, conviction: Any) -> str:
    polarity_value = _safe_float(polarity)
    conviction_value = _safe_float(conviction)
    if polarity_value is None:
        return "UNAVAILABLE"
    conviction_value = conviction_value or 0.0
    if polarity_value >= 0.2 and conviction_value >= 0.6:
        return "POSITIVE"
    if polarity_value <= -0.2 and conviction_value >= 0.6:
        return "NEGATIVE"
    return "NEUTRAL"


def _resolve_unified_daily(bundle: dict[str, Any]) -> pd.DataFrame:
    unified_daily = _frame(bundle, "unified_daily")
    market_state = _frame(bundle, "market_state")
    intelligent_market_state = _frame(bundle, "intelligent_market_state")

    result = _normalize_unified_daily(unified_daily)

    overlays: list[pd.DataFrame] = []
    for source in [market_state, intelligent_market_state]:
        if source.empty:
            continue
        working = source.copy()
        date_col = "date" if "date" in working.columns else "Date" if "Date" in working.columns else None
        if date_col is None:
            continue
        working["date"] = pd.to_datetime(working[date_col], errors="coerce").dt.normalize()
        mapped = pd.DataFrame(
            {
                "date": working["date"],
                "MacroScore": pd.to_numeric(working.get("macro_score"), errors="coerce"),
                "Regime": working.get("regime", working.get("macro_regime")),
                "MarketBreadth": pd.to_numeric(working.get("breadth_pct"), errors="coerce"),
                "MarketParticipation": pd.to_numeric(working.get("participation_score"), errors="coerce"),
                "Max_Equity_Exposure": pd.to_numeric(working.get("allowed_exposure"), errors="coerce"),
                "TrueStress": pd.to_numeric(working.get("stress_score"), errors="coerce"),
                "MarketStress_z": pd.to_numeric(working.get("stress_score"), errors="coerce"),
                "breadth": pd.to_numeric(working.get("breadth_pct"), errors="coerce"),
                "participation": pd.to_numeric(working.get("participation_score"), errors="coerce"),
                "volatility": pd.to_numeric(working.get("exposure_multiplier"), errors="coerce"),
                "correlation": pd.to_numeric(working.get("correlation"), errors="coerce"),
                "risk_on_score": pd.to_numeric(working.get("risk_on_probability"), errors="coerce"),
                "market_regime": working.get("regime"),
            }
        ).dropna(subset=["date"])
        if not mapped.empty:
            overlays.append(mapped.groupby("date", dropna=False).last().reset_index())

    if result.empty and overlays:
        result = overlays[0]
        overlays = overlays[1:]

    for overlay in overlays:
        if result.empty:
            result = overlay
            continue
        merged = result.merge(overlay, on="date", how="outer", suffixes=("", "__overlay"))
        for column in overlay.columns:
            if column == "date":
                continue
            overlay_col = f"{column}__overlay"
            if overlay_col not in merged.columns:
                continue
            if column not in merged.columns:
                merged[column] = merged[overlay_col]
            else:
                merged[column] = merged[overlay_col].combine_first(merged[column])
            merged = merged.drop(columns=[overlay_col])
        result = merged

    if result.empty:
        return result
    result["date"] = pd.to_datetime(result["date"], errors="coerce")
    return result.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)


def _historical_market_state_from_unified_daily(bundle: dict[str, Any]) -> pd.DataFrame:
    """Build a chart-friendly market-state history from long-horizon daily data.

    The canonical `market_state.parquet` is allowed to be a one-row live state
    snapshot. That is useful for badges, but it makes Market section charts look
    broken. For visualization we preserve the live row and fill historical
    columns from `unified_daily`, which is the long PIT-safe market spine.
    """
    unified_daily = _resolve_unified_daily(bundle)
    live_market = _frame(bundle, "market_state")

    if unified_daily.empty:
        return live_market

    out = pd.DataFrame(
        {
            "date": pd.to_datetime(unified_daily.get("date"), errors="coerce"),
            "macro_score": pd.to_numeric(unified_daily.get("MacroScore"), errors="coerce"),
            "regime": unified_daily.get("Regime", unified_daily.get("market_regime")),
            "macro_regime": unified_daily.get("Regime", unified_daily.get("market_regime")),
            "stress_score": pd.to_numeric(
                unified_daily.get("TrueStress", unified_daily.get("MarketStress_z")),
                errors="coerce",
            ),
            "breadth_pct": pd.to_numeric(
                unified_daily.get("MarketBreadth", unified_daily.get("breadth")),
                errors="coerce",
            ),
            "participation_score": pd.to_numeric(
                unified_daily.get("MarketParticipation", unified_daily.get("participation")),
                errors="coerce",
            ),
            "correlation": pd.to_numeric(unified_daily.get("correlation"), errors="coerce"),
            "risk_on_probability": pd.to_numeric(unified_daily.get("risk_on_score"), errors="coerce"),
            "allowed_exposure": pd.to_numeric(unified_daily.get("Max_Equity_Exposure"), errors="coerce"),
            "health_score": pd.to_numeric(unified_daily.get("health_score"), errors="coerce"),
        }
    )
    if "volatility" in unified_daily.columns:
        out["volatility_regime"] = pd.to_numeric(unified_daily["volatility"], errors="coerce")
    out = out.dropna(subset=["date"]).sort_values("date")

    if not live_market.empty:
        live = live_market.copy()
        if "date" not in live.columns:
            for column in ["Date", "timestamp"]:
                if column in live.columns:
                    live["date"] = live[column]
                    break
        if "date" in live.columns:
            live["date"] = pd.to_datetime(live["date"], errors="coerce")
            shared_cols = [col for col in out.columns if col in live.columns]
            live = live[shared_cols].dropna(subset=["date"])
            if not live.empty:
                out = pd.concat([out, live], ignore_index=True)

    if out.empty:
        return live_market
    return out.drop_duplicates(subset=["date"], keep="last").sort_values("date").reset_index(drop=True)


def _resolve_regime_history(bundle: dict[str, Any]) -> pd.DataFrame:
    current = _frame(bundle, "regime_history")
    market_state = _frame(bundle, "market_state")
    if market_state.empty or "date" not in market_state.columns:
        return current

    regime_col = next((col for col in ["regime", "macro_regime", "volatility_regime"] if col in market_state.columns), None)
    if regime_col is None:
        return current

    history = pd.DataFrame(
        {
            "date": _coerce_datetime_series(market_state["date"], normalize=False),
            "regime": market_state[regime_col].astype(str),
        }
    )
    column_map = {
        "breadth_pct": "breadth",
        "participation_score": "participation",
        "stress_score": "stress_score",
        "volatility_regime": "volatility_regime",
        "correlation": "correlation",
        "risk_on_probability": "risk_on_probability",
        "allowed_exposure": "allowed_exposure",
        "health_score": "health_score",
        "macro_score": "macro_score",
    }
    for source, target in column_map.items():
        if source not in market_state.columns:
            continue
        if target == "volatility_regime":
            history[target] = market_state[source]
        else:
            history[target] = pd.to_numeric(market_state[source], errors="coerce")

    history = history.dropna(subset=["date"]).sort_values("date")
    if history.empty:
        return current

    current_latest = _frame_last_timestamp(current, "date", "Date", "timestamp")
    history_latest = _frame_last_timestamp(history, "date")
    current_len = len(current) if isinstance(current, pd.DataFrame) else 0
    history_is_fresher = history_latest is not None and (current_latest is None or history_latest >= current_latest)
    if current.empty or len(history) > current_len or history_is_fresher:
        return history.reset_index(drop=True)
    return current


def _resolve_daily_sentiment(bundle: dict[str, Any]) -> pd.DataFrame:
    daily_sentiment = _frame(bundle, "daily_sentiment")
    market_sentiment = _frame(bundle, "market_sentiment")
    ticker_sentiment = _frame(bundle, "ticker_sentiment")

    overlays: list[pd.DataFrame] = []
    if not market_sentiment.empty and "date" in market_sentiment.columns:
        market_overlay = pd.DataFrame(
            {
                "date": market_sentiment["date"],
                "sentiment_mean": pd.to_numeric(market_sentiment.get("india_market_polarity"), errors="coerce"),
                "conviction_mean": pd.to_numeric(market_sentiment.get("india_market_conviction"), errors="coerce"),
                "uncertainty_mean": pd.to_numeric(market_sentiment.get("india_market_uncertainty"), errors="coerce"),
                "headline_count": pd.to_numeric(market_sentiment.get("news_volume_total"), errors="coerce"),
            }
        ).dropna(subset=["date"])
        if not market_overlay.empty:
            overlays.append(market_overlay)

    if not ticker_sentiment.empty and "date" in ticker_sentiment.columns:
        ticker_overlay = (
            ticker_sentiment.groupby("date", dropna=False)
            .agg(
                sentiment_mean=("sentiment_polarity", "mean"),
                conviction_mean=("sentiment_conviction", "mean"),
                uncertainty_mean=("sentiment_uncertainty", "mean"),
                headline_count=("news_volume", "sum"),
            )
            .reset_index()
        )
        if not ticker_overlay.empty:
            overlays.append(ticker_overlay)

    resolved = daily_sentiment.copy()
    for overlay in overlays:
        resolved = _overlay_frame(resolved, overlay, "date", normalize_daily=True)

    if resolved.empty:
        return resolved
    if "sentiment_regime" not in resolved.columns:
        resolved["sentiment_regime"] = pd.NA
    if {"sentiment_mean", "conviction_mean"}.issubset(resolved.columns):
        resolved["sentiment_regime"] = resolved.apply(
            lambda row: _derive_sentiment_regime(row.get("sentiment_mean"), row.get("conviction_mean")),
            axis=1,
        )
    return resolved.sort_values("date").reset_index(drop=True)


def _allocation_history_strategy_weights(bundle: dict[str, Any]) -> dict[str, float]:
    allocation_history = _frame(bundle, "allocation_history")
    if allocation_history.empty or "date" not in allocation_history.columns:
        return {}
    working = allocation_history.copy()
    working["date"] = pd.to_datetime(working["date"], errors="coerce")
    working = working.dropna(subset=["date"])
    if working.empty:
        return {}
    latest_date = working["date"].dt.normalize().max()
    latest = working[working["date"].dt.normalize() == latest_date].copy()
    meta_cols = {
        "date",
        "regime",
        "timestamp",
        "regime_name",
        "regime_stability",
        "exposure_cap",
        "total_exposure",
        "freeze_active",
        "cash",
        "momentum",
        "quality",
        "value",
        "strategy_name",
        "strategy_category",
        "allocation_weight",
        "allocation_score",
        "regime_fitness",
        "adjusted_return",
        "adjusted_sharpe",
        "risk_contribution",
        "allocation_reason",
        "no_edge_state",
    }
    strategy_weights: dict[str, float] = {}
    for column in latest.columns:
        if column in meta_cols:
            continue
        series = pd.to_numeric(latest[column], errors="coerce")
        if series.notna().sum() == 0:
            continue
        value = float(series.mean())
        if abs(value) > 1e-12:
            strategy_weights[column] = value
    return strategy_weights


def _resolve_strategy_weights(bundle: dict[str, Any]) -> pd.DataFrame:
    current = _frame(bundle, "strategy_weights")
    if not current.empty and pd.to_numeric(current.get("weight"), errors="coerce").abs().sum() > 0:
        return current.sort_values("weight", ascending=False).reset_index(drop=True)

    weights: dict[str, float] = {}
    options_dashboard_state = bundle.get("options_dashboard_state") or {}
    portfolio_overlay = options_dashboard_state.get("portfolio_overlay") or {}
    capital_allocation_top = portfolio_overlay.get("capital_allocation_top") or []
    if isinstance(capital_allocation_top, list):
        for row in capital_allocation_top:
            if not isinstance(row, dict):
                continue
            name = row.get("strategy")
            weight = _safe_float(row.get("allocation"))
            if name and weight is not None:
                weights[str(name)] = weight

    for name, weight in _allocation_history_strategy_weights(bundle).items():
        weights.setdefault(name, weight)

    alpha_os_posteriors = _frame(bundle, "alpha_os_posteriors")
    if alpha_os_posteriors.empty is False and {"timestamp", "strategy_name", "final_weight"}.issubset(alpha_os_posteriors.columns):
        latest_ts = alpha_os_posteriors["timestamp"].max()
        latest = alpha_os_posteriors[alpha_os_posteriors["timestamp"] == latest_ts].copy()
        latest["final_weight"] = pd.to_numeric(latest["final_weight"], errors="coerce")
        latest = latest.dropna(subset=["strategy_name", "final_weight"])
        if latest["final_weight"].abs().sum() > 0:
            for _, row in latest.iterrows():
                weights.setdefault(str(row["strategy_name"]), float(row["final_weight"]))

    if not weights:
        return pd.DataFrame(columns=["strategy", "weight"])

    return (
        pd.DataFrame([{"strategy": strategy, "weight": weight} for strategy, weight in weights.items()])
        .sort_values("weight", ascending=False)
        .reset_index(drop=True)
    )


def _resolve_alpha_os_posteriors(bundle: dict[str, Any]) -> pd.DataFrame:
    current = _frame(bundle, "alpha_os_posteriors")
    alpha_payload = (bundle.get("options_dashboard_state") or {}).get("alpha_os") or {}
    live_rows: list[dict[str, Any]] = []
    live_timestamp = _first_non_null(
        alpha_payload.get("timestamp"),
        (bundle.get("options_dashboard_state") or {}).get("timestamp"),
        (bundle.get("options_runtime_state") or {}).get("timestamp"),
    )

    strategy_posteriors = alpha_payload.get("strategy_posteriors") or []
    if isinstance(strategy_posteriors, list):
        for row in strategy_posteriors:
            if not isinstance(row, dict):
                continue
            live_rows.append(
                {
                    "timestamp": live_timestamp,
                    "mode": alpha_payload.get("mode"),
                    "strategy_name": row.get("strategy_name") or row.get("strategy"),
                    "posterior_mean": _safe_float(row.get("posterior_mean")),
                    "posterior_variance": _safe_float(row.get("posterior_variance")),
                    "credibility": _safe_float(row.get("credibility")),
                    "final_weight": _safe_float(row.get("final_weight") or row.get("weight")),
                }
            )

    if not live_rows:
        strategy_weights = _frame(bundle, "strategy_weights")
        if not strategy_weights.empty and live_timestamp is not None:
            for _, row in strategy_weights.iterrows():
                live_rows.append(
                    {
                        "timestamp": live_timestamp,
                        "mode": alpha_payload.get("mode"),
                        "strategy_name": row.get("strategy"),
                        "final_weight": _safe_float(row.get("weight")),
                    }
                )

    live = pd.DataFrame(live_rows)
    if not live.empty:
        live["timestamp"] = _coerce_datetime_series(live["timestamp"], normalize=False)
    return _concat_dedup_frames(
        [current, live],
        subset=["timestamp", "strategy_name"],
        sort_cols=["timestamp"],
    )


def _resolve_governor_budgets(bundle: dict[str, Any]) -> pd.DataFrame:
    state = bundle.get("state") or {}
    governor = (state.get("governor_state") or {}) if isinstance(state, dict) else {}
    current = _frame(bundle, "governor_budgets")
    if current.empty:
        current = pd.DataFrame(
            [
                {"bucket": "Equity", "fraction": governor.get("equity_fraction"), "budget_inr": governor.get("equity_budget_inr")},
                {"bucket": "Options", "fraction": governor.get("options_fraction"), "budget_inr": governor.get("options_budget_inr")},
                {"bucket": "Cash", "fraction": governor.get("cash_fraction"), "budget_inr": governor.get("cash_reserve_inr")},
            ]
        )

    performance_metrics = bundle.get("performance_metrics") or {}
    options_dashboard_state = bundle.get("options_dashboard_state") or {}
    options_runtime_state = bundle.get("options_runtime_state") or {}
    centralized = options_dashboard_state.get("centralized_pnl") or {}
    shadow_component = ((centralized.get("components") or {}).get("shadow_portfolio") or {})
    total_capital = _first_positive(
        governor.get("total_capital_inr"),
        performance_metrics.get("current_nav"),
        shadow_component.get("portfolio_value"),
        options_runtime_state.get("net_equity"),
        options_runtime_state.get("base_capital"),
    )

    working = current.copy()
    if "bucket" not in working.columns:
        working["bucket"] = ["Equity", "Options", "Cash"][: len(working)]
    working["fraction"] = pd.to_numeric(working.get("fraction"), errors="coerce")
    working["budget_inr"] = pd.to_numeric(working.get("budget_inr"), errors="coerce")
    if total_capital:
        missing_budget = working["budget_inr"].isna() | (working["budget_inr"].abs() < 1e-9)
        working.loc[missing_budget, "budget_inr"] = working.loc[missing_budget, "fraction"] * total_capital
    return working.dropna(subset=["bucket"]).reset_index(drop=True)


def _resolve_state_history(bundle: dict[str, Any]) -> pd.DataFrame:
    state_history = _frame(bundle, "state_history")
    if not state_history.empty:
        return state_history

    state = bundle.get("state") or {}
    governor = (state.get("governor_state") or {}) if isinstance(state, dict) else {}
    alpha_os = (state.get("alpha_os") or {}) if isinstance(state, dict) else {}
    timestamp = _first_non_null(
        governor.get("last_updated"),
        governor.get("last_morning_decision"),
        (bundle.get("options_dashboard_state") or {}).get("timestamp"),
        (bundle.get("options_runtime_state") or {}).get("timestamp"),
        (state.get("market") or {}).get("last_updated") if isinstance(state, dict) else None,
    )
    as_of = _safe_datetime(timestamp)
    if as_of is None:
        return pd.DataFrame()

    governor_budgets = _frame(bundle, "governor_budgets")
    budget_lookup = (
        governor_budgets.set_index("bucket")["budget_inr"].to_dict()
        if not governor_budgets.empty and {"bucket", "budget_inr"}.issubset(governor_budgets.columns)
        else {}
    )
    strategy_weights = _frame(bundle, "strategy_weights")
    active_strategy_count = int((pd.to_numeric(strategy_weights.get("weight"), errors="coerce").abs() > 1e-9).sum()) if not strategy_weights.empty else 0
    alpha_active = int(alpha_os.get("active_strategy_count") or 0)
    if alpha_active <= 0:
        alpha_active = active_strategy_count
    equity_budget = _first_positive(governor.get("equity_budget_inr"), budget_lookup.get("Equity")) or _safe_float(governor.get("equity_budget_inr")) or _safe_float(budget_lookup.get("Equity"))
    options_budget = _first_positive(governor.get("options_budget_inr"), budget_lookup.get("Options")) or _safe_float(governor.get("options_budget_inr")) or _safe_float(budget_lookup.get("Options"))
    cash_budget = _first_positive(governor.get("cash_reserve_inr"), budget_lookup.get("Cash")) or _safe_float(governor.get("cash_reserve_inr")) or _safe_float(budget_lookup.get("Cash"))

    return pd.DataFrame(
        [
            {
                "date": as_of,
                "timestamp": as_of,
                "governor_state_equity_fraction": _safe_float(governor.get("equity_fraction")),
                "governor_state_options_fraction": _safe_float(governor.get("options_fraction")),
                "governor_state_cash_fraction": _safe_float(governor.get("cash_fraction")),
                "governor_state_equity_budget_inr": equity_budget,
                "governor_state_options_budget_inr": options_budget,
                "governor_state_cash_reserve_inr": cash_budget,
                "alpha_os_active_strategy_count": alpha_active,
            }
        ]
    )


def _runtime_regime_bucket(label: Any) -> str:
    normalized = str(label or "").strip().lower()
    if not normalized or normalized in {"nan", "none"}:
        return "regime_low_vol"
    if "low_vol" in normalized or normalized in {"neutral", "range", "carry"}:
        return "regime_low_vol"
    if any(token in normalized for token in ["crisis", "panic", "tail", "shock", "meltdown"]):
        return "regime_crisis"
    if any(token in normalized for token in ["rising_vol", "falling_vol", "transition", "breakout", "whipsaw", "unstable"]):
        return "regime_transition"
    if any(token in normalized for token in ["high_vol", "volatile", "selloff", "risk_off", "event"]):
        return "regime_high_vol"
    return "regime_low_vol"


def _resolve_alpha_os_timeseries(bundle: dict[str, Any]) -> pd.DataFrame:
    alpha_os_timeseries = _frame(bundle, "alpha_os_timeseries")
    options_dashboard_state = bundle.get("options_dashboard_state") or {}
    options_runtime_state = bundle.get("options_runtime_state") or {}
    alpha_payload = options_dashboard_state.get("alpha_os") or {}
    strategy_weights = _frame(bundle, "strategy_weights")
    regime_history = _frame(bundle, "options_regime_history")

    if regime_history.empty:
        regime_history = pd.DataFrame(options_runtime_state.get("regime_history") or [])
    if not regime_history.empty:
        regime_history["timestamp"] = _coerce_datetime_series(regime_history["timestamp"], normalize=False)
        regime_history["regime_label"] = regime_history.get("routed_regime").combine_first(regime_history.get("regime"))
        regime_history["regime_bucket"] = regime_history["regime_label"].map(_runtime_regime_bucket)
        regime_history["confidence"] = pd.to_numeric(regime_history.get("confidence"), errors="coerce")

    portfolio_overlay = options_dashboard_state.get("portfolio_overlay") or options_runtime_state.get("portfolio_overlay") or {}
    portfolio_greeks = options_dashboard_state.get("portfolio_greeks") or {}
    portfolio_risk_usage = options_dashboard_state.get("portfolio_risk_usage") or {}
    concentration = _safe_float(portfolio_overlay.get("concentration"))
    gross_target = _safe_float(alpha_payload.get("gross_target")) or 0.0
    net_target = _safe_float(alpha_payload.get("net_target")) or 0.0
    gross_used = _first_positive(
        pd.to_numeric(strategy_weights.get("weight"), errors="coerce").abs().sum() if not strategy_weights.empty else None,
        portfolio_overlay.get("total_exposure"),
    ) or 0.0
    net_used = _safe_float(
        pd.to_numeric(strategy_weights.get("weight"), errors="coerce").sum() if not strategy_weights.empty else None
    )
    if net_used is None:
        net_used = _safe_float(portfolio_overlay.get("total_exposure")) or 0.0
    gamma_exposure = abs(_safe_float(portfolio_greeks.get("gamma")) or 0.0)
    gap_risk_score = _clip_unit_interval(portfolio_risk_usage.get("risk_pct")) or 0.0
    crowding_score = _clip_unit_interval(concentration) or 0.0
    mode = alpha_payload.get("mode") or options_runtime_state.get("current_mode") or "runtime_live"
    used_fallback = bool(alpha_payload.get("used_fallback"))
    fallback_level = alpha_payload.get("fallback_level")

    live_rows: list[dict[str, Any]] = []
    if not regime_history.empty:
        for timestamp, group in regime_history.dropna(subset=["timestamp"]).groupby("timestamp", dropna=False):
            counts = group["regime_bucket"].value_counts(normalize=True)
            probabilities = {bucket: float(counts.get(bucket, 0.0)) for bucket in ["regime_low_vol", "regime_high_vol", "regime_crisis", "regime_transition"]}
            entropy = -sum(probability * log(probability) for probability in probabilities.values() if probability > 0.0)
            dominant_regime = max(probabilities, key=probabilities.get)
            live_rows.append(
                {
                    "timestamp": timestamp,
                    "mode": mode,
                    "used_fallback": used_fallback,
                    "fallback_level": fallback_level,
                    "gross_target": gross_target,
                    "net_target": net_target,
                    "gross_cap": max(1.0, gross_target, gross_used),
                    "net_cap": max(1.0, abs(net_target), abs(net_used)),
                    "gross_used": gross_used,
                    "net_used": net_used,
                    "convexity_score": gamma_exposure,
                    "gap_risk_score": gap_risk_score,
                    "crowding_score": crowding_score,
                    "regime_low_vol": probabilities["regime_low_vol"],
                    "regime_high_vol": probabilities["regime_high_vol"],
                    "regime_crisis": probabilities["regime_crisis"],
                    "regime_transition": probabilities["regime_transition"],
                    "regime_confidence": float(pd.to_numeric(group.get("confidence"), errors="coerce").dropna().mean())
                    if "confidence" in group.columns and pd.to_numeric(group.get("confidence"), errors="coerce").dropna().empty is False
                    else None,
                    "regime_entropy": entropy,
                    "dominant_regime": dominant_regime.replace("regime_", "").upper(),
                    "weights_count_final": int((pd.to_numeric(strategy_weights.get("weight"), errors="coerce").abs() > 1e-9).sum()) if not strategy_weights.empty else 0,
                }
            )

    if not live_rows:
        live_timestamp = _first_non_null(
            alpha_payload.get("timestamp"),
            options_dashboard_state.get("timestamp"),
            options_runtime_state.get("timestamp"),
        )
        live_rows.append(
            {
                "timestamp": live_timestamp,
                "mode": mode,
                "used_fallback": used_fallback,
                "fallback_level": fallback_level,
                "gross_target": gross_target,
                "net_target": net_target,
                "gross_cap": max(1.0, gross_target, gross_used),
                "net_cap": max(1.0, abs(net_target), abs(net_used)),
                "gross_used": gross_used,
                "net_used": net_used,
                "convexity_score": gamma_exposure,
                "gap_risk_score": gap_risk_score,
                "crowding_score": crowding_score,
                "regime_low_vol": 1.0 if mode == "blocked_contract_violation" else 0.0,
                "regime_high_vol": 0.0,
                "regime_crisis": 0.0,
                "regime_transition": 0.0,
                "regime_confidence": None,
                "regime_entropy": 0.0,
                "dominant_regime": "UNKNOWN",
                "weights_count_final": int((pd.to_numeric(strategy_weights.get("weight"), errors="coerce").abs() > 1e-9).sum()) if not strategy_weights.empty else 0,
            }
        )

    live = pd.DataFrame(live_rows)
    if not live.empty:
        live["timestamp"] = _coerce_datetime_series(live["timestamp"], normalize=False)

    working = _concat_dedup_frames(
        [alpha_os_timeseries, live],
        subset=["timestamp"],
        sort_cols=["timestamp"],
    )
    if working.empty:
        return working
    prob_cols = [col for col in ["regime_low_vol", "regime_high_vol", "regime_crisis", "regime_transition"] if col in working.columns]
    if not prob_cols:
        return working.dropna(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
    numeric_probs = working[prob_cols].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    prob_sum = numeric_probs.sum(axis=1)
    gross_target_series = pd.to_numeric(working.get("gross_target"), errors="coerce").fillna(0.0)
    net_target_series = pd.to_numeric(working.get("net_target"), errors="coerce").fillna(0.0)
    gross_used_series = pd.to_numeric(working.get("gross_used"), errors="coerce").fillna(0.0)
    meaningful = (prob_sum > 0) | (gross_target_series.abs() > 1e-9) | (net_target_series.abs() > 1e-9) | (gross_used_series.abs() > 1e-9)
    if meaningful.any():
        working = working.loc[meaningful].copy()
    return working.dropna(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)


def _resolve_benchmark(bundle: dict[str, Any]) -> pd.DataFrame:
    benchmark = _frame(bundle, "benchmark")
    market_live_snapshot = bundle.get("market_live_snapshot") or {}
    nifty_snapshot = (market_live_snapshot.get("indices") or {}).get("NIFTY") or {}
    timestamp = _safe_datetime(market_live_snapshot.get("timestamp"))
    current_price = _safe_float(nifty_snapshot.get("current_price"))
    previous_close = _safe_float(nifty_snapshot.get("previous_close"))

    if timestamp and current_price and previous_close:
        latest = _latest_row(benchmark, "date")
        base_close = _safe_float(latest.get("close") if latest is not None else None)
        if base_close is not None and previous_close > 0:
            implied_close = base_close * (current_price / previous_close)
            live_row = pd.DataFrame(
                [
                    {
                        "date": timestamp,
                        "close": implied_close,
                    }
                ]
            )
            benchmark = _overlay_frame(benchmark, live_row, "date", normalize_daily=True)
            if not benchmark.empty and "close" in benchmark.columns:
                benchmark["close"] = pd.to_numeric(benchmark["close"], errors="coerce")
                benchmark = benchmark.sort_values("date").reset_index(drop=True)
                benchmark["daily_return"] = benchmark["close"].pct_change() * 100.0
                if benchmark["close"].notna().any():
                    first_close = benchmark["close"].dropna().iloc[0]
                    benchmark["cumulative_return"] = (benchmark["close"] / first_close - 1.0) * 100.0
    return benchmark


def _resolve_nav_history(bundle: dict[str, Any]) -> pd.DataFrame:
    current = _normalize_nav(_frame(bundle, "nav"))
    performance_metrics = bundle.get("performance_metrics") or {}
    options_dashboard_state = bundle.get("options_dashboard_state") or {}
    options_runtime_state = bundle.get("options_runtime_state") or {}
    pnl_state = ((bundle.get("state") or {}).get("pnl_state") or {}) if isinstance(bundle.get("state"), dict) else {}

    current_nav = _first_positive(
        performance_metrics.get("current_nav"),
        pnl_state.get("current_nav"),
        pnl_state.get("current_nav_inr"),
    )
    timestamp = _safe_datetime(
        _first_non_null(
            options_dashboard_state.get("timestamp"),
            options_runtime_state.get("timestamp"),
            pnl_state.get("last_updated"),
            performance_metrics.get("as_of"),
        )
    )
    if current_nav is None or timestamp is None:
        return current

    latest = _latest_row(current, "date")
    previous_nav = _safe_float(latest.get("nav") if latest is not None else None)
    overlay_row = dict(latest.to_dict()) if latest is not None else {}
    overlay_row["date"] = timestamp
    overlay_row["nav"] = current_nav
    if "nav_combined" in current.columns or "nav_combined" in overlay_row:
        overlay_row["nav_combined"] = current_nav

    nav_per_unit = _safe_float(overlay_row.get("nav_per_unit"))
    unit_count = None
    if previous_nav and nav_per_unit:
        unit_count = previous_nav / nav_per_unit
    if unit_count and unit_count > 0:
        overlay_row["nav_per_unit"] = current_nav / unit_count

    if previous_nav and previous_nav > 0:
        overlay_row["daily_return"] = current_nav / previous_nav - 1.0
    elif overlay_row.get("daily_return") is None:
        overlay_row["daily_return"] = 0.0

    high_water_mark = max(
        current_nav,
        _safe_float(overlay_row.get("high_water_mark")) or current_nav,
    )
    overlay_row["high_water_mark"] = high_water_mark
    overlay_row["drawdown"] = current_nav / high_water_mark - 1.0 if high_water_mark > 0 else 0.0
    prior_max_drawdown = _safe_float(overlay_row.get("max_drawdown_to_date"))
    if prior_max_drawdown is None:
        prior_max_drawdown = overlay_row["drawdown"]
    overlay_row["max_drawdown_to_date"] = min(prior_max_drawdown, overlay_row["drawdown"])

    overlay = pd.DataFrame([overlay_row])
    return _overlay_frame(current, overlay, "date", normalize_daily=True)


def _resolve_execution_quality(bundle: dict[str, Any]) -> pd.DataFrame:
    current = _frame(bundle, "execution_quality")
    options_dashboard_state = bundle.get("options_dashboard_state") or {}
    trade_metrics = options_dashboard_state.get("trade_metrics") or {}
    timestamp = _safe_datetime(options_dashboard_state.get("timestamp"))
    if timestamp is None:
        return current

    total_trades = _safe_float(trade_metrics.get("total_trades"))
    avg_slippage_bps = _safe_float(trade_metrics.get("avg_slippage_bps"))
    latest = _latest_row(current, "date")
    if avg_slippage_bps is None and total_trades == 0:
        avg_slippage_bps = _safe_float(latest.get("avg_slippage_bps") if latest is not None else 0.0) or 0.0
    if avg_slippage_bps is None:
        return current

    overlay = pd.DataFrame(
        [
            {
                "date": timestamp,
                "avg_slippage_bps": avg_slippage_bps,
                "trade_count": total_trades,
                "total_slippage_inr": _safe_float(trade_metrics.get("total_slippage_inr")),
                "implementation_shortfall_bps": _safe_float(trade_metrics.get("implementation_shortfall_bps")),
                "fill_rate": _safe_float(trade_metrics.get("fill_rate")),
                "partial_fills": _safe_float(trade_metrics.get("partial_fills")),
                "unfilled_count": _safe_float(trade_metrics.get("unfilled_count")),
            }
        ]
    )
    return _overlay_frame(current, overlay, "date", normalize_daily=False)


def _resolve_greeks_history(bundle: dict[str, Any]) -> pd.DataFrame:
    current = _frame(bundle, "greeks_history")
    dashboard_state = bundle.get("options_dashboard_state") or {}
    live_records = dashboard_state.get("greeks_history") or []
    live = pd.DataFrame(live_records)
    if not live.empty and "timestamp" in live.columns:
        live["timestamp"] = _coerce_datetime_series(live["timestamp"], normalize=False)
        for greek in ["delta", "gamma", "theta", "vega"]:
            if greek in live.columns:
                live[greek] = pd.to_numeric(live[greek], errors="coerce")
    return _concat_dedup_frames(
        [current, live],
        subset=["timestamp"],
        sort_cols=["timestamp"],
    )


def _normalize_option_type(value: Any) -> str | None:
    if value in [None, "", "nan", "None"]:
        return None
    normalized = str(value).strip().upper()
    mapping = {
        "CE": "C",
        "PE": "P",
        "CALL": "C",
        "PUT": "P",
        "CALL_OPTION": "C",
        "PUT_OPTION": "P",
    }
    return mapping.get(normalized, normalized[:1] if normalized else None)


def _normalize_options_chain_frame(df: pd.DataFrame, *, symbol_hint: str | None = None) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    working = df.copy()
    for column in ["timestamp", "date", "expiry"]:
        if column in working.columns:
            working[column] = pd.to_datetime(working[column], errors="coerce")
    if "symbol" not in working.columns and symbol_hint:
        working["symbol"] = symbol_hint
    if "symbol" in working.columns:
        working["symbol"] = working["symbol"].where(working["symbol"].notna(), symbol_hint).astype(str).str.upper()
    if "option_type" in working.columns:
        working["option_type"] = working["option_type"].map(_normalize_option_type)
    elif "instrument_type" in working.columns:
        working["option_type"] = working["instrument_type"].map(_normalize_option_type)
    if "date" not in working.columns:
        if "timestamp" in working.columns:
            working["date"] = working["timestamp"]
        elif "expiry" in working.columns:
            working["date"] = working["expiry"]
    if "underlying_price" not in working.columns:
        for source in ["spot_price", "underlying_spot", "underlying_ltp", "underlying_value"]:
            if source in working.columns:
                working["underlying_price"] = pd.to_numeric(working[source], errors="coerce")
                break
    if "moneyness" not in working.columns and {"strike", "underlying_price"}.issubset(working.columns):
        strike = pd.to_numeric(working["strike"], errors="coerce")
        underlying_price = pd.to_numeric(working["underlying_price"], errors="coerce")
        working["moneyness"] = strike / underlying_price.replace({0: pd.NA})
    return working


def _path_snapshot_timestamp(path) -> datetime:
    stem_parts = path.stem.rsplit("_", 2)
    if len(stem_parts) == 3:
        date_token = stem_parts[-2]
        time_token = stem_parts[-1]
        if date_token.isdigit() and time_token.isdigit():
            try:
                return datetime.strptime(f"{date_token}{time_token}", "%Y%m%d%H%M%S")
            except ValueError:
                pass
    return datetime.fromtimestamp(path.stat().st_mtime)


def _load_latest_chain_cache(symbols: list[str]) -> pd.DataFrame:
    cache_dir = PROJECT_ROOT / "data/options/chains_cache"
    if not cache_dir.exists():
        return pd.DataFrame()
    frames: list[pd.DataFrame] = []
    for symbol in symbols:
        candidates = list(cache_dir.glob(f"{symbol}_*.parquet"))
        if not candidates:
            continue
        latest_path = max(candidates, key=_path_snapshot_timestamp)
        frame = _normalize_options_chain_frame(_read_parquet(latest_path), symbol_hint=symbol)
        if not frame.empty:
            frames.append(frame)
    return _concat_dedup_frames(
        frames,
        subset=["symbol", "expiry", "strike", "option_type"],
        sort_cols=["timestamp", "date", "expiry"],
    )


def _select_freshest_options_chain_source(*candidates: pd.DataFrame) -> pd.DataFrame:
    prepared = [_normalize_options_chain_frame(frame) for frame in candidates if isinstance(frame, pd.DataFrame) and not frame.empty]
    if not prepared:
        return pd.DataFrame()
    if all("symbol" in frame.columns for frame in prepared):
        symbol_frames: list[pd.DataFrame] = []
        symbols = sorted(
            {
                symbol
                for frame in prepared
                for symbol in frame["symbol"].dropna().astype(str).unique().tolist()
                if symbol
            }
        )
        for symbol in symbols:
            freshest_frame = pd.DataFrame()
            freshest_timestamp: datetime | None = None
            for frame in prepared:
                symbol_frame = frame[frame["symbol"].astype(str) == symbol].copy()
                if symbol_frame.empty:
                    continue
                timestamp = _frame_last_timestamp(symbol_frame, "timestamp", "date", "expiry")
                if freshest_timestamp is None or (timestamp is not None and timestamp > freshest_timestamp):
                    freshest_timestamp = timestamp
                    freshest_frame = symbol_frame
            if not freshest_frame.empty:
                symbol_frames.append(freshest_frame)
        if symbol_frames:
            return _concat_dedup_frames(
                symbol_frames,
                subset=["symbol", "expiry", "strike", "option_type"],
                sort_cols=["timestamp", "date", "expiry"],
            )
    freshest = max(prepared, key=lambda frame: _frame_last_timestamp(frame, "timestamp", "date", "expiry") or datetime.min)
    return freshest.copy()


def _resolve_risk_frame(bundle: dict[str, Any]) -> pd.DataFrame:
    current = _frame(bundle, "risk_frame")
    if not current.empty:
        row = current.iloc[-1]
        current_level = row.get("overall_risk_level")
        level_is_meaningful = str(current_level).strip().lower() not in {"", "0", "0.0", "none", "nan"}
        portfolio_exposure = _safe_float(row.get("portfolio_exposure"))
        if level_is_meaningful and portfolio_exposure not in [None, 0.0]:
            return current

    state = bundle.get("state") or {}
    risk = (state.get("risk") or {}) if isinstance(state, dict) else {}
    portfolio = (state.get("portfolio") or {}) if isinstance(state, dict) else {}
    market = (state.get("market") or {}) if isinstance(state, dict) else {}
    risk_live = risk if risk.get("last_updated") not in [None, ""] else {}
    portfolio_live = portfolio if portfolio.get("last_updated") not in [None, ""] else {}
    market_live = market if market.get("last_updated") not in [None, ""] else {}
    market_row = _latest_market_row(bundle)
    options_dashboard_state = bundle.get("options_dashboard_state") or {}
    options_runtime_state = bundle.get("options_runtime_state") or {}
    portfolio_overlay = options_dashboard_state.get("portfolio_overlay") or ((options_dashboard_state.get("options_cycle") or {}).get("portfolio_overlay") or {})
    portfolio_greeks = options_dashboard_state.get("portfolio_greeks") or {}
    portfolio_risk_usage = options_dashboard_state.get("portfolio_risk_usage") or {}
    weekly_risk_usage = options_dashboard_state.get("weekly_risk_usage") or {}

    system_stress = _first_non_null(
        risk_live.get("system_stress"),
        market_row.get("stress_score") if market_row is not None else None,
        market_live.get("market_stress"),
    )
    exposure_multiplier = _first_non_null(
        risk_live.get("exposure_multiplier"),
        market_row.get("exposure_multiplier") if market_row is not None else None,
        1.0,
    )
    allowed_exposure = _first_non_null(
        market_live.get("allowed_exposure"),
        market_row.get("allowed_exposure") if market_row is not None else None,
    )
    portfolio_exposure = _first_non_null(
        portfolio_live.get("total_exposure") if _safe_float(portfolio_live.get("total_exposure")) not in [None, 0.0] else None,
        portfolio_overlay.get("total_exposure"),
    )
    risk_pct = _first_non_null(
        portfolio_risk_usage.get("risk_pct"),
        (_safe_float(weekly_risk_usage.get("risk_used")) or 0.0) / (_safe_float(weekly_risk_usage.get("risk_limit")) or 1.0)
        if _safe_float(weekly_risk_usage.get("risk_limit")) not in [None, 0.0]
        else None,
    )
    status_label = str(risk_live.get("status", "")).replace("RiskStatus.", "").strip().upper()
    if not status_label:
        stress_value = _safe_float(system_stress) or 0.0
        risk_value = _safe_float(risk_pct) or 0.0
        if max(stress_value, risk_value) >= 0.7:
            status_label = "CRITICAL"
        elif max(stress_value, risk_value) >= 0.45:
            status_label = "HIGH"
        elif max(stress_value, risk_value) >= 0.2:
            status_label = "ELEVATED"
        else:
            status_label = "NORMAL"

    timestamp = _first_non_null(
        options_runtime_state.get("timestamp"),
        options_dashboard_state.get("timestamp"),
        (bundle.get("live_heartbeat") or {}).get("timestamp"),
        risk.get("last_updated"),
        portfolio_live.get("last_updated"),
        market_live.get("last_updated"),
        market_row.get("date") if market_row is not None else None,
    )
    return pd.DataFrame(
        [
            {
                "timestamp": timestamp,
                "overall_risk_level": status_label,
                "system_stress": system_stress,
                "exposure_multiplier": exposure_multiplier,
                "allowed_exposure": allowed_exposure,
                "portfolio_exposure": portfolio_exposure,
                "options_delta_exposure_inr": _first_non_null(risk_live.get("options_delta_exposure_inr"), portfolio_greeks.get("delta"), 0.0),
                "options_vega_exposure_inr": _first_non_null(risk_live.get("options_vega_exposure_inr"), portfolio_greeks.get("vega"), 0.0),
                "options_margin_utilization": _first_non_null(risk_live.get("options_margin_utilization"), risk_pct, 0.0),
                "options_max_loss_scenario": _first_non_null(
                    risk_live.get("options_max_loss_scenario"),
                    portfolio_risk_usage.get("total_risk"),
                    (_safe_float(options_runtime_state.get("risk_cap_value")) or 0.0) - (_safe_float(options_runtime_state.get("risk_remaining")) or 0.0),
                    0.0,
                ),
            }
        ]
    )


def _resolve_exposure_history(bundle: dict[str, Any]) -> pd.DataFrame:
    current = _frame(bundle, "exposure_history")
    state = bundle.get("state") or {}
    market = (state.get("market") or {}) if isinstance(state, dict) else {}
    portfolio = (state.get("portfolio") or {}) if isinstance(state, dict) else {}
    risk = (state.get("risk") or {}) if isinstance(state, dict) else {}
    market_row = _latest_market_row(bundle)
    options_dashboard_state = bundle.get("options_dashboard_state") or {}
    portfolio_overlay = options_dashboard_state.get("portfolio_overlay") or {}
    timestamp = _safe_datetime(
        _first_non_null(
            portfolio_overlay.get("timestamp"),
            options_dashboard_state.get("timestamp"),
            market.get("last_updated"),
            risk.get("last_updated"),
            market_row.get("date") if market_row is not None else None,
        )
    )
    if timestamp is None:
        return current

    allowed_exposure = _first_non_null(
        market.get("allowed_exposure"),
        market_row.get("allowed_exposure") if market_row is not None else None,
    )
    actual_exposure = _first_non_null(
        portfolio.get("total_exposure"),
        portfolio_overlay.get("total_exposure"),
    )
    exposure_multiplier = _first_non_null(
        risk.get("exposure_multiplier"),
        market_row.get("exposure_multiplier") if market_row is not None else None,
        1.0,
    )
    overlay = pd.DataFrame(
        [
            {
                "date": timestamp,
                "allowed_exposure": _safe_float(allowed_exposure),
                "actual_exposure": _safe_float(actual_exposure),
                "risk_scaled_exposure": (_safe_float(actual_exposure) or 0.0) * (_safe_float(exposure_multiplier) or 1.0),
                "regime": _first_non_null(
                    market.get("regime"),
                    market_row.get("regime") if market_row is not None else None,
                ),
                "stress_score": _first_non_null(
                    risk.get("system_stress"),
                    market_row.get("stress_score") if market_row is not None else None,
                ),
            }
        ]
    )
    return _overlay_frame(current, overlay, "date", normalize_daily=True)


def _resolve_system_health(bundle: dict[str, Any]) -> dict[str, Any]:
    current = bundle.get("system_health") or {}
    current_score = _clip_unit_interval((current or {}).get("overall_health_score"))
    if current_score not in [None, 0.0] and str((current or {}).get("health_status", "")).lower() not in {"", "unknown"}:
        return current

    pipeline = _frame(bundle, "pipeline_freshness")
    market_row = _latest_market_row(bundle)
    scores: list[float] = []
    healthy_components = 0

    market_health = _clip_unit_interval(market_row.get("health_score") if market_row is not None else None)
    if market_health is not None:
        scores.append(market_health)

    if not pipeline.empty:
        for _, row in pipeline.iterrows():
            age_hours = _safe_float(row.get("age_hours"))
            score = 1.0 if _status_is_healthy(str(row.get("source")), str(row.get("status", "")), age_hours) else 0.0
            scores.append(score)
            healthy_components += int(score >= 1.0)

    overall_health_score = float(sum(scores) / len(scores)) if scores else 0.0
    if overall_health_score >= 0.8:
        health_status = "healthy"
    elif overall_health_score >= 0.55:
        health_status = "degraded"
    else:
        health_status = "critical"

    average_age = None
    if not pipeline.empty and "age_hours" in pipeline.columns:
        ages = pd.to_numeric(pipeline["age_hours"], errors="coerce").dropna()
        if not ages.empty:
            average_age = float(ages.mean())

    options_dashboard_state = bundle.get("options_dashboard_state") or {}
    portfolio_overlay = options_dashboard_state.get("portfolio_overlay") or {}
    return {
        "overall_health_score": overall_health_score,
        "health_status": health_status,
        "data_fresh": healthy_components >= max(1, len(scores) - 1),
        "data_freshness_hours": average_age or 0.0,
        "component_availability": float(healthy_components / len(scores)) if scores else 0.0,
        "components_healthy": healthy_components,
        "total_components": len(scores),
        "portfolio_active": (_safe_float(portfolio_overlay.get("total_exposure")) or 0.0) > 0.0,
        "intelligence_active": bool((bundle.get("sentiment_status") or {}).get("status") == "success"),
        "last_updated": max(
            [_safe_datetime(value) for value in [
                (bundle.get("live_heartbeat") or {}).get("timestamp"),
                (bundle.get("orchestrator_status") or {}).get("timestamp"),
                (bundle.get("sentiment_status") or {}).get("timestamp"),
                market_row.get("date") if market_row is not None else None,
            ] if _safe_datetime(value) is not None],
            default=datetime.now(),
        ).isoformat(),
    }


def _resolve_sentiment_section(bundle: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    section = deepcopy(current or {})
    if str(section.get("market_sentiment_regime", "")).upper() not in {"", "UNAVAILABLE"} and (_safe_float(section.get("regime_confidence")) or 0.0) > 0.0:
        return section

    sentiment_status = bundle.get("sentiment_status") or {}
    snapshot = sentiment_status.get("sentiment_snapshot") or {}
    market_sentiment = _frame(bundle, "market_sentiment")
    latest_market_sentiment = _latest_row(market_sentiment, "date")
    latest_ticker_sentiment = _frame(bundle, "latest_ticker_sentiment")
    latest_ticker_date = None
    coverage = 0
    if not latest_ticker_sentiment.empty and "date" in latest_ticker_sentiment.columns:
        latest_ticker_date = pd.to_datetime(latest_ticker_sentiment["date"], errors="coerce").max()
        if pd.notna(latest_ticker_date):
            coverage = int(
                latest_ticker_sentiment[
                    pd.to_datetime(latest_ticker_sentiment["date"], errors="coerce") == latest_ticker_date
                ]["ticker"].nunique()
            )

    market_row = _latest_market_row(bundle)
    polarity = _first_non_null(
        snapshot.get("polarity"),
        latest_market_sentiment.get("india_market_polarity") if latest_market_sentiment is not None else None,
        market_row.get("sentiment_polarity") if market_row is not None else None,
    )
    conviction = _first_non_null(
        snapshot.get("conviction"),
        latest_market_sentiment.get("india_market_conviction") if latest_market_sentiment is not None else None,
        market_row.get("sentiment_conviction") if market_row is not None else None,
    )
    uncertainty = _first_non_null(
        snapshot.get("uncertainty"),
        latest_market_sentiment.get("india_market_uncertainty") if latest_market_sentiment is not None else None,
        market_row.get("sentiment_uncertainty") if market_row is not None else None,
    )
    last_updated = _first_non_null(
        sentiment_status.get("timestamp"),
        sentiment_status.get("finished_at"),
        latest_market_sentiment.get("date") if latest_market_sentiment is not None else None,
        latest_ticker_date,
    )
    last_updated_dt = _safe_datetime(last_updated)
    is_fresh = bool(last_updated_dt and (datetime.now() - last_updated_dt).total_seconds() <= 6 * 3600)

    section.update(
        {
            "market_sentiment_regime": _derive_sentiment_regime(polarity, conviction),
            "sentiment_trend": snapshot.get("dominant_theme") or (market_row.get("sentiment_dominant_theme") if market_row is not None else section.get("sentiment_trend")) or "UNKNOWN",
            "market_sentiment_zscore": _safe_float(polarity) or 0.0,
            "regime_confidence": _safe_float(conviction) or 0.0,
            "sentiment_volatility": _safe_float(uncertainty),
            "last_updated": last_updated_dt.isoformat() if last_updated_dt else section.get("last_updated"),
            "pipeline_last_run": _first_non_null(sentiment_status.get("finished_at"), sentiment_status.get("started_at"), section.get("pipeline_last_run")),
            "is_fresh": is_fresh,
            "data_lag_days": max(0, (datetime.now().date() - last_updated_dt.date()).days) if last_updated_dt else section.get("data_lag_days", 0),
            "company_sentiment_available": coverage > 0,
            "companies_with_coverage": coverage,
            "sentiment_divergence": _safe_float(snapshot.get("delta_polarity")) or 0.0,
        }
    )
    return section


def _resolve_state_payload(bundle: dict[str, Any]) -> dict[str, Any]:
    canonical_state = deepcopy(bundle.get("canonical_state") or bundle.get("state") or {})
    market = canonical_state.setdefault("market", {})
    portfolio = canonical_state.setdefault("portfolio", {})
    risk = canonical_state.setdefault("risk", {})
    health = canonical_state.setdefault("health", {})
    governor = canonical_state.setdefault("governor_state", {})
    alpha_os = canonical_state.setdefault("alpha_os", {})
    pnl_state = canonical_state.setdefault("pnl_state", {})
    canonical_state["sentiment"] = _resolve_sentiment_section(bundle, canonical_state.get("sentiment") or {})

    market_row = _latest_market_row(bundle)
    if market_row is not None:
        market.setdefault("regime", market_row.get("regime"))
        market.setdefault("allowed_exposure", market_row.get("allowed_exposure"))
        market.setdefault("risk_on_probability", market_row.get("risk_on_probability"))
        market.setdefault("volatility_regime", market_row.get("volatility_regime"))
        market["last_updated"] = _first_non_null(market.get("last_updated"), market_row.get("date"))

    risk_frame = _frame(bundle, "risk_frame")
    if not risk_frame.empty:
        risk_row = risk_frame.iloc[-1]
        risk.update(
            {
                "overall_risk_level": risk_row.get("overall_risk_level"),
                "status": risk.get("status") if risk.get("status") not in [None, ""] else f"RiskStatus.{risk_row.get('overall_risk_level', 'UNKNOWN')}",
                "system_stress": risk_row.get("system_stress"),
                "exposure_multiplier": risk_row.get("exposure_multiplier"),
                "options_delta_exposure_inr": risk_row.get("options_delta_exposure_inr"),
                "options_vega_exposure_inr": risk_row.get("options_vega_exposure_inr"),
                "options_margin_utilization": risk_row.get("options_margin_utilization"),
                "options_max_loss_scenario": risk_row.get("options_max_loss_scenario"),
                "last_updated": risk_row.get("timestamp"),
            }
        )

    options_dashboard_state = bundle.get("options_dashboard_state") or {}
    options_runtime_state = bundle.get("options_runtime_state") or {}
    portfolio_overlay = options_dashboard_state.get("portfolio_overlay") or ((options_dashboard_state.get("options_cycle") or {}).get("portfolio_overlay") or {})
    portfolio_greeks = options_dashboard_state.get("portfolio_greeks") or {}
    active_positions = _frame(bundle, "active_option_positions")
    portfolio.update(
        {
            "total_exposure": _first_non_null(
                portfolio.get("total_exposure") if _safe_float(portfolio.get("total_exposure")) not in [None, 0.0] else None,
                portfolio_overlay.get("total_exposure"),
            ),
            "options_position_count": int(len(active_positions)) if not active_positions.empty else int(len(options_runtime_state.get("open_positions") or [])),
            "options_net_delta": _first_non_null(portfolio.get("options_net_delta"), portfolio_greeks.get("delta"), 0.0),
            "options_net_gamma": _first_non_null(portfolio.get("options_net_gamma"), portfolio_greeks.get("gamma"), 0.0),
            "options_net_theta": _first_non_null(portfolio.get("options_net_theta"), portfolio_greeks.get("theta"), 0.0),
            "options_net_vega": _first_non_null(portfolio.get("options_net_vega"), portfolio_greeks.get("vega"), 0.0),
            "options_unrealized_pnl": _first_non_null(portfolio.get("options_unrealized_pnl"), options_runtime_state.get("unrealized_pnl"), 0.0),
            "options_system_mode": _first_non_null(portfolio.get("options_system_mode"), options_runtime_state.get("current_mode"), "UNKNOWN"),
            "last_updated": _first_non_null(portfolio.get("last_updated"), options_dashboard_state.get("timestamp"), options_runtime_state.get("timestamp")),
        }
    )

    resolved_health = bundle.get("system_health") or {}
    health.update(resolved_health)

    governor_budgets = _frame(bundle, "governor_budgets")
    if not governor_budgets.empty and {"bucket", "budget_inr"}.issubset(governor_budgets.columns):
        budget_lookup = governor_budgets.set_index("bucket")["budget_inr"].to_dict()
        governor["equity_budget_inr"] = _first_positive(governor.get("equity_budget_inr"), budget_lookup.get("Equity")) or _safe_float(governor.get("equity_budget_inr")) or _safe_float(budget_lookup.get("Equity"))
        governor["options_budget_inr"] = _first_positive(governor.get("options_budget_inr"), budget_lookup.get("Options")) or _safe_float(governor.get("options_budget_inr")) or _safe_float(budget_lookup.get("Options"))
        governor["cash_reserve_inr"] = _first_positive(governor.get("cash_reserve_inr"), budget_lookup.get("Cash")) or _safe_float(governor.get("cash_reserve_inr")) or _safe_float(budget_lookup.get("Cash"))
        governor["total_capital_inr"] = _first_positive(
            governor.get("total_capital_inr"),
            sum(value for value in budget_lookup.values() if _safe_float(value) is not None),
        ) or _safe_float(governor.get("total_capital_inr")) or sum(value for value in budget_lookup.values() if _safe_float(value) is not None)

    strategy_weights = _frame(bundle, "strategy_weights")
    if not strategy_weights.empty:
        alpha_os["strategy_weights"] = {str(row["strategy"]): float(row["weight"]) for _, row in strategy_weights.iterrows()}
        alpha_os["active_strategy_count"] = int((pd.to_numeric(strategy_weights["weight"], errors="coerce").abs() > 1e-9).sum())
        latest_alpha = _latest_row(_frame(bundle, "alpha_os_timeseries"), "timestamp")
        alpha_os["last_updated"] = _first_non_null(
            alpha_os.get("last_updated"),
            latest_alpha.get("timestamp") if latest_alpha is not None else None,
            ((options_dashboard_state.get("alpha_os") or {}).get("timestamp")),
        )

    performance_metrics = bundle.get("performance_metrics") or {}
    execution_quality = _frame(bundle, "execution_quality")
    latest_execution = _latest_row(execution_quality, "date")
    pnl_state.update(
        {
            "current_nav_inr": _first_non_null(pnl_state.get("current_nav_inr"), performance_metrics.get("current_nav")),
            "current_nav": _first_non_null(pnl_state.get("current_nav"), performance_metrics.get("current_nav")),
            "nav_return_since_inception_pct": _first_non_null(pnl_state.get("nav_return_since_inception_pct"), performance_metrics.get("total_return")),
            "max_drawdown_to_date_pct": _first_non_null(pnl_state.get("max_drawdown_to_date_pct"), performance_metrics.get("max_drawdown")),
            "sharpe_ratio_30d": _first_non_null(pnl_state.get("sharpe_ratio_30d"), performance_metrics.get("sharpe_ratio")),
            "avg_slippage_bps_30d": _first_non_null(pnl_state.get("avg_slippage_bps_30d"), latest_execution.get("avg_slippage_bps") if latest_execution is not None else None, 0.0),
            "last_updated": _first_non_null(
                pnl_state.get("last_updated"),
                latest_execution.get("date") if latest_execution is not None else None,
                performance_metrics.get("as_of"),
            ),
        }
    )
    return canonical_state


@st.cache_data(ttl=300, show_spinner=False)
def load_static_data() -> dict[str, Any]:
    contract = DashboardDataContract()
    hub = V3DataHub(project_root=PROJECT_ROOT)

    state = contract._load_state_payload(force=True) or {}
    nav = _normalize_nav(_read_parquet(PROJECT_ROOT / "data/pnl/nav_history.parquet"))
    ledger = _ensure_datetime(_read_parquet(PROJECT_ROOT / "data/pnl/master_ledger.parquet"), "trade_date", "settlement_date", "recorded_at")
    if not ledger.empty:
        if "trade_date" in ledger.columns:
            ledger["date"] = ledger["trade_date"]
        elif "recorded_at" in ledger.columns:
            ledger["date"] = ledger["recorded_at"]

    execution_quality = _ensure_datetime(_read_parquet(PROJECT_ROOT / "data/pnl/execution_quality.parquet"), "date")
    reconciliation = _ensure_datetime(_read_parquet(PROJECT_ROOT / "data/pnl/reconciliation_log.parquet"), "date")
    shadow_pnl = _ensure_datetime(_read_parquet(PROJECT_ROOT / "data/processed/shadow_pnl_series.parquet"), "date", "timestamp")
    market_state = _ensure_datetime(_df_or_empty(hub.market_state()), "date", "Date", "timestamp")
    intelligent_market_state = _ensure_datetime(_df_or_empty(hub.intelligent_market_state()), "date", "Date")
    unified_daily = _normalize_unified_daily(_read_parquet(PROJECT_ROOT / "data/processed/unified_daily.parquet"))
    exposure_history = _ensure_datetime(_read_parquet(PROJECT_ROOT / "data/processed/exposure_history.parquet"), "date")
    unified_portfolio = _ensure_datetime(_read_parquet(PROJECT_ROOT / "data/processed/unified_portfolio.parquet"), "Date", "date", "allocation_timestamp")
    if "allocation_timestamp" in unified_portfolio.columns and "date" not in unified_portfolio.columns:
        unified_portfolio["date"] = unified_portfolio["allocation_timestamp"]
    portfolio_weights = _enrich_portfolio_weights(_df_or_empty(hub.portfolio_weights()), unified_portfolio)
    allocation_history = _ensure_datetime(_read_parquet(PROJECT_ROOT / "data/processed/allocation_history.parquet"), "date", "timestamp")
    stock_roles = _read_parquet(PROJECT_ROOT / "data/processed/stock_roles.parquet")
    scores = _ensure_datetime(_read_parquet(PROJECT_ROOT / "data/processed/scores.parquet"), "date")
    strategy_performance = _normalize_strategy_performance(
        _ensure_datetime(_read_parquet(PROJECT_ROOT / "data/processed/strategy_performance.parquet"), "last_updated")
    )
    strategy_beliefs = _ensure_datetime(_read_parquet(PROJECT_ROOT / "data/processed/strategy_beliefs.parquet"), "timestamp")
    strategy_regret = _normalize_strategy_regret(
        _ensure_datetime(_read_parquet(PROJECT_ROOT / "data/processed/strategy_regret.parquet"), "last_updated", "date")
    )
    current_positions = _read_json(PROJECT_ROOT / "data/portfolio/current_positions.json")
    current_holdings = _ensure_datetime(
        _read_parquet(PROJECT_ROOT / "data/processed/current_holdings.parquet"),
        "date",
        "allocation_timestamp",
    )
    rebalance_trades = _ensure_datetime(
        _read_parquet(PROJECT_ROOT / "data/processed/rebalance_trades.parquet"),
        "timestamp_utc",
        "created_at",
    )
    options_trade_history = _ensure_datetime(
        _read_parquet(PROJECT_ROOT / "data/processed/options_trade_history.parquet"),
        "entry_time",
        "exit_time",
        "expiry",
    )
    portfolio_trade_blotter = _ensure_datetime(
        _read_parquet(PROJECT_ROOT / "data/processed/portfolio_trade_blotter.parquet"),
        "timestamp_utc",
        "created_at",
    )
    portfolio_sentiment_watchlist = _read_json(PROJECT_ROOT / "data/processed/portfolio_sentiment_watchlist.json")
    options_runtime_audit = _read_json(PROJECT_ROOT / "data/processed/options_runtime_audit.json")
    sector_flows = _ensure_datetime(_df_or_empty(hub.sector_flows()), "Date", "date")
    sector_rotation = _ensure_datetime(_read_parquet(PROJECT_ROOT / "data/processed/sector_rotation.parquet"), "Date", "date")
    market_sentiment, ticker_sentiment, daily_sentiment, latest_ticker_sentiment = _load_sentiment_frames()
    bulk_deals = _ensure_datetime(_read_parquet(PROJECT_ROOT / "data/processed/alternative/bulk_deals_nse_all.parquet"), "date")
    credit_ratings = _read_parquet(PROJECT_ROOT / "data/processed/alternative/credit_ratings_nse_all.parquet")
    promoter_pledge = _ensure_datetime(_read_csv(PROJECT_ROOT / "data/processed/alternative/promoter_pledge_all.csv"), "date")
    announcements = _ensure_datetime(_read_csv(PROJECT_ROOT / "data/processed/alternative/announcements_all.csv"), "date")
    screener_metadata = _read_csv(PROJECT_ROOT / "data/processed/screener_metadata.csv")
    shareholding = _ensure_datetime(_read_csv(PROJECT_ROOT / "data/processed/screener_shareholding.csv"), "availability_date")
    valuation = _ensure_datetime(_read_parquet(PROJECT_ROOT / "data/processed/valuation.parquet"), "date")
    valuation_families = _ensure_datetime(_read_parquet(PROJECT_ROOT / "data/processed/valuation_families.parquet"), "date")
    valuation_posterior = _ensure_datetime(_read_parquet(PROJECT_ROOT / "data/processed/valuation_posterior.parquet"), "date")
    valuation_engines = _ensure_datetime(_read_parquet(PROJECT_ROOT / "data/processed/valuation_engines.parquet"), "date")
    cohesive_alpha = _ensure_datetime(_read_parquet(PROJECT_ROOT / "data/processed/cohesive_alpha_feed.parquet"), "as_of")
    alpha_os_timeseries = _ensure_datetime(_read_parquet(PROJECT_ROOT / "data/processed/alpha_os_timeseries.parquet"), "timestamp")
    alpha_os_posteriors = _ensure_datetime(_read_parquet(PROJECT_ROOT / "data/processed/alpha_os_strategy_posteriors.parquet"), "timestamp")
    benchmark_contract = contract.get_benchmark_returns(lookback_days=2000).value
    if not isinstance(benchmark_contract, pd.DataFrame):
        benchmark_contract = pd.DataFrame()
    benchmark_contract = _ensure_datetime(benchmark_contract, "date")
    benchmark_native = _ensure_datetime(_read_parquet(PROJECT_ROOT / "data/benchmark_nifty50.parquet"), "date")
    benchmark = _overlay_frame(benchmark_contract, benchmark_native, "date", normalize_daily=True)
    system_execution_log = _read_json(PROJECT_ROOT / "data/processed/system_execution_log.json")
    component_status = _parse_component_status(system_execution_log)
    state_log = _parse_state_log(_read_jsonl(PROJECT_ROOT / "data/state/state_change_log.jsonl"))
    state_history = _normalize_state_history(_read_parquet(PROJECT_ROOT / "data/state/unified_state_history.parquet"))
    system_health = contract.get_system_health().value if contract.get_system_health().is_available else {}
    performance_metrics = contract.get_performance_metrics().value if contract.get_performance_metrics().is_available else {}
    regime_history = contract.get_regime_history(lookback_days=365).value
    if not isinstance(regime_history, pd.DataFrame):
        regime_history = pd.DataFrame()

    return {
        "state": state,
        "nav": nav,
        "ledger": ledger,
        "execution_quality": execution_quality,
        "reconciliation": reconciliation,
        "shadow_pnl": shadow_pnl,
        "market_state": market_state,
        "intelligent_market_state": intelligent_market_state,
        "unified_daily": unified_daily,
        "exposure_history": exposure_history,
        "portfolio_weights": portfolio_weights,
        "unified_portfolio": unified_portfolio,
        "allocation_history": allocation_history,
        "stock_roles": stock_roles,
        "scores": scores,
        "strategy_performance": strategy_performance,
        "strategy_beliefs": strategy_beliefs,
        "strategy_regret": strategy_regret,
        "current_positions": current_positions,
        "current_holdings": current_holdings,
        "rebalance_trades": rebalance_trades,
        "options_trade_history": options_trade_history,
        "portfolio_trade_blotter": portfolio_trade_blotter,
        "portfolio_sentiment_watchlist": portfolio_sentiment_watchlist,
        "options_runtime_audit": options_runtime_audit,
        "sector_flows": sector_flows,
        "sector_rotation": sector_rotation,
        "market_sentiment": market_sentiment,
        "ticker_sentiment": ticker_sentiment,
        "daily_sentiment": daily_sentiment,
        "latest_ticker_sentiment": latest_ticker_sentiment,
        "bulk_deals": bulk_deals,
        "credit_ratings": credit_ratings,
        "promoter_pledge": promoter_pledge,
        "announcements": announcements,
        "screener_metadata": screener_metadata,
        "shareholding": shareholding,
        "valuation": valuation,
        "valuation_families": valuation_families,
        "valuation_posterior": valuation_posterior,
        "valuation_engines": valuation_engines,
        "cohesive_alpha": cohesive_alpha,
        "alpha_os_timeseries": alpha_os_timeseries,
        "alpha_os_posteriors": alpha_os_posteriors,
        "benchmark": benchmark,
        "system_execution_log": system_execution_log,
        "component_status": component_status,
        "state_log": state_log,
        "state_history": state_history,
        "system_health": system_health,
        "performance_metrics": performance_metrics,
        "strategy_weights": _parse_strategy_weights(state),
        "governor_budgets": _parse_governor_budgets(state),
        "regime_history": regime_history,
        "_loaded_static_at": datetime.now().isoformat(),
    }


@st.cache_data(ttl=300, show_spinner=False)
def load_intraday_market_sentiment_data() -> dict[str, Any]:
    hub = V3DataHub(project_root=PROJECT_ROOT)
    market_state = _ensure_datetime(_df_or_empty(hub.market_state()), "date", "Date", "timestamp")
    intelligent_market_state = _ensure_datetime(_df_or_empty(hub.intelligent_market_state()), "date", "Date")
    market_sentiment, ticker_sentiment, daily_sentiment, latest_ticker_sentiment = _load_sentiment_frames()
    market_refresh_status = _read_json(PROJECT_ROOT / "data/processed/market_refresh_status.json")
    sentiment_status = _read_json(PROJECT_ROOT / "data/sentiment/v3/sentiment_loop_status.json")
    market_live_snapshot = _read_json(PROJECT_ROOT / "data/options/live/market_data_latest.json")
    return {
        "market_state": market_state,
        "intelligent_market_state": intelligent_market_state,
        "market_sentiment": market_sentiment,
        "ticker_sentiment": ticker_sentiment,
        "daily_sentiment": daily_sentiment,
        "latest_ticker_sentiment": latest_ticker_sentiment,
        "market_refresh_status": market_refresh_status,
        "sentiment_status": sentiment_status,
        "market_live_snapshot": market_live_snapshot,
        "_loaded_intraday_market_sentiment_at": datetime.now().isoformat(),
    }


@st.cache_data(ttl=300, show_spinner=False)
def load_live_options_data() -> dict[str, Any]:
    options_chain_primary = _normalize_options_chain_frame(
        _read_parquet(PROJECT_ROOT / "data/options/live/nifty_options_latest.parquet"),
        symbol_hint="NIFTY",
    )
    options_chain_fallback = _normalize_options_chain_frame(
        _read_parquet(PROJECT_ROOT / "data/options/live_option_chain.parquet"),
        symbol_hint="NIFTY",
    )
    options_chain_cache = _load_latest_chain_cache(["NIFTY", "BANKNIFTY"])
    options_chain = _select_freshest_options_chain_source(
        options_chain_primary,
        options_chain_fallback,
        options_chain_cache,
    )
    options_governance = _ensure_datetime(_read_parquet(PROJECT_ROOT / "data/options/live/governance_events.parquet"), "timestamp", "resolved_at")
    options_runtime_state = _read_json(PROJECT_ROOT / "data/options/live/options_runtime_state.json")
    options_dashboard_state = _read_json(PROJECT_ROOT / "data/options/live/options_dashboard_state.json")
    active_option_positions = _parse_options_active_positions(options_dashboard_state)
    if active_option_positions.empty:
        active_option_positions = _parse_options_active_positions(options_runtime_state)
    option_iv_history = _concat_dedup_frames(
        [
            _parse_options_iv_history(options_runtime_state),
            _ensure_datetime(_read_parquet(PROJECT_ROOT / "data/options/iv_history.parquet"), "timestamp"),
        ],
        subset=["timestamp", "underlying"],
        sort_cols=["timestamp"],
    )
    options_regime_history = _ensure_datetime(_read_parquet(PROJECT_ROOT / "data/options/regime_history.parquet"), "timestamp")
    volatility_state = _read_parquet(PROJECT_ROOT / "data/processed/volatility_state.parquet")
    return {
        "options_chain": options_chain,
        "options_governance": options_governance,
        "options_runtime_state": options_runtime_state,
        "options_dashboard_state": options_dashboard_state,
        "active_option_positions": active_option_positions,
        "option_iv_history": option_iv_history,
        "options_regime_history": options_regime_history,
        "volatility_state": volatility_state,
        "_loaded_live_options_at": datetime.now().isoformat(),
    }


@st.cache_data(ttl=300, show_spinner=False)
def load_risk_runtime_data() -> dict[str, Any]:
    contract = DashboardDataContract()
    market_refresh_status = _read_json(PROJECT_ROOT / "data/processed/market_refresh_status.json")
    sentiment_status = _read_json(PROJECT_ROOT / "data/sentiment/v3/sentiment_loop_status.json")
    alternative_status = _read_json(PROJECT_ROOT / "data/processed/alternative/alternative_pipeline_status.json")
    orchestrator_status = _read_json(PROJECT_ROOT / "data/options/live/trading_day_orchestrator_status.json")
    live_heartbeat = _read_json(PROJECT_ROOT / "data/options/live/live_engine_heartbeat.json")
    options_runtime_state = _read_json(PROJECT_ROOT / "data/options/live/options_runtime_state.json")
    options_dashboard_state = _read_json(PROJECT_ROOT / "data/options/live/options_dashboard_state.json")
    greeks_history = contract.get_greeks_history(lookback_days=120).value
    if not isinstance(greeks_history, pd.DataFrame):
        greeks_history = pd.DataFrame()
    options_regime_history = _ensure_datetime(_read_parquet(PROJECT_ROOT / "data/options/regime_history.parquet"), "timestamp")
    risk_frame = contract.get_realtime_risk().value
    if not isinstance(risk_frame, pd.DataFrame):
        risk_frame = pd.DataFrame()
    system_health = contract.get_system_health().value if contract.get_system_health().is_available else {}
    return {
        "market_refresh_status": market_refresh_status,
        "sentiment_status": sentiment_status,
        "alternative_status": alternative_status,
        "orchestrator_status": orchestrator_status,
        "live_heartbeat": live_heartbeat,
        "options_runtime_state": options_runtime_state,
        "options_dashboard_state": options_dashboard_state,
        "active_option_positions": _parse_options_active_positions(options_dashboard_state)
        if options_dashboard_state
        else _parse_options_active_positions(options_runtime_state),
        "option_iv_history": _parse_options_iv_history(options_runtime_state),
        "options_regime_history": options_regime_history,
        "greeks_history": greeks_history,
        "risk_frame": risk_frame,
        "system_health": system_health,
        "_loaded_live_runtime_at": datetime.now().isoformat(),
    }


def compose_dashboard_bundle(
    static_bundle: dict[str, Any],
    intraday_bundle: dict[str, Any] | None = None,
    live_bundle: dict[str, Any] | None = None,
    runtime_bundle: dict[str, Any] | None = None,
) -> dict[str, Any]:
    bundle: dict[str, Any] = {}
    bundle.update(static_bundle or {})
    bundle.update(intraday_bundle or {})
    bundle.update(live_bundle or {})
    bundle.update(runtime_bundle or {})
    bundle["canonical_state"] = deepcopy(bundle.get("state") or {})
    bundle["unified_daily"] = _resolve_unified_daily(bundle)
    bundle["market_state_live"] = _frame(bundle, "market_state")
    bundle["market_state"] = _historical_market_state_from_unified_daily(bundle)
    bundle["regime_history"] = _resolve_regime_history(bundle)
    bundle["daily_sentiment"] = _resolve_daily_sentiment(bundle)
    bundle["nav"] = _resolve_nav_history(bundle)
    bundle["benchmark"] = _resolve_benchmark(bundle)
    bundle["execution_quality"] = _resolve_execution_quality(bundle)
    bundle["greeks_history"] = _resolve_greeks_history(bundle)
    bundle["strategy_weights"] = _resolve_strategy_weights(bundle)
    bundle["alpha_os_posteriors"] = _resolve_alpha_os_posteriors(bundle)
    bundle["alpha_os_timeseries"] = _resolve_alpha_os_timeseries(bundle)
    bundle["governor_budgets"] = _resolve_governor_budgets(bundle)
    bundle["state_history"] = _resolve_state_history(bundle)
    bundle["pipeline_freshness"] = _parse_pipeline_freshness(bundle)
    bundle["risk_frame"] = _resolve_risk_frame(bundle)
    bundle["system_health"] = _resolve_system_health(bundle)
    bundle["state"] = _resolve_state_payload(bundle)
    bundle["exposure_history"] = _resolve_exposure_history(bundle)
    return bundle


def _find_date_column(df: pd.DataFrame) -> str | None:
    for column in ["date", "Date", "timestamp", "trade_date", "availability_date", "last_updated", "recorded_at"]:
        if column in df.columns:
            return column
    return None


def _filter_frame_by_date(df: pd.DataFrame, filters: DashboardFilters) -> pd.DataFrame:
    if df.empty or (filters.start_date is None and filters.end_date is None):
        return df
    date_col = _find_date_column(df)
    if not date_col:
        return df
    working = df.copy()
    series = pd.to_datetime(working[date_col], errors="coerce")
    # Cross-sectional snapshots (valuation, engines, scores…) carry a single
    # as-of stamp, not a time series — date-filtering them just erases the
    # whole surface whenever the stamp falls outside the selected window.
    if series.dt.normalize().nunique(dropna=True) <= 1:
        return df
    mask = pd.Series(True, index=working.index)
    if filters.start_date is not None:
        mask &= series.dt.date >= filters.start_date
    if filters.end_date is not None:
        mask &= series.dt.date <= filters.end_date
    return working.loc[mask].copy()


def _apply_regime_filter(df: pd.DataFrame, filters: DashboardFilters) -> pd.DataFrame:
    if df.empty or not filters.regimes:
        return df
    for column in ["regime", "market_regime", "regime_name", "regime_current_regime", "volatility_regime"]:
        if column in df.columns:
            return df[df[column].astype(str).isin(filters.regimes)].copy()
    return df


def _apply_strategy_filter(df: pd.DataFrame, filters: DashboardFilters) -> pd.DataFrame:
    if df.empty or not filters.strategies:
        return df
    for column in ["strategy_name", "strategy"]:
        if column in df.columns:
            return df[df[column].astype(str).isin(filters.strategies)].copy()
    return df


def _apply_asset_class_filter(bundle: dict[str, Any], filters: DashboardFilters) -> dict[str, Any]:
    if not filters.asset_classes:
        return bundle
    allowed = set(filters.asset_classes)
    working = dict(bundle)
    if "Equity" not in allowed:
        for key in ["portfolio_weights", "unified_portfolio", "shadow_pnl"]:
            working[key] = pd.DataFrame()
    if "Options" not in allowed:
        for key in ["options_chain", "options_governance", "active_option_positions", "option_iv_history", "greeks_history", "risk_frame"]:
            working[key] = pd.DataFrame()
        working["options_runtime_state"] = {}
        working["options_dashboard_state"] = {}
    if "Sentiment" not in allowed:
        for key in ["market_sentiment", "ticker_sentiment", "daily_sentiment", "latest_ticker_sentiment"]:
            working[key] = pd.DataFrame()
    if "Alternatives" not in allowed:
        for key in ["bulk_deals", "credit_ratings", "promoter_pledge", "announcements", "shareholding"]:
            working[key] = pd.DataFrame()
    if "Macro" not in allowed:
        for key in ["market_state", "regime_history", "unified_daily", "exposure_history", "sector_flows", "sector_rotation"]:
            working[key] = pd.DataFrame()
    if "Research" not in allowed:
        for key in ["valuation", "valuation_families", "valuation_posterior", "valuation_engines", "cohesive_alpha", "scores"]:
            working[key] = pd.DataFrame()
    if "Alpha OS" not in allowed:
        for key in ["alpha_os_timeseries", "alpha_os_posteriors", "strategy_beliefs", "strategy_regret", "strategy_performance", "strategy_weights"]:
            working[key] = pd.DataFrame()
    return working


def apply_dashboard_filters(bundle: dict[str, Any], filters: DashboardFilters) -> dict[str, Any]:
    filtered: dict[str, Any] = {}
    for key, value in bundle.items():
        if isinstance(value, pd.DataFrame):
            if key in {"options_chain", "active_option_positions", "option_iv_history", "risk_frame"}:
                filtered[key] = value.copy()
            else:
                frame = _filter_frame_by_date(value, filters)
                frame = _apply_regime_filter(frame, filters)
                frame = _apply_strategy_filter(frame, filters)
                filtered[key] = frame
        else:
            filtered[key] = value

    if filters.strategies and isinstance(filtered.get("allocation_history"), pd.DataFrame):
        allocation_history = filtered["allocation_history"].copy()
        meta_cols = {
            "date",
            "regime",
            "timestamp",
            "regime_name",
            "regime_stability",
            "exposure_cap",
            "total_exposure",
            "freeze_active",
            "cash",
            "momentum",
            "quality",
            "value",
        }
        strategy_cols = [col for col in allocation_history.columns if col in filters.strategies]
        if strategy_cols:
            filtered["allocation_history"] = allocation_history[[col for col in allocation_history.columns if col in meta_cols or col in strategy_cols]].copy()

    return _apply_asset_class_filter(filtered, filters)
