"""
Dashboard Chart Library - 74 Production Charts

All charts use ONLY real data from the data contract.
No mocks, no synthetic data.
"""

import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from typing import Optional, Dict, Any
from pathlib import Path

# Theme
THEME = {
    "bg": "#0b1220",
    "panel": "#0f172a",
    "text": "#e5e7eb",
    "blue": "#3B82F6",
    "green": "#22c55e",
    "red": "#ef4444",
    "amber": "#f59e0b",
    "cyan": "#06b6d4",
}


def apply_theme(fig: go.Figure, height: int = 400) -> go.Figure:
    """Apply consistent dark theme to all charts"""
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=THEME["bg"],
        plot_bgcolor=THEME["panel"],
        font=dict(color=THEME["text"], size=12),
        height=height,
        margin=dict(l=60, r=40, t=60, b=60),
        hovermode='x unified',
    )
    return fig


# ============================================================================
# PERFORMANCE TAB CHARTS (15 charts)
# ============================================================================

def chart_capital_curve(df: pd.DataFrame) -> Optional[go.Figure]:
    """1. Total Capital Curve (log scale)"""
    if df is None or df.empty or 'date' not in df.columns:
        return None
    
    fig = go.Figure()
    
    if 'equity' in df.columns:
        fig.add_trace(go.Scatter(
            x=df['date'],
            y=df['equity'],
            mode='lines',
            name='Capital',
            line=dict(color=THEME["blue"], width=2),
        ))
    
    fig.update_yaxes(type="log", title="Capital (₹)")
    fig.update_xaxes(title="Date")
    fig.update_layout(title="Total Capital Curve (Log Scale)")
    
    return apply_theme(fig, 450)


def chart_rolling_sharpe(df: pd.DataFrame, window: int = 252) -> Optional[go.Figure]:
    """2. Rolling Sharpe (12M)"""
    if df is None or df.empty or 'date' not in df.columns:
        return None
    
    fig = go.Figure()
    
    if 'rolling_sharpe' in df.columns:
        fig.add_trace(go.Scatter(
            x=df['date'],
            y=df['rolling_sharpe'],
            mode='lines',
            name=f'Sharpe ({window}D)',
            line=dict(color=THEME["green"], width=2),
        ))
    
    fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
    fig.update_xaxes(title="Date")
    fig.update_yaxes(title="Sharpe Ratio")
    fig.update_layout(title=f"Rolling Sharpe Ratio ({window} days)")
    
    return apply_theme(fig, 400)


def chart_max_drawdown(df: pd.DataFrame) -> Optional[go.Figure]:
    """3. Rolling Max Drawdown"""
    if df is None or df.empty or 'date' not in df.columns:
        return None
    
    fig = go.Figure()
    
    if 'drawdown' in df.columns:
        fig.add_trace(go.Scatter(
            x=df['date'],
            y=df['drawdown'] * 100,  # Convert to percentage
            mode='lines',
            name='Drawdown',
            line=dict(color=THEME["red"], width=2),
            fill='tozeroy',
            fillcolor='rgba(239, 68, 68, 0.2)',
        ))
    
    fig.update_xaxes(title="Date")
    fig.update_yaxes(title="Drawdown (%)")
    fig.update_layout(title="Rolling Maximum Drawdown")
    
    return apply_theme(fig, 400)


def chart_survival_probability(df: pd.DataFrame) -> Optional[go.Figure]:
    """4. Survival Probability Estimate"""
    if df is None or df.empty:
        return None
    
    fig = go.Figure()
    
    if 'survival_probability' in df.columns and 'date' in df.columns:
        fig.add_trace(go.Scatter(
            x=df['date'],
            y=df['survival_probability'],
            mode='lines',
            name='Survival Probability',
            line=dict(color=THEME["cyan"], width=2),
        ))
    
    fig.update_yaxes(range=[0, 1], title="Probability")
    fig.update_xaxes(title="Date")
    fig.update_layout(title="Survival Probability Estimate")
    
    return apply_theme(fig, 400)


def chart_daily_returns_dist(df: pd.DataFrame) -> Optional[go.Figure]:
    """5. Daily Returns Distribution"""
    if df is None or df.empty:
        return None
    
    returns = None
    if 'daily_return' in df.columns:
        returns = df['daily_return'].dropna()
    elif 'equity' in df.columns:
        returns = df['equity'].pct_change().dropna()
    
    if returns is None or len(returns) < 10:
        return None
    
    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=returns * 100,
        nbinsx=50,
        name='Returns',
        marker_color=THEME["blue"],
    ))
    
    fig.update_xaxes(title="Daily Return (%)")
    fig.update_yaxes(title="Frequency")
    fig.update_layout(title="Daily Returns Distribution")
    
    return apply_theme(fig, 400)


def chart_monthly_returns_heatmap(df: pd.DataFrame) -> Optional[go.Figure]:
    """6. Monthly Returns Heatmap"""
    if df is None or df.empty or 'date' not in df.columns:
        return None
    
    df = df.copy()
    df['date'] = pd.to_datetime(df['date'])
    
    # Calculate monthly returns from NAV
    if 'nav' in df.columns:
        df = df.sort_values('date')
        df['year_month'] = df['date'].dt.to_period('M')
        monthly = df.groupby('year_month')['nav'].last().pct_change()
        
        if monthly.empty or len(monthly) < 2:
            return None
        
        monthly_df = monthly.reset_index()
        monthly_df['year'] = monthly_df['year_month'].dt.year
        monthly_df['month'] = monthly_df['year_month'].dt.month
        
        pivot = monthly_df.pivot_table(
            values='nav',
            index='year',
            columns='month',
            aggfunc='first'
        )
    elif 'monthly_return' in df.columns:
        df['year'] = df['date'].dt.year
        df['month'] = df['date'].dt.month
        pivot = df.pivot_table(
            values='monthly_return',
            index='year',
            columns='month',
            aggfunc='first'
        )
    else:
        return None
    
    if pivot.empty:
        return None
    
    fig = go.Figure(data=go.Heatmap(
        z=pivot.values * 100,
        x=['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
           'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
        y=pivot.index,
        colorscale='RdYlGn',
        zmid=0,
        text=np.round(pivot.values * 100, 2),
        texttemplate='%{text}%',
        textfont={"size": 10},
    ))
    
    fig.update_layout(title="Monthly Returns Heatmap (%)")
    
    return apply_theme(fig, 500)


def chart_cumulative_vs_benchmark(pnl_df: pd.DataFrame, bench_df: pd.DataFrame) -> Optional[go.Figure]:
    """7. Cumulative Returns vs Benchmark"""
    if pnl_df is None or pnl_df.empty:
        return None
    
    fig = go.Figure()
    
    # Portfolio cumulative returns
    if 'equity' in pnl_df.columns and 'date' in pnl_df.columns:
        pnl_df = pnl_df.sort_values('date')
        cum_ret = (pnl_df['equity'] / pnl_df['equity'].iloc[0] - 1) * 100
        fig.add_trace(go.Scatter(
            x=pnl_df['date'],
            y=cum_ret,
            mode='lines',
            name='Portfolio',
            line=dict(color=THEME["blue"], width=2),
        ))
    
    # Benchmark cumulative returns
    if bench_df is not None and not bench_df.empty:
        if 'close' in bench_df.columns and 'date' in bench_df.columns:
            bench_df = bench_df.sort_values('date')
            bench_cum = (bench_df['close'] / bench_df['close'].iloc[0] - 1) * 100
            fig.add_trace(go.Scatter(
                x=bench_df['date'],
                y=bench_cum,
                mode='lines',
                name='Nifty 50',
                line=dict(color=THEME["amber"], width=2, dash='dash'),
            ))
    
    fig.update_xaxes(title="Date")
    fig.update_yaxes(title="Cumulative Return (%)")
    fig.update_layout(title="Cumulative Returns vs Benchmark")
    
    return apply_theme(fig, 450)


def chart_rolling_volatility(df: pd.DataFrame, window: int = 30) -> Optional[go.Figure]:
    """8. Rolling Volatility"""
    if df is None or df.empty or 'date' not in df.columns:
        return None
    
    returns = None
    if 'daily_return' in df.columns:
        returns = df['daily_return']
    elif 'equity' in df.columns:
        returns = df['equity'].pct_change()
    
    if returns is None:
        return None
    
    rolling_vol = returns.rolling(window).std() * np.sqrt(252) * 100
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df['date'],
        y=rolling_vol,
        mode='lines',
        name=f'Volatility ({window}D)',
        line=dict(color=THEME["red"], width=2),
    ))
    
    fig.update_xaxes(title="Date")
    fig.update_yaxes(title="Annualized Volatility (%)")
    fig.update_layout(title=f"Rolling Volatility ({window} days)")
    
    return apply_theme(fig, 400)


def chart_win_rate(df: pd.DataFrame, window: int = 30) -> Optional[go.Figure]:
    """9. Win Rate Over Time"""
    if df is None or df.empty:
        return None
    
    returns = None
    if 'daily_return' in df.columns:
        returns = df['daily_return']
    elif 'equity' in df.columns:
        returns = df['equity'].pct_change()
    
    if returns is None:
        return None
    
    wins = (returns > 0).astype(int)
    win_rate = wins.rolling(window).mean() * 100
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df['date'] if 'date' in df.columns else range(len(win_rate)),
        y=win_rate,
        mode='lines',
        name='Win Rate',
        line=dict(color=THEME["green"], width=2),
    ))
    
    fig.add_hline(y=50, line_dash="dash", line_color="gray", opacity=0.5)
    fig.update_xaxes(title="Date")
    fig.update_yaxes(title="Win Rate (%)", range=[0, 100])
    fig.update_layout(title=f"Win Rate Over Time ({window}D Rolling)")
    
    return apply_theme(fig, 400)


