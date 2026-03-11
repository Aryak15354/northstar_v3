"""
Canonical NS-USO sentiment context loader.

This module centralizes sentiment artifact parsing so all V3 components
consume one normalized view of sentiment context.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd


POSITIVE_SENTIMENT_LABELS = {"positive", "very_positive", "bullish"}
NEGATIVE_SENTIMENT_LABELS = {"negative", "very_negative", "bearish", "downside"}
DEFAULT_TOP_COMPANIES_LIMIT = 100


def _project_root(project_root: Optional[Path]) -> Path:
    if project_root is not None:
        return Path(project_root)
    return Path(__file__).resolve().parents[2]


def _safe_read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text())
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except Exception:
        return default
    if not math.isfinite(out):
        return default
    return out


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except Exception:
        return default


def _sentiment_sign(sentiment_label: str, sentiment_score: float) -> int:
    label = str(sentiment_label or "").strip().lower()
    if label in POSITIVE_SENTIMENT_LABELS:
        return 1
    if label in NEGATIVE_SENTIMENT_LABELS:
        return -1
    if sentiment_score >= 0.08:
        return 1
    if sentiment_score <= -0.08:
        return -1
    return 0


def _parse_ts(value: Any) -> Optional[pd.Timestamp]:
    if value is None or value == "":
        return None
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return None
    return pd.Timestamp(ts)


def _age_minutes(now: datetime, ts: Optional[pd.Timestamp]) -> Optional[float]:
    if ts is None or pd.isna(ts):
        return None
    try:
        if ts.tzinfo is not None:
            aware_now = now if now.tzinfo is not None else now.replace(tzinfo=timezone.utc)
            ts_py = ts.to_pydatetime().astimezone(aware_now.tzinfo)
            return max(0.0, (aware_now - ts_py).total_seconds() / 60.0)
        naive_now = now if now.tzinfo is None else now.replace(tzinfo=None)
        ts_py = ts.to_pydatetime().replace(tzinfo=None)
        return max(0.0, (naive_now - ts_py).total_seconds() / 60.0)
    except Exception:
        return None


def _infer_intensity(sentiment_score: float, trend_score: float, event_shock_factor: float) -> float:
    return float(
        max(
            0.0,
            0.62 * abs(sentiment_score)
            + 0.28 * max(0.0, trend_score)
            + 0.10 * max(0.0, event_shock_factor),
        )
    )


def _sanitize_company_row(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not isinstance(row, dict):
        return None
    ticker = str(row.get("ticker", "") or "").replace(".NS", "").strip().upper()
    if not ticker:
        return None

    trend_score = _to_float(row.get("trend_score", 0.0))
    headline_count = _to_int(row.get("headline_count", 0))
    sentiment_score = _to_float(row.get("sentiment_score", 0.0))
    event_shock_factor = _to_float(row.get("event_shock_factor", 0.0))
    sentiment_label = str(row.get("sentiment_label", "") or "").strip().lower()

    raw_sign = row.get("sentiment_sign")
    sentiment_sign = _to_int(raw_sign, default=_sentiment_sign(sentiment_label, sentiment_score))
    if sentiment_sign not in (-1, 0, 1):
        sentiment_sign = _sentiment_sign(sentiment_label, sentiment_score)

    intensity = _to_float(row.get("sentiment_intensity"), default=math.nan)
    if not math.isfinite(intensity):
        intensity = _infer_intensity(sentiment_score, trend_score, event_shock_factor)

    signed_intensity = _to_float(row.get("signed_sentiment_intensity"), default=math.nan)
    if not math.isfinite(signed_intensity):
        signed_intensity = float(sentiment_sign * intensity)
    if sentiment_sign > 0 and signed_intensity < 0:
        signed_intensity = abs(signed_intensity)
    elif sentiment_sign < 0 and signed_intensity > 0:
        signed_intensity = -abs(signed_intensity)

    return {
        "ticker": ticker,
        "rank": _to_int(row.get("rank"), default=0),
        "trend_score": trend_score,
        "sentiment_label": sentiment_label,
        "headline_count": headline_count,
        "sentiment_score": sentiment_score,
        "sentiment_sign": sentiment_sign,
        "sentiment_intensity": float(intensity),
        "signed_sentiment_intensity": float(signed_intensity),
        "event_shock_factor": event_shock_factor,
    }


def _latest_rows_by_ticker(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or df.empty or "ticker" not in df.columns:
        return pd.DataFrame()

    out = df.copy()
    out["ticker"] = out["ticker"].astype(str).str.replace(".NS", "", regex=False).str.strip().str.upper()
    out = out[out["ticker"] != ""]
    if out.empty:
        return out

    ts_col = None
    for candidate in ("timestamp", "time", "datetime", "date", "as_of", "run_date"):
        if candidate in out.columns:
            parsed = pd.to_datetime(out[candidate], errors="coerce")
            if parsed.notna().any():
                out["_sent_ts"] = parsed
                ts_col = "_sent_ts"
                break

    if ts_col is not None:
        out = out.sort_values([ts_col, "ticker"]).drop_duplicates(subset=["ticker"], keep="last")
        out = out.drop(columns=[ts_col], errors="ignore")
    else:
        out = out.drop_duplicates(subset=["ticker"], keep="last")
    return out


def load_company_sentiment_scores(
    project_root: Optional[Path] = None,
    top_companies_limit: int = DEFAULT_TOP_COMPANIES_LIMIT,
) -> pd.DataFrame:
    """
    Load ticker-level sentiment scores for cross-system alpha integration.

    Returns a DataFrame with one row per ticker and at least:
    - ticker
    - sentiment_signal
    - signed_sentiment_intensity
    - sentiment_intensity
    - trend_score
    - sentiment_score
    - headline_count
    """
    root = _project_root(project_root)
    data_dir = root / "data" / "sentiment" / "v3"
    company_trends_path = data_dir / "company_sentiment_trends.parquet"
    weekend_top100_path = data_dir / "weekend_top100_trending_companies.json"
    weekend_top30_path = data_dir / "weekend_top30_trending_companies.json"

    rows: List[Dict[str, Any]] = []

    if company_trends_path.exists():
        try:
            cdf = pd.read_parquet(company_trends_path)
            cdf = _latest_rows_by_ticker(cdf)
            if not cdf.empty:
                records = cdf.to_dict("records")
                for raw in records:
                    clean = _sanitize_company_row(raw if isinstance(raw, dict) else {})
                    if clean is not None:
                        rows.append(clean)
        except Exception:
            pass

    if not rows:
        weekend_payload = _safe_read_json(weekend_top100_path)
        if not weekend_payload:
            weekend_payload = _safe_read_json(weekend_top30_path)
        top_rows = weekend_payload.get("top_companies", []) if isinstance(weekend_payload, dict) else []
        if isinstance(top_rows, list):
            for raw in top_rows:
                clean = _sanitize_company_row(raw if isinstance(raw, dict) else {})
                if clean is not None:
                    rows.append(clean)

    if not rows:
        return pd.DataFrame(
            columns=[
                "ticker",
                "sentiment_signal",
                "signed_sentiment_intensity",
                "sentiment_intensity",
                "trend_score",
                "sentiment_score",
                "headline_count",
                "event_shock_factor",
                "sentiment_sign",
                "sentiment_label",
            ]
        )

    df = pd.DataFrame(rows)
    df = _latest_rows_by_ticker(df)

    df["signed_sentiment_intensity"] = pd.to_numeric(df.get("signed_sentiment_intensity"), errors="coerce").fillna(0.0)
    df["sentiment_intensity"] = pd.to_numeric(df.get("sentiment_intensity"), errors="coerce").fillna(0.0)
    df["trend_score"] = pd.to_numeric(df.get("trend_score"), errors="coerce").fillna(0.0)
    df["sentiment_score"] = pd.to_numeric(df.get("sentiment_score"), errors="coerce").fillna(0.0)
    df["headline_count"] = pd.to_numeric(df.get("headline_count"), errors="coerce").fillna(0).astype(int)
    df["event_shock_factor"] = pd.to_numeric(df.get("event_shock_factor"), errors="coerce").fillna(0.0)
    df["sentiment_sign"] = pd.to_numeric(df.get("sentiment_sign"), errors="coerce").fillna(0).astype(int)
    df["sentiment_label"] = df.get("sentiment_label", "neutral").astype(str).str.lower()

    # Composite ticker-level sentiment signal in [-1, 1].
    raw_signal = (
        0.66 * df["signed_sentiment_intensity"]
        + 0.22 * df["sentiment_score"]
        + 0.12 * df["trend_score"] * df["sentiment_sign"]
    )
    df["sentiment_signal"] = raw_signal.clip(lower=-1.0, upper=1.0)

    df = df.sort_values(
        ["signed_sentiment_intensity", "sentiment_intensity", "trend_score", "headline_count"],
        ascending=[False, False, False, False],
    ).head(max(1, int(top_companies_limit)))

    keep_cols = [
        "ticker",
        "sentiment_signal",
        "signed_sentiment_intensity",
        "sentiment_intensity",
        "trend_score",
        "sentiment_score",
        "headline_count",
        "event_shock_factor",
        "sentiment_sign",
        "sentiment_label",
    ]
    return df[keep_cols].reset_index(drop=True)


def load_sentiment_context(
    now: Optional[datetime] = None,
    project_root: Optional[Path] = None,
    top_companies_limit: int = DEFAULT_TOP_COMPANIES_LIMIT,
) -> Dict[str, Any]:
    """
    Load canonical NS-USO sentiment context for system-level integration.
    """
    root = _project_root(project_root)
    data_dir = root / "data" / "sentiment" / "v3"
    now_ts = now if now is not None else datetime.now(timezone.utc)

    out: Dict[str, Any] = {
        "available": False,
        "status": "missing",
        "message": "",
        "summary_timestamp": None,
        "summary_age_minutes": None,
        "market_timestamp": None,
        "market_age_minutes": None,
        "fresh": False,
        "polarity": 0.0,
        "uncertainty": 0.0,
        "conviction": 1.0,
        "narrative_conflict": 0.0,
        "dominant_theme": "neutral",
        "micro_shift_score": 0.0,
        "change_velocity": 0.0,
        "delta_polarity": 0.0,
        "delta_uncertainty": 0.0,
        "delta_conviction": 0.0,
        "sentiment_bias": 0.0,
        "event_shock_score": 0.0,
        "alert_level": "normal",
        "news_signal_score": 0.0,
        "top_trending_companies": [],
        "negative_trending_companies": [],
        "event_company_impacts": [],
        "negative_trending_company_total": 0,
        "event_company_impact_total": 0,
    }

    summary_path = data_dir / "v3_sentiment_summary.json"
    market_path = data_dir / "market_sentiment_india.parquet"
    event_impact_path = data_dir / "event_company_impact.parquet"

    summary = _safe_read_json(summary_path)
    if summary:
        out["status"] = str(summary.get("status", "") or "").strip().lower() or "unknown"
        out["message"] = str(summary.get("message", "") or "").strip()
        summary_ts = (
            summary.get("timestamp")
            or summary.get("created_timestamp")
            or summary.get("run_date")
            or summary.get("as_of")
        )
        summary_ts_parsed = _parse_ts(summary_ts)
        out["summary_timestamp"] = str(summary_ts) if summary_ts is not None else None
        out["summary_age_minutes"] = _age_minutes(now_ts, summary_ts_parsed)

    ticker_scores = load_company_sentiment_scores(
        project_root=root,
        top_companies_limit=max(1, int(top_companies_limit)),
    )
    if isinstance(ticker_scores, pd.DataFrame) and not ticker_scores.empty:
        rows = ticker_scores.to_dict("records")
        out["top_trending_companies"] = rows[: max(1, int(top_companies_limit))]
        negative_rows = [
            str(r.get("ticker", "")).upper()
            for r in rows
            if _to_int(r.get("sentiment_sign", 0)) < 0
            or str(r.get("sentiment_label", "")).strip().lower() in NEGATIVE_SENTIMENT_LABELS
        ]
        out["negative_trending_company_total"] = int(len(negative_rows))
        out["negative_trending_companies"] = negative_rows[: max(20, int(top_companies_limit))]
        out["news_signal_score"] = float(
            max(
                0.0,
                min(
                    1.0,
                    _to_float(ticker_scores["event_shock_factor"].mean(), 0.0)
                    if "event_shock_factor" in ticker_scores.columns
                    else 0.0,
                ),
            )
        )

    if event_impact_path.exists():
        try:
            edf = pd.read_parquet(event_impact_path)
            if isinstance(edf, pd.DataFrame) and not edf.empty:
                if "impact_score" in edf.columns:
                    ranked = edf.sort_values("impact_score", ascending=False)
                else:
                    ranked = edf
                impacts: List[Dict[str, Any]] = []
                for _, row in ranked.iterrows():
                    ticker = str(row.get("ticker", "") or "").replace(".NS", "").strip().upper()
                    if not ticker:
                        continue
                    impacts.append(
                        {
                            "ticker": ticker,
                            "impact_score": _to_float(row.get("impact_score", 0.0)),
                            "impact_direction": str(row.get("impact_direction", "unknown") or "unknown").lower(),
                            "event_type": str(row.get("event_type", "macro") or "macro").lower(),
                        }
                    )
                out["event_company_impact_total"] = int(len(impacts))
                out["event_company_impacts"] = impacts[: max(20, int(top_companies_limit))]
        except Exception:
            pass

    if market_path.exists():
        try:
            mdf = pd.read_parquet(market_path)
            if isinstance(mdf, pd.DataFrame) and not mdf.empty:
                row = mdf.iloc[-1].to_dict()
                prev = mdf.iloc[-2].to_dict() if len(mdf) >= 2 else {}

                polarity = max(-1.0, min(1.0, _to_float(row.get("polarity", 0.0))))
                uncertainty = max(0.0, min(1.0, _to_float(row.get("uncertainty", 0.0))))
                conviction = max(0.0, _to_float(row.get("conviction", 1.0), 1.0))
                conflict = max(0.0, min(1.0, _to_float(row.get("narrative_conflict", 0.0))))
                dominant_theme = str(row.get("dominant_theme", "neutral") or "neutral")
                micro_shift = max(0.0, min(1.0, _to_float(row.get("micro_shift_score", 0.0))))
                change_velocity = max(0.0, _to_float(row.get("change_velocity", 0.0)))

                delta_polarity = _to_float(row.get("delta_polarity", 0.0))
                delta_uncertainty = _to_float(row.get("delta_uncertainty", 0.0))
                delta_conviction = _to_float(row.get("delta_conviction", 0.0))
                if (
                    delta_polarity == 0.0
                    and delta_uncertainty == 0.0
                    and delta_conviction == 0.0
                    and prev
                ):
                    delta_polarity = polarity - _to_float(prev.get("polarity", 0.0))
                    delta_uncertainty = uncertainty - _to_float(prev.get("uncertainty", 0.0))
                    delta_conviction = conviction - _to_float(prev.get("conviction", 1.0), 1.0)
                    if change_velocity == 0.0:
                        change_velocity = (
                            abs(delta_polarity)
                            + 0.7 * abs(delta_uncertainty)
                            + 0.5 * abs(delta_conviction)
                        )
                    if micro_shift == 0.0:
                        micro_shift = max(0.0, min(1.0, change_velocity * 1.8))

                market_ts = None
                for key in ("timestamp", "date", "as_of", "run_date"):
                    if key in row:
                        market_ts = _parse_ts(row.get(key))
                        if market_ts is not None:
                            break
                if market_ts is None:
                    market_ts = _parse_ts(summary.get("timestamp") if summary else None)

                bearish_component = max(0.0, -polarity)
                shock_score = bearish_component * (0.55 + 0.45 * uncertainty) * (1.0 + 0.5 * min(1.0, conviction))
                shock_score += 0.20 * conflict
                shock_score += 0.30 * micro_shift
                shock_score += 0.18 * min(1.0, change_velocity)
                if delta_polarity < 0:
                    shock_score += 0.14 * min(1.0, abs(delta_polarity))
                shock_score += min(0.30, _to_float(out.get("news_signal_score", 0.0)) * 0.35)
                negative_count = int(_to_int(out.get("negative_trending_company_total", len(out["negative_trending_companies"])), 0))
                event_count = int(_to_int(out.get("event_company_impact_total", len(out["event_company_impacts"])), 0))
                shock_score += min(0.20, negative_count / 80.0)
                shock_score += min(0.20, event_count / 120.0)

                if shock_score >= 0.90:
                    alert_level = "critical"
                elif shock_score >= 0.65:
                    alert_level = "high"
                elif shock_score >= 0.35:
                    alert_level = "elevated"
                else:
                    alert_level = "normal"

                out.update(
                    {
                        "available": True,
                        "polarity": polarity,
                        "uncertainty": uncertainty,
                        "conviction": conviction,
                        "narrative_conflict": conflict,
                        "dominant_theme": dominant_theme,
                        "micro_shift_score": micro_shift,
                        "change_velocity": change_velocity,
                        "delta_polarity": delta_polarity,
                        "delta_uncertainty": delta_uncertainty,
                        "delta_conviction": delta_conviction,
                        "sentiment_bias": polarity,
                        "event_shock_score": float(max(0.0, shock_score)),
                        "alert_level": alert_level,
                        "market_timestamp": market_ts.isoformat() if market_ts is not None else None,
                        "market_age_minutes": _age_minutes(now_ts, market_ts),
                    }
                )
        except Exception:
            pass

    if (out["top_trending_companies"] or out["event_company_impacts"]) and not out["available"]:
        negative_count = int(_to_int(out.get("negative_trending_company_total", len(out["negative_trending_companies"])), 0))
        event_count = int(_to_int(out.get("event_company_impact_total", len(out["event_company_impacts"])), 0))
        fallback_shock = min(
            1.0,
            _to_float(out["news_signal_score"])
            + min(0.35, negative_count / 50.0)
            + min(0.25, event_count / 80.0),
        )
        out["available"] = True
        out["event_shock_score"] = max(_to_float(out["event_shock_score"]), float(fallback_shock))
        if out["alert_level"] == "normal" and fallback_shock >= 0.35:
            out["alert_level"] = "elevated" if fallback_shock < 0.65 else ("high" if fallback_shock < 0.90 else "critical")

    if out["available"] and out.get("status") in {"", "unknown", "missing"}:
        out["status"] = "success"

    freshness_candidates = [
        out.get("summary_age_minutes"),
        out.get("market_age_minutes"),
    ]
    valid_ages: List[float] = [float(x) for x in freshness_candidates if isinstance(x, (int, float))]
    if valid_ages:
        out["fresh"] = min(valid_ages) <= 24.0 * 60.0
    else:
        out["fresh"] = False

    return out


def aggregate_signed_sentiment(values: Iterable[float]) -> float:
    vals = [_to_float(v, default=math.nan) for v in values]
    vals = [v for v in vals if math.isfinite(v)]
    if not vals:
        return 0.0
    return float(sum(vals) / len(vals))
