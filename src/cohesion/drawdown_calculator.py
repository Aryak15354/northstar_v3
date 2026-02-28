"""
Drawdown Calculator

Calculates portfolio and benchmark drawdown metrics:
- Maximum drawdown: largest peak-to-trough decline
- Current drawdown: current decline from peak
- Drawdown formula: (equity[t] - max(equity[0:t])) / max(equity[0:t])

Stores results in portfolio_analytics.json for tracking and comparison.
"""

import logging
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
import pandas as pd
import numpy as np

from src.cohesion.state_file_manager import StateFileManager

logger = logging.getLogger(__name__)


class DrawdownCalculator:
    """
    Calculates drawdown metrics for portfolio and benchmark.
    
    Drawdown is the percentage decline from peak equity. This calculator
    computes both maximum drawdown (worst decline ever) and current drawdown
    (current decline from peak).
    
    Formula: drawdown[t] = (equity[t] - peak_equity[0:t]) / peak_equity[0:t]
    """
    
    def __init__(self, state_manager: Optional[StateFileManager] = None):
        """
        Initialize the drawdown calculator.
        
        Args:
            state_manager: StateFileManager instance (creates new if None)
        """
        self.state_manager = state_manager or StateFileManager()
        logger.info("DrawdownCalculator initialized")
    
    def calculate_drawdown_series(self, equity_curve: pd.Series) -> pd.Series:
        """
        Calculate drawdown series from equity curve.
        
        Args:
            equity_curve: Series of equity values indexed by date
            
        Returns:
            Series of drawdown values (negative percentages)
        """
        if len(equity_curve) == 0:
            return pd.Series(dtype=float)
        
        # Calculate running maximum (peak equity up to each point)
        running_max = equity_curve.expanding().max()
        
        # Calculate drawdown as percentage decline from peak
        drawdown = (equity_curve - running_max) / running_max
        
        return drawdown
    
    def calculate_max_drawdown(self, equity_curve: pd.Series) -> float:
        """
        Calculate maximum drawdown from equity curve.
        
        Args:
            equity_curve: Series of equity values
            
        Returns:
            Maximum drawdown as negative percentage (e.g., -0.15 for 15% drawdown)
        """
        if len(equity_curve) == 0:
            return 0.0
        
        drawdown_series = self.calculate_drawdown_series(equity_curve)
        max_dd = drawdown_series.min()  # Most negative value
        
        return max_dd if not np.isnan(max_dd) else 0.0
    
    def calculate_current_drawdown(self, equity_curve: pd.Series) -> float:
        """
        Calculate current drawdown from equity curve.
        
        Args:
            equity_curve: Series of equity values
            
        Returns:
            Current drawdown as negative percentage
        """
        if len(equity_curve) == 0:
            return 0.0
        
        drawdown_series = self.calculate_drawdown_series(equity_curve)
        current_dd = drawdown_series.iloc[-1]
        
        return current_dd if not np.isnan(current_dd) else 0.0
    
    def find_drawdown_periods(
        self,
        equity_curve: pd.Series
    ) -> list[Dict[str, Any]]:
        """
        Find all drawdown periods (peak to trough to recovery).
        
        Args:
            equity_curve: Series of equity values indexed by date
            
        Returns:
            List of drawdown period dictionaries with:
            - peak_date: Date of peak
            - trough_date: Date of trough
            - recovery_date: Date of recovery (or None if not recovered)
            - peak_value: Equity at peak
            - trough_value: Equity at trough
            - drawdown: Maximum drawdown percentage
            - duration_days: Days from peak to trough
            - recovery_days: Days from trough to recovery (or None)
        """
        if len(equity_curve) == 0:
            return []
        
        drawdown_series = self.calculate_drawdown_series(equity_curve)
        periods = []
        
        in_drawdown = False
        peak_idx = None
        trough_idx = None
        
        for i in range(len(drawdown_series)):
            if drawdown_series.iloc[i] == 0.0:
                # At a new peak
                if in_drawdown and trough_idx is not None:
                    # Drawdown has recovered
                    periods.append({
                        'peak_date': equity_curve.index[peak_idx],
                        'trough_date': equity_curve.index[trough_idx],
                        'recovery_date': equity_curve.index[i],
                        'peak_value': equity_curve.iloc[peak_idx],
                        'trough_value': equity_curve.iloc[trough_idx],
                        'drawdown': drawdown_series.iloc[trough_idx],
                        'duration_days': (equity_curve.index[trough_idx] - equity_curve.index[peak_idx]).days,
                        'recovery_days': (equity_curve.index[i] - equity_curve.index[trough_idx]).days
                    })
                in_drawdown = False
                peak_idx = i
                trough_idx = None
            else:
                # In drawdown
                if not in_drawdown:
                    # Starting new drawdown
                    in_drawdown = True
                    peak_idx = i - 1 if i > 0 else 0
                    trough_idx = i
                else:
                    # Update trough if this is deeper
                    if drawdown_series.iloc[i] < drawdown_series.iloc[trough_idx]:
                        trough_idx = i
        
        # Handle ongoing drawdown
        if in_drawdown and trough_idx is not None:
            periods.append({
                'peak_date': equity_curve.index[peak_idx],
                'trough_date': equity_curve.index[trough_idx],
                'recovery_date': None,
                'peak_value': equity_curve.iloc[peak_idx],
                'trough_value': equity_curve.iloc[trough_idx],
                'drawdown': drawdown_series.iloc[trough_idx],
                'duration_days': (equity_curve.index[trough_idx] - equity_curve.index[peak_idx]).days,
                'recovery_days': None
            })
        
        return periods
    
    def calculate_portfolio_metrics(
        self,
        portfolio_equity: pd.Series
    ) -> Dict[str, Any]:
        """
        Calculate comprehensive portfolio metrics.
        
        Args:
            portfolio_equity: Series of portfolio equity values
            
        Returns:
            Dictionary with portfolio metrics
        """
        if len(portfolio_equity) == 0:
            return {
                'total_return': 0.0,
                'sharpe_ratio': 0.0,
                'max_drawdown': 0.0,
                'current_drawdown': 0.0,
                'volatility': 0.0
            }
        
        # Calculate returns
        returns = portfolio_equity.pct_change().dropna()
        
        # Total return
        total_return = (portfolio_equity.iloc[-1] / portfolio_equity.iloc[0]) - 1.0
        
        # Volatility (annualized)
        volatility = returns.std() * np.sqrt(252) if len(returns) > 1 else 0.0
        
        # Sharpe ratio (assuming 0% risk-free rate)
        mean_return = returns.mean() * 252  # Annualized
        sharpe_ratio = mean_return / volatility if volatility > 0 else 0.0
        
        # Drawdowns
        max_dd = self.calculate_max_drawdown(portfolio_equity)
        current_dd = self.calculate_current_drawdown(portfolio_equity)
        
        return {
            'total_return': total_return,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_dd,
            'current_drawdown': current_dd,
            'volatility': volatility
        }
    
    def calculate_and_store_analytics(
        self,
        portfolio_equity: pd.Series,
        benchmark_equity: pd.Series,
        as_of_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Calculate and store portfolio analytics.
        
        Args:
            portfolio_equity: Series of portfolio equity values
            benchmark_equity: Series of benchmark equity values
            as_of_date: Date of calculation (defaults to now)
            
        Returns:
            Dictionary with complete analytics
        """
        if as_of_date is None:
            as_of_date = datetime.now()
        
        # Calculate portfolio metrics
        portfolio_metrics = self.calculate_portfolio_metrics(portfolio_equity)
        
        # Calculate benchmark metrics
        benchmark_metrics = self.calculate_portfolio_metrics(benchmark_equity)
        
        # Calculate relative performance
        excess_return = portfolio_metrics['total_return'] - benchmark_metrics['total_return']
        
        # Tracking error (volatility of excess returns)
        if len(portfolio_equity) > 1 and len(benchmark_equity) > 1:
            portfolio_returns = portfolio_equity.pct_change().dropna()
            benchmark_returns = benchmark_equity.pct_change().dropna()
            
            # Align returns
            aligned_portfolio, aligned_benchmark = portfolio_returns.align(benchmark_returns, join='inner')
            excess_returns = aligned_portfolio - aligned_benchmark
            
            tracking_error = excess_returns.std() * np.sqrt(252) if len(excess_returns) > 1 else 0.0
            information_ratio = (excess_returns.mean() * 252) / tracking_error if tracking_error > 0 else 0.0
        else:
            tracking_error = 0.0
            information_ratio = 0.0
        
        # Assemble analytics
        analytics = {
            'as_of_date': as_of_date.strftime('%Y-%m-%d'),
            'portfolio_metrics': portfolio_metrics,
            'benchmark_metrics': benchmark_metrics,
            'relative_performance': {
                'excess_return': excess_return,
                'information_ratio': information_ratio,
                'tracking_error': tracking_error
            }
        }
        
        # Store to file
        self.state_manager.write_portfolio_analytics(analytics)
        
        logger.info(
            f"Portfolio analytics calculated: "
            f"return={portfolio_metrics['total_return']:.2%}, "
            f"max_dd={portfolio_metrics['max_drawdown']:.2%}, "
            f"sharpe={portfolio_metrics['sharpe_ratio']:.2f}"
        )
        
        return analytics
    
    def get_latest_analytics(self) -> Optional[Dict[str, Any]]:
        """
        Get the latest stored portfolio analytics.
        
        Returns:
            Dictionary with analytics, or None if not found
        """
        try:
            return self.state_manager.read_portfolio_analytics()
        except FileNotFoundError:
            logger.warning("No portfolio analytics found")
            return None
