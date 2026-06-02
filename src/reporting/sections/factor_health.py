"""Daily factor health section."""

from __future__ import annotations

from datetime import date

import pandas as pd

from src.reporting.common import (
    SectionResult,
    factor_columns,
    latest_research_factor_frame,
    num_text,
    pct_text,
    render_note,
    safe_float,
    trailing_factor_ics,
    unavailable_section,
)
from src.reporting.renderers.html_renderer import (
    HTMLRenderer,
    render_bar_chart_horizontal,
    render_chart_block,
    render_metric_grid,
    render_table,
)


SECTION_NAME = "factor_health"
SECTION_TITLE = "Factor Health"


def _health_flag(ic_4w: float | None, ic_12w: float | None) -> tuple[str, str]:
    if ic_4w is None:
        return "warn", "N/A"
    if abs(ic_4w) < 0.02:
        return "critical", "RED"
    if ic_12w is not None and ic_4w < ic_12w - 0.05:
        return "warn", "AMBER"
    return "ok", "GREEN"


def build_section(report_date: date) -> SectionResult:
    try:
        research = latest_research_factor_frame(report_date)
        target_col = "forward_return_5d__realized" if research["forward_return_5d__realized"].notna().any() else "forward_return_5d"
        latest_date = research["date"].max()
        latest_slice = research.loc[research["date"] == latest_date].copy()
        if latest_slice.empty:
            raise KeyError("No latest research slice available")

        rows = []
        ic_values = []
        factor_statuses = []
        for factor_name, candidates in factor_columns().items():
            factor_col = next((col for col in candidates if col in research.columns), None)
            if factor_col is None:
                continue
            latest_values = pd.to_numeric(latest_slice[factor_col], errors="coerce").dropna()
            if latest_values.empty:
                continue
            ic_4w, ic_12w = trailing_factor_ics(research, factor_col, target_col)
            status, health = _health_flag(ic_4w, ic_12w)
            factor_statuses.append(status)
            rows.append(
                {
                    "Factor": factor_name,
                    "Feature": factor_col,
                    "IC 4W": num_text(ic_4w, digits=3, signed=True),
                    "IC 12W": num_text(ic_12w, digits=3, signed=True),
                    "Dispersion": num_text(safe_float(latest_values.std(ddof=0)), digits=3),
                    "Top Decile": num_text(safe_float(latest_values.quantile(0.9)), digits=3),
                    "Bottom Decile": num_text(safe_float(latest_values.quantile(0.1)), digits=3),
                    "Health": health,
                }
            )
            ic_values.append(0.0 if ic_4w is None else ic_4w)

        if not rows:
            raise KeyError("No factor metrics could be derived from research snapshot")

        chart = render_bar_chart_horizontal(
            [row["Factor"] for row in rows],
            ic_values,
            width=520,
            height=max(170, 26 * len(rows)),
            color_fn=lambda value: "#2ea043" if value >= 0 else "#f85149",
        )
        metrics = render_metric_grid(
            [
                ("Factor families", f"{len(rows)}", "Derived from PIT research snapshot"),
                ("Latest factor date", str(pd.Timestamp(latest_date).date()), None),
                ("Weak factors", str(sum(row["Health"] == "RED" for row in rows)), "4W IC magnitude below 0.02"),
            ]
        )
        status = "critical" if "critical" in factor_statuses else "warn" if "warn" in factor_statuses else "ok"
        badge = "CRITICAL" if status == "critical" else "ALERT" if status == "warn" else "OK"
        summary = f"{len(rows)} factor families evaluated on live PIT data through {pd.Timestamp(latest_date).date()}."
        return SectionResult(
            name=SECTION_NAME,
            title=SECTION_TITLE,
            status=status,
            badge=badge,
            summary=summary,
            body_html=metrics + render_table(pd.DataFrame(rows)) + render_chart_block("Rolling 4W cross-sectional IC", chart) + render_note("ICs are recomputed from the PIT research snapshot when a dedicated factor IC parquet is absent."),
        )
    except (FileNotFoundError, KeyError) as exc:
        return unavailable_section(SECTION_TITLE, str(exc), name=SECTION_NAME)
    except Exception as exc:
        return unavailable_section(SECTION_TITLE, f"Unexpected error: {exc}", name=SECTION_NAME)


if __name__ == "__main__":
    section = build_section(date.today())
    print(HTMLRenderer(title=SECTION_TITLE).render_section(section))
