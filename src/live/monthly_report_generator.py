"""
Monthly Report Generator

Generates comprehensive monthly reports for shadow trading performance.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any
import pandas as pd
import numpy as np

class MonthlyReportGenerator:
    """Monthly shadow trading report generator"""
    
    def __init__(self, data_directory: str):
        self.data_dir = Path(data_directory)
        self.logger = logging.getLogger(__name__)
    
    def generate_monthly_report(self, year: Optional[int] = None, month: Optional[int] = None) -> Dict[str, Any]:
        """Generate monthly performance report"""
        if year is None or month is None:
            now = datetime.now(timezone.utc)
            year = now.year
            month = now.month
        
        self.logger.info(f"Generating monthly report for {year}-{month:02d}")
        
        # Load monthly data
        monthly_data = self._load_monthly_data(year, month)
        
        if not monthly_data:
            return {'error': f'No data available for {year}-{month:02d}'}
        
        # Calculate performance metrics
        performance_metrics = self._calculate_monthly_performance(monthly_data)
        
        # Generate report
        report = {
            'period': f"{year}-{month:02d}",
            'generation_timestamp': datetime.now(timezone.utc).isoformat(),
            'performance_metrics': performance_metrics,
            'trading_days': len(monthly_data),
            'data_quality': 'good' if len(monthly_data) >= 15 else 'limited'
        }
        
        # Save report
        self._save_monthly_report(report, year, month)
        
        return report
    
    def _load_monthly_data(self, year: int, month: int) -> List[Dict[str, Any]]:
        """Load all data for a specific month"""
        monthly_data = []
        
        pnl_dir = self.data_dir / "pnl"
        if not pnl_dir.exists():
            return []
        
        # Load all P&L files for the month
        for pnl_file in pnl_dir.glob(f"pnl_{year}-{month:02d}-*.json"):
            try:
                with open(pnl_file, 'r') as f:
                    daily_data = json.load(f)
                    monthly_data.append(daily_data)
            except Exception as e:
                self.logger.warning(f"Failed to load {pnl_file}: {e}")
        
        return sorted(monthly_data, key=lambda x: x['date'])
    
    def _calculate_monthly_performance(self, monthly_data: List[Dict[str, Any]]) -> Dict[str, float]:
        """Calculate monthly performance metrics"""
        if not monthly_data:
            return {}
        
        # Extract daily returns
        daily_returns = [day['daily_return'] for day in monthly_data if 'daily_return' in day]
        
        if not daily_returns:
            return {}
        
        # Calculate metrics
        total_return = sum(daily_returns)
        avg_return = np.mean(daily_returns)
        volatility = np.std(daily_returns)
        
        # Sharpe ratio
        risk_free_daily = 0.06 / 252
        excess_returns = [r - risk_free_daily for r in daily_returns]
        sharpe_ratio = np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(252) if np.std(excess_returns) > 0 else 0
        
        # Win rate
        positive_days = sum(1 for r in daily_returns if r > 0)
        win_rate = positive_days / len(daily_returns)
        
        # Max drawdown
        cumulative_returns = np.cumsum(daily_returns)
        running_max = np.maximum.accumulate(cumulative_returns)
        drawdowns = cumulative_returns - running_max
        max_drawdown = np.min(drawdowns)
        
        return {
            'total_return': total_return,
            'average_daily_return': avg_return,
            'volatility': volatility,
            'sharpe_ratio': sharpe_ratio,
            'win_rate': win_rate,
            'max_drawdown': max_drawdown,
            'trading_days': len(daily_returns)
        }
    
    def _save_monthly_report(self, report: Dict[str, Any], year: int, month: int) -> None:
        """Save monthly report to file"""
        reports_dir = self.data_dir / "reports"
        reports_dir.mkdir(exist_ok=True)
        
        report_file = reports_dir / f"monthly_report_{year}{month:02d}.json"
        
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        self.logger.info(f"Monthly report saved: {report_file}")