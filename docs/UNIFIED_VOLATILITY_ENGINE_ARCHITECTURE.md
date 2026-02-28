# Unified Volatility Engine - System Architecture

## Overview

The Unified Volatility Engine is an institutional-grade options trading system that consolidates all volatility trading strategies into a single, coherent framework. The system provides real-time Greeks tracking, regime-adaptive capital allocation, multi-strategy execution, and comprehensive risk management.

## System Architecture

### High-Level Data Flow

```
Market Data → State Engine → Regime Detection
                ↓
         Strategy Generation
                ↓
         Risk Validation
                ↓
         Capital Allocation
                ↓
         Execution Interface
                ↓
      Performance Monitoring
```

### Core Components

#### 1. VolatilityStateEngine (`src/volatility/state_engine.py`)

**Purpose**: Central state management for all volatility-related data

**Key Responsibilities**:
- Maintain current IV surface across all underlyings
- Track portfolio positions and Greeks
- Store correlation matrices (implied and realized)
- Manage regime state and history
- Provide state persistence (save/restore snapshots)

**Key Methods**:
- `update_iv_surface(underlying, surface)` - Update IV surface for an underlying
- `update_regime(regime, probabilities)` - Update current market regime
- `update_correlations(corr_matrix, implied_corr, realized_corr)` - Update correlation data
- `update_volatility_metrics(metrics)` - Update volatility metrics
- `save_state(path)` - Persist state to disk
- `load_state(path)` - Restore state from disk

**State Validation**: Automatic validation on all updates ensures consistency

---

#### 2. IVSurface (`src/volatility/iv_surface.py`)

**Purpose**: Model implied volatility surface with no-arbitrage constraints

**Key Features**:
- SVI parameterization for smooth surface fitting
- No-arbitrage constraint enforcement (calendar spreads, butterfly spreads)
- Surface quality metrics and validation
- Extrapolation handling for extreme strikes

**Key Methods**:
- `fit(strikes, expiries, ivs, spot)` - Fit surface to market data
- `get_iv(strike, expiry)` - Query IV at any strike/expiry
- `validate_no_arbitrage()` - Check arbitrage-free conditions

---

#### 3. GreeksAggregator (`src/volatility/greeks_aggregator.py`)

**Purpose**: Real-time portfolio Greeks computation and monitoring

**Greeks Computed**:
- First-order: Delta, Gamma, Vega, Theta, Rho
- Second-order: Vanna, Volga, Charm, Vomma

**Key Features**:
- Portfolio-level aggregation with per-underlying breakdown
- Constraint validation against limits
- Scenario analysis (shifted spot, IV, time)
- Anomaly detection for Greek evolution
- Optimized computation (P95 latency <20ms)

**Key Methods**:
- `compute_portfolio_greeks(positions, state)` - Aggregate all Greeks
- `validate_constraints(greeks, limits)` - Check against risk limits
- `scenario_analysis(positions, scenarios)` - Stress test Greeks

---

#### 4. StrategyGenerator (`src/volatility/strategy_generator.py`)

**Purpose**: AST-based generation of option structures to achieve target Greeks

**Strategy Types**:
- Primitives: Call, Put, Spread, Straddle, Strangle, Butterfly, Condor, Calendar
- Composites: Multi-leg structures built from primitives

**Key Features**:
- Target Greeks decomposition
- Cost-efficient structure ranking
- No-arbitrage validation
- Greeks additivity for composed structures

**Key Methods**:
- `generate_strategies(target_greeks, constraints)` - Generate candidate structures
- `rank_by_efficiency(strategies)` - Rank by cost per unit Greek
- `compose_structures(structures)` - Build complex multi-leg positions

---

#### 5. RiskAuthority (`src/volatility/risk_authority.py`)

**Purpose**: Absolute veto power over all trades with emergency action capability

**Risk Checks**:
- Position limits (per underlying, total)
- Greeks limits (delta, gamma, vega, theta)
- Concentration limits
- Margin requirements
- Liquidity validation

**Emergency Actions**:
- Reduce positions
- Liquidate positions
- Hedge exposure
- Halt trading

**Key Features**:
- Regime-conditional limits (tighter in crisis)
- Complete audit trail of all decisions
- Escalation to human oversight
- Emergency trigger detection

**Key Methods**:
- `validate_trade(strategy, current_state)` - Approve/reject trades
- `check_emergency_triggers(state)` - Detect emergency conditions
- `execute_emergency_action(action, state)` - Execute emergency response

---

#### 6. RegimeDetector (`src/volatility/regime_detector.py`)

