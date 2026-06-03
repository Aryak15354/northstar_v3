#!/usr/bin/env python3
"""
📊 OPTIONS TRADING PANEL
Dashboard component for displaying options trading system state

This panel displays:
✅ Current regime with IV rank and stability
✅ Active positions with P&L and Greeks
✅ Portfolio Greeks time series chart
✅ Trade history with metrics
✅ Risk metrics (weekly usage, capital scaling)
✅ Kill switch status
✅ Next trade eligibility with reasons
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

from src.dashboard.observers.options_observer import OptionsObserver


class OptionsPanel:
    """Options Trading Panel for Dashboard"""
    
    def __init__(self, observer: Optional[OptionsObserver] = None) -> None:
        """
        Initialize options panel
        
        Args:
            observer: OptionsObserver instance (optional, will create if not provided)
        """
        self.name = "Options Trading"
        self.observer = observer or OptionsObserver()
        self.project_root = Path(__file__).resolve().parents[3]

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            if value is None:
                return default
            if pd.isna(value):
                return default
            return float(value)
        except Exception:
            return default

    @staticmethod
    def _safe_datetime(value: Any) -> Optional[datetime]:
        """Best-effort parser that supports mixed naive/aware payload timestamps."""
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        try:
            ts = pd.to_datetime(value, errors="coerce")
            if pd.isna(ts):
                return None
            if isinstance(ts, pd.Timestamp):
                return ts.to_pydatetime()
        except Exception:
            return None
        return None

    @staticmethod
    def _days_since(value: Any) -> int:
        dt = OptionsPanel._safe_datetime(value)
        if dt is None:
            return 0
        now = datetime.now(dt.tzinfo) if dt.tzinfo is not None else datetime.now()
        try:
            return max(0, int((now - dt).days))
        except Exception:
            return 0

    @staticmethod
    def _normalize_violations(value: Any) -> List[str]:
        if isinstance(value, list):
            out: List[str] = []
            for item in value:
                txt = str(item).strip()
                if txt:
                    out.append(txt)
            return out
        if isinstance(value, str):
            txt = value.strip()
            if txt and txt.lower() not in {"n/a", "na", "none", "null", "unknown", "nan"}:
                return [txt]
        return []

    def _decision_reason(self, row: Dict[str, Any], default: str = "N/A") -> str:
        if not isinstance(row, dict):
            return default

        reason = row.get("reason")
        if reason is not None:
            txt = str(reason).strip()
            if txt and txt.lower() not in {"n/a", "na", "none", "null", "unknown", "nan"}:
                return txt

        violations = self._normalize_violations(row.get("violations"))
        if not violations:
            eligibility = row.get("eligibility")
            if isinstance(eligibility, dict):
                violations = self._normalize_violations(eligibility.get("violations"))
        if violations:
            return "; ".join(violations)

        for key in ("status_reason", "message", "error", "detail"):
            val = row.get(key)
            if val is None:
                continue
            txt = str(val).strip()
            if txt and txt.lower() not in {"n/a", "na", "none", "null", "unknown", "nan"}:
                return txt

        selector = row.get("strategy_selector")
        if isinstance(selector, dict):
            sel_reason = selector.get("reason")
            if sel_reason is not None:
                txt = str(sel_reason).strip()
                if txt and txt.lower() not in {"n/a", "na", "none", "null", "unknown", "nan"}:
                    return txt

        status = str(row.get("status", "") or "").strip().lower()
        if status.startswith("rejected"):
            return "Rejected by eligibility checks (reason unavailable)"
        if status.startswith("blocked"):
            return "Blocked by control rules (reason unavailable)"
        return default

    @staticmethod
    def _is_rejected_status(status: Any) -> bool:
        return str(status or "").strip().lower().startswith("rejected")

    def _strategy_payoff_curve(self, strategy: Dict[str, Any], points: int = 161) -> pd.DataFrame:
        """Compute expiry payoff curve from leg definitions (dashboard approximation)."""
        if not isinstance(strategy, dict):
            return pd.DataFrame()
        legs = strategy.get("legs", []) or []
        if not legs:
            return pd.DataFrame()

        spot = self._safe_float(strategy.get("underlying_price"), 0.0)
        strikes = [self._safe_float(l.get("strike"), np.nan) for l in legs]
        strikes = [s for s in strikes if np.isfinite(s) and s > 0]
        if not strikes:
            return pd.DataFrame()
        if spot <= 0:
            spot = float(np.median(strikes))

        lo = min(spot * 0.82, min(strikes) * 0.88)
        hi = max(spot * 1.18, max(strikes) * 1.12)
        if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
            return pd.DataFrame()

        prices = np.linspace(lo, hi, int(max(61, points)))
        total = np.zeros_like(prices, dtype=float)

        for leg in legs:
            strike = self._safe_float(leg.get("strike"), np.nan)
            premium = self._safe_float(leg.get("premium"), 0.0)
            qty = max(0.0, self._safe_float(leg.get("quantity"), 0.0))
            if not np.isfinite(strike) or strike <= 0 or qty <= 0:
                continue
            option_type = str(leg.get("option_type", "")).upper()
            action = str(leg.get("action", "")).upper()

            if option_type.startswith("C"):
                intrinsic = np.maximum(prices - strike, 0.0)
            else:
                intrinsic = np.maximum(strike - prices, 0.0)

            leg_payoff = (intrinsic - premium) * qty
            if action == "SELL":
                leg_payoff = -leg_payoff
            total += leg_payoff

        return pd.DataFrame({"underlying_price": prices, "pnl": total, "spot_ref": spot})

    @staticmethod
    def _health_badge(status: Any) -> str:
        raw = str(status or "").strip().lower()
        if raw == "fresh":
            return "🟢 fresh"
        if raw in {"lagging", "partial"}:
            return "🟡 lagging"
        if raw in {"stale", "missing"}:
            return "🔴 stale"
        if raw == "ready":
            return "🟢 ready"
        return raw or "unknown"

    def render_data_health(self, summary: Dict[str, Any]) -> None:
        """Render verified universe health + live loop freshness."""
        st.subheader("🛰️ Data Health & Cadence")
        hist = summary.get("historical_universe_health", {}) or {}
        loop = summary.get("live_loop_health", {}) or {}
        intervals = hist.get("intervals", {}) if isinstance(hist.get("intervals"), dict) else {}
        daily = intervals.get("1d", {}) if isinstance(intervals.get("1d"), dict) else {}
        weekly = intervals.get("1w", {}) if isinstance(intervals.get("1w"), dict) else {}
        intraday = intervals.get("5m", {}) if isinstance(intervals.get("5m"), dict) else {}
        universe = hist.get("universe", {}) if isinstance(hist.get("universe"), dict) else {}
        qc = hist.get("calculation_qc", {}) if isinstance(hist.get("calculation_qc"), dict) else {}

        q1, q2, q3, q4, q5, q6 = st.columns(6)
        with q1:
            st.metric("Provider", str(universe.get("provider", "unknown") or "unknown").upper())
        with q2:
            st.metric("Daily Symbols", int(daily.get("files", 0) or 0))
        with q3:
            st.metric("Weekly Symbols", int(weekly.get("files", 0) or 0))
        with q4:
            st.metric("5m Symbols", int(intraday.get("files", 0) or 0))
        with q5:
            sampled_rows = int(qc.get("sampled_rows", 0) or 0)
            st.metric("QC Rows", f"{sampled_rows:,}")
        with q6:
            loop_status = self._health_badge(loop.get("overall_status"))
            st.metric("5m Loop", loop_status)

        c1, c2, c3, c4 = st.columns(4)
        od = loop.get("options_dashboard_state", {}) if isinstance(loop.get("options_dashboard_state"), dict) else {}
        md = loop.get("market_data", {}) if isinstance(loop.get("market_data"), dict) else {}
        sd = loop.get("sentiment_cycle", {}) if isinstance(loop.get("sentiment_cycle"), dict) else {}
        sl = loop.get("sentiment_loop", {}) if isinstance(loop.get("sentiment_loop"), dict) else {}
        with c1:
            age = od.get("age_minutes")
            st.metric(
                "Options State",
                self._health_badge(od.get("status")),
                delta=f"{age:.1f}m old" if isinstance(age, (int, float)) else "no timestamp",
            )
        with c2:
            age = md.get("age_minutes")
            st.metric(
                "Market Feed",
                self._health_badge(md.get("status")),
                delta=f"{age:.1f}m old" if isinstance(age, (int, float)) else "no timestamp",
            )
        with c3:
            age = sd.get("age_minutes")
            st.metric(
                "NS-USO Sentiment",
                self._health_badge(sd.get("status")),
                delta=f"{age:.1f}m old" if isinstance(age, (int, float)) else "no timestamp",
            )
        with c4:
            age = sl.get("age_minutes")
            st.metric(
                "Sentiment Loop",
                self._health_badge(sl.get("status")),
                delta=f"{age:.1f}m old" if isinstance(age, (int, float)) else "not running",
            )
        if sd.get("summary_message"):
            st.caption(f"Sentiment note: {sd.get('summary_message')}")

        interval_rows = []
        for key in ("1d", "1w", "5m"):
            info = intervals.get(key, {}) if isinstance(intervals.get(key), dict) else {}
            bd = info.get("status_breakdown", {}) if isinstance(info.get("status_breakdown"), dict) else {}
            interval_rows.append(
                {
                    "Interval": key,
                    "Status": self._health_badge(info.get("status")),
                    "Files": int(info.get("files", 0) or 0),
                    "Size MB": float(info.get("size_mb", 0.0) or 0.0),
                    "Coverage %": float(info.get("coverage_pct", 0.0) or 0.0) if info.get("coverage_pct") is not None else None,
                    "Success": int(bd.get("success", 0) or 0),
                    "Failed": int(bd.get("failed", 0) or 0),
                    "Date Range": f"{info.get('start_date') or 'n/a'} → {info.get('end_date') or 'n/a'}",
                }
            )
        st.dataframe(pd.DataFrame(interval_rows), width="stretch", hide_index=True)

        anomalies = (
            int(qc.get("ask_lt_bid", 0) or 0)
            + int(qc.get("negative_ltp", 0) or 0)
            + int(qc.get("delta_out_of_range", 0) or 0)
            + int(qc.get("iv_out_of_range", 0) or 0)
        )
        if anomalies == 0 and int(qc.get("sampled_rows", 0) or 0) > 0:
            st.success(
                "Calculation QC passed on sampled rows: no ask<bid, no negative LTP, no out-of-range delta/IV in samples."
            )
        elif anomalies > 0:
            st.warning(
                "Calculation QC flagged anomalies: "
                f"ask<bid={int(qc.get('ask_lt_bid', 0) or 0)}, "
                f"ltp<0={int(qc.get('negative_ltp', 0) or 0)}, "
                f"|delta|>1.25={int(qc.get('delta_out_of_range', 0) or 0)}, "
                f"iv outside [0,5]={int(qc.get('iv_out_of_range', 0) or 0)}."
            )
        else:
            st.info("Calculation QC has not sampled any rows yet.")

    def render_upstox_chain_monitor(self, summary: Dict[str, Any]) -> None:
        """Render Upstox-style quick option-chain monitor from live chain cache."""
        st.subheader("📡 Upstox-Style Option Chain Monitor")
        decision_rows = summary.get("underlying_decisions", []) or []
        from_cycle = sorted(
            {
                str(r.get("underlying", "") or "").strip().upper()
                for r in decision_rows
                if isinstance(r, dict) and str(r.get("underlying", "") or "").strip()
            }
        )
        available = self.observer.get_available_chain_underlyings(limit=800)
        universe = sorted({*from_cycle, *available})

        if not universe:
            st.info("No option-chain files are available yet.")
            return

        default_symbol = "NIFTY" if "NIFTY" in universe else universe[0]
        selected = st.selectbox(
            "Underlying",
            options=universe,
            index=universe.index(default_symbol),
            key="options_chain_monitor_underlying",
        )

        snapshot = self.observer.get_chain_snapshot(selected, strikes_around_atm=10)
        if not snapshot.get("available"):
            st.warning(f"No chain snapshot available for {selected}.")
            return

        k1, k2, k3, k4, k5, k6 = st.columns(6)
        with k1:
            st.metric("Underlying", snapshot.get("underlying", selected))
        with k2:
            st.metric("Spot", f"{float(snapshot.get('spot', 0.0) or 0.0):,.2f}")
        with k3:
            st.metric("ATM Strike", f"{float(snapshot.get('atm_strike', 0.0) or 0.0):,.0f}")
        with k4:
            st.metric("Expiry", str(snapshot.get("expiry") or "N/A"))
        with k5:
            pcr_oi = snapshot.get("pcr_oi")
            st.metric("PCR (OI)", f"{float(pcr_oi):.2f}" if pcr_oi is not None else "N/A")
        with k6:
            pcr_vol = snapshot.get("pcr_volume")
            st.metric("PCR (Vol)", f"{float(pcr_vol):.2f}" if pcr_vol is not None else "N/A")
        st.caption(
            f"Source: {snapshot.get('source', 'unknown')} | Snapshot: {snapshot.get('asof', 'n/a')} | "
            f"Strikes shown: {snapshot.get('strikes', 0)}"
        )

        chart_controls = st.columns([1, 1, 3])
        with chart_controls[0]:
            candle_interval = st.selectbox(
                "Candles",
                options=["1d", "1w", "5m"],
                index=0,
                key=f"options_chain_candle_interval_{selected}",
            )
        with chart_controls[1]:
            lookback_bars = st.selectbox(
                "Bars",
                options=[60, 120, 240, 500],
                index=1,
                key=f"options_chain_candle_bars_{selected}",
            )
        with chart_controls[2]:
            st.caption(
                "Candles source priority: index/stock OHLC datasets, then option-chain-derived spot fallback."
            )

        rows = snapshot.get("rows", []) or []
        if not rows:
            st.info("No strikes available in selected snapshot.")
            return

        df = pd.DataFrame(rows)
        for col in df.columns:
            if col != "strike":
                df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df.sort_values("strike")

        oi_cols = [c for c in ("ce_oi", "pe_oi") if c in df.columns]
        if oi_cols:
            c_left, c_right = st.columns(2)
            with c_left:
                candles = self.observer.get_underlying_candles(
                    selected,
                    interval=candle_interval,
                    lookback_bars=int(lookback_bars),
                )
                if candles.get("available"):
                    cdf = pd.DataFrame(candles.get("rows", []) or [])
                    for col in ("open", "high", "low", "close"):
                        if col in cdf.columns:
                            cdf[col] = pd.to_numeric(cdf[col], errors="coerce")
                    cdf["timestamp"] = pd.to_datetime(cdf.get("timestamp"), errors="coerce")
                    cdf = cdf.dropna(subset=["timestamp", "open", "high", "low", "close"])
                    if not cdf.empty:
                        cfig = go.Figure(
                            data=[
                                go.Candlestick(
                                    x=cdf["timestamp"],
                                    open=cdf["open"],
                                    high=cdf["high"],
                                    low=cdf["low"],
                                    close=cdf["close"],
                                    name="OHLC",
                                    increasing_line_color="#16a34a",
                                    decreasing_line_color="#dc2626",
                                )
                            ]
                        )
                        cfig.update_layout(
                            title=f"{selected} Candlestick ({str(candle_interval).upper()})",
                            xaxis_title="Time",
                            yaxis_title="Price",
                            height=340,
                        )
                        st.plotly_chart(cfig, width="stretch", key="options_panel_chart_425")
                        st.caption(f"Candle source: {candles.get('source', 'unknown')}")
                    else:
                        st.info("No usable OHLC rows for selected underlying.")
                else:
                    st.info("Candlestick series not available for selected underlying.")

            with c_right:
                fig_oi = go.Figure()
                if "ce_oi" in df.columns:
                    fig_oi.add_bar(x=df["strike"], y=df["ce_oi"], name="CE OI", marker_color="#2563eb")
                if "pe_oi" in df.columns:
                    fig_oi.add_bar(x=df["strike"], y=df["pe_oi"], name="PE OI", marker_color="#d97706")
                fig_oi.add_vline(
                    x=float(snapshot.get("atm_strike", 0.0) or 0.0),
                    line_dash="dot",
                    line_color="#22c55e",
                    annotation_text="ATM",
                    annotation_position="top",
                )
                fig_oi.update_layout(
                    title="Open Interest by Strike",
                    xaxis_title="Strike",
                    yaxis_title="Open Interest",
                    barmode="group",
                    height=340,
                )
                st.plotly_chart(fig_oi, width="stretch", key="options_panel_chart_452")

        display_cols = [
            c
            for c in (
                "ce_bid",
                "ce_ask",
                "ce_ltp",
                "ce_iv",
                "ce_oi",
                "ce_volume",
                "strike",
                "pe_volume",
                "pe_oi",
                "pe_iv",
                "pe_ltp",
                "pe_bid",
                "pe_ask",
            )
            if c in df.columns
        ]
        st.dataframe(df[display_cols], width="stretch", hide_index=True)

    def render_opportunity_surface(self, summary: Dict[str, Any]) -> None:
        """Render opportunity-surface bridge for options strategy context."""
        st.subheader("🧭 Opportunity Surface Bridge")
        opp = summary.get("opportunity_surface", {}) or {}
        if not opp.get("available"):
            st.info("No opportunity surface available (`data/processed/opportunity_surface.parquet`).")
            return

        score_col = opp.get("score_column")
        updated_at = opp.get("updated_at")
        top_rows = opp.get("top", []) or []
        types = opp.get("type_distribution", []) or []

        o1, o2, o3 = st.columns(3)
        with o1:
            st.metric("Universe Rows", int(opp.get("rows", 0) or 0))
        with o2:
            st.metric("Score Field", str(score_col or "N/A"))
        with o3:
            st.metric("Updated", updated_at or "N/A")

        if top_rows:
            df = pd.DataFrame(top_rows)
            score = score_col if score_col in df.columns else None
            if score:
                df[score] = pd.to_numeric(df[score], errors="coerce")
                df = df.dropna(subset=[score]).sort_values(score, ascending=False)
                x_col = "underlying" if "underlying" in df.columns else ("ticker" if "ticker" in df.columns else df.columns[0])
                fig = px.bar(
                    df.head(15),
                    x=x_col,
                    y=score,
                    color="opportunity_type" if "opportunity_type" in df.columns else None,
                    title="Top Opportunity Scores",
                )
                fig.update_layout(height=320, xaxis_title="Symbol")
                st.plotly_chart(fig, width="stretch", key="options_panel_chart_511")

            table_cols = [c for c in ("underlying", "ticker", "Company Name", "opportunity_type", "regime_adjusted_score", "pulse_weighted_score", "northstar_score") if c in df.columns]
            st.dataframe(df[table_cols].head(20), width="stretch", hide_index=True)

        if types:
            tdf = pd.DataFrame(types)
            if {"opportunity_type", "count"}.issubset(tdf.columns):
                fig_t = px.pie(tdf, names="opportunity_type", values="count", title="Opportunity Type Mix", hole=0.42)
                fig_t.update_layout(height=300)
                st.plotly_chart(fig_t, width="stretch", key="options_panel_chart_521")

    def render_backtester(self, summary: Dict[str, Any]) -> None:
        """Render options backtester metrics and diagnostics."""
        st.subheader("🧪 Options Backtester")
        backtest = summary.get("options_backtest", {}) or {}
        if not backtest.get("available"):
            st.info(
                "No backtest artifact found yet. Run: "
                "`python3 scripts/run_options_backtester.py --underlyings NIFTY,BANKNIFTY,FINNIFTY,RELIANCE,TCS,HDFCBANK,INFY,ICICIBANK,SBIN`"
            )
            return

        stats = backtest.get("summary", {}) if isinstance(backtest.get("summary"), dict) else {}
        m1, m2, m3, m4, m5 = st.columns(5)
        with m1:
            st.metric("Trades", int(stats.get("total_trades", 0) or 0))
        with m2:
            st.metric("Win Rate", f"{float(stats.get('win_rate', 0.0) or 0.0):.1%}")
        with m3:
            st.metric("Net P&L", f"₹{float(stats.get('net_pnl', 0.0) or 0.0):,.0f}")
        with m4:
            st.metric("Profit Factor", f"{float(stats.get('profit_factor', 0.0) or 0.0):.2f}")
        with m5:
            st.metric("Updated", str(backtest.get("updated_at") or "N/A"))

        eq_rows = backtest.get("equity_curve", []) or []
        if eq_rows:
            eq = pd.DataFrame(eq_rows)
            time_col = "timestamp" if "timestamp" in eq.columns else ("date" if "date" in eq.columns else None)
            val_col = "equity" if "equity" in eq.columns else ("cumulative_pnl" if "cumulative_pnl" in eq.columns else None)
            if time_col and val_col:
                eq[time_col] = pd.to_datetime(eq[time_col], errors="coerce")
                eq[val_col] = pd.to_numeric(eq[val_col], errors="coerce")
                eq = eq.dropna(subset=[time_col, val_col]).sort_values(time_col)
                if not eq.empty:
                    fig = go.Figure()
                    fig.add_trace(
                        go.Scatter(
                            x=eq[time_col],
                            y=eq[val_col],
                            mode="lines",
                            name="Equity",
                            line=dict(color="#2563eb", width=2),
                        )
                    )
                    fig.update_layout(
                        title="Backtest Equity Curve",
                        xaxis_title="Time",
                        yaxis_title="Equity / Cumulative P&L",
                        height=320,
                    )
                    st.plotly_chart(fig, width="stretch", key="options_panel_chart_573")

        b1, b2 = st.columns(2)
        with b1:
            sb = backtest.get("strategy_breakdown", []) or []
            if sb:
                sdf = pd.DataFrame(sb)
                if {"strategy", "count"}.issubset(set(sdf.columns)):
                    fig_s = px.bar(sdf, x="strategy", y="count", title="Trades by Strategy", color="count")
                    fig_s.update_layout(height=300, xaxis_title=None)
                    st.plotly_chart(fig_s, width="stretch", key="options_panel_chart_583")
        with b2:
            ub = backtest.get("underlying_breakdown", []) or []
            if ub:
                udf = pd.DataFrame(ub).head(15)
                if {"underlying", "count"}.issubset(set(udf.columns)):
                    fig_u = px.bar(udf, x="underlying", y="count", title="Trades by Underlying", color="count")
                    fig_u.update_layout(height=300, xaxis_title=None)
                    st.plotly_chart(fig_u, width="stretch", key="options_panel_chart_591")

        recent = backtest.get("recent_trades", []) or []
        if recent:
            tdf = pd.DataFrame(recent)
            show_cols = [
                c for c in (
                    "entry_time",
                    "exit_time",
                    "underlying",
                    "strategy",
                    "side",
                    "entry_price",
                    "exit_price",
                    "net_pnl",
                    "return_pct",
                    "exit_reason",
                ) if c in tdf.columns
            ]
            st.markdown("#### Recent Backtest Trades")
            st.dataframe(tdf[show_cols], width="stretch", hide_index=True)
    
    def render(self) -> None:
        """Render complete options panel"""
        st.header("📊 Options Trading System")
        
        # Get options summary
        summary = self.observer.get_options_summary()

        tab_overview, tab_pipeline, tab_backtester, tab_portfolio, tab_diagnostics = st.tabs(
            ["Overview", "Strategy Pipeline", "Backtester", "Portfolio", "Diagnostics"]
        )

        with tab_overview:
            self.render_data_health(summary)
            st.divider()
            self.render_regime_status(summary)
            st.divider()
            self.render_upstox_chain_monitor(summary)
            st.divider()
            self.render_underlying_coverage(summary)
            st.divider()
            self.render_risk_metrics(summary)
            st.divider()
            self.render_trade_eligibility(summary)

        with tab_pipeline:
            self.render_opportunity_surface(summary)
            st.divider()
            self.render_strategy_pipeline(summary)
            st.divider()
            self.render_decision_history(summary)

        with tab_backtester:
            self.render_backtester(summary)

        with tab_portfolio:
            self.render_portfolio_greeks(summary)
            st.divider()
            self.render_active_positions(summary)
            st.divider()
            self.render_trade_history(summary)
            st.divider()
            self.render_centralized_pnl(summary)
            st.divider()
            self.render_tax_and_profitability(summary)

        with tab_diagnostics:
            self.render_portfolio_overlay(summary)
            st.divider()
            self.render_advanced_analytics(summary)
    
    def render_regime_status(self, summary: Dict[str, Any]) -> None:
        """Render current regime status"""
        st.subheader("🎯 Current Regime")
        
        regime = summary.get('regime', 'NO DATA')
        regime_metrics = summary.get('regime_metrics', {})
        
        # Regime display with color coding
        regime_colors = {
            'LOW_VOL_SELL': '🟢',
            'HIGH_VOL_SELL': '🟡',
            'RISING_VOL_BUY': '🔵',
            'NEUTRAL': '⚪',
            'CRASH_HEDGE': '🔴',
            'NO DATA': '⚫'
        }
        
        regime_icon = regime_colors.get(regime, '⚫')
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "Regime",
                f"{regime_icon} {regime.replace('_', ' ').title()}",
                help="Current options market regime"
            )
        
        with col2:
            iv_rank = pd.to_numeric(regime_metrics.get('iv_rank'), errors='coerce')
            st.metric(
                "IV Rank",
                f"{float(iv_rank):.1%}" if pd.notna(iv_rank) else "N/A",
                help="IV percentile rank (252-day history)"
            )
        
        with col3:
            days_in_regime = (
                summary.get('regime_metrics', {}).get('days_in_regime')
                or summary.get('regime_metrics', {}).get('days_in_old_regime')
                or summary.get('regime_metrics', {}).get('days_in_current_regime')
                or 0
            )
            try:
                days_in_regime = int(float(days_in_regime))
            except Exception:
                days_in_regime = 0
            stability_status = "✓ Stable" if days_in_regime >= 2 else "⚠ Building"
            st.metric(
                "Stability",
                f"{days_in_regime} days",
                delta=stability_status,
                help="Days in current regime (need 2+ for trading)"
            )
        
        with col4:
            # Vol-of-vol status (would come from regime metrics)
            st.metric(
                "Vol-of-Vol",
                "Normal",
                help="Volatility of volatility status"
            )

        market_snapshot = summary.get('market_snapshot', {}) or {}
        m1, m2, m3 = st.columns(3)
        with m1:
            st.metric(
                "Contracts Seen",
                int(market_snapshot.get('option_contracts', 0) or 0),
                help="Contracts available in latest option-chain snapshot"
            )
        with m2:
            nifty_px = market_snapshot.get('nifty_price')
            st.metric(
                "NIFTY Spot",
                f"{float(nifty_px):,.2f}" if nifty_px is not None else "N/A",
            )
        with m3:
            banknifty_px = market_snapshot.get('banknifty_price')
            st.metric(
                "BANKNIFTY Spot",
                f"{float(banknifty_px):,.2f}" if banknifty_px is not None else "N/A",
            )
        if market_snapshot.get('timestamp'):
            st.caption(f"Market feed timestamp: {market_snapshot.get('timestamp')}")

    def render_portfolio_overlay(self, summary: Dict[str, Any]) -> None:
        """Render V3 portfolio -> options integration details."""
        st.subheader("🧬 Portfolio-Aware Options Overlay")
        overlay = summary.get("portfolio_overlay", {}) or {}
        if not overlay:
            st.info("Portfolio overlay context not available yet.")
            return

        enabled = bool(overlay.get("enabled", False))
        status = str(overlay.get("status", "unknown"))
        if not enabled:
            st.info("Portfolio overlay is disabled for this engine run.")
            return

        k1, k2, k3, k4, k5, k6 = st.columns(6)
        with k1:
            st.metric("Objective", str(overlay.get("portfolio_objective", "N/A")).replace("_", " ").title())
        with k2:
            st.metric("Hedge Intensity", f"{float(overlay.get('hedge_intensity', 0.0) or 0.0):.2f}")
        with k3:
            st.metric("Risk-On Prob", f"{float(overlay.get('risk_on_probability', 0.0) or 0.0):.1%}")
        with k4:
            st.metric("Portfolio Exposure", f"{float(overlay.get('total_exposure', 0.0) or 0.0):.1%}")
        with k5:
            st.metric("Cash Level", f"{float(overlay.get('cash_level', 0.0) or 0.0):.1%}")
        with k6:
            ws = overlay.get("weights_summary", {}) if isinstance(overlay.get("weights_summary"), dict) else {}
            st.metric(
                "Selected Stocks",
                f"{int(ws.get('selected_holdings', 0) or 0)}/{int(ws.get('option_eligible_holdings', 0) or 0)}",
            )

        dominant = overlay.get("dominant_sector", {}) if isinstance(overlay.get("dominant_sector"), dict) else {}
        if dominant.get("name"):
            st.caption(
                f"Status: {status} | Regime: {overlay.get('regime', 'N/A')} | "
                f"Dominant sector: {dominant.get('name')} ({float(dominant.get('weight', 0.0) or 0.0):.1%})"
            )
        else:
            st.caption(f"Status: {status} | Regime: {overlay.get('regime', 'N/A')}")

        warnings = overlay.get("warnings", []) or []
        if warnings:
            st.warning("Overlay warnings: " + "; ".join(str(w) for w in warnings))

        sentiment_ctx = overlay.get("sentiment_context", {}) if isinstance(overlay.get("sentiment_context"), dict) else {}
        if sentiment_ctx.get("available"):
            s1, s2, s3, s4 = st.columns(4)
            with s1:
                st.metric("Sentiment Bias", f"{float(sentiment_ctx.get('sentiment_bias', 0.0) or 0.0):+.2f}")
            with s2:
                st.metric("Event Shock", f"{float(sentiment_ctx.get('event_shock_score', 0.0) or 0.0):.2f}")
            with s3:
                st.metric("Alert Level", str(sentiment_ctx.get("alert_level", "normal")).upper())
            with s4:
                st.metric("Theme", str(sentiment_ctx.get("dominant_theme", "neutral")).replace("_", " ").title())
            if sentiment_ctx.get("summary_age_minutes") is not None:
                st.caption(
                    f"Sentiment summary age: {float(sentiment_ctx.get('summary_age_minutes', 0.0) or 0.0):.1f} minutes"
                )

        rationale = str(overlay.get("weekly_rationale", "") or "").strip()
        if rationale:
            st.markdown("**Why This Week's Portfolio Is Positioned This Way**")
            st.info(rationale)

        selected_rows = overlay.get("selected_stock_rows", []) or []
        if selected_rows:
            st.markdown("**Portfolio Holdings Routed Into Options Universe**")
            rows = []
            for row in selected_rows:
                rows.append({
                    "Ticker": row.get("ticker", row.get("symbol", "N/A")),
                    "Symbol": row.get("symbol", "N/A"),
                    "Weight": f"{float(row.get('weight', 0.0) or 0.0):.2%}",
                    "Objective": str(row.get("objective", "N/A")).replace("_", " "),
                    "Reason": row.get("reason", "N/A"),
                    "Sector": row.get("sector", "N/A"),
                })
            st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

        col_left, col_right = st.columns(2)
        with col_left:
            index_obj = overlay.get("index_objectives", {}) if isinstance(overlay.get("index_objectives"), dict) else {}
            if index_obj:
                st.markdown("**Index Overlay Objectives**")
                sector_indices = set(overlay.get("sector_index_underlyings", []) or [])
                idx_df = pd.DataFrame([
                    {
                        "Underlying": k,
                        "Objective": str(v).replace("_", " "),
                        "Type": "Sector/Industry Index" if k in sector_indices else "Core Index",
                    }
                    for k, v in index_obj.items()
                ])
                st.dataframe(idx_df, width="stretch", hide_index=True)
        with col_right:
            alloc_top = overlay.get("capital_allocation_top", []) or []
            if alloc_top:
                st.markdown("**Top Capital Allocation Drivers**")
                alloc_df = pd.DataFrame([
                    {
                        "Strategy": r.get("strategy", "N/A"),
                        "Allocation": f"{float(r.get('allocation', 0.0) or 0.0):.2%}",
                    }
                    for r in alloc_top
                ])
                st.dataframe(alloc_df, width="stretch", hide_index=True)
    
    def render_active_positions(self, summary: Dict[str, Any]) -> None:
        """Render active positions table"""
        st.subheader("💼 Active Positions")
        
        positions = self.observer.get_active_positions()
        
        if not positions:
            st.info("No active positions")
            return
        
        # Summary metrics
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(
                "Open Positions",
                len(positions),
                help="Number of active options positions"
            )
        
        with col2:
            total_pnl = summary.get('total_unrealized_pnl', 0.0)
            pnl_color = "normal" if total_pnl >= 0 else "inverse"
            st.metric(
                "Total Unrealized P&L",
                f"₹{total_pnl:,.0f}",
                delta=f"{total_pnl:+,.0f}",
                delta_color=pnl_color,
                help="Total unrealized P&L across all positions"
            )
        
        with col3:
            total_risk = sum(pos.get('max_loss', 0.0) for pos in positions)
            st.metric(
                "Total Risk",
                f"₹{total_risk:,.0f}",
                help="Total max loss across all positions"
            )
        
        # Positions table
        st.markdown("#### Position Details")
        
        table_data = []
        for pos in positions:
            days_held = self._days_since(pos.get('entry_time'))
            
            greeks = pos.get('greeks', {})
            
            table_data.append({
                'Position ID': pos.get('position_id', 'N/A')[:20] + '...',
                'Strategy': pos.get('strategy_type', 'N/A').replace('_', ' ').title(),
                'P&L': f"₹{pos.get('unrealized_pnl', 0.0):,.0f}",
                'Days': days_held,
                'Delta': f"{greeks.get('delta', 0.0):.2f}",
                'Theta': f"{greeks.get('theta', 0.0):.0f}",
                'Vega': f"{greeks.get('vega', 0.0):.2f}"
            })
        
        df = pd.DataFrame(table_data)
        st.dataframe(df, width="stretch", hide_index=True)
    
    def render_portfolio_greeks(self, summary: Dict[str, Any]) -> None:
        """Render portfolio Greeks display and chart"""
        st.subheader("📈 Portfolio Greeks")
        
        greeks = summary.get('portfolio_greeks', {}) or {}
        greek_ctx = summary.get('portfolio_greeks_context', {}) or {}
        greek_source = str(greek_ctx.get("source", "none") or "none")
        greek_contributors = greek_ctx.get("contributors", []) or []
        violations = summary.get('greek_violations', [])

        source_labels = {
            "persisted_portfolio": "Persisted Live Portfolio",
            "active_positions": "Active Positions Aggregate",
            "cycle_strategies": "Cycle Candidates (Indicative)",
            "none": "No Greeks Source Available",
        }
        source_text = source_labels.get(greek_source, greek_source)
        is_cycle_only = greek_source == "cycle_strategies"
        live_positions_count = len(self.observer.get_active_positions())

        live_greeks = {
            "delta": self._safe_float(greeks.get("delta"), 0.0),
            "gamma": self._safe_float(greeks.get("gamma"), 0.0),
            "theta": self._safe_float(greeks.get("theta"), 0.0),
            "vega": self._safe_float(greeks.get("vega"), 0.0),
        }
        if is_cycle_only:
            live_greeks = {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0}
        cycle_greeks = {
            "delta": self._safe_float(greeks.get("delta"), 0.0),
            "gamma": self._safe_float(greeks.get("gamma"), 0.0),
            "theta": self._safe_float(greeks.get("theta"), 0.0),
            "vega": self._safe_float(greeks.get("vega"), 0.0),
        } if is_cycle_only else {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0}

        st.markdown("#### Live Portfolio Exposure")
        live_cols = st.columns(4)
        with live_cols[0]:
            delta = live_greeks["delta"]
            delta_status = "✓" if -0.2 <= delta <= 0.2 else "⚠"
            st.metric("Delta", f"{delta:.2f}", delta=f"{delta_status} [-0.2, +0.2]")
        with live_cols[1]:
            st.metric("Gamma", f"{live_greeks['gamma']:.2f}")
        with live_cols[2]:
            theta = live_greeks["theta"]
            theta_status = "✓" if theta > 0 else "⚠"
            st.metric("Theta", f"{theta:.2f}", delta=f"{theta_status} Positive")
        with live_cols[3]:
            vega = live_greeks["vega"]
            vega_status = "✓" if -0.3 <= vega <= 0.1 else "⚠"
            st.metric("Vega", f"{vega:.2f}", delta=f"{vega_status} [-0.3, +0.1]")

        if is_cycle_only:
            st.info(
                "Live book has no open positions. Large Greek values below are from current cycle strategy candidates "
                "(indicative only, not executed exposure)."
            )
        elif violations:
            st.warning(f"⚠️ Greek Violations: {'; '.join(violations)}")
        elif live_positions_count == 0:
            st.caption("No active options positions in live book.")

        if is_cycle_only:
            st.markdown("#### Cycle Indicative Exposure (Not Live)")
            cyc_cols = st.columns(4)
            with cyc_cols[0]:
                st.metric("Cycle Δ", f"{cycle_greeks['delta']:.2f}")
            with cyc_cols[1]:
                st.metric("Cycle Γ", f"{cycle_greeks['gamma']:.2f}")
            with cyc_cols[2]:
                st.metric("Cycle Θ", f"{cycle_greeks['theta']:.2f}")
            with cyc_cols[3]:
                st.metric("Cycle V", f"{cycle_greeks['vega']:.2f}")

        if greek_contributors:
            st.caption(
                f"Greeks source: {source_text} • contributors: {', '.join(greek_contributors[:12])}"
            )
        else:
            st.caption(f"Greeks source: {source_text}")
        
        # Greeks time series chart
        greeks_history = self.observer.get_portfolio_greeks_history()
        
        if not greeks_history.empty:
            st.markdown("#### Greeks Time Series (30 Days)")
            
            fig = go.Figure()
            
            # Add traces for each Greek
            fig.add_trace(go.Scatter(
                x=greeks_history.index,
                y=greeks_history['delta'],
                name='Delta',
                line=dict(color='blue', width=2)
            ))
            
            fig.add_trace(go.Scatter(
                x=greeks_history.index,
                y=greeks_history['theta'],
                name='Theta',
                line=dict(color='green', width=2),
                yaxis='y2'
            ))
            
            fig.add_trace(go.Scatter(
                x=greeks_history.index,
                y=greeks_history['vega'],
                name='Vega',
                line=dict(color='orange', width=2)
            ))
            
            # Update layout
            fig.update_layout(
                title="Portfolio Greeks Over Time",
                xaxis_title="Date",
                yaxis_title="Delta / Vega",
                yaxis2=dict(
                    title="Theta",
                    overlaying='y',
                    side='right'
                ),
                hovermode='x unified',
                height=400
            )
            
            st.plotly_chart(fig, width="stretch", key="options_panel_chart_1045")
        else:
            if is_cycle_only:
                st.info("No live portfolio Greeks history yet (only cycle-candidate exposure is available).")
            else:
                st.info("No Greeks time-series history available yet.")

        decisions = summary.get("underlying_decisions", []) or []
        contrib_rows: List[Dict[str, Any]] = []
        for d in decisions:
            if not isinstance(d, dict):
                continue
            strategy = d.get("strategy")
            if not isinstance(strategy, dict):
                continue
            g = strategy.get("greeks")
            if not isinstance(g, dict):
                continue
            under = str(d.get("underlying", "N/A") or "N/A")
            contrib_rows.append({
                "underlying": under,
                "status": str(d.get("status", "unknown") or "unknown"),
                "delta": self._safe_float(g.get("delta"), 0.0),
                "gamma": self._safe_float(g.get("gamma"), 0.0),
                "theta": self._safe_float(g.get("theta"), 0.0),
                "vega": self._safe_float(g.get("vega"), 0.0),
            })

        if contrib_rows:
            st.markdown("#### Underlying Greek Contributions (Latest Cycle)")
            cdf = pd.DataFrame(contrib_rows)
            cdf["abs_total"] = cdf[["delta", "gamma", "theta", "vega"]].abs().sum(axis=1)
            cdf = cdf.sort_values("abs_total", ascending=False).head(16)
            long = cdf.melt(
                id_vars=["underlying", "status"],
                value_vars=["delta", "gamma", "theta", "vega"],
                var_name="greek",
                value_name="value",
            )
            fig_c = px.bar(
                long,
                x="underlying",
                y="value",
                color="greek",
                barmode="group",
                title="Per-Underlying Greek Profile",
            )
            fig_c.update_layout(height=360, xaxis_title="Underlying", yaxis_title="Greek Value")
            st.plotly_chart(fig_c, width="stretch", key="options_panel_chart_1093")
    
    def render_risk_metrics(self, summary: Dict[str, Any]) -> None:
        """Render risk metrics"""
        st.subheader("⚠️ Risk Metrics")
        
        weekly_usage = summary.get('weekly_risk_usage', {})
        weekly_activity = summary.get('weekly_trade_activity', {}) or {}
        capital_scaling = summary.get('capital_scaling', {})
        portfolio_risk = summary.get('portfolio_risk_usage', {})
        kill_switch = summary.get('kill_switch_status', {})
        active_limits = summary.get('active_limits', {}) or {}
        unbounded_sentinel = 1_000_000
        trades_limit_cfg = int(active_limits.get('max_trades_per_week', weekly_usage.get('trades_limit', 2)) or 2)
        risk_cap_pct_cfg = float(active_limits.get('portfolio_risk_cap_pct', portfolio_risk.get('risk_cap_pct', 0.02)) or 0.02)
        no_max_trades = bool(active_limits.get('no_max_trades_limit', False) or trades_limit_cfg >= unbounded_sentinel)
        
        src = active_limits.get('source', {}) if isinstance(active_limits.get('source'), dict) else {}
        src_trades = src.get('max_trades_per_week', 'config')
        src_risk = src.get('portfolio_risk_cap_pct', 'config')
        st.caption(
            f"Active limits: trades/week={'∞' if no_max_trades else trades_limit_cfg} ({src_trades}), "
            f"portfolio risk cap={risk_cap_pct_cfg:.1%} ({src_risk})"
        )
        
        # Weekly usage
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### Weekly Usage")
            
            trades_used = int(weekly_usage.get('trades_used', 0) or 0)
            trades_limit = int(weekly_usage.get('trades_limit', trades_limit_cfg) or trades_limit_cfg)
            open_events = int(weekly_activity.get("open_events", trades_used) or trades_used)
            close_events = int(weekly_activity.get("close_events", 0) or 0)
            unique_underlyings_open = int(weekly_activity.get("unique_underlyings_open", 0) or 0)
            if no_max_trades:
                trades_limit = max(trades_limit, unbounded_sentinel)

            if no_max_trades:
                st.metric(
                    "Weekly Opens (Telemetry)",
                    f"{trades_used:,}",
                    delta="Cap disabled",
                    help="Open-position events this week; not constrained while unbounded mode is active"
                )
                st.caption("No max-trades limit is active in this engine run.")
            else:
                st.metric(
                    "Trade Open Events (Week)",
                    f"{trades_used}/{trades_limit}",
                    help="Raw open events recorded in ledger against configured weekly cap"
                )
                trade_pct = (trades_used / trades_limit) if trades_limit > 0 else 0
                st.progress(min(trade_pct, 1.0))
            st.caption(
                f"Telemetry: opens={open_events}, closes={close_events}, unique underlyings opened={unique_underlyings_open}"
            )
        
        with col2:
            st.markdown("#### Capital Scaling")
            
            current_risk = capital_scaling.get('current_risk_pct', 1.0)
            
            st.metric(
                "Risk Per Trade",
                f"{current_risk:.2%}",
                help="Current risk percentage per trade"
            )
            
            equity = capital_scaling.get('current_equity', 0.0)
            hwm = capital_scaling.get('equity_high_water_mark', 0.0)
            
            if equity > 0 and hwm > 0:
                drawdown = (equity - hwm) / hwm
                st.metric(
                    "Drawdown from HWM",
                    f"{drawdown:.1%}",
                    help="Drawdown from equity high water mark"
                )
        
        # Portfolio risk
        col3, col4 = st.columns(2)
        
        with col3:
            st.markdown("#### Portfolio Risk")
            
            risk_pct = portfolio_risk.get('risk_pct', 0.0)
            risk_cap_pct = float(portfolio_risk.get('risk_cap_pct', risk_cap_pct_cfg) or risk_cap_pct_cfg)
            
            st.metric(
                "Risk Usage",
                f"{risk_pct:.2%} of {risk_cap_pct:.1%}",
                help="Portfolio risk as % of capital"
            )
            
            # Progress bar
            risk_usage_pct = (risk_pct / risk_cap_pct) if risk_cap_pct > 0 else 0
            st.progress(min(risk_usage_pct, 1.0))
        
        with col4:
            st.markdown("#### Kill Switch")
            
            is_active = kill_switch.get('active', False)
            
            if is_active:
                st.error("🛑 ACTIVE")
                st.caption(kill_switch.get('reason', 'Unknown reason'))
                
                cooldown = kill_switch.get('cooldown_until')
                if cooldown:
                    cooldown_dt = self._safe_datetime(cooldown)
                    st.caption(
                        f"Until: {cooldown_dt.strftime('%Y-%m-%d %H:%M IST')}"
                        if cooldown_dt
                        else f"Until: {cooldown}"
                    )
            else:
                st.success("✓ Inactive")
                st.caption("All systems operational")

    def render_tax_and_profitability(self, summary: Dict[str, Any]) -> None:
        """Render India tax-aware profitability block."""
        st.subheader("🧾 Tax & Net Profitability (India)")
        ytd = summary.get("ytd", {}) or {}
        if not ytd:
            st.info("YTD tax/profitability metrics are not available yet.")
            return

        gross_profit = float(ytd.get("ytd_gross_profits", 0.0) or 0.0)
        gross_loss = float(ytd.get("ytd_gross_losses", 0.0) or 0.0)
        total_costs = float(ytd.get("ytd_total_costs", 0.0) or 0.0)
        tax_liability = float(ytd.get("ytd_tax_liability", 0.0) or 0.0)
        net_pnl = float(ytd.get("ytd_net_pnl", 0.0) or 0.0)
        cash_buffer = float(ytd.get("cash_buffer", 0.0) or 0.0)
        tax_gap = float(ytd.get("tax_buffer_gap", tax_liability - cash_buffer) or 0.0)
        tax_tolerance = float(ytd.get("tax_buffer_tolerance", 0.0) or 0.0)
        tax_status = str(ytd.get("tax_buffer_status", "N/A"))

        c1, c2, c3, c4, c5, c6 = st.columns(6)
        with c1:
            st.metric("Gross Profit", f"₹{gross_profit:,.0f}")
        with c2:
            st.metric("Gross Loss", f"₹{gross_loss:,.0f}")
        with c3:
            st.metric("Costs", f"₹{total_costs:,.0f}")
        with c4:
            st.metric("Tax Liability", f"₹{tax_liability:,.0f}")
        with c5:
            st.metric("Net P&L", f"₹{net_pnl:,.0f}", delta=f"{net_pnl:+,.0f}")
        with c6:
            st.metric("Tax Buffer", tax_status, delta=f"₹{cash_buffer:,.0f}")
        st.caption(
            f"Tax buffer gap: ₹{tax_gap:,.2f} | tolerance band: ₹{tax_tolerance:,.2f}"
        )

        comp_df = pd.DataFrame([
            {"Component": "Gross Profit", "Amount": gross_profit, "Direction": "positive"},
            {"Component": "Gross Loss", "Amount": -gross_loss, "Direction": "negative"},
            {"Component": "Costs", "Amount": -total_costs, "Direction": "negative"},
            {"Component": "Tax", "Amount": -tax_liability, "Direction": "negative"},
            {"Component": "Net P&L", "Amount": net_pnl, "Direction": "net"},
        ])
        fig = px.bar(
            comp_df,
            x="Component",
            y="Amount",
            color="Direction",
            color_discrete_map={"positive": "#1f9d55", "negative": "#d64545", "net": "#2d6cdf"},
            title="P&L Decomposition (Tax-Aware)",
        )
        fig.update_layout(height=320, showlegend=False)
        st.plotly_chart(fig, width="stretch", key="options_panel_chart_1265")

        if cash_buffer > 0:
            tax_usage = max(0.0, tax_liability / cash_buffer)
            usage_fig = go.Figure(
                go.Indicator(
                    mode="gauge+number",
                    value=tax_usage * 100.0,
                    number={"suffix": "%"},
                    title={"text": "Tax Buffer Utilization"},
                    gauge={
                        "axis": {"range": [0, max(120.0, tax_usage * 120.0)]},
                        "bar": {"color": "#2d6cdf"},
                        "steps": [
                            {"range": [0, 80], "color": "#d8f3dc"},
                            {"range": [80, 100], "color": "#ffe8a1"},
                            {"range": [100, max(120.0, tax_usage * 120.0)], "color": "#ffd6d6"},
                        ],
                        "threshold": {"line": {"color": "#d64545", "width": 3}, "value": 100},
                    },
                )
            )
            usage_fig.update_layout(height=260)
            st.plotly_chart(usage_fig, width="stretch", key="options_panel_chart_1288")

    def render_centralized_pnl(self, summary: Dict[str, Any]) -> None:
        """Render unified cross-system PnL state."""
        st.subheader("🧩 Centralized V3 P&L")
        payload = summary.get("centralized_pnl", {}) or {}
        if not payload or not bool(payload.get("available", False)):
            st.info("Centralized V3 P&L artifact is not available yet.")
            return

        components = payload.get("components", {}) if isinstance(payload.get("components"), dict) else {}
        options = components.get("options_live", {}) if isinstance(components.get("options_live"), dict) else {}
        weekly = components.get("v3_weekly_portfolio", {}) if isinstance(components.get("v3_weekly_portfolio"), dict) else {}
        shadow = components.get("shadow_portfolio", {}) if isinstance(components.get("shadow_portfolio"), dict) else {}
        aggregates = payload.get("aggregates", {}) if isinstance(payload.get("aggregates"), dict) else {}

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("Combined Net", f"₹{float(aggregates.get('combined_net_pnl_estimate', 0.0) or 0.0):,.0f}")
        with c2:
            st.metric("Options (Tax-Aware)", f"₹{float(options.get('ytd_net_pnl_after_costs_and_tax', 0.0) or 0.0):,.0f}")
        with c3:
            st.metric("Weekly Portfolio", f"₹{float(weekly.get('total_pnl_from_series_start', 0.0) or 0.0):,.0f}")
        with c4:
            st.metric("Shadow Portfolio", f"₹{float(shadow.get('total_pnl_from_series_start', 0.0) or 0.0):,.0f}")

        gate_status = "PASS" if bool(aggregates.get("tax_aware_net_gate", False)) else "FAIL"
        st.caption(f"Tax-aware net gate: {gate_status} | Snapshot: {payload.get('timestamp', 'n/a')}")

    def render_advanced_analytics(self, summary: Dict[str, Any]) -> None:
        """Render richer decision/risk analytics graphs."""
        st.subheader("📉 Advanced Options Analytics")
        rows = summary.get("decision_history", []) or []
        if not rows:
            st.info("No decision history available for analytics yet.")
            return

        df = pd.DataFrame(rows).copy()
        if df.empty:
            st.info("No analytics rows available yet.")
            return

        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        if "objective" not in df.columns:
            df["objective"] = "N/A"
        if "selected_source" not in df.columns:
            df["selected_source"] = "N/A"

        left, right = st.columns(2)
        with left:
            status_counts = (
                df["status"].fillna("unknown").astype(str).value_counts().reset_index()
            )
            status_counts.columns = ["Status", "Count"]
            fig_status = px.bar(
                status_counts,
                x="Status",
                y="Count",
                title="Decision Outcomes",
                color="Count",
                color_continuous_scale="Blues",
            )
            fig_status.update_layout(height=320)
            st.plotly_chart(fig_status, width="stretch", key="options_panel_chart_1352")
        with right:
            obj_counts = (
                df["objective"].fillna("N/A").astype(str).value_counts().reset_index()
            )
            obj_counts.columns = ["Objective", "Count"]
            fig_obj = px.pie(
                obj_counts,
                names="Objective",
                values="Count",
                title="Objective Mix",
                hole=0.45,
            )
            fig_obj.update_layout(height=320)
            st.plotly_chart(fig_obj, width="stretch", key="options_panel_chart_1366")

        if {"underlying", "status"}.issubset(df.columns):
            heat = (
                df.groupby(["underlying", "status"]).size().reset_index(name="count")
            )
            heat_fig = px.density_heatmap(
                heat,
                x="underlying",
                y="status",
                z="count",
                color_continuous_scale="Teal",
                title="Underlying vs Decision Type",
            )
            heat_fig.update_layout(height=360)
            st.plotly_chart(heat_fig, width="stretch", key="options_panel_chart_1381")

        rejection_rows: List[Dict[str, Any]] = []
        for _, r in df.iterrows():
            status = str(r.get("status", "") or "")
            if not self._is_rejected_status(status):
                continue
            row = r.to_dict()
            violations = self._normalize_violations(row.get("violations"))
            if violations:
                for v in violations:
                    rejection_rows.append({"reason": str(v), "underlying": row.get("underlying", "N/A")})
            else:
                rejection_rows.append(
                    {"reason": self._decision_reason(row, default="reason unavailable"), "underlying": row.get("underlying", "N/A")}
                )
        if rejection_rows:
            rej_df = pd.DataFrame(rejection_rows)
            rej_counts = (
                rej_df.groupby("reason").size().reset_index(name="count").sort_values("count", ascending=False).head(12)
            )
            fig_rej = px.bar(
                rej_counts,
                x="reason",
                y="count",
                title="Top Rejection Reasons",
                color="count",
                color_continuous_scale="Reds",
            )
            fig_rej.update_layout(height=340, xaxis_title=None, yaxis_title="Count")
            st.plotly_chart(fig_rej, width="stretch", key="options_panel_chart_1411")

        trades = self.observer.get_trade_history(limit=150)
        if trades:
            tdf = pd.DataFrame(trades)
            if "exit_time" in tdf.columns:
                tdf["exit_time"] = pd.to_datetime(tdf["exit_time"], errors="coerce")
            elif "entry_time" in tdf.columns:
                tdf["exit_time"] = pd.to_datetime(tdf["entry_time"], errors="coerce")
            tdf = tdf.dropna(subset=["exit_time"]).sort_values("exit_time")
            if not tdf.empty:
                tdf["realized_pnl"] = pd.to_numeric(tdf.get("realized_pnl", 0.0), errors="coerce").fillna(0.0)
                tdf["cum_realized_pnl"] = tdf["realized_pnl"].cumsum()
                pnl_fig = go.Figure()
                pnl_fig.add_trace(go.Bar(
                    x=tdf["exit_time"],
                    y=tdf["realized_pnl"],
                    name="Trade P&L",
                    marker_color=np.where(tdf["realized_pnl"] >= 0, "#1f9d55", "#d64545"),
                    opacity=0.55,
                ))
                pnl_fig.add_trace(go.Scatter(
                    x=tdf["exit_time"],
                    y=tdf["cum_realized_pnl"],
                    mode="lines+markers",
                    name="Cumulative Realized P&L",
                    line=dict(color="#2d6cdf", width=2),
                ))
                pnl_fig.update_layout(
                    title="Realized P&L Path",
                    xaxis_title="Trade Time",
                    yaxis_title="₹",
                    height=360,
                )
                st.plotly_chart(pnl_fig, width="stretch", key="options_panel_chart_1445")

    def render_underlying_coverage(self, summary: Dict[str, Any]) -> None:
        """Render per-underlying market coverage and decision outcomes."""
        st.subheader("🧩 Underlyings Coverage")
        decisions = summary.get("underlying_decisions", []) or []
        if not decisions:
            st.info("No per-underlying diagnostic payload yet.")
            return

        processed = len(decisions)
        with_chain = sum(1 for d in decisions if int(d.get("contracts", 0) or 0) > 0)
        with_strategy = sum(1 for d in decisions if isinstance(d.get("strategy"), dict))
        opened = sum(1 for d in decisions if d.get("status") == "opened_position")
        rejected = sum(1 for d in decisions if str(d.get("status", "")).startswith("rejected"))
        blocked = sum(1 for d in decisions if str(d.get("status", "")).startswith("blocked"))

        c1, c2, c3, c4, c5, c6 = st.columns(6)
        with c1:
            st.metric("Processed", processed)
        with c2:
            st.metric("Chains Loaded", with_chain)
        with c3:
            st.metric("Strategies Built", with_strategy)
        with c4:
            st.metric("Opened", opened)
        with c5:
            st.metric("Rejected", rejected)
        with c6:
            st.metric("Blocked", blocked)

        status_rows = [
            {"status": str(d.get("status", "unknown") or "unknown"), "count": 1}
            for d in decisions
        ]
        if status_rows:
            status_df = pd.DataFrame(status_rows).groupby("status", as_index=False)["count"].sum()
            fig_status = px.bar(
                status_df.sort_values("count", ascending=False),
                x="status",
                y="count",
                title="Decision Status Distribution (Current Cycle)",
                color="count",
                color_continuous_scale="Blues",
            )
            fig_status.update_layout(height=300, xaxis_title=None, yaxis_title="Underlyings")
            st.plotly_chart(fig_status, width="stretch", key="options_panel_chart_1491")

        rows: List[Dict[str, Any]] = []
        for d in decisions:
            strategy = d.get("strategy") or {}
            rows.append({
                "Underlying": d.get("underlying", "N/A"),
                "Contracts": int(d.get("contracts", 0) or 0),
                "Spot": f"{float(d.get('spot')):,.2f}" if d.get("spot") is not None else "N/A",
                "ATM IV": f"{float(d.get('atm_iv', 0.0)):.2%}" if d.get("atm_iv") is not None else "N/A",
                "Regime": d.get("routed_regime", d.get("regime", "N/A")),
                "Objective": d.get("portfolio_objective", "N/A"),
                "Strategy": strategy.get("strategy_type", "N/A"),
                "Selected Via": (d.get("strategy_selector", {}) or {}).get("selected_source", "N/A"),
                "Decision": d.get("status", "N/A"),
                "Reason": self._decision_reason(d),
            })
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

    def render_strategy_pipeline(self, summary: Dict[str, Any]) -> None:
        """Render generated strategy candidates with leg-level details."""
        st.subheader("🧠 Strategy Pipeline (This Cycle)")
        decisions = summary.get("underlying_decisions", []) or []
        candidates = [d for d in decisions if isinstance((d.get("strategy") or None), dict)]
        if not candidates:
            st.info("No strategy candidates generated in the latest cycle.")
            return

        st.caption(f"Showing {len(candidates)} generated candidates from the latest cycle")
        for d in candidates:
            strategy = d.get("strategy") or {}
            eligibility = d.get("eligibility") or {}
            with st.expander(
                f"{d.get('underlying', 'N/A')} • {strategy.get('strategy_type', 'N/A')} • {d.get('status', 'N/A')}",
                expanded=False,
            ):
                selector = d.get("strategy_selector", {}) or {}
                st.caption(
                    f"Objective: {str(d.get('portfolio_objective', 'N/A')).replace('_', ' ')} | "
                    f"Selection: {selector.get('reason', 'N/A')}"
                )
                status = str(d.get("status", "N/A") or "N/A")
                if self._is_rejected_status(status) or status.lower().startswith("blocked"):
                    st.error(f"Decision reason: {self._decision_reason(d)}")

                k1, k2, k3, k4, k5 = st.columns(5)
                with k1:
                    st.metric("Max Loss", f"₹{float(strategy.get('max_loss', 0.0) or 0.0):,.0f}")
                with k2:
                    st.metric("Max Profit", f"₹{float(strategy.get('max_profit', 0.0) or 0.0):,.0f}")
                with k3:
                    st.metric("Net Credit/Debit", f"₹{float(strategy.get('net_credit_debit', 0.0) or 0.0):,.0f}")
                with k4:
                    rr = strategy.get("risk_reward_ratio")
                    st.metric("Risk/Reward", f"{float(rr):.2f}" if rr is not None else "N/A")
                with k5:
                    st.metric("DTE", int(strategy.get("days_to_expiry", 0) or 0))

                greeks = strategy.get("greeks", {}) or {}
                st.caption(
                    "Greeks: "
                    f"Δ={float(greeks.get('delta', 0.0) or 0.0):.3f}, "
                    f"Γ={float(greeks.get('gamma', 0.0) or 0.0):.3f}, "
                    f"Θ={float(greeks.get('theta', 0.0) or 0.0):.3f}, "
                    f"V={float(greeks.get('vega', 0.0) or 0.0):.3f}"
                )

                legs = strategy.get("legs", []) or []
                if legs:
                    legs_df = pd.DataFrame(legs)
                    st.markdown("**Legs**")
                    st.dataframe(legs_df, width="stretch", hide_index=True)

                    payoff_df = self._strategy_payoff_curve(strategy)
                    if not payoff_df.empty:
                        payoff_fig = go.Figure()
                        payoff_fig.add_trace(
                            go.Scatter(
                                x=payoff_df["underlying_price"],
                                y=payoff_df["pnl"],
                                mode="lines",
                                name="Expiry Payoff",
                                line=dict(color="#2d6cdf", width=2),
                            )
                        )
                        payoff_fig.add_hline(y=0, line_dash="dash", line_color="#888")
                        spot_ref = self._safe_float(payoff_df["spot_ref"].iloc[0], 0.0)
                        if spot_ref > 0:
                            payoff_fig.add_vline(
                                x=spot_ref,
                                line_dash="dot",
                                line_color="#22c55e",
                                annotation_text="Spot",
                                annotation_position="top",
                            )
                        payoff_fig.update_layout(
                            title="Strategy Payoff Curve (at Expiry, premium-adjusted)",
                            xaxis_title="Underlying Price",
                            yaxis_title="P&L (unit-scaled by leg quantity)",
                            height=320,
                        )
                        st.plotly_chart(payoff_fig, width="stretch", key="options_strategy_payoff_curve")

                    greek_df = pd.DataFrame(
                        {
                            "greek": ["Delta", "Gamma", "Theta", "Vega"],
                            "value": [
                                self._safe_float(greeks.get("delta"), 0.0),
                                self._safe_float(greeks.get("gamma"), 0.0),
                                self._safe_float(greeks.get("theta"), 0.0),
                                self._safe_float(greeks.get("vega"), 0.0),
                            ],
                        }
                    )
                    greek_fig = px.bar(
                        greek_df,
                        x="greek",
                        y="value",
                        color="value",
                        color_continuous_scale="RdBu",
                        title="Strategy Greek Exposures",
                    )
                    greek_fig.update_layout(height=300, showlegend=False)
                    st.plotly_chart(greek_fig, width="stretch", key="options_panel_chart_1614")

                st.markdown("**Eligibility**")
                st.write(f"Eligible: {'Yes' if eligibility.get('is_eligible') else 'No'}")
                st.write(f"Size adjustment: {float(eligibility.get('size_adjustment', 1.0) or 1.0):.2f}x")
                violations = eligibility.get("violations") or []
                if violations:
                    st.error("Violations: " + "; ".join(violations))

                checks = eligibility.get("checks") or []
                if checks:
                    checks_df = pd.DataFrame(checks)
                    st.dataframe(checks_df, width="stretch", hide_index=True)

                scored_candidates = selector.get("candidates", []) or []
                if scored_candidates:
                    st.markdown("**Candidate Scoring (objective optimizer)**")
                    score_rows = []
                    for row in scored_candidates:
                        score_rows.append({
                            "Source": row.get("source", "N/A"),
                            "Strategy": row.get("strategy_type", "N/A"),
                            "Score": f"{float(row.get('score', 0.0) or 0.0):.3f}",
                            "Max Loss": f"₹{float(row.get('max_loss', 0.0) or 0.0):,.0f}",
                            "Max Profit": f"₹{float(row.get('max_profit', 0.0) or 0.0):,.0f}",
                            "Net Credit/Debit": f"₹{float(row.get('net_credit_debit', 0.0) or 0.0):,.0f}",
                        })
                    st.dataframe(pd.DataFrame(score_rows), width="stretch", hide_index=True)

                    raw_df = pd.DataFrame(scored_candidates).copy()
                    for c in ("score", "max_loss", "max_profit", "net_credit_debit"):
                        if c in raw_df.columns:
                            raw_df[c] = pd.to_numeric(raw_df[c], errors="coerce")
                    scatter_cols = {"max_loss", "max_profit", "score"}
                    if scatter_cols.issubset(set(raw_df.columns)):
                        fig_sc = px.scatter(
                            raw_df,
                            x="max_loss",
                            y="max_profit",
                            color="score",
                            hover_data=[c for c in ["strategy_type", "source", "net_credit_debit"] if c in raw_df.columns],
                            title="Candidate Frontier: Max Loss vs Max Profit",
                            color_continuous_scale="Viridis",
                        )
                        fig_sc.update_layout(height=320, xaxis_title="Max Loss (₹)", yaxis_title="Max Profit (₹)")
                        st.plotly_chart(fig_sc, width="stretch", key="options_panel_chart_1659")

    def render_decision_history(self, summary: Dict[str, Any]) -> None:
        """Render compact rolling decision history for quick diagnosis."""
        st.subheader("🕘 Decision Log")
        rows = summary.get("decision_history", []) or []
        if not rows:
            st.info("No decision history rows available yet.")
            return

        normalized_rows: List[Dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            out = dict(row)
            out["reason"] = self._decision_reason(out)
            violations = self._normalize_violations(out.get("violations"))
            if not violations:
                eligibility = out.get("eligibility")
                if isinstance(eligibility, dict):
                    violations = self._normalize_violations(eligibility.get("violations"))
            out["violations"] = "; ".join(violations)
            normalized_rows.append(out)

        df = pd.DataFrame(normalized_rows)
        if df.empty:
            st.info("No decision history rows available yet.")
            return

        if "timestamp" in df.columns:
            ts = pd.to_datetime(df["timestamp"], errors="coerce")
            df["_ts"] = ts
            df["timestamp"] = ts.dt.strftime("%Y-%m-%d %H:%M:%S")

        controls = st.columns([2, 2, 1])
        with controls[0]:
            statuses = sorted([str(s) for s in df.get("status", pd.Series(dtype=str)).dropna().astype(str).unique().tolist()])
            selected_statuses = st.multiselect("Status Filter", statuses, default=statuses)
        with controls[1]:
            underlyings = sorted([str(u) for u in df.get("underlying", pd.Series(dtype=str)).dropna().astype(str).unique().tolist()])
            selected_underlyings = st.multiselect("Underlying Filter", underlyings, default=underlyings)
        with controls[2]:
            row_cap = st.selectbox("Rows", [25, 50, 100, 200], index=1)

        if "status" in df.columns and selected_statuses:
            df = df[df["status"].astype(str).isin(selected_statuses)]
        if "underlying" in df.columns and selected_underlyings:
            df = df[df["underlying"].astype(str).isin(selected_underlyings)]
        if "_ts" in df.columns:
            df = df.sort_values("_ts", ascending=False)
        df = df.head(int(row_cap))

        order = [
            c
            for c in [
                "timestamp",
                "underlying",
                "objective",
                "regime",
                "strategy_type",
                "selected_source",
                "status",
                "reason",
                "contracts",
                "violations",
            ]
            if c in df.columns
        ]
        st.dataframe(df[order], width="stretch", hide_index=True)
    
    def render_trade_history(self, summary: Dict[str, Any]) -> None:
        """Render trade history and metrics"""
        st.subheader("📜 Trade History")
        
        metrics = summary.get('trade_metrics', {})
        
        # Trade metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "Total Trades",
                metrics.get('total_trades', 0),
                help="Total number of closed trades"
            )
        
        with col2:
            win_rate = metrics.get('win_rate', 0.0)
            st.metric(
                "Win Rate",
                f"{win_rate:.1%}",
                help="Percentage of profitable trades"
            )
        
        with col3:
            avg_profit = metrics.get('avg_profit', 0.0)
            st.metric(
                "Avg Profit",
                f"₹{avg_profit:,.0f}",
                help="Average profit per winning trade"
            )
        
        with col4:
            profit_factor = metrics.get('profit_factor', 0.0)
            st.metric(
                "Profit Factor",
                f"{profit_factor:.2f}",
                help="Total profit / Total loss"
            )
        
        # Recent trades table
        trades = self.observer.get_trade_history(limit=10)
        
        if trades:
            st.markdown("#### Recent Trades")
            
            table_data = []
            for trade in trades:
                entry_time = self._safe_datetime(trade.get('entry_time'))
                
                table_data.append({
                    'Date': entry_time.strftime('%Y-%m-%d') if entry_time else 'N/A',
                    'Strategy': trade.get('strategy_type', 'N/A').replace('_', ' ').title(),
                    'P&L': f"₹{trade.get('realized_pnl', 0.0):,.0f}",
                    'Days': trade.get('hold_duration_days', 0),
                    'Exit Reason': str(trade.get('exit_reason') or 'N/A').replace('_', ' ').title()
                })
            
            df = pd.DataFrame(table_data)
            st.dataframe(df, width="stretch", hide_index=True)
    
    def render_trade_eligibility(self, summary: Dict[str, Any]) -> None:
        """Render next trade eligibility status"""
        st.subheader("✅ Next Trade Eligibility")
        
        eligibility = summary.get('trade_eligibility', {})
        checks = summary.get('eligibility_checks', [])
        
        # Overall status
        signal_generated = eligibility.get('signal_generated', False)
        rejected = eligibility.get('rejected', False)
        stale = bool(eligibility.get('stale', False))

        if stale and not signal_generated:
            st.warning("⏳ Waiting for fresh eligibility evaluation (latest snapshot is stale)")
        elif signal_generated and not rejected:
            st.success("✓ Trade signal generated and eligible")
            strategy = eligibility.get('strategy_type', 'N/A')
            st.info(f"Strategy: {strategy.replace('_', ' ').title()}")
        elif rejected:
            st.error("✗ Trade signal rejected")
            violations = eligibility.get('violations', [])
            if violations:
                st.caption("Violations:")
                for v in violations:
                    st.caption(f"  • {v}")
        else:
            st.info("⏳ No trade signal generated yet")
        
        # Detailed eligibility checks
        st.markdown("#### Eligibility Checks")
        
        for check in checks:
            check_name = check.get('check', 'Unknown')
            passed = check.get('passed', False)
            detail = check.get('detail', '')
            check_stale = bool(check.get("stale", False))
            
            status_icon = "✓" if passed else "✗"
            
            col1, col2 = st.columns([1, 3])
            
            with col1:
                if check_stale and not passed:
                    st.warning(f"⚠ {check_name}")
                elif passed:
                    st.success(f"{status_icon} {check_name}")
                else:
                    st.error(f"{status_icon} {check_name}")
            
            with col2:
                if check_stale:
                    st.caption(f"{detail} (stale snapshot)")
                else:
                    st.caption(detail)


def render_options_panel(observer: Optional[OptionsObserver] = None) -> None:
    """
    Convenience function to render options panel
    
    Args:
        observer: OptionsObserver instance (optional)
    """
    panel = OptionsPanel(observer=observer)
    panel.render()


if __name__ == "__main__":
    # Test options panel
    st.set_page_config(page_title="Options Trading Panel", layout="wide")
    
    # Create test observer with mock data
    observer = OptionsObserver()
    
    # Simulate some events
    observer.on_regime_change({
        'old_regime': 'NEUTRAL',
        'new_regime': 'LOW_VOL_SELL',
        'iv_rank': 0.75,
        'days_in_old_regime': 5,
        'reason': 'IV rank exceeded 70%',
        'timestamp': datetime.now()
    })
    
    observer.on_position_opened({
        'position_id': 'POS_20240115_123456_IRON_CONDOR',
        'strategy_type': 'IRON_CONDOR',
        'max_loss': 5000.0,
        'entry_time': datetime.now() - timedelta(days=5),
        'legs': [],
        'timestamp': datetime.now()
    })
    
    observer.on_position_updated({
        'position_id': 'POS_20240115_123456_IRON_CONDOR',
        'unrealized_pnl': 2100.0,
        'current_value': 2100.0,
        'portfolio_greeks': {
            'delta': -0.05,
            'gamma': 0.02,
            'theta': 150.0,
            'vega': -0.15
        },
        'timestamp': datetime.now()
    })
    
    # Render panel
    render_options_panel(observer=observer)