def chart_profit_factor(df: pd.DataFrame, window: int = 60) -> Optional[go.Figure]:
    """10. Profit Factor"""
    if df is None or df.empty:
        return None
    
    returns = None
    if 'daily_return' in df.columns:
        returns = df['daily_return']
    elif 'equity' in df.columns:
        returns = df['equity'].pct_change()
    
    if returns is None:
        return None
    
    def calc_profit_factor(r):
        wins = r[r > 0].sum()
        losses = abs(r[r < 0].sum())
        return wins / losses if losses != 0 else np.nan
    
    pf = returns.rolling(window).apply(calc_profit_factor, raw=False)
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df['date'] if 'date' in df.columns else range(len(pf)),
        y=pf,
        mode='lines',
        name='Profit Factor',
        line=dict(color=THEME["cyan"], width=2),
    ))
    
    fig.add_hline(y=1, line_dash="dash", line_color="gray", opacity=0.5)
    fig.update_xaxes(title="Date")
    fig.update_yaxes(title="Profit Factor")
    fig.update_layout(title=f"Profit Factor ({window}D Rolling)")
    
    return apply_theme(fig, 400)


def chart_risk_adjusted_returns(df: pd.DataFrame) -> Optional[go.Figure]:
    """11. Risk-Adjusted Returns (Sharpe, Sortino, Calmar)"""
    if df is None or df.empty:
        return None
    
    # Handle both 'daily_return' and 'return' column names
    return_col = 'daily_return' if 'daily_return' in df.columns else 'return' if 'return' in df.columns else None
    if return_col is None:
        return None
    
    returns = df[return_col].dropna()
    
    if len(returns) < 30:
        return None
    
    # Calculate metrics
    mean_return = returns.mean()
    std_return = returns.std()
    
    # Sharpe Ratio (annualized)
    sharpe = (mean_return / std_return) * np.sqrt(252) if std_return > 0 else 0
    
    # Sortino Ratio (annualized, downside deviation)
    downside_returns = returns[returns < 0]
    downside_std = downside_returns.std() if len(downside_returns) > 0 else std_return
    sortino = (mean_return / downside_std) * np.sqrt(252) if downside_std > 0 else 0
    
    # Calmar Ratio (return / max drawdown)
    if 'nav' in df.columns:
        nav = df['nav'].values
        cummax = np.maximum.accumulate(nav)
        drawdown = (nav - cummax) / cummax
        max_dd = abs(drawdown.min()) if len(drawdown) > 0 else 0.01
        annual_return = mean_return * 252
        calmar = annual_return / max_dd if max_dd > 0 else 0
    else:
        calmar = 0
    
    metrics = ['Sharpe', 'Sortino', 'Calmar']
    values = [sharpe, sortino, calmar]
    
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=metrics,
        y=values,
        marker_color=[THEME["green"] if v > 0 else THEME["red"] for v in values],
        text=[f"{v:.2f}" for v in values],
        textposition='auto'
    ))
    
    fig.add_hline(y=0, line_dash="dash", line_color="gray")
    fig.update_xaxes(title="Metric")
    fig.update_yaxes(title="Ratio")
    fig.update_layout(title="Risk-Adjusted Return Metrics")
    
    return apply_theme(fig, 400)

def chart_drawdown_duration(df: pd.DataFrame) -> Optional[go.Figure]:
    """12. Drawdown Duration Analysis"""
    if df is None or df.empty:
        return None
    
    # Use nav or equity column
    if 'nav' in df.columns:
        equity = df['nav']
    elif 'equity' in df.columns:
        equity = df['equity']
    else:
        return None
    
    # Calculate drawdown
    running_max = equity.expanding().max()
    drawdown = (equity - running_max) / running_max
    
    # Find drawdown periods
    in_drawdown = drawdown < 0
    drawdown_periods = []
    start = None
    
    for i, is_dd in enumerate(in_drawdown):
        if is_dd and start is None:
            start = i
        elif not is_dd and start is not None:
            duration = i - start
            depth = drawdown.iloc[start:i].min()
            drawdown_periods.append({'duration': duration, 'depth': depth * 100})
            start = None
    
    if not drawdown_periods:
        return None
    
    dd_df = pd.DataFrame(drawdown_periods)
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dd_df['duration'],
        y=dd_df['depth'],
        mode='markers',
        marker=dict(
            size=10,
            color=dd_df['depth'],
            colorscale='Reds',
            showscale=True,
            colorbar=dict(title="Depth (%)"),
        ),
        text=[f"Duration: {d}d<br>Depth: {dep:.1f}%" 
              for d, dep in zip(dd_df['duration'], dd_df['depth'])],
        hovertemplate='%{text}<extra></extra>',
    ))
    
    fig.update_xaxes(title="Duration (days)")
    fig.update_yaxes(title="Depth (%)")
    fig.update_layout(title="Drawdown Duration vs Depth")
    
    return apply_theme(fig, 450)


def chart_nav_history(df: pd.DataFrame) -> Optional[go.Figure]:
    """13. NAV History"""
    if df is None or df.empty:
        return None
    
    fig = go.Figure()
    
    if 'nav' in df.columns and 'date' in df.columns:
        fig.add_trace(go.Scatter(
            x=df['date'],
            y=df['nav'],
            mode='lines',
            name='NAV',
            line=dict(color=THEME["blue"], width=2),
        ))
    
    fig.update_xaxes(title="Date")
    fig.update_yaxes(title="NAV")
    fig.update_layout(title="Net Asset Value History")
    
    return apply_theme(fig, 400)


def chart_underwater_plot(df: pd.DataFrame) -> Optional[go.Figure]:
    """14. Underwater Plot (Drawdown from Peak)"""
    if df is None or df.empty:
        return None
    
    # Use nav or equity column
    if 'nav' in df.columns:
        equity = df['nav']
    elif 'equity' in df.columns:
        equity = df['equity']
    else:
        return None
    
    running_max = equity.expanding().max()
    drawdown = (equity - running_max) / running_max * 100
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df['date'] if 'date' in df.columns else range(len(drawdown)),
        y=drawdown,
        mode='lines',
        name='Drawdown',
        line=dict(color=THEME["red"], width=1),
        fill='tozeroy',
        fillcolor='rgba(239, 68, 68, 0.3)',
    ))
    
    fig.update_xaxes(title="Date")
    fig.update_yaxes(title="Drawdown from Peak (%)")
    fig.update_layout(title="Underwater Plot")
    
    return apply_theme(fig, 400)


def chart_returns_quantiles(df: pd.DataFrame) -> Optional[go.Figure]:
    """15. Returns Quantile Analysis"""
    if df is None or df.empty:
        return None
    
    returns = None
    if 'daily_return' in df.columns:
        returns = df['daily_return'].dropna()
    elif 'equity' in df.columns:
        returns = df['equity'].pct_change().dropna()
    
    if returns is None or len(returns) < 10:
        return None
    
    quantiles = returns.quantile([0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99])
    
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=['1%', '5%', '25%', '50%', '75%', '95%', '99%'],
        y=quantiles.values * 100,
        marker_color=[THEME["red"] if v < 0 else THEME["green"] for v in quantiles.values],
    ))
    
    fig.add_hline(y=0, line_dash="dash", line_color="gray")
    fig.update_xaxes(title="Quantile")
    fig.update_yaxes(title="Return (%)")
    fig.update_layout(title="Returns Quantile Distribution")
    
    return apply_theme(fig, 400)



# ============================================================================
# INTELLIGENCE & REGIME TAB CHARTS (12 charts)
# ============================================================================

def chart_regime_timeline(df: pd.DataFrame) -> Optional[go.Figure]:
    """16. Regime Timeline"""
    if df is None or df.empty or 'date' not in df.columns:
        return None
    
    fig = go.Figure()
    
    if 'regime' in df.columns:
        # Map regimes to numeric values for visualization
        regime_map = {'bullish': 2, 'neutral': 1, 'bearish': 0, 'crisis': -1}
        regime_colors = {'bullish': THEME["green"], 'neutral': THEME["blue"], 
                        'bearish': THEME["red"], 'crisis': THEME["amber"]}
        
        df = df.copy()
        df['regime_num'] = df['regime'].map(regime_map)
        
        for regime in df['regime'].unique():
            regime_df = df[df['regime'] == regime]
            fig.add_trace(go.Scatter(
                x=regime_df['date'],
                y=regime_df['regime_num'],
                mode='markers',
                name=regime.capitalize(),
                marker=dict(size=8, color=regime_colors.get(regime, THEME["blue"])),
            ))
    
    fig.update_xaxes(title="Date")
    fig.update_yaxes(title="Regime", ticktext=['Crisis', 'Bearish', 'Neutral', 'Bullish'],
                     tickvals=[-1, 0, 1, 2])
    fig.update_layout(title="Market Regime Timeline")
    
    return apply_theme(fig, 400)


def chart_regime_transition_matrix(df: pd.DataFrame) -> Optional[go.Figure]:
    """17. Regime Transition Matrix"""
    if df is None or df.empty or 'regime' not in df.columns:
        return None
    
    # Calculate transition matrix
    regimes = df['regime'].values
    transitions = {}
    
    for i in range(len(regimes) - 1):
        from_regime = regimes[i]
        to_regime = regimes[i + 1]
        key = (from_regime, to_regime)
        transitions[key] = transitions.get(key, 0) + 1
    
    # Create matrix
    unique_regimes = sorted(df['regime'].unique())
    matrix = np.zeros((len(unique_regimes), len(unique_regimes)))
    
    for i, from_r in enumerate(unique_regimes):
        for j, to_r in enumerate(unique_regimes):
            matrix[i, j] = transitions.get((from_r, to_r), 0)
    
    # Normalize by row
    row_sums = matrix.sum(axis=1, keepdims=True)
    matrix = np.divide(matrix, row_sums, where=row_sums != 0)
    
    fig = go.Figure(data=go.Heatmap(
        z=matrix,
        x=[r.capitalize() for r in unique_regimes],
        y=[r.capitalize() for r in unique_regimes],
        colorscale='Blues',
        text=np.round(matrix * 100, 1),
        texttemplate='%{text}%',
        textfont={"size": 12},
    ))
    
    fig.update_layout(
        title="Regime Transition Probability Matrix",
        xaxis_title="To Regime",
        yaxis_title="From Regime",
    )
    
    return apply_theme(fig, 450)


