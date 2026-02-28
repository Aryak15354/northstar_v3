# Design Document: Unified Volatility Engine

## Overview

The Unified Volatility Engine transforms the Northstar v3 options trading system from a collection of loosely coupled components into a cohesive institutional-grade volatility trading organism. The design centers on three core principles:

1. **Single Source of Truth**: All volatility-related state (IV surface, correlations, regime, Greeks) flows through one unified engine
2. **Exposure-Based Reasoning**: Strategies are generated from target Greeks rather than selected from templates
3. **Absolute Risk Authority**: Independent risk component with veto power over all trading decisions

The architecture eliminates redundancy by consolidating multiple state managers, risk engines, and regime detectors into unified components with clear ownership and interfaces.

### Key Design Decisions

**AST-Based Strategy Generation**: We use Abstract Syntax Trees to represent option structures programmatically, enabling composition of complex multi-leg positions from primitives. This allows the system to explore the full space of possible structures rather than being limited to pre-defined templates.

**Regime-Conditional Everything**: Every component adapts behavior based on the current volatility regime. Capital allocation, strategy generation, risk limits, and hedging frequency all vary by regime.

**Greeks as First-Class Citizens**: Portfolio Greeks are computed in real-time and treated as primary risk metrics. All strategies are expressed as target Greeks profiles.

**Separation of Concerns**: Strategy generation, risk management, and execution are strictly separated with defined interfaces. The Risk Authority operates independently and cannot be overridden.

## Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                   Unified Volatility Engine                  │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────────┐         ┌──────────────────┐          │
│  │  Volatility      │────────▶│   Strategy       │          │
│  │  State Engine    │         │   Generator      │          │
│  └──────────────────┘         └──────────────────┘          │
│         │                              │                     │
│         │                              ▼                     │
│         │                     ┌──────────────────┐          │
│         │                     │     Greeks       │          │
│         │                     │   Aggregator     │          │
│         │                     └──────────────────┘          │
│         │                              │                     │
│         ▼                              ▼                     │
│  ┌──────────────────┐         ┌──────────────────┐          │
│  │    Regime        │────────▶│  Risk Authority  │◀─────┐   │
│  │   Detector       │         │  (Veto Power)    │      │   │
│  └──────────────────┘         └──────────────────┘      │   │
│         │                              │                 │   │
│         │                              │                 │   │
│         ▼                              ▼                 │   │
│  ┌──────────────────┐         ┌──────────────────┐      │   │
│  │    Capital       │         │  Monte Carlo     │──────┘   │
│  │   Allocator      │         │  Risk Engine     │          │
│  └──────────────────┘         └──────────────────┘          │
│         │                                                    │
│         ▼                                                    │
│  ┌──────────────────┐         ┌──────────────────┐          │
│  │   Dispersion     │         │     Gamma        │          │
│  │     Module       │         │    Scalper       │          │
│  └──────────────────┘         └──────────────────┘          │
│                                                               │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
                  ┌──────────────────┐
                  │    Execution     │
                  │    Interface     │
                  └──────────────────┘
```

### Data Flow

1. **Market Data Ingestion**: Raw option chains, spot prices, and macro data enter the system
2. **Volatility State Construction**: IV surface fitted, correlations computed, regime detected
3. **Strategy Generation**: Target exposures specified, AST structures generated
4. **Risk Validation**: Risk Authority validates against limits
5. **Capital Allocation**: Regime-based allocation determines position sizing
6. **Execution**: Orders generated and submitted to execution interface
7. **Greeks Monitoring**: Real-time portfolio Greeks tracked and compared to targets
8. **Performance Attribution**: P&L decomposed into Greeks contributions



## Components and Interfaces

### 1. Volatility State Engine

**Purpose**: Single source of truth for all volatility-related market state.

**State Components**:
```python
@dataclass
class VolatilityState:
    timestamp: datetime
    
    # IV Surface
    iv_surface: IVSurface  # Fitted volatility surface
    surface_quality: float  # Fit quality metric [0, 1]
    
    # Regime
    regime: RegimeState  # Current regime classification
    regime_probabilities: Dict[str, float]  # Probability distribution
    regime_duration: timedelta  # Time in current regime
    
    # Correlations
    correlation_matrix: np.ndarray  # Asset correlations
    implied_correlation: float  # From index options
    realized_correlation: float  # From constituent stocks
    
    # Volatility Metrics
    vix_level: float
    vix_term_structure: Dict[str, float]  # VIX futures curve
    realized_vol_20d: float
    realized_vol_60d: float
    vol_of_vol: float  # Second-order uncertainty
    
    # Event Risk
    upcoming_events: List[EventRisk]  # Earnings, FOMC, etc.
    event_premium: Dict[str, float]  # Extra vol for events
    
    # Greeks Snapshot
    portfolio_greeks: PortfolioGreeks
    
    # Metadata
    data_sources: Dict[str, datetime]  # Last update per source
    validation_status: ValidationStatus
