#!/usr/bin/env python3
"""Security Viewer — the DES page: everything Northstar knows about one name.

Bloomberg's core insight is entity-centric drill-down: you don't browse charts,
you ask "tell me everything about RELIANCE". This page answers that in one
screen: price/volume history, the v3 score, the full valuation-engine stack,
quality/ratio snapshot, news sentiment, smart-money bulk deals, promoter
pledge, corporate announcements, credit-rating actions, live options
suggestions on the name, and a peer comparison within its industry.

All panels read canonical artifacts; every loader is cached. A missing surface
degrades to a quiet caption, never an error.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from src.dashboard.layout.terminal_theme import TERM, apply_terminal_layout

PROJECT_ROOT = Path(__file__).resolve().parents[3]
_MONO = TERM["mono"]

TICKER_STATE_KEY = "des_ticker"


# --------------------------------------------------------------------------- #
# cached loaders
# --------------------------------------------------------------------------- #
@st.cache_data(ttl=600, show_spinner=False)
def _universe() -> pd.DataFrame:
    """ticker -> Company Name, Industry (the searchable universe)."""
    p = PROJECT_ROOT / "data/processed/scores.parquet"
    if not p.exists():
        return pd.DataFrame()
    df = pd.read_parquet(p)
    keep = [c for c in ("ticker", "Company Name", "Industry", "northstar_score", "quintile", "suggested_weight") if c in df.columns]
    return df[keep].dropna(subset=["ticker"]).drop_duplicates("ticker")


@st.cache_data(ttl=600, show_spinner=False)
def _prices(ticker: str) -> pd.DataFrame:
    p = PROJECT_ROOT / "data/processed/prices.parquet"
    if not p.exists():
        return pd.DataFrame()
    try:
        df = pd.read_parquet(p, filters=[("ticker", "==", ticker)])
    except Exception:
        df = pd.read_parquet(p)
        df = df[df["ticker"] == ticker]
    if df.empty:
        return df
    df = df.copy()
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    return df.dropna(subset=["Date"]).sort_values("Date")


@st.cache_data(ttl=600, show_spinner=False)
def _valuation_row(ticker: str) -> pd.Series:
    p = PROJECT_ROOT / "data/processed/valuation.parquet"
    if not p.exists():
        return pd.Series(dtype=object)
    df = pd.read_parquet(p)
    hit = df[df["ticker"] == ticker]
    return hit.iloc[-1] if not hit.empty else pd.Series(dtype=object)


@st.cache_data(ttl=600, show_spinner=False)
def _sentiment(ticker: str) -> pd.DataFrame:
    p = PROJECT_ROOT / "data/processed/sentiment/ticker_sentiment_daily.parquet"
    if not p.exists():
        return pd.DataFrame()
    try:
        df = pd.read_parquet(p, filters=[("ticker", "==", ticker)])
    except Exception:
        df = pd.read_parquet(p)
        df = df[df["ticker"] == ticker]
    if df.empty:
        return df
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    return df.dropna(subset=["date"]).sort_values("date")


@st.cache_data(ttl=600, show_spinner=False)
def _alt_frame(rel: str, ticker_col: str, ticker: str) -> pd.DataFrame:
    p = PROJECT_ROOT / rel
    if not p.exists():
        return pd.DataFrame()
    try:
        df = pd.read_parquet(p) if rel.endswith("parquet") else pd.read_csv(p)
    except Exception:
        return pd.DataFrame()
    if ticker_col not in df.columns:
        return pd.DataFrame()
    hit = df[df[ticker_col].astype(str) == ticker].copy()
    if "date" in hit.columns:
        hit["date"] = pd.to_datetime(hit["date"], errors="coerce")
        hit = hit.sort_values("date")
    return hit


@st.cache_data(ttl=300, show_spinner=False)
def _options_on(ticker: str) -> pd.DataFrame:
    p = PROJECT_ROOT / "data/options/suggestions/options_suggestions_latest.json"
    if not p.exists():
        return pd.DataFrame()
    try:
        data = json.loads(p.read_text())
    except Exception:
        return pd.DataFrame()
    rows = [s for cat in (data.get("suggestions") or {}).values() for s in cat if s.get("underlying") == ticker]
    return pd.DataFrame(rows)


@st.cache_data(ttl=300, show_spinner=False)
def _options_universe_size() -> int:
    """How many distinct underlyings the options organ currently covers —
    context for why most names show no active suggestion on any given day."""
    p = PROJECT_ROOT / "data/options/suggestions/options_suggestions_latest.json"
    if not p.exists():
        return 0
    try:
        data = json.loads(p.read_text())
    except Exception:
        return 0
    names = {s.get("underlying") for cat in (data.get("suggestions") or {}).values() for s in cat}
    return len(names)


@st.cache_data(ttl=600, show_spinner=False)
def _uni_size() -> int:
    return len(_universe())


# --------------------------------------------------------------------------- #
# panel builders
# --------------------------------------------------------------------------- #
def _fmt(v, pattern="{:,.2f}", dash="—") -> str:
    try:
        f = float(v)
        if pd.isna(f):
            return dash
        return pattern.format(f)
    except Exception:
        return dash


def _fmt_cr(v) -> str:
    """Format a rupee amount in crores."""
    try:
        f = float(v)
        if pd.isna(f):
            return "—"
        return f"₹{f/1e7:,.0f} Cr"
    except Exception:
        return "—"


def _metric_html(label: str, value: str, color: str = TERM["text"]) -> str:
    return (
        f'<div style="padding:6px 10px;border:1px solid {TERM["border"]};background:{TERM["panel"]};">'
        f'<div style="font-family:{_MONO};font-size:0.62rem;color:{TERM["muted"]};text-transform:uppercase;">{label}</div>'
        f'<div style="font-family:{_MONO};font-size:1.05rem;font-weight:700;color:{color};">{value}</div></div>'
    )


def _price_figure(px_df: pd.DataFrame, window: str) -> Optional[go.Figure]:
    if px_df.empty:
        return None
    days = {"3M": 66, "1Y": 252, "5Y": 1260, "MAX": len(px_df)}.get(window, 252)
    df = px_df.tail(max(days, 30)).copy()
    full = px_df.copy()
    full["dma50"] = full["Close"].rolling(50).mean()
    full["dma200"] = full["Close"].rolling(200).mean()
    df = df.merge(full[["Date", "dma50", "dma200"]], on="Date", how="left")
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.78, 0.22], vertical_spacing=0.03)
    fig.add_trace(go.Candlestick(
        x=df["Date"], open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"],
        increasing=dict(line=dict(color=TERM["up"]), fillcolor=TERM["up"]),
        decreasing=dict(line=dict(color=TERM["down"]), fillcolor=TERM["down"]),
        name="OHLC", showlegend=False,
    ), row=1, col=1)
    fig.add_trace(go.Scatter(x=df["Date"], y=df["dma50"], mode="lines", name="50-DMA",
                             line=dict(color=TERM["cyan"], width=1)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df["Date"], y=df["dma200"], mode="lines", name="200-DMA",
                             line=dict(color=TERM["amber"], width=1)), row=1, col=1)
    vol_colors = [TERM["up"] if c >= o else TERM["down"] for c, o in zip(df["Close"], df["Open"])]
    fig.add_trace(go.Bar(x=df["Date"], y=df["Volume"], marker_color=vol_colors, showlegend=False,
                         name="Volume"), row=2, col=1)
    fig.update_layout(height=470, xaxis_rangeslider_visible=False,
                      legend=dict(orientation="h", y=1.03, x=0))
    return apply_terminal_layout(fig)


def _engine_gap_figure(val: pd.Series) -> Optional[go.Figure]:
    """Every valuation engine's verdict on one chart: % gap to fair value."""
    engines = [
        ("core_gap", "Core"), ("fcff_gap", "FCFF DCF"), ("fcfe_gap", "FCFE DCF"),
        ("ddm_gap", "Dividend"), ("apv_gap", "APV"), ("residual_gap", "Residual Inc."),
        ("transaction_gap", "Transactions"), ("lbo_gap", "LBO"), ("credit_gap", "Credit"),
        ("real_option_gap", "Real Option"),
    ]
    rows = [(label, float(val[c]) * 100) for c, label in engines
            if c in val.index and pd.notna(val[c]) and np.isfinite(float(val[c]))]
    if not rows:
        return None
    rows.sort(key=lambda r: r[1])
    labels = [r[0] for r in rows]
    gaps = [r[1] for r in rows]
    colors = [TERM["up"] if g > 0 else TERM["down"] for g in gaps]
    fig = go.Figure(go.Bar(
        x=gaps, y=labels, orientation="h", marker_color=colors,
        text=[f"{g:+.0f}%" for g in gaps], textposition="outside", textfont=dict(size=9),
        hovertemplate="%{y}: %{x:+.1f}% vs fair value<extra></extra>",
    ))
    post_gap = val.get("posterior_gap")
    if pd.notna(post_gap):
        fig.add_vline(x=float(post_gap) * 100, line=dict(color=TERM["amber"], width=2, dash="dash"))
        fig.add_annotation(x=float(post_gap) * 100, y=1.06, yref="paper", showarrow=False,
                           text=f"posterior {float(post_gap)*100:+.0f}%", font=dict(color=TERM["amber"], size=10))
    fig.add_vline(x=0, line=dict(color=TERM["border"], width=1))
    fig.update_layout(height=380, xaxis_title="% gap to fair value (+ = undervalued)")
    return apply_terminal_layout(fig)


