#!/usr/bin/env python3
"""
Tab 6: System Operations

Replaces automation_dashboard.py. Shows system health, data pipeline status,
state reconciliation results, and cron job health.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.dashboard.data_contract import DashboardDataContract

from src.dashboard.components.charts import (
    create_heatmap,
    create_bar_chart,
    create_gauge_chart,
    THEME
)


def render(contract: 'DashboardDataContract'):
    """Render the System Operations tab"""
    
    st.header("🔧 System Operations")
    
    # Row 1: System Health Overview
    st.subheader("System Health")
    
    health = contract.get_system_health()
    
    if health.is_available:
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            health_score = health.value.get('overall_health_score', 0.0)
            st.metric("Health Score", f"{health_score:.1%}")
        
        with col2:
            health_status = health.value.get('health_status', 'unknown')
            st.metric("Status", health_status.upper())
        
        with col3:
            data_fresh = health.value.get('data_fresh', False)
            st.metric("Data Fresh", "✅ Yes" if data_fresh else "❌ No")
        
        with col4:
            freshness_hours = health.value.get('data_freshness_hours', 0.0)
            st.metric("Data Age", f"{freshness_hours:.1f}h")
        
        st.caption(f"Source: {health.source} | Freshness: {health.freshness.value}")
    else:
        st.error(f"System health unavailable: {health.unavailability_reason}")
    
    # Row 2: Component Health
    if health.is_available:
        st.subheader("Component Status")
        
        col1, col2 = st.columns([6, 4])
        
        with col1:
            components_healthy = health.value.get('components_healthy', 0)
            total_components = health.value.get('total_components', 0)
            component_availability = health.value.get('component_availability', 0.0)
            
            st.metric("Healthy Components", f"{components_healthy}/{total_components}")
            st.metric("Component Availability", f"{component_availability:.1%}")
            
            # Component health breakdown
            component_status = health.value.get('component_status', {})
            
            if component_status:
                # Create bar chart of component health
                components = list(component_status.keys())
                statuses = [1 if status == 'healthy' else 0.5 if status == 'degraded' else 0 
                           for status in component_status.values()]
                
                fig = create_bar_chart(
                    labels=components,
                    values=statuses,
                    title="Component Health Status",
                    y_label="Status (1=Healthy, 0.5=Degraded, 0=Down)",
                    color_by_value=True,
                    height=350
                )
                st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # System health gauge
            health_score = health.value.get('overall_health_score', 0.0)
            
            fig = create_gauge_chart(
                value=health_score * 100,
                title="Overall System Health",
                min_val=0,
                max_val=100,
                threshold_low=60,
                threshold_high=85,
                height=300
            )
            st.plotly_chart(fig, use_container_width=True)
    
    # Row 3: Data Pipeline Health
    st.subheader("Data Pipeline Health")
    
    pipeline_health = contract.get_data_pipeline_health()
    
    if pipeline_health.is_available:
        health_data = pipeline_health.value
        
        # Display pipeline health metrics
        if isinstance(health_data, dict):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                ingestion_health = health_data.get('ingestion_health', 'unknown')
                health_emoji = "🟢" if ingestion_health == 'healthy' else "🟡" if ingestion_health == 'degraded' else "🔴"
                st.metric(f"{health_emoji} Ingestion Health", ingestion_health.upper())
            
            with col2:
                last_update = health_data.get('last_successful_update', 'N/A')
                st.metric("Last Update", last_update)
            
            with col3:
                failed_loaders = health_data.get('failed_loaders', 0)
                st.metric("Failed Loaders", failed_loaders)
            
            # Loader status table
            loader_status = health_data.get('loader_status', {})
            
            if loader_status:
                st.markdown("**Loader Status:**")
                
                loader_list = []
                for loader_name, status in loader_status.items():
                    loader_list.append({
                        'Loader': loader_name,
                        'Status': status.get('status', 'unknown') if isinstance(status, dict) else status,
                        'Last Run': status.get('last_run', 'N/A') if isinstance(status, dict) else 'N/A',
                        'Records': status.get('records_loaded', 0) if isinstance(status, dict) else 0
                    })
                
                if loader_list:
                    df_loaders = pd.DataFrame(loader_list)
                    st.dataframe(df_loaders, use_container_width=True, hide_index=True)
        
        st.caption(f"Source: {pipeline_health.source} | Freshness: {pipeline_health.freshness.value}")
    else:
        st.info(f"Pipeline health unavailable: {pipeline_health.unavailability_reason}")
    
    # Row 3: State Reconciliation
    st.subheader("State Reconciliation")
    
    reconciliation = contract.get_state_reconciliation_status()
    
    if reconciliation.is_available:
        st.success("✅ State reconciliation active")
        st.json(reconciliation.value)
    else:
        st.info(f"ℹ️ {reconciliation.unavailability_reason}")
    
    # Row 4: Automation Status
    st.subheader("Automation & Cron Jobs")
    
    automation_status = contract.get_automation_status()
    
    if automation_status.is_available:
        status_data = automation_status.value
        
        if isinstance(status_data, dict):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                active_jobs = status_data.get('active_jobs', 0)
                st.metric("Active Jobs", active_jobs)
            
            with col2:
                failed_jobs = status_data.get('failed_jobs', 0)
                st.metric("Failed Jobs", failed_jobs)
            
            with col3:
                last_run = status_data.get('last_run', 'N/A')
                st.metric("Last Run", last_run)
            
            # Job status table
            job_status = status_data.get('job_status', {})
            
            if job_status:
                st.markdown("**Job Status:**")
                
                job_list = []
                for job_name, status in job_status.items():
                    job_list.append({
                        'Job': job_name,
                        'Status': status.get('status', 'unknown') if isinstance(status, dict) else status,
                        'Last Run': status.get('last_run', 'N/A') if isinstance(status, dict) else 'N/A',
                        'Next Run': status.get('next_run', 'N/A') if isinstance(status, dict) else 'N/A'
                    })
                
                if job_list:
                    df_jobs = pd.DataFrame(job_list)
                    st.dataframe(df_jobs, use_container_width=True, hide_index=True)
        
        st.caption(f"Source: {automation_status.source} | Freshness: {automation_status.freshness.value}")
    else:
        st.info(f"Automation status unavailable: {automation_status.unavailability_reason}")
    
    # Row 5: State Write Log
    st.subheader("Recent State Changes")
    
    state_log = contract.get_state_write_log(last_n=20)
    
    if state_log.is_available and state_log.value:
        log_entries = state_log.value
        
        if isinstance(log_entries, list):
            # Convert to DataFrame
            log_list = []
            for entry in log_entries[-10:]:  # Show last 10
                if isinstance(entry, dict):
                    log_list.append({
                        'Timestamp': entry.get('timestamp', 'N/A'),
                        'Component': entry.get('component', 'N/A'),
                        'Action': entry.get('action', 'N/A'),
                        'Status': entry.get('status', 'N/A')
                    })
            
            if log_list:
                df_log = pd.DataFrame(log_list)
                st.dataframe(df_log, use_container_width=True, hide_index=True)
        
        st.caption(f"Source: {state_log.source} | As of: {state_log.as_of}")
    else:
        st.info(f"State change log unavailable: {state_log.unavailability_reason}")
