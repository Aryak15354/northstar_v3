#!/usr/bin/env python3
"""
Produce NS-USO V3 export artifacts from live Northstar data.

This is a guaranteed producer path used when external NS-USO exports are
unavailable. It derives sentiment from real market/macro/narrative artifacts
and appends new rows so sentiment trends stay live intraday.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EXPORT_DIR = PROJECT_ROOT / "ns_uso" / "exports" / "v3"
DEFAULT_TARGET_DIR = PROJECT_ROOT / "data" / "sentiment" / "v3"
WEEKEND_TOP_COMPANIES = 100
POSITIVE_SENTIMENT_LABELS = {"positive", "very_positive", "bullish", "upside"}
NEGATIVE_SENTIMENT_LABELS = {"negative", "very_negative", "bearish", "downside"}


def _safe_read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def _safe_read_parquet(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_parquet(path)
    except Exception:
        return pd.DataFrame()


def _last_market_row(path: Path) -> dict:
    """Read latest sentiment row for micro-shift deltas."""
    df = _safe_read_parquet(path)
    if not isinstance(df, pd.DataFrame) or df.empty:
        return {}
    try:
        return dict(df.iloc[-1].to_dict())
    except Exception:
        return {}


def _load_market_inputs() -> Tuple[Dict[str, dict], dict, dict]:
    market_json = _safe_read_json(PROJECT_ROOT / "data/options/live/market_data_latest.json")
    indices = market_json.get("indices", {}) if isinstance(market_json, dict) else {}

    market_state = _safe_read_parquet(PROJECT_ROOT / "data/processed/market_state.parquet")
    market_state_latest = market_state.iloc[-1].to_dict() if isinstance(market_state, pd.DataFrame) and not market_state.empty else {}

    narrative_change = _safe_read_json(PROJECT_ROOT / "data/processed/latest_narrative_change.json")
    return indices, market_state_latest, narrative_change


def _build_market_sentiment_row(
    indices: Dict[str, dict],
    market_state: dict,
    narrative_change: dict,
    previous_row: dict | None = None,
) -> dict:
    pct_changes = []
    for payload in indices.values():
        try:
            pct_changes.append(float(payload.get("pct_change", 0.0)))
        except Exception:
            continue

    if pct_changes:
        avg_pct = float(np.mean(pct_changes))
        dispersion = float(np.std(pct_changes))
        polarity = float(np.clip(avg_pct / 2.0, -1.0, 1.0))
        uncertainty = float(np.clip((dispersion / 3.0), 0.0, 1.0))
        cohesion = float(np.clip(1.0 - uncertainty * 0.8, 0.0, 1.0))
        conviction = float(np.clip(0.55 + min(abs(avg_pct), 2.5) / 6.0 + cohesion * 0.2, 0.2, 1.8))
    else:
        polarity = 0.0
        uncertainty = 0.35
        cohesion = 0.6
        conviction = 0.6

    macro_score = float(pd.to_numeric(market_state.get("macro_score", 0.0), errors="coerce") or 0.0)
    risk_on_probability = float(pd.to_numeric(market_state.get("risk_on_probability", market_state.get("risk_on", 0.5)), errors="coerce") or 0.5)
    change_count = int(narrative_change.get("change_count", 0) or 0)

    policy_weight = float(np.clip(0.35 + abs(macro_score) * 0.25 + min(change_count, 6) * 0.03, 0.0, 1.0))
    uncertainty = float(np.clip(uncertainty + min(change_count, 5) * 0.02, 0.0, 1.0))

    # Capture subtle intraday shifts from previous cycle in the 5-min loop.
    prev = previous_row or {}
    prev_polarity = float(pd.to_numeric(prev.get("polarity", 0.0), errors="coerce") or 0.0)
    prev_uncertainty = float(pd.to_numeric(prev.get("uncertainty", 0.0), errors="coerce") or 0.0)
    prev_conviction = float(pd.to_numeric(prev.get("conviction", conviction), errors="coerce") or conviction)
    delta_polarity = float(polarity - prev_polarity)
    delta_uncertainty = float(uncertainty - prev_uncertainty)
    delta_conviction = float(conviction - prev_conviction)
    change_velocity = float(abs(delta_polarity) + 0.7 * abs(delta_uncertainty) + 0.5 * abs(delta_conviction))
    micro_shift_score = float(np.clip(change_velocity * 1.8 + min(change_count, 5) * 0.05, 0.0, 1.0))

    narrative_conflict = float(
        np.clip(
            min(1.0, dispersion / 2.5 if pct_changes else 0.25)
            + abs(delta_polarity) * 0.35
            + abs(delta_uncertainty) * 0.25,
            0.0,
            1.0,
        )
    )

    if risk_on_probability >= 0.62:
        dominant_theme = "risk_on_growth"
    elif risk_on_probability <= 0.38:
        dominant_theme = "defensive_rotation"
    elif abs(macro_score) > 0.35:
        dominant_theme = "macro_policy_shift"
    else:
        dominant_theme = "monetary_policy"

    return {
        "date": pd.Timestamp.now(tz="UTC").tz_localize(None),
        "polarity": polarity,
        "conviction": conviction,
        "uncertainty": uncertainty,
        "narrative_cohesion": cohesion,
        "narrative_conflict": narrative_conflict,
        "delta_polarity": delta_polarity,
        "delta_uncertainty": delta_uncertainty,
        "delta_conviction": delta_conviction,
        "change_velocity": change_velocity,
        "micro_shift_score": micro_shift_score,
        "dominant_theme": dominant_theme,
        "policy_weight": policy_weight,
    }


def _build_sector_narratives(indices: Dict[str, dict]) -> pd.DataFrame:
    if not indices:
        return pd.DataFrame(
            [
                {
                    "sector": "BROAD_MARKET",
                    "sentiment_score": 0.0,
                    "conviction": 0.55,
                    "dominant_topics": "market_balance",
                    "narrative_conflict": 0.2,
                }
            ]
        )

    rows = []
    for sector, payload in indices.items():
        try:
            pct = float(payload.get("pct_change", 0.0))
        except Exception:
            pct = 0.0
        sentiment = float(np.clip(pct / 2.0, -1.0, 1.0))
        conflict = float(np.clip(abs(sentiment) * 0.4, 0.0, 1.0))
        conviction = float(np.clip(0.5 + min(abs(pct), 2.0) * 0.15, 0.2, 1.0))
        rows.append(
            {
                "sector": str(sector).upper(),
                "sentiment_score": sentiment,
                "conviction": conviction,
                "dominant_topics": f"{str(sector).lower()}_flow_dynamics",
                "narrative_conflict": conflict,
            }
        )
    return pd.DataFrame(rows)


def _build_policy_context(market_state: dict, narrative_change: dict) -> dict:
    macro_score = float(pd.to_numeric(market_state.get("macro_score", 0.0), errors="coerce") or 0.0)
    momentum = float(pd.to_numeric(market_state.get("macro_momentum", 0.0), errors="coerce") or 0.0)
    change_count = int(narrative_change.get("change_count", 0) or 0)

    if macro_score >= 0.2:
        rbi_stance = "neutral_hawkish" if momentum > 0 else "neutral"
    elif macro_score <= -0.2:
        rbi_stance = "neutral_accommodative"
    else:
        rbi_stance = "neutral"

    flags = []
    if change_count >= 4:
        flags.append("high_narrative_velocity")
    if abs(momentum) > 0.5:
        flags.append("macro_momentum_spike")

    return {
        "rbi_stance": rbi_stance,
        "fiscal_tone": "supportive" if macro_score >= 0 else "neutral",
        "regulatory_stress_flags": flags,
        "expected_half_life": 30,
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }


def _normalize_ticker(value: Any) -> str:
    return str(value or "").strip().upper()


def _extract_focus_avoid_sectors() -> Tuple[List[str], List[str]]:
    daily_path = PROJECT_ROOT / "data/reports/daily_narrative_enhanced.json"
    fallback_path = PROJECT_ROOT / "data/reports/daily_narrative.json"
    focus: List[str] = []
    avoid: List[str] = []

    payload = _safe_read_json(daily_path)
    if not payload:
        payload = _safe_read_json(fallback_path)

    if not payload:
        return focus, avoid

    market_context = payload.get("market_context", {}) if isinstance(payload.get("market_context"), dict) else {}
    key_insights = payload.get("key_insights", {}) if isinstance(payload.get("key_insights"), dict) else {}
    focus_raw = (
        payload.get("focus_sectors")
        or market_context.get("focus_sectors")
        or key_insights.get("focus_sectors")
        or ""
    )
    avoid_raw = (
        payload.get("avoid_sectors")
        or market_context.get("avoid_sectors")
        or key_insights.get("avoid_sectors")
        or ""
    )

    if isinstance(focus_raw, list):
        focus = [str(x).strip().lower() for x in focus_raw if str(x).strip()]
    else:
        focus = [s.strip().lower() for s in str(focus_raw).split(",") if s.strip()]

    if isinstance(avoid_raw, list):
        avoid = [str(x).strip().lower() for x in avoid_raw if str(x).strip()]
    else:
        avoid = [s.strip().lower() for s in str(avoid_raw).split(",") if s.strip()]

    return focus, avoid


def _load_company_inputs() -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "opportunity": _safe_read_parquet(PROJECT_ROOT / "data/processed/opportunity_surface.parquet"),
        "scores": _safe_read_parquet(PROJECT_ROOT / "data/processed/scores.parquet"),
        "cohesive": _safe_read_parquet(PROJECT_ROOT / "data/processed/cohesive_alpha_feed.parquet"),
        "events": _safe_read_parquet(PROJECT_ROOT / "data/processed/narrative_events.parquet"),
        "fingerprints": [],
    }
    fp_payload = _safe_read_json(PROJECT_ROOT / "data/processed/macro_impact/company_fingerprints.json")
    if isinstance(fp_payload, dict):
        rows = fp_payload.get("fingerprints", [])
        if isinstance(rows, list):
            out["fingerprints"] = rows
    return out


def _prep_company_frame(inputs: Dict[str, Any]) -> pd.DataFrame:
    opp = inputs.get("opportunity") if isinstance(inputs.get("opportunity"), pd.DataFrame) else pd.DataFrame()
    scores = inputs.get("scores") if isinstance(inputs.get("scores"), pd.DataFrame) else pd.DataFrame()
    cohesive = inputs.get("cohesive") if isinstance(inputs.get("cohesive"), pd.DataFrame) else pd.DataFrame()

    if opp.empty and scores.empty and cohesive.empty:
        return pd.DataFrame()

    if not scores.empty and "ticker" in scores.columns:
        base = scores.copy()
    elif not opp.empty and "ticker" in opp.columns:
        base = opp.copy()
    else:
        base = cohesive.copy() if "ticker" in cohesive.columns else pd.DataFrame()

    if base.empty or "ticker" not in base.columns:
        return pd.DataFrame()

    base["ticker"] = base["ticker"].map(_normalize_ticker)
    merge_cols = ["ticker", "Industry", "Company Name", "northstar_score", "momentum_score"]
    if not scores.empty and "ticker" in scores.columns:
        s = scores.copy()
        s["ticker"] = s["ticker"].map(_normalize_ticker)
        keep = [c for c in merge_cols if c in s.columns]
        if keep:
            base = base.merge(s[keep], on="ticker", how="left", suffixes=("", "_score"))

    if not opp.empty and "ticker" in opp.columns:
        o = opp.copy()
        o["ticker"] = o["ticker"].map(_normalize_ticker)
        keep = [c for c in ["ticker", "mispricing", "confirmation", "opportunity_type"] if c in o.columns]
        if keep:
            o = o[keep].drop_duplicates("ticker", keep="last")
            base = base.merge(o, on="ticker", how="left", suffixes=("", "_opp"))

    if not cohesive.empty and "ticker" in cohesive.columns:
        c = cohesive.copy()
        c["ticker"] = c["ticker"].map(_normalize_ticker)
        keep = [cname for cname in ["ticker", "cohesive_alpha_score"] if cname in c.columns]
        if keep:
            c = c[keep].drop_duplicates("ticker", keep="last")
            base = base.merge(c, on="ticker", how="left", suffixes=("", "_cohesive"))

    base = base.drop_duplicates("ticker", keep="last")
    return base


def _type_bias(opportunity_type: str) -> float:
    text = str(opportunity_type or "").strip().lower()
    if text == "momentum breakouts":
        return 0.22
    if text == "alpha core":
        return 0.10
    if text == "deteriorations":
        return -0.22
    if text == "value traps":
        return -0.32
    return 0.0


def _event_severity(events_df: pd.DataFrame) -> float:
    if not isinstance(events_df, pd.DataFrame) or events_df.empty:
        return 0.0
    e = events_df.copy().tail(40)
    mag = pd.to_numeric(e.get("magnitude", pd.Series(dtype=float)), errors="coerce").fillna(0.0).abs()
    sig = e.get("significance", pd.Series(dtype=object)).astype(str).str.lower()
    sig_weight = sig.map({"high": 1.0, "medium": 0.6, "low": 0.3}).fillna(0.4)
    if mag.empty:
        return float(np.clip(sig_weight.mean() * 0.25, 0.0, 1.0))
    return float(np.clip((mag.mean() * 0.8) + (sig_weight.mean() * 0.25), 0.0, 1.0))


def _build_company_sentiment_trends(inputs: Dict[str, Any]) -> pd.DataFrame:
    base = _prep_company_frame(inputs)
    if base.empty:
        return pd.DataFrame(
            columns=[
                "timestamp",
                "ticker",
                "industry",
                "sentiment_score",
                "sentiment_label",
                "trend_score",
                "event_shock_factor",
                "headline_count",
                "opportunity_type",
                "source_mode",
            ]
        )

    events_df = inputs.get("events") if isinstance(inputs.get("events"), pd.DataFrame) else pd.DataFrame()
    event_severity = _event_severity(events_df)
    focus_sectors, avoid_sectors = _extract_focus_avoid_sectors()

    out_rows: List[Dict[str, Any]] = []
    now_ts = datetime.now(timezone.utc)

    for _, row in base.iterrows():
        ticker = _normalize_ticker(row.get("ticker", ""))
        if not ticker:
            continue
        industry = str(row.get("Industry", row.get("industry", "Unknown")) or "Unknown").strip()
        industry_l = industry.lower()
        mispricing = float(pd.to_numeric(row.get("mispricing", 0.0), errors="coerce") or 0.0)
        confirmation = float(pd.to_numeric(row.get("confirmation", 0.0), errors="coerce") or 0.0)
        northstar_score = float(pd.to_numeric(row.get("northstar_score", 50.0), errors="coerce") or 50.0)
        momentum_score = float(pd.to_numeric(row.get("momentum_score", 50.0), errors="coerce") or 50.0)
        cohesive_alpha = float(pd.to_numeric(row.get("cohesive_alpha_score", 0.0), errors="coerce") or 0.0)
        opp_type = str(row.get("opportunity_type", "Unknown") or "Unknown")

        alpha_component = np.tanh((northstar_score - 50.0) / 22.0)
        momentum_component = np.tanh((momentum_score - 50.0) / 18.0)
        opp_component = (confirmation - 0.5) * 1.05 + (mispricing - 0.5) * 0.75
        cohesive_component = np.tanh(cohesive_alpha / 2.2)
        type_component = _type_bias(opp_type)

        focus_bias = 0.0
        if any(sec in industry_l for sec in focus_sectors):
            focus_bias += 0.10
        if any(sec in industry_l for sec in avoid_sectors):
            focus_bias -= 0.12

        sentiment_score = float(np.clip(
            0.42 * alpha_component
            + 0.28 * momentum_component
            + 0.20 * opp_component
            + 0.16 * cohesive_component
            + type_component
            + focus_bias,
            -1.0,
            1.0,
        ))

        event_shock_factor = float(np.clip(event_severity * (0.45 + abs(type_component)), 0.0, 1.0))
        trend_score = float(np.clip(
            abs(sentiment_score) * 0.58
            + abs(opp_component) * 0.28
            + event_shock_factor * 0.30,
            0.0,
            1.8,
        ))

        if sentiment_score >= 0.35:
            label = "positive"
        elif sentiment_score <= -0.35:
            label = "negative"
        else:
            label = "neutral"

        headline_count = int(max(1, round(3 + trend_score * 5 + event_shock_factor * 4)))

        out_rows.append(
            {
                "timestamp": now_ts,
                "ticker": ticker,
                "industry": industry,
                "northstar_score": northstar_score,
                "momentum_score": momentum_score,
                "mispricing": mispricing,
                "confirmation": confirmation,
                "cohesive_alpha_score": cohesive_alpha,
                "opportunity_type": opp_type,
                "sentiment_score": sentiment_score,
                "sentiment_label": label,
                "trend_score": trend_score,
                "event_shock_factor": event_shock_factor,
                "headline_count": headline_count,
                "source_mode": "northstar_multi_artifact_fusion",
            }
        )

    out_df = pd.DataFrame(out_rows)
    if out_df.empty:
        return out_df
    out_df = out_df.sort_values(["trend_score", "headline_count"], ascending=False)
    out_df = out_df.drop_duplicates("ticker", keep="first")
    return out_df.head(300).reset_index(drop=True)


def _build_event_company_impact(company_df: pd.DataFrame, inputs: Dict[str, Any]) -> pd.DataFrame:
    if not isinstance(company_df, pd.DataFrame) or company_df.empty:
        return pd.DataFrame(
            columns=[
                "timestamp",
                "event_type",
                "ticker",
                "industry",
                "impact_direction",
                "impact_score",
                "sentiment_label",
                "top_macro_driver",
            ]
        )

    events_df = inputs.get("events") if isinstance(inputs.get("events"), pd.DataFrame) else pd.DataFrame()
    fingerprints = inputs.get("fingerprints", []) if isinstance(inputs.get("fingerprints"), list) else []
    fp_map = {
        _normalize_ticker(row.get("ticker")): str(row.get("top_drivers_text", "") or "")
        for row in fingerprints
        if isinstance(row, dict) and row.get("ticker")
    }

    if isinstance(events_df, pd.DataFrame) and not events_df.empty:
        event_rows = events_df.tail(12).copy()
    else:
        event_rows = pd.DataFrame([{"event_type": "macro_shift", "significance": "medium", "magnitude": 0.25}])

    out_rows: List[Dict[str, Any]] = []
    now_ts = datetime.now(timezone.utc)

    for _, ev in event_rows.iterrows():
        event_type = str(ev.get("event_type", "macro_shift") or "macro_shift")
        magnitude = float(pd.to_numeric(ev.get("magnitude", 0.0), errors="coerce") or 0.0)
        significance = str(ev.get("significance", "medium") or "medium").strip().lower()
        sig_weight = {"high": 1.0, "medium": 0.65, "low": 0.35}.get(significance, 0.5)
        event_weight = float(np.clip(abs(magnitude) * 0.8 + sig_weight * 0.35, 0.15, 1.25))

        for _, row in company_df.head(180).iterrows():
            ticker = _normalize_ticker(row.get("ticker", ""))
            if not ticker:
                continue
            base_trend = float(row.get("trend_score", 0.0) or 0.0)
            sentiment = float(row.get("sentiment_score", 0.0) or 0.0)
            shock_factor = float(row.get("event_shock_factor", 0.0) or 0.0)
            score = float(np.clip(base_trend * (0.55 + shock_factor * 0.45) * event_weight, 0.0, 3.0))
            direction = "downside" if sentiment < -0.15 else ("upside" if sentiment > 0.15 else "mixed")

            out_rows.append(
                {
                    "timestamp": now_ts,
                    "event_type": event_type,
                    "ticker": ticker,
                    "industry": str(row.get("industry", "Unknown") or "Unknown"),
                    "impact_direction": direction,
                    "impact_score": score,
                    "sentiment_label": str(row.get("sentiment_label", "neutral") or "neutral"),
                    "top_macro_driver": fp_map.get(ticker, ""),
                }
            )

    out_df = pd.DataFrame(out_rows)
    if out_df.empty:
        return out_df
    out_df = out_df.sort_values(["impact_score"], ascending=False)
    out_df = out_df.drop_duplicates(subset=["event_type", "ticker"], keep="first")
    return out_df.head(250).reset_index(drop=True)


def _week_ending_friday(today: date) -> date:
    # Monday=0 ... Friday=4.
    offset = (today.weekday() - 4) % 7
    return today - timedelta(days=offset)


def _sentiment_sign(label: str, sentiment_score: float) -> int:
    label_norm = str(label or "").strip().lower()
    if label_norm in POSITIVE_SENTIMENT_LABELS:
        return 1
    if label_norm in NEGATIVE_SENTIMENT_LABELS:
        return -1
    if sentiment_score >= 0.08:
        return 1
    if sentiment_score <= -0.08:
        return -1
    return 0


def _compute_sentiment_intensity(
    sentiment_score: float,
    trend_score: float,
    event_shock_factor: float,
) -> Tuple[float, float]:
    intensity = float(
        np.clip(
            0.62 * abs(sentiment_score)
            + 0.28 * max(0.0, trend_score)
            + 0.10 * max(0.0, event_shock_factor),
            0.0,
            2.0,
        )
    )
    sign = _sentiment_sign("", sentiment_score)
    signed_intensity = float(sign * intensity)
    return intensity, signed_intensity


def _build_weekend_top_report(
    company_df: pd.DataFrame,
    event_df: pd.DataFrame,
    max_companies: int = WEEKEND_TOP_COMPANIES,
) -> Dict[str, Any]:
    now_utc = datetime.now(timezone.utc)
    today = now_utc.date()

    if isinstance(company_df, pd.DataFrame) and not company_df.empty:
        c = company_df.copy()
        c["sentiment_label"] = c.get("sentiment_label", "neutral").astype(str).str.lower()
        c["sentiment_score"] = pd.to_numeric(c.get("sentiment_score", 0.0), errors="coerce").fillna(0.0)
        c["trend_score"] = pd.to_numeric(c.get("trend_score", 0.0), errors="coerce").fillna(0.0)
        c["event_shock_factor"] = pd.to_numeric(c.get("event_shock_factor", 0.0), errors="coerce").fillna(0.0)
        c["headline_count"] = pd.to_numeric(c.get("headline_count", 0), errors="coerce").fillna(0).astype(int)

        signs = []
        intensities = []
        signed_intensities = []
        for _, row in c.iterrows():
            sentiment_label = str(row.get("sentiment_label", "neutral") or "neutral").strip().lower()
            sentiment_score = float(row.get("sentiment_score", 0.0) or 0.0)
            trend_score = float(row.get("trend_score", 0.0) or 0.0)
            event_shock_factor = float(row.get("event_shock_factor", 0.0) or 0.0)
            sign = _sentiment_sign(sentiment_label, sentiment_score)
            intensity, signed_intensity = _compute_sentiment_intensity(
                sentiment_score=sentiment_score,
                trend_score=trend_score,
                event_shock_factor=event_shock_factor,
            )
            # Preserve explicit label polarity when present.
            signed_intensity = float((1 if sign > 0 else -1 if sign < 0 else 0) * intensity)
            signs.append(sign)
            intensities.append(intensity)
            signed_intensities.append(signed_intensity)

        c["sentiment_sign"] = signs
        c["sentiment_intensity"] = intensities
        c["signed_sentiment_intensity"] = signed_intensities
        c["ticker"] = c.get("ticker", "").map(_normalize_ticker)
        c = c[c["ticker"].astype(str).str.len() > 0].copy()
        c = c.sort_values(
            ["signed_sentiment_intensity", "sentiment_intensity", "trend_score", "headline_count"],
            ascending=[False, False, False, False],
        ).drop_duplicates("ticker", keep="first")
    else:
        c = pd.DataFrame(
            columns=[
                "ticker",
                "industry",
                "sentiment_label",
                "trend_score",
                "headline_count",
                "event_shock_factor",
                "opportunity_type",
                "sentiment_score",
                "sentiment_sign",
                "sentiment_intensity",
                "signed_sentiment_intensity",
            ]
        )

    event_type_map: Dict[str, str] = {}
    if isinstance(event_df, pd.DataFrame) and not event_df.empty and {"ticker", "event_type"}.issubset(event_df.columns):
        for _, row in event_df.iterrows():
            ticker = _normalize_ticker(row.get("ticker", ""))
            if ticker and ticker not in event_type_map:
                event_type_map[ticker] = str(row.get("event_type", "macro_shift") or "macro_shift")

    top_companies: List[Dict[str, Any]] = []
    for rank, (_, row) in enumerate(c.head(max(1, int(max_companies))).iterrows(), start=1):
        ticker = _normalize_ticker(row.get("ticker", ""))
        sentiment_label = str(row.get("sentiment_label", "neutral") or "neutral").strip().lower()
        sentiment_score = float(row.get("sentiment_score", 0.0) or 0.0)
        sentiment_sign = int(row.get("sentiment_sign", _sentiment_sign(sentiment_label, sentiment_score)) or 0)
        sentiment_intensity = float(row.get("sentiment_intensity", 0.0) or 0.0)
        signed_sentiment_intensity = float(
            row.get("signed_sentiment_intensity", float(sentiment_sign * sentiment_intensity)) or 0.0
        )
        top_companies.append(
            {
                "ticker": ticker,
                "rank": int(rank),
                "industry": str(row.get("industry", "Unknown") or "Unknown"),
                "sentiment_label": sentiment_label,
                "sentiment_score": sentiment_score,
                "sentiment_sign": int(sentiment_sign),
                "sentiment_intensity": sentiment_intensity,
                "signed_sentiment_intensity": signed_sentiment_intensity,
                "trend_score": float(row.get("trend_score", 0.0) or 0.0),
                "headline_count": int(row.get("headline_count", 0) or 0),
                "event_shock_factor": float(row.get("event_shock_factor", 0.0) or 0.0),
                "opportunity_type": str(row.get("opportunity_type", "Unknown") or "Unknown"),
                "primary_event_type": event_type_map.get(ticker, "macro_shift"),
            }
        )

    week_ending = _week_ending_friday(today)
    trading_days = [week_ending - timedelta(days=i) for i in range(4, -1, -1)]

    positives = sum(1 for row in top_companies if int(row.get("sentiment_sign", 0) or 0) > 0)
    negatives = sum(1 for row in top_companies if int(row.get("sentiment_sign", 0) or 0) < 0)

    return {
        "timestamp": now_utc.isoformat(),
        "is_weekend": bool(today.weekday() >= 5),
        "week_ending": week_ending.isoformat(),
        "trading_days_window": [d.isoformat() for d in trading_days],
        "max_companies": int(max_companies),
        "ranking_method": "signed_sentiment_intensity_desc",
        "top_companies": top_companies,
        "counts": {
            "total": int(len(top_companies)),
            "positive": int(positives),
            "negative": int(negatives),
            "neutral": int(len(top_companies) - positives - negatives),
        },
        "generated_mode": "rolling_weekly_refresh",
    }


def _build_balanced_top_subset(weekend_report: Dict[str, Any], max_companies: int = 30) -> Dict[str, Any]:
    if not isinstance(weekend_report, dict):
        return {}
    rows = weekend_report.get("top_companies", [])
    if not isinstance(rows, list) or not rows:
        out = dict(weekend_report)
        out["top_companies"] = []
        out["max_companies"] = int(max_companies)
        out["ranking_method"] = "balanced_signed_intensity_round_robin"
        out["counts"] = {"total": 0, "positive": 0, "negative": 0, "neutral": 0}
        return out

    positive_rows: List[Dict[str, Any]] = []
    negative_rows: List[Dict[str, Any]] = []
    neutral_rows: List[Dict[str, Any]] = []

    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            sign = int(row.get("sentiment_sign", 0) or 0)
        except Exception:
            sign = 0
        if sign > 0:
            positive_rows.append(row)
        elif sign < 0:
            negative_rows.append(row)
        else:
            neutral_rows.append(row)

    # More negative (lower signed intensity) gets higher downside priority.
    negative_rows = sorted(
        negative_rows,
        key=lambda r: float(r.get("signed_sentiment_intensity", 0.0) or 0.0),
    )

    ordered: List[Dict[str, Any]] = []
    max_rows = max(1, int(max_companies))
    seed_positive = positive_rows[:max_rows]
    seed_negative = negative_rows[:max_rows]
    seed_neutral = neutral_rows[:max_rows]
    for idx in range(max(len(seed_positive), len(seed_negative), len(seed_neutral))):
        if idx < len(seed_positive):
            ordered.append(seed_positive[idx])
        if idx < len(seed_negative):
            ordered.append(seed_negative[idx])
        if idx < len(seed_neutral):
            ordered.append(seed_neutral[idx])
        if len(ordered) >= max_rows:
            break
    if len(ordered) < max_rows:
        ordered.extend(positive_rows[len(seed_positive):])
    if len(ordered) < max_rows:
        ordered.extend(negative_rows[len(seed_negative):])
    if len(ordered) < max_rows:
        ordered.extend(neutral_rows[len(seed_neutral):])

    ordered = ordered[:max_rows]
    top_companies: List[Dict[str, Any]] = []
    for rank, row in enumerate(ordered, start=1):
        row_copy = dict(row)
        row_copy["rank"] = int(rank)
        top_companies.append(row_copy)

    positives = sum(1 for row in top_companies if int(row.get("sentiment_sign", 0) or 0) > 0)
    negatives = sum(1 for row in top_companies if int(row.get("sentiment_sign", 0) or 0) < 0)

    out = dict(weekend_report)
    out["top_companies"] = top_companies
    out["max_companies"] = int(max_companies)
    out["ranking_method"] = "balanced_signed_intensity_round_robin"
    out["counts"] = {
        "total": int(len(top_companies)),
        "positive": int(positives),
        "negative": int(negatives),
        "neutral": int(len(top_companies) - positives - negatives),
    }
    return out


def _append_market_sentiment(path: Path, new_row: dict, max_rows: int = 2000) -> int:
    existing = _safe_read_parquet(path)
    new_df = pd.DataFrame([new_row])
    if isinstance(existing, pd.DataFrame) and not existing.empty:
        df = pd.concat([existing, new_df], ignore_index=True)
    else:
        df = new_df

    if "date" in df.columns:
        df["date"] = (
            pd.to_datetime(df["date"], errors="coerce", utc=True)
            .dt.tz_localize(None)
        )
        df = df.dropna(subset=["date"]).sort_values("date").drop_duplicates(subset=["date"], keep="last")
    df = df.tail(max_rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
    return len(df)


def _write_outputs(export_dir: Path, target_dir: Path) -> dict:
    indices, market_state, narrative_change = _load_market_inputs()
    prev_export = _last_market_row(export_dir / "market_sentiment_india.parquet")
    prev_target = _last_market_row(target_dir / "market_sentiment_india.parquet")
    previous_row = prev_export if prev_export else prev_target
    market_row = _build_market_sentiment_row(indices, market_state, narrative_change, previous_row=previous_row)
    sectors = _build_sector_narratives(indices)
    policy_context = _build_policy_context(market_state, narrative_change)

    company_inputs = _load_company_inputs()
    company_trends = _build_company_sentiment_trends(company_inputs)
    event_impact = _build_event_company_impact(company_trends, company_inputs)
    weekend_top100 = _build_weekend_top_report(
        company_trends,
        event_impact,
        max_companies=WEEKEND_TOP_COMPANIES,
    )
    weekend_top30 = _build_balanced_top_subset(weekend_top100, max_companies=30)

    export_dir.mkdir(parents=True, exist_ok=True)
    target_dir.mkdir(parents=True, exist_ok=True)

    market_rows_export = _append_market_sentiment(export_dir / "market_sentiment_india.parquet", market_row)
    market_rows_target = _append_market_sentiment(target_dir / "market_sentiment_india.parquet", market_row)

    sectors.to_parquet(export_dir / "sector_narratives.parquet", index=False)
    sectors.to_parquet(target_dir / "sector_narratives.parquet", index=False)

    company_trends.to_parquet(export_dir / "company_sentiment_trends.parquet", index=False)
    company_trends.to_parquet(target_dir / "company_sentiment_trends.parquet", index=False)

    event_impact.to_parquet(export_dir / "event_company_impact.parquet", index=False)
    event_impact.to_parquet(target_dir / "event_company_impact.parquet", index=False)

    (export_dir / "policy_context.json").write_text(json.dumps(policy_context, indent=2))
    (target_dir / "policy_context.json").write_text(json.dumps(policy_context, indent=2))

    # Write both names for backward compatibility with existing consumers.
    (export_dir / "weekend_top100_trending_companies.json").write_text(json.dumps(weekend_top100, indent=2))
    (target_dir / "weekend_top100_trending_companies.json").write_text(json.dumps(weekend_top100, indent=2))
    (export_dir / "weekend_top30_trending_companies.json").write_text(json.dumps(weekend_top30, indent=2))
    (target_dir / "weekend_top30_trending_companies.json").write_text(json.dumps(weekend_top30, indent=2))

    top_negative = []
    top_positive = []
    if isinstance(company_trends, pd.DataFrame) and not company_trends.empty:
        neg_df = company_trends[company_trends["sentiment_label"] == "negative"].sort_values("trend_score", ascending=False)
        pos_df = company_trends[company_trends["sentiment_label"] == "positive"].sort_values("trend_score", ascending=False)
        top_negative = [str(x) for x in neg_df["ticker"].head(10).tolist()]
        top_positive = [str(x) for x in pos_df["ticker"].head(10).tolist()]

    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "success",
        "message": "Generated NS-USO V3 exports from live market/macro/narrative artifacts.",
        "data_available": True,
        "source_mode": "northstar_live_fallback",
        "micro_shift_score": float(market_row.get("micro_shift_score", 0.0) or 0.0),
        "change_velocity": float(market_row.get("change_velocity", 0.0) or 0.0),
        "narrative_conflict": float(market_row.get("narrative_conflict", 0.0) or 0.0),
        "rows_market_export": market_rows_export,
        "rows_market_target": market_rows_target,
        "rows_sector": int(len(sectors)),
        "rows_company_trends": int(len(company_trends)),
        "rows_event_company_impact": int(len(event_impact)),
        "weekend_top30_count": int(len(weekend_top30.get("top_companies", []))),
        "weekend_top100_count": int(len(weekend_top100.get("top_companies", []))),
        "weekend_report_generated": bool(weekend_top100.get("is_weekend", False)),
        "top_negative_companies": top_negative,
        "top_positive_companies": top_positive,
    }
    (export_dir / "v3_sentiment_summary.json").write_text(json.dumps(summary, indent=2))
    (target_dir / "v3_sentiment_summary.json").write_text(json.dumps(summary, indent=2))
    return summary


def main() -> int:
    summary = _write_outputs(DEFAULT_EXPORT_DIR, DEFAULT_TARGET_DIR)
    print(
        "✅ Produced NS-USO V3 exports "
        f"(market_rows={summary['rows_market_target']}, sector_rows={summary['rows_sector']}, "
        f"company_rows={summary['rows_company_trends']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
