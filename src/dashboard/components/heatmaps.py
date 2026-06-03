#!/usr/bin/env python3
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


def build_heatmap(pivot: pd.DataFrame, title: str, *, height: int = 420) -> go.Figure | None:
    if pivot is None or pivot.empty:
        return None
    fig = px.imshow(pivot, aspect="auto", color_continuous_scale="Tealgrn")
    fig.update_layout(template="plotly_dark", title=title, height=height)
    return fig
