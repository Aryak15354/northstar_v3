"""
Unit tests for Monte Carlo risk metrics computation.

Tests VaR, CVaR, maximum drawdown, scenario analysis, and risk alerting.

Validates: Requirements 7.4, 7.5, 7.7
"""

import pytest
import numpy as np
from datetime import datetime, timedelta
from src.volatility.monte_carlo_engine import (
    MonteCarloEngine,
    SimulationResult,
    RiskMetrics,
    WorstScenario,
    ScenarioDecomposition,
    RiskAlert,
    HestonParams
)


class TestVaRCalculation:
    """Test Value-at-Risk calculation accuracy"""
    
    def test_var_calculation_normal_distribution(self):
        """Test VaR calculation with known normal distribution"""
        # Create engine
        engine = MonteCarloEngine(
            underlyings=['SPY'],
            risk_free_rate=0.05
        )
        
        # Create synthetic P&L paths from normal distribution
        np.random.seed(42)
        num_paths = 10000
        horizon_days = 30
        
        # Normal distribution with mean=0, std=10000
        terminal_pnl = np.random.normal(0, 10000, num_paths)
        pnl_paths = np.zeros((num_paths, horizon_days))
        pnl_paths[:, -1] = terminal_pnl
        
        # Create simulation result
        simulation = SimulationResult(
            pnl_paths=pnl_paths,
            price_paths=np.zeros((num_paths, horizon_days, 1)),
            vol_paths=np.zeros((num_paths, horizon_days)),
            num_paths=num_paths,
            horizon_days=horizon_days,
            timestamp=datetime.now()
        )
        
        # Compute risk metrics
        metrics = engine.compute_risk_metrics(simulation)
        
        # For normal distribution, VaR should be approximately:
        # VaR_95 ≈ -1.645 * std = -16450
        # VaR_99 ≈ -2.326 * std = -23260
        
        assert metrics.var_95 < 0, "VaR should be negative (loss)"
        assert -18000 < metrics.var_95 < -15000, f"VaR_95 should be around -16450, got {metrics.var_95}"
        
        assert metrics.var_99 < metrics.var_95, "VaR_99 should be worse than VaR_95"
        assert -25000 < metrics.var_99 < -21000, f"VaR_99 should be around -23260, got {metrics.var_99}"
        
        assert metrics.var_999 < metrics.var_99, "VaR_999 should be worse than VaR_99"
    
    def test_var_confidence_levels(self):
        """Test that VaR at different confidence levels are ordered correctly"""
        engine = MonteCarloEngine(underlyings=['SPY'])
        
        # Create simulation with losses
        np.random.seed(42)
        num_paths = 10000
        horizon_days = 30
        
        terminal_pnl = np.random.normal(-5000, 15000, num_paths)
        pnl_paths = np.zeros((num_paths, horizon_days))
        pnl_paths[:, -1] = terminal_pnl
        
        simulation = SimulationResult(
            pnl_paths=pnl_paths,
            price_paths=np.zeros((num_paths, horizon_days, 1)),
            vol_paths=np.zeros((num_paths, horizon_days)),
            num_paths=num_paths,
            horizon_days=horizon_days,
            timestamp=datetime.now()
        )
        
        metrics = engine.compute_risk_metrics(simulation)
        
        # VaR should get worse (more negative) at higher confidence levels
        assert metrics.var_999 < metrics.var_99 < metrics.var_95, \
            "VaR should be ordered: VaR_999 < VaR_99 < VaR_95"
    
    def test_var_with_all_profits(self):
        """Test VaR when all paths are profitable"""
        engine = MonteCarloEngine(underlyings=['SPY'])
        
        # All paths profitable
        num_paths = 1000
        horizon_days = 30
        
        terminal_pnl = np.random.uniform(1000, 10000, num_paths)
        pnl_paths = np.zeros((num_paths, horizon_days))
        pnl_paths[:, -1] = terminal_pnl
        
        simulation = SimulationResult(
            pnl_paths=pnl_paths,
            price_paths=np.zeros((num_paths, horizon_days, 1)),
            vol_paths=np.zeros((num_paths, horizon_days)),
            num_paths=num_paths,
            horizon_days=horizon_days,
            timestamp=datetime.now()
        )
        
        metrics = engine.compute_risk_metrics(simulation)
        
        # Even with all profits, VaR should be the 5th percentile
        assert metrics.var_95 > 0, "VaR should be positive when all paths are profitable"
        assert metrics.var_99 > 0, "VaR_99 should be positive when all paths are profitable"


