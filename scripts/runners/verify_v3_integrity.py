#!/usr/bin/env python3
"""
Comprehensive V3 artifact integrity verification.

Checks:
- Missing/empty core artifacts
- NaN/Inf/null quality issues
- Key-column/schema expectations
- Basic date freshness
- Cross-artifact sanity checks (NIFTY flatline, macro collinearity,
  macro-impact significance-rate inflation)

Outputs:
- data/processed/integrity/v3_integrity_report_latest.json
- data/processed/integrity/v3_integrity_artifacts_latest.parquet
- timestamped copies for traceability
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass
class ArtifactSpec:
    rel_path: str
    kind: str  # parquet | csv | json
    required: bool = False
    key_columns: Optional[List[str]] = None
    date_columns: Optional[List[str]] = None
    max_stale_days: Optional[float] = None
    read_columns: Optional[List[str]] = None


@dataclass
class ArtifactCheck:
    artifact: str
    kind: str
    exists: bool
    status: str
    message: str
    rows: int = 0
    columns: int = 0
    null_ratio: float = math.nan
    inf_count: int = 0
    duplicate_keys: int = 0
    stale_days: float = math.nan
    min_date: Optional[str] = None
    max_date: Optional[str] = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _safe_float(v: Any, default: float = math.nan) -> float:
    try:
        x = float(v)
        if math.isfinite(x):
            return x
        return default
    except Exception:
        return default


def _status_rank(status: str) -> int:
    return {"ok": 0, "warn": 1, "critical": 2}.get(status, 1)


def _worst_status(values: Iterable[str]) -> str:
    worst = "ok"
    for s in values:
        if _status_rank(s) > _status_rank(worst):
            worst = s
    return worst


def _read_table(path: Path, spec: ArtifactSpec) -> pd.DataFrame:
    if spec.kind == "parquet":
        if spec.read_columns:
            return pd.read_parquet(path, columns=spec.read_columns)
        return pd.read_parquet(path)
    if spec.kind == "csv":
        if spec.read_columns:
            return pd.read_csv(path, usecols=[c for c in spec.read_columns])
        return pd.read_csv(path)
    raise ValueError(f"Unsupported table kind: {spec.kind}")


def _sample_for_quality(df: pd.DataFrame, max_rows: int) -> pd.DataFrame:
    if len(df) <= max_rows:
        return df
    # Deterministic sample for stable reports.
    return df.sample(n=max_rows, random_state=7)


def _normalize_dates(df: pd.DataFrame, candidates: List[str]) -> Optional[pd.Series]:
    for c in candidates:
        if c in df.columns:
            s = pd.to_datetime(df[c], errors="coerce")
            if s.notna().any():
                return s
    # Datetime index fallback.
    if isinstance(df.index, pd.DatetimeIndex) and len(df.index) > 0:
        s = pd.to_datetime(df.index, errors="coerce")
        if pd.Series(s).notna().any():
            return pd.Series(s, index=df.index)
    return None


def _table_check(path: Path, spec: ArtifactSpec, sample_rows: int) -> ArtifactCheck:
    if not path.exists():
        return ArtifactCheck(
            artifact=spec.rel_path,
            kind=spec.kind,
            exists=False,
            status="critical" if spec.required else "warn",
            message="missing",
        )

    statuses: List[str] = []
    messages: List[str] = []

    try:
        df = _read_table(path, spec)
    except Exception as e:
        return ArtifactCheck(
            artifact=spec.rel_path,
            kind=spec.kind,
            exists=True,
            status="critical" if spec.required else "warn",
            message=f"read_failed:{e}",
        )

    rows = int(len(df))
    cols = int(len(df.columns))
    if rows == 0 or cols == 0:
        statuses.append("critical" if spec.required else "warn")
        messages.append("empty_table")

    # Key-column presence
    if spec.key_columns:
        missing = [c for c in spec.key_columns if c not in df.columns]
        if missing:
            statuses.append("critical" if spec.required else "warn")
            messages.append(f"missing_columns:{','.join(missing)}")

    # Quality metrics (sampled for very large tables)
    qdf = _sample_for_quality(df, sample_rows)
    null_ratio = float(qdf.isna().sum().sum() / max(1, qdf.shape[0] * max(1, qdf.shape[1])))

    if null_ratio > 0.80:
        statuses.append("critical")
        messages.append(f"very_high_null_ratio:{null_ratio:.3f}")
    elif null_ratio > 0.40:
        statuses.append("warn")
        messages.append(f"high_null_ratio:{null_ratio:.3f}")

    num = qdf.select_dtypes(include=[np.number])
    inf_count = int(np.isinf(num.to_numpy()).sum()) if not num.empty else 0
    if inf_count > 0:
        statuses.append("critical" if inf_count > 100 else "warn")
        messages.append(f"inf_count:{inf_count}")

    # Duplicate key diagnostics if common identity columns exist.
    duplicate_keys = 0
    key_pair = None
    for pair in (["Date", "ticker"], ["date", "ticker"], ["date", "asset_id"], ["Date", "symbol"]):
        if all(c in df.columns for c in pair):
            key_pair = pair
            break
    if key_pair is not None:
        duplicate_keys = int(df.duplicated(subset=key_pair).sum())
        if duplicate_keys > 0:
            statuses.append("warn" if duplicate_keys < max(1000, rows * 0.01) else "critical")
            messages.append(f"duplicate_keys:{duplicate_keys}({'+'.join(key_pair)})")

    # Freshness check
    stale_days = math.nan
    min_date = None
    max_date = None
    date_cols = spec.date_columns or ["Date", "date", "timestamp", "as_of"]
    ds = _normalize_dates(df, date_cols)
    if ds is not None:
        ds = pd.to_datetime(ds, errors="coerce")
        ds = ds.dropna()
        if not ds.empty:
            min_d = pd.Timestamp(ds.min())
            max_d = pd.Timestamp(ds.max())
            min_date = min_d.isoformat()
            max_date = max_d.isoformat()
            stale_days = float((_now().replace(tzinfo=None) - max_d.to_pydatetime().replace(tzinfo=None)).total_seconds() / 86400.0)
            if spec.max_stale_days is not None and stale_days > spec.max_stale_days:
                statuses.append("warn")
                messages.append(f"stale:{stale_days:.1f}d>{spec.max_stale_days:.1f}d")

    status = _worst_status(statuses) if statuses else "ok"
    message = "; ".join(messages) if messages else "ok"

    return ArtifactCheck(
        artifact=spec.rel_path,
        kind=spec.kind,
        exists=True,
        status=status,
        message=message,
        rows=rows,
        columns=cols,
        null_ratio=float(null_ratio),
        inf_count=inf_count,
        duplicate_keys=duplicate_keys,
        stale_days=stale_days,
        min_date=min_date,
        max_date=max_date,
    )


def _json_check(path: Path, spec: ArtifactSpec) -> ArtifactCheck:
    if not path.exists():
        return ArtifactCheck(
            artifact=spec.rel_path,
            kind=spec.kind,
            exists=False,
            status="critical" if spec.required else "warn",
            message="missing",
        )

    statuses: List[str] = []
    messages: List[str] = []

    try:
        obj = json.loads(path.read_text())
    except Exception as e:
        return ArtifactCheck(
            artifact=spec.rel_path,
            kind=spec.kind,
            exists=True,
            status="critical" if spec.required else "warn",
            message=f"json_parse_failed:{e}",
        )

    rows = 1
    cols = 1
    if isinstance(obj, dict):
        cols = len(obj)
        if cols == 0:
            statuses.append("warn")
            messages.append("empty_object")
    elif isinstance(obj, list):
        rows = len(obj)
        cols = len(obj[0]) if obj and isinstance(obj[0], dict) else 1
        if len(obj) == 0:
            statuses.append("warn")
            messages.append("empty_list")

    # Detect placeholder/test payload patterns.
    blob = json.dumps(obj).lower()
    if any(tok in blob for tok in ["mock", "synthetic", "sample_data", "demo_data"]):
        statuses.append("warn")
        messages.append("contains_placeholder_tokens")

    status = _worst_status(statuses) if statuses else "ok"
    message = "; ".join(messages) if messages else "ok"

    return ArtifactCheck(
        artifact=spec.rel_path,
        kind=spec.kind,
        exists=True,
        status=status,
        message=message,
        rows=int(rows),
        columns=int(cols),
    )


def _check_specs(specs: List[ArtifactSpec], sample_rows: int) -> List[ArtifactCheck]:
    checks: List[ArtifactCheck] = []
    for spec in specs:
        path = PROJECT_ROOT / spec.rel_path
        if spec.kind in {"parquet", "csv"}:
            checks.append(_table_check(path, spec, sample_rows=sample_rows))
        elif spec.kind == "json":
            checks.append(_json_check(path, spec))
        else:
            checks.append(
                ArtifactCheck(
                    artifact=spec.rel_path,
                    kind=spec.kind,
                    exists=path.exists(),
                    status="warn",
                    message=f"unsupported_kind:{spec.kind}",
                )
            )
    return checks


def _cross_checks() -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []

    def add(name: str, status: str, message: str, metrics: Optional[Dict[str, Any]] = None) -> None:
        out.append({
            "check": name,
            "status": status,
            "message": message,
            "metrics": metrics or {},
        })

    # 1) NIFTY flatline sanity
    try:
        p = PROJECT_ROOT / "data/processed/nifty.parquet"
        if p.exists():
            n = pd.read_parquet(p)
            ccol = "close" if "close" in n.columns else ("Close" if "Close" in n.columns else None)
            if ccol:
                s = pd.to_numeric(n[ccol], errors="coerce").dropna()
                if len(s) >= 120:
                    r = s.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
                    flat_ratio = float((r.abs() < 1e-6).mean()) if len(r) else 0.0
                    status = "ok"
                    msg = "nifty_return_continuity_ok"
                    if flat_ratio > 0.20:
                        status = "critical"
                        msg = "nifty_flatline_ratio_very_high"
                    elif flat_ratio > 0.10:
                        status = "warn"
                        msg = "nifty_flatline_ratio_high"
                    add("nifty_flatline", status, msg, {"flat_ratio": flat_ratio, "n_returns": int(len(r))})
    except Exception as e:
        add("nifty_flatline", "warn", f"check_failed:{e}")

    # 2) Macro-impact significance-rate sanity
    try:
        p = PROJECT_ROOT / "data/processed/macro_impact/analysis_metadata.json"
        if p.exists():
            meta = json.loads(p.read_text())
            res = meta.get("results_summary") or {}
            sig = _safe_float(res.get("significant_relationships"), 0.0)
            total = _safe_float(res.get("total_relationships"), 0.0)
            if total > 0:
                rate = float(sig / total)
                status = "ok"
                msg = "significance_rate_reasonable"
                if rate > 0.80:
                    status = "critical"
                    msg = "significance_rate_implausibly_high"
                elif rate > 0.50:
                    status = "warn"
                    msg = "significance_rate_high"
                add("macro_impact_significance_rate", status, msg, {"significant": sig, "total": total, "rate": rate})
    except Exception as e:
        add("macro_impact_significance_rate", "warn", f"check_failed:{e}")

    # 3) Macro collinearity sanity (v2 preferred)
    try:
        p_v2 = PROJECT_ROOT / "data/processed/macro_factors_v2.parquet"
        p_v1 = PROJECT_ROOT / "data/processed/macro_factors.parquet"
        p = p_v2 if p_v2.exists() else p_v1
        if p.exists():
            df = pd.read_parquet(p)
            if isinstance(df.index, pd.DatetimeIndex):
                df = df.copy().sort_index()
            num = df.apply(pd.to_numeric, errors="coerce").dropna(axis=1, how="all")
            if num.shape[1] >= 2:
                corr = num.corr().abs()
                np.fill_diagonal(corr.values, 0.0)
                max_offdiag = float(np.nanmax(corr.to_numpy()))
                status = "ok"
                msg = "macro_collinearity_ok"
                if max_offdiag > 0.995:
                    status = "critical"
                    msg = "macro_collinearity_extreme"
                elif max_offdiag > 0.95:
                    status = "warn"
                    msg = "macro_collinearity_high"
                add("macro_collinearity", status, msg, {"max_abs_corr": max_offdiag, "n_factors": int(num.shape[1])})
    except Exception as e:
        add("macro_collinearity", "warn", f"check_failed:{e}")

    # 4) Core timeline alignment (prices vs market_regime)
    try:
        pp = PROJECT_ROOT / "data/processed/prices.parquet"
        mr = PROJECT_ROOT / "data/processed/market_regime.parquet"
        if pp.exists() and mr.exists():
            p_df = pd.read_parquet(pp, columns=["Date"])
            m_df = pd.read_parquet(mr, columns=["Date"])
            d1 = pd.to_datetime(p_df["Date"], errors="coerce").dropna().max()
            d2 = pd.to_datetime(m_df["Date"], errors="coerce").dropna().max()
            if pd.notna(d1) and pd.notna(d2):
                lag_days = int((d1 - d2).days)
                status = "ok"
                msg = "prices_vs_regime_alignment_ok"
                if abs(lag_days) > 7:
                    status = "warn"
                    msg = "prices_vs_regime_misaligned"
                add("timeline_alignment", status, msg, {"prices_max_date": str(d1.date()), "market_regime_max_date": str(d2.date()), "lag_days": lag_days})
    except Exception as e:
        add("timeline_alignment", "warn", f"check_failed:{e}")

    # 5) Sentiment freshness + spine propagation sanity.
    try:
        sentiment_market = PROJECT_ROOT / "data/sentiment/v3/market_sentiment_india.parquet"
        sentiment_summary = PROJECT_ROOT / "data/sentiment/v3/v3_sentiment_summary.json"
        market_state = PROJECT_ROOT / "data/processed/market_state.parquet"

        if sentiment_market.exists():
            sdf = pd.read_parquet(sentiment_market)
            if isinstance(sdf, pd.DataFrame) and not sdf.empty:
                latest_sent = sdf.iloc[-1].to_dict()
                sent_date = None
                for key in ("timestamp", "date", "as_of", "run_date"):
                    if key in latest_sent:
                        sent_date = pd.to_datetime(latest_sent.get(key), errors="coerce")
                        if pd.notna(sent_date):
                            break
                if sent_date is None or pd.isna(sent_date):
                    if isinstance(sdf.index, pd.DatetimeIndex) and len(sdf.index) > 0:
                        sent_date = pd.to_datetime(sdf.index.max(), errors="coerce")

                if sent_date is not None and pd.notna(sent_date):
                    stale_days = float((_now().replace(tzinfo=None) - sent_date.to_pydatetime().replace(tzinfo=None)).total_seconds() / 86400.0)
                    status = "ok"
                    msg = "sentiment_freshness_ok"
                    if stale_days > 7.0:
                        status = "warn"
                        msg = "sentiment_stale"
                    add(
                        "sentiment_freshness",
                        status,
                        msg,
                        {
                            "sentiment_latest_date": str(sent_date.date()),
                            "stale_days": stale_days,
                            "summary_exists": sentiment_summary.exists(),
                        },
                    )

                if market_state.exists():
                    ms = pd.read_parquet(market_state)
                    if isinstance(ms, pd.DataFrame) and not ms.empty:
                        latest_ms = ms.iloc[-1].to_dict()
                        spine_has_sentiment = bool(latest_ms.get("sentiment_available", False))
                        spine_status = "ok" if spine_has_sentiment else "warn"
                        spine_msg = (
                            "market_state_sentiment_available"
                            if spine_has_sentiment
                            else "market_state_missing_sentiment_fields"
                        )

                        sent_polarity = float(pd.to_numeric(latest_sent.get("polarity", np.nan), errors="coerce"))
                        spine_polarity = float(pd.to_numeric(latest_ms.get("sentiment_polarity", np.nan), errors="coerce"))
                        polarity_diff = float(abs(spine_polarity - sent_polarity)) if np.isfinite(spine_polarity) and np.isfinite(sent_polarity) else math.nan
                        if spine_has_sentiment and np.isfinite(polarity_diff) and polarity_diff > 0.35:
                            spine_status = "warn"
                            spine_msg = "market_state_sentiment_drift"

                        add(
                            "sentiment_spine_propagation",
                            spine_status,
                            spine_msg,
                            {
                                "sentiment_available": spine_has_sentiment,
                                "state_sentiment_event_shock": float(pd.to_numeric(latest_ms.get("sentiment_event_shock", np.nan), errors="coerce"))
                                if pd.notna(pd.to_numeric(latest_ms.get("sentiment_event_shock", np.nan), errors="coerce"))
                                else math.nan,
                                "state_sentiment_alert": latest_ms.get("sentiment_alert_level"),
                                "state_sentiment_status": latest_ms.get("sentiment_status"),
                                "polarity_diff": polarity_diff,
                            },
                        )
    except Exception as e:
        add("sentiment_checks", "warn", f"check_failed:{e}")

    # 6) Certification lineage + macro-unit integrity coherence.
    try:
        p = PROJECT_ROOT / "reports/research/formula_lineage_and_unit_integrity_latest.json"
        if not p.exists():
            add("formula_lineage_unit_integrity", "critical", "missing_formula_lineage_report")
        else:
            obj = json.loads(p.read_text())
            required_blocks = [
                "formula_lineage",
                "macro_unit_integrity",
                "belief_layer_diagnostics",
                "gate_overfitting_audit",
            ]
            missing = [k for k in required_blocks if not isinstance(obj.get(k), dict)]
            if missing:
                add(
                    "formula_lineage_unit_integrity",
                    "critical",
                    "missing_required_blocks",
                    {"missing_blocks": missing},
                )
            else:
                fl = obj.get("formula_lineage", {}) if isinstance(obj.get("formula_lineage"), dict) else {}
                mu = obj.get("macro_unit_integrity", {}) if isinstance(obj.get("macro_unit_integrity"), dict) else {}
                belief = obj.get("belief_layer_diagnostics", {}) if isinstance(obj.get("belief_layer_diagnostics"), dict) else {}
                anomaly = fl.get("anomaly_normalization", {}) if isinstance(fl.get("anomaly_normalization"), dict) else {}
                flat = int(_safe_float(anomaly.get("flatline_series_count"), 0.0))
                lim = int(_safe_float(anomaly.get("max_unexplained_flatlines"), 12.0))
                suspicious = mu.get("suspicious_unit_usage", [])
                suspicious_n = int(len(suspicious)) if isinstance(suspicious, list) else 0
                report_passed = bool(obj.get("passed", True))
                history_days = int(_safe_float(belief.get("history_days"), 0.0))
                updates_observed = int(_safe_float(belief.get("updates_observed"), 0.0))

                status = "ok"
                msg = "formula_lineage_unit_integrity_ok"
                if suspicious_n > 0:
                    status = "critical"
                    msg = "macro_unit_suspicious_usage_detected"
                elif flat > lim:
                    status = "critical"
                    msg = "unexplained_flatlines_exceed_limit"
                elif not report_passed:
                    status = "warn"
                    msg = "formula_lineage_report_not_passed"
                elif history_days == 0 and updates_observed == 0:
                    status = "warn"
                    msg = "belief_history_not_available"

                add(
                    "formula_lineage_unit_integrity",
                    status,
                    msg,
                    {
                        "flatline_series_count": flat,
                        "flatline_limit": lim,
                        "macro_suspicious_count": suspicious_n,
                        "belief_history_days": history_days,
                        "belief_updates_observed": updates_observed,
                        "report_passed": report_passed,
                    },
                )
    except Exception as e:
        add("formula_lineage_unit_integrity", "warn", f"check_failed:{e}")

    return out


def _build_specs() -> List[ArtifactSpec]:
    return [
        ArtifactSpec("data/processed/prices.parquet", "parquet", required=True, key_columns=["Date", "ticker", "Close"], max_stale_days=7.0, read_columns=["Date", "ticker", "Close"]),
        ArtifactSpec("data/processed/technicals.parquet", "parquet", required=False, key_columns=["Date", "ticker"], max_stale_days=14.0, read_columns=["Date", "ticker"]),
        ArtifactSpec("data/processed/market_regime.parquet", "parquet", required=True, key_columns=["Date", "market_regime"], max_stale_days=7.0, read_columns=["Date", "market_regime", "risk_on_score", "volatility", "correlation"]),
        ArtifactSpec("data/processed/intelligent_market_state.parquet", "parquet", required=False, key_columns=["date"], max_stale_days=7.0, read_columns=["date", "regime_ai", "allowed_exposure"]),
        ArtifactSpec("data/sentiment/v3/v3_sentiment_summary.json", "json", required=False),
        ArtifactSpec("data/sentiment/v3/market_sentiment_india.parquet", "parquet", required=False, key_columns=["polarity", "conviction", "uncertainty"], max_stale_days=7.0),
        ArtifactSpec("data/sentiment/v3/company_sentiment_trends.parquet", "parquet", required=False, key_columns=["ticker"], max_stale_days=14.0),
        ArtifactSpec("data/sentiment/v3/event_company_impact.parquet", "parquet", required=False, key_columns=["ticker"], max_stale_days=14.0),
        ArtifactSpec("data/processed/regime_intelligence_feed.json", "json", required=True),
        ArtifactSpec("data/processed/portfolio_analytics.json", "json", required=False),
        ArtifactSpec("data/processed/portfolio_weights.parquet", "parquet", required=False, key_columns=["ticker"], max_stale_days=14.0, read_columns=["ticker", "weight"]),
        ArtifactSpec("data/portfolio/pnl_on_paper.parquet", "parquet", required=False, key_columns=["Date", "Equity", "Return"], max_stale_days=14.0, read_columns=["Date", "Equity", "Return"]),
        ArtifactSpec("data/processed/daily_narrative.parquet", "parquet", required=False, key_columns=["Date", "market_regime"], max_stale_days=14.0, read_columns=["Date", "market_regime", "allowed_exposure"]),
        ArtifactSpec("data/processed/macro_factors.parquet", "parquet", required=False, max_stale_days=35.0),
        ArtifactSpec("data/processed/macro_factors_v2.parquet", "parquet", required=False, max_stale_days=60.0),
        ArtifactSpec("data/processed/macro_impact/analysis_metadata.json", "json", required=False),
        ArtifactSpec("data/processed/macro_impact/company_macro_betas.parquet", "parquet", required=False, key_columns=["ticker", "macro_variable", "lag", "beta", "p_value"], max_stale_days=35.0, read_columns=["ticker", "macro_variable", "lag", "beta", "p_value", "significant"]),
        ArtifactSpec("data/processed/macro_transmission/run_metadata.json", "json", required=False),
        ArtifactSpec("data/processed/macro_transmission/current_kalman_betas.parquet", "parquet", required=False, key_columns=["ticker", "macro_variable", "beta"], max_stale_days=35.0, read_columns=["ticker", "macro_variable", "beta", "beta_abs"]),
        ArtifactSpec("data/processed/macro_transmission/macro_expected_change.parquet", "parquet", required=False, key_columns=["macro_variable", "expected_change"], max_stale_days=35.0, read_columns=["macro_variable", "expected_change", "as_of"]),
        ArtifactSpec("data/processed/valuation.parquet", "parquet", required=False, key_columns=["ticker"], max_stale_days=120.0, read_columns=["date", "ticker", "true_undervaluation", "final_value_index", "final_value_index_core", "posterior_gap", "posterior_confidence"]),
        ArtifactSpec("data/processed/valuation_families.parquet", "parquet", required=False, key_columns=["ticker"], max_stale_days=120.0, read_columns=["date", "ticker", "core_gap", "fcff_gap", "residual_gap", "transaction_gap", "credit_gap", "real_option_gap", "macro_percentile", "macro_adjustment_factor"]),
        ArtifactSpec("data/processed/valuation_posterior.parquet", "parquet", required=False, key_columns=["ticker"], max_stale_days=120.0, read_columns=["date", "ticker", "posterior_gap", "posterior_value", "posterior_variance", "agreement_score", "posterior_confidence"]),
        ArtifactSpec("data/processed/portfolio_valuation_state.parquet", "parquet", required=False, key_columns=["date", "valuation_regime"], max_stale_days=120.0, read_columns=["date", "market_percentile", "aggregate_gap_mean", "aggregate_gap_std", "bubble_probability", "valuation_regime"]),
        ArtifactSpec("data/processed/valuation_validation_summary.json", "json", required=False),
        ArtifactSpec("data/processed/valuation_validation_deciles.parquet", "parquet", required=False, key_columns=["date", "horizon_days", "decile"], max_stale_days=120.0, read_columns=["date", "horizon_days", "decile", "mean_return"]),
        ArtifactSpec("data/processed/valuation_validation_ic.parquet", "parquet", required=False, key_columns=["date", "horizon_days"], max_stale_days=120.0, read_columns=["date", "horizon_days", "ic_spearman", "top_bottom_spread", "monotonic_pass"]),
        ArtifactSpec("data/processed/valuation_validation_regime.parquet", "parquet", required=False, key_columns=["market_regime", "horizon_days"], max_stale_days=120.0, read_columns=["market_regime", "horizon_days", "ic_mean", "spread_mean", "monotonic_rate"]),
        ArtifactSpec("data/processed/shadow_trading_snapshot.json", "json", required=False),
        ArtifactSpec("data/processed/shadow_pnl_series.parquet", "parquet", required=False, key_columns=["date", "portfolio_value"], max_stale_days=35.0, read_columns=["date", "portfolio_value", "daily_return"]),
        ArtifactSpec("reports/research/formula_lineage_and_unit_integrity_latest.json", "json", required=True),
        ArtifactSpec("data/processed/macro_transmission/macro_unit_profile.json", "json", required=False),
        ArtifactSpec("data/processed/macro_transmission/macro_unit_conversion_log.json", "json", required=False),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify V3 artifact integrity")
    parser.add_argument("--strict", action="store_true", help="Fail on warnings as well")
    parser.add_argument("--sample-rows", type=int, default=250_000, help="Max sampled rows per table for quality checks")
    args = parser.parse_args()

    checks = _check_specs(_build_specs(), sample_rows=max(20_000, int(args.sample_rows)))
    cross = _cross_checks()

    by_status = {
        "ok": sum(1 for c in checks if c.status == "ok"),
        "warn": sum(1 for c in checks if c.status == "warn"),
        "critical": sum(1 for c in checks if c.status == "critical"),
    }
    cross_by_status = {
        "ok": sum(1 for c in cross if c.get("status") == "ok"),
        "warn": sum(1 for c in cross if c.get("status") == "warn"),
        "critical": sum(1 for c in cross if c.get("status") == "critical"),
    }

    report = {
        "timestamp": _now().isoformat(),
        "version": "v3_integrity_1.1",
        "summary": {
            "artifacts_checked": len(checks),
            "artifact_status": by_status,
            "cross_checks": cross_by_status,
            "strict_mode": bool(args.strict),
        },
        "artifacts": [asdict(c) for c in checks],
        "cross_checks": cross,
    }

    out_dir = PROJECT_ROOT / "data/processed/integrity"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    latest_json = out_dir / "v3_integrity_report_latest.json"
    ts_json = out_dir / f"v3_integrity_report_{ts}.json"
    latest_tbl = out_dir / "v3_integrity_artifacts_latest.parquet"
    ts_tbl = out_dir / f"v3_integrity_artifacts_{ts}.parquet"

    latest_json.write_text(json.dumps(report, indent=2, default=str))
    ts_json.write_text(json.dumps(report, indent=2, default=str))

    table_df = pd.DataFrame([asdict(c) for c in checks])
    table_df.to_parquet(latest_tbl, index=False)
    table_df.to_parquet(ts_tbl, index=False)

    print("V3 Integrity Audit Summary")
    print("=" * 48)
    print(f"Artifacts: ok={by_status['ok']} warn={by_status['warn']} critical={by_status['critical']}")
    print(f"Cross-checks: ok={cross_by_status['ok']} warn={cross_by_status['warn']} critical={cross_by_status['critical']}")
    print(f"Report: {latest_json.relative_to(PROJECT_ROOT)}")
    print(f"Table:  {latest_tbl.relative_to(PROJECT_ROOT)}")

    fail = by_status["critical"] + cross_by_status["critical"]
    if args.strict:
        fail += by_status["warn"] + cross_by_status["warn"]

    return 1 if fail > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
