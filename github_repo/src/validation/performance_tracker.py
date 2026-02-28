"""
Performance Tracker - Point-in-Time Performance Attribution

This module provides comprehensive performance tracking and attribution with
strict temporal consistency and no-lookahead bias prevention.
"""

from abc import ABC, abstractmethod
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass
from enum import Enum
import numpy as np
import pandas as pd


class AttributionMethod(Enum):
    """Performance attribution methodologies"""
    BRINSON = "brinson"
    FACTOR = "factor"
    SECTOR = "sector"
    SECURITY = "security"
    CURRENCY = "currency"


class PerformancePeriod(Enum):
    """Performance measurement periods"""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"
    INCEPTION = "inception"


@dataclass
class Return:
    """Return data point"""
    date: date
    portfolio_return: float
    benchmark_return: float
    active_return: float
    gross_return: float
    net_return: float
    currency: str = "USD"


@dataclass
class Attribution:
    """Performance attribution result"""
    date: date
    method: AttributionMethod
    allocation_effect: float
    selection_effect: float
    interaction_effect: float
    total_effect: float
    breakdown: Dict[str, float]


@dataclass
class RiskMetrics:
    """Risk-adjusted performance metrics"""
    volatility: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    var_95: float
    var_99: float
    beta: float
    alpha: float
    tracking_error: float
    information_ratio: float


@dataclass
class PerformanceSummary:
    """Comprehensive performance summary"""
    period: PerformancePeriod
    start_date: date
    end_date: date
    total_return: float
    annualized_return: float
    benchmark_return: float
    active_return: float
    risk_metrics: RiskMetrics
    attributions: List[Attribution]


class TemporalValidator:
    """Validates temporal consistency in performance calculations"""
    
    def __init__(self, current_time: datetime):
        self.current_time = current_time
    
    def validate_data_access(self, data_timestamp: datetime) -> bool:
        """Ensure no future data access"""
        return data_timestamp <= self.current_time
    
    def validate_calculation_period(self, start_date: date, end_date: date) -> bool:
        """Validate calculation period doesn't extend into future"""
        return end_date <= self.current_time.date()


class ReturnCalculator:
    """Point-in-time return calculation with temporal validation"""
    
    def __init__(self, temporal_validator: TemporalValidator):
        self.temporal_validator = temporal_validator
    
    def calculate_simple_return(self, start_value: float, end_value: float) -> float:
        """Calculate simple return"""
        if start_value <= 0:
            raise ValueError("Start value must be positive")
        return (end_value - start_value) / start_value
    
    def calculate_log_return(self, start_value: float, end_value: float) -> float:
        """Calculate logarithmic return"""
        if start_value <= 0 or end_value <= 0:
            raise ValueError("Values must be positive for log returns")
        return np.log(end_value / start_value)
    
    def calculate_time_weighted_return(self, values: List[float], 
                                     cash_flows: List[float],
                                     dates: List[date]) -> float:
        """Calculate time-weighted return accounting for cash flows"""
        if len(values) != len(cash_flows) or len(values) != len(dates):
            raise ValueError("All input lists must have same length")
        
        # Validate temporal access
        for date_val in dates:
            if not self.temporal_validator.validate_calculation_period(date_val, date_val):
                raise ValueError(f"Cannot access future date: {date_val}")
        
        # Simplified TWR calculation
        periods = []
        for i in range(1, len(values)):
            period_return = (values[i] - cash_flows[i]) / (values[i-1] + cash_flows[i-1])
            periods.append(1 + period_return)
        
        if not periods:
            return 0.0
        
        twr = np.prod(periods) - 1
        return twr
    
    def annualize_return(self, return_value: float, periods_per_year: float) -> float:
        """Annualize return based on period frequency"""
        return (1 + return_value) ** periods_per_year - 1


class BenchmarkManager:
    """Manages benchmark data and calculations"""
    
    def __init__(self, temporal_validator: TemporalValidator):
        self.temporal_validator = temporal_validator
        self.benchmark_data: Dict[str, pd.DataFrame] = {}
    
    def add_benchmark(self, name: str, data: pd.DataFrame) -> None:
        """Add benchmark data"""
        # Validate all dates are not in future
        for date_val in data.index:
            if isinstance(date_val, pd.Timestamp):
                date_val = date_val.date()
            if not self.temporal_validator.validate_calculation_period(date_val, date_val):
                raise ValueError(f"Benchmark data contains future date: {date_val}")
        
        self.benchmark_data[name] = data.copy()
    
    def get_benchmark_return(self, benchmark_name: str, start_date: date, end_date: date) -> float:
        """Get benchmark return for period"""
        if benchmark_name not in self.benchmark_data:
            raise ValueError(f"Benchmark {benchmark_name} not found")
        
        # Validate temporal access
        if not self.temporal_validator.validate_calculation_period(start_date, end_date):
            raise ValueError("Cannot calculate returns for future period")
        
        data = self.benchmark_data[benchmark_name]
        
        # Get values for period
        start_value = data.loc[start_date, 'value'] if start_date in data.index else None
        end_value = data.loc[end_date, 'value'] if end_date in data.index else None
        
        if start_value is None or end_value is None:
            raise ValueError("Benchmark data not available for requested period")
        
        return (end_value - start_value) / start_value


