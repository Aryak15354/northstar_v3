#!/usr/bin/env python3
"""
📊 STRATEGY INTELLIGENCE DASHBOARD PANEL
Visual interface for the learning financial organism

This creates the dashboard components that show:
- Strategy Belief Heatmap
- Regret Leaderboard  
- Bayesian Capital Weights
- Strategy Lifecycle Timeline

Usage:
    from src.dashboard.strategy_intelligence_panel import render_intelligence_panel
    
    render_intelligence_panel(st)
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
from datetime import datetime, timedelta

def load_strategy_beliefs():
    """Load strategy beliefs data"""
    
    beliefs_file = 'data/processed/strategy_beliefs.parquet'
    if os.path.exists(beliefs_file):
        try:
            beliefs_df = pd.read_parquet(beliefs_file)
            return beliefs_df
        except Exception as e:
            st.error(f"Error loading beliefs: {e}")
    
    return pd.DataFrame()

def load_strategy_regret():
    """Load strategy regret data"""
    
    regret_file = 'data/processed/strategy_regret.parquet'
    if os.path.exists(regret_file):
        try:
            regret_df = pd.read_parquet(regret_file)
            return regret_df
        except Exception as e:
            st.error(f"Error loading regret: {e}")
    
    return pd.DataFrame()

def load_capital_allocations():
    """Load current capital allocations"""
    
    alloc_file = 'data/processed/capital_allocations.json'
    if os.path.exists(alloc_file):
        try:
            import json
            with open(alloc_file, 'r') as f:
                data = json.load(f)
                return data.get('allocations', {})
        except Exception as e:
            st.error(f"Error loading allocations: {e}")
    
    return {}

def render_belief_heatmap(beliefs_df):
    """Render strategy belief heatmap"""
    
    st.subheader("🧠 Strategy Belief Heatmap")
    st.caption("Which models do we trust right now?")
    
    if beliefs_df.empty:
        st.warning("No belief data available")
        return
    
    # Get latest beliefs
    latest_beliefs = beliefs_df.sort_values('date').groupby('strategy').tail(1)
    
    if len(latest_beliefs) == 0:
        st.warning("No recent belief data")
        return
    
    # Prepare heatmap data
    heatmap_data = latest_beliefs[['strategy', 'skill_prob', 'sharpe', 'regime_fit', 'confidence']].copy()
    heatmap_data = heatmap_data.set_index('strategy')
    
    # Create heatmap
    fig = px.imshow(
        heatmap_data.T,
        aspect='auto',
        color_continuous_scale='RdYlGn',
        title="Strategy Trustworthiness Matrix",
        labels={'x': 'Strategy', 'y': 'Metric', 'color': 'Score'}
    )
    
    fig.update_layout(
        height=300,
        xaxis_tickangle=-45
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Status distribution
    col1, col2, col3, col4 = st.columns(4)
    
    status_counts = latest_beliefs['status'].value_counts()
    
    with col1:
        st.metric("Active", status_counts.get('ACTIVE', 0), delta=None)
    with col2:
        st.metric("Fading", status_counts.get('FADING', 0), delta=None)
    with col3:
        st.metric("Suspended", status_counts.get('SUSPENDED', 0), delta=None)
    with col4:
        avg_skill = latest_beliefs['skill_prob'].mean()
        st.metric("Avg Skill", f"{avg_skill:.1%}", delta=None)

def render_regret_leaderboard(regret_df):
    """Render regret leaderboard"""
    
    st.subheader("😈 Regret Leaderboard")
    st.caption("Who failed us when opportunity was highest?")
    
    if regret_df.empty:
        st.warning("No regret data available")
        return
    
    # Get latest regret for each strategy
    latest_regret = regret_df.sort_values('date').groupby('strategy').tail(1)
    
    # Sort by cumulative regret (worst first)
    regret_ranking = latest_regret.sort_values('cum_regret', ascending=False)
    
    # Display table
    display_cols = ['strategy', 'cum_regret', 'regret_30d', 'regret_90d', 'drawdown', 'penalty_score']
    display_data = regret_ranking[display_cols].copy()
    
    # Format percentages
    for col in ['cum_regret', 'regret_30d', 'regret_90d', 'drawdown']:
        display_data[col] = display_data[col].apply(lambda x: f"{x:.2%}")
    
    display_data['penalty_score'] = display_data['penalty_score'].apply(lambda x: f"{x:.2f}")
    
    # Rename columns for display
    display_data.columns = ['Strategy', 'Cum Regret', '30d Regret', '90d Regret', 'Drawdown', 'Penalty']
    
    st.dataframe(
        display_data.head(10),
        use_container_width=True,
        hide_index=True
    )
    
    # Regret distribution chart
    fig = px.histogram(
        latest_regret,
        x='cum_regret',
        nbins=20,
        title="Cumulative Regret Distribution",
        labels={'cum_regret': 'Cumulative Regret', 'count': 'Number of Strategies'}
    )
    
    fig.update_layout(height=300)
    st.plotly_chart(fig, use_container_width=True)

def render_capital_weights(allocations):
    """Render Bayesian capital weights"""
    
    st.subheader("⚖️ Bayesian Capital Weights")
    st.caption("These are not fixed — they move daily as beliefs update")
    
    if not allocations:
        st.warning("No allocation data available")
        return
    
    # Convert to DataFrame for plotting
    alloc_df = pd.DataFrame(list(allocations.items()), columns=['Strategy', 'Allocation'])
    alloc_df = alloc_df.sort_values('Allocation', ascending=True)
    
    # Create horizontal bar chart
    fig = px.bar(
        alloc_df,
        x='Allocation',
        y='Strategy',
        orientation='h',
        title="Current Capital Allocation",
        labels={'Allocation': 'Capital Allocation', 'Strategy': 'Strategy'},
        color='Allocation',
        color_continuous_scale='viridis'
    )
    
    fig.update_layout(
        height=max(400, len(alloc_df) * 30),
        showlegend=False
    )
    
    # Format as percentages
    fig.update_traces(
        texttemplate='%{x:.1%}',
        textposition='outside'
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Allocation metrics
    col1, col2, col3 = st.columns(3)
    
    with col1:
        total_allocated = sum(allocations.values())
        st.metric("Total Allocated", f"{total_allocated:.1%}")
    
    with col2:
        max_allocation = max(allocations.values()) if allocations else 0
        st.metric("Max Single", f"{max_allocation:.1%}")
    
    with col3:
        n_strategies = len(allocations)
        st.metric("Active Strategies", n_strategies)

def render_strategy_lifecycle(beliefs_df):
    """Render strategy lifecycle timeline"""
    
    st.subheader("📉 Strategy Lifecycle")
    st.caption("ACTIVE → FADING → SUSPENDED → REACTIVATED")
    
    if beliefs_df.empty:
        st.warning("No belief data available for lifecycle tracking")
        return
    
    # Get status changes over time
    lifecycle_data = []
    
    for strategy in beliefs_df['strategy'].unique():
        strategy_data = beliefs_df[beliefs_df['strategy'] == strategy].sort_values('date')
        
        for i, row in strategy_data.iterrows():
            lifecycle_data.append({
                'date': row['date'],
                'strategy': strategy,
                'status': row['status'],
                'skill_prob': row['skill_prob']
            })
    
    if not lifecycle_data:
        st.warning("No lifecycle data available")
        return
    
    lifecycle_df = pd.DataFrame(lifecycle_data)
    
    # Create timeline chart
    status_colors = {
        'ACTIVE': 'green',
        'FADING': 'orange', 
        'SUSPENDED': 'red',
        'REACTIVATED': 'blue'
    }
    
    fig = px.scatter(
        lifecycle_df,
        x='date',
        y='strategy',
        color='status',
        size='skill_prob',
        title="Strategy Status Evolution",
        color_discrete_map=status_colors,
        hover_data=['skill_prob']
    )
    
    fig.update_layout(
        height=max(400, len(lifecycle_df['strategy'].unique()) * 30),
        xaxis_title="Date",
        yaxis_title="Strategy"
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Status transition summary
    if len(beliefs_df) > 1:
        st.subheader("📊 Status Transitions")
        
        # Calculate transitions
        transitions = []
        for strategy in beliefs_df['strategy'].unique():
            strategy_data = beliefs_df[beliefs_df['strategy'] == strategy].sort_values('date')
            
            if len(strategy_data) > 1:
                for i in range(1, len(strategy_data)):
                    prev_status = strategy_data.iloc[i-1]['status']
                    curr_status = strategy_data.iloc[i]['status']
                    
                    if prev_status != curr_status:
                        transitions.append({
                            'strategy': strategy,
                            'from_status': prev_status,
                            'to_status': curr_status,
                            'date': strategy_data.iloc[i]['date']
                        })
        
        if transitions:
            transitions_df = pd.DataFrame(transitions)
            
            # Show recent transitions
            recent_transitions = transitions_df.sort_values('date', ascending=False).head(10)
            
            st.dataframe(
                recent_transitions[['date', 'strategy', 'from_status', 'to_status']],
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("No status transitions detected")

def render_intelligence_panel():
    """Main function to render the complete intelligence panel"""
    
    st.title("🧬 Strategy Intelligence Panel")
    st.markdown("**The Learning Financial Organism**")
    
    # Load data
    beliefs_df = load_strategy_beliefs()
    regret_df = load_strategy_regret()
    allocations = load_capital_allocations()
    
    # Check if intelligence system is active
    intelligence_file = 'data/processed/strategy_intelligence_summary.json'
    intelligence_active = False
    
    if os.path.exists(intelligence_file):
        try:
            import json
            with open(intelligence_file, 'r') as f:
                summary = json.load(f)
                intelligence_active = summary.get('system_health', {}).get('intelligence_active', False)
        except:
            pass
    
    # Status indicator
    if intelligence_active:
        st.success("🧬 Intelligence System: ACTIVE")
    else:
        st.warning("🧬 Intelligence System: INITIALIZING")
    
    # Create tabs for different views
    tab1, tab2, tab3, tab4 = st.tabs([
        "🧠 Beliefs", 
        "😈 Regret", 
        "⚖️ Capital", 
        "📉 Lifecycle"
    ])
    
    with tab1:
        render_belief_heatmap(beliefs_df)
    
    with tab2:
        render_regret_leaderboard(regret_df)
    
    with tab3:
        render_capital_weights(allocations)
    
    with tab4:
        render_strategy_lifecycle(beliefs_df)
    
    # Intelligence summary at bottom
    if intelligence_active and os.path.exists(intelligence_file):
        with st.expander("🔍 Intelligence System Details"):
            try:
                import json
                with open(intelligence_file, 'r') as f:
                    summary = json.load(f)
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.json(summary.get('strategy_insights', {}))
                
                with col2:
                    st.json(summary.get('system_health', {}))
                    
            except Exception as e:
                st.error(f"Error loading intelligence summary: {e}")

if __name__ == "__main__":
    # For testing
    render_intelligence_panel()