"""
Property tests for Task 4: Backtest Orchestrator

These tests validate the universal correctness properties of the backtest orchestrator
using property-based testing to ensure the system behaves correctly across all scenarios.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from hypothesis import given, strategies as st, settings, assume
from pathlib import Path
import tempfile
import os
import json

from src.operation.backtest_orchestrator import BacktestOrchestrator
from src.operation.base_types import BacktestConfig, BacktestResult, PerformanceMetrics


class TestBacktestOrchestratorProperties:
    """Property tests for Backtest Orchestrator functionality."""
    
    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.orchestrator = BacktestOrchestrator()
        
        # Override paths to use temp directory
        self.orchestrator.paths = {
            'prices': os.path.join(self.temp_dir, 'prices.parquet'),
            'market_state': os.path.join(self.temp_dir, 'market_state.parquet'),
            'backtests': os.path.join(self.temp_dir, 'backtests'),
            'reports': os.path.join(self.temp_dir, 'reports'),
            'attribution': os.path.join(self.temp_dir, 'attribution')
        }
        
        # Create directories
        for path in [self.orchestrator.paths['backtests'], 
                     self.orchestrator.paths['reports'], 
                     self.orchestrator.paths['attribution']]:
            os.makedirs(path, exist_ok=True)
        
        # Create sample data
        self._create_sample_data()
    
    def _create_sample_data(self):
        """Create sample price and market state data for testing."""
        # Create sample price data
        dates = pd.date_range(start='2020-01-01', end='2023-12-31', freq='D')
        tickers = ['STOCK1', 'STOCK2', 'STOCK3', 'STOCK4', 'STOCK5']
        
        # Generate realistic price data
        np.random.seed(42)
        price_data = []
        
        for ticker in tickers:
            base_price = 100
            for date in dates:
                # Random walk with drift
                daily_return = np.random.normal(0.0005, 0.02)  # 0.05% daily drift, 2% volatility
                base_price *= (1 + daily_return)
                price_data.append({
                    'Date': date,
                    'ticker': ticker,
                    'Close': base_price
                })
        
        prices_df = pd.DataFrame(price_data)
        prices_df.to_parquet(self.orchestrator.paths['prices'], index=False)
        
        # Create sample market state data
        market_data = []
        regimes = ['bull', 'bear', 'sideways']
        
        for date in dates:
            market_data.append({
                'Date': date,
                'macro_regime': np.random.choice(regimes),
                'vol_regime': np.random.choice(['low', 'medium', 'high']),
                'risk_on_probability': np.random.uniform(0.2, 0.8)
            })
        
        market_df = pd.DataFrame(market_data)
        market_df.to_parquet(self.orchestrator.paths['market_state'], index=False)
    
    @given(
        lookback_years=st.integers(min_value=1, max_value=3),
        initial_capital=st.floats(min_value=100000, max_value=10000000),
        transaction_cost_bps=st.floats(min_value=1, max_value=50)
    )
    @settings(max_examples=10, deadline=30000)
    def test_property_6_multi_year_backtest_execution(self, lookback_years, initial_capital, transaction_cost_bps):
        """
        Property 6: Multi-Year Backtest Execution
        
        For any valid date range spanning multiple years, the backtest orchestrator 
        should successfully execute historical simulations and produce results.
        
        Validates: Requirements 3.1
        """
        # Create backtest configuration with proper date range
        end_date = datetime(2023, 12, 31)
        start_date = end_date - timedelta(days=lookback_years * 365)
        
        config = BacktestConfig(
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital,
            transaction_cost_bps=transaction_cost_bps
        )
        
        # Execute multi-year backtest
        results = self.orchestrator.run_multi_year_backtest(config)
        
        # Property assertions
        assert isinstance(results, list), "Multi-year backtest should return a list of results"
        assert len(results) > 0, "Multi-year backtest should produce at least one result"
        
        for result in results:
            assert isinstance(result, BacktestResult), "Each result should be a BacktestResult instance"
            assert result.start_date is not None, "Each result should have a start date"
            assert result.end_date is not None, "Each result should have an end date"
            assert result.end_date > result.start_date, "End date should be after start date"
            
            # Duration should match requested lookback
            duration_years = (result.end_date - result.start_date).days / 365.25
            assert abs(duration_years - lookback_years) < 0.1, f"Duration should be approximately {lookback_years} years"
            
            # Performance metrics should be finite
            assert np.isfinite(result.total_return), "Total return should be finite"
            assert np.isfinite(result.volatility), "Volatility should be finite"
            assert np.isfinite(result.sharpe_ratio), "Sharpe ratio should be finite"
            assert np.isfinite(result.max_drawdown), "Max drawdown should be finite"
            
            # Logical constraints
            assert result.max_drawdown <= 0, "Max drawdown should be non-positive"
            assert result.volatility >= 0, "Volatility should be non-negative"
    
    @given(
        num_engines=st.integers(min_value=2, max_value=5)
    )
    @settings(max_examples=5, deadline=30000)
    def test_property_7_simultaneous_engine_operation(self, num_engines):
        """
        Property 7: Simultaneous Engine Operation
        
        For any backtesting execution, all intelligence engines should operate 
        simultaneously without conflicts or resource contention.
        
        Validates: Requirements 3.2
        """
        # Limit engines for testing
        original_engines = self.orchestrator.intelligence_engines.copy()
        self.orchestrator.intelligence_engines = original_engines[:num_engines]
        
        try:
            # Execute backtest with multiple engines
            results = self.orchestrator.run_multi_year_backtest()
            
            # Property assertions
            assert len(results) == num_engines, f"Should have results for all {num_engines} engines"
            
            # Check that all engines ran simultaneously (no conflicts)
            engine_names = [result.engine_name for result in results]
            assert len(set(engine_names)) == num_engines, "All engines should have unique names"
            
            # Check that all engines processed the same time period
            start_dates = [result.start_date for result in results]
            end_dates = [result.end_date for result in results]
            
            # All engines should have similar start/end dates (within 1 day tolerance)
            for i in range(1, len(start_dates)):
                assert abs((start_dates[i] - start_dates[0]).days) <= 1, "All engines should start on similar dates"
                assert abs((end_dates[i] - end_dates[0]).days) <= 1, "All engines should end on similar dates"
            
            # Check that results are independent (no resource conflicts)
            returns = [result.total_return for result in results]
            assert len(set(returns)) > 1 or len(returns) == 1, "Engines should produce independent results"
            
        finally:
            # Restore original engines
            self.orchestrator.intelligence_engines = original_engines
    
    @given(
        num_results=st.integers(min_value=1, max_value=10)
    )
    @settings(max_examples=5, deadline=20000)
    def test_property_9_backtest_report_generation(self, num_results):
        """
        Property 9: Backtest Report Generation
        
        For any completed backtest, the system should generate detailed 
        performance attribution reports with all required metrics.
        
        Validates: Requirements 3.4
        """
        # Create mock backtest results
        results = []
        for i in range(num_results):
            result = BacktestResult(
                engine_name=f"test_engine_{i}",
                start_date=datetime(2022, 1, 1),
                end_date=datetime(2023, 12, 31),
                total_return=np.random.uniform(-0.2, 0.3),
                annualized_return=np.random.uniform(-0.1, 0.2),
                volatility=np.random.uniform(0.1, 0.4),
                sharpe_ratio=np.random.uniform(-1, 2),
                max_drawdown=np.random.uniform(-0.3, 0),
                information_ratio=np.random.uniform(-0.5, 1.5),
                alpha=np.random.uniform(-0.05, 0.1),
                beta=np.random.uniform(0.5, 1.5),
                tracking_error=np.random.uniform(0.05, 0.2),
                var_breach_count=np.random.randint(0, 20),
                validation_passed=np.random.choice([True, False])
            )
            results.append(result)
        
        # Generate backtest report
        report = self.orchestrator.generate_backtest_report(results)
        
        # Property assertions
        assert isinstance(report, dict), "Report should be a dictionary"
        assert "summary" in report, "Report should contain summary section"
        assert "performance_metrics" in report, "Report should contain performance metrics"
        assert "engine_specific_results" in report, "Report should contain engine-specific results"
        assert "generated_at" in report, "Report should contain generation timestamp"
        
        # Summary section validation
        summary = report["summary"]
        assert summary["total_engines_tested"] == num_results, "Summary should show correct number of engines"
        assert 0 <= summary["pass_rate"] <= 1, "Pass rate should be between 0 and 1"
        assert summary["overall_assessment"] in ["STRONG", "MODERATE", "WEAK"], "Assessment should be valid"
        
        # Performance metrics validation
        perf_metrics = report["performance_metrics"]
        assert "average_total_return" in perf_metrics, "Should include average total return"
        assert "average_sharpe_ratio" in perf_metrics, "Should include average Sharpe ratio"
        assert "average_max_drawdown" in perf_metrics, "Should include average max drawdown"
        assert "average_volatility" in perf_metrics, "Should include average volatility"
        
        # Engine-specific results validation
        engine_results = report["engine_specific_results"]
        assert len(engine_results) == num_results, "Should have results for all engines"
        
        for engine_name, engine_data in engine_results.items():
            assert "passed" in engine_data, "Each engine should have pass/fail status"
            assert "total_return" in engine_data, "Each engine should have total return"
            assert "sharpe_ratio" in engine_data, "Each engine should have Sharpe ratio"
            assert "max_drawdown" in engine_data, "Each engine should have max drawdown"
    
    @given(
        strategy_name=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd')))
    )
    @settings(max_examples=3, deadline=20000)
    def test_property_10_performance_attribution_system(self, strategy_name):
        """
        Property 10: Performance Attribution System
        
        For any strategy attribution analysis, the system should provide 
        comprehensive factor-level, strategy-level, and alpha/beta attribution.
        
        Validates: Requirements 7.1, 7.2, 7.3
        """
        assume(len(strategy_name.strip()) > 0)  # Ensure non-empty strategy name
        
        # Create mock backtest results for attribution
        results = []
        for i in range(3):  # Test with 3 strategies
            result = BacktestResult(
                engine_name=f"{strategy_name}_{i}",
                start_date=datetime(2022, 1, 1),
                end_date=datetime(2023, 12, 31),
                total_return=np.random.uniform(0.05, 0.25),
                annualized_return=np.random.uniform(0.03, 0.15),
                volatility=np.random.uniform(0.12, 0.25),
                sharpe_ratio=np.random.uniform(0.5, 2.0),
                max_drawdown=np.random.uniform(-0.15, -0.02),
                information_ratio=np.random.uniform(0.2, 1.2),
                alpha=np.random.uniform(0.01, 0.08),
                beta=np.random.uniform(0.8, 1.2),
                tracking_error=np.random.uniform(0.08, 0.15),
                var_breach_count=np.random.randint(0, 10),
                validation_passed=True
            )
            results.append(result)
        
        # Build performance attribution system
        attribution_system = self.orchestrator.build_performance_attribution_system(results)
        
        # Property assertions
        assert isinstance(attribution_system, dict), "Attribution system should be a dictionary"
        
        # Required attribution components
        required_components = [
            "strategy_level_attribution",
            "factor_level_attribution", 
            "alpha_beta_decomposition",
            "risk_attribution",
            "time_series_attribution",
            "cross_sectional_attribution",
            "summary_insights"
        ]
        
        for component in required_components:
            assert component in attribution_system, f"Attribution system should contain {component}"
        
        # Strategy-level attribution validation
        strategy_attr = attribution_system["strategy_level_attribution"]
        assert len(strategy_attr) == len(results), "Should have attribution for all strategies"
        
        for strategy_name, attr_data in strategy_attr.items():
            assert "total_return_contribution" in attr_data, "Should include return contribution"
            assert "alpha_contribution" in attr_data, "Should include alpha contribution"
            assert "beta_contribution" in attr_data, "Should include beta contribution"
            assert "risk_adjusted_contribution" in attr_data, "Should include risk-adjusted contribution"
        
        # Factor-level attribution validation
        factor_attr = attribution_system["factor_level_attribution"]
        expected_factors = ["momentum_factor", "value_factor", "quality_factor", "volatility_factor"]
        
        for factor in expected_factors:
            assert factor in factor_attr, f"Should include {factor} attribution"
            factor_data = factor_attr[factor]
            assert "average_contribution" in factor_data, f"{factor} should have average contribution"
            assert "contribution_range" in factor_data, f"{factor} should have contribution range"
            assert "consistency" in factor_data, f"{factor} should have consistency measure"
        
        # Alpha/Beta decomposition validation
        alpha_beta = attribution_system["alpha_beta_decomposition"]
        assert "aggregate_alpha" in alpha_beta, "Should include aggregate alpha"
        assert "aggregate_beta" in alpha_beta, "Should include aggregate beta"
        assert "average_alpha" in alpha_beta, "Should include average alpha"
        assert "average_beta" in alpha_beta, "Should include average beta"
        assert "alpha_contribution_to_return" in alpha_beta, "Should include alpha contribution"
        assert "beta_contribution_to_return" in alpha_beta, "Should include beta contribution"
        
        # Risk attribution validation
        risk_attr = attribution_system["risk_attribution"]
        assert "aggregate_volatility" in risk_attr, "Should include aggregate volatility"
        assert "average_volatility" in risk_attr, "Should include average volatility"
        assert "systematic_risk_contribution" in risk_attr, "Should include systematic risk"
        assert "idiosyncratic_risk_contribution" in risk_attr, "Should include idiosyncratic risk"
        
        # Summary insights validation
        insights = attribution_system["summary_insights"]
        assert "key_findings" in insights, "Should include key findings"
        assert "performance_drivers" in insights, "Should include performance drivers"
        assert "risk_insights" in insights, "Should include risk insights"
        assert "recommendations" in insights, "Should include recommendations"
        
        # Ensure insights are lists
        for insight_type in ["key_findings", "performance_drivers", "risk_insights", "recommendations"]:
            assert isinstance(insights[insight_type], list), f"{insight_type} should be a list"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])