```

**Interface**:
```python
class VolatilityStateEngine:
    def update_iv_surface(self, option_chain: OptionChain) -> None:
        """Fit new IV surface from option prices"""
        
    def update_regime(self, market_data: MarketData) -> RegimeState:
        """Detect current volatility regime"""
        
    def update_correlations(self, returns: pd.DataFrame) -> np.ndarray:
        """Compute rolling correlation matrix"""
        
    def get_state(self) -> VolatilityState:
        """Return complete current state"""
        
    def get_state_at(self, timestamp: datetime) -> VolatilityState:
        """Return historical state snapshot"""
        
    def validate_state(self) -> ValidationResult:
        """Check state consistency and data quality"""
        
    def persist_state(self) -> None:
        """Save state snapshot to disk"""
        
    def restore_state(self, timestamp: datetime) -> None:
        """Restore from saved snapshot"""
```

**IV Surface Fitting**:
- Use SVI (Stochastic Volatility Inspired) parameterization for robustness
- Enforce no-arbitrage constraints (calendar spreads, butterfly spreads)
- Fallback to simpler models (flat vol, sticky strike) if fit fails
- Compute confidence intervals based on fit residuals
- Extrapolate for missing strikes using wing behavior

**Regime Detection Logic**:
```python
def detect_regime(self, state: MarketData) -> RegimeState:
    # Feature extraction
    vix_level = state.vix
    vix_slope = state.vix_3m - state.vix_1m
    realized_vol = state.realized_vol_20d
    vol_ratio = vix_level / realized_vol
    correlation = state.avg_correlation
    
    # Regime classification
    if vix_level > 40 or correlation > 0.8:
        return RegimeState.CRISIS
    elif vix_level > 25:
        return RegimeState.HIGH_VOL
    elif vix_level < 15 and vix_slope < 0:
        return RegimeState.LOW_VOL
    else:
        return RegimeState.TRANSITION
```

### 2. Strategy Generator (AST-Based)

**Purpose**: Generate option structures from target exposure specifications.

**AST Representation**:
```python
class OptionNode:
    """Base class for option structure AST"""
    pass

class Call(OptionNode):
    strike: float
    expiry: date
    quantity: int

class Put(OptionNode):
    strike: float
    expiry: date
    quantity: int

class Spread(OptionNode):
    long_leg: OptionNode
    short_leg: OptionNode

class Straddle(OptionNode):
    strike: float
    expiry: date
    quantity: int
    
class Butterfly(OptionNode):
    lower_strike: float
    middle_strike: float
    upper_strike: float
    expiry: date
    quantity: int

class Calendar(OptionNode):
    strike: float
    near_expiry: date
    far_expiry: date
    quantity: int
```

**Generation Algorithm**:
```python
class StrategyGenerator:
    def generate(
        self,
        target_greeks: TargetGreeks,
        constraints: Constraints,
        state: VolatilityState
    ) -> List[OptionStructure]:
        """
        Generate option structures matching target Greeks.
        
        Algorithm:
        1. Decompose target Greeks into primitive exposures
        2. Generate candidate structures using AST composition
        3. Price each structure and compute actual Greeks
        4. Rank by cost-efficiency and constraint satisfaction
        5. Return top N candidates
        """
        
        # Step 1: Decompose targets
        primitives = self._decompose_greeks(target_greeks)
        
        # Step 2: Generate candidates
        candidates = []
        for primitive in primitives:
            structures = self._generate_structures(primitive, state)
            candidates.extend(structures)
        
        # Step 3: Price and compute Greeks
        for structure in candidates:
            structure.price = self._price_structure(structure, state)
            structure.greeks = self._compute_greeks(structure, state)
        
        # Step 4: Filter and rank
        feasible = [s for s in candidates if self._satisfies_constraints(s, constraints)]
        ranked = sorted(feasible, key=lambda s: s.price / s.greeks.vega)
        
        # Step 5: Return top candidates
        return ranked[:3]
    
    def _decompose_greeks(self, target: TargetGreeks) -> List[PrimitiveExposure]:
        """Break down target Greeks into basic exposures"""
        primitives = []
        
        # Vega exposure
        if target.vega > 0:
            primitives.append(PrimitiveExposure(type="long_vol", size=target.vega))
        elif target.vega < 0:
            primitives.append(PrimitiveExposure(type="short_vol", size=-target.vega))
        
        # Gamma exposure
        if target.gamma > 0:
            primitives.append(PrimitiveExposure(type="long_gamma", size=target.gamma))
        
        # Delta exposure
        if abs(target.delta) > 0.1:
            primitives.append(PrimitiveExposure(type="directional", size=target.delta))
        
        return primitives
    
    def _generate_structures(
        self,
        primitive: PrimitiveExposure,
        state: VolatilityState
    ) -> List[OptionStructure]:
        """Generate structures for a primitive exposure"""
        
        if primitive.type == "long_vol":
            return [
                self._create_straddle(state),
                self._create_strangle(state),
                self._create_call_spread(state),
            ]
        elif primitive.type == "short_vol":
            return [
                self._create_iron_condor(state),
                self._create_short_strangle(state),
            ]
        elif primitive.type == "long_gamma":
            return [
                self._create_atm_straddle(state),
                self._create_calendar_spread(state),
            ]
        else:
            return []