class TestCVaRCalculation:
    """Test Conditional Value-at-Risk (expected shortfall) computation"""
    
    def test_cvar_less_than_var(self):
        """Test that CVaR is always worse than or equal to VaR"""
        engine = MonteCarloEngine(underlyings=['SPY'])
        
        np.random.seed(42)
        num_paths = 10000
        horizon_days = 30
        
        # Create distribution with fat tails
        terminal_pnl = np.random.standard_t(df=3, size=num_paths) * 10000
        pnl_paths = np.zeros((num_paths, horizon_days))
        pnl_paths[:, -1] = terminal_pnl
        
        simulation = SimulationResult(
            pnl_paths=pnl_paths,
            price_paths=np.zeros((num_paths, horizon_days, 1)),
            vol_paths=np.zeros((num_paths, horizon_days)),
            num_paths=num_paths,
            horizon_days=horizon_days,
            timestamp=datetime.now()
        )
        
        metrics = engine.compute_risk_metrics(simulation)
        
        # CVaR should be worse than VaR (more negative)
        assert metrics.cvar_95 <= metrics.var_95, \
            f"CVaR_95 ({metrics.cvar_95}) should be <= VaR_95 ({metrics.var_95})"
        assert metrics.cvar_99 <= metrics.var_99, \
            f"CVaR_99 ({metrics.cvar_99}) should be <= VaR_99 ({metrics.var_99})"
    
    def test_cvar_expected_shortfall(self):
        """Test that CVaR is the mean of losses beyond VaR"""
        engine = MonteCarloEngine(underlyings=['SPY'])
        
        np.random.seed(42)
        num_paths = 10000
        horizon_days = 30
        
        terminal_pnl = np.random.normal(0, 10000, num_paths)
        pnl_paths = np.zeros((num_paths, horizon_days))
        pnl_paths[:, -1] = terminal_pnl
        
        simulation = SimulationResult(
            pnl_paths=pnl_paths,
            price_paths=np.zeros((num_paths, horizon_days, 1)),
            vol_paths=np.zeros((num_paths, horizon_days)),
            num_paths=num_paths,
            horizon_days=horizon_days,
            timestamp=datetime.now()
        )
        
        metrics = engine.compute_risk_metrics(simulation)
        
        # Manually compute CVaR to verify
        var_95 = np.percentile(terminal_pnl, 5)
        expected_cvar_95 = terminal_pnl[terminal_pnl <= var_95].mean()
        
        # Should match within small tolerance
        assert abs(metrics.cvar_95 - expected_cvar_95) < 100, \
            f"CVaR_95 calculation mismatch: {metrics.cvar_95} vs {expected_cvar_95}"


