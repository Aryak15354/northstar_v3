#!/usr/bin/env python3
"""
🏛️ REAL DATA CONSTITUTIONAL COCKPIT
Dashboard that shows YOUR actual data and reports - no mock data, no random changes

Features:
- Loads actual files from your data/ and reports/ directories
- Shows real institutional reports, validation results, and system state
- Persistent data that doesn't change on refresh
- Fixed color contrast for readability
- Professional styling
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import os
import sys
import json
import glob
import warnings
warnings.filterwarnings('ignore')

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# =========================== STREAMLIT CONFIG ===========================

st.set_page_config(
    layout="wide", 
    page_title="🏛️ Northstar V3 - Real Data Cockpit",
    initial_sidebar_state="collapsed"
)

# =========================== FIXED STYLING ===========================

st.markdown("""
<style>
    /* FIXED CONTRAST STYLING - DARK TEXT ON LIGHT BACKGROUNDS */
    
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    .main { 
        padding: 2rem !important; 
        font-family: 'Inter', sans-serif;
        background: #fafbfc;
        color: #1e293b !important;
    }
    
    /* Hide Streamlit branding */
    #MainMenu, footer, header, .stDeployButton, .stToolbar { 
        visibility: hidden !important; 
    }
    
    /* Professional header */
    .real-data-header {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #334155 100%);
        color: white !important;
        padding: 2rem;
        text-align: center;
        font-weight: 600;
        margin-bottom: 2rem;
        border-radius: 12px;
        box-shadow: 0 10px 25px rgba(0,0,0,0.1);
    }
    
    .header-title {
        font-size: 2.5rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
        color: white !important;
    }
    
    .header-subtitle {
        font-size: 1.125rem;
        opacity: 0.9;
        color: white !important;
    }
    
    /* Panel styling */
    .data-panel {
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 2rem;
        margin-bottom: 2rem;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
    }
    
    .panel-title {
        font-size: 1.5rem;
        font-weight: 600;
        color: #1e293b !important;
        margin-bottom: 1.5rem;
        padding-bottom: 0.75rem;
        border-bottom: 3px solid #3b82f6;
    }
    
    /* Metric cards */
    .metric-card {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 1.5rem;
        text-align: center;
        margin-bottom: 1rem;
    }
    
    .metric-value {
        font-size: 2rem;
        font-weight: 700;
        color: #1e293b !important;
        margin-bottom: 0.25rem;
    }
    
    .metric-label {
        font-size: 0.875rem;
        color: #64748b !important;
        font-weight: 500;
        text-transform: uppercase;
    }
    
    /* File info styling */
    .file-info {
        background: #f0f9ff;
        border: 1px solid #bae6fd;
        border-radius: 8px;
        padding: 1rem;
        margin: 1rem 0;
        font-family: 'Monaco', 'Menlo', monospace;
        font-size: 0.875rem;
        color: #0c4a6e !important;
    }
    
    .file-path {
        color: #1e40af !important;
        font-weight: 600;
    }
    
    /* Report content */
    .report-content {
        background: #fffbeb;
        border: 1px solid #fbbf24;
        border-radius: 8px;
        padding: 1.5rem;
        margin: 1rem 0;
        color: #92400e !important;
    }
    
    /* Data tables */
    .dataframe {
        border: none !important;
        border-radius: 8px !important;
    }
    
    .dataframe th {
        background: #f8fafc !important;
        color: #374151 !important;
        font-weight: 600 !important;
        padding: 1rem !important;
    }
    
    .dataframe td {
        color: #1e293b !important;
        padding: 0.75rem 1rem !important;
    }
    
    /* Status indicators */
    .status-pass { color: #059669 !important; font-weight: 600; }
    .status-fail { color: #dc2626 !important; font-weight: 600; }
    .status-healthy { color: #059669 !important; }
    .status-warning { color: #d97706 !important; }
    
    /* Ensure all text is dark */
    .stMarkdown, .stMarkdown p, .stMarkdown div, .stMarkdown span,
    .stDataFrame, .stTable, .stMetric {
        color: #1e293b !important;
    }
</style>
""", unsafe_allow_html=True)

# =========================== REAL DATA LOADING ===========================

@st.cache_data(ttl=60)  # Cache for 1 minute only to show fresh data
def load_actual_system_data():
    """Load actual data from your files - no mock data"""
    
    data = {
        'timestamp': datetime.now(),
        'files_loaded': [],
        'reports': {},
        'validation_results': {},
        'system_files': {},
        'portfolio_data': {},
        'error_log': []
    }
    
    try:
        # Load institutional reports
        institutional_dir = os.path.join(project_root, 'data/validation/institutional_complete')
        if os.path.exists(institutional_dir):
            institutional_files = glob.glob(os.path.join(institutional_dir, '*.md'))
            for file_path in institutional_files[-5:]:  # Last 5 reports
                try:
                    with open(file_path, 'r') as f:
                        content = f.read()
                    
                    file_name = os.path.basename(file_path)
                    data['reports'][file_name] = {
                        'path': file_path,
                        'content': content[:2000],  # First 2000 chars
                        'size': len(content),
                        'modified': datetime.fromtimestamp(os.path.getmtime(file_path))
                    }
                    data['files_loaded'].append(file_path)
                    
                    # Extract validation status
                    if 'PASS' in content:
                        data['validation_results']['status'] = 'PASS'
                    elif 'FAIL' in content:
                        data['validation_results']['status'] = 'FAIL'
                        
                except Exception as e:
                    data['error_log'].append(f"Error loading {file_path}: {e}")
        
        # Load system reports
        system_reports_dir = os.path.join(project_root, 'reports/system')
        if os.path.exists(system_reports_dir):
            system_files = glob.glob(os.path.join(system_reports_dir, '*.md'))
            for file_path in system_files[-3:]:  # Last 3 system reports
                try:
                    with open(file_path, 'r') as f:
                        content = f.read()
                    
                    file_name = os.path.basename(file_path)
                    data['system_files'][file_name] = {
                        'path': file_path,
                        'content': content[:1500],
                        'size': len(content),
                        'modified': datetime.fromtimestamp(os.path.getmtime(file_path))
                    }
                    data['files_loaded'].append(file_path)
                    
                except Exception as e:
                    data['error_log'].append(f"Error loading {file_path}: {e}")
        
        # Load universe data (your actual portfolio universe)
        universe_file = os.path.join(project_root, 'universe/nifty500.csv')
        if os.path.exists(universe_file):
            try:
                universe_df = pd.read_csv(universe_file)
                data['portfolio_data']['universe'] = {
                    'file': universe_file,
                    'total_stocks': len(universe_df),
                    'columns': list(universe_df.columns),
                    'sample_data': universe_df.head(10).to_dict('records') if len(universe_df) > 0 else [],
                    'modified': datetime.fromtimestamp(os.path.getmtime(universe_file))
                }
                data['files_loaded'].append(universe_file)
            except Exception as e:
                data['error_log'].append(f"Error loading universe: {e}")
        
        # Load any JSON state files
        json_files = [
            'data/state/unified_state.json',
            'data/deployment_state.json',
            'sealed_results.json'
        ]
        
        for json_file in json_files:
            full_path = os.path.join(project_root, json_file)
            if os.path.exists(full_path):
                try:
                    with open(full_path, 'r') as f:
                        json_content = json.load(f)
                    
                    data['system_files'][os.path.basename(json_file)] = {
                        'path': full_path,
                        'content': json.dumps(json_content, indent=2)[:1000],
                        'type': 'json',
                        'keys': list(json_content.keys()) if isinstance(json_content, dict) else [],
                        'modified': datetime.fromtimestamp(os.path.getmtime(full_path))
                    }
                    data['files_loaded'].append(full_path)
                    
                except Exception as e:
                    data['error_log'].append(f"Error loading {json_file}: {e}")
        
        # Load brutal period test results
        brutal_dir = os.path.join(project_root, 'data/validation/brutal_periods')
        if os.path.exists(brutal_dir):
            brutal_files = glob.glob(os.path.join(brutal_dir, '*.json'))
            for file_path in brutal_files[-2:]:  # Last 2 brutal period tests
                try:
                    with open(file_path, 'r') as f:
                        brutal_data = json.load(f)
                    
                    file_name = os.path.basename(file_path)
                    data['validation_results'][file_name] = {
                        'path': file_path,
                        'data': brutal_data,
                        'modified': datetime.fromtimestamp(os.path.getmtime(file_path))
                    }
                    data['files_loaded'].append(file_path)
                    
                except Exception as e:
                    data['error_log'].append(f"Error loading {file_path}: {e}")
        
        # Count different types of files in your system
        data['file_counts'] = {
            'total_reports': len(glob.glob(os.path.join(project_root, 'reports/**/*.md'), recursive=True)),
            'validation_files': len(glob.glob(os.path.join(project_root, 'data/validation/**/*'), recursive=True)),
            'data_files': len(glob.glob(os.path.join(project_root, 'data/**/*'), recursive=True)),
            'source_files': len(glob.glob(os.path.join(project_root, 'src/**/*.py'), recursive=True)),
            'test_files': len(glob.glob(os.path.join(project_root, 'tests/**/*.py'), recursive=True))
        }
        
    except Exception as e:
        data['error_log'].append(f"General error: {e}")
    
    return data

# =========================== DASHBOARD FUNCTIONS ===========================

def render_data_overview(data):
    """Show overview of your actual data"""
    
    st.markdown('<div class="data-panel">', unsafe_allow_html=True)
    st.markdown('<div class="panel-title">📊 YOUR ACTUAL DATA OVERVIEW</div>', unsafe_allow_html=True)
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{len(data['files_loaded'])}</div>
            <div class="metric-label">Files Loaded</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{len(data['reports'])}</div>
            <div class="metric-label">Reports Found</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        universe_count = data['portfolio_data'].get('universe', {}).get('total_stocks', 0)
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{universe_count}</div>
            <div class="metric-label">Universe Stocks</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        validation_status = data['validation_results'].get('status', 'Unknown')
        status_class = 'status-pass' if validation_status == 'PASS' else 'status-fail'
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value {status_class}">{validation_status}</div>
            <div class="metric-label">Last Validation</div>
        </div>
        """, unsafe_allow_html=True)
    
    # File counts
    if data.get('file_counts'):
        st.markdown("### Your System File Counts")
        counts = data['file_counts']
        
        col5, col6, col7, col8, col9 = st.columns(5)
        
        with col5:
            st.metric("Reports", counts['total_reports'])
        with col6:
            st.metric("Validation Files", counts['validation_files'])
        with col7:
            st.metric("Data Files", counts['data_files'])
        with col8:
            st.metric("Source Files", counts['source_files'])
        with col9:
            st.metric("Test Files", counts['test_files'])
    
    st.markdown('</div>', unsafe_allow_html=True)

def render_institutional_reports(data):
    """Show your actual institutional reports"""
    
    st.markdown('<div class="data-panel">', unsafe_allow_html=True)
    st.markdown('<div class="panel-title">📋 YOUR INSTITUTIONAL REPORTS</div>', unsafe_allow_html=True)
    
    if not data['reports']:
        st.warning("No institutional reports found in data/validation/institutional_complete/")
        st.markdown('</div>', unsafe_allow_html=True)
        return
    
    for report_name, report_info in data['reports'].items():
        st.markdown(f"### {report_name}")
        
        # File info
        st.markdown(f"""
        <div class="file-info">
            <strong>File:</strong> <span class="file-path">{report_info['path']}</span><br>
            <strong>Size:</strong> {report_info['size']:,} bytes<br>
            <strong>Modified:</strong> {report_info['modified'].strftime('%Y-%m-%d %H:%M:%S')}
        </div>
        """, unsafe_allow_html=True)
        
        # Report content preview
        st.markdown(f"""
        <div class="report-content">
            <strong>Content Preview:</strong><br>
            {report_info['content'][:1000]}...
        </div>
        """, unsafe_allow_html=True)
        
        # Show full content in expander
        with st.expander(f"View Full Report: {report_name}"):
            try:
                with open(report_info['path'], 'r') as f:
                    full_content = f.read()
                st.text(full_content)
            except Exception as e:
                st.error(f"Error reading full report: {e}")
    
    st.markdown('</div>', unsafe_allow_html=True)

def render_portfolio_universe(data):
    """Show your actual portfolio universe"""
    
    st.markdown('<div class="data-panel">', unsafe_allow_html=True)
    st.markdown('<div class="panel-title">🎯 YOUR PORTFOLIO UNIVERSE</div>', unsafe_allow_html=True)
    
    universe_data = data['portfolio_data'].get('universe')
    if not universe_data:
        st.warning("No universe data found in universe/nifty500.csv")
        st.markdown('</div>', unsafe_allow_html=True)
        return
    
    # Universe info
    st.markdown(f"""
    <div class="file-info">
        <strong>File:</strong> <span class="file-path">{universe_data['file']}</span><br>
        <strong>Total Stocks:</strong> {universe_data['total_stocks']}<br>
        <strong>Columns:</strong> {', '.join(universe_data['columns'])}<br>
        <strong>Modified:</strong> {universe_data['modified'].strftime('%Y-%m-%d %H:%M:%S')}
    </div>
    """, unsafe_allow_html=True)
    
    # Show sample data
    if universe_data['sample_data']:
        st.markdown("### Sample Data (First 10 Rows)")
        sample_df = pd.DataFrame(universe_data['sample_data'])
        st.dataframe(sample_df, use_container_width=True)
        
        # Show full universe file
        with st.expander("View Full Universe Data"):
            try:
                full_universe = pd.read_csv(universe_data['file'])
                st.dataframe(full_universe, use_container_width=True)
                
                # Basic stats
                st.markdown("### Universe Statistics")
                col1, col2 = st.columns(2)
                
                with col1:
                    st.metric("Total Stocks", len(full_universe))
                    if 'Sector' in full_universe.columns:
                        st.metric("Unique Sectors", full_universe['Sector'].nunique())
                
                with col2:
                    if 'Market Cap' in full_universe.columns:
                        st.metric("Avg Market Cap", f"₹{full_universe['Market Cap'].mean():,.0f}Cr")
                    
            except Exception as e:
                st.error(f"Error loading full universe: {e}")
    
    st.markdown('</div>', unsafe_allow_html=True)

def render_validation_results(data):
    """Show your actual validation results"""
    
    st.markdown('<div class="data-panel">', unsafe_allow_html=True)
    st.markdown('<div class="panel-title">✅ YOUR VALIDATION RESULTS</div>', unsafe_allow_html=True)
    
    if not data['validation_results']:
        st.warning("No validation results found")
        st.markdown('</div>', unsafe_allow_html=True)
        return
    
    # Show validation status
    status = data['validation_results'].get('status', 'Unknown')
    status_class = 'status-pass' if status == 'PASS' else 'status-fail'
    
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value {status_class}">VALIDATION {status}</div>
        <div class="metric-label">Latest Result</div>
    </div>
    """, unsafe_allow_html=True)
    
    # Show brutal period test results
    for file_name, result_info in data['validation_results'].items():
        if file_name.endswith('.json'):
            st.markdown(f"### {file_name}")
            
            st.markdown(f"""
            <div class="file-info">
                <strong>File:</strong> <span class="file-path">{result_info['path']}</span><br>
                <strong>Modified:</strong> {result_info['modified'].strftime('%Y-%m-%d %H:%M:%S')}
            </div>
            """, unsafe_allow_html=True)
            
            # Show test data
            test_data = result_info['data']
            if isinstance(test_data, dict):
                col1, col2 = st.columns(2)
                
                with col1:
                    for key, value in list(test_data.items())[:5]:
                        st.metric(key.replace('_', ' ').title(), str(value)[:50])
                
                with col2:
                    if len(test_data) > 5:
                        for key, value in list(test_data.items())[5:10]:
                            st.metric(key.replace('_', ' ').title(), str(value)[:50])
                
                # Full data in expander
                with st.expander(f"View Full Data: {file_name}"):
                    st.json(test_data)
    
    st.markdown('</div>', unsafe_allow_html=True)

def render_system_files(data):
    """Show your actual system files"""
    
    st.markdown('<div class="data-panel">', unsafe_allow_html=True)
    st.markdown('<div class="panel-title">⚙️ YOUR SYSTEM FILES</div>', unsafe_allow_html=True)
    
    if not data['system_files']:
        st.warning("No system files found")
        st.markdown('</div>', unsafe_allow_html=True)
        return
    
    for file_name, file_info in data['system_files'].items():
        st.markdown(f"### {file_name}")
        
        # File info
        st.markdown(f"""
        <div class="file-info">
            <strong>File:</strong> <span class="file-path">{file_info['path']}</span><br>
            <strong>Type:</strong> {file_info.get('type', 'text')}<br>
            <strong>Modified:</strong> {file_info['modified'].strftime('%Y-%m-%d %H:%M:%S')}
        </div>
        """, unsafe_allow_html=True)
        
        # Show JSON keys if it's a JSON file
        if file_info.get('keys'):
            st.markdown(f"**Keys:** {', '.join(file_info['keys'])}")
        
        # Content preview
        st.markdown(f"""
        <div class="report-content">
            <strong>Content Preview:</strong><br>
            <pre>{file_info['content']}</pre>
        </div>
        """, unsafe_allow_html=True)
        
        # Full content in expander
        with st.expander(f"View Full File: {file_name}"):
            try:
                with open(file_info['path'], 'r') as f:
                    full_content = f.read()
                
                if file_name.endswith('.json'):
                    try:
                        json_data = json.loads(full_content)
                        st.json(json_data)
                    except:
                        st.text(full_content)
                else:
                    st.text(full_content)
                    
            except Exception as e:
                st.error(f"Error reading file: {e}")
    
    st.markdown('</div>', unsafe_allow_html=True)

# =========================== MAIN DASHBOARD ===========================

def main():
    """Main dashboard showing your actual data"""
    
    # Header
    st.markdown("""
    <div class="real-data-header">
        <div class="header-title">🏛️ NORTHSTAR V3</div>
        <div class="header-subtitle">Real Data Constitutional Cockpit - Your Actual Files & Reports</div>
    </div>
    """, unsafe_allow_html=True)
    
    # Load your actual data
    with st.spinner("Loading your actual data files..."):
        data = load_actual_system_data()
    
    # Show any errors
    if data['error_log']:
        with st.expander("⚠️ Loading Errors", expanded=False):
            for error in data['error_log']:
                st.error(error)
    
    # Data overview
    render_data_overview(data)
    
    # Create tabs for different data types
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📋 Institutional Reports", 
        "🎯 Portfolio Universe", 
        "✅ Validation Results", 
        "⚙️ System Files",
        "📁 File Browser"
    ])
    
    with tab1:
        render_institutional_reports(data)
    
    with tab2:
        render_portfolio_universe(data)
    
    with tab3:
        render_validation_results(data)
    
    with tab4:
        render_system_files(data)
    
    with tab5:
        st.markdown('<div class="data-panel">', unsafe_allow_html=True)
        st.markdown('<div class="panel-title">📁 FILES LOADED THIS SESSION</div>', unsafe_allow_html=True)
        
        if data['files_loaded']:
            for i, file_path in enumerate(data['files_loaded'], 1):
                rel_path = os.path.relpath(file_path, project_root)
                file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
                mod_time = datetime.fromtimestamp(os.path.getmtime(file_path)) if os.path.exists(file_path) else "Unknown"
                
                st.markdown(f"""
                **{i}.** `{rel_path}`  
                Size: {file_size:,} bytes | Modified: {mod_time}
                """)
        else:
            st.warning("No files were loaded")
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Footer with real data info
    st.markdown(f"""
    <div style="text-align: center; color: #64748b; margin-top: 2rem; padding: 1rem; border-top: 1px solid #e2e8f0;">
        <strong>Real Data Dashboard</strong> | 
        Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 
        Files Loaded: {len(data['files_loaded'])} | 
        <span style="color: #059669;">●</span> Showing YOUR actual data (no mock data)
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()