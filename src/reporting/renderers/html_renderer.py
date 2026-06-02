"""Self-contained HTML rendering for Northstar reports."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Iterable, Sequence

import numpy as np
import pandas as pd

from src.reporting.common import SectionResult, html_escape


CSS_PALETTE = {
    "bg_primary": "#0d1117",
    "bg_secondary": "#161b22",
    "bg_card": "#1c2128",
    "border": "#30363d",
    "text_primary": "#e6edf3",
    "text_secondary": "#8b949e",
    "green": "#2ea043",
    "red": "#f85149",
    "amber": "#d29922",
    "blue": "#388bfd",
    "purple": "#a371f7",
    "gray": "#6e7681",
}


def badge_class(status: str) -> str:
    normalized = (status or "").lower()
    if normalized in {"ok", "healthy"}:
        return "badge-ok"
    if normalized in {"warn", "amber"}:
        return "badge-warn"
    if normalized in {"critical", "fail"}:
        return "badge-critical"
    return "badge-muted"


def render_badge(label: str, status: str) -> str:
    return f"<span class='badge {badge_class(status)}'>{html_escape(label)}</span>"


def render_metric_grid(metrics: Sequence[tuple[str, str, str | None]]) -> str:
    cards = []
    for label, value, meta in metrics:
        meta_html = f"<div class='metric-meta'>{html_escape(meta)}</div>" if meta else ""
        cards.append(
            "<div class='metric-card'>"
            f"<div class='metric-label'>{html_escape(label)}</div>"
            f"<div class='metric-value'>{html_escape(value)}</div>"
            f"{meta_html}"
            "</div>"
        )
    return "<div class='metric-grid'>" + "".join(cards) + "</div>"


def render_kv_rows(rows: Sequence[tuple[str, str, str | None]]) -> str:
    html_rows = []
    for label, value, extra in rows:
        extra_html = f"<span class='kv-extra'>{html_escape(extra)}</span>" if extra else ""
        html_rows.append(
            "<div class='kv-row'>"
            f"<div class='kv-label'>{html_escape(label)}</div>"
            f"<div class='kv-value'>{html_escape(value)}{extra_html}</div>"
            "</div>"
        )
    return "<div class='kv-grid'>" + "".join(html_rows) + "</div>"


def render_table(df: pd.DataFrame, *, index: bool = False, limit: int | None = None) -> str:
    if df is None or df.empty:
        return "<p class='section-note'>No rows available.</p>"
    work = df.head(limit).copy() if limit else df.copy()
    columns = list(work.columns)
    header = "".join(f"<th>{html_escape(col)}</th>" for col in (["index"] + columns if index else columns))
    body_rows = []
    for idx, row in work.iterrows():
        parts = []
        if index:
            parts.append(f"<td>{html_escape(idx)}</td>")
        for col in columns:
            parts.append(f"<td>{html_escape(row[col])}</td>")
        body_rows.append("<tr>" + "".join(parts) + "</tr>")
    return (
        "<div class='table-wrap'><table>"
        f"<thead><tr>{header}</tr></thead>"
        f"<tbody>{''.join(body_rows)}</tbody>"
        "</table></div>"
    )


def render_list(items: Iterable[str]) -> str:
    rows = [f"<li>{html_escape(item)}</li>" for item in items if str(item).strip()]
    if not rows:
        return "<p class='section-note'>None.</p>"
    return "<ul class='bullet-list'>" + "".join(rows) + "</ul>"


def render_chart_block(title: str, chart_html: str) -> str:
    if not chart_html:
        return ""
    return (
        "<div class='chart-block'>"
        f"<div class='chart-title'>{html_escape(title)}</div>"
        f"{chart_html}"
        "</div>"
    )


def _points(values: Sequence[float], width: int, height: int, pad: int = 4) -> str:
    clean = [float(v) for v in values if v is not None and not pd.isna(v)]
    if len(clean) < 2:
        return ""
    min_v = min(clean)
    max_v = max(clean)
    span = max(max_v - min_v, 1e-9)
    xs = np.linspace(pad, width - pad, len(clean))
    ys = [height - pad - ((v - min_v) / span) * (height - 2 * pad) for v in clean]
    return " ".join(f"{x:.2f},{y:.2f}" for x, y in zip(xs, ys))


def render_sparkline(values: list[float], width: int = 120, height: int = 32, color: str = "#388bfd") -> str:
    points = _points(values, width, height)
    if not points:
        return ""
    return (
        f"<svg width='{width}' height='{height}' viewBox='0 0 {width} {height}' class='svg-chart'>"
        f"<polyline fill='none' stroke='{color}' stroke-width='2' points='{points}' />"
        "</svg>"
    )


def render_bar_chart_horizontal(
    labels: Sequence[str],
    values: Sequence[float],
    width: int = 400,
    height: int = 200,
    color_fn: Callable[[float], str] | None = None,
) -> str:
    if not labels or not values:
        return ""
    clean_values = [float(v or 0.0) for v in values]
    max_abs = max(max(abs(v) for v in clean_values), 1e-9)
    row_h = max(height / max(len(clean_values), 1), 18)
    chart_h = max(height, int(row_h * len(clean_values)))
    zero_x = width * 0.45
    items = []
    for i, (label, value) in enumerate(zip(labels, clean_values)):
        y = i * row_h + 4
        bar_w = (abs(value) / max_abs) * (width * 0.45)
        x = zero_x if value >= 0 else zero_x - bar_w
        fill = color_fn(value) if color_fn else CSS_PALETTE["blue"]
        items.append(
            f"<text x='4' y='{y + row_h * 0.7:.1f}' fill='{CSS_PALETTE['text_secondary']}' font-size='11'>{html_escape(label)}</text>"
            f"<rect x='{x:.1f}' y='{y:.1f}' width='{bar_w:.1f}' height='{row_h * 0.62:.1f}' fill='{fill}' rx='3' />"
            f"<text x='{width - 4}' y='{y + row_h * 0.7:.1f}' text-anchor='end' fill='{CSS_PALETTE['text_primary']}' font-size='11'>{value:.2f}</text>"
        )
    items.append(
        f"<line x1='{zero_x:.1f}' y1='0' x2='{zero_x:.1f}' y2='{chart_h}' stroke='{CSS_PALETTE['border']}' stroke-width='1' />"
    )
    return (
        f"<svg width='{width}' height='{chart_h}' viewBox='0 0 {width} {chart_h}' class='svg-chart'>"
        + "".join(items)
        + "</svg>"
    )


def render_line_chart(series_dict: dict[str, list], dates: list, width: int = 600, height: int = 200) -> str:
    if not series_dict:
        return ""
    colors = [CSS_PALETTE["blue"], CSS_PALETTE["green"], CSS_PALETTE["amber"], CSS_PALETTE["purple"]]
    pad = 12
    all_values = []
    for values in series_dict.values():
        all_values.extend([float(v) for v in values if v is not None and not pd.isna(v)])
    if len(all_values) < 2:
        return ""
    min_v = min(all_values)
    max_v = max(all_values)
    span = max(max_v - min_v, 1e-9)
    paths = []
    legend = []
    for idx, (label, values) in enumerate(series_dict.items()):
        clean = [float(v) if v is not None and not pd.isna(v) else np.nan for v in values]
        xs = np.linspace(pad, width - pad, len(clean))
        coords = []
        for x, v in zip(xs, clean):
            if np.isnan(v):
                continue
            y = height - pad - ((v - min_v) / span) * (height - 2 * pad)
            coords.append((x, y))
        if len(coords) < 2:
            continue
        points = " ".join(f"{x:.2f},{y:.2f}" for x, y in coords)
        color = colors[idx % len(colors)]
        paths.append(f"<polyline fill='none' stroke='{color}' stroke-width='2' points='{points}' />")
        legend.append(
            f"<text x='{pad + idx * 110}' y='12' fill='{color}' font-size='11'>{html_escape(label)}</text>"
        )
    return (
        f"<svg width='{width}' height='{height}' viewBox='0 0 {width} {height}' class='svg-chart'>"
        f"<rect x='0' y='0' width='{width}' height='{height}' fill='none' stroke='{CSS_PALETTE['border']}' stroke-width='1' />"
        + "".join(paths)
        + "".join(legend)
        + "</svg>"
    )


def render_drawdown_chart(drawdown_series: list[float], dates: list, width: int = 600, height: int = 160) -> str:
    clean = [float(v or 0.0) for v in drawdown_series]
    if len(clean) < 2:
        return ""
    min_v = min(clean)
    max_v = max(max(clean), 0.0)
    span = max(max_v - min_v, 1e-9)
    pad = 8
    xs = np.linspace(pad, width - pad, len(clean))
    points = []
    for x, v in zip(xs, clean):
        y = height - pad - ((v - min_v) / span) * (height - 2 * pad)
        points.append((x, y))
    baseline_y = height - pad - ((0.0 - min_v) / span) * (height - 2 * pad)
    path = " ".join(f"{x:.2f},{y:.2f}" for x, y in points)
    area = f"{pad},{baseline_y:.2f} " + path + f" {width - pad},{baseline_y:.2f}"
    return (
        f"<svg width='{width}' height='{height}' viewBox='0 0 {width} {height}' class='svg-chart'>"
        f"<polygon fill='{CSS_PALETTE['red']}' fill-opacity='0.18' points='{area}' />"
        f"<polyline fill='none' stroke='{CSS_PALETTE['red']}' stroke-width='2' points='{path}' />"
        f"<line x1='{pad}' y1='{baseline_y:.2f}' x2='{width - pad}' y2='{baseline_y:.2f}' stroke='{CSS_PALETTE['border']}' stroke-width='1' />"
        "</svg>"
    )


def render_heatmap(matrix: pd.DataFrame, width: int = 500, height: int = 300) -> str:
    if matrix is None or matrix.empty:
        return ""
    rows = list(matrix.index)
    cols = list(matrix.columns)
    cell_w = max((width - 120) / max(len(cols), 1), 24)
    cell_h = max((height - 40) / max(len(rows), 1), 18)
    values = matrix.astype(float).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    max_abs = max(values.abs().to_numpy().max(), 1e-9)
    items = []
    for c_idx, col in enumerate(cols):
        x = 110 + c_idx * cell_w
        items.append(
            f"<text x='{x + cell_w / 2:.1f}' y='14' text-anchor='middle' fill='{CSS_PALETTE['text_secondary']}' font-size='10'>{html_escape(col)}</text>"
        )
    for r_idx, row in enumerate(rows):
        y = 24 + r_idx * cell_h
        items.append(
            f"<text x='4' y='{y + cell_h * 0.72:.1f}' fill='{CSS_PALETTE['text_secondary']}' font-size='10'>{html_escape(row)}</text>"
        )
        for c_idx, col in enumerate(cols):
            x = 110 + c_idx * cell_w
            value = float(values.loc[row, col])
            intensity = min(abs(value) / max_abs, 1.0)
            fill = "#2ea043" if value >= 0 else "#f85149"
            items.append(
                f"<rect x='{x:.1f}' y='{y:.1f}' width='{cell_w - 2:.1f}' height='{cell_h - 2:.1f}' fill='{fill}' fill-opacity='{0.18 + 0.62 * intensity:.2f}' rx='2' />"
            )
    svg_w = int(110 + len(cols) * cell_w + 6)
    svg_h = int(24 + len(rows) * cell_h + 6)
    return f"<svg width='{svg_w}' height='{svg_h}' viewBox='0 0 {svg_w} {svg_h}' class='svg-chart'>{''.join(items)}</svg>"


@dataclass(slots=True)
class HTMLRenderer:
    """Render report sections into a single self-contained HTML file."""

    title: str

    def render_section(self, section: SectionResult) -> str:
        summary_html = f"<p class='section-summary'>{html_escape(section.summary)}</p>" if section.summary else ""
        warnings = section.warnings or []
        warnings_html = ""
        if warnings:
            warnings_html = "<div class='section-warnings'>" + "".join(
                f"<div class='warning-row'>{html_escape(item)}</div>" for item in warnings
            ) + "</div>"
        return (
            "<section class='section-card'>"
            "<div class='section-header'>"
            f"<h2>{html_escape(section.title)}</h2>"
            f"{render_badge(section.badge, section.status)}"
            "</div>"
            f"{summary_html}"
            f"{section.body_html}"
            f"{warnings_html}"
            "</section>"
        )

    def render_document(
        self,
        *,
        report_type: str,
        report_date: str,
        generated_at: datetime,
        sections: Sequence[SectionResult],
        subtitle: str | None = None,
    ) -> str:
        subtitle_html = f"<div class='subtitle'>{html_escape(subtitle)}</div>" if subtitle else ""
        sections_html = "".join(self.render_section(section) for section in sections)
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{html_escape(self.title)} - {html_escape(report_date)}</title>
  <style>
    :root {{
      color-scheme: dark;
    }}
    body {{
      margin: 0;
      background: {CSS_PALETTE['bg_primary']};
      color: {CSS_PALETTE['text_primary']};
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
      line-height: 1.5;
    }}
    .page {{
      max-width: 1280px;
      margin: 0 auto;
      padding: 28px 20px 48px;
    }}
    .hero {{
      border: 1px solid {CSS_PALETTE['border']};
      background: linear-gradient(135deg, {CSS_PALETTE['bg_secondary']} 0%, {CSS_PALETTE['bg_card']} 100%);
      padding: 20px 22px;
      margin-bottom: 18px;
      border-radius: 14px;
      box-shadow: 0 20px 40px rgba(0, 0, 0, 0.18);
    }}
    .eyebrow {{
      color: {CSS_PALETTE['blue']};
      text-transform: uppercase;
      letter-spacing: 0.12em;
      font-size: 11px;
      margin-bottom: 8px;
    }}
    h1 {{
      margin: 0;
      font-size: 28px;
      line-height: 1.2;
    }}
    .subtitle {{
      margin-top: 8px;
      color: {CSS_PALETTE['text_secondary']};
    }}
    .meta {{
      margin-top: 12px;
      color: {CSS_PALETTE['text_secondary']};
      font-size: 12px;
    }}
    .section-card {{
      border: 1px solid {CSS_PALETTE['border']};
      background: {CSS_PALETTE['bg_card']};
      border-radius: 14px;
      padding: 16px 18px 18px;
      margin: 0 0 16px;
    }}
    .section-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      margin-bottom: 8px;
    }}
    h2 {{
      margin: 0;
      font-size: 16px;
      letter-spacing: 0.03em;
      text-transform: uppercase;
    }}
    .section-summary {{
      margin: 0 0 12px;
      color: {CSS_PALETTE['text_secondary']};
    }}
    .badge {{
      display: inline-flex;
      align-items: center;
      padding: 3px 10px;
      border-radius: 999px;
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.04em;
      text-transform: uppercase;
      border: 1px solid transparent;
      white-space: nowrap;
    }}
    .badge-ok {{
      color: {CSS_PALETTE['green']};
      background: rgba(46, 160, 67, 0.12);
      border-color: rgba(46, 160, 67, 0.45);
    }}
    .badge-warn {{
      color: {CSS_PALETTE['amber']};
      background: rgba(210, 153, 34, 0.12);
      border-color: rgba(210, 153, 34, 0.45);
    }}
    .badge-critical {{
      color: {CSS_PALETTE['red']};
      background: rgba(248, 81, 73, 0.12);
      border-color: rgba(248, 81, 73, 0.45);
    }}
    .badge-muted {{
      color: {CSS_PALETTE['text_secondary']};
      background: rgba(139, 148, 158, 0.1);
      border-color: rgba(139, 148, 158, 0.35);
    }}
    .metric-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
      gap: 10px;
      margin-bottom: 14px;
    }}
    .metric-card {{
      padding: 10px 12px;
      border-radius: 10px;
      background: {CSS_PALETTE['bg_secondary']};
      border: 1px solid {CSS_PALETTE['border']};
    }}
    .metric-label {{
      color: {CSS_PALETTE['text_secondary']};
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: 4px;
    }}
    .metric-value {{
      font-size: 20px;
      font-weight: 700;
    }}
    .metric-meta, .kv-extra, .section-note {{
      color: {CSS_PALETTE['text_secondary']};
      font-size: 12px;
    }}
    .kv-grid {{
      display: grid;
      gap: 8px;
    }}
    .kv-row {{
      display: flex;
      justify-content: space-between;
      gap: 16px;
      padding: 8px 0;
      border-bottom: 1px solid rgba(48, 54, 61, 0.6);
    }}
    .kv-row:last-child {{
      border-bottom: 0;
    }}
    .kv-label {{
      color: {CSS_PALETTE['text_secondary']};
    }}
    .kv-value {{
      text-align: right;
      font-weight: 600;
    }}
    .table-wrap {{
      overflow-x: auto;
      border: 1px solid {CSS_PALETTE['border']};
      border-radius: 10px;
      background: {CSS_PALETTE['bg_secondary']};
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 12px;
    }}
    th, td {{
      padding: 9px 10px;
      border-bottom: 1px solid rgba(48, 54, 61, 0.65);
      text-align: left;
      vertical-align: top;
    }}
    th {{
      color: {CSS_PALETTE['text_secondary']};
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      background: rgba(13, 17, 23, 0.3);
    }}
    tr:last-child td {{
      border-bottom: 0;
    }}
    .chart-block {{
      margin-top: 12px;
      padding: 12px;
      border: 1px solid {CSS_PALETTE['border']};
      border-radius: 10px;
      background: {CSS_PALETTE['bg_secondary']};
    }}
    .chart-title {{
      margin-bottom: 8px;
      color: {CSS_PALETTE['text_secondary']};
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }}
    .svg-chart {{
      display: block;
      max-width: 100%;
      overflow: visible;
    }}
    .bullet-list {{
      margin: 0;
      padding-left: 18px;
    }}
    .bullet-list li {{
      margin: 5px 0;
    }}
    .split-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 12px;
    }}
    .warning-row {{
      padding-top: 8px;
      color: {CSS_PALETTE['amber']};
      font-size: 12px;
    }}
    .unavailable-block {{
      padding: 10px 12px;
      border-radius: 10px;
      border: 1px dashed {CSS_PALETTE['gray']};
      color: {CSS_PALETTE['text_secondary']};
      background: rgba(110, 118, 129, 0.08);
    }}
    p {{
      margin: 8px 0;
    }}
  </style>
</head>
<body>
  <main class="page">
    <header class="hero">
      <div class="eyebrow">{html_escape(report_type)}</div>
      <h1>{html_escape(self.title)}</h1>
      {subtitle_html}
      <div class="meta">Report date: {html_escape(report_date)} | Generated: {html_escape(generated_at.isoformat())}</div>
    </header>
    {sections_html}
  </main>
</body>
</html>"""
