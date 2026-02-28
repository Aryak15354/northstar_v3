"""
Backtest Reporting Module

Generates comprehensive reports for backtest results including:
- Win rate, net P&L, max drawdown
- Greek violations tracking
- Kill switch activations
- Trade-by-trade analysis
- Performance charts

Requirements: US-12.4
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from pathlib import Path
import json
import logging
from datetime import datetime

from src.options.backtest_simulation_engine import BacktestResults, BacktestTrade

logger = logging.getLogger(__name__)


class BacktestReporter:
    """
    Generates comprehensive backtest reports.
    
    Produces:
    - Summary statistics
    - Trade-by-trade breakdown
    - Performance metrics
    - Risk metrics
    - Charts and visualizations
    """
    
    def __init__(self, output_dir: str = "data/options/backtest_reports"):
        """
        Initialize the backtest reporter.
        
        Args:
            output_dir: Directory to save reports
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_report(
        self,
        results: BacktestResults,
        report_name: Optional[str] = None
    ) -> Dict:
        """
        Generate a comprehensive backtest report.
        
        Args:
            results: BacktestResults from simulation
            report_name: Optional name for the report
            
        Returns:
            Dictionary with all report sections
        """
        if report_name is None:
            report_name = f"backtest_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        logger.info(f"Generating backtest report: {report_name}")
        
        # Generate report sections
        report = {
            'metadata': self._generate_metadata(results, report_name),
            'summary': self._generate_summary(results),
            'performance_metrics': self._generate_performance_metrics(results),
            'risk_metrics': self._generate_risk_metrics(results),
            'trade_analysis': self._generate_trade_analysis(results),
            'regime_analysis': self._generate_regime_analysis(results),
            'greek_violations': self._generate_greek_violations(results),
            'kill_switches': self._generate_kill_switch_analysis(results),
            'equity_curve': self._generate_equity_curve_data(results)
        }
        
        # Save report
        self._save_report(report, report_name)
        
        # Generate visualizations
        self._generate_visualizations(results, report_name)
        
        logger.info(f"Report saved to {self.output_dir / report_name}")
        
        return report
    
    def _generate_metadata(
        self,
        results: BacktestResults,
        report_name: str
    ) -> Dict:
        """Generate report metadata."""
        return {
            'report_name': report_name,
            'generated_at': datetime.now().isoformat(),
            'backtest_period': {
                'start_date': results.config.start_date.isoformat(),
                'end_date': results.config.end_date.isoformat(),
                'duration_days': (
                    results.config.end_date - results.config.start_date
                ).days
            },
            'configuration': {
                'initial_capital': results.config.initial_capital,
                'slippage_pct': results.config.slippage_pct,
                'max_trades_per_week': results.config.max_trades_per_week,
                'symbols': results.config.symbols
            }
        }
    
    def _generate_summary(self, results: BacktestResults) -> Dict:
        """Generate summary statistics."""
        return {
            'total_trades': results.total_trades,
            'winning_trades': results.winning_trades,
            'losing_trades': results.losing_trades,
            'win_rate_pct': round(results.win_rate, 2),
            'total_net_pnl': round(results.total_net_pnl, 2),
            'total_return_pct': round(results.total_return_pct, 2),
            'avg_trade_return_pct': round(results.avg_trade_return_pct, 2),
            'max_drawdown_pct': round(results.max_drawdown_pct, 2),
            'sharpe_ratio': round(results.sharpe_ratio, 2)
        }
    
    def _generate_performance_metrics(self, results: BacktestResults) -> Dict:
        """Generate detailed performance metrics."""
        if not results.trades:
            return {}
        
        winning_trades = [t for t in results.trades if t.net_pnl > 0]
        losing_trades = [t for t in results.trades if t.net_pnl < 0]
        
        avg_win = (
            np.mean([t.net_pnl for t in winning_trades])
            if winning_trades else 0
        )
        avg_loss = (
            np.mean([t.net_pnl for t in losing_trades])
            if losing_trades else 0
        )
        
        profit_factor = (
            abs(sum(t.net_pnl for t in winning_trades) /
                sum(t.net_pnl for t in losing_trades))
            if losing_trades and sum(t.net_pnl for t in losing_trades) != 0
            else 0
        )
        
        return {
            'avg_win': round(avg_win, 2),
            'avg_loss': round(avg_loss, 2),
            'profit_factor': round(profit_factor, 2),
            'largest_win': round(max(t.net_pnl for t in results.trades), 2),
            'largest_loss': round(min(t.net_pnl for t in results.trades), 2),
            'avg_days_held': round(
                np.mean([t.days_held for t in results.trades]), 1
            ),
            'total_costs': round(results.total_costs, 2),
            'total_tax': round(results.total_tax, 2),
            'cost_ratio_pct': round(
                (results.total_costs / abs(results.total_gross_pnl)) * 100
                if results.total_gross_pnl != 0 else 0,
                2
            )
        }
    
    def _generate_risk_metrics(self, results: BacktestResults) -> Dict:
        """Generate risk metrics."""
        if not results.trades:
            return {}
        
        # Calculate consecutive losses
        max_consecutive_losses = 0
        current_consecutive = 0
        
        for trade in results.trades:
            if trade.net_pnl < 0:
                current_consecutive += 1
                max_consecutive_losses = max(
                    max_consecutive_losses,
                    current_consecutive
                )
            else:
                current_consecutive = 0
        
        # Calculate recovery factor
        recovery_factor = (
            abs(results.total_net_pnl / results.max_drawdown_pct)
            if results.max_drawdown_pct != 0 else 0
        )
        
        return {
            'max_drawdown_pct': round(results.max_drawdown_pct, 2),
            'max_consecutive_losses': max_consecutive_losses,
            'recovery_factor': round(recovery_factor, 2),
            'kill_switch_activations': results.kill_switch_activations,
            'trauma_rule_activations': results.trauma_rule_activations,
            'total_greek_violations': results.total_greek_violations,
            'avg_max_loss_realized_pct': round(
                np.mean([t.max_loss_realized_pct for t in results.trades]), 2
            )
        }
    
    def _generate_trade_analysis(self, results: BacktestResults) -> Dict:
        """Generate trade-by-trade analysis."""
        if not results.trades:
            return {'trades': []}
        
        trades_data = []
        
        for trade in results.trades:
            trades_data.append({
                'entry_date': trade.entry_date.isoformat(),
                'exit_date': trade.exit_date.isoformat(),
                'symbol': trade.symbol,
                'strategy_type': trade.strategy_type,
                'regime': trade.regime,
                'days_held': trade.days_held,
                'entry_max_loss': round(trade.entry_max_loss, 2),
                'gross_pnl': round(trade.gross_pnl, 2),
                'costs': round(trade.costs, 2),
                'tax': round(trade.tax, 2),
                'net_pnl': round(trade.net_pnl, 2),
                'return_pct': round(trade.return_pct, 2),
                'exit_reason': trade.exit_reason,
                'max_loss_realized_pct': round(trade.max_loss_realized_pct, 2),
                'greek_violations': trade.greek_violations
            })
        
        return {
            'trades': trades_data,
            'total_trades': len(trades_data)
        }
    
    def _generate_regime_analysis(self, results: BacktestResults) -> Dict:
        """Analyze performance by regime."""
        if not results.trades:
            return {}
        
        regime_stats = {}
        
        for trade in results.trades:
            regime = trade.regime
            
            if regime not in regime_stats:
                regime_stats[regime] = {
                    'count': 0,
                    'wins': 0,
                    'losses': 0,
                    'total_pnl': 0.0,
                    'avg_return_pct': []
                }
            
            regime_stats[regime]['count'] += 1
            regime_stats[regime]['total_pnl'] += trade.net_pnl
            regime_stats[regime]['avg_return_pct'].append(trade.return_pct)
            
            if trade.net_pnl > 0:
                regime_stats[regime]['wins'] += 1
            else:
                regime_stats[regime]['losses'] += 1
        
        # Calculate averages
        for regime, stats in regime_stats.items():
            stats['win_rate_pct'] = round(
                (stats['wins'] / stats['count']) * 100, 2
            )
            stats['avg_return_pct'] = round(
                np.mean(stats['avg_return_pct']), 2
            )
            stats['total_pnl'] = round(stats['total_pnl'], 2)
        
        return regime_stats
    
    def _generate_greek_violations(self, results: BacktestResults) -> Dict:
        """Generate Greek violations summary."""
        return {
            'total_violations': results.total_greek_violations,
            'violations_per_trade': round(
                results.total_greek_violations / results.total_trades
                if results.total_trades > 0 else 0,
                2
            ),
            'note': 'Greek violations tracking is simplified in current implementation'
        }
    
    def _generate_kill_switch_analysis(self, results: BacktestResults) -> Dict:
        """Generate kill switch analysis."""
        return {
            'weekly_loss_activations': results.kill_switch_activations,
            'trauma_rule_activations': results.trauma_rule_activations,
            'total_activations': (
                results.kill_switch_activations +
                results.trauma_rule_activations
            ),
            'activation_rate_pct': round(
                ((results.kill_switch_activations +
                  results.trauma_rule_activations) /
                 results.total_trades) * 100
                if results.total_trades > 0 else 0,
                2
            )
        }
    
    def _generate_equity_curve_data(self, results: BacktestResults) -> Dict:
        """Generate equity curve data for visualization."""
        if results.equity_curve.empty:
            return {'data': []}
        
        equity_data = []
        
        for _, row in results.equity_curve.iterrows():
            equity_data.append({
                'date': row['date'].isoformat(),
                'equity': round(row['equity'], 2),
                'net_pnl': round(row['net_pnl'], 2)
            })
        
        return {
            'data': equity_data,
            'initial_equity': results.config.initial_capital,
            'final_equity': round(results.equity_curve['equity'].iloc[-1], 2)
            if not results.equity_curve.empty else results.config.initial_capital
        }
    
    def _save_report(self, report: Dict, report_name: str) -> None:
        """Save report to JSON file."""
        report_path = self.output_dir / f"{report_name}.json"
        
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"Report saved to {report_path}")
    
    def _generate_visualizations(
        self,
        results: BacktestResults,
        report_name: str
    ) -> None:
        """Generate visualization charts (placeholder for future implementation)."""
        # This would generate charts using matplotlib or plotly
        # For now, we just log that visualizations would be generated
        logger.info(
            f"Visualization generation placeholder for {report_name}. "
            "Charts would include: equity curve, drawdown chart, "
            "returns distribution, regime performance."
        )
    
    def print_summary(self, results: BacktestResults) -> None:
        """Print a formatted summary to console."""
        print("\n" + "=" * 70)
        print("BACKTEST RESULTS SUMMARY")
        print("=" * 70)
        
        print(f"\nPeriod: {results.config.start_date} to {results.config.end_date}")
        print(f"Initial Capital: ₹{results.config.initial_capital:,.0f}")
        
        print(f"\n{'PERFORMANCE METRICS':-^70}")
        print(f"Total Trades: {results.total_trades}")
        print(f"Win Rate: {results.win_rate:.1f}%")
        print(f"Total Net P&L: ₹{results.total_net_pnl:,.0f}")
        print(f"Total Return: {results.total_return_pct:.2f}%")
        print(f"Avg Trade Return: {results.avg_trade_return_pct:.2f}%")
        
        print(f"\n{'RISK METRICS':-^70}")
        print(f"Max Drawdown: {results.max_drawdown_pct:.2f}%")
        print(f"Sharpe Ratio: {results.sharpe_ratio:.2f}")
        print(f"Kill Switch Activations: {results.kill_switch_activations}")
        print(f"Trauma Rule Activations: {results.trauma_rule_activations}")
        print(f"Greek Violations: {results.total_greek_violations}")
        
        print(f"\n{'COST ANALYSIS':-^70}")
        print(f"Total Costs: ₹{results.total_costs:,.0f}")
        print(f"Total Tax: ₹{results.total_tax:,.0f}")
        print(f"Gross P&L: ₹{results.total_gross_pnl:,.0f}")
        
        if results.trades:
            print(f"\n{'TOP 5 TRADES':-^70}")
            top_trades = sorted(results.trades, key=lambda t: t.net_pnl, reverse=True)[:5]
            
            for i, trade in enumerate(top_trades, 1):
                print(
                    f"{i}. {trade.entry_date} | {trade.strategy_type} | "
                    f"₹{trade.net_pnl:,.0f} ({trade.return_pct:.1f}%)"
                )
            
            print(f"\n{'WORST 5 TRADES':-^70}")
            worst_trades = sorted(results.trades, key=lambda t: t.net_pnl)[:5]
            
            for i, trade in enumerate(worst_trades, 1):
                print(
                    f"{i}. {trade.entry_date} | {trade.strategy_type} | "
                    f"₹{trade.net_pnl:,.0f} ({trade.return_pct:.1f}%)"
                )
        
        print("\n" + "=" * 70)