def chart_sentiment_score(df: pd.DataFrame) -> Optional[go.Figure]:
    """18. Sentiment Score Over Time"""
    if df is None or df.empty:
        return None
    
    fig = go.Figure()
    
    if 'sentiment_score' in df.columns and 'date' in df.columns:
        fig.add_trace(go.Scatter(
            x=df['date'],
            y=df['sentiment_score'],
            mode='lines',
            name='Sentiment',
            line=dict(color=THEME["cyan"], width=2),
        ))
        
        fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
    
    fig.update_xaxes(title="Date")
    fig.update_yaxes(title="Sentiment Score", range=[-1, 1])
    fig.update_layout(title="Market Sentiment Score Over Time")
    
    return apply_theme(fig, 400)


def chart_sentiment_polarity(df: pd.DataFrame) -> Optional[go.Figure]:
    """19. Market Sentiment Polarity Distribution"""
    if df is None or df.empty:
        return None
    
    # Use sentiment_polarity if available, otherwise try sentiment_regime
    if 'sentiment_polarity' in df.columns:
        # Create polarity categories from continuous values
        df = df.copy()
        df['polarity_category'] = pd.cut(
            df['sentiment_polarity'],
            bins=[0, 0.33, 0.67, 1.0],
            labels=['Negative', 'Neutral', 'Positive']
        )
        sentiment_counts = df['polarity_category'].value_counts()
    elif 'sentiment_regime' in df.columns:
        sentiment_counts = df['sentiment_regime'].value_counts()
    else:
        return None
    
    if sentiment_counts.empty:
        return None
    
    fig = go.Figure(data=[go.Pie(
        labels=sentiment_counts.index,
        values=sentiment_counts.values,
        marker=dict(colors=[THEME["red"], THEME["blue"], THEME["green"]]),
    )])
    
    fig.update_layout(title="Sentiment Polarity Distribution")
    
    return apply_theme(fig, 400)


def chart_sentiment_conviction(df: pd.DataFrame) -> Optional[go.Figure]:
    """20. Sentiment Conviction Over Time"""
    if df is None or df.empty:
        return None
    
    fig = go.Figure()
    
    if 'sentiment_conviction' in df.columns and 'date' in df.columns:
        fig.add_trace(go.Scatter(
            x=df['date'],
            y=df['sentiment_conviction'],
            mode='lines',
            name='Conviction',
            line=dict(color=THEME["amber"], width=2),
            fill='tozeroy',
            fillcolor='rgba(245, 158, 11, 0.2)',
        ))
    
    fig.update_xaxes(title="Date")
    fig.update_yaxes(title="Conviction", range=[0, 1])
    fig.update_layout(title="Sentiment Conviction Level")
    
    return apply_theme(fig, 400)


def chart_narrative_strength(df: pd.DataFrame) -> Optional[go.Figure]:
    """21. Narrative Strength"""
    if df is None or df.empty:
        return None
    
    fig = go.Figure()
    
    if 'narrative_strength' in df.columns and 'date' in df.columns:
        fig.add_trace(go.Scatter(
            x=df['date'],
            y=df['narrative_strength'],
            mode='lines+markers',
            name='Narrative Strength',
            line=dict(color=THEME["green"], width=2),
            marker=dict(size=6),
        ))
    
    fig.update_xaxes(title="Date")
    fig.update_yaxes(title="Strength")
    fig.update_layout(title="Market Narrative Strength")
    
    return apply_theme(fig, 400)


def chart_macro_driver_heatmap(df: pd.DataFrame) -> Optional[go.Figure]:
    """22. Macro Driver Heatmap"""
    if df is None or df.empty:
        return None
    
    # Prepare macro data for heatmap
    macro_cols = [c for c in df.columns if c not in ['date', 'timestamp']]
    
    if not macro_cols:
        return None
    
    # Take recent data and calculate z-scores
    recent_df = df.tail(60).copy()
    
    z_scores = {}
    for col in macro_cols:
        if pd.api.types.is_numeric_dtype(recent_df[col]):
            values = recent_df[col].dropna()
            if len(values) > 5:
                mean = values.mean()
                std = values.std()
                if std > 0:
                    z_scores[col] = ((values - mean) / std).values
    
    if not z_scores:
        return None
    
    # Create matrix
    max_len = max(len(v) for v in z_scores.values())
    matrix = np.full((len(z_scores), max_len), 0.0)  # Use 0 instead of NaN
    
    for i, (col, values) in enumerate(z_scores.items()):
        matrix[i, :len(values)] = values
    
    fig = go.Figure(data=go.Heatmap(
        z=matrix,
        y=list(z_scores.keys()),
        colorscale='RdBu_r',
        zmid=0,
        zmin=-3,
        zmax=3,
    ))
    
    fig.update_layout(
        title="Macro Drivers Heatmap (Z-Scores)",
        xaxis_title="Time",
        yaxis_title="Macro Variable",
    )
    
    return apply_theme(fig, 500)


def chart_macro_changes(df: pd.DataFrame) -> Optional[go.Figure]:
    """23. Macro Changes Z-Score"""
    if df is None or df.empty:
        return None
    
    # Calculate changes for numeric columns
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    
    if len(numeric_cols) == 0:
        return None
    
    changes = df[numeric_cols].diff()
    
    # Calculate z-scores
    z_scores = (changes - changes.mean()) / changes.std()
    z_scores = z_scores.clip(-3, 3)
    
    # Drop columns with all NaN
    z_scores = z_scores.dropna(axis=1, how='all')
    
    if z_scores.empty or len(z_scores.columns) == 0:
        return None
    
    # Take recent data
    recent = z_scores.tail(30)
    
    # Replace remaining NaN with 0
    recent = recent.fillna(0)
    
    if recent.empty:
        return None
    
    fig = go.Figure(data=go.Heatmap(
        z=recent.T.values,
        x=list(range(len(recent))),
        y=list(recent.columns),
        colorscale='RdBu_r',
        zmid=0,
    ))
    
    fig.update_layout(
        title="Macro Variable Changes (Z-Scores)",
        xaxis_title="Time Period",
        yaxis_title="Variable",
    )
    
    return apply_theme(fig, 500)


def chart_regime_stability(df: pd.DataFrame) -> Optional[go.Figure]:
    """24. Regime Stability Score"""
    if df is None or df.empty:
        return None
    
    fig = go.Figure()
    
    if 'regime_stability' in df.columns and 'date' in df.columns:
        fig.add_trace(go.Scatter(
            x=df['date'],
            y=df['regime_stability'],
            mode='lines',
            name='Stability',
            line=dict(color=THEME["blue"], width=2),
        ))
        
        fig.add_hline(y=0.5, line_dash="dash", line_color="gray", opacity=0.5,
                     annotation_text="Threshold")
    
    fig.update_xaxes(title="Date")
    fig.update_yaxes(title="Stability Score", range=[0, 1])
    fig.update_layout(title="Regime Stability Score")
    
    return apply_theme(fig, 400)


def chart_intelligence_freshness(df: pd.DataFrame) -> Optional[go.Figure]:
    """25. Intelligence Data Freshness"""
    if df is None or df.empty or 'date' not in df.columns:
        return None
    
    # Calculate data age
    latest_date = pd.to_datetime(df['date']).max()
    current_date = pd.Timestamp.now()
    age_hours = (current_date - latest_date).total_seconds() / 3600
    
    fig = go.Figure()
    
    fig.add_trace(go.Indicator(
        mode="gauge+number",
        value=age_hours,
        title={'text': "Data Age (hours)"},
        gauge={
            'axis': {'range': [None, 72]},
            'bar': {'color': THEME["blue"]},
            'steps': [
                {'range': [0, 24], 'color': THEME["green"]},
                {'range': [24, 48], 'color': THEME["amber"]},
                {'range': [48, 72], 'color': THEME["red"]},
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': 48
            }
        }
    ))
    
    fig.update_layout(title="Intelligence Data Freshness")
    
    return apply_theme(fig, 350)


def chart_sentiment_returns_correlation(sentiment_df: pd.DataFrame, returns_df: pd.DataFrame) -> Optional[go.Figure]:
    """26. Sentiment vs Returns Correlation"""
    if sentiment_df is None or returns_df is None:
        return None
    
    if sentiment_df.empty or returns_df.empty:
        return None
    
    # Merge on date
    if 'date' not in sentiment_df.columns or 'date' not in returns_df.columns:
        return None
    
    # Ensure dates are datetime
    sentiment_df = sentiment_df.copy()
    returns_df = returns_df.copy()
    sentiment_df['date'] = pd.to_datetime(sentiment_df['date']).dt.date
    returns_df['date'] = pd.to_datetime(returns_df['date']).dt.date
    
    merged = pd.merge(sentiment_df, returns_df, on='date', how='inner')
    
    if len(merged) < 5:
        return None
    
    if 'sentiment_score' not in merged.columns:
        return None
    
    returns_col = 'daily_return' if 'daily_return' in merged.columns else 'equity'
    if returns_col not in merged.columns:
        return None
    
    # Drop NaN values
    merged = merged[['sentiment_score', returns_col]].dropna()
    
    if len(merged) < 5:
        return None
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=merged['sentiment_score'],
        y=merged[returns_col] * 100,
        mode='markers',
        marker=dict(
            size=6,
            color=merged['sentiment_score'],
            colorscale='RdYlGn',
            showscale=True,
        ),
    ))
    
    # Add trend line
    try:
        z = np.polyfit(merged['sentiment_score'], merged[returns_col] * 100, 1)
        p = np.poly1d(z)
        x_trend = np.linspace(merged['sentiment_score'].min(), 
                             merged['sentiment_score'].max(), 100)
        
        fig.add_trace(go.Scatter(
            x=x_trend,
            y=p(x_trend),
            mode='lines',
            name='Trend',
            line=dict(color=THEME["red"], width=2, dash='dash'),
        ))
    except:
        pass  # Skip trend line if it fails
    
    fig.update_xaxes(title="Sentiment Score")
    fig.update_yaxes(title="Daily Return (%)")
    fig.update_layout(title="Sentiment vs Returns Correlation")
    
    return apply_theme(fig, 450)


