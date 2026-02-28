# Unified Volatility Engine - API Reference

## Core Interfaces

### VolatilityStateEngine

```python
from volatility.state_engine import VolatilityStateEngine, VolatilityState

# Initialize
state_engine = VolatilityStateEngine()

# Update IV surface
state_engine.update_iv_surface(
    underlying="SPY",
    surface=iv_surface_object
)

# Update regime
state_engine.update_regime(
    regime="high_vol",
    probabilities={"low_vol": 0.1, "high_vol": 0.7, "crisis": 0.2}
)

# Update correlations
state_engine.update_correlations(
    correlation_matrix=corr_matrix,  # NxN numpy array
    implied_corr=0.65,
    realized_corr=0.45
)

# Get current state
state: VolatilityState = state_engine.get_state()

# Save/restore state
state_engine.save_state("snapshots/state_20260211.json")
state_engine.load_state("snapshots/state_20260211.json")
```

---

### IVSurface

```python
from volatility.iv_surface import IVSurface
import numpy as np

# Create and fit surface
surface = IVSurface(underlying="SPY")
surface.fit(
    strikes=np.array([400, 420, 440, 460, 480]),
    expiries=np.array([30, 30, 30, 30, 30]),  # days to expiry
    ivs=np.array([0.18, 0.16, 0.15, 0.16, 0.18]),
    spot=440.0
)

# Query IV at any point
iv = surface.get_iv(strike=450, expiry=30)

# Validate no-arbitrage
is_valid, violations = surface.validate_no_arbitrage()

# Get surface quality metrics
metrics = surface.get_quality_metrics()
# Returns: {'rmse': 0.002, 'max_error': 0.005, 'arbitrage_violations': 0}
```

---

### GreeksAggregator

```python
from volatility.greeks_aggregator import GreeksAggregator, Position

# Initialize
greeks_agg = GreeksAggregator()

# Define positions
positions = [
    Position(
        underlying="SPY",
        option_type="call",
        strike=450,
        expiry=30,
        quantity=10,
        spot=440,
        iv=0.16,
        rate=0.05
    ),
    # ... more positions
]

# Compute portfolio Greeks
portfolio_greeks = greeks_agg.compute_portfolio_greeks(
    positions=positions,
    state=volatility_state
)

# Access Greeks
print(f"Delta: {portfolio_greeks.delta}")
print(f"Gamma: {portfolio_greeks.gamma}")
print(f"Vega: {portfolio_greeks.vega}")
print(f"Theta: {portfolio_greeks.theta}")

# Per-underlying breakdown
for underlying, greeks in portfolio_greeks.by_underlying.items():
    print(f"{underlying}: Delta={greeks.delta}, Gamma={greeks.gamma}")

# Validate constraints
violations = greeks_agg.validate_constraints(
    greeks=portfolio_greeks,
    limits={"delta": 1000, "gamma": 500, "vega": 10000}
)

# Scenario analysis
scenarios = [
    {"spot_shift": 0.01, "iv_shift": 0.0, "time_shift": 0},
    {"spot_shift": -0.01, "iv_shift": 0.0, "time_shift": 0},
    {"spot_shift": 0.0, "iv_shift": 0.01, "time_shift": 0},
]
scenario_results = greeks_agg.scenario_analysis(positions, scenarios)
```

---

### StrategyGenerator

```python
from volatility.strategy_generator import StrategyGenerator, TargetGreeks

# Initialize
strategy_gen = StrategyGenerator(state_engine=state_engine)

# Define target Greeks
target = TargetGreeks(
    delta=0,  # Delta-neutral
    gamma=100,  # Long gamma
    vega=500,  # Long vega
    theta=-50,  # Negative theta acceptable
    max_cost=10000  # Maximum premium to pay
)

# Generate strategies
strategies = strategy_gen.generate_strategies(
    target_greeks=target,
    underlying="SPY",
    constraints={
        "max_legs": 4,
        "min_liquidity": 1000,
        "allowed_types": ["straddle", "strangle", "butterfly"]
    }
)

# Rank by cost-efficiency
ranked = strategy_gen.rank_by_efficiency(strategies)

# Get best strategy
best_strategy = ranked[0]
print(f"Type: {best_strategy.structure_type}")
print(f"Legs: {best_strategy.legs}")
print(f"Cost: {best_strategy.cost}")
print(f"Greeks: {best_strategy.greeks}")
```

---

### RiskAuthority