**Purpose**: Probabilistic classification of market volatility regime

**Regimes**:
- Low Volatility: VIX < 15, stable markets
- High Volatility: VIX 15-30, elevated uncertainty
- Crisis: VIX > 30, extreme stress
- Transition: Rapid regime changes

**Key Features**:
- Probabilistic classification (not binary)
- Regime history tracking
- Transition detection
- Regime-conditional parameter adaptation

**Key Methods**:
- `detect_regime(vix, realized_vol, correlation)` - Classify current regime
- `get_regime_probabilities()` - Get probability distribution
- `detect_transition()` - Identify rapid regime changes

---

#### 7. DispersionModule (`src/volatility/dispersion_module.py`)

**Purpose**: Trade implied vs realized correlation spreads

**Strategy**:
- Long index options (implied correlation)
- Short constituent options (realized correlation)
- Variance-weighted position sizing
- Delta-neutral rebalancing

**Key Features**:
- Implied correlation computation from index options
- Realized correlation from constituent stocks
- Variance contribution weighting
- Daily rebalancing with threshold logic

**Key Methods**:
- `identify_opportunities(index_iv, constituent_ivs, weights)` - Find dispersion trades
- `compute_position_sizes(opportunity, capital)` - Size variance-weighted positions
- `rebalance_positions(positions, current_deltas)` - Maintain delta neutrality

---

#### 8. GammaScalper (`src/volatility/gamma_scalper.py`)

**Purpose**: Monetize gamma through dynamic delta hedging

**Strategy**:
- Long gamma positions (straddles, strangles)
- Dynamic hedging when delta exceeds threshold
- Profit from realized > implied volatility

**Key Features**:
- Optimal hedging threshold calculation
- Realized variance tracking from hedge history
- Adaptive hedging frequency
- Expiration-aware adjustments

**Key Methods**:
- `identify_opportunities(positions, state)` - Find gamma scalping candidates
- `compute_hedge_threshold(position, params)` - Calculate optimal hedge trigger
- `generate_hedge_orders(position, current_delta)` - Create hedge orders

---

#### 9. CapitalAllocator (`src/volatility/capital_allocator.py`)

**Purpose**: Regime-adaptive capital allocation across strategy buckets

**Allocation Methods**:
- Kelly criterion with fractional sizing
- Historical performance by regime
- Drawdown-based adjustment

**Constraints**:
- Min/max allocation bounds per strategy
- Regime-conditional constraints (e.g., zero short vol in crisis)
- Diversification requirements

**Key Features**:
- Automatic reallocation on regime changes
- Drawdown tracking and recovery detection
- Performance-based allocation adjustment

**Key Methods**:
- `allocate_capital(total_capital, regime, performance_history)` - Compute allocations
- `apply_constraints(allocations, regime)` - Enforce regime-specific limits
- `adjust_for_drawdown(allocations, drawdowns)` - Reduce allocation in drawdown

---

#### 10. MonteCarloEngine (`src/volatility/monte_carlo_engine.py`)

**Purpose**: Risk assessment through simulation of correlated price paths

**Simulation Features**:
- Correlated price paths with fat-tailed distributions (Student-t)
- Stochastic volatility (Heston model)
- Volatility clustering effects
- Portfolio revaluation along paths

**Risk Metrics**:
- Value-at-Risk (VaR) at 95%, 99%, 99.9%
- Conditional VaR (CVaR / Expected Shortfall)
- Maximum drawdown
- Probability of ruin

**Stress Scenarios**:
- 2008 financial crisis
- 2020 COVID crash
- Combined crisis scenario
- Correlation breakdown

**Key Methods**:
- `simulate_paths(n_paths, n_steps, correlations)` - Generate price paths
- `compute_portfolio_pnl(positions, paths)` - Revalue portfolio
- `compute_risk_metrics(pnl_distribution)` - Calculate VaR/CVaR
- `run_stress_test(scenario, positions)` - Execute stress scenario

---

#### 11. ExecutionInterface (`src/volatility/execution_interface.py`)

**Purpose**: Generate and manage execution instructions

**Key Features**:
- Order generation from approved strategies
- Multi-venue routing based on liquidity
- Pre-trade risk checks
- Order status tracking (pending, filled, rejected, cancelled)
- Order modification and cancellation

**Order Types**:
- Market orders
- Limit orders
- Stop orders

**Key Methods**:
- `generate_orders(strategy, execution_params)` - Create orders from strategy
- `submit_order(order)` - Submit to execution venue
- `modify_order(order_id, new_params)` - Modify existing order
- `cancel_order(order_id)` - Cancel order
- `get_order_status(order_id)` - Query order state

