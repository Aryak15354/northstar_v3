"""
NAVCalculator — Computes properly compounding Net Asset Value time series

NAV computation principles:
1. Fund starts with defined starting capital on inception date
2. Every day, NAV = prior NAV * (1 + daily_return)
3. Transaction costs reduce NAV correctly (already in ledger as negative entries)
4. Corporate actions adjust NAV correctly
5. NAV per unit = total NAV / units outstanding
6. High-water mark is maintained separately, drawdown computed from it
"""

from datetime import datetime, timedelta
from typing import Dict, Optional
import pandas as pd
import numpy as np
import logging

from .ledger import UnifiedPnLLedger, LedgerBook

logger = logging.getLogger(__name__)


class NAVCalculator:
    """Computes properly compounding NAV time series from the ledger"""

    _BUY_ENTRY_TYPES = {
        "EQUITY_BUY",
        "OPTIONS_BUY",
        "SHADOW_BUY",
    }
    _SELL_ENTRY_TYPES = {
        "EQUITY_SELL",
        "OPTIONS_SELL",
        "SHADOW_SELL",
    }
    _CASH_IN_ENTRY_TYPES = {"CASH_IN"}
    _CASH_OUT_ENTRY_TYPES = {"CASH_OUT"}
    _COST_ONLY_ENTRY_TYPES = {"TXN_COST", "SLIPPAGE"}
    
    def __init__(self, ledger: UnifiedPnLLedger, config: dict):
        self.ledger = ledger
        self.config = config
        
        # Get NAV config
        nav_config = config.get('pnl', {}).get('nav', {})
        self.starting_capital = nav_config.get('starting_capital_inr', 10_000_000)
        self.inception_date = pd.to_datetime(nav_config.get('inception_date', '2024-09-01'))
        self.nav_unit_size = nav_config.get('nav_unit_size', 1000)
        self.benchmark = nav_config.get('benchmark', 'NIFTY500_TR')
        self.risk_free_rate = nav_config.get('risk_free_rate_pct', 6.5) / 100  # India 10yr
        
        # Initial units
        self.initial_units = self.starting_capital / self.nav_unit_size

    @classmethod
    def _cash_flow_for_entry(cls, row: pd.Series) -> float:
        """Estimate cash movement from an immutable ledger row."""
        entry_type = str(row.get("entry_type", "") or "").strip().upper()
        notional = float(row.get("notional", 0.0) or 0.0)
        transaction_cost = float(row.get("transaction_cost", 0.0) or 0.0)

        if entry_type in cls._BUY_ENTRY_TYPES:
            return float(-abs(notional) + transaction_cost)
        if entry_type in cls._SELL_ENTRY_TYPES:
            return float(abs(notional) + transaction_cost)
        if entry_type in cls._CASH_IN_ENTRY_TYPES:
            return float(abs(notional))
        if entry_type in cls._CASH_OUT_ENTRY_TYPES:
            return float(-abs(notional))
        if entry_type in cls._COST_ONLY_ENTRY_TYPES:
            return float(transaction_cost if transaction_cost != 0.0 else row.get("net_pnl", 0.0) or 0.0)
        return 0.0
    
    def compute_daily_nav(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> pd.DataFrame:
        """
        Core method. Returns Date-indexed DataFrame with NAV time series.
        """
        logger.info(f"Computing daily NAV from {start_date.date()} to {end_date.date()}")

        query_end_date = pd.Timestamp(end_date).to_pydatetime()
        if query_end_date.time() == datetime.min.time():
            query_end_date = query_end_date + timedelta(days=1) - timedelta(microseconds=1)

        # Get all ledger entries for the period
        df = self.ledger.query(start_date=start_date, end_date=query_end_date)

        if len(df) == 0:
            logger.warning("No ledger entries found for period")
            # Return empty NAV series from inception to end_date
            dates = pd.date_range(self.inception_date, end_date, freq='D')
            return pd.DataFrame({
                'date': dates,
                'nav_combined': [self.starting_capital] * len(dates),
                'nav_equity_only': [self.starting_capital] * len(dates),
                'nav_options_pnl': [0.0] * len(dates),
                'nav_per_unit': [self.starting_capital / self.initial_units] * len(dates),
                'daily_return': [0.0] * len(dates),
                'daily_return_equity': [0.0] * len(dates),
                'high_water_mark': [self.starting_capital] * len(dates),
                'drawdown': [0.0] * len(dates),
                'max_drawdown_to_date': [0.0] * len(dates),
                'net_cash_position': [self.starting_capital] * len(dates),
                'transaction_costs_cumulative': [0.0] * len(dates),
            }).set_index('date')

        # Ensure trade_date is datetime
        if not pd.api.types.is_datetime64_any_dtype(df['trade_date']):
            df['trade_date'] = pd.to_datetime(df['trade_date'])

        # Group by date and compute daily P&L from ALL entries (not just by book)
        # This captures realized P&L from closed positions correctly
        daily_pnl = df.groupby(df['trade_date'].dt.date)['net_pnl'].sum().reset_index()
        daily_pnl.columns = ['date', 'net_pnl']
        daily_pnl['date'] = pd.to_datetime(daily_pnl['date'])

        # Also get equity-only P&L (for equity NAV tracking)
        equity_df = df[df['book'] == 'EQUITY']
        if len(equity_df) > 0:
            equity_daily_pnl = equity_df.groupby(equity_df['trade_date'].dt.date)['net_pnl'].sum().reset_index()
            equity_daily_pnl.columns = ['date', 'equity_pnl']
            equity_daily_pnl['date'] = pd.to_datetime(equity_daily_pnl['date'])
        else:
            equity_daily_pnl = pd.DataFrame(columns=['date', 'equity_pnl'])

        # Get options P&L
        options_df = df[df['book'] == 'OPTIONS']
        if len(options_df) > 0:
            options_daily_pnl = options_df.groupby(options_df['trade_date'].dt.date)['net_pnl'].sum().reset_index()
            options_daily_pnl.columns = ['date', 'options_pnl']
            options_daily_pnl['date'] = pd.to_datetime(options_daily_pnl['date'])
        else:
            options_daily_pnl = pd.DataFrame(columns=['date', 'options_pnl'])

        # Merge all daily P&L
        daily_pnl = daily_pnl.merge(equity_daily_pnl, on='date', how='left').fillna(0)
        daily_pnl = daily_pnl.merge(options_daily_pnl, on='date', how='left').fillna(0)

        # Get transaction costs separately
        cost_df = df[df['transaction_cost'] < 0].groupby(df['trade_date'].dt.date)['transaction_cost'].sum()
        cash_flow_df = df.copy()
        cash_flow_df['cash_flow'] = cash_flow_df.apply(self._cash_flow_for_entry, axis=1)
        daily_cash_flow = cash_flow_df.groupby(cash_flow_df['trade_date'].dt.date)['cash_flow'].sum()

        # Initialize NAV series
        nav_series = []
        current_nav_combined = self.starting_capital
        current_nav_equity = self.starting_capital
        current_cash_position = self.starting_capital
        high_water_mark = self.starting_capital
        max_drawdown = 0.0
        cumulative_options_pnl = 0.0
        cumulative_costs = 0.0

        for date in pd.date_range(start_date, end_date, freq='D'):
            date_key = date.date()

            if date_key not in daily_pnl['date'].dt.date.values:
                # No trading activity this day
                daily_pnl_combined = 0.0
                daily_pnl_equity = 0.0
                daily_pnl_options = 0.0
                daily_costs = 0.0
            else:
                day_row = daily_pnl[pd.to_datetime(daily_pnl['date']).dt.date == date_key].iloc[0]
                daily_pnl_combined = day_row['net_pnl']
                daily_pnl_equity = day_row['equity_pnl']
                daily_pnl_options = day_row['options_pnl']
                daily_costs = cost_df.get(date_key, 0.0)
            daily_cash_change = daily_cash_flow.get(date_key, 0.0)

            # Update NAVs by ADDING daily P&L (not multiplying by return)
            # This correctly captures both realized and unrealized P&L
            current_nav_combined += daily_pnl_combined
            current_nav_equity += daily_pnl_equity
            current_cash_position += daily_cash_change
            cumulative_options_pnl += daily_pnl_options
            cumulative_costs += abs(daily_costs)

            # Compute returns for reporting
            daily_return_combined = daily_pnl_combined / current_nav_combined if current_nav_combined > 0 else 0
            daily_return_equity = daily_pnl_equity / current_nav_equity if current_nav_equity > 0 else 0

            # Update high water mark
            if current_nav_combined > high_water_mark:
                high_water_mark = current_nav_combined

            # Compute drawdown
            drawdown = (current_nav_combined / high_water_mark - 1) if high_water_mark > 0 else 0
            if drawdown < max_drawdown:
                max_drawdown = drawdown

            # NAV per unit
            nav_per_unit = current_nav_combined / self.initial_units if self.initial_units > 0 else 0

            nav_series.append({
                'date': date,
                'nav_combined': current_nav_combined,
                'nav_equity_only': current_nav_equity,
                'nav_options_pnl': cumulative_options_pnl,
                'nav_per_unit': nav_per_unit,
                'daily_return': daily_return_combined,
                'daily_return_equity': daily_return_equity,
                'high_water_mark': high_water_mark,
                'drawdown': drawdown,
                'max_drawdown_to_date': max_drawdown,
                'net_cash_position': current_cash_position,
                'transaction_costs_cumulative': cumulative_costs,
            })
        
        nav_df = pd.DataFrame(nav_series)
        nav_df.set_index('date', inplace=True)
        
        logger.info(f"Computed NAV for {len(nav_df)} days")
        
        return nav_df
    
    def compute_performance_metrics(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> Dict:
        """Compute standard institutional performance metrics"""
        nav_df = self.compute_daily_nav(start_date, end_date)
        
        if len(nav_df) == 0:
            return {}
        
        # Basic returns
        starting_nav = nav_df['nav_combined'].iloc[0]
        ending_nav = nav_df['nav_combined'].iloc[-1]
        total_return = (ending_nav / starting_nav - 1) if starting_nav > 0 else 0
        
        # Annualized return
        days = len(nav_df)
        years = days / 252  # Trading days
        annualized_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0
        
        # Volatility
        daily_returns = nav_df['daily_return'].dropna()
        annualized_volatility = daily_returns.std() * np.sqrt(252) if len(daily_returns) > 0 else 0
        
        # Sharpe ratio
        excess_return = annualized_return - self.risk_free_rate
        sharpe_ratio = excess_return / annualized_volatility if annualized_volatility > 0 else 0
        
        # Sortino ratio (downside deviation)
        downside_returns = daily_returns[daily_returns < 0]
        downside_deviation = downside_returns.std() * np.sqrt(252) if len(downside_returns) > 0 else 0
        sortino_ratio = excess_return / downside_deviation if downside_deviation > 0 else 0
        
        # Drawdown metrics
        max_drawdown = nav_df['max_drawdown_to_date'].min()
        
        # Drawdown duration
        in_drawdown = nav_df['drawdown'] < 0
        if in_drawdown.any():
            drawdown_periods = (in_drawdown != in_drawdown.shift()).cumsum()
            max_drawdown_duration = drawdown_periods[in_drawdown].value_counts().max()
        else:
            max_drawdown_duration = 0
        
        # Calmar ratio
        calmar_ratio = annualized_return / abs(max_drawdown) if max_drawdown != 0 else 0
        
        # Win rate
        win_rate = (daily_returns > 0).sum() / len(daily_returns) if len(daily_returns) > 0 else 0
        
        # Best/worst days
        best_day = daily_returns.max() if len(daily_returns) > 0 else 0
        worst_day = daily_returns.min() if len(daily_returns) > 0 else 0
        
        # Transaction costs
        total_costs = nav_df['transaction_costs_cumulative'].iloc[-1]
        gross_return = total_return + (total_costs / starting_nav) if starting_nav > 0 else 0
        cost_drag = (total_costs / starting_nav) if starting_nav > 0 else 0
        
        # Options contribution
        options_pnl = nav_df['nav_options_pnl'].iloc[-1]
        options_contribution = (options_pnl / starting_nav) if starting_nav > 0 else 0
        
        metrics = {
            'total_return_pct': total_return * 100,
            'annualized_return_pct': annualized_return * 100,
            'annualized_volatility_pct': annualized_volatility * 100,
            'sharpe_ratio': sharpe_ratio,
            'sortino_ratio': sortino_ratio,
            'max_drawdown_pct': max_drawdown * 100,
            'max_drawdown_duration_days': int(max_drawdown_duration),
            'calmar_ratio': calmar_ratio,
            'win_rate_days': win_rate,
            'avg_daily_return_pct': daily_returns.mean() * 100 if len(daily_returns) > 0 else 0,
            'best_day_pct': best_day * 100,
            'worst_day_pct': worst_day * 100,
            'total_transaction_cost_inr': total_costs,
            'transaction_cost_drag_pct': cost_drag * 100,
            'options_pnl_contribution_pct': options_contribution * 100,
            'trading_days': days,
        }
        
        logger.info(f"Performance metrics: Sharpe={sharpe_ratio:.2f}, Return={annualized_return*100:.2f}%, MaxDD={max_drawdown*100:.2f}%")
        
        return metrics
    
    def compute_benchmark_comparison(
        self,
        start_date: datetime,
        end_date: datetime,
        benchmark_series: pd.Series
    ) -> Dict:
        """Compare fund performance to benchmark"""
        nav_df = self.compute_daily_nav(start_date, end_date)
        
        if len(nav_df) == 0 or len(benchmark_series) == 0:
            return {}
        
        # Align dates
        fund_returns = nav_df['daily_return']
        benchmark_returns = benchmark_series.reindex(fund_returns.index).fillna(0)
        
        # Total returns
        fund_total_return = (nav_df['nav_combined'].iloc[-1] / nav_df['nav_combined'].iloc[0] - 1)
        benchmark_total_return = (1 + benchmark_returns).prod() - 1
        
        # Excess return (alpha)
        excess_return = fund_total_return - benchmark_total_return
        
        # Tracking error
        excess_returns = fund_returns - benchmark_returns
        tracking_error = excess_returns.std() * np.sqrt(252)
        
        # Information ratio
        information_ratio = (excess_return / tracking_error) if tracking_error > 0 else 0
        
        # Beta
        covariance = fund_returns.cov(benchmark_returns)
        benchmark_variance = benchmark_returns.var()
        beta = covariance / benchmark_variance if benchmark_variance > 0 else 1.0
        
        # Alpha (Jensen's alpha)
        fund_annualized = (1 + fund_total_return) ** (252 / len(fund_returns)) - 1
        benchmark_annualized = (1 + benchmark_total_return) ** (252 / len(benchmark_returns)) - 1
        alpha_annualized = fund_annualized - (self.risk_free_rate + beta * (benchmark_annualized - self.risk_free_rate))
        
        # Capture ratios
        up_days = benchmark_returns > 0
        down_days = benchmark_returns < 0
        
        upside_capture = (fund_returns[up_days].mean() / benchmark_returns[up_days].mean()) if up_days.sum() > 0 else 0
        downside_capture = (fund_returns[down_days].mean() / benchmark_returns[down_days].mean()) if down_days.sum() > 0 else 0
        
        # Correlation
        correlation = fund_returns.corr(benchmark_returns)
        
        comparison = {
            'fund_return': fund_total_return,
            'benchmark_return': benchmark_total_return,
            'excess_return': excess_return,
            'tracking_error': tracking_error,
            'information_ratio': information_ratio,
            'beta': beta,
            'alpha_annualized': alpha_annualized,
            'upside_capture': upside_capture,
            'downside_capture': downside_capture,
            'correlation': correlation,
        }
        
        return comparison
    
    def get_rolling_metrics(
        self,
        window_days: int = 30
    ) -> pd.DataFrame:
        """Returns rolling versions of all metrics"""
        # Get full NAV history
        nav_df = self.compute_daily_nav(self.inception_date, datetime.now())
        
        if len(nav_df) < window_days:
            logger.warning(f"Not enough data for {window_days}-day rolling metrics")
            return pd.DataFrame()
        
        # Compute rolling metrics
        rolling_return = nav_df['daily_return'].rolling(window_days).mean() * 252
        rolling_vol = nav_df['daily_return'].rolling(window_days).std() * np.sqrt(252)
        rolling_sharpe = (rolling_return - self.risk_free_rate) / rolling_vol
        
        rolling_df = pd.DataFrame({
            'rolling_return_annualized': rolling_return,
            'rolling_volatility_annualized': rolling_vol,
            'rolling_sharpe': rolling_sharpe,
        }, index=nav_df.index)
        
        return rolling_df