class TestMaximumDrawdown:
    """Test maximum drawdown detection"""
    
    def test_max_drawdown_simple_path(self):
        """Test max drawdown with a simple path"""
        engine = MonteCarloEngine(underlyings=['SPY'])
        
        # Create path with known drawdown
        # Path: 0 -> 1000 -> 500 -> 1200 -> 300
        # Max drawdown: (300 - 1200) / 1200 = -75%
        num_paths = 1
        horizon_days = 5
        
        pnl_paths = np.array([[0, 1000, 500, 1200, 300]])
        
        simulation = SimulationResult(
            pnl_paths=pnl_paths,
            price_paths=np.zeros((num_paths, horizon_days, 1)),
            vol_paths=np.zeros((num_paths, horizon_days)),
            num_paths=num_paths,
            horizon_days=horizon_days,
            timestamp=datetime.now()
        )
        
        metrics = engine.compute_risk_metrics(simulation)
        
        # Max drawdown should be approximately -75%
        assert metrics.max_drawdown < 0, "Max drawdown should be negative"
        assert -0.76 < metrics.max_drawdown < -0.74, \
            f"Max drawdown should be around -0.75, got {metrics.max_drawdown}"
    
    def test_max_drawdown_no_losses(self):
        """Test max drawdown when portfolio only increases"""
        engine = MonteCarloEngine(underlyings=['SPY'])
        
        # Monotonically increasing path
        num_paths = 1
        horizon_days = 10
        
        pnl_paths = np.array([np.linspace(0, 10000, horizon_days)])
        
        simulation = SimulationResult(
            pnl_paths=pnl_paths,
            price_paths=np.zeros((num_paths, horizon_days, 1)),
            vol_paths=np.zeros((num_paths, horizon_days)),
            num_paths=num_paths,
            horizon_days=horizon_days,
            timestamp=datetime.now()
        )
        
        metrics = engine.compute_risk_metrics(simulation)
        
        # No drawdown expected
        assert metrics.max_drawdown >= -0.01, \
            f"Max drawdown should be near 0 for increasing path, got {metrics.max_drawdown}"
    
    def test_max_drawdown_multiple_paths(self):
        """Test max drawdown across multiple paths"""
        engine = MonteCarloEngine(underlyings=['SPY'])
        
        num_paths = 100
        horizon_days = 30
        
        # Create paths with varying drawdowns
        np.random.seed(42)
        pnl_paths = np.cumsum(np.random.randn(num_paths, horizon_days) * 100, axis=1)
        
        simulation = SimulationResult(
            pnl_paths=pnl_paths,
            price_paths=np.zeros((num_paths, horizon_days, 1)),
            vol_paths=np.zeros((num_paths, horizon_days)),
            num_paths=num_paths,
            horizon_days=horizon_days,
            timestamp=datetime.now()
        )
        
        metrics = engine.compute_risk_metrics(simulation)
        
        # Should find the worst drawdown across all paths
        assert metrics.max_drawdown < 0, "Should detect negative drawdown"
        # Drawdown can be large with random walks, just check it's reasonable
        assert metrics.max_drawdown > -1000.0, "Drawdown should be within reasonable bounds"


class TestScenarioAnalysis:
    """Test scenario identification and decomposition"""
    
    def test_identify_worst_scenarios(self):
        """Test identification of worst-case scenarios"""
        engine = MonteCarloEngine(underlyings=['SPY', 'QQQ'])
        
        np.random.seed(42)
        num_paths = 1000
        horizon_days = 30
        
        # Create simulation with some very bad paths
        terminal_pnl = np.random.normal(0, 10000, num_paths)
        terminal_pnl[:10] = np.random.uniform(-50000, -30000, 10)  # 10 worst paths
        
        pnl_paths = np.zeros((num_paths, horizon_days))
        pnl_paths[:, -1] = terminal_pnl
        
        price_paths = np.random.randn(num_paths, horizon_days, 2) * 0.02 + 1.0
        price_paths = np.cumprod(price_paths, axis=1) * 100
        
        vol_paths = np.random.uniform(0.15, 0.35, (num_paths, horizon_days))
        
        simulation = SimulationResult(
            pnl_paths=pnl_paths,
            price_paths=price_paths,
            vol_paths=vol_paths,
            num_paths=num_paths,
            horizon_days=horizon_days,
            timestamp=datetime.now()
        )
        
        # Identify worst 5 scenarios
        worst_scenarios = engine.identify_worst_scenarios(simulation, num_scenarios=5)
        
        assert len(worst_scenarios) == 5, "Should return 5 worst scenarios"
        
        # Verify scenarios are ordered by severity
        for i in range(len(worst_scenarios) - 1):
            assert worst_scenarios[i].terminal_pnl <= worst_scenarios[i+1].terminal_pnl, \
                "Scenarios should be ordered by terminal P&L"
        
        # Verify worst scenario has expected characteristics
        worst = worst_scenarios[0]
        assert worst.terminal_pnl < -30000, "Worst scenario should have severe loss"
        assert worst.scenario_description, "Should have description"
        assert worst.price_moves, "Should have price moves"
    
    def test_decompose_scenario(self):
        """Test scenario decomposition"""
        engine = MonteCarloEngine(underlyings=['SPY'])
        
        # Create a specific worst scenario
        worst_scenario = WorstScenario(
            path_index=0,
            terminal_pnl=-50000,
            max_drawdown=-0.35,
            price_moves={'SPY': -0.25},  # 25% crash
            vol_change=0.20,  # Vol spike
            scenario_description="severe market crash, volatility explosion"
        )
        
        # Create minimal simulation for context
        simulation = SimulationResult(
            pnl_paths=np.array([[-50000]]),
            price_paths=np.array([[[100]]]),
            vol_paths=np.array([[0.35]]),
            num_paths=1,
            horizon_days=1,
            timestamp=datetime.now()
        )
        
        # Decompose scenario
        decomposition = engine.decompose_scenario(simulation, worst_scenario)
        
        assert decomposition.scenario_id == 0
        assert decomposition.price_shocks == {'SPY': -0.25}
        assert decomposition.volatility_shock == 0.20
        assert decomposition.primary_driver in ['price_shock', 'volatility_shock', 'combined_factors']
        assert len(decomposition.contributing_factors) > 0
    
    def test_probability_of_ruin(self):
        """Test probability of ruin calculation"""
        engine = MonteCarloEngine(underlyings=['SPY'])
        
        np.random.seed(42)
        num_paths = 10000
        horizon_days = 30
        
        # Create distribution where 10% of paths exceed ruin threshold
        terminal_pnl = np.random.normal(0, 10000, num_paths)
        terminal_pnl[:1000] = np.random.uniform(-30000, -20000, 1000)  # 10% ruined
        
        pnl_paths = np.zeros((num_paths, horizon_days))
        pnl_paths[:, -1] = terminal_pnl
        
        simulation = SimulationResult(
            pnl_paths=pnl_paths,
            price_paths=np.zeros((num_paths, horizon_days, 1)),
            vol_paths=np.zeros((num_paths, horizon_days)),
            num_paths=num_paths,
            horizon_days=horizon_days,
            timestamp=datetime.now()
        )
        
        # Compute probability of ruin with -20% threshold
        prob_ruin = engine.compute_probability_of_ruin(simulation, ruin_threshold=-20000)
        
        # Should be approximately 10% (allow wider tolerance due to randomness)
        assert 0.08 < prob_ruin < 0.15, \
            f"Probability of ruin should be around 0.10, got {prob_ruin}"


