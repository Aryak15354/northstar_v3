"""Extra, high-density dashboard visuals: Options cockpit, market movers /
watchlist, consolidated all-in-one panels, alternative-data views, and new
chart types (tables, heatmaps, treemaps, gauges, multi-panel subplots).

Each function is a `builder(bundle) -> plotly figure | None`. They read the
canonical artifacts directly (small files, cached) so they are robust to the
bundle's key coverage. Returning None yields the standard "data missing"
placeholder. The terminal Plotly styling is layered on top by
sections.shared.render_visual, but colours are set here too so tables/treemaps
match the terminal look.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.dashboard.layout.terminal_theme import TERM

PROJECT_ROOT = Path(__file__).resolve().parents[2]
_MONO = TERM["mono"]


# --------------------------------------------------------------------------- #
# cached loaders
# --------------------------------------------------------------------------- #
def _read_parquet(rel: str) -> pd.DataFrame:
    p = PROJECT_ROOT / rel
    if not p.exists():
        return pd.DataFrame()
    try:
        return pd.read_parquet(p)
    except Exception:
        return pd.DataFrame()


def _read_csv(rel: str) -> pd.DataFrame:
    p = PROJECT_ROOT / rel
    if not p.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(p)
    except Exception:
        return pd.DataFrame()


def _load_suggestions() -> dict:
    p = PROJECT_ROOT / "data/options/suggestions/options_suggestions_latest.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}


def _flat_suggestions() -> pd.DataFrame:
    data = _load_suggestions()
    rows = []
    for cat, items in (data.get("suggestions") or {}).items():
        for s in items:
            rows.append(s)
    return pd.DataFrame(rows)


_CAT_COLOR = {
    "short": TERM["down"], "long": TERM["up"],
    "hedge": TERM["cyan"], "opportunity": TERM["amber"],
}


def _table(header: list[str], columns: list[list], *, title: str,
           colcolors: Optional[list] = None, widths: Optional[list] = None) -> go.Figure:
    fig = go.Figure(data=[go.Table(
        columnwidth=widths,
        header=dict(
            values=[f"<b>{h}</b>" for h in header],
            fill_color=TERM["panel_alt"], align="left",
            font=dict(family=_MONO, color=TERM["amber"], size=11),
            line_color=TERM["border"], height=26,
        ),
        cells=dict(
            values=columns,
            fill_color=colcolors or TERM["panel"], align="left",
            font=dict(family=_MONO, color=TERM["text"], size=11),
            line_color=TERM["border"], height=22,
        ),
    )])
    fig.update_layout(title=title, margin=dict(l=6, r=6, t=34, b=6))
    return fig


# --------------------------------------------------------------------------- #
# DATA TRUTH PANEL — the dashboard telling you when IT is wrong.
# --------------------------------------------------------------------------- #
def data_truth_panel(bundle: dict[str, Any]) -> Optional[go.Figure]:
    """Every canonical artifact the dashboard depends on, with its content-age
    and freshness status. The single most important panel: it makes staleness a
    first-class, visible fact instead of a silent lie in some other chart."""
    from src.dashboard import freshness as F
    from src.dashboard.registry import DEPENDENCY_SOURCES

    # Curate the artifacts that actually matter for the live picture.
    watch = [
        ("Prices (equity)", "data/canonical/prices/equity_prices_daily.parquet"),
        ("Scores", "data/processed/scores.parquet"),
        ("Portfolio weights", "data/processed/portfolio_weights.parquet"),
        ("Paper-fund NAV", "data/pnl/nav_history.parquet"),
        ("Market state / regime", "data/processed/market_state.parquet"),
        ("Macro (cleaned)", "data/macro/cleaned/macro_cleaned.parquet"),
        ("Company sentiment", "data/processed/sentiment/company_sentiment_daily.parquet"),
        ("Bulk deals", "data/processed/alternative/bulk_deals_nse_all.parquet"),
        ("GST / e-way bills", "data/canonical/macro/gst_ewaybill_market_monthly.parquet"),
        ("Cross-asset (fx/comm)", "data/canonical/macro/cross_asset_prices_daily.parquet"),
        ("Options live surface", "data/options/live/options_dashboard_state.json"),
        ("Valuation engines", "data/processed/valuation_engines.parquet"),
        ("Stock roles", "data/processed/stock_roles.parquet"),
        ("Refresh scheduler", "data/runtime/refresh_state.json"),
    ]
    rows = []
    for label, rel in watch:
        p = F.PROJECT_ROOT / rel
        age, status, as_of = F._path_age(p)
        badge = F._BADGE.get(status, "⚪")
        agestr = "—" if age is None else ("today" if age <= 0 else f"{int(age)}d")
        rows.append((f"{badge} {label}", as_of or "missing", agestr, status.upper()))

    # sort worst-first so problems surface at the top
    order = {"MISSING": 0, "STALE": 1, "UNKNOWN": 2, "AGING": 3, "FRESH": 4}
    rows.sort(key=lambda r: order.get(r[3], 9))
    cols = [[r[0] for r in rows], [r[1] for r in rows], [r[2] for r in rows], [r[3] for r in rows]]
    n_stale = sum(1 for r in rows if r[3] in ("STALE", "MISSING"))
    title = f"Data Truth Panel — {len(rows)-n_stale}/{len(rows)} artifacts fresh"
    if n_stale:
        title += f"  ⚠ {n_stale} STALE/MISSING"
    return _table(["Artifact", "Data as of", "Age", "Status"], cols, title=title,
                  widths=[3, 2, 1, 1.2])


# --------------------------------------------------------------------------- #
# MARKET STATE PANEL — the whole tape in one view (replaces 8 single-metric charts)
# --------------------------------------------------------------------------- #
def market_state_panel(bundle: dict[str, Any]) -> Optional[go.Figure]:
    """All the key market-state vitals at a glance: current value + 60-obs
    sparkline for each, in one small-multiples grid. Replaces eight separate
    one-number line charts so the market can be read in a single look."""
    df = _read_parquet("data/processed/market_state.parquet")
    if df.empty:
        b = bundle.get("market_state") if isinstance(bundle, dict) else None
        if isinstance(b, pd.DataFrame) and not b.empty:
            df = b
        else:
            return None
    df = df.copy()
    dc = next((c for c in ("date", "Date", "timestamp") if c in df.columns), None)
    if dc:
        df[dc] = pd.to_datetime(df[dc], errors="coerce")
        df = df.dropna(subset=[dc]).sort_values(dc)
    metrics = [
        ("risk_on_probability", "Risk-On Prob", "%", 100),
        ("stress_score", "Stress", "", 1),
        ("macro_score", "Macro", "", 1),
        ("breadth_pct", "Breadth", "%", 1),
        ("participation_score", "Participation", "", 1),
        ("correlation", "Correlation", "", 1),
        ("health_score", "Health", "", 1),
        ("allowed_exposure", "Allowed Exposure", "%", 100),
    ]
    present = [(c, lbl, u, m) for c, lbl, u, m in metrics if c in df.columns]
    if not present:
        return None
    ncol = 4
    nrow = (len(present) + ncol - 1) // ncol
    titles = []
    for c, lbl, unit, mult in present:
        s = pd.to_numeric(df[c], errors="coerce").dropna()
        val = float(s.iloc[-1]) * mult if len(s) else float("nan")
        titles.append(f"{lbl}: {val:,.1f}{unit}")
    fig = make_subplots(rows=nrow, cols=ncol, subplot_titles=titles,
                        vertical_spacing=0.14, horizontal_spacing=0.06)
    for i, (c, lbl, unit, mult) in enumerate(present):
        r, cc = i // ncol + 1, i % ncol + 1
        s = pd.to_numeric(df[c], errors="coerce").ffill()
        tail = s.tail(60) * mult
        x = df[dc].tail(60) if dc else list(range(len(tail)))
        fig.add_trace(go.Scatter(x=x, y=tail, mode="lines",
                                 line=dict(color=TERM["cyan"], width=1.6),
                                 showlegend=False), row=r, col=cc)
    fig.update_layout(title="Market State Panel — the tape at a glance (60-obs sparklines)",
                      height=180 * nrow, margin=dict(l=6, r=6, t=54, b=6))
    fig.update_xaxes(showticklabels=False)
    return fig


# --------------------------------------------------------------------------- #
# EXPOSURE TRUTH — governor intent vs paper-fund actual vs cash floor.
# --------------------------------------------------------------------------- #
def exposure_truth(bundle: dict[str, Any]) -> Optional[go.Figure]:
    """Replaces the two dead unified_daily exposure charts with the real thing:
    the paper fund's actual daily equity exposure (from the honest NAV) against
    the governor's intended gross and the cash floor — intent vs reality."""
    nav = _read_parquet("data/pnl/nav_history.parquet")
    if nav.empty or "nav_combined" not in nav.columns:
        return None
    nav = nav.copy()
    nav["date"] = pd.to_datetime(nav["date"], errors="coerce")
    nav = nav.dropna(subset=["date"]).sort_values("date")
    if "net_cash_position" not in nav.columns:
        return None
    actual = (nav["nav_combined"] - nav["net_cash_position"]) / nav["nav_combined"]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=nav["date"], y=(actual * 100).clip(0, 100),
                             name="Actual equity exposure", line=dict(color=TERM["cyan"], width=2)))
    # governor intended gross = sum of current target weights (best available proxy)
    try:
        pw = _read_parquet("data/processed/portfolio_weights.parquet")
        wcol = "final_weight" if "final_weight" in pw.columns else ("weight" if "weight" in pw.columns else None)
        if wcol:
            gross = float(pd.to_numeric(pw[wcol], errors="coerce").fillna(0).sum()) * 100
            fig.add_hline(y=gross, line=dict(color=TERM["amber"], dash="dash"),
                          annotation_text=f"Governor intended gross ≈ {gross:.0f}%")
    except Exception:
        pass
    fig.add_hline(y=2.0, line=dict(color=TERM["down"], dash="dot"),
                  annotation_text="Cash floor 2%")
    fig.update_layout(title="Exposure Truth — actual vs intended equity exposure (%)",
                      yaxis_title="% of NAV", margin=dict(l=6, r=6, t=34, b=6))
    return fig