def chart_regime_duration_dist(df: pd.DataFrame) -> Optional[go.Figure]:
    """27. Regime Duration Distribution"""
    if df is None or df.empty or 'regime' not in df.columns:
        return None
    
    # Calculate regime durations
    regimes = df['regime'].values
    durations = []
    current_regime = regimes[0]
    current_duration = 1
    
    for regime in regimes[1:]:
        if regime == current_regime:
            current_duration += 1
        else:
            durations.append({'regime': current_regime, 'duration': current_duration})
            current_regime = regime
            current_duration = 1
    
    durations.append({'regime': current_regime, 'duration': current_duration})
    
    dur_df = pd.DataFrame(durations)
    
    fig = go.Figure()
    
    for regime in dur_df['regime'].unique():
        regime_data = dur_df[dur_df['regime'] == regime]['duration']
        fig.add_trace(go.Box(
            y=regime_data,
            name=regime.capitalize(),
            boxmean='sd',
        ))
    
    fig.update_xaxes(title="Regime")
    fig.update_yaxes(title="Duration (days)")
    fig.update_layout(title="Regime Duration Distribution")
    
    return apply_theme(fig, 400)



# ============================================================================
# OPTIONS SYSTEM TAB CHARTS (15 charts)
# ============================================================================

def chart_greeks_heatmap(options_df: pd.DataFrame) -> Optional[go.Figure]:
    """28. Greeks Heatmap (Delta, Gamma, Vega, Theta) - CRITICAL"""
    if options_df is None or options_df.empty:
        return None
    
    # Prepare Greeks data
    greeks = ['delta', 'gamma', 'vega', 'theta']
    available_greeks = [g for g in greeks if g in options_df.columns]
    
    if not available_greeks or 'strike' not in options_df.columns:
        return None
    
    # Create subplots for each Greek
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=('Delta', 'Gamma', 'Vega', 'Theta'),
        vertical_spacing=0.12,
        horizontal_spacing=0.1,
    )
    
    positions = [(1, 1), (1, 2), (2, 1), (2, 2)]
    colors = ['Blues', 'Greens', 'Reds', 'Purples']
    
    for idx, greek in enumerate(available_greeks[:4]):
        row, col = positions[idx]
        
        # Pivot data by strike and expiry
        if 'expiry' in options_df.columns:
            pivot = options_df.pivot_table(
                values=greek,
                index='strike',
                columns='expiry',
                aggfunc='mean'
            )
        else:
            pivot = options_df.groupby('strike')[greek].mean().to_frame()
        
        fig.add_trace(
            go.Heatmap(
                z=pivot.values,
                x=pivot.columns if hasattr(pivot, 'columns') else ['Value'],
                y=pivot.index,
                colorscale=colors[idx],
                showscale=True,
            ),
            row=row, col=col
        )
    
    fig.update_layout(
        title="Options Greeks Heatmap",
        height=600,
    )
    
    return apply_theme(fig, 600)


def chart_iv_surface_3d(options_df: pd.DataFrame) -> Optional[go.Figure]:
    """29. IV Surface 3D - CRITICAL"""
    if options_df is None or options_df.empty:
        return None
    
    required_cols = ['strike', 'implied_volatility']
    if not all(col in options_df.columns for col in required_cols):
        return None
    
    # Prepare data
    if 'days_to_expiry' in options_df.columns:
        x = options_df['days_to_expiry']
        x_label = 'Days to Expiry'
    elif 'expiry' in options_df.columns:
        options_df['days_to_expiry'] = (pd.to_datetime(options_df['expiry']) - pd.Timestamp.now()).dt.days
        x = options_df['days_to_expiry']
        x_label = 'Days to Expiry'
    else:
        return None
    
    y = options_df['strike']
    z = options_df['implied_volatility'] * 100  # Convert to percentage
    
    # Create 3D surface
    fig = go.Figure(data=[go.Surface(
        x=x,
        y=y,
        z=z,
        colorscale='Viridis',
        colorbar=dict(title="IV (%)"),
    )])
    
    fig.update_layout(
        title="Implied Volatility Surface",
        scene=dict(
            xaxis_title=x_label,
            yaxis_title='Strike Price',
            zaxis_title='Implied Volatility (%)',
        ),
        height=600,
    )
    
    return apply_theme(fig, 600)


def chart_implied_vs_realized_vol(options_df: pd.DataFrame, realized_vol: float = None) -> Optional[go.Figure]:
    """30. Implied vs Realized Volatility"""
    if options_df is None or options_df.empty:
        return None
    
    fig = go.Figure()
    
    if 'implied_volatility' in options_df.columns and 'strike' in options_df.columns:
        # ATM options
        atm_options = options_df.nsmallest(5, 'strike')
        
        fig.add_trace(go.Scatter(
            x=atm_options['strike'],
            y=atm_options['implied_volatility'] * 100,
            mode='lines+markers',
            name='Implied Vol',
            line=dict(color=THEME["blue"], width=2),
        ))
        
        if realized_vol is not None:
            fig.add_hline(
                y=realized_vol * 100,
                line_dash="dash",
                line_color=THEME["red"],
                annotation_text="Realized Vol",
            )
    
    fig.update_xaxes(title="Strike Price")
    fig.update_yaxes(title="Volatility (%)")
    fig.update_layout(title="Implied vs Realized Volatility")
    
    return apply_theme(fig, 400)


def chart_volatility_smile(options_df: pd.DataFrame, expiry: str = None) -> Optional[go.Figure]:
    """31. Volatility Smile by Expiry"""
    if options_df is None or options_df.empty:
        return None
    
    if 'implied_volatility' not in options_df.columns or 'strike' not in options_df.columns:
        return None
    
    fig = go.Figure()
    
    if 'expiry' in options_df.columns:
        expiries = options_df['expiry'].unique()
        
        for exp in expiries[:5]:  # Show up to 5 expiries
            exp_data = options_df[options_df['expiry'] == exp].sort_values('strike')
            
            fig.add_trace(go.Scatter(
                x=exp_data['strike'],
                y=exp_data['implied_volatility'] * 100,
                mode='lines+markers',
                name=str(exp),
                line=dict(width=2),
            ))
    else:
        fig.add_trace(go.Scatter(
            x=options_df['strike'],
            y=options_df['implied_volatility'] * 100,
            mode='lines+markers',
            name='IV',
            line=dict(color=THEME["blue"], width=2),
        ))
    
    fig.update_xaxes(title="Strike Price")
    fig.update_yaxes(title="Implied Volatility (%)")
    fig.update_layout(title="Volatility Smile")
    
    return apply_theme(fig, 450)


def chart_options_pnl_attribution(positions_df: pd.DataFrame) -> Optional[go.Figure]:
    """32. Options P&L Attribution"""
    if positions_df is None or positions_df.empty:
        return None
    
    fig = go.Figure()
    
    if 'pnl' in positions_df.columns and 'strategy' in positions_df.columns:
        pnl_by_strategy = positions_df.groupby('strategy')['pnl'].sum().sort_values()
        
        fig.add_trace(go.Bar(
            x=pnl_by_strategy.values,
            y=pnl_by_strategy.index,
            orientation='h',
            marker_color=[THEME["green"] if v > 0 else THEME["red"] for v in pnl_by_strategy.values],
        ))
    
    fig.update_xaxes(title="P&L (₹)")
    fig.update_yaxes(title="Strategy")
    fig.update_layout(title="Options P&L Attribution by Strategy")
    
    return apply_theme(fig, 450)


def chart_hedge_effectiveness(positions_df: pd.DataFrame) -> Optional[go.Figure]:
    """33. Hedge Effectiveness"""
    if positions_df is None or positions_df.empty:
        return None
    
    fig = go.Figure()
    
    if 'delta' in positions_df.columns and 'date' in positions_df.columns:
        # Portfolio delta over time
        delta_by_date = positions_df.groupby('date')['delta'].sum()
        
        fig.add_trace(go.Scatter(
            x=delta_by_date.index,
            y=delta_by_date.values,
            mode='lines',
            name='Portfolio Delta',
            line=dict(color=THEME["blue"], width=2),
        ))
        
        fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
    
    fig.update_xaxes(title="Date")
    fig.update_yaxes(title="Portfolio Delta")
    fig.update_layout(title="Hedge Effectiveness (Portfolio Delta)")
    
    return apply_theme(fig, 400)


def chart_gamma_exposure_by_strike(options_df: pd.DataFrame) -> Optional[go.Figure]:
    """34. Gamma Exposure by Strike"""
    if options_df is None or options_df.empty:
        return None
    
    if 'gamma' not in options_df.columns or 'strike' not in options_df.columns:
        return None
    
    gamma_by_strike = options_df.groupby('strike')['gamma'].sum().sort_index()
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=gamma_by_strike.index,
        y=gamma_by_strike.values,
        marker_color=THEME["green"],
    ))
    
    fig.update_xaxes(title="Strike Price")
    fig.update_yaxes(title="Gamma Exposure")
    fig.update_layout(title="Gamma Exposure by Strike")
    
    return apply_theme(fig, 400)


def chart_vega_exposure_by_expiry(options_df: pd.DataFrame) -> Optional[go.Figure]:
    """35. Vega Exposure by Expiry"""
    if options_df is None or options_df.empty:
        return None
    
    if 'vega' not in options_df.columns or 'expiry' not in options_df.columns:
        return None
    
    vega_by_expiry = options_df.groupby('expiry')['vega'].sum()
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=vega_by_expiry.index,
        y=vega_by_expiry.values,
        marker_color=THEME["cyan"],
    ))
    
    fig.update_xaxes(title="Expiry Date")
    fig.update_yaxes(title="Vega Exposure")
    fig.update_layout(title="Vega Exposure by Expiry")
    
    return apply_theme(fig, 400)