```

**Structure Composition**:
```python
def compose_structures(
    self,
    structures: List[OptionStructure]
) -> OptionStructure:
    """Combine multiple structures into a complex position"""
    
    # Build AST by combining nodes
    root = CompositeNode(children=structures)
    
    # Compute combined Greeks
    combined_greeks = sum(s.greeks for s in structures)
    
    # Validate no-arbitrage
    if not self._validate_arbitrage_free(root):
        raise ValueError("Combined structure violates arbitrage bounds")
    
    return OptionStructure(ast=root, greeks=combined_greeks)
```



### 3. Portfolio Greeks Aggregator

**Purpose**: Real-time portfolio-level Greeks computation with constraint enforcement.

**Data Model**:
```python
@dataclass
class PortfolioGreeks:
    # First-order Greeks
    delta: float  # Price sensitivity
    gamma: float  # Delta sensitivity
    vega: float   # Volatility sensitivity
    theta: float  # Time decay
    rho: float    # Interest rate sensitivity
    
    # Second-order Greeks
    vanna: float  # Delta sensitivity to vol
    volga: float  # Vega sensitivity to vol
    charm: float  # Delta decay
    vomma: float  # Vega convexity
    
    # Per-underlying breakdown
    delta_by_underlying: Dict[str, float]
    vega_by_underlying: Dict[str, float]
    
    # Metadata
    timestamp: datetime
    num_positions: int
    total_notional: float
```

**Interface**:
```python
class GreeksAggregator:
    def compute_portfolio_greeks(
        self,
        positions: List[Position],
        state: VolatilityState
    ) -> PortfolioGreeks:
        """Compute portfolio-level Greeks from all positions"""
        
        greeks = PortfolioGreeks.zero()
        
        for position in positions:
            # Compute position Greeks
            pos_greeks = self._compute_position_greeks(position, state)
            
            # Aggregate to portfolio level
            greeks.delta += pos_greeks.delta * position.quantity
            greeks.gamma += pos_greeks.gamma * position.quantity
            greeks.vega += pos_greeks.vega * position.quantity
            greeks.theta += pos_greeks.theta * position.quantity
            
            # Track by underlying
            underlying = position.underlying
            greeks.delta_by_underlying[underlying] += pos_greeks.delta * position.quantity
            greeks.vega_by_underlying[underlying] += pos_greeks.vega * position.quantity
        
        return greeks
    
    def check_constraints(
        self,
        greeks: PortfolioGreeks,
        limits: GreeksLimits
    ) -> List[ConstraintViolation]:
        """Check if Greeks are within limits"""
        
        violations = []
        
        if abs(greeks.delta) > limits.max_delta:
            violations.append(ConstraintViolation(
                metric="delta",
                value=greeks.delta,
                limit=limits.max_delta
            ))
        
        if abs(greeks.vega) > limits.max_vega:
            violations.append(ConstraintViolation(
                metric="vega",
                value=greeks.vega,
                limit=limits.max_vega
            ))
        
        # Check concentration limits
        for underlying, delta in greeks.delta_by_underlying.items():
            if abs(delta) > limits.max_delta_per_underlying:
                violations.append(ConstraintViolation(
                    metric=f"delta_{underlying}",
                    value=delta,
                    limit=limits.max_delta_per_underlying
                ))
        
        return violations
    
    def scenario_greeks(
        self,
        positions: List[Position],
        state: VolatilityState,
        scenario: Scenario
    ) -> PortfolioGreeks:
        """Compute Greeks under shifted market conditions"""
        
        # Apply scenario shifts
        shifted_state = self._apply_scenario(state, scenario)
        
        # Recompute Greeks
        return self.compute_portfolio_greeks(positions, shifted_state)
```

**Greeks Computation**:
```python
def _compute_position_greeks(
    self,
    position: Position,
    state: VolatilityState
) -> Greeks:
    """Compute Greeks for a single position using Black-Scholes"""
    
    S = state.spot_price
    K = position.strike
    T = (position.expiry - state.timestamp).days / 365
    r = state.risk_free_rate
    sigma = state.iv_surface.get_vol(K, T)
    
    # Black-Scholes formulas
    d1 = (np.log(S/K) + (r + 0.5*sigma**2)*T) / (sigma*np.sqrt(T))
    d2 = d1 - sigma*np.sqrt(T)
    
    if position.option_type == "call":
        delta = norm.cdf(d1)
        theta = (-S*norm.pdf(d1)*sigma/(2*np.sqrt(T)) 
                 - r*K*np.exp(-r*T)*norm.cdf(d2))
    else:  # put
        delta = -norm.cdf(-d1)
        theta = (-S*norm.pdf(d1)*sigma/(2*np.sqrt(T)) 
                 + r*K*np.exp(-r*T)*norm.cdf(-d2))
    
    # Greeks that are same for calls and puts
    gamma = norm.pdf(d1) / (S*sigma*np.sqrt(T))
    vega = S*norm.pdf(d1)*np.sqrt(T) / 100  # Per 1% vol change
    rho = K*T*np.exp(-r*T)*norm.cdf(d2) / 100  # Per 1% rate change
    
    # Second-order Greeks
    vanna = -norm.pdf(d1)*d2/sigma
    volga = S*norm.pdf(d1)*np.sqrt(T)*d1*d2/sigma
    
    return Greeks(
        delta=delta,
        gamma=gamma,
        vega=vega,
        theta=theta,
        rho=rho,
        vanna=vanna,
        volga=volga
    )