```python
from volatility.risk_authority import UnifiedRiskAuthority

# Initialize with limits
risk_authority = UnifiedRiskAuthority(
    position_limits={"per_underlying": 100, "total": 500},
    greeks_limits={"delta": 1000, "gamma": 500, "vega": 10000, "theta": -500},
    concentration_limits={"max_pct_per_underlying": 0.2},
    margin_buffer=1.5
)

# Validate trade
result = risk_authority.validate_trade(
    strategy=proposed_strategy,
    current_state=volatility_state
)

if result.approved:
    print("Trade approved")
else:
    print(f"Trade rejected: {result.rejection_reason}")
    print(f"Violations: {result.violations}")

# Check emergency triggers
emergency = risk_authority.check_emergency_triggers(volatility_state)
if emergency:
    print(f"Emergency detected: {emergency.trigger_type}")
    print(f"Recommended action: {emergency.action}")

# Execute emergency action
risk_authority.execute_emergency_action(
    action="reduce_positions",
    state=volatility_state,
    params={"reduction_pct": 0.5}
)

# Get audit trail
audit_entries = risk_authority.get_audit_trail(
    start_date="2026-02-01",
    end_date="2026-02-11"
)
```

---

### RegimeDetector

```python
from volatility.regime_detector import RegimeDetector

# Initialize
regime_detector = RegimeDetector()

# Detect regime
regime = regime_detector.detect_regime(
    vix=18.5,
    realized_vol=0.16,
    correlation=0.65
)

print(f"Current regime: {regime.current}")
print(f"Probabilities: {regime.probabilities}")
# {'low_vol': 0.2, 'high_vol': 0.7, 'crisis': 0.1, 'transition': 0.0}

# Check for transition
is_transition = regime_detector.detect_transition()
if is_transition:
    print(f"Transition from {regime.previous} to {regime.current}")

# Get regime history
history = regime_detector.get_regime_history(lookback_days=30)
```

---

### DispersionModule

```python
from volatility.dispersion_module import DispersionModule

# Initialize
dispersion = DispersionModule(state_engine=state_engine)

# Identify opportunities
opportunities = dispersion.identify_opportunities(
    index="SPY",
    constituents=["AAPL", "MSFT", "GOOGL", "AMZN"],
    index_weights={"AAPL": 0.3, "MSFT": 0.3, "GOOGL": 0.2, "AMZN": 0.2}
)

for opp in opportunities:
    print(f"Implied corr: {opp.implied_corr}")
    print(f"Realized corr: {opp.realized_corr}")
    print(f"Spread: {opp.spread}")
    print(f"Expected P&L: {opp.expected_pnl}")

# Compute position sizes
positions = dispersion.compute_position_sizes(
    opportunity=opportunities[0],
    capital=100000
)

# Rebalance to maintain delta neutrality
rebalance_orders = dispersion.rebalance_positions(
    positions=current_positions,
    current_deltas=current_deltas,
    threshold=50  # Rebalance if delta > 50
)
```

---

### GammaScalper

```python
from volatility.gamma_scalper import GammaScalper

# Initialize
gamma_scalper = GammaScalper(state_engine=state_engine)

# Identify opportunities
opportunities = gamma_scalper.identify_opportunities(
    positions=current_positions,
    state=volatility_state
)

for opp in opportunities:
    print(f"Position: {opp.position}")
    print(f"Current gamma: {opp.gamma}")
    print(f"Implied vol: {opp.implied_vol}")
    print(f"Realized vol: {opp.realized_vol}")
    print(f"Expected profit: {opp.expected_profit}")

# Compute hedge threshold
threshold = gamma_scalper.compute_hedge_threshold(
    position=long_straddle,
    params={"transaction_cost": 0.01, "risk_aversion": 0.5}
)

# Generate hedge orders
hedge_orders = gamma_scalper.generate_hedge_orders(
    position=long_straddle,
    current_delta=75,
    threshold=50
)

# Track realized variance
realized_var = gamma_scalper.compute_realized_variance(
    hedge_history=hedge_history
)
```

---

### CapitalAllocator

```python
from volatility.capital_allocator import CapitalAllocator

# Initialize
allocator = CapitalAllocator()

# Allocate capital
allocations = allocator.allocate_capital(
    total_capital=1000000,
    regime="high_vol",
    performance_history={
        "dispersion": {"sharpe": 1.5, "returns": [0.02, 0.03, -0.01]},
        "gamma_scalping": {"sharpe": 1.2, "returns": [0.01, 0.02, 0.01]},
        "short_vol": {"sharpe": 0.8, "returns": [-0.02, 0.01, -0.03]}
    }
)

print(f"Dispersion: ${allocations['dispersion']}")
print(f"Gamma scalping: ${allocations['gamma_scalping']}")
print(f"Short vol: ${allocations['short_vol']}")

# Apply regime-conditional constraints
constrained = allocator.apply_constraints(
    allocations=allocations,
    regime="crisis",
    constraints={"short_vol": 0}  # Zero short vol in crisis
)

# Adjust for drawdown
adjusted = allocator.adjust_for_drawdown(
    allocations=allocations,
    drawdowns={"dispersion": 0.05, "gamma_scalping": 0.15, "short_vol": 0.25}
)
```

