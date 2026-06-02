"""Daily macro pulse section."""

from __future__ import annotations

from datetime import date

import pandas as pd

from src.reporting.common import (
    SectionResult,
    find_series_change,
    normalize_datetime_frame,
    num_text,
    pct_text,
    read_parquet_candidates,
    render_note,
    rolling_signal_flag,
    safe_float,
    select_as_of,
    unavailable_section,
)
from src.reporting.renderers.html_renderer import HTMLRenderer, render_metric_grid, render_table


SECTION_NAME = "macro_pulse"
SECTION_TITLE = "Macro Pulse"


VARIABLE_MAP = {
    "INR/USD spot": [
        "rbi_other_macro_indicators__rbi_s_reference_rate_inr_per_usd",
        "rbi_50_macro_indicators__exchange_rate_of_indian_rupee_vis_vis_us_dollar_month_end",
    ],
    "10Y G-Sec yield": ["rbi_50_macro_indicators__10_year_g_sec_yield_fbil"],
    "91D T-Bill yield": ["rbi_50_macro_indicators__91_day_treasury_bill_primary_yield"],
    "Call money rate": [
        "rbi_other_macro_indicators__daily_call_money_rate_high",
        "rbi_other_macro_indicators__call_money_rate_borrowings_high",
    ],
    "RBI repo rate": [
        "rbi_50_macro_indicators__policy_repo_rate",
        "rbi_other_macro_indicators__repo_rate_overnight",
    ],
    "FII flow proxy": ["rbi_50_macro_indicators__net_portfolio_investment_us_million"],
}


def _pick_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for candidate in candidates:
        if candidate in df.columns:
            return candidate
    return None


def _format_latest(label: str, value: float | None) -> str:
    if value is None:
        return "N/A"
    if "yield" in label.lower() or "rate" in label.lower():
        return f"{value:.2f}%"
    if "flow" in label.lower():
        return f"{value:,.0f} USD mn"
    return f"{value:.2f}"


def build_section(report_date: date) -> SectionResult:
    try:
        macro = read_parquet_candidates(["data/canonical/macro/rbi_macro_wide.parquet"])
        macro = normalize_datetime_frame(macro)
        macro = select_as_of(macro, report_date)
        if macro.empty:
            raise KeyError("Macro panel empty as of report date")

        latest_ts = pd.Timestamp(macro["date"].max())
        cpi_candidates = [
            "rbi_other_macro_indicators__all_india_new_consumer_price_index_rural_urban_combined_base_2012_100",
            "rbi_50_macro_indicators__consumer_price_index_2012_100",
        ]
        cpi_col = _pick_column(macro, cpi_candidates)
        cpi_yoy = None
        cpi_1d = None
        cpi_1w = None
        cpi_flag = "N/A"
        if cpi_col:
            cpi_frame = macro[["date", cpi_col]].copy()
            cpi_frame[cpi_col] = pd.to_numeric(cpi_frame[cpi_col], errors="coerce")
            cpi_frame = cpi_frame.dropna()
            cpi_frame["cpi_yoy"] = cpi_frame[cpi_col].pct_change(12) * 100.0
            cpi_yoy, cpi_1d = find_series_change(cpi_frame[["date", "cpi_yoy"]].dropna(), "cpi_yoy", latest_ts, 1)
            _, cpi_1w = find_series_change(cpi_frame[["date", "cpi_yoy"]].dropna(), "cpi_yoy", latest_ts, 7)
            cpi_flag = rolling_signal_flag(cpi_frame["cpi_yoy"])

        rows = []
        policy_inputs: dict[str, float | None] = {}
        for label, candidates in VARIABLE_MAP.items():
            value_col = _pick_column(macro, candidates)
            if value_col is None:
                continue
            work = macro[["date", value_col]].copy()
            work[value_col] = pd.to_numeric(work[value_col], errors="coerce")
            work = work.dropna()
            latest, delta_1d = find_series_change(work, value_col, latest_ts, 1)
            _, delta_1w = find_series_change(work, value_col, latest_ts, 7)
            rows.append(
                {
                    "Variable": label,
                    "Latest": _format_latest(label, latest),
                    "Delta 1D": num_text(delta_1d, digits=2, signed=True) if latest is not None else "N/A",
                    "Delta 1W": num_text(delta_1w, digits=2, signed=True) if latest is not None else "N/A",
                    "Signal": rolling_signal_flag(work[value_col]),
                }
            )
            policy_inputs[label] = latest

        rows.append(
            {
                "Variable": "CPI YoY",
                "Latest": f"{cpi_yoy:.2f}%" if cpi_yoy is not None else "N/A",
                "Delta 1D": num_text(cpi_1d, digits=2, signed=True),
                "Delta 1W": num_text(cpi_1w, digits=2, signed=True),
                "Signal": cpi_flag,
            }
        )

        call_rate = policy_inputs.get("Call money rate")
        repo_rate = policy_inputs.get("RBI repo rate")
        gsec_week = None
        gsec_row = next((row for row in rows if row["Variable"] == "10Y G-Sec yield"), None)
        if gsec_row is not None:
            raw = gsec_row["Delta 1W"].replace("+", "").replace("N/A", "")
            gsec_week = safe_float(raw)
        if call_rate is not None and repo_rate is not None and gsec_week is not None:
            if call_rate > repo_rate + 0.25 and gsec_week > 0.15:
                pressure = "TIGHTENING PRESSURE"
            elif call_rate < repo_rate - 0.25 and gsec_week < -0.15:
                pressure = "EASING PRESSURE"
            else:
                pressure = "NEUTRAL"
        else:
            pressure = "NEUTRAL"

        metrics = render_metric_grid(
            [
                ("Macro observations", f"{len(macro):,}", "Rows in canonical RBI panel"),
                ("Latest macro date", str(latest_ts.date()), "Last observation in panel"),
                ("Policy pressure", pressure, "Call money vs repo and 10Y move"),
            ]
        )
        summary = f"Canonical macro panel through {latest_ts.date()} with policy pressure flagged as {pressure.lower()}."
        notes = "FII flow is proxied with RBI net portfolio investment because a separate daily FII equity flow artifact is not present."
        return SectionResult(
            name=SECTION_NAME,
            title=SECTION_TITLE,
            status="warn" if pressure != "NEUTRAL" else "ok",
            badge="ALERT" if pressure != "NEUTRAL" else "OK",
            summary=summary,
            body_html=metrics + render_table(pd.DataFrame(rows)) + render_note(notes),
            warnings=[notes],
        )
    except (FileNotFoundError, KeyError) as exc:
        return unavailable_section(SECTION_TITLE, str(exc), name=SECTION_NAME)
    except Exception as exc:
        return unavailable_section(SECTION_TITLE, f"Unexpected error: {exc}", name=SECTION_NAME)


if __name__ == "__main__":
    section = build_section(date.today())
    print(HTMLRenderer(title=SECTION_TITLE).render_section(section))
