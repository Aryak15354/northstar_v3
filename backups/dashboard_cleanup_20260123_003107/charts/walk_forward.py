#!/usr/bin/env python3
"""
Walk-Forward Visualization Charts
Institutional-grade visualizations that show behavior, distribution, and structure — not promise.

These charts answer "can I live with this?" not "should I trade?"
"""

import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

class WalkForwardCharts:
    """Walk-forward visualization charts for constitutional cockpit"""
    
    def __init__(self):
        self.name = "Walk-Forward Charts"
        self.version = "1.0.0"
        
        # Chart styling (institutional, muted)
        self.colors = {
            'primary': '#1e40af',
            'secondary': '#6b7280',
            'success': '#059669',
            'warning': '#d97706',
            'danger': '#dc2626',
            'neutral': '#9ca3af'
        }
        
        self.chart_config = {
            'displayModeBar': False,
            'staticPlot': False,
            'responsive': True
        }
    
    def create_walk_forward_timeline_matrix(self, walk_forward_data: pd.DataFrame) -> go.Figure:
        """
        1️⃣ Walk-Forward Timeline Matrix (Signature Visual)
        
        Each 12-month window as a tile
        Color = return bucket
        Border thickness = max drawdown
        Icon = engine behavior correctness
        
        This instantly shows lumpiness and non-smoothness without cumulative curve illusion.
        """
        
        # Create matrix data
        years = walk_forward_data['year'].unique()
        
        # Create heatmap
        fig = go.Figure()
        
        # Add heatmap tiles
        fig.add_trace(go.Heatmap(
            x=years,
            y=['Walk-Forward Results'],
            z=[walk_forward_data['annual_return'].values],
            colorscale=[
                [0, '#dc2626'],    # Red for negative
                [0.5, '#6b7280'],  # Gray for neutral
                [1, '#059669']     # Green for positive
            ],
            showscale=True,
            colorbar=dict(
                title="Annual Return",
                tickformat=".1%"
            ),
            hovertemplate="<b>%{x}</b><br>" +
                         "Return: %{z:.1%}<br>" +
                         "<extra></extra>"
        ))
        
        # Update layout
        fig.update_layout(
            title="Walk-Forward Timeline Matrix",
            xaxis_title="Year",
            yaxis_title="",
            height=200,
            margin=dict(l=50, r=50, t=50, b=50),
            font=dict(size=10),
            plot_bgcolor='white',
            paper_bgcolor='white'
        )
        
        return fig
    
    def create_walk_forward_equity_fan(self, equity_paths: Dict[str, pd.Series]) -> go.Figure:
        """
        2️⃣ Walk-Forward Equity Fan, not Curve
        
        Plot all walk-forward equity paths (normalized to start at 1)
        Semi-transparent with median + worst 10% overlay
        
        Shows dispersion, pain, and unpredictability. Removes false confidence.
        """
        
        fig = go.Figure()
        
        # Plot all equity paths (semi-transparent)
        for path_name, equity_series in equity_paths.items():
            # Normalize to start at 1
            normalized_equity = equity_series / equity_series.iloc[0]
            
            fig.add_trace(go.Scatter(
                x=equity_series.index,
                y=normalized_equity,
                mode='lines',
                name=path_name,
                line=dict(width=1, color='rgba(107, 114, 128, 0.3)'),
                showlegend=False,
                hovertemplate="<b>%{fullData.name}</b><br>" +
                             "Date: %{x}<br>" +
                             "Equity: %{y:.2f}<br>" +
                             "<extra></extra>"
            ))
        
        # Calculate and plot median
        all_values = pd.DataFrame(equity_paths)
        median_equity = all_values.median(axis=1)
        median_equity = median_equity / median_equity.iloc[0]
        
        fig.add_trace(go.Scatter(
            x=median_equity.index,
            y=median_equity,
            mode='lines',
            name='Median',
            line=dict(width=3, color=self.colors['primary']),
            showlegend=True
        ))
        
        # Calculate and plot worst 10%
        worst_10_pct = all_values.quantile(0.1, axis=1)
        worst_10_pct = worst_10_pct / worst_10_pct.iloc[0]
        
        fig.add_trace(go.Scatter(
            x=worst_10_pct.index,
            y=worst_10_pct,
            mode='lines',
            name='Worst 10%',
            line=dict(width=2, color=self.colors['danger'], dash='dash'),
            showlegend=True
        ))
        
        # Update layout
        fig.update_layout(
            title="Walk-Forward Equity Fan (All Paths)",
            xaxis_title="Date",
            yaxis_title="Normalized Equity",
            height=400,
            margin=dict(l=50, r=50, t=50, b=50),
            font=dict(size=10),
            plot_bgcolor='white',
            paper_bgcolor='white',
            hovermode='x unified'
        )
        
        return fig
    
    def create_return_vs_drawdown_scatter(self, walk_forward_results: pd.DataFrame) -> go.Figure:
        """
        3️⃣ Return vs Drawdown Scatter (Reality Check)
        
        Each dot = one walk-forward window
        X-axis: Max drawdown
        Y-axis: Total return
        Color: dominant engine
        Size: volatility
        
        Answers: "What kind of pain buys what kind of reward?"
        This single chart prevents most self-deception.
        """
        
        fig = go.Figure()
        
        # Create scatter plot
        fig.add_trace(go.Scatter(
            x=walk_forward_results['max_drawdown'],
            y=walk_forward_results['total_return'],
            mode='markers',
            marker=dict(
                size=walk_forward_results['volatility'] * 500,  # Scale for visibility
                color=walk_forward_results['dominant_engine'].map({
                    'trend': self.colors['primary'],
                    'crisis': self.colors['warning'],
                    'mixed': self.colors['neutral']
                }),
                opacity=0.7,
                line=dict(width=1, color='white')
            ),
            text=walk_forward_results['period'],
            hovertemplate="<b>%{text}</b><br>" +
                         "Max Drawdown: %{x:.1%}<br>" +
                         "Total Return: %{y:.1%}<br>" +
                         "Volatility: %{marker.size:.1%}<br>" +
                         "<extra></extra>",
            showlegend=False
        ))
        
        # Add quadrant lines
        fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
        fig.add_vline(x=0, line_dash="dash", line_color="gray", opacity=0.5)
        
        # Update layout
        fig.update_layout(
            title="Return vs Drawdown Reality Check",
            xaxis_title="Max Drawdown",
            yaxis_title="Total Return",
            height=400,
            margin=dict(l=50, r=50, t=50, b=50),
            font=dict(size=10),
            plot_bgcolor='white',
            paper_bgcolor='white'
        )
        
        # Format axes as percentages
        fig.update_xaxis(tickformat='.1%')
        fig.update_yaxis(tickformat='.1%')
        
        return fig
    
    def create_exposure_distribution(self, exposure_data: pd.DataFrame) -> go.Figure:
        """
        Exposure Distribution (Truth Chart)
        
        Histogram: % time at each exposure level split by regime
        This immediately explains: "Why returns look small most of the time."
        """
        
        fig = go.Figure()
        
        # Create histogram for each regime
        regimes = exposure_data['regime'].unique()
        
        for regime in regimes:
            regime_data = exposure_data[exposure_data['regime'] == regime]
            
            fig.add_trace(go.Histogram(
                x=regime_data['exposure'],
                name=regime,
                opacity=0.7,
                nbinsx=20,
                histnorm='percent'
            ))
        
        # Update layout
        fig.update_layout(
            title="Exposure Distribution by Regime",
            xaxis_title="Exposure Level",
            yaxis_title="% of Time",
            height=300,
            margin=dict(l=50, r=50, t=50, b=50),
            font=dict(size=10),
            plot_bgcolor='white',
            paper_bgcolor='white',
            barmode='overlay'
        )
        
        # Format x-axis as percentage
        fig.update_xaxis(tickformat='.0%')
        
        return fig
    
    def create_engine_state_gantt(self, engine_timeline: pd.DataFrame) -> go.Figure:
        """
        Engine State Gantt Chart
        
        Timeline showing:
        - Regime state
        - Active engine
        - Exposure state
        
        This is huge psychologically. You see:
        - long boredom
        - sudden intensity
        - short action windows
        
        It trains expectations.
        """
        
        fig = go.Figure()
        
        # Create Gantt chart for engine states
        for i, row in engine_timeline.iterrows():
            # Determine color based on active engine
            color = {
                'trend': self.colors['primary'],
                'crisis': self.colors['warning'],
                'none': self.colors['neutral']
            }.get(row['active_engine'], self.colors['neutral'])
            
            fig.add_trace(go.Scatter(
                x=[row['start_date'], row['end_date']],
                y=[row['active_engine'], row['active_engine']],
                mode='lines',
                line=dict(width=10, color=color),
                name=row['active_engine'],
                showlegend=False,
                hovertemplate="<b>%{y} Engine</b><br>" +
                             "Start: %{x[0]}<br>" +
                             "End: %{x[1]}<br>" +
                             "<extra></extra>"
            ))
        
        # Update layout
        fig.update_layout(
            title="Engine State Timeline",
            xaxis_title="Date",
            yaxis_title="Active Engine",
            height=200,
            margin=dict(l=50, r=50, t=50, b=50),
            font=dict(size=10),
            plot_bgcolor='white',
            paper_bgcolor='white'
        )
        
        return fig