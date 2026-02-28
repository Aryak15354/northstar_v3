#!/usr/bin/env python3
"""
📊 RISK STATE DASHBOARD - INSTITUTIONAL VALIDATION LAYER 2
Real-time risk monitoring and visualization system

This dashboard provides institutional-grade risk monitoring with:
- Exposure over time with kill switch activations
- Drawdown vs threshold tracking
- Sector risk utilization monitoring
- Kill switch activation history
- Risk level trending

Key Features:
- Real-time risk state visualization
- Kill switch activation alerts
- Sector concentration monitoring
- Historical risk trend analysis
- Export capabilities for reporting

Usage:
    from src.validation.risk_state_dashboard import RiskStateDashboard
    
    dashboard = RiskStateDashboard()
    dashboard.generate_risk_dashboard()
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import warnings
warnings.filterwarnings('ignore')

# Set style for professional charts
plt.style.use('default')
plt.rcParams['figure.facecolor'] = 'white'
plt.rcParams['axes.facecolor'] = 'white'
plt.rcParams['axes.grid'] = True
plt.rcParams['grid.alpha'] = 0.3


class RiskStateDashboard:
    """
    Risk State Dashboard - Institutional Validation Layer 2
    
    Provides comprehensive risk monitoring and visualization:
    1. Exposure Timeline with Kill Switch Activations
    2. Drawdown vs Threshold Tracking
    3. Sector Risk Utilization Heatmap
    4. Risk Level Trending
    5. Kill Switch Activation Summary
    
    All charts are saved to docs/figures/risk/ for institutional reporting.
    """
    
    def __init__(self):
        """Initialize risk state dashboard"""
        # File paths
        self.risk_state_file = 'data/risk/risk_state.parquet'
        self.risk_budget_file = 'data/risk/risk_budget.parquet'
        self.risk_budget_state_file = 'data/risk/risk_budget_state.parquet'
        self.performance_file = 'data/processed/performance_summary.parquet'
        
        # Output directory
        self.output_dir = 'docs/figures/risk'
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Chart configuration
        self.figsize = (15, 10)
        self.dpi = 300
        
        # Risk thresholds for visualization
        self.risk_thresholds = {
            'max_drawdown': 0.20,
            'max_daily_loss': 0.05,
            'max_volatility': 0.30,
            'high_risk_level': 0.75,
            'medium_risk_level': 0.50
        }
        
        # Sector limits for visualization
        self.sector_limits = {
            'Banks': 0.10,
            'IT': 0.08,
            'Metals': 0.06,
            'Pharma': 0.07,
            'Auto': 0.05,
            'FMCG': 0.05,
            'Energy': 0.05,
            'Telecom': 0.04,
            'Realty': 0.03,
            'Media': 0.02,
            'Others': 0.05
        }
    
    def load_risk_data(self) -> Tuple[Optional[pd.DataFrame], Optional[pd.DataFrame], Optional[pd.DataFrame]]:
        """
        Load all risk-related data files
        
        Returns:
            Tuple of (risk_state_df, risk_budget_df, performance_df)
        """
        risk_state_df = None
        risk_budget_df = None
        performance_df = None
        
        # Load risk state data
        try:
            if os.path.exists(self.risk_state_file):
                risk_state_df = pd.read_parquet(self.risk_state_file)
                if 'date' in risk_state_df.columns:
                    risk_state_df['date'] = pd.to_datetime(risk_state_df['date'])
                    risk_state_df = risk_state_df.sort_values('date')
        except Exception as e:
            print(f"⚠️ Error loading risk state data: {e}")
        
        # Load risk budget data
        try:
            if os.path.exists(self.risk_budget_file):
                risk_budget_df = pd.read_parquet(self.risk_budget_file)
                if 'timestamp' in risk_budget_df.columns:
                    risk_budget_df['timestamp'] = pd.to_datetime(risk_budget_df['timestamp'])
                    risk_budget_df = risk_budget_df.sort_values('timestamp')
        except Exception as e:
            print(f"⚠️ Error loading risk budget data: {e}")
        
        # Load performance data
        try:
            if os.path.exists(self.performance_file):
                performance_df = pd.read_parquet(self.performance_file)
                if 'date' in performance_df.columns:
                    performance_df['date'] = pd.to_datetime(performance_df['date'])
                    performance_df = performance_df.sort_values('date')
        except Exception as e:
            print(f"⚠️ Error loading performance data: {e}")
        
        return risk_state_df, risk_budget_df, performance_df
    
    def create_exposure_timeline_chart(self, risk_state_df: pd.DataFrame) -> str:
        """
        Create exposure timeline chart with kill switch activations
        
        Args:
            risk_state_df: Risk state data
            
        Returns:
            Path to saved chart
        """
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=self.figsize, height_ratios=[3, 1])
        
        if risk_state_df is not None and not risk_state_df.empty:
            dates = risk_state_df['date']
            exposure = risk_state_df['exposure_cap'] * 100  # Convert to percentage
            emergency_active = risk_state_df['emergency_active']
            
            # Plot exposure timeline
            ax1.plot(dates, exposure, linewidth=2, label='Portfolio Exposure', color='steelblue')
            ax1.fill_between(dates, exposure, alpha=0.3, color='steelblue')
            
            # Highlight kill switch activations
            kill_switch_dates = dates[emergency_active]
            kill_switch_exposure = exposure[emergency_active]
            
            if len(kill_switch_dates) > 0:
                ax1.scatter(kill_switch_dates, kill_switch_exposure, 
                           color='red', s=100, marker='v', 
                           label='Kill Switch Activated', zorder=5)
                
                # Add vertical lines for kill switch activations
                for date in kill_switch_dates:
                    ax1.axvline(x=date, color='red', linestyle='--', alpha=0.7)
            
            # Add threshold lines
            ax1.axhline(y=100, color='green', linestyle='-', alpha=0.5, label='Normal Exposure (100%)')
            ax1.axhline(y=60, color='orange', linestyle='--', alpha=0.7, label='Volatility Cap (60%)')
            ax1.axhline(y=50, color='red', linestyle='--', alpha=0.7, label='Drawdown Brake (50%)')
            ax1.axhline(y=25, color='darkred', linestyle='--', alpha=0.7, label='Daily Loss Brake (25%)')
            
            # Risk level subplot
            risk_level = risk_state_df['risk_level'] * 100
            ax2.fill_between(dates, risk_level, alpha=0.6, color='orange', label='Risk Level')
            ax2.axhline(y=75, color='red', linestyle='--', alpha=0.7, label='High Risk (75%)')
            ax2.axhline(y=50, color='orange', linestyle='--', alpha=0.7, label='Medium Risk (50%)')
            
        else:
            # No data available
            ax1.text(0.5, 0.5, 'No risk state data available', 
                    transform=ax1.transAxes, ha='center', va='center', fontsize=14)
            ax2.text(0.5, 0.5, 'No risk level data available', 
                    transform=ax2.transAxes, ha='center', va='center', fontsize=14)
        
        # Formatting
        ax1.set_title('Portfolio Exposure Timeline with Kill Switch Activations', fontsize=16, fontweight='bold')
        ax1.set_ylabel('Exposure (%)', fontsize=12)
        ax1.legend(loc='upper right')
        ax1.grid(True, alpha=0.3)
        ax1.set_ylim(0, 110)
        
        ax2.set_title('Risk Level Over Time', fontsize=14)
        ax2.set_xlabel('Date', fontsize=12)
        ax2.set_ylabel('Risk Level (%)', fontsize=12)
        ax2.legend(loc='upper right')
        ax2.grid(True, alpha=0.3)
        ax2.set_ylim(0, 100)
        
        # Format x-axis
        for ax in [ax1, ax2]:
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
            ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=1))
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
        
        plt.tight_layout()
        
        # Save chart
        chart_path = os.path.join(self.output_dir, 'exposure_timeline.png')
        plt.savefig(chart_path, dpi=self.dpi, bbox_inches='tight')
        plt.close()
        
        return chart_path
    
    def create_drawdown_tracking_chart(self, risk_state_df: pd.DataFrame, performance_df: pd.DataFrame) -> str:
        """
        Create drawdown vs threshold tracking chart
        
        Args:
            risk_state_df: Risk state data
            performance_df: Performance data
            
        Returns:
            Path to saved chart
        """
        fig, ax = plt.subplots(figsize=self.figsize)
        
        if risk_state_df is not None and not risk_state_df.empty:
            dates = risk_state_df['date']
            drawdown = risk_state_df['drawdown'] * 100  # Convert to percentage
            
            # Plot drawdown
            ax.fill_between(dates, drawdown, 0, alpha=0.6, color='red', label='Current Drawdown')
            ax.plot(dates, drawdown, linewidth=2, color='darkred')
            
            # Add threshold line
            threshold = -self.risk_thresholds['max_drawdown'] * 100
            ax.axhline(y=threshold, color='red', linestyle='--', linewidth=2, 
                      label=f'Kill Switch Threshold ({threshold:.0f}%)')
            
            # Highlight periods when threshold was breached
            breach_mask = drawdown < threshold
            if breach_mask.any():
                breach_dates = dates[breach_mask]
                breach_drawdown = drawdown[breach_mask]
                ax.scatter(breach_dates, breach_drawdown, color='darkred', s=50, 
                          marker='v', label='Threshold Breached', zorder=5)
            
            # Add portfolio value on secondary axis
            if performance_df is not None and not performance_df.empty:
                ax2 = ax.twinx()
                
                # Calculate equity curve
                returns = performance_df['net_return'] if 'net_return' in performance_df.columns else performance_df.get('northstar_return', pd.Series([0]))
                equity_curve = (1 + returns).cumprod()
                
                ax2.plot(performance_df['date'], equity_curve, 
                        color='steelblue', alpha=0.7, linewidth=1, label='Portfolio Value')
                ax2.set_ylabel('Portfolio Value', fontsize=12, color='steelblue')
                ax2.tick_params(axis='y', labelcolor='steelblue')
                
                # Add legend for secondary axis
                lines2, labels2 = ax2.get_legend_handles_labels()
                ax.legend(loc='upper left')
                ax2.legend(lines2, labels2, loc='upper right')
            else:
                ax.legend()
        
        else:
            ax.text(0.5, 0.5, 'No drawdown data available', 
                   transform=ax.transAxes, ha='center', va='center', fontsize=14)
        
        # Formatting
        ax.set_title('Drawdown Tracking vs Kill Switch Threshold', fontsize=16, fontweight='bold')
        ax.set_xlabel('Date', fontsize=12)
        ax.set_ylabel('Drawdown (%)', fontsize=12)
        ax.grid(True, alpha=0.3)
        
        # Format x-axis
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=1))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
        
        plt.tight_layout()
        
        # Save chart
        chart_path = os.path.join(self.output_dir, 'drawdown_tracking.png')
        plt.savefig(chart_path, dpi=self.dpi, bbox_inches='tight')
        plt.close()
        
        return chart_path
    
    def create_sector_risk_heatmap(self, risk_budget_df: pd.DataFrame) -> str:
        """
        Create sector risk utilization heatmap
        
        Args:
            risk_budget_df: Risk budget data
            
        Returns:
            Path to saved chart
        """
        fig, ax = plt.subplots(figsize=(12, 8))
        
        if risk_budget_df is not None and not risk_budget_df.empty:
            # Get latest sector data
            latest_data = risk_budget_df.groupby('sector').last().reset_index()
            
            # Calculate utilization percentage
            latest_data['utilization_pct'] = (latest_data['current_risk'] / latest_data['max_risk']) * 100
            latest_data = latest_data.sort_values('utilization_pct', ascending=False)
            
            # Create horizontal bar chart
            sectors = latest_data['sector']
            utilization = latest_data['utilization_pct']
            
            # Color bars based on utilization level
            colors = []
            for util in utilization:
                if util >= 100:
                    colors.append('darkred')
                elif util >= 80:
                    colors.append('red')
                elif util >= 60:
                    colors.append('orange')
                else:
                    colors.append('green')
            
            bars = ax.barh(sectors, utilization, color=colors, alpha=0.7)
            
            # Add utilization percentage labels
            for i, (bar, util) in enumerate(zip(bars, utilization)):
                ax.text(bar.get_width() + 1, bar.get_y() + bar.get_height()/2, 
                       f'{util:.1f}%', va='center', fontweight='bold')
            
            # Add vertical lines for thresholds
            ax.axvline(x=100, color='red', linestyle='--', alpha=0.7, label='Limit (100%)')
            ax.axvline(x=80, color='orange', linestyle='--', alpha=0.5, label='Warning (80%)')
            
            # Add sector limits as text
            for i, (sector, util) in enumerate(zip(sectors, utilization)):
                limit = self.sector_limits.get(sector, 0.05) * 100
                ax.text(5, i, f'Limit: {limit:.0f}%', va='center', fontsize=9, alpha=0.7)
            
        else:
            ax.text(0.5, 0.5, 'No sector risk data available', 
                   transform=ax.transAxes, ha='center', va='center', fontsize=14)
        
        # Formatting
        ax.set_title('Sector Risk Utilization Heatmap', fontsize=16, fontweight='bold')
        ax.set_xlabel('Risk Utilization (%)', fontsize=12)
        ax.set_ylabel('Sector', fontsize=12)
        ax.legend()
        ax.grid(True, alpha=0.3, axis='x')
        ax.set_xlim(0, 120)
        
        plt.tight_layout()
        
        # Save chart
        chart_path = os.path.join(self.output_dir, 'sector_risk_heatmap.png')
        plt.savefig(chart_path, dpi=self.dpi, bbox_inches='tight')
        plt.close()
        
        return chart_path
    
    def create_kill_switch_summary_chart(self, risk_state_df: pd.DataFrame) -> str:
        """
        Create kill switch activation summary chart
        
        Args:
            risk_state_df: Risk state data
            
        Returns:
            Path to saved chart
        """
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=self.figsize)
        
        if risk_state_df is not None and not risk_state_df.empty:
            # Kill switch activation frequency
            kill_switch_counts = risk_state_df['kill_switch_triggered'].value_counts()
            
            if not kill_switch_counts.empty:
                # Remove None values
                kill_switch_counts = kill_switch_counts.dropna()
                
                if not kill_switch_counts.empty:
                    # Pie chart of kill switch types
                    colors = ['red', 'orange', 'darkred'][:len(kill_switch_counts)]
                    ax1.pie(kill_switch_counts.values, labels=kill_switch_counts.index, 
                           autopct='%1.1f%%', colors=colors, startangle=90)
                    ax1.set_title('Kill Switch Activation Frequency', fontsize=14, fontweight='bold')
                else:
                    ax1.text(0.5, 0.5, 'No kill switch activations', 
                            transform=ax1.transAxes, ha='center', va='center', fontsize=12)
                    ax1.set_title('Kill Switch Activation Frequency', fontsize=14, fontweight='bold')
            else:
                ax1.text(0.5, 0.5, 'No kill switch activations', 
                        transform=ax1.transAxes, ha='center', va='center', fontsize=12)
                ax1.set_title('Kill Switch Activation Frequency', fontsize=14, fontweight='bold')
            
            # Risk level distribution
            risk_levels = risk_state_df['risk_level'] * 100
            
            # Create risk level histogram
            ax2.hist(risk_levels, bins=20, alpha=0.7, color='steelblue', edgecolor='black')
            ax2.axvline(x=75, color='red', linestyle='--', label='High Risk (75%)')
            ax2.axvline(x=50, color='orange', linestyle='--', label='Medium Risk (50%)')
            ax2.axvline(x=risk_levels.mean(), color='green', linestyle='-', 
                       label=f'Average ({risk_levels.mean():.1f}%)')
            
        else:
            ax1.text(0.5, 0.5, 'No kill switch data available', 
                    transform=ax1.transAxes, ha='center', va='center', fontsize=12)
            ax1.set_title('Kill Switch Activation Frequency', fontsize=14, fontweight='bold')
            
            ax2.text(0.5, 0.5, 'No risk level data available', 
                    transform=ax2.transAxes, ha='center', va='center', fontsize=12)
        
        # Formatting
        ax2.set_title('Risk Level Distribution', fontsize=14, fontweight='bold')
        ax2.set_xlabel('Risk Level (%)', fontsize=12)
        ax2.set_ylabel('Frequency', fontsize=12)
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        # Save chart
        chart_path = os.path.join(self.output_dir, 'kill_switch_summary.png')
        plt.savefig(chart_path, dpi=self.dpi, bbox_inches='tight')
        plt.close()
        
        return chart_path
    
    def generate_risk_dashboard_summary(self, 
                                       risk_state_df: pd.DataFrame, 
                                       risk_budget_df: pd.DataFrame) -> Dict:
        """
        Generate risk dashboard summary statistics
        
        Args:
            risk_state_df: Risk state data
            risk_budget_df: Risk budget data
            
        Returns:
            Summary statistics dictionary
        """
        summary = {
            'timestamp': datetime.now().isoformat(),
            'data_availability': {
                'risk_state_records': len(risk_state_df) if risk_state_df is not None else 0,
                'risk_budget_records': len(risk_budget_df) if risk_budget_df is not None else 0
            }
        }
        
        if risk_state_df is not None and not risk_state_df.empty:
            latest_risk = risk_state_df.iloc[-1]
            
            summary['current_risk_state'] = {
                'date': latest_risk['date'].strftime('%Y-%m-%d'),
                'portfolio_value': float(latest_risk['portfolio_value']),
                'drawdown': float(latest_risk['drawdown']),
                'daily_return': float(latest_risk['daily_return']),
                'realized_vol': float(latest_risk['realized_vol']),
                'risk_level': float(latest_risk['risk_level']),
                'emergency_active': bool(latest_risk['emergency_active']),
                'exposure_cap': float(latest_risk['exposure_cap']),
                'kill_switch_triggered': latest_risk.get('kill_switch_triggered'),
                'kill_switch_reason': latest_risk.get('kill_switch_reason')
            }
            
            # Kill switch statistics
            kill_switch_activations = risk_state_df['emergency_active'].sum()
            total_days = len(risk_state_df)
            
            summary['kill_switch_stats'] = {
                'total_activations': int(kill_switch_activations),
                'activation_rate': float(kill_switch_activations / total_days) if total_days > 0 else 0.0,
                'days_monitored': int(total_days),
                'avg_risk_level': float(risk_state_df['risk_level'].mean()),
                'max_risk_level': float(risk_state_df['risk_level'].max()),
                'avg_exposure': float(risk_state_df['exposure_cap'].mean())
            }
        
        if risk_budget_df is not None and not risk_budget_df.empty:
            # Sector risk statistics
            latest_sectors = risk_budget_df.groupby('sector').last()
            
            summary['sector_risk_stats'] = {
                'sectors_monitored': len(latest_sectors),
                'sectors_over_limit': int((latest_sectors['current_risk'] > latest_sectors['max_risk']).sum()),
                'avg_utilization': float((latest_sectors['current_risk'] / latest_sectors['max_risk']).mean()),
                'max_utilization': float((latest_sectors['current_risk'] / latest_sectors['max_risk']).max()),
                'total_risk_budget_used': float(latest_sectors['current_risk'].sum())
            }
        
        return summary
    
    def generate_risk_dashboard(self) -> Dict:
        """
        Generate complete risk dashboard with all visualizations
        
        Returns:
            Dictionary with chart paths and summary statistics
        """
        print("📊 RISK STATE DASHBOARD - INSTITUTIONAL VALIDATION")
        print("=" * 60)
        
        # Load data
        risk_state_df, risk_budget_df, performance_df = self.load_risk_data()
        
        # Generate charts
        chart_paths = {}
        
        print("📈 Generating exposure timeline chart...")
        chart_paths['exposure_timeline'] = self.create_exposure_timeline_chart(risk_state_df)
        
        print("📉 Generating drawdown tracking chart...")
        chart_paths['drawdown_tracking'] = self.create_drawdown_tracking_chart(risk_state_df, performance_df)
        
        print("🔥 Generating sector risk heatmap...")
        chart_paths['sector_risk_heatmap'] = self.create_sector_risk_heatmap(risk_budget_df)
        
        print("🚨 Generating kill switch summary chart...")
        chart_paths['kill_switch_summary'] = self.create_kill_switch_summary_chart(risk_state_df)
        
        # Generate summary
        summary = self.generate_risk_dashboard_summary(risk_state_df, risk_budget_df)
        
        # Create dashboard result
        dashboard_result = {
            'timestamp': datetime.now().isoformat(),
            'chart_paths': chart_paths,
            'summary': summary,
            'output_directory': self.output_dir
        }
        
        # Print results
        print(f"\n📊 RISK DASHBOARD COMPLETE:")
        print(f"   Charts generated: {len(chart_paths)}")
        print(f"   Output directory: {self.output_dir}")
        
        for chart_name, chart_path in chart_paths.items():
            print(f"   📈 {chart_name}: {chart_path}")
        
        if 'current_risk_state' in summary:
            current = summary['current_risk_state']
            print(f"\n🔍 CURRENT RISK STATE:")
            print(f"   Date: {current['date']}")
            print(f"   Risk Level: {current['risk_level']:.2f}")
            print(f"   Exposure Cap: {current['exposure_cap']:.1%}")
            print(f"   Emergency Active: {current['emergency_active']}")
            
            if current['kill_switch_triggered']:
                print(f"   🚨 Kill Switch: {current['kill_switch_triggered']}")
                print(f"   Reason: {current['kill_switch_reason']}")
        
        if 'kill_switch_stats' in summary:
            stats = summary['kill_switch_stats']
            print(f"\n📊 KILL SWITCH STATISTICS:")
            print(f"   Total Activations: {stats['total_activations']}")
            print(f"   Activation Rate: {stats['activation_rate']:.1%}")
            print(f"   Days Monitored: {stats['days_monitored']}")
            print(f"   Average Risk Level: {stats['avg_risk_level']:.2f}")
        
        if 'sector_risk_stats' in summary:
            stats = summary['sector_risk_stats']
            print(f"\n🏭 SECTOR RISK STATISTICS:")
            print(f"   Sectors Monitored: {stats['sectors_monitored']}")
            print(f"   Sectors Over Limit: {stats['sectors_over_limit']}")
            print(f"   Average Utilization: {stats['avg_utilization']:.1%}")
            print(f"   Max Utilization: {stats['max_utilization']:.1%}")
        
        return dashboard_result


def main():
    """Main execution function"""
    dashboard = RiskStateDashboard()
    result = dashboard.generate_risk_dashboard()
    return result


if __name__ == "__main__":
    main()