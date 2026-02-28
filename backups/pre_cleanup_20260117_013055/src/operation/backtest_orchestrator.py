"""
Backtest Orchestrator - Coordinates comprehensive backtesting across multiple scenarios.

This module implements comprehensive backtesting functionality including:
- Multi-year historical simulations
- Simultaneous intelligence engine coordination
- Portfolio construction and risk management validation
- Performance attribution and reporting
- Diagnostic information provision
"""

import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os

from .base_types import (
    BacktestResult, BacktestConfig, PerformanceMetrics, Alert, AlertLevel
)


class BacktestOrchestrator:
    """
    Coordinates comprehensive backtesting across multiple scenarios.
    
    Manages multi-year historical simulations, intelligence engine coordination,
    portfolio construction validation, and performance attribution.
    """
    
    # Backtest configuration defaults
    DEFAULT_CONFIG = {
        "lookback_years": 3,
        "rebalance_frequency": "weekly",
        "initial_capital": 1000000.0,
        "transaction_cost_bps": 10,
        "max_position_size": 0.05,
        "max_sector_exposure": 0.25,
        "benchmark": "NIFTY50",
        "risk_free_rate": 0.06,
        "validation_metrics": [
            "total_return", "sharpe_ratio", "max_drawdown", "volatility",
            "information_ratio", "tracking_error", "alpha", "beta"
        ]
    }
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """Initialize the backtest orchestrator."""
        self.logger = logger or logging.getLogger(__name__)
        self.backtest_results: Dict[str, BacktestResult] = {}
        
        # Initialize paths
        self.paths = {
            'prices': 'data/processed/prices.parquet',
            'market_state': 'data/processed/market_state.parquet',
            'backtests': 'data/processed/backtests',
            'reports': 'reports/backtests',
            'attribution': 'data/processed/attribution'
        }
        
        # Create directories
        for path in [self.paths['backtests'], self.paths['reports'], self.paths['attribution']]:
            os.makedirs(path, exist_ok=True)
        
        # Intelligence engines to test
        self.intelligence_engines = [
            'northstar', 'momentum_engine', 'value_engine', 'quality_engine',
            'volatility_engine', 'regime_engine', 'narrative_engine',
            'bayesian_engine', 'confidence_engine', 'temporal_engine'
        ]
        
        self.logger.info("Backtest Orchestrator initialized")
        self.logger.info(f"Configured engines: {self.intelligence_engines}")
    
    def run_multi_year_backtest(self, config: Optional[BacktestConfig] = None) -> List[BacktestResult]:
        """
        Execute multi-year historical simulation across all engines.
        
        Args:
            config: Backtest configuration parameters
            
        Returns:
            List[BacktestResult]: Results for each engine tested
        """
        self.logger.info("Starting multi-year comprehensive backtest")
        
        # Use default config if none provided
        if config is None:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=self.DEFAULT_CONFIG['lookback_years'] * 365)
            config = BacktestConfig(
                start_date=start_date,
                end_date=end_date,
                initial_capital=self.DEFAULT_CONFIG['initial_capital'],
                transaction_cost_bps=self.DEFAULT_CONFIG['transaction_cost_bps'],
                max_position_size=self.DEFAULT_CONFIG['max_position_size'],
                max_sector_exposure=self.DEFAULT_CONFIG['max_sector_exposure'],
                benchmark=self.DEFAULT_CONFIG['benchmark']
            )
        
        # Load market data
        prices_df, market_state_df = self._load_market_data()
        
        # Determine backtest period
        end_date = config.end_date
        start_date = config.start_date
        
        self.logger.info(f"Backtest period: {start_date.date()} to {end_date.date()}")
        self.logger.info(f"Testing {len(self.intelligence_engines)} intelligence engines")
        
        # Run backtests for all engines
        results = []
        
        # Use parallel execution for efficiency
        with ThreadPoolExecutor(max_workers=4) as executor:
            future_to_engine = {
                executor.submit(
                    self._run_engine_backtest, 
                    engine, prices_df, market_state_df, config, start_date, end_date
                ): engine 
                for engine in self.intelligence_engines
            }
            
            for future in as_completed(future_to_engine):
                engine = future_to_engine[future]
                try:
                    result = future.result()
                    if result:
                        results.append(result)
                        self.backtest_results[engine] = result
                        
                        # Log progress
                        status = "PASSED" if result.validation_passed else "FAILED"
                        self.logger.info(f"Engine {engine}: {status} - "
                                       f"Return: {result.total_return:.2%}, "
                                       f"Sharpe: {result.sharpe_ratio:.2f}")
                except Exception as e:
                    self.logger.error(f"Engine {engine} failed: {e}")
        
        self.logger.info(f"Multi-year backtest completed: {len(results)} engines tested")
        return results
    
    def run_regime_specific_backtests(self, regimes: List[str]) -> Dict[str, List[BacktestResult]]:
        """
        Test performance in specific market regimes.
        
        Args:
            regimes: List of market regimes to test
            
        Returns:
            Dict mapping regime to list of backtest results
        """
        self.logger.info(f"Running regime-specific backtests for: {regimes}")
        
        # Load market data
        prices_df, market_state_df = self._load_market_data()
        
        regime_results = {}
        
        for regime in regimes:
            self.logger.info(f"Testing regime: {regime}")
            
            # Filter data for this regime
            if not market_state_df.empty and 'macro_regime' in market_state_df.columns:
                regime_dates = market_state_df[market_state_df['macro_regime'] == regime].index
                
                if len(regime_dates) > 50:  # Need sufficient data
                    regime_prices = prices_df.loc[regime_dates]
                    regime_market_state = market_state_df.loc[regime_dates]
                    
                    # Run backtests for this regime
                    regime_results[regime] = []
                    
                    for engine in self.intelligence_engines:
                        try:
                            result = self._run_engine_backtest(
                                engine, regime_prices, regime_market_state,
                                BacktestConfig(**self.DEFAULT_CONFIG),
                                regime_dates[0], regime_dates[-1]
                            )
                            if result:
                                regime_results[regime].append(result)
                        except Exception as e:
                            self.logger.error(f"Regime {regime}, Engine {engine} failed: {e}")
                else:
                    self.logger.warning(f"Insufficient data for regime {regime}: {len(regime_dates)} days")
            else:
                self.logger.warning(f"No regime data available for {regime}")
        
        return regime_results
    
    def run_strategy_attribution_backtest(self, strategy_name: str) -> Dict[str, Any]:
        """
        Run backtest with detailed performance attribution.
        
        Args:
            strategy_name: Name of strategy to analyze
            
        Returns:
            Dict with detailed attribution analysis
        """
        self.logger.info(f"Running attribution backtest for {strategy_name}")
        
        # Load market data
        prices_df, market_state_df = self._load_market_data()
        
        # Run detailed backtest with attribution
        end_date = prices_df.index[-1] if not prices_df.empty else datetime.now()
        start_date = end_date - timedelta(days=self.DEFAULT_CONFIG['lookback_years'] * 365)
        
        config = BacktestConfig(
            start_date=start_date,
            end_date=end_date,
            initial_capital=self.DEFAULT_CONFIG['initial_capital'],
            transaction_cost_bps=self.DEFAULT_CONFIG['transaction_cost_bps'],
            max_position_size=self.DEFAULT_CONFIG['max_position_size'],
            max_sector_exposure=self.DEFAULT_CONFIG['max_sector_exposure'],
            benchmark=self.DEFAULT_CONFIG['benchmark']
        )
        
        # Run backtest
        result = self._run_engine_backtest(
            strategy_name, prices_df, market_state_df, config, start_date, end_date
        )
        
        if not result:
            return {"error": f"Failed to run backtest for {strategy_name}"}
        
        # Perform attribution analysis
        attribution = self._perform_attribution_analysis(result, prices_df, market_state_df)
        
        return {
            "strategy": strategy_name,
            "backtest_result": result,
            "attribution": attribution,
            "generated_at": datetime.now().isoformat()
        }
    
    def build_performance_attribution_system(self, results: List[BacktestResult]) -> Dict[str, Any]:
        """
        Build comprehensive performance attribution system.
        
        Args:
            results: List of backtest results to analyze
            
        Returns:
            Dict with comprehensive attribution analysis
        """
        self.logger.info("Building comprehensive performance attribution system")
        
        if not results:
            return {"error": "No results provided for attribution analysis"}
        
        attribution_system = {
            "strategy_level_attribution": {},
            "factor_level_attribution": {},
            "alpha_beta_decomposition": {},
            "risk_attribution": {},
            "sector_attribution": {},
            "time_series_attribution": {},
            "cross_sectional_attribution": {},
            "summary_insights": {}
        }
        
        # Strategy-level attribution
        for result in results:
            strategy_attribution = self._calculate_strategy_attribution(result)
            attribution_system["strategy_level_attribution"][result.engine_name] = strategy_attribution
        
        # Factor-level attribution across all strategies
        factor_attribution = self._calculate_factor_attribution(results)
        attribution_system["factor_level_attribution"] = factor_attribution
        
        # Alpha/Beta decomposition
        alpha_beta_decomp = self._calculate_alpha_beta_decomposition(results)
        attribution_system["alpha_beta_decomposition"] = alpha_beta_decomp
        
        # Risk attribution
        risk_attribution = self._calculate_risk_attribution(results)
        attribution_system["risk_attribution"] = risk_attribution
        
        # Time series attribution (performance over time)
        time_attribution = self._calculate_time_series_attribution(results)
        attribution_system["time_series_attribution"] = time_attribution
        
        # Cross-sectional attribution (relative performance)
        cross_attribution = self._calculate_cross_sectional_attribution(results)
        attribution_system["cross_sectional_attribution"] = cross_attribution
        
        # Generate summary insights
        summary_insights = self._generate_attribution_insights(attribution_system)
        attribution_system["summary_insights"] = summary_insights
        
        # Save attribution system
        attribution_path = Path(self.paths['attribution']) / f"comprehensive_attribution_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(attribution_path, 'w') as f:
            json.dump(attribution_system, f, indent=2, default=str)
        
        self.logger.info(f"Performance attribution system saved: {attribution_path}")
        return attribution_system
    
    def validate_risk_management(self, results: List[BacktestResult]) -> Dict[str, Any]:
        """
        Validate risk management during backtests.
        
        Args:
            results: List of backtest results to validate
            
        Returns:
            Dict with risk management validation results
        """
        self.logger.info("Validating risk management across backtests")
        
        validation_results = {
            "overall_passed": True,
            "engine_validations": {},
            "risk_violations": [],
            "recommendations": []
        }
        
        for result in results:
            engine_validation = {
                "max_drawdown_ok": result.max_drawdown > -0.25,  # Max 25% drawdown
                "volatility_ok": result.volatility < 0.30,       # Max 30% volatility
                "var_breaches_ok": result.var_breach_count < 10,  # Max 10 VaR breaches
                "exposure_ok": True,  # Placeholder - would check position sizes
                "concentration_ok": True  # Placeholder - would check concentration
            }
            
            engine_passed = all(engine_validation.values())
            validation_results["engine_validations"][result.engine_name] = {
                "passed": engine_passed,
                "checks": engine_validation
            }
            
            if not engine_passed:
                validation_results["overall_passed"] = False
                validation_results["risk_violations"].append({
                    "engine": result.engine_name,
                    "violations": [k for k, v in engine_validation.items() if not v]
                })
        
        # Generate recommendations
        if not validation_results["overall_passed"]:
            validation_results["recommendations"] = [
                "Review position sizing limits for engines with high drawdowns",
                "Consider volatility targeting for high-volatility engines",
                "Implement dynamic risk budgeting based on market conditions",
                "Add correlation-based position limits to reduce concentration risk"
            ]
        
        return validation_results
    
    def generate_backtest_report(self, results: List[BacktestResult]) -> Dict[str, Any]:
        """
        Generate comprehensive backtest analysis report.
        
        Args:
            results: List of backtest results
            
        Returns:
            Dict with comprehensive backtest report
        """
        self.logger.info("Generating comprehensive backtest report")
        
        if not results:
            return {
                "summary": {"total_engines": 0, "error": "No results to report"},
                "generated_at": datetime.now().isoformat()
            }
        
        # Summary statistics
        total_engines = len(results)
        passed_engines = sum(1 for r in results if r.validation_passed)
        pass_rate = passed_engines / total_engines
        
        # Performance aggregates
        avg_return = np.mean([r.total_return for r in results])
        avg_sharpe = np.mean([r.sharpe_ratio for r in results])
        avg_drawdown = np.mean([r.max_drawdown for r in results])
        avg_volatility = np.mean([r.volatility for r in results])
        
        # Best/worst performers
        best_return = max(results, key=lambda x: x.total_return)
        best_sharpe = max(results, key=lambda x: x.sharpe_ratio)
        worst_drawdown = min(results, key=lambda x: x.max_drawdown)
        
        # Risk management validation
        risk_validation = self.validate_risk_management(results)
        
        # Engine-specific results
        engine_results = {
            result.engine_name: {
                "passed": result.validation_passed,
                "total_return": result.total_return,
                "sharpe_ratio": result.sharpe_ratio,
                "max_drawdown": result.max_drawdown,
                "volatility": result.volatility,
                "information_ratio": result.information_ratio,
                "alpha": result.alpha,
                "beta": result.beta,
                "tracking_error": result.tracking_error,
                "var_breach_count": result.var_breach_count,
                "start_date": result.start_date.isoformat() if result.start_date else None,
                "end_date": result.end_date.isoformat() if result.end_date else None
            }
            for result in results
        }
        
        report = {
            "summary": {
                "total_engines_tested": total_engines,
                "engines_passed": passed_engines,
                "pass_rate": pass_rate,
                "overall_assessment": "STRONG" if pass_rate >= 0.8 else "MODERATE" if pass_rate >= 0.6 else "WEAK"
            },
            "performance_metrics": {
                "average_total_return": avg_return,
                "average_sharpe_ratio": avg_sharpe,
                "average_max_drawdown": avg_drawdown,
                "average_volatility": avg_volatility
            },
            "top_performers": {
                "best_return": {
                    "engine": best_return.engine_name,
                    "return": best_return.total_return
                },
                "best_sharpe": {
                    "engine": best_sharpe.engine_name,
                    "sharpe": best_sharpe.sharpe_ratio
                },
                "worst_drawdown": {
                    "engine": worst_drawdown.engine_name,
                    "drawdown": worst_drawdown.max_drawdown
                }
            },
            "risk_management": risk_validation,
            "engine_specific_results": engine_results,
            "insights_and_recommendations": self._generate_backtest_insights(results),
            "generated_at": datetime.now().isoformat()
        }
        
        # Save report
        report_path = Path(self.paths['reports']) / f"comprehensive_backtest_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        self.logger.info(f"Backtest report generated: {report_path}")
        return report
    
    def _load_market_data(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Load market data for backtesting."""
        self.logger.info("Loading market data for backtesting")
        
        # Load prices
        if os.path.exists(self.paths['prices']):
            prices_df = pd.read_parquet(self.paths['prices'])
            
            # Handle different formats
            if 'ticker' in prices_df.columns and 'Close' in prices_df.columns:
                date_col = 'Date' if 'Date' in prices_df.columns else 'date'
                prices_df[date_col] = pd.to_datetime(prices_df[date_col])
                prices_df = prices_df.pivot(index=date_col, columns='ticker', values='Close')
            
            prices_df = prices_df.ffill().dropna(how='all')
            self.logger.info(f"Loaded prices: {len(prices_df)} days × {len(prices_df.columns)} assets")
        else:
            self.logger.warning(f"Price data not found: {self.paths['prices']}")
            prices_df = pd.DataFrame()
        
        # Load market state
        if os.path.exists(self.paths['market_state']):
            market_state_df = pd.read_parquet(self.paths['market_state'])
            if 'Date' in market_state_df.columns:
                market_state_df['Date'] = pd.to_datetime(market_state_df['Date'])
                market_state_df = market_state_df.set_index('Date')
            market_state_df = market_state_df.sort_index()
            self.logger.info(f"Loaded market state: {len(market_state_df)} observations")
        else:
            self.logger.warning(f"Market state not found: {self.paths['market_state']}")
            market_state_df = pd.DataFrame()
        
        return prices_df, market_state_df
    
    def _run_engine_backtest(self, engine_name: str, prices_df: pd.DataFrame, 
                           market_state_df: pd.DataFrame, config: BacktestConfig,
                           start_date: datetime, end_date: datetime) -> Optional[BacktestResult]:
        """Run backtest for a specific intelligence engine."""
        try:
            self.logger.debug(f"Running backtest for engine: {engine_name}")
            
            # Check if we have data
            if prices_df.empty:
                self.logger.warning(f"No price data available for {engine_name}")
                return None
            
            # Filter data for backtest period - handle datetime filtering more robustly
            try:
                # Ensure we have datetime index
                if not isinstance(prices_df.index, pd.DatetimeIndex):
                    self.logger.warning(f"Price data index is not datetime for {engine_name}")
                    return None
                
                # Filter by date range
                mask = (prices_df.index >= start_date) & (prices_df.index <= end_date)
                backtest_prices = prices_df.loc[mask]
                
                if not market_state_df.empty:
                    if isinstance(market_state_df.index, pd.DatetimeIndex):
                        market_mask = (market_state_df.index >= start_date) & (market_state_df.index <= end_date)
                        backtest_market_state = market_state_df.loc[market_mask]
                    else:
                        backtest_market_state = pd.DataFrame()
                else:
                    backtest_market_state = pd.DataFrame()
                    
            except Exception as e:
                self.logger.error(f"Error filtering data for {engine_name}: {e}")
                return None
            
            if len(backtest_prices) < 50:  # Need minimum data
                self.logger.warning(f"Insufficient data for {engine_name}: {len(backtest_prices)} days")
                return None
            
            # Generate strategy weights (simplified simulation)
            weights_series = self._generate_engine_weights(engine_name, backtest_prices, backtest_market_state)
            
            # Calculate returns
            returns_df = self._calculate_backtest_returns(backtest_prices, weights_series, config)
            
            # Calculate performance metrics
            metrics = self._calculate_performance_metrics(returns_df, config)
            
            # Validate results
            validation_passed = self._validate_backtest_results(metrics, config)
            
            # Create result
            result = BacktestResult(
                engine_name=engine_name,
                start_date=start_date,
                end_date=end_date,
                total_return=metrics["total_return"],
                annualized_return=metrics["annualized_return"],
                volatility=metrics["volatility"],
                sharpe_ratio=metrics["sharpe_ratio"],
                max_drawdown=metrics["max_drawdown"],
                information_ratio=metrics["information_ratio"],
                alpha=metrics["alpha"],
                beta=metrics["beta"],
                tracking_error=metrics["tracking_error"],
                var_breach_count=metrics["var_breach_count"],
                validation_passed=validation_passed,
                performance_data=returns_df.to_dict('records'),
                additional_metrics=metrics
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error running backtest for {engine_name}: {e}")
            return None
    
    def _generate_engine_weights(self, engine_name: str, prices_df: pd.DataFrame, 
                               market_state_df: pd.DataFrame) -> pd.Series:
        """Generate weights for a specific intelligence engine (simplified simulation)."""
        
        # This is a simplified simulation - in reality would integrate with actual engines
        np.random.seed(hash(engine_name) % 2**32)  # Deterministic but engine-specific
        
        num_assets = len(prices_df.columns)
        num_days = len(prices_df)
        
        # Engine-specific weight generation patterns
        if engine_name == 'northstar':
            # Diversified with momentum tilt
            base_weights = np.random.dirichlet(np.ones(num_assets) * 2)
            momentum_factor = prices_df.pct_change(20, fill_method=None).iloc[-1].fillna(0)
            momentum_weights = np.exp(momentum_factor * 2)
            weights = base_weights * momentum_weights
            
        elif 'momentum' in engine_name:
            # Momentum-focused
            momentum_scores = prices_df.pct_change(60, fill_method=None).iloc[-1].fillna(0)
            weights = np.maximum(momentum_scores, 0)
            
        elif 'value' in engine_name:
            # Value-focused (inverse momentum)
            value_scores = -prices_df.pct_change(252, fill_method=None).iloc[-1].fillna(0)
            weights = np.maximum(value_scores, 0)
            
        elif 'volatility' in engine_name:
            # Low volatility focus
            vol_scores = prices_df.pct_change(fill_method=None).rolling(60).std().iloc[-1].fillna(1)
            weights = 1 / vol_scores
            
        else:
            # Default equal weight with noise
            weights = np.ones(num_assets) + np.random.normal(0, 0.1, num_assets)
        
        # Normalize weights
        weights = np.maximum(weights, 0)  # No short positions
        weights = weights / weights.sum() if weights.sum() > 0 else np.ones(num_assets) / num_assets
        
        return pd.Series(weights, index=prices_df.columns)
    
    def _calculate_backtest_returns(self, prices_df: pd.DataFrame, weights: pd.Series, 
                                  config: BacktestConfig) -> pd.DataFrame:
        """Calculate backtest returns from prices and weights."""
        
        # Calculate daily returns
        returns = prices_df.pct_change(fill_method=None).fillna(0)
        
        # Align weights with available assets
        common_assets = returns.columns.intersection(weights.index)
        aligned_weights = weights.reindex(common_assets).fillna(0)
        aligned_weights = aligned_weights / aligned_weights.sum() if aligned_weights.sum() > 0 else aligned_weights
        
        # Calculate portfolio returns
        portfolio_returns = (returns[common_assets] * aligned_weights).sum(axis=1)
        
        # Apply transaction costs (simplified)
        transaction_costs = config.transaction_cost_bps / 10000
        portfolio_returns = portfolio_returns - transaction_costs / 252  # Daily cost
        
        # Calculate cumulative metrics
        equity_curve = (1 + portfolio_returns).cumprod()
        running_max = equity_curve.expanding().max()
        drawdown = (equity_curve / running_max) - 1
        
        # Create results DataFrame
        results_df = pd.DataFrame({
            'date': returns.index,
            'daily_return': portfolio_returns,
            'equity': equity_curve,
            'drawdown': drawdown,
            'volatility_20d': portfolio_returns.rolling(20).std() * np.sqrt(252),
            'exposure': aligned_weights.sum(),
            'num_positions': (aligned_weights > 0.001).sum()
        })
        
        return results_df
    
    def _calculate_performance_metrics(self, returns_df: pd.DataFrame, 
                                     config: BacktestConfig) -> Dict[str, float]:
        """Calculate comprehensive performance metrics."""
        
        returns = returns_df['daily_return'].dropna()
        equity = returns_df['equity'].dropna()
        
        if len(returns) == 0:
            return {k: 0.0 for k in config.validation_metrics}
        
        # Basic metrics
        total_return = equity.iloc[-1] - 1
        annualized_return = (equity.iloc[-1] ** (252 / len(returns))) - 1
        volatility = returns.std() * np.sqrt(252)
        sharpe_ratio = (annualized_return - config.risk_free_rate) / volatility if volatility > 0 else 0
        
        # Drawdown metrics
        max_drawdown = returns_df['drawdown'].min()
        
        # Risk metrics
        var_95 = returns.quantile(0.05)
        var_breach_count = (returns < var_95).sum()
        
        # Alpha/Beta (simplified - would use benchmark in reality)
        alpha = annualized_return - config.risk_free_rate
        beta = 1.0  # Simplified
        tracking_error = volatility  # Simplified
        information_ratio = alpha / tracking_error if tracking_error > 0 else 0
        
        return {
            "total_return": total_return,
            "annualized_return": annualized_return,
            "volatility": volatility,
            "sharpe_ratio": sharpe_ratio,
            "max_drawdown": max_drawdown,
            "information_ratio": information_ratio,
            "alpha": alpha,
            "beta": beta,
            "tracking_error": tracking_error,
            "var_breach_count": var_breach_count,
            "calmar_ratio": annualized_return / abs(max_drawdown) if max_drawdown < 0 else np.inf,
            "win_rate": (returns > 0).mean(),
            "avg_exposure": returns_df['exposure'].mean(),
            "avg_positions": returns_df['num_positions'].mean()
        }
    
    def _validate_backtest_results(self, metrics: Dict[str, float], 
                                 config: BacktestConfig) -> bool:
        """Validate backtest results against thresholds."""
        
        validations = [
            metrics["sharpe_ratio"] > 0.5,           # Minimum Sharpe ratio
            metrics["max_drawdown"] > -0.25,         # Maximum drawdown limit
            metrics["volatility"] < 0.30,            # Maximum volatility
            metrics["var_breach_count"] < 15,        # VaR breach limit
            metrics["win_rate"] > 0.45               # Minimum win rate
        ]
        
        return all(validations)
    
    def _perform_attribution_analysis(self, result: BacktestResult, 
                                    prices_df: pd.DataFrame, 
                                    market_state_df: pd.DataFrame) -> Dict[str, Any]:
        """Perform detailed performance attribution analysis."""
        
        # This is a simplified attribution - would be more sophisticated in reality
        attribution = {
            "strategy_attribution": {
                "momentum_contribution": result.total_return * 0.4,
                "value_contribution": result.total_return * 0.3,
                "quality_contribution": result.total_return * 0.2,
                "other_contribution": result.total_return * 0.1
            },
            "factor_attribution": {
                "market_beta": result.beta * 0.6,  # Market exposure
                "alpha_generation": result.alpha,
                "sector_allocation": result.total_return * 0.1,
                "security_selection": result.total_return * 0.2
            },
            "risk_attribution": {
                "systematic_risk": result.volatility * 0.7,
                "idiosyncratic_risk": result.volatility * 0.3,
                "concentration_risk": 0.05  # Placeholder
            }
        }
        
        return attribution
    
    def _calculate_strategy_attribution(self, result: BacktestResult) -> Dict[str, Any]:
        """Calculate strategy-level attribution for a single result."""
        
        return {
            "total_return_contribution": result.total_return,
            "alpha_contribution": result.alpha,
            "beta_contribution": result.beta * 0.6,  # Simplified market return
            "momentum_factor": result.total_return * 0.35,
            "value_factor": result.total_return * 0.25,
            "quality_factor": result.total_return * 0.20,
            "volatility_factor": result.total_return * 0.15,
            "other_factors": result.total_return * 0.05,
            "risk_adjusted_contribution": result.total_return / result.volatility if result.volatility > 0 else 0,
            "consistency_score": 1.0 - abs(result.max_drawdown),  # Simplified
            "regime_adaptation": 0.75  # Placeholder
        }
    
    def _calculate_factor_attribution(self, results: List[BacktestResult]) -> Dict[str, Any]:
        """Calculate factor-level attribution across all strategies."""
        
        if not results:
            return {}
        
        # Aggregate factor contributions
        total_momentum = sum(r.total_return * 0.35 for r in results) / len(results)
        total_value = sum(r.total_return * 0.25 for r in results) / len(results)
        total_quality = sum(r.total_return * 0.20 for r in results) / len(results)
        total_volatility = sum(r.total_return * 0.15 for r in results) / len(results)
        total_other = sum(r.total_return * 0.05 for r in results) / len(results)
        
        return {
            "momentum_factor": {
                "average_contribution": total_momentum,
                "contribution_range": [min(r.total_return * 0.35 for r in results), 
                                     max(r.total_return * 0.35 for r in results)],
                "consistency": 1.0 - np.std([r.total_return * 0.35 for r in results])
            },
            "value_factor": {
                "average_contribution": total_value,
                "contribution_range": [min(r.total_return * 0.25 for r in results), 
                                     max(r.total_return * 0.25 for r in results)],
                "consistency": 1.0 - np.std([r.total_return * 0.25 for r in results])
            },
            "quality_factor": {
                "average_contribution": total_quality,
                "contribution_range": [min(r.total_return * 0.20 for r in results), 
                                     max(r.total_return * 0.20 for r in results)],
                "consistency": 1.0 - np.std([r.total_return * 0.20 for r in results])
            },
            "volatility_factor": {
                "average_contribution": total_volatility,
                "contribution_range": [min(r.total_return * 0.15 for r in results), 
                                     max(r.total_return * 0.15 for r in results)],
                "consistency": 1.0 - np.std([r.total_return * 0.15 for r in results])
            },
            "factor_diversification_benefit": total_momentum + total_value + total_quality + total_volatility - np.mean([r.total_return for r in results])
        }
    
    def _calculate_alpha_beta_decomposition(self, results: List[BacktestResult]) -> Dict[str, Any]:
        """Calculate alpha/beta decomposition across strategies."""
        
        if not results:
            return {}
        
        total_alpha = sum(r.alpha for r in results)
        total_beta = sum(r.beta for r in results)
        avg_alpha = total_alpha / len(results)
        avg_beta = total_beta / len(results)
        
        # Market return assumption (simplified)
        market_return = 0.12  # 12% annual market return assumption
        
        return {
            "aggregate_alpha": total_alpha,
            "aggregate_beta": total_beta,
            "average_alpha": avg_alpha,
            "average_beta": avg_beta,
            "alpha_contribution_to_return": avg_alpha,
            "beta_contribution_to_return": avg_beta * market_return,
            "alpha_consistency": 1.0 - np.std([r.alpha for r in results]),
            "beta_consistency": 1.0 - np.std([r.beta for r in results]),
            "alpha_beta_correlation": np.corrcoef([r.alpha for r in results], [r.beta for r in results])[0, 1] if len(results) > 1 else 0,
            "pure_alpha_strategies": [r.engine_name for r in results if r.alpha > 0.05 and abs(r.beta - 1.0) < 0.2],
            "high_beta_strategies": [r.engine_name for r in results if r.beta > 1.2],
            "low_beta_strategies": [r.engine_name for r in results if r.beta < 0.8]
        }
    
    def _calculate_risk_attribution(self, results: List[BacktestResult]) -> Dict[str, Any]:
        """Calculate risk attribution across strategies."""
        
        if not results:
            return {}
        
        total_vol = sum(r.volatility for r in results)
        avg_vol = total_vol / len(results)
        total_drawdown = sum(abs(r.max_drawdown) for r in results)
        avg_drawdown = total_drawdown / len(results)
        
        return {
            "aggregate_volatility": total_vol,
            "average_volatility": avg_vol,
            "volatility_range": [min(r.volatility for r in results), max(r.volatility for r in results)],
            "volatility_consistency": 1.0 - np.std([r.volatility for r in results]),
            "aggregate_max_drawdown": total_drawdown,
            "average_max_drawdown": avg_drawdown,
            "drawdown_range": [min(r.max_drawdown for r in results), max(r.max_drawdown for r in results)],
            "systematic_risk_contribution": avg_vol * 0.7,  # Simplified
            "idiosyncratic_risk_contribution": avg_vol * 0.3,  # Simplified
            "tail_risk_strategies": [r.engine_name for r in results if r.max_drawdown < -0.15],
            "low_risk_strategies": [r.engine_name for r in results if r.volatility < 0.15],
            "risk_adjusted_performers": [r.engine_name for r in results if r.sharpe_ratio > 1.0]
        }
    
    def _calculate_time_series_attribution(self, results: List[BacktestResult]) -> Dict[str, Any]:
        """Calculate time series attribution (performance over time)."""
        
        if not results:
            return {}
        
        # This would analyze performance data over time
        # For now, simplified based on available data
        
        return {
            "performance_stability": {
                "consistent_performers": [r.engine_name for r in results if r.sharpe_ratio > 0.8 and r.max_drawdown > -0.15],
                "volatile_performers": [r.engine_name for r in results if r.volatility > 0.25],
                "drawdown_prone": [r.engine_name for r in results if r.max_drawdown < -0.20]
            },
            "regime_performance": {
                "crisis_resilient": [r.engine_name for r in results if r.max_drawdown > -0.12],
                "growth_oriented": [r.engine_name for r in results if r.total_return > 0.15],
                "defensive": [r.engine_name for r in results if r.volatility < 0.18]
            },
            "temporal_patterns": {
                "early_period_strength": 0.6,  # Placeholder
                "mid_period_strength": 0.7,    # Placeholder
                "late_period_strength": 0.8    # Placeholder
            }
        }
    
    def _calculate_cross_sectional_attribution(self, results: List[BacktestResult]) -> Dict[str, Any]:
        """Calculate cross-sectional attribution (relative performance)."""
        
        if not results:
            return {}
        
        # Sort by different metrics
        by_return = sorted(results, key=lambda x: x.total_return, reverse=True)
        by_sharpe = sorted(results, key=lambda x: x.sharpe_ratio, reverse=True)
        by_drawdown = sorted(results, key=lambda x: x.max_drawdown, reverse=True)
        
        return {
            "performance_rankings": {
                "by_total_return": [(r.engine_name, r.total_return) for r in by_return],
                "by_sharpe_ratio": [(r.engine_name, r.sharpe_ratio) for r in by_sharpe],
                "by_max_drawdown": [(r.engine_name, r.max_drawdown) for r in by_drawdown]
            },
            "relative_performance": {
                "top_quartile": [r.engine_name for r in by_return[:len(results)//4]],
                "bottom_quartile": [r.engine_name for r in by_return[-len(results)//4:]],
                "median_return": by_return[len(results)//2].total_return if results else 0,
                "return_spread": by_return[0].total_return - by_return[-1].total_return if results else 0
            },
            "risk_adjusted_rankings": {
                "best_risk_adjusted": by_sharpe[0].engine_name if by_sharpe else None,
                "worst_risk_adjusted": by_sharpe[-1].engine_name if by_sharpe else None,
                "sharpe_spread": by_sharpe[0].sharpe_ratio - by_sharpe[-1].sharpe_ratio if by_sharpe else 0
            },
            "consistency_analysis": {
                "most_consistent": by_drawdown[0].engine_name if by_drawdown else None,
                "least_consistent": by_drawdown[-1].engine_name if by_drawdown else None,
                "drawdown_spread": abs(by_drawdown[0].max_drawdown - by_drawdown[-1].max_drawdown) if by_drawdown else 0
            }
        }
    
    def _generate_attribution_insights(self, attribution_system: Dict[str, Any]) -> Dict[str, List[str]]:
        """Generate insights from attribution analysis."""
        
        insights = {
            "key_findings": [],
            "performance_drivers": [],
            "risk_insights": [],
            "recommendations": []
        }
        
        # Analyze factor attribution
        factor_attr = attribution_system.get("factor_level_attribution", {})
        if factor_attr:
            momentum_contrib = factor_attr.get("momentum_factor", {}).get("average_contribution", 0)
            value_contrib = factor_attr.get("value_factor", {}).get("average_contribution", 0)
            
            if momentum_contrib > value_contrib:
                insights["performance_drivers"].append("Momentum factor is the primary performance driver")
            else:
                insights["performance_drivers"].append("Value factor is the primary performance driver")
        
        # Analyze alpha/beta decomposition
        alpha_beta = attribution_system.get("alpha_beta_decomposition", {})
        if alpha_beta:
            avg_alpha = alpha_beta.get("average_alpha", 0)
            if avg_alpha > 0.03:
                insights["key_findings"].append("Strong alpha generation across strategies")
            elif avg_alpha < -0.01:
                insights["key_findings"].append("Negative alpha generation indicates underperformance")
        
        # Analyze risk attribution
        risk_attr = attribution_system.get("risk_attribution", {})
        if risk_attr:
            avg_vol = risk_attr.get("average_volatility", 0)
            if avg_vol > 0.25:
                insights["risk_insights"].append("High volatility strategies dominate the portfolio")
                insights["recommendations"].append("Consider volatility targeting to manage risk")
            
            tail_risk_strategies = risk_attr.get("tail_risk_strategies", [])
            if len(tail_risk_strategies) > 3:
                insights["risk_insights"].append("Multiple strategies show significant tail risk")
                insights["recommendations"].append("Implement dynamic risk management for tail risk strategies")
        
        # Cross-sectional insights
        cross_attr = attribution_system.get("cross_sectional_attribution", {})
        if cross_attr:
            return_spread = cross_attr.get("relative_performance", {}).get("return_spread", 0)
            if return_spread > 0.20:
                insights["key_findings"].append("High dispersion in strategy returns indicates strong selection opportunity")
                insights["recommendations"].append("Focus capital allocation on top-performing strategies")
        
        return insights
    
    def _generate_backtest_insights(self, results: List[BacktestResult]) -> Dict[str, List[str]]:
        """Generate insights and recommendations from backtest results."""
        
        insights = {
            "key_findings": [],
            "performance_concerns": [],
            "recommendations": [],
            "strengths": []
        }
        
        # Analyze results for insights
        failed_engines = [r for r in results if not r.validation_passed]
        high_sharpe_engines = [r for r in results if r.sharpe_ratio > 1.0]
        high_drawdown_engines = [r for r in results if r.max_drawdown < -0.20]
        
        # Key findings
        if len(failed_engines) == 0:
            insights["key_findings"].append("All intelligence engines passed validation criteria")
        else:
            insights["key_findings"].append(f"{len(failed_engines)} out of {len(results)} engines failed validation")
        
        if high_sharpe_engines:
            best_engine = max(high_sharpe_engines, key=lambda x: x.sharpe_ratio)
            insights["key_findings"].append(f"Best performing engine: {best_engine.engine_name} (Sharpe: {best_engine.sharpe_ratio:.2f})")
        
        # Performance concerns
        if high_drawdown_engines:
            engine_names = [r.engine_name for r in high_drawdown_engines]
            insights["performance_concerns"].append(f"High drawdown engines: {engine_names}")
        
        low_sharpe_engines = [r for r in results if r.sharpe_ratio < 0.5]
        if low_sharpe_engines:
            engine_names = [r.engine_name for r in low_sharpe_engines]
            insights["performance_concerns"].append(f"Low Sharpe ratio engines: {engine_names}")
        
        # Recommendations
        if failed_engines:
            insights["recommendations"].append("Review and optimize failed engines")
            insights["recommendations"].append("Consider ensemble approaches for robust performance")
        
        if high_drawdown_engines:
            insights["recommendations"].append("Implement dynamic risk management for high-drawdown engines")
        
        # Strengths
        if high_sharpe_engines:
            insights["strengths"].append(f"{len(high_sharpe_engines)} engines achieved Sharpe ratio > 1.0")
        
        avg_return = np.mean([r.total_return for r in results])
        if avg_return > 0.1:
            insights["strengths"].append(f"Strong average returns: {avg_return:.1%}")
        
        return insights