"""Daily stress and credit watch section."""

from __future__ import annotations

from datetime import date

import pandas as pd

from src.reporting.common import (
    SectionResult,
    latest_research_factor_frame,
    load_current_positions_frame,
    normalize_datetime_frame,
    num_text,
    read_parquet_candidates,
    render_note,
    safe_float,
    select_as_of,
    unavailable_section,
)
from src.reporting.renderers.html_renderer import HTMLRenderer, render_kv_rows, render_list, render_metric_grid


SECTION_NAME = "stress_watch"
SECTION_TITLE = "Stress & Credit Watch"


def build_section(report_date: date) -> SectionResult:
    try:
        macro = read_parquet_candidates(["data/canonical/macro/rbi_macro_wide.parquet"])
        macro = normalize_datetime_frame(macro)
        macro = select_as_of(macro, report_date)
        if macro.empty:
            raise KeyError("Macro panel empty for stress watch")

        gsec_col = "rbi_50_macro_indicators__10_year_g_sec_yield_fbil"
        tbill_col = "rbi_50_macro_indicators__91_day_treasury_bill_primary_yield"
        fii_col = "rbi_50_macro_indicators__net_portfolio_investment_us_million"
        if gsec_col not in macro.columns or tbill_col not in macro.columns:
            raise KeyError("Required term-spread columns missing from canonical macro panel")

        macro[gsec_col] = pd.to_numeric(macro[gsec_col], errors="coerce")
        macro[tbill_col] = pd.to_numeric(macro[tbill_col], errors="coerce")
        macro[fii_col] = pd.to_numeric(macro.get(fii_col), errors="coerce") if fii_col in macro.columns else pd.Series(dtype=float)
        spread_series = (macro[gsec_col] - macro[tbill_col]) * 100.0
        spread_series = spread_series.dropna()
        term_spread_bps = safe_float(spread_series.iloc[-1]) if not spread_series.empty else None
        spread_z = None
        if len(spread_series) >= 12:
            trailing = spread_series.tail(min(252, len(spread_series)))
            std = trailing.std(ddof=0)
            if std and not pd.isna(std):
                spread_z = (float(trailing.iloc[-1]) - float(trailing.mean())) / float(std)

        fii_proxy = macro[["date", fii_col]].dropna() if fii_col in macro.columns else pd.DataFrame()
        fii_7_sum = safe_float(fii_proxy[fii_col].tail(7).sum()) if not fii_proxy.empty else None
        fii_z = None
        if len(fii_proxy) >= 12:
            rolling = fii_proxy[fii_col].rolling(12).sum().dropna()
            if not rolling.empty:
                std = rolling.std(ddof=0)
                if std and not pd.isna(std):
                    fii_z = (float(rolling.iloc[-1]) - float(rolling.mean())) / float(std)
        fii_signal = "INFLOW" if (fii_7_sum or 0.0) > 0 else "OUTFLOW" if (fii_7_sum or 0.0) < 0 else "NEUTRAL"

        research = latest_research_factor_frame(report_date, extra_columns=["amihud_illiquidity", "piotroski_f_score_norm"])
        latest_slice = research.loc[research["date"] == research["date"].max()].copy()
        positions = load_current_positions_frame()
        threshold = latest_slice["amihud_illiquidity"].quantile(0.95) if "amihud_illiquidity" in latest_slice.columns else None
        illiquid_holdings = []
        crowding_score = None
        if threshold is not None:
            flagged = latest_slice.loc[latest_slice["amihud_illiquidity"] > threshold, "ticker_base"].tolist()
            held = positions["ticker_base"].isin(flagged)
            illiquid_holdings = positions.loc[held, "ticker"].astype(str).tolist()

        merged = positions.merge(
            latest_slice[["ticker_base", "piotroski_f_score_norm"]].drop_duplicates("ticker_base"),
            on="ticker_base",
            how="left",
        )
        if merged["piotroski_f_score_norm"].notna().sum() >= 3:
            crowding_score = safe_float(merged["weight"].corr(merged["piotroski_f_score_norm"]))

        metrics = render_metric_grid(
            [
                ("Term spread", f"{term_spread_bps:.1f} bps" if term_spread_bps is not None else "N/A", f"z={spread_z:.2f}" if spread_z is not None else "z=N/A"),
                ("Portfolio flow proxy", f"{fii_7_sum:,.0f} USD mn" if fii_7_sum is not None else "N/A", fii_signal),
                ("Illiquid holdings", str(len(illiquid_holdings)), "Top 5% Amihud screen"),
                ("Crowding score", num_text(crowding_score, digits=2), "Weights vs Piotroski"),
            ]
        )
        details = render_kv_rows(
            [
                ("Term-spread trend", "WIDENING" if (spread_z or 0.0) > 0 else "FLATTENING", None),
                ("Flow signal", fii_signal, "RBI net portfolio investment proxy"),
                ("Crowding label", "HIGH" if (crowding_score or 0.0) > 0.6 else "MODERATE" if (crowding_score or 0.0) > 0.3 else "LOW", None),
            ]
        )
        body = metrics + details + "<h3>Illiquid holdings</h3>" + render_list(illiquid_holdings or ["None"])
        body += render_note("Daily FII equity flow is approximated with RBI net portfolio investment because a dedicated daily FII flow artifact is not available.")
        status = "warn" if illiquid_holdings or abs(spread_z or 0.0) > 2.0 else "ok"
        badge = "ALERT" if status == "warn" else "OK"
        return SectionResult(
            name=SECTION_NAME,
            title=SECTION_TITLE,
            status=status,
            badge=badge,
            summary="Stress watch combines term spread, flow proxy, liquidity, and crowding diagnostics from canonical macro and PIT research data.",
            body_html=body,
        )
    except (FileNotFoundError, KeyError) as exc:
        return unavailable_section(SECTION_TITLE, str(exc), name=SECTION_NAME)
    except Exception as exc:
        return unavailable_section(SECTION_TITLE, f"Unexpected error: {exc}", name=SECTION_NAME)


if __name__ == "__main__":
    section = build_section(date.today())
    print(HTMLRenderer(title=SECTION_TITLE).render_section(section))
