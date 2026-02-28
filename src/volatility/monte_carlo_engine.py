"""
Monte Carlo Risk Engine

Stochastic simulation system for tail risk modeling and scenario analysis.
Implements correlated price paths with fat-tailed distributions and stochastic volatility.

Validates: Requirements 7.1, 7.2, 13.4
"""

import numpy as np
from dataclasses import dataclass
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional, Tuple, Any
from scipy.stats import t as student_t


@dataclass
class SimulationResult:
    """Results from Monte Carlo simulation"""
    pnl_paths: np.ndarray  # Shape: (num_paths, horizon_days)
    price_paths: np.ndarray  # Shape: (num_paths, horizon_days, num_underlyings)
    vol_paths: np.ndarray  # Shape: (num_paths, horizon_days)
    num_paths: int
    horizon_days: int
    timestamp: datetime


@dataclass
class RiskMetrics:
    """Portfolio risk metrics from simulation"""
    var_95: float
    var_99: float
    var_999: float
    cvar_95: float
    cvar_99: float
    max_drawdown: float
    prob_ruin: float
    expected_return: float
    volatility: float


@dataclass
class WorstScenario:
    """Details of a worst-case scenario from simulation"""
    path_index: int
    terminal_pnl: float
    max_drawdown: float
    price_moves: Dict[str, float]  # Percentage moves for each underlying
    vol_change: float  # Change in volatility
    scenario_description: str


@dataclass
class ScenarioDecomposition:
    """Decomposition of what caused a scenario"""
    scenario_id: int
    price_shocks: Dict[str, float]  # Price changes by underlying
    volatility_shock: float
    correlation_impact: float
    time_decay_impact: float
    primary_driver: str  # What caused the loss
    contributing_factors: List[str]


@dataclass
class RiskAlert:
    """Risk alert when thresholds are breached"""
    metric_name: str
    threshold: float
    actual_value: float
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW
    timestamp: datetime
    scenario_details: Optional[ScenarioDecomposition] = None
    recommended_action: str = ""


@dataclass
class StressScenario:
    """Stress test scenario definition"""
    name: str
    spot_shock: float  # Percentage change (e.g., -0.35 for 35% crash)
    vol_shock: float  # Absolute change in volatility (e.g., +0.40)
    correlation_shock: float  # Target correlation level (e.g., 0.95)
    liquidity_multiplier: float  # Bid-ask spread multiplier
    description: str


@dataclass
class StressTestResult:
    """Results from stress test execution"""
    scenario: StressScenario
    base_pnl: float
    stressed_pnl: float
    pnl_change: float
    pnl_change_pct: float
    survives: bool  # Whether portfolio survives max loss threshold
    max_drawdown: float
    timestamp: datetime


@dataclass
class HestonParams:
    """Parameters for Heston stochastic volatility model"""
    kappa: float = 2.0  # Mean reversion speed
    theta: float = 0.04  # Long-term variance
    sigma_v: float = 0.3  # Vol of vol
    rho: float = -0.7  # Correlation between price and vol