---

#### 12. PerformanceMonitor (`src/volatility/performance_monitor.py`)

**Purpose**: Real-time P&L tracking and performance attribution

**P&L Decomposition**:
- Greeks contributions (delta P&L, gamma P&L, vega P&L, theta P&L)
- Realized vs implied volatility per position
- Variance P&L

**Performance Attribution**:
- Alpha (strategy skill) vs Beta (market exposure)
- Regime-conditional performance analysis
- Performance statistics (Sharpe, Sortino, max drawdown, win rate)

**Key Features**:
- Real-time P&L updates
- Performance degradation detection
- Diagnostic recommendations

**Key Methods**:
- `update_pnl(positions, state)` - Update real-time P&L
- `decompose_pnl(pnl_history)` - Attribute P&L to Greeks
- `compute_performance_stats(returns, regime)` - Calculate statistics
- `detect_degradation(recent_perf, historical_perf)` - Alert on deterioration

---

#### 13. UnifiedVolatilityEngine (`src/volatility/unified_engine.py`)

**Purpose**: Main orchestrator coordinating all components

**Key Responsibilities**:
- Component lifecycle management
- Event-driven communication between components
- Error handling and recovery at component boundaries
- Complete trading cycle execution

**Event Types**:
- STATE_UPDATE, REGIME_CHANGE
- STRATEGY_GENERATED, STRATEGY_APPROVED, STRATEGY_REJECTED
- ORDER_SUBMITTED, ORDER_FILLED, ORDER_FAILED
- GREEKS_VIOLATION, RISK_ALERT, EMERGENCY_ACTION
- COMPONENT_ERROR

**Key Methods**:
- `run_trading_cycle()` - Execute complete trading cycle
- `subscribe_to_events(event_type, callback)` - Register event handlers
- `handle_component_error(error)` - Recover from component failures
- `shutdown()` - Graceful system shutdown

---

## Component Interactions

### Trading Cycle Flow

1. **Market Data Ingestion**
   - New market data arrives (prices, IVs, volumes)
   - StateEngine updates IV surfaces and correlations

2. **Regime Detection**
   - RegimeDetector classifies current market regime
   - If regime changes, event propagates to all components

3. **Strategy Generation**
   - StrategyGenerator creates candidate structures
   - Targets regime-appropriate Greeks profiles

4. **Risk Validation**
   - RiskAuthority validates each strategy
   - Checks position limits, Greeks limits, margin
   - Approves or rejects with detailed reasoning

5. **Capital Allocation**
   - CapitalAllocator determines capital per strategy bucket
   - Applies regime-conditional constraints
   - Adjusts for drawdowns

6. **Execution**
   - ExecutionInterface generates orders for approved strategies
   - Routes to optimal venues
   - Tracks order status and updates portfolio

7. **Performance Monitoring**
   - PerformanceMonitor tracks real-time P&L
   - Decomposes P&L into Greeks contributions
   - Alerts on performance degradation

### Emergency Response Flow

1. **Trigger Detection**
   - MonteCarloEngine detects risk metric breach (VaR, CVaR)
   - OR GreeksAggregator detects Greeks limit violation
   - OR PerformanceMonitor detects severe drawdown

2. **Risk Authority Activation**
   - RiskAuthority receives emergency alert
   - Evaluates severity and determines action

3. **Emergency Action Execution**
   - Reduce positions (scale down exposure)
   - Liquidate positions (exit specific trades)
   - Hedge exposure (add protective positions)
   - Halt trading (stop all new trades)

4. **Audit and Escalation**
   - Complete audit trail logged
   - Human oversight notified
   - System awaits manual intervention if needed

---

## Configuration Management

### Configuration System (`src/volatility/config.py`)

**Configuration Profiles**:
- Aggressive: Higher risk limits, more leverage
- Moderate: Balanced risk/reward
- Conservative: Tight limits, lower leverage

**Key Parameters**:
- Position limits (per underlying, total)
- Greeks limits (delta, gamma, vega, theta)
- Risk thresholds (VaR, CVaR, max drawdown)
- Regime-conditional adjustments
- Execution parameters (order types, venues)

**Features**:
- Schema validation on load
- Hot-reloading for non-critical parameters
- Configuration versioning
- Audit trail of configuration changes

---

## State Persistence

### Snapshot System

**Automatic Snapshots**:
- Every 5 minutes during trading
- On regime changes
- Before emergency actions
- On system shutdown

**Snapshot Contents**:
- Complete VolatilityState
- All component states
- Configuration version
- Timestamp and metadata

