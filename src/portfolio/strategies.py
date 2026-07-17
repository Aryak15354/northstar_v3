#!/usr/bin/env python3
"""
Strategy Lab: real-data portfolio constructors for cross-comparison.

Strategies implemented:
- northstar: rank by daily scorer score snapshot
- equal_weight_top: top N by daily scorer score snapshot
- low_vol: lowest realized volatility among liquid names
- liquidity_weighted: weight by dollar volume among top scores
- mom_6m / mom_12m / mom_vol_adj: price-momentum variants
- quality_tilt: real fundamental quality using canonical annual/quarterly panels
- value_tilt: real value using price + EPS/FCF/book proxies
- sector_neutral_eq / sector_tilt_mom / risk_parity_vol
- regime_conditional / mom_3m_6m_12m / dual_momentum / quality_value_combo
- sentiment_trend: positive company sentiment with recency/conviction weighting
- alternative_event: recent bullish NSE alternative-data event aggregation
- ownership_accumulation: rising promoter/institutional ownership

Outputs: DataFrame with [ticker, Industry, weight]
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

try:
    import yaml
except Exception:  # pragma: no cover - optional dependency in some runtimes
    yaml = None

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.intelligence.temporal_guard import TemporalGuard
from src.intelligence.temporal_signal_engine import TemporalSignalEngine
from src.data.price_access import canonical_price_path

SCORES_FILE = PROJECT_ROOT / "data/processed/scores.parquet"
SCORE_HISTORY_DIR = PROJECT_ROOT / "data/processed/score_history"
UNIVERSE_FILE = PROJECT_ROOT / "universe/nifty500.csv"
# Canonical, point-in-time-safe price contract. Previously hardcoded to the
# legacy data/processed/prices.parquet, which is missing ~91 tickers
# (including delisted names -- a survivorship-bias risk for momentum/vol
# signals computed here) and has no availability_date/source columns.
PRICES_FILE = canonical_price_path()
STRATEGY_PORTFOLIOS_DIR = PROJECT_ROOT / "data/processed/strategy_portfolios"
ANNUAL_FUNDAMENTALS_FILE = PROJECT_ROOT / "data/canonical/fundamentals/fundamentals_annual_panel.parquet"
QUARTERLY_FUNDAMENTALS_FILE = PROJECT_ROOT / "data/canonical/fundamentals/fundamentals_quarterly_panel.parquet"
SHAREHOLDING_FILE = PROJECT_ROOT / "data/canonical/fundamentals/shareholding_quarterly.parquet"
SENTIMENT_FILE = PROJECT_ROOT / "data/canonical/sentiment/company_sentiment_daily.parquet"
ALT_EVENTS_FILE = PROJECT_ROOT / "data/canonical/alternative/nse_alternative_events.parquet"
RESEARCH_POLICY_FILE = PROJECT_ROOT / "config/research_policy.yaml"

# Ensure strategy portfolios directory exists
STRATEGY_PORTFOLIOS_DIR.mkdir(parents=True, exist_ok=True)
SCORE_HISTORY_DIR.mkdir(parents=True, exist_ok=True)

AVAILABLE_STRATEGIES = [
    "northstar",
    "equal_weight_top",
    "low_vol",
    "liquidity_weighted",
    "mom_6m",
    "mom_12m",
    "mom_vol_adj",
    "quality_tilt",
    "value_tilt",
    "sector_neutral_eq",
    "risk_parity_vol",
    "regime_conditional",
    "mom_3m_6m_12m",
    "dual_momentum",
    "quality_value_combo",
    "sector_tilt_mom",
    "sentiment_trend",
    "alternative_event",
    "ownership_accumulation",
    "vol_target_ovr",
]

DEFAULT_CFG = {
    "max_names": 30,
    "min_weight": 0.005,
    "max_weight_per_name": 0.08,
}

_DATA_CACHE: dict[str, pd.DataFrame | pd.Series | dict] = {}


def _normalize_date(value: object | None) -> pd.Timestamp | None:
    if value is None or str(value).strip() == "":
        return None
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return None
    return pd.Timestamp(ts).normalize()


def _normalize_ticker_value(value: object) -> str:
    ticker = str(value or "").strip().upper()
    if ticker and not ticker.endswith(".NS"):
        ticker = f"{ticker}.NS"
    return ticker


def _normalize_ticker_series(series: pd.Series) -> pd.Series:
    return series.map(_normalize_ticker_value)


def _zscore(series: pd.Series, clip_abs: float = 4.0) -> pd.Series:
    x = pd.to_numeric(series, errors="coerce")
    if x.notna().sum() <= 1:
        return pd.Series(np.nan, index=series.index, dtype=float)
    mu = float(x.mean())
    sigma = float(x.std())
    if not np.isfinite(sigma) or sigma <= 1e-12:
        return pd.Series(np.nan, index=series.index, dtype=float)
    out = (x - mu) / sigma
    return out.clip(lower=-clip_abs, upper=clip_abs).astype(float)


def _average_signals(signals: list[pd.Series], index: pd.Index) -> pd.Series:
    usable = []
    for signal in signals:
        if signal is None:
            continue
        s = pd.Series(signal, copy=False)
        s = pd.to_numeric(s, errors="coerce")
        if s.notna().sum() > 0:
            usable.append(s.reindex(index))
    if not usable:
        return pd.Series(np.nan, index=index, dtype=float)
    stacked = pd.concat(usable, axis=1)
    return stacked.mean(axis=1, skipna=True).astype(float)


def _read_parquet_cached(cache_key: str, path: Path) -> pd.DataFrame:
    cached = _DATA_CACHE.get(cache_key)
    if isinstance(cached, pd.DataFrame):
        return cached.copy()
    if not path.exists():
        frame = pd.DataFrame()
    else:
        frame = pd.read_parquet(path)
    _DATA_CACHE[cache_key] = frame.copy()
    return frame


def _load_research_policy_config() -> dict:
    cached = _DATA_CACHE.get("daily_scorer_config")
    if isinstance(cached, dict):
        return dict(cached)
    if yaml is None or not RESEARCH_POLICY_FILE.exists():
        _DATA_CACHE["daily_scorer_config"] = {}
        return {}
    try:
        payload = yaml.safe_load(RESEARCH_POLICY_FILE.read_text()) or {}
    except Exception:
        payload = {}
    if isinstance(payload, dict) and isinstance(payload.get("historical_research"), dict):
        hr = dict(payload.get("historical_research") or {})
        config = {
            "dataset": dict(hr.get("dataset", {}) or {}),
            "trainer": {},
            "regime": {
                "regime_labels_path": str(
                    hr.get("regime_labels_path", "data/processed/regime_labels.parquet")
                ),
            },
            "sentiment_overlay": {
                "sentiment_path": str(
                    hr.get("dataset", {}).get(
                        "sentiment_path",
                        "data/canonical/sentiment/company_sentiment_daily.parquet",
                    )
                ),
                "market_sentiment_path": str(
                    hr.get("dataset", {}).get(
                        "market_sentiment_path",
                        "data/canonical/sentiment/market_sentiment_daily.parquet",
                    )
                ),
                "macro_regime_path": str(
                    hr.get("dataset", {}).get(
                        "macro_features_path",
                        "data/canonical/macro/macro_regime_features.parquet",
                    )
                ),
            },
            "portfolio_mandate": str(hr.get("portfolio_mandate", "long_only") or "long_only"),
        }
    else:
        config = {}
    _DATA_CACHE["daily_scorer_config"] = dict(config)
    return config


def _normalize_scored_frame(frame: pd.DataFrame, as_of_date: pd.Timestamp | None) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame(columns=["ticker", "northstar_score", "score", "date", "Industry"])
    work = frame.copy()
    if "ticker" not in work.columns:
        return pd.DataFrame(columns=["ticker", "northstar_score", "score", "date", "Industry"])
    work["ticker"] = _normalize_ticker_series(work["ticker"].astype(str))
    if "date" in work.columns:
        work["date"] = pd.to_datetime(work["date"], errors="coerce").dt.normalize()
    elif as_of_date is not None:
        work["date"] = as_of_date
    else:
        work["date"] = pd.NaT

    score_col = next(
        (c for c in ["northstar_score", "score", "final_score", "model_score"] if c in work.columns),
        None,
    )
    if score_col is None:
        work["score"] = 0.0
    else:
        work["score"] = pd.to_numeric(work[score_col], errors="coerce").fillna(0.0)
    work["northstar_score"] = pd.to_numeric(
        work.get("northstar_score", work["score"]),
        errors="coerce",
    ).fillna(work["score"])

    if "Industry" not in work.columns:
        sec_col = next((c for c in ["sector", "Sector", "industry", "sector_name"] if c in work.columns), None)
        work["Industry"] = work[sec_col].astype(str) if sec_col else "Unknown"
    work["Industry"] = work["Industry"].fillna("Unknown").astype(str)

    keep_cols = [c for c in ["ticker", "date", "northstar_score", "score", "Industry"] if c in work.columns]
    if "sector" in work.columns and "sector" not in keep_cols:
        keep_cols.append("sector")
    work = work[keep_cols].copy()
    return work.drop_duplicates(["ticker", "date"], keep="last").reset_index(drop=True)


def _generate_score_snapshot(as_of_date: pd.Timestamp) -> pd.DataFrame:
    cache_key = f"score_snapshot:{as_of_date:%Y%m%d}"
    cached = _DATA_CACHE.get(cache_key)
    if isinstance(cached, pd.DataFrame):
        return cached.copy()

    snapshot_path = SCORE_HISTORY_DIR / f"scores_{as_of_date:%Y%m%d}.parquet"
    if snapshot_path.exists():
        out = _normalize_scored_frame(pd.read_parquet(snapshot_path), as_of_date)
        _DATA_CACHE[cache_key] = out.copy()
        return out

    from src.scoring.daily_scorer import DailyScorer

    cfg = _load_research_policy_config()
    cfg.setdefault("portfolio_mandate", "long_only")
    scorer = DailyScorer(cfg)
    scored = scorer.score(as_of_date)
    out = _normalize_scored_frame(scored, as_of_date)
    if not out.empty:
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        out.to_parquet(snapshot_path, index=False)
    _DATA_CACHE[cache_key] = out.copy()
    return out


def _load_scores(as_of_date: object | None = None) -> pd.DataFrame:
    dt = _normalize_date(as_of_date)
    if dt is not None:
        base = _normalize_scored_frame(_read_parquet_cached("scores", SCORES_FILE), None)
        latest_available = pd.DataFrame()
        if not base.empty and "date" in base.columns:
            dated = base[base["date"].notna()].copy()
            dated = dated[dated["date"] <= dt]
            if not dated.empty:
                latest_date = pd.to_datetime(dated["date"], errors="coerce").max()
                latest_available = dated[dated["date"] == latest_date].copy().reset_index(drop=True)
                if pd.notna(latest_date) and pd.Timestamp(latest_date).normalize() == dt:
                    return latest_available
        try:
            generated = _generate_score_snapshot(dt)
            if not generated.empty:
                return generated
        except Exception:
            pass
        if not latest_available.empty:
            return latest_available

    base = _normalize_scored_frame(_read_parquet_cached("scores", SCORES_FILE), None)
    if base.empty:
        return base
    if "date" in base.columns and base["date"].notna().any():
        latest_date = pd.to_datetime(base["date"], errors="coerce").max()
        base = base[base["date"] == latest_date].copy()
    return base.reset_index(drop=True)


def _load_prices_pivot() -> pd.DataFrame:
    cached = _DATA_CACHE.get("prices_pivot")
    if isinstance(cached, pd.DataFrame):
        return cached
    if not PRICES_FILE.exists():
        pivot = pd.DataFrame()
    else:
        px = pd.read_parquet(PRICES_FILE)
        date_col = next((c for c in ["Date", "date", "Timestamp", "timestamp"] if c in px.columns), None)
        ticker_col = next((c for c in ["ticker", "Ticker", "symbol", "Symbol"] if c in px.columns), None)
        close_col = next((c for c in ["Close", "close", "Adj Close", "adj_close"] if c in px.columns), None)
        if date_col and ticker_col and close_col:
            work = px[[date_col, ticker_col, close_col]].copy()
            work[date_col] = pd.to_datetime(work[date_col], errors="coerce").dt.normalize()
            work[ticker_col] = _normalize_ticker_series(work[ticker_col].astype(str))
            work[close_col] = pd.to_numeric(work[close_col], errors="coerce")
            work = work.dropna(subset=[date_col, ticker_col, close_col]).sort_values([date_col, ticker_col])
            pivot = work.pivot_table(
                index=date_col,
                columns=ticker_col,
                values=close_col,
                aggfunc="last",
            ).sort_index().ffill()
        else:
            pivot = pd.DataFrame()
    _DATA_CACHE["prices_pivot"] = pivot
    return pivot


def _load_latest_prices(as_of_date: object | None = None) -> pd.Series:
    pivot = _load_prices_pivot()
    if pivot.empty:
        return pd.Series(dtype=float)
    dt = _normalize_date(as_of_date)
    if dt is None:
        row = pivot.iloc[-1]
    else:
        subset = pivot[pivot.index <= dt]
        if subset.empty:
            return pd.Series(dtype=float)
        row = subset.iloc[-1]
    return pd.to_numeric(row, errors="coerce")


def _load_annual_fundamentals() -> pd.DataFrame:
    df = _read_parquet_cached("annual_fundamentals", ANNUAL_FUNDAMENTALS_FILE)
    if df.empty:
        return df
    work = df.copy()
    work["ticker"] = _normalize_ticker_series(work["ticker"].astype(str))
    for col in ["availability_date", "report_date"]:
        if col in work.columns:
            work[col] = pd.to_datetime(work[col], errors="coerce").dt.normalize()
    return work


def _load_quarterly_fundamentals() -> pd.DataFrame:
    df = _read_parquet_cached("quarterly_fundamentals", QUARTERLY_FUNDAMENTALS_FILE)
    if df.empty:
        return df
    work = df.copy()
    work["ticker"] = _normalize_ticker_series(work["ticker"].astype(str))
    for col in ["availability_date", "quarter_end"]:
        if col in work.columns:
            work[col] = pd.to_datetime(work[col], errors="coerce").dt.normalize()
    return work


def _load_shareholding() -> pd.DataFrame:
    df = _read_parquet_cached("shareholding", SHAREHOLDING_FILE)
    if df.empty:
        return df
    work = df.copy()
    work["ticker"] = _normalize_ticker_series(work["ticker"].astype(str))
    for col in ["availability_date", "quarter_end"]:
        if col in work.columns:
            work[col] = pd.to_datetime(work[col], errors="coerce").dt.normalize()
    return work


def _load_company_sentiment() -> pd.DataFrame:
    df = _read_parquet_cached("company_sentiment", SENTIMENT_FILE)
    if df.empty:
        return df
    work = df.copy()
    work["ticker"] = _normalize_ticker_series(work["ticker"].astype(str))
    for col in ["date", "availability_date"]:
        if col in work.columns:
            work[col] = pd.to_datetime(work[col], errors="coerce").dt.normalize()
    return work


def _load_alt_events() -> pd.DataFrame:
    df = _read_parquet_cached("alt_events", ALT_EVENTS_FILE)
    if df.empty:
        return df
    work = df.copy()
    work["ticker"] = _normalize_ticker_series(work["ticker"].astype(str))
    for col in ["event_date", "availability_date"]:
        if col in work.columns:
            work[col] = pd.to_datetime(work[col], errors="coerce").dt.normalize()
    return work


def _latest_available_by_ticker(
    df: pd.DataFrame,
    as_of_date: object | None,
    *,
    date_col: str = "availability_date",
    max_age_days: int | None = None,
) -> pd.DataFrame:
    if df.empty or date_col not in df.columns or "ticker" not in df.columns:
        return pd.DataFrame(columns=df.columns if not df.empty else [])
    dt = _normalize_date(as_of_date)
    work = df.copy()
    work[date_col] = pd.to_datetime(work[date_col], errors="coerce").dt.normalize()
    if dt is not None:
        work = work[work[date_col] <= dt].copy()
        if max_age_days is not None:
            work = work[work[date_col] >= (dt - pd.Timedelta(days=max_age_days))].copy()
    if work.empty:
        return work
    work = work.sort_values(["ticker", date_col], kind="mergesort")
    return work.groupby("ticker", as_index=False).tail(1).reset_index(drop=True)


def _latest_available_cached(
    cache_name: str,
    loader,
    as_of_date: object | None,
    *,
    date_col: str = "availability_date",
    max_age_days: int | None = None,
) -> pd.DataFrame:
    dt = _normalize_date(as_of_date)
    dt_token = dt.strftime("%Y%m%d") if dt is not None else "latest"
    age_token = "none" if max_age_days is None else str(int(max_age_days))
    cache_key = f"latest:{cache_name}:{dt_token}:{date_col}:{age_token}"
    cached = _DATA_CACHE.get(cache_key)
    if isinstance(cached, pd.DataFrame):
        return cached.copy()
    out = _latest_available_by_ticker(
        loader(),
        dt,
        date_col=date_col,
        max_age_days=max_age_days,
    )
    _DATA_CACHE[cache_key] = out.copy()
    return out


def _load_base_universe(as_of_date: object | None = None) -> pd.DataFrame:
    scores = _load_scores(as_of_date)
    if scores.empty:
        return _load_reference_universe(as_of_date)
    work = scores.copy()
    work["ticker"] = _normalize_ticker_series(work["ticker"].astype(str))
    if "Industry" not in work.columns:
        work["Industry"] = "Unknown"
    work["Industry"] = work["Industry"].fillna("Unknown").astype(str)

    # Enrich industry from reference universe when missing.
    try:
        unknown_mask = work["Industry"].eq("Unknown")
        if bool(unknown_mask.mean() > 0.5) and UNIVERSE_FILE.exists():
            uni = pd.read_csv(UNIVERSE_FILE)
            uni["ticker"] = _normalize_ticker_series(uni["Symbol"].astype(str))
            icol = next(
                (c for c in ["Industry", "Industry Name", "industry", "industry_name"] if c in uni.columns),
                None,
            )
            if icol:
                work = work.merge(
                    uni[["ticker", icol]].dropna().drop_duplicates("ticker"),
                    on="ticker",
                    how="left",
                    suffixes=("", "_u"),
                )
                enrich_col = f"{icol}_u" if f"{icol}_u" in work.columns else icol
                work["Industry"] = work["Industry"].where(
                    work["Industry"].ne("Unknown"),
                    work[enrich_col].fillna("Unknown").astype(str),
                )
                drop_cols = [f"{icol}_u"]
                if icol != "Industry":
                    drop_cols.append(icol)
                work = work.drop(columns=drop_cols, errors="ignore")
    except Exception:
        pass

    latest_prices = _load_latest_prices(as_of_date)
    if not latest_prices.empty:
        work["close"] = work["ticker"].map(latest_prices.to_dict())
    return work.drop_duplicates("ticker", keep="last").reset_index(drop=True)


def _load_reference_universe(as_of_date: object | None = None) -> pd.DataFrame:
    work = pd.DataFrame(columns=["ticker", "Industry"])
    try:
        if UNIVERSE_FILE.exists():
            uni = pd.read_csv(UNIVERSE_FILE)
            ticker_col = next((c for c in ["Symbol", "ticker", "Ticker", "symbol"] if c in uni.columns), None)
            industry_col = next(
                (c for c in ["Industry", "Industry Name", "industry", "industry_name"] if c in uni.columns),
                None,
            )
            if ticker_col is not None:
                work["ticker"] = _normalize_ticker_series(uni[ticker_col].astype(str))
                if industry_col is not None:
                    work["Industry"] = uni[industry_col].fillna("Unknown").astype(str)
                else:
                    work["Industry"] = "Unknown"
                work = work[work["ticker"].ne("")].drop_duplicates("ticker", keep="last").reset_index(drop=True)
    except Exception:
        work = pd.DataFrame(columns=["ticker", "Industry"])

    if work.empty:
        scores = _normalize_scored_frame(_read_parquet_cached("scores", SCORES_FILE), None)
        if not scores.empty:
            work = scores[["ticker", "Industry"]].drop_duplicates("ticker", keep="last").reset_index(drop=True)

    latest_prices = _load_latest_prices(as_of_date)
    if not work.empty and not latest_prices.empty:
        work["close"] = work["ticker"].map(latest_prices.to_dict())
    return work.reset_index(drop=True)


def _clip_and_floor(weights: pd.Series, cfg: dict) -> pd.Series:
    w = pd.to_numeric(weights, errors="coerce").fillna(0.0).clip(lower=0.0)
    if float(w.sum()) <= 0.0:
        return pd.Series(dtype=float)
    w = w / float(w.sum())
    w = w.clip(upper=cfg.get("max_weight_per_name", DEFAULT_CFG["max_weight_per_name"]))
    if float(w.sum()) <= 0.0:
        return pd.Series(dtype=float)
    w = w / float(w.sum())
    w = w.clip(lower=cfg.get("min_weight", DEFAULT_CFG["min_weight"]))
    return w / max(1e-12, float(w.sum()))


def _top_signal_portfolio(signal: pd.Series, base: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    if base.empty:
        return pd.DataFrame(columns=["ticker", "Industry", "weight"])
    work = base.set_index("ticker", drop=False).copy()
    work["signal"] = pd.to_numeric(signal.reindex(work.index), errors="coerce")
    work = work.dropna(subset=["signal"]).sort_values("signal", ascending=False)
    positives = work[work["signal"] > 0].copy()
    if not positives.empty:
        work = positives
    n = int(cfg.get("max_names", DEFAULT_CFG["max_names"]))
    work = work.head(max(1, n)).copy()
    if work.empty:
        return pd.DataFrame(columns=["ticker", "Industry", "weight"])
    ranks = work["signal"].rank(pct=True, method="average")
    weights = _clip_and_floor(ranks / max(1e-12, float(ranks.sum())), cfg)
    if weights.empty:
        return pd.DataFrame(columns=["ticker", "Industry", "weight"])
    out = work.loc[weights.index, ["ticker", "Industry"]].copy()
    out["weight"] = weights.values
    return out.reset_index(drop=True)


def _load_prices_slice(as_of_date: object | None = None) -> pd.DataFrame:
    pivot = _load_prices_pivot()
    dt = _normalize_date(as_of_date)
    if pivot.empty:
        return pivot
    if dt is None:
        return pivot
    return pivot[pivot.index <= dt]


def _momentum_weights(pivot: pd.DataFrame, window_days: int, universe: list[str], cfg: dict) -> pd.Series:
    if pivot.empty:
        return pd.Series(dtype=float)
    common = pivot.columns.intersection(universe)
    if len(common) == 0:
        return pd.Series(dtype=float)
    px = pivot[common].copy()
    tail = px.tail(window_days + 1)
    if len(tail) <= 1:
        return pd.Series(dtype=float)
    ret = tail.pct_change().dropna()
    if ret.empty:
        return pd.Series(dtype=float)
    mom = (1 + ret).prod() - 1
    mom = mom.sort_values(ascending=False).head(int(cfg.get("max_names", 30)))
    ranks = mom.rank(pct=True)
    return (ranks / max(1e-12, float(ranks.sum()))).astype(float)


def _volatility(pivot: pd.DataFrame, window_days: int, universe: list[str]) -> pd.Series:
    common = pivot.columns.intersection(universe)
    if len(common) == 0:
        return pd.Series(dtype=float)
    ret = pivot[common].pct_change().dropna()
    if ret.empty:
        return pd.Series(dtype=float)
    return ret.tail(window_days).std()


def _fundamental_snapshot(as_of_date: object | None = None) -> pd.DataFrame:
    dt = _normalize_date(as_of_date)
    cache_key = f"fundamental_snapshot:{dt.strftime('%Y%m%d') if dt is not None else 'latest'}"
    cached = _DATA_CACHE.get(cache_key)
    if isinstance(cached, pd.DataFrame):
        return cached.copy()
    base = _load_reference_universe(as_of_date).set_index("ticker", drop=False)
    annual = _latest_available_cached("annual_fundamentals", _load_annual_fundamentals, as_of_date, max_age_days=540)
    quarterly = _latest_available_cached("quarterly_fundamentals", _load_quarterly_fundamentals, as_of_date, max_age_days=200)
    share = _latest_available_cached("shareholding", _load_shareholding, as_of_date, max_age_days=200)
    if not annual.empty:
        annual = annual.set_index("ticker")
        cols = [
            "roe_pct",
            "roce_pct",
            "opm_pct",
            "operating_cash_flow",
            "net_income",
            "free_cash_flow",
            "equity",
            "native_shares_outstanding",
            "availability_date",
        ]
        cols = [c for c in cols if c in annual.columns]
        base = base.join(annual[cols], how="left", rsuffix="_annual")
    if not quarterly.empty:
        quarterly = quarterly.set_index("ticker")
        cols = ["eps", "eps_in_rs", "availability_date"]
        cols = [c for c in cols if c in quarterly.columns]
        base = base.join(quarterly[cols], how="left", rsuffix="_quarterly")
    if not share.empty:
        share = share.set_index("ticker")
        cols = [
            "promoter_pct",
            "institutional_pct",
            "promoter_pct_change_1q",
            "fii_pct_change_1q",
            "dii_pct_change_1q",
            "availability_date",
        ]
        cols = [c for c in cols if c in share.columns]
        base = base.join(share[cols], how="left", rsuffix="_share")
    out = base
    _DATA_CACHE[cache_key] = out.copy()
    return out


def save_strategy(name: str, df: pd.DataFrame) -> None:
    """Save strategy portfolio to persistent storage."""
    path = STRATEGY_PORTFOLIOS_DIR / f"{name}.parquet"
    df.to_parquet(path, index=False)
    print(f"   💾 Saved {name} strategy: {len(df)} positions")


def load_strategy_weights(strategy_name: str) -> pd.Series:
    """Load strategy weights from persistent storage."""
    path = STRATEGY_PORTFOLIOS_DIR / f"{strategy_name}.parquet"
    if path.exists():
        df = pd.read_parquet(path)
        if "ticker" in df.columns and "weight" in df.columns:
            return df.set_index("ticker")["weight"]
    return pd.Series(dtype=float)


def build_strategy_portfolio(
    strategy: str,
    cfg: dict | None = None,
    *,
    as_of_date: object | None = None,
) -> pd.DataFrame:
    cfg = {**DEFAULT_CFG, **(cfg or {})}
    strategy = str(strategy or "").strip()
    n = int(cfg.get("max_names", DEFAULT_CFG["max_names"]))
    scores_cache: pd.DataFrame | None = None
    prices_pivot_cache: pd.DataFrame | None = None

    def _scores() -> pd.DataFrame:
        nonlocal scores_cache
        if scores_cache is None:
            scores_cache = _load_base_universe(as_of_date).copy()
        return scores_cache.copy()

    def _prices() -> pd.DataFrame:
        nonlocal prices_pivot_cache
        if prices_pivot_cache is None:
            prices_pivot_cache = _load_prices_slice(as_of_date)
        return prices_pivot_cache

    if strategy == "northstar":
        scores = _scores()
        sel = scores.sort_values("northstar_score", ascending=False).head(n).copy()
        ranks = sel["northstar_score"].rank(pct=True)
        sel["weight"] = _clip_and_floor(ranks / max(1e-12, float(ranks.sum())), cfg)
    elif strategy == "equal_weight_top":
        scores = _scores()
        sel = scores.sort_values("northstar_score", ascending=False).head(n).copy()
        sel["weight"] = 1.0 / max(1, len(sel))
    elif strategy == "low_vol":
        scores = _scores()
        prices_pivot = _prices()
        universe = scores["ticker"].tolist()
        vol = _volatility(prices_pivot, 63, universe)
        if vol.empty:
            sel = scores.sort_values("northstar_score", ascending=False).head(n).copy()
            sel["weight"] = 1.0 / max(1, len(sel))
        else:
            vol = vol.sort_values().head(n)
            inv = 1.0 / (vol.replace(0.0, np.nan) + 1e-6)
            inv = inv.fillna(inv.median())
            sel = scores.set_index("ticker").reindex(vol.index).reset_index()
            sel["weight"] = _clip_and_floor(inv / max(1e-12, float(inv.sum())), cfg).values
    elif strategy == "liquidity_weighted":
        scores = _scores()
        prices_pivot = _prices()
        sel = scores.sort_values("northstar_score", ascending=False).head(n).copy()
        if not prices_pivot.empty:
            volume_frame = _read_parquet_cached("prices_frame", PRICES_FILE)
            ticker_col = next((c for c in ["ticker", "Ticker"] if c in volume_frame.columns), None)
            close_col = next((c for c in ["Close", "close"] if c in volume_frame.columns), None)
            volume_col = next((c for c in ["Volume", "volume"] if c in volume_frame.columns), None)
            date_col = next((c for c in ["Date", "date", "Timestamp", "timestamp"] if c in volume_frame.columns), None)
            if not volume_frame.empty and ticker_col and close_col and volume_col and date_col:
                work = volume_frame.copy()
                work[date_col] = pd.to_datetime(work[date_col], errors="coerce").dt.normalize()
                dt = _normalize_date(as_of_date)
                if dt is not None:
                    work = work[work[date_col] <= dt].copy()
                if not work.empty:
                    work["ticker"] = _normalize_ticker_series(work[ticker_col].astype(str))
                    work["dollar_volume"] = pd.to_numeric(work[close_col], errors="coerce") * pd.to_numeric(
                        work[volume_col], errors="coerce"
                    )
                    latest_dv = (
                        work.sort_values(date_col, kind="mergesort")
                        .groupby("ticker", as_index=False)
                        .tail(1)
                        .set_index("ticker")["dollar_volume"]
                    )
                    w = latest_dv.reindex(sel["ticker"]).fillna(0.0)
                    if float(w.sum()) > 0.0:
                        sel["weight"] = _clip_and_floor(w / float(w.sum()), cfg).values
                    else:
                        sel["weight"] = 1.0 / max(1, len(sel))
                else:
                    sel["weight"] = 1.0 / max(1, len(sel))
            else:
                sel["weight"] = 1.0 / max(1, len(sel))
        else:
            sel["weight"] = 1.0 / max(1, len(sel))
    elif strategy in ("mom_6m", "mom_12m", "mom_vol_adj"):
        scores = _scores()
        prices_pivot = _prices()
        universe = scores["ticker"].tolist()
        window = 126 if strategy == "mom_6m" else 252
        wraw = _momentum_weights(prices_pivot, window, universe, cfg)
        if wraw.empty:
            sel = scores.sort_values("northstar_score", ascending=False).head(n).copy()
            sel["weight"] = 1.0 / max(1, len(sel))
        else:
            if strategy == "mom_vol_adj":
                vol = _volatility(prices_pivot, 63, list(wraw.index))
                score = (wraw.reindex(vol.index).fillna(0.0) / (vol + 1e-6))
                w = _clip_and_floor(score / max(1e-12, float(score.sum())), cfg)
            else:
                w = _clip_and_floor(wraw, cfg)
            sel = scores.set_index("ticker").reindex(w.index).reset_index()
            sel["weight"] = w.values
    elif strategy == "mom_3m_6m_12m":
        scores = _scores()
        prices_pivot = _prices()
        universe = scores["ticker"].tolist()
        w3 = _momentum_weights(prices_pivot, 63, universe, cfg)
        w6 = _momentum_weights(prices_pivot, 126, universe, cfg)
        w12 = _momentum_weights(prices_pivot, 252, universe, cfg)
        union = w3.index.union(w6.index).union(w12.index)
        comp = (w3.reindex(union).fillna(0.0) + w6.reindex(union).fillna(0.0) + w12.reindex(union).fillna(0.0)) / 3.0
        comp = comp.sort_values(ascending=False).head(n)
        w = _clip_and_floor(comp / max(1e-12, float(comp.sum())), cfg)
        if w.empty:
            sel = scores.sort_values("northstar_score", ascending=False).head(n).copy()
            sel["weight"] = 1.0 / max(1, len(sel))
        else:
            sel = scores.set_index("ticker").reindex(w.index).reset_index()
            sel["weight"] = w.values
    elif strategy == "dual_momentum":
        scores = _scores()
        prices_pivot = _prices()
        universe = scores["ticker"].tolist()
        px = prices_pivot[prices_pivot.columns.intersection(universe)].copy() if not prices_pivot.empty else pd.DataFrame()
        if px.empty or len(px) < 253:
            return build_strategy_portfolio("mom_6m", cfg, as_of_date=as_of_date)
        mom12 = (px.tail(253).pct_change().dropna() + 1.0).prod() - 1.0
        abs_pos = mom12[mom12 > 0].index.tolist()
        if not abs_pos:
            return build_strategy_portfolio("value_tilt", cfg, as_of_date=as_of_date)
        w6 = _momentum_weights(prices_pivot, 126, abs_pos, cfg)
        w = _clip_and_floor(w6, cfg)
        if w.empty:
            return build_strategy_portfolio("mom_6m", cfg, as_of_date=as_of_date)
        sel = scores.set_index("ticker").reindex(w.index).reset_index()
        sel["weight"] = w.values
    elif strategy == "quality_tilt":
        snap = _fundamental_snapshot(as_of_date)
        cfo_to_income = pd.to_numeric(snap.get("operating_cash_flow"), errors="coerce") / (
            pd.to_numeric(snap.get("net_income"), errors="coerce").abs().clip(lower=1.0)
        )
        quality_score = _average_signals(
            [
                _zscore(snap.get("roe_pct", pd.Series(dtype=float))),
                _zscore(snap.get("roce_pct", pd.Series(dtype=float))),
                _zscore(snap.get("opm_pct", pd.Series(dtype=float))),
                _zscore(cfo_to_income.clip(lower=-5.0, upper=5.0)),
                _zscore(snap.get("institutional_pct", pd.Series(dtype=float))),
            ],
            snap.index,
        )
        sel = _top_signal_portfolio(quality_score, snap.reset_index(drop=True), cfg)
        if sel.empty:
            return build_strategy_portfolio("northstar", cfg, as_of_date=as_of_date)
    elif strategy == "value_tilt":
        snap = _fundamental_snapshot(as_of_date)
        price = pd.to_numeric(snap.get("close", pd.Series(index=snap.index, dtype=float)), errors="coerce")
        eps = pd.to_numeric(
            snap.get("eps", pd.Series(index=snap.index, dtype=float)),
            errors="coerce",
        ).fillna(
            pd.to_numeric(snap.get("eps_in_rs", pd.Series(index=snap.index, dtype=float)), errors="coerce")
        )
        earnings_yield = (eps * 4.0) / price.replace(0.0, np.nan)
        shares = pd.to_numeric(
            snap.get("native_shares_outstanding", pd.Series(index=snap.index, dtype=float)),
            errors="coerce",
        )
        market_cap = price * shares
        book_to_price = pd.to_numeric(
            snap.get("equity", pd.Series(index=snap.index, dtype=float)),
            errors="coerce",
        ) / market_cap.replace(0.0, np.nan)
        fcf_yield = pd.to_numeric(
            snap.get("free_cash_flow", pd.Series(index=snap.index, dtype=float)),
            errors="coerce",
        ) / market_cap.replace(0.0, np.nan)
        value_score = _average_signals(
            [
                _zscore(earnings_yield.clip(lower=-1.0, upper=1.0)),
                _zscore(book_to_price.clip(lower=-1.0, upper=3.0)),
                _zscore(fcf_yield.clip(lower=-1.0, upper=1.0)),
            ],
            snap.index,
        )
        sel = _top_signal_portfolio(value_score, snap.reset_index(drop=True), cfg)
        if sel.empty:
            return build_strategy_portfolio("northstar", cfg, as_of_date=as_of_date)
    elif strategy == "quality_value_combo":
        snap = _fundamental_snapshot(as_of_date)
        price = pd.to_numeric(snap.get("close", pd.Series(index=snap.index, dtype=float)), errors="coerce")
        eps = pd.to_numeric(
            snap.get("eps", pd.Series(index=snap.index, dtype=float)),
            errors="coerce",
        ).fillna(
            pd.to_numeric(snap.get("eps_in_rs", pd.Series(index=snap.index, dtype=float)), errors="coerce")
        )
        earnings_yield = (eps * 4.0) / price.replace(0.0, np.nan)
        shares = pd.to_numeric(
            snap.get("native_shares_outstanding", pd.Series(index=snap.index, dtype=float)),
            errors="coerce",
        )
        market_cap = price * shares
        book_to_price = pd.to_numeric(
            snap.get("equity", pd.Series(index=snap.index, dtype=float)),
            errors="coerce",
        ) / market_cap.replace(0.0, np.nan)
        fcf_yield = pd.to_numeric(
            snap.get("free_cash_flow", pd.Series(index=snap.index, dtype=float)),
            errors="coerce",
        ) / market_cap.replace(0.0, np.nan)
        cfo_to_income = pd.to_numeric(snap.get("operating_cash_flow"), errors="coerce") / (
            pd.to_numeric(snap.get("net_income"), errors="coerce").abs().clip(lower=1.0)
        )
        quality_score = _average_signals(
            [
                _zscore(snap.get("roe_pct", pd.Series(dtype=float))),
                _zscore(snap.get("roce_pct", pd.Series(dtype=float))),
                _zscore(cfo_to_income.clip(lower=-5.0, upper=5.0)),
            ],
            snap.index,
        )
        value_score = _average_signals(
            [
                _zscore(earnings_yield.clip(lower=-1.0, upper=1.0)),
                _zscore(book_to_price.clip(lower=-1.0, upper=3.0)),
                _zscore(fcf_yield.clip(lower=-1.0, upper=1.0)),
            ],
            snap.index,
        )
        combo = _average_signals([quality_score, value_score], snap.index)
        sel = _top_signal_portfolio(combo, snap.reset_index(drop=True), cfg)
        if sel.empty:
            return build_strategy_portfolio("quality_tilt", cfg, as_of_date=as_of_date)
    elif strategy == "sector_neutral_eq":
        scores = _scores()
        base = scores.sort_values("northstar_score", ascending=False).head(5 * n).copy()
        sec_score = base.groupby("Industry")["northstar_score"].sum().sort_values(ascending=False)
        top_secs = set(sec_score.head(5).index.tolist())
        sel = base[base["Industry"].isin(top_secs)].copy().head(n)
        sel["weight"] = 1.0 / max(1, len(sel))
    elif strategy == "risk_parity_vol":
        scores = _scores()
        prices_pivot = _prices()
        universe = scores["ticker"].tolist()
        vol = _volatility(prices_pivot, 63, universe)
        if vol.empty:
            return build_strategy_portfolio("low_vol", cfg, as_of_date=as_of_date)
        base = vol.sort_values().head(n)
        inv = 1.0 / (base.replace(0.0, np.nan) + 1e-6)
        inv = inv.fillna(inv.median())
        sel = scores.set_index("ticker").reindex(base.index).reset_index()
        sel["weight"] = _clip_and_floor(inv / max(1e-12, float(inv.sum())), cfg).values
    elif strategy == "regime_conditional":
        regime = "neutral"
        try:
            market_state = pd.read_parquet(PROJECT_ROOT / "data/processed/market_state.parquet")
            if not market_state.empty:
                date_col = "date" if "date" in market_state.columns else ("Date" if "Date" in market_state.columns else None)
                if date_col is not None:
                    market_state[date_col] = pd.to_datetime(market_state[date_col], errors="coerce").dt.normalize()
                    dt = _normalize_date(as_of_date)
                    if dt is not None:
                        market_state = market_state[market_state[date_col] <= dt].copy()
                if not market_state.empty:
                    regime = str(market_state.iloc[-1].get("macro_regime", "neutral")).lower()
        except Exception:
            pass
        if regime in ("boom", "expansion", "late-expansion", "recovery"):
            return build_strategy_portfolio("mom_6m", cfg, as_of_date=as_of_date)
        return build_strategy_portfolio("value_tilt", cfg, as_of_date=as_of_date)
    elif strategy == "sector_tilt_mom":
        scores = _scores()
        prices_pivot = _prices()
        base = scores.sort_values("northstar_score", ascending=False).head(5 * n).copy()
        top_secs = set(
            base.groupby("Industry")["northstar_score"].sum().sort_values(ascending=False).head(5).index.tolist()
        )
        tickers = base[base["Industry"].isin(top_secs)]["ticker"].tolist()
        wraw = _momentum_weights(prices_pivot, 126, tickers, cfg)
        if wraw.empty:
            return build_strategy_portfolio("mom_6m", cfg, as_of_date=as_of_date)
        w = _clip_and_floor(wraw, cfg)
        sel = scores.set_index("ticker").reindex(w.index).reset_index()
        sel["weight"] = w.values
    elif strategy == "sentiment_trend":
        base = _load_reference_universe(as_of_date)
        sentiment = _latest_available_cached("company_sentiment", _load_company_sentiment, as_of_date, date_col="availability_date", max_age_days=21)
        if sentiment.empty:
            return pd.DataFrame(columns=["ticker", "Industry", "weight"])
        sentiment = sentiment.set_index("ticker")
        signal = (
            pd.to_numeric(sentiment.get("sentiment_polarity"), errors="coerce").fillna(0.0)
            * pd.to_numeric(sentiment.get("sentiment_conviction"), errors="coerce").fillna(0.0).clip(lower=0.0)
            * (1.0 - pd.to_numeric(sentiment.get("sentiment_uncertainty"), errors="coerce").fillna(1.0).clip(0.0, 1.0))
            * np.log1p(pd.to_numeric(sentiment.get("news_volume"), errors="coerce").fillna(0.0))
        )
        sel = _top_signal_portfolio(signal, base, cfg)
        if sel.empty:
            return pd.DataFrame(columns=["ticker", "Industry", "weight"])
    elif strategy == "alternative_event":
        base = _load_reference_universe(as_of_date)
        events = _load_alt_events()
        dt = _normalize_date(as_of_date)
        if events.empty or dt is None:
            return pd.DataFrame(columns=["ticker", "Industry", "weight"])
        recent = events[
            (events["availability_date"] <= dt)
            & (events["event_date"] >= (dt - pd.Timedelta(days=30)))
        ].copy()
        if recent.empty:
            return pd.DataFrame(columns=["ticker", "Industry", "weight"])
        days_old = (dt - recent["availability_date"]).dt.days.clip(lower=0)
        decay = np.exp(-days_old / 10.0)
        signal = (
            pd.to_numeric(recent.get("signal_strength"), errors="coerce").fillna(0.0)
            * decay.astype(float)
        )
        agg = signal.groupby(recent["ticker"]).sum()
        sel = _top_signal_portfolio(agg, base, cfg)
        if sel.empty:
            return pd.DataFrame(columns=["ticker", "Industry", "weight"])
    elif strategy == "ownership_accumulation":
        base = _load_reference_universe(as_of_date)
        share = _latest_available_cached("shareholding", _load_shareholding, as_of_date, max_age_days=200)
        if share.empty:
            return pd.DataFrame(columns=["ticker", "Industry", "weight"])
        share = share.set_index("ticker")
        accumulation = _average_signals(
            [
                _zscore(share.get("promoter_pct_change_1q", pd.Series(dtype=float))),
                _zscore(share.get("fii_pct_change_1q", pd.Series(dtype=float))),
                _zscore(share.get("dii_pct_change_1q", pd.Series(dtype=float))),
                _zscore(share.get("institutional_pct", pd.Series(dtype=float))),
            ],
            share.index,
        )
        sel = _top_signal_portfolio(accumulation, base, cfg)
        if sel.empty:
            return pd.DataFrame(columns=["ticker", "Industry", "weight"])
    elif strategy == "vol_target_ovr":
        sel = build_strategy_portfolio("northstar", cfg, as_of_date=as_of_date).copy()
    else:
        raise ValueError(f"Unknown strategy: {strategy}")

    out = sel[["ticker", "Industry", "weight"]].copy()
    out["weight"] = pd.to_numeric(out["weight"], errors="coerce").fillna(0.0).astype(float)
    out = out[out["weight"] > 0.0].copy()
    if out.empty:
        return out
    out["weight"] = out["weight"] / max(1e-12, float(out["weight"].sum()))
    return out.reset_index(drop=True)


def compare_strategies(
    strategies: list[str],
    cfg: dict | None = None,
    *,
    as_of_date: object | None = None,
) -> dict:
    """Compare strategies and save them to persistent storage."""
    out = {}
    for name in strategies:
        try:
            portfolio = build_strategy_portfolio(name, cfg, as_of_date=as_of_date)
            out[name] = portfolio
            save_strategy(name, portfolio)
        except Exception as e:
            out[name] = pd.DataFrame({"error": [str(e)]})
    return out


def generate_all_strategies(*, as_of_date: object | None = None):
    """Generate and save all available strategies."""
    dt = _normalize_date(as_of_date)
    if dt is None:
        dt = pd.Timestamp.today().normalize()

    print("🧪 GENERATING ALL STRATEGY PORTFOLIOS")
    print("=" * 50)

    results = compare_strategies(AVAILABLE_STRATEGIES, as_of_date=dt)

    print(f"\n✅ Generated {len([k for k, v in results.items() if not v.empty])} strategies")
    print(f"📁 Saved to: {STRATEGY_PORTFOLIOS_DIR}")

    return results


if __name__ == "__main__":
    generate_all_strategies()


# =========================== TEMPORAL STRATEGY WRAPPER ===========================

class TemporalStrategyWrapper:
    """
    Wrapper that makes any strategy temporal-safe.

    This ensures all strategies use temporal signals and respect point-in-time constraints.
    """

    def __init__(self, original_strategy):
        self.original_strategy = original_strategy
        self.signal_engine = TemporalSignalEngine()
        self.guard = TemporalGuard()

    def generate_signals(self, symbol, current_time):
        """Generate temporal-safe signals."""
        return self.signal_engine.generate_all_signals(symbol, current_time)

    def execute_strategy(self, symbol, current_time, *args, **kwargs):
        """Execute strategy with temporal protection."""
        signals = self.generate_signals(symbol, current_time)
        kwargs["temporal_signals"] = signals
        kwargs["current_time"] = current_time
        return self.original_strategy.execute(symbol, *args, **kwargs)


# =========================== TEMPORAL STRATEGY FACTORY ===========================

def make_temporal_safe(strategy_class):
    """Factory function to make any strategy temporal-safe."""

    class TemporalSafeStrategy(strategy_class):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.signal_engine = TemporalSignalEngine()
            self.guard = TemporalGuard()

        def get_signals(self, symbol, current_time):
            """Override to use temporal signals."""
            return self.signal_engine.generate_all_signals(symbol, current_time)

    return TemporalSafeStrategy