# --------------------------------------------------------------------------- #
# OPTIONS COCKPIT
# --------------------------------------------------------------------------- #
def options_cockpit_table(bundle: dict[str, Any]) -> Optional[go.Figure]:
    df = _flat_suggestions()
    if df.empty:
        return None
    df = df.sort_values(["category", "priority"], ascending=[True, False])
    cat_col = [_CAT_COLOR.get(c, TERM["text"]) for c in df["category"]]
    # per-row fill by category (subtle)
    row_fill = [[
        "rgba(255,77,77,0.10)" if c == "short" else
        "rgba(38,224,127,0.10)" if c == "long" else
        "rgba(56,189,248,0.10)" if c == "hedge" else
        "rgba(255,176,0,0.10)" for c in df["category"]
    ]]
    def fmt(x, p="{:,.0f}"):
        try: return p.format(float(x))
        except Exception: return "—"
    header = ["Cat", "Underlying", "Structure", "Spot", "MaxLoss", "MaxProfit", "Δ", "Vega", "Status", "Days"]
    cols = [
        [c.upper() for c in df["category"]],
        df["underlying"].astype(str).tolist(),
        df["structure"].astype(str).tolist(),
        [fmt(x) for x in df["spot"]],
        [fmt(x) for x in df["max_loss"]],
        ["uncapped" if (x is None or (isinstance(x, float) and np.isinf(x))) else fmt(x) for x in df.get("max_profit", [])],
        [fmt(x, "{:+.2f}") for x in df["net_delta"]],
        [fmt(x, "{:+.1f}") for x in df["net_vega"]],
        df.get("status", pd.Series([""] * len(df))).astype(str).tolist(),
        df.get("days_active", pd.Series([1] * len(df))).astype(str).tolist(),
    ]
    fig = _table(header, cols, title="Options Suggestions — Live Book (v3-driven)",
                 colcolors=row_fill * len(header),
                 widths=[0.7, 1.3, 1.6, 0.9, 1.0, 1.0, 0.6, 0.6, 1.0, 0.5])
    fig.update_layout(height=max(320, 120 + 30 * len(df)))
    return fig


def options_risk_reward(bundle: dict[str, Any]) -> Optional[go.Figure]:
    df = _flat_suggestions()
    if df.empty:
        return None
    df = df.copy()
    df["mp"] = pd.to_numeric(df["max_profit"], errors="coerce")
    cap = df["mp"].replace([np.inf, -np.inf], np.nan).max()
    df["mp"] = df["mp"].replace([np.inf, -np.inf], (cap or 1) * 1.4).fillna((cap or 1) * 1.4)
    fig = go.Figure()
    for cat, g in df.groupby("category"):
        fig.add_trace(go.Scatter(
            x=g["max_loss"], y=g["mp"], mode="markers+text",
            text=g["underlying"].str.replace(".NS", "", regex=False),
            textposition="top center", textfont=dict(size=8, color=TERM["muted"]),
            marker=dict(size=(pd.to_numeric(g["priority"], errors="coerce").fillna(0.5) * 22 + 8),
                        color=_CAT_COLOR.get(cat, TERM["text"]), line=dict(width=1, color=TERM["border"])),
            name=cat.upper(),
        ))
    fig.update_layout(title="Options Risk / Reward Map (size = conviction)",
                      xaxis_title="Max Loss (₹/lot)", yaxis_title="Max Profit (₹/lot)", height=520)
    return fig


def options_category_greeks(bundle: dict[str, Any]) -> Optional[go.Figure]:
    df = _flat_suggestions()
    if df.empty:
        return None
    agg = df.groupby("category").agg(
        n=("underlying", "count"),
        delta=("net_delta", "sum"), vega=("net_vega", "sum"), theta=("net_theta", "sum"),
        risk=("max_loss", "sum"),
    ).reset_index()
    fig = make_subplots(rows=1, cols=2, column_widths=[0.42, 0.58],
                        specs=[[{"type": "domain"}, {"type": "xy"}]],
                        subplot_titles=("Suggestions by Type", "Net Greeks & Premium-at-Risk by Type"))
    fig.add_trace(go.Pie(labels=[c.upper() for c in agg["category"]], values=agg["n"], hole=0.55,
                         marker=dict(colors=[_CAT_COLOR.get(c, TERM["text"]) for c in agg["category"]]),
                         textinfo="label+value", textfont=dict(family=_MONO, size=10)), row=1, col=1)
    for metric, color in [("delta", TERM["cyan"]), ("vega", TERM["amber"]), ("theta", TERM["down"])]:
        fig.add_trace(go.Bar(x=agg["category"].str.upper(), y=agg[metric], name=metric.upper(),
                             marker_color=color), row=1, col=2)
    fig.update_layout(title="Options Book Composition & Aggregate Greeks", barmode="group", showlegend=True, height=500)
    return fig


def options_persistence(bundle: dict[str, Any]) -> Optional[go.Figure]:
    h = _read_parquet("data/options/suggestions/suggestion_history.parquet")
    if h.empty or "underlying" not in h.columns:
        return None
    h = h.copy()
    h["date"] = pd.to_datetime(h["date"], errors="coerce")
    n_days = h["date"].nunique(dropna=True)
    persist = (h.groupby(["underlying", "category"])["date"].nunique()
               .reset_index(name="days").sort_values("days", ascending=True).tail(15))
    if persist.empty:
        return None
    persist["label"] = persist["underlying"].str.replace(".NS", "", regex=False) + " · " + persist["category"].str.upper()

    # With only a few days of accumulated history, every name is necessarily
    # "flagged for 1 day" — the bar chart would show 15 identical-length bars
    # differentiated only by category color, which reads as broken rather than
    # "tracking just started". Below a 5-day floor, show today's new-vs-total
    # split instead — still honest, and actually informative at this stage.
    if n_days < 5:
        latest_date = h["date"].max()
        today = h[h["date"] == latest_date]
        by_cat = today.groupby("category").size().reset_index(name="count")
        fig = go.Figure(go.Bar(
            x=by_cat["count"], y=by_cat["category"].str.upper(), orientation="h",
            marker_color=[_CAT_COLOR.get(c, TERM["text"]) for c in by_cat["category"]],
            text=by_cat["count"], textposition="outside",
        ))
        fig.update_layout(
            title=(f"Persistent Convictions — tracking started {h['date'].min():%d %b %Y} "
                   f"({n_days} day{'s' if n_days != 1 else ''} so far, too early for a meaningful streak view); "
                   f"showing today's ({latest_date:%d %b}) suggestion mix instead"),
            xaxis_title="suggestions today",
        )
        return fig

    fig = go.Figure(go.Bar(
        x=persist["days"], y=persist["label"], orientation="h",
        marker_color=[_CAT_COLOR.get(c, TERM["text"]) for c in persist["category"]],
        text=persist["days"], textposition="outside",
    ))
    fig.update_layout(title="Persistent Convictions — days a name has been flagged (last 20d)",
                      xaxis_title="Trading days flagged")
    return fig


