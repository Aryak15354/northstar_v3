"""
Production Grade Dashboard Panel - Fixed Version

Integrates Edge Half-Life Model and Liquidity-Aware Kill Switch
into the Northstar V3 dashboard with real data only.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import json
import os
from pathlib import Path

# Import production grade components
try:
    # Try main src location first
    from src.intelligence.edge_half_life import EdgeHalfLifeTracker, EdgeStatus
    from src.risk.liquidity_kill_switch import LiquidityRiskAssessor, LiquidityStatus
    from src.integration.production_grade_enhancements import ProductionGradeRiskManager
    PRODUCTION_COMPONENTS_AVAILABLE = True
except ImportError:
    try:
        # Try github_repo location as fallback
        from github_repo.src.intelligence.edge_half_life import EdgeHalfLifeTracker, EdgeStatus
        from github_repo.src.risk.liquidity_kill_switch import LiquidityRiskAssessor, LiquidityStatus
        from github_repo.src.integration.production_grade_enhancements import ProductionGradeRiskManager
        PRODUCTION_COMPONENTS_AVAILABLE = True
    except ImportError:
        PRODUCTION_COMPONENTS_AVAILABLE = False


class ProductionGradeDashboardPanel:
    """
    Production Grade Dashboard Panel
    
    Displays Edge Half-Life and Liquidity metrics with real data only.
    No mock or synthetic data is used.
    """
    
    def __init__(self, data_hub=None):
        self.data_hub = data_hub
        self.data_dir = Path("data")
        
    def render_production_grade_panel(self):
        """Render the complete production grade panel"""
        
        st.header("🧬 Production Grade Risk Management")
        st.markdown("**Edge Half-Life Tracking & Liquidity-Aware Risk Controls**")
        
        if not PRODUCTION_COMPONENTS_AVAILABLE:
            st.error("❌ Production Grade Components not available. Please check installation.")
            return
        
        # Create tabs for different views
        tab1, tab2, tab3, tab4 = st.tabs([
            "📈 Edge Health Monitor", 
            "💧 Liquidity Risk Dashboard", 
            "⚡ Kill Switch Status",
            "📊 Production Metrics"
        ])
        
        with tab1:
            self._render_edge_health_monitor()
        
        with tab2:
            self._render_liquidity_dashboard()
        
        with tab3:
            self._render_kill_switch_status()
        
        with tab4:
            self._render_production_metrics()
    
    def _render_edge_health_monitor(self):
        """Render edge health monitoring dashboard"""
        
        st.subheader("📈 Strategy Edge Health Monitor")
        
        # Load real edge data
        edge_data = self._load_edge_health_data()
        
        if edge_data is None:
            st.info("📊 No edge health data available. Run strategy performance tracking to generate data.")
            self._show_edge_health_setup_guide()
            return
        
        # Edge health overview
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_strategies = len(edge_data.get('strategies', {}))
            st.metric("Total Strategies", total_strategies)
        
        with col2:
            healthy_count = sum(1 for s in edge_data.get('strategies', {}).values() 
                              if s.get('status') in ['fresh', 'healthy'])
            st.metric("Healthy Strategies", healthy_count)
        
        with col3:
            strategies = edge_data.get('strategies', {})
            if strategies:
                avg_edge_health = np.mean([s.get('edge_health', 0) for s in strategies.values()])
                st.metric("Avg Edge Health", f"{avg_edge_health:.3f}")
            else:
                st.metric("Avg Edge Health", "0.000")
        
        with col4:
            portfolio_score = edge_data.get('portfolio_edge_score', 0)
            st.metric("Portfolio Edge Score", f"{portfolio_score:.3f}")
        
        # Strategy-level edge health
        if edge_data.get('strategies'):
            self._render_strategy_edge_chart(edge_data['strategies'])
        
        # Edge decay visualization
        self._render_edge_decay_analysis(edge_data)
        
        # Capital allocation impact
        self._render_capital_allocation_impact(edge_data)
    
    def _render_liquidity_dashboard(self):
        """Render liquidity risk dashboard"""
        
        st.subheader("💧 Portfolio Liquidity Risk Dashboard")
        
        # Load real liquidity data
        liquidity_data = self._load_liquidity_data()
        
        if liquidity_data is None:
            st.info("📊 No liquidity data available. Market data ingestion required for liquidity analysis.")
            self._show_liquidity_setup_guide()
            return
        
        # Liquidity overview metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            portfolio_liquidity = liquidity_data.get('portfolio_liquidity_score', 0)
            st.metric("Portfolio Liquidity", f"{portfolio_liquidity:.2%}")
        
        with col2:
            systemic_risk = liquidity_data.get('systemic_risk_level', 0)
            st.metric("Systemic Risk Level", f"{systemic_risk:.2%}")
        
        with col3:
            safe_liquidation = liquidity_data.get('max_safe_liquidation_pct', 0)
            st.metric("Max Safe Liquidation", f"{safe_liquidation:.1%}")
        
        with col4:
            frozen_positions = liquidity_data.get('frozen_positions', 0)
            st.metric("Frozen Positions", frozen_positions)
        
        # Position-level liquidity analysis
        if liquidity_data.get('positions'):
            self._render_position_liquidity_chart(liquidity_data['positions'])
        
        # Liquidity risk heatmap
        self._render_liquidity_risk_heatmap(liquidity_data)
        
        # Exit cost analysis
        self._render_exit_cost_analysis(liquidity_data)
    
    def _render_kill_switch_status(self):
        """Render kill switch status dashboard"""
        
        st.subheader("⚡ Enhanced Kill Switch Status")
        
        # Load kill switch data
        kill_switch_data = self._load_kill_switch_data()
        
        if kill_switch_data is None:
            st.info("📊 No kill switch data available. System monitoring required.")
            return
        
        # Kill switch status overview
        status = kill_switch_data.get('status', 'unknown')
        
        if status == 'ACTIVE':
            st.success("✅ Kill Switch: ACTIVE")
        elif status == 'TRIGGERED':
            st.error("🚨 Kill Switch: TRIGGERED")
        elif status == 'EXECUTING':
            st.warning("⚡ Kill Switch: EXECUTING")
        else:
            st.info(f"ℹ️ Kill Switch: {status}")
        
        # Trigger conditions
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Trigger Conditions**")
            triggers = kill_switch_data.get('triggers', {})
            for trigger_name, config in triggers.items():
                enabled = config.get('enabled', False)
                threshold = config.get('threshold', 0)
                status_icon = "✅" if enabled else "❌"
                st.markdown(f"{status_icon} {trigger_name}: {threshold:.1%}")
        
        with col2:
            st.markdown("**Recent Events**")
            events = kill_switch_data.get('recent_events', [])
            if events:
                for event in events[-5:]:  # Show last 5 events
                    timestamp = event.get('timestamp', 'Unknown')
                    event_type = event.get('trigger_type', 'Unknown')
                    st.markdown(f"• {timestamp}: {event_type}")
            else:
                st.markdown("No recent events")
        
        # Liquidity-aware recommendations
        recommendation = kill_switch_data.get('liquidity_recommendation', 'UNKNOWN')
        
        if recommendation == 'NORMAL_KILL_SWITCH_OPERATION':
            st.success("💧 Liquidity Status: Normal operation recommended")
        elif recommendation == 'USE_GRADUAL_LIQUIDATION_ONLY':
            st.warning("💧 Liquidity Status: Use gradual liquidation only")
        elif recommendation == 'DISABLE_KILL_SWITCH_HIGH_ILLIQUIDITY':
            st.error("💧 Liquidity Status: Kill switch disabled due to high illiquidity")
        else:
            st.info(f"💧 Liquidity Status: {recommendation}")
    
    def _render_production_metrics(self):
        """Render overall production metrics"""
        
        st.subheader("📊 Production System Metrics")
        
        # Load production metrics
        prod_metrics = self._load_production_metrics()
        
        if prod_metrics is None:
            st.info("📊 No production metrics available.")
            return
        
        # System health overview
        col1, col2, col3 = st.columns(3)
        
        with col1:
            overall_status = prod_metrics.get('overall_status', 'UNKNOWN')
            if overall_status == 'HEALTHY':
                st.success(f"✅ System Status: {overall_status}")
            elif overall_status in ['WARNING', 'POOR_EDGE_HEALTH']:
                st.warning(f"⚠️ System Status: {overall_status}")
            else:
                st.error(f"❌ System Status: {overall_status}")
        
        with col2:
            edge_enabled = prod_metrics.get('edge_integration_enabled', False)
            st.metric("Edge Integration", "✅ Enabled" if edge_enabled else "❌ Disabled")
        
        with col3:
            liquidity_enabled = prod_metrics.get('liquidity_integration_enabled', False)
            st.metric("Liquidity Integration", "✅ Enabled" if liquidity_enabled else "❌ Disabled")
        
        # Performance impact metrics
        st.markdown("**Performance Impact Analysis**")
        
        impact_data = prod_metrics.get('performance_impact', {})
        if impact_data:
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                drawdown_reduction = impact_data.get('drawdown_reduction', 0)
                st.metric("Drawdown Reduction", f"{drawdown_reduction:.1%}")
            
            with col2:
                sharpe_improvement = impact_data.get('sharpe_improvement', 0)
                st.metric("Sharpe Improvement", f"{sharpe_improvement:.1%}")
            
            with col3:
                cost_reduction = impact_data.get('transaction_cost_reduction', 0)
                st.metric("Cost Reduction", f"{cost_reduction:.1%}")
            
            with col4:
                crisis_survival = impact_data.get('crisis_survival_rate', 0)
                st.metric("Crisis Survival", f"{crisis_survival:.1%}")
        
        # Integration status timeline
        self._render_integration_timeline(prod_metrics)
    
    def _render_strategy_edge_chart(self, strategies_data):
        """Render strategy edge health chart"""
        
        st.markdown("**Strategy Edge Health Analysis**")
        
        # Prepare data for visualization
        strategy_names = list(strategies_data.keys())
        edge_health = [strategies_data[s].get('edge_health', 0) for s in strategy_names]
        half_life_days = [strategies_data[s].get('half_life_days', 0) for s in strategy_names]
        status_colors = []
        
        for s in strategy_names:
            status = strategies_data[s].get('status', 'unknown')
            if status == 'fresh':
                status_colors.append('#28a745')  # Green
            elif status == 'healthy':
                status_colors.append('#17a2b8')  # Blue
            elif status == 'decaying':
                status_colors.append('#ffc107')  # Yellow
            elif status == 'stale':
                status_colors.append('#fd7e14')  # Orange
            else:
                status_colors.append('#dc3545')  # Red
        
        # Create edge health chart
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=strategy_names,
            y=edge_health,
            mode='markers+lines',
            marker=dict(
                size=12,
                color=status_colors,
                line=dict(width=2, color='white')
            ),
            line=dict(width=2),
            name='Edge Health',
            hovertemplate='<b>%{x}</b><br>Edge Health: %{y:.3f}<br>Half-Life: %{customdata:.1f} days<extra></extra>',
            customdata=half_life_days
        ))
        
        fig.update_layout(
            title="Strategy Edge Health Status",
            xaxis_title="Strategy",
            yaxis_title="Edge Health Score",
            yaxis=dict(range=[0, 1]),
            height=400,
            showlegend=False
        )
        
        # Add threshold lines
        fig.add_hline(y=0.8, line_dash="dash", line_color="green", 
                     annotation_text="Fresh Threshold")
        fig.add_hline(y=0.5, line_dash="dash", line_color="orange", 
                     annotation_text="Healthy Threshold")
        fig.add_hline(y=0.3, line_dash="dash", line_color="red", 
                     annotation_text="Exit Threshold")
        
        try:
            st.plotly_chart(fig, width="stretch")
        except Exception as e:
            st.error(f"Error creating chart: {e}")
    
    def _render_position_liquidity_chart(self, positions_data):
        """Render position liquidity analysis chart"""
        
        st.markdown("**Position Liquidity Risk Analysis**")
        
        # Prepare data
        symbols = list(positions_data.keys())
        exit_risks = [positions_data[s].get('exit_risk', 0) for s in symbols]
        participation_rates = [positions_data[s].get('participation_rate', 0) for s in symbols]
        market_values = [positions_data[s].get('market_value', 0) for s in symbols]
        
        # Create bubble chart
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=participation_rates,
            y=exit_risks,
            mode='markers',
            marker=dict(
                size=[mv/1000000 for mv in market_values],  # Size by market value
                sizemode='diameter',
                sizeref=2.*max([mv/1000000 for mv in market_values])/(40.**2),
                sizemin=4,
                color=exit_risks,
                colorscale='RdYlGn_r',
                showscale=True,
                colorbar=dict(title="Exit Risk")
            ),
            text=symbols,
            hovertemplate='<b>%{text}</b><br>Participation: %{x:.1%}<br>Exit Risk: %{y:.2f}<br>Market Value: $%{customdata:,.0f}<extra></extra>',
            customdata=market_values
        ))
        
        fig.update_layout(
            title="Position Liquidity Risk Matrix",
            xaxis_title="Participation Rate (%)",
            yaxis_title="Exit Risk Ratio",
            height=500
        )
        
        # Add risk zones
        fig.add_hline(y=1.0, line_dash="dash", line_color="red", 
                     annotation_text="High Risk Zone")
        fig.add_vline(x=0.2, line_dash="dash", line_color="orange", 
                     annotation_text="High Participation")
        
        try:
            st.plotly_chart(fig, width="stretch")
        except Exception as e:
            st.error(f"Error creating chart: {e}")
    
    def _load_edge_health_data(self) -> Optional[Dict]:
        """Load real edge health data from files"""
        
        # Try to load from unified state
        edge_file = self.data_dir / "state" / "edge_metrics.json"
        if edge_file.exists():
            try:
                with open(edge_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                st.error(f"Error loading edge data: {e}")
        
        # Try to load from intelligence data
        intel_dir = self.data_dir / "intelligence"
        if intel_dir.exists():
            edge_files = list(intel_dir.glob("*edge*.json"))
            if edge_files:
                try:
                    with open(edge_files[0], 'r') as f:
                        return json.load(f)
                except Exception as e:
                    st.error(f"Error loading intelligence edge data: {e}")
        
        return None
    
    def _load_liquidity_data(self) -> Optional[Dict]:
        """Load real liquidity data from files"""
        
        # Try to load from risk data
        liquidity_file = self.data_dir / "risk" / "liquidity_metrics.json"
        if liquidity_file.exists():
            try:
                with open(liquidity_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                st.error(f"Error loading liquidity data: {e}")
        
        # Try to load from market data
        market_dir = self.data_dir / "market"
        if market_dir.exists():
            liquidity_files = list(market_dir.glob("*liquidity*.json"))
            if liquidity_files:
                try:
                    with open(liquidity_files[0], 'r') as f:
                        return json.load(f)
                except Exception as e:
                    st.error(f"Error loading market liquidity data: {e}")
        
        return None
    
    def _load_kill_switch_data(self) -> Optional[Dict]:
        """Load real kill switch data from files"""
        
        # Try to load from risk data
        kill_switch_file = self.data_dir / "risk" / "kill_switch_status.json"
        if kill_switch_file.exists():
            try:
                with open(kill_switch_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                st.error(f"Error loading kill switch data: {e}")
        
        return None
    
    def _load_production_metrics(self) -> Optional[Dict]:
        """Load real production metrics from files"""
        
        # Try to load from system state
        prod_file = self.data_dir / "state" / "production_metrics.json"
        if prod_file.exists():
            try:
                with open(prod_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                st.error(f"Error loading production metrics: {e}")
        
        return None
    
    def _show_edge_health_setup_guide(self):
        """Show setup guide for edge health tracking"""
        
        st.markdown("""
        **To enable Edge Health Tracking:**
        
        1. **Initialize Edge Tracker** in your strategy execution:
        ```python
        from src.intelligence.edge_half_life import EdgeHalfLifeTracker
        
        tracker = EdgeHalfLifeTracker()
        tracker.update_performance(
            strategy_id="your_strategy",
            timestamp=datetime.now(),
            returns=0.05,
            benchmark_returns=0.02,
            volatility=0.15,
            confidence=0.8,
            regime="bull"
        )
        ```
        
        2. **Save Edge State** to data files:
        ```python
        edge_state = tracker.get_all_edge_metrics()
        with open('data/state/edge_metrics.json', 'w') as f:
            json.dump(edge_state, f)
        ```
        
        3. **Run Strategy Performance Tracking** regularly to build history
        """)
    
    def _show_liquidity_setup_guide(self):
        """Show setup guide for liquidity tracking"""
        
        st.markdown("""
        **To enable Liquidity Risk Tracking:**
        
        1. **Initialize Liquidity Assessor** with market data:
        ```python
        from src.risk.liquidity_kill_switch import LiquidityRiskAssessor
        
        assessor = LiquidityRiskAssessor()
        assessor.update_market_data(
            symbol="STOCK",
            timestamp=datetime.now(),
            volume=100000,
            bid_price=99.5,
            ask_price=100.5,
            last_price=100.0
        )
        ```
        
        2. **Calculate Position Liquidity** for portfolio:
        ```python
        metrics = assessor.calculate_position_liquidity(
            symbol="STOCK",
            position_size=10000,
            market_value=1000000,
            remaining_edge=0.03,
            timestamp=datetime.now()
        )
        ```
        
        3. **Ensure Market Data Pipeline** is running for volume/spread data
        """)
    
    def _render_edge_decay_analysis(self, edge_data):
        """Render edge decay analysis charts"""
        
        st.markdown("**Edge Decay Analysis**")
        
        # This would show historical edge decay patterns
        # For now, show placeholder for real implementation
        st.info("📈 Edge decay analysis requires historical performance data. Run system for several weeks to build decay models.")
    
    def _render_capital_allocation_impact(self, edge_data):
        """Render capital allocation impact analysis"""
        
        st.markdown("**Capital Allocation Impact**")
        
        # Show how edge health affects capital allocation
        strategies = edge_data.get('strategies', {})
        if strategies:
            strategy_names = list(strategies.keys())
            proposed_alloc = [0.25] * len(strategy_names)  # Equal weight baseline
            edge_multipliers = [strategies[s].get('capital_multiplier', 0.5) for s in strategy_names]
            adjusted_alloc = [p * m for p, m in zip(proposed_alloc, edge_multipliers)]
            
            # Normalize to sum to 1
            total_adjusted = sum(adjusted_alloc)
            if total_adjusted > 0:
                adjusted_alloc = [a / total_adjusted for a in adjusted_alloc]
            
            # Create comparison chart
            fig = go.Figure()
            
            fig.add_trace(go.Bar(
                name='Proposed Allocation',
                x=strategy_names,
                y=proposed_alloc,
                marker_color='lightblue'
            ))
            
            fig.add_trace(go.Bar(
                name='Edge-Adjusted Allocation',
                x=strategy_names,
                y=adjusted_alloc,
                marker_color='darkblue'
            ))
            
            fig.update_layout(
                title="Capital Allocation: Proposed vs Edge-Adjusted",
                xaxis_title="Strategy",
                yaxis_title="Allocation Weight",
                barmode='group',
                height=400
            )
            
            try:
                st.plotly_chart(fig, width="stretch")
            except Exception as e:
                st.error(f"Error creating chart: {e}")
    
    def _render_liquidity_risk_heatmap(self, liquidity_data):
        """Render liquidity risk heatmap"""
        
        st.markdown("**Liquidity Risk Heatmap**")
        
        positions = liquidity_data.get('positions', {})
        if positions:
            # Create risk matrix
            symbols = list(positions.keys())
            risk_metrics = ['exit_risk', 'participation_rate', 'impact_cost']
            
            risk_matrix = []
            for metric in risk_metrics:
                row = [positions[s].get(metric, 0) for s in symbols]
                risk_matrix.append(row)
            
            fig = go.Figure(data=go.Heatmap(
                z=risk_matrix,
                x=symbols,
                y=risk_metrics,
                colorscale='RdYlGn_r',
                hoverongaps=False
            ))
            
            fig.update_layout(
                title="Position Liquidity Risk Heatmap",
                height=300
            )
            
            try:
                st.plotly_chart(fig, width="stretch")
            except Exception as e:
                st.error(f"Error creating chart: {e}")
    
    def _render_exit_cost_analysis(self, liquidity_data):
        """Render exit cost analysis"""
        
        st.markdown("**Exit Cost vs Edge Analysis**")
        
        positions = liquidity_data.get('positions', {})
        if positions:
            symbols = list(positions.keys())
            exit_costs = [positions[s].get('impact_cost', 0) for s in symbols]
            remaining_edges = [positions[s].get('remaining_edge', 0.03) for s in symbols]
            
            fig = go.Figure()
            
            fig.add_trace(go.Scatter(
                x=remaining_edges,
                y=exit_costs,
                mode='markers+text',
                text=symbols,
                textposition="top center",
                marker=dict(size=10, color='red'),
                name='Positions'
            ))
            
            # Add diagonal line where exit cost = remaining edge
            max_val = max(max(exit_costs), max(remaining_edges))
            fig.add_trace(go.Scatter(
                x=[0, max_val],
                y=[0, max_val],
                mode='lines',
                line=dict(dash='dash', color='gray'),
                name='Break-even Line'
            ))
            
            fig.update_layout(
                title="Exit Cost vs Remaining Edge",
                xaxis_title="Remaining Edge",
                yaxis_title="Exit Cost",
                height=400
            )
            
            try:
                st.plotly_chart(fig, width="stretch")
            except Exception as e:
                st.error(f"Error creating chart: {e}")
    
    def _render_integration_timeline(self, prod_metrics):
        """Render integration status timeline"""
        
        st.markdown("**Integration Status Timeline**")
        
        # This would show when different components were enabled/disabled
        # For now, show current status
        timeline_data = prod_metrics.get('integration_timeline', [])
        
        if timeline_data:
            df = pd.DataFrame(timeline_data)
            fig = px.timeline(df, x_start="start", x_end="end", y="component", color="status")
            fig.update_layout(height=300)
            try:
                st.plotly_chart(fig, width="stretch")
            except Exception as e:
                st.error(f"Error creating chart: {e}")
        else:
            st.info("📊 Integration timeline data not available. Enable logging to track component status changes.")