def chart_theta_decay_timeline(options_df: pd.DataFrame) -> Optional[go.Figure]:
    """36. Theta Decay Timeline"""
    if options_df is None or options_df.empty:
        return None
    
    if 'theta' not in options_df.columns:
        return None
    
    fig = go.Figure()
    
    if 'days_to_expiry' in options_df.columns:
        # Group by days to expiry
        theta_by_dte = options_df.groupby('days_to_expiry')['theta'].sum().sort_index()
        
        fig.add_trace(go.Scatter(
            x=theta_by_dte.index,
            y=theta_by_dte.values,
            mode='lines+markers',
            name='Theta',
            line=dict(color=THEME["red"], width=2),
        ))
    
    fig.update_xaxes(title="Days to Expiry")
    fig.update_yaxes(title="Theta (Daily Decay)")
    fig.update_layout(title="Theta Decay Timeline")
    
    return apply_theme(fig, 400)


def chart_options_position_sizing(positions_df: pd.DataFrame) -> Optional[go.Figure]:
    """37. Options Position Sizing"""
    if positions_df is None or positions_df.empty:
        return None
    
    if 'notional_value' not in positions_df.columns:
        return None
    
    fig = go.Figure()
    
    if 'symbol' in positions_df.columns:
        sizing = positions_df.groupby('symbol')['notional_value'].sum().sort_values(ascending=False).head(10)
        
        fig.add_trace(go.Bar(
            x=sizing.index,
            y=sizing.values,
            marker_color=THEME["blue"],
        ))
    
    fig.update_xaxes(title="Option Symbol")
    fig.update_yaxes(title="Notional Value (₹)")
    fig.update_layout(title="Top 10 Options Positions by Notional Value")
    
    return apply_theme(fig, 450)


def chart_strike_distribution(options_df: pd.DataFrame) -> Optional[go.Figure]:
    """38. Strike Distribution"""
    if options_df is None or options_df.empty or 'strike' not in options_df.columns:
        return None
    
    fig = go.Figure()
    
    fig.add_trace(go.Histogram(
        x=options_df['strike'],
        nbinsx=30,
        marker_color=THEME["blue"],
    ))
    
    # Add current spot price if available
    if 'spot_price' in options_df.columns:
        spot = options_df['spot_price'].iloc[0]
        fig.add_vline(
            x=spot,
            line_dash="dash",
            line_color=THEME["red"],
            annotation_text="Spot",
        )
    
    fig.update_xaxes(title="Strike Price")
    fig.update_yaxes(title="Number of Contracts")
    fig.update_layout(title="Strike Price Distribution")
    
    return apply_theme(fig, 400)


def chart_expiry_calendar(options_df: pd.DataFrame) -> Optional[go.Figure]:
    """39. Expiry Calendar - CRITICAL"""
    if options_df is None or options_df.empty or 'expiry' not in options_df.columns:
        return None
    
    # Count contracts by expiry
    expiry_counts = options_df['expiry'].value_counts().sort_index()
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=expiry_counts.index,
        y=expiry_counts.values,
        marker_color=THEME["cyan"],
    ))
    
    # Highlight near-term expiries
    today = pd.Timestamp.now()
    for expiry in expiry_counts.index:
        days_to_expiry = (pd.to_datetime(expiry) - today).days
        if days_to_expiry <= 7:
            fig.add_vline(
                x=expiry,
                line_dash="dash",
                line_color=THEME["red"],
                opacity=0.5,
            )
    
    fig.update_xaxes(title="Expiry Date")
    fig.update_yaxes(title="Number of Contracts")
    fig.update_layout(title="Options Expiry Calendar")
    
    return apply_theme(fig, 450)


def chart_volatility_regime(options_df: pd.DataFrame) -> Optional[go.Figure]:
    """40. Volatility Regime Detection"""
    if options_df is None or options_df.empty:
        return None
    
    if 'implied_volatility' not in options_df.columns:
        return None
    
    # Calculate IV percentiles
    iv_values = options_df['implied_volatility'].dropna()
    
    if len(iv_values) < 10:
        return None
    
    percentiles = [10, 25, 50, 75, 90]
    pct_values = np.percentile(iv_values * 100, percentiles)
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=[f'{p}th' for p in percentiles],
        y=pct_values,
        marker_color=THEME["blue"],
    ))
    
    # Add current IV level
    current_iv = iv_values.iloc[-1] * 100 if len(iv_values) > 0 else 0
    fig.add_hline(
        y=current_iv,
        line_dash="dash",
        line_color=THEME["red"],
        annotation_text=f"Current: {current_iv:.1f}%",
    )
    
    fig.update_xaxes(title="Percentile")
    fig.update_yaxes(title="Implied Volatility (%)")
    fig.update_layout(title="Volatility Regime (IV Percentiles)")
    
    return apply_theme(fig, 400)


def chart_options_strategy_performance(positions_df: pd.DataFrame) -> Optional[go.Figure]:
    """41. Options Strategy Performance"""
    if positions_df is None or positions_df.empty:
        return None
    
    if 'strategy' not in positions_df.columns or 'pnl' not in positions_df.columns:
        return None
    
    # Calculate cumulative P&L by strategy
    if 'date' in positions_df.columns:
        positions_df = positions_df.sort_values('date')
        
        fig = go.Figure()
        
        for strategy in positions_df['strategy'].unique():
            strategy_data = positions_df[positions_df['strategy'] == strategy]
            cum_pnl = strategy_data['pnl'].cumsum()
            
            fig.add_trace(go.Scatter(
                x=strategy_data['date'],
                y=cum_pnl,
                mode='lines',
                name=strategy,
                line=dict(width=2),
            ))
        
        fig.update_xaxes(title="Date")
        fig.update_yaxes(title="Cumulative P&L (₹)")
        fig.update_layout(title="Options Strategy Performance")
        
        return apply_theme(fig, 450)
    
    return None


def chart_greeks_evolution(greeks_df: pd.DataFrame) -> Optional[go.Figure]:
    """42. Greeks Evolution Over Time"""
    if greeks_df is None or greeks_df.empty or 'date' not in greeks_df.columns:
        return None
    
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=('Delta', 'Gamma', 'Vega', 'Theta'),
        vertical_spacing=0.12,
    )
    
    greeks = ['delta', 'gamma', 'vega', 'theta']
    positions = [(1, 1), (1, 2), (2, 1), (2, 2)]
    colors = [THEME["blue"], THEME["green"], THEME["red"], THEME["amber"]]
    
    for idx, greek in enumerate(greeks):
        if greek not in greeks_df.columns:
            continue
        
        row, col = positions[idx]
        
        fig.add_trace(
            go.Scatter(
                x=greeks_df['date'],
                y=greeks_df[greek],
                mode='lines',
                name=greek.capitalize(),
                line=dict(color=colors[idx], width=2),
            ),
            row=row, col=col
        )
    
    fig.update_layout(
        title="Portfolio Greeks Evolution",
        height=600,
    )
    
    return apply_theme(fig, 600)



# ============================================================================
# PORTFOLIO GOVERNOR TAB CHARTS (10 charts)
# ============================================================================

def chart_portfolio_weights(positions_df: pd.DataFrame) -> Optional[go.Figure]:
    """43. Current Portfolio Weights"""
    if positions_df is None or positions_df.empty:
        return None
    
    if 'weight' not in positions_df.columns:
        # Calculate weights from notional values
        if 'notional_value' in positions_df.columns:
            total = positions_df['notional_value'].sum()
            positions_df['weight'] = positions_df['notional_value'] / total
        else:
            return None
    
    fig = go.Figure()
    
    if 'symbol' in positions_df.columns:
        weights = positions_df.nlargest(20, 'weight')[['symbol', 'weight']]
        
        fig.add_trace(go.Bar(
            x=weights['symbol'],
            y=weights['weight'] * 100,
            marker=dict(
                color=weights['weight'],
                colorscale='Blues',
                showscale=True,
                colorbar=dict(title="Weight (%)"),
            ),
        ))
    
    fig.update_xaxes(title="Symbol", tickangle=-45)
    fig.update_yaxes(title="Weight (%)")
    fig.update_layout(title="Top 20 Portfolio Weights")
    
    return apply_theme(fig, 500)


def chart_cluster_exposure(positions_df: pd.DataFrame) -> Optional[go.Figure]:
    """44. Cluster Exposure Pie"""
    if positions_df is None or positions_df.empty:
        return None
    
    if 'cluster' not in positions_df.columns:
        return None
    
    cluster_exposure = positions_df.groupby('cluster')['notional_value'].sum() if 'notional_value' in positions_df.columns else positions_df['cluster'].value_counts()
    
    fig = go.Figure(data=[go.Pie(
        labels=cluster_exposure.index,
        values=cluster_exposure.values,
        hole=0.3,
    )])
    
    fig.update_layout(title="Portfolio Cluster Exposure")
    
    return apply_theme(fig, 450)


def chart_eigenvalue_spectrum(returns_df: pd.DataFrame) -> Optional[go.Figure]:
    """45. Eigenvalue Spectrum"""
    if returns_df is None or returns_df.empty:
        return None
    
    # Calculate correlation matrix
    numeric_cols = returns_df.select_dtypes(include=[np.number]).columns
    
    if len(numeric_cols) < 2:
        return None
    
    corr_matrix = returns_df[numeric_cols].corr()
    
    # Calculate eigenvalues
    eigenvalues = np.linalg.eigvalsh(corr_matrix.values)
    eigenvalues = np.sort(eigenvalues)[::-1]
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=list(range(1, len(eigenvalues) + 1)),
        y=eigenvalues,
        marker_color=THEME["blue"],
    ))
    
    fig.update_xaxes(title="Eigenvalue Rank")
    fig.update_yaxes(title="Eigenvalue")
    fig.update_layout(title="Correlation Matrix Eigenvalue Spectrum")
    
    return apply_theme(fig, 450)