```

### 4. Dispersion Trading Module

**Purpose**: Exploit correlation inefficiencies between index and stock volatilities.

**Core Logic**:
```python
class DispersionModule:
    def analyze_dispersion_opportunity(
        self,
        state: VolatilityState
    ) -> Optional[DispersionTrade]:
        """Identify dispersion trading opportunities"""
        
        # Compute implied correlation from index options
        index_var = state.iv_surface.get_variance(atm_strike, expiry)
        
        # Compute weighted average of stock variances
        stock_vars = []
        weights = []
        for stock in self.constituents:
            stock_var = state.iv_surface.get_variance(stock, expiry)
            weight = self._get_index_weight(stock)
            stock_vars.append(stock_var)
            weights.append(weight)
        
        avg_stock_var = np.average(stock_vars, weights=weights)
        
        # Implied correlation
        implied_corr = (index_var - avg_stock_var) / avg_stock_var
        
        # Realized correlation
        realized_corr = state.correlation_matrix.mean()
        
        # Dispersion spread
        spread = implied_corr - realized_corr
        
        # Generate trade if spread exceeds threshold
        if spread > self.entry_threshold:
            return DispersionTrade(
                direction="short_dispersion",  # Short index vol, long stock vol
                spread=spread,
                index_position=self._create_index_position(state),
                stock_positions=self._create_stock_positions(state, weights)
            )
        elif spread < -self.entry_threshold:
            return DispersionTrade(
                direction="long_dispersion",  # Long index vol, short stock vol
                spread=spread,
                index_position=self._create_index_position(state),
                stock_positions=self._create_stock_positions(state, weights)
            )
        
        return None
    
    def rebalance_dispersion(
        self,
        trade: DispersionTrade,
        state: VolatilityState
    ) -> List[Order]:
        """Rebalance delta hedges for dispersion position"""
        
        orders = []
        
        # Compute current portfolio delta
        current_delta = self._compute_dispersion_delta(trade, state)
        
        # Target is delta-neutral
        target_delta = 0.0
        delta_imbalance = current_delta - target_delta
        
        # Generate hedging orders
        if abs(delta_imbalance) > self.rebalance_threshold:
            # Hedge using index futures
            hedge_quantity = -delta_imbalance / state.index_delta
            orders.append(Order(
                instrument="index_future",
                quantity=hedge_quantity,
                order_type="market"
            ))
        
        return orders
```

**Variance Weighting**:
```python
def _get_variance_weights(
    self,
    constituents: List[str],
    state: VolatilityState
) -> Dict[str, float]:
    """Compute variance-weighted position sizes"""
    
    # Get index weights
    index_weights = self._get_index_weights(constituents)
    
    # Adjust for variance contribution
    variance_weights = {}
    for stock in constituents:
        stock_vol = state.iv_surface.get_vol(stock)
        index_weight = index_weights[stock]
        
        # Variance contribution = weight^2 * vol^2 + 2*weight*cov_terms
        var_contribution = (index_weight * stock_vol)**2
        
        variance_weights[stock] = var_contribution
    
    # Normalize
    total = sum(variance_weights.values())
    return {k: v/total for k, v in variance_weights.items()}
```



### 5. Gamma Scalping Engine

**Purpose**: Harvest realized variance through systematic delta-hedging of long gamma positions.

**Core Algorithm**:
```python
class GammaScalper:
    def compute_hedging_threshold(
        self,
        position: Position,
        state: VolatilityState
    ) -> float:
        """Compute optimal hedging threshold based on gamma and transaction costs"""
        
        # Get position Greeks
        gamma = position.greeks.gamma
        vega = position.greeks.vega
        
        # Transaction cost per hedge
        tc = self.transaction_cost_bps * state.spot_price / 10000
        
        # Optimal threshold minimizes: hedging_cost + gamma_slippage
        # Threshold = sqrt(2 * tc / (gamma * S))
        threshold = np.sqrt(2 * tc / (gamma * state.spot_price))
        
        return threshold
    
    def should_hedge(
        self,
        position: Position,
        state: VolatilityState,
        last_hedge_price: float
    ) -> bool:
        """Determine if delta hedge should be executed"""
        
        current_price = state.spot_price
        price_move = abs(current_price - last_hedge_price) / last_hedge_price
        
        threshold = self.compute_hedging_threshold(position, state)
        
        return price_move > threshold
    
    def generate_hedge_order(
        self,
        position: Position,
        state: VolatilityState
    ) -> Order:
        """Generate delta-hedging order"""
        
        # Current delta exposure
        current_delta = position.greeks.delta * position.quantity
        
        # Target is delta-neutral
        target_delta = 0.0
        
        # Hedge quantity
        hedge_quantity = -(current_delta - target_delta)
        
        return Order(
            instrument=position.underlying,
            quantity=hedge_quantity,
            order_type="market",
            reason="gamma_scalp_hedge"
        )
    
    def track_realized_pnl(
        self,
        position: Position,
        hedges: List[Hedge],
        state: VolatilityState
    ) -> RealizedPnL:
        """Track P&L from gamma scalping"""
        
        # Option P&L (mark-to-market)
        option_pnl = position.current_value - position.entry_value
        
        # Hedge P&L (realized)
        hedge_pnl = sum(h.pnl for h in hedges)
        
        # Total realized P&L
        total_pnl = option_pnl + hedge_pnl
        
        # Compute realized variance
        realized_var = self._compute_realized_variance(hedges)
        
        # Implied variance paid
        implied_var = position.entry_iv ** 2
        
        # Variance P&L
        var_pnl = (realized_var - implied_var) * position.vega * position.quantity
        
        return RealizedPnL(
            total_pnl=total_pnl,
            option_pnl=option_pnl,
            hedge_pnl=hedge_pnl,
            variance_pnl=var_pnl,
            realized_var=realized_var,
            implied_var=implied_var
        )
    
    def _compute_realized_variance(self, hedges: List[Hedge]) -> float:
        """Compute realized variance from hedge history"""
        
        # Extract price moves from hedges
        returns = []
        for i in range(1, len(hedges)):
            ret = np.log(hedges[i].price / hedges[i-1].price)
            returns.append(ret)
        
        # Annualized realized variance
        variance = np.var(returns) * 252  # Assuming daily hedges
        
        return variance
