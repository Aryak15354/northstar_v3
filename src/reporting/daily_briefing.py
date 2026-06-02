"""Daily briefing assembler."""

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
from src.reporting.sections.factor_health import build_section as build_factor_health
from src.reporting.sections.holdings_digest import build_section as build_holdings_digest
from src.reporting.sections.macro_pulse import build_section as build_macro_pulse
from src.reporting.sections.portfolio_risk import build_section as build_portfolio_risk
from src.reporting.sections.regime_snapshot import build_section as build_regime_snapshot
from src.reporting.sections.stress_watch import build_section as build_stress_watch
from src.reporting.sections.system_health import build_section as build_system_health


def run_daily_briefing(report_date: date) -> str:
    sections = [
        build_regime_snapshot(report_date),
        build_macro_pulse(report_date),
        build_factor_health(report_date),
        build_portfolio_risk(report_date),
        build_system_health(report_date),
        build_holdings_digest(report_date),
        build_stress_watch(report_date),
    ]
    renderer = HTMLRenderer(title="Northstar V3 Daily Briefing")
    html = renderer.render_document(
        report_type="Daily Briefing",
        report_date=report_date.isoformat(),
        generated_at=datetime.now(),
        subtitle="Canonical operational briefing sourced exclusively from live Northstar artifacts.",
        sections=sections,
    )
    output_path = PROJECT_ROOT / "reports" / "daily" / f"{report_date.isoformat()}.html"
    write_text_with_archive(output_path, html)
    LOGGER.info("Generated daily briefing at %s", output_path)
    return str(output_path)


if __name__ == "__main__":
    print(run_daily_briefing(date.today()))
