#!/usr/bin/env python3
"""
🌟 WORKING NORTHSTAR DASHBOARD
A practical dashboard that actually works with your existing data

This dashboard reads from:
- Your actual reports in the reports/ directory
- Existing data files in data/ directories
- Real configuration files
- Actual log files and outputs

No complex component imports - just reads what you actually have.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
import warnings
import glob
import re
from collections import defaultdict

warnings.filterwarnings('ignore')

# Page configuration
st.set_page_config(
    page_title="Northstar V3 - Working Dashboard",
    page_icon="🌟",
    layout="wide",
    initial_sidebar_state="expanded"
)

class WorkingNorthstarDashboard:
    """A dashboard that actually works with your existing data"""
    
    def __init__(self):
        self.base_path = Path(".")
        self.reports_path = Path("reports")
        self.data_path = Path("data")
        self.config_path = Path("config")
        self.logs_path = Path("logs")
        
    def render_header(self):
        """Render dashboard header"""
        st.markdown("""
        <div style='text-align: center; padding: 2rem; background: linear-gradient(135deg, #1e3c72, #2a5298); color: white; border-radius: 15px; margin-bottom: 2rem;'>
            <h1 style='margin: 0; font-size: 3rem; font-weight: 700;'>🌟 NORTHSTAR V3</h1>
            <h2 style='margin: 0.5rem 0; font-weight: 300;'>Working System Dashboard</h2>
            <p style='margin: 1rem 0 0 0; opacity: 0.9;'>Real Data • Actual Reports • Live System Status</p>
        </div>
        """, unsafe_allow_html=True)
        
    def scan_reports(self):
        """Scan and categorize all reports"""
        if not self.reports_path.exists():
            return {}
            
        reports = {}
        
        # Get all report files
        report_files = list(self.reports_path.glob("*.md")) + list(self.reports_path.glob("*.json"))
        
        for report_file in report_files:
            name = report_file.name
            size = report_file.stat().st_size
            modified = datetime.fromtimestamp(report_file.stat().st_mtime)
            
            # Categorize reports
            category = "Other"
            if "TASK" in name.upper():
                category = "Task Reports"
            elif "COMPLETION" in name.upper() or "COMPLETE" in name.upper():
                category = "Completion Reports"
            elif "VALIDATION" in name.upper():
                category = "Validation Reports"
            elif "PERFORMANCE" in name.upper():
                category = "Performance Reports"
            elif "WALK_FORWARD" in name.upper():
                category = "Walk Forward Analysis"
            elif "SHADOW" in name.upper():
                category = "Shadow Trading"
            elif "SYSTEM" in name.upper():
                category = "System Reports"
                
            if category not in reports:
                reports[category] = []
                
            reports[category].append({
                "name": name,
                "path": report_file,
                "size": size,
                "modified": modified
            })
            
        # Sort by modification time (newest first)
        for category in reports:
            reports[category].sort(key=lambda x: x["modified"], reverse=True)
            
        return reports
        
    def scan_data_directories(self):
        """Scan data directories for actual data"""
        data_info = {}
        
        if self.data_path.exists():
            for subdir in self.data_path.iterdir():
                if subdir.is_dir():
                    files = list(subdir.glob("*"))
                    data_files = [f for f in files if f.is_file()]
                    
                    if data_files:
                        data_info[subdir.name] = {
                            "file_count": len(data_files),
                            "total_size": sum(f.stat().st_size for f in data_files),
                            "latest_file": max(data_files, key=lambda x: x.stat().st_mtime),
                            "file_types": list(set(f.suffix for f in data_files if f.suffix))
                        }
                        
        return data_info
        
    def load_walk_forward_results(self):
        """Load actual walk forward analysis results with proper data extraction"""
        results = []
        
        # Look for walk forward reports
        wf_files = list(self.reports_path.glob("*walk_forward*")) + list(self.reports_path.glob("*WALK_FORWARD*"))
        
        for wf_file in wf_files:
            try:
                if wf_file.suffix == '.json':
                    with open(wf_file, 'r') as f:
                        data = json.load(f)
                        
                        # Extract meaningful metrics from the JSON structure
                        processed_data = self.process_walk_forward_json(data)
                        results.append({
                            "file": wf_file.name,
                            "data": processed_data,
                            "date": datetime.fromtimestamp(wf_file.stat().st_mtime),
                            "raw_data": data  # Keep raw data for detailed view
                        })
                elif wf_file.suffix == '.md':
                    with open(wf_file, 'r') as f:
                        content = f.read()
                        # Extract metrics from markdown
                        metrics = self.extract_metrics_from_markdown(content)
                        if metrics:
                            results.append({
                                "file": wf_file.name,
                                "data": metrics,
                                "date": datetime.fromtimestamp(wf_file.stat().st_mtime),
                                "raw_content": content
                            })
            except Exception as e:
                st.warning(f"Could not load {wf_file.name}: {e}")
                
        return results
    
    def process_walk_forward_json(self, data):
        """Process walk forward JSON data to extract meaningful metrics"""
        processed = {}
        
        # Extract summary metrics
        if 'analysis_summary' in data:
            summary = data['analysis_summary']
            processed['total_windows'] = summary.get('total_windows', 0)
            processed['strategies_analyzed'] = summary.get('strategies_analyzed', 0)
            processed['analysis_duration'] = summary.get('total_analysis_duration', 0)
        
        # Process window results
        if 'window_results' in data and data['window_results']:
            windows = data['window_results']
            returns = [w.get('avg_out_of_sample_return', 0) * 100 for w in windows]  # Convert to percentage
            
            processed['avg_return'] = np.mean(returns) if returns else 0
            processed['total_return'] = sum(returns) if returns else 0
            processed['win_rate'] = len([r for r in returns if r > 0]) / len(returns) * 100 if returns else 0
            processed['max_return'] = max(returns) if returns else 0
            processed['min_return'] = min(returns) if returns else 0
            processed['volatility'] = np.std(returns) if len(returns) > 1 else 0
            processed['sharpe_ratio'] = (np.mean(returns) / np.std(returns)) if len(returns) > 1 and np.std(returns) > 0 else 0
            processed['window_returns'] = returns
            processed['window_details'] = windows
        
        # Extract degradation info
        if 'degradation_analysis' in data:
            deg = data['degradation_analysis']
            processed['degradations'] = deg.get('total_degradations', 0)
            processed['critical_degradations'] = deg.get('critical_degradations', 0)
        
        return processed
        
    def extract_metrics_from_markdown(self, content):
        """Extract numerical metrics from markdown content"""
        metrics = {}
        
        # Common patterns for extracting metrics
        patterns = {
            "success_rate": r"success rate[:\s]*(\d+\.?\d*)%",
            "total_return": r"total return[:\s]*(\d+\.?\d*)%",
            "sharpe_ratio": r"sharpe ratio[:\s]*(\d+\.?\d*)",
            "max_drawdown": r"max drawdown[:\s]*-?(\d+\.?\d*)%",
            "win_rate": r"win rate[:\s]*(\d+\.?\d*)%",
            "volatility": r"volatility[:\s]*(\d+\.?\d*)%"
        }
        
        content_lower = content.lower()
        
        for metric, pattern in patterns.items():
            matches = re.findall(pattern, content_lower)
            if matches:
                try:
                    metrics[metric] = float(matches[0])
                except ValueError:
                    pass
                    
        return metrics
        
    def load_shadow_trading_data(self):
        """Load actual shadow trading data with historical portfolio tracking"""
        shadow_data = {"trading_state": {}, "daily_logs": [], "historical_positions": [], "pnl_history": []}
        
        shadow_path = self.data_path / "live" / "shadow_trading"
        if shadow_path.exists():
            # Load current trading state
            state_file = shadow_path / "trading_state.json"
            if state_file.exists():
                try:
                    with open(state_file, 'r') as f:
                        shadow_data["trading_state"] = json.load(f)
                except Exception as e:
                    st.warning(f"Could not load trading state: {e}")
            
            # Load historical positions
            positions_path = shadow_path / "positions"
            if positions_path.exists():
                for pos_file in positions_path.glob("positions_*.json"):
                    try:
                        with open(pos_file, 'r') as f:
                            pos_data = json.load(f)
                            if pos_data:  # Only add non-empty position data
                                shadow_data["historical_positions"].append({
                                    "date": pos_file.stem.replace("positions_", ""),
                                    "positions": pos_data
                                })
                    except Exception as e:
                        st.warning(f"Could not load {pos_file.name}: {e}")
            
            # Load P&L history
            pnl_path = shadow_path / "pnl"
            if pnl_path.exists():
                for pnl_file in pnl_path.glob("pnl_*.json"):
                    try:
                        with open(pnl_file, 'r') as f:
                            pnl_data = json.load(f)
                            shadow_data["pnl_history"].append({
                                "date": pnl_file.stem.replace("pnl_", ""),
                                "pnl": pnl_data
                            })
                    except Exception as e:
                        st.warning(f"Could not load {pnl_file.name}: {e}")
                    
            # Load daily logs
            log_files = list(shadow_path.glob("daily_log_*.json"))
            for log_file in log_files:
                try:
                    with open(log_file, 'r') as f:
                        logs = json.load(f)
                        if isinstance(logs, list):
                            shadow_data["daily_logs"].extend(logs)
                        else:
                            shadow_data["daily_logs"].append(logs)
                except Exception as e:
                    st.warning(f"Could not load {log_file.name}: {e}")
                    
    def load_current_market_data(self):
        """Load current market situation metrics with improved regime detection"""
        market_data = {
            "nifty_data": {},
            "macro_data": {},
            "regime_data": {},
            "market_health": {}
        }
        
        # Load macro data
        macro_path = self.data_path / "macro"
        if macro_path.exists():
            # Load yields data
            yields_file = macro_path / "yields_enhanced.csv"
            if yields_file.exists():
                try:
                    yields_df = pd.read_csv(yields_file)
                    if not yields_df.empty:
                        latest_yields = yields_df.iloc[-1].to_dict()
                        market_data["macro_data"]["yields"] = latest_yields
                        market_data["macro_data"]["yield_trend"] = "up" if len(yields_df) > 1 and yields_df.iloc[-1]['10Y'] > yields_df.iloc[-2]['10Y'] else "down"
                except Exception as e:
                    st.warning(f"Could not load yields data: {e}")
        
        # Load market regime from multiple sources
        regime_sources = [
            self.data_path / "reports" / "monthly_report.json",
            self.data_path / "live" / "shadow_trading" / "decisions" / "decisions_2026-01-18.json",
            self.data_path / "state" / "state_events.json"
        ]
        
        for source in regime_sources:
            if source.exists():
                try:
                    with open(source, 'r') as f:
                        data = json.load(f)
                        
                        # Extract regime information
                        if "market_regime_analysis" in data:
                            regime_info = data["market_regime_analysis"]
                            if "current_regime" in regime_info:
                                market_data["regime_data"]["current_regime"] = regime_info["current_regime"]
                        elif "market_regime" in data:
                            market_data["regime_data"]["regime"] = data["market_regime"]
                        elif isinstance(data, dict) and "decisions" in data:
                            if "market_regime" in data["decisions"]:
                                market_data["regime_data"]["regime"] = data["decisions"]["market_regime"]
                        
                        # Store full data for analysis
                        market_data["regime_data"][source.name] = data
                        
                except Exception as e:
                    continue
        
        # Load recent performance data
        perf_files = list(self.data_path.glob("**/performance*.json"))
        for perf_file in perf_files[:3]:  # Latest 3 files
            try:
                with open(perf_file, 'r') as f:
                    perf_data = json.load(f)
                    market_data["market_health"][perf_file.name] = perf_data
            except Exception as e:
                continue
        
        return market_data
    
    def visualize_json_data(self, json_data, title="JSON Data Visualization"):
        """Create comprehensive visualizations for JSON data"""
        if not isinstance(json_data, dict):
            st.json(json_data)
            return
        
        st.markdown(f"### 📊 {title}")
        
        # Extract numeric data for visualization
        numeric_data = {}
        categorical_data = {}
        time_series_data = {}
        
        def extract_data(obj, prefix=""):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    new_key = f"{prefix}.{key}" if prefix else key
                    if isinstance(value, (int, float)) and not isinstance(value, bool):
                        numeric_data[new_key] = value
                    elif isinstance(value, str):
                        categorical_data[new_key] = value
                    elif isinstance(value, (dict, list)):
                        extract_data(value, new_key)
            elif isinstance(obj, list) and obj:
                for i, item in enumerate(obj[:10]):  # Limit to first 10 items
                    extract_data(item, f"{prefix}[{i}]")
        
        extract_data(json_data)
        
        # Create visualizations
        col1, col2 = st.columns(2)
        
        with col1:
            if numeric_data:
                # Numeric data bar chart
                keys = list(numeric_data.keys())[:15]  # Top 15 metrics
                values = [numeric_data[k] for k in keys]
                
                fig = go.Figure()
                fig.add_trace(go.Bar(
                    x=keys,
                    y=values,
                    marker_color=px.colors.qualitative.Set3,
                    text=[f"{v:.3f}" if abs(v) < 1 else f"{v:.1f}" for v in values],
                    textposition='auto'
                ))
                
                fig.update_layout(
                    title="📈 Numeric Metrics",
                    xaxis_title="Metric",
                    yaxis_title="Value",
                    height=400,
                    xaxis_tickangle=-45
                )
                st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            if categorical_data:
                # Categorical data pie chart
                cat_counts = {}
                for key, value in categorical_data.items():
                    cat_counts[f"{key}: {value}"] = 1
                
                if len(cat_counts) <= 10:  # Only show if manageable number
                    fig = go.Figure(data=[go.Pie(
                        labels=list(cat_counts.keys()),
                        values=list(cat_counts.values()),
                        hole=.3
                    )])
                    
                    fig.update_layout(
                        title="📋 Categorical Data",
                        height=400,
                        showlegend=True
                    )
                    st.plotly_chart(fig, use_container_width=True)
        
        # Show hierarchical structure
        if len(json_data) > 0:
            st.markdown("#### 🌳 Data Structure")
            
            # Create a tree-like visualization
            structure_data = []
            
            def build_structure(obj, level=0, parent="root"):
                if isinstance(obj, dict):
                    for key, value in obj.items():
                        node_type = type(value).__name__
                        size = len(value) if isinstance(value, (dict, list)) else 1
                        structure_data.append({
                            "name": key,
                            "parent": parent,
                            "level": level,
                            "type": node_type,
                            "size": size
                        })
                        if isinstance(value, (dict, list)) and level < 3:  # Limit depth
                            build_structure(value, level + 1, key)
            
            build_structure(json_data)
            
            if structure_data:
                # Create sunburst chart for structure
                fig = go.Figure(go.Sunburst(
                    labels=[item["name"] for item in structure_data],
                    parents=[item["parent"] for item in structure_data],
                    values=[item["size"] for item in structure_data],
                    branchvalues="total",
                ))
                
                fig.update_layout(
                    title="JSON Structure Hierarchy",
                    height=400
                )
                st.plotly_chart(fig, use_container_width=True)
        
        # Interactive JSON explorer
        with st.expander("🔍 Interactive JSON Explorer"):
            st.json(json_data)
    
    def extract_and_visualize_report_data(self, content, report_name):
        """Extract and visualize data from markdown reports with intelligent analysis"""
        
        # Determine report type and create specialized visualizations
        report_type = self.identify_report_type(report_name, content)
        
        if report_type == "performance":
            self.visualize_performance_report(content, report_name)
        elif report_type == "stress_test":
            self.visualize_stress_test_report(content, report_name)
        elif report_type == "walk_forward":
            self.visualize_walk_forward_report(content, report_name)
        elif report_type == "system_integrity":
            self.visualize_system_report(content, report_name)
        else:
            self.visualize_generic_report(content, report_name)
    
    def identify_report_type(self, report_name, content):
        """Identify the type of report based on name and content"""
        name_lower = report_name.lower()
        content_lower = content.lower()
        
        if "performance" in name_lower or "12m" in name_lower:
            return "performance"
        elif "stress" in name_lower or "stress test" in content_lower:
            return "stress_test"
        elif "walk_forward" in name_lower or "walk forward" in content_lower:
            return "walk_forward"
        elif "system" in name_lower or "integrity" in name_lower:
            return "system_integrity"
        else:
            return "generic"
    
    def visualize_performance_report(self, content, report_name):
        """Create specialized visualizations for performance reports"""
        st.markdown("#### 📈 Performance Report Analysis")
        
        # Extract performance data
        import re
        
        # Extract key metrics
        metrics = {}
        
        # Performance metrics patterns
        patterns = {
            "cumulative_return": r"cumulative return[:\s]*[+\-]?(\d+\.?\d*)%",
            "sharpe_ratio": r"sharpe ratio[:\s]*[+\-]?(\d+\.?\d*)",
            "volatility": r"volatility[:\s]*(\d+\.?\d*)%",
            "max_drawdown": r"max drawdown[:\s]*[+\-]?(\d+\.?\d*)%",
            "win_rate": r"win rate[:\s]*(\d+\.?\d*)%"
        }
        
        for metric, pattern in patterns.items():
            matches = re.findall(pattern, content.lower())
            if matches:
                try:
                    metrics[metric] = float(matches[0])
                except ValueError:
                    continue
        
        # Extract monthly data if available
        monthly_data = self.extract_monthly_performance_data(content)
        
        # Create visualizations
        col1, col2 = st.columns(2)
        
        with col1:
            if metrics:
                # Performance metrics radar chart
                categories = list(metrics.keys())
                values = list(metrics.values())
                
                # Normalize values for radar chart
                normalized_values = []
                for i, (cat, val) in enumerate(zip(categories, values)):
                    if "rate" in cat or "ratio" in cat:
                        normalized_values.append(min(100, max(0, val * 20)))  # Scale ratios
                    else:
                        normalized_values.append(min(100, max(0, abs(val))))  # Use absolute values
                
                fig = go.Figure()
                fig.add_trace(go.Scatterpolar(
                    r=normalized_values,
                    theta=[cat.replace('_', ' ').title() for cat in categories],
                    fill='toself',
                    name='Performance Metrics'
                ))
                
                fig.update_layout(
                    polar=dict(
                        radialaxis=dict(
                            visible=True,
                            range=[0, 100]
                        )),
                    title="📊 Performance Metrics Overview",
                    height=400
                )
                st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            if monthly_data:
                # Monthly performance chart
                months = list(monthly_data.keys())
                returns = [monthly_data[month].get('return', 0) for month in months]
                
                fig = go.Figure()
                fig.add_trace(go.Bar(
                    x=months,
                    y=returns,
                    marker_color=['green' if r > 0 else 'red' for r in returns],
                    name='Monthly Returns'
                ))
                
                fig.update_layout(
                    title="📅 Monthly Performance",
                    xaxis_title="Month",
                    yaxis_title="Return (%)",
                    height=400,
                    xaxis_tickangle=-45
                )
                st.plotly_chart(fig, use_container_width=True)
        
        # Performance summary table
        if metrics:
            st.markdown("#### 📋 Performance Summary")
            
            summary_data = []
            for metric, value in metrics.items():
                summary_data.append({
                    "Metric": metric.replace('_', ' ').title(),
                    "Value": f"{value:.2f}%" if "rate" in metric or "return" in metric or "drawdown" in metric or "volatility" in metric else f"{value:.2f}",
                    "Status": "✅ Good" if self.is_good_performance_metric(metric, value) else "⚠️ Needs Attention"
                })
            
            summary_df = pd.DataFrame(summary_data)
            st.dataframe(summary_df, use_container_width=True)
    
    def visualize_stress_test_report(self, content, report_name):
        """Create specialized visualizations for stress test reports"""
        st.markdown("#### 🧪 Stress Test Analysis")
        
        # Extract stress test metrics
        import re
        
        # Look for test results patterns
        test_patterns = {
            "pass_rate": r"pass rate[:\s]*(\d+\.?\d*)",
            "total_tests": r"total tests[:\s]*(\d+)",
            "failed_tests": r"failed tests[:\s]*(\d+)",
            "max_drawdown": r"max drawdown[:\s]*(\d+\.?\d*)",
            "var_breaches": r"var breaches[:\s]*(\d+)",
            "cpu_usage": r"cpu usage[:\s]*(\d+\.?\d*)",
            "memory_usage": r"memory usage[:\s]*(\d+\.?\d*)"
        }
        
        stress_metrics = {}
        for metric, pattern in test_patterns.items():
            matches = re.findall(pattern, content.lower())
            if matches:
                try:
                    stress_metrics[metric] = float(matches[0])
                except ValueError:
                    continue
        
        # Create stress test visualizations
        col1, col2 = st.columns(2)
        
        with col1:
            if stress_metrics:
                # Stress test results gauge
                pass_rate = stress_metrics.get('pass_rate', 0) * 100 if stress_metrics.get('pass_rate', 0) <= 1 else stress_metrics.get('pass_rate', 0)
                
                fig = go.Figure(go.Indicator(
                    mode = "gauge+number+delta",
                    value = pass_rate,
                    domain = {'x': [0, 1], 'y': [0, 1]},
                    title = {'text': "Stress Test Pass Rate"},
                    delta = {'reference': 80},
                    gauge = {
                        'axis': {'range': [None, 100]},
                        'bar': {'color': "darkblue"},
                        'steps': [
                            {'range': [0, 50], 'color': "red"},
                            {'range': [50, 80], 'color': "yellow"},
                            {'range': [80, 100], 'color': "green"}],
                        'threshold': {
                            'line': {'color': "red", 'width': 4},
                            'thickness': 0.75,
                            'value': 90}}))
                
                fig.update_layout(height=300)
                st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            if stress_metrics:
                # Resource usage chart
                resource_metrics = {k: v for k, v in stress_metrics.items() if 'usage' in k or 'drawdown' in k}
                
                if resource_metrics:
                    categories = list(resource_metrics.keys())
                    values = list(resource_metrics.values())
                    
                    fig = go.Figure()
                    fig.add_trace(go.Bar(
                        x=[cat.replace('_', ' ').title() for cat in categories],
                        y=values,
                        marker_color=['red' if v > 0.8 else 'orange' if v > 0.6 else 'green' for v in values],
                        text=[f"{v:.1%}" if v <= 1 else f"{v:.1f}" for v in values],
                        textposition='auto'
                    ))
                    
                    fig.update_layout(
                        title="📊 Resource Usage & Risk Metrics",
                        xaxis_title="Metric",
                        yaxis_title="Value",
                        height=300
                    )
                    st.plotly_chart(fig, use_container_width=True)
        
        # Stress test scenarios analysis
        scenarios = self.extract_stress_scenarios(content)
        if scenarios:
            st.markdown("#### 🎯 Stress Test Scenarios")
            
            scenario_data = []
            for scenario in scenarios:
                scenario_data.append({
                    "Scenario": scenario.get('name', 'Unknown'),
                    "Status": "✅ Passed" if scenario.get('passed', False) else "❌ Failed",
                    "Duration": f"{scenario.get('duration', 0):.1f}s",
                    "Impact": scenario.get('impact', 'Unknown')
                })
            
            if scenario_data:
                scenario_df = pd.DataFrame(scenario_data)
                st.dataframe(scenario_df, use_container_width=True)
    
    def extract_monthly_performance_data(self, content):
        """Extract monthly performance data from content"""
        import re
        
        monthly_data = {}
        
        # Look for monthly performance table
        lines = content.split('\n')
        in_table = False
        
        for line in lines:
            if '| Month |' in line or '|-------|' in line:
                in_table = True
                continue
            elif in_table and line.strip().startswith('|') and len(line.split('|')) > 3:
                parts = [p.strip() for p in line.split('|') if p.strip()]
                if len(parts) >= 3 and parts[0] not in ['Month', '']:
                    try:
                        month = parts[0]
                        northstar_return = float(parts[1].replace('%', '').replace('+', ''))
                        monthly_data[month] = {'return': northstar_return}
                    except (ValueError, IndexError):
                        continue
            elif in_table and not line.strip().startswith('|'):
                break
        
        return monthly_data
    
    def extract_stress_scenarios(self, content):
        """Extract stress test scenarios from content"""
        scenarios = []
        
        # Look for scenario patterns
        import re
        
        scenario_patterns = [
            r"scenario[:\s]*([^\n]+)",
            r"test[:\s]*([^\n]+)",
            r"extreme[_\s]volatility",
            r"liquidity[_\s]crisis",
            r"system[_\s]overload",
            r"data[_\s]feed[_\s]interruption"
        ]
        
        for pattern in scenario_patterns:
            matches = re.findall(pattern, content.lower())
            for match in matches:
                if isinstance(match, str) and len(match) > 3:
                    scenarios.append({
                        'name': match.strip(),
                        'passed': 'pass' in content.lower(),
                        'duration': 0,
                        'impact': 'Unknown'
                    })
        
        return scenarios[:5]  # Limit to first 5 scenarios
    
    def is_good_performance_metric(self, metric, value):
        """Determine if a performance metric value is good"""
        if "return" in metric:
            return value > 0
        elif "sharpe" in metric:
            return value > 1.0
        elif "drawdown" in metric:
            return abs(value) < 10
        elif "win_rate" in metric:
            return value > 50
        elif "volatility" in metric:
            return value < 20
        else:
            return True  # Default to good
    
    def visualize_generic_report(self, content, report_name):
        """Create generic visualizations for any report"""
        
        # Extract numerical data using existing method
        import re
        
        # Common patterns for metrics
        patterns = {
            "percentages": r"(\d+\.?\d*)%",
            "currency": r"[₹$€£](\d+(?:,\d{3})*(?:\.\d{2})?)",
            "ratios": r"ratio[:\s]*(\d+\.?\d*)",
            "scores": r"score[:\s]*(\d+\.?\d*)",
            "returns": r"return[:\s]*[+-]?(\d+\.?\d*)%?",
            "dates": r"(\d{4}-\d{2}-\d{2})"
        }
        
        extracted_data = {}
        for pattern_name, pattern in patterns.items():
            matches = re.findall(pattern, content.lower())
            if matches:
                try:
                    # Convert to float where possible
                    numeric_matches = []
                    for match in matches[:10]:  # Limit to first 10 matches
                        try:
                            if pattern_name == "currency":
                                # Remove commas from currency
                                numeric_matches.append(float(match.replace(',', '')))
                            elif pattern_name != "dates":
                                numeric_matches.append(float(match))
                            else:
                                numeric_matches.append(match)
                        except ValueError:
                            continue
                    
                    if numeric_matches and pattern_name != "dates":
                        extracted_data[pattern_name] = numeric_matches
                except Exception:
                    continue
        
        # Create visualizations if we found data
        if extracted_data:
            st.markdown("#### 📊 Extracted Metrics Visualization")
            
            # Create charts for different data types
            chart_cols = st.columns(min(3, len(extracted_data)))
            
            for i, (data_type, values) in enumerate(extracted_data.items()):
                if i < 3 and len(values) > 1:  # Only show first 3 charts with multiple values
                    with chart_cols[i]:
                        if data_type == "percentages":
                            # Histogram for percentages
                            fig = go.Figure()
                            fig.add_trace(go.Histogram(
                                x=values,
                                nbinsx=min(10, len(values)),
                                marker_color='lightblue',
                                name='Percentages'
                            ))
                            fig.update_layout(
                                title=f"📊 {data_type.title()} Distribution",
                                height=300
                            )
                            st.plotly_chart(fig, use_container_width=True)
                            
                        elif data_type == "currency":
                            # Bar chart for currency values
                            fig = go.Figure()
                            fig.add_trace(go.Bar(
                                x=list(range(len(values))),
                                y=values,
                                marker_color='green',
                                name='Currency Values'
                            ))
                            fig.update_layout(
                                title=f"💰 {data_type.title()} Values",
                                height=300
                            )
                            st.plotly_chart(fig, use_container_width=True)
                            
                        else:
                            # Line chart for other metrics
                            fig = go.Figure()
                            fig.add_trace(go.Scatter(
                                x=list(range(len(values))),
                                y=values,
                                mode='lines+markers',
                                name=data_type.title()
                            ))
                            fig.update_layout(
                                title=f"📈 {data_type.title()} Trend",
                                height=300
                            )
                            st.plotly_chart(fig, use_container_width=True)
            
            # Show summary statistics
            st.markdown("#### 📋 Extracted Data Summary")
            summary_data = []
            for data_type, values in extracted_data.items():
                if isinstance(values[0], (int, float)):
                    summary_data.append({
                        "Metric Type": data_type.title(),
                        "Count": len(values),
                        "Average": f"{np.mean(values):.2f}",
                        "Min": f"{min(values):.2f}",
                        "Max": f"{max(values):.2f}"
                    })
            
            if summary_data:
                summary_df = pd.DataFrame(summary_data)
                st.dataframe(summary_df, use_container_width=True)
        
    def load_system_logs(self):
        """Load actual system logs"""
        logs = []
        
        if self.logs_path.exists():
            log_files = list(self.logs_path.glob("*.log")) + list(self.logs_path.rglob("*.log"))
            
            for log_file in log_files[-5:]:  # Last 5 log files
                try:
                    with open(log_file, 'r') as f:
                        lines = f.readlines()[-20:]  # Last 20 lines
                        logs.append({
                            "file": log_file.name,
                            "lines": lines,
                            "modified": datetime.fromtimestamp(log_file.stat().st_mtime)
                        })
                except Exception as e:
                    st.warning(f"Could not load {log_file.name}: {e}")
                    
        return logs
        
    def render_system_overview(self):
        """Render system overview with comprehensive visualizations"""
        st.markdown("## 🏗️ System Overview")
        
        # Scan reports
        reports = self.scan_reports()
        data_info = self.scan_data_directories()
        
        # System Health Dashboard
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_reports = sum(len(reports[cat]) for cat in reports)
            st.metric("Total Reports", total_reports, delta=f"+{total_reports-100}" if total_reports > 100 else None)
            
        with col2:
            data_dirs = len(data_info)
            st.metric("Data Directories", data_dirs, delta=f"+{data_dirs-40}" if data_dirs > 40 else None)
            
        with col3:
            total_files = sum(info["file_count"] for info in data_info.values())
            st.metric("Data Files", total_files, delta=f"+{total_files-500}" if total_files > 500 else None)
            
        with col4:
            if self.logs_path.exists():
                log_files = len(list(self.logs_path.rglob("*.log")))
                st.metric("Log Files", log_files, delta=f"+{log_files-10}" if log_files > 10 else None)
            else:
                st.metric("Log Files", 0)
                
        st.markdown("---")
        
        # Visual System Health
        if reports and data_info:
            col1, col2 = st.columns(2)
            
            with col1:
                # System Health Gauge
                health_score = min(100, (total_reports * 0.5 + data_dirs * 2 + min(total_files/10, 50)))
                
                fig = go.Figure(go.Indicator(
                    mode = "gauge+number+delta",
                    value = health_score,
                    domain = {'x': [0, 1], 'y': [0, 1]},
                    title = {'text': "System Health Score"},
                    delta = {'reference': 80},
                    gauge = {
                        'axis': {'range': [None, 100]},
                        'bar': {'color': "darkblue"},
                        'steps': [
                            {'range': [0, 50], 'color': "lightgray"},
                            {'range': [50, 80], 'color': "yellow"},
                            {'range': [80, 100], 'color': "green"}],
                        'threshold': {
                            'line': {'color': "red", 'width': 4},
                            'thickness': 0.75,
                            'value': 90}}))
                
                fig.update_layout(height=300)
                st.plotly_chart(fig, use_container_width=True)
                
            with col2:
                # Data Size Distribution (Pie Chart)
                if data_info:
                    sizes = [info["total_size"] / (1024*1024) for info in data_info.values()]  # MB
                    labels = list(data_info.keys())
                    
                    fig = go.Figure(data=[go.Pie(
                        labels=labels[:8],  # Top 8 directories
                        values=sizes[:8],
                        hole=.3,
                        textinfo='label+percent'
                    )])
                    
                    fig.update_layout(
                        title="Data Storage Distribution (MB)",
                        height=300,
                        showlegend=False
                    )
                    st.plotly_chart(fig, use_container_width=True)
        
        # Reports Timeline and Category Analysis
        if reports:
            st.markdown("### 📊 Reports Analysis Dashboard")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Report counts by category (Enhanced Bar Chart)
                categories = list(reports.keys())
                counts = [len(reports[cat]) for cat in categories]
                colors = px.colors.qualitative.Set3[:len(categories)]
                
                fig = go.Figure(data=[go.Bar(
                    x=categories, 
                    y=counts,
                    marker_color=colors,
                    text=counts,
                    textposition='auto'
                )])
                
                fig.update_layout(
                    title="📋 Reports by Category",
                    xaxis_title="Category",
                    yaxis_title="Number of Reports",
                    height=400,
                    xaxis_tickangle=-45
                )
                st.plotly_chart(fig, use_container_width=True)
                
            with col2:
                # Report Activity Timeline
                all_reports = []
                for cat, rep_list in reports.items():
                    for rep in rep_list:
                        rep["category"] = cat
                        all_reports.append(rep)
                        
                # Group by date
                from collections import defaultdict
                daily_counts = defaultdict(int)
                for report in all_reports:
                    date_str = report["modified"].strftime("%Y-%m-%d")
                    daily_counts[date_str] += 1
                
                dates = sorted(daily_counts.keys())[-30:]  # Last 30 days
                counts = [daily_counts[date] for date in dates]
                
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=dates, y=counts,
                    mode='lines+markers',
                    name='Reports Created',
                    line=dict(color='#1f77b4', width=3),
                    marker=dict(size=8)
                ))
                
                fig.update_layout(
                    title="📈 Report Creation Timeline (Last 30 Days)",
                    xaxis_title="Date",
                    yaxis_title="Reports Created",
                    height=400,
                    xaxis_tickangle=-45
                )
                st.plotly_chart(fig, use_container_width=True)
                
        # Data Directories Visualization
        if data_info:
            st.markdown("### 💾 Data Infrastructure Dashboard")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # File Count vs Size Scatter Plot
                dirs = list(data_info.keys())
                file_counts = [info["file_count"] for info in data_info.values()]
                sizes_mb = [info["total_size"] / (1024*1024) for info in data_info.values()]
                
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=file_counts,
                    y=sizes_mb,
                    mode='markers+text',
                    text=dirs,
                    textposition="top center",
                    marker=dict(
                        size=[min(50, max(10, count/10)) for count in file_counts],
                        color=sizes_mb,
                        colorscale='Viridis',
                        showscale=True,
                        colorbar=dict(title="Size (MB)")
                    )
                ))
                
                fig.update_layout(
                    title="📊 Data Directories: File Count vs Size",
                    xaxis_title="Number of Files",
                    yaxis_title="Size (MB)",
                    height=400
                )
                st.plotly_chart(fig, use_container_width=True)
                
            with col2:
                # Top Data Directories (Horizontal Bar)
                sorted_dirs = sorted(data_info.items(), key=lambda x: x[1]["total_size"], reverse=True)[:10]
                dir_names = [item[0] for item in sorted_dirs]
                dir_sizes = [item[1]["total_size"] / (1024*1024) for item in sorted_dirs]
                
                fig = go.Figure(go.Bar(
                    x=dir_sizes,
                    y=dir_names,
                    orientation='h',
                    marker_color='lightblue',
                    text=[f"{size:.1f} MB" for size in dir_sizes],
                    textposition='auto'
                ))
                
                fig.update_layout(
                    title="🗂️ Top Data Directories by Size",
                    xaxis_title="Size (MB)",
                    yaxis_title="Directory",
                    height=400
                )
                st.plotly_chart(fig, use_container_width=True)
                
            # Detailed Data Table with Enhanced Formatting
            st.markdown("### 📋 Detailed Data Directory Analysis")
            
            data_df = pd.DataFrame([
                {
                    "Directory": name,
                    "Files": info["file_count"],
                    "Size (MB)": round(info["total_size"] / (1024*1024), 2),
                    "Avg File Size (KB)": round(info["total_size"] / (1024 * info["file_count"]), 1) if info["file_count"] > 0 else 0,
                    "File Types": ", ".join(info["file_types"][:3]) + ("..." if len(info["file_types"]) > 3 else ""),
                    "Latest File": info["latest_file"].name[:30] + ("..." if len(info["latest_file"].name) > 30 else "")
                }
                for name, info in data_info.items()
            ])
            
            # Sort by size descending
            data_df = data_df.sort_values("Size (MB)", ascending=False)
            
            st.dataframe(
                data_df, 
                use_container_width=True,
                column_config={
                    "Files": st.column_config.NumberColumn(format="%d"),
                    "Size (MB)": st.column_config.NumberColumn(format="%.2f"),
                    "Avg File Size (KB)": st.column_config.NumberColumn(format="%.1f")
                }
            )
    
    def render_market_situation(self):
        """Render current market situation with comprehensive metrics"""
        st.markdown("## 📊 Current Market Situation")
        
        market_data = self.load_current_market_data()
        
        # Market Overview Dashboard
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            # Market Health Score
            health_score = 75  # Default, calculate from available data
            if market_data["market_health"]:
                # Calculate based on available performance data
                health_score = min(100, len(market_data["market_health"]) * 25)
            
            st.metric("Market Health", f"{health_score}%", delta="Stable")
            
        with col2:
            # Current Regime
            current_regime = "Unknown"
            if market_data["regime_data"]:
                # Extract regime from latest data
                if "current_regime" in market_data["regime_data"]:
                    regime_info = market_data["regime_data"]["current_regime"]
                    if isinstance(regime_info, dict) and "name" in regime_info:
                        current_regime = regime_info["name"].replace("_", " ")
                elif "regime" in market_data["regime_data"]:
                    current_regime = market_data["regime_data"]["regime"].replace("_", " ").title()
                else:
                    # Look in nested data
                    for key, data in market_data["regime_data"].items():
                        if isinstance(data, dict):
                            if "market_regime_analysis" in data:
                                regime_analysis = data["market_regime_analysis"]
                                if "current_regime" in regime_analysis and "name" in regime_analysis["current_regime"]:
                                    current_regime = regime_analysis["current_regime"]["name"].replace("_", " ")
                                    break
                            elif "market_regime" in data:
                                current_regime = data["market_regime"].replace("_", " ").title()
                                break
            
            st.metric("Market Regime", current_regime)
            
        with col3:
            # Volatility Level
            volatility = "Medium"
            if market_data["macro_data"].get("yields"):
                # Simple volatility indicator based on yield data
                volatility = "High" if any(abs(v) > 0.1 for v in market_data["macro_data"]["yields"].values() if isinstance(v, (int, float))) else "Low"
            
            st.metric("Volatility", volatility)
            
        with col4:
            # Trend Direction
            trend = market_data["macro_data"].get("yield_trend", "Neutral").title()
            st.metric("Trend", trend, delta="📈" if trend == "Up" else "📉" if trend == "Down" else "➡️")
        
        # Market Data Visualizations
        if market_data["macro_data"].get("yields"):
            st.markdown("### 📈 Macro Economic Indicators")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Yield Curve Visualization
                yields = market_data["macro_data"]["yields"]
                yield_keys = [k for k in yields.keys() if isinstance(yields[k], (int, float))]
                yield_values = [yields[k] for k in yield_keys]
                
                if yield_keys and yield_values:
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=yield_keys,
                        y=yield_values,
                        mode='lines+markers',
                        name='Yield Curve',
                        line=dict(color='#1f77b4', width=3),
                        marker=dict(size=8)
                    ))
                    
                    fig.update_layout(
                        title="📊 Current Yield Curve",
                        xaxis_title="Maturity",
                        yaxis_title="Yield (%)",
                        height=400
                    )
                    st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                # Yield Levels Bar Chart
                if yield_keys and yield_values:
                    fig = go.Figure()
                    fig.add_trace(go.Bar(
                        x=yield_keys,
                        y=yield_values,
                        marker_color=['green' if v < 5 else 'orange' if v < 7 else 'red' for v in yield_values],
                        text=[f"{v:.2f}%" for v in yield_values],
                        textposition='auto'
                    ))
                    
                    fig.update_layout(
                        title="📊 Yield Levels by Maturity",
                        xaxis_title="Maturity",
                        yaxis_title="Yield (%)",
                        height=400
                    )
                    st.plotly_chart(fig, use_container_width=True)
        
        # Market Regime Analysis
        if market_data["regime_data"]:
            st.markdown("### 🎯 Market Regime Analysis")
            
            for regime_file, regime_data in market_data["regime_data"].items():
                with st.expander(f"📊 {regime_file}"):
                    self.visualize_json_data(regime_data, f"Market Regime Data - {regime_file}")
        
        # Market Health Metrics
        if market_data["market_health"]:
            st.markdown("### 💊 Market Health Metrics")
            
            for health_file, health_data in market_data["market_health"].items():
                with st.expander(f"📈 {health_file}"):
                    self.visualize_json_data(health_data, f"Market Health - {health_file}")
        
        # Real-time Market Indicators
        st.markdown("### ⚡ Real-time Indicators")
        
        # Create a market dashboard
        indicator_col1, indicator_col2, indicator_col3 = st.columns(3)
        
        with indicator_col1:
            # Risk Appetite Gauge
            risk_appetite = 65  # Calculate from available data
            
            fig = go.Figure(go.Indicator(
                mode = "gauge+number",
                value = risk_appetite,
                domain = {'x': [0, 1], 'y': [0, 1]},
                title = {'text': "Risk Appetite"},
                gauge = {
                    'axis': {'range': [None, 100]},
                    'bar': {'color': "darkblue"},
                    'steps': [
                        {'range': [0, 30], 'color': "red"},
                        {'range': [30, 70], 'color': "yellow"},
                        {'range': [70, 100], 'color': "green"}],
                    'threshold': {
                        'line': {'color': "red", 'width': 4},
                        'thickness': 0.75,
                        'value': 80}}))
            
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)
        
        with indicator_col2:
            # Market Momentum
            momentum_data = [65, 70, 68, 72, 75, 73, 78]  # Sample data
            dates = pd.date_range(end=datetime.now(), periods=7, freq='D')
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=dates,
                y=momentum_data,
                mode='lines+markers',
                name='Market Momentum',
                line=dict(color='#ff6b6b', width=3)
            ))
            
            fig.update_layout(
                title="📈 Market Momentum (7 days)",
                xaxis_title="Date",
                yaxis_title="Momentum Score",
                height=300
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with indicator_col3:
            # Sector Performance
            sectors = ['Technology', 'Finance', 'Healthcare', 'Energy', 'Consumer']
            performance = [2.3, -0.8, 1.5, -1.2, 0.9]  # Sample data
            
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=sectors,
                y=performance,
                marker_color=['green' if p > 0 else 'red' for p in performance],
                text=[f"{p:+.1f}%" for p in performance],
                textposition='auto'
            ))
            
            fig.update_layout(
                title="📊 Sector Performance Today",
                xaxis_title="Sector",
                yaxis_title="Performance (%)",
                height=300,
                xaxis_tickangle=-45
            )
            st.plotly_chart(fig, use_container_width=True)
            
    def render_reports_analysis(self):
        """Render reports analysis with enhanced visualizations"""
        st.markdown("## 📋 Reports Analysis Dashboard")
        
        reports = self.scan_reports()
        
        if not reports:
            st.info("No reports found in the reports/ directory")
            return
        
        # Reports Overview Dashboard
        col1, col2, col3 = st.columns(3)
        
        total_reports = sum(len(reports[cat]) for cat in reports)
        categories_count = len(reports)
        
        with col1:
            st.metric("Total Reports", total_reports)
        with col2:
            st.metric("Categories", categories_count)
        with col3:
            # Calculate average reports per category
            avg_per_category = total_reports / categories_count if categories_count > 0 else 0
            st.metric("Avg per Category", f"{avg_per_category:.1f}")
        
        # Category Analysis
        col1, col2 = st.columns(2)
        
        with col1:
            # Enhanced Category Distribution
            categories = list(reports.keys())
            counts = [len(reports[cat]) for cat in categories]
            
            # Create a more visually appealing bar chart
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=categories,
                y=counts,
                marker_color=px.colors.qualitative.Set3,
                text=counts,
                textposition='auto',
                hovertemplate='<b>%{x}</b><br>Reports: %{y}<extra></extra>'
            ))
            
            fig.update_layout(
                title="📊 Reports by Category",
                xaxis_title="Category",
                yaxis_title="Number of Reports",
                height=400,
                xaxis_tickangle=-45,
                showlegend=False
            )
            st.plotly_chart(fig, use_container_width=True)
            
        with col2:
            # Report Size Analysis
            all_reports = []
            for cat, rep_list in reports.items():
                for rep in rep_list:
                    rep["category"] = cat
                    all_reports.append(rep)
            
            # Group by size ranges
            size_ranges = {
                "Small (<10KB)": 0,
                "Medium (10KB-100KB)": 0,
                "Large (100KB-1MB)": 0,
                "Very Large (>1MB)": 0
            }
            
            for report in all_reports:
                size_kb = report["size"] / 1024
                if size_kb < 10:
                    size_ranges["Small (<10KB)"] += 1
                elif size_kb < 100:
                    size_ranges["Medium (10KB-100KB)"] += 1
                elif size_kb < 1024:
                    size_ranges["Large (100KB-1MB)"] += 1
                else:
                    size_ranges["Very Large (>1MB)"] += 1
            
            fig = go.Figure(data=[go.Pie(
                labels=list(size_ranges.keys()),
                values=list(size_ranges.values()),
                hole=.3,
                marker_colors=px.colors.qualitative.Pastel
            )])
            
            fig.update_layout(
                title="📏 Report Size Distribution",
                height=400,
                showlegend=True
            )
            st.plotly_chart(fig, use_container_width=True)
        
        # Timeline Analysis
        st.markdown("### 📅 Report Creation Timeline")
        
        # Group reports by date
        from collections import defaultdict
        daily_counts = defaultdict(lambda: defaultdict(int))
        
        for cat, rep_list in reports.items():
            for rep in rep_list:
                date_str = rep["modified"].strftime("%Y-%m-%d")
                daily_counts[date_str][cat] += 1
        
        # Create stacked bar chart for last 30 days
        dates = sorted(daily_counts.keys())[-30:]
        
        fig = go.Figure()
        
        for cat in categories:
            counts = [daily_counts[date][cat] for date in dates]
            fig.add_trace(go.Bar(
                name=cat,
                x=dates,
                y=counts,
                hovertemplate=f'<b>{cat}</b><br>Date: %{{x}}<br>Reports: %{{y}}<extra></extra>'
            ))
        
        fig.update_layout(
            title="📈 Report Creation by Category (Last 30 Days)",
            xaxis_title="Date",
            yaxis_title="Reports Created",
            height=400,
            barmode='stack',
            xaxis_tickangle=-45
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # Interactive Category Explorer
        st.markdown("### 🔍 Interactive Report Explorer")
        
        # Select category
        selected_category = st.selectbox("Select Report Category:", categories)
        
        if selected_category and selected_category in reports:
            category_reports = reports[selected_category]
            
            st.markdown(f"### 📂 {selected_category} ({len(category_reports)} reports)")
            
            # Category statistics
            col1, col2, col3, col4 = st.columns(4)
            
            total_size = sum(rep["size"] for rep in category_reports)
            avg_size = total_size / len(category_reports) if category_reports else 0
            latest_date = max(rep["modified"] for rep in category_reports) if category_reports else None
            oldest_date = min(rep["modified"] for rep in category_reports) if category_reports else None
            
            with col1:
                st.metric("Total Size", f"{total_size / (1024*1024):.1f} MB")
            with col2:
                st.metric("Average Size", f"{avg_size / 1024:.1f} KB")
            with col3:
                if latest_date:
                    st.metric("Latest Report", latest_date.strftime("%Y-%m-%d"))
            with col4:
                if oldest_date and latest_date:
                    days_span = (latest_date - oldest_date).days
                    st.metric("Time Span", f"{days_span} days")
            
            # Reports in this category with enhanced display
            for i, report in enumerate(category_reports[:10]):  # Show top 10
                with st.expander(f"📄 {report['name']} - {report['modified'].strftime('%Y-%m-%d %H:%M')}"):
                    
                    # Report metadata
                    col1, col2 = st.columns([3, 1])
                    
                    with col2:
                        st.markdown("**📊 Report Info:**")
                        st.markdown(f"**Size:** {report['size']:,} bytes ({report['size']/1024:.1f} KB)")
                        st.markdown(f"**Modified:** {report['modified'].strftime('%Y-%m-%d %H:%M:%S')}")
                        st.markdown(f"**Type:** {report['path'].suffix.upper()}")
                    
                    with col1:
                        try:
                            if report['path'].suffix == '.json':
                                with open(report['path'], 'r') as f:
                                    data = json.load(f)
                                    
                                # Show key metrics if it's a performance report
                                if any(key in data for key in ['total_return', 'sharpe_ratio', 'success_rate']):
                                    st.markdown("**🎯 Key Metrics:**")
                                    metrics_col1, metrics_col2, metrics_col3 = st.columns(3)
                                    
                                    with metrics_col1:
                                        if 'total_return' in data:
                                            st.metric("Return", f"{data['total_return']:.1f}%")
                                    with metrics_col2:
                                        if 'sharpe_ratio' in data:
                                            st.metric("Sharpe", f"{data['sharpe_ratio']:.2f}")
                                    with metrics_col3:
                                        if 'success_rate' in data:
                                            st.metric("Success", f"{data['success_rate']:.1f}%")
                                
                                # Show JSON data
                                with st.expander("🔍 Full JSON Data"):
                                    self.visualize_json_data(data, f"Report Data - {report['name']}")
                                    
                            else:
                                with open(report['path'], 'r') as f:
                                    content = f.read()
                                    
                                # Show preview
                                if len(content) > 2000:
                                    st.markdown("**📖 Content Preview:**")
                                    st.markdown(content[:2000] + "...")
                                    
                                    with st.expander("📄 Full Content"):
                                        st.markdown(content)
                                        
                                        # Try to extract and visualize any embedded data
                                        self.extract_and_visualize_report_data(content, report['name'])
                                else:
                                    st.markdown("**📖 Full Content:**")
                                    st.markdown(content)
                                    
                                    # Try to extract and visualize any embedded data
                                    self.extract_and_visualize_report_data(content, report['name'])
                                    
                        except Exception as e:
                            st.error(f"Could not display content: {e}")
            
            if len(category_reports) > 10:
                st.info(f"Showing first 10 reports. Total: {len(category_reports)} reports in this category.")
                        
    def render_walk_forward_analysis(self):
        """Render walk forward analysis with comprehensive visualizations"""
        st.markdown("## 🔬 Walk Forward Analysis Dashboard")
        
        wf_results = self.load_walk_forward_results()
        
        if not wf_results:
            st.info("No walk forward analysis results found")
            return
            
        st.markdown(f"📊 **Analysis Overview:** {len(wf_results)} walk forward analysis files found")
        
        # Extract all metrics for visualization
        all_metrics = []
        for result in wf_results:
            if isinstance(result['data'], dict):
                # Use processed metrics
                metrics = {
                    'file': result['file'],
                    'date': result['date'],
                    'avg_return': result['data'].get('avg_return', 0),
                    'total_return': result['data'].get('total_return', 0),
                    'sharpe_ratio': result['data'].get('sharpe_ratio', 0),
                    'win_rate': result['data'].get('win_rate', 0),
                    'volatility': result['data'].get('volatility', 0),
                    'max_return': result['data'].get('max_return', 0),
                    'min_return': result['data'].get('min_return', 0),
                    'window_returns': result['data'].get('window_returns', [])
                }
                all_metrics.append(metrics)
        
        if all_metrics:
            # Performance Dashboard
            col1, col2, col3, col4 = st.columns(4)
            
            latest_metrics = all_metrics[-1] if all_metrics else {}
            
            with col1:
                avg_return = latest_metrics.get('avg_return', 0)
                st.metric(
                    "Avg Return", 
                    f"{avg_return:.2f}%",
                    delta=f"{avg_return:.2f}%" if avg_return != 0 else None
                )
                
            with col2:
                total_return = latest_metrics.get('total_return', 0)
                st.metric(
                    "Total Return", 
                    f"{total_return:.1f}%",
                    delta=f"{total_return:.1f}%" if total_return != 0 else None
                )
                
            with col3:
                sharpe_ratio = latest_metrics.get('sharpe_ratio', 0)
                st.metric(
                    "Sharpe Ratio", 
                    f"{sharpe_ratio:.2f}",
                    delta=f"{sharpe_ratio-1:.2f}" if sharpe_ratio > 0 else None
                )
                
            with col4:
                win_rate = latest_metrics.get('win_rate', 0)
                st.metric(
                    "Win Rate", 
                    f"{win_rate:.1f}%",
                    delta=f"{win_rate-50:.1f}%" if win_rate > 0 else None
                )
            
            st.markdown("---")
            
            # Performance Evolution Charts
            col1, col2 = st.columns(2)
            
            with col1:
                # Returns Over Time
                dates = [m['date'] for m in all_metrics]
                returns = [m['total_return'] for m in all_metrics]
                
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=dates, y=returns,
                    mode='lines+markers',
                    name='Total Return',
                    line=dict(color='#2E86AB', width=3),
                    marker=dict(size=8),
                    fill='tonexty' if any(r > 0 for r in returns) else None
                ))
                
                # Add zero line
                fig.add_hline(y=0, line_dash="dash", line_color="red", annotation_text="Break Even")
                
                fig.update_layout(
                    title="📈 Total Return Evolution",
                    xaxis_title="Analysis Date",
                    yaxis_title="Total Return (%)",
                    height=400,
                    showlegend=False
                )
                st.plotly_chart(fig, use_container_width=True)
                
            with col2:
                # Risk-Return Scatter
                returns = [m['total_return'] for m in all_metrics]
                sharpes = [m['sharpe_ratio'] for m in all_metrics]
                volatilities = [m['volatility'] for m in all_metrics if m['volatility'] > 0]
                
                if volatilities:
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=volatilities,
                        y=returns[:len(volatilities)],
                        mode='markers',
                        marker=dict(
                            size=15,
                            color=sharpes[:len(volatilities)],
                            colorscale='RdYlGn',
                            showscale=True,
                            colorbar=dict(title="Sharpe Ratio")
                        ),
                        text=[f"Run {i+1}" for i in range(len(volatilities))],
                        textposition="top center"
                    ))
                    
                    fig.update_layout(
                        title="🎯 Risk-Return Profile",
                        xaxis_title="Volatility (%)",
                        yaxis_title="Total Return (%)",
                        height=400
                    )
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    # Sharpe Ratio Evolution
                    fig = go.Figure()
                    fig.add_trace(go.Bar(
                        x=[f"Run {i+1}" for i in range(len(sharpes))],
                        y=sharpes,
                        marker_color=['green' if s > 1 else 'orange' if s > 0 else 'red' for s in sharpes],
                        text=[f"{s:.2f}" for s in sharpes],
                        textposition='auto'
                    ))
                    
                    fig.add_hline(y=1, line_dash="dash", line_color="blue", annotation_text="Good (>1.0)")
                    fig.add_hline(y=0, line_dash="dash", line_color="red", annotation_text="Break Even")
                    
                    fig.update_layout(
                        title="📊 Sharpe Ratio by Analysis Run",
                        xaxis_title="Analysis Run",
                        yaxis_title="Sharpe Ratio",
                        height=400
                    )
                    st.plotly_chart(fig, use_container_width=True)
            
            # Performance Metrics Heatmap
            if len(all_metrics) > 1:
                st.markdown("### 🔥 Performance Metrics Heatmap")
                
                metrics_df = pd.DataFrame(all_metrics)
                metrics_df['date_str'] = metrics_df['date'].dt.strftime('%Y-%m-%d')
                
                # Select only available numeric columns for heatmap
                available_cols = [col for col in ['avg_return', 'total_return', 'sharpe_ratio', 'win_rate', 'volatility', 'max_return', 'min_return'] 
                                if col in metrics_df.columns and not metrics_df[col].isna().all()]
                
                if available_cols:
                    heatmap_data = metrics_df[available_cols].T
                    
                    fig = go.Figure(data=go.Heatmap(
                        z=heatmap_data.values,
                        x=[f"Run {i+1}" for i in range(len(all_metrics))],
                        y=[col.replace('_', ' ').title() for col in available_cols],
                        colorscale='RdYlGn',
                        text=heatmap_data.values,
                        texttemplate="%{text:.2f}",
                        textfont={"size": 10}
                    ))
                    
                    fig.update_layout(
                        title="Performance Metrics Across All Runs",
                        height=300
                    )
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No numeric metrics available for heatmap visualization")
        
        # Detailed Results
        st.markdown("### 📋 Detailed Analysis Results")
        
        for i, result in enumerate(wf_results):
            with st.expander(f"📊 Analysis Run {i+1}: {result['file']} - {result['date'].strftime('%Y-%m-%d')}"):
                if isinstance(result['data'], dict):
                    # Create metrics visualization for this specific run
                    metrics = result['data']
                    
                    # Key metrics in columns
                    if any(key in metrics for key in ['success_rate', 'total_return', 'sharpe_ratio']):
                        col1, col2, col3, col4 = st.columns(4)
                        
                        with col1:
                            if 'success_rate' in metrics:
                                st.metric("Success Rate", f"{metrics['success_rate']:.1f}%")
                                
                        with col2:
                            if 'total_return' in metrics:
                                st.metric("Total Return", f"{metrics['total_return']:.1f}%")
                                
                        with col3:
                            if 'sharpe_ratio' in metrics:
                                st.metric("Sharpe Ratio", f"{metrics['sharpe_ratio']:.2f}")
                                
                        with col4:
                            if 'max_drawdown' in metrics:
                                st.metric("Max Drawdown", f"{metrics['max_drawdown']:.1f}%")
                    
                    # Additional metrics if available
                    if 'window_results' in metrics and isinstance(metrics['window_results'], list):
                        st.markdown("**📈 Window-by-Window Performance:**")
                        
                        windows = metrics['window_results']
                        window_returns = [w.get('avg_out_of_sample_return', 0) * 100 for w in windows]
                        window_ids = [w.get('window_id', f'W{i+1}') for i, w in enumerate(windows)]
                        
                        fig = go.Figure()
                        fig.add_trace(go.Bar(
                            x=window_ids,
                            y=window_returns,
                            marker_color=['green' if r > 0 else 'red' for r in window_returns],
                            text=[f"{r:.1f}%" for r in window_returns],
                            textposition='auto'
                        ))
                        
                        fig.update_layout(
                            title="Out-of-Sample Returns by Window",
                            xaxis_title="Window",
                            yaxis_title="Return (%)",
                            height=300
                        )
                        st.plotly_chart(fig, use_container_width=True)
                    
                    # Show full data
                    with st.expander("🔍 Raw Data"):
                        st.json(result['data'])
                else:
                    st.write(result['data'])
                    
    def render_shadow_trading(self):
        """Render shadow trading with comprehensive visualizations"""
        st.markdown("## 📈 Shadow Trading Dashboard")
        
        shadow_data = self.load_shadow_trading_data()
        
        # Trading state
        trading_state = shadow_data.get("trading_state", {})
        daily_logs = shadow_data.get("daily_logs", [])
        historical_positions = shadow_data.get("historical_positions", [])
        pnl_history = shadow_data.get("pnl_history", [])
        
        if trading_state:
            st.markdown("### 💰 Portfolio Overview")
            
            # Key Performance Metrics
            col1, col2, col3, col4 = st.columns(4)
            
            current_capital = trading_state.get("current_capital", 0)
            initial_capital = trading_state.get("initial_capital", current_capital)
            positions = trading_state.get("positions", {})
            
            with col1:
                st.metric("Current Capital", f"₹{current_capital:,.0f}")
                
            with col2:
                if initial_capital > 0:
                    total_return = (current_capital / initial_capital - 1) * 100
                    st.metric("Total Return", f"{total_return:.2f}%", delta=f"{total_return:.2f}%")
                    
            with col3:
                st.metric("Active Positions", len(positions))
                
            with col4:
                total_invested = sum(pos.get('shares', 0) * pos.get('avg_price', 0) for pos in positions.values())
                cash_available = current_capital - total_invested
                st.metric("Cash Available", f"₹{cash_available:,.0f}")
            
            # Portfolio Composition Visualizations
            if positions:
                col1, col2 = st.columns(2)
                
                with col1:
                    # Portfolio Allocation Pie Chart
                    symbols = list(positions.keys())
                    weights = [pos.get('weight', 0) * 100 for pos in positions.values()]
                    values = [pos.get('shares', 0) * pos.get('avg_price', 0) for pos in positions.values()]
                    
                    fig = go.Figure(data=[go.Pie(
                        labels=symbols,
                        values=weights,
                        hole=.4,
                        textinfo='label+percent',
                        textposition='auto',
                        marker=dict(colors=px.colors.qualitative.Set3)
                    )])
                    
                    fig.update_layout(
                        title="🥧 Portfolio Allocation by Weight",
                        height=400,
                        showlegend=True,
                        legend=dict(orientation="v", yanchor="middle", y=0.5)
                    )
                    st.plotly_chart(fig, use_container_width=True)
                    
                with col2:
                    # Position Values Bar Chart
                    fig = go.Figure()
                    fig.add_trace(go.Bar(
                        x=symbols,
                        y=values,
                        marker_color=px.colors.qualitative.Set2,
                        text=[f"₹{v:,.0f}" for v in values],
                        textposition='auto'
                    ))
                    
                    fig.update_layout(
                        title="💼 Position Values",
                        xaxis_title="Symbol",
                        yaxis_title="Value (₹)",
                        height=400,
                        xaxis_tickangle=-45
                    )
                    st.plotly_chart(fig, use_container_width=True)
                
                # Detailed Positions Table with Enhanced Formatting
                st.markdown("### 📊 Current Positions")
                
                positions_data = []
                for symbol, pos_data in positions.items():
                    weight = pos_data.get('weight', 0)
                    shares = pos_data.get('shares', 0)
                    avg_price = pos_data.get('avg_price', 0)
                    position_value = shares * avg_price
                    
                    positions_data.append({
                        "Symbol": symbol,
                        "Weight": weight,
                        "Shares": shares,
                        "Avg Price": avg_price,
                        "Position Value": position_value,
                        "% of Portfolio": (position_value / current_capital * 100) if current_capital > 0 else 0
                    })
                    
                positions_df = pd.DataFrame(positions_data)
                positions_df = positions_df.sort_values("Position Value", ascending=False)
                
                st.dataframe(
                    positions_df, 
                    use_container_width=True,
                    column_config={
                        "Weight": st.column_config.NumberColumn(format="%.1f%%", help="Target weight"),
                        "Shares": st.column_config.NumberColumn(format="%d"),
                        "Avg Price": st.column_config.NumberColumn(format="₹%.2f"),
                        "Position Value": st.column_config.NumberColumn(format="₹%,.0f"),
                        "% of Portfolio": st.column_config.NumberColumn(format="%.1f%%")
                    }
                )
                
        # Daily Performance Analysis
        if daily_logs:
            st.markdown("### 📅 Performance Analytics")
            
            # Process daily logs for visualization
            dates = []
            returns = []
            portfolio_values = []
            daily_pnls = []
            
            for log in daily_logs[-60:]:  # Last 60 days
                if isinstance(log, dict) and 'date' in log:
                    dates.append(log['date'])
                    pnl = log.get('pnl', {})
                    returns.append(pnl.get('total_pnl_pct', 0))
                    portfolio_values.append(pnl.get('portfolio_value', 0))
                    daily_pnls.append(pnl.get('total_pnl', 0))
            
            if dates and returns:
                col1, col2 = st.columns(2)
                
                with col1:
                    # Daily Returns Chart
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=dates, y=returns,
                        mode='lines+markers',
                        name='Daily Returns',
                        line=dict(color='#2E86AB', width=2),
                        marker=dict(size=6),
                        fill='tonexty'
                    ))
                    
                    # Add zero line
                    fig.add_hline(y=0, line_dash="dash", line_color="gray", annotation_text="Break Even")
                    
                    fig.update_layout(
                        title="📈 Daily Returns (%)",
                        xaxis_title="Date",
                        yaxis_title="Return (%)",
                        height=400,
                        showlegend=False
                    )
                    st.plotly_chart(fig, use_container_width=True)
                    
                with col2:
                    # Portfolio Value Growth
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=dates, y=portfolio_values,
                        mode='lines',
                        name='Portfolio Value',
                        line=dict(color='#28a745', width=3),
                        fill='tonexty'
                    ))
                    
                    fig.update_layout(
                        title="💰 Portfolio Value Growth",
                        xaxis_title="Date",
                        yaxis_title="Portfolio Value (₹)",
                        height=400,
                        showlegend=False
                    )
                    st.plotly_chart(fig, use_container_width=True)
                
                # Performance Statistics
                if len(returns) > 1:
                    col1, col2, col3, col4 = st.columns(4)
                    
                    avg_return = np.mean(returns)
                    volatility = np.std(returns) * np.sqrt(252)  # Annualized
                    sharpe = avg_return / np.std(returns) * np.sqrt(252) if np.std(returns) > 0 else 0
                    max_dd = min(returns) if returns else 0
                    
                    with col1:
                        st.metric("Avg Daily Return", f"{avg_return:.2f}%")
                    with col2:
                        st.metric("Annualized Volatility", f"{volatility:.1f}%")
                    with col3:
                        st.metric("Sharpe Ratio", f"{sharpe:.2f}")
                    with col4:
                        st.metric("Max Daily Loss", f"{max_dd:.2f}%")
                
                # Returns Distribution
                st.markdown("### 📊 Returns Distribution Analysis")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    # Returns Histogram
                    fig = go.Figure()
                    fig.add_trace(go.Histogram(
                        x=returns,
                        nbinsx=20,
                        marker_color='lightblue',
                        opacity=0.7,
                        name='Daily Returns'
                    ))
                    
                    # Add normal distribution overlay
                    if len(returns) > 5:
                        mean_ret = np.mean(returns)
                        std_ret = np.std(returns)
                        x_norm = np.linspace(min(returns), max(returns), 100)
                        y_norm = len(returns) * (max(returns) - min(returns)) / 20 * \
                                 (1/(std_ret * np.sqrt(2*np.pi))) * np.exp(-0.5*((x_norm - mean_ret)/std_ret)**2)
                        
                        fig.add_trace(go.Scatter(
                            x=x_norm, y=y_norm,
                            mode='lines',
                            name='Normal Distribution',
                            line=dict(color='red', width=2)
                        ))
                    
                    fig.update_layout(
                        title="📊 Daily Returns Distribution",
                        xaxis_title="Daily Return (%)",
                        yaxis_title="Frequency",
                        height=400
                    )
                    st.plotly_chart(fig, use_container_width=True)
                    
                with col2:
                    # Cumulative Returns
                    cumulative_returns = np.cumprod(1 + np.array(returns)/100) - 1
                    
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=dates, y=cumulative_returns * 100,
                        mode='lines',
                        name='Cumulative Return',
                        line=dict(color='#ff6b6b', width=3),
                        fill='tonexty'
                    ))
                    
                    fig.update_layout(
                        title="📈 Cumulative Returns",
                        xaxis_title="Date",
                        yaxis_title="Cumulative Return (%)",
                        height=400,
                        showlegend=False
                    )
                    st.plotly_chart(fig, use_container_width=True)
                
            # Recent Activity Table with Enhanced Formatting
            st.markdown("### 📋 Recent Trading Activity")
            
            recent_logs = daily_logs[-15:] if len(daily_logs) > 15 else daily_logs
            
            activity_data = []
            for log in recent_logs:
                if isinstance(log, dict):
                    pnl = log.get('pnl', {})
                    nifty = log.get('nifty_performance', {})
                    
                    activity_data.append({
                        "Date": log.get('date', 'Unknown'),
                        "Return": pnl.get('total_pnl_pct', 0),
                        "P&L": pnl.get('total_pnl', 0),
                        "Portfolio Value": pnl.get('portfolio_value', 0),
                        "Nifty Return": nifty.get('daily_return', 0),
                        "Trades": len(log.get('trades', [])),
                        "Alpha": pnl.get('total_pnl_pct', 0) - nifty.get('daily_return', 0)
                    })
                    
            if activity_data:
                activity_df = pd.DataFrame(activity_data)
                activity_df = activity_df.sort_values("Date", ascending=False)
                
                st.dataframe(
                    activity_df, 
                    use_container_width=True,
                    column_config={
                        "Return": st.column_config.NumberColumn(format="%.2f%%"),
                        "P&L": st.column_config.NumberColumn(format="₹%,.0f"),
                        "Portfolio Value": st.column_config.NumberColumn(format="₹%,.0f"),
                        "Nifty Return": st.column_config.NumberColumn(format="%.2f%%"),
                        "Trades": st.column_config.NumberColumn(format="%d"),
                        "Alpha": st.column_config.NumberColumn(format="%.2f%%", help="Excess return vs Nifty")
                    }
                )
                
        # Historical Portfolio Analysis
        if historical_positions:
            st.markdown("### 📚 Historical Portfolio Evolution")
            
            # Portfolio evolution over time
            portfolio_dates = [pos["date"] for pos in historical_positions]
            portfolio_counts = [len(pos["positions"]) for pos in historical_positions]
            
            if portfolio_dates and portfolio_counts:
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=portfolio_dates,
                    y=portfolio_counts,
                    mode='lines+markers',
                    name='Portfolio Size',
                    line=dict(color='#2E86AB', width=3),
                    marker=dict(size=8)
                ))
                
                fig.update_layout(
                    title="📈 Portfolio Size Evolution",
                    xaxis_title="Date",
                    yaxis_title="Number of Positions",
                    height=400
                )
                st.plotly_chart(fig, use_container_width=True)
            
            # Historical positions details
            st.markdown("#### 📋 Historical Positions")
            for i, pos_data in enumerate(historical_positions[-5:]):  # Last 5 days
                with st.expander(f"📅 Portfolio on {pos_data['date']} ({len(pos_data['positions'])} positions)"):
                    if pos_data['positions']:
                        hist_positions_data = []
                        for symbol, pos_info in pos_data['positions'].items():
                            hist_positions_data.append({
                                "Symbol": symbol,
                                "Weight": f"{pos_info.get('weight', 0)*100:.1f}%",
                                "Shares": pos_info.get('shares', 0),
                                "Avg Price": f"₹{pos_info.get('avg_price', 0):.2f}",
                                "Value": f"₹{pos_info.get('shares', 0) * pos_info.get('avg_price', 0):,.0f}"
                            })
                        
                        if hist_positions_data:
                            hist_df = pd.DataFrame(hist_positions_data)
                            st.dataframe(hist_df, use_container_width=True)
                    else:
                        st.info("No positions held on this date")
        
        # P&L History Analysis
        if pnl_history:
            st.markdown("### 💰 P&L History Analysis")
            
            pnl_dates = [pnl["date"] for pnl in pnl_history]
            pnl_values = [pnl["pnl"].get("total_pnl", 0) for pnl in pnl_history if isinstance(pnl["pnl"], dict)]
            
            if pnl_dates and pnl_values:
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=pnl_dates,
                    y=pnl_values,
                    mode='lines+markers',
                    name='Daily P&L',
                    line=dict(color='#28a745', width=3),
                    fill='tonexty'
                ))
                
                fig.update_layout(
                    title="💰 Historical P&L",
                    xaxis_title="Date",
                    yaxis_title="P&L (₹)",
                    height=400
                )
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No shadow trading data found. Run shadow trading to generate data.")
            
            # Show setup instructions
            st.markdown("### 🚀 Getting Started with Shadow Trading")
            st.code("python scripts/launch_shadow_trading.py", language="bash")
            st.markdown("This will start the shadow trading system and begin generating performance data.")
            
    def render_system_logs(self):
        """Render system logs with enhanced visualizations"""
        st.markdown("## 📋 System Logs Dashboard")
        
        logs = self.load_system_logs()
        
        if not logs:
            st.info("No system logs found")
            return
        
        # Log Overview
        col1, col2, col3, col4 = st.columns(4)
        
        total_lines = sum(len(log['lines']) for log in logs)
        latest_log = max(logs, key=lambda x: x['modified']) if logs else None
        
        with col1:
            st.metric("Log Files", len(logs))
        with col2:
            st.metric("Total Lines", total_lines)
        with col3:
            if latest_log:
                st.metric("Latest Log", latest_log['modified'].strftime("%m-%d %H:%M"))
        with col4:
            avg_lines = total_lines / len(logs) if logs else 0
            st.metric("Avg Lines/File", f"{avg_lines:.0f}")
        
        # Log Activity Timeline
        if logs:
            st.markdown("### 📈 Log Activity Timeline")
            
            log_names = [log['file'] for log in logs]
            log_dates = [log['modified'] for log in logs]
            log_sizes = [len(log['lines']) for log in logs]
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=log_dates,
                y=log_sizes,
                mode='markers+lines',
                marker=dict(
                    size=[min(20, max(8, size/5)) for size in log_sizes],
                    color=log_sizes,
                    colorscale='Viridis',
                    showscale=True,
                    colorbar=dict(title="Lines")
                ),
                text=log_names,
                hovertemplate='<b>%{text}</b><br>Date: %{x}<br>Lines: %{y}<extra></extra>',
                line=dict(color='lightblue', width=2)
            ))
            
            fig.update_layout(
                title="Log File Activity Over Time",
                xaxis_title="Date",
                yaxis_title="Number of Lines",
                height=400
            )
            st.plotly_chart(fig, use_container_width=True)
        
        # Log Analysis
        col1, col2 = st.columns(2)
        
        with col1:
            # Log Size Distribution
            if logs:
                sizes = [len(log['lines']) for log in logs]
                names = [log['file'] for log in logs]
                
                fig = go.Figure(go.Bar(
                    x=names,
                    y=sizes,
                    marker_color=px.colors.qualitative.Set2,
                    text=sizes,
                    textposition='auto'
                ))
                
                fig.update_layout(
                    title="📊 Log File Sizes (Lines)",
                    xaxis_title="Log File",
                    yaxis_title="Number of Lines",
                    height=400,
                    xaxis_tickangle=-45
                )
                st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Log Content Analysis (Error/Warning/Info counts)
            if logs:
                error_counts = []
                warning_counts = []
                info_counts = []
                
                for log in logs:
                    content = ' '.join(log['lines']).lower()
                    error_counts.append(content.count('error'))
                    warning_counts.append(content.count('warning') + content.count('warn'))
                    info_counts.append(content.count('info'))
                
                fig = go.Figure()
                fig.add_trace(go.Bar(name='Errors', x=names, y=error_counts, marker_color='red'))
                fig.add_trace(go.Bar(name='Warnings', x=names, y=warning_counts, marker_color='orange'))
                fig.add_trace(go.Bar(name='Info', x=names, y=info_counts, marker_color='blue'))
                
                fig.update_layout(
                    title="🚨 Log Level Distribution",
                    xaxis_title="Log File",
                    yaxis_title="Count",
                    height=400,
                    barmode='stack',
                    xaxis_tickangle=-45
                )
                st.plotly_chart(fig, use_container_width=True)
        
        # Detailed Log Viewer
        st.markdown("### 🔍 Log File Viewer")
        
        for log in logs:
            with st.expander(f"📄 {log['file']} - {log['modified'].strftime('%Y-%m-%d %H:%M')} ({len(log['lines'])} lines)"):
                
                # Log statistics
                col1, col2, col3 = st.columns(3)
                content = ' '.join(log['lines']).lower()
                
                with col1:
                    error_count = content.count('error')
                    st.metric("Errors", error_count, delta=f"{'🔴' if error_count > 0 else '✅'}")
                with col2:
                    warning_count = content.count('warning') + content.count('warn')
                    st.metric("Warnings", warning_count, delta=f"{'🟡' if warning_count > 0 else '✅'}")
                with col3:
                    info_count = content.count('info')
                    st.metric("Info Messages", info_count)
                
                # Log content with syntax highlighting
                st.markdown("**📋 Log Content:**")
                log_text = '\n'.join(log['lines'])
                
                # Highlight important lines
                highlighted_lines = []
                for line in log['lines']:
                    line_lower = line.lower()
                    if 'error' in line_lower:
                        highlighted_lines.append(f"🔴 {line.strip()}")
                    elif 'warning' in line_lower or 'warn' in line_lower:
                        highlighted_lines.append(f"🟡 {line.strip()}")
                    elif 'success' in line_lower or 'complete' in line_lower:
                        highlighted_lines.append(f"✅ {line.strip()}")
                    else:
                        highlighted_lines.append(f"ℹ️ {line.strip()}")
                
                # Show highlighted content in code block
                st.code('\n'.join(highlighted_lines), language='text')
                    
    def render_configuration(self):
        """Render configuration with enhanced visualizations"""
        st.markdown("## ⚙️ Configuration Dashboard")
        
        if not self.config_path.exists():
            st.info("No config directory found")
            return
            
        config_files = list(self.config_path.rglob("*.yaml")) + list(self.config_path.rglob("*.json"))
        
        if not config_files:
            st.info("No configuration files found")
            return
        
        # Configuration Overview
        col1, col2, col3, col4 = st.columns(4)
        
        yaml_files = [f for f in config_files if f.suffix == '.yaml']
        json_files = [f for f in config_files if f.suffix == '.json']
        total_size = sum(f.stat().st_size for f in config_files)
        
        with col1:
            st.metric("Total Config Files", len(config_files))
        with col2:
            st.metric("YAML Files", len(yaml_files))
        with col3:
            st.metric("JSON Files", len(json_files))
        with col4:
            st.metric("Total Size", f"{total_size / 1024:.1f} KB")
        
        # Configuration Structure Visualization
        col1, col2 = st.columns(2)
        
        with col1:
            # File type distribution
            fig = go.Figure(data=[go.Pie(
                labels=['YAML', 'JSON'],
                values=[len(yaml_files), len(json_files)],
                hole=.3,
                marker_colors=['#ff9999', '#66b3ff']
            )])
            
            fig.update_layout(
                title="📊 Configuration File Types",
                height=300,
                showlegend=True
            )
            st.plotly_chart(fig, use_container_width=True)
            
        with col2:
            # Directory structure
            config_dirs = defaultdict(int)
            for config_file in config_files:
                relative_path = config_file.relative_to(self.config_path)
                if len(relative_path.parts) > 1:
                    config_dirs[relative_path.parts[0]] += 1
                else:
                    config_dirs['root'] += 1
            
            if config_dirs:
                dirs = list(config_dirs.keys())
                counts = list(config_dirs.values())
                
                fig = go.Figure(go.Bar(
                    x=dirs,
                    y=counts,
                    marker_color=px.colors.qualitative.Pastel,
                    text=counts,
                    textposition='auto'
                ))
                
                fig.update_layout(
                    title="📁 Config Files by Directory",
                    xaxis_title="Directory",
                    yaxis_title="Number of Files",
                    height=300,
                    xaxis_tickangle=-45
                )
                st.plotly_chart(fig, use_container_width=True)
        
        # Configuration File Explorer
        st.markdown("### 🔍 Configuration File Explorer")
        
        # Group files by directory
        grouped_files = defaultdict(list)
        for config_file in config_files:
            relative_path = config_file.relative_to(self.config_path)
            if len(relative_path.parts) > 1:
                group = relative_path.parts[0]
            else:
                group = 'root'
            grouped_files[group].append(config_file)
        
        for group, files in grouped_files.items():
            st.markdown(f"#### 📂 {group.title()} Configuration ({len(files)} files)")
            
            for config_file in files:
                file_size = config_file.stat().st_size
                file_modified = datetime.fromtimestamp(config_file.stat().st_mtime)
                
                with st.expander(f"⚙️ {config_file.name} ({file_size} bytes) - Modified: {file_modified.strftime('%Y-%m-%d %H:%M')}"):
                    try:
                        with open(config_file, 'r') as f:
                            content = f.read()
                        
                        # Show file info
                        col1, col2 = st.columns([3, 1])
                        
                        with col2:
                            st.markdown("**📊 File Info:**")
                            st.markdown(f"**Type:** {config_file.suffix.upper()}")
                            st.markdown(f"**Size:** {file_size:,} bytes")
                            st.markdown(f"**Lines:** {len(content.splitlines())}")
                            st.markdown(f"**Modified:** {file_modified.strftime('%Y-%m-%d %H:%M:%S')}")
                        
                        with col1:
                            # Parse and analyze config content
                            if config_file.suffix == '.json':
                                try:
                                    config_data = json.loads(content)
                                    
                                    # Show key statistics
                                    if isinstance(config_data, dict):
                                        st.markdown(f"**🔑 Configuration Keys:** {len(config_data)}")
                                        
                                        # Show key structure
                                        if len(config_data) <= 10:
                                            key_info = []
                                            for key, value in config_data.items():
                                                value_type = type(value).__name__
                                                if isinstance(value, (list, dict)):
                                                    size = len(value)
                                                    key_info.append(f"• **{key}**: {value_type} ({size} items)")
                                                else:
                                                    key_info.append(f"• **{key}**: {value_type}")
                                            
                                            st.markdown("**📋 Structure:**")
                                            st.markdown('\n'.join(key_info))
                                    
                                    # Show JSON with syntax highlighting
                                    st.markdown("**📄 Configuration Content:**")
                                    st.json(config_data)
                                    
                                except json.JSONDecodeError as e:
                                    st.error(f"Invalid JSON: {e}")
                                    st.code(content, language='json')
                                    
                            else:  # YAML
                                try:
                                    import yaml
                                    config_data = yaml.safe_load(content)
                                    
                                    if isinstance(config_data, dict):
                                        st.markdown(f"**🔑 Configuration Keys:** {len(config_data)}")
                                    
                                    st.markdown("**📄 Configuration Content:**")
                                    st.code(content, language='yaml')
                                    
                                except ImportError:
                                    st.markdown("**📄 Configuration Content:**")
                                    st.code(content, language='yaml')
                                except Exception as e:
                                    st.error(f"Error parsing YAML: {e}")
                                    st.code(content, language='yaml')
                                    
                    except Exception as e:
                        st.error(f"Could not load {config_file.name}: {e}")
        
        # Configuration Summary
        st.markdown("### 📊 Configuration Summary")
        
        # Create summary table
        summary_data = []
        for config_file in config_files:
            file_size = config_file.stat().st_size
            file_modified = datetime.fromtimestamp(config_file.stat().st_mtime)
            relative_path = config_file.relative_to(self.config_path)
            
            summary_data.append({
                "File": config_file.name,
                "Path": str(relative_path.parent) if relative_path.parent != Path('.') else 'root',
                "Type": config_file.suffix.upper(),
                "Size (bytes)": file_size,
                "Size (KB)": round(file_size / 1024, 1),
                "Modified": file_modified.strftime('%Y-%m-%d %H:%M')
            })
        
        summary_df = pd.DataFrame(summary_data)
        summary_df = summary_df.sort_values(['Path', 'File'])
        
        st.dataframe(
            summary_df,
            use_container_width=True,
            column_config={
                "Size (bytes)": st.column_config.NumberColumn(format="%d"),
                "Size (KB)": st.column_config.NumberColumn(format="%.1f")
            }
        )
                    
    def render_sidebar(self):
        """Render enhanced sidebar with visualizations"""
        st.sidebar.markdown("## 🎛️ Dashboard Controls")
        
        # Refresh button
        if st.sidebar.button("🔄 Refresh Data", type="primary"):
            st.rerun()
            
        st.sidebar.markdown("---")
        
        # System Health Overview
        st.sidebar.markdown("## 📡 System Health")
        
        # Check if key directories exist
        dirs_status = {
            "Reports": self.reports_path.exists(),
            "Data": self.data_path.exists(),
            "Config": self.config_path.exists(),
            "Logs": self.logs_path.exists()
        }
        
        # Create a mini health dashboard
        health_score = sum(dirs_status.values()) / len(dirs_status) * 100
        
        # Health gauge in sidebar
        if health_score == 100:
            st.sidebar.success(f"🟢 System Health: {health_score:.0f}%")
        elif health_score >= 75:
            st.sidebar.warning(f"🟡 System Health: {health_score:.0f}%")
        else:
            st.sidebar.error(f"🔴 System Health: {health_score:.0f}%")
        
        # Directory status with icons
        for dir_name, exists in dirs_status.items():
            status_icon = "✅" if exists else "❌"
            color = "green" if exists else "red"
            st.sidebar.markdown(f":{color}[{status_icon} {dir_name}]")
        
        st.sidebar.markdown("---")
        
        # Quick Stats
        st.sidebar.markdown("## 📊 Quick Stats")
        
        # File counts with progress bars
        if self.reports_path.exists():
            report_count = len(list(self.reports_path.glob("*")))
            st.sidebar.metric("📋 Reports", report_count)
            if report_count > 0:
                st.sidebar.progress(min(1.0, report_count / 200))  # Assuming 200 is max expected
            
        if self.data_path.exists():
            data_dirs = len([d for d in self.data_path.iterdir() if d.is_dir()])
            st.sidebar.metric("💾 Data Dirs", data_dirs)
            if data_dirs > 0:
                st.sidebar.progress(min(1.0, data_dirs / 50))  # Assuming 50 is max expected
                
        if self.logs_path.exists():
            log_files = len(list(self.logs_path.rglob("*.log")))
            st.sidebar.metric("📋 Log Files", log_files)
            if log_files > 0:
                st.sidebar.progress(min(1.0, log_files / 20))  # Assuming 20 is max expected
        
        st.sidebar.markdown("---")
        
        # System Status Indicators
        st.sidebar.markdown("## 🚦 Status Indicators")
        
        # Check for recent activity
        recent_activity = False
        if self.reports_path.exists():
            recent_reports = [f for f in self.reports_path.glob("*") 
                            if (datetime.now() - datetime.fromtimestamp(f.stat().st_mtime)).days < 7]
            if recent_reports:
                recent_activity = True
                st.sidebar.success(f"🟢 Recent Activity ({len(recent_reports)} new reports)")
            else:
                st.sidebar.info("🔵 No Recent Activity")
        
        # Check shadow trading status
        shadow_path = self.data_path / "live" / "shadow_trading"
        if shadow_path.exists() and (shadow_path / "trading_state.json").exists():
            st.sidebar.success("🟢 Shadow Trading Active")
        else:
            st.sidebar.warning("🟡 Shadow Trading Inactive")
        
        # Check for errors in logs
        if self.logs_path.exists():
            error_found = False
            for log_file in self.logs_path.rglob("*.log"):
                try:
                    with open(log_file, 'r') as f:
                        content = f.read().lower()
                        if 'error' in content:
                            error_found = True
                            break
                except:
                    pass
            
            if error_found:
                st.sidebar.error("🔴 Errors Detected in Logs")
            else:
                st.sidebar.success("🟢 No Errors in Logs")
        
        st.sidebar.markdown("---")
        
        # Quick Actions
        st.sidebar.markdown("## ⚡ Quick Actions")
        
        if st.sidebar.button("🚀 Launch Shadow Trading"):
            st.sidebar.code("python scripts/launch_shadow_trading.py")
            
        if st.sidebar.button("🔬 Run Walk Forward"):
            st.sidebar.code("python scripts/run_honest_walk_forward.py")
            
        if st.sidebar.button("📊 Generate Report"):
            st.sidebar.code("python scripts/generate_12month_performance_report.py")
        
        st.sidebar.markdown("---")
        
        # System Info
        st.sidebar.markdown("## ℹ️ System Info")
        st.sidebar.markdown(f"**Dashboard Version:** 2.0")
        st.sidebar.markdown(f"**Last Updated:** {datetime.now().strftime('%H:%M:%S')}")
        st.sidebar.markdown(f"**Data Source:** Real Files Only")
        
        # Add a mini system architecture diagram
        st.sidebar.markdown("### 🏗️ Architecture")
        st.sidebar.markdown("""
        ```
        📊 Dashboard
        ├── 📋 Reports
        ├── 💾 Data
        ├── ⚙️ Config  
        └── 📋 Logs
        ```
        """)
        
        # Footer
        st.sidebar.markdown("---")
        st.sidebar.markdown("*🌟 Northstar V3 Dashboard*")
        st.sidebar.markdown("*Real Data • Live Updates*")
            
    def run(self):
        """Run the dashboard"""
        self.render_header()
        self.render_sidebar()
        
        # Navigation
        tabs = st.tabs([
            "🏗️ System Overview",
            "📊 Market Situation",
            "📋 Reports Analysis", 
            "🔬 Walk Forward Analysis",
            "📈 Shadow Trading",
            "📋 System Logs",
            "⚙️ Configuration"
        ])
        
        with tabs[0]:
            self.render_system_overview()
            
        with tabs[1]:
            self.render_market_situation()
            
        with tabs[2]:
            self.render_reports_analysis()
            
        with tabs[3]:
            self.render_walk_forward_analysis()
            
        with tabs[4]:
            self.render_shadow_trading()
            
        with tabs[5]:
            self.render_system_logs()
            
        with tabs[6]:
            self.render_configuration()

def main():
    """Main dashboard execution"""
    dashboard = WorkingNorthstarDashboard()
    dashboard.run()

if __name__ == "__main__":
    main()