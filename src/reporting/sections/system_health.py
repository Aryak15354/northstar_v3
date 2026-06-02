"""Daily system health section."""

from __future__ import annotations

from datetime import date

import pandas as pd

from src.reporting.common import (
    PROJECT_ROOT,
    SectionResult,
    age_hours,
    latest_run_report_path,
    parse_iso_datetime,
    pct_text,
    read_json_candidates,
    read_text_candidates,
    render_note,
    safe_float,
    unavailable_section,
)
from src.reporting.renderers.html_renderer import HTMLRenderer, render_metric_grid, render_table


SECTION_NAME = "system_health"
SECTION_TITLE = "System Health"


def _status_from_age(hours: float | None) -> str:
    if hours is None:
        return "STALE"
    if hours <= 26:
        return "OK"
    if hours <= 72:
        return "DEGRADED"
    return "STALE"


def build_section(report_date: date) -> SectionResult:
    try:
        unified_state = read_json_candidates(["data/state/unified_state.json"])
        manifest = read_json_candidates(["data/canonical/manifest.json"])
        run_report = read_json_candidates([latest_run_report_path(report_date)])

        outputs = manifest.get("outputs", {})
        prices_info = outputs.get("prices_daily", {})
        macro_info = outputs.get("rbi_macro_wide", {})
        sentiment_info = outputs.get("company_sentiment_daily", {})

        stage_lookup = {stage.get("name"): stage for stage in run_report.get("stage_results", []) if isinstance(stage, dict)}
        finished_at = run_report.get("finished_at")
        run_age = age_hours(finished_at)

        rows = [
            {
                "Module": "Equities",
                "Status": stage_lookup.get("Market Refresh", stage_lookup.get("Market Prices", {})).get("status", "UNKNOWN"),
                "Coverage": str(prices_info.get("unique_entities", "N/A")),
                "Last Run": finished_at or "N/A",
            },
            {
                "Module": "Macro",
                "Status": stage_lookup.get("RBI Macro", {}).get("status", "UNKNOWN"),
                "Coverage": str(max(int(macro_info.get("columns", 0)) - 2, 0) or "N/A"),
                "Last Run": stage_lookup.get("RBI Macro", {}).get("finished_at", finished_at or "N/A"),
            },
            {
                "Module": "Financials",
                "Status": stage_lookup.get("Screener Processing", {}).get("status", "UNKNOWN"),
                "Coverage": str(outputs.get("fundamentals_annual", {}).get("unique_entities", "N/A")),
                "Last Run": stage_lookup.get("Screener Processing", {}).get("finished_at", finished_at or "N/A"),
            },
            {
                "Module": "Factors",
                "Status": "OK" if (PROJECT_ROOT / "data/processed/scores.parquet").exists() else "DEGRADED",
                "Coverage": str(outputs.get("prices_daily", {}).get("unique_entities", "N/A")),
                "Last Run": unified_state.get("health", {}).get("last_updated", "N/A"),
            },
            {
                "Module": "Sentiment",
                "Status": "OK" if unified_state.get("sentiment", {}).get("is_fresh", False) else "DEGRADED",
                "Coverage": str(sentiment_info.get("unique_entities", unified_state.get("sentiment", {}).get("companies_with_coverage", "N/A"))),
                "Last Run": unified_state.get("sentiment", {}).get("pipeline_last_run", unified_state.get("sentiment", {}).get("last_updated", "N/A")),
            },
        ]

        error_lines = []
        for path_candidates in (
            ["logs/pipeline_failures.log"],
            ["logs/operation/operation_errors.log"],
        ):
            try:
                text = read_text_candidates(path_candidates)
            except FileNotFoundError:
                continue
            for line in text.splitlines():
                if "ERROR" in line or "FAIL" in line:
                    error_lines.append(line.strip())
        error_tail = error_lines[-5:]

        metrics = render_metric_grid(
            [
                ("Complete-system status", run_report.get("overall_status", "UNKNOWN"), "Latest complete_v3 run report"),
                ("Run age", f"{run_age:.1f}h" if run_age is not None else "N/A", "Stale above 26h"),
                ("Health score", pct_text(safe_float(unified_state.get("health", {}).get("overall_health_score")) / 100.0 if safe_float(unified_state.get("health", {}).get("overall_health_score")) is not None and safe_float(unified_state.get("health", {}).get("overall_health_score")) > 1 else safe_float(unified_state.get("health", {}).get("overall_health_score")), digits=1), unified_state.get("health", {}).get("health_status", "UNKNOWN")),
                ("Component availability", f"{unified_state.get('health', {}).get('components_healthy', 'N/A')}/{unified_state.get('health', {}).get('total_components', 'N/A')}", "From canonical unified state"),
            ]
        )

        body = metrics + render_table(pd.DataFrame(rows))
        if error_tail:
            body += render_note("Recent pipeline errors") + "<pre class='section-note'>" + "\n".join(error_tail) + "</pre>"
        status = "warn" if any(row["Status"] not in {"PASS", "OK"} for row in rows) or (run_age or 0.0) > 26 else "ok"
        badge = "ALERT" if status == "warn" else "OK"
        summary = f"Latest complete-system run is {run_report.get('overall_status', 'UNKNOWN')} and {len(error_tail)} recent error lines were found."
        return SectionResult(
            name=SECTION_NAME,
            title=SECTION_TITLE,
            status=status,
            badge=badge,
            summary=summary,
            body_html=body,
        )
    except (FileNotFoundError, KeyError) as exc:
        return unavailable_section(SECTION_TITLE, str(exc), name=SECTION_NAME)
    except Exception as exc:
        return unavailable_section(SECTION_TITLE, f"Unexpected error: {exc}", name=SECTION_NAME)


if __name__ == "__main__":
    section = build_section(date.today())
    print(HTMLRenderer(title=SECTION_TITLE).render_section(section))