def chart_correlation_heatmap(returns_df: pd.DataFrame, crisis_mode: bool = False) -> Optional[go.Figure]:
    """46. Correlation Heatmap (Base vs Crisis)"""
    if returns_df is None or returns_df.empty:
        return None
    
    numeric_cols = returns_df.select_dtypes(include=[np.number]).columns
    
    if len(numeric_cols) < 2:
        return None
    
    # Calculate correlation matrix
    corr_matrix = returns_df[numeric_cols].corr()
    
    # Replace NaN with 0
    corr_matrix = corr_matrix.fillna(0)
    
    if corr_matrix.empty:
        return None
    
    fig = go.Figure(data=go.Heatmap(
        z=corr_matrix.values,
        x=list(corr_matrix.columns),
        y=list(corr_matrix.columns),
        colorscale='RdBu_r',
        zmid=0,
        zmin=-1,
        zmax=1,
        text=np.round(corr_matrix.values, 2),
        texttemplate='%{text}',
        textfont={"size": 8},
    ))
    
    title = "Crisis Correlation Matrix" if crisis_mode else "Base Correlation Matrix"
    fig.update_layout(title=title)
    
    return apply_theme(fig, 600)


def chart_kelly_multiplier(df: pd.DataFrame) -> Optional[go.Figure]:
    """47. Kelly Multiplier Over Time"""
    if df is None or df.empty:
        return None
    
    fig = go.Figure()
    
    if 'kelly_multiplier' in df.columns and 'date' in df.columns:
        fig.add_trace(go.Scatter(
            x=df['date'],
            y=df['kelly_multiplier'],
            mode='lines',
            name='Kelly Multiplier',
            line=dict(color=THEME["green"], width=2),
        ))
        
        fig.add_hline(y=1, line_dash="dash", line_color="gray", opacity=0.5)
    
    fig.update_xaxes(title="Date")
    fig.update_yaxes(title="Kelly Multiplier")
    fig.update_layout(title="Kelly Multiplier Over Time")
    
    return apply_theme(fig, 400)


def chart_exposure_multiplier(df: pd.DataFrame) -> Optional[go.Figure]:
    """48. Exposure Multiplier Over Time"""
    if df is None or df.empty:
        return None
    
    fig = go.Figure()
    
    if 'exposure_multiplier' in df.columns and 'date' in df.columns:
        fig.add_trace(go.Scatter(
            x=df['date'],
            y=df['exposure_multiplier'],
            mode='lines',
            name='Exposure',
            line=dict(color=THEME["amber"], width=2),
            fill='tozeroy',
            fillcolor='rgba(245, 158, 11, 0.2)',
        ))
    
    fig.update_xaxes(title="Date")
    fig.update_yaxes(title="Exposure Multiplier")
    fig.update_layout(title="Exposure Multiplier Over Time")
    
    return apply_theme(fig, 400)


def chart_gross_target_evolution(df: pd.DataFrame) -> Optional[go.Figure]:
    """49. Gross Target Evolution"""
    if df is None or df.empty:
        return None
    
    fig = go.Figure()
    
    if 'gross_target' in df.columns and 'date' in df.columns:
        fig.add_trace(go.Scatter(
            x=df['date'],
            y=df['gross_target'],
            mode='lines',
            name='Gross Target',
            line=dict(color=THEME["blue"], width=2),
        ))
        
        if 'smoothed_target' in df.columns:
            fig.add_trace(go.Scatter(
                x=df['date'],
                y=df['smoothed_target'],
                mode='lines',
                name='Smoothed',
                line=dict(color=THEME["cyan"], width=2, dash='dash'),
            ))
    
    fig.update_xaxes(title="Date")
    fig.update_yaxes(title="Gross Target")
    fig.update_layout(title="Gross Target Evolution")
    
    return apply_theme(fig, 400)


def chart_capital_allocation_by_strategy(df: pd.DataFrame) -> Optional[go.Figure]:
    """50. Capital Allocation by Strategy"""
    if df is None or df.empty:
        return None
    
    if 'strategy' not in df.columns or 'allocation' not in df.columns:
        return None
    
    allocation = df.groupby('strategy')['allocation'].sum().sort_values(ascending=False)
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=allocation.index,
        y=allocation.values * 100,
        marker_color=THEME["blue"],
    ))
    
    fig.update_xaxes(title="Strategy", tickangle=-45)
    fig.update_yaxes(title="Allocation (%)")
    fig.update_layout(title="Capital Allocation by Strategy")
    
    return apply_theme(fig, 450)


def chart_risk_contribution(positions_df: pd.DataFrame) -> Optional[go.Figure]:
    """51. Risk Contribution by Position"""
    if positions_df is None or positions_df.empty:
        return None
    
    if 'risk_contribution' not in positions_df.columns:
        # Calculate from volatility and weight
        if 'volatility' in positions_df.columns and 'weight' in positions_df.columns:
            positions_df['risk_contribution'] = positions_df['volatility'] * positions_df['weight']
        else:
            return None
    
    risk_contrib = positions_df.nlargest(15, 'risk_contribution')[['symbol', 'risk_contribution']] if 'symbol' in positions_df.columns else None
    
    if risk_contrib is None:
        return None
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=risk_contrib['symbol'],
        y=risk_contrib['risk_contribution'] * 100,
        marker_color=THEME["red"],
    ))
    
    fig.update_xaxes(title="Symbol", tickangle=-45)
    fig.update_yaxes(title="Risk Contribution (%)")
    fig.update_layout(title="Top 15 Risk Contributors")
    
    return apply_theme(fig, 450)


def chart_sector_exposure(positions_df: pd.DataFrame, sector_mapping: pd.DataFrame = None) -> Optional[go.Figure]:
    """52. Sector Exposure Breakdown"""
    if positions_df is None or positions_df.empty:
        return None
    
    # Merge with sector mapping if provided
    if sector_mapping is not None and 'ticker' in positions_df.columns:
        positions_df = positions_df.merge(sector_mapping, left_on='ticker', right_on='ticker', how='left')
    
    if 'sector' not in positions_df.columns:
        return None
    
    sector_exposure = positions_df.groupby('sector')['notional_value'].sum() if 'notional_value' in positions_df.columns else positions_df['sector'].value_counts()
    
    fig = go.Figure(data=[go.Pie(
        labels=sector_exposure.index,
        values=sector_exposure.values,
        hole=0.4,
    )])
    
    fig.update_layout(title="Sector Exposure Breakdown")
    
    return apply_theme(fig, 450)


# ============================================================================
# LIVE TRADING TAB CHARTS (53-64)
# ============================================================================

def chart_intraday_pnl(trades_df: pd.DataFrame) -> Optional[go.Figure]:
    """53. Intraday P&L Tracking"""
    if trades_df is None or trades_df.empty or 'timestamp' not in trades_df.columns:
        return None
    
    trades_df = trades_df.copy()
    trades_df['timestamp'] = pd.to_datetime(trades_df['timestamp'])
    trades_df = trades_df.sort_values('timestamp')
    
    if 'pnl' in trades_df.columns:
        trades_df['cumulative_pnl'] = trades_df['pnl'].cumsum()
    else:
        return None
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=trades_df['timestamp'],
        y=trades_df['cumulative_pnl'],
        mode='lines',
        name='Cumulative P&L',
        line=dict(color='#00D9FF', width=2),
        fill='tozeroy',
        fillcolor='rgba(0, 217, 255, 0.1)'
    ))
    
    fig.update_xaxes(title="Time")
    fig.update_yaxes(title="Cumulative P&L (₹)")
    fig.update_layout(title="Intraday P&L Tracking")
    
    return apply_theme(fig, 400)


def chart_position_tracking(positions_df: pd.DataFrame) -> Optional[go.Figure]:
    """54. Real-Time Position Tracking"""
    if positions_df is None or positions_df.empty:
        return None
    
    top_positions = positions_df.nlargest(15, 'notional_value') if 'notional_value' in positions_df.columns else positions_df.head(15)
    
    fig = go.Figure()
    
    if 'ticker' in top_positions.columns and 'quantity' in top_positions.columns:
        colors = ['#00D9FF' if q > 0 else '#FF6B9D' for q in top_positions['quantity']]
        
        fig.add_trace(go.Bar(
            x=top_positions['ticker'],
            y=top_positions['quantity'],
            marker_color=colors,
            name='Position Size'
        ))
    
    fig.update_xaxes(title="Symbol", tickangle=-45)
    fig.update_yaxes(title="Quantity")
    fig.update_layout(title="Top 15 Active Positions")
    
    return apply_theme(fig, 450)


def chart_order_flow(orders_df: pd.DataFrame) -> Optional[go.Figure]:
    """55. Order Flow Analysis"""
    if orders_df is None or orders_df.empty:
        return None
    
    if 'side' in orders_df.columns:
        order_counts = orders_df['side'].value_counts()
        
        fig = go.Figure(data=[go.Bar(
            x=order_counts.index,
            y=order_counts.values,
            marker_color=['#00D9FF', '#FF6B9D'],
            text=order_counts.values,
            textposition='auto'
        )])
        
        fig.update_xaxes(title="Order Side")
        fig.update_yaxes(title="Count")
        fig.update_layout(title="Order Flow Distribution")
        
        return apply_theme(fig, 350)
    
    return None


def chart_execution_quality(trades_df: pd.DataFrame) -> Optional[go.Figure]:
    """56. Execution Quality Metrics"""
    if trades_df is None or trades_df.empty:
        return None
    
    if 'execution_price' in trades_df.columns and 'reference_price' in trades_df.columns:
        trades_df = trades_df.copy()
        trades_df['price_improvement'] = (trades_df['reference_price'] - trades_df['execution_price']) / trades_df['reference_price'] * 100
        
        fig = go.Figure()
        fig.add_trace(go.Histogram(
            x=trades_df['price_improvement'],
            nbinsx=30,
            marker_color='#00D9FF',
            name='Price Improvement'
        ))
        
        fig.update_xaxes(title="Price Improvement (%)")
        fig.update_yaxes(title="Frequency")
        fig.update_layout(title="Execution Quality Distribution")
        
        return apply_theme(fig, 400)
    
    return None


