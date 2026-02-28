#!/usr/bin/env python3
'''
📈 AUTOMATION DASHBOARD
Simple web dashboard for automation status
'''

import streamlit as st
import json
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
import plotly.graph_objects as go

project_root = Path(__file__).parent.parent

st.set_page_config(page_title="Northstar Automation Dashboard", layout="wide")

st.title("🤖 Northstar Automation Dashboard")

# Load execution summaries
summaries_path = project_root / 'data' / 'execution_summaries'

if summaries_path.exists():
    summary_files = sorted(summaries_path.glob('*.json'), reverse=True)[:30]  # Last 30 executions
    
    if summary_files:
        summaries = []
        for file in summary_files:
            with open(file, 'r') as f:
                summaries.append(json.load(f))
        
        # Create DataFrame
        df = pd.DataFrame(summaries)
        df['execution_date'] = pd.to_datetime(df['execution_date'])
        
        # Metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            avg_success_rate = df['success_rate'].mean()
            st.metric("Avg Success Rate", f"{avg_success_rate:.1%}")
        
        with col2:
            avg_duration = df['execution_duration'].mean()
            st.metric("Avg Duration", f"{avg_duration:.1f}s")
        
        with col3:
            last_execution = df['execution_date'].max()
            st.metric("Last Execution", last_execution.strftime('%Y-%m-%d'))
        
        with col4:
            total_executions = len(df)
            st.metric("Total Executions", total_executions)
        
        # Success rate chart
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df['execution_date'],
            y=df['success_rate'] * 100,
            mode='lines+markers',
            name='Success Rate'
        ))
        
        fig.update_layout(
            title="Success Rate Over Time",
            xaxis_title="Date",
            yaxis_title="Success Rate (%)",
            height=400
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Recent executions table
        st.subheader("Recent Executions")
        display_df = df[['execution_date', 'execution_duration', 'success_rate', 'successful_components', 'total_components']].copy()
        display_df['execution_date'] = display_df['execution_date'].dt.strftime('%Y-%m-%d %H:%M')
        st.dataframe(display_df, use_container_width=True)
    else:
        st.warning("No execution summaries found")
else:
    st.error("Execution summaries directory not found")
