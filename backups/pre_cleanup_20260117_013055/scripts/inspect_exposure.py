"""
Exposure Inspection Utility

Visualizes and analyzes the relationship between allowed_exposure (from Market Brain)
and actual_exposure (from Portfolio Governor) over time to detect divergence and
validate system integrity.

Requirements: 7.5
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from pathlib import Path
import argparse
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ExposureInspector:
    """
    Inspects and visualizes exposure alignment between Market Brain and Portfolio Governor
    """
    
    def __init__(self, data_dir: str = "data/state"):
        """
        Initialize exposure inspector
        
        Args:
            data_dir: Directory containing state files
        """
        self.data_dir = Path(data_dir)
        self.exposure_history_file = self.data_dir / "exposure_history.parquet"
    
    def load_exposure_history(self, days: int = 60) -> pd.DataFrame:
        """
        Load exposure history for the specified number of days
        
        Args:
            days: Number of days to load
        
        Returns:
            DataFrame with exposure history
        """
        if not self.exposure_history_file.exists():
            raise FileNotFoundError(
                f"Exposure history file not found: {self.exposure_history_file}"
            )
        
        df = pd.read_parquet(self.exposure_history_file)
        
        # Filter to last N days
        cutoff = datetime.now() - timedelta(days=days)
        df = df[df['date'] >= cutoff].copy()
        
        # Sort by date
        df = df.sort_values('date')
        
        logger.info(f"Loaded {len(df)} exposure records from last {days} days")
        
        return df
    
    def calculate_divergence(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate divergence between allowed and actual exposure
        
        Args:
            df: DataFrame with exposure history
        
        Returns:
            DataFrame with divergence metrics
        """
        df = df.copy()
        
        # Calculate absolute divergence
        df['divergence'] = df['actual_exposure'] - df['allowed_exposure']
        
        # Calculate percentage divergence
        df['divergence_pct'] = (
            df['divergence'] / df['allowed_exposure'].replace(0, 0.01) * 100
        )
        
        # Flag significant divergence (>10%)
        df['significant_divergence'] = df['divergence_pct'].abs() > 10
        
        return df
    
    def calculate_correlation(self, df: pd.DataFrame) -> float:
        """
        Calculate correlation between allowed and actual exposure
        
        Args:
            df: DataFrame with exposure history
        
        Returns:
            Correlation coefficient
        """
        if len(df) < 2:
            return 0.0
        
        correlation = df['allowed_exposure'].corr(df['actual_exposure'])
        
        return correlation
    
    def identify_divergence_periods(self, df: pd.DataFrame, threshold: float = 10.0) -> list:
        """
        Identify periods of significant divergence
        
        Args:
            df: DataFrame with exposure history
            threshold: Divergence threshold percentage
        
        Returns:
            List of divergence periods
        """
        df = df.copy()
        df['significant'] = df['divergence_pct'].abs() > threshold
        
        periods = []
        in_period = False
        period_start = None
        
        for idx, row in df.iterrows():
            if row['significant'] and not in_period:
                # Start of divergence period
                in_period = True
                period_start = row['date']
            elif not row['significant'] and in_period:
                # End of divergence period
                in_period = False
                periods.append({
                    'start': period_start,
                    'end': row['date'],
                    'duration_days': (row['date'] - period_start).days
                })
        
        # Handle case where period extends to end of data
        if in_period:
            periods.append({
                'start': period_start,
                'end': df['date'].iloc[-1],
                'duration_days': (df['date'].iloc[-1] - period_start).days
            })
        
        return periods
    
    def plot_exposure_comparison(
        self,
        df: pd.DataFrame,
        output_path: str = "reports/exposure_comparison.png"
    ) -> None:
        """
        Plot allowed vs actual exposure over time
        
        Args:
            df: DataFrame with exposure history
            output_path: Path to save plot
        """
        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(14, 10))
        
        # Plot 1: Allowed vs Actual Exposure
        ax1.plot(df['date'], df['allowed_exposure'] * 100, 
                label='Allowed Exposure (Market Brain)', 
                color='blue', linewidth=2, alpha=0.7)
        ax1.plot(df['date'], df['actual_exposure'] * 100, 
                label='Actual Exposure (Portfolio)', 
                color='red', linewidth=2, alpha=0.7)
        
        # Highlight significant divergence periods
        if 'significant_divergence' in df.columns:
            divergent = df[df['significant_divergence']]
            if len(divergent) > 0:
                ax1.scatter(divergent['date'], divergent['actual_exposure'] * 100,
                          color='orange', s=50, alpha=0.5, 
                          label='Significant Divergence (>10%)', zorder=5)
        
        ax1.set_ylabel('Exposure (%)', fontsize=12)
        ax1.set_title('Market Brain vs Portfolio Governor Exposure', fontsize=14, fontweight='bold')
        ax1.legend(loc='best')
        ax1.grid(True, alpha=0.3)
        
        # Plot 2: Divergence Over Time
        ax2.plot(df['date'], df['divergence'] * 100, 
                color='purple', linewidth=2, alpha=0.7)
        ax2.axhline(y=0, color='black', linestyle='--', linewidth=1, alpha=0.5)
        ax2.axhline(y=10, color='red', linestyle='--', linewidth=1, alpha=0.3, label='±10% threshold')
        ax2.axhline(y=-10, color='red', linestyle='--', linewidth=1, alpha=0.3)
        ax2.fill_between(df['date'], -10, 10, alpha=0.1, color='green', label='Acceptable range')
        
        ax2.set_ylabel('Divergence (%)', fontsize=12)
        ax2.set_title('Exposure Divergence (Actual - Allowed)', fontsize=14, fontweight='bold')
        ax2.legend(loc='best')
        ax2.grid(True, alpha=0.3)
        
        # Plot 3: Risk-Scaled Exposure
        if 'risk_scaled_exposure' in df.columns:
            ax3.plot(df['date'], df['allowed_exposure'] * 100, 
                    label='Allowed (Market)', color='blue', linewidth=2, alpha=0.7)
            ax3.plot(df['date'], df['risk_scaled_exposure'] * 100, 
                    label='Risk-Scaled', color='green', linewidth=2, alpha=0.7)
            ax3.plot(df['date'], df['actual_exposure'] * 100, 
                    label='Actual (min of both)', color='red', linewidth=2, alpha=0.7)
            
            ax3.set_ylabel('Exposure (%)', fontsize=12)
            ax3.set_xlabel('Date', fontsize=12)
            ax3.set_title('Exposure Decision Components', fontsize=14, fontweight='bold')
            ax3.legend(loc='best')
            ax3.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        # Save plot
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        logger.info(f"Plot saved to {output_path}")
        
        plt.close()
    
    def generate_report(self, df: pd.DataFrame, days: int = 60) -> dict:
        """
        Generate comprehensive exposure analysis report
        
        Args:
            df: DataFrame with exposure history
            days: Number of days analyzed
        
        Returns:
            Dictionary with report metrics
        """
        df_with_divergence = self.calculate_divergence(df)
        correlation = self.calculate_correlation(df)
        divergence_periods = self.identify_divergence_periods(df_with_divergence)
        
        # Calculate summary statistics
        report = {
            'period_days': days,
            'total_records': len(df),
            'date_range': {
                'start': df['date'].min().isoformat() if len(df) > 0 else None,
                'end': df['date'].max().isoformat() if len(df) > 0 else None
            },
            'correlation': round(correlation, 4),
            'divergence_stats': {
                'mean_divergence_pct': round(df_with_divergence['divergence_pct'].mean(), 2),
                'std_divergence_pct': round(df_with_divergence['divergence_pct'].std(), 2),
                'max_divergence_pct': round(df_with_divergence['divergence_pct'].max(), 2),
                'min_divergence_pct': round(df_with_divergence['divergence_pct'].min(), 2),
                'significant_divergence_count': int(df_with_divergence['significant_divergence'].sum()),
                'significant_divergence_pct': round(
                    df_with_divergence['significant_divergence'].sum() / len(df) * 100, 2
                ) if len(df) > 0 else 0
            },
            'divergence_periods': [
                {
                    'start': p['start'].isoformat(),
                    'end': p['end'].isoformat(),
                    'duration_days': p['duration_days']
                }
                for p in divergence_periods
            ],
            'exposure_stats': {
                'allowed': {
                    'mean': round(df['allowed_exposure'].mean() * 100, 2),
                    'std': round(df['allowed_exposure'].std() * 100, 2),
                    'min': round(df['allowed_exposure'].min() * 100, 2),
                    'max': round(df['allowed_exposure'].max() * 100, 2)
                },
                'actual': {
                    'mean': round(df['actual_exposure'].mean() * 100, 2),
                    'std': round(df['actual_exposure'].std() * 100, 2),
                    'min': round(df['actual_exposure'].min() * 100, 2),
                    'max': round(df['actual_exposure'].max() * 100, 2)
                }
            }
        }
        
        # Add regime analysis if available
        if 'regime' in df.columns:
            regime_divergence = df_with_divergence.groupby('regime')['divergence_pct'].agg(['mean', 'std', 'count'])
            report['regime_analysis'] = {
                regime: {
                    'mean_divergence_pct': round(row['mean'], 2),
                    'std_divergence_pct': round(row['std'], 2),
                    'count': int(row['count'])
                }
                for regime, row in regime_divergence.iterrows()
            }
        
        return report
    
    def print_report(self, report: dict) -> None:
        """
        Print formatted report to console
        
        Args:
            report: Report dictionary
        """
        print("\n" + "="*80)
        print("EXPOSURE INSPECTION REPORT")
        print("="*80)
        
        print(f"\nPeriod: {report['date_range']['start']} to {report['date_range']['end']}")
        print(f"Total Records: {report['total_records']}")
        print(f"Days Analyzed: {report['period_days']}")
        
        print(f"\n{'CORRELATION':-^80}")
        print(f"Allowed vs Actual Exposure: {report['correlation']:.4f}")
        
        if report['correlation'] > 0.9:
            print("  ✅ Excellent alignment")
        elif report['correlation'] > 0.7:
            print("  ⚠️  Good alignment, some divergence")
        else:
            print("  ❌ Poor alignment, significant divergence")
        
        print(f"\n{'DIVERGENCE STATISTICS':-^80}")
        stats = report['divergence_stats']
        print(f"Mean Divergence: {stats['mean_divergence_pct']:+.2f}%")
        print(f"Std Divergence: {stats['std_divergence_pct']:.2f}%")
        print(f"Max Divergence: {stats['max_divergence_pct']:+.2f}%")
        print(f"Min Divergence: {stats['min_divergence_pct']:+.2f}%")
        print(f"Significant Divergence (>10%): {stats['significant_divergence_count']} records ({stats['significant_divergence_pct']:.1f}%)")
        
        print(f"\n{'EXPOSURE STATISTICS':-^80}")
        print(f"Allowed Exposure: {report['exposure_stats']['allowed']['mean']:.1f}% ± {report['exposure_stats']['allowed']['std']:.1f}%")
        print(f"  Range: [{report['exposure_stats']['allowed']['min']:.1f}%, {report['exposure_stats']['allowed']['max']:.1f}%]")
        print(f"Actual Exposure: {report['exposure_stats']['actual']['mean']:.1f}% ± {report['exposure_stats']['actual']['std']:.1f}%")
        print(f"  Range: [{report['exposure_stats']['actual']['min']:.1f}%, {report['exposure_stats']['actual']['max']:.1f}%]")
        
        if report['divergence_periods']:
            print(f"\n{'DIVERGENCE PERIODS':-^80}")
            for i, period in enumerate(report['divergence_periods'], 1):
                print(f"{i}. {period['start']} to {period['end']} ({period['duration_days']} days)")
        else:
            print(f"\n{'DIVERGENCE PERIODS':-^80}")
            print("✅ No significant divergence periods detected")
        
        if 'regime_analysis' in report:
            print(f"\n{'REGIME ANALYSIS':-^80}")
            for regime, stats in report['regime_analysis'].items():
                print(f"{regime}: {stats['mean_divergence_pct']:+.2f}% ± {stats['std_divergence_pct']:.2f}% ({stats['count']} records)")
        
        print("\n" + "="*80 + "\n")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Inspect exposure alignment')
    parser.add_argument('--days', type=int, default=60, help='Number of days to analyze')
    parser.add_argument('--data-dir', type=str, default='data/state', help='Data directory')
    parser.add_argument('--output', type=str, default='reports/exposure_comparison.png', help='Output plot path')
    parser.add_argument('--no-plot', action='store_true', help='Skip plot generation')
    
    args = parser.parse_args()
    
    try:
        # Initialize inspector
        inspector = ExposureInspector(args.data_dir)
        
        # Load data
        df = inspector.load_exposure_history(args.days)
        
        if len(df) == 0:
            logger.warning("No exposure history data found")
            return
        
        # Calculate divergence
        df_with_divergence = inspector.calculate_divergence(df)
        
        # Generate plot
        if not args.no_plot:
            inspector.plot_exposure_comparison(df_with_divergence, args.output)
        
        # Generate and print report
        report = inspector.generate_report(df, args.days)
        inspector.print_report(report)
        
        # Save report to JSON
        import json
        report_path = Path(args.output).parent / 'exposure_inspection_report.json'
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        logger.info(f"Report saved to {report_path}")
        
    except Exception as e:
        logger.error(f"Error during inspection: {e}")
        raise


if __name__ == "__main__":
    main()