def chart_slippage_analysis(trades_df: pd.DataFrame) -> Optional[go.Figure]:
    """57. Slippage Analysis"""
    if trades_df is None or trades_df.empty or 'slippage_bps' not in trades_df.columns:
        return None
    
    trades_df = trades_df.copy()
    trades_df['timestamp'] = pd.to_datetime(trades_df['timestamp']) if 'timestamp' in trades_df.columns else pd.to_datetime('today')
    trades_df = trades_df.sort_values('timestamp')
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=trades_df['timestamp'],
        y=trades_df['slippage_bps'],
        mode='markers',
        marker=dict(size=8, color='#FF6B9D', opacity=0.6),
        name='Slippage'
    ))
    
    # Add rolling average
    if len(trades_df) > 10:
        trades_df['slippage_ma'] = trades_df['slippage_bps'].rolling(10).mean()
        fig.add_trace(go.Scatter(
            x=trades_df['timestamp'],
            y=trades_df['slippage_ma'],
            mode='lines',
            line=dict(color='#00D9FF', width=2),
            name='10-Trade MA'
        ))
    
    fig.update_xaxes(title="Time")
    fig.update_yaxes(title="Slippage (bps)")
    fig.update_layout(title="Slippage Over Time")
    
    return apply_theme(fig, 400)


def chart_fill_rate(orders_df: pd.DataFrame) -> Optional[go.Figure]:
    """58. Order Fill Rate"""
    if orders_df is None or orders_df.empty or 'status' not in orders_df.columns:
        return None
    
    status_counts = orders_df['status'].value_counts()
    
    fig = go.Figure(data=[go.Pie(
        labels=status_counts.index,
        values=status_counts.values,
        hole=0.4,
        marker=dict(colors=['#00D9FF', '#FF6B9D', '#FFD700', '#9370DB'])
    )])
    
    fig.update_layout(title="Order Fill Rate Distribution")
    
    return apply_theme(fig, 400)


def chart_market_impact(trades_df: pd.DataFrame) -> Optional[go.Figure]:
    """59. Market Impact Analysis"""
    if trades_df is None or trades_df.empty:
        return None
    
    if 'trade_size' in trades_df.columns and 'market_impact_bps' in trades_df.columns:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=trades_df['trade_size'],
            y=trades_df['market_impact_bps'],
            mode='markers',
            marker=dict(size=8, color='#00D9FF', opacity=0.6),
            name='Market Impact'
        ))
        
        fig.update_xaxes(title="Trade Size (₹)", type='log')
        fig.update_yaxes(title="Market Impact (bps)")
        fig.update_layout(title="Market Impact vs Trade Size")
        
        return apply_theme(fig, 400)
    
    return None


def chart_execution_latency(trades_df: pd.DataFrame) -> Optional[go.Figure]:
    """60. Execution Latency Distribution"""
    if trades_df is None or trades_df.empty or 'latency_ms' not in trades_df.columns:
        return None
    
    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=trades_df['latency_ms'],
        nbinsx=40,
        marker_color='#00D9FF',
        name='Latency'
    ))
    
    # Add percentile lines
    p50 = trades_df['latency_ms'].quantile(0.50)
    p95 = trades_df['latency_ms'].quantile(0.95)
    p99 = trades_df['latency_ms'].quantile(0.99)
    
    fig.add_vline(x=p50, line_dash="dash", line_color="#FFD700", annotation_text=f"P50: {p50:.1f}ms")
    fig.add_vline(x=p95, line_dash="dash", line_color="#FF6B9D", annotation_text=f"P95: {p95:.1f}ms")
    fig.add_vline(x=p99, line_dash="dash", line_color="#FF0000", annotation_text=f"P99: {p99:.1f}ms")
    
    fig.update_xaxes(title="Latency (ms)")
    fig.update_yaxes(title="Frequency")
    fig.update_layout(title="Execution Latency Distribution")
    
    return apply_theme(fig, 400)


def chart_trade_size_distribution(trades_df: pd.DataFrame) -> Optional[go.Figure]:
    """61. Trade Size Distribution"""
    if trades_df is None or trades_df.empty or 'notional_value' not in trades_df.columns:
        return None
    
    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=trades_df['notional_value'],
        nbinsx=30,
        marker_color='#00D9FF',
        name='Trade Size'
    ))
    
    fig.update_xaxes(title="Notional Value (₹)", type='log')
    fig.update_yaxes(title="Frequency")
    fig.update_layout(title="Trade Size Distribution")
    
    return apply_theme(fig, 400)


def chart_time_of_day_performance(trades_df: pd.DataFrame) -> Optional[go.Figure]:
    """62. Time-of-Day Performance"""
    if trades_df is None or trades_df.empty:
        return None
    
    if 'timestamp' in trades_df.columns and 'pnl' in trades_df.columns:
        trades_df = trades_df.copy()
        trades_df['timestamp'] = pd.to_datetime(trades_df['timestamp'])
        trades_df['hour'] = trades_df['timestamp'].dt.hour
        
        hourly_pnl = trades_df.groupby('hour')['pnl'].sum()
        
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=hourly_pnl.index,
            y=hourly_pnl.values,
            marker_color=['#00D9FF' if v > 0 else '#FF6B9D' for v in hourly_pnl.values],
            name='Hourly P&L'
        ))
        
        fig.update_xaxes(title="Hour of Day", dtick=1)
        fig.update_yaxes(title="P&L (₹)")
        fig.update_layout(title="P&L by Hour of Day")
        
        return apply_theme(fig, 400)
    
    return None


def chart_strategy_attribution_live(trades_df: pd.DataFrame) -> Optional[go.Figure]:
    """63. Live Strategy Attribution"""
    if trades_df is None or trades_df.empty:
        return None
    
    if 'strategy' in trades_df.columns and 'pnl' in trades_df.columns:
        strategy_pnl = trades_df.groupby('strategy')['pnl'].sum().sort_values(ascending=True)
        
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=strategy_pnl.values,
            y=strategy_pnl.index,
            orientation='h',
            marker_color=['#00D9FF' if v > 0 else '#FF6B9D' for v in strategy_pnl.values],
            text=[f"₹{v:,.0f}" for v in strategy_pnl.values],
            textposition='auto'
        ))
        
        fig.update_xaxes(title="P&L (₹)")
        fig.update_yaxes(title="Strategy")
        fig.update_layout(title="Strategy Attribution (Today)")
        
        return apply_theme(fig, 450)
    
    return None


def chart_realtime_risk_metrics(risk_df: pd.DataFrame) -> Optional[go.Figure]:
    """64. Real-Time Risk Metrics"""
    if risk_df is None or risk_df.empty:
        return None
    
    if 'timestamp' in risk_df.columns and 'var_95' in risk_df.columns:
        risk_df = risk_df.copy()
        risk_df['timestamp'] = pd.to_datetime(risk_df['timestamp'])
        risk_df = risk_df.sort_values('timestamp')
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=risk_df['timestamp'],
            y=risk_df['var_95'],
            mode='lines',
            name='VaR 95%',
            line=dict(color='#FF6B9D', width=2)
        ))
        
        if 'exposure' in risk_df.columns:
            fig.add_trace(go.Scatter(
                x=risk_df['timestamp'],
                y=risk_df['exposure'],
                mode='lines',
                name='Gross Exposure',
                line=dict(color='#00D9FF', width=2),
                yaxis='y2'
            ))
        
        fig.update_xaxes(title="Time")
        fig.update_yaxes(title="VaR (₹)", secondary_y=False)
        fig.update_layout(
            title="Real-Time Risk Metrics",
            yaxis2=dict(title="Exposure (₹)", overlaying='y', side='right')
        )
        
        return apply_theme(fig, 400)
    
    return None



# ============================================================================
# VALUATION TAB CHARTS (65-74)
# ============================================================================

def chart_buffett_intrinsic_value(valuation_df: pd.DataFrame) -> Optional[go.Figure]:
    """65. Buffett Intrinsic Value vs Market Price"""
    if valuation_df is None or valuation_df.empty:
        return None
    
    if 'ticker' in valuation_df.columns and 'intrinsic_value' in valuation_df.columns and 'market_price' in valuation_df.columns:
        top_stocks = valuation_df.nlargest(15, 'margin_of_safety') if 'margin_of_safety' in valuation_df.columns else valuation_df.head(15)
        
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=top_stocks['ticker'],
            y=top_stocks['intrinsic_value'],
            name='Intrinsic Value',
            marker_color='#00D9FF'
        ))
        fig.add_trace(go.Bar(
            x=top_stocks['ticker'],
            y=top_stocks['market_price'],
            name='Market Price',
            marker_color='#FF6B9D'
        ))
        
        fig.update_xaxes(title="Symbol", tickangle=-45)
        fig.update_yaxes(title="Price (₹)")
        fig.update_layout(
            title="Buffett Intrinsic Value vs Market Price",
            barmode='group'
        )
        
        return apply_theme(fig, 500)
    
    return None


def chart_moat_score(valuation_df: pd.DataFrame) -> Optional[go.Figure]:
    """66. Economic Moat Scores"""
    if valuation_df is None or valuation_df.empty or 'moat_score' not in valuation_df.columns:
        return None
    
    top_moats = valuation_df.nlargest(20, 'moat_score')
    
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=top_moats['ticker'] if 'ticker' in top_moats.columns else top_moats.index,
        y=top_moats['moat_score'],
        marker_color='#00D9FF',
        text=[f"{v:.2f}" for v in top_moats['moat_score']],
        textposition='auto'
    ))
    
    fig.update_xaxes(title="Symbol", tickangle=-45)
    fig.update_yaxes(title="Moat Score", range=[0, 10])
    fig.update_layout(title="Top 20 Economic Moat Scores")
    
    return apply_theme(fig, 500)