# Standalone test
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("=" * 60)
    print("Backtest Reporting - Standalone Test")
    print("=" * 60)
    
    # Create mock results for testing
    from src.options.backtest_simulation_engine import (
        BacktestConfig,
        BacktestResults,
        BacktestTrade
    )
    from datetime import date
    
    config = BacktestConfig(
        start_date=date(2024, 1, 1),
        end_date=date(2024, 3, 1),
        initial_capital=500_000.0
    )
    
    # Create mock trades
    mock_trades = [
        BacktestTrade(
            entry_date=date(2024, 1, 5),
            exit_date=date(2024, 1, 12),
            symbol='NIFTY',
            strategy_type='IRON_CONDOR',
            regime='LOW_VOL_SELL',
            entry_credit_debit=15000,
            entry_max_loss=50000,
            exit_value=8000,
            exit_reason='profit_target',
            gross_pnl=7000,
            costs=500,
            tax=2100,
            net_pnl=4400,
            days_held=7,
            return_pct=8.8,
            max_loss_realized_pct=-14.0,
            greek_violations=0
        ),
        BacktestTrade(
            entry_date=date(2024, 1, 20),
            exit_date=date(2024, 1, 27),
            symbol='BANKNIFTY',
            strategy_type='CALENDAR_SPREAD',
            regime='NEUTRAL',
            entry_credit_debit=-20000,
            entry_max_loss=20000,
            exit_value=-15000,
            exit_reason='profit_target',
            gross_pnl=5000,
            costs=600,
            tax=1500,
            net_pnl=2900,
            days_held=7,
            return_pct=14.5,
            max_loss_realized_pct=25.0,
            greek_violations=0
        )
    ]
    
    # Create mock equity curve
    equity_curve = pd.DataFrame([
        {'date': date(2024, 1, 12), 'equity': 504400, 'net_pnl': 4400},
        {'date': date(2024, 1, 27), 'equity': 507300, 'net_pnl': 2900}
    ])
    
    results = BacktestResults(
        config=config,
        trades=mock_trades,
        total_trades=2,
        winning_trades=2,
        losing_trades=0,
        win_rate=100.0,
        total_gross_pnl=12000,
        total_costs=1100,
        total_tax=3600,
        total_net_pnl=7300,
        total_return_pct=1.46,
        avg_trade_return_pct=11.65,
        max_drawdown_pct=0.0,
        sharpe_ratio=2.5,
        kill_switch_activations=0,
        trauma_rule_activations=0,
        total_greek_violations=0,
        equity_curve=equity_curve
    )
    
    # Generate report
    reporter = BacktestReporter()
    report = reporter.generate_report(results, report_name="test_backtest")
    
    # Print summary
    reporter.print_summary(results)
    
    print("\n" + "=" * 60)
    print("Test complete")
    print("=" * 60)
