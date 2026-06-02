#!/usr/bin/env python3
from __future__ import annotations

import plotly.graph_objects as go


def build_gauge(title: str, value: float, *, min_value: float = 0.0, max_value: float = 1.0, color: str = "#38bdf8") -> go.Figure:
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=value,
            title={"text": title},
            gauge={
                "axis": {"range": [min_value, max_value]},
                "bar": {"color": color},
                "bgcolor": "rgba(15, 23, 42, 0.35)",
            },
        )
    )
    fig.update_layout(template="plotly_dark", height=260, margin=dict(l=24, r=24, t=56, b=20))
    return fig