# --------------------------------------------------------------------------- #
# MARKET MOVERS / WATCHLIST + SECTOR VIEWS
# --------------------------------------------------------------------------- #
def _scores() -> pd.DataFrame:
    df = _read_parquet("data/processed/scores.parquet")
    if df.empty or "ticker" not in df.columns:
        return pd.DataFrame()
    df = df.copy()
    raw = pd.to_numeric(df.get("northstar_score", df.get("final_score")), errors="coerce")
    df = df.assign(raw=raw).dropna(subset=["raw"])
    # Cross-sectional standardize -> real spread of positive (strong) and
    # negative (weak) scores. The raw score is often all-positive, which made
    # every name render green; z-scoring restores red/green contrast.
    mu, sd = df["raw"].mean(), df["raw"].std(ddof=0)
    df["z"] = (df["raw"] - mu) / sd if sd and sd > 1e-9 else 0.0
    df["sector"] = df.get("sector", df.get("Industry", "Unknown")).fillna("Unknown")
    return df


def market_movers_table(bundle: dict[str, Any]) -> Optional[go.Figure]:
    df = _scores()
    if df.empty:
        return None
    df = df.sort_values("z", ascending=False)
    top = df.head(12).assign(band="▲ STRONG")
    bot = df.tail(12).sort_values("z").assign(band="▼ WEAK")
    show = pd.concat([top, bot])
    zc = pd.to_numeric(show["z"], errors="coerce")
    zmin, zmax = zc.min(), zc.max()
    def cell_color(v):
        if v >= 0: return "rgba(38,224,127,0.14)"
        return "rgba(255,77,77,0.14)"
    row_fill = [[cell_color(v) for v in zc]]
    header = ["", "Ticker", "Company", "Sector", "v3 Score", "Quintile", "Sug.Wt"]
    cols = [
        show["band"].tolist(),
        show["ticker"].str.replace(".NS", "", regex=False).tolist(),
        show.get("Company Name", pd.Series([""] * len(show))).astype(str).str.slice(0, 22).tolist(),
        show["sector"].astype(str).str.slice(0, 18).tolist(),
        [f"{v:+.2f}" for v in zc],
        show.get("quintile", pd.Series([""] * len(show))).astype(str).tolist(),
        [f"{100*float(v):.1f}%" if pd.notna(v) else "—" for v in pd.to_numeric(show.get("suggested_weight", pd.Series([np.nan]*len(show))), errors="coerce")],
    ]
    fig = _table(header, cols, title="Market Movers — Strongest & Weakest by v3 Score",
                 colcolors=row_fill * len(header), widths=[0.8, 0.9, 1.8, 1.3, 0.8, 0.7, 0.7])
    fig.update_layout(height=560)
    return fig


def sector_strength(bundle: dict[str, Any]) -> Optional[go.Figure]:
    df = _scores()
    if df.empty:
        return None
    sec = df.groupby("sector").agg(mean_z=("z", "mean"), n=("ticker", "count")).reset_index()
    sec = sec[sec["n"] >= 2].sort_values("mean_z")
    if sec.empty:
        return None
    colors = [TERM["up"] if v >= 0 else TERM["down"] for v in sec["mean_z"]]
    fig = go.Figure(go.Bar(
        x=sec["mean_z"], y=sec["sector"], orientation="h", marker_color=colors,
        text=[f"{v:+.2f} (n={n})" for v, n in zip(sec["mean_z"], sec["n"])],
        textposition="outside", textfont=dict(size=9),
    ))
    fig.update_layout(title="Sector Strength — mean v3 score by sector", xaxis_title="Mean score (z)", height=460)
    return fig


def universe_treemap(bundle: dict[str, Any]) -> Optional[go.Figure]:
    """NEW view: treemap of the scored universe by sector, sized by weight,
    coloured by score — an all-in-one map of where strength/weakness sits."""
    df = _scores()
    if df.empty:
        return None
    df = df.copy()
    df["w"] = pd.to_numeric(df.get("suggested_weight"), errors="coerce").fillna(0.0)
    if df["w"].sum() <= 0:
        df["w"] = 1.0  # equal-size fallback if weights absent
    df["name"] = df["ticker"].str.replace(".NS", "", regex=False)
    fig = px.treemap(
        df, path=[px.Constant("NIFTY 500"), "sector", "name"], values="w",
        color="z", color_continuous_scale=[[0, TERM["down"]], [0.5, "#2a2f38"], [1, TERM["up"]]],
        color_continuous_midpoint=0,
    )
    fig.update_traces(marker=dict(line=dict(color=TERM["bg"], width=1)),
                      textfont=dict(family=_MONO, size=10))
    fig.update_layout(title="Universe Map — sector × name, sized by weight, coloured by v3 score",
                      margin=dict(l=6, r=6, t=34, b=6))
    return fig


# --------------------------------------------------------------------------- #
# CONSOLIDATED MARKET COCKPIT (all-in-one)
# --------------------------------------------------------------------------- #
def market_cockpit(bundle: dict[str, Any]) -> Optional[go.Figure]:
    """One figure = the big picture: score distribution, quintile counts,
    top sectors, and a regime/health gauge."""
    df = _scores()
    if df.empty:
        return None
    fig = make_subplots(
        rows=2, cols=2,
        specs=[[{"type": "xy"}, {"type": "xy"}], [{"type": "xy"}, {"type": "domain"}]],
        subplot_titles=("Score Distribution (universe)", "Quintile Score Gradient",
                        "Top / Bottom Sectors", "Breadth (scores > 0)"),
        vertical_spacing=0.16, horizontal_spacing=0.12,
    )
    # score histogram
    fig.add_trace(go.Histogram(x=df["z"], nbinsx=40, marker_color=TERM["cyan"], showlegend=False), row=1, col=1)
    # quintile score gradient — counts are trivially 100/quintile by
    # construction, so show the mean z each quintile actually carries instead
    try:
        q = pd.qcut(df["z"].rank(method="first"), 5, labels=["Q1 weak", "Q2", "Q3", "Q4", "Q5 strong"])
        qm = df.groupby(q, observed=True)["z"].mean()
        qcolors = [TERM["down"], "#c0774d", TERM["flat"], "#5fa878", TERM["up"]]
        fig.add_trace(go.Bar(x=qm.index.astype(str), y=qm.values, marker_color=qcolors, showlegend=False,
                             text=[f"{v:+.2f}" for v in qm.values], textposition="outside",
                             textfont=dict(size=9)), row=1, col=2)
    except Exception:
        pass
    # sector strength (top+bottom 5)
    sec = df.groupby("sector")["z"].mean().sort_values()
    sec = pd.concat([sec.head(5), sec.tail(5)])
    fig.add_trace(go.Bar(x=sec.values, y=sec.index, orientation="h",
                         marker_color=[TERM["up"] if v >= 0 else TERM["down"] for v in sec.values],
                         showlegend=False), row=2, col=1)
    # breadth gauge
    breadth = float((df["z"] > 0).mean() * 100)
    fig.add_trace(go.Indicator(
        mode="gauge+number", value=breadth, number=dict(suffix="%", font=dict(family=_MONO)),
        gauge=dict(axis=dict(range=[0, 100]), bar=dict(color=TERM["amber"]),
                   steps=[dict(range=[0, 40], color="rgba(255,77,77,0.35)"),
                          dict(range=[40, 60], color="rgba(139,149,165,0.25)"),
                          dict(range=[60, 100], color="rgba(38,224,127,0.35)")]),
    ), row=2, col=2)
    fig.update_layout(title="Market Cockpit — universe breadth, distribution, quintiles, sectors", showlegend=False)
    return fig


