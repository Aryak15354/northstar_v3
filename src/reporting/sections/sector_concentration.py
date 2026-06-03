"""Weekly sector and concentration section."""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from src.reporting.common import (
    SectionResult,
    latest_research_factor_frame,
    load_current_positions_frame,
    load_sector_mapping,
    normalize_datetime_frame,
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
    render_heatmap,
    render_metric_grid,
)


SECTION_NAME = "sector_concentration"
SECTION_TITLE = "Sector & Concentration Risk"


def build_section(report_date: date) -> SectionResult:
    try:
        positions = load_current_positions_frame()
        sector_map = load_sector_mapping().drop_duplicates("ticker_base")
        positions = positions.merge(sector_map[["ticker_base", "sector"]].rename(columns={"sector": "sector_map"}), on="ticker_base", how="left")
        positions["sector"] = positions["sector"].fillna(positions["sector_map"])
        if positions.empty:
            raise KeyError("No positions available")

        scores = read_parquet_candidates(["data/processed/scores.parquet"])
        benchmark_sector = scores.groupby("sector").size() / max(len(scores), 1)
        portfolio_sector = positions.groupby("sector")["weight"].sum()
        tilt = (portfolio_sector - benchmark_sector.reindex(portfolio_sector.index).fillna(0.0)).sort_values()

        prices = read_parquet_candidates(
            ["data/processed/prices.parquet", "data/canonical/prices/equity_prices_daily.parquet"],
            columns=["Date", "Close", "ticker"],
        )
        prices = normalize_datetime_frame(prices, date_candidates=("Date", "date"))
        prices = select_as_of(prices, report_date)
        price_matrix = prices.pivot_table(index="date", columns="ticker", values="Close", aggfunc="last").sort_index()
        returns = price_matrix.pct_change(fill_method=None).dropna(how="all").tail(120)
        held_weights = positions.set_index("ticker")["weight"]
        common_cols = [col for col in returns.columns if col in held_weights.index]
        portfolio_beta = None
        if common_cols:
            portfolio_returns = returns[common_cols].fillna(0.0).mul(held_weights.reindex(common_cols).fillna(0.0), axis=1).sum(axis=1)
            benchmark_returns = returns.mean(axis=1)
            cov = np.cov(portfolio_returns, benchmark_returns)
            if cov.shape == (2, 2) and cov[1, 1] != 0:
                portfolio_beta = float(cov[0, 1] / cov[1, 1])

        research = latest_research_factor_frame(report_date, extra_columns=["bab_beta", "amihud_illiquidity", "piotroski_f_score_norm", "max_lottery_21d", "earnings_quality_score"])
        latest_slice = research.loc[research["date"] == research["date"].max()].copy()
        exposure = (
            latest_slice.drop(columns=["sector"], errors="ignore")
            .merge(positions[["ticker_base", "weight", "sector"]], on="ticker_base", how="inner")
            .groupby("sector")[["bab_beta", "amihud_illiquidity", "piotroski_f_score_norm", "max_lottery_21d", "earnings_quality_score"]]
            .mean()
        )
        heatmap = render_heatmap(exposure.rename(columns={"piotroski_f_score_norm": "piotroski", "max_lottery_21d": "max_lottery", "earnings_quality_score": "earnings_quality"}))
        tilt_chart = render_bar_chart_horizontal(
            list(tilt.index),
            list((tilt * 100.0).round(2)),
            width=620,
            height=max(180, len(tilt) * 24),
            color_fn=lambda value: "#2ea043" if value >= 0 else "#f85149",
        )
        hhi = float((positions["weight"] ** 2).sum())

        metrics = render_metric_grid(
            [
                ("HHI", f"{hhi:.4f}", "1.0 = fully concentrated"),
                ("Top-1 weight", pct_text(positions["weight"].max(), digits=2), None),
                ("Top-5 weight", pct_text(positions.nlargest(5, "weight")["weight"].sum(), digits=2), None),
                ("Top-10 weight", pct_text(positions.nlargest(10, "weight")["weight"].sum(), digits=2), None),
                ("Portfolio beta", f"{portfolio_beta:.2f}" if portfolio_beta is not None else "N/A", "Vs equal-weight 500-name proxy"),
            ]
        )
        body = metrics + render_chart_block("Sector active tilts", tilt_chart) + render_chart_block("Sector factor exposure heatmap", heatmap)
        body += render_note("Benchmark sector weights are derived from the live 500-name score universe when an explicit benchmark-weight file is unavailable.")
        return SectionResult(
            name=SECTION_NAME,
            title=SECTION_TITLE,
            status="warn" if (positions.nlargest(5, "weight")["weight"].sum() > 0.40) else "ok",
            badge="ALERT" if (positions.nlargest(5, "weight")["weight"].sum() > 0.40) else "OK",
            summary="Sector concentration risk is measured against the equal-weight live score universe and current PIT factor exposures.",
            body_html=body,
        )
    except (FileNotFoundError, KeyError) as exc:
        return unavailable_section(SECTION_TITLE, str(exc), name=SECTION_NAME)
    except Exception as exc:
        return unavailable_section(SECTION_TITLE, f"Unexpected error: {exc}", name=SECTION_NAME)


if __name__ == "__main__":
    print(HTMLRenderer(title=SECTION_TITLE).render_section(build_section(date.today())))
