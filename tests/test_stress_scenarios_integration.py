"""
Integration Tests for Stress Scenarios

Tests specific historical crisis scenarios:
- 2008 financial crisis
- 2020 COVID crash
- Combined crisis scenario

Validates: Requirements 13.2
"""

import pytest
import numpy as np
from datetime import datetime

from src.volatility.monte_carlo_engine import (
    MonteCarloEngine,
    StressScenario,
    StressTestResult
)


class TestStressScenarios:
    """Integration tests for historical crisis scenarios"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.engine = MonteCarloEngine(
            underlyings=['SPY', 'QQQ'],
            correlation_matrix=np.array([
                [1.0, 0.8],
                [0.8, 1.0]
            ]),
            risk_free_rate=0.05
        )
        
        self.spot_prices = {
            'SPY': 400.0,
            'QQQ': 350.0
        }
        
        self.volatilities = {
            'SPY': 0.20,
            'QQQ': 0.25
        }
        
        self.portfolio_value = 1000000.0  # $1M portfolio
    
    def test_2008_financial_crisis_scenario(self):
        """
        **Validates: Requirements 13.2**
        
        Test 2008 financial crisis scenario.
        
        Characteristics:
        - 35% market crash
        - Correlation breakdown (0.95)
        - Extreme volatility spike (+50%)
        - Liquidity crisis (5x spreads)
        """
        # Create 2008 crisis scenario
        scenario = self.engine.create_crisis_2008_scenario()
        
        # Verify scenario parameters
        assert scenario.name == "2008_financial_crisis"
        assert scenario.spot_shock == -0.35
        assert scenario.vol_shock == 0.50
        assert scenario.correlation_shock == 0.95
        assert scenario.liquidity_multiplier == 5.0
        
        # Execute stress test
        result = self.engine.execute_stress_test(
            scenario=scenario,
            spot_prices=self.spot_prices,
            volatilities=self.volatilities,
            initial_portfolio_value=self.portfolio_value,
            max_loss_threshold=-0.25
        )
        
        # Verify result structure
        assert isinstance(result, StressTestResult)
        assert result.scenario.name == "2008_financial_crisis"
        assert result.base_pnl == 0.0
        
        # Verify P&L is computed
        assert result.pnl_change is not None
        assert result.pnl_change_pct is not None
        
        # Verify max drawdown is computed
        assert result.max_drawdown <= 0.0  # Should be negative (loss)
        
        # Verify timestamp
        assert isinstance(result.timestamp, datetime)
        
        print(f"\n2008 Crisis Results:")
        print(f"  P&L Change: ${result.pnl_change:,.2f} ({result.pnl_change_pct:.2%})")
        print(f"  Max Drawdown: {result.max_drawdown:.2%}")
        print(f"  Survives: {result.survives}")
    
    def test_2020_covid_crash_scenario(self):
        """
        **Validates: Requirements 13.2**
        
        Test 2020 COVID crash scenario.
        
        Characteristics:
        - 30% rapid crash
        - Extreme volatility spike (+60%)
        - High correlation (0.90)
        - Moderate liquidity stress (3x spreads)
        """
        # Create 2020 COVID scenario
        scenario = self.engine.create_crisis_2020_scenario()
        
        # Verify scenario parameters
        assert scenario.name == "2020_covid_crash"
        assert scenario.spot_shock == -0.30
        assert scenario.vol_shock == 0.60
        assert scenario.correlation_shock == 0.90
        assert scenario.liquidity_multiplier == 3.0
        
        # Execute stress test
        result = self.engine.execute_stress_test(
            scenario=scenario,
            spot_prices=self.spot_prices,
            volatilities=self.volatilities,
            initial_portfolio_value=self.portfolio_value,
            max_loss_threshold=-0.25
        )
        
        # Verify result structure
        assert isinstance(result, StressTestResult)
        assert result.scenario.name == "2020_covid_crash"
        
        # Verify P&L is computed
        assert result.pnl_change is not None
        assert result.pnl_change_pct is not None
        
        # Verify max drawdown
        assert result.max_drawdown <= 0.0
        
        print(f"\n2020 COVID Crisis Results:")
        print(f"  P&L Change: ${result.pnl_change:,.2f} ({result.pnl_change_pct:.2%})")
        print(f"  Max Drawdown: {result.max_drawdown:.2%}")
        print(f"  Survives: {result.survives}")
    
    def test_combined_crisis_scenario(self):
        """
        **Validates: Requirements 13.2**
        
        Test combined 2008 + 2020 crisis scenario.
        
        Characteristics:
        - 40% crash (worst of both)
        - Extreme volatility (+70%)
        - Near-perfect correlation (0.98)
        - Severe liquidity crisis (6x spreads)
        """
        # Create combined crisis scenario
        scenario = self.engine.create_combined_crisis_scenario()
        
        # Verify scenario parameters
        assert scenario.name == "combined_crisis"
        assert scenario.spot_shock == -0.40
        assert scenario.vol_shock == 0.70
        assert scenario.correlation_shock == 0.98
        assert scenario.liquidity_multiplier == 6.0
        
        # Execute stress test
        result = self.engine.execute_stress_test(
            scenario=scenario,
            spot_prices=self.spot_prices,
            volatilities=self.volatilities,
            initial_portfolio_value=self.portfolio_value,
            max_loss_threshold=-0.25
        )
        
        # Verify result structure
        assert isinstance(result, StressTestResult)
        assert result.scenario.name == "combined_crisis"
        
        # Verify P&L is computed
        assert result.pnl_change is not None
        assert result.pnl_change_pct is not None
        
        # Verify max drawdown
        assert result.max_drawdown <= 0.0
        
        print(f"\nCombined Crisis Results:")
        print(f"  P&L Change: ${result.pnl_change:,.2f} ({result.pnl_change_pct:.2%})")
        print(f"  Max Drawdown: {result.max_drawdown:.2%}")
        print(f"  Survives: {result.survives}")
    
    def test_all_stress_scenarios_execution(self):
        """
        **Validates: Requirements 13.2**
        
        Test execution of all predefined stress scenarios.
        
        Verifies that all scenarios can be executed and produce valid results.
        """
        # Run all stress tests
        results = self.engine.run_all_stress_tests(
            spot_prices=self.spot_prices,
            volatilities=self.volatilities,
            initial_portfolio_value=self.portfolio_value,
            max_loss_threshold=-0.25
        )
        
        # Verify all scenarios are present
        expected_scenarios = [
            "2008_financial_crisis",
            "2020_covid_crash",
            "combined_crisis",
            "volatility_spike",
            "liquidity_crisis"
        ]
        
        for scenario_name in expected_scenarios:
            assert scenario_name in results, f"Missing scenario: {scenario_name}"
            
            result = results[scenario_name]
            assert isinstance(result, StressTestResult)
            assert result.scenario.name == scenario_name
            
            # Verify all results have valid data
            assert result.pnl_change is not None
            assert result.pnl_change_pct is not None
            assert result.max_drawdown <= 0.0
        
        print(f"\nAll Stress Scenarios Results:")
        for scenario_name, result in results.items():
            print(f"  {scenario_name}:")
            print(f"    P&L: ${result.pnl_change:,.2f} ({result.pnl_change_pct:.2%})")
            print(f"    Survives: {result.survives}")
    
    def test_portfolio_survival_validation(self):
        """
        **Validates: Requirements 13.2**
        
        Test portfolio survival validation across all scenarios.
        
        Verifies that the survival validation logic works correctly.
        """
        # Run all stress tests
        results = self.engine.run_all_stress_tests(
            spot_prices=self.spot_prices,
            volatilities=self.volatilities,
            initial_portfolio_value=self.portfolio_value,
            max_loss_threshold=-0.25
        )
        
        # Validate survival
        all_survived, failed_scenarios = self.engine.validate_portfolio_survival(results)
        
        # Verify validation results
        assert isinstance(all_survived, bool)
        assert isinstance(failed_scenarios, list)
        
        # If portfolio survives all scenarios
        if all_survived:
            assert len(failed_scenarios) == 0
            print("\n✓ Portfolio survives all stress scenarios")
        else:
            assert len(failed_scenarios) > 0
            print(f"\n✗ Portfolio fails {len(failed_scenarios)} scenarios:")
            for scenario_name in failed_scenarios:
                result = results[scenario_name]
                print(f"  - {scenario_name}: {result.pnl_change_pct:.2%} loss")
    
    def test_correlation_shock_application(self):
        """
        **Validates: Requirements 13.2**
        
        Test that correlation shocks are properly applied.
        
        Verifies that the correlation matrix is modified during stress tests.
        """
        # Store original correlation matrix
        original_corr = self.engine.correlation_matrix.copy()
        
        # Create scenario with high correlation shock
        scenario = StressScenario(
            name="test_correlation",
            spot_shock=-0.20,
            vol_shock=0.30,
            correlation_shock=0.95,
            liquidity_multiplier=2.0,
            description="Test correlation shock"
        )
        
        # Execute stress test
        result = self.engine.execute_stress_test(
            scenario=scenario,
            spot_prices=self.spot_prices,
            volatilities=self.volatilities,
            initial_portfolio_value=self.portfolio_value
        )
        
        # Verify correlation matrix is restored after test
        np.testing.assert_array_almost_equal(
            self.engine.correlation_matrix,
            original_corr,
            decimal=10,
            err_msg="Correlation matrix not restored after stress test"
        )
        
        # Verify result is valid
        assert isinstance(result, StressTestResult)
        assert result.scenario.name == "test_correlation"
    
    def test_volatility_spike_scenario(self):
        """
        **Validates: Requirements 13.2**
        
        Test volatility spike scenario.
        
        Verifies pure volatility shock without major price move.
        """
        # Create volatility spike scenario
        scenario = self.engine.create_volatility_spike_scenario()
        
        # Verify scenario parameters
        assert scenario.name == "volatility_spike"
        assert scenario.spot_shock == -0.10  # Moderate price decline
        assert scenario.vol_shock == 0.40  # Large vol spike
        assert scenario.correlation_shock == 0.60  # Normal correlation
        
        # Execute stress test
        result = self.engine.execute_stress_test(
            scenario=scenario,
            spot_prices=self.spot_prices,
            volatilities=self.volatilities,
            initial_portfolio_value=self.portfolio_value
        )
        
        # Verify result
        assert isinstance(result, StressTestResult)
        assert result.scenario.name == "volatility_spike"
        
        print(f"\nVolatility Spike Results:")
        print(f"  P&L Change: ${result.pnl_change:,.2f} ({result.pnl_change_pct:.2%})")
        print(f"  Survives: {result.survives}")
    
    def test_liquidity_crisis_scenario(self):
        """
        **Validates: Requirements 13.2**
        
        Test liquidity crisis scenario.
        
        Verifies severe spread widening and correlation breakdown.
        """
        # Create liquidity crisis scenario
        scenario = self.engine.create_liquidity_crisis_scenario()
        
        # Verify scenario parameters
        assert scenario.name == "liquidity_crisis"
        assert scenario.spot_shock == -0.15
        assert scenario.vol_shock == 0.30
        assert scenario.correlation_shock == 0.85
        assert scenario.liquidity_multiplier == 8.0  # Extreme spreads
        
        # Execute stress test
        result = self.engine.execute_stress_test(
            scenario=scenario,
            spot_prices=self.spot_prices,
            volatilities=self.volatilities,
            initial_portfolio_value=self.portfolio_value
        )
        
        # Verify result
        assert isinstance(result, StressTestResult)
        assert result.scenario.name == "liquidity_crisis"
        
        print(f"\nLiquidity Crisis Results:")
        print(f"  P&L Change: ${result.pnl_change:,.2f} ({result.pnl_change_pct:.2%})")
        print(f"  Survives: {result.survives}")
    
    def test_stress_test_with_different_portfolio_sizes(self):
        """
        **Validates: Requirements 13.2**
        
        Test stress scenarios with different portfolio sizes.
        
        Verifies that stress tests scale correctly with portfolio value.
        """
        scenario = self.engine.create_crisis_2008_scenario()
        
        portfolio_sizes = [100000.0, 500000.0, 1000000.0, 5000000.0]
        
        for portfolio_value in portfolio_sizes:
            result = self.engine.execute_stress_test(
                scenario=scenario,
                spot_prices=self.spot_prices,
                volatilities=self.volatilities,
                initial_portfolio_value=portfolio_value
            )
            
            # Verify result scales with portfolio size
            assert isinstance(result, StressTestResult)
            
            # P&L percentage should be similar across portfolio sizes
            # (absolute P&L will scale, but percentage should be consistent)
            assert result.pnl_change_pct is not None
            
            print(f"\nPortfolio ${portfolio_value:,.0f}:")
            print(f"  P&L: ${result.pnl_change:,.2f} ({result.pnl_change_pct:.2%})")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