class AttributionEngine:
    """Performance attribution calculation engine"""
    
    def __init__(self, temporal_validator: TemporalValidator):
        self.temporal_validator = temporal_validator
    
    def calculate_brinson_attribution(self, 
                                    portfolio_weights: Dict[str, float],
                                    benchmark_weights: Dict[str, float],
                                    portfolio_returns: Dict[str, float],
                                    benchmark_returns: Dict[str, float],
                                    calculation_date: date) -> Attribution:
        """Calculate Brinson attribution"""
        
        # Validate temporal access
        if not self.temporal_validator.validate_calculation_period(calculation_date, calculation_date):
            raise ValueError("Cannot calculate attribution for future date")
        
        allocation_effect = 0.0
        selection_effect = 0.0
        interaction_effect = 0.0
        breakdown = {}
        
        # Get all sectors
        all_sectors = set(portfolio_weights.keys()) | set(benchmark_weights.keys())
        
        for sector in all_sectors:
            pw = portfolio_weights.get(sector, 0.0)  # Portfolio weight
            bw = benchmark_weights.get(sector, 0.0)  # Benchmark weight
            pr = portfolio_returns.get(sector, 0.0)  # Portfolio return
            br = benchmark_returns.get(sector, 0.0)  # Benchmark return
            
            # Brinson attribution formulas
            sector_allocation = (pw - bw) * br
            sector_selection = bw * (pr - br)
            sector_interaction = (pw - bw) * (pr - br)
            
            allocation_effect += sector_allocation
            selection_effect += sector_selection
            interaction_effect += sector_interaction
            
            breakdown[sector] = {
                'allocation': sector_allocation,
                'selection': sector_selection,
                'interaction': sector_interaction
            }
        
        total_effect = allocation_effect + selection_effect + interaction_effect
        
        return Attribution(
            date=calculation_date,
            method=AttributionMethod.BRINSON,
            allocation_effect=allocation_effect,
            selection_effect=selection_effect,
            interaction_effect=interaction_effect,
            total_effect=total_effect,
            breakdown=breakdown
        )
    
    def calculate_factor_attribution(self,
                                   factor_exposures: Dict[str, float],
                                   factor_returns: Dict[str, float],
                                   calculation_date: date) -> Attribution:
        """Calculate factor-based attribution"""
        
        # Validate temporal access
        if not self.temporal_validator.validate_calculation_period(calculation_date, calculation_date):
            raise ValueError("Cannot calculate attribution for future date")
        
        factor_contributions = {}
        total_factor_return = 0.0
        
        for factor, exposure in factor_exposures.items():
            if factor in factor_returns:
                contribution = exposure * factor_returns[factor]
                factor_contributions[factor] = contribution
                total_factor_return += contribution
        
        return Attribution(
            date=calculation_date,
            method=AttributionMethod.FACTOR,
            allocation_effect=0.0,  # Not applicable for factor attribution
            selection_effect=total_factor_return,
            interaction_effect=0.0,
            total_effect=total_factor_return,
            breakdown=factor_contributions
        )


