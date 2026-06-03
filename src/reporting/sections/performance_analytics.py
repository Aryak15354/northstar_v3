"""Weekly performance analytics section."""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from src.reporting.common import SectionResult, pct_text, read_parquet_candidates, render_note, unavailable_section
from src.reporting.renderers.html_renderer import (
    HTMLRenderer,
    render_chart_block,
    render_drawdown_chart,
    render_line_chart,
    render_metric_grid,
    render_table,
)


SECTION_NAME = "performance_analytics"
SECTION_TITLE = "Performance Analytics"


def _max_drawdown(returns: pd.Series) -> float | None:
    if returns.empty:
        return None
    curve = (1.0 + returns.fillna(0.0)).cumprod()
    drawdown = curve / curve.cummax() - 1.0
    return float(drawdown.min())


def build_section(report_date: date) -> SectionResult:
    try:
        history = read_parquet_candidates(["data/dashboard/time_series/returns_history.parquet"])
        history["date"] = pd.to_datetime(history["date"], errors="coerce")
        history = history.dropna(subset=["date"]).sort_values("date")
        history = history.loc[history["date"] <= pd.Timestamp(report_date) + pd.Timedelta(days=1)]
        if history.empty:
            raise KeyError("Returns history is empty")

        windows = [20, 60, 130, 252, "inception"]
        rows = []
        for window in windows:
            subset = history if window == "inception" else history.tail(window)
            if len(subset) < 5:
                continue
            port = pd.to_numeric(subset["daily_return"], errors="coerce").fillna(0.0)
            bench = pd.to_numeric(subset["benchmark_return"], errors="coerce").fillna(0.0)
            active = pd.to_numeric(subset["excess_return"], errors="coerce").fillna(port - bench)
            sharpe = port.mean() / (port.std(ddof=0) or np.nan) * np.sqrt(252.0)
            info_ratio = active.mean() / (active.std(ddof=0) or np.nan) * np.sqrt(252.0)
            rows.append(
                {
                    "Window": str(window),
                    "Cumulative Return": pct_text((1.0 + port).prod() - 1.0, digits=2),
                    "Active Return": pct_text((1.0 + active).prod() - 1.0, digits=2),
                    "Sharpe": f"{sharpe:.2f}" if np.isfinite(sharpe) else "N/A",
                    "Information Ratio": f"{info_ratio:.2f}" if np.isfinite(info_ratio) else "N/A",
                    "Max Drawdown": pct_text(_max_drawdown(port), digits=2),
                    "Hit Rate": pct_text((active > 0).mean(), digits=1),
                    "IC": "N/A",
                }
            )

        history["portfolio_curve"] = (1.0 + history["daily_return"].fillna(0.0)).cumprod() - 1.0
        history["benchmark_curve"] = (1.0 + history["benchmark_return"].fillna(0.0)).cumprod() - 1.0
        curve_chart = render_line_chart(
            {
                "Portfolio": history["portfolio_curve"].tail(252).tolist(),
                "Benchmark": history["benchmark_curve"].tail(252).tolist(),
            },
            dates=history["date"].tail(252).astype(str).tolist(),
            width=700,
            height=220,
        )
        drawdown_series = ((1.0 + history["daily_return"].fillna(0.0)).cumprod())
        drawdown_series = drawdown_series / drawdown_series.cummax() - 1.0
        dd_chart = render_drawdown_chart(drawdown_series.tail(252).tolist(), history["date"].tail(252).astype(str).tolist())

        metrics = render_metric_grid(
            [
                ("History rows", f"{len(history):,}", "Dashboard return surface"),
                ("Latest date", str(pd.Timestamp(history['date'].max()).date()), None),
                ("52W available", "YES" if len(history) >= 252 else "PARTIAL", None),
            ]
        )
        body = metrics + render_table(pd.DataFrame(rows))
        body += render_chart_block("Cumulative return vs benchmark", curve_chart)
        body += render_chart_block("Drawdown, latest available window", dd_chart)
        body += render_note("IC is left unavailable here until a dedicated weekly score-history surface is promoted into the reporting layer.")
        return SectionResult(
            name=SECTION_NAME,
            title=SECTION_TITLE,
            status="ok",
            badge="OK",
            summary="Performance analytics are computed from the canonical dashboard return history surface.",
            body_html=body,
        )
    except (FileNotFoundError, KeyError) as exc:
        return unavailable_section(SECTION_TITLE, str(exc), name=SECTION_NAME)
    except Exception as exc:
        return unavailable_section(SECTION_TITLE, f"Unexpected error: {exc}", name=SECTION_NAME)


if __name__ == "__main__":
    print(HTMLRenderer(title=SECTION_TITLE).render_section(build_section(date.today())))