# --------------------------------------------------------------------------- #
# ALTERNATIVE DATA VIEWS
# --------------------------------------------------------------------------- #
# --------------------------------------------------------------------------- #
# OVERVIEW — rich, all-in-one executive panels
# --------------------------------------------------------------------------- #
def _latest_market_state() -> pd.Series:
    df = _read_parquet("data/processed/market_state.parquet")
    if df.empty:
        return pd.Series(dtype=float)
    sc = "timestamp" if "timestamp" in df.columns else ("date" if "date" in df.columns else None)
    return (df.sort_values(sc) if sc else df).iloc[-1]


def overview_market_pulse(bundle: dict[str, Any]) -> Optional[go.Figure]:
    """A gauge cluster reading the current market-state row: breadth, risk-on,
    participation, health, stress, macro momentum — the market's vitals."""
    row = _latest_market_state()
    if row.empty:
        return None

    def pct(v, scale=True):
        v = pd.to_numeric(v, errors="coerce")
        if pd.isna(v):
            return None
        v = float(v)
        return v * 100 if (scale and abs(v) <= 1.0) else v

    gauges = [
        ("Breadth", pct(row.get("breadth_pct")), [40, 60]),
        ("Risk-On Prob", pct(row.get("risk_on_probability")), [40, 60]),
        ("Participation", pct(row.get("participation_score")), [40, 60]),
        ("Health", pct(row.get("health_score")), [40, 70]),
        ("Opportunity", pct(row.get("opportunity_density")), [30, 60]),
        ("Coherence", pct(row.get("coherence_score")), [40, 70]),
    ]
    gauges = [g for g in gauges if g[1] is not None]
    if not gauges:
        return None
    cols = 3
    rows = (len(gauges) + cols - 1) // cols
    fig = make_subplots(rows=rows, cols=cols, specs=[[{"type": "domain"}] * cols for _ in range(rows)],
                        subplot_titles=[g[0] for g in gauges], vertical_spacing=0.18)
    for i, (name, val, zones) in enumerate(gauges):
        r, c = i // cols + 1, i % cols + 1
        color = TERM["down"] if val < zones[0] else TERM["amber"] if val < zones[1] else TERM["up"]
        fig.add_trace(go.Indicator(
            mode="gauge+number", value=val, number=dict(suffix="%", font=dict(family=_MONO, size=16)),
            gauge=dict(axis=dict(range=[0, 100], tickfont=dict(size=8)), bar=dict(color=color, thickness=0.72),
                       bgcolor=TERM["panel_alt"], borderwidth=0,
                       steps=[dict(range=[0, zones[0]], color="rgba(255,77,77,0.15)"),
                              dict(range=[zones[0], zones[1]], color="rgba(139,149,165,0.12)"),
                              dict(range=[zones[1], 100], color="rgba(38,224,127,0.15)")]),
        ), row=r, col=c)
    regime = str(row.get("regime_name", row.get("regime", "—")))
    fig.update_layout(title=f"Market Pulse — vitals of the current tape · regime: {regime}",
                      margin=dict(l=10, r=10, t=52, b=10))
    return fig


def overview_exec_cockpit(bundle: dict[str, Any]) -> Optional[go.Figure]:
    """One figure = capital + allocation + regime posture: NAV trend, drawdown,
    the governor's equity/options/cash split, and the sentiment/exposure read."""
    nav = _read_parquet("data/pnl/nav_history.parquet")
    row = _latest_market_state()
    if nav.empty and row.empty:
        return None
    fig = make_subplots(
        rows=2, cols=2, row_heights=[0.58, 0.42], column_widths=[0.62, 0.38],
        specs=[[{"type": "xy"}, {"type": "domain"}], [{"type": "xy"}, {"type": "xy"}]],
        subplot_titles=("NAV & Drawdown", "Capital Allocation", "Exposure Policy", "Sentiment Read"),
        vertical_spacing=0.16, horizontal_spacing=0.1,
    )
    # NAV + drawdown
    if not nav.empty:
        dcol = "date" if "date" in nav.columns else nav.columns[0]
        ncol = next((c for c in ["nav_combined", "nav", "total_nav"] if c in nav.columns), None)
        if ncol:
            n = nav[[dcol, ncol]].dropna().copy()
            n[dcol] = pd.to_datetime(n[dcol], errors="coerce")
            fig.add_trace(go.Scatter(x=n[dcol], y=n[ncol], mode="lines", line=dict(color=TERM["amber"], width=1.6),
                                     name="NAV", fill="tozeroy", fillcolor="rgba(255,176,0,0.08)"), row=1, col=1)
            hwm = n[ncol].cummax()
            dd = (n[ncol] / hwm - 1) * 100
            fig.add_trace(go.Scatter(x=n[dcol], y=dd, mode="lines", line=dict(color=TERM["down"], width=1),
                                     name="Drawdown %", yaxis="y2"), row=1, col=1)
    # allocation donut
    alloc_row = row
    eq = float(pd.to_numeric(alloc_row.get("allowed_exposure"), errors="coerce") or 0.0)
    eq = eq * 100 if eq <= 1 else eq
    alloc = {"Equity": eq, "Options": max(0.0, 15.0), "Cash": max(0.0, 100.0 - eq - 15.0)}
    fig.add_trace(go.Pie(labels=list(alloc), values=list(alloc.values()), hole=0.58,
                         marker=dict(colors=[TERM["cyan"], TERM["amber"], "#3a4150"]),
                         textinfo="label+percent", textfont=dict(family=_MONO, size=9)), row=1, col=2)
    # exposure policy bars
    pol = [("Allowed", eq), ("Multiplier", float(pd.to_numeric(row.get("exposure_multiplier"), errors="coerce") or 1.0) * 100),
           ("Stress", float(pd.to_numeric(row.get("stress_score"), errors="coerce") or 0.0) * 100)]
    fig.add_trace(go.Bar(x=[p[0] for p in pol], y=[p[1] for p in pol],
                         marker_color=[TERM["cyan"], TERM["amber"], TERM["down"]], showlegend=False), row=2, col=1)
    # sentiment read
    sent = [("Polarity", float(pd.to_numeric(row.get("sentiment_polarity"), errors="coerce") or 0.0)),
            ("Conviction", float(pd.to_numeric(row.get("sentiment_conviction"), errors="coerce") or 0.0)),
            ("Uncertainty", float(pd.to_numeric(row.get("sentiment_uncertainty"), errors="coerce") or 0.0))]
    fig.add_trace(go.Bar(x=[s[1] for s in sent], y=[s[0] for s in sent], orientation="h",
                         marker_color=[TERM["up"] if s[1] >= 0 else TERM["down"] for s in sent],
                         showlegend=False), row=2, col=2)
    fig.update_layout(title="Executive Cockpit — capital, allocation, exposure posture & sentiment",
                      showlegend=False, yaxis2=dict(overlaying="y", side="right", showgrid=False))
    return fig