**Recovery**:
- Automatic state validation on load
- Fallback to previous snapshot if corrupted
- Manual recovery procedures available

---

## Performance Characteristics

### Latency Targets

| Operation | Target | Actual (P95) |
|-----------|--------|--------------|
| Greeks Computation | <50ms | 19.17ms |
| State Update | <100ms | 0.02ms |
| Strategy Generation | <200ms | ~150ms |
| Risk Validation | <50ms | ~30ms |

### Throughput

- Handles 1000+ positions in portfolio
- Processes 100+ strategy candidates per cycle
- Executes 10,000 Monte Carlo paths in <2s (parallel)

### Scalability

- Linear scaling verified up to 1000 positions
- Parallel Monte Carlo with 4 workers: 3.3x speedup
- Optimized Greeks computation: 73.7% improvement

---

## Testing Strategy

### Property-Based Tests (Hypothesis)

17 universal correctness properties validated:
- No-arbitrage constraints
- Put-call parity
- Greeks monotonicity and boundary conditions
- State serialization round-trip
- Generated structures satisfy target Greeks
- Composed Greeks are additive
- Risk authority rejects limit violations
- Dispersion positions are delta-neutral
- Hedging reduces delta exposure
- Realized variance is non-negative
- Allocations sum to total capital
- Allocations respect bounds
- Simulated paths have correct mean
- Volatility paths are non-negative
- Portfolio survives stress scenarios
- Strategy behavior stable across regime transitions

### Integration Tests

- Complete trading day simulation
- Multi-strategy portfolio management
- Regime transition handling
- Emergency action execution
- State persistence and recovery

### Stress Tests

- 2008 financial crisis scenario
- 2020 COVID crash scenario
- Combined crisis scenario
- Correlation breakdown scenarios

---

## Deployment Architecture

### System Requirements

- Python 3.9+
- NumPy, SciPy for numerical computation
- Pandas for data handling
- Hypothesis for property-based testing
- 8GB+ RAM recommended
- Multi-core CPU for parallel Monte Carlo

### External Dependencies

- Market data feed (real-time prices, IVs)
- Execution venues (broker APIs)
- Historical data for backtesting

### Monitoring

- Real-time P&L dashboard
- Greeks monitoring display
- Regime visualization
- Performance attribution charts
- Risk metrics dashboard
- Audit trail viewer

---

## Operational Procedures

### System Startup

1. Load configuration profile
2. Restore state from latest snapshot
3. Validate state consistency
4. Initialize all components
5. Subscribe to market data feed
6. Begin trading cycles

### Daily Operations

1. Pre-market: Review overnight positions
2. Market open: Begin trading cycles
3. Intraday: Monitor Greeks, P&L, risk metrics
4. Market close: Final rebalancing
5. Post-market: Performance review, snapshot

### Emergency Procedures

1. **Greeks Violation**: Automatic hedging or position reduction
2. **Risk Metric Breach**: Emergency action per RiskAuthority
3. **Component Failure**: Automatic recovery or graceful degradation
4. **Market Disruption**: Halt trading, protect positions

### System Shutdown

1. Cancel all pending orders
2. Save final state snapshot
3. Generate end-of-day reports
4. Archive audit trail
5. Graceful component shutdown

---

## Security and Compliance

### Audit Trail

Complete logging of:
- All trade decisions (approved/rejected)
- Emergency actions
- Configuration changes
- Component errors
- Performance metrics

### Risk Controls

- Pre-trade validation (position limits, margin)
- Real-time monitoring (Greeks, VaR, CVaR)
- Emergency triggers (automatic response)
- Human oversight escalation

### Data Integrity

- State validation on all updates
- Snapshot integrity checks
- Configuration schema validation
- No-arbitrage constraint enforcement

---

## Future Enhancements

### Planned Features

- Machine learning for regime prediction
- Reinforcement learning for hedging optimization
- Multi-asset class support (FX, commodities)
- Advanced execution algorithms (TWAP, VWAP, POV)
- Real-time risk aggregation across multiple portfolios

### Scalability Improvements

- Distributed Monte Carlo simulation
- GPU acceleration for Greeks computation
- Streaming data pipeline
- Horizontal scaling for multiple strategies

---

## References

- Requirements: `.kiro/specs/unified-volatility-engine/requirements.md`
- Design: `.kiro/specs/unified-volatility-engine/design.md`
- Tasks: `.kiro/specs/unified-volatility-engine/tasks.md`
- Performance: `docs/PERFORMANCE_OPTIMIZATION_SUMMARY.md`
