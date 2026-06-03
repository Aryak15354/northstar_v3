#!/usr/bin/env python3
"""
Reusable Chart Components for Dashboard

All chart creation functions for the unified dashboard.
Each function returns a Plotly Figure object that can be rendered with st.plotly_chart().
"""

import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any
from datetime import datetime


# Theme colors
THEME = {
    'blue': '#3B82F6',
    'cyan': '#06B6D4',
    'green': '#10B981',
    'red': '#EF4444',
    'yellow': '#F59E0B',
    'purple': '#8B5CF6',
    'gray': '#6B7280',
    'dark_bg': '#1F2937',
    'light_bg': '#374151'
}


def create_line_chart(
    df: pd.DataFrame,
    x_col: str,
    y_cols: List[str],
    title: str,
    x_label: str = "",
    y_label: str = "",
    colors: Optional[List[str]] = None,
    height: int = 400
) -> go.Figure:
    """Create a multi-line chart"""
    fig = go.Figure()
    
    if colors is None:
        colors = [THEME['blue'], THEME['cyan'], THEME['green'], THEME['purple']]
    
    for i, y_col in enumerate(y_cols):
        if y_col in df.columns:
            fig.add_trace(go.Scatter(
                x=df[x_col],
                y=df[y_col],
                mode='lines',
                name=y_col,
                line=dict(color=colors[i % len(colors)], width=2)
            ))
    
    fig.update_layout(
        title=title,
        xaxis_title=x_label,
        yaxis_title=y_label,
        template="plotly_dark",
        height=height,
        hovermode='x unified',
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )
    
    return fig


def create_bar_chart(
    labels: List[str],
    values: List[float],
    title: str,
    x_label: str = "",
    y_label: str = "",
    color_by_value: bool = True,
    height: int = 400
) -> go.Figure:
    """Create a bar chart with optional color coding by value"""
    if color_by_value:
        colors = [THEME['green'] if v >= 0 else THEME['red'] for v in values]
    else:
        colors = [THEME['blue']] * len(values)
    
    fig = go.Figure(data=[
        go.Bar(
            x=labels,
            y=values,
            marker_color=colors,
            text=[f"{v:.2f}" for v in values],
            textposition='outside'
        )
    ])
    
    fig.update_layout(
        title=title,
        xaxis_title=x_label,
        yaxis_title=y_label,
        template="plotly_dark",
        height=height,
        showlegend=False
    )
    
    return fig


def create_pie_chart(
    labels: List[str],
    values: List[float],
    title: str,
    height: int = 400
) -> go.Figure:
    """Create a pie chart"""
    fig = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        hole=0.3,
        marker=dict(
            colors=[THEME['blue'], THEME['cyan'], THEME['green'], 
                   THEME['purple'], THEME['yellow'], THEME['red']]
        )
    )])
    
    fig.update_layout(
        title=title,
        template="plotly_dark",
        height=height,
        showlegend=True,
        legend=dict(
            orientation="v",
            yanchor="middle",
            y=0.5,
            xanchor="left",
            x=1.05
        )
    )
    
    return fig


def create_greeks_bar_chart(greeks: Dict[str, float], height: int = 400) -> go.Figure:
    """Create a bar chart for portfolio Greeks"""
    greek_names = ['Delta', 'Gamma', 'Vega', 'Theta']
    greek_values = [
        greeks.get('delta', 0.0),
        greeks.get('gamma', 0.0),
        greeks.get('vega', 0.0),
        greeks.get('theta', 0.0)
    ]
    
    colors = [THEME['green'] if v >= 0 else THEME['red'] for v in greek_values]
    
    fig = go.Figure(data=[
        go.Bar(
            x=greek_names,
            y=greek_values,
            marker_color=colors,
            text=[f"{v:.2f}" for v in greek_values],
            textposition='outside'
        )
    ])
    
    fig.update_layout(
        title="Portfolio Greeks Breakdown",
        xaxis_title="Greek",
        yaxis_title="Value",
        template="plotly_dark",
        height=height,
        showlegend=False
    )
    
    return fig