```

**Adaptive Hedging Frequency**:
```python
def adapt_hedging_frequency(
    self,
    position: Position,
    state: VolatilityState,
    performance: RealizedPnL
) -> HedgingMode:
    """Adjust hedging frequency based on realized vs implied variance"""
    
    var_ratio = performance.realized_var / performance.implied_var
    
    if var_ratio > 1.5:
        # Realized vol much higher than implied - hedge more frequently
        return HedgingMode.HIGH_FREQUENCY
    elif var_ratio > 1.1:
        # Realized vol slightly higher - normal hedging
        return HedgingMode.NORMAL
    else:
        # Realized vol lower than implied - reduce hedging
        return HedgingMode.LOW_FREQUENCY
```

### 6. Regime-Adaptive Capital Allocator

**Purpose**: Dynamically allocate capital across strategy buckets based on volatility regime.

**Allocation Model**:
```python
class CapitalAllocator:
    def allocate_capital(
        self,
        total_capital: float,
        state: VolatilityState,
        performance_history: PerformanceHistory
    ) -> Dict[str, float]:
        """Allocate capital across strategy buckets"""
        
        regime = state.regime
        regime_probs = state.regime_probabilities
        
        # Get historical performance by regime
        strategy_returns = {}
        for strategy in self.strategy_buckets:
            returns = performance_history.get_returns(strategy, regime)
            strategy_returns[strategy] = returns
        
        # Compute Kelly fractions
        kelly_fractions = {}
        for strategy, returns in strategy_returns.items():
            if len(returns) > 0:
                mean_return = np.mean(returns)
                variance = np.var(returns)
                
                # Kelly criterion: f = mean / variance
                kelly = mean_return / variance if variance > 0 else 0
                
                # Apply fractional Kelly for safety
                kelly_fractions[strategy] = kelly * self.kelly_fraction
            else:
                kelly_fractions[strategy] = 0
        
        # Apply regime-conditional constraints
        allocations = self._apply_regime_constraints(
            kelly_fractions,
            regime,
            regime_probs
        )
        
        # Enforce min/max bounds
        allocations = self._enforce_bounds(allocations)
        
        # Normalize to total capital
        total_fraction = sum(allocations.values())
        if total_fraction > 0:
            allocations = {k: v/total_fraction * total_capital 
                          for k, v in allocations.items()}
        
        return allocations
    
    def _apply_regime_constraints(
        self,
        allocations: Dict[str, float],
        regime: RegimeState,
        regime_probs: Dict[str, float]
    ) -> Dict[str, float]:
        """Apply regime-specific allocation constraints"""
        
        constrained = allocations.copy()
        
        if regime == RegimeState.CRISIS:
            # Crisis: zero allocation to short vol strategies
            constrained["short_vol"] = 0
            constrained["dispersion"] = 0
            
            # Increase allocation to long vol and hedging
            constrained["long_vol"] *= 2.0
            constrained["tail_hedge"] *= 3.0
        
        elif regime == RegimeState.LOW_VOL:
            # Low vol: favor short vol and carry strategies
            constrained["short_vol"] *= 1.5
            constrained["gamma_scalp"] *= 0.5
        
        elif regime == RegimeState.HIGH_VOL:
            # High vol: favor gamma scalping and dispersion
            constrained["gamma_scalp"] *= 1.5
            constrained["dispersion"] *= 1.5
            constrained["short_vol"] *= 0.5
        
        elif regime == RegimeState.TRANSITION:
            # Uncertain regime: increase market-neutral strategies
            constrained["dispersion"] *= 1.2
            constrained["relative_value"] *= 1.2
            
            # Reduce directional exposure
            constrained["directional_vol"] *= 0.5
        
        return constrained
    
    def _enforce_bounds(
        self,
        allocations: Dict[str, float]
    ) -> Dict[str, float]:
        """Enforce min/max allocation bounds"""
        
        bounded = {}
        for strategy, allocation in allocations.items():
            min_alloc = self.min_allocations.get(strategy, 0.0)
            max_alloc = self.max_allocations.get(strategy, 1.0)
            
            bounded[strategy] = np.clip(allocation, min_alloc, max_alloc)
        
        return bounded
