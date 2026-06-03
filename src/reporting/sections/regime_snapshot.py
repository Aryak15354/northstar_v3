"""Daily market regime snapshot section."""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from src.reporting.common import (
    SectionResult,
    normalize_datetime_frame,
    num_text,
    pct_text,
    read_parquet_candidates,
    render_note,
    safe_float,
    select_as_of,
    unavailable_section,
)
from src.reporting.renderers.html_renderer import (
    HTMLRenderer,
    render_chart_block,
    render_kv_rows,
    render_metric_grid,
    render_sparkline,
)


SECTION_NAME = "regime_snapshot"
SECTION_TITLE = "Market Regime Snapshot"


def _classify_vix(value: float | None) -> str:
    if value is None:
        return "UNKNOWN"
    if value < 14:
        return "LOW"
    if value < 20:
        return "ELEVATED"
    if value < 28:
        return "STRESSED"
    return "CRISIS"


def build_section(report_date: date) -> SectionResult:
    try:
        prices = read_parquet_candidates(
            ["data/processed/prices.parquet", "data/canonical/prices/equity_prices_daily.parquet"],
            columns=["Date", "Close", "ticker"],
        )
        prices = normalize_datetime_frame(prices, date_candidates=("Date", "date"))
        prices = select_as_of(prices, report_date)
        prices["Close"] = pd.to_numeric(prices["Close"], errors="coerce")
        prices = prices.dropna(subset=["date", "ticker", "Close"])
        if prices.empty:
            raise KeyError("No price rows available for report date")

        pivot = (
            prices.pivot_table(index="date", columns="ticker", values="Close", aggfunc="last")
            .sort_index()
            .dropna(axis=1, how="all")
        )
        if pivot.shape[0] < 25:
            raise KeyError("Insufficient price history to compute regime metrics")

        returns_1d = pivot.pct_change(fill_method=None)
        returns_20d = pivot.pct_change(20, fill_method=None)
        breadth_history = returns_20d.gt(0).mean(axis=1).dropna().tail(60)
        momentum_breadth = safe_float(breadth_history.iloc[-1]) if not breadth_history.empty else None

        ew_returns = returns_1d.mean(axis=1).fillna(0.0)
        ew_index = (1.0 + ew_returns).cumprod()
        ew_sma_200 = ew_index.rolling(200, min_periods=60).mean()
        trend_state = "RISK ON" if ew_index.iloc[-1] > ew_sma_200.iloc[-1] else "RISK OFF"

        realized_vol_20d = safe_float(returns_1d.std(axis=1).rolling(20, min_periods=10).mean().iloc[-1], None)
        realized_vol_pct = realized_vol_20d * np.sqrt(252.0) * 100.0 if realized_vol_20d is not None else None

        regime_df = read_parquet_candidates(
            ["data/processed/market_state.parquet", "data/processed/regime_labels.parquet"],
        )
        regime_df = normalize_datetime_frame(regime_df)
        regime_df = select_as_of(regime_df, report_date)
        latest_regime = regime_df.iloc[-1].to_dict() if not regime_df.empty else {}
        regime_label = str(
            latest_regime.get("macro_regime")
            or latest_regime.get("regime")
            or latest_regime.get("macro_label")
            or "unknown"
        )

        vix_df = read_parquet_candidates(
            ["data/processed/regime/india_vix_proxy.parquet", "data/processed/india_vix.parquet"],
        )
        vix_df = normalize_datetime_frame(vix_df, date_candidates=("Date", "date"))
        vix_df = select_as_of(vix_df, report_date)
        vix_col = "vix_proxy" if "vix_proxy" in vix_df.columns else "vix"
        vix_df[vix_col] = pd.to_numeric(vix_df[vix_col], errors="coerce")
        vix_df = vix_df.dropna(subset=[vix_col])
        latest_vix = safe_float(vix_df.iloc[-1][vix_col]) if not vix_df.empty else None
        vix_regime = _classify_vix(latest_vix)

        complacency_ratio = (realized_vol_pct / latest_vix) if (realized_vol_pct is not None and latest_vix) else None

        metrics = render_metric_grid(
            [
                ("Trend Filter", trend_state, "Equal-weight index vs 200D mean"),
                ("VIX Proxy", num_text(latest_vix, digits=1), vix_regime),
                ("Momentum Breadth", pct_text(momentum_breadth, digits=1), "Share of universe above 20D return"),
                ("PCA / Macro Regime", regime_label.replace("_", " "), "Latest canonical regime label"),
                ("Complacency Ratio", num_text(complacency_ratio, digits=2), "Realized vol / VIX proxy"),
            ]
        )
        sparkline = render_sparkline(list(breadth_history.fillna(0.0).astype(float).tolist()), width=220, height=40)
        details = render_kv_rows(
            [
                ("Universe size", f"{pivot.shape[1]:,}", None),
                ("Latest market date", str(pd.Timestamp(pivot.index[-1]).date()), None),
                ("EW index level", num_text(safe_float(ew_index.iloc[-1]), digits=3), None),
                ("20D realized vol", pct_text(realized_vol_pct / 100.0 if realized_vol_pct is not None else None, digits=1), None),
                ("VIX regime", vix_regime, "Flagged from India VIX proxy"),
            ]
        )
        chart = render_chart_block("Momentum breadth, last 60 observations", sparkline)
        summary = f"{trend_state} with {pct_text(momentum_breadth, digits=1)} breadth and {vix_regime.lower()} volatility."
        if complacency_ratio is not None and complacency_ratio > 1.2:
            summary += " Complacency ratio is elevated."

        return SectionResult(
            name=SECTION_NAME,
            title=SECTION_TITLE,
            status="warn" if complacency_ratio is not None and complacency_ratio > 1.2 else "ok",
            badge="ALERT" if complacency_ratio is not None and complacency_ratio > 1.2 else "OK",
            summary=summary,
            body_html=metrics + chart + details + render_note("Computed from canonical price, market-state, and VIX proxy artifacts."),
        )
    except (FileNotFoundError, KeyError) as exc:
        return unavailable_section(SECTION_TITLE, str(exc), name=SECTION_NAME)
    except Exception as exc:
        return unavailable_section(SECTION_TITLE, f"Unexpected error: {exc}", name=SECTION_NAME)


if __name__ == "__main__":
    section = build_section(date.today())
    print(HTMLRenderer(title=SECTION_TITLE).render_section(section))
