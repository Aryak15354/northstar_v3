"""Weekly macro regime review section."""

from __future__ import annotations

from datetime import date

import pandas as pd

from src.reporting.common import (
    SectionResult,
    factor_columns,
    latest_research_factor_frame,
    normalize_datetime_frame,
    num_text,
    read_parquet_candidates,
    render_note,
    trailing_factor_ics,
    unavailable_section,
)
from src.reporting.renderers.html_renderer import HTMLRenderer, render_kv_rows, render_metric_grid, render_table


SECTION_NAME = "macro_regime_review"
SECTION_TITLE = "Macro Regime Review"


CATEGORY_VARS = {
    "Monetary": [
        "rbi_50_macro_indicators__policy_repo_rate",
        "rbi_other_macro_indicators__daily_call_money_rate_high",
        "rbi_50_macro_indicators__cash_reserve_ratio",
        "rbi_50_macro_indicators__statutory_liquidity_ratio",
    ],
    "Yield Curve": [
        "rbi_50_macro_indicators__91_day_treasury_bill_primary_yield",
        "rbi_50_macro_indicators__182_day_treasury_bill_primary_yield",
        "rbi_50_macro_indicators__10_year_g_sec_yield_fbil",
    ],
    "FX": [
        "rbi_other_macro_indicators__rbi_s_reference_rate_inr_per_usd",
        "rbi_50_macro_indicators__exchange_rate_of_indian_rupee_vis_vis_us_dollar_month_end",
    ],
    "Capital Flows": [
        "rbi_50_macro_indicators__net_portfolio_investment_us_million",
        "rbi_50_macro_indicators__net_foreign_direct_investment_us_million",
    ],
    "Inflation": [
        "rbi_50_macro_indicators__consumer_price_index_2012_100",
        "rbi_50_macro_indicators__wholesale_price_index_2011_12_100",
    ],
    "Money Supply": [
        "rbi_50_macro_indicators__m3_crore",
        "rbi_50_macro_indicators__bank_credit_crore",
    ],
}


def _category_signal(frame: pd.DataFrame, columns: list[str]) -> tuple[str, str]:
    available = [col for col in columns if col in frame.columns]
    if not available:
        return "N/A", "No columns"
    work = frame[["date", *available]].copy().sort_values("date")
    latest = work[available].tail(1).mean(axis=1).iloc[-1]
    prev = work[available].tail(5).head(1).mean(axis=1).iloc[0] if len(work) >= 5 else work[available].head(1).mean(axis=1).iloc[0]
    delta = float(latest - prev)
    if abs(delta) < 1e-9:
        return "FLAT", "Stable"
    return ("UP" if delta > 0 else "DOWN"), f"Delta {delta:.2f}"


def build_section(report_date: date) -> SectionResult:
    try:
        regime = read_parquet_candidates(["data/processed/regime_labels.parquet"])
        regime = normalize_datetime_frame(regime)
        regime = regime.loc[regime["date"] <= pd.Timestamp(report_date) + pd.Timedelta(days=1)].copy()
        if regime.empty:
            raise KeyError("No regime label history available")
        regime = regime.sort_values("date")
        latest_regime = str(regime.iloc[-1]["regime"])
        prior_regime = next((str(val) for val in reversed(regime["regime"].iloc[:-1].tolist()) if str(val) != latest_regime), "N/A")
        duration = 0
        for value in reversed(regime["regime"].tolist()):
            if str(value) == latest_regime:
                duration += 1
            else:
                break

        macro = read_parquet_candidates(["data/canonical/macro/rbi_macro_wide.parquet"])
        macro = normalize_datetime_frame(macro)
        macro = macro.loc[macro["date"] <= pd.Timestamp(report_date) + pd.Timedelta(days=1)].copy()

        category_rows = []
        for category, columns in CATEGORY_VARS.items():
            signal, note = _category_signal(macro, columns)
            category_rows.append({"Category": category, "Signal": signal, "Note": note})

        research = latest_research_factor_frame(report_date, extra_columns=["regime"])
        research = research.loc[research["regime"] == latest_regime].copy()
        target_col = "forward_return_5d__realized" if research["forward_return_5d__realized"].notna().any() else "forward_return_5d"
        factor_rows = []
        for factor_name, candidates in factor_columns().items():
            factor_col = next((col for col in candidates if col in research.columns), None)
            if factor_col is None or research.empty:
                continue
            _, ic_12w = trailing_factor_ics(research, factor_col, target_col)
            factor_rows.append({"Factor": factor_name, "Historical IC in regime": num_text(ic_12w, digits=3, signed=True)})

        strongest = next((row["Factor"] for row in sorted(factor_rows, key=lambda item: float(item["Historical IC in regime"].replace("+", "")) if item["Historical IC in regime"] not in {"N/A", ""} else -999, reverse=True)), "N/A") if factor_rows else "N/A"
        category_phrase = ", ".join(
            f"{row['Category']} {str(row['Signal']).lower()}" for row in category_rows[:3]
        )
        narrative = (
            f"The system is currently in {latest_regime}, and it has persisted for {duration} observations after transitioning from {prior_regime}. "
            f"Category signals indicate {category_phrase}. "
            f"Within this regime, the strongest historical factor family in the PIT research snapshot is {strongest}. "
            "Use this section as context for tilts and exposure pacing rather than as a trading instruction on its own."
        )

        metrics = render_metric_grid(
            [
                ("Current regime", latest_regime, None),
                ("Duration", f"{duration} obs", None),
                ("Prior regime", prior_regime, None),
            ]
        )
        body = metrics + render_table(pd.DataFrame(category_rows)) + render_table(pd.DataFrame(factor_rows))
        body += render_note(narrative)
        return SectionResult(
            name=SECTION_NAME,
            title=SECTION_TITLE,
            status="ok",
            badge="OK",
            summary=f"Macro regime review anchored to {latest_regime} with duration {duration}.",
            body_html=body,
        )
    except (FileNotFoundError, KeyError) as exc:
        return unavailable_section(SECTION_TITLE, str(exc), name=SECTION_NAME)
    except Exception as exc:
        return unavailable_section(SECTION_TITLE, f"Unexpected error: {exc}", name=SECTION_NAME)


if __name__ == "__main__":
    print(HTMLRenderer(title=SECTION_TITLE).render_section(build_section(date.today())))
