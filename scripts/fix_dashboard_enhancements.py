#!/usr/bin/env python3
"""
🔧 FIX DASHBOARD ENHANCEMENTS
Fix the dashboard enhancement integration issues
"""

import os

def fix_dashboard_enhancements():
    """Fix dashboard enhancement integration"""
    
    dashboard_path = 'src/dashboard/northstar_v3_dashboard.py'
    
    if not os.path.exists(dashboard_path):
        print("❌ Dashboard file not found")
        return False
    
    with open(dashboard_path, 'r') as f:
        content = f.read()
    
    # Add the missing render_comparison_analysis method
    comparison_method = '''
    def render_comparison_analysis(self, days_back: int):
        """Render comparison analysis for specified period"""
        
        st.markdown(f"### 📈 Changes Over Last {days_back} Days")
        
        try:
            # Get historical data
            portfolio_changes = time_series_manager.get_portfolio_changes(days_back)
            trades_summary = time_series_manager.get_trades_summary(days_back)
            returns_analysis = time_series_manager.get_returns_analysis(days_back)
            metrics_trends = time_series_manager.get_metrics_trends(days_back)
            
            # Portfolio changes
            if portfolio_changes:
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    value_change = portfolio_changes['total_value_change']
                    value_change_pct = portfolio_changes['total_value_change_pct']
                    color = "normal" if value_change >= 0 else "inverse"
                    st.metric(
                        "Portfolio Value Change",
                        f"₹{value_change/10_000_000:.2f}Cr",
                        f"{value_change_pct:+.2f}%",
                        delta_color=color
                    )
                
                with col2:
                    pos_change = portfolio_changes['positions_change']
                    st.metric(
                        "Positions Change",
                        f"{portfolio_changes['current_value']/10_000_000:.1f}Cr",
                        f"{pos_change:+d} positions"
                    )
                
                with col3:
                    beta_change = portfolio_changes['beta_change']
                    st.metric(
                        "Portfolio Beta",
                        f"{portfolio_changes.get('current_beta', 0.88):.3f}",
                        f"{beta_change:+.3f}"
                    )
                
                with col4:
                    conc_change = portfolio_changes['concentration_change']
                    st.metric(
                        "Concentration Risk",
                        f"{portfolio_changes.get('current_concentration', 0.32):.1%}",
                        f"{conc_change:+.1%}"
                    )
            
            # Trading activity
            if trades_summary:
                st.markdown("#### 🔄 Trading Activity")
                
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("Total Trades", trades_summary['total_trades'])
                
                with col2:
                    st.metric("Trading Volume", f"₹{trades_summary['total_volume']/10_000_000:.1f}Cr")
                
                with col3:
                    pnl = trades_summary['total_pnl']
                    color = "normal" if pnl >= 0 else "inverse"
                    st.metric("Trading P&L", f"₹{pnl/100_000:.1f}L", delta_color=color)
                
                with col4:
                    st.metric("Win Rate", f"{trades_summary['win_rate']:.1f}%")
            
            # Returns analysis
            if returns_analysis:
                st.markdown("#### 📈 Returns Analysis")
                
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    period_return = returns_analysis['period_return']
                    color = "normal" if period_return >= 0 else "inverse"
                    st.metric("Period Return", f"{period_return:+.2f}%", delta_color=color)
                
                with col2:
                    st.metric("Annualized Return", f"{returns_analysis['annualized_return']:.1f}%")
                
                with col3:
                    st.metric("Sharpe Ratio", f"{returns_analysis['sharpe_ratio']:.2f}")
                
                with col4:
                    max_dd = returns_analysis['max_drawdown']
                    st.metric("Max Drawdown", f"{max_dd:.2f}%", delta_color="inverse")
        
        except Exception as e:
            st.error(f"Error loading comparison data: {e}")
            st.info("Historical data will be available after the system runs for a few days.")
'''
    
    # Add enhanced CSS with better color contrast
    enhanced_css = '''
        /* Enhanced readability - ensure all text is dark on light backgrounds */
        .stApp, .stApp * {
            color: #1a1a1a !important;
        }
        
        /* Force white backgrounds */
        .stApp, .main, .block-container,
        div[data-testid="stAppViewContainer"] {
            background-color: #ffffff !important;
        }
        
        /* Fix metric containers */
        div[data-testid="metric-container"] {
            background-color: #f8f9fa !important;
            color: #1a1a1a !important;
            border: 1px solid #dee2e6 !important;
        }
        
        div[data-testid="metric-container"] * {
            color: #1a1a1a !important;
        }
'''
    
    # Find where to insert the comparison method
    if "def render_time_series_comparison_panel(self):" in content:
        # Insert the comparison method after the time series panel method
        insertion_point = content.find("def render_time_series_comparison_panel(self):")
        # Find the end of this method
        method_end = content.find("\n    def ", insertion_point + 1)
        if method_end == -1:
            method_end = content.find("\n\n# Global instance", insertion_point)
        
        if method_end != -1:
            content = content[:method_end] + comparison_method + content[method_end:]
    
    # Add enhanced CSS to the existing CSS section
    if "/* Enhanced readability fixes */" in content:
        content = content.replace(
            "/* Enhanced readability fixes */",
            f"/* Enhanced readability fixes */{enhanced_css}"
        )
    
    # Write the fixed content
    with open(dashboard_path, 'w') as f:
        f.write(content)
    
    print("✅ Dashboard enhancements fixed")
    return True

def main():
    """Main execution"""
    
    print("🔧 FIXING DASHBOARD ENHANCEMENTS")
    print("=" * 40)
    
    if fix_dashboard_enhancements():
        print("✅ Dashboard enhancements fixed successfully!")
    else:
        print("❌ Failed to fix dashboard enhancements")

if __name__ == "__main__":
    main()