def create_greeks_evolution_chart(
    df: pd.DataFrame,
    time_col: str = 'timestamp',
    height: int = 400
) -> go.Figure:
    """Create a multi-axis chart for Greeks evolution over time"""
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    # Delta on primary axis
    if 'delta' in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df[time_col],
                y=df['delta'],
                mode='lines+markers',
                name='Delta',
                line=dict(color=THEME['blue'], width=2)
            ),
            secondary_y=False
        )
    
    # Gamma on secondary axis
    if 'gamma' in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df[time_col],
                y=df['gamma'],
                mode='lines+markers',
                name='Gamma',
                line=dict(color=THEME['yellow'], width=2)
            ),
            secondary_y=True
        )
    
    # Vega on primary axis
    if 'vega' in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df[time_col],
                y=df['vega'],
                mode='lines+markers',
                name='Vega',
                line=dict(color=THEME['purple'], width=2)
            ),
            secondary_y=False
        )
    
    # Theta on secondary axis
    if 'theta' in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df[time_col],
                y=df['theta'],
                mode='lines+markers',
                name='Theta',
                line=dict(color=THEME['red'], width=2)
            ),
            secondary_y=True
        )
    
    fig.update_layout(
        title="Greeks Evolution Over Time",
        template="plotly_dark",
        height=height,
        hovermode='x unified'
    )
    
    fig.update_xaxes(title_text="Time")
    fig.update_yaxes(title_text="Delta / Vega", secondary_y=False)
    fig.update_yaxes(title_text="Gamma / Theta", secondary_y=True)
    
    return fig


def create_nav_chart(
    df: pd.DataFrame,
    date_col: str = 'date',
    nav_col: str = 'nav',
    benchmark_col: Optional[str] = None,
    title: str = "NAV History",
    height: int = 400
) -> go.Figure:
    """Create NAV time series chart with optional benchmark"""
    fig = go.Figure()
    
    # Portfolio NAV
    fig.add_trace(go.Scatter(
        x=df[date_col],
        y=df[nav_col],
        mode='lines',
        name='Portfolio NAV',
        line=dict(color=THEME['blue'], width=2)
    ))
    
    # Benchmark if provided
    if benchmark_col and benchmark_col in df.columns:
        fig.add_trace(go.Scatter(
            x=df[date_col],
            y=df[benchmark_col],
            mode='lines',
            name='Benchmark',
            line=dict(color=THEME['cyan'], width=2, dash='dash')
        ))
    
    fig.update_layout(
        title=title,
        xaxis_title="Date",
        yaxis_title="NAV (₹)",
        template="plotly_dark",
        height=height,
        hovermode='x unified'
    )
    
    return fig


def create_returns_distribution(
    returns: pd.Series,
    title: str = "Returns Distribution",
    height: int = 400
) -> go.Figure:
    """Create histogram of returns distribution"""
    fig = go.Figure(data=[go.Histogram(
        x=returns,
        nbinsx=50,
        marker_color=THEME['blue'],
        opacity=0.7
    )])
    
    # Add mean line
    mean_return = returns.mean()
    fig.add_vline(
        x=mean_return,
        line_dash="dash",
        line_color=THEME['green'],
        annotation_text=f"Mean: {mean_return:.2%}"
    )
    
    fig.update_layout(
        title=title,
        xaxis_title="Return",
        yaxis_title="Frequency",
        template="plotly_dark",
        height=height
    )
    
    return fig


def create_drawdown_chart(
    df: pd.DataFrame,
    date_col: str = 'date',
    equity_col: str = 'equity',
    title: str = "Drawdown Analysis",
    height: int = 400
) -> go.Figure:
    """Create drawdown chart"""
    # Calculate drawdown
    cummax = df[equity_col].cummax()
    drawdown = (df[equity_col] - cummax) / cummax * 100
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=df[date_col],
        y=drawdown,
        mode='lines',
        name='Drawdown',
        fill='tozeroy',
        line=dict(color=THEME['red'], width=2)
    ))
    
    fig.update_layout(
        title=title,
        xaxis_title="Date",
        yaxis_title="Drawdown (%)",
        template="plotly_dark",
        height=height,
        hovermode='x unified'
    )
    
    return fig


def create_sector_exposure_pie(
    sector_exposure: Dict[str, float],
    title: str = "Sector Exposure",
    height: int = 400
) -> go.Figure:
    """Create pie chart for sector exposure"""
    labels = list(sector_exposure.keys())
    values = list(sector_exposure.values())
    
    return create_pie_chart(labels, values, title, height)


def create_strategy_attribution_chart(
    df: pd.DataFrame,
    date_col: str = 'date',
    strategy_cols: Optional[List[str]] = None,
    title: str = "Strategy Attribution",
    height: int = 400
) -> go.Figure:
    """Create stacked bar chart for strategy attribution"""
    if strategy_cols is None:
        # Auto-detect strategy columns
        strategy_cols = [col for col in df.columns if col not in [date_col]]
    
    fig = go.Figure()
    
    colors = [THEME['blue'], THEME['cyan'], THEME['green'], 
             THEME['purple'], THEME['yellow'], THEME['red']]
    
    for i, col in enumerate(strategy_cols):
        if col in df.columns:
            fig.add_trace(go.Bar(
                x=df[date_col],
                y=df[col],
                name=col,
                marker_color=colors[i % len(colors)]
            ))
    
    fig.update_layout(
        title=title,
        xaxis_title="Date",
        yaxis_title="Contribution",
        barmode='stack',
        template="plotly_dark",
        height=height,
        hovermode='x unified'
    )
    
    return fig