```

**Drawdown-Based Adjustment**:
```python
def adjust_for_drawdown(
    self,
    allocations: Dict[str, float],
    performance: PerformanceHistory
) -> Dict[str, float]:
    """Reduce allocation to strategies in drawdown"""
    
    adjusted = allocations.copy()
    
    for strategy in allocations.keys():
        # Compute current drawdown
        drawdown = performance.get_drawdown(strategy)
        
        if drawdown > self.drawdown_threshold:
            # Reduce allocation proportionally to drawdown
            reduction_factor = 1.0 - (drawdown / self.max_drawdown)
            adjusted[strategy] *= max(reduction_factor, 0.1)  # Min 10% allocation
    
    return adjusted
```



### 7. Monte Carlo Risk Engine

**Purpose**: Stochastic simulation of portfolio outcomes for tail risk quantification.

**Simulation Framework**:
```python
class MonteCarloRiskEngine:
    def simulate_portfolio(
        self,
        positions: List[Position],
        state: VolatilityState,
        horizon_days: int,
        num_paths: int = 10000
    ) -> SimulationResult:
        """Simulate portfolio P&L over horizon"""
        
        # Generate correlated price paths
        price_paths = self._generate_price_paths(
            state,
            horizon_days,
            num_paths
        )
        
        # Generate volatility paths (stochastic vol)
        vol_paths = self._generate_vol_paths(
            state,
            horizon_days,
            num_paths
        )
        
        # Simulate P&L for each path
        pnl_paths = np.zeros((num_paths, horizon_days))
        
        for path_idx in range(num_paths):
            portfolio_value = self._compute_portfolio_value(positions, state)
            
            for day in range(horizon_days):
                # Update market state
                sim_state = VolatilityState(
                    spot_price=price_paths[path_idx, day],
                    iv_surface=self._update_iv_surface(
                        state.iv_surface,
                        vol_paths[path_idx, day]
                    ),
                    timestamp=state.timestamp + timedelta(days=day)
                )
                
                # Revalue portfolio
                new_value = self._compute_portfolio_value(positions, sim_state)
                pnl_paths[path_idx, day] = new_value - portfolio_value
                portfolio_value = new_value
        
        return SimulationResult(
            pnl_paths=pnl_paths,
            price_paths=price_paths,
            vol_paths=vol_paths
        )
    
    def _generate_price_paths(
        self,
        state: VolatilityState,
        horizon_days: int,
        num_paths: int
    ) -> np.ndarray:
        """Generate correlated price paths with fat tails"""
        
        dt = 1/252  # Daily steps
        
        # Use Student-t distribution for fat tails
        df = 5  # Degrees of freedom
        
        paths = np.zeros((num_paths, horizon_days, len(self.underlyings)))
        
        for underlying_idx, underlying in enumerate(self.underlyings):
            S0 = state.spot_prices[underlying]
            vol = state.realized_vol_20d
            
            for path_idx in range(num_paths):
                S = S0
                for day in range(horizon_days):
                    # Student-t innovations for fat tails
                    z = np.random.standard_t(df) * np.sqrt((df-2)/df)
                    
                    # Geometric Brownian motion with fat tails
                    S = S * np.exp((self.drift - 0.5*vol**2)*dt + vol*np.sqrt(dt)*z)
                    paths[path_idx, day, underlying_idx] = S
        
        return paths
    
    def _generate_vol_paths(
        self,
        state: VolatilityState,
        horizon_days: int,
        num_paths: int
    ) -> np.ndarray:
        """Generate stochastic volatility paths using Heston model"""
        
        dt = 1/252
        
        # Heston parameters
        kappa = 2.0  # Mean reversion speed
        theta = state.realized_vol_20d ** 2  # Long-term variance
        sigma_v = state.vol_of_vol  # Vol of vol
        
        vol_paths = np.zeros((num_paths, horizon_days))
        
        for path_idx in range(num_paths):
            v = state.realized_vol_20d ** 2  # Initial variance
            
            for day in range(horizon_days):
                # Heston dynamics: dv = kappa*(theta - v)*dt + sigma_v*sqrt(v)*dW
                dW = np.random.randn() * np.sqrt(dt)
                v = v + kappa*(theta - v)*dt + sigma_v*np.sqrt(max(v, 0))*dW
                v = max(v, 0)  # Ensure non-negative
                
                vol_paths[path_idx, day] = np.sqrt(v)
        
        return vol_paths
    
    def compute_risk_metrics(
        self,
        simulation: SimulationResult
    ) -> RiskMetrics:
        """Compute VaR, CVaR, and other risk metrics"""
        
        # Terminal P&L distribution
        terminal_pnl = simulation.pnl_paths[:, -1]
        
        # Value at Risk
        var_95 = np.percentile(terminal_pnl, 5)
        var_99 = np.percentile(terminal_pnl, 1)
        var_999 = np.percentile(terminal_pnl, 0.1)
        
        # Conditional Value at Risk (expected shortfall)
        cvar_95 = terminal_pnl[terminal_pnl <= var_95].mean()
        cvar_99 = terminal_pnl[terminal_pnl <= var_99].mean()
        
        # Maximum drawdown across paths
        max_drawdown = self._compute_max_drawdown(simulation.pnl_paths)
        
        # Probability of ruin (losing more than X%)
        ruin_threshold = -0.20  # 20% loss
        prob_ruin = (terminal_pnl < ruin_threshold).mean()
        
        return RiskMetrics(
            var_95=var_95,
            var_99=var_99,
            var_999=var_999,
            cvar_95=cvar_95,
            cvar_99=cvar_99,
            max_drawdown=max_drawdown,
            prob_ruin=prob_ruin
        )
    
    def stress_test(
        self,
        positions: List[Position],
        state: VolatilityState,
        scenario: StressScenario
    ) -> StressTestResult:
        """Test portfolio under extreme scenarios"""
        
        # Apply scenario shocks
        stressed_state = self._apply_stress_scenario(state, scenario)
        
        # Revalue portfolio
        base_value = self._compute_portfolio_value(positions, state)
        stressed_value = self._compute_portfolio_value(positions, stressed_state)
        
        pnl = stressed_value - base_value
        pnl_pct = pnl / base_value
        
        # Check if portfolio survives
        survives = pnl_pct > -self.max_loss_threshold
        
        return StressTestResult(
            scenario=scenario,
            pnl=pnl,
            pnl_pct=pnl_pct,
            survives=survives,
            base_value=base_value,
            stressed_value=stressed_value
        )
