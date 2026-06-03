"""Markdown fallback renderer for Northstar reports."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Sequence

from src.reporting.common import SectionResult


@dataclass(slots=True)
class MarkdownRenderer:
    """Simple markdown renderer for debugging/fallback use."""

    title: str

    def render_document(
        self,
        *,
        report_type: str,
        report_date: str,
        generated_at: datetime,
        sections: Sequence[SectionResult],
        subtitle: str | None = None,
    ) -> str:
        lines = [f"# {self.title}", "", f"- Type: {report_type}", f"- Report date: {report_date}", f"- Generated: {generated_at.isoformat()}"]
        if subtitle:
            lines.extend(["", subtitle])
        for section in sections:
            lines.extend(["", f"## {section.title} [{section.badge}]", ""])
            if section.summary:
                lines.append(section.summary)
                lines.append("")
            lines.append(section.body_html)
        return "\n".join(lines).strip() + "\n"
