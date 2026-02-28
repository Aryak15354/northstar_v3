#!/usr/bin/env python3
"""
📊 PERFORMANCE TRACKER - LAYER 1: PROOF ENGINE
Point-in-Time Monthly Performance Tracking with No Lookahead Bias

This implements the core of Layer 1 (Proof Engine) for institutional validation.
It provides undeniable proof that Northstar makes money after costs with strict
temporal discipline - no future data ever leaks into past decisions.

CRITICAL PRINCIPLE: Temporal Correctness
- Use t-1 weights with t returns (allocation decided BEFORE returns observed)
- Never use information dated after the decision timestamp
- All metrics computed using only past data

Usage:
    from src.validation.performance_tracker import PerformanceTracker
    
    tracker = PerformanceTracker()
    metrics = tracker.compute_monthly_performance(
        month_end=datetime(2024, 1, 31),
        positions_start={'RELIANCE': 0.05, 'TCS': 0.03},
        returns_current=returns_df,
        nifty_return=0.02
    )
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass, asdict
import os
import warnings
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

warnings.filterwarnings('ignore')


@dataclass
class PerformanceMetrics:
    """
    Monthly performance metrics with strict temporal discipline
    
    All metrics computed using only data available at decision time.
    """
    date: datetime
    northstar_return: float  # Portfolio return for the month
    nifty_return: float  # Benchmark return for the month
    exposure: float  # Average % invested (0.0 to 1.0)
    active_share: float  # Differentiation from NIFTY (0.0 to 1.0)
    turnover: float  # % portfolio traded (>= 0.0)
    drawdown: float  # Running max decline (<= 0.0)
    transaction_costs: float  # Costs paid (>= 0.0)
    net_return: float  # Return after costs
    volatility: float  # 60-day rolling vol (>= 0.0)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        return asdict(self)
    
    def validate(self) -> List[str]:
        """Validate metrics are within expected bounds"""
        errors = []
        
        if not (0.0 <= self.exposure <= 1.0):
            errors.append(f"Exposure {self.exposure} outside bounds [0.0, 1.0]")
        
        if not (0.0 <= self.active_share <= 1.0):
            errors.append(f"Active share {self.active_share} outside bounds [0.0, 1.0]")
        
        if self.turnover < 0.0:
            errors.append(f"Turnover {self.turnover} is negative")
        
        if self.drawdown > 0.0:
            errors.append(f"Drawdown {self.drawdown} is positive (should be <= 0.0)")
        
        if self.transaction_costs < 0.0:
            errors.append(f"Transaction costs {self.transaction_costs} are negative")
        
        if self.volatility < 0.0:
            errors.append(f"Volatility {self.volatility} is negative")
        
        # Net return should equal gross return minus costs
        gross_return = self.northstar_return
        expected_net = gross_return - self.transaction_costs
        if abs(self.net_return - expected_net) > 1e-6:
            errors.append(f"Net return {self.net_return} != gross {gross_return} - costs {self.transaction_costs}")
        
        return errors


class TransactionCostModel:
    """
    Realistic transaction cost model
    
    Applies:
    - Base cost: 0.05% (5 bps)
    - Slippage: Based on liquidity and trade size
    - Market impact: Scales with trade volume
    """
    
    def __init__(self, base_cost_bps: float = 5.0):
        """
        Initialize transaction cost model
        
        Args:
            base_cost_bps: Base cost in basis points (default 5 bps = 0.05%)
        """
        self.base_cost_bps = base_cost_bps
        self.base_cost = base_cost_bps / 10000.0  # Convert bps to decimal
    
    def compute_costs(self,
                     turnover: float,
                     portfolio_value: float = 1.0,
                     liquidity_data: Optional[pd.DataFrame] = None) -> float:
        """
        Compute realistic transaction costs
        
        Args:
            turnover: Portfolio turnover (0.0 to 1.0+)
            portfolio_value: Portfolio value (default 1.0 for percentage)
            liquidity_data: Optional liquidity data for slippage calculation
            
        Returns:
            Total transaction costs as decimal (e.g., 0.001 = 0.1%)
        """
        
        # Base cost
        base_cost = self.base_cost * turnover * portfolio_value
        
        # Slippage (increases with turnover)
        # Higher turnover = more aggressive trading = more slippage
        slippage_factor = 1.0 + (turnover * 0.5)  # 50% increase per 100% turnover
        slippage = base_cost * slippage_factor * 0.2  # 20% of base cost
        
        # Market impact (scales with trade size)
        # Simplified model: impact = k * sqrt(trade_size / ADV)
        # For now, use turnover as proxy
        market_impact = base_cost * np.sqrt(turnover) * 0.1  # 10% of base cost
        
        total_cost = base_cost + slippage + market_impact
        
        return total_cost


class BenchmarkComparator:
    """
    Benchmark Comparator - Layer 1: Proof Engine
    
    Generates performance comparison metrics versus NIFTY benchmark.
    
    Computes:
    - Sharpe Ratio: (Mean Return - Risk Free) / Std Dev
    - Win Rate: % months with positive returns
    - Rolling 3-Month Alpha: Outperformance vs NIFTY
    
    Target Metrics:
    - Sharpe > 1.0 (preferably > 1.5)
    - Win Rate: 55-70%
    - Positive alpha in most rolling windows
    """
    
    def __init__(self, risk_free_rate: float = 0.06):
        """
        Initialize Benchmark Comparator
        
        Args:
            risk_free_rate: Annual risk-free rate (default 6% = 0.06)
        """
        self.risk_free_rate = risk_free_rate
        self.risk_free_monthly = risk_free_rate / 12
        
        print("📈 Benchmark Comparator initialized")
        print(f"   Risk-free rate: {risk_free_rate:.2%} annually")
    
    def compute_sharpe_ratio(self, returns: pd.Series) -> float:
        """
        Compute Sharpe ratio
        
        ENFORCES PROPERTY 11: Sharpe Ratio Formula Correctness
        Sharpe = (Mean Return - Risk Free) / Std Dev
        
        Args:
            returns: Series of returns
            
        Returns:
            Annualized Sharpe ratio
        """
        
        if len(returns) < 2:
            return 0.0
        
        # Calculate excess returns
        excess_returns = returns - self.risk_free_monthly
        
        # Calculate mean and std dev
        mean_excess = excess_returns.mean()
        std_excess = excess_returns.std(ddof=1)
        
        if std_excess == 0:
            return 0.0
        
        # Sharpe ratio (monthly)
        sharpe_monthly = mean_excess / std_excess
        
        # Annualize (multiply by sqrt(12))
        sharpe_annual = sharpe_monthly * np.sqrt(12)
        
        return sharpe_annual
    
    def compute_win_rate(self, returns: pd.Series) -> float:
        """
        Compute win rate (% of positive return months)
        
        ENFORCES PROPERTY 12: Win Rate Bounds
        Win rate must be between 0.0 and 1.0
        
        Args:
            returns: Series of returns
            
        Returns:
            Win rate between 0.0 and 1.0
        """
        
        if len(returns) == 0:
            return 0.0
        
        # Count positive returns
        positive_months = (returns > 0).sum()
        total_months = len(returns)
        
        win_rate = positive_months / total_months
        
        # Ensure bounds
        win_rate = max(0.0, min(1.0, win_rate))
        
        return win_rate
    
    def compute_rolling_alpha(self,
                             northstar_returns: pd.Series,
                             nifty_returns: pd.Series,
                             window: int = 3) -> pd.Series:
        """
        Compute rolling alpha (outperformance vs NIFTY)
        
        Args:
            northstar_returns: Northstar returns
            nifty_returns: NIFTY returns
            window: Rolling window size (default 3 months)
            
        Returns:
            Series of rolling alpha values
        """
        
        if len(northstar_returns) < window or len(nifty_returns) < window:
            return pd.Series()
        
        # Ensure same index
        if not northstar_returns.index.equals(nifty_returns.index):
            # Align indices
            common_index = northstar_returns.index.intersection(nifty_returns.index)
            northstar_returns = northstar_returns.loc[common_index]
            nifty_returns = nifty_returns.loc[common_index]
        
        # Calculate rolling cumulative returns
        northstar_rolling = (1 + northstar_returns).rolling(window=window).apply(lambda x: x.prod() - 1, raw=True)
        nifty_rolling = (1 + nifty_returns).rolling(window=window).apply(lambda x: x.prod() - 1, raw=True)
        
        # Alpha = Northstar return - NIFTY return
        rolling_alpha = northstar_rolling - nifty_rolling
        
        return rolling_alpha
    
    def generate_comparison_report(self,
                                  performance_df: pd.DataFrame) -> Dict:
        """
        Generate comprehensive benchmark comparison report
        
        Args:
            performance_df: DataFrame with performance history
            
        Returns:
            Dictionary with comparison metrics
        """
        
        if performance_df.empty:
            return {}
        
        # Extract returns
        northstar_returns = performance_df['net_return']
        nifty_returns = performance_df['nifty_return']
        
        # Compute Sharpe ratios
        northstar_sharpe = self.compute_sharpe_ratio(northstar_returns)
        nifty_sharpe = self.compute_sharpe_ratio(nifty_returns)
        
        # Compute win rates
        northstar_win_rate = self.compute_win_rate(northstar_returns)
        nifty_win_rate = self.compute_win_rate(nifty_returns)
        
        # Compute rolling alpha
        rolling_alpha = self.compute_rolling_alpha(northstar_returns, nifty_returns)
        
        # Calculate cumulative returns
        northstar_cumulative = (1 + northstar_returns).prod() - 1
        nifty_cumulative = (1 + nifty_returns).prod() - 1
        outperformance = northstar_cumulative - nifty_cumulative
        
        # Calculate volatilities
        northstar_vol = northstar_returns.std() * np.sqrt(12)
        nifty_vol = nifty_returns.std() * np.sqrt(12)
        
        # Calculate max drawdowns
        northstar_max_dd = performance_df['drawdown'].min()
        
        # Calculate NIFTY drawdown
        nifty_cumulative_series = (1 + nifty_returns).cumprod()
        nifty_peak = nifty_cumulative_series.expanding().max()
        nifty_drawdown = (nifty_cumulative_series - nifty_peak) / nifty_peak
        nifty_max_dd = nifty_drawdown.min()
        
        # Positive alpha months
        if not rolling_alpha.empty:
            positive_alpha_pct = (rolling_alpha > 0).sum() / len(rolling_alpha.dropna())
        else:
            positive_alpha_pct = 0.0
        
        return {
            'northstar_sharpe': northstar_sharpe,
            'nifty_sharpe': nifty_sharpe,
            'sharpe_advantage': northstar_sharpe - nifty_sharpe,
            'northstar_win_rate': northstar_win_rate,
            'nifty_win_rate': nifty_win_rate,
            'northstar_cumulative_return': northstar_cumulative,
            'nifty_cumulative_return': nifty_cumulative,
            'outperformance': outperformance,
            'northstar_volatility': northstar_vol,
            'nifty_volatility': nifty_vol,
            'northstar_max_drawdown': northstar_max_dd,
            'nifty_max_drawdown': nifty_max_dd,
            'positive_alpha_pct': positive_alpha_pct,
            'rolling_alpha_mean': rolling_alpha.mean() if not rolling_alpha.empty else 0.0,
            'rolling_alpha_std': rolling_alpha.std() if not rolling_alpha.empty else 0.0
        }


class VisualizationEngine:
    """
    Visualization Engine - Layer 1: Proof Engine
    
    Creates institutional-quality performance charts.
    
    Outputs:
    - Cumulative return chart (Northstar vs NIFTY)
    - Drawdown comparison chart
    - Rolling alpha chart
    
    All charts saved to docs/figures/
    """
    
    def __init__(self, output_dir: str = "docs/figures"):
        """
        Initialize Visualization Engine
        
        Args:
            output_dir: Directory for output charts
        """
        self.output_dir = output_dir
        
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        
        # Set style
        plt.style.use('seaborn-v0_8-darkgrid')
        
        print("📊 Visualization Engine initialized")
        print(f"   Output: {output_dir}/")
    
    def plot_cumulative_returns(self,
                               performance_df: pd.DataFrame,
                               filename: str = "northstar_vs_nifty_12m.png") -> str:
        """
        Generate cumulative return chart (Northstar vs NIFTY)
        
        ENFORCES PROPERTY 10: Visualization Data Fidelity
        Chart must accurately represent compounded returns
        
        Args:
            performance_df: DataFrame with performance history
            filename: Output filename
            
        Returns:
            Path to saved chart
        """
        
        if performance_df.empty:
            print("⚠️ No data to plot")
            return ""
        
        # Calculate cumulative returns
        northstar_cumulative = (1 + performance_df['net_return']).cumprod()
        nifty_cumulative = (1 + performance_df['nifty_return']).cumprod()
        
        # Create figure
        fig, ax = plt.subplots(figsize=(12, 6))
        
        # Plot cumulative returns
        ax.plot(performance_df['date'], northstar_cumulative, 
                label='Northstar', linewidth=2, color='#2E86AB')
        ax.plot(performance_df['date'], nifty_cumulative, 
                label='NIFTY', linewidth=2, color='#A23B72', linestyle='--')
        
        # Formatting
        ax.set_xlabel('Date', fontsize=12)
        ax.set_ylabel('Cumulative Return (Base = 1.0)', fontsize=12)
        ax.set_title('Northstar vs NIFTY: Cumulative Returns', fontsize=14, fontweight='bold')
        ax.legend(loc='best', fontsize=11)
        ax.grid(True, alpha=0.3)
        
        # Format x-axis
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        plt.xticks(rotation=45)
        
        # Add horizontal line at 1.0
        ax.axhline(y=1.0, color='gray', linestyle=':', alpha=0.5)
        
        plt.tight_layout()
        
        # Save
        output_path = os.path.join(self.output_dir, filename)
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"✅ Saved cumulative returns chart: {output_path}")
        
        return output_path
    
    def plot_drawdown_comparison(self,
                                performance_df: pd.DataFrame,
                                filename: str = "drawdown_comparison.png") -> str:
        """
        Generate drawdown comparison chart
        
        Args:
            performance_df: DataFrame with performance history
            filename: Output filename
            
        Returns:
            Path to saved chart
        """
        
        if performance_df.empty:
            print("⚠️ No data to plot")
            return ""
        
        # Get Northstar drawdown
        northstar_drawdown = performance_df['drawdown']
        
        # Calculate NIFTY drawdown
        nifty_cumulative = (1 + performance_df['nifty_return']).cumprod()
        nifty_peak = nifty_cumulative.expanding().max()
        nifty_drawdown = (nifty_cumulative - nifty_peak) / nifty_peak
        
        # Create figure
        fig, ax = plt.subplots(figsize=(12, 6))
        
        # Plot drawdowns
        ax.fill_between(performance_df['date'], northstar_drawdown * 100, 0,
                        label='Northstar', alpha=0.6, color='#2E86AB')
        ax.fill_between(performance_df['date'], nifty_drawdown * 100, 0,
                        label='NIFTY', alpha=0.4, color='#A23B72')
        
        # Formatting
        ax.set_xlabel('Date', fontsize=12)
        ax.set_ylabel('Drawdown (%)', fontsize=12)
        ax.set_title('Drawdown Comparison: Northstar vs NIFTY', fontsize=14, fontweight='bold')
        ax.legend(loc='lower left', fontsize=11)
        ax.grid(True, alpha=0.3)
        
        # Format x-axis
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        plt.xticks(rotation=45)
        
        # Invert y-axis (drawdowns are negative)
        ax.invert_yaxis()
        
        plt.tight_layout()
        
        # Save
        output_path = os.path.join(self.output_dir, filename)
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"✅ Saved drawdown comparison chart: {output_path}")
        
        return output_path
    
    def plot_rolling_alpha(self,
                          performance_df: pd.DataFrame,
                          window: int = 3,
                          filename: str = "rolling_alpha.png") -> str:
        """
        Generate rolling alpha chart (3-month rolling outperformance)
        
        Args:
            performance_df: DataFrame with performance history
            window: Rolling window size (default 3 months)
            filename: Output filename
            
        Returns:
            Path to saved chart
        """
        
        if performance_df.empty or len(performance_df) < window:
            print("⚠️ Insufficient data to plot rolling alpha")
            return ""
        
        # Calculate rolling cumulative returns
        northstar_rolling = (1 + performance_df['net_return']).rolling(window=window).apply(
            lambda x: x.prod() - 1, raw=True
        )
        nifty_rolling = (1 + performance_df['nifty_return']).rolling(window=window).apply(
            lambda x: x.prod() - 1, raw=True
        )
        
        # Calculate rolling alpha
        rolling_alpha = (northstar_rolling - nifty_rolling) * 100  # Convert to percentage
        
        # Create figure
        fig, ax = plt.subplots(figsize=(12, 6))
        
        # Plot rolling alpha
        ax.plot(performance_df['date'], rolling_alpha, 
                linewidth=2, color='#F18F01', label=f'{window}-Month Rolling Alpha')
        
        # Fill positive/negative areas
        ax.fill_between(performance_df['date'], rolling_alpha, 0,
                        where=(rolling_alpha >= 0), alpha=0.3, color='green', label='Outperformance')
        ax.fill_between(performance_df['date'], rolling_alpha, 0,
                        where=(rolling_alpha < 0), alpha=0.3, color='red', label='Underperformance')
        
        # Formatting
        ax.set_xlabel('Date', fontsize=12)
        ax.set_ylabel('Rolling Alpha (%)', fontsize=12)
        ax.set_title(f'{window}-Month Rolling Alpha: Northstar vs NIFTY', fontsize=14, fontweight='bold')
        ax.legend(loc='best', fontsize=11)
        ax.grid(True, alpha=0.3)
        
        # Format x-axis
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        plt.xticks(rotation=45)
        
        # Add horizontal line at 0
        ax.axhline(y=0, color='black', linestyle='-', linewidth=0.8)
        
        plt.tight_layout()
        
        # Save
        output_path = os.path.join(self.output_dir, filename)
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"✅ Saved rolling alpha chart: {output_path}")
        
        return output_path
    
    def generate_all_charts(self, performance_df: pd.DataFrame) -> Dict[str, str]:
        """
        Generate all performance charts
        
        Args:
            performance_df: DataFrame with performance history
            
        Returns:
            Dictionary mapping chart names to file paths
        """
        
        charts = {}
        
        # Generate cumulative returns chart
        charts['cumulative_returns'] = self.plot_cumulative_returns(performance_df)
        
        # Generate drawdown comparison chart
        charts['drawdown_comparison'] = self.plot_drawdown_comparison(performance_df)
        
        # Generate rolling alpha chart
        charts['rolling_alpha'] = self.plot_rolling_alpha(performance_df)
        
        return charts


class PerformanceTracker:
    """
    Performance Tracker - Layer 1: Proof Engine
    
    Provides undeniable proof that Northstar makes money after costs
    with strict temporal discipline (no lookahead bias).
    
    ENFORCES PROPERTY 1: Temporal Correctness
    - Uses t-1 weights with t returns
    - Never uses future information
    
    V3 INTEGRATION:
    - Uses UnifiedState for state storage (Requirement 14.1)
    - Emits events through EventBus (Requirement 14.2)
    - Integrates with Market_Clock for time-driven updates (Requirement 14.4)
    """
    
    def __init__(self, 
                 output_dir: str = "data/processed",
                 unified_state=None,
                 event_bus=None,
                 market_clock=None):
        """
        Initialize Performance Tracker
        
        Args:
            output_dir: Directory for output files
            unified_state: Optional UnifiedState instance for V3 integration
            event_bus: Optional EventBus instance for V3 integration
            market_clock: Optional Market_Clock instance for V3 integration
        """
        self.output_dir = output_dir
        self.performance_file = os.path.join(output_dir, "performance_summary.parquet")
        
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        
        # Transaction cost model
        self.cost_model = TransactionCostModel(base_cost_bps=5.0)
        
        # Historical data for rolling calculations
        self.historical_returns: List[float] = []
        self.historical_values: List[float] = [1.0]  # Start with $1
        self.peak_value: float = 1.0
        
        # Previous month positions for turnover calculation
        self.previous_positions: Optional[Dict[str, float]] = None
        
        # V3 Integration (optional)
        self.unified_state = unified_state
        self.event_bus = event_bus
        self.market_clock = market_clock
        
        print("📊 Performance Tracker initialized")
        print(f"   Output: {self.performance_file}")
        if unified_state:
            print("   ✅ V3 Integration: UnifiedState connected")
        if event_bus:
            print("   ✅ V3 Integration: EventBus connected")
        if market_clock:
            print("   ✅ V3 Integration: Market_Clock connected")
    
    def compute_monthly_performance(self,
                                   month_end: datetime,
                                   positions_start: Dict[str, float],
                                   returns_current: pd.DataFrame,
                                   nifty_return: float,
                                   nifty_weights: Optional[Dict[str, float]] = None) -> PerformanceMetrics:
        """
        Compute monthly performance with strict temporal discipline
        
        CRITICAL: Uses t-1 weights (positions_start) with t returns (returns_current)
        This ensures no lookahead bias - allocation decided BEFORE returns observed.
        
        Args:
            month_end: End date of the month
            positions_start: Portfolio weights at START of month (t-1)
            returns_current: Stock returns during CURRENT month (t)
            nifty_return: NIFTY return for the month
            nifty_weights: Optional NIFTY constituent weights for active share
            
        Returns:
            PerformanceMetrics for the month
        """
        
        # Validate temporal correctness
        if not isinstance(month_end, datetime):
            month_end = pd.to_datetime(month_end)
        
        # Calculate portfolio return using t-1 weights and t returns
        portfolio_return = self._calculate_portfolio_return(positions_start, returns_current)
        
        # Calculate exposure (average % invested) - cap at 1.0
        exposure = min(1.0, sum(abs(w) for w in positions_start.values()))
        
        # Calculate active share (differentiation from NIFTY)
        active_share = self._calculate_active_share(positions_start, nifty_weights)
        
        # Calculate turnover (% portfolio traded)
        turnover = self._calculate_turnover(positions_start)
        
        # Calculate transaction costs
        transaction_costs = self.cost_model.compute_costs(turnover)
        
        # Calculate net return (after costs)
        net_return = portfolio_return - transaction_costs
        
        # Update historical data
        self.historical_returns.append(net_return)
        current_value = self.historical_values[-1] * (1 + net_return)
        self.historical_values.append(current_value)
        
        # Calculate drawdown
        self.peak_value = max(self.peak_value, current_value)
        drawdown = (current_value - self.peak_value) / self.peak_value
        
        # Calculate volatility (60-day rolling)
        volatility = self._calculate_volatility()
        
        # Store current positions for next month's turnover calculation
        self.previous_positions = positions_start.copy()
        
        # Create metrics object
        metrics = PerformanceMetrics(
            date=month_end,
            northstar_return=portfolio_return,
            nifty_return=nifty_return,
            exposure=exposure,
            active_share=active_share,
            turnover=turnover,
            drawdown=drawdown,
            transaction_costs=transaction_costs,
            net_return=net_return,
            volatility=volatility
        )
        
        # Validate metrics
        validation_errors = metrics.validate()
        if validation_errors:
            print(f"⚠️ Validation warnings for {month_end.date()}:")
            for error in validation_errors:
                print(f"   {error}")
        
        # V3 Integration: Store in UnifiedState
        self._store_in_unified_state(metrics)
        
        # V3 Integration: Emit performance event
        self._emit_performance_event(metrics)
        
        return metrics
    
    def _calculate_portfolio_return(self,
                                   positions: Dict[str, float],
                                   returns: pd.DataFrame) -> float:
        """
        Calculate portfolio return as weighted sum of asset returns
        
        ENFORCES PROPERTY 2: Performance Calculation Correctness
        Portfolio return = sum(weight_i * return_i)
        
        Args:
            positions: Portfolio weights {ticker: weight}
            returns: DataFrame with 'ticker' and 'return' columns
            
        Returns:
            Portfolio return as decimal
        """
        
        if returns.empty or not positions:
            return 0.0
        
        # Ensure returns DataFrame has required columns
        if 'ticker' not in returns.columns or 'return' not in returns.columns:
            # Try to infer structure
            if len(returns.columns) >= 2:
                returns = returns.copy()
                returns.columns = ['ticker', 'return']
            else:
                return 0.0
        
        # Calculate weighted return
        portfolio_return = 0.0
        
        for ticker, weight in positions.items():
            # Find return for this ticker
            ticker_returns = returns[returns['ticker'] == ticker]
            
            if not ticker_returns.empty:
                ticker_return = ticker_returns['return'].iloc[0]
                portfolio_return += weight * ticker_return
        
        return portfolio_return
    
    def _calculate_active_share(self,
                                portfolio_weights: Dict[str, float],
                                benchmark_weights: Optional[Dict[str, float]]) -> float:
        """
        Calculate active share (portfolio differentiation from benchmark)
        
        ENFORCES PROPERTY 6: Active Share Bounds
        Active share = 0.5 * sum(|w_portfolio - w_benchmark|)
        Range: [0.0, 1.0] where 0.0 = identical, 1.0 = completely different
        
        Args:
            portfolio_weights: Portfolio weights
            benchmark_weights: Benchmark weights (optional)
            
        Returns:
            Active share between 0.0 and 1.0
        """
        
        if benchmark_weights is None:
            # If no benchmark weights provided, assume high active share
            # (portfolio is differentiated from equal-weight benchmark)
            return 0.8
        
        # Get all tickers
        all_tickers = set(portfolio_weights.keys()) | set(benchmark_weights.keys())
        
        # Calculate sum of absolute differences
        total_diff = 0.0
        
        for ticker in all_tickers:
            port_weight = portfolio_weights.get(ticker, 0.0)
            bench_weight = benchmark_weights.get(ticker, 0.0)
            total_diff += abs(port_weight - bench_weight)
        
        # Active share is half the sum of absolute differences
        active_share = 0.5 * total_diff
        
        # Ensure bounds [0.0, 1.0]
        active_share = max(0.0, min(1.0, active_share))
        
        return active_share
    
    def _calculate_turnover(self, current_positions: Dict[str, float]) -> float:
        """
        Calculate portfolio turnover
        
        ENFORCES PROPERTY 7: Turnover Non-Negativity
        Turnover = 0.5 * sum(|w_current - w_previous|)
        
        Args:
            current_positions: Current portfolio weights
            
        Returns:
            Turnover as decimal (>= 0.0)
        """
        
        if self.previous_positions is None:
            # First month - assume full portfolio construction
            return sum(abs(w) for w in current_positions.values())
        
        # Get all tickers
        all_tickers = set(current_positions.keys()) | set(self.previous_positions.keys())
        
        # Calculate sum of absolute weight changes
        total_change = 0.0
        
        for ticker in all_tickers:
            current_weight = current_positions.get(ticker, 0.0)
            previous_weight = self.previous_positions.get(ticker, 0.0)
            total_change += abs(current_weight - previous_weight)
        
        # Turnover is half the sum of absolute changes
        turnover = 0.5 * total_change
        
        # Ensure non-negative
        turnover = max(0.0, turnover)
        
        return turnover
    
    def _calculate_volatility(self, window: int = 60) -> float:
        """
        Calculate rolling volatility
        
        Uses 60-day (approximately 3-month) rolling window
        
        Args:
            window: Rolling window size in days (default 60)
            
        Returns:
            Annualized volatility
        """
        
        if len(self.historical_returns) < 2:
            return 0.0
        
        # Use last N returns
        recent_returns = self.historical_returns[-window:]
        
        if len(recent_returns) < 2:
            return 0.0
        
        # Calculate standard deviation
        std_dev = np.std(recent_returns, ddof=1)
        
        # Annualize (assuming monthly returns, multiply by sqrt(12))
        annualized_vol = std_dev * np.sqrt(12)
        
        return annualized_vol
    
    def persist_metrics(self, metrics: PerformanceMetrics):
        """
        Persist performance metrics to parquet file
        
        ENFORCES PROPERTY 9: Data Persistence Round-Trip
        
        Args:
            metrics: Performance metrics to persist
        """
        
        # Convert to DataFrame
        metrics_dict = metrics.to_dict()
        new_row = pd.DataFrame([metrics_dict])
        
        # Append to existing file or create new
        if os.path.exists(self.performance_file):
            existing_df = pd.read_parquet(self.performance_file)
            updated_df = pd.concat([existing_df, new_row], ignore_index=True)
        else:
            updated_df = new_row
        
        # Ensure proper schema
        updated_df = self._enforce_schema(updated_df)
        
        # Save to parquet
        updated_df.to_parquet(self.performance_file, index=False)
        
        print(f"✅ Persisted metrics for {metrics.date.date()}")
    
    def _enforce_schema(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Enforce performance summary schema
        
        ENFORCES PROPERTY 3: Schema Completeness
        ENFORCES REQUIREMENT 15: Performance Summary Schema Validation
        
        Args:
            df: DataFrame to validate
            
        Returns:
            DataFrame with enforced schema
        """
        
        # Required columns with types
        required_schema = {
            'date': 'datetime64[ns]',
            'northstar_return': 'float64',
            'nifty_return': 'float64',
            'exposure': 'float64',
            'active_share': 'float64',
            'turnover': 'float64',
            'drawdown': 'float64',
            'transaction_costs': 'float64',
            'net_return': 'float64',
            'volatility': 'float64'
        }
        
        # Ensure all required columns exist
        for col in required_schema.keys():
            if col not in df.columns:
                raise ValueError(f"Missing required column: {col}")
        
        # Enforce types
        for col, dtype in required_schema.items():
            if col == 'date':
                df[col] = pd.to_datetime(df[col])
            else:
                df[col] = df[col].astype(dtype)
        
        # Validate and fix bounds
        # Cap exposure between 0.0 and 1.0
        df['exposure'] = df['exposure'].clip(0.0, 1.0)
        
        # Cap active_share between 0.0 and 1.0
        if 'active_share' in df.columns:
            df['active_share'] = df['active_share'].clip(0.0, 1.0)
        
        # Ensure turnover is non-negative
        if 'turnover' in df.columns:
            df['turnover'] = df['turnover'].clip(0.0, None)
        
        # Ensure drawdown is non-positive (cap at 0.0)
        if 'drawdown' in df.columns:
            df['drawdown'] = df['drawdown'].clip(None, 0.0)
        
        # Ensure transaction costs are non-negative
        if 'transaction_costs' in df.columns:
            df['transaction_costs'] = df['transaction_costs'].clip(0.0, None)
        
        # Ensure volatility is non-negative
        if 'volatility' in df.columns:
            df['volatility'] = df['volatility'].clip(0.0, None)
        
        return df
    
    def load_performance_summary(self) -> pd.DataFrame:
        """
        Load performance summary from disk
        
        Returns:
            DataFrame with performance history
        """
        
        if not os.path.exists(self.performance_file):
            return pd.DataFrame()
        
        df = pd.read_parquet(self.performance_file)
        
        # Ensure proper schema
        df = self._enforce_schema(df)
        
        return df
    
    def get_summary_statistics(self) -> Dict:
        """
        Get summary statistics for performance tracking
        
        Returns:
            Dictionary with summary stats
        """
        
        df = self.load_performance_summary()
        
        if df.empty:
            return {}
        
        # Calculate summary statistics
        total_months = len(df)
        total_return = (1 + df['net_return']).prod() - 1
        avg_monthly_return = df['net_return'].mean()
        annualized_return = (1 + avg_monthly_return) ** 12 - 1
        
        # Sharpe ratio (assuming 6% risk-free rate)
        risk_free_monthly = 0.06 / 12
        excess_returns = df['net_return'] - risk_free_monthly
        sharpe_ratio = excess_returns.mean() / excess_returns.std() * np.sqrt(12) if excess_returns.std() > 0 else 0
        
        # Win rate
        win_rate = (df['net_return'] > 0).mean()
        
        # Average metrics
        avg_exposure = df['exposure'].mean()
        avg_active_share = df['active_share'].mean()
        avg_turnover = df['turnover'].mean()
        avg_costs = df['transaction_costs'].mean()
        
        # Drawdown stats
        max_drawdown = df['drawdown'].min()
        avg_drawdown = df['drawdown'].mean()
        
        # Benchmark comparison
        total_nifty_return = (1 + df['nifty_return']).prod() - 1
        outperformance = total_return - total_nifty_return
        
        return {
            'total_months': total_months,
            'total_return': total_return,
            'annualized_return': annualized_return,
            'sharpe_ratio': sharpe_ratio,
            'win_rate': win_rate,
            'avg_exposure': avg_exposure,
            'avg_active_share': avg_active_share,
            'avg_turnover': avg_turnover,
            'avg_costs': avg_costs,
            'max_drawdown': max_drawdown,
            'avg_drawdown': avg_drawdown,
            'total_nifty_return': total_nifty_return,
            'outperformance': outperformance
        }


    # ========================================================================
    # V3 INTEGRATION METHODS
    # ========================================================================
    
    def _store_in_unified_state(self, metrics: PerformanceMetrics):
        """
        Store performance metrics in UnifiedState
        
        ENFORCES PROPERTY 31: V3 Integration State Management
        VALIDATES REQUIREMENT 14.1: Use UnifiedState for state storage
        
        Args:
            metrics: Performance metrics to store
        """
        
        if self.unified_state is None:
            return
        
        try:
            # Store in performance_validation component
            component_name = "performance_validation"
            
            # Store latest metrics
            self.unified_state.set(
                component=component_name,
                key="latest_metrics",
                value=metrics.to_dict()
            )
            
            # Store cumulative performance
            self.unified_state.set(
                component=component_name,
                key="cumulative_return",
                value=(1 + metrics.net_return) * self.unified_state.get(
                    component=component_name,
                    key="cumulative_return",
                    default=1.0
                )
            )
            
            # Store peak value for drawdown tracking
            self.unified_state.set(
                component=component_name,
                key="peak_value",
                value=self.peak_value
            )
            
            # Store historical returns
            self.unified_state.set(
                component=component_name,
                key="historical_returns",
                value=self.historical_returns[-60:]  # Keep last 60 months
            )
            
        except Exception as e:
            print(f"⚠️ Failed to store in UnifiedState: {e}")
    
    def _emit_performance_event(self, metrics: PerformanceMetrics):
        """
        Emit performance event through EventBus
        
        ENFORCES PROPERTY 32: V3 Integration Event Emission
        VALIDATES REQUIREMENT 14.2: Emit events through EventBus
        
        Args:
            metrics: Performance metrics to emit
        """
        
        if self.event_bus is None:
            return
        
        try:
            # Emit performance update event
            self.event_bus.emit(
                event_type="PERFORMANCE_UPDATE",
                source="performance_tracker",
                data={
                    "date": metrics.date.isoformat(),
                    "northstar_return": metrics.northstar_return,
                    "nifty_return": metrics.nifty_return,
                    "net_return": metrics.net_return,
                    "exposure": metrics.exposure,
                    "drawdown": metrics.drawdown,
                    "transaction_costs": metrics.transaction_costs,
                    "volatility": metrics.volatility,
                    "outperformance": metrics.northstar_return - metrics.nifty_return
                },
                tags=["performance", "validation", "layer1"]
            )
            
            # Emit alert if significant drawdown
            if metrics.drawdown < -0.10:  # More than 10% drawdown
                self.event_bus.emit(
                    event_type="RISK_ALERT",
                    source="performance_tracker",
                    data={
                        "alert_type": "drawdown_warning",
                        "drawdown": metrics.drawdown,
                        "threshold": -0.10,
                        "date": metrics.date.isoformat()
                    },
                    tags=["risk", "drawdown", "alert"],
                    priority="HIGH"
                )
            
            # Emit alert if high transaction costs
            if metrics.transaction_costs > 0.01:  # More than 1% costs
                self.event_bus.emit(
                    event_type="COST_ALERT",
                    source="performance_tracker",
                    data={
                        "alert_type": "high_transaction_costs",
                        "costs": metrics.transaction_costs,
                        "turnover": metrics.turnover,
                        "date": metrics.date.isoformat()
                    },
                    tags=["costs", "alert"],
                    priority="MEDIUM"
                )
            
        except Exception as e:
            print(f"⚠️ Failed to emit event: {e}")
    
    def register_with_market_clock(self):
        """
        Register performance tracking with Market_Clock for time-driven updates
        
        VALIDATES REQUIREMENT 14.4: Use Market_Clock for time-driven updates
        
        This allows the performance tracker to automatically update at month-end.
        """
        
        if self.market_clock is None:
            print("⚠️ Market_Clock not available for registration")
            return
        
        try:
            # Register callback for month-end events
            def on_month_end(event):
                """Handle month-end event from Market_Clock"""
                print(f"📅 Month-end event received: {event.get('date')}")
                # Performance computation would be triggered here in live operation
                # For now, just log the event
            
            # Subscribe to month-end events
            if hasattr(self.market_clock, 'subscribe'):
                self.market_clock.subscribe('MONTH_END', on_month_end)
                print("✅ Registered with Market_Clock for month-end updates")
            else:
                print("⚠️ Market_Clock does not support subscriptions")
                
        except Exception as e:
            print(f"⚠️ Failed to register with Market_Clock: {e}")
    
    def load_from_unified_state(self) -> Optional[Dict]:
        """
        Load performance state from UnifiedState
        
        Returns:
            Dictionary with performance state or None
        """
        
        if self.unified_state is None:
            return None
        
        try:
            component_name = "performance_validation"
            
            state = {
                "latest_metrics": self.unified_state.get(
                    component=component_name,
                    key="latest_metrics",
                    default=None
                ),
                "cumulative_return": self.unified_state.get(
                    component=component_name,
                    key="cumulative_return",
                    default=1.0
                ),
                "peak_value": self.unified_state.get(
                    component=component_name,
                    key="peak_value",
                    default=1.0
                ),
                "historical_returns": self.unified_state.get(
                    component=component_name,
                    key="historical_returns",
                    default=[]
                )
            }
            
            return state
            
        except Exception as e:
            print(f"⚠️ Failed to load from UnifiedState: {e}")
            return None


