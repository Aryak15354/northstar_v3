"""Weekly review assembler."""

from __future__ import annotations

import sys
from datetime import date, datetime

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.reporting.common import LOGGER, PROJECT_ROOT
from src.reporting.renderers.html_renderer import HTMLRenderer
from src.reporting.report_versioning import write_text_with_archive
from src.reporting.sections.factor_attribution import build_section as build_factor_attribution
from src.reporting.sections.governance_review import build_section as build_governance_review
from src.reporting.sections.macro_regime_review import build_section as build_macro_regime_review
from src.reporting.sections.performance_analytics import build_section as build_performance_analytics
from src.reporting.sections.rebalance_summary import build_section as build_rebalance_summary
from src.reporting.sections.sector_concentration import build_section as build_sector_concentration
from src.reporting.sections.signal_research import build_section as build_signal_research


def _week_label(report_date: date) -> str:
    iso = report_date.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def run_weekly_review(report_date: date) -> str:
    sections = [
        build_rebalance_summary(report_date),
        build_factor_attribution(report_date),
        build_performance_analytics(report_date),
        build_sector_concentration(report_date),
        build_macro_regime_review(report_date),
        build_signal_research(report_date),
        build_governance_review(report_date),
    ]
    renderer = HTMLRenderer(title="Northstar V3 Weekly Review")
    html = renderer.render_document(
        report_type="Weekly Review",
        report_date=_week_label(report_date),
        generated_at=datetime.now(),
        subtitle="Weekly operating review grounded in the live ledger, runtime DB, strategy registry, regime models, and PIT research snapshot.",
        sections=sections,
    )
    output_path = PROJECT_ROOT / "reports" / "weekly" / f"{_week_label(report_date)}.html"
    write_text_with_archive(output_path, html)
    LOGGER.info("Generated weekly review at %s", output_path)
    return str(output_path)


if __name__ == "__main__":
    print(run_weekly_review(date.today()))
