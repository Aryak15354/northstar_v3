"""Weekly governance and model integrity review."""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta

import pandas as pd

from src.reporting.common import (
    PROJECT_ROOT,
    SectionResult,
    latest_run_report_path,
    read_json_candidates,
    read_text_candidates,
    render_note,
    unavailable_section,
)
from src.reporting.renderers.html_renderer import HTMLRenderer, render_metric_grid, render_table


SECTION_NAME = "governance_review"
SECTION_TITLE = "Governance & Model Integrity"


def build_section(report_date: date) -> SectionResult:
    try:
        latest_run = read_json_candidates([latest_run_report_path(report_date)])
        integrity = read_json_candidates(["data/processed/integrity/v3_integrity_report_latest.json"])
        unified_state = read_json_candidates(["data/state/unified_state.json"])
        registry = read_json_candidates(["models/regime_models/regime_model_registry.json"])

        errors = []
        for candidate in (["logs/pipeline_failures.log"], ["logs/operation/operation_errors.log"]):
            try:
                text = read_text_candidates(candidate)
            except FileNotFoundError:
                continue
            errors.extend([line.strip() for line in text.splitlines() if "ERROR" in line or "FAIL" in line])
        error_tail = errors[-5:]

        db_path = PROJECT_ROOT / "data" / "runtime" / "portfolio_runtime.db"
        override_count = 0
        if db_path.exists():
            con = sqlite3.connect(db_path)
            cutoff = pd.Timestamp(report_date - timedelta(days=7)).isoformat()
            override_count = int(
                con.execute(
                    "select count(*) from portfolio_events where timestamp_utc >= ? and risk_override_flag = 1",
                    (cutoff,),
                ).fetchone()[0]
            )
            con.close()

        stage_events = latest_run.get("stage_results", [])[-3:]
        stage_rows = [
            {
                "Stage": stage.get("name", "unknown"),
                "Status": stage.get("status", "UNKNOWN"),
                "Finished": stage.get("finished_at", "N/A"),
            }
            for stage in stage_events
            if isinstance(stage, dict)
        ]

        models = registry.get("models", {})
        current_regime = unified_state.get("market", {}).get("regime", "")
        current_model = models.get(current_regime) if isinstance(models, dict) else None
        if current_model is None and isinstance(models, dict) and models:
            current_model = next(iter(models.values()))
        model_row = {
            "Model regime": current_model.get("regime", "unknown") if current_model else "unknown",
            "Backend": current_model.get("backend", "unknown") if current_model else "unknown",
            "Feature count": len(current_model.get("feature_cols", []) or []) if current_model else 0,
            "Train IC": current_model.get("train_ic", "N/A") if current_model else "N/A",
            "Observations": current_model.get("n_obs", "N/A") if current_model else "N/A",
        }

        metrics = render_metric_grid(
            [
                ("Latest run", latest_run.get("overall_status", "UNKNOWN"), "Complete V3 runner"),
                ("Integrity artifact checks", str(integrity.get("summary", {}).get("artifacts_checked", "N/A")), None),
                ("Governor overrides 7D", str(override_count), "Runtime risk override flags"),
                ("Error lines tailed", str(len(error_tail)), "Pipeline + operation error logs"),
            ]
        )
        body = metrics
        body += "<h3>Recent operational events</h3>" + render_table(pd.DataFrame(stage_rows))
        body += "<h3>Current regime model</h3>" + render_table(pd.DataFrame([model_row]))
        body += render_note("StateAuthority event log and explicit gap_tracker.json are not present on the live surface, so this section uses the latest complete-system run, integrity report, runtime overrides, and regime-model registry instead.")
        if error_tail:
            body += "<h3>Error tail</h3><pre class='section-note'>" + "\n".join(error_tail) + "</pre>"
        return SectionResult(
            name=SECTION_NAME,
            title=SECTION_TITLE,
            status="warn" if latest_run.get("overall_status") != "PASS" or override_count > 0 else "ok",
            badge="ALERT" if latest_run.get("overall_status") != "PASS" or override_count > 0 else "OK",
            summary="Governance review is grounded in the latest run report, integrity diagnostics, runtime overrides, and live regime model registry.",
            body_html=body,
        )
    except (FileNotFoundError, KeyError) as exc:
        return unavailable_section(SECTION_TITLE, str(exc), name=SECTION_NAME)
    except Exception as exc:
        return unavailable_section(SECTION_TITLE, f"Unexpected error: {exc}", name=SECTION_NAME)


if __name__ == "__main__":
    print(HTMLRenderer(title=SECTION_TITLE).render_section(build_section(date.today())))