def _sentiment_figure(sent: pd.DataFrame) -> Optional[go.Figure]:
    if sent.empty:
        return None
    df = sent.tail(365).copy()
    df["polarity_sm"] = pd.to_numeric(df["sentiment_polarity"], errors="coerce").rolling(10, min_periods=1).mean()
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(x=df["date"], y=df["news_volume"], name="News volume",
                         marker_color=TERM["grid"], opacity=0.9), secondary_y=True)
    fig.add_trace(go.Scatter(x=df["date"], y=df["polarity_sm"], name="Polarity (10d avg)",
                             mode="lines", line=dict(color=TERM["cyan"], width=1.6)), secondary_y=False)
    if "sentiment_surprise" in df.columns:
        spikes = df[pd.to_numeric(df["sentiment_surprise"], errors="coerce").abs() > 1.5]
        if not spikes.empty:
            fig.add_trace(go.Scatter(x=spikes["date"], y=spikes["polarity_sm"], mode="markers",
                                     name="Surprise", marker=dict(color=TERM["amber"], size=7, symbol="diamond")),
                          secondary_y=False)
    fig.add_hline(y=0, line=dict(color=TERM["border"], width=1))
    fig.update_layout(height=380)
    fig.update_yaxes(title_text="polarity", secondary_y=False)
    fig.update_yaxes(title_text="stories/day", secondary_y=True, showgrid=False)
    return apply_terminal_layout(fig)


