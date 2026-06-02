"""Daily portfolio risk section."""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta

import numpy as np
import pandas as pd

from src.reporting.common import (
    PROJECT_ROOT,
    SectionResult,
    load_current_positions_frame,
    money_text,
    normalize_datetime_frame,
    pct_text,
    read_parquet_candidates,
    render_note,
    safe_float,
    select_as_of,
    unavailable_section,
)
from src.reporting.renderers.html_renderer import HTMLRenderer, render_metric_grid, render_table


SECTION_NAME = "portfolio_risk"
SECTION_TITLE = "Portfolio Risk Metrics"


def _governor_breaches(report_date: date) -> int:
    db_path = PROJECT_ROOT / "data" / "runtime" / "portfolio_runtime.db"
    if not db_path.exists():
        return 0
    cutoff = pd.Timestamp(report_date - timedelta(days=7)).isoformat()
    con = sqlite3.connect(db_path)
    try:
        query = """
            select count(*)
            from portfolio_events
            where timestamp_utc >= ?
              and risk_override_flag = 1
        """
        return int(con.execute(query, (cutoff,)).fetchone()[0])
    finally:
        con.close()


def build_section(report_date: date) -> SectionResult:
    try:
        positions = load_current_positions_frame()
        if positions.empty:
            raise KeyError("No current positions available")

        if "side" in positions.columns:
            positions["side"] = positions["side"].fillna("long")
        else:
            positions["side"] = "long"
        gross_exposure = safe_float(positions["weight"].abs().sum(), 0.0) or 0.0
        net_exposure = safe_float(positions.loc[positions["side"].eq("long"), "weight"].sum(), 0.0) or 0.0

        held_tickers = positions["ticker"].astype(str).tolist()
        prices = read_parquet_candidates(
            ["data/processed/prices.parquet", "data/canonical/prices/equity_prices_daily.parquet"],
            columns=["Date", "Close", "ticker"],
        )
        prices = normalize_datetime_frame(prices, date_candidates=("Date", "date"))
        prices = select_as_of(prices, report_date)
        prices = prices.loc[prices["ticker"].isin(held_tickers)].copy()
        prices["Close"] = pd.to_numeric(prices["Close"], errors="coerce")
        price_matrix = prices.pivot_table(index="date", columns="ticker", values="Close", aggfunc="last").sort_index()
        returns = price_matrix.pct_change(fill_method=None).dropna(how="all")
        latest_returns = returns.iloc[-1].fillna(0.0) if not returns.empty else pd.Series(dtype=float)
        weights = positions.set_index("ticker")["weight"].reindex(latest_returns.index).fillna(0.0)
        portfolio_return_1d = safe_float((weights * latest_returns).sum(), 0.0)

        if returns.empty:
            var_95_1d = None
        else:
            cov = returns.tail(60).fillna(0.0).cov()
            aligned_weights = positions.set_index("ticker")["weight"].reindex(cov.index).fillna(0.0).to_numpy()
            portfolio_vol = float(np.sqrt(np.clip(aligned_weights @ cov.to_numpy() @ aligned_weights, 0.0, None)))
            var_95_1d = 1.645 * portfolio_vol

        top5_concentration = safe_float(positions.nlargest(5, "weight")["weight"].sum() / max(gross_exposure, 1e-9))
        governor_breaches = _governor_breaches(report_date)

        positions_table = positions.nlargest(10, "weight")[
            ["ticker", "sector", "weight", "market_value", "unrealized_pnl"]
        ].copy()
        positions_table["Weight"] = positions_table["weight"].map(lambda x: pct_text(x, digits=2))
        positions_table["Market Value"] = positions_table["market_value"].map(lambda x: money_text(x, digits=0))
        positions_table["Unrealized PnL"] = positions_table["unrealized_pnl"].map(lambda x: money_text(x, digits=0))
        positions_table = positions_table.drop(columns=["weight", "market_value", "unrealized_pnl"]).rename(columns={"ticker": "Ticker", "sector": "Sector"})

        metrics = render_metric_grid(
            [
                ("Daily PnL estimate", pct_text(portfolio_return_1d, digits=2, signed=True), "Weight-adjusted latest return"),
                ("Gross exposure", pct_text(gross_exposure, digits=1), None),
                ("Net exposure", pct_text(net_exposure, digits=1, signed=True), "Current core book bias"),
                ("VaR 95% 1D", pct_text(var_95_1d, digits=2), "Parametric from 60D covariance"),
                ("Top-5 concentration", pct_text(top5_concentration, digits=1), ">40% gets flagged"),
                ("Governor breaches 7D", str(governor_breaches), "Runtime risk overrides"),
            ]
        )
        status = "warn" if (top5_concentration or 0.0) > 0.40 or governor_breaches > 0 else "ok"
        badge = "ALERT" if status == "warn" else "OK"
        summary = f"{len(positions)} live equity positions with {pct_text(gross_exposure, digits=1)} gross exposure."
        return SectionResult(
            name=SECTION_NAME,
            title=SECTION_TITLE,
            status=status,
            badge=badge,
            summary=summary,
            body_html=metrics + render_table(positions_table) + render_note("Governor breach count is sourced from runtime risk override flags because a dedicated governor log parquet is not present."),
        )
    except (FileNotFoundError, KeyError) as exc:
        return unavailable_section(SECTION_TITLE, str(exc), name=SECTION_NAME)
    except Exception as exc:
        return unavailable_section(SECTION_TITLE, f"Unexpected error: {exc}", name=SECTION_NAME)


if __name__ == "__main__":
    section = build_section(date.today())
    print(HTMLRenderer(title=SECTION_TITLE).render_section(section))
