#!/usr/bin/env python3
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Optional

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from src.dashboard.data_contract import DashboardDataContract
from src.dashboard.v3_data_hub import V3DataHub

PROJECT_ROOT = Path(__file__).resolve().parents[2]

THEME = {
    "bg": "#07111f",
    "panel": "#0f1b2d",
    "panel_alt": "#102339",
    "grid": "rgba(148, 163, 184, 0.14)",
    "text": "#e2e8f0",
    "muted": "#94a3b8",
    "blue": "#38bdf8",
    "green": "#34d399",
    "amber": "#f59e0b",
    "red": "#f87171",
    "cyan": "#22d3ee",
    "teal": "#14b8a6",
}

SECTION_ORDER = [
    "Executive Overview",
    "Performance & P&L",
    "Market & Regime",
    "Sentiment & Alternative Data",
    "Portfolio & Governor",
    "Options & Risk",
    "Valuation & Research",
    "Alpha OS & Operations",
]


@dataclass(frozen=True)
class VisualSpec:
    visual_id: str
    section: str
    title: str
    description: str
    builder: Callable[[dict[str, Any]], Optional[go.Figure]]


def _inject_styles() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=IBM+Plex+Sans:wght@400;500;600&display=swap');
        html, body, [class*="css"]  {
            font-family: "IBM Plex Sans", sans-serif;
        }
        h1, h2, h3, h4, h5 {
            font-family: "Space Grotesk", sans-serif;
            letter-spacing: -0.02em;
        }
        .stApp {
            background:
                radial-gradient(circle at top right, rgba(34, 211, 238, 0.10), transparent 28%),
                radial-gradient(circle at top left, rgba(20, 184, 166, 0.10), transparent 24%),
                linear-gradient(180deg, #07111f 0%, #08101b 100%);
        }
        .ns-hero {
            padding: 1.25rem 1.35rem;
            border-radius: 18px;
            border: 1px solid rgba(148, 163, 184, 0.18);
            background: linear-gradient(135deg, rgba(15, 27, 45, 0.95), rgba(10, 18, 31, 0.92));
            margin-bottom: 1rem;
        }
        .ns-pill {
            display: inline-block;
            padding: 0.28rem 0.65rem;
            border-radius: 999px;
            font-size: 0.78rem;
            border: 1px solid rgba(148, 163, 184, 0.18);
            color: #cbd5e1;
            margin-right: 0.4rem;
            margin-bottom: 0.35rem;
            background: rgba(15, 23, 42, 0.65);
        }
        .ns-card-title {
            font-family: "Space Grotesk", sans-serif;
            font-weight: 600;
            margin-bottom: 0.15rem;
        }
        .ns-card-subtitle {
            color: #94a3b8;
            font-size: 0.84rem;
            margin-bottom: 0.75rem;
        }
        .ns-section-note {
            color: #cbd5e1;
            padding: 0.6rem 0 0.2rem 0;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _read_json(path: str | Path) -> dict[str, Any]:
    file_path = Path(path)
    if not file_path.exists():
        return {}
    try:
        return json.loads(file_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    file_path = Path(path)
    if not file_path.exists():
        return []
    entries: list[dict[str, Any]] = []
    try:
        with file_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except Exception:
                    continue
                if isinstance(payload, dict):
                    entries.append(payload)
    except Exception:
        return []
    return entries


def _read_parquet(path: str | Path) -> pd.DataFrame:
    file_path = Path(path)
    if not file_path.exists():
        return pd.DataFrame()
    try:
        return pd.read_parquet(file_path)
    except Exception:
        return pd.DataFrame()


def _read_csv(path: str | Path) -> pd.DataFrame:
    file_path = Path(path)
    if not file_path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(file_path)
    except Exception:
        return pd.DataFrame()


def _safe_datetime(series: pd.Series) -> pd.Series:
    try:
        return pd.to_datetime(series, errors="coerce", format="mixed")
    except TypeError:
        return pd.to_datetime(series, errors="coerce")


def _ensure_datetime(df: pd.DataFrame, *cols: str) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    working = df.copy()
    for col in cols:
        if col in working.columns:
            working[col] = _safe_datetime(working[col])
    return working


def _latest_per_group(df: pd.DataFrame, group_col: str, date_col: str) -> pd.DataFrame:
    if df is None or df.empty or group_col not in df.columns or date_col not in df.columns:
        return pd.DataFrame()
    working = _ensure_datetime(df, date_col).dropna(subset=[group_col, date_col]).sort_values(date_col)
    if working.empty:
        return pd.DataFrame()
    idx = working.groupby(group_col)[date_col].idxmax()
    return working.loc[idx].reset_index(drop=True)


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


def _normalize_options_chain(df: pd.DataFrame, *, symbol_hint: str | None = None) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    working = _ensure_datetime(df, "timestamp", "date", "expiry")
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


def _frame_last_timestamp(df: pd.DataFrame, *cols: str) -> datetime | None:
    if df is None or df.empty:
        return None
    for column in cols:
        if column not in df.columns:
            continue
        parsed = _safe_datetime(df[column]).dropna()
        if not parsed.empty:
            return parsed.max().to_pydatetime()
    return None


def _path_snapshot_timestamp(path: Path) -> datetime:
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


def _load_latest_options_chain_cache(symbols: list[str]) -> pd.DataFrame:
    cache_dir = PROJECT_ROOT / "data/options/chains_cache"
    if not cache_dir.exists():
        return pd.DataFrame()
    frames: list[pd.DataFrame] = []
    for symbol in symbols:
        candidates = list(cache_dir.glob(f"{symbol}_*.parquet"))
        if not candidates:
            continue
        latest_path = max(candidates, key=_path_snapshot_timestamp)
        frame = _normalize_options_chain(_read_parquet(latest_path), symbol_hint=symbol)
        if not frame.empty:
            frames.append(frame)
    if not frames:
        return pd.DataFrame()
    combined = pd.concat(frames, ignore_index=True, sort=False)
    subset = [col for col in ["symbol", "expiry", "strike", "option_type"] if col in combined.columns]
    if subset:
        combined = combined.drop_duplicates(subset=subset, keep="last")
    return combined.sort_values([col for col in ["timestamp", "date", "expiry"] if col in combined.columns]).reset_index(drop=True)


def _select_freshest_options_chain(*candidates: pd.DataFrame) -> pd.DataFrame:
    prepared = [_normalize_options_chain(frame) for frame in candidates if isinstance(frame, pd.DataFrame) and not frame.empty]
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
            return pd.concat(symbol_frames, ignore_index=True, sort=False)
    return max(prepared, key=lambda frame: _frame_last_timestamp(frame, "timestamp", "date", "expiry") or datetime.min).copy()


def _normalize_nav(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    working = _ensure_datetime(df, "date", "timestamp", "as_of_date")
    if "nav" not in working.columns:
        for column in ["nav_combined", "current_nav", "nav_per_unit"]:
            if column in working.columns:
                working["nav"] = pd.to_numeric(working[column], errors="coerce")
                break
    if "date" not in working.columns:
        for column in ["timestamp", "as_of_date"]:
            if column in working.columns:
                working["date"] = working[column]
                break
    return working.dropna(subset=["date"]).sort_values("date")


def _normalize_state_history(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    working = _ensure_datetime(df, "timestamp")
    if "date" not in working.columns and "timestamp" in working.columns:
        working["date"] = working["timestamp"]
    return working.dropna(subset=["date"]).sort_values("date")


def _normalize_unified_daily(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    working = df.copy()
    if "Date" not in working.columns:
        working = working.reset_index()
    if "Date" in working.columns and "date" not in working.columns:
        working["date"] = pd.to_datetime(working["Date"], errors="coerce")
    return working.dropna(subset=["date"]).sort_values("date")


def _parse_strategy_weights(state: dict[str, Any]) -> pd.DataFrame:
    weights = (((state or {}).get("alpha_os") or {}).get("strategy_weights") or {})
    if not isinstance(weights, dict) or not weights:
        return pd.DataFrame(columns=["strategy", "weight"])
    return pd.DataFrame(
        [{"strategy": name, "weight": float(weight)} for name, weight in weights.items()]
    ).sort_values("weight", ascending=False)


def _parse_governor_budgets(state: dict[str, Any]) -> pd.DataFrame:
    governor = (state or {}).get("governor_state") or {}
    rows = [
        {"bucket": "Equity", "fraction": governor.get("equity_fraction"), "budget_inr": governor.get("equity_budget_inr")},
        {"bucket": "Options", "fraction": governor.get("options_fraction"), "budget_inr": governor.get("options_budget_inr")},
        {"bucket": "Cash", "fraction": governor.get("cash_fraction"), "budget_inr": governor.get("cash_reserve_inr")},
    ]
    df = pd.DataFrame(rows)
    return df.dropna(how="all")


def _parse_state_log(entries: list[dict[str, Any]]) -> pd.DataFrame:
    if not entries:
        return pd.DataFrame()
    df = pd.DataFrame(entries)
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    return df.dropna(subset=["timestamp"]) if "timestamp" in df.columns else df


def _parse_component_status(payload: dict[str, Any]) -> pd.DataFrame:
    component_status = payload.get("component_status") or {}
    if not isinstance(component_status, dict):
        return pd.DataFrame()
    rows = [{"component": component, "status": status} for component, status in component_status.items()]
    return pd.DataFrame(rows)


def _parse_options_active_positions(payload: dict[str, Any]) -> pd.DataFrame:
    positions = payload.get("active_positions") or payload.get("open_positions") or payload.get("positions") or []
    if not isinstance(positions, list):
        return pd.DataFrame()
    df = pd.DataFrame(positions)
    if df.empty:
        return pd.DataFrame()
    if "position_id" not in df.columns:
        if "symbol" in df.columns:
            df["position_id"] = df["symbol"].astype(str)
        elif "ticker" in df.columns:
            df["position_id"] = df["ticker"].astype(str)
        elif "underlying" in df.columns:
            df["position_id"] = df["underlying"].astype(str) + "_" + df.index.astype(str)
        else:
            df["position_id"] = df.index.astype(str)
    if "underlying" not in df.columns:
        for candidate in ["symbol", "ticker", "instrument", "instrument_key"]:
            if candidate in df.columns:
                df["underlying"] = df[candidate].astype(str).str.split("|").str[-1]
                break
    for greek in ["delta", "gamma", "theta", "vega"]:
        if greek in df.columns:
            df[greek] = pd.to_numeric(df[greek], errors="coerce")
    return df


def _parse_options_iv_history(payload: dict[str, Any]) -> pd.DataFrame:
    iv_history = payload.get("iv_history") or {}
    rows: list[dict[str, Any]] = []
    if not isinstance(iv_history, dict):
        return pd.DataFrame()
    for underlying, points in iv_history.items():
        if not isinstance(points, list):
            continue
        for point in points:
            if not isinstance(point, dict):
                continue
            rows.append(
                {
                    "underlying": underlying,
                    "timestamp": pd.to_datetime(point.get("timestamp"), errors="coerce"),
                    "iv": pd.to_numeric(point.get("iv"), errors="coerce"),
                }
            )
    df = pd.DataFrame(rows)
    return df.dropna(subset=["timestamp", "iv"]) if not df.empty else df


def _extract_nested(payload: dict[str, Any], path: str) -> Any:
    current: Any = payload
    for part in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _coalesce_timestamp(payload: dict[str, Any], *paths: str) -> Any:
    for path in paths:
        value = _extract_nested(payload, path)
        if value not in [None, "", "NaT"]:
            return value
    return None


def _winsorize_series(series: pd.Series, lower: float = 0.01, upper: float = 0.99) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    valid = numeric.dropna()
    if len(valid) < 20:
        return numeric
    low = valid.quantile(lower)
    high = valid.quantile(upper)
    return numeric.clip(lower=low, upper=high)


def _parse_pipeline_freshness(bundle: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    mappings = [
        ("Market", bundle.get("market_refresh_status") or {}, ("finished_at", "completed_at", "market_state.last_updated", "started_at")),
        ("Sentiment", bundle.get("sentiment_status") or {}, ("timestamp", "canonical_state.pipeline_last_run", "last_updated")),
        ("Alternative", bundle.get("alternative_status") or {}, ("finished_at", "state_sync.finished_at", "started_at")),
        ("Orchestrator", bundle.get("orchestrator_status") or {}, ("timestamp",)),
        ("Options Runtime", bundle.get("options_runtime_state") or {}, ("timestamp", "last_reconciled_at")),
        ("Heartbeat", bundle.get("live_heartbeat") or {}, ("timestamp",)),
        ("Alpha OS", (bundle.get("options_dashboard_state") or {}).get("alpha_os") or {}, ("timestamp",)),
    ]
    now = datetime.now()
    for name, payload, ts_keys in mappings:
        ts = pd.to_datetime(_coalesce_timestamp(payload, *ts_keys), errors="coerce")
        age_hours = None
        if not pd.isna(ts):
            age_hours = (now - ts.to_pydatetime().replace(tzinfo=None)).total_seconds() / 3600.0
        rows.append(
            {
                "source": name,
                "timestamp": ts,
                "age_hours": age_hours,
                "status": payload.get("pipeline_status")
                or payload.get("status")
                or payload.get("stage")
                or payload.get("current_mode")
                or payload.get("mode")
                or payload.get("health_status")
                or _extract_nested(payload, "collection.status")
                or _extract_nested(payload, "state_sync.pipeline_status"),
            }
        )
    return pd.DataFrame(rows)


def _load_bundle() -> dict[str, Any]:
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
    portfolio_weights = _df_or_empty(hub.portfolio_weights())
    unified_portfolio = _ensure_datetime(_read_parquet(PROJECT_ROOT / "data/processed/unified_portfolio.parquet"), "Date", "date", "allocation_timestamp")
    if "allocation_timestamp" in unified_portfolio.columns and "date" not in unified_portfolio.columns:
        unified_portfolio["date"] = unified_portfolio["allocation_timestamp"]
    allocation_history = _ensure_datetime(_read_parquet(PROJECT_ROOT / "data/processed/allocation_history.parquet"), "date", "timestamp")
    stock_roles = _read_parquet(PROJECT_ROOT / "data/processed/stock_roles.parquet")
    scores = _ensure_datetime(_read_parquet(PROJECT_ROOT / "data/processed/scores.parquet"), "date")
    strategy_performance = _ensure_datetime(_read_parquet(PROJECT_ROOT / "data/processed/strategy_performance.parquet"), "last_updated")
    strategy_beliefs = _ensure_datetime(_read_parquet(PROJECT_ROOT / "data/processed/strategy_beliefs.parquet"), "timestamp")
    strategy_regret = _ensure_datetime(_read_parquet(PROJECT_ROOT / "data/processed/strategy_regret.parquet"), "last_updated")
    sector_flows = _ensure_datetime(_df_or_empty(hub.sector_flows()), "Date", "date")
    sector_rotation = _ensure_datetime(_read_parquet(PROJECT_ROOT / "data/processed/sector_rotation.parquet"), "Date", "date")
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
        sentiment_fallback = daily_sentiment[["date", "sentiment_mean", "conviction_mean", "uncertainty_mean", "headline_count"]].copy()
        sentiment_fallback = sentiment_fallback.rename(
            columns={
                "sentiment_mean": "india_market_polarity",
                "conviction_mean": "india_market_conviction",
                "uncertainty_mean": "india_market_uncertainty",
                "headline_count": "news_volume_total",
            }
        )
        if market_sentiment.empty:
            market_sentiment = ticker_sentiment_fallback.copy() if not ticker_sentiment_fallback.empty else sentiment_fallback.copy()
        else:
            for fallback_df, suffix in [
                (ticker_sentiment_fallback, "__ticker_fallback"),
                (sentiment_fallback, "__fallback"),
            ]:
                if fallback_df.empty:
                    continue
                market_sentiment = market_sentiment.merge(
                    fallback_df,
                    on="date",
                    how="outer",
                    suffixes=("", suffix),
                )
            for column in [
                "india_market_polarity",
                "india_market_conviction",
                "india_market_uncertainty",
                "news_volume_total",
            ]:
                for fallback_col in [f"{column}__ticker_fallback", f"{column}__fallback"]:
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
    options_chain = _select_freshest_options_chain(
        _normalize_options_chain(
            _read_parquet(PROJECT_ROOT / "data/options/live/nifty_options_latest.parquet"),
            symbol_hint="NIFTY",
        ),
        _normalize_options_chain(
            _read_parquet(PROJECT_ROOT / "data/options/live_option_chain.parquet"),
            symbol_hint="NIFTY",
        ),
        _load_latest_options_chain_cache(["NIFTY", "BANKNIFTY"]),
    )
    options_governance = _ensure_datetime(_read_parquet(PROJECT_ROOT / "data/options/live/governance_events.parquet"), "timestamp", "resolved_at")
    options_runtime_state = _read_json(PROJECT_ROOT / "data/options/live/options_runtime_state.json")
    options_dashboard_state = _read_json(PROJECT_ROOT / "data/options/live/options_dashboard_state.json")
    active_option_positions = _parse_options_active_positions(options_dashboard_state)
    option_iv_history = _parse_options_iv_history(options_runtime_state)
    volatility_state = _read_parquet(PROJECT_ROOT / "data/processed/volatility_state.parquet")
    benchmark = contract.get_benchmark_returns(lookback_days=2000).value
    if not isinstance(benchmark, pd.DataFrame):
        benchmark = pd.DataFrame()
    benchmark = _ensure_datetime(benchmark, "date")
    system_execution_log = _read_json(PROJECT_ROOT / "data/processed/system_execution_log.json")
    component_status = _parse_component_status(system_execution_log)
    market_refresh_status = _read_json(PROJECT_ROOT / "data/processed/market_refresh_status.json")
    sentiment_status = _read_json(PROJECT_ROOT / "data/sentiment/v3/sentiment_loop_status.json")
    alternative_status = _read_json(PROJECT_ROOT / "data/processed/alternative/alternative_pipeline_status.json")
    orchestrator_status = _read_json(PROJECT_ROOT / "data/options/live/trading_day_orchestrator_status.json")
    live_heartbeat = _read_json(PROJECT_ROOT / "data/options/live/live_engine_heartbeat.json")
    state_log = _parse_state_log(_read_jsonl(PROJECT_ROOT / "data/state/state_change_log.jsonl"))
    state_history = _normalize_state_history(_read_parquet(PROJECT_ROOT / "data/state/unified_state_history.parquet"))
    system_health = contract.get_system_health().value if contract.get_system_health().is_available else {}
    performance_metrics = contract.get_performance_metrics().value if contract.get_performance_metrics().is_available else {}
    regime_history = contract.get_regime_history(lookback_days=365).value
    if not isinstance(regime_history, pd.DataFrame):
        regime_history = pd.DataFrame()
    greeks_history = contract.get_greeks_history(lookback_days=120).value
    if not isinstance(greeks_history, pd.DataFrame):
        greeks_history = pd.DataFrame()
    risk_frame = contract.get_realtime_risk().value
    if not isinstance(risk_frame, pd.DataFrame):
        risk_frame = pd.DataFrame()
    market_intelligence_view = contract.get_market_intelligence()
    market_intelligence = market_intelligence_view.value if market_intelligence_view.is_available else {}

    bundle = {
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
        "options_chain": options_chain,
        "options_governance": options_governance,
        "options_runtime_state": options_runtime_state,
        "options_dashboard_state": options_dashboard_state,
        "active_option_positions": active_option_positions,
        "option_iv_history": option_iv_history,
        "volatility_state": volatility_state,
        "benchmark": benchmark,
        "system_execution_log": system_execution_log,
        "component_status": component_status,
        "market_refresh_status": market_refresh_status,
        "sentiment_status": sentiment_status,
        "alternative_status": alternative_status,
        "orchestrator_status": orchestrator_status,
        "live_heartbeat": live_heartbeat,
        "state_log": state_log,
        "state_history": state_history,
        "system_health": system_health,
        "performance_metrics": performance_metrics,
        "strategy_weights": _parse_strategy_weights(state),
        "governor_budgets": _parse_governor_budgets(state),
        "regime_history": regime_history,
        "greeks_history": greeks_history,
        "risk_frame": risk_frame,
        "intelligence": market_intelligence,
    }
    bundle["pipeline_freshness"] = _parse_pipeline_freshness(bundle)
    return bundle


@st.cache_data(ttl=60, show_spinner=False)
def load_dashboard_bundle() -> dict[str, Any]:
    return _load_bundle()


def _apply_theme(fig: go.Figure, *, title: str, height: int = 360) -> go.Figure:
    fig.update_layout(
        title=title,
        template="plotly_dark",
        paper_bgcolor=THEME["panel"],
        plot_bgcolor=THEME["panel_alt"],
        font=dict(color=THEME["text"], size=12),
        title_font=dict(family="Space Grotesk", size=18, color=THEME["text"]),
        height=height,
        margin=dict(l=56, r=28, t=60, b=52),
        hovermode="x unified",
        uirevision=title,
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="left", x=0.0),
    )
    fig.update_xaxes(showgrid=True, gridcolor=THEME["grid"], zeroline=False, tickfont=dict(size=11))
    fig.update_yaxes(showgrid=True, gridcolor=THEME["grid"], zeroline=False, tickfont=dict(size=11))
    return fig


def _frame(bundle: dict[str, Any], key: str) -> pd.DataFrame:
    value = bundle.get(key)
    return value.copy() if isinstance(value, pd.DataFrame) else pd.DataFrame()


def _df_or_empty(value: Any) -> pd.DataFrame:
    return value.copy() if isinstance(value, pd.DataFrame) else pd.DataFrame()


def _line_figure(df: pd.DataFrame, x: str, y: str, title: str, *, color: str = THEME["blue"], area: bool = False) -> Optional[go.Figure]:
    if df.empty or x not in df.columns or y not in df.columns:
        return None
    working = df[[x, y]].copy()
    working[x] = pd.to_datetime(working[x], errors="coerce")
    working[y] = pd.to_numeric(working[y], errors="coerce")
    working = working.dropna().sort_values(x)
    if working[x].duplicated().any():
        working = working.groupby(x, dropna=False)[y].mean().reset_index()
    if working.empty:
        return None
    if area:
        fig = px.area(working, x=x, y=y, color_discrete_sequence=[color])
    else:
        fig = px.line(working, x=x, y=y, color_discrete_sequence=[color])
        fig.update_traces(line=dict(width=2.4), mode="lines+markers", marker=dict(size=4))
    dynamic_height = 420 if len(working) > 80 else 380
    return _apply_theme(fig, title=title, height=dynamic_height)


def _multi_line_figure(df: pd.DataFrame, x: str, y_cols: list[str], title: str) -> Optional[go.Figure]:
    if df.empty or x not in df.columns:
        return None
    available = [col for col in y_cols if col in df.columns]
    if not available:
        return None
    working = df[[x] + available].copy()
    working[x] = pd.to_datetime(working[x], errors="coerce")
    for col in available:
        working[col] = pd.to_numeric(working[col], errors="coerce")
    working = working.dropna(subset=[x]).sort_values(x)
    if working.empty:
        return None
    fig = px.line(working, x=x, y=available)
    fig.update_traces(line=dict(width=2.1))
    return _apply_theme(fig, title=title, height=430)


def _bar_figure(
    df: pd.DataFrame,
    x: str,
    y: str,
    title: str,
    *,
    orientation: str = "v",
    color: Optional[str] = None,
    top_n: Optional[int] = None,
    ascending: bool = False,
) -> Optional[go.Figure]:
    if df.empty or x not in df.columns or y not in df.columns:
        return None
    working = df[[x, y] + ([color] if color and color in df.columns else [])].copy()
    working[y] = pd.to_numeric(working[y], errors="coerce")
    working = working.dropna(subset=[x, y])
    if working.empty:
        return None
    working[x] = working[x].astype(str)
    auto_horizontal = (
        orientation == "v"
        and (
            working[x].str.len().max() > 18
            or working[x].str.contains(r"\s", regex=True).any()
            or len(working) > 12
        )
    )
    orientation_mode = "h" if auto_horizontal else orientation
    working = working.sort_values(y, ascending=ascending if orientation_mode == "v" else True)
    if top_n:
        if orientation_mode == "h":
            working = working.tail(top_n)
        else:
            working = working.head(top_n) if ascending else working.tail(top_n)
    if auto_horizontal:
        working[x] = working[x].map(lambda value: value if len(value) <= 42 else value[:39] + "...")
    marker_color = THEME["blue"]
    hover_text = None
    if color and color in working.columns:
        color_values = working[color].astype(str).fillna("unknown")
        palette = [
            THEME["blue"],
            THEME["cyan"],
            THEME["green"],
            THEME["amber"],
            THEME["red"],
            THEME["teal"],
        ]
        mapping = {label: palette[idx % len(palette)] for idx, label in enumerate(color_values.unique())}
        marker_color = [mapping[label] for label in color_values]
        hover_text = color_values
    if pd.to_numeric(working[y], errors="coerce").abs().sum() == 0:
        fig = go.Figure(
            go.Scatter(
                x=working[x] if orientation_mode == "v" else working[y],
                y=working[y] if orientation_mode == "v" else working[x],
                mode="markers+text",
                marker=dict(color=marker_color, size=10, symbol="diamond"),
                text=["0" for _ in range(len(working))],
                textposition="top center" if orientation_mode == "v" else "middle right",
                customdata=hover_text,
                hovertemplate="%{y}: %{x}<extra></extra>" if orientation_mode == "h" else "%{x}: %{y}<extra></extra>",
            )
        )
    else:
        fig = go.Figure(
            go.Bar(
                x=working[x] if orientation_mode == "v" else working[y],
                y=working[y] if orientation_mode == "v" else working[x],
                orientation=orientation_mode,
                marker_color=marker_color,
                customdata=hover_text,
                hovertemplate="%{y}: %{x}<extra></extra>" if orientation_mode == "h" else "%{x}: %{y}<extra></extra>",
            )
        )
    dynamic_height = 360
    if orientation_mode == "h":
        dynamic_height = min(820, max(380, 110 + 28 * len(working)))
    return _apply_theme(fig, title=title, height=dynamic_height)


def _histogram_figure(df: pd.DataFrame, column: str, title: str) -> Optional[go.Figure]:
    if df.empty or column not in df.columns:
        return None
    working = pd.to_numeric(df[column], errors="coerce").dropna()
    if working.empty:
        return None
    fig = px.histogram(working.to_frame(name=column), x=column, nbins=40, color_discrete_sequence=[THEME["cyan"]])
    return _apply_theme(fig, title=title, height=390)


def _scatter_figure(df: pd.DataFrame, x: str, y: str, title: str, *, color: Optional[str] = None, size: Optional[str] = None) -> Optional[go.Figure]:
    if df.empty or x not in df.columns or y not in df.columns:
        return None
    columns = [x, y]
    if color and color in df.columns:
        columns.append(color)
    size_col = size if size and size in df.columns else None
    if size_col:
        columns.append(size_col)
    # Carry a human-readable identifier so hovering a bubble names the company.
    id_col = next((c for c in ("Company Name", "company_name", "Company", "ticker", "symbol") if c in df.columns), None)
    if id_col and id_col not in columns:
        columns.append(id_col)
    working = df[columns].copy()
    if id_col:
        working["__label__"] = working[id_col].astype(str).str.replace(".NS", "", regex=False)
    working[x] = _winsorize_series(working[x])
    working[y] = _winsorize_series(working[y])
    size_plot_col = None
    if size_col and size_col in working.columns:
        working[size_col] = _winsorize_series(working[size_col])
        working[size_col] = pd.to_numeric(working[size_col], errors="coerce").replace([np.inf, -np.inf], np.nan)
        if working[size_col].notna().sum() == 0:
            working = working.drop(columns=[size_col])
            size_col = None
        else:
            size_plot_col = "__size_plot__"
            # Plotly marker sizes must be non-negative; use magnitude for sizing
            # while preserving the original signed value in hover data.
            working[size_plot_col] = working[size_col].abs()
            if (working[size_plot_col].fillna(0.0) > 0).sum() == 0:
                working = working.drop(columns=[size_col, size_plot_col])
                size_col = None
                size_plot_col = None
    working = working.dropna(subset=[x, y])
    if working.empty:
        return None
    if size_col and size_col in working.columns:
        working = working.dropna(subset=[size_col])
    if working.empty:
        return None
    color_col = None
    if color and color in working.columns:
        unique_colors = working[color].nunique(dropna=True)
        if pd.api.types.is_numeric_dtype(working[color]) and unique_colors > 3:
            color_col = color
        elif unique_colors <= 8:
            color_col = color
    hover_data = {}
    if color and color in working.columns and color_col is None:
        hover_data[color] = True
    if size_col and size_col in working.columns:
        hover_data[size_col] = ":.4f"
    has_label = "__label__" in working.columns
    fig = px.scatter(
        working,
        x=x,
        y=y,
        color=color_col if color_col in working.columns else None,
        size=size_plot_col if size_plot_col and size_plot_col in working.columns else None,
        hover_data=hover_data or None,
        hover_name="__label__" if has_label else None,
    )
    if size_plot_col:
        fig.update_traces(marker=dict(sizemode="area", sizemin=6))
    if "market_cap" in {x, y}:
        axis_name = "xaxis" if x == "market_cap" else "yaxis"
        fig.update_layout(**{axis_name: {"type": "log"}})
    return _apply_theme(fig, title=title, height=440)


def _box_figure(df: pd.DataFrame, x: str, y: str, title: str) -> Optional[go.Figure]:
    if df.empty or x not in df.columns or y not in df.columns:
        return None
    working = df[[x, y]].copy()
    working[y] = pd.to_numeric(working[y], errors="coerce")
    working = working.dropna(subset=[x, y])
    if working.empty:
        return None
    group_sizes = working.groupby(x).size()
    if len(group_sizes) > 12 or group_sizes.median() <= 1:
        grouped = working.groupby(x, dropna=False)[y].mean().reset_index().sort_values(y, ascending=False).head(15)
        return _bar_figure(grouped, x, y, title, orientation="h")
    fig = px.box(working, x=x, y=y, points="outliers", color=x)
    return _apply_theme(fig, title=title, height=440)


def _heatmap_figure(pivot: pd.DataFrame, title: str) -> Optional[go.Figure]:
    if pivot is None or pivot.empty:
        return None
    fig = px.imshow(pivot, aspect="auto", color_continuous_scale="Tealgrn")
    dynamic_height = min(900, max(440, 120 + 24 * len(pivot.index)))
    return _apply_theme(fig, title=title, height=dynamic_height)


def _donut_figure(df: pd.DataFrame, names: str, values: str, title: str) -> Optional[go.Figure]:
    if df.empty or names not in df.columns or values not in df.columns:
        return None
    working = df[[names, values]].copy()
    working[values] = pd.to_numeric(working[values], errors="coerce")
    working = working.dropna(subset=[names, values])
    if working.empty:
        return None
    fig = px.pie(working, names=names, values=values, hole=0.58)
    return _apply_theme(fig, title=title, height=400)


def _overview_nav_vs_benchmark(bundle: dict[str, Any]) -> Optional[go.Figure]:
    nav = _frame(bundle, "nav")
    benchmark = _frame(bundle, "benchmark")
    if nav.empty or benchmark.empty or "date" not in nav.columns or "date" not in benchmark.columns:
        return None
    left = nav[["date", "nav"]].copy().dropna()
    right = benchmark[["date", "close"]].copy().dropna()
    if left.empty or right.empty:
        return None
    left["date"] = pd.to_datetime(left["date"], errors="coerce")
    right["date"] = pd.to_datetime(right["date"], errors="coerce")
    left = left[left["date"].dt.dayofweek < 5].groupby("date", dropna=False)["nav"].last().reset_index()
    right = right[right["date"].dt.dayofweek < 5].groupby("date", dropna=False)["close"].last().reset_index()
    left["portfolio_index"] = left["nav"] / left["nav"].iloc[0] * 100.0
    right["benchmark_index"] = right["close"] / right["close"].iloc[0] * 100.0
    merged = left.merge(right[["date", "benchmark_index"]], on="date", how="inner")
    if merged.empty:
        return None
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=merged["date"], y=merged["portfolio_index"], mode="lines+markers", name="Portfolio", line=dict(width=2.6, color=THEME["blue"])))
    fig.add_trace(go.Scatter(x=merged["date"], y=merged["benchmark_index"], mode="lines", name="NIFTY 50", line=dict(width=2.2, color=THEME["amber"])))
    merged["excess_bps"] = (merged["portfolio_index"] - merged["benchmark_index"]) * 100.0
    fig.add_trace(go.Bar(x=merged["date"], y=merged["excess_bps"], name="Excess Return (bps)", marker_color="rgba(34,211,238,0.25)", yaxis="y2"))
    fig.update_layout(
        yaxis2=dict(overlaying="y", side="right", showgrid=False, title="Excess (bps)"),
    )
    return _apply_theme(fig, title="Portfolio vs NIFTY 50 (Indexed)")


def _overview_pnl_mix(bundle: dict[str, Any]) -> Optional[go.Figure]:
    pnl_state = (bundle.get("state") or {}).get("pnl_state") or {}
    equity = float(pnl_state.get("pnl_today_equity_inr", 0.0) or 0.0)
    options = float(pnl_state.get("pnl_today_options_inr", 0.0) or 0.0)
    net = float(pnl_state.get("net_pnl_today_inr", pnl_state.get("pnl_today_inr", 0.0)) or 0.0)
    if abs(equity) + abs(options) + abs(net) < 1e-9:
        fig = go.Figure(
            go.Indicator(
                mode="number",
                value=0.0,
                title={"text": "Today's P&L Mix<br><span style='font-size:0.8em;color:#94a3b8'>No realized move has been persisted yet today</span>"},
                number={"prefix": "₹", "valueformat": ",.0f"},
            )
        )
        return _apply_theme(fig, title="Today's P&L Mix", height=320)
    fig = go.Figure(
        go.Waterfall(
            x=["Equity", "Options", "Net"],
            y=[equity, options, net],
            measure=["relative", "relative", "total"],
            connector={"line": {"color": THEME["muted"]}},
        )
    )
    return _apply_theme(fig, title="Today's P&L Mix", height=360)


def _market_regime_timeline(bundle: dict[str, Any]) -> Optional[go.Figure]:
    df = _frame(bundle, "regime_history")
    if df.empty or "date" not in df.columns or "regime" not in df.columns:
        return None
    working = df[["date", "regime"]].dropna().sort_values("date")
    if working.empty:
        return None
    working["date"] = pd.to_datetime(working["date"], errors="coerce").dt.normalize()
    working = working.dropna(subset=["date"]).groupby("date", dropna=False)["regime"].last().reset_index()
    regime_codes = {regime: idx for idx, regime in enumerate(working["regime"].astype(str).unique(), start=1)}
    working["regime_code"] = working["regime"].astype(str).map(regime_codes)
    timeline = pd.DataFrame([working["regime_code"].tolist()], index=["Regime"], columns=working["date"].dt.strftime("%Y-%m-%d"))
    fig = px.imshow(timeline, aspect="auto", color_continuous_scale="Tealgrn")
    fig.update_yaxes(showticklabels=False)
    return _apply_theme(fig, title="Regime Timeline", height=260)


def _regime_transition_matrix(bundle: dict[str, Any]) -> Optional[go.Figure]:
    df = _frame(bundle, "regime_history")
    if df.empty or "regime" not in df.columns:
        return None
    working = df[["date", "regime"]].dropna().sort_values("date")
    if len(working) < 2:
        latest = str(working["regime"].iloc[-1]) if not working.empty else "unknown"
        fig = go.Figure(
            go.Indicator(
                mode="number",
                value=1,
                title={
                    "text": (
                        "Regime Transition Matrix<br>"
                        f"<span style='font-size:0.8em;color:#94a3b8'>Current regime: {latest}; "
                        "transition history has not accumulated yet</span>"
                    )
                },
                number={"suffix": " observed regime"},
            )
        )
        return _apply_theme(fig, title="Regime Transition Matrix", height=320)
    working["next_regime"] = working["regime"].shift(-1)
    matrix = pd.crosstab(working["regime"], working["next_regime"])
    if matrix.empty:
        return None
    return _heatmap_figure(matrix, "Regime Transition Matrix")


def _monthly_returns_heatmap(bundle: dict[str, Any]) -> Optional[go.Figure]:
    nav = _frame(bundle, "nav")
    if nav.empty or "date" not in nav.columns or "nav" not in nav.columns:
        return None
    working = nav[["date", "nav"]].copy().dropna()
    working["date"] = pd.to_datetime(working["date"], errors="coerce")
    working = working.dropna(subset=["date"]).sort_values("date")
    if len(working) < 20:
        return None
    monthly = working.set_index("date")["nav"].resample("ME").last().pct_change()
    if monthly.dropna().empty:
        return None
    monthly_df = monthly.reset_index(name="monthly_return")
    monthly_df["year"] = monthly_df["date"].dt.year
    monthly_df["month"] = monthly_df["date"].dt.strftime("%b")
    order = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    pivot = monthly_df.pivot(index="year", columns="month", values="monthly_return").reindex(columns=order)
    return _heatmap_figure(pivot * 100.0, "Monthly Returns Heatmap (%)")


def _ledger_pnl_by_book(bundle: dict[str, Any]) -> Optional[go.Figure]:
    ledger = _frame(bundle, "ledger")
    if ledger.empty or "book" not in ledger.columns or "net_pnl" not in ledger.columns:
        return None
    grouped = ledger.groupby("book", dropna=False)["net_pnl"].sum().reset_index()
    return _bar_figure(grouped, "book", "net_pnl", "Ledger Net P&L by Book")


def _ledger_pnl_by_strategy(bundle: dict[str, Any]) -> Optional[go.Figure]:
    ledger = _frame(bundle, "ledger")
    if ledger.empty or "strategy_id" not in ledger.columns or "net_pnl" not in ledger.columns:
        return None
    grouped = (
        ledger.dropna(subset=["strategy_id"])
        .groupby("strategy_id", dropna=False)["net_pnl"]
        .sum()
        .reset_index()
        .sort_values("net_pnl", ascending=False)
        .head(12)
    )
    return _bar_figure(grouped, "strategy_id", "net_pnl", "Ledger Net P&L by Strategy")


def _shadow_vs_nav(bundle: dict[str, Any]) -> Optional[go.Figure]:
    nav = _frame(bundle, "nav")
    shadow = _frame(bundle, "shadow_pnl")
    if nav.empty or shadow.empty:
        return None
    nav_df = nav[["date", "nav"]].copy().dropna()
    shadow_df = shadow.copy()
    if "portfolio_value" not in shadow_df.columns:
        return None
    if "date" not in shadow_df.columns and "timestamp" in shadow_df.columns:
        shadow_df["date"] = shadow_df["timestamp"]
    shadow_df = shadow_df[["date", "portfolio_value"]].copy().dropna()
    nav_df["date"] = pd.to_datetime(nav_df["date"], errors="coerce")
    shadow_df["date"] = pd.to_datetime(shadow_df["date"], errors="coerce")
    merged = nav_df.merge(shadow_df, on="date", how="outer").sort_values("date")
    if merged.empty:
        return None
    fig = px.line(merged, x="date", y=["nav", "portfolio_value"])
    return _apply_theme(fig, title="Canonical NAV vs Shadow Portfolio Value")


def _risk_on_vs_stress(bundle: dict[str, Any]) -> Optional[go.Figure]:
    df = _frame(bundle, "market_state")
    return _scatter_figure(df, "risk_on_probability", "stress_score", "Risk-On Probability vs Stress Score", color="regime")


def _volatility_regime_counts(bundle: dict[str, Any]) -> Optional[go.Figure]:
    df = _frame(bundle, "market_state")
    if df.empty or "volatility_regime" not in df.columns:
        return None
    grouped = df["volatility_regime"].astype(str).value_counts().reset_index()
    grouped.columns = ["volatility_regime", "count"]
    return _bar_figure(grouped, "volatility_regime", "count", "Volatility Regime Counts")


def _exposure_allowed_vs_actual(bundle: dict[str, Any]) -> Optional[go.Figure]:
    df = _frame(bundle, "exposure_history")
    if df.empty or "date" not in df.columns:
        return None
    cols = [col for col in ["allowed_exposure", "actual_exposure", "risk_scaled_exposure"] if col in df.columns]
    return _multi_line_figure(df, "date", cols, "Allowed vs Actual Exposure")


def _unified_macro_and_exposure(bundle: dict[str, Any]) -> Optional[go.Figure]:
    """MacroScore (a composite of growth/inflation/liquidity/stress
    contributions, roughly 0=worst to 2=best regime backdrop) and the equity-
    exposure ceiling it implies, on one shared timeline instead of two bare
    unlabeled line charts. The bottom panel makes the causal link explicit:
    exposure ceiling tracks the macro score with regime-dependent haircuts."""
    df = _frame(bundle, "unified_daily")
    if df.empty or "date" not in df.columns:
        return None
    cols = [c for c in ("MacroScore", "Max_Equity_Exposure") if c in df.columns]
    if len(cols) < 2:
        return None
    working = df[["date"] + cols].copy()
    for c in cols:
        working[c] = pd.to_numeric(working[c], errors="coerce")
    working = working.dropna(subset=["date"]).sort_values("date")
    if working.dropna(subset=cols, how="all").empty:
        return None
    last_valid = working.dropna(subset=cols, how="all")["date"].max()

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.55, 0.45],
                        vertical_spacing=0.08,
                        subplot_titles=("Macro Score (0 = worst backdrop, ~2 = best)",
                                        "Implied Max Equity Exposure Ceiling"))
    fig.add_trace(go.Scatter(x=working["date"], y=working["MacroScore"], mode="lines",
                             line=dict(color=THEME["green"], width=2), name="MacroScore",
                             showlegend=False), row=1, col=1)
    fig.add_hline(y=working["MacroScore"].median(), line=dict(color=THEME["grid"], width=1, dash="dot"),
                  row=1, col=1)
    fig.add_trace(go.Scatter(x=working["date"], y=working["Max_Equity_Exposure"], mode="lines",
                             fill="tozeroy", line=dict(color=THEME["amber"], width=2),
                             name="Max Equity Exposure", showlegend=False), row=2, col=1)
    fig.update_yaxes(range=[0, 1], tickformat=".0%", row=2, col=1)
    fig = _apply_theme(
        fig,
        title=f"Unified Daily Macro Score & Exposure Ceiling — last data point {last_valid:%d %b %Y}"
              + (" (this feed has not been refreshed since)" if (pd.Timestamp.now() - last_valid).days > 30 else ""),
        height=480,
    )
    return fig


def _latest_ticker_sentiment_chart(bundle: dict[str, Any], *, positive: bool) -> Optional[go.Figure]:
    df = _frame(bundle, "latest_ticker_sentiment")
    if df.empty or "sentiment_polarity" not in df.columns or "ticker" not in df.columns:
        return None
    working = df[["ticker", "sentiment_polarity"]].copy().dropna()
    working["sentiment_polarity"] = pd.to_numeric(working["sentiment_polarity"], errors="coerce")
    working = working.dropna().sort_values("sentiment_polarity", ascending=not positive).head(15)
    title = "Top Positive Ticker Sentiment" if positive else "Top Negative Ticker Sentiment"
    return _bar_figure(working, "ticker", "sentiment_polarity", title)


def _sentiment_source_coverage(bundle: dict[str, Any]) -> Optional[go.Figure]:
    df = _frame(bundle, "latest_ticker_sentiment")
    if df.empty or "source" not in df.columns:
        return None
    grouped = df["source"].astype(str).value_counts().reset_index()
    grouped.columns = ["source", "ticker_count"]
    return _bar_figure(grouped, "source", "ticker_count", "Ticker Sentiment Coverage by Source")


def _bulk_deal_daily_counts(bundle: dict[str, Any]) -> Optional[go.Figure]:
    df = _frame(bundle, "bulk_deals")
    if df.empty or "date" not in df.columns:
        return None
    working = df.copy()
    working["deal_count"] = 1
    grouped = working.groupby(working["date"].dt.date)["deal_count"].sum().reset_index()
    grouped["date"] = pd.to_datetime(grouped["date"], errors="coerce")
    return _line_figure(grouped, "date", "deal_count", "Bulk Deals Count by Day", color=THEME["amber"])


def _bulk_deal_top_symbols(bundle: dict[str, Any]) -> Optional[go.Figure]:
    df = _frame(bundle, "bulk_deals")
    if df.empty or "nse_ticker" not in df.columns or "quantity" not in df.columns:
        return None
    working = df[["nse_ticker", "quantity"]].copy()
    working["quantity"] = pd.to_numeric(working["quantity"], errors="coerce")
    grouped = working.groupby("nse_ticker")["quantity"].sum().reset_index().sort_values("quantity", ascending=False).head(15)
    return _bar_figure(grouped, "nse_ticker", "quantity", "Top NSE Bulk-Deal Names by Quantity")


def _announcement_categories(bundle: dict[str, Any]) -> Optional[go.Figure]:
    df = _frame(bundle, "announcements")
    if df.empty or "category" not in df.columns:
        return None
    grouped = df["category"].astype(str).value_counts().reset_index()
    grouped.columns = ["category", "announcement_count"]
    return _bar_figure(grouped, "category", "announcement_count", "Announcement Categories")


def _promoter_pledge_top(bundle: dict[str, Any]) -> Optional[go.Figure]:
    df = _frame(bundle, "promoter_pledge")
    if df.empty or "nse_ticker" not in df.columns or "pledge_pct" not in df.columns:
        return None
    working = _latest_per_group(df, "nse_ticker", "date")
    working["pledge_pct"] = pd.to_numeric(working["pledge_pct"], errors="coerce")
    working = working.dropna(subset=["pledge_pct"]).sort_values("pledge_pct", ascending=False).head(15)
    return _bar_figure(working, "nse_ticker", "pledge_pct", "Top Promoter Pledge Levels")


def _shareholding_mix(bundle: dict[str, Any]) -> Optional[go.Figure]:
    df = _frame(bundle, "shareholding")
    if df.empty or "ticker" not in df.columns or "availability_date" not in df.columns:
        return None
    latest = _latest_per_group(df, "ticker", "availability_date")
    if latest.empty:
        return None
    rows = []
    for owner in ["promoter_pct", "fii_pct", "dii_pct", "public_pct", "govt_pct"]:
        if owner in latest.columns:
            rows.append({"owner_group": owner.replace("_pct", "").upper(), "avg_pct": pd.to_numeric(latest[owner], errors="coerce").mean()})
    return _bar_figure(pd.DataFrame(rows), "owner_group", "avg_pct", "Average Ownership Mix Across Covered NSE Names")


def _weights_role_donut(bundle: dict[str, Any]) -> Optional[go.Figure]:
    df = _frame(bundle, "portfolio_weights")
    if df.empty or "position_role" not in df.columns:
        return None
    grouped = df.groupby("position_role")["weight"].sum().reset_index()
    return _donut_figure(grouped, "position_role", "weight", "Portfolio Weight by Role")


def _sector_exposure(bundle: dict[str, Any]) -> Optional[go.Figure]:
    df = _frame(bundle, "portfolio_weights")
    if df.empty or "Industry" not in df.columns:
        return None
    working = df.copy()
    working["Industry"] = working["Industry"].astype(str)
    if working["Industry"].nunique(dropna=True) > 1:
        working = working[working["Industry"].str.lower() != "unknown"]
    grouped = working.groupby("Industry", dropna=False)["weight"].sum().reset_index().sort_values("weight", ascending=False).head(15)
    return _bar_figure(grouped, "Industry", "weight", "Sector Exposure by Weight")


def _mispricing_vs_weight(bundle: dict[str, Any]) -> Optional[go.Figure]:
    weights = _frame(bundle, "portfolio_weights")
    if weights.empty:
        weights = _frame(bundle, "unified_portfolio")
    if weights.empty or "ticker" not in weights.columns:
        return None

    working = weights.copy()
    if "final_weight" not in working.columns and "weight" in working.columns:
        working["final_weight"] = pd.to_numeric(working["weight"], errors="coerce")
    if "mispricing" not in working.columns:
        valuation = _frame(bundle, "valuation")
        value_cols = [col for col in ["ticker", "margin_of_safety_pct", "valuation_signal"] if col in valuation.columns]
        if len(value_cols) >= 2:
            latest_val = valuation[value_cols].drop_duplicates(subset=["ticker"], keep="last")
            working = working.merge(latest_val, on="ticker", how="left")
            if "margin_of_safety_pct" in working.columns:
                working["mispricing"] = pd.to_numeric(working["margin_of_safety_pct"], errors="coerce")
            elif "valuation_signal" in working.columns:
                working["mispricing"] = pd.to_numeric(working["valuation_signal"], errors="coerce")
    if "northstar_score" not in working.columns:
        scores = _frame(bundle, "scores")
        score_cols = [col for col in ["ticker", "northstar_score", "score", "final_score"] if col in scores.columns]
        if len(score_cols) >= 2:
            latest_scores = scores[score_cols].drop_duplicates(subset=["ticker"], keep="last")
            working = working.merge(latest_scores, on="ticker", how="left")
            for col in ["northstar_score", "score", "final_score"]:
                if col in working.columns:
                    working["northstar_score"] = pd.to_numeric(working[col], errors="coerce")
                    break
    return _scatter_figure(working, "mispricing", "final_weight", "Mispricing vs Final Weight", color="position_role", size="northstar_score")


def _top_portfolio_scores(bundle: dict[str, Any]) -> Optional[go.Figure]:
    weights = _frame(bundle, "portfolio_weights")
    scores = _frame(bundle, "scores")
    if weights.empty or "ticker" not in weights.columns or scores.empty or "ticker" not in scores.columns:
        return None
    score_col = next((col for col in ["northstar_score", "score", "final_score"] if col in scores.columns), None)
    if score_col is None:
        return None
    latest_scores = scores[["ticker", score_col]].drop_duplicates(subset=["ticker"], keep="last")
    working = weights[["ticker"]].drop_duplicates().merge(latest_scores, on="ticker", how="left")
    working = working.rename(columns={score_col: "northstar_score"})
    working["northstar_score"] = pd.to_numeric(working["northstar_score"], errors="coerce")
    working = working.dropna().sort_values("northstar_score", ascending=False).head(15)
    return _bar_figure(working, "ticker", "northstar_score", "Top Northstar Scores in Current Portfolio")


def _strategy_allocation_area(bundle: dict[str, Any]) -> Optional[go.Figure]:
    df = _frame(bundle, "allocation_history")
    if df.empty or "date" not in df.columns:
        return None
    strategy_cols = [col for col in ["northstar", "mom_6m", "mom_vol_adj", "regime_conditional", "quality_value_combo", "dual_momentum", "value_tilt", "low_vol"] if col in df.columns]
    if not strategy_cols:
        return None
    working = df.copy()
    working["date"] = pd.to_datetime(working["date"], errors="coerce")
    working = working.dropna(subset=["date"]).groupby("date", dropna=False)[strategy_cols].mean().reset_index().tail(120)
    return _multi_line_figure(working, "date", strategy_cols, "Strategy Allocation Time Series")


def _strategy_allocation_heatmap(bundle: dict[str, Any]) -> Optional[go.Figure]:
    df = _frame(bundle, "allocation_history")
    if df.empty or "date" not in df.columns:
        return None
    strategy_cols = [col for col in ["northstar", "mom_6m", "mom_vol_adj", "regime_conditional", "quality_value_combo", "dual_momentum", "value_tilt", "low_vol"] if col in df.columns]
    if not strategy_cols:
        return None
    working = df.copy()
    working["date"] = pd.to_datetime(working["date"], errors="coerce")
    working = working.dropna(subset=["date"]).groupby("date", dropna=False)[strategy_cols].mean().reset_index().tail(120)
    working["date"] = working["date"].dt.strftime("%Y-%m-%d")
    working = working.groupby("date", dropna=False)[strategy_cols].mean().reset_index()
    pivot = working.set_index("date")[strategy_cols].T
    return _heatmap_figure(pivot, "Allocation Heatmap (Recent)")


def _stock_role_distribution(bundle: dict[str, Any]) -> Optional[go.Figure]:
    df = _frame(bundle, "stock_roles")
    if df.empty or "stock_role" not in df.columns:
        return None
    grouped = df["stock_role"].astype(str).value_counts().reset_index()
    grouped.columns = ["stock_role", "count"]
    return _bar_figure(grouped, "stock_role", "count", "NSE Universe Stock-Role Distribution")


def _governor_fraction_donut(bundle: dict[str, Any]) -> Optional[go.Figure]:
    return _donut_figure(_frame(bundle, "governor_budgets"), "bucket", "fraction", "Governor Capital Fractions")


def _governor_budget_bar(bundle: dict[str, Any]) -> Optional[go.Figure]:
    return _bar_figure(_frame(bundle, "governor_budgets"), "bucket", "budget_inr", "Governor Budget Allocation (INR)")


def _chain_by_option_type(bundle: dict[str, Any], value_col: str, title: str) -> Optional[go.Figure]:
    """Strike-axis chain chart, faceted by underlying.

    The raw options_chain bundle mixes every fetched index/underlying together
    (e.g. NIFTY strikes ~21-26k alongside BANKNIFTY strikes ~50k+) — plotting
    them on one shared strike axis produced a nonsensical chart with two
    disconnected, unlabeled clusters. Faceting by `symbol` (falling back to
    `underlying`) keeps each underlying's own strike ladder legible while still
    showing everything the live chain currently covers."""
    df = _frame(bundle, "options_chain")
    if df.empty or "strike" not in df.columns or value_col not in df.columns or "option_type" not in df.columns:
        return None
    working = df.copy()
    derived_column = value_col
    if value_col in {"gamma", "theta", "vega"}:
        source = pd.to_numeric(working[value_col], errors="coerce")
        oi = pd.to_numeric(working.get("oi"), errors="coerce")
        strike = pd.to_numeric(working.get("strike"), errors="coerce")
        if source.nunique(dropna=True) <= 1 and oi.notna().any():
            if value_col == "gamma":
                working["gamma_exposure"] = source * oi * strike
                derived_column = "gamma_exposure"
            elif value_col == "theta":
                working["theta_exposure"] = source * oi
                derived_column = "theta_exposure"
            elif value_col == "vega":
                working["vega_exposure"] = source * oi
                derived_column = "vega_exposure"
    symbol_col = "symbol" if "symbol" in working.columns else ("underlying" if "underlying" in working.columns else None)
    keep = ["strike", derived_column, "option_type"] + ([symbol_col] if symbol_col else [])
    working = working[keep].copy().dropna(subset=["strike", derived_column, "option_type"])
    if working.empty:
        return None
    if symbol_col and working[symbol_col].nunique(dropna=True) > 1:
        symbols = sorted(working[symbol_col].dropna().unique().tolist())
        fig = make_subplots(rows=1, cols=len(symbols), subplot_titles=symbols, shared_yaxes=False)
        colors = {"C": THEME["green"], "CE": THEME["green"], "P": THEME["red"], "PE": THEME["red"]}
        seen_legend = set()
        for i, sym in enumerate(symbols, start=1):
            sub = working[working[symbol_col] == sym].sort_values("strike")
            for opt_type, grp in sub.groupby("option_type"):
                show_legend = opt_type not in seen_legend
                seen_legend.add(opt_type)
                fig.add_trace(
                    go.Scatter(x=grp["strike"], y=grp[derived_column], mode="lines",
                              name=str(opt_type), legendgroup=str(opt_type), showlegend=show_legend,
                              line=dict(width=2.3, color=colors.get(str(opt_type), THEME["blue"]))),
                    row=1, col=i,
                )
        return _apply_theme(fig, title=title, height=420)
    fig = px.line(working.sort_values("strike"), x="strike", y=derived_column, color="option_type")
    fig.update_traces(line=dict(width=2.3))
    return _apply_theme(fig, title=title)


def _options_iv_heatmap(bundle: dict[str, Any]) -> Optional[go.Figure]:
    df = _frame(bundle, "options_chain")
    if df.empty or not {"strike", "option_type", "iv"}.issubset(df.columns):
        return None
    symbol_col = "symbol" if "symbol" in df.columns else ("underlying" if "underlying" in df.columns else None)
    if symbol_col and df[symbol_col].nunique(dropna=True) > 1:
        # Heatmap needs one primary underlying (mixed strike ladders can't
        # share one index axis); show the most-liquid one by open interest.
        primary = (df.groupby(symbol_col)["oi"].sum().sort_values(ascending=False).index[0]
                   if "oi" in df.columns else df[symbol_col].value_counts().index[0])
        df = df[df[symbol_col] == primary]
        title_suffix = f" — {primary}"
    else:
        title_suffix = ""
    pivot = df.pivot_table(index="strike", columns="option_type", values="iv", aggfunc="mean")
    return _heatmap_figure(pivot, f"Option Chain IV Heatmap{title_suffix}")


def _options_active_greeks(bundle: dict[str, Any]) -> Optional[go.Figure]:
    """Net greeks of the fund's OWN open option positions — never a proxy.

    A prior fallback summed OI x greeks across the ENTIRE fetched chain (every
    strike, every underlying, other market participants' open interest
    included) when no positions were open. That is not "active position"
    exposure at all — it is a market-wide aggregate that happens to net near
    zero by construction (calls and puts roughly offset), which silently
    mislabeled "no exposure data" as "flat exposure". When there are truly no
    open positions we say so instead of fabricating a number."""
    df = _frame(bundle, "active_option_positions")
    rows = []
    for greek in ["delta", "gamma", "vega", "theta"]:
        if not df.empty and greek in df.columns:
            rows.append({"greek": greek.upper(), "value": pd.to_numeric(df[greek], errors="coerce").sum()})
    if not rows:
        portfolio_greeks = (bundle.get("options_dashboard_state") or {}).get("portfolio_greeks") or {}
        for greek in ["delta", "gamma", "vega", "theta"]:
            if greek in portfolio_greeks:
                rows.append({"greek": greek.upper(), "value": pd.to_numeric(portfolio_greeks.get(greek), errors="coerce")})
    rows = [r for r in rows if pd.notna(r.get("value"))]
    if rows and any(abs(r["value"]) > 1e-9 for r in rows):
        return _bar_figure(pd.DataFrame(rows), "greek", "value", "Active Option Positions: Net Greeks")
    fig = go.Figure(go.Indicator(
        mode="number", value=0,
        title={"text": "Active Option Positions: Net Greeks<br>"
                       "<span style='font-size:0.8em;color:#94a3b8'>No live option positions are open right now</span>"},
        number={"valueformat": ",d"},
    ))
    return _apply_theme(fig, title="Active Option Positions: Net Greeks", height=320)


def _options_active_underlyings(bundle: dict[str, Any]) -> Optional[go.Figure]:
    df = _frame(bundle, "active_option_positions")
    if not df.empty and "underlying" in df.columns:
        grouped = df["underlying"].astype(str).value_counts().reset_index()
        grouped.columns = ["underlying", "position_count"]
        return _bar_figure(grouped, "underlying", "position_count", "Active Option Positions by Underlying")

    runtime = bundle.get("options_runtime_state") or {}
    open_positions = runtime.get("open_positions") or []
    fig = go.Figure(
        go.Indicator(
            mode="number",
            value=len(open_positions),
            title={
                "text": "Active Option Positions by Underlying<br><span style='font-size:0.8em;color:#94a3b8'>No live option positions are open right now</span>"
            },
            number={"valueformat": ",d"},
        )
    )
    return _apply_theme(fig, title="Active Option Positions by Underlying", height=320)


def _governance_event_counts(bundle: dict[str, Any]) -> Optional[go.Figure]:
    df = _frame(bundle, "options_governance")
    if df.empty or "event_type" not in df.columns:
        return None
    grouped = df["event_type"].astype(str).value_counts().reset_index().head(15)
    grouped.columns = ["event_type", "count"]
    return _bar_figure(grouped, "event_type", "count", "Options Governance Events")


def _runtime_iv_history(bundle: dict[str, Any]) -> Optional[go.Figure]:
    df = _frame(bundle, "option_iv_history")
    if df.empty:
        chain = _frame(bundle, "options_chain")
        if chain.empty or not {"underlying", "iv"}.issubset(chain.columns):
            return None
        latest = chain[["underlying", "iv"]].copy()
        latest["iv"] = pd.to_numeric(latest["iv"], errors="coerce")
        latest = latest.dropna(subset=["underlying", "iv"])
        if latest.empty:
            return None
        latest = latest.groupby("underlying", dropna=False)["iv"].mean().reset_index().sort_values("iv", ascending=False).head(20)
        return _bar_figure(latest, "underlying", "iv", "Current Chain IV by Underlying", orientation="h")
    if df["timestamp"].nunique(dropna=True) <= 2:
        latest = df.sort_values("timestamp").groupby("underlying", dropna=False)["iv"].last().reset_index().sort_values("iv", ascending=False).head(20)
        return _bar_figure(latest, "underlying", "iv", "Current Runtime IV by Underlying", orientation="h")
    fig = px.line(df.sort_values("timestamp"), x="timestamp", y="iv", color="underlying")
    fig.update_traces(line=dict(width=2.3))
    return _apply_theme(fig, title="Runtime IV History by Underlying")


def _volatility_regime_distribution(bundle: dict[str, Any]) -> Optional[go.Figure]:
    df = _frame(bundle, "volatility_state")
    if df.empty or "volatility_regime" not in df.columns:
        return None
    grouped = df["volatility_regime"].astype(str).value_counts().reset_index()
    grouped.columns = ["volatility_regime", "count"]
    return _bar_figure(grouped, "volatility_regime", "count", "Cross-Sectional Volatility Regimes")


def _top_realized_vol(bundle: dict[str, Any]) -> Optional[go.Figure]:
    df = _frame(bundle, "volatility_state")
    if df.empty or "ticker" not in df.columns or "realized_vol" not in df.columns:
        return None
    working = df[["ticker", "realized_vol"]].copy().dropna().sort_values("realized_vol", ascending=False).head(15)
    return _bar_figure(working, "ticker", "realized_vol", "Highest Realized Volatility Names")


def _valuation_family_heatmap(bundle: dict[str, Any]) -> Optional[go.Figure]:
    df = _frame(bundle, "valuation_families")
    if df.empty or "ticker" not in df.columns:
        return None
    cols = [col for col in ["core_gap", "fcff_gap", "fcfe_gap", "ddm_gap", "apv_gap", "transaction_gap", "credit_gap", "real_option_gap"] if col in df.columns]
    if not cols:
        return None
    working = df[["ticker"] + cols].copy().dropna(subset=["ticker"])
    if "core_gap" in working.columns:
        working = working.sort_values("core_gap", ascending=False).head(20)
    pivot = working.set_index("ticker")[cols]
    return _heatmap_figure(pivot, "Valuation-Family Gap Heatmap")


def _cohesive_alpha_top(bundle: dict[str, Any]) -> Optional[go.Figure]:
    df = _frame(bundle, "cohesive_alpha")
    if df.empty or "ticker" not in df.columns or "cohesive_alpha_score" not in df.columns:
        return None
    working = df[["ticker", "cohesive_alpha_score"]].copy().dropna().sort_values("cohesive_alpha_score", ascending=False).head(20)
    return _bar_figure(working, "ticker", "cohesive_alpha_score", "Top Cohesive Alpha Scores")


def _score_quintiles(bundle: dict[str, Any]) -> Optional[go.Figure]:
    """Quintiles are rank-defined so their *counts* are trivially uniform (100
    each). What actually matters is the score gradient they carry — so plot the
    mean composite score per quintile with its min/max whiskers."""
    df = _frame(bundle, "scores")
    if df.empty or "quintile" not in df.columns:
        return None
    score_col = next((c for c in ("northstar_score", "final_score", "score", "model_score") if c in df.columns), None)
    if score_col is None:
        return None
    work = df[["quintile", score_col]].copy()
    work["quintile"] = pd.to_numeric(work["quintile"], errors="coerce")
    work[score_col] = pd.to_numeric(work[score_col], errors="coerce")
    work = work.dropna()
    if work.empty:
        return None
    g = work.groupby("quintile")[score_col].agg(["mean", "min", "max", "count"]).reset_index().sort_values("quintile")
    labels = {1: "Q1 weak", 2: "Q2", 3: "Q3", 4: "Q4", 5: "Q5 strong"}
    x = [labels.get(int(q), f"Q{int(q)}") for q in g["quintile"]]
    palette = ["#ff4d4d", "#c0774d", "#8b95a5", "#5fa878", "#26e07f"]
    colors = [palette[min(int(q) - 1, 4)] for q in g["quintile"]]
    fig = go.Figure(go.Bar(
        x=x, y=g["mean"], marker_color=colors,
        error_y=dict(type="data", symmetric=False,
                     array=(g["max"] - g["mean"]).tolist(),
                     arrayminus=(g["mean"] - g["min"]).tolist(),
                     color="#7d8899", thickness=1),
        text=[f"μ={m:.3f}<br>n={int(n)}" for m, n in zip(g["mean"], g["count"])],
        textposition="outside", textfont=dict(size=9),
        hovertemplate="%{x}<br>mean=%{y:.4f}<extra></extra>",
    ))
    fig.update_layout(title="Score Quintile Gradient — mean composite score (whiskers = min/max)",
                      yaxis_title="Composite score")
    return fig


def _strategy_regret_fig(bundle: dict[str, Any]) -> Optional[go.Figure]:
    """Regret = how much return each strategy left on the table versus the best
    performer. The frame is a long daily history, so show each strategy's most
    recent rolling regret (lower = closer to the best call)."""
    df = _frame(bundle, "strategy_regret")
    if df.empty or "strategy" not in df.columns:
        return None
    metric = next((c for c in ("regret_90d", "regret_30d", "cum_regret", "regret") if c in df.columns), None)
    if metric is None:
        return None
    work = df.copy()
    if "date" in work.columns:
        work["date"] = pd.to_datetime(work["date"], errors="coerce")
        work = work.sort_values("date").groupby("strategy", as_index=False).last()
    work[metric] = pd.to_numeric(work[metric], errors="coerce")
    work = work.dropna(subset=[metric])
    if work.empty:
        return None
    return _bar_figure(work, "strategy", metric, f"Strategy Regret — latest {metric} (lower is better)",
                       orientation="h", ascending=True)


def _strategy_sharpe_vs_drawdown(bundle: dict[str, Any]) -> Optional[go.Figure]:
    df = _frame(bundle, "strategy_performance")
    return _scatter_figure(df, "sharpe", "max_drawdown", "Strategy Sharpe vs Max Drawdown", color="strategy", size="final_equity")


_REGIME_LABEL = {
    "regime_low_vol": "Low-vol (calm)",
    "regime_high_vol": "High-vol (choppy)",
    "regime_crisis": "Crisis (risk-off)",
    "regime_transition": "Transition",
}
_REGIME_COLOR = {
    "regime_low_vol": "#26e07f",
    "regime_high_vol": "#f5a623",
    "regime_crisis": "#ff4d4d",
    "regime_transition": "#38bdf8",
}


def _alpha_os_probabilities(bundle: dict[str, Any]) -> Optional[go.Figure]:
    """How to read: each coloured band is the model's probability, that day, of
    being in a given volatility regime — the bands stack to 100%. The widest
    band on the right edge is the regime the system believes we're in *now*."""
    df = _frame(bundle, "alpha_os_timeseries")
    if df.empty or "timestamp" not in df.columns:
        return None
    cols = [c for c in ["regime_low_vol", "regime_high_vol", "regime_crisis", "regime_transition"] if c in df.columns]
    if not cols:
        return None
    working = df[["timestamp"] + cols].copy()
    working["timestamp"] = pd.to_datetime(working["timestamp"], errors="coerce")
    for c in cols:
        working[c] = pd.to_numeric(working[c], errors="coerce")
    working = working.dropna(subset=["timestamp"]).sort_values("timestamp")
    # Drop degenerate rows where the model emitted no signal: probabilities
    # all zero, OR uniform (0.25 each = maximum entropy = zero information —
    # 92% of history was uniform per the 2026-07-06 audit, finding H1).
    working = working[working[cols].sum(axis=1) > 0.5]
    spread = working[cols].max(axis=1) - working[cols].min(axis=1)
    working = working[spread > 0.01].tail(180)
    if working.empty:
        return None
    fig = go.Figure()
    for c in cols:
        fig.add_trace(go.Scatter(
            x=working["timestamp"], y=working[c], name=_REGIME_LABEL.get(c, c),
            mode="lines", stackgroup="one", groupnorm="percent",
            line=dict(width=0.5, color=_REGIME_COLOR.get(c)),
            fillcolor=_REGIME_COLOR.get(c),
            hovertemplate="%{x|%d-%b}<br>" + _REGIME_LABEL.get(c, c) + ": %{y:.0f}%<extra></extra>",
        ))
    latest = working.iloc[-1]
    dom = max(cols, key=lambda c: latest[c])
    fig.add_annotation(
        xref="paper", yref="paper", x=1.0, y=1.12, showarrow=False, xanchor="right",
        text=f"NOW: <b>{_REGIME_LABEL.get(dom, dom)}</b> ({100*latest[dom]/max(latest[cols].sum(),1e-9):.0f}%)",
        font=dict(color=_REGIME_COLOR.get(dom), size=12),
    )
    fig.update_layout(yaxis=dict(title="probability", ticksuffix="%", range=[0, 100]))
    return _apply_theme(fig, title="Alpha OS Regime Probabilities — belief the market is calm / choppy / crisis (stacked to 100%)", height=430)


def _alpha_os_risk_stack(bundle: dict[str, Any]) -> Optional[go.Figure]:
    """How to read: three named risk pressures on a 0→1 scale. Green = benign,
    amber = building, red = hot. The bar shows *today's* level; the number in
    brackets is where it sits versus its own recent history.

    A run of exact 0.0 across the whole recorded history means the Alpha OS
    orchestrator has never emitted these risk metrics (it mostly runs in
    shadow/degraded mode) — that is "no signal", not "confirmed calm", so we
    say that explicitly rather than paint three green zero-bars that read as
    reassuring."""
    df = _frame(bundle, "alpha_os_timeseries")
    if df.empty:
        return None
    specs = [
        ("crowding_score", "Crowding — everyone in the same trade"),
        ("gap_risk_score", "Gap risk — overnight jump exposure"),
        ("convexity_score", "Convexity — payoff curvature stress"),
    ]
    # "Current" must come from the latest row where the orchestrator was
    # actually operating (not 'error'/'blocked_*') — a transient degraded
    # cycle at the very tail of history was zeroing out every metric even
    # though 70%+ of the recorded history carries real, nonzero readings.
    mode = df.get("mode", pd.Series(dtype=str)).astype(str)
    healthy = ~mode.str.contains("error", case=False, na=False) & ~mode.str.contains("blocked", case=False, na=False)
    current_slice = df[healthy] if healthy.any() else df

    rows = []
    for col, label in specs:
        if col not in df.columns:
            continue
        s = pd.to_numeric(df[col], errors="coerce").dropna()
        if s.empty or not (s.abs() > 1e-9).any():
            continue
        cur_series = pd.to_numeric(current_slice[col], errors="coerce").dropna()
        cur = float(cur_series.iloc[-1]) if not cur_series.empty else float(s.iloc[-1])
        pct = float((s <= cur).mean() * 100) if len(s) > 1 else 50.0
        rows.append((label, cur, pct))
    if not rows:
        fig = go.Figure(go.Indicator(
            mode="number", value=0,
            title={"text": "Alpha OS Risk Stack<br>"
                           "<span style='font-size:0.75em;color:#94a3b8'>No signal: the orchestrator has not "
                           "emitted crowding/gap/convexity risk in its recorded history (running in shadow mode)</span>"},
        ))
        return _apply_theme(fig, title="Alpha OS Risk Stack", height=320)
    labels = [r[0] for r in rows]
    values = [r[1] for r in rows]

    def sev(v: float) -> str:
        return "#26e07f" if v < 0.33 else "#f5a623" if v < 0.66 else "#ff4d4d"

    fig = go.Figure(go.Bar(
        x=values, y=labels, orientation="h",
        marker=dict(color=[sev(v) for v in values]),
        text=[f"{v:.2f}  ·  {p:.0f}th pct" for (_, v, p) in rows],
        textposition="outside", textfont=dict(size=10),
        hovertemplate="%{y}<br>level=%{x:.3f}<extra></extra>",
    ))
    fig.add_vline(x=0.33, line=dict(color="#5fa878", width=1, dash="dot"))
    fig.add_vline(x=0.66, line=dict(color="#ff4d4d", width=1, dash="dot"))
    fig.update_layout(xaxis=dict(range=[0, 1.05], title="risk level"))
    return _apply_theme(fig, title="Alpha OS Risk Stack — current pressure per risk (0 calm → 1 hot)", height=360)


def _alpha_os_capacity(bundle: dict[str, Any]) -> Optional[go.Figure]:
    df = _frame(bundle, "alpha_os_timeseries")
    return _multi_line_figure(
        df.tail(200),
        "timestamp",
        [col for col in ["gross_target", "gross_used", "gross_cap", "net_target", "net_used"] if col in df.columns],
        "Alpha OS Capacity & Utilization",
    )


def _alpha_os_latest_weights(bundle: dict[str, Any]) -> Optional[go.Figure]:
    df = _frame(bundle, "alpha_os_posteriors")
    if not df.empty and {"strategy_name", "timestamp", "final_weight"}.issubset(df.columns):
        latest_ts = df["timestamp"].max()
        latest = df[df["timestamp"] == latest_ts].copy()
        latest["final_weight"] = pd.to_numeric(latest["final_weight"], errors="coerce")
        latest = latest.dropna(subset=["strategy_name", "final_weight"])
        if not latest.empty and latest["final_weight"].abs().sum() > 0:
            latest = latest.sort_values("final_weight", ascending=False)
            return _bar_figure(latest, "strategy_name", "final_weight", "Latest Alpha OS Strategy Weights")
    weights = _frame(bundle, "strategy_weights")
    if weights.empty:
        return None
    latest = weights.rename(columns={"strategy": "strategy_name", "weight": "final_weight"})
    return _bar_figure(latest, "strategy_name", "final_weight", "Latest Alpha OS Strategy Weights")


def _alpha_os_mean_vs_weight(bundle: dict[str, Any]) -> Optional[go.Figure]:
    df = _frame(bundle, "alpha_os_posteriors")
    return _scatter_figure(df.tail(100), "posterior_mean", "final_weight", "Alpha OS Posterior Mean vs Final Weight", color="strategy_name", size="credibility")


def _state_write_sections(bundle: dict[str, Any]) -> Optional[go.Figure]:
    df = _frame(bundle, "state_log")
    if df.empty:
        return None
    section_col = "canonical_section" if "canonical_section" in df.columns else "section"
    if section_col not in df.columns:
        return None
    grouped = df[section_col].astype(str).value_counts().reset_index().head(12)
    grouped.columns = ["section", "write_count"]
    return _bar_figure(grouped, "section", "write_count", "Canonical State Writes by Section")


def _state_write_intensity(bundle: dict[str, Any]) -> Optional[go.Figure]:
    df = _frame(bundle, "state_log")
    if df.empty or "timestamp" not in df.columns:
        return None
    working = df.copy()
    working["minute"] = working["timestamp"].dt.floor("30min")
    grouped = working.groupby("minute").size().reset_index(name="writes")
    return _line_figure(grouped, "minute", "writes", "State Write Intensity", color=THEME["teal"])


def _humanize_age(hours: float) -> str:
    if hours < 1:
        return f"{hours * 60:.0f}m"
    if hours < 48:
        return f"{hours:.1f}h"
    return f"{hours / 24:.1f}d"


def _pipeline_freshness_fig(bundle: dict[str, Any]) -> Optional[go.Figure]:
    """Operational freshness board across every tracked pipeline.

    Raw ages here span 5+ orders of magnitude (seconds for the live-engine
    heartbeat vs. months for a dormant status file) — a plain linear bar chart
    made every fast-refreshing source an invisible sliver next to the stale
    ones, and a source with no timestamp at all (Alpha OS, which only carries
    one when the orchestrator isn't in shadow mode) rendered as a NaN-height
    bar. Log-scale x-axis + explicit "no timestamp" row + human-readable age
    labels + severity coloring make this an actual ops board."""
    df = _frame(bundle, "pipeline_freshness")
    if df.empty or "source" not in df.columns:
        return None
    working = df.copy()
    working["age_hours"] = pd.to_numeric(working.get("age_hours"), errors="coerce")
    has_age = working[working["age_hours"].notna() & (working["age_hours"] > 0)].sort_values("age_hours")
    missing = working[working["age_hours"].isna() | (working["age_hours"] <= 0)]

    def sev(age_h: float) -> str:
        if age_h <= 1:
            return THEME["green"]
        if age_h <= 24:
            return THEME["blue"]
        if age_h <= 72:
            return THEME["amber"]
        return THEME["red"]

    fig = go.Figure()
    if not has_age.empty:
        fig.add_trace(go.Bar(
            x=has_age["age_hours"], y=has_age["source"], orientation="h",
            marker=dict(color=[sev(a) for a in has_age["age_hours"]]),
            text=[f"{_humanize_age(a)} · {s}" for a, s in zip(has_age["age_hours"], has_age.get("status", ""))],
            textposition="outside", textfont=dict(size=10),
            hovertemplate="%{y}: %{text}<extra></extra>",
            showlegend=False,
        ))
    if not missing.empty:
        # Plot at a fixed sentinel position past the oldest real bar so "we
        # don't know" is visually distinct from "we know it's very stale".
        sentinel = float(has_age["age_hours"].max() * 1.3) if not has_age.empty else 1.0
        fig.add_trace(go.Bar(
            x=[sentinel] * len(missing), y=missing["source"], orientation="h",
            marker=dict(color=THEME["grid"], pattern=dict(shape="/")),
            text=["no timestamp reported"] * len(missing),
            textposition="outside", textfont=dict(size=10, color=THEME["grid"]),
            hovertemplate="%{y}: no timestamp reported<extra></extra>",
            showlegend=False,
        ))
    fig.update_xaxes(type="log", title="age (hours, log scale)")
    return _apply_theme(fig, title="Data Pipeline Age — freshness across every tracked source", height=max(320, 60 + 34 * len(working)))


def _component_status_fig(bundle: dict[str, Any]) -> Optional[go.Figure]:
    df = _frame(bundle, "component_status")
    if df.empty or "status" not in df.columns:
        return None
    grouped = df["status"].astype(str).value_counts().reset_index()
    grouped.columns = ["status", "count"]
    return _bar_figure(grouped, "status", "count", "System Component Status Mix")


def _runtime_surface_age(bundle: dict[str, Any]) -> Optional[go.Figure]:
    df = _frame(bundle, "pipeline_freshness")
    if df.empty:
        return None
    working = df[df["source"].isin(["Orchestrator", "Options Runtime", "Heartbeat", "Alpha OS"])].copy()
    if working.empty:
        working = df.copy()
    return _bar_figure(working, "source", "age_hours", "Runtime Surface Age (Hours)", color="status")


def _average_slippage_series(bundle: dict[str, Any]) -> Optional[go.Figure]:
    df = _frame(bundle, "execution_quality")
    if df.empty or "date" not in df.columns or "avg_slippage_bps" not in df.columns:
        return None
    working = df[["date", "avg_slippage_bps"]].copy()
    working["date"] = pd.to_datetime(working["date"], errors="coerce")
    working["avg_slippage_bps"] = pd.to_numeric(working["avg_slippage_bps"], errors="coerce")
    working = working.dropna(subset=["date", "avg_slippage_bps"]).sort_values("date")
    if working.empty:
        return None
    fig = px.line(working, x="date", y="avg_slippage_bps", markers=True)
    fig.update_traces(line=dict(width=2.4, color=THEME["amber"]), marker=dict(size=7, color=THEME["amber"]))
    return _apply_theme(fig, title="Average Slippage (bps)", height=380)


def _top_owner_earnings_yield(bundle: dict[str, Any]) -> Optional[go.Figure]:
    df = _frame(bundle, "valuation")
    if df.empty or "ticker" not in df.columns or "owner_earnings_yield_v2" not in df.columns:
        return None
    working = df[["ticker", "owner_earnings_yield_v2"]].copy()
    working["owner_earnings_yield_v2"] = pd.to_numeric(working["owner_earnings_yield_v2"], errors="coerce")
    working = working.dropna(subset=["ticker", "owner_earnings_yield_v2"])
    if working.empty:
        return None
    display_cap = working["owner_earnings_yield_v2"].quantile(0.95)
    if pd.isna(display_cap) or display_cap <= 0:
        display_cap = working["owner_earnings_yield_v2"].max()
    working = working.sort_values("owner_earnings_yield_v2", ascending=False).head(20)
    working["display_yield"] = working["owner_earnings_yield_v2"].clip(upper=display_cap)
    fig = px.bar(
        working.sort_values("display_yield", ascending=True),
        x="display_yield",
        y="ticker",
        orientation="h",
        custom_data=["owner_earnings_yield_v2"],
    )
    fig.update_traces(
        marker_color=THEME["green"],
        hovertemplate="%{y}: %{customdata[0]:.4f}<extra></extra>",
    )
    return _apply_theme(fig, title="Top Owner-Earnings Yield", height=min(820, max(420, 120 + 24 * len(working))))


def _spec_line(section: str, key: str, x: str, y: str, title: str, description: str, *, area: bool = False, color: str = THEME["blue"]) -> VisualSpec:
    return VisualSpec(
        visual_id=f"{section}:{key}:{y}",
        section=section,
        title=title,
        description=description,
        builder=lambda bundle, key=key, x=x, y=y, title=title, area=area, color=color: _line_figure(_frame(bundle, key), x, y, title, color=color, area=area),
    )


def _spec_hist(section: str, key: str, column: str, title: str, description: str) -> VisualSpec:
    return VisualSpec(
        visual_id=f"{section}:{key}:{column}:hist",
        section=section,
        title=title,
        description=description,
        builder=lambda bundle, key=key, column=column, title=title: _histogram_figure(_frame(bundle, key), column, title),
    )


def _spec_bar(section: str, key: str, x: str, y: str, title: str, description: str, *, orientation: str = "v", top_n: Optional[int] = None, ascending: bool = False, color: Optional[str] = None) -> VisualSpec:
    return VisualSpec(
        visual_id=f"{section}:{key}:{x}:{y}:bar",
        section=section,
        title=title,
        description=description,
        builder=lambda bundle, key=key, x=x, y=y, title=title, orientation=orientation, top_n=top_n, ascending=ascending, color=color: _bar_figure(_frame(bundle, key), x, y, title, orientation=orientation, top_n=top_n, ascending=ascending, color=color),
    )


def _spec_scatter(section: str, key: str, x: str, y: str, title: str, description: str, *, color: Optional[str] = None, size: Optional[str] = None) -> VisualSpec:
    return VisualSpec(
        visual_id=f"{section}:{key}:{x}:{y}:scatter",
        section=section,
        title=title,
        description=description,
        builder=lambda bundle, key=key, x=x, y=y, title=title, color=color, size=size: _scatter_figure(_frame(bundle, key), x, y, title, color=color, size=size),
    )


def _build_specs() -> list[VisualSpec]:
    specs: list[VisualSpec] = [
        VisualSpec("overview_nav_vs_benchmark", "Executive Overview", "Portfolio vs NIFTY 50 (Indexed)", "Hard-cutover NAV surface against benchmark.", _overview_nav_vs_benchmark),
        VisualSpec("overview_governor_fractions", "Executive Overview", "Governor Capital Fractions", "Top-level capital structure from the canonical governor.", _governor_fraction_donut),
        VisualSpec("overview_pnl_mix", "Executive Overview", "Today's P&L Mix", "Equity, options, and net P&L from the unified P&L surface.", _overview_pnl_mix),
        VisualSpec("overview_market_regime_timeline", "Executive Overview", "Regime Timeline", "Current market regime path from canonical state and regime history.", _market_regime_timeline),
        VisualSpec("overview_alpha_probs", "Executive Overview", "Alpha OS Regime Probabilities", "How to read: each band is the model's belief the market is calm (green), choppy (amber), crisis (red) or transitioning (cyan); bands stack to 100%, and the widest band at the right edge is the regime it believes we are in NOW.", _alpha_os_probabilities),
        VisualSpec("overview_pipeline_age", "Executive Overview", "Data Pipeline Age (Hours)", "Freshness across canonical operational surfaces.", _pipeline_freshness_fig),
        VisualSpec("overview_component_status", "Executive Overview", "System Component Status Mix", "Execution-log component status by outcome.", _component_status_fig),
        VisualSpec("overview_runtime_age", "Executive Overview", "Runtime Surface Age (Hours)", "Operational age of orchestrator and options runtime surfaces.", _runtime_surface_age),
    ]

    perf_metrics = [
        ("nav", "Total NAV", "Canonical combined NAV history.", False),
        ("nav_equity_only", "Equity-Only NAV", "Equity sleeve NAV through the unified ledger.", False),
        ("nav_options_pnl", "Options P&L Sleeve", "Options contribution in the unified NAV stack.", True),
        ("daily_return", "Daily Return", "Day-over-day canonical returns.", True),
        ("drawdown", "Drawdown", "Canonical drawdown series.", True),
        ("high_water_mark", "High Water Mark", "Running capital high-water mark.", False),
        ("net_cash_position", "Net Cash Position", "Cash carried by the unified book.", True),
        ("transaction_costs_cumulative", "Cumulative Transaction Costs", "Integrated transaction cost drag.", False),
    ]
    for column, title, description, area in perf_metrics:
        specs.append(_spec_line("Performance & P&L", "nav", "date", column, title, description, area=area, color=THEME["blue"]))
    specs.extend(
        [
            _spec_hist("Performance & P&L", "nav", "daily_return", "Daily Return Distribution", "Distribution of realized daily returns."),
            VisualSpec("performance_monthly_heatmap", "Performance & P&L", "Monthly Returns Heatmap (%)", "Monthly return grid from canonical NAV.", _monthly_returns_heatmap),
            VisualSpec("performance_ledger_book", "Performance & P&L", "Ledger Net P&L by Book", "P&L contribution by book inside the unified ledger.", _ledger_pnl_by_book),
            VisualSpec("performance_ledger_strategy", "Performance & P&L", "Ledger Net P&L by Strategy", "Strategy-level P&L from recorded ledger events.", _ledger_pnl_by_strategy),
            _spec_bar("Performance & P&L", "ledger", "entry_type", "notional", "Ledger Notional by Entry Type", "Executed notional split by event type.", color="book"),
            _spec_hist("Performance & P&L", "ledger", "quantity", "Trade Size Distribution", "Distribution of traded quantities."),
            VisualSpec("perf_avg_slippage", "Performance & P&L", "Average Slippage (bps)", "Execution-quality slippage series.", _average_slippage_series),
            VisualSpec("performance_shadow_nav", "Performance & P&L", "Canonical NAV vs Shadow Portfolio Value", "Shadow engine parity check against the unified P&L surface.", _shadow_vs_nav),
        ]
    )

    market_metrics = [
        ("risk_on_probability", "Risk-On Probability", "Model-implied risk-on probability."),
        ("stress_score", "Stress Score", "Canonical market stress score."),
        ("macro_score", "Macro Score", "Macro scoring stream from the integrated market state."),
        ("breadth_pct", "Market Breadth", "Cross-sectional breadth in the NSE universe."),
        ("participation_score", "Participation Score", "Participation quality in the current tape."),
        ("correlation", "Market Correlation", "Cross-sectional correlation pressure."),
        ("allowed_exposure", "Allowed Equity Exposure", "Maximum top-down exposure permission."),
        ("health_score", "Market Health Score", "Integrated market health from the live state."),
    ]
    for column, title, description in market_metrics:
        specs.append(_spec_line("Market & Regime", "market_state", "date", column, title, description, color=THEME["cyan"]))
    specs.extend(
        [
            VisualSpec("market_regime_timeline", "Market & Regime", "Regime Timeline", "Observed regime path over time.", _market_regime_timeline),
            VisualSpec("market_transition_matrix", "Market & Regime", "Regime Transition Matrix", "Empirical regime-to-regime transition map.", _regime_transition_matrix),
            VisualSpec("market_vol_regime_counts", "Market & Regime", "Volatility Regime Counts", "Distribution of volatility regime observations.", _volatility_regime_counts),
            VisualSpec("market_risk_on_vs_stress", "Market & Regime", "Risk-On Probability vs Stress Score", "Relationship between risk appetite and stress.", _risk_on_vs_stress),
            VisualSpec("market_unified_macro_exposure", "Market & Regime", "Long-Horizon Macro Score & Exposure Ceiling",
                       "5-year history of the macro-conditioning score and the equity-exposure cap it implies.",
                       _unified_macro_and_exposure),
            VisualSpec("market_exposure_allowed_vs_actual", "Market & Regime", "Allowed vs Actual Exposure", "Live exposure policy vs actual runtime exposure.", _exposure_allowed_vs_actual),
        ]
    )

    sentiment_metrics = [
        ("india_market_polarity", "India Market Polarity", "Market-level sentiment polarity."),
        ("india_market_conviction", "India Market Conviction", "Market-level conviction signal."),
        ("india_market_uncertainty", "India Market Uncertainty", "Market-level uncertainty signal."),
        ("global_risk_sentiment", "Global Risk Sentiment", "Global risk backdrop carried into V3 sentiment."),
        ("news_volume_total", "Market News Volume", "Daily market-news volume processed by the sentiment system."),
        ("sentiment_mean", "Daily Sentiment Mean", "Cross-headline sentiment average."),
        ("conviction_mean", "Daily Conviction Mean", "Average conviction in the sentiment pipeline."),
        ("uncertainty_mean", "Daily Uncertainty Mean", "Average uncertainty in processed headlines."),
        ("headline_count", "Headline Count", "Total processed headlines by day."),
    ]
    for key, title, description in [
        ("market_sentiment", "India Market Polarity", "Market-level sentiment polarity."),
        ("market_sentiment", "India Market Conviction", "Market-level conviction signal."),
        ("market_sentiment", "India Market Uncertainty", "Market-level uncertainty signal."),
        ("market_sentiment", "Global Risk Sentiment", "Global risk backdrop carried into V3 sentiment."),
        ("market_sentiment", "Market News Volume", "Daily market-news volume processed by the sentiment system."),
        ("daily_sentiment", "Daily Sentiment Mean", "Cross-headline sentiment average."),
        ("daily_sentiment", "Daily Conviction Mean", "Average conviction in the sentiment pipeline."),
        ("daily_sentiment", "Daily Uncertainty Mean", "Average uncertainty in processed headlines."),
        ("daily_sentiment", "Headline Count", "Total processed headlines by day."),
    ]:
        column = {
            "India Market Polarity": "india_market_polarity",
            "India Market Conviction": "india_market_conviction",
            "India Market Uncertainty": "india_market_uncertainty",
            "Global Risk Sentiment": "global_risk_sentiment",
            "Market News Volume": "news_volume_total",
            "Daily Sentiment Mean": "sentiment_mean",
            "Daily Conviction Mean": "conviction_mean",
            "Daily Uncertainty Mean": "uncertainty_mean",
            "Headline Count": "headline_count",
        }[title]
        specs.append(_spec_line("Sentiment & Alternative Data", key, "date", column, title, description, color=THEME["teal"]))
    specs.extend(
        [
            VisualSpec("sentiment_top_positive", "Sentiment & Alternative Data", "Top Positive Ticker Sentiment", "Latest covered names with the strongest positive polarity.", lambda bundle: _latest_ticker_sentiment_chart(bundle, positive=True)),
            VisualSpec("sentiment_top_negative", "Sentiment & Alternative Data", "Top Negative Ticker Sentiment", "Latest covered names with the strongest negative polarity.", lambda bundle: _latest_ticker_sentiment_chart(bundle, positive=False)),
            VisualSpec("sentiment_source_coverage", "Sentiment & Alternative Data", "Ticker Sentiment Coverage by Source", "Which real news surfaces are driving company sentiment coverage.", _sentiment_source_coverage),
            VisualSpec("alternative_bulk_daily", "Sentiment & Alternative Data", "Bulk Deals Count by Day", "NSE bulk-deal collection throughput over time.", _bulk_deal_daily_counts),
            VisualSpec("alternative_announce_categories", "Sentiment & Alternative Data", "Announcement Categories", "Real announcement-category mix in the alternative-data layer.", _announcement_categories),
        ]
    )

    portfolio_specs = [
        _spec_bar("Portfolio & Governor", "portfolio_weights", "ticker", "weight", "Current Portfolio Weights", "Canonical equity portfolio weights.", top_n=15),
        VisualSpec("portfolio_role_donut", "Portfolio & Governor", "Portfolio Weight by Role", "Core vs satellite expression in the current portfolio.", _weights_role_donut),
        VisualSpec("portfolio_sector_exposure", "Portfolio & Governor", "Sector Exposure by Weight", "Sector-level concentration inside the current equity book.", _sector_exposure),
        VisualSpec("portfolio_mispricing_weight", "Portfolio & Governor", "Mispricing vs Final Weight", "Whether capital is flowing to the biggest opportunity gaps.", _mispricing_vs_weight),
        VisualSpec("portfolio_top_scores", "Portfolio & Governor", "Top Northstar Scores in Current Portfolio", "Highest conviction portfolio names by score.", _top_portfolio_scores),
        VisualSpec("portfolio_strategy_area", "Portfolio & Governor", "Strategy Allocation Time Series", "Recent history of multi-strategy allocations.", _strategy_allocation_area),
        VisualSpec("portfolio_strategy_heatmap", "Portfolio & Governor", "Allocation Heatmap (Recent)", "Compact recent allocation map across strategies.", _strategy_allocation_heatmap),
        _spec_line("Portfolio & Governor", "state_history", "date", "governor_state_equity_fraction", "Governor Equity Fraction History", "Historical equity fraction in canonical state.", color=THEME["green"]),
        _spec_line("Portfolio & Governor", "state_history", "date", "governor_state_options_fraction", "Governor Options Fraction History", "Historical options fraction in canonical state.", color=THEME["amber"]),
        _spec_line("Portfolio & Governor", "state_history", "date", "governor_state_cash_fraction", "Governor Cash Fraction History", "Historical cash reserve fraction.", color=THEME["red"]),
        VisualSpec("portfolio_governor_donut", "Portfolio & Governor", "Governor Capital Fractions", "Current top-level capital split from the canonical governor.", _governor_fraction_donut),
        VisualSpec("portfolio_governor_budget", "Portfolio & Governor", "Governor Budget Allocation (INR)", "Current capital budget by sleeve.", _governor_budget_bar),
        VisualSpec("portfolio_stock_roles", "Portfolio & Governor", "NSE Universe Stock-Role Distribution", "Leader/follower role mix in the modeled NSE universe.", _stock_role_distribution),
        _spec_bar("Portfolio & Governor", "strategy_weights", "strategy", "weight", "Alpha OS Strategy Weights", "Active strategy weights from canonical Alpha OS state.", top_n=12),
        _spec_bar("Portfolio & Governor", "strategy_performance", "strategy", "total_return", "Strategy Total Return", "Backtest/live strategy return comparison.", top_n=16),
    ]
    specs.extend(portfolio_specs)

    option_specs = [
        VisualSpec("options_iv_smile", "Options & Risk", "IV Smile by Strike", "Current option-chain IV smile for calls and puts.", lambda bundle: _chain_by_option_type(bundle, "iv", "IV Smile by Strike")),
        VisualSpec("options_oi", "Options & Risk", "Open Interest by Strike", "Current option-chain open interest by strike.", lambda bundle: _chain_by_option_type(bundle, "oi", "Open Interest by Strike")),
        VisualSpec("options_volume", "Options & Risk", "Volume by Strike", "Current option-chain traded volume by strike.", lambda bundle: _chain_by_option_type(bundle, "volume", "Volume by Strike")),
        VisualSpec("options_delta", "Options & Risk", "Delta by Strike", "Current chain delta exposure by strike.", lambda bundle: _chain_by_option_type(bundle, "delta", "Delta by Strike")),
        VisualSpec("options_gamma", "Options & Risk", "Gamma by Strike", "Current chain gamma exposure by strike.", lambda bundle: _chain_by_option_type(bundle, "gamma", "Gamma by Strike")),
        VisualSpec("options_theta", "Options & Risk", "Theta by Strike", "Current chain theta by strike.", lambda bundle: _chain_by_option_type(bundle, "theta", "Theta by Strike")),
        VisualSpec("options_vega", "Options & Risk", "Vega by Strike", "Current chain vega by strike.", lambda bundle: _chain_by_option_type(bundle, "vega", "Vega by Strike")),
        _spec_scatter("Options & Risk", "options_chain", "moneyness", "iv", "Moneyness vs IV", "Current moneyness vs implied-vol relationship.", color="option_type", size="oi"),
        VisualSpec("options_iv_heatmap", "Options & Risk", "Option Chain IV Heatmap", "Strike x option-type IV surface built from the latest real chain.", _options_iv_heatmap),
        VisualSpec("options_active_greeks", "Options & Risk", "Active Option Positions: Net Greeks", "Greeks aggregated from the live options dashboard state.", _options_active_greeks),
        VisualSpec("options_active_underlyings", "Options & Risk", "Active Option Positions by Underlying", "Underlying concentration in the live options overlay.", _options_active_underlyings),
        VisualSpec("options_governance_events", "Options & Risk", "Options Governance Events", "Governance event frequencies in the options engine.", _governance_event_counts),
        VisualSpec("options_runtime_iv", "Options & Risk", "Runtime IV History by Underlying", "IV history persisted by the options runtime.", _runtime_iv_history),
        VisualSpec("options_volatility_regimes", "Options & Risk", "Cross-Sectional Volatility Regimes", "Volatility-state distribution across covered NSE names.", _volatility_regime_distribution),
    ]
    specs.extend(option_specs)

    valuation_specs = [
        _spec_hist("Valuation & Research", "valuation", "margin_of_safety_pct", "Margin of Safety Distribution", "Cross-sectional margin of safety across the valuation engine."),
        _spec_bar("Valuation & Research", "valuation", "ticker", "margin_of_safety_pct", "Top Margin of Safety Names", "Most undervalued names by margin of safety.", top_n=20),
        _spec_hist("Valuation & Research", "valuation", "moat_score_v2", "Moat Score Distribution", "Distribution of moat scores in the covered NSE universe."),
        _spec_scatter("Valuation & Research", "valuation", "pe", "pb", "P/E vs P/B", "Cross-sectional valuation map.", color="Industry", size="market_cap"),
        VisualSpec("research_owner_earnings", "Valuation & Research", "Top Owner-Earnings Yield", "Highest owner-earnings yield opportunities.", _top_owner_earnings_yield),
        _spec_box("Valuation & Research", "valuation", "Industry", "margin_of_safety_pct", "Margin of Safety by Industry", "Industry dispersion in valuation opportunity."),
        _spec_scatter("Valuation & Research", "valuation", "market_cap", "margin_of_safety_pct", "Market Cap vs Margin of Safety", "Whether opportunity lives in size or mispricing.", color="Industry"),
        _spec_scatter("Valuation & Research", "valuation", "buffett_quality_score", "final_value_index", "Quality vs Final Value Index", "Value capture vs quality overlay.", color="Industry", size="market_cap"),
        _spec_hist("Valuation & Research", "valuation_posterior", "posterior_gap", "Posterior Gap Distribution", "Posterior valuation gap across the universe."),
        _spec_scatter("Valuation & Research", "valuation_posterior", "posterior_gap", "posterior_confidence", "Posterior Gap vs Confidence", "Posterior confidence against mispricing signal.", color="regime_crisis_prob"),
        VisualSpec("valuation_family_heatmap", "Valuation & Research", "Valuation-Family Gap Heatmap", "Family-level gap matrix across a representative opportunity set.", _valuation_family_heatmap),
        _spec_bar("Valuation & Research", "valuation_engines", "ticker", "composite_z", "Top Composite Engine Z-Scores", "Composite valuation-engine winners.", top_n=20),
        _spec_hist("Valuation & Research", "valuation_engines", "agreement", "Valuation Engine Agreement", "Agreement distribution across valuation engines."),
        VisualSpec("valuation_cohesive_alpha", "Valuation & Research", "Top Cohesive Alpha Scores", "Best combined research/ranking names from the cohesive alpha feed.", _cohesive_alpha_top),
        _spec_hist("Valuation & Research", "cohesive_alpha", "cohesive_alpha_score", "Cohesive Alpha Score Distribution", "Distribution of the cohesive alpha signal."),
        VisualSpec("valuation_score_quintiles", "Valuation & Research", "Score Quintile Distribution", "Final score coverage by quintile.", _score_quintiles),
    ]
    specs.extend(valuation_specs)

    alpha_ops_specs = [
        VisualSpec("alpha_probs", "Alpha OS & Operations", "Alpha OS Regime Probabilities", "How to read: each band is the model's belief the market is calm (green), choppy (amber), crisis (red) or transitioning (cyan); bands stack to 100%, and the widest band at the right edge is the regime it believes we are in NOW.", _alpha_os_probabilities),
        _spec_line("Alpha OS & Operations", "alpha_os_timeseries", "timestamp", "regime_entropy", "Alpha OS Regime Entropy", "Regime uncertainty through time.", color=THEME["red"]),
        VisualSpec("alpha_capacity", "Alpha OS & Operations", "Alpha OS Capacity & Utilization", "Gross/net capacity vs utilization in Alpha OS.", _alpha_os_capacity),
        VisualSpec("alpha_risk_stack", "Alpha OS & Operations", "Alpha OS Risk Stack", "How to read: three named risk pressures on a 0-to-1 scale — green bar = benign, amber = building, red = hot; the label shows today's level and where it sits vs its own history (percentile).", _alpha_os_risk_stack),
        VisualSpec("alpha_latest_weights", "Alpha OS & Operations", "Latest Alpha OS Strategy Weights", "Most recent final strategy weights chosen by Alpha OS.", _alpha_os_latest_weights),
        VisualSpec("alpha_mean_vs_weight", "Alpha OS & Operations", "Alpha OS Posterior Mean vs Final Weight", "Posterior return signal vs deployed weight.", _alpha_os_mean_vs_weight),
        VisualSpec("ops_strategy_regret", "Alpha OS & Operations", "Strategy Regret Scores", "How much return each strategy left on the table vs the best performer.", _strategy_regret_fig),
        _spec_bar("Alpha OS & Operations", "strategy_beliefs", "strategy", "belief_strength", "Strategy Belief Strength", "Belief weights emitted by the intelligence layer.", top_n=16),
        VisualSpec("ops_pipeline_age", "Alpha OS & Operations", "Data Pipeline Age (Hours)", "Freshness across top operational surfaces.", _pipeline_freshness_fig),
        VisualSpec("ops_component_mix", "Alpha OS & Operations", "System Component Status Mix", "Status mix across execution-log components.", _component_status_fig),
        VisualSpec("ops_state_write_sections", "Alpha OS & Operations", "Canonical State Writes by Section", "Shared-state write mix after the hard cutover.", _state_write_sections),
        VisualSpec("ops_state_write_intensity", "Alpha OS & Operations", "State Write Intensity", "Recent cadence of canonical state writes.", _state_write_intensity),
        VisualSpec("ops_runtime_age", "Alpha OS & Operations", "Runtime Surface Age (Hours)", "Freshness of the orchestrator/runtime heartbeat surfaces.", _runtime_surface_age),
        VisualSpec("ops_strategy_sharpe_drawdown", "Alpha OS & Operations", "Strategy Sharpe vs Max Drawdown", "Higher-level strategy outcome map.", _strategy_sharpe_vs_drawdown),
    ]
    specs.extend(alpha_ops_specs)

    return specs


def _spec_box(section: str, key: str, x: str, y: str, title: str, description: str) -> VisualSpec:
    return VisualSpec(
        visual_id=f"{section}:{key}:{x}:{y}:box",
        section=section,
        title=title,
        description=description,
        builder=lambda bundle, key=key, x=x, y=y, title=title: _box_figure(_frame(bundle, key), x, y, title),
    )


VISUAL_SPECS = _build_specs()


def _section_counts() -> dict[str, int]:
    counts: dict[str, int] = {section: 0 for section in SECTION_ORDER}
    for spec in VISUAL_SPECS:
        counts[spec.section] = counts.get(spec.section, 0) + 1
    return counts


def _freshness_pills(bundle: dict[str, Any]) -> str:
    pills = []
    for row in _frame(bundle, "pipeline_freshness").to_dict("records"):
        age = row.get("age_hours")
        status = row.get("status") or "unknown"
        age_str = "n/a" if age is None or pd.isna(age) else f"{float(age):.1f}h"
        pills.append(f'<span class="ns-pill">{row.get("source")}: {status} / {age_str}</span>')
    return "".join(pills)


def _render_header(bundle: dict[str, Any]) -> None:
    state = bundle.get("state") or {}
    market = state.get("market") or {}
    sentiment = state.get("sentiment") or {}
    alpha_os = state.get("alpha_os") or {}
    health = bundle.get("system_health") or {}
    perf = bundle.get("performance_metrics") or {}
    valuation_state = state.get("valuation_state") or {}

    st.markdown(
        f"""
        <div class="ns-hero">
            <div class="ns-card-title" style="font-size:1.65rem;">Northstar V3 Canonical Intelligence Dashboard</div>
            <div class="ns-card-subtitle">Gap 8 cutover: one integrated dashboard, one canonical state, real data only.</div>
            <div>{_freshness_pills(bundle)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric("Current NAV", f"₹{float(perf.get('current_nav', 0.0)):,.0f}")
    col2.metric("Market Regime", str(market.get("regime", "unknown")))
    col3.metric("Sentiment", str(sentiment.get("market_sentiment_regime", sentiment.get("regime", "unknown"))))
    col4.metric("Active Strategies", int(alpha_os.get("active_strategy_count", 0) or 0))
    col5.metric("Health Score", f"{float(health.get('overall_health_score', 0.0)):.1%}")
    col6.metric("Valuation Coverage", f"{float(valuation_state.get('valuation_coverage_pct', 0.0)):.1f}%")


def _render_sidebar(bundle: dict[str, Any]) -> tuple[str, bool]:
    st.sidebar.markdown("## Dashboard Surface")
    section_counts = _section_counts()
    section = st.sidebar.radio(
        "Section",
        options=["Full Board"] + SECTION_ORDER,
        index=1,
        format_func=lambda value: value if value == "Full Board" else f"{value} ({section_counts.get(value, 0)})",
    )
    show_data_manifest = st.sidebar.toggle("Show Data Manifest", value=True)
    st.sidebar.markdown("---")
    st.sidebar.caption(f"Visualization modules: {len(VISUAL_SPECS)}")
    if st.sidebar.button("Refresh Dashboard Data", width="stretch"):
        st.cache_data.clear()
        st.cache_resource.clear()
        st.rerun()
    return section, show_data_manifest


def _render_data_manifest(bundle: dict[str, Any]) -> None:
    manifest = _frame(bundle, "pipeline_freshness")
    if manifest.empty:
        return
    st.subheader("Data Manifest")
    st.caption("Real persisted surfaces feeding the canonical dashboard.")
    st.dataframe(
        manifest.sort_values("age_hours", ascending=True),
        width="stretch",
        hide_index=True,
    )


def _render_visual(spec: VisualSpec, bundle: dict[str, Any]) -> bool:
    fig = spec.builder(bundle)
    if fig is None:
        st.info(f"{spec.title}: unavailable because the required real dataset is missing or incomplete.")
        return False
    st.markdown(f'<div class="ns-card-title">{spec.title}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="ns-card-subtitle">{spec.description}</div>', unsafe_allow_html=True)
    st.plotly_chart(
        fig,
        width="stretch",
        config={"displaylogo": False, "responsive": True},
        key=f"plotly_{spec.visual_id}",
    )
    return True


def _render_section(section: str, bundle: dict[str, Any]) -> tuple[int, int]:
    specs = [spec for spec in VISUAL_SPECS if spec.section == section]
    rendered = 0
    total = len(specs)
    st.markdown(f"### {section}")
    st.markdown('<div class="ns-section-note">Real-data visual surfaces only. Empty panels are hidden or marked unavailable instead of being backfilled with synthetic placeholders.</div>', unsafe_allow_html=True)
    for idx in range(0, len(specs), 2):
        cols = st.columns(2)
        for col, spec in zip(cols, specs[idx:idx + 2]):
            with col:
                rendered += 1 if _render_visual(spec, bundle) else 0
    return rendered, total


def _render_footer(bundle: dict[str, Any], rendered: int, total: int) -> None:
    st.markdown("---")
    st.caption(
        f"Rendered {rendered} of {total} visualization modules from real persisted artifacts. "
        "Unavailable panels are intentionally left empty when the underlying canonical dataset is missing or stale."
    )


def render_dashboard() -> None:
    _inject_styles()
    bundle = load_dashboard_bundle()
    section, show_data_manifest = _render_sidebar(bundle)

    _render_header(bundle)

    if show_data_manifest:
        with st.expander("Data Manifest & Freshness", expanded=False):
            _render_data_manifest(bundle)

    total_rendered = 0
    total_possible = 0

    if section == "Full Board":
        for item in SECTION_ORDER:
            rendered, total = _render_section(item, bundle)
            total_rendered += rendered
            total_possible += total
    else:
        total_rendered, total_possible = _render_section(section, bundle)

    _render_footer(bundle, total_rendered, total_possible)