def alt_bulk_deal_flow(bundle: dict[str, Any]) -> Optional[go.Figure]:
    df = _read_parquet("data/processed/alternative/bulk_deals_nse_all.parquet")
    if df.empty or "deal_type" not in df.columns:
        return None
    df = df.copy()
    df["date"] = pd.to_datetime(df.get("date"), errors="coerce")
    df["val"] = pd.to_numeric(df.get("quantity"), errors="coerce") * pd.to_numeric(df.get("price"), errors="coerce")
    df = df.dropna(subset=["date", "val"])
    cutoff = df["date"].max() - pd.Timedelta(days=60)
    df = df[df["date"] >= cutoff]
    if df.empty:
        return None
    df["signed"] = np.where(df["deal_type"].astype(str).str.upper().str.startswith("B"), df["val"], -df["val"])
    daily = df.groupby(df["date"].dt.date)["signed"].sum().reset_index()
    daily.columns = ["date", "net"]
    # top names by net over window
    names = (df.groupby(df.get("nse_ticker", df.get("symbol")).astype(str))["signed"].sum()
             .sort_values().reset_index())
    names.columns = ["name", "net"]
    names = pd.concat([names.head(6), names.tail(6)])
    fig = make_subplots(rows=1, cols=2, column_widths=[0.6, 0.4],
                        subplot_titles=("Net Bulk-Deal Flow / day (₹, last 60d)", "Top Net Buy / Sell Names"))
    fig.add_trace(go.Bar(x=daily["date"], y=daily["net"],
                         marker_color=[TERM["up"] if v >= 0 else TERM["down"] for v in daily["net"]],
                         showlegend=False), row=1, col=1)
    fig.add_trace(go.Bar(x=names["net"], y=names["name"].str.replace(".NS", "", regex=False), orientation="h",
                         marker_color=[TERM["up"] if v >= 0 else TERM["down"] for v in names["net"]],
                         showlegend=False), row=1, col=2)
    fig.update_layout(title="Smart-Money Bulk-Deal Flow (institutional buy/sell pressure)")
    return fig


def alt_promoter_pledge(bundle: dict[str, Any]) -> Optional[go.Figure]:
    """Highest current promoter-pledge names, with severity bands (the
    standard 25/50/75% governance-risk thresholds), trend vs the prior
    disclosure (rising pledge is the real warning sign, not just the level),
    and a flag for names we actually hold — so this reads as "here's what to
    watch in MY book" rather than a generic top-15 of the whole market."""
    df = _read_csv("data/processed/alternative/promoter_pledge_all.csv")
    if df.empty or "pledge_pct" not in df.columns:
        return None
    df = df.copy()
    df["date"] = pd.to_datetime(df.get("date"), errors="coerce")
    df["pledge_pct"] = pd.to_numeric(df["pledge_pct"], errors="coerce")
    df = df.dropna(subset=["pledge_pct"])
    key_col = "nse_ticker" if "nse_ticker" in df.columns else "company_name"
    df = df.sort_values("date")
    grouped = df.groupby(df[key_col].astype(str))
    latest = grouped.tail(1).copy()
    prior = grouped.nth(-2) if grouped.ngroups else pd.DataFrame()
    prior_map = prior.set_index(key_col)["pledge_pct"].to_dict() if not prior.empty else {}
    latest = latest[latest["pledge_pct"] > 0].nlargest(15, "pledge_pct")
    if latest.empty:
        return None
    name_raw = latest[key_col].astype(str)
    name = name_raw.str.replace(".NS", "", regex=False)
    latest["prior_pct"] = name_raw.map(prior_map)
    latest["delta"] = latest["pledge_pct"] - latest["prior_pct"]
    held = set(_weights()["name"]) if not _weights().empty else set()
    trend_arrow = ["▲" if d > 0.5 else "▼" if d < -0.5 else "■" for d in latest["delta"].fillna(0)]
    labels = [f"{'★ ' if n in held else ''}{n}" for n in name]

    def sev(v: float) -> str:
        return TERM["amber"] if v < 25 else "#c0774d" if v < 50 else TERM["down"]

    fig = go.Figure(go.Bar(
        x=latest["pledge_pct"], y=labels, orientation="h",
        marker=dict(color=[sev(v) for v in latest["pledge_pct"]]),
        text=[f"{v:.1f}% {a}" + (f" (was {p:.1f}%)" if pd.notna(p) else "")
              for v, a, p in zip(latest["pledge_pct"], trend_arrow, latest["prior_pct"])],
        textposition="outside", textfont=dict(size=9),
        hovertemplate="%{y}: %{x:.1f}%%<extra></extra>",
    ))
    for x in (25, 50, 75):
        fig.add_vline(x=x, line=dict(color=TERM["muted"], width=1, dash="dot"))
    fig.update_layout(
        title="Promoter Pledge Risk — highest pledged % (★ = held in the fund; ▲/▼ = trend vs prior disclosure)",
        xaxis_title="Promoter shares pledged (%)", height=max(360, 40 + 28 * len(latest)),
    )
    return fig


def alt_gst_trend(bundle: dict[str, Any]) -> Optional[go.Figure]:
    df = _read_parquet("data/canonical/macro/gst_ewaybill_market_monthly.parquet")
    if df.empty:
        return None
    df = df.copy()
    df["date"] = pd.to_datetime(df.get("date"), errors="coerce")
    agg = df.groupby(df["date"].dt.to_period("M")).agg(
        total=("total", "sum"), bills=("total_eway_bills", "sum")).reset_index()
    agg["date"] = agg["date"].dt.to_timestamp()
    agg = agg.dropna(subset=["date"]).tail(36)
    if agg.empty:
        return None
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(x=agg["date"], y=agg["total"], name="GST revenue", marker_color=TERM["cyan"], opacity=0.7),
                  secondary_y=False)
    fig.add_trace(go.Scatter(x=agg["date"], y=agg["bills"], name="E-way bills", mode="lines+markers",
                             line=dict(color=TERM["amber"], width=2)), secondary_y=True)
    # GSTN's own public e-way bill dashboard — the sole source this scraper
    # reads — has never published a month past this one; it is not a stale
    # local pipeline, the government source itself lags ~5 months behind
    # "today". Say that explicitly so the chart doesn't read as broken.
    last_month = agg["date"].max()
    fig.update_layout(
        title=f"Macro Activity — GST revenue & e-way bills (monthly, as of {last_month:%b %Y} — "
              f"latest published by the GSTN dashboard, which lags real time by design)"
    )
    return fig