def _pledge_figure(pledge: pd.DataFrame) -> Optional[go.Figure]:
    if pledge.empty or "pledge_pct" not in pledge.columns:
        return None
    df = pledge.dropna(subset=["date"]).copy()
    df["pledge_pct"] = pd.to_numeric(df["pledge_pct"], errors="coerce")
    df = df.dropna(subset=["pledge_pct"])
    if df.empty:
        return None
    cur = float(df["pledge_pct"].iloc[-1])
    fig = go.Figure(go.Scatter(
        x=df["date"], y=df["pledge_pct"], mode="lines+markers",
        line=dict(color=TERM["down"] if cur > 25 else TERM["amber"] if cur > 0 else TERM["up"], width=1.6),
        marker=dict(size=4), fill="tozeroy",
        hovertemplate="%{x|%b %Y}: %{y:.1f}%<extra></extra>",
    ))
    fig.add_hline(y=25, line=dict(color=TERM["down"], width=1, dash="dot"))
    fig.update_layout(height=300, yaxis_title="promoter shares pledged %")
    return apply_terminal_layout(fig)


def _small_table(df: pd.DataFrame, title_cols: dict[str, str], height: int = 300) -> go.Figure:
    header = list(title_cols.values())
    cols = [df[c].astype(str).tolist() for c in title_cols.keys()]
    fig = go.Figure(go.Table(
        header=dict(values=[f"<b>{h}</b>" for h in header], fill_color=TERM["panel_alt"], align="left",
                    font=dict(family=_MONO, color=TERM["amber"], size=10), line_color=TERM["border"], height=24),
        cells=dict(values=cols, fill_color=TERM["panel"], align="left",
                   font=dict(family=_MONO, color=TERM["text"], size=10), line_color=TERM["border"], height=21),
    ))
    fig.update_layout(height=height, margin=dict(l=4, r=4, t=6, b=4))
    return apply_terminal_layout(fig)