class RiskCalculator:
    """Risk metric calculation with temporal validation"""
    
    def __init__(self, temporal_validator: TemporalValidator):
        self.temporal_validator = temporal_validator
    
    def calculate_volatility(self, returns: List[float], annualize: bool = True) -> float:
        """Calculate return volatility"""
        if len(returns) < 2:
            return 0.0
        
        vol = np.std(returns, ddof=1)
        if annualize:
            vol *= np.sqrt(252)  # Assuming daily returns
        
        return vol
    
    def calculate_sharpe_ratio(self, returns: List[float], risk_free_rate: float = 0.0) -> float:
        """Calculate Sharpe ratio"""
        if len(returns) < 2:
            return 0.0
        
        excess_returns = [r - risk_free_rate/252 for r in returns]  # Daily risk-free rate
        mean_excess = np.mean(excess_returns)
        vol_excess = np.std(excess_returns, ddof=1)
        
        if vol_excess == 0:
            return 0.0
        
        return (mean_excess / vol_excess) * np.sqrt(252)  # Annualized
    
    def calculate_sortino_ratio(self, returns: List[float], target_return: float = 0.0) -> float:
        """Calculate Sortino ratio (downside deviation)"""
        if len(returns) < 2:
            return 0.0
        
        excess_returns = [r - target_return/252 for r in returns]
        downside_returns = [min(0, r) for r in excess_returns]
        
        mean_excess = np.mean(excess_returns)
        downside_vol = np.std(downside_returns, ddof=1)
        
        if downside_vol == 0:
            return 0.0
        
        return (mean_excess / downside_vol) * np.sqrt(252)  # Annualized
    
    def calculate_max_drawdown(self, values: List[float]) -> float:
        """Calculate maximum drawdown"""
        if len(values) < 2:
            return 0.0
        
        peak = values[0]
        max_dd = 0.0
        
        for value in values[1:]:
            if value > peak:
                peak = value
            else:
                drawdown = (peak - value) / peak
                max_dd = max(max_dd, drawdown)
        
        return max_dd
    
    def calculate_var(self, returns: List[float], confidence_level: float = 0.95) -> float:
        """Calculate Value at Risk"""
        if len(returns) < 10:  # Need sufficient data
            return 0.0
        
        return np.percentile(returns, (1 - confidence_level) * 100)
    
    def calculate_beta(self, portfolio_returns: List[float], 
                      benchmark_returns: List[float]) -> float:
        """Calculate portfolio beta"""
        if len(portfolio_returns) != len(benchmark_returns) or len(portfolio_returns) < 10:
            return 1.0
        
        covariance = np.cov(portfolio_returns, benchmark_returns)[0, 1]
        benchmark_variance = np.var(benchmark_returns, ddof=1)
        
        if benchmark_variance == 0:
            return 1.0
        
        return covariance / benchmark_variance
    
    def calculate_alpha(self, portfolio_returns: List[float],
                       benchmark_returns: List[float],
                       risk_free_rate: float = 0.0) -> float:
        """Calculate Jensen's alpha"""
        if len(portfolio_returns) != len(benchmark_returns) or len(portfolio_returns) < 10:
            return 0.0
        
        beta = self.calculate_beta(portfolio_returns, benchmark_returns)
        
        portfolio_mean = np.mean(portfolio_returns) * 252  # Annualized
        benchmark_mean = np.mean(benchmark_returns) * 252  # Annualized
        
        alpha = portfolio_mean - (risk_free_rate + beta * (benchmark_mean - risk_free_rate))
        
        return alpha
    
    def calculate_tracking_error(self, portfolio_returns: List[float],
                               benchmark_returns: List[float]) -> float:
        """Calculate tracking error"""
        if len(portfolio_returns) != len(benchmark_returns) or len(portfolio_returns) < 2:
            return 0.0
        
        active_returns = [p - b for p, b in zip(portfolio_returns, benchmark_returns)]
        return np.std(active_returns, ddof=1) * np.sqrt(252)  # Annualized
    
    def calculate_information_ratio(self, portfolio_returns: List[float],
                                  benchmark_returns: List[float]) -> float:
        """Calculate information ratio"""
        if len(portfolio_returns) != len(benchmark_returns) or len(portfolio_returns) < 2:
            return 0.0
        
        active_returns = [p - b for p, b in zip(portfolio_returns, benchmark_returns)]
        mean_active = np.mean(active_returns) * 252  # Annualized
        tracking_error = self.calculate_tracking_error(portfolio_returns, benchmark_returns)
        
        if tracking_error == 0:
            return 0.0
        
        return mean_active / tracking_error


