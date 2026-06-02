"""
PaperFundManager — Manages Northstar V3's 6-month paper trading validation fund

The paper fund is a forward test where every trade was generated in real time
by the live system, using real market prices, but paper-executed.
This is the highest-quality evidence for institutional readiness.
"""

from datetime import datetime, timedelta
from typing import Dict, List
from pathlib import Path
import pandas as pd
import json
import logging

from .ledger import UnifiedPnLLedger, LedgerBook
from .nav_calculator import NAVCalculator
from .attribution import PnLAttributor

logger = logging.getLogger(__name__)


class PaperFundManager:
    """Manages the 6-month paper trading validation fund"""
    
    def __init__(
        self,
        ledger: UnifiedPnLLedger,
        nav_calculator: NAVCalculator,
        attributor: PnLAttributor,
        config: dict
    ):
        self.ledger = ledger
        self.nav_calculator = nav_calculator
        self.attributor = attributor
        self.config = config
        
        # Get paper fund config
        fund_config = config.get('pnl', {}).get('paper_fund', {})
        self.inception_date = pd.to_datetime(fund_config.get('inception_date', '2024-09-01'))
        self.starting_capital = fund_config.get('starting_capital_inr', 10_000_000)
        self.fund_name = fund_config.get('fund_name', 'Northstar V3 Paper Fund')
        self.benchmark = fund_config.get('benchmark', 'NIFTY500_TR')
        self.target_monthly_return_pct = fund_config.get('target_monthly_return_pct', 2.0)
        self.max_acceptable_drawdown_pct = fund_config.get('max_acceptable_drawdown_pct', -15.0)
        self.min_sharpe_ratio = fund_config.get('min_sharpe_ratio', 1.2)

    def compute_current_fund_status(self) -> Dict:
        """
        Dashboard-facing method. Returns real-time snapshot of paper fund status.
        """
        logger.info("Computing current paper fund status")
        
        current_date = datetime.now()
        days_running = (current_date - self.inception_date).days
        
        # Compute NAV
        nav_df = self.nav_calculator.compute_daily_nav(self.inception_date, current_date)
        
        if len(nav_df) == 0:
            logger.warning("No NAV data available")
            return {}
        
        current_nav = nav_df['nav_combined'].iloc[-1]
        nav_per_unit = nav_df['nav_per_unit'].iloc[-1]
        
        # Returns
        total_return_pct = (current_nav / self.starting_capital - 1) * 100
        
        # Annualized return
        years = days_running / 365
        annualized_return_pct = ((1 + total_return_pct/100) ** (1/years) - 1) * 100 if years > 0 else 0
        
        # Drawdown
        current_drawdown_pct = nav_df['drawdown'].iloc[-1] * 100
        max_drawdown_pct = nav_df['max_drawdown_to_date'].iloc[-1] * 100
        
        # Performance metrics
        perf_metrics = self.nav_calculator.compute_performance_metrics(self.inception_date, current_date)
        sharpe_ratio = perf_metrics.get('sharpe_ratio', 0)
        
        # Benchmark comparison (would need benchmark data)
        benchmark_return_pct = 0.0  # TODO: load benchmark data
        excess_return_pct = total_return_pct - benchmark_return_pct
        information_ratio = 0.0  # TODO: compute from benchmark
        
        # Health checks
        target_met = annualized_return_pct >= self.target_monthly_return_pct * 12
        drawdown_breach = max_drawdown_pct < self.max_acceptable_drawdown_pct
        sharpe_breach = sharpe_ratio < self.min_sharpe_ratio
        
        if drawdown_breach or sharpe_breach:
            fund_health = "BREACH"
        elif not target_met:
            fund_health = "WARNING"
        else:
            fund_health = "ON_TRACK"
        
        status = {
            'fund_name': self.fund_name,
            'inception_date': self.inception_date.date(),
            'current_date': current_date.date(),
            'days_running': days_running,
            'starting_nav': self.starting_capital,
            'current_nav': current_nav,
            'nav_per_unit': nav_per_unit,
            'total_return_pct': total_return_pct,
            'annualized_return_pct': annualized_return_pct,
            'current_drawdown_pct': current_drawdown_pct,
            'max_drawdown_pct': max_drawdown_pct,
            'sharpe_ratio_since_inception': sharpe_ratio,
            'benchmark_return_pct': benchmark_return_pct,
            'excess_return_pct': excess_return_pct,
            'information_ratio': information_ratio,
            'target_met': target_met,
            'drawdown_breach': drawdown_breach,
            'sharpe_breach': sharpe_breach,
            'fund_health': fund_health,
        }
        
        logger.info(f"Fund health: {fund_health}, Return: {annualized_return_pct:.2f}%, Sharpe: {sharpe_ratio:.2f}")
        
        return status

    def generate_monthly_report(self, year: int, month: int) -> Dict:
        """
        Generates institutional monthly performance report for the paper fund.
        """
        logger.info(f"Generating monthly report for {year}-{month:02d}")
        
        # Date range for the month
        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = datetime(year, month + 1, 1) - timedelta(days=1)
        
        # NAV metrics
        nav_df = self.nav_calculator.compute_daily_nav(start_date, end_date)
        perf_metrics = self.nav_calculator.compute_performance_metrics(start_date, end_date)
        
        # Attribution
        attribution = self.attributor.generate_attribution_report(start_date, end_date)
        
        # Fund status
        fund_status = self.compute_current_fund_status()
        
        report = {
            'report_type': 'monthly',
            'fund_name': self.fund_name,
            'period': f"{year}-{month:02d}",
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'performance_metrics': perf_metrics,
            'attribution': attribution,
            'fund_status': fund_status,
            'generated_at': datetime.now().isoformat(),
        }
        
        # Write to file
        output_dir = Path("data/pnl/monthly_reports")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{year}_{month:02d}_paper_fund_report.json"
        
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        logger.info(f"Wrote monthly report to {output_path}")
        
        return report
    
    def generate_six_month_certificate(self) -> Dict:
        """
        Generates the final 6-month institutional performance certificate.
        This is the document presented for institutional validation.
        """
        logger.info("Generating 6-month performance certificate")
        
        six_month_date = self.inception_date + timedelta(days=180)
        
        # Full NAV history
        nav_df = self.nav_calculator.compute_daily_nav(self.inception_date, six_month_date)
        
        # Performance metrics
        perf_metrics = self.nav_calculator.compute_performance_metrics(self.inception_date, six_month_date)
        
        # Strategy attribution
        strategy_attr = self.attributor.compute_strategy_attribution(self.inception_date, six_month_date)
        
        # Regime attribution
        regime_attr = self.attributor.compute_regime_attribution(self.inception_date, six_month_date)
        
        # Benchmark comparison (would need benchmark data)
        benchmark_comparison = {}  # TODO: load and compare benchmark
        
        # Worst drawdown periods
        drawdown_periods = self._analyze_drawdown_periods(nav_df)
        
        # Execution quality summary
        # TODO: load from execution_quality.parquet
        
        certificate = {
            'certificate_type': 'six_month_validation',
            'fund_name': self.fund_name,
            'inception_date': self.inception_date.isoformat(),
            'end_date': six_month_date.isoformat(),
            'starting_capital_inr': self.starting_capital,
            'ending_nav_inr': nav_df['nav_combined'].iloc[-1] if len(nav_df) > 0 else 0,
            'performance_metrics': perf_metrics,
            'strategy_attribution': strategy_attr.to_dict('index') if len(strategy_attr) > 0 else {},
            'regime_attribution': regime_attr.to_dict('index') if len(regime_attr) > 0 else {},
            'benchmark_comparison': benchmark_comparison,
            'drawdown_analysis': drawdown_periods,
            'nav_history_chart_data': nav_df[['nav_combined', 'nav_per_unit', 'drawdown']].to_dict('records') if len(nav_df) > 0 else [],
            'generated_at': datetime.now().isoformat(),
        }
        
        # Write to file
        output_path = Path("data/pnl/paper_fund_6month_certificate.json")
        with open(output_path, 'w') as f:
            json.dump(certificate, f, indent=2, default=str)
        
        logger.info(f"Wrote 6-month certificate to {output_path}")
        
        return certificate
    
    def check_fund_health_alerts(self) -> List[str]:
        """
        Returns list of alert strings if fund is breaching performance targets.
        Called daily by EOD process.
        """
        status = self.compute_current_fund_status()
        
        alerts = []
        
        if status.get('drawdown_breach'):
            alerts.append(f"CRITICAL: Drawdown {status['max_drawdown_pct']:.2f}% exceeds limit {self.max_acceptable_drawdown_pct}%")
        
        if status.get('sharpe_breach'):
            alerts.append(f"WARNING: Sharpe ratio {status['sharpe_ratio_since_inception']:.2f} below target {self.min_sharpe_ratio}")
        
        if not status.get('target_met'):
            alerts.append(f"INFO: Annualized return {status['annualized_return_pct']:.2f}% below target {self.target_monthly_return_pct * 12}%")
        
        return alerts
    
    def _analyze_drawdown_periods(self, nav_df: pd.DataFrame) -> List[Dict]:
        """Analyze worst drawdown periods and recovery"""
        if len(nav_df) == 0:
            return []
        
        # Find drawdown periods
        in_drawdown = nav_df['drawdown'] < 0
        
        if not in_drawdown.any():
            return []
        
        # Label each drawdown period
        drawdown_periods = (in_drawdown != in_drawdown.shift()).cumsum()
        
        periods = []
        for period_id in drawdown_periods[in_drawdown].unique():
            period_data = nav_df[drawdown_periods == period_id]
            
            if len(period_data) == 0:
                continue
            
            start_date = period_data.index[0]
            end_date = period_data.index[-1]
            duration_days = len(period_data)
            max_dd = period_data['drawdown'].min()
            
            # Check if recovered
            after_period = nav_df[nav_df.index > end_date]
            recovered = (after_period['drawdown'] >= 0).any() if len(after_period) > 0 else False
            
            if recovered:
                recovery_date = after_period[after_period['drawdown'] >= 0].index[0]
                recovery_days = (recovery_date - end_date).days
            else:
                recovery_date = None
                recovery_days = None
            
            periods.append({
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'duration_days': duration_days,
                'max_drawdown_pct': max_dd * 100,
                'recovered': recovered,
                'recovery_date': recovery_date.isoformat() if recovery_date else None,
                'recovery_days': recovery_days,
            })
        
        # Sort by max drawdown (worst first)
        periods.sort(key=lambda x: x['max_drawdown_pct'])
        
        return periods[:5]  # Return top 5 worst drawdowns
