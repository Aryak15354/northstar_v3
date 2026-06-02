"""Weekly signal research update section."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd

from src.reporting.common import PROJECT_ROOT, SectionResult, read_json_candidates, render_note, unavailable_section
from src.reporting.renderers.html_renderer import HTMLRenderer, render_metric_grid, render_table


SECTION_NAME = "signal_research"
SECTION_TITLE = "Signal Research Update"


def build_section(report_date: date) -> SectionResult:
    try:
        registry = read_json_candidates(["data/model_registry/strategy_registry.json"])
        research_kernel = read_json_candidates(["data/results/research/state/research_kernel_status.json"])
        strategies = registry.get("strategies", {})
        if not isinstance(strategies, dict) or not strategies:
            raise KeyError("Strategy registry is empty")

        live_rows = []
        progress_rows = []
        queue_rows = []
        for strategy_id, payload in strategies.items():
            if not isinstance(payload, dict):
                continue
            row = {
                "Name": strategy_id,
                "Family": payload.get("family", "UNKNOWN"),
                "Status": payload.get("status", "UNKNOWN"),
                "Validation IC": f"{float(payload.get('validation_ic_mean', 0.0)):.3f}",
                "Live IC": f"{float(payload.get('current_live_ic', 0.0)):.3f}",
            }
            status = str(payload.get("status", "")).upper()
            if status in {"ACTIVE", "PROBATION"}:
                live_rows.append(row)
            elif status in {"CANDIDATE", "IN_PROGRESS"}:
                progress_rows.append(
                    {
                        "Name": strategy_id,
                        "Family": payload.get("family", "UNKNOWN"),
                        "Stage": status,
                        "Note": payload.get("probation_reason") or payload.get("redundant_with") or "Awaiting promotion",
                    }
                )
            else:
                queue_rows.append(
                    {
                        "Name": strategy_id,
                        "Priority": "high" if float(payload.get("validation_ic_mean", 0.0)) > 0 else "watch",
                        "Source": payload.get("family", "UNKNOWN"),
                    }
                )

        latest_weekly_review = sorted(
            (PROJECT_ROOT / "data" / "results" / "research" / "weekly_reviews").rglob("weekly_review_*.json")
        )
        note_text = "No weekly research note file available."
        if latest_weekly_review:
            review = json.loads(latest_weekly_review[-1].read_text(encoding="utf-8"))
            outputs = review.get("sections", {}).get("research_outputs", {})
            note_text = (
                f"Latest weekly review logged {outputs.get('total_outputs', 0)} research outputs, "
                f"{outputs.get('actionable_outputs', 0)} actionable, modules active: "
                f"{', '.join(outputs.get('modules_active', [])) or 'unknown'}."
            )

        kernel_data = research_kernel.get("data", [])
        latest_dataset = next((item.get("data", {}) for item in kernel_data if isinstance(item, dict) and item.get("type") == "research_dataset"), {})
        metrics = render_metric_grid(
            [
                ("Tracked strategies", str(registry.get("total_strategies", len(strategies))), None),
                ("Research freeze", "ON" if research_kernel.get("freeze_active") else "OFF", None),
                ("Dataset rows", str(latest_dataset.get("n_rows", "N/A")), "Latest PIT research dataset"),
                ("Dataset features", str(latest_dataset.get("n_features", "N/A")), None),
            ]
        )
        body = metrics
        body += "<h3>Live strategies</h3>" + render_table(pd.DataFrame(live_rows).sort_values(["Status", "Live IC"], ascending=[True, False]) if live_rows else pd.DataFrame())
        body += "<h3>In progress</h3>" + render_table(pd.DataFrame(progress_rows) if progress_rows else pd.DataFrame())
        body += "<h3>Research queue</h3>" + render_table(pd.DataFrame(queue_rows).head(10) if queue_rows else pd.DataFrame())
        body += render_note(note_text)
        return SectionResult(
            name=SECTION_NAME,
            title=SECTION_TITLE,
            status="ok",
            badge="OK",
            summary="Signal research status is derived from the canonical strategy registry and research kernel status artifacts.",
            body_html=body,
        )
    except (FileNotFoundError, KeyError) as exc:
        return unavailable_section(SECTION_TITLE, str(exc), name=SECTION_NAME)
    except Exception as exc:
        return unavailable_section(SECTION_TITLE, f"Unexpected error: {exc}", name=SECTION_NAME)


if __name__ == "__main__":
    print(HTMLRenderer(title=SECTION_TITLE).render_section(build_section(date.today())))
