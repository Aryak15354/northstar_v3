"""Bloomberg-style terminal theme primitives for the Northstar dashboard.

Centralises the terminal colour palette, a shared Plotly layout applied to
every chart (so all 9 tabs match), and small HTML helpers (delta-coloured
values, status LEDs, ticker tape). Keeping this in one place means the whole
dashboard's look is driven from a single file.
"""

from __future__ import annotations

from typing import Any, Optional

import pandas as pd

# ---- terminal palette (dark, high-contrast, amber/green/red on near-black) ----
TERM = {
    "bg": "#080a0d",          # app background (near-black)
    "panel": "#0e1116",       # card/panel background
    "panel_alt": "#12161d",   # alternating rows / headers
    "border": "#232a33",      # grid / hairline borders
    "grid": "#1a1f27",        # chart gridlines
    "text": "#c9d3df",        # primary text
    "muted": "#7d8899",       # secondary text
    "amber": "#ffb000",       # accent / headers (the Bloomberg amber)
    "cyan": "#38bdf8",        # links / secondary accent
    "up": "#26e07f",          # positive / long / bullish
    "down": "#ff4d4d",        # negative / short / bearish
    "flat": "#8b95a5",        # unchanged
    "warn": "#f5a623",
    "mono": "'JetBrains Mono','IBM Plex Mono',ui-monospace,SFMono-Regular,Menlo,monospace",
}


def _num(value: Any) -> float:
    try:
        n = pd.to_numeric(value, errors="coerce")
        return 0.0 if pd.isna(n) else float(n)
    except Exception:
        return 0.0


def delta_color(value: Any) -> str:
    v = _num(value)
    return TERM["up"] if v > 0 else TERM["down"] if v < 0 else TERM["flat"]


def value_html(value: str, *, color: Optional[str] = None, size: str = "1.1rem") -> str:
    c = color or TERM["text"]
    return f'<span style="font-family:{TERM["mono"]};font-weight:600;font-size:{size};color:{c};">{value}</span>'


def led(color: str, label: str = "") -> str:
    dot = (
        f'<span style="display:inline-block;width:8px;height:8px;border-radius:50%;'
        f'background:{color};box-shadow:0 0 8px {color};margin-right:6px;"></span>'
    )
    return f'{dot}<span style="color:{TERM["text"]};font-weight:600;">{label}</span>' if label else dot


def apply_terminal_layout(fig, *, height: Optional[int] = None):
    """Style a Plotly figure to the terminal aesthetic. Called on every chart."""
    if fig is None:
        return fig
    try:
        fig.update_layout(
            paper_bgcolor=TERM["panel"],
            plot_bgcolor=TERM["panel"],
            font=dict(family=TERM["mono"], size=11, color=TERM["text"]),
            title_font=dict(family=TERM["mono"], size=13, color=TERM["amber"]),
            legend=dict(font=dict(size=10, color=TERM["muted"]), bgcolor="rgba(0,0,0,0)"),
            margin=dict(l=48, r=18, t=40, b=36),
            colorway=[TERM["amber"], TERM["cyan"], TERM["up"], TERM["down"], "#a78bfa", "#f472b6", "#fbbf24"],
            hoverlabel=dict(font=dict(family=TERM["mono"], size=11), bgcolor=TERM["panel_alt"]),
        )
        fig.update_xaxes(gridcolor=TERM["grid"], zerolinecolor=TERM["border"],
                         linecolor=TERM["border"], tickfont=dict(family=TERM["mono"], size=10, color=TERM["muted"]))
        fig.update_yaxes(gridcolor=TERM["grid"], zerolinecolor=TERM["border"],
                         linecolor=TERM["border"], tickfont=dict(family=TERM["mono"], size=10, color=TERM["muted"]))
        # Setting title_font above creates a title object with no text; Plotly.js
        # renders that as the literal string "undefined". Guarantee a string.
        if fig.layout.title.text is None:
            fig.update_layout(title_text="")
        if height is not None:
            fig.update_layout(height=height)
    except Exception:
        # Never let styling break a chart.
        return fig
    return fig


def ticker_tape(items: list[tuple[str, str, float]]) -> str:
    """items: (label, value_str, change) -> a scrolling terminal ticker row."""
    cells = []
    for label, val, chg in items:
        c = delta_color(chg)
        arrow = "▲" if chg > 0 else "▼" if chg < 0 else "■"
        cells.append(
            f'<span class="ns-tick"><span class="ns-tick-l">{label}</span> '
            f'<span class="ns-tick-v">{val}</span> '
            f'<span style="color:{c};">{arrow} {abs(chg):.2f}%</span></span>'
        )
    inner = '<span class="ns-tick-sep">•</span>'.join(cells)
    # duplicate for seamless marquee
    return f'<div class="ns-ticker"><div class="ns-ticker-track">{inner}{"&nbsp;" * 8}{inner}</div></div>'