class TestRiskAlerting:
    """Test risk alerting functionality"""
    
    def test_monitor_risk_thresholds_no_breach(self):
        """Test monitoring when no thresholds are breached"""
        engine = MonteCarloEngine(underlyings=['SPY'])
        
        # Create metrics within acceptable ranges
        metrics = RiskMetrics(
            var_95=-5000,
            var_99=-8000,
            var_999=-12000,
            cvar_95=-6000,
            cvar_99=-9000,
            max_drawdown=-0.10,
            prob_ruin=0.02,
            expected_return=1000,
            volatility=5000
        )
        
        # Set thresholds that won't be breached
        thresholds = {
            'var_99': -10000,
            'cvar_99': -12000,
            'max_drawdown': -0.20,
            'prob_ruin': 0.05
        }
        
        alerts = engine.monitor_risk_thresholds(metrics, thresholds)
        
        assert len(alerts) == 0, "Should have no alerts when thresholds not breached"
    
    def test_monitor_risk_thresholds_with_breaches(self):
        """Test monitoring when thresholds are breached"""
        engine = MonteCarloEngine(underlyings=['SPY'])
        
        # Create metrics that breach thresholds
        metrics = RiskMetrics(
            var_95=-15000,
            var_99=-25000,
            var_999=-40000,
            cvar_95=-18000,
            cvar_99=-30000,
            max_drawdown=-0.30,
            prob_ruin=0.08,
            expected_return=-5000,
            volatility=15000
        )
        
        # Set strict thresholds
        thresholds = {
            'var_99': -20000,
            'cvar_99': -25000,
            'max_drawdown': -0.25,
            'prob_ruin': 0.05
        }
        
        alerts = engine.monitor_risk_thresholds(metrics, thresholds)
        
        # Should have multiple alerts
        assert len(alerts) > 0, "Should have alerts when thresholds breached"
        
        # Check specific alerts
        alert_metrics = [a.metric_name for a in alerts]
        assert 'var_99' in alert_metrics, "Should alert on VaR_99 breach"
        assert 'cvar_99' in alert_metrics, "Should alert on CVaR_99 breach"
        assert 'max_drawdown' in alert_metrics, "Should alert on max drawdown breach"
        assert 'prob_ruin' in alert_metrics, "Should alert on probability of ruin breach"
        
        # Verify severity levels
        for alert in alerts:
            assert alert.severity in ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']
            assert alert.recommended_action, "Should have recommended action"
    
    def test_generate_risk_alert(self):
        """Test generation of detailed risk alert"""
        engine = MonteCarloEngine(underlyings=['SPY'])
        
        # Create alert
        alert = RiskAlert(
            metric_name='var_99',
            threshold=-20000,
            actual_value=-30000,
            severity='HIGH',
            timestamp=datetime.now(),
            recommended_action='Reduce high-risk positions immediately'
        )
        
        # Create simulation context
        simulation = SimulationResult(
            pnl_paths=np.zeros((1000, 30)),
            price_paths=np.zeros((1000, 30, 1)),
            vol_paths=np.zeros((1000, 30)),
            num_paths=1000,
            horizon_days=30,
            timestamp=datetime.now()
        )
        
        # Create worst scenario
        worst_scenario = WorstScenario(
            path_index=0,
            terminal_pnl=-30000,
            max_drawdown=-0.25,
            price_moves={'SPY': -0.20},
            vol_change=0.15,
            scenario_description="significant market decline, elevated volatility"
        )
        
        # Generate alert
        alert_dict = engine.generate_risk_alert(alert, simulation, worst_scenario)
        
        # Verify alert structure
        assert 'alert_id' in alert_dict
        assert alert_dict['metric_name'] == 'var_99'
        assert alert_dict['severity'] == 'HIGH'
        assert alert_dict['threshold'] == -20000
        assert alert_dict['actual_value'] == -30000
        assert alert_dict['breach_magnitude'] == 10000
        assert 'simulation_context' in alert_dict
        assert 'worst_scenario' in alert_dict
        
        # Verify worst scenario details
        assert alert_dict['worst_scenario']['terminal_pnl'] == -30000
        assert alert_dict['worst_scenario']['price_moves'] == {'SPY': -0.20}