```

**Crisis Scenario Modeling**:
```python
def model_crisis_scenario(
    self,
    state: VolatilityState
) -> VolatilityState:
    """Model combined 2008 + 2020 crisis scenario"""
    
    crisis_state = state.copy()
    
    # Price shocks
    crisis_state.spot_prices = {
        k: v * 0.65  # 35% crash
        for k, v in state.spot_prices.items()
    }
    
    # Volatility spike
    crisis_state.vix_level = 80  # Extreme fear
    crisis_state.realized_vol_20d = 0.60  # 60% annualized vol
    
    # Correlation breakdown
    crisis_state.correlation_matrix = np.ones_like(state.correlation_matrix) * 0.95
    
    # Vol of vol explosion
    crisis_state.vol_of_vol = 2.0
    
    # Liquidity evaporation (wider spreads)
    crisis_state.bid_ask_spread_multiplier = 5.0
    
    return crisis_state
```

### 8. Risk Authority

**Purpose**: Independent risk oversight with absolute veto power.

**Interface**:
```python
class RiskAuthority:
    def validate_trade(
        self,
        trade: ProposedTrade,
        state: VolatilityState,
        portfolio: Portfolio
    ) -> ValidationResult:
        """Validate trade against all risk limits"""
        
        # Simulate portfolio after trade
        simulated_portfolio = portfolio.copy()
        simulated_portfolio.add_trade(trade)
        
        # Check all constraints
        violations = []
        
        # Position limits
        violations.extend(self._check_position_limits(simulated_portfolio))
        
        # Greeks limits
        violations.extend(self._check_greeks_limits(simulated_portfolio, state))
        
        # Concentration limits
        violations.extend(self._check_concentration_limits(simulated_portfolio))
        
        # Margin requirements
        violations.extend(self._check_margin_requirements(simulated_portfolio))
        
        # Liquidity requirements
        violations.extend(self._check_liquidity(trade, state))
        
        # Regime-conditional limits
        violations.extend(self._check_regime_limits(simulated_portfolio, state))
        
        if len(violations) > 0:
            return ValidationResult(
                approved=False,
                violations=violations,
                reason="Risk limit violations detected"
            )
        
        return ValidationResult(approved=True)
    
    def emergency_action(
        self,
        portfolio: Portfolio,
        state: VolatilityState,
        trigger: EmergencyTrigger
    ) -> EmergencyAction:
        """Take emergency action when risk thresholds breached"""
        
        if trigger.type == "PORTFOLIO_VAR_BREACH":
            # Force reduce positions
            return EmergencyAction(
                action="REDUCE_POSITIONS",
                target_reduction=0.50,  # Cut positions by 50%
                priority="IMMEDIATE"
            )
        
        elif trigger.type == "MARGIN_CALL":
            # Liquidate positions to meet margin
            return EmergencyAction(
                action="LIQUIDATE",
                positions=self._select_liquidation_candidates(portfolio),
                priority="IMMEDIATE"
            )
        
        elif trigger.type == "CORRELATION_BREAKDOWN":
            # Hedge portfolio delta
            return EmergencyAction(
                action="HEDGE_DELTA",
                target_delta=0.0,
                priority="HIGH"
            )
        
        elif trigger.type == "VOLATILITY_SPIKE":
            # Reduce vega exposure
            return EmergencyAction(
                action="REDUCE_VEGA",
                target_vega=portfolio.greeks.vega * 0.5,
                priority="HIGH"
            )
        
        return EmergencyAction(action="HALT_TRADING", priority="IMMEDIATE")
    
    def _check_greeks_limits(
        self,
        portfolio: Portfolio,
        state: VolatilityState
    ) -> List[Violation]:
        """Check portfolio Greeks against limits"""
        
        violations = []
        greeks = portfolio.greeks
        limits = self._get_regime_limits(state.regime)
        
        if abs(greeks.delta) > limits.max_delta:
            violations.append(Violation(
                type="DELTA_LIMIT",
                value=greeks.delta,
                limit=limits.max_delta,
                severity="HIGH"
            ))
        
        if abs(greeks.vega) > limits.max_vega:
            violations.append(Violation(
                type="VEGA_LIMIT",
                value=greeks.vega,
                limit=limits.max_vega,
                severity="HIGH"
            ))
        
        if greeks.gamma < limits.min_gamma:
            violations.append(Violation(
                type="GAMMA_LIMIT",
                value=greeks.gamma,
                limit=limits.min_gamma,
                severity="MEDIUM"
            ))
        
        return violations