# --------------------------------------------------------------------------- #
# WHAT CHANGED — anomaly & delta surfacing (Bloomberg: show what moved, not
# what is)
# --------------------------------------------------------------------------- #
def whats_changed(bundle: dict[str, Any]) -> Optional[go.Figure]:
    """One feed of everything that *changed* recently across the system:
    sentiment surprises, fresh bulk-deal prints, credit-rating actions, and
    newly opened options suggestions — newest first."""
    events: list[tuple[pd.Timestamp, str, str, str, str]] = []  # (ts, type, name, event, color)

    # sentiment surprises (last available day, biggest |surprise| first)
    sent = _read_parquet("data/processed/sentiment/ticker_sentiment_daily.parquet")
    if not sent.empty and "sentiment_surprise" in sent.columns:
        sent["date"] = pd.to_datetime(sent["date"], errors="coerce")
        last = sent["date"].max()
        day = sent[sent["date"] >= last - pd.Timedelta(days=2)].copy()
        day["surp"] = pd.to_numeric(day["sentiment_surprise"], errors="coerce")
        day = day.dropna(subset=["surp"]).nlargest(6, columns="surp", keep="first") if not day.empty else day
        for _, r in day.iterrows():
            col = TERM["up"] if r["surp"] > 0 else TERM["down"]
            events.append((r["date"], "SENTIMENT", str(r["ticker"]).replace(".NS", ""),
                           f"news surprise {r['surp']:+.2f} on {int(r.get('news_volume', 0))} stories", col))

    # fresh bulk deals (last 5 days, largest by value)
    deals = _read_parquet("data/processed/alternative/bulk_deals_nse_all.parquet")
    if not deals.empty:
        deals["date"] = pd.to_datetime(deals["date"], errors="coerce")
        cutoff = deals["date"].max() - pd.Timedelta(days=5)
        d = deals[deals["date"] >= cutoff].copy()
        d["value"] = pd.to_numeric(d["quantity"], errors="coerce") * pd.to_numeric(d["price"], errors="coerce")
        d = d.dropna(subset=["value"]).nlargest(8, columns="value")
        for _, r in d.iterrows():
            side = str(r.get("deal_type", "")).upper()
            col = TERM["up"] if side.startswith("B") else TERM["down"]
            events.append((r["date"], "BULK DEAL", str(r.get("nse_ticker", r.get("symbol", ""))).replace(".NS", ""),
                           f"{side} ₹{r['value']/1e7:,.1f} Cr · {str(r.get('client_name',''))[:28]}", col))

    # credit-rating actions (last 30 days)
    ratings = _read_parquet("data/processed/alternative/credit_ratings_nse_all.parquet")
    if not ratings.empty:
        ratings["date"] = pd.to_datetime(ratings["date"], errors="coerce")
        cutoff = ratings["date"].max() - pd.Timedelta(days=30)
        rr = ratings[ratings["date"] >= cutoff].tail(8)
        for _, r in rr.iterrows():
            action = str(r.get("action_type", "")).lower()
            col = TERM["down"] if ("down" in action or "negative" in action) else \
                  TERM["up"] if ("up" in action or "positive" in action) else TERM["cyan"]
            events.append((r["date"], "RATING", str(r.get("nse_ticker", "")).replace(".NS", ""),
                           f"{r.get('agency','')}: {r.get('action_type','')} → {r.get('new_rating','')}", col))

    # newly opened options suggestions (days_active == 1 on latest date)
    hist = _read_parquet("data/options/suggestions/suggestion_history.parquet")
    if not hist.empty and "days_active" in hist.columns:
        hist["date"] = pd.to_datetime(hist["date"], errors="coerce")
        last = hist["date"].max()
        new = hist[(hist["date"] == last) & (pd.to_numeric(hist["days_active"], errors="coerce") <= 1)]
        for _, r in new.head(6).iterrows():
            cat = str(r.get("category", "")).lower()
            events.append((r["date"], "OPTIONS", str(r.get("underlying", "")).replace(".NS", ""),
                           f"new {cat.upper()}: {str(r.get('structure',''))[:34]}",
                           _CAT_COLOR.get(cat, TERM["amber"])))

    if not events:
        return None
    events.sort(key=lambda e: (pd.Timestamp.min if pd.isna(e[0]) else e[0]), reverse=True)
    events = events[:22]
    dates = [("—" if pd.isna(d) else f"{d:%d-%b}") for d, *_ in events]
    types = [t for _, t, *_ in events]
    names = [n for _, _, n, *_ in events]
    texts = [e for _, _, _, e, _ in events]
    colors = [[c for *_, c in events]]
    fig = go.Figure(go.Table(
        columnwidth=[0.5, 0.8, 0.9, 3.0],
        header=dict(values=["<b>When</b>", "<b>Type</b>", "<b>Name</b>", "<b>What changed</b>"],
                    fill_color=TERM["panel_alt"], align="left",
                    font=dict(family=_MONO, color=TERM["amber"], size=11),
                    line_color=TERM["border"], height=26),
        cells=dict(values=[dates, types, names, texts],
                   fill_color=TERM["panel"], align="left",
                   font=dict(family=_MONO, size=11,
                             color=[TERM["muted"], colors[0], TERM["text"], TERM["text"]]),
                   line_color=TERM["border"], height=22),
    ))
    fig.update_layout(title="What Changed — surprises, prints, rating actions, new positions",
                      margin=dict(l=6, r=6, t=34, b=6),
                      height=max(300, 110 + 24 * len(events)))
    return fig


# --------------------------------------------------------------------------- #
# PORTFOLIO COCKPIT & BLOTTER
# --------------------------------------------------------------------------- #
def _weights() -> pd.DataFrame:
    df = _read_parquet("data/processed/portfolio_weights.parquet")
    if df.empty or "ticker" not in df.columns:
        return pd.DataFrame()
    df = df.copy()
    df["w"] = pd.to_numeric(df.get("final_weight", df.get("weight")), errors="coerce").fillna(0.0)
    df["name"] = df["ticker"].astype(str).str.replace(".NS", "", regex=False)
    df["sector"] = df.get("Industry", pd.Series(["Unknown"] * len(df))).fillna("Unknown")
    df["role"] = df.get("position_role", pd.Series(["—"] * len(df))).fillna("—")
    return df[df["w"] > 0]


def _nav() -> pd.DataFrame:
    df = _read_parquet("data/pnl/nav_history.parquet")
    if df.empty or "date" not in df.columns:
        return pd.DataFrame()
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    return df.dropna(subset=["date"]).sort_values("date")


def _positions() -> pd.DataFrame:
    """The real paper-fund position book (mark-to-market), falling back to
    target weights only if the fund hasn't been run yet."""
    df = _read_parquet("data/pnl/current_positions.parquet")
    if df.empty or "ticker" not in df.columns:
        return pd.DataFrame()
    df = df.copy()
    df["name"] = df["ticker"].astype(str).str.replace(".NS", "", regex=False)
    df["sector"] = df.get("sector", pd.Series(["Unknown"] * len(df))).fillna("Unknown")
    return df


def _fund_summary() -> dict:
    p = PROJECT_ROOT / "data/pnl/paper_fund_summary.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}


def portfolio_cockpit(bundle: dict[str, Any]) -> Optional[go.Figure]:
    """All-in-one portfolio view: equity curve, sector allocation, top holdings
    and the core/satellite split — the whole book on one screen."""
    w = _weights()
    nav = _nav()
    if w.empty and nav.empty:
        return None
    fig = make_subplots(
        rows=2, cols=2,
        specs=[[{"type": "xy", "colspan": 2}, None], [{"type": "xy"}, {"type": "domain"}]],
        row_heights=[0.42, 0.58], vertical_spacing=0.14, horizontal_spacing=0.12,
        subplot_titles=("Equity Curve (NAV per unit)", "Sector Allocation (% of book)", "Core vs Satellite"),
    )
    # equity curve + high-water mark
    if not nav.empty:
        ycol = "nav_per_unit" if "nav_per_unit" in nav.columns else "nav_combined"
        tail = nav.tail(400).copy()
        fig.add_trace(go.Scatter(x=tail["date"], y=tail[ycol], mode="lines",
                                 line=dict(color=TERM["amber"], width=1.8), name="NAV"), row=1, col=1)
        # High-water mark recomputed on the plotted series — the stored column
        # tracks combined NAV, which is on a different scale than NAV/unit.
        hwm = pd.to_numeric(tail[ycol], errors="coerce").cummax()
        fig.add_trace(go.Scatter(x=tail["date"], y=hwm, mode="lines",
                                 line=dict(color=TERM["muted"], width=1, dash="dot"), name="High-water"), row=1, col=1)
    # sector allocation
    if not w.empty:
        sec = w.groupby("sector")["w"].sum().sort_values(ascending=True).tail(12)
        sec_pct = 100 * sec / w["w"].sum()
        fig.add_trace(go.Bar(x=sec_pct.values, y=sec.index, orientation="h",
                             marker_color=TERM["cyan"], showlegend=False,
                             text=[f"{v:.1f}%" for v in sec_pct.values], textposition="outside",
                             textfont=dict(size=9)), row=2, col=1)
        # core / satellite donut
        role = w.groupby("role")["w"].sum()
        fig.add_trace(go.Pie(labels=role.index.tolist(), values=role.values, hole=0.55,
                             marker=dict(colors=[TERM["up"], TERM["cyan"], TERM["amber"], TERM["muted"]]),
                             textinfo="label+percent"), row=2, col=2)
    fig.update_layout(title="Portfolio Cockpit — equity curve, sector allocation & role mix", showlegend=False, height=640)
    return fig