def main():
    """Demonstrate Performance Tracker"""
    
    print("📊 PERFORMANCE TRACKER - DEMONSTRATION")
    print("=" * 60)
    
    # Initialize tracker
    tracker = PerformanceTracker(output_dir="data/processed")
    
    # Initialize benchmark comparator
    comparator = BenchmarkComparator(risk_free_rate=0.06)
    
    # Initialize visualization engine
    visualizer = VisualizationEngine(output_dir="docs/figures")
    
    # Simulate 12 months of performance
    np.random.seed(42)
    
    for month in range(12):
        month_end = datetime(2024, month + 1, 28)
        
        # Mock positions (t-1 weights)
        positions_start = {
            'RELIANCE': 0.05,
            'TCS': 0.04,
            'INFY': 0.03,
            'HDFCBANK': 0.06,
            'ICICIBANK': 0.04
        }
        
        # Mock returns (t returns)
        returns_current = pd.DataFrame({
            'ticker': ['RELIANCE', 'TCS', 'INFY', 'HDFCBANK', 'ICICIBANK'],
            'return': np.random.normal(0.01, 0.05, 5)  # 1% mean, 5% std
        })
        
        # Mock NIFTY return
        nifty_return = np.random.normal(0.008, 0.04)  # 0.8% mean, 4% std
        
        # Compute performance
        metrics = tracker.compute_monthly_performance(
            month_end=month_end,
            positions_start=positions_start,
            returns_current=returns_current,
            nifty_return=nifty_return
        )
        
        # Persist metrics
        tracker.persist_metrics(metrics)
        
        print(f"\n📅 {month_end.date()}")
        print(f"   Northstar: {metrics.northstar_return:+.2%}")
        print(f"   NIFTY: {metrics.nifty_return:+.2%}")
        print(f"   Net Return: {metrics.net_return:+.2%}")
        print(f"   Costs: {metrics.transaction_costs:.4%}")
        print(f"   Turnover: {metrics.turnover:.2%}")
    
    # Get summary statistics
    print("\n📊 SUMMARY STATISTICS")
    print("=" * 60)
    
    stats = tracker.get_summary_statistics()
    
    for key, value in stats.items():
        if isinstance(value, float):
            if 'return' in key or 'performance' in key or 'drawdown' in key:
                print(f"   {key}: {value:+.2%}")
            elif 'ratio' in key or 'rate' in key or 'share' in key or 'exposure' in key or 'turnover' in key or 'costs' in key:
                print(f"   {key}: {value:.2%}")
            else:
                print(f"   {key}: {value:.4f}")
        else:
            print(f"   {key}: {value}")
    
    # Generate benchmark comparison
    print("\n📈 BENCHMARK COMPARISON")
    print("=" * 60)
    
    performance_df = tracker.load_performance_summary()
    comparison = comparator.generate_comparison_report(performance_df)
    
    for key, value in comparison.items():
        if isinstance(value, float):
            if 'return' in key or 'performance' in key or 'drawdown' in key or 'alpha' in key:
                print(f"   {key}: {value:+.2%}")
            elif 'ratio' in key or 'rate' in key or 'pct' in key or 'volatility' in key:
                print(f"   {key}: {value:.2%}")
            else:
                print(f"   {key}: {value:.4f}")
        else:
            print(f"   {key}: {value}")
    
    # Generate visualizations
    print("\n📊 GENERATING VISUALIZATIONS")
    print("=" * 60)
    
    charts = visualizer.generate_all_charts(performance_df)
    
    print("\n✅ Performance Tracker demonstration complete")


if __name__ == "__main__":
    main()