def chart_owner_earnings(valuation_df: pd.DataFrame) -> Optional[go.Figure]:
    """67. Owner Earnings vs Reported Earnings"""
    if valuation_df is None or valuation_df.empty:
        return None
    
    if 'ticker' in valuation_df.columns and 'owner_earnings' in valuation_df.columns and 'reported_earnings' in valuation_df.columns:
        top_stocks = valuation_df.nlargest(15, 'owner_earnings')
        
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=top_stocks['ticker'],
            y=top_stocks['owner_earnings'],
            name='Owner Earnings',
            marker_color='#00D9FF'
        ))
        fig.add_trace(go.Bar(
            x=top_stocks['ticker'],
            y=top_stocks['reported_earnings'],
            name='Reported Earnings',
            marker_color='#FFD700'
        ))
        
        fig.update_xaxes(title="Symbol", tickangle=-45)
        fig.update_yaxes(title="Earnings (₹ Cr)")
        fig.update_layout(
            title="Owner Earnings vs Reported Earnings",
            barmode='group'
        )
        
        return apply_theme(fig, 500)
    
    return None


def chart_dcf_waterfall(ticker: str, dcf_components: dict) -> Optional[go.Figure]:
    """68. DCF Valuation Waterfall"""
    if not dcf_components:
        return None
    
    # Build waterfall components
    components = ['FCF', 'Growth', 'Terminal Value', 'Discount', 'Enterprise Value', 'Net Debt', 'Equity Value']
    values = [
        dcf_components.get('fcf', 0),
        dcf_components.get('growth_value', 0),
        dcf_components.get('terminal_value', 0),
        -dcf_components.get('discount_adjustment', 0),
        dcf_components.get('enterprise_value', 0),
        -dcf_components.get('net_debt', 0),
        dcf_components.get('equity_value', 0)
    ]
    
    fig = go.Figure(go.Waterfall(
        x=components,
        y=values,
        connector={"line": {"color": "rgb(63, 63, 63)"}},
        decreasing={"marker": {"color": "#FF6B9D"}},
        increasing={"marker": {"color": "#00D9FF"}},
        totals={"marker": {"color": "#FFD700"}}
    ))
    
    fig.update_xaxes(title="Component", tickangle=-45)
    fig.update_yaxes(title="Value (₹ Cr)")
    fig.update_layout(title=f"DCF Valuation Waterfall - {ticker}")
    
    return apply_theme(fig, 450)


def chart_earnings_quality(valuation_df: pd.DataFrame) -> Optional[go.Figure]:
    """69. Earnings Quality Score"""
    if valuation_df is None or valuation_df.empty or 'earnings_quality' not in valuation_df.columns:
        return None
    
    # Categorize earnings quality
    valuation_df = valuation_df.copy()
    valuation_df['quality_category'] = pd.cut(
        valuation_df['earnings_quality'],
        bins=[0, 3, 6, 10],
        labels=['Low', 'Medium', 'High']
    )
    
    quality_counts = valuation_df['quality_category'].value_counts()
    
    fig = go.Figure(data=[go.Bar(
        x=quality_counts.index,
        y=quality_counts.values,
        marker_color=['#FF6B9D', '#FFD700', '#00D9FF'],
        text=quality_counts.values,
        textposition='auto'
    )])
    
    fig.update_xaxes(title="Earnings Quality")
    fig.update_yaxes(title="Number of Stocks")
    fig.update_layout(title="Earnings Quality Distribution")
    
    return apply_theme(fig, 400)


def chart_accounting_distortions(valuation_df: pd.DataFrame) -> Optional[go.Figure]:
    """70. Accounting Distortion Flags"""
    if valuation_df is None or valuation_df.empty:
        return None
    
    distortion_cols = [col for col in valuation_df.columns if 'distortion' in col.lower() or 'flag' in col.lower()]
    
    if not distortion_cols:
        return None
    
    distortion_counts = {}
    for col in distortion_cols:
        distortion_counts[col.replace('_', ' ').title()] = valuation_df[col].sum() if valuation_df[col].dtype == bool else (valuation_df[col] > 0).sum()
    
    fig = go.Figure(data=[go.Bar(
        x=list(distortion_counts.keys()),
        y=list(distortion_counts.values()),
        marker_color='#FF6B9D',
        text=list(distortion_counts.values()),
        textposition='auto'
    )])
    
    fig.update_xaxes(title="Distortion Type", tickangle=-45)
    fig.update_yaxes(title="Number of Stocks Flagged")
    fig.update_layout(title="Accounting Distortion Flags")
    
    return apply_theme(fig, 450)


def chart_normalized_financials(valuation_df: pd.DataFrame, metric: str = 'roe') -> Optional[go.Figure]:
    """71. Normalized Financial Metrics"""
    if valuation_df is None or valuation_df.empty:
        return None
    
    raw_col = f'raw_{metric}'
    normalized_col = f'normalized_{metric}'
    
    if raw_col not in valuation_df.columns or normalized_col not in valuation_df.columns:
        return None
    
    top_stocks = valuation_df.nlargest(15, normalized_col)
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=top_stocks['ticker'] if 'ticker' in top_stocks.columns else top_stocks.index,
        y=top_stocks[raw_col],
        mode='markers',
        name='Raw',
        marker=dict(size=10, color='#FF6B9D', symbol='circle')
    ))
    fig.add_trace(go.Scatter(
        x=top_stocks['ticker'] if 'ticker' in top_stocks.columns else top_stocks.index,
        y=top_stocks[normalized_col],
        mode='markers',
        name='Normalized',
        marker=dict(size=10, color='#00D9FF', symbol='diamond')
    ))
    
    fig.update_xaxes(title="Symbol", tickangle=-45)
    fig.update_yaxes(title=f"{metric.upper()} (%)")
    fig.update_layout(title=f"Raw vs Normalized {metric.upper()}")
    
    return apply_theme(fig, 450)


def chart_sector_valuation(valuation_df: pd.DataFrame, sector_mapping: pd.DataFrame = None) -> Optional[go.Figure]:
    """72. Sector Valuation Comparison"""
    if valuation_df is None or valuation_df.empty:
        return None
    
    # Merge with sector mapping if provided
    if sector_mapping is not None and 'ticker' in valuation_df.columns:
        valuation_df = valuation_df.merge(sector_mapping, left_on='ticker', right_on='ticker', how='left')
    
    if 'sector' not in valuation_df.columns or 'pe_ratio' not in valuation_df.columns:
        return None
    
    sector_pe = valuation_df.groupby('sector')['pe_ratio'].median().sort_values(ascending=True)
    
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=sector_pe.values,
        y=sector_pe.index,
        orientation='h',
        marker_color='#00D9FF',
        text=[f"{v:.1f}x" for v in sector_pe.values],
        textposition='auto'
    ))
    
    fig.update_xaxes(title="Median P/E Ratio")
    fig.update_yaxes(title="Sector")
    fig.update_layout(title="Sector Valuation Comparison (P/E)")
    
    return apply_theme(fig, 500)


def chart_value_vs_growth(valuation_df: pd.DataFrame) -> Optional[go.Figure]:
    """73. Value vs Growth Scatter"""
    if valuation_df is None or valuation_df.empty:
        return None
    
    if 'pe_ratio' not in valuation_df.columns or 'earnings_growth' not in valuation_df.columns:
        return None
    
    # Filter outliers
    valuation_df = valuation_df[
        (valuation_df['pe_ratio'] > 0) & 
        (valuation_df['pe_ratio'] < 100) &
        (valuation_df['earnings_growth'].abs() < 100)
    ]
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=valuation_df['earnings_growth'],
        y=valuation_df['pe_ratio'],
        mode='markers',
        marker=dict(
            size=8,
            color=valuation_df['moat_score'] if 'moat_score' in valuation_df.columns else '#00D9FF',
            colorscale='Viridis',
            showscale=True,
            colorbar=dict(title="Moat Score"),
            opacity=0.6
        ),
        text=valuation_df['ticker'] if 'ticker' in valuation_df.columns else None,
        hovertemplate='<b>%{text}</b><br>Growth: %{x:.1f}%<br>P/E: %{y:.1f}x<extra></extra>'
    ))
    
    # Add PEG = 1 line
    growth_range = valuation_df['earnings_growth'].quantile([0.05, 0.95])
    fig.add_trace(go.Scatter(
        x=[growth_range.iloc[0], growth_range.iloc[1]],
        y=[growth_range.iloc[0], growth_range.iloc[1]],
        mode='lines',
        line=dict(color='#FF6B9D', dash='dash', width=2),
        name='PEG = 1'
    ))
    
    fig.update_xaxes(title="Earnings Growth (%)")
    fig.update_yaxes(title="P/E Ratio")
    fig.update_layout(title="Value vs Growth Analysis")
    
    return apply_theme(fig, 500)


def chart_margin_of_safety(valuation_df: pd.DataFrame) -> Optional[go.Figure]:
    """74. Margin of Safety Distribution"""
    if valuation_df is None or valuation_df.empty or 'margin_of_safety' not in valuation_df.columns:
        return None
    
    # Filter reasonable range
    mos_filtered = valuation_df[valuation_df['margin_of_safety'].between(-50, 100)]
    
    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=mos_filtered['margin_of_safety'],
        nbinsx=40,
        marker_color='#00D9FF',
        name='Margin of Safety'
    ))
    
    # Add vertical line at 0
    fig.add_vline(x=0, line_dash="dash", line_color="#FF6B9D", annotation_text="Fair Value")
    
    # Add vertical line at 25% (typical buy threshold)
    fig.add_vline(x=25, line_dash="dash", line_color="#00FF00", annotation_text="Buy Zone")
    
    fig.update_xaxes(title="Margin of Safety (%)")
    fig.update_yaxes(title="Number of Stocks")
    fig.update_layout(title="Margin of Safety Distribution")
    
    return apply_theme(fig, 450)