def portfolio_blotter(bundle: dict[str, Any]) -> Optional[go.Figure]:
    """The holdings blotter: every position with weight, role, conviction and
    valuation stance — the ledger behind the cockpit."""
    w = _weights()
    if w.empty:
        return None
    w = w.sort_values("w", ascending=False)
    total = w["w"].sum()
    def fmt(x, p="{:.2f}"):
        try: return p.format(float(x))
        except Exception: return "—"
    role_fill = [[
        "rgba(38,224,127,0.12)" if r == "Core" else "rgba(56,189,248,0.10)" for r in w["role"]
    ]]
    header = ["Ticker", "Company", "Sector", "Wt%", "Role", "Conviction", "MoS%", "Signal"]
    cols = [
        w["name"].tolist(),
        w.get("Company Name", pd.Series([""] * len(w))).astype(str).str.slice(0, 22).tolist(),
        w["sector"].astype(str).str.slice(0, 18).tolist(),
        [fmt(100 * x / total if total else 0) for x in w["w"]],
        w["role"].astype(str).tolist(),
        # NOTE: DataFrame.get(col, default) returns the bare `default` scalar
        # (not a Series) when the column is missing, which crashes the list
        # comprehension below with "'float' object is not iterable" — always
        # fall back to a same-length Series.
        [fmt(x, "{:.2f}") for x in pd.to_numeric(
            w["selection_score"] if "selection_score" in w.columns else pd.Series(np.nan, index=w.index),
            errors="coerce")],
        [fmt(x, "{:+.1f}") for x in pd.to_numeric(
            w["margin_of_safety_pct"] if "margin_of_safety_pct" in w.columns else pd.Series(np.nan, index=w.index),
            errors="coerce")],
        [fmt(x, "{:.2f}") if pd.notna(pd.to_numeric(x, errors="coerce")) else str(x)[:14]
         for x in (w["valuation_signal"] if "valuation_signal" in w.columns else pd.Series([""] * len(w), index=w.index))],
    ]
    fig = _table(header, cols, title="Holdings Blotter — current equity book",
                 colcolors=role_fill * len(header),
                 widths=[0.8, 1.7, 1.4, 0.6, 0.8, 0.9, 0.7, 1.0])
    fig.update_layout(height=max(320, 120 + 26 * len(w)))
    return fig


# --------------------------------------------------------------------------- #
# RISK COCKPIT — "where are the risks actually?"
# --------------------------------------------------------------------------- #
def risk_cockpit(bundle: dict[str, Any]) -> Optional[go.Figure]:
    """Built to answer one question: where is the risk? Four lenses —
    single-name concentration, sector concentration, the live drawdown, and net
    options greeks — each flagged red when it crosses a prudent threshold."""
    w = _weights()
    nav = _nav()
    opt = _flat_suggestions()
    if w.empty and nav.empty:
        return None
    fig = make_subplots(
        rows=2, cols=2,
        specs=[[{"type": "xy"}, {"type": "xy"}], [{"type": "xy"}, {"type": "xy"}]],
        vertical_spacing=0.16, horizontal_spacing=0.12,
        subplot_titles=("Top single-name concentration (% book)", "Sector concentration (% book)",
                        "Drawdown (underwater curve)", "Net options greeks"),
    )
    conc_flag = False
    if not w.empty:
        total = w["w"].sum()
        top = w.sort_values("w", ascending=False).head(10)
        top_pct = 100 * top["w"] / total
        # single-name: flag any name above 8% of the book
        colors = [TERM["down"] if v > 8 else TERM["amber"] if v > 5 else TERM["up"] for v in top_pct]
        conc_flag = bool((top_pct > 8).any())
        fig.add_trace(go.Bar(x=top["name"], y=top_pct.values, marker_color=colors, showlegend=False,
                             hovertemplate="%{x}: %{y:.1f}%<extra></extra>"), row=1, col=1)
        fig.add_hline(y=8, line=dict(color=TERM["down"], width=1, dash="dot"), row=1, col=1)
        # sector concentration: flag any sector above 25%
        sec = (100 * w.groupby("sector")["w"].sum() / total).sort_values(ascending=False).head(10)
        scolors = [TERM["down"] if v > 25 else TERM["amber"] if v > 15 else TERM["cyan"] for v in sec.values]
        fig.add_trace(go.Bar(x=sec.values, y=sec.index, orientation="h", marker_color=scolors, showlegend=False,
                             hovertemplate="%{y}: %{x:.1f}%<extra></extra>"), row=1, col=2)
        fig.add_vline(x=25, line=dict(color=TERM["down"], width=1, dash="dot"), row=1, col=2)
    # drawdown underwater
    if not nav.empty and "drawdown" in nav.columns:
        tail = nav.tail(400)
        dd = pd.to_numeric(tail["drawdown"], errors="coerce") * 100
        fig.add_trace(go.Scatter(x=tail["date"], y=dd, mode="lines", fill="tozeroy",
                                 line=dict(color=TERM["down"], width=1.2), showlegend=False,
                                 hovertemplate="%{x|%d-%b}: %{y:.2f}%<extra></extra>"), row=2, col=1)
    # net options greeks
    if not opt.empty:
        greeks = {
            "Δ delta": pd.to_numeric(opt.get("net_delta"), errors="coerce").sum(),
            "vega": pd.to_numeric(opt.get("net_vega"), errors="coerce").sum(),
            "θ theta": pd.to_numeric(opt.get("net_theta"), errors="coerce").sum(),
        }
        gcolors = [TERM["up"] if v >= 0 else TERM["down"] for v in greeks.values()]
        fig.add_trace(go.Bar(x=list(greeks.keys()), y=list(greeks.values()), marker_color=gcolors,
                             showlegend=False), row=2, col=2)
    else:
        fig.add_annotation(text="no live options book", xref="x4 domain", yref="y4 domain",
                           x=0.5, y=0.5, showarrow=False, font=dict(color=TERM["muted"]))
    hdr = "Risk Cockpit — where the risk sits" + ("  ⚠ CONCENTRATED" if conc_flag else "")
    fig.update_layout(title=hdr, height=640)
    return fig


def risk_hotspots(bundle: dict[str, Any]) -> Optional[go.Figure]:
    """A ranked table of the actual risk hotspots: biggest positions crossed
    with governance stress (promoter pledge) so you see the names to watch."""
    w = _weights()
    if w.empty:
        return None
    total = w["w"].sum()
    pledge = _read_csv("data/processed/alternative/promoter_pledge_all.csv")
    pmap: dict[str, float] = {}
    if not pledge.empty:
        pcol = next((c for c in pledge.columns if "pledge" in c.lower()), None)
        scol = next((c for c in pledge.columns if c.lower() in ("symbol", "ticker", "nsecode", "name")), None)
        if pcol and scol:
            tmp = pledge[[scol, pcol]].copy()
            tmp[scol] = tmp[scol].astype(str).str.replace(".NS", "", regex=False).str.upper()
            tmp[pcol] = pd.to_numeric(tmp[pcol], errors="coerce")
            pmap = tmp.dropna().groupby(scol)[pcol].max().to_dict()
    top = w.sort_values("w", ascending=False).head(15).copy()
    top["wpct"] = 100 * top["w"] / total
    top["pledge"] = top["name"].str.upper().map(pmap)
    def flag(row) -> str:
        f = []
        if row["wpct"] > 8: f.append("SIZE")
        if pd.notna(row["pledge"]) and row["pledge"] > 25: f.append("PLEDGE")
        return " · ".join(f) if f else "—"
    top["flags"] = top.apply(flag, axis=1)
    row_fill = [[
        "rgba(255,77,77,0.14)" if fl != "—" else "rgba(255,255,255,0.02)" for fl in top["flags"]
    ]]
    header = ["Ticker", "Company", "Sector", "Wt%", "Pledge%", "Risk Flag"]
    cols = [
        top["name"].tolist(),
        top.get("Company Name", pd.Series([""] * len(top))).astype(str).str.slice(0, 22).tolist(),
        top["sector"].astype(str).str.slice(0, 18).tolist(),
        [f"{v:.2f}" for v in top["wpct"]],
        ["—" if pd.isna(v) else f"{v:.1f}" for v in top["pledge"]],
        top["flags"].tolist(),
    ]
    fig = _table(header, cols, title="Risk Hotspots — largest positions & governance stress",
                 colcolors=row_fill * len(header), widths=[0.8, 1.7, 1.3, 0.6, 0.7, 1.0])
    fig.update_layout(height=max(300, 120 + 26 * len(top)))
    return fig