---

### MonteCarloEngine

```python
from volatility.monte_carlo_engine import MonteCarloEngine

# Initialize
mc_engine = MonteCarloEngine(n_workers=4)  # Parallel execution

# Simulate price paths
paths = mc_engine.simulate_paths(
    n_paths=10000,
    n_steps=252,  # Daily steps for 1 year
    initial_prices={"SPY": 440, "QQQ": 360},
    correlations=correlation_matrix,
    volatilities={"SPY": 0.16, "QQQ": 0.20},
    drift=0.05,  # Risk-free rate
    distribution="student_t",  # Fat tails
    df=5  # Degrees of freedom
)

# Compute portfolio P&L
pnl_distribution = mc_engine.compute_portfolio_pnl(
    positions=current_positions,
    paths=paths,
    state=volatility_state
)

# Compute risk metrics
risk_metrics = mc_engine.compute_risk_metrics(pnl_distribution)
print(f"VaR 95%: ${risk_metrics['var_95']}")
print(f"VaR 99%: ${risk_metrics['var_99']}")
print(f"CVaR 95%: ${risk_metrics['cvar_95']}")
print(f"Max drawdown: ${risk_metrics['max_drawdown']}")
print(f"Probability of ruin: {risk_metrics['prob_ruin']}")

# Run stress test
stress_result = mc_engine.run_stress_test(
    scenario="crisis_2008",
    positions=current_positions,
    state=volatility_state
)
print(f"Stress P&L: ${stress_result.pnl}")
print(f"Survives: {stress_result.survives}")
```

---

### ExecutionInterface

```python
from volatility.execution_interface import ExecutionInterface, Order, OrderType

# Initialize
execution = ExecutionInterface(venues=["CBOE", "ISE", "PHLX"])

# Generate orders from strategy
orders = execution.generate_orders(
    strategy=approved_strategy,
    execution_params={
        "order_type": OrderType.LIMIT,
        "time_in_force": "DAY",
        "limit_price_offset": 0.05  # 5 cents better than mid
    }
)

# Submit order
order_id = execution.submit_order(orders[0])

# Check order status
status = execution.get_order_status(order_id)
print(f"Status: {status.state}")  # PENDING, FILLED, REJECTED, CANCELLED
print(f"Filled quantity: {status.filled_quantity}")
print(f"Average price: {status.avg_fill_price}")

# Modify order
execution.modify_order(
    order_id=order_id,
    new_params={"limit_price": 2.55}
)

# Cancel order
execution.cancel_order(order_id)

# Get execution history
history = execution.get_execution_history(
    start_date="2026-02-01",
    end_date="2026-02-11"
)
```

---

### PerformanceMonitor

```python
from volatility.performance_monitor import PerformanceMonitor

# Initialize
perf_monitor = PerformanceMonitor()

# Update P&L
perf_monitor.update_pnl(
    positions=current_positions,
    state=volatility_state
)

# Get current P&L
current_pnl = perf_monitor.get_current_pnl()
print(f"Total P&L: ${current_pnl.total}")
print(f"Realized P&L: ${current_pnl.realized}")
print(f"Unrealized P&L: ${current_pnl.unrealized}")

# Decompose P&L into Greeks
decomposition = perf_monitor.decompose_pnl(pnl_history)
print(f"Delta P&L: ${decomposition['delta']}")
print(f"Gamma P&L: ${decomposition['gamma']}")
print(f"Vega P&L: ${decomposition['vega']}")
print(f"Theta P&L: ${decomposition['theta']}")

# Compute performance statistics
stats = perf_monitor.compute_performance_stats(
    returns=daily_returns,
    regime="high_vol"
)
print(f"Sharpe ratio: {stats['sharpe']}")
print(f"Sortino ratio: {stats['sortino']}")
print(f"Max drawdown: {stats['max_drawdown']}")
print(f"Win rate: {stats['win_rate']}")

# Detect performance degradation
degradation = perf_monitor.detect_degradation(
    recent_perf=recent_returns,
    historical_perf=historical_returns
)
if degradation.detected:
    print(f"Performance degradation detected!")
    print(f"Recent Sharpe: {degradation.recent_sharpe}")
    print(f"Historical Sharpe: {degradation.historical_sharpe}")
    print(f"Recommendations: {degradation.recommendations}")
```

---

### UnifiedVolatilityEngine