class PerformanceTracker:
    """
    Comprehensive performance tracking and attribution system
    
    Provides point-in-time performance measurement with strict temporal validation
    and comprehensive attribution analysis across multiple methodologies.
    """
    
    def __init__(self, current_time: datetime):
        self.temporal_validator = TemporalValidator(current_time)
        self.return_calculator = ReturnCalculator(self.temporal_validator)
        self.benchmark_manager = BenchmarkManager(self.temporal_validator)
        self.attribution_engine = AttributionEngine(self.temporal_validator)
        self.risk_calculator = RiskCalculator(self.temporal_validator)
        
        self.performance_history: List[Return] = []
        self.attribution_history: List[Attribution] = []
    
    def update_current_time(self, new_time: datetime) -> None:
        """Update current time for temporal validation"""
        if new_time < self.temporal_validator.current_time:
            raise ValueError("Time cannot move backwards")
        self.temporal_validator.current_time = new_time
    
    def record_performance(self, return_data: Return) -> None:
        """Record performance data point"""
        # Validate temporal consistency
        return_datetime = datetime.combine(return_data.date, datetime.min.time())
        if not self.temporal_validator.validate_data_access(return_datetime):
            raise ValueError(f"Cannot record future performance: {return_data.date}")
        
        self.performance_history.append(return_data)
    
    def calculate_period_performance(self, start_date: date, end_date: date,
                                   benchmark_name: str = "benchmark") -> PerformanceSummary:
        """Calculate performance for specified period"""
        
        # Validate period
        if not self.temporal_validator.validate_calculation_period(start_date, end_date):
            raise ValueError("Cannot calculate performance for future period")
        
        # Get returns for period
        period_returns = [r for r in self.performance_history 
                         if start_date <= r.date <= end_date]
        
        if not period_returns:
            raise ValueError("No performance data available for period")
        
        # Calculate metrics
        portfolio_returns = [r.portfolio_return for r in period_returns]
        benchmark_returns = [r.benchmark_return for r in period_returns]
        
        total_return = np.prod([1 + r for r in portfolio_returns]) - 1
        benchmark_total = np.prod([1 + r for r in benchmark_returns]) - 1
        active_return = total_return - benchmark_total
        
        # Annualize returns
        days = (end_date - start_date).days
        periods_per_year = 365.25 / days if days > 0 else 1
        annualized_return = self.return_calculator.annualize_return(total_return, periods_per_year)
        
        # Calculate risk metrics
        risk_metrics = RiskMetrics(
            volatility=self.risk_calculator.calculate_volatility(portfolio_returns),
            sharpe_ratio=self.risk_calculator.calculate_sharpe_ratio(portfolio_returns),
            sortino_ratio=self.risk_calculator.calculate_sortino_ratio(portfolio_returns),
            max_drawdown=self.risk_calculator.calculate_max_drawdown(
                np.cumprod([1 + r for r in portfolio_returns]).tolist()
            ),
            var_95=self.risk_calculator.calculate_var(portfolio_returns, 0.95),
            var_99=self.risk_calculator.calculate_var(portfolio_returns, 0.99),
            beta=self.risk_calculator.calculate_beta(portfolio_returns, benchmark_returns),
            alpha=self.risk_calculator.calculate_alpha(portfolio_returns, benchmark_returns),
            tracking_error=self.risk_calculator.calculate_tracking_error(portfolio_returns, benchmark_returns),
            information_ratio=self.risk_calculator.calculate_information_ratio(portfolio_returns, benchmark_returns)
        )
        
        # Get attributions for period
        period_attributions = [a for a in self.attribution_history 
                             if start_date <= a.date <= end_date]
        
        return PerformanceSummary(
            period=PerformancePeriod.DAILY,  # Would be determined by period length
            start_date=start_date,
            end_date=end_date,
            total_return=total_return,
            annualized_return=annualized_return,
            benchmark_return=benchmark_total,
            active_return=active_return,
            risk_metrics=risk_metrics,
            attributions=period_attributions
        )
    
    def calculate_attribution(self, attribution_method: AttributionMethod,
                            calculation_date: date, **kwargs) -> Attribution:
        """Calculate performance attribution"""
        
        if attribution_method == AttributionMethod.BRINSON:
            attribution = self.attribution_engine.calculate_brinson_attribution(
                portfolio_weights=kwargs.get('portfolio_weights', {}),
                benchmark_weights=kwargs.get('benchmark_weights', {}),
                portfolio_returns=kwargs.get('portfolio_returns', {}),
                benchmark_returns=kwargs.get('benchmark_returns', {}),
                calculation_date=calculation_date
            )
        elif attribution_method == AttributionMethod.FACTOR:
            attribution = self.attribution_engine.calculate_factor_attribution(
                factor_exposures=kwargs.get('factor_exposures', {}),
                factor_returns=kwargs.get('factor_returns', {}),
                calculation_date=calculation_date
            )
        else:
            raise ValueError(f"Attribution method {attribution_method} not implemented")
        
        self.attribution_history.append(attribution)
        return attribution
    
    def get_performance_summary(self, period: PerformancePeriod) -> Dict[str, any]:
        """Get performance summary for standard periods"""
        end_date = self.temporal_validator.current_time.date()
        
        if period == PerformancePeriod.DAILY:
            start_date = end_date
        elif period == PerformancePeriod.WEEKLY:
            start_date = end_date - pd.Timedelta(days=7)
        elif period == PerformancePeriod.MONTHLY:
            start_date = end_date - pd.Timedelta(days=30)
        elif period == PerformancePeriod.QUARTERLY:
            start_date = end_date - pd.Timedelta(days=90)
        elif period == PerformancePeriod.YEARLY:
            start_date = end_date - pd.Timedelta(days=365)
        else:  # INCEPTION
            if self.performance_history:
                start_date = self.performance_history[0].date
            else:
                start_date = end_date
        
        try:
            summary = self.calculate_period_performance(start_date, end_date)
            return {
                'period': period.value,
                'summary': summary,
                'status': 'SUCCESS'
            }
        except Exception as e:
            return {
                'period': period.value,
                'error': str(e),
                'status': 'ERROR'
            }