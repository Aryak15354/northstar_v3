"""Nightly research report generation (PDF if reportlab available, JSON fallback)."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


def _collect_summary(research_dir: Path) -> Dict[str, Any]:
    latest_cycle = None
    cycle_files = sorted(research_dir.glob("research_cycle_*.json"))
    if cycle_files:
        try:
            latest_cycle = json.loads(cycle_files[-1].read_text())
        except Exception:
            latest_cycle = None

    return {
        "generated_at": datetime.now().isoformat(),
        "latest_cycle_file": str(cycle_files[-1]) if cycle_files else None,
        "latest_cycle": latest_cycle,
    }


def generate_nightly_report(
    research_dir: Path | str = "data/research",
    output_dir: Path | str = "data/research_reports",
) -> Path:
    research_path = Path(research_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    summary = _collect_summary(research_path)
    date_token = datetime.now().strftime("%Y-%m-%d")

    # Prefer PDF if dependency exists.
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas

        pdf_path = output_path / f"northstar_report_{date_token}.pdf"
        c = canvas.Canvas(str(pdf_path), pagesize=letter)
        y = 760
        c.setFont("Helvetica-Bold", 14)
        c.drawString(72, y, "Northstar Nightly Research Report")
        y -= 28
        c.setFont("Helvetica", 10)
        c.drawString(72, y, f"Generated: {summary['generated_at']}")
        y -= 18
        c.drawString(72, y, f"Latest cycle file: {summary.get('latest_cycle_file')}")

        latest_cycle = summary.get("latest_cycle") or {}
        y -= 24
        c.setFont("Helvetica-Bold", 11)
        c.drawString(72, y, "Cycle Summary")
        c.setFont("Helvetica", 10)
        y -= 16
        c.drawString(72, y, f"freeze_active: {latest_cycle.get('freeze_active')}")
        y -= 14
        c.drawString(72, y, f"modules_run: {', '.join(latest_cycle.get('modules_run', []))}")
        y -= 14
        c.drawString(72, y, f"actionable_outputs: {len(latest_cycle.get('actionable_outputs', []))}")
        y -= 14
        c.drawString(72, y, f"non_actionable_outputs: {len(latest_cycle.get('non_actionable_outputs', []))}")
        y -= 14
        c.drawString(72, y, f"errors: {len(latest_cycle.get('errors', []))}")

        c.showPage()
        c.save()
        return pdf_path
    except Exception:
        json_path = output_path / f"northstar_report_{date_token}.json"
        with open(json_path, "w", encoding="utf-8") as handle:
            json.dump(summary, handle, indent=2)
        return json_path