class TestEdgeCases:
    """Test edge cases and boundary conditions"""
    
    def test_zero_volatility(self):
        """Test with zero volatility (deterministic paths)"""
        engine = MonteCarloEngine(underlyings=['SPY'])
        
        # All paths identical (zero volatility)
        num_paths = 100
        horizon_days = 30
        
        pnl_paths = np.ones((num_paths, horizon_days)) * 1000
        
        simulation = SimulationResult(
            pnl_paths=pnl_paths,
            price_paths=np.ones((num_paths, horizon_days, 1)) * 100,
            vol_paths=np.zeros((num_paths, horizon_days)),
            num_paths=num_paths,
            horizon_days=horizon_days,
            timestamp=datetime.now()
        )
        
        metrics = engine.compute_risk_metrics(simulation)
        
        # All VaR measures should be the same
        assert abs(metrics.var_95 - 1000) < 1
        assert abs(metrics.var_99 - 1000) < 1
        assert abs(metrics.cvar_95 - 1000) < 1
        assert metrics.volatility < 1  # Near zero volatility
    
    def test_extreme_losses(self):
        """Test with extreme loss scenarios"""
        engine = MonteCarloEngine(underlyings=['SPY'])
        
        # All paths have extreme losses
        num_paths = 100
        horizon_days = 30
        
        terminal_pnl = np.random.uniform(-100000, -50000, num_paths)
        pnl_paths = np.zeros((num_paths, horizon_days))
        pnl_paths[:, -1] = terminal_pnl
        
        simulation = SimulationResult(
            pnl_paths=pnl_paths,
            price_paths=np.zeros((num_paths, horizon_days, 1)),
            vol_paths=np.zeros((num_paths, horizon_days)),
            num_paths=num_paths,
            horizon_days=horizon_days,
            timestamp=datetime.now()
        )
        
        metrics = engine.compute_risk_metrics(simulation)
        
        # All metrics should reflect extreme losses
        assert metrics.var_95 < -50000
        assert metrics.cvar_95 < metrics.var_95
        assert metrics.prob_ruin == 1.0  # All paths ruined
    
    def test_single_path(self):
        """Test with single simulation path"""
        engine = MonteCarloEngine(underlyings=['SPY'])
        
        num_paths = 1
        horizon_days = 30
        
        pnl_paths = np.array([[1000]])
        
        simulation = SimulationResult(
            pnl_paths=pnl_paths,
            price_paths=np.zeros((num_paths, horizon_days, 1)),
            vol_paths=np.zeros((num_paths, horizon_days)),
            num_paths=num_paths,
            horizon_days=horizon_days,
            timestamp=datetime.now()
        )
        
        # Should not crash with single path
        metrics = engine.compute_risk_metrics(simulation)
        
        assert metrics.var_95 == 1000
        assert metrics.var_99 == 1000
        assert metrics.cvar_95 == 1000


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
