#!/usr/bin/env python3
"""
🧠 V3 SENTIMENT PANEL
Brain Window enhancement for displaying V3 sentiment context

This panel:
✅ Shows India semantic context (read-only)
✅ Displays regime confidence with sentiment adjustments
✅ Shows narrative health indicators
✅ Never creates actionable signals
✅ Pure observational intelligence
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st


TOP_COMPANIES_LIMIT = 100
POSITIVE_SENTIMENT_LABELS = {"positive", "very_positive", "bullish"}
NEGATIVE_SENTIMENT_LABELS = {"negative", "very_negative", "bearish", "downside"}


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return float(default)
        if isinstance(value, float) and np.isnan(value):
            return float(default)
        return float(value)
    except Exception:
        return float(default)


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


def _sentiment_intensity(sentiment_score: float, trend_score: float, event_shock_factor: float) -> float:
    return float(
        max(
            0.0,
            0.62 * abs(sentiment_score)
            + 0.28 * max(0.0, trend_score)
            + 0.10 * max(0.0, event_shock_factor),
        )
    )


def _dedupe_companies(rows: list[dict]) -> list[dict]:
    """Deduplicate ticker rows keeping strongest signed intensity, then intensity."""
    if not rows:
        return []
    df = pd.DataFrame(rows)
    if df.empty or "ticker" not in df.columns:
        return rows
    df["ticker"] = df["ticker"].astype(str).str.replace(".NS", "", regex=False).str.upper().str.strip()
    df = df[df["ticker"] != ""]
    if df.empty:
        return []
    df["signed_sentiment_intensity"] = pd.to_numeric(df.get("signed_sentiment_intensity", 0.0), errors="coerce").fillna(0.0)
    df["sentiment_intensity"] = pd.to_numeric(df.get("sentiment_intensity", 0.0), errors="coerce").fillna(0.0)
    df = df.sort_values(
        ["signed_sentiment_intensity", "sentiment_intensity", "headline_count"],
        ascending=[False, False, False],
    )
    df = df.drop_duplicates(subset=["ticker"], keep="first")
    return df.to_dict("records")


class V3SentimentPanel:
    """V3 Sentiment Panel for Brain Window"""

    def __init__(self) -> None:
        self.name = "V3 Sentiment Context"
        self.project_root = Path(__file__).resolve().parents[3]
        self.data_dir = self.project_root / "data/sentiment/v3"

    def load_sentiment_data(self) -> Dict[str, Any]:
        """Load V3 sentiment data from artifacts."""

        market_file = self.data_dir / "market_sentiment_india.parquet"
        sector_file = self.data_dir / "sector_narratives.parquet"
        policy_file = self.data_dir / "policy_context.json"
        summary_file = self.data_dir / "v3_sentiment_summary.json"
        company_file = self.data_dir / "company_sentiment_trends.parquet"
        event_file = self.data_dir / "event_company_impact.parquet"
        weekend_files = [
            self.data_dir / "weekend_top100_trending_companies.json",
            self.data_dir / "weekend_top30_trending_companies.json",
        ]

        market_df = pd.DataFrame()
        sector_df = pd.DataFrame()
        company_df = pd.DataFrame()
        event_df = pd.DataFrame()
        policy_context: Dict[str, Any] = {}
        summary: Dict[str, Any] = {}
        weekend_report: Dict[str, Any] = {}
        top_snapshot_source = "none"

        if market_file.exists():
            try:
                market_df = pd.read_parquet(market_file)
            except Exception:
                market_df = pd.DataFrame()

        if sector_file.exists():
            try:
                sector_df = pd.read_parquet(sector_file)
            except Exception:
                sector_df = pd.DataFrame()

        if policy_file.exists():
            try:
                with open(policy_file, "r") as f:
                    policy_context = json.load(f)
            except Exception:
                policy_context = {}

        if summary_file.exists():
            try:
                with open(summary_file, "r") as f:
                    summary = json.load(f)
            except Exception:
                summary = {}

        if company_file.exists():
            try:
                company_df = pd.read_parquet(company_file)
            except Exception:
                company_df = pd.DataFrame()

        if event_file.exists():
            try:
                event_df = pd.read_parquet(event_file)
            except Exception:
                event_df = pd.DataFrame()

        for weekend_file in weekend_files:
            if not weekend_file.exists():
                continue
            try:
                with open(weekend_file, "r") as f:
                    weekend_report = json.load(f)
                if isinstance(weekend_report, dict):
                    break
            except Exception:
                weekend_report = {}

        market_sentiment = None
        if not market_df.empty:
            try:
                market_sentiment = market_df.iloc[-1].to_dict()
            except Exception:
                market_sentiment = None

        sector_narratives = []
        if not sector_df.empty:
            try:
                sector_narratives = sector_df.to_dict("records")
            except Exception:
                sector_narratives = []

        # Metadata for freshness diagnostics.
        summary_status = str(summary.get("status", "")).strip().lower() if isinstance(summary, dict) else ""
        summary_message = str(summary.get("message", "")).strip() if isinstance(summary, dict) else ""
        # Backward compatibility: older NS-USO exports don't provide status/message.
        if not summary_status and isinstance(summary, dict):
            if summary.get("artifacts_created") or summary.get("processing_summary"):
                summary_status = "success"
        if not summary_message and isinstance(summary, dict):
            created_ts = summary.get("created_timestamp") or summary.get("timestamp") or summary.get("run_date")
            if created_ts:
                summary_message = f"Summary updated at {created_ts}"
        market_rows = int(len(market_df)) if isinstance(market_df, pd.DataFrame) else 0

        market_last_date = None
        staleness_days = None
        if isinstance(market_df, pd.DataFrame) and not market_df.empty:
            date_col = next((c for c in ["date", "Date", "timestamp"] if c in market_df.columns), None)
            if date_col:
                dts = pd.to_datetime(market_df[date_col], errors="coerce").dropna()
                if not dts.empty:
                    market_last_date = dts.max().to_pydatetime()
                    staleness_days = max(0, (datetime.now() - market_last_date).days)

        top_companies = []
        if isinstance(weekend_report, dict):
            raw_top = weekend_report.get("top_companies")
            if isinstance(raw_top, list):
                top_companies = raw_top
                top_snapshot_source = "weekend_snapshot"
        if not top_companies and isinstance(company_df, pd.DataFrame) and not company_df.empty:
            ranked = company_df.copy()
            ranked["sentiment_label"] = ranked.get("sentiment_label", "neutral").astype(str).str.lower()
            ranked["sentiment_score"] = pd.to_numeric(ranked.get("sentiment_score", 0.0), errors="coerce").fillna(0.0)
            ranked["trend_score"] = pd.to_numeric(ranked.get("trend_score", 0.0), errors="coerce").fillna(0.0)
            ranked["event_shock_factor"] = pd.to_numeric(ranked.get("event_shock_factor", 0.0), errors="coerce").fillna(0.0)
            ranked["headline_count"] = pd.to_numeric(ranked.get("headline_count", 0), errors="coerce").fillna(0).astype(int)
            if "sentiment_sign" in ranked.columns:
                ranked["sentiment_sign"] = pd.to_numeric(ranked["sentiment_sign"], errors="coerce").fillna(0).astype(int)
            else:
                ranked["sentiment_sign"] = ranked.apply(
                    lambda row: _sentiment_sign(
                        str(row.get("sentiment_label", "neutral") or "neutral"),
                        _to_float(row.get("sentiment_score", 0.0)),
                    ),
                    axis=1,
                )
            if "sentiment_intensity" in ranked.columns:
                ranked["sentiment_intensity"] = pd.to_numeric(ranked["sentiment_intensity"], errors="coerce")
            else:
                ranked["sentiment_intensity"] = np.nan
            ranked["sentiment_intensity"] = ranked.apply(
                lambda row: (
                    _to_float(row.get("sentiment_intensity"), np.nan)
                    if pd.notna(row.get("sentiment_intensity"))
                    else _sentiment_intensity(
                        _to_float(row.get("sentiment_score", 0.0)),
                        _to_float(row.get("trend_score", 0.0)),
                        _to_float(row.get("event_shock_factor", 0.0)),
                    )
                ),
                axis=1,
            )
            if "signed_sentiment_intensity" in ranked.columns:
                ranked["signed_sentiment_intensity"] = pd.to_numeric(
                    ranked["signed_sentiment_intensity"], errors="coerce"
                )
            else:
                ranked["signed_sentiment_intensity"] = np.nan
            ranked["signed_sentiment_intensity"] = ranked.apply(
                lambda row: (
                    _to_float(row.get("signed_sentiment_intensity"), np.nan)
                    if pd.notna(row.get("signed_sentiment_intensity"))
                    else _to_float(row.get("sentiment_sign", 0)) * _to_float(row.get("sentiment_intensity", 0.0))
                ),
                axis=1,
            )
            ranked = ranked.sort_values(
                ["signed_sentiment_intensity", "sentiment_intensity", "trend_score", "headline_count"],
                ascending=[False, False, False, False],
            )
            top_companies = ranked.head(TOP_COMPANIES_LIMIT).to_dict("records")
            top_snapshot_source = "company_trends_latest"

        top_companies = _dedupe_companies(top_companies)[:TOP_COMPANIES_LIMIT]

        return {
            "market_sentiment": market_sentiment,
            "market_df": market_df,
            "sector_narratives": sector_narratives,
            "company_df": company_df,
            "event_df": event_df,
            "top_companies": top_companies,
            "weekend_report": weekend_report,
            "top_snapshot_source": top_snapshot_source,
            "policy_context": policy_context,
            "summary": summary,
            "summary_status": summary_status,
            "summary_message": summary_message,
            "market_rows": market_rows,
            "company_rows": int(len(company_df)) if isinstance(company_df, pd.DataFrame) else 0,
            "event_rows": int(len(event_df)) if isinstance(event_df, pd.DataFrame) else 0,
            "market_last_date": market_last_date,
            "staleness_days": staleness_days,
            "data_available": market_sentiment is not None,
        }

    def render_india_semantic_context(self, data: Dict[str, Any]) -> None:
        """Render India Semantic Context panel."""

        st.subheader("🇮🇳 India Semantic Context")

        if not data["data_available"]:
            st.info("No V3 sentiment data available yet.")
            return

        market = data["market_sentiment"] or {}
        policy = data["policy_context"] or {}

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric(
                "RBI Stance",
                str(policy.get("rbi_stance", "neutral")).replace("_", " ").title(),
                help="Current RBI monetary policy stance",
            )

        with col2:
            theme = str(market.get("dominant_theme", "neutral")).replace("_", " ").title()
            st.metric(
                "Dominant Theme",
                theme,
                help="Primary narrative theme in India markets",
            )

        with col3:
            uncertainty = float(market.get("uncertainty", 0.0) or 0.0)
            st.metric(
                "Uncertainty Gauge",
                f"{uncertainty:.1%}",
                help="Market narrative uncertainty level",
            )

        policy_weight = float(market.get("policy_weight", 0.0) or 0.0)
        if policy_weight > 0.5:
            st.info(f"🏛️ High policy influence detected ({policy_weight:.1%})")

        stress_flags = policy.get("regulatory_stress_flags", [])
        if stress_flags:
            st.warning(f"⚠️ Regulatory stress: {', '.join(stress_flags)}")

    def render_regime_confidence(self, data: Dict[str, Any]) -> None:
        """Render Regime Confidence panel."""

        st.subheader("📊 Regime Confidence")

        if not data["data_available"]:
            st.info("Price-driven confidence only (no sentiment data).")
            return

        market = data["market_sentiment"] or {}

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Price Confidence", "Market-driven")

        with col2:
            conviction = float(market.get("conviction", 0.0) or 0.0)
            st.metric("Sentiment Conviction", f"{conviction:.2f}x")

        with col3:
            cohesion = float(market.get("narrative_cohesion", 0.0) or 0.0)
            st.metric("Narrative Cohesion", f"{cohesion:.1%}")

    def render_narrative_health(self, data: Dict[str, Any]) -> None:
        """Render Narrative Health panel."""

        st.subheader("🧬 Narrative Health")

        if not data["data_available"]:
            st.info("No narrative health data available yet.")
            return

        market = data["market_sentiment"] or {}
        policy = data["policy_context"] or {}

        col1, col2, col3 = st.columns(3)

        with col1:
            polarity = float(market.get("polarity", 0.0) or 0.0)
            st.metric("Polarity", f"{polarity:+.2f}")

        with col2:
            uncertainty = float(market.get("uncertainty", 0.0) or 0.0)
            st.metric("Uncertainty", f"{uncertainty:.1%}")

        with col3:
            flags = policy.get("regulatory_stress_flags", [])
            st.metric("Regulatory Flags", f"{len(flags)}")

    def render_sentiment_trend(self, data: Dict[str, Any]) -> None:
        """Render sentiment trend chart if data exists."""

        market_df: pd.DataFrame = data.get("market_df", pd.DataFrame())
        if market_df.empty:
            return

        df = market_df.copy()
        date_col = None
        for cand in ["date", "Date", "timestamp"]:
            if cand in df.columns:
                date_col = cand
                break
        if not date_col:
            return

        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        df = df.dropna(subset=[date_col]).sort_values(date_col)
        if df.empty:
            return

        y_cols = [c for c in ["polarity", "conviction", "uncertainty"] if c in df.columns]
        if not y_cols:
            return

        # Single-row data is common early on; show a clean "snapshot" instead of
        # an empty-looking line chart.
        if df[date_col].nunique() <= 1:
            latest = df.iloc[-1]
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Polarity", f"{float(latest.get('polarity', 0.0) or 0.0):+.3f}")
            c2.metric("Conviction", f"{float(latest.get('conviction', 0.0) or 0.0):.2f}x")
            c3.metric("Uncertainty", f"{float(latest.get('uncertainty', 0.0) or 0.0):.1%}")
            c4.metric("Cohesion", f"{float(latest.get('narrative_cohesion', 0.0) or 0.0):.1%}")

            # Gauge-style indicators
            fig = go.Figure()
            fig.add_trace(
                go.Indicator(
                    mode="gauge+number",
                    value=float(latest.get("uncertainty", 0.0) or 0.0) * 100.0,
                    title={"text": "Uncertainty"},
                    gauge={"axis": {"range": [0, 100]}, "bar": {"color": "#f39c12"}},
                    domain={"x": [0.0, 0.32], "y": [0, 1]},
                )
            )
            fig.add_trace(
                go.Indicator(
                    mode="gauge+number",
                    value=float(latest.get("narrative_cohesion", 0.0) or 0.0) * 100.0,
                    title={"text": "Cohesion"},
                    gauge={"axis": {"range": [0, 100]}, "bar": {"color": "#3B82F6"}},
                    domain={"x": [0.34, 0.66], "y": [0, 1]},
                )
            )
            fig.add_trace(
                go.Indicator(
                    mode="gauge+number",
                    value=float(latest.get("conviction", 0.0) or 0.0) * 100.0,
                    title={"text": "Conviction"},
                    gauge={"axis": {"range": [0, 200]}, "bar": {"color": "#22c55e"}},
                    domain={"x": [0.68, 1.0], "y": [0, 1]},
                )
            )
            fig.update_layout(height=240, margin=dict(l=10, r=10, t=20, b=10))
            st.plotly_chart(fig, width="stretch", key="v3_sentiment_panel_chart_449")
            return

        fig = go.Figure()
        for col in y_cols:
            fig.add_trace(go.Scatter(x=df[date_col], y=df[col], mode="lines", name=col.title()))

        fig.update_layout(
            height=280,
            margin=dict(l=10, r=10, t=30, b=10),
            title="Sentiment Trend",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )

        st.plotly_chart(fig, width="stretch", key="v3_sentiment_panel_chart_463")

    def render_sector_narratives(self, data: Dict[str, Any]) -> None:
        sector = data.get("sector_narratives") or []
        if not sector:
            return
        try:
            df = pd.DataFrame(sector)
        except Exception:
            return
        if df.empty or "sector" not in df.columns:
            return

        st.subheader("🧭 Sector Narrative Map")
        for c in ["sentiment_score", "conviction", "narrative_conflict"]:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")
        df = df.dropna(subset=["sentiment_score"]).sort_values("sentiment_score", ascending=False)

        fig = px.bar(
            df,
            x="sector",
            y="sentiment_score",
            color="conviction" if "conviction" in df.columns else None,
            title="Sector Sentiment Score (color = conviction)",
            color_continuous_scale="Viridis",
        )
        fig.update_layout(height=320, margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(fig, width="stretch", key="v3_sentiment_panel_chart_491")

        if "narrative_conflict" in df.columns:
            fig2 = px.bar(
                df.sort_values("narrative_conflict", ascending=False),
                x="sector",
                y="narrative_conflict",
                title="Narrative Conflict (Higher = More Mixed Signals)",
            )
            fig2.update_layout(height=260, margin=dict(l=10, r=10, t=30, b=10))
            st.plotly_chart(fig2, width="stretch", key="v3_sentiment_panel_chart_501")

    def render_company_news_trends(self, data: Dict[str, Any]) -> None:
        top_companies = data.get("top_companies") or []
        if not top_companies:
            return

        try:
            df = pd.DataFrame(top_companies)
        except Exception:
            return
        if df.empty or "ticker" not in df.columns:
            return

        df["sentiment_label"] = df.get("sentiment_label", "neutral").astype(str).str.lower()
        df["sentiment_score"] = pd.to_numeric(df.get("sentiment_score", 0.0), errors="coerce").fillna(0.0)
        df["trend_score"] = pd.to_numeric(df.get("trend_score", 0.0), errors="coerce").fillna(0.0)
        df["event_shock_factor"] = pd.to_numeric(df.get("event_shock_factor", 0.0), errors="coerce").fillna(0.0)
        df["headline_count"] = pd.to_numeric(df.get("headline_count", 0), errors="coerce").fillna(0).astype(int)
        if "sentiment_sign" in df.columns:
            df["sentiment_sign"] = pd.to_numeric(df["sentiment_sign"], errors="coerce").fillna(0).astype(int)
        else:
            df["sentiment_sign"] = df.apply(
                lambda row: _sentiment_sign(
                    str(row.get("sentiment_label", "neutral") or "neutral"),
                    _to_float(row.get("sentiment_score", 0.0)),
                ),
                axis=1,
            )
        if "sentiment_intensity" in df.columns:
            df["sentiment_intensity"] = pd.to_numeric(df["sentiment_intensity"], errors="coerce")
        else:
            df["sentiment_intensity"] = np.nan
        df["sentiment_intensity"] = df.apply(
            lambda row: (
                _to_float(row.get("sentiment_intensity"), np.nan)
                if pd.notna(row.get("sentiment_intensity"))
                else _sentiment_intensity(
                    _to_float(row.get("sentiment_score", 0.0)),
                    _to_float(row.get("trend_score", 0.0)),
                    _to_float(row.get("event_shock_factor", 0.0)),
                )
            ),
            axis=1,
        )
        if "signed_sentiment_intensity" in df.columns:
            df["signed_sentiment_intensity"] = pd.to_numeric(df["signed_sentiment_intensity"], errors="coerce")
        else:
            df["signed_sentiment_intensity"] = np.nan
        df["signed_sentiment_intensity"] = df.apply(
            lambda row: (
                _to_float(row.get("signed_sentiment_intensity"), np.nan)
                if pd.notna(row.get("signed_sentiment_intensity"))
                else _to_float(row.get("sentiment_sign", 0)) * _to_float(row.get("sentiment_intensity", 0.0))
            ),
            axis=1,
        )
        df = df.sort_values(
            ["signed_sentiment_intensity", "sentiment_intensity", "trend_score", "headline_count"],
            ascending=[False, False, False, False],
        )
        df = pd.DataFrame(_dedupe_companies(df.to_dict("records"))).head(TOP_COMPANIES_LIMIT)

        st.subheader("🏢 Company News & Sentiment (Top 100)")
        snapshot_source = str(data.get("top_snapshot_source", "unknown") or "unknown")
        st.caption(f"Snapshot source: `{snapshot_source}`")

        positives = int((df["sentiment_sign"] > 0).sum())
        negatives = int((df["sentiment_sign"] < 0).sum())
        neutrals = int((df["sentiment_sign"] == 0).sum())

        shock_col = "event_shock_factor" if "event_shock_factor" in df.columns else None
        high_shock = 0
        if shock_col:
            shock_vals = pd.to_numeric(df[shock_col], errors="coerce").fillna(0.0)
            high_shock = int((shock_vals >= 0.5).sum())

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Tracked Names", f"{len(df)}")
        c2.metric("Positive", f"{positives}")
        c3.metric("Negative", f"{negatives}")
        c4.metric("High Event Shock", f"{high_shock}")

        view_cols = [c for c in [
            "rank",
            "ticker",
            "industry",
            "sentiment_label",
            "sentiment_score",
            "sentiment_intensity",
            "signed_sentiment_intensity",
            "trend_score",
            "headline_count",
            "event_shock_factor",
            "opportunity_type",
            "primary_event_type",
        ] if c in df.columns]
        if view_cols:
            out = df[view_cols].copy()
            for c in ["sentiment_score", "sentiment_intensity", "signed_sentiment_intensity", "trend_score", "event_shock_factor"]:
                if c in out.columns:
                    out[c] = pd.to_numeric(out[c], errors="coerce").round(3)
            st.dataframe(out.head(TOP_COMPANIES_LIMIT), width="stretch", hide_index=True)

        if "signed_sentiment_intensity" in df.columns:
            rank = df.copy()
            rank["signed_sentiment_intensity"] = pd.to_numeric(rank["signed_sentiment_intensity"], errors="coerce")
            positives_rank = (
                rank[rank["sentiment_sign"] > 0]
                .dropna(subset=["signed_sentiment_intensity"])
                .head(12)
            )
            negatives_rank = (
                rank[rank["sentiment_sign"] < 0]
                .dropna(subset=["signed_sentiment_intensity"])
                .sort_values("signed_sentiment_intensity", ascending=True)
                .head(13)
            )
            rank = pd.concat([positives_rank, negatives_rank], ignore_index=True)
            if not rank.empty:
                color = "sentiment_label" if "sentiment_label" in rank.columns else None
                fig = px.bar(
                    rank,
                    x="ticker",
                    y="signed_sentiment_intensity",
                    color=color,
                    title="Sentiment Intensity Rank (Positive High → Negative Low)",
                )
                fig.update_layout(height=300, margin=dict(l=10, r=10, t=30, b=10))
                st.plotly_chart(fig, width="stretch", key="v3_sentiment_panel_chart_630")

        pos_df = (
            df[df["sentiment_sign"] > 0]
            .sort_values("signed_sentiment_intensity", ascending=False)
            .head(30)
        )
        neg_df = (
            df[df["sentiment_sign"] < 0]
            .sort_values("signed_sentiment_intensity", ascending=True)
            .head(30)
        )
        split_cols = st.columns(2)
        with split_cols[0]:
            st.markdown("**Top Positive 30**")
            if pos_df.empty:
                st.caption("No positive names in current snapshot.")
            else:
                cols = [c for c in ["ticker", "sentiment_label", "signed_sentiment_intensity", "trend_score", "headline_count"] if c in pos_df.columns]
                table = pos_df[cols].copy()
                for c in ["signed_sentiment_intensity", "trend_score"]:
                    if c in table.columns:
                        table[c] = pd.to_numeric(table[c], errors="coerce").round(3)
                st.dataframe(table, width="stretch", hide_index=True)
        with split_cols[1]:
            st.markdown("**Top Negative 30**")
            if neg_df.empty:
                st.caption("No negative names in current snapshot.")
            else:
                cols = [c for c in ["ticker", "sentiment_label", "signed_sentiment_intensity", "trend_score", "headline_count"] if c in neg_df.columns]
                table = neg_df[cols].copy()
                for c in ["signed_sentiment_intensity", "trend_score"]:
                    if c in table.columns:
                        table[c] = pd.to_numeric(table[c], errors="coerce").round(3)
                st.dataframe(table, width="stretch", hide_index=True)

        weekend = data.get("weekend_report", {}) if isinstance(data.get("weekend_report"), dict) else {}
        if weekend:
            counts = weekend.get("counts", {}) if isinstance(weekend.get("counts"), dict) else {}
            week_ending = str(weekend.get("week_ending", "") or "")
            is_weekend = bool(weekend.get("is_weekend", False))
            st.caption(
                f"Weekend Top-100 snapshot week ending {week_ending or 'N/A'} "
                f"(generated_now={is_weekend}, total={int(counts.get('total', 0) or 0)}, "
                f"positive={int(counts.get('positive', 0) or 0)}, negative={int(counts.get('negative', 0) or 0)}, "
                f"neutral={int(counts.get('neutral', 0) or 0)})."
            )

    def render_event_company_impact(self, data: Dict[str, Any]) -> None:
        event_df = data.get("event_df", pd.DataFrame())
        if not isinstance(event_df, pd.DataFrame) or event_df.empty:
            return

        df = event_df.copy()
        st.subheader("⚡ Event-to-Company Impact")

        if "impact_score" in df.columns:
            df["impact_score"] = pd.to_numeric(df["impact_score"], errors="coerce")
            df = df.dropna(subset=["impact_score"])
        if df.empty:
            return

        if "event_type" in df.columns:
            by_event = (
                df.groupby("event_type", as_index=False)["impact_score"]
                .mean()
                .sort_values("impact_score", ascending=False)
                .head(10)
            )
            if not by_event.empty:
                fig = px.bar(
                    by_event,
                    x="event_type",
                    y="impact_score",
                    title="Average Impact Score by Event Type",
                )
                fig.update_layout(height=280, margin=dict(l=10, r=10, t=30, b=10))
                st.plotly_chart(fig, width="stretch", key="v3_sentiment_panel_chart_707")

        downside = df.copy()
        if "impact_direction" in downside.columns:
            downside = downside[downside["impact_direction"].astype(str).str.lower() == "downside"]
        downside = downside.sort_values("impact_score", ascending=False).head(20)
        cols = [c for c in [
            "event_type",
            "ticker",
            "industry",
            "impact_direction",
            "impact_score",
            "sentiment_label",
            "top_macro_driver",
        ] if c in downside.columns]
        if cols and not downside.empty:
            table = downside[cols].copy()
            if "impact_score" in table.columns:
                table["impact_score"] = pd.to_numeric(table["impact_score"], errors="coerce").round(3)
            st.dataframe(table, width="stretch", hide_index=True)

    def render(self) -> None:
        """Render full V3 sentiment panel."""

        data = self.load_sentiment_data()

        status = data.get("summary_status", "")
        message = data.get("summary_message", "")
        staleness_days = data.get("staleness_days")
        market_rows = int(data.get("market_rows") or 0)

        if status == "no_data":
            st.warning(f"Sentiment source has no fresh NS-USO exports. {message}")
        elif staleness_days is not None and staleness_days > 1:
            st.warning(f"Sentiment appears stale: latest market sentiment is {staleness_days} day(s) old.")
        elif market_rows <= 1 and data.get("data_available"):
            st.info("Sentiment has a single latest snapshot; trend charts will remain flat until new cycles are ingested.")

        self.render_india_semantic_context(data)
        self.render_regime_confidence(data)
        self.render_narrative_health(data)
        self.render_sentiment_trend(data)
        self.render_sector_narratives(data)
        self.render_company_news_trends(data)
        self.render_event_company_impact(data)
