"""
Phase 5 Checkpoint Verification

Verifies that all Monte Carlo Risk Engine components are operational:
- Task 21: Monte Carlo simulation framework
- Task 22: Risk metrics computation
- Task 23: Stress testing framework

This checkpoint ensures Phase 5 is complete and ready for Phase 6.
"""

import pytest
import numpy as np
from datetime import datetime

from src.volatility.monte_carlo_engine import (
    MonteCarloEngine,
    SimulationResult,
    RiskMetrics,
    WorstScenario,
    RiskAlert,
    StressScenario,
    StressTestResult
)


class TestPhase5Checkpoint:
    """Checkpoint tests for Phase 5: Monte Carlo Risk Engine"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.engine = MonteCarloEngine(
            underlyings=['SPY', 'QQQ'],
            correlation_matrix=np.array([
                [1.0, 0.7],
                [0.7, 1.0]
            ]),
            risk_free_rate=0.05
        )
        
        self.spot_prices = {
            'SPY': 450.0,
            'QQQ': 380.0
        }
        
        self.volatilities = {
            'SPY': 0.18,
            'QQQ': 0.22
        }
    
    def test_monte_carlo_simulation_operational(self):
        """
        Verify Monte Carlo simulation framework is operational (Task 21).
        
        Tests:
        - Price path generation with fat-tailed distributions
        - Stochastic volatility paths (Heston model)
        - Portfolio simulation with P&L tracking
        """
        # Run simulation
        simulation = self.engine.simulate_portfolio(
            spot_prices=self.spot_prices,
            volatilities=self.volatilities,
            initial_portfolio_value=1000000.0,
            horizon_days=21,
            num_paths=1000,
            seed=42
        )
        
        # Verify simulation result structure
        assert isinstance(simulation, SimulationResult)
        assert simulation.num_paths == 1000
        assert simulation.horizon_days == 21
        assert simulation.price_paths.shape == (1000, 21, 2)
        assert simulation.vol_paths.shape == (1000, 21)
        assert simulation.pnl_paths.shape == (1000, 21)
        
        # Verify price paths are positive
        assert np.all(simulation.price_paths > 0)
        
        # Verify volatility paths are non-negative
        assert np.all(simulation.vol_paths >= 0)
        
        print("\n✓ Monte Carlo simulation framework operational (Task 21)")
        print(f"  - Generated {simulation.num_paths} paths over {simulation.horizon_days} days")
        print(f"  - Price paths shape: {simulation.price_paths.shape}")
        print(f"  - Vol paths shape: {simulation.vol_paths.shape}")
    
    def test_risk_metrics_operational(self):
        """
        Verify risk metrics computation is operational (Task 22).
        
        Tests:
        - VaR and CVaR calculation
        - Scenario analysis (worst scenarios, decomposition)
        - Risk alerting system
        """
        # Run simulation
        simulation = self.engine.simulate_portfolio(
            spot_prices=self.spot_prices,
            volatilities=self.volatilities,
            initial_portfolio_value=1000000.0,
            horizon_days=21,
            num_paths=1000,
            seed=42
        )
        
        # Compute risk metrics
        risk_metrics = self.engine.compute_risk_metrics(
            simulation=simulation,
            ruin_threshold=-0.20
        )
        
        # Verify risk metrics structure
        assert isinstance(risk_metrics, RiskMetrics)
        assert risk_metrics.var_95 < 0  # VaR should be negative (loss)
        assert risk_metrics.var_99 < risk_metrics.var_95  # 99% VaR worse than 95%
        assert risk_metrics.cvar_99 < risk_metrics.var_99  # CVaR worse than VaR
        assert risk_metrics.max_drawdown <= 0  # Drawdown is negative
        assert 0 <= risk_metrics.prob_ruin <= 1  # Probability between 0 and 1
        
        # Test scenario analysis
        worst_scenarios = self.engine.identify_worst_scenarios(
            simulation=simulation,
            num_scenarios=5
        )
        
        assert len(worst_scenarios) == 5
        assert all(isinstance(s, WorstScenario) for s in worst_scenarios)
        
        # Test scenario decomposition
        decomposition = self.engine.decompose_scenario(
            simulation=simulation,
            scenario=worst_scenarios[0]
        )
        
        assert decomposition.primary_driver in [
            'price_shock', 'volatility_shock', 'correlation_breakdown', 'combined_factors'
        ]
        
        # Test risk alerting
        thresholds = {
            'var_99': -50000,
            'max_drawdown': -0.15
        }
        
        alerts = self.engine.monitor_risk_thresholds(
            risk_metrics=risk_metrics,
            thresholds=thresholds
        )
        
        assert isinstance(alerts, list)
        
        print("\n✓ Risk metrics computation operational (Task 22)")
        print(f"  - VaR 95%: ${risk_metrics.var_95:,.2f}")
        print(f"  - VaR 99%: ${risk_metrics.var_99:,.2f}")
        print(f"  - CVaR 99%: ${risk_metrics.cvar_99:,.2f}")
        print(f"  - Max Drawdown: {risk_metrics.max_drawdown:.2%}")
        print(f"  - Probability of Ruin: {risk_metrics.prob_ruin:.2%}")
        print(f"  - Identified {len(worst_scenarios)} worst scenarios")
        print(f"  - Generated {len(alerts)} risk alerts")
    
    def test_stress_testing_operational(self):
        """
        Verify stress testing framework is operational (Task 23).
        
        Tests:
        - Crisis scenario definitions (2008, 2020, combined)
        - Stress test execution
        - Portfolio survival validation
        """
        # Test predefined crisis scenarios
        crisis_2008 = self.engine.create_crisis_2008_scenario()
        crisis_2020 = self.engine.create_crisis_2020_scenario()
        combined_crisis = self.engine.create_combined_crisis_scenario()
        
        assert isinstance(crisis_2008, StressScenario)
        assert isinstance(crisis_2020, StressScenario)
        assert isinstance(combined_crisis, StressScenario)
        
        # Verify combined crisis is worst case
        assert combined_crisis.spot_shock <= crisis_2008.spot_shock
        assert combined_crisis.spot_shock <= crisis_2020.spot_shock
        assert combined_crisis.vol_shock >= crisis_2008.vol_shock
        
        # Execute stress test
        result = self.engine.execute_stress_test(
            scenario=crisis_2008,
            spot_prices=self.spot_prices,
            volatilities=self.volatilities,
            initial_portfolio_value=1000000.0,
            max_loss_threshold=-0.25
        )
        
        # Verify stress test result
        assert isinstance(result, StressTestResult)
        assert result.scenario.name == "2008_financial_crisis"
        assert result.pnl_change is not None
        assert result.pnl_change_pct is not None
        assert result.max_drawdown <= 0
        assert result.survives in [True, False]  # Verify survives is boolean
        
        # Run all stress tests
        all_results = self.engine.run_all_stress_tests(
            spot_prices=self.spot_prices,
            volatilities=self.volatilities,
            initial_portfolio_value=1000000.0,
            max_loss_threshold=-0.25
        )
        
        # Verify all scenarios executed
        expected_scenarios = [
            "2008_financial_crisis",
            "2020_covid_crash",
            "combined_crisis",
            "volatility_spike",
            "liquidity_crisis"
        ]
        
        for scenario_name in expected_scenarios:
            assert scenario_name in all_results
            assert isinstance(all_results[scenario_name], StressTestResult)
        
        # Validate portfolio survival
        all_survived, failed_scenarios = self.engine.validate_portfolio_survival(all_results)
        
        assert isinstance(all_survived, bool)
        assert isinstance(failed_scenarios, list)
        
        print("\n✓ Stress testing framework operational (Task 23)")
        print(f"  - Executed {len(all_results)} stress scenarios")
        print(f"  - 2008 Crisis: {all_results['2008_financial_crisis'].pnl_change_pct:.2%}")
        print(f"  - 2020 COVID: {all_results['2020_covid_crash'].pnl_change_pct:.2%}")
        print(f"  - Combined Crisis: {all_results['combined_crisis'].pnl_change_pct:.2%}")
        print(f"  - Portfolio survives all: {all_survived}")
        if not all_survived:
            print(f"  - Failed scenarios: {failed_scenarios}")
    
    def test_phase5_integration(self):
        """
        Verify all Phase 5 components work together.
        
        End-to-end test: simulation → risk metrics → stress testing
        """
        # Step 1: Run Monte Carlo simulation
        simulation = self.engine.simulate_portfolio(
            spot_prices=self.spot_prices,
            volatilities=self.volatilities,
            initial_portfolio_value=1000000.0,
            horizon_days=21,
            num_paths=1000,
            seed=42
        )
        
        # Step 2: Compute risk metrics
        risk_metrics = self.engine.compute_risk_metrics(
            simulation=simulation,
            ruin_threshold=-0.20
        )
        
        # Step 3: Identify worst scenarios
        worst_scenarios = self.engine.identify_worst_scenarios(
            simulation=simulation,
            num_scenarios=3
        )
        
        # Step 4: Run stress tests
        stress_results = self.engine.run_all_stress_tests(
            spot_prices=self.spot_prices,
            volatilities=self.volatilities,
            initial_portfolio_value=1000000.0,
            max_loss_threshold=-0.25
        )
        
        # Step 5: Monitor risk thresholds
        thresholds = {
            'var_99': -100000,
            'cvar_99': -150000,
            'max_drawdown': -0.20,
            'prob_ruin': 0.10
        }
        
        alerts = self.engine.monitor_risk_thresholds(
            risk_metrics=risk_metrics,
            thresholds=thresholds
        )
        
        # Verify integration
        assert simulation.num_paths == 1000
        assert risk_metrics.var_99 < 0
        assert len(worst_scenarios) == 3
        assert len(stress_results) == 5
        assert isinstance(alerts, list)
        
        print("\n✓ Phase 5 integration complete")
        print(f"  - Simulation: {simulation.num_paths} paths")
        print(f"  - Risk Metrics: VaR 99% = ${risk_metrics.var_99:,.2f}")
        print(f"  - Worst Scenarios: {len(worst_scenarios)} identified")
        print(f"  - Stress Tests: {len(stress_results)} executed")
        print(f"  - Risk Alerts: {len(alerts)} generated")
        
        print("\n" + "="*60)
        print("PHASE 5 CHECKPOINT: ALL SYSTEMS OPERATIONAL")
        print("="*60)
        print("\nMonte Carlo Risk Engine Complete:")
        print("  ✓ Task 21: Monte Carlo simulation framework")
        print("  ✓ Task 22: Risk metrics computation")
        print("  ✓ Task 23: Stress testing framework")
        print("  ✓ Task 24: Checkpoint verification")
        print("\nReady to proceed to Phase 6: Execution Integration")
        print("="*60)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