class MonteCarloEngine:
    """
    Monte Carlo simulation engine for portfolio risk analysis.
    
    Features:
    - Correlated multi-asset price paths with fat-tailed distributions
    - Stochastic volatility using Heston model
    - Portfolio revaluation along simulated paths
    - Greeks evolution tracking
    - P&L distribution computation
    """
    
    def __init__(
        self,
        underlyings: List[str],
        correlation_matrix: Optional[np.ndarray] = None,
        risk_free_rate: float = 0.05,
        heston_params: Optional[HestonParams] = None
    ):
        """
        Initialize Monte Carlo engine.
        
        Args:
            underlyings: List of underlying asset symbols
            correlation_matrix: Correlation matrix for multi-asset paths (optional)
            risk_free_rate: Risk-free rate for drift calculation
            heston_params: Parameters for Heston volatility model (optional)
        """
        self.underlyings = underlyings
        self.num_underlyings = len(underlyings)
        self.risk_free_rate = risk_free_rate
        
        # Set correlation matrix (identity if not provided)
        if correlation_matrix is not None:
            self.correlation_matrix = correlation_matrix
        else:
            self.correlation_matrix = np.eye(self.num_underlyings)
        
        # Validate correlation matrix
        if self.correlation_matrix.shape != (self.num_underlyings, self.num_underlyings):
            raise ValueError(
                f"Correlation matrix shape {self.correlation_matrix.shape} "
                f"doesn't match number of underlyings {self.num_underlyings}"
            )
        
        # Set Heston parameters
        self.heston_params = heston_params or HestonParams()
        
        # Student-t degrees of freedom for fat tails
        self.student_t_df = 5
    
    def generate_price_paths(
        self,
        spot_prices: Dict[str, float],
        volatilities: Dict[str, float],
        horizon_days: int,
        num_paths: int,
        seed: Optional[int] = None
    ) -> np.ndarray:
        """
        Generate correlated price paths with fat-tailed distributions.
        
        Uses Student-t distribution with df=5 for realistic tail behavior.
        Implements geometric Brownian motion with fat-tailed innovations.
        
        Args:
            spot_prices: Current spot prices for each underlying
            volatilities: Current volatilities for each underlying
            horizon_days: Number of days to simulate
            num_paths: Number of Monte Carlo paths
            seed: Random seed for reproducibility (optional)
        
        Returns:
            Price paths array of shape (num_paths, horizon_days, num_underlyings)
        """
        if seed is not None:
            np.random.seed(seed)
        
        dt = 1 / 252  # Daily time steps
        
        # Initialize paths array
        paths = np.zeros((num_paths, horizon_days, self.num_underlyings))
        
        # Get initial prices and vols in order
        S0 = np.array([spot_prices[u] for u in self.underlyings])
        vols = np.array([volatilities[u] for u in self.underlyings])
        
        # Cholesky decomposition for correlation
        try:
            L = np.linalg.cholesky(self.correlation_matrix)
        except np.linalg.LinAlgError:
            # If correlation matrix is not positive definite, use identity
            L = np.eye(self.num_underlyings)
        
        # Generate paths
        for path_idx in range(num_paths):
            S = S0.copy()
            
            for day in range(horizon_days):
                # Generate correlated Student-t innovations
                # Student-t with df=5 for fat tails
                z_uncorrelated = student_t.rvs(
                    df=self.student_t_df,
                    size=self.num_underlyings
                )
                
                # Scale to have unit variance: Var(t_df) = df/(df-2)
                z_uncorrelated *= np.sqrt((self.student_t_df - 2) / self.student_t_df)
                
                # Apply correlation
                z = L @ z_uncorrelated
                
                # Geometric Brownian motion with fat-tailed innovations
                drift = (self.risk_free_rate - 0.5 * vols**2) * dt
                diffusion = vols * np.sqrt(dt) * z
                
                S = S * np.exp(drift + diffusion)
                paths[path_idx, day, :] = S
        
        return paths
    
    def generate_volatility_paths(
        self,
        initial_variance: float,
        horizon_days: int,
        num_paths: int,
        seed: Optional[int] = None
    ) -> np.ndarray:
        """
        Generate stochastic volatility paths using Heston model.
        
        Heston dynamics: dv = kappa*(theta - v)*dt + sigma_v*sqrt(v)*dW
        
        Args:
            initial_variance: Starting variance level
            horizon_days: Number of days to simulate
            num_paths: Number of Monte Carlo paths
            seed: Random seed for reproducibility (optional)
        
        Returns:
            Volatility paths array of shape (num_paths, horizon_days)
        """
        if seed is not None:
            np.random.seed(seed)
        
        dt = 1 / 252  # Daily time steps
        
        # Initialize paths array
        vol_paths = np.zeros((num_paths, horizon_days))
        
        # Heston parameters
        kappa = self.heston_params.kappa
        theta = self.heston_params.theta
        sigma_v = self.heston_params.sigma_v
        
        # Generate paths
        for path_idx in range(num_paths):
            v = initial_variance  # Start at initial variance
            
            for day in range(horizon_days):
                # Heston dynamics with Euler discretization
                dW = np.random.randn() * np.sqrt(dt)
                
                # Mean reversion + vol-of-vol term
                dv = kappa * (theta - v) * dt + sigma_v * np.sqrt(max(v, 0)) * dW
                v = v + dv
                
                # Ensure non-negative variance (full truncation scheme)
                v = max(v, 0)
                
                # Store volatility (sqrt of variance)
                vol_paths[path_idx, day] = np.sqrt(v)
        
        return vol_paths
    
    def simulate_portfolio(
        self,
        spot_prices: Dict[str, float],
        volatilities: Dict[str, float],
        initial_portfolio_value: float,
        horizon_days: int,
        num_paths: int = 10000,
        seed: Optional[int] = None
    ) -> SimulationResult:
        """
        Simulate portfolio P&L over horizon.
        
        Generates correlated price paths and stochastic volatility paths,
        then computes P&L evolution along each path.
        
        Args:
            spot_prices: Current spot prices for each underlying
            volatilities: Current volatilities for each underlying
            initial_portfolio_value: Starting portfolio value
            horizon_days: Number of days to simulate
            num_paths: Number of Monte Carlo paths
            seed: Random seed for reproducibility (optional)
        
        Returns:
            SimulationResult containing price paths, vol paths, and P&L paths
        """
        # Generate price paths
        price_paths = self.generate_price_paths(
            spot_prices=spot_prices,
            volatilities=volatilities,
            horizon_days=horizon_days,
            num_paths=num_paths,
            seed=seed
        )
        
        # Generate volatility paths (using average initial variance)
        avg_variance = np.mean([v**2 for v in volatilities.values()])
        vol_paths = self.generate_volatility_paths(
            initial_variance=avg_variance,
            horizon_days=horizon_days,
            num_paths=num_paths,
            seed=seed
        )
        
        # Compute P&L paths (simplified: based on price changes)
        # In a full implementation, this would revalue the entire portfolio
        # including options Greeks evolution
        pnl_paths = np.zeros((num_paths, horizon_days))
        
        for path_idx in range(num_paths):
            portfolio_value = initial_portfolio_value
            
            for day in range(horizon_days):
                # Simplified P&L: proportional to average price change
                avg_price_change = np.mean(
                    price_paths[path_idx, day, :] / 
                    (price_paths[path_idx, day-1, :] if day > 0 
                     else np.array([spot_prices[u] for u in self.underlyings]))
                ) - 1.0
                
                # Update portfolio value
                portfolio_value *= (1 + avg_price_change)
                pnl_paths[path_idx, day] = portfolio_value - initial_portfolio_value
        
        return SimulationResult(
            pnl_paths=pnl_paths,
            price_paths=price_paths,
            vol_paths=vol_paths,
            num_paths=num_paths,
            horizon_days=horizon_days,
            timestamp=datetime.now()
        )
    
    def compute_risk_metrics(
        self,
        simulation: SimulationResult,
        ruin_threshold: float = -0.20
    ) -> RiskMetrics:
        """
        Compute VaR, CVaR, and other risk metrics from simulation.
        
        Args:
            simulation: Simulation results
            ruin_threshold: Loss threshold for probability of ruin (default -20%)
        
        Returns:
            RiskMetrics with VaR, CVaR, max drawdown, etc.
        """
        # Terminal P&L distribution
        terminal_pnl = simulation.pnl_paths[:, -1]
        
        # Value at Risk (negative percentiles)
        var_95 = np.percentile(terminal_pnl, 5)
        var_99 = np.percentile(terminal_pnl, 1)
        var_999 = np.percentile(terminal_pnl, 0.1)
        
        # Conditional Value at Risk (expected shortfall)
        cvar_95 = terminal_pnl[terminal_pnl <= var_95].mean()
        cvar_99 = terminal_pnl[terminal_pnl <= var_99].mean()
        
        # Maximum drawdown across all paths
        max_drawdown = self._compute_max_drawdown(simulation.pnl_paths)
        
        # Probability of ruin (losing more than threshold)
        prob_ruin = (terminal_pnl < ruin_threshold).mean()
        
        # Expected return and volatility
        expected_return = terminal_pnl.mean()
        volatility = terminal_pnl.std()
        
        return RiskMetrics(
            var_95=var_95,
            var_99=var_99,
            var_999=var_999,
            cvar_95=cvar_95,
            cvar_99=cvar_99,
            max_drawdown=max_drawdown,
            prob_ruin=prob_ruin,
            expected_return=expected_return,
            volatility=volatility
        )
    
    def _compute_max_drawdown(self, pnl_paths: np.ndarray) -> float:
        """
        Compute maximum drawdown across all paths.
        
        Args:
            pnl_paths: P&L paths array of shape (num_paths, horizon_days)
        
        Returns:
            Maximum drawdown as a fraction
        """
        max_dd = 0.0
        
        for path in pnl_paths:
            # Compute running maximum
            running_max = np.maximum.accumulate(path)
            
            # Compute drawdown at each point
            drawdown = (path - running_max) / (running_max + 1e-10)
            
            # Track maximum drawdown
            max_dd = min(max_dd, drawdown.min())
        
        return max_dd
    def identify_worst_scenarios(
        self,
        simulation: SimulationResult,
        num_scenarios: int = 10
    ) -> List[WorstScenario]:
        """
        Identify worst-case scenarios from simulation paths.

        Finds paths with maximum losses and analyzes what market conditions
        led to those outcomes.

        Args:
            simulation: Simulation results
            num_scenarios: Number of worst scenarios to identify

        Returns:
            List of WorstScenario objects with details
        """
        terminal_pnl = simulation.pnl_paths[:, -1]

        # Find indices of worst paths
        worst_indices = np.argsort(terminal_pnl)[:num_scenarios]

        worst_scenarios = []

        for idx in worst_indices:
            path_idx = int(idx)

            # Get price moves for this path
            price_moves = {}
            for underlying_idx, underlying in enumerate(self.underlyings):
                initial_price = simulation.price_paths[path_idx, 0, underlying_idx]
                final_price = simulation.price_paths[path_idx, -1, underlying_idx]
                price_move = (final_price - initial_price) / initial_price
                price_moves[underlying] = price_move

            # Get volatility change
            initial_vol = simulation.vol_paths[path_idx, 0]
            final_vol = simulation.vol_paths[path_idx, -1]
            vol_change = final_vol - initial_vol

            # Compute max drawdown for this path
            path_pnl = simulation.pnl_paths[path_idx, :]
            running_max = np.maximum.accumulate(path_pnl)
            drawdown = (path_pnl - running_max) / (running_max + 1e-10)
            max_dd = drawdown.min()

            # Generate scenario description
            avg_price_move = np.mean(list(price_moves.values()))
            description = self._generate_scenario_description(
                avg_price_move, vol_change, max_dd
            )

            worst_scenarios.append(WorstScenario(
                path_index=path_idx,
                terminal_pnl=terminal_pnl[path_idx],
                max_drawdown=max_dd,
                price_moves=price_moves,
                vol_change=vol_change,
                scenario_description=description
            ))

        return worst_scenarios

    def decompose_scenario(
        self,
        simulation: SimulationResult,
        scenario: WorstScenario
    ) -> ScenarioDecomposition:
        """
        Decompose a scenario to understand what market conditions caused the loss.

        Analyzes price shocks, volatility changes, correlation effects, and
        time decay to identify the primary driver of losses.

        Args:
            simulation: Simulation results
            scenario: Worst scenario to decompose

        Returns:
            ScenarioDecomposition with detailed analysis
        """
        path_idx = scenario.path_index

        # Extract price shocks
        price_shocks = scenario.price_moves

        # Extract volatility shock
        vol_shock = scenario.vol_change

        # Estimate correlation impact (simplified)
        # In a full implementation, this would analyze correlation breakdown
        avg_price_move = np.mean(list(price_shocks.values()))
        price_dispersion = np.std(list(price_shocks.values()))
        correlation_impact = price_dispersion  # Higher dispersion = correlation breakdown

        # Estimate time decay impact
        # Negative theta means time decay hurts the portfolio
        time_decay_impact = -simulation.horizon_days * 0.01  # Simplified

        # Identify primary driver
        primary_driver = self._identify_primary_driver(
            price_shocks, vol_shock, correlation_impact
        )

        # Identify contributing factors
        contributing_factors = []
        if abs(avg_price_move) > 0.10:
            contributing_factors.append(f"Large price move: {avg_price_move:.1%}")
        if abs(vol_shock) > 0.10:
            contributing_factors.append(f"Volatility spike: {vol_shock:+.1%}")
        if correlation_impact > 0.15:
            contributing_factors.append(f"Correlation breakdown: {correlation_impact:.1%}")
        if scenario.max_drawdown < -0.15:
            contributing_factors.append(f"Severe drawdown: {scenario.max_drawdown:.1%}")

        return ScenarioDecomposition(
            scenario_id=path_idx,
            price_shocks=price_shocks,
            volatility_shock=vol_shock,
            correlation_impact=correlation_impact,
            time_decay_impact=time_decay_impact,
            primary_driver=primary_driver,
            contributing_factors=contributing_factors
        )

    def compute_probability_of_ruin(
        self,
        simulation: SimulationResult,
        ruin_threshold: float = -0.20
    ) -> float:
        """
        Compute probability of ruin (losing more than threshold).

        Args:
            simulation: Simulation results
            ruin_threshold: Loss threshold (default -20%)

        Returns:
            Probability of ruin as a fraction [0, 1]
        """
        terminal_pnl = simulation.pnl_paths[:, -1]

        # Count paths that exceed ruin threshold
        ruined_paths = terminal_pnl < ruin_threshold
        prob_ruin = ruined_paths.mean()

        return prob_ruin

    def _generate_scenario_description(
        self,
        avg_price_move: float,
        vol_change: float,
        max_drawdown: float
    ) -> str:
        """Generate human-readable scenario description"""
        description_parts = []

        if avg_price_move < -0.20:
            description_parts.append("severe market crash")
        elif avg_price_move < -0.10:
            description_parts.append("significant market decline")
        elif avg_price_move > 0.20:
            description_parts.append("strong market rally")

        if vol_change > 0.20:
            description_parts.append("volatility explosion")
        elif vol_change > 0.10:
            description_parts.append("elevated volatility")

        if max_drawdown < -0.25:
            description_parts.append("catastrophic drawdown")
        elif max_drawdown < -0.15:
            description_parts.append("severe drawdown")

        if not description_parts:
            description_parts.append("moderate adverse conditions")

        return ", ".join(description_parts)

    def _identify_primary_driver(
        self,
        price_shocks: Dict[str, float],
        vol_shock: float,
        correlation_impact: float
    ) -> str:
        """Identify the primary driver of losses"""
        avg_price_shock = abs(np.mean(list(price_shocks.values())))

        # Compare magnitudes to determine primary driver
        if avg_price_shock > 0.15 and avg_price_shock > abs(vol_shock):
            return "price_shock"
        elif abs(vol_shock) > 0.15:
            return "volatility_shock"
        elif correlation_impact > 0.15:
            return "correlation_breakdown"
        else:
            return "combined_factors"
    def monitor_risk_thresholds(
        self,
        risk_metrics: RiskMetrics,
        thresholds: Dict[str, float]
    ) -> List[RiskAlert]:
        """
        Monitor risk metrics against thresholds and generate alerts.

        Args:
            risk_metrics: Computed risk metrics
            thresholds: Dictionary of metric thresholds
                Example: {
                    'var_99': -100000,  # Max acceptable VaR
                    'cvar_99': -150000,  # Max acceptable CVaR
                    'max_drawdown': -0.25,  # Max acceptable drawdown
                    'prob_ruin': 0.05  # Max acceptable probability of ruin
                }

        Returns:
            List of RiskAlert objects for breached thresholds
        """
        alerts = []

        # Check VaR thresholds
        if 'var_95' in thresholds and risk_metrics.var_95 < thresholds['var_95']:
            alerts.append(RiskAlert(
                metric_name='var_95',
                threshold=thresholds['var_95'],
                actual_value=risk_metrics.var_95,
                severity='MEDIUM',
                timestamp=datetime.now(),
                recommended_action='Review position sizing and reduce exposure'
            ))

        if 'var_99' in thresholds and risk_metrics.var_99 < thresholds['var_99']:
            alerts.append(RiskAlert(
                metric_name='var_99',
                threshold=thresholds['var_99'],
                actual_value=risk_metrics.var_99,
                severity='HIGH',
                timestamp=datetime.now(),
                recommended_action='Reduce high-risk positions immediately'
            ))

        if 'var_999' in thresholds and risk_metrics.var_999 < thresholds['var_999']:
            alerts.append(RiskAlert(
                metric_name='var_999',
                threshold=thresholds['var_999'],
                actual_value=risk_metrics.var_999,
                severity='CRITICAL',
                timestamp=datetime.now(),
                recommended_action='Emergency de-risking required - consider liquidation'
            ))

        # Check CVaR thresholds
        if 'cvar_95' in thresholds and risk_metrics.cvar_95 < thresholds['cvar_95']:
            alerts.append(RiskAlert(
                metric_name='cvar_95',
                threshold=thresholds['cvar_95'],
                actual_value=risk_metrics.cvar_95,
                severity='MEDIUM',
                timestamp=datetime.now(),
                recommended_action='Expected tail losses exceed acceptable levels'
            ))

        if 'cvar_99' in thresholds and risk_metrics.cvar_99 < thresholds['cvar_99']:
            alerts.append(RiskAlert(
                metric_name='cvar_99',
                threshold=thresholds['cvar_99'],
                actual_value=risk_metrics.cvar_99,
                severity='HIGH',
                timestamp=datetime.now(),
                recommended_action='Severe tail risk detected - hedge or reduce exposure'
            ))

        # Check max drawdown threshold
        if 'max_drawdown' in thresholds and risk_metrics.max_drawdown < thresholds['max_drawdown']:
            alerts.append(RiskAlert(
                metric_name='max_drawdown',
                threshold=thresholds['max_drawdown'],
                actual_value=risk_metrics.max_drawdown,
                severity='CRITICAL',
                timestamp=datetime.now(),
                recommended_action='Maximum drawdown exceeded - implement stop-loss'
            ))

        # Check probability of ruin threshold
        if 'prob_ruin' in thresholds and risk_metrics.prob_ruin > thresholds['prob_ruin']:
            alerts.append(RiskAlert(
                metric_name='prob_ruin',
                threshold=thresholds['prob_ruin'],
                actual_value=risk_metrics.prob_ruin,
                severity='CRITICAL',
                timestamp=datetime.now(),
                recommended_action='Unacceptable ruin probability - reduce leverage and exposure'
            ))

        return alerts

    def generate_risk_alert(
        self,
        alert: RiskAlert,
        simulation: SimulationResult,
        worst_scenario: Optional[WorstScenario] = None
    ) -> Dict[str, Any]:
        """
        Generate detailed risk alert for Risk Authority.

        Creates a comprehensive alert with scenario breakdowns and
        recommended actions for risk management.

        Args:
            alert: RiskAlert object
            simulation: Simulation results for context
            worst_scenario: Optional worst scenario for detailed breakdown

        Returns:
            Dictionary with complete alert information
        """
        alert_dict = {
            'alert_id': f"RISK-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
            'timestamp': alert.timestamp.isoformat(),
            'metric_name': alert.metric_name,
            'severity': alert.severity,
            'threshold': alert.threshold,
            'actual_value': alert.actual_value,
            'breach_magnitude': abs(alert.actual_value - alert.threshold),
            'breach_percentage': abs((alert.actual_value - alert.threshold) / alert.threshold) if alert.threshold != 0 else 0,
            'recommended_action': alert.recommended_action,
            'simulation_context': {
                'num_paths': simulation.num_paths,
                'horizon_days': simulation.horizon_days,
                'timestamp': simulation.timestamp.isoformat()
            }
        }

        # Add scenario breakdown if provided
        if worst_scenario:
            alert_dict['worst_scenario'] = {
                'path_index': worst_scenario.path_index,
                'terminal_pnl': worst_scenario.terminal_pnl,
                'max_drawdown': worst_scenario.max_drawdown,
                'price_moves': worst_scenario.price_moves,
                'vol_change': worst_scenario.vol_change,
                'description': worst_scenario.scenario_description
            }

            # Add decomposition if available
            if alert.scenario_details:
                alert_dict['scenario_decomposition'] = {
                    'primary_driver': alert.scenario_details.primary_driver,
                    'price_shocks': alert.scenario_details.price_shocks,
                    'volatility_shock': alert.scenario_details.volatility_shock,
                    'correlation_impact': alert.scenario_details.correlation_impact,
                    'contributing_factors': alert.scenario_details.contributing_factors
                }

        return alert_dict
    def create_crisis_2008_scenario(self) -> StressScenario:
        """
        Model 2008 financial crisis scenario.

        Characteristics:
        - Severe market crash (35% decline)
        - Correlation breakdown (all assets move together)
        - Liquidity crisis (wide spreads)
        - Extreme volatility spike
        """
        return StressScenario(
            name="2008_financial_crisis",
            spot_shock=-0.35,  # 35% market crash
            vol_shock=0.50,  # Volatility spikes to extreme levels
            correlation_shock=0.95,  # Correlation breakdown - everything correlates
            liquidity_multiplier=5.0,  # Liquidity evaporates
            description="2008 financial crisis: severe crash, correlation breakdown, liquidity crisis"
        )

    def create_crisis_2020_scenario(self) -> StressScenario:
        """
        Model 2020 COVID crash scenario.

        Characteristics:
        - Rapid sharp drawdown (30% decline)
        - Volatility explosion (VIX to 80+)
        - Correlation surge
        - Quick recovery potential
        """
        return StressScenario(
            name="2020_covid_crash",
            spot_shock=-0.30,  # 30% rapid crash
            vol_shock=0.60,  # Extreme volatility spike
            correlation_shock=0.90,  # High correlation
            liquidity_multiplier=3.0,  # Moderate liquidity stress
            description="2020 COVID crash: rapid volatility spike, sharp drawdown"
        )

    def create_combined_crisis_scenario(self) -> StressScenario:
        """
        Model combined 2008 + 2020 crisis scenario.

        Takes worst aspects of both crises:
        - Maximum price decline
        - Extreme volatility
        - Complete correlation breakdown
        - Severe liquidity crisis
        """
        return StressScenario(
            name="combined_crisis",
            spot_shock=-0.40,  # 40% crash (worse than either crisis)
            vol_shock=0.70,  # Extreme volatility
            correlation_shock=0.98,  # Near-perfect correlation
            liquidity_multiplier=6.0,  # Severe liquidity crisis
            description="Combined 2008+2020 crisis: worst aspects of both crises"
        )

    def create_volatility_spike_scenario(self) -> StressScenario:
        """
        Model pure volatility spike without major price move.

        Characteristics:
        - Moderate price decline
        - Extreme volatility increase
        - Normal correlation
        """
        return StressScenario(
            name="volatility_spike",
            spot_shock=-0.10,  # Moderate 10% decline
            vol_shock=0.40,  # Large volatility spike
            correlation_shock=0.60,  # Normal correlation
            liquidity_multiplier=2.0,  # Moderate liquidity stress
            description="Volatility spike: extreme vol increase with moderate price move"
        )

    def create_liquidity_crisis_scenario(self) -> StressScenario:
        """
        Model liquidity crisis scenario.

        Characteristics:
        - Moderate price decline
        - Correlation breakdown
        - Severe liquidity evaporation
        """
        return StressScenario(
            name="liquidity_crisis",
            spot_shock=-0.15,  # 15% decline
            vol_shock=0.30,  # Elevated volatility
            correlation_shock=0.85,  # High correlation
            liquidity_multiplier=8.0,  # Extreme liquidity crisis
            description="Liquidity crisis: severe spread widening and correlation breakdown"
        )
    def execute_stress_test(
        self,
        scenario: StressScenario,
        spot_prices: Dict[str, float],
        volatilities: Dict[str, float],
        initial_portfolio_value: float,
        max_loss_threshold: float = -0.25
    ) -> StressTestResult:
        """
        Execute stress test under specified scenario.

        Applies scenario shocks to market conditions and revalues portfolio
        to compute stress P&L and survival check.

        Args:
            scenario: Stress scenario definition
            spot_prices: Current spot prices
            volatilities: Current volatilities
            initial_portfolio_value: Starting portfolio value
            max_loss_threshold: Maximum acceptable loss (default -25%)

        Returns:
            StressTestResult with P&L and survival status
        """
        # Apply scenario shocks
        stressed_spots = {
            u: price * (1 + scenario.spot_shock)
            for u, price in spot_prices.items()
        }

        stressed_vols = {
            u: vol + scenario.vol_shock
            for u, vol in volatilities.items()
        }

        # Apply correlation shock to correlation matrix
        stressed_corr = self._apply_correlation_shock(
            self.correlation_matrix,
            scenario.correlation_shock
        )

        # Store original correlation matrix
        original_corr = self.correlation_matrix.copy()

        try:
            # Temporarily update correlation matrix
            self.correlation_matrix = stressed_corr

            # Simulate portfolio under stressed conditions
            # Use short horizon (1 day) for stress test
            stressed_simulation = self.simulate_portfolio(
                spot_prices=stressed_spots,
                volatilities=stressed_vols,
                initial_portfolio_value=initial_portfolio_value,
                horizon_days=1,
                num_paths=1000,  # Fewer paths for stress test
                seed=42
            )

            # Compute stressed P&L
            stressed_pnl = stressed_simulation.pnl_paths[:, -1].mean()
            pnl_change = stressed_pnl
            pnl_change_pct = pnl_change / initial_portfolio_value

            # Compute max drawdown under stress
            max_drawdown = self._compute_max_drawdown(stressed_simulation.pnl_paths)

            # Check survival
            survives = pnl_change_pct > max_loss_threshold

            return StressTestResult(
                scenario=scenario,
                base_pnl=0.0,  # Starting from zero
                stressed_pnl=stressed_pnl,
                pnl_change=pnl_change,
                pnl_change_pct=pnl_change_pct,
                survives=survives,
                max_drawdown=max_drawdown,
                timestamp=datetime.now()
            )

        finally:
            # Restore original correlation matrix
            self.correlation_matrix = original_corr

    def _apply_correlation_shock(
        self,
        correlation_matrix: np.ndarray,
        target_correlation: float
    ) -> np.ndarray:
        """
        Apply correlation shock to correlation matrix.

        Moves all off-diagonal correlations toward target level
        while maintaining positive definiteness.

        Args:
            correlation_matrix: Original correlation matrix
            target_correlation: Target correlation level

        Returns:
            Shocked correlation matrix
        """
        n = correlation_matrix.shape[0]
        shocked = np.eye(n)

        # Set all off-diagonal elements to target correlation
        for i in range(n):
            for j in range(n):
                if i != j:
                    shocked[i, j] = target_correlation

        # Ensure positive definiteness by adjusting eigenvalues if needed
        eigenvalues, eigenvectors = np.linalg.eigh(shocked)

        # If any eigenvalue is negative or too small, adjust
        min_eigenvalue = 0.01
        eigenvalues = np.maximum(eigenvalues, min_eigenvalue)

        # Reconstruct matrix
        shocked = eigenvectors @ np.diag(eigenvalues) @ eigenvectors.T

        # Normalize to ensure diagonal is 1
        d = np.sqrt(np.diag(shocked))
        shocked = shocked / np.outer(d, d)

        return shocked

    def run_all_stress_tests(
        self,
        spot_prices: Dict[str, float],
        volatilities: Dict[str, float],
        initial_portfolio_value: float,
        max_loss_threshold: float = -0.25
    ) -> Dict[str, StressTestResult]:
        """
        Run all predefined stress scenarios.

        Args:
            spot_prices: Current spot prices
            volatilities: Current volatilities
            initial_portfolio_value: Starting portfolio value
            max_loss_threshold: Maximum acceptable loss

        Returns:
            Dictionary mapping scenario name to stress test result
        """
        scenarios = [
            self.create_crisis_2008_scenario(),
            self.create_crisis_2020_scenario(),
            self.create_combined_crisis_scenario(),
            self.create_volatility_spike_scenario(),
            self.create_liquidity_crisis_scenario()
        ]

        results = {}
        for scenario in scenarios:
            result = self.execute_stress_test(
                scenario=scenario,
                spot_prices=spot_prices,
                volatilities=volatilities,
                initial_portfolio_value=initial_portfolio_value,
                max_loss_threshold=max_loss_threshold
            )
            results[scenario.name] = result

        return results

    def validate_portfolio_survival(
        self,
        stress_results: Dict[str, StressTestResult]
    ) -> Tuple[bool, List[str]]:
        """
        Validate that portfolio survives all stress scenarios.

        Args:
            stress_results: Dictionary of stress test results

        Returns:
            Tuple of (all_survived, failed_scenarios)
        """
        failed_scenarios = []

        for scenario_name, result in stress_results.items():
            if not result.survives:
                failed_scenarios.append(scenario_name)

        all_survived = len(failed_scenarios) == 0

        return all_survived, failed_scenarios