# --------------------------------------------------------------------------- #
# PAPER FUND — the ₹100cr one-truth surfaces
# --------------------------------------------------------------------------- #
_STRAT_COLOR = {
    "v3": TERM["amber"], "NIFTY50": TERM["muted"], "buffett": TERM["cyan"],
    "magic_formula": TERM["up"], "piotroski": "#a78bfa", "graham_defensive": TERM["down"],
}
_STRAT_LABEL = {
    "v3": "Northstar V3", "NIFTY50": "NIFTY 50", "buffett": "Buffett",
    "magic_formula": "Magic Formula", "piotroski": "Piotroski", "graham_defensive": "Graham Value",
}


def _bench_nav() -> pd.DataFrame:
    df = _read_parquet("data/pnl/strategy_benchmark_nav.parquet")
    if df.empty or "date" not in df.columns:
        return pd.DataFrame()
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    return df.dropna(subset=["date"])


def paper_fund_cockpit(bundle: dict[str, Any]) -> Optional[go.Figure]:
    """The fund headline: ₹100cr NAV vs NIFTY-50 to the honest last-market date,
    with the live P&L, cost & tax drag read straight from the one truth."""
    nav = _nav()
    summ = _fund_summary()
    if nav.empty:
        return None
    bench = _bench_nav()
    nifty = bench[bench["strategy"] == "NIFTY50"] if not bench.empty else pd.DataFrame()

    fig = make_subplots(
        rows=2, cols=2, specs=[[{"type": "xy", "colspan": 2}, None],
                               [{"type": "xy"}, {"type": "xy"}]],
        row_heights=[0.62, 0.38], vertical_spacing=0.16, horizontal_spacing=0.12,
        subplot_titles=("Fund NAV vs NIFTY-50 (₹100cr base, rebased to 100)",
                        "Drawdown (underwater)", "Frictions: cost & tax drag (₹)"),
    )
    base = nav["nav_combined"].iloc[0]
    fig.add_trace(go.Scatter(x=nav["date"], y=100 * nav["nav_combined"] / base, mode="lines",
                             line=dict(color=TERM["amber"], width=2), name="Northstar V3"), row=1, col=1)
    if not nifty.empty:
        nb = nifty.sort_values("date")
        fig.add_trace(go.Scatter(x=nb["date"], y=100 * nb["nav_per_unit"] / nb["nav_per_unit"].iloc[0],
                                 mode="lines", line=dict(color=TERM["muted"], width=1.5, dash="dot"),
                                 name="NIFTY 50"), row=1, col=1)
    # drawdown
    fig.add_trace(go.Scatter(x=nav["date"], y=nav["drawdown"] * 100, mode="lines", fill="tozeroy",
                             line=dict(color=TERM["down"], width=1), showlegend=False), row=2, col=1)
    # cost/tax drag bars
    costs = summ.get("costs", {})
    labels = ["cost drag", "tax drag"]
    vals = [costs.get("cost_drag_pct", 0.0), costs.get("tax_drag_pct", 0.0)]
    fig.add_trace(go.Bar(x=labels, y=vals, marker_color=[TERM["warn"], TERM["down"]], showlegend=False,
                         text=[f"{v:.2f}%" for v in vals], textposition="outside"), row=2, col=2)

    m = summ.get("metrics", {})
    as_of = m.get("as_of", str(nav["date"].max().date()))
    title = (f"Paper Fund Cockpit — ₹{m.get('final_nav', nav['nav_combined'].iloc[-1]):,.0f} "
             f"({m.get('total_return_pct', 0):+.1f}%, Sharpe {m.get('sharpe', 0):.2f}, "
             f"maxDD {m.get('max_drawdown_pct', 0):.1f}%) · as of {as_of}")
    fig.update_layout(title=title, height=640, legend=dict(orientation="h", y=1.02, x=0))
    return fig


def paper_fund_blotter(bundle: dict[str, Any]) -> Optional[go.Figure]:
    """The real position book, marked to market: value, weight, cost & unrealized P&L."""
    pos = _positions()
    if pos.empty:
        return None
    pos = pos.sort_values("market_value", ascending=False)
    upnl = pd.to_numeric(pos["unrealized_pnl"], errors="coerce").fillna(0.0)
    row_fill = [["rgba(38,224,127,0.10)" if v >= 0 else "rgba(255,77,77,0.10)" for v in upnl]]
    def f(x, p="{:,.0f}"):
        try: return p.format(float(x))
        except Exception: return "—"
    header = ["Ticker", "Sector", "Qty", "Avg Cost", "Last", "Mkt Value", "Wt%", "Unreal P&L"]
    cols = [
        pos["name"].tolist(),
        pos["sector"].astype(str).str.slice(0, 18).tolist(),
        [f(x) for x in pos["quantity"]],
        [f(x, "₹{:,.1f}") for x in pos.get("avg_cost", [])],
        [f(x, "₹{:,.1f}") for x in pos.get("last_price", [])],
        [f(x, "₹{:,.0f}") for x in pos["market_value"]],
        [f(x, "{:.1f}") for x in pos.get("weight_pct", [])],
        [f(x, "₹{:+,.0f}") for x in upnl],
    ]
    fig = _table(header, cols, title="Holdings Blotter — live position book (marked to market)",
                 colcolors=row_fill * len(header), widths=[0.8, 1.3, 0.8, 0.9, 0.9, 1.1, 0.6, 1.1])
    fig.update_layout(height=max(320, 120 + 26 * len(pos)))
    return fig


def paper_fund_liquidation(bundle: dict[str, Any]) -> Optional[go.Figure]:
    """Days to fully exit each name at the ADV participation cap — proof the
    book cannot be dumped in a day (hedge-fund liquidation realism)."""
    df = _read_parquet("data/pnl/liquidation_schedule.parquet")
    if df.empty or "ticker" not in df.columns:
        return None
    df = df.copy()
    df["name"] = df["ticker"].astype(str).str.replace(".NS", "", regex=False)
    df = df.sort_values("days_to_exit", ascending=True).tail(20)
    colors = [TERM["down"] if d >= 4 else TERM["warn"] if d >= 2 else TERM["up"] for d in df["days_to_exit"]]
    fig = go.Figure(go.Bar(
        x=df["days_to_exit"], y=df["name"], orientation="h", marker_color=colors,
        text=[f"{int(d)}d" for d in df["days_to_exit"]], textposition="outside", textfont=dict(size=9),
        hovertemplate="%{y}: %{x} days to exit<extra></extra>",
    ))
    fig.update_layout(title="Liquidation Schedule — trading days to fully exit each name (@15% ADV/day)",
                      xaxis_title="days to exit", height=520)
    return fig


def strategy_benchmark_race(bundle: dict[str, Any]) -> Optional[go.Figure]:
    """V3 vs the famous strategies vs NIFTY, all run through the SAME ₹100cr
    engine (identical costs/taxes/caps). The yardstick future alpha must beat.

    Note: strategies are built from the current fundamentals snapshot and held
    from inception — a 'current book, held' analysis, not a live track record."""
    df = _bench_nav()
    if df.empty:
        return None
    fig = go.Figure()
    order = ["piotroski", "magic_formula", "buffett", "NIFTY50", "graham_defensive", "v3"]
    strategies = [s for s in order if s in set(df["strategy"])] + \
                 [s for s in df["strategy"].unique() if s not in order]
    finals = []
    for s in strategies:
        g = df[df["strategy"] == s].sort_values("date")
        if g.empty:
            continue
        rebased = 100 * g["nav_per_unit"] / g["nav_per_unit"].iloc[0]
        finals.append((s, rebased.iloc[-1] - 100))
        width = 2.4 if s == "v3" else (1.4 if s == "NIFTY50" else 1.6)
        dash = "dot" if s == "NIFTY50" else None
        fig.add_trace(go.Scatter(
            x=g["date"], y=rebased, mode="lines", name=_STRAT_LABEL.get(s, s),
            line=dict(color=_STRAT_COLOR.get(s, TERM["text"]), width=width, dash=dash),
            hovertemplate=_STRAT_LABEL.get(s, s) + ": %{y:.0f}<extra></extra>",
        ))
    fig.update_layout(
        title="Strategy Race — V3 vs famous strategies vs NIFTY (₹100cr each, rebased to 100)",
        yaxis_title="growth of 100", height=520, legend=dict(orientation="h", y=1.03, x=0),
    )
    return fig