def _peer_table(uni: pd.DataFrame, val_all: pd.DataFrame, ticker: str, industry: str) -> Optional[go.Figure]:
    peers = uni[uni["Industry"] == industry].copy()
    if peers.empty or len(peers) < 2:
        return None
    if not val_all.empty:
        vcols = [c for c in ("ticker", "pe", "roe", "margin_of_safety_pct", "market_cap", "moat_score_v2") if c in val_all.columns]
        peers = peers.merge(val_all[vcols], on="ticker", how="left")
    score = pd.to_numeric(peers.get("northstar_score"), errors="coerce")
    peers["z"] = (score - score.mean()) / score.std(ddof=0) if score.std(ddof=0) > 1e-9 else 0.0
    peers = peers.sort_values("z", ascending=False).head(12)
    fill = [["rgba(255,176,0,0.16)" if t == ticker else "rgba(255,255,255,0.02)" for t in peers["ticker"]]]
    # NOTE: DataFrame.get(col, default) returns the bare `default` scalar (not
    # a Series) when the column is missing, which breaks iteration/.astype
    # below — always fall back to a same-length Series.
    def _col(name: str, default=np.nan) -> pd.Series:
        return peers[name] if name in peers.columns else pd.Series(default, index=peers.index)
    show = pd.DataFrame({
        "Ticker": peers["ticker"].str.replace(".NS", "", regex=False),
        "Company": _col("Company Name", "").astype(str).str.slice(0, 20),
        "Score z": [_fmt(v, "{:+.2f}") for v in peers["z"]],
        "P/E": [_fmt(v, "{:.1f}") for v in _col("pe")],
        "ROE": [_fmt(v, "{:.1%}") for v in _col("roe")],
        "MoS%": [_fmt(v, "{:+.0f}") for v in _col("margin_of_safety_pct")],
        "MktCap": [_fmt_cr(v) for v in _col("market_cap")],
    })
    fig = go.Figure(go.Table(
        header=dict(values=[f"<b>{c}</b>" for c in show.columns], fill_color=TERM["panel_alt"], align="left",
                    font=dict(family=_MONO, color=TERM["amber"], size=10), line_color=TERM["border"], height=24),
        cells=dict(values=[show[c].tolist() for c in show.columns], fill_color=fill * len(show.columns),
                   align="left", font=dict(family=_MONO, color=TERM["text"], size=10),
                   line_color=TERM["border"], height=21),
    ))
    fig.update_layout(height=max(220, 90 + 24 * len(show)), margin=dict(l=4, r=4, t=6, b=4))
    return apply_terminal_layout(fig)


@st.cache_data(ttl=600, show_spinner=False)
def _valuation_all() -> pd.DataFrame:
    p = PROJECT_ROOT / "data/processed/valuation.parquet"
    if not p.exists():
        return pd.DataFrame()
    cols = ["ticker", "pe", "pb", "roe", "debt_equity", "fcf_yield", "market_cap",
            "margin_of_safety_pct", "moat_score_v2", "earnings_quality_grade_v2",
            "dcf_upside_v2", "final_value_index", "posterior_gap", "posterior_confidence"]
    df = pd.read_parquet(p)
    return df[[c for c in cols if c in df.columns]]


