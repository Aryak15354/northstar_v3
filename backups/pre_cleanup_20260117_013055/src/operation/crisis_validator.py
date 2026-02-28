"""
Crisis Validator - Validates system performance during historical market crises.

This module implements comprehensive crisis period testing including:
- 2008 Financial Crisis validation
- 2020 COVID market crash validation  
- 2000 Dot-com bubble validation
- Crisis-specific backtesting and risk analysis
"""

import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path

from .base_types import (
    CrisisValidationResult, CrisisPeriod, RiskBreach, 
    Alert, AlertLevel, BacktestConfig, OperationConfig
)


class CrisisValidator:
    """
    Validates system performance during historical market crises.
    
    Tests the Northstar V3 system against major historical crisis periods
    to ensure robustness during extreme market conditions.
    """
    
    # Crisis period definitions
    CRISIS_PERIODS = {
        "2008_financial_crisis": CrisisPeriod(
            name="2008_financial_crisis",
            start_date=datetime(2007, 10, 1),
            end_date=datetime(2009, 3, 31),
            severity="extreme",
            characteristics=["credit_crunch", "liquidity_crisis", "volatility_spike", "correlation_breakdown"],
            description="Global financial crisis triggered by subprime mortgage collapse"
        ),
        "2020_covid_crash": CrisisPeriod(
            name="2020_covid_crash", 
            start_date=datetime(2020, 2, 1),
            end_date=datetime(2020, 5, 31),
            severity="extreme",
            characteristics=["pandemic_shock", "circuit_breakers", "policy_response", "volatility_spike"],
            description="COVID-19 pandemic market crash and recovery"
        ),
        "2000_dotcom_bubble": CrisisPeriod(
            name="2000_dotcom_bubble",
            start_date=datetime(2000, 3, 1), 
            end_date=datetime(2002, 10, 31),
            severity="high",
            characteristics=["tech_bubble", "valuation_reset", "recession", "sector_rotation"],
            description="Dot-com bubble burst and subsequent recession"
        )
    }
    
    # Performance thresholds for crisis validation
    CRISIS_THRESHOLDS = {
        "max_drawdown_limit": 0.20,      # 20% max drawdown during crisis
        "min_sharpe_ratio": 0.0,         # Minimum Sharpe ratio during crisis
        "max_var_breaches": 10,          # Maximum VaR breaches allowed
        "min_recovery_days": 30,         # Minimum days to recover from drawdown
        "max_volatility": 0.40,          # Maximum volatility during crisis
        "min_hit_rate": 0.45             # Minimum hit rate during crisis
    }
    
    def __init__(self, config: Optional[OperationConfig] = None):
        """Initialize the crisis validator."""
        self.config = config or OperationConfig()
        self.logger = logging.getLogger(__name__)
        self.validation_results: Dict[str, CrisisValidationResult] = {}
        
        self.logger.info("Crisis Validator initialized")
        self.logger.info(f"Configured for {len(self.CRISIS_PERIODS)} crisis periods")
    
    def validate_all_crisis_periods(self) -> List[CrisisValidationResult]:
        """
        Validate system performance across all defined crisis periods.
        
        Returns:
            List[CrisisValidationResult]: Results for each crisis period
        """
        self.logger.info("Starting validation across all crisis periods")
        
        results = []
        for period_name, period in self.CRISIS_PERIODS.items():
            self.logger.info(f"Validating crisis period: {period_name}")
            
            try:
                result = self.validate_crisis_period(period)
                results.append(result)
                self.validation_results[period_name] = result
                
                # Log validation outcome
                status = "PASSED" if result.stress_test_passed else "FAILED"
                self.logger.info(f"Crisis validation {status} for {period_name}: "
                               f"Return={result.total_return:.2%}, "
                               f"Drawdown={result.max_drawdown:.2%}, "
                               f"Sharpe={result.sharpe_ratio:.2f}")
                
            except Exception as e:
                self.logger.error(f"Crisis validation failed for {period_name}: {str(e)}")
                # Create failed result
                failed_result = CrisisValidationResult(
                    crisis_period=period_name,
                    start_date=period.start_date,
                    end_date=period.end_date,
                    total_return=0.0,
                    max_drawdown=1.0,  # Worst case
                    volatility=1.0,    # Worst case
                    sharpe_ratio=-999, # Worst case
                    var_breach_count=999,
                    stress_test_passed=False
                )
                failed_result.additional_metrics["error"] = str(e)
                results.append(failed_result)
        
        self.logger.info(f"Crisis validation completed for {len(results)} periods")
        return results
    
    def validate_crisis_period(self, period: CrisisPeriod) -> CrisisValidationResult:
        """
        Validate system performance during a specific crisis period.
        
        Args:
            period: Crisis period definition
            
        Returns:
            CrisisValidationResult: Validation results for the period
        """
        self.logger.info(f"Starting crisis validation for {period.name} "
                        f"({period.start_date.date()} to {period.end_date.date()})")
        
        # Create backtest configuration for crisis period
        backtest_config = BacktestConfig(
            start_date=period.start_date,
            end_date=period.end_date,
            initial_capital=1000000.0,
            rebalance_frequency="weekly"
        )
        
        # Run crisis-specific backtest
        backtest_results = self._run_crisis_backtest(period, backtest_config)
        
        # Calculate crisis-specific metrics
        performance_metrics = self._calculate_crisis_metrics(backtest_results, period)
        
        # Analyze risk during crisis
        risk_analysis = self._analyze_crisis_risk(backtest_results, period)
        
        # Validate against thresholds
        validation_passed = self._validate_crisis_thresholds(performance_metrics, risk_analysis)
        
        # Create validation result
        result = CrisisValidationResult(
            crisis_period=period.name,
            start_date=period.start_date,
            end_date=period.end_date,
            total_return=performance_metrics["total_return"],
            max_drawdown=performance_metrics["max_drawdown"],
            volatility=performance_metrics["volatility"],
            sharpe_ratio=performance_metrics["sharpe_ratio"],
            var_breach_count=risk_analysis["var_breach_count"],
            risk_limit_breaches=risk_analysis["risk_breaches"],
            recovery_time_days=performance_metrics["recovery_time_days"],
            stress_test_passed=validation_passed,
            additional_metrics=performance_metrics
        )
        
        self.logger.info(f"Crisis validation completed for {period.name}: "
                        f"{'PASSED' if validation_passed else 'FAILED'}")
        
        return result
    
    def validate_2008_crisis(self) -> CrisisValidationResult:
        """Validate system performance during 2008 financial crisis."""
        return self.validate_crisis_period(self.CRISIS_PERIODS["2008_financial_crisis"])
    
    def validate_2020_covid_crash(self) -> CrisisValidationResult:
        """Validate system performance during 2020 COVID crash."""
        return self.validate_crisis_period(self.CRISIS_PERIODS["2020_covid_crash"])
    
    def validate_2000_dotcom_bubble(self) -> CrisisValidationResult:
        """Validate system performance during 2000 dot-com bubble."""
        return self.validate_crisis_period(self.CRISIS_PERIODS["2000_dotcom_bubble"])
    
    def generate_crisis_report(self, results: List[CrisisValidationResult]) -> Dict[str, Any]:
        """
        Generate comprehensive crisis validation report.
        
        Args:
            results: List of crisis validation results
            
        Returns:
            Dict[str, Any]: Comprehensive crisis report
        """
        self.logger.info("Generating comprehensive crisis validation report")
        
        # Aggregate statistics
        total_periods = len(results)
        passed_periods = sum(1 for r in results if r.stress_test_passed)
        pass_rate = passed_periods / total_periods if total_periods > 0 else 0
        
        # Performance aggregates
        avg_return = np.mean([r.total_return for r in results])
        avg_drawdown = np.mean([r.max_drawdown for r in results])
        avg_volatility = np.mean([r.volatility for r in results])
        avg_sharpe = np.mean([r.sharpe_ratio for r in results])
        total_var_breaches = sum(r.var_breach_count for r in results)
        
        # Risk analysis
        total_risk_breaches = sum(len(r.risk_limit_breaches) for r in results)
        avg_recovery_time = np.mean([r.recovery_time_days for r in results])
        
        # Enhanced risk assessment based on multiple factors
        high_drawdown_count = sum(1 for r in results if r.max_drawdown > 0.25)
        high_var_breach_count = sum(1 for r in results if r.var_breach_count > 15)
        
        # Risk assessment logic
        if total_risk_breaches >= 15 or high_drawdown_count >= len(results) * 0.5 or total_var_breaches > 50:
            risk_assessment = "HIGH"
        elif total_risk_breaches >= 5 or high_var_breach_count > 0 or total_var_breaches > 20:
            risk_assessment = "MODERATE"
        else:
            risk_assessment = "LOW"
        
        # Crisis-specific insights
        crisis_insights = self._generate_crisis_insights(results)
        
        report = {
            "summary": {
                "total_crisis_periods": total_periods,
                "periods_passed": passed_periods,
                "pass_rate": pass_rate,
                "overall_assessment": "ROBUST" if pass_rate >= 0.8 else "NEEDS_IMPROVEMENT"
            },
            "performance_metrics": {
                "average_return": avg_return,
                "average_max_drawdown": avg_drawdown,
                "average_volatility": avg_volatility,
                "average_sharpe_ratio": avg_sharpe,
                "total_var_breaches": total_var_breaches
            },
            "risk_analysis": {
                "total_risk_breaches": total_risk_breaches,
                "average_recovery_time_days": avg_recovery_time,
                "risk_assessment": risk_assessment
            },
            "crisis_specific_results": {
                result.crisis_period: {
                    "passed": result.stress_test_passed,
                    "return": result.total_return,
                    "max_drawdown": result.max_drawdown,
                    "sharpe_ratio": result.sharpe_ratio,
                    "var_breaches": result.var_breach_count,
                    "recovery_days": result.recovery_time_days
                }
                for result in results
            },
            "insights_and_recommendations": crisis_insights,
            "generated_at": datetime.now().isoformat()
        }
        
        self.logger.info(f"Crisis report generated: {pass_rate:.1%} pass rate, "
                        f"{total_var_breaches} VaR breaches")
        
        return report
    
    def _run_crisis_backtest(self, period: CrisisPeriod, config: BacktestConfig) -> Dict[str, Any]:
        """
        Run crisis-specific backtesting.
        
        This would integrate with the actual Northstar V3 backtesting engine.
        For now, we simulate realistic crisis performance.
        """
        self.logger.debug(f"Running crisis backtest for {period.name}")
        
        # Simulate crisis-appropriate performance based on historical patterns
        crisis_performance = self._simulate_crisis_performance(period)
        
        # Mock backtest results structure
        results = {
            "period": period,
            "daily_returns": crisis_performance["daily_returns"],
            "portfolio_values": crisis_performance["portfolio_values"],
            "positions": crisis_performance["positions"],
            "risk_metrics": crisis_performance["risk_metrics"],
            "execution_stats": crisis_performance["execution_stats"]
        }
        
        return results
    
    def _simulate_crisis_performance(self, period: CrisisPeriod) -> Dict[str, Any]:
        """
        Simulate realistic crisis performance based on historical patterns.
        
        This creates realistic performance data that reflects the characteristics
        of each crisis period for testing purposes.
        """
        # Calculate number of trading days
        trading_days = (period.end_date - period.start_date).days
        dates = pd.date_range(period.start_date, period.end_date, freq='D')
        
        # Crisis-specific parameters
        if period.name == "2008_financial_crisis":
            # Severe initial decline, slow recovery
            base_return = -0.0002  # Slight negative drift
            volatility = 0.025     # High volatility
            max_decline = -0.25    # 25% peak decline
            recovery_factor = 0.3  # Slow recovery
            
        elif period.name == "2020_covid_crash":
            # Sharp initial decline, rapid recovery
            base_return = 0.0001   # Slight positive drift
            volatility = 0.030     # Very high volatility
            max_decline = -0.15    # 15% peak decline
            recovery_factor = 0.8  # Fast recovery
            
        elif period.name == "2000_dotcom_bubble":
            # Prolonged decline, gradual recovery
            base_return = -0.0001  # Negative drift
            volatility = 0.020     # Moderate volatility
            max_decline = -0.30    # 30% peak decline
            recovery_factor = 0.2  # Very slow recovery
            
        else:
            # Default crisis parameters
            base_return = -0.0001
            volatility = 0.025
            max_decline = -0.20
            recovery_factor = 0.5
        
        # Generate daily returns with crisis pattern
        np.random.seed(42)  # For reproducible results
        random_returns = np.random.normal(base_return, volatility, len(dates))
        
        # Apply crisis pattern (initial decline, then recovery)
        crisis_pattern = self._generate_crisis_pattern(len(dates), max_decline, recovery_factor)
        daily_returns = random_returns + crisis_pattern
        
        # Calculate portfolio values
        initial_value = 1000000.0
        portfolio_values = [initial_value]
        for ret in daily_returns:
            portfolio_values.append(portfolio_values[-1] * (1 + ret))
        
        # Generate mock positions and risk metrics
        positions = self._generate_mock_positions(dates)
        risk_metrics = self._generate_mock_risk_metrics(daily_returns, portfolio_values)
        execution_stats = self._generate_mock_execution_stats(len(dates))
        
        return {
            "daily_returns": pd.Series(daily_returns, index=dates),
            "portfolio_values": pd.Series(portfolio_values[1:], index=dates),
            "positions": positions,
            "risk_metrics": risk_metrics,
            "execution_stats": execution_stats
        }
    
    def _generate_crisis_pattern(self, num_days: int, max_decline: float, recovery_factor: float) -> np.ndarray:
        """Generate crisis-specific return pattern."""
        pattern = np.zeros(num_days)
        
        # Crisis typically has 3 phases: decline, bottom, recovery
        decline_days = int(num_days * 0.3)
        bottom_days = int(num_days * 0.2)
        recovery_days = num_days - decline_days - bottom_days
        
        # Decline phase - accelerating negative returns
        decline_pattern = np.linspace(0, max_decline, decline_days)
        decline_returns = np.diff(np.concatenate([[0], decline_pattern]))
        
        # Bottom phase - high volatility around bottom
        bottom_returns = np.random.normal(0, abs(max_decline) * 0.1, bottom_days)
        
        # Recovery phase - gradual positive returns
        recovery_total = abs(max_decline) * recovery_factor
        recovery_pattern = np.linspace(0, recovery_total, recovery_days)
        recovery_returns = np.diff(np.concatenate([[0], recovery_pattern]))
        
        # Combine phases
        pattern[:decline_days] = decline_returns
        pattern[decline_days:decline_days + bottom_days] = bottom_returns
        pattern[decline_days + bottom_days:] = recovery_returns
        
        return pattern
    
    def _generate_mock_positions(self, dates: pd.DatetimeIndex) -> pd.DataFrame:
        """Generate mock position data for testing."""
        # Simple mock positions
        symbols = ['RELIANCE', 'TCS', 'INFY', 'HDFC', 'ICICI']
        positions_data = []
        
        for date in dates[::5]:  # Sample every 5 days
            for symbol in symbols:
                positions_data.append({
                    'date': date,
                    'symbol': symbol,
                    'quantity': np.random.randint(100, 1000),
                    'price': np.random.uniform(100, 2000),
                    'weight': np.random.uniform(0.05, 0.25)
                })
        
        return pd.DataFrame(positions_data)
    
    def _generate_mock_risk_metrics(self, returns: np.ndarray, values: List[float]) -> Dict[str, Any]:
        """Generate mock risk metrics for testing."""
        return {
            "var_95": np.percentile(returns, 5),
            "var_99": np.percentile(returns, 1),
            "expected_shortfall": np.mean(returns[returns <= np.percentile(returns, 5)]),
            "max_drawdown": self._calculate_max_drawdown(values),
            "volatility": np.std(returns) * np.sqrt(252),
            "skewness": float(pd.Series(returns).skew()),
            "kurtosis": float(pd.Series(returns).kurtosis())
        }
    
    def _generate_mock_execution_stats(self, num_days: int) -> Dict[str, Any]:
        """Generate mock execution statistics."""
        return {
            "total_trades": np.random.randint(num_days * 2, num_days * 5),
            "avg_trade_size": np.random.uniform(50000, 200000),
            "execution_cost_bps": np.random.uniform(8, 15),
            "market_impact_bps": np.random.uniform(2, 8),
            "fill_rate": np.random.uniform(0.95, 0.99)
        }
    
    def _calculate_crisis_metrics(self, backtest_results: Dict[str, Any], period: CrisisPeriod) -> Dict[str, float]:
        """Calculate crisis-specific performance metrics."""
        returns = backtest_results["daily_returns"]
        values = backtest_results["portfolio_values"]
        
        # Basic performance metrics
        total_return = (values.iloc[-1] / values.iloc[0]) - 1
        volatility = returns.std() * np.sqrt(252)
        sharpe_ratio = (returns.mean() * 252) / (volatility) if volatility > 0 else 0
        
        # Crisis-specific metrics
        max_drawdown = self._calculate_max_drawdown(values.values)
        recovery_time = self._calculate_recovery_time(values.values)
        
        # Additional crisis metrics
        downside_deviation = self._calculate_downside_deviation(returns)
        sortino_ratio = (returns.mean() * 252) / downside_deviation if downside_deviation > 0 else 0
        calmar_ratio = (returns.mean() * 252) / abs(max_drawdown) if max_drawdown != 0 else 0
        
        return {
            "total_return": total_return,
            "volatility": volatility,
            "sharpe_ratio": sharpe_ratio,
            "max_drawdown": max_drawdown,
            "recovery_time_days": recovery_time,
            "downside_deviation": downside_deviation,
            "sortino_ratio": sortino_ratio,
            "calmar_ratio": calmar_ratio,
            "worst_day_return": returns.min(),
            "best_day_return": returns.max(),
            "negative_days_pct": (returns < 0).sum() / len(returns)
        }
    
    def _analyze_crisis_risk(self, backtest_results: Dict[str, Any], period: CrisisPeriod) -> Dict[str, Any]:
        """Analyze risk characteristics during crisis period."""
        returns = backtest_results["daily_returns"]
        risk_metrics = backtest_results["risk_metrics"]
        
        # VaR breach analysis
        var_95 = risk_metrics["var_95"]
        var_breaches = int((returns < var_95).sum())  # Ensure integer type
        
        # Risk limit breaches (mock for now)
        risk_breaches = []
        
        # Check for significant drawdown breaches
        if risk_metrics["max_drawdown"] > self.CRISIS_THRESHOLDS["max_drawdown_limit"]:
            breach = RiskBreach(
                timestamp=period.start_date,
                limit_type="max_drawdown",
                limit_value=self.CRISIS_THRESHOLDS["max_drawdown_limit"],
                actual_value=risk_metrics["max_drawdown"],
                severity="high",
                component="portfolio"
            )
            risk_breaches.append(breach)
        
        # Check for volatility breaches
        if risk_metrics["volatility"] > self.CRISIS_THRESHOLDS["max_volatility"]:
            breach = RiskBreach(
                timestamp=period.start_date,
                limit_type="volatility",
                limit_value=self.CRISIS_THRESHOLDS["max_volatility"],
                actual_value=risk_metrics["volatility"],
                severity="medium",
                component="portfolio"
            )
            risk_breaches.append(breach)
        
        return {
            "var_breach_count": var_breaches,
            "risk_breaches": risk_breaches,
            "tail_risk_metrics": {
                "var_95": var_95,
                "var_99": risk_metrics["var_99"],
                "expected_shortfall": risk_metrics["expected_shortfall"],
                "skewness": risk_metrics["skewness"],
                "kurtosis": risk_metrics["kurtosis"]
            }
        }
    
    def _validate_crisis_thresholds(self, performance_metrics: Dict[str, float], risk_analysis: Dict[str, Any]) -> bool:
        """Validate performance against crisis thresholds."""
        validations = []
        
        # Check maximum drawdown
        validations.append(performance_metrics["max_drawdown"] <= self.CRISIS_THRESHOLDS["max_drawdown_limit"])
        
        # Check Sharpe ratio
        validations.append(performance_metrics["sharpe_ratio"] >= self.CRISIS_THRESHOLDS["min_sharpe_ratio"])
        
        # Check VaR breaches
        validations.append(risk_analysis["var_breach_count"] <= self.CRISIS_THRESHOLDS["max_var_breaches"])
        
        # Check volatility
        validations.append(performance_metrics["volatility"] <= self.CRISIS_THRESHOLDS["max_volatility"])
        
        # Check recovery time
        validations.append(performance_metrics["recovery_time_days"] >= self.CRISIS_THRESHOLDS["min_recovery_days"])
        
        # All validations must pass
        return all(validations)
    
    def _calculate_max_drawdown(self, values: np.ndarray) -> float:
        """Calculate maximum drawdown from portfolio values."""
        peak = np.maximum.accumulate(values)
        drawdown = (values - peak) / peak
        return float(abs(drawdown.min()))  # Return positive value
    
    def _calculate_recovery_time(self, values: np.ndarray) -> int:
        """Calculate time to recover from maximum drawdown."""
        peak = np.maximum.accumulate(values)
        drawdown = (values - peak) / peak
        
        # Find the point of maximum drawdown
        max_dd_idx = np.argmin(drawdown)
        
        # Find when portfolio recovers to previous peak
        recovery_idx = max_dd_idx
        max_dd_peak = peak[max_dd_idx]
        
        for i in range(max_dd_idx + 1, len(values)):
            if values[i] >= max_dd_peak:
                recovery_idx = i
                break
        
        return int(recovery_idx - max_dd_idx)  # Ensure integer return
    
    def _calculate_downside_deviation(self, returns: pd.Series) -> float:
        """Calculate downside deviation (volatility of negative returns)."""
        negative_returns = returns[returns < 0]
        if len(negative_returns) == 0:
            return 0.0
        return float(negative_returns.std() * np.sqrt(252))
    
    def _generate_crisis_insights(self, results: List[CrisisValidationResult]) -> Dict[str, Any]:
        """Generate insights and recommendations from crisis validation results."""
        insights = {
            "key_findings": [],
            "risk_concerns": [],
            "recommendations": [],
            "strengths": []
        }
        
        # Analyze results for insights
        failed_periods = [r for r in results if not r.stress_test_passed]
        high_drawdown_periods = [r for r in results if r.max_drawdown > 0.15]
        low_sharpe_periods = [r for r in results if r.sharpe_ratio < 0.0]
        
        # Key findings
        if len(failed_periods) == 0:
            insights["key_findings"].append("System passed all crisis validations - demonstrates strong resilience")
        else:
            insights["key_findings"].append(f"System failed {len(failed_periods)} out of {len(results)} crisis periods")
        
        # Risk concerns
        if high_drawdown_periods:
            insights["risk_concerns"].append(f"High drawdowns observed in {len(high_drawdown_periods)} periods")
        
        if low_sharpe_periods:
            insights["risk_concerns"].append(f"Negative risk-adjusted returns in {len(low_sharpe_periods)} periods")
        
        # Recommendations
        if failed_periods:
            insights["recommendations"].append("Review risk management parameters for crisis periods")
            insights["recommendations"].append("Consider implementing crisis-specific position sizing")
        
        if high_drawdown_periods:
            insights["recommendations"].append("Implement enhanced drawdown controls")
        
        # Strengths
        passed_periods = [r for r in results if r.stress_test_passed]
        if passed_periods:
            avg_recovery = np.mean([r.recovery_time_days for r in passed_periods])
            insights["strengths"].append(f"Average recovery time of {avg_recovery:.0f} days in successful periods")
        
        return insights