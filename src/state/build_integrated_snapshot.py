#!/usr/bin/env python3
"""
Build a unified daily integrated state snapshot for the V3 dashboard.

The output artifact is:
    data/integrated/integrated_state_snapshot.parquet

Design goals:
1) One coherent daily table powering cross-layer dashboard views.
2) Graceful degradation when optional artifacts are missing.
3) Lightweight execution suitable for constrained environments.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Sequence

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "data/integrated/integrated_state_snapshot.parquet"


SCHEMA_COLUMNS = [
    "date",
    "regime_label",
    "regime_confidence",
    "regime_entropy",
    "risk_pressure_index",
    "volatility_z",
    "correlation_z",
    "macro_sentiment_z",
    "fii_flow_z",
    "inflation_z",
    "policy_stance_score",
    "belief_strength",
    "belief_momentum",
    "regret_score",
    "valuation_gap_z",
    "opportunity_score_mean",
    "narrative_shock_intensity",
    "belief_news_divergence",
    "gross_exposure",
    "net_exposure",
    "portfolio_beta",
    "sector_concentration_index",
    "edge_health_mean",
    "half_life_mean",
    "exit_risk_mean",
    "cash_weight",
    "drawdown_probability_30d",
    "crisis_probability",
    "liquidity_stress_index",
    "correlation_spike_flag",
    "survival_core_active",
    "fallback_ladder_level",
    "nav",
    "benchmark_nav",
    "active_return",
    "rolling_sharpe_21d",
    "rolling_vol_21d",
    "max_drawdown_trailing",
    "macro_news_sentiment",
    "sector_news_dispersion",
    "event_intensity_mean",
    "policy_shock_flag",
    "top_sector_sentiment",
    "top_negative_sector",
]


STRING_COLUMNS = {"regime_label", "top_sector_sentiment", "top_negative_sector"}
INT_COLUMNS = {
    "correlation_spike_flag",
    "survival_core_active",
    "fallback_ladder_level",
    "policy_shock_flag",
}


def _safe_read_parquet(path: Path, columns: Optional[Sequence[str]] = None) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        if columns:
            return pd.read_parquet(path, columns=list(columns))
        return pd.read_parquet(path)
    except Exception:
        return pd.DataFrame()


def _safe_read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _to_date(values: Any) -> pd.Series:
    ts = pd.to_datetime(values, errors="coerce", utc=True)
    if isinstance(ts, pd.Series):
        return ts.dt.tz_convert(None).dt.normalize()
    idx = pd.DatetimeIndex(ts)
    return pd.Series(idx.tz_convert(None).normalize())


def _attach_date_column(df: pd.DataFrame, candidates: Sequence[str]) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame(columns=["date"])
    out = df.copy()
    date_col = next((c for c in candidates if c in out.columns), None)
    if date_col is not None:
        out["date"] = _to_date(out[date_col])
    elif isinstance(out.index, pd.DatetimeIndex):
        out = out.reset_index(drop=False)
        index_col = out.columns[0]
        out["date"] = _to_date(out[index_col])
    else:
        return pd.DataFrame(columns=["date"])
    out = out.dropna(subset=["date"]).sort_values("date")
    return out


def _zscore(series: pd.Series) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce")
    if s.notna().sum() < 2:
        return pd.Series(np.zeros(len(s)), index=s.index, dtype=float)
    mu = float(s.mean())
    sd = float(s.std(ddof=0))
    if not np.isfinite(sd) or sd <= 1e-12:
        return pd.Series(np.zeros(len(s)), index=s.index, dtype=float)
    return (s - mu) / sd


def _binary_entropy(prob: pd.Series) -> pd.Series:
    """Shannon entropy for Bernoulli probability series, normalized to [0, 1]."""
    p = pd.to_numeric(prob, errors="coerce").clip(lower=1e-6, upper=1 - 1e-6)
    h = -(p * np.log(p) + (1.0 - p) * np.log(1.0 - p))
    return h / np.log(2.0)


def _merge_on_date(base: pd.DataFrame, frame: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return base
    f = frame.copy()
    if "date" not in f.columns:
        return base
    f["date"] = _to_date(f["date"])
    f = f.dropna(subset=["date"]).sort_values("date")
    f = f.drop_duplicates(subset=["date"], keep="last")
    overlap = [c for c in f.columns if c != "date" and c in base.columns]
    if not overlap:
        return base.merge(f, on="date", how="left")

    rename_map = {c: f"{c}__new" for c in overlap}
    f = f.rename(columns=rename_map)
    merged = base.merge(f, on="date", how="left")
    for col in overlap:
        new_col = rename_map[col]
        if col in merged.columns and new_col in merged.columns:
            merged[col] = merged[col].combine_first(merged[new_col])
        elif new_col in merged.columns:
            merged[col] = merged[new_col]
        if new_col in merged.columns:
            merged = merged.drop(columns=[new_col])
    return merged


def _first_present_col(df: pd.DataFrame, candidates: Sequence[str]) -> Optional[str]:
    return next((c for c in candidates if c in df.columns), None)


def _collect_dates(df: pd.DataFrame, candidates: Sequence[str]) -> pd.Series:
    d = _attach_date_column(df, candidates)
    if d.empty or "date" not in d.columns:
        return pd.Series(dtype="datetime64[ns]")
    return d["date"].dropna()


def _policy_stance_score(policy: Dict[str, Any]) -> float:
    stance = str(policy.get("rbi_stance", "") or "").strip().lower()
    if "neutral" in stance and "hawkish" in stance:
        return -0.5
    if "neutral" in stance and "dovish" in stance:
        return 0.5
    if "hawkish" in stance or "tightening" in stance:
        return -1.0
    if "dovish" in stance or "accommodative" in stance:
        return 1.0
    return 0.0


def _policy_shock_flag(policy: Dict[str, Any]) -> int:
    stance = str(policy.get("rbi_stance", "") or "").strip().lower()
    fiscal = str(policy.get("fiscal_tone", "") or "").strip().lower()
    flags = policy.get("regulatory_stress_flags", [])
    if isinstance(flags, (list, tuple)) and len(flags) > 0:
        return 1
    hot_words = ("emergency", "crisis", "freeze", "ban", "shock")
    return int(any(w in stance or w in fiscal for w in hot_words))


def _build_fii_flow_proxy(
    root: Path,
    sector_flows: pd.DataFrame,
) -> pd.DataFrame:
    candidate_paths = [
        root / "data/processed/fii_flows.parquet",
        root / "data/processed/fii_flow.parquet",
        root / "data/processed/fii_dii_flows.parquet",
    ]
    for path in candidate_paths:
        df = _safe_read_parquet(path)
        if df.empty:
            continue
        d = _attach_date_column(df, ["date", "Date", "timestamp"])
        if d.empty:
            continue
        flow_col = None
        for col in d.columns:
            c = col.lower()
            if "fii" in c and "flow" in c:
                flow_col = col
                break
        if flow_col is None:
            flow_col = _first_present_col(d, ["flow", "net_flow", "capital_flow"])
        if flow_col is None:
            continue
        d["flow_value"] = pd.to_numeric(d[flow_col], errors="coerce")
        d = d.dropna(subset=["date", "flow_value"])
        if d.empty:
            continue
        out = d.groupby("date", as_index=False)["flow_value"].mean()
        out["fii_flow_z"] = _zscore(out["flow_value"])
        return out[["date", "fii_flow_z"]]

    sf = _attach_date_column(sector_flows, ["Date", "date", "timestamp"])
    if sf.empty:
        return pd.DataFrame(columns=["date", "fii_flow_z"])
    flow_col = _first_present_col(sf, ["capital_flow", "flow_strength", "flow_10d", "flow_30d"])
    if flow_col is None:
        return pd.DataFrame(columns=["date", "fii_flow_z"])
    sf["flow_value"] = pd.to_numeric(sf[flow_col], errors="coerce")
    sf = sf.dropna(subset=["date", "flow_value"])
    if sf.empty:
        return pd.DataFrame(columns=["date", "fii_flow_z"])
    out = sf.groupby("date", as_index=False)["flow_value"].mean()
    out["fii_flow_z"] = _zscore(out["flow_value"])
    return out[["date", "fii_flow_z"]]


def _as_int_flag(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0).round().astype(int)


def _compute_perf_frame(pnl: pd.DataFrame, nifty: pd.DataFrame) -> pd.DataFrame:
    p = _attach_date_column(pnl, ["Date", "date", "timestamp"])
    if p.empty:
        return pd.DataFrame(columns=["date"])
    eq_col = _first_present_col(p, ["Equity", "equity", "portfolio_value", "value", "nav", "total_equity"])
    if eq_col is None:
        return pd.DataFrame(columns=["date"])

    p["equity"] = pd.to_numeric(p[eq_col], errors="coerce")
    p = p.dropna(subset=["date", "equity"]).sort_values("date")
    if p.empty:
        return pd.DataFrame(columns=["date"])
    p = p.groupby("date", as_index=False)["equity"].last()
    p["ret_p"] = p["equity"].pct_change()

    b = _attach_date_column(nifty, ["Date", "date", "timestamp"])
    if b.empty:
        perf = p.rename(columns={"equity": "nav"})[["date", "nav"]].copy()
        perf["benchmark_nav"] = np.nan
        perf["active_return"] = np.nan
        perf["rolling_sharpe_21d"] = np.nan
        perf["rolling_vol_21d"] = np.nan
        perf["max_drawdown_trailing"] = np.nan
        perf["portfolio_beta"] = np.nan
        perf["drawdown_probability_30d_perf"] = np.nan
        return perf

    close_col = _first_present_col(b, ["close", "Close", "adj_close", "Adj Close"])
    if close_col is None:
        perf = p.rename(columns={"equity": "nav"})[["date", "nav"]].copy()
        perf["benchmark_nav"] = np.nan
        perf["active_return"] = np.nan
        perf["rolling_sharpe_21d"] = np.nan
        perf["rolling_vol_21d"] = np.nan
        perf["max_drawdown_trailing"] = np.nan
        perf["portfolio_beta"] = np.nan
        perf["drawdown_probability_30d_perf"] = np.nan
        return perf

    b["close"] = pd.to_numeric(b[close_col], errors="coerce")
    b = b.dropna(subset=["date", "close"]).sort_values("date")
    if b.empty:
        perf = p.rename(columns={"equity": "nav"})[["date", "nav"]].copy()
        perf["benchmark_nav"] = np.nan
        perf["active_return"] = np.nan
        perf["rolling_sharpe_21d"] = np.nan
        perf["rolling_vol_21d"] = np.nan
        perf["max_drawdown_trailing"] = np.nan
        perf["portfolio_beta"] = np.nan
        perf["drawdown_probability_30d_perf"] = np.nan
        return perf
    b = b.groupby("date", as_index=False)["close"].last()
    b["ret_b"] = b["close"].pct_change()

    m = p.merge(b, on="date", how="inner").sort_values("date")
    if m.empty:
        perf = p.rename(columns={"equity": "nav"})[["date", "nav"]].copy()
        perf["benchmark_nav"] = np.nan
        perf["active_return"] = np.nan
        perf["rolling_sharpe_21d"] = np.nan
        perf["rolling_vol_21d"] = np.nan
        perf["max_drawdown_trailing"] = np.nan
        perf["portfolio_beta"] = np.nan
        perf["drawdown_probability_30d_perf"] = np.nan
        return perf

    nav0 = float(m["equity"].iloc[0]) if float(m["equity"].iloc[0]) != 0 else 1.0
    bench0 = float(m["close"].iloc[0]) if float(m["close"].iloc[0]) != 0 else 1.0
    m["nav"] = m["equity"]
    m["benchmark_nav"] = (m["close"] / bench0) * nav0
    m["active_return"] = m["ret_p"] - m["ret_b"]

    ret_p = pd.to_numeric(m["ret_p"], errors="coerce")
    ret_b = pd.to_numeric(m["ret_b"], errors="coerce")
    roll_mean = ret_p.rolling(21, min_periods=5).mean()
    roll_std = ret_p.rolling(21, min_periods=5).std()
    m["rolling_sharpe_21d"] = np.sqrt(252.0) * roll_mean / (roll_std + 1e-9)
    m["rolling_vol_21d"] = np.sqrt(252.0) * roll_std

    drawdown = m["nav"] / m["nav"].cummax() - 1.0
    m["max_drawdown_trailing"] = drawdown.rolling(252, min_periods=1).min()

    cov = ret_p.rolling(21, min_periods=8).cov(ret_b)
    var_b = ret_b.rolling(21, min_periods=8).var()
    m["portfolio_beta"] = cov / (var_b + 1e-9)

    mu30 = ret_p.rolling(21, min_periods=8).mean() * 30.0
    sigma30 = ret_p.rolling(21, min_periods=8).std() * np.sqrt(30.0)
    z = (-0.10 - mu30) / (sigma30 + 1e-9)
    m["drawdown_probability_30d_perf"] = z.apply(
        lambda x: 0.5 * (1.0 + math.erf(float(x) / np.sqrt(2.0))) if np.isfinite(x) else np.nan
    )

    return m[
        [
            "date",
            "nav",
            "benchmark_nav",
            "active_return",
            "rolling_sharpe_21d",
            "rolling_vol_21d",
            "max_drawdown_trailing",
            "portfolio_beta",
            "drawdown_probability_30d_perf",
        ]
    ].copy()


def _fallback_dates(
    frames: Iterable[tuple[pd.DataFrame, Sequence[str]]],
    *,
    lookback_days: int,
) -> pd.DatetimeIndex:
    all_dates: list[pd.Timestamp] = []
    for df, cols in frames:
        s = _collect_dates(df, cols)
        if not s.empty:
            all_dates.extend(pd.to_datetime(s, errors="coerce").dropna().tolist())
    if all_dates:
        end_date = pd.Timestamp(max(all_dates)).normalize()
        start_date = pd.Timestamp(min(all_dates)).normalize()
    else:
        end_date = pd.Timestamp.utcnow().tz_localize(None).normalize()
        start_date = end_date - pd.Timedelta(days=365)
    if lookback_days > 0:
        start_date = max(start_date, end_date - pd.Timedelta(days=int(lookback_days)))
    if end_date < start_date:
        end_date = start_date
    return pd.date_range(start=start_date, end=end_date, freq="D")


def build_integrated_snapshot(
    output_path: Path = DEFAULT_OUTPUT_PATH,
    *,
    lookback_days: int = 3650,
) -> pd.DataFrame:
    root = PROJECT_ROOT

    market_regime = _safe_read_parquet(root / "data/processed/market_regime.parquet")
    macro_factors = _safe_read_parquet(root / "data/processed/macro_factors_v2.parquet")
    if macro_factors.empty:
        macro_factors = _safe_read_parquet(root / "data/processed/macro_factors.parquet")
    sector_flows = _safe_read_parquet(root / "data/processed/sector_flows.parquet")
    strategy_beliefs = _safe_read_parquet(root / "data/processed/strategy_beliefs.parquet")
    belief_evolution = _safe_read_json(root / "data/processed/belief_evolution.json")
    strategy_regret = _safe_read_parquet(root / "data/processed/strategy_regret.parquet")
    valuation_posterior = _safe_read_parquet(root / "data/processed/valuation_posterior.parquet")
    opportunity_surface = _safe_read_parquet(root / "data/processed/opportunity_surface.parquet")
    narrative_events = _safe_read_parquet(root / "data/processed/narrative_events.parquet")
    allocation_history = _safe_read_parquet(root / "data/processed/allocation_history.parquet")
    portfolio_weights = _safe_read_parquet(root / "data/processed/portfolio_weights.parquet")
    edge_half_life = _safe_read_parquet(root / "data/processed/edge_half_life.parquet")
    liquidity_risk = _safe_read_parquet(root / "data/processed/liquidity_risk.parquet")
    alpha_os = _safe_read_parquet(root / "data/processed/alpha_os_timeseries.parquet")
    market_state = _safe_read_parquet(root / "data/processed/market_state.parquet")
    intelligent_market_state = _safe_read_parquet(root / "data/processed/intelligent_market_state.parquet")
    narrative_state = _safe_read_parquet(root / "data/processed/narrative_state.parquet")
    pnl = _safe_read_parquet(root / "data/portfolio/pnl_on_paper.parquet")
    nifty = _safe_read_parquet(root / "data/processed/nifty.parquet")
    sentiment_market = _safe_read_parquet(root / "data/sentiment/v3/market_sentiment_india.parquet")
    sector_narratives = _safe_read_parquet(root / "data/sentiment/v3/sector_narratives.parquet")
    event_company_impact = _safe_read_parquet(root / "data/sentiment/v3/event_company_impact.parquet")
    policy_context = _safe_read_json(root / "data/sentiment/v3/policy_context.json")
    regime_feed = _safe_read_json(root / "data/processed/regime_intelligence_feed.json")
    portfolio_analytics = _safe_read_json(root / "data/processed/portfolio_analytics.json")

    calendar = _fallback_dates(
        [
            (market_regime, ("Date", "date")),
            (strategy_beliefs, ("date", "Date", "timestamp")),
            (alpha_os, ("timestamp", "date")),
            (pnl, ("Date", "date", "timestamp")),
            (nifty, ("Date", "date", "timestamp")),
            (sentiment_market, ("date", "Date", "timestamp")),
            (valuation_posterior, ("date", "Date", "timestamp")),
            (narrative_events, ("date", "Date", "timestamp")),
            (narrative_state, ("date", "Date", "timestamp")),
            (sector_flows, ("Date", "date", "timestamp")),
            (market_state, ("date", "Date", "timestamp")),
            (intelligent_market_state, ("date", "Date", "timestamp")),
        ],
        lookback_days=lookback_days,
    )
    snapshot = pd.DataFrame({"date": pd.Series(calendar).dt.normalize()})

    # -------------------- Market layer --------------------
    mr = _attach_date_column(market_regime, ["Date", "date"])
    if not mr.empty:
        for col in ["risk_on_score", "volatility", "correlation"]:
            if col in mr.columns:
                mr[col] = pd.to_numeric(mr[col], errors="coerce")
        market_cols = [c for c in ["market_regime", "risk_on_score", "volatility", "correlation"] if c in mr.columns]
        if market_cols:
            mr_daily = mr.groupby("date", as_index=False)[market_cols].last()
            if "volatility" in mr_daily.columns:
                mr_daily["volatility_z"] = _zscore(mr_daily["volatility"])
            if "correlation" in mr_daily.columns:
                mr_daily["correlation_z"] = _zscore(mr_daily["correlation"])
            if {"volatility_z", "correlation_z"}.issubset(mr_daily.columns):
                mr_daily["risk_pressure_index"] = mr_daily["volatility_z"] + mr_daily["correlation_z"]
            mr_daily = mr_daily.rename(
                columns={
                    "market_regime": "regime_label",
                    "risk_on_score": "regime_confidence",
                }
            )
            keep = [
                "date",
                "regime_label",
                "regime_confidence",
                "volatility_z",
                "correlation_z",
                "risk_pressure_index",
            ]
            snapshot = _merge_on_date(snapshot, mr_daily[[c for c in keep if c in mr_daily.columns]])

    a = _attach_date_column(alpha_os, ["timestamp", "date"])
    if not a.empty:
        alpha_cols = [
            "regime_entropy",
            "regime_crisis",
            "fallback_tier",
            "survival_core_active",
            "allocator_drawdown_probability_proxy",
            "regime_confidence",
            "gross_used",
            "net_used",
            "gross_target",
            "net_target",
        ]
        for col in alpha_cols:
            if col in a.columns:
                a[col] = pd.to_numeric(a[col], errors="coerce")
        if "survival_core_active" in a.columns:
            a["survival_core_active"] = a["survival_core_active"].fillna(0).astype(int)
        ad = a.groupby("date", as_index=False).last()
        if "regime_crisis" in ad.columns:
            ad = ad.rename(columns={"regime_crisis": "crisis_probability"})
        if "fallback_tier" in ad.columns:
            ad = ad.rename(columns={"fallback_tier": "fallback_ladder_level"})
        if "allocator_drawdown_probability_proxy" in ad.columns:
            ad = ad.rename(columns={"allocator_drawdown_probability_proxy": "drawdown_probability_30d"})
        alpha_keep = [
            "date",
            "regime_entropy",
            "crisis_probability",
            "fallback_ladder_level",
            "survival_core_active",
            "drawdown_probability_30d",
            "regime_confidence",
            "gross_used",
            "net_used",
            "gross_target",
            "net_target",
        ]
        snapshot = _merge_on_date(snapshot, ad[[c for c in alpha_keep if c in ad.columns]])

    mf = _attach_date_column(macro_factors, ["date", "Date", "timestamp"])
    if not mf.empty:
        inflation_col = _first_present_col(mf, ["I", "inflation_z", "inflation"])
        if inflation_col:
            mf[inflation_col] = pd.to_numeric(mf[inflation_col], errors="coerce")
            mfd = mf.groupby("date", as_index=False)[inflation_col].last()
            mfd["inflation_z"] = (
                mfd[inflation_col]
                if inflation_col == "inflation_z"
                else _zscore(mfd[inflation_col])
            )
            snapshot = _merge_on_date(snapshot, mfd[["date", "inflation_z"]])

    fii_proxy = _build_fii_flow_proxy(root, sector_flows)
    snapshot = _merge_on_date(snapshot, fii_proxy)

    # Macro/news sentiment backbone.
    # Precedence: explicit sentiment feed -> intelligent/market state sentiment -> risk-on proxy.
    sm = _attach_date_column(sentiment_market, ["date", "Date", "timestamp"])
    if not sm.empty:
        sentiment_col = _first_present_col(sm, ["polarity", "sentiment_score", "signed_sentiment_intensity"])
        if sentiment_col:
            sm["macro_news_sentiment"] = pd.to_numeric(sm[sentiment_col], errors="coerce")
            sm = sm.dropna(subset=["macro_news_sentiment"])
            if not sm.empty:
                smd = sm.groupby("date", as_index=False)["macro_news_sentiment"].mean()
                snapshot = _merge_on_date(snapshot, smd[["date", "macro_news_sentiment"]])

    ims = _attach_date_column(intelligent_market_state, ["date", "Date", "timestamp"])
    if not ims.empty:
        icol = _first_present_col(ims, ["sentiment_polarity", "sentiment_news_signal", "sentiment_bias"])
        if icol:
            ims["macro_news_sentiment"] = pd.to_numeric(ims[icol], errors="coerce")
            ims = ims.dropna(subset=["macro_news_sentiment"])
            if not ims.empty:
                imsd = ims.groupby("date", as_index=False)["macro_news_sentiment"].mean()
                snapshot = _merge_on_date(snapshot, imsd[["date", "macro_news_sentiment"]])

    ms = _attach_date_column(market_state, ["date", "Date", "timestamp"])
    if not ms.empty:
        mcol = _first_present_col(ms, ["sentiment_polarity", "sentiment_news_signal", "sentiment_bias"])
        if mcol:
            ms["macro_news_sentiment"] = pd.to_numeric(ms[mcol], errors="coerce")
            ms = ms.dropna(subset=["macro_news_sentiment"])
            if not ms.empty:
                msd = ms.groupby("date", as_index=False)["macro_news_sentiment"].mean()
                snapshot = _merge_on_date(snapshot, msd[["date", "macro_news_sentiment"]])

    # Long-history fallback: map risk-on score [0,1] into sentiment-like scale [-1,1].
    if not mr.empty and "risk_on_score" in mr.columns:
        rp = mr[["date", "risk_on_score"]].copy()
        rp["risk_on_score"] = pd.to_numeric(rp["risk_on_score"], errors="coerce")
        rp = rp.dropna(subset=["risk_on_score"])
        if not rp.empty:
            rpd = rp.groupby("date", as_index=False)["risk_on_score"].last()
            rpd["macro_news_sentiment"] = (2.0 * rpd["risk_on_score"].clip(0.0, 1.0)) - 1.0
            snapshot = _merge_on_date(snapshot, rpd[["date", "macro_news_sentiment"]])

    stance_score = _policy_stance_score(policy_context)
    policy_shock = _policy_shock_flag(policy_context)
    snapshot["policy_stance_score"] = float(stance_score)
    snapshot["policy_shock_flag"] = int(policy_shock)

    # -------------------- Intelligence layer --------------------
    sb = _attach_date_column(strategy_beliefs, ["date", "Date", "timestamp"])
    if not sb.empty:
        belief_candidates = ["belief_strength", "skill_prob", "confidence", "effective_skill"]
        belief_col = None
        best_non_na = -1
        for c in belief_candidates:
            if c not in sb.columns:
                continue
            nn = int(pd.to_numeric(sb[c], errors="coerce").notna().sum())
            if nn > best_non_na:
                best_non_na = nn
                belief_col = c
        if belief_col:
            sb["belief_strength"] = pd.to_numeric(sb[belief_col], errors="coerce")
            sb = sb.dropna(subset=["belief_strength"])
            if not sb.empty:
                sbd = sb.groupby("date", as_index=False)["belief_strength"].mean()
                sbd["belief_momentum"] = sbd["belief_strength"].diff(5).fillna(0.0)
                snapshot = _merge_on_date(snapshot, sbd[["date", "belief_strength", "belief_momentum"]])

    # Fallback: belief_evolution.json carries unified conviction history when
    # strategy_beliefs is sparse or single-snapshot.
    hist = belief_evolution.get("history", []) if isinstance(belief_evolution, dict) else []
    if isinstance(hist, list) and hist:
        be = pd.DataFrame(hist)
        tcol = _first_present_col(be, ["timestamp", "date", "Date"])
        vcol = _first_present_col(be, ["unified_conviction", "belief_strength", "skill_prob", "confidence"])
        if tcol and vcol:
            be["date"] = _to_date(be[tcol])
            be["belief_strength"] = pd.to_numeric(be[vcol], errors="coerce")
            be = be.dropna(subset=["date", "belief_strength"]).sort_values("date")
            if not be.empty:
                bed = be.groupby("date", as_index=False)["belief_strength"].mean()
                bed["belief_momentum"] = bed["belief_strength"].diff(5).fillna(0.0)
                snapshot = _merge_on_date(snapshot, bed[["date", "belief_strength", "belief_momentum"]])

    # Narrative state offers the longest real belief history in this stack.
    ns = _attach_date_column(narrative_state, ["date", "Date", "timestamp"])
    if not ns.empty and "avg_belief_strength" in ns.columns:
        ns["belief_strength"] = pd.to_numeric(ns["avg_belief_strength"], errors="coerce")
        ns = ns.dropna(subset=["belief_strength"])
        if not ns.empty:
            nsd = ns.groupby("date", as_index=False)["belief_strength"].mean()
            nsd["belief_momentum"] = nsd["belief_strength"].diff(5).fillna(0.0)
            snapshot = _merge_on_date(snapshot, nsd[["date", "belief_strength", "belief_momentum"]])

    # Intelligent state conviction is a useful fallback when explicit beliefs are sparse.
    ims_b = _attach_date_column(intelligent_market_state, ["date", "Date", "timestamp"])
    if not ims_b.empty and "conviction" in ims_b.columns:
        ims_b["belief_strength"] = pd.to_numeric(ims_b["conviction"], errors="coerce")
        ims_b = ims_b.dropna(subset=["belief_strength"])
        if not ims_b.empty:
            ibd = ims_b.groupby("date", as_index=False)["belief_strength"].mean()
            ibd["belief_momentum"] = ibd["belief_strength"].diff(5).fillna(0.0)
            snapshot = _merge_on_date(snapshot, ibd[["date", "belief_strength", "belief_momentum"]])

    sr = strategy_regret.copy()
    if isinstance(sr, pd.DataFrame) and not sr.empty:
        rdate_col = _first_present_col(sr, ["last_updated", "date", "Date", "timestamp"])
        if rdate_col:
            sr["date"] = _to_date(sr[rdate_col])
        else:
            sr["date"] = snapshot["date"].max()
        regret_col = _first_present_col(sr, ["regret_score", "regret", "score"])
        if regret_col:
            sr["regret_score"] = pd.to_numeric(sr[regret_col], errors="coerce")
            sr = sr.dropna(subset=["date", "regret_score"])
            if not sr.empty:
                srd = sr.groupby("date", as_index=False)["regret_score"].mean()
                snapshot = _merge_on_date(snapshot, srd)

    vp = _attach_date_column(valuation_posterior, ["date", "Date", "timestamp"])
    if not vp.empty and "posterior_gap" in vp.columns:
        vp["posterior_gap"] = pd.to_numeric(vp["posterior_gap"], errors="coerce")
        vp = vp.dropna(subset=["posterior_gap"])
        if not vp.empty:
            vpd = vp.groupby("date", as_index=False)["posterior_gap"].mean()
            vpd["valuation_gap_z"] = _zscore(vpd["posterior_gap"])
            snapshot = _merge_on_date(snapshot, vpd[["date", "valuation_gap_z"]])

    osf = opportunity_surface.copy()
    if isinstance(osf, pd.DataFrame) and not osf.empty:
        opp_col = _first_present_col(osf, ["northstar_score", "pulse_weighted_score", "regime_adjusted_score"])
        if opp_col:
            osf[opp_col] = pd.to_numeric(osf[opp_col], errors="coerce")
            osf = osf.dropna(subset=[opp_col])
            if not osf.empty:
                if _first_present_col(osf, ["date", "Date", "timestamp"]):
                    osf = _attach_date_column(osf, ["date", "Date", "timestamp"])
                    opd = osf.groupby("date", as_index=False)[opp_col].mean()
                    opd = opd.rename(columns={opp_col: "opportunity_score_mean"})
                    snapshot = _merge_on_date(snapshot, opd)
                else:
                    snapshot["opportunity_score_mean"] = float(osf[opp_col].mean())

    ne = _attach_date_column(narrative_events, ["date", "Date", "timestamp"])
    if not ne.empty:
        mag_col = _first_present_col(ne, ["magnitude", "impact", "shock_intensity", "significance"])
        if mag_col:
            ne[mag_col] = pd.to_numeric(ne[mag_col], errors="coerce")
            ne = ne.dropna(subset=[mag_col])
            if not ne.empty:
                ned = ne.groupby("date", as_index=False)[mag_col].apply(lambda s: s.abs().sum())
                ned = ned.rename(columns={mag_col: "narrative_shock_intensity"})
                snapshot = _merge_on_date(snapshot, ned)

    # -------------------- Portfolio layer --------------------
    ah = _attach_date_column(allocation_history, ["date", "Date", "timestamp"])
    if not ah.empty:
        if "total_exposure" in ah.columns:
            ah["total_exposure"] = pd.to_numeric(ah["total_exposure"], errors="coerce")
        if "allocation_weight" in ah.columns:
            ah["allocation_weight"] = pd.to_numeric(ah["allocation_weight"], errors="coerce")

        meta_cols = {
            "date",
            "regime",
            "strategy_name",
            "strategy_category",
            "allocation_weight",
            "allocation_score",
            "regime_fitness",
            "adjusted_return",
            "adjusted_sharpe",
            "risk_contribution",
            "allocation_reason",
            "timestamp",
            "regime_name",
            "regime_stability",
            "no_edge_state",
            "exposure_cap",
            "total_exposure",
        }
        strategy_cols = [
            c
            for c in ah.columns
            if c not in meta_cols and pd.api.types.is_numeric_dtype(ah[c])
        ]
        if strategy_cols:
            ah["_strat_net"] = ah[strategy_cols].sum(axis=1, skipna=True)
            ah["_strat_gross"] = ah[strategy_cols].abs().sum(axis=1, skipna=True)
        else:
            ah["_strat_net"] = np.nan
            ah["_strat_gross"] = np.nan

        by_date = ah.groupby("date", as_index=False).last()
        if "allocation_weight" in ah.columns:
            alloc_agg = ah.groupby("date", as_index=False)["allocation_weight"].sum()
            by_date = by_date.merge(alloc_agg, on="date", how="left", suffixes=("", "_sum"))
        by_date["gross_exposure"] = pd.to_numeric(by_date.get("total_exposure"), errors="coerce")
        by_date["gross_exposure"] = by_date["gross_exposure"].combine_first(pd.to_numeric(by_date["_strat_gross"], errors="coerce"))
        if "allocation_weight_sum" in by_date.columns:
            by_date["net_exposure"] = pd.to_numeric(by_date["allocation_weight_sum"], errors="coerce")
        else:
            by_date["net_exposure"] = pd.to_numeric(by_date.get("_strat_net"), errors="coerce")
        snapshot = _merge_on_date(snapshot, by_date[["date", "gross_exposure", "net_exposure"]])

    pw = portfolio_weights.copy()
    if isinstance(pw, pd.DataFrame) and not pw.empty:
        if _first_present_col(pw, ["date", "Date", "timestamp"]):
            pw = _attach_date_column(pw, ["date", "Date", "timestamp"])
        else:
            pw["date"] = snapshot["date"].max()
        weight_col = _first_present_col(pw, ["weight", "final_weight", "allocation", "exposure", "w"])
        industry_col = _first_present_col(pw, ["Industry", "industry", "sector"])
        if weight_col:
            pw["weight"] = pd.to_numeric(pw[weight_col], errors="coerce")
            pw = pw.dropna(subset=["date", "weight"])
            if not pw.empty:
                exposure_daily = pw.groupby("date").agg(
                    gross_w=("weight", lambda s: float(np.abs(s).sum())),
                    net_w=("weight", "sum"),
                )
                exposure_daily = exposure_daily.reset_index()
                if industry_col:
                    tmp = pw.dropna(subset=[industry_col]).copy()
                    tmp[industry_col] = tmp[industry_col].astype(str)
                    grouped = (
                        tmp.groupby(["date", industry_col])["weight"]
                        .apply(lambda s: float(np.abs(s).sum()))
                        .reset_index()
                    )
                    grouped = grouped.rename(columns={"weight": "industry_abs_weight"})
                    hhi_rows = []
                    for d, g in grouped.groupby("date"):
                        total = float(g["industry_abs_weight"].sum())
                        if total <= 1e-12:
                            hhi = np.nan
                        else:
                            share = g["industry_abs_weight"] / total
                            hhi = float((share ** 2).sum())
                        hhi_rows.append({"date": d, "sector_concentration_index": hhi})
                    hhi_df = pd.DataFrame(hhi_rows)
                    exposure_daily = exposure_daily.merge(hhi_df, on="date", how="left")
                exposure_daily["cash_weight"] = (1.0 - exposure_daily["gross_w"]).clip(lower=0.0)
                exposure_daily = exposure_daily.rename(columns={"gross_w": "gross_exposure_w", "net_w": "net_exposure_w"})
                snapshot = _merge_on_date(
                    snapshot,
                    exposure_daily[
                        [
                            "date",
                            "gross_exposure_w",
                            "net_exposure_w",
                            "sector_concentration_index",
                            "cash_weight",
                        ]
                    ],
                )

    ehl = edge_half_life.copy()
    if isinstance(ehl, pd.DataFrame) and not ehl.empty:
        if _first_present_col(ehl, ["last_updated", "date", "Date", "timestamp"]):
            ehl = _attach_date_column(ehl, ["last_updated", "date", "Date", "timestamp"])
        else:
            ehl["date"] = snapshot["date"].max()
        edge_col = _first_present_col(ehl, ["edge_health", "health"])
        hl_col = _first_present_col(ehl, ["half_life_days", "half_life", "remaining_half_life"])
        if edge_col or hl_col:
            if edge_col:
                ehl["edge_health"] = pd.to_numeric(ehl[edge_col], errors="coerce")
            if hl_col:
                ehl["half_life_days"] = pd.to_numeric(ehl[hl_col], errors="coerce")
            agg_map: Dict[str, str] = {}
            if "edge_health" in ehl.columns:
                agg_map["edge_health"] = "mean"
            if "half_life_days" in ehl.columns:
                agg_map["half_life_days"] = "mean"
            if agg_map:
                ehd = ehl.groupby("date", as_index=False).agg(agg_map)
                ehd = ehd.rename(
                    columns={
                        "edge_health": "edge_health_mean",
                        "half_life_days": "half_life_mean",
                    }
                )
                snapshot = _merge_on_date(snapshot, ehd)

    lr = _attach_date_column(liquidity_risk, ["timestamp", "date", "Date"])
    if not lr.empty and "exit_risk" in lr.columns:
        lr["exit_risk"] = pd.to_numeric(lr["exit_risk"], errors="coerce")
        lr = lr.dropna(subset=["exit_risk"])
        if not lr.empty:
            lrd = lr.groupby("date", as_index=False)["exit_risk"].mean()
            lrd = lrd.rename(
                columns={
                    "exit_risk": "exit_risk_mean",
                }
            )
            lrd["liquidity_stress_index"] = lrd["exit_risk_mean"]
            snapshot = _merge_on_date(snapshot, lrd)

    perf = _compute_perf_frame(pnl, nifty)
    snapshot = _merge_on_date(snapshot, perf)

    # -------------------- News layer --------------------
    sn = sector_narratives.copy()
    if isinstance(sn, pd.DataFrame) and not sn.empty and "sentiment_score" in sn.columns:
        sn["sentiment_score"] = pd.to_numeric(sn["sentiment_score"], errors="coerce")
        sn = sn.dropna(subset=["sentiment_score"])
        if not sn.empty:
            top_pos = str(sn.loc[sn["sentiment_score"].idxmax(), "sector"]) if "sector" in sn.columns else None
            top_neg = str(sn.loc[sn["sentiment_score"].idxmin(), "sector"]) if "sector" in sn.columns else None
            snapshot["sector_news_dispersion"] = float(sn["sentiment_score"].std(ddof=0))
            snapshot["top_sector_sentiment"] = top_pos
            snapshot["top_negative_sector"] = top_neg

    ev = _attach_date_column(event_company_impact, ["timestamp", "date", "Date"])
    if not ev.empty and "impact_score" in ev.columns:
        ev["impact_score"] = pd.to_numeric(ev["impact_score"], errors="coerce")
        ev = ev.dropna(subset=["impact_score"])
        if not ev.empty:
            evd = ev.groupby("date", as_index=False)["impact_score"].apply(lambda s: float(s.abs().mean()))
            evd = evd.rename(columns={"impact_score": "event_intensity_mean"})
            snapshot = _merge_on_date(snapshot, evd)

    # -------------------- Reconciliations --------------------
    if "gross_exposure" in snapshot.columns and "gross_exposure_w" in snapshot.columns:
        snapshot["gross_exposure"] = snapshot["gross_exposure"].combine_first(snapshot["gross_exposure_w"])
    elif "gross_exposure_w" in snapshot.columns:
        snapshot["gross_exposure"] = snapshot["gross_exposure_w"]
    if "net_exposure" in snapshot.columns and "net_exposure_w" in snapshot.columns:
        snapshot["net_exposure"] = snapshot["net_exposure"].combine_first(snapshot["net_exposure_w"])
    elif "net_exposure_w" in snapshot.columns:
        snapshot["net_exposure"] = snapshot["net_exposure_w"]
    snapshot = snapshot.drop(columns=[c for c in ["gross_exposure_w", "net_exposure_w"] if c in snapshot.columns])

    if "regime_label" not in snapshot.columns or snapshot["regime_label"].isna().all():
        current = regime_feed.get("current_regime", {}) if isinstance(regime_feed, dict) else {}
        regime_name = str((current.get("name") if isinstance(current, dict) else "") or "").strip()
        if regime_name:
            snapshot["regime_label"] = regime_name
    if "regime_confidence" in snapshot.columns:
        current = regime_feed.get("current_regime", {}) if isinstance(regime_feed, dict) else {}
        conf = np.nan
        if isinstance(current, dict):
            conf = pd.to_numeric(current.get("stability"), errors="coerce")
        if np.isfinite(conf):
            snapshot["regime_confidence"] = pd.to_numeric(snapshot["regime_confidence"], errors="coerce").fillna(float(conf))

    # Belief fallback hierarchy ends at regime confidence (real, daily, long-history).
    if {"belief_strength", "regime_confidence"}.issubset(snapshot.columns):
        b = pd.to_numeric(snapshot["belief_strength"], errors="coerce")
        rc = pd.to_numeric(snapshot["regime_confidence"], errors="coerce").clip(0.0, 1.0)
        snapshot["belief_strength"] = b.combine_first(rc)
        if "belief_momentum" in snapshot.columns:
            bm = pd.to_numeric(snapshot["belief_momentum"], errors="coerce")
            snapshot["belief_momentum"] = bm.combine_first(snapshot["belief_strength"].diff(5))

    ps = portfolio_analytics.get("portfolio_summary", {}) if isinstance(portfolio_analytics, dict) else {}
    cash = pd.to_numeric(ps.get("cash"), errors="coerce")
    if np.isfinite(cash):
        if "cash_weight" in snapshot.columns:
            snapshot["cash_weight"] = pd.to_numeric(snapshot["cash_weight"], errors="coerce").fillna(float(cash))
        else:
            snapshot["cash_weight"] = float(cash)

    if "macro_news_sentiment" in snapshot.columns:
        snapshot["macro_news_sentiment"] = pd.to_numeric(snapshot["macro_news_sentiment"], errors="coerce")
        snapshot["macro_sentiment_z"] = _zscore(snapshot["macro_news_sentiment"])

    # Entropy/probability fallbacks from regime confidence when AlphaOS history is sparse.
    if "regime_confidence" in snapshot.columns:
        rc = pd.to_numeric(snapshot["regime_confidence"], errors="coerce").clip(0.0, 1.0)
        entropy_fallback = _binary_entropy(rc)
        crisis_fallback = (1.0 - rc).clip(0.0, 1.0)
        if "regime_entropy" in snapshot.columns:
            snapshot["regime_entropy"] = pd.to_numeric(snapshot["regime_entropy"], errors="coerce").combine_first(entropy_fallback)
        else:
            snapshot["regime_entropy"] = entropy_fallback
        if "crisis_probability" in snapshot.columns:
            snapshot["crisis_probability"] = pd.to_numeric(snapshot["crisis_probability"], errors="coerce").combine_first(crisis_fallback)
        else:
            snapshot["crisis_probability"] = crisis_fallback

    if "risk_pressure_index" not in snapshot.columns and {"volatility_z", "correlation_z"}.issubset(snapshot.columns):
        snapshot["risk_pressure_index"] = (
            pd.to_numeric(snapshot["volatility_z"], errors="coerce")
            + pd.to_numeric(snapshot["correlation_z"], errors="coerce")
        )
    if "correlation_spike_flag" not in snapshot.columns and "correlation_z" in snapshot.columns:
        snapshot["correlation_spike_flag"] = (
            pd.to_numeric(snapshot["correlation_z"], errors="coerce") > 1.5
        ).astype(int)

    if "drawdown_probability_30d" in snapshot.columns and "drawdown_probability_30d_perf" in snapshot.columns:
        snapshot["drawdown_probability_30d"] = (
            pd.to_numeric(snapshot["drawdown_probability_30d"], errors="coerce")
            .combine_first(pd.to_numeric(snapshot["drawdown_probability_30d_perf"], errors="coerce"))
        )
    elif "drawdown_probability_30d_perf" in snapshot.columns:
        snapshot["drawdown_probability_30d"] = pd.to_numeric(snapshot["drawdown_probability_30d_perf"], errors="coerce")
    snapshot = snapshot.drop(columns=[c for c in ["drawdown_probability_30d_perf"] if c in snapshot.columns])

    if {"belief_strength", "macro_news_sentiment"}.issubset(snapshot.columns):
        snapshot["belief_news_divergence"] = _zscore(snapshot["belief_strength"]) - _zscore(snapshot["macro_news_sentiment"])

    # Forward-fill slow-moving state features.
    for col in snapshot.columns:
        if col == "date":
            continue
        if col in STRING_COLUMNS:
            snapshot[col] = snapshot[col].astype("string").ffill().bfill()
            continue
        if col == "active_return":
            snapshot[col] = pd.to_numeric(snapshot[col], errors="coerce").fillna(0.0)
            continue
        snapshot[col] = pd.to_numeric(snapshot[col], errors="coerce").ffill()

    # Ensure schema columns exist and are ordered.
    for col in SCHEMA_COLUMNS:
        if col not in snapshot.columns:
            if col in STRING_COLUMNS:
                snapshot[col] = pd.Series([None] * len(snapshot), dtype="string")
            else:
                snapshot[col] = np.nan

    for col in INT_COLUMNS:
        snapshot[col] = _as_int_flag(snapshot[col])

    snapshot = snapshot[SCHEMA_COLUMNS].copy()
    snapshot = snapshot.sort_values("date").drop_duplicates(subset=["date"], keep="last")
    snapshot["date"] = pd.to_datetime(snapshot["date"], errors="coerce").dt.normalize()

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot.to_parquet(output_path, index=False)
    return snapshot


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build integrated_state_snapshot.parquet")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Output parquet path (default: data/integrated/integrated_state_snapshot.parquet)",
    )
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=3650,
        help="Max lookback horizon for the snapshot calendar.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    df = build_integrated_snapshot(output_path=args.output, lookback_days=int(args.lookback_days))
    if df.empty:
        print(f"[integrated-snapshot] Wrote empty snapshot to {args.output}")
        return 0
    d0 = pd.to_datetime(df["date"].iloc[0]).date()
    d1 = pd.to_datetime(df["date"].iloc[-1]).date()
    print(
        f"[integrated-snapshot] rows={len(df)} cols={len(df.columns)} "
        f"range={d0}..{d1} path={args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
