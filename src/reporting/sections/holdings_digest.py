"""Daily holdings digest section."""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd

from src.reporting.common import (
    SectionResult,
    factor_columns,
    latest_research_factor_frame,
    load_current_positions_frame,
    load_sector_mapping,
    normalize_datetime_frame,
    normalize_ticker,
    pct_text,
    read_parquet_candidates,
    render_note,
    safe_float,
    select_as_of,
    unavailable_section,
)
from src.reporting.renderers.html_renderer import (
    HTMLRenderer,
    render_bar_chart_horizontal,
    render_chart_block,
    render_metric_grid,
    render_table,
)


SECTION_NAME = "holdings_digest"
SECTION_TITLE = "Top Holdings Digest"


def _factor_signs() -> dict[str, float]:
    return {
        "bab_beta": -1.0,
        "amihud_illiquidity": -1.0,
        "piotroski_f_score_norm": 1.0,
        "piotroski_f_score": 1.0,
        "max_lottery_21d": -1.0,
        "max_lottery_5d": -1.0,
        "earnings_quality_score": 1.0,
    }


def _zscore(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    std = numeric.std(ddof=0)
    if pd.isna(std) or std == 0:
        return pd.Series(np.zeros(len(series)), index=series.index)
    return (numeric - numeric.mean()) / std


def build_section(report_date: date) -> SectionResult:
    try:
        positions = load_current_positions_frame()
        sector_map = load_sector_mapping()
        research = latest_research_factor_frame(report_date)
        latest_date = research["date"].max()
        prior_cutoff = pd.Timestamp(report_date) - pd.Timedelta(days=7)
        latest_slice = research.loc[research["date"] == latest_date].copy()
        prior_slice = research.loc[research["date"] <= prior_cutoff].copy()
        prior_slice = prior_slice.loc[prior_slice["date"] == prior_slice["date"].max()].copy() if not prior_slice.empty else pd.DataFrame()
        if latest_slice.empty or positions.empty:
            raise KeyError("Missing live holdings or research factors")

        factor_features = [
            "bab_beta",
            "amihud_illiquidity",
            "piotroski_f_score_norm",
            "max_lottery_21d",
            "earnings_quality_score",
        ]
        sign_map = _factor_signs()
        for col in factor_features:
            if col in latest_slice.columns:
                latest_slice[f"{col}_signed_z"] = _zscore(latest_slice[col]) * sign_map.get(col, 1.0)
            if not prior_slice.empty and col in prior_slice.columns:
                prior_slice[f"{col}_signed_z"] = _zscore(prior_slice[col]) * sign_map.get(col, 1.0)

        latest_slice["composite_score"] = latest_slice[[c for c in latest_slice.columns if c.endswith("_signed_z")]].mean(axis=1)
        if not prior_slice.empty:
            prior_slice["composite_score"] = prior_slice[[c for c in prior_slice.columns if c.endswith("_signed_z")]].mean(axis=1)
            prior_scores = prior_slice[["ticker_base", "composite_score"]].drop_duplicates("ticker_base").rename(columns={"composite_score": "composite_score_1w"})
        else:
            prior_scores = pd.DataFrame(columns=["ticker_base", "composite_score_1w"])

        latest_scores = latest_slice[["ticker_base", "ticker", "sector", "composite_score"]].drop_duplicates("ticker_base")
        positions = positions.merge(latest_scores, on="ticker_base", how="left", suffixes=("", "_research"))
        positions = positions.merge(prior_scores, on="ticker_base", how="left")
        positions = positions.merge(
            sector_map[["ticker_base", "company_name", "sector"]].rename(columns={"sector": "sector_map"}),
            on="ticker_base",
            how="left",
        )
        positions["sector"] = positions["sector"].fillna(positions["sector_map"])
        positions["name"] = positions["company_name"].fillna(positions["ticker_base"])
        positions["score_delta_1w"] = positions["composite_score"] - positions["composite_score_1w"]

        prices = read_parquet_candidates(
            ["data/processed/prices.parquet", "data/canonical/prices/equity_prices_daily.parquet"],
            columns=["Date", "Close", "ticker"],
        )
        prices = normalize_datetime_frame(prices, date_candidates=("Date", "date"))
        prices = select_as_of(prices, report_date)
        prices = prices.loc[prices["ticker"].isin(positions["ticker"])]
        px = prices.pivot_table(index="date", columns="ticker", values="Close", aggfunc="last").sort_index().pct_change(fill_method=None).tail(1)
        latest_ret = px.iloc[-1].to_dict() if not px.empty else {}
        positions["pnl_1d"] = positions["ticker"].map(latest_ret)

        top_longs = positions.nlargest(10, "weight").copy()
        top_longs["Weight"] = top_longs["weight"].map(lambda x: pct_text(x, digits=2))
        top_longs["Composite Score"] = top_longs["composite_score"].map(lambda x: f"{x:.2f}" if pd.notna(x) else "N/A")
        top_longs["Score Delta 1W"] = top_longs["score_delta_1w"].map(lambda x: f"{x:+.2f}" if pd.notna(x) else "N/A")
        top_longs["PnL 1D"] = top_longs["pnl_1d"].map(lambda x: pct_text(x, digits=2, signed=True))
        long_table = top_longs[["ticker", "name", "sector", "Weight", "Composite Score", "Score Delta 1W", "PnL 1D"]].rename(
            columns={"ticker": "Ticker", "name": "Name", "sector": "Sector"}
        )

        short_table_html = "<p class='section-note'>No active short book in the current core portfolio.</p>"
        portfolio_sector = positions.groupby("sector", dropna=True)["weight"].sum().sort_values(ascending=False)
        scores = read_parquet_candidates(["data/processed/scores.parquet"])
        benchmark_sector = scores.groupby("sector").size() / max(len(scores), 1)
        sector_tilt = (portfolio_sector - benchmark_sector.reindex(portfolio_sector.index).fillna(0.0)).sort_values()
        tilt_chart = render_bar_chart_horizontal(
            list(sector_tilt.index),
            list((sector_tilt * 100.0).round(2)),
            width=620,
            height=max(180, len(sector_tilt) * 24),
            color_fn=lambda value: "#2ea043" if value >= 0 else "#f85149",
        )

        metrics = render_metric_grid(
            [
                ("Held names", str(len(positions)), "Current core book"),
                ("Top holding", top_longs.iloc[0]["ticker"] if not top_longs.empty else "N/A", pct_text(safe_float(top_longs.iloc[0]["weight"]) if not top_longs.empty else None, digits=2)),
                ("Sector tilts flagged", str(int((sector_tilt.abs() > 0.05).sum())), "Absolute tilt above 5%"),
            ]
        )
        body = (
            metrics
            + "<div class='split-grid'>"
            + "<div><h3>Top Longs</h3>"
            + render_table(long_table)
            + "</div><div><h3>Top Shorts</h3>"
            + short_table_html
            + "</div></div>"
            + render_chart_block("Sector tilt vs equal-weight score universe benchmark", tilt_chart)
            + render_note("Sector benchmark is derived from the equal-weight 500-name score universe when a dedicated Nifty500 sector-weight file is unavailable.")
        )
        return SectionResult(
            name=SECTION_NAME,
            title=SECTION_TITLE,
            status="ok",
            badge="OK",
            summary=f"Top holdings are enriched from the live PIT research snapshot dated {pd.Timestamp(latest_date).date()}.",
            body_html=body,
        )
    except (FileNotFoundError, KeyError) as exc:
        return unavailable_section(SECTION_TITLE, str(exc), name=SECTION_NAME)
    except Exception as exc:
        return unavailable_section(SECTION_TITLE, f"Unexpected error: {exc}", name=SECTION_NAME)


if __name__ == "__main__":
    section = build_section(date.today())
    print(HTMLRenderer(title=SECTION_TITLE).render_section(section))