```



## Data Models

### Core Data Structures

```python
@dataclass
class VolatilityState:
    """Unified volatility state - single source of truth"""
    timestamp: datetime
    iv_surface: IVSurface
    regime: RegimeState
    regime_probabilities: Dict[str, float]
    correlation_matrix: np.ndarray
    implied_correlation: float
    realized_correlation: float
    vix_level: float
    vix_term_structure: Dict[str, float]
    realized_vol_20d: float
    vol_of_vol: float
    portfolio_greeks: PortfolioGreeks
    spot_prices: Dict[str, float]
    risk_free_rate: float

@dataclass
class OptionStructure:
    """AST representation of option position"""
    ast: OptionNode
    greeks: Greeks
    price: float
    underlying: str
    expiry: date
    legs: List[OptionLeg]

@dataclass
class TargetGreeks:
    """Target exposure specification"""
    delta: float
    delta_tolerance: float
    gamma: float
    gamma_tolerance: float
    vega: float
    vega_tolerance: float
    theta: float
    theta_tolerance: float

@dataclass
class Position:
    """Individual option position"""
    position_id: str
    underlying: str
    option_type: str  # "call" or "put"
    strike: float
    expiry: date
    quantity: int
    entry_price: float
    entry_iv: float
    entry_timestamp: datetime
    greeks: Greeks

@dataclass
class Greeks:
    """Option sensitivities"""
    delta: float
    gamma: float
    vega: float
    theta: float
    rho: float
    vanna: float
    volga: float

@dataclass
class RegimeState:
    """Market regime classification"""
    regime: str  # "low_vol", "high_vol", "crisis", "transition"
    confidence: float
    duration: timedelta
    previous_regime: Optional[str]
    transition_probability: float

@dataclass
class DispersionTrade:
    """Dispersion trading position"""
    direction: str  # "long_dispersion" or "short_dispersion"
    spread: float  # Implied - realized correlation
    index_position: Position
    stock_positions: List[Position]
    entry_timestamp: datetime
    target_exit_spread: float

@dataclass
class RiskMetrics:
    """Portfolio risk metrics"""
    var_95: float
    var_99: float
    var_999: float
    cvar_95: float
    cvar_99: float
    max_drawdown: float
    prob_ruin: float
    sharpe_ratio: float
    sortino_ratio: float

@dataclass
class StressScenario:
    """Stress test scenario definition"""
    name: str
    spot_shock: float  # Percentage change
    vol_shock: float  # Absolute change in vol
    correlation_shock: float  # New correlation level
    liquidity_shock: float  # Spread multiplier
```

### State Persistence

```python
class StatePersistence:
    """Handle state serialization and recovery"""
    
    def save_state(
        self,
        state: VolatilityState,
        path: str
    ) -> None:
        """Persist state to disk"""
        
        state_dict = {
            "timestamp": state.timestamp.isoformat(),
            "iv_surface": self._serialize_surface(state.iv_surface),
            "regime": state.regime,
            "regime_probabilities": state.regime_probabilities,
            "correlation_matrix": state.correlation_matrix.tolist(),
            "vix_level": state.vix_level,
            "portfolio_greeks": asdict(state.portfolio_greeks),
            # ... other fields
        }
        
        with open(path, 'w') as f:
            json.dump(state_dict, f, indent=2)
    
    def load_state(
        self,
        path: str
    ) -> VolatilityState:
        """Restore state from disk"""
        
        with open(path, 'r') as f:
            state_dict = json.load(f)
        
        return VolatilityState(
            timestamp=datetime.fromisoformat(state_dict["timestamp"]),
            iv_surface=self._deserialize_surface(state_dict["iv_surface"]),
            regime=state_dict["regime"],
            # ... other fields
        )
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

Before writing the correctness properties, I need to analyze the acceptance criteria from the requirements document to determine which are testable as properties, examples, or edge cases.