def create_heatmap(
    df: pd.DataFrame,
    title: str = "Heatmap",
    height: int = 400,
    colorscale: str = 'RdYlGn'
) -> go.Figure:
    """Create a heatmap from DataFrame"""
    fig = go.Figure(data=go.Heatmap(
        z=df.values,
        x=df.columns,
        y=df.index,
        colorscale=colorscale,
        hoverongaps=False
    ))
    
    fig.update_layout(
        title=title,
        template="plotly_dark",
        height=height
    )
    
    return fig


def create_gauge_chart(
    value: float,
    title: str,
    min_val: float = 0,
    max_val: float = 100,
    threshold_low: float = 30,
    threshold_high: float = 70,
    height: int = 300
) -> go.Figure:
    """Create a gauge chart"""
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=value,
        title={'text': title},
        gauge={
            'axis': {'range': [min_val, max_val]},
            'bar': {'color': THEME['blue']},
            'steps': [
                {'range': [min_val, threshold_low], 'color': THEME['red']},
                {'range': [threshold_low, threshold_high], 'color': THEME['yellow']},
                {'range': [threshold_high, max_val], 'color': THEME['green']}
            ],
            'threshold': {
                'line': {'color': "white", 'width': 4},
                'thickness': 0.75,
                'value': value
            }
        }
    ))
    
    fig.update_layout(
        template="plotly_dark",
        height=height
    )
    
    return fig


def create_waterfall_chart(
    labels: List[str],
    values: List[float],
    title: str = "Waterfall Chart",
    height: int = 400
) -> go.Figure:
    """Create a waterfall chart for P&L breakdown"""
    fig = go.Figure(go.Waterfall(
        name="P&L",
        orientation="v",
        measure=["relative"] * (len(labels) - 1) + ["total"],
        x=labels,
        y=values,
        connector={"line": {"color": THEME['gray']}},
        increasing={"marker": {"color": THEME['green']}},
        decreasing={"marker": {"color": THEME['red']}},
        totals={"marker": {"color": THEME['blue']}}
    ))
    
    fig.update_layout(
        title=title,
        template="plotly_dark",
        height=height,
        showlegend=False
    )
    
    return fig


def create_regime_timeline(
    df: pd.DataFrame,
    date_col: str = 'date',
    regime_col: str = 'regime',
    title: str = "Regime Timeline",
    height: int = 300
) -> go.Figure:
    """Create a timeline showing regime changes"""
    # Map regimes to numeric values for visualization
    regime_map = {
        'BULL': 3,
        'NEUTRAL': 2,
        'BEAR': 1,
        'CRISIS': 0,
        'UNKNOWN': -1
    }
    
    df = df.copy()
    df['regime_numeric'] = df[regime_col].map(regime_map).fillna(-1)
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=df[date_col],
        y=df['regime_numeric'],
        mode='lines+markers',
        name='Regime',
        line=dict(color=THEME['blue'], width=3),
        marker=dict(size=8)
    ))
    
    fig.update_layout(
        title=title,
        xaxis_title="Date",
        yaxis_title="Regime",
        yaxis=dict(
            tickmode='array',
            tickvals=[0, 1, 2, 3],
            ticktext=['CRISIS', 'BEAR', 'NEUTRAL', 'BULL']
        ),
        template="plotly_dark",
        height=height,
        hovermode='x unified'
    )
    
    return fig


def create_intraday_pnl_chart(
    df: pd.DataFrame,
    time_col: str = 'timestamp',
    pnl_col: str = 'pnl',
    title: str = "Intraday P&L",
    height: int = 400
) -> go.Figure:
    """Create intraday P&L line chart"""
    fig = go.Figure()
    
    # Cumulative P&L
    fig.add_trace(go.Scatter(
        x=df[time_col],
        y=df[pnl_col].cumsum(),
        mode='lines',
        name='Cumulative P&L',
        line=dict(color=THEME['blue'], width=2),
        fill='tozeroy'
    ))
    
    fig.update_layout(
        title=title,
        xaxis_title="Time",
        yaxis_title="P&L (₹)",
        template="plotly_dark",
        height=height,
        hovermode='x unified'
    )
    
    return fig