```python
from volatility.unified_engine import UnifiedVolatilityEngine, EventType

# Initialize all components
state_engine = VolatilityStateEngine()
strategy_gen = StrategyGenerator(state_engine)
greeks_agg = GreeksAggregator()
risk_authority = UnifiedRiskAuthority(...)
# ... initialize other components

# Create unified engine
engine = UnifiedVolatilityEngine(
    state_engine=state_engine,
    strategy_generator=strategy_gen,
    greeks_aggregator=greeks_agg,
    risk_authority=risk_authority,
    dispersion_module=dispersion,
    gamma_scalper=gamma_scalper,
    capital_allocator=allocator,
    monte_carlo_engine=mc_engine,
    regime_detector=regime_detector,
    execution_interface=execution,
    performance_monitor=perf_monitor
)

# Subscribe to events
def on_regime_change(event):
    print(f"Regime changed to {event.data['new_regime']}")

engine.subscribe_to_events(EventType.REGIME_CHANGE, on_regime_change)

# Run trading cycle
result = engine.run_trading_cycle()
print(f"Strategies generated: {len(result.strategies_generated)}")
print(f"Strategies approved: {len(result.strategies_approved)}")
print(f"Orders submitted: {len(result.orders_submitted)}")
print(f"Portfolio Greeks: {result.portfolio_greeks}")
print(f"Errors: {result.errors}")

# Graceful shutdown
engine.shutdown()
```

---

## Configuration API

```python
from volatility.config import VolatilityConfig

# Load configuration
config = VolatilityConfig.load("config/moderate.yaml")

# Access parameters
print(f"Position limits: {config.position_limits}")
print(f"Greeks limits: {config.greeks_limits}")
print(f"Risk thresholds: {config.risk_thresholds}")

# Modify configuration
config.greeks_limits["delta"] = 1500
config.save("config/moderate_updated.yaml")

# Hot-reload (non-critical parameters only)
config.hot_reload("config/moderate_updated.yaml")

# Get configuration version
print(f"Config version: {config.version}")
print(f"Last modified: {config.last_modified}")
```

---

## Data Models

### VolatilityState

```python
@dataclass
class VolatilityState:
    timestamp: datetime
    iv_surfaces: Dict[str, IVSurface]  # underlying -> surface
    positions: List[Position]
    portfolio_greeks: PortfolioGreeks
    regime: str
    regime_probabilities: Dict[str, float]
    correlation_matrix: np.ndarray
    implied_correlation: float
    realized_correlation: float
    risk_metrics: Dict[str, float]
```

### Position

```python
@dataclass
class Position:
    underlying: str
    option_type: str  # "call" or "put"
    strike: float
    expiry: int  # days to expiry
    quantity: int
    spot: float
    iv: float
    rate: float
```

### PortfolioGreeks

```python
@dataclass
class PortfolioGreeks:
    delta: float
    gamma: float
    vega: float
    theta: float
    rho: float
    vanna: float
    volga: float
    charm: float
    vomma: float
    by_underlying: Dict[str, Greeks]  # per-underlying breakdown
```

### TradeValidationResult

```python
@dataclass
class TradeValidationResult:
    approved: bool
    rejection_reason: Optional[str]
    violations: List[str]
    risk_score: float
    audit_entry: AuditEntry
```

---

## Error Handling

All components raise specific exceptions:

```python
from volatility.exceptions import (
    StateValidationError,
    ArbitrageViolationError,
    RiskLimitViolationError,
    ComponentError,
    ExecutionError
)

try:
    state_engine.update_iv_surface(underlying, surface)
except StateValidationError as e:
    print(f"Invalid state: {e}")

try:
    surface.validate_no_arbitrage()
except ArbitrageViolationError as e:
    print(f"Arbitrage detected: {e.violations}")

try:
    risk_authority.validate_trade(strategy, state)
except RiskLimitViolationError as e:
    print(f"Risk limit violated: {e.limit_type}")
```

---

## Logging

All components use Python's logging module:

```python
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('volatility_engine.log'),
        logging.StreamHandler()
    ]
)

# Component loggers
logger = logging.getLogger('volatility.unified_engine')
logger.info("Trading cycle started")
logger.warning("Greeks approaching limit")
logger.error("Component error", exc_info=True)
```

---

## Testing Utilities

```python
from volatility.testing import (
    create_test_state,
    create_test_positions,
    create_test_surface,
    MockExecutionInterface
)

# Create test data
state = create_test_state(regime="high_vol")
positions = create_test_positions(n=10, underlying="SPY")
surface = create_test_surface(underlying="SPY", spot=440)

# Mock execution for testing
mock_execution = MockExecutionInterface()
mock_execution.set_fill_behavior("immediate")  # or "delayed", "partial", "reject"
```

---

## Examples

See `examples/` directory for complete examples:
- `unified_engine_demo.py` - Complete trading cycle
- `performance_monitoring_demo.py` - P&L tracking and attribution
- `risk_management_demo.py` - Risk validation and emergency actions
- `strategy_generation_demo.py` - Strategy generation workflow