def _panel(title: str, note: str = "") -> None:
    sub = f'<span style="color:{TERM["muted"]};font-size:0.66rem;"> · {note}</span>' if note else ""
    st.markdown(
        f'<div style="font-family:{_MONO};color:{TERM["amber"]};font-weight:700;'
        f'font-size:0.78rem;letter-spacing:0.08em;margin:10px 0 2px 0;">{title}{sub}</div>',
        unsafe_allow_html=True,
    )


# --------------------------------------------------------------------------- #
# page renderer
# --------------------------------------------------------------------------- #
def render(bundle: dict) -> tuple[int, int]:
    uni = _universe()
    if uni.empty:
        st.warning("Universe unavailable — data/processed/scores.parquet missing.")
        return 0, 1

    labels = {
        t: f"{t.replace('.NS','')} — {n}"
        for t, n in zip(uni["ticker"], uni.get("Company Name", uni["ticker"]))
    }
    tickers = sorted(labels)
    # The command bar (and prior visits) manage this key via session state, so
    # never pass index= alongside key= — that combination triggers Streamlit's
    # "default value + Session State API" warning.
    if st.session_state.get(TICKER_STATE_KEY) not in labels:
        st.session_state[TICKER_STATE_KEY] = "RELIANCE.NS" if "RELIANCE.NS" in labels else tickers[0]

    top = st.columns([3, 1])
    with top[0]:
        ticker = st.selectbox("Security", tickers,
                              format_func=lambda t: labels.get(t, t), key=TICKER_STATE_KEY,
                              label_visibility="collapsed")
    with top[1]:
        window = st.radio("Range", ["3M", "1Y", "5Y", "MAX"], index=1, horizontal=True,
                          label_visibility="collapsed")

    rendered, total = 0, 0
    px_df = _prices(ticker)
    val = _valuation_row(ticker)
    urow = uni[uni["ticker"] == ticker].iloc[0]

    # ---- header strip: the DES vitals ----
    last_close = float(px_df["Close"].iloc[-1]) if not px_df.empty else np.nan
    prev_close = float(px_df["Close"].iloc[-2]) if len(px_df) > 1 else np.nan
    chg = (last_close / prev_close - 1) * 100 if pd.notna(last_close) and pd.notna(prev_close) else np.nan
    chg_color = TERM["up"] if (pd.notna(chg) and chg >= 0) else TERM["down"]
    score = pd.to_numeric(urow.get("northstar_score"), errors="coerce")
    all_scores = pd.to_numeric(uni["northstar_score"], errors="coerce")
    z = (score - all_scores.mean()) / all_scores.std(ddof=0) if all_scores.std(ddof=0) > 1e-9 else np.nan
    cells = [
        ("LAST", _fmt(last_close, "₹{:,.1f}"), TERM["text"]),
        ("CHG", _fmt(chg, "{:+.2f}%"), chg_color),
        ("MKT CAP", _fmt_cr(val.get("market_cap")), TERM["text"]),
        ("P/E", _fmt(val.get("pe"), "{:.1f}"), TERM["text"]),
        ("ROE", _fmt(val.get("roe"), "{:.1%}"), TERM["text"]),
        ("V3 SCORE z", _fmt(z, "{:+.2f}"), TERM["up"] if (pd.notna(z) and z >= 0) else TERM["down"]),
        ("MoS", _fmt(val.get("margin_of_safety_pct"), "{:+.0f}%"), TERM["text"]),
        ("QUALITY", str(val.get("earnings_quality_grade_v2", "—") or "—"), TERM["cyan"]),
    ]
    strip = st.columns(len(cells))
    for col, (label, value, color) in zip(strip, cells):
        with col:
            st.markdown(_metric_html(label, value, color), unsafe_allow_html=True)
    st.markdown(
        f'<div style="font-family:{_MONO};color:{TERM["muted"]};font-size:0.7rem;margin:2px 0 6px 0;">'
        f'{urow.get("Company Name", ticker)} · {urow.get("Industry", "—")} · price history '
        f'{px_df["Date"].min():%Y} → {px_df["Date"].max():%d %b %Y}</div>' if not px_df.empty else "",
        unsafe_allow_html=True,
    )

    # ---- price / volume ----
    _panel("PRICE & VOLUME", f"candles · 50/200-DMA · {window}")
    fig = _price_figure(px_df, window)
    total += 1
    if fig is not None:
        st.plotly_chart(fig, width="stretch", key="des_price", config={"displaylogo": False})
        rendered += 1
    else:
        st.caption("price history unavailable")

    # ---- valuation engines + sentiment ----
    c1, c2 = st.columns(2)
    with c1:
        _panel("VALUATION ENGINE STACK", "each engine's % gap to fair value")
        fig = _engine_gap_figure(val) if not val.empty else None
        total += 1
        if fig is not None:
            st.plotly_chart(fig, width="stretch", key="des_engines", config={"displaylogo": False})
            rendered += 1
        else:
            st.caption("valuation engines unavailable for this name")
    with c2:
        _panel("NEWS SENTIMENT", "polarity trend · story volume · surprises")
        fig = _sentiment_figure(_sentiment(ticker))
        total += 1
        if fig is not None:
            st.plotly_chart(fig, width="stretch", key="des_sent", config={"displaylogo": False})
            rendered += 1
        else:
            st.caption("no news sentiment history for this name")

    # ---- quality snapshot + options on the name ----
    c1, c2 = st.columns(2)
    with c1:
        _panel("QUALITY & VALUE SNAPSHOT")
        total += 1
        if not val.empty:
            # Raw fcf_yield derives from reported operating-cashflow/capex lines
            # that yfinance only populates for ~8% of the universe (41/500) —
            # RELIANCE and most large-caps show a bare "—" here. owner_earnings
            # _yield_v2 is the same "cash the business actually generates"
            # concept, built via the institutional owner-earnings methodology,
            # and has full 500/500 coverage — use it as the primary figure,
            # falling back to the raw reported FCF yield only when present.
            oe_yield = val.get("owner_earnings_yield_v2")
            raw_fcf = val.get("fcf_yield")
            fcf_label = "Owner earnings yield" if pd.notna(pd.to_numeric(oe_yield, errors="coerce")) else "FCF yield"
            fcf_value = oe_yield if pd.notna(pd.to_numeric(oe_yield, errors="coerce")) else raw_fcf
            snap = pd.DataFrame({
                "Metric": ["P/B", fcf_label, "Debt/Equity", "Moat score", "DCF upside",
                           "Final value index", "Posterior gap", "Posterior confidence"],
                "Value": [
                    _fmt(val.get("pb"), "{:.2f}"), _fmt(fcf_value, "{:.1%}"),
                    _fmt(val.get("debt_equity"), "{:.2f}"), _fmt(val.get("moat_score_v2"), "{:.0f}/100"),
                    _fmt(val.get("dcf_upside_v2"), "{:+.0%}"), _fmt(val.get("final_value_index"), "{:.1f}"),
                    _fmt(pd.to_numeric(val.get("posterior_gap"), errors="coerce") * 100 if pd.notna(val.get("posterior_gap")) else np.nan, "{:+.0f}%"),
                    _fmt(val.get("posterior_confidence"), "{:.0%}"),
                ],
            })
            st.plotly_chart(_small_table(snap, {"Metric": "Metric", "Value": "Value"}, height=300),
                            width="stretch", key="des_snap", config={"displaylogo": False})
            rendered += 1
        else:
            st.caption("valuation snapshot unavailable")
    with c2:
        _panel("OPTIONS DESK VIEW", "live v3 suggestions on this underlying")
        opts = _options_on(ticker)
        total += 1
        if not opts.empty:
            show = pd.DataFrame({
                "Type": opts["category"].str.upper(),
                "Structure": opts["structure"].astype(str),
                "MaxLoss": [_fmt(v, "{:,.0f}") for v in opts["max_loss"]],
                "Δ": [_fmt(v, "{:+.2f}") for v in opts["net_delta"]],
                "Priority": [_fmt(v, "{:.2f}") for v in opts["priority"]],
            })
            st.plotly_chart(_small_table(show, {c: c for c in show.columns}, height=200),
                            width="stretch", key="des_opts", config={"displaylogo": False})
            rendered += 1
        else:
            # The options organ only carries the day's top-conviction names
            # (~30 out of the ~500-name universe) — most tickers legitimately
            # have no active suggestion on any given day. Say that plainly
            # instead of leaving a bare "no data" line that reads as broken.
            covered = _options_universe_size()
            st.caption(
                f"not in today's top-{covered} options conviction list "
                f"(the organ ranks the whole {_uni_size()}-name universe daily "
                f"and only surfaces its highest-conviction ideas — this is "
                f"expected for most names, not a data gap)"
                if covered else "no live options suggestions on this name"
            )
        _panel("PROMOTER PLEDGE", "governance stress · red line at 25%")
        pledge = _alt_frame("data/processed/alternative/promoter_pledge_all.parquet", "nse_ticker", ticker)
        fig = _pledge_figure(pledge)
        total += 1
        if fig is not None:
            st.plotly_chart(fig, width="stretch", key="des_pledge", config={"displaylogo": False})
            rendered += 1
        else:
            st.caption("no pledge disclosures — promoter book is clean or unreported")

    # ---- smart money + corporate events ----
    c1, c2 = st.columns(2)
    with c1:
        _panel("SMART-MONEY BULK DEALS", "latest institutional prints")
        deals = _alt_frame("data/processed/alternative/bulk_deals_nse_all.parquet", "nse_ticker", ticker)
        total += 1
        if not deals.empty:
            recent = deals.tail(15).iloc[::-1]
            show = pd.DataFrame({
                "Date": recent["date"].dt.strftime("%d-%b-%y"),
                "Client": recent["client_name"].astype(str).str.slice(0, 26),
                "Side": recent["deal_type"].astype(str).str.upper(),
                "Qty": [_fmt(v, "{:,.0f}") for v in recent["quantity"]],
                "Price": [_fmt(v, "₹{:,.1f}") for v in recent["price"]],
            })
            st.plotly_chart(_small_table(show, {c: c for c in show.columns}, height=max(220, 90 + 23 * len(show))),
                            width="stretch", key="des_deals", config={"displaylogo": False})
            rendered += 1
        else:
            st.caption("no bulk-deal prints on this name")
    with c2:
        _panel("CORPORATE EVENTS", "announcements & credit-rating actions")
        ann = _alt_frame("data/processed/alternative/announcements_all.parquet", "nse_ticker", ticker)
        ratings = _alt_frame("data/processed/alternative/credit_ratings_nse_all.parquet", "nse_ticker", ticker)
        total += 1
        events = []
        if not ann.empty:
            for _, r in ann.tail(8).iloc[::-1].iterrows():
                events.append((r["date"], "FILING", str(r.get("headline", ""))[:60]))
        if not ratings.empty:
            for _, r in ratings.tail(5).iloc[::-1].iterrows():
                events.append((r["date"], str(r.get("agency", "RATING"))[:10].upper(),
                               f'{r.get("action_type", "")} → {r.get("new_rating", "")} ({r.get("outlook", "—")})'))
        if events:
            events.sort(key=lambda e: (pd.Timestamp.min if pd.isna(e[0]) else e[0]), reverse=True)
            show = pd.DataFrame({
                "Date": [("—" if pd.isna(d) else f"{d:%d-%b-%y}") for d, _, _ in events[:12]],
                "Type": [t for _, t, _ in events[:12]],
                "Event": [e for _, _, e in events[:12]],
            })
            st.plotly_chart(_small_table(show, {c: c for c in show.columns},
                                         height=max(220, 90 + 23 * len(show))),
                            width="stretch", key="des_events", config={"displaylogo": False})
            rendered += 1
        else:
            st.caption("no recent filings or rating actions")

    # ---- peers ----
    _panel("PEER COMPARISON", f'{urow.get("Industry", "industry")} · ranked by v3 score (this name highlighted)')
    fig = _peer_table(uni, _valuation_all(), ticker, str(urow.get("Industry", "")))
    total += 1
    if fig is not None:
        st.plotly_chart(fig, width="stretch", key="des_peers", config={"displaylogo": False})
        rendered += 1
    else:
        st.caption("no industry peers in the scored universe")

    return rendered, total
